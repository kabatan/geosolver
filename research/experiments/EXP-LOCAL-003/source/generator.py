"""Result-blind C0 fixture generator for EXP-LOCAL-003.

This module deliberately stops at document construction.  It neither writes a
materialized input tree nor executes a solver.  ``build_development_documents``
returns three independent projections which a later one-shot materializer can
write into physically separated trees.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import struct
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from geotarget import (
    PluginLock,
    ProblemBuilder,
    canonical_bytes,
    canonical_hash,
    canonical_json,
    validate_document,
)

CARD_SHA256 = "0caae294a032f6d920c718219836e60e57f20c76fe5d790a615e554a95c6ee3c"

GEOMETRY_PLUGIN_ID = "5cba7841-765c-4ef1-987e-27fcb9985e3d/builtin_geometry"
GEOMETRY_MANIFEST = "\n".join(
    (
        "plugin=5cba7841-765c-4ef1-987e-27fcb9985e3d/builtin_geometry@0.1.2",
        "types=scalar,point2,line2,circle2,choice",
        "literal_codecs=scalar,point2,line2,circle2",
        "primitives=point2,line_through,circle2,distance",
        "relations=scalar_equality",
        "relation_truth_policy=scalar_equality:approximate_zero",
        "guards=positive",
        "domains=safe_geometry_domain",
        "branches=line_circle_intersections",
        "selectors=near,far,orientation",
        "capabilities=numeric_generic_float64_bigfloat",
    )
)

LOCAL3_PLUGIN_ID = "dbf04752-3c0a-4a52-894d-d26ac0522dde/local3_c0_fixture"
LOCAL3_MANIFEST = "\n".join(
    (
        "plugin=dbf04752-3c0a-4a52-894d-d26ac0522dde/local3_c0_fixture@0.1.0",
        "types=opaque_program",
        "primitives=program_target",
        "relations=program_relation",
        "relation_truth_policy=program_relation:approximate_zero",
        "guards=program_guard",
        "domains=program_domain",
        "signatures=opaque_program,variadic_scalar",
        "instructions=scalar_stack_v1,opaque_loop_v1",
        "capabilities=float64_c0_only",
    )
)

FAMILIES = (
    "SCALE-LADDER",
    "CURVED-CHAIN",
    "NEAR-RANK-DEFICIENT",
    "REDUNDANT-OVERDETERMINED",
    "TANGENT-CIRCLE-LINE",
    "MULTIROOT-WARPED",
    "STRICT-GUARD-BOUNDARY",
    "OPAQUE-TRANSCENDENTAL-C0",
)
PRIMARY_REPRESENTATIONS = (
    "base",
    "signed-permutation",
    "semantic-equivalent-row-rescaling",
)
SAFETY_REPRESENTATION = "orthogonal-safety"

CALIBRATION_DOMAIN = b"geotarget.exp-local-003.calibration.counter.v1\0"
CALIBRATION_SEED = hashlib.sha256(b"EXP-LOCAL-003-CALIBRATION-SEED-V1").digest()
START_DOMAIN = b"geotarget.exp-local-003.starts.counter.v1\0"
START_SEED = hashlib.sha256(b"EXP-LOCAL-003-START-SEED-V1").digest()
PRIVATE_SEED = hashlib.sha256(b"EXP-LOCAL-003-GENERATOR-PRIVATE-V1").digest()
CASE_KEY_SEED = hashlib.sha256(b"EXP-LOCAL-003-OPAQUE-CASE-KEY-V1").digest()

Expr = tuple[Any, ...]


def canonical_document_bytes(document: object) -> bytes:
    """Use the repository's RFC 8785 encoder for every persisted identity."""

    return canonical_bytes(document)


def canonical_document_hash(document: object) -> str:
    return canonical_hash(document)


def _sha256_text(value: str) -> str:
    return "sha256:" + hashlib.sha256(value.encode("utf-8")).hexdigest()


def _geometry_lock() -> PluginLock:
    return PluginLock(
        GEOMETRY_PLUGIN_ID,
        "0.1.2",
        "1.0.0",
        _sha256_text(GEOMETRY_MANIFEST),
    )


def _local3_lock() -> PluginLock:
    return PluginLock(
        LOCAL3_PLUGIN_ID,
        "0.1.0",
        "1.0.0",
        _sha256_text(LOCAL3_MANIFEST),
    )


def _input(index: int) -> Expr:
    return ("input", index)


def _constant(value: float) -> Expr:
    number = float(value)
    if not math.isfinite(number):
        raise ValueError("program constants must be finite binary64 values")
    return ("constant", number)


def _unary(operation: str, value: Expr) -> Expr:
    return (operation, value)


