from __future__ import annotations

import json
import os
import stat
from types import SimpleNamespace

import pytest

import root_exact_gate as gate


def test_direct_worker_without_inherited_coordinator_fds_fails_closed(tmp_path):
    with pytest.raises(gate.GateFailure, match="inherited coordinator"):
        gate._authorize_worker(
            authorization_fd=0,
            lock_fd=1,
            temporary_root=tmp_path,
            work_item=tmp_path / "item.json",
            output=tmp_path / "result.json",
            runner_sha256="0" * 64,
        )


def test_structurally_valid_same_uid_wrapper_cannot_forge_root_capability(monkeypatch):
    read_fd, write_fd = os.pipe()
    capability = {
        "schema_version": "geotarget.cross-endpoint-vieta-worker-capability/v2",
        "nonce": "a" * 64,
        "issuer_effective_uid": 0,
        "coordinator_pid": os.getpid(),
        "runner_sha256": "b" * 64,
        "temporary_root": "/tmp/forged",
        "temporary_root_device": 1,
        "temporary_root_inode": 2,
        "work_item": "/tmp/forged/item.json",
        "work_item_sha256": "c" * 64,
        "output": "/tmp/forged/result.json",
    }
    os.write(write_fd, json.dumps(capability).encode())
    os.close(write_fd)
    real_fstat = os.fstat

    def same_uid_fifo(fd):
        observed = real_fstat(fd)
        if fd == read_fd:
            return SimpleNamespace(st_mode=stat.S_IFIFO, st_uid=1000)
        return observed

    monkeypatch.setattr(gate.os, "fstat", same_uid_fifo)
    with pytest.raises(gate.GateFailure, match="root-owned one-shot FIFO"):
        gate._read_root_issued_capability(read_fd)


def test_unprivileged_coordinator_cannot_issue_worker_capability(monkeypatch):
    monkeypatch.setattr(gate.os, "geteuid", lambda: 1000)
    with pytest.raises(gate.GateFailure, match="OS-root benchmark owner"):
        gate._guarded_worker(
            guard=None,
            work_item=None,
            output=None,
            runner_sha256="0" * 64,
            degree=2,
            per_endpoint_seconds=1.0,
            lock_fd=9,
            temporary_root=None,
        )


def test_private_result_requires_materialized_union(tmp_path):
    assert gate._private_result(tmp_path / "absent.json", expected_subset_sha="0" * 64) is None
