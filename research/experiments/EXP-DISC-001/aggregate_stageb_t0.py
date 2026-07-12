#!/usr/bin/env python3
"""Independent stdlib-only aggregation for EXP-DISC-001 Stage-B T0."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import struct
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Mapping, Sequence

sys.path.insert(0, str(Path(__file__).resolve().parent))
import aggregate_t0 as common  # noqa: E402  (reuse the frozen scorer metrics)


EXPERIMENT = "EXP-DISC-001"
INPUT_SCHEMA = "geotarget.discovery-stageb-t0-input/v1"
AUTH_SCHEMA = "geotarget.discovery-stageb-t0-outcome-authorization/v1"
RAW_SCHEMA = "geotarget.discovery-stageb-t0-raw/v1"
PREARM_SCHEMA = "geotarget.discovery-stageb-t0-prearm/v1"
PROPOSAL_SCHEMA = "geotarget.discovery-proposal-matrix/v1"
OUTPUT_SCHEMA = "geotarget.discovery-stageb-t0-aggregate/v1"
SELF_TEST_SCHEMA = "geotarget.discovery-stageb-t0-aggregate-self-test/v1"

ARMS = ("CONTINUATION", "ISOTROPIC", "WEAK")
CASE_COUNT = 8
SOURCE_ATTEMPTS = 64
ARM_ATTEMPTS = 64
PROPOSAL_COLUMNS = 128
CALLBACK_CAP = 600
GEOMETRY_CALLBACK_CAP = 9_000
INCREMENTAL_WORK = (600, 1_200, 2_400, 4_800)
MAX_GLOBAL_QUARTETS = 24
EXPECTED_FAMILIES = {
    "CURVED-CHAIN",
    "NEAR-RANK-DEFICIENT",
    "TANGENT-CIRCLE-LINE",
    "MULTIROOT-WARPED",
}
NON_GENERALIZATION_FAMILIES = {"TANGENT-CIRCLE-LINE", "MULTIROOT-WARPED"}
_SHA256 = frozenset("0123456789abcdef")
_FORBIDDEN_PREARM_KEYS = {
    "case_id",
    "configuration_count",
    "family_id",
    "formal_case_id",
    "gold_configurations",
    "gold_targets",
    "instance_id",
    "source_index",
    "target_count",
}


canonical_json = common.canonical_json
sha256 = common.sha256
prefix_metrics = common.prefix_metrics


def _digest_document(document: Any) -> str:
    return hashlib.sha256(canonical_json(document).encode("utf-8")).hexdigest()


_RUNNER_FLOAT_LITERALS = {
    struct.pack(">d", 2.0**-20).hex(): "9.5367431640625e-7",
    struct.pack(">d", 2.0**-14).hex(): "0.00006103515625",
    struct.pack(">d", 2.0**-8).hex(): "0.00390625",
    struct.pack(">d", 2.0**-2).hex(): "0.25",
}
_RUNNER_FLOAT_SENTINEL = "__GEOTARGET_STAGEB_RAW_FLOAT_"


def _runner_digest(document: Any) -> str:
    """Reproduce JSON3's frozen radius spelling without invoking Julia."""
    replacements: dict[str, str] = {}

    def normalize(value: Any) -> Any:
        if isinstance(value, float):
            bits = struct.pack(">d", value).hex()
            literal = _RUNNER_FLOAT_LITERALS.get(bits)
            if literal is None:
                raise ValueError("runner digest contains an unregistered Float64")
            token = f"{_RUNNER_FLOAT_SENTINEL}{bits}__"
            replacements[json.dumps(token)] = literal
            return token
        if isinstance(value, str):
            if value.startswith(_RUNNER_FLOAT_SENTINEL):
                raise ValueError("runner digest sentinel occurs in source text")
            return value
        if isinstance(value, list):
            return [normalize(child) for child in value]
        if isinstance(value, dict):
            if any(str(key).startswith(_RUNNER_FLOAT_SENTINEL) for key in value):
                raise ValueError("runner digest sentinel occurs in a source key")
            return {str(key): normalize(child) for key, child in value.items()}
        if value is None or isinstance(value, (bool, int)):
            return value
        raise ValueError("runner digest contains an unsupported JSON value")

    serialized = canonical_json(normalize(document))
    for token, literal in replacements.items():
        serialized = serialized.replace(token, literal)
    if _RUNNER_FLOAT_SENTINEL in serialized:
        raise ValueError("runner Float64 sentinel replacement was incomplete")
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _sha_text(value: Any) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and not (set(value) - _SHA256)
    )


def _integer(value: Any, label: str, *, minimum: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise ValueError(f"{label} must be an integer >= {minimum}")
    return value


def _float64_bits(value: Any, label: str) -> str:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{label} is not numeric")
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"{label} is not finite")
    return struct.pack(">d", number).hex()


def _validate_bit(value: Any, label: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 16
        or set(value) - _SHA256
    ):
        raise ValueError(f"{label} is not lowercase Float64 bits")
    if not math.isfinite(struct.unpack(">d", bytes.fromhex(value))[0]):
        raise ValueError(f"{label} decodes to a nonfinite Float64")
    return value


def _from_bits(value: str) -> float:
    return struct.unpack(">d", bytes.fromhex(value))[0]


def _bits_vector(raw: Any, dimension: int, label: str) -> list[str]:
    if not isinstance(raw, list) or len(raw) != dimension:
        raise ValueError(f"{label} has wrong dimension")
    return [_validate_bit(value, f"{label}[{index}]") for index, value in enumerate(raw, 1)]


def _validate_bits_matrix(
    raw: Any, dimension: int, columns: int, label: str
) -> list[list[str]]:
    if not isinstance(raw, list) or len(raw) != columns:
        raise ValueError(f"{label} must contain {columns} columns")
    result: list[list[str]] = []
    for column_index, column in enumerate(raw, start=1):
        if not isinstance(column, list) or len(column) != dimension:
            raise ValueError(f"{label} column {column_index} has wrong dimension")
        result.append(
            [
                _validate_bit(value, f"{label}[{column_index}][{row_index}]")
                for row_index, value in enumerate(column, start=1)
            ]
        )
    return result


def _matrix_digest(bits: list[list[str]], dimension: int) -> str:
    return _digest_document(
        {
            "column_count": len(bits),
            "coordinate_float64_bits_by_column": bits,
            "dimension": dimension,
        }
    )


def _slice_digest(
    artifact_sha: str,
    first: int,
    last: int,
    bits: list[list[str]],
    lanes: list[str],
    source_columns: list[int],
) -> str:
    return _digest_document(
        {
            "artifact_sha256": artifact_sha,
            "column_range": [first, last],
            "coordinate_float64_bits_by_column": bits[first - 1 : last],
            "lane_schedule": lanes[first - 1 : last],
            "source_columns": source_columns[first - 1 : last],
        }
    )


def _safe_target_set(attempts: Sequence[dict[str, Any]]) -> set[str]:
    values = {row.get("assessor_matched_target_id") for row in common._safe_hits(attempts)}
    if None in values:
        raise ValueError("a safe assessor hit has no target identity")
    return {str(value) for value in values}


def _attempt_safety_counts(attempts: Sequence[dict[str, Any]]) -> dict[str, int]:
    return {
        "assessor_ambiguity": sum(
            bool(row.get("assessor_qualified"))
            and bool(row.get("assessor_target_ambiguous"))
            for row in attempts
        ),
        "assessor_false_or_unsafe": sum(common._unsafe(row) for row in attempts),
        "reported_accepted_ambiguous": sum(
            bool(row.get("reported_accepted")) and bool(row.get("target_ambiguous"))
            for row in attempts
        ),
        "reported_accepted_canonical_invalid": sum(
            bool(row.get("reported_accepted")) and not bool(row.get("canonical_valid"))
            for row in attempts
        ),
        "reported_accepted_gold_inconsistent": sum(
            bool(row.get("reported_accepted")) and not bool(row.get("gold_matched"))
            for row in attempts
        ),
        "reported_accepted_numeric_target_only": sum(
            bool(row.get("reported_accepted"))
            and bool(row.get("numeric_target_matched"))
            and not bool(row.get("gold_matched"))
            for row in attempts
        ),
    }


def _load_relative(repo_root: Path, relative: Any, label: str) -> Path:
    if not isinstance(relative, str) or not relative or Path(relative).is_absolute():
        raise ValueError(f"{label} path must be nonempty and repository-relative")
    result = (repo_root / relative).resolve()
    try:
        result.relative_to(repo_root.resolve())
    except ValueError as error:
        raise ValueError(f"{label} path escapes the repository") from error
    if not result.is_file():
        raise ValueError(f"{label} is absent: {relative}")
    return result


