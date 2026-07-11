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

struct LocalJacobianColoring{R<:Tuple,G<:Tuple}
    row_supports::R
    groups::G
    structural_nonzeros::Int
end

struct _DeferredLocalJacobianSource{E}
    entries::E
    order::Symbol
end

struct _SealedLocalJacobianProvider{C<:LocalJacobianColoring}
    coloring::C
    residual_count::Int
    variable_count::Int
    projection_hash::String
end

function _natural_local_color_groups(row_supports)
    groups = Vector{Vector{Int}}()
    occupied_rows = BitSet[]
    for column in eachindex(row_supports)
        isempty(row_supports[column]) && continue
        rows = BitSet(row_supports[column])
        destination = findfirst(occupied -> isdisjoint(occupied, rows), occupied_rows)
        if destination === nothing
            push!(groups, [column])
            push!(occupied_rows, rows)
        else
            push!(groups[destination], column)
            union!(occupied_rows[destination], rows)
        end
    end
    return Tuple(Tuple(group) for group in groups)
end

function _sealed_local_jacobian_provider(
    row_supports,
    groups,
    structural_nonzeros::Integer,
    residual_count::Integer,
    variable_count::Integer,
    projection_hash::AbstractString,
)
    residual_count isa Bool && throw(ArgumentError("residual_count must be an integer count"))
    variable_count isa Bool && throw(ArgumentError("variable_count must be an integer count"))
    structural_nonzeros isa Bool && throw(
        ArgumentError("structural_nonzeros must be an integer count"),
    )
    residual_count > 0 || throw(ArgumentError("residual_count must be positive"))
    variable_count > 0 || throw(ArgumentError("variable_count must be positive"))
    length(row_supports) == variable_count || throw(
        ArgumentError("row_supports must have one entry per variable"),
    )
    occursin(r"^sha256:[0-9a-f]{64}$", projection_hash) || throw(
        ArgumentError("projection_hash must be a canonical lowercase SHA-256 content hash"),
    )

    supports = Tuple(Tuple(
        begin
            row isa Integer && !(row isa Bool) || throw(
                ArgumentError("row supports must contain integers"),
            )
            Int(row)
        end for row in support
    ) for support in row_supports)
    for support in supports
        issorted(support) || throw(ArgumentError("row supports must be sorted"))
        allunique(support) || throw(ArgumentError("row supports must be unique"))
        all(row -> 1 <= row <= residual_count, support) || throw(
            ArgumentError("row support is outside the residual range"),
        )
    end
    expected_nonzeros = sum(length, supports)
    structural_nonzeros == expected_nonzeros || throw(
        ArgumentError("structural_nonzeros does not match row supports"),
    )

    group_tuple = Tuple(Tuple(
        begin
            column isa Integer && !(column isa Bool) || throw(
                ArgumentError("color groups must contain integers"),
            )
            Int(column)
        end for column in group
    ) for group in groups)
    all(!isempty, group_tuple) || throw(ArgumentError("color groups must be nonempty"))
    flattened = Tuple(Iterators.flatten(group_tuple))
    allunique(flattened) || throw(ArgumentError("colored columns must be unique"))
    all(column -> 1 <= column <= variable_count, flattened) || throw(
        ArgumentError("colored column is outside the variable range"),
    )
    active_columns = Tuple(column for column in 1:variable_count if !isempty(supports[column]))
    sort(collect(flattened)) == collect(active_columns) || throw(
        ArgumentError("color groups must partition exactly the active columns"),
    )
    for group in group_tuple
        occupied = BitSet()
        for column in group
            rows = BitSet(supports[column])
            isdisjoint(occupied, rows) || throw(
                ArgumentError("same-color columns have overlapping row supports"),
            )
            union!(occupied, rows)
        end
    end
    group_tuple == _natural_local_color_groups(supports) || throw(
        ArgumentError("color groups must equal the natural first-fit partition"),
    )

    projection_document = Dict{String,Any}(
        "groups" => Any[collect(group) for group in group_tuple],
        "row_supports" => Any[collect(rows) for rows in supports],
        "structural_nonzeros" => Int(structural_nonzeros),
    )
    expected_hash = string(canonical_json_hash(projection_document))
    String(projection_hash) == expected_hash || throw(
        ArgumentError("projection_hash does not seal the canonical provider projection"),
    )

    coloring = LocalJacobianColoring(supports, group_tuple, Int(structural_nonzeros))
    return _SealedLocalJacobianProvider(
        coloring,
        Int(residual_count),
        Int(variable_count),
        String(projection_hash),
    )
