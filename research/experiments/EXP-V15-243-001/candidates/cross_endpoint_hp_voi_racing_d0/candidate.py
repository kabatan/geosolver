"""Censor-aware cross-endpoint HP value-of-information racing.

The first three slots in every four-slot cycle are immutable first probes of
previously untried endpoints.  Only the fourth slot may revisit an endpoint,
so at least 75% of equal-cost work remains breadth insurance while untried
endpoints exist.  Retry priority uses only cheap-rung progress, stability,
descriptor-hint novelty and endpoint-local censor history.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from enum import Enum
import hashlib
import math
import struct
from typing import Callable, Sequence


class Arm(str, Enum):
    CONTROL = "FIFO_RESIDUAL_DEPTH"
    CANDIDATE = "CENSOR_AWARE_CROSS_ENDPOINT_VOI_75"


class Rung(str, Enum):
    CHEAP = "ORDINARY_LOW_PRECISION"
    DEEP = "HIGH_PRECISION_RESTART"


@dataclass(frozen=True, slots=True)
class Endpoint:
    values: tuple[float, ...]
    residual_inf: float
    semantic_valid: bool = True
    guard_ok: bool = True
    hard_feasible: bool = True

    def __post_init__(self) -> None:
        if not self.values or not all(math.isfinite(value) for value in self.values):
            raise ValueError("endpoint values must be finite and nonempty")
        if not math.isfinite(self.residual_inf) or self.residual_inf < 0.0:
            raise ValueError("residual_inf must be finite and nonnegative")
        if any(type(value) is not bool for value in (
            self.semantic_valid, self.guard_ok, self.hard_feasible
        )):
            raise TypeError("endpoint safety flags must be plain booleans")

    @property
    def source_safe(self) -> bool:
        return self.semantic_valid and self.guard_ok and self.hard_feasible

    @property
    def key(self) -> str:
        payload = struct.pack(">I", len(self.values)) + b"".join(
            struct.pack(">d", value) for value in self.values
        )
        return hashlib.sha256(payload).hexdigest()


@dataclass(frozen=True, slots=True)
class RungOutcome:
    status: str
    charged_callbacks: int
    charged_wall_seconds: float
    improvement_rate: float = 0.0
    stability: float = 0.0
    descriptor_hint: str | None = None
    exact_descriptor: str | None = None
    authority_contract_ok: bool = False
    source_replay_ok: bool = False
    censored: bool = False


@dataclass(frozen=True, slots=True)
class Configuration:
    maximum_dispatches: int = 16
    callbacks_per_dispatch: int = 4
    wall_seconds_per_dispatch: float = 0.25
    insurance_numerator: int = 3
    insurance_denominator: int = 4

    def __post_init__(self) -> None:
        if self.maximum_dispatches < 1 or self.callbacks_per_dispatch < 1:
            raise ValueError("dispatch budgets must be positive")
        if not math.isfinite(self.wall_seconds_per_dispatch) or self.wall_seconds_per_dispatch <= 0:
            raise ValueError("wall budget must be finite and positive")
        if (self.insurance_numerator, self.insurance_denominator) != (3, 4):
            raise ValueError("D0 freezes a three-of-four untried insurance cycle")


@dataclass(frozen=True, slots=True)
class Attempt:
    ordinal: int
    endpoint_key: str
    rung: str
    status: str
    censored: bool


@dataclass(frozen=True, slots=True)
class RacingResult:
    descriptors: tuple[str, ...]
    attempts: tuple[Attempt, ...]
    status: str
    charged_callbacks: int
    charged_wall_seconds: float
    untried_dispatches: int
    revisit_dispatches: int
    invalid_outcomes: int
    censored_outcomes: int
    first_probe_insurance_holds: bool
    retained_endpoint_count: int


Runner = Callable[[Endpoint, Rung, int, float], RungOutcome]


@dataclass
class _State:
    cheap: RungOutcome | None = None
    deep_attempts: int = 0
    deep_completed: int = 0
    deep_censored: int = 0


def _plain_finite(value: object, *, lower: float, upper: float) -> bool:
    return (
        type(value) in (int, float)
        and math.isfinite(float(value))
        and lower <= float(value) <= upper
    )


def _valid_outcome(value: object, rung: Rung, cfg: Configuration) -> bool:
    # Exact type blocks adversarial numeric/string/dataclass subclasses before
    # any overloaded property or comparison can escape the fail-closed seam.
    if type(value) is not RungOutcome or type(value.status) is not str:
        return False
    if type(value.charged_callbacks) is not int or not (
        0 <= value.charged_callbacks <= cfg.callbacks_per_dispatch
    ):
        return False
    if not _plain_finite(
        value.charged_wall_seconds,
        lower=0.0,
        upper=cfg.wall_seconds_per_dispatch,
    ):
        return False
    if not _plain_finite(value.improvement_rate, lower=0.0, upper=1.0):
        return False
    if not _plain_finite(value.stability, lower=0.0, upper=1.0):
        return False
    if any(type(flag) is not bool for flag in (
        value.authority_contract_ok, value.source_replay_ok, value.censored
    )):
        return False
    for text in (value.descriptor_hint, value.exact_descriptor):
        if text is not None and (type(text) is not str or not text):
            return False
    if rung is Rung.CHEAP and value.exact_descriptor is not None:
        return False
    if value.censored and value.exact_descriptor is not None:
        return False
    return True


def _fallback_outcome(cfg: Configuration) -> RungOutcome:
    return RungOutcome(
        "INVALID_OUTCOME_FAIL_CLOSED",
        cfg.callbacks_per_dispatch,
        cfg.wall_seconds_per_dispatch,
        censored=True,
    )


def _baseline(states: dict[str, _State], endpoints: dict[str, Endpoint]) -> str:
    observed = [key for key, state in states.items() if state.cheap is not None]
    return min(observed, key=lambda key: (endpoints[key].residual_inf, key))


def _voi_score(
    key: str,
    states: dict[str, _State],
    endpoints: dict[str, Endpoint],
    hint_counts: Counter[str],
) -> float:
    state = states[key]
    cheap = state.cheap
    if cheap is None:
        return -math.inf
    novelty = 1.0
    if cheap.descriptor_hint is not None:
        novelty = 1.0 / max(1, hint_counts[cheap.descriptor_hint])
    cheap_survival = 0.25 if cheap.censored else 1.0
    deep_survival = (1.0 + state.deep_completed) / (1.0 + state.deep_attempts)
    diminishing = 1.0 / (1.0 + state.deep_attempts)
    quality = (
        0.45 * float(cheap.improvement_rate)
        + 0.35 * float(cheap.stability)
        + 0.20 * novelty
    )
    score = cheap_survival * deep_survival * diminishing * quality
    if key == _baseline(states, endpoints):
        score += 0.35 * diminishing
    return score


def _choose_revisit(
    arm: Arm,
    states: dict[str, _State],
    endpoints: dict[str, Endpoint],
) -> str:
    baseline = _baseline(states, endpoints)
    if arm is Arm.CONTROL or sum(state.deep_attempts for state in states.values()) == 0:
        return baseline
    hint_counts: Counter[str] = Counter(
        state.cheap.descriptor_hint
        for state in states.values()
        if state.cheap is not None and state.cheap.descriptor_hint is not None
    )
    return min(
        (key for key, state in states.items() if state.cheap is not None),
        key=lambda key: (-_voi_score(key, states, endpoints, hint_counts), key),
    )


def run_racing(
    endpoints: Sequence[Endpoint],
    runner: Runner,
    arm: Arm,
    configuration: Configuration = Configuration(),
    *,
    maximum_dispatches: int | None = None,
) -> RacingResult:
    """Run a prefix-stable equal-cost schedule; every restart is fully charged."""

    limit = configuration.maximum_dispatches if maximum_dispatches is None else maximum_dispatches
    if type(limit) is not int or not 0 <= limit <= configuration.maximum_dispatches:
        raise ValueError("maximum_dispatches outside frozen bound")
    safe = {endpoint.key: endpoint for endpoint in endpoints if endpoint.source_safe}
    if len(safe) != sum(endpoint.source_safe for endpoint in endpoints):
        return RacingResult((), (), "DUPLICATE_ENDPOINT_KEY", 0, 0.0, 0, 0, 0, 0, True, len(safe))
    ordered = sorted(safe)
    if not ordered or limit == 0:
        return RacingResult((), (), "NO_SAFE_WORK", 0, 0.0, 0, 0, 0, 0, True, len(safe))

    states = {key: _State() for key in ordered}
    descriptors: set[str] = set()
    attempts: list[Attempt] = []
    invalid = censored = first_probes = revisits = 0
    for ordinal in range(limit):
        untried = [key for key in ordered if states[key].cheap is None]
        insurance_slot = ordinal % configuration.insurance_denominator < configuration.insurance_numerator
        if untried and (insurance_slot or not any(state.cheap for state in states.values())):
            key = untried[0]
            rung = Rung.CHEAP
            first_probes += 1
        elif any(state.cheap for state in states.values()):
            key = _choose_revisit(arm, states, safe)
            rung = Rung.DEEP
            revisits += 1
        else:
            key = untried[0]
            rung = Rung.CHEAP
            first_probes += 1

        try:
            outcome = runner(
                safe[key],
                rung,
                configuration.callbacks_per_dispatch,
                configuration.wall_seconds_per_dispatch,
            )
        except Exception:
            outcome = _fallback_outcome(configuration)
            invalid += 1
        if not _valid_outcome(outcome, rung, configuration):
            outcome = _fallback_outcome(configuration)
            invalid += 1
        if outcome.censored:
            censored += 1
        state = states[key]
        if rung is Rung.CHEAP:
            state.cheap = outcome
        else:
            state.deep_attempts += 1
            if outcome.censored:
                state.deep_censored += 1
            else:
                state.deep_completed += 1
            if (
                outcome.exact_descriptor is not None
                and outcome.authority_contract_ok
                and outcome.source_replay_ok
                and not outcome.censored
            ):
                descriptors.add(outcome.exact_descriptor)
        attempts.append(Attempt(ordinal, key, rung.value, outcome.status, outcome.censored))

    charged_callbacks = limit * configuration.callbacks_per_dispatch
    charged_wall = limit * configuration.wall_seconds_per_dispatch
    insurance_holds = first_probes * configuration.insurance_denominator >= (
        configuration.insurance_numerator * len(attempts)
    ) or not any(state.cheap is None for state in states.values())
    return RacingResult(
        tuple(sorted(descriptors)),
        tuple(attempts),
        "OK" if invalid == 0 and insurance_holds else "FAIL_CLOSED",
        charged_callbacks,
        charged_wall,
        first_probes,
        revisits,
        invalid,
        censored,
        insurance_holds,
        len(states),
    )


def configuration_manifest() -> dict[str, object]:
    return {
        "mechanism": "censor-aware cross-endpoint HP value-of-information racing",
        "routing_inputs": [
            "ordinary/low-precision residual improvement rate",
            "ordinary/low-precision stability",
            "descriptor-hint novelty",
            "endpoint-local censor/completion counts",
            "declared evaluation cost",
        ],
        "untried_insurance_work_fraction_minimum": 0.75,
        "full_restart_charging": True,
        "successful_descriptor_does_not_stop_cross_endpoint_search": True,
        "truth_case_family_id_previous_case_outcome_routing": False,
        "pslq_grid_or_path_reordering": False,
    }


__all__ = [
    "Arm", "Attempt", "Configuration", "Endpoint", "RacingResult", "Rung",
    "RungOutcome", "configuration_manifest", "run_racing",
]
