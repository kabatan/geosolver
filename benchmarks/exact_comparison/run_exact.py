"""Run one exact baseline on one benchmark case and filter its real solutions.

usage: run_exact.py CASE_ID MODE SOLVER TIMEOUT OUT.json
  MODE   fresh | inline
  SOLVER msolve | phc | singular
"""

from __future__ import annotations

import json
import os
import re
import resource
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import sympy as sp

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from algebraize import Unsupported, translate  # noqa: E402

CASES = HERE.parent / "cases.jsonl"
MEM_BYTES = 6 << 30


def load_case(cid):
    for line in CASES.open():
        c = json.loads(line)
        if c["id"] == cid:
            return c
    raise KeyError(cid)


def poly_str(e):
    """Integer-coefficient form; msolve does not parse rational coefficients."""
    e = sp.expand(e)
    gens = sorted(e.free_symbols, key=str)
    if gens:
        _, p = sp.Poly(e, *gens).clear_denoms()
        e = p.primitive()[1].as_expr()
    return str(e).replace("**", "^")


def build(sys_, rabinowitsch):
    eqs = []
    for e in sys_.eqs:
        e = sp.expand(e)
        p = sp.Poly(e, *sorted(e.free_symbols, key=str))
        e = p.monic().as_expr() if p.LC() != 0 else e
        if not any(sp.expand(e - f) == 0 or sp.expand(e + f) == 0 for f in eqs):
            eqs.append(e)
    used = sorted(set().union(*[e.free_symbols for e in eqs]) if eqs else set(), key=str)
    factors = {}
    if rabinowitsch:
        for d in sys_.nondeg:
            for f, _ in sp.factor_list(d)[1]:
                if f.free_symbols and f.free_symbols <= set(used):
                    f = sp.Poly(f, *sorted(f.free_symbols, key=str)).monic().as_expr()
                    factors[sp.srepr(f)] = f
        if factors:
            z = sp.Symbol("zz")
            prod = sp.Integer(1)
            for f in factors.values():
                prod *= f
            eqs.append(sp.expand(z * prod - 1))
            used.append(z)
    return eqs, used, list(factors.values())


def stats(eqs, used):
    degs = [sp.Poly(e, *used).total_degree() for e in eqs]
    bezout = 1
    for d in degs:
        bezout *= d
    return {
        "nvars": len(used),
        "neqs": len(eqs),
        "degrees": degs,
        "bezout": bezout,
        "terms": sum(len(sp.Poly(e, *used).terms()) for e in eqs),
    }


def limit_child():
    resource.setrlimit(resource.RLIMIT_AS, (MEM_BYTES, MEM_BYTES))
    os.sched_setaffinity(0, os.sched_getaffinity(0))


def run_cmd(cmd, timeout, cwd):
    t0 = time.monotonic()
    try:
        p = subprocess.run(
            cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout, preexec_fn=limit_child
        )
        return time.monotonic() - t0, p.returncode, p.stdout[-2000:] + p.stderr[-2000:]
    except subprocess.TimeoutExpired:
        return time.monotonic() - t0, "timeout", ""


# ---------------------------------------------------------------- msolve

FRAC = re.compile(r"(-?\d+)\s*(?:/\s*2\^(\d+))?")


def parse_msolve(text, nvars):
    text = text.strip().rstrip(":")
    if text.startswith("[-1]"):
        return "no_complex_solution", []
    if re.match(r"\[1,\s*\d+,\s*-1", text):
        return "positive_dimensional", []
    body = re.sub(r"\s+", "", text)

    def num(tok):
        m = re.fullmatch(r"(-?\d+)(?:/2\^(\d+))?", tok)
        if m:
            return sp.Rational(int(m.group(1)), 2 ** int(m.group(2) or 0))
        m = re.fullmatch(r"(-?\d+)/(\d+)", tok)
        if not m:
            raise ValueError(tok)
        return sp.Rational(int(m.group(1)), int(m.group(2)))

    boxes = re.findall(r"\[\[([^\[\]]+)\](?:,\[([^\[\]]+)\])*\]", body)
    # robust parse: collect all [a,b] intervals in order, group by nvars
    intervals = re.findall(r"\[([^\[\],]+),([^\[\],]+)\]", body)
    vals = [(num(a) + num(b)) / 2 for a, b in intervals]
    if len(vals) % nvars:
        raise ValueError("cannot group msolve intervals")
    sols = [vals[i : i + nvars] for i in range(0, len(vals), nvars)]
    return "ok", sols


