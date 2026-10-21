"""Artificial raw artifacts only: no natural problem is solved or inspected."""

from __future__ import annotations

import copy
import csv
import hashlib
import importlib
import json
import sys
from pathlib import Path

import pytest

from tests.paths import REPO_ROOT

sys.path.insert(0, str(REPO_ROOT))
try:
    assessment = importlib.import_module("benchmarks.gmb_comparison.assessment")
finally:
    sys.path.pop(0)

SOURCE = """(param (A B C) triangle)
(define M point (midp A B))
(eval (cong A C B C))
"""
DECLARATIONS = {name: "point" for name in ("A", "B", "C", "M")}
ENGINE = {"source_sha256": "synthetic-only"}


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def seal(root, name):
    paths = sorted(path for path in root.rglob("*") if path.is_file() and path != root / name)
    (root / name).write_text(
        "".join(
            f"{assessment.sha256(path)}  {path.relative_to(root).as_posix()}\n" for path in paths
        ),
        encoding="utf-8",
    )


def witness(*, goal=False, invalid=False, error=None):
    return {
        "points": {
            "A": ["0", "0"],
            "B": ["2", "0"],
            "C": ["1" if goal else "0", "1"],
            "M": ["1", error or ("0.1" if invalid else "0")],
        },
        "lines": {},
        "circles": {},
    }


