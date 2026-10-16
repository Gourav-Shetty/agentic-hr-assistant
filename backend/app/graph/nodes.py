"""Graph nodes: RAG answering + multi-turn booking with interrupt-resume."""

from .guardrails import sanitize, validate_email
from .router import normalize_query
from backend.app.tools.booking import SLOTS, extract_name_email, generate_ref, match_slot

import re

_AFFIRM = re.compile(
    r"\b(yes|yeah|yep|yup|confirm|confirmed|lock it|lock it in|proceed|go ahead)\b"
    r"|let'?s go|go with|book it|sounds good|that works|works for me|\bok\b|\bokay\b",
    re.IGNORECASE,
)
_CANCEL = re.compile(
    r"\b(no|nope|don'?t|cancel|change|different|other|another|back)\b",
    re.IGNORECASE,
)


def _wants_confirm(text: str) -> bool:
    return bool(_AFFIRM.search(text or ""))


def _wants_change(text: str) -> bool:
    t = (text or "").lower()
    if _AFFIRM.search(text or ""):
        return False  # affirmation wins ties ("no, actually yes")
    return bool(_CANCEL.search(text or ""))


def _last_user_text(state: dict) -> str:
    for m in reversed(state.get("messages", []) or []):
        if isinstance(m, dict) and m.get("role") == "user":
            return m.get("content", "")
    return ""


def _append(state: dict, role: str, content: str) -> list:
    return [*(state.get("messages", []) or []), {"role": role, "content": content}]


def _expand_query(query: str) -> str:
    """Expand HR acronyms so short queries retrieve (PTO -> paid time off leave)."""
    tl = query.lower()
    extra = []
    if "pto" in tl.split() or tl.strip() == "pto":
        extra.append("paid time off leave vacation absence")
    if "benefit" in tl:
        extra.append("health insurance coverage plan")
    return f"{query} {' '.join(extra)}".strip() if extra else query


def _rewrite_queries(query: str) -> list[str]:
    """LLM query rewrite (2 variants) for better recall; falls back to expansion."""
    base = _expand_query(query)
    try:
        from .llm import active_provider, generate as default_generate

        if active_provider() == "none":
            return [base]
        out = default_generate(
            f"Rewrite this HR question into 2 short search queries, one per line, no numbering: {query}",
            "",
        )
        variants = [ln.strip("- •0123456789. ").strip() for ln in out.splitlines()]
        variants = [v for v in variants if v and v.lower() != query.lower()][:2]
        return [base, *variants] if variants else [base]
    except Exception:
        return [base]


OUT_OF_SCOPE_HINTS = (
    "write", "python", "code", "program", "script", "function",
    "print number", "fibonacci", "sort", "algorithm", "math",
    "joke", "poem", "story", "recipe", "weather", "news",
)


def _is_out_of_scope(query: str) -> bool:
    tl = query.lower()
    return any(h in tl for h in OUT_OF_SCOPE_HINTS)


def rag_node(state: dict, retriever_fn=None, llm_fn=None) -> dict:
    """Answer HR question with citations. Preserves booking progress."""
    from .llm import generate as default_generate

    query = normalize_query(sanitize(_last_user_text(state)))
    # Greeting short-circuit: no retrieval, no LLM waste
    tl = query.lower().strip()
    if tl in {"hi", "hello", "hey", "thanks", "thank you", "bye"} or (
        len(tl.split()) <= 2 and not any(k in tl for k in ("pto", "leave", "policy", "benefit", "handbook", "review", "salary", "health", "vacation"))
    ):
        reply = "Hi! I can answer handbook questions (PTO, benefits, performance reviews) or book a performance review. What would you like?"
        return {
            "messages": _append(state, "assistant", reply),
            "citations": [],
            "last_route": "greeting",
            "just_answered_faq": False,
        }
    if _is_out_of_scope(query):
        reply = ("I can help with handbook questions (PTO, benefits, performance reviews) "
                 "or booking a performance review — I can't write code or answer general questions.")
        return {
            "messages": _append(state, "assistant", reply),
            "citations": [],
            "last_route": "faq",
        }
    docs, context, citations = [], "", []
    if retriever_fn is not None:
        try:
            seen: set[tuple] = set()
            for variant in _rewrite_queries(query):
                for d in retriever_fn(variant) or []:
                    key = (d.get("text") if isinstance(d, dict) else str(d),
                           d.get("page") if isinstance(d, dict) else None)
                    if key not in seen:
                        seen.add(key)
                        docs.append(d)
                    if len(docs) >= 4:
                        break
                if len(docs) >= 4:
                    break
        except Exception:
            docs = []
    for d in docs:
        if isinstance(d, dict):
            page = d.get("page")
            text = d.get("text", "")
            source = d.get("source", "handbook")
        else:
            page, text = getattr(d, "page", None), getattr(d, "text", str(d))
            source = getattr(d, "source", "handbook")
        if page is not None and page not in citations:
            citations.append(page)
        if text:
            label = f"[Page {page} ({source})]" if source and source != "handbook" else f"[Page {page}]"
            context += f"{label} {text}\n"
    gen = llm_fn or default_generate
    if not docs:
        reply = ("I couldn't find that in the handbook or benefits documents. "
                 "Try asking about performance reviews, leave, benefits, or booking a review.")
        return {
            "messages": _append(state, "assistant", reply),
            "citations": [],
            "last_route": "mixed" if state.get("booking_pending") else "faq",
            "just_answered_faq": False,
        }
    try:
        reply = gen(query, context)
    except Exception:
        reply = f"Based on the handbook: {context[:500]}" if context else "I couldn't find that in the handbook."
    low = reply.lower().replace("\u2019", "'").replace("\u2018", "'")
    if ("sorry" in low or "couldn't find" in low or "could not find" in low) and ("don't contain" in low or "do not contain" in low or "does not include" in low or "no information" in low or "no details" in low):
        citations = []
    if not citations and context:
        reply = reply  # no pages found; leave reply as-is
    return {
        "messages": _append(state, "assistant", reply),
        "citations": citations,
        "last_route": "mixed" if state.get("booking_pending") else "faq",
        "just_answered_faq": bool(state.get("booking_pending")),
        # stage/booking fields untouched -> resume works
    }


