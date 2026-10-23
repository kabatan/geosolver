"""Small read-only reanalysis of inputs/results; write only beside this script.

No local optimization. Run with the specified interpreter and -B.
Published solver results are a manual transcription of Sinha et al. Fig. 1.
"""
from __future__ import annotations

import collections
import csv
import hashlib
import itertools
import json
from pathlib import Path
import platform
import re
import time

BASE = Path(__file__).resolve().parent
ROOT = BASE.parents[3]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(name, value):
    (BASE / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def write_csv(name, rows):
    with (BASE / name).open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


def main():
    start = time.monotonic()
    import mpmath as mp
    import sympy as sp

    lines = (BASE / "upstream/imo_ag_30.txt").read_text().splitlines()
    assert len(lines) == 60
    inputs = dict(zip(lines[::2], lines[1::2]))
    groups = collections.defaultdict(list)
    for case, text in inputs.items():
        premise, goal = text.split(" ? ")
        groups[premise].append({"id": case, "goal": goal})
    pairs = [{"premise": p, "premise_sha256": hashlib.sha256(p.encode()).hexdigest(),
              "members": rows} for p, rows in groups.items() if len(rows) > 1]
    write_json("same-premise-groups.json", pairs)

    # Figure 1(B), top to bottom. A 0 means no proof credited by that figure,
    # not a theorem is false; Wu's zeros include four unformalized problems.
    pubgroups = [
        ((0, 0, 0), "2008-P6 2011-P6 2019-P2"),
        ((0, 1, 0), "2008-P1B 2021-P3"),
        ((0, 1, 1), "2008-P1A 2009-P2 2012-P5 2014-P4 2018-P1"),
        ((1, 1, 1), "2000-P1 2002-P2A 2002-P2B 2004-P5 2010-P4 2015-P4 2016-P1 2017-P4"),
        ((1, 0, 1), "2003-P4 2005-P5 2007-P4 2012-P1 2013-P4 2022-P4"),
        ((0, 0, 1), "2000-P6 2004-P1 2010-P2 2015-P3 2019-P6 2020-P1"),
    ]
    published = []
    for (dd, wu, ag), ids in pubgroups:
        for item in ids.split():
            match = re.fullmatch(r"(\d{4})-P(\d)([AB]?)", item)
            year, number, suffix = match.groups()
            ag_id = f"translated_imo_{year}_p{number}{suffix.lower()}"
            assert ag_id in inputs
            published.append({"id": ag_id, "original_id": f"IMO_{year}_P{number}",
                              "ddar_reported_solved": dd, "wu_reported_solved": wu,
                              "ag1_reported_solved": ag, "figure_row": len(published)+1})
    assert len(published) == len({r["id"] for r in published}) == 30
    assert set(r["id"] for r in published) == set(inputs)
    counts = {k: sum(r[k] for r in published) for k in ["ddar_reported_solved", "wu_reported_solved", "ag1_reported_solved"]}
    assert list(counts.values()) == [14, 15, 25]
    counts["wu_union_ddar"] = sum(r["wu_reported_solved"] or r["ddar_reported_solved"] for r in published)
    counts["wu_union_ag1"] = sum(r["wu_reported_solved"] or r["ag1_reported_solved"] for r in published)
    counts["wu_only_vs_ddar"] = sum(r["wu_reported_solved"] and not r["ddar_reported_solved"] for r in published)
    counts["ddar_only_vs_wu"] = sum(r["ddar_reported_solved"] and not r["wu_reported_solved"] for r in published)
    assert counts["wu_union_ddar"] == 21 and counts["wu_union_ag1"] == 27
    write_csv("published-imo-ag30.csv", published)

    current_hashes = {p.name: sha(p) for p in sorted((BASE / "upstream").iterdir()) if p.is_file()}
    runs, queries = [], []
    for path in sorted(BASE.glob("ddar-*.json")):
        d = json.loads(path.read_text())
        assert d["source_hashes"] == current_hashes, path
        assert d["source_premise_sha256"] == hashlib.sha256(inputs["translated_imo_2008_p1a"].split(" ? ")[0].encode()).hexdigest()
        coords = d["coordinates"]
        def dot_at(q, p, r):
            return sum((coords[p][i]-coords[q][i])*(coords[r][i]-coords[q][i]) for i in range(2))
        diagram_acute = all(dot_at(q, p, r) > 0 for q, p, r in [("a","b","c"),("b","a","c"),("c","a","b")])
        diagram_min_pair_d2 = min(sum((coords[p][i]-coords[q][i])**2 for i in range(2))
                                  for p,q in itertools.combinations(["a1","a2","b1","b2","c1","c2"], 2))
        runs.append({"file": path.name, "sha256": sha(path), "seed": d["seed"],
                     "renamed": d["renamed"], "status": d["status"],
                     "saturation_confirmed": d.get("saturation_confirmed", False),
                     "derived": sum(q["derived"] for q in d.get("queries", [])),
                     "diagram_acute": diagram_acute, "diagram_min_pair_distance_squared": diagram_min_pair_d2,
                     "total_seconds": d["total_seconds"], "max_rss_kib": d["max_rss_kib"]})
        for q in d.get("queries", []):
            queries.append({"run": path.name, "points": " ".join(q["points"]),
                            "occupancy": "+".join(str(n) for n in q["occupancy"] if n),
                            "predicted_derived": q["occupancy"] == [2, 2, 0],
                            "derived": q["derived"], "initial": q["initial"]})
    write_csv("ddar-runs.csv", runs)
    write_csv("ddar-queries.csv", queries)

    # Exact, hand-derived common-center argument. No theorem discovery here.
    x, y = sp.symbols("x y", real=True)
    A, B, C = sp.Matrix([0, 0]), sp.Matrix([1, 0]), sp.Matrix([x, y])
    O = sp.Matrix([sp.Rational(1, 2), (x*x-x+y*y)/(2*y)])
    H = sp.Matrix([x, x*(1-x)/y])
    mids = [(B+C)/2, (C+A)/2, (A+B)/2]
    square = lambda v: v.dot(v)
    radii = [sp.factor(square(O-M)+square(H-M)) for M in mids]
    diffs = [sp.factor(r-radii[0]) for r in radii]
    perpendiculars = [sp.factor((O-M).dot(V-U)) for M, (U,V) in zip(mids, [(B,C),(C,A),(A,B)])]
    circle_formula = sp.factor((square(O-A)+square(O-H))/2)
    assert diffs == [0, 0, 0] and perpendiculars == [0, 0, 0]
    assert sp.factor(radii[0]-circle_formula) == 0
    exact = {"method": "hand-derived algebra checked by exact SymPy expansion, not GeoSolver",
             "domain": "y != 0; all six side-circle intersections must be pairwise distinct for 15 four-point queries",
             "circumcenter": str(O), "orthocenter": str(H), "radius_squared": str(radii[0]),
             "radius_differences": [str(z) for z in diffs],
             "side_perpendicular_dot_products": [str(z) for z in perpendiculars],
             "radius_formula": "(circumradius(ABC)^2 + Distance(O,H)^2)/2"}
    write_json("exact-common-circle.json", exact)

    mp.mp.dps = 60
    rational_triangles = [(1,3,4,5),(2,5,3,4),(1,2,4,3),(3,5,5,6),(2,3,6,5),(4,7,9,10)]
    sub = lambda a,b: [a[i]-b[i] for i in range(2)]
    dot = lambda a,b: sum(a[i]*b[i] for i in range(2))
    norm2 = lambda a: dot(a,a)
    numerical = []
    for index, (xn,xd,yn,yd) in enumerate(rational_triangles):
        u, v = mp.mpf(xn)/xd, mp.mpf(yn)/yd
        a,b,c = [mp.mpf(0),mp.mpf(0)], [mp.mpf(1),mp.mpf(0)], [u,v]
        h = [u,u*(1-u)/v]
        coords = {}
        for prefix,(p,q) in zip("abc", [(b,c),(c,a),(a,b)]):
            m = [(p[i]+q[i])/2 for i in range(2)]
            side = sub(q,p)
            ratio = mp.sqrt(norm2(sub(m,h))/norm2(side))
            for num,sign in [(1,1),(2,-1)]:
                coords[prefix+str(num)] = [m[i]+sign*ratio*side[i] for i in range(2)]
        allpairs = [norm2(sub(p,q)) for p,q in itertools.combinations(coords.values(),2)]
        scale2 = max(allpairs)
        acute = all(dot(sub(p,q),sub(r,q))>0 for p,q,r in [(a,b,c),(b,c,a),(c,a,b)])
        for names in itertools.combinations(coords,4):
            mat = mp.matrix([[*coords[n], norm2(coords[n]), 1] for n in names])
            residual = abs(mp.det(mat))/(scale2*scale2)
            numerical.append({"triangle": index+1, "cx": f"{xn}/{xd}", "cy": f"{yn}/{yd}",
                              "acute": acute, "six_distinct": min(allpairs)>mp.mpf("1e-40"),
                              "points": " ".join(names), "normalized_cyclic_determinant": mp.nstr(residual,20),
                              "below_1e-40": residual<=mp.mpf("1e-40")})
    write_csv("analytic-coordinate-checks.csv", numerical)

    gmb_path = ROOT / "jssa/results/gmb-success-definition/per-trial.csv"
    gmb = list(csv.DictReader(gmb_path.open()))
    gmb_p1 = [r for r in gmb if r["case_id"] == "IMO_2008_P1"]
    assert len(gmb_p1) == 6
    write_csv("gmb-2008p1-existing.csv", gmb_p1)
    human_path = ROOT / "jssa/difficulty/ghost-1023/human_feat.csv"
    human = list(csv.DictReader(human_path.open()))
    available_human = [r for r in human if r["human"]]
    gmb_ids = {p.stem for p in (ROOT/"benchmarks/gmb_comparison/cases").glob("*.json")}
    published_original_ids = {r["original_id"] for r in published}
    coverage = {"ag30_tasks": len(inputs), "ag30_original_problem_ids":len(published_original_ids),
                "same_premise_groups":len(pairs), "gmb_input_cases":len(gmb_ids),
                "ag30_originals_in_gmb":len(gmb_ids & published_original_ids),
                "ag30_tasks_mapped_to_gmb":sum(r["original_id"] in gmb_ids for r in published),
                "ag30_originals_not_in_gmb":sorted(published_original_ids-gmb_ids),
                "human_total_rows":len(human), "human_labeled_rows":len(available_human),
                "human_labeled_by_contest":dict(collections.Counter(r["contest"] for r in available_human)),
                "human_labeled_imo_rows":sum(r["contest"]=="IMO" for r in available_human),
                "gmb_csv_rows":len(gmb), "gmb_csv_is_all_trials":False}
    write_json("coverage.json", coverage)

    summary = {"coverage":coverage, "published_counts":counts,
               "ddar_runs":len(runs), "ddar_query_evaluations":len(queries),
               "ddar_saturated_runs":sum(r["saturation_confirmed"] for r in runs),
               "ddar_derived":sum(q["derived"] for q in queries),
               "ddar_acute_diagram_runs":sum(r["diagram_acute"] for r in runs),
               "P1_exact_prediction":all(q["predicted_derived"]==q["derived"] for q in queries),
               "P1_positive_predictions":sum(q["predicted_derived"] for q in queries),
               "analytic_checks":len(numerical), "analytic_checks_passed":sum(r["below_1e-40"] for r in numerical),
               "analytic_max_residual":mp.nstr(max(mp.mpf(r["normalized_cyclic_determinant"]) for r in numerical),20),
               "all_fixed_triangles_acute_and_distinct":all(r["acute"] and r["six_distinct"] for r in numerical),
               "gmb_p1_existing_passes":sum(r["indep_1e-6"]=="True" for r in gmb_p1),
               "gmb_p1_existing_goals_all_passed":sum(r["goals_passed"]==r["goals_total"]=="15" for r in gmb_p1),
               "environment":{"python":platform.python_version(),"sympy":sp.__version__,"mpmath":mp.__version__},
               "upstream_hashes":current_hashes, "input_hashes": {str(p.relative_to(ROOT)):sha(p) for p in [gmb_path,human_path,BASE/"analysis-plan.md",BASE/"resume-plan.md",BASE/"run_ddar.py"]},
               "analysis_seconds":time.monotonic()-start}
    write_json("summary.json", summary)
    print(json.dumps({k:v for k,v in summary.items() if k not in {"upstream_hashes","input_hashes"}}, ensure_ascii=False,indent=2))


if __name__ == "__main__":
    main()
