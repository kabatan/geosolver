from __future__ import annotations

import sys
import time
from pathlib import Path

import pytest

from geotarget.continuation import _load_frozen
from geotarget.raw_libmp_backend import (
    UnsupportedRawLibmpBackend,
    compile_raw_libmp_program,
)
from geotarget.typed_refnum_ir import compile_typed_refnum_program


def _build(document: dict):
    runtime_root = Path(__file__).resolve().parents[1] / "src/geotarget/_engine/runtime"
    sys.path.insert(0, str(runtime_root / "geosolver/src"))
    base = _load_frozen(runtime_root)
    runtime = base._load_module(
        "geotarget_periodic_rounding_gate_runtime", base.PRECISION_RUNTIME
    )
    _case, _budget, evaluator = runtime.build_source_case(
        document, callback_cap=32, deadline=time.monotonic() + 120
    )
    return evaluator


def _problem(extra: list[dict[str, str]], measurement: str) -> dict:
    return {
        "task": "solve",
        "id": "unknown-generated-periodic-rounding-composition",
        "variables": {"names": ["t", "u", "r", "ax", "ay", "bx", "by", "z"]},
        "construction": [
            {"name": "O", "expr": "Point(0,0)"},
            {"name": "G", "expr": "Circle(O,abs(r)+1)"},
            {"name": "P", "expr": "PointOnCircle(G,t)"},
            {"name": "Q", "expr": "PointOnCircle(G,u)"},
            {"name": "A", "expr": "Point(ax,ay)"},
            {"name": "B", "expr": "Point(bx,by)"},
            {"name": "C", "expr": "Point(2,-3)"},
            *extra,
        ],
        "constraints": [{"def": measurement, "value": 1}],
        "guards": [],
        "answer": measurement,
        "post_process": "",
    }


@pytest.mark.parametrize(
    ("extra", "measurement", "consumer"),
    [
        ([{"name": "H", "expr": "Circumcircle(P,A,B)"}], "Distance(C,H)", "Circumcircle"),
        ([{"name": "R", "expr": "Reflect(P,A)"}], "Distance(R,B)", "ReflectPP"),
        (
            [
                {"name": "ell", "expr": "Line(P,A)"},
                {"name": "m", "expr": "PerpendicularLine(ell,B)"},
            ],
            "Distance(C,m)",
            "PerpendicularLineLP",
        ),
        (
            [
                {"name": "ell", "expr": "Line(P,A)"},
                {"name": "m", "expr": "Line(B,C)"},
                {"name": "X", "expr": "Intersect(ell,m,n=1)"},
            ],
            "Distance(X,C)",
            "Intersect",
        ),
        ([], "OnCircle(P,G)", "OnCirclePC"),
    ],
)
def test_unqualified_periodic_rounding_signatures_fail_closed(
    extra: list[dict[str, str]], measurement: str, consumer: str
) -> None:
    typed = compile_typed_refnum_program(_build(_problem(extra, measurement)).bundle)
    with pytest.raises(UnsupportedRawLibmpBackend, match=consumer):
        compile_raw_libmp_program(typed)
