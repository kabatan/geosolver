#!/usr/bin/env python3
"""Independent, stdlib-only aggregation of EXP-DISC-001 T0 raw shards."""
from __future__ import annotations
import argparse, hashlib, json
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable, Sequence
INPUT_SCHEMA = "geotarget.discovery-t0-input/v1"
RAW_SCHEMA = "geotarget.discovery-t0-raw/v1"
OUTPUT_SCHEMA = "geotarget.discovery-t0-aggregate/v1"
EXPERIMENT = "EXP-DISC-001"
PREFIXES = (8, 16, 32, 64, 128)
THRESHOLDS = (600, 1_200, 2_400, 4_800)
ATTEMPTS_PER_STREAM = 128
CALLBACK_CAP = 600
RAW_H0 = "D-CURRENT-COUNTER-HALTON-MIX"
AUTH_SCHEMA = "geotarget.discovery-t0-outcome-authorization/v1"
def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()
def canonical_json(document: Any) -> str:
    return json.dumps(document, ensure_ascii=False, allow_nan=False, sort_keys=True,
                      separators=(",", ":"))
def _method(row: dict[str, Any]) -> str:
    value = row.get("method", row.get("variant"))
    if not isinstance(value, str) or not value:
        raise ValueError("row lacks a method")
    return value
def _index(row: dict[str, Any]) -> int:
    value = row.get("proposal_index", row.get("start_index"))
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError("attempt lacks an integer proposal index")
    return value
def _observed(attempt: dict[str, Any]) -> int:
    value = attempt.get("observed_evaluations", attempt.get("evaluations"))
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError("attempt has invalid observed callback work")
    return value
def _reported(attempt: dict[str, Any]) -> int:
    value = attempt.get("reported_evaluations", attempt.get("evaluations"))
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError("attempt has invalid reported callback work")
    return value
def _unsafe(attempt: dict[str, Any]) -> bool:
    return bool(attempt["assessor_qualified"]) and (
        not bool(attempt["assessor_gold_matched"])
        or bool(attempt["assessor_target_ambiguous"])
    )
def _safe_hits(attempts: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        row
        for row in attempts
        if bool(row["assessor_qualified"])
        and bool(row["assessor_gold_matched"])
        and not bool(row["assessor_target_ambiguous"])
    ]
def prefix_metrics(
    attempts: Sequence[dict[str, Any]], target_count: int, configuration_count: int
) -> dict[str, Any]:
    hits = _safe_hits(attempts)
    targets = [row.get("assessor_matched_target_id") for row in hits]
    configurations = [row.get("assessor_matched_configuration") for row in hits]
    if any(value is None for value in targets + configurations):
        raise ValueError("a qualified Gold hit lacks its assessor identity")
    if any(
        isinstance(value, bool)
        or not isinstance(value, int)
        or not 1 <= value <= configuration_count
        for value in configurations
    ):
        raise ValueError("assessor configuration lies outside the input manifest")
    distinct_targets = set(map(str, targets))
    if len(distinct_targets) > target_count:
        raise ValueError("assessor found more distinct targets than the input manifest")
    unsafe = sum(_unsafe(row) for row in attempts)
    ambiguity = sum(
        bool(row["assessor_qualified"]) and bool(row["assessor_target_ambiguous"])
        for row in attempts
    )
    false_targets = sum(
        bool(row["assessor_qualified"])
        and not bool(row["assessor_numeric_target_matched"])
        and not bool(row["assessor_target_ambiguous"])
        for row in attempts
    )
    mismatches = sum(
        _observed(row) != _reported(row) or bool(row.get("evaluation_count_mismatch"))
        for row in attempts
    )
    cap = sum(_observed(row) > CALLBACK_CAP or _reported(row) > CALLBACK_CAP
              for row in attempts)
    return {
        "assessor_ambiguity": ambiguity,
        "assessor_distinct_targets_found": len(distinct_targets),
        "assessor_false_targets": false_targets,
        "assessor_qualified": sum(bool(row["assessor_qualified"]) for row in attempts),
        "assessor_qualified_distinct_target_recall": len(distinct_targets) / target_count,
        "assessor_safe_full": len(distinct_targets) == target_count and unsafe == 0,
        "assessor_unsafe": unsafe,
        "callback_cap_violations": cap,
        "callback_work": sum(_observed(row) for row in attempts),
        "duplicate_configuration_hits": len(configurations) - len(set(configurations)),
        "duplicate_target_hits": len(targets) - len(distinct_targets),
        "evaluation_count_mismatches": mismatches,
    }
