module GeoTargetNativeSafeguardedLM

using GeoTargetBenchmarks
using LinearAlgebra

const NATIVE_LM_CONVERGED = "NATIVE_LM_CONVERGED"
const NATIVE_LM_MAX_ITERATIONS = "NATIVE_LM_MAX_ITERATIONS"
const NATIVE_LM_MAX_EVALUATIONS = "LOCAL_MAX_EVALUATIONS"
const NATIVE_LM_NO_PROGRESS = "NATIVE_LM_NO_PROGRESS"
const NATIVE_LM_INITIAL_EVALUATION_INVALID = "NATIVE_LM_INITIAL_EVALUATION_INVALID"
const NATIVE_LM_JACOBIAN_FAILED = "NATIVE_LM_JACOBIAN_FAILED"

const DEFAULT_MAX_ITERATIONS = 120
const DEFAULT_MAX_EVALUATIONS = 600
const RESIDUAL_TOLERANCE = 1.0e-12

struct _NativeLMBudgetExceeded <: Exception
    limit::Int
end

Base.showerror(io::IO, error::_NativeLMBudgetExceeded) =
    print(io, "native LM evaluation budget ", error.limit, " exhausted")

struct _NativeLMOptions
    max_iterations::Int
    max_evaluations::Int
    finite_difference_step::Float64
    minimum_central_step_fraction::Float64
    jacobian_scale_floor::Float64
    initial_damping::Float64
    minimum_damping::Float64
    maximum_damping::Float64
    acceptance_ratio::Float64
    damping_decrease_floor::Float64
    initial_rejection_multiplier::Float64
    maximum_rejection_multiplier::Float64
    max_damping_trials_per_iteration::Int
    step_tolerance::Float64
end

mutable struct _NativeLMState
    calls::Int
    invalid_calls::Int
    accepted_trials::Int
    rejected_trials::Int
    invalid_trials::Int
    central_columns::Int
    one_sided_columns::Int
    iterations::Int
    damping::Float64
    rejection_multiplier::Float64
    last_residual_linf::Float64
    last_ratio::Float64
    last_scale_min::Float64
    last_scale_max::Float64
end

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
        throw(ArgumentError("bounds must be finite"))
    all(upper .> lower) || throw(ArgumentError("bounds must have positive width"))
    origin = lower ./ 2 .+ upper ./ 2
    half_range = upper ./ 2 .- lower ./ 2
    all(isfinite, origin) && all(value -> isfinite(value) && value > 0, half_range) ||
        throw(ArgumentError("bounds midpoint/half-range transform is not finite"))
    initial = collect(Float64, start)
    all(isfinite, initial) || throw(ArgumentError("start must be finite"))
    all(lower .<= initial .<= upper) ||
        throw(ArgumentError("start must lie within bounds"))
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
    state::_NativeLMState,
    evaluation_limit::Int,
)
    state.calls < evaluation_limit || throw(_NativeLMBudgetExceeded(evaluation_limit))
    all(-1.0 .<= normalized .<= 1.0) ||
        throw(ArgumentError("native LM attempted an out-of-box evaluation"))
    state.calls += 1
    evaluation = evaluate_case(case, _physical_coordinates(bounds, normalized))
    scaled = Float64[
        evaluation.residuals[index] / residual_scales[index] for
        index in 1:case.residual_dimension
    ]
    valid = evaluation.finite && evaluation.semantics_valid && all(isfinite, scaled)
    state.invalid_calls += !valid
    return scaled, valid
end

function _one_sided_column!(jacobian, column, side_residual, residual, step, direction)
    if direction > 0
        jacobian[:, column] .= (side_residual .- residual) ./ step
    else
        jacobian[:, column] .= (residual .- side_residual) ./ step
    end
    return jacobian
end

