"""Truth-blind block-triangular routing prototype for V15 residual systems.

This module is deliberately isolated from the production solver.  It consumes
only residual-to-variable structural support.  A block route may propose a
point, but only the caller-supplied canonical verifier can accept that point.
"""

from __future__ import annotations

import ast
import math
from dataclasses import dataclass
from typing import Callable, Iterable, Mapping, Sequence


@dataclass(frozen=True)
class StructuralBlock:
    relation_indices: tuple[int, ...]
    variable_indices: tuple[int, ...]
    predecessor_blocks: tuple[int, ...]


@dataclass(frozen=True)
class BlockTriangularPlan:
    variable_count: int
    relation_count: int
    relation_supports: tuple[tuple[int, ...], ...]
    relation_to_variable: tuple[int, ...]
    blocks: tuple[StructuralBlock, ...]
    applicable: bool
    reason: str

    @property
    def structural_nonzeros(self) -> int:
        return sum(map(len, self.relation_supports))

    @property
    def maximum_block_size(self) -> int:
        return max((len(block.variable_indices) for block in self.blocks), default=0)

    @property
    def dense_factor_work(self) -> int:
        return self.variable_count**3

    @property
    def block_factor_work(self) -> int:
        if not self.applicable:
            return self.dense_factor_work
        return sum(len(block.variable_indices) ** 3 for block in self.blocks)

    @property
    def factor_work_ratio(self) -> float:
        if not self.dense_factor_work:
            return 1.0
        return self.block_factor_work / self.dense_factor_work


@dataclass(frozen=True)
class PortfolioAllocation:
    total_starts: int
    baseline_starts: int
    block_starts: int


@dataclass(frozen=True)
class NumericalAttempt:
    point: tuple[float, ...]
    accepted: bool
    route: str
    residual_evaluations: int
    linear_work: int
    failure: str | None


@dataclass(frozen=True)
class V15Structure:
    variable_names: tuple[str, ...]
    relation_supports: tuple[tuple[int, ...], ...]
    guard_supports: tuple[tuple[int, ...], ...]
    plan: BlockTriangularPlan
    polynomial_scalar_candidate: bool


def _normalized_supports(
    relation_supports: Iterable[Iterable[int]], variable_count: int
) -> tuple[tuple[int, ...], ...]:
    if isinstance(variable_count, bool) or variable_count <= 0:
        raise ValueError("variable_count must be a positive integer")
    result: list[tuple[int, ...]] = []
    for support in relation_supports:
        normalized = tuple(sorted(set(support)))
        if any(isinstance(index, bool) or not isinstance(index, int) for index in normalized):
            raise TypeError("support indexes must be integers")
        if any(index < 0 or index >= variable_count for index in normalized):
            raise ValueError("support index outside variable range")
        result.append(normalized)
    return tuple(result)


def _perfect_matching(
    supports: tuple[tuple[int, ...], ...], variable_count: int
) -> tuple[int, ...] | None:
    """Return relation -> variable matching or ``None``.

    The augmenting-path order is deterministic.  Correctness and the resulting
    irreducible block partition do not depend on numerical values or case IDs.
    """

    variable_to_relation = [-1] * variable_count

    def augment(relation: int, seen: list[bool]) -> bool:
        for variable in supports[relation]:
            if seen[variable]:
                continue
            seen[variable] = True
            owner = variable_to_relation[variable]
            if owner == -1 or augment(owner, seen):
                variable_to_relation[variable] = relation
                return True
        return False

    for relation in range(len(supports)):
        if not augment(relation, [False] * variable_count):
            return None
    relation_to_variable = [-1] * len(supports)
    for variable, relation in enumerate(variable_to_relation):
        if relation >= 0:
            relation_to_variable[relation] = variable
    if any(variable < 0 for variable in relation_to_variable):
        return None
    return tuple(relation_to_variable)


def _strong_components(adjacency: Sequence[Sequence[int]]) -> tuple[tuple[int, ...], ...]:
    index = 0
    indexes = [-1] * len(adjacency)
    lowlinks = [0] * len(adjacency)
    stack: list[int] = []
    on_stack = [False] * len(adjacency)
    components: list[tuple[int, ...]] = []

    def visit(vertex: int) -> None:
        nonlocal index
        indexes[vertex] = lowlinks[vertex] = index
        index += 1
        stack.append(vertex)
        on_stack[vertex] = True
        for successor in adjacency[vertex]:
            if indexes[successor] < 0:
                visit(successor)
                lowlinks[vertex] = min(lowlinks[vertex], lowlinks[successor])
            elif on_stack[successor]:
                lowlinks[vertex] = min(lowlinks[vertex], indexes[successor])
        if lowlinks[vertex] != indexes[vertex]:
            return
        component: list[int] = []
        while True:
            member = stack.pop()
            on_stack[member] = False
            component.append(member)
            if member == vertex:
                break
        components.append(tuple(sorted(component)))

    for vertex in range(len(adjacency)):
        if indexes[vertex] < 0:
            visit(vertex)
    return tuple(components)


