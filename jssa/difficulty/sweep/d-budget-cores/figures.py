"""Read-only evaluation of saved accepted coordinates, without new search.

Compare coordinates and labelled pairwise distances separately. The latter
identifies congruent figures including mirror images, but not scale changes.
"""
from __future__ import annotations

import argparse
from collections import Counter
import csv
import hashlib
import json
import math
from pathlib import Path
import sys

BASE = Path(__file__).resolve().parent
ROOT = BASE.parents[3]
sys.dont_write_bytecode = True
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "jssa/difficulty"), str(ROOT)]
from probe_basins import answer_float, construction_coordinates
from geosolver import GeometryProblem
from geosolver.engine.standard.problem.load_problem_bundle import load_problem_bundle
from geosolver.runtime.integrity import source_tree_hash

TOL = 1e-7


def close(a, b, tol=TOL):
    return len(a) == len(b) and all(abs(x-y) <= tol * max(1.0, abs(x), abs(y)) for x, y in zip(a, b))


def cluster_index(representatives, vector, tol=TOL):
    for i, other in enumerate(representatives):
        if close(other, vector, tol):
            return i
    representatives.append(vector)
    return len(representatives)-1


def write_csv(name, rows):
    with (BASE / name).open("w") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows({k: json.dumps(v) if isinstance(v, (list, dict)) else v for k, v in r.items()} for r in rows)


