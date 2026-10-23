"""Posthoc scoring of existing receipts only. Never execute a solver."""
from __future__ import annotations

import collections
import csv
import datetime as dt
import hashlib
import io
import json
import statistics
import subprocess
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.setrecursionlimit(10000)
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
PREFLIGHT = json.loads((HERE / "preflight.json").read_text())
sys.path[:0] = [str(Path(PREFLIGHT["runtime_root"]) / "src"), str(ROOT), str(HERE)]
from prepare import CORPUS, IDS, now, sha
from score import assess, validate_conversions
from geosolver.runtime.integrity import source_tree_hash


def write_small(path, text):
    assert len(text.encode("utf-8")) < 5_000_000, path
    Path(path).write_text(text, encoding="utf-8")


def dump_csv(path, rows):
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
    writer.writeheader()
    writer.writerows(rows)
    write_small(path, stream.getvalue())


def timestamp(value):
    parsed = dt.datetime.fromisoformat(value)
    assert parsed.tzinfo is not None
    return parsed


def utc_time(value):
    return timestamp(value).astimezone(dt.timezone.utc).strftime("%H:%M:%S.%f")


def verify_inputs(fixed, execution):
    assert sha(HERE / "prediction.md") == fixed["prediction_sha256"] == execution["prediction_sha256"]
    assert sha(HERE / "prediction.lock.json") == execution["prediction_lock_sha256"]
    assert execution["frozen_commit"] == fixed["frozen_commit"]
    assert source_tree_hash() == fixed["source_hash"] == execution["runtime"]["source_hash"]
    assert execution["preflight_sha256"] == sha(HERE / "preflight.json")
    for name, digest in {**fixed["files_sha256"], "prediction.lock.json": execution["prediction_lock_sha256"]}.items():
        path = ROOT / "benchmarks/research_runner.py" if name == "@research_runner.py" else HERE / name
        assert sha(path) == digest, "locked file changed: " + name
        committed = subprocess.check_output(
            ["git", "show", execution["prediction_commit"] + ":" + path.relative_to(ROOT).as_posix()], cwd=ROOT)
        assert hashlib.sha256(committed).hexdigest() == digest, "commit mismatch: " + name
    source = json.loads((HERE / "source-inputs.json").read_text())
    for cid, digest in source["original_dsl_sha256"].items():
        assert sha(CORPUS / "dsl" / (cid + ".json")) == digest, cid
    assert sha(CORPUS / "prereg/q19-scored/assessment.jsonl") == source["q19_assessment_sha256"]


