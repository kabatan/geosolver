module AdaptivePrecisionRescue

using LinearAlgebra

export ADAPTED_NAME,
       FORMAL_WEIGHTED_WORK_CAP,
       PRECISION_TIERS,
       REFERENCE_ADAPTED_DIFFERENCES,
       ACTIVATION_OBSERVABLES,
       TYPED_BREAK_CONDITIONS,
       AdaptiveRescueOptions,
       AdaptiveRescueProblem,
       AdaptiveRescueSample,
       AdaptiveSemanticState,
       AdaptiveRescueSeed,
       AdaptivePrecisionWork,
       AdaptiveRefinementSeedEvidence,
       AdaptivePrecisionResult,
       rescue_adaptive_precision

const ADAPTED_NAME = "GEOTARGET-ADAPTED-128-256-512-CPQR"
const FORMAL_WEIGHTED_WORK_CAP = 600
const PRECISION_TIERS = (128, 256, 512)
const CONDITION_TRIGGER = 1.0e8
const _METHOD = "EXP-LOCAL-015-$ADAPTED_NAME"

# Causal-conformance contract.  These are mechanism facts, not performance
# outcomes.  In particular, ADAPTED changes both the precision schedule and the
# derivative stencil; a differential result must not attribute their combined
# effect to precision scheduling alone.
const REFERENCE_ADAPTED_DIFFERENCES = (
    reference_precision_route="fixed 512 bits",
    adapted_precision_route="public Float64 rank/condition selects 128 or 256; next tier confirms",
    reference_stencil="five-point h and h/2; 1+8n callbacks before a Newton step",
    adapted_stencil="central two-point h and h/2; 1+4n callbacks per tier",
    adapted_rank_authority="normalized one-sided Jacobi singular spectrum and homogeneous h/h2 uncertainty",
    adapted_confirmation_site="next tier confirms the same source model before Newton; it does not replay the refined endpoint",
    reference_d8_formal_work="650 weighted units before a Newton step",
    adapted_d8_longest_route="599 weighted units for 128 diagnostic, 256 step, 512 confirmation",
    common_answer_authority="neither mechanism emits an answer; production 512/768 replay is mandatory",
)

const ACTIVATION_OBSERVABLES = (
    :selected_precision_bits,
    :confirmation_precision_bits,
    :precision_path,
    :calls_by_precision,
    :tier_count,
    :newton_steps,
    :source_residual_linf,
    :refined_residual_linf,
    :selected_numerical_rank,
    :confirmation_numerical_rank,
    :cross_tier_residual_disagreement,
    :cross_tier_residual_tolerance,
    :cross_tier_jacobian_disagreement,
    :cross_tier_jacobian_tolerance,
    :cross_tier_correction_disagreement,
    :cross_tier_correction_tolerance,
    :rank_stable,
    :correction_stable,
)

const TYPED_BREAK_CONDITIONS = (
    :dimension_mismatch,
    :invalid_prefilter_rank,
    :c2_capability_missing,
    :finite_box_required,
    :underdetermined_manifold,
    :prefilter_semantics_invalid,
    :prefilter_semantic_contract_invalid,
    :prefilter_semantic_margin_invalid,
    :model_disagreement,
    :condition_trigger_not_met,
    :complete_route_budget_insufficient,
    :complete_stencil_budget_insufficient,
    :budget_exhausted,
    :outside_bounds,
    :callback_failed,
    :callback_contract_failed,
    :nonfinite_callback,
    :precision_downgrade,
    :semantics_invalid,
    :branch_identity_failed,
    :semantic_identity_failed,
    :semantic_margin_failed,
    :nonfinite_jacobian,
    :rank_unstable,
    :stationary_nonroot_or_singular,
    :rank_deficient_unisolated,
    :correction_unstable,
    :factorization_failed,
    :linear_solve_failed,
    :escalation_route_budget_insufficient,
    :confirmation_route_budget_insufficient,
    :newton_step_budget_insufficient,
    :newton_step_not_residual_decreasing,
    :confirmation_tier_unavailable,
    :cross_tier_condition_unresolved,
    :cross_tier_model_disagreement,
)

_precision_weight(bits::Integer) = cld(Int(bits), 53)

"""
Opaque semantic identity plus public branch/strict guard/domain margins.

Identity values are never inspected or ordered.  Margin validation and all
identity comparisons happen fail-closed inside the charged callback boundary.
"""
struct AdaptiveSemanticState{B,BM,G,D,GM,DM}
    branch_identity::B
    branch_margin::BM
    guard_identities::G
    guard_margins::GM
    domain_identities::D
    domain_margins::DM

    function AdaptiveSemanticState(
        branch_identity::B,
        branch_margin::BM,
        guard_identities::G,
        guard_margins::GM,
        domain_identities::D,
        domain_margins::DM,
    ) where {B,BM,G,D,GM,DM}
        return new{B,BM,G,D,GM,DM}(
            branch_identity,
            branch_margin,
            guard_identities,
            guard_margins,
            domain_identities,
            domain_margins,
        )
    end
end

AdaptiveSemanticState(branch_identity) =
    AdaptiveSemanticState(branch_identity, 1, (), (), (), ())

