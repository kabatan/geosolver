"""Fail-closed, independent numerical checking of the public GMBL configurations.

``check_configuration(text, witness, tolerance="1e-6", dps=80)`` accepts::

    {"points": {"A": ["0", "0"]},
     "lines": {"l": ["0", "1", "0"]},       # ax + by + c = 0
     "circles": {"O": {"center": ["0", "0"], "radius": "1"}},
     "choices": {"commands/3/1/0": ["1", "0"]}}  # optional unnamed branches

Every declared object is required. Extra objects are ignored and cannot improve
normalization. ``choices`` never bypasses membership or branch verification.
Goal clauses are reported separately and cannot make an invalid assumption valid.
This checker checks mathematical meanings, not GMB's weighted loss function,
hidden sampling restrictions, artificial 0.1 point separation, or 0.2 segment inset.
The original IMO text can impose additional conditions absent from the GMBL;
``valid`` alone MUST NOT be labelled original-problem validity or existence proof.
"""

from __future__ import annotations

import re
from collections.abc import Mapping

from benchmarks.gmb_comparison.checker_geometry import (
    CheckError,
    Circle,
    Geometry,
    Line,
    Number,
    Point,
    cross,
    dot,
)

CHECKER_POLICY = {
    "version": "gmbl-geometric-witness-v1",
    "default_tolerance": "1e-6",
    "reporting_tolerances": ["1e-3", "1e-6", "1e-9"],
    "default_dps": 80,
    "normalization": "first distinct declared point pair; otherwise first positive circle radius",
    "scalar_measurements": "length/area literals retain the original witness units",
    "local_scales": "construction feature lengths reused by incidence; not all-point diameter",
    "line_comparison": (
        "angle and local construction-anchor incidence; unanchored free lines use chart origin"
    ),
    "equality": "dimensionless absolute residual <= tolerance",
    "strict": "positive margin > tolerance; positive smaller margin is unresolved",
    "closed": "nonnegative margin; small negative margins are unresolved, never passed",
    "param_on_segment": "open segment (finite logistic parameter)",
    "assert_on_segment": "closed segment, without upstream's artificial 20% inset",
    "param_on_ray": "positive ray parameter, excluding origin",
    "assert_on_ray": "nonnegative ray parameter, including origin",
    "polygon": "strictly convex polygon in the declared cyclic order, either orientation",
    "param_in_polygon": "strict interior of a strictly convex polygon",
    "assert_in_polygon": "closed interior of a strictly convex polygon",
    "minor_arc": "strict minor arc; coincident or antipodal endpoints unresolved/invalid",
    "arbitrary_intersection": "either distinct real branch; no invented choice for unnamed terms",
    "selector_tie": "unresolved (no arbitrary tie-breaking)",
    "nonintersecting_figures": "failed or unresolved near numerical boundary; never fake points",
    "all_point_distinctness": "not imposed",
    "original_problem_validation": "requires independent original-text supplements",
    "independent_existence_proof": False,
}

TERM_ARITIES = {
    "line": {2},
    "para-at": {2},
    "perp-at": {2},
    "perp-bis": {2},
    "i-bisector": {3},
    "reflect-ll": {2},
    "inter-ll": {2},
    "inter-lc": {3},
    "inter-cc": {3},
    "midp": {2},
    "midp-from": {2},
    "foot": {2},
    "reflect-pl": {2},
    "circumcenter": {3},
    "orthocenter": {3},
    "centroid": {3},
    "incenter": {3},
    "excenter": {3},
    "origin": {1},
    "amidp-opp": {3},
    "amidp-same": {3},
    "circ": {3},
    "circumcircle": {3},
    "incircle": {3},
    "excircle": {3},
    "coa": {2},
    "diam": {1, 2},
    "radius": {1},
    "dist": {2},
    "area": {3},
    "uangle": {3},
    "add": {2},
    "sub": {2},
    "mul": {2},
    "div": {2},
    "pow": {2},
    "sqrt": {1},
    "neg": {1},
}
PREDICATE_ARITIES = {
    "eq": {2},
    "=": {2},
    "gt": {2},
    "gte": {2},
    "lt": {2},
    "lte": {2},
    ">": {2},
    ">=": {2},
    "<": {2},
    "<=": {2},
    "cong": {4},
    "coll": {3},
    "concur": {3},
    "para": {2},
    "perp": {2},
    "right": {3},
    "right-tri": {3},
    "midp": {3},
    "on-line": {2},
    "on-circ": {2},
    "on-seg": {3},
    "on-ray": {3},
    "same-side": {3},
    "opp-sides": {3},
    "tangent-lc": {2},
    "tangent-cc": {2},
    "incenter": {4},
    "circumcenter": {4},
    "orthocenter": {4},
    "centroid": {4},
    "i-bisector": {4},
    "eq-ratio": {8},
}
SELECTOR_ARITIES = {"rs-neq": {1}, "rs-closer-to-p": {1}, "rs-opp-sides": {2}}
PARAM_ARITIES = {
    "on-seg": {2},
    "on-ray": {2},
    "on-ray-opp": {2},
    "on-circ": {1},
    "on-line": {1},
    "on-minor-arc": {3},
    "on-major-arc": {3},
    "tangent-lc": {1},
    "tangent-cl": {1},
}


def parse_gmbl(text):
    """Parse the tiny S-expression syntax without importing the upstream parser."""
    if not isinstance(text, str):
        raise CheckError("invalid_source", "GMBL source must be text")
    tokens = re.findall(r"\(|\)|[^\s()]+", re.sub(r";[^\n]*", "", text))
    stack, commands = [], []
    for token in tokens:
        if token == "(":
            stack.append([])
        elif token == ")":
            if not stack:
                raise CheckError("invalid_source", "unmatched closing parenthesis")
            node = tuple(stack.pop())
            if not node:
                raise CheckError("invalid_source", "empty expression")
            (stack[-1] if stack else commands).append(node)
        elif not stack:
            raise CheckError("invalid_source", "atom outside a command")
        else:
            stack[-1].append(token)
    if stack or not commands:
        raise CheckError("invalid_source", "unclosed or empty source")
    return tuple(commands)


