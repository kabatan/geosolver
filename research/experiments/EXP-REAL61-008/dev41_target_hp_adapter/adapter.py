"""Minimal Float64-endpoint to numerical-v3 target-authority adapter.

The public entry point accepts exactly the untouched source bytes, their
caller-supplied SHA-256, and one Float64 endpoint.  It delegates refinement,
original-DSL replay, and target-only PSLQ to the already-frozen EXP008 path.
It neither consumes nor emits a case/family routing key and never changes the
source problem, adds bounds, or applies a gauge/symmetry reduction.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import struct
import sys
import time
from types import ModuleType
from typing import Callable, Mapping, Sequence

from mpmath import mp


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
FROZEN_DIRECTORY = (
    ROOT / "research/experiments/EXP-REAL61-006/adaptive_hp_escalation"
)
FROZEN_CANDIDATE = FROZEN_DIRECTORY / "target_stable_candidate.py"
FROZEN_WORKER = FROZEN_DIRECTORY / "target_stable_worker.py"
PREFERRED_CANDIDATE = (
    HERE.parent / "hp_undamped_first_candidate/candidate.py"
)

FROZEN_SHA256 = {
    FROZEN_CANDIDATE: (
        "3f33c5755efbc39c06d70e9118c53a3a69e5cafaeeacb8562a127db733ed0275"
    ),
    FROZEN_WORKER: (
        "9037698a9e3886255c06c4a75e9b7ffb37832badfd0b0e52cf5306f5e9c01a2a"
    ),
    PREFERRED_CANDIDATE: (
        "59a8e65f21c5b5d2860f563644ebf40b58a253fed6a61cd00386cd6661ae0979"
    ),
}
ARM = "UNDAMPED_MINIMUM_NORM_BEFORE_EXISTING_DAMPING_LADDER"
NUMERIC_GATE = mp.mpf("1e-100")
FLOAT64_INTRINSIC_DOMAIN_SLACK = mp.mpf(str(32 * math.ulp(1.0)))
SCHEMA = "geotarget.exp008-dev41-target-hp-adapter/v1"

# These closed unit domains are part of the named construction semantics.  They
# are validation predicates only: this adapter never turns them into a search
# box, clips a proposal, or inserts a constraint into the source document.
_UNIT_PARAMETER_POSITIONS = {
    "PointOnSegment": (2,),
    "PointOnCircle": (1,),
    "PointOnArc": (1,),
}
_UNIT_PARAMETER_VARARGS_AFTER = {"InscribedPolygon": 1}
_UNIT_PARAMETER_KEYWORDS = frozenset({"t", "parameter"})


class AdapterInputError(ValueError):
    """Fail-closed malformed source/digest/endpoint input."""


@dataclass(frozen=True)
class _IntrinsicDomainCheck:
    semantic_id: str
    primitive: str
    expression: ast.AST
    expression_text: str


@dataclass(frozen=True)
class _Runtime:
    candidate: ModuleType | object
    frozen_worker: ModuleType | object
    components: Mapping[str, object]
    counting_evaluator: Callable[[object], object]
    opaque_adapter: Callable[[object, Callable[[], object]], object]
    high_precision_mode: Callable[[], object]


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _module(name: str, path: Path) -> ModuleType:
    expected = path.resolve()
    cached = sys.modules.get(name)
    if cached is not None:
        observed = getattr(cached, "__file__", None)
        if observed is None or Path(observed).resolve() != expected:
            raise RuntimeError(f"module path mismatch for {name}")
        return cached
    specification = importlib.util.spec_from_file_location(name, expected)
    if specification is None or specification.loader is None:
        raise ImportError(f"cannot load frozen component {expected}")
    loaded = importlib.util.module_from_spec(specification)
    sys.modules[name] = loaded
    specification.loader.exec_module(loaded)
    if Path(getattr(loaded, "__file__", "")).resolve() != expected:
        raise RuntimeError(f"loaded component path mismatch for {name}")
    return loaded


def _load_runtime() -> _Runtime:
    for path, expected in FROZEN_SHA256.items():
        observed = _sha256(path.read_bytes())
        if observed != expected:
            raise RuntimeError(f"frozen component digest mismatch: {path}: {observed}")

    # target_stable_worker imports this exact canonical name.  A dedicated
    # fresh endpoint process prevents unrelated experimental adapters from
    # occupying that module name.
    _module("target_stable_candidate", FROZEN_CANDIDATE)
    candidate = _module(
        "geotarget_exp008_dev41_undamped_first_candidate",
        PREFERRED_CANDIDATE,
    )
    frozen_worker = _module(
        "geotarget_exp008_dev41_target_stable_worker", FROZEN_WORKER
    )
    observed_base = Path(getattr(candidate.FROZEN, "__file__", ""))
    if observed_base.resolve() != FROZEN_CANDIDATE.resolve():
        raise RuntimeError("undamped-first frozen-base path mismatch")
    frozen_worker.candidate = candidate

    bridge = frozen_worker._load(
        "geotarget_exp008_dev41_refinement_bridge", frozen_worker.BRIDGE_PATH
    )
    components = bridge._load_components()
    from geosolver._internal.solver.precision.type_guards.high_precision_mode import (
        high_precision_mode,
    )

    return _Runtime(
        candidate=candidate,
        frozen_worker=frozen_worker,
        components=components,
        counting_evaluator=frozen_worker.COMMON.CountingEvaluator,
        opaque_adapter=frozen_worker.COMMON.OpaqueAdapter,
        high_precision_mode=high_precision_mode,
    )


def _strict_source(
    source_payload: bytes, expected_source_sha256: str
) -> tuple[dict[str, object], tuple[str, ...]]:
    if not isinstance(source_payload, bytes) or not source_payload:
        raise AdapterInputError("source payload must be nonempty bytes")
    if (
        not isinstance(expected_source_sha256, str)
        or len(expected_source_sha256) != 64
        or any(character not in "0123456789abcdef" for character in expected_source_sha256)
    ):
        raise AdapterInputError("source SHA-256 must be lowercase hexadecimal")
    if _sha256(source_payload) != expected_source_sha256:
        raise AdapterInputError("source SHA-256 mismatch")
    try:
        source = json.loads(source_payload)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise AdapterInputError("source payload is not JSON") from error
    if not isinstance(source, dict) or source.get("task") != "solve":
        raise AdapterInputError("source must be an untouched solve problem")
    variables = source.get("variables")
    names = variables.get("names") if isinstance(variables, dict) else None
    if not isinstance(names, list) or not all(
        isinstance(name, str) and name for name in names
    ):
        raise AdapterInputError("source variable declaration is malformed")
    return source, tuple(names)


def _strict_endpoint(
    endpoint: Sequence[object], *, dimension: int
) -> tuple[float, ...]:
    if isinstance(endpoint, (str, bytes, bytearray, Mapping)) or not isinstance(
        endpoint, Sequence
    ):
        raise AdapterInputError("endpoint must be a bare numeric sequence")
    if len(endpoint) != dimension:
        raise AdapterInputError("endpoint dimension does not match original source")
    values: list[float] = []
    for value in endpoint:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise AdapterInputError("endpoint must contain only JSON numbers")
        try:
            converted = float(value)
        except (OverflowError, ValueError) as error:
            raise AdapterInputError("endpoint coordinate is not Float64") from error
        if not math.isfinite(converted):
            raise AdapterInputError("endpoint coordinate is non-finite")
        values.append(converted)
    return tuple(values)


def endpoint_float64_sha256(endpoint: Sequence[float]) -> str:
    payload = struct.pack(">I", len(endpoint)) + b"".join(
        struct.pack(">d", value) for value in endpoint
    )
    return _sha256(payload)


def _call_name(node: ast.Call) -> str | None:
    if isinstance(node.func, ast.Name):
        return node.func.id
    if isinstance(node.func, ast.Attribute):
        return node.func.attr
    return None


def _parameter_nodes(node: ast.Call, primitive: str) -> tuple[ast.AST, ...]:
    selected: list[ast.AST] = []
    for position in _UNIT_PARAMETER_POSITIONS.get(primitive, ()):
        if position < len(node.args):
            selected.append(node.args[position])
    start = _UNIT_PARAMETER_VARARGS_AFTER.get(primitive)
    if start is not None:
        selected.extend(node.args[start:])
    selected.extend(
        keyword.value
        for keyword in node.keywords
        if keyword.arg in _UNIT_PARAMETER_KEYWORDS
    )
    return tuple(selected)


def _compile_intrinsic_domains(
    source: Mapping[str, object], variable_names: Sequence[str]
) -> tuple[_IntrinsicDomainCheck, ...]:
    """Compile only construction-implied closed unit parameter domains."""

    constructions = source.get("construction")
    if constructions is None:
        return ()
    if not isinstance(constructions, list):
        raise AdapterInputError("source construction declaration is malformed")
    allowed_names = set(variable_names)
    checks: list[_IntrinsicDomainCheck] = []
    for construction_index, construction in enumerate(constructions):
        expression_text = (
            construction.get("expr") if isinstance(construction, Mapping) else None
        )
        if not isinstance(expression_text, str):
            raise AdapterInputError("source construction expression is malformed")
        try:
            tree = ast.parse(expression_text, mode="eval")
        except SyntaxError as error:
            raise AdapterInputError("source construction expression is invalid") from error
        occurrence: dict[str, int] = {}
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            primitive = _call_name(node)
            if primitive not in (
                _UNIT_PARAMETER_POSITIONS.keys()
                | _UNIT_PARAMETER_VARARGS_AFTER.keys()
            ):
                continue
            primitive_index = occurrence.get(primitive, 0)
            occurrence[primitive] = primitive_index + 1
            for parameter_index, parameter in enumerate(
                _parameter_nodes(node, primitive)
            ):
                referenced_names = {
                    child.id
                    for child in ast.walk(parameter)
                    if isinstance(child, ast.Name)
                }
                if not referenced_names.issubset(allowed_names):
                    raise AdapterInputError(
                        "intrinsic parameter must use source variables only"
                    )
                checks.append(
                    _IntrinsicDomainCheck(
                        semantic_id=(
                            f"construction[{construction_index}].intrinsic."
                            f"{primitive}[{primitive_index}].parameter[{parameter_index}]"
                        ),
                        primitive=primitive,
                        expression=parameter,
                        expression_text=ast.unparse(parameter),
                    )
                )
    return tuple(checks)


def _evaluate_scalar_expression(node: ast.AST, values: Mapping[str, object]):
    if isinstance(node, ast.Name):
        return mp.mpf(values[node.id])
    if (
        isinstance(node, ast.Constant)
        and isinstance(node.value, (int, float))
        and not isinstance(node.value, bool)
    ):
        return mp.mpf(node.value)
    if isinstance(node, ast.UnaryOp):
        operand = _evaluate_scalar_expression(node.operand, values)
        if isinstance(node.op, ast.UAdd):
            return operand
        if isinstance(node.op, ast.USub):
            return -operand
    if isinstance(node, ast.BinOp):
        left = _evaluate_scalar_expression(node.left, values)
        right = _evaluate_scalar_expression(node.right, values)
        if isinstance(node.op, ast.Add):
            return left + right
        if isinstance(node.op, ast.Sub):
            return left - right
        if isinstance(node.op, ast.Mult):
            return left * right
        if isinstance(node.op, ast.Div):
            return left / right
        if isinstance(node.op, ast.Pow):
            return left**right
    raise AdapterInputError("unsupported intrinsic parameter expression")


def _evaluate_intrinsic_domains(
    checks: Sequence[_IntrinsicDomainCheck],
    variable_names: Sequence[str],
    point: Sequence[object],
    *,
    tolerance: object,
) -> dict[str, object]:
    slack = mp.mpf(tolerance)
    if not checks:
        return {
            "ok": True,
            "compiled_check_count": 0,
            "tolerance": mp.nstr(slack, 40, strip_zeros=False),
            "violations": [],
        }
    if len(point) != len(variable_names):
        raise AdapterInputError("intrinsic-domain point dimension mismatch")
    context = dict(zip(variable_names, point, strict=True))
    violations: list[dict[str, object]] = []
    with mp.workdps(380):
        for check in checks:
            try:
                value = _evaluate_scalar_expression(check.expression, context)
            except (ArithmeticError, KeyError, TypeError, ValueError) as error:
                raise AdapterInputError(
                    "intrinsic parameter evaluation failed"
                ) from error
            satisfied = bool(
                mp.isfinite(value)
                and value >= -slack
                and value <= mp.mpf("1") + slack
            )
            if not satisfied:
                violations.append(
                    {
                        "semantic_id": check.semantic_id,
                        "primitive": check.primitive,
                        "parameter_expression": check.expression_text,
                        "closed_lower": "0",
                        "closed_upper": "1",
                        "value": mp.nstr(value, 80, strip_zeros=False),
                    }
                )
    return {
        "ok": not violations,
        "compiled_check_count": len(checks),
        "tolerance": mp.nstr(slack, 40, strip_zeros=False),
        "violations": violations,
    }


def _apply_intrinsic_domains_to_replay(
    replay: Mapping[str, object],
    checks: Sequence[_IntrinsicDomainCheck],
    variable_names: Sequence[str],
) -> dict[str, object]:
    """Attach final-lane DSL-domain validation without rerunning refinement."""

    updated = dict(replay)
    lanes = replay.get("lanes")
    if not isinstance(lanes, list):
        return updated
    updated_lanes: list[dict[str, object]] = []
    all_domains_ok = True
    for row in lanes:
        if not isinstance(row, Mapping) or not isinstance(row.get("point"), list):
            all_domains_ok = False
            updated_lanes.append(dict(row) if isinstance(row, Mapping) else {})
            continue
        evaluation = _evaluate_intrinsic_domains(
            checks,
            variable_names,
            row["point"],
            tolerance=NUMERIC_GATE,
        )
        domain_ok = evaluation["ok"] is True
        all_domains_ok = all_domains_ok and domain_ok
        updated_lanes.append(
            {
                **row,
                "raw_hard_feasible_without_intrinsic_domains": bool(
                    row.get("hard_feasible")
                ),
                "hard_feasible": bool(row.get("hard_feasible") and domain_ok),
                "intrinsic_domain_ok": domain_ok,
                "intrinsic_domain_violations": evaluation["violations"],
            }
        )
    updated["lanes"] = updated_lanes
    updated["intrinsic_domain_check_count"] = len(checks)
    if not all_domains_ok:
        updated["numeric_v3_ready"] = False
        updated["status"] = "INTRINSIC_DOMAIN_REJECTED"
    return updated


def _less_equal(value: object, threshold: object = NUMERIC_GATE) -> bool:
    try:
        with mp.workdps(380):
            return bool(mp.mpf(value) <= mp.mpf(threshold))
    except (TypeError, ValueError):
        return False


def _authority_gate(
    replay: Mapping[str, object], authority: Mapping[str, object]
) -> tuple[bool, list[str]]:
    """The compact EXP008 target-only gate, including the 1024 replay."""

    failures: list[str] = []
    if replay.get("numeric_v3_ready") is not True:
        failures.append("numeric_v3_not_ready")
    for field in (
        "configuration_512_768_disagreement_inf",
        "target_512_768_disagreement",
        "target_768_1024_disagreement",
    ):
        if not _less_equal(replay.get(field)):
            failures.append(field)

    lanes = replay.get("lanes")
    if not isinstance(lanes, list) or [row.get("bits") for row in lanes] != [
        512,
        768,
        1024,
    ]:
        failures.append("precision_lane_set")
    else:
        for row in lanes:
            bits = row.get("bits")
            if row.get("intrinsic_domain_ok") is False:
                failures.append(f"intrinsic_domain_{bits}")
            if not (
                row.get("finite") is True
                and row.get("hard_feasible") is True
                and row.get("guard_ok") is True
                and row.get("answer") is not None
            ):
                failures.append(f"original_dsl_semantics_{bits}")
            if not _less_equal(row.get("residual_inf")):
                failures.append(f"original_dsl_residual_{bits}")

    proposal = authority.get("proposal_relation_low_to_high")
    confirmation = authority.get("confirmation_relation_low_to_high")
    polynomial = authority.get("minimal_polynomial_high_to_low")
    isolator = authority.get("isolating_interval")
    if not (
        authority.get("status") == "TARGET_RELATION_CONFIRMED"
        and authority.get("target_relation_confirmed") is True
        and authority.get("proposal_bits") == 768
        and authority.get("confirmation_bits") == 1024
        and isinstance(proposal, list)
        and proposal
        and proposal == confirmation
        and isinstance(polynomial, list)
        and polynomial
        and authority.get("primitive") is True
        and authority.get("square_free") is True
        and authority.get("irreducible_over_Q") is True
        and isinstance(isolator, Mapping)
        and authority.get("selected_real_root_index")
        == isolator.get("real_root_index")
        and isolator.get("multiplicity") == 1
    ):
        failures.append("target_relation_authority")
    return not failures, failures


def _refinement_summary(refined: Mapping[str, object]) -> dict[str, object]:
    return {
        key: refined.get(key)
        for key in (
            "variant",
            "status",
            "target_stability_ready",
            "numeric_v3_ready",
            "independent_prefix_lane_count",
            "common_anchor_after_independent_prefix",
            "undamped_first_corrective",
            "step_order",
            "stability_counters",
            "semismooth_counters",
            "elapsed_seconds",
        )
        if key in refined
    }


def _build_with_runtime(
    source_payload: bytes,
    expected_source_sha256: str,
    endpoint: Sequence[object],
    *,
    deadline_seconds: float,
    runtime: _Runtime,
) -> dict[str, object]:
    started = time.monotonic()
    source, variable_names = _strict_source(source_payload, expected_source_sha256)
    point = _strict_endpoint(endpoint, dimension=len(variable_names))
    intrinsic_checks = _compile_intrinsic_domains(source, variable_names)
    float_intrinsic = _evaluate_intrinsic_domains(
        intrinsic_checks,
        variable_names,
        point,
        tolerance=FLOAT64_INTRINSIC_DOMAIN_SLACK,
    )
    if not math.isfinite(deadline_seconds) or deadline_seconds <= 0:
        raise AdapterInputError("deadline must be finite and positive")

    bundle = runtime.components["load_problem_bundle"](source, prefer_fast=False)
    raw = runtime.counting_evaluator(
        runtime.components["build_ir_evaluator"](bundle)
    )
    observation = raw.evaluate_float_residual(point)
    hard = raw.evaluate_float_hard_feasibility(point)
    guard_ok, violations = raw.evaluate_guard(point)
    residual = float(observation.residual_norm_float)
    float_valid = bool(
        observation.evaluation_status
        is runtime.components["evaluation_status"].OK
        and hard.hard_feasible
        and guard_ok
        and float_intrinsic["ok"] is True
        and math.isfinite(residual)
    )

    if float_valid and not point:
        # A zero-dimensional solve problem has one static configuration.  No
        # local-refinement method is applicable; replay that same empty vector
        # independently in the frozen three numerical-authority lanes.
        refined = {
            "variant": "DIMENSION_ZERO_DIRECT_ORIGINAL_DSL_REPLAY",
            "status": "DIMENSION_ZERO_DIRECT_ORIGINAL_DSL_REPLAY",
            "target_stability_ready": True,
            "numeric_v3_ready": True,
            "lanes": [
                {"status": "TARGET_STABILITY_REACHED", "point": []}
                for _ in range(3)
            ],
        }
        lane_points = [[], [], []]
        cache = {"hits": 0, "misses": 0}
    elif float_valid:
        opaque = runtime.opaque_adapter(raw, runtime.high_precision_mode)
        refined = runtime.candidate.refine_endpoint(
            opaque,
            point,
            variant=ARM,
            deadline_seconds=float(deadline_seconds),
        )
        lane_points = [
            row["point"]
            for row in refined.get("lanes", [])
            if row.get("point") is not None
            and row.get("status") in {"SUCCESS", "TARGET_STABILITY_REACHED"}
        ]
        cache = {
            "hits": getattr(opaque, "cache_hits", None),
            "misses": getattr(opaque, "cache_misses", None),
        }
    else:
        refined = {
            "variant": ARM,
            "status": "FLOAT64_SEMANTIC_REJECTED",
            "numeric_v3_ready": False,
            "lanes": [],
        }
        lane_points = []
        cache = {"hits": 0, "misses": 0}

    replay = runtime.frozen_worker._original_replay(
        raw, lane_points, runtime.high_precision_mode
    )
    replay = _apply_intrinsic_domains_to_replay(
        replay,
        intrinsic_checks,
        variable_names,
    )
    authority = runtime.frozen_worker._target_authority(source, replay)
    authority_pass, failures = _authority_gate(replay, authority)
    result = {
        "schema_version": SCHEMA,
        "status": (
            "TARGET_AUTHORITY_READY"
            if authority_pass
            else authority.get("status", replay.get("status", "HP_REJECTED"))
        ),
        "source_raw_sha256": expected_source_sha256,
        "endpoint_float64_sha256": endpoint_float64_sha256(point),
        "input_contract": {
            "source_bytes_and_digest": True,
            "bare_float64_endpoint": True,
            "truth": False,
            "known_target_count": False,
            "case_id": False,
            "family": False,
        },
        "problem_transformations": {
            "source_mutated": False,
            "bounds_added": False,
            "coordinate_fixing_or_gauge": False,
            "symmetry_reduction": False,
            "constraint_or_answer_changed": False,
        },
        "float64_replay": {
            "semantic_valid": float_valid,
            "residual_inf": residual if math.isfinite(residual) else None,
            "hard_feasible": bool(hard.hard_feasible),
            "guard_ok": bool(guard_ok),
            "guard_violations": list(violations),
            "intrinsic_domain_ok": float_intrinsic["ok"],
            "intrinsic_domain_violations": float_intrinsic["violations"],
        },
        "refinement": _refinement_summary(refined),
        "semantic_residual_cache": cache,
        "original_numerical_replay": replay,
        "target_authority": authority,
        "authority_pass": authority_pass,
        "failure_reasons": failures,
        "intrinsic_domain_contract": {
            "compiled_check_count": len(intrinsic_checks),
            "source_bytes_modified": False,
            "source_constraints_added": False,
            "search_bounds_added": False,
            "proposals_clipped": False,
            "validation_only": True,
        },
        "authority_scope": {
            "numerical_configuration_512_768": True,
            "target_512_768_1024": True,
            "original_dsl_hp_replay": True,
            "target_only_owned_pslq": True,
            "minimal_polynomial_and_isolator": True,
            "all_coordinate_exactification_required": False,
            "exact_configuration_witness_required": False,
            "target_image_completeness_required": False,
        },
        "callback_counts": dict(getattr(raw, "counts", {})),
        "elapsed_seconds": time.monotonic() - started,
    }
    return runtime.frozen_worker._jsonable(result)


def build_target_authority(
    source_payload: bytes,
    expected_source_sha256: str,
    endpoint: Sequence[object],
    *,
    deadline_seconds: float = 23.0,
) -> dict[str, object]:
    """Refine and validate one endpoint without any identity/truth input."""

    return _build_with_runtime(
        source_payload,
        expected_source_sha256,
        endpoint,
        deadline_seconds=deadline_seconds,
        runtime=_load_runtime(),
    )


__all__ = [
    "AdapterInputError",
    "ARM",
    "SCHEMA",
    "build_target_authority",
    "endpoint_float64_sha256",
]
