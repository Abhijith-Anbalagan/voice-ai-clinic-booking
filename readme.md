# MediBook — Voice AI Clinic Booking

🔗 **Live App:** https://medibook-6tml.onrender.com  

A voice-first doctor appointment booking system. Speak naturally in your browser; the AI assistant converses back through audio and confirms the booking via a calendar-invite email.

---

## Requirements Met

| ID | Requirement | How |
|----|-------------|-----|
| R1 | Book by speaking, no app install | Web Speech API in Chrome — works cold in any modern browser |
| R2 | System converses back through audio | SpeechSynthesis API reads every assistant reply aloud |
| R3 | Check doctor availability | `find_slots()` in `booking.py` queries working hours and existing appointments before offering slots |
| R4 | Detect scheduling conflicts | `patient_has_conflict()` + `doctor_has_conflict()` block double-bookings |
| R5 | Calendar invite to patient email | Gmail SMTP + RFC-5545 `.ics` attachment with branded HTML email |
| R6 | Open-source scheduling backend | **SQLite + SQLAlchemy ORM** — 100 % open-source; optional Easy!Appointments REST client also included (`easyappointments.py`) |
| R7 | Free-tier only | Render.com free web service + SQLite disk; Gmail free SMTP |
| R8 | Public URL | Deployed on Render.com (`*.onrender.com`) |
| R9 | Works cold without instructions | Intro message auto-plays; assistant prompts for every missing piece of info |
| R10 | Thank-you + Book Another button | Confirmation screen shown; "Book Another Appointment" resets the session |

---

## Local Setup

```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt

# copy .env.example → .env and fill in values
cp .env.example .env

python -m app.seed              # populate doctors + sample data
uvicorn app.main:app --reload   # open http://127.0.0.1:8000
```

### `.env` variables

```
APP_TIMEZONE=Asia/Kolkata
DATABASE_URL=sqlite:///./clinic.db

# Gmail SMTP — use an App Password (not your account password)
# https://myaccount.google.com/apppasswords
EMAIL_FROM=you@gmail.com
EMAIL_PASSWORD=xxxx xxxx xxxx xxxx
```
---

# 🎥 Live Demo

👉 Try it here:  
https://medibook-6tml.onrender.com  

🗣️ Example:  
“Book a cardiology appointment tomorrow morning”

---


## Architecture

```
Browser (HTTPS)
  │
  ├── GET  /            → index.html  (voice UI)
  ├── GET  /static/*    → app.js, styles.css
  └── POST /api/chat    → FastAPI session handler
                              │
                    ┌─────────┴──────────┐
                    │   NLU layer         │  (nlu.py — regex + dateparser)
                    │   Booking layer     │  (booking.py — SQLAlchemy ORM)
                    │   Email layer       │  (emailer.py — SMTP + .ics)
                    └─────────────────────┘
                              │
                         SQLite DB  (clinic.db)
```
