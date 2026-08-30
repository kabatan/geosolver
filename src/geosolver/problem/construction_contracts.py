"""Proof-gated lowering of constructions defined only on the constraint set.

Public expressions are unchanged. We only use incidences implied by explicit
equalities or construction identities; a nearby numeric point is not a proof.
"""

import ast
from dataclasses import replace
from functools import lru_cache

from geosolver.problem.expression_source import annotate_source, source_expression
from geosolver.problem.ir.schema import IRConstruction


def tree(source):
    return annotate_source(ast.parse(str(source), mode="eval"), str(source)).body


def key(node):
    return source_expression(node)


def call(node, name):
    return isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == name


@lru_cache(maxsize=512)
def _lower(constructions, equalities):
    definitions = {name: tree(source) for name, source in constructions}

    def resolve(node):
        seen = set()
        while isinstance(node, ast.Name) and node.id in definitions and node.id not in seen:
            seen.add(node.id)
            node = definitions[node.id]
        return node

    pairs = set()
    zero_sources = set()
    for left, right in equalities:
        a, b = tree(left), tree(right)
        pairs.update(((key(a), key(b)), (key(b), key(a))))
        if key(b) == "0":
            zero_sources.add(key(a))
            if isinstance(a, ast.BinOp) and isinstance(a.op, ast.Sub):
                pairs.update(((key(a.left), key(a.right)), (key(a.right), key(a.left))))

    def equal(a, b):
        return key(a) == key(b) or (key(a), key(b)) in pairs

    def incident(point, obj, *, constraints=True, seen=()):
        identity = (key(point), key(obj))
        if identity in seen:
            return False
        seen = (*seen, identity)
        shape, pdef = resolve(obj), resolve(point)

        def same(a, b):
            return equal(a, b) if constraints else key(a) == key(b)

        if constraints and key(tree(f"OnCircle({key(point)},{key(obj)})")) in zero_sources:
            return True
        if call(shape, "Line"):
            return any(same(point, p) for p in shape.args[:2])
        if call(shape, "Circumcircle") or call(shape, "CircleThroughThreePoints"):
            return any(same(point, p) for p in shape.args[:3])
        if call(pdef, "PointOnCircle") and same(pdef.args[0], obj):
            return True
        if call(pdef, "Intersect") and any(same(obj, arg) for arg in pdef.args[:2]):
            return True
        if not call(shape, "Circle") or len(shape.args) != 2:
            return False
        center, radius = shape.args
        if constraints and any(
            equal(tree(f"Distance({key(p)},{key(q)})"), radius)
            for p, q in ((point, center), (center, point))
        ):
            return True
        # A small exact scalar identity also recognizes Cartesian sin/cos
        # parametrizations. Unknown operations fail closed, never numerically.
        try:
            from geosolver.problem.scalar_geometry import ScalarGeometry

            geometry = ScalarGeometry(dict(constructions))
            x, y = geometry.point(point)
            u, v = geometry.point(center)
            r = geometry.scalar(radius)
            from geosolver.runtime.symbolic import request

            return request("scalar_identity", str((x - u) ** 2 + (y - v) ** 2 - r**2))
        except (ValueError, TypeError, KeyError, NotImplementedError):
            return False

    guards, evidence, output = [], [], []

    class Lower(ast.NodeTransformer):
        def visit_Call(self, node):
            node = self.generic_visit(node)
            if (
                isinstance(node.func, ast.Name)
                and node.func.id in {"Tangent", "TangentLine"}
                and len(node.args) >= 2
            ):
                point, circle = node.args[:2]
                # Public aliases also permit the reversed argument order.
                if call(resolve(point), "Circle") or call(resolve(point), "Circumcircle"):
                    point, circle = circle, point
                # Keep the original circle construction in the snapshot,
                # including its positive-radius/noncollinearity checks.
                if (
                    isinstance(circle, ast.Name)
                    and circle.id in definitions
                    and incident(point, circle, constraints=False)
                ):
                    shape = resolve(circle)
                    center = (
                        key(shape.args[0])
                        if call(shape, "Circle")
                        else f"Circumcenter({','.join(key(a) for a in shape.args[:3])})"
                    )
                    evidence.append(("tangent_incidence", key(node)))
                    return tree(f"PerpendicularLine({key(point)},Line({key(point)},{center}))")
            if node is current_root and call(node, "Intersect") and len(node.args) == 2:
                exclusion = next((kw.value for kw in node.keywords if kw.arg == "exclude"), None)
                # Limit the proof to line/circle intersections with at most two
                # points. Arc membership and infinite intersections stay native.
                shapes = [resolve(arg) for arg in node.args]
                supported = all(
                    any(
                        call(s, name)
                        for name in ("Circle", "Circumcircle", "CircleThroughThreePoints", "Line")
                    )
                    for s in shapes
                )
                if (
                    exclusion is not None
                    and supported
                    and len(node.keywords) == 1
                    and all(incident(exclusion, obj) for obj in node.args)
                ):
                    evidence.append(("excluded_known_intersection", key(node)))
                    node.keywords[0].arg = "far"
                    guards.append((current_name, key(exclusion)))
            return node

    for current_name, source in constructions:
        current_root = tree(source)
        node = Lower().visit(current_root)
        output.append((current_name, key(node)))
    return tuple(output), tuple(guards), tuple(evidence)


def lower_construction_contracts(spec):
    pairs = tuple(
        (source, str(target))
        for source, target in zip(
            spec.constraints, spec.v or [0] * len(spec.constraints), strict=True
        )
    )
    constructions = tuple((item.name, item.expr) for item in spec.construction)
    lowered, guards, evidence = _lower(constructions, pairs)
    if not evidence:
        return spec
    return replace(
        spec,
        construction=[IRConstruction(name, source) for name, source in lowered],
        guards=list(
            dict.fromkeys(
                [*spec.guards, *(f"Distance({name},{point})>0" for name, point in guards)]
            )
        ),
    )
