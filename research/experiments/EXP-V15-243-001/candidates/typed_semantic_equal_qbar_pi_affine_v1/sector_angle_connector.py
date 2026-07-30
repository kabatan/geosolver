"""Repair A plus sector-certified integer relations between direct angles."""

from __future__ import annotations

import copy
from fractions import Fraction
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time
from typing import Any, Mapping

import typed_replay_connector as repair_a


BASELINE_FRACTION = 0.75
SIDE_FRACTION = 0.25
ANGLE_FAILURE = "scalar is not an exact angle expression"
FAILURES = repair_a.FAILURES
ANGLE_BASELINE_FAILURES = (
    ANGLE_FAILURE,
    "angle equality has ambiguous full-turn lift",
)


_SECTOR_HELPERS = r'''

struct SectorAngleScale
  angle::AngleExpression
  factor::Int
end

function qx_sector_factor(value)::Int
  factor = if value isa Integer
    Int(value)
  elseif value isa Rational && denominator(value) == 1
    Int(numerator(value))
  elseif value isa QQFieldElem && denominator(value) == 1
    Int(numerator(value))
  else
    throw(ReplayFailure("sector angle coefficient is not an exact integer"))
  end
  1 <= factor <= 3 || throw(ReplayFailure("sector angle coefficient is outside 1:3"))
  return factor
end

function qx_sector_scale(first, second)
  first isa AngleExpression && second isa AngleExpression &&
    throw(ReplayFailure("angle-angle multiplication is outside sector authority"))
  if first isa AngleExpression
    return SectorAngleScale(first, qx_sector_factor(second))
  elseif second isa AngleExpression
    return SectorAngleScale(second, qx_sector_factor(first))
  end
  throw(ReplayFailure("sector scaling requires one direct angle"))
end

function qx_sector_unpack(value, asserted_factor::Int)
  1 <= asserted_factor <= 3 || throw(ReplayFailure("asserted sector coefficient is outside 1:3"))
  if value isa AngleExpression
    asserted_factor == 1 || throw(ReplayFailure("source/DAG direct-angle coefficient mismatch"))
    return value
  elseif value isa SectorAngleScale
    value.factor == asserted_factor || throw(ReplayFailure("source/DAG scaled-angle coefficient mismatch"))
    return value.angle
  end
  throw(ReplayFailure("sector relation operand is not a direct angle"))
end

function qx_unit_power(value::AngleExpression, factor::Int)
  cosine, sine = QB(1), QB(0)
  for _ in 1:factor
    cosine, sine = (
      cosine * value.cosine - sine * value.sine,
      sine * value.cosine + cosine * value.sine,
    )
  end
  return cosine, sine
end

function qx_sector_index(value::AngleExpression, factor::Int)::Int
  value.lower_pi == 0//1 && value.upper_pi == 1//1 ||
    throw(ReplayFailure("full-circle or nonprincipal angle domain"))
  value.cosine^2 + value.sine^2 == 1 ||
    throw(ReplayFailure("sector angle is not normalized unit complex"))
  value.sine >= 0 || throw(ReplayFailure("sector angle has negative sine"))
  thresholds = QQBarFieldElem[
    cospi(to_qbar(BigInt(index) // BigInt(factor)))
    for index in 0:factor
  ]
  any(value.cosine == threshold for threshold in thresholds) &&
    throw(ReplayFailure("angle lies on a sector boundary or tie"))
  for index in 0:(factor - 1)
    thresholds[index + 2] < value.cosine < thresholds[index + 1] && return index
  end
  throw(ReplayFailure("angle has no unique exact sector"))
end

function qx_sector_certified_equal(first, first_factor::Int, second, second_factor::Int)::Bool
  left = qx_sector_unpack(first, first_factor)
  right = qx_sector_unpack(second, second_factor)
  left_sector = qx_sector_index(left, first_factor)
  right_sector = qx_sector_index(right, second_factor)
  left_sector == right_sector ||
    throw(ReplayFailure("scaled-angle equality has nonzero or ambiguous full-turn lift"))
  left_power = qx_unit_power(left, first_factor)
  right_power = qx_unit_power(right, second_factor)
  return left_power[1] == right_power[1] && left_power[2] == right_power[2]
end
'''


