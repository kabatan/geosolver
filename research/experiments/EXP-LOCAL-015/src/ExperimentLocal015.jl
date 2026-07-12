module ExperimentLocal015

using LinearAlgebra
using Random
using SHA

include("RankPrecisionRescue.jl")
include("AdaptivePrecisionRescue.jl")
include("WeakBracketRescue.jl")
include("RescueFixtures.jl")

const REF = RankPrecisionRescue
const ADAPT = AdaptivePrecisionRescue
const WEAK = WeakBracketRescue
const FIXTURES = RescueFixtures

export ADAPTIVE_ARM,
    DIAGNOSTIC_ARM,
    ISOTROPIC_ARM,
    NO_RESCUE_ARM,
    REFERENCE_ARM,
    WEAK_ADAPTIVE_ARM,
    WEAK_ARM,
    WEAK_NO_EMIT_ARM,
    T0_ARMS,
    ArmTrialResult,
    AssessorMatch,
    SharedPrefilterResult,
    acquire_shared_prefilter,
    assess_bracket_seeds,
    assess_point_seeds,
    materialize_t0_cases,
    run_adaptive_arm,
    run_combined_arm,
    run_diagnostic_arm,
    run_no_rescue_arm,
    run_reference_arm,
    run_weak_arm

const NO_RESCUE_ARM = "E4-ENDPOINT-NO-RESCUE"
const DIAGNOSTIC_ARM = "FLOAT64-H-H2-DIAGNOSTIC-ONLY"
const REFERENCE_ARM = REF.REFERENCE_NAME
const ADAPTIVE_ARM = ADAPT.ADAPTED_NAME
const WEAK_ARM = "WEAK-BRACKET"
const ISOTROPIC_ARM = "ISOTROPIC-BRACKET"
const WEAK_NO_EMIT_ARM = "WEAK-NO-EMIT"
const WEAK_ADAPTIVE_ARM = "WEAK-THEN-ADAPTIVE"
const T0_ARMS = (
    NO_RESCUE_ARM,
    DIAGNOSTIC_ARM,
    REFERENCE_ARM,
    ADAPTIVE_ARM,
    WEAK_ARM,
    ISOTROPIC_ARM,
    WEAK_NO_EMIT_ARM,
    WEAK_ADAPTIVE_ARM,
)

const SHARED_FD_STEP = WEAK.CPQR_FD_STEP
const SHARED_RANK_UNCERTAINTY_MULTIPLIER = 4.0
const SHARED_MODEL_RELATIVE_DISAGREEMENT_MAX = 0.25
const SHARED_ROUNDOFF_MULTIPLIER = 16.0
const CONDITION_TRIGGER = 1.0e8
# Derived from the frozen Float64 central-FD step, not fitted to outcomes.
const CONDITION_GREY_RELATIVE_WIDTH = sqrt(SHARED_FD_STEP)
const ROOT_MATCH_TOLERANCE = 0x1.0p-40
const BRACKET_CURVATURE_MULTIPLIER = 8.0

"""Assessor-only support; never pass this object back through a candidate API."""
struct AssessorMatch
    emitted_count::Int
    supported_count::Int
    matched_root_indices::Vector{Int}
    unsupported_count::Int
end

"""Candidate-side output.  It deliberately contains no assessor truth."""
struct ArmTrialResult
    arm::String
    status::Symbol
    reason::Symbol
    rescue_callbacks::Int
    rescue_raw_work::Int
    rescue_weighted_work::Int
    activation::Bool
    new_seed_count::Int
    point_seeds::Vector{Tuple}
    bracket_seeds::Vector{WEAK.RefinementSeed}
    requested_precision_counts::Dict{String,Int}
    observables::Any
end

"""Opaque binding between one acquired stencil and its callback source."""
struct SharedWeakProbeContext
    evaluate_float64::Function
    box::WEAK.NormalizedBox
    endpoint::Vector{Float64}
    anchor::WEAK.RescueEvaluation
    diagnostic::WEAK.CPQRDiagnostic
end

function _semantic_signature(observation)
    return (
        branch=observation.branch_identity,
        guard=observation.guard_identity,
        domain=observation.domain_identity,
    )
end

function _semantic_valid(observation)
    observation isa WEAK.RescueEvaluation || return false
    observation.valid || return false
    all(isfinite, observation.residual) || return false
    return all(value -> isfinite(value) && value > 0.0, (
        observation.branch_margin,
        observation.guard_margin,
        observation.domain_margin,
    ))
end

function _routed_condition(prefilter)
    return prefilter.condition_class == :above_trigger ?
           CONDITION_TRIGGER * (1 + 2CONDITION_GREY_RELATIVE_WIDTH) : 0.0
end