class SyntheticCampaign:
    """Mirrors production record shapes, with small exact artificial triangles."""

    def __init__(self, tmp_path, *, cases=1, seeds=(0, 1, 2), aligned=False):
        self.root, self.legacy = tmp_path / "new", tmp_path / "old"
        self.root.mkdir()
        self.legacy.mkdir()
        self.aligned = aligned
        self.entries, native_entries = [], []
        for index in range(cases):
            case_id = f"SYNTHETIC_{index:02d}"
            geo_input = self.root / f"inputs/geosolver/{case_id}.json"
            gmbl_input = self.root / f"inputs/gmbl/{case_id}.smt2"
            write(geo_input, {"id": case_id, "target": "0"})
            gmbl_input.parent.mkdir(parents=True, exist_ok=True)
            gmbl_input.write_text(SOURCE, encoding="utf-8")
            old_input = self.legacy / f"inputs/{case_id}.smt2"
            old_input.parent.mkdir(parents=True, exist_ok=True)
            old_input.write_text(SOURCE, encoding="utf-8")
            gmb_root = self.root / "gmb-aligned" if aligned else self.legacy
            self.entries.append(
                {
                    "case_id": case_id,
                    "geo_input": str(geo_input.relative_to(self.root)),
                    "geo_sha256": assessment.sha256(geo_input),
                    "gmbl_input": str(gmbl_input.relative_to(self.root)),
                    "gmbl_sha256": assessment.sha256(gmbl_input),
                    "original_assumptions_covered": True,
                    "input_origin": "original_statement_aligned" if aligned else "official_gmb",
                    "declarations": DECLARATIONS,
                    "bindings": {},
                    "gmb_runs": {
                        str(seed): {
                            "directory": str(gmb_root / "runs" / case_id / str(seed)),
                            "origin": "new_aligned" if aligned else "reused_official",
                        }
                        for seed in seeds
                    },
                }
            )
            native_entries.append(
                {
                    "case_id": case_id,
                    "input": str(gmbl_input if aligned else old_input),
                    "input_sha256": assessment.sha256(gmbl_input),
                }
            )
        self.native = {
            "schema_version": 1,
            "cpu": 4,
            "timeout_seconds": 180,
            "seeds": list(seeds),
            "entries": native_entries,
            "options": {"eps": 1e-6},
            "upstream_defaults": {"synthetic": True},
        }
        self.manifest = {
            "schema_version": 1,
            "study": "SYNTHETIC_ONLY",
            "input_profile": "synthetic",
            "cpu": 4,
            "timeout_seconds": 180,
            "seeds": list(seeds),
            "protocol": {
                "common_tolerance": "1e-6",
                "sensitivity_tolerances": ["1e-3", "1e-6", "1e-9"],
                "checker_dps": 80,
            },
            "entries": self.entries,
            "legacy_sources": [],
            "engine_identity": ENGINE,
        }
        for entry in self.entries:
            for seed in seeds:
                for method in assessment.METHODS:
                    self.set_run(method, entry["case_id"], seed)

    def directory(self, method, case_id="SYNTHETIC_00", seed=0):
        base = (
            self.root / "geosolver"
            if method == "geosolver"
            else (self.root / "gmb-aligned" if self.aligned else self.legacy)
        )
        return base / "runs" / case_id / str(seed)

    def set_run(
        self,
        method,
        case_id="SYNTHETIC_00",
        seed=0,
        *,
        models=None,
        termination="completed",
        stage="native_accepted_return",
    ):
        if models is None:
            models = [(1.0, witness())]
        entry = next(entry for entry in self.entries if entry["case_id"] == case_id)
        directory = self.directory(method, case_id, seed)
        directory.mkdir(parents=True, exist_ok=True)
        # Test fixtures replace only their own explicitly known files.
        for path in (directory / "models").glob("*.json"):
            path.unlink()
        events = [
            {"event": "worker_start", "elapsed_seconds": 0.01},
            {
                "event": "solver_start" if method == "geosolver" else "build_start",
                "elapsed_seconds": 0.02,
            },
        ]
        names = []
        for index, (elapsed, geometry) in enumerate(models):
            name = f"models/{index:04d}.json"
            names.append(name)
            if method == "gmb":
                payload = {
                    "named_points": geometry["points"],
                    "named_lines": {},
                    "named_circles": {},
                    "goals": {"ignored_native_loss": 0},
                }
                event = {
                    "event": "model_materialized",
                    "model": name,
                    "materialized_seconds": elapsed - 0.1,
                    "elapsed_seconds": elapsed,
                }
            else:
                coordinates = geometry["points"]["C"]
                candidate = {"candidate_id": index, "revision": 1, "x_hp": coordinates}
                digest = hashlib.sha256(
                    json.dumps(coordinates, separators=(",", ":")).encode()
                ).hexdigest()
                identity = {
                    "candidate_id": index,
                    "revision": 1,
                    "candidate_uid": f"synthetic/{index}",
                    "coordinate_sha256": digest,
                    "stage": stage,
                }
                payload = {
                    **identity,
                    "candidate": candidate,
                    "witness": geometry,
                    "coordinate_observed_seconds": elapsed - 0.2,
                    "materialized_seconds": elapsed - 0.1,
                }
                event = {
                    **identity,
                    "event": "model_materialized",
                    "model": name,
                    "materialized_seconds": elapsed - 0.1,
                    "emitted_seconds": elapsed,
                    "elapsed_seconds": elapsed + 0.001,
                }
            write(directory / name, payload)
            events.append(event)
        end = max([event["elapsed_seconds"] for event in events] + [3.0]) + 0.1
        crashed = termination == "crash"
        timed_out = termination == "timeout"
        cancelled = termination == "cancelled"
        wall = max(end + 0.1, 180.2 if timed_out else 0)
        if not (crashed or timed_out or cancelled):
            events.append({"event": "worker_end", "elapsed_seconds": end})
        (directory / "events.jsonl").write_text(
            "".join(json.dumps(event) + "\n" for event in events), encoding="utf-8"
        )
        for name in ("stdout.log", "stderr.log"):
            (directory / name).write_text("synthetic\n", encoding="utf-8")
        resources = {
            "pid": 99999,
            "returncode": -15 if crashed or timed_out or cancelled else 0,
            "timed_out": timed_out,
            "cancelled": cancelled,
            "wall_seconds": wall,
            "cpu_seconds": 1.5,
            "cpu_user_seconds": 1.0,
            "cpu_system_seconds": 0.5,
            "peak_rss_bytes": 1024**2,
            "affinity_masks_observed": [[4]],
            "affinity_violations": [],
            "affinity_samples": 3,
            "max_os_threads": 1,
            "descendants_remaining_at_leader_exit": False,
        }
        request = {
            "schema_version": 1,
            "case_id": case_id,
            "seed": seed,
            "cpu": 4,
            "input": str(self.root / entry["geo_input"])
            if method == "geosolver"
            else self.native["entries"][self.entries.index(entry)]["input"],
            "input_sha256": entry["geo_sha256" if method == "geosolver" else "gmbl_sha256"],
            "instrument": True,
            "timeout_seconds": 180,
            "engine_identity": ENGINE,
            "declarations": DECLARATIONS,
            "bindings": {},
            "options": self.native["options"],
            "upstream_defaults": self.native["upstream_defaults"],
        }
        child = {"schema_version": 1, "model_files": names}
        if method == "gmb":
            child.update(
                outcome="model_returned" if names else "no_model", models_returned=len(names)
            )
            write(directory / "identity.json", {"cpu_affinity": [4], "visible_gpus": []})
        else:
            child.update(
                outcome="completed",
                solver_status="success" if names else "no_answer_found",
                engine_identity=ENGINE,
                cpu_affinity=[4],
                materialization_failures=[],
            )
            artifact = {
                "status": "completed",
                "solver_status": child["solver_status"],
                "public_solved": bool(names),
                "execution_identity": ENGINE,
                "process_info": {"cpu_affinity": [4]},
                "phase_timings": {"search": 0.4},
                "counters": {"evaluation_count": 10},
            }
            if not (timed_out or crashed or cancelled):
                write(directory / "worker-artifact.json", artifact)
        if not (timed_out or crashed or cancelled):
            write(directory / "child-result.json", child)
        else:
            for name in ("child-result.json", "worker-artifact.json"):
                path = directory / name
                if path.exists():
                    path.unlink()
        write(directory / "request.json", request)
        write(
            directory / "run.json",
            {
                "schema_version": 1,
                "case_id": case_id,
                "seed": seed,
                "input_sha256": request["input_sha256"],
                "manifest_sha256": "pending",
                "process": resources,
                "outcome": termination if termination != "completed" else child["outcome"],
                "environment": {
                    **dict.fromkeys(assessment.COMMON_THREADS, "1"),
                    "CUDA_VISIBLE_DEVICES": "-1",
                    "PYTHONHASHSEED": str(seed),
                },
            },
        )

    def finalize(self):
        if not self.aligned:
            write(self.legacy / "campaign-manifest.json", self.native)
            for path in self.legacy.glob("runs/*/*/run.json"):
                value = read(path)
                value["manifest_sha256"] = assessment.sha256(self.legacy / "campaign-manifest.json")
                write(path, value)
            seal(self.legacy, "SHA256SUMS")
            self.manifest["legacy_sources"] = [
                {
                    "directory": str(self.legacy),
                    "seeds": self.manifest["seeds"],
                    "manifest_sha256": assessment.sha256(self.legacy / "campaign-manifest.json"),
                    "sha256sums_sha256": assessment.sha256(self.legacy / "SHA256SUMS"),
                }
            ]
        write(self.root / "campaign-manifest.json", self.manifest)
        root_hash = assessment.sha256(self.root / "campaign-manifest.json")
        for path in self.root.glob("geosolver/runs/*/*/run.json"):
            value = read(path)
            value["manifest_sha256"] = root_hash
            write(path, value)
        if self.aligned:
            self.native["comparison_manifest_sha256"] = root_hash
            path = self.root / "gmb-aligned/campaign-manifest.json"
            write(path, self.native)
            for run_path in self.root.glob("gmb-aligned/runs/*/*/run.json"):
                value = read(run_path)
                value["manifest_sha256"] = assessment.sha256(path)
                write(run_path, value)
        seal(self.root, "RAW_SHA256SUMS")
        return self.root

    def assess(self):
        result = assessment.assess_campaign(self.finalize())
        rows = [
            json.loads(line)
            for line in (self.root / "assessment/run-results.jsonl").read_text().splitlines()
        ]
        return result, rows