def _ordered_blocks(
    supports: tuple[tuple[int, ...], ...], matching: tuple[int, ...], variable_count: int
) -> tuple[StructuralBlock, ...]:
    adjacency_sets = [set() for _ in range(variable_count)]
    for relation, matched_variable in enumerate(matching):
        for dependency in supports[relation]:
            if dependency != matched_variable:
                adjacency_sets[dependency].add(matched_variable)
    adjacency = tuple(tuple(sorted(successors)) for successors in adjacency_sets)
    components = _strong_components(adjacency)
    component_of = {}
    for component_index, variables in enumerate(components):
        for variable in variables:
            component_of[variable] = component_index

    successors = [set() for _ in components]
    predecessors = [set() for _ in components]
    for variable, variable_successors in enumerate(adjacency):
        source = component_of[variable]
        for successor in variable_successors:
            destination = component_of[successor]
            if source != destination:
                successors[source].add(destination)
                predecessors[destination].add(source)

    # Stable Kahn ordering makes the result reproducible while retaining the
    # dependency order required by a staged solve.
    remaining_predecessors = [set(values) for values in predecessors]
    ready = sorted(
        (index for index, values in enumerate(remaining_predecessors) if not values),
        key=lambda item: components[item],
    )
    component_order: list[int] = []
    while ready:
        current = ready.pop(0)
        component_order.append(current)
        for successor in sorted(successors[current], key=lambda item: components[item]):
            remaining_predecessors[successor].discard(current)
            if not remaining_predecessors[successor] and successor not in component_order and successor not in ready:
                ready.append(successor)
        ready.sort(key=lambda item: components[item])
    if len(component_order) != len(components):
        raise AssertionError("SCC condensation graph unexpectedly contains a cycle")

    ordered_index = {component: index for index, component in enumerate(component_order)}
    relations_by_component: list[list[int]] = [[] for _ in components]
    for relation, variable in enumerate(matching):
        relations_by_component[component_of[variable]].append(relation)

    blocks: list[StructuralBlock] = []
    for component in component_order:
        block_predecessors = tuple(
            sorted(ordered_index[value] for value in predecessors[component])
        )
        blocks.append(
            StructuralBlock(
                tuple(sorted(relations_by_component[component])),
                components[component],
                block_predecessors,
            )
        )
    return tuple(blocks)


def analyze_relation_supports(
    relation_supports: Iterable[Iterable[int]], variable_count: int
) -> BlockTriangularPlan:
    supports = _normalized_supports(relation_supports, variable_count)
    if len(supports) != variable_count:
        return BlockTriangularPlan(
            variable_count, len(supports), supports, (), (), False, "non_square"
        )
    if any(not support for support in supports):
        return BlockTriangularPlan(
            variable_count, len(supports), supports, (), (), False, "constant_relation"
        )
    matching = _perfect_matching(supports, variable_count)
    if matching is None:
        return BlockTriangularPlan(
            variable_count, len(supports), supports, (), (), False, "no_perfect_matching"
        )
    blocks = _ordered_blocks(supports, matching, variable_count)
    if len(blocks) <= 1:
        return BlockTriangularPlan(
            variable_count, len(supports), supports, matching, blocks, False, "irreducible"
        )
    return BlockTriangularPlan(
        variable_count, len(supports), supports, matching, blocks, True, "decomposable"
    )


def allocate_portfolio(
    plan: BlockTriangularPlan, total_starts: int, baseline_quota: float = 0.5
) -> PortfolioAllocation:
    if isinstance(total_starts, bool) or total_starts <= 0:
        raise ValueError("total_starts must be a positive integer")
    if not math.isfinite(baseline_quota) or not 0.0 < baseline_quota <= 1.0:
        raise ValueError("baseline_quota must be in (0, 1]")
    if not plan.applicable:
        return PortfolioAllocation(total_starts, total_starts, 0)
    baseline = max(1, math.ceil(total_starts * baseline_quota))
    return PortfolioAllocation(total_starts, baseline, total_starts - baseline)


