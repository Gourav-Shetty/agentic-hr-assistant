# Implementation Plan: Agentic HR Assistant

## Overview
Contract-first vertical slices: API contract -> graph+LLM -> RAG -> FastAPI+SSE -> React -> hardening/docker/tests/README.

## Architecture Decisions
- SqliteSaver file `data/checkpoints.db` with check_same_thread=False + lock, not MemorySaver (persists restart, 35% weight)
- Embeddings local all-MiniLM-L6-v2, Chroma persistent, TF-IDF fallback for offline/Windows
- LLM wrapper: Groq llama-3.3-70b-versatile primary, gemini-2.0-flash fallback, rule-based last resort
- State TypedDict JSON-only to avoid checkpointer serialization hallucinations
- SSE via fastapi.sse EventSourceResponse, events: node, token, done

## Task List
### Phase 1: Foundation (contract + guardrails)
- [ ] Task 1: requirements, .env.example, .gitignore, config, schemas
- [ ] Task 2: guardrails + booking tool + router unit logic
### Checkpoint: Foundation
### Phase 2: Core agent + RAG
- [ ] Task 3: LLM wrapper + graph state/nodes/graph compile
- [ ] Task 4: PDF download + ingest + retriever with page citations
### Checkpoint: Core
### Phase 3: API + UI
- [ ] Task 5: FastAPI main + chat + slots + SSE stream
- [ ] Task 6: React Vite chat + badge + thread + slots
### Checkpoint: E2E
### Phase 4: Polish
- [ ] Task 7: tests + verify.py
- [ ] Task 8: Docker + README + AI Log
### Checkpoint: Complete

## Risks and Mitigations
| Risk | Impact | Mitigation |
| Chroma Windows build fail | High | TF-IDF fallback, pin chromadb>=0.4 |
| Groq rate limit | Med | Gemini fallback + rule fallback, retry |
| Sqlite lock | Med | check_same_thread=False, single conn |
| Tailwind v4 Vite plugin | Low | follow official Vite plugin docs |

## Open Questions
- None
