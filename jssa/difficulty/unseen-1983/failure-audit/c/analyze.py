"""Q29c: read-only source audit and descriptive comparisons, never run a solver.

Writes only small derived files in this directory. No sealed/ or run data access.
Run with a Python environment providing numpy/scipy; no geosolver imports.
"""
from __future__ import annotations

import ast
import csv
import hashlib
import io
import json
import os
import re
import subprocess
from collections import Counter
from functools import lru_cache
from pathlib import Path

import numpy as np
from scipy import stats

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[4]
UNSEEN = ROOT / "jssa/difficulty/unseen-1983"
UPSTREAM = Path(os.environ.get("Q29C_UPSTREAM", "/home/kabatan/work/solver-experiment"))
UPCOMMIT = "7b6691be8d8a15a7a95816b532cad06cc2819112"
UPBASE = "research/datasets/competition_geometry_20y/"
FREEZE = "60db4b679b04167175c51c479c87c22fa663fda0"
ARCHIVE = "c30f97d9c908a1c8ca576bfac220ad8e113da5fd"
LIMIT = 5_000_000
INPUTS = {}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def write(name, data):
    raw = data.encode() if isinstance(data, str) else data
    assert len(raw) < LIMIT, (name, len(raw))
    path = OUT / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(raw)


def write_json(name, data):
    write(name, json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + "\n")


def write_csv(name, rows):
    assert rows
    buf = io.StringIO()
    fields = list(dict.fromkeys(k for row in rows for k in row))
    writer = csv.DictWriter(buf, fields, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    write(name, buf.getvalue())


def read(path):
    path = Path(path)
    assert "sealed" not in path.parts and path.suffix not in {".tar", ".zst", ".gz"}
    data = path.read_bytes()
    INPUTS[str(path.relative_to(ROOT))] = {"bytes": len(data), "sha256": sha(data)}
    return data


def git(*args, repo=ROOT):
    return subprocess.check_output(["git", "-C", str(repo), *args])


@lru_cache(maxsize=None)
def blob(commit, path, upstream=False):
    assert "sealed/" not in path and not re.search(r"\.tar(?:\.|$)", path)
    data = git("show", f"{commit}:{path}", repo=UPSTREAM if upstream else ROOT)
    key = f"git:{'upstream:' if upstream else ''}{commit}:{path}"
    INPUTS[key] = {"bytes": len(data), "sha256": sha(data)}
    return data


def lines(data):
    return [json.loads(line) for line in data.decode().splitlines() if line.strip()]


@lru_cache(maxsize=None)
def tree(expr):
    return ast.parse(str(expr), mode="eval").body


def head(node):
    return node.func.id if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) else ""


POINT_OPS = {
    "Point", "PointOnSegment", "PointOnLine", "PointOnCircle", "Midpoint",
    "Intersect", "FootOfPerpendicular", "Circumcenter", "Incenter", "Centroid",
    "Orthocenter", "Reflect", "Rotate", "ContactPoint", "IncircleContactPoint", "Center",
}
PARAMETRIC = {"PointOnSegment", "PointOnLine", "PointOnCircle"}
SELECTORS = {
    "Intersect": {"n", "exclude", "near", "far"},
    "Arc": {"including", "excluding"},
    "Excircle": {"vertex"}, "Excenter": {"vertex"},
    "IncircleContactPoint": {"side"},
    "FermatPoint": {"first"}, "IsodynamicPoint": {"first"},
    "Tangent": {"use_first"}, "TangentLine": {"use_first"},
    "RegularPolygon": {"ccw"},
}
POSITIONAL_SELECTOR = {"Intersect": 2, "Excircle": 3, "Excenter": 3,
                       "IncircleContactPoint": 3, "Tangent": 2, "TangentLine": 2}


