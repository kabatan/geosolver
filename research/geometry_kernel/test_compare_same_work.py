from __future__ import annotations

from copy import deepcopy

from compare_same_work import compare


def _measurement() -> dict:
    timing = {"completed": 8, "wall_ns": 100, "cpu_ns": 90, "throughput_per_second": 8.0}
    return {
        "schema_version": "geotarget.geometry-kernel-same-work/v1",
        "config": {"probes": 4, "repeats": 2},
        "input_stream_digest": "a" * 64,
        "rows": [
            {
                "source_sha256": "b" * 64,
                "structural_family": "raw_libmp:x",
                "input_digest": "c" * 64,
                "residual_digest": "d" * 64,
                "callback_digest": "e" * 64,
                "residual": timing,
                "callback": timing,
            }
        ],
    }


def test_compare_requires_identical_observations() -> None:
    control = _measurement()
    candidate = deepcopy(control)
    candidate["rows"][0]["residual"]["wall_ns"] = 80
    candidate["rows"][0]["callback"]["wall_ns"] = 90
    report = compare(control, candidate)
    assert report["same_work"] is True
    assert report["overall_geometric_mean_wall_ratio"] < 1.0


def test_compare_reports_bitwise_mismatch() -> None:
    control = _measurement()
    candidate = deepcopy(control)
    candidate["rows"][0]["callback_digest"] = "f" * 64
    assert compare(control, candidate)["same_work"] is False
