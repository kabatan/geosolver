module ExperimentLocal005

const EXPERIMENT_DIRECTORY = normpath(joinpath(@__DIR__, ".."))
const PYTHON_ENVIRONMENT = joinpath(EXPERIMENT_DIRECTORY, "python", ".venv")
const PYTHON_EXECUTABLE = joinpath(PYTHON_ENVIRONMENT, "bin", "python")

isfile(PYTHON_EXECUTABLE) || error(
    "EXP-LOCAL-005 Python environment is missing; run `uv sync --project " *
    "research/experiments/EXP-LOCAL-005/python --python 3.12.11 --frozen`",
)
ENV["JULIA_CONDAPKG_BACKEND"] = "Null"
ENV["JULIA_PYTHONCALL_EXE"] = PYTHON_EXECUTABLE

using GeoTargetBenchmarks
using PythonCall

normpath(String(PythonCall.python_executable_path())) == normpath(PYTHON_EXECUTABLE) || error(
    "EXP-LOCAL-005 loaded an unexpected Python interpreter: " *
    string(PythonCall.python_executable_path()),
)

const EXPERIMENT_ID = "EXP-LOCAL-005"
const DFOLS_VERSION = "1.6.5"
const DEFAULT_MAX_EVALUATIONS = 2_000
const ALGORITHM_MAX_EVALUATIONS = DEFAULT_MAX_EVALUATIONS - 1
const ACCEPTANCE_RESIDUAL_TOLERANCE = 1.0e-12
const OBJECTIVE_TOLERANCE = 1.0e-24
const INITIAL_TRUST_REGION_RADIUS = 0.1
const FINAL_TRUST_REGION_RADIUS = 1.0e-12
const BOUNDS_TRANSFORM = "midpoint-half-range-to-unit-box"
const PYTHON_BRIDGE_DIRECTORY = joinpath(EXPERIMENT_DIRECTORY, "python")

struct CallbackBudgetExceeded <: Exception
    limit::Int
end

Base.showerror(io::IO, error::CallbackBudgetExceeded) =
    print(io, "residual callback budget ", error.limit, " exhausted")

mutable struct CallbackCounter
    calls::Int
    limit::Int
    exhausted::Bool
    runner_exhausted::Bool
    nonfinite_calls::Int
    outside_bounds_calls::Int
end

function _bridge()
    sys = pyimport("sys")
    path = pyconvert(Vector{String}, sys.path)
    PYTHON_BRIDGE_DIRECTORY in path || sys.path.insert(0, PYTHON_BRIDGE_DIRECTORY)
    return pyimport("geotarget_dfols_bridge")
end

function _package_version()
    return pyconvert(String, _bridge().package_version())
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
    return origins, half_ranges, fill(-1.0, case.dimension), fill(1.0, case.dimension), u0
end

_vector_text(values) = "[" * join((repr(value) for value in values), ',') * "]"

function _pyfield(result, name::Symbol, ::Type{T}, fallback) where {T}
    try
        return pyconvert(T, getproperty(result, name))
    catch
        return fallback
    end
end

function _diagnostic(
    counter::CallbackCounter,
    origins,
    half_ranges;
    flag="UNAVAILABLE",
    message="",
    algorithm_evaluations=-1,
    algorithm_runs=-1,
    exception=nothing,
    screening_residual_linf=nothing,
    screening_finite=nothing,
    screening_in_bounds=nothing,
    screening_semantics_valid=nothing,
    screening_accepted=nothing,
)
    fields = String[
        "flag=$flag",
        "message=$(replace(String(message), ';' => ','))",
        "callbacks=$(counter.calls)",
        "callback_limit=$(counter.limit)",
        "algorithm_maxfun=$(max(1, counter.limit - 1))",
        "algorithm_evaluations=$algorithm_evaluations",
        "algorithm_runs=$algorithm_runs",
        "nonfinite_callbacks=$(counter.nonfinite_calls)",
        "outside_bounds_callbacks=$(counter.outside_bounds_calls)",
        "bounds_transform=$BOUNDS_TRANSFORM",
        "native_bounds=true",
        "bounds_origin=$(_vector_text(origins))",
        "bounds_half_range=$(_vector_text(half_ranges))",
        "normalized_bounds=[-1.0,1.0]",
    ]
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
    evaluation = try
        evaluate_case(case, input)
    catch error
        error isa SolverExperimentBudgetExceeded && (counter.runner_exhausted = true)
        rethrow()
    end
    counter.calls += 1
    scaled = Float64[
        evaluation.residuals[index] / residual_scales[index] for
        index in eachindex(residual_scales)
    ]
    counter.nonfinite_calls += !evaluation.finite || !all(isfinite, scaled)
    return evaluation, scaled
end

function _failed_outcome(counter, origins, half_ranges, error)
    status = if counter.runner_exhausted
        "runner_evaluation_budget_exhausted"
    elseif counter.exhausted
        "LOCAL_MAX_EVALUATIONS"
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
            flag=counter.runner_exhausted ? "RUNNER-BUDGET" :
                 counter.exhausted ? "BUDGET" : "EXCEPTION",
            exception=error,
        ),
    )
end