function _finite_difference_jacobian(
    case::SolverExperimentCase,
    bounds::_BoundsMap,
    normalized,
    residual,
    residual_scales,
    state::_NativeLMState,
    options::_NativeLMOptions,
)
    jacobian = zeros(Float64, case.residual_dimension, case.dimension)
    plus = copy(normalized)
    minus = copy(normalized)
    for column in 1:case.dimension
        nominal = options.finite_difference_step * max(1.0, abs(normalized[column]))
        plus_room = max(0.0, 1.0 - normalized[column])
        minus_room = max(0.0, normalized[column] + 1.0)
        central_step = min(nominal, plus_room, minus_room)
        central_usable = central_step >=
                         options.minimum_central_step_fraction * nominal

        if central_usable
            plus[column] = normalized[column] + central_step
            minus[column] = normalized[column] - central_step
            plus_residual, plus_valid = _scaled_evaluation(
                case,
                bounds,
                plus,
                residual_scales,
                state,
                options.max_evaluations,
            )
            minus_residual, minus_valid = _scaled_evaluation(
                case,
                bounds,
                minus,
                residual_scales,
                state,
                options.max_evaluations,
            )
            plus[column] = normalized[column]
            minus[column] = normalized[column]
            if plus_valid && minus_valid
                jacobian[:, column] .=
                    (plus_residual .- minus_residual) ./ (2 * central_step)
                state.central_columns += 1
            elseif plus_valid
                _one_sided_column!(
                    jacobian,
                    column,
                    plus_residual,
                    residual,
                    central_step,
                    1,
                )
                state.one_sided_columns += 1
            elseif minus_valid
                _one_sided_column!(
                    jacobian,
                    column,
                    minus_residual,
                    residual,
                    central_step,
                    -1,
                )
                state.one_sided_columns += 1
            else
                return nothing
            end
            continue
        end

        directions = plus_room >= minus_room ? (1, -1) : (-1, 1)
        column_completed = false
        for direction in directions
            room = direction > 0 ? plus_room : minus_room
            step = min(nominal, room)
            step > 0 || continue
            side = direction > 0 ? plus : minus
            side[column] = normalized[column] + direction * step
            side_residual, side_valid = _scaled_evaluation(
                case,
                bounds,
                side,
                residual_scales,
                state,
                options.max_evaluations,
            )
            side[column] = normalized[column]
            side_valid || continue
            _one_sided_column!(
                jacobian,
                column,
                side_residual,
                residual,
                step,
                direction,
            )
            state.one_sided_columns += 1
            column_completed = true
            break
        end
        column_completed || return nothing
    end
    return all(isfinite, jacobian) ? jacobian : nothing
end

function _diagonal_scaling(jacobian, floor::Float64)
    scaling = Float64[
        max(norm(view(jacobian, :, column)), floor) for
        column in axes(jacobian, 2)
    ]
    return all(isfinite, scaling) ? scaling : nothing
end

function _lm_step(jacobian, residual, scaling, damping::Float64)
    variable_count = length(scaling)
    damped_diagonal = sqrt(damping) .* scaling
    augmented = [jacobian; Matrix(Diagonal(damped_diagonal))]
    right_hand_side = [-residual; zeros(Float64, variable_count)]
    all(isfinite, augmented) && all(isfinite, right_hand_side) || return nothing
    step = try
        qr(augmented, ColumnNorm()) \ right_hand_side
    catch
        return nothing
    end
    return all(isfinite, step) ? step : nothing
end

function _increase_damping!(state::_NativeLMState, options::_NativeLMOptions)
    state.damping = clamp(
        state.damping * state.rejection_multiplier,
        options.minimum_damping,
        options.maximum_damping,
    )
    state.rejection_multiplier = min(
        state.rejection_multiplier * 2,
        options.maximum_rejection_multiplier,
    )
    return nothing
end

function _accept_damping!(state::_NativeLMState, options::_NativeLMOptions, ratio)
    factor = max(options.damping_decrease_floor, 1 - (2ratio - 1)^3)
    state.damping = clamp(
        state.damping * factor,
        options.minimum_damping,
        options.maximum_damping,
    )
    state.rejection_multiplier = options.initial_rejection_multiplier
    return nothing
end

