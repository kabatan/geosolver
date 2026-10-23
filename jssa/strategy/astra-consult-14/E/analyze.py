"""Exploratory target-dependency audit; writes only in this E directory.

Run with the designated Python, -B and BLAS threads=1. No solver runs here.
Human labels come ONLY from human_feat.csv; downloaded ratings audit the join.
"""
from __future__ import annotations

import ast
import csv
import hashlib
import json
import math
import re
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
import scipy
from scipy.stats import rankdata, spearmanr

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[3]
SEED = 10231405
B = 2000


def readcsv(rel, key):
    return {r[key]: r for r in csv.DictReader((ROOT / rel).open())}


def writecsv(name, rows):
    with (OUT / name).open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


def dump(name, value):
    (OUT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False)+"\n")


def finite(x):
    try:
        return math.isfinite(float(x))
    except (TypeError, ValueError):
        return False


def references(expr, names):
    tree = ast.parse(str(expr).replace("^", "**"), mode="eval")
    return {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)} & names


def features(dsl):
    cons = {c["name"]: c["expression"] for c in dsl["constructions"]}
    assert len(cons) == len(dsl["constructions"]), "duplicate construction name"
    deps = {k: references(v, set(cons)) for k, v in cons.items()}
    ancestor_cache, depth_cache = {}, {}

    def ancestors(name, visiting=frozenset()):
        if name in visiting:
            raise ValueError("cyclic construction dependency")
        if name not in ancestor_cache:
            aa = {name}
            for p in deps[name]:
                aa |= ancestors(p, visiting | {name})
            ancestor_cache[name] = aa
            depth_cache[name] = 1 + max((depth_cache[p] for p in deps[name]), default=0)
        return ancestor_cache[name]

    for n in cons:
        ancestors(n)

    def closure(expressions):
        aa = set()
        for expr in expressions:
            for n in references(expr, set(cons)):
                aa |= ancestor_cache[n]
        return aa

    eq_expr, guard_expr = [], []
    for c in dsl["conditions"]:
        dest = eq_expr if c.get("operator") == "=" else guard_expr
        dest.extend(c[k] for k in ("left", "right", "predicate") if k in c)
    target = closure([dsl["target"]])
    eq, guards = closure(eq_expr), closure(guard_expr)
    result = dict(
        target_ancestors=len(target), target_depth=max((depth_cache[n] for n in target), default=0),
        target_only=len(target - eq - guards), target_not_eq=len(target - eq),
        condition_ancestors=len(eq | guards), equality_ancestors=len(eq),
        target_only_names=";".join(sorted(target-eq-guards)),
        target_ancestor_names=";".join(sorted(target)),
        construction_depth=max(depth_cache.values(), default=0))
    return result


def source_id(r):
    if r["contest"] == "AIME":
        return f'AIME-{r["year"]}-{r["subtest"]}-{r["index"]:02d}'
    if r["contest"] == "HMMT":
        return f'HMMT-{r["year"]}-{r["month"].upper()}-{r["subtest"].upper()}-{r["index"]:02d}'
    return ""


def rank_contest(values, contests):
    values, contests = np.asarray(values, float), np.asarray(contests)
    ans = np.zeros(len(values))
    for c in sorted(set(contests)):
        mask = contests == c
        ans[mask] = (rankdata(values[mask]) - .5) / sum(mask)
    return ans


def corr(x, y):
    x, y = np.asarray(x), np.asarray(y)
    if np.std(x) < 1e-12 or np.std(y) < 1e-12:
        return float("nan")
    return float(np.corrcoef(x, y)[0, 1])


def partial(rows, feature, outcome, controls):
    contests = np.array([r["contest"] for r in rows])
    rank = lambda k: rank_contest([r[k] for r in rows], contests)
    xx = np.column_stack([np.ones(len(rows)), contests == "HMMT", *[rank(k) for k in controls]])
    x, y = rank(feature), rank(outcome)
    x = x - xx @ np.linalg.lstsq(xx, x, rcond=None)[0]
    y = y - xx @ np.linalg.lstsq(xx, y, rcond=None)[0]
    return corr(x, y)


def interval(values):
    v = np.array(values)
    v = v[np.isfinite(v)]
    return [float(z) for z in np.quantile(v, [.025, .975])] if len(v) else [None, None]