# Compatibility constructor for pre-branch-margin experiment fixtures.  The
# formal EXP-LOCAL-015 adapter uses the six-argument form and supplies the public
# branch margin explicitly.
AdaptiveSemanticState(
    branch_identity,
    guard_identities,
    guard_margins,
    domain_identities,
    domain_margins,
) = AdaptiveSemanticState(
    branch_identity,
    1,
    guard_identities,
    guard_margins,
    domain_identities,
    domain_margins,
)

"""One canonical C2 observation with explicit semantic state."""
struct AdaptiveRescueSample{R,S<:AdaptiveSemanticState}
    residual::R
    semantics_valid::Bool
    semantic_state::S
end

AdaptiveRescueSample(residual, semantics_valid::Bool, branch_identity) =
    AdaptiveRescueSample(
        residual,
        semantics_valid,
        branch_identity isa AdaptiveSemanticState ?
        branch_identity : AdaptiveSemanticState(branch_identity),
    )

"""
Truth-blind experiment input.

`evaluate(x, bits)` must preserve the requested BigFloat precision.  Every call,
including a failed one, costs `callback_cost * ceil(bits/53)` weighted units.
"""
struct AdaptiveRescueProblem{F}
    dimension::Int
    residual_dimension::Int
    capability::Symbol
    lower::Tuple
    upper::Tuple
    callback_cost::Int
    evaluate::F

    function AdaptiveRescueProblem(
        dimension::Integer,
        residual_dimension::Integer,
        capability::Symbol,
        lower,
        upper,
        evaluate::F;
        callback_cost::Integer=1,
    ) where {F}
        dimension > 0 || throw(ArgumentError("dimension must be positive"))
        residual_dimension > 0 || throw(
            ArgumentError("residual_dimension must be positive"),
        )
        length(lower) == dimension || throw(DimensionMismatch("lower bound count"))
        length(upper) == dimension || throw(DimensionMismatch("upper bound count"))
        callback_cost > 0 || throw(ArgumentError("callback_cost must be positive"))
        return new{F}(
            Int(dimension),
            Int(residual_dimension),
            capability,
            Tuple(lower),
            Tuple(upper),
            Int(callback_cost),
            evaluate,
        )
    end
end

"""
Float64 pre-filter evidence used to choose the first precision tier.

No case, family, plugin, primitive or Gold identifier is accepted.  A deficient
Float64 rank starts at 256 bits; a full-rank condition trigger starts at 128.
"""
struct AdaptiveRescueSeed{S<:AdaptiveSemanticState}
    coordinates::Tuple
    numerical_rank::Int
    condition_estimate::Float64
    model_agreement::Bool
    semantics_valid::Bool
    semantic_state::S

    function AdaptiveRescueSeed(
        coordinates,
        numerical_rank::Integer,
        condition_estimate::Real,
        model_agreement::Bool,
        semantics_valid::Bool,
        semantic_state,
    )
        frozen = Tuple(Float64(value) for value in coordinates)
        all(isfinite, frozen) || throw(ArgumentError("seed coordinates must be finite"))
        numerical_rank >= 0 || throw(ArgumentError("numerical rank cannot be negative"))
        condition = Float64(condition_estimate)
        condition >= 0 && (isfinite(condition) || isinf(condition)) || throw(
            ArgumentError("condition estimate must be nonnegative or infinite"),
        )
        frozen_semantics = semantic_state isa AdaptiveSemanticState ?
                           semantic_state : AdaptiveSemanticState(semantic_state)
        return new{typeof(frozen_semantics)}(
            frozen,
            Int(numerical_rank),
            condition,
            model_agreement,
            semantics_valid,
            frozen_semantics,
        )
    end
end

"""Formal cap may be lowered only to exercise typed budget insufficiency."""
struct AdaptiveRescueOptions
    maximum_weighted_oracle_work::Int
    maximum_callbacks::Int

    function AdaptiveRescueOptions(
        ;
        maximum_weighted_oracle_work::Integer=FORMAL_WEIGHTED_WORK_CAP,
        maximum_callbacks::Integer=FORMAL_WEIGHTED_WORK_CAP,
    )
        0 < maximum_weighted_oracle_work <= FORMAL_WEIGHTED_WORK_CAP || throw(
            ArgumentError("weighted cap must lie in 1:600; it may never be relaxed"),
        )
        maximum_callbacks > 0 || throw(
            ArgumentError("maximum_callbacks must be positive"),
        )
        return new(Int(maximum_weighted_oracle_work), Int(maximum_callbacks))
    end
end

struct AdaptivePrecisionWork
    callbacks::Int
    raw_oracle_work::Int
    precision_weighted_oracle_work::Int
    calls_by_precision::Tuple
    factorization_count::Int
    tier_count::Int
    newton_steps::Int
end

"""
Candidate seed evidence, never an answer or certificate.

The existing production 512/768-bit validation remains the only answer
authority.  `refined_coordinates` were actually evaluated after a
branch/semantics-preserving residual-decreasing Newton step.  The higher-tier
model is confirmed at `source_coordinates`, not at the refined endpoint.
"""
struct AdaptiveRefinementSeedEvidence{S<:AdaptiveSemanticState}
    method::String
    source_coordinates::Tuple
    refined_coordinates::Tuple
    selected_precision_bits::Int
    confirmation_precision_bits::Int
    precision_path::Tuple
    source_residual_linf::BigFloat
    refined_residual_linf::BigFloat
    selected_numerical_rank::Int
    confirmation_numerical_rank::Int
    selected_condition_estimate::BigFloat
    confirmation_condition_estimate::BigFloat
    confirmation_correction_linf::BigFloat
    confirmation_correction_disagreement::BigFloat
    cross_tier_residual_disagreement::BigFloat
    cross_tier_residual_tolerance::BigFloat
    cross_tier_jacobian_disagreement::BigFloat
    cross_tier_jacobian_tolerance::BigFloat
    cross_tier_correction_disagreement::BigFloat
    cross_tier_correction_tolerance::BigFloat
    rank_stable::Bool
    correction_stable::Bool
    semantic_state::S
