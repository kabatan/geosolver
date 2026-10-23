"""Read-only endpoint analysis; writes only beside this script. No search calls."""
from __future__ import annotations

import os
os.environ["OPENBLAS_NUM_THREADS"] = "1"
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"
import sys
sys.dont_write_bytecode = True
import csv
import hashlib
import json
import math
import time
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime, timezone
from itertools import combinations
from pathlib import Path

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[2]
sys.path[:0] = [str(ROOT / "src"), str(OUT.parent)]
import numpy as np
from ghost_scan import point_names
from probe_basins import answer_float, construction_coordinates
from geosolver import GeometryProblem
from geosolver.engine.standard.problem.load_problem_bundle import load_problem_bundle

RAW = OUT.parent / "minima/raw-323"
BASINS = OUT.parent / "minima/basins-323.csv"
PAIRS = OUT.parent / "ghost-exact/per-pair.csv"
PROBLEMS = OUT.parent / "ghost-exact/per-problem.csv"
CASES = ROOT / "benchmarks/cases.jsonl"
TOL = 1e-4
FAILURES = {"left_box", "error", "stuck", "wrong_answer", "wrong_branch"}
CATEGORIES = ["success", "collision_failure", "other_failure", "failure_geometry_missing", "class_unknown"]
START_FIELDS = ["id", "k", "n_vars", "group", "cls", "category", "coinc_any", "coinc_G",
                "target_state", "any_state", "n_finite_points", "n_coordinate_points", "diameter",
                "n_target_pairs", "n_target_measured", "matching_pairs", "geometry_note"]


def read_csv(path):
    with path.open() as f:
        return list(csv.DictReader(f))


def write_csv(path, rows, fields=None):
    with path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields or list(rows[0]))
        w.writeheader()
        w.writerows(rows)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def stratum(n):
    return str(n) if n < 5 else "5+"


def pair_metric(pairs, distances, diameter):
    values = [(p, distances[p] / diameter if diameter > 0 else 0.0)
              for p in pairs if p in distances and diameter is not None]
    minimum = min((v for _, v in values), default=None)
    matches = [p for p, v in values if v < TOL]
    state = "positive" if matches else "negative" if pairs and len(values) == len(pairs) else "missing"
    return minimum, state, matches, len(values)


def classify(cls, state):
    if cls == "hit":
        return "success"
    if cls not in FAILURES:
        return "class_unknown"
    return {"positive": "collision_failure", "negative": "other_failure", "missing": "failure_geometry_missing"}[state]


def selftest():
    # G's matched pair need not be the globally closest pair.
    ds = {("A", "B"): 1e-8, ("B", "C"): 9e-5}
    assert pair_metric([("B", "C")], ds, 1)[1] == "positive"
    assert pair_metric([("B", "C")], {("B", "C"): TOL}, 1)[1] == "negative"
    assert pair_metric([("A", "B"), ("B", "C")], {("A", "B"): 1.0}, 1)[1] == "missing"
    assert pair_metric([("A", "B"), ("B", "C")], {("A", "B"): 0.0}, 1)[1] == "positive"
    assert pair_metric([], {}, 1)[1] == "missing"
    assert pair_metric([("A", "B")], {("A", "B"): 0.0}, 0)[0] == 0
    assert classify("error", "missing") == "failure_geometry_missing"
    assert classify("hit", "missing") == "success"
    assert classify("", "positive") == "class_unknown"


