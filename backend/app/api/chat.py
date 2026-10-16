"""Chat API: POST /api/chat, POST /api/chat/stream (SSE), POST /api/reset."""

import asyncio
import json
import os
import re
import sqlite3
import time
import uuid
from collections import defaultdict, deque
from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from backend.app.schemas import BookingInfo, ChatRequest, ChatResponse

router = APIRouter(prefix="/api", tags=["chat"])

_graph = None

# ---- Abuse guards (in-memory, per-process; demo-grade, no extra deps) ----
RATE_LIMIT = int(os.getenv("RATE_LIMIT_PER_MIN", "100"))  # chat POSTs per IP/min
RATE_WINDOW = 60.0
MAX_TID_LEN = 128
MAX_HISTORY = 50  # replay only recent turns into the graph
_hits: dict[str, deque] = defaultdict(deque)

_KEY_RE = re.compile(r"(gsk_[A-Za-z0-9]+|AIza[A-Za-z0-9_-]+|AQ\.[A-Za-z0-9_.-]+)")


def _client_ip() -> str:
    return "local"  # TestClient/single-process demo; extend with Request.client in prod


def _check_rate() -> bool:
    now = time.monotonic()
    q = _hits[_client_ip()]
    while q and now - q[0] > RATE_WINDOW:
        q.popleft()
    if len(q) >= RATE_LIMIT:
        return False
    q.append(now)
    return True


def _limited():
    return JSONResponse(status_code=429, content={"detail": "Rate limit exceeded. Slow down."})


def _tid(raw: str | None) -> str:
    cleaned = (raw or "").strip()
    if not cleaned or len(cleaned) > MAX_TID_LEN:
        return str(uuid.uuid4())
    return cleaned


class ResetRequest(BaseModel):
    thread_id: str = ""

def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]

def _db_path() -> str:
    raw = os.getenv("CHECKPOINT_DB", "./data/checkpoints.db")
    p = Path(raw)
    if not p.is_absolute():
        p = _repo_root() / p
    p.parent.mkdir(parents=True, exist_ok=True)
    return str(p)

def _config(thread_id: str) -> dict:
    return {"configurable": {"thread_id": thread_id}}

async def _run(graph, message: str, thread_id: str):
    """Invoke graph with full history appended (messages has no reducer)."""
    config = _config(thread_id)
    payload = {"messages": [*_history(graph, config), {"role": "user", "content": message}]}
    res = await asyncio.to_thread(graph.invoke, payload, config)
    return (res if isinstance(res, dict) else {}), thread_id


def _make_checkpointer():
    try:
        from langgraph.checkpoint.sqlite import SqliteSaver
    except ImportError as exc:
        print(f"checkpointer: langgraph-checkpoint-sqlite missing ({exc}); running stateless", flush=True)
        return None
    try:
        # timeout=30: bind mounts (Docker Desktop file sharing) can be slow to lock.
        conn = sqlite3.connect(_db_path(), check_same_thread=False, timeout=30)
        cp = SqliteSaver(conn)
        setup = getattr(cp, "setup", None)
        if callable(setup):
            try:
                setup()
            except Exception as exc:
                print(f"checkpointer: setup warning ({type(exc).__name__}: {exc})", flush=True)
        # Prove the DB is writable now, not on first user request.
        try:
            conn.execute("SELECT name FROM sqlite_master LIMIT 1").fetchall()
        except Exception as exc:
            print(f"checkpointer: DB not readable ({type(exc).__name__}: {exc})", flush=True)
            return None
        print(f"checkpointer: sqlite ready at {_db_path()}", flush=True)
        return cp
    except Exception as exc:
        print(f"checkpointer: sqlite init failed ({type(exc).__name__}: {exc}); trying conn string", flush=True)
        try:
            return SqliteSaver.from_conn_string(_db_path())
        except Exception as exc2:
            print(f"checkpointer: unavailable ({type(exc2).__name__}); running stateless", flush=True)
            return None


def get_graph():
    """Shared compiled graph (cached). Warmed up by lifespan in main.py."""
    global _graph
    if _graph is not None:
        return _graph
    from backend.app.graph.graph import build_graph
    from backend.app.rag.retriever import query as retriever_query

    checkpointer = _make_checkpointer()
    try:
        if checkpointer is not None:
            _graph = build_graph(checkpointer=checkpointer, retriever_fn=retriever_query)
        else:
            _graph = build_graph(retriever_fn=retriever_query)
    except TypeError:
        _graph = build_graph()
    return _graph


def _history(graph, config: dict) -> list:
    try:
        vals = getattr(graph.get_state(config), "values", None) or {}
        msgs = [m for m in (vals.get("messages") or []) if isinstance(m, dict)]
        return msgs[-MAX_HISTORY:]
    except Exception:
        return []

