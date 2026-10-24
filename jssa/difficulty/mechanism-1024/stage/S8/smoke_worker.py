"""One full EngineRunner execution, with answers/grades deliberately omitted."""
import json
import sys
import time
from pathlib import Path

from geosolver.engine.runner import EngineRunner, EngineFailure
from geosolver.problem.models import GeometryProblem
from geosolver.runtime.integrity import source_tree_hash, verify_engine_lock

EXPECTED = 'sha256:03a44bfbb743b972d95306c63a14c04b78c7d12b96a1ba83d147c56eea7f86a3'
assert source_tree_hash() == EXPECTED
assert verify_engine_lock() == (True, EXPECTED)
problem = GeometryProblem.model_validate_json(Path(sys.argv[1]).read_text())
started = time.monotonic()
receipt = dict(source_hash=EXPECTED, full_process=True, seed=601, time_limit_seconds=20,
               correctness_recorded=False, grading_performed=False)
try:
    execution = EngineRunner().run(problem.engine_document(), seed=601, cores=1,
        time_limit_seconds=20, deadline_monotonic=started + 20)
    a = execution.artifact
    # No answers, result status, public_solved, candidate values or reference keys.
    summary = a.diagnostics.get('pipeline_summary', {})
    search = summary.get('search', {})
    receipt.update(worker_artifact_received=True, worker_process_info=a.process_info,
        config_snapshot=a.config_snapshot,
        backend_diagnostics={k: v for k, v in search.items()
            if k in ('search_mode', 'backend', 'fallback_reason', 'search_diagnostics')},
        mechanism_counters={k: v for k, v in a.counters.items()
            if k.startswith(('analytic_jacobian_', 'positive_scale_chart_', 'algebraic_'))},
        worker_stdout_bytes=len(execution.stdout.encode()), worker_stderr_bytes=len(execution.stderr.encode()))
except EngineFailure as exc:
    receipt.update(worker_artifact_received=False, infrastructure_error=exc.code)
receipt['elapsed_seconds'] = time.monotonic() - started
Path(sys.argv[2]).write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + '\n')
