"""Regenerate docs/demo_transcript.json via the live sample dialogue (TestClient)."""
import json
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient

from backend.app.main import app

TURNS = [
    "Hi, I need to book a 1-on-1 Performance Review session.",
    "Alex Chen (alex.chen@example.com). Wait, before that, how often are performance reviews conducted?",
    "Friday at 10:30 AM",
    "Yes, confirm",
]

with TestClient(app) as client:
    tid = "demo-" + uuid.uuid4().hex[:6]
    out = []
    for msg in TURNS:
        r = client.post("/api/chat", json={"thread_id": tid, "message": msg})
        assert r.status_code == 200, r.text[:200]
        out.append(r.json())
    (ROOT / "docs" / "demo_transcript.json").write_text(
        json.dumps({"thread_id": tid, "turns": out}, indent=2), encoding="utf-8"
    )
    print("saved", tid, "| final:", out[-1]["booking"])
