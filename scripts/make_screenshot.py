"""Render chat UI screenshot mock from real demo_transcript.json."""
import json
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
data = json.loads((ROOT / "docs" / "demo_transcript.json").read_text())
turns = [
    ("user", "Hi, I need to book a 1-on-1 Performance Review session."),
    ("agent", data["turns"][0]["reply"]),
    ("user", "Alex Chen (alex.chen@example.com). Wait — how often are performance reviews conducted?"),
    ("agent", data["turns"][1]["reply"][:420] + "…"),
    ("user", "Friday at 10:30 AM"),
    ("agent", data["turns"][2]["reply"]),
]
fig, ax = plt.subplots(figsize=(8.5, 9))
ax.set_xlim(0, 10); ax.set_ylim(0, len(turns) * 1.6 + 1.5); ax.axis("off")
ax.text(5, len(turns)*1.6+1.0, "Agentic HR Assistant — Live Demo  •  thread " + data["thread_id"] + "  •  Router → mixed → booking", ha="center", fontsize=10, fontweight="bold")
ax.text(5, len(turns)*1.6+0.55, "Badge shows active node per turn  •  citations [Page N]  •  slot buttons  •  #REV reference", ha="center", fontsize=8.5, style="italic")
y = len(turns)*1.6 - 0.2
for role, txt in reversed(turns):
    is_user = role == "user"
    x, w, fc, ec = (5.2, 4.5, "#1f4e79", "#1f4e79") if is_user else (0.3, 7.2, "#f1f5f9", "#94a3b8")
    ax.text(x + (w if is_user else 0), y+1.05, "YOU" if is_user else "AGENT", fontsize=7.5, fontweight="bold", color="#1f4e79", ha="right" if is_user else "left")
    ax.text(x, y, "", fontsize=1)
    import textwrap
    wrapped = "\n".join(textwrap.wrap(txt, 62))
    lines = wrapped.count("\n") + 1
    h = max(0.55, lines * 0.22)
    import matplotlib.patches as mpatches
    ax.add_patch(mpatches.FancyBboxPatch((x, y-h), w, h+0.25, boxstyle="round,pad=0.08", fc=fc if not is_user else "#1f4e79", ec=ec, lw=1.1))
    ax.text(x+0.15, y-h+0.12, wrapped, va="top", ha="left", fontsize=7.2, color="white" if is_user else "black", linespacing=1.35)
    y -= (h + 0.55)
fig.tight_layout(); fig.savefig(ROOT / "docs" / "screenshot_chat.png", dpi=150); print("saved screenshot_chat.png")
