#!/usr/bin/env python3
"""Independent checks used by FAILURE_CASE_AUDIT_STRICT_RAW.md.

This script intentionally does not call geosolver.  It checks the witnesses
and the algebraic contradiction used to separate DSL defects from solver
search/refinement failures.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import sympy as sp

ROOT = Path(__file__).resolve().parent


def norm(p: np.ndarray, q: np.ndarray) -> float:
    return float(np.linalg.norm(p - q))


def cross(p: np.ndarray, q: np.ndarray) -> float:
    return float(p[0] * q[1] - p[1] * q[0])


def triangle_area(*points: np.ndarray) -> float:
    return abs(sum(cross(points[i], points[(i + 1) % len(points)]) for i in range(len(points))) / 2.0)


def line_intersection(a: np.ndarray, b: np.ndarray, c: np.ndarray, d: np.ndarray) -> np.ndarray:
    r = b - a
    s = d - c
    t = cross(c - a, s) / cross(r, s)
    return a + t * r


def foot(p: np.ndarray, a: np.ndarray, b: np.ndarray) -> np.ndarray:
    direction = b - a
    t = float(np.dot(p - a, direction) / np.dot(direction, direction))
    return a + t * direction


def check_aime_2018_ii_12() -> dict[str, object]:
    A, B = np.array([0.0, 0.0]), np.array([10.0, 0.0])
    C, D = np.array([1.6, 11.2]), np.array([-8.0, 14.0])
    P = line_intersection(A, C, B, D)
    side_residuals = [norm(A, B) - 10, norm(B, C) - 14, norm(C, D) - 10, norm(D, A) - 2 * math.sqrt(65)]
    area_residual = triangle_area(A, P, B) + triangle_area(C, P, D) - triangle_area(B, P, C) - triangle_area(A, P, D)
    points = [A, B, C, D]
    turns = [cross(points[(i + 1) % 4] - points[i], points[(i + 2) % 4] - points[(i + 1) % 4]) for i in range(4)]
    return {"case_id": "AIME-2018-II-12", "witness": {"C": C.tolist(), "D": D.tolist(), "P": P.tolist()}, "max_side_abs_residual": max(abs(x) for x in side_residuals), "area_equality_abs_residual": abs(area_residual), "convex_turns": turns, "answer_area": triangle_area(A, B, C, D)}


def check_aime_2019_i_06() -> dict[str, object]:
    K, M, N, O = np.array([0.0, 0.0]), np.array([98.0, 0.0]), np.array([98.0, 65.0]), np.array([8.0, 0.0])
    t = -520 / 13829 + 28 * math.sqrt(13045) / 13829
    L = np.array([8 + 65 * t, -98 * t])
    pts = [K, L, M, N]
    turns = [cross(pts[(i + 1) % 4] - pts[i], pts[(i + 2) % 4] - pts[(i + 1) % 4]) for i in range(4)]
    return {"case_id": "AIME-2019-I-06", "witness": {"K": K.tolist(), "M": M.tolist(), "N": N.tolist(), "L": L.tolist(), "O": O.tolist()}, "MN": norm(M, N), "KL": norm(K, L), "KO": norm(K, O), "MO": norm(M, O), "MN_dot_KM": float(np.dot(N - M, M - K)), "KL_dot_LN": float(np.dot(L - K, N - L)), "(O-L)_dot_KN": float(np.dot(O - L, N - K)), "convex_turns": turns}


def check_aime_2020_ii_15() -> dict[str, object]:
    A, B, C = np.array([3.92145098, 25.04529231]), np.array([-11.0, 0.0]), np.array([11.0, 0.0])
    ax, ay = A
    center_y = (ax * ax + ay * ay - 121) / (2 * ay)
    T = np.array([0.0, -121 / center_y])
    X, Y = foot(T, A, B), foot(T, A, C)
    xy2, tx2, ty2 = norm(X, Y) ** 2, norm(T, X) ** 2, norm(T, Y) ** 2
    return {"case_id": "AIME-2020-II-15", "witness": {"A": A.tolist(), "T": T.tolist(), "X": X.tolist(), "Y": Y.tolist()}, "BT": norm(B, T), "CT": norm(C, T), "XY2": xy2, "given_sum": tx2 + ty2 + xy2, "acute_dot_products": [float(np.dot(B - A, C - A)), float(np.dot(A - B, C - B)), float(np.dot(A - C, B - C))], "side_lengths": [norm(A, B), norm(A, C), norm(B, C)]}


def check_aime_2021_i_13() -> dict[str, object]:
    r1, r2, d, r = 961.0, 625.0, 672.0, 1000.0
    x = (d * d + r1 * r1 - r2 * r2) / (2 * d)
    y = math.sqrt(r1 * r1 - x * x)
    ox, oy = x + r / 2, math.sqrt((r + r1) ** 2 - (x + r / 2) ** 2)
    half_chord = math.sqrt(r * r - (ox - x) ** 2)
    central_angle = 2 * math.asin(half_chord / r)
    return {"case_id": "AIME-2021-I-13", "witness": {"A": [x, y], "O": [ox, oy], "r": r}, "O1O": math.hypot(ox, oy), "O2O": math.hypot(ox - d, oy), "radical_axis_x": x, "half_chord": half_chord, "central_angle_rad": central_angle, "central_angle_deg": central_angle * 180 / math.pi}


def check_aime_2022_ii_07() -> dict[str, object]:
    m, b = sp.symbols("m b", real=True)
    e1 = (30 * m + b) ** 2 / (m * m + 1) - 24 ** 2
    e2 = (-30 * m + b) ** 2 / (m * m + 1) - 24 ** 2
    difference = sp.factor(e1 - e2)
    return {"case_id": "AIME-2022-II-07", "tangent_equation_difference": str(difference), "consequence_under_m_gt_0": "b=0", "distance_from_O1_to_l1_when_b_0": "0, not 6"}


def check_jmo_2019_08yk() -> dict[str, object]:
    b = (81 + 9 * sp.sqrt(13)) / 16
    c = (81 - 9 * sp.sqrt(13)) / 16
    A, B = sp.Point(0, 0), sp.Point(b, 0)
    C = sp.Point(-c / 2, sp.sqrt(3) * c / 2)
    D, E = sp.Point(b / 9, 0), sp.Point(C.x / 9, C.y / 9)
    a = B.distance(C)
    I = sp.Point((a * A.x + c * B.x + b * C.x) / (a + c + b), (a * A.y + c * B.y + b * C.y) / (a + c + b))
    return {"case_id": "JMO-2019-MATHNET-08yk/JMO-2019-PRE-08", "AB": str(sp.simplify(b)), "AC": str(sp.simplify(c)), "AB_minus_AC": str(sp.simplify(b - c)), "C_x": str(sp.simplify(C.x)), "DE2": str(sp.simplify(D.distance(E) ** 2)), "DI2": str(sp.simplify(D.distance(I) ** 2)), "EI2": str(sp.simplify(E.distance(I) ** 2)), "angle_A": "2*pi/3"}


def check_area_semantics() -> dict[str, object]:
    path = Path("/home/kabatan/work/solver-experiment-runtime/geosolver/src/geosolver/geometry/operations/basic.py")
    text = path.read_text(encoding="utf-8")
    return {"file": str(path), "contains_unsigned_area_return": "return Abs(s) / 2" in text, "line_reference": "basic.py:194-225"}


def main() -> int:
    checks = [check_aime_2018_ii_12(), check_aime_2019_i_06(), check_aime_2020_ii_15(), check_aime_2021_i_13(), check_aime_2022_ii_07(), check_jmo_2019_08yk(), check_area_semantics()]
    print(json.dumps(checks, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