function _diagnostic(state::_NativeLMState, options::_NativeLMOptions)
    return join(
        (
            "callbacks=$(state.calls)",
            "callback_limit=$(options.max_evaluations)",
            "iterations=$(state.iterations)",
            "residual_linf=$(state.last_residual_linf)",
            "damping=$(state.damping)",
            "last_ratio=$(state.last_ratio)",
            "accepted_trials=$(state.accepted_trials)",
            "rejected_trials=$(state.rejected_trials)",
            "invalid_trials=$(state.invalid_trials)",
            "invalid_callbacks=$(state.invalid_calls)",
            "central_columns=$(state.central_columns)",
            "one_sided_columns=$(state.one_sided_columns)",
            "diagonal_scale_min=$(state.last_scale_min)",
            "diagonal_scale_max=$(state.last_scale_max)",
        ),
        ';',
    )
end

function _outcome(
    status,
    case,
    bounds,
    normalized,
    state,
    options;
    converged=false,
    accepted=false,
)
    endpoint = normalized === nothing ? nothing : _physical_coordinates(bounds, normalized)
    return SolverAttemptOutcome(
        endpoint;
        status,
        reported_converged=converged,
        reported_accepted=accepted,
        evaluations=state.calls,
        iterations=state.iterations,
        diagnostic=_diagnostic(state, options),
    )
end

function _run_native_lm(
    case::SolverExperimentCase,
    start::AbstractVector,
    options::_NativeLMOptions,
)
    state = _NativeLMState(
        0,
        0,
        0,
        0,
        0,
        0,
        0,
        0,
        options.initial_damping,
        options.initial_rejection_multiplier,
        Inf,
        NaN,
        NaN,
        NaN,
    )
    bounds = nothing
    normalized = nothing
    try
        bounds, normalized = _bounds_map(case, start)
        residual_scales = collect(Float64, case.residual_scales)
        length(residual_scales) == case.residual_dimension ||
            throw(DimensionMismatch("residual scales have wrong dimension"))
        all(value -> isfinite(value) && value > 0, residual_scales) ||
            throw(ArgumentError("residual scales must be finite and positive"))

        residual, valid = _scaled_evaluation(
            case,
            bounds,
            normalized,
            residual_scales,
            state,
            options.max_evaluations,
        )
        valid || return _outcome(
            NATIVE_LM_INITIAL_EVALUATION_INVALID,
            case,
            bounds,
            normalized,
            state,
            options,
        )
        state.last_residual_linf = norm(residual, Inf)
        state.last_residual_linf <= RESIDUAL_TOLERANCE && return _outcome(
            NATIVE_LM_CONVERGED,
            case,
            bounds,
            normalized,
            state,
            options;
            converged=true,
            accepted=true,
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
                NATIVE_LM_JACOBIAN_FAILED,
                case,
                bounds,
                normalized,
                state,
                options,
            )
            scaling = _diagonal_scaling(jacobian, options.jacobian_scale_floor)
            scaling === nothing && return _outcome(
                NATIVE_LM_JACOBIAN_FAILED,
                case,
                bounds,
                normalized,
                state,
                options,
            )
            state.last_scale_min = minimum(scaling)
            state.last_scale_max = maximum(scaling)
            merit = 0.5 * dot(residual, residual)
            accepted_step = false

            for _ in 1:options.max_damping_trials_per_iteration
                step = _lm_step(jacobian, residual, scaling, state.damping)
                if step === nothing
                    state.rejected_trials += 1
                    _increase_damping!(state, options)
                    continue
                end
                trial_normalized = clamp.(normalized .+ step, -1.0, 1.0)
                feasible_step = trial_normalized .- normalized
                if norm(feasible_step, Inf) <= options.step_tolerance
                    return _outcome(
                        NATIVE_LM_NO_PROGRESS,
                        case,
                        bounds,
                        normalized,
                        state,
                        options,
                    )
                end
                linearized = residual .+ jacobian * feasible_step
                predicted_reduction = merit - 0.5 * dot(linearized, linearized)
                if !isfinite(predicted_reduction) || predicted_reduction <= 0
                    state.rejected_trials += 1
                    _increase_damping!(state, options)
                    continue
                end

                trial_residual, trial_valid = _scaled_evaluation(
                    case,
                    bounds,
                    trial_normalized,
                    residual_scales,
                    state,
                    options.max_evaluations,
                )
                if !trial_valid
                    state.invalid_trials += 1
                    state.rejected_trials += 1
                    _increase_damping!(state, options)
                    continue
                end
                trial_merit = 0.5 * dot(trial_residual, trial_residual)
                actual_reduction = merit - trial_merit
                ratio = actual_reduction / predicted_reduction
                state.last_ratio = ratio
                if isfinite(ratio) && actual_reduction > 0 &&
                   ratio >= options.acceptance_ratio
                    normalized = trial_normalized
                    residual = trial_residual
                    state.accepted_trials += 1
                    state.last_residual_linf = norm(residual, Inf)
                    _accept_damping!(state, options, ratio)
                    accepted_step = true
                    state.last_residual_linf <= RESIDUAL_TOLERANCE && return _outcome(
                        NATIVE_LM_CONVERGED,
                        case,
                        bounds,
                        normalized,
                        state,
                        options;
                        converged=true,
                        accepted=true,
                    )
                    break
                end
                state.rejected_trials += 1
                _increase_damping!(state, options)
            end
            accepted_step || return _outcome(
                NATIVE_LM_NO_PROGRESS,
                case,
                bounds,
                normalized,
                state,
                options,
            )
        end
        return _outcome(
            NATIVE_LM_MAX_ITERATIONS,
            case,
            bounds,
            normalized,
            state,
            options,
        )
    catch error
        error isa SolverExperimentBudgetExceeded && rethrow()
        if error isa _NativeLMBudgetExceeded
            return _outcome(
                NATIVE_LM_MAX_EVALUATIONS,
                case,
                bounds,
                normalized,
                state,
                options,
            )
        end
        endpoint = normalized === nothing ? nothing : _physical_coordinates(bounds, normalized)
        return SolverAttemptOutcome(
            endpoint;
            status="NATIVE_LM_EXCEPTION:$(nameof(typeof(error)))",
            evaluations=state.calls,
            iterations=state.iterations,
            diagnostic="$(_diagnostic(state, options));exception=$(sprint(showerror, error))",
        )
    end
