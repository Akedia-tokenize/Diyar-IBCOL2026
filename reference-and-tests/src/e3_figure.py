"""Figure for E3: (a) absorption of a persistent manipulation by the fast gate vs the slow gate;
(b) quarterly one-sided slow test: share of manipulated buildings flagged vs manipulation size.

Usage: python3 e3_figure.py <e3a_results.json> <e3a_quarterly.json> <out.png>
"""
import json
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib import font_manager as fm

for f in fm.findSystemFonts():
    if "Lora" in f and "Italic" not in f:
        fm.fontManager.addfont(f)
plt.rcParams.update({"font.family": "Lora", "font.size": 8.5})
INK, MUTED, GRID = "#1f1f1f", "#6b6b6b", "#e6e6e6"

daily = json.load(open(sys.argv[1]))
quart = json.load(open(sys.argv[2]))
c = daily["curves"]["shave_20"]
fast, slow = np.array(c["fast"]) * 100, np.array(c["slow"]) * 100

fig, (a, b) = plt.subplots(1, 2, figsize=(7.0, 2.9), dpi=300, gridspec_kw={"width_ratios": [1.1, 1]})


def style(ax):
    ax.grid(axis="y", color=GRID, linewidth=0.8, zorder=0)
    for s in ["top", "right", "left"]:
        ax.spines[s].set_visible(False)
    ax.spines["bottom"].set_color(GRID)
    ax.tick_params(colors=MUTED, length=0)


x = np.arange(len(fast))
a.axhline(5, color=INK, linewidth=0.9, linestyle=(0, (4, 3)), zorder=1)
a.plot(x, fast, color="#2a78d6", linewidth=1.6, zorder=3)
a.plot(x, slow, color="#eb6834", linewidth=1.6, zorder=3)
a.text(4, 50, "Fast gate (rolling 28-day)", color=INK, fontsize=8)
a.annotate("", xy=(1.2, fast[0] - 2), xytext=(4, 50), arrowprops=dict(arrowstyle="-", color="#2a78d6", lw=0.8))
a.text(38, 22, "Slow gate (vs committed baseline)", color=INK, fontsize=8, va="bottom")
a.text(89, 1.0, "clean 5%", color=INK, fontsize=7.5, ha="right")
a.set_xlim(0, 90); a.set_ylim(0, 60)
a.set_yticks([0, 10, 20, 30, 40, 50, 60]); a.set_yticklabels([f"{v}%" for v in range(0, 61, 10)])
a.set_xlabel("Days since a persistent 20% under-reporting began", color=MUTED)
a.set_ylabel("Manipulated buildings flagged that day", color=MUTED)
a.set_title("(a) The fast gate absorbs it within ~28 days", color=INK, fontsize=9, loc="left")
style(a)

rows = quart["power_single_building"]
for kind, color, mk, label in [("shave", "#1baf7a", "o", "Under-reporting"), ("relocate", "#6250d6", "s", "Meter relocation")]:
    r = [q for q in rows if q["manipulation"] == kind]
    sz = [q["size"] * 100 for q in r]
    pw = [q["power_one_sided"] * 100 for q in r]
    b.plot(sz, pw, color=color, linewidth=2, marker=mk, markersize=4.5, markeredgecolor="white",
           markeredgewidth=1, zorder=3)
    b.text(sz[-1] + 1, pw[-1] - (3 if kind == "relocate" else -1), label, color=INK, fontsize=8, va="center")
b.axhline(5, color=INK, linewidth=0.9, linestyle=(0, (4, 3)), zorder=1)
b.axhline(80, color=MUTED, linewidth=0.8, linestyle=(0, (1, 2)), zorder=1)
b.text(1, 81.5, "80% power", color=MUTED, fontsize=7.5)
b.text(22, 7, "false-flag rate (alpha)", color=INK, fontsize=7.5)
b.set_xlim(0, 58); b.set_ylim(0, 100)
b.set_xticks([0, 10, 20, 30, 40]); b.set_xticklabels(["0", "10%", "20%", "30%", "40%"])
b.set_yticks([0, 20, 40, 60, 80, 100]); b.set_yticklabels([f"{v}%" for v in range(0, 101, 20)])
b.set_xlabel("Size of manipulation", color=MUTED)
b.set_ylabel("Flagged at the quarterly test", color=MUTED)
b.set_title("(b) The slow gate catches only large ones", color=INK, fontsize=9, loc="left")
style(b)

plt.tight_layout(w_pad=2.5)
plt.savefig(sys.argv[3], facecolor="white", bbox_inches="tight")
print("saved", sys.argv[3])
