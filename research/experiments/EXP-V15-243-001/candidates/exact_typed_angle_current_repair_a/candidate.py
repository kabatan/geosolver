"""Truth-blind exact-coordinate authority prototype for v15 endpoints.

Numeric lanes only propose one irreducible polynomial and one isolated real
root for every source coordinate and for the raw source answer.  Acceptance
is delegated to the established FLINT QQBar straight-line interpreter, which
replays the untouched v15 construction, every constraint, every guard, every
source bound, and the answer equality exactly.  A proposal which cannot be
proved by that replay fails closed.
"""

from __future__ import annotations

import ast
import copy
import importlib.util
import json
import math
import os
import subprocess
import sys
import tempfile
import time
from fractions import Fraction
from functools import reduce
from math import gcd
from pathlib import Path
from typing import Any, Mapping, Sequence

import sympy as sp
from mpmath import mp


HERE = Path(__file__).resolve().parent
WORKSPACE = Path(
    os.environ.get(
        "GEOTARGET_CURRENT_RUNTIME_ROOT",
        "/home/kabatan/work/solver-experiment-runtime/solver",
    )
).resolve()
DAG_COMPILE_PATH = HERE / "dag_compile.py"
QQBAR_WORKER = HERE / "qqbar_worker.jl"
JULIA_PROJECT = WORKSPACE / "research/experiments/EXP-REAL61-002/target_elimination"


class ExactCoordinateFailure(RuntimeError):
    """A numeric proposal could not be converted into exact source evidence."""


def _load_dag_compile():
    name = "v15_243_exact_coordinate_dag_compile"
    cached = sys.modules.get(name)
    if cached is not None:
        return cached
    spec = importlib.util.spec_from_file_location(name, DAG_COMPILE_PATH)
    if spec is None or spec.loader is None:
        raise ExactCoordinateFailure("established QQBar DAG compiler is unavailable")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


DAG = _load_dag_compile()


EXTENDED_DSL_CALLS = {
    "Circle",
    "CircleThroughPoint",
    "CircleThroughThreePoints",
    "Centroid",
    "CoordinateA",
    "CoordinateB",
    "CoordinateC",
    "CoordinateX",
    "CoordinateY",
    "Dot",
    "Excircle",
    "IncircleContactPoint",
    "IsTangent",
    "NoSelfIntersection",
    "Parallel",
    "ParallelismMeasure",
    "PerpendicularBisector",
    "PointOnCircle",
    "PointOnLine",
    "RadicalAxis",
    "StrictConvex",
    "Vector",
    "AssumeRight",
    "AssumeObtuse",
    "cos",
    "max",
    "min",
    "sin",
    "tan",
}


# Only these source keyword forms have a matching exact implementation.
# Every other keyword must fail closed instead of being silently discarded by
# a Julia dispatch branch that happens not to inspect it.
_ALLOWED_EXACT_KEYWORDS: dict[str, frozenset[str]] = {
    "Arc": frozenset({"including", "excluding"}),
    "Collinear": frozenset({"ordered"}),
    "Excenter": frozenset({"vertex"}),
    "Excircle": frozenset({"vertex"}),
    "IncircleContactPoint": frozenset({"side"}),
    "Intersect": frozenset({"exclude", "near", "far"}),
    "OnLine": frozenset({"ordered"}),
    "ParallelismMeasure": frozenset({"method"}),
}


class _SemanticLowerer(ast.NodeTransformer):
    """Lower bounded source spellings without inspecting endpoint values.

    The legacy functions ``Bound`` and ``Assume*`` signal rejection through
    evaluator side effects.  In a replay DAG, their exact mathematical
    predicates are represented explicitly.  Container/attribute lowering is
    restricted to the source forms whose semantics are mechanically known.
    """

    _COMPARE = {
        "AssumeEq": ast.Eq,
        "AssumeNe": ast.NotEq,
        "AssumeLt": ast.Lt,
        "AssumeLe": ast.LtE,
        "AssumeGt": ast.Gt,
        "AssumeGe": ast.GtE,
    }
    # `_collect_guard_violations` evaluates source guards at no less than
    # 80 decimal digits and uses 10^(-dps/2).  Thus 1e-40 is the largest
    # default tolerance any accepted endpoint sees.  Exact replay uses this
    # fixed rational as a conservative algebraic margin for strict guards.
    _DEFAULT_GUARD_MARGIN_EXPONENT = 40

    def __init__(self, *, guard_context: bool) -> None:
        self.guard_context = guard_context
        self.records: list[str] = []

    @staticmethod
    def _direct_name(node: ast.Call) -> str | None:
        return node.func.id if isinstance(node.func, ast.Name) else None

    @staticmethod
    def _reject_options(node: ast.Call, name: str) -> None:
        if len(node.args) != 2 or node.keywords:
            raise ExactCoordinateFailure(
                f"exact semantic lowering does not cover {name} options"
            )

    @classmethod
    def _guard_margin(cls) -> ast.AST:
        return ast.BinOp(
            left=ast.Constant(value=1),
            op=ast.Div(),
            right=ast.BinOp(
                left=ast.Constant(value=10),
                op=ast.Pow(),
                right=ast.Constant(
                    value=cls._DEFAULT_GUARD_MARGIN_EXPONENT
                ),
            ),
        )

    def _guard_comparison(
        self,
        left_raw: ast.AST,
        operator: ast.cmpop,
        right_raw: ast.AST,
    ) -> ast.AST:
        left = self.visit(left_raw)
        right = self.visit(right_raw)
        margin = self._guard_margin()
        if isinstance(operator, ast.Gt):
            return ast.Compare(
                left=left,
                ops=[ast.Gt()],
                comparators=[
                    ast.BinOp(left=right, op=ast.Add(), right=margin)
                ],
            )
        if isinstance(operator, ast.Lt):
            return ast.Compare(
                left=left,
                ops=[ast.Lt()],
                comparators=[
                    ast.BinOp(left=right, op=ast.Sub(), right=margin)
                ],
            )
        if isinstance(operator, ast.NotEq):
            return ast.Compare(
                left=ast.Call(
                    func=ast.Name(id="abs", ctx=ast.Load()),
                    args=[ast.BinOp(left=left, op=ast.Sub(), right=right)],
                    keywords=[],
                ),
                ops=[ast.Gt()],
                comparators=[margin],
            )
        if isinstance(operator, (ast.Eq, ast.GtE, ast.LtE)):
            # Exact equality and exact closed inequalities are conservative
            # subsets of the tolerance-relaxed source guards.
            return ast.Compare(left=left, ops=[operator], comparators=[right])
        raise ExactCoordinateFailure(
            "exact guard comparison uses an unsupported operator"
        )

    def visit_Compare(self, node: ast.Compare) -> ast.AST:
        if not self.guard_context:
            return self.generic_visit(node)
        if len(node.ops) != 1 or len(node.comparators) != 1:
            raise ExactCoordinateFailure(
                "exact guard replay rejects chained comparisons"
            )
        self.records.append("DEFAULT_GUARD_MARGIN_1E_40")
        return ast.copy_location(
            self._guard_comparison(
                node.left,
                node.ops[0],
                node.comparators[0],
            ),
            node,
        )

    def visit_UnaryOp(self, node: ast.UnaryOp) -> ast.AST:
        if self.guard_context and isinstance(node.op, ast.Not):
            # A conservative predicate becomes an unsafe superset when
            # negated.  Fail closed rather than attempting to complement a
            # tolerance-dependent source guard.
            raise ExactCoordinateFailure(
                "exact guard replay rejects logical not"
            )
        return self.generic_visit(node)

    def visit_Attribute(self, node: ast.Attribute) -> ast.AST:
        value = self.visit(node.value)
        coordinate_calls = {
            "x": "CoordinateX",
            "y": "CoordinateY",
            "a": "CoordinateA",
            "b": "CoordinateB",
            "c": "CoordinateC",
        }
        if node.attr not in coordinate_calls:
            raise ExactCoordinateFailure(
                f"exact replay does not cover source attribute .{node.attr}"
            )
        self.records.append(f"ATTRIBUTE_{node.attr.upper()}")
        return ast.copy_location(
            ast.Call(
                func=ast.Name(
                    id=coordinate_calls[node.attr],
                    ctx=ast.Load(),
                ),
                args=[value],
                keywords=[],
            ),
            node,
        )

    def visit_Call(self, node: ast.Call) -> ast.AST:
        name = self._direct_name(node)
        if name == "Arc":
            # Arc side selection and midpoint construction are tolerance-
            # sensitive branch operations in v15.  Until an exact angular
            # separation certificate is available, the optional fallback
            # must not claim authority for any source containing an Arc.
            raise ExactCoordinateFailure(
                "Arc is outside exact branch authority"
            )
        if name == "Bound":
            if not self.guard_context:
                raise ExactCoordinateFailure(
                    "Bound can only be lowered in a source guard"
                )
            if len(node.args) != 2:
                raise ExactCoordinateFailure("Bound needs value and interval")
            options = {item.arg: item.value for item in node.keywords if item.arg}
            if len(options) != len(node.keywords) or set(options) - {"inclusive"}:
                raise ExactCoordinateFailure(
                    "exact Bound lowering rejects message/tolerance options"
                )
            inclusive_node = options.get("inclusive", ast.Constant(value=True))
            if not isinstance(inclusive_node, ast.Constant) or not isinstance(
                inclusive_node.value, bool
            ):
                raise ExactCoordinateFailure("Bound inclusive must be a literal Bool")
            interval = node.args[1]
            if (
                not isinstance(interval, (ast.Tuple, ast.List))
                or len(interval.elts) != 2
            ):
                raise ExactCoordinateFailure("Bound interval must be a literal pair")
            value = self.visit(node.args[0])
            lower_raw, upper_raw = interval.elts
            lower_is_none = (
                isinstance(lower_raw, ast.Constant) and lower_raw.value is None
            )
            upper_is_none = (
                isinstance(upper_raw, ast.Constant) and upper_raw.value is None
            )
            if lower_is_none or upper_is_none:
                # The frozen v15 GuardIR evaluator currently rejects
                # one-sided bounds while the public helper accepts them.
                # Exact fallback follows the active evaluator authority and
                # fails closed until those contracts are unified.
                raise ExactCoordinateFailure(
                    "one-sided Bound is outside frozen evaluator authority"
                )
            else:
                clauses: list[ast.AST] = []
                lower = self.visit(lower_raw)
                upper = self.visit(upper_raw)
                if lower is not None and upper is not None:
                    clauses.append(
                        ast.Compare(
                            left=copy.deepcopy(lower),
                            ops=[ast.Lt()],
                            comparators=[copy.deepcopy(upper)],
                        )
                    )
                if lower is not None:
                    if inclusive_node.value:
                        clauses.append(
                            ast.Compare(
                                left=copy.deepcopy(lower),
                                ops=[ast.LtE()],
                                comparators=[copy.deepcopy(value)],
                            )
                        )
                    else:
                        clauses.append(
                            ast.Compare(
                                left=ast.BinOp(
                                    left=copy.deepcopy(lower),
                                    op=ast.Add(),
                                    right=self._guard_margin(),
                                ),
                                ops=[ast.Lt()],
                                comparators=[copy.deepcopy(value)],
                            )
                        )
                if upper is not None:
                    if inclusive_node.value:
                        clauses.append(
                            ast.Compare(
                                left=copy.deepcopy(value),
                                ops=[ast.LtE()],
                                comparators=[copy.deepcopy(upper)],
                            )
                        )
                    else:
                        clauses.append(
                            ast.Compare(
                                left=copy.deepcopy(value),
                                ops=[ast.Lt()],
                                comparators=[
                                    ast.BinOp(
                                        left=copy.deepcopy(upper),
                                        op=ast.Sub(),
                                        right=self._guard_margin(),
                                    )
                                ],
                            )
                        )
                result = (
                    clauses[0]
                    if len(clauses) == 1
                    else ast.BoolOp(op=ast.And(), values=clauses)
                )
            self.records.append(
                "BOUND_CLOSED" if inclusive_node.value else "BOUND_OPEN"
            )
            return ast.copy_location(result, node)

        if name in self._COMPARE:
            if not self.guard_context:
                raise ExactCoordinateFailure(f"{name} can only be lowered in a guard")
            self._reject_options(node, name)
            self.records.append(name.upper())
            return ast.copy_location(
                self._guard_comparison(
                    node.args[0],
                    self._COMPARE[name](),
                    node.args[1],
                ),
                node,
            )

        if name in {"AssumeConvex", "AssumeNoSelfIntersecting"}:
            if not self.guard_context:
                raise ExactCoordinateFailure(f"{name} can only be lowered in a guard")
            if len(node.args) != 1 or node.keywords:
                raise ExactCoordinateFailure(
                    f"exact semantic lowering does not cover {name} options"
                )
            points = node.args[0]
            if not isinstance(points, (ast.List, ast.Tuple)) or len(points.elts) < 3:
                raise ExactCoordinateFailure(f"{name} needs a literal point sequence")
            lowered_name = (
                "StrictConvex" if name == "AssumeConvex" else "NoSelfIntersection"
            )
            self.records.append(name.upper())
            return ast.copy_location(
                ast.Call(
                    func=ast.Name(id=lowered_name, ctx=ast.Load()),
                    args=[self.visit(item) for item in points.elts],
                    keywords=[],
                ),
                node,
            )

        if name is not None and node.keywords:
            keyword_names = [item.arg for item in node.keywords]
            if any(item is None for item in keyword_names):
                raise ExactCoordinateFailure(
                    f"exact replay rejects expanded keyword options for {name}"
                )
            names = [str(item) for item in keyword_names]
            if len(set(names)) != len(names):
                raise ExactCoordinateFailure(
                    f"exact replay rejects duplicate keyword options for {name}"
                )
            unsupported = set(names) - _ALLOWED_EXACT_KEYWORDS.get(
                name, frozenset()
            )
            if unsupported:
                raise ExactCoordinateFailure(
                    "exact replay does not cover source keyword options for "
                    f"{name}: {sorted(unsupported)}"
                )

        # Unknown lists/tuples are intentionally left for DagBuilder to reject.
        return self.generic_visit(node)


