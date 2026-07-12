module ExperimentLocal008

using GeoTargetBenchmarks
using LinearAlgebra

const EXPERIMENT_ID = "EXP-LOCAL-008"
const DEFAULT_MAX_CALLBACKS = 600
const DEFAULT_MAX_ITERATIONS = 10_000
const DEFAULT_MAX_MESH_INDEX = 40
const DEFAULT_DETERMINISTIC_SEED = 0
const ACCEPTANCE_RESIDUAL_TOLERANCE = 1.0e-12
const NORMALIZED_LOWER = -1.0
const NORMALIZED_UPPER = 1.0

struct CallbackBudgetExceeded <: Exception
    limit::Int
end

Base.showerror(io::IO, error::CallbackBudgetExceeded) =
    print(io, "candidate callback budget ", error.limit, " exhausted")

mutable struct CallbackLedger
    calls::Int
    hard_limit::Int
    algorithm_limit::Int
    algorithm_calls::Int
    endpoint_screen_calls::Int
    bound_rejections::Int
    nonfinite_calls::Int
    semantic_invalid_calls::Int
    oracle_exceptions::Int
    extreme_barrier_calls::Int
    runner_exhausted::Bool
end

CallbackLedger(limit::Int) = CallbackLedger(
    0,
    limit,
    limit - 1,
    0,
    0,
    0,
    0,
    0,
    0,
    0,
    false,
)

struct BoundsMap
    lower::Vector{Float64}
    upper::Vector{Float64}
    origin::Vector{Float64}
    half_range::Vector{Float64}
end

struct MeritEvaluation
    normalized::Vector{Float64}
    physical::Vector{Float64}
    merit::Float64
    residual_linf::Float64
    valid::Bool
end

function _bounds_map(case::SolverExperimentCase, start::AbstractVector)
    length(start) == case.dimension || throw(DimensionMismatch("start has wrong dimension"))
    lower = collect(Float64, case.lower_bounds)
    upper = collect(Float64, case.upper_bounds)
    all(isfinite, lower) && all(isfinite, upper) ||
        throw(ArgumentError("bounds must be finite"))
    all(upper .> lower) || throw(ArgumentError("bounds must have positive width"))
    origin = lower ./ 2 .+ upper ./ 2
    half_range = upper ./ 2 .- lower ./ 2
    all(isfinite, origin) && all(value -> isfinite(value) && value > 0, half_range) ||
        throw(ArgumentError("normalized bounds map must be finite"))
    initial = collect(Float64, start)
    all(isfinite, initial) || throw(ArgumentError("start must be finite"))
    all(lower .<= initial .<= upper) ||
        throw(ArgumentError("start must lie within bounds"))
    normalized = (initial .- origin) ./ half_range
    all(NORMALIZED_LOWER .<= normalized .<= NORMALIZED_UPPER) ||
        throw(ArgumentError("normalized start must lie in the unit box"))
    return BoundsMap(lower, upper, origin, half_range), normalized
end

function _physical_coordinates(bounds::BoundsMap, normalized::AbstractVector)
    return bounds.origin .+ bounds.half_range .* normalized
end

function _prime_bases(dimension::Int)
    dimension > 0 || throw(ArgumentError("dimension must be positive"))
    primes = Int[]
    candidate = 2
    while length(primes) < dimension
        isprime = all(prime -> prime * prime > candidate || candidate % prime != 0, primes)
        isprime && push!(primes, candidate)
        candidate += candidate == 2 ? 1 : 2
    end
    return primes
end

function _radical_inverse(index::Int, base::Int)
    index >= 0 || throw(ArgumentError("Halton index must be nonnegative"))
    base >= 2 || throw(ArgumentError("Halton base must be at least two"))
    result = 0.0
    factor = inv(Float64(base))
    remaining = index
    while remaining > 0
        remaining, digit = divrem(remaining, base)
        result += digit * factor
        factor /= base
    end
    return result
