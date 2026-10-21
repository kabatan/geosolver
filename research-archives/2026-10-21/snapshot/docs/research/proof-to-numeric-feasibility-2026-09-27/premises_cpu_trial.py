"""Small CPU receipt: construct from premises; never read theorem/proof/answer key.

Run from repository root with .venv/bin/python <this file>.
The fixed coordinates are a complete triangle instantiation, not a derived lemma.
Public solver inputs and returned descriptors are saved next to this script.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from geosolver import GeometryProblem, SolveOptions, solve, validate


HERE = Path(__file__).resolve().parent


def constructions(pairs):
    return [{"name": name, "expression": expression} for name, expression in pairs]


TRIANGLE = [("A", "Point(0,4)"), ("B", "Point(-2,0)"), ("C", "Point(4,0)")]
HUMPTY = TRIANGLE + [
    ("M", "Midpoint(B,C)"),
    ("H", "Orthocenter(A,B,C)"),
    ("P", "FootOfPerpendicular(H,Line(A,M))"),
]
DUMPTY = TRIANGLE + [
    ("U", "IntersectLines(PerpendicularLine(Line(A,C),A),PerpendicularBisector(A,B))"),
    ("V", "IntersectLines(PerpendicularLine(Line(A,B),A),PerpendicularBisector(A,C))"),
    ("omega", "CircleThroughPoint(U,A)"),
    ("sigma", "CircleThroughPoint(V,A)"),
    ("T", "Intersect(omega,sigma,exclude=A)"),
]
DA15 = TRIANGLE + [
    ("M", "Midpoint(B,C)"),
    ("O", "Circumcenter(A,B,C)"),
    ("D", "IntersectLines(PerpendicularBisector(A,B),Line(A,M))"),
    ("E", "IntersectLines(PerpendicularBisector(A,C),Line(A,M))"),
    ("F", "IntersectLines(Line(B,D),Line(C,E))"),
]


def problem(cid, pairs, target, extra=()):
    return GeometryProblem(
        id=cid,
        variables=[],
        constructions=constructions(pairs),
        conditions=[{"predicate": "AcuteTriangle(A,B,C)"}, *extra],
        target=target,
    )


def main():
    # Query is a primitive metric of already named points. No gold relation is used.
    tasks = [
        problem("H01_full_shape", HUMPTY, "Distance(A,P)"),
        problem("H04_full_shape", HUMPTY + [
            ("T", "IntersectLines(PerpendicularBisector(A,P),Line(B,C))"),
        ], "Distance(A,T)", [{"predicate": "Order(T,B,C)"}]),
        problem("DA01_full_shape", DUMPTY, "Distance(A,T)"),
        problem("DA15_full_shape", DA15, "Distance(O,F)", [
            {"left": "Dot(Vector(A,D),Vector(A,M))", "operator": ">", "right": 0},
            {"left": "Dot(Vector(A,E),Vector(A,M))", "operator": ">", "right": 0},
            {"left": "Area(A,F,B)+Area(B,F,C)+Area(C,F,A)",
             "operator": "=", "right": "Area(A,B,C)"},
            {"left": "Area(A,F,B)", "operator": ">", "right": 0},
            {"left": "Area(B,F,C)", "operator": ">", "right": 0},
            {"left": "Area(C,F,A)", "operator": ">", "right": 0},
        ]),
    ]
    rows = []
    for task in tasks:
        validation = validate(task)
        print(task.id, "validation", validation.valid, flush=True)
        row = {"problem": task.model_dump(mode="json"),
               "validation": validation.model_dump(mode="json")}
        if validation.valid:
            result = solve(task, SolveOptions(time_limit_seconds=180, cores=1, seed=0))
            row["result"] = result.model_dump(mode="json")
            print(task.id, result.status, [a.decimal for a in result.answers],
                  result.elapsed_seconds, flush=True)
        rows.append(row)
        # Preserve partial receipt if a later task is interrupted.
        receipt = {"purpose": "premises-only full-shape label API smoke trial",
                   "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                   "no_theorem_or_proof_loaded": True, "gpu_used": False,
                   "scope": "one complete fixed shape; no general uniqueness claim",
                   "rows": rows}
        (HERE / "CPU_RECEIPT.json").write_text(
            json.dumps(receipt, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
