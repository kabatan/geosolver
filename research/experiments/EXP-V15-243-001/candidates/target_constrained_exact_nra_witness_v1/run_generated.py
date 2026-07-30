"""Truth-free generated D0 for target-constrained exact NRA witnesses."""

from __future__ import annotations

from dataclasses import replace
from fractions import Fraction
import json
from pathlib import Path
import time

import sympy as sp

from candidate import PolynomialSource, TargetProposal, prove, prove_semantic_document


HERE = Path(__file__).resolve().parent


def proposal(coefficients, ordinal, lower, upper):
    return TargetProposal(tuple(coefficients), ordinal, Fraction(lower), Fraction(upper))


def generated():
    x, y = sp.symbols("x y", real=True)
    regular = PolynomialSource(
        ("x", "y"),
        (x**2 - 2, y - x),
        sp.And(x > 0, y > 0),
        x + y,
        label="regular-irrational-coupled",
    )
    regular_p = proposal((1, 0, -8), 1, 2, 3)
    singular = PolynomialSource(
        ("x", "y"),
        ((x**2 - 3) ** 2, y - x**2),
        sp.And(x < 0, sp.Eq(y, 3)),
        x,
        label="singular-nonradical",
    )
    singular_p = proposal((1, 0, -3), 0, -2, -1)
    positive_dimensional = PolynomialSource(
        ("x", "y"),
        (x**2 - 5,),
        x > 0,
        x,
        label="positive-dimensional-configuration-finite-target",
    )
    positive_dimensional_p = proposal((1, 0, -5), 1, 2, 3)
    division = PolynomialSource(
        ("x", "y"),
        ((x**2 - 2) / (x + 1), y - x),
        x > 0,
        1 / (x + 2),
        label="explicit-division-definedness",
    )
    division_p = proposal((2, -4, 1), 0, Fraction(1, 4), Fraction(1, 3))
    return regular, regular_p, singular, singular_p, positive_dimensional, positive_dimensional_p, division, division_p


def run() -> dict[str, object]:
    started = time.monotonic()
    regular, rp, singular, sp_, positive_dimensional, pp, division, dp = generated()
    x, y = sp.symbols("x y", real=True)
    positives = [
        (regular, rp),
        (singular, sp_),
        (positive_dimensional, pp),
        (division, dp),
    ]
    positive_rows = [
        {"structure": source.label, "result": prove(source, candidate)}
        for source, candidate in positives
    ]
    semantic_document = {
        "variables": {"names": ["x"]},
        "construction": [],
        "constraints": [{"def": "x*x", "value": "2"}],
        "guards": ["AssumeGt(x,0)"],
        "answer": "x",
        "post_process": "",
    }
    positive_rows.append(
        {
            "structure": "frozen-semantic-frontend-untouched-replay",
            "result": prove_semantic_document(
                semantic_document, proposal((1, 0, -2), 1, 1, 2)
            ),
        }
    )
    negatives = [
        ("wrong-polynomial", regular, proposal((1, 0, -7), 1, 2, 3)),
        ("wrong-isolator", regular, proposal((1, 0, -8), 1, -3, -2)),
        (
            "strict-guard-boundary",
            PolynomialSource(("x", "y"), (x, y), x > 0, x, label="strict-boundary"),
            proposal((1, 0), 0, -1, 1),
        ),
        (
            "denominator-zero",
            PolynomialSource(("x", "y"), (x - 1, y), sp.true, x, (x - 1,), "denominator-zero"),
            proposal((1, -1), 0, 0, 2),
        ),
        (
            "unsupported-transcendental",
            PolynomialSource(("x", "y"), (sp.sin(x), y), sp.true, x, label="transcendental"),
            proposal((1, 0), 0, -1, 1),
        ),
        (
            "boolean-guard-reject",
            replace(regular, guard=sp.Or(x < 0, sp.Eq(y, 0)), label="boolean-reject"),
            rp,
        ),
    ]
    negative_rows = [
        {"mutation": name, "result": prove(source, candidate)}
        for name, source, candidate in negatives
    ]

    permuted = PolynomialSource(
        ("y", "x"), regular.equations[::-1], regular.guard, regular.raw_target,
        label="variable-and-equation-permutation",
    )
    scaled = replace(
        regular,
        equations=(sp.Rational(7, 3) * regular.equations[0], -11 * regular.equations[1]),
        label="nonzero-rational-equation-scale",
    )
    affine = replace(
        regular,
        raw_target=3 * regular.raw_target + 1,
        label="reversible-affine-target",
    )
    affine_p = proposal((1, -2, -71), 1, 9, 10)
    metamorphic_rows = [
        {"mutation": "permutation", "result": prove(permuted, rp)},
        {"mutation": "equation-scale", "result": prove(scaled, rp)},
        {"mutation": "affine-target", "result": prove(affine, affine_p)},
    ]
    result = {
        "schema_version": "geotarget.target-constrained-exact-nra-generated-d0/v1",
        "preferred_backend": "Z3 complete QF_NRA",
        "preferred_backend_available": False,
        "fallback_backend": "complete zero-dimensional QQ subset via SymPy",
        "positive": positive_rows,
        "negative": negative_rows,
        "metamorphic": metamorphic_rows,
        "positive_activation_count": sum(row["result"]["authority_pass"] is True for row in positive_rows),
        "negative_false_accept_count": sum(row["result"]["authority_pass"] is True for row in negative_rows),
        "metamorphic_pass_count": sum(row["result"]["authority_pass"] is True for row in metamorphic_rows),
        "elapsed_seconds": time.monotonic() - started,
    }
    result["decision"] = (
        "GO_D0"
        if result["positive_activation_count"] >= 2
        and result["negative_false_accept_count"] == 0
        and result["metamorphic_pass_count"] == len(metamorphic_rows)
        else "HOLD"
    )
    return result


def main() -> None:
    result = run()
    compact = {
        "schema_version": result["schema_version"],
        "decision": result["decision"],
        "preferred_backend_available": result["preferred_backend_available"],
        "fallback_backend": result["fallback_backend"],
        "positive_activation_count": result["positive_activation_count"],
        "negative_false_accept_count": result["negative_false_accept_count"],
        "metamorphic_pass_count": result["metamorphic_pass_count"],
        "elapsed_seconds": result["elapsed_seconds"],
        "positive": [
            {
                "structure": row["structure"],
                "authority_pass": row["result"]["authority_pass"],
            }
            for row in result["positive"]
        ],
        "negative": [
            {
                "mutation": row["mutation"],
                "authority_pass": row["result"]["authority_pass"],
                "reason": row["result"].get("reason"),
            }
            for row in result["negative"]
        ],
        "metamorphic": [
            {
                "mutation": row["mutation"],
                "authority_pass": row["result"]["authority_pass"],
            }
            for row in result["metamorphic"]
        ],
    }
    payload = json.dumps(compact, indent=2, sort_keys=True) + "\n"
    (HERE / "GENERATED_RESULT.json").write_text(payload, encoding="utf-8")
    print(payload, end="")


if __name__ == "__main__":
    main()
