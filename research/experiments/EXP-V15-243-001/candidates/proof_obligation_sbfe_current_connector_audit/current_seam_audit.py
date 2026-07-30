#!/usr/bin/env python3
"""Hash-bound source-only audit for the proof-obligation SBFE connector.

The script reads candidate/runtime source bytes only.  It never imports a
solver, opens a problem source/result, or invokes a scorer/formal runner.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Mapping


HERE = Path(__file__).resolve().parent
RUNTIME_ROOT = Path(
    os.environ.get(
        "GEOTARGET_EXPERIMENT_RUNTIME",
        "/home/kabatan/work/solver-experiment-runtime/solver",
    )
).resolve()
CURRENT_COMPOSITION_ROOT = Path(
    os.environ.get(
        "GEOTARGET_CURRENT_COMPOSITION_ROOT",
        "/home/kabatan/work/solver-wt/cross-endpoint-proof-racing",
    )
).resolve()
RUNTIME_EXP = RUNTIME_ROOT / "research/experiments/EXP-V15-243-001"
COMPOSITION_EXP = (
    CURRENT_COMPOSITION_ROOT / "research/experiments/EXP-V15-243-001"
)

PATHS = {
    "exact_outer": RUNTIME_EXP / "candidates/exact_outer_decorator/worker.py",
    "exact_authority": RUNTIME_EXP
    / "candidates/exact_outer_decorator/authority_boundary.py",
    "hp_policy": RUNTIME_EXP / "candidates/hp_lock_scheduler/policy.py",
    "hp_adapter": RUNTIME_EXP / "candidates/hp_lock_scheduler/adapter.py",
    "hp_bridge": RUNTIME_EXP / "candidates/hp_lock_scheduler/bridge.py",
    "cross_scheduler": RUNTIME_EXP
    / "candidates/cross_endpoint_hp_rungs/scheduler.py",
    "cross_h1_binding": RUNTIME_EXP
    / "candidates/cross_endpoint_hp_rungs/h1_binding.py",
    "adaptive_exact_prototype": RUNTIME_EXP
    / "candidates/adaptive_exact_coordinate_first_wave2/candidate.py",
    "adaptive_exact_breadth": RUNTIME_EXP
    / "candidates/adaptive_exact_coordinate_first_wave2/breadth_endpoint_worker.py",
    "zero_worker": RUNTIME_EXP / "champion_v2/worker.py",
    "poc_wrapper": RUNTIME_EXP
    / "candidates/point_on_circle_periodic_semantics/champion_v2_wrapper.py",
    "current_scheduler_shim": COMPOSITION_EXP
    / "candidates/archive_progressive_hybrid_exact_outer_v1/scheduler_shim.py",
    "current_exact_worker": COMPOSITION_EXP
    / "candidates/archive_progressive_hybrid_exact_outer_v1/worker.py",
}

EXPECTED_SHA256 = {
    "exact_outer": "05650c1016f3974c0f74845037c76604eb38f2f4a337cc700721f0e148d9d3f7",
    "exact_authority": "a36520a416d0b8c900bca6b79192c7014812c9b1270be09248347f0f19e167e9",
    "hp_policy": "c32ed095643c7154742bc94743fbe69e83e77cddd6d5b9f8a00e4b38b5c16121",
    "hp_adapter": "af7fcc70dd7be727d395c048907424e3d46ba167fe7a7981df3f71c7c49884bb",
    "hp_bridge": "15a292ccc98f1c86b989aa1104584cc60fa590fe011b1a33de45a7b66704b8e8",
    "cross_scheduler": "2fbaa23b05fe67ea0845780d3a81ceaea38499ae2962d01f41f92f13d37bca8c",
    "cross_h1_binding": "da5c3761d4603d626cffe07c56b730483b9ca2587ac1a59cdfc858829efab718",
    "adaptive_exact_prototype": "ea23cc32d4d5dc6ca48b844f3bd75372e7d0e63662331c521607210d54de76e6",
    "adaptive_exact_breadth": "371910a1fba566d978bd171dff4f9ada3eed4034f5afd2cc7034736f178668a0",
    "zero_worker": "241128047481cc8a428ff99dcb9d840cbc2ade3e87ddb564bb1a920fe10346ca",
    "poc_wrapper": "0fc41efe21ab029e74ab8c3112d42271057d4dfeb808b52fea11500c2ae7003d",
    "current_scheduler_shim": "b3b9df6062dc0aa603fc5da02ae2eefa0947721eafe9069bf545af75747350e0",
    "current_exact_worker": "6948cdb468601b53c6a2034ee3b4fd92971898f79899bb0a025be5abafe5c9a8",
}

D0 = {
    "branch": "codex/exp-proof-obligation-sbfe-d0",
    "commit": "ee29f3e69835516e5c1271ba1627099d23840254",
    "mechanism_sha256": "6a4c2146c66d3d7f06bb443cc3ce09e0122a9ce27222cc3b39d1a1542b080e1e",
    "tape_sha256": "07e220eb15c74f525aaadde7fa856f17ba4e59be5a871dbd49b61d665c628d4d",
}

CURRENT_LINEAGE = {
    "exact_outer_branch_commit": "4cd7ff9f0fc1a07ef9a2802bf2144a7f7657eefd",
    "cross_endpoint_reaudit_commit": "24a2c9a71c8de77544b519e95f33eb40b07dc438",
}

GRAPH_ABI_TOKENS = (
    '"proof_obligations"',
    '"route_alternatives"',
    '"shared_prerequisite_ids"',
    '"declared_route_cost"',
    '"descriptor_first_service_age"',
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _has_all(text: str, tokens: tuple[str, ...]) -> bool:
    return all(token in text for token in tokens)


def _ordered(text: str, tokens: tuple[str, ...]) -> bool:
    cursor = -1
    for token in tokens:
        cursor = text.find(token, cursor + 1)
        if cursor < 0:
            return False
    return True


def _section(text: str, start: str, end: str | None = None) -> str:
    if start not in text:
        return ""
    result = text.split(start, 1)[1]
    if end is not None and end in result:
        result = result.split(end, 1)[0]
    return result


def audit(paths: Mapping[str, Path] = PATHS) -> dict[str, object]:
    observed = {
        name: _sha256(path) if path.is_file() else "MISSING"
        for name, path in paths.items()
    }
    hash_binding_valid = observed == EXPECTED_SHA256
    source = {
        name: _text(path) if path.is_file() else "" for name, path in paths.items()
    }

    exact_run = _section(
        source["exact_outer"], "def _run_exact_outer", "if getattr(BASE"
    )
    exact_ordinary_then_fallback = _ordered(
        exact_run,
        (
            '_ORDINARY_HP(**kwargs)',
            'ready = _ordinary_ready(ordinary)',
            'remaining = timeout_seconds',
            '_fallback_command(',
            'with RESOURCE.adapter.per_core_lease(',
            '_consume_fallback(',
        ),
    )
    confirm_ready_does_not_return_ordinary = _has_all(
        exact_run,
        (
            'if MODE == FAILURE_ONLY and ready:',
            'return ordinary',
            'if ready:',
            'ordinary_identity = boundary.descriptor_identity(',
            '"EXACT_CONFIRMATION_DESCRIPTOR_MISMATCH"',
        ),
    )
    exact_execution_caps_present = _has_all(
        source["exact_outer"],
        (
            'MINIMUM_FALLBACK_REMAINING_SECONDS = 7.0',
            'MAXIMUM_FALLBACK_SECONDS = 12.0',
            'fallback_seconds = min(',
            'rss_bytes=768 * 1024**2',
        ),
    )
    exact_graph_abi_present = all(
        token in source["exact_outer"] for token in GRAPH_ABI_TOKENS
    )
    exact_outcome_only_after_dispatch = _ordered(
        exact_run,
        (
            'ordinary = _ORDINARY_HP(**kwargs)',
            'fallback = None',
            'loaded = json.loads(artifact.read_text',
            'descriptor = _consume_fallback(',
        ),
    )
    exact_current_backend_is_legacy_single_route = _has_all(
        source["exact_outer"],
        (
            'EXACT_ROOT = HERE.parent / "exact_coordinate_replay"',
            'EXACT_WORKER = EXACT_ROOT / "fallback_worker.py"',
        ),
    )

    hp_resource_lease_only = _has_all(
        source["hp_policy"],
        (
            'def per_core_lease(',
            'fcntl.LOCK_EX | fcntl.LOCK_NB',
            'DEFAULT_POLICY = ResourcePolicy(',
        ),
    ) and _has_all(
        source["hp_bridge"],
        (
            'with per_core_lease(cpu, wait_seconds=wait_seconds):',
            'bridge._exclusive_hp_job = _bounded_per_core_job',
            'bridge.main()',
        ),
    )
    hp_terminal_is_posthoc = _ordered(
        _section(source["hp_adapter"], 'def run_hp_candidate', 'def install'),
        (
            'executed = run_guarded_until(',
            'bridge_result = None',
            'authority = None',
            'terminal_evidence = _terminal_evidence(',
            'return {',
        ),
    )
    hp_graph_abi_present = all(
        token in source["hp_adapter"] or token in source["hp_policy"]
        for token in GRAPH_ABI_TOKENS
    )

    request_section = _section(
        source["cross_scheduler"], 'class RungRequest:', 'class RungOutcomeStatus'
    )
    cross_run = _section(
        source["cross_scheduler"], 'def run_fifo_rungs(', '__all__ = ['
    )
    cross_is_endpoint_fifo = _has_all(
        cross_run,
        (
            'queue = deque(',
            'key=lambda row: (row.discovery_ordinal, row.endpoint_sha256)',
            'state = queue.popleft()',
            'queue.append(',
            'requeued_at_fifo_tail',
        ),
    )
    cross_single_runner_per_dispatch = _has_all(
        cross_run,
        (
            'outcome = runner(source_payload, request)',
            'outcome.status is RungOutcomeStatus.YIELDED',
            'outcome.status is RungOutcomeStatus.EXACT_AUTHORITY',
        ),
    ) and 'route' not in request_section.lower()
    cross_outcome_is_posthoc = _ordered(
        cross_run,
        (
            'outcome = runner(source_payload, request)',
            '_validate_outcome(request, outcome)',
            'charged_seconds = max(',
            'if requeued:',
        ),
    )
    cross_declares_restart_caps = _has_all(
        source["cross_scheduler"],
        (
            'cumulative_dense_build_cap',
            'maximum_dispatches_per_endpoint',
            'restart_accounting": "FULL_OBSERVED_COST_EACH_DISPATCH"',
        ),
    )
    cross_has_proof_route_costs = all(
        token in source["cross_scheduler"] for token in GRAPH_ABI_TOKENS
    )
    cross_has_shared_prerequisites = (
        '"shared_prerequisite_ids"' in source["cross_scheduler"]
    )
    h1_single_backend_chain = _has_all(
        source["cross_h1_binding"],
        (
            'class H1No1280RungRunner:',
            'run_adaptive_hp_portfolio(',
            'status=RungOutcomeStatus.EXACT_AUTHORITY',
            'status=RungOutcomeStatus.TERMINAL_FAILURE',
        ),
    )

    prototype_has_two_routes = _has_all(
        source["adaptive_exact_prototype"],
        (
            'enable_coordinate_route: bool = True',
            'enable_source_link_route: bool = True',
            'return _coordinate_authority(',
            'return _univariate_source_link_authority(',
        ),
    )
    breadth_declares_one_current_route = _has_all(
        source["adaptive_exact_breadth"],
        (
            'intentionally exposes only the existing exact-coordinate v15',
            'future source-link',
            'may be added as a second proof route',
            'CHILD_AUTHORITY_MISSING_DEFINEDNESS_MARKERS',
        ),
    )
    prototype_is_current_backend = bool(
        'adaptive_exact_coordinate_first_wave2' in source["exact_outer"]
        or 'adaptive_exact_coordinate_first_wave2' in source["current_scheduler_shim"]
    )

    current_search_insurance_is_not_authority_baseline = _has_all(
        source["current_scheduler_shim"],
        (
            'original_order_baseline_handoff_fraction"] != 0.25',
            'counter_cauchy_handoff_fraction"] != 0.25',
            'ordinary_original_order_baseline_handoff_fraction": 0.25',
        ),
    )
    baseline_authority_queue_75_present = _has_all(
        source["current_scheduler_shim"],
        (
            'baseline_authority_queue_fraction": 0.75',
            'baseline_authority_queue_byte_identical": True',
            'baseline_authority_first_service_complete": True',
            'proof_graph_lane_fraction_cap": 0.25',
        ),
    )
    cross_scheduler_bound_into_current_worker = bool(
        'cross_endpoint_hp_rungs' in source["current_scheduler_shim"]
        or 'cross_endpoint_hp_rungs' in source["current_exact_worker"]
    )

    canonical_authority_workers_present = _has_all(
        source["exact_outer"],
        (
            'BASE._run_hp_candidate = _run_exact_outer',
            '"ordinary_descriptor_is_final_authority": False',
        ),
    ) and 'primitive minimal polynomial' in source["exact_authority"]
    zero_dimensional_identity_preserved = _has_all(
        source["zero_worker"],
        (
            'source-exact zero-dimensional bypass',
            '"zero_dimensional_search_bypass": True',
            'ZERO.run_zero_dimensional_authority(',
        ),
    ) and _has_all(
        source["poc_wrapper"],
        (
            'preserving its zero-dimensional authority verbatim',
            'ZERO = ORIGINAL_V2.ZERO',
        ),
    ) and _has_all(
        source["current_exact_worker"],
        (
            'if ZERO is not SCHEDULER.CONTROL.CHAMPION.ZERO:',
            '"zero_dimensional_authority_logic_changed": False',
        ),
    )

    graph_abi_complete = bool(
        exact_graph_abi_present
        and hp_graph_abi_present
        and cross_has_proof_route_costs
        and cross_has_shared_prerequisites
    )
    current_heterogeneous_or_routes = 0
    anonymous_structural_strata = 0
    route_gate = current_heterogeneous_or_routes >= 2
    strata_gate = anonymous_structural_strata >= 2
    budget_gate = baseline_authority_queue_75_present
    authority_gate = canonical_authority_workers_present and zero_dimensional_identity_preserved
    connector_allowed = bool(
        hash_binding_valid
        and graph_abi_complete
        and route_gate
        and strata_gate
        and budget_gate
        and authority_gate
    )

    return {
        "schema": "geotarget.proof-obligation-sbfe-current-connector-audit/v1",
        "decision": "READY_THIN_CONNECTOR" if connector_allowed else "STOP_BEFORE_CONNECTOR",
        "d0": D0,
        "current_lineage": CURRENT_LINEAGE,
        "hash_binding_valid": hash_binding_valid,
        "audited_sha256": observed,
        "exact_outer": {
            "ordinary_runs_before_fallback_selection": exact_ordinary_then_fallback,
            "confirm_all_ready_requires_exact_fallback": confirm_ready_does_not_return_ordinary,
            "execution_caps_present": exact_execution_caps_present,
            "predispatch_proof_graph_abi_present": exact_graph_abi_present,
            "terminal_outcome_available_only_after_dispatch": exact_outcome_only_after_dispatch,
            "current_backend_is_legacy_single_exact_route": exact_current_backend_is_legacy_single_route,
            "heterogeneous_or_exposed_before_ordinary_work": False,
        },
        "hp_lock": {
            "resource_lease_only": hp_resource_lease_only,
            "terminal_evidence_is_posthoc": hp_terminal_is_posthoc,
            "predispatch_proof_graph_abi_present": hp_graph_abi_present,
            "shared_prerequisite_identity_exported": False,
            "declared_cap_is_resource_or_child_wall_not_proof_route_cost": True,
        },
        "cross_endpoint": {
            "endpoint_fifo": cross_is_endpoint_fifo,
            "one_runner_one_backend_chain_per_dispatch": (
                cross_single_runner_per_dispatch and h1_single_backend_chain
            ),
            "terminal_outcome_is_posthoc": cross_outcome_is_posthoc,
            "restart_and_dispatch_caps_present": cross_declares_restart_caps,
            "proof_route_costs_exported": cross_has_proof_route_costs,
            "shared_prerequisites_exported": cross_has_shared_prerequisites,
            "descriptor_obligation_in_rung_request": (
                'descriptor' in request_section.lower()
            ),
            "bound_into_current_exact_worker": cross_scheduler_bound_into_current_worker,
        },
        "alternate_route_audit": {
            "generated_prototype_has_coordinate_and_source_link_routes": prototype_has_two_routes,
            "breadth_worker_declares_only_one_current_route": breadth_declares_one_current_route,
            "prototype_is_current_exact_outer_backend": prototype_is_current_backend,
            "current_callable_heterogeneous_or_route_count": current_heterogeneous_or_routes,
            "reason": (
                "the only two-route implementation is a non-current generated prototype; "
                "the current breadth child advertises one exact-coordinate route and the "
                "current exact_outer is a fixed ordinary-then-fallback compound path"
            ),
        },
        "budget_and_first_service": {
            "current_search_has_25_percent_original_order_and_25_percent_cauchy_insurance": (
                current_search_insurance_is_not_authority_baseline
            ),
            "that_search_insurance_is_a_75_percent_byte_identical_authority_queue": False,
            "baseline_authority_queue_fraction_required": 0.75,
            "proof_graph_lane_fraction_cap_required": 0.25,
            "baseline_byte_identity_and_first_service_hook_present": (
                baseline_authority_queue_75_present
            ),
            "passed": budget_gate,
        },
        "activation": {
            "required_anonymous_structural_strata": 2,
            "observed_anonymous_structural_strata": anonymous_structural_strata,
            "passed": strata_gate,
            "zero_dimensional_route_counted_as_scheduler_stratum": False,
            "problem_sources_or_results_opened": False,
        },
        "authority": {
            "canonical_exact_outer_worker_present": canonical_authority_workers_present,
            "zero_dimensional_object_and_route_identity_preserved": zero_dimensional_identity_preserved,
            "scheduler_would_emit_authority_directly": False,
            "passed": authority_gate,
        },
        "connector_created": False,
        "generated_or_dry_connector_integration_run": False,
        "rung_cache_species_order_changed": False,
        "generic_proof_platform_created": False,
        "formal_execute_dev_scorer_truth_or_case_results_used": False,
        "cpus_zero_through_thirteen_used": False,
        "reopen_gate": [
            (
                "current callable worker exports, before any proof work, descriptor-bound "
                "monotone obligations with two genuinely available heterogeneous routes, "
                "stable shared-prerequisite IDs, declared route caps/costs, and typed reveal callbacks"
            ),
            (
                "the hash-bound current composition completes a byte-identical authority "
                "baseline with first service under at least 75% of budget before a side graph "
                "lane can consume at most 25%, returning unused side budget"
            ),
            (
                "the callable seam activates without source/result outcomes in at least two "
                "anonymous positive-dimensional structural strata; zero-dimensional authority "
                "is identity-bypassed and does not count"
            ),
            (
                "only existing canonical workers can emit descriptors, with source/guard/branch/" 
                "raw-target replay and exact_outer confirmation unchanged"
            ),
        ],
    }


def main() -> None:
    print(json.dumps(audit(), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
