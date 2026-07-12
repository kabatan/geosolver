module ExperimentLocal011

using GeoTargetBase
using GeoTargetBenchmarks
using GeoTargetCore
using LinearAlgebra

const EXPERIMENT_ID = "EXP-LOCAL-011"
const CANDIDATE_NAME = "E2-FD2-SVD3"
const SHADOW_NAME = "E2-FD2-SVD3-SHADOW"
const MAX_EVALUATIONS = 600
const MAX_CORRECTIONS = 3
const RESIDUAL_TOLERANCE = 1.0e-12
const FD_RADIUS = cbrt(eps(Float64))
const BX_LIMIT = 1.0e-6
const ARMIJO_COEFFICIENT = 1.0e-4
const ARMIJO_ALPHAS = (1.0, 0.5, 0.25, 0.125)

const STATUS_CERTIFIED = "E2_FD2_SVD3_CERTIFIED"
const STATUS_UNKNOWN = "E2_FD2_SVD3_UNKNOWN"
const STATUS_SHADOW = "E2_FD2_SVD3_SHADOW"

const _SEMANTICS_GUARD = NodeId("exp-local-011-semantics")

mutable struct _State
    calls::Int
    fd_calls::Int
    invalid_fd_calls::Int
    armijo_calls::Int
    invalid_armijo_calls::Int
    central_columns::Int
    one_sided_columns::Int
    proofs::Int
    corrections::Int
    last_eta::Float64
    last_sigma_min::Float64
    last_bx::Float64
    reason::String
end

_State(calls) = _State(
    calls, 0, 0, 0, 0, 0, 0, 0, 0, NaN, NaN, NaN, "not-run",
)

function _oracle_observation(case, input)
    evaluation = evaluate_case(case, input)
    relations = Tuple(
        RelationObservation(
            NodeId("exp-local-011-residual-$index"),
            evaluation.residuals[index],
            case.residual_scales[index],
            evaluation.residuals[index] / case.residual_scales[index],
            nothing,
        ) for index in 1:case.residual_dimension
    )
    guard = GuardObservation(
        _SEMANTICS_GUARD,
        evaluation.semantics_valid ? 1.0 : -1.0,
        true,
        1.0,
        evaluation.semantics_valid,
    )
    return OracleObservation(
        relations,
        evaluation.target,
        (guard,),
        (),
        (),
        evaluation.finite ? EVAL_OK : EVAL_NONFINITE,
        1,
        nothing,
    )
end

function _base_attempt(case, start)
    lower = collect(Float64, case.lower_bounds)
    upper = collect(Float64, case.upper_bounds)
    origins = lower ./ 2 .+ upper ./ 2
    scales = upper ./ 2 .- lower ./ 2
    options = LocalSolveOptions(
        max_iterations=120,
        max_evaluations=MAX_EVALUATIONS,
        residual_tolerance=RESIDUAL_TOLERANCE,
        initial_damping=1.0e-3,
        finite_difference_step=FD_RADIUS,
    )
    return solve_local(
        input -> _oracle_observation(case, input),
        start;
        origins,
        scales,
        lower,
        upper,
        options,
    )
end

function _bounds_map(case)
    lower = collect(Float64, case.lower_bounds)
    upper = collect(Float64, case.upper_bounds)
    origin = lower ./ 2 .+ upper ./ 2
    half_range = upper ./ 2 .- lower ./ 2
    length(lower) == length(upper) == case.dimension || return nothing
    all(isfinite, lower) && all(isfinite, upper) || return nothing
    all(value -> isfinite(value) && value > 0, half_range) || return nothing
    return (; lower, upper, origin, half_range)
end

_physical(bounds, u) = bounds.origin .+ bounds.half_range .* u

function _initial_residual(attempt, case)
    observation = attempt.observation
    observation.status == EVAL_OK || return nothing
    all(guard -> guard.valid, observation.guards) || return nothing
    all(domain -> domain.valid, observation.domains) || return nothing
    length(observation.relations) == case.residual_dimension || return nothing
    residual = Float64[relation.scaled for relation in observation.relations]
    return all(isfinite, residual) ? residual : nothing
end

