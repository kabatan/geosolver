"""Threshold-free guard-relative lower-star merge-tree portal proposal."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
from typing import Any, Mapping, Sequence

import numpy as np


CANDIDATE = "GUARD_RELATIVE_MERGE_TREE_PORTAL_V1"


class GateUnknown(ValueError):
    pass


@dataclass(frozen=True)
class Observation:
    point: tuple[float, ...]
    residual: float
    guard_state: str
    endpoint: bool


@dataclass(frozen=True)
class Pool:
    anonymous_source_hash: str
    dimension: int
    scale: tuple[float, ...]
    observations: tuple[Observation, ...]


@dataclass(frozen=True)
class PortalProposal:
    point: tuple[float, ...]
    midpoint_probe: tuple[float, ...]
    merge_residual: float
    source_vertex_index: int
    authority_pass: bool = False
    canonical_replay_required: bool = True


def parse_pool(value: Mapping[str, Any]) -> Pool:
    source_hash = value.get("anonymous_source_hash")
    dimension = value.get("dimension")
    scale = value.get("scale")
    raw = value.get("observations")
    if (
        not isinstance(source_hash, str)
        or len(source_hash) != 64
        or any(character not in "0123456789abcdef" for character in source_hash)
        or not isinstance(dimension, int)
        or isinstance(dimension, bool)
        or dimension < 1
        or not isinstance(scale, list)
        or len(scale) != dimension
        or not isinstance(raw, list)
        or len(raw) < 2
        or value.get("typed_guard_complete") is not True
        or value.get("guard_count") != value.get("typed_guard_count")
        or not isinstance(value.get("guard_count"), int)
        or value.get("guard_count") < 1
    ):
        raise GateUnknown("INCOMPLETE_TYPED_POOL")
    scale_values = tuple(float(item) for item in scale)
    if any(not math.isfinite(item) or item <= 0.0 for item in scale_values):
        raise GateUnknown("INVALID_DIMENSIONLESS_SCALE")
    observations = []
    for item in raw:
        if not isinstance(item, Mapping) or item.get("charged") is not True:
            raise GateUnknown("UNCHARGED_OR_MALFORMED_OBSERVATION")
        point = item.get("point")
        residual = item.get("residual")
        state = item.get("guard_state")
        endpoint = item.get("endpoint")
        if (
            not isinstance(point, list)
            or len(point) != dimension
            or not isinstance(residual, (int, float))
            or isinstance(residual, bool)
            or state not in {"INTERIOR", "INVALID"}
            or not isinstance(endpoint, bool)
        ):
            raise GateUnknown("MALFORMED_TYPED_OBSERVATION")
        point_values = tuple(float(coordinate) for coordinate in point)
        residual_value = float(residual)
        if not all(math.isfinite(coordinate) for coordinate in point_values) or not math.isfinite(residual_value) or residual_value < 0.0:
            raise GateUnknown("NONFINITE_OBSERVATION")
        observations.append(Observation(point_values, residual_value, state, endpoint))
    return Pool(source_hash, dimension, scale_values, tuple(observations))


def mutual_knn_edges(pool: Pool) -> tuple[tuple[int, int], ...]:
    points = np.asarray([item.point for item in pool.observations], dtype=float)
    scaled = points / np.asarray(pool.scale, dtype=float)
    count = len(points)
    k = min(2 * pool.dimension + 1, count - 1)
    neighbors: list[set[int]] = []
    for index in range(count):
        distances = np.sum((scaled - scaled[index]) ** 2, axis=1)
        if np.any(distances[np.arange(count) != index] == 0.0):
            raise GateUnknown("DUPLICATE_DIMENSIONLESS_VERTEX")
        order = [item for item in np.argsort(distances, kind="stable") if item != index]
        if k < count - 1 and distances[order[k - 1]] == distances[order[k]]:
            raise GateUnknown("KNN_CUTOFF_TIE")
        neighbors.append(set(int(item) for item in order[:k]))
    return tuple(
        (first, second)
        for first in range(count)
        for second in range(first + 1, count)
        if second in neighbors[first] and first in neighbors[second]
    )


def low_residual_invalid_minima(pool: Pool, edges: Sequence[tuple[int, int]]) -> tuple[int, ...]:
    adjacency = [set() for _ in pool.observations]
    for first, second in edges:
        adjacency[first].add(second)
        adjacency[second].add(first)
    result = []
    for index, observation in enumerate(pool.observations):
        if observation.guard_state != "INVALID" or not observation.endpoint or not adjacency[index]:
            continue
        if all(observation.residual < pool.observations[other].residual for other in adjacency[index]):
            result.append(index)
    return tuple(result)


def dynamic_gate(raw_pools: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    try:
        pools = tuple(parse_pool(item) for item in raw_pools)
        if not pools:
            raise GateUnknown("NO_POOLS")
        minima_by_pool = []
        hashes = set()
        for pool in pools:
            if sum(item.guard_state == "INTERIOR" for item in pool.observations) < 8:
                raise GateUnknown("INTERIOR_OBSERVATIONS_BELOW_EIGHT")
            edges = mutual_knn_edges(pool)
            minima = low_residual_invalid_minima(pool, edges)
            minima_by_pool.append(len(minima))
            if minima:
                hashes.add(pool.anonymous_source_hash)
        total = sum(minima_by_pool)
        passed = total >= 3 and len(hashes) >= 2
        payload = {
            "candidate": CANDIDATE,
            "decision": "DYNAMIC_GATE_PASS" if passed else "HOLD_DYNAMIC_RECURRENCE",
            "gate_pass": passed,
            "pool_count": len(pools),
            "typed_guard_complete_pool_count": len(pools),
            "pools_with_at_least_8_interior_observations": len(pools),
            "low_residual_invalid_endpoint_count": total,
            "anonymous_hash_count_with_low_invalid_endpoint": len(hashes),
            "required_low_residual_invalid_endpoints": 3,
            "required_anonymous_hashes": 2,
            "threshold_or_persistence_parameter_used": False,
            "individual_observations_emitted": False,
        }
    except (GateUnknown, KeyError, TypeError, ValueError, OverflowError) as error:
        payload = {
            "candidate": CANDIDATE,
            "decision": "UNKNOWN_FULL_BASELINE_FALLBACK",
            "gate_pass": False,
            "unknown_reason": str(error),
            "threshold_or_persistence_parameter_used": False,
            "individual_observations_emitted": False,
        }
    payload["anonymous_gate_signature_sha256"] = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return payload


class _UnionFind:
    def __init__(self, count: int, minima: set[int], interiors: set[int]) -> None:
        self.parent = list(range(count))
        self.pending = [{index} if index in minima else set() for index in range(count)]
        self.interiors = [{index} if index in interiors else set() for index in range(count)]

    def find(self, index: int) -> int:
        while self.parent[index] != index:
            self.parent[index] = self.parent[self.parent[index]]
            index = self.parent[index]
        return index

    def merge(self, first: int, second: int) -> int:
        first, second = self.find(first), self.find(second)
        if first == second:
            return first
        if first > second:
            first, second = second, first
        self.parent[second] = first
        self.pending[first] |= self.pending[second]
        self.interiors[first] |= self.interiors[second]
        return first


def _nearest_interior(pool: Pool, candidates: set[int], crossing: int) -> int:
    point = np.asarray(pool.observations[crossing].point) / np.asarray(pool.scale)
    return min(
        candidates,
        key=lambda index: (
            float(np.sum((np.asarray(pool.observations[index].point) / np.asarray(pool.scale) - point) ** 2)),
            pool.observations[index].residual,
            tuple(np.asarray(pool.observations[index].point) / np.asarray(pool.scale)),
        ),
    )


def select_portal(raw_pool: Mapping[str, Any], gate: Mapping[str, Any]) -> PortalProposal | None:
    if gate.get("gate_pass") is not True or gate.get("decision") != "DYNAMIC_GATE_PASS":
        return None
    pool = parse_pool(raw_pool)
    edges = mutual_knn_edges(pool)
    minima = set(low_residual_invalid_minima(pool, edges))
    if not minima:
        return None
    residuals = [item.residual for item in pool.observations]
    if len(set(residuals)) != len(residuals):
        raise GateUnknown("LOWER_STAR_RESIDUAL_TIE")
    adjacency = [set() for _ in pool.observations]
    for first, second in edges:
        adjacency[first].add(second)
        adjacency[second].add(first)
    interiors = {index for index, item in enumerate(pool.observations) if item.guard_state == "INTERIOR"}
    forest = _UnionFind(len(pool.observations), minima, interiors)
    active: set[int] = set()
    candidates: list[tuple[float, int, int, int]] = []
    for vertex in sorted(range(len(pool.observations)), key=lambda index: residuals[index]):
        active.add(vertex)
        for neighbor in sorted(
            adjacency[vertex] & active,
            key=lambda index: (
                float(np.sum(
                    (
                        np.asarray(pool.observations[index].point) / np.asarray(pool.scale)
                        - np.asarray(pool.observations[vertex].point) / np.asarray(pool.scale)
                    ) ** 2
                )),
                pool.observations[index].residual,
                tuple(np.asarray(pool.observations[index].point) / np.asarray(pool.scale)),
            ),
        ):
            left, right = forest.find(vertex), forest.find(neighbor)
            if left == right:
                continue
            for pending_root, interior_root, crossing in ((left, right, vertex), (right, left, neighbor)):
                if forest.pending[pending_root] and forest.interiors[interior_root]:
                    portal = _nearest_interior(pool, forest.interiors[interior_root], crossing)
                    for seed in sorted(forest.pending[pending_root]):
                        candidates.append((residuals[vertex], seed, crossing, portal))
                    forest.pending[pending_root].clear()
            forest.merge(left, right)
    if not candidates:
        return None
    merge_residual, seed, _crossing, portal = min(
        candidates,
        key=lambda item: (
            item[0],
            pool.observations[item[1]].residual,
            tuple(np.asarray(pool.observations[item[1]].point) / np.asarray(pool.scale)),
            pool.observations[item[3]].residual,
            tuple(np.asarray(pool.observations[item[3]].point) / np.asarray(pool.scale)),
        ),
    )
    # The probe is on the segment from the threshold-free invalid minimum to
    # the first existing interior portal, not an order-dependent graph edge.
    source_point = np.asarray(pool.observations[seed].point, dtype=float)
    portal_point = np.asarray(pool.observations[portal].point, dtype=float)
    return PortalProposal(
        tuple(float(value) for value in portal_point),
        tuple(float(value) for value in 0.5 * (source_point + portal_point)),
        float(merge_residual),
        int(portal),
    )


def partition_start_ordinals(count: int, gate: Mapping[str, Any]) -> tuple[tuple[int, ...], tuple[int, ...]]:
    if not isinstance(count, int) or isinstance(count, bool) or count < 0:
        raise ValueError("start count must be nonnegative")
    if gate.get("gate_pass") is not True:
        return tuple(range(count)), ()
    side = tuple(index for index in range(count) if index % 4 == 3)
    side_set = set(side)
    return tuple(index for index in range(count) if index not in side_set), side


def callback_allocation(total: int, *, portal_available: bool) -> dict[str, int]:
    if not isinstance(total, int) or isinstance(total, bool) or total < 0:
        raise ValueError("callback total must be nonnegative")
    side = total // 4 if portal_available else 0
    midpoint = 1 if side >= 2 else 0
    return {
        "baseline_callbacks": total - side,
        "side_callbacks": side,
        "midpoint_evaluation_callbacks": midpoint,
        "portal_local_callbacks": side - midpoint,
    }


def proposal_disposition(proposal: object) -> str:
    if not isinstance(proposal, PortalProposal):
        return "FULL_BASELINE_FALLBACK"
    if proposal.authority_pass or not proposal.canonical_replay_required:
        return "FULL_BASELINE_FALLBACK"
    return "SEND_TO_CANONICAL_LOCAL_AND_REPLAY"
