from datetime import datetime, timedelta, time
from zoneinfo import ZoneInfo

from app.db import Base, engine, SessionLocal
from app.models import Doctor, WorkingHour, Leave, Appointment

TZ = ZoneInfo("Asia/Kolkata")


def next_weekday(base: datetime, target_weekday: int) -> datetime:
    days_ahead = (target_weekday - base.weekday()) % 7
    if days_ahead == 0:
        days_ahead = 7
    return base + timedelta(days=days_ahead)


def seed():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    try:
        db.query(Appointment).delete()
        db.query(Leave).delete()
        db.query(WorkingHour).delete()
        db.query(Doctor).delete()
        db.commit()

        d1 = Doctor(
            name="Dr Priya Sharma",
            specialty="cardiology",
            email="priya.sharma@clinic.local",
            timezone="Asia/Kolkata",
            slot_minutes=30,
        )
        d2 = Doctor(
            name="Dr Arjun Mehta",
            specialty="dermatology",
            email="arjun.mehta@clinic.local",
            timezone="Asia/Kolkata",
            slot_minutes=30,
        )
        db.add_all([d1, d2])
        db.commit()
        db.refresh(d1)
        db.refresh(d2)

        # Priya: Mon-Fri 9-13 and 14-17
        for weekday in range(0, 5):
            db.add(WorkingHour(doctor_id=d1.id, weekday=weekday, start_time=time(9, 0), end_time=time(13, 0)))
            db.add(WorkingHour(doctor_id=d1.id, weekday=weekday, start_time=time(14, 0), end_time=time(17, 0)))

        # Arjun: Tue-Sat 10-14 and 15-18
        for weekday in range(1, 6):
            db.add(WorkingHour(doctor_id=d2.id, weekday=weekday, start_time=time(10, 0), end_time=time(14, 0)))
            db.add(WorkingHour(doctor_id=d2.id, weekday=weekday, start_time=time(15, 0), end_time=time(18, 0)))

        now = datetime.now(TZ)

        # Priya leave: next Wednesday 2pm-5pm  (store NAIVE — SQLite has no tz)
        priya_leave_day = next_weekday(now, 2).replace(hour=14, minute=0, second=0, microsecond=0, tzinfo=None)
        db.add(Leave(
            doctor_id=d1.id,
            start_at=priya_leave_day,
            end_at=priya_leave_day.replace(hour=17),
            reason="Conference"
        ))

        # Arjun leave: next Friday full day  (store NAIVE)
        arjun_leave_day = next_weekday(now, 4).replace(hour=10, minute=0, second=0, microsecond=0, tzinfo=None)
        db.add(Leave(
            doctor_id=d2.id,
            start_at=arjun_leave_day,
            end_at=arjun_leave_day.replace(hour=18),
            reason="Personal leave"
        ))

        # Existing appointment to test conflict handling  (store NAIVE)
        appt_day = next_weekday(now, 1).replace(hour=10, minute=30, second=0, microsecond=0, tzinfo=None)
        db.add(Appointment(
            doctor_id=d1.id,
            patient_name="Existing Patient",
            patient_email="existing@example.com",
            reason="Follow-up",
            start_at=appt_day,
            end_at=appt_day + timedelta(minutes=30),
            status="confirmed",
        ))

        db.commit()
        print("Seed complete.")
    finally:
        db.close()


if __name__ == "__main__":
    seed()