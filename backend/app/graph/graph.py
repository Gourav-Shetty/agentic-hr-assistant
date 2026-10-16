"""Compile the LangGraph supervisor + specialist StateGraph.

Supervisor node routes every turn (faq | booking | mixed | greeting);
specialist nodes (rag, booking) do the work. 'mixed' (FAQ interrupt during
booking) goes to rag first, then resumes booking while booking_pending is set.
State persists per thread via the checkpointer.
"""

from langgraph.graph import END, StateGraph

from .nodes import booking_node, rag_node
from .router import route_intent
from .state import AgentState


def supervisor_node(state: AgentState) -> dict:
    """Supervisor: inspect latest user text + booking stage, choose a specialist."""
    text = ""
    for m in reversed(state.get("messages", []) or []):
        if isinstance(m, dict) and m.get("role") == "user":
            text = m.get("content", "")
            break
    decision = route_intent(text, stage=state.get("stage", "idle") or "idle")
    return {"next_step": decision, "last_route": decision}


def build_graph(checkpointer=None, retriever_fn=None, llm_fn=None):
    """Build and compile the agent graph."""
    graph = StateGraph(AgentState)

    def _rag(state: AgentState) -> dict:
        return rag_node(dict(state), retriever_fn=retriever_fn, llm_fn=llm_fn)

    def _booking(state: AgentState) -> dict:
        return booking_node(dict(state), llm_fn=llm_fn)

    def _supervisor(state: AgentState) -> dict:
        return supervisor_node(dict(state))

    graph.add_node("supervisor", _supervisor)
    graph.add_node("rag", _rag)
    graph.add_node("booking", _booking)

    graph.set_entry_point("supervisor")
    graph.add_conditional_edges(
        "supervisor",
        lambda s: s.get("next_step", "faq"),
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