def solve_msolve(eqs, used, timeout, work):
    names = [str(v) for v in used]
    ren = {v: sp.Symbol(f"x{i}") for i, v in enumerate(used)}  # msolve rejects "_"
    inp = work / "in.ms"
    inp.write_text(
        ",".join(f"x{i}" for i in range(len(used)))
        + "\n0\n"
        + ",\n".join(poly_str(e.xreplace(ren)) for e in eqs)
        + "\n"
    )
    out = work / "out.ms"
    elapsed, rc, log = run_cmd(
        ["msolve", "-t", "1", "-p", "256", "-f", str(inp), "-o", str(out)], timeout, work
    )
    if rc != 0:
        return elapsed, f"error:{rc}", [], log
    status, sols = parse_msolve(out.read_text(), len(names))
    return elapsed, status, [dict(zip(names, s)) for s in sols], ""


# ---------------------------------------------------------------- PHCpack


def solve_phc(eqs, used, timeout, work):
    names = [str(v) for v in used]
    if len(eqs) < len(used):
        return 0.0, "underdetermined", [], ""
    if len(eqs) > len(used):
        import random

        rng = random.Random(0)
        eqs = [sum(rng.randint(-9, 9) * e for e in eqs) for _ in range(len(used))]
    ren = {v: sp.Symbol(f"x{i}") for i, v in enumerate(used)}
    lines = [f"{len(eqs)}"]
    for e in eqs:
        lines.append(poly_str(e.xreplace(ren)).replace("^", "**") + ";")
    inp = work / "in.phc"
    inp.write_text("\n".join(lines) + "\n")
    out = work / "out.phc"
    elapsed, rc, log = run_cmd(["phc", "-b", str(inp), str(out)], timeout, work)
    if rc == "timeout":
        return elapsed, "timeout", [], ""
    if not out.exists():
        return elapsed, f"error:{rc}", [], log
    text = out.read_text(errors="replace")
    idx = text.rfind("THE SOLUTIONS")
    if idx < 0:
        return elapsed, f"error:no_solutions_section", [], text[-1500:]
    blocks = text[idx:].split("solution ")[1:]
    sols, complex_count = [], 0
    for b in blocks:
        vals = dict(re.findall(r"\s(x\d+)\s*:\s*(\S+)\s+\S+", b))
        ims = dict(re.findall(r"\s(x\d+)\s*:\s*\S+\s+(\S+)", b))
        if len(vals) != len(names):
            continue
        complex_count += 1
        scale = max(1.0, max(abs(float(vals[f"x{i}"])) for i in range(len(names))))
        if all(abs(float(ims[f"x{i}"])) < 1e-6 * scale for i in range(len(names))):
            sols.append({names[i]: sp.Float(vals[f"x{i}"], 30) for i in range(len(names))})
    return elapsed, f"ok:{complex_count}", sols, ""


# ---------------------------------------------------------------- Singular


def solve_singular(eqs, used, timeout, work, target=None):
    """Groebner basis (and elimination to the target for positive dimension)."""
    ren = {v: sp.Symbol(f"x{i}") for i, v in enumerate(used)}
    names = [f"x{i}" for i in range(len(used))]
    script = ["option(redSB);", f"ring r = 0, ({','.join(names)}), dp;"]
    script.append("ideal I = " + ",\n".join(poly_str(e.xreplace(ren)) for e in eqs) + ";")
    script.append("int t0 = rtimer; ideal G = std(I); int d = dim(G);")
    script.append('print("DIM"); print(d); print("VDIM"); print(vdim(G));')
    script.append("quit;")
    inp = work / "in.sing"
    inp.write_text("\n".join(script) + "\n")
    elapsed, rc, log = run_cmd(["Singular", "-q", str(inp)], timeout, work)
    if rc == "timeout":
        return elapsed, "timeout", [], ""
    m = re.search(r"DIM\s*\n\s*(-?\d+)\s*\nVDIM\s*\n\s*(-?\d+)", log)
    if not m:
        return elapsed, f"error:{rc}", [], log[-800:]
    return elapsed, f"dim={m.group(1)},vdim={m.group(2)}", [], ""


