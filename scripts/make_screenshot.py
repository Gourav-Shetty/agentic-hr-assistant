"""Render chat demo screenshot from docs/demo_transcript.json (chronological, no overflow)."""
import json
import textwrap
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

ROOT = Path(__file__).resolve().parents[1]
data = json.loads((ROOT / "docs" / "demo_transcript.json").read_text(encoding="utf-8"))
turns_api = data["turns"]

# Chronological conversation: oldest first, top to bottom.
convo = [
    ("user", "Hi, I need to book a 1-on-1 Performance Review session."),
    ("agent", turns_api[0]["reply"]),
    ("user", "Alex Chen (alex.chen@example.com). Wait \u2014 how often are performance reviews conducted?"),
    ("agent", turns_api[1]["reply"]),
    ("user", "Friday at 10:30 AM"),
    ("agent", turns_api[2]["reply"]),
]

WRAP_USER, WRAP_AGENT = 52, 66
LINE_H = 0.19
PAD = 0.32


def wrapped_lines(txt, width):
    lines = []
    for para in str(txt).split("\n"):
        lines.extend(textwrap.wrap(para, width) or [""])
    return lines


items = []
for role, txt in convo:
    w = WRAP_USER if role == "user" else WRAP_AGENT
    lines = wrapped_lines(txt, w)
    # Trim very long RAG answers so the image stays readable.
    if role == "agent" and len(lines) > 9:
        lines = lines[:8] + ["\u2026"]
    items.append((role, lines))

heights = [PAD + len(lines) * LINE_H for _, lines in items]
gap = 0.34
title_h = 1.15
total_h = title_h + sum(heights) + gap * len(items) + 0.3

fig, ax = plt.subplots(figsize=(9.2, total_h))
ax.set_xlim(0, 10)
ax.set_ylim(0, total_h)
ax.axis("off")

ax.text(5, total_h - 0.45,
        f"Agentic HR Assistant \u2014 Live Demo  \u2022  {data['thread_id']}  \u2022  Router \u2192 mixed \u2192 booking",
        ha="center", fontsize=10.5, fontweight="bold")
ax.text(5, total_h - 0.82,
        "Badge shows active node per turn  \u2022  citations [Page N]  \u2022  slot buttons  \u2022  #REV reference",
        ha="center", fontsize=8.5, style="italic")

y = total_h - title_h
for (role, lines), h in zip(items, heights):
    y -= h
    is_user = role == "user"
    if is_user:
        x, w = 4.6, 5.1
        fc, ec, tc = "#1f4e79", "#1f4e79", "white"
        ax.text(x + w, y + h + 0.06, "YOU", ha="right", fontsize=7.5, fontweight="bold", color="#1f4e79")
    else:
        x, w = 0.3, 7.6
        fc, ec, tc = "#eef3f8", "#8fa3b8", "black"
        ax.text(x, y + h + 0.06, "AGENT", ha="left", fontsize=7.5, fontweight="bold", color="#1f4e79")
    ax.add_patch(mpatches.FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.02",
                                         fc=fc, ec=ec, lw=1.1))
    ax.text(x + 0.18, y + h - 0.16, "\n".join(lines), va="top", ha="left",
            fontsize=7.4, color=tc, linespacing=1.4, wrap=False)
    y -= gap

fig.tight_layout()
fig.savefig(ROOT / "docs" / "screenshot_chat.png", dpi=150)
print("saved docs/screenshot_chat.png")
