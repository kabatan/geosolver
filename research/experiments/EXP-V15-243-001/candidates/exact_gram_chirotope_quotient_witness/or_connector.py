"""Candidate-private additive OR; baseline always retains at least 80%."""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any, Callable, Mapping

from candidate import attempt_source
from verifier import verify_source


SIDE_FRACTION = 0.20
BASELINE_MINIMUM_FRACTION = 0.80


def gram_or_baseline(
    *,
    source: Path,
    source_sha256: str,
    total_confirmation_seconds: float,
    baseline: Callable[[], Any],
    side_attempt: Callable[..., Mapping[str, Any]] = attempt_source,
) -> Any:
    # Baseline is first and unconditional, so this D0 side route cannot starve
    # it even if exact algebra unexpectedly becomes expensive.
    baseline_result = baseline()
    if (
        isinstance(baseline_result, Mapping)
        and baseline_result.get("authority_pass") is True
    ):
        return baseline_result
    witness = None
    try:
        if (
            isinstance(total_confirmation_seconds, (int, float))
            and not isinstance(total_confirmation_seconds, bool)
            and math.isfinite(float(total_confirmation_seconds))
            and total_confirmation_seconds >= 1.0
        ):
            candidate = side_attempt(source=source, source_sha256=source_sha256)
            if isinstance(candidate, Mapping) and candidate.get("authority_pass") is True:
                independent = verify_source(
                    source=source,
                    source_sha256=source_sha256,
                    certificate=candidate,
                )
                if independent.get("verified") is True:
                    witness = {**candidate, "independent_verification": independent}
    except Exception:  # noqa: BLE001 - additive side route is never terminal
        witness = None
    if witness is None:
        return baseline_result
    return {
        **witness,
        "attempt_kind": "EXACT_GRAM_CHIROTOPE_ADDITIVE_OR_AFTER_BASELINE_MISS",
        "baseline_result": baseline_result,
        "baseline_was_called": True,
        "budget": {
            "side_maximum_fraction": SIDE_FRACTION,
            "baseline_minimum_fraction": BASELINE_MINIMUM_FRACTION,
            "side_allocated_seconds": SIDE_FRACTION * float(total_confirmation_seconds),
            "baseline_reserved_seconds": BASELINE_MINIMUM_FRACTION * float(total_confirmation_seconds),
        },
    }


__all__ = ["BASELINE_MINIMUM_FRACTION", "SIDE_FRACTION", "gram_or_baseline"]
