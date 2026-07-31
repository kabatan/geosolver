"""Disposable 75/25 portal splice for the frozen champion search loop."""

from __future__ import annotations

from collections import Counter
from dataclasses import is_dataclass, replace
import hashlib
import json
import math
from pathlib import Path
import time
from types import SimpleNamespace
from typing import Callable, Mapping, Sequence

import numpy as np


PORTAL_SCHEMA = "geotarget.guard-relative-merge-tree-portal-repair/v1"


def _phase_ordinals(
    count: int,
) -> tuple[tuple[int, ...], tuple[int, ...], tuple[int, ...]]:
    # Infer once after the first complete 3:1 block.  Ordinal three is a
    # non-insurance start; every period-four Cauchy insurance ordinal remains
    # in pilot or resume baseline.
    pilot_count = min(3, count)
    pilot = tuple(range(pilot_count))
    fallback = tuple(range(pilot_count, count))
    resume = tuple(range(4, count)) if count >= 4 else ()
    return pilot, fallback, resume


def _prefix_slice(prefix: object, ordinals: Sequence[int]) -> object:
    points = tuple(prefix.points[index] for index in ordinals)
    if is_dataclass(prefix):
        updates: dict[str, object] = {"points": points}
        for name in ("sources", "scale_exponents"):
            value = getattr(prefix, name, None)
            if isinstance(value, tuple) and len(value) == len(prefix.points):
                updates[name] = tuple(value[index] for index in ordinals)
        return replace(prefix, **updates)
    return SimpleNamespace(points=points)


def _merge_outcomes(
    first: object,
    second: object,
    *,
    lane_offset: int,
    first_lane_extra: int = 0,
    status_extra: Mapping[str, int] | None = None,
    counter_extra: Mapping[str, int] | None = None,
) -> object:
    statuses: Counter[str] = Counter(getattr(first, "statuses"))
    statuses.update(getattr(second, "statuses"))
    statuses.update(status_extra or {})
    counters: Counter[str] = Counter(getattr(first, "counters"))
    counters.update(getattr(second, "counters"))
    counters.update(counter_extra or {})
    endpoints = tuple(getattr(first, "endpoints")) + tuple(
        (int(lane) + lane_offset, np.asarray(point, dtype=float).copy())
        for lane, point in getattr(second, "endpoints")
    )
    second_callbacks = list(getattr(second, "lane_callbacks"))
    if first_lane_extra:
        if second_callbacks:
            second_callbacks[0] += int(first_lane_extra)
        else:
            second_callbacks.append(int(first_lane_extra))
    return type(first)(
        endpoints=endpoints,
        statuses=dict(statuses),
        counters=dict(counters),
        lane_callbacks=tuple(getattr(first, "lane_callbacks"))
        + tuple(second_callbacks),
    )


