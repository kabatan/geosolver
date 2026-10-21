"""Bounded scalar branch discovery before a local solver can stop at one root."""

import time

import numpy as np

from geosolver.engine.standard.contracts.candidate_record import SearchBatchResult
from geosolver.engine.standard.evaluation.classify_evaluation_failure import EvaluationStatus
from geosolver.engine.standard.search.build_guard_feasible_ledger import build_guard_feasible_ledger
from geosolver.engine.standard.search.scipy_multistart_backend import (
    _ONE_D_FAMILY_CODE,
    _RESIDUAL_ACCEPT_FLOAT,
    _build_candidate,
    _run_one_dimensional_search,
    _SearchTelemetry,
)


def scan_scalar_branches(*, evaluator, bounds, config, prefix_count, constraint_scales=None):
    """Return root candidates only; every candidate still requires final verification."""
    budget = 2.0 if config.max_time_sec is None else min(2.0, config.max_time_sec)
    if budget <= 0:
        return SearchBatchResult(
            candidates=(),
            evaluation_count=0,
            failure_ratio=0,
            evaluation_failure_count=0,
            search_diagnostics={"primary_scalar_branch_scan": {"reason": "no_time_budget"}},
        )
    telemetry = _SearchTelemetry()
    points, diagnostics = _run_one_dimensional_search(
        evaluator=evaluator,
        bounds=bounds,
        config=config,
        deadline_monotonic=time.monotonic() + max(0.0, budget),
        telemetry=telemetry,
    )
    seed = (config.seed_values or (11,))[0]
    records = tuple(
        _build_candidate(
            evaluator=evaluator,
            config=config,
            bounds=bounds,
            values=np.array(point, dtype=float),
            origin_seed=int(seed),
            family_code=_ONE_D_FAMILY_CODE,
            origin_start_point_index=index,
            telemetry=telemetry,
            constraint_scales=constraint_scales,
        )
        for index, point in enumerate(points)
    )
    # A closed mathematical endpoint has zero margin. The original guards and
    # hard-feasibility result decide admission; final verification remains mandatory.
    selected = tuple(
        sorted(
            (
                record
                for record in records
                if record.evaluation_status is EvaluationStatus.OK
                and record.residual_norm_float < _RESIDUAL_ACCEPT_FLOAT
                and record.guard_ok
                and record.hard_feasible
            ),
            key=lambda record: (record.residual_norm_float, record.score, record.candidate_id),
        )[: int(config.keep_after_dedup)]
    )
    _, ledger = build_guard_feasible_ledger(
        all_records=records,
        bounds=bounds,
        compact_keep_count=int(config.keep_after_dedup),
        prefix_count=int(prefix_count),
    )
    return SearchBatchResult(
        candidates=selected,
        evaluation_count=telemetry.evaluation_count,
        failure_ratio=telemetry.failure_count / max(1, telemetry.evaluation_count),
        evaluation_failure_count=telemetry.failure_count,
        all_records=records,
        guard_feasible_ledger=ledger,
        search_diagnostics={"primary_scalar_branch_scan": diagnostics},
    )
