#!/usr/bin/env python3
"""Run the frozen generated-only D0 tapes; never imports formal/dev truth."""

from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import platform
from typing import Callable, Mapping

from candidate import Leaf, PublicCase, ScheduleResult, canonical_dnf, run


HERE = Path(__file__).resolve().parent
TAPE_PATH = HERE / "tapes.json"
FROZEN_TAPE_SHA256 = "07e220eb15c74f525aaadde7fa856f17ba4e59be5a871dbd49b61d665c628d4d"


def load_tape() -> dict[str, object]:
    payload = TAPE_PATH.read_bytes()
    actual = hashlib.sha256(payload).hexdigest()
    if actual != FROZEN_TAPE_SHA256:
        raise RuntimeError(f"hidden tape hash mismatch: {actual}")
    document = json.loads(payload)
    if document["schema"] != "proof-obligation-sbfe-hidden-tape-v1":
        raise RuntimeError("unexpected tape schema")
    return document


def _node_remap(node: Mapping[str, object], leaf_map: Mapping[str, str]) -> dict[str, object]:
    if "leaf" in node:
        return {"leaf": leaf_map[str(node["leaf"])]}
    if "const" in node:
        return {"const": bool(node["const"])}
    key = "and" if "and" in node else "or"
    return {key: [_node_remap(child, leaf_map) for child in node[key]]}


def _reverse_node(node: Mapping[str, object]) -> dict[str, object]:
    if "leaf" in node:
        return {"leaf": str(node["leaf"])}
    if "const" in node:
        return {"const": bool(node["const"])}
    key = "and" if "and" in node else "or"
    return {key: [_reverse_node(child) for child in reversed(node[key])]}


def _public_and_oracle(
    raw: Mapping[str, object], *, scale: float = 1.0
) -> tuple[PublicCase, Callable[[str], tuple[bool, float]], dict[str, bool]]:
    budget = load_tape()["budget_contract"]
    public_leaves = {
        leaf: Leaf(float(spec["p"]), scale * float(spec["c"]))
        for leaf, spec in raw["leaves"].items()
    }
    hidden = {
        leaf: (bool(spec["outcome"]), scale * float(spec["actual_cost"]))
        for leaf, spec in raw["leaves"].items()
    }
    calls: list[str] = []

    def reveal(selected_leaf: str) -> tuple[bool, float]:
        # This is the only closure containing realised outcome/cost.  It is
        # invoked by candidate.run only after the leaf has been selected.
        calls.append(selected_leaf)
        return hidden[selected_leaf]

    reveal.calls = calls  # type: ignore[attr-defined]
    case = PublicCase(
        descriptors=raw["descriptors"],
        leaves=public_leaves,
        total_budget=scale * float(budget["total"]),
        baseline_fraction=float(budget["baseline_fraction"]),
        graph_fraction_cap=float(budget["graph_fraction_cap"]),
    )
    return case, reveal, {leaf: outcome for leaf, (outcome, _cost) in hidden.items()}


def _execute(raw: Mapping[str, object], strategy: str, *, scale: float = 1.0) -> tuple[ScheduleResult, dict[str, bool]]:
    case, reveal, truth = _public_and_oracle(raw, scale=scale)
    result = run(case, reveal, strategy=strategy)
    if list(result.selections) != reveal.calls:  # type: ignore[attr-defined]
        raise AssertionError("oracle was called before or outside a recorded selection")
    return result, truth


def _false_authority(
    raw: Mapping[str, object], result: ScheduleResult, truth: Mapping[str, bool]
) -> int:
    false_count = 0
    for descriptor in result.certificates:
        routes = canonical_dnf(raw["descriptors"][descriptor])
        if not any(all(truth[leaf] for leaf in route) for route in routes):
            false_count += 1
        witness = result.proof_witnesses[descriptor]
        if not witness or not all(truth[leaf] for leaf in witness):
            false_count += 1
    return false_count


def _mapped_signature(
    result: ScheduleResult,
    *,
    leaf_inverse: Mapping[str, str] | None = None,
    descriptor_inverse: Mapping[str, str] | None = None,
    cost_scale: float = 1.0,
) -> dict[str, object]:
    li = leaf_inverse or {}
    di = descriptor_inverse or {}
    leaf = lambda value: li.get(value, value)
    desc = lambda value: di.get(value, value)
    return {
        "certificates": sorted(desc(value) for value in result.certificates),
        "failed": sorted(desc(value) for value in result.failed_descriptors),
        "unresolved": sorted(desc(value) for value in result.unresolved_descriptors),
        "witnesses": {
            desc(key): sorted(leaf(value) for value in values)
            for key, values in sorted(result.proof_witnesses.items())
        },
        "selections": [leaf(value) for value in result.selections],
        "revealed": {leaf(key): value for key, value in sorted(result.revealed.items())},
        "not_run": sorted(leaf(value) for value in result.not_run),
        "late": [leaf(value) for value in result.deadline_late],
        "first_served": result.descriptors_first_served,
        "eligible": result.eligible_descriptors,
        "shared_hits": result.shared_resolution_hits,
        "graph_spent": round(result.graph_spent / cost_scale, 10),
        "graph_cap": round(result.graph_cap / cost_scale, 10),
        "unused_returned": round(result.unused_graph_budget_returned / cost_scale, 10),
        "score_operations": result.score_operations,
        "tie_events": result.tie_events,
        "false_authority": result.false_authority,
    }


