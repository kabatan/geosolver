import pytest

from qwen.study_run import forecast, validate_config


def contract():
    config = {
        "route": "fp16_native",
        "prompts_per_round": 4,
        "samples": 4,
        "rounds": 37,
        "max_seqs": 4,
        "max_completion": 32512,
        "kv_cache_dtype": "auto",
        "lr": 1e-6,
        "evaluation_samples": {"numeric": 2, "proof": 4},
        "evaluation_reserve_hours": 8,
        "minimum_mixed_groups_after_five": 4,
        "planning": {
            "training_tokens_per_second": 220,
            "update_seconds_per_round": 300,
            "process_overhead_seconds_per_round": 60,
            "safety_factor": 1.2,
        },
    }
    budget = {
        "limit_seconds": 144000,
        "preparation_limit_seconds": 7200,
        "created_utc": "fixed",
        "jobs": [{"status": "complete", "charged_seconds": 3600}],
    }
    gate = {
        "technical_pass": True,
        "validated_lr": 1e-6,
        "route": "fp16_native",
        "budget_created_utc": "fixed",
        "preparation_jobs": list(budget["jobs"]),
        "source_sha256": {},
        "cost": {"post_evaluation_reserve_seconds": 28800, "fits_40_hours": True},
    }
    return config, gate, budget


def test_study_cannot_reset_preparation_charges_or_change_precision():
    c, g, b = contract()
    validate_config(c, g, b)
    b["jobs"] = []
    with pytest.raises(ValueError, match="charges"):
        validate_config(c, g, b)
    c, g, b = contract()
    c["route"] = "fp32"
    with pytest.raises(ValueError, match="contract"):
        validate_config(c, g, b)


def test_study_retains_evaluation_money_and_rejects_missing_signal():
    c, _, _ = contract()
    state = {
        "rounds": 5,
        "tokens": 1600000,
        "generation_seconds": 6400,
        "generated_responses": 80,
        "update_seconds": 1000,
        "mixed_groups": 10,
    }
    assert forecast(c, state, 140000)["continue"]
    assert not forecast(c, state, 40000)["continue"]
    state["mixed_groups"] = 0
    assert not forecast(c, state, 140000)["continue"]


def test_slow_or_long_observed_answers_make_forecast_more_conservative():
    c, _, _ = contract()
    state = {
        "rounds": 5,
        "tokens": 1600000,
        "generation_seconds": 6400,
        "generated_responses": 80,
        "update_seconds": 1000,
        "mixed_groups": 10,
    }
    original = forecast(c, state, 140000)["estimated_training_seconds_remaining"]
    state["generation_seconds"] = 14000
    assert forecast(c, state, 140000)["estimated_training_seconds_remaining"] > original
    state["tokens"] = 2500000
    state["generation_seconds"] = 10000
    assert forecast(c, state, 140000)["estimated_training_seconds_remaining"] > original


def test_cost_includes_preparation_training_and_both_evaluations():
    from qwen.fast_readiness import cost_estimate

    _, _, budget = contract()
    speeds = {
        k: {"output_tokens": 22000, "generation_seconds": 100}
        for k in ("base4", "adapter4", "adapter2")
    }
    update = {"elapsed_seconds": 100, "forward_backward_seconds": 75}
    capacity = {"capacity_seconds": 18.82, "context_tokens": 32768}
    c = cost_estimate(speeds, update, budget, capacity, safety=1)
    assert c["estimated_total_hours"] == pytest.approx((3600 + 788 * 100 + 37 * 300 + 240) / 3600)
    assert c["post_evaluation_reserve_seconds"] > 98 * 100
    speeds["adapter4"]["generation_seconds"] = 400
    assert not cost_estimate(speeds, update, budget, capacity)["fits_40_hours"]
