"""FastAPI entrypoint: CORS *, /health, routers, lifespan warms graph/checkpoints."""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.app.api.chat import get_graph, router as chat_router
from backend.app.api.slots import router as slots_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        (Path(__file__).resolve().parents[2] / "data").mkdir(parents=True, exist_ok=True)
        get_graph()  # compile graph + init SqliteSaver file (data/checkpoints.db)
    except Exception as exc:
        print(f"lifespan warmup skipped: {exc}")
    yield


app = FastAPI(title="Agentic HR Assistant", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat_router)
app.include_router(slots_router)


@app.get("/health")
async def health():
    info: dict = {"status": "ok"}
    try:
        from backend.app.version import APP_VERSION

        info["version"] = APP_VERSION
    except ImportError:
        info["version"] = "unknown"
    try:
        from backend.app.api.chat import _db_path, get_graph

        get_graph()  # ensure compiled
        import sqlite3

        conn = sqlite3.connect(_db_path(), check_same_thread=False, timeout=5)
        tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        threads = 0
        if "checkpoints" in tables:
            try:
                threads = conn.execute("SELECT COUNT(DISTINCT thread_id) FROM checkpoints").fetchone()[0]
            except Exception:
                threads = -1
        conn.close()
        info["checkpointer"] = "sqlite" if "checkpoints" in tables else "none"
        info["threads"] = threads
    except Exception as exc:
        info["checkpointer"] = f"error: {type(exc).__name__}"
    return info


@app.exception_handler(Exception)
async def all_errors(request: Request, exc: Exception):
    return JSONResponse(status_code=500, content={"detail": f"{type(exc).__name__}: {exc}"})
