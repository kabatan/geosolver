"""Conservative joint-affinity proof over the existing typed source DAG.

The three abstract values mean independent of the selected inner block,
jointly affine in that block, and not proved affine.  The rules are
syntax-directed.  Cancellation and branch identities are deliberately not
used, so an unsupported or ambiguous operation fails closed.
"""

from __future__ import annotations

from collections import Counter
from itertools import combinations
from typing import Iterable, Sequence


CONSTANT = 0
AFFINE = 1
NONLINEAR = 2


def _add(classes: Iterable[int]) -> int:
    return max(classes, default=CONSTANT)


def _multiply(left: int, right: int) -> int:
    if NONLINEAR in (left, right) or left == right == AFFINE:
        return NONLINEAR
    return max(left, right)


def _divide(numerator: int, denominator: int) -> int:
    if denominator != CONSTANT or numerator == NONLINEAR:
        return NONLINEAR
    return numerator


def _scalar_class(operation: str, inputs: Sequence[int], payload: object) -> int:
    if operation == "constant":
        return CONSTANT
    if operation in {"add", "sub"}:
        return _add(inputs)
    if operation == "mul":
        return _multiply(inputs[0], inputs[1])
    if operation == "div":
        return _divide(inputs[0], inputs[1])
    if operation == "neg":
        return inputs[0]
    if operation == "integer_power":
        exponent = int(payload)
        if exponent == 0:
            return CONSTANT
        if exponent == 1:
            return inputs[0]
        return CONSTANT if inputs[0] == CONSTANT else NONLINEAR
    if operation in {"sqrt", "abs", "sin", "cos", "distance"}:
        return CONSTANT if all(item == CONSTANT for item in inputs) else NONLINEAR
    if operation == "attribute":
        return inputs[0]
    if operation == "dot":
        return _multiply(inputs[0], inputs[1])
    if operation == "area":
        dependent = sum(item != CONSTANT for item in inputs)
        if dependent == 0:
            return CONSTANT
        if dependent == 1 and all(item != NONLINEAR for item in inputs):
            return AFFINE
        return NONLINEAR
    return CONSTANT if all(item == CONSTANT for item in inputs) else NONLINEAR


def residual_affinity(program: object, inner: Sequence[int]) -> tuple[int, ...]:
    """Prove each residual constant/affine/nonlinear for one inner block."""

    selected = frozenset(int(item) for item in inner)
    values: list[int] = []
    for node in program.nodes:
        operation = str(node.op)
        if operation == "variable":
            values.append(AFFINE if int(node.payload) in selected else CONSTANT)
            continue
        inputs = tuple(values[index] for index in node.inputs)
        if node.sort == "scalar":
            output = _scalar_class(operation, inputs, node.payload)
        elif operation in {
            "point",
            "circle",
            "point_add",
            "point_sub",
            "point_neg",
            "midpoint_points",
            "midpoint_circle",
        }:
            output = _add(inputs)
        elif operation == "point_scale":
            output = _multiply(inputs[0], inputs[1])
        elif operation == "point_div":
            output = _divide(inputs[0], inputs[1])
        elif operation in {"line_points", "circle_through_point"}:
            output = CONSTANT if all(item == CONSTANT for item in inputs) else NONLINEAR
        elif operation == "line_coefficients":
            if all(item == CONSTANT for item in inputs):
                output = CONSTANT
            elif inputs[0] == inputs[1] == CONSTANT and inputs[2] == AFFINE:
                output = AFFINE
            else:
                output = NONLINEAR
        elif operation == "point_on_segment":
            first, second, parameter = inputs
            if first == second == parameter == CONSTANT:
                output = CONSTANT
            elif parameter == CONSTANT and first != NONLINEAR and second != NONLINEAR:
                output = _add((first, second))
            elif first == second == CONSTANT and parameter == AFFINE:
                output = AFFINE
            else:
                output = NONLINEAR
        elif operation == "point_on_line":
            line, parameter = inputs
            if line == parameter == CONSTANT:
                output = CONSTANT
            elif line == CONSTANT and parameter == AFFINE:
                output = AFFINE
            else:
                output = NONLINEAR
        elif operation == "point_on_circle":
            circle, parameter = inputs
            if circle == parameter == CONSTANT:
                output = CONSTANT
            elif parameter == CONSTANT and circle == AFFINE:
                output = AFFINE
            else:
                output = NONLINEAR
        elif operation in {"foot", "parallelline", "perpendicularline"}:
            sorts = tuple(node.payload)
            line_position = 0 if sorts[0] == "line" else 1
            if all(item == CONSTANT for item in inputs):
                output = CONSTANT
            elif inputs[line_position] == CONSTANT and all(
                item != NONLINEAR for item in inputs
            ):
                output = AFFINE
            else:
                output = NONLINEAR
        elif operation == "rotate":
            point, angle, center = inputs
            if all(item == CONSTANT for item in inputs):
                output = CONSTANT
            elif angle == CONSTANT and point != NONLINEAR and center != NONLINEAR:
                output = AFFINE
            else:
                output = NONLINEAR
        elif operation == "reflect":
            sorts = tuple(node.payload)
            if all(item == CONSTANT for item in inputs):
                output = CONSTANT
            elif sorts == ("point", "point") and all(
                item != NONLINEAR for item in inputs
            ):
                output = AFFINE
            elif sorts == ("point", "line") and inputs[1] == CONSTANT and inputs[0] != NONLINEAR:
                output = AFFINE
            else:
                output = NONLINEAR
        else:
            output = CONSTANT if all(item == CONSTANT for item in inputs) else NONLINEAR
        values.append(output)
    return tuple(values[index] for index in program.residual_outputs)


