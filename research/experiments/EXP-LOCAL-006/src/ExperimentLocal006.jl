module ExperimentLocal006

const EXPERIMENT_DIRECTORY = normpath(joinpath(@__DIR__, ".."))
const PYTHON_ENVIRONMENT = joinpath(EXPERIMENT_DIRECTORY, "python", ".venv")
const PYTHON_EXECUTABLE = joinpath(PYTHON_ENVIRONMENT, "bin", "python")

isfile(PYTHON_EXECUTABLE) || error(
    "EXP-LOCAL-006 Python environment is missing; run `uv sync --project " *
    "research/experiments/EXP-LOCAL-006/python --python 3.12.11 --frozen`",
)
ENV["JULIA_CONDAPKG_BACKEND"] = "Null"
ENV["JULIA_PYTHONCALL_EXE"] = PYTHON_EXECUTABLE

using GeoTargetBenchmarks
using PythonCall

normpath(String(PythonCall.python_executable_path())) == normpath(PYTHON_EXECUTABLE) || error(
    "EXP-LOCAL-006 loaded an unexpected Python interpreter: " *
    string(PythonCall.python_executable_path()),
)

const EXPERIMENT_ID = "EXP-LOCAL-006"
const SCIPY_VERSION = "1.18.0"
const DEFAULT_MAX_CALLBACKS = 600
const ACCEPTANCE_RESIDUAL_TOLERANCE = 1.0e-12
const FUNCTION_TOLERANCE = 1.0e-12
const STEP_TOLERANCE = 1.0e-12
const GRADIENT_TOLERANCE = 1.0e-12
const FINITE_DIFFERENCE_STEP = cbrt(eps(Float64))
const MAX_FINITE_DIFFERENCE_BACKOFFS = 8
const BOUNDS_TRANSFORM = "midpoint-half-range-to-unit-box"
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

struct GuardedFiniteDifferenceFailure <: Exception
    column::Int
end

Base.showerror(io::IO, error::GuardedFiniteDifferenceFailure) =
    print(io, "guarded finite difference failed for column ", error.column)

mutable struct CallbackLedger
    calls::Int
    hard_limit::Int
    algorithm_limit::Int
    exhausted::Bool
    runner_exhausted::Bool
    residual_calls::Int
    jacobian_base_calls::Int
    jacobian_probe_calls::Int
    endpoint_screen_calls::Int
    nonfinite_calls::Int
    semantic_invalid_calls::Int
    probe_exceptions::Int
    outside_bounds_calls::Int
    jacobian_calls::Int
    central_columns::Int
    one_sided_columns::Int
    backoff_events::Int
    failed_columns::Int
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
    0,
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

mutable struct ResidualCache
    normalized::Vector{Float64}
    residual::Vector{Float64}
    valid::Bool
end

ResidualCache() = ResidualCache(Float64[], Float64[], false)

function _bridge()
    sys = pyimport("sys")
    path = pyconvert(Vector{String}, sys.path)
    PYTHON_BRIDGE_DIRECTORY in path || sys.path.insert(0, PYTHON_BRIDGE_DIRECTORY)
    return pyimport("geotarget_scipy_trf_bridge")
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
    return BoundsMap(lower, upper, origin, half_range), normalized
end

_physical_coordinates(bounds::BoundsMap, normalized) =
    bounds.origin .+ bounds.half_range .* normalized

function _increment_role!(ledger::CallbackLedger, role::Symbol)
    if role === :residual
        ledger.residual_calls += 1
    elseif role === :jacobian_base
        ledger.jacobian_base_calls += 1
    elseif role === :jacobian_probe
        ledger.jacobian_probe_calls += 1
    elseif role === :endpoint_screen
        ledger.endpoint_screen_calls += 1
    else
        throw(ArgumentError("unknown callback role: $role"))
    end
    return nothing
end

function _decrement_role!(ledger::CallbackLedger, role::Symbol)
    if role === :residual
        ledger.residual_calls -= 1
    elseif role === :jacobian_base
        ledger.jacobian_base_calls -= 1
    elseif role === :jacobian_probe
        ledger.jacobian_probe_calls -= 1
    elseif role === :endpoint_screen
        ledger.endpoint_screen_calls -= 1
    end
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
    normalized,
    residual_scales,
    ledger::CallbackLedger,
    role::Symbol,
)
    length(normalized) == case.dimension ||
        throw(DimensionMismatch("normalized point has wrong dimension"))
    outside_bounds = !all(-1.0 .<= normalized .<= 1.0)
    ledger.outside_bounds_calls += outside_bounds
    _charge!(ledger, role)
    evaluation = try
        evaluate_case(case, _physical_coordinates(bounds, normalized))
    catch error
        if error isa SolverExperimentBudgetExceeded
            ledger.runner_exhausted = true
            ledger.calls -= 1
            _decrement_role!(ledger, role)
        end
        rethrow()
    end
    scaled = Float64[
        evaluation.residuals[index] / residual_scales[index] for
        index in eachindex(residual_scales)
    ]
    finite = evaluation.finite && all(isfinite, scaled)
    ledger.nonfinite_calls += !finite
    semantics_valid = finite && evaluation.semantics_valid && !outside_bounds
    ledger.semantic_invalid_calls += finite && !semantics_valid
    return scaled, semantics_valid, evaluation
