"""Tables for the basin count: python summarize_basins.py ANALYSIS_DIR RECHECK_DIR"""
import csv, json, sys
from pathlib import Path
import numpy as np
from scipy.stats import spearmanr

A, RC = Path(sys.argv[1]), Path(sys.argv[2])
f = lambda r, k: float(r[k]) if r.get(k, "") != "" else float("nan")
med = lambda v: float(np.median(v)) if len(v) else float("nan")


def rechecks(ids):
    s = z = n = 0
    for i in ids:
        p = RC / f"{i}.json"
        if p.exists():
            d = json.loads(p.read_text()); n += d["n"]; s += d["settled"]; z += d["reached_zero"]
    return n, s, z


def table(rows, keyf, labels, title):
    print(f"\n{title}\n")
    print("| 群 | 問題数 | p中央値 | 外れ終点のうち箱外 | 外れ終点のうち打切り(stuck) | 残差の谷(2点以上) 中央値 | 位置の谷(誤・2点以上) 中央値 | 再開で残差0に達した割合 | 再開で動かず(真の極小)の割合 |")
    print("|---|---|---|---|---|---|---|---|---|")
    for lab in labels:
        g = [r for r in rows if keyf(r) == lab]
        if not g: continue
        fail = [1 - f(r, "p") for r in g]
        lb = np.nansum([f(r, "frac_left_box") for r in g]); st = np.nansum([f(r, "frac_stuck") for r in g])
        tot = lb + st + np.nansum([f(r, "frac_wrong_answer") + f(r, "frac_wrong_branch") + f(r, "frac_error") for r in g])
        n, s, z = rechecks([r["id"] for r in g])
        print(f"| {lab} | {len(g)} | {med([f(r,'p') for r in g]):.2f} | {lb/tot:.2f} | {st/tot:.2f} | {med([f(r,'n_levels_ge2') for r in g]):.0f} | {med([f(r,'n_wrong_basins_ge2') for r in g]):.0f} | {(z/n if n else float('nan')):.2f} | {(s/n if n else float('nan')):.2f} |")


r323 = [r for r in csv.DictReader(open(A / "basins-323.csv")) if r["status"] == "ok"]
r60 = list(csv.DictReader(open(A / "basins-extra60.csv")))
bins = lambda r: "1" if f(r, "n_vars") == 1 else "2" if f(r, "n_vars") == 2 else "3-4" if f(r, "n_vars") <= 4 else "5-6" if f(r, "n_vars") <= 6 else "7+"
table(r323, bins, ["1", "2", "3-4", "5-6", "7+"], "## 323問(探索変数あり292問)：探索変数の数で群分け")
table(r60, lambda r: r["k"], ["0", "1", "2", "3"], "## extra-variables 60入力：追加した自由点の数 k")
print("\n## 相関(Spearman)")
for nm, rows in (("323", r323), ("extra60", r60)):
    for a, b in (("n_vars", "p"), ("n_vars", "n_levels_ge2"), ("p", "n_levels_ge2"), ("p", "top_wrong_share"), ("p", "n_wrong_basins_ge2"), ("n_vars", "n_wrong_basins_ge2")):
        x = [f(r, a) for r in rows]; y = [f(r, b) for r in rows]
        print(f"- {nm}: {a} vs {b}: ρ={spearmanr(x,y)[0]:.2f}")
n, s, z = rechecks([r["id"] for r in r323 + r60])
print(f"\n再検査: stuck終点 {n} 個(1問最大40)、再開して動かなかった(真の極小)={s}({s/max(n,1):.0%})、再開で残差0に達した={z}({z/max(n,1):.0%})")
