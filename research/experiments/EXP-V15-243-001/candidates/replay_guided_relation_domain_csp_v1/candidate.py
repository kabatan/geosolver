"""Target-blind finite relation-domain CSP proposal generator.

This disposable candidate compiles only construction, constraints, guards and
bounds.  The source target is replaced by the constant zero before the pinned
semantic lift is invoked, so it cannot seed, prune or order a domain.  Exact
univariate roots seed finite domains; low-arity relations then enforce
generalized arc consistency.  Only complete assignments that survive a fresh
target-blind source replay are emitted.

Emissions are proposals, never descriptor authority.  A separate audit may
run the untouched source including its raw target, but that audit does not
remove or reorder proposals and still cannot release a target.
"""

from __future__ import annotations

import ast
from copy import deepcopy
from dataclasses import dataclass
import hashlib
import importlib.util
import itertools
import json
from pathlib import Path
import sys
from typing import Any, Iterable, Mapping, Sequence

import sympy as sp


SCHEMA = "geotarget.replay-guided-relation-domain-csp/v1"
RUNTIME_ROOT = Path(
    "/home/kabatan/work/solver-experiment-runtime/solver"
).resolve()
SEMANTIC_ROOT = (
    RUNTIME_ROOT
    / "research/experiments/EXP-V15-243-001/candidates/semantic_algebraic_lift"
)
SEMANTIC_LIFT_PATH = SEMANTIC_ROOT / "semantic_lift.py"
EXACT_REPLAY_PATH = SEMANTIC_ROOT / "exact_replay.py"
EXPECTED_SHA256 = {
    SEMANTIC_LIFT_PATH: "4ab15c79605156b25d7aa3fbbf7b37a02be89a8a42bb642a09a4addcecb99836",
    EXACT_REPLAY_PATH: "8c1c18e4d46ce4910ca630589fda3424198dfcfc2c3537ff39f31d3b9f89d23a",
}

MAX_VARIABLES = 12
MAX_RELATIONS = 48
MAX_UNIVARIATE_DEGREE = 4
MAX_DOMAIN_SIZE = 16
MAX_SUPPORT_PRODUCT = 4_096
MAX_ASSIGNMENTS = 4_096
MAX_PROPAGATION_ROUNDS = 64
MAX_SOURCE_BYTES = 65_536
MAX_TOTAL_EXPRESSION_CHARS = 16_384
MAX_EXPRESSION_CHARS = 4_096
MAX_AST_NODES_PER_EXPRESSION = 512
MAX_AST_DEPTH = 64
MAX_INTEGER_BITS = 256
MAX_POWER = 32
MAX_COMPILED_EXPRESSION_CHARS = 8_192
MAX_COMPILED_OPERATIONS = 1_024

FORBIDDEN_ROUTING_KEYS = frozenset(
    {
        "truth",
        "known_truth",
        "known_target",
        "expected_target",
        "target_values",
        "score",
        "outcome",
        "historical_result",
    }
)


class CSPNotApplicable(ValueError):
    """The source is outside the finite, exactly replayed subset."""


class CSPResourceCap(CSPNotApplicable):
    """A fixed combinatorial or algebraic cap was reached."""


class CSPContradiction(CSPNotApplicable):
    """Exact relations proved that the finite domain has no assignment."""


@dataclass(frozen=True)
class Relation:
    expression: sp.Expr
    relation: str
    source: str


@dataclass(frozen=True)
class Problem:
    target_blind_document: dict[str, Any]
    artifact: Any
    variables: tuple[sp.Symbol, ...]
    source_variables: tuple[str, ...]
    relations: tuple[Relation, ...]


