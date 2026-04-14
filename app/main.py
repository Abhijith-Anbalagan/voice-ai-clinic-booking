"""
app/main.py — MediBook FastAPI application
"""

from __future__ import annotations

import os
import uuid
from datetime import datetime
from typing import Optional
from zoneinfo import ZoneInfo

from fastapi import FastAPI, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db import get_db, engine
from app.models import Doctor  # noqa: F401 — ensures Base sees all models
from app.db import Base
from app.services import booking, nlu
from app.services.emailer import send_invite_email

# ── Bootstrap ─────────────────────────────────────────────────────────────────
Base.metadata.create_all(bind=engine)

APP_TZ = ZoneInfo(os.getenv("APP_TIMEZONE", "Asia/Kolkata"))

app = FastAPI(title="MediBook Voice Clinic")

# Static files live in  voice-ai/app/static/
_STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
app.mount("/static", StaticFiles(directory=_STATIC_DIR), name="static")


# ── In-memory session store ───────────────────────────────────────────────────
_SESSIONS: dict[str, dict] = {}

_EMPTY_STATE = dict(
    doctor_name=None,
    specialty=None,
    requested_date=None,
    requested_time=None,
    daypart=None,
    patient_name=None,
    patient_email=None,
    reason=None,
    doctor_id=None,
    confirmed_slot=None,   # {"start_at": datetime, "end_at": datetime, "doctor_name": str}
    pending_slots=None,    # list of slot dicts waiting for user to pick
)


def _new_session() -> tuple[str, dict]:
    sid = str(uuid.uuid4())
    _SESSIONS[sid] = {k: v for k, v in _EMPTY_STATE.items()}
    return sid, _SESSIONS[sid]


def _get_session(session_id: Optional[str]) -> tuple[str, dict]:
    if session_id and session_id in _SESSIONS:
        return session_id, _SESSIONS[session_id]
    return _new_session()


# ── Pydantic schemas ──────────────────────────────────────────────────────────
class ChatRequest(BaseModel):
    session_id: Optional[str] = None
    text: str


class ChatResponse(BaseModel):
    session_id: str
    reply: str
    done: bool = False
    state: dict = {}


# ── Routes ────────────────────────────────────────────────────────────────────
@app.get("/", include_in_schema=False)
def serve_index():
    index_path = os.path.join(_STATIC_DIR, "index.html")
    return FileResponse(index_path)


@app.post("/api/reset")
def reset_session(body: dict = {}):
    """Explicitly reset a session (called by 'Book Another' button)."""
    sid = body.get("session_id")
    if sid and sid in _SESSIONS:
        del _SESSIONS[sid]
    new_sid, _ = _new_session()
    return JSONResponse({"session_id": new_sid})


@app.post("/api/chat", response_model=ChatResponse)
def chat(req: ChatRequest, db: Session = Depends(get_db)):
    sid, state = _get_session(req.session_id)
    text = req.text.strip()

    # ── 1. Load doctor list for NLU ───────────────────────────────────────────
    doctors = booking.doctors_payload(db)

    # ── 2. Extract everything we can from the utterance ───────────────────────
    dt_bits  = nlu.extract_datetime_bits(text)
    doc_bits = nlu.extract_doctor_or_specialty(text, doctors)
    name     = nlu.extract_name(text)
    email    = nlu.extract_email(text)
    reason   = nlu.extract_reason(text)

    # Merge into state — never overwrite an existing value with None
    for key, val in doc_bits.items():
        if val:
            state[key] = val
    for key in ("requested_date", "requested_time", "daypart"):
        if dt_bits.get(key):
            state[key] = dt_bits[key]
    if name and not state["patient_name"]:
        state["patient_name"] = name
    if email:
        state["patient_email"] = email
    if reason and not state["reason"]:
        state["reason"] = reason

    # ── 3. Handle slot-selection if we offered options last turn ──────────────
    if state.get("pending_slots"):
        slots = state["pending_slots"]
        pick  = _parse_slot_pick(text, len(slots))
        if pick is not None:
            chosen = slots[pick]
            state["confirmed_slot"] = chosen
            state["doctor_id"]      = chosen["doctor_id"]
            state["doctor_name"]    = chosen["doctor_name"]
            state["requested_date"] = chosen["start_at"].date()
            state["requested_time"] = chosen["start_at"].strftime("%H:%M")
            state["pending_slots"]  = None
        elif _is_none_of_these(text):
            state["pending_slots"]  = None
            state["requested_date"] = None
            state["requested_time"] = None
            return ChatResponse(
                session_id=sid,
                reply="No problem. What date or time would you prefer?",
                state=_safe_state(state),
            )

    # ── 4. Dialogue manager ───────────────────────────────────────────────────
    reply, done = _build_reply(state, db)
    return ChatResponse(session_id=sid, reply=reply, done=done, state=_safe_state(state))


