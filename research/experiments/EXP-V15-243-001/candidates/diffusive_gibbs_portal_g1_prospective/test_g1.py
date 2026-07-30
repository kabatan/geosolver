from __future__ import annotations

import importlib.util
from pathlib import Path
import sys


HERE = Path(__file__).resolve().parent


def _load():
    name = "test_diffusive_gibbs_prospective_g1"
    specification = importlib.util.spec_from_file_location(name, HERE / "run_g1.py")
    assert specification is not None and specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    sys.modules[name] = module
    specification.loader.exec_module(module)
    return module


def test_small_prospective_contract() -> None:
    result = _load().execute(instances=1, seeds=1)
    assert result["candidate_bytes_changed_from_g0"] is False
    assert len(result["families"]) == 5
    assert result["incumbent_lane_fraction"] == 0.75
    assert result["byte_identical_insurance_mismatch"] == 0
    assert result["work_mismatch"] == 0
    assert result["productive_callback_ratio"] <= 1.10
    assert result["loss"] == 0
    assert result["false_extra"] == 0
    assert result["metamorphic_pass"] == result["metamorphic_total"]
    assert result["candidate_receives_case_family_truth_target_outcome"] is False
