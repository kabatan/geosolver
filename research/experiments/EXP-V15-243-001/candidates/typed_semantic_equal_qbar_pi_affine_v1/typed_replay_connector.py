"""Baseline-first 75/25 connector into the copied exact QQBar replay."""

from __future__ import annotations

import copy
import ctypes
import json
import os
from pathlib import Path
import signal
import subprocess
import tempfile
import time
from typing import Any, Mapping


BASELINE_FRACTION = 0.75
SIDE_FRACTION = 0.25
MAX_AFFINE_NODES = 12
FAILURES = (
    "value is not exact rational",
    "scalar is not an exact angle expression",
)
PR_SET_PDEATHSIG = 1


_TYPED_HELPERS = r'''

# Candidate-private equality-only Qbar[pi] repair. pi remains transcendental;
# a*pi+b is zero exactly when its two algebraic coefficients are zero.
struct QPiAffine
  coefficient::QQBarFieldElem
  offset::QQBarFieldElem
  node_count::Int
end

qx_rational_runtime(value) = value isa Integer || value isa Rational || value isa QQFieldElem
qx_qbar_runtime(value) = value isa QQBarFieldElem
qx_pi_runtime(value) = value isa PiMultiple || value isa QPiAffine

function qx_algebraic_scalar(value)::QQBarFieldElem
  (qx_rational_runtime(value) || qx_qbar_runtime(value)) ||
    throw(ReplayFailure("typed affine scalar is not exact algebraic"))
  return to_qbar(value)
end

function qx_pi_affine(value)::QPiAffine
  result = if value isa QPiAffine
    value
  elseif value isa PiMultiple
    QPiAffine(to_qbar(value.coefficient), QB(0), 1)
  elseif qx_rational_runtime(value) || qx_qbar_runtime(value)
    QPiAffine(QB(0), to_qbar(value), 1)
  else
    throw(ReplayFailure("mixed value cannot enter typed Qbar[pi]"))
  end
  result.node_count <= 12 || throw(ReplayFailure("typed Qbar[pi] bound exceeded"))
  return result
end

function qx_affine_add(first, second, subtract::Bool)
  left, right = qx_pi_affine(first), qx_pi_affine(second)
  count = left.node_count + right.node_count + 1
  count <= 12 || throw(ReplayFailure("typed Qbar[pi] bound exceeded"))
  sign = subtract ? -1 : 1
  return QPiAffine(
    left.coefficient + sign * right.coefficient,
    left.offset + sign * right.offset,
    count,
  )
end

function qx_affine_scale(value, scalar, divide::Bool)
  affine = qx_pi_affine(value)
  factor = qx_algebraic_scalar(scalar)
  divide && iszero(factor) && throw(ReplayFailure("typed affine division by zero"))
  count = affine.node_count + 2
  count <= 12 || throw(ReplayFailure("typed Qbar[pi] bound exceeded"))
  if divide
    return QPiAffine(affine.coefficient / factor, affine.offset / factor, count)
  end
  return QPiAffine(affine.coefficient * factor, affine.offset * factor, count)
end

function qx_typed_semantic_equal(first, second)::Bool
  if qx_qbar_runtime(first) && qx_qbar_runtime(second)
    return first == second
  elseif qx_rational_runtime(first) && qx_rational_runtime(second)
    return to_qbar(first) == to_qbar(second)
  elseif (qx_qbar_runtime(first) && qx_rational_runtime(second)) ||
      (qx_rational_runtime(first) && qx_qbar_runtime(second))
    # The sole mixed rule: the unique canonical embedding Q -> Qbar, equality only.
    return to_qbar(first) == to_qbar(second)
  elseif first isa PiMultiple && second isa PiMultiple
    return first.coefficient == second.coefficient
  elseif first isa AngleExpression && second isa AngleExpression
    return first.lower_pi == second.lower_pi && first.upper_pi == second.upper_pi &&
      first.cosine == second.cosine && first.sine == second.sine
  elseif first isa QPiAffine && second isa QPiAffine
    return first.coefficient == second.coefficient && first.offset == second.offset
  end
  throw(ReplayFailure("typed equality rejects mixed or unknown runtime types"))
end
'''