function _evaluate_scaled(case, bounds, u, state::_State; fd::Bool)
    state.calls < MAX_EVALUATIONS || return nothing
    all(isfinite, u) && all(-1.0 .<= u .<= 1.0) || return nothing
    state.calls += 1
    fd ? (state.fd_calls += 1) : (state.armijo_calls += 1)
    evaluation = try
        evaluate_case(case, _physical(bounds, u))
    catch error
        error isa InterruptException && rethrow()
        fd ? (state.invalid_fd_calls += 1) : (state.invalid_armijo_calls += 1)
        return nothing
    end
    residual = Float64[
        evaluation.residuals[index] / case.residual_scales[index] for
        index in 1:case.residual_dimension
    ]
    valid = evaluation.finite && evaluation.semantics_valid && all(isfinite, residual)
    if !valid
        fd ? (state.invalid_fd_calls += 1) : (state.invalid_armijo_calls += 1)
        return nothing
    end
    return residual
end

_gamma(count::Int) = (count * eps(Float64)) / (1 - count * eps(Float64))

function _central_column(plus, minus, radius)
    derivative = (plus .- minus) ./ (2radius)
    rounding = _gamma(3) .* (abs.(plus) .+ abs.(minus)) ./ (2radius)
    return derivative, rounding
end

function _one_sided_column(base, first, second, radius, direction)
    derivative = direction .* (-3 .* base .+ 4 .* first .- second) ./ (2radius)
    rounding = _gamma(6) .* (
        3 .* abs.(base) .+ 4 .* abs.(first) .+ abs.(second)
    ) ./ (2radius)
    return derivative, rounding
end

function _sample!(cache, case, bounds, u, column, offset, state)
    point = copy(u)
    point[column] += offset
    all(-1.0 .<= point .<= 1.0) || return nothing
    key = Tuple(point)
    haskey(cache, key) && return cache[key]
    value = _evaluate_scaled(case, bounds, point, state; fd=true)
    cache[key] = value
    return value
end

function _fd_pair(case, bounds, u, residual, state::_State)
    m, n = case.residual_dimension, case.dimension
    m >= n || return nothing
    jacobian_h = zeros(Float64, m, n)
    jacobian_h2 = zeros(Float64, m, n)
    rounding_h = zeros(Float64, m, n)
    rounding_h2 = zeros(Float64, m, n)
    cache = Dict{Tuple,Union{Nothing,Vector{Float64}}}()
    h = FD_RADIUS
    for column in 1:n
        central_in_bounds = u[column] - h >= -1.0 && u[column] + h <= 1.0
        if central_in_bounds
            plus_h = _sample!(cache, case, bounds, u, column, h, state)
            minus_h = _sample!(cache, case, bounds, u, column, -h, state)
            plus_h2 = _sample!(cache, case, bounds, u, column, h / 2, state)
            minus_h2 = _sample!(cache, case, bounds, u, column, -h / 2, state)
            plus_h === nothing && return nothing
            minus_h === nothing && return nothing
            plus_h2 === nothing && return nothing
            minus_h2 === nothing && return nothing
            jacobian_h[:, column], rounding_h[:, column] =
                _central_column(plus_h, minus_h, h)
            jacobian_h2[:, column], rounding_h2[:, column] =
                _central_column(plus_h2, minus_h2, h / 2)
            state.central_columns += 1
            continue
        end

        plus_room = 1.0 - u[column]
        minus_room = u[column] + 1.0
        direction = plus_room >= 2h ? 1.0 : minus_room >= 2h ? -1.0 : 0.0
        iszero(direction) && return nothing
        first_h2 = _sample!(cache, case, bounds, u, column, direction * h / 2, state)
        first_h = _sample!(cache, case, bounds, u, column, direction * h, state)
        second_h = _sample!(cache, case, bounds, u, column, direction * 2h, state)
        first_h2 === nothing && return nothing
        first_h === nothing && return nothing
        second_h === nothing && return nothing
        jacobian_h[:, column], rounding_h[:, column] =
            _one_sided_column(residual, first_h, second_h, h, direction)
        jacobian_h2[:, column], rounding_h2[:, column] =
            _one_sided_column(residual, first_h2, first_h, h / 2, direction)
        state.one_sided_columns += 1
    end
    all(isfinite, jacobian_h) && all(isfinite, jacobian_h2) || return nothing
    error_envelope = abs.(jacobian_h .- jacobian_h2) .+ rounding_h .+ rounding_h2
    eta = opnorm(error_envelope, 2)
    isfinite(eta) || return nothing
    return (; jacobian_h, jacobian_h2, eta)
