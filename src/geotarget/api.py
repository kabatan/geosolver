from __future__ import annotations

import json
import logging
import queue
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
from pydantic import BaseModel

from geotarget.doctor import diagnose
from geotarget.dsl_contract import catalog_payload
from geotarget.engine import ChampionSubprocessEngine
from geotarget.models import SolveOptions, SolveResult
from geotarget.qualification import policy
from geotarget.service import solve, unexpected_engine_error_result
from geotarget.validation import validate

LOGGER = logging.getLogger(__name__)
MAX_EVENTS_PER_JOB = 256
COMPLETED_JOB_TTL_SECONDS = 60 * 60
MAX_COMPLETED_JOBS = 100


class SolveRequest(BaseModel):
    # Keep the caller's JSON scalar shapes intact.  Parsing the problem into a
    # Pydantic model here would coerce e.g. constraint value ``0`` to ``0.0``
    # before the source-preserving validator and exact replay authority see it.
    problem: dict[str, Any]
    options: SolveOptions = SolveOptions()


@dataclass
class Job:
    id: str
    request: SolveRequest
    state: str = "queued"
    result: SolveResult | None = None
    events: deque[dict[str, Any]] = field(
        default_factory=lambda: deque(maxlen=MAX_EVENTS_PER_JOB)
    )
    engine: ChampionSubprocessEngine | None = None
    cancelled: bool = False
    progress: dict[str, Any] = field(default_factory=dict)
    started_monotonic: float | None = None
    created_monotonic: float = field(default_factory=time.monotonic)
    completed_monotonic: float | None = None
    next_event_id: int = 0
    condition: threading.Condition = field(
        default_factory=threading.Condition, repr=False, compare=False
    )

    def emit(self, event: str, **payload: Any) -> None:
        with self.condition:
            item = {
                "id": self.next_event_id,
                "event": event,
                "at": time.time(),
                **payload,
            }
            self.next_event_id += 1
            self.events.append(item)
            self.condition.notify_all()

    def update_progress(self, payload: dict[str, Any]) -> None:
        with self.condition:
            self.progress = {**self.progress, **payload}
            self.emit("progress", **self.progress)


