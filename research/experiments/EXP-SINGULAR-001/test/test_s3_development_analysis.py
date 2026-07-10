from __future__ import annotations

import importlib.util
import json
import shutil
from pathlib import Path

import pytest


EXPERIMENT_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = EXPERIMENT_ROOT.parents[2]
RESULT_ROOT = (
    REPO_ROOT / "research" / "results" / "EXP-SINGULAR-001" / "development-s3-v0"
)
INPUT_MANIFEST = EXPERIMENT_ROOT / "s3-development-input-manifest.json"

spec = importlib.util.spec_from_file_location(
    "s3_development_analysis",
    EXPERIMENT_ROOT / "s3_development_analysis.py",
)
assert spec is not None and spec.loader is not None
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_independent_s3_analysis_matches_bounded_negative_result() -> None:
    document = module.analyze(RESULT_ROOT, INPUT_MANIFEST)
    assert document["summary_match"] is True
    assert document["development_advancement_passed"] is False
    assert document["product_connected"] is False
    assert document["locked_validation"] is False
    assert document["recomputed_hard_budget_failures"] == []
    assert document["recomputed_budget_limit_violation_rows"] == []
    assert document["recomputed_analytic_control_disagreement_cases"] == []
    assert document["recomputed_metamorphic_disagreement_groups"] == [
        "S1-AP-LMQR:s3-fold-close"
    ]


def test_s3_and_control_fail_closed_at_the_global_iteration_cap() -> None:
    document = module.analyze(RESULT_ROOT, INPUT_MANIFEST)
    variants = document["recomputed_variants"]
    assert variants["S1-AP-LMQR"]["eligible_gold_successes"] == 0
    assert variants["S3-AP-BROYDEN"]["eligible_gold_successes"] == 0
    assert variants["S3-ANALYTIC-SECANT-CONTROL"]["eligible_gold_successes"] == 0
    assert variants["S3-AP-BROYDEN"]["budget_exhaustions"] == 12
    assert variants["S3-ANALYTIC-SECANT-CONTROL"]["budget_exhaustions"] == 12
    assert all(entry["false_promotions"] == 0 for entry in variants.values())
    assert document["recomputed_criteria"]["false_promotions_zero"] is True
    assert document["recomputed_criteria"]["recall_gain_at_least_0_50"] is False


def test_independent_analyzer_rejects_a_tampered_summary(tmp_path: Path) -> None:
    for filename in ("attempts.json", "environment.json", "summary.json"):
        shutil.copy2(RESULT_ROOT / filename, tmp_path / filename)
    summary_path = tmp_path / "summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    summary["development_advancement_passed"] = True
    summary_path.write_text(json.dumps(summary), encoding="utf-8")
    with pytest.raises(ValueError, match="development_advancement_passed"):
        module.analyze(tmp_path, INPUT_MANIFEST)


def test_independent_analyzer_rejects_iteration_overrun(tmp_path: Path) -> None:
    for filename in ("attempts.json", "environment.json", "summary.json"):
        shutil.copy2(RESULT_ROOT / filename, tmp_path / filename)
    attempts_path = tmp_path / "attempts.json"
    attempts = json.loads(attempts_path.read_text(encoding="utf-8"))
    attempts["rows"][0]["outcome"]["work"]["iterations"] = 65
    attempts_path.write_text(json.dumps(attempts), encoding="utf-8")
    with pytest.raises(ValueError, match="hard-budget|summary mismatch"):
        module.analyze(tmp_path, INPUT_MANIFEST)