function run_no_rescue_arm(endpoint)
    return ArmTrialResult(
        NO_RESCUE_ARM,
        :control,
        :unchanged_endpoint,
        0,
        0,
        0,
        false,
        0,
        Tuple[Tuple(Float64[endpoint...])],
        WEAK.RefinementSeed[],
        Dict{String,Int}(),
        (;),
    )
end

function run_diagnostic_arm(prefilter)
    ready = prefilter.status == :ready
    trigger = ready && (
        prefilter.numerical_rank < length(prefilter.endpoint) ||
        prefilter.condition_class == :above_trigger
    )
    return ArmTrialResult(
        DIAGNOSTIC_ARM,
        ready ? :control : :unknown,
        ready ? :shared_prefilter_only : prefilter.reason,
        0,
        0,
        0,
        trigger,
        0,
        Tuple[],
        WEAK.RefinementSeed[],
        Dict{String,Int}(),
        (;
            complete_h_h2_model=ready,
            rank_or_condition_trigger=trigger,
            condition_uncertain=ready && prefilter.condition_class == :uncertain,
        ),
    )
end

function _reference_sample(fixture, x, _bits)
    raw = try
        fixture.evaluate_arbitrary(x)
    catch error
        error isa InterruptException && rethrow()
        return nothing
    end
    observation = _weak_observation(raw)
    observation isa WEAK.RescueEvaluation || return nothing
    return REF.RankRescueSample(
        BigFloat[BigFloat(value) for value in observation.residual],
        _semantic_valid(observation),
        _semantic_signature(observation),
    )
end

function _adaptive_semantic_state(observation)
    return ADAPT.AdaptiveSemanticState(
        observation.branch_identity,
        observation.branch_margin,
        (observation.guard_identity,),
        (observation.guard_margin,),
        (observation.domain_identity,),
        (observation.domain_margin,),
    )
end

function _adaptive_sample(fixture, x, _bits)
    raw = try
        fixture.evaluate_arbitrary(x)
    catch error
        error isa InterruptException && rethrow()
        return nothing
    end
    state = try
        ADAPT.AdaptiveSemanticState(
            raw.branch_identity,
            raw.branch_margin,
            (raw.guard_identity,),
            (raw.guard_margin,),
            (raw.domain_identity,),
            (raw.domain_margin,),
        )
    catch error
        error isa InterruptException && rethrow()
        return nothing
    end
    return ADAPT.AdaptiveRescueSample(raw.residual, raw.valid, state)
end

function _empty_adaptive_arm(reason::Symbol)
    return ArmTrialResult(
        ADAPTIVE_ARM,
        :unknown,
        reason,
        0,
        0,
        0,
        false,
        0,
        Tuple[],
        WEAK.RefinementSeed[],
        Dict{String,Int}(),
        (;
            confirmation_site="same_source_model",
            tier_started=false,
            newton_step_accepted=false,
            cross_tier_confirmed=false,
            same_source_model_confirmed=false,
            refined_endpoint_high_precision_confirmed=false,
        ),
    )
end

