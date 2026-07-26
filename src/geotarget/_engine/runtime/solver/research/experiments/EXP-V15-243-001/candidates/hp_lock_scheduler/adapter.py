"""Candidate-private v15 HP seam with corrected wrapper RSS accounting."""

from __future__ import annotations

import json
import math
import os
from pathlib import Path
import time
from typing import Mapping

from deadline_guard import (
    DEFAULT_CLEANUP_RESERVE_SECONDS,
    MINIMUM_CHILD_SECONDS,
    run_guarded_until,
)
from policy import DEFAULT_POLICY, LeaseUnavailable, per_core_lease


MIB = 1024**2
FORMAL_CASE_DEADLINE_ENV = "GEOTARGET_FORMAL_CASE_DEADLINE_MONOTONIC"


def _bounded_case_deadline(relative_seconds: float) -> float:
    deadline = time.monotonic() + relative_seconds
    raw = os.environ.get(FORMAL_CASE_DEADLINE_ENV)
    if raw is None:
        return deadline
    try:
        formal_deadline = float(raw)
    except ValueError as error:
        raise RuntimeError("invalid formal case deadline") from error
    if not math.isfinite(formal_deadline):
        raise RuntimeError("invalid formal case deadline")
    return min(deadline, formal_deadline)


def _authority_evidence(
    authority: Mapping[str, object] | None,
    *,
    source_sha256: str,
    endpoint_sha256: str,
) -> dict[str, object]:
    final = (
        authority.get("final_result")
        if isinstance(authority, Mapping)
        else None
    )
    contract = (
        authority.get("input_contract")
        if isinstance(authority, Mapping)
        else None
    )
    final_contract = (
        final.get("input_contract") if isinstance(final, Mapping) else None
    )
    transforms = (
        final.get("problem_transformations")
        if isinstance(final, Mapping)
        else None
    )
    scope = (
        final.get("authority_scope")
        if isinstance(final, Mapping)
        else None
    )
    authority_pass = (
        authority.get("authority_pass")
        if isinstance(authority, Mapping)
        else None
    )
    final_authority_pass = (
        final.get("authority_pass") if isinstance(final, Mapping) else None
    )
    required_scope = (
        "numerical_configuration_512_768",
        "target_512_768_1024",
        "original_dsl_hp_replay",
        "target_only_owned_pslq",
        "minimal_polynomial_and_isolator",
    )
    valid = bool(
        isinstance(authority, Mapping)
        and authority.get("schema_version")
        == "geotarget.exp008-target-first-fallback-composition/v1"
        and isinstance(authority_pass, bool)
        and isinstance(final, Mapping)
        and isinstance(final_authority_pass, bool)
        and authority_pass is final_authority_pass
        and final.get("source_raw_sha256") == source_sha256
        and final.get("endpoint_float64_sha256") == endpoint_sha256
        and isinstance(contract, Mapping)
        and contract.get("same_source_bytes_both_attempts") is True
        and contract.get("same_float64_endpoint_both_attempts") is True
        and contract.get("source_or_problem_modified") is False
        and contract.get("bounds_added") is False
        and contract.get("gauge_or_symmetry_reduction") is False
        and isinstance(final_contract, Mapping)
        and all(
            final_contract.get(name) is False
            for name in ("truth", "known_target_count", "case_id", "family")
        )
        and isinstance(transforms, Mapping)
        and transforms
        and all(value is False for value in transforms.values())
        and isinstance(scope, Mapping)
        and all(scope.get(name) is True for name in required_scope)
    )
    return {
        "present": isinstance(authority, Mapping),
        "document_valid": valid,
        "authority_pass": authority_pass if valid else None,
        "source_sha256_matches": bool(
            isinstance(final, Mapping)
            and final.get("source_raw_sha256") == source_sha256
        ),
        "endpoint_sha256_matches": bool(
            isinstance(final, Mapping)
            and final.get("endpoint_float64_sha256") == endpoint_sha256
        ),
    }


