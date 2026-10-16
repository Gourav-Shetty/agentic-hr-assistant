"""Offline RAG golden-set eval (no network, no LLM keys needed).

Run from repo root:  python scripts/eval_rag.py
Prints PASS/FAIL per case with retrieved pages; exits 1 on any failure.

Coverage (~8 questions):
  - retriever.query on the REAL data/chunks.json index (performance review
    frequency, benefits coordination, hearing-care coverage)
  - retriever.query on a small synthetic corpus for topics absent from the
    shipped handbook (PTO accrual, leave advance notice) via the same
    TF-IDF path tests use (patch _load_chunks_json, disable Chroma)
  - nodes.rag_node greeting + out-of-scope paths with exploding
    retriever/LLM stubs (proves no retrieval and no network LLM call)
  - router.route_intent booking intent

Nothing here calls Groq/Gemini or downloads models: sentence-transformers
is not required (retriever falls back to TF-IDF when it is unavailable).
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.app.graph import nodes as nodes_mod  # noqa: E402
from backend.app.graph.router import route_intent  # noqa: E402
from backend.app.rag import retriever  # noqa: E402

RESULTS: list[tuple[str, bool, str]] = []


def log(name: str, ok: bool, detail: str) -> None:
    print(f"[{'PASS' if ok else 'FAIL'}] {name} :: {detail}")
    RESULTS.append((name, ok, detail))


def pages_of(hits: list[dict]) -> str:
    return ",".join(f"p{h.get('page')}({h.get('source')})" for h in hits)


def retriever_case(
    name: str,
    question: str,
    expect_page: int,
    expect_source: str,
    keywords: tuple[str, ...],
    corpus: list[dict] | None = None,
) -> None:
    """Query retriever (optionally over a synthetic corpus) and assert the
    top hit's page/source plus expected keywords in the top hit text."""
    orig_load, orig_chroma = retriever._load_chunks_json, retriever._query_chroma
    if corpus is not None:
        retriever._load_chunks_json = lambda: corpus  # type: ignore[method-assign]
        retriever._query_chroma = lambda text, k: None  # type: ignore[method-assign]
    try:
        hits = retriever.query(question, k=3)
    finally:
        retriever._load_chunks_json = orig_load  # type: ignore[method-assign]
        retriever._query_chroma = orig_chroma  # type: ignore[method-assign]
    if not hits:
        return log(name, False, f"no hits for {question!r}")
    top = hits[0]
    text = str(top.get("text", "")).lower()
    missing = [kw for kw in keywords if kw.lower() not in text]
    ok = (
        top.get("page") == expect_page
        and top.get("source") == expect_source
        and not missing
    )
    log(
        name,
        ok,
        f"q={question!r} hits=[{pages_of(hits)}] "
        f"expect=top p{expect_page}({expect_source}) keywords={list(keywords)} "
        f"missing={missing}",
    )


SYNTHETIC_CORPUS = [
    {
        "text": "PTO accrues at 15 days per year. Unused leave carries over up to 5 days.",
        "page": 2,
        "source": "handbook",
    },
    {
        "text": "Leave policy: request time off two weeks in advance through your manager.",
        "page": 3,
        "source": "handbook",
    },
    {
        "text": "Performance reviews are conducted annually in June with ratings and goals.",
        "page": 4,
        "source": "handbook",
    },
    {
        "text": "Health benefits enrollment opens in November each year.",
        "page": 7,
        "source": "benefits",
    },
]


def _exploding_retriever(calls: list):
    def _fn(query: str):
        calls.append(query)
        raise AssertionError("retriever must not be called on this path")

    return _fn


def _exploding_llm(prompt: str, context: str = "") -> str:
    raise AssertionError("LLM must not be called on this path (offline eval)")


def greeting_case() -> None:
    calls: list = []
    out = nodes_mod.rag_node(
        {"messages": [{"role": "user", "content": "hello"}]},
        retriever_fn=_exploding_retriever(calls),
        llm_fn=_exploding_llm,
    )
    reply = str(out["messages"][-1]["content"])
    ok = (
        out.get("last_route") == "greeting"
        and out.get("citations") == []
        and not calls
        and "book" in reply.lower()
    )
    log("greeting-short-circuit", ok, f"route={out.get('last_route')} citations={out.get('citations')}")


def out_of_scope_case() -> None:
    calls: list = []
    out = nodes_mod.rag_node(
        {"messages": [{"role": "user", "content": "Write python code to print fibonacci numbers"}]},
        retriever_fn=_exploding_retriever(calls),
        llm_fn=_exploding_llm,
    )
    reply = str(out["messages"][-1]["content"]).lower()
    ok = (
        "can't write code" in reply
        and out.get("citations") == []
        and not calls
    )
    log("out-of-scope-code-request", ok, f"route={out.get('last_route')} reply={reply[:80]!r}")


def booking_intent_case() -> None:
    route = route_intent("I want to book a performance review for Friday")
    log("booking-intent-routes-to-booking", route == "booking", f"route={route}")


def main() -> int:
    retriever_case(
        "perf-review-frequency",
        "When are performance reviews conducted?",
        expect_page=4,
        expect_source="handbook",
        keywords=("performance",),
    )
    retriever_case(
        "pto-accrual",
        "How much PTO do I accrue per year?",
        expect_page=2,
        expect_source="handbook",
        keywords=("15 days",),
        corpus=SYNTHETIC_CORPUS,
    )
    retriever_case(
        "leave-advance-notice",
        "How far in advance must I request leave?",
        expect_page=3,
        expect_source="handbook",
        keywords=("two weeks",),
        corpus=SYNTHETIC_CORPUS,
    )
    retriever_case(
        "benefits-coordination",
        "How do I coordinate benefits with other coverage?",
        expect_page=72,
        expect_source="benefits",
        keywords=("coordinat",),
    )
    retriever_case(
        "hearing-care-coverage",
        "hearing care coverage",
        expect_page=30,
        expect_source="benefits",
        keywords=("hearing",),
    )
    greeting_case()
    out_of_scope_case()
    booking_intent_case()

    passed = sum(1 for _, ok, _ in RESULTS if ok)
    print(f"eval_rag: {passed}/{len(RESULTS)} passed")
    return 0 if passed == len(RESULTS) else 1


if __name__ == "__main__":
    raise SystemExit(main())
