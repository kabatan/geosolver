#!/usr/bin/env python3.12
"""Anonymous static/stored/pure-gain gates for exact anchored EDM reconstruction."""

from __future__ import annotations

import argparse
import ast
from collections import Counter
from fractions import Fraction
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import time
from typing import Mapping, Sequence

from candidate import Inapplicable, reconstruct_anchored_edm


REQUESTS_SHA256 = "ee424315256582652ea0df72a05c21903a5fd4366867c6788129a79e4f80fd35"
APPROVED_SOURCE_ROOT = Path(
    "/home/kabatan/work/solver-experiment-results/partial-ideal-root-readiness-v1/degree1-inputs"
).resolve()
APPROVED_REQUESTS = APPROVED_SOURCE_ROOT.parent / "degree1-requests.json"
PANEL_PROVENANCE = APPROVED_SOURCE_ROOT.parent / "DEGREE1_REQUEST_AGGREGATE.json"
PANEL_PROVENANCE_SHA256 = "c686498c6fec6b5a8f6d03eae68ef991ed1ea6998d3ea9479ba78d25f9ea74d3"
APPROVED_PYTHON = Path("/home/kabatan/work/solver/.venv/bin/python").resolve()
APPROVED_PYTHON_SHA256 = "ccc93c55c24bb92866cc2f9eff61b124abf5d1ee6c8da0ef9b5eed4d78a21f07"
ROW_KEYS = frozenset(("candidate_relation_high_to_low", "endpoint", "source_path"))
FORBIDDEN_SOURCE_KEYS = frozenset(
    ("id", "case_id", "problem_id", "family", "truth", "outcome", "result", "score", "known_count")
)
RUNTIME_SHA256 = "5594c7f673171999ac4455f00223861673ea42bc02be1bb3e115f28951dfdaf1"
AUTHORITY_RUNTIME_SHA256 = "a3596c7273122ee49f537a43c1c05b57318a86b56bfdf6f19eb0bd20c6f59796"
EXACT_WORKER_SHA256 = "44d6fa802dc51e7f58e5a72e48b434a62be84275c328bd605f0e9e2f6eb11900"
POINT_OPERATORS = frozenset(
    (
        "Point", "Intersect", "Midpoint", "Centroid", "Circumcenter", "Incenter",
        "Orthocenter", "FootOfPerpendicular", "IncircleContactPoint", "ContactPoint",
        "PointOnCircle", "PointOnSegment", "Reflect", "Center",
    )
)
MAX_DENOMINATOR = 1_000_000
RECOGNITION_TOLERANCE = 2.0e-8


def _sha(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _endpoint_sha(endpoint: Sequence[float]) -> str:
    payload = struct.pack(">I", len(endpoint)) + b"".join(
        struct.pack(">d", float(value)) for value in endpoint
    )
    return _sha(payload)


def _load(name: str, path: Path, expected: str):
    if not path.is_file() or _sha(path.read_bytes()) != expected:
        raise SystemExit(f"pinned runtime changed: {path.name}")
    specification = importlib.util.spec_from_file_location(name, path)
    if specification is None or specification.loader is None:
        raise SystemExit(f"cannot load pinned runtime: {path}")
    module = importlib.util.module_from_spec(specification)
    sys.modules[name] = module
    specification.loader.exec_module(module)
    if Path(module.__file__).resolve() != path.resolve():
        raise SystemExit("loaded runtime identity changed")
    return module


def _name(node: ast.AST) -> str | None:
    return node.id if isinstance(node, ast.Name) else None


def _exact_constant(node: ast.AST) -> Fraction | None:
    sign = 1
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)):
        sign = -1 if isinstance(node.op, ast.USub) else 1
        node = node.operand
    if not isinstance(node, ast.Constant) or isinstance(node.value, bool):
        return None
    try:
        return sign * Fraction(str(node.value))
    except (ValueError, ZeroDivisionError):
        return None


