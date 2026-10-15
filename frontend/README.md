# HR Assistant — Frontend

React + Vite + Tailwind CSS v4. Chat UI for the FastAPI backend (`http://localhost:8000`).

> No `tailwind.config.js` — Tailwind v4 is configured via the `@tailwindcss/vite`
> plugin (`vite.config.js`) and `@import "tailwindcss"` in `src/index.css`.

## Run

```bash
npm install
npm run dev      # http://localhost:5173
```

Backend first:

```bash
uvicorn backend.app.main:app --reload --port 8000
```

Point at another backend with `VITE_API_URL`:

```bash
# .env
VITE_API_URL=http://localhost:8000
```

## What it does

- `src/api.js` — `chat()` (POST `/api/chat`), `streamChat()` (POST
  `/api/chat/stream` SSE parser for `event:`/`data:` frames: `node` → `token`* →
  `done`, plus forward-compat `citations`/`booking`/`meta`/`error`), `getSlots()`
  (GET `/api/slots`), `reset()` (POST `/api/reset`).
- `src/App.jsx` — header with status dot (idle/loading/streaming/error), node
  badge (`Router → FAQ RAG` / `Router → Booking`), thread_id display with
  Copy/New; thread persists in `localStorage` (`hr.thread_id`).
- `src/components/Chat.jsx` — message list with citation expander (`[Page N]`
  sources + booking card), slot quick-buttons (one tap sends the slot), input
  with loading/error/empty states, auto-scroll, keyboard accessible
  (`Enter` send, `Esc` clear, `aria-live` log, labelled controls), mobile-first
  responsive (`max-w-3xl`, wrapping header/buttons).

## Notes

- Design is flat white/slate (no gradients), visible `:focus-visible` rings,
  `prefers-reduced-motion` respected.
- Streaming shows tokens live; if SSE fails it falls back to plain `chat()`
  once rather than double-invoking the graph.
