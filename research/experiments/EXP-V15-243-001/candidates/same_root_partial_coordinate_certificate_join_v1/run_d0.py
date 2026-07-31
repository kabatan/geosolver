#!/usr/bin/env python3
"""Generated D0/adversary for same-root partial-coordinate joining."""

from __future__ import annotations

from dataclasses import replace
from fractions import Fraction as Q
import hashlib
import json
from pathlib import Path

from candidate import (
    Descriptor,
    ExactifierAttempt,
    Interval,
    PartialCoordinateFact,
    ReplayBinding,
    SourceSystem,
    boundary_manifest,
    join_partial_coordinates,
)


HERE = Path(__file__).resolve().parent


def I(lower, upper):
    return Interval(Q(lower), Q(upper))


BINDING = ReplayBinding("source-a", "guard-a", "branch-a", "target-a")


def quadratic_system():
    def residual(point):
        x, y = point
        return x * x - 2, y * y - 3

    def jacobian(box):
        x, y = box
        return ((I(2 * x.lower, 2 * x.upper), I(0, 0)), (I(0, 0), I(2 * y.lower, 2 * y.upper)))

    return SourceSystem(2, BINDING.source_sha256, residual, jacobian)


def linear_system():
    def residual(point):
        x, y = point
        return x, y

    def jacobian(_box):
        return ((I(1, 1), I(0, 0)), (I(0, 0), I(1, 1)))

    return SourceSystem(2, BINDING.source_sha256, residual, jacobian)


def two_root_system():
    def residual(point):
        x, y = point
        return x * x - 1, y

    def jacobian(box):
        x, _y = box
        return ((I(2 * x.lower, 2 * x.upper), I(0, 0)), (I(0, 0), I(1, 1)))

    return SourceSystem(2, BINDING.source_sha256, residual, jacobian)


DX = Descriptor((1, 0, -2), 1, I(Q(7, 5), Q(3, 2)))
DY = Descriptor((1, 0, -3), 1, I(Q(17, 10), Q(9, 5)))
ZERO = Descriptor((1, 0), 0, I(Q(-1, 10), Q(1, 10)))
ONE = Descriptor((1, -1), 0, I(Q(9, 10), Q(11, 10)))
MINUS_ONE = Descriptor((1, 1), 0, I(Q(-11, 10), Q(-9, 10)))


def positive_attempts():
    box = (I(Q(7, 5), Q(3, 2)), I(Q(17, 10), Q(9, 5)))
    return (
        ExactifierAttempt(
            11, 2, BINDING, box,
            (PartialCoordinateFact(0, box[0], minpoly=DX.minpoly),),
        ),
        ExactifierAttempt(
            11, 3, BINDING, box,
            (PartialCoordinateFact(
                0, box[0], real_root_ordinal=DX.real_root_ordinal, isolator=DX.isolator,
            ),),
        ),
        ExactifierAttempt(
            4, 7, BINDING, box,
            (PartialCoordinateFact(
                1, box[1], minpoly=DY.minpoly,
                real_root_ordinal=DY.real_root_ordinal, isolator=DY.isolator,
            ),),
        ),
    )


def signature(proposal):
    return (
        proposal.binding,
        proposal.descriptors,
        proposal.certificate.source_hull,
        proposal.certificate.krawczyk_image,
        proposal.consumed_attempts,
    )


def run():
    system = quadratic_system()
    positive = positive_attempts()
    checks = []

    joined = join_partial_coordinates(system, positive)
    checks.append(("positive-staggered-x-y", len(joined.proposals) == 1))

    permuted = join_partial_coordinates(system, tuple(reversed(positive)))
    checks.append(("endpoint-rung-permutation", len(permuted.proposals) == 1 and signature(joined.proposals[0]) == signature(permuted.proposals[0])))

    box_left = (I(Q(-11, 10), Q(-9, 10)), I(Q(-1, 10), Q(1, 10)))
    box_right = (I(Q(9, 10), Q(11, 10)), I(Q(-1, 10), Q(1, 10)))
    two_roots = (
        ExactifierAttempt(1, 1, BINDING, box_left, (PartialCoordinateFact(0, box_left[0], MINUS_ONE.minpoly, MINUS_ONE.real_root_ordinal, MINUS_ONE.isolator),)),
        ExactifierAttempt(2, 1, BINDING, box_right, (PartialCoordinateFact(1, box_right[1], ZERO.minpoly, ZERO.real_root_ordinal, ZERO.isolator),)),
    )
    checks.append(("negative-two-roots-in-hull", not join_partial_coordinates(two_root_system(), two_roots).proposals))

    origin = (I(Q(-1, 10), Q(1, 10)), I(Q(-1, 10), Q(1, 10)))
    away = (I(1, Q(11, 10)), I(Q(-1, 10), Q(1, 10)))
    disjoint = (
        ExactifierAttempt(1, 1, BINDING, origin, (PartialCoordinateFact(0, origin[0], ZERO.minpoly, ZERO.real_root_ordinal, ZERO.isolator),)),
        ExactifierAttempt(2, 1, BINDING, away, (PartialCoordinateFact(1, away[1], ZERO.minpoly, ZERO.real_root_ordinal, ZERO.isolator),)),
    )
    disjoint_result = join_partial_coordinates(linear_system(), disjoint)
    checks.append(("negative-disjoint-boxes", not disjoint_result.proposals and disjoint_result.work["root_membership_reject_count"] == 1))

    conflict = positive + (
        ExactifierAttempt(12, 8, BINDING, positive[0].root_box, (PartialCoordinateFact(0, positive[0].root_box[0], minpoly=ONE.minpoly),)),
    )
    conflict_result = join_partial_coordinates(system, conflict)
    checks.append(("negative-coordinate-conflict", not conflict_result.proposals and conflict_result.work["conflict_count"] == 1))

    missing_result = join_partial_coordinates(system, positive[:2])
    checks.append(("negative-missing-coordinate", not missing_result.proposals and missing_result.work["missing_coordinate_count"] == 1))

    guard_mismatch = (
        positive[0],
        positive[1],
        replace(positive[2], binding=replace(BINDING, guard_sha256="guard-b")),
    )
    guard_result = join_partial_coordinates(system, guard_mismatch)
    checks.append(("negative-guard-mismatch", not guard_result.proposals and guard_result.work["binding_group_count"] == 2))

    unfinished = (positive[0], positive[1], replace(positive[2], finalized=False))
    checks.append(("negative-unfinalized-partial-artifact", not join_partial_coordinates(system, unfinished).proposals))

    manifest = boundary_manifest()
    checks.append(("authority-boundary", not joined.proposal_authority and not joined.release and not joined.proposals[0].proposal_authority and not joined.proposals[0].release and manifest["sole_final_authority"].startswith("unchanged QQBar")))

    return {
        "schema_version": "geotarget.same-root-partial-coordinate-join-d0/v1",
        "candidate_sha256": hashlib.sha256((HERE / "candidate.py").read_bytes()).hexdigest(),
        "passed": sum(int(ok) for _name, ok in checks),
        "total": len(checks),
        "checks": [{"name": name, "passed": ok} for name, ok in checks],
        "positive_work": dict(joined.work),
        "boundary": manifest,
    }


if __name__ == "__main__":
    print(json.dumps(run(), indent=2, sort_keys=True))