def _binary(operation: str, left: Expr, right: Expr) -> Expr:
    return (operation, left, right)


def _add(left: Expr, right: Expr) -> Expr:
    return _binary("add", left, right)


def _sub(left: Expr, right: Expr) -> Expr:
    return _binary("sub", left, right)


def _mul(left: Expr, right: Expr) -> Expr:
    return _binary("mul", left, right)


def _div(left: Expr, right: Expr) -> Expr:
    return _binary("div", left, right)


def _neg(value: Expr) -> Expr:
    return _unary("neg", value)


def _sum(expressions: list[Expr]) -> Expr:
    if not expressions:
        return _constant(0.0)
    result = expressions[0]
    for expression in expressions[1:]:
        result = _add(result, expression)
    return result


def _product(expressions: list[Expr]) -> Expr:
    if not expressions:
        return _constant(1.0)
    result = expressions[0]
    for expression in expressions[1:]:
        result = _mul(result, expression)
    return result


def _scaled(value: Expr, coefficient: float) -> Expr:
    if coefficient == 1.0:
        return value
    if coefficient == -1.0:
        return _neg(value)
    return _mul(_constant(coefficient), value)


def _compile_expression(expression: Expr) -> dict[str, object]:
    instructions: list[dict[str, object]] = []

    def visit(node: Expr) -> None:
        operation = str(node[0])
        if operation == "input":
            instructions.append({"op": operation, "index": int(node[1])})
            return
        if operation == "constant":
            instructions.append({"op": operation, "value": float(node[1])})
            return
        if operation == "opaque":
            visit(node[1])
            instructions.append(
                {
                    "op": operation,
                    "loops": int(node[2]),
                    "mixing": float(node[3]),
                    "bias": float(node[4]),
                }
            )
            return
        for child in node[1:]:
            visit(child)
        instructions.append({"op": operation})

    visit(expression)
    return {"version": 1, "instructions": instructions}


def _evaluate_expression(expression: Expr, values: list[float]) -> float:
    operation = str(expression[0])
    if operation == "input":
        return float(values[int(expression[1])])
    if operation == "constant":
        return float(expression[1])
    if operation == "neg":
        return -_evaluate_expression(expression[1], values)
    if operation == "sin":
        return math.sin(_evaluate_expression(expression[1], values))
    if operation == "cos":
        return math.cos(_evaluate_expression(expression[1], values))
    if operation == "exp":
        return math.exp(_evaluate_expression(expression[1], values))
    if operation == "tanh":
        return math.tanh(_evaluate_expression(expression[1], values))
    if operation == "abs":
        return abs(_evaluate_expression(expression[1], values))
    if operation == "sqrt":
        return math.sqrt(_evaluate_expression(expression[1], values))
    if operation == "opaque":
        input_value = _evaluate_expression(expression[1], values)
        loops = int(expression[2])
        mixing = float(expression[3])
        bias = float(expression[4])
        state = input_value + bias
        for iteration in range(1, loops + 1):
            attenuation = 1.0 / (iteration + 1)
            transcendental = (
                math.sin(state)
                + math.cos(attenuation * input_value)
                + math.exp(-abs(state))
            )
            if iteration % 2:
                state = math.tanh(
                    transcendental / 3.0
                    + mixing * input_value / (1.0 + abs(input_value))
                )
            else:
                state = math.tanh(transcendental / 3.0 - mixing * state + bias)
        return state
    left = _evaluate_expression(expression[1], values)
    right = _evaluate_expression(expression[2], values)
    if operation == "add":
        return left + right
    if operation == "sub":
        return left - right
    if operation == "mul":
        return left * right
    if operation == "div":
        return left / right
    raise ValueError(f"unknown expression operation: {operation}")


@dataclass(frozen=True, slots=True)
class BaseCase:
    bounds: tuple[tuple[float, float], ...]
    origins: tuple[float, ...]
    variable_scales: tuple[float, ...]
    relations: tuple[Expr, ...]
    relation_scales: tuple[float, ...]
    target: Expr
    guards: tuple[Expr, ...]
    domains: tuple[Expr, ...]
    gold_configurations: tuple[tuple[float, ...], ...]
    outward_target_intervals: bool = False


@dataclass(frozen=True, slots=True)
class Representation:
    name: str
    variable_permutation: tuple[int, ...]  # base j -> candidate index
    variable_signs: tuple[float, ...]  # x_base[j] = sign[j] * x_candidate[perm[j]]
    residual_matrix: tuple[tuple[float, ...], ...]  # candidate rows by base rows
    expected_invariant: bool


