"""One preregistered, resource-limited Q11 certification attempt.

Generator: astra-L's extended Groebner basis and saturation certificates.
Verifier: astra-L's independent Fraction sparse-polynomial arithmetic.
Numerics: exact function definitions extracted from L/experiment.py, without
executing that script's top-level hooks, filesystem operations, or experiment.
"""
import ast
from contextlib import contextmanager
import hashlib
import json
import math
import os
from pathlib import Path
import sys
import time

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
L = ROOT / "jssa/strategy/astra-consult-17/L"
START = float(os.environ.get("Q11_START", time.monotonic()))
END = START + 60
for k in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
    os.environ[k] = "1"
sys.path.insert(0, str(L / "vendor"))
sys.path.insert(0, str(L))
sys.path.insert(0, str(ROOT / "src"))
import numpy as np
from scipy.linalg import qr
import sympy as sp
from mpmath import mp
from certificate import Prover, encode, make_certificate, primitive, deadline, Limit
from verify_certificate import verify
from algebraize import Unsupported
from geosolver import GeometryProblem
from geosolver.engine.standard.evaluation.ir_evaluator import build_ir_evaluator
from geosolver.engine.standard.problem.load_problem_bundle import load_problem_bundle
from geosolver.engine.standard.precision.type_guards.high_precision_mode import high_precision_mode
sys.path.insert(0, str(HERE))
from bounds import target_bounds

_source = ast.parse((L / "experiment.py").read_text())
_functions = ast.Module(body=[n for n in _source.body if isinstance(n, ast.FunctionDef) and n.name in ("polish", "pslq", "evaluator", "hard", "zero_dim")], type_ignores=[])
exec(compile(_functions, str(L / "experiment.py"), "exec"), globals())


def stable_json(o):
    return json.dumps(o, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False, default=str).encode()


def save(path, o):
    data = stable_json(o)
    if len(data) >= 8 * 1024**2: raise Limit("artifact size cap")
    path.write_bytes(data + b"\n")


def protection(event, args):
    if event == "open" and isinstance(args[0], (str, bytes)):
        p = Path(os.fsdecode(args[0])).resolve()
        mode = args[1]
        flags = args[2] if len(args) > 2 else 0
        writing = isinstance(mode, str) and any(c in mode for c in "wax+")
        writing |= isinstance(flags, int) and bool(flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC))
        if writing and not p.is_relative_to(HERE):
            raise PermissionError("Q11 worker writes only within certify-all")
        if p.name == "cases.jsonl" or any(x in p.parts for x in ("raw-323", "raw-323-seed1", "audit_source")):
            raise PermissionError("Q11 worker cannot read reference-bearing source data")


def root_intervals(poly, t):
    p = sp.Poly(poly, t, domain=sp.QQ).sqf_part()
    return [ab for ab, _ in p.intervals(eps=sp.Rational(1, 10**24))]


def root_count(p, lo, hi, lop, hip):
    if p.degree() <= 0: return 0
    k = int(p.count_roots(lo, hi))
    if lop and lo.is_finite and p.eval(lo) == 0: k -= 1
    if hip and hi.is_finite and p.eval(hi) == 0: k -= 1
    return k


def numeric_root(p, t, value):
    """Define a candidate as a polynomial plus a rational isolating interval.

    The float selects an algebraic root, never an allowed geometric range.
    The separation and closeness checks make that selection explicit.
    """
    ivs = root_intervals(p, t)
    v = sp.Rational(str(value))
    tol = sp.Rational(1, 10**7) * max(1, abs(v))
    near = [(a, b) for a, b in ivs if a - tol <= v <= b + tol]
    if len(near) != 1: raise ValueError("candidate has no unique nearby PSLQ root")
    a, b = near[0]
    eps = sp.Rational(1, 10**30)
    if a == b: a, b = a - eps, b + eps
    # Make endpoints nonroots so root counts are unambiguous.
    pp = sp.Poly(p, t, domain=sp.QQ)
    if pp.eval(a) == 0: a -= eps
    if pp.eval(b) == 0: b += eps
    assert int(pp.sqf_part().count_roots(a, b)) == 1
    return a, b


