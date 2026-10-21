"""Export an already found GeoSolver point; never optimize or assess correctness.

GeoSolver is used only to materialize its own output. The independent checker
reconstructs GMBL's geometry separately and must not trust this exporter.
"""

from __future__ import annotations

import ast
from collections.abc import Mapping, Sequence
from typing import Any

from mpmath import mp

# Deliberately limited to the constructors used by this translation set. The
# public compiler distinguishes scalar/object but not point/line/circle; guessing
# the latter at the measurement boundary would hide a broken name mapping.
OUTPUT_KINDS = {
    **dict.fromkeys(
        (
            "Point",
            "Midpoint",
            "Center",
            "Circumcenter",
            "Incenter",
            "Excenter",
            "Orthocenter",
            "FootOfPerpendicular",
            "IncircleContactPoint",
            "Intersect",
            "PointOnArc",
            "PointOnCircle",
            "PointOnLine",
            "PointOnSegment",
        ),
        "point",
    ),
    **dict.fromkeys(
        ("Line", "ParallelLine", "PerpendicularLine", "PerpendicularBisector", "AngleBisector"),
        "line",
    ),
    **dict.fromkeys(("Circle", "CircleThroughPoint", "Circumcircle", "Incircle"), "circle"),
    "Arc": "arc",
}


def construction_kinds(problem):
    from geosolver.problem.dsl_spec import symbols_by_name

    symbols = symbols_by_name()
    known = dict.fromkeys(problem.variables, "scalar")

    def infer(node):
        if isinstance(node, ast.Name):
            return known.get(node.id)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            symbol = symbols.get(node.func.id)
            name = node.func.id if symbol is None else symbol.name
            if name == "Reflect" and node.args:
                return infer(node.args[0])
            if name in OUTPUT_KINDS:
                return OUTPUT_KINDS[name]
            if symbol is not None and symbol.output_type == "scalar":
                return "scalar"
        if isinstance(node, ast.Attribute):
            if infer(node.value) == "circle" and node.attr == "center":
                return "point"
            if node.attr in {"x", "y", "a", "b", "c", "radius"}:
                return "scalar"
        if isinstance(node, ast.Constant | ast.BinOp | ast.UnaryOp):
            return "scalar"
        return None

    for item in problem.constructions:
        known[item.name] = infer(ast.parse(item.expression, mode="eval").body)
    return known


class WitnessExporter:
    def __init__(
        self,
        problem: Mapping[str, Any],
        declarations: Mapping[str, str],
        bindings: Mapping[str, str] | None = None,
    ):
        from geosolver.engine.standard.problem.load_problem_bundle import load_problem_bundle
        from geosolver.problem.models import GeometryProblem
        from geosolver.problem.validation import validate

        parsed = GeometryProblem.model_validate(problem)
        report = validate(parsed)
        if not report.valid:
            raise ValueError(f"Invalid public problem: {report.issues}")
        self.bundle = load_problem_bundle(parsed.engine_document())
        self.declarations = dict(declarations)
        self.bindings = dict(bindings or {})
        kinds = construction_kinds(parsed)
        if set(self.bindings) - set(self.declarations):
            raise ValueError("Witness binding refers to an undeclared GMB object")
        available = {item.name for item in self.bundle.spec.construction}
        for name, kind in self.declarations.items():
            if kind not in {"point", "line", "circle"}:
                raise ValueError(f"Unsupported witness type: {name}: {kind}")
            if self.bindings.get(name, name) not in available:
                raise ValueError(f"No GeoSolver construction for GMB object: {name}")
            if kinds.get(self.bindings.get(name, name)) != kind:
                raise TypeError(f"Static witness type mismatch: {name}: expected {kind}")

    @property
    def coordinate_names(self) -> tuple[str, ...]:
        return self.bundle.var_names

    def export(self, coordinates: Sequence[Any], *, precision_dps: int = 180) -> dict:
        from geosolver.engine.standard.evaluation.high_precision_expressions import (
            build_solution_context_high_precision,
        )
        from geosolver.engine.standard.precision.type_guards.high_precision_mode import (
            high_precision_mode,
        )
        from geosolver.geometry.mp.mp_core_types import MPCircle, MPLine, MPPoint

        if not 30 <= precision_dps <= 550:
            raise ValueError("Unsupported witness materialization precision")
        if len(coordinates) != len(self.coordinate_names):
            raise ValueError("Candidate coordinate count does not match the compiled problem")
        if any(isinstance(value, bool | float) for value in coordinates):
            raise TypeError("Use retained mpf values or decimal strings, not Python floats")
        with mp.workdps(precision_dps), high_precision_mode():
            values = [mp.mpf(value) for value in coordinates]
            if not all(mp.isfinite(value) for value in values):
                raise ValueError("Nonfinite candidate coordinate")
            context = build_solution_context_high_precision(
                self.bundle.spec,
                list(self.coordinate_names),
                values,
                self.bundle.base_context,
                precision_dps,
            )

            def decimal(value):
                if not mp.isfinite(value):
                    raise ValueError("Nonfinite constructed object")
                return mp.nstr(value, n=precision_dps + 8)

            result: dict[str, dict] = {"points": {}, "lines": {}, "circles": {}}
            for name, kind in self.declarations.items():
                item = context[self.bindings.get(name, name)]
                if kind == "point" and isinstance(item, MPPoint):
                    result["points"][name] = [decimal(item.x), decimal(item.y)]
                elif kind == "line" and isinstance(item, MPLine):
                    result["lines"][name] = [decimal(item.a), decimal(item.b), decimal(item.c)]
                elif kind == "circle" and isinstance(item, MPCircle):
                    result["circles"][name] = {
                        "center": [decimal(item.center.x), decimal(item.center.y)],
                        "radius": decimal(item.radius),
                    }
                else:
                    raise TypeError(f"Witness object type mismatch: {name}: expected {kind}")
            return result