def _linear_residual(
    operator: list[list[float]], root: list[float]
) -> tuple[Expr, ...]:
    variables = [_input(index) for index in range(len(root))]
    centered = [
        _sub(value, _constant(root[index])) for index, value in enumerate(variables)
    ]
    return tuple(
        _sum(
            [
                _scaled(centered[column], coefficient)
                for column, coefficient in enumerate(row)
            ]
        )
        for row in operator
    )


def _opaque_state(value: Expr, *, loops: int, mixing: float, bias: float) -> Expr:
    return ("opaque", value, int(loops), float(mixing), float(bias))


def _family_case(family_ordinal: int, group: int) -> BaseCase:
    if family_ordinal == 0:
        dimension = 4
        root = [-0.5, -0.25, 0.25, 0.5]
        exponents = (0, 6, 12, 18) if group == 0 else (-6, 2, 10, 22)
        relations = tuple(
            _scaled(
                _sub(_input(index), _constant(root[index])), math.ldexp(1.0, exponent)
            )
            for index, exponent in enumerate(exponents)
        )
        return BaseCase(
            tuple((-2.0, 2.0) for _ in range(dimension)),
            (0.0,) * dimension,
            (2.0,) * dimension,
            relations,
            (1.0,) * dimension,
            _input(0),
            (),
            (),
            (tuple(root),),
        )

    if family_ordinal == 1:
        dimension = 4
        curvature = 32.0 if group == 0 else 256.0
        relations: list[Expr] = [_sub(_input(0), _constant(1.0))]
        for index in range(1, dimension):
            square = _mul(_input(index - 1), _input(index - 1))
            relations.append(_scaled(_sub(_input(index), square), curvature))
        return BaseCase(
            tuple((-2.0, 2.0) for _ in range(dimension)),
            (0.0,) * dimension,
            (2.0,) * dimension,
            tuple(relations),
            (1.0,) * dimension,
            _input(dimension - 1),
            (),
            (),
            ((1.0,) * dimension,),
        )

    if family_ordinal == 2:
        epsilon = math.ldexp(1.0, -12 if group == 0 else -22)
        operator = [
            [1.0, 1.0, 0.0],
            [1.0, 1.0 + epsilon, 0.0],
            [0.25, -0.25, 0.5],
        ]
        root = [-0.5, 0.25, 0.5]
        return BaseCase(
            ((-2.0, 2.0),) * 3,
            (0.0,) * 3,
            (2.0,) * 3,
            _linear_residual(operator, root),
            (1.0, 1.0, 0.5),
            _input(0),
            (),
            (),
            (tuple(root),),
        )

    if family_ordinal == 3:
        perturbation = math.ldexp(1.0, -18) if group else 0.0
        operator = [
            [1.0, 0.0, 0.0],
            [0.0, 1.0, 0.0],
            [0.0, 0.0, 1.0],
            [1.0, 1.0, 0.0],
            [0.0, 1.0, 1.0],
            [1.0, -1.0 + perturbation, 1.0],
        ]
        root = [-0.5, 0.25, 0.5]
        return BaseCase(
            ((-2.0, 2.0),) * 3,
            (0.0,) * 3,
            (2.0,) * 3,
            _linear_residual(operator, root),
            (1.0,) * len(operator),
            _input(0),
            (),
            (),
            (tuple(root),),
        )

    if family_ordinal == 4:
        radius = 1.0 if group == 0 else 0.75
        ratio = 0.99 if group == 0 else 0.9999
        height = radius * ratio
        horizontal = math.sqrt((radius - height) * (radius + height))
        circle = _sub(
            _add(_mul(_input(0), _input(0)), _mul(_input(1), _input(1))),
            _constant(radius * radius),
        )
        line = _sub(_input(1), _constant(height))
        configurations = ((-horizontal, height), (horizontal, height))
        return BaseCase(
            ((-1.5 * radius, 1.5 * radius),) * 2,
            (0.0, 0.0),
            (1.5 * radius, 1.5 * radius),
            (circle, line),
            (radius * radius, radius),
            _input(0),
            (),
            (),
            configurations,
            True,
        )

    if family_ordinal == 5:
        roots = (-0.75, -0.125, 0.625) if group == 0 else (-0.625, 0.25, 0.75)
        coefficient = 0.75 if group == 0 else 1.25
        warp = 0.125 if group == 0 else 0.375
        polynomial = _product([_sub(_input(0), _constant(root)) for root in roots])
        dependent = _scaled(
            _add(_mul(_input(0), _input(0)), _scaled(_input(0), 0.2)),
            coefficient,
        )
        second = _scaled(
            _sub(_add(_input(1), _scaled(_unary("sin", _input(0)), warp)), dependent),
            64.0,
        )
        third = _scaled(
            _sub(_input(2), _add(_scaled(_input(0), 0.5), _scaled(_input(1), 0.25))),
            4.0,
        )
        configurations: list[tuple[float, ...]] = []
        for root in roots:
            y = coefficient * (root * root + 0.2 * root) - warp * math.sin(root)
            configurations.append((root, y, 0.5 * root + 0.25 * y))
        return BaseCase(
            ((-2.0, 2.0),) * 3,
            (0.0,) * 3,
            (2.0,) * 3,
            (polynomial, second, third),
            (1.0, 1.0, 1.0),
            _input(0),
            (),
            (),
            tuple(configurations),
            True,
        )

    if family_ordinal == 6:
        boundary = 1.0 - math.ldexp(1.0, -20) if group == 0 else 1.0
        coupling = 0.625 if group == 0 else 0.875
        polynomial = _mul(
            _sub(_input(0), _constant(1.0)),
            _sub(_input(0), _constant(2.0)),
        )
        coupled = _sub(_input(1), _scaled(_input(0), coupling))
        guard = _sub(_input(0), _constant(boundary))
        domain = _sub(_constant(3.0), _input(0))
        candidates = ((1.0, coupling), (2.0, 2.0 * coupling))
        valid = tuple(
            configuration for configuration in candidates if configuration[0] > boundary
        )
        return BaseCase(
            ((0.0, 3.0), (-1.0, 3.0)),
            (1.5, 1.0),
            (1.5, 2.0),
            (polynomial, coupled),
            (1.0, 1.0),
            _input(0),
            (guard,),
            (domain,),
            valid,
        )

    if family_ordinal == 7:
        roots = (-0.75, 0.0, 0.75) if group == 0 else (-0.6, 0.15, 0.7)
        loops = 5 if group == 0 else 7
        mixing = 0.1 if group == 0 else 0.2
        bias = 0.017 if group == 0 else 0.043
        opaque = _opaque_state(_input(0), loops=loops, mixing=mixing, bias=bias)
        polynomial = _product([_sub(_input(0), _constant(root)) for root in roots])
        first = _mul(polynomial, _add(_constant(1.0), _scaled(opaque, 0.05)))
        second = _sub(_input(1), opaque)
        target = _add(_input(0), _scaled(_input(1), 0.125))
        domain = _sub(_constant(1.24), _unary("abs", _input(0)))
        configurations = tuple(
            (root, _evaluate_expression(opaque, [root, 0.0])) for root in roots
        )
        return BaseCase(
            ((-1.2, 1.2), (-1.5, 1.5)),
            (0.0, 0.0),
            (1.2, 1.5),
            (first, second),
            (1.0, 1.0),
            target,
            (),
            (domain,),
            configurations,
            True,
        )

    raise ValueError(f"unknown family ordinal: {family_ordinal}")


