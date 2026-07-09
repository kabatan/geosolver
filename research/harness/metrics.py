"""Completion, safety, stability, and anytime-prefix benchmark metrics."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping

from .bootstrap import ClusteredValue, family_clustered_lower_bound
from .matching import RunEvaluation
from .models import DomainKind


@dataclass(frozen=True, slots=True)
class SliceMetrics:
    label: str
    run_count: int
    family_count: int
    p_full_validated: float | None
    p_full_validated_lower_95: float | None
    exact_eligible_run_count: int
    p_full_exact: float | None
    p_full_exact_lower_95: float | None
    false_exact_count: int
    false_validated_count: int
    false_branch_count: int
    false_boundary_count: int
    false_complete_count: int

    @property
    def safety_pass(self) -> bool:
        return not any(
            (
                self.false_exact_count,
                self.false_validated_count,
                self.false_branch_count,
                self.false_boundary_count,
                self.false_complete_count,
            )
        )


@dataclass(frozen=True, slots=True)
class AggregateMetrics:
    budget_seconds: int
    overall: SliceMetrics
    by_stratum: tuple[SliceMetrics, ...]
    by_domain_kind: tuple[SliceMetrics, ...]


@dataclass(frozen=True, slots=True)
class StabilityCase:
    case_id: str
    family_id: str
    observed_seeds: tuple[int, ...]
    missing_seeds: tuple[int, ...]
    unexpected_seeds: tuple[int, ...]
    success_count: int
    complete_seed_grid: bool
    stable_27_of_30: bool


@dataclass(frozen=True, slots=True)
class StabilityReport:
    budget_seconds: int
    expected_seeds: tuple[int, ...]
    cases: tuple[StabilityCase, ...]
    complete_case_count: int
    stable_case_count: int
    stable_fraction: float | None
    release_pass: bool


@dataclass(frozen=True, slots=True)
class PrefixLoss:
    case_id: str
    seed: int
    lost_target_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class PrefixMonotonicity:
    short_budget_seconds: int
    long_budget_seconds: int
    compared_pairs: int
    missing_short_pairs: tuple[tuple[str, int], ...]
    missing_long_pairs: tuple[tuple[str, int], ...]
    validated_losses: tuple[PrefixLoss, ...]
    exact_losses: tuple[PrefixLoss, ...]
    remaining_short_misses: int
    recovered_short_misses: int
    recovered_fraction: float
    release_pass: bool

    @property
    def no_verified_answer_loss(self) -> bool:
        return not self.validated_losses and not self.exact_losses


def _at_budget(
    evaluations: Iterable[RunEvaluation], budget_seconds: int
) -> tuple[RunEvaluation, ...]:
    if not isinstance(budget_seconds, int) or isinstance(budget_seconds, bool) or budget_seconds < 1:
        raise ValueError("budget_seconds must be a positive integer")
    selected = tuple(item for item in evaluations if item.budget_seconds == budget_seconds)
    seen: set[tuple[str, int]] = set()
    for item in selected:
        key = (item.case_id, item.seed)
        if key in seen:
            raise ValueError(f"duplicate run for case/seed/budget {key + (budget_seconds,)!r}")
        seen.add(key)
    return selected


def _slice(
    label: str,
    evaluations: tuple[RunEvaluation, ...],
    *,
    bootstrap_seed: int,
    bootstrap_resamples: int,
) -> SliceMetrics:
    run_count = len(evaluations)
    families = {item.family_id for item in evaluations}
    p_validated = (
        sum(item.full_validated for item in evaluations) / run_count if run_count else None
    )
    validated_lower = None
    if evaluations:
        validated_lower = family_clustered_lower_bound(
            (
                ClusteredValue(
                    item.family_id,
                    f"{item.case_id}:{item.seed}",
                    float(item.full_validated),
                )
                for item in evaluations
            ),
            resamples=bootstrap_resamples,
            seed=bootstrap_seed,
        ).lower_bound

    exact = tuple(item for item in evaluations if item.exact_eligible)
    p_exact = sum(item.full_exact for item in exact) / len(exact) if exact else None
    exact_lower = None
    if exact:
        exact_lower = family_clustered_lower_bound(
            (
                ClusteredValue(
                    item.family_id,
                    f"{item.case_id}:{item.seed}",
                    float(item.full_exact),
                )
                for item in exact
            ),
            resamples=bootstrap_resamples,
            seed=bootstrap_seed,
        ).lower_bound

    return SliceMetrics(
        label=label,
        run_count=run_count,
        family_count=len(families),
        p_full_validated=p_validated,
        p_full_validated_lower_95=validated_lower,
        exact_eligible_run_count=len(exact),
        p_full_exact=p_exact,
        p_full_exact_lower_95=exact_lower,
        false_exact_count=sum(item.false_exact_count for item in evaluations),
        false_validated_count=sum(item.false_validated_count for item in evaluations),
        false_branch_count=sum(item.false_branch_count for item in evaluations),
        false_boundary_count=sum(item.false_boundary_count for item in evaluations),
        false_complete_count=sum(item.false_complete_count for item in evaluations),
    )


def aggregate_metrics(
    evaluations: Iterable[RunEvaluation],
    *,
    budget_seconds: int,
    bootstrap_seed: int = 0,
    bootstrap_resamples: int = 10_000,
) -> AggregateMetrics:
    """Compute P_full and release-blocking counts, including empty named slices."""

    selected = _at_budget(evaluations, budget_seconds)
    if not selected:
        raise ValueError(f"no evaluations at budget {budget_seconds}")
    if bootstrap_resamples < 1:
        raise ValueError("bootstrap_resamples must be positive")

    overall = _slice(
        "overall",
        selected,
        bootstrap_seed=bootstrap_seed,
        bootstrap_resamples=bootstrap_resamples,
    )
    by_stratum = tuple(
        _slice(
            stratum,
            tuple(item for item in selected if stratum in item.strata),
            bootstrap_seed=bootstrap_seed,
            bootstrap_resamples=bootstrap_resamples,
        )
        for stratum in (f"S{index}" for index in range(1, 9))
    )
    by_domain = tuple(
        _slice(
            domain.value,
            tuple(item for item in selected if item.domain_kind is domain),
            bootstrap_seed=bootstrap_seed,
            bootstrap_resamples=bootstrap_resamples,
        )
        for domain in (DomainKind.BOUNDED, DomainKind.ADAPTIVE_UNBOUNDED)
    )
    return AggregateMetrics(budget_seconds, overall, by_stratum, by_domain)


def stability_27_of_30(
    evaluations: Iterable[RunEvaluation],
    *,
    budget_seconds: int = 180,
    expected_seeds: Iterable[int] = range(30),
    expected_case_families: Mapping[str, str] | None = None,
) -> StabilityReport:
    selected = _at_budget(evaluations, budget_seconds)
    seed_grid = tuple(sorted(set(expected_seeds)))
    if len(seed_grid) != 30 or any(
        not isinstance(seed, int) or isinstance(seed, bool) or seed < 0 for seed in seed_grid
    ):
        raise ValueError("expected_seeds must contain exactly 30 distinct nonnegative integers")

    grouped: dict[str, list[RunEvaluation]] = {}
    for item in selected:
        grouped.setdefault(item.case_id, []).append(item)
    if expected_case_families is not None:
        if any(
            not isinstance(case_id, str)
            or not case_id
            or not isinstance(family_id, str)
            or not family_id
            for case_id, family_id in expected_case_families.items()
        ):
            raise ValueError("expected case and family IDs must be nonempty strings")
        unexpected_cases = set(grouped) - set(expected_case_families)
        if unexpected_cases:
            raise ValueError(f"unexpected cases at stability budget: {sorted(unexpected_cases)!r}")
        for case_id in expected_case_families:
            grouped.setdefault(case_id, [])

    expected = set(seed_grid)
    cases: list[StabilityCase] = []
    for case_id, items in sorted(grouped.items()):
        families = {item.family_id for item in items}
        expected_family = (
            expected_case_families[case_id] if expected_case_families is not None else None
        )
        if expected_family is not None and families and families != {expected_family}:
            raise ValueError(f"case {case_id!r} does not match its expected family")
        if expected_family is None and len(families) != 1:
            raise ValueError(f"case {case_id!r} has inconsistent family IDs")
        observed = {item.seed for item in items}
        missing = tuple(sorted(expected - observed))
        unexpected = tuple(sorted(observed - expected))
        success_count = sum(item.full_validated for item in items if item.seed in expected)
        complete = not missing and not unexpected
        cases.append(
            StabilityCase(
                case_id=case_id,
                family_id=expected_family or next(iter(families)),
                observed_seeds=tuple(sorted(observed)),
                missing_seeds=missing,
                unexpected_seeds=unexpected,
                success_count=success_count,
                complete_seed_grid=complete,
                stable_27_of_30=complete and success_count >= 27,
            )
        )

    stable_count = sum(item.stable_27_of_30 for item in cases)
    complete_count = sum(item.complete_seed_grid for item in cases)
    stable_fraction = stable_count / len(cases) if cases else None
    release_pass = bool(cases) and complete_count == len(cases) and stable_fraction >= 0.9
    return StabilityReport(
        budget_seconds=budget_seconds,
        expected_seeds=seed_grid,
        cases=tuple(cases),
        complete_case_count=complete_count,
        stable_case_count=stable_count,
        stable_fraction=stable_fraction,
        release_pass=release_pass,
    )


def prefix_monotonicity(
    evaluations: Iterable[RunEvaluation],
    *,
    short_budget_seconds: int = 180,
    long_budget_seconds: int = 420,
) -> PrefixMonotonicity:
    """Check target-set inclusion and recovery of the short-budget misses."""

    if long_budget_seconds <= short_budget_seconds:
        raise ValueError("long_budget_seconds must exceed short_budget_seconds")
    all_evaluations = tuple(evaluations)
    short = {
        (item.case_id, item.seed): item
        for item in _at_budget(all_evaluations, short_budget_seconds)
    }
    long = {
        (item.case_id, item.seed): item
        for item in _at_budget(all_evaluations, long_budget_seconds)
    }
    missing_short = tuple(sorted(long.keys() - short.keys()))
    missing_long = tuple(sorted(short.keys() - long.keys()))
    common = sorted(short.keys() & long.keys())

    validated_losses: list[PrefixLoss] = []
    exact_losses: list[PrefixLoss] = []
    for key in common:
        before = short[key]
        after = long[key]
        if before.family_id != after.family_id:
            raise ValueError(f"case/seed {key!r} changes family between budgets")
        if before.gold_target_ids != after.gold_target_ids:
            raise ValueError(f"case/seed {key!r} changes Gold targets between budgets")
        lost_validated = before.covered_validated_targets - after.covered_validated_targets
        lost_exact = before.covered_exact_targets - after.covered_exact_targets
        if lost_validated:
            validated_losses.append(PrefixLoss(*key, tuple(sorted(lost_validated))))
        if lost_exact:
            exact_losses.append(PrefixLoss(*key, tuple(sorted(lost_exact))))

    short_misses = [key for key, item in short.items() if not item.full_validated]
    recovered = sum(key in long and long[key].full_validated for key in short_misses)
    recovered_fraction = recovered / len(short_misses) if short_misses else 1.0
    release_pass = (
        bool(common)
        and not missing_short
        and not missing_long
        and not validated_losses
        and not exact_losses
        and recovered_fraction >= 0.5
    )
    return PrefixMonotonicity(
        short_budget_seconds=short_budget_seconds,
        long_budget_seconds=long_budget_seconds,
        compared_pairs=len(common),
        missing_short_pairs=missing_short,
        missing_long_pairs=missing_long,
        validated_losses=tuple(validated_losses),
        exact_losses=tuple(exact_losses),
        remaining_short_misses=len(short_misses),
        recovered_short_misses=recovered,
        recovered_fraction=recovered_fraction,
        release_pass=release_pass,
    )
