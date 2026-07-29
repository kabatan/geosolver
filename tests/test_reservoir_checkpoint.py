from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import pytest

from geotarget.reservoir_checkpoint import (
    ReservoirCheckpointCorrupt,
    load_checkpoint,
    search_binding,
    write_checkpoint,
)


@dataclass(frozen=True)
class Candidate:
    endpoint: tuple[float, ...]
    endpoint_sha256: str
    residual_inf: float
    provisional_target: float | None = None
    cluster_ordinal: int = 0
    cluster_rank: int = 0
    discovery_ordinal: int = 0
    admission_role: str = "RAW_SAFE"
    record_id: str = ""
    bucket_id: str = ""
    bucket_kind: str = ""
    aging_wave: int = 0
    semantic_verified: bool = True


class Reservoir(tuple):
    def __new__(cls, verified, backlog=()):
        result = super().__new__(cls, verified)
        result.deadline_backlog = tuple(backlog)
        return result


def _search() -> dict:
    return {
        "arm": "frozen",
        "seed": 0,
        "endpoints": [{"lane": 0, "point": [1.25, -0.0]}],
        "literal_prefix": {
            "full_prefix_sha256": "a" * 64,
            "selected_shard_proposal_sha256": ["b" * 64],
        },
        "optimized_parallel_search": {"completed_start_ordinals": [0]},
        "work": {"lanes_started": 1, "callbacks": 600},
        "budget": {"starts": 256, "callbacks_per_start": 600},
    }


def _reservoir() -> Reservoir:
    return Reservoir(
        (
            Candidate(
                (1.25, -0.0), "1" * 64, 1e-9, None, 4, 1, 8,
                "TARGET_UNAVAILABLE_RAW_SAFE", "8:abc", "safe", "SAFE", 2, True,
            ),
        ),
        (
            Candidate(
                (2.5, 3.5), "2" * 64, 1e-4, None, 5, 0, 9,
                "DEADLINE_BACKLOG", "9:def", "backlog", "DEADLINE", 3, False,
            ),
        ),
    )


def test_checkpoint_round_trips_every_candidate_field_and_stable_order(tmp_path: Path) -> None:
    binding = search_binding("f" * 64, _search())
    path = tmp_path / "reservoir.json"
    original = _reservoir()
    write_checkpoint(path, binding=binding, reservoir=original)

    restored = load_checkpoint(
        path,
        expected_binding=binding,
        candidate_type=Candidate,
        reservoir_type=Reservoir,
    )

    assert tuple(restored or ()) == tuple(original)
    assert tuple(getattr(restored, "deadline_backlog", ())) == original.deadline_backlog
    assert json.loads(path.read_text())["stable_order"] == "verified_then_deadline_backlog"


def test_binding_change_falls_back_to_full_replay(tmp_path: Path) -> None:
    path = tmp_path / "reservoir.json"
    binding = search_binding("f" * 64, _search())
    write_checkpoint(path, binding=binding, reservoir=_reservoir())
    changed = {**binding, "source_sha256": "e" * 64}

    assert load_checkpoint(
        path,
        expected_binding=changed,
        candidate_type=Candidate,
        reservoir_type=Reservoir,
    ) is None


def test_schema_change_falls_back_to_full_replay(tmp_path: Path) -> None:
    path = tmp_path / "reservoir.json"
    path.write_text('{"schema_version":"future"}\n', encoding="utf-8")
    assert load_checkpoint(
        path,
        expected_binding=search_binding("f" * 64, _search()),
        candidate_type=Candidate,
        reservoir_type=Reservoir,
    ) is None


@pytest.mark.parametrize("mutation", ["truncate", "tamper"])
def test_partial_or_tampered_checkpoint_fails_closed(tmp_path: Path, mutation: str) -> None:
    path = tmp_path / "reservoir.json"
    binding = search_binding("f" * 64, _search())
    write_checkpoint(path, binding=binding, reservoir=_reservoir())
    if mutation == "truncate":
        path.write_text(path.read_text()[:30], encoding="utf-8")
    else:
        document = json.loads(path.read_text())
        document["verified"][0]["record_id"] = "tampered"
        path.write_text(json.dumps(document), encoding="utf-8")

    with pytest.raises(ReservoirCheckpointCorrupt):
        load_checkpoint(
            path,
            expected_binding=binding,
            candidate_type=Candidate,
            reservoir_type=Reservoir,
        )