def _source_plan(document: Mapping[str, object]):
    construction = document.get("construction")
    if not isinstance(construction, list):
        return None
    calls: dict[str, ast.Call] = {}
    source_order = []
    fixed: dict[str, tuple[Fraction, Fraction]] = {}
    variable_points: dict[str, tuple[str | None, str | None]] = {}
    variable_names = set(((document.get("variables") or {}).get("names") or [])) if isinstance(document.get("variables"), Mapping) else set()
    for item in construction:
        if not isinstance(item, Mapping) or not isinstance(item.get("name"), str) or not isinstance(item.get("expr"), str):
            continue
        try:
            node = ast.parse(item["expr"], mode="eval").body
        except SyntaxError:
            continue
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name) or node.func.id not in POINT_OPERATORS:
            continue
        name = item["name"]
        calls[name] = node
        source_order.append(name)
        if node.func.id == "Point" and len(node.args) == 2:
            x_exact, y_exact = _exact_constant(node.args[0]), _exact_constant(node.args[1])
            if x_exact is not None and y_exact is not None:
                fixed[name] = (x_exact, y_exact)
            x_name, y_name = _name(node.args[0]), _name(node.args[1])
            if (x_name in variable_names) or (y_name in variable_names):
                variable_points[name] = (
                    x_name if x_name in variable_names else None,
                    y_name if y_name in variable_names else None,
                )

    metric = set()
    expressions = []
    constraints = document.get("constraints")
    if isinstance(constraints, list):
        for constraint in constraints:
            if isinstance(constraint, Mapping):
                expressions.extend(value for value in constraint.values() if isinstance(value, str))
    if isinstance(document.get("answer"), str):
        expressions.append(document["answer"])
    for expression in expressions:
        try:
            tree = ast.parse(expression, mode="eval")
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if not (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "Distance"
            ):
                continue
            metric.update(
                argument.id
                for argument in node.args
                if isinstance(argument, ast.Name) and argument.id in calls
            )
    labels = tuple(name for name in source_order if name in metric)
    if len(labels) < 3:
        return None
    signature = "K3" if len(labels) == 3 else "K4" if len(labels) == 4 else "K5PLUS"
    anchors = tuple(name for name in labels if name in fixed)
    dynamic = tuple(name for name in labels if name in variable_points)
    return {
        "labels": labels,
        "signature": signature,
        "fixed": fixed,
        "anchors": anchors,
        "variable_points": variable_points,
        "dynamic": dynamic,
    }


def _xy(value: object) -> tuple[float, float]:
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)) and len(value) == 2:
        return float(value[0]), float(value[1])
    for x_name, y_name in (("x", "y"), ("X", "Y")):
        if hasattr(value, x_name) and hasattr(value, y_name):
            return float(getattr(value, x_name)), float(getattr(value, y_name))
    raise Inapplicable("POINT_VALUE_UNAVAILABLE")


def _recognize_square(value: float) -> Fraction:
    if not math.isfinite(value) or value <= 0:
        raise Inapplicable("NONPOSITIVE_NUMERIC_SQUARED_DISTANCE")
    exact = Fraction(value).limit_denominator(MAX_DENOMINATOR)
    if not math.isclose(float(exact), value, rel_tol=RECOGNITION_TOLERANCE, abs_tol=RECOGNITION_TOLERANCE):
        raise Inapplicable("RATIONAL_SQUARED_DISTANCE_RECOGNITION_FAILED")
    return exact


def _context(runtime, document, endpoint):
    _case, _budget, evaluator = runtime.build_source_case(
        document, callback_cap=8, deadline=time.monotonic() + 2.0
    )
    bundle = evaluator.bundle
    context = dict(bundle.base_context)
    runtime.AUTHORITY._assign_variables(context, list(bundle.var_names), endpoint)
    for item in bundle.spec.construction:
        context[item.name] = runtime.AUTHORITY.safe_eval_expr(item.expr, context)
    return evaluator, context, tuple(bundle.var_names)


def _source_replay_ready(evaluator, endpoint) -> bool:
    try:
        residual = evaluator.evaluate_float_residual(endpoint)
        guard_ok, _violations = evaluator.evaluate_guard(endpoint)
        hard = evaluator.evaluate_float_hard_feasibility(endpoint)
        return bool(
            residual.is_finite
            and float(residual.residual_norm_float) <= 1.0e-8
            and guard_ok
            and hard.hard_feasible
        )
    except Exception:
        return False