def _solve_linear(matrix: Sequence[Sequence[float]], rhs: Sequence[float]) -> list[float]:
    size = len(rhs)
    augmented = [list(map(float, matrix[row])) + [float(rhs[row])] for row in range(size)]
    for column in range(size):
        pivot = max(range(column, size), key=lambda row: abs(augmented[row][column]))
        if abs(augmented[pivot][column]) <= 1.0e-14:
            raise ArithmeticError("singular_jacobian")
        augmented[column], augmented[pivot] = augmented[pivot], augmented[column]
        scale = augmented[column][column]
        for index in range(column, size + 1):
            augmented[column][index] /= scale
        for row in range(size):
            if row == column:
                continue
            factor = augmented[row][column]
            for index in range(column, size + 1):
                augmented[row][index] -= factor * augmented[column][index]
    return [augmented[row][-1] for row in range(size)]


def _newton_subset(
    residual_fn: Callable[[Sequence[float]], Sequence[float]],
    point: list[float],
    relation_indices: Sequence[int],
    variable_indices: Sequence[int],
    *,
    tolerance: float,
    max_iterations: int,
) -> tuple[list[float], int, int, str | None]:
    evaluations = 0
    linear_work = 0

    def evaluate(candidate: Sequence[float]) -> list[float]:
        nonlocal evaluations
        values = tuple(float(value) for value in residual_fn(candidate))
        evaluations += 1
        if any(not math.isfinite(values[index]) for index in relation_indices):
            raise ArithmeticError("nonfinite_residual")
        return [values[index] for index in relation_indices]

    try:
        for _ in range(max_iterations):
            base = evaluate(point)
            norm = max(map(abs, base), default=0.0)
            if norm <= tolerance:
                return point, evaluations, linear_work, None
            jacobian = [[0.0 for _ in variable_indices] for _ in relation_indices]
            for column, variable in enumerate(variable_indices):
                step = math.sqrt(math.ulp(1.0)) * max(1.0, abs(point[variable]))
                perturbed = list(point)
                perturbed[variable] += step
                shifted = evaluate(perturbed)
                for row in range(len(relation_indices)):
                    jacobian[row][column] = (shifted[row] - base[row]) / step
            delta = _solve_linear(jacobian, [-value for value in base])
            linear_work += len(variable_indices) ** 3
            accepted = False
            damping = 1.0
            for _ in range(12):
                candidate = list(point)
                for column, variable in enumerate(variable_indices):
                    candidate[variable] += damping * delta[column]
                trial = evaluate(candidate)
                if max(map(abs, trial), default=0.0) < norm:
                    point = candidate
                    accepted = True
                    break
                damping *= 0.5
            if not accepted:
                return point, evaluations, linear_work, "no_progress"
        return point, evaluations, linear_work, "max_iterations"
    except (ArithmeticError, OverflowError, ValueError) as error:
        return point, evaluations, linear_work, str(error)


def solve_candidate(
    residual_fn: Callable[[Sequence[float]], Sequence[float]],
    start: Sequence[float],
    plan: BlockTriangularPlan,
    canonical_verifier: Callable[[Sequence[float]], bool],
    *,
    use_block_route: bool,
    tolerance: float = 1.0e-9,
    max_iterations: int = 30,
) -> NumericalAttempt:
    """Generate one candidate, then unconditionally replay canonical verification."""

    point = [float(value) for value in start]
    evaluations = 0
    linear_work = 0
    failure: str | None = None
    route = "baseline"
    if use_block_route and plan.applicable:
        route = "block"
        for block in plan.blocks:
            point, block_evaluations, block_work, failure = _newton_subset(
                residual_fn,
                point,
                block.relation_indices,
                block.variable_indices,
                tolerance=tolerance,
                max_iterations=max_iterations,
            )
            evaluations += block_evaluations
            linear_work += block_work
            if failure is not None:
                break
    else:
        relation_indices = tuple(range(plan.relation_count))
        variable_indices = tuple(range(plan.variable_count))
        point, evaluations, linear_work, failure = _newton_subset(
            residual_fn,
            point,
            relation_indices,
            variable_indices,
            tolerance=tolerance,
            max_iterations=max_iterations,
        )
    # A routing or local-solver result never has answer authority.
    accepted = bool(canonical_verifier(tuple(point)))
    if not accepted and failure is None:
        failure = "canonical_rejected"
    return NumericalAttempt(tuple(point), accepted, route, evaluations, linear_work, failure)


