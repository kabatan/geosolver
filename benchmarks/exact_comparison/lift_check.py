"""Check that a configuration found by GeoSolver satisfies the polynomial system.

The DSL variables are fixed to GeoSolver's verified values; every auxiliary
unknown is then computed in creation order (all real branches), and the
search succeeds if one branch makes every equation vanish. This shows the
relaxation does not lose the true configuration.
"""

from __future__ import annotations

import sympy as sp
from mpmath import mp


def _real_roots_1d(expr, v, dps):
    p = sp.Poly(expr, v)
    if p.degree() <= 0:
        return None  # equation does not determine v
    coeffs = [mp.mpf(str(sp.Float(c, dps))) if c.is_real else mp.mpc(complex(c)) for c in p.all_coeffs()]
    roots = mp.polyroots(coeffs, maxsteps=400, extraprec=4 * dps)
    out = []
    for r in roots:
        r = mp.mpc(r)
        if abs(r.imag) <= mp.mpf(10) ** (-dps // 3) * max(1, abs(r)):
            out.append(sp.Float(mp.nstr(r.real, dps), dps))
    return out


def lift(sys_, eqs, dsl_values, dps=60, tol_exp=25):
    """Return (ok, worst_residual)."""
    mp.dps = dps
    tol = sp.Float(10) ** (-tol_exp)
    assign = {v: sp.Float(dsl_values[v], dps) for v in sys_.dsl_vars if v in dsl_values}
    for x, (c, s_) in sys_.angle_vars.items():
        if x in dsl_values:
            assign[c] = sp.Float(mp.cos(mp.mpf(str(sp.Float(dsl_values[x], dps)))), dps)
            assign[s_] = sp.Float(mp.sin(mp.mpf(str(sp.Float(dsl_values[x], dps)))), dps)
            assign.pop(x, None)
    blocks = [vars_ for kind, vars_ in sys_.defs if kind != "anglevar"]
    eqs = [sp.expand(e) for e in eqs]

    def residual_ok(a):
        for e in eqs:
            if e.free_symbols <= set(a):
                val = e.xreplace(a)
                scale = 1 + sum(abs(t.xreplace(a)) for t in sp.Add.make_args(e))
                if abs(val) > tol * scale:
                    return False
        return True

    best = [None]

    def dfs(i, a):
        if not residual_ok(a):
            return False
        if i == len(blocks):
            return all(e.free_symbols <= set(a) for e in eqs)
        vars_ = blocks[i]
        rel = [e for e in eqs if set(vars_) & e.free_symbols and
               e.free_symbols <= set(a) | set(vars_)]
        if len(vars_) == 1:
            v = vars_[0]
            cands = None
            for e in rel:
                cands = _real_roots_1d(e.xreplace(a), v, dps)
                if cands is not None:
                    break
            for c in cands or []:
                if dfs(i + 1, {**a, v: c}):
                    return True
            return False
        if len(rel) < 2:
            return False
        e1, e2 = [e.xreplace(a) for e in rel[:2]]
        for x, y in (vars_, vars_[::-1]):
            for f1, f2 in ((e1, e2), (e2, e1)):
                if y not in f1.free_symbols:
                    continue
                res = sp.expand(sp.resultant(f1, f2, y))
                xs = _real_roots_1d(res, x, dps) if x in res.free_symbols else None
                if xs is None:
                    continue
                for cx in xs:
                    for cy in _real_roots_1d(sp.expand(f1.xreplace({x: cx})), y, dps) or []:
                        if dfs(i + 1, {**a, x: cx, y: cy}):
                            return True
                return False
        return False

    return dfs(0, assign)
