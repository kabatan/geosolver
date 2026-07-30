from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
from types import SimpleNamespace
import unittest

from leftover_overlay import baseline_waves_complete, install_leftover_only
import worker_v2


HERE = Path(__file__).resolve().parent
PYTHON = Path("/home/kabatan/work/solver-experiment-runtime/solver/python/.venv/bin/python")


def statistics(complete: bool):
    return {
        "all_discovered_primaries_served": complete,
        "primary_wave_complete": complete,
        "alternate_wave_complete": complete,
        "restoration_wave_complete": complete,
        "primary_deferred_unknown_count": 0 if complete else 1,
        "deadline_backlog_unexamined_count": 0,
    }


def fake_champion(service_result, events):
    def fresh(document, endpoints, *, hard_deadline):
        events.append(("fresh", endpoints, hard_deadline))
        return endpoints

    def service(**kwargs):
        events.append(("service", kwargs["candidates"]))
        return service_result

    base = SimpleNamespace(
        _fresh_replay_candidates=fresh,
        _service_candidates=service,
        _plan=lambda **kwargs: dict(kwargs),
        _run_hp_candidate=lambda: None,
        _run_restoration_candidate=lambda: None,
        _authority_descriptor=lambda: None,
        _descriptor_key=lambda: None,
        FINALIZE_RESERVE_SECONDS=3.0,
        MIN_HP_ATTEMPT_SECONDS=0.25,
    )
    return SimpleNamespace(BASE=base)


def payload(document):
    return json.dumps(document, sort_keys=True, separators=(",", ":")).encode() + b"\n"


def cli(source, output, content):
    return [
        "--source", str(source),
        "--source-sha256", hashlib.sha256(content).hexdigest(),
        "--total-seconds", "15",
        "--search-seconds", "5",
        "--starts", "16",
        "--callbacks-per-start", "32",
        "--aggregate-callback-cap", "512",
        "--seed", "0",
        "--cpu", "0",
        "--output", str(output),
    ]