def case_prefix_rows(
    attempts: Sequence[dict[str, Any]], case: dict[str, Any], method: str
) -> list[dict[str, Any]]:
    rows = []
    for prefix in PREFIXES:
        row = prefix_metrics(
            attempts[:prefix], int(case["target_count"]), int(case["configuration_count"])
        )
        row.update(
            case_id=case["case_id"], case_index=int(case["case_index"]),
            configuration_count=int(case["configuration_count"]),
            family_id=case["family_id"], instance_id=case["instance_id"],
            method=method, prefix=prefix, target_count=int(case["target_count"]),
        )
        rows.append(row)
    return rows
def callback_rows(
    attempts: Sequence[dict[str, Any]], case: dict[str, Any], method: str
) -> list[dict[str, Any]]:
    rows, work, threshold_index = [], 0, 0
    for completed, attempt in enumerate(attempts, start=1):
        work += _observed(attempt)
        while threshold_index < len(THRESHOLDS) and work >= THRESHOLDS[threshold_index]:
            row = prefix_metrics(
                attempts[:completed], int(case["target_count"]),
                int(case["configuration_count"]),
            )
            row.update(
                callback_threshold=THRESHOLDS[threshold_index], case_id=case["case_id"],
                case_index=int(case["case_index"]), crossing_callback_work=work,
                crossing_proposal_index=completed, family_id=case["family_id"],
                instance_id=case["instance_id"], method=method,
                target_count=int(case["target_count"]),
            )
            rows.append(row)
            threshold_index += 1
    return rows
def suffix_work(attempts: Sequence[dict[str, Any]], target_count: int, configuration_count: int) -> int | None:
    for end in range(1, len(attempts) + 1):
        if (prefix_metrics(attempts[:end], target_count, configuration_count)["assessor_safe_full"]
                and not any(_unsafe(row) for row in attempts[end:])):
            return sum(_observed(row) for row in attempts[:end])
    return None
ALIASES = {
    "prefix": ("prefix", "proposal_prefix"),
    "assessor_distinct_targets_found": (
        "assessor_distinct_targets_found", "assessor_qualified_targets_found",
        "assessor_targets_found",
    ),
    "assessor_qualified_distinct_target_recall": (
        "assessor_qualified_distinct_target_recall", "assessor_qualified_target_recall",
        "assessor_target_recall",
    ),
    "assessor_safe_full": ("assessor_safe_full", "assessor_safe_all_targets"),
    "assessor_unsafe": ("assessor_unsafe", "assessor_qualified_gold_inconsistent"),
    "callback_work": ("callback_work", "evaluations"),
    "crossing_proposal_index": ("crossing_proposal_index", "crossing_start_index"),
}
def _value(row: dict[str, Any], field: str) -> Any:
    for candidate in ALIASES.get(field, (field,)):
        if candidate in row:
            return row[candidate]
    raise KeyError(field)
def row_mismatches(
    observed: Sequence[dict[str, Any]], expected: Sequence[dict[str, Any]],
    keys: Sequence[str], fields: Sequence[str],
) -> int:
    def identity(row: dict[str, Any]) -> tuple[Any, ...]:
        return tuple(_value(row, field) for field in keys)
    observed_by_key = {identity(row): row for row in observed}
    expected_by_key = {identity(row): row for row in expected}
    if len(observed_by_key) != len(observed) or len(expected_by_key) != len(expected):
        return 1
    mismatches = len(set(observed_by_key) ^ set(expected_by_key))
    for key in set(observed_by_key) & set(expected_by_key):
        left, right = observed_by_key[key], expected_by_key[key]
        for field in fields:
            wanted = right[field]
            try:
                actual = _value(left, field)
            except KeyError:
                mismatches += 1
                break
            if isinstance(wanted, float):
                different = not isinstance(actual, (int, float)) or abs(actual - wanted) > 1e-15
            else:
                different = actual != wanted
            if different:
                mismatches += 1
                break
    return mismatches
