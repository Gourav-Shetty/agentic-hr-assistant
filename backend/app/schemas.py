"""API request/response schemas (Pydantic at the boundary only, never in state)."""

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    thread_id: str = Field(default="", description="Conversation id; server generates if empty")
    message: str = Field(min_length=1, description="User message")


class BookingInfo(BaseModel):
    name: str | None = None
    email: str | None = None
    slot: str | None = None
    reference: str | None = None


class ChatResponse(BaseModel):
    reply: str
    route: str
    citations: list = Field(default_factory=list)
    booking: BookingInfo | None = None
    thread_id: str
