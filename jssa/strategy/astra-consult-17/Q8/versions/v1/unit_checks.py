"""Small mathematical counterexamples; not the natural-problem pilot."""
import copy
import json
from pathlib import Path
import sympy as s

from exact_onevar import solve, Unsupported, root_from_wire, Compiler, eval_formula
from verify_certificate import verify, same_set


def dsl(id, left, right=0, guards=(), constructions=(), target="x"):
    return {"id": id, "variables": ["x"], "constructions": list(constructions),
            "conditions": [{"left": left, "operator": "=", "right": right}, *guards], "target": target}


def main():
    rows = []
    examples = [
        (dsl("two-roots", "x*x", 2), [-s.sqrt(2), s.sqrt(2)]),
        (dsl("repeated-root", "(x-2)**2"), [s.Integer(2)]),
        (dsl("sqrt-sign", "sqrt(x+2)", "x"), [s.Integer(2)]),
        (dsl("denominator-pole", "(x*x-1)/(x-1)", 0), [s.Integer(-1)]),
        (dsl("empty-real", "x*x+1"), []),
        (dsl("guarded-root", "x*x", 4, [{"left":"x", "operator":">", "right":0}]), [s.Integer(2)]),
        (dsl("undefined-cancel", "x*x", 1,
             constructions=[{"name":"q", "expression":"(x-1)/(x-1)"}]), [s.Integer(-1)]),
        (dsl("algebraic-coefficient", "x-sqrt(2)"), [s.sqrt(2)]),
        (dsl("absolute-branches", "abs(x-1)", 2), [s.Integer(-1), s.Integer(3)]),
        (dsl("empty-by-guard", "x*x", 1, [{"left":"x", "operator":">", "right":5}]), []),
    ]
    for problem, expected in examples:
        cert = solve(problem)
        check = verify(problem, cert)
        actual = [root_from_wire(a) for a in cert["answer_set"]]
        assert len(actual) == len(expected)
        assert all(any(s.simplify(a-e) == 0 for a in actual) for e in expected), (problem["id"], actual)
        negative = []
        if cert["roots"]:
            bad = copy.deepcopy(cert)
            bad["roots"].pop()
            try:
                verify(problem, bad)
            except ValueError:
                negative.append("omitted_root_detected")
            else:
                raise AssertionError("omitted root accepted")
        if cert["answer_set"]:
            bad = copy.deepcopy(cert)
            bad["answer_set"].pop()
            try:
                verify(problem, bad)
            except ValueError:
                negative.append("omitted_answer_detected")
            else:
                raise AssertionError("omitted answer accepted")
        rows.append({"id": problem["id"], "passed": True, "check": check, "negative": negative})
    # Unknown feature is refused, not silently translated to a polynomial.
    try:
        solve(dsl("free-trig", "sin(x)"))
    except Unsupported:
        rows.append({"id": "free-trig", "passed": True, "refused": True})
    else:
        raise AssertionError("free trigonometric variable accepted")
    path = Path(__file__).with_name("unit-checks.json")
    path.write_text(json.dumps(rows, indent=2) + "\n")
    print(json.dumps({"unit_checks": len(rows), "passed": True}))


if __name__ == "__main__":
    main()
