from __future__ import annotations

import importlib.util
import json
from pathlib import Path


EXPERIMENT_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = EXPERIMENT_ROOT.parents[2]
RESULT_ROOT = (
    REPO_ROOT
    / "research"
    / "results"
    / "EXP-SINGULAR-001"
    / "development-s0-s1-v0"
)
INPUT_MANIFEST = EXPERIMENT_ROOT / "development-input-manifest.json"

spec = importlib.util.spec_from_file_location(
    "development_analysis",
    EXPERIMENT_ROOT / "development_analysis.py",
)
assert spec is not None and spec.loader is not None
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_independent_analysis_matches_committed_summary() -> None:
    document = module.analyze(RESULT_ROOT, INPUT_MANIFEST)
    assert document["summary_match"] is True
    assert document["development_advancement_passed"] is True
    assert document["product_connected"] is False
    assert document["metamorphic_disagreement_groups"] == []
    assert all(document["recomputed_criteria"].values())


def test_s0_is_diagnostic_and_s1_has_root_evidence() -> None:
    attempts = json.loads((RESULT_ROOT / "attempts.json").read_text(encoding="utf-8"))
    p1_rows = [
        row
        for row in attempts["rows"]
        if row["case_id"] == "dev-near-d1p0em13-m1p0-base"
    ]
    assert len(p1_rows) == 3
    s0 = next(row for row in p1_rows if row["variant"] == "S0-POINT-REPLAY")
    s1 = next(row for row in p1_rows if row["variant"] == "S1-AP-LMQR")
    assert s0["outcome"]["status"] == "diagnostic_only"
    assert s0["outcome"]["semantic_replay"]["accepted"] is True
    assert s0["outcome"]["root_evidence"] is None
    assert s1["outcome"]["status"] == "promoted"
    assert s1["outcome"]["root_evidence"] is not None
    assert s1["assessment"]["gold_success"] is True
