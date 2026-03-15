import re
from datetime import date, datetime, timedelta
from typing import Optional

SPECIALIZATIONS = [
    "cardiologist",
    "dermatologist",
    "neurologist",
    "orthopedic",
    "pediatrician",
    "general physician",
]

SPECIALIZATION_SYNONYMS = {
    "cardiologist": ["cardio", "heart", "chest pain", "bp", "blood pressure"],
    "dermatologist": ["skin", "rash", "acne", "eczema"],
    "neurologist": ["migraine", "headache", "seizure", "nerve"],
    "orthopedic": ["bone", "joint", "knee", "back pain", "fracture"],
    "pediatrician": ["child", "baby", "infant", "kid"],
    "general physician": ["fever", "cold", "cough", "flu", "general checkup"],
}


def find_specialization(text: str) -> Optional[str]:
    lowered = text.lower()
    for spec in SPECIALIZATIONS:
        if spec in lowered:
            return spec
    for spec, keywords in SPECIALIZATION_SYNONYMS.items():
        if any(keyword in lowered for keyword in keywords):
            return spec
    return None


def extract_date(text: str) -> Optional[date]:
    lowered = text.lower()
    if "tomorrow" in lowered:
        return date.today() + timedelta(days=1)
    if "today" in lowered:
        return date.today()

    try:
        import dateparser
    except ImportError:
        dateparser = None

    if dateparser:
        parsed = dateparser.parse(
            text,
            settings={"PREFER_DATES_FROM": "future", "RELATIVE_BASE": datetime.now()},
        )
        if parsed:
            return parsed.date()

    match = re.search(r"\b(\d{4}-\d{2}-\d{2})\b", text)
    if match:
        try:
            return datetime.strptime(match.group(1), "%Y-%m-%d").date()
        except ValueError:
            return None
    return None


def extract_time(text: str) -> Optional[str]:
    lowered = text.lower()
    if "noon" in lowered:
        return "12:00"
    if "midnight" in lowered:
        return "00:00"
    if "morning" in lowered:
        return "09:00"
    if "afternoon" in lowered:
        return "14:00"
    if "evening" in lowered:
        return "17:00"
    match = re.search(r"\b(\d{1,2}):(\d{2})\b", lowered)
    if match:
        hour = int(match.group(1))
        minute = int(match.group(2))
        if 0 <= hour <= 23 and 0 <= minute <= 59:
            return f"{hour:02d}:{minute:02d}"

    match = re.search(r"\b(\d{1,2})\s*(am|pm)\b", lowered)
    if match:
        hour = int(match.group(1))
        meridiem = match.group(2)
        if meridiem == "pm" and hour != 12:
            hour += 12
        if meridiem == "am" and hour == 12:
            hour = 0
        return f"{hour:02d}:00"

    return None


def extract_name(text: str) -> Optional[str]:
    match = re.search(r"my name is ([a-zA-Z\s]+)", text, re.IGNORECASE)
    if match:
        name = match.group(1).strip()
        if name:
            return name
    return None
