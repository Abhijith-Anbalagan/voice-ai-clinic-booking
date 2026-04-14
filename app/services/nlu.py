import re
from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Optional, Dict, Any

from dateparser.search import search_dates

EMAIL_RE = re.compile(r'[\w\.-]+@[\w\.-]+\.\w+')
NAME_PATTERNS = [
    re.compile(r"\bmy name is ([a-zA-Z ]{2,60})", re.I),
    re.compile(r"\bi am ([a-zA-Z ]{2,60})", re.I),
    re.compile(r"\bthis is ([a-zA-Z ]{2,60})", re.I),
]
TIME_RE = re.compile(r"\b(at\s+)?(\d{1,2})(?::(\d{2}))?\s*(am|pm)\b", re.I)


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
        "email is ",
        "it is ",
        "it's ",
        "send it to ",
        "send to ",
        "mail id is ",
        "my mail is ",
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

    if len(text.split()) == 1 and text.replace(" ", "").isalpha():
        return text.title()

    for pattern in NAME_PATTERNS:
        m = pattern.search(text)
        if m:
            return " ".join(m.group(1).strip().split()).title()

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

        pieces = doc["name"].lower().replace("dr ", "").split()
        if pieces and pieces[0] in t:
            found_doctor = doc["name"]

    return {"doctor_name": found_doctor, "specialty": found_specialty}