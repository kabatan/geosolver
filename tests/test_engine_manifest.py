import os
import subprocess
from pathlib import Path

from geotarget.doctor import diagnose
from geotarget.engine import (
    ENGINE_HASH,
    FROZEN_THREAD_ENVIRONMENT,
    engine_root,
    evaluator_execution_metadata,
    extract_answers,
    optimized_engine_hash,
    verify_engine,
)


def test_evaluator_metadata_reports_structural_gate_without_identity_routing() -> None:
    enabled = evaluator_execution_metadata(
        {
            "compiled_evaluator": {
                "enabled": True,
                "case_specific_routing": False,
                "support_key_sha256": "a" * 64,
            }
        },
        reference=False,
    )
    assert enabled["typed_kernel_enabled"] is True
    assert enabled["evaluator_mode"] == "typed_compiled_whole_problem"
    assert enabled["compiled_evaluator"]["case_specific_routing"] is False

    fallback = evaluator_execution_metadata(
        {
            "compiled_evaluator": {
                "enabled": False,
                "fallback_reason": "unsupported structural opcode",
                "fused_evaluation": {"enabled": True},
            }
        },
        reference=False,
    )
    assert fallback["typed_kernel_enabled"] is False
    assert fallback["fused_evaluation_enabled"] is True
    assert fallback["evaluator_mode"] == "fused_reference_semantics"
    assert fallback["typed_kernel_gate"] == "bitwise_equivalent_callback_fusion"

    reference = evaluator_execution_metadata({}, reference=True)
    assert reference["evaluator_mode"] == "frozen_reference"
    assert reference["typed_kernel_enabled"] is False


def test_frozen_product_manifest_matches_every_engine_file() -> None:
    assert verify_engine() == []


def test_deployment_qualification_policy_is_not_part_of_engine_identity(
    monkeypatch,
) -> None:
    original_read_bytes = Path.read_bytes

    def guarded_read_bytes(path: Path) -> bytes:
        if path.name in {"qualification.py", "qualification.json"}:
            raise AssertionError("deployment policy was read while hashing the engine")
        return original_read_bytes(path)

    monkeypatch.setattr(Path, "read_bytes", guarded_read_bytes)
    assert len(optimized_engine_hash()) == 64


def test_doctor_reports_locked_runtime() -> None:
    report = diagnose()
    assert report["ok"]
    assert report["engine_hash"] == ENGINE_HASH
    assert report["nemo_locked"] is True
    assert (
        report["optimized_qualification"]["report_summary"]["qualified_engine_hash"]
        == optimized_engine_hash()
    )


def test_doctor_reports_julia_probe_failure(monkeypatch) -> None:
    monkeypatch.setattr("geotarget.doctor.shutil.which", lambda _name: "/missing/julia")

    def fail_probe(*_args, **_kwargs):
        raise subprocess.TimeoutExpired(cmd="julia --version", timeout=10)

    monkeypatch.setattr("geotarget.doctor.subprocess.run", fail_probe)
    report = diagnose()

    assert report["julia"] is None
    assert report["ok"] is False
    assert any("Julia version check failed" in error for error in report["errors"])


def test_frozen_subprocess_python_launcher_is_executable() -> None:
    launcher = engine_root() / "runtime/solver/python/.venv/bin/python"
    assert launcher.is_file()
    assert os.access(Path(launcher), os.X_OK)


def test_reference_runtime_freezes_native_thread_environment() -> None:
    expected = {
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONHASHSEED": "0",
        "OMP_NUM_THREADS": "1",
        "OMP_THREAD_LIMIT": "1",
        "OPENBLAS_NUM_THREADS": "1",
        "MKL_NUM_THREADS": "1",
        "BLIS_NUM_THREADS": "1",
        "GOTO_NUM_THREADS": "1",
        "VECLIB_MAXIMUM_THREADS": "1",
        "NUMEXPR_NUM_THREADS": "1",
        "JULIA_NUM_THREADS": "1",
        "JULIA_NUM_PRECOMPILE_TASKS": "1",
        "JULIA_PKG_PRECOMPILE_AUTO": "0",
        "RAYON_NUM_THREADS": "1",
        "CMAKE_BUILD_PARALLEL_LEVEL": "1",
        "MAKEFLAGS": "-j1",
        "MALLOC_ARENA_MAX": "2",
        "GEOTARGET_GLOBAL_RSS_RESERVATION_BYTES": str(8 * 1024**3),
    }
    assert expected == FROZEN_THREAD_ENVIRONMENT


def test_exact_descriptor_mapping_is_exposed_without_losing_its_interval() -> None:
    answers = extract_answers(
        {
            "distinct_exact_target_descriptors": [{
                "minimal_polynomial_high_to_low": [1, -40],
                "selected_real_root_index": 0,
                "isolating_interval": {"left": "39.9", "right": "40.1"},
                "target_1024": "40.000",
                "authority_kind": "MINPOLY_REAL_ROOT_ISOLATOR",
            }]
        }
    )

    assert answers[0].isolating_interval == ["39.9", "40.1"]
    assert answers[0].exact_authority_kind == "MINPOLY_REAL_ROOT_ISOLATOR"


def test_exact_rational_root_is_a_display_decimal_fallback() -> None:
    answers = extract_answers(
        {
            "distinct_exact_target_descriptors": [{
                "minimal_polynomial_high_to_low": [1, -5],
                "selected_real_root_index": 0,
                "isolating_interval": {
                    "left": "4.9",
                    "right": "5.1",
                    "exact_rational_root": "5",
                },
            }],
        }
    )

    assert answers[0].decimal == "5"


def test_rejected_attempt_minpoly_is_never_exposed_as_an_answer() -> None:
    raw = {
        "distinct_exact_target_descriptors": [],
        "hp_attempts": [
            {
                "authority_pass": False,
                "final_result": {
                    "target_authority": {
                        "minimal_polynomial_high_to_low": [1, -999],
                        "selected_real_root_index": 0,
                        "target_1024": "999",
                    }
                },
            }
        ],
    }

    assert extract_answers(raw) == []


def test_only_promoted_descriptor_is_exposed_when_rejected_attempts_remain() -> None:
    accepted = {
        "minimal_polynomial_high_to_low": [1, -5],
        "selected_real_root_index": 0,
        "target_1024": "5",
    }
    raw = {
        "distinct_exact_target_descriptors": [accepted],
        "hp_attempts": [
            {
                "authority_pass": False,
                "descriptor": {
                    "minimal_polynomial_high_to_low": [1, -999],
                    "selected_real_root_index": 0,
                    "target_1024": "999",
                },
            }
        ],
    }

    answers = extract_answers(raw)

    assert len(answers) == 1
    assert answers[0].minimal_polynomial_high_to_low == [1, -5]
