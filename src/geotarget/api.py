from __future__ import annotations

import json
import queue
import secrets
import threading
import time
import uuid
from dataclasses import dataclass, field
from importlib.resources import files
from pathlib import Path
from typing import Any

from fastapi import Cookie, FastAPI, HTTPException, Request, Response
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from geotarget.doctor import diagnose
from geotarget.engine import ChampionSubprocessEngine
from geotarget.models import SolveOptions, SolveResult
from geotarget.qualification import policy
from geotarget.service import solve
from geotarget.validation import validate


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
    events: list[dict[str, Any]] = field(default_factory=list)
    engine: ChampionSubprocessEngine | None = None
    cancelled: bool = False
    progress: dict[str, Any] = field(default_factory=dict)
    started_monotonic: float | None = None

    def emit(self, event: str, **payload: Any) -> None:
        self.events.append({"id": len(self.events), "event": event, "at": time.time(), **payload})

    def update_progress(self, payload: dict[str, Any]) -> None:
        self.progress = {**self.progress, **payload}
        self.emit("progress", **self.progress)


class JobManager:
    def __init__(self) -> None:
        self.jobs: dict[str, Job] = {}
        self.pending: queue.Queue[str] = queue.Queue()
        self.lock = threading.Lock()
        threading.Thread(target=self._worker, daemon=True, name="geotarget-solve-fifo").start()

    def create(self, request: SolveRequest) -> Job:
        job = Job(id=uuid.uuid4().hex, request=request)
        job.emit("queued")
        with self.lock:
            self.jobs[job.id] = job
        self.pending.put(job.id)
        return job

    def get(self, job_id: str) -> Job:
        with self.lock:
            job = self.jobs.get(job_id)
        if not job:
            raise KeyError(job_id)
        return job

    def cancel(self, job_id: str) -> Job:
        job = self.get(job_id)
        job.cancelled = True
        if job.engine:
            job.engine.cancel()
        job.emit("cancellation_requested")
        return job

    def _worker(self) -> None:
        while True:
            job = self.get(self.pending.get())
            if job.cancelled:
                job.state = "cancelled"
                job.emit("cancelled")
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
            job.engine = None


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
    return {
        "job_id": job.id,
        "state": job.state,
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
        },
        "result": job.result.model_dump(mode="json") if job.result else None,
    }


@app.get("/api/v1/solves/{job_id}/events")
def solve_events(
    job_id: str, geotarget_session: str | None = Cookie(default=None)
) -> StreamingResponse:
    _require_session(geotarget_session)
    try:
        job = MANAGER.get(job_id)
    except KeyError as error:
        raise HTTPException(status_code=404, detail="job not found") from error

    def stream():
        cursor = 0
        while True:
            while cursor < len(job.events):
                item = job.events[cursor]
                cursor += 1
                data = json.dumps(item, ensure_ascii=False)
                yield f"id: {item['id']}\nevent: {item['event']}\ndata: {data}\n\n"
            if job.state in {"completed", "cancelled"}:
                return
            time.sleep(0.2)

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
    return json.loads(files("geotarget").joinpath("dsl_catalog.json").read_text(encoding="utf-8"))


@app.get("/api/v1/doctor")
def doctor() -> dict[str, Any]:
    return diagnose()


@app.get("/api/v1/qualification")
def qualification() -> dict[str, Any]:
    return policy()


_frontend = Path(__file__).resolve().parents[2] / "frontend/dist/client"
if _frontend.is_dir():
    app.mount("/", StaticFiles(directory=_frontend, html=True), name="ui")