def selected(rows, method="geosolver", seed=0):
    return next(row for row in rows if row["method"] == method and row["seed"] == seed)


def test_valid_model_and_false_goal_are_separate(tmp_path):
    fixture = SyntheticCampaign(tmp_path)
    result, rows = fixture.assess()
    assert result["complete_evidence"] is True
    assert len(rows) == 6
    for row in rows:
        assert row["success"] is True
        assert row["goals_valid"] is False
        assert row["native_completed_success"] is True
        assert row["checker_seconds"] >= 0
        assert row["time_to_first_valid_seconds"] == 1


@pytest.mark.parametrize("method", assessment.METHODS)
@pytest.mark.parametrize("termination", ["timeout", "crash", "cancelled"])
def test_emitted_model_survives_later_timeout_or_crash(tmp_path, method, termination):
    fixture = SyntheticCampaign(tmp_path)
    fixture.set_run(method, termination=termination)
    _, rows = fixture.assess()
    row = selected(rows, method)
    assert row["success"] is True
    assert row["evidence_issues"] == []
    assert row["termination_outcome"] == termination
    assert row["native_completed_success"] is False


@pytest.mark.parametrize("method", assessment.METHODS)
def test_late_valid_model_is_not_success_or_broken_evidence(tmp_path, method):
    fixture = SyntheticCampaign(tmp_path)
    fixture.set_run(method, models=[(180.1, witness())], termination="timeout")
    _, rows = fixture.assess()
    row = selected(rows, method)
    assert row["outcome"] == "late_output_only"
    assert row["evidence_issues"] == []
    assert row["capped_time_seconds"] == 180


