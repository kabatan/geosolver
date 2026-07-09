@enum LocalSolveStatus::UInt8 begin
    LOCAL_CONVERGED = 0
    LOCAL_MAX_ITERATIONS = 1
    LOCAL_MAX_EVALUATIONS = 2
    LOCAL_DEADLINE = 3
    LOCAL_CANCELLED = 4
    LOCAL_NO_PROGRESS = 5
    LOCAL_EVALUATION_FAILED = 6
end

struct LocalSolveOptions
    max_iterations::Int
    max_evaluations::Int
    residual_tolerance::Float64
    step_tolerance::Float64
    finite_difference_step::Float64
    initial_damping::Float64
    damping_increase::Float64
    damping_decrease::Float64

    function LocalSolveOptions(
        ;
        max_iterations::Integer = 250,
        max_evaluations::Integer = 2_000,
        residual_tolerance::Real = sqrt(eps(Float64)),
        step_tolerance::Real = eps(Float64)^(4 / 5),
        finite_difference_step::Real = cbrt(eps(Float64)),
        initial_damping::Real = 1.0e-3,
        damping_increase::Real = 10.0,
        damping_decrease::Real = 1 / 3,
    )
        max_iterations > 0 || throw(ArgumentError("max_iterations must be positive"))
        max_evaluations > 0 || throw(ArgumentError("max_evaluations must be positive"))
        values = (
            residual_tolerance,
            step_tolerance,
            finite_difference_step,
            initial_damping,
            damping_increase,
            damping_decrease,
        )
        all(value -> isfinite(value) && value > 0, values) || throw(
            ArgumentError("all local-solver scales and tolerances must be finite and positive"),
        )
        damping_increase > 1 || throw(ArgumentError("damping_increase must exceed one"))
        damping_decrease < 1 || throw(ArgumentError("damping_decrease must be below one"))
        return new(
            Int(max_iterations),
            Int(max_evaluations),
            Float64(residual_tolerance),
            Float64(step_tolerance),
            Float64(finite_difference_step),
            Float64(initial_damping),
            Float64(damping_increase),
            Float64(damping_decrease),
        )
    end
end

struct LocalTracePoint
    iteration::Int
    evaluations::Int
    residual_infinity::Float64
    merit::Float64
    damping::Float64
    accepted_step::Bool
end

struct LocalAttempt
    start::Tuple
    final::Tuple
    observation::OracleObservation
    status::LocalSolveStatus
    accepted::Bool
    iterations::Int
    evaluations::Int
    numerical_rank::Int
    condition_estimate::Float64
    trace::Tuple
end

function _vector_parameter(values, count, default, name)
    source = values === nothing ? fill(default, count) : collect(Float64, values)
    length(source) == count || throw(ArgumentError("$name must have length $count"))
    return source
end

function _normalize_problem(x, origins, scales)
    return (collect(Float64, x) .- origins) ./ scales
end

_denormalize_problem(u, origins, scales) = origins .+ scales .* u

function _normalized_bounds(lower, upper, origins, scales)
    return (lower .- origins) ./ scales, (upper .- origins) ./ scales
end

function _usable_local_observation(observation::OracleObservation)
    return observation.status == EVAL_OK && !isempty(observation.relations)
end

function _float_residual(observation::OracleObservation)
    return Float64[relation.scaled for relation in observation.relations]
end

function _evaluate_local(evaluate_fn, u, origins, scales)
    x = _denormalize_problem(u, origins, scales)
    observation = evaluate_fn(x)
    observation isa OracleObservation || throw(
        ArgumentError("local solver callback must return OracleObservation"),
    )
    return observation
end