function run_adaptive_arm(
    fixture,
    prefilter;
    maximum_rescue_work::Integer=ADAPT.FORMAL_WEIGHTED_WORK_CAP,
    observe_callback=(precision_bits) -> nothing,
)
    prefilter.status == :ready || return _empty_adaptive_arm(
        :shared_prefilter_unavailable,
    )
    maximum_rescue_work > 0 || return _empty_adaptive_arm(
        :remaining_rescue_budget_exhausted,
    )
    anchor = prefilter.anchor
    anchor isa WEAK.RescueEvaluation || return _empty_adaptive_arm(
        :shared_anchor_unavailable,
    )
    problem = ADAPT.AdaptiveRescueProblem(
        length(prefilter.endpoint),
        length(anchor.residual),
        :C2,
        fixture.box.lower,
        fixture.box.upper,
        (x, bits) -> begin
            observe_callback(bits)
            sample = _adaptive_sample(fixture, x, bits)
            sample === nothing && error("malformed arbitrary-precision fixture callback")
            sample
        end,
    )
    seed = ADAPT.AdaptiveRescueSeed(
        prefilter.endpoint,
        prefilter.numerical_rank,
        _routed_condition(prefilter),
        prefilter.model_agreement,
        _semantic_valid(anchor),
        _adaptive_semantic_state(anchor),
    )
    cap = min(Int(maximum_rescue_work), ADAPT.FORMAL_WEIGHTED_WORK_CAP)
    result = ADAPT.rescue_adaptive_precision(
        problem,
        seed;
        options=ADAPT.AdaptiveRescueOptions(
            maximum_weighted_oracle_work=cap,
            maximum_callbacks=ADAPT.FORMAL_WEIGHTED_WORK_CAP,
        ),
    )
    point_seeds = result.status == :seed_ready ?
                  Tuple[Tuple(result.evidence.refined_coordinates)] : Tuple[]
    counts = Dict(
        string(entry.precision_bits) => entry.callbacks for
        entry in result.work.calls_by_precision
    )
    evidence = result.status == :seed_ready ? result.evidence : nothing
    return ArmTrialResult(
        ADAPTIVE_ARM,
        result.status,
        result.reason,
        result.work.callbacks,
        result.work.raw_oracle_work,
        result.work.precision_weighted_oracle_work,
        result.work.tier_count > 0,
        length(point_seeds),
        point_seeds,
        WEAK.RefinementSeed[],
        counts,
        (;
            confirmation_site="same_source_model",
            prefilter_numerical_rank=prefilter.numerical_rank,
            prefilter_condition_class=String(prefilter.condition_class),
            routed_condition_estimate=_routed_condition(prefilter),
            tier_started=result.work.tier_count > 0,
            newton_step_accepted=result.work.newton_steps > 0,
            cross_tier_confirmed=result.status == :seed_ready,
            same_source_model_confirmed=result.status == :seed_ready,
            refined_endpoint_high_precision_confirmed=false,
            tier_count=result.work.tier_count,
            factorization_count=result.work.factorization_count,
            newton_steps=result.work.newton_steps,
            precision_path=(evidence === nothing ? () : evidence.precision_path),
            selected_precision_bits=(
                evidence === nothing ? nothing : evidence.selected_precision_bits
            ),
            confirmation_precision_bits=(
                evidence === nothing ? nothing : evidence.confirmation_precision_bits
            ),
            selected_numerical_rank=(
                evidence === nothing ? nothing : evidence.selected_numerical_rank
            ),
            confirmation_numerical_rank=(
                evidence === nothing ? nothing : evidence.confirmation_numerical_rank
            ),
            rank_stable=(evidence === nothing ? false : evidence.rank_stable),
            correction_stable=(evidence === nothing ? false : evidence.correction_stable),
            cross_tier_residual_disagreement=(
                evidence === nothing ? nothing : string(evidence.cross_tier_residual_disagreement)
            ),
            cross_tier_residual_tolerance=(
                evidence === nothing ? nothing : string(evidence.cross_tier_residual_tolerance)
            ),
            cross_tier_jacobian_disagreement=(
                evidence === nothing ? nothing : string(evidence.cross_tier_jacobian_disagreement)
            ),
            cross_tier_jacobian_tolerance=(
                evidence === nothing ? nothing : string(evidence.cross_tier_jacobian_tolerance)
            ),
            cross_tier_correction_disagreement=(
                evidence === nothing ? nothing : string(evidence.cross_tier_correction_disagreement)
            ),
            cross_tier_correction_tolerance=(
                evidence === nothing ? nothing : string(evidence.cross_tier_correction_tolerance)
            ),
        ),
    )
end

function _merge_precision_counts!(destination, source)
    for (tier, count) in source
        destination[tier] = get(destination, tier, 0) + count
    end
    return destination
end

function run_combined_arm(
    fixture,
    prefilter;
    endpoint_ordinal::Integer=1,
    observe_callback=(precision_bits) -> nothing,
)
    weak = run_weak_arm(
        fixture,
        prefilter;
        lane=:weak,
        endpoint_ordinal,
        maximum_rescue_work=ADAPT.FORMAL_WEIGHTED_WORK_CAP,
        observe_callback,
    )
    counts = copy(weak.requested_precision_counts)
    used_work = weak.rescue_weighted_work
    used_callbacks = weak.rescue_callbacks
    adaptive_attempts = 0
    adaptive_attempt_observables = Any[]
    local_prefilter_observables = Any[]
    last_reason = weak.reason
    selected_points = Tuple[]
    for bracket in weak.bracket_seeds
        remaining = ADAPT.FORMAL_WEIGHTED_WORK_CAP - used_work
        required_prefilter = 1 + 4length(bracket.normalized_point)
        remaining >= required_prefilter || begin
            last_reason = :combined_prefilter_budget_insufficient
            break
        end
        local_prefilter = acquire_shared_prefilter(
            fixture,
            bracket.normalized_point;
            observe_callback,
        )
        local_prefilter.callbacks == required_prefilter || error(
            "combined shared-prefilter work drifted",
        )
        counts["float64"] = get(counts, "float64", 0) + local_prefilter.callbacks
        used_work += local_prefilter.callbacks
        used_callbacks += local_prefilter.callbacks
        push!(local_prefilter_observables, (;
            status=String(local_prefilter.status),
            reason=String(local_prefilter.reason),
            callbacks=local_prefilter.callbacks,
            numerical_rank=local_prefilter.numerical_rank,
            condition_class=String(local_prefilter.condition_class),
            model_agreement=local_prefilter.model_agreement,
        ))
        local_prefilter.status == :ready || begin
            last_reason = local_prefilter.reason
            continue
        end
        adaptive_attempts += 1
        adaptive = run_adaptive_arm(
            fixture,
            local_prefilter;
            maximum_rescue_work=ADAPT.FORMAL_WEIGHTED_WORK_CAP - used_work,
            observe_callback,
        )
        push!(adaptive_attempt_observables, adaptive.observables)
        _merge_precision_counts!(counts, adaptive.requested_precision_counts)
        used_work += adaptive.rescue_weighted_work
        used_callbacks += adaptive.rescue_callbacks
        used_work <= ADAPT.FORMAL_WEIGHTED_WORK_CAP || error("combined cap exceeded")
        last_reason = adaptive.reason
        if adaptive.status == :seed_ready
            append!(selected_points, adaptive.point_seeds)
            break
        end
    end
    status = isempty(selected_points) ? :unknown : :seed_ready
    return ArmTrialResult(
        WEAK_ADAPTIVE_ARM,
        status,
        isempty(selected_points) ? last_reason : :none,
        used_callbacks,
        used_callbacks,
        used_work,
        weak.activation || adaptive_attempts > 0,
        length(selected_points),
        selected_points,
        WEAK.RefinementSeed[],
        counts,
        (;
            strict_bracket_detected=weak.activation,
            adaptive_attempt_started=adaptive_attempts > 0,
            adaptive_attempt_count=adaptive_attempts,
            cross_tier_confirmed=!isempty(selected_points),
            confirmation_site="same_source_model",
            same_source_model_confirmed=!isempty(selected_points),
            refined_endpoint_high_precision_confirmed=false,
            adaptive_attempt_observables=Tuple(adaptive_attempt_observables),
            local_prefilter_observables=Tuple(local_prefilter_observables),
        ),
    )
