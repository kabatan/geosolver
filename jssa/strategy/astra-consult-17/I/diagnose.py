"""Post-hoc descriptions of where the fixed selector failed; no new rules fitted."""
from __future__ import annotations
import csv
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]


def rows(path):
    with path.open() as f:
        return list(csv.DictReader(f))


def main():
    data = rows(HERE / "local-per-problem.csv")
    pred = {r["id"]: r for r in rows(ROOT / "jssa/difficulty/start-feasibility-1023/predictions.csv")}
    lost = []
    for r in data:
        if int(r["pilot20_any_hit"]) < int(r["feasible_any_hit"]):
            lost.append({k: r[k] for k in ("id", "M", "pilot_n", "pilot_f", "pilot_q_f", "pilot_q_i", "choice", "plain_p", "feasible_p", "pilot20_p")}
                         | {"phi0": pred[r["id"]]["phi0"]})
    disagreement = [{k: r[k] for k in ("id", "pilot_f", "pilot_q_f", "pilot_q_i", "choice", "oracle_label_choice", "pilot20_p", "oracle_labels20_p")}
                    for r in data if r["choice"] != r["oracle_label_choice"]]
    unavailable = [r for r in data if int(r["pilot_n"]) < 20 or not 2 <= int(r["pilot_f"]) <= 18]
    large_benefit = [r for r in data if float(r["full_p_feasible"]) - float(r["full_p_plain"]) >= .2]
    unseen_f = [r for r in data if int(r["pilot_f"]) == 0]
    zero_observation_probability = {str(phi): (1-phi)**20 for phi in (.005, .01, .05, .1)}
    # Actual data verification: raw output hashes remain unchanged.
    mismatches = []
    checked = set()
    for filename, field in [("provenance.json", "input_sha256"), ("feature-provenance.json", "feature_input_hashes")]:
        prov = json.loads((HERE / filename).read_text())
        for path, expected in prov[field].items():
            if path in checked:
                continue
            checked.add(path)
            actual = hashlib.sha256((ROOT / path).read_bytes()).hexdigest()
            if expected != actual:
                mismatches.append(path)
    assert not mismatches, mismatches
    result = {"status": "post-hoc explanation, not a new validated predictor",
              "insufficient_FI_support": len(unavailable), "zero_F_in_pilot": len(unseen_f),
              "large_full_stream_benefit_ge_0_2": len(large_benefit),
              "large_benefit_without_support": sum(r in unavailable for r in large_benefit),
              "large_benefit_zero_F": sum(r in unseen_f for r in large_benefit),
              "lost_any_hit_vs_feasible": lost, "candidate_vs_label_disagreements": disagreement,
              "probability_no_feasible_in_20_iid": zero_observation_probability,
              "unchanged_input_hashes_checked": len(checked), "hash_mismatches": mismatches}
    (HERE / "diagnostics.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
