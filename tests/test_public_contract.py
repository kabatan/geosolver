from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from jsonschema import Draft202012Validator
from pydantic import ValidationError

from geotarget.models import SolveOptions, SolveResult
from geotarget.qualification import policy, report_summary_sha256, validate_policy
from geotarget.resources import AUTO_MEMORY_RESERVE_BYTES, BYTES_PER_WORKER, ResourceError, reserve


def test_qualified_optimized_engine_is_the_atomic_default() -> None:
    options = SolveOptions()

    assert options.engine == "optimized"
    assert options.run_mode == "adaptive"
    assert options.max_time_seconds == 900
    assert options.cores == "auto"
    assert options.seed == 0
    assert options.model_dump() == {
        "engine": "optimized",
        "run_mode": "adaptive",
        "max_time_seconds": 900.0,
        "cores": "auto",
        "seed": 0,
    }
    qualification = policy()
    assert qualification["promotion_status"] == "qualified"
    assert qualification["correctness_gate_passed"] is True
    assert qualification["performance_gate_passed"] is True
    assert qualification["report_summary"]["all_gates_passed"] is True


def test_qualification_policy_returns_an_independent_snapshot() -> None:
    first = policy()
    first["promotion_status"] = "reference"

    assert policy()["promotion_status"] == "qualified"


def test_promoted_policy_requires_timestamped_checksum_evidence() -> None:
    summary = {
        "schema_version": "geotarget.optimized-qualification-summary/v1",
        "exact_set_cases_matched": 145,
        "false_exact_descriptors": 0,
        "performance_regression_percent": 0.0,
    }
    promoted = {
        "promotion_status": "qualified",
        "correctness_gate_passed": True,
        "performance_gate_passed": True,
        "default_engine": "optimized",
        "qualified_at": "2026-07-29T12:00:00+09:00",
        "report_sha256": report_summary_sha256(summary),
        "report_summary": summary,
    }
    assert validate_policy(promoted) is promoted
    with pytest.raises(RuntimeError, match="checksum"):
        validate_policy({**promoted, "report_sha256": None})
    with pytest.raises(RuntimeError, match="timestamp"):
        validate_policy({**promoted, "qualified_at": "2026-07-29T12:00:00"})
    with pytest.raises(RuntimeError, match="does not match"):
        validate_policy(
            {**promoted, "report_summary": {**summary, "false_exact_descriptors": 1}}
        )
    with pytest.raises(RuntimeError, match="summary is missing"):
        validate_policy({**promoted, "report_summary": None})


def test_optimized_engine_can_still_be_selected_explicitly() -> None:
    options = SolveOptions(engine="optimized")
    assert options.engine == "optimized"


@pytest.mark.parametrize(
    "override",
    [
        {"run_mode": "adaptive"},
        {"max_time_seconds": 300},
        {"cores": "auto"},
        {"cores": 2},
    ],
)
def test_reference_contract_rejects_incoherent_resource_tuple(override) -> None:
    with pytest.raises(ValidationError, match="reference requires"):
        SolveOptions(engine="reference", **override)


def test_legacy_time_limit_maps_to_fixed_time_without_serializing_alias() -> None:
    options = SolveOptions.model_validate(
        {"engine": "optimized", "time_limit_seconds": 300, "cores": 2}
    )

    assert options.run_mode == "fixed_time"
    assert options.max_time_seconds == 300
    assert options.time_limit_seconds == 300
    assert options.compatibility_time_limit_used is True
    assert "time_limit_seconds" not in options.model_dump()


@pytest.mark.parametrize("value", [179, 901, float("inf")])
def test_max_time_is_bounded(value: float) -> None:
    with pytest.raises(ValidationError):
        SolveOptions(max_time_seconds=value)


def test_solve_result_new_metadata_is_backward_compatible() -> None:
    result = SolveResult.model_validate(
        {
            "status": "no_answer_found",
            "engine_id": "engine",
            "engine_hash": "hash",
            "problem_sha256": "problem",
            "requested_resources": {
                "time_limit_seconds": 180,
                "cores": 1,
                "seed": 0,
            },
            "used_resources": {"time_limit_seconds": 180, "cores": 1, "seed": 0},
            "elapsed_seconds": 1,
            "work_checkpoint": {},
        }
    )

    assert result.engine_variant == "reference"
    assert result.termination_reason is None
    assert result.phase_metadata.completed == []
    assert result.work_metadata.completed_items == 0
    assert result.cache_metadata.hits == 0


def test_solve_result_json_schema_tracks_model_and_validates_serialization() -> None:
    schema_path = Path(__file__).parents[1] / "schemas/solve-result.schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    model_schema = SolveResult.model_json_schema()

    Draft202012Validator.check_schema(schema)
    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    assert schema["$id"] == "https://geotarget.local/schemas/solve-result.schema.json"
    assert set(schema["properties"]) == set(model_schema["properties"])
    assert set(schema["required"]) == set(model_schema["required"])

    result = SolveResult.model_validate(
        {
            "status": "answers_found_completeness_unknown",
            "engine_id": "engine",
            "engine_hash": "hash",
            "problem_sha256": "problem",
            "requested_resources": {
                "time_limit_seconds": 300,
                "max_time_seconds": 300,
                "cores": 2,
                "seed": 0,
            },
            "used_resources": {
                "time_limit_seconds": 300,
                "max_time_seconds": 300,
                "cores": 2,
                "seed": 0,
            },
            "elapsed_seconds": 12.5,
            "work_checkpoint": {
                "completed_start_ordinals": [0, 1],
                "termination_reason": "initial_work_answered",
            },
            "answers": [
                {
                    "minimal_polynomial_high_to_low": [1, "-2"],
                    "selected_real_root_index": 0,
                    "isolating_interval": ["1", "2"],
                    "decimal": "1.414",
                }
            ],
            "engine_variant": "optimized",
            "termination_reason": "initial_work_answered",
        }
    )
    Draft202012Validator(schema).validate(result.model_dump(mode="json"))


def test_auto_core_selection_reserves_cpu_and_memory(monkeypatch) -> None:
    monkeypatch.setattr("geotarget.resources.physical_cpu_ids", lambda: tuple(range(8)))
    monkeypatch.setattr(
        "geotarget.resources.psutil.virtual_memory",
        lambda: SimpleNamespace(
            available=AUTO_MEMORY_RESERVE_BYTES + 3 * BYTES_PER_WORKER
        ),
    )

    reservation = reserve(SolveOptions(engine="optimized", cores="auto"))

    assert reservation.physical_cpus == (0, 1, 2)


def test_auto_core_selection_fails_if_reserves_cannot_be_kept(monkeypatch) -> None:
    monkeypatch.setattr("geotarget.resources.physical_cpu_ids", lambda: (0,))
    monkeypatch.setattr(
        "geotarget.resources.psutil.virtual_memory",
        lambda: SimpleNamespace(available=AUTO_MEMORY_RESERVE_BYTES + BYTES_PER_WORKER),
    )

    with pytest.raises(ResourceError, match="reserve one physical core and 4 GiB"):
        reserve(SolveOptions(engine="optimized", cores="auto"))