def features(dsl):
    """Syntax only. k is a conservative proxy, not historical eliminated DOF."""
    variables = set(dsl["variables"])
    definitions = {c["name"]: tree(c["expression"]) for c in dsl["constructions"]}

    @lru_cache(maxsize=None)
    def deps(name):
        if name in variables:
            return frozenset([name])
        if name not in definitions:
            return frozenset()
        return dependencies(definitions[name])

    def dependencies(node):
        return frozenset().union(*(deps(x.id) for x in ast.walk(node) if isinstance(x, ast.Name)))

    def line_type(node):
        if isinstance(node, ast.Name) and node.id in definitions:
            return line_type(definitions[node.id])
        return head(node) in {"Line", "PerpendicularLine", "ParallelLine", "PerpendicularBisector", "AngleBisector", "Polar", "Tangent"}

    roots = [tree(dsl["target"])]
    for c in dsl["conditions"]:
        roots.extend([tree(c["predicate"])] if "predicate" in c else [tree(c["left"]), tree(c["right"])])
    active = set()

    def activate(node):
        for x in ast.walk(node):
            if isinstance(x, ast.Name) and x.id in definitions and x.id not in active:
                active.add(x.id)
                activate(definitions[x.id])

    for node in roots:
        activate(node)
    k_names, k4_names, point_names, formula_names, param_names = [], [], [], [], []
    for name, node in definitions.items():
        h = head(node)
        if h not in POINT_OPS:
            continue
        point_names.append(name)
        if h == "Point":
            # A diagnostic for coordinate-form constructions omitted from k.
            if any(not isinstance(a, (ast.Name, ast.Constant)) for a in node.args):
                formula_names.append(name)
            continue
        if h in PARAMETRIC:
            parameter = node.args[-1]
            if dependencies(parameter):
                param_names.append(name)
                continue
        k_names.append(name)
        if h in {"Midpoint", "FootOfPerpendicular", "Circumcenter"} or (
            h == "Intersect" and len(node.args) == 2 and all(line_type(a) for a in node.args)
        ):
            k4_names.append(name)
    guard_rows = sum(c.get("operator") != "=" for c in dsl["conditions"])
    inequality_rows = sum(c.get("operator") in {">", "<", ">=", "<=", "!="} for c in dsl["conditions"])
    inequality_atoms = inequality_rows
    predicate_rows = sum("predicate" in c for c in dsl["conditions"])
    for c in dsl["conditions"]:
        if "predicate" not in c:
            continue
        for n in ast.walk(tree(c["predicate"])):
            if isinstance(n, ast.Compare):
                inequality_atoms += sum(not isinstance(op, ast.Eq) for op in n.ops)
            if head(n) == "Bound":
                inequality_atoms += 2
    alltrees = list(definitions.values()) + roots
    calls = Counter(head(n) for t in alltrees for n in ast.walk(t) if head(n))
    selectors, selector_details, ors = 0, [], 0
    for t in alltrees:
        for n in ast.walk(t):
            h = head(n)
            if h == "Or" or isinstance(n, ast.BoolOp) and isinstance(n.op, ast.Or):
                ors += 1
            explicit = h in SELECTORS and (
                any(k.arg in SELECTORS[h] for k in n.keywords)
                or h in POSITIONAL_SELECTOR and len(n.args) > POSITIONAL_SELECTOR[h]
            )
            if explicit:
                selectors += 1
                selector_details.append(ast.unparse(n))
    used_variables = set().union(*(dependencies(t) for t in roots))
    return {
        "n_vars": len(variables), "n_used_vars": len(used_variables),
        "k_constructed_points": len(k_names), "k_active": len(set(k_names) & active),
        "k_four_ops": len(k4_names), "n_points": len(point_names),
        "n_point_formula": len(formula_names), "n_parametric_points": len(param_names),
        "n_conditions": len(dsl["conditions"]), "n_inequality_rows": inequality_rows,
        "n_inequality_atoms": inequality_atoms, "n_guard_rows": guard_rows,
        "n_predicate_rows": predicate_rows, "n_selectors": selectors, "n_or": ors,
        "n_integer_calls": calls["IsInteger"], "n_onsegment_calls": calls["OnSegment"],
        "k_names": ";".join(k_names), "k4_names": ";".join(k4_names),
        "point_formula_names": ";".join(formula_names),
        "selector_expressions": " ; ".join(selector_details),
    }


def describe(values):
    x = np.array(values, dtype=float)
    if not len(x):
        return {"n": 0}
    return {"n": len(x), "mean": float(x.mean()), "median": float(np.median(x)),
            "q25": float(np.quantile(x, .25)), "q75": float(np.quantile(x, .75)),
            "min": float(x.min()), "max": float(x.max())}