end

struct AdaptivePrecisionResult{E}
    status::Symbol
    reason::Symbol
    diagnostic::String
    evidence::E
    work::AdaptivePrecisionWork

    function AdaptivePrecisionResult(
        status::Symbol,
        reason::Symbol,
        diagnostic::AbstractString,
        evidence::E,
        work::AdaptivePrecisionWork,
    ) where {E}
        status in (:seed_ready, :unknown) || throw(
            ArgumentError("status must be seed_ready or unknown"),
        )
        (status == :seed_ready) == (evidence isa AdaptiveRefinementSeedEvidence) || throw(
            ArgumentError("only seed_ready carries refinement evidence"),
        )
        (status == :seed_ready) == (reason == :none) || throw(
            ArgumentError("status and typed reason disagree"),
        )
        return new{E}(status, reason, String(diagnostic), evidence, work)
    end
end

mutable struct _Ledger
    options::AdaptiveRescueOptions
    callback_cost::Int
    callbacks::Int
    raw_oracle_work::Int
    weighted_oracle_work::Int
    calls_by_precision::Dict{Int,Int}
    factorization_count::Int
    tier_count::Int
    newton_steps::Int
    branch_changes::Int
    semantics_failures::Int
end

_Ledger(options, callback_cost) = _Ledger(
    options,
    callback_cost,
    0,
    0,
    0,
    Dict{Int,Int}(),
    0,
    0,
    0,
    0,
    0,
)

function _snapshot(ledger::_Ledger)
    calls = Tuple(
        (precision_bits=bits, callbacks=ledger.calls_by_precision[bits]) for
        bits in sort!(collect(keys(ledger.calls_by_precision)))
    )
    return AdaptivePrecisionWork(
        ledger.callbacks,
        ledger.raw_oracle_work,
        ledger.weighted_oracle_work,
        calls,
        ledger.factorization_count,
        ledger.tier_count,
        ledger.newton_steps,
    )
end

function _unknown(ledger, reason::Symbol, diagnostic::AbstractString)
    return AdaptivePrecisionResult(
        :unknown,
        reason,
        "$ADAPTED_NAME: $diagnostic",
        nothing,
        _snapshot(ledger),
    )
end

function _checked_product(left::Int, right::Int)
    try
        return Base.checked_mul(left, right)
    catch error
        error isa OverflowError || rethrow()
        return typemax(Int)
    end
end

function _route_cost(ledger::_Ledger, calls::Int, bits::Int)
    raw = _checked_product(calls, ledger.callback_cost)
    return _checked_product(raw, _precision_weight(bits))
end

function _can_reserve(ledger::_Ledger, route::Tuple)
    callback_count = sum(first, route; init=0)
    ledger.callbacks <= ledger.options.maximum_callbacks - callback_count || return false
    cost = 0
    for (calls, bits) in route
        increment = _route_cost(ledger, calls, bits)
        increment <= typemax(Int) - cost || return false
        cost += increment
    end
    cost <= ledger.options.maximum_weighted_oracle_work || return false
    return ledger.weighted_oracle_work <=
           ledger.options.maximum_weighted_oracle_work - cost
end

function _charge_callback!(ledger::_Ledger, bits::Int)
    _can_reserve(ledger, ((1, bits),)) || return false
    raw = ledger.callback_cost
    weighted = _route_cost(ledger, 1, bits)
    ledger.callbacks += 1
    ledger.raw_oracle_work += raw
    ledger.weighted_oracle_work += weighted
    ledger.calls_by_precision[bits] = get(ledger.calls_by_precision, bits, 0) + 1
    return true
end

function _precision_preserved(value::Real, bits::Int)
    value isa Union{Integer,Rational} && return true
    value isa BigFloat || return false
    return precision(value) >= bits
end

function _finite_box(problem::AdaptiveRescueProblem)
    for index in 1:problem.dimension
        lower = problem.lower[index]
        upper = problem.upper[index]
        lower isa Real && upper isa Real || return false
        isfinite(lower) && isfinite(upper) && lower < upper || return false
    end
    return true
end

function _within_bounds(problem::AdaptiveRescueProblem, x)
    return all(
        BigFloat(problem.lower[index]) <= x[index] <= BigFloat(problem.upper[index]) for
        index in 1:problem.dimension
    )
end

function _semantic_shape_ok(state::AdaptiveSemanticState)
    guard_ids = try
        collect(state.guard_identities)
    catch
        return false
    end
    guard_margins = try
        collect(state.guard_margins)
    catch
        return false
    end
    domain_ids = try
        collect(state.domain_identities)
    catch
        return false
    end
    domain_margins = try
        collect(state.domain_margins)
    catch
        return false
    end
    length(guard_ids) == length(guard_margins) || return false
    length(domain_ids) == length(domain_margins) || return false
    return true
end

