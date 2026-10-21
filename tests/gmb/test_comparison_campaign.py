"""Synthetic contract tests for production authorization; no IMO optimization."""

import copy
import importlib
import json
import sys
import time
from pathlib import Path

import pytest

from tests.paths import REPO_ROOT

sys.path.insert(0, str(REPO_ROOT))
try:
    authorization = importlib.import_module("benchmarks.gmb_comparison.authorization")
    campaign = importlib.import_module("benchmarks.gmb_comparison.campaign")
    worker = importlib.import_module("benchmarks.gmb_comparison.measurement_worker")
finally:
    sys.path.pop(0)


def fixture_request(tmp_path):
    problem = {"id": "TEST_CONTRACT", "target": "0"}
    entry = {
        "case_id": problem["id"],
        "geo_input": "inputs/case.json",
        "geo_sha256": "input-digest",
        "original_assumptions_covered": True,
        "declarations": {"A": "point"},
        "bindings": {},
    }
    manifest = {
        "authorization": {"user_authorized": True},
        "protocol": {"main_run_authorized": True},
        "entries": [entry],
        "cpu": 4,
        "timeout_seconds": 180,
        "seeds": [0, 1, 2],
        "engine_identity": {"source_hash": "test-source"},
        "geo_environment": {"prefix": "/test/venv"},
    }
    path = tmp_path / "campaign-manifest.json"
    campaign.write_json(path, manifest)
    request = {
        "synthetic_canary": False,
        "case_id": problem["id"],
        "seed": 0,
        "cpu": 4,
        "timeout_seconds": 180,
        "input_sha256": entry["geo_sha256"],
        "input": str(tmp_path / entry["geo_input"]),
        "engine_identity": manifest["engine_identity"],
        "declarations": entry["declarations"],
        "bindings": {},
        "instrument": True,
        "venv": "/test/venv",
        "campaign_manifest": str(path),
        "campaign_manifest_sha256": campaign.sha256(path),
        "output_directory": str(tmp_path / "geosolver/runs/TEST_CONTRACT/0"),
    }
    return request, problem, manifest


def test_synthetic_authorization_cannot_run_natural_problem():
    with pytest.raises(RuntimeError, match="natural"):
        authorization.authorize_request({"synthetic_canary": True}, {"id": "IMO_9999_P1"})
    authorization.authorize_request({"synthetic_canary": True}, {"id": "SYNTHETIC_TEST"})


def test_valid_frozen_campaign_authorizes_exact_request(tmp_path):
    request, problem, _ = fixture_request(tmp_path)
    authorization.authorize_request(request, problem)


def test_rejected_worker_request_cannot_modify_existing_evidence(tmp_path, monkeypatch):
    problem = tmp_path / "input.json"
    campaign.write_json(problem, {"id": "NATURAL_TEST", "target": "0"})
    old = tmp_path / "old-evidence"
    old.mkdir()
    (old / "events.jsonl").write_text("old event\n")
    (old / "child-result.json").write_text('{"old":"evidence"}')
    expected = {p.name: p.read_bytes() for p in old.iterdir()}
    request = {
        "input": str(problem),
        "input_sha256": campaign.sha256(problem),
        "output_directory": str(old),
        "monotonic_origin": time.monotonic(),
        "cpu": 4,
        "venv": sys.prefix,
        "synthetic_canary": False,
    }
    request_path = tmp_path / "request.json"
    campaign.write_json(request_path, request)
    monkeypatch.setattr(worker.os, "sched_getaffinity", lambda pid: {4})
    assert worker.main(request_path) == 1
    assert expected == {p.name: p.read_bytes() for p in old.iterdir()}


@pytest.mark.parametrize(
    "key,value",
    [
        ("cpu", 5),
        ("timeout_seconds", 900),
        ("seed", 8),
        ("seed", True),
        ("input_sha256", "changed"),
        ("instrument", False),
        ("bindings", {"A": "B"}),
        ("declarations", {}),
        ("engine_identity", {}),
        ("case_id", "different"),
        ("venv", "/elsewhere"),
        ("campaign_manifest_sha256", "changed"),
        ("input", "/tmp/wrong.json"),
        ("output_directory", "/tmp/other-output"),
    ],
)
def test_frozen_request_rejects_changes(tmp_path, key, value):
    request, problem, _ = fixture_request(tmp_path)
    request[key] = value
    with pytest.raises(RuntimeError):
        authorization.authorize_request(request, problem)


@pytest.mark.parametrize("change", ["user", "protocol", "coverage", "duplicate", "missing"])
def test_manifest_must_include_independent_authorization_and_coverage(tmp_path, change):
    request, problem, manifest = fixture_request(tmp_path)
    if change == "user":
        manifest["authorization"]["user_authorized"] = False
    elif change == "protocol":
        manifest["protocol"]["main_run_authorized"] = False
    elif change == "coverage":
        manifest["entries"][0]["original_assumptions_covered"] = False
    elif change == "duplicate":
        manifest["entries"].append(copy.deepcopy(manifest["entries"][0]))
    else:
        manifest["entries"] = []
    path = Path(request["campaign_manifest"])
    campaign.write_json(path, manifest)
    request["campaign_manifest_sha256"] = campaign.sha256(path)
    with pytest.raises(RuntimeError):
        authorization.authorize_request(request, problem)


