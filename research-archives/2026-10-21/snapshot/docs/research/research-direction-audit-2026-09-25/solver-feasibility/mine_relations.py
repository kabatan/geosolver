"""Bounded CPU feasibility probe, not an LLM learning or transfer experiment.

Enumerate ALL binomial relations between degree-1/2 monomials of ALL pairwise
squared distances of H01's six named points. Coefficients p/q are bounded by 16.
No expected theorem, relation dictionary, or target equality is used in mining.
Only geometry primitives are imported from the solver, never solver.solve.
"""

from __future__ import annotations

import hashlib
import itertools
import json
from pathlib import Path
import random
import time

import sympy as s

from geosolver.geometry import FootOfPerpendicular, Line, Midpoint, Orthocenter, Point


OUT = Path(__file__).resolve().parent
NAMES = ("A", "B", "C", "M", "H", "P")
PAIRS = list(itertools.combinations(NAMES, 2))
FEATURES = ["".join(pair) + "^2" for pair in PAIRS]
MONOMIALS = {
    degree: list(itertools.combinations_with_replacement(range(len(PAIRS)), degree))
    for degree in (1, 2)
}


def squared_distances(points):
    return [
        s.cancel((points[a].x - points[b].x) ** 2 + (points[a].y - points[b].y) ** 2)
        for a, b in PAIRS
    ]


def construct(u, v, b=1):
    """Coordinate normalization, followed by the original construction definitions."""
    u, v, b = map(s.sympify, (u, v, b))
    points = {"A": Point(u, v), "B": Point(-b, s.S.Zero), "C": Point(b, s.S.Zero)}
    points["M"] = Midpoint(points["B"], points["C"])
    points["H"] = Orthocenter(points["A"], points["B"], points["C"])
    points["P"] = FootOfPerpendicular(points["H"], Line(points["A"], points["M"]))
    for point in points.values():
        point.x, point.y = s.cancel(point.x), s.cancel(point.y)
    return points


def sample(seed, count):
    """Freeze the original candidate pool; canonical filtering happens afterwards."""
    rng = random.Random(seed)
    accepted = []
    seen_shapes = set()
    while len(accepted) < count:
        # Vary shape AND scale. Acuteness and scaleneness checked below.
        b = s.Rational(rng.randint(8, 23), 10)
        u = b * s.Rational(rng.choice([i for i in range(-8, 9) if i]), 10)
        v = b * s.Rational(rng.randint(11, 26), 10)
        shape = (u / b, v / b)
        if shape in seen_shapes:
            continue
        points = construct(u, v, b)
        tri = [points[x] for x in "ABC"]
        dists = [s.cancel((p.x-q.x)**2+(p.y-q.y)**2) for p, q in itertools.combinations(tri, 2)]
        if len(set(dists)) != 3 or any(2 * d >= sum(dists) for d in dists):
            continue
        seen_shapes.add(shape)
        accepted.append({"params": list(map(str, (u, v, b))), "distances": squared_distances(points)})
    return accepted


def canonical_shape(row):
    """Identify mirror images / B,C exchanges as the same triangle shape."""
    u, v, b = map(s.Rational, row["params"])
    return abs(u / b), v / b


def distinct_shapes(rows, excluded=()):
    seen = set(excluded)
    accepted = []
    for row in rows:
        key = canonical_shape(row)
        if key not in seen:
            accepted.append(row)
            seen.add(key)
    return accepted


def values(distances, monomials):
    return [s.prod(distances[k] for k in mono) for mono in monomials]


def mine(rows):
    found = []
    for degree, monomials in MONOMIALS.items():
        matrix = [values(row["distances"], monomials) for row in rows]
        for left, right in itertools.combinations(range(len(monomials)), 2):
            if matrix[0][left] == 0 or matrix[0][right] == 0:
                continue
            coefficient = matrix[0][left] / matrix[0][right]
            if coefficient.p > 16 or coefficient.q > 16:
                continue
            if all(row[left] == coefficient * row[right] for row in matrix):
                found.append((degree, monomials[left], monomials[right], coefficient))
    return found


def residual(relation, distances):
    _, left, right, coefficient = relation
    return s.prod(distances[k] for k in left) - coefficient * s.prod(distances[k] for k in right)


def text_relation(relation):
    _, left, right, coefficient = relation
    term = lambda ids: " * ".join(FEATURES[k] for k in ids) or "1"
    return f"{term(left)} = {coefficient} * {term(right)}"


def reduce_duplicate(relation):
    degree, left, right, coefficient = relation
    left, right = list(left), list(right)
    for k in left.copy():
        if k in right:
            left.remove(k)
            right.remove(k)
    if len(left) == len(right) == 2 and left[0] == left[1] and right[0] == right[1]:
        root = s.sqrt(coefficient)
        if root.is_Rational:
            return 1, (left[0],), (right[0],), root
    return len(left), tuple(left), tuple(right), coefficient


