"""Collect-only hook for the guard-relative merge-tree dynamic gate.

This module deliberately has no proposal path.  It observes the result of the
already charged baseline ``SourceOnlyCase.evaluate`` callback, keeps at most
1,200 unique finite observations in process, and emits only aggregate gate
statistics after the unchanged search worker has written its normal result.
"""

from __future__ import annotations

from dataclasses import replace
import hashlib
import json
import math
from pathlib import Path
import struct
from typing import Any, Callable, Mapping

import numpy as np


COLLECTOR_SCHEMA = "geotarget.guard-relative-merge-tree-collect-only/v1"
OBSERVATION_CAP = 1200


def _point_key(point: np.ndarray) -> bytes:
    values = tuple(float(value) for value in point)
    return struct.pack(">I", len(values)) + b"".join(
        struct.pack(">d", value) for value in values
    )


def _output_argument(argv: list[str]) -> Path:
    try:
        index = argv.index("--output")
        value = argv[index + 1]
    except (ValueError, IndexError):
        raise SystemExit("collect-only connector requires --output") from None
    return Path(value)


class Collector:
    def __init__(self, source_sha256: str, candidate: Any) -> None:
        if (
            len(source_sha256) != 64
            or any(character not in "0123456789abcdef" for character in source_sha256)
        ):
            raise SystemExit("collect-only connector requires canonical source SHA-256")
        self.source_sha256 = source_sha256
        self.candidate = candidate
        self.case = None
        self.guard_count = 0
        self.typed_guard_complete = True
        self.charged_evaluate_calls = 0
        self.progressive_calls_not_observed = 0
        self.nonfinite_or_untyped_skipped = 0
        self.hard_only_invalid_skipped = 0
        self.duplicate_points_skipped = 0
        self.cap_dropped = 0
        self.accounting_mismatch = False
        self._rows: list[dict[str, object]] = []
        self._point_keys: set[bytes] = set()

    def wrap_build_source_case(self, original: Callable[..., object]):
        def build_source_case(document, *, callback_cap: int, deadline: float):
            case, budget, evaluator = original(
                document, callback_cap=callback_cap, deadline=deadline
            )
            self.case = case
            self.guard_count = len(getattr(evaluator, "compiled_guards", ()))
            baseline_evaluate = case.evaluate

            def evaluate(point):
                before = int(budget.callbacks)
                observation = baseline_evaluate(point)
                after = int(budget.callbacks)
                if after != before + 1:
                    self.accounting_mismatch = True
                self.charged_evaluate_calls += max(0, after - before)
                self._observe(point, observation)
                return observation

            # The progressive evaluator remains the exact baseline bound
            # method.  It is intentionally not replayed merely to obtain guard
            # state, because that would add callbacks and alter the solver.
            return replace(case, evaluate=evaluate), budget, evaluator

        return build_source_case

    def _observe(self, point: object, observation: object) -> None:
        if len(self._rows) >= OBSERVATION_CAP:
            self.cap_dropped += 1
            return
        try:
            values = np.asarray(point, dtype=float).reshape(-1)
            residual = np.asarray(getattr(observation, "residual"), dtype=float)
            violations = np.asarray(
                getattr(observation, "violation_vector"), dtype=float
            ).reshape(-1)
            finite = bool(getattr(observation, "finite"))
        except Exception:
            self.nonfinite_or_untyped_skipped += 1
            self.typed_guard_complete = False
            return
        if (
            self.case is None
            or values.shape != (int(self.case.dimension),)
            or residual.shape != (int(self.case.residual_dimension),)
        ):
            self.nonfinite_or_untyped_skipped += 1
            self.typed_guard_complete = False
            return
        if (
            not finite
            or not np.all(np.isfinite(values))
            or not np.all(np.isfinite(residual))
        ):
            self.nonfinite_or_untyped_skipped += 1
            return
        if violations.shape != (self.guard_count + 1,) or not np.all(
            np.isfinite(violations)
        ):
            self.nonfinite_or_untyped_skipped += 1
            self.typed_guard_complete = False
            return
        key = _point_key(values)
        if key in self._point_keys:
            self.duplicate_points_skipped += 1
            return
        semantic_interior = bool(getattr(observation, "semantics_valid"))
        typed_guard_invalid = bool(
            self.guard_count > 0 and np.any(violations[: self.guard_count] > 0.0)
        )
        if semantic_interior:
            guard_state = "INTERIOR"
        elif typed_guard_invalid:
            guard_state = "INVALID"
        else:
            # Hard-feasibility-only failures cannot be used as a guard portal
            # seed without another evaluator call, so fail conservatively.
            self.hard_only_invalid_skipped += 1
            return
        residual_inf = float(np.linalg.norm(residual, ord=np.inf))
        if not math.isfinite(residual_inf) or residual_inf < 0.0:
            self.nonfinite_or_untyped_skipped += 1
            return
        self._point_keys.add(key)
        self._rows.append(
            {
                "point": [float(value) for value in values],
                "residual": residual_inf,
                "guard_state": guard_state,
                "endpoint": False,
                "charged": True,
            }
        )

    def _mark_endpoints(self, result: Mapping[str, object]) -> int:
        endpoint_keys: set[bytes] = set()
        raw_endpoints = result.get("endpoints")
        if isinstance(raw_endpoints, list):
            for row in raw_endpoints:
                if not isinstance(row, Mapping) or not isinstance(row.get("point"), list):
                    continue
                try:
                    values = np.asarray(row["point"], dtype=float).reshape(-1)
                except (TypeError, ValueError, OverflowError):
                    continue
                if self.case is not None and values.shape == (int(self.case.dimension),):
                    endpoint_keys.add(_point_key(values))
        marked = 0
        for row in self._rows:
            values = np.asarray(row["point"], dtype=float)
            if _point_key(values) in endpoint_keys:
                row["endpoint"] = True
                marked += 1
        return marked

    def aggregate(self, result: Mapping[str, object]) -> dict[str, object]:
        endpoint_count = self._mark_endpoints(result)
        if self.case is None:
            gate = {
                "candidate": getattr(self.candidate, "CANDIDATE", "UNKNOWN"),
                "decision": "UNKNOWN_FULL_BASELINE_FALLBACK",
                "gate_pass": False,
                "unknown_reason": "SOURCE_CASE_WAS_NOT_BUILT",
                "individual_observations_emitted": False,
            }
        else:
            scales = np.asarray(self.case.scales, dtype=float).reshape(-1)
            scale_valid = bool(
                scales.shape == (int(self.case.dimension),)
                and np.all(np.isfinite(scales))
                and np.all(scales > 0.0)
            )
            pool = {
                "anonymous_source_hash": self.source_sha256,
                "dimension": int(self.case.dimension),
                "scale": [float(value) for value in scales] if scale_valid else [],
                "typed_guard_complete": bool(
                    self.typed_guard_complete and not self.accounting_mismatch
                ),
                "guard_count": self.guard_count,
                "typed_guard_count": self.guard_count,
                "observations": self._rows,
            }
            gate = self.candidate.dynamic_gate([pool])
        return {
            "schema_version": COLLECTOR_SCHEMA,
            "candidate": getattr(self.candidate, "CANDIDATE", "UNKNOWN"),
            "mode": "COLLECT_ONLY_PORTAL_OFF",
            "portal_proposal_enabled": False,
            "side_callback_quota_enabled": False,
            "solver_output_modified": False,
            "individual_observations_emitted": False,
            "collector": {
                "observation_cap": OBSERVATION_CAP,
                "charged_evaluate_calls": self.charged_evaluate_calls,
                "unique_finite_typed_observations": len(self._rows),
                "endpoint_observations": endpoint_count,
                "duplicate_points_skipped": self.duplicate_points_skipped,
                "nonfinite_or_untyped_skipped": self.nonfinite_or_untyped_skipped,
                "hard_only_invalid_skipped": self.hard_only_invalid_skipped,
                "cap_dropped": self.cap_dropped,
                "accounting_mismatch": self.accounting_mismatch,
            },
            "dynamic_gate": gate,
        }


def write_aggregate_sidecar(
    *, collector: Collector, output: Path, atomic_write_json: Callable[..., object]
) -> Path:
    result = json.loads(output.read_text(encoding="utf-8"))
    if not isinstance(result, Mapping):
        raise RuntimeError("baseline search result is not a mapping")
    payload = collector.aggregate(result)
    # Bind the aggregate to the unchanged baseline result without copying any
    # result row or in-memory observation into the sidecar.
    payload["baseline_result_sha256"] = hashlib.sha256(output.read_bytes()).hexdigest()
    sidecar = output.with_name(output.name + ".guard-merge-gate.json")
    atomic_write_json(sidecar, payload)
    return sidecar


__all__ = [
    "COLLECTOR_SCHEMA",
    "Collector",
    "OBSERVATION_CAP",
    "_output_argument",
    "write_aggregate_sidecar",
]
