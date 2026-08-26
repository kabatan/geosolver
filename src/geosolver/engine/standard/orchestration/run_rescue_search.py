"""Phase rescue: box-constrained PyNomad search pass."""

from __future__ import annotations

from dataclasses import dataclass, replace
import time

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
    runtime_budget.reserve_or_fail(pipeline_config.rescue_time_budget_sec)
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
    )
    rescued_candidates: list[FloatCandidate] = []
    seed = int(rescue_config.seed_values[0]) if rescue_config.seed_values else 0
    for box in boxes:
        if runtime_budget.remaining_sec() <= 0.0:
            break
        adapter = NomadBlackboxAdapter(
            evaluator=evaluator,
            config=rescue_config,
            origin_seed=seed,
            origin_start_point_index=0,
            constraint_scales=constraint_scales,
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
    )