function _semantic_margins_positive(state::AdaptiveSemanticState)
    _semantic_shape_ok(state) || return false
    margins = try
        vcat(
            Any[state.branch_margin],
            collect(state.guard_margins),
            collect(state.domain_margins),
        )
    catch
        return false
    end
    return all(value -> value isa Real && isfinite(value) && value > 0, margins)
end

function _safe_identity_equal(first, second)
    return try
        value = isequal(first, second)
        value isa Bool ? value : false
    catch
        nothing
    end
end

function _semantic_identity_reason(observed, contract)
    observed isa AdaptiveSemanticState || return :callback_contract_failed
    _semantic_shape_ok(observed) || return :callback_contract_failed
    branch_equal = _safe_identity_equal(
        observed.branch_identity,
        contract.branch_identity,
    )
    branch_equal === true || return :branch_identity_failed
    guard_equal = _safe_identity_equal(
        observed.guard_identities,
        contract.guard_identities,
    )
    guard_equal === true || return :semantic_identity_failed
    domain_equal = _safe_identity_equal(
        observed.domain_identities,
        contract.domain_identities,
    )
    domain_equal === true || return :semantic_identity_failed
    _semantic_margins_positive(observed) || return :semantic_margin_failed
    return :none
end

function _evaluate!(ledger, problem, x, bits, semantic_contract)
    _within_bounds(problem, x) || return (sample=nothing, reason=:outside_bounds)
    _charge_callback!(ledger, bits) || return (sample=nothing, reason=:budget_exhausted)
    raw = try
        problem.evaluate(x, bits)
    catch error
        error isa InterruptException && rethrow()
        return (sample=nothing, reason=:callback_failed)
    end
    raw isa AdaptiveRescueSample || return (sample=nothing, reason=:callback_contract_failed)
    residual = try
        collect(raw.residual)
    catch
        return (sample=nothing, reason=:callback_contract_failed)
    end
    residual_length_ok = try
        length(residual) == problem.residual_dimension
    catch
        false
    end
    residual_length_ok || return (sample=nothing, reason=:callback_contract_failed)
    finite_ok = try
        all(value -> value isa Real && isfinite(value), residual)
    catch
        return (sample=nothing, reason=:callback_contract_failed)
    end
    finite_ok || return (
        sample=nothing,
        reason=:nonfinite_callback,
    )
    precision_ok = try
        all(value -> _precision_preserved(value, bits), residual)
    catch
        return (sample=nothing, reason=:callback_contract_failed)
    end
    precision_ok || return (
        sample=nothing,
        reason=:precision_downgrade,
    )
    raw.semantics_valid || begin
        ledger.semantics_failures += 1
        return (sample=nothing, reason=:semantics_invalid)
    end
    identity_reason = _semantic_identity_reason(raw.semantic_state, semantic_contract)
    identity_reason == :none || begin
        ledger.branch_changes += 1
        return (sample=nothing, reason=identity_reason)
    end
    return (sample=(residual=BigFloat[residual...],), reason=:none)
end

_linf(values) = isempty(values) ? BigFloat(0) : norm(values, Inf)

function _coordinate_chart(problem, coordinates)
    origin = BigFloat[
        (BigFloat(problem.lower[index]) + BigFloat(problem.upper[index])) / 2 for
        index in 1:problem.dimension
    ]
    scale = BigFloat[
        (BigFloat(problem.upper[index]) - BigFloat(problem.lower[index])) / 2 for
        index in 1:problem.dimension
    ]
    normalized = BigFloat[
        (coordinates[index] - origin[index]) / scale[index] for
        index in 1:problem.dimension
    ]
    return normalized, origin, scale
end

_physical(normalized, origin, scale) = origin .+ scale .* normalized

function _central_column!(
    ledger,
    problem,
    normalized,
    origin,
    scale,
    column,
    radius,
    bits,
    branch_contract,
)
    plus = copy(normalized)
    minus = copy(normalized)
    plus[column] += radius
    minus[column] -= radius
    plus_outcome = _evaluate!(
        ledger,
        problem,
        _physical(plus, origin, scale),
        bits,
        branch_contract,
    )
    plus_outcome.sample === nothing && return nothing, plus_outcome.reason
    minus_outcome = _evaluate!(
        ledger,
        problem,
        _physical(minus, origin, scale),
        bits,
        branch_contract,
    )
    minus_outcome.sample === nothing && return nothing, minus_outcome.reason
    derivative = (plus_outcome.sample.residual .- minus_outcome.sample.residual) ./ (2radius)
    all(isfinite, derivative) || return nothing, :nonfinite_jacobian
    return derivative, :none
end

function _central_jacobian!(
    ledger,
    problem,
    normalized,
    origin,
    scale,
    bits,
    branch_contract,
    half_radius::Bool,
)
    jacobian = zeros(BigFloat, problem.residual_dimension, problem.dimension)
    # Exact powers of two keep the A_delta conformance fixture diagnostic about
    # precision rather than about decimal step rounding.  This is the central-
    # difference eps^(1/3) scale rounded conservatively to a binary exponent.
    exponent = -max(8, cld(bits, 3))
    radius = ldexp(one(BigFloat), exponent)
    half_radius && (radius /= 2)
    for column in 1:problem.dimension
        derivative, reason = _central_column!(
            ledger,
            problem,
            normalized,
            origin,
            scale,
            column,
            radius,
            bits,
            branch_contract,
        )
        derivative === nothing && return nothing, reason
        jacobian[:, column] .= derivative
    end
    return jacobian, :none
