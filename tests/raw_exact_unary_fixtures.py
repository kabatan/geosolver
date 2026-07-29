"""Case-independent fixtures for the next raw exact-unary ABI.

This is intentionally not a test module yet.  The raw backend implementation
is being changed independently; these fixtures give its differential tests a
shared set of source problems and probes without coupling admission to corpus
identity.
"""

from __future__ import annotations

import math


def exact_unary_composition_problem(identifier: str = "unknown-exact-unary-composition") -> dict:
    """Non-square radicals and exact trig flow through general geometry."""

    return {
        "task": "solve",
        "id": identifier,
        "variables": {"names": ["x", "y"]},
        "construction": [
            {"name": "s", "expr": "sqrt(2)"},
            {"name": "c", "expr": "cos(2)"},
            {"name": "q", "expr": "sin(3)"},
            {"name": "O", "expr": "Point(0, 0)"},
            {"name": "A", "expr": "Point(s, 0)"},
            {"name": "B", "expr": "Point(0, s)"},
            {"name": "U", "expr": "Point(c, q)"},
            {"name": "Z", "expr": "Point(s - s, c - c)"},
            {"name": "P", "expr": "Point(x, y)"},
            {"name": "ell", "expr": "Line(A, B)"},
        ],
        "constraints": [
            {"def": "Distance(Z, O)", "value": 0},
            {"def": "Area(O, A, B)", "value": 0},
            {"def": "Distance(A, B)", "value": 0},
            {"def": "Distance(A, ell)", "value": 0},
            {"def": "Distance(U, O)", "value": 0},
            {"def": "Distance(P, ell)", "value": 0},
        ],
        "guards": [],
        "answer": "Distance(P, U)",
        "post_process": "",
    }


def exact_unary_degenerate_problem(identifier: str = "unknown-exact-unary-degenerate") -> dict:
    """Exact cancellation must trigger the frozen Line construction fault."""

    return {
        "task": "solve",
        "id": identifier,
        "variables": {"names": ["x"]},
        "construction": [
            {"name": "s", "expr": "sqrt(2)"},
            {"name": "c", "expr": "cos(2)"},
            {"name": "A", "expr": "Point(s, c)"},
            {"name": "B", "expr": "Point(s, c)"},
            {"name": "bad", "expr": "Line(A, B)"},
            {"name": "P", "expr": "Point(x, 0)"},
        ],
        "constraints": [
            {"def": "Distance(P, A)", "value": 1},
            {"def": "Distance(P, bad)", "value": 0},
        ],
        "guards": [],
        "answer": "Distance(P, A)",
        "post_process": "",
    }


EXACT_UNARY_PROBES = (
    (0.0, 0.0),
    (math.sqrt(2.0), 0.0),
    (math.nextafter(math.sqrt(2.0), 0.0), math.nextafter(0.0, 1.0)),
    (-3.25, 7.5),
)

DEGENERATE_PROBES = ((0.0,), (1.0,), (-4.5,))