def main(preview=False):
    manifest = json.loads((BASE / "manifest.json").read_text())
    assert source_tree_hash() == manifest["source_hash"]
    receipts = {r["job"]: r for p in (BASE / "receipts").glob("*.json") if (r := json.loads(p.read_text()))}
    if not preview:
        assert len(receipts) == len(manifest["jobs"]), "finish every fixed job first"
    raw = Path(manifest["raw_root"])
    cases_out, runs_out, details = [], [], {}
    for case in manifest["cases"]:
        if preview and any(j["job"] not in receipts for j in manifest["jobs"] if j["id"] == case["id"]):
            continue
        dsl = json.loads((ROOT / case["dsl_path"]).read_text())
        assert hashlib.sha256((ROOT / case["dsl_path"]).read_bytes()).hexdigest() == case["dsl_sha256"]
        bundle = load_problem_bundle(GeometryProblem.model_validate(dsl).engine_document())
        var_names = list(bundle.var_names)
        names = [c["name"] for c in dsl["constructions"] if c["expression"].split("(")[0] not in
                 ("Line", "Circle", "Circumcircle", "Incircle", "Tangent", "Ray", "Segment", "Polygon", "Triangle")]
        evaluators, unavailable_names = {}, []
        for name in names:
            try:
                cc = construction_coordinates(dsl, [name])
                assert list(cc[f"x_{name}"][0]) == var_names == list(cc[f"y_{name}"][0])
                evaluators[name] = (cc[f"x_{name}"][1], cc[f"y_{name}"][1])
            except Exception as exc:
                unavailable_names.append({"name": name, "error": repr(exc)})
        representatives, jobs = [], []
        for job in manifest["jobs"]:
            if job["id"] != case["id"]:
                continue
            r = receipts[job["job"]]
            witnesses = json.loads(Path(r["witness_path"]).read_text())
            indices, unavailable = [], 0
            for w in witnesses:
                x = w["x"]
                if len(x) != len(var_names) or any(v is None or not math.isfinite(v) for v in x):
                    unavailable += 1
                    continue
                indices.append(cluster_index(representatives, x))
            jobs.append({"job": job["job"], "id": case["id"], "seed": job["seed"], "cores": job["cores"],
                         "budget": job["budget"], "normal": r["normal"], "status": r["status"],
                         "accepted_records": len(witnesses), "unavailable_records": unavailable,
                         "coordinate_classes": sorted(set(indices))})
        configurations = []
        for x in representatives:
            points, failures = {}, []
            for name, (ex, ey) in evaluators.items():
                px, py = answer_float(ex, x), answer_float(ey, x)
                if px is None or py is None or not math.isfinite(px) or not math.isfinite(py):
                    failures.append(name)
                else:
                    points[name] = [px, py]
            configurations.append({"variables": x, "points": points, "unavailable_points": failures})
        shape_reps = {}
        for conf in configurations:
            names_here = tuple(sorted(conf["points"]))
            if len(names_here) < 2:
                conf.update(shape_class=None, distances=[])
                continue
            distances = [math.dist(conf["points"][a], conf["points"][b])
                         for i, a in enumerate(names_here) for b in names_here[i+1:]]
            # Separate availability patterns; never merge figures with different missing point names.
            reps = shape_reps.setdefault(names_here, [])
            local_id = cluster_index(reps, distances)
            conf.update(shape_class=f"{list(shape_reps).index(names_here)}:{local_id}", distances=distances)
        for job in jobs:
            job["shape_classes"] = sorted({configurations[i]["shape_class"] for i in job["coordinate_classes"]
                                           if configurations[i]["shape_class"] is not None})
            job["coordinate_count"] = len(job["coordinate_classes"])
            job["shape_count"] = len(job["shape_classes"])
        runs_out.extend(jobs)
        lookup = {(j["seed"], j["budget"], j["cores"]): j for j in jobs}
        core_changes, shape_changes, seed_changes, seed_shape_changes = [], [], [], []
        core_observable = []
        for seed in manifest["seeds"][:2]:
            block = [lookup[(seed, 180, c)] for c in (1, 2, 4, 8)]
            core_observable.append(all(j["shape_classes"] for j in block))
            core_changes.append(len({tuple(j["coordinate_classes"]) for j in block}) > 1 if all(j["normal"] for j in block) else None)
            shape_changes.append(len({tuple(j["shape_classes"]) for j in block}) > 1 if all(j["normal"] for j in block) else None)
        for a, b in ((manifest["seeds"][0], manifest["seeds"][1]), (manifest["seeds"][2], manifest["seeds"][3])):
            ja, jb = lookup[(a, 180, 1)], lookup[(b, 180, 1)]
            seed_changes.append(ja["coordinate_classes"] != jb["coordinate_classes"] if ja["normal"] and jb["normal"] else None)
            seed_shape_changes.append(ja["shape_classes"] != jb["shape_classes"] if ja["normal"] and jb["normal"] else None)
        cases_out.append({"id": case["id"], "group": case["group"], "n_vars": len(var_names),
                          "coordinate_classes": len(representatives), "congruence_classes": sum(len(v) for v in shape_reps.values()),
                          "accepted_records": sum(j["accepted_records"] for j in jobs),
                          "coordinate_changes_primary_seeds": core_changes,
                          "congruence_changes_primary_seeds": shape_changes,
                          "core_diagrams_available_both_seeds": all(core_observable),
                          "seed_pair_coordinate_change": seed_changes, "seed_pair_congruence_change": seed_shape_changes,
                          "point_names": sorted(evaluators), "unavailable_names": unavailable_names})
        details[case["id"]] = {"variable_order": var_names, "configurations": configurations, "jobs": jobs,
                               "point_evaluation_issues": unavailable_names}
    full = raw / ("preview-evaluated-figures.json" if preview else "evaluated-figures.json")
    full.write_text(json.dumps(details, ensure_ascii=False) + "\n")
    if preview:
        print(json.dumps(cases_out, ensure_ascii=False, indent=2))
        return
    write_csv("figure-per-run.csv", runs_out)
    write_csv("figure-per-problem.csv", cases_out)
    summary = {"tolerance": TOL, "comparison": "Componentwise |a-b| <= 1e-7 max(1,|a|,|b|); greedy representatives in fixed job order.",
               "meaning": "Accepted saved configurations only; labelled pairwise distances quotient translation/rotation/reflection, retain scale. Empty sets mean no saved accepted figure, not proof of no figure.",
               "probe_basins_sha256": hashlib.sha256((ROOT / "jssa/difficulty/probe_basins.py").read_bytes()).hexdigest(),
               "source_hash": source_tree_hash(), "details_path": str(full), "details_sha256": hashlib.sha256(full.read_bytes()).hexdigest(),
               "cases": cases_out}
    (BASE / "figure-summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(cases_out, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--preview", action="store_true", help="Evaluate only completed problem blocks; save outside repository")
    main(parser.parse_args().preview)