def _terminal_evidence(
    *,
    executed: Mapping[str, object],
    bridge_result: Mapping[str, object] | None,
    authority: Mapping[str, object] | None,
    source_sha256: str,
    endpoint_sha256: str,
    descriptor: object | None,
) -> dict[str, object]:
    authority_evidence = _authority_evidence(
        authority,
        source_sha256=source_sha256,
        endpoint_sha256=endpoint_sha256,
    )
    authority_pass = authority_evidence["authority_pass"]
    bridge_authority_pass = (
        bridge_result.get("authority_pass")
        if isinstance(bridge_result, Mapping)
        else None
    )
    common = bool(
        executed.get("classification") == "SUCCESS"
        and executed.get("accepted_output") is True
        and executed.get("descendant_leak") is not True
        and isinstance(bridge_result, Mapping)
        and bridge_result.get("status") == "COMPLETE"
        and bridge_result.get("process_classification") == "SUCCESS"
        and bridge_result.get("artifact_accepted") is True
        and bridge_result.get("source_sha256") == source_sha256
        and bridge_result.get("endpoint_float64_sha256")
        == endpoint_sha256
        and authority_evidence["present"] is True
        and authority_evidence["document_valid"] is True
        and isinstance(bridge_authority_pass, bool)
        and bridge_authority_pass is authority_pass
    )
    ready = bool(common and authority_pass is True and descriptor is not None)
    terminal_no_authority = bool(
        common and authority_pass is False and descriptor is None
    )
    return {
        "pass": ready or terminal_no_authority,
        "terminal_kind": (
            "TARGET_AUTHORITY_READY"
            if ready
            else (
                "TERMINAL_NO_TARGET_AUTHORITY"
                if terminal_no_authority
                else "INVALID_HP_TERMINAL"
            )
        ),
        "outer_execute_classification": executed.get("classification"),
        "outer_execute_accepted": executed.get("accepted_output") is True,
        "outer_execute_descendant_leak": (
            executed.get("descendant_leak") is True
        ),
        "bridge_result_present": isinstance(bridge_result, Mapping),
        "bridge_status": (
            bridge_result.get("status")
            if isinstance(bridge_result, Mapping)
            else None
        ),
        "nested_process_classification": (
            bridge_result.get("process_classification")
            if isinstance(bridge_result, Mapping)
            else None
        ),
        "artifact_accepted": bool(
            isinstance(bridge_result, Mapping)
            and bridge_result.get("artifact_accepted") is True
        ),
        "bridge_source_sha256_matches": bool(
            isinstance(bridge_result, Mapping)
            and bridge_result.get("source_sha256") == source_sha256
        ),
        "bridge_endpoint_sha256_matches": bool(
            isinstance(bridge_result, Mapping)
            and bridge_result.get("endpoint_float64_sha256")
            == endpoint_sha256
        ),
        "bridge_authority_pass": (
            bridge_authority_pass
            if isinstance(bridge_authority_pass, bool)
            else None
        ),
        "authority_artifact_present": authority_evidence["present"],
        "authority_document_valid": authority_evidence["document_valid"],
        "authority_source_sha256_matches": authority_evidence[
            "source_sha256_matches"
        ],
        "authority_endpoint_sha256_matches": authority_evidence[
            "endpoint_sha256_matches"
        ],
        "authority_pass": authority_pass,
        "descriptor_consistent": (
            descriptor is not None
            if authority_pass is True
            else descriptor is None
        ),
    }


