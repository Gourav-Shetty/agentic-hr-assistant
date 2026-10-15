"""RAG tests: chunking/ingest helpers and retriever page citations.

Offline-safe: no network, no model downloads. The retriever test injects
synthetic chunks and disables Chroma so it covers the TF-IDF/keyword path.
"""

import pytest

from backend.app.rag import ingest, retriever


def test_split_pages_preserves_page_numbers():
    pages = [("performance reviews are held annually. " * 60, 4)]
    chunks = ingest.split_pages(pages)
    assert len(chunks) > 1  # 800-char chunks over long text
    assert all(c["text"].strip() for c in chunks)
    assert all(c["page"] == 4 for c in chunks)


def test_split_simple_respects_overlap_and_pages():
    pages = [("abcdefghij" * 200, 2)]
    chunks = ingest._split_simple(pages, size=100, overlap=20)
    assert len(chunks) > 1
    assert all(c["page"] == 2 for c in chunks)
    assert all(len(c["text"]) <= 100 for c in chunks)


def test_ingest_pdf_missing_file_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        ingest.ingest_pdf(tmp_path / "does-not-exist.pdf")


def test_query_returns_text_and_page_citations(monkeypatch):
    data = [
        {"text": "Performance reviews are conducted annually in June.", "page": 4},
        {"text": "Vacation accrual is 15 days per year.", "page": 2},
        {"text": "Health benefits enrollment opens in November.", "page": 7},
    ]
    monkeypatch.setattr(retriever, "_load_chunks_json", lambda: data)
    monkeypatch.setattr(retriever, "_query_chroma", lambda text, k: None)
    hits = retriever.query("when are performance reviews?", k=2)
    assert hits, "retriever must return hits when an index exists"
    assert len(hits) <= 2
    for hit in hits:
        assert isinstance(hit["text"], str) and hit["text"].strip()
        assert isinstance(hit["page"], int) and hit["page"] >= 1
    assert "performance" in hits[0]["text"].lower()


def test_query_empty_index_returns_empty_list(monkeypatch):
    monkeypatch.setattr(retriever, "_load_chunks_json", lambda: [])
    monkeypatch.setattr(retriever, "_query_chroma", lambda text, k: None)
    assert retriever.query("pto policy") == []
    assert retriever.query("   ") == []
