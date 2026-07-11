module ExperimentLocal004

using ADTypes
using GeoTargetBenchmarks
using NonlinearSolve

const EXPERIMENT_ID = "EXP-LOCAL-004"
const NONLINEAR_SOLVE_VERSION = "4.20.2"
const DEFAULT_MAX_ITERATIONS = 250
const DEFAULT_MAX_EVALUATIONS = 2_000
const ABSOLUTE_TOLERANCE = 1.0e-12
const RELATIVE_TOLERANCE = 0.0
const FINITE_DIFFERENCE_STEP = cbrt(eps(Float64))
const DERIVATIVE_BACKEND =
    "ADTypes.AutoFiniteDiff(fdtype=Val(:central),fdjtype=Val(:central),explicit-step)"
const BOUNDS_TRANSFORM = "midpoint-half-range-to-unit-box"
const LIBRARY_BOUNDS_TRANSFORM = "NonlinearSolve-logistic-unconstraining"

struct CallbackBudgetExceeded <: Exception
    limit::Int
end

Base.showerror(io::IO, error::CallbackBudgetExceeded) =
    print(io, "residual callback budget ", error.limit, " exhausted")

mutable struct CallbackCounter
    calls::Int
    limit::Int
    exhausted::Bool
    nonfinite_calls::Int
    outside_bounds_calls::Int
end

function _algorithm(kind::Symbol)
    backend = AutoFiniteDiff(
        fdtype=Val(:central),
        fdjtype=Val(:central),
        relstep=FINITE_DIFFERENCE_STEP,
        absstep=FINITE_DIFFERENCE_STEP,
    )
    kind === :tr && return TrustRegion(autodiff=backend)
    kind === :lm && return LevenbergMarquardt(
        autodiff=backend,
        disable_geodesic=Val(false),
        finite_diff_step_geodesic=0.1,
        α_geodesic=0.75,
    )
    throw(ArgumentError("NonlinearSolve candidate must be :tr or :lm"))
end

function _variant_name(kind::Symbol)
    kind === :tr && return "NLS-TR"
    kind === :lm && return "NLS-LM"
    throw(ArgumentError("NonlinearSolve candidate must be :tr or :lm"))
end

function _bounds_transform(case::SolverExperimentCase, start::AbstractVector)
    length(start) == case.dimension || throw(DimensionMismatch("start has wrong dimension"))
    lower = collect(Float64, case.lower_bounds)
    upper = collect(Float64, case.upper_bounds)
    all(isfinite, lower) && all(isfinite, upper) ||
        throw(ArgumentError("bounds must be finite"))
    all(upper .> lower) || throw(ArgumentError("bounds must have positive width"))
    origins = (lower .+ upper) ./ 2
    half_ranges = (upper .- lower) ./ 2
    x0 = collect(Float64, start)
    all(isfinite, x0) || throw(ArgumentError("start must be finite"))
    all(lower .<= x0 .<= upper) || throw(ArgumentError("start must be within bounds"))
    u0 = (x0 .- origins) ./ half_ranges
    lower_u = fill(-1.0, case.dimension)
    upper_u = fill(1.0, case.dimension)
    return origins, half_ranges, lower_u, upper_u, u0
end

function _stat(stats, name::Symbol)
    stats !== nothing && hasproperty(stats, name) || return -1
    value = getproperty(stats, name)
    return value isa Integer ? Int(value) : -1
end

_vector_text(values) = "[" * join((repr(value) for value in values), ',') * "]"

function _diagnostic(
    counter::CallbackCounter,
    origins,
    half_ranges;
    retcode::AbstractString,
    stats=nothing,
    exception=nothing,
    retcode_success=nothing,
    screening_residual_linf=nothing,
    screening_finite=nothing,
    screening_in_bounds=nothing,
    screening_semantics_valid=nothing,
    screening_accepted=nothing,
)
    fields = String[
        "retcode=$retcode",
        "callbacks=$(counter.calls)",
        "callback_limit=$(counter.limit)",
        "nf=$(_stat(stats, :nf))",
        "njacs=$(_stat(stats, :njacs))",
        "nfactors=$(_stat(stats, :nfactors))",
        "nsolve=$(_stat(stats, :nsolve))",
        "nsteps=$(_stat(stats, :nsteps))",
        "nonfinite_callbacks=$(counter.nonfinite_calls)",
        "outside_bounds_callbacks=$(counter.outside_bounds_calls)",
        "bounds_transform=$BOUNDS_TRANSFORM",
        "library_bounds_transform=$LIBRARY_BOUNDS_TRANSFORM",
        "bounds_origin=$(_vector_text(origins))",
        "bounds_half_range=$(_vector_text(half_ranges))",
        "normalized_bounds=[-1.0,1.0]",
    ]
    retcode_success === nothing || push!(fields, "retcode_success=$retcode_success")
    screening_residual_linf === nothing ||
        push!(fields, "screening_residual_linf=$screening_residual_linf")
    screening_finite === nothing || push!(fields, "screening_finite=$screening_finite")
    screening_in_bounds === nothing ||
        push!(fields, "screening_in_bounds=$screening_in_bounds")
    screening_semantics_valid === nothing ||
        push!(fields, "screening_semantics_valid=$screening_semantics_valid")
    screening_accepted === nothing ||
        push!(fields, "screening_accepted=$screening_accepted")
    exception === nothing || push!(fields, "exception=$(sprint(showerror, exception))")
    return join(fields, ';')