def solve_elim(eqs, used, timeout, work, target):
    """Singular: eliminate every unknown except the target t (positive dimension)."""
    ren = {v: sp.Symbol(f"x{i}") for i, v in enumerate(used)}
    names = [f"x{i}" for i in range(len(used))]
    t = str(ren[target])
    others = "*".join(n for n in names if n != t) or "1"
    script = [f"ring r = 0, ({','.join(names)}), dp;"]
    script.append("ideal I = " + ",\n".join(poly_str(e.xreplace(ren)) for e in eqs) + ";")
    script.append(f"ideal E = eliminate(I, {others});")
    script.append('print("ELIM"); print(size(E)); int i; for(i=1;i<=size(E);i++){print(E[i]);} print("END");')
    script.append("quit;")
    inp = work / "in.sing"
    inp.write_text("\n".join(script) + "\n")
    elapsed, rc, log = run_cmd(["Singular", "-q", str(inp)], timeout, work)
    if rc == "timeout":
        return elapsed, "timeout", [], ""
    m = re.search(r"ELIM\s*\n\s*(\d+)\s*\n(.*?)END", log, re.S)
    if not m:
        return elapsed, f"error:{rc}", [], log[-800:]
    polys = [p for p in re.split(r"\n(?=\S)", m.group(2).strip()) if p.strip()]
    tsym = sp.Symbol(t)
    roots = []
    for p in polys:
        e = sp.sympify(p.replace("^", "**").replace("\n", ""))
        if e.free_symbols <= {tsym} and e.free_symbols:
            for f, _ in sp.factor_list(e)[1]:
                for root in sp.Poly(f, tsym).real_roots():
                    roots.append(float(root.evalf(30)))
            break
    else:
        return elapsed, "no_univariate", [], ""
    return elapsed, f"univariate:{len(roots)}", sorted(set(roots)), ""


# ---------------------------------------------------------------- filtering


def verifier_for(case):
    from geosolver import GeometryProblem
    from geosolver.engine.standard.evaluation.ir_evaluator import build_ir_evaluator
    from geosolver.engine.standard.problem.load_problem_bundle import load_problem_bundle

    problem = GeometryProblem.model_validate(case["dsl"])
    bundle = load_problem_bundle(problem.engine_document())
    return bundle, build_ir_evaluator(bundle)


def filter_candidates(case, sys_, sols, deadline):
    from mpmath import mp

    from geosolver.engine.standard.evaluation.final_verifier import verify_final_candidate

    bundle, ev = verifier_for(case)
    dsl_names = {f"v_{n}": n for n in case["dsl"]["variables"]}
    seen, answers, verified = set(), [], 0
    for sol in sols:
        if time.monotonic() > deadline:
            return answers, verified, "filter_timeout"
        values = {}
        for k, v in sol.items():
            if k in dsl_names:
                values[dsl_names[k]] = v
        angle_names = []
        for x, (c, s_) in sys_.angle_vars.items():
            if str(c) in sol and str(s_) in sol:
                with mp.workdps(70):
                    theta = sp.Float(mp.nstr(mp.atan2(mp.mpf(str(sp.Float(sol[str(s_)], 70))),
                                                      mp.mpf(str(sp.Float(sol[str(c)], 70)))), 65), 65)
                values[dsl_names[str(x)]] = theta
                angle_names.append(dsl_names[str(x)])
        try:
            point = tuple(values[n] for n in bundle.var_names)
        except KeyError:
            continue  # a DSL variable is free in the relaxation
        key = tuple(round(float(x), 9) for x in point)
        if key in seen:
            continue
        seen.add(key)
        # an angle unknown is known modulo 2*pi; try the shifts the bounds may need
        two_pi = sp.Float(2 * sp.pi.evalf(70), 70)
        shifts = [{}] + [{n: two_pi} for n in angle_names] + [{n: -two_pi} for n in angle_names]
        r = None
        for shift in shifts:
            pt = tuple(values[n] + shift.get(n, 0) for n in bundle.var_names)
            try:
                with mp.workdps(80):
                    r = verify_final_candidate(
                        evaluator=ev, values=tuple(mp.mpf(str(sp.Float(x, 60))) for x in pt)
                    )
            except Exception:
                r = None
            if r is not None and r.verified:
                break
        if r is not None and r.verified and r.answer_hp is not None:
            verified += 1
            a = float(r.answer_hp)
            if all(abs(a - b) > 1e-9 * max(1, abs(a)) for b in answers):
                answers.append(a)
    return sorted(answers), verified, "ok"


