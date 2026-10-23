"""Certify P(tau)=0 on positive-dimensional cases by ideal membership (Singular).

usage: certify.py CASE_ID P_COEFFS(comma, highest first) OUTDIR [TIMEOUT]
Writes OUTDIR/CASE_ID/{system.txt, singular.in, singular.out, certificate.txt, result.json}.
"""
import json, re, subprocess, sys, time
from pathlib import Path
import sympy as sp
sys.setrecursionlimit(1000000)
import threading
threading.stack_size(512 * 1024 * 1024)

FOS = Path(__file__).resolve().parent.parent / "fos" / "benchmarks"
sys.path.insert(0, str(FOS / "exact_comparison"))
from algebraize import translate  # noqa: E402
from run_exact import build, poly_str  # noqa: E402


TERM = re.compile(r"([+-]?)([^+-]+)")


def parse_sing(text):
    """Parse an expanded Singular polynomial without eval (huge cofactors overflow the compiler)."""
    text = text.replace("\n", "").replace(" ", "")
    if text in ("", "0"):
        return sp.Integer(0)
    terms = []
    for sign, body in TERM.findall(text):
        coef = sp.Integer(-1 if sign == "-" else 1)
        mono = sp.Integer(1)
        for f in body.split("*"):
            if f[0].isdigit():
                coef *= sp.Rational(f)
            else:
                b, _, e = f.partition("^")
                mono *= sp.Symbol(b) ** int(e or 1)
        terms.append(coef * mono)
    return sp.Add(*terms)


def intform(e):
    return sp.sympify(poly_str(e).replace("^", "**"))


def load(cid):
    for line in (FOS / "cases.jsonl").open():
        c = json.loads(line)
        if c["id"] == cid:
            return c
    raise KeyError(cid)


