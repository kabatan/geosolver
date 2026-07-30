from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys


HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import candidate_v4  # noqa: E402
import worker_v4  # noqa: E402


PYTHON = Path("/home/kabatan/work/solver/.venv/bin/python")


def _source(tmp_path: Path) -> tuple[Path, str]:
    source = tmp_path / "source.json"
    source.write_text(
        json.dumps({"task": "solve", "variables": {"names": ["x"]}}),
        encoding="utf-8",
    )
    return source, hashlib.sha256(source.read_bytes()).hexdigest()


def _dry_arguments(source: Path, digest: str, output: Path) -> list[str]:
    return [
        "--source",
        str(source),
        "--source-sha256",
        digest,
        "--total-seconds",
        "15",
        "--search-seconds",
        "6",
        "--starts",
        "8",
        "--callbacks-per-start",
        "64",
        "--aggregate-callback-cap",
        "512",
        "--seed",
        "0",
        "--cpu",
        "7",
        "--output",
        str(output),
    ]


def test_control_closure_and_entrypoint_are_hash_bound() -> None:
    worker_v4._verify_control_closure(worker_v4.DEFAULT_CONTROL_ROOT)
    entrypoint = (
        worker_v4.DEFAULT_CONTROL_ROOT / worker_v4.CONTROL_RELATIVE_ENTRYPOINT
    )
    assert worker_v4._sha256(entrypoint) == (
        worker_v4.EXPECTED_CONTROL_ENTRYPOINT_SHA256
    )


def test_v4_dry_plan_is_byte_equal_to_direct_common_control(tmp_path: Path) -> None:
    source, digest = _source(tmp_path)
    output = tmp_path / "dry"
    arguments = _dry_arguments(source, digest, output)
    environment = {
        **os.environ,
        "PYTHONHASHSEED": "0",
        "OMP_NUM_THREADS": "1",
        "OPENBLAS_NUM_THREADS": "1",
        "MKL_NUM_THREADS": "1",
    }
    control = (
        worker_v4.DEFAULT_CONTROL_ROOT / worker_v4.CONTROL_RELATIVE_ENTRYPOINT
    )
    subprocess.run(
        [str(PYTHON), str(control), *arguments],
        check=True,
        capture_output=True,
        text=True,
        env=environment,
    )
    direct_plan = (output / "PLAN.json").read_bytes()
    subprocess.run(
        [str(PYTHON), str(HERE / "worker_v4.py"), *arguments],
        check=True,
        capture_output=True,
        text=True,
        env=environment,
    )
    assert (output / "PLAN.json").read_bytes() == direct_plan


def test_common_control_snapshot_is_byte_exact(tmp_path: Path) -> None:
    output = tmp_path / "output"
    output.mkdir()
    payload = b'{"completed":true,"control":"exact"}\n'
    (output / "RESULT.json").write_bytes(payload)
    digest = candidate_v4.snapshot_common_control_result(output)
    assert digest == hashlib.sha256(payload).hexdigest()
    assert (
        output / candidate_v4.COMMON_CONTROL_SNAPSHOT
    ).read_bytes() == payload


@dataclass(frozen=True)
class Candidate:
    endpoint: tuple[float, ...]
    endpoint_sha256: str
    residual_inf: float
    provisional_target: float | None


class FakeControlBase:
    def _fresh_replay_candidates(self, *_args, **_kwargs):
        return (
            Candidate((0.0,), "a", 1e-12, None),
            Candidate((1.0,), "b", 2e-12, None),
        )


def test_control_side_adapter_handles_delayed_unknown_targets() -> None:
    adapter = candidate_v4._CommonControlSideBase(FakeControlBase())
    rows = adapter._fresh_replay_candidates({}, [], hard_deadline=1.0)
    assert [row.provisional_target for row in rows] == [0.0, 0.0]
    assert [row.endpoint_sha256 for row in rows] == ["a", "b"]


def test_control_arguments_are_forwarded_verbatim_except_overlay_root() -> None:
    argv = [
        "--source",
        "source.json",
        "--source-sha256",
        "a" * 64,
        "--total-seconds",
        "30",
        "--search-seconds",
        "20",
        "--seed",
        "2",
        "--cpu",
        "7",
        "--output",
        "output",
        "--control-root",
        "/tmp/control",
        "--execute",
        "--plan-sha256",
        "b" * 64,
    ]
    _observed, forwarded = worker_v4._observe_arguments(argv)
    assert forwarded == argv[:14] + argv[16:]


def test_v4_wrapper_does_not_patch_common_control_and_is_truth_blind() -> None:
    wrapper = (HERE / "worker_v4.py").read_text(encoding="utf-8")
    mechanism = (HERE / "candidate_v4.py").read_text(encoding="utf-8")
    for forbidden in (
        "control.CHAMPION.BASE._service_candidates =",
        "control.CHAMPION.BASE._plan =",
        "control.CHAMPION.BASE.PYTHON =",
        "control.CHAMPION.BASE.SELECTION_RESERVE_SECONDS =",
    ):
        assert forbidden not in wrapper
    assert "gold_targets" not in mechanism
    assert "case_id" not in mechanism
    assert '.get("known_target_count"' not in mechanism
    assert '["known_target_count"]' not in mechanism
