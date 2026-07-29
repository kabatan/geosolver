import hashlib
import importlib.util
import os
import sys
import time
from pathlib import Path

import numpy as np

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


def _load_path_module(name: str, path: Path):
    specification = importlib.util.spec_from_file_location(name, path)
    assert specification is not None and specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    sys.modules[name] = module
    specification.loader.exec_module(module)
    return module


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


def test_restoration_rescue_transitive_dependencies_are_hash_bound() -> None:
    experiment = (
        engine_root()
        / "runtime/solver/research/experiments/EXP-REAL61-008"
    )
    expected = {
        "dev41_row_restoration_v4/candidate.py": (
            "4a9eacaa3f592ea78992c174a4c37e7a0562273655ca9ba72c34575ee599485c"
        ),
        "dev41_restoration_filter_v3/acceptance_corrective/candidate.py": (
            "a2279ffa1b3ee31a6fbe501e7bbcb1d00c211bc43bdc76bbdfa83a2bcaa49b72"
        ),
        "dev41_restoration_filter_v3/candidate.py": (
            "61ade7133531d6a74675896deea2e1ca8cd833238005595b50ac044cf86cf29d"
        ),
    }

    for relative, digest in expected.items():
        assert hashlib.sha256((experiment / relative).read_bytes()).hexdigest() == digest

    rescue = _load_path_module(
        "geotarget_test_restoration_rescue_import",
        experiment / "hp_failure_restoration_rescue_v6/candidate.py",
    )
    assert expected["dev41_row_restoration_v4/candidate.py"] == rescue.RESTORATION_SHA256
    assert rescue.RESTORATION.CORRECTIVE.BASE.VECTOR_CORE_SHA256 == (
        "021d90c5c46a8308b71cb04db1a6ae30577f018bc21c7556b0d372e7a0335dee"
    )


def test_restoration_rescue_executes_the_frozen_kernel_on_a_synthetic_problem() -> None:
    runtime_root = engine_root() / "runtime"
    sys.path.insert(0, str(runtime_root / "geosolver/src"))
    experiment = runtime_root / "solver/research/experiments/EXP-REAL61-008"
    rescue = _load_path_module(
        "geotarget_test_restoration_rescue_execution",
        experiment / "hp_failure_restoration_rescue_v6/candidate.py",
    )
    source_runtime = _load_path_module(
        "geotarget_test_restoration_source_runtime",
        experiment / "source_only/runtime.py",
    )
    document = {
        "task": "solve",
        "id": "synthetic-restoration-regression",
        "variables": {"names": ["x"]},
        "construction": [
            {"name": "O", "expr": "Point(0, 0)"},
            {"name": "P", "expr": "Point(x, 0)"},
        ],
        "constraints": [{"def": "Distance(O, P)", "value": 1}],
        "guards": [],
        "answer": "x",
        "post_process": "",
    }
    base_case, budget, _evaluator = source_runtime.build_source_case(
        document,
        callback_cap=50,
        deadline=time.monotonic() + 10.0,
    )

    outcome = rescue.run_restoration_rescue(
        base_case=base_case,
        budget=budget,
        document=document,
        failed_endpoint=[0.0],
        leftover_callback_cap=10,
        deadline_monotonic=time.monotonic() + 10.0,
    )

    assert outcome.statuses.get("safe_root", 0) >= 1
    assert outcome.callbacks <= 10
    assert any(np.isclose(abs(float(endpoint[0])), 1.0) for endpoint in outcome.endpoints)


def test_doctor_reports_locked_runtime() -> None:
    report = diagnose()
    assert report["ok"]
    assert report["engine_hash"] == ENGINE_HASH
    assert report["nemo_locked"] is True


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
            "descriptor": {
                "minimal_polynomial_high_to_low": [1, -40],
                "selected_real_root_index": 0,
                "isolating_interval": {"left": "39.9", "right": "40.1"},
                "target_1024": "40.000",
                "authority_kind": "MINPOLY_REAL_ROOT_ISOLATOR",
            }
        }
    )

    assert answers[0].isolating_interval == ["39.9", "40.1"]
    assert answers[0].exact_authority_kind == "MINPOLY_REAL_ROOT_ISOLATOR"


def test_exact_rational_root_is_a_display_decimal_fallback() -> None:
    answers = extract_answers(
        {
            "minimal_polynomial_high_to_low": [1, -5],
            "selected_real_root_index": 0,
            "isolating_interval": {
                "left": "4.9",
                "right": "5.1",
                "exact_rational_root": "5",
            },
        }
    )

    assert answers[0].decimal == "5"
