"""Phase A orchestration for NOMAD global search."""

from __future__ import annotations

from dataclasses import replace
import time

from geosolver._internal.pipeline.contracts.candidate_record import (
    FloatCandidate,
    SearchBatchResult,
)
from geosolver._internal.pipeline.contracts.evaluator_port import EvaluatorPort
from geosolver._internal.pipeline.contracts.external_pipeline_config import (
    SEARCH_MODE_DISCO_MADS,
    SEARCH_MODE_HYBRID_LEGACY_NOMAD,
    SEARCH_MODE_SCIPY_MULTISTART,
)
from geosolver._internal.pipeline.contracts.global_search_port import GlobalSearchPort
from geosolver._internal.pipeline.contracts.problem_bundle import ProblemBundle
from geosolver._internal.pipeline.evaluator.classify_evaluation_failure import (
    EvaluationStatus,
)
from geosolver._internal.pipeline.search.build_guard_feasible_ledger import (
    build_guard_feasible_ledger,
)
from geosolver._internal.pipeline.search.deduplicate_search_candidates import (
    deduplicate_search_candidates,
)
from geosolver._internal.pipeline.search.nomad_backend import NomadBackend
from geosolver._internal.pipeline.search.nomad_config import NomadConfig
from geosolver._internal.pipeline.search.scipy_multistart_backend import (
    ScipyMultistartBackend,
)
from geosolver._internal.pipeline.search.select_search_start_points import select_search_start_points

from .run_initial_probe import InitialProbeResult


def _merge_search_diagnostics(
    *,
    first: dict[str, object],
    second: dict[str, object],
) -> dict[str, object]:
    if not first:
        return dict(second)
    if not second:
        return dict(first)
    merged = dict(first)
    first_events = first.get("local_start_events", ())
    second_events = second.get("local_start_events", ())
    local_start_events = list(first_events) if isinstance(first_events, (tuple, list)) else []
    if isinstance(second_events, (tuple, list)):
        local_start_events.extend(second_events)
    if local_start_events:
        merged["local_start_events"] = tuple(local_start_events)
    status_counts: dict[str, int] = {}
    for source in (first, second):
        source_counts = source.get("local_start_status_counts", {})
        if not isinstance(source_counts, dict):
            continue
        for status, count in source_counts.items():
            key = str(status)
            status_counts[key] = status_counts.get(key, 0) + int(count)
    if status_counts:
        merged["local_start_status_counts"] = status_counts
    per_seed_counts: dict[str, dict[str, int]] = {}
    for source in (first, second):
        source_per_seed = source.get("local_start_status_counts_by_seed", {})
        if not isinstance(source_per_seed, dict):
            continue
        for seed, counts in source_per_seed.items():
            if not isinstance(counts, dict):
                continue
            merged_counts = per_seed_counts.setdefault(str(seed), {})
            for status, count in counts.items():
                key = str(status)
                merged_counts[key] = merged_counts.get(key, 0) + int(count)
    if per_seed_counts:
        merged["local_start_status_counts_by_seed"] = per_seed_counts
    return merged

def _build_search_backend(
    *,
    config: NomadConfig,
    start_points: list[list[float]],
    search_mode: str,
    constraint_scales: tuple[float, ...] | None = None,
) -> GlobalSearchPort:
    """Build the phase-A backend requested by the pipeline search mode."""
    if search_mode == SEARCH_MODE_SCIPY_MULTISTART:
        return ScipyMultistartBackend(
            config=config,
            start_points=tuple(start_points),
            constraint_scales=constraint_scales,
        )
    return NomadBackend(
        config=config,
        start_points=tuple(start_points),
        constraint_scales=constraint_scales,
    )


def _attach_search_diagnostic(
    result: SearchBatchResult,
    *,
    key: str,
    value: object,
) -> SearchBatchResult:
    diagnostics = dict(result.search_diagnostics)
    diagnostics[str(key)] = value
    return SearchBatchResult(
        candidates=result.candidates,
        evaluation_count=result.evaluation_count,
        failure_ratio=result.failure_ratio,
        all_records=result.all_records,
        guard_feasible_ledger=result.guard_feasible_ledger,
        search_diagnostics=diagnostics,
    )


def _run_scipy_search_pass(
    *,
    bundle: ProblemBundle,
    evaluator: EvaluatorPort,
    bounds: list[tuple[float, float]],
    start_points: tuple[list[float], ...],
    config: NomadConfig,
    guard_feasible_prefix_count: int,
    constraint_scales: tuple[float, ...] | None = None,
    fallback_reason: str | None = None,
) -> SearchBatchResult:
    result = ScipyMultistartBackend(
        config=config,
        start_points=start_points,
        constraint_scales=constraint_scales,
    ).run_search(
        bundle=bundle,
        evaluator=evaluator,
        bounds=bounds,
        search_mode=SEARCH_MODE_SCIPY_MULTISTART,
        guard_feasible_prefix_count=guard_feasible_prefix_count,
    )
    if fallback_reason:
        result = _attach_search_diagnostic(
            result,
            key="nomad_fallback_reason",
            value=str(fallback_reason),
        )
    return result


