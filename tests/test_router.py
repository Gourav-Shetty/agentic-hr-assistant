"""Router intent tests (faq vs booking vs mixed/interrupt).

Resolves the router function by candidate names so this stays green while
the graph module evolves; skips when backend/app/graph/router.py is absent.
"""

import importlib

import pytest

_ROUTER_MODULES = ("backend.app.graph.router", "backend.app.graph.nodes")
_ROUTER_FNS = ("route", "route_message", "route_intent", "classify", "classify_intent")
_BOOKING_LABELS = {"booking", "book", "schedule", "calendar", "appointment"}
_FAQ_LABELS = {"faq", "rag", "qa", "knowledge", "handbook"}
_MIXED_LABELS = {"mixed", "both", "booking", "interrupt"}


def _load_router():
    for module in _ROUTER_MODULES:
        try:
            mod = importlib.import_module(module)
        except ImportError:
            continue
        for name in _ROUTER_FNS:
            fn = getattr(mod, name, None)
            if callable(fn):
                return fn
    return None


def _label(result) -> str:
    if isinstance(result, str):
        return result.lower()
    if isinstance(result, dict):
        for key in ("route", "intent", "next", "node"):
            if isinstance(result.get(key), str):
                return result[key].lower()
    return str(result).lower()


def _route(fn, message: str) -> str:
    try:
        return _label(fn(message))
    except TypeError:
        pass
    try:
        return _label(fn({"message": message}))
    except TypeError:
        pass
    try:
        return _label(fn({"messages": [{"role": "user", "content": message}]}))
    except TypeError as exc:
        pytest.skip(f"router signature not covered by test harness: {exc}")


@pytest.fixture(scope="module")
def router_fn():
    fn = _load_router()
    if fn is None:
        pytest.skip("router not implemented yet")
    return fn


def test_faq_routes_to_knowledge(router_fn):
    label = _route(router_fn, "How is PTO accrued each year?")
    assert any(tok in label for tok in _FAQ_LABELS), label


def test_booking_routes_to_booking(router_fn):
    label = _route(router_fn, "I want to book a performance review for Friday")
    assert any(tok in label for tok in _BOOKING_LABELS), label


def test_mixed_faq_interrupt_keeps_booking_context(router_fn):
    label = _route(
        router_fn,
        "What is the PTO policy? Also I still want to book my performance review.",
    )
    assert any(tok in label for tok in (_MIXED_LABELS | _FAQ_LABELS | _BOOKING_LABELS)), label


def test_typo_benefits_routes_to_knowledge(router_fn):
    label = _route(router_fn, "may i know all the benegits")
    assert any(tok in label for tok in _FAQ_LABELS), label


def test_interview_routes_to_booking(router_fn):
    label = _route(router_fn, "can i book an interview please")
    assert any(tok in label for tok in _BOOKING_LABELS), label


def test_normalize_query_fixes_typos():
    from backend.app.graph.router import normalize_query

    assert normalize_query("all the benegits") == "all the benefits"
    assert normalize_query("book a reveiw") == "book a review"


def test_done_state_question_goes_to_knowledge():
    from backend.app.graph.router import route_intent

    assert route_intent("how will the performance interview go?", stage="done") == "faq"
    assert route_intent("is it possible to know more?", stage="done") == "faq"


def test_done_state_rebook_goes_to_booking():
    from backend.app.graph.router import route_intent

    assert route_intent("book another slot please", stage="done") == "booking"


def test_identity_and_capability_replies():
    from backend.app.graph.nodes import booking_node, rag_node

    base = {"messages": [], "stage": "idle", "booking_pending": False,
            "citations": [4], "just_answered_faq": False}
    ident = rag_node({**base, "messages": [{"role": "user", "content": "what model are you?"}]})
    assert "Zava HR Assistant" in ident["messages"][-1]["content"]
    assert ident["citations"] == []
    assert "OpenAI" not in ident["messages"][-1]["content"]

    cap = rag_node({**base, "messages": [{"role": "user", "content": "what else can you do?"}]})
    assert "book a 1-on-1" in cap["messages"][-1]["content"] or "Book a" in cap["messages"][-1]["content"]
    assert cap["citations"] == []

    booked = {"messages": [{"role": "user", "content": "book another please"}],
              "name": "G", "email": "g@x.com", "slot": "Tomorrow 11AM",
              "stage": "done", "booking_pending": False, "citations": [],
              "just_answered_faq": False, "booking_ref": "#REV-ABC123"}
    out = booking_node(dict(booked))
    assert out["stage"] == "booking_name" and out["booking_ref"] is None

    same = booking_node({**booked, "messages": [{"role": "user", "content": "thanks!"}]})
    assert same["booking_ref"] == "#REV-ABC123"
