"""Truth-free BTF-to-strict-polynomial proposal pipeline prototype."""

from __future__ import annotations

import ast
from dataclasses import dataclass
import itertools
import math
from pathlib import Path
import sys
import time
from typing import Callable, Mapping, Sequence


HERE = Path(__file__).resolve().parent
STRUCTURE_ROOT = HERE.parent / "EXP-STRUCT-001"
POLYNOMIAL_ROOT = HERE.parent / "EXP-POLY-001"
for dependency_root in (STRUCTURE_ROOT, POLYNOMIAL_ROOT):
    if str(dependency_root) not in sys.path:
        sys.path.insert(0, str(dependency_root))

from block_structure import BlockTriangularPlan, StructuralBlock, extract_v15_structure
from polynomial_side_route import (
    PolynomialLimits,
    PolynomialPlan,
    SymbolicAllocation,
    _bounded_candidates,
    allocate_symbolic_portfolio,
    detect_polynomial_plan,
)


@dataclass(frozen=True)
class BlockPolynomialGate:
    block_index: int
    relation_indices: tuple[int, ...]
    variable_indices: tuple[int, ...]
    formulation: Mapping[str, object]
    polynomial_plan: PolynomialPlan


@dataclass(frozen=True)
class BTFPolynomialPlan:
    applicable: bool
    reason: str
    structure_plan: BlockTriangularPlan | None
    variable_names: tuple[str, ...]
    block_gates: tuple[BlockPolynomialGate, ...]

    @property
    def active_blocks(self) -> tuple[BlockPolynomialGate, ...]:
        return tuple(gate for gate in self.block_gates if gate.polynomial_plan.applicable)


@dataclass(frozen=True)
class BTFPolynomialResult:
    plan: BTFPolynomialPlan
    allocation: SymbolicAllocation
    status: str
    proposals: tuple[tuple[float, ...], ...]
    verified: tuple[tuple[float, ...], ...]
    verifier_calls: int
    symbolic_elapsed_seconds: float


def _names(expression: str) -> set[str]:
    tree = ast.parse(expression, mode="eval")
    direct_calls = {
        node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }
    return {
        node.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Name) and node.id not in direct_calls
    }


def _needed_construction(
    formulation: Mapping[str, object], constraints: Sequence[Mapping[str, object]]
) -> list[Mapping[str, object]]:
    """Select exact source aliases needed by a block; perform no rewriting."""

    raw = formulation.get("construction", [])
    if not isinstance(raw, list):
        return []
    by_name = {
        binding.get("name"): binding
        for binding in raw
        if isinstance(binding, Mapping) and isinstance(binding.get("name"), str)
    }
    needed: set[str] = set()
    frontier: list[str] = []
    for constraint in constraints:
        for key in ("def", "value"):
            expression = constraint.get(key)
            if isinstance(expression, str):
                frontier.extend(_names(expression))
    while frontier:
        name = frontier.pop()
        if name in needed or name not in by_name:
            continue
        needed.add(name)
        expression = by_name[name].get("expr")
        if isinstance(expression, str):
            frontier.extend(_names(expression))
    # Source ordering is retained because aliases may depend on prior aliases.
    return [binding for binding in raw if isinstance(binding, Mapping) and binding.get("name") in needed]


def _project_block_formulation(
    formulation: Mapping[str, object],
    variable_names: Sequence[str],
    block: StructuralBlock,
) -> Mapping[str, object]:
    constraints_document = formulation.get("constraints")
    if not isinstance(constraints_document, list):
        raise ValueError("constraints must be a list")
    selected_constraints = []
    for index in block.relation_indices:
        constraint = constraints_document[index]
        if not isinstance(constraint, Mapping):
            raise ValueError("constraint must be an object")
        selected_constraints.append(dict(constraint))
    selected_names = [variable_names[index] for index in block.variable_indices]
    return {
        "task": "solve",
        "variables": {"names": selected_names},
        "construction": [
            dict(binding)
            for binding in _needed_construction(formulation, selected_constraints)
        ],
        "constraints": selected_constraints,
        # Guard semantics remain exclusively in the final canonical verifier.
        "guards": [],
    }


def detect_btf_polynomial_plan(
    formulation: Mapping[str, object],
    limits: PolynomialLimits = PolynomialLimits(),
) -> BTFPolynomialPlan:
    try:
        structure = extract_v15_structure(formulation)
    except (SyntaxError, TypeError, ValueError):
        return BTFPolynomialPlan(False, "structure_parse_failure", None, (), ())
    plan = structure.plan
    if not plan.applicable:
        return BTFPolynomialPlan(
            False, f"btf_{plan.reason}", plan, structure.variable_names, ()
        )
    gates: list[BlockPolynomialGate] = []
    try:
        for block_index, block in enumerate(plan.blocks):
            projected = _project_block_formulation(
                formulation, structure.variable_names, block
            )
            polynomial = detect_polynomial_plan(projected, limits)
            gates.append(
                BlockPolynomialGate(
                    block_index,
                    block.relation_indices,
                    block.variable_indices,
                    projected,
                    polynomial,
                )
            )
    except (SyntaxError, TypeError, ValueError):
        return BTFPolynomialPlan(
            False, "block_projection_failure", plan, structure.variable_names, ()
        )
    applicable = any(gate.polynomial_plan.applicable for gate in gates)
    return BTFPolynomialPlan(
        applicable,
        "strict_polynomial_block" if applicable else "no_strict_polynomial_block",
        plan,
        structure.variable_names,
        tuple(gates),
    )


