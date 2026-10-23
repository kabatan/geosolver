"""Read-only census of existing records; writes only beside this script.

No solver, optimizer, external process, network, or third-party package is used.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import math
import statistics
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[3]
SOURCES: dict[str, dict] = {}


def read(path: str) -> str:
    assert "sealed-raw" not in path and "unseen-1983" not in path
    data = (ROOT / path).read_bytes()
    assert len(data) < 30 * 1024**2
    SOURCES[path] = {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}
    return data.decode("utf-8")


def table(path: str) -> list[dict]:
    return list(csv.DictReader(io.StringIO(read(path))))


def obj(path: str):
    return json.loads(read(path))


def dump(name: str, data) -> None:
    text = json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    assert len(text.encode()) < 10 * 1024**2
    (OUT / name).write_text(text)


def write_csv(name: str, rows: list[dict]) -> None:
    with (OUT / name).open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def truth(value) -> bool:
    return value in (True, "True", "true", "1", 1)


def raw_summary(data: dict) -> dict:
    records = data.get("records", [])
    counts = Counter(r.get("cls", "missing") for r in records)
    n, hits = len(records), counts["hit"]
    return {
        "n": n, "hits": hits, "p": hits / n if n else None,
        "n_vars": data.get("n_vars"), "seed": data.get("seed"),
        "classes": dict(counts),
        "count_agrees": dict(counts) == data.get("counts", {}),
    }


def main() -> None:
    started = time.monotonic()
    lock = json.loads((OUT / "registration-lock.json").read_text())
    for name, digest in lock["files"].items():
        assert hashlib.sha256((OUT / name).read_bytes()).hexdigest() == digest, name
    comparison = table("jssa/strategy/astra-consult-17/H/sources/comparison-cases.csv")
    certificates = table("jssa/difficulty/certify-all/per-case.csv")
    cert = {r["id"]: r for r in certificates if r["group"] == "development323"}
    h = {r["id"]: r for r in table("jssa/strategy/astra-consult-17/H/classification.csv")}
    attrib = table("jssa/results/mechanism-attribution/attribution.csv")
    stages = table("jssa/results/stage-profile-20261023/per-case.csv")
    runs = defaultdict(list)
    for r in attrib:
        runs[r["case_id"]].append(r)
    assert len(comparison) == len(cert) == 323
    assert len(attrib) == len(stages) == 969
    assert len({(r["case_id"], r["seed"]) for r in attrib}) == 969
    assert all(len(v) == 3 for v in runs.values())
    raw = {}
    for seed, folder in [(0, "raw-323"), (1, "raw-323-seed1")]:
        for p in sorted((ROOT / "jssa/difficulty/minima" / folder).glob("*.json")):
            d = obj(str(p.relative_to(ROOT)))
            raw[(d["case_id"], seed)] = raw_summary(d)

    matrix, discrepancies = [], []
    stage_lookup = {(r["case_id"], r["seed"]): r for r in stages}
    for c in comparison:
        cid = c["id"]
        a, b = raw[(cid, 0)], raw[(cid, 1)]
        rr = sorted(runs[cid], key=lambda r: int(r["seed"]))
        ncorrect = sum(truth(r["matched"]) for r in rr)
        if ncorrect != int(c["geo_matched"]):
            discrepancies.append({"id": cid, "comparison": c["geo_matched"], "attribution": ncorrect})
        for r in rr:
            if truth(r["matched"]) != truth(stage_lookup[(cid, r["seed"])]["correct"]):
                discrepancies.append({"id": cid, "seed": r["seed"], "stage_vs_attribution": True})
        row = {
            "id": cid, "n_vars": a["n_vars"],
            "starts0": a["n"], "hits0": a["hits"], "p0": a["p"],
            "starts1": b["n"], "hits1": b["hits"], "p1": b["p"],
            "msolve_class": c["msolve_class"], "geo_matched_comparison": int(c["geo_matched"]),
            "geo_matched_attribution": ncorrect,
            "cert_status": cert[cid]["status"], "cert_source_kind": cert[cid]["source_kind"],
            "cert_candidates": cert[cid]["saved_candidate_count"],
            "h_class": h.get(cid, {}).get("classification", ""),
            "h_evidence": h.get(cid, {}).get("evidence_code", ""),
            "h_physical_dimension": h.get(cid, {}).get("physical_dimension", ""),
            "source0": rr[0]["answer_source_uid_prefix"],
            "source1": rr[1]["answer_source_uid_prefix"],
            "source2": rr[2]["answer_source_uid_prefix"],
            "correct0": truth(rr[0]["matched"]), "correct1": truth(rr[1]["matched"]),
            "correct2": truth(rr[2]["matched"]),
        }
        matrix.append(row)

    selected = [r.copy() for r in matrix if r["n_vars"] > 0 and r["starts0"] > 0 and r["hits0"] == 0]
    assert len(selected) == 29
    for r in selected:
        r["zero_both"] = r["starts1"] > 0 and r["hits1"] == 0
        r["p2_qualifies"] = r["zero_both"] and r["geo_matched_comparison"] == 3
        r["all_three_exact"] = all(r[f"source{i}"] == "search/exact_polynomial" for i in range(3))
        n = r["starts0"] + r["starts1"]
        r["p_upper95_iid_reference"] = -math.expm1(math.log(.05) / n) if r["zero_both"] else None
        r["success200_upper95_iid_reference"] = -math.expm1(math.log(.05) * 200 / n) if r["zero_both"] else None

    write_csv("case-matrix.csv", matrix)
    write_csv("selected-case-validation.csv", selected)
    p1 = sum(r["zero_both"] for r in selected)
    p2_rows = [r for r in selected if r["p2_qualifies"]]
    p3 = sum(r["all_three_exact"] for r in p2_rows)
    failed_enum = [r for r in matrix if r["msolve_class"] != "answer_set_matches"]
    posdim = [r for r in matrix if r["msolve_class"] in ("positive_dimensional", "free_parameter")]
    failed_cert = [r for r in matrix if r["cert_status"] != "certified_saved_endpoint_set"]
    deform_ids = {cid for cid, r in h.items() if r["classification"] == "genuine_shape_motion"}
    h_counts = dict(Counter(r["classification"] for r in h.values()))
    assert len(deform_ids) == 16
    counts = {}
    for cls in sorted({r["msolve_class"] for r in matrix}):
        ss = [r for r in matrix if r["msolve_class"] == cls]
        counts[cls] = {
            "n": len(ss), "full_any": sum(r["geo_matched_comparison"] > 0 for r in ss),
            "full_all3": sum(r["geo_matched_comparison"] == 3 for r in ss),
            "certificate": sum(r["cert_status"] == "certified_saved_endpoint_set" for r in ss),
            "certificate_statuses": dict(Counter(r["cert_status"] for r in ss)),
        }

    h_detail = {}
    for code in sorted({r["h_evidence"] for r in posdim}):
        ss = [r for r in posdim if r["h_evidence"] == code]
        h_detail[code] = {
            "n": len(ss), "full_all3": sum(r["geo_matched_comparison"] == 3 for r in ss),
            "certified": sum(r["cert_status"] == "certified_saved_endpoint_set" for r in ss),
            "local_hit_problem_seed0": sum(r["hits0"] > 0 for r in ss),
            "local_hit_problem_seed1": sum(r["hits1"] > 0 for r in ss),
            "median_p0": statistics.median(r["p0"] for r in ss if r["p0"] is not None) if any(r["p0"] is not None for r in ss) else None,
            "median_p1": statistics.median(r["p1"] for r in ss if r["p1"] is not None) if any(r["p1"] is not None for r in ss) else None,
        }
    zero_sources = Counter(r[f"source{i}"] for r in p2_rows for i in range(3))
    summary = {
        "created_utc": datetime.now(timezone.utc).isoformat(), "registration": lock,
        "comparison_attribution_discrepancies": discrepancies,
        "raw_counts": {str(s): {"cases": sum(k[1] == s for k in raw), "records": sum(v["n"] for k, v in raw.items() if k[1] == s), "classes": dict(sum((Counter(v["classes"]) for k, v in raw.items() if k[1] == s), Counter()))} for s in (0, 1)},
        "raw_stored_counts_disagreements": [{"id": cid, "seed": s} for (cid, s), d in raw.items() if not d["count_agrees"] and d["n"]],
        "comparison_classes": counts,
        "enumeration_not_match": {"n": len(failed_enum), "full_any": sum(r["geo_matched_comparison"] > 0 for r in failed_enum), "full_all3": sum(r["geo_matched_comparison"] == 3 for r in failed_enum), "certified": sum(r["cert_status"] == "certified_saved_endpoint_set" for r in failed_enum)},
        "certification_statuses_development": dict(Counter(r["cert_status"] for r in matrix)),
        "certification_by_dimension": {"positive_dimension": h_detail, "h_classification_counts": h_counts},
        "h_evidence_counts": dict(Counter(r["evidence_code"] for r in h.values())),
        "unification_necessary_conditions": {
            "genuine_deformation_ids": sorted(deform_ids),
            "genuine_in_enum_failure": sum(r["id"] in deform_ids for r in failed_enum),
            "genuine_in_cert_failure": sum(r["id"] in deform_ids for r in failed_cert),
            "all_posdim_in_enum_failure": sum(r["msolve_class"] in ("positive_dimensional", "free_parameter") for r in failed_enum),
            "all_posdim_in_cert_failure": sum(r["msolve_class"] in ("positive_dimensional", "free_parameter") for r in failed_cert),
            "denominators_enum_cert": [len(failed_enum), len(failed_cert)],
        },
        "validation": {
            "selected": len(selected), "selected_full_any": sum(r["geo_matched_comparison"] > 0 for r in selected), "selected_full_all3": sum(r["geo_matched_comparison"] == 3 for r in selected),
            "P1": {"observed": p1, "denominator": 29, "required": 24, "passed": p1 >= 24},
            "P2": {"observed": len(p2_rows), "required": 20, "passed": len(p2_rows) >= 20},
            "P3": {"observed": p3, "denominator": len(p2_rows), "passed": p3 > len(p2_rows) / 2},
            "zero_both_all3_sources": dict(zero_sources),
            "new_hits_seed1": [{k: r[k] for k in ("id", "starts1", "hits1", "p1")} for r in selected if not r["zero_both"]],
            "both_seeds_total_starts": sum(r["starts0"] + r["starts1"] for r in selected if r["zero_both"]),
            "p2_ids": [r["id"] for r in p2_rows],
        },
    }
    # Secondary survey of available summaries, not a new optimization campaign.
    gmb = obj("jssa/results/gmb-success-definition/summary.json")
    role = obj("jssa/difficulty/role-reassign/summary.json")
    ghost = obj("jssa/difficulty/false-attractors/summary.json")
    redraw = table("jssa/difficulty/full-solver-redraw-cloud/out/A/per-problem.csv")
    holdout = table("jssa/difficulty/holdout-1023/out/scored.csv")
    new = table("jssa/difficulty/new2026-predict/outcomes.csv")
    summary["secondary_survey"] = {
        "gmb": gmb,
        "role_reassign": {k: role[k] for k in ("completed_pairs", "gains", "losses", "strata", "A_decision")},
        "false_attractors": {k: ghost[k] for k in ("expected_problems", "processed_problems", "primary", "main_causes", "local_searches_run")},
        "redraw_available_rows": len(redraw),
        "redraw_success_counts": {arm: sum(int(r[f"ok_{arm}"]) for r in redraw) for arm in ("plain", "redraw")},
        "redraw_lm_used_problems": {arm: sum(float(r[f"lm_ran_{arm}"]) > 0 for r in redraw) for arm in ("plain", "redraw")},
        "holdout_n": len(holdout),
        "holdout_Y_minus_E_top": sorted([{"id": r["case_id"], "n": int(r["N"]), "delta": float(r["pY"]) - float(r["pE"])} for r in holdout], key=lambda r: r["delta"], reverse=True)[:5],
        "new2026_outcome_count": len(new),
    }
    summary["elapsed_seconds"] = time.monotonic() - started
    summary["optimizer_calls"] = 0
    dump("summary.json", summary)
    dump("sources.json", SOURCES)
    print(json.dumps({k: summary[k] for k in ("elapsed_seconds", "comparison_attribution_discrepancies", "enumeration_not_match", "h_evidence_counts", "unification_necessary_conditions", "validation")}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
