"""Static input authoring and reference derivation; never calls a solver."""
from __future__ import annotations

import copy
import hashlib
import json
import re
from pathlib import Path

import sympy as sp
from geosolver import GeometryProblem
from geosolver.problem.validation import validate

OUT = Path(__file__).resolve().parent


def dump(path: Path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def main():
    if (OUT / "registration-lock.json").exists():
        raise SystemExit("Inputs are registered; do not regenerate them in place.")
    (OUT / "inputs").mkdir(exist_ok=True)
    base = {
        "variables": ["u"],
        "constructions": [
            {"name": n, "expression": e}
            for n, e in [
                ("O", "Point(0, 0)"), ("U", "Point(u, 0)"),
                ("V", "Point(u, 1)"), ("W", "Point(u, 2)"),
                ("X", "Point(2*u, 3)"), ("Y", "Point(u, 4)"),
                ("Z", "Point(u, 3)"),
            ]
        ],
        "conditions": [
            {"left": "Distance(O, V)", "operator": "=", "right": "sqrt(2)"},
            {"left": "u", "operator": ">", "right": "0"},
            {"left": "u", "operator": "<", "right": "2"},
        ],
    }
    queries = [
        ("R1", ["V"], sp.sqrt(2)),
        ("R2", ["V", "W"], sp.sqrt(2) + sp.sqrt(5)),
        ("R3", ["V", "W", "X"], sp.sqrt(2) + sp.sqrt(5) + sp.sqrt(13)),
        ("R4", ["V", "W", "X", "Y"], sp.sqrt(2) + sp.sqrt(5) + sp.sqrt(13) + sp.sqrt(17)),
        ("DEP", ["V", "V", "W", "Z"], 2*sp.sqrt(2) + sp.sqrt(5) + sp.sqrt(10)),
        ("S5", ["W"], sp.sqrt(5)),
        ("S13", ["X"], sp.sqrt(13)),
        ("S17", ["Y"], sp.sqrt(17)),
    ]
    cases, refs = [], {}
    for name, points, value in queries:
        dsl = copy.deepcopy(base)
        dsl.update(id=name, target=" + ".join(f"Distance(O, {p})" for p in points))
        cases.append(dsl)
        refs[name] = value
    fixed = copy.deepcopy(cases[3])
    fixed["id"] = "FIXED4"
    fixed["variables"] = []
    for item in fixed["constructions"]:
        item["expression"] = re.sub(r"\bu\b", "1", item["expression"])
    for item in fixed["conditions"]:
        item["left"] = re.sub(r"\bu\b", "1", item["left"])
    cases.append(fixed)
    refs["FIXED4"] = refs["R4"]
    cubic = {
        "id": "CUBIC", "variables": ["u", "v"],
        "constructions": [
            {"name": n, "expression": e}
            for n, e in [("O", "Point(0, 0)"), ("A", "Point(1, 0)"),
                         ("B", "Point(2, 0)"), ("U", "Point(u, 0)"), ("V", "Point(v, 0)")]
        ],
        "conditions": [
            {"left": "Distance(O, U)**2", "operator": "=", "right": "Distance(O, A)*Distance(O, V)"},
            {"left": "Distance(O, U)*Distance(O, V)", "operator": "=", "right": "Distance(O, A)*Distance(O, B)"},
            {"left": "u", "operator": ">", "right": "0"},
            {"left": "u", "operator": "<", "right": "2"},
            {"left": "v", "operator": ">", "right": "0"},
            {"left": "v", "operator": "<", "right": "2"},
        ],
        "target": "Distance(O, U)",
    }
    cases.append(cubic)
    refs["CUBIC"] = sp.real_root(2, 3)
    T = sp.Symbol("T")
    reference_rows, manifest = {}, []
    for dsl in cases:
        report = validate(GeometryProblem.model_validate(dsl))
        if not report.valid:
            raise ValueError((dsl["id"], report.model_dump()))
        path = OUT / "inputs" / f"{dsl['id']}.json"
        dump(path, dsl)
        value = refs[dsl["id"]]
        p = sp.Poly(sp.minpoly(value, T), T)
        reference_rows[dsl["id"]] = {
            "expression": str(value), "decimal_100": str(sp.N(value, 100)),
            "minimal_polynomial": str(p.as_expr()),
            "coefficients": [int(c) for c in p.all_coeffs()],
            "degree": p.degree(), "height": max(abs(int(c)) for c in p.all_coeffs()),
            "irreducible_over_Q": bool(p.is_irreducible),
            "root_expression_verified": sp.simplify(p.as_expr().subs(T, value)) == 0,
        }
        manifest.append({"id": dsl["id"], "path": str(path.relative_to(OUT)),
                         "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                         "valid": report.valid})
    dump(OUT / "references.json", reference_rows)
    dump(OUT / "input-manifest.json", manifest)
    print(json.dumps({"inputs": len(cases), "degree": {k: v["degree"] for k, v in reference_rows.items()}}, ensure_ascii=False))


if __name__ == "__main__":
    main()