def _renamed(raw: Mapping[str, object]) -> tuple[dict[str, object], dict[str, str], dict[str, str]]:
    changed = deepcopy(raw)
    old_leaves = sorted(raw["leaves"])
    old_descriptors = sorted(raw["descriptors"])
    leaf_map = {
        old: f"node_{len(old_leaves) - ordinal:03d}_renamed"
        for ordinal, old in enumerate(old_leaves)
    }
    descriptor_map = {
        old: f"proof_{len(old_descriptors) - ordinal:03d}_renamed"
        for ordinal, old in enumerate(old_descriptors)
    }
    changed["leaves"] = {
        leaf_map[key]: deepcopy(value) for key, value in reversed(list(raw["leaves"].items()))
    }
    changed["descriptors"] = {
        descriptor_map[key]: _node_remap(value, leaf_map)
        for key, value in reversed(list(raw["descriptors"].items()))
    }
    return changed, {value: key for key, value in leaf_map.items()}, {
        value: key for key, value in descriptor_map.items()
    }


def _insertion_permuted(raw: Mapping[str, object]) -> dict[str, object]:
    changed = deepcopy(raw)
    changed["leaves"] = dict(reversed(list(raw["leaves"].items())))
    changed["descriptors"] = {
        key: _reverse_node(value) for key, value in reversed(list(raw["descriptors"].items()))
    }
    return changed


def _factored(raw: Mapping[str, object]) -> dict[str, object]:
    changed = deepcopy(raw)
    descriptor = raw.get("factor_descriptor")
    if descriptor is not None:
        changed["descriptors"][descriptor] = deepcopy(raw["factored_node"])
    return changed


def _with_inert_terminal(raw: Mapping[str, object]) -> dict[str, object]:
    changed = deepcopy(raw)
    changed["descriptors"] = {
        key: {"or": [deepcopy(value), {"const": False}]}
        for key, value in raw["descriptors"].items()
    }
    return changed


def _case_summary(raw: Mapping[str, object]) -> tuple[dict[str, object], ScheduleResult, ScheduleResult]:
    control, control_truth = _execute(raw, "fifo")
    candidate, candidate_truth = _execute(raw, "sbfe")
    if control_truth != candidate_truth:
        raise AssertionError("control and candidate did not receive the same hidden tape")
    false_control = _false_authority(raw, control, control_truth)
    false_candidate = _false_authority(raw, candidate, candidate_truth)
    baseline_ok = (
        control.baseline_byte_identical_contract
        and candidate.baseline_byte_identical_contract
        and control.baseline_bytes == candidate.baseline_bytes
        and control.baseline_spent == control.baseline_reserved
        and candidate.baseline_spent == candidate.baseline_reserved
    )
    summary = {
        "name": raw["name"],
        "class": raw["class"],
        "control_certificates": len(control.certificates),
        "candidate_certificates": len(candidate.certificates),
        "delta_certificates": len(candidate.certificates) - len(control.certificates),
        "control_first_served": control.descriptors_first_served,
        "candidate_first_served": candidate.descriptors_first_served,
        "control_not_run": len(control.not_run),
        "candidate_not_run": len(candidate.not_run),
        "control_graph_spent": control.graph_spent,
        "candidate_graph_spent": candidate.graph_spent,
        "candidate_unused_graph_budget_returned": candidate.unused_graph_budget_returned,
        "candidate_shared_resolution_hits": candidate.shared_resolution_hits,
        "candidate_deadline_late": len(candidate.deadline_late),
        "false_authority": false_control + false_candidate,
        "baseline_contract": baseline_ok,
        "control_selections": list(control.selections),
        "candidate_selections": list(candidate.selections),
    }
    return summary, control, candidate


def _metamorphic(cases: list[Mapping[str, object]]) -> dict[str, object]:
    checks: list[dict[str, object]] = []
    for raw in cases:
        base, _truth = _execute(raw, "sbfe")
        base_signature = _mapped_signature(base)

        renamed, leaf_inverse, descriptor_inverse = _renamed(raw)
        renamed_result, _truth = _execute(renamed, "sbfe")
        checks.append(
            {
                "case": raw["name"],
                "transform": "ids",
                "pass": _mapped_signature(
                    renamed_result,
                    leaf_inverse=leaf_inverse,
                    descriptor_inverse=descriptor_inverse,
                )
                == base_signature,
            }
        )

        insertion_result, _truth = _execute(_insertion_permuted(raw), "sbfe")
        checks.append(
            {
                "case": raw["name"],
                "transform": "insertion",
                "pass": _mapped_signature(insertion_result) == base_signature,
            }
        )

        scaled_result, _truth = _execute(raw, "sbfe", scale=7.0)
        checks.append(
            {
                "case": raw["name"],
                "transform": "common_cost_budget_scale",
                "pass": _mapped_signature(scaled_result, cost_scale=7.0) == base_signature,
            }
        )

        factored_result, _truth = _execute(_factored(raw), "sbfe")
        checks.append(
            {
                "case": raw["name"],
                "transform": "equivalent_dag_factoring",
                "pass": _mapped_signature(factored_result) == base_signature,
            }
        )

        inert_result, _truth = _execute(_with_inert_terminal(raw), "sbfe")
        checks.append(
            {
                "case": raw["name"],
                "transform": "inert_terminal_route",
                "pass": _mapped_signature(inert_result) == base_signature,
            }
        )
    return {
        "checks": len(checks),
        "passed": sum(bool(check["pass"]) for check in checks),
        "failed": [check for check in checks if not check["pass"]],
    }