end

function run_reference_arm(
    fixture,
    prefilter;
    observe_callback=(precision_bits) -> nothing,
)
    anchor = prefilter.anchor
    anchor isa WEAK.RescueEvaluation || return ArmTrialResult(
        REFERENCE_ARM,
        :unknown,
        :shared_prefilter_unavailable,
        0,
        0,
        0,
        false,
        0,
        Tuple[],
        WEAK.RefinementSeed[],
        Dict{String,Int}(),
        (;),
    )
    problem = REF.RankRescueProblem(
        length(prefilter.endpoint),
        length(anchor.residual),
        :C2,
        fixture.box.lower,
        fixture.box.upper,
        (x, bits) -> begin
            observe_callback(bits)
            sample = _reference_sample(fixture, x, bits)
            sample === nothing && error("malformed arbitrary-precision fixture callback")
            sample
        end,
    )
    seed = REF.RankRescueSeed(
        prefilter.endpoint,
        prefilter.numerical_rank,
        _routed_condition(prefilter),
        prefilter.model_agreement,
        _semantic_valid(anchor),
        _semantic_signature(anchor),
    )
    result = REF.rescue_rank_precision(
        problem,
        seed;
        options=REF.RankRescueOptions(
            maximum_callbacks=600,
            maximum_weighted_oracle_work=600,
        ),
    )
    point_seeds = result.status == :seed_ready ?
                  Tuple[Tuple(result.evidence.refined_coordinates)] : Tuple[]
    work = result.work
    return ArmTrialResult(
        REFERENCE_ARM,
        result.status,
        result.reason,
        work.callbacks,
        work.raw_oracle_work,
        work.precision_weighted_oracle_work,
        work.factorization_count > 0,
        length(point_seeds),
        point_seeds,
        WEAK.RefinementSeed[],
        Dict("512" => work.callbacks),
        (;
            precision_bits=work.precision_bits,
            precision_weight=work.precision_weight,
            factorization_count=work.factorization_count,
            iterations=work.iteration_count,
            formal_equal_work_authority=REF.FORMAL_EQUAL_WORK_PROMOTION_AUTHORITY,
        ),
    )
end

function _fixed_isotropic_direction(dimension::Int, endpoint_ordinal::Int)
    seed = xor(
        0x4558504c4f43414c,
        UInt64(dimension) << 32,
        UInt64(endpoint_ordinal),
    )
    generator = Random.Xoshiro(seed)
    direction = randn(generator, dimension)
    magnitude = norm(direction, 2)
    isfinite(magnitude) && magnitude > 0 || error("isotropic control produced zero")
    return direction ./ magnitude
end

function _empty_weak_arm(arm::String, reason::Symbol, lane::Symbol)
    return ArmTrialResult(
        arm,
        :unknown,
        reason,
        0,
        0,
        0,
        false,
        0,
        Tuple[],
        WEAK.RefinementSeed[],
        Dict{String,Int}(),
        (;
            lane,
            required_callbacks=2length(WEAK.BRACKET_RADII),
            rank_evidence_activated=false,
            strict_bracket_detected=false,
            detected_bracket_count=0,
            diagnostic_reason=reason,
            probe_reason=reason,
        ),
    )
