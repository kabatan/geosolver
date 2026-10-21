"""Phase rescue: box-constrained PyNomad search pass."""

from __future__ import annotations

import time
from dataclasses import dataclass, replace

from geosolver.engine.standard.contracts.branch_box import BranchBox
from geosolver.engine.standard.contracts.candidate_record import FloatCandidate, SearchBatchResult
from geosolver.engine.standard.contracts.evaluator_port import EvaluatorPort
from geosolver.engine.standard.contracts.external_pipeline_config import ExternalPipelineConfig
from geosolver.engine.standard.contracts.problem_bundle import ProblemBundle
from geosolver.engine.standard.contracts.runtime_budget import RuntimeBudget
from geosolver.engine.standard.search.deduplicate_search_candidates import (
    deduplicate_search_candidates,
)
from geosolver.engine.standard.search.nomad_blackbox_adapter import NomadBlackboxAdapter
from geosolver.engine.standard.search.select_rescue_boxes import select_rescue_boxes
from geosolver.runtime.deadline import timed_phase, uses_deadline

_RESCUE_CANDIDATE_NAMESPACE = 10_000_000_000_000
_RESCUE_BOX_NAMESPACE_STRIDE = 1_000_000_000


def _import_pynomad() -> object:
    try:
        import PyNomad  # type: ignore[import-not-found]
    except Exception as exc:
        raise ImportError(
            "PyNomad (provided by PyNomadBBO) is required for rescue search (no silent fallback)."
        ) from exc
    return PyNomad


@dataclass(frozen=True)
class RescueSearchResult:
    """Output of rescue search stage."""

    boxes: tuple[BranchBox, ...]
    candidates: tuple[FloatCandidate, ...]
    elapsed_sec: float
    box_runs: tuple[dict[str, object], ...] = ()


@timed_phase("rescue")
@uses_deadline
def run_rescue_search(
    *,
    bundle: ProblemBundle,
    evaluator: EvaluatorPort,
    bounds: list[tuple[float, float]],
    search_result: SearchBatchResult,
    pipeline_config: ExternalPipelineConfig,
    runtime_budget: RuntimeBudget,
    constraint_scales: tuple[float, ...] | None = None,
) -> RescueSearchResult:
    """Run conditional rescue search over selected rescue boxes."""
    started_at = time.monotonic()
    boxes = select_rescue_boxes(
        search_result.guard_feasible_ledger,
        bounds,
        pipeline_config,
    )
    if not boxes:
        return RescueSearchResult(boxes=(), candidates=(), elapsed_sec=0.0)
    py_nomad = _import_pynomad()
    rescue_config = replace(
        pipeline_config.search,
        max_bb_eval=int(pipeline_config.rescue_max_bb_eval),
        keep_per_run=int(pipeline_config.keep_per_rescue_box),
        keep_after_dedup=int(pipeline_config.keep_per_rescue_box),
        min_per_seed_after_dedup=0,
        max_time_sec=min(runtime_budget.remaining_sec(), pipeline_config.rescue_time_budget_sec),
    )
    rescued_candidates: list[FloatCandidate] = []
    box_runs = []
    seed = int(rescue_config.seed_values[0]) if rescue_config.seed_values else 0
    for box_index, box in enumerate(boxes):
        remaining = min(
            runtime_budget.remaining_sec(),
            started_at + pipeline_config.rescue_time_budget_sec - time.monotonic(),
        )
        if remaining <= 0.0:
            break
        quota = remaining / (len(boxes) - box_index)
        box_started = time.monotonic()
        box_deadline = min(float(runtime_budget.deadline_monotonic), box_started + quota)
        rescue_config = replace(rescue_config, max_time_sec=quota)
        adapter = NomadBlackboxAdapter(
            evaluator=evaluator,
            config=rescue_config,
            origin_seed=seed,
            origin_start_point_index=0,
            constraint_scales=constraint_scales,
            candidate_namespace=(
                _RESCUE_CANDIDATE_NAMESPACE + int(box_index) * _RESCUE_BOX_NAMESPACE_STRIDE
            ),
            origin_phase="rescue",
            origin_backend="nomad",
            origin_box_index=int(box_index),
            deadline_monotonic=box_deadline,
        )
        py_nomad.setSeed(seed)
        params = rescue_config.build_params(
            dimension=len(bounds),
            seed=seed,
            search_mode=pipeline_config.rescue_search_mode,
        )
        py_nomad.optimize(
            adapter,
            list(box.center),
            list(box.lower_bounds),
            list(box.upper_bounds),
            params,
        )
        box_finished = time.monotonic()
        box_runs.append(
            {
                "box_index": box_index,
                "quota_seconds": quota,
                "elapsed_seconds": box_finished - box_started,
                "evaluation_count": adapter.evaluation_count,
                "stop_reason": "time_limit"
                if box_finished >= box_deadline
                else "backend_completed",
            }
        )
        run_top = sorted(adapter.records, key=lambda item: item.score)[
            : int(pipeline_config.keep_per_rescue_box)
        ]
        rescued_candidates.extend(run_top)
    deduped = deduplicate_search_candidates(
        candidates=tuple(rescued_candidates),
        bounds=bounds,
        keep_count=max(1, len(rescued_candidates)),
        dedup_distance_threshold=rescue_config.dedup_distance,
        min_per_seed=0,
    )
    elapsed_sec = time.monotonic() - started_at
    _ = bundle
    return RescueSearchResult(
        boxes=tuple(boxes),
        candidates=tuple(deduped),
        elapsed_sec=float(elapsed_sec),
        box_runs=tuple(box_runs),
    )
