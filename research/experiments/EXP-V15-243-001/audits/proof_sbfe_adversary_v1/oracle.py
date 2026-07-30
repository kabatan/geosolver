#!/usr/bin/env python3
"""Candidate-independent oracle for a fixed proof-SBFE counterexample corpus."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from copy import deepcopy
import math
from typing import Any


Node = Mapping[str, object]


def _ordered_dnf(node: Node) -> list[tuple[str, ...]]:
    if "const" in node:
        return [()] if node["const"] is True else []
    if "leaf" in node:
        leaf = node["leaf"]
        if not isinstance(leaf, str):
            raise ValueError("leaf id must be text")
        return [(leaf,)]
    if "or" in node:
        children = node["or"]
        if not isinstance(children, Sequence) or isinstance(children, (str, bytes)):
            raise ValueError("or children must be a sequence")
        answer: list[tuple[str, ...]] = []
        for child in children:
            if not isinstance(child, Mapping):
                raise ValueError("node child must be a mapping")
            answer.extend(_ordered_dnf(child))
        return answer
    if "and" in node:
        children = node["and"]
        if not isinstance(children, Sequence) or isinstance(children, (str, bytes)):
            raise ValueError("and children must be a sequence")
        answer = [()]
        for child in children:
            if not isinstance(child, Mapping):
                raise ValueError("node child must be a mapping")
            terms = _ordered_dnf(child)
            answer = [left + right for left in answer for right in terms]
        return answer
    raise ValueError("unknown monotone node")


def canonical_dnf(node: Node) -> tuple[frozenset[str], ...]:
    terms = {frozenset(term) for term in _ordered_dnf(node)}
    minimal = [term for term in terms if not any(other < term for other in terms)]
    return tuple(sorted(minimal, key=lambda term: (len(term), tuple(sorted(term)))))


def _state(
    routes: Sequence[frozenset[str]], resolved: Mapping[str, bool]
) -> tuple[str, frozenset[str] | None]:
    for route in routes:
        if all(resolved.get(leaf) is True for leaf in route):
            return "true", route
    if all(any(resolved.get(leaf) is False for leaf in route) for route in routes):
        return "false", None
    return "unknown", None


def _case(
    descriptors: Mapping[str, Node],
    leaves: Mapping[str, tuple[float, float]],
    tape: Mapping[str, tuple[bool, float]],
) -> dict[str, Any]:
    return {
        "total_budget": 100.0,
        "baseline_fraction": 0.75,
        "graph_fraction_cap": 0.25,
        "descriptors": deepcopy(dict(descriptors)),
        "leaves": {
            name: {"probability_true": probability, "estimated_cost": cost}
            for name, (probability, cost) in leaves.items()
        },
        "tape": {
            name: {"outcome": outcome, "actual_cost": cost}
            for name, (outcome, cost) in tape.items()
        },
    }


HIDDEN_PUBLIC = _case(
    {
        "target": {
            "or": [
                {"and": [{"leaf": "a"}, {"leaf": "b"}]},
                {"leaf": "c"},
            ]
        }
    },
    {"a": (0.8, 1.0), "b": (0.8, 2.0), "c": (0.95, 20.0)},
    {"a": (True, 1.0), "b": (True, 2.0), "c": (False, 20.0)},
)
HIDDEN_LEFT = deepcopy(HIDDEN_PUBLIC)
HIDDEN_RIGHT = deepcopy(HIDDEN_PUBLIC)
HIDDEN_RIGHT["tape"]["b"] = {"outcome": False, "actual_cost": 3.0}
HIDDEN_RIGHT["tape"]["c"] = {"outcome": True, "actual_cost": 19.0}

FACTOR_EXPANDED = _case(
    {
        "factor": {
            "or": [
                {"and": [{"leaf": "s"}, {"leaf": "a"}]},
                {"and": [{"leaf": "s"}, {"leaf": "b"}]},
            ]
        }
    },
    {"s": (0.85, 1.0), "a": (0.70, 2.0), "b": (0.40, 1.5)},
    {"s": (True, 1.0), "a": (False, 2.0), "b": (True, 1.5)},
)
FACTOR_FACTORED = deepcopy(FACTOR_EXPANDED)
FACTOR_FACTORED["descriptors"] = {
    "factor": {
        "and": [
            {"leaf": "s"},
            {"or": [{"leaf": "a"}, {"leaf": "b"}]},
        ]
    }
}

SHARED = _case(
    {
        "first": {"and": [{"leaf": "s"}, {"leaf": "a"}]},
        "second": {"and": [{"leaf": "s"}, {"leaf": "b"}]},
    },
    {"s": (0.8, 0.5), "a": (0.7, 2.0), "b": (0.6, 3.0)},
    {"s": (True, 0.5), "a": (True, 2.0), "b": (True, 3.0)},
)

TERMINAL_TRUE = _case(
    {
        "done": {
            "or": [
                {"leaf": "a"},
                {"and": [{"leaf": "b"}, {"leaf": "c"}]},
            ]
        }
    },
    {"a": (0.9, 0.5), "b": (0.8, 5.0), "c": (0.8, 5.0)},
    {"a": (True, 0.5), "b": (True, 5.0), "c": (True, 5.0)},
)

TERMINAL_FALSE = _case(
    {"done": {"and": [{"leaf": "a"}, {"leaf": "b"}]}},
    {"a": (0.1, 0.5), "b": (0.9, 5.0)},
    {"a": (False, 0.5), "b": (True, 5.0)},
)

BASELINE_QUOTA = _case(
    {
        "one": {"leaf": "a"},
        "two": {"leaf": "b"},
        "three": {"leaf": "c"},
    },
    {"a": (0.5, 10.0), "b": (0.6, 10.0), "c": (0.7, 10.0)},
    {"a": (True, 10.0), "b": (True, 10.0), "c": (True, 10.0)},
)

DEADLINE_PARTIAL = _case(
    {"partial": {"and": [{"leaf": "a"}, {"leaf": "b"}]}},
    {"a": (0.5, 5.0), "b": (0.9, 10.0)},
    {"a": (True, 10.0), "b": (True, 20.0)},
)

PERMUTATION_BASE = _case(
    {
        "first": {
            "or": [
                {"and": [{"leaf": "s"}, {"leaf": "a"}]},
                {"leaf": "z"},
            ]
        },
        "second": {"and": [{"leaf": "s"}, {"leaf": "b"}]},
    },
    {"s": (0.8, 1.0), "a": (0.7, 2.0), "z": (0.5, 4.0), "b": (0.6, 3.0)},
    {"s": (True, 1.0), "a": (False, 2.0), "z": (True, 4.0), "b": (True, 3.0)},
)

LEAF_RENAME = {"s": "zz", "a": "middle", "z": "aa", "b": "q"}
DESCRIPTOR_RENAME = {"first": "omega", "second": "beta"}
PERMUTATION_VARIANT = _case(
    {
        "beta": {"and": [{"leaf": "q"}, {"leaf": "zz"}]},
        "omega": {
            "or": [
                {"leaf": "aa"},
                {"and": [{"leaf": "middle"}, {"leaf": "zz"}]},
            ]
        },
    },
    {
        "zz": (0.8, 1.0),
        "middle": (0.7, 2.0),
        "aa": (0.5, 4.0),
        "q": (0.6, 3.0),
    },
    {
        "zz": (True, 1.0),
        "middle": (False, 2.0),
        "aa": (True, 4.0),
        "q": (True, 3.0),
    },
)

FIXED_RUNS = {
    "hidden-left": HIDDEN_LEFT,
    "hidden-right": HIDDEN_RIGHT,
    "factor-expanded": FACTOR_EXPANDED,
    "factor-factored": FACTOR_FACTORED,
    "shared-once": SHARED,
    "terminal-true": TERMINAL_TRUE,
    "terminal-false": TERMINAL_FALSE,
    "baseline-75": BASELINE_QUOTA,
    "deadline-partial": DEADLINE_PARTIAL,
    "permutation-base": PERMUTATION_BASE,
    "permutation-variant": PERMUTATION_VARIANT,
}


def validate_observation(
    name: str,
    case: Mapping[str, Any],
    observation: Mapping[str, Any],
) -> list[str]:
    failures: list[str] = []
    descriptors = case["descriptors"]
    tape = case["tape"]
    routes = {key: canonical_dnf(node) for key, node in descriptors.items()}
    referenced = {
        leaf for descriptor_routes in routes.values() for route in descriptor_routes for leaf in route
    }
    selections = tuple(observation.get("selections", ()))
    reveal_calls = tuple(observation.get("reveal_calls", ()))
    late = tuple(observation.get("deadline_late", ()))
    revealed = dict(observation.get("revealed", {}))

    if selections != reveal_calls:
        failures.append(f"{name}:selection/reveal callback trace mismatch")
    if len(selections) != len(set(selections)):
        failures.append(f"{name}:shared leaf selected or charged twice")
    if any(leaf not in referenced for leaf in selections):
        failures.append(f"{name}:selected undeclared or irrelevant leaf")
    if any(leaf in revealed for leaf in late):
        failures.append(f"{name}:deadline-late outcome entered revealed state")
    if late and selections[-len(late) :] != late:
        failures.append(f"{name}:selection continued after deadline-late leaf")

    prefix: dict[str, bool] = {}
    for index, leaf in enumerate(selections):
        if leaf in prefix:
            continue
        relevant = False
        for descriptor_routes in routes.values():
            state, _witness = _state(descriptor_routes, prefix)
            if state != "unknown":
                continue
            for route in descriptor_routes:
                if leaf in route and not any(prefix.get(item) is False for item in route):
                    relevant = True
                    break
            if relevant:
                break
        if not relevant:
            failures.append(f"{name}:terminal route resurrected at selection {index}")
        if leaf not in late:
            prefix[leaf] = bool(tape[leaf]["outcome"])
    if prefix != revealed:
        failures.append(f"{name}:revealed map differs from causal replay prefix")

    expected_true: set[str] = set()
    expected_false: set[str] = set()
    expected_unknown: set[str] = set()
    for descriptor, descriptor_routes in routes.items():
        state, _witness = _state(descriptor_routes, revealed)
        if state == "true":
            expected_true.add(descriptor)
        elif state == "false":
            expected_false.add(descriptor)
        else:
            expected_unknown.add(descriptor)
    certificates = set(observation.get("certificates", ()))
    failed = set(observation.get("failed_descriptors", ()))
    unresolved = set(observation.get("unresolved_descriptors", ()))
    if certificates != expected_true:
        failures.append(f"{name}:certificate set is not exact for revealed state")
    if failed != expected_false:
        failures.append(f"{name}:failure set is not exact for revealed state")
    if unresolved != expected_unknown:
        failures.append(f"{name}:unresolved set is not exact for revealed state")

    witnesses = observation.get("proof_witnesses", {})
    for descriptor in certificates:
        witness = frozenset(witnesses.get(descriptor, ()))
        if witness not in routes[descriptor] or not all(
            revealed.get(leaf) is True for leaf in witness
        ):
            failures.append(f"{name}:{descriptor}:invalid proof witness")
    if set(witnesses) != certificates:
        failures.append(f"{name}:witness keys differ from certificates")

    graph_cap = float(observation.get("graph_cap", math.nan))
    graph_spent = float(observation.get("graph_spent", math.nan))
    baseline_reserved = float(observation.get("baseline_reserved", math.nan))
    baseline_spent = float(observation.get("baseline_spent", math.nan))
    total = float(case["total_budget"])
    expected_cap = total * float(case["graph_fraction_cap"])
    expected_baseline = total * float(case["baseline_fraction"])
    if not math.isclose(graph_cap, expected_cap):
        failures.append(f"{name}:graph cap is not 25%")
    if not math.isclose(baseline_reserved, expected_baseline):
        failures.append(f"{name}:baseline reservation is not 75%")
    if not math.isclose(baseline_spent, expected_baseline):
        failures.append(f"{name}:baseline spend is not 75%")
    if graph_spent < -1.0e-12 or graph_spent > graph_cap + 1.0e-12:
        failures.append(f"{name}:graph accounting exceeded cap")
    if baseline_spent + graph_spent > total + 1.0e-12:
        failures.append(f"{name}:graph lane starved baseline quota")
    actual_sum = sum(float(tape[leaf]["actual_cost"]) for leaf in selections)
    expected_spent = min(graph_cap, actual_sum)
    if not math.isclose(graph_spent, expected_spent):
        failures.append(f"{name}:shared/late graph cost accounting mismatch")
    if observation.get("baseline_byte_identical_contract") is not True:
        failures.append(f"{name}:baseline byte identity contract failed")
    if int(observation.get("false_authority", -1)) != 0:
        failures.append(f"{name}:candidate reported false authority")
    expected_not_run = tuple(sorted(referenced - set(selections)))
    if tuple(observation.get("not_run", ())) != expected_not_run:
        failures.append(f"{name}:not_run set mismatch")
    return failures


def _normalized(observation: Mapping[str, Any], leaf_inverse=None, descriptor_inverse=None):
    leaf_inverse = leaf_inverse or (lambda value: value)
    descriptor_inverse = descriptor_inverse or (lambda value: value)
    return {
        "certificates": tuple(sorted(descriptor_inverse(x) for x in observation["certificates"])),
        "failed": tuple(sorted(descriptor_inverse(x) for x in observation["failed_descriptors"])),
        "unresolved": tuple(
            sorted(descriptor_inverse(x) for x in observation["unresolved_descriptors"])
        ),
        "witnesses": {
            descriptor_inverse(key): tuple(sorted(leaf_inverse(x) for x in value))
            for key, value in observation["proof_witnesses"].items()
        },
        "selections": tuple(leaf_inverse(x) for x in observation["selections"]),
        "revealed": {
            leaf_inverse(key): value for key, value in observation["revealed"].items()
        },
        "not_run": tuple(sorted(leaf_inverse(x) for x in observation["not_run"])),
        "deadline_late": tuple(leaf_inverse(x) for x in observation["deadline_late"]),
        "graph_spent": observation["graph_spent"],
        "graph_cap": observation["graph_cap"],
        "baseline_spent": observation["baseline_spent"],
        "baseline_reserved": observation["baseline_reserved"],
        "baseline_sha256": observation["baseline_sha256"],
    }


def validate_relations(observations: Mapping[str, Mapping[str, Any]]) -> list[str]:
    failures: list[str] = []
    hidden_left = observations["hidden-left"]
    hidden_right = observations["hidden-right"]
    if tuple(hidden_left["selections"][:2]) != tuple(hidden_right["selections"][:2]):
        failures.append("hidden-future:selection prefix depends on unrevealed tape")
    if tuple(hidden_left["selections"][:2]) != ("a", "b"):
        failures.append("hidden-future:frozen public SBFE prefix changed")

    expanded = _normalized(observations["factor-expanded"])
    factored = _normalized(observations["factor-factored"])
    if expanded != factored:
        failures.append("equivalent-factoring:normalized execution changed")

    shared = observations["shared-once"]
    if tuple(shared["selections"]).count("s") != 1:
        failures.append("shared-node:shared leaf was not evaluated exactly once")
    if set(shared["certificates"]) != {"first", "second"}:
        failures.append("shared-node:both consumers did not reuse shared resolution")

    if tuple(observations["terminal-true"]["selections"]) != ("a",):
        failures.append("terminal-true:dead alternate route was resurrected")
    if tuple(observations["terminal-false"]["selections"]) != ("a",):
        failures.append("terminal-false:dead conjunction tail was resurrected")

    deadline = observations["deadline-partial"]
    if set(deadline["certificates"]):
        failures.append("deadline-partial:late leaf completed a certificate")
    if tuple(deadline["deadline_late"]) != ("b",):
        failures.append("deadline-partial:frozen late-leaf trace changed")
    if set(deadline["revealed"]) != {"a"}:
        failures.append("deadline-partial:late outcome leaked into proof state")

    leaf_inverse_map = {value: key for key, value in LEAF_RENAME.items()}
    descriptor_inverse_map = {value: key for key, value in DESCRIPTOR_RENAME.items()}
    base = _normalized(observations["permutation-base"])
    variant = _normalized(
        observations["permutation-variant"],
        leaf_inverse=lambda value: leaf_inverse_map[value],
        descriptor_inverse=lambda value: descriptor_inverse_map[value],
    )
    if base != variant:
        failures.append("id-insertion-permutation:normalized execution changed")

    baseline_hashes = {value["baseline_sha256"] for value in observations.values()}
    if len(baseline_hashes) != 1:
        failures.append("baseline-75:baseline bytes changed with graph/tape representation")
    return failures


def self_test() -> dict[str, Any]:
    assert canonical_dnf(FACTOR_EXPANDED["descriptors"]["factor"]) == canonical_dnf(
        FACTOR_FACTORED["descriptors"]["factor"]
    )
    compliant = {
        "selections": ("s", "a", "b"),
        "reveal_calls": ("s", "a", "b"),
        "revealed": {"s": True, "a": True, "b": True},
        "deadline_late": (),
        "certificates": ("first", "second"),
        "failed_descriptors": (),
        "unresolved_descriptors": (),
        "proof_witnesses": {"first": ("a", "s"), "second": ("b", "s")},
        "graph_spent": 5.5,
        "graph_cap": 25.0,
        "baseline_spent": 75.0,
        "baseline_reserved": 75.0,
        "baseline_byte_identical_contract": True,
        "baseline_sha256": "self-test",
        "not_run": (),
        "false_authority": 0,
    }
    assert validate_observation("self-good", SHARED, compliant) == []
    mutations = []
    duplicate = deepcopy(compliant)
    duplicate["selections"] = ("s", "s", "a", "b")
    duplicate["reveal_calls"] = duplicate["selections"]
    mutations.append(validate_observation("self-double-charge", SHARED, duplicate))
    false_certificate = deepcopy(compliant)
    false_certificate["revealed"]["a"] = False
    mutations.append(validate_observation("self-false-certificate", SHARED, false_certificate))
    starved = deepcopy(compliant)
    starved["graph_spent"] = 30.0
    mutations.append(validate_observation("self-starved", SHARED, starved))
    if not all(mutations):
        raise AssertionError("oracle failed to reject a fixed mutation")
    return {
        "fixed_candidate_runs": len(FIXED_RUNS),
        "oracle_positive_self_checks": 2,
        "oracle_negative_mutations_rejected": len(mutations),
        "decision": "ORACLE_SELF_TEST_PASS",
    }


if __name__ == "__main__":
    import json

    print(json.dumps(self_test(), indent=2, sort_keys=True))
