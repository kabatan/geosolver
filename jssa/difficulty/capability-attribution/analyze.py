"""Aggregate saved tables only. No solver imports, optimization, or network.

Outputs are restricted to this directory; each file must remain below 5 MB.
"""
from pathlib import Path
from collections import Counter, defaultdict
import csv
import hashlib
import json
import statistics
import subprocess

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[2]
SOURCES = {}


def source(path):
    p = ROOT / path
    assert p.stat().st_size < 5_000_000, path
    digest = hashlib.sha256()
    with p.open("rb") as handle:
        for block in iter(lambda: handle.read(65536), b""):
            digest.update(block)
    SOURCES[path] = {"bytes": p.stat().st_size, "sha256": digest.hexdigest()}
    return p


def table(path):
    p = source(path)
    with p.open(newline="") as handle:
        return list(csv.DictReader(handle))


def saved_json(path):
    p = source(path)
    # Only the selected cases' small files, never a bulk campaign log.
    assert p.stat().st_size < 1_000_000, path
    with p.open() as handle:
        return json.load(handle)


def write_json(name, value):
    data = json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
    assert len(data.encode()) < 5_000_000
    (OUT / name).write_text(data)


def truth(value):
    assert value in ("True", "False", "true", "false", "1", "0"), value
    return value in ("True", "true", "1")


def write_csv(name, rows):
    with (OUT / name).open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    assert (OUT / name).stat().st_size < 5_000_000


def access_audit():
    ref = "refs/remotes/origin/claude/project-thread-nycxfb"
    repositories = []
    for directory in [ROOT, Path("/home/kabatan/work/solver"), Path("/home/kabatan/work/geosolver")]:
        command = ["git", "-C", str(directory), "show-ref", "--verify", ref]
        result = subprocess.run(command, capture_output=True, text=True, timeout=20)
        repositories.append({"repository": str(directory), "command": command,
                             "exit_code": result.returncode, "stdout": result.stdout[:2000],
                             "stderr": result.stderr[:2000]})
    result = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, timeout=20, check=True)
    frozen_paths = [
        "src/geosolver/engine/standard/search/scipy_multistart_backend.py",
        "src/geosolver/engine/standard/search/nomad_blackbox_adapter.py",
        "src/geosolver/engine/standard/search/nomad_backend.py",
        "src/geosolver/engine/standard/search/nomad_config.py",
        "src/geosolver/engine/standard/search/select_search_start_points.py",
        "src/geosolver/engine/standard/contracts/baseline_search_policy.py",
        "src/geosolver/engine/standard/contracts/external_pipeline_config.py",
        "src/geosolver/engine/standard/orchestration/run_external_pipeline.py",
        "src/geosolver/engine/standard/orchestration/run_search.py",
        "src/geosolver/engine/standard/search/scale_chart.py",
        "src/geosolver/engine/standard/refinement/analytic_jacobian.py",
    ]
    hashes = subprocess.run(["git", "rev-parse", *["60db4b6:" + p for p in frozen_paths]],
                            cwd=ROOT, capture_output=True, text=True, timeout=20, check=True)
    write_json("access-audit.json", {
        "workspace_head": result.stdout.strip(), "requested_ref": ref,
        "repositories_checked": repositories,
        "requested_ref_available": any(r["exit_code"] == 0 for r in repositories),
        "frozen_code_blobs": dict(zip(frozen_paths, hashes.stdout.splitlines(), strict=True)),
        "additional_checks": [
            "workspace: git ls-tree -r --name-only origin/claude/project-thread-nycxfb jssa/results failed: Not a valid object name",
            "workspace and /home/kabatan/work/solver: git log --all -- jssa/results/ablation-20261022 returned no entries",
            "available workspace remote refs fos2rk and ulho54: no ablation/stage-profile/mechanism result paths",
            "bounded local artifact-directory search found no ablation result directory",
            "/mnt/c/geosolver and /home/kabatan/work/jssa-searchmode (paths recorded in old aggregation scripts) unavailable",
        ],
        "scope": "No network, fetch, solver, or optimization. Missing raw data is not proof that an experiment was never performed.",
    })


