module ECPAcceptanceEmitter

export ECPArm,
    ECP_V1,
    ECP_LB_FULL,
    ECPStatus,
    ECP_COMPLETE,
    ECP_FALLBACK_REQUIRED,
    ECP_INAPPLICABLE_RAW_MATRIX,
    ECPObservation,
    ECPProposal,
    ECPFallbackRequest,
    ECPDiagnostics,
    ECPEmitterResult,
    ACCEPTED_SCREEN_CAP,
    RAW_DRAW_CAP,
    EPSILON0,
    TAU_FLOOR,
    REJECTION_GROWTH_C,
    stable_phi,
    acceptance_envelope,
    emit_ecp

@enum ECPArm begin
    ECP_V1
    ECP_LB_FULL
end

@enum ECPStatus begin
    ECP_COMPLETE
    ECP_FALLBACK_REQUIRED
    ECP_INAPPLICABLE_RAW_MATRIX
end

const ACCEPTED_SCREEN_CAP = 48
const RAW_DRAW_CAP = 65_536
const EPSILON0 = 1.0e-2
const TAU_FLOOR = 1.001
const REJECTION_GROWTH_C = 1_000

"""Truth-blind result of one charged canonical screening callback."""
struct ECPObservation
    scaled_residual::Vector{Float64}
    canonical_valid::Bool

    function ECPObservation(residual::AbstractVector, canonical_valid::Bool)
        return new(Float64[residual...], canonical_valid)
    end
end

ECPObservation(residual::AbstractVector; canonical_valid::Bool=true) =
    ECPObservation(residual, canonical_valid)

"""One accepted, evaluated point. Every instance is a later local proposal."""
struct ECPProposal
    accepted_ordinal::Int
    raw_draw_index::Int
    point::Vector{Float64}
    phi::Float64
    reward::Float64
    canonical_valid::Bool
    callback_failed::Bool
    epsilon_used::Float64
    optimistic_envelope::Union{Nothing,Float64}
    best_reward_before::Union{Nothing,Float64}
end

"""A missing accepted-screen slot that the caller must fill with fresh IID."""
struct ECPFallbackRequest
    slot::Int
    source::Symbol
    reason::Symbol
end

"""Capability and work accounting only; no answer, target, family, or Gold facts."""
struct ECPDiagnostics
    arm::ECPArm
    status::ECPStatus
    reason::Symbol
    dimension::Int
    source_columns::Int
    accepted_screen_cap::Int
    raw_draw_cap::Int
    raw_draws_consumed::Int
    accepted_screening_callbacks::Int
    logical_screening_callbacks::Int
    rejected_unscored_draws::Int
    fallback_requests::Int
    invalid_count::Int
    callback_failure_count::Int
    epsilon_initial::Float64
    epsilon_final::Float64
    tau::Union{Nothing,Float64}
    rejection_growth_count::Int
    lower_bound_update_count::Int
    previous_round_h_final::Int
    current_round_h_final::Int
    all_evaluated_proposals_retained::Bool
    screened_evidence_discard_count::Int
    answer_authority::Bool
    target_authority::Bool
    gold_authority::Bool
    completeness_authority::Bool
    external_result_used::Bool
end

struct ECPEmitterResult
    proposals::Vector{ECPProposal}
    fallbacks::Vector{ECPFallbackRequest}
    diagnostics::ECPDiagnostics
end

"""
Stable row-permutation-invariant bounded residual score.

Finite canonical residuals map to `[0, 1)`. Invalid, empty, or nonfinite
observations map to exactly `1`, hence to ECP reward `-1`.
"""
function stable_phi(observation::ECPObservation)
    observation.canonical_valid || return 1.0, false
    residual = observation.scaled_residual
    isempty(residual) && return 1.0, false
    all(isfinite, residual) || return 1.0, false
    magnitudes = sort!(abs.(residual))
    scale = magnitudes[end]
    scale == 0.0 && return 0.0, true
    normalized_squares = sort!((magnitudes ./ scale) .^ 2)
    shape = sqrt(sum(normalized_squares))
    if scale <= inv(shape)
        rho = scale * shape
        return rho / (1.0 + rho), true
    end
    inverse_rho = inv(scale) / shape
    score = 1.0 - inverse_rho / (1.0 + inverse_rho)
    return min(prevfloat(1.0), score), true
