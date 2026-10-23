"""Audit inherited Q20a records without rerunning root searches or tracking."""
from __future__ import annotations

import csv
import datetime as dt
import hashlib
import importlib.util
import json
from pathlib import Path
import time

import mpmath as mpmath
import sympy as sp
from mpmath import mp

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[3]
mp.dps = 80


def read(name):
    return json.loads((OUT / name).read_text())


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def zvalue(value):
    return mp.mpc(value["re"], value["im"])


def serial(value):
    return mp.nstr(value, 24)


def main():
    start = time.perf_counter()
    spec = importlib.util.spec_from_file_location("q20a_inherited", OUT / "experiment.py")
    old = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(old)  # Definitions only; main() is not called.
    provenance = read("provenance.json")
    inherited_files = {p.name: sha(p) for p in OUT.iterdir()
                       if p.is_file() and p.name not in {
                           "answer.md", "resume-audit.json", "resume-audit.py",
                           "resume-audit-plan.md", "natural-audit.csv", "basin-audit.csv"}}
    checks = {
        "script_hash": sha(OUT / "experiment.py") == provenance["script_sha256"],
        "case_file_hash": sha(ROOT / "benchmarks/cases.jsonl") == provenance["input_cases_sha256"],
        "registration_hash": sha(OUT / "preregistration.md") == provenance["registration_sha256"],
        "registration_lock": sha(OUT / "preregistration.md") == read("registration-lock.json")["sha256"],
        "src_hash": old.src_digest() == read("summary.json")["src_sha256_after"],
    }
    src_before = old.src_digest()
    cases = {r["id"]: r for r in map(json.loads, (ROOT / "benchmarks/cases.jsonl").read_text().splitlines())
             if r["id"] in old.IDS}
    for cid in old.IDS:
        checks[f"dsl/{cid}"] = hashlib.sha256(json.dumps(cases[cid]["dsl"], sort_keys=True).encode()).hexdigest() == provenance["selected_dsl_sha256"][cid]
        for seed, folder in [(0, "raw-323"), (1, "raw-323-seed1")]:
            path = ROOT / "jssa/difficulty/minima" / folder / (cid + ".json")
            checks[f"raw/{seed}/{cid}"] = sha(path) == provenance["raw_sha256"][f"{seed}/{cid}"]

    path_rows, natural_rows, basin_rows = [], [], []
    existing = {(r["id"], r["seed"]): r for r in read("existing-basins.json")}
    for result in read("natural-results.json"):
        cid = result["id"]
        par = old.params(cid)
        bundle = old.load_problem_bundle(old.GeometryProblem.model_validate(cases[cid]["dsl"]).engine_document())
        ev = old.build_ir_evaluator(bundle)
        bounds = old.infer_problem_bounds(bundle)
        refs = old.reference_values(cases[cid]["answer"])
        paths = read(cid + "-paths.json")
        checked = []
        for loop_key, result_key in [("loop1", "one_loop"), ("loop2", "two_loop")]:
            path = paths[loop_key]
            radius = mp.mpf(path["radius"])
            zs = zvalue(path["start"])
            max_residual = mp.mpf(0)
            max_analytic_error = mp.mpf(0)
            for node in path["nodes"]:
                j = node["node"]
                theta = 2 * mp.pi * j / 64
                t = zvalue(node["parameter"])
                z = zvalue(node["z"])
                if par["degree"] == 2:
                    a, b = par["a"], par["b"]
                    center = -b / (2 * a)
                    sign = 1 if mp.re(zs) > center else -1
                    exact = center + sign * mp.sqrt(radius / a) * mp.exp(1j * theta / 2)
                else:
                    sign = 1 if mp.re(zs ** 2) > mp.mpf("1.5") else -1
                    exact = mp.sqrt((3 + sign * 2 * mp.sqrt(radius) * mp.exp(1j * theta / 2)) / 2)
                max_residual = max(max_residual, abs(old.poly(z, t, par)) / max(1, radius))
                max_analytic_error = max(max_analytic_error, abs(z - exact) / max(1, abs(exact)))
            endpoint = zvalue(path["end"])
            end_check = old.inspect_vector(bundle, ev, bounds, old.lift(cid, endpoint, result["selected_seed"]["coordinates"]), refs)
            checked.append(end_check)
            assert len(path["nodes"]) == 64
            assert max_residual < mp.mpf("1e-40")
            assert max_analytic_error < mp.mpf("1e-40")
            assert abs(mp.im(endpoint)) < mp.mpf("1e-30")
            assert end_check["valid"] and end_check["reference_index"] is not None
            assert sum(n["newton_steps"] for n in path["nodes"]) == path["newton_total"] == result[result_key]["newton_total"]
            assert path["end"] == result[result_key]["end"]
            path_rows.append({"id": cid, "loop": loop_key, "nodes": len(path["nodes"]),
                              "max_normalized_residual": serial(max_residual),
                              "max_analytic_branch_relative_error": serial(max_analytic_error),
                              "newton_total_saved": path["newton_total"], "DSL_endpoint": end_check})
        first = old.inspect_vector(bundle, ev, bounds,
                                   old.lift(cid, zvalue(paths["loop1"]["start"]), result["selected_seed"]["coordinates"]), refs)
        assert first["reference_index"] != checked[0]["reference_index"]
        assert first["reference_index"] == checked[1]["reference_index"]
        for key in ["closed_checks", "nroots_checks"]:
            repeated = [old.inspect_vector(bundle, ev, bounds,
                                           dict(zip(bundle.var_names, item["x"])), refs)
                        for item in result[key]]
            assert [c["valid"] for c in repeated] == [c["valid"] for c in result[key]]
            assert {c["reference_index"] for c in repeated if c["valid"]} == set(range(len(refs)))
        natural_rows.append({"id": cid, "start_k": result["selected_seed"]["k"],
                             "one_loop_ms_saved": 1000 * result["one_loop"]["track_sec"],
                             "newton_per_loop_saved": result["one_loop"]["newton_total"],
                             "max_DSL_endpoint_residual": max(first["residual_norm"], *(c["residual_norm"] for c in checked)),
                             "closed_roots_ms_saved": 1000 * result["closed_root_sec"],
                             "closed_roots_plus_validation_ms_saved": 1000 * (result["closed_root_sec"] + result["closed_validation_sec"]),
                             "nroots_ms_saved": 1000 * result["nroots_sec"],
                             "nroots_plus_validation_ms_saved": 1000 * (result["nroots_sec"] + result["nroots_validation_sec"]),
                             "valid_direct_roots": sum(c["valid"] for c in result["closed_checks"]),
                             "candidate_roots": len(result["closed_checks"]),
                             "loop_answer_before": first["answer"], "loop_answer_after": checked[0]["answer"]})
        for row in old.count_existing(cid):
            assert row == existing[(cid, row["seed"])]
            basin_rows.append(row)

    controls = []
    for row in read("distance-controls.json"):
        par = old.params(row["id"])
        radius = mp.mpf(row["radius"])
        center = -par["b"] / (2 * par["a"])
        endpoint = zvalue(row["end"])
        t = par["critical"] - radius
        scaled_error = abs((endpoint - center) / mp.sqrt(radius / par["a"]) - 1)
        assert scaled_error < mp.mpf("1e-30")
        assert abs(old.poly(endpoint, t, par)) / radius < mp.mpf("1e-35")
        assert row["newton_total"] == 256 and row["newton_max"] == 4 and row["swapped"] and row["all_nodes_pass"]
        controls.append({"id": row["id"], "exponent": row["exponent"],
                         "scaled_endpoint_error_recomputed": serial(scaled_error),
                         "all_nodes_independently_checked": False})

    # Symbolic identities only: no additional iterative solver calls.
    eta, xi, k = sp.symbols("eta xi k")
    error_map = sp.factor((1 + eta + 1/(1 + eta))/2 - 1)
    mobius = sp.factor((error_map/(2 + error_map)) - (eta/(2 + eta))**2)
    qxi = sp.factor(xi - (xi**2 - k)/(2*xi))
    assert sp.cancel(error_map - eta**2/(2*(eta + 1))) == 0
    assert mobius == 0
    assert sp.cancel(qxi - (xi**2 + k)/(2*xi)) == 0
    source_rows = []
    stage_path = ROOT / "jssa/results/stage-profile-20261023/per-case.csv"
    if stage_path.exists():
        with stage_path.open() as stream:
            source_rows = [r for r in csv.DictReader(stream) if any(r.get(name) in old.IDS for name in ["id", "case_id"])]
    checks["src_unchanged_during_audit"] = old.src_digest() == src_before
    checks["inherited_artifacts_unchanged"] = all(sha(OUT / name) == value for name, value in inherited_files.items())
    assert all(checks.values())
    for name, rows in [("natural-audit.csv", natural_rows), ("basin-audit.csv", basin_rows)]:
        with (OUT / name).open("w", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
    output = {
        "finished_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "kind": "post-result integrity audit, no new tracking or local search",
        "new_LM_Powell_Newton_or_tracking_runs": 0,
        "checks": checks, "natural_paths": path_rows, "natural_summary": natural_rows,
        "controls_endpoint_audit": controls, "basin_rows": basin_rows,
        "stage_profile_source": str(stage_path.relative_to(ROOT)), "stage_profile_rows": source_rows,
        "symbolic_error_map": str(error_map), "symbolic_mobius_identity_remainder": str(mobius),
        "inherited_artifact_sha256": inherited_files,
        "audit_script_sha256": sha(__file__), "src_sha256": src_before,
        "elapsed_sec_excluding_import": time.perf_counter() - start,
        "limitations": ["Original DSL checks use the inherited double-precision evaluator.",
                        "Distance-control paths were not saved, so only endpoints and summaries are independently audited.",
                        "No frozen full-solver runs are added; timings are inherited single-run observations."]}
    (OUT / "resume-audit.json").write_text(json.dumps(output, ensure_ascii=False, indent=2, allow_nan=False) + "\n")
    print(json.dumps({"all_hash_checks_pass": all(checks.values()), "natural_nodes": sum(r["nodes"] for r in path_rows),
                      "natural_endpoints": len(path_rows), "control_endpoints": len(controls),
                      "stage_profile_rows": len(source_rows), "elapsed_sec_excluding_import": output["elapsed_sec_excluding_import"]}))


if __name__ == "__main__":
    main()