end

function _validate_options(options::_NativeLMOptions)
    options.max_iterations > 0 || throw(ArgumentError("max_iterations must be positive"))
    options.max_evaluations > 0 || throw(ArgumentError("max_evaluations must be positive"))
    options.max_damping_trials_per_iteration > 0 ||
        throw(ArgumentError("max_damping_trials_per_iteration must be positive"))
    positive = (
        options.finite_difference_step,
        options.jacobian_scale_floor,
        options.initial_damping,
        options.minimum_damping,
        options.maximum_damping,
        options.initial_rejection_multiplier,
        options.maximum_rejection_multiplier,
        options.step_tolerance,
    )
    all(value -> isfinite(value) && value > 0, positive) ||
        throw(ArgumentError("native LM scales and safeguards must be finite and positive"))
    0 < options.minimum_central_step_fraction <= 1 ||
        throw(ArgumentError("minimum_central_step_fraction must be in (0, 1]"))
    0 < options.acceptance_ratio < 1 ||
        throw(ArgumentError("acceptance_ratio must be in (0, 1)"))
    0 < options.damping_decrease_floor < 1 ||
        throw(ArgumentError("damping_decrease_floor must be in (0, 1)"))
    options.minimum_damping <= options.initial_damping <= options.maximum_damping ||
        throw(ArgumentError("initial_damping must lie within damping bounds"))
    options.initial_rejection_multiplier > 1 ||
        throw(ArgumentError("initial_rejection_multiplier must exceed one"))
    options.maximum_rejection_multiplier >= options.initial_rejection_multiplier ||
        throw(ArgumentError("maximum_rejection_multiplier is too small"))
    return options
end

