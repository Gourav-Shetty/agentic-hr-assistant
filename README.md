# Agentic HR Assistant — Full-Stack LangGraph RAG + Booking

![Python 3.11](https://img.shields.io/badge/python-3.11-blue) ![FastAPI](https://img.shields.io/badge/FastAPI-async-green) ![LangGraph](https://img.shields.io/badge/LangGraph-StateGraph-purple) ![React](https://img.shields.io/badge/React-Vite-61dafb) ![Docker](https://img.shields.io/badge/docker-compose-ready-blue)

Autonomous conversational assistant with **dual responsibility**: Domain Knowledge Retrieval (RAG over `employee_handbook.pdf`) + Transactional Booking (multi-turn Performance Review scheduling). Preserves state across turns by `thread_id`, answers FAQ mid-booking and resumes without losing parameters.

> Runs **offline without API keys** (rule-based + TF-IDF fallback). Add Groq/Gemini keys for fluent LLM answers.

Repo: `https://github.com/Gourav-Shetty/agentic-hr-assistant`

## Demo — context interleaving (real output)

![Chat demo](docs/screenshot_chat.png)

```
User:  Hi, I need to book a 1-on-1 Performance Review session.
Agent [booking]: Sure, let's book your performance review. What is your full name?

User:  Alex Chen (alex.chen@example.com). Wait, before that, how often are performance reviews conducted?
Agent [mixed, citations=[4,8]]: Based on the handbook: [Page 4] ... Performance reviews are conducted annually ...
        Returning to your booking — Which slot works for you? Options: Tomorrow 11AM, Tomorrow 3PM, Friday 10:30AM IST
        booking={name: Alex Chen, email: alex.chen@example.com}

User:  Friday at 10:30 AM
Agent [booking]: Done! Booked your performance review Friday 10:30AM IST for Alex Chen (alex.chen@example.com). Reference #REV-8RCV.
```

Full JSON: `docs/demo_transcript.json`. Verification log: `docs/verify_log.txt` (14/14 PASS).

## Architecture

![Architecture](docs/architecture.png)

```mermaid
flowchart TB
  UI[React Vite<br/>thread_id badge slot buttons] -->|POST /api/chat<br/>SSE /stream| API[FastAPI async]
  API --> R[Router<br/>faq booking mixed greeting]
  R -->|faq| RAG[FAQ RAG Node<br/>Chroma TF-IDF Page N]
  R -->|booking| BK[Booking Node<br/>name email slot REV]
  R -->|mixed| RAG
  RAG -->|booking_pending| BK
  RAG --> END
  BK --> END
  BK -.->|SqliteSaver by thread_id| DB[(checkpoints.db)]
  RAG -.-> DB
```

State (`backend/app/graph/state.py`): `TypedDict` JSON-only — `messages, name, email, slot, stage, booking_pending, last_route, citations, booking_ref`. No Pydantic in state (SqliteSaver-safe). Pydantic lives only at API boundary (`schemas.py`).

![State machine](docs/state_diagram.png)

Router (`router.py`): keywords first, LLM-free. Active booking defaults to `booking`; pure FAQ interrupt → `mixed`; idle slot/email clicks (`Tomorrow 11AM`, `ada@x.com`) → `booking`; `faq+booking verbs` → `booking`. RAG short-circuits greetings.

RAG (`rag/`): `pypdf` per-page parse → 800/150 splitter → `all-MiniLM-L6-v2` → Chroma persistent `./data/chroma` (page+source metadata). Fallbacks: `data/chunks.json` TF-IDF → keyword overlap. Always `[{text, page, source}]`.
Knowledge base is dual-PDF: `employee_handbook.pdf` (source=`handbook`, policies + Page-4 performance reviews) + `Northwind_Standard_Benefits_Details.pdf` (source=`benefits`, PTO/leave/health). Context cites `[Page N]` or `[Page N (benefits)]`.

LLM (`graph/llm.py`): Groq `llama-3.3-70b-versatile` → Gemini `gemini-2.0-flash` → rule fallback. Guardrails (`guardrails.py`): injection blocklist enforced in `/api/chat` + `/stream`, email regex, slot allowlist, 2000-char cap.

## Quickstart

```bash
pip install -r backend/requirements.txt
cp .env.example .env   # optional: add GROQ_API_KEY / GEMINI_API_KEY, no quotes
python scripts/download_pdf.py          # handbook + benefits PDFs
python -m backend.app.rag.ingest --all  # 448 chunks (27 handbook + 421 benefits)
uvicorn backend.app.main:app --port 8000
cd frontend && npm install && npm run dev   # http://localhost:5173
```

Docker: `docker-compose up --build` → backend `:8000`, frontend `:5173`.

`.env` is gitignored and never pushed. Commit only `.env.example`.

## API

| Method | Path | Response |
|---|---|---|
| GET | `/health` | `{status: ok}` |
| POST | `/api/chat` `{message, thread_id}` | `{reply, route, citations, booking{name,email,slot,reference}, thread_id}` |
| POST | `/api/chat/stream` | SSE `node{route,thread_id}` → `token{token}*` → `done{thread_id,route,citations,booking,reply}` |
| GET | `/api/slots` | `{slots: [Tomorrow 11AM, Tomorrow 3PM, Friday 10:30AM IST]}` |
| POST | `/api/reset` `{thread_id}` | `{thread_id, status: reset}` |

`route` drives UI badge: `Router → FAQ RAG / Booking / Mixed`. `citations` renders `[Page N]`. `booking.reference` like `#REV-XXXX` on `done`.

Frontend (`frontend/src`): `api.js` SSE parser, `App.jsx` thread copy/new + status dot, `Chat.jsx` slot buttons, citation `<details>`, booking card, empty/typing/error states, aria-live, mobile-first.

## Verification

```bash
pytest tests/ -v          # 9 passed — router, booking validation, RAG pages
python scripts/verify.py  # OK — slots, Page-4 cite, booking, mixed resume, SSE, reset
npm run build             # vite build success (frontend/)
```

```
[PASS] RAG answer cites Page 4 (citations=[4, 3])
[PASS] booking asks for name / email / slot
[PASS] booking completes with ref #REV-9BXE
[PASS] FAQ interrupt answered mid-booking (route=mixed)
[PASS] booking resumes after interrupt (name kept)
[PASS] SSE stream emits node/token/done events
verify: OK
```

Manual: book via slot button on fresh thread, interrupt with PTO question mid-booking, restart backend — same `thread_id` history persists via `data/checkpoints.db`.

## AI Engineering Log

Tools: Copilot, Cursor, Claude, ChatGPT.

1. **Checkpointer serialization** — AI put Pydantic models in `AgentState`; `SqliteSaver` checkpoint writes failed on resume. Diagnosed via `graph.get_state` pickle error. Fix: `TypedDict` primitives only, Pydantic at boundary.
2. **Blocking SSE** — AI called `graph.invoke` directly in async SSE generator, stalling streams. Diagnosed via concurrent stream timeout. Fix: `await asyncio.to_thread(graph.invoke…)` + `await asyncio.sleep(0)` yields in `api/chat.py`.
3. **Chroma Windows + offline** — AI assumed `chromadb` + OpenAI embeddings always available; builds fail offline. Diagnosed via `ImportError` on clean Windows. Fix: layered retriever Chroma → stdlib TF-IDF → keyword, local `all-MiniLM` only, `chunks.json` always written.
4. **Router amnesia** — AI returned `mixed` for `book + performance review`, dropping booking start; slot texts (`Friday 10:30AM`) had no booking keywords → `greeting`. Diagnosed via `verify.py` + TestClient transcript. Fix: booking verbs win idle, slot/email clicks → `booking`, active FAQ-only → `mixed`, bare-name extraction only with email present, FAQ+booking replies merged with `Returning to your booking —` prefix preserving citations.

## Structure

```
backend/app/{main.py,config.py,schemas.py,graph/{state,router,nodes,graph,llm,guardrails},rag/{ingest,retriever},tools/booking,api/{chat,slots}}
frontend/src/{App.jsx,api.js,components/Chat.jsx}
scripts/{download_pdf.py,verify.py,make_diagrams.py,make_screenshot.py}
tests/test_{router,booking,rag}.py  docs/{architecture.png,state_diagram.png,screenshot_chat.png,demo_transcript.json,verify_log.txt}
```

## Submission

Public repo with clean history, `.env.example`, `Dockerfile` + `docker-compose.yml`, `SPEC.md`, `tasks/plan.md`, `docs/ADR-001-checkpointer.md`. Deadline 18 Oct 2026.
