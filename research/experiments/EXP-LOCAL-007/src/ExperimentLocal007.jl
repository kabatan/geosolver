module ExperimentLocal007

const EXPERIMENT_DIRECTORY = normpath(joinpath(@__DIR__, ".."))
const PYTHON_ENVIRONMENT = joinpath(EXPERIMENT_DIRECTORY, "python", ".venv")
const PYTHON_EXECUTABLE = joinpath(PYTHON_ENVIRONMENT, "bin", "python")

isfile(PYTHON_EXECUTABLE) || error(
    "EXP-LOCAL-007 Python environment is missing; run `uv sync --project " *
    "research/experiments/EXP-LOCAL-007/python --python 3.12.11 --frozen`",
)
ENV["JULIA_CONDAPKG_BACKEND"] = "Null"
ENV["JULIA_PYTHONCALL_EXE"] = PYTHON_EXECUTABLE

using GeoTargetBenchmarks
using PythonCall

normpath(String(PythonCall.python_executable_path())) == normpath(PYTHON_EXECUTABLE) || error(
    "EXP-LOCAL-007 loaded an unexpected Python interpreter: " *
    string(PythonCall.python_executable_path()),
)

const EXPERIMENT_ID = "EXP-LOCAL-007"
const SCIPY_VERSION = "1.18.0"
const DEFAULT_MAX_CALLBACKS = 600
const ACCEPTANCE_RESIDUAL_TOLERANCE = 1.0e-12
const STEP_TOLERANCE = 1.0e-12
const INITIAL_STEP_FACTOR = 100.0
const BOUNDARY_INTERIOR_MARGIN = sqrt(eps(Float64))
const LOWER_OPEN_UNIT = nextfloat(-1.0)
const UPPER_OPEN_UNIT = prevfloat(1.0)
const BOUNDS_TRANSFORM = "midpoint-half-range-plus-open-tanh"
const PYTHON_BRIDGE_DIRECTORY = joinpath(EXPERIMENT_DIRECTORY, "python")

struct CallbackBudgetExceeded <: Exception
    limit::Int
end

Base.showerror(io::IO, error::CallbackBudgetExceeded) =
    print(io, "candidate callback budget ", error.limit, " exhausted")

struct InvalidResidualEvaluation <: Exception
    role::Symbol
end

Base.showerror(io::IO, error::InvalidResidualEvaluation) =
    print(io, "invalid ", error.role, " residual evaluation")

mutable struct CallbackLedger
    calls::Int
    hard_limit::Int
    algorithm_limit::Int
    exhausted::Bool
    runner_exhausted::Bool
    residual_calls::Int
    endpoint_screen_calls::Int
    nonfinite_calls::Int
    semantic_invalid_calls::Int
    invalid_algorithm_calls::Int
    oracle_exceptions::Int
end

CallbackLedger(limit::Int) = CallbackLedger(
    0,
    limit,
    limit - 1,
    false,
    false,
    0,
    0,
    0,
    0,
    0,
    0,
)

struct BoundsMap
    lower::Vector{Float64}
    upper::Vector{Float64}
    origin::Vector{Float64}
    half_range::Vector{Float64}
end

function _bridge()
    sys = pyimport("sys")
    path = pyconvert(Vector{String}, sys.path)
    PYTHON_BRIDGE_DIRECTORY in path || sys.path.insert(0, PYTHON_BRIDGE_DIRECTORY)
    return pyimport("geotarget_scipy_hybr_bridge")
end

_package_version() = pyconvert(String, _bridge().package_version())

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
        throw(ArgumentError("bounds transform must be finite"))
    initial = collect(Float64, start)
    all(isfinite, initial) || throw(ArgumentError("start must be finite"))
    all(lower .<= initial .<= upper) ||
        throw(ArgumentError("start must lie within bounds"))
    normalized = clamp.((initial .- origin) ./ half_range, -1.0, 1.0)
    interior = clamp.(
        normalized,
        -1.0 + BOUNDARY_INTERIOR_MARGIN,
        1.0 - BOUNDARY_INTERIOR_MARGIN,
    )
    unconstrained = atanh.(interior)
    all(isfinite, unconstrained) || throw(ArgumentError("inverse tanh map must be finite"))
    return BoundsMap(lower, upper, origin, half_range), unconstrained, normalized