def _exact_ready(value: object, source_sha: str, endpoint_sha: str) -> bool:
    exact = value.get("exact_coordinate_authority") if isinstance(value, Mapping) else None
    numeric = value.get("numeric_source_replay") if isinstance(value, Mapping) else None
    lanes = numeric.get("lane_source_replay") if isinstance(numeric, Mapping) else None
    return bool(
        isinstance(value, Mapping)
        and value.get("schema_version") == "geotarget.v15-243-exact-coordinate-fallback/v1"
        and value.get("completed") is True
        and value.get("status") == "EXACT_COORDINATE_TARGET_AUTHORITY_READY"
        and value.get("authority_pass") is True
        and value.get("source_sha256") == source_sha
        and value.get("endpoint_float64_sha256") == endpoint_sha
        and value.get("truth_used") is False
        and value.get("case_family_known_target_count_routing") is False
        and value.get("source_or_problem_modified") is False
        and value.get("bounds_added_or_inferred") is False
        and value.get("coordinate_reparameterization") is False
        and value.get("target_set_completeness_claim") is False
        and value.get("within_fallback_wall_budget") is True
        and value.get("numeric_guard_branch_replay_is_authority") is True
        and value.get("numeric_target_nearness_is_authority") is False
        and value.get("numeric_float_residual_is_authority") is False
        and isinstance(value.get("descriptor"), Mapping)
        and isinstance(exact, Mapping)
        and exact.get("schema_version") == "geotarget.v15-243-exact-coordinate-replay/v1"
        and exact.get("status") == "EXACT_TARGET_AUTHORITY_READY"
        and exact.get("authority_pass") is True
        and exact.get("truth_used") is False
        and exact.get("source_replay_required") is True
        and exact.get("source_semantic_lowering_endpoint_independent") is True
        and isinstance(exact.get("source_constraints_exact"), int)
        and not isinstance(exact.get("source_constraints_exact"), bool)
        and exact.get("source_constraints_exact") >= 0
        and isinstance(exact.get("source_guards_exact"), int)
        and not isinstance(exact.get("source_guards_exact"), bool)
        and exact.get("source_guards_exact") >= 0
        and isinstance(exact.get("source_bounds_exact"), int)
        and not isinstance(exact.get("source_bounds_exact"), bool)
        and exact.get("source_bounds_exact") >= 0
        and exact.get("source_raw_answer_exact") is True
        and exact.get("target_link_exact") is True
        and exact.get("post_process_used") is False
        and exact.get("target_set_completeness_claim") is False
        and isinstance(numeric, Mapping)
        and numeric.get("schema_version") == "geotarget.v15-243-frozen-numeric-source-replay/v1"
        and numeric.get("source_sha256") == source_sha
        and numeric.get("float_endpoint_source_replay_required") is True
        and numeric.get("all_precision_lanes_guard_and_hard_feasible") is True
        and numeric.get("all_precision_lanes_source_residual_reached") is True
        and numeric.get("coordinates_linked_to_exact_roots_by_independent_lanes") is True
        and numeric.get("branch_and_guard_parity_is_not_inferred_from_qqbar") is True
        and isinstance(lanes, Mapping)
        and set(lanes) == {"155", "232", "320"}
        and all(
            isinstance(lanes[key], Mapping)
            and lanes[key].get("guard_ok") is True
            and lanes[key].get("hard_feasible") is True
            and lanes[key].get("residual_reached") is True
            and lanes[key].get("answer_defined") is True
            for key in ("155", "232", "320")
        )
    )


