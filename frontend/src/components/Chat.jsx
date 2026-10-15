import { useCallback, useEffect, useRef, useState } from "react";
import { chat as chatOnce, getSlots, streamChat } from "../api.js";

let msgSeq = 0;
const nextId = () => `m-${Date.now()}-${msgSeq++}`;

/** Extract a page number from a citation (string | {page} | {page_number} | {metadata}). */
function citationPage(c) {
  if (c == null) return null;
  if (typeof c === "number") return c;
  if (typeof c === "string") {
    const m = c.match(/(\d+)/);
    return m ? m[1] : null;
  }
  if (typeof c === "object") {
    const v = c.page ?? c.page_number ?? c.pageno ?? c?.metadata?.page;
    if (v !== undefined && v !== null && String(v).match(/\d/)) return String(v).match(/\d+/)[0];
    return null;
  }
  return null;
}

function citationText(c) {
  if (c == null) return "";
  if (typeof c === "string") return c;
  if (typeof c === "object") return c.text ?? c.snippet ?? c.content ?? JSON.stringify(c);
  return String(c);
}

function Citations({ citations }) {
  if (!citations || citations.length === 0) return null;
  return (
    <details className="mt-2 rounded-md border border-slate-200 bg-slate-50 px-2 py-1 text-xs">
      <summary
        className="cursor-pointer font-medium text-slate-600 hover:text-slate-900"
        aria-label={`Show ${citations.length} citations`}
      >
        Sources ({citations.length})
      </summary>
      <ul className="mt-1 space-y-1">
        {citations.map((c, i) => {
          const page = citationPage(c);
          return (
            <li key={i} className="text-slate-600">
              <span className="mr-1 inline-block rounded bg-slate-200 px-1.5 py-0.5 font-mono text-[11px] font-semibold text-slate-700">
                {page ? `[Page ${page}]` : `[${i + 1}]`}
              </span>
              <span className="break-words">{citationText(c)}</span>
            </li>
          );
        })}
      </ul>
    </details>
  );
}

function BookingCard({ booking }) {
  if (!booking) return null;
  const { name, email, slot, reference } = booking;
  if (!name && !email && !slot && !reference) return null;
  return (
    <div
      className="mt-2 rounded-md border border-emerald-200 bg-emerald-50 px-2 py-1.5 text-xs text-emerald-900"
      role="status"
      aria-label={reference ? `Booking confirmed ${reference}` : "Booking progress"}
    >
      {reference ? (
        <p>
          <span className="font-semibold">Booked {reference}</span>
          {[name, email, slot].filter(Boolean).join(" · ") && (
            <span> — {[name, email, slot].filter(Boolean).join(" · ")}</span>
          )}
        </p>
      ) : (
        <p>
          <span className="font-semibold">Booking…</span>{" "}
          {[name, email, slot].filter(Boolean).join(" · ")}
        </p>
      )}
    </div>
  );
}

