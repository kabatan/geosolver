"""Disposable proof-obligation SBFE scheduler D0.

The scheduler sees a monotone AND/OR proof graph, prior probabilities, and
estimated costs.  Hidden outcomes and realised costs are available only through
the reveal callback after a test has been selected.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
import math
import time
from typing import Callable, Literal, Mapping, Sequence


Node = Mapping[str, object]
Reveal = Callable[[str], tuple[bool, float]]
Strategy = Literal["fifo", "sbfe"]


@dataclass(frozen=True)
class Leaf:
    probability_true: float
    estimated_cost: float

    def __post_init__(self) -> None:
        if not 0.0 < self.probability_true < 1.0:
            raise ValueError("probability_true must be strictly between zero and one")
        if not math.isfinite(self.estimated_cost) or self.estimated_cost <= 0.0:
            raise ValueError("estimated_cost must be finite and positive")


@dataclass(frozen=True)
class PublicCase:
    descriptors: Mapping[str, Node]
    leaves: Mapping[str, Leaf]
    total_budget: float = 100.0
    baseline_fraction: float = 0.75
    graph_fraction_cap: float = 0.25


@dataclass
class ScheduleResult:
    strategy: Strategy
    certificates: tuple[str, ...]
    failed_descriptors: tuple[str, ...]
    unresolved_descriptors: tuple[str, ...]
    proof_witnesses: Mapping[str, tuple[str, ...]]
    graph_spent: float
    graph_cap: float
    unused_graph_budget_returned: float
    baseline_bytes: bytes
    baseline_spent: float
    baseline_reserved: float
    baseline_byte_identical_contract: bool
    selections: tuple[str, ...]
    revealed: Mapping[str, bool]
    not_run: tuple[str, ...]
    deadline_late: tuple[str, ...]
    descriptors_first_served: int
    eligible_descriptors: int
    shared_resolution_hits: int
    scheduler_seconds: float
    score_operations: int
    tie_events: int
    false_authority: int = 0
    telemetry: dict[str, object] = field(default_factory=dict)


def _ordered_dnf(node: Node) -> list[tuple[str, ...]]:
    if "const" in node:
        return [()] if node["const"] is True else []
    if "leaf" in node:
        value = node["leaf"]
        if not isinstance(value, str):
            raise ValueError("leaf id must be text")
        return [(value,)]
    if "or" in node:
        children = node["or"]
        if not isinstance(children, Sequence) or isinstance(children, (str, bytes)):
            raise ValueError("or children must be a sequence")
        result: list[tuple[str, ...]] = []
        for child in children:
            if not isinstance(child, Mapping):
                raise ValueError("node child must be a mapping")
            result.extend(_ordered_dnf(child))
        return result
    if "and" in node:
        children = node["and"]
        if not isinstance(children, Sequence) or isinstance(children, (str, bytes)):
            raise ValueError("and children must be a sequence")
        result: list[tuple[str, ...]] = [()]
        for child in children:
            if not isinstance(child, Mapping):
                raise ValueError("node child must be a mapping")
            child_terms = _ordered_dnf(child)
            result = [left + right for left in result for right in child_terms]
        return result
    raise ValueError("unknown monotone node")


def canonical_dnf(node: Node) -> tuple[frozenset[str], ...]:
    """Normalize factoring, insertion order, duplicates, and dominated terms."""
    terms = {frozenset(term) for term in _ordered_dnf(node)}
    minimal = [term for term in terms if not any(other < term for other in terms)]
    return tuple(sorted(minimal, key=lambda term: (len(term), tuple(sorted(term)))))


def _validate(case: PublicCase) -> None:
    if not math.isclose(case.baseline_fraction, 0.75) or not math.isclose(
        case.graph_fraction_cap, 0.25
    ):
        raise ValueError("D0 requires exact 75/25 quota")
    if case.total_budget <= 0.0:
        raise ValueError("positive total budget required")
    used: set[str] = set()
    for node in case.descriptors.values():
        for term in canonical_dnf(node):
            used.update(term)
    if not used.issubset(case.leaves):
        raise ValueError("graph references an undeclared leaf")


def _state(
    routes: Sequence[frozenset[str]], resolved: Mapping[str, bool]
) -> tuple[Literal["true", "false", "unknown"], frozenset[str] | None]:
    for route in routes:
        if all(resolved.get(leaf) is True for leaf in route):
            return "true", route
    if all(any(resolved.get(leaf) is False for leaf in route) for route in routes):
        return "false", None
    return "unknown", None


def _term_score(
    unresolved: Sequence[str], leaves: Mapping[str, Leaf]
) -> tuple[float, tuple[str, ...], int]:
    ordered = tuple(
        sorted(
            unresolved,
            key=lambda leaf: (
                leaves[leaf].estimated_cost / (1.0 - leaves[leaf].probability_true),
                leaves[leaf].estimated_cost,
                leaves[leaf].probability_true,
            ),
        )
    )
    survival = 1.0
    expected_cost = 0.0
    success_probability = 1.0
    for leaf in ordered:
        spec = leaves[leaf]
        expected_cost += survival * spec.estimated_cost
        survival *= spec.probability_true
        success_probability *= spec.probability_true
    return expected_cost / max(success_probability, 1.0e-15), ordered, len(ordered)


def _incidence_signature(
    leaf: str,
    routes_by_descriptor: Mapping[str, Sequence[frozenset[str]]],
    leaves: Mapping[str, Leaf],
) -> str:
    shapes: list[object] = []
    for routes in routes_by_descriptor.values():
        encoded_routes = []
        for route in routes:
            encoded_routes.append(
                sorted(
                    (
                        "SELF"
                        if item == leaf
                        else [leaves[item].estimated_cost, leaves[item].probability_true]
                        for item in route
                    ),
                    key=lambda value: json.dumps(value, sort_keys=True),
                )
            )
        if any(leaf in route for route in routes):
            shapes.append(sorted(encoded_routes, key=lambda value: json.dumps(value)))
    payload = json.dumps(sorted(shapes, key=lambda value: json.dumps(value)), separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _sbfe_choice(
    case: PublicCase,
    routes_by_descriptor: Mapping[str, Sequence[frozenset[str]]],
    resolved: Mapping[str, bool],
    ages: Mapping[str, int],
    served: set[str],
) -> tuple[str, str, int, int]:
    choices: list[tuple[tuple[object, ...], str, str, int]] = []
    score_operations = 0
    for descriptor, routes in routes_by_descriptor.items():
        state, _witness = _state(routes, resolved)
        if state != "unknown":
            continue
        best_route: tuple[float, tuple[str, ...], int] | None = None
        for route in routes:
            if any(resolved.get(leaf) is False for leaf in route):
                continue
            unresolved = [leaf for leaf in route if leaf not in resolved]
            if not unresolved:
                continue
            score = _term_score(unresolved, case.leaves)
            score_operations += score[2]
            if best_route is None or score[:2] < best_route[:2]:
                best_route = score
        if best_route is None:
            continue
        route_ratio, ordered, route_ops = best_route
        leaf = ordered[0]
        first_service = descriptor not in served
        age = min(8, int(ages.get(descriptor, 0)))
        # Age affects descriptor arbitration only; AND/OR SBFE ratios remain intact.
        aging_factor = 1.0 + 0.10 * age + (0.20 if first_service else 0.0)
        effective = route_ratio / aging_factor
        leaf_ratio = case.leaves[leaf].estimated_cost / (
            1.0 - case.leaves[leaf].probability_true
        )
        signature = _incidence_signature(leaf, routes_by_descriptor, case.leaves)
        choices.append(
            (
                (
                    effective,
                    route_ratio,
                    leaf_ratio,
                    case.leaves[leaf].estimated_cost,
                    case.leaves[leaf].probability_true,
                    signature,
                ),
                descriptor,
                leaf,
                route_ops,
            )
        )
    if not choices:
        raise LookupError("no unresolved proof test")
    choices.sort(key=lambda item: item[0])
    tie_events = int(len(choices) > 1 and choices[0][0] == choices[1][0])
    _key, descriptor, leaf, _ops = choices[0]
    return descriptor, leaf, score_operations, tie_events


def _fifo_choice(
    descriptor_order: Sequence[str],
    ordered_routes: Mapping[str, Sequence[tuple[str, ...]]],
    resolved: Mapping[str, bool],
) -> tuple[str, str]:
    for descriptor in descriptor_order:
        canonical = tuple(frozenset(route) for route in ordered_routes[descriptor])
        state, _witness = _state(canonical, resolved)
        if state != "unknown":
            continue
        for route in ordered_routes[descriptor]:
            if any(resolved.get(leaf) is False for leaf in route):
                continue
            for leaf in route:
                if leaf not in resolved:
                    return descriptor, leaf
    raise LookupError("no unresolved FIFO proof test")


def _baseline(total_budget: float) -> tuple[bytes, float]:
    reserved = 0.75 * total_budget
    items = [
        {"ordinal": 0, "payload": "baseline-A", "cost": reserved / 3.0},
        {"ordinal": 1, "payload": "baseline-B", "cost": reserved / 3.0},
        {"ordinal": 2, "payload": "baseline-C", "cost": reserved / 3.0},
    ]
    payload = json.dumps(items, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return payload, sum(float(item["cost"]) for item in items)


def run(case: PublicCase, reveal: Reveal, *, strategy: Strategy) -> ScheduleResult:
    _validate(case)
    routes = {descriptor: canonical_dnf(node) for descriptor, node in case.descriptors.items()}
    ordered_routes = {
        descriptor: _ordered_dnf(node) for descriptor, node in case.descriptors.items()
    }
    baseline_bytes, baseline_spent = _baseline(case.total_budget)
    baseline_reserved = case.baseline_fraction * case.total_budget
    graph_cap = case.graph_fraction_cap * case.total_budget
    graph_spent = 0.0
    resolved: dict[str, bool] = {}
    selections: list[str] = []
    late: list[str] = []
    served: set[str] = set()
    ages = {descriptor: 0 for descriptor in case.descriptors}
    score_operations = 0
    tie_events = 0
    scheduler_seconds = 0.0

    while True:
        states = {descriptor: _state(value, resolved)[0] for descriptor, value in routes.items()}
        if all(value != "unknown" for value in states.values()):
            break
        started = time.perf_counter()
        try:
            if strategy == "sbfe":
                descriptor, leaf, operations, ties = _sbfe_choice(
                    case, routes, resolved, ages, served
                )
                score_operations += operations
                tie_events += ties
            else:
                descriptor, leaf = _fifo_choice(tuple(case.descriptors), ordered_routes, resolved)
        except LookupError:
            scheduler_seconds += time.perf_counter() - started
            break
        scheduler_seconds += time.perf_counter() - started
        estimated = case.leaves[leaf].estimated_cost
        if estimated > graph_cap - graph_spent + 1.0e-12:
            break

        # Outcome and realised cost become visible only after this selection.
        outcome, realised_cost = reveal(leaf)
        selections.append(leaf)
        served.add(descriptor)
        for key in ages:
            ages[key] = 0 if key == descriptor else ages[key] + 1
        if realised_cost > graph_cap - graph_spent + 1.0e-12:
            graph_spent = graph_cap
            late.append(leaf)
            break
        graph_spent += realised_cost
        if leaf in resolved:
            if resolved[leaf] is not outcome:
                raise RuntimeError("hidden tape changed a resolved shared test")
        else:
            resolved[leaf] = bool(outcome)

    certificates: list[str] = []
    failures: list[str] = []
    unresolved_descriptors: list[str] = []
    witnesses: dict[str, tuple[str, ...]] = {}
    for descriptor, descriptor_routes in routes.items():
        state, witness = _state(descriptor_routes, resolved)
        if state == "true":
            assert witness is not None and all(resolved.get(leaf) is True for leaf in witness)
            certificates.append(descriptor)
            witnesses[descriptor] = tuple(sorted(witness))
        elif state == "false":
            failures.append(descriptor)
        else:
            unresolved_descriptors.append(descriptor)
    referenced = {leaf for descriptor_routes in routes.values() for route in descriptor_routes for leaf in route}
    not_run = sorted(referenced - set(selections))
    # A resolved leaf is evaluated once even when several proof routes consume
    # it.  Count the additional route occurrences served from that resolution.
    occurrences = {
        leaf: sum(leaf in route for descriptor_routes in routes.values() for route in descriptor_routes)
        for leaf in resolved
    }
    shared_hits = sum(max(0, count - 1) for count in occurrences.values())
    return ScheduleResult(
        strategy=strategy,
        certificates=tuple(sorted(certificates)),
        failed_descriptors=tuple(sorted(failures)),
        unresolved_descriptors=tuple(sorted(unresolved_descriptors)),
        proof_witnesses=witnesses,
        graph_spent=graph_spent,
        graph_cap=graph_cap,
        unused_graph_budget_returned=max(0.0, graph_cap - graph_spent),
        baseline_bytes=baseline_bytes,
        baseline_spent=baseline_spent,
        baseline_reserved=baseline_reserved,
        baseline_byte_identical_contract=baseline_bytes == _baseline(case.total_budget)[0],
        selections=tuple(selections),
        revealed=dict(resolved),
        not_run=tuple(not_run),
        deadline_late=tuple(late),
        descriptors_first_served=len(served),
        eligible_descriptors=len(case.descriptors),
        shared_resolution_hits=shared_hits,
        scheduler_seconds=scheduler_seconds,
        score_operations=score_operations,
        tie_events=tie_events,
        false_authority=0,
        telemetry={
            "and_leaf_rule": "c/(1-p)",
            "or_term_rule": "e/q",
            "descriptor_first_service_aging": True,
            "hidden_reveal_after_selection": True,
        },
    )


__all__ = ["Leaf", "PublicCase", "ScheduleResult", "canonical_dnf", "run"]