def check_roots(q, t, bound, candidates):
    qq = sp.Poly(q, t, domain=sp.QQ).sqf_part()
    lo, hi, lop, hip = bound
    count = root_count(qq, lo, hi, lop, hip)
    all_iv = root_intervals(q, t)
    matching = []
    for c in candidates:
        pp = sp.Poly(c["P_expr"], t, domain=sp.QQ)
        common = sp.gcd(qq, pp)
        a, b = c["root_interval_exact"]
        if not (a >= lo and b <= hi):
            # A rational endpoint of the allowed interval may itself be a root.
            # If so, intersect first; no numerical inclusion test is used.
            a, b = max(a, lo), min(b, hi)
        hits = root_count(common, a, b, lop and a == lo, hip and b == hi) if a <= b else 0
        matching.append(hits == 1)
    # Intervals for different candidate roots must be disjoint. Equal values from
    # different PSLQ polynomials are merged only after an exact gcd root check.
    unique_candidates = []
    for c in candidates:
        a, b = c["root_interval_exact"]
        duplicate = False
        for old in unique_candidates:
            x, y = old["root_interval_exact"]
            u, v = max(a, x), min(b, y)
            if u <= v:
                g = sp.gcd(sp.Poly(c["P_expr"], t), sp.Poly(old["P_expr"], t))
                if g.degree() > 0 and int(g.count_roots(u, v)) == 1: duplicate = True
        if not duplicate: unique_candidates.append(c)
    return {
        "range": [str(lo), str(hi), lop, hip],
        "all_real_root_intervals": [[str(a), str(b)] for a, b in all_iv],
        "allowed_root_count": count, "candidate_count": len(unique_candidates),
        "candidate_matches": matching,
        "set_complete": bool(unique_candidates) and count == len(unique_candidates) and all(matching),
        "unique": count == 1 and bool(unique_candidates) and all(matching),
    }


def low_precision_pslq(value, t):
    with mp.workdps(100):
        v = mp.mpf(str(value))
        if not v: return t
        for deg in range(1, 7):
            rel = mp.pslq(mp.matrix([v**j for j in range(deg + 1)]), tol=mp.mpf("1e-13"), maxcoeff=10**6, maxsteps=1000)
            if rel and rel[-1]: return primitive(sum(int(c) * t**j for j, c in enumerate(rel)), t)
    return None


