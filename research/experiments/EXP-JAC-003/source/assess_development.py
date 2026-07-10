"""Result-owning EXP-JAC-003 development safety and ABBA assessor.

This module is frozen before any safety, K0, Gold, timing or candidate outcome is
opened.  Candidate execution never imports it.  It uses only Python's standard
library and joins distinct owners by opaque_case_id plus saved start_index.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import math
import random
import statistics
from collections import defaultdict
from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Any


CARD_ID = "EXP-JAC-003"
SAFETY_SCHEMA = "exp-jac-003-candidate-safety/v1"
TRACE_SCHEMA = "exp-jac-003-segment-trace/v1"
RUN_SCHEMA = "exp-jac-003-formal-abba-run/v1"
SUMMARY_SCHEMA = "exp-jac-003-development-summary/v1"
ABBA = (
    "K0-DENSE-PUBLIC",
    "K1-CACHED-ROUTED",
    "K1-CACHED-ROUTED",
    "K0-DENSE-PUBLIC",
)
ELIGIBLE_FAMILIES = (
    "JAC3-TRIG-TREE",
    "JAC3-RATIONAL-HYPERGRAPH",
    "JAC3-HEX-RING-STENCIL",
)
DENSE_FAMILY = "JAC3-DENSE-BRANCH-CONTROL"
CANONICAL_RESIDUAL_TOLERANCE = 1.0e-8
GOLD_CONFIGURATION_TOLERANCE = 1.0e-5
GOLD_TARGET_TOLERANCE = 1.0e-6
DENSE_COLOR_ATOL = 1.0e-10
DENSE_COLOR_RTOL = 1.0e-10
DENSE_ANALYTIC_ATOL = 2.0e-5
DENSE_ANALYTIC_RTOL = 2.0e-5
BOOTSTRAP_REPLICATES = 20_000
PROVIDER_FIELDS = ["groups", "row_supports", "structural_nonzeros"]
ROUTE_FIELDS = [
    "color_count",
    "residual_count",
    "structural_nonzeros",
    "variable_count",
]
K0_EXACT_FIELDS = (
    "status",
    "accepted",
    "final",
    "iterations",
    "evaluations",
    "numerical_rank",
    "condition_estimate",
    "final_residual_infinity",
    "observation_status",
    "branch_keys",
    "jacobian_events",
    "trace",
)


class AssessmentError(RuntimeError):
    """A malformed or provenance-invalid formal artifact."""


def _read_file(path: Path) -> bytes:
    return path.read_bytes()


def _uncompressed_bytes(path: Path) -> bytes:
    payload = _read_file(path)
    return gzip.decompress(payload) if path.suffix == ".gz" else payload


def _load(path: Path) -> Any:
    return json.loads(_uncompressed_bytes(path))


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _canonical(value: Any) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def _require(condition: bool, detail: str) -> None:
    if not condition:
        raise AssessmentError(detail)


def _finite_float(value: Any, label: str) -> float:
    _require(isinstance(value, float), f"{label} type")
    result = value
    _require(math.isfinite(result), f"{label} nonfinite")
    return result


def _exact_int(value: Any, label: str) -> int:
    _require(not isinstance(value, bool) and isinstance(value, int), f"{label} type")
    return value


def _artifact(
    path: Path,
    descriptor: dict[str, Any],
    label: str,
) -> Any:
    compressed = _read_file(path)
    raw = gzip.decompress(compressed)
    _require(
        _sha256(compressed) == descriptor["compressed_sha256"],
        f"{label} compressed hash",
    )
    _require(_sha256(raw) == descriptor["uncompressed_sha256"], f"{label} raw hash")
    _require(
        len(compressed) == descriptor["compressed_bytes"], f"{label} compressed size"
    )
    _require(len(raw) == descriptor["uncompressed_bytes"], f"{label} raw size")
    return json.loads(raw)


def _matrix(document: dict[str, Any], label: str) -> list[list[float]]:
    shape = document.get("shape")
    _require(isinstance(shape, list) and len(shape) == 2, f"{label} shape")
    rows = _exact_int(shape[0], f"{label} rows")
    columns = _exact_int(shape[1], f"{label} columns")
    _require(rows > 0 and columns > 0, f"{label} positive shape")
    matrix = [[0.0] * columns for _ in range(rows)]
    seen: set[tuple[int, int]] = set()
    entries = document.get("entries")
    _require(isinstance(entries, list), f"{label} entries")
    for offset, entry in enumerate(entries):
        _require(isinstance(entry, list) and len(entry) == 3, f"{label} entry {offset}")
        row = _exact_int(entry[0], f"{label} row")
        column = _exact_int(entry[1], f"{label} column")
        _require(0 <= row < rows and 0 <= column < columns, f"{label} entry range")
        _require((row, column) not in seen, f"{label} duplicate entry")
        seen.add((row, column))
        matrix[row][column] = _finite_float(entry[2], f"{label} value")
    return matrix


def _analytic_matrix(trace: dict[str, Any], label: str) -> list[list[float]]:
    return _matrix({"shape": trace["shape"], "entries": trace["entries"]}, label)


def _entry_mismatches(
    left: Sequence[Sequence[float]],
    right: Sequence[Sequence[float]],
    *,
    atol: float,
    rtol: float,
    scale_right_only: bool,
) -> int:
    if len(left) != len(right) or any(
        len(a) != len(b) for a, b in zip(left, right, strict=True)
    ):
        return 1
    count = 0
    for left_row, right_row in zip(left, right, strict=True):
        for left_value, right_value in zip(left_row, right_row, strict=True):
            if not (math.isfinite(left_value) and math.isfinite(right_value)):
                count += 1
                continue
            scale = (
                abs(right_value)
                if scale_right_only
                else max(abs(left_value), abs(right_value))
            )
            if abs(left_value - right_value) > atol + rtol * scale:
                count += 1
    return count


def _analytic_mismatch(
    dense: Sequence[Sequence[float]], analytic: Sequence[Sequence[float]]
) -> int:
    if len(dense) != len(analytic) or any(
        len(a) != len(b) for a, b in zip(dense, analytic, strict=True)
    ):
        return 1
    errors: list[float] = []
    scales: list[float] = []
    for dense_row, analytic_row in zip(dense, analytic, strict=True):
        for dense_value, analytic_value in zip(dense_row, analytic_row, strict=True):
            if not (math.isfinite(dense_value) and math.isfinite(analytic_value)):
                return 1
            errors.append(abs(dense_value - analytic_value))
            scales.append(abs(analytic_value))
    tolerance = DENSE_ANALYTIC_ATOL + DENSE_ANALYTIC_RTOL * max(scales, default=0.0)
    return int(max(errors, default=0.0) > tolerance)


def _index_by(
    items: Iterable[dict[str, Any]], key: str, label: str
) -> dict[Any, dict[str, Any]]:
    result: dict[Any, dict[str, Any]] = {}
    for item in items:
        identity = item[key]
        _require(identity not in result, f"duplicate {label} {identity}")
        result[identity] = item
    return result


def assess_safety(safety: dict[str, Any], truth: dict[str, Any]) -> dict[str, Any]:
    _require(safety.get("schema_version") == SAFETY_SCHEMA, "safety schema")
    _require(safety.get("case_count") == 64, "safety case count")
    _require(safety.get("starts_per_case") == 32, "safety start count")
    truth_cases = _index_by(truth["assessments"], "opaque_case_id", "truth case")
    safety_cases = _index_by(safety["cases"], "opaque_case_id", "safety case")
    _require(set(safety_cases) == set(truth_cases), "safety/truth case join")
    counts = {
        "dense_colored_mismatch_count": 0,
        "dense_analytic_mismatch_count": 0,
        "outside_support_nonzero_count": 0,
        "safety_failure_status_count": 0,
        "incomplete_pattern_undetected_count": 0,
        "fallback_coverage_failure_count": 0,
    }
    case_provider_hashes: dict[str, str] = {}
    case_route_hashes: dict[str, str] = {}
    for opaque_id in sorted(truth_cases):
        truth_case = truth_cases[opaque_id]
        safety_case = safety_cases[opaque_id]
        analytic = _index_by(
            truth_case["analytic_jacobian_traces"],
            "start_index",
            f"analytic {opaque_id}",
        )
        starts = safety_case["starts"]
        _require(len(starts) == 32, f"safety starts {opaque_id}")
        row_supports = safety_case["row_supports"]
        case_provider_hashes[opaque_id] = safety_case["provider_projection_hash"]
        case_route_hashes[opaque_id] = safety_case["route_projection_hash"]
        for expected_index, record in enumerate(starts):
            _require(
                record["start_index"] == expected_index,
                f"safety start order {opaque_id}",
            )
            dense = _matrix(record["dense"], f"dense {opaque_id}/{expected_index}")
            colored = _matrix(
                record["colored"], f"colored {opaque_id}/{expected_index}"
            )
            analytic_matrix = _analytic_matrix(
                analytic[expected_index], f"analytic {opaque_id}/{expected_index}"
            )
            counts["dense_colored_mismatch_count"] += _entry_mismatches(
                colored,
                dense,
                atol=DENSE_COLOR_ATOL,
                rtol=DENSE_COLOR_RTOL,
                scale_right_only=True,
            )
            counts["dense_analytic_mismatch_count"] += _analytic_mismatch(
                dense, analytic_matrix
            )
            counts["safety_failure_status_count"] += int(record["failure"] is not None)
            _require(
                len(row_supports) == len(colored[0]), f"support columns {opaque_id}"
            )
            for column, rows in enumerate(row_supports):
                support = set(rows)
                _require(len(support) == len(rows), f"support duplicate {opaque_id}")
                for row in range(len(colored)):
                    if row not in support and colored[row][column] != 0.0:
                        counts["outside_support_nonzero_count"] += 1

    negatives = _index_by(
        safety["incomplete_pattern_controls"], "opaque_case_id", "KNEG case"
    )
    _require(set(negatives) == set(truth_cases), "KNEG case join")
    for opaque_id, record in negatives.items():
        dense = _matrix(record["dense"], f"KNEG dense {opaque_id}")
        colored = _matrix(record["colored"], f"KNEG colored {opaque_id}")
        mismatches = _entry_mismatches(
            colored,
            dense,
            atol=DENSE_COLOR_ATOL,
            rtol=DENSE_COLOR_RTOL,
            scale_right_only=True,
        )
        counts["incomplete_pattern_undetected_count"] += int(mismatches == 0)

    controls = _index_by(safety["fallback_controls"], "mode", "fallback mode")
    expected_modes = {"plus_invalid", "minus_invalid", "nonfinite", "length"}
    _require(set(controls) == expected_modes, "fallback mode allocation")
    for mode, record in controls.items():
        failed = record["failure"] is not None or record["evaluations"] != 6
        matrix = _matrix(record["matrix"], f"fallback {mode}")
        failed = failed or matrix != [[1.0, 0.0], [0.0, 1.0]]
        events = record["group_events"]
        failed = failed or len(events) != 1
        if len(events) == 1:
            event = events[0]
            failed = failed or not event["fallback"]
            failed = failed or event["columns"] != [1, 2]
            failed = failed or event["completed_fallback_columns"] != 2
            failed = failed or event["fallback_evaluations"] != 4
            failed = failed or event["grouped_evaluations"] != 2
        counts["fallback_coverage_failure_count"] += int(failed)
    return {
        "counts": counts,
        "provider_hashes": case_provider_hashes,
        "route_hashes": case_route_hashes,
        "passed": all(value == 0 for value in counts.values()),
    }


def _segment_cases(
    segment: dict[str, Any], slot: int, expected: str
) -> list[dict[str, Any]]:
    _require(segment.get("schema_version") == TRACE_SCHEMA, f"segment {slot} schema")
    _require(segment.get("variant") == expected, f"segment {slot} variant")
    _require(segment.get("case_count") == 64, f"segment {slot} case count")
    _require(segment.get("starts_per_case") == 32, f"segment {slot} starts")
    cases = segment["cases"]
    _require(len(cases) == 64, f"segment {slot} cases length")
    ids = [case["opaque_case_id"] for case in cases]
    _require(ids == sorted(ids) and len(set(ids)) == 64, f"segment {slot} case order")
    for ordinal, case in enumerate(cases, start=1):
        _require(case["case_ordinal"] == ordinal, f"segment {slot} case ordinal")
        _require(len(case["attempts"]) == 32, f"segment {slot} attempt count")
        _require(
            [attempt["start_index"] for attempt in case["attempts"]] == list(range(32)),
            f"segment {slot} start order",
        )
    return cases


def validate_run(
    run: dict[str, Any],
    segments: Sequence[dict[str, Any]],
    safety: dict[str, Any],
) -> dict[str, Any]:
    _require(run.get("schema_version") == RUN_SCHEMA, "formal run schema")
    _require(run.get("experiment_id") == CARD_ID, "formal run experiment")
    _require(run.get("sequence") == list(ABBA), "formal ABBA sequence")
    _require(run.get("atomically_published") is True, "formal atomic publication")
    _require(run.get("child_exit_codes") == [0, 0, 0, 0], "formal child exits")
    _require(run.get("fresh_process_count") == 4, "formal fresh process count")
    pids = run.get("child_pids")
    _require(isinstance(pids, list) and len(pids) == len(set(pids)) == 4, "formal PIDs")
    _require(run.get("fresh_writable_depot_count") == 4, "formal depot count")
    _require(run.get("host_contention_event_count") == 0, "formal host contention")
    _require(run.get("lease_loss_count") == 0, "formal lease loss")
    _require(run.get("staging_mismatch_count") == 0, "formal staging mismatch")
    _require(run.get("source_hash_mismatch_count") == 0, "formal source mismatch")
    _require(run.get("input_hash_mismatch_count") == 0, "formal input mismatch")
    _require(run.get("public_surface_drift_count") == 0, "formal public surface drift")
    _require(
        run.get("frozen_control_preflight_mismatch_count") == 0, "formal K0 preflight"
    )
    _require(len(segments) == 4, "formal segment count")
    cases_by_slot = [
        _segment_cases(segment, slot, ABBA[slot])
        for slot, segment in enumerate(segments)
    ]
    reference_ids = [case["opaque_case_id"] for case in cases_by_slot[0]]
    for slot, cases in enumerate(cases_by_slot[1:], start=1):
        _require(
            [case["opaque_case_id"] for case in cases] == reference_ids,
            f"segment {slot} pairing",
        )
    expected_candidate = run["candidate_input_uncompressed_sha256"]
    expected_manifest = run["julia_manifest_sha256"]
    expected_source = run["source_lock_sha256"]
    for slot, segment in enumerate(segments):
        _require(
            segment["candidate_input_sha256"] == expected_candidate,
            f"segment {slot} input",
        )
        _require(
            segment["manifest_sha256"] == expected_manifest, f"segment {slot} manifest"
        )
        _require(
            segment["source_lock_sha256"] == expected_source, f"segment {slot} source"
        )
        _require(segment["julia_threads"] == 1, f"segment {slot} Julia threads")

    safety_provider = {
        case["opaque_case_id"]: case["provider_projection_hash"]
        for case in safety["cases"]
    }
    safety_route = {
        case["opaque_case_id"]: case["route_projection_hash"]
        for case in safety["cases"]
    }
    counts = {
        "identity_routing_input_count": 0,
        "projection_ownership_failure_count": 0,
        "budget_overrun_count": 0,
        "route_formula_mismatch_count": 0,
        "route_dense_boundary_failure_count": 0,
    }
    for case_index, opaque_id in enumerate(reference_ids):
        k0_structures = [
            cases_by_slot[slot][case_index]["structure"] for slot in (0, 3)
        ]
        k1_structures = [
            cases_by_slot[slot][case_index]["structure"] for slot in (1, 2)
        ]
        counts["projection_ownership_failure_count"] += int(
            k0_structures[0]["compiler_projection_hash"]
            != k0_structures[1]["compiler_projection_hash"]
        )
        for structure in k0_structures:
            counts["identity_routing_input_count"] += int(
                structure["provider_field_names"] != []
                or structure["route_field_names"] != []
                or structure["route"] != "dense-public"
            )
        first = k1_structures[0]
        counts["projection_ownership_failure_count"] += int(
            first["provider_projection_hash"]
            != k1_structures[1]["provider_projection_hash"]
            or first["route_projection_hash"]
            != k1_structures[1]["route_projection_hash"]
            or first["provider_projection_hash"] != safety_provider[opaque_id]
            or first["route_projection_hash"] != safety_route[opaque_id]
        )
        for structure in k1_structures:
            counts["identity_routing_input_count"] += int(
                structure["provider_field_names"] != PROVIDER_FIELDS
                or structure["route_field_names"] != ROUTE_FIELDS
            )
            n = _exact_int(structure["variable_count"], "route n")
            m = _exact_int(structure["residual_count"], "route m")
            nnz = _exact_int(structure["structural_nonzeros"], "route nnz")
            colors = _exact_int(structure["color_count"], "route colors")
            expected_colored = (
                n > 0
                and m > 0
                and 0 <= nnz <= m * n
                and nnz >= colors
                and ((nnz == 0) == (colors == 0))
                and 0 <= colors < n
                and 40 * n * colors + 5 * nnz <= 32 * n * n
            )
            observed_colored = structure["route"] == "colored"
            counts["route_formula_mismatch_count"] += int(
                observed_colored != expected_colored
            )
            counts["route_dense_boundary_failure_count"] += int(
                5 * colors >= 4 * n and observed_colored
            )
        for slot in range(4):
            case = cases_by_slot[slot][case_index]
            counts["budget_overrun_count"] += case["budget_overrun_count"]
            counts["budget_overrun_count"] += case["post_deadline_callback_entry_count"]
    return {"cases_by_slot": cases_by_slot, "counts": counts}


def _k0_replay_count(
    cases_by_slot: Sequence[Sequence[dict[str, Any]]], frozen_k0: dict[str, Any]
) -> int:
    _require(
        frozen_k0.get("schema_version") == "exp-jac-003-k0-control-traces/v1",
        "K0 schema",
    )
    frozen_cases = _index_by(frozen_k0["cases"], "opaque_case_id", "frozen K0 case")
    mismatch = 0
    for slot in (0, 3):
        for case in cases_by_slot[slot]:
            expected = frozen_cases[case["opaque_case_id"]]["attempts"]
            observed = case["attempts"]
            if len(expected) != len(observed):
                mismatch += 1
                continue
            for expected_attempt, observed_attempt in zip(
                expected, observed, strict=True
            ):
                if expected_attempt["start_index"] != observed_attempt["start_index"]:
                    mismatch += 1
                    continue
                expected_view = {key: expected_attempt[key] for key in K0_EXACT_FIELDS}
                observed_view = {key: observed_attempt[key] for key in K0_EXACT_FIELDS}
                mismatch += int(_canonical(expected_view) != _canonical(observed_view))
    return mismatch


def _gold_valid(
    attempt: dict[str, Any], truth: dict[str, Any], candidate: dict[str, Any]
) -> tuple[bool, float | None, float | None]:
    if not attempt["started"] or not attempt["replay_completed_within_deadline"]:
        return False, None, None
    final = attempt["final"]
    gold = truth["gold_configuration"]
    scales = candidate["scales"]
    if not (
        isinstance(final, list)
        and len(final) == len(gold) == len(scales)
        and all(isinstance(value, float) and math.isfinite(value) for value in final)
        and all(
            isinstance(scale, float) and math.isfinite(scale) and scale > 0
            for scale in scales
        )
    ):
        return False, None, None
    configuration_error = max(
        abs((float(value) - float(expected)) / float(scale))
        for value, expected, scale in zip(final, gold, scales, strict=True)
    )
    target_error = abs(float(final[-1]) - float(truth["gold_target"]))
    canonical = (
        attempt["replay_status"] == "EVAL_OK"
        and attempt["replay_residual_count"] == candidate["residual_count"]
        and attempt["replay_residual_infinity"] is not None
        and math.isfinite(float(attempt["replay_residual_infinity"]))
        and float(attempt["replay_residual_infinity"]) <= CANONICAL_RESIDUAL_TOLERANCE
    )
    expected_branch = truth["gold_branch_label"]
    branch = expected_branch is None or attempt["replay_branch_keys"] == [
        expected_branch
    ]
    valid = (
        canonical
        and configuration_error <= GOLD_CONFIGURATION_TOLERANCE
        and target_error <= GOLD_TARGET_TOLERANCE
        and branch
    )
    return valid, configuration_error, target_error


def _mean(values: Sequence[float]) -> float:
    _require(bool(values), "empty metric")
    return statistics.fmean(values)


def _bootstrap_lower(values: Sequence[float], namespace: str) -> float:
    _require(bool(values), f"empty bootstrap {namespace}")
    seed = int.from_bytes(
        hashlib.sha256(namespace.encode("utf-8")).digest()[:16], "big"
    )
    rng = random.Random(seed)
    count = len(values)
    samples = sorted(
        statistics.fmean(values[rng.randrange(count)] for _ in range(count))
        for _ in range(BOOTSTRAP_REPLICATES)
    )
    index = math.floor(0.05 * BOOTSTRAP_REPLICATES)
    return samples[index]


def _stratum_labels(truth: dict[str, Any], route: str) -> set[str]:
    family = truth["family_id"]
    labels = {f"family:{family}", f"route:{route}"}
    for key, value in sorted(truth["factors"].items()):
        labels.add(f"family:{family}/factor:{key}={value}")
    branch = truth["gold_branch_label"]
    if branch is not None:
        labels.add(f"branch:{branch}")
        margin = abs(float(truth["gold_branch_margin"]))
        labels.add(
            "branch-margin:boundary" if margin <= 1.0e-7 else "branch-margin:interior"
        )
    return labels


def assess_metrics(
    cases_by_slot: Sequence[Sequence[dict[str, Any]]],
    truth_document: dict[str, Any],
    candidate_document: dict[str, Any],
    process_walls: Sequence[int],
) -> dict[str, Any]:
    truth_cases = _index_by(truth_document["assessments"], "opaque_case_id", "truth")
    candidate_cases = _index_by(
        candidate_document["cases"], "opaque_case_id", "candidate"
    )
    ids = [case["opaque_case_id"] for case in cases_by_slot[0]]
    _require(set(ids) == set(truth_cases) == set(candidate_cases), "metric case join")
    gold_by_slot: list[list[bool]] = [[] for _ in range(4)]
    stratum_gold: dict[str, list[list[bool]]] = defaultdict(
        lambda: [[] for _ in range(4)]
    )
    false_candidates = 0
    case_rows: list[dict[str, Any]] = []
    for case_index, opaque_id in enumerate(ids):
        truth = truth_cases[opaque_id]
        candidate = candidate_cases[opaque_id]
        route = cases_by_slot[1][case_index]["structure"]["route"]
        labels = _stratum_labels(truth, route)
        for slot in range(4):
            for attempt in cases_by_slot[slot][case_index]["attempts"]:
                valid, _, _ = _gold_valid(attempt, truth, candidate)
                gold_by_slot[slot].append(valid)
                for label in labels:
                    stratum_gold[label][slot].append(valid)
                if slot in (1, 2) and attempt["accepted"] and not valid:
                    false_candidates += 1
        walls = [
            float(cases_by_slot[slot][case_index]["charged_wall_ns"])
            for slot in range(4)
        ]
        works = [
            float(
                sum(
                    attempt["primal_equivalent_oracle_work"]
                    for attempt in cases_by_slot[slot][case_index]["attempts"]
                )
            )
            for slot in range(4)
        ]
        k0_wall = (walls[0] + walls[3]) / 2.0
        k1_wall = (walls[1] + walls[2]) / 2.0
        k0_work = (works[0] + works[3]) / 2.0
        k1_work = (works[1] + works[2]) / 2.0
        case_rows.append(
            {
                "opaque_case_id": opaque_id,
                "family_id": truth["family_id"],
                "k0_wall": k0_wall,
                "k1_wall": k1_wall,
                "wall_improvement": (k0_wall - k1_wall) / k0_wall,
                "k0_work": k0_work,
                "k1_work": k1_work,
                "work_reduction": (k0_work - k1_work) / k0_work,
                "route": route,
            }
        )

    recall = {}
    overall_k0 = (
        _mean([float(value) for value in gold_by_slot[0]])
        + _mean([float(value) for value in gold_by_slot[3]])
    ) / 2.0
    overall_k1 = (
        _mean([float(value) for value in gold_by_slot[1]])
        + _mean([float(value) for value in gold_by_slot[2]])
    ) / 2.0
    recall["overall"] = {
        "k0": overall_k0,
        "k1": overall_k1,
        "loss": overall_k0 - overall_k1,
    }
    maximum_recall_loss = overall_k0 - overall_k1
    for label in sorted(stratum_gold):
        slots = stratum_gold[label]
        k0 = (
            _mean([float(value) for value in slots[0]])
            + _mean([float(value) for value in slots[3]])
        ) / 2.0
        k1 = (
            _mean([float(value) for value in slots[1]])
            + _mean([float(value) for value in slots[2]])
        ) / 2.0
        loss = k0 - k1
        recall[label] = {"k0": k0, "k1": k1, "loss": loss}
        maximum_recall_loss = max(maximum_recall_loss, loss)

    family_metrics = {}
    eligible_wall_means = []
    for family in (*ELIGIBLE_FAMILIES, DENSE_FAMILY):
        rows = [row for row in case_rows if row["family_id"] == family]
        _require(len(rows) == 16, f"family allocation {family}")
        wall_values = [row["wall_improvement"] for row in rows]
        work_values = [row["work_reduction"] for row in rows]
        family_metrics[family] = {
            "wall_improvement": _mean(wall_values),
            "wall_lower_95_one_sided": _bootstrap_lower(
                wall_values, f"jac3-analysis-v1/wall/{family}"
            ),
            "work_reduction": _mean(work_values),
            "work_lower_95_one_sided": _bootstrap_lower(
                work_values, f"jac3-analysis-v1/work/{family}"
            ),
        }
        if family in ELIGIBLE_FAMILIES:
            eligible_wall_means.append(family_metrics[family]["wall_improvement"])

    overall_case_wall = _mean(eligible_wall_means)
    overall_case_wall_lower = _bootstrap_lower(
        eligible_wall_means, "jac3-analysis-v1/wall/overall-family-clusters"
    )
    _require(
        len(process_walls) == 4 and all(value > 0 for value in process_walls),
        "process walls",
    )
    process_k0 = (process_walls[0] + process_walls[3]) / 2.0
    process_k1 = (process_walls[1] + process_walls[2]) / 2.0
    process_improvement = (process_k0 - process_k1) / process_k0
    repeat_regression = [
        (process_walls[slot] - process_k0) / process_k0 for slot in (1, 2)
    ]
    return {
        "case_rows": case_rows,
        "dense_control_wall_overhead": -family_metrics[DENSE_FAMILY][
            "wall_improvement"
        ],
        "eligible_overall_case_wall_improvement": overall_case_wall,
        "eligible_overall_case_wall_lower_95_one_sided": overall_case_wall_lower,
        "false_candidate_count": false_candidates,
        "family_metrics": family_metrics,
        "maximum_recall_loss": maximum_recall_loss,
        "process_k0_wall_ns": process_k0,
        "process_k1_repeat_regressions": repeat_regression,
        "process_k1_wall_ns": process_k1,
        "process_wall_improvement": process_improvement,
        "recall": recall,
    }


def build_summary(
    *,
    manifest: dict[str, Any],
    candidate: dict[str, Any],
    truth: dict[str, Any],
    frozen_k0: dict[str, Any],
    safety: dict[str, Any],
    run: dict[str, Any],
    segments: Sequence[dict[str, Any]],
) -> dict[str, Any]:
    safety_result = assess_safety(safety, truth)
    run_result = validate_run(run, segments, safety)
    k0_mismatches = _k0_replay_count(run_result["cases_by_slot"], frozen_k0)
    metrics = assess_metrics(
        run_result["cases_by_slot"],
        truth,
        candidate,
        run["process_wall_ns"],
    )
    safety_counts = dict(safety_result["counts"])
    safety_counts.update(run_result["counts"])
    safety_counts["false_candidate_count"] = metrics["false_candidate_count"]
    safety_counts["frozen_control_replay_mismatch_count"] = k0_mismatches
    safety_counts["host_contention_event_count"] = run["host_contention_event_count"]
    safety_counts["public_surface_drift_count"] = run["public_surface_drift_count"]
    safety_counts["input_or_source_hash_mismatch_count"] = (
        run["input_hash_mismatch_count"] + run["source_hash_mismatch_count"]
    )

    failures: list[str] = []
    for name, value in sorted(safety_counts.items()):
        if value != 0:
            failures.append(f"zero-required safety metric {name}={value}")
    if metrics["maximum_recall_loss"] > 0.02:
        failures.append("P_local_gold loss exceeds two percentage points")
    for family in ELIGIBLE_FAMILIES:
        family_metric = metrics["family_metrics"][family]
        if family_metric["work_reduction"] < 0.20:
            failures.append(f"{family} work reduction below 20 percent")
        if family_metric["work_lower_95_one_sided"] <= 0.0:
            failures.append(f"{family} work lower bound is not positive")
    if metrics["eligible_overall_case_wall_improvement"] < 0.10:
        failures.append("overall family-clustered wall improvement below 10 percent")
    if metrics["eligible_overall_case_wall_lower_95_one_sided"] <= 0.0:
        failures.append("overall family-clustered wall lower bound is not positive")
    if metrics["process_wall_improvement"] < 0.10:
        failures.append("fully charged process wall improvement below 10 percent")
    if any(value > 0.0 for value in metrics["process_k1_repeat_regressions"]):
        failures.append("one or more K1 process repetitions regress against mean K0")
    if metrics["dense_control_wall_overhead"] > 0.05:
        failures.append("dense control wall overhead exceeds five percent")
    return {
        "decision": "PASS" if not failures else "FAIL",
        "development_only": True,
        "experiment_id": CARD_ID,
        "failures": failures,
        "locked_inputs_authorized": not failures,
        "metrics": metrics,
        "product_connection_authorized": False,
        "provenance": {
            "candidate_input_uncompressed_sha256": manifest["artifacts"]["candidate"][
                "uncompressed_sha256"
            ],
            "input_manifest_sha256": run["input_manifest_sha256"],
            "julia_manifest_sha256": run["julia_manifest_sha256"],
            "run_source_lock_sha256": run["source_lock_sha256"],
        },
        "safety_counts": safety_counts,
        "schema_version": SUMMARY_SCHEMA,
    }


def _write_once(path: Path, document: dict[str, Any]) -> None:
    if path.exists():
        raise AssessmentError(f"output already exists: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    if temporary.exists():
        raise AssessmentError(f"temporary output already exists: {temporary}")
    payload = json.dumps(document, indent=2, sort_keys=True, allow_nan=False) + "\n"
    with temporary.open("x", encoding="utf-8", newline="\n") as handle:
        handle.write(payload)
        handle.flush()
    temporary.replace(path)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--candidate", required=True, type=Path)
    parser.add_argument("--truth", required=True, type=Path)
    parser.add_argument("--frozen-k0", required=True, type=Path)
    parser.add_argument("--safety", required=True, type=Path)
    parser.add_argument("--run", required=True, type=Path)
    parser.add_argument("--segment", required=True, action="append", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = _parser().parse_args(argv)
    if len(arguments.segment) != 4:
        raise AssessmentError("exactly four --segment paths are required")
    manifest_bytes = arguments.manifest.read_bytes()
    manifest = json.loads(manifest_bytes)
    artifacts = manifest["artifacts"]
    candidate = _artifact(arguments.candidate, artifacts["candidate"], "candidate")
    truth = _artifact(arguments.truth, artifacts["assessor"], "assessor")
    frozen_k0 = _artifact(arguments.frozen_k0, artifacts["k0_control"], "K0")
    safety = _load(arguments.safety)
    run = _load(arguments.run)
    segments = [_load(path) for path in arguments.segment]
    _require(
        run["candidate_input_uncompressed_sha256"]
        == artifacts["candidate"]["uncompressed_sha256"],
        "run/candidate input hash",
    )
    _require(
        run["input_manifest_sha256"] == _sha256(manifest_bytes),
        "run input manifest hash",
    )
    summary = build_summary(
        manifest=manifest,
        candidate=candidate,
        truth=truth,
        frozen_k0=frozen_k0,
        safety=safety,
        run=run,
        segments=segments,
    )
    _write_once(arguments.output, summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
