"""Export raw production records, then aggregate per-run.csv without solver calls."""
from __future__ import annotations

import argparse
import csv
import math
import os
import sys
from collections import Counter
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]
for key in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
    os.environ[key] = "1"

import numpy as np
from scipy.stats import spearmanr

from benchmarks import research_runner as research
from run import CONDITIONS, HERE, prediction_rows, read_json, summarize_audit


def write_csv(path, rows):
    if not rows:
        raise ValueError("no rows")
    temporary = path.with_suffix(".csv.tmp")
    with temporary.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    temporary.replace(path)


def correct_and_cost(raw, references):
    """Same answer parser and set equality as research.assess_campaign."""
    from geosolver.exact import describe_exact
    outcome = research.read_run_outcome(raw)
    actual = research._answer_keys(raw.get("solver_result"))
    expected = sorted({research._canonical_json(describe_exact(value).canonical_key())
                       for reference in references
                       for value in research.reference_expressions(reference)})
    matched = bool(outcome["normal_completion"] and actual == expected)
    wall = outcome["wall_seconds"]
    correct = (matched and raw.get("process", {}).get("returncode") in (0, None)
               and wall is not None and math.isfinite(float(wall)) and 0 <= float(wall) <= 180)
    return outcome, matched, correct, float(wall) if correct else 180.0


def export_per_run(destination):
    manifest = read_json(destination / "manifest.json")["fixed"]
    cases = {r.identifier: r for r in research._load_cases()}
    rows = []
    for identifier in manifest["ids"]:
        for seed in manifest["seeds"]:
            for condition in CONDITIONS:
                run_dir = destination / condition / "runs" / identifier
                raw_path = run_dir / f"{seed}.json"
                if not raw_path.exists():
                    continue
                raw = read_json(raw_path)
                receipt_path = run_dir / f"{seed}.receipt"
                receipt = read_json(receipt_path) if receipt_path.exists() else {}
                audit = summarize_audit(run_dir / f"{seed}.starts.jsonl", condition)
                error = ""
                try:
                    outcome, matched, correct, cost = correct_and_cost(raw, cases[identifier].references)
                except Exception as exc:
                    outcome = research.read_run_outcome(raw)
                    matched, correct, cost = False, False, 180.0
                    error = f"{type(exc).__name__}: {exc}"
                process = raw.get("process", {})
                # Never silently exclude runtime failures, external timeouts, or scoring errors.
                runtime_error = bool(not outcome["normal_completion"] or error
                                     or process.get("returncode") not in (0, None))
                if runtime_error or process.get("timed_out"):
                    correct, cost = False, 180.0
                row = dict(id=identifier, seed=seed, condition=condition,
                           correct=int(correct), cost=cost, matched=int(matched),
                           wall_seconds=outcome["wall_seconds"],
                           process_wall_seconds=outcome["process_wall_seconds"],
                           status=outcome["status"], external_timeout=int(bool(process.get("timed_out"))),
                           error=int(runtime_error), assessment_error=error,
                           execution_contract_issues=";".join(raw.get("execution_contract_issues", [])),
                           runner_error=receipt.get("runner_error") or "",
                           returncode=process.get("returncode"),
                           ordinal=receipt.get("ordinal"), hostname=receipt.get("hostname"),
                           cpu=process.get("assigned_cpu"),
                           affinity=research._canonical_json(process.get("actual_affinity")),
                           load_samples=receipt.get("load_samples"),
                           receipt_recovered=int(bool(receipt.get("recovered"))),
                           started_unix=receipt.get("started_unix"),
                           finished_unix=receipt.get("finished_unix"))
                for prefix, key in (("start", "start_loadavg"), ("max", "max_loadavg")):
                    values = receipt.get(key)
                    for index, minutes in enumerate((1, 5, 15)):
                        row[f"{prefix}_loadavg_{minutes}m"] = values[index] if values else None
                row.update({key: int(value) if isinstance(value, bool) else value
                            for key, value in audit.items()})
                rows.append(row)
    write_csv(destination / "per-run.csv", rows)
    return rows


