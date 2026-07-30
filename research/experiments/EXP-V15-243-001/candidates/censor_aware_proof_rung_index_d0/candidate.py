"""Disposable censor-aware proof-rung scheduler D0 for synthetic traces only."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
from typing import Literal, Sequence


Strategy = Literal["fifo", "round-robin", "static-shortest", "censor-index"]


@dataclass(frozen=True)
class TaskSpec:
    public_estimated_rungs: tuple[float, ...]
    hidden_durations: tuple[float, ...]
    hidden_success: tuple[bool, ...]

    def __post_init__(self) -> None:
        count = len(self.public_estimated_rungs)
        if count == 0 or len(self.hidden_durations) != count or len(self.hidden_success) != count:
            raise ValueError("rung vectors must have equal positive length")
        if any(not math.isfinite(value) or value <= 0.0 for value in self.public_estimated_rungs):
            raise ValueError("public rung estimates must be finite and positive")
        if any(not math.isfinite(value) or value <= 0.0 for value in self.hidden_durations):
            raise ValueError("hidden rung durations must be finite and positive")


@dataclass
class _State:
    progress: int = 0
    elapsed: float = 0.0
    served: bool = False
    wait_turns: int = 0
    terminal: bool = False
    certified: bool = False
    failed: bool = False


@dataclass(frozen=True)
class PublicView:
    ordinal: int
    estimates: tuple[float, ...]
    progress: int
    elapsed: float
    served: bool
    wait_turns: int


@dataclass(frozen=True)
class RunResult:
    strategy: Strategy
    certificates: int
    failures: int
    unresolved: int
    first_served: int
    eligible: int
    side_spent: float
    side_cap: float
    baseline_spent: float
    baseline_reserved: float
    baseline_sha256: str
    selections: tuple[int, ...]
    observations: tuple[tuple[int, int, int, str], ...]
    terminal_resurrection_count: int
    future_fields_exposed_to_policy: int


class _HazardIndex:
    """Discrete posterior hazards from completion and censor observations."""

    def __init__(self) -> None:
        self.at_risk: dict[tuple[int, int], int] = {}
        self.events: dict[tuple[int, int], int] = {}
        self.stage_at_risk: dict[int, int] = {}
        self.stage_events: dict[int, int] = {}

    @staticmethod
    def _bucket(elapsed: float) -> int:
        return min(7, int(math.floor(max(0.0, elapsed))))

    def observe(self, progress: int, elapsed_before: float, completed: bool) -> None:
        key = (progress, self._bucket(elapsed_before))
        self.at_risk[key] = self.at_risk.get(key, 0) + 1
        self.stage_at_risk[progress] = self.stage_at_risk.get(progress, 0) + 1
        if completed:
            self.events[key] = self.events.get(key, 0) + 1
            self.stage_events[progress] = self.stage_events.get(progress, 0) + 1

    def index(self, view: PublicView) -> tuple[float, ...]:
        if not view.served:
            # A hard first-service stratum prevents proof-rung starvation.
            return (1.0, -view.estimates[view.progress], -sum(view.estimates), 0.0)
        key = (view.progress, self._bucket(view.elapsed))
        prior_hazard = 1.0 - math.exp(
            -1.0 / max(0.05, view.estimates[view.progress])
        )
        prior_weight = 2.0
        local_hazard = (
            self.events.get(key, 0) + prior_weight * prior_hazard
        ) / (self.at_risk.get(key, 0) + prior_weight)
        stage_hazard = (
            self.stage_events.get(view.progress, 0) + prior_weight * prior_hazard
        ) / (self.stage_at_risk.get(view.progress, 0) + prior_weight)
        hazard = 0.5 * local_hazard + 0.5 * stage_hazard
        remaining = len(view.estimates) - view.progress
        progress_fraction = (view.progress + 1.0) / len(view.estimates)
        # Near-certificate state matters, but cannot swamp a posterior hazard
        # collapse caused by repeated right censoring.
        certificate_nearness = (0.75 + 0.25 * progress_fraction) / (remaining + 0.5)
        wait_bonus = 1.0 + min(12, view.wait_turns) * 0.025
        score = hazard * certificate_nearness * wait_bonus
        # The final terms are public, ID-free tie breakers.
        return (
            0.0,
            score,
            -view.estimates[view.progress],
            -sum(view.estimates[view.progress :]),
        )


def _baseline(total_budget: float) -> tuple[float, float, str]:
    reserved = 0.75 * total_budget
    payload = json.dumps(
        [
            {"ordinal": 0, "payload": "ordinary-A", "cost": reserved / 3.0},
            {"ordinal": 1, "payload": "ordinary-B", "cost": reserved / 3.0},
            {"ordinal": 2, "payload": "ordinary-C", "cost": reserved / 3.0},
        ],
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return reserved, reserved, hashlib.sha256(payload).hexdigest()


def _views(specs: Sequence[TaskSpec], states: Sequence[_State]) -> list[PublicView]:
    return [
        PublicView(
            ordinal=index,
            estimates=spec.public_estimated_rungs,
            progress=state.progress,
            elapsed=state.elapsed,
            served=state.served,
            wait_turns=state.wait_turns,
        )
        for index, (spec, state) in enumerate(zip(specs, states, strict=True))
        if not state.terminal
    ]


def run(
    specs: Sequence[TaskSpec],
    *,
    strategy: Strategy,
    total_budget: float = 100.0,
    quantum: float = 1.0,
) -> RunResult:
    if not specs or total_budget <= 0.0 or quantum <= 0.0:
        raise ValueError("positive tasks, budget, and quantum required")
    baseline_reserved, baseline_spent, baseline_sha = _baseline(total_budget)
    side_cap = 0.25 * total_budget
    side_spent = 0.0
    states = [_State() for _ in specs]
    hazard = _HazardIndex()
    rr_cursor = -1
    selections: list[int] = []
    observations: list[tuple[int, int, int, str]] = []
    terminal_resurrections = 0

    while side_spent < side_cap - 1.0e-12:
        active = _views(specs, states)
        if not active:
            break
        if strategy == "fifo":
            chosen = active[0]
        elif strategy == "round-robin":
            eligible = sorted(view.ordinal for view in active)
            later = [ordinal for ordinal in eligible if ordinal > rr_cursor]
            ordinal = later[0] if later else eligible[0]
            chosen = next(view for view in active if view.ordinal == ordinal)
            rr_cursor = ordinal
        elif strategy == "static-shortest":
            chosen = min(
                active,
                key=lambda view: (
                    sum(view.estimates[view.progress :]),
                    view.estimates[view.progress],
                    view.ordinal,
                ),
            )
        elif strategy == "censor-index":
            chosen = max(active, key=lambda view: (hazard.index(view), -view.ordinal))
        else:
            raise ValueError(strategy)

        state = states[chosen.ordinal]
        if state.terminal:
            terminal_resurrections += 1
            raise AssertionError("terminal proof route resurrected")
        spec = specs[chosen.ordinal]
        progress_before = state.progress
        elapsed_before = state.elapsed
        allocation = min(quantum, side_cap - side_spent)
        remaining = spec.hidden_durations[state.progress] - state.elapsed
        used = min(allocation, remaining)
        side_spent += used
        state.elapsed += used
        state.served = True
        selections.append(chosen.ordinal)
        for index, other in enumerate(states):
            if other.terminal:
                continue
            other.wait_turns = 0 if index == chosen.ordinal else other.wait_turns + 1

        completed = remaining <= allocation + 1.0e-12
        if strategy == "censor-index":
            hazard.observe(progress_before, elapsed_before, completed)
        if completed:
            success = spec.hidden_success[state.progress]
            event = "complete-pass" if success else "complete-fail"
            observations.append((chosen.ordinal, progress_before, int(elapsed_before), event))
            if not success:
                state.failed = True
                state.terminal = True
            elif state.progress + 1 == len(spec.hidden_durations):
                state.progress += 1
                state.certified = True
                state.terminal = True
            else:
                state.progress += 1
                state.elapsed = 0.0
        else:
            observations.append((chosen.ordinal, progress_before, int(elapsed_before), "censored"))

    return RunResult(
        strategy=strategy,
        certificates=sum(state.certified for state in states),
        failures=sum(state.failed for state in states),
        unresolved=sum(not state.terminal for state in states),
        first_served=sum(state.served for state in states),
        eligible=len(states),
        side_spent=side_spent,
        side_cap=side_cap,
        baseline_spent=baseline_spent,
        baseline_reserved=baseline_reserved,
        baseline_sha256=baseline_sha,
        selections=tuple(selections),
        observations=tuple(observations),
        terminal_resurrection_count=terminal_resurrections,
        future_fields_exposed_to_policy=0,
    )


__all__ = ["RunResult", "Strategy", "TaskSpec", "run"]