def rescore(path, fixed):
    doc = json.loads(path.read_text())
    stored = doc["assessment"]
    group, cid, seed = doc["group"], stored["case_id"], stored["seed"]
    assert path.relative_to(HERE / "campaign").parts == (group, "runs", cid, str(seed) + ".json")
    available = "answers" in doc
    execution, process = doc.get("execution", {}), doc.get("process", {})
    if available:
        assert (execution["case_id"], execution["seed"]) == (cid, seed)
        assert execution["source_hash"] == doc["engine"]["source_hash"] == fixed["source_hash"]
        dsl = json.loads(((HERE if group == "main" else CORPUS) / "dsl" / (cid + ".json")).read_text())
        canonical = json.dumps(dsl, ensure_ascii=False, allow_nan=False, sort_keys=True, separators=(",", ":"))
        assert hashlib.sha256(canonical.encode()).hexdigest() == execution["problem_hash"]
        assert execution["config"]["time_limit_seconds"] == 180 and execution["config"]["cores"] == 1
        assert all(value == "1" for value in execution["config"]["thread_environment"].values())
        assert execution["dependency_lock_hash"] == sha(Path(PREFLIGHT["runtime_root"]) / "uv.lock")
        assert process["actual_affinity"] == [process["assigned_cpu"]]
        assert process["assigned_cpu"] in PREFLIGHT["cpus"]
        raw = {**execution, "process": process, "solver_result": {
            "status": stored["status"], "answers": doc["answers"], "engine": doc["engine"],
            "diagnostics": doc["diagnostics"], "elapsed_seconds": stored["wall_seconds"],
            "termination_reason": stored["termination_reason"]}}
    else:
        assert stored["status"] == "runner_error" and not stored["matched"]
        assert doc["runner_error"].splitlines()[-1] == "AssertionError: summary unexpectedly large"
        # Missing output is not evidence that the solver returned zero answers.
        raw = {"case_id": cid, "seed": seed, "solver_result": None}
    scored = assess(raw)
    assert scored["matched"] == stored["matched"], path
    if available:
        for key in ("matched", "geometric_matched", "official_output_matched", "actual_exact_keys",
                    "expected_exact_keys", "answer_expressions", "converted_outputs", "conversion_errors",
                    "n_answers", "normal_completion", "status", "failure_stage", "termination_reason"):
            assert scored[key] == stored[key], (path, key)
    start, finish = timestamp(doc["started_at_utc"]), timestamp(doc["finished_at_utc"])
    assert finish >= start
    delay = (start - timestamp(fixed["locked_at_utc"])).total_seconds()
    return {
        "group": group, "case_id": cid, "seed": seed, "matched": scored["matched"],
        "status": stored["status"], "scoring_status": scored["status"], "solver_result_available": available,
        "n_answers": scored["n_answers"] if available else None, "score_n_answers": scored["n_answers"],
        "answer_expressions": " | ".join(scored["answer_expressions"]),
        "converted_outputs": " | ".join(scored["converted_outputs"]),
        "geometric_matched": scored["geometric_matched"], "official_output_matched": scored["official_output_matched"],
        "conversion_errors": " | ".join(scored["conversion_errors"]),
        "wall_seconds": scored["wall_seconds"], "process_wall_seconds": scored["process_wall_seconds"],
        "receipt_elapsed_seconds": round((finish - start).total_seconds(), 6),
        "failure_stage": scored["failure_stage"], "artifact_failure": None if available else "summary_size_assertion",
        "runner_error": doc["runner_error"].splitlines()[-1] if doc.get("runner_error") else None,
        "termination_reason": scored["termination_reason"],
        "numeric_feasible": scored["diag_numeric"], "exact_identified": scored["diag_identified"],
        "normal_completion": scored["normal_completion"],
        "source_hash": execution.get("source_hash"), "problem_hash": execution.get("problem_hash"),
        "dependency_lock_hash": execution.get("dependency_lock_hash"),
        "execution_contract_issues": json.dumps(execution["execution_contract_issues"]) if available else None,
        "assigned_cpu": process.get("assigned_cpu"),
        "actual_affinity": json.dumps(process["actual_affinity"]) if available else None,
        "started_at_utc": doc["started_at_utc"], "finished_at_utc": doc["finished_at_utc"], "start_order": None,
        "prediction_locked_at_utc": fixed["locked_at_utc"],
        "seconds_after_prediction_lock": round(delay, 6), "started_after_prediction_lock": delay > 0,
        "receipt_path": path.relative_to(HERE).as_posix(), "receipt_sha256": sha(path),
        "raw_canonical_sha256": doc.get("raw_canonical_sha256"), "stored_match_agrees": True,
    }


def counts(rows):
    return {"correct": sum(r["matched"] for r in rows), "completed": len(rows),
            "answer_records_available": sum(r["solver_result_available"] for r in rows),
            "output_record_missing": sum(not r["solver_result_available"] for r in rows)}