class JobManager:
    def __init__(
        self,
        *,
        completed_ttl_seconds: float = COMPLETED_JOB_TTL_SECONDS,
        max_completed_jobs: int = MAX_COMPLETED_JOBS,
        max_events_per_job: int = MAX_EVENTS_PER_JOB,
    ) -> None:
        self.jobs: dict[str, Job] = {}
        self.pending: queue.Queue[str] = queue.Queue()
        self.lock = threading.Lock()
        self.completed_ttl_seconds = float(completed_ttl_seconds)
        self.max_completed_jobs = int(max_completed_jobs)
        self.max_events_per_job = int(max_events_per_job)
        threading.Thread(target=self._worker, daemon=True, name="geotarget-solve-fifo").start()

    def _prune_locked(self, now: float) -> None:
        terminal = [
            job
            for job in self.jobs.values()
            if job.state in {"completed", "cancelled"}
            and job.completed_monotonic is not None
        ]
        expired = {
            job.id
            for job in terminal
            if now - float(job.completed_monotonic) >= self.completed_ttl_seconds
        }
        retained = sorted(
            (job for job in terminal if job.id not in expired),
            key=lambda job: float(job.completed_monotonic or 0.0),
        )
        overflow = max(0, len(retained) - self.max_completed_jobs)
        expired.update(job.id for job in retained[:overflow])
        for job_id in expired:
            self.jobs.pop(job_id, None)

    def _mark_terminal(self, job: Job) -> None:
        with job.condition:
            if job.completed_monotonic is None:
                job.completed_monotonic = time.monotonic()
            job.condition.notify_all()

    def create(self, request: SolveRequest) -> Job:
        job = Job(
            id=uuid.uuid4().hex,
            request=request,
            events=deque(maxlen=self.max_events_per_job),
        )
        job.emit("queued")
        with self.lock:
            self._prune_locked(time.monotonic())
            self.jobs[job.id] = job
        self.pending.put(job.id)
        return job

    def get(self, job_id: str) -> Job:
        with self.lock:
            self._prune_locked(time.monotonic())
            job = self.jobs.get(job_id)
        if not job:
            raise KeyError(job_id)
        return job

    def cancel(self, job_id: str) -> Job:
        job = self.get(job_id)
        with job.condition:
            job.cancelled = True
            engine = job.engine
            queued = job.state == "queued"
            if queued:
                job.state = "cancelled"
        if engine:
            try:
                engine.cancel()
            except Exception:
                LOGGER.exception("job %s engine cancellation failed", job.id)
        job.emit("cancellation_requested")
        if queued:
            job.emit("cancelled")
            self._mark_terminal(job)
        return job

    def _worker(self) -> None:
        while True:
            job_id = self.pending.get()
            job: Job | None = None
            try:
                job = self.get(job_id)
                if job.cancelled:
                    job.state = "cancelled"
                    job.emit("cancelled")
                    self._mark_terminal(job)
                    continue
                job.state = "running"
                job.started_monotonic = time.monotonic()
                job.engine = ChampionSubprocessEngine(job.update_progress)
                job.emit("phase", phase="initialization")
                result = solve(job.request.problem, job.request.options, engine=job.engine)
                job.result = result
                job.state = "cancelled" if result.status == "cancelled" else "completed"
                job.update_progress(
                    {
                        "phase": "cancelled" if result.status == "cancelled" else "completed",
                        "elapsed_seconds": result.elapsed_seconds,
                        "termination_reason": result.termination_reason,
                        "completed_starts": len(
                            result.work_checkpoint.completed_start_ordinals
                        ),
                        "extension_batches_completed": (
                            result.work_checkpoint.extension_batches_completed
                        ),
                        "consecutive_empty_extension_batches": (
                            result.work_checkpoint.consecutive_empty_extension_batches
                        ),
                        "used_cores": result.used_resources.cores,
                        "max_time_seconds": result.requested_resources.max_time_seconds,
                    }
                )
                job.emit("completed", status=result.status)
                self._mark_terminal(job)
            except Exception:
                LOGGER.exception("unexpected failure while executing job %s", job_id)
                if job is not None:
                    started = job.started_monotonic or time.monotonic()
                    result = unexpected_engine_error_result(
                        job.request.problem,
                        job.request.options,
                        elapsed_seconds=time.monotonic() - started,
                    )
                    job.result = result
                    job.state = "completed"
                    job.update_progress(
                        {
                            "phase": "error",
                            "elapsed_seconds": result.elapsed_seconds,
                            "termination_reason": "engine_error",
                            "max_time_seconds": result.requested_resources.max_time_seconds,
                        }
                    )
                    job.emit("completed", status=result.status)
                    self._mark_terminal(job)
            finally:
                if job is not None:
                    job.engine = None
                self.pending.task_done()


SESSION_TOKEN = secrets.token_urlsafe(32)
MANAGER = JobManager()
app = FastAPI(title="GeoTarget Local API", version="1.0.0", openapi_version="3.1.0")


@app.middleware("http")
async def local_only(request: Request, call_next):
    host = request.client.host if request.client else ""
    if host not in {"127.0.0.1", "::1", "localhost", "testclient"}:
        return Response(status_code=403, content="loopback only")
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    return response


def _require_session(token: str | None) -> None:
    if not token or not secrets.compare_digest(token, SESSION_TOKEN):
        raise HTTPException(status_code=403, detail="invalid local session")


@app.get("/api/v1/session")
def session(response: Response) -> dict[str, str]:
    response.set_cookie("geotarget_session", SESSION_TOKEN, httponly=True, samesite="strict")
    return {"status": "ready"}


@app.post("/api/v1/solves", status_code=202)
def create_solve(
    request: SolveRequest, geotarget_session: str | None = Cookie(default=None)
) -> dict[str, Any]:
    _require_session(geotarget_session)
    report = validate(request.problem)
    if not report.valid:
        raise HTTPException(status_code=422, detail=report.model_dump(mode="json"))
    job = MANAGER.create(request)
    return {"job_id": job.id, "state": job.state}


