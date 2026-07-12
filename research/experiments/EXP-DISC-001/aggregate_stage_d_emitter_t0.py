#!/usr/bin/env python3
"""Independent, stdlib-only aggregation for the Stage-D point-emitter T0."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import struct
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable, Sequence

sys.path.insert(0, str(Path(__file__).resolve().parent))
import aggregate_t0 as common  # noqa: E402

EXPERIMENT = "EXP-DISC-001"
CASE_COUNT = 12
STARTS = PRESCREENS = 64
EMITTER_SLOTS = 48
LOCAL_CAP = 600
THRESHOLDS = (600, 1_200, 2_400, 4_800)
ARMS = (
    "D0_PRESCORED_64",
    "RECT_ORBIT_BREADTH",
    "DIRECT_RECT_EMIT",
    "SIMPLICIAL_UNGUIDED",
    "SIMPLICIAL_STAR_EMIT",
    "ECP_LB_FULL",
)
CANDIDATE_CONTROLS = {
    "DIRECT_RECT_EMIT": ("RECT_ORBIT_BREADTH", "D0_PRESCORED_64"),
    "SIMPLICIAL_STAR_EMIT": ("SIMPLICIAL_UNGUIDED", "D0_PRESCORED_64"),
    "ECP_LB_FULL": ("D0_PRESCORED_64",),
}
SPECIAL = frozenset(("TANGENT-CIRCLE-LINE", "MULTIROOT-WARPED"))
PREREG_SCHEMA = "geotarget.discovery-stage-d-emitter-t0-preregistration/v1"
RAW_SCHEMA = "geotarget.discovery-stage-d-emitter-t0-raw/v1"
OUTPUT_SCHEMA = "geotarget.discovery-stage-d-emitter-t0-aggregate/v1"


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, allow_nan=False, sort_keys=True,
                      separators=(",", ":"))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _sha(value: Any) -> bool:
    return isinstance(value, str) and len(value) == 64 and not set(value) - set("0123456789abcdef")


def _bits(value: Any) -> str:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError("expected a finite Float64 value")
    return struct.pack(">d", float(value)).hex()


def _observed(attempt: dict[str, Any]) -> int:
    value = attempt.get("observed_evaluations", attempt.get("evaluations"))
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError("invalid observed callback count")
    return value


def _reported(attempt: dict[str, Any]) -> int:
    value = attempt.get("reported_evaluations", attempt.get("evaluations"))
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError("invalid reported callback count")
    return value


def _matrix(document: Any, dimension: int) -> list[list[str]]:
    if not isinstance(document, dict) or set(document) != {
        "column_count", "coordinate_float64_bits_by_column", "dimension", "matrix_sha256"
    }:
        raise ValueError("matrix document keys differ")
    if document["dimension"] != dimension or document["column_count"] != STARTS:
        raise ValueError("matrix shape differs")
    columns = document["coordinate_float64_bits_by_column"]
    if not isinstance(columns, list) or len(columns) != STARTS:
        raise ValueError("matrix column count differs")
    for column in columns:
        if not isinstance(column, list) or len(column) != dimension or any(not _sha_bit(x) for x in column):
            raise ValueError("matrix coordinate bits differ")
    payload = {"column_count": STARTS, "coordinate_float64_bits_by_column": columns,
               "dimension": dimension}
    wanted = hashlib.sha256(canonical_json(payload).encode()).hexdigest()
    if document["matrix_sha256"] != wanted:
        raise ValueError("matrix digest differs")
    return columns


def _sha_bit(value: Any) -> bool:
    return isinstance(value, str) and len(value) == 16 and not set(value) - set("0123456789abcdef")


def _truth_free(value: Any) -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            lowered = str(key).lower()
            if "branch_token" in lowered or "known_root" in lowered:
                raise ValueError(f"source document leaks {key}")
            if any(word in lowered for word in ("family", "instance", "gold", "target")):
                if not lowered.endswith("_authority") or child is not False:
                    raise ValueError(f"source document leaks {key}")
            _truth_free(child)
    elif isinstance(value, list):
        for child in value:
            _truth_free(child)


def _validate_prereg(document: dict[str, Any]) -> None:
    if document.get("schema_version") != PREREG_SCHEMA or document.get("experiment_id") != EXPERIMENT:
        raise ValueError("unexpected Stage-D preregistration")
    if document.get("status") != "preregistered" or document.get("outcome_execution_authorized") is not True:
        raise ValueError("Stage-D outcomes are not authorized")
    if document.get("nonpromotional_t0") is not True or document.get("case_count") != CASE_COUNT:
        raise ValueError("Stage-D scope differs")
    if tuple(document.get("arms", ())) != ARMS or tuple(document.get("callback_thresholds", ())) != THRESHOLDS:
        raise ValueError("Stage-D arms/checkpoints differ")
    if document.get("local_start_count") != STARTS or document.get(
        "logical_prescreen_callbacks_per_arm"
    ) != PRESCREENS:
        raise ValueError("Stage-D fixed work differs")
    if not isinstance(document.get("source_sha256"), dict) or not isinstance(
        document.get("executable_sha256"), dict
    ):
        raise ValueError("Stage-D source bindings are absent")
    cases = document.get("case_manifests")
    if not isinstance(cases, list) or len(cases) != CASE_COUNT:
        raise ValueError("Stage-D fixed case manifests are absent")
    wanted_indices = list(range(1, CASE_COUNT + 1))
    if [case.get("case_index") for case in cases] != wanted_indices:
        raise ValueError("Stage-D fixed case order differs")
    source_indices = document.get("case_selection", {}).get("indices")
    if not isinstance(source_indices, list) or len(source_indices) != CASE_COUNT or [
        case.get("source_index") for case in cases
    ] != source_indices:
        raise ValueError("Stage-D source-index binding differs")
    sources = document.get("case_sources")
    if not isinstance(sources, list) or len(sources) != CASE_COUNT:
        raise ValueError("Stage-D case-source binding is absent")
    for case, source in zip(cases, sources, strict=True):
        if source.get("index") != case.get("source_index"):
            raise ValueError("Stage-D case-source index differs")
        for field in ("dimension", "target_count", "configuration_count"):
            if isinstance(case.get(field), bool) or not isinstance(case.get(field), int) or case[field] < 1:
                raise ValueError(f"Stage-D fixed case {field} differs")
        for field in ("family_id", "instance_id"):
            if not isinstance(case.get(field), str) or not case[field]:
                raise ValueError(f"Stage-D fixed case {field} differs")
        if not _sha(case.get("replay_checksum")):
            raise ValueError("Stage-D fixed replay checksum differs")
    selection = document.get("case_selection", {})
    if sum(int(case["target_count"]) for case in cases) != selection.get("target_count") or sum(
        int(case["configuration_count"]) for case in cases
    ) != selection.get("configuration_count"):
        raise ValueError("Stage-D fixed case denominator totals differ")
    if Counter(str(case["family_id"]) for case in cases) != Counter(selection.get("families", {})):
        raise ValueError("Stage-D fixed family balance differs")


def _generation_common(name: str, generation: Any) -> dict[str, Any]:
    if not isinstance(generation, dict):
        raise ValueError(f"{name} generation is absent")
    _truth_free(generation)
    if generation.get("logical_prescreen_callbacks") != PRESCREENS:
        raise ValueError(f"{name} logical prescreen count differs")
    if generation.get("all_prescores_returned") is not True or generation.get(
        "answer_authority"
    ) is not False:
        raise ValueError(f"{name} prescreen authority differs")
    return generation


def _module(generation: dict[str, Any]) -> dict[str, Any]:
    value = generation.get("module_diagnostics")
    if not isinstance(value, dict):
        raise ValueError("module diagnostics are absent")
    return value


def _validate_generation(arms: dict[str, dict[str, Any]]) -> int:
    for name, arm in arms.items():
        _generation_common(name, arm["generation"])

    def typed_fallback_slots(name: str, kind: str) -> list[int]:
        result: list[int] = []
        for source in arms[name].get("schedule", []):
            if source.get("kind") != kind:
                continue
            slot = source.get("emitter_slot")
            if not isinstance(slot, int) or source.get("slot") != slot:
                raise ValueError(f"{name} typed fallback slot binding differs")
            result.append(slot)
        if result != sorted(set(result)):
            raise ValueError(f"{name} typed fallback slots are duplicated or unordered")
        return result
    for name in ("D0_PRESCORED_64", "RECT_ORBIT_BREADTH", "DIRECT_RECT_EMIT"):
        if arms[name]["generation"].get("physical_prescreen_callbacks") != PRESCREENS:
            raise ValueError(f"{name} physical prescreen count differs")
    for name in ("RECT_ORBIT_BREADTH", "DIRECT_RECT_EMIT"):
        generation = arms[name]["generation"]
        module = _module(generation)
        module_count = int(generation.get("module_proposal_count", -1))
        fallback_count = int(generation.get("fallback_prescreen_callbacks", -1))
        if module.get("screening_callbacks") != module_count or module_count + fallback_count != EMITTER_SLOTS or module.get(
            "all_requests_serviced"
        ) is not True or module.get("hard_discard_count") != 0:
            raise ValueError(f"{name} module accounting differs")
        status = module.get("status")
        if (status == "EMITTER_COMPLETE" and (module_count != EMITTER_SLOTS or fallback_count != 0)) or (
            status != "EMITTER_COMPLETE" and (module_count != 0 or fallback_count != EMITTER_SLOTS)
        ):
            raise ValueError(f"{name} complete/inapplicable closure differs")
        if bool(generation.get("applicable")) != (module.get("status") == "EMITTER_COMPLETE"):
            raise ValueError(f"{name} applicability differs")
        if module.get("arm") != name or module.get("external_result_used") is not False:
            raise ValueError(f"{name} module authority/wire identity differs")
        fallback_slots = typed_fallback_slots(name, "DIRECT_TYPED_IID_FALLBACK")
        if fallback_slots != list(range(module_count + 1, EMITTER_SLOTS + 1)):
            raise ValueError(f"{name} typed fallback set differs")
    if arms["RECT_ORBIT_BREADTH"]["generation"].get("applicable") != arms[
        "DIRECT_RECT_EMIT"
    ]["generation"].get("applicable"):
        raise ValueError("DIRECT candidate/control applicability differs on the same public box")
    simplicial = [arms[name]["generation"] for name in (
        "SIMPLICIAL_UNGUIDED", "SIMPLICIAL_STAR_EMIT"
    )]
    reports = [_module(value) for value in simplicial]
    if reports[0].get("arm") != "SIMPLICIAL_UNGUIDED" or reports[1].get(
        "arm"
    ) != "SIMPLICIAL_STAR_EMIT":
        raise ValueError("simplicial wire identity differs")
    if simplicial[0].get("paired_physical_module_callbacks") != simplicial[1].get(
        "paired_physical_module_callbacks"
    ):
        raise ValueError("simplicial shared physical count differs")
    for field in (
        "applicable", "reason", "dimension", "base_vertex_count", "simplex_count",
        "combinatorial_minimum_count", "logical_screening_callbacks", "shared_base_evaluation",
    ):
        if reports[0].get(field) != reports[1].get(field):
            raise ValueError(f"simplicial paired {field} differs")
    base = int(reports[0].get("base_vertex_count", -1))
    physical_module = int(simplicial[0]["paired_physical_module_callbacks"])
    wanted_module = base + sum(int(report.get("refinement_count", -1)) for report in reports)
    if physical_module != wanted_module:
        raise ValueError("simplicial base/refinement physical ledger differs")
    for generation, report in zip(simplicial, reports, strict=True):
        if int(report.get("logical_screening_callbacks", -1)) != EMITTER_SLOTS:
            raise ValueError("simplicial logical module count differs")
        if int(report.get("logical_prescores", -1)) + int(report.get("fallback_requests", -1)) != EMITTER_SLOTS:
            raise ValueError("simplicial proposal/fallback count differs")
        if generation.get("physical_fallback_callbacks") != report.get("fallback_requests"):
            raise ValueError("simplicial fallback physical count differs")
        if generation.get("physical_insurance_callbacks") != 16:
            raise ValueError("simplicial insurance physical count differs")
        if report.get("all_prescores_returned") is not True or report.get(
            "answer_authority"
        ) is not False or report.get("homology_authority") is not False or report.get(
            "completeness_authority"
        ) is not False:
            raise ValueError("simplicial module authority differs")
    for name, report in zip(("SIMPLICIAL_UNGUIDED", "SIMPLICIAL_STAR_EMIT"), reports, strict=True):
        fallback_slots = typed_fallback_slots(name, "SIMPLICIAL_TYPED_IID_FALLBACK")
        first = int(report.get("logical_prescores", -1)) + 1
        if fallback_slots != list(range(first, EMITTER_SLOTS + 1)):
            raise ValueError(f"{name} typed fallback set differs")
    ecp_generation = arms["ECP_LB_FULL"]["generation"]
    ecp = _module(ecp_generation)
    if ecp.get("arm") != "ECP_LB_FULL" or ecp.get("accepted_screen_cap") != EMITTER_SLOTS:
        raise ValueError("ECP fixed arm differs")
    if ecp.get("accepted_screening_callbacks") + ecp.get("fallback_requests") != EMITTER_SLOTS:
        raise ValueError("ECP accepted/fallback count differs")
    raw_draws = ecp.get("raw_draws_consumed")
    accepted = ecp.get("accepted_screening_callbacks")
    rejected = ecp.get("rejected_unscored_draws")
    if any(isinstance(value, bool) or not isinstance(value, int) for value in (
        raw_draws, accepted, rejected
    )) or not 0 <= raw_draws <= 65_536 or not 1 <= accepted <= EMITTER_SLOTS or rejected != raw_draws - accepted:
        raise ValueError("ECP raw/rejection ledger differs")
    if ecp.get("raw_draw_cap") != 65_536 or ecp.get(
        "logical_screening_callbacks"
    ) != EMITTER_SLOTS or ecp.get("screened_evidence_discard_count") != 0 or ecp.get(
        "all_evaluated_proposals_retained"
    ) is not True:
        raise ValueError("ECP raw/service contract differs")
    if any(ecp.get(field) is not False for field in (
        "answer_authority", "target_authority", "gold_authority",
        "completeness_authority", "external_result_used",
    )):
        raise ValueError("ECP module authority differs")
    if ecp_generation.get("physical_module_callbacks") != ecp.get("accepted_screening_callbacks") or ecp_generation.get(
        "physical_fallback_callbacks"
    ) != ecp.get("fallback_requests") or ecp_generation.get("physical_insurance_callbacks") != 16:
        raise ValueError("ECP physical ledger differs")
    ecp_fallback_slots = typed_fallback_slots("ECP_LB_FULL", "ECP_TYPED_IID_FALLBACK")
    if ecp_fallback_slots != list(range(int(ecp.get("accepted_screening_callbacks", -1)) + 1,
                                        EMITTER_SLOTS + 1)):
        raise ValueError("ECP typed fallback set differs")
    return (
        sum(int(arms[name]["generation"]["physical_prescreen_callbacks"]) for name in (
            "D0_PRESCORED_64", "RECT_ORBIT_BREADTH", "DIRECT_RECT_EMIT"
        ))
        + physical_module
        + sum(int(value["physical_fallback_callbacks"]) for value in simplicial)
        + 32
        + int(ecp_generation["physical_module_callbacks"])
        + int(ecp_generation["physical_fallback_callbacks"])
        + int(ecp_generation["physical_insurance_callbacks"])
    )


def _validate_arm(arm: Any, name: str, case: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(arm, dict) or arm.get("name") != name:
        raise ValueError(f"{name} raw arm is malformed")
    if arm.get("all_locally_serviced") is not True:
        raise ValueError(f"{name} was not fully locally serviced")
    matrix = _matrix(arm.get("matrix"), int(case["dimension"]))
    schedule, attempts = arm.get("schedule"), arm.get("attempts")
    if not isinstance(schedule, list) or not isinstance(attempts, list) or len(schedule) != STARTS or len(
        attempts
    ) != STARTS:
        raise ValueError(f"{name} service count differs")
    if [row.get("position") for row in schedule] != list(range(1, STARTS + 1)):
        raise ValueError(f"{name} schedule positions differ")
    for position, (source, attempt) in enumerate(zip(schedule, attempts, strict=True), 1):
        expected_lane = "IID_INSURANCE" if position % 4 == 1 else "EMITTER"
        if source.get("lane") != expected_lane or attempt.get("discovery_lane") != expected_lane:
            raise ValueError(f"{name} IID bounded-gap schedule differs")
        if expected_lane == "IID_INSURANCE":
            wanted_insurance = (position + 3) // 4
            if source.get("insurance_slot") != wanted_insurance or source.get("emitter_slot") is not None:
                raise ValueError(f"{name} insurance slot differs")
        else:
            wanted_emitter = position - (position + 2) // 4
            if source.get("emitter_slot") != wanted_emitter or source.get("insurance_slot") is not None:
                raise ValueError(f"{name} emitter slot differs")
        if attempt.get("discovery_position") != position:
            raise ValueError(f"{name} local position differs")
        if attempt.get("emitter_slot") != source.get("emitter_slot") or attempt.get(
            "insurance_slot"
        ) != source.get("insurance_slot"):
            raise ValueError(f"{name} local/source slot binding differs")
        start = attempt.get("start")
        if not isinstance(start, list) or [_bits(value) for value in start] != matrix[position - 1]:
            raise ValueError(f"{name} local start differs from source matrix")
        if _observed(attempt) > LOCAL_CAP or _reported(attempt) > LOCAL_CAP:
            raise ValueError(f"{name} local callback cap violated")
    terminal = arm.get("terminal")
    if not isinstance(terminal, dict) or terminal.get("attempt_count") != STARTS:
        raise ValueError(f"{name} terminal count differs")
    if terminal.get("callback_work") != sum(_observed(attempt) for attempt in attempts):
        raise ValueError(f"{name} terminal callback work differs")
    if terminal.get("callback_cap_violations") != sum(
        _observed(attempt) > LOCAL_CAP or _reported(attempt) > LOCAL_CAP for attempt in attempts
    ):
        raise ValueError(f"{name} terminal cap ledger differs")
    if terminal.get("evaluation_count_mismatches") != sum(
        _observed(attempt) != _reported(attempt) or bool(attempt.get("evaluation_count_mismatch"))
        for attempt in attempts
    ):
        raise ValueError(f"{name} terminal mismatch ledger differs")
    if terminal.get("exceptions") != sum(attempt.get("exception") is not None for attempt in attempts):
        raise ValueError(f"{name} terminal exception ledger differs")
    if terminal.get("runner_budget_exhausted") != sum(
        bool(attempt.get("budget_exhausted")) for attempt in attempts
    ):
        raise ValueError(f"{name} terminal runner-budget ledger differs")
    return {"document": arm, "matrix": matrix, "schedule": schedule, "attempts": attempts}


def _validate_cross_arm(arms: dict[str, dict[str, Any]]) -> None:
    reference = arms[ARMS[0]]
    for block in range(16):
        position = 4 * block
        bits = reference["matrix"][position]
        if any(arms[name]["matrix"][position] != bits for name in ARMS[1:]):
            raise ValueError("permanent IID insurance differs between arms")
    fallbacks: defaultdict[int, list[list[str]]] = defaultdict(list)
    for name, arm in arms.items():
        for position, source in enumerate(arm["schedule"]):
            kind = str(source.get("kind", ""))
            if "TYPED_IID_FALLBACK" in kind:
                slot = source.get("emitter_slot")
                if not isinstance(slot, int):
                    raise ValueError("typed fallback lacks its emitter slot")
                fallbacks[slot].append(arm["matrix"][position])
    for matrices in fallbacks.values():
        if len({canonical_json(value) for value in matrices}) != 1:
            raise ValueError("fresh IID fallback differs for the same slot")
    d0_by_slot = {
        int(source["emitter_slot"]): reference["matrix"][position]
        for position, source in enumerate(reference["schedule"])
        if source.get("lane") == "EMITTER"
    }
    ecp_indices = [
        source["raw_draw_index"] for source in arms["ECP_LB_FULL"]["schedule"]
        if isinstance(source.get("raw_draw_index"), int)
    ]
    ecp_module = _module(arms["ECP_LB_FULL"]["document"]["generation"])
    if ecp_indices != sorted(set(ecp_indices)) or len(ecp_indices) != ecp_module.get(
        "accepted_screening_callbacks"
    ) or not ecp_indices or ecp_indices[0] != 1 or any(
        not 1 <= index <= ecp_module.get("raw_draws_consumed", 0) for index in ecp_indices
    ):
        raise ValueError("ECP accepted raw-index ledger differs")
    for position, source in enumerate(arms["ECP_LB_FULL"]["schedule"]):
        raw_index = source.get("raw_draw_index")
        if isinstance(raw_index, int) and raw_index <= EMITTER_SLOTS:
            if arms["ECP_LB_FULL"]["matrix"][position] != d0_by_slot[raw_index]:
                raise ValueError("ECP and D0 do not share their raw prefix")


def _prefix(attempts: Sequence[dict[str, Any]], threshold: int) -> tuple[list[dict[str, Any]], int]:
    work = PRESCREENS
    selected: list[dict[str, Any]] = []
    for attempt in attempts:
        candidate = work + _observed(attempt)
        if candidate > threshold:
            break
        selected.append(attempt)
        work = candidate
    return selected, work


def _reported_safety(attempts: Iterable[dict[str, Any]]) -> int:
    return sum(
        bool(row.get("reported_accepted")) and (
            not bool(row.get("canonical_valid"))
            or not bool(row.get("gold_matched"))
            or bool(row.get("target_ambiguous"))
            or (bool(row.get("numeric_target_matched")) and not bool(row.get("gold_matched")))
        )
        for row in attempts
    )


def aggregate(prereg: dict[str, Any], shards: Sequence[dict[str, Any]], prereg_sha: str) -> dict[str, Any]:
    _validate_prereg(prereg)
    if len(shards) != CASE_COUNT or sorted(int(row.get("case_index", 0)) for row in shards) != list(
        range(1, CASE_COUNT + 1)
    ):
        raise ValueError("Stage-D shards are missing or duplicated")
    revisions: set[str] = set()
    rows: list[dict[str, Any]] = []
    terminal_rows: list[dict[str, Any]] = []
    terminals: dict[tuple[int, str], dict[str, Any]] = {}
    applicability: dict[tuple[int, str], bool] = {}
    families: dict[int, str] = {}
    accounting = Counter()
    for shard in sorted(shards, key=lambda row: int(row["case_index"])):
        index = int(shard["case_index"])
        if shard.get("schema_version") != RAW_SCHEMA or shard.get("experiment_id") != EXPERIMENT:
            raise ValueError(f"raw shard {index} schema differs")
        if shard.get("stage") != "stage-d-emitter-t0" or shard.get("nonpromotional_t0") is not True:
            raise ValueError(f"raw shard {index} scope differs")
        if tuple(shard.get("arm_order", ())) != ARMS or shard.get("lab_confirmation_512_768") is not False:
            raise ValueError(f"raw shard {index} arm/lab boundary differs")
        if shard.get("preregistration", {}).get("sha256") != prereg_sha:
            raise ValueError(f"raw shard {index} preregistration differs")
        if shard.get("source_generation_completed_before_local") is not True:
            raise ValueError(f"raw shard {index} source/local phase order differs")
        revision = shard.get("revision", {})
        if revision.get("git_dirty") is not False or not isinstance(revision.get("git_head"), str):
            raise ValueError(f"raw shard {index} revision differs")
        revisions.add(revision["git_head"])
        thread = shard.get("thread_contract", {})
        if any(thread.get(key) != 1 for key in ("julia_threads", "blas_threads", "solver_worker_count")):
            raise ValueError(f"raw shard {index} thread contract differs")
        environment = thread.get("environment", {})
        if any(environment.get(name) != "1" for name in (
            "JULIA_NUM_THREADS", "OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"
        )):
            raise ValueError(f"raw shard {index} thread environment differs")
        if thread.get("assigned_cpu") != index - 1 or thread.get("case_process_limit") != 12:
            raise ValueError(f"raw shard {index} CPU contract differs")
        if thread.get("cpus_allowed_list") != str(index - 1):
            raise ValueError(f"raw shard {index} CPU affinity record differs")
        case = shard.get("case_manifest", {})
        fixed = prereg["case_manifests"][index - 1]
        expected_case = {
            field: fixed[field] for field in (
                "configuration_count", "dimension", "family_id", "instance_id",
                "replay_checksum", "target_count",
            )
        }
        if case != expected_case:
            raise ValueError(f"raw shard {index} case manifest differs from the frozen denominator")
        family = str(case["family_id"])
        families[index] = family
        stream = shard.get("source_stream", {})
        _truth_free(stream)
        if stream.get("truth_fields_visible") is not False or stream.get("candidate_columns") != 65_536:
            raise ValueError(f"raw shard {index} source stream differs")
        if len({stream.get(key) for key in ("insurance_seed", "candidate_seed", "fallback_seed")}) != 3:
            raise ValueError(f"raw shard {index} source namespaces are not distinct")
        if any(not _sha(stream.get(key)) for key in (
            "insurance_matrix_sha256", "candidate_matrix_sha256", "fallback_matrix_sha256"
        )):
            raise ValueError(f"raw shard {index} source checksums differ")
        raw_arms = shard.get("arms")
        if not isinstance(raw_arms, list) or tuple(row.get("name") for row in raw_arms) != ARMS:
            raise ValueError(f"raw shard {index} arm order differs")
        validated = {name: _validate_arm(raw_arms[position], name, case) for position, name in enumerate(ARMS)}
        physical_total = _validate_generation({name: validated[name]["document"] for name in ARMS})
        if stream.get("physical_prescreen_callbacks_total") != physical_total or physical_total > 384:
            raise ValueError(f"raw shard {index} total physical prescreen ledger differs")
        if stream.get("observed_physical_prescreen_callbacks") != physical_total or stream.get(
            "screen_oracle_budget_exhausted"
        ) is not False or stream.get("screen_oracle_evaluation_limit") != 384:
            raise ValueError(f"raw shard {index} observed source oracle ledger differs")
        _validate_cross_arm(validated)
        star = _module(validated["SIMPLICIAL_STAR_EMIT"]["document"]["generation"])
        applicability[index, "SIMPLICIAL_STAR_EMIT"] = bool(star.get("applicable"))
        applicability[index, "DIRECT_RECT_EMIT"] = bool(
            validated["DIRECT_RECT_EMIT"]["document"]["generation"].get("applicable")
            and validated["RECT_ORBIT_BREADTH"]["document"]["generation"].get("applicable")
        )
        applicability[index, "ECP_LB_FULL"] = True
        for name, arm in validated.items():
            attempts = arm["attempts"]
            terminal = common.prefix_metrics(attempts, int(case["target_count"]), int(case["configuration_count"]))
            terminal["callback_work"] += PRESCREENS
            terminals[index, name] = terminal
            terminal_rows.append({
                **terminal,
                "arm": name,
                "case_index": index,
                "configuration_count": int(case["configuration_count"]),
                "family_id": family,
                "target_count": int(case["target_count"]),
            })
            accounting["assessor_unsafe"] += int(terminal["assessor_unsafe"])
            accounting["assessor_false_targets"] += int(terminal["assessor_false_targets"])
            accounting["evaluation_count_mismatches"] += int(terminal["evaluation_count_mismatches"])
            accounting["callback_cap_violations"] += int(terminal["callback_cap_violations"])
            accounting["reported_safety"] += _reported_safety(attempts)
            accounting["exceptions"] += int(arm["document"]["terminal"].get("exceptions", 0))
            accounting["runner_budget_exhausted"] += int(
                arm["document"]["terminal"].get("runner_budget_exhausted", 0)
            )
            for threshold in THRESHOLDS:
                selected, work = _prefix(attempts, threshold)
                metric = common.prefix_metrics(selected, int(case["target_count"]), int(case["configuration_count"]))
                metric.update({"arm": name, "case_index": index, "family_id": family,
                               "threshold": threshold, "callback_work": work})
                rows.append(metric)
    if len(revisions) != 1:
        raise ValueError("Stage-D shards span multiple revisions")
    by_checkpoint = {
        (int(row["case_index"]), str(row["arm"]), int(row["threshold"])): row for row in rows
    }
    decisions: dict[str, Any] = {}
    for candidate, controls in CANDIDATE_CONTROLS.items():
        eligible = [index for index in range(1, CASE_COUNT + 1) if applicability[index, candidate]]
        headroom = [index for index in eligible if max(
            terminals[index, control]["assessor_distinct_targets_found"] for control in controls
        ) < int(next(shard["case_manifest"]["target_count"] for shard in shards if shard["case_index"] == index))]
        wins = [index for index in headroom if all(
            terminals[index, candidate]["assessor_distinct_targets_found"]
            > terminals[index, control]["assessor_distinct_targets_found"] for control in controls
        )]
        losses = [index for index in eligible if any(
            terminals[index, candidate]["assessor_distinct_targets_found"]
            < terminals[index, control]["assessor_distinct_targets_found"] for control in controls
        )]
        win_families = sorted({families[index] for index in wins})
        checkpoint_win_thresholds = {
            index: [threshold for threshold in THRESHOLDS if all(
                by_checkpoint[index, candidate, threshold]["assessor_distinct_targets_found"]
                > by_checkpoint[index, control, threshold]["assessor_distinct_targets_found"]
                for control in controls
            )]
            for index in headroom
        }
        checkpoint_wins = sorted(index for index, values in checkpoint_win_thresholds.items() if values)
        checkpoint_losses = sorted(index for index in eligible if any(
            by_checkpoint[index, candidate, threshold]["assessor_distinct_targets_found"]
            < by_checkpoint[index, control, threshold]["assessor_distinct_targets_found"]
            for threshold in THRESHOLDS for control in controls
        ))
        checkpoint_win_families = sorted({families[index] for index in checkpoint_wins})
        pooled_candidate = sum(terminals[index, candidate]["assessor_distinct_targets_found"] for index in eligible)
        pooled_controls = {control: sum(
            terminals[index, control]["assessor_distinct_targets_found"] for index in eligible
        ) for control in controls}
        signal = (
            len(wins) >= 2
            and len(win_families) >= 2
            and any(families[index] not in SPECIAL for index in wins)
            and len(checkpoint_wins) >= 2
            and len(checkpoint_win_families) >= 2
            and any(families[index] not in SPECIAL for index in checkpoint_wins)
            and all(pooled_candidate >= value for value in pooled_controls.values())
            and len(losses) <= len(wins)
            and len(checkpoint_losses) <= len(checkpoint_wins)
        )
        decisions[candidate] = {
            "equal_work_checkpoint_loss_cases": checkpoint_losses,
            "equal_work_checkpoint_win_cases": checkpoint_wins,
            "equal_work_checkpoint_win_families": checkpoint_win_families,
            "equal_work_checkpoint_win_thresholds": checkpoint_win_thresholds,
            "controls": list(controls),
            "eligible_cases": eligible,
            "headroom_cases": headroom,
            "loss_cases": losses,
            "pooled_distinct_targets": {candidate: pooled_candidate, **pooled_controls},
            "strict_terminal_win_cases": wins,
            "strict_terminal_win_families": win_families,
            "t0_signal": signal,
        }
    safety = sum(accounting.values())
    for decision in decisions.values():
        decision["safety_and_operational_zero"] = safety == 0
        decision["status"] = (
            "FAVORABLE_NONPROMOTIONAL_T0"
            if decision["t0_signal"] and safety == 0
            else "NEGATIVE_OR_INCONCLUSIVE_T0"
        )
    return {
        "accounting": dict(sorted(accounting.items())),
        "candidate_decisions": decisions,
        "case_count": CASE_COUNT,
        "experiment_id": EXPERIMENT,
        "nonpromotional_t0": True,
        "preregistration_sha256": prereg_sha,
        "revision": next(iter(revisions)),
        "rows": rows,
        "schema_version": OUTPUT_SCHEMA,
        "safety_and_operational_total": safety,
        "terminal_rows": terminal_rows,
    }


def self_test() -> dict[str, Any]:
    attempts = [{
        "assessor_qualified": False,
        "assessor_gold_matched": False,
        "assessor_target_ambiguous": False,
        "assessor_numeric_target_matched": False,
        "observed_evaluations": value,
        "reported_evaluations": value,
        "evaluation_count_mismatch": False,
    } for value in (535, 1, 20)]
    selected_600, work_600 = _prefix(attempts, 600)
    selected_1200, work_1200 = _prefix(attempts, 1_200)
    if len(selected_600) != 2 or work_600 != 600 or len(selected_1200) != 3 or work_1200 != 620:
        raise AssertionError("whole-attempt prefix fixture failed")
    try:
        _truth_free({"family_id": "forbidden"})
    except ValueError:
        poison_rejected = True
    else:
        poison_rejected = False
    if not poison_rejected:
        raise AssertionError("truth poison was accepted")
    return {
        "schema_version": "geotarget.discovery-stage-d-emitter-t0-aggregate-self-test/v1",
        "truth_poison_rejected": True,
        "whole_attempt_prefix": True,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--preregistration", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("shards", nargs="*", type=Path)
    args = parser.parse_args()
    if args.self_test:
        print(canonical_json(self_test()))
        return
    if args.preregistration is None or args.output is None:
        parser.error("--preregistration and --output are required")
    prereg = json.loads(args.preregistration.read_text())
    shards = [json.loads(path.read_text()) for path in args.shards]
    document = aggregate(prereg, shards, sha256(args.preregistration))
    args.output.write_text(canonical_json(document) + "\n")
    print(f"output={args.output}")


if __name__ == "__main__":
    main()
