"""GeoSolver measurement worker with separate synthetic and sealed-campaign gates.

This module does not assess configurations and never imports the common checker.
It stores each observed coordinate revision with its own materialization time.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
import time
import traceback
from pathlib import Path


def write_json(path, value):
    path = Path(path)
    pending = path.with_suffix(path.suffix + ".tmp")
    pending.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8"
    )
    pending.replace(path)


def main(request_path):
    request = json.loads(Path(request_path).read_text(encoding="utf-8"))
    directory = Path(request["output_directory"])
    origin = request["monotonic_origin"]
    model_paths = []
    failures = []
    authorized = False

    def event(name, **values):
        record = {"event": name, "elapsed_seconds": time.monotonic() - origin, **values}
        with (directory / "events.jsonl").open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, allow_nan=False, sort_keys=True) + "\n")

    try:
        if sorted(os.sched_getaffinity(0)) != [request["cpu"]]:
            raise RuntimeError("Worker must be CPU-pinned before Python starts")
        if Path(sys.prefix).resolve() != Path(request["venv"]).resolve():
            raise RuntimeError("Unexpected interpreter prefix")
        problem_path = Path(request["input"])
        if hashlib.sha256(problem_path.read_bytes()).hexdigest() != request["input_sha256"]:
            raise RuntimeError("Problem hash mismatch")
        problem = json.loads(problem_path.read_text(encoding="utf-8"))
        if problem["target"] != "0":
            raise RuntimeError("This worker measures feasibility, not an unknown exact target")
        from benchmarks.gmb_comparison.authorization import authorize_request

        authorize_request(request, problem)
        authorized = True
        event("worker_start", pid=os.getpid())

        event("imports_start")
        from benchmarks.gmb_comparison.observation import observe_candidates
        from benchmarks.gmb_comparison.witness import WitnessExporter
        from geosolver.errors import GeometryError
        from geosolver.problem.models import GeometryProblem
        from geosolver.runtime.integrity import engine_identity_hashes, verify_engine_lock
        from geosolver.runtime.protocol import WorkerRequest
        from geosolver.runtime.worker import _json_value, execute

        ok, reason = verify_engine_lock()
        if not ok or engine_identity_hashes() != request["engine_identity"]:
            raise RuntimeError(f"Solver identity mismatch: {reason}")
        event("imports_end")
        exporter = WitnessExporter(problem, request["declarations"], request.get("bindings", {}))

        def materialize(candidate, stage):
            # Observation errors are evidence failures, not optimizer feedback.
            # Preserve ordinary solver control flow and fail the observation gate.
            observed = time.monotonic() - origin
            try:
                precision = max(
                    80, candidate.coordinate_precision_dps, candidate.answer_precision_dps
                )
                witness = exporter.export(candidate.x_hp, precision_dps=precision)
                materialized = time.monotonic() - origin
                index = len(model_paths)
                path = directory / "models" / f"{index:04d}.json"
                path.parent.mkdir(exist_ok=True)
                candidate_record = _json_value(candidate)
                coordinate_hash = hashlib.sha256(
                    json.dumps(candidate_record["x_hp"], separators=(",", ":")).encode()
                ).hexdigest()
                payload = {
                    "witness": witness,
                    "candidate": candidate_record,
                    "candidate_uid": candidate.candidate_uid,
                    "candidate_id": candidate.candidate_id,
                    "coordinate_sha256": coordinate_hash,
                    "revision": candidate.revision,
                    "coordinate_names": list(exporter.coordinate_names),
                    "materialization_dps": precision,
                    "coordinate_observed_seconds": observed,
                    "materialized_seconds": materialized,
                    "stage": stage,
                }
                write_json(path, payload)
                emitted = time.monotonic() - origin
                model_paths.append(str(path.relative_to(directory)))
                event(
                    "model_materialized",
                    model=model_paths[-1],
                    candidate_uid=candidate.candidate_uid,
                    candidate_id=candidate.candidate_id,
                    coordinate_sha256=coordinate_hash,
                    stage=stage,
                    revision=candidate.revision,
                    materialized_seconds=materialized,
                    emitted_seconds=emitted,
                )
            except Exception as error:
                failure = {
                    "candidate_uid": candidate.candidate_uid,
                    "revision": candidate.revision,
                    "stage": stage,
                    "kind": "candidate_domain_rejection"
                    if isinstance(error, GeometryError)
                    and stage in {"refinement_return", "verified_candidate_revision"}
                    else "observation_error",
                    "candidate": _json_value(candidate),
                    "error": f"{type(error).__name__}: {error}",
                }
                failures.append(failure)
                event("materialization_error", **failure)

        worker_request = WorkerRequest(
            engine_document=GeometryProblem.model_validate(problem).engine_document(),
            seed=request["seed"],
            effective_cores=1,
            deadline_monotonic=origin + request["timeout_seconds"],
            config_snapshot={
                "measurement": "one_configuration",
                "synthetic_canary": request.get("synthetic_canary") is True,
                "campaign_manifest_sha256": request.get("campaign_manifest_sha256"),
            },
        )
        event("solver_start")
        if request.get("instrument", True):
            with observe_candidates(materialize):
                artifact = execute(worker_request)
        else:
            artifact = execute(worker_request)
        event("solver_end", solver_status=artifact.solver_status)
        write_json(directory / "worker-artifact.json", artifact.model_dump(mode="json"))
        write_json(
            directory / "child-result.json",
            {
                "schema_version": 1,
                "outcome": "completed" if artifact.status == "completed" else "error",
                "model_files": model_paths,
                "materialization_failures": failures,
                "solver_status": artifact.solver_status,
                "termination_reason": artifact.termination_reason,
                "common_geometry_validation": "not_performed_in_worker",
                "engine_identity": engine_identity_hashes(),
                "cpu_affinity": sorted(os.sched_getaffinity(0)),
            },
        )
        event("worker_end")
        return 0
    except Exception as error:
        traceback.print_exc()
        # A rejected request has not established ownership of its output path.
        # Never modify that path, even to report an authorization error.
        if authorized:
            write_json(
                directory / "child-result.json",
                {
                    "schema_version": 1,
                    "outcome": "error",
                    "exception": type(error).__name__,
                    "message": str(error),
                    "model_files": model_paths,
                },
            )
        return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1]))