def reference_values(case):
    ans = case["answer"]
    ans = ans if isinstance(ans, list) else [ans]
    sys.path.insert(0, str(HERE.parent))
    from research_runner import reference_expressions

    out = []
    for a in ans:
        for e in reference_expressions(str(a)):
            out.append(float(sp.sympify(e).evalf(30)))
    return sorted(out)


def same_set(xs, ys):
    return len(xs) == len(ys) and all(
        abs(a - b) <= 1e-7 * max(1, abs(b)) for a, b in zip(sorted(xs), sorted(ys))
    )


def main():
    cid, mode, solver, timeout, out_path = sys.argv[1:6]
    timeout = float(timeout)
    case = load_case(cid)
    rec = {"id": cid, "mode": mode, "solver": solver, "timeout": timeout,
           "dsl_vars": len(case["dsl"]["variables"])}
    t0 = time.monotonic()
    try:
        sys_, target = translate(case["dsl"], mode=mode, with_target=(solver == "elim"))
        eqs, used, nondeg = build(sys_, rabinowitsch=(solver != "phc"))
        if solver == "elim" and target not in used:
            raise Unsupported("target eliminated away")
    except Unsupported as e:
        rec.update(status="unsupported", reason=str(e)[:120])
        Path(out_path).write_text(json.dumps(rec))
        return
    rec["translate_seconds"] = time.monotonic() - t0
    rec.update(stats(eqs, used))
    rec["nondeg_factors"] = len(nondeg)
    free = [str(v) for v in sys_.dsl_vars if v not in used]
    rec["free_dsl_vars"] = free
    with tempfile.TemporaryDirectory() as td:
        work = Path(td)
        if solver == "elim":
            elapsed, status, sols, log = solve_elim(eqs, used, timeout, work, target)
            rec.update(solve_seconds=elapsed, solve_status=status, candidate_values=sols)
            ref = reference_values(case)
            rec["reference"] = ref
            rec["reference_among_candidates"] = bool(sols) and all(
                any(abs(a - b) <= 1e-7 * max(1, abs(b)) for a in sols) for b in ref)
            Path(out_path).write_text(json.dumps(rec, default=str))
            return
        fn = {"msolve": solve_msolve, "phc": solve_phc, "singular": solve_singular}[solver]
        elapsed, status, sols, log = fn(eqs, used, timeout, work)
    rec.update(solve_seconds=elapsed, solve_status=status, real_solutions=len(sols))
    if log:
        rec["log"] = log[-600:]
    if sols:
        t1 = time.monotonic()
        answers, verified, fstatus = filter_candidates(case, sys_, sols, t1 + 600)
        rec.update(filter_seconds=time.monotonic() - t1, filter_status=fstatus,
                   verified_configurations=verified, answers=answers)
        ref = reference_values(case)
        rec["reference"] = ref
        rec["answer_set_matches"] = same_set(answers, ref)
    Path(out_path).write_text(json.dumps(rec, default=str))


if __name__ == "__main__":
    main()
