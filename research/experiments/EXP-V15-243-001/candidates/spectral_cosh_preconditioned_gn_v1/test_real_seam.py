from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np

import integrated_worker
from real_seam_patch import transform_augmented_residual


def test_lift_matches_transformed_normal_rhs_and_scale() -> None:
    J = np.array([[5.0, 0.2], [0.0, 1.0], [2.0, -0.5]])
    r = np.array([12.0, -1.0, 5.0])
    transformed = transform_augmented_residual(J, r, 1e-3)
    assert transformed.activated
    assert transformed.direction_change > 1e-5
    scaled = transform_augmented_residual(3.0 * J, 3.0 * r, 9e-3)
    assert scaled.activated
    np.testing.assert_allclose(
        scaled.residual, 3.0 * transformed.residual, rtol=2e-12, atol=2e-12
    )


def test_rank_and_ambiguous_frame_fail_closed() -> None:
    rank = transform_augmented_residual(
        np.array([[1.0, 0.0], [0.0, 0.0]]), np.array([2.0, 0.0]), 1e-16
    )
    assert not rank.activated
    repeated = transform_augmented_residual(np.eye(2), np.array([2.0, 3.0]), 1e-3)
    assert not repeated.activated
    assert repeated.reason == "eigenframe"


def test_real_candidate_and_quarter_lane_adapter_load() -> None:
    import real_adapter
    import real_candidate

    assert real_candidate.REFERENCE_NAME == real_adapter.CANDIDATE
    manifest = real_adapter.configuration_manifest()
    assert manifest["baseline_minimum_share"] == 0.75
    assert manifest["case_family_truth_target_or_outcome_routing"] is False


def test_smooth_source_scan_repairs_thin_ad_capability_mismatch() -> None:
    import real_candidate

    class SmoothUnsupported:
        construction = (("q", "Distance(P, Q)"),)
        constraints = (("q*q", "radius*radius"),)

        def relation_rows(self, _start):
            return (None,)

    class NonsmoothUnsupported:
        construction = ()
        constraints = (("abs(x)", "1"),)

        def relation_rows(self, _start):
            return (None,)

    assert real_candidate._source_smooth_at_start(SmoothUnsupported(), [0.0])
    assert not real_candidate._source_smooth_at_start(NonsmoothUnsupported(), [0.0])


def test_current_campaign_full_binding_changes_only_search_executable(
    tmp_path: Path,
) -> None:
    frozen_root = Path("/home/kabatan/work/solver-experiment-runtime/solver")
    control = integrated_worker.configure(frozen_root=frozen_root)
    base = control.CHAMPION.BASE
    assert base.SEARCH_WORKER == Path(integrated_worker.__file__).resolve()
    assert base.SEARCH_ADAPTER == integrated_worker.CURRENT_SEARCH_ADAPTER
    assert base.SEARCH_CANDIDATE == integrated_worker.CURRENT_SEARCH_CANDIDATE
    assert base.SEARCH_ARM == "progressive_adaptive_hybrid_64_600"
    assert base.HP_BRIDGE == (
        frozen_root / "research/experiments/EXP-V15-243-001/candidates/"
        "point_on_circle_periodic_semantics/approved_hp_bridge_v5.py"
    )
    source = tmp_path / "generated-source-only.json"
    source_payload = json.dumps({"variables": {"names": ["x"]}}).encode()
    source.write_bytes(source_payload)
    plan = base._plan(
        source=source,
        source_sha256=hashlib.sha256(source_payload).hexdigest(),
        total_seconds=10.0,
        search_seconds=4.0,
        starts=8,
        callbacks_per_start=100,
        aggregate_callback_cap=800,
        seed=0,
        cpu=31,
        output=tmp_path / "output",
    )
    assert plan["spectral_cosh_current_campaign"] is True
    assert plan["spectral_cosh_source_guard_replay_deadline_changed"] is False
    assert plan["spectral_cosh_hp_or_final_authority_changed"] is False
    assert plan["truth_case_family_target_or_previous_outcome_routing"] is False


def test_current_campaign_arm_binds_thin_worker() -> None:
    here = Path(__file__).resolve().parent
    arm = json.loads((here / "arm.json").read_text())
    worker = here / arm["entrypoint"]
    assert arm["id"] == "spectral-cosh-current-campaign-v1"
    assert hashlib.sha256(worker.read_bytes()).hexdigest() == arm["mechanism_hash"]
    integrated_worker._verify_dependencies()