class LeftoverOverlayTests(unittest.TestCase):
    def test_incomplete_baseline_returns_original_result_object_bitwise(self):
        events = []
        baseline_result = ([{"attempt": "baseline"}], {"b": 1}, statistics(False))
        champion = fake_champion(baseline_result, events)
        factory_calls = []
        audit = install_leftover_only(
            champion,
            proposal_factory=lambda *_args: factory_calls.append(True),
            mechanism_hash="test",
        )
        endpoints = ({"point": [0.0]},)
        candidates = champion.BASE._fresh_replay_candidates(
            {"variables": {"names": ["x"]}}, endpoints, hard_deadline=time.monotonic() + 3
        )
        returned = champion.BASE._service_candidates(
            candidates=candidates, hard_deadline=time.monotonic() + 100
        )
        self.assertIs(returned, baseline_result)
        self.assertEqual(factory_calls, [])
        self.assertEqual(audit()["side_skip_reason"], "BASELINE_WAVES_INCOMPLETE")
        self.assertEqual([event[0] for event in events], ["fresh", "service"])

    def test_no_leftover_returns_original_result_object_bitwise(self):
        events = []
        baseline_result = ([{"attempt": "baseline"}], {"b": 1}, statistics(True))
        champion = fake_champion(baseline_result, events)
        factory_calls = []
        audit = install_leftover_only(
            champion,
            proposal_factory=lambda *_args: factory_calls.append(True),
            mechanism_hash="test",
        )
        endpoints = ({"point": [0.0]},)
        candidates = champion.BASE._fresh_replay_candidates(
            {"variables": {"names": ["x"]}}, endpoints, hard_deadline=time.monotonic()
        )
        returned = champion.BASE._service_candidates(
            candidates=candidates, hard_deadline=time.monotonic()
        )
        self.assertIs(returned, baseline_result)
        self.assertEqual(factory_calls, [])
        self.assertEqual(
            audit()["side_skip_reason"], "NO_LEFTOVER_GENERATION_AND_HP_SLOT"
        )

    def test_side_failure_cannot_replace_completed_baseline_result(self):
        events = []
        baseline_result = ([{"attempt": "baseline"}], {"b": 1}, statistics(True))
        champion = fake_champion(baseline_result, events)

        def broken_factory(*_args):
            raise RuntimeError("generated side failure")

        audit = install_leftover_only(
            champion,
            proposal_factory=broken_factory,
            mechanism_hash="test",
        )
        endpoints = ({"point": [0.0]},)
        candidates = champion.BASE._fresh_replay_candidates(
            {"variables": {"names": ["x"]}}, endpoints, hard_deadline=time.monotonic() + 3
        )
        returned = champion.BASE._service_candidates(
            candidates=candidates, hard_deadline=time.monotonic() + 100
        )
        self.assertIs(returned, baseline_result)
        self.assertEqual(
            audit()["side_skip_reason"], "PROPOSAL_FACTORY_FAILED:RuntimeError"
        )

    def test_completion_gate_requires_every_wave_and_backlog(self):
        self.assertTrue(baseline_waves_complete(statistics(True)))
        for field in (
            "all_discovered_primaries_served",
            "primary_wave_complete",
            "alternate_wave_complete",
            "restoration_wave_complete",
        ):
            changed = statistics(True)
            changed[field] = False
            self.assertFalse(baseline_waves_complete(changed), field)
        changed = statistics(True)
        changed["deadline_backlog_unexamined_count"] = 1
        self.assertFalse(baseline_waves_complete(changed))

    def test_generated_trace_smoke_is_exact_and_baseline_first(self):
        completed = subprocess.run(
            [str(PYTHON), str(HERE / "run_leftover_trace_smoke.py")],
            cwd=HERE,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
            timeout=10,
        )
        observed = json.loads(completed.stdout)
        expected = json.loads((HERE / "leftover-trace-smoke.json").read_text())
        self.assertEqual(observed, expected)
        self.assertEqual(
            observed["events"],
            [
                "baseline_fresh",
                "baseline_service_complete",
                "side_proposal_generation",
                "side_fresh",
                "side_service",
            ],
        )

    def test_v2_common_arm_hash_and_applicable_dry_plan(self):
        arm = json.loads((HERE / "arm-v2.json").read_text())
        self.assertEqual(
            hashlib.sha256((HERE / "worker_v2.py").read_bytes()).hexdigest(),
            arm["mechanism_hash"],
        )
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
        content = payload(document)
        with tempfile.TemporaryDirectory(prefix="exp-struct-poly-v2-dry-") as raw:
            root = Path(raw)
            source = root / "source.json"
            source.write_bytes(content)
            output = root / "output"
            subprocess.run(
                [str(PYTHON), str(HERE / "worker_v2.py"), *cli(source, output, content)],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=True,
                timeout=10,
            )
            plan = json.loads((output / "PLAN.json").read_text())
            overlay = plan["exp_struct_poly_001_v2"]
            self.assertEqual(overlay["mode"], "LEFTOVER_ONLY_AFTER_IDENTICAL_BASELINE_WAVES")
            self.assertTrue(overlay["baseline_fresh_replay_first"])
            self.assertEqual(overlay["side_proposals_in_baseline_reservoir"], 0)
            self.assertTrue(overlay["baseline_completion_required"])

    def test_v2_nonapplicable_dry_is_bitwise_frozen_passthrough(self):
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
        content = payload(document)
        with tempfile.TemporaryDirectory(prefix="exp-struct-poly-v2-nonapp-") as raw:
            root = Path(raw)
            source = root / "source.json"
            source.write_bytes(content)
            output = root / "shared"
            args = cli(source, output, content)
            direct = subprocess.run(
                [str(PYTHON), str(worker_v2.V1.FROZEN_WORKER), *args],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=True,
                timeout=10,
            )
            plan_bytes = (output / "PLAN.json").read_bytes()
            shutil.rmtree(output)
            candidate = subprocess.run(
                [str(PYTHON), str(HERE / "worker_v2.py"), *args],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=True,
                timeout=10,
            )
            self.assertEqual(candidate.stdout, direct.stdout)
            self.assertEqual(candidate.stderr, direct.stderr)
            self.assertEqual((output / "PLAN.json").read_bytes(), plan_bytes)


if __name__ == "__main__":
    unittest.main()