@dataclass(frozen=True)
class CandidatePrejoinHold:
    """Candidate-only hold; it is not a solver result or authority object."""

    untouched_baseline: object
    proposal_result: Mapping[str, Any]


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _canonical_sha256(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _load(name: str, path: Path):
    specification = importlib.util.spec_from_file_location(name, path)
    if specification is None or specification.loader is None:
        raise ImportError(path)
    module = importlib.util.module_from_spec(specification)
    sys.modules[name] = module
    specification.loader.exec_module(module)
    return module


def _semantic_modules():
    for path, expected in EXPECTED_SHA256.items():
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise CSPNotApplicable("PINNED_SEMANTIC_RUNTIME_HASH_MISMATCH")
    semantic = sys.modules.get("semantic_lift")
    if semantic is None:
        semantic = _load("semantic_lift", SEMANTIC_LIFT_PATH)
    replay = sys.modules.get("geotarget_relation_domain_exact_replay")
    if replay is None:
        replay = _load("geotarget_relation_domain_exact_replay", EXACT_REPLAY_PATH)
    return semantic, replay


def _target_blind_document(document: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(document, Mapping):
        raise CSPNotApplicable("SOURCE_NOT_MAPPING")
    crossed = sorted(
        str(key) for key in document if str(key).lower() in FORBIDDEN_ROUTING_KEYS
    )
    if crossed:
        raise CSPNotApplicable("FORBIDDEN_TRUTH_OR_OUTCOME_INPUT")
    if document.get("task") != "solve":
        raise CSPNotApplicable("TASK_IS_NOT_SOLVE")
    if document.get("post_process", "") not in (None, ""):
        raise CSPNotApplicable("POST_PROCESS_NOT_EMPTY")
    variables = document.get("variables")
    if not isinstance(variables, Mapping):
        raise CSPNotApplicable("VARIABLES_NOT_MAPPING")
    names = variables.get("names")
    if not isinstance(names, Sequence) or isinstance(names, (str, bytes)):
        raise CSPNotApplicable("VARIABLE_NAMES_NOT_SEQUENCE")
    # Deliberately omit id, family, answer, post_process and every unknown
    # top-level field.  The placeholder target is constant and creates no
    # source-domain relation.
    projection = {
        "task": "solve",
        "variables": {"names": deepcopy(list(names))},
        "bounds": deepcopy(document.get("bounds")),
        "construction": deepcopy(document.get("construction", [])),
        "constraints": deepcopy(document.get("constraints", [])),
        "guards": deepcopy(document.get("guards", [])),
        "answer": "0",
        "post_process": "",
    }
    if len(_canonical_bytes(projection)) > MAX_SOURCE_BYTES:
        raise CSPResourceCap("SOURCE_BYTE_CAP")
    _audit_source_syntax(projection)
    return projection


def _small_integer_literal(node: ast.AST) -> int | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, int) and not isinstance(
        node.value, bool
    ):
        return int(node.value)
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
        value = _small_integer_literal(node.operand)
        if value is not None:
            return value if isinstance(node.op, ast.UAdd) else -value
    return None


def _ast_depth(node: ast.AST) -> int:
    children = list(ast.iter_child_nodes(node))
    return 1 if not children else 1 + max(_ast_depth(child) for child in children)


def _audit_expression(text: str) -> None:
    if len(text) > MAX_EXPRESSION_CHARS:
        raise CSPResourceCap("EXPRESSION_CHARACTER_CAP")
    try:
        root = ast.parse(text, mode="eval")
    except (SyntaxError, ValueError) as error:
        raise CSPNotApplicable("EXPRESSION_SYNTAX_REJECTED") from error
    nodes = list(ast.walk(root))
    if len(nodes) > MAX_AST_NODES_PER_EXPRESSION:
        raise CSPResourceCap("EXPRESSION_AST_NODE_CAP")
    if _ast_depth(root) > MAX_AST_DEPTH:
        raise CSPResourceCap("EXPRESSION_AST_DEPTH_CAP")
    for node in nodes:
        if isinstance(node, ast.Constant) and isinstance(node.value, int) and not isinstance(
            node.value, bool
        ):
            if abs(int(node.value)).bit_length() > MAX_INTEGER_BITS:
                raise CSPResourceCap("INTEGER_LITERAL_BIT_CAP")
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Pow):
            exponent = _small_integer_literal(node.right)
            if exponent is None or abs(exponent) > MAX_POWER:
                raise CSPResourceCap("POWER_CAP_OR_NONLITERAL_EXPONENT")


def _audit_source_syntax(document: Mapping[str, Any]) -> None:
    expressions: list[str] = []
    for item in document.get("construction", ()):
        if not isinstance(item, Mapping) or not isinstance(item.get("expr"), str):
            raise CSPNotApplicable("CONSTRUCTION_EXPRESSION_MALFORMED")
        expressions.append(item["expr"])
    for item in document.get("constraints", ()):
        if not isinstance(item, Mapping) or not isinstance(item.get("def"), str):
            raise CSPNotApplicable("CONSTRAINT_EXPRESSION_MALFORMED")
        expressions.extend((item["def"], str(item.get("value", 0))))
    for guard in document.get("guards", ()):
        if not isinstance(guard, str):
            raise CSPNotApplicable("GUARD_EXPRESSION_MALFORMED")
        expressions.append(guard)
    if sum(len(text) for text in expressions) > MAX_TOTAL_EXPRESSION_CHARS:
        raise CSPResourceCap("TOTAL_EXPRESSION_CHARACTER_CAP")
    for text in expressions:
        _audit_expression(text)


