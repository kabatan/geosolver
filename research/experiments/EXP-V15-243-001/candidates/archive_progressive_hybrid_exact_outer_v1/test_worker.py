from __future__ import annotations

from contextlib import contextmanager
import hashlib
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
import sys
import uuid

import numpy as np
import pytest


HERE = Path(__file__).resolve().parent
WORKER = HERE / "worker.py"
ARM = HERE / "arm.json"


def _load_worker(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("GEOTARGET_EXACT_OUTER_SCHEDULER_WORKER", raising=False)
    monkeypatch.delenv("GEOTARGET_EXACT_OUTER_MODE", raising=False)
    name = f"archive_progressive_exact_test_{uuid.uuid4().hex}"
    specification = importlib.util.spec_from_file_location(name, WORKER)
    assert specification is not None and specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    sys.modules[name] = module
    specification.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def module():
    monkeypatch = pytest.MonkeyPatch()
    loaded = _load_worker(monkeypatch)
    yield loaded
    monkeypatch.undo()


def _descriptor(value: int = 0) -> dict[str, object]:
    polynomial = [1, -value]
    return {
        "minimal_polynomial_high_to_low": polynomial,
        "selected_real_root_index": 0,
        "isolating_interval": {
            "left": str(value),
            "right": str(value),
            "multiplicity": 1,
            "real_root_index": 0,
        },
        "proposal_relation_low_to_high": list(reversed(polynomial)),
        "confirmation_relation_low_to_high": list(reversed(polynomial)),
        "target_512": str(value),
        "target_768": str(value),
        "target_1024": str(value),
    }


def _ordinary_ready(value: int = 0) -> dict[str, object]:
    return {
        "attempt_kind": "HISTORICAL_POC_ORDINARY_HP",
        "endpoint_float64_sha256": "a" * 64,
        "residual_inf": 0.0,
        "provisional_target": float(value),
        "cluster_ordinal": 0,
        "cluster_rank": 0,
        "status": "TARGET_AUTHORITY_READY",
        "authority_pass": True,
        "descriptor": _descriptor(value),
    }


def _candidate(value: float = 0.0) -> SimpleNamespace:
    return SimpleNamespace(
        endpoint=(value,),
        endpoint_sha256="a" * 64,
        residual_inf=0.0,
        provisional_target=value,
        cluster_ordinal=0,
        cluster_rank=0,
    )


def _source(tmp_path: Path) -> tuple[Path, str]:
    document = {
        "task": "solve",
        "variables": {"names": ["x"]},
        "construction": [],
        "constraints": ["x == 0"],
        "guards": [],
        "answer": "x",
        "post_process": "",
    }
    path = tmp_path / "source.json"
    path.write_text(json.dumps(document), encoding="utf-8")
    return path, hashlib.sha256(path.read_bytes()).hexdigest()


def _kwargs(tmp_path: Path, source: Path, digest: str) -> dict[str, object]:
    return {
        "timeout_seconds": 1.0,
        "source": source,
        "source_sha256": digest,
        "candidate": _candidate(),
        "cpu": 15,
        "output": tmp_path / "output",
    }


def test_progressive_and_historical_poc_are_one_execution(module) -> None:
    scheduler = module.SCHEDULER
    assert scheduler.HISTORICAL is scheduler.CONTROL
    assert module.BASE is scheduler.CONTROL.CHAMPION.BASE
    assert module.BASE.SEARCH_ARM == "progressive_adaptive_hybrid_64_600"
    assert module.BASE.SEARCH_WORKER == scheduler.SEARCH_WORKER
    assert module.BASE.SEARCH_ADAPTER == scheduler.SEARCH_ADAPTER
    assert module.BASE.SEARCH_CANDIDATE == scheduler.SEARCH_CANDIDATE
    assert module.OUTER._ORDINARY_HP is scheduler._HISTORICAL_HP
    assert module.BASE._run_hp_candidate is module.OUTER._run_exact_outer
    assert module.ZERO is scheduler.CONTROL.CHAMPION.ZERO
    for name, value in scheduler._HISTORICAL_AUTHORITY.items():
        if name != "_run_hp_candidate":
            assert getattr(module.BASE, name) is value


def test_progressive_baseline_and_insurance_quotas_execute(module) -> None:
    policy = module.SCHEDULER.SEARCH_POLICY
    starts = tuple(
        policy.StartSpec(
            ordinal,
            (
                policy.INSURANCE_SOURCE
                if ordinal % 4 == 0
                else "source_literal_product_cauchy"
            ),
            np.asarray([float(ordinal), 2.0 * ordinal + 1.0]),
            ordinal % 4 == 0,
        )
        for ordinal in range(32)
    )

    class Clock:
        now = 0.0

        def __call__(self) -> float:
            return self.now

    clock = Clock()

    def runner(spec, allowance, deadline, checkpoint):
        del deadline, checkpoint
        clock.now += 0.001
        return policy.RungOutcome(
            spec.point.copy(),
            policy.Assessment(True, True, float(spec.ordinal + 1), 0.0),
            min(allowance, 1),
            "SYNTHETIC_FAST",
        )

    result = policy.run_rung_scheduler(
        starts,
        callback_cap=100_000,
        hard_deadline=100.0,
        finalize_reserve_seconds=0.0,
        run_rung=runner,
        clock=clock,
    )

    assert result.activation["minimum_service_complete"] is True
    assert result.activation["handoff_selected_count"] == 16
    assert result.activation["baseline_handoff_selected"] == 4
    assert result.activation["insurance_handoff_selected"] == 4
    assert result.activation["counter_cauchy_service_floor_holds"] is True


def test_ready_ordinary_authority_cannot_escape_exact_deadline(
    module, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(module.OUTER, "_ORDINARY_HP", lambda **_kw: _ordinary_ready())
    source, digest = _source(tmp_path)

    result = module.OUTER._run_exact_outer(**_kwargs(tmp_path, source, digest))

    assert result is not None
    assert result["status"] == "EXACT_CONFIRMATION_NOT_RUN"
    assert result["authority_pass"] is False
    assert result["descriptor"] is None
    assert result["ordinary_descriptor_is_final_authority"] is False


def test_matching_exact_replay_is_the_only_published_descriptor(
    module, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    exact = _descriptor()
    monkeypatch.setattr(module.OUTER, "_ORDINARY_HP", lambda **_kw: _ordinary_ready())
    monkeypatch.setattr(module.OUTER, "_consume_fallback", lambda **_kw: exact)

    @contextmanager
    def lease(_cpu: int, *, wait_seconds: float):
        assert wait_seconds >= 0.0
        yield

    monkeypatch.setattr(module.SCHEDULER.adapter, "per_core_lease", lease)
    guarded = SimpleNamespace(
        classification="SUCCESS",
        accepted_output=True,
        descendant_leak=False,
        to_dict=lambda: {
            "classification": "SUCCESS",
            "accepted_output": True,
            "descendant_leak": False,
        },
    )
    monkeypatch.setattr(module.BASE, "run_guarded", lambda *_a, **_kw: guarded)
    source, digest = _source(tmp_path)
    kwargs = _kwargs(tmp_path, source, digest)
    kwargs["timeout_seconds"] = 30.0

    result = module.OUTER._run_exact_outer(**kwargs)

    assert result is not None
    assert result["status"] == "TARGET_AUTHORITY_READY"
    assert result["descriptor"] is exact
    assert result["ordinary_descriptor_is_final_authority"] is False
    assert result["ordinary_and_exact_descriptor_identity_match"] is True


def test_plan_records_search_quota_and_exact_boundary(module, tmp_path: Path) -> None:
    source, digest = _source(tmp_path)
    plan = module.BASE._plan(
        source=source,
        source_sha256=digest,
        total_seconds=30.0,
        search_seconds=20.0,
        starts=32,
        callbacks_per_start=600,
        aggregate_callback_cap=19_200,
        seed=0,
        cpu=15,
        output=tmp_path / "plan",
    )

    assert plan["search_arm"] == "progressive_adaptive_hybrid_64_600"
    assert plan["exact_outer_mode"] == "CONFIRM_ALL_AUTHORITIES"
    assert plan["exact_outer_ordinary_hp_capture_count"] == 1
    assert plan["ordinary_original_order_baseline_handoff_fraction"] == 0.25
    assert plan["ordinary_baseline_quota_permanently_retained"] is True
    assert plan["positive_dimensional_ordinary_authority_can_bypass_exact_outer"] is False
    assert plan["case_family_truth_target_count_or_outcome_routing"] is False


def test_conflicting_exact_mode_fails_before_composition(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("GEOTARGET_EXACT_OUTER_MODE", "FAILURE_ONLY")
    monkeypatch.delenv("GEOTARGET_EXACT_OUTER_SCHEDULER_WORKER", raising=False)
    name = f"archive_progressive_exact_conflict_{uuid.uuid4().hex}"
    specification = importlib.util.spec_from_file_location(name, WORKER)
    assert specification is not None and specification.loader is not None
    loaded = importlib.util.module_from_spec(specification)
    sys.modules[name] = loaded
    with pytest.raises(RuntimeError, match="conflicting global setting"):
        specification.loader.exec_module(loaded)


def test_arm_mechanism_hash_is_entrypoint_hash() -> None:
    arm = json.loads(ARM.read_text(encoding="utf-8"))
    assert arm["entrypoint"] == "worker.py"
    assert arm["mechanism_hash"] == hashlib.sha256(WORKER.read_bytes()).hexdigest()
