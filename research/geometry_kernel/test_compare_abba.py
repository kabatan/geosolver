from __future__ import annotations

from copy import deepcopy

from research.geometry_kernel.compare_abba import compare_abba


def _measurement(wall: int, *, digest: str = "same") -> dict[str, object]:
    phase = {
        "wall_ns": wall,
        "cpu_ns": wall,
        "completed": 10,
        "throughput_per_second": 1.0,
    }
    return {
        "schema_version": 1,
        "config": {"probes": 1},
        "input_stream_digest": "input",
        "skipped_source_sha256": [],
        "rows": [
            {
                "source_sha256": "source",
                "backend": "raw",
                "input_digest": digest,
                "residual_digest": digest,
                "callback_digest": digest,
                "routing": {
                    "case_specific": False,
                    "corpus_metadata_read": False,
                    "problem_identity_read": False,
                },
                "residual": deepcopy(phase),
                "callback": deepcopy(phase),
            }
        ],
    }


def test_abba_uses_geometric_pair_and_checks_same_work() -> None:
    report = compare_abba(
        _measurement(100),
        _measurement(50),
        _measurement(50),
        _measurement(100),
    )

    assert report["same_work"] is True
    assert report["routing_contract_satisfied"] is True
    assert report["aggregates"]["callback"]["wall_ns"][
        "case_geometric_mean_ratio"
    ] == 0.5
    assert report["no_structural_group_regression"] is True


def test_abba_reports_digest_mismatch() -> None:
    report = compare_abba(
        _measurement(100),
        _measurement(50, digest="different"),
        _measurement(50),
        _measurement(100),
    )

    assert report["same_work"] is False
    assert {item["field"] for item in report["mismatches"]} == {
        "input_digest",
        "residual_digest",
        "callback_digest",
    }
