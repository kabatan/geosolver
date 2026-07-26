"""Outcome-blind undamped-first -> shared-HP authority composition.

The fallback trigger observes only whether the frozen undamped-first attempt
produced target authority and whether wall-clock budget remains.  It never
receives problem identity, family, truth, a known target count, or prior
benchmark outcomes.  Both attempts use the same untouched source bytes and
bare Float64 endpoint through the same original-DSL/intrinsic-domain authority
adapter.
"""

from __future__ import annotations

from dataclasses import replace
import importlib.util
import math
from pathlib import Path
import sys
import time
from typing import Sequence


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
PRIMARY_ADAPTER_PATH = HERE.parent / "dev41_target_hp_adapter/adapter.py"
FALLBACK_CANDIDATE_PATH = HERE.parent / "hp_target_first_shared_v1/candidate.py"

DEFAULT_PRIMARY_CAP_SECONDS = 23.0
MIN_FALLBACK_BUDGET_SECONDS = 0.03


def _module(name: str, path: Path):
    cached = sys.modules.get(name)
    if cached is not None:
        observed = Path(getattr(cached, "__file__", "")).resolve()
        if observed != path.resolve():
            raise RuntimeError(f"module path mismatch for {name}")
        return cached
    specification = importlib.util.spec_from_file_location(name, path)
    if specification is None or specification.loader is None:
        raise ImportError(path)
    module = importlib.util.module_from_spec(specification)
    sys.modules[name] = module
    specification.loader.exec_module(module)
    return module


PRIMARY = _module(
    "geotarget_exp008_target_first_fallback_primary_adapter",
    PRIMARY_ADAPTER_PATH,
)
FALLBACK = _module(
    "geotarget_exp008_target_first_fallback_candidate",
    FALLBACK_CANDIDATE_PATH,
)


def _attempt_summary(name: str, result: dict[str, object], elapsed: float):
    return {
        "name": name,
        "attempted": True,
        "authority_pass": result.get("authority_pass") is True,
        "status": result.get("status"),
        "source_raw_sha256": result.get("source_raw_sha256"),
        "endpoint_float64_sha256": result.get("endpoint_float64_sha256"),
        "elapsed_seconds": elapsed,
    }


def build_target_authority_with_fallback(
    source_payload: bytes,
    expected_source_sha256: str,
    endpoint: Sequence[object],
    *,
    deadline_seconds: float = 46.0,
    primary_cap_seconds: float = DEFAULT_PRIMARY_CAP_SECONDS,
) -> dict[str, object]:
    """Run the shared corrective iff primary authority fails with time left."""

    if not math.isfinite(deadline_seconds) or deadline_seconds <= 0:
        raise PRIMARY.AdapterInputError("deadline must be finite and positive")
    if not math.isfinite(primary_cap_seconds) or primary_cap_seconds <= 0:
        raise PRIMARY.AdapterInputError("primary cap must be finite and positive")

    started = time.monotonic()
    deadline = started + float(deadline_seconds)
    primary_started = time.monotonic()
    primary_budget = min(float(primary_cap_seconds), max(0.03, deadline - primary_started))
    primary = PRIMARY.build_target_authority(
        source_payload,
        expected_source_sha256,
        endpoint,
        deadline_seconds=primary_budget,
    )
    attempts = [
        _attempt_summary(
            "FROZEN_UNDAMPED_FIRST",
            primary,
            time.monotonic() - primary_started,
        )
    ]

    # This is the complete runtime decision.  In particular, status subtype,
    # case/source identity, target value, and benchmark history are not read.
    remaining = deadline - time.monotonic()
    fallback_eligible = bool(
        primary.get("authority_pass") is not True
        and remaining >= MIN_FALLBACK_BUDGET_SECONDS
    )
    fallback = None
    if fallback_eligible:
        fallback_started = time.monotonic()
        runtime = replace(PRIMARY._load_runtime(), candidate=FALLBACK)
        fallback_budget = deadline - time.monotonic()
        fallback_eligible = fallback_budget >= MIN_FALLBACK_BUDGET_SECONDS
        if fallback_eligible:
            fallback = PRIMARY._build_with_runtime(
                source_payload,
                expected_source_sha256,
                endpoint,
                deadline_seconds=fallback_budget,
                runtime=runtime,
            )
            attempts.append(
                _attempt_summary(
                    "TARGET_FIRST_SHARED_HP_CONTINUATION_ACCEPTED_FIRST",
                    fallback,
                    time.monotonic() - fallback_started,
                )
            )

    if primary.get("authority_pass") is True:
        winner = "FROZEN_UNDAMPED_FIRST"
        final = primary
    elif isinstance(fallback, dict) and fallback.get("authority_pass") is True:
        winner = "TARGET_FIRST_SHARED_HP_CONTINUATION_ACCEPTED_FIRST"
        final = fallback
    else:
        winner = None
        final = fallback if isinstance(fallback, dict) else primary

    return {
        "schema_version": "geotarget.exp008-target-first-fallback-composition/v1",
        "status": final.get("status"),
        "authority_pass": final.get("authority_pass") is True,
        "winner": winner,
        "final_result": final,
        "attempts": attempts,
        "fallback_decision": {
            "primary_authority_failed": primary.get("authority_pass") is not True,
            "remaining_budget_sufficient": fallback_eligible,
            "fallback_eligible": fallback_eligible,
            "case_identity_read": False,
            "family_read": False,
            "truth_read": False,
            "known_target_count_read": False,
            "failure_status_subtype_read": False,
        },
        "input_contract": {
            "same_source_bytes_both_attempts": True,
            "same_float64_endpoint_both_attempts": True,
            "source_or_problem_modified": False,
            "bounds_added": False,
            "gauge_or_symmetry_reduction": False,
        },
        "deadline_seconds": float(deadline_seconds),
        "primary_cap_seconds": float(primary_cap_seconds),
        "elapsed_seconds": time.monotonic() - started,
    }


__all__ = [
    "DEFAULT_PRIMARY_CAP_SECONDS",
    "MIN_FALLBACK_BUDGET_SECONDS",
    "build_target_authority_with_fallback",
]
