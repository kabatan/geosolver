from __future__ import annotations

import importlib.util
from pathlib import Path
import sys


HERE = Path(__file__).resolve().parent
WORKER_PATH = HERE / "champion_v2_poc_cross_endpoint_hp_preloaded.py"


def _load():
    name = "geotarget_test_champion_v2_poc_cross_endpoint_hp_preloaded"
    specification = importlib.util.spec_from_file_location(name, WORKER_PATH)
    assert specification is not None and specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    sys.modules[name] = module
    specification.loader.exec_module(module)
    return module


def test_composition_uses_registered_fifo_policy_and_preserves_current_routes():
    worker = _load()
    assert worker.DENSE_BUILD_FACTOR in worker.SCHEDULER.ALLOWED_DENSE_BUILD_FACTORS
    assert worker.DENSE_BUILD_FACTOR == 8
    assert worker.MAXIMUM_DISPATCHES_PER_ENDPOINT == 4
    assert worker.BASE._service_candidates is worker._service_candidates
    assert worker.CHAMPION.CHAMPION.ZERO is not None


def test_safe_endpoint_adapter_is_source_bound_and_keeps_discoveries():
    worker = _load()

    class Candidate:
        semantic_verified = True
        endpoint = (1.25, -2.5)
        residual_inf = 1.0e-9

    source_sha256 = "a" * 64
    rows = worker._safe_endpoints(source_sha256, [Candidate(), Candidate()])
    assert [row.discovery_ordinal for row in rows] == [0, 1]
    assert all(row.safety.source_sha256 == source_sha256 for row in rows)
    assert rows[0].endpoint_sha256 == rows[1].endpoint_sha256
    assert rows[0].safety.certificate_sha256 != rows[1].safety.certificate_sha256