def compare(rows, feature, controls=("n_vars", "n_cons"), outcome="solver_difficulty"):
    other = all(finite(r.get(outcome)) for r in rows)

    def statistic(rr):
        h = partial(rr, feature, "human", controls)
        if other:
            s = partial(rr, feature, outcome, controls)
            return h, s, h-s
        return (h,)
    point = statistic(rows)
    rng = np.random.default_rng(SEED)
    groups = [[i for i,r in enumerate(rows) if r["contest"] == c] for c in sorted({r["contest"] for r in rows})]
    samples = []
    for _ in range(B):
        idx = np.concatenate([rng.choice(g, len(g), replace=True) for g in groups])
        samples.append(statistic([rows[i] for i in idx]))
    vals = np.asarray(samples)
    names = ("human", outcome, "human_minus_solver") if other else ("human",)
    return {"n": len(rows), "feature": feature, "controls": list(controls),
            **{k: {"rho": point[j], "ci95": interval(vals[:,j])} for j,k in enumerate(names)}}


def ecdf(train, values):
    train = np.sort(train)
    return (np.searchsorted(train, values, "left") + np.searchsorted(train, values, "right")) / (2*len(train))


def cv(rows, outcome, extra_controls):
    rows = [r for r in rows if finite(r.get(outcome)) and all(finite(r.get(k)) for k in extra_controls)]
    n = len(rows)
    contests = np.array([r["contest"] for r in rows])
    years = np.array([r["year"] for r in rows])
    raw_y = np.array([r[outcome] for r in rows])
    d = np.minimum([r["n_vars"] for r in rows], 5)
    base = np.column_stack([*(d==i for i in range(1,6)),
                            np.log1p([r["n_cons"] for r in rows]), contests=="HMMT",
                            *[np.log1p([r[k] for r in rows]) for k in extra_controls]])
    adds = np.array([[r["target_only"], r["target_depth"]] for r in rows])
    predictions = np.zeros((n,2))
    y = np.zeros(n)
    for year in sorted(set(years)):
        train, test = years != year, years == year
        fold_y = np.zeros(n)
        for contest in sorted(set(contests)):
            tt = train & (contests==contest)
            aa = contests==contest
            fold_y[aa] = ecdf(raw_y[tt], raw_y[aa])
        y[test] = fold_y[test]
        for j, x in enumerate([base, np.column_stack([base,adds])]):
            mu, sd = x[train].mean(0), x[train].std(0)
            sd[sd<1e-12]=1
            x = np.column_stack([np.ones(n), (x-mu)/sd])
            penalty = np.eye(x.shape[1]); penalty[0,0]=0
            beta = np.linalg.solve(x[train].T @ x[train] + penalty, x[train].T @ fold_y[train])
            predictions[test,j] = x[test] @ beta
    squared = (predictions-y[:,None])**2
    delta = squared[:,1]-squared[:,0]
    # Uncertainty of fixed OOF residuals, not full nested retraining uncertainty.
    rng = np.random.default_rng(SEED+2)
    year_groups = [np.flatnonzero(years==t) for t in sorted(set(years))]
    ci = interval([np.mean(delta[np.concatenate([year_groups[g] for g in rng.integers(len(year_groups), size=len(year_groups))])]) for _ in range(B)])
    records = [{"id": r["id"], "year": r["year"], "contest": r["contest"], "y_train_ecdf": y[i],
                "prediction_base": predictions[i,0], "prediction_plus_target": predictions[i,1],
                "loss_difference": delta[i]} for i,r in enumerate(rows)]
    suffix = "_".join(extra_controls) or "base"
    writecsv(f"cv-{outcome}-{suffix}.csv", records)
    return {"n": n, "outcome": outcome, "extra_controls": list(extra_controls),
            "years": len(set(years)), "mse_base": float(squared[:,0].mean()),
            "mse_plus_target": float(squared[:,1].mean()), "delta_mse": float(delta.mean()),
            "relative_improvement": float(1-squared[:,1].mean()/squared[:,0].mean()),
            "delta_ci95_fixed_oof_year_bootstrap": ci}


