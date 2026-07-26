from geotarget.doctor import diagnose
from geotarget.engine import ENGINE_HASH, verify_engine


def test_frozen_product_manifest_matches_every_engine_file() -> None:
    assert verify_engine() == []


def test_doctor_reports_locked_runtime() -> None:
    report = diagnose()
    assert report["ok"]
    assert report["engine_hash"] == ENGINE_HASH
    assert report["nemo_locked"] is True