end

function _one_sided_singular_values(jacobian)
    rows, columns = size(jacobian)
    columns == 0 && return BigFloat[], true
    scale = norm(jacobian)
    iszero(scale) && return zeros(BigFloat, columns), true
    working = Matrix{BigFloat}(jacobian ./ scale)
    relative_floor = BigFloat(32 * max(1, rows, columns)) * eps(BigFloat)
    converged = false
    for _ in 1:max(32, 12columns)
        rotated = false
        for first in 1:(columns - 1), second in (first + 1):columns
            first_column = view(working, :, first)
            second_column = view(working, :, second)
            alpha = dot(first_column, first_column)
            beta = dot(second_column, second_column)
            denominator = sqrt(alpha * beta)
            iszero(denominator) && continue
            gamma = dot(first_column, second_column)
            abs(gamma) <= relative_floor * denominator && continue
            zeta = (beta - alpha) / (2gamma)
            tangent = if iszero(zeta)
                one(BigFloat)
            elseif zeta > 0
                inv(zeta + sqrt(one(BigFloat) + zeta^2))
            else
                -inv(-zeta + sqrt(one(BigFloat) + zeta^2))
            end
            cosine = inv(sqrt(one(BigFloat) + tangent^2))
            sine = cosine * tangent
            frozen_first = copy(first_column)
            frozen_second = copy(second_column)
            working[:, first] .= cosine .* frozen_first .- sine .* frozen_second
            working[:, second] .= sine .* frozen_first .+ cosine .* frozen_second
            rotated = true
        end
        if !rotated
            converged = true
            break
        end
    end
    singular_values = sort!(
        BigFloat[norm(view(working, :, column)) * scale for column in 1:columns];
        rev=true,
    )
    return singular_values, converged
end

function _rank_factorization(jacobian, uncertainty)
    # CPQR is used only for the Newton solve.  Rank, gap and condition authority
    # come from one-sided Jacobi singular values, avoiding Gram squaring and
    # remaining invariant to left/right orthogonal transforms and global F scale.
    factor = try
        qr(jacobian, ColumnNorm())
    catch
        return nothing
    end
    singular_values, spectral_converged = _one_sided_singular_values(jacobian)
    spectral_converged || return nothing
    scale = norm(jacobian)
    roundoff = BigFloat(8 * max(1, maximum(size(jacobian)))) *
               eps(BigFloat)^(BigFloat(2) / BigFloat(3)) * scale
    threshold = roundoff + BigFloat(2) * BigFloat(uncertainty)
    retained = filter(value -> value > threshold, singular_values)
    rank = length(retained)
    condition = isempty(retained) ? BigFloat(Inf) : first(singular_values) / last(retained)
    gap_stable = if rank == length(singular_values)
        iszero(threshold) ? !isempty(singular_values) && last(singular_values) > 0 :
        last(singular_values) > 2threshold
    elseif rank == 0
        isempty(singular_values) || first(singular_values) <= threshold
    else
        retained_smallest = singular_values[rank]
        discarded_largest = singular_values[rank + 1]
        retained_smallest > 2threshold && discarded_largest <= threshold
    end
    return (;
        factor,
        rank,
        condition,
        threshold,
        gap_stable,
        singular_values=Tuple(singular_values),
    )
end

function _correction(factor, residual)
    correction = try
        factor \ (-residual)
    catch
        return nothing
    end
    all(isfinite, correction) || return nothing
    return BigFloat[correction...]
end

function _complete_tier_route(problem, bits)
    # One base observation and central +/- samples at h and h/2 for every axis.
    return ((1 + 4problem.dimension, bits),)
end

