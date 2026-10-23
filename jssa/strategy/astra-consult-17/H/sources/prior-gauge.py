"""Classify the free direction of a positive-dimensional case.

For each case: (a) add a gauge-fixing equation and recompute the dimension;
(b) eliminate onto a shape invariant w = expr (in DSL variables) and test whether
w is constant on the solution set (nonzero univariate elimination polynomial).
"""
import json, re, subprocess, sys
import sympy as sp
sys.path.insert(0, ".")
from certify import load, translate, build, poly_str  # noqa

CASES = {
    # id: (kind, gauge-fix equation in DSL vars or None, invariant expr, invariant meaning)
    "AIME-2009-I-05": ("rotation about C left unfixed", "v_ax", "(v_ax-v_bx)**2+(v_ay-v_by)**2", "AB^2"),
    "HMMT-2021-FEB-GEO-06": ("rotation about B left unfixed", "v_ax", "(v_ax-v_cx)**2+(v_ay-v_cy)**2", "AC^2"),
    "AIME-2013-I-03": ("scale left unfixed", "v_s-1", "v_e/v_s", "AE/AB"),
    "AIME-2015-II-11": ("auxiliary point V slides on line OV", "v_vx", "v_cx", "C_x (shape of ABC)"),
    "HMMT-2008-FEB-GEO-06": ("genuine: A moves on the 45-degree arc", None, "(v_Ax+3)**2+v_Ay**2", "AB^2"),
    "HMMT-2013-FEB-GEO-02": ("genuine: trapezoid height h is not determined", None, "v_h", "height h"),
    "HMMT-2013-FEB-GEO-08": ("genuine: angle g is not determined", None, None, "angle g (cos g)"),
    "HMMT-2022-FEB-GEO-01": ("genuine: U slides on AB", None, "v_u", "AU"),
    "AIME-2015-II-07": ("genuine: rectangle slides (target uses fixed points only)", None, "v_t", "AP/AB"),
}


def sing(eqs, used, extra_lines):
    ren = {v: sp.Symbol(f"x{i}") for i, v in enumerate(used)}
    names = [f"x{i}" for i in range(len(used))]
    sc = [f"ring r = 0, ({','.join(names)}), dp;",
          "ideal I = " + ",\n".join(poly_str(e.xreplace(ren)) for e in eqs) + ";"] + [l(ren, names) for l in extra_lines] + ["quit;"]
    p = subprocess.run(["Singular", "-q"], input="\n".join(sc), capture_output=True, text=True, timeout=600)
    return p.stdout


def main():
    out = {}
    for cid, (kind, fix, inv, invname) in CASES.items():
        case = load(cid)
        sys_, target = translate(case["dsl"], mode="fresh", with_target=True)
        eqs, used, nondeg = build(sys_, rabinowitsch=True)
        env = {str(v): v for v in sys_.variables}
        rec = {"kind": kind}
        o = sing(eqs, used, [lambda r, n: 'print("D0"); print(dim(std(I)));'])
        rec["dim"] = int(re.search(r"D0\s+(-?\d+)", o).group(1))
        if fix:
            f = sp.sympify(fix, locals=env)
            o = sing(eqs + [f], used, [lambda r, n: 'print("D1"); print(dim(std(I)));'])
            rec["gauge_fix"] = fix
            rec["dim_after_fix"] = int(re.search(r"D1\s+(-?\d+)", o).group(1))
        if inv is None and cid == "HMMT-2013-FEB-GEO-08":
            # angle g is encoded by (cos, sin) unknowns a*, c*: use the cosine unknown
            cs = [v for v in used if str(v).startswith(("a", "c")) and sys_.aux_kinds.get(v) not in ("dsl",)]
            inv = str(cs[0]); rec["invariant_unknown"] = inv
        w = sp.Symbol("w_inv")
        e = sp.sympify(inv, locals=env)
        num, den = sp.fraction(sp.together(e))
        eqs2 = eqs + [w * den - num]
        used2 = used + [w]
        o = sing(eqs2, used2, [lambda r, n: f'ideal E = eliminate(I, {"*".join(n[:-1])}); print("E"); print(E); print("END");'])
        body = o.split("E", 1)[1].split("END")[0].strip()
        rec["invariant"] = invname
        rec["invariant_elimination"] = body.replace("\n", " ")
        rec["invariant_finitely_many_values"] = not re.fullmatch(r"(_\[1\]=)?0", body)
        out[cid] = rec
        print(cid, rec)
    json.dump(out, open("out/gauge.json", "w"), indent=1, ensure_ascii=False)


main()

