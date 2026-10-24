"""Aggregate the fixed registered runs; never invokes the solver."""
import csv
import gzip
import hashlib
import json
import io
import statistics as st
from collections import Counter
from pathlib import Path

OUT = Path(__file__).resolve().parent
M = json.loads((OUT / "pre-run-hashes.json").read_text())
SCRATCH = Path(M["scratch"])
ARMS = M["arms"]


def median(values):
    return st.median(values) if values else None


def fmt(value):
    return "算出不可" if value is None else f"{value:.4f}"


def write_csv(name, rows):
    fields = list(dict.fromkeys(k for row in rows for k in row))
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=fields)
    writer.writeheader()
    for row in rows:
        writer.writerow({k: json.dumps(v, ensure_ascii=False, separators=(",", ":"))
                         if isinstance(v, (dict, list)) else v for k, v in row.items()})
    payload = stream.getvalue().encode()
    assert len(payload) <= 3_000_000, (name, len(payload))
    (OUT / name).write_bytes(payload)


def main():
    rows = [json.loads(path.read_text()) for path in sorted(SCRATCH.glob("runs/*/*/*/record.json"))]
    assert len(rows) == 648, len(rows)
    lookup = {(r["case_id"], r["seed"], r["arm"]): r for r in rows}
    assert len(lookup) == 648
    raw_hashes = []
    flat = []
    for row in sorted(rows, key=lambda r: r["schedule_index"]):
        path = Path(row["raw_path"])
        sha = hashlib.sha256(path.read_bytes()).hexdigest()
        assert sha == row["raw_sha256"]
        raw_hashes.append({"path": str(path), "sha256": sha, "bytes": path.stat().st_size})
        with gzip.open(path, "rt") as stream:
            raw = json.load(stream)
        result = raw.get("solver_result") or {}
        artifact = result.get("worker_artifact") or {}
        summary = (artifact.get("diagnostics") or {}).get("pipeline_summary") or {}
        candidates = artifact.get("candidate_records") or []
        records = summary.get("exact_candidate_records") or []
        source_id = summary.get("answer_source_candidate_id")
        sources = []
        for candidate in candidates:
            if candidate.get("accepted"):
                source = candidate.get("source") or {}
                sources.append({k: source.get(k) for k in ("origin_phase", "origin_backend", "origin_attempt", "candidate_uid")})
        r = dict(row)
        # Detailed counters are retained in raw; the two registered counts have
        # their own scalar columns in this table.
        r.pop("counters", None)
        r["second_attempt"] = {k: v for k, v in (summary.get("search_staged_fallback") or {}).items()
                               if k in ("triggered", "selected_stage", "primary_search_mode", "primary_exact_assembly_accepted_count")}
        r["rescue"] = summary.get("phase_rescue")
        # Full UIDs, norms and local-start event ledgers remain in hashed raw.
        r["handoffs"] = [{k: h.get(k) for k in ("kind", "selected", "all_records", "pool")} for h in row["handoffs"]]
        search = summary.get("search") or {}
        r["search"] = {k: search[k] for k in (
            "evaluation_count", "failure_ratio", "selected_candidates", "all_record_count",
            "guard_feasible_record_count", "guard_feasible_ledger_count", "compact_candidate_count",
        ) if k in search}
        r["search_diagnostic_kinds"] = [k for k in search if k not in r["search"]]
        r["second_attempt_triggered"] = (summary.get("search_staged_fallback") or {}).get("triggered")
        r["rescue_triggered"] = (summary.get("phase_rescue") or {}).get("triggered")
        r["algebraic_branch_discovery"] = bool((summary.get("initial_probe") or {}).get("algebraic_branch_discovery")) if summary else None
        r["refinement"] = summary.get("refinement")
        r["exact_assembly"] = summary.get("exact_assembly")
        verifications = summary.get("verification_records")
        r["verification_records"] = [v.get("verified") if isinstance(v, dict) else v
                                     for v in verifications] if verifications is not None else None
        r["verification_checked_count"] = len(verifications) if verifications is not None else None
        r["verification_passed_count"] = sum(v is True for v in r["verification_records"]) if verifications is not None else None
        r["answer_source_candidate_id"] = source_id
        r["answer_sources"] = sources
        r["refinement_converged_observed"] = sum(e["converged"] for e in raw["probe_events"] if e["kind"] == "refinement_return")
        r["refinement_hard_feasible_observed"] = sum(e["hard_feasible"] for e in raw["probe_events"] if e["kind"] == "refinement_return")
        r["verified_candidate_count"] = sum(any(h.get("verified") for h in c.get("verification_history", [])) for c in candidates)
        r["accepted_candidate_count"] = sum(bool(c.get("accepted")) for c in candidates)
        r["algebraic_preprocessing_answer"] = any(s["origin_backend"] == "exact_polynomial" for s in sources)
        flat.append(r)
    write_csv("per-run.csv", flat)
    (OUT / "raw-hashes.json").write_text(json.dumps(raw_hashes, indent=1) + "\n")
    problems = []
    for problem in M["inputs"]:
        cid = problem["case_id"]
        r = {"case_id": cid, "group": problem["group"]}
        arms = {a: [lookup[cid, s, a] for s in M["seeds"]] for a in ARMS}
        for arm in ARMS:
            r[arm + "_correct_runs"] = sum(x["matched"] for x in arms[arm])
            r[arm + "_solved"] = r[arm + "_correct_runs"] >= 2
            r[arm + "_C_mean"] = st.mean(x["C"] for x in arms[arm])
            r[arm + "_C_median"] = st.median(x["C"] for x in arms[arm])
        counts = [x["smooth_calls"] for x in arms["BASE"]]
        r["BASE_smooth_calls"] = counts
        r["rewrite_applies"] = any(x is not None and x >= 1 for x in counts)
        r["rewrite_classification_complete"] = r["rewrite_applies"] or all(x is not None for x in counts)
        for arm in ARMS[1:]:
            pairs = [lookup[cid, s, arm]["wall_seconds"] / lookup[cid, s, "BASE"]["wall_seconds"]
                     for s in M["seeds"] if lookup[cid, s, arm]["matched"] and lookup[cid, s, "BASE"]["matched"]]
            r[arm + "_paired_ratios"] = pairs
            r[arm + "_ratio_median"] = median(pairs)
        r["R1_lost_solved"] = r["BASE_solved"] and not r["NO_RESIDUAL_REWRITE_solved"]
        ratio = r["NO_RESIDUAL_REWRITE_ratio_median"]
        r["R1_ratio_ge_1_5"] = ratio is not None and ratio >= 1.5
        r["R1_affected"] = r["R1_lost_solved"] or r["R1_ratio_ge_1_5"]
        problems.append(r)
    write_csv("per-problem.csv", problems)
    applies = [p for p in problems if p["rewrite_applies"]]
    not_applies = [p for p in problems if not p["rewrite_applies"] and p["rewrite_classification_complete"]]
    unknown_rewrite = [p for p in problems if not p["rewrite_classification_complete"]]
    nonmulti = [p for p in problems if p["group"] != "multivalued"]
    multi = [p for p in problems if p["group"] == "multivalued"]
    solved = lambda ps, arm: sum(p[arm + "_solved"] for p in ps)
    correct = lambda ps, arm: sum(p[arm + "_correct_runs"] for p in ps)
    affected = sum(p["R1_affected"] for p in applies)
    r2_diff = solved(not_applies, "NO_RESIDUAL_REWRITE") - solved(not_applies, "BASE")
    r2_ratio = median([p["NO_RESIDUAL_REWRITE_ratio_median"] for p in not_applies if p["NO_RESIDUAL_REWRITE_ratio_median"] is not None])
    d1_drop = correct(multi, "BASE") - correct(multi, "NO_DIVERSE_SELECTION")
    d2_diff = solved(nonmulti, "NO_DIVERSE_SELECTION") - solved(nonmulti, "BASE")
    d3_ratios = [p["NO_DIVERSE_SELECTION_ratio_median"] for p in nonmulti if p["NO_DIVERSE_SELECTION_ratio_median"] is not None]
    d3_over = [p["case_id"] for p in nonmulti if p["NO_DIVERSE_SELECTION_ratio_median"] is not None and p["NO_DIVERSE_SELECTION_ratio_median"] > 1]
    d3_missing = len(nonmulti) - len(d3_ratios)
    r1 = bool(applies) and affected * 2 >= len(applies) and not unknown_rewrite
    r2 = abs(r2_diff) <= 1 and r2_ratio is not None and 0.9 <= r2_ratio <= 1.1 and not unknown_rewrite
    d1 = d1_drop >= 3
    d2 = abs(d2_diff) <= 2
    d3 = not d3_over and d3_missing == 0
    verdict = lambda flag: "的中" if flag else "外れ"
    missing = sum(r["category"] == "missing" for r in rows)
    runtime_failures = sum(not r["normal_completion"] and r["category"] not in ("timeout", "missing") for r in rows)
    worker_artifact_missing = sum(r["source_hash"] is None for r in rows)
    probe_missing = sum(not r["probe_available"] for r in rows)
    lines = [
        "| 予測 | 判定 | 固定条件に対する実測 |", "|---|---|---|",
        f"| R1 | {verdict(r1)} | 書き換え呼出あり{len(applies)}問中、解けなくなる／時間比中央値≥1.5：{affected}問（半数以上が条件） |",
        f"| R2 | {verdict(r2)} | 呼出なし{len(not_applies)}問：解けた問題差 {r2_diff:+d}問、時間比の中央値 {fmt(r2_ratio)}（条件：差±1問、0.9–1.1） |",
        f"| D1 | {verdict(d1)} | 複数値8問・24実行：BASE {correct(multi, 'BASE')}、残差順上位20 {correct(multi, 'NO_DIVERSE_SELECTION')}正解、減少{d1_drop}回（条件≥3） |",
        f"| D2 | {verdict(d2)} | 他64問：BASE {solved(nonmulti, 'BASE')}、残差順上位20 {solved(nonmulti, 'NO_DIVERSE_SELECTION')}問が解けた。差 {d2_diff:+d}問（条件±2） |",
        f"| D3 | {verdict(d3)} | 他64問の問題別時間比中央値：1.0超 {len(d3_over)}問、算出不可 {d3_missing}問。中央値の中央値 {fmt(median(d3_ratios))} |", "",
        f"648/648実行終了。生結果の欠測 {missing}件、worker artifact欠落 {worker_artifact_missing}件、計数欠測 {probe_missing}件、書き換え群の分類不能 {len(unknown_rewrite)}問。実行失敗 {runtime_failures}件も不正解に含めた。",
        f"開始時1分load average：最小 {min(r['loadavg_start'] for r in rows):.2f}、中央値 {st.median(r['loadavg_start'] for r in rows):.2f}、最大 {max(r['loadavg_start'] for r in rows):.2f}。他作業の負荷を含むため、時間は参考値。", "",
        "「解けた」は3 seed中2回以上で参照の答え集合に完全一致。時間比は同じ問題・seedで両構成が完全一致した実行だけを使い、まず問題別中央値を求めた。R1の対象群はBASEの実際の書き換え呼出数だけで機械的に決めた。",
        "D3は原文の「問題ごとの中央値は1.0倍以下」を各問題の条件として判定した。中央値の中央値も併記するが、判定の代わりには使わない。算出できない場合は数値条件の成立を確認できないため外れとした。", "",
        "| 構成 | 解けた問題/72 | 完全一致/216 | 費用Cの平均（秒） |", "|---|---:|---:|---:|"]
    for arm in ARMS:
        lines.append(f"| {arm} | {solved(problems, arm)} | {correct(problems, arm)} | {st.mean(r['C'] for r in rows if r['arm']==arm):.3f} |")
    lines += ["", "Cは完全一致なら記録時間、それ以外は180秒。失敗・時間切れも全件含む。", "",
              "| 構成 | 完全一致 | 誤答 | 一部回収 | 答えなし | 時間切れ | 欠測 |", "|---|---:|---:|---:|---:|---:|---:|"]
    for arm in ARMS:
        counts = Counter(r["category"] for r in rows if r["arm"] == arm)
        lines.append("| " + arm + " | " + " | ".join(str(counts[k]) for k in ("correct", "wrong", "partial", "no_answer", "timeout", "missing")) + " |")
    lines += ["", f"完全一致と時間切れは別列にも保存し、期限内保存の正解は共通採点に従って完全一致に含めた。「答えなし」のうち実行失敗は{runtime_failures}件。worker artifactがない実行ではworkerの実行元・実測CPU情報は欠測とし、起動コマンドと計数は残した。",
              f"R1内訳：解けなくなった {sum(p['R1_lost_solved'] for p in applies)}問、時間比≥1.5 {sum(p['R1_ratio_ge_1_5'] for p in applies)}問（重複あり）。",
              f"R2の時間比算出不可：{sum(p['NO_RESIDUAL_REWRITE_ratio_median'] is None for p in not_applies)}問。",
              f"D3の1.0超：{', '.join(d3_over) or 'なし'}。", "",
              f"実行元：`{M['clean_source']}`（新しいクリーン展開）。source_hash `{M['source_hash']}`。",
              "EngineRunner直接、180秒・1コア・並列16・内部スレッド各1、CPU固定。seed 401–403。構成順は既存方式のcrc32回転。再試行・追加seed・問題交換なし。最終検証は凍結版とバイト一致、採点は60db4b6のresearch_runner。",
              f"生記録は `{SCRATCH}/runs/` のgzipに全回答・worker artifact・計数・stdout/stderrを保存。対応するハッシュ一覧は `raw-hashes.json`。入力・patch・ソース・ランナーの実行前ハッシュは `pre-run-hashes.json`。",
              "問題別判定と対応時間比は `per-problem.csv`、全実行の状態・負荷・候補数・段階記録は `per-run.csv`。段階情報が期限切れで残らない項目は空欄／nullとし、推測で埋めていない。",
              "この72問は開発群から差の出やすい問題を多めに選んだ固定組であり、全問題の平均へ一般化しない。", ""]
    (OUT / "answer.md").write_text("\n".join(lines))
    summary = {"runs": len(rows), "verdicts": dict(zip(("R1", "R2", "D1", "D2", "D3"), (r1, r2, d1, d2, d3))),
               "missing": missing, "probe_missing": probe_missing, "d3_median_of_medians": median(d3_ratios)}
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary), flush=True)


if __name__ == "__main__":
    main()