def _validate_input(document: dict[str, Any]) -> list[dict[str, Any]]:
    if document.get("schema_version") != INPUT_SCHEMA or document.get("experiment_id") != EXPERIMENT:
        raise ValueError("unexpected Stage-B T0 input manifest")
    if document.get("stage") != "stage-b-weak-geometry-t0":
        raise ValueError("Stage-B T0 input stage differs")
    if document.get("lab_confirmation_512_768", False) is not False:
        raise ValueError("Stage-B T0 cannot claim 512/768-bit confirmation")
    if document.get("nonpromotional_t0") is not True:
        raise ValueError("Stage-B T0 input is not explicitly nonpromotional")
    if not _sha_text(document.get("preregistration", {}).get("sha256")):
        raise ValueError("Stage-B T0 input lacks its preregistration binding")
    cases = document.get("cases")
    if not isinstance(cases, list) or len(cases) != CASE_COUNT:
        raise ValueError("Stage-B T0 input must contain exactly eight cases")
    if [case.get("case_index") for case in cases] != list(range(1, CASE_COUNT + 1)):
        raise ValueError("Stage-B T0 input case order differs")
    counts = Counter(case.get("family_id") for case in cases)
    if set(counts) != EXPECTED_FAMILIES or any(count != 2 for count in counts.values()):
        raise ValueError("Stage-B T0 must contain two cases from each frozen family")
    for case in cases:
        for field in (
            "case_index",
            "configuration_count",
            "dimension",
            "family_id",
            "formal_case_id",
            "instance_id",
            "proposal",
            "residual_dimension",
            "source",
            "target_count",
        ):
            if field not in case:
                raise ValueError(f"input case lacks {field}")
        for field in ("dimension", "residual_dimension", "configuration_count", "target_count"):
            _integer(case[field], f"case {case['case_index']} {field}", minimum=1)
        proposal = case["proposal"]
        if not isinstance(proposal, dict) or proposal.get("method") != "D0-IID-ALL":
            raise ValueError("Stage-B source must be D0-IID-ALL")
        if proposal.get("initial_prefix_columns") != [1, 64] or proposal.get(
            "continuation_columns"
        ) != [65, 128]:
            raise ValueError("Stage-B D0 source/continuation columns differ")
        for field in (
            "artifact_sha256",
            "continuation_sha256",
            "file_sha256",
            "initial_prefix_sha256",
            "maximum_prefix_sha256",
        ):
            if not _sha_text(proposal.get(field)):
                raise ValueError(f"Stage-B proposal lacks a valid {field}")
        if proposal["maximum_prefix_sha256"] != proposal["artifact_sha256"]:
            raise ValueError("maximum prefix must bind the complete proposal artifact")
        source = case["source"]
        if not isinstance(source, dict) or not _sha_text(source.get("replay_checksum")):
            raise ValueError("Stage-B source replay binding is absent")
    if document.get("prefixes", {}).get("initial", [1, 64]) != [1, 64] or document.get(
        "prefixes", {}
    ).get("continuation", [65, 128]) != [65, 128]:
        raise ValueError("Stage-B top-level prefix contract differs")
    return cases


def _validate_authorization(
    document: dict[str, Any], input_sha: str, aggregator_sha: str, preregistration_sha: str
) -> None:
    if document.get("schema_version") != AUTH_SCHEMA or document.get(
        "outcome_execution_authorized"
    ) is not True:
        raise ValueError("Stage-B T0 outcomes are not authorized")
    if document.get("input_manifest", {}).get("sha256") != input_sha:
        raise ValueError("authorization binds another Stage-B input")
    if document.get("nonpromotional_t0") is not True:
        raise ValueError("authorization is not limited to nonpromotional T0")
    if document.get("aggregator_source_sha256") != aggregator_sha:
        raise ValueError("authorization binds another Stage-B aggregator")
    if not _sha_text(document.get("runner_source_sha256")):
        raise ValueError("authorization lacks a runner SHA-256")
    if document.get("preregistration", {}).get("sha256") != preregistration_sha:
        raise ValueError("authorization binds another preregistration")
    dependencies = document.get("dependency_source_sha256")
    if not isinstance(dependencies, dict) or not dependencies or not all(
        isinstance(path, str) and path and _sha_text(digest)
        for path, digest in dependencies.items()
    ):
        raise ValueError("authorization dependency bindings are absent")


def _validate_proposal(
    case: dict[str, Any], document: dict[str, Any], file_sha: str
) -> list[list[str]]:
    binding = case["proposal"]
    if file_sha != binding["file_sha256"]:
        raise ValueError("D0 proposal file hash differs")
    if document.get("schema_version") != PROPOSAL_SCHEMA or document.get("method") != "D0-IID-ALL":
        raise ValueError("unexpected Stage-B proposal artifact")
    dimension = int(case["dimension"])
    if document.get("dimension") != dimension or document.get("column_count") != PROPOSAL_COLUMNS:
        raise ValueError("D0 proposal shape differs")
    internal_sha = document.get("sha256")
    if internal_sha != binding["artifact_sha256"] or not _sha_text(internal_sha):
        raise ValueError("D0 proposal internal hash differs")
    payload = dict(document)
    payload.pop("sha256", None)
    if _digest_document(payload) != internal_sha:
        raise ValueError("D0 proposal internal digest is invalid")
    bits = _validate_bits_matrix(
        document.get("coordinate_float64_bits_by_column"),
        dimension,
        PROPOSAL_COLUMNS,
        "D0 coordinates",
    )
    lanes = document.get("lane_schedule")
    columns = document.get("source_columns")
    if (
        not isinstance(lanes, list)
        or len(lanes) != PROPOSAL_COLUMNS
        or any(str(lane).lower() != "iid" for lane in lanes)
    ):
        raise ValueError("D0 proposal is not all-IID")
    if columns != list(range(1, PROPOSAL_COLUMNS + 1)):
        raise ValueError("D0 proposal source-column trace differs")
    if _slice_digest(internal_sha, 1, 64, bits, lanes, columns) != binding[
        "initial_prefix_sha256"
    ]:
        raise ValueError("D0 source prefix digest differs")
    if _slice_digest(internal_sha, 65, 128, bits, lanes, columns) != binding[
        "continuation_sha256"
    ]:
        raise ValueError("D0 continuation digest differs")
    return bits


def _case_manifest_matches(observed: Any, case: dict[str, Any]) -> bool:
    if not isinstance(observed, dict):
        return False
    for field in (
        "case_index",
        "configuration_count",
        "dimension",
        "family_id",
        "formal_case_id",
        "instance_id",
        "residual_dimension",
        "target_count",
    ):
        if observed.get(field) != case.get(field):
            return False
    observed_replay = observed.get("source_replay_checksum")
    if observed_replay is None and isinstance(observed.get("source"), dict):
        observed_replay = observed["source"].get("replay_checksum")
    return observed_replay == case["source"]["replay_checksum"]


def _inspect_truth_free(value: Any) -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            if str(key) in _FORBIDDEN_PREARM_KEYS:
                raise ValueError(f"pre-arm artifact leaks {key}")
            _inspect_truth_free(child)
    elif isinstance(value, list):
        for child in value:
            _inspect_truth_free(child)


def _arm_entries(prearm: dict[str, Any]) -> list[dict[str, Any]]:
    entries = prearm.get("arm_matrices")
    if not isinstance(entries, list) or [entry.get("name") for entry in entries] != list(ARMS):
        raise ValueError("pre-arm matrices must use the frozen arm order")
    return entries


def _plan_status(plan: dict[str, Any]) -> str:
    return str(plan.get("status", "")).lower().lstrip(":")


def _plan_source_index(plan: dict[str, Any]) -> int:
    value = plan.get(
        "parent_source_index", plan.get("source_start_index", plan.get("source_index"))
    )
    return _integer(value, "geometry plan parent source index", minimum=1)


def _plan_callbacks(plan: dict[str, Any]) -> int:
    return _integer(plan.get("callback_count"), "geometry plan callbacks")


def _quartet_map(plans: Sequence[dict[str, Any]], dimension: int) -> dict[int, dict[str, Any]]:
    result: dict[int, dict[str, Any]] = {}
    for plan in plans:
        quartets = plan.get("quartets", [])
        if not isinstance(quartets, list):
            raise ValueError("geometry plan quartets must be a list")
        for quartet in quartets:
            index = quartet.get("global_comparison_index", quartet.get("comparison_index"))
            index = _integer(index, "global comparison index", minimum=1)
            if index in result:
                raise ValueError("global comparison index is duplicated")
            physical = _validate_bits_matrix(
                quartet.get("physical_float64_bits_by_column"),
                dimension,
                4,
                f"quartet {index} physical points",
            )
            radius = quartet.get("radius")
            if isinstance(radius, bool) or not isinstance(radius, (int, float)) or not math.isfinite(
                float(radius)
            ) or float(radius) <= 0:
                raise ValueError("quartet radius must be finite and positive")
            copy_quartet = dict(quartet)
            copy_quartet["_physical"] = physical
            result[index] = copy_quartet
    if sorted(result) != list(range(1, len(result) + 1)):
        raise ValueError("global comparison indices must be contiguous from one")
    if len(result) > MAX_GLOBAL_QUARTETS:
        raise ValueError("case-global quartet cap exceeded")
    return result