def aggregate(destination):
    design = read_json(destination / "manifest.json")["fixed"]
    with (destination / "per-run.csv").open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    expected = {(identifier, seed, condition) for identifier in design["ids"]
                for seed in design["seeds"] for condition in CONDITIONS}
    seen, indexed = set(), {}
    for row in rows:
        key = (row["id"], int(row["seed"]), row["condition"])
        if key not in expected or key in seen:
            raise ValueError(f"duplicate/unplanned per-run row: {key}")
        seen.add(key)
        row["cost"], row["correct"] = float(row["cost"]), int(row["correct"])
        if (row["correct"] not in (0, 1) or not 0 <= row["cost"] <= 180
                or (not row["correct"] and row["cost"] != 180)):
            raise ValueError(f"invalid cost/correct: {key}")
        if (int(row["external_timeout"]) or int(row["error"])) and (row["correct"] or row["cost"] != 180):
            raise ValueError(f"error excluded/misscored: {key}")
        indexed[key] = row
    predictions = {r["id"]: r for r in prediction_rows()}
    problems = []
    for identifier in design["ids"]:
        groups = {c: [indexed[identifier, seed, c] for seed in design["seeds"]
                      if (identifier, seed, c) in indexed] for c in CONDITIONS}
        complete = all(len(g) == len(design["seeds"]) for g in groups.values())
        record = dict(id=identifier, complete=int(complete), pred_delta=predictions[identifier]["pred_delta"])
        for condition, group in groups.items():
            record[f"n_{condition}"] = len(group)
            record[f"mean_cost_{condition}"] = float(np.mean([r["cost"] for r in group])) if group else None
            record[f"accuracy_{condition}"] = float(np.mean([r["correct"] for r in group])) if group else None
            record[f"external_timeouts_{condition}"] = sum(int(r["external_timeout"]) for r in group)
            record[f"errors_{condition}"] = sum(int(r["error"]) for r in group)
        record["delta_cost_redraw_minus_normal"] = (
            record["mean_cost_redraw"] - record["mean_cost_normal"] if complete else None)
        record["cost_reduction_normal_minus_redraw"] = (
            -record["delta_cost_redraw_minus_normal"] if complete else None)
        problems.append(record)
    write_csv(destination / "per-problem.csv", problems)
    paired = [r for r in problems if r["complete"]]
    if not paired:
        raise ValueError("no complete problem pairs yet; per-problem.csv written")
    deltas = np.array([r["delta_cost_redraw_minus_normal"] for r in paired])
    rng = np.random.default_rng(design["bootstrap_seed"])
    # Resample problems, retaining their complete seed averages and paired arms.
    bootstrap = np.mean(deltas[rng.integers(0, len(deltas), (10000, len(deltas)))], axis=1)
    low, high = np.quantile(bootstrap, [0.025, 0.975])
    difference = float(deltas.mean())
    accuracy_delta = float(np.mean([r["accuracy_redraw"] - r["accuracy_normal"] for r in paired]))
    s3_rows = [r for r in paired if r["pred_delta"] != ""]
    rho = None
    if len(s3_rows) >= 2:
        x = [float(r["pred_delta"]) for r in s3_rows]
        y = [r["cost_reduction_normal_minus_redraw"] for r in s3_rows]
        if len(set(x)) > 1 and len(set(y)) > 1:
            rho = float(spearmanr(x, y).statistic)
    complete = seen == expected
    confirmatory = complete and design["mode"] == "full"
    s1 = difference < 0 and high < 0
    s2 = accuracy_delta >= -0.01
    s3 = rho is not None and rho >= 0.3
    status = lambda passed: ("成立" if passed else "不成立") if confirmatory else "判定しない（smoke/未完了）"
    lines = ["# 費用比較 " + ("本計算" if confirmatory else "動作確認または途中集計（本計算の判定ではない）"), "",
             f"完了 {len(rows)}/{len(expected)} 実行、全 seed・両条件が揃った問題 {len(paired)}/{len(problems)}。",
             "C = 本番採点で集合一致かつ180秒以内なら solver_result.elapsed_seconds、それ以外180秒。",
             "外部タイムアウト・エラーを除外しない。未実行は費用を補完せず、途中では判定しない。", "",
             "| 指標 | 値 | 事前登録の判定 |", "|---|---|---|",
             f"| S1 平均 C(選び直し) − C(通常) | {difference:.6f} 秒; 95% CI [{low:.6f}, {high:.6f}] | {status(s1)} |",
             f"| S2 正答率差（選び直し − 通常） | {accuracy_delta:.6f} | {status(s2)} |",
             f"| S3 費用の減少 × pred_delta の Spearman 順位相関 | {rho if rho is not None else 'NA（定数または点数不足）'} | {status(s3)} |", "",
             "S1: 問題単位の paired percentile bootstrap 10,000回、95%区間。"
             f"集計専用乱数 seed={design['bootstrap_seed']}（solver乱数とは独立）。",
             f"S3: {len(s3_rows)}問、pred_delta欠測 {len(paired) - len(s3_rows)}問。"
             "同順位は平均順位、欠測の補完なし。全150問では122問が利用可能。", "",
             "| 条件 | 実行数 | 正答 | 外部タイムアウト | エラー（重複あり） | audit未確認 |", "|---|---:|---:|---:|---:|---:|"]
    for condition in CONDITIONS:
        group = [r for r in rows if r["condition"] == condition]
        lines.append(f"| {condition} | {len(group)} | {sum(r['correct'] for r in group)} | "
                     f"{sum(int(r['external_timeout']) for r in group)} | {sum(int(r['error']) for r in group)} | "
                     f"{sum(r['audit_verified'] != '1' for r in group)} |")
    lines += ["", f"状態別件数: {dict(Counter(r['status'] for r in rows))}", "",
              "audit未確認・未消費（starts_consumed=0）は、効果の実装確認と区別して記録する。"
              "生成だけで未使用の点を、使用済みとは数えない。"]
    if confirmatory and not s1:
        lines += ["", "局所探索の成功率の改善は、完成した solver の費用の改善には移らなかった。"]
    (destination / "score.md").write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    print(f"aggregate: {len(rows)} runs -> {len(problems)} problems -> {destination / 'score.md'}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--smoke", action="store_true")
    parser.add_argument("--refresh-per-run", action="store_true", help="rebuild CSV from raw records; no solver")
    args = parser.parse_args()
    destination = HERE / "smoke" if args.smoke else HERE
    if args.refresh_per_run:
        export_per_run(destination)
    aggregate(destination)


if __name__ == "__main__":
    main()
