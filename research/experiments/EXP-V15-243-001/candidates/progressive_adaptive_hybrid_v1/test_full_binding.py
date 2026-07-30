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


def test_full_wrapper_noop_is_exact_common_control() -> None:
    wrapper = _load("test_adaptive_hybrid_full_wrapper", HERE / "full_wrapper.py")
    frozen_root = Path("/home/kabatan/work/solver-experiment-runtime/solver")
    control = wrapper.configure(frozen_root=frozen_root, enable_hybrid=False)
    wrapper._verify_control_stack(control)
    base = control.CHAMPION.BASE
    assert hashlib.sha256(
        (frozen_root / wrapper.CONTROL_ENTRYPOINT_RELATIVE).read_bytes()
    ).hexdigest() == wrapper.EXPECTED_CONTROL_ENTRYPOINT_SHA256
    assert base.SEARCH_ARM == (
        "precision_isolated_retained_then_strict_nearroot_restart_direct_broyden_ruiz_tr_lm"
    )
    assert hashlib.sha256(Path(base.SEARCH_WORKER).read_bytes()).hexdigest() == (
        wrapper.EXPECTED_CONTROL_CLOSURE_SHA256["baseline_search_worker"]
    )


def test_full_wrapper_changes_only_declared_search_seam(monkeypatch) -> None:
    wrapper = _load("test_adaptive_hybrid_full_wrapper_rebind", HERE / "full_wrapper.py")
    frozen_root = Path("/home/kabatan/work/solver-experiment-runtime/solver")
    control = wrapper._load_control(frozen_root)
    wrapper._verify_control_stack(control)
    original = control.CHAMPION.BASE
    authority = {
        name: getattr(original, name)
        for name in (
            "SCHEMA",
            "PYTHON",
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
            "_load_module",
            "_plan",
            "_service_candidates",
        )
    }
    champion_authority = {
        "control_main": control.main,
        "champion": control.CHAMPION,
        "original_v2": control.CHAMPION.ORIGINAL_V2,
        "periodic_v1": control.CHAMPION.V1,
        "zero": control.CHAMPION.ZERO,
    }
    monkeypatch.setattr(wrapper, "_load_control", lambda _root: control)
    configured = wrapper.configure(
        frozen_root=frozen_root,
        enable_hybrid=True,
    )
    assert configured is control
    base = configured.CHAMPION.BASE
    assert base.SEARCH_ARM == "progressive_adaptive_hybrid_64_600"
    assert base.SEARCH_WORKER == HERE / "search_worker.py"
    assert base.SEARCH_ADAPTER == HERE / "search_adapter.py"
    assert base.SEARCH_CANDIDATE == HERE / "candidate.py"
    for name, value in authority.items():
        assert getattr(base, name) is value
    assert configured.main is champion_authority["control_main"]
    assert configured.CHAMPION is champion_authority["champion"]
    assert configured.CHAMPION.ORIGINAL_V2 is champion_authority["original_v2"]
    assert configured.CHAMPION.V1 is champion_authority["periodic_v1"]
    assert configured.CHAMPION.ZERO is champion_authority["zero"]


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


def test_current_control_audit_and_s0_bind_candidate_and_entrypoint() -> None:
    candidate_sha = hashlib.sha256((HERE / "candidate.py").read_bytes()).hexdigest()
    entrypoint_sha = hashlib.sha256((HERE / "full_worker.py").read_bytes()).hexdigest()
    s0 = json.loads((HERE / "S0_EVIDENCE.json").read_text())
    audit = json.loads((HERE / "CONTROL_STACK_AUDIT.json").read_text())
    assert s0["candidate_sha256"] == candidate_sha
    assert audit["candidate_sha256"] == candidate_sha
    assert audit["entrypoint_sha256"] == entrypoint_sha
    assert audit["verdict"] == "PASS_EXACT_CONTROL_STACK_REBOUND"
    assert all(row["semantic_result_equal"] for row in audit["noop_runs"])
    assert audit["formal_screen_executed"] is False
    assert audit["scorer_used"] is False
    assert audit["benchmark_truth_used"] is False