end

function run_weak_arm(
    fixture,
    prefilter;
    lane::Symbol=:weak,
    endpoint_ordinal::Integer=1,
    maximum_rescue_work::Integer=600,
    observe_callback=(precision_bits) -> nothing,
)
    arm = lane == :weak ? WEAK_ARM :
          lane == :isotropic ? ISOTROPIC_ARM :
          lane == :no_bracket ? WEAK_NO_EMIT_ARM :
          throw(ArgumentError("unsupported weak arm lane"))
    anchor = prefilter.anchor
    anchor isa WEAK.RescueEvaluation || return _empty_weak_arm(
        arm,
        :shared_anchor_unavailable,
        lane,
    )
    context = prefilter.weak_probe_context
    context isa SharedWeakProbeContext || return _empty_weak_arm(
        arm,
        :shared_weak_probe_context_unavailable,
        lane,
    )
    fixture.evaluate_float64 === context.evaluate_float64 || return _empty_weak_arm(
        arm,
        :shared_weak_probe_source_mismatch,
        lane,
    )
    counter = Ref(0)
    evaluator = point -> begin
        raw = context.evaluate_float64(point)
        observation = _weak_observation(raw)
        observation isa WEAK.RescueEvaluation || error("malformed Float64 fixture callback")
        observation
    end
    direction = lane == :isotropic ?
                _fixed_isotropic_direction(length(prefilter.endpoint), Int(endpoint_ordinal)) :
                nothing
    charge_callback = () -> begin
        counter[] += 1
        observe_callback(53)
        nothing
    end
    result = WEAK._symmetric_bracket_probe_authoritative(
        evaluator,
        context.box,
        context.endpoint,
        anchor,
        context.diagnostic;
        remaining_callbacks=Int(maximum_rescue_work),
        lane,
        isotropic_direction=direction,
        charge_callback,
    )
    counter[] == result.callback_count || error("weak callback ledger mismatch")
    detected = result.detected_bracket_count
    return ArmTrialResult(
        arm,
        result.status,
        result.reason,
        result.callback_count,
        result.callback_count,
        result.callback_count,
        detected > 0,
        length(result.seeds),
        Tuple[],
        copy(result.seeds),
        Dict("float64" => result.callback_count),
        (;
            lane,
            required_callbacks=2length(WEAK.BRACKET_RADII),
            rank_evidence_activated=(
                context.diagnostic.status == :applicable
            ),
            strict_bracket_detected=detected > 0,
            detected_bracket_count=detected,
            diagnostic_reason=context.diagnostic.reason,
            probe_reason=result.reason,
        ),
    )
end

function _exact_bigfloat(value)
    return BigFloat(numerator(value)) / BigFloat(denominator(value))
end

function _exact_bigfloat_vector(values)
    return BigFloat[_exact_bigfloat(value) for value in values]
end

function assess_point_seeds(truth, points; tolerance::Real=ROOT_MATCH_TOLERANCE)
    matches = Int[]
    supported = 0
    setprecision(BigFloat, 512) do
        exact_roots = [_exact_bigfloat_vector(root) for root in truth.isolated_roots]
        for point in points
            candidate = try
                BigFloat[BigFloat(value) for value in point]
            catch
                continue
            end
            index = findfirst(root -> begin
                length(root) == length(candidate) || return false
                norm(candidate - root, Inf) <= BigFloat(tolerance)
            end, exact_roots)
            index === nothing && continue
            supported += 1
            push!(matches, index)
        end
    end
    unique!(sort!(matches))
    emitted = length(points)
    return AssessorMatch(emitted, supported, matches, emitted - supported)
end

