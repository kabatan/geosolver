"""Protected 75/25 scheduler over invariant failed-guard species features.

This is a narrow revival of the frozen guard-stratum G1 mechanism.  Endpoint
admission and descriptor types are imported byte-for-byte from the frozen
candidate.  Absolute coordinates are never scored.  Three quarters of the
control ordinals remain byte-identical in place; only ordinal class 3 mod 4
may be reordered using a whitening transform fitted once to the untouched
prefix margin/residual observations.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import sys
from typing import Mapping, Sequence

import numpy as np


SCHEMA = "geotarget.protected-affine-invariant-guard-species/v1"
REFERENCE_NAME = "protected_affine_invariant_guard_species_portfolio"
INSURANCE_SOURCE = "counter_product_cauchy"
OLD_SOURCE = Path(
    "/home/kabatan/work/solver-experiment-runtime/solver/research/experiments/"
    "EXP-V15-243-001/candidates/guard_stratum_novelty/candidate.py"
)
OLD_CANDIDATE_SHA256 = "e61562f1ec880ad6618646b804cf2151a2a595481b6f13beb4a92bde35d53ffb"


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_base():
    if _digest(OLD_SOURCE) != OLD_CANDIDATE_SHA256:
        raise RuntimeError("frozen guard-stratum candidate bytes changed")
    spec = importlib.util.spec_from_file_location(
        "protected_affine_guard_stratum_base", OLD_SOURCE
    )
    if spec is None or spec.loader is None:
        raise ImportError(OLD_SOURCE)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


BASE = _load_base()
ArchiveConfiguration = BASE.ArchiveConfiguration
ArchiveRecord = BASE.ArchiveRecord
RuntimeDescriptor = BASE.RuntimeDescriptor
ScheduledLaunch = BASE.ScheduledLaunch
TypedMargin = BASE.TypedMargin


def failed_guard_species(descriptor: RuntimeDescriptor) -> tuple[tuple[str, int], ...]:
    """Order/key-free typed species of non-interior source guard leaves."""

    return tuple(
        sorted(Counter(item.kind for item in descriptor.typed_margins if item.margin <= 0).items())
    )


def _species_distance(left: RuntimeDescriptor, right: RuntimeDescriptor) -> float:
    a = Counter(dict(failed_guard_species(left)))
    b = Counter(dict(failed_guard_species(right)))
    keys = set(a) | set(b)
    denominator = max(1, sum(a.values()) + sum(b.values()))
    return sum(abs(a[key] - b[key]) for key in keys) / denominator


@dataclass(frozen=True, slots=True)
class PrefixWhitening:
    """Prefix-owned affine/equation-scale invariant feature transform."""

    guard_schema: tuple[tuple[str, str], ...]
    guard_kinds: tuple[str, ...]
    residual_count: int
    location: np.ndarray
    scale: np.ndarray
    whitener: np.ndarray

    @classmethod
    def fit(cls, descriptors: Sequence[RuntimeDescriptor]) -> "PrefixWhitening":
        if len(descriptors) < 2:
            raise ValueError("at least two prefix observations required")
        schema = tuple((item.kind, item.key) for item in descriptors[0].typed_margins)
        residual_count = len(descriptors[0].raw_residual)
        if not schema or residual_count < 1:
            raise ValueError("typed margins and residual observations required")
        if any(
            not item.finite
            or tuple((margin.kind, margin.key) for margin in item.typed_margins) != schema
            or len(item.raw_residual) != residual_count
            for item in descriptors
        ):
            raise ValueError("incomplete prefix feature schema")
        matrix = np.asarray(
            [
                [float(margin.margin) for margin in item.typed_margins]
                + [abs(float(value)) for value in item.raw_residual]
                for item in descriptors
            ],
            dtype=float,
        )
        if not np.all(np.isfinite(matrix)):
            raise ValueError("prefix feature matrix is nonfinite")
        location = np.median(matrix, axis=0)
        centered = matrix - location
        scale = np.sqrt(np.mean(centered * centered, axis=0))
        scale = np.where(scale > np.finfo(float).tiny, scale, 1.0)
        standardized = centered / scale
        kinds = tuple(kind for kind, _key in schema)
        standardized = cls._canonicalize_rows(standardized, kinds, residual_count)
        covariance = standardized.T @ standardized / max(1, len(descriptors))
        values, vectors = np.linalg.eigh(covariance)
        cutoff = max(1.0, float(np.max(values))) * 1.0e-12
        inverse_root = np.zeros_like(values)
        supported = values > cutoff
        inverse_root[supported] = 1.0 / np.sqrt(values[supported])
        whitener = (vectors * inverse_root) @ vectors.T
        if not np.all(np.isfinite(whitener)):
            raise ValueError("prefix whitener is nonfinite")
        return cls(schema, kinds, residual_count, location, scale, whitener)

    @staticmethod
    def _canonicalize_rows(
        rows: np.ndarray, guard_kinds: tuple[str, ...], residual_count: int
    ) -> np.ndarray:
        rows = np.asarray(rows, dtype=float).copy()
        guard_count = len(guard_kinds)
        for kind in sorted(set(guard_kinds)):
            columns = [index for index, value in enumerate(guard_kinds) if value == kind]
            rows[:, columns] = np.sort(rows[:, columns], axis=1)
        rows[:, guard_count:] = np.sort(rows[:, guard_count:], axis=1)
        if rows.shape[1] != guard_count + residual_count:
            raise ValueError("feature width changed")
        return rows

    def feature(self, descriptor: RuntimeDescriptor) -> np.ndarray:
        schema = tuple((item.kind, item.key) for item in descriptor.typed_margins)
        if (
            not descriptor.finite
            or schema != self.guard_schema
            or len(descriptor.raw_residual) != self.residual_count
        ):
            raise ValueError("descriptor feature schema mismatch")
        raw = np.asarray(
            [float(item.margin) for item in descriptor.typed_margins]
            + [abs(float(value)) for value in descriptor.raw_residual],
            dtype=float,
        )
        standardized = (raw - self.location) / self.scale
        canonical = self._canonicalize_rows(
            standardized[None, :], self.guard_kinds, self.residual_count
        )[0]
        feature = canonical @ self.whitener
        if not np.all(np.isfinite(feature)):
            raise ValueError("descriptor invariant feature is nonfinite")
        return feature

    def distance(self, left: RuntimeDescriptor, right: RuntimeDescriptor) -> float:
        return float(np.linalg.norm(self.feature(left) - self.feature(right)))


@dataclass(frozen=True, slots=True)
class NoveltyScore:
    combined_novelty: float
    species_novelty: float
    invariant_feature_novelty: float
    residual_quality: float
    conditioning_quality: float = 0.0

    @property
    def guard_novelty(self) -> float:
        return self.species_novelty

    @property
    def configuration_novelty(self) -> float:
        return self.invariant_feature_novelty

    def ordering_key(self, ordinal: int) -> tuple[float, ...]:
        return (
            self.combined_novelty,
            self.species_novelty,
            self.invariant_feature_novelty,
            self.residual_quality,
            -float(ordinal),
        )


class InvalidBasinArchive:
    """Frozen G1 admission with coordinate-free invariant diversity."""

    def __init__(
        self,
        configuration: ArchiveConfiguration | None = None,
        *,
        transform: PrefixWhitening | None = None,
    ) -> None:
        self.configuration = configuration or ArchiveConfiguration()
        self.transform = transform
        self._records: list[ArchiveRecord] = []
        self.rejected_nonroot = 0
        self.rejected_valid = 0
        self.rejected_untyped = 0
        self.merged = 0
        self.evicted = 0

    @property
    def records(self) -> tuple[ArchiveRecord, ...]:
        return tuple(self._records)

    def _eligible(self, descriptor: RuntimeDescriptor) -> bool:
        if descriptor.source_valid:
            self.rejected_valid += 1
            return False
        if not descriptor.finite or descriptor.residual_inf > self.configuration.root_tolerance:
            self.rejected_nonroot += 1
            return False
        if not descriptor.typed_margins or not failed_guard_species(descriptor):
            self.rejected_untyped += 1
            return False
        if self.transform is None:
            self.rejected_untyped += 1
            return False
        try:
            self.transform.feature(descriptor)
        except (ValueError, ArithmeticError, np.linalg.LinAlgError):
            self.rejected_untyped += 1
            return False
        return True

    def _distance(self, left: RuntimeDescriptor, right: RuntimeDescriptor) -> float:
        if self.transform is None:
            return math.inf
        return math.hypot(
            _species_distance(left, right), self.transform.distance(left, right)
        )

    def add(self, descriptor: RuntimeDescriptor) -> bool:
        if not self._eligible(descriptor):
            return False
        for record in self._records:
            if (
                failed_guard_species(record.descriptor) == failed_guard_species(descriptor)
                and self._distance(record.descriptor, descriptor)
                <= self.configuration.merge_tolerance
            ):
                record.visits += 1
                self.merged += 1
                if descriptor.residual_inf < record.descriptor.residual_inf:
                    record.descriptor = descriptor
                return True
        self._records.append(ArchiveRecord(descriptor=descriptor))
        if len(self._records) > self.configuration.maximum_entries:
            contributions = []
            for index, record in enumerate(self._records):
                nearest = min(
                    (
                        self._distance(record.descriptor, other.descriptor)
                        for other_index, other in enumerate(self._records)
                        if other_index != index
                    ),
                    default=math.inf,
                )
                contributions.append(
                    (nearest, -record.visits, -record.descriptor.residual_inf, index)
                )
            self._records.pop(min(contributions)[-1])
            self.evicted += 1
        return True

    def novelty_score(self, descriptor: RuntimeDescriptor) -> NoveltyScore:
        if self.transform is None or not descriptor.finite or not descriptor.typed_margins:
            return NoveltyScore(*([-math.inf] * 4))
        try:
            feature = self.transform.feature(descriptor)
        except (ValueError, ArithmeticError, np.linalg.LinAlgError):
            return NoveltyScore(*([-math.inf] * 4))
        if not self._records:
            return NoveltyScore(0.0, 0.0, 0.0, 0.0)
        species = min(_species_distance(descriptor, item.descriptor) for item in self._records)
        invariant = min(
            float(np.linalg.norm(feature - self.transform.feature(item.descriptor)))
            for item in self._records
        )
        combined = min(
            math.hypot(
                _species_distance(descriptor, item.descriptor),
                float(np.linalg.norm(feature - self.transform.feature(item.descriptor))),
            )
            for item in self._records
        )
        return NoveltyScore(
            combined,
            species,
            invariant,
            -math.log1p(descriptor.residual_inf),
        )


class OnlineNoveltyScheduler:
    """Keep 75% control ordinals in place; reorder only the 25% side class."""

    def __init__(
        self,
        *,
        points: Sequence[Sequence[float]],
        sources: Sequence[str],
        descriptors: Sequence[RuntimeDescriptor],
        archive: InvalidBasinArchive | None = None,
        configuration: ArchiveConfiguration | None = None,
    ) -> None:
        if not points or len(points) != len(sources) or len(points) != len(descriptors):
            raise ValueError("prefix points, sources, and descriptors must align")
        self.configuration = configuration or ArchiveConfiguration()
        self.points = tuple(tuple(float(value) for value in point) for point in points)
        self.sources = tuple(str(value) for value in sources)
        self.descriptors = tuple(descriptors)
        dimension = len(self.points[0])
        if dimension < 1 or any(len(point) != dimension for point in self.points):
            raise ValueError("prefix points must have one positive common dimension")
        if not all(math.isfinite(value) for point in self.points for value in point):
            raise ValueError("prefix points must be finite")
        if any(descriptor.point != point for descriptor, point in zip(self.descriptors, self.points, strict=True)):
            raise ValueError("descriptor coordinates must match prefix bytes")
        schema = tuple((item.kind, item.key) for item in self.descriptors[0].typed_margins)
        self._typed_guard_contract = bool(schema) and all(
            descriptor.finite
            and tuple((item.kind, item.key) for item in descriptor.typed_margins) == schema
            and len(descriptor.raw_residual) == len(self.descriptors[0].raw_residual)
            for descriptor in self.descriptors
        )
        self._source_contract = all(source == INSURANCE_SOURCE for source in self.sources)
        transform = None
        if self._typed_guard_contract and self._source_contract:
            try:
                transform = PrefixWhitening.fit(self.descriptors)
            except (ValueError, ArithmeticError, np.linalg.LinAlgError):
                self._typed_guard_contract = False
        self.archive = archive or InvalidBasinArchive(self.configuration, transform=transform)
        if archive is not None:
            supplied = archive.transform
            transform_matches_prefix = bool(
                transform is not None
                and supplied is not None
                and supplied.guard_schema == transform.guard_schema
                and supplied.guard_kinds == transform.guard_kinds
                and supplied.residual_count == transform.residual_count
                and np.array_equal(supplied.location, transform.location)
                and np.array_equal(supplied.scale, transform.scale)
                and np.array_equal(supplied.whitener, transform.whitener)
            )
            if archive.configuration != self.configuration or not transform_matches_prefix:
                self._typed_guard_contract = False
        self._typed_guard_schema = schema
        self._emitted: set[int] = set()
        self._launches: list[ScheduledLaunch] = []

    @property
    def insurance_contract_holds(self) -> bool:
        return self._source_contract

    @property
    def activation_contract_holds(self) -> bool:
        return self._source_contract and self._typed_guard_contract

    @property
    def launches(self) -> tuple[ScheduledLaunch, ...]:
        return tuple(self._launches)

    @staticmethod
    def _side_ordinal(index: int) -> bool:
        return index % 4 == 3

    def _adaptive_pool(self, launch: int) -> tuple[int, ...]:
        stop = min(len(self.points), launch + self.configuration.lookahead + 1)
        pool = tuple(
            index
            for index in range(stop)
            if index not in self._emitted and self._side_ordinal(index)
        )
        return pool or tuple(
            index
            for index in range(len(self.points))
            if index not in self._emitted and self._side_ordinal(index)
        )

    def next(self) -> ScheduledLaunch:
        launch = len(self._launches)
        if launch >= len(self.points):
            raise StopIteration
        protected = not self._side_ordinal(launch)
        if not self.activation_contract_holds or protected:
            ordinal = launch
        else:
            pool = self._adaptive_pool(launch)
            if not pool:
                raise RuntimeError("protected side pool lost permutation support")
            ordinal = max(
                pool,
                key=lambda index: self.archive.novelty_score(
                    self.descriptors[index]
                ).ordering_key(index),
            )
        if ordinal in self._emitted:
            raise RuntimeError("proposal emitted twice")
        self._emitted.add(ordinal)
        score = self.archive.novelty_score(self.descriptors[ordinal])
        result = ScheduledLaunch(
            launch=launch,
            ordinal=ordinal,
            source=self.sources[ordinal],
            point=self.points[ordinal],
            insurance=bool(protected and self.activation_contract_holds),
            score=score,
        )
        self._launches.append(result)
        return result

    def observe_endpoint(self, descriptor: RuntimeDescriptor) -> bool:
        schema = tuple((item.kind, item.key) for item in descriptor.typed_margins)
        if not descriptor.finite or schema != self._typed_guard_schema:
            self.archive.rejected_untyped += 1
            return False
        return self.archive.add(descriptor)

    def complete_order(self) -> tuple[int, ...]:
        while len(self._launches) < len(self.points):
            self.next()
        order = tuple(item.ordinal for item in self._launches)
        if sorted(order) != list(range(len(self.points))):
            raise RuntimeError("protected schedule is not a full permutation")
        return order


def configuration_manifest() -> Mapping[str, object]:
    payload = {
        "schema_version": SCHEMA,
        "reference_name": REFERENCE_NAME,
        "frozen_g1_candidate_sha256": OLD_CANDIDATE_SHA256,
        "archive_admission_changed": False,
        "absolute_coordinates_used_for_scoring": False,
        "novelty_features": [
            "typed failed-guard kind multiset",
            "prefix-whitened typed signed margins",
            "prefix-whitened absolute source residuals",
        ],
        "control_ordinal_rule": "ordinal_mod_4_ne_3",
        "control_ordinal_fraction": 0.75,
        "adaptive_side_rule": "ordinal_mod_4_eq_3",
        "adaptive_side_fraction": 0.25,
        "source_residual_or_local_solver_modified": False,
        "target_truth_case_family_or_outcome_inputs": False,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return {**payload, "configuration_sha256": hashlib.sha256(encoded).hexdigest()}


__all__ = [
    "ArchiveConfiguration",
    "INSURANCE_SOURCE",
    "InvalidBasinArchive",
    "NoveltyScore",
    "OnlineNoveltyScheduler",
    "PrefixWhitening",
    "RuntimeDescriptor",
    "ScheduledLaunch",
    "TypedMargin",
    "configuration_manifest",
    "failed_guard_species",
]
