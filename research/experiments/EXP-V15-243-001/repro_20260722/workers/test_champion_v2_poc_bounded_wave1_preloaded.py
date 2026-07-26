from __future__ import annotations

import importlib.util
from pathlib import Path
import sys


HERE = Path(__file__).resolve().parent
WORKER = HERE / "champion_v2_poc_bounded_wave1_preloaded.py"


def _load():
    name = "test_champion_v2_poc_bounded_wave1_preloaded"
    specification = importlib.util.spec_from_file_location(name, WORKER)
    assert specification is not None and specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    sys.modules[name] = module
    specification.loader.exec_module(module)
    return module


def test_only_search_proposal_seam_is_rebound() -> None:
    worker = _load()
    manifest = worker.active_manifest()

    assert worker.BASE is worker.POC.BASE
    assert worker.ZERO is worker.POC.ZERO
    assert worker.BASE.SEARCH_WORKER == worker.SEARCH_WORKER
    assert worker.BASE.SEARCH_ADAPTER == worker.SEARCH_ADAPTER
    assert worker.BASE.SEARCH_CANDIDATE == worker.SEARCH_CANDIDATE
    assert worker.BASE.SEARCH_ARM == worker.SEARCH_ARM
    assert Path(worker.BASE.HP_BRIDGE).resolve() == worker._HP_BRIDGE
    assert manifest["truth_or_case_routing"] is False
    assert manifest["changed_seams"] == [
        "SEARCH_WORKER",
        "SEARCH_ADAPTER",
        "SEARCH_CANDIDATE",
        "SEARCH_ARM",
    ]
