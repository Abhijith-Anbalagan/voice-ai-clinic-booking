from __future__ import annotations

from datetime import datetime, timedelta, time
from zoneinfo import ZoneInfo
from typing import Optional, List, Dict

from sqlalchemy.orm import Session

from app.models import Doctor, WorkingHour, Leave, Appointment

APP_TZ = ZoneInfo("Asia/Kolkata")


def get_doctors(db: Session) -> list[Doctor]:
    return db.query(Doctor).order_by(Doctor.name.asc()).all()


def doctors_payload(db: Session) -> list[dict]:
    return [
        {"id": d.id, "name": d.name, "specialty": d.specialty}
        for d in get_doctors(db)
    ]


def combine_date_time(d, hhmm: str) -> datetime:
    hh, mm = map(int, hhmm.split(":"))
    return datetime(d.year, d.month, d.day, hh, mm, tzinfo=APP_TZ)


def _aware(dt: datetime) -> datetime:
    """Attach APP_TZ to a naive datetime (SQLite strips tzinfo on read-back)."""
    if dt is None:
        return dt
    if dt.tzinfo is None:
        return dt.replace(tzinfo=APP_TZ)
    return dt


def _naive(dt: datetime) -> datetime:
    """Strip tzinfo so SQLite string comparisons are apples-to-apples."""
    if dt is None:
        return dt
    if dt.tzinfo is not None:
        return dt.replace(tzinfo=None)
    return dt


def patient_has_conflict(db: Session, patient_email: str, start_at: datetime, end_at: datetime) -> bool:
    # Compare naive values — SQLite stores datetimes without tz
    s, e = _naive(start_at), _naive(end_at)
    return db.query(Appointment).filter(
        Appointment.patient_email == patient_email.lower(),
        Appointment.status == "confirmed",
        Appointment.start_at < e,
        Appointment.end_at > s,
    ).first() is not None


def doctor_has_conflict(db: Session, doctor_id: int, start_at: datetime, end_at: datetime) -> bool:
    s, e = _naive(start_at), _naive(end_at)
    appt_conflict = db.query(Appointment).filter(
        Appointment.doctor_id == doctor_id,
        Appointment.status == "confirmed",
        Appointment.start_at < e,
        Appointment.end_at > s,
    ).first() is not None

    leave_conflict = db.query(Leave).filter(
        Leave.doctor_id == doctor_id,
        Leave.start_at < e,
        Leave.end_at > s,
    ).first() is not None

    return appt_conflict or leave_conflict


def doctor_works_at(db: Session, doctor_id: int, start_at: datetime, end_at: datetime) -> bool:
    start_at = _aware(start_at)
    end_at = _aware(end_at)
    weekday = start_at.weekday()
    rows = db.query(WorkingHour).filter(
        WorkingHour.doctor_id == doctor_id,
        WorkingHour.weekday == weekday,
    ).all()

    for row in rows:
        window_start = datetime.combine(start_at.date(), row.start_time, tzinfo=APP_TZ)
        window_end = datetime.combine(start_at.date(), row.end_time, tzinfo=APP_TZ)
        if start_at >= window_start and end_at <= window_end:
            return True
    return False


def find_slots(
    db: Session,
    requested_date,
    doctor_name: Optional[str] = None,
    specialty: Optional[str] = None,
    requested_time: Optional[str] = None,
    daypart: Optional[str] = None,
    limit: int = 3,
) -> List[Dict]:
    doctors_query = db.query(Doctor)

    if doctor_name:
        doctors_query = doctors_query.filter(Doctor.name == doctor_name)
    elif specialty:
        doctors_query = doctors_query.filter(Doctor.specialty.ilike(specialty))

    doctors = doctors_query.order_by(Doctor.name.asc()).all()
    if not doctors:
        return []

    slots: List[Dict] = []
    now = datetime.now(APP_TZ)

    daypart_ranges = {
        "morning": (time(9, 0), time(12, 59)),
        "afternoon": (time(13, 0), time(16, 59)),
        "evening": (time(17, 0), time(19, 0)),
    }

    for doctor in doctors:
        rows = db.query(WorkingHour).filter(
            WorkingHour.doctor_id == doctor.id,
            WorkingHour.weekday == requested_date.weekday(),
        ).all()

        for row in rows:
            current = datetime.combine(requested_date, row.start_time, tzinfo=APP_TZ)
            window_end = datetime.combine(requested_date, row.end_time, tzinfo=APP_TZ)

            while current + timedelta(minutes=doctor.slot_minutes) <= window_end:
                end_at = current + timedelta(minutes=doctor.slot_minutes)

                if current < now:
                    current += timedelta(minutes=doctor.slot_minutes)
                    continue

                if requested_time:
                    hh, mm = map(int, requested_time.split(":"))
                    if current.time() != time(hh, mm):
                        current += timedelta(minutes=doctor.slot_minutes)
                        continue

                if daypart:
                    start_range, end_range = daypart_ranges[daypart]
                    if not (start_range <= current.time() <= end_range):
                        current += timedelta(minutes=doctor.slot_minutes)
                        continue

                if doctor_works_at(db, doctor.id, current, end_at) and not doctor_has_conflict(db, doctor.id, current, end_at):
                    slots.append({
                        "doctor_id": doctor.id,
                        "doctor_name": doctor.name,
                        "specialty": doctor.specialty,
                        "start_at": current,
                        "end_at": end_at,
                    })

                current += timedelta(minutes=doctor.slot_minutes)

    slots.sort(key=lambda x: x["start_at"])
    return slots[:limit]


def create_appointment(
    db: Session,
    *,
    doctor_id: int,
    patient_name: str,
    patient_email: str,
    reason: str,
    start_at: datetime,
    end_at: datetime,
) -> Appointment:
    appt = Appointment(
        doctor_id=doctor_id,
        patient_name=patient_name,
        patient_email=patient_email.lower(),
        reason=reason,
        start_at=_naive(start_at),
        end_at=_naive(end_at),
        status="confirmed",
    )
    db.add(appt)
    db.commit()
    db.refresh(appt)
    return appt