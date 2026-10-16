"""Drive the real UI through the sample dialogue and capture docs/screenshot_ui.png."""
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
URL = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:5173"

TURNS = [
    ("Hi, I need to book a 1-on-1 Performance Review session.", "What is your full name?"),
    ("Alex Chen (alex.chen@example.com). Wait, before that, how often are performance reviews conducted?",
     "Returning to your booking"),
    ("Friday at 10:30 AM", "Lock it in"),
    ("Yes, confirm", "Your reference is"),
]


def main() -> int:
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 880, "height": 1600})
        page.goto(URL, wait_until="networkidle")
        page.get_by_role("button", name="New").click()
        page.wait_for_timeout(800)
        box = page.get_by_label("Message the HR assistant")
        for msg, expect in TURNS:
            box.fill(msg)
            page.get_by_label("Send message").click()
            page.wait_for_function(
                f"document.body.innerText.includes({expect!r})",
                timeout=120000,
            )
            page.wait_for_timeout(1200)
        page.screenshot(path=str(ROOT / "docs" / "screenshot_ui.png"))
        browser.close()
    print("saved docs/screenshot_ui.png")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
