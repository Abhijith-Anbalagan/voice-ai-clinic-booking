import os
import uuid
from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Optional

from dotenv import load_dotenv
from fastapi import FastAPI, Depends
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db import Base, engine, get_db
from app.models import Doctor
from app.services.nlu import (
    extract_email,
    extract_name,
    extract_reason,
    extract_datetime_bits,
    extract_doctor_or_specialty,
)
from app.services.booking import (
    doctors_payload,
    find_slots,
    create_appointment,
    patient_has_conflict,
)

from app.services.emailer import send_invite_email

load_dotenv()

APP_TZ = ZoneInfo(os.getenv("APP_TIMEZONE", "Asia/Kolkata"))
app = FastAPI(title="Voice AI Clinic")
Base.metadata.create_all(bind=engine)

app.mount("/static", StaticFiles(directory="static"), name="static")

SESSIONS: dict[str, dict] = {}


class ChatRequest(BaseModel):
    session_id: Optional[str] = None
    text: str


def get_session(session_id: Optional[str]) -> tuple[str, dict]:
    if not session_id or session_id not in SESSIONS:
        new_id = str(uuid.uuid4())
        SESSIONS[new_id] = {
            "patient_name": None,
            "patient_email": None,
            "doctor_name": None,
            "specialty": None,
            "requested_date": None,
            "requested_time": None,
            "daypart": None,
            "reason": None,
            "slot_choices": [],
        }
        return new_id, SESSIONS[new_id]
    return session_id, SESSIONS[session_id]


def normalize_choice(text: str) -> Optional[int]:
    t = text.lower()
    mapping = {
        "1": 0, "first": 0,
        "2": 1, "second": 1,
        "3": 2, "third": 2,
    }
    for k, v in mapping.items():
        if k in t:
            return v
    return None


@app.get("/")
def home():
    return FileResponse("static/index.html")


@app.get("/api/doctors")
def list_doctors(db: Session = Depends(get_db)):
    return doctors_payload(db)


@app.post("/api/chat")
def chat(payload: ChatRequest, db: Session = Depends(get_db)):
    session_id, state = get_session(payload.session_id)
    text = payload.text.strip()

    docs = doctors_payload(db)
    doc_info = extract_doctor_or_specialty(text, docs)
    bits = extract_datetime_bits(text, timezone=str(APP_TZ))

    state["patient_name"] = extract_name(text) or state["patient_name"]
    state["patient_email"] = extract_email(text) or state["patient_email"]
    state["doctor_name"] = doc_info["doctor_name"] or state["doctor_name"]
    state["specialty"] = doc_info["specialty"] or state["specialty"]
    state["requested_date"] = bits["requested_date"] or state["requested_date"]
    state["requested_time"] = bits["requested_time"] or state["requested_time"]
    state["daypart"] = bits["daypart"] or state["daypart"]
    state["reason"] = extract_reason(text) or state["reason"] or "General consultation"

    # If user is choosing among proposed slots
    if state["slot_choices"]:
        idx = normalize_choice(text)
        if idx is not None and idx < len(state["slot_choices"]):
            slot = state["slot_choices"][idx]

            if patient_has_conflict(db, state["patient_email"], slot["start_at"], slot["end_at"]):
                return {
                    "session_id": session_id,
                    "reply": "You already have another appointment that overlaps with that time. Please choose a different slot.",
                    "done": False,
                }

            appt = create_appointment(
                db,
                doctor_id=slot["doctor_id"],
                patient_name=state["patient_name"],
                patient_email=state["patient_email"],
                reason=state["reason"],
                start_at=slot["start_at"],
                end_at=slot["end_at"],
            )

            ok, msg = send_invite_email(
                patient_email=state["patient_email"],
                patient_name=state["patient_name"],
                doctor_name=slot["doctor_name"],
                start_at=slot["start_at"],
                end_at=slot["end_at"],
                reason=state["reason"],
                appointment_id=appt.id,
            )

            nice = slot["start_at"].astimezone(APP_TZ).strftime("%A, %d %B at %I:%M %p")
            state["slot_choices"] = []

            return {
                "session_id": session_id,
                "reply": f"Your appointment is confirmed with {slot['doctor_name']} on {nice}. Calendar invite status: {msg}.",
                "done": True,
            }

    # Ask for missing info
    if not state["doctor_name"] and not state["specialty"]:
        doctor_names = ", ".join([d["name"] for d in docs])
        return {
            "session_id": session_id,
            "reply": f"Which doctor or specialty would you like? Available doctors are {doctor_names}.",
            "done": False,
        }

    if not state["requested_date"]:
        return {
            "session_id": session_id,
            "reply": "What date would you like? You can say something like next Tuesday or tomorrow afternoon.",
            "done": False,
        }

    if not state["requested_time"] and not state["daypart"]:
        return {
            "session_id": session_id,
            "reply": "What time works for you? You can say a specific time like 3 PM, or say morning or afternoon.",
            "done": False,
        }

    if not state["patient_name"]:
        return {
            "session_id": session_id,
            "reply": "What is your full name?",
            "done": False,
        }

    if not state["patient_email"]:
        return {
            "session_id": session_id,
            "reply": "What email address should I send the calendar invite to?",
            "done": False,
        }

    slots = find_slots(
        db,
        requested_date=state["requested_date"],
        doctor_name=state["doctor_name"],
        specialty=state["specialty"],
        requested_time=state["requested_time"],
        daypart=state["daypart"],
        limit=3,
    )

    if not slots:
        return {
            "session_id": session_id,
            "reply": "I could not find an available slot that matches your request. Please try another date or time.",
            "done": False,
        }

    # Exact time match with one slot -> auto-book
    if state["requested_time"] and len(slots) == 1:
        slot = slots[0]

        if patient_has_conflict(db, state["patient_email"], slot["start_at"], slot["end_at"]):
            return {
                "session_id": session_id,
                "reply": "You already have another appointment that overlaps with that time. Please choose a different time.",
                "done": False,
            }

        appt = create_appointment(
            db,
            doctor_id=slot["doctor_id"],
            patient_name=state["patient_name"],
            patient_email=state["patient_email"],
            reason=state["reason"],
            start_at=slot["start_at"],
            end_at=slot["end_at"],
        )

        ok, msg = send_invite_email(
            patient_email=state["patient_email"],
            patient_name=state["patient_name"],
            doctor_name=slot["doctor_name"],
            start_at=slot["start_at"],
            end_at=slot["end_at"],
            reason=state["reason"],
            appointment_id=appt.id,
        )

        nice = slot["start_at"].astimezone(APP_TZ).strftime("%A, %d %B at %I:%M %p")
        return {
            "session_id": session_id,
            "reply": f"Your appointment is confirmed with {slot['doctor_name']} on {nice}. Calendar invite status: {msg}.",
            "done": True,
        }

    state["slot_choices"] = slots
    options = []
    for i, s in enumerate(slots, start=1):
        nice = s["start_at"].astimezone(APP_TZ).strftime("%A %d %B at %I:%M %p")
        options.append(f"Option {i}: {s['doctor_name']} on {nice}")

    return {
        "session_id": session_id,
        "reply": "I found these available slots. " + ". ".join(options) + ". Please say first, second, or third.",
        "done": False,
    }