end

_resolve_local_jacobian_source(::Nothing, residual_count, variable_count) = nothing

function _resolve_local_jacobian_source(
    source::_DeferredLocalJacobianSource,
    residual_count,
    variable_count,
)
    return _local_jacobian_coloring(
        residual_count,
        variable_count,
        source.entries;
        order=source.order,
    )
end

function _resolve_local_jacobian_source(
    source::_SealedLocalJacobianProvider,
    residual_count,
    variable_count,
)
    source.residual_count == residual_count || throw(
        ArgumentError("sealed provider residual dimension mismatch"),
    )
    source.variable_count == variable_count || throw(
        ArgumentError("sealed provider variable dimension mismatch"),
    )
    return source
end

function _local_jacobian_coloring(
    residual_count::Integer,
    variable_count::Integer,
    entries;
    order::Symbol=:natural,
)
    residual_count >= 0 || throw(ArgumentError("residual_count must be nonnegative"))
    variable_count >= 0 || throw(ArgumentError("variable_count must be nonnegative"))
    order in (:natural, :largest_first) || throw(
        ArgumentError("color order must be natural or largest_first"),
    )
    supports = [BitSet() for _ in 1:variable_count]
    seen = Set{Tuple{Int,Int}}()
    for entry in entries
        entry isa Tuple && length(entry) == 2 || throw(
            ArgumentError("Jacobian sparsity entries must be (row, column) tuples"),
        )
        row, column = entry
        row isa Integer && column isa Integer || throw(
            ArgumentError("Jacobian sparsity indexes must be integers"),
        )
        1 <= row <= residual_count || throw(
            ArgumentError("Jacobian sparsity row $row is out of bounds"),
        )
        1 <= column <= variable_count || throw(
            ArgumentError("Jacobian sparsity column $column is out of bounds"),
        )
        key = (Int(row), Int(column))
        key in seen && throw(ArgumentError("Jacobian sparsity entries must be unique"))
        push!(seen, key)
        push!(supports[Int(column)], Int(row))
    end

    columns = Int[column for column in 1:variable_count if !isempty(supports[column])]
    if order == :largest_first
        degree(column) = count(
            other -> other != column && !isdisjoint(supports[column], supports[other]),
            columns,
        )
        sort!(columns; by=column -> (-degree(column), column))
    end
    groups = Vector{Vector{Int}}()
    occupied_rows = BitSet[]
    for column in columns
        destination = findfirst(rows -> isdisjoint(rows, supports[column]), occupied_rows)
        if destination === nothing
            push!(groups, [column])
            push!(occupied_rows, copy(supports[column]))
        else
            push!(groups[destination], column)
            union!(occupied_rows[destination], supports[column])
        end
    end
    return LocalJacobianColoring(
        Tuple(Tuple(sort!(collect(rows))) for rows in supports),
        Tuple(Tuple(group) for group in groups),
        length(seen),
    )
end

function _finite_difference_column(
    evaluate_fn,
    u,
    base_residual,
    origins,
    scales,
    lower_u,
    upper_u,
    step_scale,
    column,
)
    step = step_scale * max(1.0, abs(u[column]))
    plus_u = copy(u)
    minus_u = copy(u)
    plus_u[column] = min(upper_u[column], u[column] + step)
    minus_u[column] = max(lower_u[column], u[column] - step)
    plus_step = plus_u[column] - u[column]
    minus_step = u[column] - minus_u[column]
    evaluations = 0
    plus = plus_step > 0 ? _evaluate_local(evaluate_fn, plus_u, origins, scales) : nothing
    plus_step > 0 && (evaluations += 1)
    minus = minus_step > 0 ? _evaluate_local(evaluate_fn, minus_u, origins, scales) : nothing
    minus_step > 0 && (evaluations += 1)
    plus_valid = plus !== nothing && _usable_local_observation(plus)
    minus_valid = minus !== nothing && _usable_local_observation(minus)
    derivative = zeros(Float64, length(base_residual))
    if plus_valid && minus_valid
        derivative .= (_float_residual(plus) .- _float_residual(minus)) ./
                      (plus_step + minus_step)
    elseif plus_valid
        derivative .= (_float_residual(plus) .- base_residual) ./ plus_step
    elseif minus_valid
        derivative .= (base_residual .- _float_residual(minus)) ./ minus_step
    end
    return derivative, evaluations
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
        derivative, column_evaluations = _finite_difference_column(
            evaluate_fn,
            u,
            base_residual,
            origins,
            scales,
            lower_u,
            upper_u,
            step_scale,
            column,
        )
        jacobian[:, column] .= derivative
        evaluations += column_evaluations
    end
    return jacobian, evaluations
