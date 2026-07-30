from __future__ import annotations

import os
from types import SimpleNamespace
import unittest
from unittest import mock

import current_exact_candidate as base
import scanner
import sector_angle_connector as connector


def descriptor(coefficients, left, right, index):
    return {
        "coefficients_high_to_low": coefficients,
        "isolating_interval": {
            "left": left,
            "right": right,
            "multiplicity": 1,
            "real_root_index": index,
        },
    }


ZERO = descriptor(["1", "0"], "0", "0", 0)
ONE = descriptor(["1", "-1"], "1", "1", 0)
NEG_ONE = descriptor(["1", "1"], "-1", "-1", 0)
HALF = descriptor(["2", "-1"], "1/2", "1/2", 0)
NEG_HALF = descriptor(["2", "1"], "-1/2", "-1/2", 0)
SQRT2_HALF = descriptor(["2", "0", "-1"], "0", "1", 1)
SQRT3_HALF = descriptor(["4", "0", "-3"], "0", "1", 1)
NEG_SQRT3_HALF = descriptor(["4", "0", "-3"], "-1", "0", 0)


ANGLE_COORDINATES = {
    "zero": (ONE, ZERO),
    "pi_6": (SQRT3_HALF, HALF),
    "pi_4": (SQRT2_HALF, SQRT2_HALF),
    "pi_3": (HALF, SQRT3_HALF),
    "pi_2": (ZERO, ONE),
    "two_pi_3": (NEG_HALF, SQRT3_HALF),
    "five_pi_6": (NEG_SQRT3_HALF, HALF),
    "pi": (NEG_ONE, ZERO),
}


def relation_text(factor, points, *, commute=False):
    angle = f"Angle({','.join(points)})"
    if factor == 1:
        return angle
    return f"{angle}*{factor}" if commute else f"{factor}*{angle}"


def source_document(first_factor, second_factor, *, commute_left=False, commute_right=False):
    names = [
        "ax", "ay", "bx", "by", "cx", "cy",
        "dx", "dy", "ex", "ey", "fx", "fy",
    ]
    return {
        "task": "solve",
        "variables": {"names": names},
        "construction": [
            {"name": name, "expr": f"Point({x},{y})"}
            for name, x, y in (
                ("A", "ax", "ay"), ("B", "bx", "by"),
                ("C", "cx", "cy"), ("D", "dx", "dy"),
                ("E", "ex", "ey"), ("F", "fx", "fy"),
            )
        ],
        "constraints": [
            {
                "def": relation_text(first_factor, ("A", "B", "C"), commute=commute_left),
                "value": relation_text(second_factor, ("D", "E", "F"), commute=commute_right),
            }
        ],
        "guards": [],
        "bounds": None,
        "answer": "ax",
        "post_process": None,
    }


def replay_job(first_factor, second_factor, first_angle, second_angle, **source_options):
    document = source_document(first_factor, second_factor, **source_options)
    first_cosine, first_sine = ANGLE_COORDINATES[first_angle]
    second_cosine, second_sine = ANGLE_COORDINATES[second_angle]
    coordinates = [
        ONE, ZERO, ZERO, ZERO, first_cosine, first_sine,
        ONE, ZERO, ZERO, ZERO, second_cosine, second_sine,
    ]
    prepared, _records = base.prepare_document(document)
    job = base.DAG.compile_document(
        prepared,
        coordinate_descriptors=coordinates,
        target_descriptor=ONE,
    )
    job["typed_semantic_eligible_relation_indices"] = {
        "value is not exact rational": [],
        connector.ANGLE_FAILURE: scanner.eligible_relation_indices(
            document, connector.ANGLE_FAILURE
        ),
    }
    job["sector_angle_relation_specs"] = {
        str(index): list(spec)
        for index, spec in scanner.sector_relation_specs(document).items()
    }
    base._normalize_exact_guard_calls(job)
    return document, job