function assess_bracket_seeds(truth, endpoint, seeds)
    # Brackets are only mechanism/seed evidence on the preregistered clustered
    # simple-root stratum.  They never establish an answer or target recall.
    truth.classification == :clustered_simple_roots || return AssessorMatch(
        length(seeds),
        0,
        Int[],
        length(seeds),
    )
    point = try
        Float64[endpoint...]
    catch
        return AssessorMatch(length(seeds), 0, Int[], length(seeds))
    end
    matches = Int[]
    supported = 0
    for seed in seeds
        direction = Float64[seed.probe_direction...]
        seed_point = Float64[seed.normalized_point...]
        length(direction) == length(point) == length(seed_point) || continue
        all(isfinite, direction) && all(isfinite, seed_point) || continue
        magnitude = norm(direction, 2)
        isfinite(magnitude) && abs(magnitude - 1.0) <= 128eps(Float64) || continue
        lower = min(Float64(seed.lower_parameter), Float64(seed.upper_parameter))
        upper = max(Float64(seed.lower_parameter), Float64(seed.upper_parameter))
        isfinite(lower) && isfinite(upper) && lower < upper || continue
        Float64(seed.lower_parameter) == lower || continue
        Float64(seed.upper_parameter) == upper || continue
        lower_projected = Float64(seed.lower_projected_residual)
        upper_projected = Float64(seed.upper_projected_residual)
        isfinite(lower_projected) && isfinite(upper_projected) || continue
        lower_projected != 0.0 && upper_projected != 0.0 || continue
        signbit(lower_projected) != signbit(upper_projected) || continue
        radius = max(abs(lower), abs(upper))
        radius <= maximum(WEAK.BRACKET_RADII) || continue
        midpoint = (lower + upper) / 2
        expected_point = point .+ midpoint .* direction
        point_tolerance = 128eps(Float64) * (
            norm(expected_point, 2) + norm(seed_point, 2) + abs(midpoint)
        )
        norm(seed_point - expected_point, 2) <= point_tolerance || continue

        seed_matches = Int[]
        setprecision(BigFloat, 512) do
            big_point = BigFloat[BigFloat(value) for value in point]
            big_direction = BigFloat[BigFloat(value) for value in direction]
            denominator = dot(big_direction, big_direction)
            denominator > 0 || return
            big_lower = BigFloat(lower)
            big_upper = BigFloat(upper)
            for (index, exact_root) in enumerate(truth.isolated_roots)
                root = _exact_bigfloat_vector(exact_root)
                length(root) == length(big_point) || continue
                offset = root - big_point
                parameter = dot(offset, big_direction) / denominator
                perpendicular = norm(offset - parameter .* big_direction, 2)
                curvature_tolerance = max(
                    BigFloat(ROOT_MATCH_TOLERANCE),
                    BigFloat(BRACKET_CURVATURE_MULTIPLIER) * abs(parameter)^2,
                )
                big_lower - BigFloat(ROOT_MATCH_TOLERANCE) <= parameter <=
                    big_upper + BigFloat(ROOT_MATCH_TOLERANCE) || continue
                perpendicular <= curvature_tolerance || continue
                push!(seed_matches, index)
            end
        end
        isempty(seed_matches) && continue
        supported += 1
        append!(matches, seed_matches)
    end
    unique!(sort!(matches))
    emitted = length(seeds)
    return AssessorMatch(emitted, supported, matches, emitted - supported)
end

"""
Truth-blind, orthogonally invariant Float64 evidence shared by all T0 arms.

This is measured once per endpoint.  It is not an answer, root proof, or
candidate-specific rescue.  Singular values, not CPQR diagonals, are routing
authority.  Every threshold is homogeneous in the residual/Jacobian scale.
"""
struct SharedPrefilterResult
    status::Symbol
    reason::Symbol
    endpoint::Vector{Float64}
    anchor::Any
    weak_probe_context::Union{Nothing,SharedWeakProbeContext}
    callbacks::Int
    required_callbacks::Int
    coarse_jacobian::Matrix{Float64}
    fine_jacobian::Matrix{Float64}
    coarse_singular_values::Vector{Float64}
    fine_singular_values::Vector{Float64}
    coarse_rank::Int
    fine_rank::Int
    numerical_rank::Int
    condition_estimate::Float64
    condition_lower_bound::Float64
    condition_upper_bound::Float64
    condition_class::Symbol
    uncertainty::Float64
    relative_model_disagreement::Float64
    model_agreement::Bool
end

function _empty_prefilter(
    reason::Symbol,
    endpoint,
    callbacks::Integer,
    required::Integer;
    anchor=nothing,
    weak_probe_context=nothing,
    coarse=zeros(Float64, 0, 0),
    fine=zeros(Float64, 0, 0),
    coarse_values=Float64[],
    fine_values=Float64[],
    coarse_rank::Integer=0,
    fine_rank::Integer=0,
    uncertainty::Real=NaN,
    relative_disagreement::Real=NaN,
)
    return SharedPrefilterResult(
        :unknown,
        reason,
        Float64[endpoint...],
        anchor,
        weak_probe_context,
        Int(callbacks),
        Int(required),
        Matrix{Float64}(coarse),
        Matrix{Float64}(fine),
        Float64[coarse_values...],
        Float64[fine_values...],
        Int(coarse_rank),
        Int(fine_rank),
        min(Int(coarse_rank), Int(fine_rank)),
        Inf,
        Inf,
        Inf,
        :unknown,
        Float64(uncertainty),
        Float64(relative_disagreement),
        false,
    )
end

function _weak_observation(evaluation)
    return try
        WEAK.RescueEvaluation(
            evaluation.residual;
            branch_identity=evaluation.branch_identity,
            guard_identity=evaluation.guard_identity,
            domain_identity=evaluation.domain_identity,
            branch_margin=evaluation.branch_margin,
            guard_margin=evaluation.guard_margin,
            domain_margin=evaluation.domain_margin,
            valid=evaluation.valid,
        )
    catch error
        error isa InterruptException && rethrow()
        nothing
    end