end

"""Return the deterministic `t`th Halton vector in the first `dimension` prime bases."""
function halton_direction(dimension::Integer, t::Integer)
    n = Int(dimension)
    index = Int(t)
    n > 0 || throw(ArgumentError("dimension must be positive"))
    index > 0 || throw(ArgumentError("OrthoMADS uses a positive Halton index"))
    return Float64[_radical_inverse(index, base) for base in _prime_bases(n)]
end

_round_integer(value::Float64) = round(Int, value, RoundNearestTiesAway)

function _rounded_direction(unit_direction::Vector{Float64}, alpha::Float64)
    return Int[_round_integer(alpha * component) for component in unit_direction]
end

"""
Construct the adjusted integer Halton direction `q(t, ell)`.

It is the last value of `round(alpha * w_t)` whose squared Euclidean norm does not
exceed `2^abs(ell)`, where `w_t=(2h_t-e)/norm(2h_t-e)`.  Bisection is valid because
the norm of this rounded ray is a nondecreasing step function of `alpha`.
"""
function adjusted_halton_direction(dimension::Integer, t::Integer, ell::Integer)
    n = Int(dimension)
    mesh_index = Int(ell)
    n > 0 || throw(ArgumentError("dimension must be positive"))
    0 <= mesh_index <= 50 ||
        throw(ArgumentError("mesh index must be between zero and 50"))
    halton = halton_direction(n, t)
    ray = 2.0 .* halton .- 1.0
    ray_norm = norm(ray)
    isfinite(ray_norm) && ray_norm > 0 ||
        throw(ArgumentError("adjusted Halton ray must be nonzero"))
    unit = ray ./ ray_norm
    maximum_norm_squared = Int(1) << mesh_index

    lower = 0.0
    upper = 1.0
    while sum(abs2, _rounded_direction(unit, upper)) <= maximum_norm_squared
        lower = upper
        upper *= 2.0
        isfinite(upper) || error("failed to bracket adjusted Halton direction")
    end
    for _ in 1:96
        middle = lower / 2 + upper / 2
        candidate = _rounded_direction(unit, middle)
        if sum(abs2, candidate) <= maximum_norm_squared
            lower = middle
        else
            upper = middle
        end
    end
    adjusted = _rounded_direction(unit, lower)
    any(!iszero, adjusted) || error("adjusted Halton direction must be nonzero")
    sum(abs2, adjusted) <= maximum_norm_squared ||
        error("adjusted Halton direction exceeded its norm cap")
    return adjusted
end

"""Return the integer scaled-Householder OrthoMADS basis `||q||^2 I - 2qq'`."""
function orthomads_basis(dimension::Integer, t::Integer, ell::Integer)
    n = Int(dimension)
    q = adjusted_halton_direction(n, t, ell)
    norm_squared = sum(abs2, q)
    basis = norm_squared .* Matrix{Int}(I, n, n) .- 2 .* (q * transpose(q))
    return basis
end

"""Return the 2n normalized-coordinate poll steps `[delta_m H, -delta_m H]`."""
function orthomads_poll_steps(dimension::Integer, t::Integer, ell::Integer)
    mesh_index = Int(ell)
    0 <= mesh_index <= 50 ||
        throw(ArgumentError("mesh index must be between zero and 50"))
    basis = orthomads_basis(dimension, t, mesh_index)
    delta_mesh = mesh_index == 0 ? 1.0 : 4.0^(-mesh_index)
    positive = delta_mesh .* Float64.(basis)
    return hcat(positive, -positive)
end

function _charge!(ledger::CallbackLedger, role::Symbol)
    limit = role === :endpoint_screen ? ledger.hard_limit : ledger.algorithm_limit
    ledger.calls < limit || throw(CallbackBudgetExceeded(limit))
    ledger.calls += 1
    if role === :algorithm
        ledger.algorithm_calls += 1
    elseif role === :endpoint_screen
        ledger.endpoint_screen_calls += 1
    else
        throw(ArgumentError("unknown callback role: $role"))
    end
    return nothing
