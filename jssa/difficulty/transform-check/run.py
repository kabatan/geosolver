"""Fixed preregistration-3 runner; all writes stay beside this file."""
from __future__ import annotations

import os
import sys
for key in ("OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "OMP_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
    os.environ[key] = "1"
sys.dont_write_bytecode = True

import argparse
from collections import Counter
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import csv
import math
import multiprocessing
from pathlib import Path
import platform
import time
import traceback

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[2]
SOURCE = ROOT / "jssa/strategy/astra-consult-12/B"
spec = importlib.util.spec_from_file_location("astra_b_experiment", SOURCE / "experiment.py")
B = importlib.util.module_from_spec(spec)
spec.loader.exec_module(B)
np = B.np

def now():
    return datetime.now(timezone.utc).isoformat()

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def dump(path, data):
    def clean(x):
        if isinstance(x, (bool, np.bool_)):
            return bool(x)
        if isinstance(x, (float, np.floating)):
            return float(x) if math.isfinite(x) else None
        if isinstance(x, (int, np.integer)):
            return int(x)
        if isinstance(x, np.ndarray):
            return clean(x.tolist())
        if isinstance(x, dict):
            return {str(k):clean(v) for k,v in x.items()}
        if isinstance(x, (list, tuple)):
            return [clean(v) for v in x]
        return x
    path.write_text(json.dumps(clean(data), ensure_ascii=False, indent=2)+"\n")

def read(path):
    return json.loads(path.read_text())

def tracked_inputs():
    paths = [OUT / "run.py", OUT / "README.md", SOURCE / "experiment.py",
             SOURCE / "features.csv", SOURCE / "replication/AIME-2023-I-12.json",
             SOURCE / "replication/HMMT-2024-FEB-GEO-04.json",
             ROOT / "benchmarks/cases.jsonl", ROOT / "jssa/difficulty/minima/basins-323.csv",
             ROOT / "jssa/difficulty/ghost-1023/preregistration-3.md",
             ROOT / "jssa/difficulty/ghost-1023/transform-targets.csv",
             ROOT / "jssa/difficulty/probe_basins.py", Path(B.smb.__file__)]
    # Include every source module, since an unchanged backend alone is insufficient.
    paths += sorted((ROOT / "src").rglob("*.py"))
    return {str(p.relative_to(ROOT)): sha(p) for p in paths}

def calibration(b, ev, box, index):
    rng = np.random.default_rng([102312, index])
    fn, tel = B.vector_function(b, ev)
    rows, norms = [], []
    for k in range(16):
        x = box[:, 0] + rng.random(len(box)) * (box[:, 1] - box[:, 0])
        r, ok = B.valid_call(fn, tel, x)
        rn = B.norm(r) if ok else None
        rows.append(dict(k=k, start=x, valid=ok, residual_norm=rn))
        if ok:
            norms.append(rn)
    return max(1e-6, float(np.median(norms))) if norms else None, rows

def replicate(cid):
    started = time.monotonic()
    original = read(SOURCE / "replication" / f"{cid}.json")
    case = B.all_cases()[cid]
    b, ev, box = B.context(case)
    a, cal = calibration(b, ev, box, original["index"])
    assert a == original["a"], (cid, a, original["a"])
    rng = np.random.default_rng([102317, original["index"]])
    rows, mismatches = [], []
    for k, old in enumerate(original["rows"]):
        x = box[:, 0] + rng.random(len(box)) * (box[:, 1] - box[:, 0])
        assert np.array_equal(x, old["start"]), (cid, k, "start")
        row = dict(k=k, start=x)
        for mode in ("base", "sharpen"):
            rec = B.solve(b, ev, box, B.reference_values(case["answer"]), x, a, mode, 320, k)
            row[mode] = rec
            if rec["cls"] != old[mode]["cls"]:
                mismatches.append(dict(k=k, mode=mode, expected=old[mode]["cls"], actual=rec["cls"]))
        rows.append(row)
    result = dict(id=cid, a=a, calibration=cal, n=len(rows), rows=rows,
                  mismatches=mismatches, passed=not mismatches, seconds=time.monotonic()-started)
    dump(OUT / "replication" / f"{cid}.json", result)
    return {k:v for k,v in result.items() if k not in ("rows", "calibration")}

def prepare():
    if (OUT / "manifest.json").exists():
        raise RuntimeError("manifest already fixed; do not overwrite")
    started = time.monotonic()
    stamp = now()
    (OUT / "calibration").mkdir(exist_ok=True)
    (OUT / "replication").mkdir(exist_ok=True)
    (OUT / "raw").mkdir(exist_ok=True)
    targets = sorted(csv.DictReader((ROOT / "jssa/difficulty/ghost-1023/transform-targets.csv").open()), key=lambda r:r["id"])
    assert len(targets) == len({r["id"] for r in targets}) == 40
    assert Counter(r["group"] for r in targets) == {"phi_lt_0.8":20, "phi_eq_1":20}
    eligible = sorted(r["id"] for r in csv.DictReader((ROOT / "jssa/difficulty/minima/basins-323.csv").open()) if int(r["n_vars"]) >= 1)
    features = {r["id"]: r for r in csv.DictReader((SOURCE / "features.csv").open())}
    cases = B.all_cases()
    manifest = dict(prepared_utc=stamp, inputs=tracked_inputs(), python=sys.version,
                    executable=sys.executable, numpy=np.__version__, scipy=B.scipy.__version__,
                    platform=platform.platform(), workers=4, starts=64, cap=320, timeout=30.0,
                    feature_population=len(eligible), targets=[])
    for rank, target in enumerate(targets):
        cid = target["id"]
        index = eligible.index(cid)
        assert index == int(features[cid]["index"])
        b, ev, box = B.context(cases[cid])
        a, cal = calibration(b, ev, box, index)
        existing_a = features[cid]["a"]
        if existing_a:
            assert a == float(existing_a), (cid, a, existing_a)
        dump(OUT / "calibration" / f"{cid}.json", dict(id=cid, feature_index=index, a=a, rows=cal,
                                                     existing_a_matched=bool(existing_a),
                                                     existing_feature_status=features[cid]["status"]))
        rng = np.random.default_rng([3, rank])
        starts = [box[:,0] + rng.random(len(box))*(box[:,1]-box[:,0]) for _ in range(64)]
        manifest["targets"].append(dict(target, target_rank=rank, feature_index=index, a=a,
                                        n_vars=len(b.var_names), n_constraints=len(b.spec.constraints),
                                        var_names=list(b.var_names), box=box, start_seed=[3,rank],
                                        calibration_seed=[102312,index], starts=starts))
    # This manifest is written before any optimization, including replication.
    dump(OUT / "manifest.json", manifest)
    print("FIXED manifest: 40 targets; existing a match where present; excluded features calibrated identically", flush=True)
    results = []
    with ProcessPoolExecutor(max_workers=2, mp_context=multiprocessing.get_context("spawn")) as pool:
        for result in pool.map(replicate, ("AIME-2023-I-12", "HMMT-2024-FEB-GEO-04")):
            results.append(result)
            print("REPLICATION", result, flush=True)
    dump(OUT / "preflight.json", dict(started_utc=stamp, finished_utc=now(), seconds=time.monotonic()-started,
                                      manifest_sha256=sha(OUT / "manifest.json"), replications=results,
                                      passed=all(r["passed"] for r in results)))
    assert all(r["passed"] for r in results), "replication failed; main experiment blocked"

UNKNOWN = {"timeout", "error", "missing", "missing_answer"}

def observed(rec):
    return rec.get("cls", "missing") not in UNKNOWN

def solve_problem(target):
    started = time.monotonic()
    cid = target["id"]
    rows = []
    try:
        case = B.all_cases()[cid]
        b, ev, box = B.context(case)
        refs = B.reference_values(case["answer"])
        for k, start in enumerate(target["starts"]):
            x = np.array(start)
            row = dict(k=k, start=start)
            try:
                snap = ev.evaluate_float_hard_feasibility(list(x), include_margins=False)
                row.update(start_hard_feasible=bool(snap.hard_feasible), start_hard_tags=list(snap.failure_tags))
            except Exception as exc:
                row.update(start_hard_feasible=None, start_hard_error=repr(exc))
            for mode in ("base", "sharpen"):
                rec = B.solve(b, ev, box, refs, x.copy(), target["a"], mode, 320, k, timeout=30.0)
                rec["original_cls"] = rec["cls"]
                if rec["cls"] == "wrong_answer" and rec.get("answer") is None:
                    rec["cls"] = "missing_answer"
                row[mode] = rec
            rows.append(row)
            if (k+1) % 16 == 0:
                print(f"PROGRESS {cid} {k+1}/64 {time.monotonic()-started:.1f}s", flush=True)
        result = dict(id=cid, rows=rows, seconds=time.monotonic()-started, finished_utc=now())
    except Exception:
        result = dict(id=cid, rows=rows, seconds=time.monotonic()-started,
                      finished_utc=now(), problem_error=traceback.format_exc())
    dump(OUT / "raw" / f"{cid}.json", result)
    return cid, result["seconds"], result.get("problem_error")

def run():
    manifest = read(OUT / "manifest.json")
    preflight = read(OUT / "preflight.json")
    assert preflight["passed"]
    assert preflight["manifest_sha256"] == sha(OUT / "manifest.json")
    assert manifest["inputs"] == tracked_inputs(), "input/source changed since preparation"
    if (OUT / "run-timing.json").exists():
        raise RuntimeError("run already started; no automatic retries or overwrites")
    started = time.monotonic()
    stamp = now()
    dump(OUT / "run-timing.json", dict(started_utc=stamp, status="running"))
    with ProcessPoolExecutor(max_workers=4, mp_context=multiprocessing.get_context("spawn")) as pool:
        futures = [pool.submit(solve_problem, t) for t in manifest["targets"]]
        for fut in as_completed(futures):
            print("DONE", fut.result(), flush=True)
    dump(OUT / "run-timing.json", dict(started_utc=stamp, finished_utc=now(),
                                      seconds=time.monotonic()-started, status="finished",
                                      inputs_unchanged=manifest["inputs"] == tracked_inputs()))

def write_csv(path, rows):
    fields = list(dict.fromkeys(k for row in rows for k in row))
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)

