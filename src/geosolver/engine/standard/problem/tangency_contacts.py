"""Simple tangency equations when a contact point has proven incidence.

A line through a point on a circle is tangent exactly when its direction is
perpendicular to the radius at that point. The usual squared-distance residual
has a double zero. Construction incidence or additional equality constraints
can prove the two incidences; the complete original system remains mandatory.
"""

import ast
from functools import lru_cache

from geosolver.engine.standard.problem.zero_test_source import rational_constant, zero_test_call
from geosolver.problem.expression_source import annotate_source, source_expression


def _parse(source):
    return annotate_source(ast.parse(source, mode="eval"), source).body


@lru_cache(maxsize=512)
def contact_tangency_source(left, right, constructions, equalities=()):
    """Return a contact-radius dot product, or None without proven incidence."""
    definitions = {name: _parse(source) for name, source in constructions}

    def resolve(node):
        seen = set()
        while isinstance(node, ast.Name) and node.id in definitions:
            if node.id in seen:
                raise ValueError("cyclic construction")
            seen.add(node.id)
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
                raise ValueError("missing exact numeric token") from None
        if isinstance(node, ast.AST):
            return (
                type(node).__name__,
                tuple(
                    (name, canonical(value, active))
                    for name, value in ast.iter_fields(node)
                    if name not in {"ctx"}
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

    equations, zero_calls, candidates = [], [], []
    for lhs, rhs in equalities:
        a, b = _parse(lhs), _parse(str(rhs))
        equations.extend(((a, b), (b, a)))
        try:
            is_zero = rational_constant(b) == 0
        except (ValueError, ArithmeticError):
            is_zero = False
        if is_zero:
            node = zero_test_call(lhs)
            if node is not None:
                zero_calls.append(node)
                if node.args:
                    candidates.append(node.args[0])
    candidates.extend(ast.Name(id=name, ctx=ast.Load()) for name in definitions)

    def same(a, b):
        return canonical(a) == canonical(b)

    def circle_contains(point, circle_source):
        circle_ast = _parse(circle_source)
        circle_node = resolve(circle_ast)
        center_ast = (
            circle_node.args[0]
            if call(circle_node, "Circle", 2)
            else _parse(f"Center({circle_source})")
        )
        radius_ast = (
            circle_node.args[1]
            if call(circle_node, "Circle", 2)
            else _parse(f"Radius({circle_source})")
        )
        if call(circle_node, "Circumcircle", 3) and any(same(point, p) for p in circle_node.args):
            return True
        built = resolve(point)
        if isinstance(built, ast.Call) and isinstance(built.func, ast.Name):
            if built.func.id == "Intersect" and any(same(arg, circle_ast) for arg in built.args):
                return True
            if (
                built.func.id == "IncircleContactPoint"
                and call(circle_node, "Incircle", 3)
                and len(built.args) >= 3
                and all(same(a, b) for a, b in zip(built.args[:3], circle_node.args, strict=True))
            ):
                return True
        if any(
            call(n, "OnCircle", 2) and same(n.args[0], point) and same(n.args[1], circle_ast)
            for n in zero_calls
        ):
            return True
        return any(
            call(resolve(a), "Distance", 2)
            and same(b, radius_ast)
            and {canonical(arg) for arg in resolve(a).args}
            == {canonical(point), canonical(center_ast)}
            for a, b in equations
        )

    try:
        left_node, right_node = (
            _parse(left),
            _parse(right),
        )
        for line_node, circle_node, circle_source in (
            (resolve(left_node), resolve(right_node), right),
            (resolve(right_node), resolve(left_node), left),
        ):
            if not call(line_node, "Line", 2):
                continue
            if not (
                call(circle_node, "Circle", 2)
                or call(circle_node, "Circumcircle", 3)
                or call(circle_node, "Incircle", 3)
            ):
                continue

            def line_contains(point, line_node=line_node):
                if any(same(point, p) for p in line_node.args):
                    return True
                built = resolve(point)
                if (
                    isinstance(built, ast.Call)
                    and isinstance(built.func, ast.Name)
                    and built.func.id == "Intersect"
                    and any(same(arg, line_node) for arg in built.args)
                ):
                    return True
                for n in zero_calls:
                    if (
                        call(n, "OnLine", 2)
                        and same(n.args[0], point)
                        and same(n.args[1], line_node)
                    ):
                        return True
                    if (
                        call(n, "OnLine", 3)
                        and same(n.args[0], point)
                        and {canonical(arg) for arg in n.args[1:]}
                        == {canonical(arg) for arg in line_node.args}
                    ):
                        return True
                    if call(n, "Collinear", 3) and {canonical(arg) for arg in n.args} == {
                        canonical(point),
                        *(canonical(arg) for arg in line_node.args),
                    }:
                        return True
                return False

            contact = next(
                (
                    p
                    for p in (*line_node.args, *candidates)
                    if circle_contains(p, circle_source) and line_contains(p)
                ),
                None,
            )
            if contact is None:
                continue
            a, b = (f"({source_expression(point)})" for point in line_node.args)
            p = f"({source_expression(contact)})"
            center = f"Center({circle_source})"
            return (
                f"(({center}.x-{p}.x)*({b}.x-{a}.x)+({center}.y-{p}.y)*({b}.y-{a}.y))"
                f"/Distance({a},{b})"
            )

        def is_circle(node):
            return (
                call(node, "Circle", 2)
                or call(node, "Circumcircle", 3)
                or call(node, "Incircle", 3)
            )

        if is_circle(resolve(left_node)) and is_circle(resolve(right_node)):
            contact = next(
                (p for p in candidates if circle_contains(p, left) and circle_contains(p, right)),
                None,
            )
            if contact is not None:
                p = f"({source_expression(contact)})"
                a, b = f"Center({left})", f"Center({right})"
                # Given a shared point, tangent circles have collinear radii.
                # This cross product has a simple zero at a contact, whereas
                # the distance between centers has a double zero.
                return f"(({a}.x-{p}.x)*({b}.y-{p}.y)-({a}.y-{p}.y)*({b}.x-{p}.x))/Radius({left})"
    except (ValueError, TypeError, RecursionError):
        return None
    return None


@lru_cache(maxsize=256)
def distance_contact_sources(constructions, equalities):
    """Prove contacts expressed as Distance(center,line)=circle radius.

    Only an exactly matching Circle(center,radius) construction supplies the
    circle. The contact itself still needs an independent incidence proof.
    """
    definitions = {name: _parse(source) for name, source in constructions}

    def resolve(node):
        seen = set()
        while isinstance(node, ast.Name) and node.id in definitions:
            if node.id in seen:
                raise ValueError("cyclic construction")
            seen.add(node.id)
            node = definitions[node.id]
        return node

    def call(node, name, count):
        return (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == name
            and len(node.args) == count
            and not node.keywords
        )

    def same(a, b):
        return source_expression(resolve(a)) == source_expression(resolve(b))

    result = {}
    try:
        circles = [(name, resolve(node)) for name, node in definitions.items()]
        circles = [(name, node) for name, node in circles if call(node, "Circle", 2)]
        for index, (lhs, rhs) in enumerate(equalities):
            a, b = _parse(lhs), _parse(str(rhs))
            for distance, radius in ((resolve(a), b), (resolve(b), a)):
                if not call(distance, "Distance", 2):
                    continue
                for point, line in (
                    (distance.args[0], distance.args[1]),
                    (distance.args[1], distance.args[0]),
                ):
                    if not call(resolve(line), "Line", 2):
                        continue
                    for name, circle in circles:
                        if not same(point, circle.args[0]) or not same(radius, circle.args[1]):
                            continue
                        source = contact_tangency_source(
                            source_expression(line), name, constructions, equalities
                        )
                        if source is not None:
                            result[index] = source
        return result
    except (ValueError, TypeError, RecursionError):
        return {}