end

function _colored_finite_difference_jacobian(
    evaluate_fn,
    u,
    base_residual,
    origins,
    scales,
    lower_u,
    upper_u,
    step_scale,
    coloring::LocalJacobianColoring,
    ;
    group_observer=nothing,
)
    residual_count = length(base_residual)
    variable_count = length(u)
    jacobian = zeros(Float64, residual_count, variable_count)
    evaluations = 0
    for group in coloring.groups
        plus_u = copy(u)
        minus_u = copy(u)
        plus_steps = zeros(Float64, variable_count)
        minus_steps = zeros(Float64, variable_count)
        for column in group
            step = step_scale * max(1.0, abs(u[column]))
            plus_u[column] = min(upper_u[column], u[column] + step)
            minus_u[column] = max(lower_u[column], u[column] - step)
            plus_steps[column] = plus_u[column] - u[column]
            minus_steps[column] = u[column] - minus_u[column]
        end
        plus_attempted = any(column -> plus_steps[column] > 0, group)
        minus_attempted = any(column -> minus_steps[column] > 0, group)
        plus = plus_attempted ? _evaluate_local(evaluate_fn, plus_u, origins, scales) : nothing
        plus_attempted && (evaluations += 1)
        minus = minus_attempted ? _evaluate_local(evaluate_fn, minus_u, origins, scales) : nothing
        minus_attempted && (evaluations += 1)
        plus_valid = !plus_attempted || _usable_local_observation(plus)
        minus_valid = !minus_attempted || _usable_local_observation(minus)
        grouped_evaluations = Int(plus_attempted) + Int(minus_attempted)

        if !plus_valid || !minus_valid
            fallback_evaluations = 0
            for column in group
                derivative, column_evaluations = _finite_difference_column(
                    evaluate_fn,
                    u,
                    base_residual,
                    origins,
                    scales,
                    lower_u,
                    upper_u,
                    step_scale,
                    column,
                )
                jacobian[:, column] .= derivative
                evaluations += column_evaluations
                fallback_evaluations += column_evaluations
            end
            group_observer === nothing || group_observer((
                columns = Tuple(group),
                grouped_evaluations = grouped_evaluations,
                fallback = true,
                fallback_evaluations = fallback_evaluations,
            ))
            continue
        end

        plus_residual = plus_attempted ? _float_residual(plus) : base_residual
        minus_residual = minus_attempted ? _float_residual(minus) : base_residual
        for column in group
            rows = coloring.row_supports[column]
            plus_step = plus_steps[column]
            minus_step = minus_steps[column]
            if plus_step > 0 && minus_step > 0
                for row in rows
                    jacobian[row, column] =
                        (plus_residual[row] - minus_residual[row]) / (plus_step + minus_step)
                end
            elseif plus_step > 0
                for row in rows
                    jacobian[row, column] =
                        (plus_residual[row] - base_residual[row]) / plus_step
                end
            elseif minus_step > 0
                for row in rows
                    jacobian[row, column] =
                        (base_residual[row] - minus_residual[row]) / minus_step
                end
            end
        end
        group_observer === nothing || group_observer((
            columns = Tuple(group),
            grouped_evaluations = grouped_evaluations,
            fallback = false,
            fallback_evaluations = 0,
        ))
    end
    return jacobian, evaluations
end

function _sealed_probe(
    evaluate_fn,
    u,
    origins,
    scales,
    residual_count,
    deadline_ns,
    cancelled;
    require_finite_shape::Bool=true,
)
    cancelled() && return nothing, false, 0, LOCAL_CANCELLED
    time_ns() >= deadline_ns && return nothing, false, 0, LOCAL_DEADLINE
    observation = _evaluate_local(evaluate_fn, u, origins, scales)
    evaluations = 1
    cancelled() && return observation, false, evaluations, LOCAL_CANCELLED
    if time_ns() >= deadline_ns
        return observation, false, evaluations, LOCAL_DEADLINE
    end
    usable = _usable_local_observation(observation) && (
        !require_finite_shape ||
        length(observation.relations) == residual_count &&
        all(relation -> isfinite(relation.scaled), observation.relations)
    )
    return observation, usable, evaluations, nothing
