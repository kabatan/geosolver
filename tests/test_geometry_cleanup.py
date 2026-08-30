"""Geometry backend dispatch and internal import integrity."""

import ast
from pathlib import Path

import pytest
from mpmath import mp

from geosolver.engine.standard.interpreter.context.high_precision import (
    _get_high_precision_context,
)
from geosolver.engine.standard.precision.type_guards.high_precision_mode import high_precision_mode
from geosolver.geometry import AssumeAcute, IsInteger, IsPrime
from geosolver.geometry.mp.mp_api import MP_Area, MP_Point, MP_PolygonArea
from geosolver.geometry.runtime import BackendType, use_runtime
from geosolver.geometry.safety import AssumptionError


@pytest.mark.parametrize("precision", [80, 180])
@pytest.mark.parametrize("name,function", [("IsInteger", IsInteger), ("IsPrime", IsPrime)])
def test_registered_mp_number_constraints_match_pipeline_without_symbolic_fallback(
    precision, name, function
):
    with mp.workdps(precision), high_precision_mode():
        hp = _get_high_precision_context(precision)
        values = [mp.mpf(v) for v in ("-3", "0", "2", "9", "1009", "3.5")]
        values.append(mp.mpf(3) + mp.mpf("1e-40"))
        for value in values:
            expected = hp[name](value)
            direct = function.mp(value)
            with use_runtime(backend=BackendType.MPMATH, precision=precision):
                dispatched = function(value)
            assert isinstance(direct, mp.mpf) and isinstance(dispatched, mp.mpf)
            assert direct == dispatched == expected
        assert IsPrime.mp(mp.mpf(1009)) == 0
        assert IsPrime.mp(mp.mpf(9)) > 0
        assert IsPrime.mp(mp.mpf(3) + mp.mpf("1e-40")) > 0
        assert IsInteger.mp(mp.mpf("3.5")) > 0


def test_public_polygon_area_and_acute_guards_keep_the_active_implementations():
    with mp.workdps(120), high_precision_mode():
        a, b, c = MP_Point(0, 0), MP_Point(4, 0), MP_Point(2, 3)
        assert MP_Area(a, b, c) == MP_PolygonArea(a, b, c) == 6
        AssumeAcute(a, b, c)
        with pytest.raises(AssumptionError):
            AssumeAcute(a, b, MP_Point(2, 0))


def test_all_explicit_internal_import_targets_exist():
    """Catch stale lazy imports even when normal DSL dispatch bypasses them."""
    source = Path(__file__).resolve().parents[1] / "src"
    for path in source.rglob("*.py"):
        package = list(path.relative_to(source).parent.parts)
        for node in ast.walk(ast.parse(path.read_bytes())):
            if not isinstance(node, ast.ImportFrom):
                continue
            if node.level:
                parts = package[: len(package) - node.level + 1]
                parts += node.module.split(".") if node.module else []
            elif node.module and node.module.startswith("geosolver."):
                parts = node.module.split(".")
            else:
                continue
            target = source.joinpath(*parts)
            assert target.with_suffix(".py").is_file() or (target / "__init__.py").is_file(), (
                path.relative_to(source),
                node.lineno,
                ".".join(parts),
            )