def _validate_quartet_geometry(
    quartet: dict[str, Any], lower_bits: list[str], upper_bits: list[str], dimension: int
) -> None:
    anchor_bits = _bits_vector(
        quartet.get("anchor_float64_bits"), dimension, "quartet anchor"
    )
    weak_bits = _bits_vector(
        quartet.get("weak_direction_float64_bits"), dimension, "weak direction"
    )
    isotropic_bits = _bits_vector(
        quartet.get("isotropic_direction_float64_bits"), dimension, "isotropic direction"
    )
    normalized_bits = _validate_bits_matrix(
        quartet.get("normalized_float64_bits_by_column"),
        dimension,
        4,
        "quartet normalized points",
    )
    physical_bits = quartet["_physical"]
    lower = [_from_bits(value) for value in lower_bits]
    upper = [_from_bits(value) for value in upper_bits]
    anchor = [_from_bits(value) for value in anchor_bits]
    weak = [_from_bits(value) for value in weak_bits]
    isotropic = [_from_bits(value) for value in isotropic_bits]
    midpoint = [lo / 2.0 + hi / 2.0 for lo, hi in zip(lower, upper, strict=True)]
    half_range = [hi / 2.0 - lo / 2.0 for lo, hi in zip(lower, upper, strict=True)]
    if any(scale <= 0 or not math.isfinite(scale) for scale in half_range):
        raise ValueError("pre-arm bounds are not a finite box")
    for direction, label in ((weak, "weak"), (isotropic, "isotropic")):
        norm = math.sqrt(sum(value * value for value in direction))
        if not math.isfinite(norm) or abs(norm - 1.0) > 1.0e-12:
            raise ValueError(f"{label} probe direction is not unit length")
    radius = float(quartet["radius"])
    anchor_unit = [
        (value - midpoint[row]) / half_range[row] for row, value in enumerate(anchor)
    ]
    expected_unit: list[list[float]] = []
    for direction, sign in ((weak, 1.0), (weak, -1.0), (isotropic, 1.0), (isotropic, -1.0)):
        expected_unit.append(
            [
                anchor_unit[row] + sign * radius * direction[row]
                for row in range(dimension)
            ]
        )
    for column in range(4):
        expected_normalized = [
            _float64_bits(value, "expected normalized point")
            for value in expected_unit[column]
        ]
        if normalized_bits[column] != expected_normalized:
            raise ValueError("quartet normalized point is not anchor +/- radius*direction")
        expected_physical = [
            _float64_bits(
                midpoint[row] + half_range[row] * expected_unit[column][row],
                "expected physical point",
            )
            for row in range(dimension)
        ]
        if physical_bits[column] != expected_physical:
            raise ValueError("quartet physical point is not the affine box image")


def _validate_prearm(
    document: dict[str, Any], case: dict[str, Any], proposal_bits: list[list[str]]
) -> dict[str, Any]:
    if document.get("schema_version") != PREARM_SCHEMA:
        raise ValueError("unexpected pre-arm artifact schema")
    _inspect_truth_free(document)
    if document.get("truth_free") is not True:
        raise ValueError("pre-arm artifact is not truth-free")
    if document.get("experiment_id") != EXPERIMENT or document.get("stage") != "stage-b-t0":
        raise ValueError("pre-arm experiment/stage differs")
    if document.get("arm_order") != list(ARMS) or document.get("column_count") != ARM_ATTEMPTS:
        raise ValueError("pre-arm arm/column contract differs")
    if int(document.get("dimension", case["dimension"])) != int(case["dimension"]):
        raise ValueError("pre-arm dimension differs")
    if document.get("recursive_plan_calls", 0) != 0:
        raise ValueError("pre-arm artifact records recursive geometry")

    dimension = int(case["dimension"])
    matrix_bits: dict[str, list[list[str]]] = {}
    matrix_sha: dict[str, str] = {}
    for entry in _arm_entries(document):
        name = entry["name"]
        bits = _validate_bits_matrix(
            entry.get("coordinate_float64_bits_by_column"),
            dimension,
            ARM_ATTEMPTS,
            f"{name} pre-arm matrix",
        )
        digest = _matrix_digest(bits, dimension)
        if entry.get("matrix_sha256") != digest:
            raise ValueError(f"{name} pre-arm matrix digest differs")
        matrix_bits[name], matrix_sha[name] = bits, digest

    geometry = document.get("geometry")
    if not isinstance(geometry, dict):
        raise ValueError("pre-arm geometry binding is absent")
    raw_quartets = geometry.get("quartets")
    if not isinstance(raw_quartets, list):
        raise ValueError("pre-arm geometry quartets must be a list")
    quartets = _quartet_map([{"quartets": raw_quartets}], dimension)
    bounds = document.get("bounds")
    if not isinstance(bounds, dict):
        raise ValueError("pre-arm public bounds are absent")
    lower_bits = _bits_vector(bounds.get("lower_float64_bits"), dimension, "lower bounds")
    upper_bits = _bits_vector(bounds.get("upper_float64_bits"), dimension, "upper bounds")
    if geometry.get("quartet_count") != len(quartets) or len(quartets) > MAX_GLOBAL_QUARTETS:
        raise ValueError("pre-arm quartet count differs")
    for quartet in quartets.values():
        parent = _integer(
            quartet.get("parent_source_index"), "quartet parent source index", minimum=1
        )
        if parent > SOURCE_ATTEMPTS or quartet.get("parent_generation") != 0:
            raise ValueError("quartet provenance is not from a generation-zero source")
        _validate_quartet_geometry(quartet, lower_bits, upper_bits, dimension)
    if geometry.get("quartet_provenance_sha256") != _runner_digest(raw_quartets):
        raise ValueError("pre-arm quartet provenance digest differs")

    schedule = document.get("schedule")
    if not isinstance(schedule, list) or len(schedule) != ARM_ATTEMPTS:
        raise ValueError("pre-arm schedule must contain 64 slots")
    if document.get("schedule_sha256") != _runner_digest(schedule):
        raise ValueError("pre-arm schedule digest differs")
    geometry_groups: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for ordinal, slot in enumerate(schedule, start=1):
        if slot.get("slot") != ordinal:
            raise ValueError("pre-arm slot order differs")
        lane = str(slot.get("lane", "")).lower().lstrip(":")
        iid_slot = (ordinal - 1) % 4 == 0
        if iid_slot != (lane == "iid"):
            raise ValueError("IID service is not exactly one-in-four")
        if lane not in {"iid", "continuation", "geometry"}:
            raise ValueError("pre-arm schedule has an unknown lane")
        if matrix_bits["CONTINUATION"][ordinal - 1] != proposal_bits[63 + ordinal]:
            raise ValueError("continuation control differs from frozen D0 source")
        derived = slot.get("derived_from_probe")
        if lane == "geometry":
            if slot.get("generation") != 1 or slot.get("parent_generation") != 0:
                raise ValueError("geometry provenance is not generation 0 -> 1")
            if derived is not True or slot.get("source_column") is not None:
                raise ValueError("geometry slot provenance differs")
            comparison = slot.get(
                "global_comparison_index", slot.get("comparison_index")
            )
            comparison = _integer(comparison, "schedule comparison index", minimum=1)
            if comparison not in quartets:
                raise ValueError("schedule references an absent geometry quartet")
            point_ordinal = _integer(slot.get("point_ordinal"), "weak point ordinal", minimum=1)
            if point_ordinal not in (1, 2):
                raise ValueError("weak point ordinal must be one or two")
            if slot.get("sign") != (1 if point_ordinal == 1 else -1):
                raise ValueError("geometry sign and point ordinal disagree")
            quartet = quartets[comparison]
            if slot.get("parent_source_index") != quartet.get("parent_source_index"):
                raise ValueError("schedule and quartet parent differ")
            if float(slot.get("radius")) != float(quartet["radius"]):
                raise ValueError("schedule and quartet radius differ")
            if matrix_bits["WEAK"][ordinal - 1] != quartet["_physical"][point_ordinal - 1]:
                raise ValueError("weak matrix is not the scheduled quartet point")
            if matrix_bits["ISOTROPIC"][ordinal - 1] != quartet["_physical"][point_ordinal + 1]:
                raise ValueError("isotropic matrix is not the paired quartet point")
            geometry_groups[comparison].append(slot)
        else:
            if slot.get("generation") != 0 or slot.get("parent_generation") is not None:
                raise ValueError("source continuation must remain generation zero")
            if derived is not False or slot.get("source_column") != 64 + ordinal:
                raise ValueError("source continuation provenance differs")
            expected = proposal_bits[63 + ordinal]
            if any(matrix_bits[name][ordinal - 1] != expected for name in ARMS):
                raise ValueError("source continuation bits differ across arms")
    if set(geometry_groups) != set(quartets):
        raise ValueError("one or more valid quartets were not scheduled")
    for comparison, slots in geometry_groups.items():
        if len(slots) != 2 or {slot["point_ordinal"] for slot in slots} != {1, 2}:
            raise ValueError(f"comparison {comparison} is not a +/- pair")
        if len({slot["parent_source_index"] for slot in slots}) != 1:
            raise ValueError("paired slots do not share an anchor")
    return {
        "anchor_count": _integer(geometry.get("anchor_count"), "pre-arm anchor count"),
        "callback_count": _integer(
            geometry.get("callback_count"), "pre-arm geometry callback count"
        ),
        "matrix_bits": matrix_bits,
        "matrix_sha": matrix_sha,
        "quartets": raw_quartets,
        "quartet_map": quartets,
        "quartet_count": len(quartets),
        "schedule": schedule,
    }


