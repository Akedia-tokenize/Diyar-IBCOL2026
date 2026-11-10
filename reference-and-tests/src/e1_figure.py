"""Figure for E1: 60-year single-copy custody volume under each signing design.

Usage: python3 e1_figure.py <e1_storage.csv> <out.png>
"""
import sys

import matplotlib
import matplotlib.ticker
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
from matplotlib import font_manager as fm

for f in fm.findSystemFonts():
    if "Lora" in f and "Italic" not in f:
        fm.fontManager.addfont(f)
plt.rcParams.update({"font.family": "Lora", "font.size": 9})

INK, MUTED, GRID, BAR = "#1f1f1f", "#6b6b6b", "#e6e6e6", "#8B1C31"

df = pd.read_csv(sys.argv[1])
df = df[df["basis"].str.startswith("whitepaper")]
labels = {
    "S0": "Raw readings only",
    "S1": "+ device ECDSA per reading",
    "S2": "+ SLH-DSA-128s per reading",
    "S3": "+ SLH-DSA-256s per building per day",
    "S4": "+ SLH-DSA-256s on one global daily root",
    "S5": "Device ECDSA per channel-day + global root",
}
df["key"] = df["scenario"].str[:2]
df = df.set_index("key").loc[["S0", "S1", "S2", "S3", "S4", "S5"]]
vals = df["TB_60y_single_copy"]

fig, ax = plt.subplots(figsize=(6.6, 2.9), dpi=300)
y = range(len(vals))[::-1]
ax.barh(list(y), vals.values, height=0.55, color=BAR, zorder=2)
ax.set_xscale("log")
ax.set_xlim(1, 4000)
ax.set_yticks(list(y))
ax.set_yticklabels([f"{k}  {labels[k]}" for k in vals.index], color=INK)
for yi, v in zip(y, vals.values):
    ax.text(v * 1.12, yi, f"{v:,.1f} TB", va="center", ha="left", color=INK, fontsize=8.5)
ax.set_xticks([1, 10, 100, 1000])
ax.set_xticklabels(["1", "10", "100", "1,000"])
ax.xaxis.set_minor_locator(matplotlib.ticker.NullLocator())
ax.set_xlabel("60-year custody, single copy, 10,000 buildings (TB, log scale)", color=MUTED)
ax.grid(axis="x", color=GRID, linewidth=0.8, zorder=0)
for s in ["top", "right", "left"]:
    ax.spines[s].set_visible(False)
ax.spines["bottom"].set_color(GRID)
ax.tick_params(axis="both", colors=MUTED, length=0)
plt.tight_layout()
plt.savefig(sys.argv[2], facecolor="white")
print("saved", sys.argv[2])