def _referenced_names(expression: str) -> set[str]:
    """Return value references, excluding direct DSL operation names.

    ``Point(A, x)`` depends on ``A`` and ``x``, not on the registry operation
    named ``Point``.  Unknown names in every other position fail closed in the
    caller instead of silently under-approximating the dependency graph.
    """

    tree = ast.parse(expression, mode="eval")
    direct_call_names = {
        node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }
    return {
        node.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Name) and node.id not in direct_call_names
    }


def _dependency_support(
    expression: str,
    dependencies: Mapping[str, set[int]],
    *,
    constants: frozenset[str] = frozenset(("pi", "e")),
) -> set[int]:
    support: set[int] = set()
    unknown: list[str] = []
    for symbol in _referenced_names(expression):
        if symbol in dependencies:
            support.update(dependencies[symbol])
        elif symbol not in constants:
            unknown.append(symbol)
    if unknown:
        raise ValueError("unknown value reference in formulation expression")
    return support


def _scalar_polynomial(expression: str, variables: set[str]) -> bool:
    try:
        tree = ast.parse(expression, mode="eval")
    except SyntaxError:
        return False

    def allowed(node: ast.AST) -> bool:
        if isinstance(node, ast.Expression):
            return allowed(node.body)
        if isinstance(node, ast.Constant):
            return isinstance(node.value, (int, float)) and not isinstance(node.value, bool)
        if isinstance(node, ast.Name):
            return node.id in variables
        if isinstance(node, ast.UnaryOp):
            return isinstance(node.op, (ast.UAdd, ast.USub)) and allowed(node.operand)
        if isinstance(node, ast.BinOp):
            if isinstance(node.op, (ast.Add, ast.Sub, ast.Mult)):
                return allowed(node.left) and allowed(node.right)
            if isinstance(node.op, ast.Pow):
                return (
                    allowed(node.left)
                    and isinstance(node.right, ast.Constant)
                    and isinstance(node.right.value, int)
                    and not isinstance(node.right.value, bool)
                    and node.right.value >= 0
                )
        return False

    return allowed(tree)


def extract_v15_structure(formulation: Mapping[str, object]) -> V15Structure:
    """Extract supports from a source formulation without reading answer fields."""

    variables_document = formulation.get("variables")
    if not isinstance(variables_document, Mapping):
        raise ValueError("variables must be an object")
    names_value = variables_document.get("names")
    if not isinstance(names_value, list) or not names_value:
        raise ValueError("variables.names must be a nonempty list")
    variable_names = tuple(str(name) for name in names_value)
    if len(set(variable_names)) != len(variable_names):
        raise ValueError("variable names must be unique")
    variable_indexes = {name: index for index, name in enumerate(variable_names)}
    dependencies: dict[str, set[int]] = {
        name: {index} for name, index in variable_indexes.items()
    }

    construction = formulation.get("construction", [])
    if not isinstance(construction, list):
        raise ValueError("construction must be a list")
    for binding in construction:
        if not isinstance(binding, Mapping):
            raise ValueError("construction binding must be an object")
        name = binding.get("name")
        expression = binding.get("expr")
        if not isinstance(name, str) or not isinstance(expression, str):
            raise ValueError("construction binding needs string name and expr")
        dependencies[name] = _dependency_support(expression, dependencies)

    constraints = formulation.get("constraints", [])
    if not isinstance(constraints, list):
        raise ValueError("constraints must be a list")
    relation_supports: list[tuple[int, ...]] = []
    polynomial = True
    scalar_variables = set(variable_names)
    for constraint in constraints:
        if not isinstance(constraint, Mapping):
            raise ValueError("constraint must be an object")
        expressions = []
        for key in ("def", "value"):
            value = constraint.get(key)
            if isinstance(value, str):
                expressions.append(value)
        support: set[int] = set()
        for expression in expressions:
            support.update(_dependency_support(expression, dependencies))
        relation_supports.append(tuple(sorted(support)))
        polynomial = polynomial and bool(expressions) and all(
            _scalar_polynomial(expression, scalar_variables) for expression in expressions
        )

    guards = formulation.get("guards", [])
    if not isinstance(guards, list):
        raise ValueError("guards must be a list")
    guard_supports: list[tuple[int, ...]] = []
    for guard in guards:
        if not isinstance(guard, str):
            raise ValueError("guard must be a string")
        support = _dependency_support(guard, dependencies)
        guard_supports.append(tuple(sorted(support)))

    plan = analyze_relation_supports(relation_supports, len(variable_names))
    return V15Structure(
        variable_names,
        tuple(relation_supports),
        tuple(guard_supports),
        plan,
        polynomial,
    )