def _attempt_start_bits(attempt: dict[str, Any], dimension: int) -> list[str]:
    start = attempt.get("start")
    if not isinstance(start, list) or len(start) != dimension:
        raise ValueError("solver attempt start has wrong dimension")
    return [_float64_bits(value, "solver attempt start") for value in start]


def _validate_attempts(
    attempts: Any,
    expected_bits: list[list[str]],
    dimension: int,
    label: str,
) -> dict[str, int]:
    if not isinstance(attempts, list) or len(attempts) != len(expected_bits):
        raise ValueError(f"{label} must contain {len(expected_bits)} attempts")
    if [common._index(row) for row in attempts] != list(range(1, len(attempts) + 1)):
        raise ValueError(f"{label} attempt order differs")
    for index, (attempt, wanted) in enumerate(zip(attempts, expected_bits, strict=True), start=1):
        if _attempt_start_bits(attempt, dimension) != wanted:
            raise ValueError(f"{label} start {index} differs from its frozen matrix")
    return {
        "callback_cap_violations": sum(
            common._observed(row) > CALLBACK_CAP or common._reported(row) > CALLBACK_CAP
            for row in attempts
        ),
        "evaluation_count_mismatches": sum(
            common._observed(row) != common._reported(row)
            or bool(row.get("evaluation_count_mismatch"))
            for row in attempts
        ),
        "exceptions": sum(row.get("exception") is not None for row in attempts),
        "runner_budget_exhausted": sum(bool(row.get("budget_exhausted")) for row in attempts),
    }


def _validate_terminal(
    terminal: Any, attempts: Sequence[dict[str, Any]], expected_count: int
) -> int:
    if not isinstance(terminal, dict):
        return 1
    expected = {
        "attempt_count": expected_count,
        "callback_work": sum(common._observed(row) for row in attempts),
        "evaluation_count_mismatches": sum(
            common._observed(row) != common._reported(row)
            or bool(row.get("evaluation_count_mismatch"))
            for row in attempts
        ),
        "exceptions": sum(row.get("exception") is not None for row in attempts),
        "runner_budget_exhausted": sum(bool(row.get("budget_exhausted")) for row in attempts),
        "callback_cap_violations": sum(
            common._observed(row) > CALLBACK_CAP or common._reported(row) > CALLBACK_CAP
            for row in attempts
        ),
    }
    return int(any(terminal.get(field) != value for field, value in expected.items()))


def _validate_geometry(
    geometry: Any, prearm: dict[str, Any], source_attempts: Sequence[dict[str, Any]]
) -> tuple[int, bool, int]:
    if not isinstance(geometry, dict) or not isinstance(geometry.get("attempt"), dict):
        raise ValueError("raw geometry accounting attempt is absent")
    attempt = geometry["attempt"]
    work = _integer(geometry.get("callback_count"), "geometry callback count")
    if work > GEOMETRY_CALLBACK_CAP:
        raise ValueError("geometry callback hard cap exceeded")
    if common._observed(attempt) != work or common._reported(attempt) != work or bool(
        attempt.get("evaluation_count_mismatch")
    ):
        raise ValueError("geometry observed/reported callback count differs")
    if (
        attempt.get("endpoint") is not None
        or bool(attempt.get("assessor_qualified"))
        or bool(attempt.get("reported_accepted"))
        or bool(attempt.get("reported_converged"))
        or attempt.get("status") != "STAGEB_GEOMETRY_ONLY"
        or attempt.get("exception") is not None
        or bool(attempt.get("budget_exhausted"))
    ):
        raise ValueError("geometry accounting attempt became an answer or failed")
    plans = geometry.get("plans")
    if not isinstance(plans, list):
        raise ValueError("raw geometry plans must be a list")
    anchor_count = _integer(geometry.get("anchor_count"), "geometry anchor count")
    if anchor_count != len(plans) or anchor_count != prearm["anchor_count"]:
        raise ValueError("geometry did not process its complete FIFO archive")
    source_indices = [_plan_source_index(plan) for plan in plans]
    if source_indices != sorted(source_indices) or len(source_indices) != len(set(source_indices)):
        raise ValueError("geometry plans are not a unique FIFO sequence")
    remaining = MAX_GLOBAL_QUARTETS
    for plan in plans:
        if plan.get("generation") != 0:
            raise ValueError("geometry plan is not generation zero")
        if plan.get("maximum_comparisons") != remaining:
            raise ValueError("geometry plan did not receive the remaining global budget")
        plan_quartets = _integer(plan.get("quartet_count"), "plan quartet count")
        attempted = _integer(
            plan.get("attempted_comparisons", 0), "plan attempted comparisons"
        )
        rejected = _integer(
            plan.get("rejected_comparisons", 0), "plan rejected comparisons"
        )
        if plan_quartets > remaining or attempted > remaining or rejected > attempted:
            raise ValueError("geometry plan exceeded its remaining comparison budget")
        remaining -= plan_quartets
    endpoint_indices = [
        index
        for index, row in enumerate(source_attempts, start=1)
        if row.get("endpoint") is not None
    ]
    if source_indices != endpoint_indices:
        raise ValueError("geometry plans are not the complete source endpoint FIFO")
    for quartet in prearm["quartet_map"].values():
        parent = int(quartet["parent_source_index"])
        endpoint = source_attempts[parent - 1].get("endpoint")
        if not isinstance(endpoint, list) or len(endpoint) != len(
            quartet["anchor_float64_bits"]
        ):
            raise ValueError("quartet anchor source endpoint is malformed")
        endpoint_bits = [_float64_bits(value, "source endpoint") for value in endpoint]
        if endpoint_bits != quartet["anchor_float64_bits"]:
            raise ValueError("quartet anchor differs from its FIFO source endpoint")
    if sum(_plan_callbacks(plan) for plan in plans) != work:
        raise ValueError("per-plan callbacks do not sum to geometry work")
    applicable = sum(_plan_status(plan) == "applicable" for plan in plans)
    if geometry.get("applicable_anchor_count") != applicable:
        raise ValueError("geometry applicable-anchor count differs")
    if geometry.get("quartet_count") != prearm["quartet_count"]:
        raise ValueError("geometry quartet count differs")
    if sum(_integer(plan.get("quartet_count"), "plan quartet count") for plan in plans) != prearm[
        "quartet_count"
    ]:
        raise ValueError("raw per-plan quartet counts differ from pre-arm provenance")
    if prearm["callback_count"] != work:
        raise ValueError("raw and pre-arm geometry callback work differs")
    reasons = geometry.get("reasons")
    expected_reasons = dict(Counter(str(plan.get("reason")) for plan in plans))
    if reasons != expected_reasons:
        raise ValueError("geometry reason trace differs")
    return work, applicable > 0, applicable


def _completed_within(
    attempts: Sequence[dict[str, Any]], callback_allowance: int
) -> list[dict[str, Any]]:
    completed: list[dict[str, Any]] = []
    work = 0
    for attempt in attempts:
        candidate = work + common._observed(attempt)
        if candidate > callback_allowance:
            break
        completed.append(attempt)
        work = candidate
    return completed


def _metrics_row(
    attempts: Sequence[dict[str, Any]], case: dict[str, Any]
) -> dict[str, Any]:
    return prefix_metrics(
        attempts, int(case["target_count"]), int(case["configuration_count"])
    )


