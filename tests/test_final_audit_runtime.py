import contextlib
import sys
import time

import psutil
import pytest

from geosolver.engine.standard.search.nomad_config import NomadConfig
from geosolver.engine.standard.search.scipy_multistart_backend import _family_budget
from geosolver.platform.processes import spawn_process, terminate_process_tree
from geosolver.runtime.deadline import check_deadline, runtime_session, uses_deadline


def test_zero_budget_never_becomes_default_budget():
    budget = _family_budget(
        config=NomadConfig(max_bb_eval=10, max_time_sec=0), has_parametric_variables=False
    )
    assert budget.lm_budget_sec == budget.trf_budget_sec == 0


def test_subsecond_nomad_budget_still_has_a_time_cap():
    params = NomadConfig(max_bb_eval=10, max_time_sec=0.2).build_params(
        dimension=1, seed=0, search_mode="mads"
    )
    assert "MAX_TIME 1" in params


def test_nested_deadline_cannot_extend_outer_budget():
    @uses_deadline
    def inner(*, deadline_monotonic):
        check_deadline()

    with runtime_session(time.monotonic() - 1), pytest.raises(TimeoutError):
        inner(deadline_monotonic=time.monotonic() + 100)


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX signal-specific descendant test")
def test_ignoring_descendant_is_killed_even_if_parent_exits(tmp_path):
    import os

    code = (
        "import subprocess,sys,time; "
        "p=subprocess.Popen([sys.executable,'-c',"
        "'import signal,time;signal.signal(signal.SIGTERM,signal.SIG_IGN);time.sleep(30)']); "
        "print(p.pid,flush=True);time.sleep(30)"
    )
    parent = spawn_process([sys.executable, "-c", code], cwd=tmp_path, env=os.environ.copy())
    child = None
    try:
        child = psutil.Process(int(parent.stdout.readline()))
        terminate_process_tree(parent, grace_seconds=0.2)
        _, alive = psutil.wait_procs([child], timeout=2)
        assert not [p for p in alive if p.status() != psutil.STATUS_ZOMBIE]
    finally:
        terminate_process_tree(parent, grace_seconds=0.1)
        if child is not None and child.is_running():
            with contextlib.suppress(psutil.Error):
                child.kill()


def test_public_result_keeps_phase_and_candidate_artifacts():
    from geosolver import GeometryProblem, solve

    result = solve(
        GeometryProblem(
            id="artifact", variables=[], constructions=[], conditions=[], target="sqrt(2)"
        )
    )
    assert result.answers
    assert result.completeness == "unknown"
    assert "descriptors" in result.diagnostics["phase_timings"]
    assert result.diagnostics["candidate_records"][0]["x_hp"] == []
    assert result.diagnostics["candidate_records"][0]["accepted"]
    assert result.diagnostics["pipeline_backend"] == "direct_evaluation"
    assert result.diagnostics["counters"]["evaluate_answer_hp"] > 0
