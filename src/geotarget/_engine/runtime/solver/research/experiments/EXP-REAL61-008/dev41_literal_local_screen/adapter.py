"""Hash-bound local kernels on one immutable literal-scale proposal prefix.

This adapter changes no source problem.  It constructs the already frozen
full-support literal-scale prefix from the untouched document and gives that
same point sequence to the CPQR control and exactly two local-kernel
candidates.  Source bounds are passed through verbatim; missing bounds remain
infinite.  Per-start scales are numerical preconditioners, never bounds.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass, is_dataclass, replace
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import time
from typing import Mapping, Sequence

import numpy as np


HERE = Path(__file__).resolve().parent
EXP008 = HERE.parent
SOURCE_ONLY = EXP008 / "source_only"
ROOT = HERE.parents[3]
for path in (SOURCE_ONLY, ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from runtime import BudgetExceeded  # noqa: E402
from scaling import case_for_start  # noqa: E402


CONTROL = "literal_prefix_analytic_forward_ad_cpqr"
ROW = "literal_prefix_ad_row_equilibrated_cpqr"
VECTOR = "literal_prefix_ad_vector_filter"
ARMS = (CONTROL, ROW, VECTOR)
CANDIDATE_ARMS = (ROW, VECTOR)

SOURCE_ONLY_FREEZE = SOURCE_ONLY / "FREEZE.json"
SOURCE_ONLY_FREEZE_SHA256 = (
    "fe6371eb5c687857d2b497de40a7c46c16da6c011386f20eb0fe3dd69984528b"
)
POLICY_DIGEST = "fbf70a530960ffdbcc59f87ede65644ff5eb968dc9e67eb75b47f67384dcd609"

MODULE_BINDINGS = {
    "control": (
        HERE.parents[1] / "EXP-REAL61-006/analytic_jacobian/candidate.py",
        "9b1a8117c39d93e2c0b72b2fd1f18b49976730630ab664d0b45843d1ee90e35d",
    ),
    "row": (
        EXP008 / "ad_row_equilibration_rebind/candidate.py",
        "59a021f7a5628dcf03010e7cc2035ce2582e61f092235164f635e159b5f48e9a",
    ),
    "vector": (
        EXP008 / "ad_vector_filter_kernel/candidate.py",
        "021d90c5c46a8308b71cb04db1a6ae30577f018bc21c7556b0d372e7a0335dee",
    ),
    "literal": (
        EXP008 / "literal_scale_mixture_rebind/candidate.py",
        "696bfdacc369cb85e54d00b107a9608837719d6ff6e65f1c36d07b3020c815cf",
    ),
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load(name: str, path: Path, expected: str):
    if _sha256(path) != expected:
        raise RuntimeError(f"hash-bound local-screen module changed: {name}")
    module_name = f"geotarget_exp008_dev41_literal_local_{name}"
    cached = sys.modules.get(module_name)
    if cached is not None:
        return cached
    specification = importlib.util.spec_from_file_location(module_name, path)
    if specification is None or specification.loader is None:
        raise ImportError(path)
    module = importlib.util.module_from_spec(specification)
    sys.modules[module_name] = module
    specification.loader.exec_module(module)
    return module


def verify_bindings() -> dict[str, object]:
    if _sha256(SOURCE_ONLY_FREEZE) != SOURCE_ONLY_FREEZE_SHA256:
        raise RuntimeError("source-only freeze changed")
    packet = json.loads(SOURCE_ONLY_FREEZE.read_text(encoding="utf-8"))
    if packet.get("policy_digest") != POLICY_DIGEST:
        raise RuntimeError("source-only policy digest changed")
    for relative, expected in packet["file_sha256"].items():
        if _sha256(SOURCE_ONLY / relative) != expected:
            raise RuntimeError(f"source-only policy file changed: {relative}")
    module_hashes = {}
    for name, (path, expected) in MODULE_BINDINGS.items():
        actual = _sha256(path)
        if actual != expected:
            raise RuntimeError(f"local-screen binding changed: {name}")
        module_hashes[name] = actual
    return {
        "source_only_freeze_sha256": SOURCE_ONLY_FREEZE_SHA256,
        "source_only_policy_digest": POLICY_DIGEST,
        "module_sha256": module_hashes,
        "proposal_prefix": "frozen pure literal-scale mixture",
        "source_problem_modified": False,
        "variables_or_equations_changed": False,
        "added_or_inferred_bounds": False,
        "gauge_or_symmetry_reduction": False,
        "problem_identity_family_truth_or_target_count_inputs": False,
        "candidate_count_excluding_control": len(CANDIDATE_ARMS),
    }


BINDING_RECORD = verify_bindings()
CONTROL_MODULE = _load("control", *MODULE_BINDINGS["control"])
ROW_MODULE = _load("row", *MODULE_BINDINGS["row"])
VECTOR_MODULE = _load("vector", *MODULE_BINDINGS["vector"])
LITERAL_MODULE = _load("literal", *MODULE_BINDINGS["literal"])


@dataclass(frozen=True)
class LocalScreenOutcome:
    endpoints: tuple[tuple[int, np.ndarray], ...]
    statuses: Mapping[str, int]
    counters: Mapping[str, int]
    lane_callbacks: tuple[int, ...]


class LaneQuota:
    """Per-lane cap layered over the already charged opaque evaluator."""

    def __init__(self, case: object, budget: object, cap: int) -> None:
        self._evaluate = case.evaluate
        self._progressive = case.progressive_residual
        self._budget = budget
        self._begin = int(budget.callbacks)
        self._cap = max(0, int(cap))

    @property
    def used(self) -> int:
        return int(self._budget.callbacks) - self._begin

    def _check(self) -> None:
        if self.used >= self._cap:
            raise BudgetExceeded("literal_local_lane_callback_cap")

    def evaluate(self, point: Sequence[float]):
        self._check()
        return self._evaluate(np.asarray(point, dtype=float))

    def progressive(self, point: Sequence[float]):
        self._check()
        return self._progressive(np.asarray(point, dtype=float))


def _counter_map(value: object) -> dict[str, int]:
    if isinstance(value, Mapping):
        raw = value
    elif is_dataclass(value):
        raw = asdict(value)
    elif hasattr(value, "__dict__"):
        raw = vars(value)
    else:
        return {}
    return {
        str(name): int(item)
        for name, item in raw.items()
        if isinstance(item, (bool, int, np.integer))
    }


def build_literal_prefix(
    document: Mapping[str, object],
    base_case: object,
    base_policy: object,
):
    """Build the one arm-independent point sequence used by every kernel."""

    return LITERAL_MODULE.build_literal_scale_prefix(
        document,
        base_case.lower,
        base_case.upper,
        base_policy.points,
        base_policy.sources,
        seed=base_policy.seed,
    )


def compile_program(arm: str, document: Mapping[str, object]):
    if arm == CONTROL:
        return CONTROL_MODULE.compile_program(document)
    if arm == ROW:
        return ROW_MODULE.compile_program(document)
    if arm == VECTOR:
        return VECTOR_MODULE.compile_program(document)
    raise ValueError(f"unknown local-screen arm {arm!r}")


def _solve_lane(
    arm: str,
    lane_case: object,
    program: object,
    start: np.ndarray,
    scale: np.ndarray,
    lower: np.ndarray,
    upper: np.ndarray,
    lane_cap: int,
    deadline: float,
):
    if arm == CONTROL:
        control_case = case_for_start(lane_case, start)
        return CONTROL_MODULE.solve_local(
            control_case,
            program,
            CONTROL_MODULE.CONFIGURATIONS[CONTROL_MODULE.ANALYTIC_CPQR],
            start,
            max_callbacks=lane_cap,
            deadline_monotonic=deadline,
        )
    common = {
        "per_start_scale": scale,
        "source_lower": lower,
        "source_upper": upper,
        "max_callbacks": lane_cap,
        "deadline_monotonic": deadline,
    }
    if arm == ROW:
        return ROW_MODULE.solve_local(
            lane_case, program, ROW_MODULE.REFERENCE, start, **common
        )
    if arm == VECTOR:
        return VECTOR_MODULE.solve_local(
            lane_case, program, VECTOR_MODULE.CONFIGURATION, start, **common
        )
    raise ValueError(f"unknown local-screen arm {arm!r}")


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
) -> LocalScreenOutcome:
    """Run one local kernel on the frozen, arm-independent proposal prefix."""

    if arm not in ARMS:
        raise ValueError(f"unknown local-screen arm {arm!r}")
    endpoints: list[tuple[int, np.ndarray]] = []
    statuses: Counter[str] = Counter()
    counters: Counter[str] = Counter()
    lane_callbacks: list[int] = []
    for lane, raw_start in enumerate(literal_prefix.points):
        if int(budget.callbacks) >= callback_cap or time.monotonic() >= deadline_monotonic:
            statuses["global_stop_before_lane"] += 1
            break
        start = np.asarray(raw_start, dtype=float)
        scale = np.maximum(1.0, np.abs(start))
        lane_cap = min(callbacks_per_start, callback_cap - int(budget.callbacks))
        quota = LaneQuota(base_case, budget, lane_cap)
        lane_case = replace(
            base_case,
            evaluate=quota.evaluate,
            progressive_residual=quota.progressive,
        )
        try:
            outcome = _solve_lane(
                arm,
                lane_case,
                program,
                start,
                scale,
                base_case.lower,
                base_case.upper,
                lane_cap,
                deadline_monotonic,
            )
            statuses[str(getattr(outcome, "status", "unknown"))] += 1
            counters.update(_counter_map(getattr(outcome, "counters", {})))
            endpoint = np.asarray(getattr(outcome, "endpoint"), dtype=float)
            if endpoint.shape == (base_case.dimension,) and np.all(np.isfinite(endpoint)):
                endpoints.append((lane, endpoint.copy()))
        except Exception as error:
            statuses[f"exception:{type(error).__name__}"] += 1
            counters["lane_exceptions"] += 1
        lane_callbacks.append(quota.used)
    return LocalScreenOutcome(
        endpoints=tuple(endpoints),
        statuses=dict(statuses),
        counters=dict(counters),
        lane_callbacks=tuple(lane_callbacks),
    )


def configuration_manifest() -> Mapping[str, object]:
    return {
        "binding_record": BINDING_RECORD,
        "arms": list(ARMS),
        "control": CONTROL,
        "candidate_arms": list(CANDIDATE_ARMS),
        "same_literal_prefix_for_every_arm": True,
        "local_scale": "max(1, abs(start)); preconditioning only",
        "source_bytes_or_semantics_changed": False,
        "all_source_variables_and_equations_retained": True,
        "source_bounds_only": True,
        "added_or_inferred_bounds": False,
        "gauge_or_symmetry_reduction": False,
        "truth_or_outcome_inputs": False,
    }


__all__ = [
    "ARMS",
    "BINDING_RECORD",
    "CANDIDATE_ARMS",
    "CONTROL",
    "ROW",
    "VECTOR",
    "build_literal_prefix",
    "compile_program",
    "configuration_manifest",
    "run_local_arm",
    "verify_bindings",
]
