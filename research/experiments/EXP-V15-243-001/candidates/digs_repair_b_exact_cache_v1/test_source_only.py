from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import time
from types import SimpleNamespace


HERE = Path(__file__).resolve().parent
REPAIR_PATH = HERE.parent / "diffusive_gibbs_repair_b_authority_v1/worker.py"


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def combo():
    return load("wave3_combo_test", HERE / "worker.py")


def repair():
    return load("wave3_repair_b_test", REPAIR_PATH)


def descriptor(identity: str):
    return {
        "minimal_polynomial_high_to_low": [1, -ord(identity[0])],
        "selected_real_root_index": 0,
        "identity": identity,
    }


class Boundary:
    @staticmethod
    def descriptor_identity(value):
        return value.get("identity") if isinstance(value, dict) else None


def fake_exact():
    exact = SimpleNamespace()
    exact.boundary = Boundary()
    exact_calls = {"count": 0}

    def ordinary(**kwargs):
        candidate = kwargs["candidate"]
        return {
            "status": "TARGET_AUTHORITY_READY",
            "authority_pass": True,
            "descriptor": descriptor(candidate.identity),
        }

    def exact_outer(**kwargs):
        exact_calls["count"] += 1
        ordinary_result = exact._ORDINARY_HP(**kwargs)
        candidate = kwargs["candidate"]
        if getattr(candidate, "fail_exact", False):
            return {
                "status": "EXACT_CONFIRMATION_REJECTED",
                "authority_pass": False,
                "descriptor": None,
            }
        return {
            "attempt_kind": "EXACT_CONFIRMATION_OF_ORDINARY_PROPOSAL",
            "status": "TARGET_AUTHORITY_READY",
            "authority_pass": True,
            "descriptor": ordinary_result["descriptor"],
            "ordinary_and_exact_descriptor_identity_match": True,
            "exact_coordinate_fallback": {
                "status": "TARGET_AUTHORITY_READY",
                "authority_pass": True,
            },
        }

    exact._ORDINARY_HP = ordinary
    exact._run_exact_outer = exact_outer
    exact._ordinary_ready = lambda value: value.get("authority_pass") is True
    exact.BASE = SimpleNamespace(
        _run_hp_candidate=exact_outer,
        _plan=lambda **kwargs: dict(kwargs),
    )
    return exact, exact_calls


def candidate(identity: str, *, fail_exact: bool = False):
    return SimpleNamespace(
        identity=identity,
        fail_exact=fail_exact,
        endpoint_sha256=identity * 8,
        residual_inf=0.0,
        provisional_target=0.0,
        cluster_ordinal=0,
        cluster_rank=0,
    )


def found(results):
    return {
        result["descriptor"]["identity"]
        for result in results
        if result.get("authority_pass") is True
    }


def test_duplicate_heavy_preserves_exact_mapping_and_saves_confirmations():
    worker = combo()
    exact, calls = fake_exact()
    stats = worker.install_cache(exact)
    sequence = [candidate("a") for _ in range(12)] + [candidate("b") for _ in range(8)]
    results = [exact.BASE._run_hp_candidate(candidate=item) for item in sequence]
    assert found(results) == {"a", "b"}
    assert calls["count"] == 2
    assert stats["cache_hits"] == 18
    assert sum(result.get("confirmed_identity_cache_hit") is True for result in results) == 18


def test_unique_is_neutral():
    worker = combo()
    exact, calls = fake_exact()
    stats = worker.install_cache(exact)
    sequence = [candidate(value) for value in "abcdefgh"]
    results = [exact.BASE._run_hp_candidate(candidate=item) for item in sequence]
    assert found(results) == set("abcdefgh")
    assert calls["count"] == len(sequence)
    assert stats["cache_hits"] == 0


def test_failed_first_confirmation_is_not_cached():
    worker = combo()
    exact, calls = fake_exact()
    stats = worker.install_cache(exact)
    sequence = [candidate("a", fail_exact=True), candidate("a"), candidate("a")]
    results = [exact.BASE._run_hp_candidate(candidate=item) for item in sequence]
    assert results[0]["authority_pass"] is False
    assert results[1]["authority_pass"] is True
    assert results[2]["confirmed_identity_cache_hit"] is True
    assert calls["count"] == 2
    assert stats["cache_hits"] == 1


