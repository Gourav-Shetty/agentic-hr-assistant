"""Compile the LangGraph StateGraph with router conditional edges."""

from langgraph.graph import END, StateGraph

from .nodes import booking_node, rag_node
from .router import route_intent
from .state import AgentState


def build_graph(checkpointer=None, retriever_fn=None, llm_fn=None):
    """Build and compile the agent graph.

    Entry routes via route_intent -> rag | booking.
    'mixed' (FAQ interrupt during booking) goes to rag first, then
    resumes booking while booking_pending is set.
    """
    graph = StateGraph(AgentState)

    def _rag(state: AgentState) -> dict:
        return rag_node(dict(state), retriever_fn=retriever_fn, llm_fn=llm_fn)

    def _booking(state: AgentState) -> dict:
        return booking_node(dict(state), llm_fn=llm_fn)

    graph.add_node("rag", _rag)
    graph.add_node("booking", _booking)

    def _route(state: AgentState) -> str:
        text = ""
        for m in reversed(state.get("messages", []) or []):
            if isinstance(m, dict) and m.get("role") == "user":
                text = m.get("content", "")
                break
        return route_intent(text, stage=state.get("stage", "idle") or "idle")

    graph.set_conditional_entry_point(
        _route,
        {
            "faq": "rag",
            "greeting": "rag",
            "booking": "booking",
            "mixed": "rag",
        },
    )

    def _after_rag(state: AgentState) -> str:
        # Resume interrupted booking after answering the FAQ.
        if state.get("booking_pending"):
            return "booking"
        return END

    graph.add_conditional_edges("rag", _after_rag, {"booking": "booking", END: END})
    graph.add_edge("booking", END)

    if checkpointer is not None:
        return graph.compile(checkpointer=checkpointer)
    return graph.compile()
