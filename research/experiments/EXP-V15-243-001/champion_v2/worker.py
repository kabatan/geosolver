#!/usr/bin/env python3
"""Champion v2: champion_v1 plus a source-exact zero-dimensional bypass.

Positive-dimensional sources are delegated to champion_v1 without changing
their search, endpoint reservoir, HP schedule, or exactification path.  A
source with no declared variables has exactly one numerical configuration,
the empty tuple.  Searching that tuple wastes the search budget and the old HP
bridge rejects it as nonempty-required.

The zero-dimensional route therefore evaluates the unchanged source AST
exactly, proves every source equation and guard, derives the target minimal
polynomial and rational isolator from that exact value, and uses the existing
512/768/1024-bit replay only as an implementation-parity audit.  Numeric PSLQ
or a numeric target descriptor is never an authority for this route.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import sys
import time
from typing import Mapping


PROCESS_STARTED = time.monotonic()
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
CHAMPION_V1_WORKER = HERE.parent / "champion_v1/worker.py"
ZERO_ROOT = HERE.parent / "candidates/zero_dimensional_authority"
ZERO_CANDIDATE = ZERO_ROOT / "candidate.py"
ZERO_MANIFEST_PATH = ZERO_ROOT / "IMPLEMENTATION_DIGESTS.json"
ZERO_AUTHORITY_KIND = "SOURCE_EXACT_SYMBOLIC_MINPOLY_ISOLATOR"
ZERO_SCHEMA = "geotarget.exp-v15-243-champion-v2-plan/v1"

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _load_module(name: str, path: Path):
    specification = importlib.util.spec_from_file_location(name, path)
    if specification is None or specification.loader is None:
        raise ImportError(path)
    module = importlib.util.module_from_spec(specification)
    sys.modules[name] = module
    specification.loader.exec_module(module)
    return module


V1 = _load_module(
    "geotarget_exp_v15_243_champion_v2_v1",
    CHAMPION_V1_WORKER,
)
ZERO = _load_module(
    "geotarget_exp_v15_243_champion_v2_zero_authority",
    ZERO_CANDIDATE,
)
BASE = V1.V0.BASE
_V1_PLAN = BASE._plan


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _zero_closure() -> dict[str, object]:
    """Verify and return the independently approved candidate closure."""

    document = json.loads(ZERO_MANIFEST_PATH.read_text(encoding="utf-8"))
    files = document.get("files") if isinstance(document, Mapping) else None
    if not isinstance(files, Mapping):
        raise RuntimeError("zero-dimensional digest manifest is malformed")
    mismatches: dict[str, dict[str, str]] = {}
    for relative, expected in files.items():
        if not isinstance(relative, str) or not isinstance(expected, str):
            raise RuntimeError("zero-dimensional digest row is malformed")
        path = ZERO_ROOT / relative
        actual = _sha256(path.read_bytes()) if path.is_file() else "MISSING"
        if actual != expected:
            mismatches[relative] = {"expected": expected, "actual": actual}
    if mismatches:
        raise RuntimeError(
            "zero-dimensional independently approved closure changed: "
            + json.dumps(mismatches, sort_keys=True)
        )
    if (
        document.get("exact_authority_kind") != ZERO_AUTHORITY_KIND
        or document.get("numeric_pslq_descriptor_used") is not False
        or document.get("case_family_truth_target_count_routing") is not False
    ):
        raise RuntimeError("zero-dimensional authority contract changed")
    adapter = Path(ZERO.AUTHORITY_ADAPTER)
    payload = {
        "manifest": document,
        "manifest_sha256": _sha256(ZERO_MANIFEST_PATH.read_bytes()),
        "candidate_path": str(ZERO_CANDIDATE),
        "candidate_sha256": _sha256(ZERO_CANDIDATE.read_bytes()),
        "numeric_replay_adapter_path": str(adapter),
        "numeric_replay_adapter_sha256": _sha256(adapter.read_bytes()),
    }
    payload["closure_sha256"] = _sha256(
        json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    )
    return payload


def _source_dimension(source: Path) -> int:
    document = json.loads(source.read_text(encoding="utf-8"))
    variables = document.get("variables") if isinstance(document, Mapping) else None
    names = variables.get("names") if isinstance(variables, Mapping) else None
    if not isinstance(names, list) or not all(
        isinstance(name, str) for name in names
    ):
        raise ValueError("untouched solve JSON with variables.names is required")
    return len(names)


def _plan(**kwargs) -> dict[str, object]:
    plan = _V1_PLAN(**kwargs)
    dimension = _source_dimension(Path(kwargs["source"]))
    plan.update(
        {
            "schema_version": ZERO_SCHEMA,
            "champion_v2_worker_sha256": _sha256(Path(__file__).read_bytes()),
            "execution_route": (
                "source_exact_zero_dimensional"
                if dimension == 0
                else "unchanged_champion_v1_positive_dimensional"
            ),
            "zero_dimensional_search_bypass": True,
            "zero_dimensional_authority": _zero_closure(),
            "zero_dimensional_source_ast_exact_target_required": True,
            "zero_dimensional_exact_source_conditions_required": True,
            "zero_dimensional_numeric_pslq_authority": False,
            "positive_dimensional_path_unchanged": True,
            "case_family_truth_target_count_routing": False,
        }
    )
    return plan


# Champion_v1 calls this same BASE object.  This changes only its dry-plan
# custody record; all positive-dimensional runtime functions stay untouched.
BASE._plan = _plan


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--source-sha256", required=True)
    parser.add_argument(
        "--total-seconds",
        type=float,
        default=BASE.DEFAULT_TOTAL_SECONDS,
    )
    parser.add_argument(
        "--search-seconds",
        type=float,
        default=BASE.DEFAULT_SEARCH_SECONDS,
    )
    parser.add_argument("--starts", type=int, default=BASE.DEFAULT_STARTS)
    parser.add_argument(
        "--callbacks-per-start",
        type=int,
        default=BASE.DEFAULT_CALLBACKS_PER_START,
    )
    parser.add_argument(
        "--aggregate-callback-cap",
        type=int,
        default=BASE.DEFAULT_AGGREGATE_CALLBACK_CAP,
    )
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--cpu", type=int, default=13)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--plan-sha256")
    return parser


def _validate_arguments(arguments: argparse.Namespace) -> None:
    if len(arguments.source_sha256) != 64:
        raise SystemExit("source SHA-256 must contain 64 hexadecimal digits")
    try:
        int(arguments.source_sha256, 16)
    except ValueError as error:
        raise SystemExit("source SHA-256 must be hexadecimal") from error
    if arguments.cpu < 0 or arguments.cpu >= 16:
        raise SystemExit("CPU must be a first-sibling physical core in [0,15]")
    if (
        not math.isfinite(arguments.total_seconds)
        or not math.isfinite(arguments.search_seconds)
        or arguments.total_seconds <= 0.0
        or arguments.total_seconds > 180.0
        or arguments.search_seconds <= 0.0
        or arguments.search_seconds
        > arguments.total_seconds
        - BASE.SELECTION_RESERVE_SECONDS
        - BASE.FINALIZE_RESERVE_SECONDS
        - BASE.MIN_HP_ATTEMPT_SECONDS
        or arguments.starts < 1
        or arguments.callbacks_per_start < 2
        or arguments.aggregate_callback_cap < 1
    ):
        raise SystemExit("invalid integrated wall/callback budget")


def _source_exact_descriptor(result: object) -> dict[str, object] | None:
    """Accept only the source-exact descriptor variant, never numeric claims."""

    if (
        not isinstance(result, Mapping)
        or result.get("status") != "EXACT_SYMBOLIC_TARGET_READY"
        or result.get("authority_pass") is not True
        or result.get("exact_authority_kind") != ZERO_AUTHORITY_KIND
        or result.get("numeric_pslq_descriptor_used") is not False
    ):
        return None
    descriptor = result.get("exact_target_descriptor")
    certificates = result.get("source_certificates")
    routing = result.get("routing_audit")
    if not isinstance(descriptor, Mapping) or not isinstance(
        certificates, Mapping
    ):
        return None
    required_certificates = (
        "target_algebraicity_from_source_ast",
        "target_evaluated_exactly_from_source_ast",
        "primitive_square_free_irreducible_minpoly",
        "exact_rational_root_isolator",
        "all_constraints_exactly_zero",
        "all_guards_exactly_true",
    )
    if any(certificates.get(field) is not True for field in required_certificates):
        return None
    if (
        not isinstance(routing, Mapping)
        or routing.get("case_id_read") is not False
        or routing.get("family_read") is not False
        or routing.get("truth_read") is not False
        or routing.get("known_target_count_read") is not False
        or routing.get("target_value_used_for_routing") is not False
    ):
        return None
    polynomial = descriptor.get("minimal_polynomial_high_to_low")
    root_index = descriptor.get("selected_real_root_index")
    isolator = descriptor.get("isolating_interval")
    if (
        descriptor.get("authority_kind") != ZERO_AUTHORITY_KIND
        or descriptor.get("numeric_pslq_used") is not False
        or not isinstance(polynomial, list)
        or not polynomial
        or not all(
            isinstance(value, int) and not isinstance(value, bool)
            for value in polynomial
        )
        or not isinstance(root_index, int)
        or isinstance(root_index, bool)
        or root_index < 0
        or not isinstance(isolator, Mapping)
        or descriptor.get("primitive") is not True
        or descriptor.get("square_free") is not True
        or descriptor.get("irreducible_over_Q") is not True
    ):
        return None
    return dict(descriptor)


def _zero_result(
    *,
    arguments: argparse.Namespace,
    source_payload: bytes,
) -> dict[str, object]:
    available = max(
        0.25,
        arguments.total_seconds
        - (time.monotonic() - PROCESS_STARTED)
        - BASE.FINALIZE_RESERVE_SECONDS,
    )
    deadline_seconds = min(8.0, available)
    primary_cap_seconds = min(4.0, deadline_seconds)
    authority = ZERO.run_zero_dimensional_authority(
        source_payload,
        arguments.source_sha256,
        (),
        deadline_seconds=deadline_seconds,
        primary_cap_seconds=primary_cap_seconds,
    )
    descriptor = _source_exact_descriptor(authority)
    exact_targets = [descriptor] if descriptor is not None else []
    source_unchanged = arguments.source.read_bytes() == source_payload
    elapsed = time.monotonic() - PROCESS_STARTED
    if not source_unchanged:
        raise RuntimeError("source bytes changed during zero-dimensional run")
    return {
        "schema_version": BASE.SCHEMA,
        "status": (
            "ZERO_DIMENSIONAL_SOURCE_EXACT_COMPLETE"
            if descriptor is not None
            else "ZERO_DIMENSIONAL_FAIL_CLOSED"
        ),
        "completed": True,
        "source_sha256": arguments.source_sha256,
        "source_bytes_unchanged": True,
        "elapsed_wall_seconds": elapsed,
        "within_total_wall_budget": elapsed <= arguments.total_seconds,
        "seed": arguments.seed,
        "search": {
            "arm": "source_exact_zero_dimensional_bypass",
            "process_classification": "NOT_LAUNCHED_UNIQUE_EMPTY_CONFIGURATION",
            "artifact_accepted": True,
            "endpoint_count": 1,
            "fresh_safe_provisional_cluster_count": 1,
            "fresh_safe_selected_candidate_count": 1,
            "maximum_candidates_per_provisional_cluster": 1,
        },
        "hp_attempt_count": 0,
        "hp_attempts": [],
        "hp_schedule": {
            "search_bypassed": True,
            "numeric_replay_only": True,
            "numeric_pslq_descriptor_used": False,
            "source_exact_authority_kind": ZERO_AUTHORITY_KIND,
        },
        "distinct_exact_targets": exact_targets,
        "distinct_exact_target_descriptors": exact_targets,
        "distinct_exact_target_count": len(exact_targets),
        "exact_descriptor_novelty_key": (
            "minimal polynomial high-to-low plus selected real-root index"
        ),
        "zero_dimensional_authority_audit": {
            "status": (
                authority.get("status")
                if isinstance(authority, Mapping)
                else "MALFORMED"
            ),
            "authority_pass": (
                authority.get("authority_pass")
                if isinstance(authority, Mapping)
                else False
            ),
            "failure_reasons": (
                authority.get("failure_reasons")
                if isinstance(authority, Mapping)
                else ["MALFORMED_AUTHORITY_RESULT"]
            ),
            "numeric_replay_artifact_sha256": (
                authority.get("numeric_replay_artifact_sha256")
                if isinstance(authority, Mapping)
                else None
            ),
            "numeric_pslq_descriptor_used": False,
        },
        "target_image_completeness_claim": descriptor is not None,
        "target_image_completeness_scope": (
            "unique zero-dimensional source configuration only"
        ),
        "truth_case_family_known_target_count_read": False,
        "source_or_problem_modified": False,
        "variables_or_equations_removed": False,
        "bounds_added_or_inferred": False,
        "gauge_or_symmetry_reduction": False,
        "coordinate_reparameterization": False,
    }


def _run_zero(
    arguments: argparse.Namespace,
    source_payload: bytes,
) -> None:
    output = arguments.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    plan = _plan(
        source=arguments.source,
        source_sha256=arguments.source_sha256,
        total_seconds=arguments.total_seconds,
        search_seconds=arguments.search_seconds,
        starts=arguments.starts,
        callbacks_per_start=arguments.callbacks_per_start,
        aggregate_callback_cap=arguments.aggregate_callback_cap,
        seed=arguments.seed,
        cpu=arguments.cpu,
        output=output,
    )
    plan_path = output / "PLAN.json"
    BASE.atomic_write_json(plan_path, plan)
    plan_sha256 = _sha256(plan_path.read_bytes())
    if not arguments.execute:
        print(json.dumps({"plan_sha256": plan_sha256, **plan}, indent=2))
        return
    if arguments.plan_sha256 != plan_sha256:
        raise SystemExit("execution requires the exact dry-run PLAN SHA-256")
    if sorted(os.sched_getaffinity(0)) != [arguments.cpu]:
        raise SystemExit("execution requires the outer worker pinned to --cpu")
    _zero_closure()
    result = _zero_result(arguments=arguments, source_payload=source_payload)
    BASE.atomic_write_json(output / "RESULT.json", result)


def main() -> None:
    arguments = _parser().parse_args()
    _validate_arguments(arguments)
    source_payload, source_document = BASE._source_contract(
        arguments.source,
        arguments.source_sha256,
    )
    names = source_document["variables"]["names"]
    if names:
        # Parsing above is only a dimension gate.  Champion_v1 owns every
        # positive-dimensional runtime decision and parses the unchanged argv.
        V1.main()
        return
    _run_zero(arguments, source_payload)


if __name__ == "__main__":
    main()