def difference(a, b):
    """Mean A-B; resample problems (never treat 200 starts as independent cases)."""
    a, b = np.array(a, float), np.array(b, float)
    if not len(a) or not len(b):
        return {}
    rng = np.random.default_rng(2903)
    draws = np.concatenate([
        a[rng.integers(0, len(a), (500, len(a)))].mean(1)
        - b[rng.integers(0, len(b), (500, len(b)))].mean(1)
        for _ in range(20)
    ])
    u = stats.mannwhitneyu(a, b, alternative="two-sided", method="asymptotic")
    return {"mean_difference_A_minus_B": float(a.mean() - b.mean()),
            "bootstrap95_low": float(np.quantile(draws, .025)),
            "bootstrap95_high": float(np.quantile(draws, .975)),
            "rank_biserial_A_minus_B": float(2 * u.statistic / (len(a) * len(b)) - 1),
            "mw_p_exploratory": float(u.pvalue) if np.isfinite(u.pvalue) else None}


def structural_legacy(dsl):
    return {k: dsl.get(k) for k in ["variables", "construction", "constraints", "guards", "answer"]}


def main():
    cases_bytes = read(ROOT / "benchmarks/cases.jsonl")
    cases = lines(cases_bytes)
    assert cases_bytes == blob(FREEZE, "benchmarks/cases.jsonl")
    ids = {r["id"] for r in cases}
    assert len(ids) == len(cases) == 323
    basin = {r["id"]: r for r in csv.DictReader(io.StringIO(read(ROOT / "jssa/difficulty/minima/basins-323.csv").decode()))}
    assert ids == set(basin)
    targets = read(UNSEEN / "prereg/target-26.txt").decode().split()
    unseen_input_freeze = json.loads(read(UNSEEN / "revisions/v3-input-freeze.json"))
    scored = [r for r in lines(read(UNSEEN / "prereg/q19-scored/assessment.jsonl")) if r["in_target"]]
    assert set(targets) == {r["case_id"] for r in scored} and len(targets) == 26 and len(scored) == 130
    assert sum(r["matched"] for r in scored) == 85
    assert all(r["extra"] == 0 for r in scored)
    outcomes = {i: [r for r in scored if r["case_id"] == i] for i in targets}
    assert all(len(v) == 5 and {r["seed"] for r in v} == set(range(201, 206)) for v in outcomes.values())

    ledger97_path = "benchmarks/repairs/corpus97/repair-ledger.jsonl"
    ledger6_path = "benchmarks/repairs/corpus323-inputs-v1/ledger.jsonl"
    l97 = lines(blob(ARCHIVE, ledger97_path))
    l6 = lines(blob(ARCHIVE, ledger6_path))
    write("evidence/corpus97-ledger.jsonl", blob(ARCHIVE, ledger97_path))
    write("evidence/corpus323-ledger.jsonl", blob(ARCHIVE, ledger6_path))
    for p, dest in [
        ("benchmarks/repairs/corpus97/README.md", "corpus97-README.md"),
        ("benchmarks/repairs/corpus323-inputs-v1/README.md", "corpus323-README.md"),
        ("benchmarks/repairs/corpus97/known-boundary-regression.json", "JMO-2009-PRE-02-before.json"),
    ]:
        write("evidence/" + dest, blob(ARCHIVE, p))
    before = {}
    for p in ["benchmarks/repairs/corpus97/before.jsonl", "benchmarks/repairs/corpus323-inputs-v1/before.jsonl"]:
        before.update({r["id"]: r for r in lines(blob(ARCHIVE, p))})
    ledgers = {r["id"]: r for r in l97 + l6 if r["id"] in ids}

    # Current benchmark git history: compare common DSLs, not added files or metadata.
    commits = git("log", "--reverse", "--format=%H", "--", "benchmarks/cases.jsonl").decode().split()
    history, prev = [], {}
    for co in commits:
        rows = {r["id"]: r for r in lines(blob(co, "benchmarks/cases.jsonl"))}
        for i in sorted(rows.keys() & prev.keys() & ids):
            if rows[i].get("dsl") != prev[i].get("dsl"):
                history.append({"id": i, "commit": co, "event": "main_git_dsl_change",
                                "before_vars": len(prev[i]["dsl"]["variables"]),
                                "after_vars": len(rows[i]["dsl"]["variables"])})
        prev = rows
    main_touched = {r["id"] for r in history}

    # Archive an independent, hash-identified source for the inherited compression.
    upstream_docs = ["DOF_COMPRESSION_AUDIT.md", "PERFORMANCE_DIAGNOSIS.md",
                     "DSL_DEFICIENCY_AUDIT_2026-08-05.md", "DSL_DEFICIENCY_REPAIR_REPORT.md",
                     "DSL_REPAIR_BENCHMARK_REPORT_180S_1CORE.md"]
    for p in upstream_docs:
        write("evidence/" + p, blob(UPCOMMIT, UPBASE + p, True))
    dof_latest = {}
    for r in lines(blob(UPCOMMIT, UPBASE + "dof_measurement_180s_1core.jsonl", True)):
        dof_latest[r["case_id"]] = r
    dof_ids = set(dof_latest) & ids
    up_commits = git("log", "--reverse", "--format=%H", UPCOMMIT, "--", UPBASE + "dsl", repo=UPSTREAM).decode().split()
    up_prev, up_hist = {}, []
    for co in up_commits:
        paths = git("diff-tree", "--no-commit-id", "--name-only", "-r", "--root", co, "--", UPBASE + "dsl", repo=UPSTREAM).decode().splitlines()
        for p in paths:
            if not p.endswith(".json") or Path(p).stem not in ids:
                continue
            i = Path(p).stem
            d = structural_legacy(json.loads(blob(co, p, True)))
            if i in up_prev and d != up_prev[i]:
                up_hist.append({"id": i, "commit": co, "event": "upstream_core_dsl_change",
                                "changed_fields": ";".join(k for k in d if d[k] != up_prev[i][k])})
            up_prev[i] = d
    up_touched = {r["id"] for r in up_hist}
    history.extend(up_hist)
    write_csv("git-history-events.csv", history)

    detailed, repair_events = [], []
    legacy_verified = 0
    for case in cases:
        i = case["id"]
        dsl_path = "benchmarks/" + case["dsl_path"]
        data = read(ROOT / dsl_path)
        assert data == blob(FREEZE, dsl_path)
        dsl = json.loads(data)
        assert dsl == case["dsl"]
        f = features(dsl)
        assert f["n_vars"] == int(basin[i]["n_vars"])
        p = float(basin[i]["p"]) if basin[i]["p"] else None
        starts = int(basin[i]["n_starts"]) if basin[i]["n_starts"] else 0
        raw = json.loads(read(ROOT / "jssa/difficulty/minima/raw-323" / (i + ".json")))
        records = raw.get("records", [])
        hits = sum(r["cls"] == "hit" for r in records)
        assert len(records) == starts
        if p is not None:
            assert 0 < starts <= 200 and abs(p - hits / starts) < 1e-12
        else:
            assert f["n_vars"] == 0 and starts == 0
        if "migration" in case:
            legacy = blob(UPCOMMIT, UPBASE + case["migration"]["legacy_path"], True)
            assert sha(legacy) == case["migration"]["legacy_sha256"], i
            legacy_verified += 1
        ledger = ledgers.get(i)
        change = "no_current_ledger"
        if ledger:
            old = before[i].get("dsl")
            change = "new_dsl" if old is None else "dsl_changed" if old != dsl else "reference_only"
            hash_changed = ledger.get("dsl_before_sha256") != ledger.get("dsl_after_sha256")
            assert hash_changed == (change != "reference_only"), i
            # Ledgers use canonical JSON with ASCII escaping, no whitespace.
            assert sha(json.dumps(dsl, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()) == ledger["dsl_after_sha256"], i
            event = {"id": i, "revision": ledger["revision"], "class": change,
                     "before_vars": len(old["variables"]) if old else None,
                     "after_vars": f["n_vars"], "reference_from_solver": ledger["reference_from_solver"],
                     "reason": ledger.get("translation_note", ledger.get("reason")),
                     "current_p_local": p}
            if old:
                bf = features(old)
                for k in ["k_constructed_points", "n_inequality_atoms", "n_guard_rows", "n_selectors"]:
                    event["before_" + k] = bf[k]
                    event["after_" + k] = f[k]
            repair_events.append(event)
        detailed.append({"id": i, "cohort": "development323", "family": i.upper().split("-")[0],
                         "dsl_sha256": sha(data), "p_local": p, "n_starts": starts,
                         "local_hits": hits, "local_truncated": 0 < starts < 200,
                         "repair_tag": bool(case.get("repair")), "ledger_class": change,
                         "ledger_dsl_changed_or_new": change in {"new_dsl", "dsl_changed"},
                         "main_git_dsl_changed": i in main_touched,
                         "upstream_git_dsl_changed": i in up_touched,
                         "compression_followup39": i in dof_ids,
                         "any_documented_dsl_change": change in {"new_dsl", "dsl_changed"} or i in main_touched | up_touched,
                         "documented_change_or_compression_followup": change in {"new_dsl", "dsl_changed"} or i in main_touched | up_touched | dof_ids,
                         "history_partition": case.get("history_partition", "unmarked"), **f})
    assert legacy_verified == 295
    for i in targets:
        data = read(UNSEEN / "dsl" / (i + ".json"))
        assert sha(data) == unseen_input_freeze["input_hashes"][i], i
        dsl = json.loads(data)
        runs = outcomes[i]
        hits = sum(r["matched"] for r in runs)
        detailed.append({"id": i, "cohort": "unseen26", "family": i.split("-")[0],
                         "dsl_sha256": sha(data), "q19_hits": hits, "q19_n": 5,
                         "q19_run_success": hits / 5, "q19_group": "success16" if hits == 5 else "failure10",
                         **features(dsl)})
    write_csv("per-case.csv", detailed)
    write_csv("repair-events.csv", repair_events)
    dev = [r for r in detailed if r["cohort"] == "development323"]
    unseen = [r for r in detailed if r["cohort"] == "unseen26"]
    active = [r for r in dev if r["p_local"] is not None]
    failed = [r for r in unseen if r["q19_group"] == "failure10"]
    success = [r for r in unseen if r["q19_group"] == "success16"]
    assert (len(active), len(failed), len(success)) == (292, 10, 16)

    groups = {"development323": dev, "development_active292": active, "unseen26": unseen,
              "failure10": failed, "success16": success,
              "unseen_without_fixed_668": [r for r in unseen if r["id"] != "AIME-1991-02"],
              "success_without_fixed_668": [r for r in success if r["id"] != "AIME-1991-02"],
              "development_AIME": [r for r in dev if r["family"] == "AIME"],
              "unseen_AIME": [r for r in unseen if r["family"] == "AIME"]}
    metrics = ["n_vars", "k_constructed_points", "k_active", "k_four_ops", "n_inequality_atoms",
               "n_guard_rows", "n_selectors", "n_or", "n_integer_calls", "n_points", "n_point_formula"]
    summaries = [{"group": name, "metric": k, **describe([r[k] for r in rows])}
                 for name, rows in groups.items() for k in metrics]
    write_csv("feature-summary.csv", summaries)
    comparisons = []
    for aname, bname in [("unseen26", "development323"), ("failure10", "success16"), ("unseen_AIME", "development_AIME")]:
        for k in metrics:
            comparisons.append({"A": aname, "B": bname, "metric": k,
                                **difference([r[k] for r in groups[aname]], [r[k] for r in groups[bname]])})
    write_csv("feature-comparisons.csv", comparisons)

    repair_stats, repair_diffs, strata = [], [], []
    flags = ["repair_tag", "ledger_dsl_changed_or_new", "any_documented_dsl_change", "compression_followup39",
             "documented_change_or_compression_followup"]
    for flag in flags:
        for val in [True, False]:
            rows = [r for r in dev if r[flag] == val]
            ps = [r["p_local"] for r in rows if r["p_local"] is not None]
            repair_stats.append({"definition": flag, "value": val, "cases": len(rows),
                                 "zero_vars": sum(r["n_vars"] == 0 for r in rows),
                                 "mean_vars": float(np.mean([r["n_vars"] for r in rows])), **describe(ps)})
        repair_diffs.append({"definition": flag, **difference(
            [r["p_local"] for r in active if r[flag]], [r["p_local"] for r in active if not r[flag]])})
        for lo, hi in [(1, 2), (3, 4), (5, 100)]:
            for val in [True, False]:
                ps = [r["p_local"] for r in active if r[flag] == val and lo <= r["n_vars"] <= hi]
                strata.append({"definition": flag, "value": val, "n_vars_bin": f"{lo}-{hi}", **describe(ps)})
    for kind in sorted({r["ledger_class"] for r in dev}):
        rows = [r for r in dev if r["ledger_class"] == kind]
        repair_stats.append({"definition": "ledger_class", "value": kind, "cases": len(rows),
                             "zero_vars": sum(r["n_vars"] == 0 for r in rows),
                             "mean_vars": float(np.mean([r["n_vars"] for r in rows])),
                             **describe([r["p_local"] for r in rows if r["p_local"] is not None])})
    write_csv("repair-p-summary.csv", repair_stats)
    write_csv("repair-p-comparisons.csv", repair_diffs)
    write_csv("repair-p-by-dimension.csv", strata)
    completed_sensitivity = []
    for flag in flags:
        for val in [True, False]:
            ps = [r["p_local"] for r in active if r[flag] == val and r["n_starts"] == 200]
            completed_sensitivity.append({"definition": flag, "value": val, **describe(ps)})
    write_csv("repair-p-completed200.csv", completed_sensitivity)

    # Sensitivity: linear probability outcome p_local; categorical dimension and family.
    # HC3 is descriptive, not an estimate of a causal repair benefit.
    adjusted = []
    for flag in flags[:3]:
        ds = sorted({r["n_vars"] for r in active})
        fs = sorted({r["family"] for r in active})
        X = np.array([[1., float(r[flag])] + [float(r["n_vars"] == d) for d in ds[1:]]
                      + [float(r["family"] == f) for f in fs[1:]] for r in active])
        y = np.array([r["p_local"] for r in active])
        inv = np.linalg.pinv(X.T @ X)
        beta = inv @ X.T @ y
        resid = y - X @ beta
        h = np.sum((X @ inv) * X, axis=1)
        cov = inv @ (X.T @ ((resid / (1 - h))[:, None] ** 2 * X)) @ inv
        se = float(np.sqrt(cov[1, 1]))
        adjusted.append({"definition": flag, "n": len(y), "coefficient": float(beta[1]),
                         "hc3_se": se, "normal95_low": float(beta[1] - 1.96 * se),
                         "normal95_high": float(beta[1] + 1.96 * se),
                         "adjustment": "categorical n_vars and contest family"})
    write_json("repair-adjusted-sensitivity.json", adjusted)

    # The 39 follow-up cases are selected, use a different solver, and are not paired p.
    pre = {r["case_id"]: r for r in csv.DictReader(io.StringIO(read(ROOT / "jssa/difficulty/pre-0803-dsl/baseline-pre-compression-results.csv").decode()))}
    current = {r["id"]: r for r in dev}
    dof_table = []
    for i, r in sorted(dof_latest.items()):
        dof_table.append({"id": i, "in_current323": i in ids,
                          "old_baseline_status": pre.get(i, {}).get("status"),
                          "old_followup_status": r["status"],
                          "current_n_vars": current[i]["n_vars"] if i in ids else None,
                          "current_p_local": current[i]["p_local"] if i in ids else None})
    write_csv("compression-followup39.csv", dof_table)
    p_correlations = []
    for k in metrics:
        rho, sig = stats.spearmanr([r[k] for r in active], [r["p_local"] for r in active])
        p_correlations.append({"metric": k, "n": len(active), "rho_p_local": float(rho), "p_exploratory": float(sig)})
    write_csv("development-p-correlations.csv", p_correlations)
    integer_summary = []
    for val in [True, False]:
        rows = [r for r in unseen if bool(r["n_integer_calls"]) == val]
        integer_summary.append({"integer_constraints": val, "cases": len(rows),
                                "some_failure_cases": sum(r["q19_hits"] < 5 for r in rows),
                                "correct_runs": sum(r["q19_hits"] for r in rows), "runs": 5 * len(rows),
                                "ids": [r["id"] for r in rows]})
    write_json("integer-subgroup.json", integer_summary)

    def fmt(x):
        return f"{x:g}"

    summary_map = {(r["group"], r["metric"]): r for r in summaries}
    table = ["# DSLの書き方とQ19結果", "", "件数は構文の数。定義と限界は [methods.md](methods.md)。中央値［第1–第3四分位］。", "",
             "|指標|開発323|未使用26|失敗10|全5回成功16|", "|---|---:|---:|---:|---:|"]
    for k, label in [("n_vars", "自由変数 d"), ("k_constructed_points", "完全な作図点 k（代理値）"),
                     ("k_four_ops", "作図点・4演算のみ"), ("n_inequality_atoms", "明示的不等式の原子数 I"),
                     ("n_guard_rows", "guard条件行 G"), ("n_selectors", "明示的枝selector S"),
                     ("n_or", "Or分岐"), ("n_integer_calls", "IsInteger呼出し")]:
        vals = [summary_map[g, k] for g in ["development323", "unseen26", "failure10", "success16"]]
        table.append("|" + label + "|" + "|".join(f"{fmt(s['median'])}［{fmt(s['q25'])}–{fmt(s['q75'])}］" for s in vals) + "|")
    table += ["", "AIME-1991-02だけで固定作図668点、自由変数0。kの単純平均は開発1.65・未使用26.81となる。",
              "この1問を外した感度分析では未使用25問のk平均1.16（成功15問1.53、失敗10問0.60）。主解析26問は変更しない。", "",
              "|ID|Q19正解/5|d|k|I|G|S|整数条件|", "|---|---:|---:|---:|---:|---:|---:|---:|"]
    for r in sorted(unseen, key=lambda r: r["id"]):
        table.append("|" + "|".join(str(r[k]) for k in ["id", "q19_hits", "n_vars", "k_constructed_points", "n_inequality_atoms", "n_guard_rows", "n_selectors", "n_integer_calls"]) + "|")
    table += ["", "整数条件8問のQ19成績は1/40、残る18問は84/90。これは結果を見て発見した記述的な関連であり、因果効果ではない。",
              "この表はDSLの充足可能性・局所解の存在を判定していない。失敗10問は0/5の8問と1/5・4/5の各1問。", ""]
    write("comparison.md", "\n".join(table))

    read(UNSEEN / "prereg/result.md")
    read(ROOT / "jssa/strategy/codex-tasks-1023.md")
    read(UNSEEN / "authoring-rules.md")
    read(UNSEEN / "audit/summary.json")
    read(ROOT / "jssa/difficulty/probe_basins.py")
    read(OUT / "analyze.py")
    manifest = {
        "task": "Q29c", "head": git("rev-parse", "HEAD").decode().strip(),
        "solver_commit": FREEZE, "archive_commit": ARCHIVE,
        "upstream_repo": str(UPSTREAM), "upstream_commit": UPCOMMIT,
        "inputs": INPUTS,
        "checks": {"development323_matches_frozen_commit_bytes": True,
                   "unseen26_matches_pre_answer_input_freeze_sha256": True,
                   "migration_legacy_sha256_verified": legacy_verified,
                   "q19_target_cases": len(unseen), "q19_runs": len(scored), "q19_correct": 85,
                   "q19_all_five_correct_cases": len(success), "q19_some_failure_cases": len(failed),
                   "local_probe_cases_with_p": len(active), "local_starts_requested": 200,
                   "local_starts_min": min(r["n_starts"] for r in active),
                   "local_starts_total": sum(r["n_starts"] for r in active),
                   "local_truncated_cases": sum(r["local_truncated"] for r in active),
                   "local_csv_p_verified_against_development_records": True,
                   "solver_executions": 0, "sealed_reads": 0},
        "repair_counts": dict(Counter(r["ledger_class"] for r in dev)),
        "main_git_changed_ids": sorted(main_touched),
        "upstream_core_changed_ids": sorted(up_touched),
        "compression_followup_in_current_ids": sorted(dof_ids),
        "current_git_history_dsl_changed_union": len(main_touched | {r["id"] for r in dev if r["ledger_dsl_changed_or_new"]}),
        "explicit_any_history_dsl_changed_union": sum(r["any_documented_dsl_change"] for r in dev),
        "including_compression_followup_union": sum(r["documented_change_or_compression_followup"] for r in dev),
        "bootstrap": {"seed": 2903, "replicates": 10000, "unit": "problem", "interval": "percentile"},
        "versions": {"numpy": np.__version__, "scipy": __import__("scipy").__version__},
    }
    write_json("input-manifest.json", manifest)
    print(json.dumps({"checks": manifest["checks"], "repair_counts": manifest["repair_counts"],
                      "main_git_changes": len(main_touched), "upstream_core_changes": len(up_touched),
                      "any_documented_change": sum(r["any_documented_dsl_change"] for r in dev)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