class PortalRuntime:
    """Own the same in-process pool and splice one portal start after 75%."""

    def __init__(
        self,
        *,
        collector: object,
        candidate: object,
        point_key: Callable[[np.ndarray], bytes],
        global_gate: Mapping[str, object],
    ) -> None:
        if (
            global_gate.get("global_dynamic_gate_pass") is not True
            or global_gate.get("decision")
            != "ROOT_COLLECT_SCREEN24_SEED0_DYNAMIC_GATE_PASS"
        ):
            raise SystemExit("frozen global dynamic gate is not PASS")
        self.collector = collector
        self.candidate = candidate
        self.point_key = point_key
        self.global_gate = dict(global_gate)
        self.summary: dict[str, object] = {
            "mode": "NOT_RUN",
            "portal_activated": False,
            "individual_observations_emitted": False,
        }

    def _mark_endpoints(self, endpoints: Sequence[tuple[int, np.ndarray]]) -> int:
        keys = {self.point_key(np.asarray(point, dtype=float)) for _lane, point in endpoints}
        marked = 0
        for row in self.collector._rows:
            if self.point_key(np.asarray(row["point"], dtype=float)) in keys:
                row["endpoint"] = True
                marked += 1
        return marked

    def _pool(self) -> Mapping[str, object]:
        case = self.collector.case
        if case is None:
            raise self.candidate.GateUnknown("SOURCE_CASE_WAS_NOT_BUILT")
        scales = np.asarray(case.scales, dtype=float).reshape(-1)
        if (
            scales.shape != (int(case.dimension),)
            or not np.all(np.isfinite(scales))
            or not np.all(scales > 0.0)
        ):
            raise self.candidate.GateUnknown("INVALID_DIMENSIONLESS_SCALE")
        return {
            "anonymous_source_hash": self.collector.source_sha256,
            "dimension": int(case.dimension),
            "scale": [float(value) for value in scales],
            "typed_guard_complete": bool(
                self.collector.typed_guard_complete
                and not self.collector.accounting_mismatch
            ),
            "guard_count": int(self.collector.guard_count),
            "typed_guard_count": int(self.collector.guard_count),
            "observations": self.collector._rows,
        }

    def _proposal(self, endpoints: Sequence[tuple[int, np.ndarray]]):
        marked = self._mark_endpoints(endpoints)
        try:
            pool = self._pool()
            proposal = self.candidate.select_portal(
                pool,
                {"gate_pass": True, "decision": "DYNAMIC_GATE_PASS"},
            )
        except (
            self.candidate.GateUnknown,
            KeyError,
            TypeError,
            ValueError,
            OverflowError,
        ) as error:
            return None, marked, f"{type(error).__name__}:{error}"
        if proposal is None:
            return None, marked, "NO_LOCAL_PORTAL"
        return proposal, marked, None

    def wrap_run_local_arm(self, original: Callable[..., object]):
        def run_local_arm(
            arm: str,
            *,
            base_case: object,
            budget: object,
            program: object,
            literal_prefix: object,
            callback_cap: int,
            callbacks_per_start: int,
            deadline_monotonic: float,
        ) -> object:
            points = tuple(literal_prefix.points)
            pilot_ordinals, fallback_ordinals, resume_ordinals = _phase_ordinals(
                len(points)
            )
            if len(points) < 4:
                self.summary = {
                    "mode": "FULL_BASELINE_NO_SIDE_QUOTA",
                    "portal_activated": False,
                    "individual_observations_emitted": False,
                }
                return original(
                    arm,
                    base_case=base_case,
                    budget=budget,
                    program=program,
                    literal_prefix=literal_prefix,
                    callback_cap=callback_cap,
                    callbacks_per_start=callbacks_per_start,
                    deadline_monotonic=deadline_monotonic,
                )

            begin = int(budget.callbacks)
            allocation = self.candidate.callback_allocation(
                max(0, int(callback_cap) - begin), portal_available=True
            )
            baseline_limit = begin + int(allocation["baseline_callbacks"])
            baseline = original(
                arm,
                base_case=base_case,
                budget=budget,
                program=program,
                literal_prefix=_prefix_slice(literal_prefix, pilot_ordinals),
                callback_cap=baseline_limit,
                callbacks_per_start=callbacks_per_start,
                deadline_monotonic=deadline_monotonic,
            )
            # A censored baseline never gives the side route authority.
            if (
                len(getattr(baseline, "lane_callbacks")) < len(pilot_ordinals)
                or time.monotonic() >= deadline_monotonic
                or int(budget.callbacks) >= int(callback_cap)
            ):
                self.summary = {
                    "mode": "BASELINE_CENSORED_NO_PORTAL",
                    "portal_activated": False,
                    "baseline_callbacks": int(budget.callbacks) - begin,
                    "individual_observations_emitted": False,
                }
                return baseline

            proposal, marked, reason = self._proposal(getattr(baseline, "endpoints"))
            if proposal is None:
                fallback = original(
                    arm,
                    base_case=base_case,
                    budget=budget,
                    program=program,
                    literal_prefix=_prefix_slice(literal_prefix, fallback_ordinals),
                    callback_cap=callback_cap,
                    callbacks_per_start=callbacks_per_start,
                    deadline_monotonic=deadline_monotonic,
                )
                self.summary = {
                    "mode": "UNKNOWN_FULL_BASELINE_FALLBACK",
                    "portal_activated": False,
                    "unknown_reason": reason,
                    "baseline_endpoint_observations": marked,
                    "individual_observations_emitted": False,
                }
                # No candidate counters are added: the search result is the
                # exact baseline prefix/kernel/callback continuation.
                return _merge_outcomes(
                    baseline, fallback, lane_offset=len(pilot_ordinals)
                )

            midpoint_before = int(budget.callbacks)
            midpoint_error = None
            portal_limit = min(
                int(callback_cap),
                midpoint_before + int(allocation["side_callbacks"]),
            )
            try:
                if int(budget.callbacks) < portal_limit:
                    base_case.evaluate(np.asarray(proposal.midpoint_probe, dtype=float))
            except Exception as error:  # fail closed; the charged attempt remains charged
                midpoint_error = type(error).__name__
            midpoint_callbacks = max(0, int(budget.callbacks) - midpoint_before)
            remaining = max(0, portal_limit - int(budget.callbacks))
            if remaining > 0 and time.monotonic() < deadline_monotonic:
                portal = original(
                    arm,
                    base_case=base_case,
                    budget=budget,
                    program=program,
                    literal_prefix=SimpleNamespace(
                        points=(np.asarray(proposal.point, dtype=float),)
                    ),
                    callback_cap=portal_limit,
                    callbacks_per_start=remaining,
                    deadline_monotonic=deadline_monotonic,
                )
            else:
                portal = type(baseline)(
                    endpoints=(), statuses={}, counters={}, lane_callbacks=()
                )
            portal_used = int(budget.callbacks) - midpoint_before
            baseline_used = midpoint_before - begin
            baseline_remaining = max(
                0, int(allocation["baseline_callbacks"]) - baseline_used
            )
            if (
                resume_ordinals
                and baseline_remaining > 0
                and time.monotonic() < deadline_monotonic
            ):
                resume_limit = min(
                    int(callback_cap), int(budget.callbacks) + baseline_remaining
                )
                resumed = original(
                    arm,
                    base_case=base_case,
                    budget=budget,
                    program=program,
                    literal_prefix=_prefix_slice(literal_prefix, resume_ordinals),
                    callback_cap=resume_limit,
                    callbacks_per_start=callbacks_per_start,
                    deadline_monotonic=deadline_monotonic,
                )
            else:
                resumed = type(baseline)(
                    endpoints=(), statuses={}, counters={}, lane_callbacks=()
                )
            used = int(budget.callbacks) - begin
            self.summary = {
                "mode": "PORTAL_SIDE_ACTIVE",
                "portal_activated": True,
                "baseline_endpoint_observations": marked,
                "baseline_callbacks_cap": int(allocation["baseline_callbacks"]),
                "side_callbacks_cap": int(allocation["side_callbacks"]),
                "midpoint_callbacks": midpoint_callbacks,
                "midpoint_error": midpoint_error,
                "portal_callbacks_used_including_midpoint": portal_used,
                "baseline_callbacks_used": used - portal_used,
                "total_callbacks_used": used,
                "portal_is_existing_interior_vertex": True,
                "canonical_replay_required": True,
                "individual_observations_emitted": False,
            }
            activated = _merge_outcomes(
                baseline,
                portal,
                lane_offset=3,
                first_lane_extra=midpoint_callbacks,
                status_extra={"guard_merge_portal_side_active": 1},
                counter_extra={
                    "guard_merge_portal_activations": 1,
                    "guard_merge_midpoint_callbacks": midpoint_callbacks,
                },
            )
            return _merge_outcomes(activated, resumed, lane_offset=4)

        return run_local_arm


def write_portal_sidecar(
    *, runtime: PortalRuntime, output: Path, atomic_write_json: Callable[..., object]
) -> Path:
    payload = {
        "schema_version": PORTAL_SCHEMA,
        "candidate": getattr(runtime.candidate, "CANDIDATE", "UNKNOWN"),
        "global_gate": {
            key: runtime.global_gate.get(key)
            for key in (
                "decision",
                "global_dynamic_gate_pass",
                "complete_typed_pools",
                "interior_ge_8_pools",
                "low_residual_invalid_endpoints",
                "distinct_anonymous_sources",
            )
        },
        "runtime": runtime.summary,
        "individual_observations_emitted": False,
        "search_result_sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
    }
    sidecar = output.with_name(output.name + ".guard-merge-portal.json")
    atomic_write_json(sidecar, payload)
    return sidecar


__all__ = [
    "PORTAL_SCHEMA",
    "PortalRuntime",
    "_phase_ordinals",
    "write_portal_sidecar",
]