def _audit_compiled_expression(expression: sp.Expr) -> None:
    text = str(expression)
    if len(text) > MAX_COMPILED_EXPRESSION_CHARS:
        raise CSPResourceCap("COMPILED_EXPRESSION_CHARACTER_CAP")
    if int(sp.count_ops(expression, visual=False)) > MAX_COMPILED_OPERATIONS:
        raise CSPResourceCap("COMPILED_OPERATION_CAP")
    for rational in expression.atoms(sp.Rational):
        if int(rational.p).bit_length() > MAX_INTEGER_BITS or int(
            rational.q
        ).bit_length() > MAX_INTEGER_BITS:
            raise CSPResourceCap("COMPILED_COEFFICIENT_BIT_CAP")


def compile_problem(document: Mapping[str, Any]) -> Problem:
    semantic, _ = _semantic_modules()
    target_blind = _target_blind_document(document)
    try:
        artifact = semantic.compile_document(target_blind)
    except semantic.LiftFailure as error:
        raise CSPNotApplicable(f"SEMANTIC_LIFT_REJECTED:{error}") from error
    if artifact.phase_groups:
        # Algebraic unit-circle coordinates do not by themselves provide a
        # finite exact domain for the original periodic source coordinate.
        raise CSPNotApplicable("PERIODIC_SOURCE_RECONSTRUCTION_NOT_IMPLEMENTED")
    names = tuple(name for name in artifact.variables if name != artifact.target_variable)
    if len(names) > MAX_VARIABLES:
        raise CSPResourceCap("VARIABLE_CAP")
    symbols = {name: sp.Symbol(name, real=True) for name in artifact.variables}
    variables = tuple(symbols[name] for name in names)
    relations: list[Relation] = []
    for index, text in enumerate(artifact.equations):
        expression = sp.sympify(text, locals=symbols)
        if symbols[artifact.target_variable] in expression.free_symbols:
            continue
        _audit_compiled_expression(expression)
        relations.append(Relation(sp.expand(expression), "eq", f"equation:{index}"))
    for predicate in artifact.predicates:
        expression = sp.sympify(predicate["expression"], locals=symbols)
        if symbols[artifact.target_variable] in expression.free_symbols:
            raise CSPNotApplicable("TARGET_LEAKED_INTO_SOURCE_PREDICATE")
        _audit_compiled_expression(expression)
        relations.append(
            Relation(
                sp.expand(expression),
                str(predicate["relation"]),
                str(predicate["source"]),
            )
        )
    if len(relations) > MAX_RELATIONS:
        raise CSPResourceCap("RELATION_CAP")
    declared = tuple(str(name) for name in target_blind["variables"]["names"])
    if any(name not in names for name in declared):
        raise CSPNotApplicable("DECLARED_SOURCE_COORDINATE_NOT_ALGEBRAIC")
    return Problem(target_blind, artifact, variables, declared, tuple(relations))


def _zero(value: object) -> bool:
    expression = sp.simplify(sp.sympify(value))
    return expression == 0 or expression.is_zero is True


def _sign(value: object) -> int:
    expression = sp.simplify(sp.sympify(value))
    if _zero(expression):
        return 0
    if expression.is_positive is True or sp.ask(sp.Q.positive(expression)) is True:
        return 1
    if expression.is_negative is True or sp.ask(sp.Q.negative(expression)) is True:
        return -1
    raise CSPNotApplicable("EXACT_RELATION_SIGN_UNDECIDED")


def _holds(relation: Relation, substitutions: Mapping[sp.Symbol, sp.Expr]) -> bool:
    sign = _sign(relation.expression.subs(substitutions))
    return {
        "eq": sign == 0,
        "ne": sign != 0,
        "gt": sign > 0,
        "ge": sign >= 0,
        "lt": sign < 0,
        "le": sign <= 0,
    }[relation.relation]


def _same(left: sp.Expr, right: sp.Expr) -> bool:
    return _zero(sp.sympify(left) - sp.sympify(right))


def _unique(values: Iterable[sp.Expr]) -> tuple[sp.Expr, ...]:
    result: list[sp.Expr] = []
    for raw in values:
        value = sp.simplify(raw)
        if any(_same(value, previous) for previous in result):
            continue
        result.append(value)
        if len(result) > MAX_DOMAIN_SIZE:
            raise CSPResourceCap("DOMAIN_SIZE_CAP")
    return tuple(sorted(result, key=sp.default_sort_key))