def _identity_matrix(rows: int) -> list[list[float]]:
    return [
        [1.0 if row == column else 0.0 for column in range(rows)] for row in range(rows)
    ]


def _representation(base: BaseCase, group: int, name: str) -> Representation:
    dimension = len(base.bounds)
    residual_dimension = len(base.relations)
    if name == "base":
        return Representation(
            name,
            tuple(range(dimension)),
            (1.0,) * dimension,
            tuple(tuple(row) for row in _identity_matrix(residual_dimension)),
            True,
        )
    if name == "signed-permutation":
        shift = 1 + group % max(1, dimension - 1)
        variable_permutation = tuple(
            (index + shift) % dimension for index in range(dimension)
        )
        variable_signs = tuple(
            -1.0 if (index + group) % 2 else 1.0 for index in range(dimension)
        )
        residual_matrix = [
            [0.0] * residual_dimension for _ in range(residual_dimension)
        ]
        residual_shift = 1 + group % max(1, residual_dimension - 1)
        for base_row in range(residual_dimension):
            candidate_row = (base_row + residual_shift) % residual_dimension
            sign = -1.0 if (base_row + group) % 2 else 1.0
            residual_matrix[candidate_row][base_row] = sign
        return Representation(
            name,
            variable_permutation,
            variable_signs,
            tuple(tuple(row) for row in residual_matrix),
            True,
        )
    if name == "semantic-equivalent-row-rescaling":
        matrix = [[0.0] * residual_dimension for _ in range(residual_dimension)]
        for row in range(residual_dimension):
            exponent = ((row + 2 * group) % 9) - 4
            matrix[row][row] = math.ldexp(1.0, exponent)
        return Representation(
            name,
            tuple(range(dimension)),
            (1.0,) * dimension,
            tuple(tuple(row) for row in matrix),
            True,
        )
    if name == SAFETY_REPRESENTATION:
        matrix = _identity_matrix(residual_dimension)
        for row in range(0, residual_dimension - 1, 2):
            matrix[row][row] = 0.6
            matrix[row][row + 1] = 0.8
            matrix[row + 1][row] = -0.8
            matrix[row + 1][row + 1] = 0.6
        return Representation(
            name,
            tuple(range(dimension)),
            (1.0,) * dimension,
            tuple(tuple(row) for row in matrix),
            False,
        )
    raise ValueError(f"unknown representation: {name}")


