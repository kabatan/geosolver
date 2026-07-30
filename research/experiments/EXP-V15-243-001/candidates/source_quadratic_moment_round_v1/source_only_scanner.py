#!/usr/bin/env python3
"""Truth-blind static readiness scanner for a quadratic moment side lane.

The scanner consumes one target-stripped source file and emits only an
anonymous structural record.  It does not consume endpoints, case identity,
targets, outcomes, or truth.  The output is proposal-only capability; it is
never solve authority.
"""

from __future__ import annotations

import argparse
import ast
from collections import Counter, defaultdict, deque
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
from typing import Any, Iterable, Mapping

import sympy as sp


SCHEMA = "geotarget.source-quadratic-moment-readiness/v1"
RUNTIME_ROOT = Path(
    os.environ.get(
        "GEOTARGET_CURRENT_RUNTIME_ROOT",
        "/home/kabatan/work/solver-experiment-runtime/solver",
    )
).resolve()
SEMANTIC_LIFT_PATH = (
    RUNTIME_ROOT
    / "research/experiments/EXP-V15-243-001/candidates/"
    "semantic_algebraic_lift/semantic_lift.py"
)
SEMANTIC_LIFT_SHA256 = (
    "4ab15c79605156b25d7aa3fbbf7b37a02be89a8a42bb642a09a4addcecb99836"
)
MAX_LIFT_VARIABLES = 96
MAX_SELECTED_EQUALITIES = 192
FORBIDDEN_TOP_LEVEL_KEYS = frozenset(
    {
        "answer",
        "case_id",
        "expected_target",
        "family",
        "id",
        "known_target",
        "known_truth",
        "post_process",
        "problem_id",
        "score",
        "target",
        "target_values",
        "truth",
    }
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _canonical_sha(value: object) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode()
    ).hexdigest()


def _load_semantic_lift():
    if _sha256(SEMANTIC_LIFT_PATH) != SEMANTIC_LIFT_SHA256:
        raise RuntimeError("pinned semantic_algebraic_lift compiler changed")
    specification = importlib.util.spec_from_file_location(
        "source_quadratic_moment_pinned_semantic_lift",
        SEMANTIC_LIFT_PATH,
    )
    if specification is None or specification.loader is None:
        raise ImportError(SEMANTIC_LIFT_PATH)
    module = importlib.util.module_from_spec(specification)
    sys.modules[specification.name] = module
    specification.loader.exec_module(module)
    return module


SEMANTIC = _load_semantic_lift()


def _base_record(status: str, reason: str) -> dict[str, object]:
    return {
        "schema_version": SCHEMA,
        "status": status,
        "reason": reason,
        "ready": status == "SOURCE_QUADRATIC_MOMENT_READY",
        "authority_pass": False,
        "target_release": False,
        "proposal_only": True,
        "target_read": False,
        "endpoint_read": False,
        "truth_used": False,
        "case_identity_used": False,
        "semantic_lift_sha256": SEMANTIC_LIFT_SHA256,
    }


def _row_variables(expression: sp.Expr, allowed: frozenset[sp.Symbol]) -> frozenset[sp.Symbol]:
    return frozenset(expression.free_symbols & allowed)


def _guard_kind(text: object) -> str | None:
    try:
        node = ast.parse(str(text), mode="eval").body
    except SyntaxError:
        return None
    if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name):
        return None
    return node.func.id