function _finite_difference_jacobian(
    evaluate_fn,
    u,
    base_residual,
    origins,
    scales,
    lower_u,
    upper_u,
    step_scale,
)
    residual_count = length(base_residual)
    variable_count = length(u)
    jacobian = zeros(Float64, residual_count, variable_count)
    evaluations = 0
    for column in 1:variable_count
        step = step_scale * max(1.0, abs(u[column]))
        plus_u = copy(u)
        minus_u = copy(u)
        plus_u[column] = min(upper_u[column], u[column] + step)
        minus_u[column] = max(lower_u[column], u[column] - step)
        plus_step = plus_u[column] - u[column]
        minus_step = u[column] - minus_u[column]

        plus = plus_step > 0 ? _evaluate_local(evaluate_fn, plus_u, origins, scales) : nothing
        plus_step > 0 && (evaluations += 1)
        minus = minus_step > 0 ? _evaluate_local(evaluate_fn, minus_u, origins, scales) : nothing
        minus_step > 0 && (evaluations += 1)
        plus_valid = plus !== nothing && _usable_local_observation(plus)
        minus_valid = minus !== nothing && _usable_local_observation(minus)

        if plus_valid && minus_valid
            plus_residual = _float_residual(plus)
            minus_residual = _float_residual(minus)
            jacobian[:, column] .= (plus_residual .- minus_residual) ./ (plus_step + minus_step)
        elseif plus_valid
            jacobian[:, column] .= (_float_residual(plus) .- base_residual) ./ plus_step
        elseif minus_valid
            jacobian[:, column] .= (base_residual .- _float_residual(minus)) ./ minus_step
        end
    end
    return jacobian, evaluations
end

function _lm_step(jacobian, residual, damping)
    variable_count = size(jacobian, 2)
    augmented = [jacobian; sqrt(damping) * Matrix{Float64}(I, variable_count, variable_count)]
    right_hand_side = [-residual; zeros(Float64, variable_count)]
    return qr(augmented, ColumnNorm()) \ right_hand_side
end

function _rank_condition(jacobian)
    isempty(jacobian) && return 0, Inf
    singular_values = svdvals(jacobian)
    isempty(singular_values) && return 0, Inf
    threshold = maximum(singular_values) * sqrt(eps(Float64))
    retained = filter(value -> value > threshold, singular_values)
    isempty(retained) && return 0, Inf
    rank = length(retained)
    rank < min(size(jacobian)...) && return rank, Inf
    condition = maximum(retained) / minimum(retained)
    return rank, isfinite(condition) ? condition : Inf
end

function _local_result(
    start,
    u,
    origins,
    scales,
    observation,
    status,
    iterations,
    evaluations,
    jacobian,
    trace,
    options,
)
    rank, condition = _rank_condition(jacobian)
    accepted = canonical_feasible(
        observation;
        residual_tolerance = options.residual_tolerance,
    )
    return LocalAttempt(
        Tuple(start),
        Tuple(_denormalize_problem(u, origins, scales)),
        observation,
        status,
        accepted,
        iterations,
        evaluations,
        rank,
        condition,
        Tuple(trace),
    )
end