function _run_candidate(
    case::SolverExperimentCase,
    start::AbstractVector,
    max_evaluations::Int,
)
    origins = Float64[]
    half_ranges = Float64[]
    counter = CallbackCounter(0, max_evaluations, false, false, 0, 0)
    try
        max_evaluations >= 2 || throw(ArgumentError("max_evaluations must be at least two"))
        origins, half_ranges, lower_u, upper_u, u0 = _bounds_transform(case, start)
        residual_scales = collect(Float64, case.residual_scales)
        length(residual_scales) == case.residual_dimension ||
            throw(DimensionMismatch("residual scales have wrong dimension"))
        all(scale -> isfinite(scale) && scale > 0, residual_scales) ||
            throw(ArgumentError("residual scales must be finite and positive"))

        function scaled_residual(normalized_input)
            u = pyconvert(Vector{Float64}, normalized_input)
            outside = any(u .< lower_u) || any(u .> upper_u)
            counter.outside_bounds_calls += outside
            x = origins .+ half_ranges .* u
            _, scaled = _scaled_evaluation(case, x, residual_scales, counter)
            return scaled
        end

        result = _bridge().solve(
            scaled_residual,
            u0,
            lower_u,
            upper_u;
            maxfun=max_evaluations - 1,
            rhobeg=INITIAL_TRUST_REGION_RADIUS,
            rhoend=FINAL_TRUST_REGION_RADIUS,
            objective_tolerance=OBJECTIVE_TOLERANCE,
        )
        normalized_endpoint = pyconvert(Vector{Float64}, result.x)
        endpoint = origins .+ half_ranges .* normalized_endpoint
        flag = _pyfield(result, :flag, Int, -99)
        message = _pyfield(result, :msg, String, "")
        algorithm_evaluations = _pyfield(result, :nf, Int, -1)
        algorithm_runs = _pyfield(result, :nruns, Int, -1)
        retcode_success = flag == _pyfield(result, :EXIT_SUCCESS, Int, 0)
        local_exhausted = flag == _pyfield(result, :EXIT_MAXFUN_WARNING, Int, 1)

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
            screening_residual_linf = maximum(abs, scaled_endpoint_residual; init=0.0)
            reported_accepted = screening_finite && screening_semantics_valid &&
                                screening_residual_linf <= ACCEPTANCE_RESIDUAL_TOLERANCE
        end
        status = local_exhausted ? "LOCAL_MAX_EVALUATIONS" : "DFOLS_FLAG_$flag"
        return SolverAttemptOutcome(
            endpoint;
            status,
            reported_converged=retcode_success,
            reported_accepted,
            evaluations=counter.calls,
            iterations=0,
            diagnostic=_diagnostic(
                counter,
                origins,
                half_ranges;
                flag,
                message,
                algorithm_evaluations,
                algorithm_runs,
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

"""Build the truth-blind DFO-LS 1.6.5 solver-lab candidate."""
function dfols_variant(; max_evaluations::Integer=DEFAULT_MAX_EVALUATIONS)
    max_evaluations >= 2 || throw(ArgumentError("max_evaluations must be at least two"))
    max_evaluations <= typemax(Int) || throw(ArgumentError("max_evaluations is too large"))
    actual_version = _package_version()
    actual_version == DFOLS_VERSION || error(
        "EXP-LOCAL-005 requires DFO-LS $DFOLS_VERSION, got $actual_version",
    )
    configuration = (;
        package="DFO-LS",
        package_version=DFOLS_VERSION,
        algorithm="deterministic-interpolation-trust-region",
        derivative_backend="derivative-free-linear-residual-model",
        bounds_transform=BOUNDS_TRANSFORM,
        native_bounds=true,
        normalized_lower=-1.0,
        normalized_upper=1.0,
        residual_scaling="declared",
        initial_trust_region_radius=INITIAL_TRUST_REGION_RADIUS,
        final_trust_region_radius=FINAL_TRUST_REGION_RADIUS,
        objective_tolerance=OBJECTIVE_TOLERANCE,
        max_evaluations=Int(max_evaluations),
        algorithm_max_evaluations=Int(max_evaluations) - 1,
        endpoint_screen_reservation=1,
        interpolation_points="dimension-plus-one",
        random_initial_directions=false,
        parallel_initial_evaluations=false,
        restarts=false,
        noisy_objective=false,
        endpoint_policy="solution.x-only",
        reported_acceptance="finite-bounds-semantics-scaled-residual-linf",
        acceptance_residual_tolerance=ACCEPTANCE_RESIDUAL_TOLERANCE,
        acceptance_requires_semantics_valid=true,
    )
    runner = (case, start) -> _run_candidate(case, start, Int(max_evaluations))
    return SolverVariant("DFO-LS-TR", runner; configuration)
end

export ACCEPTANCE_RESIDUAL_TOLERANCE,
    ALGORITHM_MAX_EVALUATIONS,
    BOUNDS_TRANSFORM,
    DEFAULT_MAX_EVALUATIONS,
    DFOLS_VERSION,
    EXPERIMENT_ID,
    FINAL_TRUST_REGION_RADIUS,
    INITIAL_TRUST_REGION_RADIUS,
    OBJECTIVE_TOLERANCE,
    PYTHON_EXECUTABLE,
    dfols_variant

end