def _validate_input(document: dict[str, Any]) -> tuple[list[dict[str, Any]], tuple[str, ...]]:
    if document.get("schema_version") != INPUT_SCHEMA or document.get("experiment_id") != EXPERIMENT:
        raise ValueError("unexpected T0 input manifest")
    cases, methods = document.get("cases"), tuple(document.get("methods", ()))
    if not isinstance(cases, list) or len(cases) != 6 or len(methods) != 7 or len(set(methods)) != 7 or methods[3] != RAW_H0:
        raise ValueError("T0 input manifest must contain 6 cases and 7 methods")
    if tuple(document.get("prefixes", ())) != PREFIXES or tuple(document.get("callback_thresholds", ())) != THRESHOLDS:
        raise ValueError("T0 input checkpoints differ")
    if (document.get("lab_confirmation_512_768") is not False or document.get("attempt_evaluation_limit") != CALLBACK_CAP
            or document.get("target_count") != sum(int(case["target_count"]) for case in cases)):
        raise ValueError("T0 laboratory input must not claim 512/768-bit confirmation")
    if [int(case["case_index"]) for case in cases] != list(range(1, 7)):
        raise ValueError("T0 input case indices differ")
    return cases, methods
def _validate_authorization(document: dict[str, Any], input_sha: str, own_sha: str) -> None:
    if document.get("schema_version") != AUTH_SCHEMA or document.get("outcome_execution_authorized") is not True:
        raise ValueError("T0 outcome execution is not authorized")
    binding = document.get("input_manifest", {})
    if binding.get("sha256") != input_sha:
        raise ValueError("authorization binds another input manifest")
    if document.get("aggregator_source_sha256") != own_sha:
        raise ValueError("authorization binds another aggregator source")
    if not isinstance(document.get("runner_source_sha256"), str):
        raise ValueError("authorization lacks the runner source hash")
    preregistration = document.get("preregistration", {})
    if not isinstance(preregistration.get("sha256"), str):
        raise ValueError("authorization lacks its preregistration hash")
def _case_manifest_matches(observed: dict[str, Any], expected: dict[str, Any]) -> bool:
    fields = ("case_id", "case_index", "configuration_count", "dimension", "family_id", "instance_id",
              "residual_dimension", "source_replay_checksum", "target_count")
    return all(observed.get(field) == expected.get(field) for field in fields)