end

_open_tanh(value::Float64) = clamp(tanh(value), LOWER_OPEN_UNIT, UPPER_OPEN_UNIT)

function _normalized_coordinates(unconstrained)
    return Float64[_open_tanh(Float64(value)) for value in unconstrained]
end

function _physical_coordinates(bounds::BoundsMap, unconstrained)
    normalized = _normalized_coordinates(unconstrained)
    return bounds.origin .+ bounds.half_range .* normalized, normalized
end

function _increment_role!(ledger::CallbackLedger, role::Symbol)
    if role === :residual
        ledger.residual_calls += 1
    elseif role === :endpoint_screen
        ledger.endpoint_screen_calls += 1
    else
        throw(ArgumentError("unknown callback role: $role"))
    end
    return nothing
end

function _decrement_role!(ledger::CallbackLedger, role::Symbol)
    role === :residual && (ledger.residual_calls -= 1)
    role === :endpoint_screen && (ledger.endpoint_screen_calls -= 1)
    return nothing
end

function _charge!(ledger::CallbackLedger, role::Symbol)
    limit = role === :endpoint_screen ? ledger.hard_limit : ledger.algorithm_limit
    if ledger.calls >= limit
        ledger.exhausted = true
        throw(CallbackBudgetExceeded(limit))
    end
    ledger.calls += 1
    _increment_role!(ledger, role)
    return nothing
end

function _scaled_evaluation(
    case::SolverExperimentCase,
    bounds::BoundsMap,
    unconstrained,
    residual_scales,
    ledger::CallbackLedger,
    role::Symbol,
)
    length(unconstrained) == case.dimension ||
        throw(DimensionMismatch("unconstrained point has wrong dimension"))
    _charge!(ledger, role)
    finite_input = all(isfinite, unconstrained)
    input, normalized = if finite_input
        _physical_coordinates(bounds, unconstrained)
    else
        fill(NaN, case.dimension), fill(NaN, case.dimension)
    end
    evaluation = try
        evaluate_case(case, input)
    catch error
        if error isa SolverExperimentBudgetExceeded
            ledger.runner_exhausted = true
            ledger.calls -= 1
            _decrement_role!(ledger, role)
        else
            ledger.oracle_exceptions += 1
        end
        rethrow()
    end
    scaled = Float64[
        evaluation.residuals[index] / residual_scales[index] for
        index in eachindex(residual_scales)
    ]
    finite = finite_input && evaluation.finite && all(isfinite, normalized) &&
             all(isfinite, scaled)
    semantics_valid = finite && evaluation.semantics_valid
    ledger.nonfinite_calls += !finite
    ledger.semantic_invalid_calls += finite && !semantics_valid
    return scaled, semantics_valid, evaluation, input, normalized
end

function _pyfield(result, name::Symbol, ::Type{T}, fallback) where {T}
    try
        return pyconvert(T, getproperty(result, name))
    catch
        return fallback
    end
end

_vector_text(values) = "[" * join((repr(value) for value in values), ',') * "]"

function _diagnostic(
    ledger::CallbackLedger,
    bounds::Union{Nothing,BoundsMap};
    applicability="square",
    status=-99,
    success=false,
    message="",
    nfev=-1,
    screening_residual_linf=nothing,
    screening_finite=nothing,
    screening_in_bounds=nothing,
    screening_semantics_valid=nothing,
    screening_accepted=nothing,
    exception=nothing,
)
    fields = String[
        "applicability=$applicability",
        "scipy_status=$status",
        "scipy_success=$success",
        "scipy_message=$(replace(String(message), ';' => ','))",
        "scipy_nfev=$nfev",
        "callbacks=$(ledger.calls)",
        "callback_hard_limit=$(ledger.hard_limit)",
        "algorithm_callback_limit=$(ledger.algorithm_limit)",
        "endpoint_screen_reservation=1",
        "residual_callbacks=$(ledger.residual_calls)",
        "endpoint_screen_callbacks=$(ledger.endpoint_screen_calls)",
        "nonfinite_callbacks=$(ledger.nonfinite_calls)",
        "semantic_invalid_callbacks=$(ledger.semantic_invalid_calls)",
        "invalid_algorithm_callbacks=$(ledger.invalid_algorithm_calls)",
        "oracle_exceptions=$(ledger.oracle_exceptions)",
        "bounds_transform=$BOUNDS_TRANSFORM",
        "boundary_interior_margin=$BOUNDARY_INTERIOR_MARGIN",
        "normalized_open_lower=$LOWER_OPEN_UNIT",
        "normalized_open_upper=$UPPER_OPEN_UNIT",
    ]
    if bounds !== nothing
        push!(fields, "bounds_origin=$(_vector_text(bounds.origin))")
        push!(fields, "bounds_half_range=$(_vector_text(bounds.half_range))")
    end
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