end

function _uncharge!(ledger::CallbackLedger, role::Symbol)
    ledger.calls -= 1
    role === :algorithm && (ledger.algorithm_calls -= 1)
    role === :endpoint_screen && (ledger.endpoint_screen_calls -= 1)
    return nothing
end

function _barrier_evaluation(normalized, physical)
    return MeritEvaluation(
        collect(Float64, normalized),
        collect(Float64, physical),
        Inf,
        Inf,
        false,
    )
end

function _evaluate_merit(
    case::SolverExperimentCase,
    bounds::BoundsMap,
    normalized::AbstractVector,
    residual_scales::Vector{Float64},
    ledger::CallbackLedger,
    role::Symbol,
)
    point = collect(Float64, normalized)
    length(point) == case.dimension ||
        throw(DimensionMismatch("normalized point has wrong dimension"))
    if !all(isfinite, point) ||
       !all(NORMALIZED_LOWER .<= point .<= NORMALIZED_UPPER)
        ledger.bound_rejections += 1
        return _barrier_evaluation(point, fill(NaN, case.dimension))
    end
    physical = _physical_coordinates(bounds, point)
    _charge!(ledger, role)
    evaluation = try
        evaluate_case(case, physical)
    catch error
        if error isa SolverExperimentBudgetExceeded
            ledger.runner_exhausted = true
            _uncharge!(ledger, role)
            rethrow()
        end
        error isa InterruptException && rethrow()
        ledger.oracle_exceptions += 1
        ledger.extreme_barrier_calls += 1
        return _barrier_evaluation(point, physical)
    end
    scaled = Float64[
        evaluation.residuals[index] / residual_scales[index] for
        index in eachindex(residual_scales)
    ]
    finite = evaluation.finite && all(isfinite, physical) && all(isfinite, scaled)
    semantics_valid = finite && evaluation.semantics_valid
    if !finite
        ledger.nonfinite_calls += 1
    elseif !semantics_valid
        ledger.semantic_invalid_calls += 1
    end
    if !semantics_valid
        ledger.extreme_barrier_calls += 1
        return _barrier_evaluation(point, physical)
    end
    merit = 0.5 * dot(scaled, scaled)
    if !isfinite(merit)
        ledger.nonfinite_calls += 1
        ledger.extreme_barrier_calls += 1
        return _barrier_evaluation(point, physical)
    end
    return MeritEvaluation(
        point,
        physical,
        merit,
        maximum(abs, scaled; init=0.0),
        true,
    )
end

function _diagnostic(
    ledger::CallbackLedger;
    iterations=0,
    mesh_index=0,
    halton_index=0,
    best_merit=Inf,
    best_residual_linf=Inf,
    screening_accepted=false,
    exception=nothing,
)
    fields = String[
        "callbacks=$(ledger.calls)",
        "callback_hard_limit=$(ledger.hard_limit)",
        "algorithm_callback_limit=$(ledger.algorithm_limit)",
        "endpoint_screen_reservation=1",
        "algorithm_callbacks=$(ledger.algorithm_calls)",
        "endpoint_screen_callbacks=$(ledger.endpoint_screen_calls)",
        "bound_extreme_barrier_rejections=$(ledger.bound_rejections)",
        "nonfinite_callbacks=$(ledger.nonfinite_calls)",
        "semantic_invalid_callbacks=$(ledger.semantic_invalid_calls)",
        "oracle_exceptions=$(ledger.oracle_exceptions)",
        "extreme_barrier_callbacks=$(ledger.extreme_barrier_calls)",
        "iterations=$iterations",
        "mesh_index=$mesh_index",
        "halton_index=$halton_index",
        "best_merit=$best_merit",
        "best_residual_linf=$best_residual_linf",
        "screening_accepted=$screening_accepted",
    ]
    exception === nothing || push!(
        fields,
        "exception=$(replace(sprint(showerror, exception), ';' => ','))",
    )
    return join(fields, ';')
