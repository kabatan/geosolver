"""Necessary smooth incidence equations supplement original distance gaps.

OnSegment uses a triangle-inequality gap with a double zero in perpendicular
motion. Every segment incidence also has zero oriented area, including the
degenerate segment. Keep the original residual and guards; add this consequence
only to expose first-order information to search and verification.
"""

import ast
from dataclasses import replace
from functools import lru_cache


@lru_cache(maxsize=1024)
def necessary_incidence_residuals(source, constructions=()):
    from geosolver.engine.standard.problem.zero_test_source import zero_test_call

    node = zero_test_call(source)
    if not (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "OnSegment"
        and len(node.args) == 3
        and not node.keywords
    ):
        return ()
    if _construction_implies_collinear(node.args, constructions):
        return ()
    # Preserve each original decimal token, not ast.unparse's binary rounding.
    args = [ast.get_source_segment(source, argument) for argument in node.args]
    if any(argument is None for argument in args):
        return ()
    p, a, b = (f"({argument})" for argument in args)
    return (f"(({b}.x-{a}.x)*({p}.y-{a}.y)-({b}.y-{a}.y)*({p}.x-{a}.x))",)


def augment_incidence_clauses(clauses, constructions=()):
    augmented = tuple(
        (
            *clause,
            *dict.fromkeys(
                extra
                for source in clause
                for extra in necessary_incidence_residuals(source, constructions)
                if extra not in clause
            ),
        )
        for clause in clauses
    )
    return augmented if max(map(len, augmented), default=0) <= 16 else clauses


def lower_incidence_equalities(spec):
    constructions = tuple((item.name, item.expr) for item in spec.construction)
    targets = spec.v or [0] * len(spec.constraints)
    extra = tuple(
        dict.fromkeys(
            equation
            for source, target in zip(spec.constraints, targets, strict=True)
            for equation in necessary_incidence_residuals(f"({source})-({target})", constructions)
            if equation not in spec.constraints
        )
    )
    if not extra:
        return spec
    return replace(
        spec, constraints=[*spec.constraints, *extra], v=[*targets, *([0] * len(extra))], m=None
    )


def _construction_implies_collinear(arguments, constructions):
    """Decline a numerically useless incidence row proved by construction.

    Projection feet and circle/line contact points already lie on their line.
    Their determinant is an identity, whose cancellation noise must not become
    a new equation in the numerical correction system. Original OnSegment still
    checks both incidence and the endpoint inequalities.
    """
    from geosolver.engine.standard.problem.zero_test_source import rational_constant
    from geosolver.problem.expression_source import annotate_source

    def parse(source):
        return annotate_source(ast.parse(source, mode="eval"), source).body

    definitions = {name: parse(source) for name, source in constructions}

    def resolve(node):
        active = set()
        while isinstance(node, ast.Name) and node.id in definitions:
            if node.id in active:
                raise ValueError("cyclic construction")
            active.add(node.id)
            node = definitions[node.id]
        return node

    def canonical(node, active=frozenset()):
        if isinstance(node, ast.Name) and node.id in definitions:
            if node.id in active:
                raise ValueError("cyclic construction")
            return canonical(definitions[node.id], active | {node.id})
        try:
            return ("rational", rational_constant(node))
        except (ValueError, ArithmeticError):
            if isinstance(node, ast.Constant) and type(node.value) is float:
                raise ValueError("missing numeric token") from None
        if isinstance(node, ast.AST):
            return (
                type(node).__name__,
                tuple(
                    (name, canonical(value, active))
                    for name, value in ast.iter_fields(node)
                    if name != "ctx"
                ),
            )
        if isinstance(node, list):
            return tuple(canonical(value, active) for value in node)
        return node

    def call(node, name, arity):
        return (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == name
            and len(node.args) == arity
            and not node.keywords
        )

    try:
        point, a, b = arguments
        endpoints = (canonical(a), canonical(b))
        if canonical(point) in endpoints or endpoints[0] == endpoints[1]:
            return True
        built = resolve(point)
        if call(built, "Midpoint", 2):
            return {canonical(arg) for arg in built.args} == set(endpoints)
        if call(built, "FootOfPerpendicular", 2):
            lines = (resolve(built.args[1]),)
        elif call(built, "ContactPoint", 2):
            resolved = tuple(resolve(arg) for arg in built.args)
            if not any(
                call(arg, "Circle", 2) or call(arg, "Circumcircle", 3) or call(arg, "Incircle", 3)
                for arg in resolved
            ):
                return False
            lines = resolved
        else:
            return False
        return any(
            call(line, "Line", 2) and {canonical(arg) for arg in line.args} == set(endpoints)
            for line in lines
        )
    except (ValueError, TypeError, ArithmeticError, RecursionError):
        return False
