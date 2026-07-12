module ExperimentLocal007T2Policy

using ..ExperimentLocal007T2Corpus

const T2_PRIMARY_CONTROL = "prod-tol-120x600"
const T2_CANDIDATE = "SCIPY-HYBR"
const T2_NUMERIC_EPSILON = 1.0e-12
const T2_CRITICAL_STRATA = (
    "S1-regular-curved",
    "S2-S5-close-root-target-collision",
    "S3-singular-tangent-rank-deficient",
    "S4-guard-boundary-domain",
    "S6-opaque-transcendental",
    "S8-extreme-scale",
)

function _require_exact_keys(values, expected, label)
    observed = Set(String(key) for key in keys(values))
    required = Set(expected)
    observed == required || throw(ArgumentError(
        "$label keys must be exactly $(join(sort!(collect(required)), ','))",
    ))
    return nothing
end

function _rate(value, label)
    converted = Float64(value)
    isfinite(converted) && 0.0 <= converted <= 1.0 ||
        throw(ArgumentError("$label must be a finite rate in [0,1]"))
    return converted
end

function _cost(value, label; positive=false)
    converted = Float64(value)
    valid = isfinite(converted) && (positive ? converted > 0.0 : converted >= 0.0)
    valid || throw(ArgumentError(
        "$label must be finite and $(positive ? "positive" : "nonnegative")",
    ))
    return converted
end

function _family_rates(values, label)
    _require_exact_keys(values, T2_APPLICABLE_FAMILIES, label)
    return Dict(
        family => _rate(values[family], "$label/$family") for
        family in T2_APPLICABLE_FAMILIES
    )
end

function _family_costs(values, label; positive=false)
    _require_exact_keys(values, T2_APPLICABLE_FAMILIES, label)
    return Dict(
        family => _cost(values[family], "$label/$family"; positive) for
        family in T2_APPLICABLE_FAMILIES
    )
end

function _critical_rates(values, label)
    _require_exact_keys(values, T2_CRITICAL_STRATA, label)
    return Dict(
        stratum => _rate(values[stratum], "$label/$stratum") for
        stratum in T2_CRITICAL_STRATA
    )
end

_family_equal(values) =
    sum(values[family] for family in T2_APPLICABLE_FAMILIES) /
    length(T2_APPLICABLE_FAMILIES)

function _total_matches(parts, total)
    return abs(sum(values(parts)) - total) <=
           T2_NUMERIC_EPSILON * max(1.0, abs(total))
end

