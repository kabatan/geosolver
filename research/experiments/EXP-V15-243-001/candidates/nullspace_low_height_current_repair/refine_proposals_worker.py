"""Refine one development case into non-authoritative exact-value proposals.

The three precision lanes start independently from the same Float64 endpoint.
Nothing produced here is truth, an exact DSL replay, or a completeness proof.
"""

from __future__ import annotations

import argparse
from fractions import Fraction
import hashlib
import json
import math
import os
import sys
import tempfile
import time
from dataclasses import dataclass
from functools import reduce
from math import gcd
from pathlib import Path

import numpy as np

from mpmath import mp

CURRENT_RUNTIME_ROOT = Path(
    os.environ.get(
        "GEOTARGET_CURRENT_RUNTIME_ROOT",
        "/home/kabatan/work/solver-experiment-runtime/solver",
    )
).resolve()
CURRENT_REFINER_ROOT = CURRENT_RUNTIME_ROOT / "research/experiments/EXP-REAL61-001"
if str(CURRENT_REFINER_ROOT) not in sys.path:
    sys.path.insert(0, str(CURRENT_REFINER_ROOT))
from legacy61_runtime import LEGACY_SOURCE, load_legacy_runtime
from exact_transport import exact_transport


@dataclass(frozen=True)
class RankAdaptiveLane:
    x_hp: tuple
    residual_norm_hp: object
    answer_hp: object
    hard_feasible: bool
    method: str = "rank_adaptive_minimum_norm_newton"
    working_dps: int = 0


def _install_legacy_imports():
    load_problem_bundle, build_ir_evaluator, _infer, _penalty = load_legacy_runtime()
    if str(LEGACY_SOURCE) not in sys.path:
        sys.path.insert(0, str(LEGACY_SOURCE))
    from geosolver._internal.pipeline.contracts.candidate_record import FloatCandidate
    from geosolver._internal.pipeline.evaluator.classify_evaluation_failure import (
        EvaluationStatus,
    )
    from geosolver._internal.pipeline.refine.mpmath_refiner import (
        MpmathRefiner,
        TARGET_REACHED,
    )
    from geosolver._internal.pipeline.refine.refiner_config import RefinerConfig

    class _GateRefinerConfig(RefinerConfig):
        targets = {50: "1e-20", 100: "1e-50", 155: "1e-100", 232: "1e-150", 320: "1e-200"}

        def target_for_dps(self, dps: int):
            try:
                return self.targets[int(dps)]
            except KeyError as error:
                raise ValueError(f"unsupported exact-proposal dps: {dps}") from error

    return (
        load_problem_bundle,
        build_ir_evaluator,
        FloatCandidate,
        EvaluationStatus,
        MpmathRefiner,
        TARGET_REACHED,
        _GateRefinerConfig,
    )


