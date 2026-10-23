"""Redraw figure 2 from the saved common-start measurements; no solver calls."""

import csv
from pathlib import Path
from statistics import median

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.lines import Line2D

ROOT = Path(__file__).resolve().parents[3]
font_manager.fontManager.addfont("/usr/share/fonts/opentype/ipafont-gothic/ipag.ttf")
plt.rcParams.update({"font.family": "IPAGothic", "font.size": 10,
                     "figure.facecolor": "#fcfcfb", "axes.facecolor": "#fcfcfb"})
with (ROOT / "jssa/difficulty/common-start/summary.csv").open() as f:
    rows = {r["case_id"]: r for r in csv.DictReader(f)}

# Same order and grouping as the original figure and supplement S2.5(a).
upper = [
    ("HMMT-2011-FEB-ALGGEO-08", "HMMT11 AG8"),
    ("AIME-2014-II-14", "AIME14 II-14"),
    ("HMMT-2025-FEB-GEO-06", "HMMT25 G6"),
    ("JMO-2013-PRE-03", "JMO13 予3"),
    ("AIME-2010-II-09", "AIME10 II-9"),
    ("AIME-2021-I-11", "AIME21 I-11"),
]
lower = [
    ("HMMT-2024-FEB-GEO-07", "HMMT24 G7"),
    ("AIME-2025-II-05", "AIME25 II-5"),
    ("AIME-2011-I-14", "AIME11 I-14"),
    ("AIME-2010-II-15", "AIME10 II-15"),
    ("HMMT-2021-FEB-GEO-03", "HMMT21 G3"),
    ("JMO-2014-PRE-09", "JMO14 予9 †"),
    ("AIME-2015-II-11", "AIME15 II-11"),
    ("AIME-2024-II-05", "AIME24 II-5"),
]
assert set(rows) == {cid for cid, _ in upper + lower}
assert all(int(r["n_x"]) == 60 for r in rows.values())
positions = list(range(6)) + [6.8 + i for i in range(8)]
gray, green, orange = "#8a8985", "#1baf7a", "#eb6834"
fig = plt.figure(figsize=(8, 6.5))
ax = fig.add_axes([0.19, 0.20, 0.785, 0.71])
for y, (cid, _) in zip(positions, upper + lower, strict=True):
    p = {k: float(rows[cid][k]) for k in ("pE", "pY", "pZ")}
    ax.plot([min(p.values()), max(p.values())], [y, y], color="#d9d8d4", lw=2.4,
            zorder=1)
    ax.scatter(p["pE"], y, s=110, facecolors="none", edgecolors=gray, lw=2.2, zorder=3)
    ax.scatter(p["pZ"], y, s=46, color=green, edgecolors="none", zorder=4)
    ax.scatter(p["pY"], y, s=54, color=orange, marker="D", edgecolors="none", zorder=5)
ax.set_yticks(positions, [label for _, label in upper + lower])
ax.set_xlim(-0.03, 1.03)
ax.set_ylim(14.5, -0.7)
ax.set_xticks([i / 5 for i in range(6)])
ax.grid(axis="x", color="#e9e8e4", lw=0.8)
ax.set_axisbelow(True)
ax.axhline(5.9, color="#bcbab5", lw=0.8, ls=(0, (3, 3)))
ax.text(1.02, 5.43, "上：書き換えた点が元の等式に現れない", ha="right", va="center",
        fontsize=9, color="#52514e")
ax.text(1.02, 6.32, "下：現れる（一部を含む）", ha="right", va="center",
        fontsize=9, color="#52514e")
ax.set_xlabel("当たる確率 p（同じ出発点60個）", labelpad=6)
for side in ("top", "right"):
    ax.spines[side].set_visible(False)
for side in ("left", "bottom"):
    ax.spines[side].set_color("#52514e")
ax.tick_params(colors="#52514e", labelsize=10)
handles = [
    Line2D([], [], marker="o", ls="none", ms=9, mfc="none", mec=gray, mew=2.2,
           label="元の系（作図で計算）"),
    Line2D([], [], marker="o", ls="none", ms=6, color=green,
           label="ずれの系（変数の数は自由点と同じ）"),
    Line2D([], [], marker="D", ls="none", ms=6, color=orange, label="自由点の系"),
]
fig.legend(handles=handles, loc="upper center", bbox_to_anchor=(0.57, 0.965), ncol=3,
           frameon=False, fontsize=8.4, columnspacing=1.2, handletextpad=0.5)
kept = [r for cid, r in rows.items() if cid != "JMO-2014-PRE-09"]
med = {k: median(float(r[k]) for r in kept) for k in ("pE", "pY", "pZ")}
fig.text(0.03, 0.061,
         "† JMO 2014予選9：入力条件の不足で、求める値が連続的に動く。",
         fontsize=8.5, color="#52514e")
fig.text(0.03, 0.031,
         f"  除外した13問の中央値：元の系 {med['pE']:.2f}、"
         f"ずれの系 {med['pZ']:.2f}、自由点の系 {med['pY']:.2f}。",
         fontsize=8.5, color="#52514e")
fig.savefig(Path(__file__).with_name("fig1_common_start_v7.png"), dpi=200)
plt.close(fig)
