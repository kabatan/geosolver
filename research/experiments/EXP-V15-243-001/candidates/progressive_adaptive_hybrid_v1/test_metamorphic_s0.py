from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys


HERE = Path(__file__).resolve().parent


def _load():
    name = "test_progressive_adaptive_hybrid_metamorphic_s0"
    path = HERE / "metamorphic_s0.py"
    specification = importlib.util.spec_from_file_location(name, path)
    assert specification is not None and specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    sys.modules[name] = module
    specification.loader.exec_module(module)
    return module


S0 = _load()


def test_equivalent_representations_preserve_hybrid_decisions() -> None:
    profile = S0.CANDIDATE.PROFILE
    _base, expected = S0.BASE_S0.equivalent_run(profile, "base")
    for variant in (
        "variable_permutation",
        "residual_permutation",
        "affine_scale",
    ):
        _result, observed = S0.BASE_S0.equivalent_run(profile, variant)
        assert observed == expected


def test_long_callback_starvation_and_useful_preemption() -> None:
    starvation = S0.BASE_S0.starvation_run(S0.CANDIDATE.PROFILE)
    assert starvation["first_service_count"] == starvation["start_count"]
    assert starvation["later_start_serviced"] is True
    useful = S0.demonstrated_starvation_handoff_run()
    assert useful["rungs"] == [64, 600]
    assert useful["deep_handoff_wall_cap_seconds"] <= 4.0


def test_work_accounting_faults_remain_fail_closed() -> None:
    taxonomy = S0.BASE_S0.work_accounting_failure_taxonomy(
        S0.CANDIDATE.PROFILE
    )
    assert len(taxonomy) == 6
    assert all(
        value.startswith(("ValueError:", "AssertionError:"))
        for value in taxonomy.values()
    )


def test_frozen_evidence_matches_reproduction() -> None:
    observed = S0.build_evidence()
    frozen = json.loads((HERE / "S0_EVIDENCE.json").read_text())
    assert observed == frozen
    row = observed["profiles"][S0.CANDIDATE.PROFILE]
    assert row["hybrid_reopen_gate"]["target_direct_rungs"] == [64, 600]
    assert row["hybrid_reopen_gate"][
        "target_deep_service_not_limited_to_probe_wall_cap"
    ] is True
    assert row["hybrid_reopen_gate"][
        "completed_probe_handoffs_uncapped"
    ] is True
