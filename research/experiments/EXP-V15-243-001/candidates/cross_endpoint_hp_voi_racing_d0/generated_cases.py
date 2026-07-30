"""Generated opaque backends for the cross-endpoint HP VOI D0."""

from __future__ import annotations

from dataclasses import dataclass, replace
import random
from typing import Mapping

import candidate


FAMILIES = (
    "duplicate_heavy",
    "one_hard_novel",
    "misleading_cheap_rung",
    "all_fail_opaque",
)


@dataclass(frozen=True, slots=True)
class EndpointSpec:
    cheap_improvement: float
    cheap_stability: float
    descriptor_hint: str | None
    deep_descriptor: str | None
    cheap_censored: bool = False
    deep_censors_before_success: int = 0
    opaque: bool = False


@dataclass(frozen=True, slots=True)
class GeneratedCase:
    family: str
    seed: int
    endpoints: tuple[candidate.Endpoint, ...]
    specs: Mapping[str, EndpointSpec]
    expected_descriptors: frozenset[str]


class Backend:
    def __init__(self, case: GeneratedCase) -> None:
        self.case = case
        self.deep_visits: dict[str, int] = {}

    def __call__(self, endpoint, rung, callback_cap, wall_cap):
        spec = self.case.specs[endpoint.key]
        if rung is candidate.Rung.CHEAP:
            return candidate.RungOutcome(
                "CHEAP_CENSORED" if spec.cheap_censored else "CHEAP_OBSERVED",
                callback_cap,
                wall_cap,
                improvement_rate=spec.cheap_improvement,
                stability=spec.cheap_stability,
                descriptor_hint=spec.descriptor_hint,
                censored=spec.cheap_censored,
            )
        visit = self.deep_visits.get(endpoint.key, 0)
        self.deep_visits[endpoint.key] = visit + 1
        if spec.opaque or visit < spec.deep_censors_before_success:
            return candidate.RungOutcome(
                "DEEP_OPAQUE_CENSORED",
                callback_cap,
                wall_cap,
                improvement_rate=spec.cheap_improvement,
                stability=spec.cheap_stability,
                descriptor_hint=spec.descriptor_hint,
                censored=True,
            )
        return candidate.RungOutcome(
            "DEEP_AUTHORITY_READY" if spec.deep_descriptor else "DEEP_NO_AUTHORITY",
            callback_cap,
            wall_cap,
            improvement_rate=spec.cheap_improvement,
            stability=spec.cheap_stability,
            descriptor_hint=spec.descriptor_hint,
            exact_descriptor=spec.deep_descriptor,
            authority_contract_ok=spec.deep_descriptor is not None,
            source_replay_ok=spec.deep_descriptor is not None,
        )


def make_case(family: str, seed: int) -> GeneratedCase:
    if family not in FAMILIES:
        raise ValueError(family)
    rng = random.Random(81_011 + seed)
    endpoints = tuple(
        candidate.Endpoint(
            (rng.uniform(-4.0, 4.0), rng.uniform(-4.0, 4.0)),
            1.0e-8 * (index + 2),
        )
        for index in range(12)
    )
    ordered = sorted(endpoints, key=lambda endpoint: endpoint.key)
    # The stable content-key order is used only by the generator to attach an
    # opaque backend behavior.  The candidate receives neither role nor family.
    endpoints_by_key = {endpoint.key: endpoint for endpoint in endpoints}
    baseline = replace(ordered[0], residual_inf=1.0e-12)
    endpoints_by_key[baseline.key] = baseline
    endpoints = tuple(endpoints_by_key[endpoint.key] for endpoint in endpoints)
    ordered = sorted(endpoints, key=lambda endpoint: endpoint.key)
    specs = {
        endpoint.key: EndpointSpec(0.56, 0.86, "shared", None)
        for endpoint in ordered
    }
    expected: set[str] = set()

    def assign(index: int, **updates) -> None:
        specs[ordered[index].key] = replace(specs[ordered[index].key], **updates)

    assign(0, cheap_improvement=0.78, cheap_stability=0.96,
           descriptor_hint="baseline", deep_descriptor=f"d0:{seed}")
    expected.add(f"d0:{seed}")
    if family == "duplicate_heavy":
        for index, label in ((3, "d1"), (6, "d2"), (9, "d3")):
            assign(index, cheap_improvement=0.84, cheap_stability=0.97,
                   descriptor_hint=f"novel:{label}", deep_descriptor=f"{label}:{seed}")
            expected.add(f"{label}:{seed}")
    elif family == "one_hard_novel":
        assign(3, cheap_improvement=0.80, cheap_stability=0.94,
               descriptor_hint="novel:decoy")
        assign(6, cheap_improvement=0.91, cheap_stability=0.99,
               descriptor_hint="novel:hard", deep_descriptor=f"hard:{seed}")
        expected.add(f"hard:{seed}")
    elif family == "misleading_cheap_rung":
        assign(3, cheap_improvement=1.0, cheap_stability=1.0,
               descriptor_hint="novel:bait", deep_censors_before_success=99)
        assign(4, cheap_improvement=0.92, cheap_stability=0.99,
               descriptor_hint="novel:robust", deep_descriptor=f"robust:{seed}")
        assign(9, cheap_improvement=0.88, cheap_stability=0.97,
               descriptor_hint="novel:second", deep_descriptor=f"second:{seed}")
        expected.update((f"robust:{seed}", f"second:{seed}"))
    else:
        expected.clear()
        for index, endpoint in enumerate(ordered):
            specs[endpoint.key] = EndpointSpec(
                0.95 if index % 3 == 0 else 0.0,
                0.1,
                None if index % 2 else "opaque",
                None,
                cheap_censored=index % 4 == 0,
                deep_censors_before_success=99,
                opaque=True,
            )

    return GeneratedCase(family, seed, endpoints, specs, frozenset(expected))


def permuted(case: GeneratedCase, salt: int) -> GeneratedCase:
    values = list(case.endpoints)
    random.Random(91_003 + 101 * case.seed + salt).shuffle(values)
    return replace(case, endpoints=tuple(values))


__all__ = ["Backend", "FAMILIES", "GeneratedCase", "make_case", "permuted"]
