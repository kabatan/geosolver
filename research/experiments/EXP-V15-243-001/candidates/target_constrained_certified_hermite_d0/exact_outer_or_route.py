"""Dry/source-generated OR seam ahead of the unchanged exact_outer fallback."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from repair_adapter import attempt_repair


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


class OrRouteFailure(RuntimeError):
    pass


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_outer_pins() -> None:
    if (
        not EXACT_OUTER_WORKER.is_file()
        or not EXACT_OUTER_BOUNDARY.is_file()
        or _sha256(EXACT_OUTER_WORKER) != EXPECTED_EXACT_OUTER_SHA256
        or _sha256(EXACT_OUTER_BOUNDARY) != EXPECTED_EXACT_OUTER_BOUNDARY_SHA256
    ):
        raise OrRouteFailure("current exact_outer digest changed")


def repair_or_unchanged_fallback(
    *,
    route_kind: str,
    ordinary: Mapping[str, Any] | None,
    source: Path,
    source_sha256: str,
    endpoint: Sequence[Any],
    unchanged_fallback: Callable[[], Any],
    deadline_monotonic: float | None = None,
) -> Any:
    """Use Hermite only as an additive proof OR; fallback is byte/object unchanged."""

    verify_outer_pins()
    if (
        route_kind != "ordinary-exact-outer"
        or not isinstance(ordinary, Mapping)
        or ordinary.get("authority_pass") is not True
        or ordinary.get("status") != "TARGET_AUTHORITY_READY"
        or not isinstance(ordinary.get("descriptor"), Mapping)
    ):
        return unchanged_fallback()
    try:
        repaired = attempt_repair(
            source=source,
            source_sha256=source_sha256,
            descriptor=ordinary["descriptor"],
            endpoint=endpoint,
            deadline_monotonic=deadline_monotonic,
        )
    except Exception:  # noqa: BLE001 - never let a candidate exception cross the OR seam
        return unchanged_fallback()
    if repaired.get("authority_pass") is not True:
        return unchanged_fallback()
    return {
        **repaired,
        "attempt_kind": "TARGET_HERMITE_REPAIR_OF_ORDINARY_PROPOSAL",
        "ordinary_hp_proposal": dict(ordinary),
        "ordinary_descriptor_is_final_authority": False,
        "ordinary_and_hermite_descriptor_identity_match": True,
        "zero_dimensional_route_logic_changed": False,
        "ordinary_fallback_logic_changed": False,
        "baseline_quota_changed": False,
    }


__all__ = ["repair_or_unchanged_fallback", "verify_outer_pins"]
