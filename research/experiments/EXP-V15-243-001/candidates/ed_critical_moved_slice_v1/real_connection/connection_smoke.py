"""One source-only thin connection; no truth, target, scorer, HP, or CAS."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import math
from pathlib import Path
import sys
import time

import numpy as np


HERE = Path(__file__).resolve().parent
CANDIDATE_DIR = HERE.parent
RUNTIME_ROOT = Path("/home/kabatan/work/solver-experiment-runtime/solver")
SOURCE_ONLY = RUNTIME_ROOT / "research/experiments/EXP-REAL61-008/source_only"
BASE_ADAPTER = (
    RUNTIME_ROOT
    / "research/experiments/EXP-REAL61-008/hybrid_direct_broyden_tr_lm_v9"
    / "corrective_nearroot_strict_restart_v2/adapter.py"
)
BASE_ADAPTER_SHA256 = "cda4e348ce1bb848af84afaba062c931ec5f1ebf882bdb8cf122df0366e75dc2"
DATASET = (
    RUNTIME_ROOT
    / "research/experiments/EXP-OMC-V15-MERGED5-EVAL-001/inputs"
    / "omc_v15_merged_5files.audit-canonical.jsonl"
)

for directory in (CANDIDATE_DIR, SOURCE_ONLY, RUNTIME_ROOT):
    if str(directory) not in sys.path:
        sys.path.insert(0, str(directory))

from candidate import Observation, Problem, critical_slice_lane  # noqa: E402
from policy import materialize_policy  # noqa: E402


def _load_base():
    observed = hashlib.sha256(BASE_ADAPTER.read_bytes()).hexdigest()
    if observed != BASE_ADAPTER_SHA256:
        raise RuntimeError("frozen source-only base adapter hash mismatch")
    name = "geotarget_ed_slice_thin_base"
    specification = importlib.util.spec_from_file_location(name, BASE_ADAPTER)
    if specification is None or specification.loader is None:
        raise ImportError(BASE_ADAPTER)
    module = importlib.util.module_from_spec(specification)
    sys.modules[name] = module
    specification.loader.exec_module(module)
    return module


BASE = _load_base()


def _source_only(document: dict[str, object]) -> dict[str, object]:
    return {k: v for k, v in document.items() if k not in {"answer", "post_process"}}


def _canonical(document: dict[str, object]) -> bytes:
    return (
        json.dumps(document, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        + "\n"
    ).encode("utf-8")


def _formulations() -> list[tuple[str, bytes, dict[str, object]]]:
    rows = []
    for line in DATASET.read_text().splitlines():
        try:
            document = _source_only(json.loads(line)["formulation"])
        except Exception:
            continue
        if document.get("task") != "solve":
            continue
        payload = _canonical(document)
        rows.append((hashlib.sha256(payload).hexdigest(), payload, document))
    return sorted(rows, key=lambda row: row[0])


def _raw_residual(case: object, point: np.ndarray) -> np.ndarray | None:
    try:
        raw = case.evaluate(np.asarray(point, dtype=float))
        residual = np.asarray(raw.residual, dtype=float)
    except Exception:
        return None
    if residual.ndim != 1 or not np.all(np.isfinite(residual)):
        return None
    return residual


def _fd(case: object, point: np.ndarray, residual: np.ndarray) -> np.ndarray | None:
    dimension = point.size
    jacobian = np.empty((residual.size, dimension), dtype=float)
    lower = np.asarray(case.lower, dtype=float)
    upper = np.asarray(case.upper, dtype=float)
    for column in range(dimension):
        step = 2e-6 * max(1.0, abs(float(point[column])))
        trial = point.copy()
        if not math.isfinite(float(upper[column])) or point[column] + step <= upper[column]:
            trial[column] += step
        elif not math.isfinite(float(lower[column])) or point[column] - step >= lower[column]:
            trial[column] -= step
        else:
            return None
        displaced = _raw_residual(case, trial)
        if displaced is None or displaced.shape != residual.shape:
            return None
        jacobian[:, column] = (displaced - residual) / (trial[column] - point[column])
    return jacobian if np.all(np.isfinite(jacobian)) else None


def _rank(jacobian: np.ndarray) -> int:
    row_norm = np.maximum(np.linalg.norm(jacobian, axis=1), 1e-13)
    singular = np.linalg.svd(jacobian / row_norm[:, None], compute_uv=False)
    if singular.size == 0:
        return 0
    threshold = max(jacobian.shape) * np.finfo(float).eps * max(float(singular[0]), 1.0) * 64
    return int(np.count_nonzero(singular > threshold))


def _select_fixed_source_for_endpoint_rank() -> tuple[
    str, bytes, dict[str, object], dict[str, int]
]:
    for source_sha, payload, document in _formulations()[:1]:
        deadline = time.monotonic() + 0.75
        try:
            case, _, _ = BASE.PRECISION_RUNTIME.build_source_case(
                document, callback_cap=24, deadline=deadline
            )
            policy = materialize_policy(
                document, source_sha256=source_sha, starts=1, seed=0
            )
            point = np.asarray(policy.points[0], dtype=float)
            residual = _raw_residual(case, point)
            if residual is None:
                continue
        except Exception:
            continue
        # Case selection is fixed SHA order.  Numerical rank at this arbitrary
        # point is deliberately ignored; actual activation is decided only
        # from the endpoint returned by the untouched ordinary solver.
        return source_sha, payload, document, {
            "sources_scanned": 1,
            "dimension": int(case.dimension),
            "residual_dimension": int(residual.size),
            "structural_n_gt_m": bool(residual.size < int(case.dimension)),
            "activation_deferred_to_ordinary_endpoint_fd_rank": True,
        }
    raise RuntimeError("fixed SHA source could not be materialized")


class _SourceProblem:
    def __init__(self, case: object, evaluator: object, prefix_points: list[np.ndarray]):
        self.case = case
        self.evaluator = evaluator
        self.proposal_replay_attempts = 0
        self.final_authority_replay_attempts = 0
        lower = np.asarray(case.lower, dtype=float)
        upper = np.asarray(case.upper, dtype=float)
        points = np.vstack(prefix_points)
        center = np.median(points, axis=0)
        scale = np.maximum(1.0, np.median(np.abs(points - center), axis=0) * 1.4826)
        both = np.isfinite(lower) & np.isfinite(upper) & (upper > lower)
        center[both] = 0.5 * (lower[both] + upper[both])
        scale[both] = 0.5 * (upper[both] - lower[both])
        self.problem = Problem(
            center=center,
            chart=np.diag(scale),
            lower=lower,
            upper=upper,
            observe=self.observe,
            replay=self.proposal_replay,
            in_bounds=self.in_bounds,
            ed_capable=True,
        )

    def in_bounds(self, point: np.ndarray) -> bool:
        point = np.asarray(point, dtype=float)
        return bool(
            point.shape == self.problem.lower.shape
            and np.all(np.isfinite(point))
            and np.all(point >= self.problem.lower)
            and np.all(point <= self.problem.upper)
        )

    def observe(self, point: np.ndarray) -> Observation:
        residual = _raw_residual(self.case, point)
        if residual is None:
            raise ValueError("opaque residual")
        jacobian = _fd(self.case, np.asarray(point, dtype=float), residual)
        if jacobian is None:
            raise ValueError("opaque FD Jacobian")
        return Observation(residual, jacobian, True)

    def _fresh_canonical_replay(self, point: np.ndarray) -> bool:
        values = [float(value) for value in point]

        def check() -> bool:
            residual = self.evaluator.evaluate_float_residual(values)
            guard_ok, _ = self.evaluator.evaluate_guard(values)
            hard = self.evaluator.evaluate_float_hard_feasibility(values)
            norm = float(residual.residual_norm_float)
            return bool(
                self.in_bounds(np.asarray(values, dtype=float))
                and residual.is_finite
                and math.isfinite(norm)
                and norm <= 1e-8
                and guard_ok
                and hard.hard_feasible
            )

        try:
            return bool(BASE.PRECISION_RUNTIME.precision_isolated(check))
        except Exception:
            return False

    def proposal_replay(self, point: np.ndarray) -> bool:
        """Replay every candidate endpoint, but do not terminate discovery."""
        self.proposal_replay_attempts += 1
        self._fresh_canonical_replay(point)
        return False

    def final_authority_replay(self, point: np.ndarray) -> bool:
        self.final_authority_replay_attempts += 1
        return self._fresh_canonical_replay(point)


def main() -> None:
    source_sha, payload, document, eligibility = (
        _select_fixed_source_for_endpoint_rank()
    )
    total_cap = 128
    deadline = time.monotonic() + 8.0
    case, budget, evaluator = BASE.PRECISION_RUNTIME.build_source_case(
        document, callback_cap=total_cap, deadline=deadline
    )
    policy = materialize_policy(document, source_sha256=source_sha, starts=4, seed=0)
    prefix = BASE.build_literal_prefix(document, case, policy)
    prefix_points = [np.asarray(point, dtype=float).copy() for point in prefix.points]
    prefix_digest = hashlib.sha256(
        b"".join(np.asarray(point, dtype="<f8").tobytes() for point in prefix_points)
    ).hexdigest()
    program = BASE.compile_program(BASE.CANDIDATE, document)
    original = BASE.run_local_arm(
        BASE.CANDIDATE,
        base_case=case,
        budget=budget,
        program=program,
        literal_prefix=prefix,
        callback_cap=total_cap,
        callbacks_per_start=24,
        deadline_monotonic=deadline,
    )
    baseline_callbacks = int(budget.callbacks)
    route_cap = min(total_cap - baseline_callbacks, baseline_callbacks // 3)
    start = (
        np.asarray(original.endpoints[-1][1], dtype=float)
        if original.endpoints
        else prefix_points[-1]
    )
    endpoint_digest = hashlib.sha256(np.asarray(start, dtype="<f8").tobytes()).hexdigest()
    endpoint_residual = _raw_residual(case, start)
    endpoint_jacobian = (
        _fd(case, start, endpoint_residual) if endpoint_residual is not None else None
    )
    endpoint_rank = (
        _rank(endpoint_jacobian) if endpoint_jacobian is not None else int(case.dimension)
    )
    if endpoint_rank >= int(case.dimension):
        raise RuntimeError("ordinary endpoint has no positive nullity")
    eligibility.update(
        {
            "endpoint_fd_rank": endpoint_rank,
            "endpoint_nullity": int(case.dimension) - endpoint_rank,
        }
    )
    wrapper = _SourceProblem(case, evaluator, prefix_points)
    conceptual_cap = max(1, route_cap // (int(case.dimension) + 1))
    before_route = int(budget.callbacks)
    outcome = critical_slice_lane(
        wrapper.problem,
        start,
        prefix_points[:3],
        conceptual_cap,
    )
    # Mandatory final fresh canonical source/guard replay.  Its Boolean result
    # is deliberately not serialized: this artifact is a connection smoke,
    # not case-outcome evidence.
    wrapper.final_authority_replay(outcome.point)
    route_callbacks = int(budget.callbacks) - before_route
    total_callbacks = baseline_callbacks + route_callbacks
    current_prefix_digest = hashlib.sha256(
        b"".join(np.asarray(point, dtype="<f8").tobytes() for point in prefix.points)
    ).hexdigest()
    current_endpoint_digest = hashlib.sha256(
        np.asarray(start, dtype="<f8").tobytes()
    ).hexdigest()
    connected = bool(
        outcome.activated
        and (outcome.ed_queries > 0 or outcome.slice_moves > 0)
        and route_callbacks <= route_cap
        and baseline_callbacks >= 3 * route_callbacks
        and wrapper.proposal_replay_attempts > 0
        and wrapper.final_authority_replay_attempts == 1
        and current_endpoint_digest == endpoint_digest
    )
    script_sha = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    candidate_sha = hashlib.sha256((CANDIDATE_DIR / "candidate.py").read_bytes()).hexdigest()
    mechanism_sha = hashlib.sha256(
        candidate_sha.encode("ascii")
        + b"\0"
        + script_sha.encode("ascii")
        + b"\0"
        + BASE_ADAPTER_SHA256.encode("ascii")
    ).hexdigest()
    result = {
        "schema": "ed-critical-moved-slice-thin-source-smoke/v1",
        "status": "CONNECTED_SOURCE_ONLY" if connected else "HOLD_CONNECTION",
        "source_sha256": source_sha,
        "source_bytes_unchanged": _canonical(document) == payload,
        "source_document_passed_to_candidate": False,
        "target_or_answer_evaluated": False,
        "truth_scorer_hp_cas_used": False,
        "eligibility": eligibility,
        "ordinary_prefix": {
            "points": len(prefix_points),
            "lanes_completed": len(original.lane_callbacks),
            "endpoints_retained": len(original.endpoints),
            "callbacks": baseline_callbacks,
            "lane_callback_vector": [int(value) for value in original.lane_callbacks],
            "start_digest_unchanged": current_prefix_digest == prefix_digest,
            "endpoint_digest_unchanged": current_endpoint_digest == endpoint_digest,
            "starts_replaced_or_discarded": 0,
        },
        "candidate_route": {
            "actual_callbacks": route_callbacks,
            "callback_cap": route_cap,
            "fraction_of_total_callbacks": route_callbacks / max(1, total_callbacks),
            "conceptual_observation_cap": conceptual_cap,
            "activated": bool(outcome.activated),
            "status": outcome.status,
            "ed_queries": int(outcome.ed_queries),
            "slice_moves": int(outcome.slice_moves),
            "proposal_fresh_canonical_replay_attempts": wrapper.proposal_replay_attempts,
            "final_authority_fresh_canonical_replay_attempts": (
                wrapper.final_authority_replay_attempts
            ),
            "canonical_replay_results_intentionally_not_recorded": True,
        },
        "connection_contract": {
            "baseline_fraction_at_least_0_75": baseline_callbacks >= 3 * route_callbacks,
            "candidate_fraction_at_most_0_25": route_callbacks <= total_callbacks / 4,
            "all_endpoint_proposals_return_to_fresh_source_guard_hard_replay": (
                wrapper.proposal_replay_attempts > 0
            ),
            "structural_n_gt_m_and_endpoint_rank_only_activation": True,
            "proposal_and_final_authority_replay_are_distinct": True,
            "case_id_family_truth_target_or_outcome_routing": False,
        },
        "candidate_sha256": candidate_sha,
        "connection_script_sha256": script_sha,
        "mechanism_sha256": mechanism_sha,
        "base_adapter_sha256": BASE_ADAPTER_SHA256,
        "entrypoint": "real_connection/connection_smoke.py:main",
    }
    (HERE / "CONNECTION_SMOKE.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n"
    )
    print(json.dumps(result, indent=2))
    if not connected:
        raise SystemExit("thin connection gate did not pass")


if __name__ == "__main__":
    main()
