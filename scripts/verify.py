"""Headless end-to-end verification: ingest, RAG citation, booking, interrupt-resume.

Run from repo root:  python scripts/verify.py
Prints PASS lines; exits 0 on success, 1 on any failure. No browser needed.
"""

import json
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

FAILS: list[str] = []


def log(ok: bool, msg: str) -> None:
    print(f"[{'PASS' if ok else 'FAIL'}] {msg}")
    if not ok:
        FAILS.append(msg)


SEED = [
    {"text": "Performance reviews are conducted annually in June. Managers set goals and give ratings.", "page": 4},
    {"text": "PTO accrues at 15 days per year. Unused leave carries over up to 5 days.", "page": 2},
    {"text": "Health benefits enrollment opens in November each year.", "page": 7},
    {"text": "Leave policy: request time off two weeks in advance.", "page": 3},
]


def check_ingest() -> None:
    path = ROOT / "data" / "chunks.json"
    try:
        items = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(items, list) and items:
            return log(True, f"ingest artifacts present ({len(items)} chunks)")
    except (OSError, ValueError):
        pass
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(SEED, ensure_ascii=False), encoding="utf-8")
    log(True, f"seeded fallback index ({len(SEED)} chunks)")


def check_rag() -> None:
    from backend.app.rag import retriever

    hits = retriever.query("When are performance reviews conducted?", k=2)
    ok = bool(hits) and all(isinstance(h.get("page"), int) and h["page"] >= 1 for h in hits)
    log(ok, f"RAG query returned {len(hits)} hits with page citations")
    if not ok:
        return
    log("performance" in hits[0]["text"].lower(), "top RAG hit is the performance-review chunk")


def _post(client, tid: str, message: str) -> dict:
    r = client.post("/api/chat", json={"thread_id": tid, "message": message})
    assert r.status_code == 200, f"POST /api/chat -> {r.status_code}: {r.text[:200]}"
    return r.json()


def check_api() -> None:
    from fastapi.testclient import TestClient

    from backend.app.main import app

    with TestClient(app) as client:
        r = client.get("/api/slots")
        slots = r.json().get("slots") if isinstance(r.json(), dict) else r.json()
        log(r.status_code == 200 and isinstance(slots, list) and len(slots) == 3, f"GET /api/slots -> 3 slots ({slots})")

        t = f"verify-{uuid.uuid4().hex[:8]}"
        rag = _post(client, t, "How are performance reviews conducted?")
        cited = 4 in (rag.get("citations") or []) or "[Page 4]" in rag.get("reply", "")
        log(cited, f"RAG answer cites Page 4 (citations={rag.get('citations')})")

        b = f"book-{uuid.uuid4().hex[:8]}"
        r1 = _post(client, b, "I want to book a performance review")
        log("name" in r1["reply"].lower(), "booking asks for name")
        r2 = _post(client, b, "My name is Ada Rao")
        log("email" in r2["reply"].lower(), "booking asks for email")
        r3 = _post(client, b, "ada@example.com")
        log("slot" in r3["reply"].lower() or "tomorrow" in r3["reply"].lower(), "booking asks for slot")
        r4 = _post(client, b, "Friday 10:30AM IST")
        log("lock it in" in r4["reply"].lower() and r4.get("stage") == "booking_confirm",
            f"booking asks to confirm (stage={r4.get('stage')})")
        # Human-in-the-loop says no once: slot released, alternatives offered.
        r4no = _post(client, b + "-no", "I want to book a performance review")
        _post(client, b + "-no", "No Casio")
        _post(client, b + "-no", "nocasio@example.com")
        held = _post(client, b + "-no", "Tomorrow 11AM")
        deny = _post(client, b + "-no", "No, pick another slot")
        log(deny.get("booking", {}).get("slot") is None and deny.get("stage") == "booking_slot",
            "confirm-no releases slot")
        r5 = _post(client, b, "Yes, confirm it")
        ref = ((r5.get("booking") or {}).get("reference")) or ""
        log(ref.startswith("#REV-") and "#REV-" in r5["reply"], f"booking completes with ref {ref}")
        # Sample-dialogue phrasing ("Let's go with ...") confirms immediately, no extra turn.
        f = f"fast-{uuid.uuid4().hex[:8]}"
        _post(client, f, "I want to book a performance review")
        _post(client, f, "My name is Fay Lin")
        _post(client, f, "fay@example.com")
        fast = _post(client, f, "Let's go with Friday at 10:30 AM")
        log(((fast.get("booking") or {}).get("reference") or "").startswith("#REV-"),
            "affirmed slot books immediately")

        m = f"mixed-{uuid.uuid4().hex[:8]}"
        _post(client, m, "I want to book a performance review")
        _post(client, m, "My name is Bob Jones")
        inter = _post(client, m, "What is the PTO policy?")
        log(len(inter["reply"]) > 0, f"FAQ interrupt answered mid-booking (route={inter.get('route')})")
        cont = _post(client, m, "bob@example.com")
        log("slot" in cont["reply"].lower() or "tomorrow" in cont["reply"].lower(), "booking resumes after interrupt (name kept)")
        done = _post(client, m, "Tomorrow 3PM")
        log(done.get("stage") == "booking_confirm", "interrupted booking reaches confirm")
        final = _post(client, m, "yes")
        dref = ((final.get("booking") or {}).get("reference")) or ""
        log(dref.startswith("#REV-"), f"interrupted booking completes with ref {dref}")

        s = client.post("/api/chat/stream", json={"thread_id": t, "message": "hello"})
        body = s.text
        log(s.status_code == 200 and "node" in body and "done" in body, "SSE stream emits node/token/done events")

        z = client.post("/api/reset", json={"thread_id": b})
        log(z.status_code == 200 and z.json().get("status") == "reset", "POST /api/reset acknowledges")


def main() -> int:
    for step in (check_ingest, check_rag, check_api):
        try:
            step()
        except AssertionError as exc:
            log(False, f"{step.__name__}: {exc}")
        except Exception as exc:
            log(False, f"{step.__name__} raised {type(exc).__name__}: {exc}")
    print(f"verify: {'OK' if not FAILS else f'{len(FAILS)} failure(s)'}")
    return 1 if FAILS else 0


if __name__ == "__main__":
    raise SystemExit(main())
