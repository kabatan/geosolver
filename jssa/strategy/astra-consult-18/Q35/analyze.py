"""Q35: census of archived results; no solver calls and no outcome-based fits.

Run with the repository Python. All writes are restricted to this directory.
Stratification and comparison outside the original sampling frame are descriptive,
not estimates of the causal effect of geometric freedom.
"""
from __future__ import annotations

import csv
import hashlib
import json
import statistics
import subprocess
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
CERT = ROOT / "jssa/difficulty/certify-all"
H = ROOT / "jssa/strategy/astra-consult-17/H"
FROZEN = "60db4b679b04167175c51c479c87c22fa663fda0"
SOURCES = {}


def read(path):
    path = Path(path)
    data = path.read_bytes()
    SOURCES[str(path.relative_to(ROOT))] = {
        "sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)
    }
    return data.decode()


def table(path):
    return list(csv.DictReader(read(path).splitlines()))


def output(name, value):
    data = json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False).encode() + b"\n"
    assert len(data) < 5_000_000
    (HERE / name).write_bytes(data)


def csvout(name, rows):
    keys = list(dict.fromkeys(k for row in rows for k in row))
    with (HERE / name).open("w", newline="") as f:
        w = csv.DictWriter(f, keys)
        w.writeheader()
        w.writerows(rows)
    assert (HERE / name).stat().st_size < 5_000_000


def count(rows):
    n = len(rows)
    k = sum(r["certified"] for r in rows)
    timeouts = sum(r["status"] == "timeout" for r in rows)
    return {
        "n": n, "certified": k, "rate": k / n if n else None,
        "identity": sum(r["identity_count"] > 0 for r in rows),
        "timeouts": timeouts,
        "timeout_only_success_bounds": [k / n, (k + timeouts) / n] if n else None,
        "statuses": dict(sorted(Counter(r["status"] for r in rows).items())),
    }


def grouped(rows):
    return {g: count([r for r in rows if r["dimension_group"] == g]) for g in ("G", "I")}


def strata(rows, label, key):
    usable = [r for r in rows if r["dimension_group"] in ("G", "I") and key(r) is not None]
    levels = sorted(set(key(r) for r in usable), key=str)
    records = []
    numerator = {"G": 0.0, "I": 0.0}
    common_n = 0
    included = {"G": 0, "I": 0}
    for lev in levels:
        subsets = {g: [r for r in usable if key(r) == lev and r["dimension_group"] == g] for g in ("G", "I")}
        for g, rs in subsets.items():
            records.append({"stratification": label, "level": str(lev), "group": g,
                            "n": len(rs), "certified": sum(r["certified"] for r in rs),
                            "timeout": sum(r["status"] == "timeout" for r in rs)})
        if all(subsets.values()):
            w = sum(map(len, subsets.values()))
            common_n += w
            for g, rs in subsets.items():
                included[g] += len(rs)
                numerator[g] += w * sum(r["certified"] for r in rs) / len(rs)
    rates = {g: numerator[g] / common_n if common_n else None for g in ("G", "I")}
    return records, {"common_support_cases": included, "pooled_weight_n": common_n,
                     "rates_standardized_to_pooled_common_support": rates,
                     "difference": rates["G"] - rates["I"] if common_n else None}


