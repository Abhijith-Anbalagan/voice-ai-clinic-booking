# REFLECTION.md — MediBook Voice AI

## Top 3 Practices Used

### 1. State-driven architecture
Maintained a structured session state (doctor, date, time, name, email) to ensure a predictable and guided conversation flow.

### 2. Deterministic NLU (no external AI)
Used regex and dateparser instead of LLM APIs. This made the system fast, reliable, and free to run without external dependencies.

### 3. Human-in-the-loop confirmation
Added a review modal before final booking so users can verify and correct details, preventing errors from speech recognition.

---

## One Challenge Faced

Handling spoken email input accurately.

Example:
"john dot doe at gmail dot com"

Speech recognition often returns informal formats, which are not valid emails.

---

## How I Solved It

Implemented a normalization pipeline:
- Converted spoken words (dot → ., at → @)
- Cleaned unwanted characters
- Validated format using regex

This significantly improved accuracy for voice-based email input.

---

## Final Thoughts

The focus of this project was to balance:
- Simplicity (no login, no setup)
- Reliability (confirmation step)
- Real-world usability (voice-first interaction)

This approach ensures the system is both user-friendly and robust.