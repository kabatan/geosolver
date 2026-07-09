"""Reproducible equal-family-weighted clustered bootstrap utilities."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_CEILING
import hashlib
import hmac
import json
import math
import os
from pathlib import Path
import random
from typing import Any, Iterable, Mapping, Sequence


BOOTSTRAP_PLAN_VERSION = "family-clustered-bootstrap-v1"


@dataclass(frozen=True, slots=True)
class ClusteredValue:
    family_id: str
    pair_id: str
    value: float


@dataclass(frozen=True, slots=True)
class PairedValue:
    family_id: str
    pair_id: str
    candidate: float
    control: float


@dataclass(frozen=True, slots=True)
class BootstrapPlan:
    """The explicit resample indices are the replay truth, not the RNG seed."""

    version: str
    seed: int
    family_order: tuple[str, ...]
    resample_indices: tuple[tuple[int, ...], ...]
    checksum: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "seed": self.seed,
            "family_order": list(self.family_order),
            "resample_indices": [list(row) for row in self.resample_indices],
            "checksum": self.checksum,
        }


@dataclass(frozen=True, slots=True)
class BootstrapResult:
    estimate: float
    lower_bound: float
    confidence: float
    resample_count: int
    plan_checksum: str


def _plan_payload(
    version: str,
    seed: int,
    family_order: Sequence[str],
    indices: Sequence[Sequence[int]],
) -> dict[str, Any]:
    return {
        "version": version,
        "seed": seed,
        "family_order": list(family_order),
        "resample_indices": [list(row) for row in indices],
    }


def _checksum(payload: Mapping[str, Any]) -> str:
    encoded = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _validate_family_ids(family_ids: Iterable[str]) -> tuple[str, ...]:
    raw = tuple(family_ids)
    if not raw or any(not isinstance(value, str) or not value for value in raw):
        raise ValueError("at least one nonempty family_id is required")
    family_order = tuple(sorted(set(raw)))
    return family_order


def make_bootstrap_plan(
    family_ids: Iterable[str], *, resamples: int = 10_000, seed: int = 0
) -> BootstrapPlan:
    family_order = _validate_family_ids(family_ids)
    if not isinstance(resamples, int) or isinstance(resamples, bool) or resamples < 1:
        raise ValueError("resamples must be a positive integer")
    if not isinstance(seed, int) or isinstance(seed, bool) or seed < 0:
        raise ValueError("seed must be a nonnegative integer")
    rng = random.Random(seed)
    size = len(family_order)
    indices = tuple(
        tuple(rng.randrange(size) for _ in range(size)) for _ in range(resamples)
    )
    payload = _plan_payload(BOOTSTRAP_PLAN_VERSION, seed, family_order, indices)
    return BootstrapPlan(
        version=BOOTSTRAP_PLAN_VERSION,
        seed=seed,
        family_order=family_order,
        resample_indices=indices,
        checksum=_checksum(payload),
    )


def validate_bootstrap_plan(plan: BootstrapPlan) -> None:
    if plan.version != BOOTSTRAP_PLAN_VERSION:
        raise ValueError(f"unsupported bootstrap plan version {plan.version!r}")
    if not isinstance(plan.seed, int) or isinstance(plan.seed, bool) or plan.seed < 0:
        raise ValueError("bootstrap plan seed must be a nonnegative integer")
    if (
        not isinstance(plan.checksum, str)
        or len(plan.checksum) != 64
        or any(character not in "0123456789abcdef" for character in plan.checksum)
    ):
        raise ValueError("bootstrap plan checksum must be a lowercase SHA-256 digest")
    expected_order = _validate_family_ids(plan.family_order)
    if expected_order != plan.family_order:
        raise ValueError("family_order must be sorted and contain no duplicates")
    if not plan.resample_indices:
        raise ValueError("bootstrap plan must contain at least one resample")
    family_count = len(plan.family_order)
    for row_index, row in enumerate(plan.resample_indices):
        if len(row) != family_count:
            raise ValueError(f"resample_indices[{row_index}] has wrong cluster count")
        if any(
            not isinstance(index, int)
            or isinstance(index, bool)
            or not 0 <= index < family_count
            for index in row
        ):
            raise ValueError(f"resample_indices[{row_index}] contains an invalid index")
    expected = _checksum(
        _plan_payload(plan.version, plan.seed, plan.family_order, plan.resample_indices)
    )
    if not hmac.compare_digest(expected, plan.checksum):
        raise ValueError("bootstrap plan checksum mismatch")


def save_bootstrap_plan(plan: BootstrapPlan, path: str | Path) -> None:
    validate_bootstrap_plan(plan)
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(destination.name + ".tmp")
    temporary.write_text(
        json.dumps(plan.to_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    os.replace(temporary, destination)


def load_bootstrap_plan(path: str | Path) -> BootstrapPlan:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or set(raw) != {
        "version",
        "seed",
        "family_order",
        "resample_indices",
        "checksum",
    }:
        raise ValueError("bootstrap plan has unexpected or missing fields")
    try:
        plan = BootstrapPlan(
            version=raw["version"],
            seed=raw["seed"],
            family_order=tuple(raw["family_order"]),
            resample_indices=tuple(tuple(row) for row in raw["resample_indices"]),
            checksum=raw["checksum"],
        )
    except (TypeError, KeyError) as exc:
        raise ValueError("malformed bootstrap plan") from exc
    validate_bootstrap_plan(plan)
    return plan


def _finite_number(value: float, label: str) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label} must be numeric") from exc
    if not math.isfinite(result):
        raise ValueError(f"{label} must be finite")
    return result


def _family_means(values: Iterable[ClusteredValue]) -> dict[str, float]:
    grouped: dict[str, list[float]] = {}
    seen: set[tuple[str, str]] = set()
    for item in values:
        if not item.family_id or not item.pair_id:
            raise ValueError("family_id and pair_id must be nonempty")
        key = (item.family_id, item.pair_id)
        if key in seen:
            raise ValueError(f"duplicate observation {key!r}")
        seen.add(key)
        grouped.setdefault(item.family_id, []).append(
            _finite_number(item.value, f"value for {key!r}")
        )
    if not grouped:
        raise ValueError("at least one clustered value is required")
    return {family: sum(items) / len(items) for family, items in grouped.items()}


def _lower_bound(
    family_means: Mapping[str, float], plan: BootstrapPlan, confidence: float
) -> BootstrapResult:
    validate_bootstrap_plan(plan)
    confidence_value = _finite_number(confidence, "confidence")
    if not 0.0 < confidence_value < 1.0:
        raise ValueError("confidence must be strictly between zero and one")
    if set(family_means) != set(plan.family_order):
        raise ValueError("bootstrap plan families do not match the supplied observations")

    ordered = [family_means[family] for family in plan.family_order]
    samples = sorted(
        sum(ordered[index] for index in row) / len(row)
        for row in plan.resample_indices
    )
    tail_mass = Decimal(1) - Decimal(str(confidence_value))
    rank = int(
        (tail_mass * len(samples)).to_integral_value(rounding=ROUND_CEILING)
    ) - 1
    rank = max(0, min(rank, len(samples) - 1))
    return BootstrapResult(
        estimate=sum(ordered) / len(ordered),
        lower_bound=samples[rank],
        confidence=confidence_value,
        resample_count=len(samples),
        plan_checksum=plan.checksum,
    )


def family_clustered_lower_bound(
    values: Iterable[ClusteredValue],
    *,
    plan: BootstrapPlan | None = None,
    resamples: int = 10_000,
    seed: int = 0,
    confidence: float = 0.95,
) -> BootstrapResult:
    means = _family_means(values)
    selected_plan = plan or make_bootstrap_plan(means, resamples=resamples, seed=seed)
    return _lower_bound(means, selected_plan, confidence)


def family_clustered_paired_bootstrap(
    values: Iterable[PairedValue],
    *,
    plan: BootstrapPlan | None = None,
    resamples: int = 10_000,
    seed: int = 0,
    confidence: float = 0.95,
) -> BootstrapResult:
    differences = (
        ClusteredValue(
            family_id=item.family_id,
            pair_id=item.pair_id,
            value=_finite_number(item.candidate, "candidate")
            - _finite_number(item.control, "control"),
        )
        for item in values
    )
    return family_clustered_lower_bound(
        differences,
        plan=plan,
        resamples=resamples,
        seed=seed,
        confidence=confidence,
    )
