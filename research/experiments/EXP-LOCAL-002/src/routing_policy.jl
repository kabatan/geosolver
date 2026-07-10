const ROUTE_ID = "ROUTE-LMTR-A1"
const ROUTE_DEFAULT_ALGORITHM = "NLS-TR"
const ROUTE_ALTERNATE_ALGORITHM = "NLS-LM"
const ROUTE_MINIMUM_DIMENSION = 16
const ROUTE_CONDITION_THRESHOLD = 20_000.0
const ROUTE_RANK_RELATIVE_CUTOFF = sqrt(eps(Float64))
const ROUTE_FINITE_DIFFERENCE_STEP = cbrt(eps(Float64))

struct RouteDiagnostic
    selected_algorithm::String
    capability::String
    dimension::Int
    computed::Bool
    numerical_rank::Int
    condition_estimate::Float64
    rank_cutoff::Float64
    residual_calls::Int
    svd_count::Int
    wall_seconds::Float64
    status::String
    explicit_fallback::Bool
end

function _declares_c1(problem)
    capabilities = get(problem.metadata, :declared_capabilities, nothing)
    capabilities === nothing && return problem.jacobian! !== nothing
    return :C1 in capabilities
end

function _route_default(capability, dimension, status; explicit_fallback=false, wall_seconds=0.0)
    return RouteDiagnostic(
        ROUTE_DEFAULT_ALGORITHM,
        capability,
        dimension,
        false,
        -1,
        NaN,
        NaN,
        0,
        0,
        wall_seconds,
        status,
        explicit_fallback,
    )
end

function route_diagnostic(problem, start)
    dimension = problem.dimension
    capability = _declares_c1(problem) ? "C1" : "C0"
    capability == "C1" || return _route_default(capability, dimension, "capability-not-C1")
    dimension >= ROUTE_MINIMUM_DIMENSION ||
        return _route_default(capability, dimension, "dimension-below-threshold")

    started_ns = time_ns()
    residual_calls = Ref(0)
    try
        origins, scales, lower_u, upper_u = ExperimentLocal002.bounds_normalization(problem)
        u = ExperimentLocal002._normalize(collect(Float64, start), origins, scales)
        residual_dimension = problem.residual_dimension
        jacobian = zeros(residual_dimension, dimension)
        base_residual = nothing

        function evaluate_scaled(candidate)
            residual_calls[] += 1
            output = zeros(residual_dimension)
            point = ExperimentLocal002._denormalize(candidate, origins, scales)
            problem.residual!(output, point)
            output ./= problem.residual_scales
            all(isfinite, output) || error("nonfinite routing residual")
            return output
        end

        for column in 1:dimension
            step = ROUTE_FINITE_DIFFERENCE_STEP * max(1.0, abs(u[column]))
            plus = copy(u)
            minus = copy(u)
            plus[column] = min(upper_u[column], u[column] + step)
            minus[column] = max(lower_u[column], u[column] - step)
            plus_step = plus[column] - u[column]
            minus_step = u[column] - minus[column]
            if plus_step > 0 && minus_step > 0
                plus_residual = evaluate_scaled(plus)
                minus_residual = evaluate_scaled(minus)
                jacobian[:, column] .=
                    (plus_residual .- minus_residual) ./ (plus_step + minus_step)
            elseif plus_step > 0
                base_residual === nothing && (base_residual = evaluate_scaled(u))
                plus_residual = evaluate_scaled(plus)
                jacobian[:, column] .= (plus_residual .- base_residual) ./ plus_step
            elseif minus_step > 0
                base_residual === nothing && (base_residual = evaluate_scaled(u))
                minus_residual = evaluate_scaled(minus)
                jacobian[:, column] .= (base_residual .- minus_residual) ./ minus_step
            else
                error("routing finite-difference stencil has no usable side")
            end
        end
        all(isfinite, jacobian) || error("nonfinite routing Jacobian")
        singular_values = svdvals(jacobian)
        isempty(singular_values) && error("empty routing singular spectrum")
        maximum_value = maximum(singular_values)
        isfinite(maximum_value) && maximum_value > 0 ||
            error("degenerate routing singular spectrum")
        cutoff = maximum_value * ROUTE_RANK_RELATIVE_CUTOFF
        numerical_rank = count(value -> value > cutoff, singular_values)
        condition = numerical_rank == dimension ?
            maximum_value / minimum(singular_values) : Inf
        selected = numerical_rank == dimension && isfinite(condition) &&
            condition >= ROUTE_CONDITION_THRESHOLD ?
            ROUTE_ALTERNATE_ALGORITHM : ROUTE_DEFAULT_ALGORITHM
        return RouteDiagnostic(
            selected,
            capability,
            dimension,
            true,
            numerical_rank,
            condition,
            cutoff,
            residual_calls[],
            1,
            (time_ns() - started_ns) / 1.0e9,
            "ok",
            false,
        )
    catch error
        return RouteDiagnostic(
            ROUTE_DEFAULT_ALGORITHM,
            capability,
            dimension,
            true,
            -1,
            NaN,
            NaN,
            residual_calls[],
            0,
            (time_ns() - started_ns) / 1.0e9,
            string("diagnostic-fallback:", nameof(typeof(error)), ":", sprint(showerror, error)),
            true,
        )
    end
end