# ── Dialogue helpers ──────────────────────────────────────────────────────────

def _safe_state(state: dict) -> dict:
    out = {}
    for k, v in state.items():
        if isinstance(v, datetime):
            out[k] = v.isoformat()
        elif hasattr(v, "isoformat"):   # date
            out[k] = v.isoformat()
        elif isinstance(v, list):
            out[k] = None               # don't serialise slot objects to frontend
        else:
            out[k] = v
    return out


def _parse_slot_pick(text: str, n: int) -> Optional[int]:
    t = text.lower()
    for i, word in enumerate(["first", "second", "third", "fourth", "fifth"][:n]):
        if word in t:
            return i
    for i in range(1, n + 1):
        if str(i) in t:
            return i - 1
    return None


def _is_none_of_these(text: str) -> bool:
    t = text.lower()
    return any(p in t for p in ["none", "neither", "other", "different", "another", "no thanks"])


def _fmt_slot(slot: dict) -> str:
    dt: datetime = slot["start_at"]
    return dt.strftime("%A %d %B at %I:%M %p")


def _build_reply(state: dict, db: Session) -> tuple[str, bool]:

    # A. Need doctor / specialty
    if not state["doctor_name"] and not state["specialty"]:
        return (
            "Which doctor or specialty would you like to see? "
            "We have Dr Priya Sharma in cardiology and Dr Arjun Mehta in dermatology."
        ), False

    # B. Need date
    if not state["requested_date"]:
        name = state["doctor_name"] or state["specialty"]
        return f"Great! What date would you like to see {name}?", False

    # C. Find slots (if not already confirmed)
    if not state.get("confirmed_slot"):
        slots = booking.find_slots(
            db,
            requested_date=state["requested_date"],
            doctor_name=state.get("doctor_name"),
            specialty=state.get("specialty"),
            requested_time=state.get("requested_time"),
            daypart=state.get("daypart"),
            limit=3,
        )

        # Widen search if no slots at the requested time/daypart
        if not slots and (state.get("requested_time") or state.get("daypart")):
            state["requested_time"] = None
            state["daypart"]        = None
            slots = booking.find_slots(
                db,
                requested_date=state["requested_date"],
                doctor_name=state.get("doctor_name"),
                specialty=state.get("specialty"),
                limit=3,
            )

        if not slots:
            state["requested_date"] = None
            state["requested_time"] = None
            return (
                "Sorry, there are no available slots on that date. "
                "Could you try a different date?"
            ), False

        if len(slots) == 1:
            state["confirmed_slot"] = slots[0]
            state["doctor_id"]      = slots[0]["doctor_id"]
            state["doctor_name"]    = slots[0]["doctor_name"]
        else:
            options = "; ".join(
                f"option {i+1}: {_fmt_slot(s)}" for i, s in enumerate(slots)
            )
            state["pending_slots"] = slots
            return (
                f"I found a few openings with {slots[0]['doctor_name']}. "
                f"{options}. Which would you prefer?"
            ), False

    # D. Need patient name
    if not state["patient_name"]:
        return "Could I get your full name please?", False

    # E. Need email
    if not state["patient_email"]:
        return (
            "What email address should I send the confirmation to? "
            "You can spell it out if that's easier."
        ), False

    # F. All info gathered — create the booking
    slot   = state["confirmed_slot"]
    reason = state.get("reason") or "General consultation"

    if booking.patient_has_conflict(
        db, state["patient_email"], slot["start_at"], slot["end_at"]
    ):
        return (
            "It looks like you already have an appointment at that time. "
            "Would you like to pick a different slot?"
        ), False

    appt = booking.create_appointment(
        db,
        doctor_id     = state["doctor_id"],
        patient_name  = state["patient_name"],
        patient_email = state["patient_email"],
        reason        = reason,
        start_at      = slot["start_at"],
        end_at        = slot["end_at"],
    )

    send_invite_email(
        patient_email  = state["patient_email"],
        patient_name   = state["patient_name"],
        doctor_name    = slot["doctor_name"],
        start_at       = slot["start_at"],
        end_at         = slot["end_at"],
        reason         = reason,
        appointment_id = appt.id,
    )

    nice_dt = slot["start_at"].strftime("%A %d %B at %I:%M %p")
    return (
        f"All done! Your appointment with {slot['doctor_name']} is confirmed for "
        f"{nice_dt} IST. A confirmation email with a calendar invite has been sent to "
        f"{state['patient_email']}. See you then!"
    ), True