def aggregate_documents(
    input_document: dict[str, Any], authorization: dict[str, Any],
    shards: Sequence[dict[str, Any]], *, input_sha: str, authorization_sha: str,
    aggregator_sha: str,
) -> dict[str, Any]:
    cases, methods = _validate_input(input_document)
    _validate_authorization(authorization, input_sha, aggregator_sha)
    if len(shards) != 6 or sorted(int(row.get("case_index", 0)) for row in shards) != list(range(1, 7)):
        raise ValueError("raw T0 case shards are missing or duplicated")
    revisions, case_rows, crossing_rows = set(), [], []
    accounting = defaultdict(int)
    for shard in sorted(shards, key=lambda row: int(row["case_index"])):
        index = int(shard["case_index"])
        case = cases[index - 1]
        if any((
            shard.get("schema_version") != RAW_SCHEMA, shard.get("experiment_id") != EXPERIMENT,
            shard.get("stage") != "t0", shard.get("partition") != "development",
            shard.get("lab_confirmation_512_768") is not False,
            shard.get("input_manifest", {}).get("sha256") != input_sha,
            shard.get("authorization", {}).get("sha256") != authorization_sha,
            not _case_manifest_matches(shard.get("case_manifest", {}), case),
            tuple(shard.get("stream_order", ())) != methods,
            not isinstance(shard.get("thread_contract"), dict),
            shard.get("thread_contract", {}).get("julia_threads") != 1,
            shard.get("thread_contract", {}).get("blas_threads") != 1,
        )):
            raise ValueError(f"raw T0 shard {index} contract mismatch")
        revision = shard.get("revision", {})
        if revision.get("git_dirty") is not False or not revision.get("git_head"):
            raise ValueError("raw T0 shard did not run from a clean commit")
        revisions.add(revision["git_head"])
        streams = shard.get("streams", [])
        if len(streams) != 7 or tuple(_method(row) for row in streams) != methods:
            raise ValueError(f"raw T0 shard {index} stream order differs")
        expected_proposals = {row["method"]: row for row in case["proposals"]}
        for stream in streams:
            method, attempts = _method(stream), stream.get("attempts", [])
            expected_scope = "h0-raw-attribution-only" if method == RAW_H0 else "fixed-source"
            if stream.get("source_scope") != expected_scope or stream.get("proposal") != expected_proposals[method]:
                raise ValueError(f"raw T0 proposal binding differs for case {index} {method}")
            if len(attempts) != ATTEMPTS_PER_STREAM or [_index(row) for row in attempts] != list(range(1, 129)):
                raise ValueError(f"raw T0 attempts differ for case {index} {method}")
            expected_prefixes = case_prefix_rows(attempts, case, method)
            expected_crossings = callback_rows(attempts, case, method)
            summaries = stream.get("proposal_summaries", [])
            snapshots = stream.get("callback_snapshots", [])
            if len(summaries) != 5:
                raise ValueError("each T0 stream must contain five proposal summaries")
            accounting["proposal_summary_mismatches"] += row_mismatches(
                summaries, expected_prefixes, ("prefix",),
                ("assessor_qualified", "assessor_distinct_targets_found",
                 "assessor_qualified_distinct_target_recall", "assessor_safe_full",
                 "assessor_unsafe", "callback_work", "evaluation_count_mismatches"),
            )
            accounting["callback_snapshot_mismatches"] += row_mismatches(
                snapshots, expected_crossings, ("callback_threshold",),
                ("assessor_qualified", "assessor_distinct_targets_found",
                 "assessor_qualified_distinct_target_recall", "assessor_safe_full",
                 "assessor_unsafe", "crossing_callback_work", "crossing_proposal_index"),
            )
            terminal = stream.get("terminal", {})
            full = expected_prefixes[-1]
            suffix = suffix_work(attempts, int(case["target_count"]), int(case["configuration_count"]))
            accounting["terminal_mismatches"] += any((
                terminal.get("attempt_count") != 128,
                terminal.get("callback_work") != full["callback_work"],
                terminal.get("evaluation_count_mismatches") != full["evaluation_count_mismatches"],
                terminal.get("exceptions") != sum(row.get("exception") is not None for row in attempts),
                terminal.get("runner_budget_exhausted") != sum(bool(row.get("budget_exhausted")) for row in attempts),
                terminal.get("local_cap_violations") != full["callback_cap_violations"],
                terminal.get("suffix_stable_assessor_work") != suffix,
            ))
            audit = expected_proposals[method].get("iid_service_audit")
            if method in (methods[0], RAW_H0, methods[-1]):
                if not isinstance(audit, dict):
                    raise ValueError("IID-serving stream lacks its frozen service audit")
                accounting["iid_bounded_gap_violations"] += not bool(audit.get("bounded_gap"))
                accounting["iid_starvation_count"] += int(audit.get("starvation_count", 0))
                accounting["iid_violation_prefix_count"] += len(audit.get("violation_prefixes", []))
            elif audit is not None:
                raise ValueError("non-IID stream unexpectedly carries an IID service audit")
            accounting["evaluation_count_mismatches"] += full["evaluation_count_mismatches"]
            accounting["callback_cap_violations"] += full["callback_cap_violations"]
            accounting["exceptions"] += sum(row.get("exception") is not None for row in attempts)
            accounting["runner_budget_exhausted"] += sum(bool(row.get("budget_exhausted")) for row in attempts)
            case_rows.extend(expected_prefixes)
            crossing_rows.extend(expected_crossings)
    if len(revisions) != 1:
        raise ValueError("raw T0 shards came from different revisions")
    aggregates = []
    for method in methods:
        for prefix in PREFIXES:
            selected = [row for row in case_rows if row["method"] == method and row["prefix"] == prefix]
            targets = sum(row["target_count"] for row in selected)
            aggregate = {
                "assessor_distinct_targets_found": sum(row["assessor_distinct_targets_found"] for row in selected),
                "assessor_safe_full_cases": sum(row["assessor_safe_full"] for row in selected),
                "case_count": len(selected), "method": method, "prefix": prefix,
                "source_scope": "h0-raw-attribution-only" if method == RAW_H0 else "fixed-source",
                "target_count": targets,
            }
            aggregate["assessor_qualified_distinct_target_recall"] = aggregate["assessor_distinct_targets_found"] / targets
            aggregate["assessor_safe_full_rate"] = aggregate["assessor_safe_full_cases"] / len(selected)
            for field in ("assessor_qualified", "assessor_unsafe", "assessor_ambiguity",
                          "assessor_false_targets", "duplicate_configuration_hits",
                          "duplicate_target_hits", "callback_work", "evaluation_count_mismatches",
                          "callback_cap_violations"):
                aggregate[field] = sum(row[field] for row in selected)
            aggregates.append(aggregate)
    return {
        "accounting": dict(sorted(accounting.items())),
        "authorization_sha256": authorization_sha,
        "callback_rows": crossing_rows,
        "case_rows": case_rows,
        "experiment_id": EXPERIMENT,
        "input_manifest_sha256": input_sha,
        "lab_confirmation": False,
        "lab_confirmation_512_768": False,
        "method_aggregates": aggregates,
        "raw_counter_halton_scope": "H0 attribution only; not the complete adaptive H0 control",
        "revision": revisions.pop(),
        "schema_version": OUTPUT_SCHEMA,
        "stage": "t0",
    }
