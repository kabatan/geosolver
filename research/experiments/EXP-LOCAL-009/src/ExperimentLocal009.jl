module ExperimentLocal009

using GeoTargetBenchmarks
using LinearAlgebra

const EXPERIMENT_ID = "EXP-LOCAL-009"
const VARIANT_NAME = "RESTORING-GN-CPQR"

const STATUS_CONVERGED = "RESTORING_GN_CONVERGED"
const STATUS_MAX_ITERATIONS = "RESTORING_GN_MAX_ITERATIONS"
const STATUS_MAX_EVALUATIONS = "LOCAL_MAX_EVALUATIONS"
const STATUS_INITIAL_INFEASIBLE = "RESTORING_GN_INITIAL_INFEASIBLE"
const STATUS_JACOBIAN_FAILED = "RESTORING_GN_JACOBIAN_FAILED"
const STATUS_RANK_STALLED = "RESTORING_GN_RANK_STALLED"
const STATUS_LINE_SEARCH_FAILED = "RESTORING_GN_LINE_SEARCH_FAILED"

const DEFAULT_MAX_ITERATIONS = 120
const DEFAULT_MAX_EVALUATIONS = 600
const RESIDUAL_TOLERANCE = 1.0e-12
const DEFAULT_FINITE_DIFFERENCE_STEP = cbrt(eps(Float64))
const DEFAULT_MAX_FD_BACKOFFS = 16
const DEFAULT_MAX_LINE_SEARCH_STEPS = 24
const DEFAULT_BACKTRACK_FACTOR = 0.5
const DEFAULT_ARMIJO_COEFFICIENT = 1.0e-4
const DEFAULT_MODEL_RATIO_FLOOR = 1.0e-4
const DEFAULT_STEP_TOLERANCE = eps(Float64)^(4 / 5)

struct _CandidateBudgetExceeded <: Exception
    limit::Int
end

Base.showerror(io::IO, error::_CandidateBudgetExceeded) =
    print(io, "restoring GN evaluation budget ", error.limit, " exhausted")

struct _Options
    max_iterations::Int
    max_evaluations::Int
    finite_difference_step::Float64
    max_fd_backoffs::Int
    max_line_search_steps::Int
    backtrack_factor::Float64
    armijo_coefficient::Float64
    model_ratio_floor::Float64
    step_tolerance::Float64
end

mutable struct _State
    calls::Int
    runner_exhausted::Bool
    invalid_calls::Int
    nonfinite_calls::Int
    semantic_invalid_calls::Int
    oracle_exceptions::Int
    restoration_trials::Int
    restoration_invalid_trials::Int
    restored_starts::Int
    fd_columns::Int
    fd_sign_reversals::Int
    fd_radius_backoffs::Int
    fd_invalid_trials::Int
    accepted_steps::Int
    rejected_steps::Int
    invalid_line_search_trials::Int
    model_rejections::Int
    armijo_rejections::Int
    iterations::Int
    last_rank::Int
    last_rank_threshold::Float64
    last_residual_linf::Float64
    last_model_ratio::Float64
    last_step_linf::Float64
end

_State() = _State(
    0,
    false,
    0,
    0,
    0,
    0,
    0,
    0,
    0,
    0,
    0,
    0,
    0,
    0,
    0,
    0,
    0,
    0,
    0,
    -1,
    NaN,
    Inf,
    NaN,
    NaN,
)

struct _BoundsMap
    lower::Vector{Float64}
    upper::Vector{Float64}
    origin::Vector{Float64}
    half_range::Vector{Float64}
end

