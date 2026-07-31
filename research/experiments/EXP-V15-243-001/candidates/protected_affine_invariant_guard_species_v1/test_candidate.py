from __future__ import annotations

import inspect

import numpy as np

from frozen import candidate


def _descriptor(point, residual, margins, *, valid=False):
    return candidate.RuntimeDescriptor(
        point=tuple(float(value) for value in point),
        raw_residual=tuple(float(value) for value in residual),
        typed_margins=tuple(
            sorted(
                candidate.TypedMargin(kind, f"guard/{index}", float(value))
                for index, (kind, value) in enumerate(margins)
            )
        ),
        finite=True,
        source_valid=valid,
    )


def _scheduler(*, shift=0.0, coordinate_scale=1.0, margin_scale=1.0, residual_scale=1.0):
    points = tuple((shift + coordinate_scale * index,) for index in range(16))
    descriptors = tuple(
        _descriptor(
            point,
            (residual_scale * (index - 4.5), residual_scale * (index + 0.25)),
            (("compare:relation", margin_scale * (index - 6.0)),),
        )
        for index, point in enumerate(points)
    )
    scheduler = candidate.OnlineNoveltyScheduler(
        points=points,
        sources=(candidate.INSURANCE_SOURCE,) * len(points),
        descriptors=descriptors,
    )
    endpoint = _descriptor(
        (shift,),
        (0.0, 0.0),
        (("compare:relation", -margin_scale),),
    )
    assert scheduler.observe_endpoint(endpoint)
    return scheduler, points


def test_75_percent_control_ordinals_are_byte_identical_and_side_is_complete():
    scheduler, points = _scheduler()
    order = scheduler.complete_order()
    assert sorted(order) == list(range(len(points)))
    for launch in range(len(points)):
        if launch % 4 != 3:
            assert order[launch] == launch
            assert np.asarray(points[order[launch]], dtype="<f8").tobytes() == np.asarray(
                points[launch], dtype="<f8"
            ).tobytes()
        else:
            assert order[launch] % 4 == 3


def test_translation_coordinate_and_equation_scale_do_not_change_side_order():
    base, _ = _scheduler()
    translated, _ = _scheduler(shift=193.0)
    scaled, _ = _scheduler(coordinate_scale=0.37)
    units, _ = _scheduler(margin_scale=11.0, residual_scale=0.031)
    assert base.complete_order() == translated.complete_order()
    assert base.complete_order() == scaled.complete_order()
    assert base.complete_order() == units.complete_order()


def test_failed_species_uses_typed_kind_not_key_or_coordinate():
    left = _descriptor((0,), (0,), (("compare:relation", -1),))
    right = candidate.RuntimeDescriptor(
        point=(1000.0,),
        raw_residual=(0.0,),
        typed_margins=(candidate.TypedMargin("compare:relation", "other/key", -99.0),),
        finite=True,
        source_valid=False,
    )
    assert candidate.failed_guard_species(left) == candidate.failed_guard_species(right)


def test_surface_excludes_identity_truth_target_and_outcome():
    surface = " ".join(
        (
            str(inspect.signature(candidate.OnlineNoveltyScheduler)),
            str(inspect.signature(candidate.OnlineNoveltyScheduler.observe_endpoint)),
        )
    ).lower()
    assert not any(
        token in surface
        for token in ("case_id", "source_hash", "truth", "target", "family", "outcome")
    )


def test_incomplete_schema_falls_back_to_exact_control_order():
    scheduler, points = _scheduler()
    broken = list(scheduler.descriptors)
    broken[1] = candidate.RuntimeDescriptor(
        point=broken[1].point,
        raw_residual=broken[1].raw_residual,
        typed_margins=(),
        finite=True,
        source_valid=False,
    )
    fallback = candidate.OnlineNoveltyScheduler(
        points=points,
        sources=(candidate.INSURANCE_SOURCE,) * len(points),
        descriptors=broken,
    )
    assert not fallback.activation_contract_holds
    assert fallback.complete_order() == tuple(range(len(points)))


def test_foreign_prefix_archive_falls_back_to_exact_control_order():
    scheduler, points = _scheduler()
    foreign_descriptors = tuple(
        _descriptor(
            point,
            (index * index + 0.5, index * index * index - 2.0),
            (("compare:relation", index * index - 3.0),),
        )
        for index, point in enumerate(points)
    )
    foreign = candidate.OnlineNoveltyScheduler(
        points=points,
        sources=(candidate.INSURANCE_SOURCE,) * len(points),
        descriptors=foreign_descriptors,
    )
    fallback = candidate.OnlineNoveltyScheduler(
        points=points,
        sources=(candidate.INSURANCE_SOURCE,) * len(points),
        descriptors=scheduler.descriptors,
        archive=foreign.archive,
    )
    assert not fallback.activation_contract_holds
    assert fallback.complete_order() == tuple(range(len(points)))


def test_nonfinite_or_ragged_prefix_is_rejected():
    scheduler, points = _scheduler()
    sources = (candidate.INSURANCE_SOURCE,) * len(points)
    with np.testing.assert_raises(ValueError):
        candidate.OnlineNoveltyScheduler(
            points=((0.0,), (float("inf"),)),
            sources=sources[:2],
            descriptors=scheduler.descriptors[:2],
        )
    with np.testing.assert_raises(ValueError):
        candidate.OnlineNoveltyScheduler(
            points=((0.0,), (1.0, 2.0)),
            sources=sources[:2],
            descriptors=scheduler.descriptors[:2],
        )