def _restoration_terminal_evidence(
    *,
    result: Mapping[str, object],
    document: Mapping[str, object] | None,
    source_sha256: str,
) -> dict[str, object]:
    process = result.get("process")
    contract = (
        document.get("problem_contract")
        if isinstance(document, Mapping)
        else None
    )
    restored = (
        document.get("restored_authority")
        if isinstance(document, Mapping)
        else None
    )
    final = (
        restored.get("final_result")
        if isinstance(restored, Mapping)
        else None
    )
    restored_endpoint = (
        final.get("endpoint_float64_sha256")
        if isinstance(final, Mapping)
        else None
    )
    restored_evidence = None
    if isinstance(restored_endpoint, str) and len(restored_endpoint) == 64:
        restored_evidence = _authority_evidence(
            restored,
            source_sha256=source_sha256,
            endpoint_sha256=restored_endpoint,
        )
    document_pass = (
        document.get("authority_pass")
        if isinstance(document, Mapping)
        else None
    )
    result_pass = result.get("authority_pass")
    descriptor = result.get("descriptor")
    process_success = bool(
        isinstance(process, Mapping)
        and process.get("classification") == "SUCCESS"
        and process.get("accepted_output") is True
        and process.get("descendant_leak") is not True
    )
    document_common = bool(
        isinstance(document, Mapping)
        and document.get("schema_version")
        == "geotarget.exp008-roweq180-hp-restoration-composition/v1"
        and isinstance(document_pass, bool)
        and isinstance(contract, Mapping)
        and all(
            contract.get(field) is False
            for field in (
                "source_or_problem_modified",
                "variables_or_equations_changed",
                "bounds_added_or_inferred",
                "gauge_or_symmetry_reduction",
                "coordinate_reparameterization",
                "case_family_source_series_truth_target_count_routing",
            )
        )
    )
    restored_valid = bool(
        isinstance(restored_evidence, Mapping)
        and restored_evidence.get("document_valid") is True
        and restored_evidence.get("authority_pass") is document_pass
    )
    explicit_no_restoration = bool(
        document_common
        and document_pass is False
        and restored is None
        and document.get("status") == "NO_ELIGIBLE_HP_FAILURE"
    )
    ready = bool(
        process_success
        and document_common
        and restored_valid
        and document_pass is True
        and result_pass is True
        and isinstance(descriptor, Mapping)
    )
    terminal_no_authority = bool(
        process_success
        and document_common
        and document_pass is False
        and result_pass is False
        and descriptor is None
        and (restored_valid or explicit_no_restoration)
    )
    return {
        "pass": ready or terminal_no_authority,
        "terminal_kind": (
            "TARGET_AUTHORITY_READY"
            if ready
            else (
                "TERMINAL_NO_RESTORED_AUTHORITY"
                if terminal_no_authority
                else "INVALID_RESTORATION_TERMINAL"
            )
        ),
        "process_success": process_success,
        "document_present": isinstance(document, Mapping),
        "document_contract_valid": document_common,
        "document_authority_pass": (
            document_pass if isinstance(document_pass, bool) else None
        ),
        "restored_authority_valid": restored_valid,
        "explicit_no_restoration": explicit_no_restoration,
        "descriptor_consistent": (
            isinstance(descriptor, Mapping)
            if document_pass is True
            else descriptor is None
        ),
    }


def _restoration_foreground_command(command) -> list[str]:
    """Keep the frozen restoration command in the pdeath-tracked PID."""

    converted = [str(part) for part in command]
    if len(converted) < 4 or converted[:2] != ["flock", "-x"]:
        raise RuntimeError("unexpected frozen restoration flock command")
    return ["flock", "-F", *converted[1:]]


