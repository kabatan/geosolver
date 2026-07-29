import time

from fastapi.testclient import TestClient

from geotarget.api import Job, JobManager, SolveRequest, app
from geotarget.models import ResourceUsage, SolveOptions, SolveResult, WorkCheckpoint


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
    assert response.json()["progress"] == {
        "phase": "completed",
        "completed_starts": 256,
        "extension_batches_completed": 2,
        "consecutive_empty_extension_batches": 1,
        "termination_reason": "exact_complete",
        "elapsed_seconds": 1.0,
    }


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