function _bounds_map(case::SolverExperimentCase, start::AbstractVector)
    length(start) == case.dimension || throw(DimensionMismatch("start has wrong dimension"))
    lower = collect(Float64, case.lower_bounds)
    upper = collect(Float64, case.upper_bounds)
    length(lower) == length(upper) == case.dimension ||
        throw(DimensionMismatch("bounds have wrong dimension"))
    all(isfinite, lower) && all(isfinite, upper) ||
        throw(ArgumentError("all bounds must be finite"))
    all(upper .> lower) || throw(ArgumentError("bounds must have positive width"))
    origin = lower ./ 2 .+ upper ./ 2
    half_range = upper ./ 2 .- lower ./ 2
    all(isfinite, origin) && all(value -> isfinite(value) && value > 0, half_range) ||
        throw(ArgumentError("midpoint/half-range map must be finite"))
    initial = collect(Float64, start)
    all(isfinite, initial) || throw(ArgumentError("start must be finite"))
    all(lower .<= initial .<= upper) ||
        throw(ArgumentError("start must lie in the declared box"))
    normalized = clamp.((initial .- origin) ./ half_range, -1.0, 1.0)
    return _BoundsMap(lower, upper, origin, half_range), normalized
end

function _physical_coordinates(bounds::_BoundsMap, normalized)
    physical = bounds.origin .+ bounds.half_range .* normalized
    return clamp.(physical, bounds.lower, bounds.upper)
end

function _scaled_evaluation(
    case::SolverExperimentCase,
    bounds::_BoundsMap,
    normalized,
    residual_scales,
    state::_State,
    options::_Options,
)
    state.calls < options.max_evaluations ||
        throw(_CandidateBudgetExceeded(options.max_evaluations))
    length(normalized) == case.dimension ||
        throw(DimensionMismatch("normalized point has wrong dimension"))
    all(isfinite, normalized) && all(-1.0 .<= normalized .<= 1.0) ||
        throw(ArgumentError("candidate attempted an invalid normalized point"))
    state.calls += 1
    evaluation = try
        evaluate_case(case, _physical_coordinates(bounds, normalized))
    catch error
        if error isa SolverExperimentBudgetExceeded
            state.calls -= 1
            state.runner_exhausted = true
            rethrow()
        end
        error isa InterruptException && rethrow()
        state.oracle_exceptions += 1
        state.invalid_calls += 1
        return nothing, false
    end
    scaled = Float64[
        evaluation.residuals[index] / residual_scales[index] for
        index in eachindex(residual_scales)
    ]
    finite = evaluation.finite && all(isfinite, scaled)
    valid = finite && evaluation.semantics_valid
    state.nonfinite_calls += !finite
    state.semantic_invalid_calls += finite && !evaluation.semantics_valid
    state.invalid_calls += !valid
    return scaled, valid
end

function _restore_initial_point(
    case,
    bounds,
    initial,
    residual_scales,
    state,
    options,
)
    residual, valid = _scaled_evaluation(
        case,
        bounds,
        initial,
        residual_scales,
        state,
        options,
    )
    valid && return initial, residual, true

    midpoint = zeros(Float64, length(initial))
    initial == midpoint && return initial, nothing, false
    midpoint_residual, midpoint_valid = _scaled_evaluation(
        case,
        bounds,
        midpoint,
        residual_scales,
        state,
        options,
    )
    state.restoration_trials += 1
    state.restoration_invalid_trials += !midpoint_valid
    midpoint_valid || return initial, nothing, false

    feasible = midpoint
    feasible_residual = midpoint_residual
    infeasible = copy(initial)
    while norm(infeasible .- feasible, Inf) > options.finite_difference_step
        trial = feasible ./ 2 .+ infeasible ./ 2
        trial == feasible && break
        trial_residual, trial_valid = _scaled_evaluation(
            case,
            bounds,
            trial,
            residual_scales,
            state,
            options,
        )
        state.restoration_trials += 1
        if trial_valid
            feasible = trial
            feasible_residual = trial_residual
        else
            state.restoration_invalid_trials += 1
            infeasible = trial
        end
    end
    state.restored_starts += 1
    return feasible, feasible_residual, true
end