_BINARY_OPERATION = r'''function binary_operation(name::String, first, second)
  if name == "add"
    (first isa AngleExpression || second isa AngleExpression) &&
      throw(ReplayFailure("nested angle arithmetic is outside typed equality"))
    if qx_pi_runtime(first) || qx_pi_runtime(second)
      return qx_affine_add(first, second, false)
    elseif first isa QPoint && second isa QPoint
      return qadd(first, second)
    end
    return first + second
  elseif name == "sub"
    (first isa AngleExpression || second isa AngleExpression) &&
      throw(ReplayFailure("nested angle arithmetic is outside typed equality"))
    if qx_pi_runtime(first) || qx_pi_runtime(second)
      return qx_affine_add(first, second, true)
    elseif first isa QPoint && second isa QPoint
      return qsub(first, second)
    end
    return first - second
  elseif name == "mul"
    first isa QPoint && return qscale(first, second)
    second isa QPoint && return qscale(second, first)
    (first isa AngleExpression || second isa AngleExpression) &&
      throw(ReplayFailure("angle scaling is outside typed equality"))
    first_pi, second_pi = qx_pi_runtime(first), qx_pi_runtime(second)
    first_pi && second_pi && throw(ReplayFailure("nonlinear pi product is outside affine authority"))
    if first_pi || second_pi
      pi_value, scalar = first_pi ? (first, second) : (second, first)
      if pi_value isa PiMultiple && qx_rational_runtime(scalar)
        return PiMultiple(pi_value.coefficient * qx_exact_rational(scalar))
      end
      return qx_affine_scale(pi_value, scalar, false)
    end
    return first * second
  elseif name == "div"
    first isa QPoint && return qdivide(first, second)
    (first isa AngleExpression || second isa AngleExpression) &&
      throw(ReplayFailure("angle division is outside typed equality"))
    qx_pi_runtime(second) && throw(ReplayFailure("division by pi is outside affine authority"))
    qx_pi_runtime(first) && return qx_affine_scale(first, second, true)
    return first / second
  elseif name == "pow"
    (qx_pi_runtime(first) || qx_pi_runtime(second)) &&
      throw(ReplayFailure("nonlinear pi power is outside affine authority"))
    second isa Rational && denominator(second) == 1 ||
      throw(ReplayFailure("only integer powers are supported"))
    return first^Int(numerator(second))
  end
  throw(ReplayFailure("unsupported binary operation"))
end

'''


def _child_setup() -> None:
    libc = ctypes.CDLL(None, use_errno=True)
    if libc.prctl(PR_SET_PDEATHSIG, signal.SIGKILL, 0, 0, 0) != 0:
        raise OSError(ctypes.get_errno(), "PR_SET_PDEATHSIG failed")


def patched_worker_source(base: Any) -> str:
    source = base._extended_worker_source()
    struct_marker = "struct AngleExpression\n"
    if source.count(struct_marker) != 1:
        raise base.ExactCoordinateFailure("typed AngleExpression seam changed")
    source = source.replace(struct_marker, _TYPED_HELPERS + "\n" + struct_marker, 1)

    binary_start = source.find("function binary_operation(name::String, first, second)\n")
    comparison_start = source.find("function comparison(name::String, first, second)\n")
    if binary_start < 0 or comparison_start <= binary_start:
        raise base.ExactCoordinateFailure("typed binary-operation seam changed")
    source = source[:binary_start] + _BINARY_OPERATION + source[comparison_start:]

    semantic_marker = "semantic_zero(value::Integer) = iszero(value)\n"
    if source.count(semantic_marker) != 1:
        raise base.ExactCoordinateFailure("typed semantic-zero seam changed")
    source = source.replace(
        semantic_marker,
        semantic_marker + "semantic_zero(value::Bool) = value\n",
        1,
    )

    eval_marker = '''    value = if operation == "coordinate"
'''
    if source.count(eval_marker) != 1:
        raise base.ExactCoordinateFailure("typed evaluator dispatch seam changed")
    source = source.replace(
        eval_marker,
        '''    value = if operation == "typed_equal"
      arguments = [values[Int(index) + 1] for index in node["args"]]
      qx_typed_semantic_equal(arguments...)
    elseif operation == "coordinate"
''',
        1,
    )

    neg_marker = '''      argument isa AngleExpression ? qangle_neg(argument) : -argument
'''
    neg_replacement = '''      if argument isa AngleExpression
        throw(ReplayFailure("nested angle negation is outside typed equality"))
      elseif argument isa PiMultiple
        PiMultiple(-argument.coefficient)
      elseif argument isa QPiAffine
        argument.node_count + 1 <= 12 || throw(ReplayFailure("typed Qbar[pi] bound exceeded"))
        QPiAffine(-argument.coefficient, -argument.offset, argument.node_count + 1)
      else
        -argument
      end
'''
    if source.count(neg_marker) != 1:
        raise base.ExactCoordinateFailure("typed unary seam changed")
    source = source.replace(neg_marker, neg_replacement, 1)

    degree_marker = '''  elseif value isa AngleExpression
    return Int[degree(value.cosine), degree(value.sine)]
'''
    if source.count(degree_marker) != 1:
        raise base.ExactCoordinateFailure("typed degree-ledger seam changed")
    source = source.replace(
        degree_marker,
        '''  elseif value isa QPiAffine
    return Int[degree(value.coefficient), degree(value.offset)]
  elseif value isa AngleExpression
    return Int[degree(value.cosine), degree(value.sine)]
''',
        1,
    )

    replay_marker = '''  job["post_process_used"] == false || throw(ReplayFailure("job post-process flag is not false"))
'''
    if source.count(replay_marker) != 1:
        raise base.ExactCoordinateFailure("typed replay custody seam changed")
    source = source.replace(
        replay_marker,
        replay_marker
        + '''  job["typed_semantic_source_only"] == true || throw(ReplayFailure("typed source-only marker missing"))
''',
        1,
    )
    return source


