from __future__ import annotations

from dataclasses import dataclass
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import unittest

import numpy as np


HERE = Path(__file__).resolve().parent
EXPERIMENT = HERE.parent
SHARED = EXPERIMENT / "arms/shared"


def _load(name: str, path: Path):
    specification = importlib.util.spec_from_file_location(name, path)
    if specification is None or specification.loader is None:
        raise ImportError(path)
    module = importlib.util.module_from_spec(specification)
    sys.modules[name] = module
    specification.loader.exec_module(module)
    return module


ADAPTER = _load("test_exp_rank_guard_001_charted_adapter", SHARED / "charted_search_adapter.py")
FULL = _load("test_exp_rank_guard_001_full_worker", SHARED / "full_worker.py")


@dataclass(frozen=True)
class Prefix:
    points: tuple[np.ndarray, ...]
    sources: tuple[str, ...]
    scale_exponents: tuple[int | None, ...]
    literal_scales: tuple[float, ...]
    sha256: str
    activation: dict[str, object]


@dataclass(frozen=True)
class Observation:
    residual: np.ndarray
    finite: bool
    semantics_valid: bool


class RankDeficientCase:
    dimension = 2
    lower = np.array([-1.0, -1.0])
    upper = np.array([1.0, 1.0])

    def __init__(self, *, semantically_valid: bool = True):
        self.callbacks = 0
        self.semantically_valid = semantically_valid

    def evaluate(self, point):
        self.callbacks += 1
        values = np.asarray(point, dtype=float)
        return Observation(
            residual=np.array([values[0], 1.0e-10 * values[1]]),
            finite=True,
            semantics_valid=self.semantically_valid,
        )


def _prefix(count: int = 16) -> Prefix:
    points = tuple(np.zeros(2, dtype=float) for _ in range(count))
    return Prefix(
        points=points,
        sources=tuple(f"baseline-{index}" for index in range(count)),
        scale_exponents=tuple(0 for _ in range(count)),
        literal_scales=tuple(1.0 for _ in range(count)),
        sha256="baseline",
        activation={"baseline": True},
    )


class ProposalOverlayTests(unittest.TestCase):
    def test_overlay_preserves_prefix_and_insurance_slots(self):
        baseline = _prefix()
        case = RankDeficientCase()
        candidate, telemetry = ADAPTER._overlay_prefix(
            case, baseline, callback_cap=512, callbacks_per_start=32
        )

        self.assertEqual(telemetry["rank_guard_overlay_activated"], 1)
        self.assertEqual(case.callbacks, 13)
        self.assertLessEqual(
            case.callbacks, telemetry["rank_guard_overlay_callback_budget"]
        )
        self.assertEqual(telemetry["rank_guard_baseline_minimum_slots"], 12)
        self.assertGreater(telemetry["rank_guard_overlay_replaced_slots"], 0)
        for ordinal in range(12):
            self.assertEqual(
                baseline.points[ordinal].tobytes(), candidate.points[ordinal].tobytes()
            )
        for ordinal in range(len(baseline.points)):
            if ordinal % ADAPTER.INSURANCE_PERIOD == 0:
                self.assertEqual(
                    baseline.points[ordinal].tobytes(),
                    candidate.points[ordinal].tobytes(),
                )
        self.assertTrue(
            all(
                np.all(point > case.lower) and np.all(point < case.upper)
                for point in candidate.points
            )
        )

    def test_semantic_failure_is_fail_closed(self):
        baseline = _prefix()
        candidate, telemetry = ADAPTER._overlay_prefix(
            RankDeficientCase(semantically_valid=False),
            baseline,
            callback_cap=512,
            callbacks_per_start=32,
        )
        self.assertIs(candidate, baseline)
        self.assertEqual(telemetry["rank_guard_overlay_activated"], 0)

    def test_nonfinite_bounds_are_ineligible(self):
        baseline = _prefix()
        case = RankDeficientCase()
        case.upper = np.array([np.inf, 1.0])
        candidate, telemetry = ADAPTER._overlay_prefix(
            case, baseline, callback_cap=512, callbacks_per_start=32
        )
        self.assertIs(candidate, baseline)
        self.assertEqual(case.callbacks, 0)
        self.assertEqual(telemetry["rank_guard_overlay_eligible"], 0)

    def test_diagnostic_never_partially_exceeds_small_quota(self):
        baseline = _prefix()
        case = RankDeficientCase()
        candidate, telemetry = ADAPTER._overlay_prefix(
            case, baseline, callback_cap=128, callbacks_per_start=8
        )
        self.assertIs(candidate, baseline)
        self.assertEqual(case.callbacks, 0)
        self.assertEqual(telemetry["rank_guard_overlay_callback_budget"], 6)


class BindingTests(unittest.TestCase):
    def test_plan_modes_preserve_schema_and_fail_closed_cpqr(self):
        original = {"schema_version": "frozen-plan/v1", "status": "dry"}
        charted = FULL._decorate_plan(
            original, mode=FULL.CHARTED, frozen_final_schema="frozen-result/v1"
        )
        blocked = FULL._decorate_plan(
            original,
            mode=FULL.ADAPTED_CPQR_BLOCKED,
            frozen_final_schema="frozen-result/v1",
        )
        self.assertEqual(charted["schema_version"], "frozen-plan/v1")
        self.assertEqual(charted["final_result_schema"], "frozen-result/v1")
        self.assertTrue(charted["proposal_overlay_active"])
        self.assertFalse(charted["hp_pslq_or_canonical_authority_modified"])
        self.assertFalse(blocked["proposal_overlay_active"])
        self.assertTrue(blocked["adapted_cpqr_fail_closed"])
        self.assertIn("128/256/512", blocked["adapted_cpqr_blocker"])

    def test_common_arm_schema_and_entrypoint_digest(self):
        for directory in (
            EXPERIMENT / "arms/charted-weak-proposal",
            EXPERIMENT / "arms/adapted-cpqr-proposal",
        ):
            manifest = json.loads((directory / "arm.json").read_text())
            self.assertEqual(set(manifest), {
                "id", "base_commit", "entrypoint", "mechanism_hash"
            })
            self.assertEqual(manifest["id"], manifest["id"].lower())
            self.assertEqual(len(manifest["base_commit"]), 40)
            entrypoint = directory / manifest["entrypoint"]
            self.assertEqual(
                hashlib.sha256(entrypoint.read_bytes()).hexdigest(),
                manifest["mechanism_hash"],
            )


if __name__ == "__main__":
    unittest.main()
