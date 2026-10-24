"""Unmodified EngineRunner, 180 s; no references enter the worker."""
import json
import sys
import time
from pathlib import Path

from geosolver.engine.runner import EngineFailure, EngineRunner
from geosolver.problem.models import GeometryProblem

problem = GeometryProblem.model_validate_json(Path(sys.argv[1]).read_text())
started = time.monotonic()
try:
    execution = EngineRunner().run(
        problem.engine_document(), seed=int(sys.argv[3]), cores=1,
        time_limit_seconds=180, deadline_monotonic=started + 180,
    )
    artifact = execution.artifact
    payload = artifact.model_dump(mode="json")
    result = {
        "status": "solved" if artifact.answers else "no_answer_found",
        "answers": payload["answers"], "elapsed_seconds": artifact.elapsed_seconds,
        "termination_reason": artifact.termination_reason,
        "diagnostics": {**artifact.diagnostics, "config_snapshot": artifact.config_snapshot,
                        "phase_timings": artifact.phase_timings, "counters": artifact.counters,
                        "process_info": artifact.process_info,
                        "rejection_tags": artifact.rejection_tags},
        "worker_artifact": payload,
    }
except EngineFailure as error:
    result = {"status": error.code, "error": str(error), "answers": [],
              "elapsed_seconds": time.monotonic() - started,
              "termination_reason": error.code}
Path(sys.argv[2]).write_text(json.dumps(result, ensure_ascii=False) + "\n")
