from __future__ import annotations

from contextlib import contextmanager
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import categorical_fallback_worker as candidate


def source(tmp_path: Path, *, construction=None) -> tuple[Path, str]:
    document = {
        "id": "ignored-identity",
        "family": "ignored-family",
        "task": "solve",
        "variables": {"names": ["x", "y"]},
        "construction": construction
        or [
            {"name": "P", "expr": "Point(x,y)"},
            {"name": "C", "expr": "Point(1,2)"},
            {"name": "R", "expr": "Reflect(P,C)"},
        ],
        "constraints": [],
        "guards": [],
        "answer": "x",
        "post_process": "",
    }
    payload = json.dumps(document, sort_keys=True, separators=(",", ":")).encode()
    path = tmp_path / "source.json"
    path.write_bytes(payload)
    return path, hashlib.sha256(payload).hexdigest()


def endpoint_sha(endpoint):
    return candidate._endpoint_sha256(endpoint)


def record(*, ready=True, sector=False):
    exact = {
        "typed_semantic_equal_repair": sector,
        "sector_certified_integer_angle_relation": sector,
    }
    return {
        "schema_version": candidate.SCHEMA,
        "completed": True,
        "status": (
            "EXACT_COORDINATE_TARGET_AUTHORITY_READY"
            if ready
            else "EXACT_COORDINATE_FALLBACK_REJECTED"
        ),
        "authority_pass": ready,
        "descriptor": {
            "minimal_polynomial_high_to_low": [1, -2],
            "selected_real_root_index": 0,
        }
        if ready
        else None,
        "exact_coordinate_authority": exact,
        "target_set_completeness_claim": False,
    }


def install_worker(
    monkeypatch,
    terminal,
    *,
    qreflect=False,
    sector_angle=False,
    ready=True,
    calls=None,
):
    monkeypatch.setattr(candidate, "verify_frozen_dependencies", lambda: {})
    monkeypatch.setattr(candidate, "_authority_ready", lambda *args, **kwargs: ready)
    state = {"qreflect": qreflect, "sector_angle": sector_angle}

    class Worker:
        @staticmethod
        def run_fallback(**kwargs):
            if calls is not None:
                calls.append(kwargs)
            return terminal

    @contextmanager
    def installed():
        yield Worker, state

    monkeypatch.setattr(candidate, "_installed_union_worker", installed)


def run(
    tmp_path,
    monkeypatch,
    terminal,
    *,
    qreflect=False,
    sector_angle=False,
    ready=True,
    timeout=20.0,
):
    path, digest = source(tmp_path)
    calls = []
    install_worker(
        monkeypatch,
        terminal,
        qreflect=qreflect,
        sector_angle=sector_angle,
        ready=ready,
        calls=calls,
    )
    result = candidate.run_portfolio(
        source=path,
        source_sha256=digest,
        endpoint=[0.0, 0.0],
        endpoint_sha256=endpoint_sha([0.0, 0.0]),
        timeout_seconds=timeout,
    )
    return result, calls


def test_noncategorical_terminal_is_identity_preserving(tmp_path, monkeypatch):
    terminal = record()
    result, calls = run(tmp_path, monkeypatch, terminal)
    assert result is terminal
    assert "categorical_exact_coordinate_portfolio" not in result
    assert calls[0]["timeout_seconds"] == 20.0


def test_rejection_is_identity_preserving_even_if_dispatch_flag_is_set(
    tmp_path, monkeypatch
):
    terminal = record(ready=False)
    result, _calls = run(
        tmp_path, monkeypatch, terminal, qreflect=True, ready=False
    )
    assert result is terminal
    assert "categorical_exact_coordinate_portfolio" not in result


def test_qreflect_requires_actual_successful_exact_dispatch(tmp_path, monkeypatch):
    terminal = record()
    result, calls = run(tmp_path, monkeypatch, terminal, qreflect=True)
    assert result is not terminal
    portfolio = result["categorical_exact_coordinate_portfolio"]
    assert portfolio["activated_routes"] == ["qreflect"]
    assert portfolio["actual_exact_dispatch_activation"] is True
    assert portfolio["single_numeric_refinement"] is True
    assert portfolio["target_set_completeness_claim"] is False
    assert calls[0]["timeout_seconds"] == 20.0