def _mapped_inputs(representation: Representation) -> list[Expr]:
    return [
        _scaled(_input(candidate_index), representation.variable_signs[base_index])
        for base_index, candidate_index in enumerate(
            representation.variable_permutation
        )
    ]


def _substitute(expression: Expr, inputs: list[Expr]) -> Expr:
    operation = str(expression[0])
    if operation == "input":
        return inputs[int(expression[1])]
    if operation == "constant":
        return expression
    if operation == "opaque":
        return (operation, _substitute(expression[1], inputs), *expression[2:])
    return (operation, *(_substitute(child, inputs) for child in expression[1:]))


def _transformed_expressions(
    base: BaseCase, representation: Representation
) -> tuple[tuple[Expr, ...], Expr, tuple[Expr, ...], tuple[Expr, ...]]:
    inputs = _mapped_inputs(representation)
    base_relations = [_substitute(expression, inputs) for expression in base.relations]
    mixing_sources = base_relations
    if not representation.expected_invariant:
        # Safety16 rotates semantic z, not unit-bearing raw y.  Its public
        # relation scales are one, so the emitted raw rows are Q * (y / s).
        mixing_sources = [
            _div(expression, _constant(base.relation_scales[index]))
            for index, expression in enumerate(base_relations)
        ]
    candidate_relations = tuple(
        _sum(
            [
                _scaled(mixing_sources[column], coefficient)
                for column, coefficient in enumerate(row)
                if coefficient != 0.0
            ]
        )
        for row in representation.residual_matrix
    )
    return (
        candidate_relations,
        _substitute(base.target, inputs),
        tuple(_substitute(expression, inputs) for expression in base.guards),
        tuple(_substitute(expression, inputs) for expression in base.domains),
    )


def _candidate_variable_metadata(
    base: BaseCase, representation: Representation
) -> tuple[list[tuple[float, float]], list[float], list[float]]:
    dimension = len(base.bounds)
    bounds: list[tuple[float, float] | None] = [None] * dimension
    origins: list[float | None] = [None] * dimension
    scales: list[float | None] = [None] * dimension
    for base_index, candidate_index in enumerate(representation.variable_permutation):
        sign = representation.variable_signs[base_index]
        lower, upper = base.bounds[base_index]
        bounds[candidate_index] = (lower, upper) if sign > 0 else (-upper, -lower)
        origins[candidate_index] = sign * base.origins[base_index]
        scales[candidate_index] = base.variable_scales[base_index]
    if any(value is None for value in (*bounds, *origins, *scales)):
        raise AssertionError("variable representation is not a bijection")
    return (
        [value for value in bounds if value is not None],
        [value for value in origins if value is not None],
        [value for value in scales if value is not None],
    )


def _relation_scales(base: BaseCase, representation: Representation) -> list[float]:
    scales: list[float] = []
    for row in representation.residual_matrix:
        nonzero = [(index, value) for index, value in enumerate(row) if value != 0.0]
        if representation.expected_invariant and len(nonzero) == 1:
            index, multiplier = nonzero[0]
            scales.append(abs(multiplier) * base.relation_scales[index])
        else:
            scales.append(1.0)
    return scales


