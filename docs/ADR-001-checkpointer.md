# ADR-001: SqliteSaver file checkpointer (not MemorySaver)

Date: 2026-10-15 · Status: accepted

## Context

Conversations must persist by `thread_id` across backend restarts, and the
interrupt-resume booking flow depends on prior state. `MemorySaver` loses
everything on restart.

## Decision

Use `langgraph-checkpoint-sqlite` `SqliteSaver` on `data/checkpoints.db` with
`check_same_thread=False` + short timeout. State is a JSON-only `TypedDict`
(no Pydantic) so checkpoints serialize. Thread reset deletes that
`thread_id`'s rows from `checkpoints`/`checkpoint_writes`/`checkpoint_blobs`.

## Consequences

- Restart-safe resume; `POST /api/reset` clears one thread.
- Single-file DB, no extra service; concurrent writes serialize on sqlite lock.
