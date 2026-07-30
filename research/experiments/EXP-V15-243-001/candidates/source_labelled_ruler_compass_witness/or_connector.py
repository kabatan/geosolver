"""Baseline-first, candidate-private ruler-compass additive OR."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Mapping

from candidate import attempt_source
from verifier import verify_source


def ruler_compass_or_baseline(
    *, source: Path, source_sha256: str, baseline: Callable[[], Any], side_attempt=attempt_source
) -> Any:
    baseline_result = baseline()
    if isinstance(baseline_result, Mapping) and baseline_result.get("authority_pass") is True:
        return baseline_result
    try:
        candidate = side_attempt(source=source, source_sha256=source_sha256)
        if candidate.get("authority_pass") is not True:
            return baseline_result
        independent = verify_source(source=source, source_sha256=source_sha256, certificate=candidate)
        if independent.get("verified") is not True:
            return baseline_result
        return {
            **candidate,
            "independent_verification": independent,
            "baseline_result": baseline_result,
            "baseline_was_called_first": True,
            "budget": {"baseline_minimum_fraction": 0.80, "side_maximum_fraction": 0.20},
        }
    except Exception:  # noqa: BLE001
        return baseline_result


__all__ = ["ruler_compass_or_baseline"]
