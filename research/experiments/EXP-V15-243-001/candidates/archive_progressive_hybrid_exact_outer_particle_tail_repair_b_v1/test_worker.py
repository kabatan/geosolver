from __future__ import annotations

from contextlib import contextmanager
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
from types import SimpleNamespace
import sys
import time
import uuid

import pytest


HERE = Path(__file__).resolve().parent
WORKER = HERE / "worker.py"
ARM = HERE / "arm.json"


def _load_worker(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("GEOTARGET_EXACT_OUTER_SCHEDULER_WORKER", raising=False)
    monkeypatch.delenv("GEOTARGET_EXACT_OUTER_MODE", raising=False)
    name = f"archive_particle_exact_test_{uuid.uuid4().hex}"
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


def _source(tmp_path: Path, names=("x",)) -> tuple[Path, str]:
    document = {
        "task": "solve",
        "variables": {"names": list(names)},
        "construction": [],
        "constraints": ([] if not names else ["x == 0"]),
        "guards": [],
        "answer": ("0" if not names else "x"),
        "post_process": "",
    }
    path = tmp_path / ("zero.json" if not names else "source.json")
    path.write_text(json.dumps(document), encoding="utf-8")
    return path, hashlib.sha256(path.read_bytes()).hexdigest()


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


def test_one_base_and_exact_authority_boundary(module) -> None:
    scheduler = module.SCHEDULER
    assert scheduler.HISTORICAL is scheduler.CONTROL
    assert module.BASE is scheduler.CONTROL.CHAMPION.BASE
    assert module.BASE.SEARCH_ARM == "progressive_adaptive_hybrid_64_600"
    assert module.OUTER._ORDINARY_HP is scheduler.UPSTREAM._HISTORICAL_HP
    assert module.BASE._run_hp_candidate is module.OUTER._run_exact_outer
    assert module.ZERO is scheduler.CONTROL.CHAMPION.ZERO
    assert module.OUTER._FROZEN_SCHEDULER_SHA256 == module.EXPECTED_SCHEDULER_SHIM_SHA256
    closure = module.OUTER._compact_closure()
    assert closure["closure_sha256"]
    assert module.OUTER.verify_exact_freeze()


def test_plan_freezes_quota_failure_and_authority_contract(module, tmp_path: Path) -> None:
    source, digest = _source(tmp_path)
    plan = module.BASE._plan(
        source=source,
        source_sha256=digest,
        total_seconds=180.0,
        search_seconds=146.0,
        starts=256,
        callbacks_per_start=600,
        aggregate_callback_cap=153_600,
        seed=0,
        cpu=15,
        output=tmp_path / "plan",
    )
    assert plan["exact_outer_mode"] == "CONFIRM_ALL_AUTHORITIES"
    assert plan["baseline_budget_quota_minimum"] == 0.75
    assert plan["particle_tail_callback_fraction_cap"] == 0.25
    assert plan["particle_tail_wall_fraction_cap"] == 0.25
    assert plan["particle_mixed_ad_fd_policy"].startswith("fail-closed")
    assert plan["positive_dimensional_particle_authority_can_bypass_exact_outer"] is False
    assert plan["case_family_truth_target_count_or_outcome_routing"] is False


def test_tail_proxy_caps_callback_and_wall_budget(
    module, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    scheduler = module.SCHEDULER
    source, _digest = _source(tmp_path)
    output = tmp_path / "output"
    output.mkdir()
    (output / "search.json").write_text(
        json.dumps({"work": {"callbacks": 1000}}), encoding="utf-8"
    )
    captured = {}

    def run_tail(**kwargs):
        captured.update(kwargs)

    monkeypatch.setattr(scheduler.TAIL, "_run_tail", run_tail)
    arguments = SimpleNamespace(
        source=source,
        output=output,
        aggregate_callback_cap=4000,
        total_seconds=40.0,
    )
    started = time.monotonic()
    scheduler._run_particle_tail(arguments=arguments, hard_deadline=started + 100.0)
    assert captured["arguments"].aggregate_callback_cap == 2000
    assert captured["arguments"] is not arguments
    assert started < captured["hard_deadline"] <= started + 10.1
    assert captured["base"] is module.BASE


def test_zero_dimensional_source_never_invokes_tail(
    module, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    scheduler = module.SCHEDULER
    source, _digest = _source(tmp_path, ())
    output = tmp_path / "zero-output"
    output.mkdir()
    (output / "search.json").write_text(
        json.dumps({"work": {"callbacks": 0}}), encoding="utf-8"
    )
    monkeypatch.setattr(
        scheduler.TAIL,
        "_run_tail",
        lambda **_kwargs: pytest.fail("zero-dimensional tail invoked"),
    )
    arguments = SimpleNamespace(
        source=source,
        output=output,
        aggregate_callback_cap=4000,
        total_seconds=40.0,
    )
    scheduler._run_particle_tail(arguments=arguments, hard_deadline=time.monotonic() + 100.0)


def test_tail_authority_is_exact_confirmed(
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
    candidate = SimpleNamespace(
        endpoint=(0.0,),
        endpoint_sha256="a" * 64,
        residual_inf=0.0,
        provisional_target=0.0,
        cluster_ordinal=0,
        cluster_rank=0,
    )
    result = module.OUTER._run_exact_outer(
        timeout_seconds=30.0,
        source=source,
        source_sha256=digest,
        candidate=candidate,
        cpu=15,
        output=tmp_path / "authority",
    )
    assert result is not None
    assert result["status"] == "TARGET_AUTHORITY_READY"
    assert result["descriptor"] is exact
    assert result["ordinary_descriptor_is_final_authority"] is False
    assert result["ordinary_and_exact_descriptor_identity_match"] is True


def test_arm_mechanism_hash_is_entrypoint_hash() -> None:
    arm = json.loads(ARM.read_text(encoding="utf-8"))
    assert arm["entrypoint"] == "worker.py"
    assert arm["mechanism_hash"] == hashlib.sha256(WORKER.read_bytes()).hexdigest()


def test_scheduler_shim_stale_mutation_fails_closed(
    module, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    stale = tmp_path / "scheduler_shim.py"
    stale.write_bytes(module.SCHEDULER_SHIM.read_bytes() + b"\n# stale mutation\n")
    monkeypatch.setattr(module, "SCHEDULER_SHIM", stale)
    with pytest.raises(module.IntegrationError, match="scheduler changed"):
        module._assert_runtime_binding()


def test_shared_source_worker_stale_mutation_fails_before_import(
    module, tmp_path: Path
) -> None:
    real_worker = module.SCHEDULER.PARTICLE_ROOT / "real_search_worker.py"
    expected = module.SCHEDULER.EXPECTED_SHA256[real_worker]
    assert hashlib.sha256(real_worker.read_bytes()).hexdigest() == expected
    stale = tmp_path / "shared-worker.py"
    stale.write_text("raise AssertionError('stale worker executed')\n", encoding="utf-8")
    environment = dict(os.environ)
    environment["GEOTARGET_PARTICLE_SHARED_SOURCE_WORKER"] = str(stale)
    code = (
        "import importlib.util,sys;"
        f"p={str(real_worker)!r};"
        "s=importlib.util.spec_from_file_location('stale_shared_worker_probe',p);"
        "m=importlib.util.module_from_spec(s);sys.modules[s.name]=m;"
        "s.loader.exec_module(m)"
    )
    completed = subprocess.run(
        [sys.executable, "-c", code],
        check=False,
        capture_output=True,
        text=True,
        env=environment,
        timeout=10.0,
    )
    assert completed.returncode != 0
    assert "particle shared source-worker SHA-256 mismatch" in completed.stderr
    assert "stale worker executed" not in completed.stderr
