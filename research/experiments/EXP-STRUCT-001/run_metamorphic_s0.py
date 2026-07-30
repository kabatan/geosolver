#!/usr/bin/env python3
"""Truth-free metamorphic and counterexample screen for EXP-STRUCT-001."""

from __future__ import annotations

import itertools
import json
import types

from block_structure import analyze_relation_supports, extract_v15_structure
from champion_overlay import install, merge_block_proposals


def signature(plan):
    return {
        "applicable": plan.applicable,
        "reason": plan.reason,
        "block_sizes": sorted(len(block.variable_indices) for block in plan.blocks),
        "factor_work_ratio": plan.factor_work_ratio,
    }


def main() -> None:
    decomposable = ((0,), (0, 1), (1, 2), (0, 2, 3))
    expected = signature(analyze_relation_supports(decomposable, 4))
    residual_permutations = 0
    variable_permutations = 0
    combined_permutations = 0
    for relation_order in itertools.permutations(range(4)):
        residual_plan = analyze_relation_supports(
            (decomposable[index] for index in relation_order), 4
        )
        assert signature(residual_plan) == expected
        residual_permutations += 1
        for old_to_new in itertools.permutations(range(4)):
            transformed = tuple(
                tuple(old_to_new[index] for index in decomposable[relation])
                for relation in relation_order
            )
            assert signature(analyze_relation_supports(transformed, 4)) == expected
            combined_permutations += 1
    for old_to_new in itertools.permutations(range(4)):
        transformed = tuple(
            tuple(old_to_new[index] for index in support) for support in decomposable
        )
        assert signature(analyze_relation_supports(transformed, 4)) == expected
        variable_permutations += 1

    irreducible = ((0, 1), (1, 2), (0, 2))
    irreducible_checks = 0
    for relation_order in itertools.permutations(range(3)):
        for old_to_new in itertools.permutations(range(3)):
            transformed = tuple(
                tuple(old_to_new[index] for index in irreducible[relation])
                for relation in relation_order
            )
            plan = analyze_relation_supports(transformed, 3)
            assert not plan.applicable and plan.reason == "irreducible"
            irreducible_checks += 1

    formulation_a = {
        "variables": {"names": ["u", "v"]},
        "construction": [
            {"name": "A", "expr": "Point(u, 0)"},
            {"name": "B", "expr": "Point(v, 0)"},
            {"name": "A_alias", "expr": "A"},
        ],
        "constraints": [
            {"def": "Coordinate(A_alias)", "value": 1},
            {"def": "Distance(A_alias, B)", "value": 1},
        ],
        "guards": [],
    }
    formulation_b = {
        **formulation_a,
        "construction": [
            {"name": "B", "expr": "Point(v, 0)"},
            {"name": "A", "expr": "Point(u, 0)"},
            {"name": "A_alias", "expr": "Point(u, 0)"},
        ],
    }
    left = extract_v15_structure(formulation_a)
    right = extract_v15_structure(formulation_b)
    assert left.relation_supports == right.relation_supports
    assert signature(left.plan) == signature(right.plan)

    forward_reference = {
        "variables": {"names": ["x", "y"]},
        "construction": [
            {"name": "B", "expr": "Point(A, y)"},
            {"name": "A", "expr": "Point(x, 0)"},
        ],
        "constraints": [
            {"def": "Coordinate(A)", "value": 1},
            {"def": "Coordinate(B)", "value": 1},
        ],
        "guards": [],
    }
    forward_reference_failed_closed = False
    try:
        extract_v15_structure(forward_reference)
    except ValueError:
        forward_reference_failed_closed = True
    assert forward_reference_failed_closed

    seam_formulation = {
        "task": "solve",
        "variables": {"names": ["x", "y"]},
        "construction": [],
        "constraints": [
            {"def": "x", "value": 1},
            {"def": "y - x", "value": 1},
        ],
        "guards": [],
    }
    replay_calls = 0

    def original_fresh(_document, endpoints, *, hard_deadline):
        nonlocal replay_calls
        replay_calls += 1
        assert hard_deadline == 10.0
        return tuple(row for row in endpoints if row.get("point") == [1.0, 2.0])

    base = types.SimpleNamespace(
        _fresh_replay_candidates=original_fresh,
        _plan=lambda **kwargs: dict(kwargs),
    )
    audit = install(
        types.SimpleNamespace(BASE=base),
        proposal_factory=lambda *_args: ((1.0, 2.0),),
        mechanism_hash="metamorphic-generated",
    )
    accepted = base._fresh_replay_candidates(
        seam_formulation, ({"point": [0.0, 0.0]},), hard_deadline=10.0
    )
    assert accepted == ({"point": [1.0, 2.0]},)
    assert replay_calls == 1 and not audit()["source_replay_bypassed"]

    original = ({"point": [0.0, 0.0]},)
    merged, failure_audit = merge_block_proposals(
        seam_formulation,
        original,
        hard_deadline=10.0,
        proposal_factory=lambda *_args: (_ for _ in ()).throw(RuntimeError("counterexample")),
    )
    assert merged == original

    result = {
        "schema_version": "geotarget.exp-struct-001-metamorphic-s0/v1",
        "truth_materialized": False,
        "formal_screen_run": False,
        "decomposable": {
            "expected": expected,
            "residual_permutations_passed": residual_permutations,
            "variable_permutations_passed": variable_permutations,
            "combined_permutations_passed": combined_permutations,
        },
        "irreducible": {
            "permuted_fallback_checks_passed": irreducible_checks,
            "all_baseline_only": True,
        },
        "dag_reorder_cse": {
            "equivalent_supports": True,
            "equivalent_plan": True,
        },
        "detector_counterexamples": {
            "forward_reference_failed_closed": forward_reference_failed_closed,
            "proposal_factory_failure_preserved_original_endpoints": merged == original,
            "proposal_factory_failure_reason": failure_audit.get("proposal_skip_reason"),
        },
        "authority_seam": {
            "original_source_replay_calls": replay_calls,
            "generated_block_proposal_accepted_only_by_original_replay": True,
            "source_replay_bypassed": audit()["source_replay_bypassed"],
            "canonical_verifier_bypassed": audit()["canonical_verifier_bypassed"],
        },
    }
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