def analyze_problem(task):
    cid, nvars, group, gpairs, dsl = task
    began = time.monotonic()
    d = json.loads((RAW / f"{cid}.json").read_text())
    assert int(d["n_vars"]) == nvars
    records = d.get("records") or []
    assert len({r["k"] for r in records}) == len(records), cid
    requested = int(d.get("starts_requested", 200))
    assert len(records) <= requested
    p = dict(id=cid, n_vars=nvars, stratum=stratum(nvars), group=group,
             status=d.get("status", ""), starts_requested=requested, n_records=len(records),
             n_unrecorded=requested-len(records) if nvars else 0,
             fewer_than_requested=int(nvars > 0 and len(records) < requested),
             n_found_pairs=len(gpairs), **{c: 0 for c in CATEGORIES},
             coinc_any_missing=0, coinc_G_missing=0, target_incomplete=0,
             partial_figures=0, no_x=0, n_points=0, n_excluded_pairs=0,
             coordinate_build_errors="", seconds=0.0)
    if nvars == 0:
        assert not records, "Unexpected zero-variable starts"
        p["seconds"] = time.monotonic()-began
        return p, []
    coords, errors = {}, {}
    for name in point_names(dsl):
        try:
            cc = construction_coordinates(dsl, [name])
            coords[name] = (cc[f"x_{name}"], cc[f"y_{name}"])
        except Exception as exc:
            errors[name] = f"{type(exc).__name__}: {exc}"
    p["coordinate_build_errors"] = json.dumps(errors, ensure_ascii=False, sort_keys=True)
    p["n_points"] = len(coords)
    base_names = list(load_problem_bundle(GeometryProblem.model_validate(dsl).engine_document()).var_names)
    assert len(base_names) == nvars, cid

    def figure(r):
        x = r.get("x")
        if not isinstance(x, list) or len(x) != nvars or not all(isinstance(v, (float, int)) and math.isfinite(v) for v in x):
            return {}, "x_missing_or_invalid"
        vals, fig = dict(zip(base_names, x)), {}
        for name, axes in coords.items():
            xy = [answer_float(ev, [vals[n] for n in names]) for names, ev in axes]
            if all(v is not None and math.isfinite(v) for v in xy):
                fig[name] = np.array(xy)
        return fig, "" if len(fig) == len(coords) else "some_coordinates_nonfinite"

    figures = [figure(r) for r in records]
    hits = [f for r, (f, _) in zip(records, figures) if r.get("cls") == "hit" and len(f) >= 2]
    all_pairs = list(combinations(sorted(coords), 2))
    excluded = {pair for pair in all_pairs if hits and all(
        pair[0] in f and pair[1] in f and np.linalg.norm(f[pair[0]]-f[pair[1]])
        < 1e-6 * max(1.0, max(np.linalg.norm(v) for v in f.values())) for f in hits)}
    assert not (set(gpairs) & excluded), f"{cid}: G pairs excluded by hit rule"
    eligible = [pair for pair in all_pairs if pair not in excluded]
    target = gpairs if group == "G_yes" else eligible
    p["n_excluded_pairs"] = len(excluded)
    output = []
    for r, (fig, note) in zip(records, figures):
        distances = {pair: float(np.linalg.norm(fig[pair[0]]-fig[pair[1]]))
                     for pair in combinations(sorted(fig), 2)}
        diameter = max(distances.values()) if distances else None
        if diameter is not None and not math.isfinite(diameter):
            diameter, note = None, "nonfinite_diameter"
        distances = {pair: v for pair, v in distances.items() if math.isfinite(v)}
        any_min, any_state, _, _ = pair_metric(eligible, distances, diameter)
        gmin, _, _, _ = pair_metric(gpairs, distances, diameter)
        target_min, state, matches, nmeasured = pair_metric(target, distances, diameter)
        cls = r.get("cls", "")
        category = classify(cls, state)
        p[category] += 1
        p["coinc_any_missing"] += int(any_min is None)
        p["coinc_G_missing"] += int(group == "G_yes" and gmin is None)
        p["target_incomplete"] += int(nmeasured < len(target) or not target)
        p["partial_figures"] += int(len(fig) < len(coords))
        p["no_x"] += int(note == "x_missing_or_invalid")
        output.append(dict(id=cid, k=r["k"], n_vars=nvars, group=group, cls=cls,
                           category=category, coinc_any=any_min, coinc_G=gmin,
                           target_state=state, any_state=any_state, n_finite_points=len(fig),
                           n_coordinate_points=len(coords), diameter=diameter,
                           n_target_pairs=len(target), n_target_measured=nmeasured,
                           matching_pairs=json.dumps(matches, separators=(",", ":")), geometry_note=note))
    assert sum(p[c] for c in CATEGORIES) == len(records)
    p["seconds"] = round(time.monotonic()-began, 3)
    return p, output