def run_hp_candidate(
    base,
    *,
    source: Path,
    source_sha256: str,
    candidate,
    cpu: int,
    output: Path,
    timeout_seconds: float,
) -> dict[str, object]:
    """Run one unchanged endpoint through the per-core HP bridge.

    The outer bridge wrapper is a small control process.  Its nested HP child
    starts a separate process group and owns its unchanged 480 MiB cap, so
    reserving 768 MiB again for the wrapper only creates false aggregate
    contention.  This adapter reserves 128 MiB for the wrapper and retains all
    inner caps and authority checks.
    """

    output.mkdir(parents=True, exist_ok=True)
    absolute_deadline = _bounded_case_deadline(timeout_seconds)
    # The nested child may consume one second of SIGTERM grace.  Reserve a
    # further bridge/status/atomic-finalization margin so the outer supervisor
    # cannot die first and orphan the child.
    deadline_seconds = max(0.1, timeout_seconds - 3.75)
    primary_cap_seconds = deadline_seconds
    process_timeout_seconds = max(
        deadline_seconds + 0.5,
        timeout_seconds - 3.25,
    )
    wrapper_rss = DEFAULT_POLICY.bridge_rss_bytes
    dry_status = output / "dry-process-status.json"
    dry_command = base._bridge_command(
        source=source,
        source_sha256=source_sha256,
        candidate=candidate,
        cpu=cpu,
        output=output,
        deadline_seconds=deadline_seconds,
        primary_cap_seconds=primary_cap_seconds,
        process_timeout_seconds=process_timeout_seconds,
        execute=False,
    )
    dry_command.extend(
        (
            "--absolute-deadline-monotonic",
            str(absolute_deadline),
        )
    )
    dry = run_guarded_until(
        dry_command,
        absolute_deadline=absolute_deadline,
        limits=base.Limits(
            timeout_seconds=min(5.0, max(0.5, timeout_seconds)),
            rss_bytes=wrapper_rss,
            address_space_bytes=1024 * MIB,
            data_bytes=768 * MIB,
            output_bytes=256 * 1024,
            tail_bytes=8 * 1024,
        ),
        environment=base.THREAD_ENVIRONMENT,
        cwd=base.ROOT,
        status_path=dry_status,
    )
    plan_path = output / "PLAN.json"
    if not dry.accepted_output or not plan_path.is_file():
        dry_resource_status = (
            "MEMORY_BUSY_DEFERRED"
            if dry.classification == "MEMORY_RESERVATION_TIMEOUT"
            else "HP_DRY_FAILED"
        )
        return {
            "endpoint_float64_sha256": candidate.endpoint_sha256,
            "status": dry_resource_status,
            "authority_pass": False,
            "process": dry.to_dict(),
            "resource_policy": DEFAULT_POLICY.to_dict(),
            "resource_busy_deferred": (
                dry_resource_status == "MEMORY_BUSY_DEFERRED"
            ),
            "late_timeout_artifact_salvaged": False,
        }
    plan_sha256 = base._sha256(plan_path.read_bytes())
    remaining_timeout = max(
        0.1,
        absolute_deadline - time.monotonic(),
    )
    execute_status = output / "execute-process-status.json"
    execute_command = base._bridge_command(
            source=source,
            source_sha256=source_sha256,
            candidate=candidate,
            cpu=cpu,
            output=output,
            deadline_seconds=deadline_seconds,
            primary_cap_seconds=primary_cap_seconds,
            process_timeout_seconds=process_timeout_seconds,
            execute=True,
            plan_sha256=plan_sha256,
        )
    execute_command.extend(
        (
            "--absolute-deadline-monotonic",
            str(absolute_deadline),
        )
    )
    executed = run_guarded_until(
        execute_command,
        absolute_deadline=absolute_deadline,
        limits=base.Limits(
            timeout_seconds=remaining_timeout,
            rss_bytes=wrapper_rss,
            address_space_bytes=1024 * MIB,
            data_bytes=768 * MIB,
            output_bytes=1024**2,
            tail_bytes=16 * 1024,
        ),
        environment=base.THREAD_ENVIRONMENT,
        cwd=base.ROOT,
        status_path=execute_status,
    )
    bridge_result = None
    authority = None
    try:
        bridge_result = json.loads(
            (output / "RESULT.json").read_text(encoding="utf-8")
        )
        authority = json.loads(
            (output / "authority.json").read_text(encoding="utf-8")
        )
    except (OSError, json.JSONDecodeError):
        pass
    descriptor = base._authority_descriptor(authority)
    # Deliberately do not salvage an artifact written after the outer wall
    # authority fired.  Timeout, nested failure, missing evidence, and
    # malformed evidence are invalid terminals rather than ordinary
    # no-authority outcomes.
    terminal_evidence = _terminal_evidence(
        executed=executed.to_dict(),
        bridge_result=bridge_result,
        authority=authority,
        source_sha256=source_sha256,
        endpoint_sha256=candidate.endpoint_sha256,
        descriptor=descriptor,
    )
    accepted = terminal_evidence["terminal_kind"] == "TARGET_AUTHORITY_READY"
    bridge_classification = (
        bridge_result.get("process_classification")
        if isinstance(bridge_result, Mapping)
        else None
    )
    resource_status = None
    if (
        executed.classification == "MEMORY_RESERVATION_TIMEOUT"
        or bridge_classification == "MEMORY_RESERVATION_TIMEOUT"
    ):
        resource_status = "MEMORY_BUSY_DEFERRED"
    elif (
        executed.classification == "NONZERO_EXIT"
        and "HP core lease unavailable" in executed.stderr_tail
    ):
        resource_status = "LOCK_BUSY_DEFERRED"
    resource_deferred = resource_status is not None
    status = (
        resource_status
        if resource_status is not None
        else str(terminal_evidence["terminal_kind"])
    )
    return {
        "attempt_kind": "PRIMARY_NUMERICAL_V3",
        "endpoint_float64_sha256": candidate.endpoint_sha256,
        "residual_inf": candidate.residual_inf,
        "provisional_target": candidate.provisional_target,
        "cluster_ordinal": candidate.cluster_ordinal,
        "cluster_rank": candidate.cluster_rank,
        "status": status,
        "authority_pass": accepted,
        "descriptor": descriptor if accepted else None,
        "bridge_result_sha256": (
            base._sha256((output / "RESULT.json").read_bytes())
            if (output / "RESULT.json").is_file()
            else None
        ),
        "authority_sha256": (
            base._sha256((output / "authority.json").read_bytes())
            if (output / "authority.json").is_file()
            else None
        ),
        "process": executed.to_dict(),
        "terminal_evidence": terminal_evidence,
        "resource_policy": DEFAULT_POLICY.to_dict(),
        "resource_busy_deferred": resource_deferred,
        "late_timeout_artifact_salvaged": False,
    }


