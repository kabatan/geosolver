from __future__ import annotations

from hashlib import sha256
import json
from types import SimpleNamespace

import stored_endpoint_adapter as candidate


ENDPOINT_SHA = "a" * 64
SOURCE = b'{"task":"solve","variables":{"names":["r","t"]},"answer":"0"}'
BRIDGE = json.dumps({"private": "bridge"}).encode()


def terminal():
    return {
        "endpoint_float64_sha256": ENDPOINT_SHA,
        "status": "EXACT_COORDINATE_REJECTED",
        "authority_pass": False,
        "descriptor": None,
        "exact_coordinate_fallback": {
            "status": "NO_EXACT_DESCRIPTOR",
            "authority_pass": False,
            "allocated_seconds": 12.0,
            "result_sha256": "b" * 64,
            "truth_used": False,
            "target_set_completeness_claim": False,
            "process": {
                "classification": "SUCCESS",
                "accepted_output": True,
                "returncode": 0,
                "timeout": False,
                "rss_cap_exceeded": False,
                "rss_monitor_failed": False,
                "output_cap_exceeded": False,
                "descendant_leak": False,
            },
        },
    }


class FakeCascade:
    proposal = {
        "source": {"endpoint_float64_sha256": ENDPOINT_SHA},
        "independent_precision_lanes": True,
        "coordinates_768bit_minimum": ["2", "0.25"],
        "coordinates_1024bit_minimum": ["2", "0.25"],
    }

    @staticmethod
    def _validate_bridge(bridge, source_bytes):
        assert bridge == {"private": "bridge"}
        return {"proposals": [FakeCascade.proposal]}, {"records": []}, sha256(source_bytes).hexdigest(), "opaque"

    @staticmethod
    def _sequence(value, label):
        return value

    @staticmethod
    def _owned_by_index(value):
        return {0: {"owned": True}}

    @staticmethod
    def _mapping(value, label):
        assert isinstance(value, dict)
        return value

    @staticmethod
    def _adapt_proposal(proposal, owned, names):
        assert proposal is FakeCascade.proposal
        assert owned == {"owned": True}
        assert names == ["r", "t"]
        return {"adapted": True}, {"descriptor": True}, {}


class FakeD1:
    atom = SimpleNamespace(coordinate_index=1, atom_binding_sha256="c" * 64)

    @staticmethod
    def verify_frozen_components():
        return {}

    @staticmethod
    def classify_source(source_bytes):
        return SimpleNamespace(eligible=True, atoms=(FakeD1.atom,))

    @staticmethod
    def _load_cascade():
        return FakeCascade

    @staticmethod
    def _validate_terminal_result(result):
        assert result.status == "VERIFIED"


def test_clean_stored_endpoint_join_is_applicable(monkeypatch):
    monkeypatch.setattr(candidate, "_load_d1", lambda: FakeD1)
    result = candidate.inspect_applicability(
        source_bytes=SOURCE,
        bridge_payload=BRIDGE,
        exact_outer_terminal=terminal(),
        proposal_index=0,
        atom_ordinal=0,
        endpoint_float64_sha256=ENDPOINT_SHA,
    )
    assert result.current_exact_outer_exhausted is True
    assert result.independent_coordinate_lanes is True
    assert result.authority_pass is False
    assert result.completeness_claimed is False


def test_verified_terminal_is_private_hold_and_failures_preserve_baseline(monkeypatch):
    monkeypatch.setattr(candidate, "_load_d1", lambda: FakeD1)
    baseline = object()

    def point(**arguments):
        assert arguments["atom"] is FakeD1.atom
        return SimpleNamespace(
            status="VERIFIED",
            exact_v2_record={"verified": True},
        )

    held = candidate.run_private_hold_or_baseline(
        source_bytes=SOURCE,
        bridge_payload=BRIDGE,
        exact_outer_terminal=terminal(),
        proposal_index=0,
        atom_ordinal=0,
        endpoint_float64_sha256=ENDPOINT_SHA,
        untouched_baseline=baseline,
        point_runner=point,
    )
    assert isinstance(held, candidate.CandidateHold)
    assert held.untouched_baseline is baseline
    assert held.authority_pass is False
    assert held.target_release is False

    bad = terminal()
    bad["exact_coordinate_fallback"]["status"] = "LOCK_BUSY_DEFERRED"
    fallback = candidate.run_private_hold_or_baseline(
        source_bytes=SOURCE,
        bridge_payload=BRIDGE,
        exact_outer_terminal=bad,
        proposal_index=0,
        atom_ordinal=0,
        endpoint_float64_sha256=ENDPOINT_SHA,
        untouched_baseline=baseline,
        point_runner=point,
    )
    assert fallback is baseline


def test_truth_endpoint_mismatch_and_not_run_fail_closed(monkeypatch):
    monkeypatch.setattr(candidate, "_load_d1", lambda: FakeD1)
    crossed = terminal()
    crossed["truth"] = [1]
    for value in (crossed, {**terminal(), "endpoint_float64_sha256": "d" * 64}):
        try:
            candidate.inspect_applicability(
                source_bytes=SOURCE,
                bridge_payload=BRIDGE,
                exact_outer_terminal=value,
                proposal_index=0,
                atom_ordinal=0,
                endpoint_float64_sha256=ENDPOINT_SHA,
            )
        except candidate.StoredEndpointRejected:
            pass
        else:
            raise AssertionError("unsafe terminal unexpectedly joined")