def _product_size(domains: Iterable[Sequence[sp.Expr]]) -> int:
    result = 1
    for domain in domains:
        result *= len(domain)
        if result > MAX_SUPPORT_PRODUCT:
            raise CSPResourceCap("RELATION_SUPPORT_PRODUCT_CAP")
    return result


def _real_roots(expression: sp.Expr, variable: sp.Symbol) -> tuple[sp.Expr, ...]:
    try:
        numerator, denominator = sp.fraction(sp.together(expression))
    except (NotImplementedError, sp.PolynomialError, TypeError, ValueError) as error:
        raise CSPNotApplicable("UNIVARIATE_RATIONAL_NORMALIZATION_FAILED") from error
    if variable in denominator.free_symbols:
        raise CSPNotApplicable("NONPOLYNOMIAL_UNIVARIATE_RELATION")
    try:
        polynomial = sp.Poly(sp.expand(numerator), variable, extension=True)
    except (sp.PolynomialError, TypeError, ValueError) as error:
        raise CSPNotApplicable("UNIVARIATE_POLYNOMIAL_COMPILE_FAILED") from error
    if polynomial.is_zero:
        raise CSPNotApplicable("UNCONSTRAINED_UNIVARIATE_BRANCH")
    degree = polynomial.degree()
    if degree < 1 or degree > MAX_UNIVARIATE_DEGREE:
        raise CSPResourceCap("UNIVARIATE_DEGREE_CAP")
    try:
        root_map = sp.roots(polynomial.as_expr(), variable)
    except (NotImplementedError, sp.PolynomialError, TypeError, ValueError) as error:
        raise CSPNotApplicable("UNIVARIATE_ROOT_ENUMERATION_FAILED") from error
    if sum(int(multiplicity) for multiplicity in root_map.values()) != degree:
        raise CSPNotApplicable("UNIVARIATE_ROOT_ENUMERATION_INCOMPLETE")
    roots: list[sp.Expr] = []
    for root in root_map:
        root = sp.simplify(root)
        real = root.is_real
        if real is None:
            real = sp.ask(sp.Q.real(root))
        if real is None:
            raise CSPNotApplicable("ROOT_REALITY_UNDECIDED")
        if real is False:
            continue
        if not _zero(polynomial.as_expr().subs(variable, root)):
            raise CSPNotApplicable("ROOT_EXACT_REPLAY_FAILED")
        roots.append(root)
    return _unique(roots)


def _intersection(
    left: Sequence[sp.Expr], right: Sequence[sp.Expr]
) -> tuple[sp.Expr, ...]:
    return tuple(value for value in left if any(_same(value, item) for item in right))


def _seed_domains(problem: Problem) -> tuple[dict[sp.Symbol, tuple[sp.Expr, ...]], int]:
    domains: dict[sp.Symbol, tuple[sp.Expr, ...]] = {
        variable: () for variable in problem.variables
    }
    for _round in range(MAX_PROPAGATION_ROUNDS):
        changed = False
        for relation in problem.relations:
            if relation.relation != "eq":
                continue
            relation_variables = tuple(
                variable for variable in problem.variables if variable in relation.expression.free_symbols
            )
            for variable in relation_variables:
                others = tuple(item for item in relation_variables if item != variable)
                if any(not domains[item] for item in others):
                    continue
                _product_size(domains[item] for item in others)
                combinations = itertools.product(*(domains[item] for item in others))
                roots: list[sp.Expr] = []
                finite_for_every_branch = True
                for combination in combinations:
                    substitutions = dict(zip(others, combination, strict=True))
                    reduced = sp.expand(relation.expression.subs(substitutions))
                    if variable not in reduced.free_symbols:
                        if _zero(reduced):
                            finite_for_every_branch = False
                            break
                        continue
                    try:
                        roots.extend(_real_roots(reduced, variable))
                    except CSPNotApplicable as error:
                        if str(error) == "UNCONSTRAINED_UNIVARIATE_BRANCH":
                            finite_for_every_branch = False
                            break
                        raise
                if not finite_for_every_branch:
                    continue
                candidate = _unique(roots)
                if not candidate:
                    continue
                previous = domains[variable]
                replacement = candidate if not previous else _intersection(previous, candidate)
                if not replacement:
                    raise CSPContradiction("EMPTY_DOMAIN_DURING_ROOT_PROPAGATION")
                if previous != replacement:
                    domains[variable] = replacement
                    changed = True
        if not changed:
            break
    else:
        raise CSPResourceCap("PROPAGATION_ROUND_CAP")
    if any(not domain for domain in domains.values()):
        raise CSPNotApplicable("NO_FINITE_DOMAIN_FOR_EVERY_COORDINATE")
    pre_arc_product = _product_size(domains.values())
    return domains, pre_arc_product