def test_repair_b_zero_surplus_returns_no_side_work(tmp_path):
    module = repair()
    source_sha = "a" * 64
    (tmp_path / "search.json").write_text(json.dumps({
        "completed": True,
        "source_sha256": source_sha,
        "source_bytes_unchanged": True,
        "truth_used": False,
        "work": {"callbacks": 10},
    }))
    (tmp_path / "RESULT.json").write_text("{}")
    base = SimpleNamespace(
        _geotarget_exact_outer_installed=True,
        PROCESS_STARTED=time.monotonic() - 30.0,
    )
    arguments = SimpleNamespace(
        total_seconds=30.0,
        output=tmp_path,
        source_sha256=source_sha,
        aggregate_callback_cap=20,
        starts=4,
        callbacks_per_start=5,
    )
    attempts, telemetry = module._run_side(base, arguments, {})
    assert attempts == []
    assert telemetry["status"] == "ZERO_ADMISSIBLE_SURPLUS"


def exact_attempt(identity: str):
    return {
        "attempt_kind": "EXACT_CONFIRMATION_OF_ORDINARY_PROPOSAL",
        "status": "TARGET_AUTHORITY_READY",
        "authority_pass": True,
        "descriptor": descriptor(identity),
        "ordinary_and_exact_descriptor_identity_match": True,
        "exact_coordinate_fallback": {
            "status": "TARGET_AUTHORITY_READY",
            "authority_pass": True,
        },
    }


def baseline():
    values = [descriptor("a")]
    return {
        "distinct_exact_targets": values,
        "distinct_exact_target_descriptors": values,
        "distinct_exact_target_count": 1,
        "hp_attempts": [{"baseline": True}],
        "hp_attempt_count": 1,
    }


def test_side_exact_union_preserves_baseline_descriptor_and_attempt_prefixes():
    module = repair()
    original = baseline()
    merged = module.merge_frozen_baseline(original, [exact_attempt("b")])
    assert merged["distinct_exact_target_descriptors"][0] == descriptor("a")
    assert merged["distinct_exact_target_descriptors"][1] == descriptor("b")
    assert merged["hp_attempts"][0] == {"baseline": True}
    assert merged["hp_attempts"][1] == exact_attempt("b")
    assert merged["distinct_exact_target_count"] == 2
    assert merged["hp_attempt_count"] == 2


def test_cache_decorated_side_exact_union_accepts_new_and_rejects_duplicate():
    worker = combo()
    exact, _calls = fake_exact()
    worker.install_cache(exact)
    baseline_proof = exact.BASE._run_hp_candidate(candidate=candidate("a"))
    duplicate = exact.BASE._run_hp_candidate(candidate=candidate("a"))
    side_proof = exact.BASE._run_hp_candidate(candidate=candidate("b"))
    assert baseline_proof["authority_pass"] is True
    assert duplicate["confirmed_identity_cache_hit"] is True
    module = repair()
    original = baseline()
    merged = module.merge_frozen_baseline(original, [duplicate, side_proof])
    assert [item["identity"] for item in merged["distinct_exact_target_descriptors"]] == [
        "a", "b"
    ]
    assert merged["hp_attempt_count"] == 2


def test_side_exception_retains_exact_baseline_bytes(tmp_path):
    module = repair()
    result_path = tmp_path / "RESULT.json"

    def atomic(path, document):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(document, sort_keys=True, separators=(",", ":")))

    base = SimpleNamespace(atomic_write_json=atomic, _plan=lambda **kwargs: dict(kwargs))
    original_side = module._run_side
    module._run_side = lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("boom"))
    try:
        module.install_result_seam(base, SimpleNamespace())
        document = baseline()
        expected = json.dumps(document, sort_keys=True, separators=(",", ":")).encode()
        base.atomic_write_json(result_path, document)
        assert result_path.read_bytes() == expected
        assert (tmp_path / "FROZEN_BASELINE_RESULT.json").read_bytes() == expected
    finally:
        module._run_side = original_side


def test_reference_cache_files_are_byte_identical_and_hash_bound():
    worker = combo()
    for path, expected in worker.EXPECTED.items():
        assert hashlib.sha256(path.read_bytes()).hexdigest() == expected
