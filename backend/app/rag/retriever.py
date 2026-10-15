"""Retrieve handbook chunks for a user query.

Order: Chroma (persistent, dense embeddings) -> data/chunks.json TF-IDF
-> keyword overlap fallback. Always returns [{text, page}] with integer
page numbers so answers can cite [Page N]. Never raises on missing
deps/data: returns [] when nothing is indexed.
"""

from __future__ import annotations

import json
import math
import os
import re
from pathlib import Path

COLLECTION = "handbook"
_WORD = re.compile(r"[a-z0-9]+")


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _chroma_dir() -> str:
    raw = os.environ.get("CHROMA_DIR", "./data/chroma")
    p = Path(raw)
    if not p.is_absolute():
        p = _repo_root() / p
    return str(p)


def _tokens(text: str) -> list[str]:
    return _WORD.findall(text.lower())


_MODEL = None
_MODEL_NAME = None
_CHROMA_CLIENT = None
_CHROMA_DIR_CACHED = None
_CHUNKS_CACHE: dict = {"mtime": None, "items": []}


def _load_chunks_json() -> list[dict]:
    """Load fallback chunks; [] when data/chunks.json is missing/invalid (cached)."""
    path = _repo_root() / "data" / "chunks.json"
    try:
        mtime = path.stat().st_mtime
    except OSError:
        return []
    if _CHUNKS_CACHE["mtime"] == mtime:
        return _CHUNKS_CACHE["items"]
    try:
        items = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    chunks: list[dict] = []
    for item in items if isinstance(items, list) else []:
        if not isinstance(item, dict) or not str(item.get("text", "")).strip():
            continue
        try:
            page = int(item.get("page") or 1)
        except (TypeError, ValueError):
            page = 1
        chunks.append({"text": str(item["text"]), "page": max(1, page)})
    _CHUNKS_CACHE["mtime"] = mtime
    _CHUNKS_CACHE["items"] = chunks
    return chunks


def _tfidf_search(chunks: list[dict], text: str, k: int) -> list[dict]:
    """Pure-stdlib TF-IDF ranking over chunks (no sklearn needed)."""
    query_terms = _tokens(text)
    if not query_terms or not chunks:
        return []
    doc_tokens = [_tokens(c["text"]) for c in chunks]
    doc_len = [max(1, len(t)) for t in doc_tokens]
    df: dict[str, int] = {}
    for toks in doc_tokens:
        for term in set(toks):
            df[term] = df.get(term, 0) + 1
    n = len(chunks)
    scored: list[tuple[float, int]] = []
    for i, toks in enumerate(doc_tokens):
        tf: dict[str, int] = {}
        for t in toks:
            tf[t] = tf.get(t, 0) + 1
        score = 0.0
        for term in set(query_terms):
            if term not in tf:
                continue
            idf = math.log((n + 1) / (df.get(term, 0) + 1)) + 1.0
            score += (tf[term] / doc_len[i]) * idf
        scored.append((score, i))
    scored.sort(key=lambda s: s[0], reverse=True)
    hits = [chunks[i] for s, i in scored[:k] if s > 0]
    if hits:
        return hits
    # no TF-IDF signal -> keyword overlap, else first chunks so callers
    # still get citable context whenever an index exists
    overlap = [
        (len(set(query_terms) & set(doc_tokens[i])), i) for i in range(n)
    ]
    overlap.sort(reverse=True)
    hits = [chunks[i] for o, i in overlap[:k] if o > 0]
    return hits or chunks[:k]


def _query_chroma(text: str, k: int) -> list[dict] | None:
    """Dense retrieval; None when Chroma/embeddings are unavailable (cached)."""
    global _MODEL, _MODEL_NAME, _CHROMA_CLIENT, _CHROMA_DIR_CACHED
    try:
        import chromadb
        from sentence_transformers import SentenceTransformer
    except ImportError:
        return None
    try:
        model_name = os.environ.get("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
        cdir = _chroma_dir()
        if _MODEL is None or _MODEL_NAME != model_name:
            _MODEL = SentenceTransformer(model_name)
            _MODEL_NAME = model_name
        if _CHROMA_CLIENT is None or _CHROMA_DIR_CACHED != cdir:
            _CHROMA_CLIENT = chromadb.PersistentClient(path=cdir)
            _CHROMA_DIR_CACHED = cdir
        collection = _CHROMA_CLIENT.get_collection(COLLECTION)
        vector = _MODEL.encode([text], show_progress_bar=False).tolist()
        res = collection.query(
            query_embeddings=vector, n_results=max(1, k)
        )
        docs = (res.get("documents") or [[]])[0]
        metas = (res.get("metadatas") or [[]])[0]
    except Exception:
        return None
    out: list[dict] = []
    for doc, meta in zip(docs, metas):
        if not (doc or "").strip():
            continue
        try:
            page = int((meta or {}).get("page") or 1)
        except (TypeError, ValueError):
            page = 1
        out.append({"text": doc, "page": max(1, page)})
    return out or None


def query(text: str, k: int = 4) -> list[dict]:
    """Return up to k chunks as [{text, page}] for a user query."""
    text = (text or "").strip()
    if not text:
        return []
    k = max(1, int(k))
    chroma_hits = _query_chroma(text, k)
    if chroma_hits:
        return chroma_hits[:k]
    return _tfidf_search(_load_chunks_json(), text, k)[:k]


# Alias used by some graph nodes.
retrieve = query
search = query
