"""Booking tool tests: extraction + validation against the real API.

Uses backend/app/tools/booking.py (extract_name_email, match_slot,
generate_ref, SLOTS) and backend/app/graph/guardrails.py (validate_email)
directly. No skips: every test must PASS or FAIL.
"""

import re

from backend.app.graph.guardrails import validate_email
from backend.app.tools.booking import SLOTS, extract_name_email, generate_ref, match_slot


def test_extract_bare_name_returns_full_name():
    assert extract_name_email("Gourav Shetty") == {"name": "Gourav Shetty", "email": None}


def test_extract_booking_sentence_returns_no_name():
    assert extract_name_email("Hi, I need to book") == {"name": None, "email": None}


def test_extract_name_and_email_combo():
    info = extract_name_email("My name is Ada Rao, email ada@example.com")
    assert info["name"] == "Ada Rao"
    assert info["email"] == "ada@example.com"


def test_extract_email_only_leaves_name_empty():
    info = extract_name_email("just my email: bob@example.com")
    assert info["email"] == "bob@example.com"
    assert info["name"] is None


def test_extract_empty_text_returns_nones():
    assert extract_name_email("") == {"name": None, "email": None}


def test_validate_email_accepts_valid_and_rejects_invalid():
    assert validate_email("ada@example.com") is True
    assert validate_email("not-an-email") is False
    assert validate_email(None) is False
    assert validate_email("") is False


def test_match_slot_friday_morning_fuzzy():
    assert match_slot("Friday at 10:30 AM") == "Friday 10:30AM IST"


def test_match_slot_tomorrow_afternoon():
    assert match_slot("Tomorrow 3PM") == "Tomorrow 3PM"


def test_match_slot_unknown_returns_none():
    assert match_slot("sometime next month maybe") is None
    assert match_slot("") is None


def test_generate_ref_format():
    ref = generate_ref()
    assert re.fullmatch(r"#REV-[A-Z0-9]{6}", ref), ref


def test_slots_lists_three_bookable_options():
    assert SLOTS == ["Tomorrow 11AM", "Tomorrow 3PM", "Friday 10:30AM IST"]
