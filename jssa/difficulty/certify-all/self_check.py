"""Synthetic correctness tests; not benchmark cases and not experiment results."""
from pathlib import Path
import json
import sys
import subprocess
import copy

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from bounds import target_bounds, FULL
import sympy as sp


def dsl(conditions, target="x", constructions=None):
    return {"id": "synthetic", "variables": ["x"], "constructions": constructions or [], "conditions": conditions, "target": target}


def cond(left, op, right): return {"left": left, "operator": op, "right": right}


def main():
    checks = []
    examples = [
        (dsl([cond("x", ">", 0), cond(3, ">", "x")]), (0, 3, True, True)),
        (dsl([cond("x", ">", 0), cond("x", ">=", 0)]), (0, sp.oo, True, False)),
        (dsl([cond("x", ">=", 1), cond("x", "<=", 4)], "1/x"), (sp.Rational(1,4), 1, False, False)),
        (dsl([cond("x", ">=", -2), cond("x", "<=", 3)], "x**2"), (0, 9, False, False)),
        (dsl([cond("x", ">", 0)], "a", [{"name": "a", "expression": "x"}]), (0, sp.oo, True, False)),
        (dsl([], "Distance(A,B)", [{"name":"A","expression":"Point(0,0)"},{"name":"B","expression":"Point(3,4)"}]), (5,5,False,False)),
    ]
    for d, expected in examples:
        got, proof = target_bounds(d)
        assert tuple(got) == expected, (got, expected)
        checks.append({"kind": "exact_bound", "target": d["target"], "pass": True})
    base = [cond("x**2", "=", 4)]
    trials = [
        ("_test_positive", dsl(base + [cond("x", ">", 0)]), [2.0], "certified_saved_endpoint_set"),
        ("_test_two_roots", dsl(base), [-2.0, 2.0], "certified_saved_endpoint_set"),
        ("_test_missing_root", dsl(base), [2.0], "multiple_roots_remain"),
        ("_test_cubic", dsl([cond("x**3", "=", 2),cond("x", ">", 0)]), [2**(1/3)], "certified_saved_endpoint_set"),
        ("_test_rational_domain", dsl([cond("x**2", "=", 4),cond("x", ">", 0)], "1/x"), [2.0], "certified_saved_endpoint_set"),
    ]
    for cid, d, xs, expect in trials:
        d["id"] = cid
        inp = {"id": cid, "group": "synthetic_not_measured", "dsl": d,
               "source_kind": "synthetic", "source_path": "self_check.py", "source_sha256": None,
               "primary_main_output_available": False,
               "candidates": [{"k": i, "x": [x], "value_float": 1/x if d["target"] == "1/x" else x, "saved_residual": 0.0} for i,x in enumerate(xs)]}
        (HERE / "inputs" / f"{cid}.json").write_text(json.dumps(inp))
    cmd = [sys.executable, "-B", str(HERE / "run.py"), "--dest", "synthetic-check", "--ids"] + [r[0] for r in trials]
    subprocess.run(cmd, check=True)
    for cid, d, xs, expected in trials:
        result = json.loads((HERE / "synthetic-check" / cid / "result.json").read_text())
        assert result["status"] == expected, (cid, result["status"], expected, result.get("detail"))
        checks.append({"kind": "full_pipeline", "id": cid, "expected": expected, "pass": True})
    sys.path.insert(0, str(HERE.parents[2] / "jssa/strategy/astra-consult-17/L"))
    from verify_certificate import verify
    certp = next((HERE / "synthetic-check/_test_positive").glob("certificate-*.json"))
    cert = json.loads(certp.read_text())
    assert verify(cert)
    bad = copy.deepcopy(cert)
    bad["Q"][0][1] = str(sp.Rational(bad["Q"][0][1]) + 1)
    assert not verify(bad)
    checks.append({"kind": "corrupted_identity_rejected", "pass": True})
    (HERE / "self-check.json").write_text(json.dumps({"benchmark_results_used": False, "checks": checks}, indent=2) + "\n")
    print("synthetic checks passed", len(checks))


if __name__ == "__main__": main()
