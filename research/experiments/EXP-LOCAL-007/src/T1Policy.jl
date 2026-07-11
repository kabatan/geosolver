module ExperimentLocal007T1Policy

const PRIMARY_CONTROL = "prod-tol-120x600"
const CANDIDATE = "SCIPY-HYBR"
const CALLBACK_PREFIXES = (600, 1_200, 2_400, 4_800)
const NUMERIC_COMPARISON_EPSILON = 1.0e-12

# These are the seven generator-unrelated families in the representative-nine
# corpus for which HYBR's public square-system applicability predicate holds.
# REDUNDANT-OVERDETERMINED remains in the corpus as an explicit typed
# inapplicability/capability-gap observation and is not silently dropped.
const APPLICABLE_FAMILIES = (
    "SCALE-LADDER",
    "CURVED-CHAIN",
    "NEAR-RANK-DEFICIENT",
    "TANGENT-CIRCLE-LINE",
    "MULTIROOT-WARPED",
    "STRICT-GUARD-BOUNDARY",
    "OPAQUE-TRANSCENDENTAL-C0",
)

const EXPECTED_INAPPLICABLE_FAMILIES = ("REDUNDANT-OVERDETERMINED",)

const EXPECTED_CORPUS = (
    (
        family_id="SCALE-LADDER",
        instance_id="scale-ladder-d4-spread1.0e12-i101-s1001",
        dimension=4,
        residual_dimension=4,
        replay_checksum="3ab44bedf2890ef0307318d3a012aeec5319b88a1e9cfed8d4b661e52d7f37c2",
    ),
    (
        family_id="CURVED-CHAIN",
        instance_id="curved-chain-d4-curve10000.0-i102-s1002",
        dimension=4,
        residual_dimension=4,
        replay_checksum="8a56042f6ddef9cc097cd1f13fe22b3eb1f376e4ed6a13b7cd70a16f0e566d74",
    ),
    (
        family_id="NEAR-RANK-DEFICIENT",
        instance_id="near-rank-d4-ratio1.0e-8-o103-s1003",
        dimension=4,
        residual_dimension=4,
        replay_checksum="a55330b98965a2a65dc18d93955458ec88b34e14445cff69ff830db028552145",
    ),
    (
        family_id="REDUNDANT-OVERDETERMINED",
        instance_id="redundant-d4-r2-error1.0e-8-i104-s1004",
        dimension=4,
        residual_dimension=12,
        replay_checksum="0da6d36f2c1d6faf115c4875fef01bab41dceca02f3e7921c862abb1589218fb",
    ),
    (
        family_id="TANGENT-CIRCLE-LINE",
        instance_id="tangent-circle-r1.0-ratio0.999999-i105-s1005",
        dimension=2,
        residual_dimension=2,
        replay_checksum="0eab38a9ca7da57f68106a9daeb24f06122433b60362f01b3dafe157e3d557ac",
    ),
    (
        family_id="MULTIROOT-WARPED",
        instance_id="multiroot-d4-n4-sep0.001-condition10000.0-warp0.5-targetz1-c106-s1006",
        dimension=4,
        residual_dimension=4,
        replay_checksum="3e012859175cd8291ffd03db916e618142f449df8a7aa03f1c0c7fe7159b48c9",
    ),
    (
        family_id="MULTIROOT-WARPED",
        instance_id="multiroot-d4-n4-sep0.001-condition10000.0-warp0.5-targetz1_squared-c106-s1006",
        dimension=4,
        residual_dimension=4,
        replay_checksum="1fce84f2621b79af38bef92cd519f1569691f8bd22c6988bf9bde413d81f2cee",
    ),
    (
        family_id="STRICT-GUARD-BOUNDARY",
        instance_id="strict-guard-on_boundary-margin0.0-i108-s1008",
        dimension=2,
        residual_dimension=2,
        replay_checksum="8a3ae1e490fa272ca26b5903b8ff7d956ceb15eaf41d13e526676e71f42cbc13",
    ),
    (
        family_id="OPAQUE-TRANSCENDENTAL-C0",
        instance_id="opaque-transcendental-n3-loops8-phase0.0-mix0.1-i109-s1009",
        dimension=2,
        residual_dimension=2,
        replay_checksum="d6f0cbdd96e75e405d3e9e6db3dec7d3c822112646610c8655663ac204c10b38",
    ),
)