function _finite_difference_column(
    case,
    bounds,
    normalized,
    residual,
    residual_scales,
    column,
    state,
    options,
)
    nominal = options.finite_difference_step * max(1.0, abs(normalized[column]))
    plus_room = max(0.0, 1.0 - normalized[column])
    minus_room = max(0.0, normalized[column] + 1.0)
    preferred = plus_room >= minus_room ? 1 : -1
    trial = copy(normalized)
    for backoff in 0:options.max_fd_backoffs
        step = ldexp(nominal, -backoff)
        step > 0 && normalized[column] + step > normalized[column] &&
            normalized[column] - step < normalized[column] || continue
        for (side_index, direction) in enumerate((preferred, -preferred))
            room = direction > 0 ? plus_room : minus_room
            room >= step || continue
            trial[column] = normalized[column] + direction * step
            side_residual, side_valid = _scaled_evaluation(
                case,
                bounds,
                trial,
                residual_scales,
                state,
                options,
            )
            trial[column] = normalized[column]
            if side_valid
                state.fd_columns += 1
                state.fd_sign_reversals += side_index == 2
                state.fd_radius_backoffs += backoff
                derivative = direction > 0 ?
                             (side_residual .- residual) ./ step :
                             (residual .- side_residual) ./ step
                return all(isfinite, derivative) ? derivative : nothing
            end
            state.fd_invalid_trials += 1
        end
    end
    return nothing
end

function _finite_difference_jacobian(
    case,
    bounds,
    normalized,
    residual,
    residual_scales,
    state,
    options,
)
    jacobian = zeros(Float64, case.residual_dimension, case.dimension)
    for column in 1:case.dimension
        derivative = _finite_difference_column(
            case,
            bounds,
            normalized,
            residual,
            residual_scales,
            column,
            state,
            options,
        )
        derivative === nothing && return nothing
        jacobian[:, column] .= derivative
    end
    return all(isfinite, jacobian) ? jacobian : nothing
end

function _cpqr_step(jacobian, residual, state::_State)
    all(isfinite, jacobian) && all(isfinite, residual) || return nothing
    factorization = try
        qr(jacobian, ColumnNorm())
    catch
        return nothing
    end
    triangular = Matrix(factorization.R)
    diagonal_count = min(size(triangular)...)
    diagonal_count > 0 || return nothing
    diagonal = abs.(diag(view(triangular, 1:diagonal_count, 1:diagonal_count)))
    maximum_diagonal = maximum(diagonal; init=0.0)
    threshold = max(size(jacobian)...) * eps(Float64) * maximum_diagonal
    rank = 0
    for value in diagonal
        value > threshold || break
        rank += 1
    end
    state.last_rank = rank
    state.last_rank_threshold = threshold
    rank > 0 || return nothing

    transformed = factorization.Q' * residual
    permuted_step = zeros(Float64, size(jacobian, 2))
    permuted_step[1:rank] .= try
        -(view(triangular, 1:rank, 1:rank) \ view(transformed, 1:rank))
    catch
        return nothing
    end
    step = zeros(Float64, size(jacobian, 2))
    step[factorization.p] .= permuted_step
    all(isfinite, step) || return nothing

    gradient = jacobian' * residual
    directional_derivative = dot(gradient, step)
    isfinite(directional_derivative) && directional_derivative < 0 || return nothing
    return step
end

