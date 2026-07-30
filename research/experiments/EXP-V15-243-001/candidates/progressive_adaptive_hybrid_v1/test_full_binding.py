from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import re
import sys


HERE = Path(__file__).resolve().parent
HEX40 = re.compile(r"^[0-9a-f]{40}$")
HEX64 = re.compile(r"^[0-9a-f]{64}$")


def _load(name: str, path: Path):
    specification = importlib.util.spec_from_file_location(name, path)
    assert specification is not None and specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    sys.modules[name] = module
    specification.loader.exec_module(module)
    return module


def test_adapter_exposes_only_common_control_and_hybrid() -> None:
    adapter = _load("test_adaptive_hybrid_adapter", HERE / "search_adapter.py")
    assert adapter.ARMS == (adapter.CONTROL, adapter.CANDIDATE)
    assert adapter.CANDIDATE == "progressive_adaptive_hybrid_64_600"
    assert adapter.BINDING_RECORD["canonical_verifier_modified"] is False
    assert adapter.BINDING_RECORD[
        "case_family_truth_target_or_previous_outcome_routing"
    ] is False


def test_full_wrapper_changes_only_declared_search_seam(monkeypatch) -> None:
    wrapper = _load("test_adaptive_hybrid_full_wrapper", HERE / "full_wrapper.py")
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
        frozen_root=frozen_root,
        python=Path("/home/kabatan/work/solver/.venv/bin/python"),
    )
    assert configured.SEARCH_ARM == "progressive_adaptive_hybrid_64_600"
    assert configured.SEARCH_WORKER == HERE / "search_worker.py"
    assert configured.SEARCH_ADAPTER == HERE / "search_adapter.py"
    assert configured.SEARCH_CANDIDATE == HERE / "candidate.py"
    for name, value in authority.items():
        assert getattr(configured, name) is value


def test_arm_contract_and_transitive_hash_binding() -> None:
    manifest_path = HERE / "arm.json"
    document = json.loads(manifest_path.read_text())
    assert set(document) == {"id", "base_commit", "entrypoint", "mechanism_hash"}
    assert document["id"] == document["id"].lower()
    assert HEX40.fullmatch(document["base_commit"])
    assert HEX64.fullmatch(document["mechanism_hash"])
    resolved = (manifest_path.parent / document["entrypoint"]).resolve()
    assert resolved == HERE / "full_worker.py"
    assert hashlib.sha256(resolved.read_bytes()).hexdigest() == document[
        "mechanism_hash"
    ]
    wrapper_hash = hashlib.sha256((HERE / "full_wrapper.py").read_bytes()).hexdigest()
    assert wrapper_hash in resolved.read_text()


def test_smoke_and_s0_evidence_bind_current_candidate_and_entrypoint() -> None:
    candidate_sha = hashlib.sha256((HERE / "candidate.py").read_bytes()).hexdigest()
    entrypoint_sha = hashlib.sha256((HERE / "full_worker.py").read_bytes()).hexdigest()
    s0 = json.loads((HERE / "S0_EVIDENCE.json").read_text())
    smoke = json.loads((HERE / "FULL_BINDING_SMOKE.json").read_text())
    assert s0["candidate_sha256"] == candidate_sha
    assert smoke["candidate_sha256"] == candidate_sha
    assert smoke["entrypoint_sha256"] == entrypoint_sha
    assert smoke["formal_screen_executed"] is False
    assert smoke["scorer_used"] is False
