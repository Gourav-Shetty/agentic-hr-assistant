"""Input guardrails: prompt-injection detection, sanitization, email validation."""

import re

INJECTION_PATTERNS = [
    r"ignore\s+(all\s+)?(previous|prior|above)\s+instructions",
    r"disregard\s+(all\s+)?(previous|prior|above)\s+instructions",
    r"system\s*prompt",
    r"reveal\s+(your\s+)?(system|secret|hidden)\s+(prompt|instructions)",
    r"jailbreak",
    r"dan\s+mode",
    r"pretend\s+(to\s+be|you\s+are)\s+(?!.*assistant)",
    r"execute\s+(this\s+)?code",
    r"<\s*script",
    r"drop\s+table",
    r"delete\s+from",
]

_COMPILED = [re.compile(p, re.IGNORECASE) for p in INJECTION_PATTERNS]

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

MAX_LEN = 2000


def is_injection(text: str) -> bool:
    """Return True if text matches any known prompt-injection pattern."""
    if not text:
        return False
    return any(rx.search(text) for rx in _COMPILED)


def sanitize(text: str) -> str:
    """Strip whitespace and truncate to a safe max length."""
    if not text:
        return ""
    cleaned = text.strip()
    if len(cleaned) > MAX_LEN:
        cleaned = cleaned[:MAX_LEN]
    return cleaned


def validate_email(email: str | None) -> bool:
    """Regex email check. Returns False for None/empty."""
    if not email:
        return False
    return bool(_EMAIL_RE.match(email.strip()))
