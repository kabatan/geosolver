from __future__ import annotations

import fcntl
import os

from research.geometry_kernel import run_frozen_arm_under_parent_lock as locked


def test_parent_lock_detector_observes_real_flock(monkeypatch, tmp_path) -> None:
    lock_path = tmp_path / "benchmark.lock"
    monkeypatch.setattr(locked, "BENCHMARK_LOCK", lock_path)
    with lock_path.open("a+", encoding="utf-8") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        monkeypatch.setattr(os, "getppid", os.getpid)

        assert locked._parent_holds_benchmark_lock() is True


def test_parent_lock_detector_rejects_unlocked_parent(monkeypatch, tmp_path) -> None:
    lock_path = tmp_path / "benchmark.lock"
    lock_path.touch()
    monkeypatch.setattr(locked, "BENCHMARK_LOCK", lock_path)

    assert locked._parent_holds_benchmark_lock() is False
