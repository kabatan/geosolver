from __future__ import annotations

import json
import logging
import secrets
import threading
import time
import uuid
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from fastapi import Cookie, FastAPI, Header, HTTPException, Request, Response
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field

from geosolver.application.service import solve
from geosolver.doctor import diagnose
from geosolver.engine import EngineRunner
from geosolver.problem.catalog import catalog_payload
from geosolver.problem.models import SolveOptions, SolveResult
from geosolver.problem.validation import validate

LOGGER = logging.getLogger(__name__)
SESSION_TOKEN = secrets.token_urlsafe(32)


class SolveRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    problem: dict[str, Any]
    options: SolveOptions = Field(default_factory=SolveOptions)


@dataclass
class Job:
    id: str
    request: SolveRequest
    state: str = "queued"
    result: SolveResult | None = None
    runner: EngineRunner = field(default_factory=EngineRunner)
    events: deque[dict[str, Any]] = field(default_factory=lambda: deque(maxlen=256))
    condition: threading.Condition = field(default_factory=threading.Condition)
    created: float = field(default_factory=time.monotonic)
    started: float | None = None
    next_event_id: int = 0

    def emit(self, event: str, **payload: Any) -> None:
        with self.condition:
            self.events.append(
                {"id": self.next_event_id, "event": event, "at": time.time(), **payload}
            )
            self.next_event_id += 1
            self.condition.notify_all()


class JobManager:
    def __init__(self) -> None:
        self._jobs: dict[str, Job] = {}
        self._lock = threading.Lock()

    def create(self, request: SolveRequest) -> Job:
        job = Job(id=uuid.uuid4().hex, request=request)
        job.emit("queued")
        with self._lock:
            self._jobs[job.id] = job
        threading.Thread(
            target=self._execute,
            args=(job,),
            daemon=True,
            name=f"geosolver-job-{job.id[:8]}",
        ).start()
        return job

    def get(self, job_id: str) -> Job:
        with self._lock:
            job = self._jobs.get(job_id)
        if job is None:
            raise KeyError(job_id)
        return job

    def cancel(self, job_id: str) -> Job:
        job = self.get(job_id)
        job.runner.cancel()
        job.emit("cancellation_requested")
        return job

    def _execute(self, job: Job) -> None:
        job.state = "running"
        job.started = time.monotonic()
        job.emit("phase", phase="search")
        try:
            job.result = solve(job.request.problem, job.request.options, runner=job.runner)
            job.state = "cancelled" if job.result.status == "cancelled" else "completed"
            job.emit("completed", status=job.result.status)
        except Exception:
            LOGGER.exception("unexpected job failure")
            job.state = "completed"
            job.emit("completed", status="engine_error")
        finally:
            with job.condition:
                job.condition.notify_all()


MANAGER = JobManager()
app = FastAPI(title="GeoSolver Local API", version="1.0.0", openapi_version="3.1.0")


@app.middleware("http")
async def local_only(request: Request, call_next: Any) -> Response:
    host = request.client.host if request.client else ""
    if host not in {"127.0.0.1", "::1", "localhost", "testclient"}:
        return Response(status_code=403, content="loopback only")
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    return response


def _require_session(token: str | None) -> None:
    if token is None or not secrets.compare_digest(token, SESSION_TOKEN):
        raise HTTPException(status_code=403, detail="invalid local session")


@app.get("/api/v1/session")
def session(response: Response) -> dict[str, str]:
    response.set_cookie("geosolver_session", SESSION_TOKEN, httponly=True, samesite="strict")
    return {"status": "ready"}


@app.post("/api/v1/solves", status_code=202)
def create_solve(
    request: SolveRequest,
    geosolver_session: str | None = Cookie(default=None),
) -> dict[str, str]:
    _require_session(geosolver_session)
    report = validate(request.problem)
    if not report.valid:
        raise HTTPException(status_code=422, detail=report.model_dump(mode="json"))
    job = MANAGER.create(request)
    return {"job_id": job.id, "state": job.state}


@app.get("/api/v1/solves/{job_id}")
def get_solve(
    job_id: str,
    geosolver_session: str | None = Cookie(default=None),
) -> dict[str, Any]:
    _require_session(geosolver_session)
    try:
        job = MANAGER.get(job_id)
    except KeyError as error:
        raise HTTPException(status_code=404, detail="job not found") from error
    elapsed = time.monotonic() - (job.started or job.created)
    return {
        "job_id": job.id,
        "state": job.state,
        "progress": {"phase": job.state, "elapsed_seconds": elapsed},
        "result": job.result.model_dump(mode="json") if job.result else None,
    }


@app.delete("/api/v1/solves/{job_id}")
def cancel_solve(
    job_id: str,
    geosolver_session: str | None = Cookie(default=None),
) -> dict[str, str]:
    _require_session(geosolver_session)
    try:
        job = MANAGER.cancel(job_id)
    except KeyError as error:
        raise HTTPException(status_code=404, detail="job not found") from error
    return {"job_id": job.id, "state": job.state}


@app.get("/api/v1/solves/{job_id}/events")
def solve_events(
    job_id: str,
    geosolver_session: str | None = Cookie(default=None),
    last_event_id: str | None = Header(default=None, alias="Last-Event-ID"),
) -> StreamingResponse:
    _require_session(geosolver_session)
    try:
        job = MANAGER.get(job_id)
    except KeyError as error:
        raise HTTPException(status_code=404, detail="job not found") from error

    def stream():
        try:
            cursor = int(last_event_id) + 1 if last_event_id is not None else 0
        except ValueError:
            cursor = 0
        while True:
            with job.condition:
                available = [item for item in job.events if int(item["id"]) >= cursor]
                terminal = job.state in {"completed", "cancelled"}
                if not available and not terminal:
                    job.condition.wait(timeout=0.5)
                    continue
            for item in available:
                cursor = int(item["id"]) + 1
                yield (
                    f"id: {item['id']}\nevent: {item['event']}\n"
                    f"data: {json.dumps(item, ensure_ascii=False)}\n\n"
                )
            if terminal:
                return

    return StreamingResponse(stream(), media_type="text/event-stream")


@app.post("/api/v1/preview")
def preview(
    problem: dict[str, Any],
    geosolver_session: str | None = Cookie(default=None),
) -> dict[str, Any]:
    _require_session(geosolver_session)
    report = validate(problem)
    return {
        "validation": report.model_dump(mode="json"),
        "objects": problem.get("constructions", []),
        "target": problem.get("target", ""),
    }


@app.get("/api/v1/dsl/catalog")
def dsl_catalog() -> dict[str, Any]:
    return catalog_payload()


@app.get("/api/v1/doctor")
def doctor() -> dict[str, Any]:
    return diagnose(smoke=False)


@app.get("/api/v1/capabilities")
def capabilities() -> dict[str, Any]:
    return {
        "default_engine": "standard",
        "engines": {
            "standard": {"supported": True},
            "reference": {"supported": __import__("platform").system() == "Linux"},
        },
    }


_frontend_candidates = (
    Path(__file__).resolve().parents[3] / "frontend" / "dist" / "client",
    Path(__file__).resolve().parents[1] / "frontend",
)
for _frontend in _frontend_candidates:
    if _frontend.is_dir():
        app.mount("/", StaticFiles(directory=_frontend, html=True), name="ui")
        break