def _write_atomic(path: Path, document: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as handle:
        json.dump(document, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
        temporary = Path(handle.name)
    os.replace(temporary, path)


def _seed_records(trial_paths: list[Path]) -> list[dict[str, object]]:
    candidates: list[dict[str, object]] = []
    for trial_path in trial_paths:
        trial = json.loads(trial_path.read_text(encoding="utf-8"))
        if trial.get("accuracy_claims_permitted") is not False:
            raise ValueError(f"unexpected claim authority in {trial_path}")
        for validation in trial.get("validations", []):
            endpoint = validation.get("endpoint")
            if not validation.get("safe") or not isinstance(endpoint, list):
                continue
            target = validation.get("diagnostic_target")
            try:
                numeric_target = float(str(target)) if target is not None else None
            except ValueError:
                numeric_target = None
            record = {
                "endpoint": [float(value) for value in endpoint],
                "residual_inf": float(validation["residual_inf"]),
                "diagnostic_group": str(target),
                "diagnostic_numeric": numeric_target,
                "source_candidate": trial["candidate"],
            }
            candidates.append(record)
    selected = []
    for record in sorted(candidates, key=lambda item: (item["diagnostic_numeric"] is None, item["diagnostic_numeric"] or 0.0, item["residual_inf"])):
        numeric = record["diagnostic_numeric"]
        match = next(
            (
                existing
                for existing in selected
                if numeric is not None
                and existing["diagnostic_numeric"] is not None
                and math.isclose(
                    numeric,
                    existing["diagnostic_numeric"],
                    rel_tol=1.0e-8,
                    abs_tol=1.0e-8,
                )
            ),
            None,
        )
        if match is None:
            selected.append(record)
        elif record["residual_inf"] < match["residual_inf"]:
            selected[selected.index(match)] = record
    return selected


def _lane(
    *,
    dps: int,
    bundle,
    evaluator,
    float_candidate,
    config_class,
    refiner_class,
    target_reached: str,
):
    config = config_class(
        schedule_dps=(50, 100, dps),
        closure_schedule_dps=(dps,),
        direct_accept_residual=None,
        direct_accept_dps=dps,
        dedup_answer_tolerance=mp.mpf("1e-110"),
    )
    batch = refiner_class(config=config).refine_candidates(
        bundle=bundle,
        evaluator=evaluator,
        candidates=(float_candidate,),
    )
    threshold = mp.mpf(config.target_for_dps(dps))
    accepted = [
        candidate
        for candidate in batch.candidates
        if candidate.refinement_status == target_reached
        and candidate.hard_feasible
        and candidate.answer_hp is not None
        and candidate.residual_norm_hp <= threshold
        and _guard_passes(
            evaluator,
            candidate.x_hp,
            dps=dps,
        )
    ]
    if not accepted:
        return _rank_adaptive_lane(
            dps=dps,
            bundle=bundle,
            evaluator=evaluator,
            float_candidate=float_candidate,
            target=threshold,
        )
    return min(accepted, key=lambda candidate: candidate.residual_norm_hp)


def _guard_passes(evaluator, point, *, dps: int) -> bool:
    """Replay the frozen source guard at a lane's final HP coordinates."""

    from geosolver._internal.solver.precision.type_guards.high_precision_mode import (
        high_precision_mode,
    )

    try:
        with mp.workdps(max(50, int(dps))), high_precision_mode():
            guard_ok, _violations = evaluator.evaluate_guard(list(point))
    except (ArithmeticError, LookupError, RuntimeError, TypeError, ValueError):
        return False
    return bool(guard_ok)


def _nominal_lane_source_replay(
    evaluator,
    lane,
    *,
    dps: int,
    residual_target,
) -> dict[str, object]:
    """Replay source semantics at the advertised lane, not solver work dps."""

    from geosolver._internal.solver.precision.type_guards.high_precision_mode import (
        high_precision_mode,
    )

    record: dict[str, object] = {
        "replay_decimal_digits": int(dps),
        "guard_replay_decimal_digits": int(dps),
        "hard_feasibility_replay_decimal_digits": int(dps),
        "residual_replay_decimal_digits": int(dps),
        "answer_replay_decimal_digits": int(dps),
        "residual_threshold": str(residual_target),
        "guard_ok": False,
        "hard_feasible": False,
        "residual_reached": False,
        "answer_defined": False,
    }
    try:
        with mp.workdps(int(dps)), high_precision_mode():
            point_at_lane = [mp.mpf(value) for value in lane.x_hp]
            observation = evaluator.evaluate_hp_residual(
                point_at_lane,
                precision=int(dps),
            )
            guard_ok, _violations = evaluator.evaluate_guard(point_at_lane)
            hard = evaluator.evaluate_hp_hard_feasibility(
                point_at_lane,
                precision=int(dps),
            )
            answer = evaluator.evaluate_answer_hp(
                point_at_lane,
                precision=int(dps),
            )
            record.update(
                {
                    "guard_ok": bool(guard_ok),
                    "hard_feasible": bool(hard.hard_feasible),
                    "residual_reached": bool(
                        observation.is_finite
                        and observation.residual_norm_hp
                        <= mp.mpf(residual_target)
                    ),
                    "answer_defined": answer.answer_hp is not None,
                }
            )
    except (ArithmeticError, LookupError, RuntimeError, TypeError, ValueError):
        pass
    return record


def _rank_adaptive_lane(*, dps: int, bundle, evaluator, float_candidate, target):
    """Arbitrary-precision minimum-norm Newton for square/manifold endpoints."""

    from geosolver._internal.solver.precision.type_guards.high_precision_mode import (
        high_precision_mode,
    )

    # A singular residual may vanish quadratically in the coordinate error.
    # Double working precision and square the ordinary residual target so the
    # requested target-coordinate accuracy is not inferred from residual alone.
    working_dps = 2 * dps + 20
    effective_target = mp.mpf(target) ** 2
    with mp.workdps(working_dps), high_precision_mode():
        point = [mp.mpf(str(value)) for value in float_candidate.x_float]
        if not point:
            observation = evaluator.evaluate_hp_residual(point, precision=working_dps)
            answer = evaluator.evaluate_answer_hp(point, precision=working_dps)
            hard = evaluator.evaluate_hp_hard_feasibility(point, precision=working_dps)
            if (
                observation.is_finite
                and observation.residual_norm_hp <= effective_target
                and answer.answer_hp is not None
                and hard.hard_feasible
                and _guard_passes(evaluator, point, dps=working_dps)
            ):
                return RankAdaptiveLane(
                    tuple(point),
                    observation.residual_norm_hp,
                    answer.answer_hp,
                    True,
                    working_dps=working_dps,
                )
            return None
        # Multiple roots can converge only linearly under a pseudoinverse step;
        # the precision-scaled cap is the single general singular rescue lane.
        for _iteration in range(max(80, 2 * working_dps)):
            observation = evaluator.evaluate_hp_residual(point, precision=working_dps)
            if not observation.is_finite:
                return None
            residual = [mp.mpf(value) for value in observation.residual_vector]
            norm = max((abs(value) for value in residual), default=mp.mpf("0"))
            if norm <= effective_target:
                hard = evaluator.evaluate_hp_hard_feasibility(point, precision=working_dps)
                guard_ok, _violations = evaluator.evaluate_guard(point)
                answer = evaluator.evaluate_answer_hp(point, precision=working_dps)
                if hard.hard_feasible and guard_ok and answer.answer_hp is not None:
                    return RankAdaptiveLane(
                        tuple(point),
                        norm,
                        answer.answer_hp,
                        True,
                        working_dps=working_dps,
                    )
                return None
            rows, columns = len(residual), len(point)
            jacobian = mp.matrix(rows, columns)
            step_exponent = max(20, working_dps // 3)
            for column in range(columns):
                step = mp.power(10, -step_exponent) * max(mp.mpf("1"), abs(point[column]))
                plus, minus = list(point), list(point)
                plus[column] += step
                minus[column] -= step
                plus_eval = evaluator.evaluate_hp_residual(plus, precision=working_dps)
                minus_eval = evaluator.evaluate_hp_residual(minus, precision=working_dps)
                if not plus_eval.is_finite or not minus_eval.is_finite:
                    return None
                for row in range(rows):
                    jacobian[row, column] = (
                        mp.mpf(plus_eval.residual_vector[row])
                        - mp.mpf(minus_eval.residual_vector[row])
                    ) / (2 * step)
            try:
                left, singular_values, right = mp.svd(jacobian)
            except (ValueError, ZeroDivisionError):
                return None
            if len(singular_values) == 0:
                return None
            largest = max(abs(value) for value in singular_values)
            cutoff = largest * mp.power(10, -(working_dps // 3))
            correction = [mp.mpf("0") for _ in range(columns)]
            used_rank = 0
            for index, singular in enumerate(singular_values):
                if abs(singular) <= cutoff:
                    continue
                projection = mp.fsum(left[row, index] * residual[row] for row in range(rows))
                coefficient = -projection / singular
                for column in range(columns):
                    correction[column] += right[index, column] * coefficient
                used_rank += 1
            if used_rank == 0:
                return None
            improved = False
            trial_scales = (mp.mpf("2"), mp.mpf("1.5")) + tuple(
                mp.power(2, -backtrack) for backtrack in range(16)
            )
            best_trial = None
            best_trial_norm = norm
            for scale in trial_scales:
                trial = [point[index] + scale * correction[index] for index in range(columns)]
                trial_eval = evaluator.evaluate_hp_residual(trial, precision=working_dps)
                if trial_eval.is_finite and trial_eval.residual_norm_hp < best_trial_norm:
                    best_trial = trial
                    best_trial_norm = trial_eval.residual_norm_hp
            if best_trial is not None:
                point = best_trial
                improved = True
            if not improved:
                return None
    return None


def _normalize_relation(relation) -> list[int] | None:
    coefficients = [int(value) for value in reversed(relation)]
    if not coefficients or not any(coefficients):
        return None
    common = reduce(gcd, (abs(value) for value in coefficients if value), 0)
    if common > 1:
        coefficients = [value // common for value in coefficients]
    if coefficients[0] < 0:
        coefficients = [-value for value in coefficients]
    return coefficients


def _owned_pslq(value, *, dps: int = 232, max_degree: int = 8, max_coeff: int = 10**8):
    with mp.workdps(dps):
        if abs(value) <= mp.mpf("1e-120"):
            return [1, 0]
        for degree in range(1, max_degree + 1):
            try:
                relation = mp.pslq(
                    [value**power for power in range(degree + 1)],
                    tol=mp.mpf("1e-120"),
                    maxcoeff=max_coeff,
                    maxsteps=20_000,
                )
            except ValueError:
                relation = None
            if relation is not None:
                return _normalize_relation(relation)
    return None


def _polynomial_value(coefficients: list[int], value):
    total = mp.mpf("0")
    for coefficient in coefficients:
        total = total * value + coefficient
    return total


def _polynomial_metadata(coefficients: list[int], numeric_value) -> dict[str, object]:
    try:
        import sympy as sp

        symbol = sp.Symbol("x")
        polynomial = sp.Poly.from_list(coefficients, gens=symbol, domain=sp.ZZ)
        square_free = bool(polynomial.is_sqf)
        irreducible = bool(polynomial.is_irreducible)
        selected_interval = None
        if square_free and irreducible:
            for interval, multiplicity in polynomial.intervals(eps=sp.Rational(1, 10**110)):
                left, right = interval
                left_mp = mp.mpf(int(left.p)) / int(left.q)
                right_mp = mp.mpf(int(right.p)) / int(right.q)
                contains_numeric = left_mp <= numeric_value <= right_mp
                if left_mp == right_mp:
                    contains_numeric = abs(numeric_value - left_mp) <= mp.mpf("1e-100")
                if contains_numeric:
                    selected_interval = {
                        "left": str(left),
                        "right": str(right),
                        "multiplicity": int(multiplicity),
                    }
                    break
        return {
            "square_free": square_free,
            "irreducible_over_Q": irreducible,
            "isolating_interval": selected_interval,
        }
    except Exception as error:
        return {
            "square_free": False,
            "irreducible_over_Q": False,
            "isolating_interval": None,
            "metadata_error": f"{type(error).__name__}: {error}",
        }


def _mp_text(value, digits: int) -> str:
    return mp.nstr(value, n=digits, strip_zeros=False)


def _configuration_proposals(lane768, lane1024):
    descriptors = []
    for approximation, confirmation in zip(lane768.x_hp, lane1024.x_hp, strict=True):
        coefficients = _owned_pslq(approximation)
        residual = None
        metadata = None
        if coefficients is not None:
            with mp.workdps(320):
                residual = abs(_polynomial_value(coefficients, confirmation))
            metadata = _polynomial_metadata(coefficients, confirmation)
        accepted = bool(
            coefficients is not None
            and residual is not None
            and residual <= mp.mpf("1e-180")
            and metadata["square_free"]
            and metadata["irreducible_over_Q"]
            and metadata["isolating_interval"] is not None
        )
        descriptors.append(
            {
                "status": "ALGEBRAIC_PROPOSAL" if accepted else "UNRECOGNIZED",
                "coefficients_high_to_low": coefficients,
                "confirmation_residual": None if residual is None else _mp_text(residual, 220),
                "polynomial_metadata": metadata,
            }
        )
    return descriptors


MAX_TRANSPORT_PROPOSALS = 4
MAX_RATIONAL_DENOMINATOR = 16
RANK_RATIO_THRESHOLD = 1.0e-8
# Quarantined direct-copy prototype only.  The 337-claim adversary invalidated
# this approximate boundary; main() routes exclusively through exact_transport.


def _float_residual(evaluator, point, evaluation_status):
    observation = evaluator.evaluate_float_residual(tuple(float(x) for x in point))
    if observation.evaluation_status is not evaluation_status.OK:
        return None
    value = np.asarray(observation.residual_vector, dtype=float)
    return value if value.ndim == 1 and np.all(np.isfinite(value)) else None


def _jacobian(evaluator, point, evaluation_status, *, step_factor):
    base = _float_residual(evaluator, point, evaluation_status)
    if base is None:
        return None
    answer = np.empty((len(base), len(point)), dtype=float)
    for column in range(len(point)):
        step = step_factor * 1.0e-6 * max(1.0, abs(float(point[column])))
        plus, minus = list(point), list(point)
        plus[column] += step
        minus[column] -= step
        left = _float_residual(evaluator, plus, evaluation_status)
        right = _float_residual(evaluator, minus, evaluation_status)
        if left is None or right is None:
            return None
        answer[:, column] = (left - right) / (2.0 * step)
    return answer


def _stable_free_chart(document, evaluator, endpoint, evaluation_status):
    dimension = len(endpoint)
    bounds = document.get("bounds")
    if dimension < 2:
        return None, {"status": "UNSUPPORTED_DIMENSION"}
    if not isinstance(bounds, list) or len(bounds) != dimension:
        return None, {"status": "SOURCE_BOUNDS_UNSUPPORTED"}
    column_scales = np.asarray(
        [
            max(
                1.0,
                abs(float(endpoint[index])),
                abs(float(pair[1]) - float(pair[0])),
            )
            for index, pair in enumerate(bounds)
            if isinstance(pair, list) and len(pair) == 2
        ],
        dtype=float,
    )
    if len(column_scales) != dimension:
        return None, {"status": "SOURCE_BOUNDS_UNSUPPORTED"}
    vectors, ratios = [], []
    for step_factor in (1.0, 0.5):
        raw = _jacobian(
            evaluator, endpoint, evaluation_status, step_factor=step_factor
        )
        if raw is None:
            return None, {"status": "JACOBIAN_UNDEFINED"}
        scaled = raw * column_scales[None, :]
        row_norms = np.linalg.norm(scaled, axis=1)
        keep = row_norms > 1.0e-14
        if not np.any(keep):
            return None, {"status": "ZERO_RANK"}
        scaled = scaled[keep] / row_norms[keep, None]
        for row_order in (scaled, scaled[::-1]):
            try:
                _left, singular, right = np.linalg.svd(
                    row_order, full_matrices=True
                )
            except np.linalg.LinAlgError:
                return None, {"status": "SVD_FAILED"}
            largest = float(singular[0]) if len(singular) else 0.0
            rank = int(
                np.count_nonzero(singular > largest * RANK_RATIO_THRESHOLD)
            )
            if largest <= 1.0e-14 or rank != dimension - 1:
                return None, {
                    "status": "FULL_RANK_OR_MULTIPLE_NULLITY",
                    "rank": rank,
                }
            physical = column_scales * right[-1]
            physical /= np.linalg.norm(physical)
            vectors.append(physical)
            previous = float(singular[rank - 1])
            tail = float(singular[rank]) if rank < len(singular) else 0.0
            ratios.append(tail / previous if previous > 0.0 else math.inf)
    reference = vectors[0]
    free_coordinate = int(np.argmax(np.abs(reference)))
    stable = all(
        int(np.argmax(np.abs(vector))) == free_coordinate
        and abs(float(np.dot(reference, vector))) >= 0.98
        for vector in vectors[1:]
    )
    if not stable or max(ratios) > RANK_RATIO_THRESHOLD:
        return None, {"status": "RANK_CHART_UNSTABLE"}
    return free_coordinate, {
        "status": "STABLE_CORANK_ONE",
        "rank": dimension - 1,
        "nullity": 1,
        "free_coordinate": free_coordinate,
        "rank_ratio": max(ratios),
        "step_factors": [1.0, 0.5],
        "row_permutations": ["identity", "reverse"],
        "row_scaled": True,
        "column_scaled": True,
    }


def _rational_slices(initial, lower, upper):
    radius = min(
        0.25 * max(0.0, upper - lower),
        max(0.1, 0.25 * max(1.0, abs(initial))),
    )
    values = set()
    for denominator in range(1, MAX_RATIONAL_DENOMINATOR + 1):
        center = round(initial * denominator)
        for numerator in range(center - 1, center + 2):
            value = Fraction(numerator, denominator)
            numeric = float(value)
            if lower < numeric < upper and abs(numeric - initial) <= radius:
                values.add(value)
    return sorted(
        values,
        key=lambda value: (
            value.denominator + abs(value.numerator),
            abs(float(value) - initial),
            value.denominator,
            value.numerator,
        ),
    )[:MAX_TRANSPORT_PROPOSALS]


def _range_newton(
    evaluator, endpoint, evaluation_status, free_coordinate, free_value, bounds
):
    point = np.asarray(endpoint, dtype=float).copy()
    point[free_coordinate] = float(free_value)
    dependent = [index for index in range(len(point)) if index != free_coordinate]
    for _iteration in range(16):
        residual = _float_residual(evaluator, point, evaluation_status)
        if residual is None:
            return None
        norm = float(np.max(np.abs(residual))) if len(residual) else 0.0
        if norm <= 1.0e-10:
            break
        jacobian = _jacobian(
            evaluator, point, evaluation_status, step_factor=1.0
        )
        if jacobian is None:
            return None
        try:
            correction, *_ = np.linalg.lstsq(
                jacobian[:, dependent], -residual, rcond=1.0e-10
            )
        except np.linalg.LinAlgError:
            return None
        improved = False
        for scale in (1.0, 0.5, 0.25, 0.125):
            trial = point.copy()
            trial[dependent] += scale * correction
            trial[free_coordinate] = float(free_value)
            if any(
                not (float(pair[0]) < trial[index] < float(pair[1]))
                for index, pair in enumerate(bounds)
            ):
                continue
            guard_ok, _violations = evaluator.evaluate_guard(trial.tolist())
            hard = evaluator.evaluate_float_hard_feasibility(trial.tolist())
            trial_residual = _float_residual(
                evaluator, trial, evaluation_status
            )
            trial_norm = (
                float(np.max(np.abs(trial_residual)))
                if trial_residual is not None and len(trial_residual)
                else 0.0
            )
            if guard_ok and hard.hard_feasible and trial_residual is not None and trial_norm < norm:
                point, improved = trial, True
                break
        if not improved:
            return None
    residual = _float_residual(evaluator, point, evaluation_status)
    guard_ok, _violations = evaluator.evaluate_guard(point.tolist())
    hard = evaluator.evaluate_float_hard_feasibility(point.tolist())
    if (
        residual is None
        or (len(residual) and float(np.max(np.abs(residual))) > 1.0e-10)
        or not guard_ok
        or not hard.hard_feasible
    ):
        return None
    return tuple(float(value) for value in point)


def _transport_endpoints(document, evaluator, endpoint, evaluation_status):
    raise RuntimeError("float Jacobian transport is disabled; exact source proof required")
    free_coordinate, rank = _stable_free_chart(
        document, evaluator, endpoint, evaluation_status
    )
    if free_coordinate is None:
        return [], rank
    bounds = document["bounds"]
    lower, upper = map(float, bounds[free_coordinate])
    proposals = []
    for value in _rational_slices(endpoint[free_coordinate], lower, upper):
        transported = _range_newton(
            evaluator,
            endpoint,
            evaluation_status,
            free_coordinate,
            value,
            bounds,
        )
        if transported is not None:
            proposals.append((value, transported))
    return proposals, {
        **rank,
        "status": "TRANSPORT_PROPOSED" if proposals else "NO_GUARD_SAFE_TRANSPORT",
        "proposal_count": len(proposals),
        "maximum_proposals": MAX_TRANSPORT_PROPOSALS,
        "maximum_denominator": MAX_RATIONAL_DENOMINATOR,
        "routing_uses_target_answer_id_family_or_outcome": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", type=Path, required=True)
    parser.add_argument("--case-sha256", required=True)
    parser.add_argument("--trial", type=Path, action="append", default=[])
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    payload = arguments.case.read_bytes()
    if hashlib.sha256(payload).hexdigest() != arguments.case_sha256:
        raise SystemExit("case source hash mismatch")
    document = json.loads(payload)
    if document.get("task") != "solve":
        raise SystemExit("exact proposals are solve-only")
    (
        load_problem_bundle,
        build_ir_evaluator,
        float_candidate_class,
        evaluation_status,
        refiner_class,
        target_reached,
        config_class,
    ) = _install_legacy_imports()
    bundle = load_problem_bundle(document, prefer_fast=False)
    evaluator = build_ir_evaluator(bundle)
    seeds = _seed_records(arguments.trial)
    proposals = []
    started = time.monotonic()
    for candidate_id, seed in enumerate(seeds):
        endpoint = tuple(float(value) for value in seed["endpoint"])
        if len(endpoint) != len(bundle.var_names) or not all(math.isfinite(value) for value in endpoint):
            continue
        observation = evaluator.evaluate_float_residual(endpoint)
        guard_ok, _guard_violations = evaluator.evaluate_guard(endpoint)
        hard = evaluator.evaluate_float_hard_feasibility(endpoint)
        if observation.evaluation_status is not evaluation_status.OK or not guard_ok or not hard.hard_feasible:
            continue
        float_source_replay = {
            "evaluation_defined": True,
            "guard_ok": True,
            "hard_feasible": True,
            "residual_inf": float(observation.residual_norm_float),
            "residual_is_authority": False,
        }
        float_candidate = float_candidate_class(
            x_float=endpoint,
            score=0.5 * float(observation.residual_norm_float) ** 2,
            residual_norm_float=float(observation.residual_norm_float),
            guard_ok=bool(guard_ok),
            evaluation_status=observation.evaluation_status,
            origin_seed=0,
            origin_start_point_index=candidate_id,
            candidate_id=candidate_id,
            hard_feasible=bool(hard.hard_feasible),
            hard_violation_tags=tuple(hard.failure_tags),
            validity_margin_float=(None if hard.min_margin is None else float(hard.min_margin)),
        )
        lanes = {
            dps: _lane(
                dps=dps,
                bundle=bundle,
                evaluator=evaluator,
                float_candidate=float_candidate,
                config_class=config_class,
                refiner_class=refiner_class,
                target_reached=target_reached,
            )
            for dps in (155, 232, 320)
        }
        if os.environ.get("GEOTARGET_D0_FORCE_BASELINE_REFINEMENT_FAILURE") == "1":
            lanes = {155: None, 232: None, 320: None}
        transport_record = None
        if any(lanes[dps] is None for dps in lanes):
            transported_points, rank_record = exact_transport(document, endpoint)
            transported = [
                (
                    Fraction(point[int(rank_record["free_coordinate"])]).limit_denominator(
                        MAX_RATIONAL_DENOMINATOR
                    ),
                    point,
                )
                for point in transported_points
            ]
            original_endpoint = endpoint
            for ordinal, (rational_slice, transported_endpoint) in enumerate(
                transported
            ):
                transported_observation = evaluator.evaluate_float_residual(
                    transported_endpoint
                )
                transported_guard, _violations = evaluator.evaluate_guard(
                    transported_endpoint
                )
                transported_hard = evaluator.evaluate_float_hard_feasibility(
                    transported_endpoint
                )
                if (
                    transported_observation.evaluation_status
                    is not evaluation_status.OK
                    or not transported_guard
                    or not transported_hard.hard_feasible
                ):
                    continue
                transported_candidate = float_candidate_class(
                    x_float=transported_endpoint,
                    score=0.5
                    * float(transported_observation.residual_norm_float) ** 2,
                    residual_norm_float=float(
                        transported_observation.residual_norm_float
                    ),
                    guard_ok=True,
                    evaluation_status=transported_observation.evaluation_status,
                    origin_seed=0,
                    origin_start_point_index=candidate_id,
                    candidate_id=candidate_id * MAX_TRANSPORT_PROPOSALS + ordinal + 1,
                    hard_feasible=True,
                    hard_violation_tags=tuple(transported_hard.failure_tags),
                    validity_margin_float=(
                        None
                        if transported_hard.min_margin is None
                        else float(transported_hard.min_margin)
                    ),
                )
                transported_lanes = {
                    dps: _lane(
                        dps=dps,
                        bundle=bundle,
                        evaluator=evaluator,
                        float_candidate=transported_candidate,
                        config_class=config_class,
                        refiner_class=refiner_class,
                        target_reached=target_reached,
                    )
                    for dps in (155, 232, 320)
                }
                if any(
                    transported_lanes[dps] is None for dps in transported_lanes
                ):
                    continue
                endpoint = transported_endpoint
                float_candidate = transported_candidate
                lanes = transported_lanes
                float_source_replay = {
                    "evaluation_defined": True,
                    "guard_ok": True,
                    "hard_feasible": True,
                    "residual_inf": float(
                        transported_observation.residual_norm_float
                    ),
                    "residual_is_authority": False,
                }
                transport_record = {
                    **rank_record,
                    "status": "TRANSPORT_HP_LANES_READY",
                    "selected_proposal_ordinal": ordinal,
                    "free_slice_numerator": rational_slice.numerator,
                    "free_slice_denominator": rational_slice.denominator,
                    "original_endpoint": list(original_endpoint),
                    "transported_endpoint": list(transported_endpoint),
                    "three_independent_hp_lanes_required": True,
                }
                break
            if any(lanes[dps] is None for dps in lanes):
                proposals.append(
                    {
                        "source": seed,
                        "status": "REFINEMENT_INCOMPLETE",
                        "successful_lanes_dps": [
                            dps for dps, lane in lanes.items() if lane is not None
                        ],
                        "nullspace_transport": rank_record,
                    }
                )
                continue
        lane512, lane768, lane1024 = lanes[155], lanes[232], lanes[320]
        lane_source_replay = {
            str(dps): _nominal_lane_source_replay(
                evaluator,
                lane,
                dps=dps,
                residual_target=config_class().target_for_dps(dps),
            )
            for dps, lane in lanes.items()
        }
        if not all(
            record
            == {
                "replay_decimal_digits": int(key),
                "guard_replay_decimal_digits": int(key),
                "hard_feasibility_replay_decimal_digits": int(key),
                "residual_replay_decimal_digits": int(key),
                "answer_replay_decimal_digits": int(key),
                "residual_threshold": config_class().target_for_dps(int(key)),
                "guard_ok": True,
                "hard_feasible": True,
                "residual_reached": True,
                "answer_defined": True,
            }
            for key, record in lane_source_replay.items()
        ):
            proposals.append(
                {
                    "source": seed,
                    "status": "SOURCE_REPLAY_INCOMPLETE",
                    "lane_source_replay": lane_source_replay,
                }
            )
            continue
        with mp.workdps(320):
            answer_disagreement = abs(lane512.answer_hp - lane768.answer_hp)
            coordinate_disagreement = max(
                (abs(left - right) for left, right in zip(lane512.x_hp, lane768.x_hp, strict=True)),
                default=mp.mpf("0"),
            )
        coefficients = _owned_pslq(lane768.answer_hp)
        pslq_residual = None
        polynomial_metadata = None
        if coefficients is not None:
            with mp.workdps(320):
                pslq_residual = abs(_polynomial_value(coefficients, lane1024.answer_hp))
            polynomial_metadata = _polynomial_metadata(coefficients, lane1024.answer_hp)
        numeric_gate = bool(answer_disagreement <= mp.mpf("1e-100"))
        relation_gate = bool(
            coefficients is not None
            and pslq_residual is not None
            and pslq_residual <= mp.mpf("1e-180")
            and polynomial_metadata["square_free"]
            and polynomial_metadata["irreducible_over_Q"]
            and polynomial_metadata["isolating_interval"] is not None
        )
        configuration_proposals = _configuration_proposals(lane768, lane1024)
        proposals.append(
            {
                "source": seed,
                "nullspace_transport": transport_record,
                "status": "PSLQ_PROPOSAL" if numeric_gate and relation_gate else "NUMERIC_ONLY",
                "independent_precision_lanes": True,
                "float_source_replay": float_source_replay,
                "lane_methods": {
                    str(dps): getattr(lane, "method", "legacy_staged_mpmath_lm")
                    for dps, lane in lanes.items()
                },
                "lane_working_decimal_digits": {
                    str(dps): int(getattr(lane, "working_dps", dps) or dps)
                    for dps, lane in lanes.items()
                },
                "lane_source_replay": lane_source_replay,
                "answer_512bit_minimum": _mp_text(lane512.answer_hp, 155),
                "answer_768bit_minimum": _mp_text(lane768.answer_hp, 232),
                "answer_1024bit_minimum": _mp_text(lane1024.answer_hp, 320),
                "coordinates_768bit_minimum": [
                    _mp_text(value, 232) for value in lane768.x_hp
                ],
                "coordinates_1024bit_minimum": [
                    _mp_text(value, 320) for value in lane1024.x_hp
                ],
                "answer_512_768_disagreement": _mp_text(answer_disagreement, 120),
                "coordinate_512_768_disagreement_inf": _mp_text(coordinate_disagreement, 120),
                "numeric_gate_1e_100": numeric_gate,
                "pslq_coefficients_high_to_low": coefficients,
                "pslq_1024_lane_residual": (
                    None if pslq_residual is None else _mp_text(pslq_residual, 220)
                ),
                "polynomial_metadata": polynomial_metadata,
                "configuration_algebraic_proposals": configuration_proposals,
                "configuration_fully_recognized": all(
                    descriptor["status"] == "ALGEBRAIC_PROPOSAL"
                    for descriptor in configuration_proposals
                ),
                "original_dsl_exact_replay": "NOT_RUN",
                "target_image_completeness": "NOT_RUN",
                "exact_descriptor_authority": False,
            }
        )
    result = {
        "schema_version": "geotarget.real61-refined-proposals/v1",
        "authority": "DEVELOPMENT_PROPOSALS_ONLY",
        "truth_status": "NOT_MATERIALIZED",
        "accuracy_claims_permitted": False,
        "completeness_claims_permitted": False,
        "case_id": arguments.case.stem,
        "case_sha256": arguments.case_sha256,
        "input_seed_count": len(seeds),
        "proposals": proposals,
        "elapsed_wall_seconds": time.monotonic() - started,
    }
    _write_atomic(arguments.output, result)


if __name__ == "__main__":
    main()