def _validate_raw_header(
    shard: dict[str, Any], case: dict[str, Any], input_sha: str, auth_sha: str,
    preregistration_sha: str,
) -> None:
    index = int(case["case_index"])
    if any(
        (
            shard.get("schema_version") != RAW_SCHEMA,
            shard.get("experiment_id") != EXPERIMENT,
            shard.get("stage") != "stage-b-t0",
            shard.get("partition", "development") != "development",
            shard.get("case_index") != index,
            shard.get("lab_confirmation_512_768", False) is not False,
            shard.get("nonpromotional_t0") is not True,
            shard.get("input_manifest", {}).get("sha256") != input_sha,
            shard.get("authorization", {}).get("sha256") != auth_sha,
            shard.get("preregistration", {}).get("sha256") != preregistration_sha,
            not _case_manifest_matches(shard.get("case_manifest"), case),
            shard.get("arm_order") != list(ARMS),
        )
    ):
        raise ValueError(f"raw Stage-B shard {index} contract mismatch")
    revision = shard.get("revision")
    if not isinstance(revision, dict) or revision.get("git_dirty") is not False or not revision.get(
        "git_head"
    ):
        raise ValueError("Stage-B shard did not run from a clean revision")
    threads = shard.get("thread_contract")
    if not isinstance(threads, dict) or threads.get("julia_threads") != 1 or threads.get(
        "blas_threads"
    ) != 1:
        raise ValueError("Stage-B shard violates the one-thread contract")
    for field, expected in (
        ("solver_worker_count", 1),
        ("case_process_limit", 8),
        ("assigned_cpu", index - 1),
        ("cpus_allowed_list", str(index - 1)),
    ):
        if threads.get(field) != expected:
            raise ValueError(f"Stage-B thread contract {field} differs")
    environment = threads.get("environment")
    if not isinstance(environment, dict) or any(
        environment.get(name) != "1"
        for name in ("JULIA_NUM_THREADS", "OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS")
    ):
        raise ValueError("Stage-B thread environment differs")


def aggregate_documents(
    input_document: dict[str, Any],
    authorization: dict[str, Any],
    shards: Sequence[dict[str, Any]],
    *,
    input_sha: str,
    authorization_sha: str,
    aggregator_sha: str,
    proposal_documents: Mapping[int, tuple[dict[str, Any], str]],
    prearm_documents: Mapping[int, tuple[dict[str, Any], str]],
) -> dict[str, Any]:
    cases = _validate_input(input_document)
    preregistration_sha = input_document["preregistration"]["sha256"]
    _validate_authorization(
        authorization, input_sha, aggregator_sha, preregistration_sha
    )
    if len(shards) != CASE_COUNT or sorted(
        int(shard.get("case_index", 0)) for shard in shards
    ) != list(range(1, CASE_COUNT + 1)):
        raise ValueError("Stage-B raw case shards are missing or duplicated")
    if set(proposal_documents) != set(range(1, CASE_COUNT + 1)) or set(
        prearm_documents
    ) != set(range(1, CASE_COUNT + 1)):
        raise ValueError("Stage-B proposal/pre-arm artifacts are incomplete")

    accounting: defaultdict[str, int] = defaultdict(int)
    case_rows: list[dict[str, Any]] = []
    checkpoint_rows: list[dict[str, Any]] = []
    case_state: list[dict[str, Any]] = []
    revisions: set[str] = set()

    for shard in sorted(shards, key=lambda row: int(row["case_index"])):
        index = int(shard["case_index"])
        case = cases[index - 1]
        _validate_raw_header(
            shard, case, input_sha, authorization_sha, preregistration_sha
        )
        revisions.add(shard["revision"]["git_head"])

        proposal_doc, proposal_file_sha = proposal_documents[index]
        proposal_bits = _validate_proposal(case, proposal_doc, proposal_file_sha)
        source = shard.get("source")
        if not isinstance(source, dict) or source.get("proposal") != case["proposal"]:
            raise ValueError("raw source does not bind the frozen D0 proposal")
        source_attempts = source.get("attempts")
        source_accounting = _validate_attempts(
            source_attempts,
            proposal_bits[:SOURCE_ATTEMPTS],
            int(case["dimension"]),
            "source",
        )
        for field, value in source_accounting.items():
            accounting[field] += value
        for field, value in _attempt_safety_counts(source_attempts).items():
            accounting[field] += value
        accounting["terminal_mismatches"] += _validate_terminal(
            source.get("terminal"), source_attempts, SOURCE_ATTEMPTS
        )
        source_work = sum(common._observed(row) for row in source_attempts)
        source_metrics = _metrics_row(source_attempts, case)
        source_targets = _safe_target_set(source_attempts)
        headroom = not bool(source_metrics["assessor_safe_full"])

        binding = shard.get("prearm")
        prearm_doc, prearm_file_sha = prearm_documents[index]
        if not isinstance(binding, dict) or binding.get("sha256") != prearm_file_sha:
            raise ValueError("raw shard binds another pre-arm artifact")
        if prearm_doc.get("input_manifest_sha256") != input_sha or prearm_doc.get(
            "preregistration", {}
        ).get("sha256") != preregistration_sha:
            raise ValueError("pre-arm input/preregistration binding differs")
        expected_source_artifact = {
            field: case["proposal"][field]
            for field in ("artifact_sha256", "continuation_sha256", "file_sha256", "path")
        }
        if prearm_doc.get("source_artifact") != expected_source_artifact:
            raise ValueError("pre-arm source artifact binding differs")
        if binding.get("schedule_sha256") != prearm_doc.get("schedule_sha256") or binding.get(
            "quartet_provenance_sha256"
        ) != prearm_doc.get("geometry", {}).get("quartet_provenance_sha256"):
            raise ValueError("raw pre-arm schedule/provenance binding differs")
        prearm = _validate_prearm(prearm_doc, case, proposal_bits)
        geometry_work, applicable, applicable_anchors = _validate_geometry(
            shard.get("geometry"), prearm, source_attempts
        )

        arms = shard.get("arms")
        if not isinstance(arms, list) or [entry.get("name") for entry in arms] != list(ARMS):
            raise ValueError("raw arms differ from the frozen order")
        terminal_by_arm: dict[str, dict[str, Any]] = {}
        checkpoint_by_arm: dict[str, dict[int, dict[str, Any]]] = {}
        for arm in arms:
            name = arm["name"]
            if arm.get("matrix_sha256") != prearm["matrix_sha"][name]:
                raise ValueError(f"raw {name} matrix binding differs")
            attempts = arm.get("attempts")
            arm_accounting = _validate_attempts(
                attempts,
                prearm["matrix_bits"][name],
                int(case["dimension"]),
                f"{name} arm",
            )
            for field, value in arm_accounting.items():
                accounting[field] += value
            for field, value in _attempt_safety_counts(attempts).items():
                accounting[field] += value
            accounting["terminal_mismatches"] += _validate_terminal(
                arm.get("terminal"), attempts, ARM_ATTEMPTS
            )
            arm_work = sum(common._observed(row) for row in attempts)
            combined = list(source_attempts) + list(attempts)
            metrics = _metrics_row(combined, case)
            targets = _safe_target_set(combined)
            new_targets = targets - source_targets
            charged_geometry = geometry_work if name in ("ISOTROPIC", "WEAK") else 0
            row = {
                **metrics,
                "applicable_geometry": applicable,
                "arm": name,
                "arm_callback_work": arm_work,
                "case_index": index,
                "charged_geometry_callback_work": charged_geometry,
                "common_source_callback_work": source_work,
                "family_id": case["family_id"],
                "formal_case_id": case["formal_case_id"],
                "headroom": headroom,
                "instance_id": case["instance_id"],
                "new_target_count": len(new_targets),
                "new_target_ids": sorted(new_targets),
                "source_safe_full": source_metrics["assessor_safe_full"],
                "source_target_count": len(source_targets),
                "target_count": int(case["target_count"]),
                "terminal_case_total_callback_work": source_work + charged_geometry + arm_work,
            }
            case_rows.append(row)
            terminal_by_arm[name] = row

            by_work: dict[int, dict[str, Any]] = {}
            for budget in INCREMENTAL_WORK:
                allowance = max(0, budget - charged_geometry)
                selected_arm = _completed_within(attempts, allowance)
                selected = list(source_attempts) + selected_arm
                budget_metrics = _metrics_row(selected, case)
                checkpoint = {
                    **budget_metrics,
                    "applicable_geometry": applicable,
                    "arm": name,
                    "arm_attempts_completed": len(selected_arm),
                    "arm_callback_allowance": allowance,
                    "arm_callback_work_completed": sum(
                        common._observed(item) for item in selected_arm
                    ),
                    "case_index": index,
                    "case_total_callback_checkpoint": source_work + budget,
                    "charged_geometry_callback_work": charged_geometry,
                    "common_source_callback_work": source_work,
                    "family_id": case["family_id"],
                    "headroom": headroom,
                    "incremental_callback_budget": budget,
                    "target_count": int(case["target_count"]),
                }
                checkpoint_rows.append(checkpoint)
                by_work[budget] = checkpoint
            checkpoint_by_arm[name] = by_work

        geometry_charge = {
            "CONTINUATION": 0,
            "ISOTROPIC": geometry_work,
            "WEAK": geometry_work,
        }
        expected_ledger = {
            "geometry_observed_callbacks": geometry_work,
            "geometry_reported_callbacks": geometry_work,
            "geometry_charge_by_arm": geometry_charge,
            "source_common_observed_callbacks": source_work,
            "charged_total_callback_work_by_arm": {
                name: source_work
                + geometry_charge[name]
                + terminal_by_arm[name]["arm_callback_work"]
                for name in ARMS
            },
        }
        if shard.get("work_ledger") != expected_ledger:
            raise ValueError("raw work ledger differs from independent callback accounting")

        strict_win = headroom and any(
            checkpoint_by_arm["WEAK"][budget]["assessor_distinct_targets_found"]
            > max(
                checkpoint_by_arm["CONTINUATION"][budget][
                    "assessor_distinct_targets_found"
                ],
                checkpoint_by_arm["ISOTROPIC"][budget]["assessor_distinct_targets_found"],
            )
            for budget in INCREMENTAL_WORK
        )
        weak_terminal = terminal_by_arm["WEAK"]
        terminal_noninferior = (not headroom) or (
            weak_terminal["assessor_distinct_targets_found"]
            >= max(
                terminal_by_arm["CONTINUATION"]["assessor_distinct_targets_found"],
                terminal_by_arm["ISOTROPIC"]["assessor_distinct_targets_found"],
            )
            and int(bool(weak_terminal["assessor_safe_full"]))
            >= max(
                int(bool(terminal_by_arm["CONTINUATION"]["assessor_safe_full"])),
                int(bool(terminal_by_arm["ISOTROPIC"]["assessor_safe_full"])),
            )
        )
        case_state.append(
            {
                "applicable": applicable,
                "applicable_anchor_count": applicable_anchors,
                "case_index": index,
                "family_id": case["family_id"],
                "headroom": headroom,
                "strict_win": strict_win,
                "terminal_noninferior": terminal_noninferior,
            }
        )

    if len(revisions) != 1:
        raise ValueError("Stage-B shards came from different revisions")

    hard_kill_fields = (
        "assessor_false_or_unsafe",
        "assessor_ambiguity",
        "callback_cap_violations",
        "evaluation_count_mismatches",
        "exceptions",
        "reported_accepted_ambiguous",
        "reported_accepted_canonical_invalid",
        "reported_accepted_gold_inconsistent",
        "reported_accepted_numeric_target_only",
        "runner_budget_exhausted",
        "terminal_mismatches",
    )
    hard_kill = any(accounting[field] != 0 for field in hard_kill_fields)
    applicable_cases = [state for state in case_state if state["applicable"]]
    applicable_families = {state["family_id"] for state in applicable_cases}
    headroom_cases = [state for state in case_state if state["headroom"]]
    outside_family_headroom = any(
        state["family_id"] not in NON_GENERALIZATION_FAMILIES for state in headroom_cases
    )
    winning_cases = [state for state in case_state if state["strict_win"]]
    winning_families = {state["family_id"] for state in winning_cases}
    non_special_win = any(
        state["family_id"] not in NON_GENERALIZATION_FAMILIES for state in winning_cases
    )
    terminal_noninferior = all(state["terminal_noninferior"] for state in headroom_cases)
    signal = (
        not hard_kill
        and bool(headroom_cases)
        and outside_family_headroom
        and len(applicable_cases) >= 4
        and len(applicable_families) >= 3
        and len(winning_cases) >= 2
        and len(winning_families) >= 2
        and non_special_win
        and terminal_noninferior
    )
    decision = (
        "HARD_KILL"
        if hard_kill
        else "NO_HEADROOM"
        if not headroom_cases
        else "INCONCLUSIVE_NO_HEADROOM"
        if not outside_family_headroom
        else "FAVORABLE_SIGNAL_ONLY_NONPROMOTIONAL"
        if signal
        else "FROZEN_DESIGN_NEGATIVE"
    )

    return {
        "accounting": dict(sorted(accounting.items())),
        "authorization_sha256": authorization_sha,
        "case_rows": case_rows,
        "case_signal_rows": case_state,
        "checkpoint_rows": checkpoint_rows,
        "decision": {
            "applicable_case_count": len(applicable_cases),
            "applicable_family_count": len(applicable_families),
            "hard_kill": hard_kill,
            "headroom_case_count": len(headroom_cases),
            "outside_family_headroom": outside_family_headroom,
            "non_tangent_multiroot_strict_win": non_special_win,
            "nonpromotional": True,
            "formal_progression_authorized": signal,
            "replacement_preregistration_permitted": (
                decision == "INCONCLUSIVE_NO_HEADROOM"
            ),
            "rejection_scope": (
                "this frozen one-replicate mechanism design only"
                if decision == "FROZEN_DESIGN_NEGATIVE"
                else None
            ),
            "signal": signal,
            "status": decision,
            "strict_win_case_count": len(winning_cases),
            "strict_win_family_count": len(winning_families),
            "terminal_noninferior_all_headroom_cases": terminal_noninferior,
        },
        "experiment_id": EXPERIMENT,
        "input_manifest_sha256": input_sha,
        "lab_confirmation": False,
        "lab_confirmation_512_768": False,
        "revision": revisions.pop(),
        "schema_version": OUTPUT_SCHEMA,
        "stage": "stage-b-t0",
    }


