from __future__ import annotations

import json
from pathlib import Path
import sys


HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from formulation_audit import (  # noqa: E402
    audit_directory,
    expression_taxonomy,
    project_formulation,
    static_decision,
)


def _payload(**changes: object) -> dict[str, object]:
    document: dict[str, object] = {
        "id": "opaque-identity",
        "task": "solve",
        "variables": {"names": ["x"]},
        "bounds": [[1.0, 2.0]],
        "construction": [],
        "constraints": [{"def": "x**2", "value": 2.0}],
        "guards": [],
        "answer": "x",
    }
    document.update(changes)
    return document


def test_projection_never_decodes_identity_truth_gold_answer_or_scorer_values() -> None:
    sentinel = "VALUE-MUST-NOT-BE-DESERIALIZED"
    payload = json.dumps(
        {
            **_payload(),
            "id": sentinel,
            "answer": sentinel,
            "truth": {"secret": sentinel},
            "gold": [sentinel],
            "scorer": {"module": sentinel},
            "unknown": {"nested": sentinel},
        },
        separators=(",", ":"),
    ).encode()
    decoded_slices: list[bytes] = []

    def decoder(raw: bytes):
        assert sentinel.encode() not in raw
        decoded_slices.append(raw)
        return json.loads(raw)

    projected = project_formulation(payload, decoder=decoder)
    assert projected["task"] == "solve"
    assert projected["variables"] == {"names": ["x"]}
    assert all(key not in projected for key in ("id", "answer", "truth", "gold", "scorer"))
    assert decoded_slices


def test_static_gate_accepts_only_complete_bounded_smooth_square_formulation() -> None:
    accepted = static_decision(project_formulation(json.dumps(_payload()).encode()))
    guarded = static_decision(
        project_formulation(json.dumps(_payload(guards=["x > 1"])).encode())
    )
    unbounded = static_decision(
        project_formulation(json.dumps(_payload(bounds=None)).encode())
    )
    assert accepted.accepted
    assert accepted.reason == "applicable"
    assert guarded.reason == "strict-guard-interior-not-proved"
    assert unbounded.reason == "explicit-finite-bounds-unavailable"


def test_lazy_cse_translation_ignores_unused_unsupported_construction() -> None:
    projected = project_formulation(
        json.dumps(
            _payload(
                construction=[
                    {"name": "square", "expr": "x*x"},
                    {"name": "unused", "expr": "sin(x)"},
                ],
                constraints=[{"def": "square", "value": 2.0}],
            )
        ).encode()
    )
    assert static_decision(projected).accepted


def test_expression_taxonomy_is_aggregate_category_only() -> None:
    document = project_formulation(
        json.dumps(
            _payload(
                construction=[{"name": "p", "expr": "Point(x, sin(x))"}],
                constraints=[{"def": "abs(x) + x/2", "value": 0}],
                guards=["x > 0"],
            )
        ).encode()
    )
    occurrences, exposures, nodes = expression_taxonomy(document)
    assert nodes > 0
    assert occurrences["geometry-or-opaque-call"] == 1
    assert occurrences["transcendental-call"] == 1
    assert occurrences["nonsmooth-call"] == 1
    assert occurrences["branch-or-comparison"] == 1
    assert all("Point" not in category and "sin" not in category for category in exposures)


def test_directory_audit_is_aggregate_and_filename_order_independent(tmp_path: Path) -> None:
    left, right = tmp_path / "left", tmp_path / "right"
    left.mkdir()
    right.mkdir()
    documents = (
        _payload(id="first-hidden"),
        _payload(
            id="second-hidden",
            variables={"names": ["x", "y", "z"]},
            bounds=[[-1, 1], [-1, 1], [-1, 1]],
            constraints=["x", "y", "z"],
        ),
    )
    for index, document in enumerate(documents):
        raw = json.dumps(document, sort_keys=True, separators=(",", ":")).encode()
        (left / f"private-{index}.json").write_bytes(raw)
        (right / f"renamed-{1-index}.json").write_bytes(raw)
    first = audit_directory(left, expected_count=2)
    second = audit_directory(right, expected_count=2)
    assert first == second
    assert first["activation"]["applicable"] == 1
    assert first["activation"]["rejection_taxonomy"] == {"dimension-outside-cap": 1}
    assert first["scope"]["individual_case_records_emitted"] == 0
    rendered = json.dumps(first, sort_keys=True)
    assert "first-hidden" not in rendered
    assert "second-hidden" not in rendered
    assert "rows" not in first and "cases" not in first