def _build_problem(
    base: BaseCase, representation: Representation
) -> tuple[dict[str, object], dict[str, object]]:
    bounds, origins, variable_scales = _candidate_variable_metadata(
        base, representation
    )
    relations, target, guards, domains = _transformed_expressions(base, representation)
    relation_scales = _relation_scales(base, representation)
    geometry = _geometry_lock()
    fixture = _local3_lock()
    builder = ProblemBuilder(plugins=(geometry, fixture))
    scalar_type = f"{GEOMETRY_PLUGIN_ID}::scalar"
    program_type = f"{LOCAL3_PLUGIN_ID}::opaque_program"
    variables = [
        builder.variable(
            f"v_{index:04d}",
            type_id=scalar_type,
            node_id=f"x_{index:04d}",
            origin=origins[index],
            scale=variable_scales[index],
            lower=bounds[index][0],
            upper=bounds[index][1],
        )
        for index in range(len(bounds))
    ]

    for index, (expression, scale) in enumerate(
        zip(relations, relation_scales, strict=True)
    ):
        program = builder.literal(
            _compile_expression(expression),
            type_id=program_type,
            node_id=f"p_r_{index:04d}",
        )
        relation = builder.call(
            f"{LOCAL3_PLUGIN_ID}::program_relation",
            program,
            *variables,
            node_id=f"r_{index:04d}",
        )
        builder.relation(relation, scale_override=scale)

    for index, expression in enumerate(guards):
        program = builder.literal(
            _compile_expression(expression),
            type_id=program_type,
            node_id=f"p_g_{index:04d}",
        )
        guard = builder.call(
            f"{LOCAL3_PLUGIN_ID}::program_guard",
            program,
            *variables,
            node_id=f"g_{index:04d}",
        )
        builder.guard(guard, strict=True, scale_override=1.0)

    for index, expression in enumerate(domains):
        program = builder.literal(
            _compile_expression(expression),
            type_id=program_type,
            node_id=f"p_d_{index:04d}",
        )
        domain = builder.call(
            f"{LOCAL3_PLUGIN_ID}::program_domain",
            program,
            *variables,
            node_id=f"d_{index:04d}",
        )
        builder.domain(domain, strict=True)

    target_program = builder.literal(
        _compile_expression(target),
        type_id=program_type,
        node_id="p_target",
    )
    target_node = builder.call(
        f"{LOCAL3_PLUGIN_ID}::program_target",
        target_program,
        *variables,
        node_id="target_value",
    )
    builder.target(target_node)
    problem = builder.build().to_dict()
    validate_document(problem)
    canonical_document_bytes(problem)
    public = {
        "dimension": len(bounds),
        "relation_count": len(relations),
        "bounds": [[lower, upper] for lower, upper in bounds],
        "origins": origins,
        "variable_scales": variable_scales,
        "relation_scales": relation_scales,
        "logical_capability": "C0",
    }
    return problem, public


def _fraction_fma(first: float, second: float, third: float) -> float:
    """Correctly rounded binary64 FMA without depending on host ``math.fma``."""

    exact = Fraction.from_float(first) * Fraction.from_float(
        second
    ) + Fraction.from_float(third)
    result = float(exact)
    if not math.isfinite(result):
        raise ValueError("fused operation produced a non-finite value")
    return result


def _safe_midpoint_halfwidth(lower: float, upper: float) -> tuple[float, float]:
    difference = upper - lower
    if math.isfinite(difference):
        halfwidth = difference / 2.0
        midpoint = lower + halfwidth
    else:
        halfwidth = upper / 2.0 - lower / 2.0
        midpoint = lower / 2.0 + upper / 2.0
    if not math.isfinite(midpoint) or not math.isfinite(halfwidth) or halfwidth <= 0.0:
        raise ValueError("bounds do not have a safe finite midpoint and halfwidth")
    return midpoint, halfwidth


def _counter_unit(
    domain: bytes, seed: bytes, key: bytes, row: int, column: int
) -> float:
    digest = hashlib.sha256(
        domain + seed + key + struct.pack(">I", row) + struct.pack(">I", column)
    ).digest()
    top_52 = int.from_bytes(digest[:8], "big") >> 12
    return (2 * top_52 + 1) * math.ldexp(1.0, -53)


def _counter_points(
    bounds: tuple[tuple[float, float], ...],
    *,
    count: int,
    domain: bytes,
    seed: bytes,
    key: bytes,
) -> list[list[float]]:
    points: list[list[float]] = []
    for row in range(count):
        point: list[float] = []
        for column, (lower, upper) in enumerate(bounds):
            midpoint, halfwidth = _safe_midpoint_halfwidth(lower, upper)
            unit = _counter_unit(domain, seed, key, row, column)
            centered = _fraction_fma(2.0, unit, -1.0)
            value = _fraction_fma(halfwidth, centered, midpoint)
            if not lower <= value <= upper:
                raise ValueError("counter point escaped its public bounds")
            point.append(value)
        points.append(point)
    return points


def _base_to_candidate(
    values: list[float] | tuple[float, ...], representation: Representation
) -> list[float]:
    transformed = [0.0] * len(values)
    for base_index, candidate_index in enumerate(representation.variable_permutation):
        transformed[candidate_index] = (
            representation.variable_signs[base_index] * values[base_index]
        )
    return transformed


def _opaque_key(source_ordinal: int) -> str:
    return hashlib.sha256(CASE_KEY_SEED + struct.pack(">I", source_ordinal)).hexdigest()


def _private_key(label: bytes, latent_ordinal: int) -> bytes:
    return hashlib.sha256(
        PRIVATE_SEED + label + struct.pack(">I", latent_ordinal)
    ).digest()