end

function _evaluate_float64(fixture, point)
    raw = try
        fixture.evaluate_float64(copy(point))
    catch error
        error isa InterruptException && rethrow()
        return nothing, :evaluation_failed
    end
    observation = _weak_observation(raw)
    observation isa WEAK.RescueEvaluation || return nothing, :malformed_evaluation
    return observation, :none
end

function _inside_open_box(box, point)
    length(point) == length(box.lower) || return false
    return all(index -> begin
        value = point[index]
        isfinite(value) && box.lower[index] < value < box.upper[index]
    end, eachindex(point))
end

function _valid_observation(observation, residual_dimension)
    observation isa WEAK.RescueEvaluation || return false
    observation.valid || return false
    length(observation.residual) == residual_dimension || return false
    all(isfinite, observation.residual) || return false
    return all(value -> isfinite(value) && value > 0.0, (
        observation.branch_margin,
        observation.guard_margin,
        observation.domain_margin,
    ))
end

function _same_semantics(observation, anchor)
    return try
        isequal(observation.branch_identity, anchor.branch_identity) &&
        isequal(observation.guard_identity, anchor.guard_identity) &&
        isequal(observation.domain_identity, anchor.domain_identity)
    catch error
        error isa InterruptException && rethrow()
        false
    end
end

function _stable_spectral_rank(values, threshold)
    all(isfinite, values) && isfinite(threshold) && threshold >= 0 || return 0
    return count(value -> value > threshold, values)
end

function _shared_fd_stencil(box, point)
    stencil = Vector{Vector{Float64}}()
    for radius in (SHARED_FD_STEP, SHARED_FD_STEP / 2), column in eachindex(point), sign in (1, -1)
        sample = copy(point)
        sample[column] += sign * radius
        _inside_open_box(box, sample) || return nothing
        push!(stencil, sample)
    end
    return stencil
end

function _drain_shared_stencil!(fixture, stencil, observe_callback)
    for sample in stencil
        observe_callback(53)
        _evaluate_float64(fixture, sample)
    end
    return length(stencil)
end