def _annotated_job(base: Any, job: Mapping[str, Any], failure: str) -> dict[str, Any] | None:
    eligibility = job.get("typed_semantic_eligible_relation_indices")
    indices = eligibility.get(failure) if isinstance(eligibility, Mapping) else None
    if not isinstance(indices, list) or not indices:
        return None
    copied = copy.deepcopy(dict(job))
    roots = copied.get("relation_roots")
    nodes = copied.get("nodes")
    if not isinstance(roots, list) or not isinstance(nodes, list):
        return None
    for relation_index in indices:
        if (
            not isinstance(relation_index, int)
            or isinstance(relation_index, bool)
            or not 0 <= relation_index < len(roots)
        ):
            return None
        root_index = roots[relation_index]
        if not isinstance(root_index, int) or not 0 <= root_index < len(nodes):
            return None
        node = nodes[root_index]
        if not isinstance(node, Mapping) or node.get("op") != "sub" or len(node.get("args", [])) != 2:
            return None
        nodes[root_index] = {"op": "typed_equal", "args": list(node["args"])}
    copied["typed_semantic_source_only"] = True
    copied["typed_semantic_failure_class"] = failure
    copied["typed_semantic_relation_count"] = len(indices)
    return copied


def _run_patched(base: Any, job: Mapping[str, Any], *, timeout_seconds: float) -> dict[str, Any]:
    affinity = sorted(os.sched_getaffinity(0))
    if len(affinity) != 1:
        raise base.ExactCoordinateFailure("typed side requires one pinned CPU")
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
                "taskset",
                "-c",
                str(affinity[0]),
                "julia",
                "--compile=no",
                f"--project={base.JULIA_PROJECT}",
                "--startup-file=no",
                "--history-file=no",
                str(worker_path),
                str(job_path),
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=max(0.25, float(timeout_seconds)),
            env=environment,
            start_new_session=False,
            preexec_fn=_child_setup,
        )
    except subprocess.TimeoutExpired as error:
        raise base.ExactCoordinateFailure("typed semantic replay timed out") from error
    finally:
        job_path is not None and job_path.unlink(missing_ok=True)
        worker_path is not None and worker_path.unlink(missing_ok=True)
    if completed.returncode != 0:
        raise base.ExactCoordinateFailure("typed QQBar worker failed: " + completed.stderr[-300:])
    records = [line for line in completed.stdout.splitlines() if line.strip()]
    if len(records) != 1:
        raise base.ExactCoordinateFailure("typed QQBar worker emitted noncanonical output")
    result = json.loads(records[0])
    if not isinstance(result, dict):
        raise base.ExactCoordinateFailure("typed QQBar worker record is not an object")
    return result


def install(base: Any) -> None:
    if getattr(base, "_typed_semantic_connector_installed", False):
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
                "typed_semantic_failure_class": failure,
                "typed_semantic_relation_count": annotated["typed_semantic_relation_count"],
                "baseline_exact_replay_ran_first": True,
                "baseline_budget_fraction": BASELINE_FRACTION,
                "typed_side_budget_fraction_maximum": SIDE_FRACTION,
                "canonical_rational_into_qbar_equality_only": True,
                "order_sign_or_unknown_broadening": False,
            }
        )
        return side

    base._run_qqbar = baseline_first
    base._typed_semantic_baseline_run = baseline_run
    base._typed_semantic_connector_installed = True
