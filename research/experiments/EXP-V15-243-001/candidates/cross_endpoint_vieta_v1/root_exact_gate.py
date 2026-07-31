#!/usr/bin/env python3
"""Root-custody aggregate gate for stored cross-endpoint Vieta proposals.

The coordinator is the only supported benchmark entry point.  It accepts an
anonymous, truth-free private manifest, runs every subset in a fresh bounded
process on the already-exclusive CPU14, and emits no per-subset result.  A
separate mode-0600 sidecar contains only the distinct source SHA-256 values
for which bounded structural Vieta reconstruction succeeded.  That file
is for a root-owned aggregate join; it contains neither control outcome nor
canonical replay outcome.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import fcntl
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import sys
import tempfile
from typing import Any, Mapping, Sequence


HERE = Path(__file__).resolve().parent
RUNNER = Path(__file__).resolve()
CONNECTOR = HERE / "canonical_connector.py"
CONNECTOR_SHA256 = "317f732f5d62ef1f92496ad6bbe1119401402377cbe63ce9765e318dbfbc4f74"
RUNTIME_ROOT = Path("/home/kabatan/work/solver-experiment-runtime/solver")
RESULTS_ROOT = Path("/home/kabatan/work/solver-experiment-results")
PYTHON = RUNTIME_ROOT / "python/.venv/bin/python"
SAFE_SUBPROCESS = (
    RUNTIME_ROOT / "research/infrastructure/memory_safety/safe_subprocess.py"
)
SAFE_LIMIT_EXEC = SAFE_SUBPROCESS.with_name("_limit_exec.py")
OFFICIAL_GLOBAL_LOCK = Path("/tmp/geotarget-exp-global-benchmark-v1.lock")

PANEL_SCHEMA = "geotarget.cross-endpoint-vieta-private-gate/v1"
WORK_ITEM_SCHEMA = "geotarget.cross-endpoint-vieta-private-subset/v3"
WORKER_SCHEMA = "geotarget.cross-endpoint-vieta-private-worker/v1"
AGGREGATE_SCHEMA = "geotarget.cross-endpoint-vieta-canonical-gate/v1"
PROPOSAL_SOURCE_SCHEMA = "geotarget.cross-endpoint-vieta-proposal-source-sha/v1"
MAX_MANIFEST_BYTES = 64 * 1024 * 1024
MAX_RESULT_BYTES = 64 * 1024
MAX_SUBSETS = 595
MAX_SOURCES = 128
MAX_SUBSETS_PER_SOURCE = 16
MIN_PER_ENDPOINT_SECONDS = 1.0
MAX_PER_ENDPOINT_SECONDS = 30.0

GATE_DEPENDENCIES = {
    PYTHON: "ccc93c55c24bb92866cc2f9eff61b124abf5d1ee6c8da0ef9b5eed4d78a21f07",
    SAFE_SUBPROCESS: "76aa547f235bd0ae11c8b567461384b22537a9b98c990db2ed126db0a19b55c5",
    SAFE_LIMIT_EXEC: "2173e83e6bcdc96bff5de5957f96b85a1281f7070e9e21deea047f81a16af8fb",
}

THREAD_ENVIRONMENT = {
    "PYTHONHASHSEED": "0",
    "OMP_NUM_THREADS": "1",
    "OMP_THREAD_LIMIT": "1",
    "OPENBLAS_NUM_THREADS": "1",
    "MKL_NUM_THREADS": "1",
    "BLIS_NUM_THREADS": "1",
    "GOTO_NUM_THREADS": "1",
    "VECLIB_MAXIMUM_THREADS": "1",
    "NUMEXPR_NUM_THREADS": "1",
    "JULIA_NUM_THREADS": "1",
    "JULIA_NUM_GC_THREADS": "1",
    "JULIA_NUM_PRECOMPILE_TASKS": "1",
    "JULIA_PKG_PRECOMPILE_AUTO": "0",
    "MALLOC_ARENA_MAX": "2",
}

WORKER_KEYS = frozenset(
    {
        "schema_version",
        "input_binding_sha256",
        "source_sha256",
        "structural_signature_sha256",
        "degree",
        "status",
        "reason",
        "bounded_rational_reconstruction_passed",
        "independent_rung_agreement_passed",
        "numeric_gate_passed",
        "proposal_constructed",
        "numeric_guard_branch_parity_passed",
        "factor_level_independent_rung_parity_pass_count",
        "factor_level_rejected_endpoint_count",
        "replay_calls",
        "canonical_replay_accepted_count",
        "canonical_replay_rejected_count",
        "canonical_replay_exception_count",
        "canonical_ready",
        "canonical_emitted_endpoint_count",
        "descriptor_identity_dedup_count",
        "fallback_identity_preserved",
        "replay_bypass_count",
        "safety_invalid_count",
        "whole_vieta_minimal_descriptor_count",
        "unobserved_root_emit_count",
        "truth_used",
        "target_set_completeness_claim",
    }
)


class GateFailure(RuntimeError):
    pass


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _valid_sha(value: object) -> bool:
    return bool(
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _check_cpu14() -> None:
    if sorted(os.sched_getaffinity(0)) != [14]:
        raise GateFailure("root exact gate requires exclusive CPU14 affinity")


def _check_self(expected_sha256: str) -> None:
    if not _valid_sha(expected_sha256) or _sha256(RUNNER.read_bytes()) != expected_sha256:
        raise GateFailure("root exact gate runner hash drift")


def _within_results(path: Path, *, must_exist: bool) -> Path:
    resolved = path.resolve(strict=must_exist)
    root = RESULTS_ROOT.resolve(strict=True)
    if resolved == root or root not in resolved.parents:
        raise GateFailure("private artifact path is outside the approved results root")
    return resolved


def _load_module(name: str, path: Path):
    specification = importlib.util.spec_from_file_location(name, path)
    if specification is None or specification.loader is None:
        raise GateFailure(f"cannot load frozen module {path.name}")
    module = importlib.util.module_from_spec(specification)
    sys.modules[name] = module
    specification.loader.exec_module(module)
    return module


def _load_connector():
    if _sha256(CONNECTOR.read_bytes()) != CONNECTOR_SHA256:
        raise GateFailure("canonical connector hash drift")
    connector = _load_module("geotarget_cross_endpoint_vieta_connector", CONNECTOR)
    connector.verify_frozen_dependencies()
    return connector


def _load_guard():
    observed = {
        path: _sha256(path.read_bytes()) if path.is_file() else "MISSING"
        for path in GATE_DEPENDENCIES
    }
    if observed != GATE_DEPENDENCIES:
        raise GateFailure("bounded subprocess closure changed")
    return _load_module("geotarget_cross_endpoint_vieta_safe_subprocess", SAFE_SUBPROCESS)


def _source_rank(source_sha256: str) -> str:
    return _sha256(b"vieta-source-v1" + bytes.fromhex(source_sha256))


def _validate_raw_artifact_paths(raw: object) -> None:
    if not isinstance(raw, Mapping):
        raise GateFailure("private subset is not an object")
    _within_results(Path(str(raw.get("source"))), must_exist=True)
    endpoints = raw.get("endpoints")
    if not isinstance(endpoints, list):
        raise GateFailure("private subset endpoint list is absent")
    for endpoint in endpoints:
        if not isinstance(endpoint, Mapping):
            raise GateFailure("private endpoint is not an object")
        for rung_name in ("low", "high"):
            rung = endpoint.get(rung_name)
            if not isinstance(rung, Mapping):
                raise GateFailure("private HP rung is not an object")
            for binding_name in (
                "result_artifact",
                "plan_artifact",
                "lane_artifact",
            ):
                binding = rung.get(binding_name)
                if not isinstance(binding, Mapping) or set(binding) != {"path", "sha256"}:
                    raise GateFailure("private original-artifact binding schema changed")
                _within_results(Path(str(binding.get("path"))), must_exist=True)


def _manifest(path: Path, connector: Any) -> tuple[bytes, list[dict[str, Any]]]:
    path = _within_results(path, must_exist=True)
    payload = path.read_bytes()
    if not payload or len(payload) > MAX_MANIFEST_BYTES:
        raise GateFailure("private panel manifest size invalid")
    try:
        document = json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise GateFailure("private panel manifest is not JSON") from error
    if (
        not isinstance(document, Mapping)
        or set(document) != {"schema_version", "subsets"}
        or document.get("schema_version") != PANEL_SCHEMA
        or not isinstance(document.get("subsets"), list)
        or not 1 <= len(document["subsets"]) <= MAX_SUBSETS
    ):
        raise GateFailure("private panel manifest schema changed")

    rows: list[dict[str, Any]] = []
    subset_digests: set[str] = set()
    source_order: list[str] = []
    grouped_subset_digests: dict[str, list[str]] = defaultdict(list)
    closed_sources: set[str] = set()
    active_source: str | None = None
    for raw in document["subsets"]:
        _validate_raw_artifact_paths(raw)
        try:
            row = connector.validate_private_subset(raw)
        except Exception as error:
            raise GateFailure("private subset failed truth-free custody validation") from error
        source = _within_results(row["source"], must_exist=True)
        row["source"] = source
        source_sha = str(row["source_sha256"])
        subset_sha = str(row["subset_sha256"])
        if subset_sha in subset_digests:
            raise GateFailure("private panel repeats a subset custody digest")
        subset_digests.add(subset_sha)
        if source_sha != active_source:
            if source_sha in closed_sources:
                raise GateFailure("private source groups are not contiguous")
            if active_source is not None:
                closed_sources.add(active_source)
            source_order.append(source_sha)
            active_source = source_sha
        grouped_subset_digests[source_sha].append(subset_sha)
        rows.append(row)
    if len(source_order) > MAX_SOURCES:
        raise GateFailure("private panel exceeds the source cap")
    if source_order != sorted(source_order, key=_source_rank):
        raise GateFailure("private source groups are not hash-ranked")
    for digests in grouped_subset_digests.values():
        if len(digests) > MAX_SUBSETS_PER_SOURCE or digests != sorted(digests):
            raise GateFailure("private subsets are not capped and hash-ranked per source")
    return payload, rows


def _atomic_json(path: Path, value: Mapping[str, Any], *, mode: int = 0o600) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            "w", encoding="utf-8", dir=path.parent, prefix=f".{path.name}.", delete=False
        ) as stream:
            temporary = Path(stream.name)
            json.dump(value, stream, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary, mode)
        os.replace(temporary, path)
        directory = os.open(path.parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def _as_core_endpoints(core: Any, row: Mapping[str, Any]):
    result = []
    raw_by_object: dict[int, Mapping[str, Any]] = {}
    for endpoint in row["endpoints"]:
        low = endpoint["low"]
        high = endpoint["high"]
        observation = core.EndpointObservation(
            source_sha256=row["source_sha256"],
            low=core.HPRung(
                precision_bits=low["precision_bits"],
                provenance_sha256=low["provenance_sha256"],
                target_decimal=low["raw_answer_decimal"],
                full_tuple_decimal=tuple(low["full_tuple_decimal"]),
            ),
            high=core.HPRung(
                precision_bits=high["precision_bits"],
                provenance_sha256=high["provenance_sha256"],
                target_decimal=high["raw_answer_decimal"],
                full_tuple_decimal=tuple(high["full_tuple_decimal"]),
            ),
        )
        result.append(observation)
        raw_by_object[id(observation)] = endpoint
    return tuple(result), raw_by_object


def _serializable_rung(rung: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "precision_bits": rung["precision_bits"],
        "provenance_sha256": rung["provenance_sha256"],
        "raw_answer_decimal": rung["raw_answer_decimal"],
        "full_tuple_decimal": list(rung["full_tuple_decimal"]),
        "result_artifact": {
            "path": str(rung["result_artifact"]["path"]),
            "sha256": rung["result_artifact"]["sha256"],
        },
        "plan_artifact": {
            "path": str(rung["plan_artifact"]["path"]),
            "sha256": rung["plan_artifact"]["sha256"],
        },
        "lane_artifact": {
            "path": str(rung["lane_artifact"]["path"]),
            "sha256": rung["lane_artifact"]["sha256"],
        },
    }


def _stage_flags(reason: str, proposal_constructed: bool) -> tuple[bool, bool, bool]:
    before_reconstruction = {
        "SOURCE_SHA_MISMATCH",
        "DEGREE_OUTSIDE_2_TO_6",
        "REPLAY_NOT_CALLABLE",
        "INVALID_PRECISION_LADDER",
        "INVALID_HEIGHT_BOUND",
        "MIXED_SOURCE_ENDPOINT_SET",
        "RUNGS_NOT_INDEPENDENT_OR_ORDERED",
        "EMPTY_FULL_TUPLE",
        "RUNG_TUPLE_DIMENSION_MISMATCH",
        "MALFORMED_HP_VALUE",
        "DUPLICATE_ENDPOINT_TUPLE",
        "MIXED_TUPLE_DIMENSIONS",
        "BOUNDED_RATIONAL_RECONSTRUCTION_FAILED",
    }
    reconstruction = reason not in before_reconstruction
    agreement = reconstruction and reason != "INDEPENDENT_RUNG_DISAGREEMENT"
    numeric = bool(proposal_constructed)
    return reconstruction, agreement, numeric


def _worker(work_item: Path, output: Path, per_endpoint_seconds: float) -> int:
    _check_cpu14()
    connector = _load_connector()
    payload = work_item.read_bytes()
    if not payload or len(payload) > MAX_MANIFEST_BYTES:
        raise GateFailure("private worker item size invalid")
    try:
        raw = json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise GateFailure("private worker item is not JSON") from error
    _validate_raw_artifact_paths(raw)
    row = connector.validate_private_subset(raw)
    core, exact = connector.load_core_and_exact()
    endpoints, raw_by_object = _as_core_endpoints(core, row)
    counters: Counter[str] = Counter()
    factor_targets: tuple[Mapping[str, Any], ...] | None = None
    factor_preparation_failed = False
    index_by_object = {id(endpoint): index for index, endpoint in enumerate(endpoints)}

    def replay(observation: Any, proposal: Any, root_ordinal: int):
        nonlocal factor_targets, factor_preparation_failed
        counters["calls"] += 1
        if (
            proposal.minimal_descriptor_claimed is not False
            or proposal.descriptor_emission_permitted is not False
        ):
            counters["whole_minimal_descriptor"] += 1
            raise GateFailure("whole Vieta polynomial reached descriptor authority")
        endpoint = raw_by_object.get(id(observation))
        endpoint_index = index_by_object.get(id(observation))
        if endpoint is None or endpoint_index is None:
            counters["exceptions"] += 1
            raise GateFailure("core replayed an endpoint outside the bound subset")
        if factor_targets is None and not factor_preparation_failed:
            try:
                factor_targets = connector.prepare_factorized_targets(
                    exact=exact,
                    endpoints=row["endpoints"],
                    coefficients=proposal.coefficients,
                    subset_root_ordinals=proposal.endpoint_root_ordinals,
                )
            except Exception:
                factor_preparation_failed = True
        if factor_preparation_failed or factor_targets is None:
            counters["factor_rejected"] += 1
            return core.EndpointReplayDecision(False, "")
        factor_target = factor_targets[endpoint_index]
        if factor_target.get("status") != "FACTOR_READY":
            counters["factor_rejected"] += 1
            return core.EndpointReplayDecision(False, "")
        if (
            factor_target.get("product_global_root_ordinal_used") is not False
            or factor_target.get("unobserved_root_emitted") is not False
        ):
            counters["exceptions"] += 1
            raise GateFailure("factor target used product ordinal or an unobserved root")
        counters["factor_parity"] += 1
        identity = factor_target.get("descriptor_identity_sha256")
        try:
            accepted = connector.canonical_replay_endpoint(
                exact=exact,
                source_document=row["source_document"],
                endpoint=endpoint,
                target_proposal=factor_target["target_proposal"],
                timeout_seconds=per_endpoint_seconds,
            )
        except Exception:
            counters["exceptions"] += 1
            return core.EndpointReplayDecision(False, "")
        if accepted is True:
            counters["accepted"] += 1
            return core.EndpointReplayDecision(True, identity)
        counters["rejected"] += 1
        return core.EndpointReplayDecision(False, "")

    fallback = object()
    outcome = core.propose_cross_endpoint_vieta_independent(
        source_bytes=row["source_payload"],
        source_sha256=row["source_sha256"],
        endpoints=endpoints,
        replay_endpoint=replay,
        fallback_result=fallback,
    )
    degree = len(endpoints)
    proposal_constructed = outcome.structural_proposal is not None
    reconstruction, agreement, numeric = _stage_flags(
        str(outcome.reason), proposal_constructed
    )
    canonical_ready = bool(
        outcome.status == "PORTFOLIO"
        and outcome.structural_proposal is not None
        and outcome.replay_calls == degree
        and counters["calls"] == degree
        and len(outcome.accepted_endpoint_indices) > 0
        and len(outcome.accepted_endpoint_indices)
        == len(outcome.accepted_descriptor_identities)
        == counters["accepted"]
    )
    replay_bypass = int(
        outcome.status == "PORTFOLIO"
        and (
            outcome.replay_calls != degree
            or counters["accepted"] != len(outcome.accepted_endpoint_indices)
        )
    )
    fallback_preserved = outcome.fallback_result is fallback
    safety_invalid = int(
        not fallback_preserved
        or replay_bypass != 0
        or outcome.status not in {"FALLBACK", "PORTFOLIO"}
        or outcome.completeness_claimed is not False
        or counters["whole_minimal_descriptor"] != 0
        or canonical_ready and not proposal_constructed
    )
    private = {
        "schema_version": WORKER_SCHEMA,
        "input_binding_sha256": row["subset_sha256"],
        "source_sha256": row["source_sha256"],
        "structural_signature_sha256": connector.structural_signature(
            row["source_document"]
        ),
        "degree": degree,
        "status": str(outcome.status),
        "reason": str(outcome.reason),
        "bounded_rational_reconstruction_passed": reconstruction,
        "independent_rung_agreement_passed": agreement,
        "numeric_gate_passed": numeric,
        "proposal_constructed": proposal_constructed,
        "numeric_guard_branch_parity_passed": all(
            endpoint["low"].get("numeric_guard_branch_parity") is True
            and endpoint["high"].get("numeric_guard_branch_parity") is True
            for endpoint in row["endpoints"]
        ),
        "factor_level_independent_rung_parity_pass_count": counters[
            "factor_parity"
        ],
        "factor_level_rejected_endpoint_count": counters["factor_rejected"],
        "replay_calls": int(outcome.replay_calls),
        "canonical_replay_accepted_count": counters["accepted"],
        "canonical_replay_rejected_count": counters["rejected"],
        "canonical_replay_exception_count": counters["exceptions"],
        "canonical_ready": canonical_ready,
        "canonical_emitted_endpoint_count": len(outcome.accepted_endpoint_indices),
        "descriptor_identity_dedup_count": outcome.duplicate_descriptor_count,
        "fallback_identity_preserved": fallback_preserved,
        "replay_bypass_count": replay_bypass,
        "safety_invalid_count": safety_invalid,
        "whole_vieta_minimal_descriptor_count": counters[
            "whole_minimal_descriptor"
        ],
        "unobserved_root_emit_count": 0,
        "truth_used": False,
        "target_set_completeness_claim": False,
    }
    _atomic_json(output.resolve(), private)
    return 0


def _private_result(path: Path, *, expected_subset_sha: str) -> dict[str, Any] | None:
    try:
        if not path.is_file() or not 0 < path.stat().st_size <= MAX_RESULT_BYTES:
            return None
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    if (
        not isinstance(value, dict)
        or set(value) != WORKER_KEYS
        or value.get("schema_version") != WORKER_SCHEMA
        or value.get("input_binding_sha256") != expected_subset_sha
        or not _valid_sha(value.get("source_sha256"))
        or not _valid_sha(value.get("structural_signature_sha256"))
        or not isinstance(value.get("degree"), int)
        or isinstance(value.get("degree"), bool)
        or not 2 <= value["degree"] <= 6
        or value.get("status") not in {"FALLBACK", "PORTFOLIO"}
        or not isinstance(value.get("reason"), str)
        or not value["reason"]
    ):
        return None
    boolean_keys = {
        "bounded_rational_reconstruction_passed",
        "independent_rung_agreement_passed",
        "numeric_gate_passed",
        "proposal_constructed",
        "numeric_guard_branch_parity_passed",
        "canonical_ready",
        "fallback_identity_preserved",
        "truth_used",
        "target_set_completeness_claim",
    }
    count_keys = {
        "replay_calls",
        "canonical_replay_accepted_count",
        "canonical_replay_rejected_count",
        "canonical_replay_exception_count",
        "factor_level_independent_rung_parity_pass_count",
        "factor_level_rejected_endpoint_count",
        "canonical_emitted_endpoint_count",
        "descriptor_identity_dedup_count",
        "replay_bypass_count",
        "safety_invalid_count",
        "whole_vieta_minimal_descriptor_count",
        "unobserved_root_emit_count",
    }
    if (
        any(not isinstance(value[key], bool) for key in boolean_keys)
        or any(
            not isinstance(value[key], int)
            or isinstance(value[key], bool)
            or value[key] < 0
            for key in count_keys
        )
        or value["truth_used"] is not False
        or value["target_set_completeness_claim"] is not False
        or value["proposal_constructed"] != value["numeric_gate_passed"]
        or value["numeric_guard_branch_parity_passed"] is not True
        or value["canonical_ready"] != (value["status"] == "PORTFOLIO")
        or value["whole_vieta_minimal_descriptor_count"] != 0
        or value["unobserved_root_emit_count"] != 0
        or value["factor_level_independent_rung_parity_pass_count"] > value["degree"]
        or value["factor_level_rejected_endpoint_count"] > value["degree"]
        or value["canonical_emitted_endpoint_count"]
        > value["factor_level_independent_rung_parity_pass_count"]
        or value["descriptor_identity_dedup_count"] > value["degree"]
        or value["canonical_ready"]
        and (
            value["replay_calls"] != value["degree"]
            or value["canonical_replay_accepted_count"]
            != value["canonical_emitted_endpoint_count"]
            or value["canonical_emitted_endpoint_count"] <= 0
        )
    ):
        return None
    return value


def _guarded_worker(
    *,
    guard: Any,
    work_item: Path,
    output: Path,
    runner_sha256: str,
    degree: int,
    per_endpoint_seconds: float,
):
    output.unlink(missing_ok=True)
    command = [
        str(PYTHON),
        str(RUNNER),
        "worker",
        "--work-item",
        str(work_item.resolve()),
        "--output",
        str(output.resolve()),
        "--runner-sha256",
        runner_sha256,
        "--per-endpoint-seconds",
        str(per_endpoint_seconds),
    ]
    environment = os.environ.copy()
    environment.update(THREAD_ENVIRONMENT)
    timeout_seconds = degree * per_endpoint_seconds + 5.0
    return guard.run_guarded(
        command,
        limits=guard.Limits(
            timeout_seconds=timeout_seconds,
            rss_bytes=1024 * 1024**2,
            address_space_bytes=4096 * 1024**2,
            data_bytes=3072 * 1024**2,
            output_bytes=256 * 1024,
            tail_bytes=16 * 1024,
        ),
        environment=environment,
        cwd=HERE,
    )


def _aggregate_private_rows(
    *,
    rows: Sequence[Mapping[str, Any]],
    request_count: int,
    source_count: int,
    process_failure_count: int,
    manifest_sha256: str,
    runner_sha256: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    degrees: Counter[int] = Counter()
    statuses: Counter[str] = Counter()
    reasons: Counter[str] = Counter()
    proposal_sources: set[str] = set()
    factor_parity_sources: set[str] = set()
    factor_parity_signatures: set[str] = set()
    ready_sources: set[str] = set()
    ready_signatures: set[str] = set()
    totals: Counter[str] = Counter()
    for row in rows:
        degrees[int(row["degree"])] += 1
        statuses[str(row["status"])] += 1
        reasons[str(row["reason"])] += 1
        for field in (
            "bounded_rational_reconstruction_passed",
            "independent_rung_agreement_passed",
            "numeric_gate_passed",
            "proposal_constructed",
            "numeric_guard_branch_parity_passed",
            "canonical_ready",
            "fallback_identity_preserved",
        ):
            totals[field] += int(row[field] is True)
        for field in (
            "replay_calls",
            "canonical_replay_accepted_count",
            "canonical_replay_rejected_count",
            "canonical_replay_exception_count",
            "factor_level_independent_rung_parity_pass_count",
            "factor_level_rejected_endpoint_count",
            "canonical_emitted_endpoint_count",
            "descriptor_identity_dedup_count",
            "replay_bypass_count",
            "safety_invalid_count",
            "whole_vieta_minimal_descriptor_count",
            "unobserved_root_emit_count",
        ):
            totals[field] += int(row[field])
        if row["proposal_constructed"] is True:
            proposal_sources.add(str(row["source_sha256"]))
        if row["factor_level_independent_rung_parity_pass_count"] > 0:
            factor_parity_sources.add(str(row["source_sha256"]))
            factor_parity_signatures.add(str(row["structural_signature_sha256"]))
        if row["canonical_ready"] is True:
            ready_sources.add(str(row["source_sha256"]))
            ready_signatures.add(str(row["structural_signature_sha256"]))

    all_workers_accepted = len(rows) == request_count and process_failure_count == 0
    safety_invalid_count = (
        totals["safety_invalid_count"]
        + totals["replay_bypass_count"]
        + totals["whole_vieta_minimal_descriptor_count"]
        + totals["unobserved_root_emit_count"]
    )
    go = bool(
        all_workers_accepted
        and safety_invalid_count == 0
        and totals["numeric_guard_branch_parity_passed"] == len(rows)
        and len(factor_parity_sources) >= 3
        and len(factor_parity_signatures) >= 2
        and len(ready_sources) >= 3
        and len(ready_signatures) >= 2
    )
    aggregate = {
        "schema_version": AGGREGATE_SCHEMA,
        "status": "GO_CANONICAL_GATE" if go else "STOP_CANONICAL_GATE_INCOMPLETE",
        "request_subset_count": request_count,
        "structural_proposal_preregistered_upper_bound": 595,
        "anonymous_source_group_count": source_count,
        "accepted_worker_result_count": len(rows),
        "guarded_process_failure_count": process_failure_count,
        "attempts_by_degree": {str(key): degrees[key] for key in sorted(degrees)},
        "status_counts": dict(sorted(statuses.items())),
        "reason_counts": dict(sorted(reasons.items())),
        "bounded_rational_reconstruction_pass_count": totals[
            "bounded_rational_reconstruction_passed"
        ],
        "independent_rung_agreement_pass_count": totals[
            "independent_rung_agreement_passed"
        ],
        "numeric_gate_pass_count": totals["numeric_gate_passed"],
        "structural_proposal_count": totals["proposal_constructed"],
        "structural_proposal_source_group_count": len(proposal_sources),
        "numeric_guard_branch_parity_subset_count": totals[
            "numeric_guard_branch_parity_passed"
        ],
        "factor_level_independent_rung_parity_endpoint_count": totals[
            "factor_level_independent_rung_parity_pass_count"
        ],
        "factor_level_rejected_endpoint_count": totals[
            "factor_level_rejected_endpoint_count"
        ],
        "factor_parity_activated_source_group_count": len(factor_parity_sources),
        "factor_parity_activated_structural_signature_count": len(
            factor_parity_signatures
        ),
        "canonical_full_tuple_replay_call_count": totals["replay_calls"],
        "canonical_replay_accepted_endpoint_count": totals[
            "canonical_replay_accepted_count"
        ],
        "canonical_replay_rejected_endpoint_count": totals[
            "canonical_replay_rejected_count"
        ],
        "canonical_replay_exception_count": totals[
            "canonical_replay_exception_count"
        ],
        "canonical_ready_subset_count": totals["canonical_ready"],
        "canonical_emitted_endpoint_count": totals[
            "canonical_emitted_endpoint_count"
        ],
        "descriptor_identity_dedup_count": totals[
            "descriptor_identity_dedup_count"
        ],
        "canonical_ready_source_group_count": len(ready_sources),
        "canonical_ready_structural_signature_count": len(ready_signatures),
        "fallback_identity_preserved_count": totals["fallback_identity_preserved"],
        "replay_bypass_count": totals["replay_bypass_count"],
        "safety_invalid_count": safety_invalid_count,
        "whole_vieta_minimal_descriptor_count": totals[
            "whole_vieta_minimal_descriptor_count"
        ],
        "unobserved_root_emit_count": totals["unobserved_root_emit_count"],
        "all_workers_accepted": all_workers_accepted,
        "minimum_gate_ready_sources": 3,
        "minimum_gate_ready_structural_signatures": 2,
        "manifest_sha256": manifest_sha256,
        "runner_sha256": runner_sha256,
        "connector_sha256": CONNECTOR_SHA256,
        "existing_canonical_full_tuple_source_guard_raw_target_replay_used": True,
        "frozen_numeric_guard_branch_parity_is_separate_required_conjunct": True,
        "original_result_plan_lane_bytes_reauthenticated": True,
        "source_projection_bound_to_original_replay_closure": True,
        "whole_vieta_polynomial_is_structural_only": True,
        "factor_local_real_root_ordinal_only": True,
        "independent_endpoint_repair_a": True,
        "baseline_union_unchanged": True,
        "source_eliminant_used": False,
        "known_root_or_exclude_primitive_used": False,
        "truth_used": False,
        "canonical_scorer_executed": False,
        "formal_score_claim": False,
        "target_set_completeness_claim": False,
        "case_ids_retained": False,
        "targets_coefficients_endpoints_retained": False,
        "per_subset_output_emitted": False,
        "proposal_source_sha_sidecar_emitted": True,
        "proposal_source_sha_sidecar_contains_control_outcomes": False,
        "cpu": 14,
        "global_lock_held": True,
    }
    aggregate["aggregate_sha256"] = _sha256(
        json.dumps(aggregate, sort_keys=True, separators=(",", ":")).encode()
    )
    sidecar = {
        "schema_version": PROPOSAL_SOURCE_SCHEMA,
        "manifest_sha256": manifest_sha256,
        "runner_sha256": runner_sha256,
        "proposal_source_count": len(proposal_sources),
        "proposal_source_sha256": sorted(proposal_sources),
        "selection_predicate": "BOUNDED_STRUCTURAL_VIETA_PROPOSAL_CONSTRUCTED",
        "control_outcome_joined": False,
        "canonical_replay_outcome_included": False,
        "truth_used": False,
    }
    sidecar["aggregate_sha256"] = _sha256(
        json.dumps(sidecar, sort_keys=True, separators=(",", ":")).encode()
    )
    return aggregate, sidecar


def _coordinator(arguments: argparse.Namespace) -> int:
    _check_cpu14()
    _check_self(arguments.runner_sha256)
    if arguments.global_lock.resolve() != OFFICIAL_GLOBAL_LOCK:
        raise GateFailure("the official machine-wide benchmark lock is required")
    if (
        not math.isfinite(arguments.per_endpoint_seconds)
        or not MIN_PER_ENDPOINT_SECONDS
        <= arguments.per_endpoint_seconds
        <= MAX_PER_ENDPOINT_SECONDS
    ):
        raise GateFailure("per-endpoint timeout is outside the frozen range")
    output = _within_results(arguments.output, must_exist=False)
    proposal_output = _within_results(
        arguments.proposal_source_sha_output, must_exist=False
    )
    requests = _within_results(arguments.requests, must_exist=True)
    if len({output, proposal_output, requests}) != 3:
        raise GateFailure("request, aggregate, and root-custody sidecar paths must differ")

    connector = _load_connector()
    guard = _load_guard()
    manifest_payload, requests_rows = _manifest(requests, connector)
    source_count = len({str(row["source_sha256"]) for row in requests_rows})
    private_rows: list[dict[str, Any]] = []
    process_failure_count = 0
    with arguments.global_lock.open("a+b") as lock, tempfile.TemporaryDirectory(
        prefix="cross-endpoint-vieta-exact-gate-"
    ) as temporary_name:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        temporary_root = Path(temporary_name)
        for ordinal, row in enumerate(requests_rows):
            work_item = temporary_root / f"subset-{ordinal}.json"
            private_output = temporary_root / f"result-{ordinal}.json"
            private_request = {
                "schema_version": WORK_ITEM_SCHEMA,
                "source": str(row["source"]),
                "source_sha256": row["source_sha256"],
                "subset_sha256": row["subset_sha256"],
                "endpoints": [
                    {
                        "endpoint_float64_bits_hex": list(
                            endpoint["endpoint_float64_bits_hex"]
                        ),
                        "endpoint_float64_sha256": endpoint[
                            "endpoint_float64_sha256"
                        ],
                        "low": _serializable_rung(endpoint["low"]),
                        "high": _serializable_rung(endpoint["high"]),
                    }
                    for endpoint in row["endpoints"]
                ],
            }
            _atomic_json(work_item, private_request)
            guarded = _guarded_worker(
                guard=guard,
                work_item=work_item,
                output=private_output,
                runner_sha256=arguments.runner_sha256,
                degree=len(row["endpoints"]),
                per_endpoint_seconds=arguments.per_endpoint_seconds,
            )
            result = _private_result(
                private_output, expected_subset_sha=row["subset_sha256"]
            )
            process_ok = bool(
                guarded.accepted_output is True
                and guarded.classification == "SUCCESS"
                and guarded.timeout is False
                and guarded.rss_cap_exceeded is False
                and guarded.rss_monitor_failed is False
                and guarded.output_cap_exceeded is False
                and guarded.descendant_leak is False
                and result is not None
                and result["source_sha256"] == row["source_sha256"]
                and result["degree"] == len(row["endpoints"])
            )
            if process_ok:
                private_rows.append(result)
            else:
                process_failure_count += 1
        fcntl.flock(lock.fileno(), fcntl.LOCK_UN)

    aggregate, sidecar = _aggregate_private_rows(
        rows=private_rows,
        request_count=len(requests_rows),
        source_count=source_count,
        process_failure_count=process_failure_count,
        manifest_sha256=_sha256(manifest_payload),
        runner_sha256=arguments.runner_sha256,
    )
    _atomic_json(proposal_output, sidecar, mode=0o600)
    _atomic_json(output, aggregate, mode=0o600)
    print(json.dumps(aggregate, sort_keys=True))
    return 0 if aggregate["status"] == "GO_CANONICAL_GATE" else 2


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    worker = subparsers.add_parser("worker")
    worker.add_argument("--work-item", required=True, type=Path)
    worker.add_argument("--output", required=True, type=Path)
    worker.add_argument("--runner-sha256", required=True)
    worker.add_argument("--per-endpoint-seconds", required=True, type=float)
    coordinator = subparsers.add_parser("coordinator")
    coordinator.add_argument("--requests", required=True, type=Path)
    coordinator.add_argument("--output", required=True, type=Path)
    coordinator.add_argument("--proposal-source-sha-output", required=True, type=Path)
    coordinator.add_argument("--global-lock", required=True, type=Path)
    coordinator.add_argument("--runner-sha256", required=True)
    coordinator.add_argument("--per-endpoint-seconds", type=float, default=18.0)
    arguments = parser.parse_args()
    _check_self(arguments.runner_sha256)
    if arguments.command == "worker":
        if (
            not math.isfinite(arguments.per_endpoint_seconds)
            or not MIN_PER_ENDPOINT_SECONDS
            <= arguments.per_endpoint_seconds
            <= MAX_PER_ENDPOINT_SECONDS
        ):
            raise GateFailure("per-endpoint timeout is outside the frozen range")
        return _worker(
            arguments.work_item, arguments.output, arguments.per_endpoint_seconds
        )
    return _coordinator(arguments)


if __name__ == "__main__":
    raise SystemExit(main())
