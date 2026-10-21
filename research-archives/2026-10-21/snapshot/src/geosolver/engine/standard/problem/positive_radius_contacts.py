"""Necessary contact equations after removing a proven nonzero radius factor.

For a Circle(B+r*v,r), where B lies on an independent circumcircle(O,R),
internal tangency implies
  r * (2*((B-O).v + R) + r*(v.v-1)) = 0.
Circle's original construction domain requires r>0. The bracket is therefore
a necessary equation and avoids attraction to the excluded zero-radius branch.
Every original residual remains present, and final certification is unchanged.
"""

import ast
from functools import lru_cache

from geosolver.engine.standard.problem.zero_test_source import rational_constant
from geosolver.problem.expression_source import annotate_source, source_expression


def _parse(source):
    return annotate_source(ast.parse(source, mode="eval"), source).body


def _call(node, name, count):
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == name
        and len(node.args) == count
        and not node.keywords
    )


def _sum(a, b, sign=1):
    if b == "0":
        return a
    if a == "0":
        return b if sign == 1 else f"-({b})"
    return f"({a}){'+' if sign == 1 else '-'}({b})"


def _product(a, b):
    if a == "0" or b == "0":
        return "0"
    if a == "1":
        return b
    if b == "1":
        return a
    return f"({a})*({b})"


@lru_cache(maxsize=256)
def positive_radius_contact_plans(variables, constructions, equalities):
    definitions = {name: _parse(source) for name, source in constructions}

    def resolve(node):
        active = set()
        while isinstance(node, ast.Name) and node.id in definitions:
            if node.id in active:
                raise ValueError("cyclic construction")
            active.add(node.id)
            node = definitions[node.id]
        return node

    def depends(node, radius, active=frozenset()):
        if isinstance(node, ast.Name):
            if node.id == radius:
                return True
            if node.id in definitions:
                if node.id in active:
                    raise ValueError("cyclic construction")
                return depends(definitions[node.id], radius, active | {node.id})
        return any(depends(child, radius, active) for child in ast.iter_child_nodes(node))

    def coordinate(node):
        if isinstance(node, ast.Attribute) and node.attr in {"x", "y"}:
            point = resolve(node.value)
            if _call(point, "Point", 2):
                return point.args[0 if node.attr == "x" else 1]
        return node

    def canonical(node, active=frozenset()):
        if isinstance(node, ast.Name) and node.id in definitions:
            if node.id in active:
                raise ValueError("cyclic construction")
            return canonical(definitions[node.id], active | {node.id})
        if isinstance(node, ast.Attribute):
            reduced = coordinate(node)
            if reduced is not node:
                return canonical(reduced, active)
        if _call(node, "Center", 1):
            circle = resolve(node.args[0])
            if _call(circle, "Circumcircle", 3):
                return canonical(
                    ast.Call(func=ast.Name(id="Circumcenter"), args=circle.args, keywords=[]),
                    active,
                )
        try:
            value = rational_constant(node)
            return ("rational", value)
        except (ValueError, ArithmeticError):
            if isinstance(node, ast.Constant) and type(node.value) is float:
                raise ValueError("missing exact numeric token") from None
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

    def affine(node, radius):
        if not depends(node, radius):
            try:
                if rational_constant(node) == 0:
                    return "0", "0"
            except (ValueError, ArithmeticError):
                pass
            return source_expression(node), "0"
        if isinstance(node, ast.Name):
            if node.id == radius:
                return "0", "1"
            return affine(resolve(node), radius)
        if isinstance(node, ast.Attribute):
            reduced = coordinate(node)
            if reduced is not node:
                return affine(reduced, radius)
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.UAdd | ast.USub):
            a, b = affine(node.operand, radius)
            return (
                (a, b) if isinstance(node.op, ast.UAdd) else (_product("-1", a), _product("-1", b))
            )
        if isinstance(node, ast.BinOp):
            a, b = affine(node.left, radius)
            c, d = affine(node.right, radius)
            if isinstance(node.op, ast.Add | ast.Sub):
                sign = -1 if isinstance(node.op, ast.Sub) else 1
                return _sum(a, c, sign), _sum(b, d, sign)
            if isinstance(node.op, ast.Mult) and (b == "0" or d == "0"):
                return _product(a, c), _sum(_product(a, d), _product(b, c))
            if isinstance(node.op, ast.Div) and d == "0":
                return ("0" if a == "0" else f"({a})/({c})"), ("0" if b == "0" else f"({b})/({c})")
        raise ValueError("center is not affine in radius")

    sources = []
    try:
        for inner in definitions.values():
            inner = resolve(inner)
            # Only this primitive has the required strictly positive radius
            # construction domain; zero-radius or other circle-like objects
            # must never justify division by a radius.
            if not _call(inner, "Circle", 2):
                continue
            radius = inner.args[1]
            if not isinstance(radius, ast.Name) or radius.id not in variables:
                continue
            center = resolve(inner.args[0])
            if not _call(center, "Point", 2):
                continue
            try:
                (bx, vx), (by, vy) = (affine(arg, radius.id) for arg in center.args)
            except (ValueError, ArithmeticError):
                continue
            base = _parse(f"Point({bx},{by})")
            for outer_name, outer in definitions.items():
                outer = resolve(outer)
                if not _call(outer, "Circumcircle", 3) or depends(outer, radius.id):
                    continue
                if not any(canonical(base) == canonical(vertex) for vertex in outer.args):
                    continue
                outer_center = _parse(f"Center({outer_name})")
                gap = _parse(f"Radius({outer_name})-{radius.id}")
                found = False
                for lhs, rhs in equalities:
                    left, right = (
                        _parse(lhs),
                        _parse(str(rhs)),
                    )
                    for distance, target in ((resolve(left), right), (resolve(right), left)):
                        if not _call(distance, "Distance", 2) or canonical(target) != canonical(
                            gap
                        ):
                            continue
                        if {canonical(arg) for arg in distance.args} == {
                            canonical(inner.args[0]),
                            canonical(outer_center),
                        }:
                            found = True
                            break
                    if found:
                        break
                if not found:
                    continue
                o = f"Center({outer_name})"
                r = f"Radius({outer_name})"
                constant = f"2*((({bx})-{o}.x)*({vx})+(({by})-{o}.y)*({vy})+{r})"
                coefficient = f"((({vx})**2)+(({vy})**2)-1)"
                sources.append(
                    (
                        radius.id,
                        f"{constant}+{radius.id}*{coefficient}",
                        f"-({constant})/({coefficient})",
                    )
                )
        return tuple(dict.fromkeys(sources))
    except (ValueError, TypeError, SyntaxError, ArithmeticError, RecursionError):
        return ()


def positive_radius_contact_sources(variables, constructions, equalities):
    """Return only the necessary zero equations used by local refinement."""
    return tuple(
        plan[1] for plan in positive_radius_contact_plans(variables, constructions, equalities)
    )
