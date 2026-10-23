"""Read-only mathematical/data audit; writes only its receipt within HERE.

No additional local optimizations and no reads of Q1/Q2 data.
"""
from collections import Counter
import csv
import json
from pathlib import Path
import numpy as np
from scipy.stats import spearmanr
from experiment import HERE, ROOT, RAW, verify_freeze, object_sha, now, sha, write_json


def main():
    manifest = verify_freeze()
    summary = json.loads((HERE / "summary.json").read_text())
    csv_rows = {r["id"]: r for r in csv.DictReader((HERE / "per-problem.csv").open())}
    errors = []
    count = Counter()
    classes = Counter()
    input_ids = [r["id"] for r in manifest]
    assert sorted(csv_rows) == sorted(input_ids)
    assert sorted(p.stem for p in (HERE / "diagnostics").glob("*.json")) == sorted(input_ids)
    assert sorted(p.stem for p in (HERE / "paired").glob("*.json")) == sorted(input_ids)
    for row in manifest:
        cid = row["id"]
        d = json.loads((HERE / "diagnostics" / f"{cid}.json").read_text())
        p = json.loads((HERE / "paired" / f"{cid}.json").read_text())
        raw = json.loads((RAW / f"{cid}.json").read_text())
        saved = {r["k"]: r for r in raw["records"]}
        lo, hi = np.array(d["bounds"]).T
        recreated = lo + (hi-lo) * np.random.default_rng(d["seed"]).random((256, len(lo)))
        assert len(d["records"]) == 256
        den = cross = 0
        for i, r in enumerate(d["records"]):
            assert np.array_equal(recreated[i], r["start"])
            if r["status"] == "decrease":
                den += 1
                cross += r["trial_F"] is False
                assert r["start_F"] is True
                assert r["trial_ss"] <= .99 * r["start_ss"]
                assert np.all(np.array(r["trial"]) >= lo) and np.all(np.array(r["trial"]) <= hi)
                assert r["alpha"] in [2.0**(-k) for k in range(9)]
                assert np.allclose(r["trial"], recreated[i] + r["alpha"] * np.array(r["delta"]), atol=0, rtol=0)
                count["accepted_diagnostic_points"] += 1
                count["equality_decreases_1pct"] += r["trial_eq_ss"] <= .99*r["start_eq_ss"]
        assert den == d["denominator"] and cross == d["crossings"]
        assert d["W"] == (cross/den if den >= 32 else None)
        expected_group = "undetermined" if den < 32 else "high" if cross/den >= .25 else "low" if cross/den <= .05 else "middle"
        assert d["group"] == expected_group
        selected_F = [s for s in p["records"] if s["F"]]
        selected_I = [s for s in p["records"] if not s["F"]]
        assert len(selected_F) == min(30, p["saved_n_F"])
        assert len(selected_I) == min(30, p["saved_n_I"])
        assert len({s["k"] for s in p["records"]}) == len(p["records"])
        for s in p["records"]:
            count["paired_starts"] += 1
            assert s["start"] == saved[s["k"]]["start"]
            assert s["saved_cls"] == saved[s["k"]]["cls"]
            for arm in ["B", "N"]:
                z = s[arm]
                count["local_calls"] += 1
                classes[(arm, z["cls"])] += 1
                if arm == "B":
                    assert z["no_hard_calls"] == 0
                if z["cls"] == "hit":
                    assert z["hard"] is True and z["guard_ok"] is True and z["res"] <= 1e-8
                    assert np.all(np.asarray(z["x"]) >= lo) and np.all(np.asarray(z["x"]) <= hi)
                    assert any(abs(z["ans"]-ref) <= 1e-6*max(1,abs(ref)) for ref in raw["references"])
                    if arm == "N":
                        assert z["no_hard_calls"] > 0
                if z["cls"] == "timeout":
                    count[f"{arm}_timeouts"] += 1
            count["baseline_cls_equal"] += s["B"]["cls"] == s["saved_cls"]
            if s["B"].get("x") is not None and s["saved_x"] is not None:
                count["baseline_coordinate_comparable"] += 1
                count["baseline_coordinate_exact"] += s["B"]["x"] == s["saved_x"]
        cr = csv_rows[cid]
        for group, selected in [("F", selected_F), ("I", selected_I), ("all", p["records"])]:
            if not selected:
                continue
            difference = sum((s["N"]["cls"] == "hit") - (s["B"]["cls"] == "hit") for s in selected) / len(selected)
            assert abs(float(cr[f"D_{group}_raw"]) - difference) < 1e-14
    assert count["paired_starts"] == 11445
    assert count["local_calls"] == 22890
    # Independent SciPy implementation checks the two primary rank correlations.
    stats_checks = {}
    for key in ["R_saved", "D_F"]:
        rr = [r for r in csv_rows.values() if r["method"] == "LM" and r["W"] and r[key]]
        value = float(spearmanr([float(r["W"]) for r in rr], [float(r[key]) for r in rr]).statistic)
        expected = summary["associations"]["LM"][key]
        assert len(rr) == expected["n"] and abs(value - expected["rho"]) < 1e-14
        stats_checks[key] = {"n": len(rr), "independent_scipy_rho": value}
    assert summary["census_disagreements"] == []
    before = json.loads((HERE / "before-local.json").read_text())
    for name, digest in before["inputs"].items():
        assert sha(ROOT/name) == digest
    largest = max((p.stat().st_size, str(p.relative_to(HERE))) for p in HERE.rglob("*") if p.is_file())
    assert largest[0] < 20_000_000
    for phase in ["diagnose", "paired"]:
        run = json.loads((HERE / f"{phase}-run.json").read_text())
        assert run["errors"] == [] and run["tasks"] == 292 and run["workers"] <= 4
    result = {"utc": now(), "passed": True, "counts": dict(count), "statistics": stats_checks,
              "classes": {f"{k[0]}:{k[1]}":v for k,v in sorted(classes.items())},
              "largest_file_bytes": largest[0], "largest_file": largest[1],
              "frozen_inputs_and_source_unchanged": True,
              "census_matches_G": True, "Q2_executed": False, "new_local_calls_in_this_audit": 0}
    write_json(HERE / "delivery-audit.json", result)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