def _run_exact(python: Path, worker: Path, source: Path, source_sha: str, endpoint, timeout: float):
    endpoint_sha = _endpoint_sha(endpoint)
    with tempfile.TemporaryDirectory(prefix="edm-gram-exact-") as temporary:
        output = Path(temporary) / "RESULT.json"
        command = [
            str(python), str(worker), "--source", str(source),
            "--source-sha256", source_sha,
            "--endpoint", json.dumps(endpoint, separators=(",", ":")),
            "--endpoint-sha256", endpoint_sha,
            "--timeout-seconds", str(timeout), "--output", str(output),
        ]
        try:
            completed = subprocess.run(
                command, check=False, timeout=timeout + 1.0,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
        except subprocess.TimeoutExpired:
            return False, endpoint_sha
        if completed.returncode != 0:
            return False, endpoint_sha
        try:
            result = json.loads(output.read_bytes())
        except (OSError, json.JSONDecodeError):
            return False, endpoint_sha
        if _sha(source.read_bytes()) != source_sha:
            raise SystemExit("source bytes changed across exact replay")
    return _exact_ready(result, source_sha, endpoint_sha), endpoint_sha


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--requests", type=Path, required=True)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--runtime-root", type=Path, required=True)
    parser.add_argument("--python", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--private-signatures", type=Path, required=True)
    parser.add_argument("--expected-cpu", type=int, default=14)
    parser.add_argument("--exact-timeout-seconds", type=float, default=5.0)
    parser.add_argument("--execute-stored", action="store_true")
    parser.add_argument("--execute-exact", action="store_true")
    arguments = parser.parse_args()
    if arguments.execute_exact and not arguments.execute_stored:
        raise SystemExit("exact gate requires stored gate")
    if arguments.python.resolve() != APPROVED_PYTHON or _sha(APPROVED_PYTHON.read_bytes()) != APPROVED_PYTHON_SHA256:
        raise SystemExit("unapproved exact-gate Python")
    if os.sched_getaffinity(0) != {arguments.expected_cpu}:
        raise SystemExit("real gate must be pinned to expected CPU")
    if arguments.source_root.resolve() != APPROVED_SOURCE_ROOT:
        raise SystemExit("unapproved anonymous source root")
    if arguments.requests.resolve() != APPROVED_REQUESTS:
        raise SystemExit("unapproved anonymous request panel")
    provenance_payload = PANEL_PROVENANCE.read_bytes()
    if _sha(provenance_payload) != PANEL_PROVENANCE_SHA256:
        raise SystemExit("request-panel provenance SHA mismatch")
    provenance = json.loads(provenance_payload)
    if provenance != {
        "anonymous_projection_count": 85,
        "answer_field_semantics": "untouched source raw-target expression only",
        "offline_truth_or_expected_value_retained": False,
        "problem_ids_retained": False,
        "request_count": 85,
        "requests_sha256": REQUESTS_SHA256,
        "schema_version": "partial-ideal-degree1-request-panel-v1",
        "selection": "first degree-one ordinary HP proposal per source; no exact outcome filter",
    }:
        raise SystemExit("request-panel outcome-blind provenance mismatch")
    request_payload = arguments.requests.read_bytes()
    if _sha(request_payload) != REQUESTS_SHA256:
        raise SystemExit("requests SHA mismatch")
    rows = json.loads(request_payload)
    if not isinstance(rows, list) or len(rows) != 85 or any(not isinstance(row, Mapping) or set(row) != ROW_KEYS for row in rows):
        raise SystemExit("anonymous request schema mismatch")

    prepared = []
    static_signatures = set()
    counters = Counter()
    for row in rows:
        source_argument = Path(str(row["source_path"])).absolute()
        if source_argument.is_symlink():
            raise SystemExit("anonymous source projection is a symlink")
        source = source_argument.resolve()
        if source.parent != APPROVED_SOURCE_ROOT or len(source.stem) != 4 or not source.stem.isdigit() or source.suffix != ".json":
            raise SystemExit("anonymous source path is not a direct four-digit projection")
        try:
            source.relative_to(APPROVED_SOURCE_ROOT)
        except ValueError:
            raise SystemExit("anonymous source escaped approved root")
        payload = source.read_bytes()
        document = json.loads(payload)
        if not isinstance(document, Mapping) or FORBIDDEN_SOURCE_KEYS & set(document):
            raise SystemExit("source crossed identity/truth boundary")
        plan = _source_plan(document)
        if plan is None:
            counters["static_inapplicable"] += 1
            continue
        counters["static_activated"] += 1
        static_signatures.add(plan["signature"])
        prepared.append((row, source, _sha(payload), dict(document), plan))
    static_pass = counters["static_activated"] >= 6 and len(static_signatures) >= 3

    runtime = None
    exact_worker = None
    if arguments.execute_stored and static_pass:
        runtime_path = arguments.runtime_root.resolve() / "research/experiments/EXP-REAL61-008/source_only/runtime.py"
        authority_runtime = arguments.runtime_root.resolve() / "research/experiments/EXP-REAL61-007/provisional_numerical_architecture/source_only_runtime.py"
        exact_worker = arguments.runtime_root.resolve() / "research/experiments/EXP-V15-243-001/candidates/exact_coordinate_replay/fallback_worker.py"
        runtime = _load("geotarget_edm_source_runtime", runtime_path, RUNTIME_SHA256)
        if _sha(authority_runtime.read_bytes()) != AUTHORITY_RUNTIME_SHA256 or Path(runtime.AUTHORITY_PATH).resolve() != authority_runtime:
            raise SystemExit("source runtime authority closure changed")
        if _sha(exact_worker.read_bytes()) != EXACT_WORKER_SHA256:
            raise SystemExit("exact replay worker changed")

    stored_sources = set()
    stored_signatures = set()
    pure_sources = set()
    pure_signatures = set()
    private = []
    if runtime is not None:
        for row, source, source_sha, document, plan in prepared:
            if len(plan["anchors"]) < 2 or not plan["dynamic"]:
                counters["stored_missing_fixed_anchor_or_dynamic_point"] += 1
                continue
            # Bound the disposable lane to two fixed anchors plus at most three
            # further metric points. Source order, not identity/outcome, decides.
            anchor_left, anchor_right = plan["anchors"][:2]
            labels = [anchor_left, anchor_right, plan["dynamic"][0]]
            labels.extend(label for label in plan["labels"] if label not in labels)
            labels = tuple(labels[:5])
            endpoint = [float(value) for value in row["endpoint"]]
            try:
                evaluator, context, variable_names = _context(runtime, document, endpoint)
                xy = {label: _xy(context[label]) for label in labels}
                distances = {}
                for left_index, left in enumerate(labels):
                    for right in labels[left_index + 1 :]:
                        dx = xy[left][0] - xy[right][0]
                        dy = xy[left][1] - xy[right][1]
                        distances[frozenset((left, right))] = _recognize_square(dx * dx + dy * dy)
                reconstruction = reconstruct_anchored_edm(
                    labels=labels,
                    squared_distances=distances,
                    anchor_left=anchor_left,
                    anchor_right=anchor_right,
                    anchor_left_xy=plan["fixed"][anchor_left],
                    anchor_right_xy=plan["fixed"][anchor_right],
                )
            except Exception:
                counters["stored_exact_edm_inapplicable"] += 1
                continue

            proposals = []
            variable_index = {name: index for index, name in enumerate(variable_names)}
            for branch in reconstruction.branches:
                proposal = list(endpoint)
                assignments: dict[int, float] = {}
                consistent = True
                for label in labels:
                    coordinate_names = plan["variable_points"].get(label)
                    if coordinate_names is None:
                        continue
                    values = (branch[label].x.as_float(), branch[label].y.as_float())
                    for name, value in zip(coordinate_names, values):
                        if name is None:
                            continue
                        index = variable_index[name]
                        if index in assignments and not math.isclose(assignments[index], value, rel_tol=1.0e-12, abs_tol=1.0e-12):
                            consistent = False
                            break
                        assignments[index] = value
                    if not consistent:
                        break
                if consistent and assignments:
                    for index, value in assignments.items():
                        proposal[index] = value
                    if _source_replay_ready(evaluator, proposal):
                        proposals.append(proposal)
            if not proposals:
                counters["stored_branch_float_replay_rejected"] += 1
                continue
            signature = "K3" if len(labels) == 3 else "K4" if len(labels) == 4 else "K5PLUS"
            stored_sources.add(source_sha)
            stored_signatures.add(signature)
            counters["stored_activated"] += 1

            if arguments.execute_exact:
                baseline_sha = _endpoint_sha(endpoint)
                distinct = []
                seen = set()
                for proposal in proposals:
                    proposal_sha = _endpoint_sha(proposal)
                    if proposal_sha == baseline_sha:
                        counters["candidate_endpoint_digest_equals_baseline"] += 1
                    elif proposal_sha in seen:
                        counters["candidate_endpoint_digest_duplicate"] += 1
                    else:
                        distinct.append(proposal)
                        seen.add(proposal_sha)
                if not distinct:
                    counters["candidate_no_distinct_endpoint_for_exact_gate"] += 1
                    continue

                # Fixed ABBA: exactly two candidate and two baseline calls at
                # the same per-call deadline.  One candidate is duplicated if
                # only one reflection survives; neither readiness outcome can
                # suppress a later call.
                candidate_attempts = (distinct + distinct)[:2]
                schedule = (
                    ("candidate", candidate_attempts[0]),
                    ("baseline", endpoint),
                    ("baseline", endpoint),
                    ("candidate", candidate_attempts[1]),
                )
                candidate_ready = []
                baseline_ready = False
                for route, exact_endpoint in schedule:
                    ready, exact_sha = _run_exact(
                        arguments.python.resolve(), exact_worker, source, source_sha,
                        exact_endpoint, arguments.exact_timeout_seconds,
                    )
                    counters[f"{route}_exact_attempt"] += 1
                    if route == "candidate" and ready:
                        candidate_ready.append(exact_sha)
                    elif route == "baseline" and ready:
                        baseline_ready = True
                candidate_ready = sorted(set(candidate_ready))
                if candidate_ready:
                    counters["candidate_exact_replay_ready"] += 1
                if baseline_ready:
                    counters["baseline_exact_replay_ready"] += 1
                if candidate_ready and not baseline_ready:
                    pure_sources.add(source_sha)
                    pure_signatures.add(signature)
                    counters["pure_gain"] += 1
                    private.extend(
                        {"source_sha256": source_sha, "endpoint_float64_sha256": value}
                        for value in candidate_ready
                    )

    stored_pass = len(stored_sources) >= 4 and len(stored_signatures) >= 2
    pure_pass = len(pure_sources) >= 2 and len(pure_signatures) >= 2
    private.sort(key=lambda item: (item["source_sha256"], item["endpoint_float64_sha256"]))
    private_payload = json.dumps(private, sort_keys=True, separators=(",", ":")).encode("ascii") + b"\n"
    arguments.private_signatures.parent.mkdir(parents=True, exist_ok=True)
    arguments.private_signatures.write_bytes(private_payload)
    if not static_pass:
        disposition = "STOP_STATIC_PREVALENCE_GATE"
    elif not arguments.execute_stored:
        disposition = "STATIC_GATE_PASS_STORED_PENDING"
    elif not stored_pass:
        disposition = "STOP_STORED_ACTIVATION_GATE"
    elif not arguments.execute_exact:
        disposition = "STORED_GATE_PASS_PURE_GAIN_PENDING"
    elif not pure_pass:
        disposition = "STOP_PURE_GAIN_GATE"
    else:
        disposition = "PROCEED_FORMAL_CANDIDATE_INTEGRATION"
    aggregate = {
        "schema_version": "geotarget.post-endpoint-edm-gram-exact-reopen-real-gate/v1",
        "request_count": len(rows),
        "requests_sha256": REQUESTS_SHA256,
        "request_panel_provenance_sha256": PANEL_PROVENANCE_SHA256,
        "python_sha256": APPROVED_PYTHON_SHA256,
        "exact_schedule": "ABBA_TWO_CANDIDATE_TWO_BASELINE_EQUAL_TIMEOUT",
        "static_activated_source_count": counters["static_activated"],
        "static_signature_count": len(static_signatures),
        "stored_activated_source_count": len(stored_sources),
        "stored_signature_count": len(stored_signatures),
        "pure_gain_source_count": len(pure_sources),
        "pure_gain_signature_count": len(pure_signatures),
        "static_gate_pass": static_pass,
        "stored_gate_pass": stored_pass if arguments.execute_stored else None,
        "pure_gain_gate_pass": pure_pass if arguments.execute_exact else None,
        "disposition": disposition,
        "status_histogram": dict(sorted(counters.items())),
        "private_signature_count": len(private),
        "private_signatures_sha256": _sha(private_payload),
        "individual_signatures_emitted_in_aggregate": False,
        "source_parser_or_compiler_modified": False,
        "authority_pass": False,
        "target_release": False,
        "truth_case_family_target_count_outcome_routing": False,
    }
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_text(json.dumps(aggregate, sort_keys=True, separators=(",", ":")) + "\n")
    print(json.dumps(aggregate, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