@pytest.mark.parametrize("method", assessment.METHODS)
def test_deadline_uses_emission_not_materialization(tmp_path, method):
    fixture = SyntheticCampaign(tmp_path)
    fixture.set_run(method, models=[(180.05, witness())], termination="timeout")
    _, rows = fixture.assess()
    assert selected(rows, method)["success"] is False


@pytest.mark.parametrize("method", assessment.METHODS)
def test_first_valid_output_and_not_first_goal_passing_output(tmp_path, method):
    fixture = SyntheticCampaign(tmp_path)
    fixture.set_run(
        method, models=[(1, witness(invalid=True)), (2, witness()), (3, witness(goal=True))]
    )
    _, rows = fixture.assess()
    row = selected(rows, method)
    assert row["time_to_first_valid_seconds"] == 2
    assert row["goals_valid"] is False
    assert row["common_status_counts"] == {"failed": 1, "passed": 2}
    assert row["failure_reasons"]


def test_intermediate_candidate_never_counts(tmp_path):
    fixture = SyntheticCampaign(tmp_path)
    fixture.set_run("geosolver", stage="refinement_return")
    _, rows = fixture.assess()
    row = selected(rows)
    assert row["outcome"] == "no_native_output"
    assert row["evidence_issues"] == []


def test_all_tolerances_keep_their_own_first_model_and_failure_reasons(tmp_path):
    fixture = SyntheticCampaign(tmp_path)
    fixture.set_run("gmb", models=[(1, witness(error="0.000001")), (2, witness())])
    _, rows = fixture.assess()
    threshold = selected(rows, "gmb")["thresholds"]
    assert threshold["1e-3"]["time_to_first_valid_seconds"] == 1
    assert threshold["1e-9"]["time_to_first_valid_seconds"] == 2
    assert threshold["1e-9"]["failure_reasons"]


def test_cpu_violation_is_evidence_issue_not_geometric_failure(tmp_path):
    fixture = SyntheticCampaign(tmp_path)
    path = fixture.directory("gmb") / "run.json"
    value = read(path)
    value["process"]["affinity_masks_observed"] = [[4, 5]]
    write(path, value)
    _, rows = fixture.assess()
    row = selected(rows, "gmb")
    assert row["outcome"] == "evidence_issue"
    assert "cpu_affinity_mismatch" in row["evidence_issues"]
    assert row["success"] is False


def test_observation_error_invalidates_trial_even_with_a_valid_model(tmp_path):
    fixture = SyntheticCampaign(tmp_path)
    directory = fixture.directory("geosolver")
    path = directory / "events.jsonl"
    events = [json.loads(line) for line in path.read_text().splitlines()]
    events.insert(
        -1,
        {
            "event": "materialization_error",
            "elapsed_seconds": 2,
            "kind": "observation_error",
            "stage": "native_accepted_return",
            "error": "synthetic export failure",
        },
    )
    path.write_text("".join(json.dumps(event) + "\n" for event in events))
    _, rows = fixture.assess()
    row = selected(rows)
    assert row["outcome"] == "evidence_issue"
    assert "observation_error:observation_error" in row["evidence_issues"]
    assert row["observation_failures"][0]["error"] == "synthetic export failure"


@pytest.mark.parametrize("mutation", ["coordinates", "revision", "backdated"])
def test_observation_record_cannot_mix_revisions_or_clocks(tmp_path, mutation):
    fixture = SyntheticCampaign(tmp_path)
    path = fixture.directory("geosolver") / "models/0000.json"
    payload = read(path)
    if mutation == "coordinates":
        payload["candidate"]["x_hp"] = ["5", "6"]
    elif mutation == "revision":
        payload["candidate"]["revision"] = 2
    else:
        payload["coordinate_observed_seconds"] = 2
    write(path, payload)
    _, rows = fixture.assess()
    row = selected(rows)
    assert row["outcome"] == "evidence_issue"
    assert row["evidence_issues"]