"""
Acquire the shared complete `anchor + h/h2 +/-` prefilter exactly once.

The weak-probe context is bound to the callback function that produced the
Jacobian pair.  Weak/isotropic arms may reuse that opaque evidence but cannot
inject a diagnostic acquired from another evaluator.  The routine evaluates
the complete preregistered stencil even after an ordinary callback/semantic
failure, so paired shared work remains exact.
"""
function acquire_shared_prefilter(
    fixture,
    endpoint::AbstractVector;
    observe_callback=(precision_bits) -> nothing,
)
    point = try
        Float64[endpoint...]
    catch
        return _empty_prefilter(:invalid_endpoint, Float64[], 0, 0)
    end
    n = length(point)
    required = n >= 2 ? 1 + 4n : 0
    n >= 2 || return _empty_prefilter(:dimension_below_two, point, 0, required)
    length(fixture.box.lower) == n || return _empty_prefilter(
        :box_dimension_mismatch,
        point,
        0,
        required,
    )
    _inside_open_box(fixture.box, point) || return _empty_prefilter(
        :endpoint_not_strictly_inside_box,
        point,
        0,
        required,
    )

    stencil = _shared_fd_stencil(fixture.box, point)
    stencil === nothing && return _empty_prefilter(
        :stencil_outside_box,
        point,
        0,
        required,
    )
    length(stencil) == 4n || error("shared prefilter stencil drifted")

    observe_callback(53)
    anchor, anchor_reason = _evaluate_float64(fixture, point)
    if !(anchor isa WEAK.RescueEvaluation)
        _drain_shared_stencil!(fixture, stencil, observe_callback)
        return _empty_prefilter(anchor_reason, point, required, required)
    end
    residual_dimension = length(anchor.residual)
    if residual_dimension != n || !_valid_observation(anchor, residual_dimension)
        _drain_shared_stencil!(fixture, stencil, observe_callback)
        reason = residual_dimension == n ? :invalid_observation :
                 :square_residual_dimension_required
        return _empty_prefilter(reason, point, required, required; anchor)
    end

    evaluate_float64 = fixture.evaluate_float64
    evaluator = sample -> begin
        raw = evaluate_float64(sample)
        observation = _weak_observation(raw)
        observation isa WEAK.RescueEvaluation || error(
            "malformed Float64 fixture callback",
        )
        observation
    end
    observed_stencil_callbacks = Ref(0)
    diagnostic = WEAK.acquire_cpqr_rank_evidence(
        evaluator,
        WEAK.NormalizedBox(fixture.box.lower, fixture.box.upper),
        point,
        anchor;
        remaining_callbacks=4n,
        charge_callback=() -> begin
            observed_stencil_callbacks[] += 1
            observe_callback(53)
            nothing
        end,
    )
    diagnostic.callback_count in (0, 4n) || error(
        "shared diagnostic returned a partial stencil",
    )
    if diagnostic.callback_count == 0
        _drain_shared_stencil!(fixture, stencil, observe_callback)
        return _empty_prefilter(
            diagnostic.reason,
            point,
            required,
            required;
            anchor,
        )
    end
    observed_stencil_callbacks[] == 4n || error("shared physical callback drifted")
    coarse = diagnostic.coarse_jacobian
    fine = diagnostic.fine_jacobian
    size(coarse) == (n, n) && size(fine) == (n, n) || return _empty_prefilter(
        diagnostic.reason == :cpqr_branch_or_guard_changed ?
        :semantic_identity_changed : diagnostic.reason,
        point,
        required,
        required;
        anchor,
        coarse,
        fine,
    )
    all(isfinite, coarse) && all(isfinite, fine) || return _empty_prefilter(
        :nonfinite_jacobian,
        point,
        required,
        required;
        anchor,
        coarse,
        fine,
    )

    coarse_values = Float64[svdvals(coarse)...]
    fine_values = Float64[svdvals(fine)...]
    spectral_scale = max(opnorm(coarse, 2), opnorm(fine, 2))
    model_delta = opnorm(coarse - fine, 2)
    roundoff = SHARED_ROUNDOFF_MULTIPLIER * n * eps(Float64) * spectral_scale
    uncertainty = model_delta + roundoff
    threshold = SHARED_RANK_UNCERTAINTY_MULTIPLIER * uncertainty
    coarse_rank = _stable_spectral_rank(coarse_values, threshold)
    fine_rank = _stable_spectral_rank(fine_values, threshold)
    relative_disagreement = spectral_scale > 0 ? model_delta / spectral_scale : Inf
    model_agreement = coarse_rank == fine_rank &&
                      isfinite(relative_disagreement) &&
                      relative_disagreement <= SHARED_MODEL_RELATIVE_DISAGREEMENT_MAX
    rank = min(coarse_rank, fine_rank)
    condition_lower = Inf
    condition_upper = Inf
    condition = Inf
    condition_class = :unknown
    if model_agreement && rank == n && fine_values[end] > 0
        numerator_lower = max(0.0, fine_values[1] - uncertainty)
        numerator_upper = fine_values[1] + uncertainty
        denominator_lower = fine_values[end] - uncertainty
        denominator_upper = fine_values[end] + uncertainty
        condition_lower = denominator_upper > 0 ? numerator_lower / denominator_upper : Inf
        condition_upper = denominator_lower > 0 ? numerator_upper / denominator_lower : Inf
        # Routing uses the conservative lower bound.  A public condition trigger
        # inside the uncertainty interval therefore cannot flip merely because
        # an equivalent representation perturbs the raw quotient.
        condition = condition_lower
        grey_lower = CONDITION_TRIGGER * (1 - CONDITION_GREY_RELATIVE_WIDTH)
        grey_upper = CONDITION_TRIGGER * (1 + CONDITION_GREY_RELATIVE_WIDTH)
        condition_class = condition_lower >= grey_upper ? :above_trigger :
                          condition_upper <= grey_lower ? :below_trigger :
                          :uncertain
    elseif model_agreement && rank < n
        condition_class = :rank_deficient
    end
    weak_probe_context = SharedWeakProbeContext(
        evaluate_float64,
        WEAK.NormalizedBox(fixture.box.lower, fixture.box.upper),
        copy(point),
        anchor,
        diagnostic,
    )
    return SharedPrefilterResult(
        model_agreement ? :ready : :unknown,
        model_agreement ? :none : :h_h2_model_disagreement,
        point,
        anchor,
        weak_probe_context,
        required,
        required,
        coarse,
        fine,
        coarse_values,
        fine_values,
        coarse_rank,
        fine_rank,
        rank,
        condition,
        condition_lower,
        condition_upper,
        condition_class,
        uncertainty,
        relative_disagreement,
        model_agreement,
    )
end

"""Return 63 root-owned records: base/signed/orthogonal for each base fixture."""
function materialize_t0_cases()
    result = NamedTuple[]
    for (class_index, base) in enumerate(FIXTURES.rescue_fixture_corpus())
        replicas = (
            (kind=:base, record=base),
            (kind=:signed_permutation, record=FIXTURES.signed_permutation_replica(base)),
            (kind=:orthogonal, record=FIXTURES.orthogonal_replica(base)),
        )
        for replica in replicas
            push!(result, (;
                class_index,
                replica_kind=replica.kind,
                record=replica.record,
            ))
        end
    end
    length(result) == 63 || error("T0 representation corpus drifted")
    return result
end

end
