from __future__ import annotations

import math
import struct
import sys
from pathlib import Path

import pytest
from mpmath import mp

from geotarget.typed_refnum_intersections import (
    SEMANTIC_ABI,
    TypedIntersectRuntimeFault,
    UnsupportedTypedIntersect,
    compile_intersect_extension,
    evaluate_intersect_extension,
    extension_manifest,
    require_point_consumer,
)


def _reference_geometry():
    runtime = Path(__file__).resolve().parents[1] / "src/geotarget/_engine/runtime"
    path = str(runtime / "geosolver/src")
    if path not in sys.path:
        sys.path.insert(0, path)
    from geosolver.geometry import Circle, Intersect, Line, Point

    return Point, Line, Circle, Intersect


def _bits(value: object) -> bytes:
    return struct.pack(">d", float(value))


def _assert_point_bits(observed: object, expected: object) -> None:
    assert _bits(observed.x) == _bits(expected.x)
    assert _bits(observed.y) == _bits(expected.y)


@pytest.mark.parametrize(
    ("operand_types", "selector", "reverse"),
    [
        (("line2", "circle2"), {"n": 1}, False),
        (("line2", "circle2"), {"n": 2}, False),
        (("circle2", "line2"), {"n": 1}, True),
        (("line2", "circle2"), {"near": object()}, False),
        (("line2", "circle2"), {"far": object()}, False),
    ],
)
def test_unknown_line_circle_order_and_selectors_are_bit_exact(
    operand_types: tuple[str, str], selector: dict[str, object], reverse: bool
) -> None:
    Point, Line, Circle, Intersect = _reference_geometry()
    line = Line(Point(-10, 3), Point(10, 3))
    circle = Circle(Point(0, 0), 5)
    reference_point = Point(9, 0)
    selector_types = {name: "point2" for name in selector if name in {"near", "far", "exclude"}}
    plan = compile_intersect_extension(
        operand_types,
        selector,
        selector_operand_types=selector_types,
    )
    kwargs = {}
    if "n" in selector:
        kwargs["n"] = selector["n"]
    if "near" in selector:
        kwargs["near"] = reference_point
    if "far" in selector:
        kwargs["far"] = reference_point
    first, second = (circle, line) if reverse else (line, circle)

    expected = Intersect(first, second, **kwargs)
    observed = evaluate_intersect_extension(
        plan,
        first,
        second,
        point_factory=Point,
        near=kwargs.get("near"),
        far=kwargs.get("far"),
    )

    _assert_point_bits(observed.value, expected)
    assert observed.trace is not None
    assert observed.trace.selected_original_index in (0, 1)


@pytest.mark.parametrize("ordinal", [1, 2])
def test_unknown_circle_circle_candidate_order_is_bit_exact(ordinal: int) -> None:
    Point, _Line, Circle, Intersect = _reference_geometry()
    first = Circle(Point(0, 0), 5)
    second = Circle(Point(6, 0), 5)
    plan = compile_intersect_extension(("circle2", "circle2"), {"n": ordinal})

    expected = Intersect(first, second, n=ordinal)
    observed = evaluate_intersect_extension(plan, first, second, point_factory=Point)

    _assert_point_bits(observed.value, expected)


def test_unknown_line_line_and_parallel_semantics_are_bit_exact() -> None:
    Point, Line, _Circle, Intersect = _reference_geometry()
    first = Line(Point(0, 0), Point(1, 2))
    second = Line(Point(0, 1), Point(2, 0))
    plan = compile_intersect_extension(("line2", "line2"), {})
    expected = Intersect(first, second)
    observed = evaluate_intersect_extension(plan, first, second, point_factory=Point)
    _assert_point_bits(observed.value, expected)

    parallel = Line(Point(0, 2), Point(1, 4))
    assert Intersect(first, parallel) is None
    assert evaluate_intersect_extension(plan, first, parallel, point_factory=Point).value is None


def test_exclude_exact_and_approximate_equality_matches_reference() -> None:
    Point, Line, Circle, Intersect = _reference_geometry()
    line = Line(Point(-10, 0), Point(10, 0))
    circle = Circle(Point(0, 0), 5)
    plan = compile_intersect_extension(
        ("line2", "circle2"),
        {"exclude": object()},
        selector_operand_types={"exclude": "point2"},
    )
    old_dps = mp.dps
    try:
        mp.dps = 15
        for excluded in (Point(5, 0), Point(5 + 1e-15, 0)):
            from geosolver._internal.pipeline.evaluator.selection_trace import (
                capture_selection_trace,
                use_selection_symbol,
            )

            with (
                capture_selection_trace() as reference_trace,
                use_selection_symbol("P"),
            ):
                expected = Intersect(line, circle, exclude=excluded)
            observed = evaluate_intersect_extension(
                plan,
                line,
                circle,
                point_factory=Point,
                exclude=excluded,
                ambient_dps=15,
            )
            _assert_point_bits(observed.value, expected)
            assert observed.trace is not None
            assert observed.trace.selector_kind == "exclude"
            assert observed.trace.hp_authority_complete is False
            assert len(reference_trace) == 1
            assert observed.trace.selected_active_index == reference_trace[0].selected_index
            assert observed.trace.candidate_count == reference_trace[0].candidate_count
    finally:
        mp.dps = old_dps