def build_report() -> dict[str, object]:
    tape = load_tape()
    cases = tape["cases"]
    rows: list[dict[str, object]] = []
    controls: list[ScheduleResult] = []
    candidates: list[ScheduleResult] = []
    for raw in cases:
        row, control, candidate = _case_summary(raw)
        rows.append(row)
        controls.append(control)
        candidates.append(candidate)

    p_improvements = sum(
        row["class"] == "P" and row["delta_certificates"] > 0 for row in rows
    )
    loss_count = sum(row["delta_certificates"] < 0 for row in rows)
    false_authority = sum(row["false_authority"] for row in rows)
    baseline_rate = sum(bool(row["baseline_contract"]) for row in rows) / len(rows)
    control_first = sum(result.descriptors_first_served for result in controls)
    candidate_first = sum(result.descriptors_first_served for result in candidates)
    first_service_gain = (candidate_first - control_first) / max(1, control_first)
    control_not_run = sum(len(result.not_run) for result in controls)
    candidate_not_run = sum(len(result.not_run) for result in candidates)
    not_run_reduction = (control_not_run - candidate_not_run) / max(1, control_not_run)
    scheduler_seconds = sum(result.scheduler_seconds for result in candidates)
    simulated_work_seconds = float(tape["cost_unit_seconds"]) * sum(
        result.graph_spent for result in candidates
    )
    overhead = scheduler_seconds / max(1.0e-15, scheduler_seconds + simulated_work_seconds)
    metamorphic = _metamorphic(cases)

    hard_gates = {
        "two_or_more_positive_families_gain_full_certificates": p_improvements >= 2,
        "all_p_n_m_loss_zero": loss_count == 0,
        "false_authority_zero": false_authority == 0,
        "baseline_contract_100_percent": baseline_rate == 1.0,
        "first_service_gain_at_least_20_percent": first_service_gain >= 0.20,
        "not_run_reduction_at_least_20_percent": not_run_reduction >= 0.20,
        "overhead_at_most_20_percent": overhead <= 0.20,
        "all_metamorphic_checks_pass": metamorphic["passed"] == metamorphic["checks"],
        "no_scheduler_ties_on_frozen_tapes": sum(r.tie_events for r in candidates) == 0,
    }
    core = all(
        hard_gates[key]
        for key in (
            "two_or_more_positive_families_gain_full_certificates",
            "all_p_n_m_loss_zero",
            "false_authority_zero",
            "baseline_contract_100_percent",
            "overhead_at_most_20_percent",
            "all_metamorphic_checks_pass",
            "no_scheduler_ties_on_frozen_tapes",
        )
    )
    if core and hard_gates["first_service_gain_at_least_20_percent"]:
        decision = "GO"
    elif core and hard_gates["not_run_reduction_at_least_20_percent"]:
        decision = "HOLD_NOT_RUN_ONLY"
    else:
        decision = "STOP"

    return {
        "schema": "proof-obligation-sbfe-d0-result-v1",
        "decision": decision,
        "scope": "generated-only; no formal/dev/scorer/truth input",
        "tape_sha256": FROZEN_TAPE_SHA256,
        "environment": {
            "python": platform.python_version(),
            "cpu_policy": "CPU15 only",
            "native_threads": 1,
        },
        "aggregate": {
            "control_certificates": sum(len(result.certificates) for result in controls),
            "candidate_certificates": sum(len(result.certificates) for result in candidates),
            "positive_families_improved": p_improvements,
            "loss_count": loss_count,
            "false_authority": false_authority,
            "baseline_contract_rate": baseline_rate,
            "control_first_served": control_first,
            "candidate_first_served": candidate_first,
            "first_service_gain": first_service_gain,
            "control_not_run": control_not_run,
            "candidate_not_run": candidate_not_run,
            "not_run_reduction": not_run_reduction,
            "scheduler_seconds": scheduler_seconds,
            "simulated_work_seconds": simulated_work_seconds,
            "overhead_ratio": overhead,
            "candidate_score_operations": sum(r.score_operations for r in candidates),
            "candidate_tie_events": sum(r.tie_events for r in candidates),
        },
        "gates": hard_gates,
        "metamorphic": metamorphic,
        "cases": rows,
    }


if __name__ == "__main__":
    print(json.dumps(build_report(), indent=2, sort_keys=True))