end

function _euclidean_distance(left::AbstractVector, right::AbstractVector)
    length(left) == length(right) || throw(DimensionMismatch("point dimensions differ"))
    squares = sort!(Float64[(left[index] - right[index])^2 for index in eachindex(left)])
    return sqrt(sum(squares))
end

"""
Return the official ECP optimistic envelope
`min_i(reward_i + epsilon * ||x - point_i||_2)`.
"""
function acceptance_envelope(
    point::AbstractVector,
    explored_points::AbstractVector{<:AbstractVector},
    rewards::AbstractVector,
    epsilon::Real,
)
    length(explored_points) == length(rewards) && !isempty(rewards) ||
        throw(ArgumentError("a nonempty point/reward archive of equal length is required"))
    epsilon_value = Float64(epsilon)
    isfinite(epsilon_value) && epsilon_value > 0.0 ||
        throw(ArgumentError("epsilon must be finite and positive"))
    values = Float64[
        Float64(rewards[index]) +
        epsilon_value * _euclidean_distance(point, explored_points[index])
        for index in eachindex(rewards)
    ]
    return minimum(values)
end

function _materialize_raw(raw_candidates::AbstractMatrix)
    dimension, columns = size(raw_candidates)
    dimension > 0 || return nothing, :empty_dimension, dimension, columns
    matrix = try
        Matrix{Float64}(raw_candidates)
    catch
        return nothing, :nonconvertible_raw_matrix, dimension, columns
    end
    all(isfinite, matrix) || return nothing, :nonfinite_raw_matrix, dimension, columns
    all(value -> -1.0 <= value <= 1.0, matrix) ||
        return nothing, :outside_normalized_box, dimension, columns
    return matrix, :applicable, dimension, columns
end

function _fallbacks(first_slot::Int, reason::Symbol)
    return ECPFallbackRequest[
        ECPFallbackRequest(slot, :fresh_iid, reason)
        for slot in first_slot:ACCEPTED_SCREEN_CAP
    ]
end

function _inapplicable_result(arm, reason, dimension, columns)
    fallbacks = _fallbacks(1, reason)
    diagnostics = ECPDiagnostics(
        arm,
        ECP_INAPPLICABLE_RAW_MATRIX,
        reason,
        dimension,
        columns,
        ACCEPTED_SCREEN_CAP,
        RAW_DRAW_CAP,
        0,
        0,
        ACCEPTED_SCREEN_CAP,
        0,
        length(fallbacks),
        0,
        0,
        EPSILON0,
        EPSILON0,
        nothing,
        0,
        0,
        1,
        0,
        true,
        0,
        false,
        false,
        false,
        false,
        false,
    )
    return ECPEmitterResult(ECPProposal[], fallbacks, diagnostics)
end

function _screen(screen!::F, point::Vector{Float64}) where {F}
    raw, callback_failed = try
        screen!(copy(point)), false
    catch
        nothing, true
    end
    callback_failed |= !(raw isa ECPObservation)
    observation = raw isa ECPObservation ? raw :
        ECPObservation(Float64[]; canonical_valid=false)
    phi, valid = stable_phi(observation)
    return phi, valid, callback_failed
end