def main():
    started = time.perf_counter()
    timings = {}
    # Three different numerical sizes, but only ONE triangle shape: diagnostic
    # of why merely multiplying numerical variants gives misleading evidence.
    similar = [
        {"params": [str(k), str(4*k), str(3*k)], "distances": squared_distances(construct(k, 4*k, 3*k))}
        for k in (1, 2, 3)
    ]
    train_pool = sample(20260925, 12)
    heldout_pool = sample(20260926, 50)
    train = distinct_shapes(train_pool)
    train_shapes = {canonical_shape(row) for row in train}
    heldout_unique = distinct_shapes(heldout_pool)
    heldout = distinct_shapes(heldout_unique, excluded=train_shapes)
    assert len(train_shapes) == len(train)
    heldout_shapes = {canonical_shape(row) for row in heldout}
    assert len(heldout_shapes) == len(heldout)
    assert train_shapes.isdisjoint(heldout_shapes)
    timings["construction_seconds"] = time.perf_counter() - started
    t = time.perf_counter()
    similar_candidates = mine(similar)
    candidates = mine(train)
    timings["enumeration_seconds"] = time.perf_counter() - t
    t = time.perf_counter()
    rejected = []
    for relation in similar_candidates:
        witness = next((r for r in train + heldout if residual(relation, r["distances"]) != 0), None)
        if witness:
            rejected.append({"relation": text_relation(relation), "counterexample": witness["params"], "residual": str(residual(relation, witness["distances"]))})
    heldout_failures = [text_relation(c) for c in candidates if any(residual(c, r["distances"]) != 0 for r in heldout)]
    timings["counterexample_seconds"] = time.perf_counter() - t
    t = time.perf_counter()
    u, v, b = s.symbols("u v b", real=True, nonzero=True)
    symbolic = squared_distances(construct(u, v, b))
    # Definition-only baseline: M midpoint, P on AM and HP perpendicular AM;
    # H is otherwise arbitrary. Removing the orthocenter constrains no theorem.
    alpha, beta = s.symbols("alpha beta", real=True)
    bare = {"A": Point(u, v), "B": Point(-b, 0), "C": Point(b, 0), "M": Point(0, 0), "P": Point(alpha*u, alpha*v), "H": Point(alpha*u-beta*v, alpha*v+beta*u)}
    bare_distances = squared_distances(bare)
    unique = sorted(set(reduce_duplicate(c) for c in candidates), key=text_relation)
    symbolic_results = []
    for c in unique:
        result = s.cancel(residual(c, symbolic))
        definitional = s.cancel(residual(c, bare_distances)) == 0
        symbolic_results.append({"relation": text_relation(c), "identity_verified": result == 0, "symbolic_residual": str(result), "follows_from_midpoint_and_foot_definitions_without_orthocenter": definitional})
    timings["symbolic_seconds"] = time.perf_counter() - t
    timings["total_seconds"] = time.perf_counter() - started
    exponent_rows = [
        [left.count(k) - right.count(k) for k in range(len(PAIRS))]
        for _, left, right, _ in unique
    ]
    report = {
        "scope": "H01 only; exact rational samples and rational symbolic identities; no LLM, training, solver.solve, theorem dictionary or target-relation candidate injection",
        "grammar": "all same-degree pairs of degree-1 and degree-2 monomials of 15 squared distances; coefficient p/q with 1<=p,q<=16; simplify common factors / equivalent squared relations only after mining",
        "seeds": {"train": 20260925, "heldout": 20260926},
        "shape_equivalence": "canonical key (abs(u/b), v/b); mirror images and B,C exchanges are equivalent; fixed original pools, no replenishment after filtering",
        "train_candidate_pool_count": len(train_pool),
        "heldout_candidate_pool_count": len(heldout_pool),
        "heldout_distinct_shapes_before_train_exclusion": len(heldout_unique),
        "correction_note": "The earlier 47 heldout rows contained mirror-equivalent duplicates and mirror-equivalent train shapes. They represented 43 distinct shapes, only 40 unseen against train. General identity results are not numerical holdout evidence.",
        "input_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "train_instances": [r["params"] for r in train],
        "heldout_instances": [r["params"] for r in heldout],
        "train_instance_count": len(train),
        "heldout_instance_count": len(heldout),
        "similarity_only_candidates": len(similar_candidates),
        "similarity_only_candidates_refuted": len(rejected),
        "diverse_train_candidates": len(candidates),
        "heldout_counterexamples": heldout_failures,
        "deduplicated_candidates": len(unique),
        "definition_only_count": sum(r["follows_from_midpoint_and_foot_definitions_without_orthocenter"] for r in symbolic_results),
        "binomial_exponent_rank_not_theorem_count": s.Matrix(exponent_rows).rank(),
        "symbolic_verified_count": sum(r["identity_verified"] for r in symbolic_results),
        "symbolic_domain": "b,v != 0; u need not be nonzero for identities but is excluded in sampled scalene triangles. Primitive line denominator u^2+v^2 > 0. Assumes real coordinates. Symbolic verification establishes equalities, not arbitrary NL proofs or inequalities.",
        "timings": timings,
        "relations": symbolic_results,
        "refutations": rejected,
    }
    (OUT / "results.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({k:v for k,v in report.items() if k not in {"train_instances", "heldout_instances", "relations", "refutations"}}, indent=2))
    print("NON-DEFINITIONAL RELATIONS (not an independence or usefulness claim):")
    for row in symbolic_results:
        if not row["follows_from_midpoint_and_foot_definitions_without_orthocenter"]:
            print(row)


if __name__ == "__main__":
    main()