def summarize(problems):
    rows = []
    for group in ("G_yes", "G_no", "G_unknown", "out_of_scope"):
        for layer in (["0", "all"] if group == "out_of_scope" else ["1", "2", "3", "4", "5+", "all"]):
            ps = [p for p in problems if p["group"] == group and (layer == "all" or p["stratum"] == layer)]
            if not ps and group in ("G_unknown", "out_of_scope"):
                continue
            row = dict(group=group, stratum=layer, n_problems=len(ps))
            for field in ["n_records", "n_unrecorded", "fewer_than_requested", *CATEGORIES,
                          "coinc_any_missing", "coinc_G_missing", "target_incomplete", "partial_figures", "no_x"]:
                row[field] = sum(p[field] for p in ps)
            row["known_failures"] = sum(row[c] for c in CATEGORIES[1:4])
            row["measurable_failures"] = row["collision_failure"] + row["other_failure"]
            row["noG_other_classified"] = row["success"] + row["other_failure"] if group == "G_no" else ""
            row["collision_share_all_failures"] = row["collision_failure"] / row["known_failures"] if row["known_failures"] else ""
            row["collision_share_measurable_failures"] = row["collision_failure"] / row["measurable_failures"] if row["measurable_failures"] else ""
            rows.append(row)
    return rows


