#!/usr/bin/env python3
"""Independent stdlib-only aggregation for EXP-DISC-001 Stage-C ordering T0."""
from __future__ import annotations
import argparse, copy, hashlib, json, math, struct, subprocess, sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Mapping, Sequence
sys.path.insert(0, str(Path(__file__).resolve().parent))
import aggregate_t0 as common  # noqa: E402
import aggregate_stageb_t0 as stageb  # noqa: E402
EXPERIMENT, CASE_COUNT, COLUMNS, BATCH = "EXP-DISC-001", 12, 128, 16
ARMS = ("FIFO_SCORED", "RESIDUAL_ONLY", "SOFT_TGO")
CONTROLS = ("FIFO_SCORED", "RESIDUAL_ONLY", "FIFO_UNSCORED")
THRESHOLDS, CAP = (600, 1_200, 2_400, 4_800), 600
INPUT_SCHEMA = "geotarget.discovery-stagec-soft-tgo-t0-input/v1"
AUTH_SCHEMA = "geotarget.discovery-stagec-soft-tgo-t0-outcome-authorization/v1"
RAW_SCHEMA = "geotarget.discovery-stagec-soft-tgo-t0-raw/v1"
PREARM_SCHEMA = "geotarget.discovery-stagec-soft-tgo-t0-prearm/v1"
OUTPUT_SCHEMA = "geotarget.discovery-stagec-soft-tgo-t0-aggregate/v1"
PROPOSAL_SCHEMA = "geotarget.discovery-proposal-matrix/v1"
RUNNER_SHA = "c2606ed4d9b6a7b656fd917a6f706bd991cb71f30f025ed44081d7bada4a90bb"
PREREG_SHA = "b473e47b67f0c270e9eb2f9b9fa93c9187d1121e04c01f44ba3dbb6086ed7cf1"
SOURCE_MANIFEST = "research/experiments/EXP-LOCAL-004/t2-input-manifest.json"
SOURCE_MANIFEST_SHA = "aa5da6b9655ebe97f5ae8832911cc253301cb64916e0f23f5637b645905bcd81"
SPECIAL = {"TANGENT-CIRCLE-LINE", "MULTIROOT-WARPED"}
REQUIRED_DEPENDENCIES = frozenset({
    "research/experiments/EXP-DISC-001/run_t0_outcomes.jl",
    "research/experiments/EXP-DISC-001/run_stagea_outcomes.jl",
    "research/experiments/EXP-DISC-001/src/ExperimentDisc001.jl",
    "research/experiments/EXP-DISC-001/src/gate.jl",
    "research/experiments/EXP-DISC-001/src/stagec_t0_inputs.jl",
    "research/experiments/EXP-DISC-001/src/soft_tgo_ordering.jl",
    "research/experiments/EXP-DISC-001/aggregate_t0.py",
    "research/experiments/EXP-DISC-001/aggregate_stageb_t0.py",
    "research/experiments/EXP-DISC-001/src/stagea_corpus.jl",
    "research/experiments/EXP-DISC-001/src/stageb_t0_inputs.jl",
    "julia/GeoTargetBenchmarks/src/GeoTargetBenchmarks.jl",
    "julia/GeoTargetBenchmarks/src/types.jl",
    "julia/GeoTargetBenchmarks/src/replay.jl",
    "julia/GeoTargetBenchmarks/src/common.jl",
    "julia/GeoTargetBenchmarks/src/solver_experiment.jl",
    "julia/GeoTargetBenchmarks/src/curved_chain.jl",
    "julia/GeoTargetBenchmarks/src/near_rank_deficient.jl",
    "julia/GeoTargetBenchmarks/src/tangent_circle_line.jl",
    "julia/GeoTargetBenchmarks/src/multiroot_warped.jl",
    "julia/GeoTargetBenchmarks/src/strict_guard_boundary.jl",
    "julia/GeoTargetBenchmarks/src/opaque_transcendental.jl",
})
OPERATIONAL_FIELDS = ("callback_cap_violations", "evaluation_count_mismatches", "exceptions", "runner_budget_exhausted")
EPS, FLOAT_MIN, SUBNORMAL_MIN = 2.0**-52, sys.float_info.min, math.ulp(0.0)
SOURCE_INDICES = (11, 12, 17, 18, 29, 30, 33, 35, 40, 41, 46, 47)
PROPOSAL_METADATA_KEYS = frozenset({"authority_freeze_sha256", "confirmation_contract_sha256", "domain_dimension", "domain_lower_float64_bits", "domain_upper_float64_bits", "experiment_source_sha256", "independence_model", "julia_version", "local_options_sha256", "local_source_sha256", "manifest_sha256", "preregistration_sha256", "proposal_engine_sha256", "proposal_engine_version", "quasi_monte_carlo_version", "rng", "stream_contract"})
PROPOSAL_TRUTH_FIELDS = frozenset({"artifact_checksums", "base_orthogonal", "boundary_case", "candidate_configurations", "candidate_guard_margins", "candidate_strict_validity", "capability_contract", "case_id", "coefficient_seed", "condition", "configuration_count", "curvature", "dependency_error", "dependency_seed", "expected_target_values", "family_id", "formal_case_id", "gold_configurations", "gold_configurations_checksum", "gold_targets", "guard_contract", "guard_margin", "height_radius_ratio", "instance_id", "instance_seed", "latent_roots", "left_orthogonal", "linear_operator", "loop_count", "minimum_separation", "mixing", "opaque_callback_values", "opaque_contract", "orientation_seed", "overdetermined_operator", "parameters", "parameters_checksum", "phase", "radius", "redundancy", "replay_checksum", "residual_dimension", "residual_scale_spread", "right_orthogonal", "root_count", "root_jacobian", "row_scales", "saved_starts", "saved_starts_checksum", "saved_starts_shape", "scales", "singular_value_ratio", "singular_values", "source_index", "start_count", "start_seed", "strata", "target_affine_scale", "target_count", "target_map", "warp", "warp_coefficients"})
PREARM_KEYS = frozenset({"arm_order", "arms", "authorization", "batch_schedule", "batch_schedule_sha256", "bounds", "branch_capability", "experiment_id", "input_manifest_sha256", "prescore_records", "preregistration", "schema_version", "source_artifact", "source_matrix", "stage", "truth_free"})
RECORD_KEYS = frozenset({"branch_fallback", "branch_partition_ordinal", "canonical_valid", "scaled_residual_float64_bits", "score_float64_bits", "source_ordinal", "start_float64_bits"})
RAW_KEYS = frozenset({"arm_order", "arms", "authorization", "case_index", "experiment_id", "input_manifest", "lab_confirmation_512_768", "nonpromotional_t0", "prearm", "prescore_attempt", "preregistration", "revision", "schema_version", "stage", "thread_contract", "work_ledger"})
canonical_json, sha256 = common.canonical_json, common.sha256
digest = stageb._digest_document
def _exact_keys(value: Any, expected: frozenset[str] | set[str], label: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != set(expected): raise ValueError(f"{label} keys differ")
    return value
def _bits(value: float) -> str: return struct.pack(">d", value).hex()
def _number(value: str) -> float:
    if not isinstance(value, str) or len(value) != 16 or set(value) - set("0123456789abcdef"):
        raise ValueError("malformed Float64 bits")
    return struct.unpack(">d", bytes.fromhex(value))[0]
def _finite_bits(value: Any, label: str) -> str:
    result = stageb._validate_bit(value, label)
    return result
def _matrix(document: Any, dimension: int, columns: int, label: str) -> tuple[list[list[str]], str]:
    _exact_keys(document, {"column_count", "coordinate_float64_bits_by_column", "dimension", "matrix_sha256"}, label)
    if document.get("dimension") != dimension or document.get("column_count") != columns:
        raise ValueError(f"{label} shape differs")
    values = stageb._validate_bits_matrix(document.get("coordinate_float64_bits_by_column"), dimension, columns, label)
    wanted = stageb._matrix_digest(values, dimension)
    if document.get("matrix_sha256") != wanted: raise ValueError(f"{label} digest differs")
    return values, wanted
def _inspect_truth_free(value: Any) -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            if any(word in str(key).lower() for word in ("token", "target", "gold", "family", "instance", "identity")):
                raise ValueError(f"prearm leaks {key}")
            _inspect_truth_free(child)
    elif isinstance(value, list):
        for child in value: _inspect_truth_free(child)
def _inspect_proposal_metadata(value: Any) -> None:
    metadata = _exact_keys(value, PROPOSAL_METADATA_KEYS, "D0 public metadata")
    serialized = canonical_json(value).lower()
    leaked = sorted(field for field in PROPOSAL_TRUTH_FIELDS if field in serialized)
    if leaked: raise ValueError(f"D0 metadata leaks {','.join(leaked)}")
    stream = _exact_keys(metadata.get("stream_contract"), {"column_count", "method", "only_difference", "prefixes", "runtime_inputs", "truth_fields_visible"}, "D0 stream contract")
    if stream.get("column_count") != COLUMNS or stream.get("method") != "D0-IID-ALL" or stream.get("prefixes") != [8, 16, 32, 64, 128] or stream.get("runtime_inputs") != ["dimension", "finite_bounds", "numeric_seed"] or stream.get("truth_fields_visible") is not False or not isinstance(stream.get("only_difference"), str): raise ValueError("D0 stream contract differs")
    for name in ("experiment_source_sha256", "local_source_sha256", "preregistration_sha256"):
        mapping = metadata.get(name)
        if not isinstance(mapping, dict) or not mapping or not all(isinstance(key, str) and stageb._sha_text(item) for key, item in mapping.items()): raise ValueError(f"D0 {name} map differs")
    for name in ("authority_freeze_sha256", "confirmation_contract_sha256", "local_options_sha256", "manifest_sha256", "proposal_engine_sha256"):
        if not stageb._sha_text(metadata.get(name)): raise ValueError(f"D0 {name} differs")
def _score(residual_bits: Any) -> tuple[float | None, str | None]:
    if not isinstance(residual_bits, list): raise ValueError("residual bits must be a list")
    values = [_number(value) for value in residual_bits]
    if not values or not all(math.isfinite(value) for value in values): return None, None
    magnitudes = sorted(abs(value) for value in values); scale = magnitudes[-1]
    normalized = [value / scale for value in magnitudes] if scale else []
    score = 0.0 if scale == 0.0 else scale * math.sqrt(sum(sorted(value * value for value in normalized)))
    return (score, _bits(score)) if math.isfinite(score) else (None, None)
def _score_envelope(score: float, dimension: int) -> float:
    return max(SUBNORMAL_MIN, 128.0 * max(1, dimension) * EPS * max(score, FLOAT_MIN))
def _normalization(lower: list[float], upper: list[float]) -> tuple[list[float], list[float], bool]:
    if not lower or len(lower) != len(upper) or not all(math.isfinite(x) for x in lower + upper) or not all(a < b for a, b in zip(lower, upper, strict=True)):
        raise ValueError("invalid finite box")
    midpoint = [a / 2.0 + b / 2.0 for a, b in zip(lower, upper, strict=True)]
    half = [b / 2.0 - a / 2.0 for a, b in zip(lower, upper, strict=True)]
    def spacing(x: float) -> float:
        gaps = [abs(x - y) for y in (math.nextafter(x, -math.inf), math.nextafter(x, math.inf)) if math.isfinite(y)]
        return max(gaps, default=math.inf)
    resolved = all(max(spacing(a), spacing(m), spacing(b)) <= 8.0 * EPS * h for a, m, b, h in zip(lower, midpoint, upper, half, strict=True))
    return midpoint, half, resolved
def _score_ranks(group: list[dict[str, Any]]) -> list[int]:
    order = sorted(range(len(group)), key=lambda i: (group[i]["score"], group[i]["source"]))
    ranks, rank = [0] * len(group), 1
    first = group[order[0]]; envelope = _score_envelope(first["score"], first["rdim"])
    upper = min(sys.float_info.max, first["score"] + envelope); ranks[order[0]] = rank
    for position in order[1:]:
        item = group[position]; envelope = _score_envelope(item["score"], item["rdim"])
        low, high = max(0.0, item["score"] - envelope), min(sys.float_info.max, item["score"] + envelope)
        if low <= upper: upper = max(upper, high)
        else: rank, upper = rank + 1, high
        ranks[position] = rank
    return ranks
def _distance(left: list[float], right: list[float]) -> float:
    differences = [abs(a - b) for a, b in zip(left, right, strict=True)]; scale = max(differences, default=0.0)
    normalized = [value / scale for value in differences] if scale else []
    return 0.0 if scale == 0.0 else scale * scale * sum(sorted(value * value for value in normalized))
def _topology(group: list[dict[str, Any]], dimension: int, ranks: list[int]) -> tuple[list[int], list[list[int]], list[int]]:
    count, neighborhoods, minima = len(group), [], []
    k = min(count - 1, 2 * dimension)
    for position, origin in enumerate(group):
        distances = sorted(((_distance(origin["unit"], other["unit"]), other["source"], j) for j, other in enumerate(group) if j != position))
        if not distances: neighbors = []
        else:
            cutoff = distances[k - 1][0]; upper = cutoff + 128.0 * max(1, dimension) * EPS * max(1.0, cutoff)
            neighbors = sorted((j for value, _, j in distances if max(0.0, value - 128.0 * max(1, dimension) * EPS * max(1.0, value)) <= upper), key=lambda j: group[j]["source"])
        neighborhoods.append(neighbors)
        key = (ranks[position], origin["source"])
        if all((ranks[j], group[j]["source"]) >= key for j in neighbors): minima.append(position)
    key = lambda i: (ranks[i], group[i]["source"])
    return sorted(minima, key=key) + sorted((i for i in range(count) if i not in minima), key=key), neighborhoods, minima
def _round_robin(orders: list[list[int]]) -> list[int]:
    return [order[round_] for round_ in range(max(map(len, orders), default=0)) for order in orders if round_ < len(order)]
def _batch_orders(records: list[dict[str, Any]], lower: list[float], upper: list[float], capability: bool) -> tuple[dict[str, list[int]], dict[str, dict[str, Any]]]:
    dimension = len(lower); midpoint, half, resolved = _normalization(lower, upper)
    groups: dict[int, list[dict[str, Any]]] = defaultdict(list); fallback_by_group: dict[int, bool] = {}
    for record in records:
        source = record.get("source_ordinal"); partition = record.get("branch_partition_ordinal"); fallback = record.get("branch_fallback")
        if isinstance(source, bool) or not isinstance(source, int) or isinstance(partition, bool) or not isinstance(partition, int) or not isinstance(fallback, bool): raise ValueError("invalid serialized partition evidence")
        start = [_number(value) for value in record.get("start_float64_bits", ())]
        if len(start) != dimension or not all(math.isfinite(x) for x in start): raise ValueError("prescore start differs")
        residual_bits = record.get("scaled_residual_float64_bits"); score, _ = _score(residual_bits)
        reported_bits = record.get("score_float64_bits")
        if score is None:
            if reported_bits is not None: raise ValueError("prescore score finite-status differs")
        else:
            reported = _number(reported_bits)
            if not math.isfinite(reported) or abs(score - reported) > _score_envelope(score, len(residual_bits)) + _score_envelope(reported, len(residual_bits)): raise ValueError("prescore score exceeds the independent roundoff envelope")
        if not isinstance(record.get("canonical_valid"), bool): raise ValueError("canonical validity is not Boolean")
        valid = record["canonical_valid"]; eligible = resolved and valid and score is not None
        if (not eligible and not fallback) or (not capability and eligible and fallback): raise ValueError("serialized fallback contradicts public applicability")
        unit = [(x - m) / h for x, m, h in zip(start, midpoint, half, strict=True)]
        if not all(math.isfinite(x) and -1.0 <= x <= 1.0 for x in unit): raise ValueError("prescore point lies outside its box")
        if partition in fallback_by_group and fallback_by_group[partition] != fallback: raise ValueError("partition fallback flag is inconsistent")
        fallback_by_group[partition] = fallback; groups[partition].append({"source": source, "score": score, "rdim": len(residual_bits), "unit": unit})
    if sorted(groups) != list(range(1, len(groups) + 1)): raise ValueError("partition ordinals are not contiguous")
    ordered_groups = [sorted(groups[index], key=lambda x: x["source"]) for index in sorted(groups)]
    if [group[0]["source"] for group in ordered_groups] != sorted(group[0]["source"] for group in ordered_groups) or sum(fallback_by_group.values()) > 1: raise ValueError("partition service order differs")
    if not resolved and (len(groups) != 1 or not fallback_by_group[1]): raise ValueError("under-resolved box is not complete FIFO fallback")
    orders, diagnostics = {}, {}
    for arm in ARMS:
        local, group_docs = [], []
        for partition, group in zip(sorted(groups), ordered_groups, strict=True):
            fallback = fallback_by_group[partition]; ranks = [] if fallback else _score_ranks(group)
            topology = (list(range(len(group))), [[] for _ in group], []) if fallback or arm != "SOFT_TGO" else _topology(group, dimension, ranks)
            if fallback or arm == "FIFO_SCORED": order = list(range(len(group)))
            elif arm == "RESIDUAL_ONLY": order = sorted(range(len(group)), key=lambda i: (ranks[i], group[i]["source"]))
            else: order = topology[0]
            local.append([group[i]["source"] for i in order]); neighborhoods, minima = topology[1], topology[2]
            group_docs.append({"fallback": fallback, "first_source_ordinal": group[0]["source"], "local_minimum_source_ordinals": sorted(group[i]["source"] for i in minima), "member_count": len(group), "neighbor_k": min(len(group) - 1, 2 * dimension) if arm == "SOFT_TGO" and not fallback else 0, "neighborhood_sizes": [len(neighborhoods[i]) for i in range(len(group))], "neighborhood_source_ordinals": [item["source"] for item in group]})
        schedule = sorted(item["source"] for group in ordered_groups for item in group) if arm == "FIFO_SCORED" else _round_robin(local)
        if sorted(schedule) != sorted(record["source_ordinal"] for record in records): raise ValueError("batch did not drain")
        orders[arm] = schedule
        diagnostics[arm] = {"all_candidates_drained": True, "arm": arm, "batch_size": len(records), "branch_capability": capability, "branch_partition_count": sum(not fallback_by_group[index] for index in groups), "dimension": dimension, "fallback_count": sum(len(groups[index]) for index in groups if fallback_by_group[index]), "group_first_source_ordinals": [group[0]["source"] for group in ordered_groups], "groups": group_docs, "normalization_well_resolved": resolved, "rounds": 1 if arm == "FIFO_SCORED" and records else max(map(len, ordered_groups), default=0), "scored_count": sum(len(groups[index]) for index in groups if not fallback_by_group[index])}
    return orders, diagnostics
def _validate_input(document: dict[str, Any]) -> list[dict[str, Any]]:
    if document.get("schema_version") != INPUT_SCHEMA or document.get("experiment_id") != EXPERIMENT or document.get("stage") != "stage-c-soft-tgo-t0" or document.get("nonpromotional_t0") is not True: raise ValueError("unexpected Stage-C input")
    cases = document.get("cases")
    if not isinstance(cases, list) or len(cases) != CASE_COUNT or [case.get("case_index") for case in cases] != list(range(1, CASE_COUNT + 1)): raise ValueError("Stage-C input cases are incomplete")
    if document.get("method") != "D0-IID-ALL" or document.get("target_count") != sum(int(case["target_count"]) for case in cases) or document.get("preregistration", {}).get("sha256") != PREREG_SHA: raise ValueError("Stage-C input source/target/prereg differs")
    if [case.get("source_index") for case in cases] != list(SOURCE_INDICES): raise ValueError("Stage-C source indices differ")
    families = Counter(case.get("family_id") for case in cases)
    expected_families = {"CURVED-CHAIN", "NEAR-RANK-DEFICIENT", "TANGENT-CIRCLE-LINE", "MULTIROOT-WARPED", "STRICT-GUARD-BOUNDARY", "OPAQUE-TRANSCENDENTAL-C0"}
    if set(families) != expected_families or any(count != 2 for count in families.values()) or sum(int(case["configuration_count"]) for case in cases) != 42 or document.get("target_count") != 34: raise ValueError("Stage-C family/denominator balance differs")
    for case in cases:
        if any(not isinstance(case.get(field), int) or isinstance(case.get(field), bool) or case[field] < 1 for field in ("dimension", "configuration_count", "target_count")): raise ValueError("case dimensions/counts differ")
        proposal = case.get("proposal")
        if not isinstance(proposal, dict) or proposal.get("truth_free_metadata") is not True or not all(stageb._sha_text(proposal.get(field)) for field in ("file_sha256", "artifact_sha256")): raise ValueError("proposal binding differs")
    return cases
def _validate_source_cases(cases: list[dict[str, Any]], source: dict[str, Any], preregistration: dict[str, Any], source_sha: str) -> None:
    if source_sha != SOURCE_MANIFEST_SHA or source.get("schema_version") != "exp-local-004-t2-input/v1" or not isinstance(source.get("instances"), list) or len(source["instances"]) != 48: raise ValueError("committed Stage-C source manifest differs")
    registered = preregistration.get("case_sources")
    if not isinstance(registered, list) or len(registered) != CASE_COUNT: raise ValueError("preregistered Stage-C case sources differ")
    for case_index, (case, source_index, registration) in enumerate(zip(cases, SOURCE_INDICES, registered, strict=True), 1):
        formal = f"EXP-DISC-001-C0-{case_index:03d}"; origin = source["instances"][source_index - 1]
        if case.get("source_index") != source_index or case.get("formal_case_id") != formal or registration != {"formal_case_id": formal, "path": SOURCE_MANIFEST, "index": source_index}: raise ValueError("Stage-C formal/source mapping differs")
        for field in ("family_id", "instance_id", "dimension", "configuration_count", "target_count", "replay_checksum"):
            if case.get(field) != origin.get(field): raise ValueError(f"Stage-C source authority differs for {field}")
def _validate_authorization(document: dict[str, Any], input_sha: str, prereg_sha: str, aggregator_sha: str) -> None:
    if document.get("schema_version") != AUTH_SCHEMA or document.get("outcome_execution_authorized") is not True or document.get("nonpromotional_t0") is not True: raise ValueError("Stage-C outcomes unauthorized")
    if document.get("input_manifest", {}).get("sha256") != input_sha or document.get("preregistration", {}).get("sha256") != prereg_sha: raise ValueError("authorization input/prereg differs")
    if document.get("aggregator_source_sha256") != aggregator_sha or document.get("runner_source_sha256") != RUNNER_SHA: raise ValueError("authorization executable hashes differ")
    dependencies = document.get("dependency_source_sha256")
    if not isinstance(dependencies, dict) or not REQUIRED_DEPENDENCIES <= set(dependencies) or not all(stageb._sha_text(value) for value in dependencies.values()): raise ValueError("authorization dependencies absent")
def _validate_proposal(case: dict[str, Any], document: dict[str, Any], file_sha: str, freeze_sha: str) -> list[list[str]]:
    binding = case["proposal"]
    if file_sha != binding["file_sha256"] or document.get("schema_version") != PROPOSAL_SCHEMA or document.get("method") != "D0-IID-ALL" or document.get("dimension") != case["dimension"] or document.get("column_count") != COLUMNS: raise ValueError("D0 artifact binding differs")
    payload = dict(document); internal = payload.pop("sha256", None)
    if internal != binding["artifact_sha256"] or digest(payload) != internal or document.get("authority_sha256") != freeze_sha or str(document.get("replicate_seed")) != str(binding["replicate_seed"]): raise ValueError("D0 artifact authority/digest differs")
    bits = stageb._validate_bits_matrix(document.get("coordinate_float64_bits_by_column"), case["dimension"], COLUMNS, "D0 source")
    if document.get("lane_schedule") != ["iid"] * COLUMNS or document.get("source_columns") != list(range(1, COLUMNS + 1)): raise ValueError("D0 artifact is not all-IID")
    metadata = document.get("metadata")
    _inspect_proposal_metadata(metadata)
    return bits
def _validate_prearm(document: dict[str, Any], case: dict[str, Any], proposal: dict[str, Any], proposal_bits: list[list[str]], input_sha: str, prereg: dict[str, Any], auth: dict[str, Any]) -> dict[str, Any]:
    _exact_keys(document, PREARM_KEYS, "prearm")
    if document.get("schema_version") != PREARM_SCHEMA or document.get("experiment_id") != EXPERIMENT or document.get("stage") != "stage-c-soft-tgo-t0" or document.get("truth_free") is not True or document.get("arm_order") != list(ARMS): raise ValueError("prearm contract differs")
    _inspect_truth_free(document)
    _exact_keys(document.get("authorization"), {"path", "sha256"}, "prearm authorization"); _exact_keys(document.get("preregistration"), {"path", "sha256"}, "prearm preregistration"); _exact_keys(document.get("source_artifact"), {"artifact_sha256", "file_sha256", "path"}, "prearm source artifact")
    if document.get("input_manifest_sha256") != input_sha or document.get("preregistration") != prereg or document.get("authorization") != auth: raise ValueError("prearm authority binding differs")
    if document.get("source_artifact") != {field: proposal[field] for field in ("artifact_sha256", "file_sha256", "path")}: raise ValueError("prearm source artifact differs")
    dimension = int(case["dimension"]); source_bits, _ = _matrix(document.get("source_matrix"), dimension, COLUMNS, "prearm source")
    if source_bits != proposal_bits: raise ValueError("prearm source matrix differs from D0")
    bounds = _exact_keys(document.get("bounds"), {"bounds_sha256", "lower_float64_bits", "upper_float64_bits"}, "prearm bounds"); lower_bits = stageb._bits_vector(bounds.get("lower_float64_bits"), dimension, "lower bounds"); upper_bits = stageb._bits_vector(bounds.get("upper_float64_bits"), dimension, "upper bounds")
    unsigned_bounds = {"lower_float64_bits": lower_bits, "upper_float64_bits": upper_bits}
    if bounds.get("bounds_sha256") != digest(unsigned_bounds): raise ValueError("prearm bounds digest differs")
    metadata = proposal["_document"].get("metadata", {})
    if lower_bits != metadata.get("domain_lower_float64_bits") or upper_bits != metadata.get("domain_upper_float64_bits"): raise ValueError("prearm bounds differ from committed D0 domain")
    records = document.get("prescore_records")
    if not isinstance(records, list) or len(records) != COLUMNS or [row.get("source_ordinal") for row in records] != list(range(1, COLUMNS + 1)): raise ValueError("prescore records are incomplete")
    for index, record in enumerate(records):
        _exact_keys(record, RECORD_KEYS, "prescore record")
        if record.get("start_float64_bits") != proposal_bits[index]: raise ValueError("prescore start differs from D0")
        _score(record.get("scaled_residual_float64_bits"))
    capability = document.get("branch_capability")
    if not isinstance(capability, bool): raise ValueError("branch capability is absent")
    batches = document.get("batch_schedule")
    if not isinstance(batches, list) or len(batches) != COLUMNS // BATCH or document.get("batch_schedule_sha256") != digest(batches): raise ValueError("prearm batch schedule differs")
    global_schedules = {name: [] for name in ARMS}
    for batch_index, batch in enumerate(batches, 1):
        _exact_keys(batch, {"arms", "batch_index", "logical_ledger", "prescore_callback_cost", "source_ordinal_range"}, "prearm batch")
        first = (batch_index - 1) * BATCH + 1; expected_range = list(range(first, first + BATCH))
        if batch.get("batch_index") != batch_index or batch.get("source_ordinal_range") != [first, first + BATCH - 1] or batch.get("prescore_callback_cost") != BATCH or batch.get("logical_ledger") != "PRESCORE16_THEN_16_WHOLE_LOCAL_ATTEMPTS": raise ValueError("batch boundary differs")
        expected, diagnostics = _batch_orders(records[first - 1:first + BATCH - 1], list(map(_number, lower_bits)), list(map(_number, upper_bits)), capability)
        entries = batch.get("arms")
        if not isinstance(entries, list) or [entry.get("name") for entry in entries] != list(ARMS): raise ValueError("batch arm order differs")
        for entry in entries:
            _exact_keys(entry, {"diagnostics", "name", "permutation_within_batch", "source_ordinal_schedule"}, "prearm batch arm")
            name = entry["name"]
            if entry.get("source_ordinal_schedule") != expected[name] or entry.get("permutation_within_batch") != [expected_range.index(value) + 1 for value in expected[name]] or entry.get("diagnostics") != diagnostics[name]: raise ValueError(f"independent {name} batch reconstruction differs")
            global_schedules[name].extend(expected[name])
    arm_entries = document.get("arms")
    if not isinstance(arm_entries, list) or [entry.get("name") for entry in arm_entries] != list(ARMS): raise ValueError("prearm arm order differs")
    matrices, matrix_sha = {}, {}
    for entry in arm_entries:
        _exact_keys(entry, {"name", "ordered_matrix", "source_ordinal_schedule"}, "prearm arm")
        name = entry["name"]
        if entry.get("source_ordinal_schedule") != global_schedules[name]: raise ValueError("global schedule differs")
        matrix_bits, matrix_sha[name] = _matrix(entry.get("ordered_matrix"), dimension, COLUMNS, f"{name} matrix")
        if matrix_bits != [proposal_bits[source - 1] for source in global_schedules[name]]: raise ValueError("ordered matrix differs from its source schedule")
        matrices[name] = matrix_bits
    return {"schedules": global_schedules, "matrices": matrices, "matrix_sha": matrix_sha, "batch_sha": document["batch_schedule_sha256"]}
def _fingerprint(attempt: dict[str, Any]) -> str:
    return canonical_json({key: value for key, value in attempt.items() if key not in {"replay_checksum", "start_index", "timing_phase", "wall_seconds"}})
def _validate_arm_replay(attempts: list[dict[str, Any]]) -> None:
    checksums = {row.get("replay_checksum") for row in attempts}
    if len(checksums) != 1 or not stageb._sha_text(next(iter(checksums), None)): raise ValueError("arm replay checksum differs")
def _expected_ledger(arms: list[dict[str, Any]], prescore: dict[str, Any]) -> dict[str, Any]:
    logical, charged = {}, {}
    for arm in arms:
        attempts, entries = arm["attempts"], []
        for batch in range(COLUMNS // BATCH):
            positions = range(batch * BATCH, (batch + 1) * BATCH)
            entries.append({"attempt_position_range": [positions.start + 1, positions.stop], "batch_index": batch + 1, "local_observed_callbacks": sum(common._observed(attempts[i]) for i in positions), "prescore_observed_callbacks": BATCH, "source_ordinals": arm["source_ordinals"][positions.start:positions.stop]})
        logical[arm["name"]] = entries; charged[arm["name"]] = COLUMNS + sum(common._observed(row) for row in attempts)
    fifo = arms[0]
    return {"charged_total_callback_work_by_arm": charged, "derived_fifo_unscored": {"prescore_charge": 0, "reuses_arm": "FIFO_SCORED", "solver_executed": False, "total_callback_work": sum(common._observed(row) for row in fifo["attempts"])}, "logical_rolling_batches_by_arm": logical, "physical_prescore_observed_callbacks": prescore["observed_evaluations"], "physical_prescore_reported_callbacks": prescore["reported_evaluations"], "work_contract": "PRESCORE16_THEN_16_WHOLE_LOCAL_ATTEMPTS_V1"}
def _ledger_prefix(attempts: list[dict[str, Any]], threshold: int, prescore_charge: int) -> tuple[list[dict[str, Any]], int]:
    selected, work, stop = [], 0, False
    for batch in range(COLUMNS // BATCH):
        if work + prescore_charge > threshold: break
        work += prescore_charge
        for attempt in attempts[batch * BATCH:(batch + 1) * BATCH]:
            if work + common._observed(attempt) > threshold: stop = True; break
            work += common._observed(attempt); selected.append(attempt)
        if stop: break
    return selected, work
def _raw_header(shard: dict[str, Any], index: int, input_sha: str, auth_sha: str, prereg_sha: str) -> None:
    _exact_keys(shard, RAW_KEYS, "raw shard")
    _exact_keys(shard.get("input_manifest"), {"path", "sha256"}, "raw input binding")
    _exact_keys(shard.get("authorization"), {"path", "sha256"}, "raw authorization binding")
    _exact_keys(shard.get("preregistration"), {"path", "sha256"}, "raw preregistration binding")
    _exact_keys(shard.get("prearm"), {"batch_schedule_sha256", "path", "sha256"}, "raw prearm binding")
    _exact_keys(shard.get("revision"), {"git_dirty", "git_head"}, "raw revision")
    threads = _exact_keys(shard.get("thread_contract"), {"assigned_cpu", "blas_threads", "case_process_limit", "cpus_allowed_list", "environment", "julia_threads", "solver_worker_count"}, "raw thread contract")
    _exact_keys(threads.get("environment"), {"JULIA_NUM_THREADS", "OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"}, "raw thread environment")
    if any((shard.get("schema_version") != RAW_SCHEMA, shard.get("experiment_id") != EXPERIMENT, shard.get("stage") != "stage-c-soft-tgo-t0", shard.get("case_index") != index, shard.get("nonpromotional_t0") is not True, shard.get("lab_confirmation_512_768") is not False, shard.get("input_manifest", {}).get("sha256") != input_sha, shard.get("authorization", {}).get("sha256") != auth_sha, shard.get("preregistration", {}).get("sha256") != prereg_sha, shard.get("arm_order") != list(ARMS))): raise ValueError(f"raw shard {index} contract differs")
    revision = shard["revision"]
    if revision.get("git_dirty") is not False or not revision.get("git_head"): raise ValueError("raw revision is not clean")
    expected = {"julia_threads": 1, "blas_threads": 1, "solver_worker_count": 1, "case_process_limit": 12, "assigned_cpu": index - 1, "cpus_allowed_list": str(index - 1)}
    if any(threads.get(key) != value for key, value in expected.items()) or any(threads.get("environment", {}).get(name) != "1" for name in ("JULIA_NUM_THREADS", "OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS")): raise ValueError("raw thread contract differs")
def _favorable(headroom: bool, strict: bool, families: Mapping[str, bool], safety: int, operational: int) -> bool:
    return headroom and strict and all(families.values()) and safety == operational == 0
def aggregate_documents(input_document: dict[str, Any], preregistration: dict[str, Any], source_document: dict[str, Any], authorization: dict[str, Any], shards: Sequence[dict[str, Any]], *, input_sha: str, prereg_sha: str, source_sha: str, authorization_sha: str, aggregator_sha: str, proposals: Mapping[int, tuple[dict[str, Any], str]], prearms: Mapping[int, tuple[dict[str, Any], str]]) -> dict[str, Any]:
    cases = _validate_input(input_document)
    if prereg_sha != PREREG_SHA or preregistration.get("schema_version") != "geotarget.discovery-stagec-soft-tgo-t0-preregistration/v1" or preregistration.get("nonpromotional_t0") is not True or preregistration.get("outcome_execution_authorized") is not False or input_document.get("preregistration", {}).get("sha256") != prereg_sha: raise ValueError("preregistration binding differs")
    _validate_source_cases(cases, source_document, preregistration, source_sha)
    _validate_authorization(authorization, input_sha, prereg_sha, aggregator_sha)
    indices = [int(shard.get("case_index", 0)) for shard in shards]
    if len(shards) != CASE_COUNT or sorted(indices) != list(range(1, CASE_COUNT + 1)) or set(proposals) != set(indices) or set(prearms) != set(indices): raise ValueError("raw/proposal/prearm shards are missing or duplicated")
    rows, checkpoints, accounting, revisions = [], [], defaultdict(int), set()
    by_case_threshold: dict[tuple[int, str, int], dict[str, Any]] = {}
    for shard in sorted(shards, key=lambda item: item["case_index"]):
        index, case = int(shard["case_index"]), cases[int(shard["case_index"]) - 1]
        _raw_header(shard, index, input_sha, authorization_sha, prereg_sha); revisions.add(shard["revision"]["git_head"])
        proposal_document, proposal_file_sha = proposals[index]; proposal_bits = _validate_proposal(case, proposal_document, proposal_file_sha, input_document["local_freeze_sha256"])
        proposal = dict(case["proposal"]); proposal["_document"] = proposal_document
        prearm_document, prearm_file_sha = prearms[index]; binding = shard.get("prearm", {})
        if binding.get("sha256") != prearm_file_sha: raise ValueError("raw binds another prearm")
        prearm = _validate_prearm(prearm_document, case, proposal, proposal_bits, input_sha, shard["preregistration"], shard["authorization"])
        if binding.get("batch_schedule_sha256") != prearm["batch_sha"]: raise ValueError("raw/prearm batch digest differs")
        prescore = shard.get("prescore_attempt", {})
        if prescore != {"budget_exhausted": False, "endpoint": None, "evaluation_count_mismatch": False, "exception": None, "iterations": COLUMNS, "observed_evaluations": COLUMNS, "reported_evaluations": COLUMNS, "status": "STAGEC_PRESCORE_ONLY"}: raise ValueError("physical prescore attempt differs")
        arms = shard.get("arms")
        if not isinstance(arms, list) or [arm.get("name") for arm in arms] != list(ARMS): raise ValueError("raw arm order differs")
        fingerprints: dict[int, str] | None = None
        for arm in arms:
            _exact_keys(arm, {"attempts", "matrix_sha256", "name", "source_ordinals", "terminal"}, "raw arm")
            _exact_keys(arm.get("terminal"), {"attempt_count", "callback_cap_violations", "callback_work", "evaluation_count_mismatches", "exceptions", "runner_budget_exhausted"}, "raw terminal")
            name, schedule, attempts = arm["name"], prearm["schedules"][arm["name"]], arm.get("attempts")
            if arm.get("source_ordinals") != schedule or arm.get("matrix_sha256") != prearm["matrix_sha"][name] or [row.get("source_ordinal") for row in attempts] != schedule: raise ValueError("raw arm schedule/matrix differs")
            _validate_arm_replay(attempts)
            counts = stageb._validate_attempts(attempts, prearm["matrices"][name], int(case["dimension"]), name)
            if stageb._validate_terminal(arm.get("terminal"), attempts, COLUMNS): raise ValueError("raw terminal accounting differs")
            current = {int(row["source_ordinal"]): _fingerprint(row) for row in attempts}
            if len(current) != COLUMNS or fingerprints is not None and current != fingerprints: raise ValueError("per-source local outcomes differ between arms")
            fingerprints = current if fingerprints is None else fingerprints
            for field, value in counts.items(): accounting[field] += value
            for field, value in stageb._attempt_safety_counts(attempts).items(): accounting[field] += value
            terminal = common.prefix_metrics(attempts, int(case["target_count"]), int(case["configuration_count"]))
            rows.append({**terminal, "arm": name, "case_index": index, "family_id": case["family_id"], "terminal_case_total_callback_work": COLUMNS + terminal["callback_work"]})
            for threshold in THRESHOLDS:
                selected, work = _ledger_prefix(attempts, threshold, BATCH)
                metric = common.prefix_metrics(selected, int(case["target_count"]), int(case["configuration_count"]))
                row = {**metric, "arm": name, "attempts_completed": len(selected), "case_index": index, "family_id": case["family_id"], "logical_callback_work": work, "threshold": threshold}
                checkpoints.append(row); by_case_threshold[(index, name, threshold)] = row
        fifo = arms[0]; terminal = common.prefix_metrics(fifo["attempts"], int(case["target_count"]), int(case["configuration_count"]))
        rows.append({**terminal, "arm": "FIFO_UNSCORED", "case_index": index, "family_id": case["family_id"], "terminal_case_total_callback_work": terminal["callback_work"]})
        for threshold in THRESHOLDS:
            selected, work = _ledger_prefix(fifo["attempts"], threshold, 0); metric = common.prefix_metrics(selected, int(case["target_count"]), int(case["configuration_count"]))
            row = {**metric, "arm": "FIFO_UNSCORED", "attempts_completed": len(selected), "case_index": index, "family_id": case["family_id"], "logical_callback_work": work, "threshold": threshold}
            checkpoints.append(row); by_case_threshold[(index, "FIFO_UNSCORED", threshold)] = row
        expected_ledger = _expected_ledger(arms, prescore)
        if shard.get("work_ledger") != expected_ledger: raise ValueError("raw logical work ledger differs")
    if len(revisions) != 1: raise ValueError("raw shards came from different revisions")
    terminal_identity = all(len({canonical_json({key: row[key] for key in ("assessor_distinct_targets_found", "assessor_safe_full", "assessor_unsafe", "assessor_ambiguity")}) for row in rows if row["case_index"] == index}) == 1 for index in range(1, CASE_COUNT + 1))
    if not terminal_identity: raise ValueError("terminal answer classes differ")
    headroom, strict_cases, nonregression = [], [], {}
    for case in cases:
        index, family = int(case["case_index"]), str(case["family_id"])
        terminal = next(row for row in rows if row["case_index"] == index and row["arm"] == "FIFO_SCORED")
        has_headroom = bool(terminal["assessor_safe_full"]) and not bool(by_case_threshold[(index, "FIFO_SCORED", 600)]["assessor_safe_full"])
        if has_headroom: headroom.append((index, family))
        nonreg = all(by_case_threshold[(index, "SOFT_TGO", threshold)][field] >= by_case_threshold[(index, control, threshold)][field] for threshold in THRESHOLDS for control in CONTROLS for field in ("assessor_distinct_targets_found", "assessor_safe_full"))
        strict_at = [threshold for threshold in THRESHOLDS if all(by_case_threshold[(index, "SOFT_TGO", threshold)]["assessor_distinct_targets_found"] > by_case_threshold[(index, control, threshold)]["assessor_distinct_targets_found"] for control in CONTROLS)]
        nonregression[index] = nonreg
        if has_headroom and nonreg and strict_at: strict_cases.append((index, family, strict_at))
    headroom_families = {family for _, family in headroom}; strict_families = {family for _, family, _ in strict_cases}
    headroom_signal = len(headroom) >= 4 and len(headroom_families) >= 3 and any(family not in SPECIAL for _, family in headroom)
    strict_signal = len(strict_cases) >= 2 and len(strict_families) >= 2 and any(family not in SPECIAL for _, family, _ in strict_cases)
    family_nonregression = {family: all(nonregression[int(case["case_index"])] for case in cases if case["family_id"] == family) for family in sorted({case["family_id"] for case in cases})}
    safety = sum(accounting[field] for field in ("assessor_false_or_unsafe", "reported_accepted_ambiguous", "reported_accepted_canonical_invalid", "reported_accepted_gold_inconsistent", "reported_accepted_numeric_target_only"))
    operational = sum(accounting[field] for field in OPERATIONAL_FIELDS)
    favorable = _favorable(headroom_signal, strict_signal, family_nonregression, safety, operational)
    status = "INCONCLUSIVE_NO_HEADROOM" if not headroom_signal else "FAVORABLE_NONPROMOTIONAL_T0" if favorable else "NEGATIVE_NONPROMOTIONAL_T0"
    return {"accounting": dict(sorted(accounting.items())), "authorization_sha256": authorization_sha, "case_rows": rows, "checkpoint_rows": checkpoints, "decision": {"accounting_violations": operational, "critical_family_nonregression": family_nonregression, "headroom_case_indices": [index for index, _ in headroom], "headroom_signal": headroom_signal, "performance_authority": False, "promotion": False, "safety_violations": safety, "status": status, "strict_win_cases": [{"case_index": index, "thresholds": thresholds} for index, _, thresholds in strict_cases], "strict_win_signal": strict_signal, "terminal_identity": terminal_identity, "tuning_allowed": False}, "experiment_id": EXPERIMENT, "input_manifest_sha256": input_sha, "preregistration_sha256": prereg_sha, "revision": revisions.pop(), "schema_version": OUTPUT_SCHEMA, "source_manifest_sha256": source_sha, "stage": "stage-c-soft-tgo-t0"}
def _load_relative(root: Path, relative: Any, label: str) -> Path: return stageb._load_relative(root, relative, label)
def validate_formal_proposals(input_path: Path) -> dict[str, Any]:
    root = Path(__file__).resolve().parents[3]; document = json.loads(input_path.read_text()); cases = _validate_input(document)
    validated, rejected = 0, 0
    for case in cases:
        path = _load_relative(root, case["proposal"]["path"], "formal D0 proposal"); proposal = json.loads(path.read_text())
        _validate_proposal(case, proposal, sha256(path), document["local_freeze_sha256"]); validated += 1
        if validated == 1:
            for field in ("parameters", "parameters_checksum", "replay_checksum", "residual_dimension", "strata", "saved_starts", "saved_starts_checksum"):
                poisoned = copy.deepcopy(proposal); poisoned["metadata"]["local_source_sha256"]["note"] = field; payload = dict(poisoned); payload.pop("sha256"); poisoned["sha256"] = digest(payload)
                poisoned_case = copy.deepcopy(case); poisoned_case["proposal"]["artifact_sha256"] = poisoned["sha256"]; poisoned_case["proposal"]["file_sha256"] = "f" * 64
                try: _validate_proposal(poisoned_case, poisoned, "f" * 64, document["local_freeze_sha256"])
                except ValueError as error: rejected += str(error).startswith("D0 metadata leaks ")
    if validated != CASE_COUNT or rejected != 7: raise ValueError("formal D0 proposal smoke is incomplete")
    return {"formal_proposals_validated": validated, "outcomes_executed": False, "schema_version": "geotarget.discovery-stagec-soft-tgo-t0-proposal-smoke/v1", "truth_tampers_rejected": rejected}
def aggregate_files(input_path: Path, auth_path: Path, shard_paths: Sequence[Path]) -> dict[str, Any]:
    root = Path(__file__).resolve().parents[3]; input_document = json.loads(input_path.read_text()); authorization = json.loads(auth_path.read_text()); shards = [json.loads(path.read_text()) for path in shard_paths]
    input_binding = authorization.get("input_manifest", {}); bound_input = _load_relative(root, input_binding.get("path"), "authorized input")
    if bound_input != input_path.resolve() or sha256(bound_input) != input_binding.get("sha256"): raise ValueError("authorization input path/hash differs")
    prereg_binding = input_document.get("preregistration", {}); prereg_path = _load_relative(root, prereg_binding.get("path"), "preregistration")
    if sha256(prereg_path) != prereg_binding.get("sha256") or authorization.get("preregistration", {}).get("path") != prereg_binding.get("path"): raise ValueError("preregistration file binding differs")
    runner = Path(__file__).with_name("run_stagec_t0.jl")
    if sha256(runner) != RUNNER_SHA or authorization.get("runner_source_sha256") != RUNNER_SHA: raise ValueError("runner source hash differs")
    for relative, expected in authorization.get("dependency_source_sha256", {}).items():
        if sha256(_load_relative(root, relative, "authorized dependency")) != expected: raise ValueError(f"dependency drifted: {relative}")
    freeze = Path(__file__).with_name("local-champion-freeze-record.json")
    if sha256(freeze) != input_document.get("local_freeze_sha256"): raise ValueError("local freeze binding differs")
    source_path = _load_relative(root, SOURCE_MANIFEST, "committed Stage-C source")
    tracked = subprocess.run(["git", "-C", str(root), "ls-files", "--error-unmatch", "--", SOURCE_MANIFEST], capture_output=True, check=False)
    if tracked.returncode or sha256(source_path) != SOURCE_MANIFEST_SHA: raise ValueError("Stage-C source manifest is uncommitted or drifted")
    input_relative, auth_relative = input_path.resolve().relative_to(root).as_posix(), auth_path.resolve().relative_to(root).as_posix()
    proposals, prearms, proposal_paths, prearm_paths = {}, {}, set(), set()
    for case in input_document["cases"]:
        index = int(case["case_index"]); path = _load_relative(root, case["proposal"]["path"], "D0 artifact")
        if path in proposal_paths: raise ValueError("duplicate D0 artifact path")
        proposal_paths.add(path); proposals[index] = (json.loads(path.read_text()), sha256(path))
    for shard in shards:
        index = int(shard.get("case_index", 0)); binding = shard.get("prearm", {}); path = _load_relative(root, binding.get("path"), "prearm")
        if sha256(path) != binding.get("sha256") or shard.get("input_manifest", {}).get("path") != input_relative or shard.get("authorization", {}).get("path") != auth_relative or path in prearm_paths: raise ValueError("raw file path/hash binding differs")
        prearm_paths.add(path)
        if index in prearms: raise ValueError("duplicate prearm case")
        prearms[index] = (json.loads(path.read_text()), sha256(path))
    return aggregate_documents(input_document, json.loads(prereg_path.read_text()), json.loads(source_path.read_text()), authorization, shards, input_sha=sha256(input_path), prereg_sha=sha256(prereg_path), source_sha=sha256(source_path), authorization_sha=sha256(auth_path), aggregator_sha=sha256(Path(__file__)), proposals=proposals, prearms=prearms)
def self_test() -> dict[str, Any]:
    lower, upper = [-1.0], [1.0]; records = []
    for source in range(1, 17):
        start, residual = -0.9 + 0.12 * (source - 1), float((source * 7) % 17)
        records.append({"branch_fallback": False, "branch_partition_ordinal": 1, "canonical_valid": True, "scaled_residual_float64_bits": [_bits(residual)], "score_float64_bits": _bits(abs(residual)), "source_ordinal": source, "start_float64_bits": [_bits(start)]})
    orders, diagnostics = _batch_orders(records, lower, upper, False)
    assert orders["FIFO_SCORED"] == list(range(1, 17)) and sorted(orders["SOFT_TGO"]) == list(range(1, 17))
    assert all(value["all_candidates_drained"] for value in diagnostics.values())
    residual = ["33803aadbefcb1eb", "b3c66103d75ceb1b", "33b6dcda09aac7c0"]
    python_score, python_bits = _score(residual); julia_bits = "33c92666acbc2cc2"; julia_score = _number(julia_bits)
    assert python_bits == "33c92666acbc2cc0" and abs(python_score - julia_score) <= _score_envelope(python_score, 3) + _score_envelope(julia_score, 3)
    tamper = copy.deepcopy(records); tamper[0]["score_float64_bits"] = _bits(999.0)
    detected = 0
    for fixture in (tamper, [{**row, "branch_partition_ordinal": 2} for row in records], [{**row, "canonical_valid": False} if index == 0 else row for index, row in enumerate(records)]):
        try: _batch_orders(fixture, lower, upper, False)
        except ValueError: detected += 1
    try: _inspect_truth_free({"target_id": "forbidden"})
    except ValueError: detected += 1
    narrow = [{**row, "branch_fallback": True, "start_float64_bits": [_bits(1.0e16)]} for row in records]
    narrow_orders, narrow_diagnostics = _batch_orders(narrow, [1.0e16], [1.0e16 + 2.0], False)
    assert narrow_orders["SOFT_TGO"] == list(range(1, 17)) and not narrow_diagnostics["SOFT_TGO"]["normalization_well_resolved"]
    assert detected == 4
    replay_a = {"replay_checksum": "a" * 64, "source_ordinal": 1, "status": "ok"}
    replay_b = {**replay_a, "replay_checksum": "b" * 64}
    assert _fingerprint(replay_a) == _fingerprint(replay_b)
    _validate_arm_replay([replay_a, replay_a]); replay_tampers = 0
    for fixture in ([replay_a, replay_b], [{**replay_a, "replay_checksum": "bad"}]):
        try: _validate_arm_replay(fixture)
        except ValueError: replay_tampers += 1
    assert replay_tampers == 2
    schema_tampers = 0
    bad_prearm = {key: None for key in PREARM_KEYS}; bad_prearm["note"] = "secret"
    try: _validate_prearm(bad_prearm, {}, {}, [], "", {}, {})
    except ValueError as error:
        schema_tampers += str(error) == "prearm keys differ"
    bad_record = {key: None for key in RECORD_KEYS}; bad_record["note"] = "secret"
    try: _exact_keys(bad_record, RECORD_KEYS, "prescore record")
    except ValueError as error:
        schema_tampers += str(error) == "prescore record keys differ"
    bad_raw = {key: None for key in RAW_KEYS}; bad_raw["note"] = "secret"
    try: _raw_header(bad_raw, 1, "", "", "")
    except ValueError as error:
        schema_tampers += str(error) == "raw shard keys differ"
    assert schema_tampers == 3
    allowed_metadata = {key: "value" for key in PROPOSAL_METADATA_KEYS}; allowed_metadata.update({"authority_freeze_sha256": "0" * 64, "confirmation_contract_sha256": "0" * 64, "domain_dimension": 1, "domain_lower_float64_bits": [_bits(-1.0)], "domain_upper_float64_bits": [_bits(1.0)], "experiment_source_sha256": {"source.jl": "0" * 64}, "local_options_sha256": "0" * 64, "local_source_sha256": {"julia/GeoTargetBase/src/GeoTargetBase.jl": "0" * 64}, "manifest_sha256": "0" * 64, "preregistration_sha256": {"original": "0" * 64}, "proposal_engine_sha256": "0" * 64, "stream_contract": {"column_count": COLUMNS, "method": "D0-IID-ALL", "only_difference": "every point launched", "prefixes": [8, 16, 32, 64, 128], "runtime_inputs": ["dimension", "finite_bounds", "numeric_seed"], "truth_fields_visible": False}}); _inspect_proposal_metadata(allowed_metadata)
    proposal_truth_tampers = 0
    for field in PROPOSAL_TRUTH_FIELDS:
        for poisoned in ({**copy.deepcopy(allowed_metadata), "independence_model": f"contains {field}"}, copy.deepcopy(allowed_metadata)):
            if poisoned["independence_model"] == allowed_metadata["independence_model"]: poisoned["local_source_sha256"][field] = "0" * 64
            try: _inspect_proposal_metadata(poisoned)
            except ValueError as error: proposal_truth_tampers += str(error).startswith("D0 metadata leaks ")
    assert proposal_truth_tampers == 2 * len(PROPOSAL_TRUTH_FIELDS)
    proposal_schema_tampers = 0
    schema_fixtures = []
    fixture = copy.deepcopy(allowed_metadata); fixture["note"] = "secret"; schema_fixtures.append(fixture)
    fixture = copy.deepcopy(allowed_metadata); fixture["stream_contract"]["note"] = "secret"; schema_fixtures.append(fixture)
    fixture = copy.deepcopy(allowed_metadata); fixture["stream_contract"]["runtime_inputs"].append("extra"); schema_fixtures.append(fixture)
    fixture = copy.deepcopy(allowed_metadata); fixture["local_source_sha256"]["source.jl"] = "bad"; schema_fixtures.append(fixture)
    for fixture in schema_fixtures:
        try: _inspect_proposal_metadata(fixture)
        except ValueError: proposal_schema_tampers += 1
    assert proposal_schema_tampers == 4
    authorization = {"schema_version": AUTH_SCHEMA, "outcome_execution_authorized": True, "nonpromotional_t0": True, "input_manifest": {"sha256": "i"}, "preregistration": {"sha256": "p"}, "aggregator_source_sha256": "a", "runner_source_sha256": RUNNER_SHA, "dependency_source_sha256": {path: "0" * 64 for path in REQUIRED_DEPENDENCIES}}
    _validate_authorization(authorization, "i", "p", "a"); omissions = 0
    for path in REQUIRED_DEPENDENCIES:
        broken = copy.deepcopy(authorization); broken["dependency_source_sha256"].pop(path)
        try: _validate_authorization(broken, "i", "p", "a")
        except ValueError: omissions += 1
    assert omissions == len(REQUIRED_DEPENDENCIES)
    assert sum(defaultdict(int, {"callback_cap_violations": 1})[field] for field in OPERATIONAL_FIELDS) == 1
    assert not _favorable(True, True, {"critical": True}, 0, 1)
    source = {"schema_version": "exp-local-004-t2-input/v1", "instances": [{} for _ in range(48)]}; source_cases, registrations = [], []
    for case_index, source_index in enumerate(SOURCE_INDICES, 1):
        origin = {"family_id": f"family-{(case_index - 1) // 2}", "instance_id": f"instance-{case_index}", "dimension": 2, "configuration_count": case_index, "target_count": case_index + 1, "replay_checksum": f"replay-{case_index}"}; source["instances"][source_index - 1] = origin
        formal = f"EXP-DISC-001-C0-{case_index:03d}"; source_cases.append({**origin, "case_index": case_index, "formal_case_id": formal, "source_index": source_index}); registrations.append({"formal_case_id": formal, "path": SOURCE_MANIFEST, "index": source_index})
    source_prereg = {"case_sources": registrations}; _validate_source_cases(source_cases, source, source_prereg, SOURCE_MANIFEST_SHA); source_tampers = 0
    for field, value in (("target_count", -1), ("family_id", "swapped-family")):
        broken = copy.deepcopy(source_cases); broken[0][field] = value
        try: _validate_source_cases(broken, source, source_prereg, SOURCE_MANIFEST_SHA)
        except ValueError: source_tampers += 1
    assert source_tampers == 2
    attempts = [{"observed_evaluations": 37} for _ in range(128)]
    selected, work = _ledger_prefix(attempts, 600, 16)
    assert work <= 600 and len(selected) == 15
    return {"algorithm_fixture": True, "dependency_omissions_detected": omissions, "formal_raw_required": False, "outcomes_executed": False, "proposal_schema_tampers_detected": proposal_schema_tampers, "proposal_truth_tampers_detected": proposal_truth_tampers, "replay_identity_tampers_detected": replay_tampers, "schema_tampers_detected": schema_tampers, "schema_version": "geotarget.discovery-stagec-soft-tgo-t0-aggregate-self-test/v1", "source_authority_tampers_detected": source_tampers, "tamper_fixtures_detected": detected}
def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument("--self-test", action="store_true"); parser.add_argument("--proposal-smoke", action="store_true"); parser.add_argument("--input-manifest", type=Path); parser.add_argument("--authorization", type=Path); parser.add_argument("--output", type=Path); parser.add_argument("shards", nargs="*", type=Path); args = parser.parse_args()
    if args.self_test:
        if args.proposal_smoke or args.input_manifest or args.authorization or args.output or args.shards: parser.error("--self-test is exclusive")
        print(canonical_json(self_test())); return
    if args.proposal_smoke:
        if not args.input_manifest or args.authorization or args.output or args.shards: parser.error("--proposal-smoke requires only --input-manifest")
        print(canonical_json(validate_formal_proposals(args.input_manifest))); return
    if not args.input_manifest or not args.authorization or not args.output or len(args.shards) != CASE_COUNT: parser.error("normal aggregation requires named paths and 12 shards")
    result = aggregate_files(args.input_manifest, args.authorization, args.shards); args.output.parent.mkdir(parents=True, exist_ok=True); args.output.write_text(canonical_json(result) + "\n")
if __name__ == "__main__": main()