def test_selector_type_schema_rejects_scalar_near_before_runtime() -> None:
    with pytest.raises(
        UnsupportedTypedIntersect, match="selector near requires point2.*got scalar"
    ):
        compile_intersect_extension(
            ("line2", "circle2"),
            {"near": object()},
            selector_operand_types={"near": "scalar"},
        )

    valid = compile_intersect_extension(
        ("line2", "circle2"),
        {"near": object()},
        selector_operand_types={"near": "point2"},
    )
    Point, Line, Circle, _Intersect = _reference_geometry()
    with pytest.raises(
        TypedIntersectRuntimeFault,
        match="selector near runtime type scalar does not match plan",
    ):
        evaluate_intersect_extension(
            valid,
            Line(Point(-10, 0), Point(10, 0)),
            Circle(Point(0, 0), 5),
            point_factory=Point,
            near=0.0,
        )


def test_nonmatching_exclude_preserves_point_list_union_and_point_consumer_falls_back() -> None:
    Point, Line, Circle, Intersect = _reference_geometry()
    line = Line(Point(-10, 0), Point(10, 0))
    circle = Circle(Point(0, 0), 5)
    excluded = Point(100, 100)
    plan = compile_intersect_extension(
        ("line2", "circle2"),
        {"exclude": object()},
        selector_operand_types={"exclude": "point2"},
    )

    expected = Intersect(line, circle, exclude=excluded)
    observed = evaluate_intersect_extension(
        plan,
        line,
        circle,
        point_factory=Point,
        exclude=excluded,
    )

    assert plan.result_type == "point_or_list"
    assert isinstance(expected, list) and isinstance(observed.value, list)
    assert len(expected) == len(observed.value) == 2
    for observed_point, expected_point in zip(observed.value, expected, strict=True):
        _assert_point_bits(observed_point, expected_point)
    with pytest.raises(UnsupportedTypedIntersect, match="Point consumer"):
        require_point_consumer(plan)

    ordinal_plan = compile_intersect_extension(
        ("line2", "circle2"),
        {"exclude": object(), "n": 2},
        selector_operand_types={"exclude": "point2", "n": "exact_int"},
    )
    assert ordinal_plan.result_type == "point2"
    require_point_consumer(ordinal_plan)
    expected_second = Intersect(line, circle, exclude=excluded, n=2)
    observed_second = evaluate_intersect_extension(
        ordinal_plan,
        line,
        circle,
        point_factory=Point,
        exclude=excluded,
    )
    _assert_point_bits(observed_second.value, expected_second)


@pytest.mark.parametrize("height", [5, 6])
def test_tangent_and_disjoint_max_clamp_are_bit_exact(height: int) -> None:
    Point, Line, Circle, Intersect = _reference_geometry()
    line = Line(Point(-10, height), Point(10, height))
    circle = Circle(Point(0, 0), 5)
    plan = compile_intersect_extension(("line2", "circle2"), {"n": 1})

    expected = Intersect(line, circle, n=1)
    observed = evaluate_intersect_extension(plan, line, circle, point_factory=Point)

    _assert_point_bits(observed.value, expected)


def test_degenerate_circle_circle_has_same_residual_bits_and_status() -> None:
    Point, _Line, Circle, Intersect = _reference_geometry()
    first = Circle(Point(0, 0), 5)
    second = Circle(Point(0, 0), 5)
    plan = compile_intersect_extension(("circle2", "circle2"), {"n": 1})

    def residual(call) -> list[float]:
        try:
            point = call()
            return [float(point.x), float(point.y)]
        except Exception:
            return [float("nan"), float("nan")]

    expected = residual(lambda: Intersect(first, second, n=1))
    observed = residual(
        lambda: evaluate_intersect_extension(plan, first, second, point_factory=Point).value
    )
    assert [_bits(value) for value in observed] == [_bits(value) for value in expected]
    assert all(math.isnan(value) for value in observed)


def test_frozen_branch_replay_and_hp_authority_fail_closed() -> None:
    Point, Line, Circle, _Intersect = _reference_geometry()
    line = Line(Point(-10, 0), Point(10, 0))
    circle = Circle(Point(0, 0), 5)
    near_plan = compile_intersect_extension(
        ("line2", "circle2"),
        {"near": object()},
        selector_operand_types={"near": "point2"},
    )
    replayed = evaluate_intersect_extension(
        near_plan,
        line,
        circle,
        point_factory=Point,
        near=Point(9, 0),
        frozen_branch_index=1,
    )
    assert replayed.trace is not None
    assert replayed.trace.selected_original_index == 1
    assert _bits(replayed.value.x) == _bits(-5.0)

    with pytest.raises(UnsupportedTypedIntersect, match="HP selector authority"):
        evaluate_intersect_extension(
            near_plan,
            line,
            circle,
            point_factory=Point,
            near=Point(9, 0),
            require_hp_authority=True,
        )

    ordinal_plan = compile_intersect_extension(("line2", "circle2"), {"n": 1})
    assert evaluate_intersect_extension(
        ordinal_plan,
        line,
        circle,
        point_factory=Point,
        require_hp_authority=True,
    ).hp_authority_complete


def test_support_manifest_and_keys_are_identity_free() -> None:
    selector_types = {"near": "point2", "n": "exact_int"}
    first = compile_intersect_extension(
        ("line2", "circle2"),
        {"near": object(), "n": 2},
        selector_operand_types=selector_types,
    )
    second = compile_intersect_extension(
        ("line2", "circle2"),
        {"near": "unrelated-runtime-node", "n": 2},
        selector_operand_types=selector_types,
    )
    assert first.support_key == second.support_key
    assert first.support_key.semantic_abi == SEMANTIC_ABI
    manifest = extension_manifest()
    assert manifest["case_specific_routing"] is False
    assert manifest["problem_identity_read"] is False
    assert manifest["support_key_fields"] == [
        "operand_types",
        "selector_kind",
        "selector_operand_types",
        "semantic_abi",
    ]
