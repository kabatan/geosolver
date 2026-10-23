"""Paired bootstrap after primary analysis; no additional local optimization."""
import json
import math
from pathlib import Path

import numpy as np

from analyze_restarts import HERE, ROOT, digest, dynamic, safe, write_csv, write_json


def all_two(c, p0, p1):
    with np.errstate(divide="ignore", invalid="ignore"):
        value = c * (1 / p0 + 1 / p1 - 1 / (p0 + p1))
    return np.where((p0 > 0) & (p1 > 0), value, np.inf)


def summarize(values):
    values = np.sort(np.asarray(values, dtype=float))
    # Order statistics avoid interpolating finite and infinite values.
    return [float(values[int(.025 * (len(values) - 1))]),
            float(values[int(.975 * (len(values) - 1))])]


def main():
    summary = json.loads((HERE / "summary.json").read_text())
    cases = [r for r in summary["multi_no_overhead"]
             if r["complete_seed0"] and r["complete_seed1"]]
    rng = np.random.default_rng(20261023)
    rows = []
    for row in cases:
        cid = row["case_id"]
        obj = json.loads((ROOT / "jssa/difficulty/minima/raw-323-seed1" / (cid + ".json")).read_text())
        assert len(obj["references"]) == 2
        n = len(obj["records"])
        times = np.array([r["nfev"] for r in obj["records"]], dtype=float)
        labels = np.array([r["ref"] if r["cls"] == "hit" else -1 for r in obj["records"]])
        b = row["first_cut_evaluations"]
        b = math.inf if b == "inf" else b
        base_c = times
        short_c = np.minimum(times, b)
        base_p = [(labels == j).astype(float) for j in range(2)]
        short_p = [((labels == j) & (times <= b)).astype(float) for j in range(2)]
        idx = rng.integers(n, size=(4000, n))
        cb, cs = base_c[idx].mean(1), short_c[idx].mean(1)
        pb, ps = [v[idx].mean(1) for v in base_p], [v[idx].mean(1) for v in short_p]
        first_ratio = (cs / (ps[0] + ps[1])) / (cb / (pb[0] + pb[1]))
        all_ratio = all_two(cs, *ps) / all_two(cb, *pb)
        cm = (cs + cb) / 2
        pm = [(ps[j] + pb[j]) / 2 for j in range(2)]
        mix_ratio = all_two(cm, *pm) / all_two(cb, *pb)
        mean_c = float((short_c.mean() + base_c.mean()) / 2)
        mean_p = [float((short_p[j].mean() + base_p[j].mean()) / 2) for j in range(2)]
        mix_dp = dynamic([(mean_c, mean_p, [])], fixed=0)[0]
        mix_formula = float(all_two(mean_c, *mean_p))
        assert abs(mix_dp - mix_formula) < 1e-8
        assert np.all(mix_ratio <= 2.0000000001)
        rows.append(dict(case_id=cid, n=n, first_cut=b,
                         first_ratio_point=row["first_ratio"], first_ratio_interval=summarize(first_ratio),
                         all_ratio_point=row["all_firstcut_ratio"], all_ratio_interval=summarize(all_ratio),
                         half_mix_all_ratio=mix_dp / row["all_baseline"],
                         half_mix_all_ratio_interval=summarize(mix_ratio),
                         bootstrap_n=4000, bootstrap_seed=20261023))
    write_csv("posthoc-bootstrap.csv", rows)
    write_json("posthoc-bootstrap.json", dict(
        status="posthoc paired endpoint bootstrap; training policy fixed; conditional on observed support",
        plan_sha256=digest(HERE / "posthoc-check-plan.md"), script_sha256=digest(Path(__file__)), rows=rows))
    for row in rows:
        print(json.dumps(safe(row)))


if __name__ == "__main__":
    main()
