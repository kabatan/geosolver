#!/usr/bin/env python3.12
"""Execute one statically admitted request through msolve and exact QQBar replay."""

from __future__ import annotations

import argparse
from fractions import Fraction
import hashlib
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
LOCAL_RUNTIME_SHA256 = {
    COMMON.HERE / "ordinary_proposal_binding.py": "aca55f2783476f7deff8c612a5f86f26681936e31a7b0ea5a19b1d2b06788bb6",
    COMMON.HERE / "selected_execution_common.py": "3e2d977fd7aebbc4f2c79739a0a3bb9f824f25074b6ddd7a3af903bce4009b0e",
    COMMON.HERE / "lossless_transport.py": "43fde3a479c2335f1e0311d990810bf4983d4c50f268a7968512cccb1daec521",
}
PARENT_AUTHORIZATION_KEYS = frozenset(
    {
        "schema_version",
        "candidate_id",
        "request_ordinal",
        "ordinary_binding_request_sha256",
        "parent_run_binding_sha256",
        "parent_token_sha256",
        "parent_acceptance_required",
        "authority_pass",
        "target_release",
        "completeness_claim",
    }
)


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
    ordinary_full_proposal_binding: bool = False,
    parent_binding: Mapping[str, Any] | None = None,
) -> None:
    document: dict[str, Any] = {
        "schema_version": SCHEMA,
        "status": status,
        "stages_passed": list(stages),
        "converted": "converted" in stages,
        "conversion_signature": conversion_signature,
        "ordinary_full_proposal_binding": ordinary_full_proposal_binding,
        "authority_pass": False,
        "target_release": False,
        "completeness_claim": "NOT_MADE",
        "target_image_completeness": "NOT_RUN",
        "truth_used": False,
        "formal_scorer_used": False,
        "full98_used": False,
        "parent_acceptance_required": True,
    }
    if parent_binding is not None:
        document.update(parent_binding)
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


def _is_sha256(value: object) -> bool:
    if not isinstance(value, str) or len(value) != 64 or value.lower() != value:
        return False
    try:
        bytes.fromhex(value)
    except ValueError:
        return False
    return True


def _exact_json_file(path: Path, expected_sha256: str, label: str) -> tuple[dict[str, Any], bytes]:
    if path.is_symlink() or not path.is_file() or not _is_sha256(expected_sha256):
        raise ChildExecutionError(f"{label} custody rejected")
    payload = path.read_bytes()
    if not payload or len(payload) > 1024 * 1024 or hashlib.sha256(payload).hexdigest() != expected_sha256:
        raise ChildExecutionError(f"{label} all-bytes digest mismatch")
    try:
        document = json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ChildExecutionError(f"{label} is not JSON") from error
    if not isinstance(document, dict):
        raise ChildExecutionError(f"{label} is not a mapping")
    return document, payload