end

function _failed_outcome(ledger::CallbackLedger, error)
    status = if ledger.runner_exhausted
        "runner_evaluation_budget_exhausted"
    elseif error isa CallbackBudgetExceeded
        "LOCAL_MAX_EVALUATIONS"
    else
        "exception:$(nameof(typeof(error)))"
    end
    return SolverAttemptOutcome(
        nothing;
        status,
        evaluations=ledger.calls,
        diagnostic=_diagnostic(ledger; exception=error),
    )
end

function _run_candidate(
    case::SolverExperimentCase,
    start::AbstractVector,
    max_callbacks::Int,
    max_iterations::Int,
    max_mesh_index::Int,
    deterministic_seed::Int,
)
    ledger = CallbackLedger(max_callbacks)
    try
        bounds, center = _bounds_map(case, start)
        residual_scales = collect(Float64, case.residual_scales)
        length(residual_scales) == case.residual_dimension ||
            throw(DimensionMismatch("residual scales have wrong dimension"))
        all(value -> isfinite(value) && value > 0, residual_scales) ||
            throw(ArgumentError("residual scales must be finite and positive"))

        incumbent = _evaluate_merit(
            case,
            bounds,
            center,
            residual_scales,
            ledger,
            :algorithm,
        )
        best_valid = incumbent.valid ? incumbent : nothing
        mesh_index = 0
        largest_mesh_index_seen = -1
        largest_halton_index = deterministic_seed + case.dimension
        halton_index = largest_halton_index
        iterations = 0
        status = "MAX_ITERATIONS"

        while iterations < max_iterations
            if incumbent.valid &&
               incumbent.residual_linf <= ACCEPTANCE_RESIDUAL_TOLERANCE
                status = "ORTHOMADS_ROOT"
                break
            end
            if ledger.calls >= ledger.algorithm_limit
                status = "LOCAL_MAX_EVALUATIONS"
                break
            end
            if mesh_index > max_mesh_index
                status = "MIN_POLL_SIZE_NONROOT"
                break
            end

            iterations += 1
            if mesh_index >= largest_mesh_index_seen
                halton_index = deterministic_seed + case.dimension + 1 + mesh_index
                largest_mesh_index_seen = max(largest_mesh_index_seen, mesh_index)
            else
                halton_index = largest_halton_index + 1
            end
            largest_halton_index = max(largest_halton_index, halton_index)
            steps = orthomads_poll_steps(case.dimension, halton_index, mesh_index)
            poll_best = nothing
            poll_complete = true

            for column in axes(steps, 2)
                if ledger.calls >= ledger.algorithm_limit
                    poll_complete = false
                    break
                end
                trial = _evaluate_merit(
                    case,
                    bounds,
                    incumbent.normalized .+ view(steps, :, column),
                    residual_scales,
                    ledger,
                    :algorithm,
                )
                if trial.valid &&
                   (poll_best === nothing || trial.merit < poll_best.merit)
                    poll_best = trial
                end
            end

            if !poll_complete
                # A complete 2n poll is the frozen comparison unit.  A point seen
                # only because it occurred before the callback cut must not gain
                # an order-dependent promotion over its unevaluated opposites.
                status = "LOCAL_MAX_EVALUATIONS"
                break
            end

            if poll_best !== nothing && poll_best.merit < incumbent.merit
                incumbent = poll_best
                best_valid = incumbent
                mesh_index = max(0, mesh_index - 1)
            else
                mesh_index += 1
            end
        end

        endpoint = best_valid === nothing ? nothing : best_valid.physical
        screening = nothing
        if best_valid !== nothing
            screening = _evaluate_merit(
                case,
                bounds,
                best_valid.normalized,
                residual_scales,
                ledger,
                :endpoint_screen,
            )
        end
        reported_accepted = screening !== nothing && screening.valid &&
                            screening.residual_linf <= ACCEPTANCE_RESIDUAL_TOLERANCE
        reported_accepted && (status = "ORTHOMADS_ROOT")
        return SolverAttemptOutcome(
            endpoint;
            status,
            reported_converged=reported_accepted,
            reported_accepted,
            evaluations=ledger.calls,
            iterations,
            diagnostic=_diagnostic(
                ledger;
                iterations,
                mesh_index,
                halton_index,
                best_merit=best_valid === nothing ? Inf : best_valid.merit,
                best_residual_linf=
                    best_valid === nothing ? Inf : best_valid.residual_linf,
                screening_accepted=reported_accepted,
            ),
        )
    catch error
        error isa InterruptException && rethrow()
        return _failed_outcome(ledger, error)
    end
