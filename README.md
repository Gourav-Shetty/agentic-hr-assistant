# Agentic HR Assistant

Full-stack agentic assistant: RAG over `employee_handbook.pdf` + multi-turn
Performance Review booking with FAQ interrupt-resume. Runs offline without API keys.

## Architecture

```
              +------------------+
              |  React (Vite)    |
              |  thread_id, badge|
              |  slot buttons    |
              +--------+---------+
                       |  POST /api/chat  |  SSE /api/chat/stream  |  GET /api/slots
              +--------v---------+
              |  FastAPI         |
              +--------+---------+
                       |
              +--------v---------+
              |  Router          |  faq | booking | mixed | greeting
              +---+----------+---+
                  |          |
          +-------v---+ +----v----------+
          |  RAG node | | Booking node  |
          | retriever | | name/email/   |
          | -> [Page] | | slot ->#REV   |
          +-------+---+ +----+----------+
                  |          |
                  +----+-----+
                       |
              +--------v---------+
              | SqliteSaver      |
              | data/checkpoints |
              | .db (thread_id)  |
              +------------------+
```

RAG retrieval: Chroma dense embeddings -> `data/chunks.json` TF-IDF -> keyword
overlap fallback. Booking: regex name/email extraction + fuzzy slot match,
`#REV-XXXX` reference. Mixed route answers the FAQ via RAG first, then resumes
booking (`booking_pending` flag) so no collected field is ever dropped.

## Quickstart

1. Install backend: `pip install -r backend/requirements.txt`
2. Ingest handbook: `python scripts/download_pdf.py && python -m backend.app.rag.ingest`
3. Run backend: `uvicorn backend.app.main:app --reload --port 8000`
4. Run frontend: `cd frontend && npm install && npm run dev`

Docker: `docker-compose up --build` (backend `:8000`, frontend `:5173` with `VITE_API_URL`).

Copy `.env.example` to `.env` for `GROQ_API_KEY` / `GEMINI_API_KEY`
(optional — rule-based fallback works offline).

## API

| Method | Path              | Request                       | Response                                                        |
| ------ | ----------------- | ----------------------------- | --------------------------------------------------------------- |
| GET    | `/health`         | —                             | `{status: "ok"}`                                                |
| POST   | `/api/chat`       | `{message, thread_id}`        | `{reply, route, citations, booking, thread_id}`                 |
| POST   | `/api/chat/stream`| `{message, thread_id}`        | SSE events `node` (`{route, thread_id}`), `token`, `done`       |
| GET    | `/api/slots`      | —                             | `{slots: [3 strings]}`                                          |
| POST   | `/api/reset`      | `{thread_id}`                 | `{thread_id, status: "reset"}`                                  |

- `route`: `faq | booking | mixed | greeting` (shown as the node badge in the UI).
- `citations`: `[{text, page}]`, rendered as `[Page N]`.
- `booking`: `{name, email, slot, reference}` (`reference` like `#REV-XXXX` when confirmed).
- `thread_id`: server-generated UUID when empty; conversation persists per thread via SqliteSaver.

## Verification artifacts

- `pytest tests/ -v` — router intent (faq/booking/mixed), booking extraction/validation, RAG page citations.
- `python scripts/verify.py` — headless end-to-end sample dialogue: RAG citation + booking + interrupt-resume.
- Manual: UI books in <5 clicks (slot button = 1 click into booking flow), interrupt with an FAQ mid-booking and resumes, SSE badge updates per turn, restart backend and `thread_id` history persists.

## AI Engineering Log

Tools used: Copilot, Cursor, Claude, ChatGPT.

1. **Checkpointer serialization (Pydantic bug)** — first `AgentState` held Pydantic models;
   `SqliteSaver` pickling/JSON checkpoint writes failed on resume. Fix: state is now a
   `TypedDict` with JSON-serializable primitives only (`messages` as plain
   `{role, content}` dicts); Pydantic `ChatRequest`/`ChatResponse` live strictly at the
   API boundary (`backend/app/schemas.py`, never in state).
2. **Async SSE + `to_thread` fix** — `graph.invoke()` is blocking and stalled the
   `EventSourceResponse` generator, starving concurrent streams. Fix: `await
   asyncio.to_thread(graph.invoke, payload, config)` in `_run`
   (`backend/app/api/chat.py`), chunked `token` events, `asyncio.sleep(0)` yields,
   plus a non-streaming `StreamingResponse` fallback when `sse-starlette` is missing.
3. **Chroma Windows fallback (TF-IDF)** — `chromadb`/`sentence-transformers` builds
   fail on some Windows setups and offline eval has no keys. Fix: layered retriever
   (`backend/app/rag/retriever.py`): Chroma dense -> pure-stdlib TF-IDF over
   `data/chunks.json` -> keyword overlap. All layers return `[{text, page}]` with
   integer pages so `[Page N]` citations work in every environment.