def main():
    t0 = time.monotonic()
    paths = [ROOT / p for p in ("benchmarks/cases.jsonl", "jssa/difficulty/ghost-1023/human_feat.csv", "jssa/difficulty/minima/basins-323.csv")]
    inputs = {str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    humans = readcsv("jssa/difficulty/ghost-1023/human_feat.csv", "case_id")
    basins = readcsv("jssa/difficulty/minima/basins-323.csv", "id")
    cases = [json.loads(l) for l in paths[0].read_text().splitlines()]
    sources = defaultdict(list)
    source_path = OUT / "e2h-rows.jsonl"
    if source_path.exists():
        inputs[str(source_path.relative_to(ROOT))] = hashlib.sha256(source_path.read_bytes()).hexdigest()
        for l in source_path.read_text().splitlines():
            r = json.loads(l); sources[source_id(r)].append(r)
    rows, joins, texts = [], [], []
    for c in cases:
        h, b, d = humans[c["id"]], basins.get(c["id"],{}), c["dsl"]
        row = dict(id=c["id"], contest=h["contest"], year=int(re.search(r"20\d\d", c["id"])[0]),
                   n_vars=int(h["n_vars"]), n_cons=len(d["constructions"]), n_eq=int(h["n_eq"]),
                   n_ineq=int(h["n_ineq"]), human=float(h["human"]) if h["human"] else None,
                   C=float(h["C"]), pos=float(h["pos"]) if h["pos"] else None,
                   p=float(b["p"]) if finite(b.get("p")) and int(h["n_vars"])>0 else None,
                   n_starts=int(b["n_starts"]) if finite(b.get("n_starts")) else 0,
                   **features(d))
        row["solver_difficulty"] = 1-row["p"] if row["p"] is not None else None
        row.update(text_words=None, text_chars=None, diagram_code=False)
        if row["human"] is not None:
            matches=sources.get(c["id"],[])
            join=dict(id=c["id"], n_matches=len(matches), rating_difference=None, truncated_cells="")
            if len(matches)==1:
                s=matches[0]
                raw=s["problem"]
                clean=re.sub(r"\[asy\].*?\[/asy\]", " ", raw, flags=re.S|re.I)
                clean=re.sub(r"\\begin\{asy\}.*?\\end\{asy\}", " ", clean, flags=re.S)
                row.update(text_words=len(clean.split()), text_chars=len(clean), diagram_code=(raw!=clean))
                join.update(rating_difference=s["rating"]-row["human"], truncated_cells=json.dumps(s["truncated_cells"]))
                texts.append({"id": c["id"], "problem":raw, "split":s["split"], "row_idx":s["row_idx"],
                              "source":"https://huggingface.co/datasets/furonghuang-lab/Easy2Hard-Bench",
                              "license":"CC-BY-SA-4.0", "human_source":row["human"]})
            joins.append(join)
        rows.append(row)
    writecsv("features.csv", rows)
    writecsv("source-join.csv", joins)
    (OUT / "human-problems.jsonl").write_text("".join(json.dumps(t,ensure_ascii=False)+"\n" for t in texts))
    human=[r for r in rows if r["human"] is not None]
    common=[r for r in human if r["p"] is not None]
    complete=[r for r in human if r["text_words"] is not None]
    measures=[]
    for feature in ("target_only", "target_depth", "target_ancestors"):
        measures.append({"set":"all_human", **compare(human,feature)})
        measures.append({"set":"common", **compare(common,feature)})
        if len(complete)>20:
            measures.append({"set":"text_control", **compare(complete,feature,("n_vars","n_cons","text_words"))})
    descriptive=[]
    for contest in ("all", "AIME", "HMMT"):
        rr=[r for r in human if contest=="all" or r["contest"]==contest]
        for f in ("target_only", "target_depth", "target_ancestors", "n_cons", "n_vars", "text_words"):
            ss=[r for r in rr if finite(r.get(f))]
            descriptive.append({"contest":contest,"feature":f,"n":len(ss),"rho":partial(ss,f,"human",()),
                                "partial_rho":partial(ss,f,"human",("n_vars","n_cons")) if f not in ("n_vars","n_cons") else None})
    results=dict(
        n_all=len(rows), n_human=len(human), n_common=len(common), n_text=len(complete),
        human_contests=dict(Counter(r["contest"] for r in human)),
        common_contests=dict(Counter(r["contest"] for r in common)),
        target_only_positive=sum(r["target_only"]>0 for r in human),
        zero_variable_human=sum(r["n_vars"]==0 for r in human),
        join_unique=sum(j["n_matches"]==1 for j in joins),
        join_max_rating_difference=max((abs(j["rating_difference"]) for j in joins if j["rating_difference"] is not None),default=None),
        descriptive=descriptive, comparisons=measures,
        cv=[cv(human,"human",()), cv(common,"solver_difficulty",()),
            cv(human,"human",("text_words",)), cv(human,"human",("text_words","pos"))],
        bootstrap=B, seed=SEED, elapsed_sec=time.monotonic()-t0,
        notes="Exploratory development corpus. Bootstrap does not propagate uncertainty of human labels or finite-start p. Target DAG is not a proof graph.")
    dump("stats.json", results)
    dump("analysis-manifest.json",dict(inputs=inputs, python=sys.version, numpy=np.__version__, scipy=scipy.__version__,
         script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()))
    print(json.dumps({k:v for k,v in results.items() if k not in ("descriptive","comparisons")},ensure_ascii=False,indent=2))
    for m in measures:
        print(m)


if __name__ == "__main__":
    main()
