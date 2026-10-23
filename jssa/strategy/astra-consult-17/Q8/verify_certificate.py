"""Replay certificates and check global root coverage with a Fraction Sturm kernel.

The root count is implemented independently of SymPy. Translation and exact
algebraic signs are shared with the generator (explicit trusted-code boundary).
"""
from fractions import Fraction as F
import sympy as s

from exact_onevar import (Compiler, choose_anchor, classify_root, digest,
                         exact_sign, root_from_wire)


def trim(p):
    p = list(p)
    while len(p) > 1 and not p[0]:
        p.pop(0)
    return p


def remainder(a, b):
    a, b = trim(a), trim(b)
    while any(a) and len(a) >= len(b):
        q = a[0] / b[0]
        for i, v in enumerate(b):
            a[i] -= q * v
        a = trim(a)
    return a


def value(p, x):
    out = F(0)
    for q in p:
        out = out * x + q
    return out


def sturm(p):
    p = trim([F(a) for a in p])
    d = [q * (len(p) - 1 - i) for i, q in enumerate(p[:-1])]
    seq = [p, trim(d)]
    while any(seq[-1]):
        rem = [-q for q in remainder(seq[-2], seq[-1])]
        if not any(rem):
            break
        seq.append(rem)
    return seq


def variation(seq, x):
    signs = []
    for p in seq:
        if x == "+inf":
            q = p[0]
        elif x == "-inf":
            q = p[0] * (-1) ** (len(p) - 1)
        else:
            q = value(p, F(x))
        if q:
            signs.append(1 if q > 0 else -1)
    return sum(a != b for a, b in zip(signs, signs[1:]))


def same_set(a, b):
    aa = [root_from_wire(v) for v in a]
    bb = [root_from_wire(v) for v in b]
    return (len(aa) == len(bb)
            and all(any(exact_sign(x - y) == 0 for y in bb) for x in aa)
            and all(any(exact_sign(x - y) == 0 for y in aa) for x in bb))


def verify(dsl, cert):
    if cert.get("status") != "complete":
        raise ValueError("not a complete certificate")
    if cert.get("input_sha256") != digest(dsl):
        raise ValueError("input hash mismatch")
    c = Compiler(dsl).run()
    p, anchor = choose_anchor(c)
    coeffs = cert["anchor"]["coefficients"]
    if coeffs != anchor["coefficients"]:
        raise ValueError("necessary polynomial mismatch")
    seq = sturm(coeffs)
    count = variation(seq, "-inf") - variation(seq, "+inf")
    if len(cert["roots"]) != count:
        raise ValueError("global real root count mismatch")
    prev_hi = None
    answer_set = []
    accepted = 0
    for i, rec in enumerate(cert["roots"]):
        if rec["index"] != i:
            raise ValueError("root ordering/index mismatch")
        lo, hi = map(F, rec["isolating_interval"])
        if lo > hi or (prev_hi is not None and lo <= prev_hi):
            raise ValueError("invalid/overlapping isolating intervals")
        prev_hi = hi
        if lo == hi:
            if value([F(a) for a in coeffs], lo) != 0:
                raise ValueError("singleton is not a root")
        else:
            if value([F(a) for a in coeffs], lo) == 0 or value([F(a) for a in coeffs], hi) == 0:
                raise ValueError("root at nonsingleton interval endpoint")
            if variation(seq, lo) - variation(seq, hi) != 1:
                raise ValueError("interval does not contain exactly one real root")
        root = root_from_wire(rec["root"])
        if (exact_sign(root - s.Rational(lo.numerator, lo.denominator)) < 0
                or exact_sign(s.Rational(hi.numerator, hi.denominator) - root) < 0
                or exact_sign(p.as_expr().subs(c.x, root)) != 0):
            raise ValueError("root identity/isolation mismatch")
        actual = classify_root(c, root)
        if actual["status"] not in ("accepted", "rejected") or actual["status"] != rec["status"]:
            raise ValueError("root feasibility status mismatch")
        if actual["status"] == "accepted":
            accepted += 1
            if not same_set([actual["target_wire"]], [rec["target_wire"]]):
                raise ValueError("root target mismatch")
            if not any(same_set([v], [actual["target_wire"]]) for v in answer_set):
                answer_set.append(actual["target_wire"])
    if not same_set(answer_set, cert["answer_set"]):
        raise ValueError("answer set differs from exactly feasible roots")
    return {"verified": True, "sturm_real_roots": count,
            "accepted_roots": accepted, "answer_count": len(answer_set)}