def patched_worker_source(base: Any) -> str:
    source = repair_a.patched_worker_source(base)
    angle_struct = '''struct AngleExpression
  cosine::QQBarFieldElem
  sine::QQBarFieldElem
  lower_pi::Rational{BigInt}
  upper_pi::Rational{BigInt}
end
'''
    if source.count(angle_struct) != 1:
        raise base.ExactCoordinateFailure("sector AngleExpression seam changed")
    source = source.replace(angle_struct, angle_struct + _SECTOR_HELPERS, 1)

    rejection = '''    (first isa AngleExpression || second isa AngleExpression) &&
      throw(ReplayFailure("angle scaling is outside typed equality"))
    first_pi, second_pi = qx_pi_runtime(first), qx_pi_runtime(second)
'''
    replacement = '''    if first isa AngleExpression || second isa AngleExpression
      return qx_sector_scale(first, second)
    elseif first isa SectorAngleScale || second isa SectorAngleScale
      throw(ReplayFailure("nested sector angle scaling is outside authority"))
    end
    first_pi, second_pi = qx_pi_runtime(first), qx_pi_runtime(second)
'''
    if source.count(rejection) != 1:
        raise base.ExactCoordinateFailure("sector multiplication seam changed")
    source = source.replace(rejection, replacement, 1)

    dispatch = '''    value = if operation == "typed_equal"
      arguments = [values[Int(index) + 1] for index in node["args"]]
      qx_typed_semantic_equal(arguments...)
'''
    sector_dispatch = '''    value = if operation == "sector_angle_equal"
      arguments = [values[Int(index) + 1] for index in node["args"]]
      multipliers = Int[Int(value) for value in node["multipliers"]]
      length(arguments) == 2 && length(multipliers) == 2 ||
        throw(ReplayFailure("malformed sector relation node"))
      qx_sector_certified_equal(arguments[1], multipliers[1], arguments[2], multipliers[2])
    elseif operation == "typed_equal"
      arguments = [values[Int(index) + 1] for index in node["args"]]
      qx_typed_semantic_equal(arguments...)
'''
    if source.count(dispatch) != 1:
        raise base.ExactCoordinateFailure("sector evaluator dispatch seam changed")
    source = source.replace(dispatch, sector_dispatch, 1)

    degree = '''  elseif value isa QPiAffine
    return Int[degree(value.coefficient), degree(value.offset)]
'''
    sector_degree = '''  elseif value isa SectorAngleScale
    return scalar_degrees(value.angle)
  elseif value isa QPiAffine
    return Int[degree(value.coefficient), degree(value.offset)]
'''
    if source.count(degree) != 1:
        raise base.ExactCoordinateFailure("sector degree-ledger seam changed")
    return source.replace(degree, sector_degree, 1)


def _rational_integer(nodes: list[Any], index: int) -> int | None:
    if not 0 <= index < len(nodes) or not isinstance(nodes[index], Mapping):
        return None
    node = nodes[index]
    if node.get("op") != "rational" or not isinstance(node.get("value"), str):
        return None
    try:
        value = Fraction(node["value"])
    except (ValueError, ZeroDivisionError):
        return None
    return value.numerator if value.denominator == 1 and 1 <= value <= 3 else None


def _direct_angle_node(nodes: list[Any], index: int) -> bool:
    return (
        0 <= index < len(nodes)
        and isinstance(nodes[index], Mapping)
        and nodes[index].get("op") == "call"
        and nodes[index].get("name") == "Angle"
        and isinstance(nodes[index].get("args"), list)
        and len(nodes[index]["args"]) in (2, 3)
        and nodes[index].get("kwargs") == {}
    )


def _verify_scaled_angle_node(nodes: list[Any], index: int, factor: int) -> bool:
    if factor == 1 and _direct_angle_node(nodes, index):
        return True
    if not 0 <= index < len(nodes) or not isinstance(nodes[index], Mapping):
        return False
    node = nodes[index]
    arguments = node.get("args")
    if node.get("op") != "mul" or not isinstance(arguments, list) or len(arguments) != 2:
        return False
    first, second = arguments
    return (
        _rational_integer(nodes, first) == factor and _direct_angle_node(nodes, second)
    ) or (
        _rational_integer(nodes, second) == factor and _direct_angle_node(nodes, first)
    )


def _annotated_job(base: Any, job: Mapping[str, Any], failure: str) -> dict[str, Any] | None:
    if failure != ANGLE_FAILURE:
        return repair_a._annotated_job(base, job, failure)
    eligibility = job.get("typed_semantic_eligible_relation_indices")
    indices = eligibility.get(failure) if isinstance(eligibility, Mapping) else None
    specs = job.get("sector_angle_relation_specs")
    if not isinstance(indices, list) or not indices or not isinstance(specs, Mapping):
        return None
    copied = copy.deepcopy(dict(job))
    roots, nodes = copied.get("relation_roots"), copied.get("nodes")
    if not isinstance(roots, list) or not isinstance(nodes, list):
        return None
    for relation_index in indices:
        if (
            not isinstance(relation_index, int)
            or isinstance(relation_index, bool)
            or not 0 <= relation_index < len(roots)
        ):
            return None
        spec = specs.get(str(relation_index), specs.get(relation_index))
        if (
            not isinstance(spec, list)
            and not isinstance(spec, tuple)
        ) or len(spec) != 2:
            return None
        first_factor, second_factor = spec
        if (
            not isinstance(first_factor, int)
            or isinstance(first_factor, bool)
            or not isinstance(second_factor, int)
            or isinstance(second_factor, bool)
            or not 1 <= first_factor <= 3
            or not 1 <= second_factor <= 3
        ):
            return None
        root_index = roots[relation_index]
        if not isinstance(root_index, int) or not 0 <= root_index < len(nodes):
            return None
        node = nodes[root_index]
        if not isinstance(node, Mapping) or node.get("op") != "sub":
            return None
        arguments = node.get("args")
        if not isinstance(arguments, list) or len(arguments) != 2:
            return None
        if not _verify_scaled_angle_node(nodes, arguments[0], first_factor):
            return None
        if not _verify_scaled_angle_node(nodes, arguments[1], second_factor):
            return None
        nodes[root_index] = {
            "op": "sector_angle_equal",
            "args": list(arguments),
            "multipliers": [first_factor, second_factor],
        }
    copied["typed_semantic_source_only"] = True
    copied["typed_semantic_failure_class"] = failure
    copied["typed_semantic_relation_count"] = len(indices)
    copied["sector_angle_q_zero_unique_required"] = True
    return copied


