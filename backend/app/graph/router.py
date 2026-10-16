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
        # Pure FAQ interrupt -> mixed (answer FAQ, then resume). Slot-time answers stay booking.
        # Email + FAQ together is still mixed so FAQ gets answered; booking_node extracts email after.
        time_like = any(k in t for k in ["tomorrow", "friday", "10:30", "11am", "3pm", "11 am", "3 pm", "morning", "afternoon"])
        if has_faq and not has_booking and not time_like:
            return "mixed"
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
