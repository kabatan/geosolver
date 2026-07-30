from __future__ import annotations

from dataclasses import replace
import json
import os
from pathlib import Path
import signal
import unittest

from candidate import (
    AMBIGUOUS_FAILURE,
    DIRECT_RELATION,
    LINE_DOMAIN,
    POINT_DOMAIN,
    ExactLine,
    ExactPoint,
    FailClosed,
    ReplayLedger,
    TypedAngle,
    classify_source_relation,
    prove_typed_angle_equality,
    repair_ambiguous_full_turn,
)
from contained_runner import run_contained


P = ExactPoint.of
L = ExactLine.of


def point(u, v, **kwargs):
    return TypedAngle.point(P(*u), P(0, 0), P(*v), **kwargs)


def line(n1, n2, **kwargs):
    return TypedAngle.line(L(*n1), L(*n2), **kwargs)


class ExactTypedAngleTests(unittest.TestCase):
    def setUp(self):
        self.ledger = ReplayLedger()

    def assert_equal(self, left, right):
        result = prove_typed_angle_equality(left, right, self.ledger)
        self.assertTrue(result.equal, result)
        self.assertTrue(result.authority_pass, result)

    def assert_reject(self, left, right, ledger=None):
        result = prove_typed_angle_equality(left, right, ledger or self.ledger)
        self.assertFalse(result.authority_pass, result)

    def test_positive_point_acute(self):
        self.assert_equal(point((1, 0), (3, 4)), point((0, 2), (-8, 6)))

    def test_positive_point_obtuse(self):
        self.assert_equal(point((1, 0), (-3, 4)), point((0, 2), (-8, -6)))

    def test_positive_line_acute(self):
        self.assert_equal(line((1, 0), (3, 4)), line((0, 1), (4, 3)))

    def test_positive_collinear_zero_and_pi(self):
        self.assert_equal(point((1, 0), (2, 0)), point((3, 0), (7, 0)))
        self.assert_equal(point((1, 0), (-2, 0)), point((3, 0), (-7, 0)))

    def test_supplementary_and_zero_vs_pi_are_unequal(self):
        self.assert_reject(point((1, 0), (3, 4)), point((1, 0), (-3, 4)))
        self.assert_reject(point((1, 0), (2, 0)), point((1, 0), (-2, 0)))

    def test_zero_vector_fails_closed(self):
        self.assert_reject(point((0, 0), (3, 4)), point((1, 0), (3, 4)))

    def test_approximate_float_fails_closed(self):
        with self.assertRaises(FailClosed):
            point((1.0, 0), (3, 4))

    def test_mixed_wrong_unit_and_unknown_domain_fail_closed(self):
        self.assert_reject(point((1, 0), (3, 4)), line((1, 0), (3, 4)))
        self.assert_reject(point((1, 0), (3, 4), unit="degree"), point((1, 0), (3, 4), unit="degree"))
        self.assert_reject(
            point((1, 0), (3, 4), domain="FULL_CIRCLE_[0,2PI]"),
            point((1, 0), (3, 4), domain="FULL_CIRCLE_[0,2PI]"),
        )

    def test_oriented_full_circle_and_full_turn_relation_fail_closed(self):
        bad = TypedAngle("full_circle", (), "radian", "FULL_CIRCLE_[0,2PI]")
        self.assert_reject(bad, bad)
        ledger = replace(self.ledger, relation_shape="ANGLE_PLUS_FULL_TURN_EQUALITY")
        self.assert_reject(point((1, 0), (3, 4)), point((1, 0), (3, 4)), ledger)

    def test_orientation_reversal_is_not_silently_typed_unsigned(self):
        bad = TypedAngle("oriented", (), "radian", "ORIENTED_[-PI,PI]")
        self.assert_reject(bad, bad)

    def test_incomplete_replay_and_qreflect_fail_closed(self):
        angle = point((1, 0), (3, 4))
        self.assert_reject(angle, angle, replace(self.ledger, raw_target_exact=False))
        self.assert_reject(angle, angle, replace(self.ledger, qreflect_used=True))
        self.assert_reject(angle, angle, replace(self.ledger, raw_target_exact="truthy"))

    def test_metamporphic_swap_scale_rotation_reflection(self):
        base = point((1, 0), (3, 4))
        transformed = [
            point((0, 2), (-8, 6)),       # independent positive scales + rotation
            point((-1, 0), (-3, 4)),      # reflection in y-axis
            point((3, 4), (1, 0)),        # ray permutation, unsigned angle
        ]
        for angle in transformed:
            self.assert_equal(base, angle)
            self.assert_equal(angle, base)  # equality-side permutation

    def test_candidate_splice_only_repairs_exact_failure(self):
        angle = point((1, 0), (3, 4))
        repaired = repair_ambiguous_full_turn({"failure": AMBIGUOUS_FAILURE}, angle, angle, self.ledger)
        self.assertTrue(repaired["authority_pass"])
        untouched = repair_ambiguous_full_turn({"failure": "some other failure"}, angle, angle, self.ledger)
        self.assertFalse(untouched["candidate_activation"])

    def test_static_activation_exact_shape_only(self):
        point_node = {
            "op": "Equal",
            "left": {"op": "Angle", "args": ["A", "B", "C"], "unit": "radian", "domain": POINT_DOMAIN},
            "right": {"op": "Angle", "args": ["D", "E", "F"], "unit": "radian", "domain": POINT_DOMAIN},
        }
        self.assertTrue(classify_source_relation(point_node))
        wrong = json.loads(json.dumps(point_node))
        wrong["right"]["unit"] = "degree"
        self.assertFalse(classify_source_relation(wrong))
        wrapped = json.loads(json.dumps(point_node))
        wrapped["left"] = {"op": "Add", "args": [wrapped["left"], "2*pi"]}
        self.assertFalse(classify_source_relation(wrapped))

    @unittest.skipUnless(os.sched_getaffinity(0) == {15}, "containment D0 requires CPU15")
    def test_containment(self):
        request = {
            "left": {"kind": "point_unsigned", "args": [["1", "0"], ["0", "0"], ["3", "4"]], "unit": "radian", "domain": POINT_DOMAIN},
            "right": {"kind": "point_unsigned", "args": [["0", "2"], ["0", "0"], ["-8", "6"]], "unit": "radian", "domain": POINT_DOMAIN},
        }
        output = run_contained(request)
        self.assertTrue(output["result"]["authority_pass"])
        self.assertEqual(output["containment"]["affinity"], [15])
        self.assertTrue(output["containment"]["same_process_group"])
        self.assertEqual(output["containment"]["pdeathsig"], signal.SIGKILL)
        self.assertFalse(output["containment"]["start_new_session"])
        self.assertFalse(output["containment"]["timed_out"])
        timeout_request = {**request, "test_sleep_ms": 200}
        timed_out = run_contained(timeout_request, timeout_seconds=0.02)
        self.assertTrue(timed_out["timed_out"])
        self.assertFalse(timed_out["authority_pass"])


if __name__ == "__main__":
    unittest.main()