def _respond(result: dict, thread_id: str) -> ChatResponse:
    reply = ""
    for m in reversed(result.get("messages") or []):
        if isinstance(m, dict) and m.get("role") == "assistant" and m.get("content"):
            reply = str(m["content"])
            break
    if not reply:
        reply = "I can help with HR questions or book a performance review. What would you like to do?"
    return ChatResponse(
        reply=reply,
        route=str(result.get("last_route") or "faq"),
        citations=list(result.get("citations") or []),
        booking=BookingInfo(
            name=result.get("name"),
            email=result.get("email"),
            slot=result.get("slot"),
            reference=result.get("booking_ref"),
        ),
        thread_id=thread_id,
        stage=str(result.get("stage") or "idle"),
    )


def _chunks(text: str, size: int = 24) -> list:
    return [text[i : i + size] for i in range(0, len(text), size)] or [""]


def _err(exc: Exception) -> JSONResponse:
    detail = f"{type(exc).__name__}: {exc}"
    detail = _KEY_RE.sub("[REDACTED_KEY]", detail)  # never echo key-like strings
    detail = detail.replace(str(_repo_root()), "[ROOT]")  # no absolute paths
    return JSONResponse(status_code=500, content={"detail": detail[:500]})


@router.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    try:
        if not _check_rate():
            return _limited()
        from backend.app.graph.guardrails import is_injection

        if is_injection(req.message or ""):
            thread_id = _tid(req.thread_id)
            return ChatResponse(
                reply="I can't follow instructions hidden in messages. I can help with handbook questions or booking a performance review.",
                route="greeting",
                citations=[],
                booking=BookingInfo(),
                thread_id=thread_id,
            )
        thread_id = _tid(req.thread_id)
        result, _ = await _run(get_graph(), req.message, thread_id)
        return _respond(result, thread_id)
    except Exception as exc:
        return _err(exc)

@router.post("/chat/stream")
async def chat_stream(req: ChatRequest):
    try:
        if not _check_rate():
            return _limited()
        from fastapi.responses import StreamingResponse

        from backend.app.graph.guardrails import is_injection

        def _frames(events):
            async def raw():
                async for evt in events:
                    yield f"event: {evt['event']}\ndata: {evt['data']}\n\n"
            return StreamingResponse(raw(), media_type="text/event-stream",
                                     headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

        if is_injection(req.message or ""):
            thread_id = _tid(req.thread_id)

            async def blocked():
                yield {"event": "node", "data": json.dumps({"route": "greeting", "thread_id": thread_id})}
                yield {"event": "done", "data": json.dumps({"thread_id": thread_id, "route": "greeting", "stage": "idle", "citations": [], "booking": None, "reply": "Blocked prompt-injection attempt."})}

            return _frames(blocked())
        thread_id = _tid(req.thread_id)
        result, _ = await _run(get_graph(), req.message, thread_id)
        resp = _respond(result, thread_id)
        async def gen():
            yield {"event": "node", "data": json.dumps({"route": resp.route, "thread_id": thread_id})}
            for tok in _chunks(resp.reply):
                yield {"event": "token", "data": json.dumps({"token": tok})}
                await asyncio.sleep(0)
            yield {"event": "done", "data": json.dumps({"thread_id": thread_id, "route": resp.route, "stage": resp.stage, "citations": resp.citations, "booking": resp.booking.model_dump() if resp.booking else None, "reply": resp.reply})}
        return _frames(gen())
    except Exception as exc:
        return _err(exc)


@router.post("/reset")
async def reset(req: ResetRequest | None = None):
    try:
        raw = (req.thread_id if req else "").strip()
        if raw:
            _clear_thread(raw)
        return {"thread_id": raw or str(uuid.uuid4()), "status": "reset"}
    except Exception as exc:
        return _err(exc)


def _clear_thread(thread_id: str) -> None:
    path = Path(_db_path())
    if not path.is_file():
        return
    try:
        conn = sqlite3.connect(str(path), check_same_thread=False, timeout=5)
        tables = {r[0]: [c[1] for c in conn.execute(f"PRAGMA table_info({r[0]})")] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        for table, cols in tables.items():
            if table not in ("checkpoints", "checkpoint_writes", "checkpoint_blobs", "checkpoints_aids"):
                continue
            if "thread_id" not in cols:
                continue
            try:
                conn.execute(f"DELETE FROM {table} WHERE thread_id = ?", (thread_id,))
            except Exception:
                pass
        conn.commit()
        conn.close()
    except Exception:
        pass
