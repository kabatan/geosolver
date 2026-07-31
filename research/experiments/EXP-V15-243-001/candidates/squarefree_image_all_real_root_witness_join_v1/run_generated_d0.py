#!/usr/bin/env python3
"""Generated theorem gate for upper-bound + every-real-root witness join."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Mapping

import sympy as sp

from candidate import canonical_sha256, certify_complete_target_image


HERE = Path(__file__).resolve().parent


def _sha(label: str) -> str:
    return hashlib.sha256(label.encode()).hexdigest()


def _run(
    name: str,
    equation: str,
    target_expression: str,
    factors: list[list[int]],
    coordinate_for_root,
    guard,
    expected: bool,
) -> dict[str, object]:
    source_sha = _sha(f"source:{name}")
    descriptor_shas = [_sha(f"descriptor:{name}:{index}") for index in range(len(factors))]

    def provider(specification: Mapping[str, object]):
        root = specification["exact_root"]
        coordinate = coordinate_for_root(root)
        if coordinate is None:
            return None
        x = sp.Symbol("x", real=True)
        if sp.simplify(sp.sympify(equation, locals={"x": x}).subs(x, coordinate)) != 0:
            return None
        if not guard(coordinate):
            return None
        if sp.simplify(sp.sympify(target_expression, locals={"x": x}).subs(x, coordinate) - root) != 0:
            return None
        body = {
            "source_sha256": source_sha,
            "system_sha256": None,
            "descriptor_set_sha256": None,
            "product_real_root_index": specification["product_real_root_index"],
            "factor_index": specification["factor_index"],
            "factor_coefficients_high_to_low": specification["factor_coefficients_high_to_low"],
            "factor_real_root_index": specification["factor_real_root_index"],
            "exact_source_guard_branch_raw_target_replay": True,
            "target_equals_selected_root": True,
            "truth_used": False,
            "target_set_completeness_claim": False,
        }
        return body

    # The provider must bind the system and descriptor-set hashes computed by
    # the upper proof.  Wrap once to fill only those two frozen fields.
    pending: dict[str, object] = {}

    def bound_provider(specification: Mapping[str, object]):
        body = provider(specification)
        if body is None:
            return None
        body["system_sha256"] = pending["system_sha256"]
        body["descriptor_set_sha256"] = pending["descriptor_set_sha256"]
        body["artifact_sha256"] = canonical_sha256(body)
        return body

    # Obtain the deterministic upper bindings once; this does not authorize.
    import candidate as join_module
    upper_module = join_module._load_upper()
    upper = upper_module.prove_multi_target_identity(
        variables=["x"], active_equations=[equation], all_equations=[equation],
        target_expression=target_expression, factors_high_to_low=factors,
        descriptor_artifact_sha256s=descriptor_shas, source_sha256=source_sha,
    )
    pending.update(system_sha256=upper["system_sha256"], descriptor_set_sha256=upper["descriptor_set_sha256"])
    result = certify_complete_target_image(
        variables=["x"], active_equations=[equation], all_equations=[equation],
        target_expression=target_expression, factors_high_to_low=factors,
        descriptor_artifact_sha256s=descriptor_shas, source_sha256=source_sha,
        witness_provider=bound_provider,
    )
    actual = result["status"] == "ALL_REAL_ROOT_WITNESS_JOIN_PROPOSAL_READY"
    if actual is not expected:
        raise AssertionError(f"{name}: expected={expected}, result={result}")
    return {"name": name, "expected": expected, "certified": actual, "reason": result.get("reason")}


def main() -> int:
    rows = [
        _run("two-rational", "x**2-1", "x", [[1,-1],[1,1]], lambda r: r, lambda _x: True, True),
        _run("rational-plus-quadratic", "(x-1)*(x**2-2)", "x", [[1,-1],[1,0,-2]], lambda r: r, lambda _x: True, True),
        _run("collapsed-four-configurations", "(x**2-1)*(x**2-4)", "x**2", [[1,-1],[1,-4]], lambda r: sp.sqrt(r), lambda _x: True, True),
        _run("missing-conjugate", "(x-1)*(x**2-2)", "x", [[1,-1],[1,0,-2]], lambda r: None if r == -sp.sqrt(2) else r, lambda _x: True, False),
        _run("extra-factor", "x**2-1", "x", [[1,-1],[1,1],[1,-3]], lambda r: r, lambda _x: True, False),
        _run("guard-excluded-conjugates", "(x**2-2)*(x**2-8)", "x", [[1,0,-2],[1,0,-8]], lambda r: r, lambda x: bool(x > 0), False),
    ]
    output = {
        "schema_version": "geotarget.squarefree-image-all-real-root-witness-generated-d0/v1",
        "decision": "GO_REAL_JOIN" if sum(row["certified"] for row in rows)==3 else "STOP",
        "positive_pass_count": sum(row["expected"] and row["certified"] for row in rows),
        "negative_reject_count": sum((not row["expected"]) and (not row["certified"]) for row in rows),
        "false_complete_count": 0,
        "target_set_completeness_claim": False,
        "canonical_outer_release_required": True,
        "rows": rows,
    }
    path = HERE / "GENERATED_RESULT.json"
    path.write_text(json.dumps(output, indent=2, sort_keys=True)+"\n", encoding="utf-8")
    print(json.dumps({**output, "rows": None}, sort_keys=True))
    print(hashlib.sha256(path.read_bytes()).hexdigest())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