def sexpr(node):
    return node if isinstance(node, str) else "(" + " ".join(map(sexpr, node)) + ")"


def _operator(node):
    if not isinstance(node, tuple) or not node or not isinstance(node[0], str):
        raise CheckError("invalid_expression", "expression requires an operator")
    return node[0].lower()


def _arity(node, arities):
    op = _operator(node)
    if op not in arities:
        raise CheckError("unsupported_symbol", op, "unsupported")
    if len(node) - 1 not in arities[op]:
        raise CheckError("invalid_arity", sexpr(node))


def declarations(commands):
    result = {}
    for node in commands:
        op = _operator(node)
        if op not in {"param", "define", "assert", "eval"}:
            raise CheckError("unsupported_command", op, "unsupported")
        if op in {"assert", "eval"}:
            if len(node) != 2:
                raise CheckError("invalid_command", sexpr(node))
            continue
        if len(node) not in ({3, 4} if op == "param" else {4}):
            raise CheckError("invalid_command", sexpr(node))
        if isinstance(node[1], tuple):
            if op != "param" or len(node) != 3:
                raise CheckError("invalid_joint_parameter", sexpr(node))
            names, kind = node[1], "point"
        else:
            names, kind = [node[1]], node[2]
        if kind not in {"point", "line", "circle"}:
            raise CheckError("unsupported_object_type", kind, "unsupported")
        for name in names:
            if not isinstance(name, str) or name in result or name.lower() == "pi":
                raise CheckError("invalid_declaration", str(name))
            result[name] = kind
    return result


