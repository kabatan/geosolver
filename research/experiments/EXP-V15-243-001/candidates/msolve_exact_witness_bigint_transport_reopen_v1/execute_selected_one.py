#!/usr/bin/env python3.12
"""Execute one statically admitted request through msolve and exact QQBar replay."""

from __future__ import annotations

import argparse
from fractions import Fraction
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from typing import Any, Mapping

import sympy as sp

import lossless_transport
import selected_execution_common as COMMON


SCHEMA = "geotarget.msolve-selected-exact-execution-child/v1"
INNER_QQBAR_CAP_SECONDS = 8.25


class ChildExecutionError(ValueError):
    """One exact execution failed closed."""


def _atomic_json(path: Path, document: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        with temporary.open("w", encoding="utf-8") as stream:
            json.dump(document, stream, ensure_ascii=False, indent=2, sort_keys=True)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary, 0o600)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _write_bytes(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        with temporary.open("wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary, 0o600)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _rational_text(value: Fraction) -> str:
    return str(value.numerator) if value.denominator == 1 else str(value)


def _checkpoint(
    output: Path,
    *,
    stages: list[str],
    status: str,
    error: BaseException | None = None,
    conversion_signature: str | None = None,
) -> None:
    document: dict[str, Any] = {
        "schema_version": SCHEMA,
        "status": status,
        "stages_passed": list(stages),
        "converted": "converted" in stages,
        "conversion_signature": conversion_signature,
        "ordinary_full_proposal_binding": False,
        "authority_pass": False,
        "target_release": False,
        "completeness_claim": "NOT_MADE",
        "target_image_completeness": "NOT_RUN",
        "truth_used": False,
        "formal_scorer_used": False,
        "full98_used": False,
    }
    if error is not None:
        document["error_type"] = type(error).__name__
        document["error"] = str(error)[:512]
    _atomic_json(output, document)


def _remaining(deadline: float, reserve: float = 0.25) -> float:
    value = deadline - time.monotonic() - reserve
    if value <= 0.05:
        raise ChildExecutionError("fresh-process deadline exhausted")
    return value


def _run_stage(command: list[str], *, deadline: float, raw_log: Path) -> None:
    completed = subprocess.run(
        command,
        check=False,
        capture_output=True,
        timeout=_remaining(deadline),
    )
    _write_bytes(
        raw_log,
        b"stdout:\n" + completed.stdout + b"\nstderr:\n" + completed.stderr,
    )
    if completed.returncode != 0:
        raise ChildExecutionError("frozen exact-witness stage returned nonzero")


def _load_exact_modules() -> tuple[Any, Any, Any]:
    msolve_output = COMMON.load_module(
        "msolve_output", COMMON.MSOLVE_DIR / "msolve_output.py"
    )
    inspect_result = COMMON.load_module(
        "msolve_selected_frozen_inspect", COMMON.MSOLVE_DIR / "inspect_result.py"
    )
    replay = COMMON.load_module(
        "msolve_selected_frozen_replay", COMMON.MSOLVE_DIR / "replay_rur_qqbar.py"
    )
    return msolve_output, inspect_result, replay


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--request", type=Path, required=True)
    parser.add_argument("--raw-dir", type=Path, required=True)
    parser.add_argument("--expected-cpu", type=int, default=14)
    arguments = parser.parse_args()
    if sys.version_info[:3] != (3, 12, 11):
        raise SystemExit("selected child requires frozen Python 3.12.11")
    if os.sched_getaffinity(0) != {arguments.expected_cpu}:
        raise SystemExit("selected child must be pinned to exactly the expected CPU")

    raw_dir = arguments.raw_dir.resolve()
    if raw_dir.exists() and any(raw_dir.iterdir()):
        raise SystemExit("child raw directory is not empty")
    raw_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    output = raw_dir / "CHILD_RESULT.json"
    stages: list[str] = []
    _checkpoint(output, stages=stages, status="STARTED")
    deadline = time.monotonic() + 29.5

    try:
        request = json.loads(arguments.request.read_bytes())
        dependencies = COMMON.load_admission_dependencies()
        admission = COMMON.classify_request(request, dependencies=dependencies)
        if admission.get("eligible") is not True:
            raise ChildExecutionError("request failed frozen re-admission")
        stages.append("eligible")
        _checkpoint(output, stages=stages, status="ELIGIBLE")

        source_bytes = admission["source_bytes"]
        compiled = admission["compiled"]
        msolve_input = admission["msolve_input"]
        source_path = raw_dir / "source.json"
        compiled_path = raw_dir / "compiled-cover.json"
        input_path = raw_dir / "msolve-input.txt"
        msolve_output_path = raw_dir / "msolve-output.txt"
        selection_path = raw_dir / "selection.json"
        factor_path = raw_dir / "factor.json"
        _write_bytes(source_path, source_bytes)
        _write_bytes(compiled_path, COMMON.canonical_bytes(compiled) + b"\n")
        _write_bytes(input_path, msolve_input)

        _run_stage(
            [
                sys.executable,
                str(COMMON.MSOLVE_DIR / "run_msolve.py"),
                "--msolve",
                str(COMMON.MSOLVE_BINARY),
                "--input",
                str(input_path),
                "--output",
                str(msolve_output_path),
                "--precision",
                "256",
            ],
            deadline=deadline,
            raw_log=raw_dir / "msolve-stage.log",
        )

        msolve_output, inspect_result, replay = _load_exact_modules()
        result = msolve_output.read_result(msolve_output_path)
        if result.dimension != 0 or result.parametrization is None:
            raise ChildExecutionError("msolve result is not a zero-dimensional RUR")
        stages.append("msolve_zero_dimensional")
        _checkpoint(output, stages=stages, status="ZERO_DIMENSIONAL_RUR")

        input_variables = compiled.get("cover_variable_names")
        source_variables = compiled.get("source_variable_names")
        predicates = compiled.get("predicates")
        if not (
            isinstance(input_variables, list)
            and isinstance(source_variables, list)
            and isinstance(predicates, list)
        ):
            raise ChildExecutionError("compiler bindings are malformed")
        reconstruction: list[dict[str, str]] = []
        compatible_indices = msolve_output.predicate_compatible_boxes(
            result.real_boxes, input_variables, reconstruction, predicates
        )
        endpoint_text = [repr(value) for value in admission["endpoint"]]
        local_index = msolve_output.select_numeric_box(
            [result.real_boxes[index] for index in compatible_indices],
            input_variables,
            source_variables,
            endpoint_text,
        )
        selected_index = compatible_indices[local_index]
        selected_box = result.real_boxes[selected_index]
        theta_left, theta_right = inspect_result.theta_interval(
            input_variables,
            selected_box,
            result.parametrization.variables,
            result.parametrization.linear_form,
        )
        selection = {
            "schema_version": "geotarget.msolve-rur-numeric-box-selection/v1",
            "status": "ZERO_DIMENSIONAL_RUR_BOX_SELECTED",
            "case_id": None,
            "msolve_output_sha256": COMMON.sha256_bytes(msolve_output_path.read_bytes()),
            "selected_box_index_zero_based": selected_index,
            "theta_isolating_interval": {
                "left": _rational_text(theta_left),
                "right": _rational_text(theta_right),
            },
            "selection_used_truth": False,
            "completeness_claim": "NOT_MADE",
        }
        _atomic_json(selection_path, selection)
        stages.append("predicate_compatible_box_selected")
        _checkpoint(output, stages=stages, status="NUMERIC_BOX_SELECTED")

        _run_stage(
            [
                str(COMMON.FACTOR_PYTHON),
                str(COMMON.MSOLVE_DIR / "factor_selected.py"),
                "--msolve-output",
                str(msolve_output_path),
                "--selection",
                str(selection_path),
                "--output",
                str(factor_path),
            ],
            deadline=deadline,
            raw_log=raw_dir / "factor-stage.log",
        )
        factor = json.loads(factor_path.read_bytes())
        if factor.get("status") != "IRREDUCIBLE_FACTOR_SELECTED_BY_EXACT_THETA_INTERVAL":
            raise ChildExecutionError("selected factor artifact rejected")
        stages.append("irreducible_factor_selected")
        _checkpoint(output, stages=stages, status="IRREDUCIBLE_FACTOR_SELECTED")

        theta = sp.Symbol("msolve_rur_theta")
        raw_factor = factor.get("selected_factor_coefficients_low_to_high")
        interval = factor.get("selected_interval")
        if not isinstance(raw_factor, list) or not isinstance(interval, Mapping):
            raise ChildExecutionError("selected factor artifact is incomplete")
        theta_factor = replay.RUR._poly_low_to_high(raw_factor, theta)
        theta_left_exact = sp.Rational(str(interval["left"]))
        theta_right_exact = sp.Rational(str(interval["right"]))
        if int(theta_factor.count_roots(theta_left_exact, theta_right_exact)) != 1:
            raise ChildExecutionError("theta interval is not isolating")
        theta_descriptor = {
            "coefficients_high_to_low": [
                int(value) for value in theta_factor.all_coeffs()
            ],
            "isolating_interval": {
                "left": str(theta_left_exact),
                "right": str(theta_right_exact),
                "multiplicity": 1,
            },
        }
        coordinate_polynomials, _eliminant, _derivative = (
            replay._coordinate_polynomials(result, theta_factor)
        )
        coordinate_descriptors: dict[str, Mapping[str, Any]] = {}
        if len(selected_box) != len(input_variables):
            raise ChildExecutionError("selected box dimension differs from cover")
        for name, raw_interval in zip(input_variables, selected_box, strict=True):
            left = sp.Rational(
                raw_interval[0].numerator, raw_interval[0].denominator
            )
            right = sp.Rational(
                raw_interval[1].numerator, raw_interval[1].denominator
            )
            coordinate_descriptors[name] = replay._descriptor_from_relation(
                theta_factor=theta_factor,
                coordinate=coordinate_polynomials[name],
                interval=(left, right),
                variable_name=name,
            )
        prepared = {
            "status": "MSOLVE_DIMENSION_PROBE_ELIGIBLE",
            "source_sha256": admission["source_sha256"],
            "source_variable_names": source_variables,
            "reduced_variable_names": input_variables,
            "linear_reconstruction": reconstruction,
            "compiled_cover_sha256": COMMON.sha256_bytes(compiled_path.read_bytes()),
            "msolve_input_sha256": COMMON.sha256_bytes(msolve_input),
        }
        target = COMMON.target_descriptor(
            admission["target_root"], admission["target_relation"]
        )
        job, exact_counts = replay._augment_job(
            source=admission["source"],
            compiled=compiled,
            prepared=prepared,
            target_descriptor=target,
            theta_descriptor=theta_descriptor,
            coordinate_descriptors=coordinate_descriptors,
            coordinate_polynomials=coordinate_polynomials,
            parametrization=result.parametrization,
            theta_factor=theta_factor,
        )
        replay_result = lossless_transport.run_julia_lossless(
            job,
            julia_project=replay.QQBAR_WORKER.JULIA_PROJECT,
            julia_worker=replay.QQBAR_WORKER.JULIA_WORKER,
            timeout_seconds=min(INNER_QQBAR_CAP_SECONDS, _remaining(deadline)),
        )
        transport_attestation = dict(lossless_transport.LAST_ATTESTATION or {})
        if not (
            replay_result.get("status") == "EXACT_REPLAY_ACCEPTED"
            and replay_result.get("source_raw_answer_exact") is True
            and replay_result.get("target_link_exact") is True
            and replay_result.get("truth_used") is False
            and replay_result.get("completeness_claim_permitted") is False
            and transport_attestation.get("round_trip_equal") is True
            and transport_attestation.get("complete_qqbar_source_replay") is True
        ):
            raise ChildExecutionError("canonical exact source replay rejected")
        stages.append("qqbar_exact_source_replay")
        _checkpoint(output, stages=stages, status="EXACT_SOURCE_REPLAY_ACCEPTED")

        signature = COMMON.canonical_sha256(
            {
                "cover_shape": compiled.get("cover_shape"),
                "cover_variable_count": len(input_variables),
                "equation_count": len(compiled.get("equations", [])),
                "predicate_count": len(predicates),
                "branch_obligation_count": compiled.get(
                    "branch_replay_obligation_count"
                ),
                "selected_theta_degree": int(theta_factor.degree()),
                "coordinate_degree_multiset": sorted(
                    int(value)
                    for value in replay_result.get("coordinate_degrees", [])
                ),
                "source_relation_count": exact_counts["source_relation_count"],
                "source_guard_count": exact_counts["source_guard_count"],
                "source_bound_count": exact_counts["source_bound_count"],
                "dag_node_bucket": int(replay_result.get("dag_node_count", 0)) // 32,
            }
        )
        conversion = {
            "schema_version": "geotarget.msolve-selected-exact-conversion/v1",
            "status": "CONVERTED_BY_CANONICAL_EXACT_SOURCE_REPLAY",
            "source_sha256": admission["source_sha256"],
            "compiled_cover_sha256": COMMON.sha256_bytes(compiled_path.read_bytes()),
            "msolve_input_sha256": COMMON.sha256_bytes(msolve_input),
            "msolve_output_sha256": COMMON.sha256_bytes(msolve_output_path.read_bytes()),
            "selection_sha256": COMMON.sha256_bytes(selection_path.read_bytes()),
            "factor_sha256": COMMON.sha256_bytes(factor_path.read_bytes()),
            "augmented_job_sha256": COMMON.canonical_sha256(job),
            "target_descriptor_sha256": COMMON.canonical_sha256(target),
            "replay_sha256": COMMON.canonical_sha256(replay_result),
            "transport_attestation": transport_attestation,
            "exact_source_counts": exact_counts,
            "conversion_signature": signature,
            "canonical_source_replay": True,
            "canonical_guard_replay": True,
            "canonical_bound_replay": True,
            "canonical_branch_replay": True,
            "raw_target_exact_replay": True,
            "ordinary_full_proposal_binding": False,
            "authority_pass": False,
            "target_release": False,
            "completeness_claim": "NOT_MADE",
            "target_image_completeness": "NOT_RUN",
            "truth_used": False,
            "formal_scorer_used": False,
            "full98_used": False,
        }
        _atomic_json(raw_dir / "CONVERSION.json", conversion)
        stages.append("converted")
        _checkpoint(
            output,
            stages=stages,
            status="CONVERTED",
            conversion_signature=signature,
        )
        print('{"status":"CONVERTED","authority_pass":false}')
        return 0
    except BaseException as error:
        _checkpoint(output, stages=stages, status="REJECTED", error=error)
        print('{"status":"REJECTED","authority_pass":false}')
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