end

function _sealed_finite_difference_column(
    evaluate_fn,
    u,
    base_residual,
    origins,
    scales,
    lower_u,
    upper_u,
    step_scale,
    column,
    deadline_ns,
    cancelled;
    fail_on_unusable::Bool=true,
    require_finite_shape::Bool=true,
)
    residual_count = length(base_residual)
    step = step_scale * max(1.0, abs(u[column]))
    plus_u = copy(u)
    minus_u = copy(u)
    plus_u[column] = min(upper_u[column], u[column] + step)
    minus_u[column] = max(lower_u[column], u[column] - step)
    plus_step = plus_u[column] - u[column]
    minus_step = u[column] - minus_u[column]
    plus_step > 0 || minus_step > 0 || return (
        zeros(Float64, residual_count),
        0,
        fail_on_unusable ? LOCAL_EVALUATION_FAILED : nothing,
    )

    plus = nothing
    plus_valid = false
    minus = nothing
    minus_valid = false
    evaluations = 0
    if plus_step > 0
        plus, plus_valid, used, terminal = _sealed_probe(
            evaluate_fn,
            plus_u,
            origins,
            scales,
            residual_count,
            deadline_ns,
            cancelled;
            require_finite_shape,
        )
        evaluations += used
        terminal === nothing || return zeros(Float64, residual_count), evaluations, terminal
    end
    if minus_step > 0
        minus, minus_valid, used, terminal = _sealed_probe(
            evaluate_fn,
            minus_u,
            origins,
            scales,
            residual_count,
            deadline_ns,
            cancelled;
            require_finite_shape,
        )
        evaluations += used
        terminal === nothing || return zeros(Float64, residual_count), evaluations, terminal
    end
    plus_valid || minus_valid || return (
        zeros(Float64, residual_count),
        evaluations,
        fail_on_unusable ? LOCAL_EVALUATION_FAILED : nothing,
    )

    derivative = zeros(Float64, residual_count)
    if plus_valid && minus_valid
        derivative .= (_float_residual(plus) .- _float_residual(minus)) ./
                      (plus_step + minus_step)
    elseif plus_valid
        derivative .= (_float_residual(plus) .- base_residual) ./ plus_step
    else
        derivative .= (base_residual .- _float_residual(minus)) ./ minus_step
    end
    return derivative, evaluations, nothing
end

function _guarded_finite_difference_jacobian(
    evaluate_fn,
    u,
    base_residual,
    origins,
    scales,
    lower_u,
    upper_u,
    step_scale;
    deadline_ns,
    cancelled,
)
    residual_count = length(base_residual)
    variable_count = length(u)
    jacobian = zeros(Float64, residual_count, variable_count)
    evaluations = 0
    for column in 1:variable_count
        derivative, used, terminal = _sealed_finite_difference_column(
            evaluate_fn,
            u,
            base_residual,
            origins,
            scales,
            lower_u,
            upper_u,
            step_scale,
            column,
            deadline_ns,
            cancelled;
            fail_on_unusable=false,
            require_finite_shape=false,
        )
        evaluations += used
        terminal === nothing || return jacobian, evaluations, terminal
        jacobian[:, column] .= derivative
    end
    return jacobian, evaluations, nothing
end