def _lower_expression(source: str, *, guard_context: bool) -> tuple[str, list[str]]:
    try:
        tree = ast.parse(source, mode="eval")
    except SyntaxError as error:
        raise ExactCoordinateFailure(f"invalid source expression: {source}") from error
    lowerer = _SemanticLowerer(guard_context=guard_context)
    lowered = lowerer.visit(tree)
    ast.fix_missing_locations(lowered)
    return ast.unparse(lowered.body), lowerer.records


def prepare_document(document: Mapping[str, Any]) -> tuple[dict[str, Any], list[str]]:
    """Create a semantics-preserving exact-replay view of one v15 document."""

    post_process = document.get("post_process")
    if post_process not in (None, ""):
        raise ExactCoordinateFailure(
            "nonempty source post_process is outside raw-answer authority"
        )
    prepared = copy.deepcopy(dict(document))
    records: list[str] = []
    construction = prepared.get("construction", [])
    constraints = prepared.get("constraints", [])
    guards = prepared.get("guards", []) or []
    if not isinstance(construction, list) or not isinstance(constraints, list):
        raise ExactCoordinateFailure("source construction/constraints are malformed")
    if not isinstance(guards, list):
        raise ExactCoordinateFailure("source guards are malformed")
    for item in construction:
        item["expr"], found = _lower_expression(item["expr"], guard_context=False)
        records.extend(found)
    for item in constraints:
        item["def"], found = _lower_expression(item["def"], guard_context=False)
        records.extend(found)
        if isinstance(item.get("value"), str):
            item["value"], found = _lower_expression(item["value"], guard_context=False)
            records.extend(found)
    lowered_guards = []
    for expression in guards:
        lowered, found = _lower_expression(expression, guard_context=True)
        lowered_guards.append(lowered)
        records.extend(found)
    prepared["guards"] = lowered_guards
    answer = prepared.get("answer")
    if isinstance(answer, str):
        prepared["answer"], found = _lower_expression(answer, guard_context=False)
        records.extend(found)
    return prepared, records


def _validate_replay_terminal(
    replay: Mapping[str, Any],
    *,
    document: Mapping[str, Any],
    coordinate_root_indices: Sequence[int],
    target_root_index: int,
) -> None:
    """Require every exact-replay authority bit, not merely a ready status."""

    constraints = document.get("constraints", [])
    guards = document.get("guards", []) or []
    bounds = document.get("bounds")
    coordinate_count = len(coordinate_root_indices)
    typed_angle_relation_count = sum(
        DAG.direct_typed_angle_arity(
            item["def"], DAG._expression(item.get("value"))
        )
        is not None
        for item in constraints
    )
    if any(
        not isinstance(root_index, int)
        or isinstance(root_index, bool)
        or root_index < 0
        for root_index in coordinate_root_indices
    ) or (
        not isinstance(target_root_index, int)
        or isinstance(target_root_index, bool)
        or target_root_index < 0
    ):
        raise ExactCoordinateFailure(
            "expected real-root ordinal metadata is malformed"
        )
    expected_bounds = 0 if bounds is None else coordinate_count
    expected = {
        "source_relation_count": len(constraints),
        "source_guard_count": len(guards),
        "source_bound_count": expected_bounds,
        "coordinate_count": coordinate_count,
        "typed_angle_relation_count": typed_angle_relation_count,
    }
    observed = {name: replay.get(name) for name in expected}
    coordinate_attestations = replay.get("coordinate_root_attestations")
    target_attestation = replay.get("target_root_attestation")

    def attestation_matches(value: object, root_index: int) -> bool:
        return bool(
            isinstance(value, Mapping)
            and isinstance(value.get("claimed_real_root_index"), int)
            and not isinstance(value.get("claimed_real_root_index"), bool)
            and value.get("claimed_real_root_index") == int(root_index)
            and isinstance(value.get("attested_real_root_index"), int)
            and not isinstance(value.get("attested_real_root_index"), bool)
            and value.get("attested_real_root_index") == int(root_index)
            and isinstance(value.get("real_root_count"), int)
            and not isinstance(value.get("real_root_count"), bool)
            and value.get("real_root_count") > int(root_index)
            and isinstance(value.get("multiplicity"), int)
            and not isinstance(value.get("multiplicity"), bool)
            and value.get("multiplicity") == 1
            and value.get("interval_unique") is True
            and value.get("index_match") is True
        )

    if (
        replay.get("schema_version")
        != "geotarget.qqbar-straight-line-replay/v1"
        or replay.get("status") != "EXACT_REPLAY_ACCEPTED"
        or replay.get("backend") != "FLINT_QQBAR_VIA_NEMO"
        or replay.get("backend_activated") is not True
        or replay.get("truth_used") is not False
        or replay.get("post_process_used") is not False
        or replay.get("completeness_claim_permitted") is not False
        or replay.get("target_image_completeness") != "NOT_RUN"
        or replay.get("source_raw_answer_exact") is not True
        or replay.get("target_link_exact") is not True
        or replay.get("root_ordinal_attestation_complete") is not True
        or replay.get("root_ordinal_attestation_backend")
        != "NEMO_QQBAR_SORTED_REAL_ROOTS"
        or replay.get("root_ordinal_policy")
        != "ZERO_BASED_STRICTLY_INCREASING_REAL_QQBAR_V1"
        or not isinstance(coordinate_attestations, list)
        or len(coordinate_attestations) != coordinate_count
        or any(
            not attestation_matches(attestation, root_index)
            for attestation, root_index in zip(
                coordinate_attestations,
                coordinate_root_indices,
                strict=True,
            )
        )
        or not attestation_matches(target_attestation, target_root_index)
        or observed != expected
        or replay.get("typed_direct_angle_equality_exact")
        is not (typed_angle_relation_count > 0)
    ):
        raise ExactCoordinateFailure(
            "exact replay terminal contract is incomplete or inconsistent: "
            + json.dumps(observed, sort_keys=True)
        )
    coordinate_degrees = replay.get("coordinate_degrees")
    if not isinstance(coordinate_degrees, list) or len(
        coordinate_degrees
    ) != coordinate_count:
        raise ExactCoordinateFailure(
            "exact replay coordinate-degree ledger is inconsistent"
        )