def test_sector_activation_comes_from_captured_raw_replay(tmp_path, monkeypatch):
    # The sector connector annotates the raw QQBar replay. The frozen exact
    # candidate intentionally does not copy those non-authority diagnostics
    # into its final exact terminal, so activation comes from captured state.
    terminal = record(sector=False)
    result, _calls = run(
        tmp_path, monkeypatch, terminal, sector_angle=True
    )
    portfolio = result["categorical_exact_coordinate_portfolio"]
    assert portfolio["activated_routes"] == ["sector_angle"]
    assert portfolio["sector_internal_generic_baseline_first"] is True
    assert portfolio["sector_internal_baseline_budget_fraction"] == 0.75
    assert portfolio["sector_internal_side_budget_fraction_maximum"] == 0.25


def test_sector_negative_flag_does_not_claim_activation(tmp_path, monkeypatch):
    terminal = record(sector=True)
    result, _calls = run(tmp_path, monkeypatch, terminal)
    assert result is terminal


def test_dual_exact_activation_is_reported_without_budget_split(tmp_path, monkeypatch):
    terminal = record(sector=False)
    result, calls = run(
        tmp_path,
        monkeypatch,
        terminal,
        qreflect=True,
        sector_angle=True,
        timeout=1.6,
    )
    portfolio = result["categorical_exact_coordinate_portfolio"]
    assert portfolio["activated_routes"] == ["qreflect", "sector_angle"]
    assert calls[0]["timeout_seconds"] == 1.6


def test_capture_reads_both_activation_bits_from_raw_replay():
    class Exact:
        @staticmethod
        def _run_qqbar(job, *, timeout_seconds):
            return {
                "status": "EXACT_REPLAY_ACCEPTED",
                "qreflect_point_point_dispatch_activated": True,
                "typed_semantic_equal_repair": True,
                "sector_certified_integer_angle_relation": True,
            }

    module = SimpleNamespace(exact_candidate=Exact)
    state = candidate._install_activation_capture(module)
    replay = module.exact_candidate._run_qqbar({}, timeout_seconds=1.0)
    assert replay["status"] == "EXACT_REPLAY_ACCEPTED"
    assert state == {"qreflect": True, "sector_angle": True}


def test_union_source_is_exact_one_opcode_superset_plus_ledger():
    sector = candidate.SECTOR_QQBAR.read_text(encoding="utf-8")
    reference = candidate.QREFLECT_REFERENCE_QQBAR.read_text(encoding="utf-8")
    union = candidate._union_qqbar_source()
    assert sector.replace(
        candidate._LINE_REFLECT,
        candidate._LINE_REFLECT + candidate._POINT_REFLECT,
    ) == reference
    assert candidate._LINE_REFLECT in union
    assert union.count("function qreflect(value::QPoint, center::QPoint)") == 1
    assert union.count("GEOTARGET_QREFLECT_POINT_POINT_ACTIVATED[] = true") == 1
    assert union.count('"qreflect_point_point_dispatch_activated"') == 1


def test_descriptor_identity_is_primitive_and_sign_normalized():
    first = {
        "minimal_polynomial_high_to_low": [-2, 4],
        "selected_real_root_index": 0,
    }
    second = {
        "minimal_polynomial_high_to_low": [1, -2],
        "selected_real_root_index": 0,
    }
    assert candidate._descriptor_identity(first) == candidate._descriptor_identity(second)
    assert candidate._descriptor_identity(first) == ((1, -2), 0)


def test_source_contract_rejects_truth_material(tmp_path):
    path, _digest = source(tmp_path)
    document = json.loads(path.read_text(encoding="utf-8"))
    document["known_target"] = "2"
    payload = json.dumps(document, sort_keys=True, separators=(",", ":")).encode()
    path.write_bytes(payload)
    digest = hashlib.sha256(payload).hexdigest()
    try:
        candidate._source_document(path, digest)
    except candidate.PortfolioFailure:
        pass
    else:
        raise AssertionError("truth-bearing source was accepted")
