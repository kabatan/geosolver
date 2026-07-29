from __future__ import annotations

import ast
import inspect
import math
import random
import re
import struct
import sys
import time
from pathlib import Path

import pytest

import geotarget.raw_libmp_backend as raw_backend
from geotarget.continuation import _load_frozen
from geotarget.raw_libmp_backend import (
    UnsupportedRawLibmpBackend,
    compile_raw_libmp_program,
)
from geotarget.typed_refnum_ir import compile_typed_refnum_program

_VARIABLES = ["t", "u", "r", "ax", "ay", "bx", "by", "z"]

# Every currently admitted PointOnCircle consumer is present in the generated
# DAG.  The test below also extracts the backend's literal policy sets, so a
# policy edit cannot silently outrun this matrix.
_ADMITTED_CONSUMERS = {
    "Abs",
    "Add",
    "AngleLL",
    "AnglePPP",
    "AreaPoints",
    "Circle",
    "CircleCenter",
    "CircleRadius",
    "DistanceCP",
    "DistanceLP",
    "DistancePC",
    "DistancePL",
    "DistancePP",
    "Div",
    "LineABC",
    "LinePP",
    "MidpointPP",
    "Mult",
    "Point",
    "PointX",
    "PointY",
    "Pow",
    "Sqrt",
    "Sub",
    "UAdd",
    "USub",
}
_UNQUALIFIED_CONSUMERS = {
    "Circumcircle",
    "Intersect",
    "OnCirclePC",
    "PerpendicularLineLP",
    "PerpendicularLinePL",
    "ReflectPL",
    "ReflectPP",
}


def _build(document: dict):
    runtime_root = Path(__file__).resolve().parents[1] / "src/geotarget/_engine/runtime"
    sys.path.insert(0, str(runtime_root / "geosolver/src"))
    base = _load_frozen(runtime_root)
    runtime = base._load_module(
        "geotarget_periodic_generality_test_runtime", base.PRECISION_RUNTIME
    )
    return runtime.build_source_case(
        document, callback_cap=512, deadline=time.monotonic() + 120
    )[2]


def _bits(value: float) -> bytes:
    return struct.pack(">d", float(value))


def _replace_names(expression: str, names: dict[str, str]) -> str:
    pattern = re.compile(r"\b(" + "|".join(map(re.escape, names)) + r")\b")
    return pattern.sub(lambda match: names[match.group(0)], expression)


