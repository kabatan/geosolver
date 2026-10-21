"""Benchmarks/test runner contracts and numerical regressions."""

import importlib.util
import json
import sys
from pathlib import Path

from tests.paths import REPO_ROOT


def _runner_module():
    path = REPO_ROOT / "benchmarks" / "research_runner.py"
    spec = importlib.util.spec_from_file_location("research_runner", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_checked_in_corpus_has_one_to_one_dsl_mapping() -> None:
    runner = _runner_module()

    report = runner.validate_corpus()

    assert report == {
        "valid": True,
        "inventory_count": 323,
        "runnable_count": 323,
        "reference_only_count": 0,
        "migration_blocked_count": 0,
        "truth_verified_count": 323,
        "unique_natural_problem_count": 323,
        "dsl_file_count": 323,
        "issues": [],
    }


def test_raw_campaign_artifact_contains_no_reference_answer(tmp_path: Path, monkeypatch) -> None:
    runner = _runner_module()
    record = runner.CaseRecord(
        identifier="case",
        dsl_path=tmp_path / "case.json",
        dsl={"id": "case"},
        source="source",
        references=("SECRET_REFERENCE",),
        authoring_status="runnable",
        truth_status="verified",
        dedupe_key="case",
    )
    assert record.dsl_path is not None
    assert record.dsl is not None
    record.dsl_path.write_text(json.dumps(record.dsl), encoding="utf-8")
    runner._source_hash = lambda: "source-hash"
    runner._dependency_hash = lambda: "dependency-hash"

    class Process:
        returncode = 0
        pid = 123

        def communicate(self, timeout: float):
            return "", ""

    def spawn(command, **kwargs):
        assert Path(command[command.index("--output") + 1]).is_absolute()
        assert kwargs["cwd"] != Path.cwd()
        return Process()

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(runner.subprocess, "Popen", spawn)
    runner._pin_process = lambda process, cpu: None

    output = runner._run_one(record, 7, Path("campaign"))
    text = output.read_text(encoding="utf-8")

    assert "SECRET_REFERENCE" not in text
    assert json.loads(text)["case_id"] == "case"


def test_checksum_manifest_is_deterministic(tmp_path: Path) -> None:
    runner = _runner_module()
    (tmp_path / "a").write_text("one", encoding="utf-8")
    runner.write_checksums(tmp_path)
    first = (tmp_path / "SHA256SUMS").read_text(encoding="utf-8")
    runner.write_checksums(tmp_path)
    assert (tmp_path / "SHA256SUMS").read_text(encoding="utf-8") == first


def test_campaign_case_filter_rejects_unknown_id(tmp_path: Path) -> None:
    runner = _runner_module()

    try:
        runner.run_campaign(tmp_path, seeds=[0], jobs=1, case_ids={"missing"})
    except runner.CampaignError as error:
        assert "unknown case ids" in str(error)
    else:
        raise AssertionError("unknown campaign id was accepted")


def test_answer_comparison_uses_mathematical_identity():
    from geosolver.exact import describe_exact

    runner = _runner_module()
    answer = describe_exact("sqrt(2)").model_dump(mode="json")
    changed = json.loads(json.dumps(answer))
    changed["value"]["decimal"] = "1.414"
    changed["value"]["isolating_interval"] = ["1", "2"]
    assert runner._answer_keys({"answers": [answer, answer]}) == runner._answer_keys(
        {"answers": [changed]}
    )


def test_campaign_refuses_overwrite_and_duplicate_seeds(tmp_path):
    import pytest

    runner = _runner_module()
    with pytest.raises(runner.CampaignError, match="unique"):
        runner.run_campaign(tmp_path, seeds=[0, 0], jobs=1)
    (tmp_path / "existing").write_text("preserve", encoding="utf-8")
    with pytest.raises(runner.CampaignError, match="empty"):
        runner.run_campaign(tmp_path, seeds=[0], jobs=1)
    assert (tmp_path / "existing").read_text() == "preserve"


def test_reference_hash_changes_with_reference_value(tmp_path):
    from dataclasses import replace

    runner = _runner_module()
    record = runner.CaseRecord(
        identifier="case",
        dsl_path=None,
        dsl=None,
        source="fixture",
        references=("1",),
        authoring_status="reference_only",
        truth_status="verified",
        dedupe_key="case",
    )
    first = runner._manifest([record], [0])
    second = runner._manifest([replace(record, references=("2",))], [0])
    assert first["corpus_hash"] != second["corpus_hash"]


def test_independent_cpus_are_unique():
    runner = _runner_module()
    cpus = [cpu for cpu in runner._independent_cpus() if cpu is not None]
    assert len(cpus) == len(set(cpus))


def test_assessment_rejects_incomplete_campaign(tmp_path, monkeypatch):
    import pytest

    runner = _runner_module()
    record = runner.CaseRecord(
        identifier="case",
        dsl_path=tmp_path / "dsl.json",
        dsl={},
        source="fixture",
        references=("1",),
        authoring_status="runnable",
        truth_status="verified",
        dedupe_key="case",
    )
    record.dsl_path.write_text("{}")
    monkeypatch.setattr(runner, "_load_cases", lambda *args: [record])
    runner._atomic_json(tmp_path / "campaign-manifest.json", runner._manifest([record], [0]))
    with pytest.raises(runner.CampaignError, match="missing run"):
        runner.assess_campaign(tmp_path)


def test_empty_answer_from_crash_is_not_a_normal_empty_set():
    runner = _runner_module()
    for raw in (
        {"process": {"timed_out": True}},
        {"process": {"returncode": 1}},
        {"solver_result": {"status": "resource_error", "answers": []}},
    ):
        outcome = runner.read_run_outcome(raw)
        assert not outcome["normal_completion"] and outcome["failure_stage"] == "runtime"


def test_runtime_fingerprint_matches_checked_out_product():
    runner = _runner_module()
    fingerprint = runner.runtime_fingerprint()
    assert not fingerprint["issues"]
    assert fingerprint["runtime_dependencies"]["mpmath"] == "1.3.0"
    assert fingerprint["import_root"] == str(runner.ROOT / "src/geosolver")


def test_display_references_preserve_exact_meaning():
    import pytest

    from geosolver.exact import describe_exact

    runner = _runner_module()
    pairs = {
        "27π/40": "27*pi/40",
        "2√3": "2*sqrt(3)",
        "(1+√13)/3": "(1+sqrt(13))/3",
        "6√37/5": "6*sqrt(37)/5",
        "64(2-√3)": "64*(2-sqrt(3))",
        r"2\\sqrt{21}": "2*sqrt(21)",
        "7/√3": "7/sqrt(3)",
        "sqrt(7250)": "sqrt(7250)",
        "∛2-1": "2**(1/3)-1",
        "2∛3": "2*3**(1/3)",
    }
    for text, expected in pairs.items():
        (actual,) = runner.reference_expressions(text)
        assert describe_exact(actual).canonical_key() == describe_exact(expected).canonical_key()
    assert runner.reference_expressions("-1,-4/3,1,3/4,-1/2,-3,1/3,2 (8個)") == [
        "-1",
        "-4/3",
        "1",
        "3/4",
        "-1/2",
        "-3",
        "1/3",
        "2",
    ]
    with pytest.raises(runner.CampaignError, match="count"):
        runner.reference_expressions("1,2 (3個)")


def test_reference_sets_split_only_top_level_commas_and_keep_numeric_source():
    runner = _runner_module()
    assert runner.reference_expressions("64,96,220") == ["64", "96", "220"]
    root = "CRootOf(x**2-2,1)"
    assert runner.reference_expressions(root) == [root]
    assert runner.reference_expressions(f"{root}, 3 (2個)") == [root, "3"]
    assert runner.reference_expressions("(64,96,220)") == ["64", "96", "220"]
    decimal = "0.1234567890123456789012345678901234567890"
    assert runner.reference_expressions(f"{decimal}, 1") == [decimal, "1"]


def test_corpus_display_references_are_scalar_expressions():
    import sympy

    runner = _runner_module()
    for record in runner._load_cases(runner.DEFAULT_CASES):
        for reference in record.references:
            values = runner.reference_expressions(reference)
            assert values, record.identifier
            for value in values:
                assert isinstance(sympy.sympify(value), sympy.Expr), (record.identifier, value)


def test_quarantined_problem_is_not_counted_as_a_solver_failure(tmp_path):
    from benchmarks.research_runner import summarize_campaign

    rows = [
        {"matched": True, "status": "solved"},
        {"matched": None, "status": "no_answer_found", "truth_status": "quarantined"},
    ]
    (tmp_path / "assessment.jsonl").write_text("\n".join(json.dumps(row) for row in rows))
    summarize_campaign(tmp_path)
    summary = json.loads((tmp_path / "summary.json").read_text())
    assert summary["run_count"] == 2 and summary["assessed_count"] == 1
    assert summary["unassessed_count"] == 1 and summary["match_rate"] == 1