end

function _full_rank_svd_step(jacobian, residual, eta)
    m, n = size(jacobian)
    m >= n > 0 || return nothing
    factor = try
        svd(jacobian; full=false)
    catch
        return nothing
    end
    length(factor.S) == n || return nothing
    sigma_min = minimum(factor.S)
    isfinite(sigma_min) && sigma_min > 2eta || return nothing
    coefficients = (factor.U' * residual) ./ factor.S
    step = -(factor.Vt' * coefficients)
    all(isfinite, step) || return nothing
    return (; step, sigma_min)
end

function _proof(case, bounds, u, residual, state::_State)
    pair = _fd_pair(case, bounds, u, residual, state)
    pair === nothing && return nothing
    solve_h = _full_rank_svd_step(pair.jacobian_h, residual, pair.eta)
    solve_h2 = _full_rank_svd_step(pair.jacobian_h2, residual, pair.eta)
    solve_h === nothing && return nothing
    solve_h2 === nothing && return nothing
    bx = max(
        norm(solve_h.step, 2),
        norm(solve_h2.step, 2),
        norm(solve_h.step .- solve_h2.step, 2),
    )
    isfinite(bx) && bx <= BX_LIMIT || return nothing
    state.proofs += 1
    state.last_eta = pair.eta
    state.last_sigma_min = min(solve_h.sigma_min, solve_h2.sigma_min)
    state.last_bx = bx
    return (; pair..., step=solve_h2.step, bx)
end

function _armijo(case, bounds, u, residual, proof, state::_State)
    merit = 0.5 * dot(residual, residual)
    gradient = proof.jacobian_h2' * residual
    directional = dot(gradient, proof.step)
    isfinite(directional) && directional < 0 || return nothing
    for alpha in ARMIJO_ALPHAS
        trial = u .+ alpha .* proof.step
        all(-1.0 .<= trial .<= 1.0) || continue
        trial == u && continue
        trial_residual = _evaluate_scaled(case, bounds, trial, state; fd=false)
        # A semantic/domain-invalid Newton trial is branch-instability evidence,
        # not a reason to certify a shorter step on the same local model.
        trial_residual === nothing && return nothing
        trial_merit = 0.5 * dot(trial_residual, trial_residual)
        if isfinite(trial_merit) &&
           trial_merit <= merit + ARMIJO_COEFFICIENT * alpha * directional
            return trial, trial_residual
        end
    end
    return nothing
end

function _correct(case, attempt, state::_State)
    case.residual_dimension >= case.dimension || (state.reason = "m-lt-n"; return nothing)
    bounds = _bounds_map(case)
    bounds === nothing && (state.reason = "invalid-finite-box"; return nothing)
    endpoint = collect(Float64, attempt.final)
    u = (endpoint .- bounds.origin) ./ bounds.half_range
    all(isfinite, u) && all(-1.0 .<= u .<= 1.0) ||
        (state.reason = "base-endpoint-outside-box"; return nothing)
    residual = _initial_residual(attempt, case)
    residual === nothing && (state.reason = "base-observation-invalid"; return nothing)

    last_proof = nothing
    for correction_index in 1:MAX_CORRECTIONS
        proof = _proof(case, bounds, u, residual, state)
        proof === nothing && (state.reason = "proof-unknown"; return nothing)
        last_proof = proof
        trial = _armijo(case, bounds, u, residual, proof, state)
        if trial === nothing
            if all(iszero, residual)
                state.reason = "certified-exact-stationary"
                return _physical(bounds, u)
            end
            state.reason = "armijo-unknown"
            return nothing
        end
        u, residual = trial
        state.corrections = correction_index
    end

    last_proof = _proof(case, bounds, u, residual, state)
    last_proof === nothing && (state.reason = "final-reproof-unknown"; return nothing)
    if norm(residual, Inf) <= RESIDUAL_TOLERANCE
        state.reason = "certified-corrected"
        return _physical(bounds, u)
    end
    state.reason = "final-residual-too-large"
    return nothing
end

function _base_endpoint_qualified(case, attempt)
    bounds = _bounds_map(case)
    bounds === nothing && return false
    endpoint = collect(Float64, attempt.final)
    length(endpoint) == case.dimension || return false
    all(isfinite, endpoint) || return false
    all(bounds.lower .<= endpoint .<= bounds.upper) || return false
    residual = _initial_residual(attempt, case)
    residual === nothing && return false
    return norm(residual, Inf) <= RESIDUAL_TOLERANCE
end

function _diagnostic(attempt, state, certified, shadow)
    return join((
        "base_status=$(attempt.status)",
        "base_callbacks=$(attempt.evaluations)",
        "callbacks=$(state.calls)",
        "fd_calls=$(state.fd_calls)",
        "invalid_fd_calls=$(state.invalid_fd_calls)",
        "armijo_calls=$(state.armijo_calls)",
        "invalid_armijo_calls=$(state.invalid_armijo_calls)",
        "central_columns=$(state.central_columns)",
        "one_sided_columns=$(state.one_sided_columns)",
        "proofs=$(state.proofs)",
        "corrections=$(state.corrections)",
        "eta=$(state.last_eta)",
        "sigma_min=$(state.last_sigma_min)",
        "bx=$(state.last_bx)",
        "certified=$(certified)",
        "shadow=$(shadow)",
        "reason=$(state.reason)",
    ), ';')
end

function endpoint_correction_variant(; shadow::Bool=false)
    name = shadow ? SHADOW_NAME : CANDIDATE_NAME
    configuration = (;
        base="prod-tol-120x600",
        endpoint_correction="h-h2-second-order-fd-full-rank-svd",
        fd_radius=FD_RADIUS,
        rank_gate="min-sigma>2*rounding-aware-eta",
        bx_limit=BX_LIMIT,
        armijo_alphas=ARMIJO_ALPHAS,
        max_corrections=MAX_CORRECTIONS,
        max_evaluations=MAX_EVALUATIONS,
        unknown_policy=shadow ? "return-original-endpoint" : "drop-endpoint",
        identity_routing=false,
    )
    runner = function (case, start)
        attempt = _base_attempt(case, start)
        state = _State(attempt.evaluations)
        eligible = _base_endpoint_qualified(case, attempt)
        corrected = if eligible
            _correct(case, attempt, state)
        else
            state.reason = "base-pass-through"
            attempt.final
        end
        certified = eligible && corrected !== nothing
        endpoint = eligible ? (shadow ? attempt.final : corrected) : attempt.final
        accepted = eligible ? (shadow ? attempt.accepted : certified) : attempt.accepted
        return SolverAttemptOutcome(
            endpoint;
            status=eligible ?
                   (shadow ? STATUS_SHADOW : certified ? STATUS_CERTIFIED : STATUS_UNKNOWN) :
                   string(attempt.status),
            reported_converged=eligible ?
                               (shadow ? attempt.status == LOCAL_CONVERGED : certified) :
                               attempt.status == LOCAL_CONVERGED,
            reported_accepted=accepted,
            evaluations=state.calls,
            iterations=attempt.iterations + state.corrections,
            diagnostic=_diagnostic(attempt, state, certified, shadow),
        )
    end
    return SolverVariant(name, runner; configuration)
end

e2_fd2_svd3_variant() = endpoint_correction_variant(; shadow=false)
e2_fd2_svd3_shadow_variant() = endpoint_correction_variant(; shadow=true)

export BX_LIMIT,
    CANDIDATE_NAME,
    EXPERIMENT_ID,
    MAX_CORRECTIONS,
    MAX_EVALUATIONS,
    SHADOW_NAME,
    STATUS_CERTIFIED,
    STATUS_SHADOW,
    STATUS_UNKNOWN,
    e2_fd2_svd3_shadow_variant,
    e2_fd2_svd3_variant,
    endpoint_correction_variant

end
