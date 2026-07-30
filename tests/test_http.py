import threading
import time

from fastapi.testclient import TestClient

from geotarget.api import Job, JobManager, SolveRequest, app
from geotarget.models import ResourceUsage, SolveOptions, SolveResult, WorkCheckpoint
from geotarget.service import unexpected_engine_error_result


def test_catalog_and_preview_share_v15_contract(problem: dict) -> None:
    with TestClient(app) as client:
        catalog = client.get("/api/v1/dsl/catalog")
        assert catalog.status_code == 200
        assert any(tool["id"] == "PointOnCircle" for tool in catalog.json()["tools"])
        assert client.post("/api/v1/preview", json=problem).status_code == 403
        assert client.get("/api/v1/session").status_code == 200
        preview = client.post("/api/v1/preview", json=problem)
        assert preview.status_code == 200
        assert preview.json()["validation"]["valid"] is True


def test_http_request_keeps_native_integer_constraint_value(problem: dict, monkeypatch) -> None:
    problem["constraints"].append({"def": "Distance(A, B)", "value": 5})
    captured = {}

    def fake_create(request):
        captured.update(request.problem)
        return type("Job", (), {"id": "job", "state": "queued"})()

    monkeypatch.setattr("geotarget.api.MANAGER.create", fake_create)
    with TestClient(app) as client:
        client.get("/api/v1/session")
        response = client.post(
            "/api/v1/solves",
            json={
                "problem": problem,
                "options": {"time_limit_seconds": 180, "cores": 1, "seed": 0},
            },
        )
    assert response.status_code == 202
    assert type(captured["constraints"][0]["value"]) is int


def test_http_accepts_optimized_public_options(problem: dict, monkeypatch) -> None:
    captured = {}

    def fake_create(request):
        captured.update(request.options.model_dump())
        return type("Job", (), {"id": "job", "state": "queued"})()

    monkeypatch.setattr("geotarget.api.MANAGER.create", fake_create)
    with TestClient(app) as client:
        client.get("/api/v1/session")
        response = client.post(
            "/api/v1/solves",
            json={
                "problem": problem,
                "options": {
                    "engine": "optimized",
                    "run_mode": "adaptive",
                    "max_time_seconds": 600,
                    "cores": "auto",
                },
            },
        )

    assert response.status_code == 202
    assert captured == {
        "engine": "optimized",
        "run_mode": "adaptive",
        "max_time_seconds": 600.0,
        "cores": "auto",
        "seed": 0,
    }


def test_http_omitted_options_follow_qualified_optimized_policy(
    problem: dict, monkeypatch
) -> None:
    captured = {}

    def fake_create(request):
        captured.update(request.options.model_dump())
        return type("Job", (), {"id": "job", "state": "queued"})()

    monkeypatch.setattr("geotarget.api.MANAGER.create", fake_create)
    with TestClient(app) as client:
        client.get("/api/v1/session")
        response = client.post("/api/v1/solves", json={"problem": problem})
        schema = client.get("/openapi.json").json()

    assert response.status_code == 202
    assert captured == SolveOptions().model_dump()
    options_schema = schema["components"]["schemas"]["SolveOptions"]["properties"]
    assert options_schema["engine"]["default"] == "optimized"
    assert options_schema["run_mode"]["default"] == "adaptive"
    assert options_schema["max_time_seconds"]["default"] == 900.0
    assert options_schema["cores"]["default"] == "auto"


