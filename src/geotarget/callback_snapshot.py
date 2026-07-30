"""Whole-callback snapshot for fully qualified compiled geometry programs."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

from mpmath import mp

from geotarget.flat_tape_backend import FlatTapeProgram

SNAPSHOT_ABI = "geotarget.compiled-callback-snapshot/v1"
_SUPPORTED_HARD_KINDS = frozenset(
    {
        "guard",
        "line_distinct",
        "triangle_nondegenerate",
    }
)


@dataclass(frozen=True, slots=True)
class _PointSnapshot:
    x: float
    y: float


@dataclass(frozen=True, slots=True)
class CallbackSnapshotResult:
    residual_observation: Any
    guard_violations: tuple[str, ...]
    guard_penalty: float
    guard_vector: tuple[float, ...]
    hard_feasibility: Any


class CompiledCallbackSnapshot:
    """One-call residual/guard/hard evaluator with isolated numeric lanes."""

    semantic_abi = SNAPSHOT_ABI

    def __init__(
        self,
        *,
        evaluator: Any,
        flat_tape: FlatTapeProgram,
        required_hard_points: frozenset[str],
    ) -> None:
        self.evaluator = evaluator
        self.flat_tape = flat_tape
        self.required_hard_points = required_hard_points

    def metadata(self) -> dict[str, Any]:
        key = {
            "semantic_abi": self.semantic_abi,
            "residual_abi": self.flat_tape.semantic_abi,
            "hard_kinds": sorted(
                {check.kind for check in self.evaluator.bundle.hard_feasibility_checks}
            ),
            "required_hard_point_count": len(self.required_hard_points),
        }
        return {
            **key,
            "support_key_sha256": hashlib.sha256(
                json.dumps(key, sort_keys=True, separators=(",", ":")).encode()
            ).hexdigest(),
            "whole_problem_admission": True,
            "runtime_fallback_scope": "whole_callback",
            "numeric_lanes": ["bf53_residual", "mp80_guard", "float_hard"],
            "numeric_lanes_share_values": False,
            "case_specific_routing": False,
            "problem_identity_read": False,
            "corpus_metadata_read": False,
        }

    def evaluate(self, raw_values: list[float]) -> CallbackSnapshotResult | None:
        # Imports remain lazy because the frozen geosolver source is installed
        # on sys.path by the worker after the product wrapper is imported.
        from geosolver._internal.autosolve.answer.precision_schedule import MIN_PRECISION
        from geosolver._internal.autosolve.execution.interpreter_helpers import (
            _build_guard_context,
        )
        from geosolver._internal.autosolve.guards.compile import (
            guard_hard_satisfied,
            guard_violation_value,
        )
        from geosolver._internal.pipeline.contracts.hard_feasibility_snapshot import (
            HardFeasibilitySnapshot,
        )
        from geosolver._internal.pipeline.evaluator._hard_feasibility_core import (
            HardFeasibilityRuntimeState,
            _evaluate_single_check,
            _is_all_input_finite,
        )

        point_values = self.flat_tape.evaluate_hard_point_lane(
            raw_values,
            self.required_hard_points,
        )
        if point_values is None:
            return None
        try:
            target_dps = max(int(mp.dps), MIN_PRECISION, 80)
            with mp.workdps(target_dps):
                context = _build_guard_context(
                    self.evaluator.bundle.spec,
                    list(self.evaluator.bundle.var_names),
                    raw_values,
                    dict(self.evaluator.bundle.base_context),
                )
                violations: list[str] = []
                penalty = mp.mpf("0")
                vector: list[float] = []
                vector_failed = False
                for index, guard in enumerate(self.evaluator.compiled_guards):
                    try:
                        if not guard_hard_satisfied(guard, context):
                            violations.append(f"guard[{index}] returned False")
                    except Exception as error:
                        violations.append(f"guard[{index}] raised: {error}")
                    try:
                        value = guard_violation_value(guard, context)
                        if mp.isfinite(value):
                            penalty += value
                            vector.append(float(value))
                        else:
                            penalty += mp.mpf("1")
                            vector.append(1.0)
                    except Exception:
                        penalty += mp.mpf("1")
                        vector_failed = True
                        vector.append(1.0)

            guard_violations = tuple(violations)
            guard_ok = not guard_violations
            hard = HardFeasibilitySnapshot(
                hard_feasible=True,
                failure_tags=(),
                min_margin=None,
            )
            checks = self.evaluator.bundle.hard_feasibility_checks
            if checks:
                if not _is_all_input_finite(raw_values, allow_float=True):
                    return None
                state = HardFeasibilityRuntimeState(
                    context={
                        name: _PointSnapshot(*coordinates)
                        for name, coordinates in point_values.items()
                    },
                    trace_entries={},
                )
                failure_tags: list[str] = []
                passed_margins: list[Any] = []
                for check in checks:
                    ok, failure_tag, margin = _evaluate_single_check(
                        check=check,
                        state=state,
                        allow_float=True,
                        guard_ok=guard_ok,
                        guard_violations=guard_violations,
                    )
                    if ok:
                        if margin is not None and mp.isfinite(margin):
                            passed_margins.append(margin)
                    else:
                        failure_tags.append(failure_tag or check.check_id)
                hard = HardFeasibilitySnapshot(
                    hard_feasible=not failure_tags,
                    failure_tags=tuple(failure_tags),
                    min_margin=min(passed_margins) if passed_margins else None,
                )
            residual_observation = self.evaluator.evaluate_float_residual(raw_values)
            return CallbackSnapshotResult(
                residual_observation=residual_observation,
                guard_violations=guard_violations,
                guard_penalty=float(penalty),
                guard_vector=(
                    tuple(1.0 for _guard in self.evaluator.compiled_guards)
                    if vector_failed
                    else tuple(vector)
                ),
                hard_feasibility=hard,
            )
        except Exception:
            return None


def compile_callback_snapshot(evaluator: Any) -> CompiledCallbackSnapshot | None:
    """Admit only a complete flat residual/guard/hard callback."""

    plan = getattr(evaluator, "plan", None)
    flat_tape = getattr(plan, "flat_tape_program", None)
    if not isinstance(flat_tape, FlatTapeProgram):
        return None
    checks = tuple(evaluator.bundle.hard_feasibility_checks)
    if any(check.kind not in _SUPPORTED_HARD_KINDS for check in checks):
        return None
    required = frozenset(
        name for check in checks if check.kind != "guard" for name in check.symbol_names
    )
    roots = dict(zip(flat_tape.construction_names, flat_tape.construction_roots, strict=True))
    if any(name not in roots for name in required):
        return None
    # evaluate_hard_point_lane applies the final point-kind gate without
    # exporting private flat-tape enum types into this module.
    return CompiledCallbackSnapshot(
        evaluator=evaluator,
        flat_tape=flat_tape,
        required_hard_points=required,
    )


__all__ = [
    "SNAPSHOT_ABI",
    "CallbackSnapshotResult",
    "CompiledCallbackSnapshot",
    "compile_callback_snapshot",
]