def _generated_document(seed: int) -> dict:
    """Generate one identity-free, topologically shuffled V15 consumer DAG."""

    rng = random.Random(seed)
    canonical_levels = [
        [("O", "Point(0,0)"), ("A", "Point(ax,ay)"), ("B", "Point(bx,by)"), ("C", "Point(2,-3)")],
        [("G", "Circle(O,abs(r)+1)")],
        [("P", "PointOnCircle(G,t)"), ("Q", "PointOnCircle(G,u)")],
        [
            (
                "X",
                "Point(+((P.x+A.x)**2)/(abs(r)+1),sqrt(abs(P.y))+(-P.y)*2)",
            ),
            ("M", "Midpoint(P,A)"),
            ("LP", "Line(P,A)"),
            ("LQ", "Line(Q,B)"),
            ("LABC", "Line(P.x+A.x,P.y-B.y,z)"),
            ("H", "Circle(P,abs(P.x)+2)"),
        ],
        [
            ("Y", "Point(X.x+B.x,X.y-B.y)"),
            ("N", "Midpoint(M,B)"),
            ("LM", "Line(M,B)"),
            ("HM", "Circle(M,abs(P.y)+2)"),
        ],
    ]
    canonical_names = [name for level in canonical_levels for name, _expr in level]
    shuffled_names = canonical_names[:]
    rng.shuffle(shuffled_names)
    names = {
        canonical: f"N{seed:x}_{ordinal}_{shuffled_names.index(canonical)}"
        for ordinal, canonical in enumerate(canonical_names)
    }
    construction = []
    for level in canonical_levels:
        level = level[:]
        rng.shuffle(level)
        construction.extend(
            {
                "name": names[name],
                "expr": _replace_names(expression, names),
            }
            for name, expression in level
        )

    expressions = [
        "Distance(X,B)",
        "Distance(Y,C)",
        "Distance(M,B)",
        "Distance(N,C)",
        "Area(N,A,C)",
        "Angle(N,A,C)",
        "Distance(C,LM)",
        "Distance(LM,C)",
        "Distance(C,LABC)",
        "Distance(C,HM)",
        "Distance(HM,C)",
        "Distance(P,A)",
        "Distance(P,G)",
        "Area(P,A,Q,B,C)",
        "Angle(P,A,Q)",
        "Angle(LP,LQ)",
        "Distance(HM.center,C)",
    ]
    constraints = [
        {"def": _replace_names(expression, names), "value": 1}
        for expression in expressions
    ]
    # Exercise CircleRadius on a constraint side without introducing a
    # different terminal consumer.
    constraints.append(
        {
            "def": _replace_names("Distance(P,A)", names),
            "value": _replace_names("HM.radius", names),
        }
    )
    rng.shuffle(constraints)
    return {
        "task": "solve",
        "id": f"generated-identity-free-{rng.getrandbits(128):032x}",
        "variables": {"names": _VARIABLES},
        "construction": construction,
        "constraints": constraints,
        "guards": [],
        "answer": _replace_names("Distance(P,A)", names),
        "post_process": "",
    }


def _literal_set_from_compiler(variable_name: str) -> set[str]:
    tree = ast.parse(inspect.getsource(raw_backend.compile_raw_libmp_program))
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        if any(
            isinstance(target, ast.Name) and target.id == variable_name
            for target in node.targets
        ):
            value = ast.literal_eval(node.value)
            assert isinstance(value, set)
            return value
    raise AssertionError(f"compiler policy set {variable_name!r} was not found")


def _tainted_consumers(program) -> set[str]:
    analysis = program.numeric_effect_analysis()
    tainted = {node.index for node in analysis.nodes if node.opcode == "PointOnCircle"}
    consumers: set[str] = set()
    changed = True
    while changed:
        changed = False
        for edge in analysis.edges:
            if edge.producer_index not in tainted or edge.consumer_index is None:
                continue
            consumers.add(edge.consumer_opcode)
            if edge.consumer_index not in tainted:
                tainted.add(edge.consumer_index)
                changed = True
    return consumers


def _probes() -> list[list[float]]:
    periodic = [
        0.0,
        0.25,
        0.5,
        0.75,
        math.nextafter(0.25, 0.0),
        math.nextafter(0.25, 1.0),
        math.ulp(0.0),
        -math.ulp(0.0),
        float(2**52),
        -float(2**52),
    ]
    probes = [[value, 0.37, 1.25, 3.0, 4.0, -2.0, 5.0, 0.75] for value in periodic]
    rng = random.Random(0xC105E)
    probes.extend(
        [
            rng.uniform(-16, 16),
            rng.uniform(-16, 16),
            rng.uniform(-3, 3),
            rng.uniform(-8, 8),
            rng.uniform(-8, 8),
            rng.uniform(-8, 8),
            rng.uniform(-8, 8),
            rng.uniform(-3, 3),
        ]
        for _ in range(32)
    )
    return probes


def test_generated_matrix_covers_exactly_the_admitted_periodic_consumer_policy() -> None:
    qualified = _literal_set_from_compiler("qualified_point_on_circle_consumers")
    unqualified = _literal_set_from_compiler("unqualified_periodic_rounding_consumers")
    assert unqualified == _UNQUALIFIED_CONSUMERS
    assert qualified - unqualified == _ADMITTED_CONSUMERS

    program = compile_typed_refnum_program(_build(_generated_document(0xA11CE)).bundle)
    assert _tainted_consumers(program) == _ADMITTED_CONSUMERS


