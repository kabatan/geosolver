from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
from types import SimpleNamespace


HERE = Path(__file__).resolve().parent


def load():
    spec = importlib.util.spec_from_file_location("repair_b_worker_test", HERE / "worker.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def descriptor(n: int):
    return {
        "minimal_polynomial_high_to_low": [1, -n],
        "selected_real_root_index": 0,
        "isolating_interval": {"lower": str(n), "upper": str(n)},
    }


def attempt(n: int):
    return {
        "attempt_kind": "EXACT_CONFIRMATION_OF_ORDINARY_PROPOSAL",
        "status": "TARGET_AUTHORITY_READY",
        "authority_pass": True,
        "descriptor": descriptor(n),
        "ordinary_and_exact_descriptor_identity_match": True,
        "exact_coordinate_fallback": {
            "status": "TARGET_AUTHORITY_READY",
            "authority_pass": True,
        },
    }


def payload_sha(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def baseline():
    values = [descriptor(2), descriptor(3)]
    return {
        "distinct_exact_targets": copy.deepcopy(values),
        "distinct_exact_target_descriptors": copy.deepcopy(values),
        "distinct_exact_target_count": 2,
        "hp_attempts": [{"baseline": 0}, {"baseline": 1}],
        "hp_attempt_count": 2,
        "opaque_baseline_payload": {"order": [7, 1, 9]},
    }


def test_zero_surplus_identity_object():
    worker = load()
    original = baseline()
    assert worker.merge_frozen_baseline(original, []) is original
    assert worker.merge_frozen_baseline(original, [attempt(2)]) is original


def test_side_union_preserves_baseline_descriptor_payload_sha_and_order():
    worker = load()
    original = baseline()
    before = copy.deepcopy(original)
    before_sha = payload_sha(before["distinct_exact_target_descriptors"])
    merged = worker.merge_frozen_baseline(original, [attempt(5)])
    prefix = merged["distinct_exact_target_descriptors"][:2]
    assert prefix == before["distinct_exact_target_descriptors"]
    assert payload_sha(prefix) == before_sha
    assert merged["opaque_baseline_payload"] == before["opaque_baseline_payload"]
    assert merged["distinct_exact_target_descriptors"][2] == descriptor(5)
    assert merged["distinct_exact_target_count"] == 3
    assert merged["hp_attempts"][:2] == before["hp_attempts"]
    assert merged["hp_attempts"][2] == attempt(5)
    assert merged["hp_attempt_count"] == 3
    assert original == before


def test_side_union_handles_baseline_alias_used_by_real_worker():
    worker = load()
    values = [descriptor(2)]
    original = {
        "distinct_exact_targets": values,
        "distinct_exact_target_descriptors": values,
        "distinct_exact_target_count": 1,
        "hp_attempts": [{"baseline": 0}],
        "hp_attempt_count": 1,
    }
    merged = worker.merge_frozen_baseline(original, [attempt(5)])
    assert merged["distinct_exact_targets"] is merged["distinct_exact_target_descriptors"]
    assert merged["distinct_exact_target_count"] == 2
    assert merged["distinct_exact_targets"] == [descriptor(2), descriptor(5)]


def test_unproven_side_descriptor_cannot_release():
    worker = load()
    original = baseline()
    malformed = attempt(5)
    malformed["exact_coordinate_fallback"]["authority_pass"] = False
    assert worker.merge_frozen_baseline(original, [malformed]) is original


def test_exception_fallback_contract_is_fail_closed_in_source():
    source = (HERE / "worker.py").read_text()
    seam = source[source.index("    def write(path:"):]
    assert "original_write(path, document)" in seam
    assert seam.index("original_write(path, document)") < seam.index("_run_side(")
    assert "SIDE_EXCEPTION_BASELINE_RETAINED" in source
    assert "path.write_bytes(frozen_bytes)" not in source


def test_exception_fallback_preserves_exact_baseline_bytes(tmp_path):
    worker = load()
    result_path = tmp_path / "RESULT.json"

    def atomic(path, document):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(document, sort_keys=True, separators=(",", ":")))

    base = SimpleNamespace(
        atomic_write_json=atomic,
        _plan=lambda **kwargs: dict(kwargs),
    )
    arguments = SimpleNamespace()
    original_side = worker._run_side
    worker._run_side = lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("boom"))
    try:
        worker.install_result_seam(base, arguments)
        document = baseline()
        expected = json.dumps(document, sort_keys=True, separators=(",", ":")).encode()
        base.atomic_write_json(result_path, document)
        assert result_path.read_bytes() == expected
        assert (tmp_path / "FROZEN_BASELINE_RESULT.json").read_bytes() == expected
        telemetry = json.loads((tmp_path / "REPAIR_B_TELEMETRY.json").read_text())
        assert telemetry["status"] == "SIDE_EXCEPTION_BASELINE_RETAINED"
    finally:
        worker._run_side = original_side


def test_exact_outer_and_hp_binding_are_pinned_in_plan_closure():
    worker = load()
    assert worker.EXPECTED[worker.EXACT_OUTER] == "05650c1016f3974c0f74845037c76604eb38f2f4a337cc700721f0e148d9d3f7"
    assert worker.EXPECTED[worker.HP_SCHEDULER] == "5453a30c46d3050c0520a6492f149595bf93d4f2794e3e1fa86d7d60c2365702"
    source = (HERE / "worker.py").read_text()
    assert "ordinary_and_exact_descriptor_identity_match" in source
    assert "EXACT_CONFIRMATION_OF_ORDINARY_PROPOSAL" in source
    assert "GEOTARGET_EXACT_OUTER_MODE\"] = \"CONFIRM_ALL_AUTHORITIES\"" in source