def _gold_document(base: BaseCase, representation: Representation) -> dict[str, object]:
    configurations = [
        _base_to_candidate(configuration, representation)
        for configuration in base.gold_configurations
    ]
    grouped: dict[str, tuple[float, list[int]]] = {}
    for index, configuration in enumerate(base.gold_configurations):
        value = _evaluate_expression(base.target, list(configuration))
        bits = struct.pack(">d", value).hex()
        if bits not in grouped:
            grouped[bits] = (value, [])
        grouped[bits][1].append(index)
    targets: list[dict[str, object]] = []
    for value, indexes in sorted(grouped.values(), key=lambda item: item[0]):
        if base.outward_target_intervals:
            lower = math.nextafter(value, -math.inf)
            upper = math.nextafter(value, math.inf)
        else:
            lower = value
            upper = value
        targets.append(
            {
                "lower": lower,
                "upper": upper,
                "configuration_indexes": indexes,
            }
        )
    return {"configurations": configurations, "targets": targets}


def _inverse_mapping(representation: Representation) -> dict[str, object]:
    semantic_matrix = [list(row) for row in representation.residual_matrix]
    if representation.expected_invariant:
        semantic_matrix = [
            [
                0.0 if coefficient == 0.0 else math.copysign(1.0, coefficient)
                for coefficient in row
            ]
            for row in representation.residual_matrix
        ]
    return {
        "base_from_candidate_permutation": list(representation.variable_permutation),
        "base_from_candidate_signs": list(representation.variable_signs),
        "candidate_residual_from_base": [
            list(row) for row in representation.residual_matrix
        ],
        "semantic_z_from_base": semantic_matrix,
    }


def _schema(name: str) -> dict[str, object]:
    path = Path(__file__).with_name(name)
    return json.loads(path.read_text(encoding="utf-8"))


def validate_projections(documents: dict[str, dict[str, object]]) -> None:
    contracts = (
        ("candidate", "candidate-inputs.schema.json"),
        ("assessor", "generator-assessor-projection.schema.json"),
        ("generator_private", "generator-private.schema.json"),
    )
    for projection, schema_name in contracts:
        Draft202012Validator(_schema(schema_name)).validate(documents[projection])
        canonical_document_bytes(documents[projection])


def build_development_documents(
    *, validate: bool = True
) -> dict[str, dict[str, object]]:
    """Build the frozen 48-primary + 16-Safety development allocation in memory."""

    candidate_cases: list[dict[str, object]] = []
    assessor_cases: list[dict[str, object]] = []
    private_cases: list[dict[str, object]] = []
    source_ordinal = 0

    for family_ordinal, family_id in enumerate(FAMILIES):
        for group in range(2):
            latent_ordinal = family_ordinal * 2 + group
            base = _family_case(family_ordinal, group)
            calibration_key = _private_key(b"calibration", latent_ordinal)
            start_key = _private_key(b"starts", latent_ordinal)
            base_calibration = _counter_points(
                base.bounds,
                count=64,
                domain=CALIBRATION_DOMAIN,
                seed=CALIBRATION_SEED,
                key=calibration_key,
            )
            base_starts = _counter_points(
                base.bounds,
                count=32,
                domain=START_DOMAIN,
                seed=START_SEED,
                key=start_key,
            )
            for representation_name in (
                *PRIMARY_REPRESENTATIONS,
                SAFETY_REPRESENTATION,
            ):
                representation = _representation(base, group, representation_name)
                opaque_case_key = _opaque_key(source_ordinal)
                problem, public_metadata = _build_problem(base, representation)
                calibration_points = [
                    _base_to_candidate(point, representation)
                    for point in base_calibration
                ]
                starts = [
                    _base_to_candidate(point, representation) for point in base_starts
                ]
                candidate_cases.append(
                    {
                        "opaque_case_key": opaque_case_key,
                        "problem_document": problem,
                        "problem_sha256": canonical_document_hash(problem),
                        "calibration_points": calibration_points,
                        "calibration_points_sha256": canonical_document_hash(
                            calibration_points
                        ),
                        "starts": starts,
                        "starts_sha256": canonical_document_hash(starts),
                        "public_numeric_metadata": public_metadata,
                        "budget": {
                            "local_max_iterations": 250,
                            "local_max_evaluations": 2000,
                            "launch_prefixes": [8, 16, 32],
                        },
                    }
                )
                assessor_cases.append(
                    {
                        "opaque_case_key": opaque_case_key,
                        "family_id": family_id,
                        "family_ordinal": family_ordinal,
                        "latent_group": group,
                        "representation": representation.name,
                        "expected_invariant": representation.expected_invariant,
                        "inverse_mapping": _inverse_mapping(representation),
                        "gold": _gold_document(base, representation),
                        "tolerances": {
                            "configuration_absolute": 1.0e-7,
                            "target_absolute": 1.0e-10,
                            "canonical_residual": math.sqrt(math.ulp(1.0)),
                        },
                    }
                )
                private_cases.append(
                    {
                        "opaque_case_key": opaque_case_key,
                        "source_ordinal": source_ordinal,
                        "family_id": family_id,
                        "latent_group": group,
                        "representation": representation.name,
                        "calibration_key_hex": calibration_key.hex(),
                        "start_key_hex": start_key.hex(),
                    }
                )
                source_ordinal += 1

    candidate_cases.sort(key=lambda item: str(item["opaque_case_key"]))
    assessor_cases.sort(key=lambda item: str(item["opaque_case_key"]))
    private_cases.sort(key=lambda item: str(item["opaque_case_key"]))
    documents: dict[str, dict[str, object]] = {
        "candidate": {
            "schema_version": "exp-local-003-candidate-inputs/v1",
            "card_sha256": CARD_SHA256,
            "cases": candidate_cases,
        },
        "assessor": {
            "schema_version": "exp-local-003-generator-assessor-projection/v1",
            "card_sha256": CARD_SHA256,
            "cases": assessor_cases,
        },
        "generator_private": {
            "schema_version": "exp-local-003-generator-private/v1",
            "card_sha256": CARD_SHA256,
            "counter_contract": {
                "calibration_domain_hex": CALIBRATION_DOMAIN.hex(),
                "calibration_seed_hex": CALIBRATION_SEED.hex(),
                "start_domain_hex": START_DOMAIN.hex(),
                "start_seed_hex": START_SEED.hex(),
                "binary64_fma": "exact-rational-then-roundTiesToEven",
            },
            "cases": private_cases,
        },
    }
    if validate:
        validate_projections(documents)
    return documents


