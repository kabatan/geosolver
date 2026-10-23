"""Read-only exploratory reanalysis; all artifacts stay beside this script.

Run with the specified Python and BLAS thread counts of 1. No solver calls.
"""
from __future__ import annotations

import hashlib
import csv as csvlib
import json
import math
import re
from pathlib import Path

import numpy as np

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[3]
INPUTS: dict[str, str] = {}


def read(path: str) -> str:
    data = (ROOT / path).read_bytes()
    INPUTS[path] = hashlib.sha256(data).hexdigest()
    return data.decode()


def csv(path: str) -> list[dict]:
    from io import StringIO
    def scalar(s):
        if s == "":
            return np.nan
        if s in ("True", "False"):
            return s == "True"
        try:
            return float(s)
        except ValueError:
            return s
    return [{k: scalar(v) for k, v in r.items()} for r in csvlib.DictReader(StringIO(read(path)))]


def write_csv(name, rows):
    keys = list(dict.fromkeys(k for r in rows for k in r))
    with (OUT / name).open("w") as h:
        w = csvlib.DictWriter(h, fieldnames=keys)
        w.writeheader()
        w.writerows(rows)


def json_safe(value):
    if isinstance(value, dict):
        return {k: json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [json_safe(v) for v in value]
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def structure(dsl: dict) -> dict:
    variables = set(dsl.get("variables", []))
    cs = {c["name"]: c["expression"] for c in dsl.get("constructions", [])}
    known = set(cs) | variables
    def symbols(s):
        # A.x means the attribute x of A, not a free scalar named x.
        return set(re.findall(r"(?<![\w.])[A-Za-z_]\w*", str(s))) & known
    deps = {k: symbols(v) - {k} for k, v in cs.items()}
    def ancestors(names, seen=None):
        seen = set() if seen is None else set(seen)
        pending = list(names)
        while pending:
            name = pending.pop()
            if name not in seen:
                seen.add(name)
                pending.extend(deps.get(name, []))
        return seen
    def depth(name, seen=frozenset()):
        if name not in cs or name in seen:
            return 0
        return 1 + max([depth(x, seen | {name}) for x in deps[name]] or [0])
    eqs = [c for c in dsl.get("conditions", []) if c.get("operator") == "="]
    supports = [ancestors(symbols(c.get("left")) | symbols(c.get("right"))) for c in eqs]
    eq_anc = set().union(*supports) if supports else set()
    target_symbols = symbols(dsl.get("target"))
    ta = ancestors(target_symbols)
    graph = {v: {v} for v in variables}
    for s in supports:
        vs = s & variables
        for v in vs:
            graph[v].update(vs)
    comps = []
    remaining = set(variables)
    while remaining:
        stack = [next(iter(remaining))]
        seen = set()
        while stack:
            v = stack.pop()
            if v not in seen:
                seen.add(v)
                stack.extend(graph[v] - seen)
        remaining -= seen
        comps.append(len(seen))
    return {
        "construction_depth": max([depth(c) for c in cs] or [0]),
        "target_depth": max([depth(c) for c in target_symbols] or [0]),
        "eq_max_support": max([len(s & variables) for s in supports] or [0]),
        "eq_mean_support": np.mean([len(s & variables) for s in supports]) if supports else 0,
        "eq_active_vars": len(eq_anc & variables),
        "eq_ancestors": len(eq_anc & set(cs)),
        "target_ancestors": len(ta & set(cs)),
        "target_only_constructions": len((ta - eq_anc) & set(cs)),
        "eq_largest_component": max(comps or [0]),
        "eq_n_components": len(comps),
    }


def partial_rho(df, x, y, controls):
    from scipy.stats import rankdata
    cols = [x, y] + controls
    z = np.array([[r.get(k, np.nan) for k in cols] for r in df], dtype=float)
    z = z[np.isfinite(z).all(axis=1)]
    if len(z) < 8 or len(np.unique(z[:, 0])) < 2 or len(np.unique(z[:, 1])) < 2:
        return {"n": len(z), "rho": None}
    ranked = np.column_stack([rankdata(z[:, i]) for i in range(len(cols))])
    mat = np.column_stack([np.ones(len(z)), ranked[:, 2:]])
    resid = ranked[:, :2] - mat @ np.linalg.lstsq(mat, ranked[:, :2], rcond=None)[0]
    return {"n": len(z), "rho": float(np.corrcoef(resid.T)[0, 1])}


def main():
    human = csv("jssa/difficulty/ghost-1023/human_feat.csv")
    profile = csv("jssa/results/stage-profile-20261023/per-case.csv")
    grouped = {}
    for r in profile:
        r["cost"] = r["wall_time_s"] if r["correct"] else 180.0
        grouped.setdefault(r["case_id"], []).append(r)
    prof = {}
    for k, rs in grouped.items():
        prof[k] = {col: float(np.mean([r[col] for r in rs])) for col in
                   ["cost", "refinement_time_s", "identification_verification_time_s", "search_time_s",
                    "candidates_sent_to_refinement", "candidates_rejected_as_false"]}
        prof[k]["successes"] = sum(r["correct"] for r in rs)
    rows, branch_rows = [], []
    cases = [json.loads(s) for s in read("benchmarks/cases.jsonl").splitlines() if s.strip()]
    for c in cases:
        row = {"case_id": c["id"], **structure(c["dsl"])}
        # Missing problem statements are not empty (easy) statements.
        row["statement_len"] = len(c["problem_statement"]) if c.get("problem_statement") else np.nan
        for seed, directory in [(0, "raw-323"), (1, "raw-323-seed1")]:
            f = f"jssa/difficulty/minima/{directory}/{c['id']}.json"
            if not (ROOT / f).exists():
                continue
            a = json.loads(read(f))
            records = a.get("records", [])
            n, h = len(records), sum(r.get("cls") == "hit" for r in records)
            row[f"n{seed}"] = n
            row[f"h{seed}"] = h
            row[f"p{seed}"] = h / n if n else np.nan
            row[f"difficulty{seed}"] = -math.log((h + 0.5) / (n + 1)) if n else np.nan
            first = list(a.get("first_hit", {}).values())
            sv = first[0].get("svals", []) if first else []
            if sv and sv[0] > 0:
                row[f"log_condition{seed}"] = math.log10(sv[0] / max(sv[-1], 1e-300))
                row[f"rank{seed}"] = sum(s > sv[0] * 1e-8 for s in sv)
                row[f"rank_defect{seed}"] = a["n_vars"] - row[f"rank{seed}"]
            refs = a.get("references", [])
            if len(refs) > 1:
                counts = [sum(r.get("cls") == "hit" and r.get("ref") == j for r in records) for j in range(len(refs))]
                branch_rows.append({"case_id": c["id"], "seed": seed, "n": n,
                                    "n_refs": len(refs), "references": json.dumps(refs),
                                    "hits": json.dumps(counts), "p_any": h / n if n else np.nan,
                                    "p_rarest": min(counts) / n if n else np.nan})
        rows.append(row)
    structural = {r["case_id"]: r for r in rows}
    phi = {r["id"]: r["n_feas"] / r["starts"] for r in csv("jssa/difficulty/start-feasibility-1023/per-problem.csv")}
    df = []
    for r in human:
        case_id = r["case_id"]
        row = {**r, **structural[case_id], **prof[case_id], "phi": phi.get(case_id, np.nan)}
        row["log_cost"] = math.log(row["cost"])
        df.append(row)
    write_csv("exploration-per-problem.csv", df)
    by_id = {r["case_id"]: r for r in df}
    branch = [{**r, **{k: by_id[r['case_id']][k] for k in ['human', 'cost', 'successes']}} for r in branch_rows]
    write_csv("branch-counts.csv", branch)
    metrics = {}
    feats = ["log_condition0", "rank_defect0", "construction_depth", "target_depth", "target_only_constructions",
             "eq_max_support", "eq_largest_component", "eq_n_components", "statement_len"]
    for group, data in [("all", df), ("AIME", [r for r in df if r['contest'] == 'AIME']),
                        ("HMMT", [r for r in df if r['contest'] == 'HMMT'])]:
        for x in feats:
            for y in ["human", "difficulty0", "log_cost"]:
                for controls in [[], ["n_vars"], ["n_vars", "n_cons"]]:
                    key = f"{group}:{x}:{y}:control={','.join(controls)}"
                    metrics[key] = partial_rho(data, x, y, controls)
    result = {"n": len(df), "human_n": sum(np.isfinite(r['human']) for r in df),
              "branch_problem_n": len({r['case_id'] for r in branch}),
              "branch_human_n": len({r['case_id'] for r in branch if np.isfinite(r['human'])}),
              "branch_rows": branch, "correlations": metrics}
    result['human_n'] = int(result['human_n'])
    result = json_safe(result)
    (OUT / "exploration-summary.json").write_text(json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False) + "\n")
    (OUT / "input-sha256.json").write_text(json.dumps(INPUTS, indent=2) + "\n")
    print(json.dumps({k: v for k, v in result.items() if k != "correlations"}, indent=2))
    for key, value in metrics.items():
        if key.endswith("control=n_vars") and (key.startswith("all:") or ":human:" in key):
            print(key, value)


if __name__ == "__main__":
    main()