"""
Run the deliberately minimal RB0 local control.

The merit function contains relation residuals only. Guards and domains remain
separate semantic channels and are enforced only by step safety/final canonical
validation; they are never multiplied into the residual.
"""
function solve_local(
    evaluate_fn,
    x0::AbstractVector;
    origins = nothing,
    scales = nothing,
    lower = nothing,
    upper = nothing,
    options::LocalSolveOptions = LocalSolveOptions(),
    deadline_ns::UInt64 = typemax(UInt64),
    cancelled = () -> false,
)
    variable_count = length(x0)
    variable_count > 0 || throw(ArgumentError("a local solve needs at least one variable"))
    origin_values = _vector_parameter(origins, variable_count, 0.0, "origins")
    scale_values = _vector_parameter(scales, variable_count, 1.0, "scales")
    all(value -> isfinite(value) && value > 0, scale_values) || throw(
        ArgumentError("variable scales must be finite and positive"),
    )
    lower_values = _vector_parameter(lower, variable_count, -Inf, "lower")
    upper_values = _vector_parameter(upper, variable_count, Inf, "upper")
    all(lower_values .< upper_values) || throw(ArgumentError("each lower bound must be below upper"))

    start = collect(Float64, x0)
    u = _normalize_problem(start, origin_values, scale_values)
    lower_u, upper_u = _normalized_bounds(lower_values, upper_values, origin_values, scale_values)
    u .= clamp.(u, lower_u, upper_u)
    evaluations = 1
    observation = _evaluate_local(evaluate_fn, u, origin_values, scale_values)
    empty_jacobian = zeros(Float64, 0, variable_count)
    trace = LocalTracePoint[]
    if !_usable_local_observation(observation)
        return _local_result(
            start,
            u,
            origin_values,
            scale_values,
            observation,
            LOCAL_EVALUATION_FAILED,
            0,
            evaluations,
            empty_jacobian,
            trace,
            options,
        )
    end

    residual = _float_residual(observation)
    damping = options.initial_damping
    jacobian = empty_jacobian
    no_progress = 0
    for iteration in 1:options.max_iterations
        if cancelled()
            return _local_result(
                start,
                u,
                origin_values,
                scale_values,
                observation,
                LOCAL_CANCELLED,
                iteration - 1,
                evaluations,
                jacobian,
                trace,
                options,
            )
        end
        if time_ns() >= deadline_ns
            return _local_result(
                start,
                u,
                origin_values,
                scale_values,
                observation,
                LOCAL_DEADLINE,
                iteration - 1,
                evaluations,
                jacobian,
                trace,
                options,
            )
        end
        residual_infinity = norm(residual, Inf)
        merit = 0.5 * sum(abs2, residual)
        if residual_infinity <= options.residual_tolerance
            return _local_result(
                start,
                u,
                origin_values,
                scale_values,
                observation,
                LOCAL_CONVERGED,
                iteration - 1,
                evaluations,
                jacobian,
                trace,
                options,
            )
        end
        if evaluations + 2 * variable_count + 1 > options.max_evaluations
            return _local_result(
                start,
                u,
                origin_values,
                scale_values,
                observation,
                LOCAL_MAX_EVALUATIONS,
                iteration - 1,
                evaluations,
                jacobian,
                trace,
                options,
            )
        end

        jacobian, jacobian_evaluations = _finite_difference_jacobian(
            evaluate_fn,
            u,
            residual,
            origin_values,
            scale_values,
            lower_u,
            upper_u,
            options.finite_difference_step,
        )
        evaluations += jacobian_evaluations
        step = _lm_step(jacobian, residual, damping)
        if norm(step) <= options.step_tolerance * (1 + norm(u))
            push!(
                trace,
                LocalTracePoint(iteration, evaluations, residual_infinity, merit, damping, false),
            )
            return _local_result(
                start,
                u,
                origin_values,
                scale_values,
                observation,
                LOCAL_NO_PROGRESS,
                iteration,
                evaluations,
                jacobian,
                trace,
                options,
            )
        end

        trial_u = clamp.(u .+ step, lower_u, upper_u)
        effective_step = trial_u .- u
        trial = _evaluate_local(evaluate_fn, trial_u, origin_values, scale_values)
        evaluations += 1
        accepted_step = false
        if _usable_local_observation(trial)
            trial_residual = _float_residual(trial)
            trial_merit = 0.5 * sum(abs2, trial_residual)
            predicted_merit = 0.5 * sum(abs2, residual + jacobian * effective_step)
            predicted_reduction = merit - predicted_merit
            actual_reduction = merit - trial_merit
            ratio = predicted_reduction > 0 ? actual_reduction / predicted_reduction : -Inf
            if actual_reduction > 0 && ratio > 1.0e-4
                u = trial_u
                observation = trial
                residual = trial_residual
                accepted_step = true
                no_progress = 0
                ratio > 0.75 && (damping *= options.damping_decrease)
                ratio < 0.25 && (damping *= options.damping_increase)
            else
                damping *= options.damping_increase
                no_progress += 1
            end
        else
            damping *= options.damping_increase
            no_progress += 1
        end
        push!(
            trace,
            LocalTracePoint(
                iteration,
                evaluations,
                residual_infinity,
                merit,
                damping,
                accepted_step,
            ),
        )
        if no_progress >= 12
            return _local_result(
                start,
                u,
                origin_values,
                scale_values,
                observation,
                LOCAL_NO_PROGRESS,
                iteration,
                evaluations,
                jacobian,
                trace,
                options,
            )
        end
    end
    return _local_result(
        start,
        u,
        origin_values,
        scale_values,
        observation,
        LOCAL_MAX_ITERATIONS,
        options.max_iterations,
        evaluations,
        jacobian,
        trace,
        options,
    )
end

function solve_local(
    problem::ProblemSpecV1,
    registry::FrozenPluginRegistry,
    x0::AbstractVector;
    options::LocalSolveOptions = LocalSolveOptions(),
    kwargs...,
)
    origins = Float64[variable.origin for variable in problem.variables]
    scales = Float64[variable.scale for variable in problem.variables]
    lower = Float64[
        variable.lower === nothing ? -Inf : variable.lower for variable in problem.variables
    ]
    upper = Float64[
        variable.upper === nothing ? Inf : variable.upper for variable in problem.variables
    ]
    evaluate_fn = x -> evaluate_reference(problem, registry, x)
    return solve_local(
        evaluate_fn,
        x0;
        origins,
        scales,
        lower,
        upper,
        options,
        kwargs...,
    )
end
