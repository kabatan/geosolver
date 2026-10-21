#!/usr/bin/env python3
"""Geometry-first numeric cases for program self-training.

Labels are measured from constructed points using geo_primitives.py.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import math
import random
import re
import runpy
from collections import Counter
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
BENCH = ROOT / "benchmarks" / "humpty_configurations_v2"
PRIMITIVES_PATH = BENCH / "authoring" / "geo_primitives.py"
TEMPLATES_PATH = ROOT / "docs" / "research" / "qwen35-diverse-sft-2026-09-24" / "english_templates.py"
G = runpy.run_path(str(PRIMITIVES_PATH))
line = G["line"]
circle = G["circle"]
tangent_circle = G["tangent_circle"]
line_circle = G["lc"]
circle_circle = G["cc"]
other = G["other"]
foot = G["foot"]
dot = G["dot"]
cross = G["cross"]
unit = G["unit"]
NUMERIC_EN = runpy.run_path(str(TEMPLATES_PATH))["NUMERIC_EN"]
CONFIGS = ("H01", "H04", "H07", "H13", "H14", "H15", "DA01", "DA05")
SPLITS = ("visible", "repair", "selection", "final")
SPLIT_COUNTS = {"visible": 4, "repair": 4, "selection": 24, "final": 24}
BUILDER_VERSION = "direct-coordinate-v1"
TOL = 2e-8


class Reject(Exception):
    """Expected geometric or deduplication rejection with an audit category."""

    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


def _finite(x: float) -> bool:
    return math.isfinite(float(x))


def _close(x: float, y: float, tol: float = TOL) -> bool:
    return abs(float(x) - float(y)) <= tol * max(1.0, abs(float(x)), abs(float(y)))


def _point_close(x: complex, y: complex, tol: float = TOL) -> bool:
    return abs(x - y) <= tol * max(1.0, abs(x), abs(y))


def _length(a: complex, b: complex) -> float:
    return abs(a - b)


def _area(a: complex, b: complex, c: complex) -> float:
    return abs(cross(b - a, c - a)) / 2


def _circle_residual(p: complex, circ: tuple[complex, float]) -> float:
    return abs(abs(p - circ[0]) - circ[1])


def _param(p: complex, a: complex, b: complex) -> float:
    v = b - a
    if abs(v) < 1e-10:
        raise Reject("zero_length_line")
    return dot(p - a, v) / abs(v) ** 2


def _triangle_lengths(a: complex, b: complex, c: complex) -> tuple[float, float, float]:
    return _length(b, c), _length(c, a), _length(a, b)


def _scalene(a: complex, b: complex, c: complex) -> None:
    sides = _triangle_lengths(a, b, c)
    scale = max(sides)
    if scale <= 1e-9:
        raise Reject("degenerate_triangle")
    if min(abs(sides[i] - sides[j]) for i in range(3) for j in range(i)) <= 2e-7 * scale:
        raise Reject("isosceles_or_near_isosceles")
    if abs(cross(b - a, c - a)) <= 2e-9 * scale * scale:
        raise Reject("degenerate_triangle")


def _acute(a: complex, b: complex, c: complex) -> None:
    _scalene(a, b, c)
    vals = (dot(b - a, c - a), dot(a - b, c - b), dot(a - c, b - c))
    scale = max(_triangle_lengths(a, b, c))
    if min(vals) <= 2e-9 * scale * scale:
        raise Reject("not_acute_scalene")


def _orthocenter(a: complex, b: complex, c: complex) -> tuple[complex, complex]:
    o, _r = circle(a, b, c)
    return a + b + c - 2 * o, o


def _triangle_signature(a: complex, b: complex, c: complex) -> tuple[float, ...]:
    lengths = sorted(_triangle_lengths(a, b, c))
    mx = lengths[-1]
    if mx <= 1e-10:
        raise Reject("degenerate_triangle")
    return tuple(round(x / mx, 9) for x in lengths)


def _circle_signature(r1: float, r2: float, baseline: float) -> tuple[float, ...]:
    if baseline <= 1e-10:
        raise Reject("zero_baseline")
    return tuple(sorted((round(r1 / baseline, 9), round(r2 / baseline, 9))))


def _round_sig(v: float, digits: int = 17) -> float:
    v = float(v)
    if not math.isfinite(v):
        raise Reject("nonfinite_value")
    return float(format(v, f".{digits}g"))


def _xy(z: complex) -> list[float]:
    return [_round_sig(z.real, 17), _round_sig(z.imag, 17)]


def _float_map(values: dict[str, float]) -> dict[str, float]:
    return {k: _round_sig(v) for k, v in values.items()}


def _witness_points(points: dict[str, complex]) -> dict[str, list[float]]:
    return {k: _xy(v) for k, v in points.items()}


def _line_circle_ray(origin: complex, through: complex, circ: tuple[complex, float]) -> complex:
    if abs(through - origin) < 1e-10:
        raise Reject("zero_length_ray")
    pts = line_circle(origin, through, circ)
    positive = [p for p in pts if _param(p, origin, through) > 1e-8]
    if len(positive) != 1:
        raise Reject("ray_circle_branch")
    return positive[0]


def _result(givens: dict[str, float], answer: float, points: dict[str, complex], sig_kind: str,
            signature: tuple[float, ...], checks: dict[str, bool]) -> dict[str, Any]:
    if any(not _finite(v) for v in (*givens.values(), answer)):
        raise Reject("nonfinite_value")
    if answer <= 1e-10:
        raise Reject("nonpositive_answer")
    return {"givens": _float_map(givens), "answer": _round_sig(answer), "points": points,
            "signature_kind": sig_kind, "shape_signature": [float(x) for x in signature],
            "checks": checks}


def _shape_key(result: dict[str, Any]) -> tuple[Any, ...]:
    return (result["signature_kind"], *result["shape_signature"])


def _given_key(givens: dict[str, float]) -> tuple[tuple[str, float], ...]:
    return tuple(sorted((k, round(float(v), 8)) for k, v in givens.items()))


def _split_seed(seed: int, config: str, split: str) -> int:
    payload = f"{seed}|{config}|{split}|{BUILDER_VERSION}".encode()
    return int.from_bytes(hashlib.sha256(payload).digest()[:8], "big")


def _build_h01(shape: dict[str, complex]) -> dict[str, Any]:
    a, b, c = shape["A"], shape["B"], shape["C"]
    _acute(a, b, c)
    m = (b + c) / 2
    h, _ = _orthocenter(a, b, c)
    p = foot(h, a, m)
    scale = max(1.0, abs(m - a), abs(h - p))
    if abs(cross(m - a, p - a)) > 2e-7 * scale * scale:
        raise Reject("orthocenter_foot_not_on_AM")
    if abs(dot(h - p, m - a)) > 2e-7 * scale * scale:
        raise Reject("orthocenter_foot_not_perpendicular")
    givens = {"BC": _length(b, c), "AM": _length(a, m)}
    answer = _length(a, p)
    sig = _triangle_signature(a, b, c)
    points = {"A": a, "B": b, "C": c, "M": m, "H": h, "P": p}
    checks = {"acute_scalene": True, "P_on_AM": True, "HP_perp_AM": True}
    return _result(givens, answer, points, "sorted_normalized_triangle_sides", sig, checks)


def _build_h04(shape: dict[str, complex]) -> dict[str, Any]:
    a, b, c = shape["A"], shape["B"], shape["C"]
    _acute(a, b, c)
    m = (b + c) / 2
    h, _ = _orthocenter(a, b, c)
    p = foot(h, a, m)
    if abs(a - p) < 1e-9:
        raise Reject("AP_degenerate")
    mid_ap = (a + p) / 2
    t = line(mid_ap, mid_ap + 1j * (a - p), b, c)
    if not _param(t, b, c) < -1e-8:
        raise Reject("T_not_before_B")
    if not _close(_length(t, a), _length(t, p), 2e-7):
        raise Reject("T_not_on_perpendicular_bisector")
    givens = {"BT": _length(b, t), "BC": _length(b, c)}
    answer = _length(a, t)
    sig = _triangle_signature(a, b, c)
    points = {"A": a, "B": b, "C": c, "M": m, "H": h, "P": p, "T": t}
    checks = {"acute_scalene": True, "T_B_C_order": True, "TA_equals_TP": True}
    return _result(givens, answer, points, "sorted_normalized_triangle_sides", sig, checks)


def _build_h07(shape: dict[str, complex]) -> dict[str, Any]:
    a, b, m = shape["A"], shape["B"], shape["M"]
    if abs((b - a).imag) > 1e-8 or abs((b - a).real) < 1e-9:
        raise Reject("AB_not_horizontal")
    w1 = tangent_circle(a, b, m)
    w2 = tangent_circle(b, a, m)
    n = other(circle_circle(w1, w2), m)
    baseline = _length(a, b)
    if not (m.imag > 1e-8 and n.imag > m.imag + 1e-8):
        raise Reject("M_not_closer_than_N")
    _acute(n, a, b)
    c = other(line_circle(m, m + 1, w1), m)
    d = other(line_circle(m, m + 1, w2), m)
    e = line(a, c, b, d)
    p = line(a, n, c, d)
    q = line(b, n, c, d)
    o = (a + b) / 2
    f = foot(m, a, b)
    givens = {"AB": baseline, "ON": _length(o, n), "MF": _length(m, f)}
    answer = _area(e, p, q)
    sig = _circle_signature(w1[1], w2[1], baseline)
    points = {"A": a, "B": b, "M": m, "N": n, "C": c, "D": d,
              "E": e, "P": p, "Q": q, "O": o, "F": f,
              "circle1_center": w1[0], "circle2_center": w2[0]}
    checks = {"NAB_acute_scalene": True, "same_side_intersections": True,
              "M_before_N": True, "C_D_on_parallel_through_M": True,
              "tangent_circles": True}
    return _result(givens, answer, points, "sorted_tangent_radii_over_AB", sig, checks)


def _build_h13(shape: dict[str, complex]) -> dict[str, Any]:
    a, b, c = shape["A"], shape["B"], shape["C"]
    _acute(a, b, c)
    m = (a + c) / 2
    circ_bmc = circle(b, m, c)
    o, _r = circ_bmc
    k = line(c, c + 1j * (c - o), b, b + 1j * (c - b))
    orient_a = cross(c - b, a - b)
    orient_k = cross(c - b, k - b)
    if orient_a * orient_k >= -1e-8:
        raise Reject("K_not_opposite_A_side")
    j = line(a, k, b, m)
    ta, tb = _param(j, a, k), _param(j, b, m)
    if not (1e-8 < ta < 1 - 1e-8 and 1e-8 < tb < 1 - 1e-8):
        raise Reject("J_not_inside_both_segments")
    z, rz = circle(b, j, k)
    if not all(_close(_length(z, v), rz, 2e-7) for v in (b, j, k)):
        raise Reject("circle_BJK_degenerate")
    cos_c = dot(a - c, b - c) / (_length(a, c) * _length(b, c))
    givens = {"BC": _length(b, c), "BK": _length(b, k), "cos_ACB": cos_c}
    answer = _length(c, z)
    sig = _triangle_signature(a, b, c)
    points = {"A": a, "B": b, "C": c, "M": m, "K": k, "J": j, "Z": z,
              "circle_BMC_center": o, "circle_BJK_center": z}
    checks = {"acute_scalene": True, "K_tangent_at_C": True, "K_opposite_A": True,
              "J_inside_AK_and_BM": True, "circle_BJK_nondegenerate": True}
    return _result(givens, answer, points, "sorted_normalized_triangle_sides", sig, checks)


def _build_h14(shape: dict[str, complex]) -> dict[str, Any]:
    a, b, c = shape["A"], shape["B"], shape["C"]
    _acute(a, b, c)
    h, _ = _orthocenter(a, b, c)
    m = (b + c) / 2
    circum = circle(a, b, c)
    d = other(line_circle(a, b, (c, _length(c, a))), a)
    e = other(line_circle(a, c, (b, _length(b, a))), a)
    p = _line_circle_ray(m, d, circum)
    q = _line_circle_ray(m, e, circum)
    cbpm = circle(b, p, m)
    ccqm = circle(c, q, m)
    r = other(circle_circle(cbpm, ccqm), m)
    if min(abs(cross(b - p, m - p)), abs(cross(c - q, m - q))) < 1e-9:
        raise Reject("common_circles_degenerate")
    givens = {"AH": _length(a, h), "AR": _length(a, r)}
    answer = _area(a, h, r)
    sig = _triangle_signature(a, b, c)
    points = {"A": a, "B": b, "C": c, "M": m, "H": h, "D": d, "E": e,
              "P": p, "Q": q, "R": r, "circumcenter": circum[0],
              "circle_BPM_center": cbpm[0], "circle_CQM_center": ccqm[0]}
    checks = {"acute_scalene": True, "D_E_other_intersections": True,
              "P_Q_on_forward_rays": True, "R_common_point_other_than_M": True,
              "all_circles_nondegenerate": True}
    return _result(givens, answer, points, "sorted_normalized_triangle_sides", sig, checks)


def _build_h15(shape: dict[str, complex]) -> dict[str, Any]:
    a, b, c = shape["A"], shape["B"], shape["C"]
    _scalene(a, b, c)
    u, v = b - a, c - a
    if dot(u, v) <= 0 or not _close(dot(u, v) / (abs(u) * abs(v)), 0.5, 2e-7):
        raise Reject("angle_A_not_60")
    circum = circle(a, b, c)
    x = line(b, b + 1j * (b - circum[0]), c, c + 1j * (c - circum[0]))
    d = other(line_circle(a, x, circum), a)
    e = 2 * foot(d, b, c) - d
    c0 = 2 * foot(e, a, b) - e
    b0 = 2 * foot(e, a, c) - e
    k = line(b, b0, c, c0)
    givens = {"AB": _length(a, b), "BD": _length(b, d), "AD": _length(a, d)}
    answer = _length(b, k)
    sig = _triangle_signature(a, b, c)
    points = {"A": a, "B": b, "C": c, "X": x, "D": d, "E": e,
              "C0": c0, "B0": b0, "K": k, "circumcenter": circum[0]}
    checks = {"scalene": True, "angle_A_60": True, "D_on_circumcircle": True,
              "reflections_defined": True, "BB0_CC0_distinct": True}
    return _result(givens, answer, points, "sorted_normalized_triangle_sides", sig, checks)


def _build_da01(shape: dict[str, complex]) -> dict[str, Any]:
    a, b, c = shape["A"], shape["B"], shape["C"]
    _scalene(a, b, c)
    w1 = tangent_circle(a, c, b)
    w2 = tangent_circle(a, b, c)
    t = other(circle_circle(w1, w2), a)
    givens = {"AB": _length(a, b), "BC": _length(b, c), "CA": _length(c, a)}
    answer = _length(a, t)
    sig = _triangle_signature(a, b, c)
    points = {"A": a, "B": b, "C": c, "T": t,
              "circle1_center": w1[0], "circle2_center": w2[0]}
    checks = {"nondegenerate_scalene_triangle": True, "tangent_circles_nondegenerate": True,
              "T_other_intersection": True}
    return _result(givens, answer, points, "sorted_normalized_triangle_sides", sig, checks)


def _build_da05(shape: dict[str, complex]) -> dict[str, Any]:
    a, b, c = shape["A"], shape["B"], shape["C"]
    _acute(a, b, c)
    w1 = tangent_circle(b, c, a)
    w2 = tangent_circle(b, a, c)
    d = other(circle_circle(w1, w2), b)
    m = (b + c) / 2
    e = line(m, d, a, c)
    if not _param(e, m, d) > 1 + 1e-8:
        raise Reject("M_D_E_order")
    givens = {"BC": _length(b, c), "MD": _length(m, d)}
    answer = _length(d, e)
    sig = _triangle_signature(a, b, c)
    points = {"A": a, "B": b, "C": c, "D": d, "M": m, "E": e,
              "circle1_center": w1[0], "circle2_center": w2[0]}
    checks = {"acute_scalene": True, "M_D_E_order": True,
              "tangent_circles_nondegenerate": True}
    return _result(givens, answer, points, "sorted_normalized_triangle_sides", sig, checks)


BUILDERS = {"H01": _build_h01, "H04": _build_h04, "H07": _build_h07,
            "H13": _build_h13, "H14": _build_h14, "H15": _build_h15,
            "DA01": _build_da01, "DA05": _build_da05}


def _sample_triangle(rng: random.Random, config: str) -> dict[str, complex]:
    if config in {"H01", "H04", "DA05"}:
        bc = rng.uniform(5.0, 18.0)
        frac = rng.uniform(0.06, 0.94)
        x = frac * bc
        h0 = math.sqrt(x * (bc - x))
        y = h0 * rng.uniform(1.015, 2.8)
        return {"A": complex(x, y), "B": 0j, "C": complex(bc, 0)}
    if config == "H13":
        bc = rng.uniform(5.0, 18.0)
        dx = rng.uniform(0.07, 0.93) * bc
        y = math.sqrt(dx * (bc - dx)) * rng.uniform(1.015, 2.7)
        return {"A": complex(bc - dx, y), "B": 0j, "C": complex(bc, 0)}
    if config == "H14":
        half = rng.uniform(3.0, 10.0)
        x = rng.uniform(-0.78, 0.78) * half
        y = math.sqrt(half * half - x * x) * rng.uniform(1.02, 2.3)
        return {"A": complex(x, y), "B": complex(-half, 0), "C": complex(half, 0)}
    raise ValueError(config)


def _sample_shape(config: str, rng: random.Random) -> dict[str, complex]:
    if config in {"H01", "H04", "H13", "H14", "DA05"}:
        return _sample_triangle(rng, config)
    if config == "H07":
        ab = rng.uniform(5.0, 18.0)
        x = rng.uniform(0.05, 0.95) * ab
        y = rng.uniform(0.08, 1.8) * ab
        return {"A": 0j, "B": complex(ab, 0), "M": complex(x, y)}
    if config == "H15":
        ab, ac = rng.uniform(2.0, 16.0), rng.uniform(1.2, 17.0)
        return {"A": 0j, "B": complex(ab, 0),
                "C": complex(ac / 2, ac * math.sqrt(3) / 2)}
    if config == "DA01":
        ab, ac = rng.uniform(2.0, 16.0), rng.uniform(2.0, 16.0)
        angle = math.radians(rng.uniform(18.0, 162.0))
        return {"A": 0j, "B": complex(ab * math.cos(angle), ab * math.sin(angle)),
                "C": complex(ac, 0)}
    raise ValueError(config)


def _serialize_private(result: dict[str, Any], config: str, split: str, number: int,
                       seed: int, attempt: int) -> dict[str, Any]:
    return {
        "case_id": f"{config}-{split}-{number:03d}",
        "source_id": config,
        "split": split,
        "givens": result["givens"],
        "answer": result["answer"],
        "private_witness": {
            "points": _witness_points(result["points"]),
            "shape_signature": {"kind": result["signature_kind"], "normalized": result["shape_signature"]},
            "construction_checks": result["checks"],
            "provenance": {"builder": BUILDER_VERSION, "split_seed": seed, "candidate_attempt": attempt},
        },
    }


def _public_row(row: dict[str, Any]) -> dict[str, Any]:
    return {k: row[k] for k in ("case_id", "source_id", "split", "givens", "answer")}


def _points_from_witness(row: dict[str, Any]) -> dict[str, complex]:
    return {k: complex(float(v[0]), float(v[1]))
            for k, v in row["private_witness"]["points"].items()}


def _values_from_points(config: str, p: dict[str, complex]) -> tuple[dict[str, float], float]:
    if config == "H01":
        g, a = {"BC": _length(p["B"], p["C"]), "AM": _length(p["A"], p["M"])}, _length(p["A"], p["P"])
    elif config == "H04":
        g, a = {"BT": _length(p["B"], p["T"]), "BC": _length(p["B"], p["C"])}, _length(p["A"], p["T"])
    elif config == "H07":
        g = {"AB": _length(p["A"], p["B"]), "ON": _length(p["O"], p["N"]), "MF": _length(p["M"], p["F"])}
        a = _area(p["E"], p["P"], p["Q"])
    elif config == "H13":
        g = {"BC": _length(p["B"], p["C"]), "BK": _length(p["B"], p["K"]),
             "cos_ACB": dot(p["A"] - p["C"], p["B"] - p["C"]) / (_length(p["A"], p["C"]) * _length(p["B"], p["C"]))}
        a = _length(p["C"], p["Z"])
    elif config == "H14":
        g, a = {"AH": _length(p["A"], p["H"]), "AR": _length(p["A"], p["R"])}, _area(p["A"], p["H"], p["R"])
    elif config == "H15":
        g = {"AB": _length(p["A"], p["B"]), "BD": _length(p["B"], p["D"]), "AD": _length(p["A"], p["D"])}
        a = _length(p["B"], p["K"])
    elif config == "DA01":
        g = {"AB": _length(p["A"], p["B"]), "BC": _length(p["B"], p["C"]), "CA": _length(p["C"], p["A"])}
        a = _length(p["A"], p["T"])
    elif config == "DA05":
        g = {"BC": _length(p["B"], p["C"]), "MD": _length(p["M"], p["D"])}
        a = _length(p["D"], p["E"])
    else:
        raise ValueError(config)
    return g, a


def _signature_from_points(config: str, p: dict[str, complex]) -> tuple[str, tuple[float, ...]]:
    if config == "H07":
        baseline = _length(p["A"], p["B"])
        r1 = _length(p["A"], p["circle1_center"])
        r2 = _length(p["B"], p["circle2_center"])
        return "sorted_tangent_radii_over_AB", _circle_signature(r1, r2, baseline)
    return "sorted_normalized_triangle_sides", _triangle_signature(p["A"], p["B"], p["C"])


def _validate_construction(config: str, p: dict[str, complex]) -> None:
    if config in {"H01", "H04", "H13", "H14", "DA05"}:
        _acute(p["A"], p["B"], p["C"])
    elif config in {"H15", "DA01"}:
        _scalene(p["A"], p["B"], p["C"])
    if config == "H01":
        h, _ = _orthocenter(p["A"], p["B"], p["C"])
        m = (p["B"] + p["C"]) / 2
        q = foot(h, p["A"], m)
        if not (_point_close(h, p["H"]) and _point_close(m, p["M"]) and _point_close(q, p["P"])):
            raise AssertionError("H01 orthocenter or projection witness mismatch")
    elif config == "H04":
        h, _ = _orthocenter(p["A"], p["B"], p["C"])
        m = (p["B"] + p["C"]) / 2
        q = foot(h, p["A"], m)
        t = p["T"]
        if not (_point_close(h, p["H"]) and _point_close(m, p["M"]) and _point_close(q, p["P"])):
            raise AssertionError("H04 orthocenter or projection witness mismatch")
        if not (_param(t, p["B"], p["C"]) < 0 and _close(_length(t, p["A"]), _length(t, p["P"]))):
            raise AssertionError("H04 branch or perpendicular bisector check failed")
    elif config == "H07":
        a, b, m, n = (p[k] for k in ("A", "B", "M", "N"))
        _acute(n, a, b)
        if not (m.imag > 0 and n.imag > m.imag):
            raise AssertionError("H07 intersection order failed")
        r1, r2 = _length(a, p["circle1_center"]), _length(b, p["circle2_center"])
        for center, radius, through in ((p["circle1_center"], r1, (a, m, p["C"])),
                                         (p["circle2_center"], r2, (b, m, p["D"]))):
            if any(not _close(_length(center, pt), radius) for pt in through):
                raise AssertionError("H07 tangent-circle points failed")
        if any(abs(pt.imag - m.imag) > 3e-7 for pt in (p["C"], p["D"])):
            raise AssertionError("H07 horizontal branch failed")
    elif config == "H13":
        a, b, c, m, k, j, z = (p[k] for k in ("A", "B", "C", "M", "K", "J", "Z"))
        if not _point_close(m, (a + c) / 2):
            raise AssertionError("H13 midpoint failed")
        if cross(c - b, a - b) * cross(c - b, k - b) >= 0:
            raise AssertionError("H13 K side failed")
        center_bmc = p["circle_BMC_center"]
        if abs(dot(c - center_bmc, k - c)) > 5e-7 * max(1.0, abs(c - center_bmc) * abs(k - c)):
            raise AssertionError("H13 tangent at C failed")
        if not (1e-8 < _param(j, a, k) < 1 - 1e-8 and 1e-8 < _param(j, b, m) < 1 - 1e-8):
            raise AssertionError("H13 J interior branch failed")
        if not _close(_length(z, b), _length(z, j)) or not _close(_length(z, b), _length(z, k)):
            raise AssertionError("H13 circle center failed")
    elif config == "H14":
        a, b, c, m, h, d, e, p0, q0, r = (p[k] for k in ("A", "B", "C", "M", "H", "D", "E", "P", "Q", "R"))
        circum = circle(a, b, c)
        for x, center, rad in ((d, c, _length(c, a)), (e, b, _length(b, a))):
            if not _close(_length(x, center), rad):
                raise AssertionError("H14 auxiliary equal-radius circle failed")
        if not all(_close(_circle_residual(x, circum), 0) for x in (p0, q0)):
            raise AssertionError("H14 P/Q not on circumcircle")
        if not (_param(p0, m, d) > 0 and _param(q0, m, e) > 0):
            raise AssertionError("H14 forward ray branch failed")
        c1, c2 = p["circle_BPM_center"], p["circle_CQM_center"]
        r1, r2 = _length(c1, b), _length(c2, c)
        if any(not _close(_length(c1, z), r1) for z in (p0, m, r)) or any(
            not _close(_length(c2, z), r2) for z in (q0, m, r)
        ):
            raise AssertionError("H14 common circles failed")
    elif config == "H15":
        a, b, c, d, e, b0, c0, k = (p[x] for x in ("A", "B", "C", "D", "E", "B0", "C0", "K"))
        if not _close(dot(b - a, c - a) / (_length(a, b) * _length(a, c)), 0.5):
            raise AssertionError("H15 fixed angle failed")
        if not _close(_circle_residual(d, circle(a, b, c)), 0):
            raise AssertionError("H15 D not on circumcircle")
        if not _close(_length(e, 2 * foot(d, b, c) - d), 0):
            raise AssertionError("H15 first reflection failed")
        if not _close(_length(b0, 2 * foot(e, a, c) - e), 0) or not _close(_length(c0, 2 * foot(e, a, b) - e), 0):
            raise AssertionError("H15 second reflections failed")
        if abs(cross(b0 - b, c0 - c)) < 1e-9:
            raise AssertionError("H15 derived lines coincide or are parallel")
        if max(abs(cross(b0 - b, k - b)), abs(cross(c0 - c, k - c))) > 5e-7:
            raise AssertionError("H15 K not on both derived lines")
    elif config == "DA01":
        a, b, c, t = (p[k] for k in ("A", "B", "C", "T"))
        for center_key, center, tangent_dir, points in (
            ("circle1_center", p["circle1_center"], c - a, (a, b, t)),
            ("circle2_center", p["circle2_center"], b - a, (a, c, t)),
        ):
            radius = _length(center, a)
            if abs(dot(center - a, tangent_dir)) > 5e-7 * max(1.0, radius * abs(tangent_dir)):
                raise AssertionError("DA01 tangency failed")
            if any(not _close(_length(center, z), radius) for z in points):
                raise AssertionError("DA01 circle incidence failed")
    elif config == "DA05":
        a, b, c, d, m, e = (p[k] for k in ("A", "B", "C", "D", "M", "E"))
        w1, w2 = p["circle1_center"], p["circle2_center"]
        for center, pts, direction in ((w1, (a, b, d), c - b), (w2, (b, c, d), a - b)):
            radius = _length(center, b)
            if any(not _close(_length(center, z), radius) for z in pts):
                raise AssertionError("DA05 tangent-circle incidence failed")
            if abs(dot(center - b, direction)) > 5e-7 * max(1.0, radius * abs(direction)):
                raise AssertionError("DA05 tangency failed")
        if not (_point_close(m, (b + c) / 2) and _param(e, m, d) > 1 + 1e-8):
            raise AssertionError("DA05 midpoint/order failed")


def validate_rows(private_rows: list[dict[str, Any]], public_rows: list[dict[str, Any]]) -> dict[str, Any]:
    ids: set[str] = set()
    shape_keys: dict[str, set[tuple[Any, ...]]] = {cid: set() for cid in CONFIGS}
    given_keys: dict[str, set[tuple[tuple[str, float], ...]]] = {cid: set() for cid in CONFIGS}
    counts: Counter[tuple[str, str]] = Counter()
    by_id: dict[str, dict[str, Any]] = {}
    for row in private_rows:
        cid = row["source_id"]
        if cid not in CONFIGS or row["case_id"] in ids:
            raise AssertionError("unknown or duplicate case identity")
        ids.add(row["case_id"])
        if set(row["givens"]) != set(re.findall(r"\{([A-Za-z0-9_]+)\}", NUMERIC_EN[cid])):
            raise AssertionError(f"{cid}: public input keys do not match NUMERIC_EN")
        if row["split"] not in SPLITS:
            raise AssertionError("unknown split")
        counts[(cid, row["split"])] += 1
        if any(not _finite(v) for v in (*row["givens"].values(), row["answer"])) or row["answer"] <= 0:
            raise AssertionError(f"{row['case_id']}: invalid scalar")
        points = _points_from_witness(row)
        _validate_construction(cid, points)
        direct_givens, direct_answer = _values_from_points(cid, points)
        if set(direct_givens) != set(row["givens"]):
            raise AssertionError(f"{row['case_id']}: direct given keys differ")
        for k in direct_givens:
            if not _close(direct_givens[k], row["givens"][k], 5e-9):
                raise AssertionError(f"{row['case_id']}: {k} does not match witness")
        if not _close(direct_answer, row["answer"], 5e-9):
            raise AssertionError(f"{row['case_id']}: answer does not match witness")
        signature_kind, signature = _signature_from_points(cid, points)
        saved_sig = row["private_witness"]["shape_signature"]
        if signature_kind != saved_sig["kind"] or tuple(signature) != tuple(saved_sig["normalized"]):
            raise AssertionError(f"{row['case_id']}: shape signature mismatch")
        skey = (signature_kind, *signature)
        gkey = _given_key(row["givens"])
        if skey in shape_keys[cid]:
            raise AssertionError(f"{row['case_id']}: similar geometry duplicates another split")
        if gkey in given_keys[cid]:
            raise AssertionError(f"{row['case_id']}: duplicate givens")
        shape_keys[cid].add(skey)
        given_keys[cid].add(gkey)
        if not all(row["private_witness"]["construction_checks"].values()):
            raise AssertionError(f"{row['case_id']}: a construction check is false")
        by_id[row["case_id"]] = row
    for cid in CONFIGS:
        for split in SPLITS:
            if counts[(cid, split)] != SPLIT_COUNTS[split]:
                raise AssertionError(f"{cid}/{split}: got {counts[(cid, split)]}, expected {SPLIT_COUNTS[split]}")
    expected_public = [_public_row(row) for row in private_rows if row["split"] in {"visible", "repair"}]
    if public_rows != expected_public:
        raise AssertionError("public manifest differs from the visible/repair private projection")
    if any("private_witness" in row for row in public_rows):
        raise AssertionError("private witness leaked into public rows")
    return {"private_rows": len(private_rows), "public_rows": len(public_rows),
            "counts_by_config_split": {cid: {s: counts[(cid, s)] for s in SPLITS} for cid in CONFIGS},
            "unique_shape_signatures": {cid: len(shape_keys[cid]) for cid in CONFIGS},
            "unique_given_tuples": {cid: len(given_keys[cid]) for cid in CONFIGS}}


def generate(seed: int = 20260926, max_attempts: int = 250000) -> tuple[list[dict[str, Any]], dict[str, Any], list[dict[str, Any]]]:
    private_rows: list[dict[str, Any]] = []
    rejected_rows: list[dict[str, Any]] = []
    statistics: dict[str, Any] = {"root_seed": seed, "configs": {}, "split_counts": dict(SPLIT_COUNTS)}
    for config in CONFIGS:
        expected_givens = set(re.findall(r"\{([A-Za-z0-9_]+)\}", NUMERIC_EN[config]))
        config_shapes: set[tuple[Any, ...]] = set()
        config_givens: set[tuple[tuple[str, float], ...]] = set()
        cstats: dict[str, Any] = {}
        for split in SPLITS:
            split_seed = _split_seed(seed, config, split)
            rng = random.Random(split_seed)
            rejected: Counter[str] = Counter()
            accepted = 0
            attempt = 0
            while accepted < SPLIT_COUNTS[split]:
                attempt += 1
                if attempt > max_attempts:
                    raise RuntimeError(f"{config}/{split}: exhausted attempts; rejects={dict(rejected)}")
                try:
                    shape = _sample_shape(config, rng)
                    result = BUILDERS[config](shape)
                except Reject as exc:
                    rejected[exc.reason] += 1
                    rejected_rows.append({"source_id": config, "split": split, "candidate_attempt": attempt,
                                          "seed": split_seed, "reason": exc.reason,
                                          "sampled_input_points": _witness_points(shape)})
                    continue
                except (AssertionError, ZeroDivisionError, OverflowError, ValueError):
                    rejected["primitive_or_construction_failure"] += 1
                    rejected_rows.append({"source_id": config, "split": split, "candidate_attempt": attempt,
                                          "seed": split_seed, "reason": "primitive_or_construction_failure",
                                          "sampled_input_points": _witness_points(shape)})
                    continue
                got_names = set(result["givens"])
                if got_names != expected_givens:
                    raise AssertionError((config, sorted(got_names), sorted(expected_givens)))
                skey = _shape_key(result)
                if skey in config_shapes:
                    rejected["similarity_duplicate"] += 1
                    rejected_rows.append({"source_id": config, "split": split, "candidate_attempt": attempt,
                                          "seed": split_seed, "reason": "similarity_duplicate",
                                          "sampled_input_points": _witness_points(shape),
                                          "candidate_givens": result["givens"],
                                          "candidate_shape_signature": result["shape_signature"]})
                    continue
                gkey = _given_key(result["givens"])
                if gkey in config_givens:
                    rejected["duplicate_givens"] += 1
                    rejected_rows.append({"source_id": config, "split": split, "candidate_attempt": attempt,
                                          "seed": split_seed, "reason": "duplicate_givens",
                                          "sampled_input_points": _witness_points(shape),
                                          "candidate_givens": result["givens"],
                                          "candidate_shape_signature": result["shape_signature"]})
                    continue
                config_shapes.add(skey)
                config_givens.add(gkey)
                accepted += 1
                private_rows.append(_serialize_private(result, config, split, accepted, split_seed, attempt))
            cstats[split] = {"seed": split_seed, "attempts": attempt, "accepted": accepted,
                             "rejected": dict(sorted(rejected.items()))}
        statistics["configs"][config] = cstats
    statistics["rejected_case_count"] = len(rejected_rows)
    return private_rows, statistics, rejected_rows


def _eval_number(expr: Any) -> float:
    """Read a tiny arithmetic expression from an old witness for comparison only."""
    if isinstance(expr, (int, float)):
        return float(expr)
    node = ast.parse(str(expr), mode="eval").body

    def visit(n: ast.AST) -> float:
        if isinstance(n, ast.Constant) and isinstance(n.value, (int, float)):
            return float(n.value)
        if isinstance(n, ast.UnaryOp) and isinstance(n.op, ast.USub):
            return -visit(n.operand)
        if isinstance(n, ast.BinOp):
            a, b = visit(n.left), visit(n.right)
            if isinstance(n.op, ast.Add):
                return a + b
            if isinstance(n.op, ast.Sub):
                return a - b
            if isinstance(n.op, ast.Mult):
                return a * b
            if isinstance(n.op, ast.Div):
                return a / b
            if isinstance(n.op, ast.Pow):
                return a**b
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == "sqrt" and len(n.args) == 1:
            return math.sqrt(visit(n.args[0]))
        raise ValueError(f"unsupported old-witness value: {expr}")

    return visit(node)


def check_old_witnesses() -> dict[str, Any]:
    """Rebuild approved base witnesses from original construction coordinates.

    Canonical answers are compared only after direct construction and measurement;
    they are not imported into sampling, labels, or branch selection.
    """
    h_cards = json.loads((BENCH / "authoring" / "h_revision.json").read_text())
    da_cards = json.loads((BENCH / "authoring" / "da_revision.json").read_text())
    cards = {c["id"]: c for c in [*h_cards, *da_cards] if c.get("id") in CONFIGS}
    old_rows = {json.loads(line)["id"]: json.loads(line)
                for line in (BENCH / "training_problems.jsonl").read_text().splitlines()}
    checked: dict[str, Any] = {}
    for cid in CONFIGS:
        witness = cards[cid]["feasibility"]["witness"]
        pts = {k: complex(_eval_number(v[0]), _eval_number(v[1]))
               for k, v in witness["points"].items()}
        input_points = {k: pts[k] for k in (("A", "B", "M") if cid == "H07" else ("A", "B", "C"))}
        rebuilt = BUILDERS[cid](input_points)
        old_givens = witness["given_values"]
        for key, value in rebuilt["givens"].items():
            if key not in old_givens or not _close(value, _eval_number(old_givens[key]), 3e-7):
                raise AssertionError(f"{cid}: direct rebuilt given {key} disagrees with old witness")
        if not _close(rebuilt["answer"], _eval_number(witness["answer"]), 3e-7):
            raise AssertionError(f"{cid}: direct answer disagrees with original authoring witness")
        if not _close(rebuilt["answer"], _eval_number(old_rows[cid]["answer_exact"]), 3e-7):
            raise AssertionError(f"{cid}: direct answer disagrees with canonical base case")
        checked[cid] = {"direct_givens": rebuilt["givens"], "direct_answer": rebuilt["answer"],
                        "old_witness_match": True, "canonical_answer_match": True}
    return checked


def _file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text("".join(json.dumps(row, ensure_ascii=False, allow_nan=False) + "\n" for row in rows))
    tmp.replace(path)


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=20260926)
    parser.add_argument("--max-attempts", type=int, default=250000,
                        help="maximum proposals per config/split")
    parser.add_argument("--out-dir", type=Path, default=HERE)
    parser.add_argument("--dry-run", action="store_true", help="generate and validate without writing manifests")
    parser.add_argument("--verify-only", action="store_true", help="validate already frozen manifests and old witnesses")
    args = parser.parse_args()

    old_checks = check_old_witnesses()
    if args.verify_only:
        private_rows = _read_jsonl(args.out_dir / "numeric_cases_private.jsonl")
        public_rows = _read_jsonl(args.out_dir / "numeric_cases_public.jsonl")
        rejected_rows = _read_jsonl(args.out_dir / "numeric_cases_rejections.private.jsonl")
        report = validate_rows(private_rows, public_rows)
        print(json.dumps({"validation": report, "old_witness_checks": old_checks,
                          "rejected_case_count": len(rejected_rows)}, ensure_ascii=False, indent=2))
        return

    private_rows, statistics, rejected_rows = generate(args.seed, args.max_attempts)
    public_rows = [_public_row(r) for r in private_rows if r["split"] in {"visible", "repair"}]
    validation = validate_rows(private_rows, public_rows)
    summary = {"validation": validation, "generation": statistics,
               "old_witness_checks": old_checks, "rejected_case_count": len(rejected_rows),
               "inputs": {p.name: _file_hash(p) for p in (PRIMITIVES_PATH, TEMPLATES_PATH,
                         BENCH / "authoring" / "h_revision.json", BENCH / "authoring" / "da_revision.json",
                         BENCH / "training_problems.jsonl")}}
    if not args.dry_run:
        args.out_dir.mkdir(parents=True, exist_ok=True)
        _write_jsonl(args.out_dir / "numeric_cases_private.jsonl", private_rows)
        _write_jsonl(args.out_dir / "numeric_cases_public.jsonl", public_rows)
        _write_jsonl(args.out_dir / "numeric_cases_rejections.private.jsonl", rejected_rows)
        summary["outputs"] = {name: _file_hash(args.out_dir / name) for name in (
            "numeric_cases_private.jsonl", "numeric_cases_public.jsonl", "numeric_cases_rejections.private.jsonl")}
    print(json.dumps(summary, ensure_ascii=False, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
