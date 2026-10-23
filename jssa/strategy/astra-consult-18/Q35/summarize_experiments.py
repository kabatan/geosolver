"""Summarize the locked Q35 experiments, retaining negative predictions."""
import csv
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent


def main():
    base = json.loads((HERE / "summary.json").read_text())
    chosen = base["optional_paired_subset_cost_rule"]
    paired = []
    for ch in chosen:
        d = json.loads((HERE / "paired" / (ch["id"] + ".json")).read_text())
        a, b = d["arms"]
        assert a["label"] == "original" and b["label"] == "linear"
        at8 = a["basis_complete"] and a["basis_seconds"] <= 8
        bt8 = b["basis_complete"] and b["basis_seconds"] + b["preprocessing_seconds"] <= 8
        paired.append({"id": ch["id"], "group": ch["dimension_group"],
                       "original_nvars": len(a["input_variables"]), "linear_nvars": len(b["output_variables"]),
                       "original_status": a["status"], "linear_status": b["status"],
                       "original_basis_seconds": a["basis_seconds"], "linear_basis_seconds": b["basis_seconds"],
                       "linear_preprocessing_seconds": b["preprocessing_seconds"],
                       "original_basis_by_8s": at8, "original_basis_by_30s": a["basis_complete"],
                       "linear_with_preprocessing_by_8s": bt8,
                       "P2_case": not at8 and bt8,
                       "P3_case": a["basis_complete"] and 8 < a["basis_seconds"] <= 30})
    components = []
    for cid in ("AIME-2009-I-12", "HMMT-2006-FEB-GEO-01", "JMO-2013-PRE-08"):
        d = json.loads((HERE / "components" / (cid + ".json")).read_text())
        a, b = d["arms"]
        components.append({"id": cid, "before": a["status"], "after": b["status"],
                           "before_total_seconds": a["total_seconds"], "after_total_seconds": b["total_seconds"],
                           "after_eliminant": b.get("eliminant_factored"),
                           "P1_case": a["status"] == "no_univariate" and b["certificate_verified"] and b["matches_predicted_eliminant"]})
    seed = json.loads((HERE / "seed-candidates.json").read_text())
    predictions = {
        "P1_components": {"successes": sum(r["P1_case"] for r in components), "n": 3, "required": 3},
        "P2_representation": {"successes": sum(r["P2_case"] for r in paired), "n": 6, "required": 1},
        "P3_time": {"successes": sum(r["P3_case"] for r in paired), "n": 6, "required": 1},
        "P4_seed_candidates": {"successes": seed["P4_same_nonempty"], "n": 7, "required": 7},
    }
    for p in predictions.values(): p["passed"] = p["successes"] >= p["required"]
    seed_counts = {}
    for g in ("G", "I"):
        rs = [r for r in seed["cases"] if r["group"] == g]
        seed_counts[g] = {"n": len(rs), "nonempty_seed0": sum(r["n0"] > 0 for r in rs),
                          "nonempty_seed1": sum(r["n1"] > 0 for r in rs),
                          "same_candidate_set": sum(r["same_numeric_candidate_set"] for r in rs),
                          "changed_ids": [r["id"] for r in rs if not r["same_numeric_candidate_set"]]}
    result = {"created_utc": datetime.now(timezone.utc).isoformat(), "predictions": predictions,
              "paired": paired, "components": components, "seed_candidate_counts": seed_counts,
              "new_optimizer_calls": 0, "full_solver_calls": 0, "max_active_workers": 1,
              "total_recorded_arm_seconds": sum(json.loads(p.read_text())["arms"][i]["total_seconds"]
                  for folder in ("paired", "components") for p in (HERE/folder).glob("*.json") for i in (0, 1))}
    (HERE / "experiment-summary.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    with (HERE / "paired.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(paired[0]))
        w.writeheader(); w.writerows(paired)
    print(json.dumps({"predictions": predictions, "seed_candidate_counts": seed_counts,
                      "total_recorded_arm_seconds": result["total_recorded_arm_seconds"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__": main()