def summarize():
    manifest = read(OUT / "manifest.json")
    starts, problems, classes = [], [], {m:Counter() for m in ("base", "sharpen")}
    for t in manifest["targets"]:
        path = OUT / "raw" / f"{t['id']}.json"
        raw = read(path) if path.exists() else {}
        by_k = {r["k"]:r for r in raw.get("rows", [])}
        p = {k:t[k] for k in ("id", "group", "phi0", "p0", "target_rank", "feature_index", "a", "n_vars", "n_constraints")}
        p.update(planned_starts=64, seconds=raw.get("seconds"), problem_error=raw.get("problem_error"))
        paired, rescues, losses, rescue_bad, rescue_unknown, start_bad, start_unknown = 0, 0, 0, 0, 0, 0, 0
        for k, x in enumerate(t["starts"]):
            row = by_k.get(k, {})
            sh = row.get("start_hard_feasible")
            start_bad += sh is False
            start_unknown += sh is None
            r = dict(id=t["id"], group=t["group"], target_rank=t["target_rank"], feature_index=t["feature_index"],
                     start_index=k, a=t["a"], start_seed=json.dumps(t["start_seed"]), start=json.dumps(x),
                     start_hard_feasible=sh, start_hard_tags=json.dumps(row.get("start_hard_tags")),
                     start_hard_error=row.get("start_hard_error"))
            bb, ss = [row.get(m, {"cls":"missing"}) for m in ("base", "sharpen")]
            pair = observed(bb) and observed(ss)
            rescued = pair and bb["cls"] != "hit" and ss["cls"] == "hit"
            lost = pair and bb["cls"] == "hit" and ss["cls"] != "hit"
            paired += pair
            rescues += rescued
            losses += lost
            rescue_bad += rescued and sh is False
            rescue_unknown += rescued and sh is None
            r.update(paired_observed=pair, rescued=rescued if pair else None, lost=lost if pair else None)
            for mode, rec in (("base", bb), ("sharpen", ss)):
                classes[mode][rec["cls"]] += 1
                for key in ("cls", "original_cls", "status", "scipy_nfev", "res", "guard_ok", "hard_feasible", "answer", "seconds", "evaluations", "evaluation_failures", "error", "message", "augmented_residual_norm"):
                    r[f"{mode}_{key}"] = rec.get(key)
                for key in ("x", "hard_tags", "guard_hard_penalties"):
                    r[f"{mode}_{key}"] = json.dumps(rec[key]) if key in rec else None
            starts.append(r)
        p.update(paired_observed=paired, rescued=rescues, lost=losses, rescued_start_hard_violated=rescue_bad,
                 rescued_start_hard_missing=rescue_unknown, start_hard_violated=start_bad, start_hard_missing=start_unknown)
        for mode in ("base", "sharpen"):
            counter = Counter(by_k.get(k, {}).get(mode, {"cls":"missing"})["cls"] for k in range(64))
            n = sum(v for cls,v in counter.items() if cls not in UNKNOWN)
            h = counter["hit"]
            p.update({f"{mode}_observed":n, f"{mode}_hits":h, f"{mode}_unobserved":64-n,
                      f"{mode}_p_observed":h/n if n else None,
                      f"{mode}_p_lower":h/64, f"{mode}_p_upper":(h+64-n)/64})
            for cls in ("hit", "stuck", "left_box", "nonfinite", "wrong_branch", "wrong_answer", "timeout", "error", "missing_answer", "missing"):
                p[f"{mode}_n_{cls}"] = counter[cls]
        p["delta_observed"] = p["sharpen_p_observed"]-p["base_p_observed"] if p["base_observed"] and p["sharpen_observed"] else None
        p["delta_preregistered"] = (p["sharpen_hits"]-p["base_hits"])/64 if paired == 64 else None
        p["delta_lower"] = p["sharpen_p_lower"]-p["base_p_upper"]
        p["delta_upper"] = p["sharpen_p_upper"]-p["base_p_lower"]
        problems.append(p)
    write_csv(OUT / "per-start.csv", starts)
    write_csv(OUT / "per-problem.csv", problems)
    complete = all(p["paired_observed"] == 64 for p in problems)
    medians = {}
    for group in ("phi_lt_0.8", "phi_eq_1"):
        subset = [p for p in problems if p["group"] == group]
        medians[group] = float(np.median([p["delta_preregistered"] for p in subset])) if all(p["delta_preregistered"] is not None for p in subset) else None
    L, H = medians["phi_lt_0.8"], medians["phi_eq_1"]
    rescued = sum(p["rescued"] for p in problems)
    bad = sum(p["rescued_start_hard_violated"] for p in problems)
    unknown = sum(p["rescued_start_hard_missing"] for p in problems)
    fraction = bad/rescued if rescued and not unknown else None
    results = dict(T1=None if L is None else L >= .10, T2=None if H is None else abs(H) <= .03,
                   T3=None if fraction is None or not complete else fraction >= .80)
    timing = read(OUT / "run-timing.json") if (OUT / "run-timing.json").exists() else {}
    preflight = read(OUT / "preflight.json")
    metrics = dict(medians=medians, rescued=rescued, rescued_start_hard_violated=bad,
                   rescued_start_hard_missing=unknown, rescued_hard_violation_fraction=fraction,
                   results=results, complete=complete, classes={m:dict(c) for m,c in classes.items()},
                   preflight_seconds=preflight["seconds"], run_timing=timing,
                   source_hashes_match=manifest["inputs"] == tracked_inputs())
    dump(OUT / "metrics.json", metrics)
    label = lambda x: "判定不能" if x is None else ("基準を満たす" if x else "基準を満たさない")
    lines = ["# sol-5 事前登録3の結果", "", "対象40問（L/H各20問）、各64共通出発点、base/sharpen、LM上限320。", "",
             "| 項目 | 実測値 | 固定基準 | 判定 |", "|---|---:|---|---|",
             f"| T1: Lの差の中央値 | {L} | ≥ 0.10 | {label(results['T1'])} |",
             f"| T2: Hの差の中央値 | {H} | 絶対値 ≤ 0.03 | {label(results['T2'])} |",
             f"| T3: 救済点の初期hard違反率 | {bad}/{rescued} = {fraction} | ≥ 0.80 | {label(results['T3'])} |", ""]
    if results["T1"] is False or results["T2"] is False:
        lines += ["事前登録の棄却規則に該当する。「単調変換の効果は形の誤った出発点を通じて生じる」とは言わない。", ""]
    elif None in results.values():
        lines += ["欠測または分母0により、事前登録の全判定は完了していない。", ""]
    else:
        lines += ["T1/T2の棄却規則には該当しない。各判定は上表のとおり。", ""]
    lines += [f"- 計画: 2560出発点、5120条件実行。観測された対: {sum(p['paired_observed'] for p in problems)}/2560。",
              f"- 救済 {rescued}、喪失 {sum(p['lost'] for p in problems)}。救済点の初期hard欠測 {unknown}。",
              f"- 全出発点の初期hard違反 {sum(p['start_hard_violated'] for p in problems)}、初期hard欠測 {sum(p['start_hard_missing'] for p in problems)}。", "",
              "| 終点の分類 | base | sharpen |", "|---|---:|---:|"]
    for cls in sorted(set(classes["base"]) | set(classes["sharpen"]) | UNKNOWN):
        lines.append(f"| {cls} | {classes['base'][cls]} | {classes['sharpen'][cls]} |")
    lines += ["", "欠測・時間切れは非成功に置き換えていない。timeout/error/missing_answer/missingを別計上し、CSVの成功率の分母から除外する。主差は64対すべて観測された場合だけ算出。LMの評価上限到達（status=0）は時間切れと区別して終点を採点する。", "",
              f"準備・2問再現確認: {preflight['seconds']:.3f}秒。本実験の実時間: {timing.get('seconds')}秒（4並列、共有CPU）。各問のsecondsの和は並列実時間ではない。",
              f"開始UTC: {timing.get('started_utc')}、終了UTC: {timing.get('finished_utc')}。", "",
              "2問の再現確認は各100点×base/sharpenで、保存済みreplicationの各点分類と完全一致。既存featuresにaがある38問は完全一致。AIME-2013-II-04、HMMT-2006-FEB-GEO-03はastra-Bのfeaturesでは等式数<変数数で除外されaがないため、同じ16点・同じ計算法で較正し、対象から除外せず指定のLMを実行した（拡張残差の行数はLMに十分）。実行後の入力・コードハッシュ一致: " + str(metrics["source_hashes_match"]) + "。", "",
              "群Hは既存seed0でφ=1の群であり、新しい64点のhard feasibilityが必ず全点Trueとは限らない。実測はper-start.csvに保存。基準・群・指標・乱数の変更はない。", "",
              "## 問題ごとの結果", "", "| ID | 群 | base hit/observed | sharpen hit/observed | 差 | 救済 | 初期hard違反の救済 |", "|---|---|---:|---:|---:|---:|---:|"]
    for p in problems:
        lines.append(f"| {p['id']} | {p['group']} | {p['base_hits']}/{p['base_observed']} | {p['sharpen_hits']}/{p['sharpen_observed']} | {p['delta_preregistered']} | {p['rescued']} | {p['rescued_start_hard_violated']} |")
    (OUT / "score.md").write_text("\n".join(lines)+"\n")
    print(json.dumps(metrics, ensure_ascii=False, indent=2), flush=True)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("prepare", "run", "summarize"))
    args = parser.parse_args()
    {"prepare":prepare, "run":run, "summarize":summarize}[args.mode]()
