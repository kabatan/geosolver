from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path

import build_ordinary_binding_manifest as builder
import ordinary_proposal_binding as binding


def _descriptor(root: int = 3):
    return {
        "minimal_polynomial_high_to_low": [1, -root],
        "selected_real_root_index": 0,
        "isolating_interval": {
            "left": str(root - 1),
            "right": str(root + 1),
            "multiplicity": 1,
            "real_root_index": 0,
        },
        "proposal_relation_low_to_high": [-root, 1],
        "confirmation_relation_low_to_high": [-root, 1],
        "target_768": str(root),
        "target_1024": str(root),
    }


def _document(root: int = 3):
    return {
        "task": "solve",
        "variables": {"names": ["x"]},
        "construction": [],
        "constraints": [{"def": "x", "value": str(root)}],
        "guards": [],
        "bounds": [[-10, 10]],
        "answer": "x",
        "post_process": None,
    }


def _fixture(tmp_path: Path, monkeypatch, *, document=None, root=3):
    source_root = tmp_path / "sources"
    proposal_root = tmp_path / "proposals"
    source_root.mkdir()
    proposal_root.mkdir()
    monkeypatch.setattr(binding, "APPROVED_SOURCE_ROOT", source_root.resolve())
    monkeypatch.setattr(binding, "APPROVED_PROPOSAL_ROOT", proposal_root.resolve())
    source = source_root / "0000.json"
    source.write_text(
        json.dumps(document or _document(root), separators=(",", ":")),
        encoding="utf-8",
    )
    endpoint = [float(root)]
    endpoint_sha = binding.endpoint_float64_sha256(endpoint)
    attempt = {
        "status": "TARGET_AUTHORITY_READY",
        "authority_pass": True,
        "endpoint_float64_sha256": endpoint_sha,
        "descriptor": _descriptor(root),
        "case_family_truth_target_count_routing": False,
    }
    wrapper = {
        "schema_version": binding.PROPOSAL_SCHEMA,
        "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "endpoint_float64_sha256": endpoint_sha,
        "original_result_sha256": "a" * 64,
        "ordinary_attempt_sha256": binding.canonical_sha256(attempt),
        "ordinary_attempt": attempt,
        "truth_used": False,
        "case_family_target_count_routing": False,
    }
    proposal = proposal_root / "0000.json"
    proposal.write_bytes(binding.canonical_bytes(wrapper) + b"\n")
    row = {
        "source_rel": source.name,
        "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "endpoint_float64_bits_hex": binding.endpoint_bits_hex(endpoint),
        "endpoint_float64_sha256": endpoint_sha,
        "degree1_descriptor": {
            "minimal_polynomial_high_to_low": [1, -root],
            "selected_real_root_index": 0,
        },
        "proposal_result_rel": proposal.name,
        "proposal_sha256": hashlib.sha256(proposal.read_bytes()).hexdigest(),
    }
    return row, source_root, proposal_root, source, proposal


def _connect(row, source_root, proposal_root):
    return binding.connect(
        row,
        source_root=source_root,
        proposal_root=proposal_root,
        timeout_seconds=3.0,
    )


def test_complete_binding_returns_existing_boundary_descriptor_but_holds_release(
    tmp_path, monkeypatch
):
    row, source_root, proposal_root, _source, proposal = _fixture(tmp_path, monkeypatch)
    expected = json.loads(proposal.read_bytes())["ordinary_attempt"]["descriptor"]
    result = _connect(row, source_root, proposal_root)
    assert result["binding_ready"] is True
    assert result["authority_boundary_descriptor_ready"] is True
    assert result["authority_boundary_exact_descriptor"] == expected
    assert result["ordinary_descriptor_returned_without_rewrite"] is True
    assert result["ordinary_and_nra_exact_identity_match"] is True
    assert result["untouched_source_replay_pass"] is True
    assert result["untouched_target_link_pass"] is True
    assert result["authority_pass"] is False
    assert result["target_release"] is False


