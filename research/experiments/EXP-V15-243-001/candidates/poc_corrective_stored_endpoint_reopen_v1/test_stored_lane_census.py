from __future__ import annotations

from decimal import Decimal
import hashlib
import json
from types import SimpleNamespace

import stored_lane_census as census


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


class FakeCascade:
    @staticmethod
    def _validate_bridge(bridge, source_bytes):
        assert bridge["case_sha256"] == hashlib.sha256(source_bytes).hexdigest()
        return bridge["refinement"], bridge["owned_pslq"], bridge["case_sha256"], "private"

    @staticmethod
    def _sequence(value, label):
        assert isinstance(value, list)
        return value

    @staticmethod
    def _owned_by_index(owned):
        return {record["source_record_index"]: record for record in owned["records"]}

    @staticmethod
    def _adapt_proposal(proposal, owned, names):
        assert owned["source_record"] == proposal
        return (
            {
                "configuration_algebraic_proposals": [
                    {"status": "ALGEBRAIC_PROPOSAL"} for _ in names
                ]
            },
            {"descriptor": True},
            {},
        )


class FakeD1:
    D1_SHA256 = "d" * 64
    TURN_ADJACENT_PRECISION_GATE = Decimal("1e-100")

    @staticmethod
    def _load_cascade():
        return FakeCascade

    @staticmethod
    def classify_source(source_bytes):
        return SimpleNamespace(
            eligible=True,
            atoms=(
                SimpleNamespace(
                    coordinate_index=1,
                    atom_binding_sha256="a" * 64,
                ),
            ),
            semantic_projection_sha256="e" * 64,
        )

    @staticmethod
    def _decimal_difference(left, right):
        return abs(Decimal(str(left)) - Decimal(str(right)))


class FakeCandidate:
    D1_SHA256 = "d" * 64

    @staticmethod
    def _load_d1():
        return FakeD1


def fixture(tmp_path, *, complete=True):
    source = {
        "task": "solve",
        "variables": {"names": ["r", "t"]},
        "construction": [],
        "constraints": [],
        "guards": [],
        "answer": "r",
    }
    source_bytes = canonical(source)
    proposal = {
        "status": "INDEPENDENT_REFINEMENT_READY",
        "independent_precision_lanes": True,
        "numeric_gate_1e_100": True,
        "coordinates_768bit_minimum": ["2", "0.25"],
        "coordinates_1024bit_minimum": ["2", "0.25"],
        "answer_512bit_minimum": "2",
        "answer_768bit_minimum": "2",
        "answer_1024bit_minimum": "2",
        "source": {"endpoint_float64_sha256": "f" * 64},
    }
    if not complete:
        proposal.pop("coordinates_1024bit_minimum")
    source_sha = hashlib.sha256(source_bytes).hexdigest()
    bridge = {
        "schema_version": census.BRIDGE_SCHEMA,
        "case_sha256": source_sha,
        "refinement": {"proposals": [proposal]},
        "owned_pslq": {
            "records": [
                {
                    "source_record_index": 0,
                    "source_record": proposal,
                }
            ]
        },
    }
    input_dir = tmp_path / "inputs"
    bridge_dir = tmp_path / "artifacts" / "fresh-bridge"
    input_dir.mkdir(parents=True)
    bridge_dir.mkdir(parents=True)
    (input_dir / "source.json").write_bytes(source_bytes)
    (bridge_dir / "RESULT.json").write_bytes(canonical(bridge))
    return source_sha


def test_complete_pair_yields_aggregate_only_go(tmp_path):
    source_sha = fixture(tmp_path)
    result = census.census_root(tmp_path, candidate_module=FakeCandidate)
    assert result["status"] == "GO_PRIVATE_HOLD_GATE_NOT_EXECUTED"
    assert result["counts"]["stored_lane_complete"] == 1
    assert result["counts"]["atom_non_turn_ready"] == 1
    assert result["per_row_output_emitted"] is False
    assert result["corrective_exactification_executed"] is False
    serialized = json.dumps(result, sort_keys=True)
    assert source_sha not in serialized
    assert "source.json" not in serialized
    assert "case_id" not in serialized


def test_zero_complete_pair_stops_without_tuning(tmp_path):
    fixture(tmp_path, complete=False)
    result = census.census_root(tmp_path, candidate_module=FakeCandidate)
    assert result["status"] == "STOP_NO_COMPLETE_STORED_LANES"
    assert result["counts"].get("stored_lane_complete", 0) == 0
    assert result["complete_zero_stops_without_tuning"] is True


def test_validation_or_sealed_root_is_rejected(tmp_path):
    forbidden = tmp_path / "validation"
    forbidden.mkdir()
    try:
        census.census_root(forbidden, candidate_module=FakeCandidate)
    except census.CensusError:
        pass
    else:
        raise AssertionError("validation root unexpectedly admitted")