end

"""Build the deterministic poll-only OrthoMADS/extreme-barrier local comparator."""
function orthomads_variant(;
    max_callbacks::Integer=DEFAULT_MAX_CALLBACKS,
    max_iterations::Integer=DEFAULT_MAX_ITERATIONS,
    max_mesh_index::Integer=DEFAULT_MAX_MESH_INDEX,
    deterministic_seed::Integer=DEFAULT_DETERMINISTIC_SEED,
)
    2 <= max_callbacks <= typemax(Int) ||
        throw(ArgumentError("max_callbacks must be at least two"))
    1 <= max_iterations <= typemax(Int) ||
        throw(ArgumentError("max_iterations must be positive"))
    0 <= max_mesh_index <= 50 ||
        throw(ArgumentError("max_mesh_index must be between zero and 50"))
    0 <= deterministic_seed <= typemax(Int) ||
        throw(ArgumentError("deterministic_seed must be nonnegative"))
    configuration = (;
        algorithm="poll-only-OrthoMADS-2n",
        coordinate_transform="midpoint-half-range-to-native-unit-box",
        normalized_lower=NORMALIZED_LOWER,
        normalized_upper=NORMALIZED_UPPER,
        merit="0.5*sum((declared-scaled-residual).^2)",
        constraint_policy="extreme-barrier",
        invalid_value="positive-infinity-no-pseudoresidual",
        direction_generator="Halton-adjusted-integer-scaled-Householder-2n",
        poll_policy="complete-poll-strict-merit-decrease",
        incomplete_poll_policy="discard-partial-poll-best-and-stop-at-local-cap",
        search_step=false,
        surrogate=false,
        residual_scaling="declared",
        max_callbacks=Int(max_callbacks),
        algorithm_callback_limit=Int(max_callbacks) - 1,
        endpoint_screen_reservation=1,
        max_iterations=Int(max_iterations),
        max_mesh_index=Int(max_mesh_index),
        deterministic_seed=Int(deterministic_seed),
        acceptance_residual_tolerance=ACCEPTANCE_RESIDUAL_TOLERANCE,
        reported_acceptance="finite-bounds-semantics-scaled-residual-linf",
        stationary_nonroot_policy="typed-nonanswer",
        all_callbacks_charged=true,
        identity_routing=false,
    )
    runner = (case, start) -> _run_candidate(
        case,
        start,
        Int(max_callbacks),
        Int(max_iterations),
        Int(max_mesh_index),
        Int(deterministic_seed),
    )
    return SolverVariant("ORTHOMADS-EB", runner; configuration)
end

export ACCEPTANCE_RESIDUAL_TOLERANCE,
    DEFAULT_DETERMINISTIC_SEED,
    DEFAULT_MAX_CALLBACKS,
    DEFAULT_MAX_ITERATIONS,
    DEFAULT_MAX_MESH_INDEX,
    EXPERIMENT_ID,
    NORMALIZED_LOWER,
    NORMALIZED_UPPER,
    adjusted_halton_direction,
    halton_direction,
    orthomads_basis,
    orthomads_poll_steps,
    orthomads_variant

end