function _failed_outcome(ledger, bounds, error)
    status = if ledger.runner_exhausted
        "runner_evaluation_budget_exhausted"
    elseif ledger.exhausted
        "LOCAL_MAX_EVALUATIONS"
    else
        "exception:$(nameof(typeof(error)))"
    end
    return SolverAttemptOutcome(
        nothing;
        status,
        evaluations=ledger.calls,
        diagnostic=_diagnostic(ledger, bounds; exception=error),
    )
end

function _inapplicable_outcome(case, ledger)
    return SolverAttemptOutcome(
        nothing;
        status="INAPPLICABLE_NONSQUARE",
        evaluations=0,
        diagnostic=_diagnostic(
            ledger,
            nothing;
            applicability="inapplicable-residual-dimension-not-equal-variable-dimension",
            message="MINPACK HYBRD requires a square residual system",
        ),
    )
end

function _run_candidate(
    case::SolverExperimentCase,
    start::AbstractVector,
    max_callbacks::Int,
)
    ledger = CallbackLedger(max_callbacks)
    case.residual_dimension == case.dimension || return _inapplicable_outcome(case, ledger)
    bounds = nothing
    try
        bounds, unconstrained_start, _ = _bounds_map(case, start)
        residual_scales = collect(Float64, case.residual_scales)
        length(residual_scales) == case.residual_dimension ||
            throw(DimensionMismatch("residual scales have wrong dimension"))
        all(value -> isfinite(value) && value > 0, residual_scales) ||
            throw(ArgumentError("residual scales must be finite and positive"))

        function residual_callback(python_point)
            unconstrained = pyconvert(Vector{Float64}, python_point)
            residual, valid, _, _, _ = _scaled_evaluation(
                case,
                bounds,
                unconstrained,
                residual_scales,
                ledger,
                :residual,
            )
            if !valid
                ledger.invalid_algorithm_calls += 1
                throw(InvalidResidualEvaluation(:algorithm))
            end
            return residual
        end

        result = _bridge().solve(
            residual_callback,
            unconstrained_start;
            maxfev=ledger.algorithm_limit,
            xtol=STEP_TOLERANCE,
            factor=INITIAL_STEP_FACTOR,
        )
        scipy_status = _pyfield(result, :status, Int, -99)
        scipy_success = _pyfield(result, :success, Bool, false)
        scipy_message = _pyfield(result, :message, String, "")
        nfev = _pyfield(result, :nfev, Int, -1)
        unconstrained_endpoint = pyconvert(Vector{Float64}, result.x)

        endpoint = nothing
        endpoint_in_bounds = false
        screening_residual_linf = Inf
        screening_finite = false
        screening_semantics_valid = false
        reported_accepted = false
        if length(unconstrained_endpoint) == case.dimension && all(isfinite, unconstrained_endpoint)
            physical_endpoint, _ = _physical_coordinates(bounds, unconstrained_endpoint)
            endpoint = physical_endpoint
            endpoint_finite = all(isfinite, physical_endpoint)
            endpoint_in_bounds = endpoint_finite && all(
                case.lower_bounds[index] <= physical_endpoint[index] <= case.upper_bounds[index] for
                index in eachindex(physical_endpoint)
            )
            if endpoint_in_bounds
                screened_residual, _, screening_evaluation, _, _ = _scaled_evaluation(
                    case,
                    bounds,
                    unconstrained_endpoint,
                    residual_scales,
                    ledger,
                    :endpoint_screen,
                )
                screening_finite = screening_evaluation.finite &&
                                   all(isfinite, screened_residual)
                screening_semantics_valid = screening_evaluation.semantics_valid
                screening_residual_linf = maximum(abs, screened_residual; init=0.0)
                reported_accepted = screening_finite && screening_semantics_valid &&
                                    screening_residual_linf <= ACCEPTANCE_RESIDUAL_TOLERANCE
            end
        end
        return SolverAttemptOutcome(
            endpoint;
            status="SCIPY_STATUS_$scipy_status",
            reported_converged=scipy_success,
            reported_accepted,
            evaluations=ledger.calls,
            iterations=0,
            diagnostic=_diagnostic(
                ledger,
                bounds;
                status=scipy_status,
                success=scipy_success,
                message=scipy_message,
                nfev,
                screening_residual_linf,
                screening_finite,
                screening_in_bounds=endpoint_in_bounds,
                screening_semantics_valid,
                screening_accepted=reported_accepted,
            ),
        )
    catch error
        error isa InterruptException && rethrow()
        return _failed_outcome(ledger, bounds, error)
    end
