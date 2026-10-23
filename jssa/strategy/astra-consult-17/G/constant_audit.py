"""Post-hoc, evaluations only: inspect rejected good trials under constant offset.

No local optimizer is called. This does not change the R1--R5 verdicts.
"""
from __future__ import annotations

import csv
import json
import math

import numpy as np

from common import (HERE, case_context, equality, classify, reference_values,
                    smb, ExternalPipelineConfig, write_json)


def main():
    rows = []
    for path in sorted((HERE / "mechanism-data").glob("*.json")):
        data = json.loads(path.read_text())
        if "records" not in data:
            continue
        case, bundle, ev, raw, bounds, lo, width = case_context(data["id"])
        refs = reference_values(case["answer"])
        config = ExternalPipelineConfig.production_baseline_tier(seed=17007, total_time_budget_sec=180).search
        for rec in data["records"]:
            if rec["N"]["cls"] != "hit" or rec["C"]["cls"] == "hit":
                continue
            out = {"id": data["id"], "k": rec["k"], "F_start": rec["F"],
                   "C_raw_info": rec["C"]["native"]["raw_info"],
                   "CS_raw_info": rec["CS"]["native"]["raw_info"],
                   "tail_rejected_hit": 0, "tail_rejected_hit_equal_float_norm": 0,
                   "last_trial_rejected_hit": False}
            trials = rec["C"]["native"]["tail"]
            for i, trial in enumerate(trials):
                if trial["decision"] != "rejected" or trial["eq_ss"] > 1e-16:
                    continue
                # Same original final validation used to score all other arms.
                cand = smb._build_candidate(evaluator=ev, config=config, bounds=bounds,
                    values=np.array(trial["x"]), origin_seed=17007,
                    family_code=smb._LM_FAMILY_CODE, origin_start_point_index=rec["k"],
                    telemetry=smb._SearchTelemetry())
                if classify(ev, cand, refs)["cls"] != "hit":
                    continue
                out["tail_rejected_hit"] += 1
                out["last_trial_rejected_hit"] |= i == len(trials)-1
                base = trial["base"]
                e0, e1 = equality(ev, base["x"]), equality(ev, trial["x"])
                n0 = math.hypot(*e0, base["guard"], base["hard"])
                n1 = math.hypot(*e1, trial["guard"], trial["hard"])
                out["tail_rejected_hit_equal_float_norm"] += n0 == n1
                out.update(last_base_eq_ss=base["eq_ss"], last_trial_eq_ss=trial["eq_ss"],
                           last_base_float_norm=n0, last_trial_float_norm=n1)
            rows.append(out)
    columns = sorted({k for r in rows for k in r})
    with (HERE / "constant-rejected-trials.csv").open("w") as f:
        w = csv.DictWriter(f, fieldnames=columns); w.writeheader(); w.writerows(rows)
    summary = {"posthoc_evaluations_only": True, "denominator_N_hit_C_fail": len(rows),
               "C_fail_with_rejected_hit_in_last8": sum(r["tail_rejected_hit"] > 0 for r in rows),
               "C_fail_with_rejected_hit_equal_float_norm": sum(r["tail_rejected_hit_equal_float_norm"] > 0 for r in rows),
               "C_fail_last_trial_rejected_hit": sum(r["last_trial_rejected_hit"] for r in rows),
               "note": "math.hypot is an independent float norm calculation; native MINPACK fnorm/ratio variables are not read"}
    write_json(HERE / "constant-audit.json", summary)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
