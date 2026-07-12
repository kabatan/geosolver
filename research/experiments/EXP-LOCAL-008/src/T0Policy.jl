module ExperimentLocal008T0Policy

const CALLBACK_PREFIXES = (600, 1_200, 2_400, 4_800)
const PRIMARY_CONTROL = "prod-tol-120x600"
const CANDIDATE = "ORTHOMADS-EB"
const T0_STRATA = (
    "CURVED-CHAIN",
    "NEAR-RANK-DEFICIENT",
    "TANGENT-CIRCLE-LINE",
    "MULTIROOT-WARPED",
    "STRICT-GUARD-BOUNDARY",
)
const PATH_A_MAXIMUM_WORK_RATIO = 1.20
const PATH_B_MAXIMUM_WORK_RATIO = 0.80

function _count(value, label)
    value isa Integer || throw(ArgumentError("$label must be an integer"))
    value >= 0 || throw(ArgumentError("$label must be nonnegative"))
    return Int(value)
end

function _exact_stratum_counts(values, label)
    material = Dict(String(key) => value for (key, value) in pairs(values))
    Set(keys(material)) == Set(T0_STRATA) ||
        throw(ArgumentError("$label keys must exactly match the preregistered T0 strata"))
    return Dict(
        stratum => _count(material[stratum], "$label[$stratum]") for stratum in T0_STRATA
    )
end

function promotion_gate_contract()
    return Dict{String,Any}(
        "final_callback_prefix" => last(CALLBACK_PREFIXES),
        "primary_control" => PRIMARY_CONTROL,
        "candidate" => CANDIDATE,
        "work" =>
            "sum-per-case-raw-common-assessor-suffix-stable-safe-full-work-right-censored-at-4800",
        "path_a" => Dict(
            "target_and_safe_full_noninferior" => true,
            "strict_target_or_safe_full_gain" => true,
            "maximum_work_ratio" => PATH_A_MAXIMUM_WORK_RATIO,
        ),
        "path_b" => Dict(
            "target_and_safe_full_noninferior" => true,
            "maximum_work_ratio" => PATH_B_MAXIMUM_WORK_RATIO,
        ),
        "exact_strata" => collect(T0_STRATA),
        "strict_guard_safe_full_required" => true,
        "qualified_extreme_barrier_recovery_required" => true,
        "candidate_safety_accounting_budget_exception_count" => 0,
        "mechanism_fixture_tests_required" => true,
        "truth_blind_source_audit_required" => true,
        "tuning_rounds" => 0,
        "wall_time_role" => "diagnostic-only",
    )
end

"""Evaluate the preregistered, outcome-independent EXP-LOCAL-008 T0 gate."""
function evaluate_t0_gate(;
    control_targets::Integer,
    candidate_targets::Integer,
    control_safe_full::Integer,
    candidate_safe_full::Integer,
    control_callback_work::Real,
    candidate_callback_work::Real,
    control_stratum_targets::AbstractDict,
    candidate_stratum_targets::AbstractDict,
    candidate_strict_guard_safe_full::Bool,
    candidate_qualified_extreme_barrier_recoveries::Integer,
    candidate_safety_accounting_budget_exception_count::Integer,
    mechanism_fixture_tests_passed::Bool,
    truth_blind_source_audit_passed::Bool,
)
    control_target_count = _count(control_targets, "control target count")
    candidate_target_count = _count(candidate_targets, "candidate target count")
    control_safe_count = _count(control_safe_full, "control safe-full count")
    candidate_safe_count = _count(candidate_safe_full, "candidate safe-full count")
    recoveries = _count(
        candidate_qualified_extreme_barrier_recoveries,
        "qualified extreme-barrier recovery count",
    )
    violations = _count(
        candidate_safety_accounting_budget_exception_count,
        "safety/accounting/budget/exception count",
    )
    isfinite(control_callback_work) && control_callback_work > 0 ||
        throw(ArgumentError("control callback work must be finite and positive"))
    isfinite(candidate_callback_work) && candidate_callback_work >= 0 ||
        throw(ArgumentError("candidate callback work must be finite and nonnegative"))
    control_strata = _exact_stratum_counts(control_stratum_targets, "control strata")
    candidate_strata = _exact_stratum_counts(candidate_stratum_targets, "candidate strata")

    target_noninferior = candidate_target_count >= control_target_count
    safe_full_noninferior = candidate_safe_count >= control_safe_count
    strict_gain = candidate_target_count > control_target_count ||
                  candidate_safe_count > control_safe_count
    callback_work_ratio = Float64(candidate_callback_work / control_callback_work)
    path_a = target_noninferior && safe_full_noninferior && strict_gain &&
             callback_work_ratio <= PATH_A_MAXIMUM_WORK_RATIO
    path_b = target_noninferior && safe_full_noninferior &&
             callback_work_ratio <= PATH_B_MAXIMUM_WORK_RATIO
    stratum_deltas = Dict(
        stratum => candidate_strata[stratum] - control_strata[stratum] for
        stratum in T0_STRATA
    )
    stratum_gate = all(value -> value >= 0, values(stratum_deltas))
    safety_gate = iszero(violations)
    strict_guard_gate = candidate_strict_guard_safe_full && recoveries >= 1
    evidence_gate = mechanism_fixture_tests_passed && truth_blind_source_audit_passed
    passed = (path_a || path_b) && stratum_gate && safety_gate &&
             strict_guard_gate && evidence_gate
    return Dict{String,Any}(
        "passed" => passed,
        "path_a" => path_a,
        "path_b" => path_b,
        "target_noninferior" => target_noninferior,
        "safe_full_noninferior" => safe_full_noninferior,
        "strict_gain" => strict_gain,
        "callback_work_ratio" => callback_work_ratio,
        "stratum_target_deltas" => stratum_deltas,
        "every_predeclared_stratum_noninferior" => stratum_gate,
        "safety_accounting_gate" => safety_gate,
        "strict_guard_mechanism_gate" => strict_guard_gate,
        "mechanism_fixture_tests_passed" => mechanism_fixture_tests_passed,
        "truth_blind_source_audit_passed" => truth_blind_source_audit_passed,
    )
end

export CALLBACK_PREFIXES,
    CANDIDATE,
    PATH_A_MAXIMUM_WORK_RATIO,
    PATH_B_MAXIMUM_WORK_RATIO,
    PRIMARY_CONTROL,
    T0_STRATA,
    evaluate_t0_gate,
    promotion_gate_contract

end
