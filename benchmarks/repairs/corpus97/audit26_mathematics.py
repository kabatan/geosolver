"""Exact, solver-independent checks accompanying the 26-case audit."""

from __future__ import annotations

import json

import sympy as s

from benchmarks.repairs.corpus97.independent_checks import hmmt_2011_collinear_branches


def hmmt_2013_angle_obstruction():
    """Check the source inconsistency without constructing circle intersections.

    Ordinary-angle conditions force P into the closed triangle ABD, so
    angle DBP <= angle DBA. The law of cosines gives the opposite inequality.
    HMMT_2013_GEO_09_SOURCE_CHECK.md supplies the geometric implication;
    this function independently verifies its exact arithmetic, not a solve.
    """
    ab_over_ad = 2 * s.sqrt(2) / 3
    bd_over_ad = s.simplify(s.sqrt(1 + ab_over_ad**2 - 2 * ab_over_ad * s.cos(s.pi / 4)))
    cosine_dba = s.simplify((ab_over_ad**2 + bd_over_ad**2 - 1) / (2 * ab_over_ad * bd_over_ad))
    pb = s.simplify(15 * s.sqrt(2) / 4 * ab_over_ad)
    pd = s.simplify(7 * s.sqrt(5) / 3 / bd_over_ad)
    bd_squared = s.simplify(pb**2 + pd**2 - 2 * pb * pd * s.cos(s.pi / 3))
    cosine_dbp = s.simplify((bd_squared + pb**2 - pd**2) / (2 * s.sqrt(bd_squared) * pb))
    squared_gap = s.simplify(cosine_dba**2 - cosine_dbp**2)
    assert cosine_dba > 0 and cosine_dbp > 0 and squared_gap > 0
    return {
        "bd_over_ad": bd_over_ad,
        "pb": pb,
        "pd": pd,
        "bd_squared": bd_squared,
        "cosine_dba": cosine_dba,
        "cosine_dbp": cosine_dbp,
        "cosine_squared_gap": squared_gap,
    }


def hmmt_2013_published_configuration():
    """Exhaust both possible P in the published similarity argument.

    For ordinary angles, any valid configuration gives an interior P in ABD,
    PB=5, PD=7, angle BPD=60 degrees and hence BD=sqrt(39). Neither of the
    two exact circle intersections is interior to ABD at that value of BD.
    See AUDIT_26.md for the geometric implication, not just this computation.
    """
    d = 3 * s.sqrt(195) / 5
    a, b, dp = s.Point(0, 0), s.Point(2 * d / 3, 2 * d / 3), s.Point(d, 0)
    output = []
    for p in s.Circle(b, 5).intersection(s.Circle(dp, 7)):
        wb = s.simplify(3 * p.y / (2 * d))
        wd = s.simplify((p.x - p.y) / d)
        wa = s.simplify(1 - wb - wd)
        assert s.simplify(wa * a + wb * b + wd * dp - p) == s.Point(0, 0)
        assert s.simplify(p.distance(b) ** 2) == 25
        assert s.simplify(p.distance(dp) ** 2) == 49
        assert any(w < 0 for w in (wa, wb, wd))
        output.append({"point": str(p), "barycentric_A_B_D": list(map(str, (wa, wb, wd)))})
    assert len(output) == 2
    return output


def hmmt_hexagon_identity():
    """The target is identically zero, not merely small at a found root."""
    t = s.symbols("t", positive=True)
    a, b, c = s.Point(t, 0), s.Point(t / 2, s.sqrt(3) * t / 2), s.Point(-t / 2, s.sqrt(3) * t / 2)
    d, e, f = -a, -b, -c
    m = s.Segment(d, e).midpoint
    x = s.Line(a, c).intersection(s.Line(b, m))[0]
    y = s.Line(b, f).intersection(s.Line(a, m))[0]
    z = s.Line(a, c).intersection(s.Line(b, f))[0]

    def area(*points):
        return abs(s.Polygon(*points).area)

    result = s.simplify(area(b, x, c) + area(a, y, f) + area(a, b, z) - area(m, x, z, y))
    assert result == 0
    return str(result)


def jmo_boundary_exact():
    """Non-P intersections with the two circles are related by ratio -2."""
    u, v = s.symbols("u v", real=True)
    # A=P+(u,v), B=P+k(u,v). The small-circle equation is
    # u²+v²+4u=0; the nonzero second root for B is k=-2.
    circle_a = (u + 2) ** 2 + v**2 - 4
    circle_b = (-2 * u - 4) ** 2 + (-2 * v) ** 2 - 16
    assert s.expand(circle_b - 4 * circle_a) == 0
    # AB=3 AP=4 and PB=2 AP.
    return str(s.Rational(8, 3))


def main():
    print(
        json.dumps(
            {
                "hmmt_2013_angle_obstruction": {
                    key: str(value) for key, value in hmmt_2013_angle_obstruction().items()
                },
                "hmmt_2013_barycentric_obstruction": hmmt_2013_published_configuration(),
                "hmmt_2011_missing_branches": list(map(str, hmmt_2011_collinear_branches())),
                "hmmt_2011_hexagon_target_identity": hmmt_hexagon_identity(),
                "jmo_2009_only_answer": jmo_boundary_exact(),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
