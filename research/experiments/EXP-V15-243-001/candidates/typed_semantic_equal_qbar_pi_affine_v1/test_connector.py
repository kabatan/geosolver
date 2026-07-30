from __future__ import annotations

import ctypes
import json
import os
import shutil
import signal
import subprocess
import sys
from types import SimpleNamespace
import unittest
from unittest import mock

import current_exact_candidate as baseline_candidate
import typed_replay_connector as connector


def eligible_job():
    return {
        "nodes": [
            {"op": "rational", "value": "1/1"},
            {"op": "rational", "value": "1/1"},
            {"op": "sub", "args": [0, 1]},
        ],
        "relation_roots": [2],
        "typed_semantic_eligible_relation_indices": {
            "value is not exact rational": [0],
            "scalar is not an exact angle expression": [],
        },
    }


class ConnectorTests(unittest.TestCase):
    def test_worker_patch_is_closed_and_source_only(self):
        source = connector.patched_worker_source(baseline_candidate)
        self.assertIn("struct QPiAffine", source)
        self.assertIn("qx_typed_semantic_equal", source)
        self.assertIn('operation == "typed_equal"', source)
        self.assertIn('job["typed_semantic_source_only"] == true', source)
        self.assertIn("unique canonical embedding Q -> Qbar", source)
        self.assertIn("nonlinear pi product is outside affine authority", source)
        self.assertNotIn("typed_semantic_less", source)

    def test_baseline_first_budget_and_side_failure_preserve_object_identity(self):
        calls = []
        baseline = {
            "status": "EXACT_REPLAY_REJECTED",
            "error": "value is not exact rational",
        }

        def baseline_run(job, *, timeout_seconds):
            calls.append(timeout_seconds)
            return baseline

        fake = SimpleNamespace(_run_qqbar=baseline_run)
        with mock.patch.object(
            connector,
            "_run_patched",
            return_value={"status": "EXACT_REPLAY_REJECTED"},
        ) as side:
            connector.install(fake)
            result = fake._run_qqbar(eligible_job(), timeout_seconds=20.0)
        self.assertIs(result, baseline)
        self.assertEqual(calls, [15.0])
        self.assertLessEqual(side.call_args.kwargs["timeout_seconds"], 5.0)

    def test_ineligible_and_unrelated_failures_never_run_side(self):
        terminals = [
            {"status": "EXACT_REPLAY_REJECTED", "error": "some other failure"},
            {"status": "EXACT_REPLAY_REJECTED", "error": "value is not exact rational"},
        ]
        for index, terminal in enumerate(terminals):
            fake = SimpleNamespace(_run_qqbar=lambda job, *, timeout_seconds, t=terminal: t)
            job = eligible_job()
            if index == 1:
                job["typed_semantic_eligible_relation_indices"]["value is not exact rational"] = []
            with mock.patch.object(connector, "_run_patched") as side:
                connector.install(fake)
                result = fake._run_qqbar(job, timeout_seconds=20.0)
            self.assertIs(result, terminal)
            side.assert_not_called()

    def test_side_success_keeps_all_existing_replay_fields(self):
        baseline = {
            "status": "EXACT_REPLAY_REJECTED",
            "error": "value is not exact rational",
        }
        side_terminal = {
            "status": "EXACT_REPLAY_ACCEPTED",
            "source_raw_answer_exact": True,
            "target_link_exact": True,
            "root_ordinal_attestation_complete": True,
        }
        fake = SimpleNamespace(_run_qqbar=lambda job, *, timeout_seconds: baseline)
        with mock.patch.object(connector, "_run_patched", return_value=dict(side_terminal)):
            connector.install(fake)
            result = fake._run_qqbar(eligible_job(), timeout_seconds=20.0)
        for key, value in side_terminal.items():
            self.assertEqual(result[key], value)
        self.assertTrue(result["baseline_exact_replay_ran_first"])
        self.assertEqual(result["baseline_budget_fraction"], 0.75)
        self.assertEqual(result["typed_side_budget_fraction_maximum"], 0.25)

    def test_child_setup_same_group_affinity_and_parent_death_signal(self):
        parent_group = os.getpgid(0)
        script = r'''
import ctypes, json, os
value = ctypes.c_int(0)
ctypes.CDLL(None).prctl(2, ctypes.byref(value), 0, 0, 0)
print(json.dumps({"affinity": sorted(os.sched_getaffinity(0)), "pgid": os.getpgid(0), "pdeathsig": value.value}))
'''
        completed = subprocess.run(
            [sys.executable, "-c", script],
            check=True,
            capture_output=True,
            text=True,
            timeout=3.0,
            start_new_session=False,
            preexec_fn=connector._child_setup,
        )
        result = json.loads(completed.stdout)
        self.assertEqual(result["affinity"], [14])
        self.assertEqual(result["pgid"], parent_group)
        self.assertEqual(result["pdeathsig"], signal.SIGKILL)

    @unittest.skipUnless(shutil.which("julia"), "Julia is required for executable QQBar D0")
    def test_actual_qbar_affine_side_replay(self):
        descriptor = {
            "coefficients_high_to_low": ["1", "0", "-2"],
            "isolating_interval": {
                "left": "1",
                "right": "2",
                "multiplicity": 1,
                "real_root_index": 1,
            },
        }
        document = {
            "task": "solve",
            "variables": {"names": ["x"]},
            "construction": [],
            "constraints": [{"def": "pi*x", "value": "x*pi"}],
            "guards": [],
            "bounds": None,
            "answer": "x",
            "post_process": None,
        }
        prepared, _records = baseline_candidate.prepare_document(document)
        job = baseline_candidate.DAG.compile_document(
            prepared,
            coordinate_descriptors=[descriptor],
            target_descriptor=descriptor,
        )
        job["typed_semantic_eligible_relation_indices"] = {
            "value is not exact rational": [0],
            "scalar is not an exact angle expression": [],
        }
        baseline_candidate._normalize_exact_guard_calls(job)
        baseline = baseline_candidate._run_qqbar(job, timeout_seconds=12.0)
        self.assertEqual(baseline["status"], "EXACT_REPLAY_REJECTED")
        self.assertIn("value is not exact rational", baseline["error"])
        annotated = connector._annotated_job(
            baseline_candidate,
            job,
            "value is not exact rational",
        )
        self.assertIsNotNone(annotated)
        side = connector._run_patched(
            baseline_candidate,
            annotated,
            timeout_seconds=12.0,
        )
        self.assertEqual(side["status"], "EXACT_REPLAY_ACCEPTED")
        self.assertTrue(side["source_raw_answer_exact"])
        self.assertTrue(side["target_link_exact"])


if __name__ == "__main__":
    unittest.main()