function _line_search(
    case,
    bounds,
    normalized,
    residual,
    jacobian,
    step,
    residual_scales,
    state,
    options,
)
    merit = 0.5 * dot(residual, residual)
    gradient = jacobian' * residual
    alpha = 1.0
    for _ in 1:options.max_line_search_steps
        trial = clamp.(normalized .+ alpha .* step, -1.0, 1.0)
        effective_step = trial .- normalized
        step_linf = norm(effective_step, Inf)
        state.last_step_linf = step_linf
        step_linf > options.step_tolerance || break

        directional_derivative = dot(gradient, effective_step)
        linearized = residual .+ jacobian * effective_step
        predicted_reduction = merit - 0.5 * dot(linearized, linearized)
        if !isfinite(directional_derivative) || directional_derivative >= 0 ||
           !isfinite(predicted_reduction) || predicted_reduction <= 0
            state.model_rejections += 1
            state.rejected_steps += 1
            alpha *= options.backtrack_factor
            continue
        end

        trial_residual, trial_valid = _scaled_evaluation(
            case,
            bounds,
            trial,
            residual_scales,
            state,
            options,
        )
        if !trial_valid
            state.invalid_line_search_trials += 1
            state.rejected_steps += 1
            alpha *= options.backtrack_factor
            continue
        end
        trial_merit = 0.5 * dot(trial_residual, trial_residual)
        actual_reduction = merit - trial_merit
        ratio = actual_reduction / predicted_reduction
        state.last_model_ratio = ratio
        armijo_bound = merit + options.armijo_coefficient * directional_derivative
        if isfinite(ratio) && trial_merit <= armijo_bound &&
           ratio >= options.model_ratio_floor
            state.accepted_steps += 1
            return trial, trial_residual, true
        end
        state.armijo_rejections += 1
        state.rejected_steps += 1
        alpha *= options.backtrack_factor
    end
    return normalized, residual, false
end

function _diagnostic(state::_State, options::_Options)
    return join((
        "callbacks=$(state.calls)",
        "callback_limit=$(options.max_evaluations)",
        "iterations=$(state.iterations)",
        "residual_linf=$(state.last_residual_linf)",
        "runner_exhausted=$(state.runner_exhausted)",
        "invalid_callbacks=$(state.invalid_calls)",
        "nonfinite_callbacks=$(state.nonfinite_calls)",
        "semantic_invalid_callbacks=$(state.semantic_invalid_calls)",
        "oracle_exceptions=$(state.oracle_exceptions)",
        "restoration_trials=$(state.restoration_trials)",
        "restoration_invalid_trials=$(state.restoration_invalid_trials)",
        "restored_starts=$(state.restored_starts)",
        "fd_columns=$(state.fd_columns)",
        "fd_sign_reversals=$(state.fd_sign_reversals)",
        "fd_radius_backoffs=$(state.fd_radius_backoffs)",
        "fd_invalid_trials=$(state.fd_invalid_trials)",
        "accepted_steps=$(state.accepted_steps)",
        "rejected_steps=$(state.rejected_steps)",
        "invalid_line_search_trials=$(state.invalid_line_search_trials)",
        "model_rejections=$(state.model_rejections)",
        "armijo_rejections=$(state.armijo_rejections)",
        "last_rank=$(state.last_rank)",
        "last_rank_threshold=$(state.last_rank_threshold)",
        "last_model_ratio=$(state.last_model_ratio)",
        "last_step_linf=$(state.last_step_linf)",
    ), ';')
end

function _outcome(status, bounds, normalized, state, options; converged=false)
    endpoint = bounds === nothing || normalized === nothing ?
               nothing : _physical_coordinates(bounds, normalized)
    return SolverAttemptOutcome(
        endpoint;
        status,
        reported_converged=converged,
        reported_accepted=converged,
        evaluations=state.calls,
        iterations=state.iterations,
        diagnostic=_diagnostic(state, options),
    )
end

