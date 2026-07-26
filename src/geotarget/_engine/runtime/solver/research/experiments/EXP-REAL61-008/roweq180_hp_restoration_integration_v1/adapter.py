"""Minimal roweq180 numerical-v3 -> leftover restoration composition.

The caller has already run the unchanged roweq180 discovery and the frozen
undamped-first -> target-first numerical-v3 policy on an endpoint.  This seam
only receives endpoints whose authority artifacts are available.  A failed,
semantic-safe, low-residual endpoint may enter the existing at-most-once aged
queue.  Service uses only wall time and Float64 callbacks explicitly handed
to the seam as leftover work.

The source document and coordinates are never transformed.  In particular,
this module introduces no bounds, clipping, gauge, symmetry reduction,
variable/equation change, or case/family/truth routing.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import math
from pathlib import Path
import struct
import sys
import time
from typing import Mapping, Sequence

import numpy as np


HERE = Path(__file__).resolve().parent
EXP008 = HERE.parent
ROOT = HERE.parents[3]
SOURCE_ONLY = EXP008 / "source_only"
RESCUE_PATH = EXP008 / "hp_failure_restoration_rescue_v6/candidate.py"
HP_PATH = EXP008 / "hp_target_first_fallback_integration_v1/adapter.py"
RUNTIME_PATH = SOURCE_ONLY / "runtime.py"
REPLAY_PATH = SOURCE_ONLY / "replay.py"

MIN_LEFTOVER_SECONDS = 0.03
MAX_RESTORATION_WALL_SECONDS = 3.0
RESTORED_ENDPOINT_REPLAY_CHARGE = 1

for path in (ROOT, SOURCE_ONLY):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))


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


RESCUE = _module("geotarget_exp008_roweq180_hp_restoration_rescue", RESCUE_PATH)
HP = _module("geotarget_exp008_roweq180_hp_restoration_authority", HP_PATH)
RUNTIME = _module("geotarget_exp008_roweq180_hp_restoration_runtime", RUNTIME_PATH)
REPLAY = _module("geotarget_exp008_roweq180_hp_restoration_replay", REPLAY_PATH)


def endpoint_sha256(endpoint: Sequence[float]) -> str:
    values = tuple(float(value) for value in endpoint)
    payload = struct.pack(">I", len(values)) + b"".join(
        struct.pack(">d", value) for value in values
    )
    return hashlib.sha256(payload).hexdigest()


def _final_result(authority_artifact: Mapping[str, object]) -> Mapping[str, object] | None:
    nested = authority_artifact.get("final_result")
    if isinstance(nested, Mapping):
        return nested
    if authority_artifact.get("schema_version") == "geotarget.exp008-dev41-target-hp-adapter/v1":
        return authority_artifact
    return None


class AgedRestorationAuthoritySeam:
    """Stateful, outcome-blind continuation for one untouched solve source."""

    def __init__(
        self,
        source_payload: bytes,
        expected_source_sha256: str,
        *,
        leftover_callback_cap: int,
        deadline_monotonic: float,
    ) -> None:
        observed = hashlib.sha256(source_payload).hexdigest()
        if observed != expected_source_sha256:
            raise ValueError("source digest mismatch")
        try:
            document = json.loads(source_payload)
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise ValueError("source is not canonical JSON") from error
        if not isinstance(document, dict) or document.get("task") != "solve":
            raise ValueError("untouched solve source required")
        if not isinstance(leftover_callback_cap, int) or leftover_callback_cap < 0:
            raise ValueError("leftover callback cap must be a nonnegative integer")
        if not math.isfinite(deadline_monotonic):
            raise ValueError("leftover deadline must be finite")

        self._source_payload = bytes(source_payload)
        self._source_sha256 = expected_source_sha256
        self._document = document
        self._leftover_callback_cap = int(leftover_callback_cap)
        self._leftover_callbacks_used = 0
        self._deadline = float(deadline_monotonic)
        self._queue = RESCUE.AgingRescueQueue()

    @property
    def pending(self) -> int:
        return len(self._queue)

    @property
    def leftover_callbacks_remaining(self) -> int:
        return max(0, self._leftover_callback_cap - self._leftover_callbacks_used)

    def enqueue(
        self,
        *,
        endpoint: Sequence[float],
        endpoint_sha256_value: str,
        authority_artifact: Mapping[str, object],
        tick: int,
    ):
        values = tuple(float(value) for value in endpoint)
        if endpoint_sha256(values) != endpoint_sha256_value:
            raise ValueError("endpoint digest mismatch")
        final = _final_result(authority_artifact)
        if final is None:
            return RESCUE.TriggerDecision(False, "malformed_authority_artifact", None, ())
        if final.get("source_raw_sha256") != self._source_sha256:
            raise ValueError("authority/source digest mismatch")
        if final.get("endpoint_float64_sha256") != endpoint_sha256_value:
            raise ValueError("authority/endpoint digest mismatch")
        return self._queue.enqueue(
            source_sha256=self._source_sha256,
            endpoint_sha256=endpoint_sha256_value,
            endpoint=values,
            authority_artifact=authority_artifact,
            tick=int(tick),
        )

    def service_oldest(self, *, tick: int) -> dict[str, object]:
        """Serve one queued item without consuming non-leftover work."""

        wall_remaining = self._deadline - time.monotonic()
        callbacks_remaining = self.leftover_callbacks_remaining
        if self.pending == 0:
            return self._result("NO_ELIGIBLE_HP_FAILURE")
        if callbacks_remaining < 2 or wall_remaining < MIN_LEFTOVER_SECONDS:
            return self._result("LEFTOVER_NOT_AVAILABLE")

        popped = self._queue.pop(tick=int(tick))
        if popped is None:
            return self._result("NO_ELIGIBLE_HP_FAILURE")
        item, service_age = popped

        restoration_deadline = min(
            self._deadline,
            time.monotonic() + MAX_RESTORATION_WALL_SECONDS,
        )
        base_case, budget, evaluator = RUNTIME.build_source_case(
            self._document,
            callback_cap=callbacks_remaining,
            deadline=restoration_deadline,
        )
        rescue = RESCUE.run_restoration_rescue(
            base_case=base_case,
            budget=budget,
            document=self._document,
            failed_endpoint=item.endpoint,
            leftover_callback_cap=callbacks_remaining,
            deadline_monotonic=restoration_deadline,
        )
        self._leftover_callbacks_used += int(rescue.callbacks)

        validations: list[dict[str, object]] = []
        selected: list[float] | None = None
        for endpoint_out in rescue.endpoints:
            if (
                self.leftover_callbacks_remaining < RESTORED_ENDPOINT_REPLAY_CHARGE
                or time.monotonic() >= self._deadline
            ):
                break
            replay = REPLAY.replay_endpoint(evaluator, endpoint_out, precision=80)
            self._leftover_callbacks_used += RESTORED_ENDPOINT_REPLAY_CHARGE
            validations.append(replay)
            if replay.get("safe") is True:
                selected = [float(value) for value in endpoint_out]
                break

        restored_authority = None
        restored_endpoint_sha256 = None
        hp_wall_remaining = self._deadline - time.monotonic()
        if selected is not None and hp_wall_remaining >= MIN_LEFTOVER_SECONDS:
            restored_endpoint_sha256 = endpoint_sha256(selected)
            restored_authority = HP.build_target_authority_with_fallback(
                self._source_payload,
                self._source_sha256,
                selected,
                deadline_seconds=hp_wall_remaining,
                primary_cap_seconds=HP.DEFAULT_PRIMARY_CAP_SECONDS,
            )

        authority_pass = bool(
            isinstance(restored_authority, Mapping)
            and restored_authority.get("authority_pass") is True
        )
        return {
            **self._result(
                "RESTORED_TARGET_AUTHORITY_READY"
                if authority_pass
                else "RESTORATION_SERVED_NO_AUTHORITY"
            ),
            "served": {
                "endpoint_sha256": item.endpoint_sha256,
                "service_age": int(service_age),
                "residual_inf": item.residual_inf,
            },
            "restoration": {
                "callbacks": int(rescue.callbacks),
                "proposals_started": int(rescue.proposals_started),
                "statuses": dict(rescue.statuses),
                "counters": dict(rescue.counters),
                "validation_count": len(validations),
                "selected_restored_endpoint_sha256": restored_endpoint_sha256,
            },
            "restored_authority": restored_authority,
            "authority_pass": authority_pass,
        }

    def _result(self, status: str) -> dict[str, object]:
        return {
            "schema_version": "geotarget.exp008-roweq180-hp-restoration-composition/v1",
            "status": status,
            "pending": self.pending,
            "leftover": {
                "callbacks_supplied": self._leftover_callback_cap,
                "callbacks_used": self._leftover_callbacks_used,
                "callbacks_remaining": self.leftover_callbacks_remaining,
                "wall_seconds_remaining": max(0.0, self._deadline - time.monotonic()),
                "default_or_primary_hp_callbacks_reserved_or_replaced": False,
                "default_or_primary_hp_wall_reserved_or_replaced": False,
            },
            "problem_contract": {
                "source_or_problem_modified": False,
                "variables_or_equations_changed": False,
                "bounds_added_or_inferred": False,
                "gauge_or_symmetry_reduction": False,
                "coordinate_reparameterization": False,
                "case_family_source_series_truth_target_count_routing": False,
            },
        }


def mechanism_manifest() -> Mapping[str, object]:
    return {
        "name": "roweq180_numerical_v3_then_hp_failure_restoration_v1",
        "primary": "unchanged roweq180 -> undamped-first -> target-first numerical-v3",
        "supplement": RESCUE.mechanism_manifest(),
        "trigger": "eligible completed HP authority failure only",
        "queue": "at-most-once oldest-age-first",
        "maximum_restoration_wall_seconds": MAX_RESTORATION_WALL_SECONDS,
        "restored_endpoint_policy": "first original-evaluator semantic-safe endpoint",
        "restored_hp_policy": "undamped-first then target-first on failure",
        "caller_supplies_leftover_callbacks_and_wall_only": True,
        "source_or_problem_modified": False,
        "bounds_added_or_inferred": False,
        "gauge_or_symmetry_reduction": False,
        "case_family_truth_target_count_routing": False,
    }


__all__ = [
    "AgedRestorationAuthoritySeam",
    "MAX_RESTORATION_WALL_SECONDS",
    "MIN_LEFTOVER_SECONDS",
    "endpoint_sha256",
    "mechanism_manifest",
]
