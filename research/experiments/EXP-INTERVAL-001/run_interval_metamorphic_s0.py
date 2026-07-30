from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys


HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from interval_rescue import Problem, Var, discover  # noqa: E402


def _run(problem: Problem, map_back=lambda point: point):
    result = discover(problem)
    if not result.applicability.applicable or len(result.proposals) != 1:
        return None, False
    proposal = result.proposals[0]
    contract = (
        proposal.authority is False
        and proposal.requires_local_solver
        and proposal.requires_canonical_source_replay
        and result.answer_promotions == 0
    )
    return tuple(map_back(proposal.point)), contract


def _matches(left, right) -> bool:
    return left is not None and right is not None and max(
        abs(a - b) for a, b in zip(left, right, strict=True)
    ) < 1.0e-10


def main() -> None:
    x, y = Var(0), Var(1)
    base = Problem((x + y - 3.0, x - y - 1.0), ((1.5, 2.5), (0.5, 1.5)))
    baseline, baseline_contract = _run(base)

    y0, x1 = Var(0), Var(1)
    variable_swap = Problem(
        (x1 + y0 - 3.0, x1 - y0 - 1.0),
        ((0.5, 1.5), (1.5, 2.5)),
    )
    x, y = Var(0), Var(1)
    residual_swap = Problem(
        (x - y - 1.0, x + y - 3.0),
        ((1.5, 2.5), (0.5, 1.5)),
    )
    u, v = Var(0), Var(1)
    affine_x, affine_y = -2.0 * u + 4.0, 0.5 * v + 0.5
    affine = Problem(
        (
            -3.0 * (affine_x + affine_y - 3.0),
            0.25 * (affine_x - affine_y - 1.0),
        ),
        ((0.75, 1.25), (0.0, 2.0)),
    )
    x, y = Var(0), Var(1)
    reordered = Problem(
        ((y - 3.0) + x, (-y - 1.0) + x),
        ((1.5, 2.5), (0.5, 1.5)),
    )
    shared = x + y
    cse = Problem(
        (shared - 3.0, ((x + x) - shared) - 1.0),
        ((1.5, 2.5), (0.5, 1.5)),
    )
    families = {
        "variable_permutation": (
            (variable_swap, lambda point: (point[1], point[0])),
        ),
        "residual_permutation": ((residual_swap, lambda point: point),),
        "affine_coordinate_and_residual_scale": (
            (
                affine,
                lambda point: (-2.0 * point[0] + 4.0, 0.5 * point[1] + 0.5),
            ),
        ),
        "dag_reorder_and_cse": (
            (reordered, lambda point: point),
            (cse, lambda point: point),
        ),
    }
    aggregate = {}
    total_variants = mismatches = contract_failures = 0
    for family, variants in families.items():
        family_mismatches = family_contract_failures = 0
        for problem, map_back in variants:
            point, contract = _run(problem, map_back)
            family_mismatches += int(not _matches(baseline, point))
            family_contract_failures += int(not contract)
        aggregate[family] = {
            "variants": len(variants),
            "proposal_mismatches": family_mismatches,
            "authority_contract_failures": family_contract_failures,
        }
        total_variants += len(variants)
        mismatches += family_mismatches
        contract_failures += family_contract_failures
    mechanism = (HERE / "interval_rescue.py").read_bytes()
    print(
        json.dumps(
            {
                "schema": "geotarget.exp-interval-001-metamorphic-s0/v1",
                "mechanism_sha256": hashlib.sha256(mechanism).hexdigest(),
                "formal_dataset_used": False,
                "truth_or_scorer_used": False,
                "baseline_proposal_available": baseline is not None,
                "baseline_authority_contract_pass": baseline_contract,
                "families": aggregate,
                "summary": {
                    "variants": total_variants,
                    "proposal_mismatches": mismatches,
                    "authority_contract_failures": contract_failures,
                    "answer_promotions": 0,
                },
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