def test_normal_failed_artifact_without_identity_is_a_solver_error(tmp_path):
    fixture = SyntheticCampaign(tmp_path)
    fixture.set_run("geosolver", models=[])
    directory = fixture.directory("geosolver")
    artifact = read(directory / "worker-artifact.json")
    artifact.update(
        status="failed",
        solver_status=None,
        execution_identity={},
        process_info={},
        error={"code": "synthetic_error", "message": "ordinary solver exception"},
    )
    child = read(directory / "child-result.json")
    child.update(outcome="error", solver_status=None)
    run = read(directory / "run.json")
    run["outcome"] = "error"
    write(directory / "worker-artifact.json", artifact)
    write(directory / "child-result.json", child)
    write(directory / "run.json", run)
    _, rows = fixture.assess()
    row = selected(rows)
    assert row["evidence_issues"] == []
    assert row["outcome"] == "no_output"
    assert row["termination_outcome"] == "error"
    assert row["worker_error"]["code"] == "synthetic_error"


def test_normal_no_output_and_native_invalid_output_are_distinct(tmp_path):
    fixture = SyntheticCampaign(tmp_path)
    fixture.set_run("gmb", models=[])
    fixture.set_run("geosolver", models=[(1, witness(invalid=True))])
    _, rows = fixture.assess()
    assert selected(rows, "gmb")["outcome"] == "no_output"
    row = selected(rows)
    assert row["outcome"] == "no_valid_output"
    assert row["native_completed_success"] is True
    assert row["common_status_counts"] == {"failed": 1}


def test_aligned_gmb_manifest_and_raw_are_validated(tmp_path):
    fixture = SyntheticCampaign(tmp_path, aligned=True)
    result, rows = fixture.assess()
    assert result["complete_evidence"] is True
    assert selected(rows, "gmb")["run_origin"] == "new_aligned"
    assert result["by_method"]["gmb"]["run_origin_counts"] == {"new_aligned": 3}


@pytest.mark.parametrize("method", assessment.METHODS)
def test_request_input_hash_mismatch_is_never_success(tmp_path, method):
    fixture = SyntheticCampaign(tmp_path)
    path = fixture.directory(method) / "request.json"
    value = read(path)
    value["input_sha256"] = "wrong"
    write(path, value)
    _, rows = fixture.assess()
    assert "request_input_sha256_mismatch" in selected(rows, method)["evidence_issues"]


def test_changed_model_after_raw_seal_is_not_read_or_checked(tmp_path, monkeypatch):
    fixture = SyntheticCampaign(tmp_path)
    root = fixture.finalize()
    path = fixture.directory("geosolver") / "models/0000.json"
    payload = read(path)
    payload["witness"] = witness(goal=True)
    write(path, payload)
    calls = []
    original = assessment.check_configuration

    def record(text, witness, **kwargs):
        calls.append(copy.deepcopy(witness))
        return original(text, witness, **kwargs)

    monkeypatch.setattr(assessment, "check_configuration", record)
    result = assessment.assess_campaign(root)
    assert result["complete_evidence"] is False
    assert all(value["points"]["C"][0] != "1" for value in calls)


def test_changed_legacy_seal_invalidates_only_reused_evidence(tmp_path):
    fixture = SyntheticCampaign(tmp_path)
    root = fixture.finalize()
    (fixture.legacy / "SHA256SUMS").write_text("tampered\n")
    result = assessment.assess_campaign(root)
    assert result["by_method"]["gmb"]["primary"]["evidence_issue_runs"] == 3
    assert result["by_method"]["geosolver"]["primary"]["success_runs"] == 3


def test_missing_run_remains_in_denominator_and_is_not_zero_time(tmp_path):
    fixture = SyntheticCampaign(tmp_path)
    path = fixture.directory("gmb") / "run.json"
    path.unlink()
    result, rows = fixture.assess()
    row = selected(rows, "gmb")
    assert row["outcome"] == "evidence_issue"
    assert row["capped_time_seconds"] == 180
    assert result["by_method"]["gmb"]["primary"]["planned_runs"] == 3
    assert result["by_method"]["gmb"]["primary"]["success_runs"] == 2


