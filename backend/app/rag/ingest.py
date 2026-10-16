"""Ingest handbook + benefits PDFs into Chroma (or a JSON fallback).

Pipeline: pypdf parse (per-page) -> RecursiveCharacterTextSplitter
chunking (800 chars / 150 overlap, simple sliding-window fallback) ->
sentence-transformers embeddings (all-MiniLM-L6-v2) -> Chroma persistent
store at CHROMA_DIR with page+source metadata. If chromadb / sentence-transformers
is unavailable (offline), chunks are written to data/chunks.json as the
TF-IDF fallback consumed by retriever.py.

Usage:
    python -m backend.app.rag.ingest [pdf_path]   # single PDF
    python -m backend.app.rag.ingest --all         # handbook + benefits PDFs
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

CHUNK_SIZE = 800
CHUNK_OVERLAP = 150
COLLECTION = "handbook"


def repo_root() -> Path:
    # backend/app/rag/ingest.py -> repo root
    return Path(__file__).resolve().parents[3]


def chroma_dir() -> str:
    raw = os.environ.get("CHROMA_DIR", "./data/chroma")
    p = Path(raw)
    if not p.is_absolute():
        p = repo_root() / p
    return str(p)


def chunks_json_path() -> Path:
    return repo_root() / "data" / "chunks.json"


def read_pages(pdf_path: str | Path) -> list[tuple[str, int]]:
    """Return [(page_text, 1-based page number)] using pypdf."""
    from pypdf import PdfReader

    reader = PdfReader(str(pdf_path))
    pages: list[tuple[str, int]] = []
    for i, page in enumerate(reader.pages):
        text = (page.extract_text() or "").strip()
        if text:
            pages.append((text, i + 1))
    return pages


def _split_simple(
    pages: list[tuple[str, int]],
    size: int = CHUNK_SIZE,
    overlap: int = CHUNK_OVERLAP,
    source: str = "handbook",
) -> list[dict]:
    """Sliding-window character splitter (no dependencies)."""
    chunks: list[dict] = []
    step = max(1, size - overlap)
    for text, page in pages:
        if len(text) <= size:
            chunks.append({"text": text, "page": page, "source": source})
            continue
        for start in range(0, len(text), step):
            piece = text[start : start + size].strip()
            if piece:
                chunks.append({"text": piece, "page": page, "source": source})
            if start + size >= len(text):
                break
    return chunks


def split_pages(
    pages: list[tuple[str, int]],
    size: int = CHUNK_SIZE,
    overlap: int = CHUNK_OVERLAP,
    source: str = "handbook",
) -> list[dict]:
    """Chunk pages, preferring RecursiveCharacterTextSplitter when installed."""
    splitter_cls = None
    try:
        from langchain_text_splitters import RecursiveCharacterTextSplitter

        splitter_cls = RecursiveCharacterTextSplitter
    except ImportError:
        try:
            from langchain.text_splitter import RecursiveCharacterTextSplitter  # type: ignore[no-redef]

            splitter_cls = RecursiveCharacterTextSplitter
        except ImportError:
            splitter_cls = None
    if splitter_cls is None:
        return _split_simple(pages, size, overlap, source)
    splitter = splitter_cls(chunk_size=size, chunk_overlap=overlap)
    chunks: list[dict] = []
    for text, page in pages:
        for piece in splitter.split_text(text):
            piece = piece.strip()
            if piece:
                chunks.append({"text": piece, "page": page, "source": source})
    return chunks


def write_fallback(chunks: list[dict]) -> Path:
    """Persist chunks as JSON for the TF-IDF/keyword fallback retriever."""
    path = chunks_json_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(chunks, ensure_ascii=False), encoding="utf-8")
    return path


def store_chroma(chunks: list[dict]) -> None:
    """Embed chunks and store them in a persistent Chroma collection."""
    import chromadb
    from sentence_transformers import SentenceTransformer

    model_name = os.environ.get(
        "EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2"
    )
    model = SentenceTransformer(model_name)
    embeddings = model.encode(
        [c["text"] for c in chunks], show_progress_bar=False
    ).tolist()
    client = chromadb.PersistentClient(path=chroma_dir())
    try:
        client.delete_collection(COLLECTION)
    except Exception:
        pass
    collection = client.get_or_create_collection(COLLECTION)
    collection.add(
        ids=[f"chunk-{i}" for i in range(len(chunks))],
        documents=[c["text"] for c in chunks],
        metadatas=[{"page": int(c.get("page") or 1), "source": str(c.get("source") or "handbook")} for c in chunks],
        embeddings=embeddings,
    )


def ingest_pdf(pdf_path: str | Path = "data/employee_handbook.pdf", source: str | None = None) -> int:
    """Ingest a single PDF; return the number of chunks stored."""
    path = Path(pdf_path)
    if not path.is_absolute():
        path = repo_root() / path
    if not path.is_file():
        raise FileNotFoundError(f"handbook PDF not found: {path}")
    if source is None:
        source = "benefits" if "benefit" in path.name.lower() or "northwind" in path.name.lower() else "handbook"
    pages = read_pages(path)
    if not pages:
        raise ValueError(f"no extractable text in {path}")
    chunks = split_pages(pages, source=source)
    if not chunks:
        raise ValueError(f"chunking produced 0 chunks for {path}")
    try:
        store_chroma(chunks)
    except Exception as exc:  # offline / missing deps -> JSON fallback
        write_fallback(chunks)
        print(f"chroma unavailable ({exc}); wrote JSON fallback instead")
    else:
        write_fallback(chunks)  # keep JSON too so retrieval works anywhere
    return len(chunks)


def ingest_all() -> int:
    """Ingest handbook + benefits PDFs (skipping missing secondary); return total chunks."""
    root = repo_root()
    targets = [
        (root / "data" / "employee_handbook.pdf", "handbook"),
        (root / "data" / "Northwind_Standard_Benefits_Details.pdf", "benefits"),
    ]
    all_chunks: list[dict] = []
    for path, source in targets:
        if not path.is_file():
            print(f"skip missing {path.name} (source={source})")
            continue
        pages = read_pages(path)
        chunks = split_pages(pages, source=source)
        print(f"parsed {len(chunks)} chunks from {path.name} (source={source})")
        all_chunks.extend(chunks)
    if not all_chunks:
        raise FileNotFoundError("no PDFs found to ingest in data/")
    try:
        store_chroma(all_chunks)
    except Exception as exc:
        write_fallback(all_chunks)
        print(f"chroma unavailable ({exc}); wrote JSON fallback instead")
    else:
        write_fallback(all_chunks)
    return len(all_chunks)


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    if "--all" in args or not args:
        # Default: ingest everything present (handbook + benefits).
        try:
            count = ingest_all()
        except (FileNotFoundError, ValueError) as exc:
            print(f"error: {exc}")
            return 1
        print(f"ingested {count} chunks (all PDFs, chroma={chroma_dir()})")
        return 0
    target = args[0]
    try:
        count = ingest_pdf(target)
    except (FileNotFoundError, ValueError) as exc:
        print(f"error: {exc}")
        return 1
    print(f"ingested {count} chunks (pdf={target}, chroma={chroma_dir()})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