def main():
    fixed = json.loads((HERE / "prediction.lock.json").read_text())
    execution = json.loads((HERE / "campaign/execution-manifest.json").read_text())
    verify_inputs(fixed, execution)
    controls = validate_conversions()
    paths = sorted((HERE / "campaign").glob("*/runs/*/*.json"))
    receipt_hashes = {path: sha(path) for path in paths}
    trials = [rescore(path, fixed) for path in paths]
    planned = {("main", cid, seed) for cid in IDS for seed in range(206, 211)}
    planned |= {("hexagon-new", "AIME-1991-14", seed) for seed in range(206, 211)}
    planned |= {(f"hexagon-repeat{rep}", "AIME-1991-14", 205) for rep in (1, 2)}
    keys = {(r["group"], r["case_id"], r["seed"]) for r in trials}
    assert len(keys) == len(trials) == 52 and keys == planned
    assert planned == {(r["group"], r["id"], r["seed"]) for r in execution["tasks"]}
    for index, row in enumerate(sorted(trials, key=lambda r: timestamp(r["started_at_utc"])), 1):
        row["start_order"] = index
    trials.sort(key=lambda r: (r["group"] != "main", r["group"], r["case_id"], r["seed"]))
    main_trials = [r for r in trials if r["group"] == "main"]
    diagnostic = sorted((r for r in trials if r["group"] != "main"), key=lambda r: r["start_order"])
    originals = [json.loads(line) for line in (CORPUS / "prereg/q19-scored/assessment.jsonl").read_text().splitlines()]
    old = collections.defaultdict(list)
    for row in originals:
        old[row["case_id"]].append(row)
    target = [r for r in originals if r["in_target"]]
    assert (sum(r["matched"] for r in target), len(target)) == (85, 130)
    manifest = {r["id"]: r for r in json.loads((HERE / "rewrite-manifest.json").read_text())}
    validation = {(r["id"], r["variant"]): r for r in json.loads((HERE / "witness-validation.json").read_text())["checks"]}
    per = []
    for cid in IDS:
        runs = [r for r in main_trials if r["case_id"] == cid]
        assert len(runs) == len(old[cid]) == 5
        original = json.loads((CORPUS / "dsl" / (cid + ".json")).read_text())
        rewritten = json.loads((HERE / "dsl" / (cid + ".json")).read_text())
        witness = validation[cid, "rewritten"]
        elapsed = [r["wall_seconds"] for r in runs if r["matched"] and r["wall_seconds"] is not None]
        per.append({
            "case_id": cid, "changed": manifest[cid]["changed"],
            "q19_correct": sum(r["matched"] for r in old[cid]), "q19_runs": len(old[cid]),
            "posthoc_correct": sum(r["matched"] for r in runs), "posthoc_completed": len(runs), "posthoc_planned": 5,
            "posthoc_accuracy": sum(r["matched"] for r in runs) / 5,
            "answer_records_available": sum(r["solver_result_available"] for r in runs),
            "output_record_missing": sum(not r["solver_result_available"] for r in runs),
            "normal_completion": sum(r["normal_completion"] for r in runs),
            "no_answer": sum(r["solver_result_available"] and r["n_answers"] == 0 for r in runs),
            "returned_wrong_or_extra": sum(r["solver_result_available"] and r["n_answers"] > 0 and not r["matched"] for r in runs),
            "correct_elapsed_median": statistics.median(elapsed) if elapsed else None,
            "old_variables": len(original["variables"]), "new_variables": len(rewritten["variables"]),
            "old_conditions": len(original["conditions"]), "new_conditions": len(rewritten["conditions"]),
            "witness_all_conditions": witness["all_conditions_satisfied"],
            "witness_hard_feasible": witness["frozen_hard_feasible"],
            "max_equality_residual": witness["max_absolute_equality_residual"],
            "min_strict_margin": witness["minimum_strict_inequality_margin"]})
    changed_ids = {cid for cid, row in manifest.items() if row["changed"]}
    assert len(changed_ids) == 8 and set(IDS) - changed_ids == {"AIME-1983-12"}
    changed = [r for r in main_trials if r["case_id"] in changed_ids]
    correct, changed_correct = sum(r["matched"] for r in main_trials), sum(r["matched"] for r in changed)
    broad = sum(r["posthoc_correct"] >= 3 for r in per if r["changed"])
    control = next(r["posthoc_correct"] for r in per if not r["changed"])
    fresh = [r for r in diagnostic if r["group"] == "hexagon-new"]
    repeats = [r for r in diagnostic if r["seed"] == 205]
    summary = {
        "updated_at_utc": now(), "posthoc": True, "solver_executed_during_resumption": False,
        "frozen_original_result": {"correct": 85, "runs": 130},
        "main": {**counts(main_trials), "planned": 45}, "changed8": {**counts(changed), "planned": 40},
        "diagnostic": {**counts(diagnostic), "planned": 7, "new_seeds": counts(fresh), "seed205_repeats": counts(repeats)},
        "all_completed": True, "completion_means": "All 52 start/end receipts exist; missing results remain failures.",
        "all_solver_outputs_preserved": all(r["solver_result_available"] for r in trials),
        "campaign_completion_file_present": (HERE / "campaign/completion.json").exists(),
        "prediction_sha256": fixed["prediction_sha256"], "prediction_lock_sha256": sha(HERE / "prediction.lock.json"),
        "score_sha256": sha(HERE / "score.py"), "locked_file_hashes_verified": len(fixed["files_sha256"]),
        "prediction_commit_verified": execution["prediction_commit"], "score_controls": controls,
        "rescored_records": len(trials), "available_answer_records_rescored": sum(r["solver_result_available"] for r in trials),
        "stored_match_agreement": all(r["stored_match_agrees"] for r in trials),
        "prediction_judgments": {"P1": correct >= 36, "P2": changed_correct >= 34, "P3": broad >= 7, "P4": control <= 2},
        "prediction_observations": {"P1": correct, "P2": changed_correct, "P3": broad, "P4": control},
        "p4_limitation": "All five control outputs are missing; numerical threshold only, not evidence of solver failure.",
        "timing": {
            "locked_at_utc": fixed["locked_at_utc"], "commit_gate_verified_at_utc": execution["verified_at_utc"],
            "campaign_started_at_utc": execution["started_at_utc"],
            "first_run_started_at_utc": min(r["started_at_utc"] for r in trials),
            "last_run_started_at_utc": max(r["started_at_utc"] for r in trials),
            "last_run_finished_at_utc": max(r["finished_at_utc"] for r in trials),
            "minimum_seconds_after_lock": min(r["seconds_after_prediction_lock"] for r in trials),
            "runs_before_or_at_lock": sum(not r["started_after_prediction_lock"] for r in trials),
            "all_starts_after_lock": all(r["started_after_prediction_lock"] for r in trials)}}
    assert summary["timing"]["all_starts_after_lock"]
    assert timestamp(fixed["locked_at_utc"]) < timestamp(execution["verified_at_utc"]) < timestamp(execution["started_at_utc"]) < timestamp(summary["timing"]["first_run_started_at_utc"])
    verdict = lambda name: "成立" if summary["prediction_judgments"][name] else "不成立"
    problem_rows = [
        f"| {r['case_id']} | {'出力のみ' if r['changed'] else '無変更'} | {r['q19_correct']}/5 | {r['posthoc_correct']}/5 | "
        f"{r['answer_records_available']}/5 | {r['output_record_missing']}/5 | {r['old_variables']}→{r['new_variables']} | {r['old_conditions']}→{r['new_conditions']} |"
        for r in per]
    diagnostic_rows = []
    for r in diagnostic:
        seconds = "—" if r["wall_seconds"] is None else f"{r['wall_seconds']:.3f}"
        saved = f"{r['answer_expressions']}→{r['converted_outputs']}（solved）" if r["solver_result_available"] else "不明（保存エラー）"
        diagnostic_rows.append(
            f"| {r['group']} | {r['seed']} | {'正答' if r['matched'] else '不正解計上'} | {saved} | {seconds} | "
            f"{r['receipt_elapsed_seconds']:.3f} | {utc_time(r['started_at_utc'])} |")
    start_rows = []
    for cid in IDS:
        rows = sorted((r for r in main_trials if r["case_id"] == cid), key=lambda r: r["seed"])
        start_rows.append("| " + cid + " | " + " | ".join(utc_time(r["started_at_utc"]) for r in rows) + " |")
    freeze_commit = "ca078d331a7ad69b20b996abe04b07f57616c337"
    commit_times = {commit: subprocess.check_output(
        ["git", "show", "-s", "--format=%cI", commit], cwd=ROOT, text=True).strip()
        for commit in (freeze_commit, execution["prediction_commit"])}
    for value in commit_times.values():
        assert timestamp(fixed["locked_at_utc"]) < timestamp(value) < timestamp(execution["verified_at_utc"])
    original_selected = sum(r["matched"] for cid in IDS for r in old[cid])
    original_changed = sum(r["matched"] for cid in changed_ids for r in old[cid])
    answer = f"""# Q29d：事後修正DSLの既存実行を再採点

**4基準：直感に反する＝否／深い理論が必要＝否／再現性と広がり＝不足／solverならでは＝否。Aの中心を担えるか：不可。**

**書き直し後の正答率は主解析{correct}/45（{100*correct/45:.1f}%）、変更8問は{changed_correct}/40（{100*changed_correct/40:.1f}%）。** 主解析の{summary['main']['output_record_missing']}件は結果保存エラーで解答が欠落し、固定規則どおり不正解に計上した。solver自体の正答率は確定できない。

**P1＝{verdict('P1')}、P2＝{verdict('P2')}、P3＝{verdict('P3')}、P4＝{verdict('P4')}（数値上のみ）。** P4の1983-12は全5件が欠落しており、探索失敗の裏付けにはならない。

**本件はQ19の失敗を見た後の事後修正であり、凍結版・元DSLの85/130（65.4%）は変更しない。** 未使用群に対する元の予測が復活したとは扱わない。今回の再開ではsolverを一度も実行せず、既存52記録だけを採点した。

主解析45件・原因調査7件には全て開始・終了時刻がある。ただし保存された解答記述子は計21件（主解析20件、原因調査1件）で、残る31件は `AssertionError: summary unexpectedly large` のエラー記録だけである。`campaign/completion.json` は存在しないため、キャンペーン終了処理の成功までは主張しない。

**問題別結果（主解析45件）**

| 問題 | 変更 | Q19 | 今回の正答/5 | 解答記録あり | 保存欠落 | 変数数 | 条件数 |
|---|---|---:|---:|---:|---:|---:|---:|
{chr(10).join(problem_rows)}

対象9問はQ19の{original_selected}/45から今回{correct}/45、変更8問は{original_changed}/40から{changed_correct}/40。変更{broad}/8問で各5/5の正答を確認した。seedはQ19の201〜205と今回の206〜210で異なり、同seedの対照実験ではない。保存欠落の偏りもあるため、書き直しの因果効果や全問題への広がりは推定しない。

**固定予測の判定**（欠落・異常終了を不正解とする規則を含む）

| 予測 | 固定点予測・主観的約90%区間 | 固定閾値 | 観測 | 判定 |
|---|---|---|---|---|
| P1 | 37/45・32〜40/45 | 36/45以上 | {correct}/45 | {verdict('P1')} |
| P2 | 37/40・32〜40/40 | 34/40以上 | {changed_correct}/40 | {verdict('P2')} |
| P3 | 8/8問・6〜8/8問 | 変更8問中7問以上が3/5以上成功 | {broad}/8問 | {verdict('P3')} |
| P4 | 0/5・0〜2/5 | 1983-12が2/5以下 | {control}/5（全5件欠落） | {verdict('P4')}（数値上のみ） |

P1〜P3は予測区間も下回った。P4は欠落を不正解に数えた結果で、本質的整数条件の難しさを再確認したとは言えない。これらの区間は固定済みの主観的予測区間であり、独立Bernoulli試行の信頼区間ではない。

**AIME-1991-14：元DSLの原因調査7実行（主解析には合算しない）**

Q19は4/5成功（seed201〜204）。seed205だけが答えなしで、133.668秒、`numeric_feasible=False`、既存採点の段階ラベルは `final_verification` だった。

| 群 | seed | 今回の採点 | 保存されたsolver結果 | solver秒 | 記録の開始→終了の秒 | 開始UTC（2026-10-23） |
|---|---:|---|---|---:|---:|---|
{chr(10).join(diagnostic_rows)}

新seedは{sum(r['matched'] for r in fresh)}/5、seed205の2反復は{sum(r['matched'] for r in repeats)}/2、別枠合計は{sum(r['matched'] for r in diagnostic)}/7。新seedの予測4/5（区間2〜5/5）を下回るが、6件のsolver成否が保存されていない。seed205の2件も保存エラーであり、「少なくとも1回探索に失敗する」という機構上の予測は検証不能。同seedでの失敗再現、乱数・共有機負荷・停止条件のどれが元の1失敗を生んだかは断定できない。

既存の正解図検算では24凸性条件・5辺長・3共円条件を満たすtarget=384の配置が通過している。今回もseed208の正答は確認できるので、入力矛盾という説明は支持されない。有限予算の探索・精製が原因という固定時の仮説は、今回の欠落した6件からは検証できない。開始→終了の秒数は保存・採点処理を含む記録区間であり、欠落したsolver実行時間の代用にはしない。

**lockと各実行の時刻順序**

全て2026-10-23 UTC。ファイル更新時刻ではなく、`prediction.lock.json`、`campaign/execution-manifest.json` と各実行JSONの記録を比較した。

| 出来事 | UTC |
|---|---|
| 予測lock | {utc_time(fixed['locked_at_utc'])}Z |
| 固定ファイルを含むcommit ca078d3のcommitter時刻 | {utc_time(commit_times[freeze_commit])}Z |
| 実行manifest記載commit 73165f4のcommitter時刻 | {utc_time(commit_times[execution['prediction_commit']])}Z |
| commit/hash照合完了の記録 | {utc_time(execution['verified_at_utc'])}Z |
| campaign開始記録 | {utc_time(execution['started_at_utc'])}Z |
| 最初の実行開始 | {utc_time(summary['timing']['first_run_started_at_utc'])}Z |
| 最後の実行開始 | {utc_time(summary['timing']['last_run_started_at_utc'])}Z |
| 最後の実行終了記録 | {utc_time(summary['timing']['last_run_finished_at_utc'])}Z |

**52/52件がlock後に開始。最初の開始もlockの{summary['timing']['minimum_seconds_after_lock']:.6f}秒後。** lock前・同時刻の開始は0件。主解析45件の個別開始時刻を以下に示す（全てUTC、末尾Zを省略）。原因調査7件の開始は上の原因調査表に記載した。

| 問題 | seed206 | seed207 | seed208 | seed209 | seed210 |
|---|---|---|---|---|---|
{chr(10).join(start_rows)}

`results.csv` には全52件の完全な開始・終了時刻、開始順 `start_order`、lockとの差秒、`started_after_prediction_lock` と元記録のパス・SHA-256を保存した。これらはランナーが `_run_one` を呼ぶ直前と終了後に付けた時刻で、solverプロセス内部の独立時計ではない。保存ログが示す範囲では事前固定の順序は守られているが、Q19を見た後の事後修正である点は変わらない。

**書き直し・採点・保存の監査**

8問は固定規則に従う出力形式だけの変更。AIME-1983-12はtargetが既に直径で、整数a,bと有理性証人p,qは問題の本質なので元DSLとバイト単位で同一。分母45に残した。差分は `diff/` と `rewrite-manifest.json` に保存済み。

保存済み `witness-validation.json` では、書き直し9問の正解図が全条件と凍結版hard-feasibilityを通過し、最大等式残差は約4.6e-100以下。これは1配置の検算で、全解の一意性・全枝の網羅証明ではない。AIME-1996-15の元targetの床演算は凍結HP評価器でTypeErrorという既知所見がある。今回の5件は保存欠落なので、書き直し後にこの問題が解けたかは確認できない。

固定 `score.py`（SHA-256 `{sha(HERE / 'score.py')}`）の `assess` を全52記録に適用した。解答記録のある21件は保存された厳密記述子を使い、status・時間等は同じ記録のassessmentから復元した。幾何量の厳密集合と採点側で形式変換した公式答を再比較し、保存済み判定と全件一致した。31件は解答データなしの入力として `artifact_missing`・不正解になる。これは完全な生データの復元ではない。

欠落を「solverが答えを返さなかった」とは読み替えない。`results.csv` の `status=runner_error` は保存時の状態、`scoring_status=artifact_missing` は再採点時の状態である。欠落行の `n_answers`・solver秒・実行hashは空欄とし、`score_n_answers=0` は採点入力に残った答え数だけを表す。`per-problem.csv` の `no_answer` は解答記録で確認できた0答、`output_record_missing` は保存欠落である。`posthoc_completed` は終了記録の件数を示す。

保存エラーは `run_campaign.py` の `write_summary` が90,000 byte未満の要約を要求するassertで発生した。`research_runner._run_one` はその書込み呼出しより前に一時solver結果を削除するため、この31件の記録には答え・プロセス情報が残っていない。全件を維持し、再実行や成功例への置換はしていない。

凍結srcは `60db4b679b04167175c51c479c87c22fa663fda0`、source hashは `{fixed['source_hash']}`。manifest/preflightは180秒・1コア・BLAS各1thread・最大4並列を記録している。個別の実行hash・CPU・契約情報まで再照合できるのは保存された21件で、欠落31件には個別証跡がない。

予測本文SHA-256は `{fixed['prediction_sha256']}`、lockのSHA-256は `{sha(HERE / 'prediction.lock.json')}`。lockが列挙する{len(fixed['files_sha256'])}ファイル全てと、実行manifest記載commit `{execution['prediction_commit']}` の内容が一致した。再開中は予測・lock・規則・DSL・score.py・実行記録・元DSL・Q19採点を変更していない。固定済み変換の参照値10件・余分な解10件・同じm+nになる誤答1件の検査も通過した。

`revisions/pre-execution-v1/` のランナー補正記録は14:50:30.922405Zで、最新lockと全開始より前。ただし、要約サイズ保存の不具合は今回31件に残った。今回変更したのは事後集計用 `summarize.py` と集計出力だけである。封印tar・封印生データにはアクセスせず、各出力ファイルは5MB未満に制限した。

再採点の実行コマンド（solver起動なし）：

~~~sh
env PYTHONDONTWRITEBYTECODE=1 /home/kabatan/work/solver/.venv/bin/python -B jssa/difficulty/unseen-1983/failure-audit/d/summarize.py
~~~
"""
    verify_inputs(fixed, execution)
    assert all(sha(path) == digest for path, digest in receipt_hashes.items())
    dump_csv(HERE / "results.csv", trials)
    dump_csv(HERE / "per-problem.csv", per)
    write_small(HERE / "summary.json", json.dumps(summary, ensure_ascii=False, indent=2) + "\n")
    write_small(HERE / "answer.md", answer)
    print(json.dumps({key: summary[key] for key in ("main", "changed8", "diagnostic", "prediction_judgments", "timing")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
