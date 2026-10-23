"""Stage 1 only: read saved evidence and write tables. No solver imports/calls.

Refuses to run once prediction.lock.json exists. Standard library only.
"""
import csv
import hashlib
import io
import json
import statistics
import subprocess
from collections import Counter
from pathlib import Path

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[3]
OLD = OUT.parent
FROZEN = "60db4b679b04167175c51c479c87c22fa663fda0"
SOURCES = {}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def read(path):
    p = ROOT / path
    data = p.read_bytes()
    SOURCES[str(p.relative_to(ROOT))] = {"sha256": sha(data), "bytes": len(data)}
    return data.decode()


def rows(path):
    return list(csv.DictReader(io.StringIO(read(path))))


def write(name, data):
    payload = data.encode()
    assert len(payload) < 5_000_000, name
    (OUT / name).write_bytes(payload)


def dump(name, obj):
    write(name, json.dumps(obj, ensure_ascii=False, indent=2, allow_nan=False) + "\n")


def csvout(name, data):
    stream = io.StringIO(newline="")
    w = csv.DictWriter(stream, fieldnames=list(data[0]), lineterminator="\n")
    w.writeheader()
    w.writerows(data)
    write(name, stream.getvalue())


def bucket(r):
    prefix = r["answer_source_uid_prefix"]
    if prefix in ("search/nomad", "search/scipy"):
        attempt = "second" if r["second_attempt_selected"] == "fallback" else "first"
        return attempt + "/" + prefix.split("/")[1]
    return prefix