def _allocation(
    total_starts: int, baseline_quota: float, active: bool
) -> SymbolicAllocation:
    proposed = allocate_symbolic_portfolio(total_starts, baseline_quota)
    if active:
        return proposed
    return SymbolicAllocation(total_starts, total_starts, 0)


def run_btf_polynomial_side_route(
    formulation: Mapping[str, object],
    template_point: Sequence[float],
    canonical_verifier: Callable[[Sequence[float]], bool],
    *,
    total_starts: int = 256,
    baseline_quota: float = 0.75,
    timeout_seconds: float = 1.0,
    maximum_symbolic_blocks: int = 4,
    maximum_cartesian_proposals: int = 32,
    limits: PolynomialLimits = PolynomialLimits(),
) -> BTFPolynomialResult:
    """Solve selected independent/substitutable blocks and verify full points.

    A block whose source still references predecessor variables fails the strict
    QQ gate.  Successful block roots replace coordinates in an existing
    numerical template.  Only the unchanged full-source verifier can accept a
    resulting point.
    """

    if not math.isfinite(timeout_seconds) or not 0.0 < timeout_seconds <= 2.0:
        raise ValueError("timeout_seconds must be in (0, 2]")
    if maximum_symbolic_blocks <= 0 or maximum_cartesian_proposals <= 0:
        raise ValueError("route caps must be positive")
    plan = detect_btf_polynomial_plan(formulation, limits)
    inactive = _allocation(total_starts, baseline_quota, False)
    if not plan.applicable:
        return BTFPolynomialResult(plan, inactive, "baseline_only", (), (), 0, 0.0)
    try:
        template = tuple(float(value) for value in template_point)
    except (TypeError, ValueError):
        return BTFPolynomialResult(plan, inactive, "invalid_template", (), (), 0, 0.0)
    if len(template) != len(plan.variable_names) or not all(map(math.isfinite, template)):
        return BTFPolynomialResult(plan, inactive, "invalid_template", (), (), 0, 0.0)

    active = plan.active_blocks
    if len(active) > maximum_symbolic_blocks:
        return BTFPolynomialResult(plan, inactive, "symbolic_block_cap", (), (), 0, 0.0)
    allocation = _allocation(total_starts, baseline_quota, True)
    started = time.monotonic()
    block_roots: list[tuple[BlockPolynomialGate, tuple[tuple[float, ...], ...]]] = []
    for offset, gate in enumerate(active):
        remaining = timeout_seconds - (time.monotonic() - started)
        # The reused worker may spend up to 250 ms collecting its queue result.
        # Reserve that envelope per remaining block, then enforce the total cap
        # again after every return.
        share = remaining / (len(active) - offset)
        if share <= 0.26:
            return BTFPolynomialResult(
                plan, inactive, "symbolic_timeout", (), (), 0, time.monotonic() - started
            )
        per_block = min(2.0, share - 0.25)
        try:
            status, roots, _elapsed = _bounded_candidates(
                gate.formulation, limits, per_block
            )
        except Exception:
            return BTFPolynomialResult(
                plan, inactive, "symbolic_worker_failure", (), (), 0, time.monotonic() - started
            )
        if time.monotonic() - started > timeout_seconds:
            return BTFPolynomialResult(
                plan, inactive, "symbolic_timeout", (), (), 0, time.monotonic() - started
            )
        if status != "complete" or not roots:
            return BTFPolynomialResult(
                plan, inactive, status, (), (), 0, time.monotonic() - started
            )
        block_roots.append((gate, roots))

    combinations = math.prod(len(roots) for _gate, roots in block_roots)
    if combinations > maximum_cartesian_proposals:
        return BTFPolynomialResult(
            plan, inactive, "cartesian_cap", (), (), 0, time.monotonic() - started
        )
    proposals: list[tuple[float, ...]] = []
    for roots in itertools.product(*(roots for _gate, roots in block_roots)):
        point = list(template)
        for (gate, _available), root in zip(block_roots, roots, strict=True):
            for variable_index, value in zip(gate.variable_indices, root, strict=True):
                point[variable_index] = value
        proposals.append(tuple(point))
    proposals = sorted(set(proposals))

    verified: list[tuple[float, ...]] = []
    verifier_calls = 0
    for proposal in proposals:
        verifier_calls += 1
        try:
            accepted = bool(canonical_verifier(proposal))
        except Exception:
            accepted = False
        if accepted:
            verified.append(proposal)
    return BTFPolynomialResult(
        plan,
        allocation,
        "complete",
        tuple(proposals),
        tuple(verified),
        verifier_calls,
        time.monotonic() - started,
    )