end

function _scaled_evaluation(case, input, residual_scales, counter::CallbackCounter)
    if counter.calls >= counter.limit
        counter.exhausted = true
        throw(CallbackBudgetExceeded(counter.limit))
    end
    evaluation = evaluate_case(case, input)
    counter.calls += 1
    scaled = Float64[
        evaluation.residuals[index] / residual_scales[index] for
        index in eachindex(residual_scales)
    ]
    counter.nonfinite_calls += !evaluation.finite || !all(isfinite, scaled)
    return evaluation, scaled
end

function _failed_outcome(
    counter::CallbackCounter,
    origins,
    half_ranges,
    error,
)
    exhausted = counter.exhausted || error isa CallbackBudgetExceeded
    runner_exhausted = error isa SolverExperimentBudgetExceeded
    status = if exhausted
        "LOCAL_MAX_EVALUATIONS"
    elseif runner_exhausted
        "runner_evaluation_budget_exhausted"
    else
        "exception:$(nameof(typeof(error)))"
    end
    return SolverAttemptOutcome(
        nothing;
        status,
        evaluations=counter.calls,
        diagnostic=_diagnostic(
            counter,
            origins,
            half_ranges;
            retcode=exhausted ? "BUDGET" : runner_exhausted ? "RUNNER-BUDGET" : "EXCEPTION",
            exception=error,
        ),
    )
end

function _run_candidate(
    case::SolverExperimentCase,
    start::AbstractVector,
    kind::Symbol,
    max_iterations::Int,
    max_evaluations::Int,
)
    origins = Float64[]
    half_ranges = Float64[]
    counter = CallbackCounter(0, max_evaluations, false, 0, 0)
    try
        origins, half_ranges, lower_u, upper_u, u0 = _bounds_transform(case, start)
        residual_scales = collect(Float64, case.residual_scales)
        length(residual_scales) == case.residual_dimension ||
            throw(DimensionMismatch("residual scales have wrong dimension"))
        all(scale -> isfinite(scale) && scale > 0, residual_scales) ||
            throw(ArgumentError("residual scales must be finite and positive"))

        function scaled_residual!(output, u, _)
            outside = any(u .< lower_u) || any(u .> upper_u)
            counter.outside_bounds_calls += outside
            x = origins .+ half_ranges .* u
            _, scaled = _scaled_evaluation(case, x, residual_scales, counter)
            output .= scaled
            return output
        end

        function_object = NonlinearFunction(
            scaled_residual!;
            resid_prototype=zeros(case.residual_dimension),
        )
        problem = NonlinearLeastSquaresProblem(
            function_object,
            u0,
            nothing;
            lb=lower_u,
            ub=upper_u,
        )
        solution = NonlinearSolve.solve(
            problem,
            _algorithm(kind);
            abstol=ABSOLUTE_TOLERANCE,
            reltol=RELATIVE_TOLERANCE,
            maxiters=max_iterations,
        )
        if counter.exhausted
            return SolverAttemptOutcome(
                nothing;
                status="LOCAL_MAX_EVALUATIONS",
                evaluations=counter.calls,
                diagnostic=_diagnostic(
                    counter,
                    origins,
                    half_ranges;
                    retcode="BUDGET",
                    stats=solution.stats,
                ),
            )
        end
        normalized_endpoint = collect(Float64, solution.u)
        endpoint = origins .+ half_ranges .* normalized_endpoint
        retcode_success = NonlinearSolve.SciMLBase.successful_retcode(solution.retcode)
        endpoint_finite = all(isfinite, endpoint)
        endpoint_in_bounds = endpoint_finite && all(
            case.lower_bounds[index] <= endpoint[index] <= case.upper_bounds[index] for
            index in eachindex(endpoint)
        )
        screening_residual_linf = Inf
        screening_finite = false
        screening_semantics_valid = false
        reported_accepted = false
        if endpoint_in_bounds
            screening_evaluation, scaled_endpoint_residual =
                _scaled_evaluation(case, endpoint, residual_scales, counter)
            screening_finite = screening_evaluation.finite &&
                               all(isfinite, scaled_endpoint_residual)
            screening_semantics_valid = screening_evaluation.semantics_valid
            screening_residual_linf =
                maximum(abs, scaled_endpoint_residual; init=0.0)
            reported_accepted = screening_finite && screening_semantics_valid &&
                                screening_residual_linf <= ABSOLUTE_TOLERANCE
        end
        iterations = max(0, _stat(solution.stats, :nsteps))
        return SolverAttemptOutcome(
            endpoint;
            status=string(solution.retcode),
            reported_converged=retcode_success,
            reported_accepted,
            evaluations=counter.calls,
            iterations,
            diagnostic=_diagnostic(
                counter,
                origins,
                half_ranges;
                retcode=string(solution.retcode),
                stats=solution.stats,
                retcode_success,
                screening_residual_linf,
                screening_finite,
                screening_in_bounds=endpoint_in_bounds,
                screening_semantics_valid,
                screening_accepted=reported_accepted,
            ),
        )
    catch error
        error isa InterruptException && rethrow()
        return _failed_outcome(counter, origins, half_ranges, error)
    end
