"""Post-generation assessment. This script, unlike workers, reads references."""
from collections import Counter, defaultdict
import csv
import hashlib
import json
from pathlib import Path
import statistics
import re
import sympy as s

from exact_onevar import exact_sign, root_from_wire

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]


def read_runs(folder):
    return {r["id"]: r for path in sorted((HERE / folder).glob("*.json"))
            if path.name not in ("run-manifest.json", "run-timing.json")
            for r in [json.loads(path.read_text())]}


def scalar_refs(answer):
    values = answer if isinstance(answer, list) else [answer]
    def parse(v):
        text = re.sub(r"√(\d+)", r"sqrt(\1)", str(v))
        text = re.sub(r"(\d)(sqrt\()", r"\1*\2", text)
        return s.sympify(text, locals={"sqrt": s.sqrt, "pi": s.pi})
    return [parse(v) for v in values]


def source_hash(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    v1, runs, checks = [read_runs(f) for f in ("pilot-v1", "pilot-v2", "verification-v2")]
    existence, existence_checks = [read_runs(f) for f in ("existence-checks", "existence-verification")]
    refs = {r["id"]: r for r in map(json.loads, (ROOT / "benchmarks/cases.jsonl").read_text().splitlines())}
    old_exact = {r["id"]: r for r in csv.DictReader((ROOT / "jssa/strategy/astra-consult-17/H/sources/comparison-cases.csv").open())}
    old_numeric = defaultdict(list)
    for r in csv.DictReader((ROOT / "jssa/results/stage-profile-20261023/per-case.csv").open()):
        old_numeric[r["case_id"]].append(r)
    manifest = json.loads((HERE / "manifest.json").read_text())
    assert len(runs) == len(v1) == len(manifest["inputs"]) == 43
    assert source_hash(HERE / "preregistration.md") == manifest["preregistration_sha256"]
    assert source_hash(ROOT / "benchmarks/cases.jsonl") == manifest["source_sha256"]
    for r in manifest["inputs"]:
        assert source_hash(HERE / "inputs" / (r["id"] + ".json")) == r["input_file_sha256"]
    rows = []
    for id, r in runs.items():
        ck = checks.get(id, {})
        verified = ck.get("status") == "verified" and ck.get("all_negative_detected") is True
        numeric_match = None
        exact_match = None
        if r["status"] == "complete":
            rr = scalar_refs(refs[id]["answer"])
            aa = list(map(float, r["answer_decimals"]))
            bb = [float(v.evalf(40)) for v in rr]
            numeric_match = (len(aa) == len(bb)
                             and all(any(abs(a-b) <= 1e-10*max(1.0,abs(b)) for b in bb) for a in aa)
                             and all(any(abs(a-b) <= 1e-10*max(1.0,abs(b)) for a in aa) for b in bb))
            if verified:
                vals = [root_from_wire(w) for w in r["answer_set"]]
                exact_match = (len(vals) == len(rr)
                               and all(any(exact_sign(a-b) == 0 for b in rr) for a in vals)
                               and all(any(exact_sign(a-b) == 0 for a in vals) for b in rr))
        rows.append({"id": id, "contest": id.split("-")[0].upper(),
                     "v1_status": v1[id]["status"], "generation_status": r["status"],
                     "verification_status": ck.get("status", "not_applicable"),
                     "retained_certificate": verified, "reference_numeric_match": numeric_match,
                     "reference_exact_match": exact_match,
                     "n_real_roots": r.get("n_real_roots"), "n_accepted": r.get("n_accepted"),
                     "n_rejected": r.get("n_rejected"), "n_answers": len(r.get("answer_set", [])) if r["status"] == "complete" else None,
                     "answer_decimals": ";".join(r.get("answer_decimals", [])),
                     "generation_seconds": r.get("processing_seconds"),
                     "verification_seconds": ck.get("processing_seconds"),
                     "reason": r.get("reason", "") or ("unresolved algebraic sign" if r["status"] == "unresolved" else ""),
                     "verification_stage": ck.get("last_stage", ""),
                     "msolve_old_status": old_exact[id]["msolve_class"],
                     "geosolver_old_correct_of_3": sum(n["correct"] == "True" for n in old_numeric[id]),
                     "geosolver_old_median_s": statistics.median(float(n["wall_time_s"]) for n in old_numeric[id])})
    with (HERE / "per-problem.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader(); w.writerows(rows)
    generated = [r for r in rows if r["generation_status"] == "complete"]
    retained = [r for r in rows if r["retained_certificate"]]
    p2 = [r for r in retained if r["n_real_roots"] >= 2 and r["n_rejected"] > 0]
    negative = [n for c in checks.values() if c.get("status") == "verified" for n in c["negative_checks"]]
    p4 = [id for id, r in existence.items() if r["status"] == "complete" and not r["answer_set"]
          and existence_checks.get(id, {}).get("status") == "verified"]
    summary = {
        "n": 43, "preregistration_sha256": manifest["preregistration_sha256"],
        "v1_counts": dict(Counter(r["status"] for r in v1.values())),
        "v2_counts": dict(Counter(r["status"] for r in runs.values())),
        "verification_counts": dict(Counter(r["status"] for r in checks.values())),
        "generated_complete": len(generated), "retained_complete": len(retained),
        "retained_by_contest": dict(Counter(r["contest"] for r in retained)),
        "generated_numeric_reference_matches": sum(r["reference_numeric_match"] is True for r in generated),
        "retained_exact_reference_matches": sum(r["reference_exact_match"] is True for r in retained),
        "negative_checks": len(negative), "negative_detected": sum(n["detected"] for n in negative),
        "P1": {"pass": len(retained) >= 22 and len(set(r["contest"] for r in retained)) == 3,
               "observed": len(retained), "threshold": 22, "generated_before_replay": len(generated)},
        "P2": {"pass": len(p2) >= 5, "observed": len(p2), "ids": [r["id"] for r in p2]},
        "P3": {"pass": len(retained) == len(generated) and all(r["reference_exact_match"] is True for r in retained)
                         and all(n["detected"] for n in negative),
               "interpretation": "not fully established: one generated certificate timed out during replay; no wrong certified set was observed"},
        "P4": {"pass": len(p4) == 5, "observed": len(p4), "ids": p4},
        "retained_multiple_answer_sets": sum(r["n_answers"] > 1 for r in retained),
        "retained_old_msolve_status": dict(Counter(r["msolve_old_status"] for r in retained)),
        "retained_old_geosolver_correct": sum(r["geosolver_old_correct_of_3"] for r in retained),
        "retained_real_roots": sum(r["n_real_roots"] for r in retained),
        "retained_rejected_roots": sum(r["n_rejected"] for r in retained),
        "retained_generation_median_s": statistics.median(r["generation_seconds"] for r in retained),
        "retained_generation_plus_replay_median_s": statistics.median(r["generation_seconds"]+r["verification_seconds"] for r in retained),
        "retained_generation_plus_replay_max_s": max(r["generation_seconds"]+r["verification_seconds"] for r in retained),
        "blocked_reference_reads": sum(len(r.get("blocked_reads",[])) for r in runs.values()),
        "timings": {}, "source_hashes": {},
    }
    for folder in ("pilot-v1", "pilot-v2", "verification-v2", "existence-checks", "existence-verification"):
        rs = read_runs(folder)
        summary["timings"][folder] = {
            "n_jobs": len(rs), "processing_seconds_sum": sum(r.get("processing_seconds",0) for r in rs.values()),
            **json.loads((HERE / folder / "run-timing.json").read_text())}
    for source in ("benchmarks/cases.jsonl", "jssa/results/stage-profile-20261023/per-case.csv",
                   "jssa/strategy/astra-consult-17/H/sources/comparison-cases.csv"):
        summary["source_hashes"][source] = source_hash(ROOT / source)
    (HERE / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n")
    lines = ["# 全43問の最終表", "", "生成completeと、保存証拠を検算できたことを分ける。時間は秒。", "",
             "| ID | 生成 | 検算 | 根：採用/全実根 | 値 | 生成秒 | 理由 |", "|---|---|---|---:|---|---:|---|"]
    for r in rows:
        roots = "—" if r["n_real_roots"] is None else str(r["n_accepted"])+"/"+str(r["n_real_roots"])
        val = r["answer_decimals"] or "—"
        lines.append(f"| {r['id']} | {r['generation_status']} | {r['verification_status']} | {roots} | {val} | {r['generation_seconds']:.3f} | {r['reason']} |")
    (HERE / "all-cases.md").write_text("\n".join(lines)+"\n")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