def test_seal_verification_is_readonly_and_rejects_changed_bytes(tmp_path):
    raw = tmp_path / "raw.json"
    raw.write_text('{"a":1}')
    seal = tmp_path / "SHA256SUMS"
    seal.write_text(f"{campaign.sha256(raw)}  raw.json\n")
    before = {p.name: p.read_bytes() for p in tmp_path.iterdir()}
    campaign.check_seal(tmp_path)
    assert before == {p.name: p.read_bytes() for p in tmp_path.iterdir()}
    raw.write_text('{"a":2}')
    with pytest.raises(RuntimeError, match="Invalid sealed"):
        campaign.check_seal(tmp_path)


def test_seal_rejects_path_escape(tmp_path):
    outside = tmp_path / "outside.json"
    outside.write_text("{}")
    root = tmp_path / "inside"
    root.mkdir()
    (root / "SHA256SUMS").write_text(f"{campaign.sha256(outside)}  ../outside.json\n")
    with pytest.raises(RuntimeError, match="Invalid sealed"):
        campaign.check_seal(root)


def test_copy_requires_expected_hash_and_never_overwrites(tmp_path):
    source, destination = tmp_path / "source", tmp_path / "destination"
    source.write_text("unchanged")
    with pytest.raises(RuntimeError, match="Input changed"):
        campaign.copy_checked(source, destination, "bad-digest")
    campaign.copy_checked(source, destination, campaign.sha256(source))
    assert destination.read_text() == "unchanged"
    with pytest.raises(RuntimeError, match="overwrite"):
        campaign.copy_checked(source, destination, campaign.sha256(source))


def test_incomplete_run_is_never_automatically_retried(tmp_path, monkeypatch):
    manifest = {"entries": [{"case_id": "TEST"}], "seeds": [0]}
    campaign.write_json(tmp_path / "campaign-manifest.json", manifest)
    (tmp_path / "geosolver/runs/TEST/0").mkdir(parents=True)
    calls = []
    monkeypatch.setattr(campaign, "assert_identity", lambda *args: None)
    monkeypatch.setattr(campaign, "run_geosolver", lambda *args: calls.append(args))
    with pytest.raises(RuntimeError, match="Incomplete run"):
        campaign.run_campaign(tmp_path)
    assert not calls


def test_sealed_campaign_cannot_run_again(tmp_path):
    (tmp_path / "RAW_SHA256SUMS").write_text("")
    with pytest.raises(RuntimeError, match="already sealed"):
        campaign.run_campaign(tmp_path)


def test_production_launcher_uses_one_cpu_and_frozen_worker_request(tmp_path, monkeypatch):
    _, _, manifest = fixture_request(tmp_path)
    manifest["geo_environment"]["prefix"] = sys.prefix
    campaign.write_json(tmp_path / "campaign-manifest.json", manifest)
    entry = manifest["entries"][0]
    captured = {}
    resources = {
        "cancelled": False,
        "timed_out": False,
        "affinity_violations": [],
        "descendants_remaining_at_leader_exit": False,
        "returncode": 0,
        "wall_seconds": 0.1,
        "cpu_seconds": 0.05,
    }

    def launch(command, **kwargs):
        request_path = Path(command[-1])
        captured.update(command=command, request=campaign.read_json(request_path), **kwargs)
        campaign.write_json(
            request_path.parent / "child-result.json", {"outcome": "completed", "model_files": []}
        )
        return object()

    monkeypatch.setattr(campaign.subprocess, "Popen", launch)
    monkeypatch.setattr(campaign.gmb, "host_snapshot", lambda cpu: {"cpu": cpu})
    monkeypatch.setattr(campaign.gmb, "monitor", lambda *args: resources)
    record = campaign.run_geosolver(tmp_path, manifest, entry, 0)
    request = captured["request"]
    authorization.authorize_request(request, {"id": entry["case_id"]})
    assert request["synthetic_canary"] is False
    assert request["timeout_seconds"] == 180
    assert captured["command"][:3] == ["taskset", "--cpu-list", "4"]
    assert captured["start_new_session"] is True
    assert captured["cwd"] == campaign.REPO
    assert captured["env"]["CUDA_VISIBLE_DEVICES"] == "-1"
    assert captured["env"]["PYTHONHASHSEED"] == "0"
    assert all(captured["env"][key] == "1" for key in campaign.THREAD_VARIABLES)
    assert record["manifest_sha256"] == campaign.sha256(tmp_path / "campaign-manifest.json")
    assert record["process"] is resources


def test_production_protocol_does_not_change_agreed_comparison():
    protocol = json.loads((campaign.HERE / "protocol.json").read_text())
    assert protocol["main_run_authorized"]
    assert protocol["common_tolerance"] == "1e-6"
    assert protocol["sensitivity_tolerances"] == ["1e-3", "1e-6", "1e-9"]
    assert protocol["time_limit_seconds"] == 180
    assert protocol["initial_seeds"] == [0, 1, 2]
    assert protocol["parallel_jobs"] == 1
    assert not protocol["automatic_failure_retry"]