def main():
    cid, pc, outdir = sys.argv[1:4]
    timeout = float(sys.argv[4]) if len(sys.argv) > 4 else 600
    out = Path(outdir) / cid
    out.mkdir(parents=True, exist_ok=True)
    case = load(cid)
    sys_, target = translate(case["dsl"], mode="fresh", with_target=True)
    extra = sys.argv[5] if len(sys.argv) > 5 else ""
    if extra:  # extra nondegeneracy condition, written in the DSL unknowns (v_name)
        sys_.nondeg.append(sp.sympify(extra, locals={str(v): v for v in sys_.variables}))
    eqs, used, nondeg = build(sys_, rabinowitsch=True)
    zz = sp.Symbol("zz")
    ren = {v: sp.Symbol(f"x{i}") for i, v in enumerate(used)}
    names = [f"x{i}" for i in range(len(used))]
    tname = str(ren[target])
    coeffs = [sp.Rational(c) for c in pc.split(",")]
    tt = sp.Symbol(tname)
    P = sum(c * tt ** (len(coeffs) - 1 - i) for i, c in enumerate(coeffs))
    s_poly = sp.Integer(1)
    for f in nondeg:
        s_poly *= f
    with (out / "system.txt").open("w") as fh:
        fh.write(f"# {cid}: polynomial encoding (fresh mode), unknowns renamed x0..\n")
        for v in used:
            fh.write(f"{ren[v]} = {v}  ({sys_.aux_kinds.get(v, 'rabinowitsch')})\n")
        fh.write(f"target unknown t = {tname}\n")
        fh.write(f"nondegeneracy s = {sp.factor(s_poly.xreplace(ren))}\n")
        for i, e in enumerate(eqs, 1):
            fh.write(f"F{i} = {intform(e.xreplace(ren))}\n")
        fh.write(f"P(t) = {P}\n")
    others = "*".join(n for n in names if n != tname)
    script = ["option(redSB);", "LIB \"primdec.lib\";",
              f"ring r = 0, ({','.join(names)}), dp;",
              "ideal I = " + ",\n".join(poly_str(e.xreplace(ren)) for e in eqs) + ";",
              "int t0 = rtimer; ideal G = std(I);",
              'print("DIM"); print(dim(G)); print("INDEP"); print(indepSet(G));',
              f"poly P = {poly_str(P)};",
              "poly red = reduce(P, G);",
              'print("MEMBER"); print(red == 0);',
              f"ideal E = eliminate(I, {others});",
              'print("ELIM"); print(E); print("ENDELIM");',
              "poly Q; if (red == 0) { Q = P; } else { Q = E[1]; }",
              'if (Q == 0) { print("COFACTORS"); print("@END"); quit; }',
              "matrix C = lift(I, Q);",
              'print("CHECK"); poly chk = Q; int i; for (i = 1; i <= ncols(I); i++) { chk = chk - C[i,1]*I[i]; } print(chk == 0);',
              'print("COFACTORS"); for (i = 1; i <= ncols(I); i++) { print("@C"); print(C[i,1]); } print("@END");',
              'print("TIME"); print(rtimer - t0);', "quit;"]
    (out / "singular.in").write_text("\n".join(script) + "\n")
    t0 = time.monotonic()
    try:
        p = subprocess.run(["Singular", "-q", "--ticks-per-sec=1000", str(out / "singular.in")],
                           capture_output=True, text=True, timeout=timeout)
        log = p.stdout + p.stderr
        status = "ok"
    except subprocess.TimeoutExpired:
        log, status = "", "timeout"
    elapsed = time.monotonic() - t0
    (out / "singular.out").write_text(log)
    res = {"id": cid, "P": str(P), "vars": len(used), "eqs": len(eqs), "nondeg_factors": len(nondeg),
           "status": status, "seconds": elapsed}
    if status != "ok" or "COFACTORS" not in log:
        res["status"] = status if status != "ok" else "error"
        (out / "result.json").write_text(json.dumps(res, indent=1))
        print(json.dumps(res)); return
    grab = lambda a, b: log.split(a, 1)[1].split(b, 1)[0].strip()
    res["dim"] = int(grab("DIM", "INDEP"))
    indep = [int(x) for x in re.findall(r"-?\d+", grab("INDEP", "MEMBER"))]
    res["independent_vars"] = [str(used[i]) for i, f in enumerate(indep) if f and i < len(used)]
    res["member"] = grab("MEMBER", "ELIM") == "1"
    elim = [e for e in re.split(r"\n", grab("ELIM", "ENDELIM")) if e.strip()]
    E = sp.sympify(elim[0].split("=", 1)[-1].replace("^", "**")) if elim else None
    res["elim_poly"] = str(sp.factor(E)) if E is not None else None
    res["extra_nondeg"] = extra or None
    if E is None or E == 0:
        res["status"] = "no_univariate"
        (out / "result.json").write_text(json.dumps(res, indent=1, ensure_ascii=False))
        print(json.dumps(res, ensure_ascii=False)); return
    tt_roots = sp.Poly(E, tt).real_roots() if E.free_symbols == {tt} else []
    res["elim_real_roots"] = [str(r) for r in tt_roots]
    res["lift_check_singular"] = grab("CHECK", "COFACTORS") == "1"
    cof = [parse_sing(c.strip()) for c in
           grab("COFACTORS", "@END").split("@C")[1:]]
    Q = P if res["member"] else E
    # zz * s - 1 is the last equation; clear zz -> 1/s
    has_z = zz in used
    z = sp.Symbol(names[-1]) if has_z else sp.Symbol("unused_z")
    s_ren = sp.expand(s_poly.xreplace(ren))
    if not has_z:
        s_ren = sp.Integer(1)
    gens = [sp.Symbol(n) for n in names if n != str(z)]
    PZ = [sp.Poly(c, z, *gens) for c in cof]
    N = max([pz.degree(z) for pz in PZ] + [0])
    S = sp.Poly(s_ren, *gens)
    Spow = [S ** k for k in range(N + 1)]
    newpolys = []
    for pz in (PZ[:-1] if has_z else PZ):
        acc = sp.Poly(0, *gens)
        for (k, *mono), coef in pz.terms():
            acc += sp.Poly(sp.Mul(coef, *[g ** e for g, e in zip(gens, mono)]), *gens) * Spow[N - k]
        newpolys.append(acc)
    F = [sp.Poly(intform(e.xreplace(ren)), *gens) for e in (eqs[:-1] if has_z else eqs)]
    resid = Spow[N] * sp.Poly(Q, *gens) - sum((c * f for c, f in zip(newpolys, F)), sp.Poly(0, *gens))
    newc = [c.as_expr() for c in newpolys]
    res["N"] = N
    res["identity_check_sympy"] = resid.is_zero
    res["cofactor_terms"] = [len(c.terms()) if not c.is_zero else 0 for c in newpolys]
    m = re.search(r"TIME\s*\n\s*(\d+)", log)
    res["singular_seconds"] = int(m.group(1)) / 1000 if m else None
    with (out / "certificate.txt").open("w") as fh:
        fh.write(f"# {cid}: s^{N} * Q = sum_i C_i * F_i  (F_i in system.txt, s = nondegeneracy product)\n")
        fh.write(f"# Q = {'P(t)' if res['member'] else 'E(t) (elimination polynomial; P is a factor)'} = {sp.factor(Q)}\n")
        fh.write(f"# verified by sympy expansion: {res['identity_check_sympy']}\n")
        for i, c in enumerate(newc, 1):
            fh.write(f"C{i} = {c}\n")
    (out / "result.json").write_text(json.dumps(res, indent=1, ensure_ascii=False))
    print(json.dumps(res, ensure_ascii=False))


if __name__ == "__main__":
    th = threading.Thread(target=main); th.start(); th.join()

