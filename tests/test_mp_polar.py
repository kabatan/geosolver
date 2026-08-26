from __future__ import annotations

from mpmath import mp

from geosolver.geometry.mp.mp_api_geometry import MP_Polar
from geosolver.geometry.mp.mp_core_types import MPCircle, MPPoint


def test_mp_polar_at_circle_point_is_the_tangent_line() -> None:
    with mp.workdps(80):
        center = MPPoint(mp.mpf("1.5"), mp.mpf("-2"))
        circle = MPCircle(center, mp.mpf("5"))
        point = MPPoint(center.x + mp.mpf("3"), center.y + mp.mpf("4"))

        line = MP_Polar(point, circle)

        # The polar of a point on the circle is its tangent: it contains the
        # point, stays one radius from the center, and has the radial normal.
        assert abs(line.a * point.x + line.b * point.y + line.c) < mp.mpf("1e-70")
        assert abs(
            abs(line.c + line.a * center.x + line.b * center.y) - circle.radius
        ) < mp.mpf("1e-70")
        assert abs(
            line.a * (point.y - center.y) - line.b * (point.x - center.x)
        ) < mp.mpf("1e-70")
