# DECISIONS.md — MediBook Voice AI Clinic Booking

## What I Built

A voice-first doctor appointment booking system that runs entirely in the browser. The user speaks naturally; the AI assistant extracts intent (doctor/specialty, date/time, name, email) through a rule-based NLU layer, checks real availability via SQLite/SQLAlchemy, presents a **review modal** before finalising, and sends a branded HTML email with an RFC-5545 `.ics` calendar attachment.

### Key pieces

| Layer | Choice | Reason |
|---|---|---|
| Speech input | Web Speech API (`webkitSpeechRecognition`) | Zero install, zero cost, Chrome/Edge natively supported |
| Speech output | Web Speech Synthesis API | Same — built into every modern browser |
| Backend | FastAPI + Uvicorn | Async-friendly, tiny footprint, auto-docs |
| ORM / DB | SQLAlchemy + SQLite | 100 % open-source; zero infra cost; sufficient for a single-service clinic demo |
| NLU | Custom regex + `dateparser` | No LLM API key needed; deterministic; fast; handles Indian English well enough |
| Email | Gmail SMTP + `smtplib` | Free; works with App Passwords; no third-party dependency |
| Hosting | Render.com free web service + 1 GB persistent disk | Meets "free tier only" requirement; persistent disk keeps SQLite alive across deploys |

---

## UX Decisions

### Start screen gate
The original code immediately spoke the greeting on page load AND rendered it as a chat bubble, causing a double-message. The fix: show a full-screen **Start Booking** overlay. The greeting fires exactly once — when the user explicitly taps the button. `introPlayed` flag then prevents any repeat.

### Review / Confirm modal
After the NLU layer has collected all four required fields (doctor, date/time, name, email), instead of immediately calling `create_appointment`, the frontend intercepts the flow and displays an editable review modal. The user can:
- Read back exactly what was understood
- Edit any field inline (e.g. correct a mis-heard email address)
- Click **Confirm Booking** to send a synthetic confirmation utterance to the server, or **Go Back** to re-state details

This prevents irreversible bookings caused by speech-recognition errors — a real problem for proper nouns (names, email local-parts).

### Auto-restart listening
After the assistant finishes speaking, a 600 ms timer re-opens the microphone. The user can interrupt by tapping the mic or speaking; pressing Stop halts the loop.

---

## What I Chose NOT to Build

| Feature | Decision |
|---|---|
| LLM-powered NLU (GPT/Claude) | Not needed for a constrained booking flow. Regex + dateparser handles the happy path reliably and is deterministic. |
| Multi-doctor specialties / search | The demo seeds 2 doctors; the `find_slots` layer already supports any number. Extending is a seed-data concern, not a code change. |
| User accounts / login | Requirement R1 explicitly says "no login". Email is the patient identifier. |
| Cancellation / rescheduling | Out of scope per requirements. The data model supports status changes; the dialogue layer does not. |
| Easy!Appointments integration | Included as `easyappointments.py` but disabled by default. Requires a self-hosted Easy!Appointments server; SQLite is simpler for the demo. |
| SMS / WhatsApp notifications | Would require Twilio or similar, which has no credibly free tier for production use. |
| Streaming TTS (ElevenLabs, etc.) | Browser SpeechSynthesis is free and synchronous; good enough for a clinic context. |

---

## Hosting Approach

```
Render.com free web service
  └── Python 3.11 runtime
  └── Build: pip install + python -m app.seed
  └── Start: uvicorn app.main:app --host 0.0.0.0 --port $PORT
  └── Disk: 1 GB persistent at /opt/render/project/src  (clinic.db lives here)
```

HTTPS is provided automatically by Render — required for `getUserMedia` / Web Speech API in browsers.

### Free-tier limits that could affect a live test

| Limit | Impact |
|---|---|
| **Render free: 0.1 CPU, 512 MB RAM** | Cold starts take ~30 s after 15 min idle. First request slow; subsequent requests fine. |
| **Render free: instance sleeps after 15 min idle** | Evaluators should hit the URL once and wait for wake-up before the demo. |
| **SQLite on disk** | Not suitable for multi-replica or high-concurrency. Fine for a demo; breaks if Render restarts and the disk is not mounted correctly. |
| **Gmail SMTP: 500 emails/day** | Ample for evaluation. |
| **Web Speech API: Chrome/Edge only** | Safari and Firefox do not support `webkitSpeechRecognition`. Manual text input fallback is always available. |

---

## Architecture Diagram

```
Browser (HTTPS)
  │
  ├── GET  /            → index.html  (voice UI, Start screen gate)
  ├── GET  /static/*    → app.js, styles.css
  └── POST /api/chat    → FastAPI session handler
                              │
                    ┌─────────┴──────────┐
                    │  NLU layer          │  regex + dateparser
                    │  Booking layer      │  SQLAlchemy ORM
                    │  Email layer        │  SMTP + .ics
                    └─────────────────────┘
                              │
                         SQLite DB  (clinic.db)
```

## Conversation State Machine

```
[Start Screen]
      │ user clicks "Start Booking"
      ▼
[Greet + ask doctor/specialty]
      │
      ▼
[Ask date]  ──► if no slots: ask different date
      │
      ▼
[Offer slots]  ──► user picks one
      │
      ▼
[Ask patient name]
      │
      ▼
[Ask email]
      │
      ▼
[Review Modal] ──► user edits if needed ──► Go Back
      │
      │ Confirm
      ▼
[Create appointment + Send email]
      │
      ▼
[Confirmed card + "Book Another" button]
```