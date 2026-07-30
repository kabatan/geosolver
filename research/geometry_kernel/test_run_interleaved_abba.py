from __future__ import annotations

from research.geometry_kernel.run_interleaved_abba import _combine


def _document(source: str) -> dict[str, object]:
    return {
        "schema_version": "measurement/v1",
        "repository": "/repo",
        "git_commit": "a" * 40,
        "config": {"probes": 8},
        "input_stream_digest": "1" * 64,
        "output_stream_digest": "2" * 64,
        "skipped_source_sha256": [],
        "peak_rss_kib": 10,
        "rows": [{"source_sha256": source}],
    }


def test_combine_preserves_every_unique_case() -> None:
    combined = _combine([_document("a" * 64), _document("b" * 64)], chunk_size=8)

    assert combined["completed_cases"] == 2
    assert combined["config"]["interleave_chunk_size"] == 8
    assert [row["source_sha256"] for row in combined["rows"]] == ["a" * 64, "b" * 64]
