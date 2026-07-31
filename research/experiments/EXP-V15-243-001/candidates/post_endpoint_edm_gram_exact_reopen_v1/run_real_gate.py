#!/usr/bin/env python3.12
"""Anonymous static/stored/pure-gain gates for exact anchored EDM reconstruction."""

from __future__ import annotations

import argparse
import atexit
import ast
from collections import Counter
from decimal import Decimal, InvalidOperation
from fractions import Fraction
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import struct
import sys
import tempfile
import time
from typing import Mapping, Sequence

from candidate import Inapplicable, reconstruct_anchored_edm
from execution_guard import (
    FormalRunLease,
    atomic_write_0600,
    canonical_json,
    run_contained,
)


REQUESTS_SHA256 = "ee424315256582652ea0df72a05c21903a5fd4366867c6788129a79e4f80fd35"
APPROVED_SOURCE_ROOT = Path(
    "/home/kabatan/work/solver-experiment-results/partial-ideal-root-readiness-v1/degree1-inputs"
).resolve()
APPROVED_REQUESTS = APPROVED_SOURCE_ROOT.parent / "degree1-requests.json"
PANEL_PROVENANCE = APPROVED_SOURCE_ROOT.parent / "DEGREE1_REQUEST_AGGREGATE.json"
PANEL_PROVENANCE_SHA256 = "c686498c6fec6b5a8f6d03eae68ef991ed1ea6998d3ea9479ba78d25f9ea74d3"
APPROVED_PYTHON = Path("/home/kabatan/work/solver/.venv/bin/python").resolve()
APPROVED_PYTHON_SHA256 = "ccc93c55c24bb92866cc2f9eff61b124abf5d1ee6c8da0ef9b5eed4d78a21f07"
APPROVED_RUNTIME_ROOT = Path("/home/kabatan/work/solver-experiment-runtime/solver").resolve()
APPROVED_RUNTIME_PYTHON = (APPROVED_RUNTIME_ROOT / "python/.venv/bin/python").resolve()
APPROVED_JULIA = Path(
    "/home/kabatan/.julia/juliaup/julia-1.12.6+0.x64.linux.gnu/bin/julia"
).resolve()
APPROVED_JULIA_SHA256 = "fd670aabc838e93f178cbcf7304c5e9c50aadcce3735e86d5e3218b1bb04e602"
APPROVED_GEOSOLVER_SOURCE = Path("/home/kabatan/work/geosolver/src").resolve()
APPROVED_GEOSOLVER_TREE_SHA256 = "03e38d35d33db708b64ca1202720154a76bc30052fc5ce737515eadaa5dcd732"
RUNTIME_CLOSURE_FILES = {
    "authority_runtime": (
        "research/experiments/EXP-REAL61-007/provisional_numerical_architecture/source_only_runtime.py",
        "a3596c7273122ee49f537a43c1c05b57318a86b56bfdf6f19eb0bd20c6f59796",
    ),
    "source_runtime": (
        "research/experiments/EXP-REAL61-008/source_only/runtime.py",
        "5594c7f673171999ac4455f00223861673ea42bc02be1bb3e115f28951dfdaf1",
    ),
    "exact_worker": (
        "research/experiments/EXP-V15-243-001/candidates/exact_coordinate_replay/fallback_worker.py",
        "44d6fa802dc51e7f58e5a72e48b434a62be84275c328bd605f0e9e2f6eb11900",
    ),
    "exact_candidate": (
        "research/experiments/EXP-V15-243-001/candidates/exact_coordinate_replay/candidate.py",
        "e0f24e605e7e7211d134ddea66e66adbb89307148a8f03c1afebd4a2c969c66f",
    ),
    "root_ordinal_audit": (
        "research/experiments/EXP-V15-243-001/candidates/exact_coordinate_replay/FINAL_ROOT_ORDINAL_BOUNDARY_AUDIT.json",
        "fa133c7243b9f455bbb4f80de1613efc53bc590ffc8556ec8ea4eee2377c3566",
    ),
    "numeric_refiner": (
        "research/experiments/EXP-REAL61-001/refine_proposals_worker.py",
        "14a107893f6db1b9ec113c28653a40b3817f274865b0fabc64e2a13702bdc7b3",
    ),
    "legacy_runtime": (
        "research/experiments/EXP-REAL61-001/legacy61_runtime.py",
        "3261a6289f4a43681e698937c158d4a4f1740e54b70b88559c399e3b6395ec2b",
    ),
    "qqbar_dag": (
        "research/experiments/EXP-REAL61-004/qqbar_exact_replay/dag_compile.py",
        "9b83181004a8ea2ea73f2974129e37ce252f7d352937b9f8b601b39eddf03d18",
    ),
    "qqbar_worker": (
        "research/experiments/EXP-REAL61-004/qqbar_exact_replay/qqbar_worker.jl",
        "3ac6415600da77f8748a11d15fa47eb3dcb9f8deada375388fc762a155df0b4a",
    ),
    "julia_project": (
        "research/experiments/EXP-REAL61-002/target_elimination/Project.toml",
        "9f39a2eb827fcc842513037ed5d9debbe1e1cf15a24e29111645917e9acaa6c7",
    ),
    "julia_manifest": (
        "research/experiments/EXP-REAL61-002/target_elimination/Manifest.toml",
        "0b93cd67d522d4cce3bea7b3a754109a972e1eb2ef7fabe7eecb6c7a3cb19b42",
    ),
}
APPROVED_RUNTIME_CLOSURE_SHA256 = "ec2d5c933d947549194e9226170702360a8e3d350d69b7c07267afe2624a55a9"
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
EXACT_ADDRESS_SPACE_CAP_BYTES = 12 * 1024**3
EXACT_RSS_CAP_BYTES = 10 * 1024**3
EXACT_DATA_CAP_BYTES = 12 * 1024**3
EXACT_FILE_CAP_BYTES = 16 * 1024**2
EXACT_LOG_CAP_BYTES = 2 * 1024**2


