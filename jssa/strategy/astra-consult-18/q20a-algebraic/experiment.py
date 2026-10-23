"""Q20a: a small preregistered monodromy experiment; no src writes or LM starts.

Run from repository root with the specified Python, PYTHONPATH=src,
PYTHONDONTWRITEBYTECODE=1 and single-thread BLAS/OMP.
"""
from __future__ import annotations

import csv
import datetime as dt
import hashlib
import json
import math
from pathlib import Path
import platform
import sys
import time

import mpmath as mpmath
from mpmath import mp
import numpy as np
import scipy
import sympy as sp

from geosolver import GeometryProblem
from geosolver.engine.standard.evaluation.ir_evaluator import build_ir_evaluator
from geosolver.engine.standard.problem.infer_problem_bounds import infer_problem_bounds
from geosolver.engine.standard.problem.load_problem_bundle import load_problem_bundle


OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[3]
sys.path.insert(0, str(ROOT / "jssa/difficulty"))
from probe_basins import answer_float, reference_values  # noqa: E402

IDS = ["AIME-2007-I-15", "HMMT-2009-FEB-GEO-07", "HMMT-2013-FEB-GEO-04"]
mp.dps = 80


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def src_digest():
    h = hashlib.sha256()
    for p in sorted((ROOT / "src").rglob("*.py")):
        h.update(str(p.relative_to(ROOT)).encode())
        h.update(p.read_bytes())
    return h.hexdigest()


def write(name, obj):
    p = OUT / name
    p.write_text(json.dumps(obj, ensure_ascii=False, indent=2, allow_nan=False) + "\n")
    assert p.stat().st_size < 10_000_000


def small_complex(z):
    return {"re": mp.nstr(mp.re(z), 70), "im": mp.nstr(mp.im(z), 70)}


def params(case_id):
    if case_id == IDS[0]:
        return {"degree": 2, "a": mp.mpf(5), "b": mp.mpf(-231),
                "constant": mp.mpf(2223), "critical": mp.mpf(53361)/20}
    if case_id == IDS[1]:
        return {"degree": 2, "a": mp.mpf(1), "b": mp.mpf(-18),
                "constant": mp.mpf(56), "critical": mp.mpf(81)}
    return {"degree": 4, "constant": mp.mpf(1), "critical": mp.mpf(9)/4}


def poly(z, t, par):
    if par["degree"] == 2:
        return par["a"]*z*z + par["b"]*z + t
    return z**4 - 3*z*z + t


def derivative(z, par):
    return 2*par["a"]*z + par["b"] if par["degree"] == 2 else 4*z**3-6*z


def closed_roots(par, t):
    if par["degree"] == 2:
        d = mp.sqrt(par["b"]**2 - 4*par["a"]*t)
        return [(-par["b"]-d)/(2*par["a"]), (-par["b"]+d)/(2*par["a"])]
    d = mp.sqrt(9-4*t)
    a, b = mp.sqrt((3-d)/2), mp.sqrt((3+d)/2)
    return [-b, -a, a, b]


def reduce_coordinate(case_id, v):
    if case_id == IDS[0]:
        return mp.mpf(str(v["s"]))
    if case_id == IDS[1]:
        return mp.mpf(str(v["c"]))
    return mp.mpf(str(v["r2"]))/mp.mpf(str(v["r1"]))


def lift(case_id, z, original):
    if case_id == IDS[0]:
        u = (5*z-66)/3
        return {"s": z, "ex": u/2, "ey": mp.sqrt(3)*u/2}
    if case_id == IDS[1]:
        return {"c": z, "e": z-9, "h": 168/z}
    scale = mp.mpf(str(original["r1"]))
    x = 1-z*z/2
    return {"r1": scale, "r2": scale*z, "Ax": scale*x,
            "Ay": scale*mp.sqrt(1-x*x), "b": 2*scale*x}


def inspect_vector(bundle, ev, bounds, values, refs=None):
    """Original DSL checks; never uses saved cls/ref for candidate selection."""
    try:
        max_imag = max(abs(mp.im(values[n])) for n in bundle.var_names)
        x = [float(mp.re(values[n])) for n in bundle.var_names]
        residuals = np.asarray(ev.evaluate_float_residual(x).residual_vector, dtype=float)
        rn = float(np.linalg.norm(residuals))
        guard, _ = ev.evaluate_guard(x)
        hard = ev.evaluate_float_hard_feasibility(x, include_margins=False).hard_feasible
        box = all(lo <= v <= hi for v, (lo, hi) in zip(x, bounds))
        good = bool(max_imag < mp.mpf("1e-30") and math.isfinite(rn)
                    and rn <= 1e-8 and guard and hard and box)
        ans = answer_float(ev, x) if good else None
        match = None
        if refs is not None and ans is not None:
            match = next((i for i, r in enumerate(refs)
                          if abs(ans-r) <= 1e-6*max(1.0, abs(r))), None)
        return {"x": x, "residual_norm": rn if math.isfinite(rn) else None,
                "max_imaginary": str(max_imag), "guard": bool(guard),
                "hard": bool(hard), "box": box, "valid": good, "answer": ans,
                "reference_index": match}
    except Exception as error:
        return {"valid": False, "error": f"{type(error).__name__}: {error}"}


