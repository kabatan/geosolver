"""Truth-free exact D0 cases for the trace-closed Angle lift."""

from __future__ import annotations

from fractions import Fraction

import sympy as sp

from candidate import AngleAtom, AngleRelation, AngleTerm


def _point_sub(first, second):
    return sp.expand(first[0] - second[0]), sp.expand(first[1] - second[1])


def triangle_sum(*, reflected: bool = False):
    ax, ay, bx, by, cx, cy = sp.symbols("ax ay bx by cx cy", real=True)
    points = ((ax, ay), (bx, by), (cx, cy))
    orientation = 1
    prefix = "triangle"
    if reflected:
        points = tuple((x, -y) for x, y in points)
        orientation = -1
        prefix = "reflection(triangle)"
    a, b, c = points
    atoms = (
        AngleAtom(f"{prefix}:Angle(B-A,C-A)", _point_sub(b, a), _point_sub(c, a), orientation),
        AngleAtom(f"{prefix}:Angle(C-B,A-B)", _point_sub(c, b), _point_sub(a, b), orientation),
        AngleAtom(f"{prefix}:Angle(A-C,B-C)", _point_sub(a, c), _point_sub(b, c), orientation),
    )
    relation = AngleRelation(tuple(AngleTerm(atom, Fraction(1)) for atom in atoms), Fraction(1))
    assignment = {ax: 0, ay: 0, bx: 1, by: 0, cx: 0, cy: 1}
    return relation, assignment


def rational_sum_difference():
    t = sp.Symbol("t", real=True)
    alpha = AngleAtom(
        "rational:alpha",
        (sp.Integer(1), sp.Integer(0)),
        (t, sp.Integer(1)),
        1,
        Fraction(1, 7),
        Fraction(1, 5),
    )
    beta = AngleAtom(
        "rational:beta",
        (sp.Integer(1), sp.Integer(0)),
        (sp.Integer(1), sp.sqrt(3)),
        1,
        Fraction(1, 4),
        Fraction(2, 5),
    )
    gamma = AngleAtom(
        "rational:gamma",
        (sp.Integer(1), sp.Integer(0)),
        (sp.Integer(0), sp.Integer(1)),
        1,
        Fraction(2, 5),
        Fraction(3, 5),
    )
    relation = AngleRelation(
        (
            AngleTerm(alpha, Fraction(1, 2)),
            AngleTerm(beta, Fraction(1)),
            AngleTerm(gamma, Fraction(-5, 6)),
        ),
        Fraction(0),
    )
    return relation, {t: sp.sqrt(3)}, {t: sp.sqrt(3) + sp.Rational(1, 10**12)}


def undefined_collinear():
    atom = AngleAtom(
        "undefined:collinear",
        (sp.Integer(1), sp.Integer(0)),
        (sp.Integer(2), sp.Integer(0)),
        1,
        Fraction(0),
        Fraction(1),
        lower_open=False,
    )
    return AngleRelation((AngleTerm(atom, Fraction(1)),), Fraction(0)), {}


def two_pi_alias():
    atom = AngleAtom(
        "alias:two-pi",
        (sp.Integer(1), sp.Integer(0)),
        (sp.Integer(-1), sp.sqrt(3)),
        1,
        Fraction(3, 5),
        Fraction(7, 10),
    )
    return AngleRelation((AngleTerm(atom, Fraction(3)),), Fraction(0)), {}


def winding_ambiguity():
    atom = AngleAtom(
        "ambiguous:wide-principal-range",
        (sp.Integer(1), sp.Integer(0)),
        ((1 + sp.sqrt(5)) / 4, sp.sqrt(10 - 2 * sp.sqrt(5)) / 4),
        1,
    )
    return AngleRelation((AngleTerm(atom, Fraction(5)),), Fraction(1)), {}


def legacy_sector3_shape():
    first = AngleAtom("legacy:left", (1, 0), (1, 1), 1)
    second = AngleAtom("legacy:right", (1, 0), (0, 1), 1)
    return AngleRelation(
        (AngleTerm(first, Fraction(2)), AngleTerm(second, Fraction(-1))),
        Fraction(0),
    )