"""
    emit_ecp(screen!, raw_candidates; arm=ECP_LB_FULL)

Apply ECP acceptance to caller-materialized normalized candidates. Columns of
`raw_candidates` are points in `[-1, 1]^d`; this module never draws randomness.
The first raw point is evaluated unconditionally. Later points are evaluated iff

`min_i(reward_i + epsilon * norm(x - x_i)) >= max_i(reward_i)`,

with `reward = -stable_phi`. `ECP_LB_FULL` uses ECPv2's adaptive epsilon lower
bound with full memory (`m=t`), zero projection distortion (`delta=0`), and the
identity Euclidean metric. Rejected raw candidates are neither evaluated nor
returned. Every evaluated point is retained as a proposal. Missing accepted slots
become typed fresh-IID fallback requests; the result has no answer authority.
Paper Algorithm 1's `h_(t+1)-h_t > C` growth check runs before acceptance;
the final previous/current `h` state is recorded in diagnostics.
"""
function emit_ecp(
    screen!::F,
    raw_candidates::AbstractMatrix;
    arm::ECPArm=ECP_LB_FULL,
) where {F}
    raw, reason, dimension, source_columns = _materialize_raw(raw_candidates)
    raw === nothing && return _inapplicable_result(arm, reason, dimension, source_columns)

    tau = max(1.0 + inv(ACCEPTED_SCREEN_CAP * dimension), TAU_FLOOR)
    diameter = 2.0 * sqrt(Float64(dimension))
    epsilon = EPSILON0
    proposals = ECPProposal[]
    explored_points = Vector{Vector{Float64}}()
    rewards = Float64[]
    raw_draws_consumed = 0
    rejected_unscored_draws = 0
    # Algorithm 1 initializes h_1=1 and h_2=0 after evaluating x_1.
    previous_round_h = 1
    current_round_h = 0
    rejection_growth_count = 0
    lower_bound_update_count = 0
    invalid_count = 0
    callback_failure_count = 0
    draw_limit = min(source_columns, RAW_DRAW_CAP)

    for raw_index in 1:draw_limit
        length(proposals) == ACCEPTED_SCREEN_CAP && break
        raw_draws_consumed = raw_index
        point = copy(@view raw[:, raw_index])
        first_evaluation = isempty(proposals)
        if !first_evaluation
            # Paper Algorithm 1, lines 4--7: grow before checking acceptance.
            current_round_h += 1
            if current_round_h - previous_round_h > REJECTION_GROWTH_C
                epsilon *= tau
                rejection_growth_count += 1
                current_round_h = 0
            end
        end
        epsilon_used = epsilon
        envelope = first_evaluation ? nothing :
            acceptance_envelope(point, explored_points, rewards, epsilon_used)
        best_before = first_evaluation ? nothing : maximum(rewards)
        accepted = first_evaluation || something(envelope) >= something(best_before)
        if !accepted
            rejected_unscored_draws += 1
            continue
        end

        stored_point = copy(point)
        phi, valid, callback_failed = _screen(screen!, point)
        reward = -phi
        push!(proposals, ECPProposal(
            length(proposals) + 1,
            raw_index,
            stored_point,
            phi,
            reward,
            valid,
            callback_failed,
            epsilon_used,
            envelope,
            best_before,
        ))
        push!(explored_points, copy(stored_point))
        push!(rewards, reward)
        invalid_count += !valid
        callback_failure_count += callback_failed

        # Algorithm 1, lines 10--11: the completed round's current h becomes
        # the previous h; then epsilon advances and the next current h is zero.
        if !first_evaluation
            previous_round_h = current_round_h
            current_round_h = 0
            grown = epsilon * tau
            if arm == ECP_LB_FULL
                lower_bound = (maximum(rewards) - minimum(rewards)) / diameter
                if lower_bound > grown
                    epsilon = lower_bound
                    lower_bound_update_count += 1
                else
                    epsilon = grown
                end
            else
                epsilon = grown
            end
        end
    end

    complete = length(proposals) == ACCEPTED_SCREEN_CAP
    fallback_reason = if complete
        :none
    elseif source_columns >= RAW_DRAW_CAP && raw_draws_consumed == RAW_DRAW_CAP
        :raw_draw_cap_reached
    else
        :raw_candidates_exhausted
    end
    fallbacks = complete ? ECPFallbackRequest[] :
        _fallbacks(length(proposals) + 1, fallback_reason)
    status = complete ? ECP_COMPLETE : ECP_FALLBACK_REQUIRED
    diagnostics = ECPDiagnostics(
        arm,
        status,
        fallback_reason,
        dimension,
        source_columns,
        ACCEPTED_SCREEN_CAP,
        RAW_DRAW_CAP,
        raw_draws_consumed,
        length(proposals),
        ACCEPTED_SCREEN_CAP,
        rejected_unscored_draws,
        length(fallbacks),
        invalid_count,
        callback_failure_count,
        EPSILON0,
        epsilon,
        tau,
        rejection_growth_count,
        lower_bound_update_count,
        previous_round_h,
        current_round_h,
        length(proposals) == length(explored_points) == length(rewards),
        0,
        false,
        false,
        false,
        false,
        false,
    )
    return ECPEmitterResult(proposals, fallbacks, diagnostics)
end

end