def main():
    src_tree = subprocess.check_output(["git", "rev-parse", "HEAD:src"], cwd=ROOT, text=True).strip()
    frozen_tree = subprocess.check_output(["git", "rev-parse", FROZEN + ":src"], cwd=ROOT, text=True).strip()
    assert src_tree == frozen_tree
    assert not subprocess.check_output(["git", "diff", FROZEN, "--", "src"], cwd=ROOT)
    h = {r["id"]: r for r in table(H / "classification.csv")}
    comparison = {r["id"]: r for r in table(H / "sources/comparison-cases.csv")}
    prior = {r["id"]: r for r in table(H / "sources/prior-batch-summary.csv")}
    components = {r["id"]: r for r in json.loads(read(H / "sources/prior-components.json"))}
    q27 = {r["id"]: r for r in table(ROOT / "jssa/strategy/astra-consult-18/Q27f/case-matrix.csv")}
    rows = []
    certificates = []
    for c in table(CERT / "per-case.csv"):
        if c["group"] != "development323":
            continue
        cid = c["id"]
        cr = json.loads(read(CERT / c["result_path"]))
        assert cr["status"] == c["status"]
        assert hashlib.sha256((CERT / c["result_path"]).read_bytes()).hexdigest() == c["result_sha256"]
        hh, old, pc = h.get(cid, {}), prior.get(cid, {}), components.get(cid, {})
        ev = hh.get("evidence_code", "")
        r = {
            "id": cid, "dimension_group": "G" if ev == "G" else "I" if ev in ("L0", "R0") else ev or "unclassified",
            "H_evidence": ev, "physical_dimension": hh.get("physical_dimension", ""),
            "msolve_class": comparison[cid]["msolve_class"],
            "dsl_variables": int(comparison[cid]["dsl_vars"]),
            "status": c["status"], "certified": c["status"] == "certified_saved_endpoint_set",
            "variables": int(c["variables"]) if c["variables"] else None,
            "equations": int(c["equations"]) if c["equations"] else None,
            "max_degree": int(c["max_degree"]) if c["max_degree"] else None,
            "total_terms": int(c["total_terms"]) if c["total_terms"] else None,
            "nondeg_count": len(cr.get("nondeg_factors", [])),
            "saved_candidates": int(c["saved_candidate_count"]),
            "proposed_candidates": int(c["proposed_candidate_count"]),
            "identity_count": int(c["identity_count"]), "certificate_kind": c["certificate_kind"],
            "zero_dimensional": c["zero_dimensional"],
            "stage": c["stage"], "stage_timeouts": c["stage_timeouts"],
            "hard_timeout": c["hard_timeout"] == "True", "wall_seconds": float(c["process_wall_seconds"]),
            "numeric_pslq_seconds": float(c["numeric_pslq_seconds"]),
            "groebner_seconds": float(c["groebner_seconds"]),
            "prior_certificate": hh.get("prior_certificate", ""),
            "prior_seconds": old.get("seconds", ""),
            "old_elimination": comparison[cid]["elim_status"],
            "old_elimination_seconds": comparison[cid]["elim_s"],
            "components_status": pc.get("status", "not_measured"),
            "components_target_varies": sum(not a["t_constant"] for a in pc.get("components", [])),
            "components_target_finite": sum(a["t_constant"] for a in pc.get("components", [])),
            "all3_correct": q27[cid]["geo_matched_comparison"] == "3",
            "result_path": str((CERT / c["result_path"]).relative_to(ROOT)),
        }
        assert r["certified"] == (q27[cid]["cert_status"] == "certified_saved_endpoint_set")
        if r["dimension_group"] in ("G", "I"):
            inp = json.loads(read(CERT / "inputs" / (cid + ".json")))
            r.update(dsl_conditions=len(inp["dsl"]["conditions"]), dsl_constructions=len(inp["dsl"]["constructions"]))
            system = (CERT / c["result_path"]).parent / "system.json"
            if system.exists():
                read(system)
            for ident in cr.get("identities", []):
                certificates.append({"id": cid, "group": r["dimension_group"], "certified": r["certified"],
                    **{k: ident.get(k) for k in ("kind", "Q", "N", "cofactor_terms", "bytes", "verified_fraction")},
                    "allowed_roots": ident.get("root_check", {}).get("allowed_root_count")})
        rows.append(r)
    assert len(rows) == 323 and len({r["id"] for r in rows}) == 323
    focal = [r for r in rows if r["dimension_group"] in ("G", "I")]
    assert (count([r for r in focal if r["dimension_group"] == "G"])["certified"],
            count([r for r in focal if r["dimension_group"] == "I"])["certified"]) == (6, 1)
    summary = {
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "solver_commit": FROZEN, "src_tree": src_tree, "archive_head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "counts": grouped(focal),
        "sensitivity": {
            "without_target_independent_rectangle_AIME2015": grouped([r for r in focal if r["id"] != "AIME-2015-II-07"]),
            "without_that_and_globally_variable_target_JMO2014": grouped([r for r in focal if r["id"] not in ("AIME-2015-II-07", "JMO-2014-PRE-09")]),
            "saved_candidate_present": grouped([r for r in focal if r["saved_candidates"] > 0]),
            "complete_candidate_P": grouped([r for r in focal if r["proposed_candidates"] > 0 and r["proposed_candidates"] == r["saved_candidates"]]),
            "exclude_timeout_descriptive_only": grouped([r for r in focal if r["status"] != "timeout"]),
            "completed_algebra_terminal": grouped([r for r in focal if r["status"] in ("certified_saved_endpoint_set", "multiple_roots_remain", "no_univariate_eliminant", "candidate_set_mismatch")]),
        },
        "archived_alternative_methods": {}, "representation_medians": {}, "standardization": {},
        "selection_controls": {
            "msolve_answer_set_matches_NOT_a_physical_dimension_class": count([r for r in rows if r["msolve_class"] == "answer_set_matches"]),
            "Q11_computed_zero_dimensional_POST_SELECTION": count([r for r in rows if r["zero_dimensional"] == "True"]),
            "H_isolated_plus_msolve_matches_proxy_NOT_causal": count([r for r in rows if r["dimension_group"] == "I" or r["msolve_class"] == "answer_set_matches"]),
        },
    }
    for g in ("G", "I"):
        rs = [r for r in focal if r["dimension_group"] == g]
        ps = [r for r in rs if r["prior_certificate"] != "outside_old_63"]
        summary["archived_alternative_methods"][g] = {
            "old_Singular_direct_elimination": dict(Counter(r["old_elimination"].split(":")[0] for r in rs)),
            "old_certificate_status": dict(Counter(r["prior_certificate"] for r in rs)),
            "old_certificate_available_n": len(ps),
            "old_small_identity_count": sum(r["prior_certificate"] in ("identity_P", "identity_E") for r in ps),
            "old_with_large_Singular_only_count": sum(r["prior_certificate"].startswith("identity_") for r in ps),
            "old_completed_small_identity_count": sum(r["prior_certificate"] in ("identity_P", "identity_E") for r in ps if r["prior_certificate"] not in ("timeout", "unsupported_angle_target")),
            "old_completed_n": sum(r["prior_certificate"] not in ("timeout", "unsupported_angle_target") for r in ps),
            "components_measured": sum(r["components_status"] == "ok" for r in rs),
            "components_with_varying_target": sum(r["components_target_varies"] > 0 for r in rs),
            "timeout_stages": dict(Counter(r["stage"] for r in rs if r["status"] == "timeout")),
        }
        summary["representation_medians"][g] = {k: statistics.median(r[k] for r in rs if r[k] is not None) for k in ("dsl_variables", "variables", "equations", "max_degree", "total_terms", "nondeg_count", "dsl_conditions", "dsl_constructions")}
    records = []
    polybin = lambda r: None if r["variables"] is None else "<=8" if r["variables"] <= 8 else "9..12" if r["variables"] <= 12 else ">=13"
    for label, key in [("dsl_variables", lambda r: r["dsl_variables"]), ("poly_variables_bins", polybin),
                       ("poly_variables_and_degree", lambda r: None if polybin(r) is None else (polybin(r), "<=3" if r["max_degree"] <= 3 else ">=4"))]:
        ss, est = strata(focal, label, key)
        records.extend(ss)
        summary["standardization"][label] = est
    # A small, reproducible, cost-based subset for optional paired algebra runs.
    # All are lex-timeout cases with complete saved candidate polynomials.
    selected = []
    for g in ("G", "I"):
        pool = [r for r in focal if r["dimension_group"] == g and r["status"] == "timeout" and r["stage"] == "groebner_lex" and r["proposed_candidates"] == r["saved_candidates"] > 0]
        selected.extend(sorted(pool, key=lambda r: (r["total_terms"], r["variables"], r["id"]))[:3])
    summary["optional_paired_subset_cost_rule"] = [{k: r[k] for k in ("id", "dimension_group", "variables", "total_terms", "max_degree", "result_path")} for r in selected]
    csvout("case-matrix.csv", rows)
    csvout("strata.csv", records)
    csvout("archived-certificates.csv", certificates)
    output("summary.json", summary)
    output("source-manifest.json", SOURCES)
    print(json.dumps({"counts": summary["counts"], "standardization": summary["standardization"],
                      "paired_subset": summary["optional_paired_subset_cost_rule"], "source_files": len(SOURCES)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
