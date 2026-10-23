"""Q37段階1: 保存ファイルの集計と選択のみ。solverのimport・起動はしない。"""
from __future__ import annotations

import csv
import gzip
import hashlib
import io
import itertools
import json
from pathlib import Path
import re
import subprocess


ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
FROZEN = "60db4b679b04167175c51c479c87c22fa663fda0"
SEEDS = [370101, 370201, 370301]
BUDGETS = [180, 360, 900]
SOURCES: dict[str, dict] = {}


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def read(relative: str) -> bytes:
    path = Path(relative)
    assert "sealed" not in path.parts
    data = (ROOT / path).read_bytes()
    SOURCES[relative] = {"sha256": sha(data), "bytes": len(data)}
    return data


def read_json(relative: str):
    return json.loads(read(relative))


def read_csv(relative: str) -> list[dict]:
    return list(csv.DictReader(io.StringIO(read(relative).decode())))


def write(name: str, data: bytes) -> None:
    assert len(data) < 4_900_000, name
    (OUT / name).write_bytes(data)


def write_json(name: str, value) -> None:
    write(name, (json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode())


def write_csv(name: str, rows: list[dict]) -> None:
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    write(name, stream.getvalue().encode())


def git(*args: str) -> bytes:
    return subprocess.check_output(["git", *args], cwd=ROOT, timeout=30)


def main() -> None:
    if (OUT / "prediction.md").exists() or (OUT / "prediction.lock.json").exists():
        raise SystemExit("予測固定後の再生成は禁止。元の固定成果物を保持する。")
    assert not git("diff", "--name-only", FROZEN, "--", "src").strip()
    instruction_commit = git("rev-parse", "4bc0f9b").decode().strip()
    instruction_source = git("show", f"{instruction_commit}:jssa/strategy/codex-tasks-1023.md")
    section = instruction_source.decode().split("### Q37", 1)[1].split("### Q38", 1)[0]
    write("q37-source.md", (f"出典: ローカルGit {instruction_commit}:jssa/strategy/codex-tasks-1023.md\n\n### Q37" + section).encode())
    read("jssa/strategy/codex-tasks-1023.md")

    product_root = ROOT / "src/geosolver"
    digest = hashlib.sha256()
    for path in sorted(product_root.rglob("*")):
        rel = path.relative_to(product_root)
        if (not path.is_file() or path.suffix not in {".py", ".json", ".toml"}
                or path.name == "engine-lock.json" or {"__pycache__", "frontend"} & set(rel.parts)):
            continue
        digest.update(rel.as_posix().encode() + b"\0")
        digest.update(path.read_bytes().replace(b"\r\n", b"\n") + b"\0")
    source_hash = "sha256:" + digest.hexdigest()
    assert source_hash == read_json("src/geosolver/engine-lock.json")["source_tree_hash"]

    main_rows = read_csv("jssa/results/mechanism-attribution/attribution.csv")
    profile_rows = read_csv("jssa/results/stage-profile-20261023/per-case.csv")
    baseline = {(r["case_id"], int(r["seed"])): r for r in main_rows}
    assert len(main_rows) == len(profile_rows) == len(baseline) == 969
    assert all(baseline[(r["case_id"], int(r["seed"]))]["matched"] == r["correct"] for r in profile_rows)
    by_id: dict[str, list[dict]] = {}
    for row in main_rows:
        by_id.setdefault(row["case_id"], []).append(row)
    cases = {r["id"]: r for r in map(json.loads, read("benchmarks/cases.jsonl").decode().splitlines())}
    nvars = {r["id"]: r["n_vars"] for r in read_csv("jssa/difficulty/minima/basins-323.csv")}
    assert len(by_id) == len(cases) == 323 and set(by_id) == set(cases)
    assert all(sorted(int(r["seed"]) for r in rows) == [0, 1, 2] for rows in by_id.values())

    def correct(cid):
        return sum(r["matched"] == "True" for r in by_id[cid])

    def late(cid):
        return any(r["second_attempt_triggered"] == "True" or r["rescue_triggered"] == "True" for r in by_id[cid])

    def maximum(cid):
        return max(float(r["wall_s"]) for r in by_id[cid])

    a = sorted(cid for cid in by_id if correct(cid) < 3)
    b_pool = sorted((cid for cid in by_id if correct(cid) == 3 and late(cid)), key=lambda cid: (-maximum(cid), cid))
    c_pool = sorted((cid for cid in by_id if correct(cid) == 3 and not late(cid)), key=lambda cid: (-maximum(cid), cid))
    assert len(a) == 10 and len(b_pool) >= 10 and len(c_pool) >= 20
    b, c = b_pool[:10], c_pool[:10]
    d_pool = [cid for cid in c_pool if cid not in c]
    d = sorted(d_pool, key=lambda cid: (sha(("Q37-control-v1\n" + cid).encode()), cid))[:10]
    selected = [(group, cid) for group, ids in [("A", a), ("B", b), ("C", c), ("D", d)] for cid in ids]
    assert len(selected) == len({cid for _, cid in selected}) == 40
    selection = []
    for ordinal, (group, cid) in enumerate(selected):
        record = cases[cid]
        path = (Path("benchmarks") / record["dsl_path"]).as_posix()
        dsl_bytes = read(path)
        assert json.loads(dsl_bytes) == record["dsl"]
        references = record["answer"] if isinstance(record["answer"], list) else [record["answer"]]
        canonical_references = json.dumps([str(v) for v in references], ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        selection.append({
            "ordinal": ordinal, "stratum": group, "id": cid, "n_vars": nvars[cid],
            "correct_of_3": correct(cid), "max_wall_seconds": maximum(cid),
            "fallback_runs": sum(r["second_attempt_triggered"] == "True" for r in by_id[cid]),
            "rescue_runs": sum(r["rescue_triggered"] == "True" for r in by_id[cid]),
            "control_order_sha256": sha(("Q37-control-v1\n" + cid).encode()),
            "dsl_path": path, "dsl_sha256": sha(dsl_bytes),
            "reference_sha256": sha(canonical_references.encode()),
        })
    write_csv("selection.csv", selection)
    write("selected-problems.txt", ("\n".join(cid for _, cid in selected) + "\n").encode())
    permutations = list(itertools.permutations(BUDGETS))
    jobs = []
    lane_order = [0, 0, 0, 0]
    for ordinal, (group, cid) in enumerate(selected):
        lane = ordinal % 4
        for seed_index, seed in enumerate(SEEDS):
            for within_triplet, budget in enumerate(permutations[(3 * ordinal + seed_index) % 6]):
                lane_order[lane] += 1
                jobs.append({"lane": lane, "lane_order": lane_order[lane], "id": cid,
                             "stratum": group, "seed": seed, "time_limit_seconds": budget,
                             "within_triplet": within_triplet,
                             "campaign_relative": f"campaign/t{budget}/s{seed}",
                             "cores": 1, "outer_watchdog_seconds": budget + 8})
    assert len(jobs) == len({(r["id"], r["seed"], r["time_limit_seconds"]) for r in jobs}) == 360
    assert lane_order == [90] * 4
    write_csv("jobs.csv", jobs)

    q19_path = "jssa/difficulty/unseen-1983/prereg/q19-scored/assessment.jsonl"
    q19 = [json.loads(line) for line in read(q19_path).decode().splitlines()]
    target = [r for r in q19 if r["in_target"]]
    assert len(target) == 130 and sum(r["matched"] for r in target) == 85
    q19_map = {(r["case_id"], r["seed"]): r for r in target}
    q29_base = "jssa/difficulty/unseen-1983/failure-audit"
    a_plan = read_json(f"{q29_base}/a/experiment-plan.json")
    b_manifest = read_json(f"{q29_base}/b/manifest.json")
    assert a_plan["identity"]["assessment_sha256"] == sha(read(q19_path))
    assert b_manifest["sources"][q19_path] == sha(read(q19_path))
    for cid, expected in a_plan["identity"]["input_sha256"].items():
        assert sha(read(f"jssa/difficulty/unseen-1983/dsl/{cid}.json")) == expected
    for path, expected in b_manifest["sources"].items():
        if "/dsl/" in path:
            assert sha(read(path)) == expected
    a_labels = {r["id"]: r for r in read_csv(f"{q29_base}/a/runs.csv") if r["experiment"] == "posthoc_original_DSL_900s"}
    b_labels = {r["id"]: r for r in read_csv(f"{q29_base}/b/runs.csv") if r["group"] == "new_public_API"}
    pairs = []
    tasks = [(t["id"], t["seed"], f"{q29_base}/a/global-900/{t['id']}-seed-{t['seed']}.json", "a") for t in a_plan["global_tasks"]]
    tasks += [(cid, 201, f"{q29_base}/b/runs/natural-900-{cid}.json", "b") for cid in sorted(b_labels)]
    for cid, seed, path, group in tasks:
        obj = read_json(path)
        result = obj.get("solver_result", obj)
        assert result["engine"]["source_hash"] == source_hash
        assert result["requested_resources"] == {"time_limit_seconds": 900.0, "cores": 1, "seed": seed}
        prior = q19_map[(cid, seed)]
        normal = result["status"] in {"solved", "no_answer_found"}
        if group == "a":
            outcome = a_labels[cid]["correct"] == "True"
        else:
            # 保存済みQ29bのラベルを転記。新しい採点器は使用しない。
            outcome = b_labels[cid]["status"] == "solved"
        if result["status"] == "solved":
            # 既存の2件の成功を、保存された整数の完全なdescriptorでも確認。
            ref = str(prior["reference"])
            assert len(result["answers"]) == 1
            value = result["answers"][0]["value"]
            assert value["minimal_polynomial"] == ["1", str(-int(ref))]
            assert value["real_root_index"] == 0
        diag = result.get("diagnostics") or {}
        summary = diag.get("pipeline_summary") or {}
        pairs.append({"id": cid, "seed": seed, "correct_180": prior["matched"],
                      "correct_900_existing_audit": outcome if normal else "",
                      "comparison": ("gain" if outcome else "same_failure") if normal else "infrastructure_unknown",
                      "status_900": result["status"], "elapsed_900": result["elapsed_seconds"],
                      "search_seconds_900": diag.get("phase_timings", {}).get("search", ""),
                      "fallback_triggered_900": summary.get("search_staged_fallback", {}).get("triggered", ""),
                      "selected_stage_900": summary.get("search_staged_fallback", {}).get("selected_stage", ""),
                      "source_180": q19_path, "source_900": path})
    assert all(not r["correct_180"] for r in pairs)
    assert [sum(r["comparison"] == c for r in pairs) for c in ["gain", "same_failure", "infrastructure_unknown"]] == [2, 7, 1]
    write_csv("existing-pairs.csv", pairs)

    role = [r for r in read_csv("jssa/difficulty/role-reassign/per-run.csv") if r["mode"] == "B"]
    assert len(role) == 323
    discordances = [{"id": r["id"], "seed": int(r["seed"]),
                    "main_180_correct": baseline[(r["id"], int(r["seed"]))]["matched"],
                    "role_B_180_correct": r["matched"], "role_B_status": r["status"]}
                   for r in role if r["matched"] != baseline[(r["id"], int(r["seed"]))]["matched"]]
    write_csv("same-budget-discordances.csv", discordances)
    smoke = [json.loads(line) for line in read("jssa/difficulty/full-solver-redraw/smoke/normal/assessment.jsonl").decode().splitlines()]

    scan_base = ["rg", "-l", "--max-filesize", "5M"]
    exclusions = ["-g", "!**/sealed/**", "-g", "!**/budget-monotonicity/**", "-g", "!**/session-excerpts.jsonl"]
    budget_pattern = r'"time_limit_seconds"\s*:\s*(?:30|60|120|240|300|360|600|900)(?:\.0)?\s*[,}]'
    scan = subprocess.run(scan_base + ["--pcre2", "-g", "*.json", "-g", "*.jsonl"] + exclusions + [budget_pattern, "jssa", "benchmarks"], cwd=ROOT, capture_output=True, text=True, timeout=60)
    assert scan.returncode in (0, 1), scan.stderr
    budget_files = {str(b): [] for b in [30, 60, 120, 240, 300, 360, 600, 900]}
    # 予算メタデータの索引だけ。これらをすべて独立した通常実行とは扱わない。
    for path in sorted(scan.stdout.splitlines()):
        assert "sealed" not in Path(path).parts
        text = (ROOT / path).read_text()
        for budget in set(re.findall(r'"time_limit_seconds"\s*:\s*(30|60|120|240|300|360|600|900)(?:\.0)?\s*[,}]', text)):
            budget_files[budget].append(path)
    # Q34原票は同時作業でgzipに移行済み。展開はメモリ内だけで行う。
    compressed_manifest = read_json("jssa/difficulty/fractal-basins/compression.json")
    expected_uncompressed = {r["path"]: r for r in compressed_manifest["files"]}
    for folder in ["full", "full-mp", "full-recheck"]:
        for path in sorted((ROOT / "jssa/difficulty/fractal-basins" / folder).glob("*.json.gz")):
            relative = path.relative_to(ROOT).as_posix()
            with gzip.GzipFile(fileobj=io.BytesIO(read(relative))) as stream:
                data = stream.read(5_242_881)
            assert len(data) <= 5_242_880
            metadata = expected_uncompressed[path.relative_to(ROOT / "jssa/difficulty/fractal-basins").as_posix()]
            assert sha(data) == metadata["uncompressed_sha256"]
            text = data.decode()
            assert not re.search(r"\b(370101|370201|370301)\b", text)
            for budget in set(re.findall(r'"time_limit_seconds"\s*:\s*(30|60|120|240|300|360|600|900)(?:\.0)?\s*[,}]', text)):
                assert relative[:-3] not in budget_files[budget]
                budget_files[budget].append(relative)
    seed_scan = subprocess.run(scan_base + ["-g", "*.json", "-g", "*.jsonl", "-g", "*.csv", "-g", "*.py", "-g", "*.md"] + exclusions + [r"\b(370101|370201|370301)\b", "jssa", "benchmarks"], cwd=ROOT, capture_output=True, text=True, timeout=60)
    assert seed_scan.returncode == 1 and not seed_scan.stdout and not seed_scan.stderr
    write_json("budget-inventory.json", {"scope": "手元のjssa/benchmarks、5MiB以下のJSON/JSONL、およびQ34のfull/full-mp/full-recheck直下のJSON.gzをメモリ展開して確認。sealed・Q33のsession抜粋・今回の出力を除外。予算メタデータの索引であり試行数ではない。", "pattern": budget_pattern, "files_by_budget": budget_files})

    for relative in [
        "benchmarks/research_runner.py", "uv.lock", "src/geosolver/dependency-lock.json",
        "src/geosolver/engine/standard/contracts/external_pipeline_config.py",
        "src/geosolver/engine/standard/contracts/runtime_budget.py",
        "src/geosolver/engine/standard/contracts/baseline_search_policy.py",
        "src/geosolver/engine/standard/orchestration/run_external_pipeline.py",
        "src/geosolver/engine/standard/orchestration/run_search.py",
        "src/geosolver/engine/standard/orchestration/run_rescue_search.py",
        "src/geosolver/engine/standard/search/scipy_multistart_backend.py",
        "src/geosolver/engine/standard/search/nomad_config.py",
        "src/geosolver/engine/standard/search/nomad_backend.py",
        "src/geosolver/engine/standard/refinement/mpmath_refiner.py", "src/geosolver/runtime/worker.py",
        "jssa/results/mechanism-attribution/README.md", "jssa/results/stage-profile-20261023/per-case-README.md",
        "jssa/difficulty/role-reassign/answer.md", "jssa/difficulty/nomad-wall/summary.json",
        "jssa/difficulty/nomad-wall/preregistration.md", "jssa/difficulty/fractal-basins/prediction.md",
        "jssa/difficulty/fractal-basins/full-runs.csv", "jssa/difficulty/fractal-basins/experiment.py",
        f"{q29_base}/a/answer.md", f"{q29_base}/a/operational-events.json",
        f"{q29_base}/b/answer.md", f"{q29_base}/b/runs/natural-900-HMMT-2022-FEB-GEO-07-io-observed.json",
        f"{q29_base}/b/runs/worker-memory-900-HMMT-2022-FEB-GEO-07.json",
    ]:
        read(relative)
    existing_selected_seconds = sum(float(r["wall_s"]) for _, cid in selected for r in by_id[cid])
    audit = {
        "main_runs": 969, "main_problems": 323, "main_correct": sum(r["matched"] == "True" for r in main_rows),
        "main_seed0_correct": sum(r["matched"] == "True" for r in main_rows if r["seed"] == "0"),
        "main_case_success_distribution": {str(k): sum(correct(cid) == k for cid in by_id) for k in range(4)},
        "main_second_attempt_runs": sum(r["second_attempt_triggered"] == "True" for r in main_rows),
        "main_rescue_runs": sum(r["rescue_triggered"] == "True" for r in main_rows),
        "main_either_late_problems": sum(late(cid) for cid in by_id),
        "q29_public_pairs": 10, "q29_valid_pairs": 9, "q29_gains": 2, "q29_same_failure": 7,
        "q29_infrastructure_unknown": 1, "q29_short_success_pairs": 0,
        "role_B_correct": sum(r["matched"] == "True" for r in role),
        "same_budget_discordances": len(discordances), "normal_smoke_runs": len(smoke),
        "normal_smoke_correct": sum(r["matched"] for r in smoke),
        "selection_pool_counts": {"A": len(a), "B": len(b_pool), "C_before_top10": len(c_pool), "D_after_C": len(d_pool)},
        "selected_existing_180_seconds_sum_120_runs": existing_selected_seconds,
        "selected_existing_180_correct": sum(correct(cid) for _, cid in selected),
        "linear_budget_scaling_reference_hours_at_4": existing_selected_seconds * 8 / 4 / 3600,
        "solver_limit_core_hours": sum(r["time_limit_seconds"] for r in jobs) / 3600,
        "outer_watchdog_hours_at_4": sum(r["outer_watchdog_seconds"] for r in jobs) / 4 / 3600,
        "file_limit_bytes": 4_900_000, "new_solver_runs": 0,
    }
    write_json("existing-summary.json", audit)
    write_json("source-manifest.json", {
        "workspace_head_at_preparation": git("rev-parse", "HEAD").decode().strip(),
        "frozen_solver_commit": FROZEN, "src_diff_vs_frozen_empty": True, "product_source_hash": source_hash,
        "q37_instruction_commit": instruction_commit, "q37_instruction_file_sha256": sha(instruction_source),
        "fresh_seeds": SEEDS, "seed_scan_match_count": 0,
        "seed_scan_scope": "手元jssa/benchmarksの5MiB以下のJSON/JSONL/CSV/Python/MarkdownとQ34のfull/full-mp/full-recheck直下JSON.gz。sealed、session-excerpts、今回の出力を除外。外部・未収録実行の未使用は保証しない。",
        "sources": dict(sorted(SOURCES.items())),
    })
    print(json.dumps(audit, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
