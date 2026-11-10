"""Figure for E2: monthly flag rate of four calibration schemes at the hot-desert site (alpha = 0.05).

Usage: python3 e2_figure.py <e2_monthly_focus.csv> <buildings> <out.png>
"""
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
from matplotlib import font_manager as fm

for f in fm.findSystemFonts():
    if "Lora" in f and "Italic" not in f:
        fm.fontManager.addfont(f)
plt.rcParams.update({"font.family": "Lora", "font.size": 9})
INK, MUTED, GRID = "#1f1f1f", "#6b6b6b", "#e6e6e6"

m = pd.read_csv(sys.argv[1], index_col="month") * 100
n_b = sys.argv[2]
series = [
    ("split", "Split (calibrated Jan–Feb)", "#2a78d6", "o"),
    ("mondrian", "Mondrian (same season, prior year)", "#eb6834", "s"),
    ("rolling28", "Rolling 28-day", "#1baf7a", "^"),
    ("aci", "Adaptive (ACI)", "#eda100", "D"),
]
months = ["Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

fig, ax = plt.subplots(figsize=(6.6, 3.2), dpi=300)
ax.axhline(5, color=INK, linewidth=1, linestyle=(0, (4, 3)), zorder=1)
ax.text(9.15, 5, r"target $\alpha$ = 5%", va="center", ha="left", color=INK, fontsize=8)
for key, label, color, mk in series:
    ax.plot(range(10), m[key].values, color=color, linewidth=2, marker=mk, markersize=4.5,
            markeredgecolor="white", markeredgewidth=1, label=label, zorder=3)
ax.set_xticks(range(10))
ax.set_xticklabels(months)
ax.set_xlim(-0.3, 10.6)
ax.set_ylim(0, 25)
ax.set_yticks([0, 5, 10, 15, 20, 25])
ax.set_yticklabels([f"{v}%" for v in [0, 5, 10, 15, 20, 25]])
ax.set_ylabel("Share of building-days flagged", color=MUTED)
ax.set_xlabel(f"2017, hot-desert site (Fox), {n_b} buildings passing ASHRAE 14", color=MUTED)
ax.grid(axis="y", color=GRID, linewidth=0.8, zorder=0)
for s in ["top", "right", "left"]:
    ax.spines[s].set_visible(False)
ax.spines["bottom"].set_color(GRID)
ax.tick_params(colors=MUTED, length=0)
leg = ax.legend(loc="upper left", ncol=2, frameon=False, fontsize=8, handlelength=2.2,
                bbox_to_anchor=(0, 1.2), labelcolor=INK)
plt.tight_layout()
plt.savefig(sys.argv[3], facecolor="white", bbox_inches="tight")
print("saved", sys.argv[3])
