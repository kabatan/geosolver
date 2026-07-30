from __future__ import annotations

import os
from pathlib import Path
import sys
import time

from deadline_policy import (
    HARD_FINISH_MARGIN_SECONDS,
    internal_budget,
    run_bounded_process,
)


def test_30_20_budget_reserves_three_seconds_before_initial_phase() -> None:
    budget = internal_budget(30.0, 20.0)
    assert budget.total_seconds == 27.0
    assert budget.search_seconds == 18.0
    assert HARD_FINISH_MARGIN_SECONDS >= 1.0


def test_simulated_slow_replay_is_killed_before_outer_margin(tmp_path: Path) -> None:
    outer_started = time.monotonic()
    outer_total = 2.0
    latest_finish = outer_started + outer_total - HARD_FINISH_MARGIN_SECONDS
    outcome = run_bounded_process(
        [sys.executable, "-c", "import time; time.sleep(5)"],
        latest_finish=latest_finish,
        environment=os.environ,
        cwd=tmp_path,
    )
    outer_elapsed = time.monotonic() - outer_started

    assert outcome.classification == "NOT_STARTED_NO_MARGIN"
    assert outer_total - outer_elapsed > 1.0


def test_started_slow_replay_process_group_is_terminated(tmp_path: Path) -> None:
    started = time.monotonic()
    outcome = run_bounded_process(
        [sys.executable, "-c", "import time; time.sleep(5)"],
        latest_finish=started + 0.9,
        environment=os.environ,
        cwd=tmp_path,
    )

    assert outcome.classification == "HARD_DEADLINE_TERMINATED"
    assert time.monotonic() - started < 1.2