def _offset_supplemental_seed_values(*, seed_values: tuple[int, ...]) -> tuple[int, ...]:
    seed_offset = len(seed_values)
    return tuple(int(seed) + seed_offset for seed in seed_values)


def _build_supplemental_start_points(
    *,
    start_points: list[list[float]],
    nomad_result: SearchBatchResult,
    max_nomad_prefix_count: int,
    include_nomad_prefix: bool = True,
) -> tuple[list[float], ...]:
    supplemental_start_points: list[list[float]] = []
    seen_points: set[tuple[float, ...]] = set()
    if include_nomad_prefix:
        prefix_limit = max(0, int(max_nomad_prefix_count))
        primary_nomad_candidates = sorted(nomad_result.candidates, key=lambda item: item.score)
        fallback_nomad_candidates = sorted(nomad_result.all_records, key=lambda item: item.score)
        for candidate in tuple(primary_nomad_candidates) + tuple(fallback_nomad_candidates):
            if len(supplemental_start_points) >= prefix_limit:
                break
            point = tuple(candidate.x_float)
            if point in seen_points:
                continue
            supplemental_start_points.append(list(point))
            seen_points.add(point)
    for start_point in start_points:
        point = tuple(start_point)
        if point in seen_points:
            continue
        supplemental_start_points.append(list(start_point))
        seen_points.add(point)
    return tuple(supplemental_start_points)


def _merge_search_results(
    *,
    primary: SearchBatchResult,
    supplemental: SearchBatchResult,
    bounds: list[tuple[float, float]],
    config: NomadConfig,
    guard_feasible_prefix_count: int,
) -> SearchBatchResult:
    all_records = tuple(primary.all_records) + tuple(supplemental.all_records)
    compact_candidates, guard_feasible_ledger = build_guard_feasible_ledger(
        all_records=all_records,
        bounds=bounds,
        compact_keep_count=int(config.keep_after_dedup),
        prefix_count=int(guard_feasible_prefix_count),
    )
    selected = compact_candidates
    if not selected:
        selected = deduplicate_search_candidates(
            candidates=all_records,
            bounds=bounds,
            keep_count=int(config.keep_after_dedup),
            dedup_distance_threshold=float(config.dedup_distance),
            min_per_seed=int(config.min_per_seed_after_dedup),
        )
    evaluation_count = int(primary.evaluation_count) + int(supplemental.evaluation_count)
    failure_count = sum(
        1 for candidate in all_records if candidate.evaluation_status is not EvaluationStatus.OK
    )
    failure_ratio = 1.0 if evaluation_count == 0 else (failure_count / evaluation_count)
    return SearchBatchResult(
        candidates=selected,
        evaluation_count=evaluation_count,
        failure_ratio=failure_ratio,
        all_records=all_records,
        guard_feasible_ledger=guard_feasible_ledger,
        search_diagnostics=_merge_search_diagnostics(
            first=primary.search_diagnostics,
            second=supplemental.search_diagnostics,
        ),
    )


def _empty_search_batch_result() -> SearchBatchResult:
    return SearchBatchResult(
        candidates=(),
        evaluation_count=0,
        failure_ratio=1.0,
        all_records=(),
        guard_feasible_ledger=(),
    )


def _merge_search_batch_results(
    first: SearchBatchResult,
    second: SearchBatchResult,
) -> SearchBatchResult:
    candidates = tuple(first.candidates) + tuple(second.candidates)
    all_records = tuple(first.all_records) + tuple(second.all_records)
    guard_feasible_ledger = tuple(first.guard_feasible_ledger) + tuple(
        second.guard_feasible_ledger
    )
    evaluation_count = int(first.evaluation_count) + int(second.evaluation_count)
    failure_count = sum(
        1 for candidate in all_records if candidate.evaluation_status is not EvaluationStatus.OK
    )
    failure_ratio = 1.0 if evaluation_count == 0 else (failure_count / evaluation_count)
    return SearchBatchResult(
        candidates=candidates,
        evaluation_count=evaluation_count,
        failure_ratio=failure_ratio,
        all_records=all_records,
        guard_feasible_ledger=guard_feasible_ledger,
        search_diagnostics=_merge_search_diagnostics(
            first=first.search_diagnostics,
            second=second.search_diagnostics,
        ),
    )


def _search_deadline_monotonic(config: NomadConfig) -> float | None:
    if config.max_time_sec is None:
        return None
    max_time_sec = float(config.max_time_sec)
    if max_time_sec <= 0.0:
        return None
    return time.monotonic() + max_time_sec


def _remaining_search_budget_sec(deadline_monotonic: float | None) -> float | None:
    if deadline_monotonic is None:
        return None
    return max(0.0, float(deadline_monotonic - time.monotonic()))