def _compile_partial_source(
    document: Mapping[str, object],
) -> tuple[Any, Any, dict[str, int]]:
    """Keep only source-order components accepted by the pinned frontend.

    Unsupported construction/equality rows remain mandatory for the later
    untouched source replay; they are merely omitted from this proposal-only
    quadratic relaxation.
    """

    base: dict[str, object] = {
        "task": "solve",
        "variables": document["variables"],
        "construction": [],
        "constraints": [],
        "guards": [],
        "answer": "0",
        "post_process": "",
    }
    if "bounds" in document:
        base["bounds"] = document["bounds"]

    def compile_trial(candidate: Mapping[str, object]) -> tuple[Any, Any] | None:
        try:
            compiler = SEMANTIC.SemanticLiftCompiler(candidate)
            return compiler, compiler.compile()
        except Exception:
            return None

    raw_guards = document.get("guards", [])
    if not isinstance(raw_guards, list):
        raw_guards = []
    # Bounds are semantic inputs to finite phase-sheet reconstruction.  They
    # are never turned into strict/neq moment constraints by this scanner.
    for guard in raw_guards:
        if _guard_kind(guard) != "Bound":
            continue
        trial = dict(base)
        trial["guards"] = [*base["guards"], guard]
        if compile_trial(trial) is not None:
            base = trial

    raw_construction = document.get("construction", [])
    if not isinstance(raw_construction, list):
        raw_construction = []
    for item in raw_construction:
        trial = dict(base)
        trial["construction"] = [*base["construction"], item]
        if compile_trial(trial) is not None:
            base = trial

    raw_constraints = document.get("constraints", [])
    if not isinstance(raw_constraints, list):
        raw_constraints = []
    for item in raw_constraints:
        trial = dict(base)
        trial["constraints"] = [*base["constraints"], item]
        if compile_trial(trial) is not None:
            base = trial

    # AssumeEq is the only guard form that contributes an equality row.  All
    # other guard/selector/definedness semantics stay replay-only in v1.
    for guard in raw_guards:
        if _guard_kind(guard) != "AssumeEq":
            continue
        trial = dict(base)
        trial["guards"] = [*base["guards"], guard]
        if compile_trial(trial) is not None:
            base = trial

    compiled = compile_trial(base)
    if compiled is None:
        raise SEMANTIC.LiftFailure("no source-order partial component compiled")
    compiler, artifact = compiled
    counts = {
        "raw_construction_count": len(raw_construction),
        "selected_construction_count": len(base["construction"]),
        "raw_constraint_count": len(raw_constraints),
        "selected_constraint_count": len(base["constraints"]),
        "raw_guard_count": len(raw_guards),
        "selected_equality_or_bound_guard_count": len(base["guards"]),
    }
    return compiler, artifact, counts


def _definition_sources(
    compiler: Any,
    artifact: Any,
) -> dict[str, dict[str, int]]:
    source_variables: dict[str, set[str]] = defaultdict(set)
    source_required_rows: Counter[str] = Counter()
    for definition in artifact.auxiliary_definitions:
        kind = str(definition.get("kind"))
        if kind == "target":
            continue
        if kind == "intersection":
            variables = tuple(str(item) for item in definition.get("variables", ()))
            source = f"intersection:{definition.get('source')}"
            required_rows = 2
        else:
            variable = definition.get("variable")
            variables = (str(variable),) if isinstance(variable, str) else ()
            source = f"{kind}:{definition.get('source')}"
            required_rows = 1
        source_required_rows[source] += required_rows
        for variable in variables:
            source_variables[source].add(variable)
    for group in artifact.phase_groups:
        source = f"unit-circle:{group['variable']}:{group['unit']}"
        source_required_rows[source] += 1
        source_variables[source].add(str(group["cosine_variable"]))
        source_variables[source].add(str(group["sine_variable"]))
    result: dict[str, dict[str, int]] = defaultdict(dict)
    for source, variables in source_variables.items():
        for variable in variables:
            result[variable][source] = source_required_rows[source]
    return dict(result)


def _source_slice_mapping(
    source_names: tuple[str, ...],
    artifact: Any,
    selected_variables: frozenset[str],
) -> tuple[list[dict[str, object]], bool]:
    index = {
        name: ordinal
        for ordinal, name in enumerate(artifact.variables)
        if name != artifact.target_variable
    }
    phases = {str(item["variable"]): item for item in artifact.phase_groups}
    mapping: list[dict[str, object]] = []
    for source_ordinal, name in enumerate(source_names):
        if name in index and name in selected_variables:
            mapping.append(
                {
                    "source_ordinal": source_ordinal,
                    "kind": "direct",
                    "lift_indices": [index[name]],
                }
            )
            continue
        phase = phases.get(name)
        if phase is None or phase.get("finite_sheet_count") is None:
            return mapping, False
        cosine = str(phase["cosine_variable"])
        sine = str(phase["sine_variable"])
        if cosine not in selected_variables or sine not in selected_variables:
            return mapping, False
        mapping.append(
            {
                "source_ordinal": source_ordinal,
                "kind": "finite_phase_pair",
                "lift_indices": [index[cosine], index[sine]],
                "finite_sheet_count": int(phase["finite_sheet_count"]),
            }
        )
    return mapping, len(mapping) == len(source_names)


