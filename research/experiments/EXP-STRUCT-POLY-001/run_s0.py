#!/usr/bin/env python3
"""Generated-only ablation for the combined BTF/polynomial route."""

from __future__ import annotations

import json
import math

from btf_polynomial_pipeline import (
    detect_btf_polynomial_plan,
    run_btf_polynomial_side_route,
)
from polynomial_side_route import detect_polynomial_plan


def mixed_chain():
    return {
        "task": "solve",
        "variables": {"names": ["x", "y", "z", "w"]},
        "construction": [],
        "constraints": [
            {"def": "x**2", "value": 1},
            {"def": "y", "value": "x"},
            {"def": "sin(z)", "value": 0},
            {"def": "w", "value": "z"},
        ],
        "guards": [],
    }


def canonical(point):
    x, y, z, w = point
    residuals = (x * x - 1.0, y - x, math.sin(z), w - z)
    return all(math.isfinite(value) for value in point) and max(map(abs, residuals)) < 1e-12


def main() -> None:
    formulation = mixed_chain()
    whole = detect_polynomial_plan(formulation)
    combined_plan = detect_btf_polynomial_plan(formulation)
    combined = run_btf_polynomial_side_route(
        formulation,
        (0.8, 1.0, 0.0, 0.0),
        canonical,
        total_starts=16,
        timeout_seconds=1.0,
    )

    irreducible_formulation = {
        "variables": {"names": ["x", "y"]},
        "construction": [],
        "constraints": [
            {"def": "x + y", "value": 1},
            {"def": "x - y", "value": 0},
        ],
        "guards": [],
    }
    irreducible = run_btf_polynomial_side_route(
        irreducible_formulation,
        (0.0, 0.0),
        lambda _point: False,
        total_starts=16,
    )
    nonpolynomial_formulation = {
        "variables": {"names": ["x", "y"]},
        "construction": [],
        "constraints": [
            {"def": "sin(x)", "value": 0},
            {"def": "cos(y)", "value": 1},
        ],
        "guards": [],
    }
    nonpolynomial = run_btf_polynomial_side_route(
        nonpolynomial_formulation,
        (0.0, 0.0),
        lambda _point: False,
        total_starts=16,
    )
    result = {
        "schema_version": "geotarget.exp-struct-poly-001-s0/v1",
        "generated_only": True,
        "truth_routing": False,
        "ablation": {
            "whole_system_polynomial": {
                "applicable": whole.applicable,
                "reason": whole.reason,
                "proposals": 0,
            },
            "btf_structure_only": {
                "applicable": bool(combined_plan.structure_plan and combined_plan.structure_plan.applicable),
                "block_count": len(combined_plan.block_gates),
                "proposals": 0,
            },
            "btf_then_polynomial": {
                "applicable": combined_plan.applicable,
                "active_polynomial_blocks": len(combined_plan.active_blocks),
                "block_gate_reasons": [
                    gate.polynomial_plan.reason for gate in combined_plan.block_gates
                ],
                "proposals": len(combined.proposals),
                "canonical_verifier_calls": combined.verifier_calls,
                "verified": len(combined.verified),
            },
        },
        "portfolio": {
            "total_starts": combined.allocation.total_starts,
            "baseline_starts": combined.allocation.baseline_starts,
            "symbolic_slots": combined.allocation.symbolic_slots,
        },
        "fallbacks": {
            "irreducible": {
                "status": irreducible.status,
                "reason": irreducible.plan.reason,
                "baseline_starts": irreducible.allocation.baseline_starts,
                "proposals": len(irreducible.proposals),
            },
            "all_nonpolynomial": {
                "status": nonpolynomial.status,
                "reason": nonpolynomial.plan.reason,
                "baseline_starts": nonpolynomial.allocation.baseline_starts,
                "proposals": len(nonpolynomial.proposals),
            },
        },
        "canonical_verifier_bypassed": False,
        "whole_system_reopen_gate_generated": (
            not whole.applicable and combined_plan.applicable and bool(combined.verified)
        ),
    }
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
