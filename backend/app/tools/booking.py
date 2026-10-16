"""Booking tool: fixed slots, name/email/slot extraction, reference gen."""

import re
import secrets
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
    if not result["name"] and m:
        # Bare "Alex Chen alex@x.com" only when email present in same message.
        # Never guess from booking sentences like "Hi, I need to book...".
        before = text[: m.start()] if m else text
        before = re.sub(r"[(,;]+", " ", before).strip()
        # drop FAQ tail ("wait before that how often ...")
        before = re.split(r"\.\s*|\bwait\b|\bbefore\b|\bhow\b|\bwhat\b|\bwhen\b", before, flags=re.IGNORECASE)[0]
        words = [w.strip(" .()'") for w in before.split() if w.strip(" .()'")]
        cap = [w for w in words if w and w[0].isupper() and w.isalpha() and len(w) > 1]
        if 2 <= len(cap) <= 3 and len(words) <= 5:
            result["name"] = " ".join(cap)
    if not result["name"] and not m:
        # Bare name alone ("Gourav Shetty") when asked for full name:
        # accept 1-3 capitalized words, reject sentences/questions/slots/emails.
        t = text.strip().strip(".,;)")
        low = t.lower()
        banned = ("book", "schedule", "slot", "tomorrow", "friday", "morning", "afternoon",
                  "review", "performance", "pto", "leave", "policy", "benefit", "handbook",
                  "hello", "hi", "hey", "thanks", "bye", "@", "?", "http")
        if not any(b in low for b in banned) and not any(ch.isdigit() for ch in t):
            words = [w.strip(" .()'") for w in t.split() if w.strip(" .()'")]
            if 1 <= len(words) <= 3 and all(w and w[0].isupper() and w.isalpha() and len(w) > 1 for w in words):
                result["name"] = " ".join(words)
    if not result["name"]:
        # Leading name before an interrupt ("Gourav but before that, ...?"):
        # take the leading run of capitalized words, reject sentences.
        head = re.split(r"\b(but|before|wait|and)\b", text.strip(), flags=re.IGNORECASE)[0]
        words = [w.strip(" .()'") for w in head.split() if w.strip(" .()'")]
        if (
            words
            and not any(ch.isdigit() for ch in head)
            and words[0].lower() not in {
                "what", "when", "where", "which", "how", "why", "is", "are",
                "can", "do", "does", "hi", "hello", "hey", "thanks",
            }
        ):
            run: list[str] = []
            for w in words:
                if w and w[0].isupper() and w.isalpha() and len(w) > 1:
                    run.append(w)
                else:
                    break
            rest = " ".join(words[len(run):]).lower()
            if 1 <= len(run) <= 3 and not any(
                b in rest for b in ("book", "schedule", "slot", "tomorrow", "friday",
                                    "morning", "afternoon", "@", "http")
            ):
                result["name"] = " ".join(run)
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
    """Return booking reference like #REV-XXXX (CSPRNG, unguessable)."""
    suffix = "".join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(6))
    return f"#REV-{suffix}"
