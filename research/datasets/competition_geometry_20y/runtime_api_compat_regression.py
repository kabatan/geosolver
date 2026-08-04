#!/usr/bin/env python3
"""Small regression suite for the public-to-mpmath geometry API boundary.

The competition DSL is written against the public geometry signatures.  The
high-precision backend must therefore accept those signatures directly; a
case-specific rewrite in JSON is not a compatibility fix.  Run this file with
``PYTHONPATH=<runtime>/geosolver/src`` and the runtime's Python interpreter.
"""

from __future__ import annotations

import math
from mpmath import mp

from geosolver.geometry.mp.mp_api import (
    MP_Circle,
    MP_IncircleContactPoint,
    MP_Line,
    MP_Perimeter,
    MP_Point,
    MP_Rotate,
    MP_Tangent,
    MP_TangentLine,
)
from geosolver.geometry.mp.mp_core_types import MPLine, MPPoint
from geosolver.ir.compiler import safe_eval_expr, safe_eval_expr_hp


def close(value, expected, tol=1e-35):
    return abs(float(value - expected)) < tol


def main() -> None:
    # Public Line(a,b,c), including the normalized high-precision boundary.
    line = MP_Line(1, -1, 2)
    assert isinstance(line, MPLine)
    assert close(line.a * 1 + line.b * 1 + line.c, 2 / math.sqrt(2))

    # Public Rotate(point, angle, center), default center, and legacy ordering
    # are all accepted by one compatibility wrapper.
    origin = MP_Point(0, 0)
    point = MP_Point(1, 0)
    quarter_turn = mp.pi / 2
    rotated = MP_Rotate(point, quarter_turn, origin)
    default_rotated = MP_Rotate(point, quarter_turn)
    legacy_rotated = MP_Rotate(point, origin, quarter_turn)
    for value in (rotated, default_rotated, legacy_rotated):
        assert close(value.x, 0, 1e-10) and close(value.y, 1, 1e-10)

    # Tangent(point,circle) and the public TangentLine alias return a single
    # line; the historical (circle, point) order remains a boundary alias.
    circle = MP_Circle(origin, 1)
    external = MP_Point(2, 0)
    tangents = (
        MP_Tangent(external, circle),
        MP_Tangent(circle, external),
        MP_TangentLine(external, circle),
        MP_TangentLine(circle, external),
    )
    for tangent in tangents:
        assert isinstance(tangent, MPLine)
        assert close(tangent.distance_to_point(origin), 1, 1e-10)

    # The public side aliases are normalized once, instead of requiring a DSL
    # rewrite for each contact-point case.
    A, B, C = MP_Point(0, 3), MP_Point(-2, 0), MP_Point(2, 0)
    contact_string = MP_IncircleContactPoint(A, B, C, side="BC")
    contact_index = MP_IncircleContactPoint(A, B, C, side=0)
    assert isinstance(contact_string, MPPoint)
    assert contact_string == contact_index
    assert close(contact_string.y, 0, 1e-10)

    # Perimeter is variadic for polygons, not limited to the old triangle-only
    # backend helper.
    square = [MP_Point(0, 0), MP_Point(1, 0), MP_Point(1, 1), MP_Point(0, 1)]
    assert close(MP_Perimeter(*square), 4, 1e-10)
    assert close(MP_Perimeter(square), 4, 1e-10)

    # Mathematical caret precedence is normalized before parsing.  Quoted
    # carets are data, not operators.
    assert safe_eval_expr("1^2+2^3", {}) == 9
    assert safe_eval_expr("'a^b'", {}) == "a^b"
    assert safe_eval_expr_hp("3^2+4^2", {"mpf": mp.mpf}) == 25

    print("runtime API compatibility regressions: PASS")


if __name__ == "__main__":
    main()
