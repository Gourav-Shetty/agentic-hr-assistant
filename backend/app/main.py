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
    return {"status": "ok"}


@app.exception_handler(Exception)
async def all_errors(request: Request, exc: Exception):
    return JSONResponse(status_code=500, content={"detail": f"{type(exc).__name__}: {exc}"})