def _validate_parent_binding(
    *,
    raw_dir: Path,
    ordinary_binding: Path,
    ordinary_binding_sha256: str,
    parent_run_binding: Path,
    parent_run_binding_sha256: str,
    parent_authorization: Path,
    parent_authorization_sha256: str,
    parent_token: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Validate parent-issued bytes without ever granting child authority."""

    request_path = ordinary_binding.resolve()
    run_path = parent_run_binding.resolve()
    authorization_path = parent_authorization.resolve()
    if not (
        request_path.parent == raw_dir.parent
        and authorization_path.parent == raw_dir.parent
        and run_path == raw_dir.parent.parent / "RUN_BINDING.json"
    ):
        raise ChildExecutionError("parent binding directory topology rejected")
    request, _request_bytes = _exact_json_file(
        request_path, ordinary_binding_sha256, "ordinary request"
    )
    run_binding, _run_bytes = _exact_json_file(
        run_path, parent_run_binding_sha256, "parent run binding"
    )
    authorization, _authorization_bytes = _exact_json_file(
        authorization_path, parent_authorization_sha256, "parent authorization"
    )
    if (
        not isinstance(parent_token, str)
        or len(parent_token) != 64
        or parent_token.lower() != parent_token
    ):
        raise ChildExecutionError("parent token malformed")
    try:
        bytes.fromhex(parent_token)
    except ValueError as error:
        raise ChildExecutionError("parent token malformed") from error
    token_sha256 = hashlib.sha256(parent_token.encode("ascii")).hexdigest()
    if not (
        run_binding.get("schema_version")
        == "geotarget.msolve-selected-exact-run-binding/v2"
        and run_binding.get("candidate_id")
        == "MSOLVE_EXACT_WITNESS_BIGINT_TRANSPORT_REOPEN_V1"
        and run_binding.get("ordinary_full_proposal_binding_required") is True
        and run_binding.get("authority_pass") is False
        and run_binding.get("target_release") is False
        and run_binding.get("completeness_claim") == "NOT_MADE"
        and run_binding.get("truth_used") is False
        and set(authorization) == PARENT_AUTHORIZATION_KEYS
        and authorization.get("schema_version")
        == "geotarget.msolve-selected-parent-authorization/v1"
        and authorization.get("candidate_id")
        == "MSOLVE_EXACT_WITNESS_BIGINT_TRANSPORT_REOPEN_V1"
        and isinstance(authorization.get("request_ordinal"), int)
        and not isinstance(authorization.get("request_ordinal"), bool)
        and authorization.get("request_ordinal") >= 0
        and authorization.get("ordinary_binding_request_sha256")
        == ordinary_binding_sha256
        and authorization.get("parent_run_binding_sha256")
        == parent_run_binding_sha256
        and authorization.get("parent_token_sha256") == token_sha256
        and authorization.get("parent_acceptance_required") is True
        and authorization.get("authority_pass") is False
        and authorization.get("target_release") is False
        and authorization.get("completeness_claim") == "NOT_MADE"
    ):
        raise ChildExecutionError("parent authorization binding rejected")
    evidence = {
        "ordinary_binding_request_sha256": ordinary_binding_sha256,
        "parent_run_binding_sha256": parent_run_binding_sha256,
        "parent_authorization_sha256": parent_authorization_sha256,
        "parent_token_sha256": token_sha256,
        "parent_acceptance_required": True,
        "standalone_conversion_authority": False,
    }
    return request, evidence


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ordinary-binding", type=Path, required=True)
    parser.add_argument("--ordinary-binding-sha256", required=True)
    parser.add_argument("--parent-run-binding", type=Path, required=True)
    parser.add_argument("--parent-run-binding-sha256", required=True)
    parser.add_argument("--parent-authorization", type=Path, required=True)
    parser.add_argument("--parent-authorization-sha256", required=True)
    parser.add_argument("--parent-token", required=True)
    parser.add_argument("--raw-dir", type=Path, required=True)
    parser.add_argument("--expected-cpu", type=int, default=14)
    arguments = parser.parse_args()
    if sys.version_info[:3] != (3, 12, 11):
        raise SystemExit("selected child requires frozen Python 3.12.11")
    if os.sched_getaffinity(0) != {arguments.expected_cpu}:
        raise SystemExit("selected child must be pinned to exactly the expected CPU")
    COMMON.verify_local_runtime(LOCAL_RUNTIME_SHA256)

    raw_dir = arguments.raw_dir.resolve()
    if raw_dir.exists() and any(raw_dir.iterdir()):
        raise SystemExit("child raw directory is not empty")
    raw_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    output = raw_dir / "CHILD_RESULT.json"
    stages: list[str] = []
    parent_binding: dict[str, Any] | None = None
    _checkpoint(output, stages=stages, status="STARTED")
    deadline = time.monotonic() + 29.5

    try:
        binding_row, parent_binding = _validate_parent_binding(
            raw_dir=raw_dir,
            ordinary_binding=arguments.ordinary_binding,
            ordinary_binding_sha256=arguments.ordinary_binding_sha256,
            parent_run_binding=arguments.parent_run_binding,
            parent_run_binding_sha256=arguments.parent_run_binding_sha256,
            parent_authorization=arguments.parent_authorization,
            parent_authorization_sha256=arguments.parent_authorization_sha256,
            parent_token=arguments.parent_token,
        )
        dependencies = COMMON.load_admission_dependencies()
        admission = COMMON.classify_bound_ordinary_row(
            binding_row, dependencies=dependencies
        )
        if admission.get("eligible") is not True:
            raise ChildExecutionError("ordinary proposal failed frozen re-admission")
        ordinary = admission["ordinary_binding"]
        stages.append("eligible")
        _checkpoint(
            output, stages=stages, status="ELIGIBLE", parent_binding=parent_binding
        )

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
        _checkpoint(
            output,
            stages=stages,
            status="ZERO_DIMENSIONAL_RUR",
            parent_binding=parent_binding,
        )

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
            "source_sha256": ordinary.source_sha256,
            "endpoint_float64_sha256": ordinary.endpoint_float64_sha256,
            "ordinary_proposal_all_bytes_sha256": ordinary.proposal_sha256,
            "ordinary_attempt_sha256": ordinary.ordinary_attempt_sha256,
            "ordinary_descriptor_sha256": ordinary.ordinary_descriptor_sha256,
            "ordinary_binding_statement_sha256": ordinary.binding_statement_sha256,
            "completeness_claim": "NOT_MADE",
        }
        _atomic_json(selection_path, selection)
        stages.append("predicate_compatible_box_selected")
        _checkpoint(
            output,
            stages=stages,
            status="NUMERIC_BOX_SELECTED",
            parent_binding=parent_binding,
        )

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
        if not (
            factor.get("status")
            == "IRREDUCIBLE_FACTOR_SELECTED_BY_EXACT_THETA_INTERVAL"
            and factor.get("msolve_output_sha256")
            == COMMON.sha256_bytes(msolve_output_path.read_bytes())
            and factor.get("selection_sha256")
            == COMMON.sha256_bytes(selection_path.read_bytes())
            and factor.get("factorization_exact") is True
            and factor.get("factor_irreducible_over_Q") is True
            and factor.get("selected_factor_multiplicity_in_radical_eliminant") == 1
            and factor.get("selection_used_truth") is False
        ):
            raise ChildExecutionError("selected factor artifact rejected")
        stages.append("irreducible_factor_selected")
        _checkpoint(
            output,
            stages=stages,
            status="IRREDUCIBLE_FACTOR_SELECTED",
            parent_binding=parent_binding,
        )

        theta = sp.Symbol("msolve_rur_theta")
        raw_factor = factor.get("selected_factor_coefficients_low_to_high")
        interval = factor.get("selected_interval")
        if not isinstance(raw_factor, list) or not isinstance(interval, Mapping):
            raise ChildExecutionError("selected factor artifact is incomplete")
        theta_factor = replay.RUR._poly_low_to_high(raw_factor, theta)
        theta_left_exact = sp.Rational(str(interval["left"]))
        theta_right_exact = sp.Rational(str(interval["right"]))
        selection_interval = selection["theta_isolating_interval"]
        selection_left = sp.Rational(str(selection_interval["left"]))
        selection_right = sp.Rational(str(selection_interval["right"]))
        if not (
            selection_left <= theta_left_exact <= theta_right_exact <= selection_right
            and int(theta_factor.count_roots(theta_left_exact, theta_right_exact)) == 1
            and theta_factor.is_sqf is True
            and theta_factor.is_irreducible is True
        ):
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
        target = dict(ordinary.target_descriptor)
        if COMMON.canonical_sha256(target) != ordinary.target_descriptor_sha256:
            raise ChildExecutionError("ordinary target descriptor digest changed")
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
            and replay_result.get("truth_used") is False
            and replay_result.get("completeness_claim_permitted") is False
            and transport_attestation.get("round_trip_equal") is True
            and transport_attestation.get("complete_qqbar_source_replay") is True
        ):
            raise ChildExecutionError("canonical exact source replay rejected")
        replay_ledger = COMMON.exact_replay_ledger(
            compiled, exact_counts, replay_result
        )
        stages.append("qqbar_exact_source_replay")
        _checkpoint(
            output,
            stages=stages,
            status="EXACT_SOURCE_REPLAY_ACCEPTED",
            parent_binding=parent_binding,
        )

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
                "ordinary_target_degree": len(
                    ordinary.polynomial_coefficients_high_to_low
                )
                - 1,
                "coordinate_degree_multiset": sorted(
                    int(value)
                    for value in replay_result.get("coordinate_degrees", [])
                ),
                "source_relation_count": exact_counts["source_relation_count"],
                "source_guard_count": exact_counts["source_guard_count"],
                "source_bound_count": exact_counts["source_bound_count"],
                "predicate_source_ledger_sha256": replay_ledger[
                    "predicate_source_ledger_sha256"
                ],
                "replay_obligation_ledger_sha256": replay_ledger[
                    "replay_obligation_ledger_sha256"
                ],
                "dag_node_bucket": int(replay_result.get("dag_node_count", 0)) // 32,
            }
        )
        conversion = {
            "schema_version": "geotarget.msolve-selected-exact-conversion/v1",
            "status": "CONVERSION_CANDIDATE_PARENT_ACCEPTANCE_REQUIRED",
            "source_sha256": admission["source_sha256"],
            "compiled_cover_sha256": COMMON.sha256_bytes(compiled_path.read_bytes()),
            "msolve_input_sha256": COMMON.sha256_bytes(msolve_input),
            "msolve_output_sha256": COMMON.sha256_bytes(msolve_output_path.read_bytes()),
            "selection_sha256": COMMON.sha256_bytes(selection_path.read_bytes()),
            "factor_sha256": COMMON.sha256_bytes(factor_path.read_bytes()),
            "augmented_job_sha256": COMMON.canonical_sha256(job),
            "target_descriptor_sha256": COMMON.canonical_sha256(target),
            "ordinary_proposal_all_bytes_sha256": ordinary.proposal_sha256,
            "original_result_all_bytes_sha256": ordinary.original_result_sha256,
            "ordinary_attempt_sha256": ordinary.ordinary_attempt_sha256,
            "ordinary_descriptor_sha256": ordinary.ordinary_descriptor_sha256,
            "ordinary_binding_statement": ordinary.binding_statement,
            "ordinary_binding_statement_sha256": ordinary.binding_statement_sha256,
            "replay_sha256": COMMON.canonical_sha256(replay_result),
            "transport_attestation": transport_attestation,
            "exact_source_counts": exact_counts,
            "exact_replay_ledger": replay_ledger,
            "conversion_signature": signature,
            "canonical_source_replay": True,
            "canonical_guard_replay": True,
            "canonical_bound_replay": True,
            "canonical_definedness_replay": replay_ledger[
                "canonical_definedness_replay"
            ],
            "canonical_branch_replay": replay_ledger["canonical_branch_replay"],
            "raw_target_exact_replay": True,
            "ordinary_full_proposal_binding": True,
            "authority_pass": False,
            "target_release": False,
            "completeness_claim": "NOT_MADE",
            "target_image_completeness": "NOT_RUN",
            "truth_used": False,
            "formal_scorer_used": False,
            "full98_used": False,
            **parent_binding,
        }
        _atomic_json(raw_dir / "CONVERSION.json", conversion)
        stages.append("converted")
        _checkpoint(
            output,
            stages=stages,
            status="PARENT_ACCEPTANCE_REQUIRED",
            conversion_signature=signature,
            ordinary_full_proposal_binding=True,
            parent_binding=parent_binding,
        )
        print('{"status":"PARENT_ACCEPTANCE_REQUIRED","authority_pass":false}')
        return 0
    except BaseException as error:
        _checkpoint(
            output,
            stages=stages,
            status="REJECTED",
            error=error,
            parent_binding=parent_binding,
        )
        print('{"status":"REJECTED","authority_pass":false}')
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
