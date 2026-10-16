"""Keyword router: faq | booking | mixed | greeting (typo-tolerant)."""

import difflib
import re

FAQ_KEYWORDS = [
    "performance review",
    "pto",
    "leave",
    "benefits",
    "policy",
    "handbook",
    "vacation",
    "salary",
    "health",
]

BOOKING_KEYWORDS = [
    "book",
    "schedule",
    "appointment",
    "slot",
    "review session",
    "interview",
]

# Common user typos, mapped to canonical keywords before matching.
TYPO_MAP = {
    "benegits": "benefits", "benefites": "benefits", "benfits": "benefits",
    "beneits": "benefits", "benifits": "benefits",
    "reveiw": "review", "reivew": "review", "revview": "review",
    "perfomance": "performance", "preformance": "performance", "performence": "performance",
    "appoinment": "appointment", "apointment": "appointment",
    "scedule": "schedule", "schedul": "schedule", "schedual": "schedule",
    "polcy": "policy", "polciy": "policy",
    "hanbook": "handbook", "handbok": "handbook",
    "vaccation": "vacation", "vacatoin": "vacation",
    "salery": "salary", "helth": "health",
    "intreview": "interview", "interveiw": "interview",
}

_TYPO_RE = re.compile(r"\b(" + "|".join(sorted(TYPO_MAP)) + r")\b")


def normalize_query(text: str) -> str:
    """Fix common typos (exact-word map). Safe for retrieval queries."""
    if not text:
        return ""
    return _TYPO_RE.sub(lambda m: TYPO_MAP[m.group(1)], text)


def _has_any(text: str, keywords: list[str]) -> bool:
    """Substring match plus difflib backstop for single-word typos."""
    if any(k in text for k in keywords):
        return True
    singles = [k for k in keywords if " " not in k]
    for tok in set(re.findall(r"[a-z]{5,}", text)):
        if difflib.get_close_matches(tok, singles, n=1, cutoff=0.86):
            return True
    return False

GREETING_KEYWORDS = ["hi", "hello", "hey", "good morning", "good afternoon", "thanks", "thank you", "bye"]

ACTIVE_STAGES = {"idle", "done"}


def route_intent(text: str, stage: str = "idle") -> str:
    """Route user text to 'faq' | 'booking' | 'mixed' | 'greeting'.

    Active booking (stage not idle/done) defaults to booking continuation
    unless it's a pure FAQ interrupt.
    """
    t = normalize_query((text or "").lower())
    has_faq = _has_any(t, FAQ_KEYWORDS)
    has_booking = _has_any(t, BOOKING_KEYWORDS)
    # Slot/email/name-like continuation signals (e.g. "Friday 10:30AM", "ada@x.com")
    slot_like = any(k in t for k in ["tomorrow", "friday", "10:30", "11am", "3pm", "11 am", "3 pm", "morning", "afternoon", "@"])
    name_like = any(p in t for p in ["my name is", "i am ", "i'm ", "this is "])

    active = stage not in ACTIVE_STAGES
    if active:
        # Pure FAQ interrupt -> mixed (answer FAQ, then resume). Slot-time answers stay booking.
        # Email + FAQ together is still mixed so FAQ gets answered; booking_node extracts email after.
        time_like = any(k in t for k in ["tomorrow", "friday", "10:30", "11am", "3pm", "11 am", "3 pm", "morning", "afternoon"])
        if has_faq and not has_booking and not time_like:
            return "mixed"
        return "booking"
    if stage == "done":
        # Booked already: questions (esp. FAQ-flavored) go to knowledge;
        # fresh booking verbs restart the flow; anything else gets the summary.
        is_question = "?" in t or t.startswith(("what ", "how ", "why ", "when ", "where ", "which ", "is ", "are ", "can ", "do "))
        if (has_faq or is_question) and not slot_like and "@" not in t:
            return "faq"
        if has_booking:
            return "booking"
        return "booking"
    # idle/done: explicit slot/email/name clicks start booking even without verbs
    if slot_like or "@" in t or name_like:
        # pure slot/email/name with no FAQ -> booking; FAQ + slot ambiguous -> mixed to answer FAQ first
        if has_faq and not has_booking:
            return "mixed"
        return "booking"
    if has_faq and has_booking:
        return "booking"
    if has_booking:
        return "booking"
    if has_faq:
        return "faq"
    if any(k in t for k in GREETING_KEYWORDS) or len(t.split()) <= 3:
        return "greeting"
    return "faq"
