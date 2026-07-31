from __future__ import annotations

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


def test_private_result_requires_materialized_union(tmp_path):
    assert gate._private_result(tmp_path / "absent.json", expected_subset_sha="0" * 64) is None
