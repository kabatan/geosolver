from __future__ import annotations

import importlib.util
import json
import shutil
from pathlib import Path

import pytest


EXPERIMENT_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = EXPERIMENT_ROOT.parents[2]
RESULT_ROOT = (
    REPO_ROOT
    / "research"
    / "results"
    / "EXP-SINGULAR-001"
    / "development-s2-v0"
)
INPUT_MANIFEST = EXPERIMENT_ROOT / "s2-development-input-manifest.json"

spec = importlib.util.spec_from_file_location(
    "s2_development_analysis",
    EXPERIMENT_ROOT / "s2_development_analysis.py",
)
assert spec is not None and spec.loader is not None
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_independent_s2_analysis_matches_committed_summary() -> None:
    document = module.analyze(RESULT_ROOT, INPUT_MANIFEST)
    assert document["summary_match"] is True
    assert document["development_advancement_passed"] is True
    assert document["product_connected"] is False
    assert document["locked_validation"] is False
    assert document["recomputed_metamorphic_disagreement_groups"] == []
    assert document["recomputed_analytic_control_disagreement_cases"] == []
    assert document["recomputed_budget_limit_violation_rows"] == []
    assert all(document["recomputed_criteria"].values())


def test_s2_dense_improves_only_the_eligible_target_constant_stratum() -> None:
    document = module.analyze(RESULT_ROOT, INPUT_MANIFEST)
    variants = document["recomputed_variants"]
    assert variants["S1-AP-LMQR"]["eligible_gold_successes"] == 0
    assert variants["S2-AP-CPQR-SUBSET"]["eligible_gold_successes"] == 12
    assert variants["S2-ANALYTIC-SUBSET-CONTROL"]["eligible_gold_successes"] == 12
    assert variants["S2-AP-CPQR-SUBSET"]["status_counts"] == {
        "promoted": 12,
        "diagnostic_only": 0,
        "unknown": 12,
    }
    assert all(entry["false_promotions"] == 0 for entry in variants.values())


def test_independent_analyzer_rejects_a_tampered_summary(tmp_path: Path) -> None:
    for filename in ("attempts.json", "environment.json", "summary.json"):
        shutil.copy2(RESULT_ROOT / filename, tmp_path / filename)
    summary_path = tmp_path / "summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    summary["false_promotions"] = 1
    summary_path.write_text(json.dumps(summary), encoding="utf-8")
    with pytest.raises(ValueError, match="false_promotions"):
        module.analyze(tmp_path, INPUT_MANIFEST)
