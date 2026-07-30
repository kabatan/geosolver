from __future__ import annotations

import sys

from mpmath import mp

from geotarget.engine import engine_root
from geotarget.hp_semantics import install, polar


def _runtime_geometry() -> None:
    path = str(engine_root() / "runtime/geosolver/src")
    if path not in sys.path:
        sys.path.insert(0, path)


def _line_value(line, x, y):
    return line.a * x + line.b * y + line.c


def test_high_precision_polar_has_the_standard_geometric_equation() -> None:
    _runtime_geometry()
    from geosolver.geometry.mp.mp_impl import MPCircle, MPPoint

    with mp.workdps(80):
        center = MPPoint(mp.mpf("1"), mp.mpf("1"))
        point = MPPoint(mp.mpf("3"), mp.mpf("4"))
        circle = MPCircle(center, mp.mpf("2"))
        line = polar(point, circle)

        dx = point.x - center.x
        dy = point.y - center.y
        inverse_scale = circle.radius**2 / (dx**2 + dy**2)
        inverse = MPPoint(
            center.x + inverse_scale * dx,
            center.y + inverse_scale * dy,
        )

        assert abs(_line_value(line, inverse.x, inverse.y)) < mp.mpf("1e-70")
        assert abs(_line_value(line, center.x, center.y)) > mp.mpf("0.1")
        assert abs(_line_value(line, point.x, point.y)) > mp.mpf("0.1")


def test_install_replaces_the_high_precision_registry_entry() -> None:
    _runtime_geometry()
    from geosolver.geometry.mp import mp_api, mp_api_geometry

    install()

    assert mp_api.MP_API["Polar"] is polar
    assert mp_api.MP_Polar is polar
    assert mp_api_geometry.MP_Polar is polar


def test_corrected_high_precision_polar_matches_the_ordinary_evaluator() -> None:
    _runtime_geometry()
    from geosolver.geometry import Circle, Point, Polar
    from geosolver.geometry.mp.mp_impl import MPCircle, MPPoint

    with mp.workdps(80):
        ordinary = Polar(Point(3, 4), Circle(Point(1, 1), 2))
        high_precision = polar(
            MPPoint(mp.mpf("3"), mp.mpf("4")),
            MPCircle(MPPoint(mp.mpf("1"), mp.mpf("1")), mp.mpf("2")),
        )

        ordinary_coefficients = [mp.mpf(str(value.evalf(80))) for value in (
            ordinary.a,
            ordinary.b,
            ordinary.c,
        )]
        high_precision_coefficients = [
            high_precision.a,
            high_precision.b,
            high_precision.c,
        ]
        scale = ordinary_coefficients[0] / high_precision_coefficients[0]
        assert max(
            abs(left - scale * right)
            for left, right in zip(
                ordinary_coefficients, high_precision_coefficients, strict=True
            )
        ) < mp.mpf("1e-70")
