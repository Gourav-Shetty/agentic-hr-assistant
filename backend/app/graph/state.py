"""LangGraph agent state. TypedDict only, JSON-serializable (no Pydantic)."""

from typing import TypedDict


class AgentState(TypedDict, total=False):
    messages: list[dict]
    name: str | None
    email: str | None
    slot: str | None
    stage: str
    booking_pending: bool
    last_route: str
    next_step: str
    just_answered_faq: bool
    citations: list
    booking_ref: str | None


def default_state() -> AgentState:
    return {
        "messages": [],
        "name": None,
        "email": None,
        "slot": None,
        "stage": "idle",
        "booking_pending": False,
        "last_route": "",
        "next_step": "",
        "just_answered_faq": False,
        "citations": [],
        "booking_ref": None,
    }
