from __future__ import annotations

from contextlib import contextmanager
import hashlib
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
import sys
import uuid

import pytest


HERE = Path(__file__).resolve().parent
WORKER = HERE / "worker.py"
ARM = HERE / "arm.json"


def _load_worker(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("GEOTARGET_EXACT_OUTER_SCHEDULER_WORKER", raising=False)
    monkeypatch.delenv("GEOTARGET_EXACT_OUTER_MODE", raising=False)
    name = f"archive_exact_outer_test_{uuid.uuid4().hex}"
    specification = importlib.util.spec_from_file_location(name, WORKER)
    assert specification is not None and specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    sys.modules[name] = module
    specification.loader.exec_module(module)
    return module


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
        "attempt_kind": "ARCHIVED_ORDINARY_HP",
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
        "constructions": [],
        "constraints": ["x == 0"],
        "guards": [],
        "answer": "x",
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


@pytest.fixture(scope="module")
def module():
    monkeypatch = pytest.MonkeyPatch()
    loaded = _load_worker(monkeypatch)
    yield loaded
    monkeypatch.undo()


def test_exact_outer_captures_historical_poc_hp_once(module) -> None:
    assert module.OUTER.MODE == "CONFIRM_ALL_AUTHORITIES"
    assert module.OUTER.ORDINARY_HP_CAPTURE_COUNT == 1
    assert module.OUTER._ORDINARY_HP is module.SCHEDULER._HISTORICAL_HP
    assert module.BASE._run_hp_candidate is module.OUTER._run_exact_outer
    assert module.ZERO is module.SCHEDULER.HISTORICAL.CHAMPION.ZERO
    assert module.SCHEDULER.adapter.per_core_lease is module.SCHEDULER.POLICY.per_core_lease


def test_every_ready_ordinary_authority_fails_closed_without_tail_budget(
    module, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(module.OUTER, "_ORDINARY_HP", lambda **_kw: _ordinary_ready(0))
    source, digest = _source(tmp_path)

    result = module.OUTER._run_exact_outer(**_kwargs(tmp_path, source, digest))

    assert result is not None
    assert result["status"] == "EXACT_CONFIRMATION_NOT_RUN"
    assert result["authority_pass"] is False
    assert result["descriptor"] is None
    assert result["ordinary_descriptor_is_final_authority"] is False


def test_malformed_ordinary_success_fails_closed(
    module, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(
        module.OUTER,
        "_ORDINARY_HP",
        lambda **_kw: {
            "status": "TARGET_AUTHORITY_READY",
            "authority_pass": True,
            "descriptor": {"not": "an exact descriptor"},
        },
    )
    source, digest = _source(tmp_path)

    result = module.OUTER._run_exact_outer(**_kwargs(tmp_path, source, digest))

    assert result is not None
    assert result["status"] == "MALFORMED_ORDINARY_AUTHORITY_REJECTED"
    assert result["authority_pass"] is False
    assert result["descriptor"] is None


def test_matching_exact_replay_is_the_published_descriptor(
    module, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    exact = _descriptor(0)
    monkeypatch.setattr(module.OUTER, "_ORDINARY_HP", lambda **_kw: _ordinary_ready(0))
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
    assert result["authority_pass"] is True
    assert result["descriptor"] is exact
    assert result["ordinary_descriptor_is_final_authority"] is False
    assert result["ordinary_and_exact_descriptor_identity_match"] is True


def test_plan_is_truth_blind_and_hash_closed(module, tmp_path: Path) -> None:
    source, digest = _source(tmp_path)
    plan = module.BASE._plan(
        source=source,
        source_sha256=digest,
        total_seconds=30.0,
        search_seconds=20.0,
        starts=1,
        callbacks_per_start=2,
        aggregate_callback_cap=2,
        seed=0,
        cpu=15,
        output=tmp_path / "plan",
    )

    assert plan["exact_outer_mode"] == "CONFIRM_ALL_AUTHORITIES"
    assert plan["exact_outer_ordinary_hp_capture_count"] == 1
    assert plan["positive_dimensional_ordinary_authority_can_bypass_exact_outer"] is False
    assert plan["case_family_truth_target_count_or_outcome_routing"] is False
    assert len(plan["archive_reopen_candidate_worker_sha256"]) == 64
    assert len(plan["archive_reopen_scheduler_shim_sha256"]) == 64
    assert len(plan["exact_coordinate_fallback"]["closure"]["closure_sha256"]) == 64


def test_conflicting_global_mode_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GEOTARGET_EXACT_OUTER_MODE", "FAILURE_ONLY")
    monkeypatch.delenv("GEOTARGET_EXACT_OUTER_SCHEDULER_WORKER", raising=False)
    name = f"archive_exact_outer_conflict_{uuid.uuid4().hex}"
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