def _normalize_low_to_high(relation: Sequence[Any]) -> list[int]:
    values = [int(item) for item in relation]
    while len(values) > 1 and values[-1] == 0:
        values.pop()
    if len(values) < 2 or not any(values):
        raise ExactCoordinateFailure("PSLQ returned no nonconstant relation")
    common = reduce(gcd, (abs(item) for item in values if item), 0)
    if common > 1:
        values = [item // common for item in values]
    if values[-1] < 0:
        values = [-item for item in values]
    return values


def _primitive_positive(polynomial: sp.Poly) -> sp.Poly:
    _content, primitive = polynomial.primitive()
    if primitive.LC() < 0:
        primitive = -primitive
    return sp.Poly(primitive, polynomial.gens[0], domain=sp.ZZ)


def _mp_poly_value(poly: sp.Poly, value: Any) -> Any:
    total = mp.mpf("0")
    for coefficient in poly.all_coeffs():
        total = total * value + int(coefficient)
    return total


def _interval_descriptor(poly: sp.Poly, approximation: Any) -> dict[str, Any]:
    tolerance = mp.mpf("1e-120")
    matches: list[tuple[sp.Rational, sp.Rational, int]] = []
    intervals = poly.intervals(eps=sp.Rational(1, 10**100))
    for root_index, (interval, multiplicity) in enumerate(intervals):
        left, right = (sp.Rational(item) for item in interval)
        left_mp = mp.mpf(int(left.p)) / int(left.q)
        right_mp = mp.mpf(int(right.p)) / int(right.q)
        if left_mp - tolerance <= approximation <= right_mp + tolerance:
            matches.append((left, right, root_index))
    if len(matches) != 1:
        raise ExactCoordinateFailure(
            f"numeric proposal selects {len(matches)} isolated real roots"
        )
    left, right, root_index = matches[0]
    return {
        "left": str(left),
        "right": str(right),
        "multiplicity": 1,
        "real_root_index": root_index,
    }


def recognize_algebraic(
    proposal_text: str,
    confirmation_text: str,
    *,
    max_degree: int = 8,
    max_coeff: int = 10**12,
) -> dict[str, Any]:
    """Propose and independently confirm one real-algebraic descriptor.

    This is deliberately not an authority boundary.  A false PSLQ relation is
    harmless because :func:`certify_exact_coordinate_witness` only returns an
    accepted record after exact QQBar source replay.
    """

    with mp.workdps(260):
        proposal = mp.mpf(str(proposal_text))
        confirmation = mp.mpf(str(confirmation_text))
        if not mp.isfinite(proposal) or not mp.isfinite(confirmation):
            raise ExactCoordinateFailure("non-finite numeric lane")
        if abs(proposal - confirmation) > mp.mpf("1e-100"):
            raise ExactCoordinateFailure("independent coordinate lanes disagree")

        # Flat equations commonly refine an exact zero as 1e-300 in one lane
        # and 1e-420 in another.  This is only a proposal shortcut: QQBar still
        # has to prove that substituting exact zero satisfies the full source.
        if abs(proposal) <= mp.mpf("1e-120") and abs(confirmation) <= mp.mpf("1e-120"):
            return {
                "status": "ALGEBRAIC_PROPOSAL",
                "coefficients_high_to_low": [1, 0],
                "polynomial_metadata": {
                    "square_free": True,
                    "irreducible_over_Q": True,
                    "isolating_interval": {
                        "left": "0",
                        "right": "0",
                        "multiplicity": 1,
                        "real_root_index": 0,
                    },
                },
                "independent_confirmation_residual": mp.nstr(abs(confirmation), 160),
                "numeric_lanes_used_only_for_proposal": True,
                "proposal_shortcut": "BOTH_LANES_BELOW_1E_120_PROPOSE_ZERO",
            }

        rejected_relation_count = 0
        for degree in range(1, int(max_degree) + 1):
            try:
                candidate = mp.pslq(
                    [proposal**power for power in range(degree + 1)],
                    tol=mp.mpf("1e-100"),
                    maxcoeff=int(max_coeff),
                    maxsteps=50_000,
                )
            except (ValueError, ZeroDivisionError):
                candidate = None
            if candidate is None:
                continue

            # A finite proposal lane can produce a low-degree accidental PSLQ
            # relation before the true relation is reached.  The independent
            # lane is the proposal filter, so a rejected relation must not
            # terminate the bounded degree search.  Exact QQBar source replay
            # remains the only acceptance authority after this loop.
            relation = _normalize_low_to_high(candidate)
            symbol = sp.Symbol("x")
            relation_poly = sp.Poly.from_list(
                list(reversed(relation)), gens=symbol, domain=sp.ZZ
            )
            factor_candidates: list[sp.Poly] = []
            for factor, _multiplicity in sp.factor_list(relation_poly)[1]:
                factor = _primitive_positive(
                    sp.Poly(factor, symbol, domain=sp.ZZ)
                )
                residual = abs(_mp_poly_value(factor, confirmation))
                if residual <= mp.mpf("1e-120"):
                    factor_candidates.append(factor)
            if len(factor_candidates) != 1:
                rejected_relation_count += 1
                continue
            polynomial = factor_candidates[0]
            if (
                polynomial.is_irreducible is not True
                or polynomial.is_sqf is not True
            ):
                rejected_relation_count += 1
                continue
            interval = _interval_descriptor(polynomial, confirmation)
            coefficients = [int(item) for item in polynomial.all_coeffs()]
            return {
                "status": "ALGEBRAIC_PROPOSAL",
                "coefficients_high_to_low": coefficients,
                "polynomial_metadata": {
                    "square_free": True,
                    "irreducible_over_Q": True,
                    "isolating_interval": interval,
                },
                "independent_confirmation_residual": mp.nstr(
                    abs(_mp_poly_value(polynomial, confirmation)), 160
                ),
                "numeric_lanes_used_only_for_proposal": True,
                "rejected_lower_degree_relation_count": (
                    rejected_relation_count
                ),
            }
        raise ExactCoordinateFailure(
            "no independently confirmed bounded PSLQ relation "
            f"after {rejected_relation_count} rejected candidates"
        )


def _qqbar_descriptor(item: Mapping[str, Any]) -> dict[str, Any]:
    metadata = item.get("polynomial_metadata")
    if not isinstance(metadata, Mapping):
        raise ExactCoordinateFailure("algebraic descriptor metadata is absent")
    interval = metadata.get("isolating_interval")
    if not isinstance(interval, Mapping):
        raise ExactCoordinateFailure("algebraic isolating interval is absent")
    coefficients = item.get("coefficients_high_to_low")
    if (
        item.get("status") != "ALGEBRAIC_PROPOSAL"
        or item.get("numeric_lanes_used_only_for_proposal") is not True
        or metadata.get("square_free") is not True
        or metadata.get("irreducible_over_Q") is not True
        or not isinstance(coefficients, list)
        or len(coefficients) < 2
        or not all(
            isinstance(value, int) and not isinstance(value, bool)
            for value in coefficients
        )
    ):
        raise ExactCoordinateFailure("algebraic polynomial is absent")
    left = interval.get("left")
    right = interval.get("right")
    multiplicity = interval.get("multiplicity")
    root_index = interval.get("real_root_index")
    if (
        not isinstance(left, str)
        or not isinstance(right, str)
        or not isinstance(multiplicity, int)
        or isinstance(multiplicity, bool)
        or multiplicity != 1
        or not isinstance(root_index, int)
        or isinstance(root_index, bool)
        or root_index < 0
    ):
        raise ExactCoordinateFailure("algebraic isolating interval is malformed")
    try:
        if Fraction(left) > Fraction(right):
            raise ExactCoordinateFailure(
                "algebraic isolating interval is reversed"
            )
    except (ValueError, ZeroDivisionError) as error:
        raise ExactCoordinateFailure(
            "algebraic isolating interval is not rational"
        ) from error
    return {
        "coefficients_high_to_low": list(coefficients),
        "isolating_interval": {
            "left": left,
            "right": right,
            "multiplicity": multiplicity,
            "real_root_index": root_index,
        },
    }


def _job_descriptor(item: Mapping[str, Any]) -> dict[str, Any]:
    """Serialize arbitrary-height coefficients losslessly through JSON3.

    JSON3 otherwise materializes integers beyond Int64 as Float64, turning a
    coefficient such as 10^40 into the non-integral token ``1.0e40`` before
    the Nemo worker sees it.  Decimal strings are parsed directly as BigInt by
    the established worker and preserve the exact polynomial.
    """

    descriptor = _qqbar_descriptor(item)
    descriptor["coefficients_high_to_low"] = [
        str(value) for value in descriptor["coefficients_high_to_low"]
    ]
    return descriptor


_EXTENDED_JULIA_HELPERS = r"""

# Candidate-local wave-2 primitives.  Every routine is algebraic over QQBar;
# an operation outside that authority subset throws ReplayFailure.
const QX_DEFAULT_GUARD_MARGIN = QB(1) / QB(10)^40
const QX_LINE_HARD_MARGIN = QB(1) / QB(10)^12
const QX_TRIANGLE_HARD_MARGIN = QB(1) / QB(10)^14
const QX_INTERSECTION_HARD_MARGIN = QB(1) / QB(10)^12

function qx_descriptor_interval(descriptor)
  interval = haskey(descriptor, "isolating_interval") ? descriptor["isolating_interval"] : nothing
  if interval === nothing && haskey(descriptor, "polynomial_metadata")
    metadata = descriptor["polynomial_metadata"]
    interval = haskey(metadata, "isolating_interval") ? metadata["isolating_interval"] : nothing
  end
  interval === nothing && throw(ReplayFailure("descriptor isolating interval is missing"))
  return interval
end

function qx_claimed_root_ordinal(descriptor)::Int
  interval = qx_descriptor_interval(descriptor)
  haskey(interval, "real_root_index") || throw(ReplayFailure("descriptor real-root ordinal is missing"))
  raw = interval["real_root_index"]
  raw isa Integer && !(raw isa Bool) ||
    throw(ReplayFailure("descriptor real-root ordinal is not an integer"))
  claimed = Int(raw)
  claimed >= 0 || throw(ReplayFailure("descriptor real-root ordinal is negative"))
  haskey(interval, "multiplicity") ||
    throw(ReplayFailure("descriptor root multiplicity is missing"))
  raw_multiplicity = interval["multiplicity"]
  raw_multiplicity isa Integer && !(raw_multiplicity isa Bool) &&
    Int(raw_multiplicity) == 1 ||
    throw(ReplayFailure("descriptor root multiplicity must be one"))
  return claimed
end

function qx_descriptor_root_with_ordinal(descriptor)
  selected = descriptor_root(descriptor)
  ring, variable = polynomial_ring(ZZ, "qx_ordinal_x")
  polynomial = descriptor_polynomial(
    descriptor["coefficients_high_to_low"], ring, variable
  )
  real_roots = sort(
    QQBarFieldElem[
      root_value for root_value in roots(QB, polynomial) if isreal(root_value)
    ];
    lt=(left, right) -> left < right,
  )
  claimed = qx_claimed_root_ordinal(descriptor)
  claimed < length(real_roots) ||
    throw(ReplayFailure("descriptor real-root ordinal is out of range"))
  position = findfirst(root_value -> root_value == selected, real_roots)
  position === nothing && throw(ReplayFailure("selected root is absent from ordered real roots"))
  ordinal = Int(position) - 1
  claimed == ordinal || throw(ReplayFailure("descriptor real-root ordinal disagrees with isolating interval"))
  return selected, Dict(
    "claimed_real_root_index" => claimed,
    "attested_real_root_index" => ordinal,
    "real_root_count" => length(real_roots),
    "multiplicity" => 1,
    "interval_unique" => true,
    "index_match" => true,
  )
end

function qx_exact_rational(value)::Rational{BigInt}
  if value isa Rational
    return BigInt(numerator(value)) // BigInt(denominator(value))
  elseif value isa Integer
    return BigInt(value) // BigInt(1)
  elseif value isa QQBarFieldElem
    ring, variable = polynomial_ring(ZZ, "qx_rational_x")
    polynomial = minpoly(ring, value)
    degree(polynomial) == 1 || throw(ReplayFailure("value is not exact rational"))
    return -BigInt(coeff(polynomial, 0)) // BigInt(coeff(polynomial, 1))
  end
  throw(ReplayFailure("value is not exact rational"))
end

function qx_exact_integer(value)::Int
  rational_value = qx_exact_rational(value)
  denominator(rational_value) == 1 || throw(ReplayFailure("value is not exact integer"))
  integer_value = numerator(rational_value)
  typemin(Int) <= integer_value <= typemax(Int) || throw(ReplayFailure("integer is too large"))
  return Int(integer_value)
end

function qx_point_on_line(axis::QLine, parameter)
  denominator_value = axis.a^2 + axis.b^2
  iszero(denominator_value) && throw(ReplayFailure("degenerate PointOnLine carrier"))
  base = QPoint(-axis.a * axis.c / denominator_value, -axis.b * axis.c / denominator_value)
  return QPoint(base.x - axis.b * to_qbar(parameter), base.y + axis.a * to_qbar(parameter))
end

function qx_on_line(arguments...; ordered=false)
  ordered isa Bool || throw(ReplayFailure("OnLine ordered must be Boolean"))
  if length(arguments) == 2 && arguments[1] isa QPoint && arguments[2] isa QLine
    return qdistance(arguments[1], arguments[2])
  elseif length(arguments) == 3 && all(value isa QPoint for value in arguments)
    point, first, second = arguments
    collinear_residual = qcross(qsub(first, point), qsub(second, point))
    if ordered
      order_residual = qdistance(point, first) + qdistance(first, second) -
        qdistance(point, second)
      return collinear_residual^2 + order_residual^2
    end
    return collinear_residual
  end
  throw(ReplayFailure("unsupported OnLine arguments"))
end

function qx_point_on_circle(value::QCircle, phase)
  rational_phase = qx_exact_rational(phase)
  argument = QB(2 * rational_phase)
  return QPoint(
    value.center.x + value.radius * cospi(argument),
    value.center.y + value.radius * sinpi(argument),
  )
end

qx_centroid(first::QPoint, second::QPoint, third::QPoint) = qdivide(qadd(qadd(first, second), third), 3)

function qx_perpendicular_bisector(first::QPoint, second::QPoint)
  midpoint = qmidpoint(first, second)
  a_value = second.x - first.x
  b_value = second.y - first.y
  return qline(a_value, b_value, -(a_value * midpoint.x + b_value * midpoint.y))
end

function qx_radical_axis(first::QCircle, second::QCircle)
  a_value = 2 * (second.center.x - first.center.x)
  b_value = 2 * (second.center.y - first.center.y)
  c_value = first.center.x^2 + first.center.y^2 - first.radius^2 -
    second.center.x^2 - second.center.y^2 + second.radius^2
  return qline(a_value, b_value, c_value)
end

function qx_excircle(first::QPoint, second::QPoint, third::QPoint; vertex="A")
  qx_require_triangle_hard_margin(first, second, third)
  vertex in ("A", "B", "C") || throw(ReplayFailure("unsupported Excircle vertex"))
  center_value, denominator_value = qtriangle_center(
    first, second, third; external=true, vertex=vertex
  )
  denominator_value > 0 || throw(ReplayFailure("degenerate Excircle"))
  return qcircle(center_value, 2 * qarea(first, second, third) / denominator_value)
end

function qx_incircle_contact(first::QPoint, second::QPoint, third::QPoint; side=nothing)
  qx_require_triangle_hard_margin(first, second, third)
  a_value = qdistance(second, third)
  b_value = qdistance(third, first)
  c_value = qdistance(first, second)
  all(value > 0 for value in (a_value, b_value, c_value)) ||
    throw(ReplayFailure("degenerate IncircleContactPoint"))
  qarea(first, second, third) > 0 || throw(ReplayFailure("degenerate IncircleContactPoint"))
  semiperimeter = (a_value + b_value + c_value) / 2
  contact_bc = qpoint_on_segment(second, third, (semiperimeter - b_value) / a_value)
  contact_ca = qpoint_on_segment(third, first, (semiperimeter - c_value) / b_value)
  contact_ab = qpoint_on_segment(first, second, (semiperimeter - a_value) / c_value)
  side == "BC" && return contact_bc
  side == "CA" && return contact_ca
  side == "AB" && return contact_ab
  throw(ReplayFailure("IncircleContactPoint needs an exact side selector"))
end

qx_circle_base(value::QCircle) = value
qx_circle_base(value::QArc) = value.circle

function qx_is_tangent(first, second)
  if first isa QLine && (second isa QCircle || second isa QArc)
    circle_value = qx_circle_base(second)
    return abs(qdistance(circle_value.center, first) - circle_value.radius)
  elseif second isa QLine && (first isa QCircle || first isa QArc)
    return qx_is_tangent(second, first)
  elseif (first isa QCircle || first isa QArc) && (second isa QCircle || second isa QArc)
    first_circle, second_circle = qx_circle_base(first), qx_circle_base(second)
    center_distance = qdistance(first_circle.center, second_circle.center)
    external = abs(center_distance - (first_circle.radius + second_circle.radius))
    internal = abs(center_distance - abs(first_circle.radius - second_circle.radius))
    return external <= internal ? external : internal
  end
  throw(ReplayFailure("unsupported IsTangent arguments"))
end

function qx_selector_scale(candidates, references...)
  scale = QB(1)
  for point in candidates
    scale = max(scale, abs(point.x), abs(point.y))
  end
  for point in references
    point === nothing && continue
    point isa QPoint || throw(ReplayFailure("intersection selector needs a Point"))
    scale = max(scale, abs(point.x), abs(point.y))
  end
  return scale
end

function qx_certify_intersection_geometry(first, second, candidates)
  (first isa QArc || second isa QArc) &&
    throw(ReplayFailure("Arc intersection is outside exact branch authority"))
  first_base, second_base = first, second
  if first_base isa QLine && second_base isa QLine
    determinant = abs(first_base.a * second_base.b - second_base.a * first_base.b)
    !iszero(determinant) && determinant <= QX_DEFAULT_GUARD_MARGIN &&
      throw(ReplayFailure("line intersection is numerically ambiguous"))
  elseif (first_base isa QLine && second_base isa QCircle) ||
      (first_base isa QCircle && second_base isa QLine)
    axis = first_base isa QLine ? first_base : second_base
    circle_value = first_base isa QCircle ? first_base : second_base
    scale = max(
      QB(1), abs(circle_value.center.x), abs(circle_value.center.y),
      abs(circle_value.radius)
    )
    gap = abs(qdistance(circle_value.center, axis) - circle_value.radius)
    !iszero(gap) && gap <= QX_DEFAULT_GUARD_MARGIN * scale &&
      throw(ReplayFailure("line-circle intersection is near tangent"))
  elseif first_base isa QCircle && second_base isa QCircle
    center_distance = qdistance(first_base.center, second_base.center)
    scale = max(
      QB(1), abs(first_base.center.x), abs(first_base.center.y),
      abs(second_base.center.x), abs(second_base.center.y),
      abs(first_base.radius), abs(second_base.radius)
    )
    external_gap = abs(
      center_distance - (first_base.radius + second_base.radius)
    )
    internal_gap = abs(
      center_distance - abs(first_base.radius - second_base.radius)
    )
    for gap in (external_gap, internal_gap)
      !iszero(gap) && gap <= QX_DEFAULT_GUARD_MARGIN * scale &&
        throw(ReplayFailure("circle intersection is near tangent"))
    end
  else
    throw(ReplayFailure("unsupported Intersect arguments"))
  end
  isempty(candidates) && throw(ReplayFailure("intersection has no selected candidate"))
end

function qx_intersect(
  first, second; exclude=nothing, near=nothing, far=nothing
)
  near !== nothing && far !== nothing &&
    throw(ReplayFailure("Intersect cannot combine near and far"))
  candidates = qintersection_candidates(first, second)
  qx_certify_intersection_geometry(first, second, candidates)
  selector_margin = QX_INTERSECTION_HARD_MARGIN *
    qx_selector_scale(candidates, exclude, near, far)
  if exclude !== nothing
    retained = QPoint[]
    for candidate in candidates
      distance_value = qdistance(candidate, exclude)
      iszero(distance_value) && continue
      distance_value > selector_margin ||
        throw(ReplayFailure("Intersect exclude is numerically ambiguous"))
      push!(retained, candidate)
    end
    candidates = retained
    isempty(candidates) &&
      throw(ReplayFailure("intersection has no selected candidate after exclusion"))
  end
  if near !== nothing || far !== nothing
    reference = near !== nothing ? near : far
    best = candidates[1]
    best_score = qdistance(best, reference)
    for candidate in Iterators.drop(candidates, 1)
      score = qdistance(candidate, reference)
      abs(score - best_score) > selector_margin ||
        throw(ReplayFailure("Intersect near/far selector is ambiguous"))
      if (near !== nothing && score < best_score) ||
          (far !== nothing && score > best_score)
        best, best_score = candidate, score
      end
    end
    return best
  end
  length(candidates) == 1 ||
    throw(ReplayFailure("unselected multivalued intersection"))
  return only(candidates)
end

qx_orientation(first::QPoint, second::QPoint, third::QPoint) = qcross(qsub(second, first), qsub(third, first))
qx_same_point(first::QPoint, second::QPoint) = first.x == second.x && first.y == second.y

function qx_squared_distance(first::QPoint, second::QPoint)
  delta = qsub(second, first)
  return qdot(delta, delta)
end

function qx_polygon_relative_margin(points::QPoint...)
  length(points) >= 2 || return nothing, QB(0)
  diameter_squared = maximum(
    qx_squared_distance(points[first], points[second])
    for first in eachindex(points) for second in (first + 1):length(points)
  )
  iszero(diameter_squared) && return nothing, diameter_squared
  coordinate_scale = maximum(
    max(abs(point.x), abs(point.y)) for point in points
  )
  translation_ratio = coordinate_scale / sqrt(diameter_squared)
  relative_margin = QX_DEFAULT_GUARD_MARGIN * max(QB(1), translation_ratio)
  return relative_margin, diameter_squared
end

function qx_orientation_class(
  first::QPoint, second::QPoint, third::QPoint, relative_margin
)
  first_delta, second_delta = qsub(second, first), qsub(third, first)
  value = qcross(first_delta, second_delta)
  scale_squared = qdot(first_delta, first_delta) * qdot(second_delta, second_delta)
  if iszero(scale_squared) || value^2 <= relative_margin^2 * scale_squared
    return 0
  end
  return value > 0 ? 1 : 2
end

function qx_on_segment_with_margin(
  first::QPoint, value::QPoint, second::QPoint, relative_margin
)
  coordinate_margin = relative_margin * sqrt(qx_squared_distance(first, second))
  return min(first.x, second.x) - coordinate_margin <= value.x <=
      max(first.x, second.x) + coordinate_margin &&
    min(first.y, second.y) - coordinate_margin <= value.y <=
      max(first.y, second.y) + coordinate_margin
end

function qx_segments_intersect(
  first::QPoint, second::QPoint, third::QPoint, fourth::QPoint, relative_margin
)
  o1 = qx_orientation_class(first, second, third, relative_margin)
  o2 = qx_orientation_class(first, second, fourth, relative_margin)
  o3 = qx_orientation_class(third, fourth, first, relative_margin)
  o4 = qx_orientation_class(third, fourth, second, relative_margin)
  !(0 in (o1, o2, o3, o4)) && o1 != o2 && o3 != o4 && return true
  o1 == 0 && qx_on_segment_with_margin(first, third, second, relative_margin) && return true
  o2 == 0 && qx_on_segment_with_margin(first, fourth, second, relative_margin) && return true
  o3 == 0 && qx_on_segment_with_margin(third, first, fourth, relative_margin) && return true
  o4 == 0 && qx_on_segment_with_margin(third, second, fourth, relative_margin) && return true
  return false
end

function qx_no_self_intersection(points::QPoint...)
  length(points) >= 3 || return false
  count = length(points)
  relative_margin, diameter_squared = qx_polygon_relative_margin(points...)
  relative_margin === nothing && return false
  iszero(diameter_squared) && return false
  for first_index in 1:count
    first_next = first_index == count ? 1 : first_index + 1
    for second_index in (first_index + 1):count
      second_next = second_index == count ? 1 : second_index + 1
      abs(first_index - second_index) == 1 && continue
      first_index == 1 && second_index == count && continue
      if qx_segments_intersect(
        points[first_index], points[first_next], points[second_index],
        points[second_next], relative_margin
      )
        return false
      end
    end
  end
  return true
end

function qx_strict_convex(points::QPoint...)
  length(points) >= 3 || return false
  relative_margin, diameter_squared = qx_polygon_relative_margin(points...)
  relative_margin === nothing && return false
  qx_no_self_intersection(points...) || return false
  for first_index in eachindex(points), second_index in (first_index + 1):length(points)
    qx_squared_distance(points[first_index], points[second_index]) <=
      relative_margin^2 * diameter_squared && return false
  end
  sign_value = nothing
  for index in eachindex(points)
    second_index = index == length(points) ? 1 : index + 1
    third_index = second_index == length(points) ? 1 : second_index + 1
    first_delta = qsub(points[second_index], points[index])
    second_delta = qsub(points[third_index], points[second_index])
    turn = qcross(first_delta, second_delta)
    turn_scale_squared = qdot(first_delta, first_delta) *
      qdot(second_delta, second_delta)
    (iszero(turn_scale_squared) ||
      turn^2 <= relative_margin^2 * turn_scale_squared) && return false
    current_sign = turn > 0
    sign_value === nothing ? (sign_value = current_sign) : current_sign == sign_value || return false
  end
  return true
end

function qx_triangle_measures(first::QPoint, second::QPoint, third::QPoint)
  ab, ac = qsub(second, first), qsub(third, first)
  ba, bc = qsub(first, second), qsub(third, second)
  ca, cb = qsub(first, third), qsub(second, third)
  ab2, ac2, bc2 = qdot(ab, ab), qdot(ac, ac), qdot(bc, bc)
  any(iszero, (ab2, ac2, bc2)) && return nothing
  maximum_side = sqrt(max(ab2, ac2, bc2))
  coordinate_scale = max(
    QB(1), abs(first.x), abs(first.y), abs(second.x), abs(second.y),
    abs(third.x), abs(third.y)
  )
  relative_margin = QX_DEFAULT_GUARD_MARGIN *
    max(QB(1), coordinate_scale / maximum_side)
  side_ratio = min(ab2, ac2, bc2) / max(ab2, ac2, bc2)
  sine_measure = abs(qcross(ab, ac)) / sqrt(ab2 * ac2)
  cosines = (
    qdot(ab, ac) / sqrt(ab2 * ac2),
    qdot(ba, bc) / sqrt(ab2 * bc2),
    qdot(ca, cb) / sqrt(ac2 * bc2),
  )
  return side_ratio, sine_measure, cosines, relative_margin
end

function qx_require_triangle_hard_margin(
  first::QPoint, second::QPoint, third::QPoint
)
  scale = max(
    QB(1), abs(first.x), abs(first.y), abs(second.x), abs(second.y),
    abs(third.x), abs(third.y)
  )
  twice_area = abs(qx_orientation(first, second, third))
  twice_area / scale^2 > QX_TRIANGLE_HARD_MARGIN ||
    throw(ReplayFailure("triangle construction violates hard margin"))
  return nothing
end

function qx_circumcircle(first::QPoint, second::QPoint, third::QPoint)
  qx_require_triangle_hard_margin(first, second, third)
  return qcircumcircle(first, second, third)
end

function qx_circumcenter(first::QPoint, second::QPoint, third::QPoint)
  qx_require_triangle_hard_margin(first, second, third)
  return qcircumcenter(first, second, third)
end

function qx_incenter(first::QPoint, second::QPoint, third::QPoint)
  qx_require_triangle_hard_margin(first, second, third)
  return qtriangle_center(first, second, third)[1]
end

function qx_incircle(first::QPoint, second::QPoint, third::QPoint)
  qx_require_triangle_hard_margin(first, second, third)
  return qincircle(first, second, third)
end

function qx_strict_triangle_measures(first::QPoint, second::QPoint, third::QPoint)
  measures = qx_triangle_measures(first, second, third)
  measures === nothing && return nothing
  side_ratio, sine_measure, cosines, relative_margin = measures
  side_ratio > relative_margin || return nothing
  sine_measure > relative_margin || return nothing
  return cosines, relative_margin
end

function qx_assume_acute(first::QPoint, second::QPoint, third::QPoint)
  measures = qx_strict_triangle_measures(first, second, third)
  measures === nothing && return false
  cosines, relative_margin = measures
  return minimum(cosines) > relative_margin
end

function qx_assume_right(first::QPoint, second::QPoint, third::QPoint)
  measures = qx_strict_triangle_measures(first, second, third)
  measures === nothing && return false
  cosines, _relative_margin = measures
  return any(iszero, cosines)
end

function qx_assume_obtuse(first::QPoint, second::QPoint, third::QPoint)
  measures = qx_strict_triangle_measures(first, second, third)
  measures === nothing && return false
  cosines, relative_margin = measures
  return minimum(cosines) < -relative_margin
end

function qx_angle_scale(value::AngleExpression, factor::Int)
  factor == 0 && return qangle_at_pi(0//1)
  factor < 0 && return qangle_neg(qx_angle_scale(value, -factor))
  result = qangle_at_pi(0//1)
  addend = value
  remaining = factor
  while remaining > 0
    isodd(remaining) && (result = qangle_add(result, addend))
    remaining = fld(remaining, 2)
    remaining > 0 && (addend = qangle_add(addend, addend))
  end
  return result
end

function qx_principal_angle(value::AngleExpression)
  return value.lower_pi >= 0//1 && value.upper_pi <= 1//1 && value.sine >= 0
end

function qx_angle_compare(first::AngleExpression, second::AngleExpression)
  if first.lower_pi == first.upper_pi && second.lower_pi == second.upper_pi
    return first.lower_pi < second.lower_pi ? -1 : first.lower_pi > second.lower_pi ? 1 : 0
  end
  qx_principal_angle(first) && qx_principal_angle(second) ||
    throw(ReplayFailure("angle order is outside the principal exact chart"))
  return first.cosine > second.cosine ? -1 : first.cosine < second.cosine ? 1 : 0
end

function qangle(first::QLine, second::QLine)
  first_norm = sqrt(first.a^2 + first.b^2)
  second_norm = sqrt(second.a^2 + second.b^2)
  (iszero(first_norm) || iszero(second_norm)) &&
    throw(ReplayFailure("degenerate line Angle"))
  denominator_value = first_norm * second_norm
  cosine = abs(first.a * second.a + first.b * second.b) / denominator_value
  sine = abs(first.a * second.b - first.b * second.a) / denominator_value
  cosine^2 + sine^2 == 1 || throw(ReplayFailure("line angle unit identity failed"))
  return AngleExpression(cosine, sine, 0//1, 1//2)
end

function qx_typed_angle_equal(first, second, arity::Int)
  (first isa AngleExpression && second isa AngleExpression) ||
    throw(ReplayFailure("typed Angle equality operands are not angles"))
  arity in (2, 3) || throw(ReplayFailure("typed Angle equality arity is unsupported"))
  expected_upper = arity == 2 ? 1//2 : 1//1
  (first.lower_pi == 0//1 && second.lower_pi == 0//1 &&
   first.upper_pi == expected_upper && second.upper_pi == expected_upper &&
   first.sine >= 0 && second.sine >= 0) ||
    throw(ReplayFailure("typed Angle equality domain proof failed"))
  equal = first.cosine == second.cosine && first.sine == second.sine
  return equal ? QB(0) : QB(1)
end

function qx_minmax(arguments, choose_min::Bool)
  isempty(arguments) && throw(ReplayFailure("min/max needs at least one argument"))
  best = arguments[1]
  for value in Iterators.drop(arguments, 1)
    order = if best isa AngleExpression || value isa AngleExpression || best isa PiMultiple || value isa PiMultiple
      qx_angle_compare(as_angle(best), as_angle(value))
    else
      scalar_compare(best, value)
    end
    ((choose_min && order > 0) || (!choose_min && order < 0)) && (best = value)
  end
  return best
end

function qx_trig(name::String, value)
  angle_value = value isa AngleExpression ? value : value isa PiMultiple ? as_angle(value) : nothing
  if angle_value !== nothing
    name == "sin" && return angle_value.sine
    name == "cos" && return angle_value.cosine
    name == "tan" && (iszero(angle_value.cosine) && throw(ReplayFailure("tan pole")); return angle_value.sine / angle_value.cosine)
  elseif value isa QQBarFieldElem && iszero(value)
    return name == "cos" ? QB(1) : QB(0)
  elseif value isa Rational && iszero(value)
    return name == "cos" ? QB(1) : QB(0)
  end
  throw(ReplayFailure("general algebraic-radian trigonometry is outside QQBar authority"))
end

"""


def _extended_worker_source() -> str:
    source = QQBAR_WORKER.read_text(encoding="utf-8")
    old_line = """function qline(arguments...)
  if length(arguments) == 2 && arguments[1] isa QPoint && arguments[2] isa QPoint
    first, second = arguments
    value = QLine(
      first.y - second.y,
      second.x - first.x,
      first.x * second.y - second.x * first.y,
    )
  elseif length(arguments) == 3
    value = QLine(to_qbar(arguments[1]), to_qbar(arguments[2]), to_qbar(arguments[3]))
  else
    throw(ReplayFailure("unsupported Line arguments"))
  end
  iszero(value.a^2 + value.b^2) && throw(ReplayFailure("degenerate line"))
  return value
end
"""
    new_line = """function qline(arguments...)
  if length(arguments) == 2 && arguments[1] isa QPoint && arguments[2] isa QPoint
    first, second = arguments
    point_scale = max(
      QB(1), abs(first.x), abs(first.y), abs(second.x), abs(second.y)
    )
    qdistance(first, second) / point_scale > QX_LINE_HARD_MARGIN ||
      throw(ReplayFailure("Line endpoints violate hard distinctness margin"))
    a_value = first.y - second.y
    b_value = second.x - first.x
    c_value = first.x * second.y - second.x * first.y
  elseif length(arguments) == 3
    a_value = to_qbar(arguments[1])
    b_value = to_qbar(arguments[2])
    c_value = to_qbar(arguments[3])
  else
    throw(ReplayFailure("unsupported Line arguments"))
  end
  norm_value = sqrt(a_value^2 + b_value^2)
  iszero(norm_value) && throw(ReplayFailure("degenerate line"))
  # The v15 source Line authority normalizes every line on construction.
  # This matters for parameterized points and the public .a/.b/.c fields;
  # retaining merely projectively equivalent coefficients changes the DSL.
  return QLine(
    a_value / norm_value,
    b_value / norm_value,
    c_value / norm_value,
  )
end
"""
    if source.count(old_line) != 1:
        raise ExactCoordinateFailure("QQBar worker line constructor changed")
    source = source.replace(old_line, new_line)
    helper_marker = "function scalar_compare(first, second)\n"
    if source.count(helper_marker) != 1:
        raise ExactCoordinateFailure("QQBar worker scalar marker changed")
    source = source.replace(helper_marker, _EXTENDED_JULIA_HELPERS + helper_marker)

    old_compare = """function scalar_compare(first, second)\n  first_value, second_value = to_qbar(first), to_qbar(second)\n"""
    new_compare = """function scalar_compare(first, second)\n  if first isa AngleExpression || second isa AngleExpression || first isa PiMultiple || second isa PiMultiple\n    return qx_angle_compare(as_angle(first), as_angle(second))\n  end\n  first_value, second_value = to_qbar(first), to_qbar(second)\n"""
    if source.count(old_compare) != 1:
        raise ExactCoordinateFailure("QQBar worker comparison body changed")
    source = source.replace(old_compare, new_compare)

    old_mul = """    if first isa PiMultiple && second isa Rational\n      return PiMultiple(first.coefficient * second)\n    elseif second isa PiMultiple && first isa Rational\n      return PiMultiple(second.coefficient * first)\n    end\n    return first * second\n"""
    new_mul = """    if first isa AngleExpression\n      return qx_angle_scale(first, qx_exact_integer(second))\n    elseif second isa AngleExpression\n      return qx_angle_scale(second, qx_exact_integer(first))\n    elseif first isa PiMultiple\n      return PiMultiple(first.coefficient * qx_exact_rational(second))\n    elseif second isa PiMultiple\n      return PiMultiple(second.coefficient * qx_exact_rational(first))\n    end\n    return first * second\n"""
    if source.count(old_mul) != 1:
        raise ExactCoordinateFailure("QQBar worker multiplication body changed")
    source = source.replace(old_mul, new_mul)

    old_div = """    if first isa PiMultiple && second isa Rational\n      return PiMultiple(first.coefficient / second)\n    end\n    return first / second\n"""
    new_div = """    if first isa PiMultiple\n      return PiMultiple(first.coefficient / qx_exact_rational(second))\n    elseif first isa AngleExpression\n      divisor = qx_exact_integer(second)\n      abs(divisor) == 1 || throw(ReplayFailure("fractional angle scaling is outside exact authority"))\n      return divisor == 1 ? first : qangle_neg(first)\n    end\n    return first / second\n"""
    if source.count(old_div) != 1:
        raise ExactCoordinateFailure("QQBar worker division body changed")
    source = source.replace(old_div, new_div)

    old_call = """function call_function(name::String, arguments, keywords)\n  keyword(name_value, default=nothing) = haskey(keywords, name_value) ? keywords[name_value] : default\n  if name == \"Point\"\n"""
    new_call = """function call_function(name::String, arguments, keywords)\n  keyword(name_value, default=nothing) = haskey(keywords, name_value) ? keywords[name_value] : default\n  if name == \"Circle\"\n    return qcircle(arguments...)\n  elseif name == \"PointOnLine\"\n    return qx_point_on_line(arguments...)\n  elseif name == \"PointOnCircle\"\n    return qx_point_on_circle(arguments...)\n  elseif name == \"CircleThroughPoint\"\n    return qcircle(arguments[1], qdistance(arguments[1], arguments[2]))\n  elseif name == \"CircleThroughThreePoints\"\n    return qcircumcircle(arguments...)\n  elseif name == \"Centroid\"\n    return qx_centroid(arguments...)\n  elseif name == \"Vector\"\n    return qsub(arguments[2], arguments[1])\n  elseif name == \"Dot\"\n    first, second = arguments\n    return first isa QPoint && second isa QPoint ? qdot(first, second) :\n      first isa QLine && second isa QLine ? first.a * second.a + first.b * second.b :\n      throw(ReplayFailure(\"unsupported Dot arguments\"))\n  elseif name in (\"Parallel\", \"ParallelismMeasure\")\n    first, second = arguments[1], arguments[2]\n    first isa QLine && second isa QLine || throw(ReplayFailure(\"parallel residual needs two lines\"))\n    method = name == \"ParallelismMeasure\" ? keyword(\"method\", \"cross\") : \"cross\"\n    residual = first.a * second.b - first.b * second.a\n    method == \"cross\" && return residual\n    method == \"normalized\" && return residual / sqrt((first.a^2 + first.b^2) * (second.a^2 + second.b^2))\n    throw(ReplayFailure(\"unsupported ParallelismMeasure method\"))\n  elseif name == \"PerpendicularBisector\"\n    return qx_perpendicular_bisector(arguments...)\n  elseif name == \"RadicalAxis\"\n    return qx_radical_axis(arguments...)\n  elseif name == \"Excircle\"\n    return qx_excircle(arguments...; vertex=keyword(\"vertex\", \"A\"))\n  elseif name == \"IncircleContactPoint\"\n    return qx_incircle_contact(arguments...; side=keyword(\"side\"))\n  elseif name == \"IsTangent\"\n    return qx_is_tangent(arguments...)\n  elseif name == \"CoordinateX\"\n    value = only(arguments)\n    return value isa QPoint ? value.x : throw(ReplayFailure(\".x needs a Point\"))\n  elseif name == \"CoordinateY\"\n    value = only(arguments)\n    return value isa QPoint ? value.y : throw(ReplayFailure(\".y needs a Point\"))\n  elseif name == \"StrictConvex\"\n    return qx_strict_convex(arguments...)\n  elseif name == \"NoSelfIntersection\"\n    return qx_no_self_intersection(arguments...)\n  elseif name == \"AssumeRight\"\n    length(arguments) == 3 || throw(ReplayFailure(\"AssumeRight options are outside exact authority\"))\n    return qx_assume_right(arguments...)\n  elseif name == \"AssumeObtuse\"\n    length(arguments) == 3 || throw(ReplayFailure(\"AssumeObtuse options are outside exact authority\"))\n    return qx_assume_obtuse(arguments...)\n  elseif name == \"min\"\n    return qx_minmax(arguments, true)\n  elseif name == \"max\"\n    return qx_minmax(arguments, false)\n  elseif name in (\"sin\", \"cos\", \"tan\")\n    return qx_trig(name, only(arguments))\n  elseif name == \"Point\"\n"""
    new_call = new_call.replace(
        '  elseif name == "AssumeRight"\n',
        '  elseif name == "AssumeAcute"\n'
        '    length(arguments) == 3 || throw('
        'ReplayFailure("AssumeAcute options are outside exact authority"))\n'
        '    return qx_assume_acute(arguments...)\n'
        '  elseif name == "AssumeRight"\n',
        1,
    )
    new_call = new_call.replace(
        '  elseif name == "Centroid"\n',
        '  elseif name == "Circumcenter"\n'
        '    return qx_circumcenter(arguments...)\n'
        '  elseif name == "Circumcircle"\n'
        '    return qx_circumcircle(arguments...)\n'
        '  elseif name == "Incenter"\n'
        '    return qx_incenter(arguments...)\n'
        '  elseif name == "Incircle"\n'
        '    return qx_incircle(arguments...)\n'
        '  elseif name == "Centroid"\n',
        1,
    )
    new_call = new_call.replace(
        'return qcircumcircle(arguments...)',
        'return qx_circumcircle(arguments...)',
        1,
    )
    if source.count(old_call) != 1:
        raise ExactCoordinateFailure("QQBar worker call dispatch changed")
    source = source.replace(old_call, new_call)
    on_line_marker = """  if name == "Circle"
    return qcircle(arguments...)
"""
    on_line_dispatch = """  if name in ("OnLine", "Collinear")
    return qx_on_line(arguments...; ordered=keyword("ordered", false))
  elseif name == "Circle"
    return qcircle(arguments...)
"""
    if source.count(on_line_marker) != 1:
        raise ExactCoordinateFailure("QQBar worker OnLine dispatch changed")
    source = source.replace(on_line_marker, on_line_dispatch)
    coordinate_marker = """  elseif name == "StrictConvex"\n"""
    coordinate_dispatch = """  elseif name in ("CoordinateA", "CoordinateB", "CoordinateC")
    value = only(arguments)
    value isa QLine || throw(ReplayFailure(".a/.b/.c needs a Line"))
    return name == "CoordinateA" ? value.a : name == "CoordinateB" ? value.b : value.c
  elseif name == "StrictConvex"
"""
    if source.count(coordinate_marker) != 1:
        raise ExactCoordinateFailure("QQBar worker coordinate dispatch changed")
    source = source.replace(coordinate_marker, coordinate_dispatch)
    intersection_dispatch = (
        'return qintersect(arguments...; exclude=keyword("exclude"), '
        'near=keyword("near"), far=keyword("far"))'
    )
    if source.count(intersection_dispatch) != 1:
        raise ExactCoordinateFailure("QQBar worker Intersect dispatch changed")
    source = source.replace(
        intersection_dispatch,
        'return qx_intersect(arguments...; exclude=keyword("exclude"), '
        'near=keyword("near"), far=keyword("far"))',
    )
    old_roots = '''  coordinates = QQBarFieldElem[descriptor_root(item) for item in job["coordinate_descriptors"]]
  target = descriptor_root(job["target_descriptor"])
'''
    new_roots = '''  coordinate_pairs = [qx_descriptor_root_with_ordinal(item) for item in job["coordinate_descriptors"]]
  coordinates = QQBarFieldElem[first(item) for item in coordinate_pairs]
  coordinate_root_attestations = [last(item) for item in coordinate_pairs]
  target, target_root_attestation = qx_descriptor_root_with_ordinal(job["target_descriptor"])
'''
    if source.count(old_roots) != 1:
        raise ExactCoordinateFailure("QQBar worker descriptor-root seam changed")
    source = source.replace(old_roots, new_roots)
    old_binary_dispatch = '''    elseif operation in ("add", "sub", "mul", "div", "pow")
      arguments = [values[Int(index) + 1] for index in node["args"]]
      binary_operation(operation, arguments...)
'''
    new_binary_dispatch = '''    elseif operation in ("add", "sub", "mul", "div", "pow")
      arguments = [values[Int(index) + 1] for index in node["args"]]
      binary_operation(operation, arguments...)
    elseif operation == "typed_angle_eq"
      arguments = [values[Int(index) + 1] for index in node["args"]]
      qx_typed_angle_equal(arguments..., Int(node["angle_arity"]))
'''
    if source.count(old_binary_dispatch) != 1:
        raise ExactCoordinateFailure("QQBar worker typed-angle operation seam changed")
    source = source.replace(old_binary_dispatch, new_binary_dispatch)
    old_ledger = '''    "coordinate_count" => length(coordinates),
    "coordinate_degrees" => [degree(value) for value in coordinates],
'''
    new_ledger = '''    "coordinate_count" => length(coordinates),
    "coordinate_degrees" => [degree(value) for value in coordinates],
    "typed_angle_relation_count" => get(operation_counts, "typed_angle_eq", 0),
    "typed_direct_angle_equality_exact" => get(operation_counts, "typed_angle_eq", 0) > 0,
    "root_ordinal_attestation_complete" => true,
    "root_ordinal_policy" => "ZERO_BASED_STRICTLY_INCREASING_REAL_QQBAR_V1",
    "root_ordinal_attestation_backend" => "NEMO_QQBAR_SORTED_REAL_ROOTS",
    "coordinate_root_attestations" => coordinate_root_attestations,
    "target_root_attestation" => target_root_attestation,
'''
    if source.count(old_ledger) != 1:
        raise ExactCoordinateFailure("QQBar worker root-ordinal ledger seam changed")
    return source.replace(old_ledger, new_ledger)


def _run_qqbar(job: Mapping[str, Any], *, timeout_seconds: float) -> dict[str, Any]:
    environment = os.environ.copy()
    environment.update(
        {
            "JULIA_NUM_THREADS": "1",
            "JULIA_NUM_GC_THREADS": "1",
            "OPENBLAS_NUM_THREADS": "1",
            "OMP_NUM_THREADS": "1",
            "MKL_NUM_THREADS": "1",
            "NUMEXPR_NUM_THREADS": "1",
        }
    )
    temporary: Path | None = None
    temporary_worker: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", suffix=".json", delete=False
        ) as stream:
            temporary = Path(stream.name)
            json.dump(
                job, stream, ensure_ascii=False, separators=(",", ":"), allow_nan=False
            )
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", suffix=".jl", delete=False
        ) as stream:
            temporary_worker = Path(stream.name)
            stream.write(_extended_worker_source())
        completed = subprocess.run(
            [
                "julia",
                "--compile=no",
                f"--project={JULIA_PROJECT}",
                "--startup-file=no",
                "--history-file=no",
                str(temporary_worker),
                str(temporary),
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=float(timeout_seconds),
            env=environment,
        )
    except subprocess.TimeoutExpired as error:
        raise ExactCoordinateFailure("QQBar exact replay timed out") from error
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
        if temporary_worker is not None:
            temporary_worker.unlink(missing_ok=True)
    if completed.returncode != 0:
        raise ExactCoordinateFailure(
            f"QQBar worker exited {completed.returncode}: {completed.stderr[-400:]}"
        )
    records = [line for line in completed.stdout.splitlines() if line.strip()]
    if len(records) != 1:
        raise ExactCoordinateFailure("QQBar worker emitted a noncanonical record count")
    try:
        result = json.loads(records[0])
    except json.JSONDecodeError as error:
        raise ExactCoordinateFailure("QQBar worker emitted invalid JSON") from error
    if not isinstance(result, dict):
        raise ExactCoordinateFailure("QQBar worker record is not an object")
    return result


def _normalize_exact_guard_calls(job: dict[str, Any]) -> None:
    """Lower comparison guards to QQBar Boolean operations.

    The established QQBar worker predates several scalar guard spellings.
    Lowering is allowed only for the exact two-argument, keyword-free forms;
    tolerance/message variants fail closed rather than silently changing
    their source contract.
    """

    operations = {
        "AssumeEq": "eq",
        "AssumeLe": "le",
        "AssumeGe": "ge",
    }
    for node in job.get("nodes", []):
        if not isinstance(node, dict) or node.get("op") != "call":
            continue
        operation = operations.get(node.get("name"))
        if operation is None:
            continue
        if len(node.get("args", [])) != 2 or node.get("kwargs"):
            raise ExactCoordinateFailure(
                f"exact lowering does not cover {node.get('name')} options"
            )
        arguments = list(node["args"])
        node.clear()
        node.update({"op": operation, "args": arguments})


def certify_exact_coordinate_witness(
    document: Mapping[str, Any],
    coordinate_lane_a: Sequence[str],
    coordinate_lane_b: Sequence[str],
    target_lane_a: str,
    target_lane_b: str,
    *,
    max_degree: int = 8,
    max_coeff: int = 10**12,
    timeout_seconds: float = 12.0,
) -> dict[str, Any]:
    """Return exact target evidence, or a fail-closed rejection record."""

    started = time.monotonic()
    names = list((document.get("variables") or {}).get("names") or [])
    base = {
        "schema_version": "geotarget.v15-243-exact-coordinate-replay/v1",
        "backend": "FLINT_QQBAR_VIA_NEMO",
        "truth_used": False,
        "case_family_or_target_count_routing": False,
        "numeric_nearness_is_authority": False,
        "source_replay_required": True,
    }
    try:
        if len(coordinate_lane_a) != len(names) or len(coordinate_lane_b) != len(names):
            raise ExactCoordinateFailure(
                "coordinate lane dimension differs from source"
            )
        prepared_document, lowering_records = prepare_document(document)
        coordinate_proposals = [
            recognize_algebraic(
                left,
                right,
                max_degree=max_degree,
                max_coeff=max_coeff,
            )
            for left, right in zip(coordinate_lane_a, coordinate_lane_b, strict=True)
        ]
        target_proposal = recognize_algebraic(
            target_lane_a,
            target_lane_b,
            max_degree=max_degree,
            max_coeff=max_coeff,
        )
        job = DAG.compile_document(
            prepared_document,
            coordinate_descriptors=[
                _job_descriptor(item) for item in coordinate_proposals
            ],
            target_descriptor=_job_descriptor(target_proposal),
        )
        _normalize_exact_guard_calls(job)
        replay = _run_qqbar(job, timeout_seconds=timeout_seconds)
        if not isinstance(replay, Mapping):
            raise ExactCoordinateFailure("exact replay returned no terminal object")
        if replay.get("status") != "EXACT_REPLAY_ACCEPTED":
            raise ExactCoordinateFailure(
                f"exact source replay rejected: {replay.get('error', 'unspecified')}"
            )
        _validate_replay_terminal(
            replay,
            document=prepared_document,
            coordinate_root_indices=[
                int(
                    _qqbar_descriptor(item)["isolating_interval"][
                        "real_root_index"
                    ]
                )
                for item in coordinate_proposals
            ],
            target_root_index=int(
                _qqbar_descriptor(target_proposal)["isolating_interval"][
                    "real_root_index"
                ]
            ),
        )
        target_descriptor = _qqbar_descriptor(target_proposal)
        target_attestation = replay["target_root_attestation"]
        target_descriptor["isolating_interval"]["real_root_index"] = int(
            target_attestation["attested_real_root_index"]
        )
        result = {
            **base,
            "status": "EXACT_TARGET_AUTHORITY_READY",
            "authority_pass": True,
            "source_guard_margin_policy": (
                "exact algebraic guard leg; frozen numeric parity separately required"
            ),
            "combined_numeric_and_exact_authority_required": True,
            "standalone_operational_v15_parity_claim": False,
            "source_guard_default_margin_exact_rational": "1/10^40",
            "source_guard_logical_not_fails_closed": True,
            "source_hard_feasibility_exact_subset": True,
            "source_hard_margin_exact_rationals": {
                "line_distinct": "1/10^12",
                "triangle_nondegenerate": "1/10^14",
                "intersection_exclude_distinct": "1/10^12",
            },
            "coordinate_descriptors": coordinate_proposals,
            "exact_target_descriptor": target_descriptor,
            "root_ordinal_attestation_complete": True,
            "root_ordinal_policy": replay["root_ordinal_policy"],
            "root_ordinal_attestation_backend": replay[
                "root_ordinal_attestation_backend"
            ],
            "coordinate_root_attestations": replay[
                "coordinate_root_attestations"
            ],
            "target_root_attestation": dict(target_attestation),
            "source_constraints_exact": int(replay["source_relation_count"]),
            "typed_angle_relation_count": int(
                replay["typed_angle_relation_count"]
            ),
            "typed_direct_angle_equality_exact": replay.get(
                "typed_direct_angle_equality_exact"
            )
            is True,
            "source_guards_exact": int(replay["source_guard_count"]),
            "source_bounds_exact": int(replay["source_bound_count"]),
            "source_raw_answer_exact": replay.get("source_raw_answer_exact") is True,
            "target_link_exact": replay.get("target_link_exact") is True,
            "post_process_used": False,
            "target_set_completeness_claim": False,
            "source_semantic_lowering_count": len(lowering_records),
            "source_semantic_lowering_kinds": sorted(set(lowering_records)),
            "source_semantic_lowering_endpoint_independent": True,
            "maximum_intermediate_qqbar_degree": int(
                replay["maximum_intermediate_qqbar_degree"]
            ),
            "dag_node_count": int(replay["dag_node_count"]),
        }
    except Exception as error:  # deliberately fail closed at every seam
        result = {
            **base,
            "status": "EXACT_TARGET_AUTHORITY_REJECTED",
            "authority_pass": False,
            "failure_type": type(error).__name__,
            "failure": str(error)[:600],
        }
    result["elapsed_wall_seconds"] = time.monotonic() - started
    return result


def finite_numeric_lanes(values: Sequence[Any]) -> bool:
    """Small public preflight used by adapters; it grants no authority."""

    try:
        return all(math.isfinite(float(value)) for value in values)
    except (TypeError, ValueError, OverflowError):
        return False
