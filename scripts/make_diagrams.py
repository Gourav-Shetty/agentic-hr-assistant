"""Generate architecture + state diagrams for README (matplotlib, no extra deps)."""
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

DOCS = Path(__file__).resolve().parents[1] / "docs"
DOCS.mkdir(exist_ok=True)

def save_arch():
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.set_xlim(0, 10); ax.set_ylim(0, 6); ax.axis("off")
    ax.set_title("Agentic HR Assistant — System Architecture", fontsize=13, fontweight="bold", pad=14)
    boxes = [
        (3.2, 4.6, 3.6, 0.7, "React (Vite) — Chat UI\nthread_id • node badge • slot buttons", "#e8f1fb", "#1f4e79"),
        (3.2, 3.6, 3.6, 0.7, "FastAPI — POST /api/chat • SSE /stream\nGET /slots • POST /reset", "#e2f0e2", "#1e6b1e"),
        (3.2, 2.6, 3.6, 0.7, "LangGraph Router\nfaq | booking | mixed | greeting", "#fff2cc", "#7f6000"),
        (0.4, 1.2, 4.2, 0.9, "FAQ RAG Node\nChroma → TF-IDF → [Page N] citations", "#f2e6f5", "#5b2d8e"),
        (5.4, 1.2, 4.2, 0.9, "Booking Tool Node\nname • email • slot → #REV-XXXX", "#fde8d8", "#8a4b00"),
        (3.2, 0.15, 3.6, 0.7, "SqliteSaver — data/checkpoints.db\npersist by thread_id", "#e6e6e6", "#333333"),
    ]
    for x, y, w, h, txt, fc, ec in boxes:
        ax.add_patch(mpatches.FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.04", fc=fc, ec=ec, lw=1.4))
        ax.text(x + w/2, y + h/2, txt, ha="center", va="center", fontsize=8.5)
    for (x1, y1, x2, y2) in [(5, 4.6, 5, 4.3), (5, 3.6, 5, 3.3), (3.4, 2.6, 2.5, 2.1), (6.6, 2.6, 7.5, 2.1), (2.5, 1.2, 4.6, 0.85), (7.5, 1.2, 5.4, 0.85)]:
        ax.annotate("", xy=(x2, y2), xytext=(x1, y1), arrowprops=dict(arrowstyle="->", color="#333333", lw=1.2))
    fig.tight_layout(); fig.savefig(DOCS / "architecture.png", dpi=150); plt.close(fig)

def save_state():
    fig, ax = plt.subplots(figsize=(10, 4.2))
    ax.set_xlim(0, 10); ax.set_ylim(0, 3.4); ax.axis("off")
    ax.set_title("Booking State Machine — Context Interleaving", fontsize=13, fontweight="bold", pad=12)
    states = [("idle", 0.5), ("booking_name", 2.4), ("booking_email", 4.3), ("booking_slot", 6.2), ("done\n#REV-XXXX", 8.3)]
    for name, x in states:
        ax.add_patch(mpatches.FancyBboxPatch((x-0.75, 1.25), 1.5, 0.9, boxstyle="round,pad=0.05", fc="#e8f1fb" if name!="done\n#REV-XXXX" else "#d9ead3", ec="#1f4e79", lw=1.4))
        ax.text(x, 1.7, name, ha="center", va="center", fontsize=8.5, fontweight="bold")
    for a, b in [(1.25, 1.65), (3.15, 3.55), (5.05, 5.45), (6.95, 7.55)]:
        ax.annotate("", xy=(b, 1.7), xytext=(a, 1.7), arrowprops=dict(arrowstyle="->", lw=1.4))
    ax.text(5, 2.7, "FAQ interrupt (mixed) → RAG answers with [Page N] → auto-resumes, fields preserved", ha="center", fontsize=8.5, style="italic",
            bbox=dict(fc="#fff2cc", ec="#7f6000", boxstyle="round,pad=0.3"))
    ax.annotate("", xy=(4.3, 2.35), xytext=(5.6, 2.35), arrowprops=dict(arrowstyle="<->", color="#7f6000", lw=1.2, linestyle="dashed"))
    fig.tight_layout(); fig.savefig(DOCS / "state_diagram.png", dpi=150); plt.close(fig)

save_arch(); save_state()
print("diagrams saved")