def main():
    fp = "jssa/strategy/astra-consult-18/Q27f/selected-case-validation.csv"
    dp = "jssa/strategy/astra-consult-18/Q27d/census-both-seeds.csv"
    ap = "jssa/results/mechanism-attribution/attribution.csv"
    sp = "jssa/results/stage-profile-20261023/per-case.csv"
    mp = "jssa/results/search-mode-ablation/per-run.csv"
    tp = "jssa/results/tangency-signed/per-case.csv"
    f = {r["id"]: r for r in table(fp) if truth(r["p2_qualifies"])}
    census = {r["id"]: r for r in table(dp)}
    d = {k: r for k, r in census.items() if int(r["d"]) in (6, 7)}
    attr = table(ap)
    stages = {(r["case_id"], r["seed"]): r for r in table(sp)}
    modes = {(r["case_id"], r["search_mode"]): r for r in table(mp)}
    tangency = {(r["case_id"], r["order"]): r for r in table(tp)}
    assert len(f) == 21 and len(d) == 29
    assert len(attr) == len(stages) == 969
    assert sum(truth(r["matched"]) for r in attr) == 953
    assert len(modes) == 969
    assert len({(r["case_id"], r["seed"]) for r in attr}) == 969
    assert all(truth(r["matched"]) == truth(stages[r["case_id"], r["seed"]]["correct"]) for r in attr)
    assert all(r["answer_source_stage"] == stages[r["case_id"], r["seed"]]["final_answer_source"] for r in attr)
    assert all(r["search_mode"] == r["recorded_mode"] for r in modes.values())
    runs = defaultdict(list)
    for r in attr:
        runs[r["case_id"]].append(r)
    rows, run_rows, component_rows, local_rows = [], [], [], []
    component_names = {
        "algebraic_preprocessing": "代数的前処理",
        "nomad_stage1": "NOMAD（第1探索）",
        "second_search": "第2探索",
        "scale_chart": "尺度の座標",
        "rescue": "rescue",
        "analytic_jacobian": "解析ヤコビアン",
        "signed_tangency_residual": "接条件の符号付き残差",
    }
    for cid in sorted(f.keys() | d.keys()):
        c = census[cid]
        rr = sorted(runs[cid], key=lambda r: int(r["seed"]))
        assert len(rr) == 3 and all(truth(r["matched"]) for r in rr)
        if cid in f:
            assert int(c["n"]) == int(f[cid]["starts0"])
            assert int(c["n1"]) == int(f[cid]["starts1"])
        row = dict(problem_id=cid, cohort=";".join(g for g, ids in [("Q27f", f), ("Q27d", d)] if cid in ids),
                   n_vars=int(c["d"]), local_hits0=int(c["h"]), local_starts0=int(c["n"]),
                   local_hits1=int(c["h1"]), local_starts1=int(c["n1"]),
                   local_p0=float(c["p"]), local_p1=float(c["p1"]), full_correct=3, full_runs=3)
        raws = []
        for seed, folder in [(0, "raw-323"), (1, "raw-323-seed1")]:
            path = f"jssa/difficulty/minima/{folder}/{cid}.json"
            raw = saved_json(path)
            counts = Counter(r["cls"] for r in raw["records"])
            assert dict(counts) == raw["counts"], path
            assert raw["case_id"] == cid and raw["seed"] == seed
            assert len(raw["records"]) == row[f"local_starts{seed}"]
            assert counts["hit"] == row[f"local_hits{seed}"]
            assert raw["starts_requested"] == 200 and raw["init_from"] is None
            assert raw["n_vars"] == row["n_vars"]
            raws.append(raw)
            local_rows.append(dict(problem_id=cid, cohort=row["cohort"], seed=seed,
                                   starts=len(raw["records"]), hits=counts["hit"],
                                   stuck=counts["stuck"], left_box=counts["left_box"],
                                   wrong_branch=counts["wrong_branch"], wrong_answer=counts["wrong_answer"],
                                   error=counts["error"], no_candidate=counts["no_candidate"],
                                   n_vars=raw["n_vars"], n_constraints=raw["n_constraints"],
                                   local_method="Powell" if raw["n_vars"] > raw["n_constraints"] else "LM",
                                   saved_nfev=sum(r["nfev"] for r in raw["records"]),
                                   elapsed_s=raw["elapsed"], box=json.dumps(raw["box"], separators=(",", ":")),
                                   source=path))
        assert raws[0]["box"] == raws[1]["box"]
        assert raws[0]["references"] == raws[1]["references"]
        row["local_method"] = "Powell" if raws[0]["n_vars"] > raws[0]["n_constraints"] else "LM"
        for r in rr:
            seed = r["seed"]
            row[f"answer_source_seed{seed}"] = r["answer_source_uid_prefix"]
            row[f"second_search_triggered_seed{seed}"] = r["second_attempt_triggered"]
            row[f"second_search_selected_seed{seed}"] = r["second_attempt_selected"]
            run_rows.append({"cohort": row["cohort"], **r,
                             "stage_candidates_sent": stages[cid, seed]["candidates_sent_to_refinement"],
                             "stage_candidates_converged": stages[cid, seed]["candidates_converged"],
                             "stage_candidates_rejected_false": stages[cid, seed]["candidates_rejected_as_false"],
                             "stage_candidates_accepted": stages[cid, seed]["candidates_accepted"],
                             "evidence": ap + ";" + sp})
        for mode in ("disco_mads", "mads", "scipy_multistart"):
            r = modes[cid, mode]
            row[f"second_off_{mode}_correct_seed0"] = truth(r["solved"])
            row[f"second_off_{mode}_status_seed0"] = r["status"]
            row[f"second_off_{mode}_wall_s"] = float(r["wall_seconds"])
            row[f"second_off_{mode}_evaluations"] = int(r["evaluation_count"])
        disco = row["second_off_disco_mads_correct_seed0"]
        scipy = row["second_off_scipy_multistart_correct_seed0"]
        row["second_search_cross_campaign_loss_seed0"] = not disco
        row["nomad_replacement_loss_given_second_off_seed0"] = disco and not scipy
        row["nomad_replacement_gain_given_second_off_seed0"] = not disco and scipy
        tr = tangency.get((cid, "off_first"))
        row["signed_rewrite_stage_measured"] = tr is not None
        for key in ("n_candidates", "with_best_digits", "without_best_digits", "with_converged", "without_converged"):
            row["signed_rewrite_" + key] = tr[key] if tr is not None else "未測定"
        row["source_varies_across_seeds"] = len({r["answer_source_uid_prefix"] for r in rr}) > 1
        classes = []
        if not disco:
            classes.append("第2探索除去で失敗（別計測seed0）")
        if disco and not scipy:
            classes.append("第2探索off下のNOMAD置換で失敗（seed0）")
        if tr:
            assert tr["status"] == "ok"
            other = tangency[cid, "on_first"]
            for key in ("with_best_digits", "without_best_digits", "with_converged", "without_converged"):
                assert tr[key] == other[key], (cid, key)
            classes.append("残差書換えで精密化改善（最終成否未測定）")
            if not disco:
                classes.append("探索と精密化の複数段階で効果（相互作用未測定）")
        if row["source_varies_across_seeds"]:
            classes.append("採用経路がseed間で変化（必要性ではない）")
        row["classification"] = ";".join(classes) or "読めた比較で喪失なし・他部品の原票未取得"
        for part, name in component_names.items():
            status = "原票未取得（未測定かは断定不可）"
            result = "未判定"
            scope = "完成solverの単独除去。指定ブランチの1/3 seed原票なし"
            evidence = "jssa/draft/supplement-v10.md:S2.2"
            baseline, altered, seeds = "", "", ""
            caveat = "採用元や全323問の集計から問題別の必要性は推論しない"
            if part == "nomad_stage1":
                status = "条件付き測定"
                baseline, altered, seeds = int(disco), int(scipy), "0"
                result = "失敗に変化" if disco and not scipy else "成功に変化" if not disco and scipy else "両方成功" if disco else "両方失敗"
                scope = "第2探索off・rescue有効で、第1探索DiscoMADSをSciPyへ置換"
                evidence = mp
                caveat = "第2探索onの完成solverでの単独除去は未照合。rescueのNOMADは残る"
            elif part == "second_search":
                status = "別計測間の1 seed比較"
                baseline, altered, seeds = 1, int(disco), "0"
                result = "失敗に変化" if not disco else "両方成功"
                scope = "本計測seed0と第2探索off・DiscoMADSの比較"
                evidence = ap + ";" + mp
                caveat = "本計測6並列・除去側4並列の別キャンペーン。3 seed除去原票は未取得"
            elif part == "signed_tangency_residual":
                scope = "同一候補の精密化で接条件・距離0・半径補助式の書換えを一括off"
                evidence = tp
                caveat = "接条件だけの単独除去でも完成solverの最終正答比較でもない"
                if tr:
                    status = "精密化のみ測定"
                    result = "精度低下・最終正答の成否は未測定"
                    baseline, altered, seeds = tr["with_best_digits"], tr["without_best_digits"], "0（2順序）"
                else:
                    status = "未測定（保存された12問に対象なし）"
                    result = "未測定"
            row[f"without_{part}"] = status + "：" + result
            component_rows.append(dict(problem_id=cid, cohort=row["cohort"], component=part,
                                       component_ja=name, measurement_status=status, removal_result=result,
                                       measured_scope=scope, seeds=seeds, baseline_metric=baseline,
                                       altered_metric=altered, metric="best_residual_digits" if part == "signed_tangency_residual" else "answer_correct",
                                       evidence=evidence, limitation=caveat))
        row["evidence"] = ";".join([dp, ap, sp, mp] + ([fp] if cid in f else []) + ([tp] if tr else []))
        rows.append(row)
    write_csv("per-problem.csv", rows)
    write_csv("per-component.csv", component_rows)
    write_csv("per-run.csv", run_rows)
    write_csv("local-probe.csv", local_rows)
    summary = {"status": "existing_data_only_missing_requested_branch", "cohort_overlap": sorted(f.keys() & d.keys()), "unique_problems": len(rows), "cohorts": {}}
    for group, ids in [("Q27f", f), ("Q27d", d), ("union", f.keys() | d.keys())]:
        subset = [r for r in rows if r["problem_id"] in ids]
        ar = [r for r in attr if r["case_id"] in ids]
        lr = [r for r in local_rows if r["problem_id"] in ids]
        summary["cohorts"][group] = {
            "problems": len(subset), "full_correct": sum(r["full_correct"] for r in subset),
            "full_runs": 3 * len(subset),
            "local_hits": sum(r["local_hits0"] + r["local_hits1"] for r in subset),
            "local_starts": sum(r["local_starts0"] + r["local_starts1"] for r in subset),
            "local_problem_mean_p0": statistics.mean(r["local_p0"] for r in subset),
            "local_problem_mean_p1": statistics.mean(r["local_p1"] for r in subset),
            "answer_sources": dict(Counter(r[f"answer_source_seed{i}"] for r in subset for i in range(3))),
            "answer_sources_by_attempt": dict(Counter(r["answer_source_uid_prefix"] + "/" + r["second_attempt_selected"] for r in ar)),
            "second_search_selected_runs": sum(r["second_attempt_selected"] == "fallback" for r in ar),
            "second_search_selected_problems": sorted({r["case_id"] for r in ar if r["second_attempt_selected"] == "fallback"}),
            "rescue_source_problems": sorted({r["case_id"] for r in ar if r["answer_source_uid_prefix"] == "rescue/nomad"}),
            "source_varies_problems": [r["problem_id"] for r in subset if r["source_varies_across_seeds"]],
            "local_methods": dict(Counter(r["local_method"] for r in subset)),
            "local_outcomes": {k: sum(r[k] for r in lr) for k in ("hits", "stuck", "left_box", "wrong_branch", "wrong_answer", "error", "no_candidate")},
            "search_mode_comparison": {},
            "second_search_cross_campaign_losses": [r["problem_id"] for r in subset if r["second_search_cross_campaign_loss_seed0"]],
            "nomad_replacement_losses_second_off": [r["problem_id"] for r in subset if r["nomad_replacement_loss_given_second_off_seed0"]],
            "nomad_replacement_gains_second_off": [r["problem_id"] for r in subset if r["nomad_replacement_gain_given_second_off_seed0"]],
            "signed_rewrite_measured_problems": [r["problem_id"] for r in subset if r["signed_rewrite_stage_measured"]],
        }
        for mode in ("disco_mads", "mads", "scipy_multistart"):
            summary["cohorts"][group]["search_mode_comparison"][mode] = {
                "correct": sum(r[f"second_off_{mode}_correct_seed0"] for r in subset),
                "runs": len(subset),
                "wall_s_median": statistics.median(r[f"second_off_{mode}_wall_s"] for r in subset),
                "evaluations_median": statistics.median(r[f"second_off_{mode}_evaluations"] for r in subset),
            }
    assert summary["cohorts"]["Q27f"]["local_starts"] == 6971
    assert summary["cohorts"]["Q27f"]["local_hits"] == 0
    assert summary["cohorts"]["union"]["full_runs"] == 129
    assert len(component_rows) == 43 * 7
    for path in ["jssa/strategy/codex-tasks-1023.md", "jssa/strategy/astra-consult-18/Q27f/answer.md",
                 "jssa/strategy/astra-consult-18/Q27d/answer.md", "jssa/results/search-mode-ablation/README.md",
                 "jssa/results/tangency-signed/README.md", "jssa/results/mechanism-attribution/README.md",
                 "jssa/results/stage-profile-20261023/per-case-README.md", "jssa/draft/supplement-v10.md",
                 "jssa/difficulty/probe_basins.py"]:
        source(path)
    write_json("summary.json", summary)
    write_json("sources.json", SOURCES)
    access_audit()
    print(json.dumps({"unique_problems": len(rows), "component_rows": len(component_rows),
                      "sources": len(SOURCES), "union": summary["cohorts"]["union"]}, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