def booking_node(state: dict, llm_fn=None) -> dict:
    """Collect name/email/slot across turns. Never drops known fields."""
    text = sanitize(_last_user_text(state))
    name = state.get("name")
    email = state.get("email")
    slot = state.get("slot")

    if state.get("stage") == "done" and state.get("booking_ref"):
        # Already booked: never mint a second ref on re-invoke/double-submit.
        reply = (f"Your performance review is already booked for {slot} ({name}). "
                 f"Reference {state.get('booking_ref')}. Click New above to start another booking.")
        return {
            "name": name, "email": email, "slot": slot,
            "booking_pending": False, "last_route": "booking",
            "citations": [], "stage": "done", "booking_ref": state.get("booking_ref"),
            "messages": _append(state, "assistant", reply),
        }

    extracted = extract_name_email(text)
    if not name and extracted.get("name"):
        name = extracted["name"]
    found_email = extracted.get("email")
    if found_email and validate_email(found_email):
        email = found_email
    found_slot = match_slot(text)
    if found_slot:
        slot = found_slot
    # If user typed a bare email without name pattern, still catch invalid ones to re-ask
    elif "@" in text and not email:
        email = None  # invalid email present -> will re-ask below

    update: dict = {
        "name": name,
        "email": email,
        "slot": slot,
        "booking_pending": True,
        "last_route": "booking",
        "citations": [],  # stale RAG pages must not leak onto booking prompts
    }

    # Mixed flow: rag just answered an FAQ this turn (flag), so prepend that
    # answer and resume booking in one message. Flag is consumed here.
    # Only then are the rag citations relevant to this turn.
    prefix = ""
    msgs = state.get("messages", []) or []
    if state.get("just_answered_faq") and msgs and isinstance(msgs[-1], dict) and msgs[-1].get("role") == "assistant":
        prev = str(msgs[-1].get("content", "")).strip()
        if prev:
            prefix = prev + "\n\nReturning to your booking — "
            update["citations"] = list(state.get("citations") or [])
    update["just_answered_faq"] = False

    tl = text.lower().strip()
    is_greeting = tl in {"hi", "hello", "hey", "yo", "thanks", "thank you", "bye"} or (
        len(tl.split()) <= 2 and tl in {"hey there", "hello there", "hi there"}
    )
    is_gibberish = len(tl) <= 4 or tl in {"wth", "huh", "what", "???", "??", "hmm"}

    if not name:
        if is_greeting or is_gibberish:
            have = f" (holding {slot})" if slot else ""
            reply = f"Hey! We're booking your performance review{have} — I just need your full name to continue."
        else:
            reply = "Sure, let's book your performance review. What is your full name?"
        update["stage"] = "booking_name"
    elif not email or not validate_email(email or ""):
        if is_greeting or is_gibberish:
            reply = f"Hi {name}! I still need your work email to hold {slot or 'your slot'} — what is it?"
        else:
            reply = f"Thanks {name}. What is your work email?"
        update["email"] = email if validate_email(email or "") else None
        update["stage"] = "booking_email"
    elif not slot:
        reply = "Which slot works for you? Options: " + ", ".join(SLOTS)
        update["stage"] = "booking_slot"
    elif state.get("stage") == "booking_confirm" and _wants_change(text):
        # Human-in-the-loop said no: release the held slot, ask again.
        # (_wants_change is False when affirmation is present, so "no, actually yes" confirms.)
        reply = "No problem — which slot works instead? Options: " + ", ".join(SLOTS)
        update["slot"] = None
        update["stage"] = "booking_slot"
    elif (state.get("stage") == "booking_confirm" and not _wants_confirm(text)) or (
        found_slot and state.get("stage") == "booking_slot" and not _wants_confirm(text)
    ):
        # Hold the slot and ask for explicit confirmation (human-in-the-loop).
        held = slot or found_slot
        update["slot"] = held
        reply = (f"Lock it in: {held} for {name} ({email})? "
                 f"Reply Yes to confirm or No to pick another slot.")
        update["stage"] = "booking_confirm"
    else:
        if not slot:
            # Affirmed with nothing held yet — ask for a slot instead of booking None.
            reply = "Which slot works for you? Options: " + ", ".join(SLOTS)
            update["stage"] = "booking_slot"
            update["messages"] = _append(state, "assistant", prefix + reply if prefix else reply)
            if prefix:
                update["last_route"] = "mixed"
            return update
        ref = generate_ref()
        reply = (
            f"Done! Booked your performance review {slot} for {name} ({email}). "
            f"Your reference is {ref}."
        )
        update["stage"] = "done"
        update["booking_pending"] = False
        update["messages"] = _append(state, "assistant", prefix + reply if prefix else reply)
        update["booking_ref"] = ref
        if prefix:
            update["last_route"] = "mixed"
        return update

    update["messages"] = _append(state, "assistant", prefix + reply if prefix else reply)
    if prefix:
        update["last_route"] = "mixed"
    return update
