"""Thin first-service Hermite OR before the current exact-coordinate confirmation."""

from __future__ import annotations

import hashlib
import math
import os
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from hard_child_runner import run_hard_child
from repair_adapter import _parse_descriptor


ARCHIVE_ROOT = Path(
    os.environ.get("GEOTARGET_ARCHIVE_RUNTIME_ROOT", "/home/kabatan/work/solver-experiment-runtime/solver")
).resolve()
EXACT_OUTER_WORKER = (
    ARCHIVE_ROOT
    / "research/experiments/EXP-V15-243-001/candidates/exact_outer_decorator/worker.py"
)
EXACT_OUTER_BOUNDARY = EXACT_OUTER_WORKER.with_name("authority_boundary.py")
EXPECTED_EXACT_OUTER_SHA256 = "05650c1016f3974c0f74845037c76604eb38f2f4a337cc700721f0e148d9d3f7"
EXPECTED_EXACT_OUTER_BOUNDARY_SHA256 = "a36520a416d0b8c900bca6b79192c7014812c9b1270be09248347f0f19e167e9"
HERMITE_BUDGET_FRACTION = 0.20
MAXIMUM_HERMITE_SECONDS = 3.0
MINIMUM_HERMITE_SECONDS = 0.50
MINIMUM_BASELINE_FRACTION = 0.75
CURRENT_EXACT_MINIMUM_SECONDS = 7.0


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _current_outer_pinned() -> bool:
    return bool(
        EXACT_OUTER_WORKER.is_file()
        and EXACT_OUTER_BOUNDARY.is_file()
        and _sha256(EXACT_OUTER_WORKER) == EXPECTED_EXACT_OUTER_SHA256
        and _sha256(EXACT_OUTER_BOUNDARY) == EXPECTED_EXACT_OUTER_BOUNDARY_SHA256
    )


def _ordinary_eligible(route_kind: str, ordinary: object) -> bool:
    if (
        route_kind != "ordinary-exact-outer"
        or not isinstance(ordinary, Mapping)
        or ordinary.get("status") != "TARGET_AUTHORITY_READY"
        or ordinary.get("authority_pass") is not True
        or not isinstance(ordinary.get("descriptor"), Mapping)
    ):
        return False
    try:
        _parse_descriptor(ordinary["descriptor"])
    except Exception:  # noqa: BLE001 - malformed descriptor is baseline-only
        return False
    return True


def _baseline_authority(result: object) -> bool:
    return bool(
        isinstance(result, Mapping)
        and result.get("status") == "TARGET_AUTHORITY_READY"
        and result.get("authority_pass") is True
        and isinstance(result.get("descriptor"), Mapping)
    )


def hermite_or_existing_exact_coordinate(
    *,
    route_kind: str,
    ordinary: Mapping[str, Any] | None,
    source: Path,
    source_sha256: str,
    endpoint: Sequence[Any],
    cpu: int,
    output_dir: Path,
    confirmation_budget_seconds: float,
    existing_exact_coordinate: Callable[[], Any],
    child_runner: Callable[..., Mapping[str, Any]] = run_hard_child,
) -> Any:
    """Reserve 20% first-service, then always run the untouched baseline.

    The callback is the current exact_outer confirmation route. Its returned
    object is returned by identity on every ineligible/failure path and also
    wins when both independent authorities pass.
    """

    hermite = None
    side_seconds = 0.0
    try:
        if (
            _current_outer_pinned()
            and _ordinary_eligible(route_kind, ordinary)
            and isinstance(confirmation_budget_seconds, (int, float))
            and not isinstance(confirmation_budget_seconds, bool)
            and math.isfinite(float(confirmation_budget_seconds))
            and confirmation_budget_seconds > 0.0
        ):
            side_seconds = min(
                MAXIMUM_HERMITE_SECONDS,
                HERMITE_BUDGET_FRACTION * float(confirmation_budget_seconds),
            )
            baseline_fraction = 1.0 - side_seconds / float(confirmation_budget_seconds)
            if (
                side_seconds >= MINIMUM_HERMITE_SECONDS
                and baseline_fraction >= MINIMUM_BASELINE_FRACTION
                and float(confirmation_budget_seconds) - side_seconds
                >= CURRENT_EXACT_MINIMUM_SECONDS
            ):
                child = child_runner(
                    source=source,
                    source_sha256=source_sha256,
                    descriptor=ordinary["descriptor"],
                    endpoint=endpoint,
                    output_dir=output_dir / "target-hermite-repair-b",
                    cpu=cpu,
                    side_seconds=side_seconds,
                )
                candidate = child.get("authority") if isinstance(child, Mapping) else None
                if isinstance(candidate, Mapping) and candidate.get("authority_pass") is True:
                    hermite = dict(candidate)
    except Exception:  # noqa: BLE001 - no Hermite error crosses baseline seam
        hermite = None

    # This is deliberately outside the Hermite try block: original exception
    # behaviour and the exact returned object are preserved.
    baseline = existing_exact_coordinate()
    if hermite is None or _baseline_authority(baseline):
        return baseline
    return {
        **hermite,
        "attempt_kind": "TARGET_HERMITE_REPAIR_B_AFTER_EXACT_COORDINATE_CONFIRMATION_MISS",
        "ordinary_hp_proposal": dict(ordinary),
        "existing_exact_coordinate_result": baseline,
        "ordinary_descriptor_is_final_authority": False,
        "existing_exact_coordinate_was_called": True,
        "ordinary_and_hermite_descriptor_identity_match": True,
        "confirmation_budget": {
            "total_seconds": float(confirmation_budget_seconds),
            "hermite_allocated_seconds": side_seconds,
            "hermite_fraction": side_seconds / float(confirmation_budget_seconds),
            "baseline_minimum_fraction": 1.0 - side_seconds / float(confirmation_budget_seconds),
        },
        "case_family_truth_target_or_outcome_routing": False,
    }


__all__ = [
    "HERMITE_BUDGET_FRACTION",
    "MINIMUM_BASELINE_FRACTION",
    "hermite_or_existing_exact_coordinate",
]
