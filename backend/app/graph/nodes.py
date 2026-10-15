"""Graph nodes: RAG answering + multi-turn booking with interrupt-resume."""

from .guardrails import sanitize, validate_email
from backend.app.tools.booking import SLOTS, extract_name_email, generate_ref, match_slot


def _last_user_text(state: dict) -> str:
    for m in reversed(state.get("messages", []) or []):
        if isinstance(m, dict) and m.get("role") == "user":
            return m.get("content", "")
    return ""


def _append(state: dict, role: str, content: str) -> list:
    return [*(state.get("messages", []) or []), {"role": role, "content": content}]


def rag_node(state: dict, retriever_fn=None, llm_fn=None) -> dict:
    """Answer HR question with citations. Preserves booking progress."""
    from .llm import generate as default_generate

    query = sanitize(_last_user_text(state))
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
        }
    docs, context, citations = [], "", []
    if retriever_fn is not None:
        try:
            docs = retriever_fn(query) or []
        except Exception:
            docs = []
    for d in docs:
        if isinstance(d, dict):
            page = d.get("page")
            text = d.get("text", "")
        else:
            page, text = getattr(d, "page", None), getattr(d, "text", str(d))
        if page is not None and page not in citations:
            citations.append(page)
        if text:
            context += f"[Page {page}] {text}\n"
    gen = llm_fn or default_generate
    try:
        reply = gen(query, context)
    except Exception:
        reply = f"Based on the handbook: {context[:500]}" if context else "I couldn't find that in the handbook."
    if not citations and context:
        reply = reply  # no pages found; leave reply as-is
    return {
        "messages": _append(state, "assistant", reply),
        "citations": citations,
        "last_route": "mixed" if state.get("booking_pending") else "faq",
        # stage/booking fields untouched -> resume works
    }


def booking_node(state: dict, llm_fn=None) -> dict:
    """Collect name/email/slot across turns. Never drops known fields."""
    text = sanitize(_last_user_text(state))
    name = state.get("name")
    email = state.get("email")
    slot = state.get("slot")

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
        "citations": [],
    }

    if not name:
        reply = "Sure, let's book your performance review. What is your full name?"
        update["stage"] = "booking_name"
    elif not email or not validate_email(email or ""):
        reply = f"Thanks {name}. What is your work email?"
        update["email"] = email if validate_email(email or "") else None
        update["stage"] = "booking_email"
    elif not slot:
        reply = "Which slot works for you? Options: " + ", ".join(SLOTS)
        update["stage"] = "booking_slot"
    else:
        ref = generate_ref()
        reply = (
            f"Done! Booked your performance review {slot} for {name} ({email}). "
            f"Your reference is {ref}."
        )
        update["stage"] = "done"
        update["booking_pending"] = False
        update["messages"] = _append(state, "assistant", reply)
        update["booking_ref"] = ref
        return update

    update["messages"] = _append(state, "assistant", reply)
    return update