def aggregate_files(input_path: Path, authorization_path: Path, shard_paths: Sequence[Path]) -> dict[str, Any]:
    input_sha, auth_sha = sha256(input_path), sha256(authorization_path)
    return aggregate_documents(
        json.loads(input_path.read_text(encoding="utf-8")),
        json.loads(authorization_path.read_text(encoding="utf-8")),
        [json.loads(path.read_text(encoding="utf-8")) for path in shard_paths],
        input_sha=input_sha, authorization_sha=auth_sha, aggregator_sha=sha256(Path(__file__)),
    )
def self_test() -> dict[str, Any]:
    methods = ("D0-IID-ALL", "D1-SOBOL-ALL", "D-HALTON-ALL", RAW_H0,
               "D2O-RQMC-OWEN-ALL", "D2M-RQMC-MATOUSEK-ALL",
               "D3-OWEN-MIXED-25IID-75RQMC")
    def service(method: str) -> dict[str, Any] | None:
        return ({"bounded_gap": True, "starvation_count": 0, "violation_prefixes": []}
                if method in (methods[0], RAW_H0, methods[-1]) else None)
    cases = [{"case_id": f"case-{i}", "case_index": i, "configuration_count": 1,
              "dimension": 2, "family_id": "MULTIROOT-WARPED", "instance_id": f"instance-{i}",
              "residual_dimension": 2, "source_replay_checksum": f"replay-{i}", "target_count": 1,
              "proposals": [{"method": method, "path": f"p-{i}-{j}",
                             "iid_service_audit": service(method)}
                            for j, method in enumerate(methods)]} for i in range(1, 7)]
    manifest = {"schema_version": INPUT_SCHEMA, "experiment_id": EXPERIMENT, "cases": cases,
                "methods": list(methods), "prefixes": list(PREFIXES),
                "callback_thresholds": list(THRESHOLDS), "attempt_evaluation_limit": 600,
                "target_count": 6, "lab_confirmation_512_768": False}
    authorization = {"schema_version": AUTH_SCHEMA, "outcome_execution_authorized": True,
                     "input_manifest": {"sha256": "input"}, "preregistration": {"sha256": "pre"},
                     "runner_source_sha256": "runner", "aggregator_source_sha256": "aggregator"}
    def attempts() -> list[dict[str, Any]]:
        result = []
        for index in range(1, 129):
            hit = index == 1
            result.append({"variant": "E4", "start_index": index, "assessor_qualified": hit,
                           "assessor_gold_matched": hit, "assessor_target_ambiguous": False,
                           "assessor_numeric_target_matched": hit, "assessor_matched_target_id": "target" if hit else None,
                           "assessor_matched_configuration": 1 if hit else None, "observed_evaluations": 10,
                           "reported_evaluations": 10, "evaluation_count_mismatch": False,
                           "exception": None, "budget_exhausted": False})
        return result
    def stream(case: dict[str, Any], method: str, proposal: dict[str, Any]) -> dict[str, Any]:
        raw = attempts()
        summaries = [{"variant": "E4", "prefix": row["prefix"], "assessor_qualified": row["assessor_qualified"], "assessor_qualified_targets_found": row["assessor_distinct_targets_found"], "assessor_qualified_target_recall": row["assessor_qualified_distinct_target_recall"], "assessor_safe_all_targets": row["assessor_safe_full"], "assessor_qualified_gold_inconsistent": row["assessor_unsafe"], "evaluations": row["callback_work"], "evaluation_count_mismatches": row["evaluation_count_mismatches"]} for row in case_prefix_rows(raw, case, method)]
        snapshots = [{"callback_threshold": row["callback_threshold"], "crossing_callback_work": row["crossing_callback_work"], "crossing_start_index": row["crossing_proposal_index"], "assessor_qualified": row["assessor_qualified"], "assessor_targets_found": row["assessor_distinct_targets_found"], "assessor_target_recall": row["assessor_qualified_distinct_target_recall"], "assessor_unsafe": row["assessor_unsafe"], "assessor_safe_full": row["assessor_safe_full"]} for row in callback_rows(raw, case, method)]
        terminal = {"attempt_count": 128, "callback_work": 1280, "evaluation_count_mismatches": 0,
                    "exceptions": 0, "runner_budget_exhausted": 0, "local_cap_violations": 0,
                    "suffix_stable_assessor_work": 10}
        return {"method": method, "source_scope": "h0-raw-attribution-only" if method == RAW_H0 else "fixed-source", "proposal": proposal, "attempts": raw, "proposal_summaries": summaries, "callback_snapshots": snapshots, "terminal": terminal}
    shards = [{"schema_version": RAW_SCHEMA, "experiment_id": EXPERIMENT, "stage": "t0",
               "partition": "development", "case_index": case["case_index"],
               "lab_confirmation_512_768": False, "input_manifest": {"sha256": "input"},
               "authorization": {"sha256": "authorization"},
               "revision": {"git_head": "fixture", "git_dirty": False},
               "thread_contract": {"julia_threads": 1, "blas_threads": 1},
               "case_manifest": case, "stream_order": list(methods),
               "streams": [stream(case, method, proposal)
                           for method, proposal in zip(methods, case["proposals"], strict=True)]}
              for case in cases]
    clean = aggregate_documents(manifest, authorization, list(reversed(shards)), input_sha="input",
                                authorization_sha="authorization", aggregator_sha="aggregator")
    assert all(value == 0 for value in clean["accounting"].values())
    shards[0]["streams"][0]["proposal_summaries"][0]["evaluations"] += 1
    tampered = aggregate_documents(manifest, authorization, shards, input_sha="input",
                                   authorization_sha="authorization", aggregator_sha="aggregator")
    assert tampered["accounting"]["proposal_summary_mismatches"] > 0
    cases[0]["proposals"][0]["iid_service_audit"].update(bounded_gap=False, starvation_count=1,
                                                           violation_prefixes=[4])
    violated = aggregate_documents(manifest, authorization, shards, input_sha="input",
                                   authorization_sha="authorization", aggregator_sha="aggregator")
    assert violated["accounting"]["iid_bounded_gap_violations"] > 0
    return {"schema_version": "geotarget.discovery-t0-aggregate-self-test/v1",
            "fixture_attempt_count": 6 * 7 * 128, "outcomes_executed": False,
            "aggregate_success": True, "tamper_detected": True, "iid_violation_detected": True}
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
            parser.error("--self-test is mutually exclusive with normal aggregation arguments")
        print(canonical_json(self_test()))
        return
    if not args.input_manifest or not args.authorization or not args.output or len(args.shards) != 6:
        parser.error("normal aggregation requires three named paths and exactly six shards")
    result = aggregate_files(args.input_manifest, args.authorization, args.shards)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(canonical_json(result) + "\n", encoding="utf-8")
if __name__ == "__main__":
    main()
