"""Measurement contracts tested without importing or running the IMO inputs."""

from __future__ import annotations

import ast
import importlib
import json
import os
import subprocess
import sys
import time
from collections import namedtuple
from pathlib import Path
from types import SimpleNamespace

import pytest

from tests.paths import REPO_ROOT

# The console-script pytest entrypoint need not include the repository on sys.path.
sys.path.insert(0, str(REPO_ROOT))
try:
    campaign = importlib.import_module("benchmarks.gmb.campaign")
    worker = importlib.import_module("benchmarks.gmb.measurement_worker")
finally:
    sys.path.pop(0)
install_recording_optimizer = worker.install_recording_optimizer
json_value = worker.json_value


def test_worker_remains_python38_parseable():
    ast.parse(campaign.WORKER.read_text(), feature_version=(3, 8))


def test_coordinates_and_nonfinite_diagnostics_are_serializable():
    point = namedtuple("Point", "x y")
    raw = json_value({"A": point(1.5, float("nan")), "B": point(0, float("inf"))})
    assert raw["A"] == {"x": 1.5, "y": {"nonfinite": "nan"}}
    assert raw["B"]["y"] == {"nonfinite": "inf"}
    json.dumps(raw, allow_nan=False)


def process_record(**updates):
    return dict(
        cancelled=False,
        timed_out=False,
        returncode=0,
        affinity_violations=[],
        descendants_remaining_at_leader_exit=False,
        **updates,
    )


@pytest.mark.parametrize("flag,expected", [("timed_out", "timeout"), ("cancelled", "cancelled")])
def test_partial_models_do_not_turn_timeout_or_cancel_into_success(flag, expected):
    process = process_record()
    process[flag] = True
    assert (
        campaign.outcome(process, {"outcome": "model_returned", "models_returned": 1}) == expected
    )


def test_exit_zero_is_not_itself_a_model():
    assert campaign.outcome(process_record(), None) == "crash"
    assert (
        campaign.outcome(process_record(), {"outcome": "no_model", "models_returned": 0})
        == "no_model"
    )
    assert (
        campaign.outcome(process_record(), {"outcome": "model_returned", "models_returned": 1})
        == "model_returned"
    )


def test_affinity_violation_is_separate_from_success():
    process = process_record()
    process["affinity_violations"] = [[1, 2]]
    assert (
        campaign.outcome(process, {"outcome": "model_returned", "models_returned": 1})
        == "resource_violation"
    )


def test_phase_aggregation_preserves_incomplete_phases_and_errors():
    events = [
        {"event": "solve_start", "elapsed_seconds": 1},
        {"event": "train_start", "elapsed_seconds": 2},
        {"event": "train_error", "elapsed_seconds": 3},
        {"event": "train_start", "elapsed_seconds": 4},
    ]
    result = campaign.event_summary(events)
    assert result["train_completed_seconds"] == 1
    assert result["train_incomplete_calls"] == 1
    assert result["solve_completed_seconds"] is None
    assert result["solve_incomplete_calls"] == 1
    assert result["train_errors"] == 1


def test_recording_hook_does_not_change_calls_or_suppress_train_errors():
    calls = []
    model = object()

    class Original:
        def __init__(self):
            calls.append("init")

        def train(self, init_name):
            calls.append(init_name)
            raise ValueError("upstream failure")

        def get_model(self):
            calls.append("get_model")
            return model

    builder = SimpleNamespace(
        TfOptimizer=Original, tf=SimpleNamespace(set_random_seed=calls.append)
    )
    events = []
    saved = []
    install_recording_optimizer(
        builder, 7, lambda name, **kwargs: events.append(name), saved.append
    )
    optimizer = builder.TfOptimizer()
    with pytest.raises(ValueError, match="upstream failure"):
        optimizer.train("init-0")
    assert optimizer.get_model() is model
    assert calls == [7, "init", "init-0", "get_model"]
    assert events == ["train_start", "train_error"]
    assert saved == [model]


def test_unsupported_rows_are_not_zero_time_or_success(tmp_path):
    manifest = {
        "entries": [
            {
                "case_id": "missing",
                "input": None,
                "availability": "unsupported",
                "reason": "variable object count",
            }
        ],
        "seeds": [0],
    }
    rows = campaign.rows_from_raw(tmp_path, manifest)
    assert len(rows) == 1
    assert rows[0]["outcome"] == "unsupported"
    assert "wall_seconds" not in rows[0]


@pytest.mark.skipif(sys.platform != "linux", reason="Linux wait4 and CPU affinity")
def test_timeout_collects_cpu_rss_and_reaps_owned_process():
    cpu = min(os.sched_getaffinity(0))
    process = subprocess.Popen(
        ["taskset", "--cpu-list", str(cpu), sys.executable, "-c", "while True: pass"],
        start_new_session=True,
    )
    result = campaign.monitor(process, time.monotonic(), 0.15, cpu)
    assert result["timed_out"]
    assert result["wall_seconds"] < 2
    assert result["cpu_seconds"] > 0
    assert result["peak_rss_bytes"] > 0
    assert not Path(f"/proc/{process.pid}").exists()
    assert not result["descendants_remaining_at_leader_exit"]


def test_inventory_requires_all_36_inputs(monkeypatch, tmp_path):
    monkeypatch.setattr(campaign.env, "SOURCE", tmp_path)
    with pytest.raises(RuntimeError, match="exactly 36"):
        campaign.inventory()


def test_changed_input_is_detected(monkeypatch, tmp_path):
    (tmp_path / "input.smt2").write_text("original")
    manifest = {
        "identity_files": {},
        "source_files": {},
        "entries": [
            {
                "case_id": "test",
                "input": "input.smt2",
                "input_sha256": campaign.sha256(tmp_path / "input.smt2"),
            }
        ],
    }
    monkeypatch.setattr(campaign.env, "source_identity", lambda: None)
    (tmp_path / "input.smt2").write_text("changed")
    with pytest.raises(RuntimeError, match="changed input"):
        campaign.assert_identity(tmp_path, manifest)