function _guarded_colored_finite_difference_jacobian(
    evaluate_fn,
    u,
    base_residual,
    origins,
    scales,
    lower_u,
    upper_u,
    step_scale,
    coloring::LocalJacobianColoring;
    deadline_ns,
    cancelled,
    group_observer=nothing,
    sealed_semantics::Bool=false,
)
    residual_count = length(base_residual)
    variable_count = length(u)
    jacobian = zeros(Float64, residual_count, variable_count)
    evaluations = 0
    for group in coloring.groups
        plus_u = copy(u)
        minus_u = copy(u)
        plus_steps = zeros(Float64, variable_count)
        minus_steps = zeros(Float64, variable_count)
        for column in group
            step = step_scale * max(1.0, abs(u[column]))
            plus_u[column] = min(upper_u[column], u[column] + step)
            minus_u[column] = max(lower_u[column], u[column] - step)
            plus_steps[column] = plus_u[column] - u[column]
            minus_steps[column] = u[column] - minus_u[column]
        end
        plus_attempted = any(column -> plus_steps[column] > 0, group)
        minus_attempted = any(column -> minus_steps[column] > 0, group)
        if !plus_attempted && !minus_attempted && sealed_semantics
            return jacobian, evaluations, LOCAL_EVALUATION_FAILED
        end

        plus = nothing
        plus_valid = !plus_attempted
        minus = nothing
        minus_valid = !minus_attempted
        grouped_evaluations = 0
        if plus_attempted
            plus, plus_valid, used, terminal = _sealed_probe(
                evaluate_fn,
                plus_u,
                origins,
                scales,
                residual_count,
                deadline_ns,
                cancelled;
                require_finite_shape=sealed_semantics,
            )
            evaluations += used
            grouped_evaluations += used
            terminal === nothing || return jacobian, evaluations, terminal
        end
        if minus_attempted
            minus, minus_valid, used, terminal = _sealed_probe(
                evaluate_fn,
                minus_u,
                origins,
                scales,
                residual_count,
                deadline_ns,
                cancelled;
                require_finite_shape=sealed_semantics,
            )
            evaluations += used
            grouped_evaluations += used
            terminal === nothing || return jacobian, evaluations, terminal
        end

        if !plus_valid || !minus_valid
            fallback_evaluations = 0
            for (fallback_index, column) in enumerate(group)
                derivative, used, terminal = _sealed_finite_difference_column(
                    evaluate_fn,
                    u,
                    base_residual,
                    origins,
                    scales,
                    lower_u,
                    upper_u,
                    step_scale,
                    column,
                    deadline_ns,
                    cancelled;
                    fail_on_unusable=sealed_semantics,
                    require_finite_shape=sealed_semantics,
                )
                evaluations += used
                fallback_evaluations += used
                if terminal !== nothing
                    group_observer === nothing || group_observer((
                        columns = Tuple(group),
                        grouped_evaluations = grouped_evaluations,
                        fallback = true,
                        fallback_evaluations = fallback_evaluations,
                        completed_fallback_columns = fallback_index - 1,
                    ))
                    return jacobian, evaluations, terminal
                end
                jacobian[:, column] .= derivative
            end
            if group_observer !== nothing
                event = if sealed_semantics
                    (
                        columns = Tuple(group),
                        grouped_evaluations = grouped_evaluations,
                        fallback = true,
                        fallback_evaluations = fallback_evaluations,
                        completed_fallback_columns = length(group),
                    )
                else
                    (
                        columns = Tuple(group),
                        grouped_evaluations = grouped_evaluations,
                        fallback = true,
                        fallback_evaluations = fallback_evaluations,
                    )
                end
                group_observer(event)
            end
            continue
        end

        plus_residual = plus_attempted ? _float_residual(plus) : base_residual
        minus_residual = minus_attempted ? _float_residual(minus) : base_residual
        for column in group
            rows = coloring.row_supports[column]
            plus_step = plus_steps[column]
            minus_step = minus_steps[column]
            if plus_step > 0 && minus_step > 0
                for row in rows
                    jacobian[row, column] =
                        (plus_residual[row] - minus_residual[row]) / (plus_step + minus_step)
                end
            elseif plus_step > 0
                for row in rows
                    jacobian[row, column] =
                        (plus_residual[row] - base_residual[row]) / plus_step
                end
            elseif minus_step > 0
                for row in rows
                    jacobian[row, column] =
                        (base_residual[row] - minus_residual[row]) / minus_step
                end
            else
                sealed_semantics &&
                    return jacobian, evaluations, LOCAL_EVALUATION_FAILED
            end
        end
        if group_observer !== nothing
            event = if sealed_semantics
                (
                    columns = Tuple(group),
                    grouped_evaluations = grouped_evaluations,
                    fallback = false,
                    fallback_evaluations = 0,
                    completed_fallback_columns = 0,
                )
            else
                (
                    columns = Tuple(group),
                    grouped_evaluations = grouped_evaluations,
                    fallback = false,
                    fallback_evaluations = 0,
                )
            end
            group_observer(event)
        end
    end
    return jacobian, evaluations, nothing
end