end

"""Build the truth-blind SciPy 1.18.0 MINPACK-HYBRD comparator."""
function scipy_hybr_variant(; max_callbacks::Integer=DEFAULT_MAX_CALLBACKS)
    max_callbacks >= 2 || throw(ArgumentError("max_callbacks must be at least two"))
    max_callbacks <= typemax(Int) || throw(ArgumentError("max_callbacks is too large"))
    actual_version = _package_version()
    actual_version == SCIPY_VERSION || error(
        "EXP-LOCAL-007 requires SciPy $SCIPY_VERSION, got $actual_version",
    )
    configuration = (;
        package="SciPy",
        package_version=SCIPY_VERSION,
        algorithm="root(method=hybr)/MINPACK-HYBRD",
        method="hybr",
        applicability="residual_dimension==dimension",
        nonsquare_policy="typed-inapplicable-zero-callbacks",
        coordinate_transform=BOUNDS_TRANSFORM,
        forward_map="u=tanh(w)-with-open-float-saturation-clamp",
        inverse_start_map="w=atanh(clamp(u,-1+sqrt(eps),1-sqrt(eps)))",
        boundary_interior_margin=BOUNDARY_INTERIOR_MARGIN,
        normalized_open_lower=LOWER_OPEN_UNIT,
        normalized_open_upper=UPPER_OPEN_UNIT,
        residual_scaling="declared",
        jacobian="MINPACK-initial-or-restart-forward-difference-plus-Broyden-rank-one-updates",
        step_tolerance=STEP_TOLERANCE,
        initial_step_factor=INITIAL_STEP_FACTOR,
        max_callbacks=Int(max_callbacks),
        algorithm_callback_limit=Int(max_callbacks) - 1,
        endpoint_screen_reservation=1,
        all_callbacks_charged=true,
        invalid_trial_policy="abort-no-pseudoresidual",
        endpoint_policy="scipy-result-x-only",
        scipy_success_role="diagnostic-only",
        reported_acceptance="finite-bounds-semantics-scaled-residual-linf",
        acceptance_residual_tolerance=ACCEPTANCE_RESIDUAL_TOLERANCE,
        acceptance_requires_semantics_valid=true,
        identity_routing=false,
    )
    runner = (case, start) -> _run_candidate(case, start, Int(max_callbacks))
    return SolverVariant("SCIPY-HYBR", runner; configuration)
end

export ACCEPTANCE_RESIDUAL_TOLERANCE,
    BOUNDARY_INTERIOR_MARGIN,
    BOUNDS_TRANSFORM,
    DEFAULT_MAX_CALLBACKS,
    EXPERIMENT_ID,
    INITIAL_STEP_FACTOR,
    LOWER_OPEN_UNIT,
    PYTHON_EXECUTABLE,
    SCIPY_VERSION,
    STEP_TOLERANCE,
    UPPER_OPEN_UNIT,
    scipy_hybr_variant

end