def test_original_ordinal_routing_preserves_source_guard_replay_and_deadline() -> None:
    baseline_module = SimpleNamespace(REFERENCE="baseline")

    class FakeFrozen:
        def __init__(self):
            self.V2 = baseline_module

        def run_local_arm(self, arm, **kwargs):
            route = "baseline" if self.V2 is baseline_module else "spectral"
            return {
                "route": route,
                "arm": arm,
                "base_case": kwargs["base_case"],
                "program": kwargs["program"],
                "literal_prefix": kwargs["literal_prefix"],
                "deadline": kwargs["deadline_monotonic"],
            }

    class FakePolicy:
        @staticmethod
        def run_rung_scheduler(starts, *, run_rung, **_kwargs):
            return tuple(run_rung(spec, 64, 91.0, None) for spec in starts)

    frozen = FakeFrozen()
    deep = SimpleNamespace(FROZEN=frozen)
    current = SimpleNamespace(
        ADAPTER=SimpleNamespace(
            POLICY=FakePolicy(),
            BASE=SimpleNamespace(DEEP=deep),
        )
    )
    spectral = SimpleNamespace(
        PARENT=SimpleNamespace(REFERENCE="baseline"),
        compile_program=lambda document: document,
        solve_local=lambda *_args, **_kwargs: None,
    )
    integrated_worker.install_search_patch(current, spectral)

    source_program = object()
    guarded_case = object()
    source_prefix = object()

    def run_rung(spec, _allowance, deadline, _checkpoint):
        return frozen.run_local_arm(
            "current-campaign-arm",
            base_case=guarded_case,
            program=source_program,
            literal_prefix=source_prefix,
            deadline_monotonic=deadline,
        )

    specs = tuple(SimpleNamespace(ordinal=index) for index in range(8))
    observed = current.ADAPTER.POLICY.run_rung_scheduler(
        specs,
        run_rung=run_rung,
    )
    assert [row["route"] for row in observed] == [
        "baseline",
        "baseline",
        "baseline",
        "spectral",
        "baseline",
        "baseline",
        "baseline",
        "spectral",
    ]
    assert all(row["base_case"] is guarded_case for row in observed)
    assert all(row["program"] is source_program for row in observed)
    assert all(row["literal_prefix"] is source_prefix for row in observed)
    assert all(row["deadline"] == 91.0 for row in observed)
    assert frozen.V2 is baseline_module


def test_zero_activation_fallback_is_canonical_byte_identical() -> None:
    @dataclass(frozen=True)
    class Outcome:
        endpoint: tuple[float, ...]
        status: str
        counters: dict[str, int]

    baseline = Outcome((1.25, -0.5), "stalled", {"callbacks": 17, "safe": 0})
    spectral = SimpleNamespace(
        solve_local=lambda *_args, **_kwargs: Outcome(
            baseline.endpoint,
            baseline.status,
            {
                **baseline.counters,
                "spectral_cosh_linearizations": 4,
                "spectral_cosh_activations": 0,
                "spectral_cosh_fallbacks": 4,
            },
        )
    )
    observed = integrated_worker._fallback_identity_solve(spectral)

    def encode(value):
        return json.dumps(asdict(value), sort_keys=True, separators=(",", ":")).encode()

    assert encode(observed) == encode(baseline)


def test_patch_installs_on_actual_current_search_modules() -> None:
    current = integrated_worker._load(
        "test_spectral_cosh_actual_current_search",
        integrated_worker.CURRENT_SEARCH_WORKER,
    )
    spectral = integrated_worker._load(
        "test_spectral_cosh_actual_candidate",
        integrated_worker.SPECTRAL_CANDIDATE,
    )
    original_deadline_reserve = current.ADAPTER.BASE.DEEP.FINALIZE_RESERVE_SECONDS
    record = integrated_worker.install_search_patch(current, spectral)
    assert record["baseline_minimum_share"] == 0.75
    assert record["source_evaluator_guard_replay_or_deadline_changed"] is False
    assert current.ADAPTER.BASE.DEEP.FINALIZE_RESERVE_SECONDS == (
        original_deadline_reserve
    )
