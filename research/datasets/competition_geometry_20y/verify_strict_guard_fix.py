#!/usr/bin/env python3
"""Small, runtime-only regression checks for the strict-boundary fix.

Run with the patched runtime on ``PYTHONPATH``.  The script deliberately uses
only public construction contracts plus the two fixed boundary primitives; it
does not modify a runtime or a DSL case.
"""

from mpmath import mp

from geosolver._internal.autosolve.guards.compile import GuardIR, guard_margin_value
from geosolver._internal.pipeline.contracts.candidate_record import RefinedCandidate
from geosolver._internal.pipeline.orchestration.run_phasec_assembly import (
    run_phasec_assembly,
)


def main() -> None:
    mp.dps = 160
    guard = GuardIR(
        source="AssumeGt(x,0)",
        kind="compare",
        operator=">",
        lhs_expr="x",
        rhs_expr="0",
    )
    margin = guard_margin_value(
        guard,
        {"x": mp.mpf("1e-122"), "mpf": mp.mpf},
    )
    assert margin == mp.mpf("1e-122"), margin

    boundary_candidate = RefinedCandidate(
        x_hp=(mp.mpf("1e-122"),),
        residual_norm_hp=mp.mpf("0"),
        answer_hp=mp.mpf("1e-122"),
        refinement_status="stalled",
        phase_history=(),
        hard_feasible=True,
        validity_margin_hp=margin,
    )
    boundary_result = run_phasec_assembly(
        refined_candidates=(boundary_candidate,),
        input_precision_dps=120,
    )
    assert boundary_result.accepted_candidates == (), boundary_result
    assert "margin_too_small" in boundary_result.rejection_tags, boundary_result

    regular_candidate = RefinedCandidate(
        x_hp=(mp.mpf("1"),),
        residual_norm_hp=mp.mpf("0"),
        answer_hp=mp.mpf("1"),
        refinement_status="stalled",
        phase_history=(),
        hard_feasible=True,
        validity_margin_hp=mp.mpf("1"),
    )
    regular_result = run_phasec_assembly(
        refined_candidates=(regular_candidate,),
        input_precision_dps=120,
    )
    assert len(regular_result.accepted_candidates) == 1, regular_result
    assert regular_result.answer_values == ("1",), regular_result
    print("strict guard regression: PASS")


if __name__ == "__main__":
    main()
