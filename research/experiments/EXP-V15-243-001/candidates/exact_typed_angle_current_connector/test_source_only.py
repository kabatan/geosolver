from __future__ import annotations

import json
from pathlib import Path

from audit_connector import BOUND_SHA256, BOUND_WORKER, audit
from source_activation import (
    LINE_DOMAIN,
    POINT_DOMAIN,
    aggregate_source_documents,
    classify_source_relation,
)


def relation(arity: int, *, unit: str = "radian", domain: str | None = None):
    expected = POINT_DOMAIN if arity == 3 else LINE_DOMAIN
    return {
        "op": "Equal",
        "left": {
            "op": "Angle",
            "args": [f"L{i}" for i in range(arity)],
            "unit": unit,
            "domain": domain or expected,
        },
        "right": {
            "op": "Angle",
            "args": [f"R{i}" for i in range(arity)],
            "unit": unit,
            "domain": domain or expected,
        },
    }


def test_static_activation_is_direct_and_typed_only():
    assert classify_source_relation(relation(3))
    assert classify_source_relation(relation(2))
    assert not classify_source_relation(relation(3, unit="degree"))
    assert not classify_source_relation(relation(3, domain="FULL_CIRCLE_[0,2PI]"))
    assert not classify_source_relation({**relation(3), "case_id": "forbidden"})


def test_aggregate_never_emits_source_identity(tmp_path: Path):
    result = aggregate_source_documents(
        [
            {"variables": [], "constraints": [relation(3)]},
            {"variables": ["x"], "nested": {"constraint": relation(2)}},
            {"variables": ["x"], "constraints": []},
        ]
    )
    assert result["documents_total"] == 3
    assert result["documents_with_direct_typed_angle_equality"] == 2
    assert result["direct_typed_angle_equality_relations"] == 2
    assert result["zero_dimensional_documents"] == 1
    assert result["authority_route_enabled"] is False
    encoded = json.dumps(result)
    assert "case_id" not in encoded
    assert "truth" not in encoded.lower() or result["truth_or_scorer_read"] is False


def test_current_control_has_no_thin_angle_or_qreflect_seam():
    result = audit(BOUND_WORKER)
    assert result["bound_worker_sha256"] == BOUND_SHA256
    assert result["typed_angle_connector_decision"].startswith("STOP_")
    assert result["qreflect_connector_decision"].startswith("STOP_")
    assert not result["additional_authority_implementable_with_thin_decorator"]
