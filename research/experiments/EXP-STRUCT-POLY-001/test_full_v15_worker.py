from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

import worker


HERE = Path(__file__).resolve().parent
PYTHON = Path("/home/kabatan/work/solver-experiment-runtime/solver/python/.venv/bin/python")


def encoded(document):
    return (
        json.dumps(document, sort_keys=True, separators=(",", ":")).encode()
        + b"\n"
    )


def arguments(source: Path, output: Path, payload: bytes):
    return [
        "--source",
        str(source),
        "--source-sha256",
        hashlib.sha256(payload).hexdigest(),
        "--total-seconds",
        "15",
        "--search-seconds",
        "5",
        "--starts",
        "16",
        "--callbacks-per-start",
        "32",
        "--aggregate-callback-cap",
        "512",
        "--seed",
        "0",
        "--cpu",
        "0",
        "--output",
        str(output),
    ]


class FullV15WorkerTests(unittest.TestCase):
    def test_common_arm_contract_hashes_entrypoint(self):
        arm = json.loads((HERE / "arm.json").read_text())
        self.assertEqual(set(arm), {"id", "base_commit", "entrypoint", "mechanism_hash"})
        self.assertEqual(arm["entrypoint"], "worker.py")
        self.assertEqual(
            hashlib.sha256((HERE / "worker.py").read_bytes()).hexdigest(),
            arm["mechanism_hash"],
        )

    def test_generated_actual_frozen_replay_smoke_is_exactly_reproducible(self):
        completed = subprocess.run(
            [str(PYTHON), str(HERE / "run_full_v15_activation_smoke.py")],
            cwd=HERE,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
            timeout=10,
        )
        self.assertEqual(
            json.loads(completed.stdout),
            json.loads((HERE / "full-v15-activation-smoke.json").read_text()),
        )

    def test_nonapplicable_dry_run_is_bitwise_frozen_passthrough(self):
        document = {
            "task": "solve",
            "variables": {"names": ["x", "y"]},
            "construction": [],
            "constraints": [
                {"def": "x + y", "value": 1},
                {"def": "x - y", "value": 0},
            ],
            "guards": [],
        }
        payload = encoded(document)
        with tempfile.TemporaryDirectory(prefix="exp-struct-poly-nonapp-") as raw:
            root = Path(raw)
            source = root / "source.json"
            source.write_bytes(payload)
            output = root / "shared-output"
            args = arguments(source, output, payload)
            direct = subprocess.run(
                [str(PYTHON), str(worker.FROZEN_WORKER), *args],
                text=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=True,
                timeout=10,
            )
            plan = (output / "PLAN.json").read_bytes()
            shutil.rmtree(output)
            candidate = subprocess.run(
                [str(PYTHON), str(HERE / "worker.py"), *args],
                text=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=True,
                timeout=10,
            )
            self.assertEqual(candidate.stdout, direct.stdout)
            self.assertEqual(candidate.stderr, direct.stderr)
            self.assertEqual((output / "PLAN.json").read_bytes(), plan)
            self.assertFalse((output / "EXP-STRUCT-POLY-001-TELEMETRY.json").exists())

    def test_applicable_dry_plan_seals_proposal_only_authority(self):
        document = {
            "task": "solve",
            "variables": {"names": ["x", "y", "z", "w"]},
            "construction": [],
            "constraints": [
                {"def": "x**2", "value": 1},
                {"def": "y", "value": "x"},
                {"def": "sin(z)", "value": 0},
                {"def": "w", "value": "z"},
            ],
            "guards": [],
        }
        payload = encoded(document)
        with tempfile.TemporaryDirectory(prefix="exp-struct-poly-app-") as raw:
            root = Path(raw)
            source = root / "source.json"
            source.write_bytes(payload)
            output = root / "output"
            completed = subprocess.run(
                [
                    str(PYTHON),
                    str(HERE / "worker.py"),
                    *arguments(source, output, payload),
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=True,
                timeout=10,
            )
            self.assertEqual(completed.stderr, b"")
            plan = json.loads((output / "PLAN.json").read_text())
            overlay = plan["exp_struct_poly_001"]
            self.assertTrue(overlay["baseline_search_starts_unchanged"])
            self.assertTrue(overlay["baseline_callback_quota_unchanged"])
            self.assertTrue(overlay["baseline_endpoints_before_proposals"])
            self.assertEqual(overlay["maximum_side_seconds"], 2.0)
            self.assertEqual(overlay["maximum_symbolic_blocks"], 4)
            self.assertEqual(overlay["maximum_cartesian_proposals"], 32)
            self.assertFalse(overlay["local_candidate_authority"])
            self.assertEqual(plan["starts"], 16)
            self.assertEqual(plan["callbacks_per_start"], 32)
            telemetry = json.loads(
                (output / "EXP-STRUCT-POLY-001-TELEMETRY.json").read_text()
            )
            self.assertFalse(telemetry["baseline_search_or_quota_modified"])
            self.assertFalse(telemetry["local_candidate_authority"])


if __name__ == "__main__":
    unittest.main()