def test_http_serializes_result_metadata(monkeypatch) -> None:
    resources = ResourceUsage(
        time_limit_seconds=180,
        max_time_seconds=180,
        cores=2,
        seed=0,
    )
    result = SolveResult(
        status="exact_complete",
        engine_id="champion",
        engine_hash="hash",
        problem_sha256="problem",
        requested_resources=resources,
        used_resources=resources,
        elapsed_seconds=1,
        work_checkpoint=WorkCheckpoint(),
        engine_variant="optimized",
        termination_reason="exact_complete",
    )
    job = type(
        "Job",
        (),
        {
            "id": "job",
            "state": "completed",
            "result": result,
            "progress": {
                "phase": "completed",
                "completed_starts": 256,
                "extension_batches_completed": 2,
                "consecutive_empty_extension_batches": 1,
                "termination_reason": "exact_complete",
                "elapsed_seconds": 1.0,
            },
        },
    )()
    monkeypatch.setattr("geotarget.api.MANAGER.get", lambda job_id: job)

    with TestClient(app) as client:
        client.get("/api/v1/session")
        response = client.get("/api/v1/solves/job")

    assert response.status_code == 200
    payload = response.json()["result"]
    assert payload["engine_variant"] == "optimized"
    assert payload["termination_reason"] == "exact_complete"
    assert payload["phase_metadata"] == {
        "current": None,
        "completed": [],
        "elapsed_seconds": {},
    }
    assert payload["cache_metadata"] == {
        "hits": 0,
        "misses": 0,
        "writes": 0,
        "runtime_generation": 0,
        "runtime_warm": False,
        "hp_preloader_warm": False,
    }
    progress = response.json()["progress"]
    assert {
        key: progress[key]
        for key in (
            "phase",
            "completed_starts",
            "extension_batches_completed",
            "consecutive_empty_extension_batches",
            "termination_reason",
            "elapsed_seconds",
        )
    } == {
        "phase": "completed",
        "completed_starts": 256,
        "extension_batches_completed": 2,
        "consecutive_empty_extension_batches": 1,
        "termination_reason": "exact_complete",
        "elapsed_seconds": 1.0,
    }
    assert progress["engine_elapsed_seconds"] == 1.0
    assert progress["wall_elapsed_seconds"] >= 0.0
    assert response.json()["engine_elapsed_seconds"] == 1.0
    assert response.json()["wall_elapsed_seconds"] >= 0.0


def test_job_manager_propagates_real_engine_progress(problem: dict, monkeypatch) -> None:
    resources = ResourceUsage(
        time_limit_seconds=180,
        max_time_seconds=180,
        cores=1,
        seed=0,
    )

    class FakeEngine:
        def __init__(self, progress):
            self.progress = progress

        def cancel(self):
            return None

    def fake_solve(_problem, _options, *, engine):
        engine.progress(
            {
                "phase": "initial",
                "completed_starts": 128,
                "elapsed_seconds": 0.25,
            }
        )
        return SolveResult(
            status="no_answer_found",
            engine_id="champion",
            engine_hash="hash",
            problem_sha256="problem",
            requested_resources=resources,
            used_resources=resources,
            elapsed_seconds=0.5,
            work_checkpoint=WorkCheckpoint(completed_start_ordinals=[0, 1]),
            engine_variant="reference",
            termination_reason="safety_cap",
        )

    monkeypatch.setattr("geotarget.api.ChampionSubprocessEngine", FakeEngine)
    monkeypatch.setattr("geotarget.api.solve", fake_solve)
    manager = JobManager()
    job = manager.create(SolveRequest(problem=problem))
    deadline = time.monotonic() + 2
    while job.state not in {"completed", "cancelled"} and time.monotonic() < deadline:
        time.sleep(0.01)

    assert job.state == "completed"
    assert any(
        event["event"] == "progress"
        and event.get("phase") == "initial"
        and event.get("completed_starts") == 128
        for event in job.events
    )
    assert job.progress["phase"] == "completed"
    assert job.progress["completed_starts"] == 2
    assert job.progress["termination_reason"] == "safety_cap"


def test_sse_emits_progress_and_terminal_events(problem: dict, monkeypatch) -> None:
    job = Job(id="job", request=SolveRequest(problem=problem), state="completed")
    job.emit("queued")
    job.emit("progress", phase="initial", completed_starts=64)
    job.emit("completed", status="no_answer_found")
    monkeypatch.setattr("geotarget.api.MANAGER.get", lambda _job_id: job)

    with TestClient(app) as client:
        client.get("/api/v1/session")
        response = client.get("/api/v1/solves/job/events")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert "event: progress" in response.text
    assert '"completed_starts": 64' in response.text
    assert "event: completed" in response.text