def main():
    selftest()
    began = time.monotonic()
    started = datetime.now(timezone.utc).isoformat()
    fixed = (OUT / "README.md").read_text().split("## 実行結果")[0]
    assert "未集計" in (OUT / "README.md").read_text(), "Do not overwrite completed report"
    inputs = [BASINS, PAIRS, PROBLEMS, CASES, *sorted(RAW.glob("*.json"))]
    hashes = {str(p.relative_to(ROOT)): digest(p) for p in inputs}
    rows = read_csv(BASINS)
    assert len({r["id"] for r in rows}) == len(rows)
    assert {r["id"] for r in rows} == {p.stem for p in RAW.glob("*.json")}
    pair_rows = read_csv(PAIRS)
    done = {r["id"]: r for r in read_csv(PROBLEMS) if r["status"] == "ok"}
    found = defaultdict(list)
    for r in pair_rows:
        if int(r["found"]) == 1:
            found[r["id"]].append(tuple(sorted((r["P"], r["Q"]))))
    for cid, r in done.items():
        assert int(r["n_pairs_found"]) == len(found[cid])
        assert int(r["n_pairs"]) == sum(p["id"] == cid for p in pair_rows)
    cases = {c["id"]: c for c in map(json.loads, CASES.read_text().splitlines())}
    tasks = []
    for r in rows:
        cid, n = r["id"], int(r["n_vars"])
        group = "out_of_scope" if n == 0 else "G_yes" if found[cid] else "G_no" if cid in done else "G_unknown"
        tasks.append((cid, n, group, found[cid], cases[cid]["dsl"]))
    problems = []
    with (OUT / "per-start.csv").open("w", newline="") as f, ProcessPoolExecutor(max_workers=2) as pool:
        writer = csv.DictWriter(f, fieldnames=START_FIELDS)
        writer.writeheader()
        for i, (p, starts) in enumerate(pool.map(analyze_problem, tasks), 1):
            problems.append(p)
            writer.writerows(starts)
            f.flush()
            print(f"{i}/{len(tasks)} {p['id']} records={p['n_records']} seconds={p['seconds']}", flush=True)
    assert hashes == {str(p.relative_to(ROOT)): digest(p) for p in inputs}, "Inputs changed during analysis"
    assert fixed == (OUT / "README.md").read_text().split("## 実行結果")[0], "Fixed definitions changed"
    write_csv(OUT / "per-problem.csv", problems)
    summary = summarize(problems)
    write_csv(OUT / "summary.csv", summary)
    elapsed = time.monotonic()-began
    manifest = dict(started_utc=started, finished_utc=datetime.now(timezone.utc).isoformat(),
                    elapsed_seconds=elapsed, workers=2, python=sys.version, executable=sys.executable,
                    numpy=np.__version__, threshold=TOL, fixed_definitions_sha256=hashlib.sha256(fixed.encode()).hexdigest(),
                    input_sha256=hashes, script_sha256=digest(Path(__file__)))
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2)+"\n")
    report = ["\n### 層別内訳\n", "各セルは件数（保存済み全記録 N に対する %）。重なる失敗は G ありでは G点対、G なしでは任意点対。\n",
              "|群|変数数|問題数|N|成功|重なる失敗|その他の失敗|失敗・幾何判定不能|cls不明|未実施・未記録|",
              "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
    def cell(n, total):
        return f"{n:,} ({100*n/total:.2f}%)" if total else f"{n:,} (—)"
    for row in summary:
        report.append("|"+"|".join([row["group"], row["stratum"], str(row["n_problems"]), f"{row['n_records']:,}",
                     *[cell(row[c], row["n_records"]) for c in CATEGORIES], f"{row['n_unrecorded']:,}"])+"|")
    report += ["\n### 失敗内の割合と欠測\n",
               "coinc_any/G 欠測数は成功も含む。target不完全は一部の点対が測れない記録（陽性を確認できる記録も含む）。\n",
               "|群|変数数|既知失敗|幾何判定可能な失敗|重なる/全失敗|重なる/判定可能失敗|coinc_any欠測|coinc_G欠測|target不完全|200回未満の問題|",
               "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for row in summary:
        if row["group"] not in ("G_yes", "G_no"):
            continue
        report.append("|"+"|".join([row["group"], row["stratum"], str(row["known_failures"]), str(row["measurable_failures"]),
                      cell(row["collision_failure"], row["known_failures"]), cell(row["collision_failure"], row["measurable_failures"]),
                      str(row["coinc_any_missing"]), str(row["coinc_G_missing"]), str(row["target_incomplete"]), str(row["fewer_than_requested"])])+"|")
    report += ["\n### G なしの二分表示\n", "その他は成功+その他の失敗。幾何判定不能・cls不明は二分に代入しない。分母は同じ N。\n",
               "|変数数|N|任意点対が重なる失敗|それ以外（分類可能）|判定不能|", "|---|---:|---:|---:|---:|"]
    for row in summary:
        if row["group"] == "G_no":
            report.append("|"+"|".join([row["stratum"], str(row["n_records"]), cell(row["collision_failure"], row["n_records"]),
                          cell(row["noG_other_classified"], row["n_records"]), cell(row["failure_geometry_missing"]+row["class_unknown"], row["n_records"])])+"|")
    report += [f"\n解析時間: {elapsed:.3f} 秒。開始 UTC {started}。worker=2、BLAS=1スレッド/worker。",
               "全入力ファイルの SHA-256 を実行前後で照合し、変更がないことを確認した。",
               "\n### 成果物と再実行\n",
               "- `analyze.py`: 分類、集計、定義固定チェック、合成例による境界・欠測・全G点対照合の自己検証。",
               "- `per-start.csv`: 全保存記録を1行ずつ。coinc_G/any は利用可能点対の最小値（空欄は欠測）。target_state の missing は部分欠測も含む。",
               "- `per-problem.csv`: 母集団全問題の分母、未記録数、分類、欠測数、座標構築失敗理由。",
               "- `summary.csv`: 層別・全体の件数と失敗内割合。",
               "- `manifest.json`: 入力ハッシュ、固定定義ハッシュ、実行環境、実測解析時間。",
               "- `run.log`: 進捗ログ。実行コマンドは下記。",
               "\n```bash\nPYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 /home/kabatan/work/solver/.venv/bin/python jssa/difficulty/ghost-pairs-match/analyze.py > jssa/difficulty/ghost-pairs-match/run.log 2>&1\n```",
               "再実行は意図しない上書きを防ぐため、README の結果節に「未集計」がある場合だけ許可する。定義節は変更しない。",
               "\n### 限界\n",
               "- Gなしは20出発点の数値探索で found=1 がなかったという意味。厳密な不存在判定ではない。Gは等式系だけであり元の不等式・答えの正しさは保証しない。",
               "- 終点だけの照合なので、そこへ近づいた軌道や引力域、因果関係は分からない。重なる失敗が G の発見解そのものと同じ座標・残差・枝にあることも意味しない。",
               "- diameter による相対尺度なので、図の膨張により絶対距離が小さくなくても重なりと判定されうる。ghost_scan と同じ有限点集合で diameter を測るため、一部座標の欠測は尺度にも影響する。",
               "- hitで常に重なる組の除外は保存済みhitに依存する。hitなしでは除外せず、少数hitによる除外の不安定さもある。座標構築できないスカラー候補等は点集合に入らない。",
               "- ghost_scan の高成功率フィルタは適用しない。また比較可能な点対が全くない場合は元コードの便宜的な0を使わず欠測とする。対象点対の一部が欠ける陰性候補も欠測として保存する。",
               "- 時間制限で出発点数が異なるため、主表は200回未満の問題を少なく重み付けする。未記録終点の帰結は不明で、完全ケース割合も選択偏りを持ちうる。",
               "- Gあり/なしで陽性の対象点対が違い、n_vars層内の点数・式・問題構造も揃えていない。群間差は記述であり介入効果ではない。"]
    with (OUT / "README.md").open("a") as f:
        f.write("\n".join(report)+"\n")
    print(f"DONE elapsed_seconds={elapsed:.3f}", flush=True)


if __name__ == "__main__":
    main()
