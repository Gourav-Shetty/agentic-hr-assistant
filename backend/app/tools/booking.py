"""Booking tool: fixed slots, name/email/slot extraction, reference gen."""

import random
import re
import string

SLOTS = [
    "Tomorrow 11AM",
    "Tomorrow 3PM",
    "Friday 10:30AM IST",
]

_EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")

_NAME_PATTERNS = [
    re.compile(r"my name is\s+([A-Za-z][A-Za-z .'-]{1,60})", re.IGNORECASE),
    re.compile(r"i am\s+([A-Za-z][A-Za-z .'-]{1,60})", re.IGNORECASE),
    re.compile(r"i'm\s+([A-Za-z][A-Za-z .'-]{1,60})", re.IGNORECASE),
    re.compile(r"this is\s+([A-Za-z][A-Za-z .'-]{1,60})", re.IGNORECASE),
]


def extract_name_email(text: str) -> dict:
    """Extract {'name': str|None, 'email': str|None} from free text."""
    result: dict = {"name": None, "email": None}
    if not text:
        return result
    m = _EMAIL_RE.search(text)
    if m:
        result["email"] = m.group(0).strip().rstrip(".,;)")
    for rx in _NAME_PATTERNS:
        nm = rx.search(text)
        if nm:
            name = nm.group(1).strip().rstrip(".,;)")
            # Cut off trailing clause ("and ...", email leftovers)
            name = re.split(r"\s+and\s+|\s+my\s+|\s+email\s+", name, flags=re.IGNORECASE)[0].strip()
            if name:
                result["name"] = name
            break
    return result


def match_slot(text: str) -> str | None:
    """Fuzzy-match user text to one of SLOTS. Returns slot or None."""
    if not text:
        return None
    t = text.lower()
    # Direct substring against slot (normalized)
    for s in SLOTS:
        if s.lower() in t:
            return s
    # Keyword heuristics
    if "10:30" in t or ("friday" in t and "10" in t) or ("friday" in t and "morning" in t):
        return SLOTS[2]
    if "friday" in t:
        return SLOTS[2]
    if "11" in t and ("am" in t or "morning" in t or "tomorrow" in t):
        return SLOTS[0]
    if "3" in t and ("pm" in t or "afternoon" in t or "tomorrow" in t):
        return SLOTS[1]
    if "morning" in t:
        return SLOTS[0]
    if "afternoon" in t:
        return SLOTS[1]
    return None


def generate_ref() -> str:
    """Return booking reference like #REV-XXXX (uppercase alnum)."""
    suffix = "".join(random.choices(string.ascii_uppercase + string.digits, k=4))
    return f"#REV-{suffix}"