def main(cid, subdir="runs"):
    out = HERE / subdir / cid
    out.mkdir(parents=True, exist_ok=True)
    inp = HERE / "inputs" / f"{cid}.json"
    case = json.loads(inp.read_text())
    sys.addaudithook(protection)
    result = {
        "id": cid, "group": case["group"], "source_kind": case["source_kind"],
        "source_path": case["source_path"], "source_sha256": case["source_sha256"],
        "input_sha256": hashlib.sha256(inp.read_bytes()).hexdigest(),
        "primary_main_output_available": case["primary_main_output_available"],
        "official_answer_loaded": False, "status": "running", "stage": "setup",
        "stages": {}, "stage_timeouts": [], "candidates": [], "identities": [],
        "saved_candidate_count": len(case["candidates"]),
    }

    def checkpoint():
        result["seconds"] = time.monotonic() - START
        save(out / "result.json", result)

    def finish(status, detail=None):
        result["status"] = status
        if detail is not None: result["detail"] = detail
        checkpoint()
        print(json.dumps({k: result.get(k) for k in ("id", "status", "seconds", "stage", "variables", "equations")}), flush=True)

    @contextmanager
    def stage(name, cap=None):
        result["stage"] = name
        checkpoint()
        before = time.monotonic()
        left = END - before
        if left <= 0: raise Limit("global 60s deadline")
        try:
            with deadline(min(left, cap) if cap is not None else left):
                yield
        except Limit:
            result["stage_timeouts"].append(name)
            raise
        finally:
            result["stages"][name] = result["stages"].get(name, 0) + time.monotonic() - before
            checkpoint()

    try:
        dsl = case["dsl"]
        with stage("encode", 20):
            sy, t, fs, vs, nd = encode(dsl)
            polys = [sp.Poly(f, *vs, domain=sp.QQ) for f in fs]
            degs = [p.total_degree() for p in polys]
            terms = sum(len(p.terms()) for p in polys)
            result.update(variables=len(vs), equations=len(fs), max_degree=max(degs, default=0), total_terms=terms,
                          nondeg_factors=list(map(str, nd)), target_symbol=str(t))
            sysdata = {"variables": list(map(str, vs)), "F_saturated": list(map(str, fs)), "nondeg_factors": list(map(str, nd)), "target": str(t)}
            blob = stable_json(sysdata)
            result["system_sha256"] = hashlib.sha256(blob).hexdigest()
            result["system_bytes"] = len(blob)
            if len(blob) <= 256 * 1024: save(out / "system.json", sysdata)
        if len(vs) > 40 or len(fs) > 100 or terms > 20000 or max(degs, default=0) > 30:
            finish("system_too_large"); return
        with stage("bounds", 4):
            bound, bproof = target_bounds(dsl)
            result["bound_derivation"] = bproof
        if not case["candidates"]:
            finish("missing_saved_candidate"); return
        valid = []
        # The total numerical phase is capped at 12s. A local HP failure can use
        # a saved float proposal, but never bypasses exact algebraic proof.
        with stage("numeric_and_pslq", 12):
            bundle, ev = evaluator(dsl)
            for candidate in case["candidates"]:
                rec = dict(candidate)
                x = candidate["x"]
                guard, tags = ev.evaluate_guard(x)
                residual = ev.evaluate_float_residual(x)
                # Residual field names are read through the public dataclass.
                rr = list(residual.residual_vector)
                residual_max = max([abs(float(v)) for v in rr] + [0.0])
                rec.update(float_guard=bool(guard), float_hard=hard(ev, x), rechecked_residual=residual_max)
                if not guard or not rec["float_hard"] or not math.isfinite(residual_max) or residual_max > 1e-7:
                    rec["candidate_status"] = "original_numeric_validation_failed"
                    result["candidates"].append(rec)
                    continue
                try:
                    xx, value, info = polish(ev, x)
                    with mp.workdps(100):
                        hp_hard = hard(ev, xx, hp=True)
                        hp_guard, hp_tags = ev.evaluate_guard(xx)
                        rec.update(info, hp_value=mp.nstr(value, 100), hp_coordinates=[mp.nstr(v, 100) for v in xx], hp_hard=hp_hard, hp_guard=bool(hp_guard))
                        if not hp_hard or not hp_guard:
                            raise ValueError("polished point violates original conditions")
                        # A different value after Newton is not the stored output.
                        if abs(float(value) - candidate["value_float"]) > 1e-7 * max(1, abs(candidate["value_float"])):
                            raise ValueError("polish changed the saved answer")
                        p, deg = pslq(value, t)
                    rec["proposal_kind"] = "100_digit_polished_saved_endpoint"
                except Limit:
                    raise
                except Exception as e:
                    rec["hp_error"] = type(e).__name__ + ": " + str(e)[:200]
                    p = low_precision_pslq(candidate["value_float"], t)
                    rec["proposal_kind"] = "saved_float_pslq_tol_1e-13"
                if p is None:
                    rec["candidate_status"] = "pslq_failed"
                    result["candidates"].append(rec)
                    continue
                try:
                    interval = numeric_root(p, t, candidate["value_float"])
                except ValueError as e:
                    rec.update(candidate_status="candidate_root_ambiguous", P=str(p), error=str(e))
                    result["candidates"].append(rec)
                    continue
                rec.update(P=str(p), candidate_status="proposed", root_interval=[str(v) for v in interval])
                result["candidates"].append(rec)
                valid.append({"P_expr": p, "root_interval_exact": interval})
        result["proposed_candidate_count"] = len(valid)
        if len(valid) != len(case["candidates"]):
            # No cherry-picking successful members of an output set.
            finish("candidate_set_incomplete", "At least one saved candidate failed original validation or PSLQ; no subset counted."); return
        p = sp.Poly(1, t, domain=sp.QQ)
        for v in valid: p = sp.lcm(p, sp.Poly(v["P_expr"], t, domain=sp.QQ))
        p = p.sqf_part().monic().as_expr()
        reflected = sp.Poly(p * p.subs(t, -t), t, domain=sp.QQ).sqf_part().monic().as_expr()
        result["candidate_union_P"] = str(p)

        def certify(pr, q, kind):
            with stage("identity_" + kind):
                cofs = pr.coefficients(q)
                if cofs is None: return False
                cert = make_certificate(fs, pr.vs, nd, q, cofs)
                # Independent Fraction verification is a required success gate.
                verified = verify(cert)
                if not verified: raise AssertionError("independent identity verification failed")
                blob = stable_json(cert)
                record = {"kind": kind, "Q": str(q), "sha256": hashlib.sha256(blob).hexdigest(),
                          "bytes": len(blob), "N": cert["N"], "cofactor_terms": cert["cofactor_terms"],
                          "verified_fraction": True, "raw_saved": len(blob) <= 256 * 1024}
                if record["raw_saved"]: save(out / ("certificate-" + kind + ".json"), cert)
                result["identities"].append(record)
            with stage("roots_" + kind):
                roots = check_roots(q, t, bound, valid)
                record["root_check"] = roots
                result["last_root_check"] = roots
            if roots["set_complete"]:
                result["certificate_kind"] = kind
                finish("certified_saved_endpoint_set")
                return True
            return False

        pr = None
        try:
            with stage("groebner_grevlex", 15):
                pr = Prover(fs, vs, order="grevlex")
                result["zero_dimensional"] = zero_dim(pr)
            if result["zero_dimensional"] == "empty":
                finish("inconsistent_polynomial_system"); return
            if certify(pr, p, "P"): return
            if sp.expand(p - reflected) != 0 and certify(pr, reflected, "reflection"): return
            # A univariate polynomial already present in this basis is a valid
            # eliminant; using it avoids a redundant lex basis in easy cases.
            with stage("extract_grevlex_eliminant", 2):
                basis = [pr.ring.to_sympy(pr.ring._sdm_to_vector(g, 1)[0]) for g in pr.gb]
                univariate = [g for g in basis if g.free_symbols <= {t} and sp.degree(g, t) > 0]
            if univariate:
                q = primitive(min(univariate, key=lambda g: sp.degree(g, t)), t)
                if certify(pr, q, "E_grevlex"): return
        except Limit:
            result["grevlex_incomplete"] = True
        # No grevlex identity can prove the answer set: use lex elimination with
        # the same remaining total budget and a fixed 22s phase cap.
        try:
            with stage("groebner_lex", 22):
                order = [v for v in vs if v != t] + [t]
                lex = Prover(fs, order, order="lex")
                result["lex_zero_dimensional"] = zero_dim(lex)
                basis = [lex.ring.to_sympy(lex.ring._sdm_to_vector(g, 1)[0]) for g in lex.gb]
                univariate = [g for g in basis if g.free_symbols <= {t} and sp.degree(g, t) > 0]
                if not univariate:
                    finish("inconsistent_polynomial_system" if result["lex_zero_dimensional"] == "empty" else "no_univariate_eliminant"); return
                q = primitive(min(univariate, key=lambda g: sp.degree(g, t)), t)
            if certify(lex, q, "E_lex"): return
        except Limit:
            finish("timeout", "fixed stage or global budget exhausted"); return
        root = result.get("last_root_check", {})
        if root.get("allowed_root_count", 0) > len(valid):
            finish("multiple_roots_remain")
        else:
            finish("candidate_set_mismatch")
    except Unsupported as e:
        reason = str(e)
        # Angle-valued targets may be algebraic in degrees, so do not label all
        # such unsupported syntax as mathematically transcendental.
        category = "transcendental_encoding" if "pi outside" in reason or "circle area (pi)" in reason else "unsupported_dsl"
        finish(category, reason)
    except Limit as e:
        finish("timeout", str(e))
    except MemoryError:
        finish("memory_limit", "3 GiB address-space limit")
    except Exception as e:
        import traceback
        finish("implementation_error", type(e).__name__ + ": " + str(e)[:500])
        save(out / "traceback.json", {"traceback": traceback.format_exc()})


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else "runs")
