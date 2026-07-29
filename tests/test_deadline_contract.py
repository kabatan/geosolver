from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from geotarget.engine import _should_continue_initial_work

ENGINE_SOLVER = Path(__file__).resolve().parents[1] / "src/geotarget/_engine/runtime/solver"
sys.path.insert(0, str(ENGINE_SOLVER))
reference_entrypoint = importlib.import_module("geotarget.reference_entrypoint")
_committed_result = reference_entrypoint._committed_result
_limits = reference_entrypoint._limits


def test_optimized_watchdog_separates_algorithm_startup_and_finalize_time() -> None:
    limits = _limits(
        "execute",
        algorithm_seconds=180.0,
        startup_grace_seconds=30.0,
        finalize_grace_seconds=12.0,
    )

    assert limits.timeout_seconds == 222.0
    assert _limits("execute").timeout_seconds == 183.0
    assert _limits("dry").timeout_seconds == 8.0


def test_timeout_recovery_accepts_only_a_committed_source_bound_result(
    tmp_path: Path,
) -> None:
    output = tmp_path / "output"
    output.mkdir()
    command = [
        "worker",
        "--source-sha256",
        "a" * 64,
        "--output",
        str(output),
    ]
    partial = output / "RESULT.json.tmp"
    partial.write_text("{}", encoding="utf-8")
    assert not _committed_result(command)

    result = output / "RESULT.json"
    result.write_text(
        json.dumps(
            {
                "completed": True,
                "source_sha256": "a" * 64,
                "source_bytes_unchanged": True,
            }
        ),
        encoding="utf-8",
    )
    assert _committed_result(command)

    document = json.loads(result.read_text(encoding="utf-8"))
    document["source_sha256"] = "b" * 64
    result.write_text(json.dumps(document), encoding="utf-8")
    assert not _committed_result(command)


def test_initial_continuation_finishes_prefix_but_stops_after_answer() -> None:
    assert _should_continue_initial_work(
        has_pending_starts=True,
        has_deferred_candidates=True,
        descriptor_count=1,
    )
    assert not _should_continue_initial_work(
        has_pending_starts=False,
        has_deferred_candidates=True,
        descriptor_count=1,
    )
    assert _should_continue_initial_work(
        has_pending_starts=False,
        has_deferred_candidates=True,
        descriptor_count=0,
    )
    assert not _should_continue_initial_work(
        has_pending_starts=False,
        has_deferred_candidates=False,
        descriptor_count=0,
    )


def test_committed_timeout_recovery_is_optimized_opt_in_only(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output = tmp_path / "output"
    output.mkdir()
    (output / "RESULT.json").write_text(
        json.dumps(
            {
                "completed": True,
                "source_sha256": "a" * 64,
                "source_bytes_unchanged": True,
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        reference_entrypoint,
        "run_guarded",
        lambda *_args, **_kwargs: SimpleNamespace(
            accepted_output=False,
            classification="TIMEOUT",
            stdout_tail="",
            stderr_tail="",
        ),
    )
    base = [
        "reference_entrypoint",
        "--phase",
        "execute",
        "--status",
        str(tmp_path / "status.json"),
    ]
    command = [
        "--",
        "worker",
        "--source-sha256",
        "a" * 64,
        "--output",
        str(output),
    ]

    monkeypatch.setattr(sys, "argv", [*base, *command])
    assert reference_entrypoint.main() == 1
    monkeypatch.setattr(
        sys,
        "argv",
        [*base, "--accept-committed-on-timeout", *command],
    )
    assert reference_entrypoint.main() == 0
