#!/usr/bin/env python3
"""Outer exact-coordinate decorator for an already-installed HP scheduler.

The scheduler worker is selected once, globally, before any source is read.
Its installed ``BASE._run_hp_candidate`` is captured exactly once and remains
the ordinary HP attempt.  This module changes neither search nor numerical HP
policy; it only adds the frozen, audited degree-eight exact source-replay tail.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import time
from typing import Mapping
import ast


HERE = Path(__file__).resolve().parent
ROOT = Path(
    os.environ.get(
        "GEOTARGET_CURRENT_RUNTIME_ROOT",
        "/home/kabatan/work/solver-experiment-runtime/solver",
    )
).resolve()
DEFAULT_SCHEDULER_WORKER = (
    ROOT
    / "research/experiments/EXP-V15-243-001/candidates/"
    "hp_scheduler_preserve_binding/worker.py"
)
SCHEDULER_ENV = "GEOTARGET_EXACT_OUTER_SCHEDULER_WORKER"
MODE_ENV = "GEOTARGET_EXACT_OUTER_MODE"
FAILURE_ONLY = "FAILURE_ONLY"
CONFIRM_ALL_AUTHORITIES = "CONFIRM_ALL_AUTHORITIES"
MODES = frozenset((FAILURE_ONLY, CONFIRM_ALL_AUTHORITIES))

EXACT_ROOT = (
    ROOT
    / "research/experiments/EXP-V15-243-001/candidates/"
    "exact_coordinate_replay"
)
EXACT_CANDIDATE = EXACT_ROOT / "candidate.py"
BASELINE_EXACT_WORKER = EXACT_ROOT / "fallback_worker.py"
EXACT_WORKER = HERE / "fallback_worker.py"
EXACT_AUDIT = EXACT_ROOT / "FINAL_ROOT_ORDINAL_BOUNDARY_AUDIT.json"
EXACT_REFINER = (
    ROOT / "research/experiments/EXP-REAL61-001/refine_proposals_worker.py"
)
EXACT_DAG = (
    ROOT
    / "research/experiments/EXP-REAL61-004/qqbar_exact_replay/dag_compile.py"
)
EXACT_QQBAR = (
    ROOT
    / "research/experiments/EXP-REAL61-004/qqbar_exact_replay/qqbar_worker.jl"
)
AUTHORITY_BOUNDARY = HERE / "authority_boundary.py"

EXPECTED_EXACT_SHA256 = {
    EXACT_CANDIDATE: (
        "e0f24e605e7e7211d134ddea66e66adbb89307148a8f03c1afebd4a2c969c66f"
    ),
    BASELINE_EXACT_WORKER: (
        "44d6fa802dc51e7f58e5a72e48b434a62be84275c328bd605f0e9e2f6eb11900"
    ),
    EXACT_REFINER: (
        "14a107893f6db1b9ec113c28653a40b3817f274865b0fabc64e2a13702bdc7b3"
    ),
    EXACT_AUDIT: (
        "fa133c7243b9f455bbb4f80de1613efc53bc590ffc8556ec8ea4eee2377c3566"
    ),
    # These executable roots are also frozen by the pinned final audit.
    EXACT_DAG: (
        "9b83181004a8ea2ea73f2974129e37ce252f7d352937b9f8b601b39eddf03d18"
    ),
    EXACT_QQBAR: (
        "3ac6415600da77f8748a11d15fa47eb3dcb9f8deada375388fc762a155df0b4a"
    ),
}

MINIMUM_FALLBACK_REMAINING_SECONDS = 7.0
MAXIMUM_FALLBACK_SECONDS = 12.0
# Safe default: the historically comparable failure-only arm must be selected
# explicitly because ordinary numerical authority is not source-certified.
MODE = os.environ.get(MODE_ENV, CONFIRM_ALL_AUTHORITIES)
if MODE not in MODES:
    raise RuntimeError(f"invalid global exact outer mode: {MODE!r}")

if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import authority_boundary as boundary  # noqa: E402


class IntegrationError(RuntimeError):
    """The supplied scheduler or frozen exact closure is incompatible."""


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_exact_freeze() -> dict[str, str]:
    observed = {
        str(path.resolve()): _sha256(path) if path.is_file() else "MISSING"
        for path in EXPECTED_EXACT_SHA256
    }
    expected = {
        str(path.resolve()): digest
        for path, digest in EXPECTED_EXACT_SHA256.items()
    }
    if observed != expected:
        raise IntegrationError("frozen exact-coordinate closure changed")
    return observed


def _load(name: str, path: Path):
    specification = importlib.util.spec_from_file_location(name, path)
    if specification is None or specification.loader is None:
        raise ImportError(path)
    module = importlib.util.module_from_spec(specification)
    sys.modules[name] = module
    specification.loader.exec_module(module)
    return module


def _base(module: object):
    direct = getattr(module, "BASE", None)
    if direct is not None:
        return direct
    scheduler = getattr(module, "SCHEDULER", None)
    champion = getattr(scheduler, "CHAMPION", None)
    indirect = getattr(champion, "BASE", None)
    if indirect is not None:
        return indirect
    raise IntegrationError("scheduler worker does not expose its installed BASE")


def _resource_runtime(module: object):
    candidates = (getattr(module, "SCHEDULER", None), module)
    for candidate in candidates:
        if (
            candidate is not None
            and getattr(candidate, "adapter", None) is not None
            and getattr(candidate, "RESOURCE_BUSY_STATUSES", None) is not None
        ):
            return candidate
    raise IntegrationError("scheduler does not expose resource requeue contract")


verify_exact_freeze()
SCHEDULER_WORKER = Path(
    os.environ.get(SCHEDULER_ENV, str(DEFAULT_SCHEDULER_WORKER))
).resolve()
if not SCHEDULER_WORKER.is_file():
    raise IntegrationError(f"scheduler worker is missing: {SCHEDULER_WORKER}")
_FROZEN_SCHEDULER_SHA256 = _sha256(SCHEDULER_WORKER)
SCHEDULER_MODULE = _load(
    "geotarget_exact_outer_selected_scheduler", SCHEDULER_WORKER
)
BASE = _base(SCHEDULER_MODULE)
RESOURCE = _resource_runtime(SCHEDULER_MODULE)
RESOURCE_BUSY_STATUSES = frozenset(RESOURCE.RESOURCE_BUSY_STATUSES)
if RESOURCE_BUSY_STATUSES != frozenset(
    ("LOCK_BUSY_DEFERRED", "MEMORY_BUSY_DEFERRED")
):
    raise IntegrationError("unknown scheduler resource-busy terminal set")

# Capture the scheduler-applied numerical HP callable once.  The execution
# path below never looks it up dynamically, so later decorator installation
# cannot accidentally recurse or silently change the selected numerical arm.
_ORDINARY_HP = BASE._run_hp_candidate
ORDINARY_HP_CAPTURE_COUNT = 1
_SCHEDULER_PLAN = BASE._plan


def _ordinary_ready(value: object) -> bool:
    return bool(
        isinstance(value, Mapping)
        and value.get("status") == "TARGET_AUTHORITY_READY"
        and value.get("authority_pass") is True
        and boundary.exact_descriptor(value.get("descriptor")) is not None
    )


def _ordinary_resource_busy(value: object) -> bool:
    return bool(
        isinstance(value, Mapping)
        # The outer scheduler's requeue authority is the typed status, not an
        # advisory Boolean.  Requiring that same status prevents a malformed
        # flag-only terminal from being returned as though it were requeueable.
        and value.get("status") in RESOURCE_BUSY_STATUSES
    )


def _confirmation_failure(
    ordinary: Mapping[str, object],
    *,
    status: str,
    evidence: Mapping[str, object],
) -> dict[str, object]:
    return {
        "attempt_kind": "EXACT_CONFIRMATION_OF_ORDINARY_PROPOSAL",
        "endpoint_float64_sha256": ordinary.get("endpoint_float64_sha256"),
        "residual_inf": ordinary.get("residual_inf"),
        "provisional_target": ordinary.get("provisional_target"),
        "cluster_ordinal": ordinary.get("cluster_ordinal"),
        "cluster_rank": ordinary.get("cluster_rank"),
        "status": status,
        "authority_pass": False,
        "descriptor": None,
        "ordinary_hp_proposal": dict(ordinary),
        "exact_coordinate_fallback": dict(evidence),
        "ordinary_descriptor_is_final_authority": False,
        "case_family_truth_target_count_routing": False,
    }


def _fallback_command(
    *,
    source: Path,
    source_sha256: str,
    candidate: object,
    cpu: int,
    artifact: Path,
    fallback_seconds: float,
    exact_worker: Path = BASELINE_EXACT_WORKER,
) -> list[str]:
    return [
        "taskset",
        "-c",
        str(cpu),
        str(BASE.PYTHON),
        str(exact_worker),
        "--source",
        str(source.resolve()),
        "--source-sha256",
        source_sha256,
        "--endpoint",
        json.dumps(
            candidate.endpoint,
            separators=(",", ":"),
            allow_nan=False,
        ),
        "--endpoint-sha256",
        candidate.endpoint_sha256,
        "--timeout-seconds",
        str(max(0.5, fallback_seconds - 0.5)),
        "--output",
        str(artifact.resolve()),
    ]


def _consume_fallback(
    *,
    fallback: object,
    guarded: object,
    source: Path,
    source_sha256: str,
    candidate: object,
) -> dict[str, object] | None:
    descriptor = (
        boundary.exact_descriptor(fallback.get("descriptor"))
        if isinstance(fallback, Mapping)
        else None
    )
    try:
        source_document = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        source_document = None
    accepted = bool(
        guarded is not None
        and guarded.accepted_output
        and guarded.descendant_leak is not True
        and isinstance(fallback, Mapping)
        and fallback.get("schema_version")
        == "geotarget.v15-243-exact-coordinate-fallback/v1"
        and fallback.get("completed") is True
        and fallback.get("status")
        == "EXACT_COORDINATE_TARGET_AUTHORITY_READY"
        and fallback.get("authority_pass") is True
        and boundary.matches_sha256(source, source_sha256)
        and fallback.get("source_sha256") == source_sha256
        and fallback.get("endpoint_float64_sha256")
        == candidate.endpoint_sha256
        and fallback.get("truth_used") is False
        and fallback.get("case_family_known_target_count_routing") is False
        and fallback.get("source_or_problem_modified") is False
        and fallback.get("bounds_added_or_inferred") is False
        and fallback.get("coordinate_reparameterization") is False
        and fallback.get("target_set_completeness_claim") is False
        and fallback.get("within_fallback_wall_budget") is True
        and descriptor is not None
        and isinstance(source_document, Mapping)
        and boundary.nested_exact_authority_matches_source(
            fallback,
            descriptor,
            source_document,
            source_sha256,
        )
    )
    return descriptor if accepted else None


def _run_current_exact_outer(**kwargs) -> dict[str, object] | None:
    verify_exact_freeze()
    timeout_seconds = float(kwargs["timeout_seconds"])
    started = time.monotonic()
    ordinary = _ORDINARY_HP(**kwargs)
    if _ordinary_resource_busy(ordinary):
        # Resource contention is not numerical failure.  Return the exact
        # scheduler terminal by identity so its outer service loop requeues.
        return ordinary

    ready = _ordinary_ready(ordinary)
    if MODE == FAILURE_ONLY and ready:
        return ordinary
    if not isinstance(ordinary, Mapping):
        return ordinary
    if not ready:
        if ordinary.get("authority_pass") is True:
            # A malformed success terminal is neither an authority nor a
            # genuine numerical failure eligible for an exact fallback.
            return _confirmation_failure(
                ordinary,
                status="MALFORMED_ORDINARY_AUTHORITY_REJECTED",
                evidence={"status": "NOT_RUN_MALFORMED_ORDINARY_TERMINAL"},
            )
        if ordinary.get("authority_pass") is not False:
            return dict(ordinary)

    remaining = timeout_seconds - (time.monotonic() - started)
    if remaining < MINIMUM_FALLBACK_REMAINING_SECONDS:
        evidence = {
            "status": "NOT_RUN_INSUFFICIENT_ENDPOINT_ALLOCATION",
            "minimum_remaining_seconds": MINIMUM_FALLBACK_REMAINING_SECONDS,
            "observed_remaining_seconds": max(0.0, remaining),
        }
        if ready or MODE == CONFIRM_ALL_AUTHORITIES and ordinary.get(
            "authority_pass"
        ) is True:
            return _confirmation_failure(
                ordinary,
                status="EXACT_CONFIRMATION_NOT_RUN",
                evidence=evidence,
            )
        result = dict(ordinary)
        result["exact_coordinate_fallback"] = evidence
        return result

    source = Path(kwargs["source"])
    source_sha256 = str(kwargs["source_sha256"])
    candidate = kwargs["candidate"]
    cpu = int(kwargs["cpu"])
    root = Path(kwargs["output"]) / "exact-coordinate-fallback"
    artifact = root / "RESULT.json"
    artifact.unlink(missing_ok=True)
    fallback_seconds = min(
        MAXIMUM_FALLBACK_SECONDS,
        max(0.5, remaining - 0.5),
    )
    command = _fallback_command(
        source=source,
        source_sha256=source_sha256,
        candidate=candidate,
        cpu=cpu,
        artifact=artifact,
        fallback_seconds=fallback_seconds,
    )

    guarded = None
    lease_status = "ACQUIRED"
    try:
        with RESOURCE.adapter.per_core_lease(
            cpu,
            wait_seconds=min(
                RESOURCE.adapter.DEFAULT_POLICY.maximum_core_lease_wait_seconds,
                max(0.0, fallback_seconds - 1.0),
            ),
        ):
            root.mkdir(parents=True, exist_ok=True)
            guarded = BASE.run_guarded(
                command,
                limits=BASE.Limits(
                    timeout_seconds=fallback_seconds,
                    rss_bytes=768 * 1024**2,
                    address_space_bytes=3072 * 1024**2,
                    data_bytes=2048 * 1024**2,
                    output_bytes=1024**2,
                    tail_bytes=16 * 1024,
                ),
                environment=BASE.THREAD_ENVIRONMENT,
                cwd=ROOT,
                status_path=root / "process-status.json",
            )
            if guarded.classification == "MEMORY_RESERVATION_TIMEOUT":
                lease_status = "MEMORY_BUSY_DEFERRED"
    except RESOURCE.adapter.LeaseUnavailable:
        lease_status = "LOCK_BUSY_DEFERRED"

    fallback = None
    try:
        loaded = json.loads(artifact.read_text(encoding="utf-8"))
        if isinstance(loaded, Mapping):
            fallback = loaded
    except (OSError, json.JSONDecodeError):
        pass
    descriptor = _consume_fallback(
        fallback=fallback,
        guarded=guarded,
        source=source,
        source_sha256=source_sha256,
        candidate=candidate,
    )
    accepted = descriptor is not None
    fallback_evidence = {
        "status": (
            "TARGET_AUTHORITY_READY"
            if accepted
            else (
                lease_status
                if lease_status in RESOURCE_BUSY_STATUSES
                else (
                    fallback.get("status")
                    if isinstance(fallback, Mapping)
                    else lease_status
                )
            )
        ),
        "authority_pass": accepted,
        "lease_status": lease_status,
        "allocated_seconds": fallback_seconds,
        "result_sha256": _sha256(artifact) if artifact.is_file() else None,
        "process": guarded.to_dict() if guarded is not None else None,
        "truth_used": False,
        "target_set_completeness_claim": False,
        "maximum_recognition_degree": 8,
    }
    if not accepted:
        if lease_status in RESOURCE_BUSY_STATUSES:
            result = dict(ordinary)
            result["exact_coordinate_fallback"] = fallback_evidence
            result.update(
                {
                    "status": lease_status,
                    "authority_pass": False,
                    "descriptor": None,
                    "resource_busy_deferred": True,
                }
            )
            return result
        if ready:
            return _confirmation_failure(
                ordinary,
                status="EXACT_CONFIRMATION_REJECTED",
                evidence=fallback_evidence,
            )
        result = dict(ordinary)
        result["exact_coordinate_fallback"] = fallback_evidence
        return result

    if ready:
        ordinary_identity = boundary.descriptor_identity(
            ordinary.get("descriptor")
        )
        exact_identity = boundary.descriptor_identity(descriptor)
        if ordinary_identity is None or ordinary_identity != exact_identity:
            evidence = dict(fallback_evidence)
            evidence.update(
                {
                    "status": "EXACT_DESCRIPTOR_MISMATCH",
                    "authority_pass": False,
                    "ordinary_exact_identity": ordinary_identity,
                    "fallback_exact_identity": exact_identity,
                }
            )
            return _confirmation_failure(
                ordinary,
                status="EXACT_CONFIRMATION_DESCRIPTOR_MISMATCH",
                evidence=evidence,
            )

    return {
        "attempt_kind": (
            "EXACT_CONFIRMATION_OF_ORDINARY_PROPOSAL"
            if ready
            else "FAILURE_ONLY_EXACT_COORDINATE_QQBAR_REPLAY"
        ),
        "endpoint_float64_sha256": candidate.endpoint_sha256,
        "residual_inf": candidate.residual_inf,
        "provisional_target": candidate.provisional_target,
        "cluster_ordinal": candidate.cluster_ordinal,
        "cluster_rank": candidate.cluster_rank,
        "status": "TARGET_AUTHORITY_READY",
        "authority_pass": True,
        "descriptor": descriptor,
        "ordinary_hp_attempt" if not ready else "ordinary_hp_proposal": ordinary,
        "exact_coordinate_fallback": fallback_evidence,
        "ordinary_descriptor_is_final_authority": False if ready else None,
        "ordinary_and_exact_descriptor_identity_match": ready,
        "case_family_truth_target_count_routing": False,
    }


def _direct_angle_arity(left: object, right: object) -> int | None:
    def angle_call(value: object) -> ast.Call | None:
        if not isinstance(value, str):
            return None
        try:
            node = ast.parse(value, mode="eval").body
        except SyntaxError:
            return None
        if (
            not isinstance(node, ast.Call)
            or not isinstance(node.func, ast.Name)
            or node.func.id != "Angle"
            or node.keywords
            or len(node.args) not in (2, 3)
        ):
            return None
        return node

    left_call, right_call = angle_call(left), angle_call(right)
    if left_call is None or right_call is None:
        return None
    return len(left_call.args) if len(left_call.args) == len(right_call.args) else None


def _direct_typed_angle_count(source: Path, source_sha256: str) -> int:
    if not boundary.matches_sha256(source, source_sha256):
        return 0
    try:
        document = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return 0
    constraints = document.get("constraints") if isinstance(document, Mapping) else None
    if not isinstance(constraints, list):
        return 0
    return sum(
        _direct_angle_arity(item.get("def"), item.get("value")) is not None
        for item in constraints
        if isinstance(item, Mapping)
    )


def _baseline_ambiguous_angle_failure(
    *, output: Path, source_sha256: str, endpoint_sha256: str
) -> bool:
    artifact = output / "exact-coordinate-fallback/RESULT.json"
    try:
        value = json.loads(artifact.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    return bool(
        isinstance(value, Mapping)
        and value.get("schema_version")
        == "geotarget.v15-243-exact-coordinate-fallback/v1"
        and value.get("source_sha256") == source_sha256
        and value.get("endpoint_float64_sha256") == endpoint_sha256
        and value.get("status") == "EXACT_COORDINATE_FALLBACK_REJECTED"
        and value.get("authority_pass") is False
        and "angle equality has ambiguous full-turn lift"
        in str(value.get("failure", ""))
    )


def _run_modified_angle_side(
    *, kwargs: Mapping[str, object], side_seconds: float
) -> tuple[dict[str, object] | None, dict[str, object]]:
    source = Path(kwargs["source"])
    source_sha256 = str(kwargs["source_sha256"])
    candidate = kwargs["candidate"]
    cpu = int(kwargs["cpu"])
    root = Path(kwargs["output"]) / "exact-typed-angle-repair-a"
    artifact = root / "RESULT.json"
    artifact.unlink(missing_ok=True)
    command = _fallback_command(
        source=source,
        source_sha256=source_sha256,
        candidate=candidate,
        cpu=cpu,
        artifact=artifact,
        fallback_seconds=side_seconds,
        exact_worker=EXACT_WORKER,
    )
    guarded = None
    lease_status = "ACQUIRED"
    try:
        with RESOURCE.adapter.per_core_lease(
            cpu,
            wait_seconds=min(
                RESOURCE.adapter.DEFAULT_POLICY.maximum_core_lease_wait_seconds,
                max(0.0, side_seconds - 1.0),
            ),
        ):
            root.mkdir(parents=True, exist_ok=True)
            guarded = BASE.run_guarded(
                command,
                limits=BASE.Limits(
                    timeout_seconds=side_seconds,
                    rss_bytes=768 * 1024**2,
                    address_space_bytes=3072 * 1024**2,
                    data_bytes=2048 * 1024**2,
                    output_bytes=1024**2,
                    tail_bytes=16 * 1024,
                ),
                environment=BASE.THREAD_ENVIRONMENT,
                cwd=ROOT,
                status_path=root / "process-status.json",
            )
            if guarded.classification == "MEMORY_RESERVATION_TIMEOUT":
                lease_status = "MEMORY_BUSY_DEFERRED"
    except RESOURCE.adapter.LeaseUnavailable:
        lease_status = "LOCK_BUSY_DEFERRED"

    fallback = None
    try:
        loaded = json.loads(artifact.read_text(encoding="utf-8"))
        if isinstance(loaded, Mapping):
            fallback = loaded
    except (OSError, json.JSONDecodeError):
        pass
    descriptor = _consume_fallback(
        fallback=fallback,
        guarded=guarded,
        source=source,
        source_sha256=source_sha256,
        candidate=candidate,
    )
    exact = fallback.get("exact_coordinate_authority") if isinstance(fallback, Mapping) else None
    containment = fallback.get("containment") if isinstance(fallback, Mapping) else None
    activated = bool(
        descriptor is not None
        and fallback.get("typed_direct_angle_equality_exact") is True
        and isinstance(fallback.get("typed_angle_relation_count"), int)
        and not isinstance(fallback.get("typed_angle_relation_count"), bool)
        and int(fallback.get("typed_angle_relation_count")) > 0
        and isinstance(exact, Mapping)
        and exact.get("typed_direct_angle_equality_exact") is True
        and exact.get("typed_angle_relation_count")
        == fallback.get("typed_angle_relation_count")
        and isinstance(containment, Mapping)
        and containment.get("same_process_group") is True
        and containment.get("pdeathsig") == 9
        and containment.get("cpu_affinity") == [cpu]
    )
    evidence = {
        "status": "TARGET_AUTHORITY_READY" if activated else lease_status,
        "authority_pass": activated,
        "allocated_seconds": side_seconds,
        "result_sha256": _sha256(artifact) if artifact.is_file() else None,
        "process": guarded.to_dict() if guarded is not None else None,
        "typed_angle_relation_count": (
            fallback.get("typed_angle_relation_count")
            if isinstance(fallback, Mapping)
            else None
        ),
        "containment": dict(containment) if isinstance(containment, Mapping) else None,
        "truth_used": False,
        "target_set_completeness_claim": False,
    }
    return descriptor if activated else None, evidence


def _run_repair_a(**kwargs) -> dict[str, object] | None:
    timeout_seconds = float(kwargs["timeout_seconds"])
    baseline_fraction = 0.75
    side_fraction = 0.25
    started = time.monotonic()
    baseline_kwargs = dict(kwargs)
    baseline_kwargs["timeout_seconds"] = max(0.5, timeout_seconds * baseline_fraction)
    baseline = _run_current_exact_outer(**baseline_kwargs)
    if _ordinary_resource_busy(baseline) or _ordinary_ready(baseline):
        return baseline
    candidate = kwargs["candidate"]
    endpoint = getattr(candidate, "endpoint", None)
    if not isinstance(endpoint, (list, tuple)) or len(endpoint) == 0:
        return baseline
    if not isinstance(baseline, Mapping):
        return baseline
    source = Path(kwargs["source"])
    source_sha256 = str(kwargs["source_sha256"])
    if _direct_typed_angle_count(source, source_sha256) == 0:
        return baseline
    if not _baseline_ambiguous_angle_failure(
        output=Path(kwargs["output"]),
        source_sha256=source_sha256,
        endpoint_sha256=str(candidate.endpoint_sha256),
    ):
        return baseline
    remaining = timeout_seconds - (time.monotonic() - started)
    side_seconds = min(timeout_seconds * side_fraction, remaining)
    if side_seconds < 0.5:
        return baseline
    descriptor, evidence = _run_modified_angle_side(
        kwargs=kwargs,
        side_seconds=side_seconds,
    )
    if descriptor is None:
        # Required byte/object-identical fallback: no telemetry is attached.
        return baseline
    return {
        "attempt_kind": "EXACT_TYPED_ANGLE_EQUALITY_REPAIR_A",
        "endpoint_float64_sha256": candidate.endpoint_sha256,
        "residual_inf": candidate.residual_inf,
        "provisional_target": candidate.provisional_target,
        "cluster_ordinal": candidate.cluster_ordinal,
        "cluster_rank": candidate.cluster_rank,
        "status": "TARGET_AUTHORITY_READY",
        "authority_pass": True,
        "descriptor": descriptor,
        "baseline_exact_outer_result": baseline,
        "typed_angle_repair_a": evidence,
        "baseline_minimum_fraction": baseline_fraction,
        "side_maximum_fraction": side_fraction,
        "ordinary_descriptor_is_final_authority": False,
        "case_family_truth_target_count_routing": False,
    }


if getattr(BASE, "_geotarget_exact_outer_installed", False):
    raise IntegrationError("exact outer decorator was installed twice")
BASE._run_hp_candidate = _run_repair_a
BASE._geotarget_exact_outer_installed = True


def _compact_closure() -> dict[str, object]:
    verify_exact_freeze()
    if _sha256(SCHEDULER_WORKER) != _FROZEN_SCHEDULER_SHA256:
        raise IntegrationError("selected scheduler changed after import")
    files = [
        {
            "role": "selected_scheduler_entry",
            "kind": "delegated_executable_entrypoint",
            "path": str(SCHEDULER_WORKER),
            "sha256": _FROZEN_SCHEDULER_SHA256,
            "delegates_transitive_closure_to_scheduler_plan": True,
        },
        {
            "role": "outer_decorator",
            "kind": "executable_python",
            "path": str(Path(__file__).resolve()),
            "sha256": _sha256(Path(__file__)),
        },
        {
            "role": "outer_authority_boundary",
            "kind": "executable_python",
            "path": str(AUTHORITY_BOUNDARY.resolve()),
            "sha256": _sha256(AUTHORITY_BOUNDARY),
        },
    ]
    roles = {
        EXACT_CANDIDATE: ("degree8_exact_candidate", "executable_python"),
        BASELINE_EXACT_WORKER: ("exact_fallback_child", "executable_python"),
        EXACT_REFINER: ("independent_numeric_refiner", "executable_python"),
        EXACT_DAG: ("exact_dag_compiler", "executable_python"),
        EXACT_QQBAR: ("qqbar_replay_worker", "executable_julia"),
        EXACT_AUDIT: ("read_only_final_boundary_audit", "evidence_json"),
    }
    files.extend(
        {
            "role": roles[path][0],
            "kind": roles[path][1],
            "path": str(path.resolve()),
            "sha256": EXPECTED_EXACT_SHA256[path],
        }
        for path in roles
    )
    repair_roles = {
        EXACT_WORKER: ("repair_a_exact_fallback_child", "executable_python"),
        HERE / "candidate.py": ("repair_a_exact_candidate", "executable_python"),
        HERE / "dag_compile.py": ("repair_a_dag_compiler", "executable_python"),
        HERE / "qqbar_worker.jl": ("repair_a_qqbar_base", "executable_julia"),
    }
    files.extend(
        {
            "role": role,
            "kind": kind,
            "path": str(path.resolve()),
            "sha256": _sha256(path),
        }
        for path, (role, kind) in repair_roles.items()
    )
    payload = {
        "schema_version": "geotarget.v15-243-exact-angle-repair-a-closure/v1",
        "closure_kind": (
            "compact executable roots plus delegated scheduler plan closure"
        ),
        "files": files,
        "maximum_recognition_degree": 8,
        "exact_authority_is_numeric_and_exact_conjunction": True,
        "audit_decision": "GO_WITH_PINNED_TRUSTED_CHILD_MODEL",
        "environment_hermetic": False,
        "julia_nemo_and_os_environment_digest": None,
    }
    payload["closure_sha256"] = hashlib.sha256(
        json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        ).encode("ascii")
    ).hexdigest()
    return payload


def _plan(**kwargs) -> dict[str, object]:
    plan = _SCHEDULER_PLAN(**kwargs)
    closure = _compact_closure()
    plan.update(
        {
            "schema_version": "geotarget.v15-243-exact-angle-repair-a-plan/v1",
            "exact_outer_mode": MODE,
            "exact_outer_mode_is_global_not_case_routed": True,
            "exact_outer_scheduler_worker": str(SCHEDULER_WORKER),
            "exact_outer_scheduler_worker_sha256": _FROZEN_SCHEDULER_SHA256,
            "exact_outer_ordinary_hp_capture_count": ORDINARY_HP_CAPTURE_COUNT,
            "exact_outer_ordinary_hp_callable_module": getattr(
                _ORDINARY_HP, "__module__", None
            ),
            "exact_outer_ordinary_hp_callable_name": getattr(
                _ORDINARY_HP, "__name__", type(_ORDINARY_HP).__name__
            ),
            "exact_coordinate_fallback": {
                "policy": (
                    "failure-only historical ablation"
                    if MODE == FAILURE_ONLY
                    else (
                        "confirm every ordinary authority with independent "
                        "degree-eight exact coordinate source replay"
                    )
                ),
                "minimum_remaining_seconds": (
                    MINIMUM_FALLBACK_REMAINING_SECONDS
                ),
                "maximum_seconds": MAXIMUM_FALLBACK_SECONDS,
                "ordinary_descriptor_is_proposal_only_in_confirm_all": True,
                "descriptor_match_key": (
                    "primitive minimal polynomial plus zero-based sorted-real-"
                    "root ordinal"
                ),
                "resource_busy_is_requeued_not_numerical_failure": True,
                "combined_numeric_and_exact_source_authority": True,
                "target_set_completeness_claim": False,
                "measured_confirm_all_coverage_claim": False,
                "closure": closure,
            },
            "case_family_truth_target_count_routing": False,
            "exact_typed_angle_repair_a": {
                "baseline_worker": str(BASELINE_EXACT_WORKER),
                "modified_worker": str(EXACT_WORKER),
                "baseline_minimum_fraction": 0.75,
                "side_maximum_fraction": 0.25,
                "activation": (
                    "direct same-arity Angle=Angle source plus exact baseline "
                    "ambiguous-full-turn failure"
                ),
                "side_failure_returns_baseline_object_by_identity": True,
                "zero_dimension_unchanged": True,
                "qreflect_used": False,
            },
        }
    )
    return plan


BASE._plan = _plan


def main() -> None:
    verify_exact_freeze()
    if _sha256(SCHEDULER_WORKER) != _FROZEN_SCHEDULER_SHA256:
        raise IntegrationError("selected scheduler changed after import")
    SCHEDULER_MODULE.main()


if __name__ == "__main__":
    main()