def correct(z, t, par, norm, fixed=False):
    n = 0
    for _ in range(4 if fixed else 8):
        if not fixed and abs(poly(z, t, par))/norm < mp.mpf("1e-40"):
            break
        z -= poly(z, t, par)/derivative(z, par)
        n += 1
    return z, n, abs(poly(z, t, par))/norm


def follow(z0, par, radius=None, fixed=False):
    R = par["critical"]-par["constant"] if radius is None else radius
    norm = R if fixed else max(mp.mpf(1), R)
    t0 = par["critical"]-R
    z, n0, initial_residual = correct(mp.mpc(z0), t0, par, norm)
    start = z
    rows, all_ok = [], initial_residual < mp.mpf("1e-40")
    tprev = t0
    tstart = time.perf_counter()
    for j in range(1, 65):
        tnext = t0 if j == 64 else par["critical"]-R*mp.exp(2*mp.pi*1j*j/64)
        zpredict = z-(tnext-tprev)/derivative(z, par)
        z, n, rr = correct(zpredict, tnext, par, norm, fixed=fixed)
        all_ok = all_ok and rr < mp.mpf("1e-35" if fixed else "1e-40")
        rows.append({"node": j, "parameter": small_complex(tnext), "z": small_complex(z),
                     "newton_steps": n, "normalized_residual": str(rr),
                     "inverse_derivative": str(1/abs(derivative(z, par)))})
        tprev = tnext
    elapsed = time.perf_counter()-tstart
    roots = closed_roots(par, t0)
    start_index = min(range(len(roots)), key=lambda j: abs(roots[j]-start))
    end_index = min(range(len(roots)), key=lambda j: abs(roots[j]-z))
    error = abs(roots[end_index]-z)/max(1, abs(roots[end_index]))
    return z, {"start": small_complex(start), "end": small_complex(z), "radius": str(R),
               "initial_corrections": n0, "start_index": start_index, "end_index": end_index,
               "swapped": start_index != end_index, "relative_endpoint_error": str(error),
               "all_nodes_pass": bool(all_ok), "newton_total": sum(r["newton_steps"] for r in rows),
               "newton_max": max(r["newton_steps"] for r in rows),
               "max_normalized_residual": str(max(mp.mpf(r["normalized_residual"]) for r in rows)),
               "track_sec": elapsed, "nodes": rows}


def symbolic_checks():
    s, u, c, t, r = sp.symbols("s u c t r")
    D = sp.Matrix([(s-u)/2+1, sp.sqrt(3)*(s-u-2)/2])
    F = sp.Matrix([5-u/2, -sp.sqrt(3)*u/2])
    cross = sp.expand(D[0]*F[1]-D[1]*F[0])
    q0 = 5*s*s-231*s+2223
    subst = sp.factor((D.dot(F)-28).subs(u, (5*s-66)/3))
    assert sp.expand(subst-sp.Rational(2,9)*q0) == 0
    assert sp.simplify(cross/sp.sqrt(3)-(3*u-5*s+10)/2) == 0
    q1 = sp.expand((c-9)**2-25)
    q2 = sp.expand((1-r*r)**2-r*r)
    assert q1 == c*c-18*c+56
    assert q2 == r**4-3*r*r+1
    polys = [(s, q0, 5*s*s-231*s+t), (c, q1, c*c-18*c+t), (r, q2, r**4-3*r*r+t)]
    rows = []
    for case_id, (var, q, deformation) in zip(IDS, polys):
        p = sp.Poly(q, var)
        exponents = [m[0] for m in p.monoms()]
        rows.append({"id": case_id, "polynomial": str(q),
                     "parameter_discriminant": str(sp.factor(sp.discriminant(deformation, var))),
                     "bkk_univariate": max(exponents)-min(exponents),
                     "complex_roots": p.degree(), "real_roots": int(p.count_roots(-sp.oo, sp.oo)),
                     "all_simple": sp.gcd(p, p.diff()).degree() == 0,
                     "note": "Counts refer to the explicitly reduced one-variable polynomial, not the DSL system."})
    return {"identities_pass": True, "aime_cross_over_sqrt3": str(sp.simplify(cross/sp.sqrt(3))),
            "aime_dot_minus_28_after_substitution": str(subst), "counts": rows}