end

function _probe(
    case,
    bounds,
    normalized,
    residual_scales,
    ledger,
)
    try
        residual, valid, _ = _scaled_evaluation(
            case,
            bounds,
            normalized,
            residual_scales,
            ledger,
            :jacobian_probe,
        )
        return residual, valid
    catch error
        error isa InterruptException && rethrow()
        error isa CallbackBudgetExceeded && rethrow()
        error isa SolverExperimentBudgetExceeded && rethrow()
        ledger.probe_exceptions += 1
        return fill(NaN, case.residual_dimension), false
    end
end

function _one_sided_column(base, side, step, direction)
    direction > 0 && return (side .- base) ./ step
    return (base .- side) ./ step
end

function _guarded_fd_jacobian(
    case::SolverExperimentCase,
    bounds::BoundsMap,
    normalized::Vector{Float64},
    base_residual::Vector{Float64},
    residual_scales::Vector{Float64},
    ledger::CallbackLedger;
    finite_difference_step::Float64=FINITE_DIFFERENCE_STEP,
    max_backoffs::Int=MAX_FINITE_DIFFERENCE_BACKOFFS,
)
    finite_difference_step > 0 && isfinite(finite_difference_step) ||
        throw(ArgumentError("finite difference step must be finite and positive"))
    max_backoffs >= 0 || throw(ArgumentError("max_backoffs must be nonnegative"))
    jacobian = zeros(Float64, case.residual_dimension, case.dimension)
    ledger.jacobian_calls += 1
    for column in 1:case.dimension
        nominal_step = finite_difference_step * max(1.0, abs(normalized[column]))
        saved_one_sided = nothing
        positive_room = 1.0 - normalized[column]
        negative_room = normalized[column] + 1.0
        exact_boundary = positive_room == 0.0 || negative_room == 0.0
        for backoff in 0:max_backoffs
            step = ldexp(nominal_step, -backoff)
            backoff > 0 && (ledger.backoff_events += 1)
            positive_feasible = step <= positive_room
            negative_feasible = step <= negative_room
            positive_residual = nothing
            negative_residual = nothing
            positive_valid = false
            negative_valid = false
            if positive_feasible
                point = copy(normalized)
                point[column] += step
                positive_residual, positive_valid = _probe(
                    case,
                    bounds,
                    point,
                    residual_scales,
                    ledger,
                )
            end
            if negative_feasible
                point = copy(normalized)
                point[column] -= step
                negative_residual, negative_valid = _probe(
                    case,
                    bounds,
                    point,
                    residual_scales,
                    ledger,
                )
            end
            if positive_valid && negative_valid
                jacobian[:, column] .=
                    (positive_residual .- negative_residual) ./ (2step)
                ledger.central_columns += 1
                saved_one_sided = nothing
                break
            end
            if positive_valid
                saved_one_sided = _one_sided_column(
                    base_residual,
                    positive_residual,
                    step,
                    1,
                )
            elseif negative_valid
                saved_one_sided = _one_sided_column(
                    base_residual,
                    negative_residual,
                    step,
                    -1,
                )
            end
            if exact_boundary && saved_one_sided !== nothing
                jacobian[:, column] .= saved_one_sided
                ledger.one_sided_columns += 1
                break
            end
            if backoff == max_backoffs
                if saved_one_sided === nothing
                    ledger.failed_columns += 1
                    throw(GuardedFiniteDifferenceFailure(column))
                end
                jacobian[:, column] .= saved_one_sided
                ledger.one_sided_columns += 1
            end
        end
    end
    all(isfinite, jacobian) || throw(GuardedFiniteDifferenceFailure(0))
    return jacobian
end

