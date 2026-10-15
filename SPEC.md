# Spec: Agentic HR Assistant

## Objective
End-to-end full-stack agentic assistant: RAG over employee_handbook.pdf + multi-turn Performance Review booking with context interleaving. Must pass sample dialogue, persist by thread_id, stream via SSE, show node badge.

User: HR candidate evaluator. Success: `scripts/verify.py` passes RAG citation + booking + interrupt-resume; UI books in <5 clicks; runs offline without keys.

## Tech Stack
- Python 3.11, FastAPI, uvicorn, sse-starlette (via fastapi.sse), pydantic
- langgraph, langchain-core, langgraph-checkpoint-sqlite, langchain-groq, langchain-google-genai, langchain-community, chromadb, sentence-transformers, pypdf
- Frontend: React Vite + Tailwind v4, fetch SSE
- Tests: pytest

## Commands
Build backend: `pip install -r backend/requirements.txt`
Ingest: `python scripts/download_pdf.py && python -m backend.app.rag.ingest`
Run backend: `uvicorn backend.app.main:app --reload --port 8000`
Run frontend: `cd frontend && npm install && npm run dev`
Test: `pytest tests/ -v`
Verify: `python scripts/verify.py`
Docker: `docker-compose up --build`

## Project Structure
backend/app/{main.py,schemas.py,config.py,graph/{state.py,router.py,nodes.py,graph.py,llm.py,guardrails.py},rag/{ingest.py,retriever.py},tools/booking.py,api/{chat.py,slots.py}}
frontend/src/{App.jsx,api.js,components/Chat.jsx}
scripts/{download_pdf.py,verify.py}
tests/test_{router,booking,rag}.py
data/, tasks/

## Code Style
- Python: black-ish, type hints, async FastAPI, TypedDict for LangGraph state (JSON-serializable only)
- Example: `config: RunnableConfig = {"configurable": {"thread_id": thread_id}}`
- Never put Pydantic objects in checkpointer state.

## Testing Strategy
- pytest: router intent (faq vs booking vs mixed), booking extraction/validation, RAG retrieval returns page numbers
- verify.py: headless end-to-end sample dialogue
- Manual: UI books + interrupt resumes + SSE badge updates

## Boundaries
- Always: validate email/slot at boundary, cite [Page N], thread_id per conversation, no secrets in repo
- Ask first: new deps, schema changes, CORS changes
- Never: commit .env, expose system prompt, trust LLM output for tool args without validation

## Success Criteria
- [ ] POST /api/chat returns {reply, route, citations, booking, thread_id}
- [ ] GET /api/slots returns 3 slots
- [ ] SSE /api/chat/stream emits node then tokens
- [ ] SqliteSaver persists across restarts
- [ ] RAG answers performance reviews Q with Page 4 citation
- [ ] Booking collects name/email/slot -> #REV-XXXX, resumes after FAQ interrupt
- [ ] React shows thread_id, badge, slot buttons
- [ ] README has arch diagram, run guide, AI Log, screenshots/logs
- [ ] Dockerfile + docker-compose.yml present

## Open Questions
- None. Groq + Gemini keys available, offline fallback required.