@app.get("/api/v1/solves/{job_id}")
def get_solve(job_id: str, geotarget_session: str | None = Cookie(default=None)) -> dict[str, Any]:
    _require_session(geotarget_session)
    try:
        job = MANAGER.get(job_id)
    except KeyError as error:
        raise HTTPException(status_code=404, detail="job not found") from error
    progress = getattr(job, "progress", {})
    started_monotonic = getattr(job, "started_monotonic", None)
    completed_monotonic = getattr(job, "completed_monotonic", None)
    wall_finished = completed_monotonic or time.monotonic()
    created_monotonic = getattr(job, "created_monotonic", wall_finished)
    wall_elapsed_seconds = max(0.0, wall_finished - created_monotonic)
    engine_elapsed_seconds = (
        job.result.elapsed_seconds
        if job.result is not None
        else float(progress.get("elapsed_seconds", 0.0))
    )
    return {
        "job_id": job.id,
        "state": job.state,
        "wall_elapsed_seconds": wall_elapsed_seconds,
        "engine_elapsed_seconds": engine_elapsed_seconds,
        "progress": {
            **progress,
            "elapsed_seconds": (
                progress.get("elapsed_seconds", 0.0)
                if job.state != "running"
                else max(
                    float(progress.get("elapsed_seconds", 0.0)),
                    time.monotonic() - (started_monotonic or time.monotonic()),
                )
            ),
            "wall_elapsed_seconds": wall_elapsed_seconds,
            "engine_elapsed_seconds": engine_elapsed_seconds,
        },
        "result": job.result.model_dump(mode="json") if job.result else None,
    }


@app.get("/api/v1/solves/{job_id}/events")
def solve_events(
    job_id: str,
    geotarget_session: str | None = Cookie(default=None),
    last_event_id: str | None = Header(default=None, alias="Last-Event-ID"),
) -> StreamingResponse:
    _require_session(geotarget_session)
    try:
        job = MANAGER.get(job_id)
    except KeyError as error:
        raise HTTPException(status_code=404, detail="job not found") from error

    def stream():
        try:
            cursor = int(last_event_id) + 1 if last_event_id is not None else None
        except ValueError:
            cursor = None
        while True:
            with job.condition:
                retained = list(job.events)
                if cursor is None:
                    cursor = retained[0]["id"] if retained else job.next_event_id
                available = [item for item in retained if int(item["id"]) >= cursor]
                terminal = job.state in {"completed", "cancelled"}
                if not available and not terminal:
                    job.condition.wait(timeout=0.5)
                    continue
            for item in available:
                cursor = int(item["id"]) + 1
                data = json.dumps(item, ensure_ascii=False)
                yield f"id: {item['id']}\nevent: {item['event']}\ndata: {data}\n\n"
            if terminal:
                return

    return StreamingResponse(stream(), media_type="text/event-stream")


@app.delete("/api/v1/solves/{job_id}")
def cancel_solve(
    job_id: str, geotarget_session: str | None = Cookie(default=None)
) -> dict[str, str]:
    _require_session(geotarget_session)
    try:
        job = MANAGER.cancel(job_id)
    except KeyError as error:
        raise HTTPException(status_code=404, detail="job not found") from error
    return {"job_id": job.id, "state": job.state}


@app.post("/api/v1/preview")
def preview(
    problem: dict[str, Any], geotarget_session: str | None = Cookie(default=None)
) -> dict[str, Any]:
    _require_session(geotarget_session)
    report = validate(problem)
    return {
        "validation": report.model_dump(mode="json"),
        "objects": problem.get("construction", []),
        "target": problem.get("answer", ""),
    }


@app.get("/api/v1/dsl/catalog")
def dsl_catalog() -> dict[str, Any]:
    return catalog_payload()


@app.get("/api/v1/doctor")
def doctor() -> dict[str, Any]:
    return diagnose()


@app.get("/api/v1/qualification")
def qualification() -> dict[str, Any]:
    return policy()


_frontend = Path(__file__).resolve().parents[2] / "frontend/dist/client"
if _frontend.is_dir():
    app.mount("/", StaticFiles(directory=_frontend, html=True), name="ui")