def install(base, *, bridge: Path) -> None:
    """Install the candidate seam into one already-loaded v15 base module."""

    base.HP_BRIDGE = Path(bridge)
    original_restoration = base._run_restoration_candidate

    def _candidate_run_hp_candidate(**kwargs):
        return run_hp_candidate(base, **kwargs)

    def _candidate_restoration(**kwargs):
        cpu = int(kwargs["cpu"])
        candidate = kwargs["candidate"]
        previous = base.GLOBAL_HP_LOCK
        had_run_guarded = hasattr(base, "run_guarded")
        previous_run_guarded = getattr(base, "run_guarded", None)
        started = time.monotonic()
        absolute_deadline = _bounded_case_deadline(
            float(kwargs["timeout_seconds"])
        )
        lease_wait_seconds = min(
            DEFAULT_POLICY.maximum_core_lease_wait_seconds,
            max(
                0.0,
                absolute_deadline
                - time.monotonic()
                - DEFAULT_CLEANUP_RESERVE_SECONDS
                - MINIMUM_CHILD_SECONDS,
            ),
        )
        try:
            with per_core_lease(
                cpu,
                wait_seconds=lease_wait_seconds,
            ):
                adjusted = dict(kwargs)
                adjusted["timeout_seconds"] = max(
                    0.1,
                    float(kwargs["timeout_seconds"])
                    - (time.monotonic() - started),
                )
                # The parent process owns the actual per-core lease.  Keep
                # the frozen restoration worker's internal flock immediate
                # and private so it cannot recursively block on the same
                # lease held by its parent.
                base.GLOBAL_HP_LOCK = (
                    Path(kwargs["output"]) / ".restoration-inner.lock"
                )

                def _contained_restoration_guard(
                    command,
                    *,
                    limits,
                    environment=None,
                    cwd=None,
                    status_path=None,
                ):
                    return run_guarded_until(
                        _restoration_foreground_command(command),
                        limits=limits,
                        absolute_deadline=absolute_deadline,
                        environment=environment,
                        cwd=cwd,
                        status_path=status_path,
                        rss_scope="closure",
                    )

                base.run_guarded = _contained_restoration_guard
                try:
                    result = original_restoration(**adjusted)
                finally:
                    if had_run_guarded:
                        base.run_guarded = previous_run_guarded
                    else:
                        delattr(base, "run_guarded")
                    base.GLOBAL_HP_LOCK = previous
        except LeaseUnavailable:
            return {
                "attempt_kind": "HP_FAILURE_RESTORATION",
                "endpoint_float64_sha256": candidate.endpoint_sha256,
                "residual_inf": candidate.residual_inf,
                "provisional_target": candidate.provisional_target,
                "cluster_ordinal": candidate.cluster_ordinal,
                "cluster_rank": candidate.cluster_rank,
                "status": "LOCK_BUSY_DEFERRED",
                "authority_pass": False,
                "descriptor": None,
                "resource_busy_deferred": True,
            }
        process = result.get("process")
        if (
            isinstance(process, Mapping)
            and process.get("classification")
            == "MEMORY_RESERVATION_TIMEOUT"
            and result.get("authority_pass") is not True
        ):
            result = dict(result)
            result["status"] = "MEMORY_BUSY_DEFERRED"
            result["resource_busy_deferred"] = True
            return result
        restoration_document = None
        restoration_path = Path(kwargs["output"]) / "RESULT.json"
        try:
            loaded = json.loads(restoration_path.read_text(encoding="utf-8"))
            if isinstance(loaded, Mapping):
                restoration_document = loaded
        except (OSError, json.JSONDecodeError):
            pass
        terminal_evidence = _restoration_terminal_evidence(
            result=result,
            document=restoration_document,
            source_sha256=str(kwargs.get("source_sha256", "")),
        )
        result = dict(result)
        result["terminal_evidence"] = terminal_evidence
        result["status"] = str(terminal_evidence["terminal_kind"])
        result["authority_pass"] = (
            terminal_evidence["terminal_kind"] == "TARGET_AUTHORITY_READY"
        )
        if result["authority_pass"] is not True:
            result["descriptor"] = None
        return result

    base._run_hp_candidate = _candidate_run_hp_candidate
    base._run_restoration_candidate = _candidate_restoration