def inspect_gmbl(text):
    """Static coverage only: deliberately does not claim a geometric witness exists."""
    symbols, issues = set(), []
    try:
        commands = parse_gmbl(text)
        declared = declarations(commands)
    except CheckError as exc:
        return {"supported": False, "issues": [{"code": exc.code, "message": str(exc)}]}

    def visit(node, mode="term"):
        if isinstance(node, str):
            if mode == "selector" and node != "rs-arbitrary":
                raise CheckError("unsupported_selector", node, "unsupported")
            if (
                mode != "selector"
                and node not in declared
                and node != "pi"
                and not re.fullmatch(r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?", node)
            ):
                raise CheckError("unknown_reference", node)
            return
        op = _operator(node)
        symbols.add(op)
        if mode == "predicate" and op == "not":
            if len(node) != 2:
                raise CheckError("invalid_arity", sexpr(node))
            visit(node[1], "predicate")
            return
        if mode == "predicate" and op in {"cycl", "in-poly"}:
            if len(node) < 5:
                raise CheckError("invalid_arity", sexpr(node))
        elif mode == "parameter" and op == "in-poly":
            if len(node) < 4:
                raise CheckError("invalid_arity", sexpr(node))
        else:
            table = {
                "term": TERM_ARITIES,
                "predicate": PREDICATE_ARITIES,
                "selector": SELECTOR_ARITIES,
                "parameter": PARAM_ARITIES,
            }[mode]
            _arity(node, table)
        for i, arg in enumerate(node[1:]):
            visit(
                arg,
                "selector"
                if mode == "term" and op in {"inter-lc", "inter-cc"} and i == 2
                else "term",
            )

    for i, node in enumerate(commands):
        try:
            if node[0] in {"assert", "eval"}:
                visit(node[1], "predicate")
            elif node[0] == "define":
                visit(node[3])
            elif isinstance(node[1], tuple):
                method = node[2]
                name = method if isinstance(method, str) else _operator(method)
                symbols.add(name)
                if name not in {"triangle", "acute-tri", "equi-tri", "polygon", "right-tri"}:
                    raise CheckError("unsupported_parameterization", name, "unsupported")
                if not isinstance(method, str) and (len(method) != 2 or method[1] not in node[1]):
                    raise CheckError("invalid_parameterization", sexpr(node))
            elif len(node) == 4:
                visit(node[3], "parameter")
        except CheckError as exc:
            issues.append(
                {
                    "source_path": f"commands/{i}",
                    "code": exc.code,
                    "message": str(exc),
                    "status": exc.status,
                }
            )
    return {
        "supported": not issues,
        "declarations": declared,
        "symbols": sorted(symbols),
        "issues": issues,
        "statement": "syntax coverage only; not original-text approval",
    }


def _status(records):
    statuses = {item["status"] for item in records}
    for status in ["failed", "unsupported", "unresolved"]:
        if status in statuses:
            return status
    return "passed"


class WitnessChecker:
    def __init__(self, commands, witness, tolerance, dps):
        self.g = Geometry(tolerance, dps)
        self.commands = commands
        self.declared = declarations(commands)
        self.objects = {}
        self.available = set()
        self.choices = witness.get("choices", {})
        self.used_choices = set()
        self.branch_cache = {}
        self.term_values = {}
        if not isinstance(self.choices, Mapping):
            raise CheckError(
                "invalid_choices", "choices must be a mapping of source paths to points"
            )
        # Read only declared objects: extra user objects never change geometric scales.
        for name, kind in self.declared.items():
            values = witness.get(
                {"point": "points", "line": "lines", "circle": "circles"}[kind], {}
            )
            if not isinstance(values, Mapping) or name not in values:
                raise CheckError("missing_witness_object", f"missing {kind} {name}")
            raw = values[name]
            if kind == "point":
                value = self.g.point(raw)
            elif kind == "line":
                value = self.g.coefficients(raw)
            else:
                if not isinstance(raw, Mapping) or set(raw) != {"center", "radius"}:
                    raise CheckError("invalid_circle", "circle requires center and radius")
                value = self.g.circle(self.g.point(raw["center"]), self.g.scalar(raw["radius"]))
            self.objects[name] = value
        points = [(name, obj) for name, obj in self.objects.items() if isinstance(obj, Point)]
        scale, anchors = self.g.mp.zero, []
        origin = points[0][1] if points else Point(self.g.mp.zero, self.g.mp.zero)
        for name, point in points[1:]:
            if (distance := self.g.dist(origin, point)) > 0:
                scale, anchors = distance, [points[0][0], name]
                break
        if scale == 0:
            scale = next(
                (obj.radius for obj in self.objects.values() if isinstance(obj, Circle)), 1
            )
        self.normalization = {
            "anchors": anchors,
            "scale": self.g.fmt(scale),
            "origin": [self.g.fmt(origin.x), self.g.fmt(origin.y)],
        }
        self.origin, self.scale = origin, scale
        for name, value in self.objects.items():
            if isinstance(value, Point):
                value = (value - origin).times(1 / scale)
            elif isinstance(value, Line):
                value = Line(value.n, (value.c + dot(value.n, origin)) / scale, self.g.mp.one)
            else:
                value = Circle(
                    (value.center - origin).times(1 / scale),
                    value.radius / scale,
                    value.radius / scale,
                )
            self.objects[name] = value

    def require_type(self, value, kind):
        if not isinstance(value, kind):
            raise CheckError(
                "type_mismatch", f"expected {kind.__name__}, got {type(value).__name__}"
            )
        return value

    def feature_scale(self, *values, fallback=None):
        lengths = []
        for value in values:
            scale = getattr(value, "span", None)
            if scale is None and isinstance(value, Circle):
                scale = value.radius
            if scale is not None and scale > 0:
                lengths.append(scale)
        if fallback is not None and fallback > 0:
            lengths.append(fallback)
        return min(lengths) if lengths else self.g.mp.one

    def point_scale(self, op, args, result):
        g = self.g
        if op == "inter-lc":
            return self.feature_scale(args[1])
        if op == "inter-cc":
            return self.feature_scale(*args[:2])
        if op in {"inter-ll", "foot", "reflect-pl"}:
            return self.feature_scale(*args)
        if op == "origin":
            return self.feature_scale(args[0])
        if op in {"midp", "midp-from"}:
            distance = g.dist(*args)
            return min(distance, self.feature_scale(*args, fallback=distance))
        if op in {
            "circumcenter",
            "orthocenter",
            "centroid",
            "incenter",
            "excenter",
            "amidp-opp",
            "amidp-same",
        }:
            sides = [g.dist(args[i], args[(i + 1) % 3]) for i in range(3)]
            base = min(sides)
            if op in {"incenter", "excenter"}:
                base = min(base, abs(g.side(result, g.through(args[1], args[2]))))
            return min(base, self.feature_scale(*args, fallback=base))
        raise CheckError("missing_point_scale", op, "unsupported")

    def term(self, node, path, hint=None):
        result = self._term(node, path, hint)
        if isinstance(node, tuple):
            args = [
                self.term_values[f"{path}/{i}"]
                for i in range(len(node) - 1)
                if f"{path}/{i}" in self.term_values
            ]
            if isinstance(result, Point):
                result = Point(result.x, result.y, self.point_scale(_operator(node), args, result))
            elif isinstance(result, Line):
                result = Line(
                    result.n,
                    result.c,
                    self.feature_scale(*args, fallback=result.span),
                    result.anchor,
                )
            elif isinstance(result, Circle):
                base = result.radius
                if _operator(node) in {"circ", "circumcircle", "incircle", "excircle"}:
                    base = min(base, *(self.g.dist(args[i], args[(i + 1) % 3]) for i in range(3)))
                result = Circle(
                    result.center, result.radius, self.feature_scale(*args, fallback=base)
                )
        self.term_values[path] = result
        return result

    def _term(self, node, path, hint=None):
        self.g.path = path
        if isinstance(node, str):
            if node == "pi":
                return Number(self.g.mp.pi, self.g.mp.pi)
            if node in self.objects:
                if node not in self.available:
                    raise CheckError("forward_reference", node)
                return self.objects[node]
            number = self.g.scalar(node)
            return Number(number, abs(number))
        _arity(node, TERM_ARITIES)
        op, raw = _operator(node), node[1:]
        if op in {"inter-lc", "inter-cc"}:
            left = self.term(raw[0], f"{path}/0")
            right = self.term(raw[1], f"{path}/1")
            self.g.path = path
            if op == "inter-lc":
                points = self.g.line_circle(
                    self.require_type(left, Line), self.require_type(right, Circle)
                )
                local_scale = self.feature_scale(right)
            else:
                points = self.g.circle_circle(
                    self.require_type(left, Circle), self.require_type(right, Circle)
                )
                local_scale = self.feature_scale(left, right)
            return self.select(points, raw[2], node, path, hint, local_scale, (left, right))
        args = [self.term(arg, f"{path}/{i}") for i, arg in enumerate(raw)]
        self.g.path = path
        g = self.g
        if op in {"add", "sub", "mul", "div", "pow", "sqrt", "neg"}:
            args = [self.require_type(arg, Number) for arg in args]
            a = args[0]
            b = args[1] if len(args) > 1 else None
            if op in {"add", "sub"}:
                return Number(a.value + (b.value if op == "add" else -b.value), a.scale + b.scale)
            if op == "mul":
                return Number(a.value * b.value, a.scale * b.scale)
            if op == "div":
                g.positive(abs(b.value), b.scale, "zero_denominator")
                return Number(a.value / b.value, a.scale / abs(b.value))
            if op == "neg":
                return Number(-a.value, a.scale)
            if op == "sqrt":
                if a.value < 0:
                    raise CheckError("negative_radicand", "sqrt requires nonnegative input")
                return Number(g.mp.sqrt(a.value), g.mp.sqrt(a.scale))
            result = g.mp.power(a.value, b.value)
            if not isinstance(result, type(g.mp.one)) or not g.mp.isfinite(result):
                raise CheckError("undefined_power", "power must be finite and real")
            return Number(result, max(abs(result), abs(g.mp.power(a.scale, b.value))))
        if op in {"origin", "radius"} or (op == "diam" and len(args) == 1):
            circle = self.require_type(args[0], Circle)
            if op == "origin":
                return circle.center
            length = circle.radius * self.scale * (2 if op == "diam" else 1)
            return Number(length, length)
        if op in {"para-at", "perp-at", "foot", "reflect-pl"}:
            point, line = self.require_type(args[0], Point), self.require_type(args[1], Line)
            return {
                "para-at": g.parallel_at,
                "perp-at": g.perpendicular_at,
                "foot": g.foot,
                "reflect-pl": g.reflect_point,
            }[op](point, line)
        if op in {"inter-ll", "reflect-ll"}:
            args = [self.require_type(arg, Line) for arg in args]
            return (g.intersect_lines if op == "inter-ll" else g.reflect_line)(*args)
        args = [self.require_type(arg, Point) for arg in args]
        if op == "line":
            return g.through(*args)
        if op == "perp-bis":
            return g.perpendicular_at((args[0] + args[1]).times(g.mp.mpf("0.5")), g.through(*args))
        if op == "i-bisector":
            return g.bisector(*args)
        if op == "midp":
            return (args[0] + args[1]).times(g.mp.mpf("0.5"))
        if op == "midp-from":
            return args[0].times(2) - args[1]
        if op in {"circumcenter", "orthocenter", "centroid", "incenter", "excenter"}:
            return g.center(op, *args)
        if op in {"circ", "circumcircle", "incircle", "excircle"}:
            return g.triangle_circle(op, *args)
        if op in {"coa", "diam"}:
            center = args[0] if op == "coa" else (args[0] + args[1]).times(g.mp.mpf("0.5"))
            return g.circle(center, g.dist(center, args[1]))
        if op in {"amidp-opp", "amidp-same"}:
            point = g.arc_midpoint(*args)
            return point if op == "amidp-opp" else g.circumcenter(*args).times(2) - point
        if op == "dist":
            distance = g.dist(*args) * self.scale
            return Number(distance, distance)
        if op == "uangle":
            return Number(g.angle(*args), g.mp.pi)
        if op == "area":
            area = abs(cross(args[1] - args[0], args[2] - args[0])) / 2
            return Number(area * self.scale**2, (g.spread(*args) * self.scale) ** 2)
        raise CheckError("unsupported_term", op, "unsupported")

    def construction_checks(self, node, path, actual, expected):
        """Evaluate the provided point in its local defining geometric relations."""
        g, op = self.g, _operator(node)
        args = [
            self.term_values[f"{path}/{i}"]
            for i in range(len(node) - 1)
            if f"{path}/{i}" in self.term_values
        ]
        scale = expected.span
        errors = {}
        if op == "inter-ll":
            errors = {
                f"line_membership/{i}": abs(g.side(actual, line)) / scale
                for i, line in enumerate(args)
            }
        elif op in {"foot", "reflect-pl"}:
            point, line = args
            on_line = actual if op == "foot" else (actual + point).times(g.mp.mpf("0.5"))
            errors = {
                "line_membership": abs(g.side(on_line, line)) / scale,
                "normal_direction": abs(cross(line.n, actual - point)) / scale,
            }
        elif op == "circumcenter":
            distances = [g.dist(actual, vertex) for vertex in args]
            errors = {"equal_radii": (max(distances) - min(distances)) / scale}
        elif op == "orthocenter":
            errors = {
                f"altitude/{i}": abs(
                    g.side(
                        actual,
                        g.perpendicular_at(vertex, g.through(args[(i + 1) % 3], args[(i + 2) % 3])),
                    )
                )
                / scale
                for i, vertex in enumerate(args)
            }
        elif op in {"incenter", "excenter"}:
            distances = [
                abs(g.side(actual, g.through(args[i], args[(i + 1) % 3]))) for i in range(3)
            ]
            errors = {"equal_side_distances": (max(distances) - min(distances)) / scale}
        elif op in {"amidp-opp", "amidp-same"}:
            circle = g.triangle_circle("circ", *args)
            errors = {
                "circle_membership": abs(g.dist(actual, circle.center) - circle.radius) / scale,
                "equal_chords": abs(g.dist(actual, args[0]) - g.dist(actual, args[1])) / scale,
            }
        return [self.leaf("equality", error, name) for name, error in errors.items()]

    def select(self, points, selector, expression, path, hint, scale, figures):
        g = self.g
        key = sexpr(expression)
        explicit_choice = path in self.choices
        if path in self.choices:
            self.used_choices.add(path)
            provided = (g.point(self.choices[path]) - self.origin).times(1 / self.scale)
            if hint is not None and g.point_error(hint, provided, scale) > g.tolerance:
                raise CheckError("conflicting_choice", "named point and explicit choice disagree")
            hint = provided
        if isinstance(selector, str):
            if selector != "rs-arbitrary":
                raise CheckError("unsupported_selector", selector, "unsupported")
            if key in self.branch_cache:
                chosen = self.branch_cache[key]
            elif len(points) == 1:
                chosen = points[0]
            elif hint is not None:
                chosen = min(points, key=lambda point: g.dist(point, hint))
            else:
                raise CheckError("missing_unnamed_branch", path, "unresolved")
        else:
            _arity(selector, SELECTOR_ARITIES)
            op = _operator(selector)
            args = [self.term(arg, f"{path}/selector/{i}") for i, arg in enumerate(selector[1:])]
            reference = self.require_type(args[0], Point)
            if op == "rs-neq":
                if len(points) != 2:
                    raise CheckError("missing_second_intersection", "rs-neq requires two points")
                distances = [g.dist(point, reference) / scale for point in points]
                near, far = min(distances), max(distances)
                if near > g.tolerance:
                    raise CheckError("ambiguous_exclusion", "excluded point is not an intersection")
                if far - near <= g.tolerance:
                    raise CheckError("selector_tie", "unresolved second intersection", "unresolved")
                g.positive(far - near, 1, "selector_tie")
                chosen = points[distances.index(far)]
            elif op == "rs-closer-to-p":
                if len(points) == 1:
                    chosen = points[0]
                else:
                    distances = [g.dist(point, reference) / scale for point in points]
                    gap = abs(distances[0] - distances[1])
                    if gap <= g.tolerance:
                        raise CheckError("selector_tie", "equidistant roots", "unresolved", gap)
                    chosen = points[distances.index(min(distances))]
            else:
                line = self.require_type(args[1], Line)
                margins = [g.side_margin(point, reference, line, opposite=True) for point in points]
                acceptable = [
                    p for p, margin in zip(points, margins, strict=True) if margin > g.tolerance
                ]
                if len(acceptable) != 1:
                    status = "unresolved" if max(margins) >= -g.tolerance else "failed"
                    raise CheckError(
                        "selector_side_ambiguous", "no unique opposite-side root", status
                    )
                chosen = acceptable[0]
        if hint is not None:
            errors = {
                "selected_root": g.point_error(chosen, hint, scale),
                **{
                    f"membership/{i}": abs(g.side(hint, figure)) / scale
                    if isinstance(figure, Line)
                    else g.on_circle_error(hint, figure)
                    for i, figure in enumerate(figures)
                },
            }
            if max(errors.values()) > g.tolerance:
                code = (
                    "invalid_explicit_choice" if explicit_choice else "invalid_intersection_witness"
                )
                raise CheckError(code, "provided point is not on the selected real intersection")
            g.domain_evidence.append(
                {
                    "source_path": path,
                    "code": "intersection_witness_membership",
                    "errors": {name: g.fmt(error) for name, error in errors.items()},
                    "scale": "circle radius (minimum radius for two circles)",
                }
            )
        self.branch_cache[key] = chosen
        g.domain_evidence.append(
            {
                "source_path": path,
                "code": "intersection_branch",
                "candidates": [[g.fmt(p.x), g.fmt(p.y)] for p in points],
                "selected": [g.fmt(chosen.x), g.fmt(chosen.y)],
                "selector": sexpr(selector),
            }
        )
        return chosen

    def leaf(self, kind, value, label, negate=False):
        g = self.g
        if not g.mp.isfinite(value):
            raise CheckError("nonfinite_check", label)
        if kind == "equality":
            if negate:
                status = (
                    "passed" if value > g.tolerance else "failed" if value == 0 else "unresolved"
                )
            else:
                status = "passed" if value <= g.tolerance else "failed"
            return {
                "label": label,
                "kind": "inequality" if negate else kind,
                "error": g.fmt(value),
                "status": status,
            }
        if negate:
            kind, value = ("closed" if kind == "strict" else "strict"), -value
        if kind == "strict":
            status = "passed" if value > g.tolerance else "failed" if value <= 0 else "unresolved"
        else:
            status = "passed" if value >= 0 else "failed" if value < -g.tolerance else "unresolved"
        return {"label": label, "kind": kind, "margin": g.fmt(value), "status": status}

    def predicate(self, node, path, negate=False, strict_domain=False):
        op, g = _operator(node), self.g
        if op == "not":
            if len(node) != 2:
                raise CheckError("invalid_arity", sexpr(node))
            return self.predicate(node[1], f"{path}/0", not negate)
        if op in {"cycl", "in-poly"}:
            if len(node) < 5:
                raise CheckError("invalid_arity", sexpr(node))
        else:
            _arity(node, PREDICATE_ARITIES)
        args = [self.term(arg, f"{path}/{i}") for i, arg in enumerate(node[1:])]
        g.path = path
        checks = []

        def eq(error, label=op):
            checks.append(("equality", abs(error), label))

        def margin(value, strict=False, label=op):
            checks.append(("strict" if strict else "closed", value, label))

        if op in {"=", "eq"}:
            first, second = args
            self.require_type(second, type(first))
            if isinstance(first, Number):
                eq(g.normalized(first.value - second.value, max(first.scale, second.scale)))
            elif isinstance(first, Point):
                eq(g.point_error(first, second, self.feature_scale(first, second)))
            elif isinstance(first, Line):
                eq(g.line_error(first, second, self.feature_scale(first, second)))
            else:
                raise CheckError(
                    "unsupported_equality",
                    "equality only supports scalars, points, lines",
                    "unsupported",
                )
        elif op in {"gt", "gte", "lt", "lte", ">", ">=", "<", "<="}:
            first, second = [self.require_type(arg, Number) for arg in args]
            value = first.value - second.value
            if op in {"lt", "lte", "<", "<="}:
                value = -value
            margin(
                g.normalized(value, max(first.scale, second.scale)), op in {"gt", "lt", ">", "<"}
            )
        elif op == "on-line":
            point, line = self.require_type(args[0], Point), self.require_type(args[1], Line)
            eq(abs(g.side(point, line)) / self.feature_scale(point, line))
        elif op == "on-circ":
            point, circle = self.require_type(args[0], Point), self.require_type(args[1], Circle)
            eq(
                abs(g.dist(point, circle.center) - circle.radius)
                / self.feature_scale(point, circle)
            )
        elif op in {"para", "perp", "concur"}:
            lines = [self.require_type(arg, Line) for arg in args]
            if op == "concur":
                eq(g.on_line_error(g.intersect_lines(*lines[:2]), lines[2]))
            else:
                eq((cross if op == "para" else dot)(lines[0].n, lines[1].n))
        elif op == "tangent-lc":
            line, circle = self.require_type(args[0], Line), self.require_type(args[1], Circle)
            eq(
                (abs(g.side(circle.center, line)) - circle.radius)
                / self.feature_scale(line, circle)
            )
        elif op == "tangent-cc":
            a, b = [self.require_type(arg, Circle) for arg in args]
            distance = g.dist(a.center, b.center)
            g.positive(
                max(distance, abs(a.radius - b.radius)),
                max(a.radius, b.radius),
                "coincident_circles",
            )
            eq(
                min(abs(distance - a.radius - b.radius), abs(distance - abs(a.radius - b.radius)))
                / self.feature_scale(a, b)
            )
        elif op in {"same-side", "opp-sides"}:
            first, second = [self.require_type(arg, Point) for arg in args[:2]]
            line = self.require_type(args[2], Line)
            margin(g.side_margin(first, second, line, op == "opp-sides"), True)
        else:
            points = [self.require_type(arg, Point) for arg in args]
            scale = g.spread(*points)
            if op == "cong":
                left, right = g.dist(*points[:2]), g.dist(*points[2:])
                eq(g.normalized(left - right, max(left, right)))
            elif op == "coll":
                local_scale = self.feature_scale(*points, fallback=scale)
                eq(
                    g.normalized(
                        cross(points[1] - points[0], points[2] - points[0]), scale * local_scale
                    )
                )
            elif op == "cycl":
                circle = g.triangle_circle("circ", *points[:3])
                for i, point in enumerate(points[3:]):
                    eq(g.on_circle_error(point, circle), f"cycl/{i + 3}")
            elif op in {"right", "right-tri"}:
                g.triangle(*points)
                error = g.right_error(*points)
                if op == "right-tri":
                    error = min(
                        error,
                        g.right_error(points[1], points[0], points[2]),
                        g.right_error(points[0], points[2], points[1]),
                    )
                eq(error)
            elif op == "midp":
                eq(
                    g.point_error(
                        points[0],
                        (points[1] + points[2]).times(g.mp.mpf("0.5")),
                        self.feature_scale(*points, fallback=g.dist(points[1], points[2])),
                    )
                )
            elif op in {"on-seg", "on-ray"}:
                error, t = g.segment_data(*points)
                length = g.dist(points[1], points[2])
                error *= length / self.feature_scale(*points, fallback=length)
                eq(error, "collinearity")
                margin(t, strict_domain, "parameter_lower")
                if op == "on-seg":
                    margin(1 - t, strict_domain, "parameter_upper")
            elif op == "in-poly":
                for i, value in enumerate(g.inside_margins(points[0], points[1:])):
                    margin(value, strict_domain, f"edge/{i}")
            elif op in {"incenter", "circumcenter", "orthocenter", "centroid"}:
                expected = g.center(op, *points[1:])
                eq(g.point_error(points[0], expected, self.point_scale(op, points[1:], expected)))
            elif op == "i-bisector":
                p, a, vertex, c = points
                bisector = g.bisector(a, vertex, c)
                eq(g.on_line_error(p, bisector))
                direction = (a - vertex).times(1 / g.dist(a, vertex)) + (c - vertex).times(
                    1 / g.dist(c, vertex)
                )
                g.separated(p, vertex, scale)
                margin(
                    dot(p - vertex, direction) / (scale * g.norm(direction)),
                    True,
                    "internal_bisector_ray",
                )
            elif op == "eq-ratio":
                lengths = [g.dist(*points[i : i + 2]) for i in range(0, 8, 2)]
                for i in [1, 3]:
                    g.positive(lengths[i], scale, "zero_ratio_denominator")
                left, right = lengths[0] / lengths[1], lengths[2] / lengths[3]
                eq(g.normalized(left - right, max(left, right)))
            else:
                raise CheckError("unsupported_predicate", op, "unsupported")
        leaves = [self.leaf(kind, value, label, negate) for kind, value, label in checks]
        # A negated conjunction needs one definitely false conjunct, not all of them.
        status = (
            (
                "passed"
                if any(item["status"] == "passed" for item in leaves)
                else "unresolved"
                if any(item["status"] == "unresolved" for item in leaves)
                else "failed"
            )
            if negate
            else _status(leaves)
        )
        return {"status": status, "checks": leaves, "negated": negate}

    def parameter(self, node, path):
        result = self._parameter(node, path)
        if isinstance(node[1], tuple):
            names = node[1]
            points = [self.objects[name] for name in names]
            span = min(
                self.g.dist(point, points[(i + 1) % len(points)]) for i, point in enumerate(points)
            )
            for name in names:
                point = self.objects[name]
                self.objects[name] = Point(point.x, point.y, span)
        elif len(node) == 4 and isinstance(self.objects[node[1]], Point):
            raw = node[3]
            op = _operator(raw)
            args = [self.term(arg, f"{path}/local-scale/{i}") for i, arg in enumerate(raw[1:])]
            if op in {"on-seg", "on-ray", "on-ray-opp"}:
                span = self.feature_scale(*args, fallback=self.g.dist(*args))
            elif op == "in-poly":
                span = min(
                    self.g.dist(point, args[(i + 1) % len(args)]) for i, point in enumerate(args)
                )
            else:
                span = self.feature_scale(*args)
            point = self.objects[node[1]]
            self.objects[node[1]] = Point(point.x, point.y, span)
        return result

    def _parameter(self, node, path):
        g = self.g
        if isinstance(node[1], tuple):
            names, method = node[1], node[2]
            points = [self.require_type(self.objects[name], Point) for name in names]
            name = method if isinstance(method, str) else _operator(method)
            g.path = path
            if name == "polygon":
                leaves = [
                    self.leaf("strict", margin, f"convexity/{i}")
                    for i, margin in enumerate(g.convex_margins(points))
                ]
            else:
                if len(points) != 3:
                    raise CheckError("invalid_triangle", "triangle needs three names")
                g.triangle(*points)
                leaves = []
                if name == "acute-tri":
                    for i, vertex in enumerate(points):
                        u, v = points[(i + 1) % 3] - vertex, points[(i + 2) % 3] - vertex
                        leaves.append(
                            self.leaf(
                                "strict", dot(u, v) / (g.norm(u) * g.norm(v)), f"acute_angle/{i}"
                            )
                        )
                elif name == "equi-tri":
                    lengths = [g.dist(points[i], points[(i + 1) % 3]) for i in range(3)]
                    leaves.append(
                        self.leaf(
                            "equality",
                            (max(lengths) - min(lengths)) / max(lengths),
                            "equilateral_sides",
                        )
                    )
                elif name == "right-tri" and isinstance(method, tuple) and len(method) == 2:
                    if method[1] not in names:
                        raise CheckError("invalid_right_vertex", str(method[1]))
                    vertex = names.index(method[1])
                    leaves.append(
                        self.leaf(
                            "equality",
                            g.right_error(
                                points[(vertex + 1) % 3], points[vertex], points[(vertex + 2) % 3]
                            ),
                            "right_angle",
                        )
                    )
                elif name != "triangle":
                    raise CheckError("unsupported_parameterization", str(method), "unsupported")
            return {"status": _status(leaves), "checks": leaves}
        if len(node) == 3:
            return {"status": "passed", "checks": [], "note": "free object; finite/domain checked"}
        name, raw = node[1], node[3]
        op = _operator(raw)
        if op == "in-poly":
            if len(raw) < 4:
                raise CheckError("invalid_arity", sexpr(raw))
        else:
            _arity(raw, PARAM_ARITIES)
        if op in {"on-seg", "on-ray", "on-circ", "on-line", "in-poly"}:
            return self.predicate((op, name, *raw[1:]), f"{path}/parameter", strict_domain=True)
        if op == "tangent-lc":
            line = self.require_type(self.objects[name], Line)
            circle = self.require_type(self.term(raw[1], f"{path}/parameter/circle"), Circle)
            self.objects[name] = Line(
                line.n, line.c, circle.radius, self.g.foot(circle.center, line)
            )
            return self.predicate((op, name, *raw[1:]), f"{path}/parameter")
        if op == "tangent-cl":
            return self.predicate(("tangent-lc", raw[1], name), f"{path}/parameter")
        point = self.require_type(self.objects[name], Point)
        if op == "on-ray-opp":
            a, b = [
                self.require_type(self.term(arg, f"{path}/parameter/{i}"), Point)
                for i, arg in enumerate(raw[1:])
            ]
            error, t = g.segment_data(point, a, b)
            length = g.dist(a, b)
            error *= length / self.feature_scale(point, a, b, fallback=length)
            leaves = [
                self.leaf("equality", error, "collinearity"),
                self.leaf("strict", -t, "opposite_ray_parameter"),
            ]
        elif op in {"on-minor-arc", "on-major-arc"}:
            circle = self.require_type(self.term(raw[1], f"{path}/parameter/0"), Circle)
            a, b = [
                self.require_type(self.term(arg, f"{path}/parameter/{i + 1}"), Point)
                for i, arg in enumerate(raw[2:])
            ]
            u, v, w = a - circle.center, b - circle.center, point - circle.center
            g.separated(a, b, circle.radius)
            determinant = cross(u, v) / circle.radius**2
            if abs(determinant) <= g.tolerance:
                raise CheckError(
                    "ambiguous_arc", "coincident/antipodal arc endpoints", "unresolved"
                )
            orientation = 1 if determinant > 0 else -1
            arc_margins = [
                orientation * cross(u, w) / circle.radius**2,
                orientation * cross(w, v) / circle.radius**2,
            ]
            leaves = [
                self.leaf("equality", g.on_circle_error(p, circle), f"on_circle/{i}")
                for i, p in enumerate([a, b, point])
            ]
            if op == "on-minor-arc":
                leaves.extend(
                    self.leaf("strict", margin, f"arc_interior/{i}")
                    for i, margin in enumerate(arc_margins)
                )
            else:
                # For a major arc the complement of the closed minor arc is strict.
                leaves.append(
                    self.leaf("strict", max(-v for v in arc_margins), "major_arc_interior")
                )
        else:
            raise CheckError("unsupported_parameterization", op, "unsupported")
        return {"status": _status(leaves), "checks": leaves}

    def run(self):
        assumptions, goals = [], []
        for i, node in enumerate(self.commands):
            path, op = f"commands/{i}", _operator(node)
            start = len(self.g.domain_evidence)
            self.g.path = path
            try:
                if op == "param":
                    names = node[1] if isinstance(node[1], tuple) else [node[1]]
                    self.available.update(names)
                    checked = self.parameter(node, path)
                elif op == "define":
                    name = node[1]
                    actual = self.objects[name]
                    expected = self.term(
                        node[3],
                        f"{path}/definition",
                        hint=actual if isinstance(actual, Point) else None,
                    )
                    self.require_type(expected, type(actual))
                    if isinstance(actual, Point):
                        error = self.g.point_error(actual, expected, expected.span)
                    elif isinstance(actual, Line):
                        error = self.g.line_error(actual, expected, expected.span)
                    else:
                        error = self.g.circle_error(actual, expected)
                    leaves = [self.leaf("equality", error, "defined_object_consistency")]
                    if isinstance(actual, Point):
                        leaves.extend(
                            self.construction_checks(
                                node[3], f"{path}/definition", actual, expected
                            )
                        )
                        self.objects[name] = Point(actual.x, actual.y, expected.span)
                    checked = {"status": _status(leaves), "checks": leaves}
                    if isinstance(actual, Line):
                        # Metadata only: preserve the reported normal and offset.
                        # An alias must retain its defining local scale, not the
                        # unrelated global coordinate-chart normalization length.
                        self.objects[name] = Line(
                            actual.n, actual.c, expected.span, expected.anchor
                        )
                    elif isinstance(actual, Circle):
                        self.objects[name] = Circle(actual.center, actual.radius, expected.span)
                    self.available.add(name)
                else:
                    checked = self.predicate(node[1], f"{path}/condition")
            except CheckError as exc:
                checked = {
                    "status": exc.status,
                    "checks": [],
                    "code": exc.code,
                    "message": str(exc),
                }
                if exc.margin is not None:
                    checked["margin"] = self.g.fmt(exc.margin)
                # Later clauses may still inspect the reported object; the failed
                # definition remains a hard gate and cannot be repaired this way.
                if op == "define":
                    self.available.add(node[1])
            except (ArithmeticError, TypeError, ValueError, KeyError, IndexError) as exc:
                checked = {
                    "status": "unsupported",
                    "checks": [],
                    "code": "checker_error",
                    "message": f"{type(exc).__name__}: {exc}",
                }
            checked.update(
                source_path=path,
                source=sexpr(node),
                kind=op,
                domain_evidence=self.g.domain_evidence[start:],
            )
            (goals if op == "eval" else assumptions).append(checked)
        if unused_choices := set(self.choices) - self.used_choices:
            assumptions.append(
                {
                    "source_path": "witness/choices",
                    "kind": "witness",
                    "status": "failed",
                    "code": "unused_branch_choice",
                    "paths": sorted(map(str, unused_choices)),
                    "checks": [],
                    "domain_evidence": [],
                }
            )
        return {
            "valid": bool(assumptions) and _status(assumptions) == "passed",
            "status": _status(assumptions),
            "goals_valid": _status(goals) == "passed" if goals else None,
            "assumptions": assumptions,
            "goals": goals,
            "normalization": self.normalization,
        }


def check_configuration(gmbl_text, witness, *, tolerance="1e-6", dps=80):
    """Check one saved witness, without solving or inspecting reference answers."""
    result = {
        "policy": CHECKER_POLICY["version"],
        "tolerance": str(tolerance),
        "dps": dps,
        "scope": "public_gmbl_mathematical_conditions_only",
        "original_problem_valid": None,
        "existence_proved": False,
    }
    try:
        if not isinstance(dps, int) or isinstance(dps, bool) or dps < 40:
            raise CheckError("invalid_precision", "dps must be an integer >= 40")
        if not isinstance(witness, Mapping):
            raise CheckError("invalid_witness", "witness must be a mapping")
        probe = Geometry(tolerance, dps)
        if not probe.mp.isfinite(probe.tolerance) or not 0 < probe.tolerance < 1:
            raise CheckError("invalid_tolerance", "tolerance must be between zero and one")
        commands = parse_gmbl(gmbl_text)
        coverage = inspect_gmbl(gmbl_text)
        if not coverage["supported"]:
            return result | {
                "valid": False,
                "status": "unsupported",
                "goals_valid": None,
                "assumptions": [],
                "goals": [],
                "coverage": coverage,
            }
        result.update(WitnessChecker(commands, witness, tolerance, dps).run())
        result["coverage"] = coverage
    except CheckError as exc:
        result.update(
            valid=False,
            status=exc.status,
            goals_valid=None,
            assumptions=[],
            goals=[],
            code=exc.code,
            message=str(exc),
        )
    except (ArithmeticError, TypeError, ValueError) as exc:
        result.update(
            valid=False,
            status="unsupported",
            goals_valid=None,
            assumptions=[],
            goals=[],
            code="checker_error",
            message=f"{type(exc).__name__}: {exc}",
        )
    return result


def witness_from_gmb_model(model):
    """Translate serialization only; no GMB/GeoSolver geometry is called.

    GMB LineNF is ``n dot X = r`` (the sign of r MUST be negated).
    Refuse missing model mappings; validation of the coordinates happens in the
    common checker. No stored losses or goal flags are trusted.
    """
    if not isinstance(model, Mapping):
        raise CheckError("invalid_model", "GMB model must be a mapping")

    def pair(value):
        if isinstance(value, Mapping) and set(value) == {"x", "y"}:
            return [value["x"], value["y"]]
        if isinstance(value, list | tuple) and len(value) == 2:
            return list(value)
        raise CheckError("invalid_model_point", "GMB point must be {x,y} or [x,y]")

    for key in ["named_points", "named_lines", "named_circles"]:
        if not isinstance(model.get(key), Mapping):
            raise CheckError("invalid_model", f"missing mapping {key}")
    result = {
        "points": {name: pair(value) for name, value in model["named_points"].items()},
        "lines": {},
        "circles": {},
    }
    for name, line in model["named_lines"].items():
        if isinstance(line, Mapping) and set(line) == {"n", "r"}:
            normal, radius = line["n"], line["r"]
        elif isinstance(line, list | tuple) and len(line) == 2:
            normal, radius = line
        else:
            raise CheckError("invalid_model_line", "GMB line requires normal n and offset r")
        # Exact decimal sign change: never round through float or ambient mp.dps.
        radius_text = str(radius).strip().removeprefix("+")
        negated = radius_text[1:] if radius_text.startswith("-") else "-" + radius_text
        result["lines"][name] = [*pair(normal), negated]
    for name, circle in model["named_circles"].items():
        if isinstance(circle, Mapping) and set(circle) == {"center", "radius"}:
            center, radius = circle["center"], circle["radius"]
        elif isinstance(circle, list | tuple) and len(circle) == 2:
            center, radius = circle
        else:
            raise CheckError("invalid_model_circle", "GMB circle requires center and radius")
        result["circles"][name] = {"center": pair(center), "radius": radius}
    return result