export default function Chat({ threadId, onStatusChange, onRouteChange }) {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [slots, setSlots] = useState([]);
  const [slotsError, setSlotsError] = useState("");
  const bottomRef = useRef(null);
  const inputRef = useRef(null);
  const busyRef = useRef(false);

  // Auto-scroll on new content.
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages, busy]);

  // Load quick-book slots once.
  useEffect(() => {
    let cancelled = false;
    getSlots()
      .then((s) => {
        if (!cancelled) setSlots(s.slice(0, 3));
      })
      .catch(() => {
        if (!cancelled) setSlotsError("Slots unavailable");
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const patchMessage = useCallback((id, patch) => {
    setMessages((prev) => prev.map((m) => (m.id === id ? { ...m, ...patch } : m)));
  }, []);

  const appendToken = useCallback((id, tok) => {
    setMessages((prev) =>
      prev.map((m) => (m.id === id ? { ...m, content: m.content + tok } : m))
    );
  }, []);

  const send = useCallback(
    async (rawText) => {
      const text = (rawText ?? input).trim();
      if (!text || busyRef.current) return;
      busyRef.current = true;
      setBusy(true);
      setError("");
      onStatusChange?.("streaming");
      setInput("");

      const userMsg = { id: nextId(), role: "user", content: text };
      const aiId = nextId();
      setMessages((prev) => [...prev, userMsg, { id: aiId, role: "assistant", content: "" }]);

      /** Commit a finished assistant turn. */
      const finish = (final, route) => {
        patchMessage(aiId, {
          content: final.reply || "",
          citations: Array.isArray(final.citations) ? final.citations : [],
          booking: final.booking || null,
        });
        if (route) onRouteChange?.(route);
      };

      try {
        // Try SSE streaming first.
        const streamed = await streamChat(text, threadId, {
          onNode: (n) => {
            if (n?.route) onRouteChange?.(n.route);
          },
          onToken: (tok) => appendToken(aiId, tok),
          onDone: (d) => {
            if (d?.route) onRouteChange?.(d.route);
            patchMessage(aiId, {
              citations: Array.isArray(d?.citations) ? d.citations : [],
              booking: d?.booking || null,
            });
          },
        });
        // Backend stream carries route/thread but not citations/booking yet:
        // if the streamed reply has no citations, top up with one plain call? No —
        // that would double-invoke the graph. Instead accept stream result as-is,
        // and only fall back to plain chat when the stream produced nothing.
        if (!streamed.reply) {
          const full = await chatOnce(text, threadId);
          finish(full, full.route);
        } else {
          if (streamed.route) onRouteChange?.(streamed.route);
          if (Array.isArray(streamed.citations) && streamed.citations.length) {
            patchMessage(aiId, { citations: streamed.citations });
          }
          if (streamed.booking) patchMessage(aiId, { booking: streamed.booking });
        }
        onStatusChange?.("idle");
      } catch (err) {
        // SSE failed (offline backend, proxy, etc.) — fall back to plain POST once.
        try {
          onStatusChange?.("loading");
          const full = await chatOnce(text, threadId);
          finish(full, full.route);
          onStatusChange?.("idle");
        } catch (err2) {
          const msg = err2 instanceof Error ? err2.message : String(err2);
          setError(`Couldn't reach the assistant (${msg}). Check the backend at :8000.`);
          patchMessage(aiId, {
            content: "Sorry — I couldn't reach the server. Please try again.",
          });
          onStatusChange?.("error");
        }
      } finally {
        busyRef.current = false;
        setBusy(false);
        inputRef.current?.focus();
      }
    },
    [appendToken, input, onRouteChange, onStatusChange, patchMessage, threadId]
  );

  const onSubmit = (e) => {
    e.preventDefault();
    send();
  };

  const onSlotClick = (slot) => {
    // One click books: send the slot text straight into the booking flow.
    send(slot);
  };

  const showEmpty = messages.length === 0 && !busy && !error;

  return (
    <section aria-label="Conversation" className="flex flex-col">
      {/* Slot quick actions */}
      <div className="mb-3" aria-label="Quick booking slots">
        {slots.length > 0 ? (
          <div className="flex flex-wrap gap-2">
            {slots.map((s) => (
              <button
                key={s}
                type="button"
                onClick={() => onSlotClick(s)}
                disabled={busy}
                className="rounded-full border border-slate-300 bg-white px-3 py-1.5 text-xs font-medium text-slate-700 hover:border-slate-400 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50"
                aria-label={`Book slot ${s}`}
              >
                {s}
              </button>
            ))}
          </div>
        ) : (
          <p className="text-xs text-slate-400" role="status">
            {slotsError || "Loading slots…"}
          </p>
        )}
      </div>

      {/* Messages */}
      <div
        className="chat-scroll flex min-h-[40vh] max-h-[60vh] flex-col gap-3 overflow-y-auto rounded-lg border border-slate-200 bg-white p-3 sm:p-4"
        role="log"
        aria-live="polite"
        aria-label="Chat messages"
      >
        {showEmpty && (
          <div className="m-auto max-w-sm text-center">
            <p className="font-medium text-slate-700">How can I help?</p>
            <p className="mt-1 text-sm text-slate-500">
              Ask about performance reviews, leave, or benefits — or tap a slot above to
              book a review. Try: “How do performance reviews work?”
            </p>
          </div>
        )}

        {messages.map((m) => (
          <article
            key={m.id}
            aria-label={m.role === "user" ? "Your message" : "Assistant message"}
            className={`max-w-[90%] rounded-lg px-3 py-2 text-sm leading-relaxed sm:max-w-[80%] ${
              m.role === "user"
                ? "self-end bg-slate-900 text-white"
                : "self-start border border-slate-200 bg-slate-50 text-slate-900"
            }`}
          >
            <p className="whitespace-pre-wrap break-words">
              {m.content || (busy ? "…" : "")}
            </p>
            {m.role === "assistant" && <Citations citations={m.citations} />}
            {m.role === "assistant" && <BookingCard booking={m.booking} />}
          </article>
        ))}

        {busy && (
          <p className="self-start text-xs text-slate-400" role="status" aria-label="Assistant is typing">
            <span className="animate-pulse">Assistant is typing…</span>
          </p>
        )}
        <div ref={bottomRef} />
      </div>

      {/* Error */}
      {error && (
        <div
          className="mt-2 rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800"
          role="alert"
        >
          {error}
        </div>
      )}

      {/* Input */}
      <form onSubmit={onSubmit} className="mt-3 flex gap-2">
        <label htmlFor="chat-input" className="sr-only">
          Message the HR assistant
        </label>
        <input
          id="chat-input"
          ref={inputRef}
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Escape") setInput("");
          }}
          placeholder="Ask a handbook question or book a review…"
          autoComplete="off"
          disabled={busy}
          className="min-w-0 flex-1 rounded-md border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 placeholder:text-slate-400 focus:border-slate-500 disabled:opacity-60"
        />
        <button
          type="submit"
          disabled={busy || !input.trim()}
          className="shrink-0 rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-700 disabled:cursor-not-allowed disabled:opacity-50"
          aria-label={busy ? "Sending message" : "Send message"}
        >
          {busy ? "…" : "Send"}
        </button>
      </form>
      <p className="mt-1 text-xs text-slate-400">
        Enter to send · Esc to clear · conversation persists by thread ID.
      </p>
    </section>
  );
}
