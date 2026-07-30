"""Common-control adapter for the post-baseline result-union core."""

from __future__ import annotations

from dataclasses import replace
import hashlib
from pathlib import Path
from typing import Any

import candidate_v3


POLICY_ID = "post_common_control_result_union_v4"
COMMON_CONTROL_SNAPSHOT = "COMMON_CONTROL_RESULT.json"
EXPECTED_RESULT_UNION_CORE_SHA256 = (
    "48b51f82803c5b41490ad24206527e96be87bcab46d9b965369519357b0f99e7"
)
REPLAY_MIN_SECONDS = candidate_v3.REPLAY_MIN_SECONDS
SNAPSHOT_AND_UNION_RESERVE_SECONDS = (
    candidate_v3.SNAPSHOT_AND_UNION_RESERVE_SECONDS
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


if _sha256(Path(candidate_v3.__file__)) != EXPECTED_RESULT_UNION_CORE_SHA256:
    raise RuntimeError("post-baseline result-union core digest changed")


def snapshot_common_control_result(output: Path) -> str:
    """Retain exact bytes written by the completed common control."""

    output = output.resolve()
    payload = (output / "RESULT.json").read_bytes()
    snapshot = output / COMMON_CONTROL_SNAPSHOT
    candidate_v3._atomic_write_bytes(snapshot, payload)
    if snapshot.read_bytes() != payload:
        raise RuntimeError("common control RESULT snapshot is not byte-exact")
    return hashlib.sha256(payload).hexdigest()


class _CommonControlSideBase:
    """Delegate exact authority while making unknown targets rankable.

    Champion-v0 intentionally delays every provisional target, representing it
    as None. Side ranking therefore uses configuration/residual diversity only;
    a neutral zero is installed in copied, post-baseline candidates. This does
    not affect baseline execution or final descriptor authority.
    """

    def __init__(self, base: Any) -> None:
        self._base = base

    def __getattr__(self, name: str) -> Any:
        return getattr(self._base, name)

    def _fresh_replay_candidates(self, *args: Any, **kwargs: Any) -> tuple[Any, ...]:
        candidates = self._base._fresh_replay_candidates(*args, **kwargs)
        return tuple(
            replace(candidate, provisional_target=0.0)
            if candidate.provisional_target is None
            else candidate
            for candidate in candidates
        )


def extend_common_control_result(
    base: Any,
    *,
    source: Path,
    source_sha256: str,
    total_seconds: float,
    cpu: int,
    output: Path,
) -> dict[str, object]:
    """Run the hash-bound union core after common control has returned."""

    adapter = _CommonControlSideBase(base)
    original_policy = candidate_v3.POLICY_ID
    original_snapshot = candidate_v3.BASELINE_SNAPSHOT
    candidate_v3.POLICY_ID = POLICY_ID
    candidate_v3.BASELINE_SNAPSHOT = COMMON_CONTROL_SNAPSHOT
    try:
        outcome = candidate_v3.extend_frozen_result(
            adapter,
            source=source,
            source_sha256=source_sha256,
            total_seconds=total_seconds,
            cpu=cpu,
            output=output,
        )
        return outcome.to_dict()
    finally:
        candidate_v3.POLICY_ID = original_policy
        candidate_v3.BASELINE_SNAPSHOT = original_snapshot
