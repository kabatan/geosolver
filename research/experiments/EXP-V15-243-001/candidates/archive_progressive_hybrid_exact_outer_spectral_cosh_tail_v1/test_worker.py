from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np

import scheduler_shim
import tail_search_worker
import worker


SPECTRAL_ROOT = Path(__file__).resolve().parent.parent / "spectral_cosh_preconditioned_gn_v1"
tail_search_worker._load("real_seam_patch", SPECTRAL_ROOT / "real_seam_patch.py")
spectral = tail_search_worker._load("test_spectral_cosh_tail_candidate", SPECTRAL_ROOT / "real_candidate.py")


def test_single_base_and_exact_authority() -> None:
    worker._assert_runtime_binding()
    assert worker.BASE is worker.SCHEDULER.CONTROL.CHAMPION.BASE
    assert worker.BASE._run_hp_candidate is worker.OUTER._run_exact_outer
    assert worker.OUTER.MODE == worker.CONFIRM_ALL_AUTHORITIES
    assert worker.ZERO is worker.SCHEDULER.CONTROL.CHAMPION.ZERO


def test_plan_records_surplus_contract(tmp_path: Path) -> None:
    source = tmp_path / "source.json"
    payload = json.dumps({"variables": {"names": ["x"]}}).encode()
    source.write_bytes(payload)
    plan = worker.BASE._plan(
        source=source,
        source_sha256=hashlib.sha256(payload).hexdigest(),
        total_seconds=30.0,
        search_seconds=20.0,
        starts=16,
        callbacks_per_start=100,
        aggregate_callback_cap=1600,
        seed=0,
        cpu=15,
        output=tmp_path / "output",
    )
    assert plan["spectral_cosh_surplus_tail"] is True
    assert plan["spectral_cosh_baseline_combined_share_minimum"] == 0.75
    assert plan["spectral_cosh_tail_callback_fraction_cap"] == 0.25
    assert plan["spectral_cosh_ordinal_schedule"] is False
    assert plan["spectral_cosh_tail_insurance_services_use_ordinary_fd"] is True
    assert plan["positive_dimensional_authority_can_bypass_exact_outer"] is False


def test_tail_routes_insurance_to_ordinary_without_ordinal_schedule() -> None:
    baseline_module = SimpleNamespace(REFERENCE="baseline")

    class FakeFrozen:
        def __init__(self):
            self.V2 = baseline_module

        def run_local_arm(self, arm, **_kwargs):
            return "ordinary" if self.V2 is baseline_module else "spectral"

    class FakePolicy:
        @staticmethod
        def run_rung_scheduler(starts, *, run_rung, **_kwargs):
            return tuple(run_rung(spec, 64, 99.0, None) for spec in starts)

    frozen = FakeFrozen()
    current = SimpleNamespace(
        ADAPTER=SimpleNamespace(
            POLICY=FakePolicy(),
            BASE=SimpleNamespace(DEEP=SimpleNamespace(FROZEN=frozen)),
        )
    )
    fake_spectral = SimpleNamespace(
        PARENT=SimpleNamespace(REFERENCE="baseline"),
        compile_program=lambda document: document,
        solve_local=lambda *_args, **_kwargs: None,
    )
    record = tail_search_worker.install_search_patch(current, fake_spectral)
    specs = (
        SimpleNamespace(ordinal=11, insurance=False),
        SimpleNamespace(ordinal=3, insurance=True),
        SimpleNamespace(ordinal=100, insurance=False),
        SimpleNamespace(ordinal=0, insurance=True),
    )

    def run_rung(_spec, _allowance, _deadline, _checkpoint):
        return frozen.run_local_arm("progressive")

    observed = current.ADAPTER.POLICY.run_rung_scheduler(specs, run_rung=run_rung)
    assert observed == ("spectral", "ordinary", "spectral", "ordinary")
    assert record["ordinal_schedule"] is False
    assert record["ordinary_counter_cauchy_insurance_preserved"] is True
    assert frozen.V2 is baseline_module


