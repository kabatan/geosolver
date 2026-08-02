"""Refine one development case into non-authoritative exact-value proposals.

The three precision lanes start independently from the same Float64 endpoint.
Nothing produced here is truth, an exact DSL replay, or a completeness proof.
"""

from __future__ import annotations

import argparse
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

from mpmath import mp

from legacy61_runtime import LEGACY_SOURCE, load_legacy_runtime


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
        if any(lanes[dps] is None for dps in lanes):
            proposals.append(
                {
                    "source": seed,
                    "status": "REFINEMENT_INCOMPLETE",
                    "successful_lanes_dps": [dps for dps, lane in lanes.items() if lane is not None],
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
