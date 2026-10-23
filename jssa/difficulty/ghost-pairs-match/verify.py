"""Audit denominators, labels, legacy coinc agreement and all-G-pair matching."""
import csv
import hashlib
import json
import math
from collections import Counter
from pathlib import Path

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[2]


def rows(path):
    with path.open() as f:
        return list(csv.DictReader(f))


def main():
    starts = rows(OUT / "per-start.csv")
    problems = rows(OUT / "per-problem.csv")
    summaries = rows(OUT / "summary.csv")
    manifest = json.loads((OUT / "manifest.json").read_text())
    for name, sha in manifest["input_sha256"].items():
        assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == sha, name
    fixed = (OUT / "README.md").read_text().split("## 実行結果")[0]
    assert hashlib.sha256(fixed.encode()).hexdigest() == manifest["fixed_definitions_sha256"]
    assert hashlib.sha256((OUT / "analyze.py").read_bytes()).hexdigest() == manifest["script_sha256"]
    index = {(r["id"], int(r["k"])): r for r in starts}
    assert len(index) == len(starts)
    for p in problems:
        raw = json.loads((OUT.parent / "minima/raw-323" / (p["id"]+".json")).read_text())
        recs = raw.get("records") or []
        assert len(recs) == int(p["n_records"])
        cats = Counter()
        for r in recs:
            s = index[(p["id"], r["k"])]
            assert s["cls"] == r.get("cls", "")
            assert (s["category"] == "success") == (r.get("cls") == "hit")
            if s["target_state"] == "missing" and s["cls"] != "hit":
                assert s["category"] in ("failure_geometry_missing", "class_unknown")
            if s["category"] == "collision_failure":
                assert json.loads(s["matching_pairs"])
                metric = s["coinc_G"] if p["group"] == "G_yes" else s["coinc_any"]
                assert float(metric) < 1e-4
            cats[s["category"]] += 1
        for c in ["success", "collision_failure", "other_failure", "failure_geometry_missing", "class_unknown"]:
            assert cats[c] == int(p[c]), (p["id"], c)
    for row in summaries:
        ps = [p for p in problems if p["group"] == row["group"] and (row["stratum"] == "all" or p["stratum"] == row["stratum"])]
        assert len(ps) == int(row["n_problems"])
        for field in ["n_records", "n_unrecorded", "fewer_than_requested", "success", "collision_failure", "other_failure", "failure_geometry_missing", "class_unknown"]:
            assert sum(int(p[field]) for p in ps) == int(row[field])
    old = rows(OUT.parent / "ghost-1023/endpoints_v1.csv")
    agreement = Counter()
    mismatches = []
    for r in old:
        s = index.get((r["id"], int(r["k"])))
        if s is None:
            agreement["legacy_record_not_in_population"] += 1
        elif not r["coinc"] or not s["coinc_any"]:
            agreement["one_or_both_missing"] += 1
        else:
            value, saved = float(s["coinc_any"]), float(r["coinc"])
            if math.isclose(value, saved, rel_tol=5.01e-4, abs_tol=1e-300):
                agreement["agrees_with_legacy_4_significant_digits"] += 1
            else:
                agreement["finite_disagreement"] += 1
                mismatches.append(dict(id=r["id"], k=r["k"], old=saved, new=value))
    diag = Counter()
    for s in starts:
        if s["group"] != "G_yes" or s["cls"] == "hit":
            continue
        if s["category"] == "collision_failure" and s["coinc_any"] and float(s["coinc_any"]) < float(s["coinc_G"]):
            diag["G_collision_failure_global_min_not_G"] += 1
        if s["any_state"] == "positive" and s["target_state"] == "negative":
            diag["any_pair_collision_but_no_G_pair_collision"] += 1
    result = dict(status="PASS", n_problems=len(problems), n_saved_records=len(starts),
                  legacy_comparison=dict(agreement), legacy_finite_mismatches=mismatches,
                  G_yes_diagnostics=dict(diag),
                  verification="All input and fixed-definition hashes, raw-record membership, labels, denominators, sums, threshold and missing handling checked.")
    assert not mismatches, mismatches[:5]
    (OUT / "validation.json").write_text(json.dumps(result, indent=2)+"\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