def build_smoke_bundle() -> dict[str, object]:
    """Return representative fixtures plus physically separate truth for Julia CI."""

    documents = build_development_documents()
    assessor_by_key = {
        str(case["opaque_case_key"]): case
        for case in documents["assessor"]["cases"]  # type: ignore[index]
    }
    selected_candidates: list[object] = []
    selected_assessors: list[object] = []
    wanted = {
        (FAMILIES[0], 0, "base"),
        (FAMILIES[6], 1, "base"),
        (FAMILIES[7], 0, "base"),
    }
    for candidate in documents["candidate"]["cases"]:  # type: ignore[index]
        key = str(candidate["opaque_case_key"])
        assessor = assessor_by_key[key]
        identity = (
            assessor["family_id"],
            assessor["latent_group"],
            assessor["representation"],
        )
        if identity in wanted:
            selected_candidates.append(candidate)
            selected_assessors.append(assessor)
    if len(selected_candidates) != len(wanted):
        raise AssertionError("development allocation omitted a smoke case")
    return {
        "candidate_cases": selected_candidates,
        "assessor_cases": selected_assessors,
    }


def build_fma_test_vectors() -> dict[str, object]:
    """Ephemeral cross-runtime vectors binding Fraction FMA to Julia ``Base.fma``."""

    triples = [
        (2.0, math.ldexp(1.0, -53), -1.0),
        (2.0, math.nextafter(1.0, 0.0), -1.0),
        (2.0, 0.5000000000000001, -1.0),
        (2.0, -0.9999999999999999, 1.0),
        (1.5, math.nextafter(1.0, 0.0), -1.5),
        (math.ldexp(1.0, 500), math.ldexp(1.0, -500), -1.0),
    ]
    return {
        "schema_version": "exp-local-003-ephemeral-fma-vectors/v1",
        "vectors": [
            {
                "first": first,
                "second": second,
                "third": third,
                "expected_bits": struct.pack(
                    ">d", _fraction_fma(first, second, third)
                ).hex(),
            }
            for first, second, third in triples
        ],
    }


def _main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--emit-smoke-bundle",
        action="store_true",
        help="write one canonical, ephemeral Python-SDK fixture to stdout",
    )
    parser.add_argument(
        "--emit-fma-vectors",
        action="store_true",
        help="write ephemeral Fraction-FMA conformance vectors to stdout",
    )
    parser.add_argument(
        "--emit-development-bundle-for-tests",
        action="store_true",
        help="write all three in-memory projections to stdout without materializing files",
    )
    args = parser.parse_args()
    if args.emit_smoke_bundle:
        print(canonical_json(build_smoke_bundle()))
        return 0
    if args.emit_fma_vectors:
        print(canonical_json(build_fma_test_vectors()))
        return 0
    if args.emit_development_bundle_for_tests:
        print(canonical_json(build_development_documents()))
        return 0
    parser.error(
        "this C0 source does not materialize inputs; use --emit-smoke-bundle for tests"
    )
    return 2


if __name__ == "__main__":
    raise SystemExit(_main())
