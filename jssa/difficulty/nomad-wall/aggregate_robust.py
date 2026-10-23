"""Read engine_error records with null diagnostics; retain the fixed analysis."""
from __future__ import annotations

import runpy
import statistics
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT))
from benchmarks import research_runner as research

original = research.read_run_outcome
original_median = statistics.median


def read_run_outcome(raw):
    result = raw.get("solver_result")
    if isinstance(result, dict) and result.get("diagnostics") is None:
        raw = {**raw, "solver_result": {**result, "diagnostics": {}}}
    return original(raw)


def available_median(values):
    available = [value for value in values if value is not None]
    return original_median(available) if available else None


if __name__ == "__main__":
    check = {"process": {"returncode": 2, "timed_out": False, "elapsed_seconds": 3.0},
             "solver_result": {"status": "engine_error", "diagnostics": None, "elapsed_seconds": 2.0}}
    result = read_run_outcome(check)
    assert result["status"] == "engine_error" and result["normal_completion"] is False
    assert check["solver_result"]["diagnostics"] is None
    research.read_run_outcome = read_run_outcome
    # A launcher that never started has no measured elapsed time. Do not invent 0.
    statistics.median = available_median
    runpy.run_path(str(HERE / "aggregate.py"), run_name="__main__")
