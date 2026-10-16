"""Replay a pasted UI transcript turn-by-turn against current code."""
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient

from backend.app.main import app

TURNS = [
    "hey",
    "book an interview",
    "Gourav Shetty but before that what are the benefits ?",
    "go ahead",
    "go ahead book an interview",
    "i juts told you",
    "i just told you my full name",
]

with TestClient(app) as client:
    tid = "replay-" + uuid.uuid4().hex[:6]
    for msg in TURNS:
        r = client.post("/api/chat", json={"thread_id": tid, "message": msg}).json()
        print("U:", msg)
        print("A:", r["reply"][:160].replace("\n", " "))
        print("route:", r["route"], "| stage:", r.get("stage"),
              "| cit:", r.get("citations"), "| booking:", r.get("booking"))
        print("-" * 80)