_same_point(left, right) = length(left) == length(right) &&
                           all(isequal(left[index], right[index]) for index in eachindex(left))

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
    status=-99,
    success=false,
    message="",
    nfev=-1,
    njev=-1,
    cost=NaN,
    optimality=NaN,
    screening_residual_linf=nothing,
    screening_finite=nothing,
    screening_in_bounds=nothing,
    screening_semantics_valid=nothing,
    screening_accepted=nothing,
    exception=nothing,
)
    fields = String[
        "scipy_status=$status",
        "scipy_success=$success",
        "scipy_message=$(replace(String(message), ';' => ','))",
        "scipy_nfev=$nfev",
        "scipy_njev=$njev",
        "scipy_cost=$cost",
        "scipy_optimality=$optimality",
        "callbacks=$(ledger.calls)",
        "callback_hard_limit=$(ledger.hard_limit)",
        "algorithm_callback_limit=$(ledger.algorithm_limit)",
        "endpoint_screen_reservation=1",
        "residual_callbacks=$(ledger.residual_calls)",
        "jacobian_base_callbacks=$(ledger.jacobian_base_calls)",
        "jacobian_probe_callbacks=$(ledger.jacobian_probe_calls)",
        "endpoint_screen_callbacks=$(ledger.endpoint_screen_calls)",
        "nonfinite_callbacks=$(ledger.nonfinite_calls)",
        "semantic_invalid_callbacks=$(ledger.semantic_invalid_calls)",
        "probe_exceptions=$(ledger.probe_exceptions)",
        "outside_bounds_callbacks=$(ledger.outside_bounds_calls)",
        "jacobian_calls=$(ledger.jacobian_calls)",
        "central_columns=$(ledger.central_columns)",
        "one_sided_columns=$(ledger.one_sided_columns)",
        "fd_backoff_events=$(ledger.backoff_events)",
        "failed_columns=$(ledger.failed_columns)",
        "native_bounds=true",
        "bounds_transform=$BOUNDS_TRANSFORM",
        "normalized_bounds=[-1.0,1.0]",
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

function _run_candidate(
    case::SolverExperimentCase,
    start::AbstractVector,
    max_callbacks::Int,
    finite_difference_step::Float64,
    max_backoffs::Int,
)
    ledger = CallbackLedger(max_callbacks)
    bounds = nothing
    try
        bounds, normalized_start = _bounds_map(case, start)
        residual_scales = collect(Float64, case.residual_scales)
        length(residual_scales) == case.residual_dimension ||
            throw(DimensionMismatch("residual scales have wrong dimension"))
        all(value -> isfinite(value) && value > 0, residual_scales) ||
            throw(ArgumentError("residual scales must be finite and positive"))
        lower_normalized = fill(-1.0, case.dimension)
        upper_normalized = fill(1.0, case.dimension)
        cache = ResidualCache()

        function residual_callback(python_point)
            normalized = pyconvert(Vector{Float64}, python_point)
            residual, valid, _ = _scaled_evaluation(
                case,
                bounds,
                normalized,
                residual_scales,
                ledger,
                :residual,
            )
            valid || throw(InvalidResidualEvaluation(:algorithm))
            cache.normalized = copy(normalized)
            cache.residual = copy(residual)
            cache.valid = true
            return residual
        end

        function jacobian_callback(python_point)
            normalized = pyconvert(Vector{Float64}, python_point)
            base_residual = if cache.valid && _same_point(cache.normalized, normalized)
                copy(cache.residual)
            else
                residual, valid, _ = _scaled_evaluation(
                    case,
                    bounds,
                    normalized,
                    residual_scales,
                    ledger,
                    :jacobian_base,
                )
                valid || throw(InvalidResidualEvaluation(:jacobian_base))
                cache.normalized = copy(normalized)
                cache.residual = copy(residual)
                cache.valid = true
                residual
            end
            return _guarded_fd_jacobian(
                case,
                bounds,
                normalized,
                base_residual,
                residual_scales,
                ledger;
                finite_difference_step,
                max_backoffs,
            )
        end

        result = _bridge().solve(
            residual_callback,
            jacobian_callback,
            normalized_start,
            lower_normalized,
            upper_normalized;
            max_nfev=ledger.algorithm_limit,
            ftol=FUNCTION_TOLERANCE,
            xtol=STEP_TOLERANCE,
            gtol=GRADIENT_TOLERANCE,
        )
        normalized_endpoint = pyconvert(Vector{Float64}, result.x)
        endpoint = _physical_coordinates(bounds, normalized_endpoint)
        scipy_status = _pyfield(result, :status, Int, -99)
        scipy_success = _pyfield(result, :success, Bool, false)
        scipy_message = _pyfield(result, :message, String, "")
        nfev = _pyfield(result, :nfev, Int, -1)
        njev = _pyfield(result, :njev, Int, -1)
        cost = _pyfield(result, :cost, Float64, NaN)
        optimality = _pyfield(result, :optimality, Float64, NaN)

        endpoint_finite = length(endpoint) == case.dimension && all(isfinite, endpoint)
        endpoint_in_bounds = endpoint_finite && all(
            case.lower_bounds[index] <= endpoint[index] <= case.upper_bounds[index] for
            index in eachindex(endpoint)
        )
        screening_residual_linf = Inf
        screening_finite = false
        screening_semantics_valid = false
        reported_accepted = false
        if endpoint_in_bounds
            screened_residual, _, screening_evaluation = _scaled_evaluation(
                case,
                bounds,
                normalized_endpoint,
                residual_scales,
                ledger,
                :endpoint_screen,
            )
            screening_finite = screening_evaluation.finite && all(isfinite, screened_residual)
            screening_semantics_valid = screening_evaluation.semantics_valid
            screening_residual_linf = maximum(abs, screened_residual; init=0.0)
            reported_accepted = screening_finite && screening_semantics_valid &&
                                screening_residual_linf <= ACCEPTANCE_RESIDUAL_TOLERANCE
        end
        return SolverAttemptOutcome(
            endpoint;
            status="SCIPY_STATUS_$scipy_status",
            reported_converged=scipy_success,
            reported_accepted,
            evaluations=ledger.calls,
            iterations=max(0, njev),
            diagnostic=_diagnostic(
                ledger,
                bounds;
                status=scipy_status,
                success=scipy_success,
                message=scipy_message,
                nfev,
                njev,
                cost,
                optimality,
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

"""Build the truth-blind SciPy 1.18.0 dense exact-TRF comparator."""
function scipy_trf_exact_variant(;
    max_callbacks::Integer=DEFAULT_MAX_CALLBACKS,
    finite_difference_step::Real=FINITE_DIFFERENCE_STEP,
    max_backoffs::Integer=MAX_FINITE_DIFFERENCE_BACKOFFS,
)
    max_callbacks >= 2 || throw(ArgumentError("max_callbacks must be at least two"))
    max_callbacks <= typemax(Int) || throw(ArgumentError("max_callbacks is too large"))
    max_backoffs >= 0 || throw(ArgumentError("max_backoffs must be nonnegative"))
    max_backoffs <= typemax(Int) || throw(ArgumentError("max_backoffs is too large"))
    step = Float64(finite_difference_step)
    isfinite(step) && step > 0 ||
        throw(ArgumentError("finite_difference_step must be finite and positive"))
    actual_version = _package_version()
    actual_version == SCIPY_VERSION || error(
        "EXP-LOCAL-006 requires SciPy $SCIPY_VERSION, got $actual_version",
    )
    configuration = (;
        package="SciPy",
        package_version=SCIPY_VERSION,
        algorithm="least_squares(method=trf,tr_solver=exact)",
        method="trf",
        trust_region_solver="exact",
        coordinate_transform=BOUNDS_TRANSFORM,
        native_bounds=true,
        normalized_lower=-1.0,
        normalized_upper=1.0,
        residual_scaling="declared",
        jacobian="candidate-guarded-finite-difference-callback",
        finite_difference_policy="central-preferred-one-sided-fallback",
        finite_difference_step=step,
        invalid_probe_policy="semantic-or-domain-invalid-half-step-backoff",
        max_finite_difference_backoffs=Int(max_backoffs),
        all_probes_charged=true,
        function_tolerance=FUNCTION_TOLERANCE,
        step_tolerance=STEP_TOLERANCE,
        gradient_tolerance=GRADIENT_TOLERANCE,
        x_scale=1.0,
        loss="linear",
        max_callbacks=Int(max_callbacks),
        algorithm_callback_limit=Int(max_callbacks) - 1,
        endpoint_screen_reservation=1,
        endpoint_policy="scipy-result-x-only",
        scipy_success_role="diagnostic-only",
        reported_acceptance="finite-bounds-semantics-scaled-residual-linf",
        acceptance_residual_tolerance=ACCEPTANCE_RESIDUAL_TOLERANCE,
        acceptance_requires_semantics_valid=true,
        identity_routing=false,
        upfront_rank_condition_routing=false,
    )
    runner = (case, start) -> _run_candidate(
        case,
        start,
        Int(max_callbacks),
        step,
        Int(max_backoffs),
    )
    return SolverVariant("SCIPY-TRF-EXACT", runner; configuration)
end

export ACCEPTANCE_RESIDUAL_TOLERANCE,
    BOUNDS_TRANSFORM,
    DEFAULT_MAX_CALLBACKS,
    EXPERIMENT_ID,
    FINITE_DIFFERENCE_STEP,
    FUNCTION_TOLERANCE,
    GRADIENT_TOLERANCE,
    MAX_FINITE_DIFFERENCE_BACKOFFS,
    PYTHON_EXECUTABLE,
    SCIPY_VERSION,
    STEP_TOLERANCE,
    scipy_trf_exact_variant

end