def test_worker_survives_unexpected_job_exception(problem: dict, monkeypatch) -> None:
    resources = ResourceUsage(
        time_limit_seconds=180,
        max_time_seconds=180,
        cores=1,
        seed=0,
    )
    calls = 0

    class FakeEngine:
        def __init__(self, _progress):
            pass

        def cancel(self):
            return None

    def fake_solve(_problem, _options, *, engine):
        nonlocal calls
        del engine
        calls += 1
        if calls == 1:
            raise OSError("synthetic worker failure")
        return SolveResult(
            status="no_answer_found",
            engine_id="champion",
            engine_hash="hash",
            problem_sha256="problem",
            requested_resources=resources,
            used_resources=resources,
            elapsed_seconds=0.1,
            work_checkpoint=WorkCheckpoint(),
            engine_variant="reference",
            termination_reason="safety_cap",
        )

    monkeypatch.setattr("geotarget.api.ChampionSubprocessEngine", FakeEngine)
    monkeypatch.setattr("geotarget.api.solve", fake_solve)
    manager = JobManager()
    first = manager.create(SolveRequest(problem=problem))
    second = manager.create(SolveRequest(problem=problem))
    deadline = time.monotonic() + 2
    while (
        second.state not in {"completed", "cancelled"}
        and time.monotonic() < deadline
    ):
        time.sleep(0.01)

    assert first.state == "completed"
    assert first.result is not None
    assert first.result.status == "engine_error"
    assert first.result.detail == "内部エラーが発生しました。再実行してください。"
    assert first.engine is None
    assert second.state == "completed"
    assert second.result is not None
    assert second.result.status == "no_answer_found"
    assert second.engine is None


def test_queued_cancellation_becomes_terminal_without_waiting_for_worker(
    problem: dict, monkeypatch
) -> None:
    release = threading.Event()

    class FakeEngine:
        def __init__(self, _progress):
            pass

        def cancel(self):
            return None

    def blocking_solve(_problem, options, *, engine):
        del engine
        release.wait(timeout=2)
        return unexpected_engine_error_result(_problem, options, elapsed_seconds=0.1)

    monkeypatch.setattr("geotarget.api.ChampionSubprocessEngine", FakeEngine)
    monkeypatch.setattr("geotarget.api.solve", blocking_solve)
    manager = JobManager()
    first = manager.create(SolveRequest(problem=problem))
    deadline = time.monotonic() + 2
    while first.state != "running" and time.monotonic() < deadline:
        time.sleep(0.01)
    assert first.state == "running"

    queued = manager.create(SolveRequest(problem=problem))
    manager.cancel(queued.id)
    assert queued.state == "cancelled"
    assert queued.completed_monotonic is not None
    assert [event["event"] for event in queued.events][-2:] == [
        "cancellation_requested",
        "cancelled",
    ]
    release.set()


def test_job_events_use_monotonic_ids_and_bounded_retention(problem: dict) -> None:
    job = Job(id="job", request=SolveRequest(problem=problem))

    for ordinal in range(300):
        job.emit("progress", ordinal=ordinal)

    retained = list(job.events)
    assert len(retained) == 256
    assert retained[0]["id"] == 44
    assert retained[-1]["id"] == 299
    assert [item["id"] for item in retained] == list(range(44, 300))


def test_job_manager_prunes_only_terminal_jobs(problem: dict) -> None:
    manager = JobManager(completed_ttl_seconds=3_600, max_completed_jobs=2)
    now = time.monotonic()
    active = Job(id="active", request=SolveRequest(problem=problem), state="running")
    completed = [
        Job(
            id=f"done-{ordinal}",
            request=SolveRequest(problem=problem),
            state="completed",
            completed_monotonic=now - (3 - ordinal),
        )
        for ordinal in range(3)
    ]
    with manager.lock:
        manager.jobs = {active.id: active, **{job.id: job for job in completed}}
        manager._prune_locked(now)

    assert set(manager.jobs) == {"active", "done-1", "done-2"}


def test_sse_resumes_after_last_event_id(problem: dict, monkeypatch) -> None:
    job = Job(id="job", request=SolveRequest(problem=problem), state="completed")
    job.emit("queued")
    job.emit("progress", phase="initial")
    job.emit("completed", status="no_answer_found")
    monkeypatch.setattr("geotarget.api.MANAGER.get", lambda _job_id: job)

    with TestClient(app) as client:
        client.get("/api/v1/session")
        response = client.get(
            "/api/v1/solves/job/events", headers={"Last-Event-ID": "0"}
        )

    assert response.status_code == 200
    assert "id: 0" not in response.text
    assert "id: 1" in response.text
    assert "id: 2" in response.text