def _arc_consistency(
    problem: Problem, domains: dict[sp.Symbol, tuple[sp.Expr, ...]]
) -> int:
    removed = 0
    for _round in range(MAX_PROPAGATION_ROUNDS):
        changed = False
        for relation in problem.relations:
            variables = tuple(
                variable for variable in problem.variables if variable in relation.expression.free_symbols
            )
            if not variables:
                if not _holds(relation, {}):
                    raise CSPContradiction("CONSTANT_RELATION_FALSE")
                continue
            _product_size(domains[variable] for variable in variables)
            support: dict[sp.Symbol, list[sp.Expr]] = {variable: [] for variable in variables}
            for values in itertools.product(*(domains[variable] for variable in variables)):
                substitutions = dict(zip(variables, values, strict=True))
                if not _holds(relation, substitutions):
                    continue
                for variable, value in substitutions.items():
                    support[variable].append(value)
            for variable in variables:
                replacement = _unique(support[variable])
                if not replacement:
                    raise CSPContradiction(f"RELATION_HAS_NO_SUPPORT:{relation.source}")
                if replacement != domains[variable]:
                    removed += len(domains[variable]) - len(replacement)
                    domains[variable] = replacement
                    changed = True
        if not changed:
            return removed
    raise CSPResourceCap("ARC_CONSISTENCY_ROUND_CAP")


def _exact_value(value: sp.Expr) -> dict[str, str]:
    exact = sp.simplify(value)
    representation = sp.srepr(exact)
    return {
        "text": str(exact),
        "srepr": representation,
        "sha256": hashlib.sha256(representation.encode("utf-8")).hexdigest(),
    }


def _target_blind_replay_matches(
    problem: Problem, assignment: Mapping[sp.Symbol, sp.Expr]
) -> bool:
    _, replay = _semantic_modules()
    raw_values = {
        name: assignment[sp.Symbol(name, real=True)] for name in problem.source_variables
    }
    try:
        lifted = replay.materialize_lift_witness(
            problem.target_blind_document, problem.artifact, raw_values
        )
        accepted, _reason = replay.verify_source_and_target_replay(
            problem.target_blind_document,
            problem.artifact,
            raw_values,
            lifted,
        )
    except Exception:
        return False
    if not accepted:
        return False
    for variable, value in assignment.items():
        if variable.name not in lifted or not _same(lifted[variable.name], value):
            return False
    return True


def _ready_result(
    problem: Problem,
    domains: Mapping[sp.Symbol, Sequence[sp.Expr]],
    *,
    pre_arc_product: int,
    arc_values_removed: int,
) -> dict[str, Any]:
    assignment_count = _product_size(domains.values())
    if assignment_count > MAX_ASSIGNMENTS:
        raise CSPResourceCap("FULL_ASSIGNMENT_CAP")
    proposals = []
    for values in itertools.product(*(domains[variable] for variable in problem.variables)):
        assignment = dict(zip(problem.variables, values, strict=True))
        if not all(_holds(relation, assignment) for relation in problem.relations):
            continue
        if not _target_blind_replay_matches(problem, assignment):
            continue
        raw = {
            name: _exact_value(assignment[sp.Symbol(name, real=True)])
            for name in problem.source_variables
        }
        lifted = {variable.name: _exact_value(assignment[variable]) for variable in problem.variables}
        proposals.append(
            {
                "raw_coordinate_assignment": raw,
                "full_lifted_coordinate_assignment": lifted,
            }
        )
    proposals.sort(key=_canonical_bytes)
    for ordinal, proposal in enumerate(proposals):
        proposal["proposal_ordinal"] = ordinal
        proposal["proposal_artifact_sha256"] = _canonical_sha256(proposal)
        proposal["authority_pass"] = False
        proposal["target_release"] = False
    if not proposals:
        raise CSPContradiction("NO_ASSIGNMENT_SURVIVED_TARGET_BLIND_SOURCE_REPLAY")
    assignment_payload = [
        {
            "raw": item["raw_coordinate_assignment"],
            "lifted": item["full_lifted_coordinate_assignment"],
        }
        for item in proposals
    ]
    return {
        "schema_version": SCHEMA,
        "status": "PROPOSAL_READY_HOLD",
        "target_blind_source_projection_sha256": _canonical_sha256(
            problem.target_blind_document
        ),
        "finite_domain_variable_count": len(problem.variables),
        "relation_count": len(problem.relations),
        "pre_arc_assignment_product": pre_arc_product,
        "post_arc_assignment_product": assignment_count,
        "arc_values_removed": arc_values_removed,
        "proposal_count": len(proposals),
        "assignment_signature_sha256": _canonical_sha256(assignment_payload),
        "proposals": proposals,
        "selection_read_raw_target": False,
        "selection_used_case_id_family_truth_or_outcome": False,
        "all_roots_preserved_until_exact_relation_pruning": True,
        "target_blind_construction_constraint_guard_bound_replay": True,
        "target_set_completeness_claim": False,
        "authority_pass": False,
        "target_release": False,
        "baseline_fallback_required": True,
    }


