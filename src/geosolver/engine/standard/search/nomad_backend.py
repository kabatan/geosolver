"""NOMAD global-search backend implementation."""

from __future__ import annotations

import time
from dataclasses import dataclass, replace

from geosolver.engine.standard.contracts.candidate_record import FloatCandidate, SearchBatchResult
from geosolver.engine.standard.contracts.evaluator_port import EvaluatorPort
from geosolver.engine.standard.contracts.global_search_port import GlobalSearchPort
from geosolver.engine.standard.contracts.problem_bundle import ProblemBundle
from geosolver.engine.standard.interpreter.compile.infer_bounds import infer_bound_expansion_locks

from .build_guard_feasible_ledger import build_guard_feasible_ledger
from .deduplicate_search_candidates import deduplicate_search_candidates
from .nomad_blackbox_adapter import NomadBlackboxAdapter
from .nomad_config import NomadConfig


def _expand_bounds(
    bounds: list[tuple[float, float]],
    ratio: float,
    *,
    expansion_locks: tuple[tuple[bool, bool], ...] | None = None,
) -> list[tuple[float, float]]:
    expanded: list[tuple[float, float]] = []
    for index, (low, high) in enumerate(bounds):
        width = high - low
        margin = width * float(ratio)
        lower_locked = False
        upper_locked = False
        if expansion_locks is not None and index < len(expansion_locks):
            lower_locked, upper_locked = expansion_locks[index]
        next_low = low if lower_locked else low - margin
        next_high = high if upper_locked else high + margin
        expanded.append((next_low, next_high))
    return expanded


def _import_pynomad() -> object:
    try:
        import PyNomad  # type: ignore[import-not-found]
    except Exception as exc:
        raise ImportError(
            "PyNomad (provided by PyNomadBBO) is required for external pipeline search "
            "backend (no silent fallback)."
        ) from exc
    return PyNomad


@dataclass(frozen=True)
class NomadBackend(GlobalSearchPort):
    """Run PyNomad with seed-wise execution and candidate aggregation."""

    config: NomadConfig
    start_points: tuple[list[float], ...]
    constraint_scales: tuple[float, ...] | None = None

    def run_search(
        self,
        *,
        bundle: ProblemBundle,
        evaluator: EvaluatorPort,
        bounds: list[tuple[float, float]],
        search_mode: str = "disco_mads",
        guard_feasible_prefix_count: int | None = None,
    ) -> SearchBatchResult:
        if not self.start_points:
            raise ValueError("start_points must not be empty")
        py_nomad = _import_pynomad()
        expansion_locks = tuple(
            infer_bound_expansion_locks(
                bundle.spec,
                bundle.var_names,
            )
        )
        expanded_bounds = _expand_bounds(
            bounds,
            self.config.bound_expansion_ratio,
            expansion_locks=expansion_locks,
        )
        lower_bounds = [low for low, _high in expanded_bounds]
        upper_bounds = [high for _low, high in expanded_bounds]
        all_candidates: list[FloatCandidate] = []
        all_records: list[FloatCandidate] = []
        total_evals = 0
        total_failures = 0
        search_deadline = (
            None
            if self.config.max_time_sec is None
            else time.monotonic() + max(0.0, float(self.config.max_time_sec))
        )
        seed_values = tuple(self.config.seed_values)
        for index, seed in enumerate(seed_values):
            remaining_seed_count = len(seed_values) - index
            seed_config = self.config
            if search_deadline is not None:
                remaining = max(0.0, search_deadline - time.monotonic())
                if remaining <= 0.0:
                    break
                seed_config = replace(
                    self.config,
                    max_time_sec=remaining / max(1, remaining_seed_count),
                )
            adapter = NomadBlackboxAdapter(
                evaluator=evaluator,
                config=seed_config,
                origin_seed=int(seed),
                origin_start_point_index=index % len(self.start_points),
                constraint_scales=self.constraint_scales,
                deadline_monotonic=(
                    None
                    if seed_config.max_time_sec is None
                    else time.monotonic() + seed_config.max_time_sec
                ),
            )
            py_nomad.setSeed(int(seed))
            start = self.start_points[index % len(self.start_points)]
            params = seed_config.build_params(
                dimension=len(bounds),
                seed=int(seed),
                search_mode=search_mode,
            )
            py_nomad.optimize(
                adapter,
                start,
                lower_bounds,
                upper_bounds,
                params,
            )
            total_evals += adapter.evaluation_count
            total_failures += adapter.failure_count
            run_top = sorted(adapter.records, key=lambda item: item.score)[
                : self.config.keep_per_run
            ]
            all_candidates.extend(run_top)
            all_records.extend(adapter.records)
        prefix_count = (
            int(guard_feasible_prefix_count)
            if guard_feasible_prefix_count is not None
            else int(self.config.keep_after_dedup)
        )
        compact_candidates, guard_feasible_ledger = build_guard_feasible_ledger(
            all_records=tuple(all_records),
            bounds=bounds,
            compact_keep_count=int(self.config.keep_after_dedup),
            prefix_count=prefix_count,
        )
        selected = compact_candidates
        if not selected:
            selected = deduplicate_search_candidates(
                candidates=tuple(all_candidates),
                bounds=bounds,
                keep_count=self.config.keep_after_dedup,
                dedup_distance_threshold=self.config.dedup_distance,
                min_per_seed=int(self.config.min_per_seed_after_dedup),
            )
        failure_ratio = 1.0 if total_evals == 0 else (total_failures / total_evals)
        return SearchBatchResult(
            candidates=selected,
            evaluation_count=total_evals,
            failure_ratio=failure_ratio,
            all_records=tuple(all_records),
            guard_feasible_ledger=guard_feasible_ledger,
        )
