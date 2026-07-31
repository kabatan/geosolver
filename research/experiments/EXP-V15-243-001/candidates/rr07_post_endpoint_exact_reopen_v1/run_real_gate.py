#!/usr/bin/env python3.12
"""Truth-blind source prevalence gate for the strict RR-07 typed pattern.

This intentionally stops before any endpoint or exact-worker work unless the
source corpus contains at least four independent sources and two typed
contact actions.  It is a candidate-local AST recognizer, not a source parser
or compiler extension.
"""

from __future__ import annotations

import argparse
import ast
from collections import Counter
from fractions import Fraction
import hashlib
import json
import os
from pathlib import Path
from typing import Mapping


REQUESTS_SHA256 = "ee424315256582652ea0df72a05c21903a5fd4366867c6788129a79e4f80fd35"
APPROVED_SOURCE_ROOT = Path(
    "/home/kabatan/work/solver-experiment-results/partial-ideal-root-readiness-v1/degree1-inputs"
).resolve()
ROW_KEYS = frozenset(("candidate_relation_high_to_low", "endpoint", "source_path"))
FORBIDDEN_SOURCE_KEYS = frozenset(
    ("id", "case_id", "problem_id", "family", "truth", "outcome", "result", "score", "known_count")
)


def _sha(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _name(node: ast.AST) -> str | None:
    return node.id if isinstance(node, ast.Name) else None


def _call(node: ast.AST | None, function: str, arity: int) -> ast.Call | None:
    if (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == function
        and len(node.args) == arity
    ):
        return node
    return None


def _positive_exact_constant(value: object) -> Fraction | None:
    if isinstance(value, bool):
        return None
    try:
        exact = Fraction(str(value))
    except (ValueError, ZeroDivisionError):
        return None
    return exact if exact > 0 else None


def _construction_calls(document: Mapping[str, object]) -> dict[str, ast.Call]:
    construction = document.get("construction")
    if not isinstance(construction, list):
        return {}
    calls: dict[str, ast.Call] = {}
    for item in construction:
        if (
            not isinstance(item, Mapping)
            or not isinstance(item.get("name"), str)
            or not isinstance(item.get("expr"), str)
        ):
            continue
        try:
            node = ast.parse(item["expr"], mode="eval").body
        except SyntaxError:
            continue
        if isinstance(node, ast.Call):
            calls[item["name"]] = node
    return calls


def _contact_patterns(document: Mapping[str, object]) -> list[tuple[tuple[str, str, str], frozenset[str], str]]:
    """Return (triangle, contact-side, contact-output) for strict incircle contacts."""

    calls = _construction_calls(document)
    found: list[tuple[tuple[str, str, str], frozenset[str], str]] = []

    for output, node in calls.items():
        direct = _call(node, "IncircleContactPoint", 3)
        if direct is None:
            continue
        triangle = tuple(_name(argument) for argument in direct.args)
        side_node = next((item.value for item in direct.keywords if item.arg == "side"), None)
        side = side_node.value if isinstance(side_node, ast.Constant) else None
        if None in triangle or side not in {"AB", "AC", "BC"}:
            continue
        indices = {"A": 0, "B": 1, "C": 2}
        endpoints = frozenset((triangle[indices[side[0]]], triangle[indices[side[1]]]))
        found.append((triangle, endpoints, output))

    for circle_name, circle_node in calls.items():
        incircle = _call(circle_node, "Incircle", 3)
        if incircle is None:
            continue
        triangle = tuple(_name(argument) for argument in incircle.args)
        if None in triangle:
            continue
        for output, node in calls.items():
            contact = _call(node, "ContactPoint", 2)
            if contact is None or _name(contact.args[0]) != circle_name:
                continue
            line = _call(contact.args[1], "Line", 2)
            if line is None:
                line_name = _name(contact.args[1])
                line = _call(calls.get(line_name), "Line", 2) if line_name is not None else None
            if line is None:
                continue
            endpoints = frozenset((_name(line.args[0]), _name(line.args[1])))
            if None in endpoints or len(endpoints) != 2 or not endpoints <= set(triangle):
                continue
            found.append((triangle, endpoints, output))
    return found


def _strict_typed_actions(document: Mapping[str, object]) -> frozenset[str]:
    """Require the source contact plus an independent positive tangent length."""

    constraints = document.get("constraints")
    if not isinstance(constraints, list):
        return frozenset()
    actions: set[str] = set()
    for triangle, side, contact in _contact_patterns(document):
        for constraint in constraints:
            if not isinstance(constraint, Mapping):
                continue
            definition = constraint.get("def")
            if not isinstance(definition, str) or _positive_exact_constant(constraint.get("value")) is None:
                continue
            try:
                distance = _call(ast.parse(definition, mode="eval").body, "Distance", 2)
            except SyntaxError:
                continue
            if distance is None:
                continue
            operands = (_name(distance.args[0]), _name(distance.args[1]))
            if operands[0] == contact and operands[1] in side:
                vertex = operands[1]
            elif operands[1] == contact and operands[0] in side:
                vertex = operands[0]
            else:
                continue
            side_indices = "".join(
                label for label, point in zip(("A", "B", "C"), triangle) if point in side
            )
            vertex_index = ("A", "B", "C")[triangle.index(vertex)]
            actions.add(f"INCIRCLE_CONTACT/{side_indices}/FROM_{vertex_index}")
    return frozenset(actions)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--requests", type=Path, required=True)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--private-signatures", type=Path, required=True)
    parser.add_argument("--expected-cpu", type=int, default=14)
    arguments = parser.parse_args()

    if os.sched_getaffinity(0) != {arguments.expected_cpu}:
        raise SystemExit("real gate must be pinned to expected CPU")
    if arguments.source_root.resolve() != APPROVED_SOURCE_ROOT:
        raise SystemExit("unapproved anonymous source root")
    request_payload = arguments.requests.read_bytes()
    if _sha(request_payload) != REQUESTS_SHA256:
        raise SystemExit("requests SHA mismatch")
    rows = json.loads(request_payload)
    if (
        not isinstance(rows, list)
        or len(rows) != 85
        or any(not isinstance(row, Mapping) or set(row) != ROW_KEYS for row in rows)
    ):
        raise SystemExit("anonymous request schema mismatch")

    counters = Counter()
    actions: set[str] = set()
    for row in rows:
        source = Path(str(row["source_path"])).resolve()
        try:
            source.relative_to(APPROVED_SOURCE_ROOT)
        except ValueError:
            raise SystemExit("anonymous source escaped approved root")
        document = json.loads(source.read_bytes())
        if not isinstance(document, Mapping) or FORBIDDEN_SOURCE_KEYS & set(document):
            raise SystemExit("source crossed identity/truth boundary")
        typed = _strict_typed_actions(document)
        if typed:
            counters["strict_typed_source"] += 1
            actions.update(typed)
        elif _contact_patterns(document):
            counters["contact_without_independent_positive_tangent"] += 1
        else:
            counters["source_signature_inapplicable"] += 1

    static_pass = counters["strict_typed_source"] >= 4 and len(actions) >= 2
    # No endpoint is consumed and no exact worker is invoked after a failed
    # prevalence gate.  The root benchmark owner therefore has no private
    # accepted signatures to intersect with old logs.
    private_payload = b"[]\n"
    arguments.private_signatures.parent.mkdir(parents=True, exist_ok=True)
    arguments.private_signatures.write_bytes(private_payload)
    aggregate = {
        "schema_version": "geotarget.rr07-post-endpoint-exact-reopen-real-static-gate/v1",
        "request_count": len(rows),
        "requests_sha256": REQUESTS_SHA256,
        "strict_typed_source_count": counters["strict_typed_source"],
        "strict_typed_action_count": len(actions),
        "status_histogram": dict(sorted(counters.items())),
        "static_gate_pass": static_pass,
        "disposition": "PROCEED_TO_ENDPOINT_REPLAY" if static_pass else "STOP_STATIC_PREVALENCE_GATE",
        "endpoint_consumed": False,
        "exact_worker_invoked": False,
        "private_signature_count": 0,
        "private_signatures_sha256": _sha(private_payload),
        "individual_signatures_emitted_in_aggregate": False,
        "source_parser_or_compiler_modified": False,
        "authority_pass": False,
        "target_release": False,
        "truth_case_family_target_count_outcome_routing": False,
    }
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_text(json.dumps(aggregate, sort_keys=True, separators=(",", ":")) + "\n")
    print(json.dumps(aggregate, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
