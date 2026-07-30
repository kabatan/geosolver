from __future__ import annotations

from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import sys


HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from interval_rescue import (  # noqa: E402
    Problem,
    RescueConfig,
    Var,
    discover,
    portfolio_plan,
    unsupported,
)


def _row(name: str, problem: Problem, config: RescueConfig = RescueConfig()) -> dict[str, object]:
    result = discover(problem, config)
    plan = portfolio_plan(result, config)
    return {
        "fixture": name,
        "status": result.status,
        "reason": result.reason,
        "applicable": result.applicability.applicable,
        "proposal_count": len(result.proposals),
        "boxes_visited": result.boxes_visited,
        "boxes_excluded": result.boxes_excluded,
        "boxes_split": result.boxes_split,
        "singular_midpoints": result.singular_midpoints,
        "krawczyk_attempts": result.krawczyk_attempts,
        "answer_promotions": result.answer_promotions,
        "baseline_slots": plan.baseline_slots,
        "interval_slots": plan.interval_slots,
        "minimum_baseline_slots": plan.minimum_baseline_slots,
        "proposal_contracts": [
            {
                "authority": proposal.authority,
                "requires_local_solver": proposal.requires_local_solver,
                "requires_canonical_source_replay": proposal.requires_canonical_source_replay,
            }
            for proposal in result.proposals
        ],
    }


def main() -> None:
    x, y = Var(0), Var(1)
    rows = [
        _row("regular-unique-1d", Problem((x**2 - 2.0,), ((1.0, 2.0),))),
        _row(
            "regular-unique-coupled-2d",
            Problem((x + y - 3.0, x - y - 1.0), ((1.5, 2.5), (0.5, 1.5))),
        ),
        _row(
            "singular-root",
            Problem((x**2,), ((-0.25, 0.25),)),
            RescueConfig(max_boxes=15, max_depth=4),
        ),
        _row("nonunique-manifold", Problem((x + y,), ((-1.0, 1.0), (-1.0, 1.0)))),
        _row(
            "root-on-box-boundary",
            Problem((x,), ((0.0, 1.0),)),
            RescueConfig(max_boxes=15, max_depth=4),
        ),
        _row(
            "strict-guard-boundary",
            Problem((x,), ((0.0, 1.0),), strict_guard_state="boundary"),
        ),
        _row("transcendental", Problem((unsupported("sin", x),), ((-1.0, 1.0),))),
        _row("branch-crossing", Problem((x,), ((-1.0, 1.0),), branch_state="crossing")),
        _row("opaque-callback", Problem((x,), ((-1.0, 1.0),), opaque_callbacks=True)),
        _row(
            "hard-box-cap",
            Problem((x**2,), ((-0.25, 0.25),)),
            RescueConfig(max_boxes=3, max_depth=20),
        ),
    ]
    source = (HERE / "interval_rescue.py").read_bytes()
    payload = {
        "schema": "geotarget.exp-interval-001-generated-s0/v1",
        "mechanism_sha256": hashlib.sha256(source).hexdigest(),
        "formal_dataset_used": False,
        "truth_or_scorer_used": False,
        "canonical_source_replay_changed": False,
        "exact_descriptor_authority_changed": False,
        "default_config": asdict(RescueConfig()),
        "rows": rows,
        "summary": {
            "fixtures": len(rows),
            "eligible_unique_with_proposal": sum(
                row["proposal_count"] > 0 for row in rows[:2]
            ),
            "singular_nonunique_boundary_proposals": sum(
                row["proposal_count"] for row in rows[2:6]
            ),
            "unsupported_boxes_visited": sum(row["boxes_visited"] for row in rows[6:9]),
            "answer_promotions": sum(row["answer_promotions"] for row in rows),
            "minimum_baseline_quota_violations": sum(
                row["baseline_slots"] < row["minimum_baseline_slots"] for row in rows
            ),
        },
    }
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