@pytest.mark.parametrize("seed", [0xA11CE, 0xB0B, 0xC0DE])
def test_identity_free_generated_v15_dags_match_independent_frozen_oracle(seed: int) -> None:
    reference = _build(_generated_document(seed))
    raw = compile_raw_libmp_program(compile_typed_refnum_program(reference.bundle))
    for values in _probes():
        expected = reference.evaluate_float_residual(values).residual_vector
        observed = raw.evaluate(values)
        assert [_bits(value) for value in observed] == [_bits(value) for value in expected]


def test_names_ids_and_topological_peer_order_do_not_change_results() -> None:
    programs = []
    references = []
    for seed in (0x51A, 0x51B, 0x51C):
        reference = _build(_generated_document(seed))
        references.append(reference)
        programs.append(compile_raw_libmp_program(compile_typed_refnum_program(reference.bundle)))

    for values in _probes()[:12]:
        frozen = [
            reference.evaluate_float_residual(values).residual_vector
            for reference in references
        ]
        observed = [program.evaluate(values) for program in programs]
        # Constraint order is intentionally shuffled, so compare multisets.
        frozen_bits = [sorted(_bits(value) for value in vector) for vector in frozen]
        observed_bits = [sorted(_bits(value) for value in vector) for vector in observed]
        assert frozen_bits[0] == frozen_bits[1] == frozen_bits[2]
        assert observed_bits == frozen_bits


@pytest.mark.parametrize(
    ("extra_construction", "constraint"),
    [
        ([{"name": "U", "expr": "Circumcircle(P,A,B)"}], "Distance(C,U)"),
        ([{"name": "U", "expr": "Reflect(P,A)"}], "Distance(C,U)"),
        (
            [
                {"name": "L", "expr": "Line(P,A)"},
                {"name": "U", "expr": "PerpendicularLine(L,B)"},
            ],
            "Distance(C,U)",
        ),
        (
            [
                {"name": "L", "expr": "Line(A,B)"},
                {"name": "U", "expr": "PerpendicularLine(P,L)"},
            ],
            "Distance(C,U)",
        ),
        (
            [
                {"name": "L", "expr": "Line(A,B)"},
                {"name": "U", "expr": "Reflect(P,L)"},
            ],
            "Distance(C,U)",
        ),
        (
            [
                {"name": "L", "expr": "Line(P,A)"},
                {"name": "K", "expr": "Line(B,C)"},
                {"name": "U", "expr": "Intersect(L,K,n=1)"},
            ],
            "Distance(C,U)",
        ),
        ([], "OnCircle(P,G)"),
    ],
)
def test_adding_an_unqualified_periodic_edge_forces_whole_problem_fallback(
    extra_construction: list[dict[str, str]], constraint: str
) -> None:
    document = {
        "task": "solve",
        "id": "identity-free-fallback-monotonicity",
        "variables": {"names": _VARIABLES},
        "construction": [
            {"name": "O", "expr": "Point(0,0)"},
            {"name": "G", "expr": "Circle(O,abs(r)+1)"},
            {"name": "P", "expr": "PointOnCircle(G,t)"},
            {"name": "A", "expr": "Point(ax,ay)"},
            {"name": "B", "expr": "Point(bx,by)"},
            {"name": "C", "expr": "Point(2,-3)"},
            *extra_construction,
        ],
        "constraints": [
            {"def": "Distance(P,A)", "value": 1},
            {"def": constraint, "value": 1},
        ],
        "guards": [],
        "answer": "Distance(P,A)",
        "post_process": "",
    }
    typed = compile_typed_refnum_program(_build(document).bundle)
    with pytest.raises(UnsupportedRawLibmpBackend, match="rounding edge"):
        compile_raw_libmp_program(typed)