def scan_document(document: object) -> dict[str, object]:
    try:
        if not isinstance(document, Mapping) or document.get("task") != "solve":
            return _base_record("SOURCE_QUADRATIC_MOMENT_NOT_READY", "raw-solve-source-required")
        forbidden = sorted(str(key) for key in document if str(key).lower() in FORBIDDEN_TOP_LEVEL_KEYS)
        if forbidden:
            return _base_record(
                "SOURCE_QUADRATIC_MOMENT_NOT_READY",
                "target-identity-or-truth-field-present",
            )
        variables = document.get("variables")
        source_names = variables.get("names") if isinstance(variables, Mapping) else None
        if (
            not isinstance(source_names, list)
            or not source_names
            or not all(isinstance(name, str) and name for name in source_names)
            or len(set(source_names)) != len(source_names)
        ):
            return _base_record("SOURCE_QUADRATIC_MOMENT_NOT_READY", "source-variable-ledger-invalid")

        compiler, artifact, partial_counts = _compile_partial_source(document)
        lift_names = tuple(
            name for name in artifact.variables if name != artifact.target_variable
        )
        if not lift_names or len(lift_names) > MAX_LIFT_VARIABLES:
            return _base_record("SOURCE_QUADRATIC_MOMENT_NOT_READY", "lift-dimension-outside-cap")
        symbols = {name: sp.Symbol(name, real=True) for name in lift_names}
        symbol_order = tuple(symbols[name] for name in lift_names)
        allowed = frozenset(symbol_order)

        valid_rows: list[dict[str, object]] = []
        invalid_source_histogram: dict[str, int] = defaultdict(int)
        for expression, source in compiler.equations:
            if source == "exact-target-link":
                continue
            expression = sp.expand(sp.sympify(expression))
            if artifact.target_variable in {item.name for item in expression.free_symbols}:
                invalid_source_histogram["synthetic-target-leak"] += 1
                continue
            if expression.atoms(sp.Function):
                invalid_source_histogram["nonpolynomial"] += 1
                continue
            try:
                polynomial = sp.Poly(expression, *symbol_order, domain=sp.QQ)
            except (sp.PolynomialError, TypeError, ValueError):
                invalid_source_histogram["non-QQ"] += 1
                continue
            degree = int(polynomial.total_degree())
            if degree > 2:
                invalid_source_histogram["degree>2"] += 1
                continue
            row_variables = _row_variables(polynomial.as_expr(), allowed)
            if not row_variables:
                if polynomial.as_expr() != 0:
                    invalid_source_histogram["constant-inconsistent"] += 1
                continue
            valid_rows.append(
                {
                    "source": str(source),
                    "degree": degree,
                    "variables": frozenset(item.name for item in row_variables),
                }
            )
        if not valid_rows or len(valid_rows) > MAX_SELECTED_EQUALITIES:
            return _base_record("SOURCE_QUADRATIC_MOMENT_NOT_READY", "quadratic-row-count-outside-cap")

        row_indices_by_source: dict[str, set[int]] = defaultdict(set)
        for ordinal, row in enumerate(valid_rows):
            row_indices_by_source[str(row["source"])].add(ordinal)
        definitions = _definition_sources(compiler, artifact)

        def definition_closed(variable: str, indices: set[int]) -> bool:
            requirements = definitions.get(variable)
            if not requirements:
                return variable in source_names
            for source, required_count in requirements.items():
                matches = {
                    index
                    for index in indices
                    if str(valid_rows[index]["source"]) == source
                }
                if len(matches) < required_count:
                    return False
                if not any(variable in set(valid_rows[index]["variables"]) for index in matches):
                    return False
            return True

        all_indices = set(range(len(valid_rows)))
        invalid_aux = {
            variable
            for variable in definitions
            if not definition_closed(variable, all_indices)
        }

        retained = {
            ordinal
            for ordinal, row in enumerate(valid_rows)
            if not (set(row["variables"]) & invalid_aux)
        }
        changed = True
        while changed:
            changed = False
            retained_variables = set().union(
                *(set(valid_rows[index]["variables"]) for index in retained)
            ) if retained else set()
            newly_invalid = {
                variable
                for variable in retained_variables
                if variable in definitions
                and not definition_closed(variable, retained)
            }
            if newly_invalid:
                next_retained = {
                    index
                    for index in retained
                    if not (set(valid_rows[index]["variables"]) & newly_invalid)
                }
                changed = next_retained != retained
                retained = next_retained
        if not retained:
            return _base_record("SOURCE_QUADRATIC_MOMENT_NOT_READY", "aux-definition-closure-empty")

        # Discard valid but source-disconnected auxiliary rows.  This prevents
        # an isolated constant construction from supplying the sole quadratic
        # row for an otherwise linear source slice.
        phase_by_source = {str(item["variable"]): item for item in artifact.phase_groups}
        seed_variables: set[str] = set()
        for name in source_names:
            if any(name in set(valid_rows[index]["variables"]) for index in retained):
                seed_variables.add(name)
                continue
            phase = phase_by_source.get(name)
            if phase is not None and phase.get("finite_sheet_count") is not None:
                seed_variables.add(str(phase["cosine_variable"]))
                seed_variables.add(str(phase["sine_variable"]))
        variable_rows: dict[str, set[int]] = defaultdict(set)
        for index in retained:
            for variable in valid_rows[index]["variables"]:
                variable_rows[str(variable)].add(index)
        connected_rows: set[int] = set()
        connected_variables = set(seed_variables)
        queue = deque(seed_variables)
        while queue:
            variable = queue.popleft()
            for index in variable_rows.get(variable, ()):
                if index in connected_rows:
                    continue
                connected_rows.add(index)
                for neighbor in valid_rows[index]["variables"]:
                    neighbor = str(neighbor)
                    if neighbor not in connected_variables:
                        connected_variables.add(neighbor)
                        queue.append(neighbor)
        retained &= connected_rows
        if not retained:
            return _base_record("SOURCE_QUADRATIC_MOMENT_NOT_READY", "source-connected-cover-empty")

        # Connectivity cannot remove a required definition row because it
        # shares the auxiliary, but replay the closure check defensively.
        retained_variables = set().union(
            *(set(valid_rows[index]["variables"]) for index in retained)
        )
        if any(
            variable in definitions and not definition_closed(variable, retained)
            for variable in retained_variables
        ):
            return _base_record("SOURCE_QUADRATIC_MOMENT_NOT_READY", "aux-definition-closure-broken")

        selected_variables = frozenset(
            set().union(*(set(valid_rows[index]["variables"]) for index in retained))
        )
        mapping, mapping_complete = _source_slice_mapping(
            tuple(source_names), artifact, selected_variables
        )
        if not mapping_complete:
            return _base_record("SOURCE_QUADRATIC_MOMENT_NOT_READY", "source-slice-mapping-incomplete")
        selected_degrees = [int(valid_rows[index]["degree"]) for index in retained]
        if 2 not in selected_degrees:
            return _base_record("SOURCE_QUADRATIC_MOMENT_NOT_READY", "no-quadratic-equality-row")

        direct_bounds = 0
        raw_bounds = document.get("bounds")
        if isinstance(raw_bounds, list) and len(raw_bounds) == len(source_names):
            for item in raw_bounds:
                if (
                    isinstance(item, list)
                    and len(item) == 2
                    and all(sp.Rational(str(value)).is_Rational for value in item)
                ):
                    direct_bounds += 1
        return {
            **_base_record("SOURCE_QUADRATIC_MOMENT_READY", "closed-QQ-degree<=2-cover"),
            **partial_counts,
            "source_variable_count": len(source_names),
            "lift_variable_count": len(selected_variables),
            "selected_equality_count": len(retained),
            "selected_linear_equality_count": selected_degrees.count(1),
            "selected_quadratic_equality_count": selected_degrees.count(2),
            "ignored_equality_count": len(compiler.equations) - 1 - len(retained),
            "predicate_replay_only_count": len(artifact.predicates),
            "selector_replay_only_count": len(artifact.selector_ledger),
            "definedness_replay_only_count": len(artifact.definedness_ledger),
            "semantic_replay_obligation_count": len(artifact.replay_ledger) - 1,
            "phase_mapping_count": sum(item["kind"] == "finite_phase_pair" for item in mapping),
            "closed_QQ_source_bound_count": direct_bounds,
            "source_slice_mapping_sha256": _canonical_sha(mapping),
            "source_slice_mapping_complete": True,
            "target_auxiliary_removed": True,
            "target_link_removed": True,
            "strict_or_neq_promoted_to_moment_constraint": False,
            "all_selected_aux_definitions_closed": True,
            "all_source_variables_incident": True,
            "cover_proof_ready": bool(artifact.proof_ready),
        }
    except Exception as error:
        reason = type(error).__name__
        if isinstance(error, getattr(SEMANTIC, "LiftFailure")):
            reason = "semantic-lift-rejected"
        return _base_record("SOURCE_QUADRATIC_MOMENT_NOT_READY", reason)


def scan_source(source_path: Path) -> dict[str, object]:
    try:
        document = json.loads(source_path.read_bytes())
    except Exception as error:
        return _base_record("SOURCE_QUADRATIC_MOMENT_NOT_READY", type(error).__name__)
    return scan_document(document)


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    arguments = parser.parse_args(argv)
    if os.sched_getaffinity(0) != {14}:
        raise RuntimeError("source-only scanner must be pinned to CPU14")
    result = scan_source(arguments.source)
    print(json.dumps(result, sort_keys=True, separators=(",", ":"), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