function _run_candidate(
    case::SolverExperimentCase,
    start::AbstractVector,
    options::_Options,
)
    state = _State()
    bounds = nothing
    normalized = nothing
    try
        bounds, initial = _bounds_map(case, start)
        residual_scales = collect(Float64, case.residual_scales)
        length(residual_scales) == case.residual_dimension ||
            throw(DimensionMismatch("residual scales have wrong dimension"))
        all(value -> isfinite(value) && value > 0, residual_scales) ||
            throw(ArgumentError("residual scales must be finite and positive"))

        normalized, residual, feasible = _restore_initial_point(
            case,
            bounds,
            initial,
            residual_scales,
            state,
            options,
        )
        feasible || return _outcome(
            STATUS_INITIAL_INFEASIBLE,
            bounds,
            normalized,
            state,
            options,
        )
        state.last_residual_linf = norm(residual, Inf)
        state.last_residual_linf <= RESIDUAL_TOLERANCE && return _outcome(
            STATUS_CONVERGED,
            bounds,
            normalized,
            state,
            options;
            converged=true,
        )

        for iteration in 1:options.max_iterations
            state.iterations = iteration
            jacobian = _finite_difference_jacobian(
                case,
                bounds,
                normalized,
                residual,
                residual_scales,
                state,
                options,
            )
            jacobian === nothing && return _outcome(
                STATUS_JACOBIAN_FAILED,
                bounds,
                normalized,
                state,
                options,
            )
            step = _cpqr_step(jacobian, residual, state)
            step === nothing && return _outcome(
                STATUS_RANK_STALLED,
                bounds,
                normalized,
                state,
                options,
            )
            normalized, residual, accepted = _line_search(
                case,
                bounds,
                normalized,
                residual,
                jacobian,
                step,
                residual_scales,
                state,
                options,
            )
            accepted || return _outcome(
                STATUS_LINE_SEARCH_FAILED,
                bounds,
                normalized,
                state,
                options,
            )
            state.last_residual_linf = norm(residual, Inf)
            state.last_residual_linf <= RESIDUAL_TOLERANCE && return _outcome(
                STATUS_CONVERGED,
                bounds,
                normalized,
                state,
                options;
                converged=true,
            )
        end
        return _outcome(
            STATUS_MAX_ITERATIONS,
            bounds,
            normalized,
            state,
            options,
        )
    catch error
        error isa SolverExperimentBudgetExceeded && rethrow()
        error isa InterruptException && rethrow()
        if error isa _CandidateBudgetExceeded
            return _outcome(
                STATUS_MAX_EVALUATIONS,
                bounds,
                normalized,
                state,
                options,
            )
        end
        outcome = _outcome(
            "RESTORING_GN_EXCEPTION:$(nameof(typeof(error)))",
            bounds,
            normalized,
            state,
            options,
        )
        return SolverAttemptOutcome(
            outcome.endpoint;
            status=outcome.status,
            evaluations=outcome.evaluations,
            iterations=outcome.iterations,
            diagnostic="$(outcome.diagnostic);exception=$(sprint(showerror, error))",
        )
    end
end

function _validate_options(options::_Options)
    options.max_iterations > 0 || throw(ArgumentError("max_iterations must be positive"))
    options.max_evaluations > 0 || throw(ArgumentError("max_evaluations must be positive"))
    options.max_fd_backoffs >= 0 ||
        throw(ArgumentError("max_fd_backoffs must be nonnegative"))
    options.max_line_search_steps > 0 ||
        throw(ArgumentError("max_line_search_steps must be positive"))
    all(isfinite, (
        options.finite_difference_step,
        options.backtrack_factor,
        options.armijo_coefficient,
        options.model_ratio_floor,
        options.step_tolerance,
    )) || throw(ArgumentError("numeric options must be finite"))
    options.finite_difference_step > 0 ||
        throw(ArgumentError("finite_difference_step must be positive"))
    0 < options.backtrack_factor < 1 ||
        throw(ArgumentError("backtrack_factor must lie in (0, 1)"))
    0 < options.armijo_coefficient < 1 ||
        throw(ArgumentError("armijo_coefficient must lie in (0, 1)"))
    0 <= options.model_ratio_floor < 1 ||
        throw(ArgumentError("model_ratio_floor must lie in [0, 1)"))
    options.step_tolerance > 0 || throw(ArgumentError("step_tolerance must be positive"))
    return options
end

