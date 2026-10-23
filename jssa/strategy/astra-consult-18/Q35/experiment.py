"""Small locked Q35 experiments. One case/command, no optimizer or full solver.

The original frozen algebraizer outputs are inputs. Constant-coefficient linear
substitutions preserve their complex varieties and the retained target exactly.
Semantic component removals are explicit case-specific interventions.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
from pathlib import Path
import resource
import subprocess
import sys
import time
from datetime import datetime, timezone

sys.dont_write_bytecode = True
for name in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
    os.environ[name] = "1"
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
L = ROOT / "jssa/strategy/astra-consult-17/L"
CERT = ROOT / "jssa/difficulty/certify-all"
FROZEN = "60db4b679b04167175c51c479c87c22fa663fda0"
LIMIT_BYTES = 4_500_000


def check_lock():
    lock = json.loads((HERE / "prediction.lock.json").read_text())
    for path, digest in lock["files"].items():
        assert hashlib.sha256((ROOT / path).read_bytes()).hexdigest() == digest, path
    assert not subprocess.check_output(["git", "diff", FROZEN, "--", "src"], cwd=ROOT)
    return lock


LOCK = check_lock()
resource.setrlimit(resource.RLIMIT_AS, (2 * 1024**3, 2 * 1024**3))
resource.setrlimit(resource.RLIMIT_FSIZE, (LIMIT_BYTES, LIMIT_BYTES))
resource.setrlimit(resource.RLIMIT_CPU, (115, 120))
sys.path.insert(0, str(L / "vendor"))
sys.path.insert(0, str(L))
sys.path.insert(0, str(ROOT / "src"))
import sympy as sp
from certificate import Prover, Limit, deadline, sparse
from verify_certificate import verify


def save(name, value):
    data = json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False).encode() + b"\n"
    if len(data) >= LIMIT_BYTES:
        raise Limit("Q35 file cap")
    (HERE / name).parent.mkdir(parents=True, exist_ok=True)
    (HERE / name).write_bytes(data)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_case(cid):
    row = next(r for r in csv.DictReader((CERT / "per-case.csv").open()) if r["id"] == cid)
    result_path = CERT / row["result_path"]
    system_path = result_path.parent / "system.json"
    manifest = json.loads((HERE / "source-manifest.json").read_text())
    for p in (result_path, system_path):
        assert digest(p) == manifest[str(p.relative_to(ROOT))]["sha256"]
    data = json.loads(system_path.read_text())
    vs = list(map(sp.Symbol, data["variables"]))
    local = {str(v): v for v in vs}
    return [sp.sympify(f, locals=local) for f in data["F_saturated"]], vs, sp.Symbol(data["target"]), row, data


def reduce_linear(fs, vs, target):
    """Use only f=a*v+b, a in QQ\{0}; do not divide by any variable expression.

    Each recorded pivot is a retained definition, so substitutions are invertible
    on the zero set. No choice of a sign or component occurs in this routine.
    """
    fs = list(fs)
    vs = list(vs)
    steps = []
    while True:
        choices = []
        for i, f in enumerate(fs):
            for v in vs:
                if v == target or v not in f.free_symbols:
                    continue
                p = sp.Poly(f, v)
                if p.degree() == 1 and p.LC().is_Rational and p.LC() != 0:
                    value = sp.expand(-p.TC() / p.LC())
                    choices.append((int(sp.count_ops(value)), len(str(value)), i, str(v), v, value))
        if not choices:
            break
        _, _, i, _, v, value = min(choices)
        pivot = fs[i]
        assert sp.expand(pivot.subs(v, value)) == 0
        before = list(fs)
        fs = [sp.expand(f.subs(v, value)) for j, f in enumerate(fs) if i != j]
        fs = list(dict.fromkeys(f for f in fs if f != 0))
        steps.append({"variable": str(v), "value": str(value), "pivot": str(pivot),
                      "pivot_index": i, "before_equations": list(map(str, before)), "after_equations": list(map(str, fs))})
        vs.remove(v)
    return fs, vs, steps


def direct_certificate(fs, vs, q, cofs):
    # Treat existing saturation variables as ordinary variables; no implicit
    # assumptions about a final generator or a distinguished variable name.
    return {"variables": list(map(str, vs)), "N": 0, "s": sparse(sp.Integer(1), vs),
            "Q": sparse(q, vs), "F": [sparse(f, vs) for f in fs],
            "C": [sparse(c, vs) for c in cofs], "Q_expression": str(q)}


def arm(cid, label, fs, vs, target, cap, simplify):
    started = time.monotonic()
    result = {"label": label, "input_variables": list(map(str, vs)), "input_equations": list(map(str, fs)),
              "cap_seconds": cap, "linear_substitutions": [], "basis_complete": False, "certificate_verified": False}
    try:
        if simplify:
            before = time.monotonic()
            with deadline(5):
                fs, vs, steps = reduce_linear(fs, vs, target)
            result.update(linear_substitutions=steps, preprocessing_seconds=time.monotonic() - before)
        else:
            result["preprocessing_seconds"] = 0.0
        vs = [v for v in vs if v != target] + [target]
        result.update(output_variables=list(map(str, vs)), output_equations=list(map(str, fs)))
        before = time.monotonic()
        try:
            with deadline(cap):
                prover = Prover(fs, vs, order="lex")
            result.update(basis_complete=True, basis_seconds=time.monotonic() - before)
        except Limit:
            result.update(status="basis_timeout", basis_seconds=time.monotonic() - before)
            return result
        with deadline(5):
            basis = [prover.ring.to_sympy(prover.ring._sdm_to_vector(g, 1)[0]) for g in prover.gb]
            univariate = [g for g in basis if g.free_symbols <= {target} and sp.degree(g, target) > 0]
            result.update(status="univariate" if univariate else "no_univariate", basis_length=len(basis),
                          basis_sha256=hashlib.sha256(json.dumps(list(map(str, basis))).encode()).hexdigest(),
                          univariate=list(map(str, univariate)))
        if univariate:
            with deadline(5):
                q = min(univariate, key=lambda p: sp.degree(p, target))
                cofs = prover.coefficients(q)
                assert cofs is not None
                certificate = direct_certificate(fs, vs, q, cofs)
                assert verify(certificate)
                result["certificate_verified"] = True
                result["eliminant_monic"] = str(sp.Poly(q, target, domain=sp.QQ).monic().as_expr())
                result["eliminant_sqf_monic"] = str(sp.Poly(q, target, domain=sp.QQ).sqf_part().monic().as_expr())
                result["eliminant_factored"] = str(sp.factor(q))
                name = f"certificates/{cid}-{label}.json"
                blob = json.dumps(certificate, ensure_ascii=False).encode()
                if len(blob) < 1_000_000:
                    save(name, certificate)
                    result["certificate_path"] = name
                result["certificate_bytes_compact"] = len(blob)
    except Limit as e:
        result["late_limit"] = str(e)
        result.setdefault("status", "preprocess_or_certificate_timeout")
    except Exception as e:
        result["error"] = type(e).__name__ + ": " + str(e)
        result.setdefault("status", "error")
    finally:
        result["total_seconds"] = time.monotonic() - started
    return result


def paired(cid):
    expected = {r["id"] for r in json.loads((HERE / "summary.json").read_text())["optional_paired_subset_cost_rule"]}
    assert cid in expected
    fs, vs, t, row, data = load_case(cid)
    result = {"id": cid, "experiment": "paired", "lock_created_utc": LOCK["created_utc"],
              "created_utc": datetime.now(timezone.utc).isoformat(), "sympy": sp.__version__, "arms": []}
    for label, simplify, cap in (("original", False, 30), ("linear", True, 8)):
        result["arms"].append(arm(cid, label, fs, vs, t, cap, simplify))
        save(f"paired/{cid}.json", result)
        rr = result["arms"][-1]
        print(json.dumps({"id": cid, "arm": label, **{k: rr.get(k) for k in ("status", "basis_seconds", "preprocessing_seconds", "certificate_verified")}}, ensure_ascii=False), flush=True)


def components(cid):
    fs, vs, t, row, data = load_case(cid)
    sy = {str(v): v for v in vs}
    s = lambda name: sy[name]
    z = sp.Symbol("q35_z")
    if cid == "AIME-2009-I-12":
        Lf = 35*s("v_ix") + 12*s("v_iy") - 420
        extra = [Lf*z - 1]
        expected = (3*t-8)*(3*t+2)*(1369*t-288)*(1369*t-2450)
        witness = {s("v_ix"): -sp.Rational(576,1369), s("v_iy"): -sp.Rational(42875,4107),
                   s("s1"): sp.Rational(210,37), s("s2"): sp.Rational(210,37),
                   s("s3"): sp.Rational(1801,111), s("s4"): sp.Rational(5044,111), t: sp.Rational(8,3)}
        witness[z] = 1/Lf.subs(witness)
        # A forbidden real component on line AB with target varying, proving
        # the original target elimination ideal is zero without relying on time.
        w = sp.Symbol("w")
        bad = {s("v_iy"): w, s("v_ix"): (420-12*w)/35,
               s("s1"): sp.Rational(210,37), s("s2"): sp.Rational(210,37),
               s("s4"): 37*(35-w)/35, t: 2-2*w/35}
        bad[s("s3")] = 37*bad[t] - 37 - bad[s("s4")]
        side_checks = {"ix_negative": bool(witness[s("v_ix")] < 0), "iy_negative": bool(witness[s("v_iy")] < 0),
                       "lengths_positive": all(bool(witness[s(k)] > 0) for k in ("s1", "s2", "s3", "s4")),
                       "target_above_2": bool(witness[t] > 2)}
        rationale = "ix<0, iy<0 imply 35ix+12iy-420<0; strict triangle inequality gives target>2"
    elif cid == "HMMT-2006-FEB-GEO-01":
        extra = [s("p2"), s("p3")]
        expected = (t-20)**2-2
        witness = {s("s1"): sp.sqrt(2), s("p2"): 0, s("p3"): 0, s("s4"): 0,
                   s("v_g"): 2, s("v_h"): 4+sp.sqrt(2), t: 20+sp.sqrt(2), s("zz"): 1/sp.sqrt(2)}
        w = sp.Symbol("w")
        bad = {s("s1"): sp.sqrt(2), s("p2"): w, s("p3"): sp.I*w, s("s4"): 0,
               s("v_h"): sp.sqrt(2)*w + 4+sp.sqrt(2), s("v_g"): 2-(1+sp.I)*w,
               t: 20+sp.sqrt(2)+(sp.sqrt(2)-1-sp.I)*w, s("zz"): 1/sp.sqrt(2)}
        side_checks = {"g_positive": True, "h_positive": True, "sqrt2_positive": True}
        rationale = "Over R, p2^2+p3^2=s4^2 and s4=0 imply p2=p3=0; s1 represents the positive sqrt(2)"
    elif cid == "JMO-2013-PRE-08":
        extra = [s("v_r")*z-1]
        expected = t**2-144
        r = sp.Rational(3600,119)
        witness = {s("v_r"): r, s("v_ox"): sp.Rational(2160,119), s("v_oy"): -sp.Rational(1200,119),
                   s("v_d"): 12, s("s1"): r-5, s("s2"): r-6, s("s3"): r-20, s("s4"): r-12, s("s5"): 12, t: 12, z: 1/r}
        w = sp.Symbol("w")
        bad = {s("v_r"): 0, s("v_ox"): 0, s("v_oy"): 0, s("v_d"): w,
               s("s1"): -5, s("s2"): -6, s("s3"): -20, s("s4"): -w, s("s5"): w, t: w}
        side_checks = {"radius_positive": bool(r > 0), "d_positive": True,
                       "lengths_positive": all(bool(witness[s(k)] > 0) for k in ("s1", "s2", "s3", "s4", "s5"))}
        rationale = "r>0 is explicit in original DSL, and target=Distance(D,X)=d>0"
    else:
        raise ValueError(cid)
    assert all(sp.simplify(f.subs(witness)) == 0 for f in fs + extra)
    assert all(sp.simplify(f.subs(bad)) == 0 for f in fs)
    assert sp.diff(bad[t], w) != 0
    assert all(side_checks.values())
    result = {"id": cid, "experiment": "components", "created_utc": datetime.now(timezone.utc).isoformat(),
              "lock_created_utc": LOCK["created_utc"], "rationale": rationale,
              "additional_equations": list(map(str, extra)), "predicted_eliminant_sqf": str(sp.Poly(expected,t).sqf_part().monic().as_expr()),
              "allowed_witness": {str(k): str(v) for k,v in witness.items()}, "witness_original_and_added_residuals_zero": True,
              "witness_side_checks": side_checks, "forbidden_family": {str(k): str(v) for k,v in bad.items()},
              "forbidden_family_residuals_zero": True, "forbidden_family_target_nonconstant": True, "arms": []}
    for label, ff in (("before", fs), ("after", fs+extra)):
        vv = vs + ([z] if label == "after" and z in set().union(*(f.free_symbols for f in extra)) else [])
        rr = arm(cid, label, ff, vv, t, 12, True)
        if label == "after" and rr.get("eliminant_sqf_monic"):
            rr["matches_predicted_eliminant"] = sp.expand(sp.sympify(rr["eliminant_sqf_monic"]) - sp.Poly(expected,t).sqf_part().monic().as_expr()) == 0
        result["arms"].append(rr)
        save(f"components/{cid}.json", result)
        print(json.dumps({"id": cid, "arm": label, **{k: rr.get(k) for k in ("status", "basis_seconds", "eliminant_factored", "certificate_verified", "matches_predicted_eliminant")}}, ensure_ascii=False), flush=True)


def seed_candidates():
    rows = [r for r in csv.DictReader((HERE / "case-matrix.csv").open()) if r["dimension_group"] in ("G", "I")]
    out = []
    sources = {}
    for row in rows:
        cid = row["id"]
        p = ROOT / "jssa/difficulty/minima/raw-323-seed1" / (cid+".json")
        d = json.loads(p.read_text())
        sources[str(p.relative_to(ROOT))] = digest(p)
        values = []
        for r in sorted(d.get("records", []), key=lambda x: x["k"]):
            a, res = r.get("ans"), r.get("res", math.inf)
            if a is None or not math.isfinite(a) or not math.isfinite(res) or res > 1e-8:
                continue
            if not any(abs(a-v) <= 1e-7*max(1.0,abs(a),abs(v)) for v in values):
                values.append(a)
        oldp = CERT / "inputs" / (cid+".json")
        sources[str(oldp.relative_to(ROOT))] = digest(oldp)
        old = [c["value_float"] for c in json.loads(oldp.read_text())["candidates"]]
        same = len(old) == len(values) and all(any(abs(a-b) <= 1e-7*max(1.0,abs(a),abs(b)) for b in values) for a in old)
        out.append({"id": cid, "group": row["dimension_group"], "certified_seed0": row["certified"] == "True",
                    "n0": len(old), "n1": len(values), "same_numeric_candidate_set": same,
                    "seed1_values": values, "seed0_values": old})
    selected = [r for r in out if r["certified_seed0"]]
    assert len(selected) == 7
    result = {"created_utc": datetime.now(timezone.utc).isoformat(), "P4_n": len(selected),
              "P4_same_nonempty": sum(r["same_numeric_candidate_set"] and r["n1"] > 0 for r in selected),
              "P4_pass": all(r["same_numeric_candidate_set"] and r["n1"] > 0 for r in selected),
              "cases": out, "source_sha256": sources}
    save("seed-candidates.json", result)
    print(json.dumps({k:v for k,v in result.items() if k not in ("cases","source_sha256")}), flush=True)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("mode", choices=["paired", "components", "seed"])
    p.add_argument("id", nargs="?")
    a = p.parse_args()
    if a.mode == "paired": paired(a.id)
    elif a.mode == "components": components(a.id)
    else: seed_candidates()
