"""Single policy packet shared by source-only candidate workers."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Mapping

import numpy as np

from prefix import Prefix, frozen_configuration as prefix_configuration
from prefix import generate_prefix
from runtime import source_bounds
from scaling import base_scales, frozen_configuration as scaling_configuration


SCHEMA = "geotarget.exp-real61-008.source-only-policy-packet/v1"


@dataclass(frozen=True)
class PolicyPacket:
    source_sha256: str
    seed: int
    points: tuple[np.ndarray, ...]
    local_origins: tuple[np.ndarray, ...]
    local_scales: tuple[np.ndarray, ...]
    sources: tuple[str, ...]
    scale_exponents: tuple[int, ...]
    prefix_sha256: str
    policy_digest: str


def policy_configuration() -> dict[str, object]:
    return {
        "schema_version": SCHEMA,
        "prefix": prefix_configuration(),
        "local_scaling": scaling_configuration(),
        "source_bytes_modified": False,
        "source_missing_bounds_remain_infinite": True,
        "non_source_bounds_or_envelope": False,
        "gauge_or_symmetry_reduction": False,
        "case_family_truth_target_count_routing": False,
    }


def _policy_digest() -> str:
    payload = json.dumps(
        policy_configuration(), sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def materialize_policy(
    document: dict[str, object],
    *,
    source_sha256: str,
    starts: int,
    seed: int,
) -> PolicyPacket:
    names = document.get("variables", {}).get("names")
    if not isinstance(names, list):
        raise ValueError("variables.names is missing")
    lower, upper = source_bounds(document, len(names))
    generated: Prefix = generate_prefix(lower, upper, count=starts, seed=seed)
    origins = tuple(point.copy() for point in generated.points)
    scales = tuple(base_scales(point) for point in generated.points)
    return PolicyPacket(
        source_sha256=str(source_sha256),
        seed=int(seed),
        points=tuple(point.copy() for point in generated.points),
        local_origins=origins,
        local_scales=scales,
        sources=generated.sources,
        scale_exponents=generated.scale_exponents,
        prefix_sha256=generated.sha256,
        policy_digest=_policy_digest(),
    )


def packet_record(packet: PolicyPacket) -> Mapping[str, object]:
    return {
        "schema_version": SCHEMA,
        "source_sha256": packet.source_sha256,
        "seed": packet.seed,
        "starts": len(packet.points),
        "prefix_sha256": packet.prefix_sha256,
        "policy_digest": packet.policy_digest,
        "sources": list(packet.sources),
        "scale_exponents": list(packet.scale_exponents),
        "local_origins_equal_starts": all(
            origin.tobytes() == point.tobytes()
            for origin, point in zip(packet.local_origins, packet.points, strict=True)
        ),
        "local_scale_rule": "max(1,abs(start_j))",
        "configuration": policy_configuration(),
    }


__all__ = [
    "PolicyPacket",
    "materialize_policy",
    "packet_record",
    "policy_configuration",
]