def _artifact_maps(
    input_document: dict[str, Any],
    shards: Sequence[dict[str, Any]],
    repo_root: Path,
) -> tuple[
    dict[int, tuple[dict[str, Any], str]],
    dict[int, tuple[dict[str, Any], str]],
]:
    proposals: dict[int, tuple[dict[str, Any], str]] = {}
    prearms: dict[int, tuple[dict[str, Any], str]] = {}
    for case in input_document["cases"]:
        index = int(case["case_index"])
        path = _load_relative(repo_root, case["proposal"]["path"], "D0 proposal")
        proposals[index] = (json.loads(path.read_text(encoding="utf-8")), sha256(path))
    for shard in shards:
        index = int(shard["case_index"])
        binding = shard.get("prearm", {})
        path = _load_relative(repo_root, binding.get("path"), "pre-arm artifact")
        observed_sha = sha256(path)
        if observed_sha != binding.get("sha256"):
            raise ValueError("pre-arm file hash differs")
        prearms[index] = (json.loads(path.read_text(encoding="utf-8")), observed_sha)
    return proposals, prearms


def _validate_file_authority(
    input_document: dict[str, Any],
    authorization: dict[str, Any],
    input_path: Path,
    repo_root: Path,
) -> None:
    input_binding = authorization.get("input_manifest", {})
    bound_input = _load_relative(repo_root, input_binding.get("path"), "authorized input")
    if bound_input != input_path.resolve() or sha256(bound_input) != input_binding.get("sha256"):
        raise ValueError("authorization input path/hash differs")
    prereg_binding = input_document["preregistration"]
    prereg_path = _load_relative(repo_root, prereg_binding.get("path"), "preregistration")
    if sha256(prereg_path) != prereg_binding.get("sha256"):
        raise ValueError("input preregistration file hash differs")
    if authorization.get("preregistration", {}).get("path") != prereg_binding.get("path"):
        raise ValueError("authorization preregistration path differs")
    runner = Path(__file__).resolve().with_name("run_stageb_t0.jl")
    if sha256(runner) != authorization.get("runner_source_sha256"):
        raise ValueError("authorization runner source hash differs from the repository")
    for relative, expected in authorization["dependency_source_sha256"].items():
        dependency = _load_relative(repo_root, relative, "authorized dependency")
        if sha256(dependency) != expected:
            raise ValueError(f"authorized dependency hash differs: {relative}")
    bindings: list[dict[str, Any]] = []
    for key in ("local_freeze", "source_manifest", "stagea_decision"):
        value = input_document.get(key)
        if isinstance(value, dict):
            bindings.append(value)
    weak = input_document.get("weak_geometry")
    if isinstance(weak, dict):
        bindings.extend(value for value in weak.values() if isinstance(value, dict))
    for binding in bindings:
        path = _load_relative(repo_root, binding.get("path"), "input source binding")
        if sha256(path) != binding.get("sha256"):
            raise ValueError("input source binding hash differs")


def aggregate_files(
    input_path: Path, authorization_path: Path, shard_paths: Sequence[Path]
) -> dict[str, Any]:
    input_document = json.loads(input_path.read_text(encoding="utf-8"))
    authorization = json.loads(authorization_path.read_text(encoding="utf-8"))
    shards = [json.loads(path.read_text(encoding="utf-8")) for path in shard_paths]
    repo_root = Path(__file__).resolve().parents[3]
    _validate_file_authority(input_document, authorization, input_path, repo_root)
    input_relative = input_path.resolve().relative_to(repo_root.resolve()).as_posix()
    auth_relative = authorization_path.resolve().relative_to(repo_root.resolve()).as_posix()
    for shard in shards:
        if shard.get("input_manifest", {}).get("path") != input_relative or shard.get(
            "authorization", {}
        ).get("path") != auth_relative:
            raise ValueError("raw shard input/authorization path binding differs")
    proposals, prearms = _artifact_maps(input_document, shards, repo_root)
    return aggregate_documents(
        input_document,
        authorization,
        shards,
        input_sha=sha256(input_path),
        authorization_sha=sha256(authorization_path),
        aggregator_sha=sha256(Path(__file__)),
        proposal_documents=proposals,
        prearm_documents=prearms,
    )


