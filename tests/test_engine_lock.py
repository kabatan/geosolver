from __future__ import annotations

from geosolver.runtime.integrity import load_engine_lock, verify_engine_lock


def test_engine_lock_matches_single_engine_protocol_v3() -> None:
    lock = load_engine_lock()
    valid, detail = verify_engine_lock()

    assert valid, detail
    assert lock["schema_version"] == 2
    assert lock["artifact_protocol_version"] == 3
    assert set(lock["engines"]) == {"standard"}
    assert lock["engines"]["standard"]["completeness"] == "unknown"
