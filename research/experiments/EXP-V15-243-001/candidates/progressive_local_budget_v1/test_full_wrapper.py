from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import re
import sys

import pytest


HERE = Path(__file__).resolve().parent
HEX40 = re.compile(r"^[0-9a-f]{40}$")
HEX64 = re.compile(r"^[0-9a-f]{64}$")


def _load_wrapper():
    name = "test_progressive_local_budget_full_wrapper"
    path = HERE / "full_wrapper.py"
    specification = importlib.util.spec_from_file_location(name, path)
    assert specification is not None and specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    sys.modules[name] = module
    specification.loader.exec_module(module)
    return module


@pytest.mark.parametrize(
    ("profile", "arm"),
    [
        ("64-192-600", "progressive_local_budget_64_192_600"),
        ("96-300-600", "progressive_local_budget_96_300_600"),
    ],
)
def test_only_declared_full_worker_seams_change(profile, arm, monkeypatch) -> None:
    wrapper = _load_wrapper()
    frozen_root = Path("/home/kabatan/work/solver-experiment-runtime/solver")
    original = wrapper._load_frozen(frozen_root)
    authority = {
        name: getattr(original, name)
        for name in (
            "SCHEMA",
            "HP_BRIDGE",
            "PRECISION_RUNTIME",
            "RESTORATION_WORKER",
            "RESTORATION_ADAPTER",
            "RESTORATION_CANDIDATE",
            "_authority_descriptor",
            "_descriptor_key",
            "_fresh_replay_candidates",
            "_run_hp_candidate",
            "_run_restoration_candidate",
        )
    }
    monkeypatch.setattr(wrapper, "_load_frozen", lambda _root: original)
    configured = wrapper.configure(
        profile,
        frozen_root=frozen_root,
        python=Path("/home/kabatan/work/solver/.venv/bin/python"),
    )
    assert configured.SEARCH_ARM == arm
    assert configured.SEARCH_WORKER == HERE / "search_worker.py"
    assert configured.SEARCH_ADAPTER == HERE / "search_adapter.py"
    assert configured.SEARCH_CANDIDATE == HERE / "candidate.py"
    for name, value in authority.items():
        assert getattr(configured, name) is value
    assert configured.SCHEMA == "geotarget.exp008-finalist-numeric-worker-v15/v1"


def test_unknown_profile_fails_closed() -> None:
    wrapper = _load_wrapper()
    with pytest.raises(SystemExit, match="unknown progressive profile"):
        wrapper.configure(
            "problem-specific",
            frozen_root=Path("/home/kabatan/work/solver-experiment-runtime/solver"),
            python=Path("/home/kabatan/work/solver/.venv/bin/python"),
        )


@pytest.mark.parametrize(
    ("directory", "entrypoint"),
    [("profile64", "full_worker_profile64.py"), ("profile96", "full_worker_profile96.py")],
)
def test_arm_contract_and_transitive_hash_binding(directory, entrypoint) -> None:
    manifest_path = HERE / "arms" / directory / "arm.json"
    document = json.loads(manifest_path.read_text())
    assert set(document) == {"id", "base_commit", "entrypoint", "mechanism_hash"}
    assert document["id"] == document["id"].lower()
    assert HEX40.fullmatch(document["base_commit"])
    assert HEX64.fullmatch(document["mechanism_hash"])
    resolved = (manifest_path.parent / document["entrypoint"]).resolve()
    assert resolved == HERE / entrypoint
    assert hashlib.sha256(resolved.read_bytes()).hexdigest() == document["mechanism_hash"]
    source = resolved.read_text()
    wrapper_hash = hashlib.sha256((HERE / "full_wrapper.py").read_bytes()).hexdigest()
    assert wrapper_hash in source