def test_zero_activation_serialization_is_baseline_identical() -> None:
    @dataclass(frozen=True)
    class Outcome:
        endpoint: tuple[float, ...]
        status: str
        counters: dict[str, int]

    baseline = Outcome((1.0,), "stalled", {"callbacks": 9})
    candidate = SimpleNamespace(
        solve_local=lambda *_args, **_kwargs: Outcome(
            baseline.endpoint,
            baseline.status,
            {
                "callbacks": 9,
                "spectral_cosh_linearizations": 2,
                "spectral_cosh_activations": 0,
                "spectral_cosh_fallbacks": 2,
            },
        )
    )
    observed = tail_search_worker._fallback_identity_solve(candidate)
    encode = lambda value: json.dumps(asdict(value), sort_keys=True, separators=(",", ":"))
    assert encode(observed) == encode(baseline)


def test_patch_installs_on_actual_progressive_search_without_deadline_change() -> None:
    current = tail_search_worker._load(
        "test_spectral_tail_actual_progressive_search",
        tail_search_worker.CURRENT_SEARCH_WORKER,
    )
    original_reserve = current.ADAPTER.BASE.DEEP.FINALIZE_RESERVE_SECONDS
    record = tail_search_worker.install_search_patch(current, spectral)
    assert record["ordinal_schedule"] is False
    assert record["source_evaluator_guard_replay_or_deadline_changed"] is False
    assert current.ADAPTER.BASE.DEEP.FINALIZE_RESERVE_SECONDS == original_reserve


def test_guard_branch_and_raw_model_disagreement_fail_closed() -> None:
    class Program:
        construction = (("p", "LineCircleIntersect(line,circle,near=q)"),)
        constraints = (("x*x", "1"),)
        guards = ()

        def relation_rows(self, _start):
            return (object(),)

    assert spectral._source_smooth_at_start(Program(), [0.0]) is False

    class Guarded(Program):
        construction = (("q", "Distance(P,Q)"),)
        guards = ("x > 0",)

    assert spectral._source_smooth_at_start(Guarded(), [0.0]) is False

    class Unknown(Program):
        construction = (("q", "OpaqueWarp(P,Q)"),)
        constraints = (("q*q", "1"),)

        def relation_rows(self, _start):
            return (None,)

    assert spectral._source_smooth_at_start(Unknown(), [0.0]) is False
    J = np.eye(2)
    residual = np.array([2.0, 1.0])
    ordinary = np.array([-1.0, -0.5])
    agreeing = np.array([-1.5, -0.75])
    opposing = -agreeing
    assert spectral._raw_model_agrees(J, residual, 1e-3, ordinary, agreeing)
    assert not spectral._raw_model_agrees(J, residual, 1e-3, ordinary, opposing)


def test_combined_quota_caps_and_zero_bypass(tmp_path: Path, monkeypatch) -> None:
    source = tmp_path / "positive.json"
    source.write_text(json.dumps({"variables": {"names": ["x"]}}))
    arguments = SimpleNamespace(
        source=source,
        output=tmp_path / "out",
        aggregate_callback_cap=2400,
        total_seconds=120.0,
        starts=16,
        callbacks_per_start=100,
    )
    captured = {}
    monkeypatch.setattr(scheduler_shim, "_callbacks_used", lambda _output: 1800)
    monkeypatch.setattr(scheduler_shim.time, "monotonic", lambda: 100.0)
    monkeypatch.setattr(scheduler_shim.BASE, "PROCESS_STARTED", 10.0)
    monkeypatch.setattr(
        scheduler_shim,
        "_run_tail",
        lambda **kwargs: captured.update(kwargs),
    )
    scheduler_shim._run_spectral_tail(arguments=arguments, hard_deadline=200.0)
    assert captured["callback_cap"] == 600
    assert captured["hard_deadline"] == 130.0

    zero = tmp_path / "zero.json"
    zero.write_text(json.dumps({"variables": {"names": []}}))
    arguments.source = zero
    captured.clear()
    scheduler_shim._run_spectral_tail(arguments=arguments, hard_deadline=200.0)
    assert captured == {}


def test_arm_and_dependency_hashes() -> None:
    here = Path(__file__).resolve().parent
    arm = json.loads((here / "arm.json").read_text())
    assert arm["id"] == "archive-progressive-hybrid-exact-outer-spectral-cosh-tail-v1"
    assert hashlib.sha256((here / arm["entrypoint"]).read_bytes()).hexdigest() == arm["mechanism_hash"]
    scheduler_shim.verify_dependencies()
    tail_search_worker.verify_dependencies()