def _sha(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _tree_sha(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(root.rglob("*")):
        if not path.is_file() or "__pycache__" in path.parts:
            continue
        relative = path.relative_to(root).as_posix().encode("utf-8")
        payload = path.read_bytes()
        digest.update(len(relative).to_bytes(4, "big"))
        digest.update(relative)
        digest.update(len(payload).to_bytes(8, "big"))
        digest.update(payload)
    return digest.hexdigest()


def _runtime_closure(runtime_root: Path) -> tuple[str, Path, dict[str, object]]:
    if runtime_root.resolve() != APPROVED_RUNTIME_ROOT:
        raise SystemExit("unapproved exact runtime root")
    records = {}
    for name, (relative, expected) in sorted(RUNTIME_CLOSURE_FILES.items()):
        path = runtime_root.resolve() / relative
        observed = _sha(path.read_bytes()) if path.is_file() else None
        if observed != expected:
            raise SystemExit(f"exact runtime closure changed: {name}")
        records[name] = {"path": str(path.resolve()), "sha256": expected}
    for name, path, expected in (
        ("formal_python", APPROVED_PYTHON, APPROVED_PYTHON_SHA256),
        ("runtime_python", APPROVED_RUNTIME_PYTHON, APPROVED_PYTHON_SHA256),
        ("julia", APPROVED_JULIA, APPROVED_JULIA_SHA256),
    ):
        if not path.is_file() or _sha(path.read_bytes()) != expected:
            raise SystemExit(f"fixed executable changed: {name}")
        records[name] = {"path": str(path), "sha256": expected}
    if _tree_sha(APPROVED_GEOSOLVER_SOURCE) != APPROVED_GEOSOLVER_TREE_SHA256:
        raise SystemExit("legacy geosolver transitive source tree changed")
    records["geosolver_source_tree"] = {
        "path": str(APPROVED_GEOSOLVER_SOURCE),
        "sha256": APPROVED_GEOSOLVER_TREE_SHA256,
    }
    closure_sha = _sha(canonical_json(records))
    if closure_sha != APPROVED_RUNTIME_CLOSURE_SHA256:
        raise SystemExit("exact runtime transitive closure manifest changed")
    return closure_sha, Path(records["exact_worker"]["path"]), records


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


def _strict_descriptor_ready(value: object, exact: object) -> bool:
    """Recompute the minimal-polynomial, isolator, and ordinal obligations."""

    if not isinstance(value, Mapping) or set(value) != {
        "minimal_polynomial_high_to_low",
        "selected_real_root_index",
        "isolating_interval",
        "proposal_relation_low_to_high",
        "confirmation_relation_low_to_high",
        "target_512",
        "target_768",
        "target_1024",
    }:
        return False
    coefficients = value.get("minimal_polynomial_high_to_low")
    ordinal = value.get("selected_real_root_index")
    isolator = value.get("isolating_interval")
    if (
        not isinstance(coefficients, list)
        or len(coefficients) < 2
        or not all(isinstance(item, int) and not isinstance(item, bool) for item in coefficients)
        or coefficients[0] <= 0
        or math.gcd(*coefficients) != 1
        or not isinstance(ordinal, int)
        or isinstance(ordinal, bool)
        or ordinal < 0
        or not isinstance(isolator, Mapping)
        or set(isolator) != {"left", "right", "multiplicity", "real_root_index"}
        or isolator.get("multiplicity") != 1
        or isinstance(isolator.get("multiplicity"), bool)
        or isolator.get("real_root_index") != ordinal
        or isinstance(isolator.get("real_root_index"), bool)
        or value.get("proposal_relation_low_to_high") != list(reversed(coefficients))
        or value.get("confirmation_relation_low_to_high") != list(reversed(coefficients))
    ):
        return False
    try:
        left = Fraction(isolator["left"])
        right = Fraction(isolator["right"])
        if left > right:
            return False
        for lane in ("target_512", "target_768", "target_1024"):
            text = value[lane]
            if not isinstance(text, str) or not Decimal(text).is_finite():
                return False
        import sympy as sp

        variable = sp.Symbol("x")
        polynomial = sp.Poly(coefficients, variable, domain=sp.ZZ)
        if polynomial.degree() < 1 or polynomial.is_irreducible is not True:
            return False
        if sp.gcd(polynomial, polynomial.diff()).degree() != 0:
            return False
        left_q = sp.Rational(left.numerator, left.denominator)
        right_q = sp.Rational(right.numerator, right.denominator)
        if left == right:
            if polynomial.degree() != 1 or polynomial.eval(left_q) != 0:
                return False
            roots_left = 0
        else:
            if polynomial.eval(left_q) == 0 or polynomial.eval(right_q) == 0:
                return False
            if polynomial.count_roots(left_q, right_q) != 1:
                return False
            roots_left = polynomial.count_roots(-sp.oo, left_q)
        real_root_count = polynomial.count_roots(-sp.oo, sp.oo)
        if int(roots_left) != ordinal or int(real_root_count) <= ordinal:
            return False
    except (InvalidOperation, TypeError, ValueError, ZeroDivisionError, KeyError):
        return False
    exact_target = exact.get("exact_target_descriptor") if isinstance(exact, Mapping) else None
    attestation = exact.get("target_root_attestation") if isinstance(exact, Mapping) else None
    return bool(
        isinstance(exact_target, Mapping)
        and set(exact_target) == {"coefficients_high_to_low", "isolating_interval"}
        and exact_target.get("coefficients_high_to_low") == coefficients
        and all(
            isinstance(item, int) and not isinstance(item, bool)
            for item in exact_target.get("coefficients_high_to_low", ())
        )
        and isinstance(exact_target.get("isolating_interval"), Mapping)
        and set(exact_target.get("isolating_interval", {}))
        == {"left", "right", "multiplicity", "real_root_index"}
        and all(
            isinstance(exact_target["isolating_interval"].get(key), int)
            and not isinstance(exact_target["isolating_interval"].get(key), bool)
            for key in ("multiplicity", "real_root_index")
        )
        and exact_target.get("isolating_interval") == dict(isolator)
        and isinstance(attestation, Mapping)
        and set(attestation)
        == {
            "claimed_real_root_index",
            "attested_real_root_index",
            "real_root_count",
            "multiplicity",
            "interval_unique",
            "index_match",
        }
        and all(
            isinstance(attestation.get(key), int)
            and not isinstance(attestation.get(key), bool)
            for key in (
                "claimed_real_root_index",
                "attested_real_root_index",
                "real_root_count",
                "multiplicity",
            )
        )
        and attestation.get("claimed_real_root_index") == ordinal
        and attestation.get("attested_real_root_index") == ordinal
        and attestation.get("real_root_count") == int(real_root_count)
        and attestation.get("multiplicity") == 1
        and attestation.get("interval_unique") is True
        and attestation.get("index_match") is True
    )


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
        and _strict_descriptor_ready(value.get("descriptor"), exact)
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


def _run_exact(
    python: Path,
    worker: Path,
    source: Path,
    source_sha: str,
    ordinary_proposal_bytes: bytes,
    endpoint,
    timeout: float,
    artifact_root: Path,
    runtime_closure_sha256: str,
    runtime_closure_records: Mapping[str, object],
    lease: FormalRunLease,
):
    endpoint_sha = _endpoint_sha(endpoint)
    source_bytes = source.read_bytes()
    if _sha(source_bytes) != source_sha:
        raise SystemExit("source bytes changed before exact replay")
    artifact_root = artifact_root.resolve()
    with tempfile.TemporaryDirectory(
        prefix=".edm-gram-exact-", dir=artifact_root
    ) as temporary:
        attempt_root = Path(temporary).resolve()
        attempt_root.chmod(0o700)
        source_copy = attempt_root / "SOURCE.json"
        proposal_copy = attempt_root / "ORDINARY-PROPOSAL.json"
        output = attempt_root / "RESULT.json"
        stdout_path = attempt_root / "STDOUT.bin"
        stderr_path = attempt_root / "STDERR.bin"
        manifest_path = attempt_root / "ATTEMPT.json"
        atomic_write_0600(attempt_root, source_copy, source_bytes)
        atomic_write_0600(attempt_root, proposal_copy, ordinary_proposal_bytes)
        shim_root = attempt_root / "fixed-bin"
        shim_root.mkdir(mode=0o700)
        julia_shim = shim_root / "julia"
        julia_shim.symlink_to(APPROVED_JULIA)
        worker_arguments = [
            "--source", str(source_copy),
            "--source-sha256", source_sha,
            "--endpoint", json.dumps(endpoint, separators=(",", ":")),
            "--endpoint-sha256", endpoint_sha,
            "--timeout-seconds", str(timeout), "--output", str(output),
        ]
        manifest = {
            "schema_version": "geotarget.edm-exact-attempt/v1",
            "python_path": str(python.resolve()),
            "worker_path": str(worker.resolve()),
            "runtime_closure_sha256": runtime_closure_sha256,
            "runtime_closure": dict(runtime_closure_records),
            "source": {"path": str(source_copy), "sha256": source_sha},
            "ordinary_proposal": {
                "path": str(proposal_copy),
                "sha256": _sha(ordinary_proposal_bytes),
            },
            "endpoint_float64_sha256": endpoint_sha,
            "worker_arguments_sha256": _sha(
                b"\0".join(item.encode("utf-8") for item in worker_arguments)
            ),
            "fixed_julia_shim": str(julia_shim),
            "limits": {
                "address_space_bytes": EXACT_ADDRESS_SPACE_CAP_BYTES,
                "rss_bytes": EXACT_RSS_CAP_BYTES,
                "data_bytes": EXACT_DATA_CAP_BYTES,
                "file_bytes": EXACT_FILE_CAP_BYTES,
                "log_bytes": EXACT_LOG_CAP_BYTES,
            },
            "truth_used": False,
            "case_family_known_target_count_routing": False,
        }
        manifest_payload = canonical_json(manifest)
        atomic_write_0600(attempt_root, manifest_path, manifest_payload)
        environment, inherited_fds = lease.child_handoff(manifest_payload)
        guard_path = Path(__file__).resolve().parent / "exact_worker_guard.py"
        command = [
            str(python.resolve()),
            str(guard_path),
            "--attempt-manifest", str(manifest_path),
            "--worker", str(worker.resolve()),
            "--python", str(python.resolve()),
            "--",
            *worker_arguments,
        ]
        try:
            completed = run_contained(
                command,
                cwd=attempt_root,
                environment=environment,
                pass_fds=inherited_fds,
                timeout_seconds=timeout + 1.0,
                rss_cap_bytes=EXACT_RSS_CAP_BYTES,
                stdout_path=stdout_path,
                stderr_path=stderr_path,
                output_cap_bytes=EXACT_LOG_CAP_BYTES,
            )
        finally:
            lease.close_child_token_fd(inherited_fds)
        if completed.classification != "COMPLETED" or completed.returncode != 0:
            return False, endpoint_sha
        if not output.is_file() or output.stat().st_size > EXACT_FILE_CAP_BYTES:
            return False, endpoint_sha
        try:
            result = json.loads(output.read_bytes())
        except (OSError, json.JSONDecodeError):
            return False, endpoint_sha
        if source.read_bytes() != source_bytes:
            raise SystemExit("source bytes changed across exact replay")
        if proposal_copy.read_bytes() != ordinary_proposal_bytes:
            raise SystemExit("ordinary proposal bytes changed across exact replay")
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
    supplied_artifact_root = arguments.output.absolute().parent
    if supplied_artifact_root.is_symlink():
        raise SystemExit("artifact root is a symlink")
    supplied_artifact_root.mkdir(parents=True, exist_ok=True, mode=0o700)
    artifact_root = supplied_artifact_root.resolve()
    if (
        arguments.private_signatures.absolute().parent.resolve() != artifact_root
        or arguments.output.name in {"", ".", ".."}
        or arguments.private_signatures.name in {"", ".", ".."}
    ):
        raise SystemExit("aggregate and sidecar must be direct children of one artifact root")
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
        ordinary_proposal_bytes = canonical_json(dict(row))
        prepared.append(
            (row, source, _sha(payload), ordinary_proposal_bytes, dict(document), plan)
        )
    static_pass = counters["static_activated"] >= 6 and len(static_signatures) >= 3

    runtime = None
    exact_worker = None
    runtime_closure_sha256 = None
    runtime_closure_records = None
    formal_lease = None
    if arguments.execute_stored and static_pass:
        runtime_path = arguments.runtime_root.resolve() / "research/experiments/EXP-REAL61-008/source_only/runtime.py"
        authority_runtime = arguments.runtime_root.resolve() / "research/experiments/EXP-REAL61-007/provisional_numerical_architecture/source_only_runtime.py"
        exact_worker = arguments.runtime_root.resolve() / "research/experiments/EXP-V15-243-001/candidates/exact_coordinate_replay/fallback_worker.py"
        runtime = _load("geotarget_edm_source_runtime", runtime_path, RUNTIME_SHA256)
        if _sha(authority_runtime.read_bytes()) != AUTHORITY_RUNTIME_SHA256 or Path(runtime.AUTHORITY_PATH).resolve() != authority_runtime:
            raise SystemExit("source runtime authority closure changed")
        if _sha(exact_worker.read_bytes()) != EXACT_WORKER_SHA256:
            raise SystemExit("exact replay worker changed")
        runtime_closure_sha256, exact_worker, runtime_closure_records = _runtime_closure(
            arguments.runtime_root
        )
        if arguments.execute_exact:
            formal_lease = FormalRunLease(
                "POST_ENDPOINT_EDM_GRAM_EXACT_REOPEN_V1"
            ).acquire()
            atexit.register(formal_lease.release)

    stored_sources = set()
    stored_signatures = set()
    pure_sources = set()
    pure_signatures = set()
    private = []
    if runtime is not None:
        for row, source, source_sha, ordinary_proposal_bytes, document, plan in prepared:
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
                        ordinary_proposal_bytes, exact_endpoint,
                        arguments.exact_timeout_seconds, artifact_root,
                        runtime_closure_sha256, runtime_closure_records, formal_lease,
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
                        {
                            "source_sha256": source_sha,
                            "ordinary_proposal_bytes_sha256": _sha(ordinary_proposal_bytes),
                            "endpoint_float64_sha256": value,
                        }
                        for value in candidate_ready
                    )

    stored_pass = len(stored_sources) >= 4 and len(stored_signatures) >= 2
    pure_pass = len(pure_sources) >= 2 and len(pure_signatures) >= 2
    private.sort(key=lambda item: (item["source_sha256"], item["endpoint_float64_sha256"]))
    private_payload = json.dumps(private, sort_keys=True, separators=(",", ":")).encode("ascii") + b"\n"
    atomic_write_0600(artifact_root, arguments.private_signatures, private_payload)
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
        "runtime_closure_sha256": runtime_closure_sha256,
        "exact_schedule": "ABBA_TWO_CANDIDATE_TWO_BASELINE_EQUAL_TIMEOUT",
        "exact_process_containment": "NEW_SESSION_PGID_RSS_AS_DATA_FSIZE_OUTPUT_CAPS",
        "formal_lease_child_handoff": "PARENT_TOKEN_HMAC_PLUS_INHERITED_LOCK_FD",
        "source_and_ordinary_proposal_all_byte_binding": True,
        "descriptor_minpoly_squarefree_isolator_ordinal_recomputed": True,
        "aggregate_and_sidecar_atomic_mode_0600_root_confined": True,
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
    aggregate_payload = canonical_json(aggregate)
    atomic_write_0600(artifact_root, arguments.output, aggregate_payload)
    if formal_lease is not None:
        formal_lease.release()
        atexit.unregister(formal_lease.release)
    print(json.dumps(aggregate, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
