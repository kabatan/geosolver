"""Archived product-side regression tests for the restoration experiment.

These tests were intentionally removed from the product test suite when the
trace-only restoration candidates were moved to the ``experiment`` branch.
They are retained here as research evidence and require a checkout that still
materializes the historical frozen runtime paths.
"""

import hashlib
import importlib.util
import sys
import time
from pathlib import Path

import numpy as np

from geotarget.engine import engine_root


def _load_path_module(name: str, path: Path):
    specification = importlib.util.spec_from_file_location(name, path)
    assert specification is not None and specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    sys.modules[name] = module
    specification.loader.exec_module(module)
    return module


def test_restoration_rescue_transitive_dependencies_are_hash_bound() -> None:
    experiment = engine_root() / "runtime/solver/research/experiments/EXP-REAL61-008"
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
        "geotarget_archived_restoration_rescue_import",
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
        "geotarget_archived_restoration_rescue_execution",
        experiment / "hp_failure_restoration_rescue_v6/candidate.py",
    )
    source_runtime = _load_path_module(
        "geotarget_archived_restoration_source_runtime",
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