def _run_supplemental_search_pass(
    *,
    bundle: ProblemBundle,
    evaluator: EvaluatorPort,
    bounds: list[tuple[float, float]],
    start_points: tuple[list[float], ...],
    config: NomadConfig,
    seed_values: tuple[int, ...],
    budget_sec: float | None,
    guard_feasible_prefix_count: int,
    constraint_scales: tuple[float, ...] | None = None,
) -> SearchBatchResult:
    if budget_sec is not None and budget_sec <= 0.0:
        return _empty_search_batch_result()
    supplemental_config = replace(config, seed_values=seed_values)
    if budget_sec is not None:
        supplemental_config = replace(supplemental_config, max_time_sec=budget_sec)
    return ScipyMultistartBackend(
        config=supplemental_config,
        start_points=start_points,
        constraint_scales=constraint_scales,
    ).run_search(
        bundle=bundle,
        evaluator=evaluator,
        bounds=bounds,
        search_mode=SEARCH_MODE_SCIPY_MULTISTART,
        guard_feasible_prefix_count=guard_feasible_prefix_count,
    )


def run_search(
    *,
    bundle: ProblemBundle,
    evaluator: EvaluatorPort,
    bounds: list[tuple[float, float]],
    initial_probe_result: InitialProbeResult,
    config: NomadConfig,
    search_mode: str = "disco_mads",
    guard_feasible_prefix_min: int = 64,
    guard_feasible_prefix_multiplier: int = 8,
    constraint_scales: tuple[float, ...] | None = None,
) -> SearchBatchResult:
    """Run phase A search with phase-0-derived start points."""
    start_points = select_search_start_points(
        probe_candidates=initial_probe_result.candidates,
        bounds=bounds,
        required_count=len(config.seed_values),
        dedup_distance_threshold=config.start_dedup_distance,
    )
    prefix_count = max(
        int(config.keep_after_dedup) * int(guard_feasible_prefix_multiplier),
        int(guard_feasible_prefix_min),
    )
    if search_mode == SEARCH_MODE_HYBRID_LEGACY_NOMAD:
        search_deadline = _search_deadline_monotonic(config)
        try:
            nomad_result = NomadBackend(
                config=config,
                start_points=tuple(start_points),
                constraint_scales=constraint_scales,
            ).run_search(
                bundle=bundle,
                evaluator=evaluator,
                bounds=bounds,
                search_mode=SEARCH_MODE_DISCO_MADS,
                guard_feasible_prefix_count=prefix_count,
            )
        except ImportError as exc:
            return _run_scipy_search_pass(
                bundle=bundle,
                evaluator=evaluator,
                bounds=bounds,
                start_points=tuple(start_points),
                config=config,
                guard_feasible_prefix_count=prefix_count,
                constraint_scales=constraint_scales,
                fallback_reason=exc,
            )
        remaining_budget_sec = _remaining_search_budget_sec(search_deadline)
        supplemental_start_points = _build_supplemental_start_points(
            start_points=start_points,
            nomad_result=nomad_result,
            max_nomad_prefix_count=len(config.seed_values),
            include_nomad_prefix=True,
        )
        offset_supplemental_start_points = _build_supplemental_start_points(
            start_points=start_points,
            nomad_result=nomad_result,
            max_nomad_prefix_count=len(config.seed_values),
            include_nomad_prefix=False,
        )
        first_pass_budget_sec = (
            None
            if remaining_budget_sec is None
            else max(0.0, float(remaining_budget_sec) / 2.0)
        )
        primary_supplemental_result = _run_supplemental_search_pass(
            bundle=bundle,
            evaluator=evaluator,
            bounds=bounds,
            start_points=supplemental_start_points,
            config=config,
            seed_values=tuple(config.seed_values),
            budget_sec=first_pass_budget_sec,
            guard_feasible_prefix_count=prefix_count,
            constraint_scales=constraint_scales,
        )
        offset_supplemental_result = _run_supplemental_search_pass(
            bundle=bundle,
            evaluator=evaluator,
            bounds=bounds,
            start_points=offset_supplemental_start_points,
            config=config,
            seed_values=_offset_supplemental_seed_values(seed_values=config.seed_values),
            budget_sec=_remaining_search_budget_sec(search_deadline),
            guard_feasible_prefix_count=prefix_count,
            constraint_scales=constraint_scales,
        )
        supplemental_result = _merge_search_batch_results(
            first=primary_supplemental_result,
            second=offset_supplemental_result,
        )
        return _merge_search_results(
            primary=nomad_result,
            supplemental=supplemental_result,
            bounds=bounds,
            config=config,
            guard_feasible_prefix_count=prefix_count,
        )
    backend = _build_search_backend(
        config=config,
        start_points=start_points,
        search_mode=search_mode,
        constraint_scales=constraint_scales,
    )
    try:
        return backend.run_search(
            bundle=bundle,
            evaluator=evaluator,
            bounds=bounds,
            search_mode=search_mode,
            guard_feasible_prefix_count=prefix_count,
        )
    except ImportError as exc:
        if search_mode == SEARCH_MODE_SCIPY_MULTISTART:
            raise
        return _run_scipy_search_pass(
            bundle=bundle,
            evaluator=evaluator,
            bounds=bounds,
            start_points=tuple(start_points),
            config=config,
            guard_feasible_prefix_count=prefix_count,
            constraint_scales=constraint_scales,
            fallback_reason=exc,
        )