def self_test() -> dict[str, Any]:
    families = (
        "CURVED-CHAIN",
        "CURVED-CHAIN",
        "NEAR-RANK-DEFICIENT",
        "NEAR-RANK-DEFICIENT",
        "TANGENT-CIRCLE-LINE",
        "TANGENT-CIRCLE-LINE",
        "MULTIROOT-WARPED",
        "MULTIROOT-WARPED",
    )

    def bits(value: float) -> str:
        return struct.pack(">d", value).hex()

    def proposal(case_index: int) -> tuple[dict[str, Any], dict[str, Any]]:
        coordinates = [
            [bits(-0.9 + 0.01 * ((case_index + column) % 100)), bits(0.25)]
            for column in range(1, 129)
        ]
        document: dict[str, Any] = {
            "authority_sha256": "a" * 64,
            "column_count": 128,
            "coordinate_float64_bits_by_column": coordinates,
            "dimension": 2,
            "lane_schedule": ["iid"] * 128,
            "metadata": {"truth_fields_visible": False},
            "method": "D0-IID-ALL",
            "replicate_seed": str(case_index),
            "schema_version": PROPOSAL_SCHEMA,
            "source_columns": list(range(1, 129)),
            "unit_float64_bits_by_column": [
                [bits(0.1 + 0.001 * column), bits(0.25)] for column in range(128)
            ],
        }
        document["sha256"] = _digest_document(document)
        file_sha = _digest_document({"fixture_file": case_index})
        binding = {
            "artifact_sha256": document["sha256"],
            "continuation_columns": [65, 128],
            "continuation_sha256": _slice_digest(
                document["sha256"],
                65,
                128,
                coordinates,
                document["lane_schedule"],
                document["source_columns"],
            ),
            "file_sha256": file_sha,
            "initial_prefix_columns": [1, 64],
            "initial_prefix_sha256": _slice_digest(
                document["sha256"],
                1,
                64,
                coordinates,
                document["lane_schedule"],
                document["source_columns"],
            ),
            "lane_schedule": "all-iid",
            "maximum_prefix_sha256": document["sha256"],
            "method": "D0-IID-ALL",
            "path": f"fixture/proposal-{case_index}.json",
            "replicate": 1,
            "replicate_seed": str(case_index),
            "truth_free_metadata": True,
        }
        return document, binding

    proposal_documents: dict[int, tuple[dict[str, Any], str]] = {}
    cases: list[dict[str, Any]] = []
    for index, family in enumerate(families, start=1):
        document, binding = proposal(index)
        proposal_documents[index] = (document, binding["file_sha256"])
        cases.append(
            {
                "case_index": index,
                "configuration_count": 2,
                "dimension": 2,
                "family_id": family,
                "formal_case_id": f"B-{index:03d}",
                "instance_id": f"instance-{index}",
                "parameters": {},
                "proposal": binding,
                "residual_dimension": 2,
                "source": {
                    "index": index,
                    "parameters_sha256": "b" * 64,
                    "path": "fixture/source.json",
                    "replay_checksum": hashlib.sha256(f"replay-{index}".encode()).hexdigest(),
                },
                "strata": ["S1"],
                "target_count": 2,
            }
        )
    manifest = {
        "schema_version": INPUT_SCHEMA,
        "experiment_id": EXPERIMENT,
        "stage": "stage-b-weak-geometry-t0",
        "cases": cases,
        "prefixes": {"initial": [1, 64], "continuation": [65, 128], "maximum": 128},
        "lab_confirmation_512_768": False,
        "nonpromotional_t0": True,
        "preregistration": {"path": "fixture/prereg.json", "sha256": "c" * 64},
    }
    authorization = {
        "schema_version": AUTH_SCHEMA,
        "outcome_execution_authorized": True,
        "nonpromotional_t0": True,
        "input_manifest": {"sha256": "input"},
        "preregistration": {"sha256": "c" * 64},
        "runner_source_sha256": "d" * 64,
        "aggregator_source_sha256": "e" * 64,
        "dependency_source_sha256": {"fixture/dependency": "f" * 64},
    }

    def attempt(
        index: int,
        start_bits: list[str],
        *,
        target: str | None = None,
        endpoint: list[float] | None = None,
    ) -> dict[str, Any]:
        start = [struct.unpack(">d", bytes.fromhex(value))[0] for value in start_bits]
        hit = target is not None
        return {
            "variant": "fixture",
            "start_index": index,
            "start": start,
            "endpoint": endpoint,
            "assessor_qualified": hit,
            "assessor_gold_matched": hit,
            "assessor_target_ambiguous": False,
            "assessor_numeric_target_matched": hit,
            "assessor_matched_target_id": target,
            "assessor_matched_configuration": 1 if target == "A" else 2 if target == "B" else None,
            "observed_evaluations": 10,
            "reported_evaluations": 10,
            "evaluation_count_mismatch": False,
            "exception": None,
            "budget_exhausted": False,
        }

    def terminal(attempts: list[dict[str, Any]]) -> dict[str, Any]:
        return {
            "attempt_count": len(attempts),
            "callback_work": sum(common._observed(row) for row in attempts),
            "evaluation_count_mismatches": 0,
            "exceptions": 0,
            "runner_budget_exhausted": 0,
            "callback_cap_violations": 0,
        }

    prearm_documents: dict[int, tuple[dict[str, Any], str]] = {}
    shards: list[dict[str, Any]] = []
    for case in cases:
        index = case["case_index"]
        proposal_doc = proposal_documents[index][0]
        proposal_bits = proposal_doc["coordinate_float64_bits_by_column"]
        source_attempts = [
            attempt(
                ordinal,
                proposal_bits[ordinal - 1],
                target="A" if ordinal == 1 else None,
                endpoint=[0.0, 0.0] if ordinal == 1 else None,
            )
            for ordinal in range(1, 65)
        ]
        continuation = copy.deepcopy(proposal_bits[64:128])
        weak = copy.deepcopy(continuation)
        isotropic = copy.deepcopy(continuation)
        quartet = [
            [bits(0.25), bits(0.0)],
            [bits(-0.25), bits(0.0)],
            [bits(0.0), bits(0.25)],
            [bits(0.0), bits(-0.25)],
        ]
        weak[1], weak[2] = quartet[0], quartet[1]
        isotropic[1], isotropic[2] = quartet[2], quartet[3]
        schedule: list[dict[str, Any]] = []
        for slot in range(1, 65):
            if (slot - 1) % 4 == 0:
                lane = "iid"
            elif slot in (2, 3):
                lane = "geometry"
            else:
                lane = "continuation"
            entry: dict[str, Any] = {
                "slot": slot,
                "lane": lane,
                "source_column": None if lane == "geometry" else 64 + slot,
                "generation": 1 if lane == "geometry" else 0,
                "parent_generation": 0 if lane == "geometry" else None,
                "derived_from_probe": lane == "geometry",
            }
            if lane == "geometry":
                entry.update(
                    global_comparison_index=1,
                    local_comparison_index=1,
                    parent_source_index=1,
                    point_ordinal=1 if slot == 2 else 2,
                    sign=1 if slot == 2 else -1,
                    radius=0.25,
                )
            schedule.append(entry)
        plan = {
            "status": "applicable",
            "reason": "stable_weak_geometry",
            "callback_count": 10,
            "generation": 0,
            "maximum_comparisons": 24,
            "source_index": 1,
            "quartet_count": 1,
        }
        quartet_document = {
            "anchor_float64_bits": [bits(0.0), bits(0.0)],
            "global_comparison_index": 1,
            "isotropic_direction_float64_bits": [bits(0.0), bits(1.0)],
            "local_comparison_index": 1,
            "normalized_float64_bits_by_column": quartet,
            "parent_generation": 0,
            "parent_source_index": 1,
            "radius": 0.25,
            "physical_float64_bits_by_column": quartet,
            "weak_direction_float64_bits": [bits(1.0), bits(0.0)],
        }
        matrices = []
        for name, matrix in zip(ARMS, (continuation, isotropic, weak), strict=True):
            matrices.append(
                {
                    "name": name,
                    "matrix_sha256": _matrix_digest(matrix, 2),
                    "coordinate_float64_bits_by_column": matrix,
                }
            )
        prearm = {
            "schema_version": PREARM_SCHEMA,
            "truth_free": True,
            "experiment_id": EXPERIMENT,
            "stage": "stage-b-t0",
            "dimension": 2,
            "column_count": 64,
            "arm_order": list(ARMS),
            "input_manifest_sha256": "input",
            "preregistration": {"path": "fixture/prereg.json", "sha256": "c" * 64},
            "source_artifact": {
                field: case["proposal"][field]
                for field in ("artifact_sha256", "continuation_sha256", "file_sha256", "path")
            },
            "bounds": {
                "lower_float64_bits": [bits(-1.0), bits(-1.0)],
                "upper_float64_bits": [bits(1.0), bits(1.0)],
            },
            "geometry": {
                "anchor_count": 1,
                "callback_count": 10,
                "quartet_count": 1,
                "quartets": [quartet_document],
                "quartet_provenance_sha256": _runner_digest([quartet_document]),
            },
            "schedule": schedule,
            "schedule_sha256": _runner_digest(schedule),
            "arm_matrices": matrices,
        }
        prearm_sha = _digest_document({"prearm_fixture": index})
        prearm_documents[index] = (prearm, prearm_sha)
        arms = []
        for name, matrix in zip(ARMS, (continuation, isotropic, weak), strict=True):
            win = name == "WEAK" and index in (1, 3)
            arm_attempts = [
                attempt(
                    ordinal,
                    matrix[ordinal - 1],
                    target="B" if win and ordinal == 2 else None,
                )
                for ordinal in range(1, 65)
            ]
            arms.append(
                {
                    "name": name,
                    "matrix_sha256": _matrix_digest(matrix, 2),
                    "attempts": arm_attempts,
                    "terminal": terminal(arm_attempts),
                }
            )
        geometry_attempt = attempt(1, proposal_bits[0])
        geometry_attempt["observed_evaluations"] = 10
        geometry_attempt["reported_evaluations"] = 10
        geometry_attempt["reported_accepted"] = False
        geometry_attempt["reported_converged"] = False
        geometry_attempt["status"] = "STAGEB_GEOMETRY_ONLY"
        shards.append(
            {
                "schema_version": RAW_SCHEMA,
                "experiment_id": EXPERIMENT,
                "stage": "stage-b-t0",
                "partition": "development",
                "case_index": index,
                "lab_confirmation_512_768": False,
                "nonpromotional_t0": True,
                "input_manifest": {"sha256": "input"},
                "authorization": {"sha256": "authorization"},
                "preregistration": {"sha256": "c" * 64},
                "revision": {"git_head": "fixture", "git_dirty": False},
                "thread_contract": {
                    "julia_threads": 1,
                    "blas_threads": 1,
                    "solver_worker_count": 1,
                    "case_process_limit": 8,
                    "assigned_cpu": index - 1,
                    "cpus_allowed_list": str(index - 1),
                    "environment": {
                        "JULIA_NUM_THREADS": "1",
                        "OPENBLAS_NUM_THREADS": "1",
                        "OMP_NUM_THREADS": "1",
                        "MKL_NUM_THREADS": "1",
                    },
                },
                "case_manifest": {
                    **{field: case[field] for field in (
                        "case_index", "configuration_count", "dimension", "family_id",
                        "formal_case_id", "instance_id", "residual_dimension", "target_count",
                    )},
                    "source_replay_checksum": case["source"]["replay_checksum"],
                },
                "source": {
                    "proposal": case["proposal"],
                    "attempts": source_attempts,
                    "terminal": terminal(source_attempts),
                },
                "geometry": {
                    "attempt": geometry_attempt,
                    "callback_count": 10,
                    "anchor_count": 1,
                    "applicable_anchor_count": 1,
                    "quartet_count": 1,
                    "reasons": {"stable_weak_geometry": 1},
                    "plans": [plan],
                },
                "prearm": {
                    "path": f"fixture/prearm-{index}.json",
                    "sha256": prearm_sha,
                    "schedule_sha256": prearm["schedule_sha256"],
                    "quartet_provenance_sha256": prearm["geometry"][
                        "quartet_provenance_sha256"
                    ],
                },
                "arm_order": list(ARMS),
                "arms": arms,
                "work_ledger": {
                    "geometry_observed_callbacks": 10,
                    "geometry_reported_callbacks": 10,
                    "geometry_charge_by_arm": {
                        "CONTINUATION": 0,
                        "ISOTROPIC": 10,
                        "WEAK": 10,
                    },
                    "source_common_observed_callbacks": 640,
                    "charged_total_callback_work_by_arm": {
                        "CONTINUATION": 1_280,
                        "ISOTROPIC": 1_290,
                        "WEAK": 1_290,
                    },
                },
            }
        )

    clean = aggregate_documents(
        manifest,
        authorization,
        list(reversed(shards)),
        input_sha="input",
        authorization_sha="authorization",
        aggregator_sha="e" * 64,
        proposal_documents=proposal_documents,
        prearm_documents=prearm_documents,
    )
    assert clean["decision"]["status"] == "FAVORABLE_SIGNAL_ONLY_NONPROMOTIONAL"
    assert all(clean["accounting"][field] == 0 for field in (
        "assessor_false_or_unsafe", "callback_cap_violations", "evaluation_count_mismatches",
        "exceptions", "runner_budget_exhausted", "terminal_mismatches",
    ))

    def detected(mutator) -> bool:
        bad_shards = copy.deepcopy(shards)
        bad_prearms = copy.deepcopy(prearm_documents)
        mutator(bad_shards, bad_prearms)
        try:
            aggregate_documents(
                manifest,
                authorization,
                bad_shards,
                input_sha="input",
                authorization_sha="authorization",
                aggregator_sha="e" * 64,
                proposal_documents=proposal_documents,
                prearm_documents=bad_prearms,
            )
        except (ValueError, KeyError, StopIteration):
            return True
        return False

    start_tamper = detected(
        lambda raw, pre: raw[0]["source"]["attempts"][0].__setitem__("start", [0.9, 0.9])
    )
    def alter_pairing(raw, pre) -> None:
        entry = pre[1][0]["arm_matrices"][2]
        entry["coordinate_float64_bits_by_column"][1] = [bits(0.75), bits(0.75)]
        entry["matrix_sha256"] = _matrix_digest(
            entry["coordinate_float64_bits_by_column"], 2
        )
        raw[0]["arms"][2]["matrix_sha256"] = entry["matrix_sha256"]

    pairing_tamper = detected(alter_pairing)

    def alter_quartet_math(raw, pre) -> None:
        artifact = pre[1][0]
        artifact["geometry"]["quartets"][0]["weak_direction_float64_bits"] = [
            bits(0.0), bits(1.0)
        ]
        digest = _runner_digest(artifact["geometry"]["quartets"])
        artifact["geometry"]["quartet_provenance_sha256"] = digest
        raw[0]["prearm"]["quartet_provenance_sha256"] = digest

    quartet_math_tamper = detected(alter_quartet_math)
    recursive_tamper = detected(
        lambda raw, pre: raw[0]["geometry"]["plans"][0].__setitem__("generation", 1)
    )
    geometry_answer_tamper = detected(
        lambda raw, pre: raw[0]["geometry"]["attempt"].__setitem__(
            "reported_accepted", True
        )
    )
    iid_tamper = detected(
        lambda raw, pre: pre[1][0]["schedule"][0].__setitem__("lane", "continuation")
    )
    unsafe_shards = copy.deepcopy(shards)
    unsafe = unsafe_shards[0]["source"]["attempts"][0]
    unsafe.update(reported_accepted=True, canonical_valid=False, gold_matched=False)
    unsafe_result = aggregate_documents(
        manifest,
        authorization,
        unsafe_shards,
        input_sha="input",
        authorization_sha="authorization",
        aggregator_sha="e" * 64,
        proposal_documents=proposal_documents,
        prearm_documents=prearm_documents,
    )
    safety_hard_kill = unsafe_result["decision"]["status"] == "HARD_KILL"
    runner_float_digest = _runner_digest(
        [{"radius": 2.0**-20}, {"radius": 2.0**-14}]
    ) == "647c497dd63b506bc75203f1bb187e0305617da3ff055fa0d0e685f67add7275"
    assert (
        start_tamper
        and pairing_tamper
        and quartet_math_tamper
        and geometry_answer_tamper
        and recursive_tamper
        and iid_tamper
        and safety_hard_kill
        and runner_float_digest
    )
    return {
        "aggregate_success": True,
        "fixture_answer_attempt_count": CASE_COUNT * (SOURCE_ATTEMPTS + len(ARMS) * ARM_ATTEMPTS),
        "iid_tamper_detected": iid_tamper,
        "geometry_answer_tamper_detected": geometry_answer_tamper,
        "normal_signal": True,
        "outcomes_executed": False,
        "pairing_tamper_detected": pairing_tamper,
        "quartet_math_tamper_detected": quartet_math_tamper,
        "recursive_tamper_detected": recursive_tamper,
        "runner_float_digest_matched": runner_float_digest,
        "safety_hard_kill_detected": safety_hard_kill,
        "schema_version": SELF_TEST_SCHEMA,
        "start_bit_tamper_detected": start_tamper,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--input-manifest", type=Path)
    parser.add_argument("--authorization", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("shards", nargs="*", type=Path)
    args = parser.parse_args()
    if args.self_test:
        if args.input_manifest or args.authorization or args.output or args.shards:
            parser.error("--self-test is mutually exclusive with aggregation paths")
        print(canonical_json(self_test()))
        return
    if (
        args.input_manifest is None
        or args.authorization is None
        or args.output is None
        or len(args.shards) != CASE_COUNT
    ):
        parser.error("aggregation requires input/auth/output and exactly eight raw shards")
    result = aggregate_files(args.input_manifest, args.authorization, args.shards)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(canonical_json(result) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