function _sealed_colored_finite_difference_jacobian(
    evaluate_fn,
    u,
    base_residual,
    origins,
    scales,
    lower_u,
    upper_u,
    step_scale,
    provider::_SealedLocalJacobianProvider;
    deadline_ns,
    cancelled,
    group_observer=nothing,
)
    return _guarded_colored_finite_difference_jacobian(
        evaluate_fn,
        u,
        base_residual,
        origins,
        scales,
        lower_u,
        upper_u,
        step_scale,
        provider.coloring;
        deadline_ns,
        cancelled,
        group_observer,
        sealed_semantics=true,
    )
end

_jacobian_evaluation_bound(::Nothing, variable_count) = 2 * variable_count
_jacobian_evaluation_bound(coloring::LocalJacobianColoring, variable_count) =
    2 * length(coloring.groups) + 2 * count(rows -> !isempty(rows), coloring.row_supports)
_jacobian_evaluation_bound(provider::_SealedLocalJacobianProvider, variable_count) =
    _jacobian_evaluation_bound(provider.coloring, variable_count)

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

function _solve_local_kernel(
    evaluate_fn,
    x0::AbstractVector,
    jacobian_source;
    origins = nothing,
    scales = nothing,
    lower = nothing,
    upper = nothing,
    options::LocalSolveOptions = LocalSolveOptions(),
    deadline_ns::UInt64 = typemax(UInt64),
    cancelled = () -> false,
    color_group_observer = nothing,
    jacobian_observer = nothing,
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
    coloring = _resolve_local_jacobian_source(
        jacobian_source,
        length(residual),
        variable_count,
    )
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
        jacobian_evaluation_bound = _jacobian_evaluation_bound(coloring, variable_count)
        if evaluations + jacobian_evaluation_bound + 1 > options.max_evaluations
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

        jacobian, jacobian_evaluations, jacobian_failure = if coloring === nothing
            _guarded_finite_difference_jacobian(
                evaluate_fn,
                u,
                residual,
                origin_values,
                scale_values,
                lower_u,
                upper_u,
                options.finite_difference_step;
                deadline_ns,
                cancelled,
            )
        elseif coloring isa _SealedLocalJacobianProvider
            _sealed_colored_finite_difference_jacobian(
                evaluate_fn,
                u,
                residual,
                origin_values,
                scale_values,
                lower_u,
                upper_u,
                options.finite_difference_step,
                coloring;
                deadline_ns,
                cancelled,
                group_observer=color_group_observer,
            )
        else
            _guarded_colored_finite_difference_jacobian(
                evaluate_fn,
                u,
                residual,
                origin_values,
                scale_values,
                lower_u,
                upper_u,
                options.finite_difference_step,
                coloring;
                deadline_ns,
                cancelled,
                group_observer=color_group_observer,
            )
        end
        evaluations += jacobian_evaluations
        jacobian_observer === nothing || jacobian_observer((
            colored = coloring !== nothing,
            evaluations = jacobian_evaluations,
        ))
        if jacobian_failure !== nothing
            return _local_result(
                start,
                u,
                origin_values,
                scale_values,
                observation,
                jacobian_failure,
                iteration - 1,
                evaluations,
                jacobian,
                trace,
                options,
            )
        end
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
    jacobian_entries = nothing,
    color_order::Symbol = :natural,
    color_group_observer = nothing,
    jacobian_observer = nothing,
)
    source = jacobian_entries === nothing ? nothing :
             _DeferredLocalJacobianSource(jacobian_entries, color_order)
    return _solve_local_kernel(
        evaluate_fn,
        x0,
        source;
        origins,
        scales,
        lower,
        upper,
        options,
        deadline_ns,
        cancelled,
        color_group_observer,
        jacobian_observer,
    )
end

function _solve_local_with_provider(
    evaluate_fn,
    x0::AbstractVector,
    provider::_SealedLocalJacobianProvider;
    origins = nothing,
    scales = nothing,
    lower = nothing,
    upper = nothing,
    options::LocalSolveOptions = LocalSolveOptions(),
    deadline_ns::UInt64 = typemax(UInt64),
    cancelled = () -> false,
    color_group_observer = nothing,
    jacobian_observer = nothing,
)
    return _solve_local_kernel(
        evaluate_fn,
        x0,
        provider;
        origins,
        scales,
        lower,
        upper,
        options,
        deadline_ns,
        cancelled,
        color_group_observer,
        jacobian_observer,
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