def _run_patched(base: Any, job: Mapping[str, Any], *, timeout_seconds: float) -> dict[str, Any]:
    affinity = sorted(os.sched_getaffinity(0))
    if len(affinity) != 1:
        raise base.ExactCoordinateFailure("sector side requires one pinned CPU")
    environment = os.environ.copy()
    environment.update(
        {
            "JULIA_NUM_THREADS": "1",
            "JULIA_NUM_GC_THREADS": "1",
            "OPENBLAS_NUM_THREADS": "1",
            "OMP_NUM_THREADS": "1",
            "MKL_NUM_THREADS": "1",
            "NUMEXPR_NUM_THREADS": "1",
        }
    )
    job_path: Path | None = None
    worker_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".json", delete=False) as stream:
            job_path = Path(stream.name)
            json.dump(job, stream, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".jl", delete=False) as stream:
            worker_path = Path(stream.name)
            stream.write(patched_worker_source(base))
        completed = subprocess.run(
            [
                "taskset", "-c", str(affinity[0]), "julia", "--compile=no",
                f"--project={base.JULIA_PROJECT}", "--startup-file=no", "--history-file=no",
                str(worker_path), str(job_path),
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=max(0.25, float(timeout_seconds)),
            env=environment,
            start_new_session=False,
            preexec_fn=repair_a._child_setup,
        )
    except subprocess.TimeoutExpired as error:
        raise base.ExactCoordinateFailure("sector-certified replay timed out") from error
    finally:
        job_path is not None and job_path.unlink(missing_ok=True)
        worker_path is not None and worker_path.unlink(missing_ok=True)
    if completed.returncode != 0:
        raise base.ExactCoordinateFailure("sector QQBar worker failed: " + completed.stderr[-300:])
    records = [line for line in completed.stdout.splitlines() if line.strip()]
    if len(records) != 1:
        raise base.ExactCoordinateFailure("sector QQBar worker emitted noncanonical output")
    result = json.loads(records[0])
    if not isinstance(result, dict):
        raise base.ExactCoordinateFailure("sector QQBar worker record is not an object")
    return result


def install(base: Any) -> None:
    if getattr(base, "_sector_angle_connector_installed", False):
        return
    baseline_run = base._run_qqbar

    def baseline_first(job: Mapping[str, Any], *, timeout_seconds: float) -> dict[str, Any]:
        total = float(timeout_seconds)
        baseline_budget = max(0.25, total * BASELINE_FRACTION)
        started = time.monotonic()
        baseline = baseline_run(job, timeout_seconds=baseline_budget)
        if not isinstance(baseline, Mapping) or baseline.get("status") != "EXACT_REPLAY_REJECTED":
            return baseline
        error = str(baseline.get("error", ""))
        if any(item in error for item in ANGLE_BASELINE_FAILURES):
            failure = ANGLE_FAILURE
        else:
            failure = next((item for item in FAILURES if item in error), None)
        if failure is None:
            return baseline
        annotated = _annotated_job(base, job, failure)
        if annotated is None:
            return baseline
        remaining = total - (time.monotonic() - started)
        side_budget = min(total * SIDE_FRACTION, remaining)
        if side_budget < 0.25:
            return baseline
        try:
            side = _run_patched(base, annotated, timeout_seconds=side_budget)
        except Exception:
            return baseline
        if side.get("status") != "EXACT_REPLAY_ACCEPTED":
            return baseline
        side.update(
            {
                "typed_semantic_equal_repair": True,
                "sector_certified_integer_angle_relation": failure == ANGLE_FAILURE,
                "typed_semantic_failure_class": failure,
                "typed_semantic_relation_count": annotated["typed_semantic_relation_count"],
                "baseline_exact_replay_ran_first": True,
                "baseline_budget_fraction": BASELINE_FRACTION,
                "typed_side_budget_fraction_maximum": SIDE_FRACTION,
                "sector_coefficients_closed_1_through_3": True,
                "sector_boundary_or_multiple_q_rejected": True,
                "canonical_rational_into_qbar_equality_only": True,
                "order_sign_or_unknown_broadening": False,
            }
        )
        return side

    base._run_qqbar = baseline_first
    base._sector_angle_baseline_run = baseline_run
    base._sector_angle_connector_installed = True
