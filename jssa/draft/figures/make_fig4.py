"""Figure 4: predicted vs observed change of the local hit rate under feasible-start redraw (seed 2)."""
import csv
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
rows = list(csv.DictReader(open(ROOT / "jssa/difficulty/start-feasibility-1023/seed2-summary.csv")))
pts = [(float(r["pred_delta"]), float(r["p_feasible"]) - float(r["p_plain"]), r["id"], float(r["p0"]))
       for r in rows if r["pred_delta"] not in ("", "None")]

from matplotlib import font_manager
font_manager.fontManager.addfont("/usr/share/fonts/opentype/ipafont-gothic/ipag.ttf")
plt.rcParams["font.family"] = "IPAGothic"
fig, ax = plt.subplots(figsize=(5.2, 4.6), dpi=200)
ax.axhline(0, color="#c8c8c8", lw=0.8, zorder=0)
ax.axvline(0, color="#c8c8c8", lw=0.8, zorder=0)
ax.plot([-0.6, 1.0], [-0.6, 1.0], color="#8a8a8a", lw=1, ls="--", zorder=1)
lo = [(a, b) for a, b, _, p0 in pts if p0 < 0.3]
hi = [(a, b) for a, b, _, p0 in pts if p0 >= 0.3]
ax.scatter([a for a, b in hi], [b for a, b in hi], s=18, color="#2a6fbb", edgecolor="white", lw=0.6, label="元の確率 0.3以上", zorder=3)
ax.scatter([a for a, b in lo], [b for a, b in lo], s=18, color="#e08a2c", edgecolor="white", lw=0.6, label="元の確率 0.3未満", zorder=3)
for a, b, i, _ in pts:
    if i == "AIME-2010-II-14":
        ax.annotate("AIME 2010 II-14", (a, b), xytext=(a + 0.05, b - 0.12), fontsize=8, color="#333333",
                    arrowprops=dict(arrowstyle="-", color="#666666", lw=0.6))
    if i == "AIME-2006-II-09":  # the largest miss: p_F rested on 1 feasible start of 200
        ax.annotate("AIME 2006 II-9（予測の外れ）", (a, b), xytext=(-0.55, 0.66), fontsize=8, color="#333333",
                    arrowprops=dict(arrowstyle="-", color="#666666", lw=0.6))
ax.set_xlim(-0.6, 1.0)
ax.set_ylim(-0.6, 1.0)
ax.set_xlabel("予測した変化（seed 0 から）", fontsize=9)
ax.set_ylabel("実測の変化（seed 2）", fontsize=9)
ax.tick_params(labelsize=8)
for s in ("top", "right"):
    ax.spines[s].set_visible(False)
ax.legend(fontsize=8, frameon=False, loc="upper left")
ax.text(0.98, 0.03, "122問、破線は予測＝実測", transform=ax.transAxes, ha="right", fontsize=8, color="#555555")
fig.tight_layout()
fig.savefig(HERE / "fig4_feasible_start.png")
