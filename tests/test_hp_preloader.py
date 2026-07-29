from __future__ import annotations

import os
import signal
import sys
from pathlib import Path

import pytest

from geotarget.hp_preloader import (
    SOCKET_ENV,
    PersistentHpPool,
    delegated_run,
    socket_path,
)

PACKAGE = Path(__file__).parents[1] / "src/geotarget"
SOLVER = PACKAGE / "_engine/runtime/solver"
WORKER = (
    SOLVER
    / "research/experiments/EXP-V15-243-001/candidates"
    / "point_on_circle_periodic_semantics/champion_composition_worker_no_1280.py"
)


def _cpu() -> int:
    eligible = sorted(cpu for cpu in os.sched_getaffinity(0) if cpu < 16)
    if not eligible:
        pytest.skip("the frozen HP bridge only accepts CPU ordinals 0 through 15")
    return eligible[0]


def test_pool_restarts_a_crashed_per_core_preloader() -> None:
    cpu = _cpu()
    with PersistentHpPool((cpu,), WORKER, {}) as pool:
        original = pool.processes[cpu]
        os.kill(original.pid, signal.SIGKILL)
        original.wait(timeout=2.0)
        pool.ensure()
        replacement = pool.processes[cpu]
        assert replacement.pid != original.pid
        assert replacement.poll() is None
        assert socket_path(pool.directory, cpu).is_socket()


def test_candidate_failure_is_fork_isolated_and_daemon_survives(monkeypatch) -> None:
    sys.path.insert(0, str(SOLVER))
    from research.infrastructure.memory_safety.safe_subprocess import Limits

    cpu = _cpu()
    limits = Limits(
        timeout_seconds=3.0,
        rss_bytes=480 * 1024**2,
        address_space_bytes=1536 * 1024**2,
        data_bytes=1024 * 1024**2,
    )
    with PersistentHpPool((cpu,), WORKER, {}) as pool:
        monkeypatch.setenv(SOCKET_ENV, str(pool.directory))
        command = ["taskset", "-c", str(cpu), sys.executable, str(WORKER)]
        first = delegated_run(command, limits=limits)
        second = delegated_run(command, limits=limits)
        assert first.classification == second.classification == "NONZERO_EXIT"
        assert first.returncode == second.returncode == 2
        assert pool.processes[cpu].poll() is None


def test_non_hp_command_uses_original_runner(monkeypatch) -> None:
    marker = object()

    def original(command, **kwargs):
        assert command == ["true"]
        return marker

    assert delegated_run(["true"], limits=object(), original=original) is marker


def test_broker_session_preloader_failure_is_fail_closed(monkeypatch, tmp_path: Path) -> None:
    sys.path.insert(0, str(SOLVER))
    from research.infrastructure.memory_safety.safe_subprocess import Limits

    called = False

    def original(command, **kwargs):
        nonlocal called
        called = True

    cpu = _cpu()
    monkeypatch.setenv(SOCKET_ENV, str(tmp_path / "missing"))
    monkeypatch.setenv("GEOTARGET_RUNTIME_BROKER_SESSION", "session")
    result = delegated_run(
        ["taskset", "-c", str(cpu), sys.executable, str(WORKER)],
        limits=Limits(
            timeout_seconds=1,
            rss_bytes=480 * 1024**2,
            address_space_bytes=1536 * 1024**2,
            data_bytes=1024 * 1024**2,
        ),
        original=original,
    )
    assert not called
    assert result.classification == "PRELOADER_ERROR"
    assert result.accepted_output is False