"""Build the truth-blind native scale-aware safeguarded LM candidate."""
function native_safeguarded_lm_variant(;
    name::AbstractString="native-safeguarded-lm",
    max_iterations::Integer=DEFAULT_MAX_ITERATIONS,
    max_evaluations::Integer=DEFAULT_MAX_EVALUATIONS,
    finite_difference_step::Real=cbrt(eps(Float64)),
    minimum_central_step_fraction::Real=0.25,
    jacobian_scale_floor::Real=sqrt(eps(Float64)),
    initial_damping::Real=1.0e-3,
    minimum_damping::Real=eps(Float64),
    maximum_damping::Real=1.0e30,
    acceptance_ratio::Real=1.0e-4,
    damping_decrease_floor::Real=1 / 3,
    initial_rejection_multiplier::Real=2.0,
    maximum_rejection_multiplier::Real=2.0^20,
    max_damping_trials_per_iteration::Integer=12,
    step_tolerance::Real=eps(Float64)^(4 / 5),
)
    max_iterations <= typemax(Int) || throw(ArgumentError("max_iterations is too large"))
    max_evaluations <= typemax(Int) || throw(ArgumentError("max_evaluations is too large"))
    max_damping_trials_per_iteration <= typemax(Int) ||
        throw(ArgumentError("max_damping_trials_per_iteration is too large"))
    options = _validate_options(_NativeLMOptions(
        Int(max_iterations),
        Int(max_evaluations),
        Float64(finite_difference_step),
        Float64(minimum_central_step_fraction),
        Float64(jacobian_scale_floor),
        Float64(initial_damping),
        Float64(minimum_damping),
        Float64(maximum_damping),
        Float64(acceptance_ratio),
        Float64(damping_decrease_floor),
        Float64(initial_rejection_multiplier),
        Float64(maximum_rejection_multiplier),
        Int(max_damping_trials_per_iteration),
        Float64(step_tolerance),
    ))
    configuration = (;
        implementation="native-scale-aware-safeguarded-lm-v1",
        coordinate_scaling="bounds-midpoint-half-range",
        normalized_lower=-1.0,
        normalized_upper=1.0,
        residual_scaling="declared",
        residual_tolerance=RESIDUAL_TOLERANCE,
        derivative="bounds-aware-central-with-one-sided-fallback",
        finite_difference_step=options.finite_difference_step,
        minimum_central_step_fraction=options.minimum_central_step_fraction,
        diagonal_scaling="max-jacobian-column-norm-floor",
        jacobian_scale_floor=options.jacobian_scale_floor,
        linear_system="augmented-J-sqrt-lambda-D-CPQR",
        initial_damping=options.initial_damping,
        minimum_damping=options.minimum_damping,
        maximum_damping=options.maximum_damping,
        damping_update="nielsen-actual-predicted-reduction-ratio",
        acceptance_ratio=options.acceptance_ratio,
        damping_decrease_floor=options.damping_decrease_floor,
        initial_rejection_multiplier=options.initial_rejection_multiplier,
        maximum_rejection_multiplier=options.maximum_rejection_multiplier,
        invalid_trial_policy="reject-and-increase-damping",
        box_step="componentwise-clipped-normalized-step",
        max_damping_trials_per_iteration=options.max_damping_trials_per_iteration,
        step_tolerance=options.step_tolerance,
        max_iterations=options.max_iterations,
        max_evaluations=options.max_evaluations,
        reported_acceptance="residual-tolerance-only",
    )
    runner = (case, start) -> _run_native_lm(case, start, options)
    return SolverVariant(name, runner; configuration)
end

export DEFAULT_MAX_EVALUATIONS,
    DEFAULT_MAX_ITERATIONS,
    NATIVE_LM_CONVERGED,
    NATIVE_LM_INITIAL_EVALUATION_INVALID,
    NATIVE_LM_JACOBIAN_FAILED,
    NATIVE_LM_MAX_EVALUATIONS,
    NATIVE_LM_MAX_ITERATIONS,
    NATIVE_LM_NO_PROGRESS,
    RESIDUAL_TOLERANCE,
    native_safeguarded_lm_variant

end