def main():
    assert not (OUT / "prediction.lock.json").exists(), "Already locked; do not rewrite."
    subprocess.run(["git", "diff", "--exit-code", FROZEN, "--", "src", "benchmarks/research_runner.py"], cwd=ROOT, check=True, capture_output=True)
    selection = rows("jssa/difficulty/derivative-free/selection.csv")
    old_f = rows("jssa/strategy/astra-consult-18/Q27f/selected-case-validation.csv")
    census = rows("jssa/strategy/astra-consult-18/Q27d/census-both-seeds.csv")
    hard = sorted(r["id"] for r in old_f if r["p2_qualifies"] == "True")
    controls = []
    for d in range(1, 8):
        pool = [r for r in census if int(r["d"]) == d and int(r["m"]) >= d and r["id"] not in hard]
        pool.sort(key=lambda r: (-min(float(r["p"]), float(r["p1"])), sha(r["id"].encode())))
        controls.append(pool[0]["id"])
    assert len(hard) == 21 and len(set(hard + controls)) == 28
    assert [r["id"] for r in selection] == hard + controls
    ids = {r["id"]: r for r in selection}
    a = rows("jssa/results/mechanism-attribution/attribution.csv")
    b = rows("jssa/results/stage-profile-20261023/per-case.csv")
    q31 = rows("jssa/difficulty/capability-attribution/per-run.csv")
    q31p = rows("jssa/difficulty/capability-attribution/per-problem.csv")
    ab = rows("jssa/results/search-mode-ablation/per-run.csv")
    q32 = rows("jssa/difficulty/derivative-free/per-problem.csv")
    starts = rows("jssa/difficulty/derivative-free/per-start.csv")
    endpoint = rows("jssa/difficulty/derivative-free/endpoint-audit.csv")
    key = lambda r: (r["case_id"], r["seed"])
    aa, bb = {key(r): r for r in a}, {key(r): r for r in b}
    assert len(aa) == len(bb) == len(a) == len(b) == 969 and aa.keys() == bb.keys()
    fields = {"matched": "correct", "answer_source_stage": "final_answer_source", "refine_attempted": "candidates_sent_to_refinement", "refine_converged": "candidates_converged", "exact_rejected_false_positive": "candidates_rejected_as_false", "exact_accepted": "candidates_accepted", "refinement_s": "refinement_time_s", "exact_assembly_s": "identification_verification_time_s", "search_s": "search_time_s", "rescue_s": "rescue_time_s", "initial_probe_s": "initial_probe_time_s", "wall_s": "wall_time_s"}
    for k, r in aa.items():
        for x, y in fields.items():
            assert r[x] == bb[k][y], (k, x)
    for r in q31:
        for f in a[0]:
            assert r[f] == aa[key(r)][f], (key(r), f)
    assert len(q31) == 129 and len(q31p) == 43
    q32idx = {(r["id"], r["arm"]): r for r in q32}
    for s in selection:
        for arm in ("N", "L", "Lnp"):
            rr = [r for r in starts if r["id"] == s["id"] and r["arm"] == arm]
            assert len(rr) == 16
            assert sum(int(r["hit"]) for r in rr) == int(q32idx[s["id"], arm]["hits"])
            assert sum(int(r["coarse"]) for r in rr) == int(q32idx[s["id"], arm]["coarse"])
    runrows = []
    for r in a:
        runrows.append({**r, "source_bucket": bucket(r), "group": ids.get(r["case_id"], {}).get("group", "other"), "discovery_time_s": "", "candidate_processing_cpu_s": "", "timing_missing_reason": "candidate_event_times_not_in_available_stats_csv"})
    csvout("existing-runs.csv", runrows)
    stages = []
    for group in ("all", "hard", "control"):
        rr = [r for r in runrows if group == "all" or r["group"] == group]
        for source in sorted(set(r["source_bucket"] for r in rr)):
            rrs = [r for r in rr if r["source_bucket"] == source]
            out = {"group": group, "source_bucket": source, "runs": len(rrs), "matched": sum(r["matched"] == "True" for r in rrs), "problems": len(set(r["case_id"] for r in rrs))}
            for f in ("wall_s", "initial_probe_s", "search_s", "refinement_s", "exact_assembly_s", "rescue_s"):
                out[f + "_median"] = statistics.median(float(r[f]) for r in rrs)
                out[f + "_mean"] = statistics.mean(float(r[f]) for r in rrs)
            for f in ("refine_attempted", "refine_converged", "exact_rejected_false_positive", "exact_accepted"):
                out[f + "_sum"] = sum(int(r[f]) for r in rrs)
            out["discovery_time_available_runs"] = 0
            stages.append(out)
    csvout("existing-stages.csv", stages)
    abi = {(r["case_id"], r["search_mode"]): r for r in ab}
    probs = []
    for s in selection:
        id = s["id"]
        rs = [r for r in runrows if r["case_id"] == id]
        out = {"id": id, "group": s["group"], "n_vars": s["n_vars"], "historical_method": s["historical_method"], "full_matched_of_3": sum(r["matched"] == "True" for r in rs), "full_sources": json.dumps(dict(sorted(Counter(r["source_bucket"] for r in rs).items())), separators=(",", ":")), "full_wall_median_s": statistics.median(float(r["wall_s"]) for r in rs)}
        for arm in ("N", "L", "Lnp"):
            p = q32idx[id, arm]
            out[arm + "_hits_of_16"] = int(p["hits"])
            out[arm + "_coarse_of_16"] = int(p["coarse"])
            out[arm + "_native_hits_of_16"] = sum(int(r["final_hit"]) for r in endpoint if r["id"] == id and r["arm"] == arm)
            out[arm + "_single_start_wall_mean_s"] = statistics.mean(float(r["seconds"]) for r in starts if r["id"] == id and r["arm"] == arm)
        for mode in ("disco_mads", "scipy_multistart"):
            out[mode + "_full_no_second_matched"] = abi[id, mode]["solved"]
            out[mode + "_full_no_second_wall_s"] = float(abi[id, mode]["wall_seconds"])
        out["apparent_L_success_vs_N_full_speed"] = out["L_hits_of_16"] > out["N_hits_of_16"] and all(out[m + "_full_no_second_matched"] == "True" for m in ("disco_mads", "scipy_multistart")) and out["disco_mads_full_no_second_wall_s"] < out["scipy_multistart_full_no_second_wall_s"]
        out["confirmed_matched_design_reversal"] = "unidentified"
        probs.append(out)
    csvout("existing-problems.csv", probs)
    discovery = []
    raw_cache = {}
    for row in starts:
        if row["arm"] not in ("N", "L", "Lnp"):
            continue
        path = "jssa/difficulty/derivative-free/" + row["raw"]
        if path not in raw_cache:
            raw_cache[path] = json.loads(read(path))
        raw = raw_cache[path]
        arm = next(r for r in raw["arms"] if r["arm"] == row["arm"])
        best = arm.get("best") or {}
        discovery.append({"id": row["id"], "group": row["group"], "seed": row["seed"], "k": row["k"], "arm": row["arm"], "strict_hit": row["hit"], "saved_best_eval_index": best.get("eval", ""), "total_evals": arm["evals"], "arm_total_wall_s": arm["seconds"], "correct_saved_point_time_upper_s": arm["seconds"] if int(row["hit"]) else "", "first_correct_time_s": "", "full_solver_refinable_candidate_time_s": "", "reason": "saved_best_eval_is_not_first_hit; no_per_candidate_time_or_common_suffix_result", "raw_path": path})
    assert len(discovery) == 28 * 16 * 3
    csvout("existing-discovery.csv", discovery)
    chosen = []
    inputs = []
    start_packets = []
    for i, s in enumerate(selection):
        id = s["id"]
        p = "jssa/difficulty/derivative-free/inputs/" + id + ".json"
        body = read(p)
        assert sha(body.encode()) == s["input_sha256"]
        inp = json.loads(body)
        grade = "jssa/difficulty/derivative-free/grading/" + id + ".json"
        read(grade)
        chosen.append({"order": i, **s, "selection_reason": "Q27f.p2_qualifies=True; all 21" if s["group"] == "hard" else "Q27d d=1..7,m>=d; maximize min(p,p1); tie SHA256(id) ascending"})
        inputs.append({"id": id, "search_input_path": p, "search_input_sha256": sha(body.encode()), "grading_path": grade, "grading_sha256": SOURCES[grade]["sha256"]})
        read("benchmarks/dsl/" + id + ".json")
        ss = list(inp["starts"])
        assert len(ss) == 16
        for k in range(8):
            coords = []
            for j, (lo, hi) in enumerate(inp["bounds"]):
                message = f"q32-stage-supplement-v1|{id}|32003|{k}|{j}".encode()
                u = (int.from_bytes(hashlib.sha256(message).digest()[:8], "big") >> 11) / (2**53)
                coords.append(lo + u * (hi - lo))
            ss.append({"seed": 32003, "k": k, "x": coords})
        start_packets.append({"id": id, "bounds": inp["bounds"], "var_names": inp["var_names"], "starts": ss})
    csvout("selection.csv", chosen)
    write("selected-problems.txt", "\n".join(hard + controls) + "\n")
    dump("starts.json", start_packets)
    dump("input-manifest.json", {"inputs": inputs, "starts_sha256": sha((OUT / "starts.json").read_bytes()), "seed_rule": "32001/32002: exact saved Q32 coordinates; 32003: first 53 bits of SHA256(q32-stage-supplement-v1|id|32003|k|j), scaled to saved box"})
    # Only read source bytes. Do not import solver code or call numerical probes.
    code_paths = subprocess.check_output(["git", "ls-files", "src"], cwd=ROOT, text=True).splitlines()
    for path in code_paths + ["benchmarks/research_runner.py", "benchmarks/cases.jsonl", "pyproject.toml", "uv.lock"]:
        if (ROOT / path).is_file():
            read(path)
    for path in ["jssa/strategy/codex-tasks-1023.md", "jssa/difficulty/capability-attribution/answer.md", "jssa/difficulty/derivative-free/sources/Q31-answer.md", "jssa/strategy/astra-consult-18/Q27f/answer.md", "jssa/difficulty/derivative-free/answer.md", "jssa/difficulty/derivative-free/prepare.py", "jssa/difficulty/derivative-free/experiment.py", "jssa/difficulty/derivative-free/analyze.py", "jssa/difficulty/derivative-free/audit_results.py", "jssa/results/mechanism-attribution/README.md", "jssa/results/stage-profile-20261023/per-case-README.md", "jssa/results/search-mode-ablation/README.md"]:
        read(path)
    dump("source-manifest.json", {"frozen_commit": FROZEN, "tracked_src_and_research_runner_match_frozen": True, "files": dict(sorted(SOURCES.items()))})
    hrows = [r for r in old_f if r["id"] in hard]
    summary = {
        "solver_calls": 0, "network_calls": 0, "src_changes": 0,
        "raw_stats_available": False, "evidence_level": "two saved 969-row stats-derived CSVs, crosschecked field by field; not 969 original JSONs",
        "stats_rows": len(a), "stats_problems": len(set(r["case_id"] for r in a)), "stats_matched": sum(r["matched"] == "True" for r in a),
        "q31_crosschecked_rows": len(q31), "q31_problems": len(q31p),
        "q27f_local_starts": sum(int(r["starts0"]) + int(r["starts1"]) for r in hrows), "q27f_local_hits": sum(int(r["hits0"]) + int(r["hits1"]) for r in hrows),
        "selected_count": len(selection), "hard_count": len(hard), "control_count": len(controls),
        "selected_full_matched": sum(r["matched"] == "True" for r in runrows if r["group"] != "other"),
        "second_triggered": sum(r["second_attempt_triggered"] == "True" for r in a), "second_selected": sum(r["second_attempt_selected"] == "fallback" for r in a),
        "known_candidate_discovery_timestamps": 0,
        "confirmed_matched_design_reversals": None, "identifiable_reversal_examples": 0,
        "apparent_mixed_protocol_speed_examples": [p["id"] for p in probs if p["apparent_L_success_vs_N_full_speed"]],
        "cautions": ["採用元は因果寄与ではない", "段階時間は実行全体の集計であり、採用候補だけの費用でも第2試行だけの費用でもない", "時刻欠測を0秒にしない", "成功集合・局所近似ヒット・収束・採用は別指標", "旧SciPy portfolioを単体LMと同一視しない", "元JSON未取得。bounded local search is not proof of nonexistence"],
    }
    dump("evidence-summary.json", summary)
    print(json.dumps({"rows_checked": 969, "q31_checked": 129, "selected": 28, "apparent_examples": summary["apparent_mixed_protocol_speed_examples"], "new_solver_calls": 0}, ensure_ascii=False))


if __name__ == "__main__":
    main()
