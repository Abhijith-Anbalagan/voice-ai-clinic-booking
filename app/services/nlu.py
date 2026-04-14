import re
from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Optional, Dict, Any

from dateparser.search import search_dates

EMAIL_RE = re.compile(r'[\w\.-]+@[\w\.-]+\.\w+')
NAME_PATTERNS = [
    re.compile(r"\bmy name is ([a-zA-Z ]{2,60})", re.I),
    re.compile(r"\bi(?:'m| am) ([a-zA-Z ]{2,60})", re.I),
    re.compile(r"\bthis is ([a-zA-Z ]{2,60})", re.I),
    re.compile(r"\bcall me ([a-zA-Z ]{2,60})", re.I),
    re.compile(r"\bname['\s]*s? ([a-zA-Z ]{2,60})", re.I),
]
TIME_RE = re.compile(r"\b(at\s+)?(\d{1,2})(?::(\d{2}))?\s*(am|pm)\b", re.I)

# Words that must never be mistaken for a patient name
_STOPWORDS = {
    # booking-domain words
    "yes", "no", "ok", "okay", "sure", "please", "thanks", "thank",
    "hello", "hi", "hey",
    "tomorrow", "today", "monday", "tuesday", "wednesday", "thursday",
    "friday", "saturday", "sunday",
    "morning", "afternoon", "evening", "night",
    "appointment", "booking", "schedule", "book",
    "doctor", "dr", "clinic",
    "cardiology", "dermatology", "specialty",
    "email", "mail", "confirm", "cancel",
    "first", "second", "third", "one", "two", "three",
    "none", "next", "other", "different", "another",
}


def detect_daypart(text: str) -> Optional[str]:
    t = text.lower()
    if "morning" in t:
        return "morning"
    if "afternoon" in t:
        return "afternoon"
    if "evening" in t:
        return "evening"
    return None


def normalize_spoken_email(text: str) -> str:
    t = text.strip().lower()

    # Remove common intro phrases
    intro_phrases = [
        "my email is ",
        "my email address is ",
        "email is ",
        "email address is ",
        "it is ",
        "it's ",
        "send it to ",
        "send to ",
        "mail id is ",
        "my mail is ",
        "the email is ",
    ]
    for phrase in intro_phrases:
        if t.startswith(phrase):
            t = t[len(phrase):]

    # Convert spoken separators/domains
    replacements = {
        " at the rate ": "@",
        " at rate ": "@",
        " at ": "@",
        " underscore ": "_",
        " under score ": "_",
        " dash ": "-",
        " hyphen ": "-",
        " minus ": "-",
        " dot ": ".",
        " point ": ".",
        " period ": ".",
        " space ": "",
    }

    t = f" {t} "
    for old, new in replacements.items():
        t = t.replace(old, new)

    # Fix common spoken domain endings
    domain_fixes = {
        " gmail com": " gmail.com",
        " yahoo com": " yahoo.com",
        " outlook com": " outlook.com",
        " hotmail com": " hotmail.com",
        " icloud com": " icloud.com",
        " protonmail com": " protonmail.com",
    }
    for old, new in domain_fixes.items():
        t = t.replace(old, new)

    # Remove all spaces around separators, then all remaining spaces
    t = re.sub(r"\s*@\s*", "@", t)
    t = re.sub(r"\s*\.\s*", ".", t)
    t = re.sub(r"\s*_\s*", "_", t)
    t = re.sub(r"\s*-\s*", "-", t)
    t = re.sub(r"\s+", "", t)

    # Keep only email-safe characters
    t = re.sub(r"[^a-z0-9@._\-+]", "", t)

    return t


def extract_name(text: str) -> Optional[str]:
    text = text.strip()
    lower = text.lower()

    # Do not treat email-like input as name
    if "@" in text or " at " in lower or " dot " in lower:
        return None

    # Try explicit name-introduction patterns first (most reliable)
    for pattern in NAME_PATTERNS:
        m = pattern.search(text)
        if m:
            candidate = " ".join(m.group(1).strip().split()).title()
            # Reject if it's entirely stopwords
            words = candidate.lower().split()
            if all(w in _STOPWORDS for w in words):
                continue
            return candidate

    # Only accept a bare word/phrase as a name if it looks like a proper name:
    # - 1–4 words, all alphabetic
    # - At least one word is NOT in stopwords
    # - Does NOT match any NLU trigger words
    words = text.split()
    if 1 <= len(words) <= 4 and all(w.replace("-", "").isalpha() for w in words):
        lower_words = [w.lower() for w in words]
        # All single-word inputs are checked against stopwords
        if len(words) == 1 and lower_words[0] in _STOPWORDS:
            return None
        # For multi-word inputs, reject only if every word is a stopword
        if len(words) > 1 and all(w in _STOPWORDS for w in lower_words):
            return None
        # Must start with a capital letter (proper name heuristic)
        if words[0][0].isupper():
            return " ".join(w.title() for w in words)

    return None


def extract_email(text: str) -> Optional[str]:
    # First try direct normal email
    direct = EMAIL_RE.search(text)
    if direct:
        return direct.group(0).lower()

    # Then try spoken email normalization
    normalized = normalize_spoken_email(text)
    spoken = EMAIL_RE.search(normalized)
    if spoken:
        return spoken.group(0).lower()

    return None


def extract_reason(text: str) -> Optional[str]:
    t = text.lower()
    for trigger in ["for ", "about ", "regarding "]:
        idx = t.find(trigger)
        if idx != -1:
            reason = text[idx + len(trigger):].strip()
            # Don't return very short or stopword-only reasons
            if len(reason) > 3:
                return reason[:120]
    return None


def extract_datetime_bits(text: str, timezone: str = "Asia/Kolkata") -> Dict[str, Any]:
    now = datetime.now(ZoneInfo(timezone))
    result: Dict[str, Any] = {
        "requested_date": None,
        "requested_time": None,
        "daypart": detect_daypart(text),
    }

    matches = search_dates(
        text,
        settings={
            "PREFER_DATES_FROM": "future",
            "RELATIVE_BASE": now,
        },
    )

    if matches:
        matches = sorted(matches, key=lambda x: len(x[0]), reverse=True)
        _, dt = matches[0]
        result["requested_date"] = dt.date()

    time_match = TIME_RE.search(text)
    if time_match:
        hour = int(time_match.group(2))
        minute = int(time_match.group(3) or 0)
        ampm = time_match.group(4).lower()
        if ampm == "pm" and hour != 12:
            hour += 12
        if ampm == "am" and hour == 12:
            hour = 0
        result["requested_time"] = f"{hour:02d}:{minute:02d}"

    return result


def extract_doctor_or_specialty(text: str, doctors: list[dict]) -> Dict[str, Optional[str]]:
    t = text.lower()
    found_doctor = None
    found_specialty = None

    for doc in doctors:
        if doc["name"].lower() in t:
            found_doctor = doc["name"]
        if doc["specialty"].lower() in t:
            found_specialty = doc["specialty"]

        # Match last name ("Sharma", "Mehta") or first name without "Dr"
        pieces = doc["name"].lower().replace("dr ", "").split()
        for piece in pieces:
            if piece and piece in t:
                found_doctor = doc["name"]

    return {"doctor_name": found_doctor, "specialty": found_specialty}