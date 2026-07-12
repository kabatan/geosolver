module ExperimentLocal009T0Policy

const CALLBACK_PREFIXES = (600, 1_200, 2_400, 4_800)
const PRIMARY_CONTROL = "prod-tol-120x600"
const CANDIDATE = "RESTORING-GN-CPQR"
const T0_STRATA = (
    "CURVED-CHAIN",
    "NEAR-RANK-DEFICIENT",
    "TANGENT-CIRCLE-LINE",
    "MULTIROOT-WARPED",
    "STRICT-GUARD-BOUNDARY",
)

function promotion_gate_contract()
    return Dict{String,Any}(
        "final_callback_prefix" => last(CALLBACK_PREFIXES),
        "primary_control" => PRIMARY_CONTROL,
        "candidate" => CANDIDATE,
        "common_assessor_authority" => true,
        "primary_work" =>
            "sum-of-per-case-suffix-stable-common-assessor-safe-full-work-right-censored-at-4800",
        "path_a" => Dict{String,Any}(
            "aggregate_target_noninferiority" => true,
            "aggregate_safe_full_noninferiority" => true,
            "strict_target_or_safe_full_gain" => true,
            "maximum_right_censored_work_ratio" => 1.20,
        ),
        "path_b" => Dict{String,Any}(
            "aggregate_target_noninferiority" => true,
            "aggregate_safe_full_noninferiority" => true,
            "maximum_right_censored_work_ratio" => 0.80,
        ),
        "stratum_target_noninferiority" => collect(T0_STRATA),
        "strict_guard_safe_full_required" => true,
        "qualified_invalid_trial_recovery_required" => true,
        "candidate_safety_accounting_budget_exception_count" => 0,
        "tuning_rounds" => 0,
        "wall_time_role" => "diagnostic-only",
    )
end

function evaluate_promotion_gate(;
    control_targets::Integer,
    candidate_targets::Integer,
    control_safe_full::Integer,
    candidate_safe_full::Integer,
    control_right_censored_assessor_work::Real,
    candidate_right_censored_assessor_work::Real,
    control_stratum_targets::AbstractDict,
    candidate_stratum_targets::AbstractDict,
    candidate_strict_guard_safe_full::Bool,
    candidate_qualified_invalid_trial_recoveries::Integer,
    candidate_safety_accounting_budget_exception_count::Integer,
)
    all(value -> value >= 0, (
        control_targets,
        candidate_targets,
        control_safe_full,
        candidate_safe_full,
        candidate_qualified_invalid_trial_recoveries,
        candidate_safety_accounting_budget_exception_count,
    )) || throw(ArgumentError("gate counts must be nonnegative"))
    isfinite(control_right_censored_assessor_work) &&
        control_right_censored_assessor_work > 0 || throw(ArgumentError(
        "control right-censored assessor work must be finite and positive",
    ))
    isfinite(candidate_right_censored_assessor_work) &&
        candidate_right_censored_assessor_work >= 0 || throw(ArgumentError(
        "candidate right-censored assessor work must be finite and nonnegative",
    ))
    control_by_stratum = Dict(String(key) => value for (key, value) in control_stratum_targets)
    candidate_by_stratum =
        Dict(String(key) => value for (key, value) in candidate_stratum_targets)
    Set(keys(control_by_stratum)) == Set(T0_STRATA) ||
        throw(ArgumentError("control stratum map must exactly match T0 strata"))
    Set(keys(candidate_by_stratum)) == Set(T0_STRATA) ||
        throw(ArgumentError("candidate stratum map must exactly match T0 strata"))

    work_ratio = Float64(
        candidate_right_censored_assessor_work / control_right_censored_assessor_work,
    )
    target_noninferior = candidate_targets >= control_targets
    safe_full_noninferior = candidate_safe_full >= control_safe_full
    strict_gain = candidate_targets > control_targets ||
                  candidate_safe_full > control_safe_full
    stratum_deltas = Dict{String,Int}(
        stratum => Int(candidate_by_stratum[stratum]) -
                   Int(control_by_stratum[stratum]) for stratum in T0_STRATA
    )
    stratum_gate = all(value -> value >= 0, values(stratum_deltas))
    safety_gate = iszero(candidate_safety_accounting_budget_exception_count)
    guard_gate = candidate_strict_guard_safe_full &&
                 candidate_qualified_invalid_trial_recoveries >= 1
    path_a = target_noninferior && safe_full_noninferior && strict_gain &&
             work_ratio <= 1.20
    path_b = target_noninferior && safe_full_noninferior && work_ratio <= 0.80
    performance_gate = path_a || path_b
    return Dict{String,Any}(
        "target_noninferior" => target_noninferior,
        "safe_full_noninferior" => safe_full_noninferior,
        "strict_gain" => strict_gain,
        "right_censored_assessor_work_ratio" => work_ratio,
        "path_a" => path_a,
        "path_b" => path_b,
        "stratum_target_deltas" => stratum_deltas,
        "stratum_gate" => stratum_gate,
        "strict_guard_mechanism_gate" => guard_gate,
        "safety_accounting_gate" => safety_gate,
        "performance_gate" => performance_gate,
        "passed" => performance_gate && stratum_gate && guard_gate && safety_gate,
    )
end

export CALLBACK_PREFIXES,
    CANDIDATE,
    PRIMARY_CONTROL,
    T0_STRATA,
    evaluate_promotion_gate,
    promotion_gate_contract

end