def count_existing(case_id):
    rows = []
    for seed, folder in [(0, "raw-323"), (1, "raw-323-seed1")]:
        data = json.loads((ROOT / "jssa/difficulty/minima" / folder / (case_id+".json")).read_text())
        refs = data["references"]
        counts = [sum(r.get("cls") == "hit" and r.get("ref") == j for r in data["records"])
                  for j in range(len(refs))]
        n = len(data["records"])
        ps = [c/n for c in counts]
        e_all = sum(1/p for p in ps)-1/sum(ps)
        p20 = 1-sum((1-p)**20 for p in ps)+(1-sum(ps))**20
        rows.append({"id": case_id, "seed": seed, "n": n, "hits": counts, "probabilities": ps,
                     "p_any": sum(ps), "p_rarest": min(ps), "expected_iid_starts_for_both_plugin": e_all,
                     "probability_both_within_20_plugin": p20,
                     "mean_sec_per_start": sum(r["sec"] for r in data["records"])/n,
                     "saved_counts_match": counts == data["hits_by_ref"]})
    return rows


def main():
    started = time.perf_counter()
    lock = json.loads((OUT / "registration-lock.json").read_text())
    assert digest(OUT / "preregistration.md") == lock["sha256"]
    src_before = src_digest()
    case_file = ROOT / "benchmarks/cases.jsonl"
    cases = {c["id"]: c for c in map(json.loads, case_file.read_text().splitlines()) if c["id"] in IDS}
    symbolic_start = time.perf_counter()
    symbolic = symbolic_checks()
    symbolic["elapsed_sec"] = time.perf_counter()-symbolic_start
    write("symbolic-checks.json", symbolic)
    natural, sensitivities, existing = [], [], []
    for case_id in IDS:
        prep_start = time.perf_counter()
        case = cases[case_id]
        bundle = load_problem_bundle(GeometryProblem.model_validate(case["dsl"]).engine_document())
        ev = build_ir_evaluator(bundle)
        bounds = infer_problem_bounds(bundle)
        par = params(case_id)
        raw = json.loads((ROOT / "jssa/difficulty/minima/raw-323" / (case_id+".json")).read_text())
        rejection, chosen = [], None
        for rec in raw["records"]:
            if "x" not in rec:
                continue
            v = dict(zip(bundle.var_names, rec["x"]))
            check = inspect_vector(bundle, ev, bounds, v)
            if not check["valid"]:
                rejection.append({"k": rec["k"], "reason": "original_DSL_failed"})
                continue
            z = reduce_coordinate(case_id, v)
            qerr = abs(poly(z, par["constant"], par))/max(1, abs(z)**par["degree"])
            restored = lift(case_id, z, v)
            mismatch = max(abs(restored[n]-v[n])/max(1, abs(v[n])) for n in bundle.var_names)
            if qerr < mp.mpf("1e-8") and mismatch < mp.mpf("1e-6"):
                chosen = {"k": rec["k"], "coordinates": v, "qerr": str(qerr),
                          "lift_mismatch": str(mismatch), "check": check}
                break
            rejection.append({"k": rec["k"], "reason": "reduction_or_lift_inconsistent",
                              "qerr": str(qerr), "lift_mismatch": str(mismatch)})
        if chosen is None:
            natural.append({"id": case_id, "failed": "no_valid_saved_seed", "rejected": rejection})
            continue
        prep_time = time.perf_counter()-prep_start
        z0 = reduce_coordinate(case_id, chosen["coordinates"])
        z1, one = follow(z0, par)
        z2, two = follow(z1, par)
        # References enter only after the tracking and seed selection are complete.
        refs = reference_values(case["answer"])
        val_start = time.perf_counter()
        checks = [inspect_vector(bundle, ev, bounds, lift(case_id, z, chosen["coordinates"]), refs)
                  for z in [mp.mpc(one["start"]["re"], one["start"]["im"]), z1, z2]]
        validation_time = time.perf_counter()-val_start
        direct_start = time.perf_counter()
        roots = closed_roots(par, par["constant"])
        closed_time = time.perf_counter()-direct_start
        direct_validate_start = time.perf_counter()
        direct_checks = [inspect_vector(bundle, ev, bounds, lift(case_id, z, chosen["coordinates"]), refs)
                         for z in roots]
        direct_validation_time = time.perf_counter()-direct_validate_start
        var = sp.Symbol("z")
        expr = (5*var*var-231*var+2223 if case_id == IDS[0] else
                var*var-18*var+56 if case_id == IDS[1] else var**4-3*var*var+1)
        nroot_start = time.perf_counter()
        nroots = sp.Poly(expr, var).nroots(n=80, maxsteps=100)
        nroot_time = time.perf_counter()-nroot_start
        nroot_validate_start = time.perf_counter()
        nroot_checks = [inspect_vector(bundle, ev, bounds,
                                      lift(case_id, mp.mpc(str(sp.re(z)), str(sp.im(z))), chosen["coordinates"]), refs)
                        for z in nroots]
        nroot_validation_time = time.perf_counter()-nroot_validate_start
        one_no_nodes = {k:v for k,v in one.items() if k != "nodes"}
        two_no_nodes = {k:v for k,v in two.items() if k != "nodes"}
        success = (all(c["valid"] and c["reference_index"] is not None for c in checks)
                   and one["swapped"] and two["swapped"] and one["all_nodes_pass"] and two["all_nodes_pass"]
                   and checks[0]["reference_index"] != checks[1]["reference_index"]
                   and checks[0]["reference_index"] == checks[2]["reference_index"])
        row = {"id": case_id, "selected_seed": chosen, "rejected_seeds": rejection,
               "preparation_sec": prep_time, "one_loop": one_no_nodes, "two_loop": two_no_nodes,
               "original_DSL_checks": checks, "validation_sec": validation_time,
               "closed_root_sec": closed_time, "closed_validation_sec": direct_validation_time,
               "closed_checks": direct_checks, "nroots_sec": nroot_time,
               "nroots_validation_sec": nroot_validation_time, "nroots_checks": nroot_checks,
               "success": success}
        natural.append(row)
        write(case_id+"-paths.json", {"loop1": one, "loop2": two})
        existing.extend(count_existing(case_id))
        print(case_id, "success=", success, "Newton steps", one["newton_total"], two["newton_total"], flush=True)
        if par["degree"] == 2:
            for exponent in [2, 8, 16, 24]:
                R = mp.mpf(10)**(-exponent)
                t0 = par["critical"]-R
                zstart = closed_roots(par, t0)[0]
                zend, result = follow(zstart, par, radius=R, fixed=True)
                halfgap = mp.sqrt(R/par["a"])
                cent = -par["b"]/(2*par["a"])
                scaled_endpoint_error = abs((zend-cent)/halfgap-1)
                sensitivities.append({"id": case_id, "radius": str(R), "exponent": exponent,
                                      "inverse_derivative_at_start": str(1/abs(derivative(zstart, par))),
                                      "scaled_endpoint_error": str(scaled_endpoint_error),
                                      **{k:v for k,v in result.items() if k != "nodes"}})
    write("natural-results.json", natural)
    write("distance-controls.json", sensitivities)
    write("existing-basins.json", existing)
    human = {r["case_id"]: r for r in csv.DictReader((ROOT / "jssa/difficulty/ghost-1023/human_feat.csv").open())}
    human_rows = [{"id": cid, "human": human.get(cid, {}).get("human", "")} for cid in IDS]
    src_after = src_digest()
    registration_unchanged = digest(OUT / "preregistration.md") == lock["sha256"]
    summary = {"natural_successes": sum(r.get("success", False) for r in natural), "natural_n": 3,
               "distance_controls_successes": sum(r["all_nodes_pass"] and r["swapped"]
                                                  and mp.mpf(r["scaled_endpoint_error"]) < mp.mpf("1e-30")
                                                  for r in sensitivities),
               "distance_controls_n": len(sensitivities), "human": human_rows,
               "src_sha256_before": src_before, "src_sha256_after": src_after,
               "src_unchanged": src_before == src_after, "preregistration_unchanged": registration_unchanged,
               "elapsed_sec_excluding_import": time.perf_counter()-started}
    write("summary.json", summary)
    provenance = {"finished_utc": dt.datetime.now(dt.timezone.utc).isoformat(), "python": sys.executable,
                  "python_version": platform.python_version(), "numpy": np.__version__, "scipy": scipy.__version__,
                  "sympy": sp.__version__, "mpmath": mpmath.__version__, "precision": mp.dps,
                  "script_sha256": digest(__file__), "input_cases_sha256": digest(case_file),
                  "registration_sha256": lock["sha256"],
                  "selected_dsl_sha256": {cid: hashlib.sha256(json.dumps(cases[cid]["dsl"], sort_keys=True).encode()).hexdigest() for cid in IDS},
                  "raw_sha256": {f"{seed}/{cid}": digest(ROOT/"jssa/difficulty/minima"/folder/(cid+".json"))
                                 for seed, folder in [(0,"raw-323"),(1,"raw-323-seed1")] for cid in IDS},
                  "limitations": ["Manual reduction and saved initial root; not a full solver run.",
                                  "Runtime single runs on a busy shared machine; no small speed claims.",
                                  "Numerical tracking is not a certified path tracker.",
                                  "No random local search starts were launched."]}
    write("provenance.json", provenance)
    assert summary["src_unchanged"] and registration_unchanged
    print(json.dumps(summary, ensure_ascii=False, indent=2), flush=True)


if __name__ == "__main__":
    main()
