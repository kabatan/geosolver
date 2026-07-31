#!/usr/bin/env python3
"""Generated D0 for the multi-target product identity."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from candidate import prove_multi_target_identity


HERE = Path(__file__).resolve().parent


def _case(
    name: str,
    variables: list[str],
    equations: list[str],
    target: str,
    factors: list[list[int]],
    expected: bool,
) -> dict[str, object]:
    source_sha256 = hashlib.sha256(f"synthetic-source:{name}".encode()).hexdigest()
    artifact_sha256s = [
        hashlib.sha256(f"synthetic-descriptor:{name}:{index}:{factor}".encode()).hexdigest()
        for index, factor in enumerate(factors)
    ]
    result = prove_multi_target_identity(
        variables=variables,
        active_equations=equations[: len(variables)],
        all_equations=equations,
        target_expression=target,
        factors_high_to_low=factors,
        descriptor_artifact_sha256s=artifact_sha256s,
        source_sha256=source_sha256,
    )
    actual = result["status"] == "IDENTITY_VERIFIED"
    if actual is not expected:
        raise AssertionError(f"{name}: expected {expected}, got {result}")
    return {
        "name": name,
        "expected": expected,
        "verified": actual,
        "factor_count": result["factor_count"],
        "product_degree": result["product_degree"],
    }


def main() -> int:
    rows = [
        _case("two-rational-components", ["x"], ["x**2-1"], "x", [[1, -1], [1, 1]], True),
        _case(
            "rational-and-quadratic-components",
            ["x"],
            ["(x-1)*(x**2-2)"],
            "x",
            [[1, -1], [1, 0, -2]],
            True,
        ),
        _case(
            "target-collapses-four-configurations",
            ["x"],
            ["(x**2-1)*(x**2-4)"],
            "x**2",
            [[1, -1], [1, -4]],
            True,
        ),
        _case(
            "positive-dimensional-constant-finite-image",
            ["x", "y"],
            ["x**2-1", "y*(x**2-1)"],
            "x",
            [[1, -1], [1, 1]],
            True,
        ),
        _case(
            "rational-target-denominator",
            ["x"],
            ["x**2-1"],
            "1/x",
            [[1, -1], [1, 1]],
            True,
        ),
        _case(
            "missing-factor-negative",
            ["x"],
            ["(x-1)*(x**2-2)"],
            "x",
            [[1, 0, -2], [1, -3]],
            False,
        ),
        _case(
            "wrong-near-polynomial-negative",
            ["x"],
            ["x**2-1"],
            "x",
            [[100000000000000000000, -100000000000000000001], [1, 1]],
            False,
        ),
    ]
    positives = sum(item["expected"] is True and item["verified"] is True for item in rows)
    negatives = sum(item["expected"] is False and item["verified"] is False for item in rows)
    output = {
        "schema_version": "geotarget.multi-target-sparse-cofactor-generated-d0/v1",
        "decision": "GO_REAL_APPLICABILITY" if positives == 5 and negatives == 2 else "STOP",
        "family_count": 5,
        "positive_pass_count": positives,
        "negative_reject_count": negatives,
        "false_accept_count": 0,
        "target_set_completeness_claim": False,
        "proposal_authority": False,
        "rows": rows,
    }
    path = HERE / "GENERATED_RESULT.json"
    path.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({**output, "rows": None}, sort_keys=True))
    print(hashlib.sha256(path.read_bytes()).hexdigest())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
