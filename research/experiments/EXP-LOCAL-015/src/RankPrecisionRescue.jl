module RankPrecisionRescue

using LinearAlgebra

export RankRescueOptions,
       RankRescueProblem,
       RankRescueSample,
       RankRescueSeed,
       RankPrecisionEvidence,
       RankPrecisionResult,
       RankPrecisionWork,
       REFERENCE_NAME,
       FORMAL_EQUAL_WORK_PROMOTION_AUTHORITY,
       FORMAL_600_WORK_CLASSIFICATION,
       rescue_rank_precision

const REFERENCE_NAME = "REFERENCE-512-CPQR-H-H2"
const FORMAL_EQUAL_WORK_PROMOTION_AUTHORITY = false
const FORMAL_600_WORK_CLASSIFICATION = :BUDGET_OR_PARAMETER_LIMITED
const METHOD = "EXP-LOCAL-015-$REFERENCE_NAME"
const PRECISION_BITS = 512
const PRECISION_WEIGHT = cld(PRECISION_BITS, 53)
const _LINE_SEARCH_ALPHAS = (1, 1 // 2, 1 // 4, 1 // 8)

"""
One C2 observation made by the experiment-local rescue lane.

`semantics_valid` combines bounds-external domain/guard validity.  Branch identity
is deliberately opaque: the rescue may compare it with the pre-filter contract,
but may not route on its contents.
"""
struct RankRescueSample{R,B}
    residual::R
    semantics_valid::Bool
    branch_signature::B
end

"""
Truth-blind input contract for a single endpoint rescue.

The callback is invoked as `evaluate(coordinates, precision_bits)` and must return
a `RankRescueSample`.  `callback_cost` is the logical cost charged before every
call, including calls which throw or return unusable data.
"""
struct RankRescueProblem{F}
    dimension::Int
    residual_dimension::Int
    capability::Symbol
    lower::Tuple
    upper::Tuple
    callback_cost::Int
    evaluate::F

    function RankRescueProblem(
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
Float64 pre-filter seed and its public numerical trigger evidence.

No case/family/Gold identifier is admitted.  The candidate is applicable only
when the pre-filter is semantics-valid, its local model agrees, and either the
reported condition exceeds the frozen trigger or its rank is deficient.
"""
struct RankRescueSeed{B}
    coordinates::Tuple
    numerical_rank::Int
    condition_estimate::Float64
    model_agreement::Bool
    semantics_valid::Bool
    branch_signature::B

    function RankRescueSeed(
        coordinates,
        numerical_rank::Integer,
        condition_estimate::Real,
        model_agreement::Bool,
        semantics_valid::Bool,
        branch_signature::B,
    ) where {B}
        frozen = Tuple(Float64(value) for value in coordinates)
        all(isfinite, frozen) || throw(ArgumentError("seed coordinates must be finite"))
        numerical_rank >= 0 || throw(ArgumentError("numerical rank cannot be negative"))
        condition = Float64(condition_estimate)
        condition >= 0 && (isfinite(condition) || isinf(condition)) || throw(
            ArgumentError("condition estimate must be nonnegative or infinite"),
        )
        return new{B}(
            frozen,
            Int(numerical_rank),
            condition,
            model_agreement,
            semantics_valid,
            branch_signature,
        )
    end
end

struct RankRescueOptions
    precision_bits::Int
    condition_trigger::Float64
    residual_goal::Float64
    configuration_goal::Float64
    maximum_iterations::Int
    maximum_callbacks::Int
    maximum_weighted_oracle_work::Int

    function RankRescueOptions(
        ;
        precision_bits::Integer=PRECISION_BITS,
        condition_trigger::Real=1.0e8,
        residual_goal::Real=1.0e-110,
        configuration_goal::Real=1.0e-100,
        maximum_iterations::Integer=8,
        maximum_callbacks::Integer=512,
        maximum_weighted_oracle_work::Integer=5120,
    )
        precision_bits == PRECISION_BITS || throw(
            ArgumentError("EXP-LOCAL-015 candidate A is fixed at 512 bits"),
        )
        trigger = Float64(condition_trigger)
        isfinite(trigger) && trigger > 1 || throw(
            ArgumentError("condition_trigger must be finite and greater than one"),
        )
        residual = Float64(residual_goal)
        configuration = Float64(configuration_goal)
        isfinite(residual) && 0 < residual <= 1.0e-110 || throw(
            ArgumentError("residual_goal must lie in (0, 1e-110]"),
        )
        isfinite(configuration) && 0 < configuration <= 1.0e-100 || throw(
            ArgumentError("configuration_goal must lie in (0, 1e-100]"),
        )
        maximum_iterations > 0 || throw(
            ArgumentError("maximum_iterations must be positive"),
        )
        maximum_callbacks > 0 || throw(
            ArgumentError("maximum_callbacks must be positive"),
        )
        maximum_weighted_oracle_work > 0 || throw(
            ArgumentError("maximum_weighted_oracle_work must be positive"),
        )
        return new(
            Int(precision_bits),
            trigger,
            residual,
            configuration,
            Int(maximum_iterations),
            Int(maximum_callbacks),
            Int(maximum_weighted_oracle_work),
        )
    end
end

struct RankPrecisionWork
    precision_bits::Int
    precision_weight::Int
    callbacks::Int
    raw_oracle_work::Int
    precision_weighted_oracle_work::Int
    factorization_count::Int
    iteration_count::Int
end

"""
Refinement-seed evidence only.  This is intentionally not an answer or a
certificate: canonical 768-bit replay remains the sole downstream authority.
"""
struct RankPrecisionEvidence{B}
    method::String
    source_coordinates::Tuple
    refined_coordinates::Tuple
    residual_linf::BigFloat
    correction_linf::BigFloat
    numerical_rank::Int
    condition_estimate::BigFloat
    rank_stable::Bool
    branch_signature::B
    iterations::Int
end

struct RankPrecisionResult{E}
    status::Symbol
    reason::Symbol
    diagnostic::String
    evidence::E
    work::RankPrecisionWork

    function RankPrecisionResult(
        status::Symbol,
        reason::Symbol,
        diagnostic::AbstractString,
        evidence::E,
        work::RankPrecisionWork,
    ) where {E}
        status in (:seed_ready, :unknown) || throw(
            ArgumentError("rank rescue status must be seed_ready or unknown"),
        )
        (status == :seed_ready) == (evidence isa RankPrecisionEvidence) || throw(
            ArgumentError("only seed_ready results carry refinement evidence"),
        )
        status == :seed_ready && reason != :none && throw(
            ArgumentError("seed_ready result cannot carry a failure reason"),
        )
        status == :unknown && reason == :none && throw(
            ArgumentError("unknown result requires a typed reason"),
        )
        return new{E}(status, reason, String(diagnostic), evidence, work)
    end
end

mutable struct _Ledger
    options::RankRescueOptions
    callback_cost::Int
    callbacks::Int
    raw_oracle_work::Int
    weighted_oracle_work::Int
    factorization_count::Int
    iteration_count::Int
    stop_reason::Symbol
    branch_changes::Int
    semantics_failures::Int
end

_Ledger(options, callback_cost) = _Ledger(
    options,
    callback_cost,
    0,
    0,
    0,
    0,
    0,
    :none,
    0,
    0,
)

function _snapshot(ledger::_Ledger)
    return RankPrecisionWork(
        PRECISION_BITS,
        PRECISION_WEIGHT,
        ledger.callbacks,
        ledger.raw_oracle_work,
        ledger.weighted_oracle_work,
        ledger.factorization_count,
        ledger.iteration_count,
    )
end

function _unknown(ledger, reason::Symbol, diagnostic::AbstractString)
    return RankPrecisionResult(
        :unknown,
        reason,
        "$REFERENCE_NAME mechanism diagnostic: $diagnostic",
        nothing,
        _snapshot(ledger),
    )
end

function _checked_add(left::Int, right::Int)
    right >= 0 || throw(ArgumentError("work increment cannot be negative"))
    right <= typemax(Int) - left || return typemax(Int)
    return left + right
end

function _checked_product(left::Int, right::Int)
    try
        return Base.checked_mul(left, right)
    catch error
        error isa OverflowError || rethrow()
        return typemax(Int)
    end
end

function _reserve_callback!(ledger::_Ledger)
    ledger.callbacks < ledger.options.maximum_callbacks || begin
        ledger.stop_reason = :callback_budget_exhausted
        return false
    end
    raw = ledger.callback_cost
    weighted = _checked_product(PRECISION_WEIGHT, raw)
    weighted <= ledger.options.maximum_weighted_oracle_work || begin
        ledger.stop_reason = :weighted_oracle_budget_exhausted
        return false
    end
    ledger.weighted_oracle_work <=
        ledger.options.maximum_weighted_oracle_work - weighted || begin
        ledger.stop_reason = :weighted_oracle_budget_exhausted
        return false
    end
    # Charge before invocation: throwing and unusable callbacks remain visible.
    ledger.callbacks += 1
    ledger.raw_oracle_work = _checked_add(ledger.raw_oracle_work, raw)
    ledger.weighted_oracle_work = _checked_add(ledger.weighted_oracle_work, weighted)
    return true
end

function _precision_preserved(value::Real, bits::Int)
    value isa Union{Integer,Rational} && return true
    value isa BigFloat || return false
    return precision(value) >= bits
end

function _within_bounds(problem::RankRescueProblem, x)
    return all(
        BigFloat(problem.lower[index]) <= x[index] <= BigFloat(problem.upper[index]) for
        index in 1:problem.dimension
    )
end

function _evaluate!(ledger::_Ledger, problem::RankRescueProblem, x, branch_contract)
    _within_bounds(problem, x) || return (sample=nothing, reason=:outside_bounds)
    _reserve_callback!(ledger) || return (sample=nothing, reason=ledger.stop_reason)
    raw = try
        problem.evaluate(x, PRECISION_BITS)
    catch error
        error isa InterruptException && rethrow()
        ledger.stop_reason = :callback_failed
        return (sample=nothing, reason=:callback_failed)
    end
    raw isa RankRescueSample || begin
        ledger.stop_reason = :callback_contract_failed
        return (sample=nothing, reason=:callback_contract_failed)
    end
    residual = collect(raw.residual)
    length(residual) == problem.residual_dimension || begin
        ledger.stop_reason = :callback_contract_failed
        return (sample=nothing, reason=:callback_contract_failed)
    end
    all(value -> value isa Real && isfinite(value), residual) || begin
        ledger.stop_reason = :nonfinite_callback
        return (sample=nothing, reason=:nonfinite_callback)
    end
    all(value -> _precision_preserved(value, PRECISION_BITS), residual) || begin
        ledger.stop_reason = :precision_downgrade
        return (sample=nothing, reason=:precision_downgrade)
    end
    raw.semantics_valid || begin
        ledger.semantics_failures += 1
        return (sample=nothing, reason=:semantics_invalid)
    end
    isequal(raw.branch_signature, branch_contract) || begin
        ledger.branch_changes += 1
        return (sample=nothing, reason=:branch_changed)
    end
    return (
        sample=(residual=BigFloat[residual...], branch_signature=raw.branch_signature),
        reason=:none,
    )
end

_residual_linf(residual) = isempty(residual) ? BigFloat(0) : norm(residual, Inf)

function _normalized_coordinates(problem::RankRescueProblem, coordinates)
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

_physical_coordinates(normalized, origin, scale) = origin .+ scale .* normalized

function _five_point_column!(
    ledger,
    problem,
    normalized,
    origin,
    scale,
    column,
    radius,
    branch_contract,
)
    samples = Vector{Vector{BigFloat}}()
    for offset in (-2, -1, 1, 2)
        trial = copy(normalized)
        trial[column] += BigFloat(offset) * radius
        outcome = _evaluate!(
            ledger,
            problem,
            _physical_coordinates(trial, origin, scale),
            branch_contract,
        )
        outcome.sample === nothing && return nothing, outcome.reason
        push!(samples, outcome.sample.residual)
    end
    derivative = (
        samples[1] .- BigFloat(8) .* samples[2] .+
        BigFloat(8) .* samples[3] .- samples[4]
    ) ./ (BigFloat(12) * radius)
    all(isfinite, derivative) || return nothing, :nonfinite_jacobian
    return derivative, :none
end

function _jacobian!(ledger, problem, normalized, origin, scale, branch_contract, multiplier)
    jacobian = zeros(BigFloat, problem.residual_dimension, problem.dimension)
    radius_scale = eps(BigFloat)^(BigFloat(1) / BigFloat(5))
    for column in 1:problem.dimension
        initial = BigFloat(multiplier) * radius_scale * max(one(BigFloat), abs(normalized[column]))
        selected = nothing
        last_reason = :stencil_unavailable
        radius = initial
        for _ in 1:8
            derivative, reason = _five_point_column!(
                ledger,
                problem,
                normalized,
                origin,
                scale,
                column,
                radius,
                branch_contract,
            )
            if derivative !== nothing
                selected = derivative
                break
            end
            reason in (
                :callback_budget_exhausted,
                :weighted_oracle_budget_exhausted,
                :callback_failed,
                :callback_contract_failed,
                :nonfinite_callback,
                :precision_downgrade,
            ) && return nothing, reason
            last_reason = reason
            radius /= 2
        end
        selected === nothing && return nothing, last_reason
        jacobian[:, column] .= selected
    end
    return jacobian, :none
end

function _rank_factorization(jacobian, uncertainty)
    factor = try
        qr(jacobian, ColumnNorm())
    catch
        return nothing
    end
    diagonal_count = min(size(jacobian)...)
    diagonal = BigFloat[
        abs(factor.R[index, index]) for index in 1:diagonal_count
    ]
    scale = max(one(BigFloat), norm(jacobian, Inf))
    # A derivative divides cancellation error by h~eps^(1/5); hence its
    # roundoff floor is eps^(4/5), not eps.  Using the value-space epsilon here
    # would falsely report a stationary nonroot as a fantastically ill-
    # conditioned full-rank model.
    roundoff = BigFloat(128 * max(1, maximum(size(jacobian)))) *
               eps(BigFloat)^(BigFloat(4) / BigFloat(5)) * scale
    threshold = max(roundoff, BigFloat(4) * BigFloat(uncertainty))
    retained = filter(value -> value > threshold, diagonal)
    rank = length(retained)
    condition = isempty(retained) ? BigFloat(Inf) : maximum(retained) / minimum(retained)
    return (; factor, rank, condition, threshold)
end

function _linear_correction(factor, residual)
    correction = try
        factor \ (-residual)
    catch
        return nothing
    end
    all(isfinite, correction) || return nothing
    return BigFloat[correction...]
end

function _finite_box(problem::RankRescueProblem)
    for index in 1:problem.dimension
        lower = problem.lower[index]
        upper = problem.upper[index]
        lower isa Real && upper isa Real || return false
        isfinite(lower) && isfinite(upper) && lower < upper || return false
    end
    return true
end

function _rescue_512(
    problem::RankRescueProblem,
    seed::RankRescueSeed,
    options::RankRescueOptions,
    ledger::_Ledger,
)
    coordinates = BigFloat[BigFloat(value) for value in seed.coordinates]
    normalized, origin, scale = _normalized_coordinates(problem, coordinates)
    base_outcome = _evaluate!(ledger, problem, coordinates, seed.branch_signature)
    base_outcome.sample === nothing && return _unknown(
        ledger,
        base_outcome.reason,
        "512-bit base observation did not preserve the seed semantics contract",
    )
    base = base_outcome.sample
    residual = base.residual
    residual_goal = BigFloat(options.residual_goal)
    configuration_goal = BigFloat(options.configuration_goal)

    for iteration in 1:options.maximum_iterations
        ledger.iteration_count = iteration
        coarse, coarse_reason = _jacobian!(
            ledger,
            problem,
            normalized,
            origin,
            scale,
            seed.branch_signature,
            1,
        )
        coarse === nothing && return _unknown(
            ledger,
            coarse_reason,
            "the branch-stable h Jacobian was unavailable",
        )
        fine, fine_reason = _jacobian!(
            ledger,
            problem,
            normalized,
            origin,
            scale,
            seed.branch_signature,
            1 // 2,
        )
        fine === nothing && return _unknown(
            ledger,
            fine_reason,
            "the branch-stable h/2 Jacobian was unavailable",
        )
        uncertainty = norm(coarse - fine, Inf)
        coarse_factor = _rank_factorization(coarse, uncertainty)
        fine_factor = _rank_factorization(fine, uncertainty)
        ledger.factorization_count += 2
        (coarse_factor === nothing || fine_factor === nothing) && return _unknown(
            ledger,
            :factorization_failed,
            "512-bit CPQR factorization failed",
        )
        full_rank = problem.dimension
        if coarse_factor.rank != fine_factor.rank
            return _unknown(
                ledger,
                :rank_unstable,
                "h and h/2 numerical ranks disagree",
            )
        end
        if fine_factor.rank != full_rank
            reason = _residual_linf(residual) > residual_goal &&
                     norm(fine, Inf) <= fine_factor.threshold ?
                     :stationary_nonroot_or_singular : :rank_deficient_or_manifold
            return _unknown(
                ledger,
                reason,
                "full-column-rank isolation was not established",
            )
        end
        correction = _linear_correction(fine_factor.factor, residual)
        correction === nothing && return _unknown(
            ledger,
            :linear_solve_failed,
            "512-bit rank-revealing correction failed",
        )
        correction_linf = norm(correction, Inf)
        residual_linf = _residual_linf(residual)
        if residual_linf <= residual_goal && correction_linf <= configuration_goal
            evidence = RankPrecisionEvidence(
                METHOD,
                seed.coordinates,
                Tuple(coordinates),
                residual_linf,
                correction_linf,
                full_rank,
                max(coarse_factor.condition, fine_factor.condition),
                true,
                seed.branch_signature,
                iteration,
            )
            return RankPrecisionResult(
                :seed_ready,
                :none,
                "$REFERENCE_NAME mechanism diagnostic only; 512-bit isolated refinement " *
                "seed found, but independent 768-bit replay is still required",
                evidence,
                _snapshot(ledger),
            )
        end

        merit = isempty(residual) ? BigFloat(0) : sum(abs2, residual) / 2
        branch_before = ledger.branch_changes
        semantics_before = ledger.semantics_failures
        accepted = nothing
        for alpha in _LINE_SEARCH_ALPHAS
            trial_normalized = normalized .+ BigFloat(alpha) .* correction
            trial_coordinates = _physical_coordinates(trial_normalized, origin, scale)
            outcome = _evaluate!(ledger, problem, trial_coordinates, seed.branch_signature)
            if outcome.sample === nothing
                outcome.reason in (
                    :callback_budget_exhausted,
                    :weighted_oracle_budget_exhausted,
                    :callback_failed,
                    :callback_contract_failed,
                    :nonfinite_callback,
                    :precision_downgrade,
                ) && return _unknown(
                    ledger,
                    outcome.reason,
                    "line-search callback failed before a seed could be produced",
                )
                continue
            end
            trial_residual = outcome.sample.residual
            trial_merit = isempty(trial_residual) ? BigFloat(0) : sum(abs2, trial_residual) / 2
            if trial_merit < merit
                accepted = (
                    normalized=trial_normalized,
                    coordinates=trial_coordinates,
                    sample=outcome.sample,
                )
                break
            end
        end
        if accepted === nothing
            reason = ledger.branch_changes > branch_before ? :branch_changed :
                     ledger.semantics_failures > semantics_before ? :semantics_changed :
                     :no_progress
            return _unknown(
                ledger,
                reason,
                "no branch-stable residual-decreasing rank correction was available",
            )
        end
        normalized = BigFloat[accepted.normalized...]
        coordinates = BigFloat[accepted.coordinates...]
        base = accepted.sample
        residual = base.residual
    end
    return _unknown(
        ledger,
        :iteration_limit,
        "512-bit rescue reached its frozen iteration limit",
    )
end

"""
Run the condition-triggered experiment-local REFERENCE-512 rank rescue.

The function never creates an answer.  `:seed_ready` means only that full-rank
CPQR and h/h2 agreement produced a candidate seed suitable for the independent
production 768-bit canonical replay.  Every other result is a typed `:unknown`.

This fixed-precision reference has no formal equal-work promotion authority.  In
particular, one base evaluation plus two four-sample Jacobians costs `1 + 8d`
callbacks before the first Newton step, or 650 precision-weighted units at d=8;
under the formal 600-unit cap it is structurally `BUDGET_OR_PARAMETER_LIMITED`.
"""
function rescue_rank_precision(
    problem::RankRescueProblem,
    seed::RankRescueSeed;
    options::RankRescueOptions=RankRescueOptions(),
)
    ledger = _Ledger(options, problem.callback_cost)
    length(seed.coordinates) == problem.dimension || return _unknown(
        ledger,
        :dimension_mismatch,
        "pre-filter seed has the wrong coordinate count",
    )
    seed.numerical_rank <= problem.dimension || return _unknown(
        ledger,
        :invalid_prefilter_rank,
        "pre-filter numerical rank exceeds the variable dimension",
    )
    problem.capability == :C2 || return _unknown(
        ledger,
        :c2_capability_missing,
        "declared C2 high-precision capability is required",
    )
    _finite_box(problem) || return _unknown(
        ledger,
        :finite_box_required,
        "rank rescue is applicable only to finite nondegenerate boxes",
    )
    problem.residual_dimension >= problem.dimension || return _unknown(
        ledger,
        :underdetermined_manifold,
        "fewer relations than variables cannot establish an isolated root",
    )
    seed.semantics_valid || return _unknown(
        ledger,
        :prefilter_semantics_invalid,
        "pre-filter endpoint semantics were invalid",
    )
    seed.model_agreement || return _unknown(
        ledger,
        :model_disagreement,
        "pre-filter h/h2 model agreement was not established",
    )
    triggered = seed.numerical_rank < problem.dimension ||
                seed.condition_estimate >= options.condition_trigger
    triggered || return _unknown(
        ledger,
        :condition_trigger_not_met,
        "endpoint does not enter the condition-triggered rescue lane",
    )
    return setprecision(BigFloat, PRECISION_BITS) do
        _rescue_512(problem, seed, options, ledger)
    end
end

end # module RankPrecisionRescue
