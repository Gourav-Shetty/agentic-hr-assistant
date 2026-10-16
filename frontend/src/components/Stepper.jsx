const STEPS = ["Name", "Email", "Slot", "Confirmed"];

const STAGE_TO_INDEX = {
  booking_name: 0,
  booking_email: 1,
  booking_slot: 2,
  booking_confirm: 3,
};

/**
 * Horizontal 4-step booking tracker: Name -> Email -> Slot -> Confirmed.
 * Hidden when no booking is in progress (idle / greeting / unknown).
 */
export function Stepper({ stage }) {
  const s = String(stage || "").toLowerCase();

  if (!s || s === "idle" || s === "greeting") return null;

  let activeIndex = -1;
  if (s === "done") {
    activeIndex = STEPS.length; // all done
  } else {
    activeIndex = STAGE_TO_INDEX[s] ?? -1;
  }
  if (activeIndex < 0) return null;

  const doneCount = s === "done" ? STEPS.length : activeIndex;

  return (
    <nav aria-label="Booking progress" className="mb-3">
      <ol className="flex items-start gap-1 sm:gap-2">
        {STEPS.map((label, i) => {
          const state = i < doneCount ? "done" : i === activeIndex ? "active" : "todo";
          const isLast = i === STEPS.length - 1;
          return (
            <li
              key={label}
              className={`flex min-w-0 ${isLast ? "" : "flex-1"} items-start`}
              aria-current={state === "active" ? "step" : undefined}
            >
              <div className="flex min-w-0 flex-col items-center gap-1">
                <span
                  className={`flex h-6 w-6 items-center justify-center rounded-full border text-xs font-semibold ${
                    state === "done"
                      ? "border-slate-900 bg-slate-900 text-white"
                      : state === "active"
                        ? "border-slate-900 bg-white text-slate-900"
                        : "border-slate-300 bg-white text-slate-400"
                  }`}
                  aria-hidden="true"
                >
                  {state === "done" ? "✓" : i + 1}
                </span>
                <span
                  className={`max-w-full truncate text-[11px] font-medium sm:text-xs ${
                    state === "todo" ? "text-slate-400" : "text-slate-700"
                  }`}
                >
                  {label}
                </span>
                <span className="sr-only">
                  {`${label}: ${state}`}
                </span>
              </div>
              {!isLast && (
                <div
                  className={`mx-1 mt-3 h-px flex-1 sm:mx-2 ${
                    i < doneCount ? "bg-slate-900" : "bg-slate-200"
                  }`}
                  aria-hidden="true"
                />
              )}
            </li>
          );
        })}
      </ol>
    </nav>
  );
}

export default Stepper;