def test_source_endpoint_descriptor_and_proposal_tamper_fail_closed(
    tmp_path, monkeypatch
):
    row, source_root, proposal_root, source, proposal = _fixture(tmp_path, monkeypatch)
    variants = []
    changed = deepcopy(row)
    changed["source_sha256"] = "0" * 64
    variants.append(changed)
    changed = deepcopy(row)
    changed["endpoint_float64_bits_hex"][0] = "4008000000000001"
    variants.append(changed)
    changed = deepcopy(row)
    changed["degree1_descriptor"]["minimal_polynomial_high_to_low"] = [1, -4]
    variants.append(changed)
    changed = deepcopy(row)
    changed["proposal_sha256"] = "0" * 64
    variants.append(changed)
    for changed in variants:
        result = _connect(changed, source_root, proposal_root)
        assert result["binding_ready"] is False
        assert result["target_release"] is False
        assert "authority_boundary_exact_descriptor" not in result

    source.write_text(json.dumps({**_document(), "id": "forbidden"}), encoding="utf-8")
    changed = deepcopy(row)
    changed["source_sha256"] = hashlib.sha256(source.read_bytes()).hexdigest()
    assert _connect(changed, source_root, proposal_root)["binding_ready"] is False

    # Restore source, then alter the proposal while updating only its outer
    # file digest: the internally bound ordinary-attempt digest must reject.
    source.write_text(json.dumps(_document(), separators=(",", ":")), encoding="utf-8")
    document = json.loads(proposal.read_bytes())
    document["ordinary_attempt"]["descriptor"]["target_1024"] = "4"
    proposal.write_bytes(binding.canonical_bytes(document) + b"\n")
    changed = deepcopy(row)
    changed["proposal_sha256"] = hashlib.sha256(proposal.read_bytes()).hexdigest()
    assert _connect(changed, source_root, proposal_root)["binding_ready"] is False


def test_symlink_escape_is_rejected(tmp_path, monkeypatch):
    row, source_root, proposal_root, _source, proposal = _fixture(tmp_path, monkeypatch)
    outside = tmp_path / "outside.json"
    outside.write_bytes(proposal.read_bytes())
    escaped = proposal_root / "escaped.json"
    escaped.symlink_to(outside)
    row["proposal_result_rel"] = escaped.name
    row["proposal_sha256"] = hashlib.sha256(outside.read_bytes()).hexdigest()
    assert _connect(row, source_root, proposal_root)["binding_ready"] is False


def test_duplicate_ordinary_matches_are_rejected_by_builder_join():
    descriptor = _descriptor()
    endpoint_sha = "a" * 64
    attempt = {
        "status": "TARGET_AUTHORITY_READY",
        "authority_pass": True,
        "endpoint_float64_sha256": endpoint_sha,
        "descriptor": descriptor,
    }
    result = {"source_sha256": "b" * 64, "hp_attempts": [attempt, deepcopy(attempt)]}
    matches = builder._matching_attempts(
        result,
        source_sha256="b" * 64,
        endpoint_sha256=endpoint_sha,
        identity=((1, -3), 0),
    )
    assert len(matches) == 2  # main rejects anything other than exactly one


def test_multitarget_source_never_claims_completeness_or_releases(
    tmp_path, monkeypatch
):
    document = {
        "task": "solve",
        "variables": {"names": ["x"]},
        "construction": [],
        "constraints": [{"def": "x*x", "value": "1"}],
        "guards": [],
        "bounds": [[-2, 2]],
        "answer": "x",
        "post_process": None,
    }
    row, source_root, proposal_root, _source, _proposal = _fixture(
        tmp_path, monkeypatch, document=document, root=1
    )
    result = _connect(row, source_root, proposal_root)
    assert result["binding_ready"] is True
    assert result["target_set_completeness_claim"] is False
    assert result["authority_pass"] is False
    assert result["target_release"] is False