"""Build the truth-blind feasibility-restoring line-search Gauss--Newton candidate."""
function restoring_gn_variant(;
    name::AbstractString=VARIANT_NAME,
    max_iterations::Integer=DEFAULT_MAX_ITERATIONS,
    max_evaluations::Integer=DEFAULT_MAX_EVALUATIONS,
    finite_difference_step::Real=DEFAULT_FINITE_DIFFERENCE_STEP,
    max_fd_backoffs::Integer=DEFAULT_MAX_FD_BACKOFFS,
    max_line_search_steps::Integer=DEFAULT_MAX_LINE_SEARCH_STEPS,
    backtrack_factor::Real=DEFAULT_BACKTRACK_FACTOR,
    armijo_coefficient::Real=DEFAULT_ARMIJO_COEFFICIENT,
    model_ratio_floor::Real=DEFAULT_MODEL_RATIO_FLOOR,
    step_tolerance::Real=DEFAULT_STEP_TOLERANCE,
)
    max_iterations <= typemax(Int) || throw(ArgumentError("max_iterations is too large"))
    max_evaluations <= typemax(Int) || throw(ArgumentError("max_evaluations is too large"))
    max_fd_backoffs <= typemax(Int) || throw(ArgumentError("max_fd_backoffs is too large"))
    max_line_search_steps <= typemax(Int) ||
        throw(ArgumentError("max_line_search_steps is too large"))
    options = _validate_options(_Options(
        Int(max_iterations),
        Int(max_evaluations),
        Float64(finite_difference_step),
        Int(max_fd_backoffs),
        Int(max_line_search_steps),
        Float64(backtrack_factor),
        Float64(armijo_coefficient),
        Float64(model_ratio_floor),
        Float64(step_tolerance),
    ))
    configuration = (;
        implementation="experiment-local-restoring-line-search-gn-cpqr-v1",
        coordinate_map="direct-midpoint-half-range-normalized-box",
        normalized_lower=-1.0,
        normalized_upper=1.0,
        residual_scaling="declared",
        residual_tolerance=RESIDUAL_TOLERANCE,
        initial_feasibility="center-anchor-segment-bisection-to-fd-resolution",
        derivative="preferred-forward-one-sided-with-symmetric-sign-and-radius-backoff",
        finite_difference_step=options.finite_difference_step,
        max_fd_backoffs=options.max_fd_backoffs,
        linear_step="rank-revealing-cpqr-truncated-gauss-newton",
        rank_threshold="max(m,n)*eps*max(abs(diag(R)))",
        box_step="componentwise-clipped-effective-step",
        globalization="backtracking-armijo-plus-actual-predicted-model-ratio",
        backtrack_factor=options.backtrack_factor,
        armijo_coefficient=options.armijo_coefficient,
        model_ratio_floor=options.model_ratio_floor,
        max_line_search_steps=options.max_line_search_steps,
        invalid_trial_policy="charged-reject-and-backtrack-without-pseudoresidual",
        step_tolerance=options.step_tolerance,
        max_iterations=options.max_iterations,
        max_evaluations=options.max_evaluations,
        callback_ledger="all-candidate-evaluations-charged-before-call",
        reported_acceptance="diagnostic-residual-only-common-assessor-authoritative",
        fallback="none",
        identity_routing=false,
    )
    runner = (case, start) -> _run_candidate(case, start, options)
    return SolverVariant(name, runner; configuration)
end

export DEFAULT_ARMIJO_COEFFICIENT,
    DEFAULT_BACKTRACK_FACTOR,
    DEFAULT_FINITE_DIFFERENCE_STEP,
    DEFAULT_MAX_EVALUATIONS,
    DEFAULT_MAX_FD_BACKOFFS,
    DEFAULT_MAX_ITERATIONS,
    DEFAULT_MAX_LINE_SEARCH_STEPS,
    DEFAULT_MODEL_RATIO_FLOOR,
    DEFAULT_STEP_TOLERANCE,
    EXPERIMENT_ID,
    RESIDUAL_TOLERANCE,
    STATUS_CONVERGED,
    STATUS_INITIAL_INFEASIBLE,
    STATUS_JACOBIAN_FAILED,
    STATUS_LINE_SEARCH_FAILED,
    STATUS_MAX_EVALUATIONS,
    STATUS_MAX_ITERATIONS,
    STATUS_RANK_STALLED,
    VARIANT_NAME,
    restoring_gn_variant

end
