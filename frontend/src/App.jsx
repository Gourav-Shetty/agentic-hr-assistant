import { useCallback, useEffect, useState } from "react";
import Chat from "./components/Chat.jsx";
import { reset as resetThread } from "./api.js";

const THREAD_KEY = "hr.thread_id";

function newThreadId() {
  if (typeof crypto !== "undefined" && crypto.randomUUID) return crypto.randomUUID();
  return `t-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;
}

function loadThreadId() {
  try {
    const saved = localStorage.getItem(THREAD_KEY);
    if (saved && saved.trim()) return saved;
  } catch {
    /* storage unavailable */
  }
  const fresh = newThreadId();
  try {
    localStorage.setItem(THREAD_KEY, fresh);
  } catch {
    /* noop */
  }
  return fresh;
}

/** Human label for the router badge. */
export function routeLabel(route) {
  const r = String(route || "").toLowerCase();
  if (r === "faq") return "Router → FAQ RAG";
  if (r === "booking") return "Router → Booking";
  if (!r) return "Router → —";
  return `Router → ${route}`;
}

const STATUS_META = {
  idle: { dot: "bg-emerald-500", text: "Idle" },
  loading: { dot: "bg-amber-500 animate-pulse", text: "Loading" },
  streaming: { dot: "bg-amber-500 animate-pulse", text: "Streaming" },
  error: { dot: "bg-red-500", text: "Error" },
};

export default function App() {
  const [threadId, setThreadId] = useState(() => loadThreadId());
  const [status, setStatus] = useState("idle");
  const [route, setRoute] = useState("");
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    try {
      localStorage.setItem(THREAD_KEY, threadId);
    } catch {
      /* noop */
    }
  }, [threadId]);

  const handleCopy = useCallback(async () => {
    try {
      await navigator.clipboard.writeText(threadId);
    } catch {
      // Fallback for non-secure contexts.
      const ta = document.createElement("textarea");
      ta.value = threadId;
      document.body.appendChild(ta);
      ta.select();
      try {
        document.execCommand("copy");
      } catch {
        /* noop */
      }
      ta.remove();
    }
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  }, [threadId]);

  const handleNew = useCallback(async () => {
    try {
      await resetThread(threadId);
    } catch {
      /* best-effort server reset; still rotate locally */
    }
    const fresh = newThreadId();
    try {
      localStorage.setItem(THREAD_KEY, fresh);
    } catch {
      /* noop */
    }
    setThreadId(fresh);
    setRoute("");
    setStatus("idle");
  }, [threadId]);

  const meta = STATUS_META[status] || STATUS_META.idle;

  return (
    <div className="min-h-full bg-slate-50 text-slate-900">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-3xl flex-col gap-3 px-4 py-4 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex items-center gap-3">
            <div
              className="flex h-9 w-9 items-center justify-center rounded-md bg-slate-900 text-sm font-bold text-white"
              aria-hidden="true"
            >
              HR
            </div>
            <div>
              <h1 className="text-base font-semibold leading-tight">HR Assistant</h1>
              <p className="text-xs text-slate-500">
                Handbook RAG + performance-review booking
              </p>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <span
              className="inline-flex items-center gap-1.5 rounded-full border border-slate-200 bg-slate-50 px-2.5 py-1 text-xs font-medium text-slate-700"
              role="status"
              aria-label={`Status: ${meta.text}`}
            >
              <span
                className={`inline-block h-2 w-2 rounded-full ${meta.dot}`}
                aria-hidden="true"
              />
              {meta.text}
            </span>
            <span
              className="inline-flex items-center rounded-full border border-slate-200 bg-slate-50 px-2.5 py-1 text-xs font-medium text-slate-700"
              aria-label={`Current node: ${routeLabel(route)}`}
              title={route ? `Last route: ${route}` : "No messages yet"}
            >
              {routeLabel(route)}
            </span>
          </div>
        </div>

        <div className="border-t border-slate-100">
          <div className="mx-auto flex max-w-3xl flex-wrap items-center gap-2 px-4 py-2">
            <span className="text-xs text-slate-500">Thread</span>
            <code
              className="max-w-full truncate rounded bg-slate-100 px-2 py-1 font-mono text-xs text-slate-700"
              title={threadId}
              aria-label={`Thread ID: ${threadId}`}
            >
              {threadId}
            </code>
            <button
              type="button"
              onClick={handleCopy}
              className="rounded-md border border-slate-300 bg-white px-2 py-1 text-xs font-medium text-slate-700 hover:bg-slate-50 focus-visible:outline-2"
              aria-label="Copy thread ID to clipboard"
            >
              {copied ? "Copied" : "Copy"}
            </button>
            <button
              type="button"
              onClick={handleNew}
              className="rounded-md border border-slate-300 bg-white px-2 py-1 text-xs font-medium text-slate-700 hover:bg-slate-50"
              aria-label="Start a new conversation thread"
            >
              New
            </button>
          </div>
        </div>
      </header>

      <main className="mx-auto flex max-w-3xl flex-col px-4 py-4">
        <Chat
          key={threadId}
          threadId={threadId}
          onStatusChange={setStatus}
          onRouteChange={setRoute}
        />
        <footer className="mt-3 text-center text-xs text-slate-400">
          Answers cite handbook pages as [Page N]. Booking confirms with a #REV reference.
        </footer>
      </main>
    </div>
  );
}