# Rates for a stratum are computed from its member cases before comparison.
# MULTIROOT-WARPED contains both target maps; S3 contains NearRank and Tangent.
const CRITICAL_STRATA = (
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

function _nonnegative(value, label; positive=false)
    converted = Float64(value)
    valid = isfinite(converted) && (positive ? converted > 0.0 : converted >= 0.0)
    valid || throw(ArgumentError(
        "$label must be finite and $(positive ? "positive" : "nonnegative")",
    ))
    return converted
end

function _family_rates(values, label)
    _require_exact_keys(values, APPLICABLE_FAMILIES, label)
    return Dict(
        family => _rate(values[family], "$label/$family") for family in APPLICABLE_FAMILIES
    )
end

function _family_costs(values, label; positive=false)
    _require_exact_keys(values, APPLICABLE_FAMILIES, label)
    return Dict(
        family => _nonnegative(values[family], "$label/$family"; positive) for
        family in APPLICABLE_FAMILIES
    )
end

function _critical_rates(values, label)
    _require_exact_keys(values, CRITICAL_STRATA, label)
    return Dict(
        stratum => _rate(values[stratum], "$label/$stratum") for
        stratum in CRITICAL_STRATA
    )
end

_family_equal(values) = sum(values[family] for family in APPLICABLE_FAMILIES) /
                        length(APPLICABLE_FAMILIES)

"""
Evaluate the frozen T1-to-T2 signal gate.

This function deliberately accepts only already-aggregated, truth-separated
family/stratum metrics. It does not inspect case names, Gold configurations or
targets while a solver is running. The representative-nine outcome still
requires an independent raw-artifact audit before these inputs are trusted.
Callback work is the sum of per-case suffix-stable common-assessor safe-full
work, right-censored at 4,800 callbacks for a miss; it is not the nearly fixed
cost of forcing every stream through the final observation threshold.
"""
function evaluate_promotion_gate(;
    control_family_safe_full,
    candidate_family_safe_full,
    control_family_callback_work,
    candidate_family_callback_work,
    control_family_end_to_end_wall,
    candidate_family_end_to_end_wall,
    control_critical_safe_full,
    candidate_critical_safe_full,
    control_callback_work,
    candidate_callback_work,
    control_end_to_end_wall,
    candidate_end_to_end_wall,
    safety_violation_count::Integer,
    tuning_rounds::Integer=0,
    wall_confirmation_passed::Bool=false,
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
    control_wall = _family_costs(
        control_family_end_to_end_wall,
        "control family end-to-end wall";
        positive=true,
    )
    candidate_wall = _family_costs(
        candidate_family_end_to_end_wall,
        "candidate family end-to-end wall",
    )
    control_critical = _critical_rates(
        control_critical_safe_full,
        "control critical safe-full",
    )
    candidate_critical = _critical_rates(
        candidate_critical_safe_full,
        "candidate critical safe-full",
    )

    total_control_work = _nonnegative(
        control_callback_work,
        "control callback work";
        positive=true,
    )
    total_candidate_work = _nonnegative(candidate_callback_work, "candidate callback work")
    total_control_wall = _nonnegative(
        control_end_to_end_wall,
        "control end-to-end wall";
        positive=true,
    )
    total_candidate_wall = _nonnegative(
        candidate_end_to_end_wall,
        "candidate end-to-end wall",
    )
    total_matches(parts, total) = abs(sum(values(parts)) - total) <=
                                  NUMERIC_COMPARISON_EPSILON * max(1.0, total)
    total_matches(control_work, total_control_work) || throw(
        ArgumentError("control family callback work does not sum to its total"),
    )
    total_matches(candidate_work, total_candidate_work) || throw(
        ArgumentError("candidate family callback work does not sum to its total"),
    )
    total_matches(control_wall, total_control_wall) || throw(
        ArgumentError("control family wall does not sum to its total"),
    )
    total_matches(candidate_wall, total_candidate_wall) || throw(
        ArgumentError("candidate family wall does not sum to its total"),
    )
    safety_violation_count >= 0 ||
        throw(ArgumentError("safety violation count must be nonnegative"))
    tuning_rounds >= 0 || throw(ArgumentError("tuning rounds must be nonnegative"))

    family_equal_control = _family_equal(control_safe)
    family_equal_candidate = _family_equal(candidate_safe)
    safe_full_delta = family_equal_candidate - family_equal_control
    callback_work_ratio = total_candidate_work / total_control_work
    end_to_end_wall_ratio = total_candidate_wall / total_control_wall
    epsilon = NUMERIC_COMPARISON_EPSILON

    performance_path_a = safe_full_delta + epsilon >= 0.05 &&
                         callback_work_ratio <= 1.20 + epsilon
    callback_efficiency = callback_work_ratio <= 0.80 + epsilon
    confirmed_wall_efficiency = end_to_end_wall_ratio <= 0.80 + epsilon &&
                                wall_confirmation_passed
    performance_path_b = safe_full_delta + epsilon >= -0.01 &&
                         (callback_efficiency || confirmed_wall_efficiency)

    critical_deltas = Dict(
        stratum => candidate_critical[stratum] - control_critical[stratum] for
        stratum in CRITICAL_STRATA
    )
    critical_gate = all(
        delta + epsilon >= -0.02 for delta in values(critical_deltas)
    )

    path_a_supporting_families = sort!(String[
        family for family in APPLICABLE_FAMILIES if
        candidate_safe[family] - control_safe[family] > epsilon
    ])
    path_b_supporting_families = sort!(String[
        family for family in APPLICABLE_FAMILIES if
        candidate_safe[family] - control_safe[family] + epsilon >= -0.01 &&
        (candidate_work[family] / control_work[family] <= 0.80 + epsilon ||
         (wall_confirmation_passed &&
          candidate_wall[family] / control_wall[family] <= 0.80 + epsilon))
    ])
    generality_gate = (performance_path_a && length(path_a_supporting_families) >= 3) ||
                      (performance_path_b && length(path_b_supporting_families) >= 3)
    safety_gate = safety_violation_count == 0
    tuning_gate = tuning_rounds <= 2
    passed = (performance_path_a || performance_path_b) && critical_gate &&
             generality_gate && safety_gate && tuning_gate

    return Dict{String,Any}(
        "family_equal_control_safe_full" => family_equal_control,
        "family_equal_candidate_safe_full" => family_equal_candidate,
        "family_equal_safe_full_delta" => safe_full_delta,
        "callback_work_ratio" => callback_work_ratio,
        "end_to_end_wall_ratio" => end_to_end_wall_ratio,
        "performance_path_a" => performance_path_a,
        "performance_path_b" => performance_path_b,
        "callback_efficiency" => callback_efficiency,
        "confirmed_wall_efficiency" => confirmed_wall_efficiency,
        "wall_confirmation_passed" => wall_confirmation_passed,
        "critical_deltas" => critical_deltas,
        "critical_gate" => critical_gate,
        "path_a_supporting_families" => path_a_supporting_families,
        "path_b_supporting_families" => path_b_supporting_families,
        "generality_gate" => generality_gate,
        "safety_gate" => safety_gate,
        "tuning_gate" => tuning_gate,
        "passed" => passed,
    )
end

function promotion_gate_contract()
    return Dict{String,Any}(
        "primary_control" => PRIMARY_CONTROL,
        "candidate" => CANDIDATE,
        "metric_scope" => "public-square-applicability-cases-only",
        "family_equal_safe_full" => "mean-of-per-family-assessor-safe-full-rates",
        "callback_work" =>
            "sum-per-case-suffix-stable-assessor-safe-full-callbacks-right-censored-at-4800",
        "callback_work_miss_value" => 4_800,
        "applicable_families" => collect(APPLICABLE_FAMILIES),
        "expected_typed_inapplicable_families" => collect(EXPECTED_INAPPLICABLE_FAMILIES),
        "callback_prefixes" => collect(CALLBACK_PREFIXES),
        "numeric_comparison_epsilon" => NUMERIC_COMPARISON_EPSILON,
        "performance_path_a" => Dict{String,Any}(
            "minimum_family_equal_safe_full_delta" => 0.05,
            "maximum_callback_work_ratio" => 1.20,
        ),
        "performance_path_b" => Dict{String,Any}(
            "minimum_family_equal_safe_full_delta" => -0.01,
            "maximum_callback_work_ratio_or_end_to_end_wall_ratio" => 0.80,
            "wall_only_confirmation" =>
                "two clean one-thread AB/BA process-order replicates must each meet 0.80 before wall alone can pass",
        ),
        "critical_strata" => collect(CRITICAL_STRATA),
        "minimum_critical_stratum_safe_full_delta" => -0.02,
        "minimum_unrelated_supporting_families" => 3,
        "maximum_tuning_rounds" => 2,
        "actual_tuning_rounds" => 0,
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
        "zero_required_scope" =>
            "candidate-only-all-applicable-cases-and-prefixes; truth-leak-by-source-audit",
        "control_safety_role" =>
            "control violations affect baseline safe-full/work but not candidate zero count",
        "promotion_meaning" => "T2-generalization-signal-only-not-production",
        "capability_limit" =>
            "typed nonsquare inapplicability is reported but cannot support a production-default claim",
    )
end

export APPLICABLE_FAMILIES,
    CALLBACK_PREFIXES,
    CANDIDATE,
    CRITICAL_STRATA,
    EXPECTED_CORPUS,
    EXPECTED_INAPPLICABLE_FAMILIES,
    NUMERIC_COMPARISON_EPSILON,
    PRIMARY_CONTROL,
    evaluate_promotion_gate,
    promotion_gate_contract

end
