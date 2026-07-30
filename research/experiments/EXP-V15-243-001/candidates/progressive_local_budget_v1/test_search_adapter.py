from __future__ import annotations

import hashlib
import importlib.util
from pathlib import Path
import sys

import pytest


HERE = Path(__file__).resolve().parent


def load_adapter():
    path = HERE / "search_adapter.py"
    specification = importlib.util.spec_from_file_location(
        "test_progressive_local_budget_adapter", path
    )
    assert specification is not None and specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    sys.modules[specification.name] = module
    specification.loader.exec_module(module)
    return module


def test_hash_bound_runtime_and_profile_routing(monkeypatch) -> None:
    adapter = load_adapter()
    assert hashlib.sha256(adapter.DEEP_ADAPTER_PATH.read_bytes()).hexdigest() == (
        adapter.DEEP_ADAPTER_SHA256
    )
    calls = []

    def fake(arm, **kwargs):
        calls.append((arm, tuple(adapter.POLICY.RUNG_CALLBACK_CAPS), kwargs))
        return "sentinel"

    monkeypatch.setattr(adapter.DEEP, "run_local_arm", fake)
    assert adapter.run_local_arm(adapter.PROFILE_64, marker=64) == "sentinel"
    assert calls[-1][1] == (64, 192, 600)
    assert adapter.run_local_arm(adapter.PROFILE_96, marker=96) == "sentinel"
    assert calls[-1][1] == (96, 300, 600)
    assert adapter.run_local_arm(adapter.CONTROL, marker=0) == "sentinel"
    assert calls[-1][0] == adapter.DEEP.CONTROL


def test_unknown_arm_fails_closed() -> None:
    adapter = load_adapter()
    with pytest.raises(ValueError, match="unknown"):
        adapter.run_local_arm("case-specific-magic")


def test_binding_preserves_source_and_verifier() -> None:
    manifest = load_adapter().configuration_manifest()
    assert manifest["same_frozen_v15_local_kernel"] is True
    assert manifest["source_problem_modified"] is False
    assert manifest["case_family_truth_target_or_previous_outcome_routing"] is False
    assert manifest["canonical_verifier_modified"] is False
