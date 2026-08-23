from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from geosolver.engine import EngineFailure, EngineResourceExhausted, EngineRunner
from geosolver.platform import processes
from geosolver.runtime.protocol import WorkerArtifact, WorkerError
from geosolver.runtime.worker import _atomic_write


class FinishedProcess:
    pid = 12345

    def __init__(self, returncode: int) -> None:
        self.returncode = returncode

    def poll(self) -> int:
        return self.returncode

    def communicate(self) -> tuple[str, str]:
        return "", "worker log"


class RunningProcess(FinishedProcess):
    def poll(self) -> None:
        return None


@pytest.mark.parametrize(
    ("artifact_kind", "returncode", "expected_code"),
    [
        ("missing", 9, "artifact_missing"),
        ("corrupt", 0, "artifact_invalid"),
        ("failed", 1, "worker_crashed"),
    ],
)
def test_runner_rejects_abnormal_worker_artifacts(
    monkeypatch: pytest.MonkeyPatch,
    artifact_kind: str,
    returncode: int,
    expected_code: str,
) -> None:
    def spawn(command: list[str], **kwargs: Any) -> FinishedProcess:
        output_path = Path(command[command.index("--output") + 1])
        if artifact_kind == "corrupt":
            output_path.write_text("{", encoding="utf-8")
        elif artifact_kind == "failed":
            output_path.write_text(
                WorkerArtifact(
                    status="failed",
                    error=WorkerError(code="worker_crashed", message="worker stopped"),
                ).model_dump_json(),
                encoding="utf-8",
            )
        return FinishedProcess(returncode)

    monkeypatch.setattr("geosolver.engine.runner.spawn_process", spawn)
    monkeypatch.setattr("geosolver.engine.runner.set_affinity", lambda *args: None)

    with pytest.raises(EngineFailure) as caught:
        EngineRunner().run({}, seed=0, cores=1, time_limit_seconds=180, prefer_fast=True)

    assert caught.value.code == expected_code


def test_atomic_artifact_update_supports_unicode_and_spaces(tmp_path: Path) -> None:
    output = tmp_path / "日本語 を含む場所" / "探索 結果.json"
    artifact = WorkerArtifact(status="completed", exact_candidates=["1"])

    _atomic_write(output, artifact)

    assert json.loads(output.read_text(encoding="utf-8"))["status"] == "completed"
    assert not list(output.parent.glob("*.tmp"))


def test_runner_stops_a_worker_tree_at_the_memory_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    process = RunningProcess(returncode=0)
    terminated: list[object] = []
    monkeypatch.setattr("geosolver.engine.runner.spawn_process", lambda *args, **kwargs: process)
    monkeypatch.setattr("geosolver.engine.runner.set_affinity", lambda *args: None)
    monkeypatch.setattr("geosolver.engine.runner.process_tree_memory_bytes", lambda pid: 101)
    monkeypatch.setattr(
        "geosolver.engine.runner.terminate_process_tree", lambda target: terminated.append(target)
    )

    with pytest.raises(EngineResourceExhausted) as caught:
        EngineRunner(memory_limit_bytes=100).run(
            {}, seed=0, cores=1, time_limit_seconds=180, prefer_fast=True
        )

    assert caught.value.code == "memory_limit_exceeded"
    assert terminated == [process]


@pytest.mark.parametrize(
    ("platform_name", "expected_option", "unexpected_option"),
    [
        ("win32", "creationflags", "start_new_session"),
        ("darwin", "start_new_session", "creationflags"),
        ("linux", "start_new_session", "creationflags"),
    ],
)
def test_spawn_process_uses_platform_process_groups(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    platform_name: str,
    expected_option: str,
    unexpected_option: str,
) -> None:
    captured: dict[str, Any] = {}
    sentinel = object()

    def popen(command: list[str], **options: Any) -> object:
        captured.update(options)
        return sentinel

    monkeypatch.setattr(processes.sys, "platform", platform_name)
    monkeypatch.setattr(processes.subprocess, "CREATE_NEW_PROCESS_GROUP", 512, raising=False)
    monkeypatch.setattr(processes.subprocess, "Popen", popen)

    result = processes.spawn_process(
        ["python", "-m", "geosolver.runtime.worker"], cwd=tmp_path, env={}
    )

    assert result is sentinel
    assert expected_option in captured
    assert unexpected_option not in captured
    if platform_name == "win32":
        assert captured["creationflags"] == 512
    else:
        assert captured["start_new_session"] is True
