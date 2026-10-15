"""Chat API: POST /api/chat, POST /api/chat/stream (SSE), POST /api/reset."""

import asyncio
import json
import os
import sqlite3
import uuid
from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from backend.app.schemas import BookingInfo, ChatRequest, ChatResponse

router = APIRouter(prefix="/api", tags=["chat"])

_graph = None


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

def _tid(raw: str | None) -> str:
    return (raw or "").strip() or str(uuid.uuid4())

async def _run(graph, message: str, thread_id: str):
    """Invoke graph with full history appended (messages has no reducer)."""
    config = _config(thread_id)
    payload = {"messages": [*_history(graph, config), {"role": "user", "content": message}]}
    res = await asyncio.to_thread(graph.invoke, payload, config)
    return (res if isinstance(res, dict) else {}), thread_id


def _make_checkpointer():
    try:
        from langgraph.checkpoint.sqlite import SqliteSaver
    except ImportError:
        return None
    try:
        conn = sqlite3.connect(_db_path(), check_same_thread=False)
        cp = SqliteSaver(conn)
        setup = getattr(cp, "setup", None)
        if callable(setup):
            try:
                setup()
            except Exception:
                pass
        return cp
    except Exception:
        try:
            return SqliteSaver.from_conn_string(_db_path())
        except Exception:
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
        return [m for m in (vals.get("messages") or []) if isinstance(m, dict)]
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
    )


def _chunks(text: str, size: int = 24) -> list:
    return [text[i : i + size] for i in range(0, len(text), size)] or [""]


def _err(exc: Exception) -> JSONResponse:
    return JSONResponse(status_code=500, content={"detail": f"{type(exc).__name__}: {exc}"})


@router.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    try:
        thread_id = _tid(req.thread_id)
        result, _ = await _run(get_graph(), req.message, thread_id)
        return _respond(result, thread_id)
    except Exception as exc:
        return _err(exc)

@router.post("/chat/stream")
async def chat_stream(req: ChatRequest):
    try:
        thread_id = _tid(req.thread_id)
        result, _ = await _run(get_graph(), req.message, thread_id)
        resp = _respond(result, thread_id)
        async def gen():
            yield {"event": "node", "data": json.dumps({"route": resp.route, "thread_id": thread_id})}
            for tok in _chunks(resp.reply):
                yield {"event": "token", "data": json.dumps({"token": tok})}
                await asyncio.sleep(0)
            yield {"event": "done", "data": json.dumps({"thread_id": thread_id, "route": resp.route})}
        try:
            from sse_starlette.sse import EventSourceResponse
            return EventSourceResponse(gen())
        except ImportError:
            from fastapi.responses import StreamingResponse
            async def raw():
                async for evt in gen():
                    yield f"event: {evt['event']}\ndata: {evt['data']}\n\n"
            return StreamingResponse(raw(), media_type="text/event-stream",
                                     headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
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
        tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")]
        for table in ("checkpoints", "checkpoint_writes", "checkpoint_blobs"):
            if table in tables:
                try:
                    conn.execute(f"DELETE FROM {table} WHERE thread_id = ?", (thread_id,))
                except Exception:
                    pass
        conn.commit()
        conn.close()
    except Exception:
        pass