end

"""Build a truth-blind NonlinearSolve 4.20.2 solver-lab v1 candidate."""
function nonlinear_solve_variant(
    kind::Symbol;
    max_iterations::Integer=DEFAULT_MAX_ITERATIONS,
    max_evaluations::Integer=DEFAULT_MAX_EVALUATIONS,
)
    max_iterations > 0 || throw(ArgumentError("max_iterations must be positive"))
    max_evaluations > 0 || throw(ArgumentError("max_evaluations must be positive"))
    max_iterations <= typemax(Int) || throw(ArgumentError("max_iterations is too large"))
    max_evaluations <= typemax(Int) || throw(ArgumentError("max_evaluations is too large"))
    name = _variant_name(kind)
    actual_version = string(Base.pkgversion(NonlinearSolve))
    actual_version == NONLINEAR_SOLVE_VERSION || error(
        "EXP-LOCAL-004 requires NonlinearSolve $NONLINEAR_SOLVE_VERSION, got $actual_version",
    )
    NonlinearSolve.SciMLBase.allowsbounds(_algorithm(kind)) && error(
        "NonlinearSolve bounds semantics changed; audit the EXP-LOCAL-004 adapter",
    )
    configuration = (;
        package="NonlinearSolve",
        package_version=NONLINEAR_SOLVE_VERSION,
        algorithm=kind === :tr ? "TrustRegion" : "LevenbergMarquardt",
        derivative_backend=DERIVATIVE_BACKEND,
        finite_difference_step=FINITE_DIFFERENCE_STEP,
        bounds_transform=BOUNDS_TRANSFORM,
        library_bounds_transform=LIBRARY_BOUNDS_TRANSFORM,
        native_bounds=false,
        normalized_lower=-1.0,
        normalized_upper=1.0,
        residual_scaling="declared",
        abstol=ABSOLUTE_TOLERANCE,
        reltol=RELATIVE_TOLERANCE,
        max_iterations=Int(max_iterations),
        max_evaluations=Int(max_evaluations),
        endpoint_policy="solution.u-only",
        reported_acceptance="finite-bounds-semantics-scaled-residual-linf",
        acceptance_residual_tolerance=ABSOLUTE_TOLERANCE,
        acceptance_requires_semantics_valid=true,
        geodesic_acceleration=kind === :lm ? "enabled" : "not-applicable",
        geodesic_finite_difference_step=kind === :lm ? 0.1 : 0.0,
        geodesic_alpha=kind === :lm ? 0.75 : 0.0,
    )
    runner = (case, start) -> _run_candidate(
        case,
        start,
        kind,
        Int(max_iterations),
        Int(max_evaluations),
    )
    return SolverVariant(name, runner; configuration)
end

nls_tr_variant(; kwargs...) = nonlinear_solve_variant(:tr; kwargs...)
nls_lm_variant(; kwargs...) = nonlinear_solve_variant(:lm; kwargs...)

export ABSOLUTE_TOLERANCE,
    BOUNDS_TRANSFORM,
    DEFAULT_MAX_EVALUATIONS,
    DEFAULT_MAX_ITERATIONS,
    DERIVATIVE_BACKEND,
    EXPERIMENT_ID,
    FINITE_DIFFERENCE_STEP,
    LIBRARY_BOUNDS_TRANSFORM,
    NONLINEAR_SOLVE_VERSION,
    RELATIVE_TOLERANCE,
    nonlinear_solve_variant,
    nls_lm_variant,
    nls_tr_variant

end
