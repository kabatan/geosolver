#!/usr/bin/env python3
"""Stdlib-only independent aggregation for EXP-DISC-001 formal Stage A."""
from __future__ import annotations

import argparse, hashlib, importlib.util, json, random, sys
from collections import Counter, defaultdict
from pathlib import Path
from statistics import fmean
from typing import Any, Sequence


def _load_t0():
    path = Path(__file__).with_name("aggregate_t0.py")
    spec = importlib.util.spec_from_file_location("geotarget_disc001_t0_metrics", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot import aggregate_t0.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


T0 = _load_t0()  # Reuse the frozen attempt-to-metric implementation; do not fork it.
INPUT_SCHEMA = "geotarget.discovery-stagea-input/v1"
RAW_SCHEMA = "geotarget.discovery-stagea-raw/v1"
AUTH_SCHEMA = "geotarget.discovery-stagea-outcome-authorization/v1"
OUTPUT_SCHEMA = "geotarget.discovery-stagea-aggregate/v1"
EXPERIMENT, STAGE, PARTITION = "EXP-DISC-001", "stage-a-source-ablation", "development"
PREFIXES, THRESHOLDS, CAP, CENSOR = T0.PREFIXES, T0.THRESHOLDS, 600, 4_800
D0, D1, HALTON = "D0-IID-ALL", "D1-SOBOL-ALL", "D-HALTON-ALL"
CURRENT = "D-CURRENT-COUNTER-HALTON-MIX"
D2O, D2M = "D2O-RQMC-OWEN-ALL", "D2M-RQMC-MATOUSEK-ALL"
D3 = "D3-OWEN-MIXED-25IID-75RQMC"
METHODS = (D0, D1, HALTON, CURRENT, D2O, D2M, D3)
RANDOMIZED = (D0, CURRENT, D2O, D2M, D3)
IID_METHODS = frozenset((D0, CURRENT, D3))
BOOTSTRAP_SEED, BOOTSTRAP_RESAMPLES = 2_002, 10_000
BOUNDARY_EPS = 1.0e-12
TRUTH_KEYS = frozenset(("case_id", "family_id", "formal_case_id", "gold_configurations",
                        "gold_targets", "instance_id", "source_index", "target_count"))


def _methods(replicate: int) -> tuple[str, ...]:
    return METHODS if replicate == 1 else RANDOMIZED


def _replicate(row: dict[str, Any]) -> int:
    value = row.get("replicate", row.get("replicate_index"))
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError("record lacks an integer replicate")
    return value


def _sha_field(value: Any, label: str) -> str:
    if not isinstance(value, str) or len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
        raise ValueError(f"{label} is not a lowercase SHA-256")
    return value


def _proposal_is_truth_free(value: Any) -> bool:
    if isinstance(value, dict):
        return not any(str(key) in TRUTH_KEYS or not _proposal_is_truth_free(child)
                       for key, child in value.items())
    if isinstance(value, list):
        return all(_proposal_is_truth_free(child) for child in value)
    return True


def _audit_iid(proposal: dict[str, Any], accounting: defaultdict[str, int]) -> None:
    method, audit = proposal.get("method"), proposal.get("iid_service_audit")
    if method not in IID_METHODS:
        if audit is not None:
            raise ValueError("non-IID stream carries an IID service audit")
        return
    if not isinstance(audit, dict):
        raise ValueError("IID-serving stream lacks its service audit")
    accounting["iid_bounded_gap_violations"] += not bool(audit.get("bounded_gap"))
    accounting["iid_starvation_count"] += int(audit.get("starvation_count", 0))
    accounting["iid_violation_prefix_count"] += len(audit.get("violation_prefixes", []))


def _validate_input(document: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[tuple[int, int, str], dict[str, Any]]]:
    if (document.get("schema_version"), document.get("experiment_id"), document.get("stage"),
            document.get("partition")) != (INPUT_SCHEMA, EXPERIMENT, STAGE, PARTITION):
        raise ValueError("unexpected Stage A input manifest")
    cases = document.get("cases")
    if not isinstance(cases, list) or len(cases) != 24 or document.get("case_count") != 24:
        raise ValueError("Stage A requires exactly 24 cases")
    if (document.get("replicate_count") != 10 or document.get("randomized_replicate_count") != 10
            or document.get("proposal_count") != 1_248):
        raise ValueError("Stage A replicate/proposal count differs")
    if document.get("lab_confirmation_512_768") is not False:
        raise ValueError("Stage A laboratory input cannot claim high-precision confirmation")
    if tuple(document.get("methods", ())) != METHODS or tuple(document.get("prefixes", ())) != PREFIXES:
        raise ValueError("Stage A method or prefix order differs")
    if tuple(document.get("callback_thresholds", ())) != THRESHOLDS or document.get("attempt_evaluation_limit") != CAP:
        raise ValueError("Stage A callback contract differs")
    if document.get("method_replicate_counts") != {method: (1 if method in (D1, HALTON) else 10) for method in METHODS}:
        raise ValueError("Stage A method replicate counts differ")
    families = Counter(case.get("family_id") for case in cases)
    if len(families) != 4 or set(families.values()) != {6}:
        raise ValueError("Stage A requires four balanced six-case families")
    critical = document.get("critical_strata")
    if tuple(critical or ()) != tuple(f"S{i}" for i in range(1, 7)):
        raise ValueError("Stage A requires six frozen critical strata")
    proposals: dict[tuple[int, int, str], dict[str, Any]] = {}
    paths, seeds, observed_strata = set(), set(), set()
    for index, case in enumerate(cases, 1):
        if case.get("case_index") != index or case.get("formal_case_id") != f"EXP-DISC-001-A-{index:03d}":
            raise ValueError("Stage A case order differs")
        strata = case.get("strata")
        if not isinstance(strata, list) or not strata or not set(strata) <= set(critical):
            raise ValueError("case strata differ from the frozen critical strata")
        observed_strata.update(strata)
        rows = case.get("proposals")
        if not isinstance(rows, list) or len(rows) != 52:
            raise ValueError("each Stage A case requires 52 proposal artifacts")
        for proposal in rows:
            if not _proposal_is_truth_free(proposal):
                raise ValueError("proposal runtime binding contains scorer truth")
            method, replicate = proposal.get("method"), _replicate(proposal)
            key = (index, replicate, method)
            if replicate not in range(1, 11) or method not in _methods(replicate) or key in proposals:
                raise ValueError("invalid or duplicate Stage A proposal binding")
            seed = proposal.get("replicate_seed")
            if not isinstance(seed, str) or not seed.isdecimal() or not 0 <= int(seed) < 2**64 or seed in seeds:
                raise ValueError("replicate seed is invalid or duplicated")
            path = proposal.get("path")
            if not isinstance(path, str) or not path or path in paths:
                raise ValueError("proposal path is invalid or duplicated")
            _sha_field(proposal.get("artifact_sha256"), "artifact hash")
            _sha_field(proposal.get("file_sha256"), "proposal file hash")
            if method == D3:
                mixed = proposal.get("mixed_sources")
                if not isinstance(mixed, dict) or set(mixed) != {"iid", "rqmc"}:
                    raise ValueError("D3 lacks its two frozen source bindings")
                for source in mixed.values():
                    if not isinstance(source, dict) or not isinstance(source.get("path"), str):
                        raise ValueError("D3 source binding is malformed")
                    _sha_field(source.get("artifact_sha256"), "D3 source artifact hash")
            proposals[key] = proposal
            paths.add(path); seeds.add(seed)
        if {(rep, method) for case_index, rep, method in proposals if case_index == index} != {
                (rep, method) for rep in range(1, 11) for method in _methods(rep)}:
            raise ValueError("case proposal matrix is incomplete")
    if observed_strata != set(critical) or len(proposals) != 1_248:
        raise ValueError("Stage A stratum/proposal coverage differs")
    if document.get("target_count") != 64 or document.get("target_count") != sum(
            int(case["target_count"]) for case in cases):
        raise ValueError("Stage A target denominator differs")
    return cases, proposals


def _validate_authorization(auth: dict[str, Any], manifest: dict[str, Any], input_sha: str, own_sha: str) -> None:
    if auth.get("schema_version") != AUTH_SCHEMA or auth.get("outcome_execution_authorized") is not True:
        raise ValueError("Stage A outcomes are not authorized")
    if auth.get("input_manifest", {}).get("sha256") != input_sha or auth.get("aggregator_source_sha256") != own_sha:
        raise ValueError("authorization input/aggregator binding differs")
    if auth.get("runner_source_sha256") != T0.sha256(Path(__file__).with_name("run_stagea_outcomes.jl")):
        raise ValueError("authorization runner binding differs")
    prereg = manifest.get("preregistration", {})
    if auth.get("preregistration", {}).get("sha256") != prereg.get("sha256"):
        raise ValueError("authorization preregistration binding differs")
    dependencies = auth.get("dependency_source_sha256", {})
    dependency_paths = {
        "research/experiments/EXP-DISC-001/aggregate_t0.py": Path(__file__).with_name("aggregate_t0.py"),
        "research/experiments/EXP-DISC-001/run_t0_outcomes.jl": Path(__file__).with_name("run_t0_outcomes.jl"),
    }
    if not isinstance(dependencies, dict) or any(
            dependencies.get(relative) != T0.sha256(path)
            for relative, path in dependency_paths.items()):
        raise ValueError("authorization Stage A dependency binding differs")


CASE_FIELDS = ("formal_case_id", "case_index", "instance_id", "family_id", "strata", "dimension",
               "residual_dimension", "configuration_count", "target_count", "source_replay_checksum",
               "parameters", "source")


def _case_matches(observed: dict[str, Any], expected: dict[str, Any]) -> bool:
    return isinstance(observed, dict) and all(observed.get(field) == expected.get(field) for field in CASE_FIELDS)


def _metric_case(case: dict[str, Any]) -> dict[str, Any]:
    return case if "case_id" in case else {**case, "case_id": case["formal_case_id"]}


def _thread_ok(thread: Any, case_index: int, replicate: int) -> bool:
    if not isinstance(thread, dict):
        return False
    cpu = (case_index + replicate - 2) % 16
    env = thread.get("environment", {})
    return all((
        thread.get("julia_threads") == 1, thread.get("blas_threads") == 1,
        thread.get("assigned_cpu") == cpu, thread.get("cpus_allowed_list") == str(cpu),
        thread.get("case_process_limit") == 16, thread.get("solver_worker_count") == 1,
        isinstance(env, dict), all(env.get(name) == "1" for name in
            ("JULIA_NUM_THREADS", "OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS")),
    ))


def _annotate(rows: list[dict[str, Any]], case: dict[str, Any], replicate: int,
              attempts: Sequence[dict[str, Any]]) -> None:
    for row in rows:
        prefix = int(row["prefix"])
        suffix = T0.suffix_work(attempts[:prefix], int(case["target_count"]), int(case["configuration_count"]))
        row.update(replicate=replicate, strata=case["strata"],
                   right_censored_suffix_work=CENSOR if suffix is None else min(suffix, CENSOR))


def _complete_callback_rows(attempts: Sequence[dict[str, Any]], case: dict[str, Any],
                            method: str) -> list[dict[str, Any]]:
    metric_case = _metric_case(case)
    rows = T0.callback_rows(attempts, metric_case, method)
    for row in rows:
        row["threshold_reached"] = True
    reached = {row["callback_threshold"] for row in rows}
    terminal_work = sum(T0._observed(row) for row in attempts)
    for threshold in THRESHOLDS:
        if threshold in reached:
            continue
        row = T0.prefix_metrics(
            attempts, int(case["target_count"]), int(case["configuration_count"]),
        )
        row.update(callback_threshold=threshold, case_id=case["formal_case_id"],
                   case_index=int(case["case_index"]), crossing_callback_work=terminal_work,
                   crossing_proposal_index=len(attempts), family_id=case["family_id"],
                   instance_id=case["instance_id"], method=method,
                   target_count=int(case["target_count"]), threshold_reached=False)
        rows.append(row)
    return sorted(rows, key=lambda row: int(row["callback_threshold"]))


def _safety(attempts: Sequence[dict[str, Any]], accounting: defaultdict[str, int]) -> None:
    accounting["reported_accepted_canonical_invalid"] += sum(
        bool(row.get("reported_accepted")) and not bool(row.get("canonical_valid")) for row in attempts)
    accounting["reported_accepted_gold_inconsistent"] += sum(
        bool(row.get("reported_accepted")) and not bool(row.get("gold_matched")) for row in attempts)
    accounting["reported_accepted_numeric_target_only"] += sum(
        bool(row.get("reported_accepted")) and bool(row.get("numeric_target_matched"))
        and not bool(row.get("gold_matched")) for row in attempts)
    accounting["reported_accepted_ambiguous"] += sum(
        bool(row.get("reported_accepted")) and bool(row.get("target_ambiguous")) for row in attempts)


def _mean(rows: Sequence[dict[str, Any]], field: str) -> float:
    return fmean(float(row[field]) for row in rows)


def _family_effects(rows: Sequence[dict[str, Any]], candidate: str, control: str,
                    threshold: int) -> tuple[dict[str, dict[str, float]], dict[str, list[dict[str, float]]]]:
    selected = [row for row in rows if row["callback_threshold"] == threshold
                and row["method"] in (candidate, control)]
    by_key = {(row["case_index"], row["replicate"], row["method"]): row for row in selected}
    keys = {(case, rep) for case, rep, method in by_key if method == candidate}
    if keys != {(case, rep) for case, rep, method in by_key if method == control} or len(keys) != 240:
        raise ValueError("formal randomized comparison lost its paired 24x10 layout")
    families: dict[str, dict[int, list[tuple[dict[str, Any], dict[str, Any]]]]] = defaultdict(
        lambda: defaultdict(list))
    for case, rep in sorted(keys):
        left, right = by_key[(case, rep, candidate)], by_key[(case, rep, control)]
        if left["family_id"] != right["family_id"] or left["strata"] != right["strata"]:
            raise ValueError("paired family/stratum identity differs")
        families[left["family_id"]][case].append((left, right))
    effects, case_effects = {}, {}
    for family, grouped in sorted(families.items()):
        case_effects[family] = []
        for case_index, pairs in sorted(grouped.items()):
            if len(pairs) != 10:
                raise ValueError("bootstrap case did not preserve ten paired replicates")
            left, right = [p[0] for p in pairs], [p[1] for p in pairs]
            cwork = _mean(left, "right_censored_suffix_work")
            bwork = _mean(right, "right_censored_suffix_work")
            case_effects[family].append({"case_index": float(case_index),
                "candidate_safe_full": _mean(left, "assessor_safe_full"),
                "control_safe_full": _mean(right, "assessor_safe_full"),
                "candidate_work": cwork, "control_work": bwork})
        left_safe = fmean(row["candidate_safe_full"] for row in case_effects[family])
        right_safe = fmean(row["control_safe_full"] for row in case_effects[family])
        cwork = fmean(row["candidate_work"] for row in case_effects[family])
        bwork = fmean(row["control_work"] for row in case_effects[family])
        effects[family] = {
            "candidate_safe_full": left_safe, "control_safe_full": right_safe,
            "candidate_work": cwork, "control_work": bwork,
        }
        effects[family]["safe_full_delta"] = effects[family]["candidate_safe_full"] - effects[family]["control_safe_full"]
        effects[family]["work_ratio"] = cwork / bwork
        effects[family]["work_reduction"] = 1.0 - effects[family]["work_ratio"]
    if len(effects) != 4 or any(len(rows) != 6 for rows in case_effects.values()):
        raise ValueError("formal family pairing is not four families by six cases by ten replicates")
    return effects, case_effects


def _bootstrap(case_effects: dict[str, list[dict[str, float]]]) -> dict[str, Any]:
    families = sorted(case_effects)
    rng, raw, safe, ratios = random.Random(BOOTSTRAP_SEED), bytearray(), [], []
    for _ in range(BOOTSTRAP_RESAMPLES):
        family_safe, family_candidate_work, family_control_work = [], [], []
        for _family_draw in range(4):
            family_index = rng.randrange(4); raw.append(family_index)
            cases = case_effects[families[family_index]]
            chosen = []
            for _case_draw in range(6):
                case_index = rng.randrange(6); raw.append(case_index); chosen.append(cases[case_index])
            family_safe.append(fmean(row["candidate_safe_full"] - row["control_safe_full"] for row in chosen))
            family_candidate_work.append(fmean(row["candidate_work"] for row in chosen))
            family_control_work.append(fmean(row["control_work"] for row in chosen))
        safe.append(fmean(family_safe))
        ratios.append(fmean(family_candidate_work) / fmean(family_control_work))
    safe.sort(); ratios.sort()
    return {
        "family_cluster_count": 4, "cases_per_family": 6, "paired_replicates_per_case": 10,
        "family_and_within_family_case_resampling": True, "paired_replicates_preserved": True,
        "resamples": BOOTSTRAP_RESAMPLES, "seed": BOOTSTRAP_SEED,
        "draw_sha256": hashlib.sha256(raw).hexdigest(),
        "safe_full_delta_lower_95": safe[249], "safe_full_delta_upper_95": safe[9_749],
        "work_ratio_lower_95": ratios[249], "work_ratio_upper_95": ratios[9_749],
        "work_reduction_lower_95": 1.0 - ratios[9_749],
        "work_reduction_upper_95": 1.0 - ratios[249],
    }


def _comparison(rows: Sequence[dict[str, Any]], cases: Sequence[dict[str, Any]], candidate: str,
                control: str, threshold: int, safety_gate: bool) -> dict[str, Any]:
    effects, case_effects = _family_effects(rows, candidate, control, threshold)
    candidate_safe = fmean(row["candidate_safe_full"] for row in effects.values())
    control_safe = fmean(row["control_safe_full"] for row in effects.values())
    candidate_work = fmean(row["candidate_work"] for row in effects.values())
    control_work = fmean(row["control_work"] for row in effects.values())
    delta, ratio = candidate_safe - control_safe, candidate_work / control_work
    bootstrap = _bootstrap(case_effects)
    case_by_index = {int(case["case_index"]): case for case in cases}
    relevant = [row for row in rows if row["callback_threshold"] == threshold
                and row["method"] in (candidate, control)]
    strata: dict[str, dict[str, float]] = {}
    for stratum in sorted({s for case in cases for s in case["strata"]}):
        chosen = [row for row in relevant if stratum in case_by_index[row["case_index"]]["strata"]]
        left, right = [r for r in chosen if r["method"] == candidate], [r for r in chosen if r["method"] == control]
        strata[stratum] = {"candidate_safe_full": _mean(left, "assessor_safe_full"),
                           "control_safe_full": _mean(right, "assessor_safe_full")}
        strata[stratum]["safe_full_delta"] = strata[stratum]["candidate_safe_full"] - strata[stratum]["control_safe_full"]
    critical_gate = all(row["safe_full_delta"] + BOUNDARY_EPS >= -0.02
                        for row in strata.values())
    positive = sum(row["safe_full_delta"] > BOUNDARY_EPS for row in effects.values())
    efficient = sum(row["safe_full_delta"] + BOUNDARY_EPS >= -0.01
                    and row["work_reduction"] > BOUNDARY_EPS for row in effects.values())
    point_a = delta + BOUNDARY_EPS >= 0.05 and ratio <= 1.20 + BOUNDARY_EPS
    point_b = delta + BOUNDARY_EPS >= -0.01 and ratio <= 0.80 + BOUNDARY_EPS
    path_a = point_a and positive >= 3 and bootstrap["safe_full_delta_lower_95"] > 0 and critical_gate and safety_gate
    path_b = (point_b and efficient >= 3 and bootstrap["work_ratio_upper_95"] < 1
              and bootstrap["safe_full_delta_lower_95"] + BOUNDARY_EPS >= -0.02
              and critical_gate and safety_gate)
    tie = (control == D0 and abs(delta) <= 0.05 + BOUNDARY_EPS
           and 0.95 - BOUNDARY_EPS <= ratio <= 1.05 + BOUNDARY_EPS)
    authority = threshold == 4_800 and control == D0
    return {
        "bootstrap": bootstrap, "candidate": candidate, "control": control,
        "callback_threshold": threshold, "promotion_authority": authority,
        "floating_boundary_epsilon": BOUNDARY_EPS,
        "family_effects": effects, "family_equal_candidate_safe_full": candidate_safe,
        "family_equal_control_safe_full": control_safe, "family_equal_safe_full_delta": delta,
        "family_equal_candidate_right_censored_work": candidate_work,
        "family_equal_control_right_censored_work": control_work,
        "family_equal_work_ratio": ratio, "family_equal_work_reduction": 1.0 - ratio,
        "families_positive_recall": positive, "families_efficiency_favorable": efficient,
        "three_of_four_path_a_direction": positive >= 3,
        "three_of_four_path_b_direction": efficient >= 3,
        "critical_strata": strata, "critical_strata_noninferior": critical_gate,
        "point_path_a": point_a, "point_path_b": point_b,
        "path_a_pass": path_a, "path_b_pass": path_b,
        "d0_within_five_percent_tie_selects_d0": tie,
        "candidate_gate_pass": authority and (path_a or path_b) and not tie,
    }


def aggregate_documents(manifest: dict[str, Any], auth: dict[str, Any], shards: Sequence[dict[str, Any]],
                        *, input_sha: str, authorization_sha: str, aggregator_sha: str) -> dict[str, Any]:
    cases, proposals = _validate_input(manifest)
    _validate_authorization(auth, manifest, input_sha, aggregator_sha)
    identities = [(_replicate(row), row.get("case_index")) for row in shards]
    expected = {(rep, case) for rep in range(1, 11) for case in range(1, 25)}
    if len(shards) != 240 or set(identities) != expected or len(set(identities)) != 240:
        raise ValueError("raw Stage A shards are missing or duplicated")
    accounting: defaultdict[str, int] = defaultdict(int)
    for field in ("proposal_summary_mismatches", "callback_snapshot_mismatches", "terminal_mismatches",
                  "iid_bounded_gap_violations", "iid_starvation_count", "iid_violation_prefix_count",
                  "reported_accepted_canonical_invalid", "reported_accepted_gold_inconsistent",
                  "reported_accepted_numeric_target_only", "reported_accepted_ambiguous",
                  "assessor_unsafe", "assessor_ambiguity", "assessor_false_targets",
                  "evaluation_count_mismatches", "callback_cap_violations", "exceptions",
                  "runner_budget_exhausted", "truth_separation_violations"):
        accounting[field] = 0
    revisions, case_rows, callback_rows = set(), [], []
    for shard in sorted(shards, key=lambda row: (_replicate(row), int(row["case_index"]))):
        replicate, case_index = _replicate(shard), int(shard["case_index"])
        case, methods = cases[case_index - 1], _methods(replicate)
        if any((shard.get("schema_version") != RAW_SCHEMA, shard.get("experiment_id") != EXPERIMENT,
                shard.get("stage") != STAGE, shard.get("partition") != PARTITION,
                shard.get("lab_confirmation_512_768") is not False,
                shard.get("input_manifest", {}).get("sha256") != input_sha,
                shard.get("authorization", {}).get("sha256") != authorization_sha,
                not _case_matches(shard.get("case_manifest", {}), case),
                tuple(shard.get("stream_order", ())) != methods,
                not _thread_ok(shard.get("thread_contract"), case_index, replicate))):
            raise ValueError(f"raw Stage A shard contract differs at case {case_index} replicate {replicate}")
        revision = shard.get("revision", {})
        if revision.get("git_dirty") is not False or not revision.get("git_head"):
            raise ValueError("raw Stage A shard did not run from a clean revision")
        revisions.add(revision["git_head"])
        streams = shard.get("streams", [])
        if len(streams) != len(methods) or tuple(T0._method(row) for row in streams) != methods:
            raise ValueError("raw Stage A method order differs")
        for stream in streams:
            method, attempts = T0._method(stream), stream.get("attempts", [])
            proposal = proposals[(case_index, replicate, method)]
            scope = "h0-raw-attribution-only" if method == CURRENT else "fixed-source"
            if (stream.get("source_scope") != scope or stream.get("replicate") != replicate
                    or stream.get("proposal") != proposal):
                raise ValueError("raw Stage A proposal/seed binding differs")
            if len(attempts) != 128 or [T0._index(row) for row in attempts] != list(range(1, 129)):
                raise ValueError("raw Stage A attempt order differs")
            prefixes = T0.case_prefix_rows(attempts, _metric_case(case), method)
            _annotate(prefixes, case, replicate, attempts)
            crossings = _complete_callback_rows(attempts, case, method)
            if tuple(row["callback_threshold"] for row in crossings) != THRESHOLDS:
                raise ValueError("formal Stage A stream did not cross every callback threshold")
            suffix = T0.suffix_work(attempts, int(case["target_count"]), int(case["configuration_count"]))
            censored = CENSOR if suffix is None else min(suffix, CENSOR)
            for row in crossings:
                row.update(replicate=replicate, strata=case["strata"],
                           right_censored_suffix_work=censored)
            accounting["proposal_summary_mismatches"] += T0.row_mismatches(
                stream.get("proposal_summaries", []), prefixes, ("prefix",),
                ("assessor_qualified", "assessor_distinct_targets_found",
                 "assessor_qualified_distinct_target_recall", "assessor_safe_full",
                 "assessor_unsafe", "callback_work", "evaluation_count_mismatches"))
            accounting["callback_snapshot_mismatches"] += T0.row_mismatches(
                stream.get("callback_snapshots", []), crossings, ("callback_threshold",),
                ("assessor_qualified", "assessor_distinct_targets_found",
                 "assessor_qualified_distinct_target_recall", "assessor_safe_full", "assessor_unsafe",
                 "crossing_callback_work", "crossing_proposal_index", "threshold_reached"))
            full, terminal = prefixes[-1], stream.get("terminal", {})
            accounting["terminal_mismatches"] += any((terminal.get("attempt_count") != 128,
                terminal.get("callback_work") != full["callback_work"],
                terminal.get("evaluation_count_mismatches") != full["evaluation_count_mismatches"],
                terminal.get("exceptions") != sum(row.get("exception") is not None for row in attempts),
                terminal.get("runner_budget_exhausted") != sum(bool(row.get("budget_exhausted")) for row in attempts),
                terminal.get("local_cap_violations") != full["callback_cap_violations"],
                terminal.get("suffix_stable_assessor_work") != suffix))
            _audit_iid(proposal, accounting); _safety(attempts, accounting)
            for field in ("assessor_unsafe", "assessor_ambiguity", "assessor_false_targets",
                          "evaluation_count_mismatches", "callback_cap_violations"):
                accounting[field] += int(full[field])
            accounting["exceptions"] += sum(row.get("exception") is not None for row in attempts)
            accounting["runner_budget_exhausted"] += sum(bool(row.get("budget_exhausted")) for row in attempts)
            case_rows.extend(prefixes); callback_rows.extend(crossings)
    if len(revisions) != 1:
        raise ValueError("raw Stage A shards came from different revisions")
    proposal_prefix_diagnostics = []
    for method in METHODS:
        for prefix in PREFIXES:
            selected = [row for row in case_rows if row["method"] == method and row["prefix"] == prefix]
            family_rows = {family: [row for row in selected if row["family_id"] == family]
                           for family in sorted({row["family_id"] for row in selected})}
            proposal_prefix_diagnostics.append({
                "method": method, "prefix": prefix, "run_count": len(selected),
                "family_equal_safe_full_rate": fmean(_mean(rows, "assessor_safe_full") for rows in family_rows.values()),
                "family_equal_target_recall": fmean(_mean(rows, "assessor_qualified_distinct_target_recall") for rows in family_rows.values()),
                "family_equal_right_censored_work": fmean(_mean(rows, "right_censored_suffix_work") for rows in family_rows.values()),
                "assessor_unsafe": sum(row["assessor_unsafe"] for row in selected),
                "promotion_authority": False,
            })
    callback_threshold_aggregates = []
    for method in METHODS:
        for threshold in THRESHOLDS:
            selected = [row for row in callback_rows if row["method"] == method
                        and row["callback_threshold"] == threshold]
            family_rows = {family: [row for row in selected if row["family_id"] == family]
                           for family in sorted({row["family_id"] for row in selected})}
            callback_threshold_aggregates.append({
                "method": method, "callback_threshold": threshold, "run_count": len(selected),
                "family_equal_safe_full_rate": fmean(_mean(rows, "assessor_safe_full") for rows in family_rows.values()),
                "family_equal_target_recall": fmean(_mean(rows, "assessor_qualified_distinct_target_recall") for rows in family_rows.values()),
                "family_equal_right_censored_work": fmean(_mean(rows, "right_censored_suffix_work") for rows in family_rows.values()),
                "assessor_unsafe": sum(row["assessor_unsafe"] for row in selected),
                "promotion_authority": threshold == 4_800,
            })
    safety_gate = all(value == 0 for value in accounting.values())
    comparisons = [_comparison(callback_rows, cases, D3, control, threshold, safety_gate)
                   for control in (D0, CURRENT) for threshold in THRESHOLDS]
    return {
        "schema_version": OUTPUT_SCHEMA, "experiment_id": EXPERIMENT, "stage": STAGE,
        "partition": PARTITION, "input_manifest_sha256": input_sha,
        "authorization_sha256": authorization_sha, "revision": revisions.pop(),
        "lab_confirmation": False, "lab_confirmation_512_768": False,
        "raw_current_scope": "H0 raw-source attribution only; not the adaptive H0 control",
        "accounting": dict(sorted(accounting.items())), "safety_accounting_gate": safety_gate,
        "callback_threshold_aggregates": callback_threshold_aggregates,
        "proposal_prefix_diagnostics": proposal_prefix_diagnostics, "comparisons": comparisons,
        "case_rows": case_rows, "callback_rows": callback_rows,
    }


def aggregate_files(input_path: Path, auth_path: Path, shard_paths: Sequence[Path]) -> dict[str, Any]:
    return aggregate_documents(json.loads(input_path.read_text()), json.loads(auth_path.read_text()),
        [json.loads(path.read_text()) for path in shard_paths], input_sha=T0.sha256(input_path),
        authorization_sha=T0.sha256(auth_path), aggregator_sha=T0.sha256(Path(__file__)))


def self_test() -> dict[str, Any]:
    critical = [f"S{i}" for i in range(1, 7)]
    cases, all_seeds = [], 0
    for index in range(1, 25):
        proposals = []
        for rep in range(1, 11):
            for method in _methods(rep):
                all_seeds += 1
                audit = ({"bounded_gap": True, "starvation_count": 0, "violation_prefixes": []}
                         if method in IID_METHODS else None)
                proposal = {"method": method, "replicate": rep, "replicate_seed": str(all_seeds),
                    "path": f"p/{index}/{rep}/{method}", "artifact_sha256": f"{all_seeds:064x}",
                    "file_sha256": f"{all_seeds + 2_000:064x}", "iid_service_audit": audit}
                if method == D3:
                    proposal["mixed_sources"] = {name: {"path": f"{name}/{index}/{rep}",
                        "artifact_sha256": f"{all_seeds + offset:064x}"}
                        for name, offset in (("iid", 4_000), ("rqmc", 6_000))}
                proposals.append(proposal)
        target_count = 3 if index <= 16 else 2
        cases.append({"formal_case_id": f"EXP-DISC-001-A-{index:03d}", "case_index": index,
            "instance_id": f"i-{index}", "family_id": f"F{(index - 1) // 6 + 1}",
            "strata": [critical[(index - 1) % 6]], "dimension": 2, "residual_dimension": 2,
            "configuration_count": target_count, "target_count": target_count,
            "source_replay_checksum": f"r-{index}",
            "parameters": {"i": index}, "source": {"path": "fixture", "index": index},
            "proposals": proposals})
    manifest = {"schema_version": INPUT_SCHEMA, "experiment_id": EXPERIMENT, "stage": STAGE,
        "partition": PARTITION, "case_count": 24, "replicate_count": 10,
        "randomized_replicate_count": 10,
        "proposal_count": 1_248, "target_count": 64, "methods": list(METHODS),
        "lab_confirmation_512_768": False,
        "method_replicate_counts": {m: (1 if m in (D1, HALTON) else 10) for m in METHODS},
        "prefixes": list(PREFIXES), "callback_thresholds": list(THRESHOLDS),
        "attempt_evaluation_limit": CAP, "critical_strata": critical,
        "preregistration": {"path": "pre.json", "sha256": "p" * 64}, "cases": cases}
    auth = {"schema_version": AUTH_SCHEMA, "outcome_execution_authorized": True,
        "input_manifest": {"sha256": "input"}, "aggregator_source_sha256": "aggregator",
        "runner_source_sha256": T0.sha256(Path(__file__).with_name("run_stagea_outcomes.jl")),
        "preregistration": {"sha256": "p" * 64},
        "dependency_source_sha256": {
            "research/experiments/EXP-DISC-001/aggregate_t0.py": T0.sha256(
                Path(__file__).with_name("aggregate_t0.py")),
            "research/experiments/EXP-DISC-001/run_t0_outcomes.jl": T0.sha256(
                Path(__file__).with_name("run_t0_outcomes.jl")),
        }}
    attempts_by_target = {target_count: [{"start_index": i, "assessor_qualified": i <= target_count,
        "assessor_gold_matched": i <= target_count, "assessor_target_ambiguous": False,
        "assessor_numeric_target_matched": i <= target_count,
        "assessor_matched_target_id": f"t{i}" if i <= target_count else None,
        "assessor_matched_configuration": i if i <= target_count else None,
        "observed_evaluations": 50, "reported_evaluations": 50,
        "evaluation_count_mismatch": False, "exception": None, "budget_exhausted": False,
        "reported_accepted": i <= target_count, "canonical_valid": i <= target_count,
        "gold_matched": i <= target_count, "numeric_target_matched": i <= target_count,
        "target_ambiguous": False} for i in range(1, 129)] for target_count in (2, 3)}
    shards = []
    for rep in range(1, 11):
        for case in cases:
            attempts = attempts_by_target[case["target_count"]]
            streams = []
            for method in _methods(rep):
                proposal = next(p for p in case["proposals"] if p["replicate"] == rep and p["method"] == method)
                prefixes = T0.case_prefix_rows(attempts, _metric_case(case), method)
                crossings = _complete_callback_rows(attempts, case, method)
                streams.append({"method": method, "replicate": rep,
                    "source_scope": "h0-raw-attribution-only" if method == CURRENT else "fixed-source",
                    "proposal": proposal, "attempts": attempts, "proposal_summaries": prefixes,
                    "callback_snapshots": crossings, "terminal": {"attempt_count": 128, "callback_work": 6_400,
                    "evaluation_count_mismatches": 0, "exceptions": 0, "runner_budget_exhausted": 0,
                    "local_cap_violations": 0,
                    "suffix_stable_assessor_work": 50 * case["target_count"]}})
            cpu = (case["case_index"] + rep - 2) % 16
            shards.append({"schema_version": RAW_SCHEMA, "experiment_id": EXPERIMENT, "stage": STAGE,
                "partition": PARTITION, "case_index": case["case_index"], "replicate": rep,
                "lab_confirmation_512_768": False,
                "input_manifest": {"sha256": "input"}, "authorization": {"sha256": "auth"},
                "revision": {"git_head": "fixture", "git_dirty": False}, "case_manifest": case,
                "stream_order": list(_methods(rep)), "streams": streams,
                "thread_contract": {"julia_threads": 1, "blas_threads": 1, "assigned_cpu": cpu,
                    "cpus_allowed_list": str(cpu), "case_process_limit": 16, "solver_worker_count": 1,
                    "environment": {name: "1" for name in ("JULIA_NUM_THREADS", "OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS")}}})
    clean = aggregate_documents(manifest, auth, shards, input_sha="input", authorization_sha="auth", aggregator_sha="aggregator")
    assert clean["safety_accounting_gate"]
    assert clean["comparisons"][0]["d0_within_five_percent_tie_selects_d0"] is True
    assert clean["comparisons"][-1]["d0_within_five_percent_tie_selects_d0"] is False
    rounded_boundary = 0.85 - 0.8
    assert rounded_boundary < 0.05 and rounded_boundary + BOUNDARY_EPS >= 0.05
    original = shards[0]["streams"][0]["proposal_summaries"][0]["callback_work"]
    shards[0]["streams"][0]["proposal_summaries"][0]["callback_work"] = original + 1
    tampered = aggregate_documents(manifest, auth, shards, input_sha="input", authorization_sha="auth", aggregator_sha="aggregator")
    assert tampered["accounting"]["proposal_summary_mismatches"] > 0
    shards[0]["streams"][0]["proposal_summaries"][0]["callback_work"] = original
    try:
        aggregate_documents(manifest, auth, shards[:-1], input_sha="input", authorization_sha="auth", aggregator_sha="aggregator")
        raise AssertionError("missing shard was accepted")
    except ValueError:
        pass
    cases[0]["proposals"][0]["iid_service_audit"].update(bounded_gap=False, starvation_count=1,
                                                           violation_prefixes=[8])
    violated = aggregate_documents(manifest, auth, shards, input_sha="input", authorization_sha="auth", aggregator_sha="aggregator")
    assert violated["accounting"]["iid_bounded_gap_violations"] > 0
    return {"schema_version": "geotarget.discovery-stagea-aggregate-self-test/v1",
        "synthetic_cases": 24, "synthetic_replicates": 10, "normal_passed": True,
        "tamper_detected": True, "missing_detected": True, "iid_violation_detected": True,
        "floating_boundary_checked": True,
        "outcomes_executed": False}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--input-manifest", type=Path); parser.add_argument("--authorization", type=Path)
    parser.add_argument("--output", type=Path); parser.add_argument("shards", nargs="*", type=Path)
    args = parser.parse_args()
    if args.self_test:
        if args.input_manifest or args.authorization or args.output or args.shards:
            parser.error("--self-test is exclusive")
        print(T0.canonical_json(self_test())); return
    if not args.input_manifest or not args.authorization or not args.output or len(args.shards) != 240:
        parser.error("normal aggregation requires named input/auth/output and exactly 240 shards")
    result = aggregate_files(args.input_manifest, args.authorization, args.shards)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(T0.canonical_json(result) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
