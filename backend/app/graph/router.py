"""Keyword router: faq | booking | mixed | greeting."""

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
]

GREETING_KEYWORDS = ["hi", "hello", "hey", "good morning", "good afternoon", "thanks", "thank you", "bye"]

ACTIVE_STAGES = {"idle", "done"}


def route_intent(text: str, stage: str = "idle") -> str:
    """Route user text to 'faq' | 'booking' | 'mixed' | 'greeting'.

    Active booking (stage not idle/done) defaults to booking continuation
    unless it's a pure FAQ interrupt.
    """
    t = (text or "").lower()
    has_faq = any(k in t for k in FAQ_KEYWORDS)
    has_booking = any(k in t for k in BOOKING_KEYWORDS)
    # Slot/email/name-like continuation signals (e.g. "Friday 10:30AM", "ada@x.com")
    slot_like = any(k in t for k in ["tomorrow", "friday", "10:30", "11am", "3pm", "11 am", "3 pm", "morning", "afternoon", "@"])
    name_like = any(p in t for p in ["my name is", "i am ", "i'm ", "this is "])

    active = stage not in ACTIVE_STAGES
    if active:
        if has_faq and not has_booking and not slot_like and not name_like and "@" not in t:
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