class SectorScannerTests(unittest.TestCase):
    def test_only_closed_positive_integer_relations_one_through_three(self):
        document = source_document(1, 2)
        self.assertEqual(scanner.eligible_relation_indices(document, connector.ANGLE_FAILURE), [0])
        self.assertEqual(scanner.sector_relation_specs(document), {0: (1, 2)})
        for left, right in (
            ("-2*Angle(A,B,C)", "Angle(D,E,F)"),
            ("4*Angle(A,B,C)", "Angle(D,E,F)"),
            ("1.5*Angle(A,B,C)", "Angle(D,E,F)"),
            ("2*(Angle(A,B,C)+Angle(A,B,C))", "Angle(D,E,F)"),
            ("2*pi", "Angle(D,E,F)"),
            ("2*Angle(A,B,C)", "Angle(Line(A,B),Line(D,E))"),
        ):
            rejected = source_document(1, 1)
            rejected["constraints"] = [{"def": left, "value": right}]
            self.assertEqual(
                scanner.eligible_relation_indices(rejected, connector.ANGLE_FAILURE),
                [],
            )

    def test_permutation_swap_and_commuted_product_preserve_eligibility(self):
        first = source_document(1, 3, commute_right=True)
        second = source_document(3, 1, commute_left=True)
        self.assertEqual(scanner.sector_relation_specs(first), {0: (1, 3)})
        self.assertEqual(scanner.sector_relation_specs(second), {0: (3, 1)})


class SectorConnectorTests(unittest.TestCase):
    def test_single_campaign_cpu_only(self):
        self.assertEqual(sorted(os.sched_getaffinity(0)), [14])

    def test_patch_has_exact_unit_sector_and_no_general_angle_arithmetic(self):
        source = connector.patched_worker_source(base)
        self.assertIn("struct SectorAngleScale", source)
        self.assertIn("qx_unit_power", source)
        self.assertIn("qx_sector_index", source)
        self.assertIn("angle lies on a sector boundary or tie", source)
        self.assertIn("scaled-angle equality has nonzero or ambiguous full-turn lift", source)
        self.assertNotIn("sector_angle_less", source)

    def test_baseline_first_and_side_failure_return_identity(self):
        baseline = {
            "status": "EXACT_REPLAY_REJECTED",
            "error": "angle equality has ambiguous full-turn lift",
        }
        _document, job = replay_job(1, 2, "pi_2", "pi_4")
        calls = []

        def baseline_run(value, *, timeout_seconds):
            calls.append(timeout_seconds)
            return baseline

        fake = SimpleNamespace(_run_qqbar=baseline_run)
        with mock.patch.object(connector, "_run_patched", side_effect=RuntimeError("closed")) as side:
            connector.install(fake)
            result = fake._run_qqbar(job, timeout_seconds=20.0)
        self.assertIs(result, baseline)
        self.assertEqual(calls, [15.0])
        self.assertLessEqual(side.call_args.kwargs["timeout_seconds"], 5.0)

    def test_actual_positive_relations_and_metamorphic_forms(self):
        examples = (
            (1, 2, "pi_2", "pi_4", {}),
            (2, 1, "pi_4", "pi_2", {"commute_left": True}),
            (1, 3, "pi_2", "pi_6", {"commute_right": True}),
            (3, 1, "pi_6", "pi_2", {}),
        )
        for first_factor, second_factor, first_angle, second_angle, options in examples:
            with self.subTest(pair=(first_factor, second_factor), options=options):
                _document, job = replay_job(
                    first_factor, second_factor, first_angle, second_angle, **options
                )
                baseline = base._run_qqbar(job, timeout_seconds=12.0)
                self.assertEqual(baseline["status"], "EXACT_REPLAY_REJECTED")
                annotated = connector._annotated_job(base, job, connector.ANGLE_FAILURE)
                self.assertIsNotNone(annotated)
                side = connector._run_patched(base, annotated, timeout_seconds=12.0)
                self.assertEqual(side["status"], "EXACT_REPLAY_ACCEPTED")
                self.assertTrue(side["source_raw_answer_exact"])
                self.assertTrue(side["target_link_exact"])

    def test_alias_boundary_supplement_and_degenerate_reject(self):
        examples = (
            (3, 1, "five_pi_6", "pi_2", "nonzero full-turn alias"),
            (2, 1, "pi_2", "pi", "sector boundary"),
            (1, 1, "pi_3", "two_pi_3", "supplement"),
            (1, 1, "zero", "pi_2", "degenerate endpoint angle"),
        )
        for first_factor, second_factor, first_angle, second_angle, label in examples:
            with self.subTest(label=label):
                _document, job = replay_job(
                    first_factor, second_factor, first_angle, second_angle
                )
                annotated = connector._annotated_job(base, job, connector.ANGLE_FAILURE)
                self.assertIsNotNone(annotated)
                side = connector._run_patched(base, annotated, timeout_seconds=12.0)
                self.assertEqual(side["status"], "EXACT_REPLAY_REJECTED")


if __name__ == "__main__":
    unittest.main()