function _linearization_stage!(ledger, problem, coordinates, bits, branch_contract)
    route = _complete_tier_route(problem, bits)
    _can_reserve(ledger, route) || return (
        status=:unknown,
        reason=:complete_stencil_budget_insufficient,
    )
    ledger.tier_count += 1
    return setprecision(BigFloat, bits) do
        x = BigFloat[BigFloat(value) for value in coordinates]
        normalized, origin, scale = _coordinate_chart(problem, x)
        base_outcome = _evaluate!(ledger, problem, x, bits, branch_contract)
        base_outcome.sample === nothing && return (
            status=:unknown,
            reason=base_outcome.reason,
        )
        coarse, coarse_reason = _central_jacobian!(
            ledger,
            problem,
            normalized,
            origin,
            scale,
            bits,
            branch_contract,
            false,
        )
        coarse === nothing && return (status=:unknown, reason=coarse_reason)
        fine, fine_reason = _central_jacobian!(
            ledger,
            problem,
            normalized,
            origin,
            scale,
            bits,
            branch_contract,
            true,
        )
        fine === nothing && return (status=:unknown, reason=fine_reason)
        uncertainty = norm(coarse - fine)
        coarse_factor = _rank_factorization(coarse, uncertainty)
        fine_factor = _rank_factorization(fine, uncertainty)
        ledger.factorization_count += 2
        (coarse_factor === nothing || fine_factor === nothing) && return (
            status=:unknown,
            reason=:factorization_failed,
        )
        residual = base_outcome.sample.residual
        if coarse_factor.rank != fine_factor.rank ||
           !coarse_factor.gap_stable || !fine_factor.gap_stable
            return (
                status=:insufficient_precision_evidence,
                reason=:rank_unstable,
                coordinates=Tuple(x),
                residual,
                residual_linf=_linf(residual),
                coarse,
                fine,
                coarse_factor,
                fine_factor,
                bits,
            )
        end
        if fine_factor.rank != problem.dimension
            residual_linf = _linf(residual)
            reason = if residual_linf > BigFloat(1.0e-110) &&
                        norm(fine, Inf) <= fine_factor.threshold
                :stationary_nonroot_or_singular
            else
                :rank_deficient_unisolated
            end
            return (
                status=:insufficient_precision_evidence,
                reason,
                coordinates=Tuple(x),
                residual,
                residual_linf,
                coarse,
                fine,
                coarse_factor,
                fine_factor,
                bits,
            )
        end
        coarse_correction = _correction(coarse_factor.factor, residual)
        fine_correction = _correction(fine_factor.factor, residual)
        (coarse_correction === nothing || fine_correction === nothing) && return (
            status=:unknown,
            reason=:linear_solve_failed,
        )
        correction_stable, correction_disagreement, correction_relative_tolerance =
            _relative_correction_agreement(
                coarse_correction,
                fine_correction,
                bits,
                max(coarse_factor.condition, fine_factor.condition),
            )
        correction_stable || return (
            status=:insufficient_precision_evidence,
            reason=:correction_unstable,
            coordinates=Tuple(x),
            residual,
            residual_linf=_linf(residual),
            coarse,
            fine,
            coarse_factor,
            fine_factor,
            bits,
        )
        return (
            status=:full_rank,
            reason=:none,
            coordinates=Tuple(x),
            normalized=Tuple(normalized),
            origin=Tuple(origin),
            scale=Tuple(scale),
            residual,
            residual_linf=_linf(residual),
            coarse,
            fine,
            coarse_factor,
            fine_factor,
            coarse_correction,
            fine_correction,
            correction_disagreement,
            correction_relative_tolerance,
            bits,
        )
    end
end

function _newton_step!(ledger, problem, stage, branch_contract)
    bits = stage.bits
    _can_reserve(ledger, ((1, bits),)) || return (
        status=:unknown,
        reason=:newton_step_budget_insufficient,
    )
    return setprecision(BigFloat, bits) do
        normalized = BigFloat[stage.normalized...]
        origin = BigFloat[stage.origin...]
        scale = BigFloat[stage.scale...]
        correction = BigFloat[stage.fine_correction...]
        trial_normalized = normalized .+ correction
        trial_coordinates = _physical(trial_normalized, origin, scale)
        outcome = _evaluate!(ledger, problem, trial_coordinates, bits, branch_contract)
        outcome.sample === nothing && return (status=:unknown, reason=outcome.reason)
        source_merit = sum(abs2, BigFloat[stage.residual...]) / 2
        trial_residual = outcome.sample.residual
        trial_merit = sum(abs2, trial_residual) / 2
        trial_merit < source_merit || return (
            status=:unknown,
            reason=:newton_step_not_residual_decreasing,
        )
        ledger.newton_steps += 1
        return (
            status=:accepted,
            reason=:none,
            coordinates=Tuple(trial_coordinates),
            residual=trial_residual,
            residual_linf=_linf(trial_residual),
        )
    end
end

function _next_tier(bits::Int)
    bits == 128 && return 256
    bits == 256 && return 512
    return nothing
end

function _minimum_remaining_route(problem, selected_bits, confirmation_bits)
    return (
        (1, selected_bits),
        first(_complete_tier_route(problem, confirmation_bits)),
    )
end

function _relative_correction_agreement(coarse_values, fine_values, bits, condition)
    return setprecision(BigFloat, bits) do
        coarse = BigFloat[coarse_values...]
        fine = BigFloat[fine_values...]
        disagreement = norm(coarse - fine)
        correction_scale = max(norm(coarse), norm(fine))
        relative_tolerance = min(
            BigFloat(1) / 8,
            BigFloat(64) * sqrt(eps(BigFloat)) * BigFloat(condition),
        )
        stable = if iszero(correction_scale)
            iszero(disagreement)
        else
            disagreement / correction_scale <= relative_tolerance
        end
        return stable,
               disagreement,
               relative_tolerance
    end
end

function _copy_at_precision(value::Real, bits::Int)
    return setprecision(BigFloat, bits) do
        BigFloat(value)
    end
end

function _copy_tuple_at_precision(values, bits::Int)
    return setprecision(BigFloat, bits) do
        Tuple(BigFloat(value) for value in values)
    end
end