def test_orphan_model_and_duplicated_event_fail_closed(tmp_path):
    fixture = SyntheticCampaign(tmp_path)
    directory = fixture.directory("geosolver")
    write(directory / "models/9999.json", read(directory / "models/0000.json"))
    _, rows = fixture.assess()
    assert "model_files_and_events_mismatch" in selected(rows)["evidence_issues"]


def test_unapproved_original_assumptions_cannot_pass(tmp_path):
    fixture = SyntheticCampaign(tmp_path)
    fixture.entries[0]["original_assumptions_covered"] = False
    result, rows = fixture.assess()
    assert result["complete_evidence"] is False
    assert all(row["outcome"] == "evidence_issue" for row in rows)


def test_seal_is_mandatory_and_unsafe_entries_are_rejected(tmp_path):
    with pytest.raises(assessment.EvidenceError, match="missing_seal"):
        assessment.assess_campaign(tmp_path)
    (tmp_path / "RAW_SHA256SUMS").write_text("0" * 64 + "  ../outside.json\n")
    with pytest.raises(assessment.EvidenceError, match="unsafe_relative_path"):
        assessment.assess_campaign(tmp_path)


def test_summary_is_reproducible_and_never_rechecks_or_changes_raw(tmp_path, monkeypatch):
    fixture = SyntheticCampaign(tmp_path)
    root = fixture.finalize()
    all_raw = {
        str(path): assessment.sha256(path)
        for base in (root, fixture.legacy)
        for path in base.rglob("*")
        if path.is_file()
    }
    first = assessment.assess_campaign(root)
    all_outputs = {
        str(path): path.read_bytes() for path in (root / "assessment").rglob("*") if path.is_file()
    }

    def forbidden(*args, **kwargs):
        raise AssertionError("Sealed per-model checks must be reused")

    monkeypatch.setattr(assessment, "check_configuration", forbidden)
    second = assessment.assess_campaign(root)
    assert first == second
    assert all(
        path == str(Path(path)) and assessment.sha256(Path(path)) == digest
        for path, digest in all_raw.items()
    )
    assert all(Path(path).read_bytes() == value for path, value in all_outputs.items())
    with (root / "assessment/run-results.csv").open() as handle:
        csv_rows = list(csv.DictReader(handle))
    assert len(csv_rows) == 6
    assert all(json.loads(row["thresholds"])["1e-6"]["success"] for row in csv_rows)


def test_corrupt_assessment_cache_cannot_be_reused(tmp_path):
    fixture = SyntheticCampaign(tmp_path)
    root = fixture.finalize()
    assessment.assess_campaign(root)
    cached = next((root / "assessment/models").rglob("*.json"))
    value = read(cached)
    value["checks"]["1e-6"]["result"]["valid"] = False
    write(cached, value)
    with pytest.raises(assessment.EvidenceError, match="file_hash_mismatch"):
        assessment.assess_campaign(root)


def test_complete_synthetic_36_by_3_by_2_has_216_rows(tmp_path):
    fixture = SyntheticCampaign(tmp_path, cases=36)
    summary, rows = fixture.assess()
    assert len(rows) == 216
    assert summary["planned_runs_per_method"] == 108
    for method in assessment.METHODS:
        assert summary["by_method"][method]["primary"]["success_runs"] == 108
        assert summary["by_method"][method]["case_success_count_distribution"] == {
            "0": 0,
            "1": 0,
            "2": 0,
            "3": 36,
        }


def test_phase_timing_keeps_unfinished_work_and_ignores_fake_endpoints():
    events = [
        {"event": "search_start", "elapsed_seconds": 1},
        {"event": "search_end", "elapsed_seconds": 2},
        {"event": "refinement_start", "elapsed_seconds": 3},
    ]
    assert assessment.event_timings(events) == {
        "search": {"completed_seconds": 1, "completed_calls": 1, "incomplete_calls": 0},
        "refinement": {"completed_seconds": None, "completed_calls": 0, "incomplete_calls": 1},
    }


@pytest.mark.parametrize("source", ['{"x":NaN}', '{"x":1e999}', '{"x":0,"x":1}'])
def test_json_corruption_fails_closed(source):
    with pytest.raises(assessment.EvidenceError):
        assessment._decode(source)