"""
Evaluate the preregistered callback-only T2 generalization gate.

All arguments are post-run, truth-separated aggregates. Runtime algorithms do
not receive family IDs, strata, Gold data or this policy. Work is the sum of
per-case suffix-stable common-assessor safe-full callback work, with a miss or
value above 4,800 right-censored at 4,800, over square-applicable cases.
"""
function evaluate_t2_promotion_gate(;
    control_family_safe_full,
    candidate_family_safe_full,
    control_family_callback_work,
    candidate_family_callback_work,
    control_critical_safe_full,
    candidate_critical_safe_full,
    control_callback_work,
    candidate_callback_work,
    candidate_safety_violation_count::Integer,
    nonsquare_inapplicability_violation_count::Integer,
    tuning_rounds::Integer=0,
)
    control_safe = _family_rates(control_family_safe_full, "control family safe-full")
    candidate_safe = _family_rates(candidate_family_safe_full, "candidate family safe-full")
    control_work = _family_costs(
        control_family_callback_work,
        "control family callback work";
        positive=true,
    )
    candidate_work = _family_costs(
        candidate_family_callback_work,
        "candidate family callback work",
    )
    control_critical = _critical_rates(
        control_critical_safe_full,
        "control critical safe-full",
    )
    candidate_critical = _critical_rates(
        candidate_critical_safe_full,
        "candidate critical safe-full",
    )
    total_control_work = _cost(
        control_callback_work,
        "control callback work";
        positive=true,
    )
    total_candidate_work = _cost(candidate_callback_work, "candidate callback work")
    _total_matches(control_work, total_control_work) || throw(
        ArgumentError("control family callback work does not sum to its total"),
    )
    _total_matches(candidate_work, total_candidate_work) || throw(
        ArgumentError("candidate family callback work does not sum to its total"),
    )
    candidate_safety_violation_count >= 0 || throw(
        ArgumentError("candidate safety violation count must be nonnegative"),
    )
    nonsquare_inapplicability_violation_count >= 0 || throw(
        ArgumentError("nonsquare inapplicability violation count must be nonnegative"),
    )
    tuning_rounds >= 0 || throw(ArgumentError("tuning rounds must be nonnegative"))

    family_equal_control = _family_equal(control_safe)
    family_equal_candidate = _family_equal(candidate_safe)
    safe_full_delta = family_equal_candidate - family_equal_control
    callback_work_ratio = total_candidate_work / total_control_work
    epsilon = T2_NUMERIC_EPSILON

    performance_path_a = safe_full_delta + epsilon >= 0.05 &&
                         callback_work_ratio <= 1.20 + epsilon
    performance_path_b = safe_full_delta + epsilon >= -0.01 &&
                         callback_work_ratio <= 0.80 + epsilon

    critical_deltas = Dict(
        stratum => candidate_critical[stratum] - control_critical[stratum] for
        stratum in T2_CRITICAL_STRATA
    )
    critical_gate = all(delta + epsilon >= -0.02 for delta in values(critical_deltas))

    path_a_supporting_families = sort!(String[
        family for family in T2_APPLICABLE_FAMILIES if
        candidate_safe[family] - control_safe[family] > epsilon
    ])
    path_b_supporting_families = sort!(String[
        family for family in T2_APPLICABLE_FAMILIES if
        candidate_safe[family] - control_safe[family] + epsilon >= -0.01 &&
        candidate_work[family] / control_work[family] <= 0.80 + epsilon
    ])
    generality_gate =
        (performance_path_a && length(path_a_supporting_families) >= 3) ||
        (performance_path_b && length(path_b_supporting_families) >= 3)
    safety_gate = candidate_safety_violation_count == 0
    nonsquare_gate = nonsquare_inapplicability_violation_count == 0
    tuning_gate = tuning_rounds <= 2
    passed = (performance_path_a || performance_path_b) && critical_gate &&
             generality_gate && safety_gate && nonsquare_gate && tuning_gate

    return Dict{String,Any}(
        "callback_work_ratio" => callback_work_ratio,
        "critical_deltas" => critical_deltas,
        "critical_gate" => critical_gate,
        "family_equal_candidate_safe_full" => family_equal_candidate,
        "family_equal_control_safe_full" => family_equal_control,
        "family_equal_safe_full_delta" => safe_full_delta,
        "generality_gate" => generality_gate,
        "nonsquare_gate" => nonsquare_gate,
        "passed" => passed,
        "path_a_supporting_families" => path_a_supporting_families,
        "path_b_supporting_families" => path_b_supporting_families,
        "performance_path_a" => performance_path_a,
        "performance_path_b" => performance_path_b,
        "safety_gate" => safety_gate,
        "tuning_gate" => tuning_gate,
    )
end

function t2_promotion_gate_contract()
    return Dict{String,Any}(
        "actual_tuning_rounds" => 0,
        "applicable_families" => collect(T2_APPLICABLE_FAMILIES),
        "callback_work" =>
            "sum-per-case-suffix-stable-common-assessor-safe-full-callbacks-miss-right-censored-at-4800-applicable-cases-only",
        "callback_work_miss_value" => 4_800,
        "candidate" => T2_CANDIDATE,
        "critical_strata" => collect(T2_CRITICAL_STRATA),
        "maximum_tuning_rounds" => 2,
        "minimum_critical_stratum_safe_full_delta" => -0.02,
        "minimum_unrelated_supporting_families" => 3,
        "nonsquare_gate" =>
            "all six REDUNDANT-OVERDETERMINED cases return typed INAPPLICABLE_NONSQUARE with zero callbacks at every paired start",
        "numeric_comparison_epsilon" => T2_NUMERIC_EPSILON,
        "performance_path_a" => Dict{String,Any}(
            "maximum_callback_work_ratio" => 1.20,
            "minimum_family_equal_safe_full_delta" => 0.05,
        ),
        "performance_path_b" => Dict{String,Any}(
            "maximum_callback_work_ratio" => 0.80,
            "minimum_family_equal_safe_full_delta" => -0.01,
        ),
        "primary_control" => T2_PRIMARY_CONTROL,
        "production_promotion" => false,
        "promotion_meaning" => "square-capability-local-survivor-only",
        "safety_scope" =>
            "candidate-only-all-square-applicable-cases-and-prefixes; truth-leak-by-source-audit",
        "wall_metric_role" => "diagnostic-never-gating",
        "zero_required" => String[
            "reported-accepted-canonical-invalid",
            "reported-accepted-gold-inconsistent",
            "reported-accepted-numeric-target-only",
            "reported-accepted-ambiguous",
            "assessor-qualified-gold-inconsistent",
            "evaluation-count-mismatch",
            "runner-cap-violation",
            "unhandled-exception",
            "truth-leak",
        ],
    )
end

export T2_CANDIDATE,
    T2_CRITICAL_STRATA,
    T2_NUMERIC_EPSILON,
    T2_PRIMARY_CONTROL,
    evaluate_t2_promotion_gate,
    t2_promotion_gate_contract

end