function _cross_tier_confirmation(selected, confirmation)
    selected_bits = selected.bits
    confirmation_bits = confirmation.bits
    selected_condition = max(
        selected.coarse_factor.condition,
        selected.fine_factor.condition,
    )
    forward_factor = setprecision(BigFloat, selected_bits) do
        # Central FD uses h~eps^(1/3), so its scale-homogeneous forward model
        # uncertainty is O(eps^(2/3)*kappa), not O(eps*kappa).
        BigFloat(8) * eps(BigFloat)^(BigFloat(2) / BigFloat(3)) *
        BigFloat(selected_condition)
    end
    if !isfinite(forward_factor) || forward_factor >= 1 // 4
        return (status=:unknown, reason=:cross_tier_condition_unresolved)
    end
    return setprecision(BigFloat, confirmation_bits) do
        selected_residual = BigFloat[selected.residual...]
        confirmation_residual = BigFloat[confirmation.residual...]
        residual_scale = norm(selected_residual)
        iszero(residual_scale) && return (
            status=:unknown,
            reason=:cross_tier_condition_unresolved,
        )
        residual_disagreement = norm(selected_residual - confirmation_residual)
        residual_tolerance = BigFloat(forward_factor) * residual_scale
        residual_disagreement <= residual_tolerance || return (
            status=:unknown,
            reason=:cross_tier_model_disagreement,
            residual_disagreement,
            residual_tolerance,
        )

        selected_coarse = Matrix{BigFloat}(selected.coarse)
        selected_fine = Matrix{BigFloat}(selected.fine)
        confirmation_coarse = Matrix{BigFloat}(confirmation.coarse)
        confirmation_fine = Matrix{BigFloat}(confirmation.fine)
        selected_spectrum = BigFloat[selected.fine_factor.singular_values...]
        confirmation_spectrum = BigFloat[confirmation.fine_factor.singular_values...]
        jacobian_scale = max(norm(selected_coarse), norm(selected_fine))
        iszero(jacobian_scale) && return (
            status=:unknown,
            reason=:cross_tier_condition_unresolved,
            residual_disagreement,
            residual_tolerance,
        )
        jacobian_disagreement = max(
            norm(selected_coarse - confirmation_coarse),
            norm(selected_fine - confirmation_fine),
            norm(selected_spectrum - confirmation_spectrum),
        )
        jacobian_tolerance = BigFloat(forward_factor) * jacobian_scale
        jacobian_disagreement <= jacobian_tolerance || return (
            status=:unknown,
            reason=:cross_tier_model_disagreement,
            residual_disagreement,
            residual_tolerance,
            jacobian_disagreement,
            jacobian_tolerance,
        )

        selected_coarse_correction = BigFloat[selected.coarse_correction...]
        selected_fine_correction = BigFloat[selected.fine_correction...]
        confirmation_coarse_correction = BigFloat[confirmation.coarse_correction...]
        confirmation_fine_correction = BigFloat[confirmation.fine_correction...]
        correction_scale = max(
            norm(selected_coarse_correction),
            norm(selected_fine_correction),
        )
        iszero(correction_scale) && return (
            status=:unknown,
            reason=:cross_tier_condition_unresolved,
        )
        correction_disagreement = max(
            norm(selected_coarse_correction - confirmation_coarse_correction),
            norm(selected_fine_correction - confirmation_fine_correction),
        )
        correction_tolerance = BigFloat(forward_factor) * correction_scale
        correction_disagreement <= correction_tolerance || return (
            status=:unknown,
            reason=:cross_tier_model_disagreement,
            residual_disagreement,
            residual_tolerance,
            jacobian_disagreement,
            jacobian_tolerance,
            correction_disagreement,
            correction_tolerance,
        )
        confirmation_correction_linf = max(
            norm(confirmation_coarse_correction, Inf),
            norm(confirmation_fine_correction, Inf),
        )
        return (
            status=:confirmed,
            reason=:none,
            residual_disagreement,
            residual_tolerance,
            jacobian_disagreement,
            jacobian_tolerance,
            correction_disagreement,
            confirmation_correction_linf,
            correction_tolerance,
        )
    end
end

function _first_tier(problem, seed)
    seed.numerical_rank < problem.dimension && return 256
    seed.condition_estimate >= CONDITION_TRIGGER && return 128
    return nothing
end