def build_proposals(document: Mapping[str, Any]) -> dict[str, Any]:
    """Build target-blind exact coordinate proposals or fail closed."""

    try:
        problem = compile_problem(document)
        domains, pre_arc_product = _seed_domains(problem)
        removed = _arc_consistency(problem, domains)
        return _ready_result(
            problem,
            domains,
            pre_arc_product=pre_arc_product,
            arc_values_removed=removed,
        )
    except Exception as error:
        reason = (
            str(error)
            if isinstance(error, CSPNotApplicable)
            else f"UNEXPECTED_SYMBOLIC_FAILURE:{type(error).__name__}"
        )
        return {
            "schema_version": SCHEMA,
            "status": "NOT_APPLICABLE_BASELINE_FALLBACK",
            "reason": reason,
            "proposal_count": 0,
            "proposals": [],
            "selection_read_raw_target": False,
            "selection_used_case_id_family_truth_or_outcome": False,
            "target_set_completeness_claim": False,
            "authority_pass": False,
            "target_release": False,
            "baseline_fallback_required": True,
        }


def candidate_prejoin_or_baseline(
    document: Mapping[str, Any], untouched_baseline: object
) -> object:
    """Return baseline by identity on every non-ready or exceptional path."""

    try:
        result = build_proposals(document)
    except Exception:
        return untouched_baseline
    if result.get("status") != "PROPOSAL_READY_HOLD":
        return untouched_baseline
    return CandidatePrejoinHold(untouched_baseline, result)


def audit_untouched_full_replay(
    document: Mapping[str, Any], proposal_result: Mapping[str, Any]
) -> dict[str, Any]:
    """Audit raw-target replay after proposal generation without pruning it."""

    proposals = proposal_result.get("proposals")
    if not isinstance(proposals, list):
        raise CSPNotApplicable("PROPOSAL_LIST_MALFORMED")
    try:
        semantic, replay = _semantic_modules()
        artifact = semantic.compile_document(document)
    except Exception:
        return {
            "proposal_count_unchanged": len(proposals),
            "full_source_raw_target_replay_pass_count": 0,
            "full_replay_compile_failed": True,
            "authority_pass": False,
            "target_release": False,
        }
    passed = 0
    for proposal in proposals:
        raw = proposal.get("raw_coordinate_assignment")
        if not isinstance(raw, Mapping):
            continue
        try:
            raw_values = {
                str(name): sp.sympify(value["text"])
                for name, value in raw.items()
                if isinstance(value, Mapping) and isinstance(value.get("text"), str)
            }
            lifted = replay.materialize_lift_witness(document, artifact, raw_values)
            accepted, _reason = replay.verify_source_and_target_replay(
                document, artifact, raw_values, lifted
            )
        except Exception:
            accepted = False
        passed += int(accepted)
    return {
        "proposal_count_unchanged": len(proposals),
        "full_source_raw_target_replay_pass_count": passed,
        "full_replay_compile_failed": False,
        "proposal_order_or_membership_changed_by_target": False,
        "authority_pass": False,
        "target_release": False,
    }


__all__ = [
    "CSPContradiction",
    "CSPNotApplicable",
    "CSPResourceCap",
    "CandidatePrejoinHold",
    "Problem",
    "Relation",
    "audit_untouched_full_replay",
    "build_proposals",
    "candidate_prejoin_or_baseline",
    "compile_problem",
]