def _has_structural_matching(
    support: Sequence[frozenset[int]], affected_rows: Sequence[int], inner: Sequence[int]
) -> bool:
    matching = [-1] * len(affected_rows)

    def augment(inner_position: int, seen: set[int]) -> bool:
        variable = inner[inner_position]
        for local_row, source_row in enumerate(affected_rows):
            if local_row in seen or variable not in support[source_row]:
                continue
            seen.add(local_row)
            if matching[local_row] < 0 or augment(matching[local_row], seen):
                matching[local_row] = inner_position
                return True
        return False

    return all(augment(position, set()) for position in range(len(inner)))


def find_affine_blocks(program: object, maximum_inner_dimension: int = 4) -> tuple[tuple[object, ...], ...]:
    """Return anonymous source-graph signatures for certified affine blocks.

    This proves affinity and a full structural matching only.  A numeric rank,
    condition, guard, branch and derivative-agreement check is still required
    before a future runtime connector may activate.
    """

    support = tuple(program.nodes[index].support for index in program.residual_outputs)
    plans: list[tuple[object, ...]] = []
    maximum = min(int(maximum_inner_dimension), int(program.dimension))
    for size in range(1, maximum + 1):
        for inner in combinations(range(program.dimension), size):
            selected = frozenset(inner)
            affected = tuple(
                row for row, row_support in enumerate(support) if row_support & selected
            )
            if len(affected) < size:
                continue
            affinity = residual_affinity(program, inner)
            if any(affinity[row] != AFFINE for row in affected):
                continue
            if not _has_structural_matching(support, affected, inner):
                continue
            inner_degree_histogram = tuple(
                sorted(Counter(len(row_support & selected) for row_support in support if row_support & selected).items())
            )
            outer_degree_histogram = tuple(
                sorted(Counter(len(row_support - selected) for row_support in support if row_support & selected).items())
            )
            plans.append(
                (
                    int(program.dimension),
                    int(program.residual_dimension),
                    size,
                    len(affected),
                    inner_degree_histogram,
                    outer_degree_histogram,
                )
            )
    return tuple(plans)


__all__ = [
    "AFFINE",
    "CONSTANT",
    "NONLINEAR",
    "find_affine_blocks",
    "residual_affinity",
]