"""
Run the formal-cap GEOTARGET_ADAPTED precision rescue.

The selected tier is public-evidence-only.  Every tier atomically prechecks its
complete `base + 4n` central h/h2 route.  A successful result contains only an
evaluated refinement seed.  The adjacent higher tier confirms the selected
model at the same source coordinates before the selected-tier Newton step; it
does not validate the refined endpoint.  Downstream 512/768 validation retains
answer authority.
"""
function rescue_adaptive_precision(
    problem::AdaptiveRescueProblem,
    seed::AdaptiveRescueSeed;
    options::AdaptiveRescueOptions=AdaptiveRescueOptions(),
)
    ledger = _Ledger(options, problem.callback_cost)
    length(seed.coordinates) == problem.dimension || return _unknown(
        ledger,
        :dimension_mismatch,
        "pre-filter seed coordinate count differs from the problem",
    )
    seed.numerical_rank <= problem.dimension || return _unknown(
        ledger,
        :invalid_prefilter_rank,
        "pre-filter rank exceeds the variable dimension",
    )
    problem.capability == :C2 || return _unknown(
        ledger,
        :c2_capability_missing,
        "declared C2 capability is required",
    )
    _finite_box(problem) || return _unknown(
        ledger,
        :finite_box_required,
        "finite nondegenerate bounds are required",
    )
    problem.residual_dimension >= problem.dimension || return _unknown(
        ledger,
        :underdetermined_manifold,
        "fewer residuals than variables cannot establish isolation",
    )
    seed.semantics_valid || return _unknown(
        ledger,
        :prefilter_semantics_invalid,
        "pre-filter endpoint semantics were invalid",
    )
    _semantic_shape_ok(seed.semantic_state) || return _unknown(
        ledger,
        :prefilter_semantic_contract_invalid,
        "pre-filter semantic identity/margin shape was malformed",
    )
    _semantic_margins_positive(seed.semantic_state) || return _unknown(
        ledger,
        :prefilter_semantic_margin_invalid,
        "pre-filter strict guard/domain margins were not finite and positive",
    )
    seed.model_agreement || return _unknown(
        ledger,
        :model_disagreement,
        "pre-filter model agreement was not established",
    )
    first_bits = _first_tier(problem, seed)
    first_bits === nothing && return _unknown(
        ledger,
        :condition_trigger_not_met,
        "endpoint does not enter the adaptive precision lane",
    )
    first_confirmation = _next_tier(first_bits)::Int
    initial_route = (
        first(_complete_tier_route(problem, first_bits)),
        _minimum_remaining_route(problem, first_bits, first_confirmation)...,
    )
    _can_reserve(ledger, initial_route) || return _unknown(
        ledger,
        :complete_route_budget_insufficient,
        "the selected tier, one Newton step and confirmation tier do not fit atomically",
    )

    path = Int[first_bits]
    selected = _linearization_stage!(
        ledger,
        problem,
        seed.coordinates,
        first_bits,
        seed.semantic_state,
    )
    selected.status == :unknown && return _unknown(
        ledger,
        selected.reason,
        "selected precision tier failed before a complete model was available",
    )
    if selected.status == :insufficient_precision_evidence
        first_bits == 128 || return _unknown(
            ledger,
            selected.reason,
            "256-bit selected tier did not establish a stable isolated model",
        )
        selected_bits = 256
        confirmation_bits = 512
        escalation_route = (
            first(_complete_tier_route(problem, selected_bits)),
            _minimum_remaining_route(problem, selected_bits, confirmation_bits)...,
        )
        _can_reserve(ledger, escalation_route) || return _unknown(
            ledger,
            :escalation_route_budget_insufficient,
            "evidence-required 256/512 route does not fit the remaining formal cap",
        )
        push!(path, selected_bits)
        selected = _linearization_stage!(
            ledger,
            problem,
            selected.coordinates,
            selected_bits,
            seed.semantic_state,
        )
        selected.status == :full_rank || return _unknown(
            ledger,
            selected.reason,
            "evidence-required 256-bit tier did not establish stable full rank",
        )
    end
    selected_bits = selected.bits
    confirmation_bits = _next_tier(selected_bits)
    confirmation_bits === nothing && return _unknown(
        ledger,
        :confirmation_tier_unavailable,
        "no independent higher precision tier remains",
    )
    _can_reserve(
        ledger,
        _minimum_remaining_route(problem, selected_bits, confirmation_bits),
    ) || return _unknown(
        ledger,
        :confirmation_route_budget_insufficient,
        "Newton step plus complete confirmation stencil exceeds the formal cap",
    )
    push!(path, confirmation_bits)
    confirmation = _linearization_stage!(
        ledger,
        problem,
        selected.coordinates,
        confirmation_bits,
        seed.semantic_state,
    )
    confirmation.status == :full_rank || return _unknown(
        ledger,
        confirmation.reason,
        "same-source next-tier rank/correction confirmation failed",
    )
    cross_tier = _cross_tier_confirmation(selected, confirmation)
    cross_tier.status == :confirmed || return _unknown(
        ledger,
        cross_tier.reason,
        "same-source adjacent-tier residual/Jacobian/correction models did not agree",
    )
    stepped = _newton_step!(ledger, problem, selected, seed.semantic_state)
    stepped.status == :accepted || return _unknown(
        ledger,
        stepped.reason,
        "selected-tier CPQR Newton step was not admissible after model confirmation",
    )
    selected_condition = _copy_at_precision(
        max(selected.coarse_factor.condition, selected.fine_factor.condition),
        selected_bits,
    )
    confirmation_condition = _copy_at_precision(
        max(
            confirmation.coarse_factor.condition,
            confirmation.fine_factor.condition,
        ),
        confirmation_bits,
    )
    evidence = AdaptiveRefinementSeedEvidence(
        _METHOD,
        seed.coordinates,
        _copy_tuple_at_precision(stepped.coordinates, selected_bits),
        selected_bits,
        confirmation_bits,
        Tuple(path),
        _copy_at_precision(selected.residual_linf, selected_bits),
        _copy_at_precision(stepped.residual_linf, selected_bits),
        selected.fine_factor.rank,
        confirmation.fine_factor.rank,
        selected_condition,
        confirmation_condition,
        _copy_at_precision(cross_tier.confirmation_correction_linf, confirmation_bits),
        _copy_at_precision(confirmation.correction_disagreement, confirmation_bits),
        _copy_at_precision(cross_tier.residual_disagreement, confirmation_bits),
        _copy_at_precision(cross_tier.residual_tolerance, confirmation_bits),
        _copy_at_precision(cross_tier.jacobian_disagreement, confirmation_bits),
        _copy_at_precision(cross_tier.jacobian_tolerance, confirmation_bits),
        _copy_at_precision(cross_tier.correction_disagreement, confirmation_bits),
        _copy_at_precision(cross_tier.correction_tolerance, confirmation_bits),
        true,
        true,
        seed.semantic_state,
    )
    return AdaptivePrecisionResult(
        :seed_ready,
        :none,
        "$ADAPTED_NAME refinement seed only; production 512/768 replay remains mandatory",
        evidence,
        _snapshot(ledger),
    )
end

end # module AdaptivePrecisionRescue
