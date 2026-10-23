"""Read-only geometry evaluation: no root finding, local solve, or endpoint access.

Run with the existing /home/kabatan/work/solver/.venv/bin/python -B.
See protocol.md for the frozen exploratory definition and its limitations.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import sys
import time
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "jssa/difficulty"))

import numpy as np
from mpmath import mp
from geosolver import GeometryProblem
from geosolver.engine.standard.evaluation.ir_evaluator import build_ir_evaluator
from geosolver.engine.standard.evaluation.snapshots import evaluation_session, numerical_snapshot
from geosolver.engine.standard.problem.infer_problem_bounds import infer_problem_bounds
from geosolver.engine.standard.problem.load_problem_bundle import load_problem_bundle
from geosolver.problem.ir.compiler import safe_eval_expr_hp
from ghost_scan import point_names

THRESHOLDS = (0.003, 0.01, 0.03)
FIELDS = [
    "id", "status", "n_vars", "n_eq", "n_points", "n_names", "n_pairs",
    "excluded_pairs", "point_names", "n_samples", "n_valid", "coverage",
    "n_near", "n_gradient_valid", "n_gradient_failed", "A", "A_upper",
    "A_given_valid", "A_tau003", "A_tau03", "frac_near", "median_c",
    "mean_cos_near", "elapsed_sec", "error",
]


class GeometryProbe:
    def __init__(self, dsl):
        self.bundle = load_problem_bundle(GeometryProblem.model_validate(dsl).engine_document())
        self.evaluator = build_ir_evaluator(self.bundle)
        self.names = point_names(dsl)
        self.var_names = list(self.bundle.var_names)
        self.bounds = np.asarray(infer_problem_bounds(self.bundle), dtype=float)
        self.lower = self.bounds[:, 0]
        self.width = self.bounds[:, 1] - self.bounds[:, 0]
        self.expressions = [*self.bundle.spec.constraints,
                            *(t for t in self.bundle.targets if isinstance(t, str)),
                            *self.names]

    def evaluate(self, z):
        x = (self.lower + self.width * z).tolist()
        b = self.bundle
        # This is the same binary64 construction/residual path as float_expressions.py.
        # One shared snapshot avoids recompiling every x/y target for every point.
        with mp.workprec(53), evaluation_session(self.evaluator):
            snap = numerical_snapshot(b.spec, self.var_names, x, dict(b.base_context), arithmetic="float")
            ctx = snap.for_expressions(self.expressions, partial=True)
            coords = np.full((len(self.names), 2), np.nan)
            for k, name in enumerate(self.names):
                try:
                    obj = ctx[name]
                    coords[k] = float(obj.x), float(obj.y)
                except (AttributeError, KeyError, TypeError, ValueError, OverflowError):
                    pass
            residuals = []
            for expr, target in zip(b.spec.constraints, b.targets, strict=True):
                try:
                    lhs = safe_eval_expr_hp(expr, ctx)
                    rhs = safe_eval_expr_hp(target, ctx) if isinstance(target, str) else target
                    residuals.append(float(lhs) - float(rhs))
                except Exception:
                    residuals.append(float("nan"))
        return np.asarray(residuals), coords


def distances(coords):
    a, b = np.triu_indices(len(coords), 1)
    dist = np.hypot(*(coords[a] - coords[b]).T)
    diameter = np.max(dist) if len(dist) else float("nan")
    return a, b, dist, diameter


def cosine(g, h):
    ng, nh = np.linalg.norm(g), np.linalg.norm(h)
    if not np.isfinite(ng + nh):
        return float("nan")
    if ng < 1e-12 or nh < 1e-12:
        return 0.0
    return float(np.clip(np.dot(g / ng, h / nh), -1, 1))


def measure(cid, dsl, n=256, h=1e-5):
    t0 = time.monotonic()
    probe = GeometryProbe(dsl)
    row = {"id": cid, "n_vars": len(probe.var_names), "n_eq": len(probe.bundle.targets),
           "n_names": len(probe.names), "n_samples": n}
    key = int(hashlib.sha256(cid.encode()).hexdigest()[:8], 16)
    rng = np.random.default_rng([20261023, key])
    calib = [probe.evaluate(z)[1] for z in rng.random((32, len(probe.var_names)))]
    calib = np.asarray(calib)
    # Retain objects actually evaluated as real points at >=16 calibration sites.
    is_point = np.sum(np.isfinite(calib).all(axis=2), axis=0) >= 16
    keep = np.flatnonzero(is_point)
    names = [probe.names[j] for j in keep]
    row.update(n_points=len(keep), point_names="|".join(names))
    if len(keep) < 2:
        return {**row, "status": "insufficient_points", "elapsed_sec": time.monotonic()-t0}
    calib = calib[:, keep]
    pa, pb = np.triu_indices(len(keep), 1)
    ratio = []
    for c in calib:
        _, _, dd, diam = distances(c)
        ratio.append(dd / diam if diam > 0 else np.full(len(pa), np.nan))
    ratio = np.asarray(ratio)
    ident = ((np.isfinite(ratio).sum(axis=0) >= 16)
             & np.all((ratio <= 1e-10) | ~np.isfinite(ratio), axis=0))
    use_pairs = ~ident
    row.update(n_pairs=int(use_pairs.sum()),
               excluded_pairs="|".join(f"{names[a]}:{names[b]}" for a,b in zip(pa[ident],pb[ident])))
    if not np.any(use_pairs):
        return {**row, "status": "no_nonconstant_pairs", "elapsed_sec": time.monotonic()-t0}

    def energy_and_sep(z):
        f, all_coords = probe.evaluate(z)
        coords = all_coords[keep]
        # An empty equality vector has energy zero, hence zero attraction;
        # it is not an evaluation failure (some cases have only inequalities).
        if not np.isfinite(f).all() or not np.isfinite(coords).all():
            return None
        _, _, dd, diam = distances(coords)
        if not diam > 0 or not math.isfinite(diam):
            return None
        sep = float(np.min(dd[use_pairs]) / diam)
        norm = math.hypot(*f)
        if not math.isfinite(norm):
            return None
        energy = math.log1p(norm*norm) if norm < 1e150 else 2*math.log(norm)
        return energy, sep

    scores = np.zeros((n, len(THRESHOLDS)))
    seps, cosines = [], []
    near = grad_valid = grad_failed = valid = 0
    for k, z in enumerate(rng.random((n, len(probe.var_names)))):
        base = energy_and_sep(z)
        if base is None:
            continue
        valid += 1
        _, sep = base
        seps.append(sep)
        if sep < 0.01:
            near += 1
        if not 1e-12 < sep < max(THRESHOLDS):
            continue
        ge, gs = [], []
        for j in range(len(z)):
            zp, zm = z.copy(), z.copy()
            zp[j] += h
            zm[j] -= h
            ep, em = energy_and_sep(zp), energy_and_sep(zm)
            if ep is None or em is None or min(ep[1],em[1]) <= 1e-14:
                break
            ge.append((ep[0]-em[0])/(2*h))
            gs.append((math.log(ep[1])-math.log(em[1]))/(2*h))
        if len(ge) != len(z):
            if sep < 0.01:
                grad_failed += 1
            continue
        co = cosine(np.asarray(ge), np.asarray(gs))
        if not math.isfinite(co):
            if sep < 0.01:
                grad_failed += 1
            continue
        if sep < 0.01:
            grad_valid += 1
            cosines.append(co)
        scores[k] = [max(0., co) if sep < tau else 0. for tau in THRESHOLDS]
    a = scores.mean(axis=0)
    row.update(status="ok" if valid/n >= 0.8 else "low_coverage", n_valid=valid,
               coverage=valid/n, n_near=near, n_gradient_valid=grad_valid,
               n_gradient_failed=grad_failed, A=a[1], A_upper=min(1.,a[1]+(n-valid+grad_failed)/n),
               A_given_valid=scores[:,1].sum()/valid if valid else float("nan"),
               A_tau003=a[0], A_tau03=a[2], frac_near=near/n,
               median_c=float(np.median(seps)) if seps else float("nan"),
               mean_cos_near=float(np.mean(cosines)) if cosines else float("nan"),
               elapsed_sec=time.monotonic()-t0)
    return row


def self_check(cases):
    from probe_basins import construction_coordinates, answer_float
    assert cosine(np.array([1.]),np.array([1.])) == 1.
    assert cosine(np.array([1.]),np.array([-1.])) == -1.
    results = []
    for cid in ["AIME-2020-II-15", "AIME-2014-II-14", "AIME-2006-I-01"]:
        dsl = cases[cid]["dsl"]
        probe = GeometryProbe(dsl)
        z = np.linspace(0.37,0.61,len(probe.var_names))
        f, coords = probe.evaluate(z)
        x = (probe.lower+probe.width*z).tolist()
        expected = probe.evaluator.evaluate_float_residual(x).residual_vector
        np.testing.assert_allclose(f,expected,rtol=1e-12,atol=1e-12)
        indices = [j for j in range(len(probe.names)) if np.isfinite(coords[j]).all()][:4]
        cc = construction_coordinates(dsl,[probe.names[j] for j in indices])
        vals = dict(zip(probe.var_names,x))
        max_error = 0.
        for j in indices:
            for axis_idx,axis in enumerate("xy"):
                vn,ev = cc[f"{axis}_{probe.names[j]}"]
                v = answer_float(ev,[vals[v] for v in vn])
                err = abs(v-coords[j,axis_idx])/max(1.,abs(v))
                max_error = max(max_error,err)
                assert err < 1e-9,(cid,probe.names[j],axis,v,coords[j,axis_idx])
        results.append({"id":cid,"residuals_match":True,"max_coordinate_scaled_error":max_error})
    (HERE/"self-check.json").write_text(json.dumps(results,indent=2)+"\n")
    print(json.dumps(results),flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ids",nargs="*")
    ap.add_argument("--output",default="attraction.csv")
    ap.add_argument("--samples",type=int,default=256)
    ap.add_argument("--h",type=float,default=1e-5)
    ap.add_argument("--self-check",action="store_true")
    args = ap.parse_args()
    output = (HERE/args.output).resolve()
    if output.parent != HERE:
        raise ValueError("Output must remain inside A/")
    cases = {c["id"]:c for c in map(json.loads,(ROOT/"benchmarks/cases.jsonl").read_text().splitlines())}
    if args.self_check:
        self_check(cases)
        return
    # Only identifiers and variable counts are consumed here, not p or endpoints.
    with (ROOT/"jssa/difficulty/minima/basins-323.csv").open() as f:
        ids = sorted(r["id"] for r in csv.DictReader(f) if int(r["n_vars"] or 0)>=1)
    if args.ids:
        ids = [cid for cid in ids if cid in args.ids]
    with output.open("w",newline="") as f:
        writer = csv.DictWriter(f,fieldnames=FIELDS)
        writer.writeheader()
        for k,cid in enumerate(ids):
            try:
                row = measure(cid,cases[cid]["dsl"],args.samples,args.h)
            except Exception as err:
                row = {"id":cid,"status":"error","error":f"{type(err).__name__}: {err}"}
            writer.writerow(row)
            f.flush()
            print(f"{k+1}/{len(ids)} {cid} {row['status']} A={row.get('A')} sec={row.get('elapsed_sec')}",flush=True)


if __name__ == "__main__":
    main()
