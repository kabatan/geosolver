"""The optional GMB launcher must not import/install GMB in GeoSolver's environment."""

from __future__ import annotations

import ast
import importlib.util
import os
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "benchmarks/gmb/environment.py"
SPEC = importlib.util.spec_from_file_location("gmb_environment_test", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
gmb = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(gmb)


def test_launcher_remains_python38_parseable():
    ast.parse(SCRIPT.read_text(), feature_version=(3, 8))


def test_child_environment_isolated_without_mutating_parent(monkeypatch, tmp_path):
    monkeypatch.setenv("PYTHONPATH", "/unwanted/geosolver/src")
    monkeypatch.setenv("PYTHONHOME", "/unwanted/python")
    monkeypatch.setenv("CUDA_VISIBLE_DEVICES", "0,1")
    monkeypatch.setenv("OMP_NUM_THREADS", "8")
    env = gmb.child_environment(tmp_path)

    assert "PYTHONPATH" not in env and "PYTHONHOME" not in env
    assert env["CUDA_VISIBLE_DEVICES"] == "-1"
    assert env["PYTHONNOUSERSITE"] == "1"
    assert env["MPLBACKEND"] == "Agg"
    assert env["MPLCONFIGDIR"] == str(tmp_path / "matplotlib")
    assert all(env[key] == "1" for key in gmb.THREAD_VARIABLES)
    assert os.environ["OMP_NUM_THREADS"] == "8"
    assert os.environ["CUDA_VISIBLE_DEVICES"] == "0,1"


def test_cpu_selection_rejects_unavailable_cpu(monkeypatch):
    monkeypatch.setattr(gmb.os, "sched_getaffinity", lambda _: {3, 5}, raising=False)
    assert gmb.choose_cpu(None) == 3
    assert gmb.choose_cpu(5) == 5
    with pytest.raises(ValueError, match="outside"):
        gmb.choose_cpu(4)


def test_modified_upstream_source_is_rejected(monkeypatch):
    def git(args, **kwargs):
        return gmb.COMMIT + "\n" if args[3] == "rev-parse" else " M src/builder.py\n"

    monkeypatch.setattr(gmb.subprocess, "check_output", git)
    with pytest.raises(RuntimeError, match="local changes"):
        gmb.source_identity()


@pytest.mark.skipif(sys.platform != "linux", reason="Linux process group launcher")
def test_owned_process_group_is_stopped():
    process = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(30)"], start_new_session=True
    )
    try:
        gmb.terminate_group(process)
        assert process.poll() is not None
    finally:
        if process.poll() is None:
            process.kill()
            process.wait()
