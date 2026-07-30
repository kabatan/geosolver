"""Disposable Krawczyk -> normalized source certificate -> C3V link seam.

This candidate adds no numerical or exact algorithm.  It hash-loads the frozen
local Krawczyk prototype and frozen C3V localized target linker, binds their
statements through exact QQ parsing, and fails closed outside a tiny polynomial
typed-DAG surface.  It is intentionally not a general verifier integration.
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
import hashlib
import importlib.util
import math
from pathlib import Path
import sys
from typing import Any, Sequence

import sympy as sp


INTERVAL_SHA256 = "b2a17ddc6321c3157f89965a8c76fd18f376c8974c3d4288bf430ff70bc6e2a3"
C3V_SHA256 = "d1b0ddef62ce1cfc52639364184cadcd0a97a1cf82fa61c724e49f0a47a016bd"
SCHEMA = "geotarget.krawczyk-c3v-connector/v1"

_ROOT = Path(__file__).resolve().parents[3]
_INTERVAL_PATH = _ROOT / "research/experiments/EXP-INTERVAL-001/interval_rescue.py"
_C3V_PATH = Path(
    "/home/kabatan/work/solver-experiment-runtime/solver/research/experiments/"
    "EXP-V15-243-001/candidates/c3v_target_link_modernization/localized_link.py"
)


def _load_pinned(name: str, path: Path, expected_sha256: str) -> Any:
    payload = path.read_bytes()
    observed = hashlib.sha256(payload).hexdigest()
    if observed != expected_sha256:
        raise RuntimeError(f"pinned dependency mismatch:{name}:{observed}")
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load pinned dependency:{name}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


interval = _load_pinned("krawczyk_connector_interval", _INTERVAL_PATH, INTERVAL_SHA256)
c3v = _load_pinned("krawczyk_connector_c3v", _C3V_PATH, C3V_SHA256)


@dataclass(frozen=True)
class Predicate:
    expression: Any
    source_expression: str
    relation: str


@dataclass(frozen=True)
class ConnectorProblem:
    variables: tuple[str, ...]
    source_equations: tuple[str, ...]
    target_expression: str
    residual_dag: tuple[Any, ...]
    target_dag: Any
    predicates: tuple[Predicate, ...]
    safe_endpoint: tuple[float, ...]
    trust_radius: tuple[float, ...]
    candidate_coefficients_high_to_low: tuple[int, ...]
    descriptor_selection_interval: tuple[str | int, str | int]
    source_kind: str = "validated-dag"
    branch_state: str = "single"
    opaque_callbacks: bool = False


@dataclass(frozen=True)
class ConnectorResult:
    status: str
    reason: str
    authority: bool
    baseline_work: int
    side_work: int
    baseline_payload: bytes
    source_certificate: dict[str, Any] | None = None
    target_link: dict[str, Any] | None = None


class ConnectorFailure(ValueError):
    pass


def _qq_float(value: float | int) -> sp.Rational:
    if isinstance(value, bool):
        raise ConnectorFailure("boolean-constant")
    numeric = float(value)
    if not math.isfinite(numeric):
        raise ConnectorFailure("nonfinite-constant")
    numerator, denominator = numeric.as_integer_ratio()
    return sp.Rational(numerator, denominator)


def _dag_to_qq(expression: Any, symbols: Sequence[sp.Symbol]) -> sp.Expr:
    if not isinstance(expression, interval.Expr):
        raise ConnectorFailure("malformed-dag-node")
    op = expression.op
    if op == "const":
        return _qq_float(expression.value)
    if op == "var":
        index = expression.value
        if not isinstance(index, int) or isinstance(index, bool) or not 0 <= index < len(symbols):
            raise ConnectorFailure("invalid-variable-index")
        return symbols[index]
    if op == "neg" and len(expression.args) == 1:
        return -_dag_to_qq(expression.args[0], symbols)
    if op in {"add", "sub", "mul"} and len(expression.args) == 2:
        left = _dag_to_qq(expression.args[0], symbols)
        right = _dag_to_qq(expression.args[1], symbols)
        return {"add": left + right, "sub": left - right, "mul": left * right}[op]
    if op == "pow" and len(expression.args) == 1:
        exponent = expression.value
        if not isinstance(exponent, int) or isinstance(exponent, bool) or not 0 <= exponent <= 6:
            raise ConnectorFailure("unsupported-power")
        return _dag_to_qq(expression.args[0], symbols) ** exponent
    # Division/opaque/branch/transcendental nodes are outside this exact seam.
    raise ConnectorFailure(f"unsupported-exact-op:{op}")


def _parse_qq(text: str, symbols: Sequence[sp.Symbol]) -> sp.Expr:
    if not isinstance(text, str) or not text:
        raise ConnectorFailure("empty-source-expression")
    local = {symbol.name: symbol for symbol in symbols}
    try:
        expression = sp.sympify(text, locals=local)
        numerator, denominator = sp.fraction(sp.cancel(expression))
        if denominator != 1:
            raise ConnectorFailure("uncleared-source-denominator")
        return sp.Poly(numerator, *symbols, domain=sp.QQ).as_expr()
    except (TypeError, ValueError, sp.PolynomialError) as error:
        if isinstance(error, ConnectorFailure):
            raise
        raise ConnectorFailure(f"source-not-QQ-polynomial:{type(error).__name__}") from error


def _same_qq(left: sp.Expr, right: sp.Expr, symbols: Sequence[sp.Symbol]) -> bool:
    try:
        return sp.Poly(sp.expand(left - right), *symbols, domain=sp.QQ).is_zero
    except sp.PolynomialError:
        return False


def _rational_endpoint(value: float) -> str:
    numerator, denominator = float(value).as_integer_ratio()
    return str(Fraction(numerator, denominator))


def _interval_json(values: Sequence[Any]) -> list[list[str]]:
    return [[_rational_endpoint(item.lo), _rational_endpoint(item.hi)] for item in values]


def _fail(reason: str, baseline_work: int, side_work: int, baseline_payload: bytes) -> ConnectorResult:
    return ConnectorResult("NOT_CERTIFIED", reason, False, baseline_work, side_work, baseline_payload)


def connect(
    problem: ConnectorProblem,
    *,
    total_work: int = 8,
    baseline_payload: bytes = b"baseline-unchanged",
) -> ConnectorResult:
    """Attempt one private connector proof while preserving >=75% baseline work."""

    if total_work < 4:
        raise ValueError("total_work must be at least four")
    baseline_work = math.ceil(0.75 * total_work)
    side_work = 1
    if not isinstance(baseline_payload, bytes):
        raise TypeError("baseline payload must be bytes")
    if len(problem.variables) not in {1, 2}:
        return _fail("dimension-outside-local-backend", baseline_work, side_work, baseline_payload)
    if len(set(problem.variables)) != len(problem.variables):
        return _fail("duplicate-variable", baseline_work, side_work, baseline_payload)
    if len(problem.residual_dag) != len(problem.variables) or len(problem.source_equations) != len(problem.variables):
        return _fail("nonsquare-system", baseline_work, side_work, baseline_payload)
    if len(problem.safe_endpoint) != len(problem.variables) or len(problem.trust_radius) != len(problem.variables):
        return _fail("point-radius-dimension-mismatch", baseline_work, side_work, baseline_payload)
    if problem.source_kind != "validated-dag" or problem.branch_state != "single" or problem.opaque_callbacks:
        return _fail("typed-branch-free-source-unavailable", baseline_work, side_work, baseline_payload)

    try:
        bounds = []
        for point, radius in zip(problem.safe_endpoint, problem.trust_radius):
            if not (math.isfinite(point) and math.isfinite(radius) and radius > 0.0):
                raise ConnectorFailure("invalid-local-box")
            lower, upper = point - radius, point + radius
            if not (math.isfinite(lower) and math.isfinite(upper) and lower < upper):
                raise ConnectorFailure("invalid-local-box")
            bounds.append((lower, upper))

        raw_problem = interval.Problem(
            residuals=problem.residual_dag,
            bounds=tuple(bounds),
            source_kind="validated-dag",
            branch_state="single",
            strict_guard_state="interior",
            opaque_callbacks=False,
        )
        config = interval.RescueConfig(
            max_dimension=2,
            max_box_width=max(4.0, max(upper - lower for lower, upper in bounds)),
            max_box_volume=16.0,
            max_boxes=1,
            max_depth=0,
            max_seconds=0.05,
            max_proposals=1,
            total_launch_slots=total_work,
            minimum_baseline_fraction=0.75,
        )
        gate = interval.applicability(raw_problem, config)
        if not gate.applicable:
            raise ConnectorFailure(f"local-backend-inapplicable:{gate.reason}")

        symbols = tuple(sp.Symbol(name, real=True) for name in problem.variables)
        typed_residuals = tuple(_dag_to_qq(item, symbols) for item in problem.residual_dag)
        parsed_residuals = tuple(_parse_qq(item, symbols) for item in problem.source_equations)
        if any(not _same_qq(left, right, symbols) for left, right in zip(typed_residuals, parsed_residuals)):
            raise ConnectorFailure("source-equation-dag-binding-mismatch")
        typed_target = _dag_to_qq(problem.target_dag, symbols)
        parsed_target = _parse_qq(problem.target_expression, symbols)
        if not _same_qq(typed_target, parsed_target, symbols):
            raise ConnectorFailure("target-dag-binding-mismatch")

        parsed_predicates = []
        for predicate in problem.predicates:
            if predicate.relation not in {"gt0", "lt0", "neq0"}:
                raise ConnectorFailure("unsupported-predicate-relation")
            typed = _dag_to_qq(predicate.expression, symbols)
            parsed = _parse_qq(predicate.source_expression, symbols)
            if not _same_qq(typed, parsed, symbols):
                raise ConnectorFailure("predicate-dag-binding-mismatch")
            parsed_predicates.append(parsed)

        source_box = tuple(interval.Interval(lower, upper) for lower, upper in bounds)
        enclosure, midpoint_singular = interval._krawczyk(problem.residual_dag, source_box, config)
        if midpoint_singular:
            raise ConnectorFailure("krawczyk-midpoint-singular")
        if enclosure is None:
            raise ConnectorFailure("krawczyk-strict-inclusion-not-proved")
        if not all(item.strictly_inside(source_box[index]) for index, item in enumerate(enclosure)):
            raise ConnectorFailure("krawczyk-enclosure-recheck-failed")

        predicate_proofs = []
        for predicate in problem.predicates:
            values, _ = interval._evaluate((predicate.expression,), enclosure, len(symbols))
            value = values[0]
            proved = (
                (predicate.relation == "gt0" and value.lo > 0.0)
                or (predicate.relation == "lt0" and value.hi < 0.0)
                or (predicate.relation == "neq0" and (value.lo > 0.0 or value.hi < 0.0))
            )
            if not proved:
                raise ConnectorFailure("source-predicate-not-proved-on-root-enclosure")
            predicate_proofs.append(
                {
                    "source_expression": predicate.source_expression,
                    "relation": predicate.relation,
                    "outward_interval": [_rational_endpoint(value.lo), _rational_endpoint(value.hi)],
                }
            )

        target_values, _ = interval._evaluate((problem.target_dag,), enclosure, len(symbols))
        target_interval = target_values[0]
        if not target_interval.lo < target_interval.hi:
            raise ConnectorFailure("degenerate-target-interval")
        exact_target_interval = [_rational_endpoint(target_interval.lo), _rational_endpoint(target_interval.hi)]

        statement = {
            "variables": list(problem.variables),
            "source_equations": list(problem.source_equations),
            "target_expression": problem.target_expression,
        }
        certificate: dict[str, Any] = {
            "schema_version": SCHEMA,
            "status": "VERIFIED",
            "proof_method": "PINNED_OUTWARD_FLOAT_KRAWCZYK_STRICT_INCLUSION_PLUS_TYPED_QQ_BINDING",
            "system_sha256": c3v.canonical_sha256(statement),
            "source_root_exists": True,
            "source_root_unique_in_box": True,
            "all_source_equations_verified": True,
            "all_source_predicates_verified": True,
            "target_interval_exactly_derived_from_source_box": True,
            "certified_target_interval": exact_target_interval,
            "source_box_exact_binary_rationals": _interval_json(source_box),
            "krawczyk_operator_enclosure_exact_binary_rationals": _interval_json(enclosure),
            "strict_krawczyk_inclusion": True,
            "source_predicate_proofs": predicate_proofs,
            "target_interval_provenance": "outward typed-DAG evaluation on Krawczyk root enclosure",
            "source_expression_bindings_exact_over_QQ": True,
            "endpoint_used_as_exact_equality": False,
            "truth_used": False,
            "coverage": "UNKNOWN",
            "pinned_interval_sha256": INTERVAL_SHA256,
            "pinned_c3v_sha256": C3V_SHA256,
        }
        certificate["artifact_sha256"] = c3v.canonical_sha256(certificate)

        link = c3v.prove_with_verified_source_certificate(
            variables=problem.variables,
            source_equations=problem.source_equations,
            target_expression=problem.target_expression,
            coefficients_high_to_low=problem.candidate_coefficients_high_to_low,
            descriptor_selection_interval=problem.descriptor_selection_interval,
            source_certificate=certificate,
        )
        authority = bool(
            link.get("status") == "VERIFIED"
            and link.get("source_certificate_join_verified") is True
            and c3v.verify_artifact(link)
        )
        if not authority:
            return ConnectorResult(
                "NOT_CERTIFIED",
                f"c3v-link:{link.get('reason', 'unknown')}",
                False,
                baseline_work,
                side_work,
                baseline_payload,
                certificate,
                link,
            )
        return ConnectorResult(
            "VERIFIED",
            "local-source-root-and-target-descriptor-exactly-linked",
            True,
            baseline_work,
            side_work,
            baseline_payload,
            certificate,
            link,
        )
    except (ArithmeticError, ConnectorFailure, IndexError, TypeError, ValueError) as error:
        return _fail(str(error), baseline_work, side_work, baseline_payload)


__all__ = [
    "ConnectorProblem",
    "ConnectorResult",
    "Predicate",
    "connect",
    "interval",
]
