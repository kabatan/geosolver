module ExperimentLocal013

using GeoTargetBase
using GeoTargetBenchmarks
using GeoTargetCore
using LinearAlgebra

const EXPERIMENT_ID = "EXP-LOCAL-013"
const CANDIDATE_NAME = "E4-EXP-GUARD-SLACK-CPQR"
const SHADOW_NAME = "E4-EXP-GUARD-SLACK-CPQR-SHADOW"
const CALLBACK_CAP = 600
const RESIDUAL_TOLERANCE = 1.0e-12
const FD_STEP = cbrt(eps(Float64))
const MAX_CORRECTIONS = 3
const INITIAL_TRUST_RADIUS = 1.0
const MAXIMUM_TRUST_RADIUS = 4.0
const ALPHAS = (1.0, 0.5, 0.25, 0.125)
const ARMIJO = 1.0e-4
const _SEMANTICS_GUARD = NodeId("exp-local-013-semantics")

const STATUS_HEURISTIC = "E4_HEURISTIC_GUARD_SEPARATED"
const STATUS_UNKNOWN = "E4_HEURISTIC_UNKNOWN"
const _E1_CONFIGURATION = (;
    base="prod-tol-120x600",
    callback_cap=600,
    proof_step=cbrt(eps(Float64)),
    proof_radius=1.0e-6,
    maximum_corrections=3,
    shadow=false,
)

mutable struct _State
    calls::Int
    fd_calls::Int
    trial_calls::Int
    invalid_fd::Int
    invalid_trials::Int
    central_columns::Int
    inward_columns::Int
    proofs::Int
    corrections::Int
    trust_radius::Float64
    separation_lower::Float64
    correction_radius::Float64
    reason::String
end

_State(calls) = _State(
    calls, 0, 0, 0, 0, 0, 0, 0, 0, INITIAL_TRUST_RADIUS, NaN, NaN, "not-run",
)

struct _GuardContract
    tokens::Vector{UInt64}
    branch_token::Union{Nothing,UInt64}
end

struct _Sample
    residual::Vector{Float64}
    guard::Vector{Float64}
end

function _oracle_observation(case, capture, input)
    evaluation = evaluate_case(case, input)
    capture[Tuple(Float64.(input))] = evaluation
    relations = Tuple(
        RelationObservation(
            NodeId("exp-local-013-residual-$index"),
            evaluation.residuals[index],
            case.residual_scales[index],
            evaluation.residuals[index] / case.residual_scales[index],
            nothing,
        ) for index in 1:case.residual_dimension
    )
    semantics = GuardObservation(
        _SEMANTICS_GUARD,
        evaluation.semantics_valid ? 1.0 : -1.0,
        true,
        1.0,
        evaluation.semantics_valid,
    )
    return OracleObservation(
        relations,
        evaluation.target,
        (semantics,),
        (),
        (),
        evaluation.finite ? EVAL_OK : EVAL_NONFINITE,
        1,
        nothing,
    )
end

function _base_solve(case, start, lower, upper, origins, scales)
    capture = Dict{Tuple,SolverCaseEvaluation}()
    options = LocalSolveOptions(
        max_iterations=120,
        max_evaluations=CALLBACK_CAP,
        residual_tolerance=RESIDUAL_TOLERANCE,
        initial_damping=1.0e-3,
        finite_difference_step=FD_STEP,
    )
    attempt = solve_local(
        input -> _oracle_observation(case, capture, input),
        start;
        origins,
        scales,
        lower,
        upper,
        options,
    )
    return attempt, get(capture, Tuple(attempt.final), nothing)
end

_base_residual(attempt) = Float64[
    relation.scaled for relation in attempt.observation.relations
]

function _base_qualified(attempt, evaluation, lower, upper)
    evaluation isa SolverCaseEvaluation || return false
    endpoint = collect(Float64, attempt.final)
    length(endpoint) == length(lower) || return false
    all(isfinite, endpoint) && all(lower .<= endpoint .<= upper) || return false
    attempt.observation.status == EVAL_OK || return false
    all(guard -> guard.valid, attempt.observation.guards) || return false
    evaluation.finite && evaluation.semantics_valid || return false
    residual = _base_residual(attempt)
    return !isempty(residual) && all(isfinite, residual) &&
           norm(residual, Inf) <= RESIDUAL_TOLERANCE
end

function _strict_guard_map(evaluation::SolverCaseEvaluation)
    guards = Dict{UInt64,Float64}()
    for guard in evaluation.public_guards
        guard.strict || continue
        haskey(guards, guard.token) && return nothing
        isfinite(guard.scale) && guard.scale > 0 || return nothing
        value = guard.margin / guard.scale
        isfinite(value) || return nothing
        guards[guard.token] = value
    end
    return guards
end

function _guard_contract(evaluation, expected_count, require_branch)
    evaluation isa SolverCaseEvaluation || return nothing
    guards = _strict_guard_map(evaluation)
    guards === nothing && return nothing
    length(guards) == expected_count || return nothing
    tokens = sort!(collect(keys(guards)))
    all(token -> guards[token] > 0, tokens) || return nothing
    require_branch && evaluation.branch_token === nothing && return nothing
    contract = _GuardContract(tokens, evaluation.branch_token)
    return contract, Float64[guards[token] for token in tokens]
end

function _sample(evaluation, case, contract::_GuardContract)
    evaluation isa SolverCaseEvaluation || return nothing
    evaluation.finite && evaluation.semantics_valid || return nothing
    evaluation.branch_token == contract.branch_token || return nothing
    guards = _strict_guard_map(evaluation)
    guards === nothing && return nothing
    sort!(collect(keys(guards))) == contract.tokens || return nothing
    guard = Float64[guards[token] for token in contract.tokens]
    all(value -> isfinite(value) && value > 0, guard) || return nothing
    residual = Float64[
        evaluation.residuals[index] / case.residual_scales[index] for
        index in 1:case.residual_dimension
    ]
    all(isfinite, residual) || return nothing
    return _Sample(residual, guard)
end

function _evaluate_sample!(cache, case, bounds, u, contract, state; fd)
    key = Tuple(u)
    haskey(cache, key) && return cache[key]
    state.calls < CALLBACK_CAP || return nothing
    all(isfinite, u) && all(-1.0 .<= u .<= 1.0) || return nothing
    state.calls += 1
    fd ? (state.fd_calls += 1) : (state.trial_calls += 1)
    evaluation = try
        evaluate_case(case, bounds.origin .+ bounds.half_range .* u)
    catch error
        error isa InterruptException && rethrow()
        nothing
    end
    sample = evaluation === nothing ? nothing : _sample(evaluation, case, contract)
    if sample === nothing
        fd ? (state.invalid_fd += 1) : (state.invalid_trials += 1)
    end
    cache[key] = sample
    return sample
end

function _augmented(sample::_Sample, z, guard_scale)
    exponential = exp.(z)
    all(value -> isfinite(value) && value > 0, exponential) || return nothing
    value = vcat(sample.residual, sample.guard ./ guard_scale .- exponential)
    return all(isfinite, value) ? value : nothing
end

_differenced_value(sample::_Sample, guard_scale) =
    vcat(sample.residual, sample.guard ./ guard_scale)

function _rounding_bound(values, denominator)
    gamma = 8eps(Float64) / (1 - 8eps(Float64))
    return gamma .* values ./ denominator
end

function _central_estimate(plus, minus, radius, guard_scale)
    plus_value = _differenced_value(plus, guard_scale)
    minus_value = _differenced_value(minus, guard_scale)
    denominator = 2radius
    derivative = (plus_value .- minus_value) ./ denominator
    rounding = _rounding_bound(abs.(plus_value) .+ abs.(minus_value), denominator)
    return derivative, rounding
end

function _one_sided_estimate(base, first, second, radius, direction, guard_scale)
    base_value = _differenced_value(base, guard_scale)
    first_value = _differenced_value(first, guard_scale)
    second_value = _differenced_value(second, guard_scale)
    denominator = 2radius
    derivative = direction .* (
        -3 .* base_value .+ 4 .* first_value .- second_value
    ) ./ denominator
    numerator = 3 .* abs.(base_value) .+ 4 .* abs.(first_value) .+ abs.(second_value)
    return derivative, _rounding_bound(numerator, denominator)
end

function _point!(cache, case, bounds, u, column, offset, contract, state)
    point = copy(u)
    point[column] += offset
    all(-1.0 .<= point .<= 1.0) || return nothing
    return _evaluate_sample!(cache, case, bounds, point, contract, state; fd=true)
end

function _fd_column!(cache, case, bounds, u, column, base, contract, guard_scale, state)
    h = FD_STEP
    plus_h = _point!(cache, case, bounds, u, column, h, contract, state)
    minus_h = _point!(cache, case, bounds, u, column, -h, contract, state)
    plus_h2 = _point!(cache, case, bounds, u, column, h / 2, contract, state)
    minus_h2 = _point!(cache, case, bounds, u, column, -h / 2, contract, state)
    if plus_h !== nothing && minus_h !== nothing &&
       plus_h2 !== nothing && minus_h2 !== nothing
        state.central_columns += 1
        coarse, coarse_round = _central_estimate(plus_h, minus_h, h, guard_scale)
        fine, fine_round = _central_estimate(plus_h2, minus_h2, h / 2, guard_scale)
        return coarse, fine, coarse_round, fine_round
    end

    candidates = NamedTuple[]
    for direction in (1.0, -1.0)
        first_h2 = _point!(
            cache, case, bounds, u, column, direction * h / 2, contract, state,
        )
        first_h = _point!(
            cache, case, bounds, u, column, direction * h, contract, state,
        )
        second_h = _point!(
            cache, case, bounds, u, column, direction * 2h, contract, state,
        )
        first_h2 === nothing && continue
        first_h === nothing && continue
        second_h === nothing && continue
        score = minimum(vcat(
            first_h2.guard ./ guard_scale,
            first_h.guard ./ guard_scale,
            second_h.guard ./ guard_scale,
        ))
        push!(candidates, (; direction, first_h2, first_h, second_h, score))
    end
    isempty(candidates) && return nothing
    selected = candidates[argmax(candidate.score for candidate in candidates)]
    coarse, coarse_round = _one_sided_estimate(
        base, selected.first_h, selected.second_h, h, selected.direction, guard_scale,
    )
    fine, fine_round = _one_sided_estimate(
        base, selected.first_h2, selected.first_h, h / 2, selected.direction, guard_scale,
    )
    state.inward_columns += 1
    return coarse, fine, coarse_round, fine_round
end

function _cpqr_full_step(jacobian, residual)
    rows, columns = size(jacobian)
    rows >= columns > 0 || return nothing
    column_scale = Float64[norm(view(jacobian, :, column), 2) for column in 1:columns]
    all(value -> isfinite(value) && value > 0, column_scale) || return nothing
    scaled = jacobian ./ reshape(column_scale, 1, :)
    factor = try
        qr(scaled, ColumnNorm())
    catch
        return nothing
    end
    triangular = Matrix(factor.R)
    diagonal = abs.(diag(view(triangular, 1:columns, 1:columns)))
    maximum_diagonal = maximum(diagonal; init=0.0)
    threshold = max(rows, columns) * eps(Float64) * maximum_diagonal
    count(value -> value > threshold, diagonal) == columns || return nothing
    step = try
        (factor \ (-residual)) ./ column_scale
    catch
        return nothing
    end
    return all(isfinite, step) ? step : nothing
end

function _proof!(cache, case, bounds, u, z, base, contract, guard_scale, state)
    n = length(u)
    k = length(z)
    rows = length(base.residual) + k
    columns = n + k
    rows >= columns || return nothing
    coarse = zeros(Float64, rows, columns)
    fine = zeros(Float64, rows, columns)
    coarse_round = zeros(Float64, rows, columns)
    fine_round = zeros(Float64, rows, columns)
    for column in 1:n
        estimate = _fd_column!(
            cache, case, bounds, u, column, base, contract, guard_scale, state,
        )
        estimate === nothing && return nothing
        coarse[:, column] .= estimate[1]
        fine[:, column] .= estimate[2]
        coarse_round[:, column] .= estimate[3]
        fine_round[:, column] .= estimate[4]
    end
    exponential = exp.(z)
    all(value -> isfinite(value) && value > 0, exponential) || return nothing
    residual_rows = length(base.residual)
    for guard_index in 1:k
        row = residual_rows + guard_index
        column = n + guard_index
        coarse[row, column] = -exponential[guard_index]
        fine[row, column] = -exponential[guard_index]
    end
    value = _augmented(base, z, guard_scale)
    value === nothing && return nothing
    envelope = abs.(coarse .- fine) .+ coarse_round .+ fine_round
    residual_envelope = view(envelope, 1:residual_rows, 1:n)
    eta = opnorm(residual_envelope, 2)
    sigma_min = min(
        minimum(svdvals(view(coarse, 1:residual_rows, 1:n))),
        minimum(svdvals(view(fine, 1:residual_rows, 1:n))),
    )
    isfinite(eta) && isfinite(sigma_min) && sigma_min > 2eta || return nothing
    coarse_step = _cpqr_full_step(coarse, value)
    fine_step = _cpqr_full_step(fine, value)
    coarse_step === nothing && return nothing
    fine_step === nothing && return nothing
    guard_error = Float64[
        norm(view(envelope, residual_rows + index, 1:n), 2) for index in 1:k
    ]
    state.proofs += 1
    return (;
        coarse,
        fine,
        coarse_step,
        fine_step,
        step=fine_step,
        eta,
        sigma_min,
        guard_error,
    )
end

function _guard_separation(sample, proof, u, guard_scale, state)
    n = length(u)
    stability = 1 - 2proof.eta / proof.sigma_min
    isfinite(stability) && stability > 0 || return false
    coarse_u = view(proof.coarse_step, 1:n)
    fine_u = view(proof.fine_step, 1:n)
    lifted_radius = max(
        norm(coarse_u, 2),
        norm(fine_u, 2),
        norm(coarse_u .- fine_u, 2),
    ) / stability
    residual_denominator = proof.sigma_min - proof.eta
    residual_denominator > 0 || return false
    residual_radius = norm(sample.residual, 2) / residual_denominator
    correction_radius = max(lifted_radius, residual_radius)
    isfinite(correction_radius) || return false
    ratios = sample.guard ./ guard_scale
    residual_rows = length(sample.residual)
    lowers = Float64[]
    for index in eachindex(ratios)
        gradient = view(proof.fine, residual_rows + index, 1:n)
        error = proof.guard_error[index]
        uncertainty = (norm(gradient, 2) + error) * correction_radius +
                      error * max(correction_radius, eps(Float64))
        uncertainty = nextfloat(
            (1 + sqrt(eps(Float64))) * uncertainty +
            8eps(Float64) * max(1.0, abs(ratios[index])),
        )
        push!(lowers, ratios[index] - uncertainty)
    end
    bound_lower = minimum(vcat(u .+ 1, 1 .- u)) - correction_radius
    push!(lowers, bound_lower)
    state.correction_radius = correction_radius
    state.separation_lower = minimum(lowers)
    return all(isfinite, lowers) && minimum(lowers) > 0
end

function _update_trust_radius!(state, ratio, accepted_step_norm)
    ratio < 0.25 && (state.trust_radius *= 0.25)
    ratio > 0.75 && accepted_step_norm >= 0.9state.trust_radius &&
        (state.trust_radius = min(2state.trust_radius, MAXIMUM_TRUST_RADIUS))
    return state.trust_radius
end

function _run_lifted(case, base, base_evaluation, bounds, contract, guard_scale, state)
    u = (collect(Float64, base.final) .- bounds.origin) ./ bounds.half_range
    z = zeros(Float64, length(guard_scale))
    base_sample = _sample(base_evaluation, case, contract)
    base_sample === nothing && (state.reason = "base-guard-contract-mismatch"; return nothing)
    cache = Dict{Tuple,Union{Nothing,_Sample}}(Tuple(u) => base_sample)
    sample = base_sample
    final_proof = nothing
    while state.corrections < MAX_CORRECTIONS
        proof = _proof!(
            cache, case, bounds, u, z, sample, contract, guard_scale, state,
        )
        proof === nothing && (state.reason = "lifted-proof-unknown"; return nothing)
        final_proof = proof
        norm(proof.step, 2) <= eps(Float64)^(4 / 5) && break
        step = copy(proof.step)
        step_norm = norm(step, 2)
        if step_norm > state.trust_radius
            step .*= state.trust_radius / step_norm
        end
        value = _augmented(sample, z, guard_scale)
        merit = 0.5 * dot(value, value)
        slope = dot(proof.fine' * value, step)
        isfinite(slope) && slope < 0 || (state.reason = "lifted-nondescent"; return nothing)
        accepted = false
        for alpha in ALPHAS
            effective = alpha .* step
            trial_u = u .+ view(effective, 1:length(u))
            trial_z = z .+ view(effective, length(u) + 1:length(effective))
            all(-1.0 .<= trial_u .<= 1.0) || (state.invalid_trials += 1; continue)
            trial_sample = _evaluate_sample!(
                cache, case, bounds, trial_u, contract, state; fd=false,
            )
            trial_sample === nothing && continue
            trial_value = _augmented(trial_sample, trial_z, guard_scale)
            trial_value === nothing && (state.invalid_trials += 1; continue)
            trial_merit = 0.5 * dot(trial_value, trial_value)
            model_value = value .+ proof.fine * effective
            predicted = merit - 0.5 * dot(model_value, model_value)
            actual = merit - trial_merit
            ratio = predicted > 0 ? actual / predicted : -Inf
            if trial_merit <= merit + ARMIJO * alpha * slope && ratio > 1.0e-4
                u = collect(trial_u)
                z = collect(trial_z)
                sample = trial_sample
                state.corrections += 1
                _update_trust_radius!(state, ratio, norm(effective, 2))
                accepted = true
                break
            end
        end
        accepted || (state.reason = "lifted-trust-step-rejected"; break)
    end
    if state.corrections > 0
        final_proof = _proof!(
            cache, case, bounds, u, z, sample, contract, guard_scale, state,
        )
        final_proof === nothing && (state.reason = "final-reproof-unknown"; return nothing)
    end
    final_proof === nothing && (state.reason = "missing-final-proof"; return nothing)
    value = _augmented(sample, z, guard_scale)
    value === nothing && (state.reason = "nonfinite-lifted-residual"; return nothing)
    norm(sample.residual, Inf) <= RESIDUAL_TOLERANCE ||
        (state.reason = "final-original-residual"; return nothing)
    norm(value, Inf) <= RESIDUAL_TOLERANCE ||
        (state.reason = "final-lifted-residual"; return nothing)
    _guard_separation(sample, final_proof, u, guard_scale, state) ||
        (state.reason = "heuristic-guard-separation-unknown"; return nothing)
    state.reason = "heuristic-guard-separated"
    return bounds.origin .+ bounds.half_range .* u
end

function _diagnostic(base, state, shadow, routed)
    return join((
        "mechanism=HEURISTIC-NOT-ANSWER-AUTHORITY",
        "base_status=$(base.status)",
        "route=$routed",
        "callbacks=$(state.calls)",
        "fd_calls=$(state.fd_calls)",
        "trial_calls=$(state.trial_calls)",
        "invalid_fd=$(state.invalid_fd)",
        "invalid_trials=$(state.invalid_trials)",
        "central_columns=$(state.central_columns)",
        "inward_columns=$(state.inward_columns)",
        "proofs=$(state.proofs)",
        "corrections=$(state.corrections)",
        "trust_radius=$(state.trust_radius)",
        "correction_radius=$(state.correction_radius)",
        "separation_lower=$(state.separation_lower)",
        "reason=$(state.reason)",
        "shadow=$shadow",
    ), ';')
end

"""Build the diagnostic strict-guard slack lane with a frozen E1 capability fallback."""
function guard_slack_variant(fallback::SolverVariant; shadow::Bool=false)
    expected_fallback = shadow ? "E1-FD2-CPQR3-SHADOW" : "E1-FD2-CPQR3"
    fallback.name == expected_fallback || throw(ArgumentError(
        "fallback must be $expected_fallback",
    ))
    expected_configuration = merge(_E1_CONFIGURATION, (; shadow))
    propertynames(fallback.configuration) == propertynames(expected_configuration) &&
        fallback.configuration == expected_configuration || throw(ArgumentError(
            "fallback configuration must exactly match frozen $expected_fallback",
        ))
    name = shadow ? SHADOW_NAME : CANDIDATE_NAME
    configuration = (;
        base="prod-tol-120x600",
        mechanism="HEURISTIC-normalized-exponential-strict-guard-slack",
        public_capability_route="public_guard_count>0",
        guardless_fallback=expected_fallback,
        callback_cap=CALLBACK_CAP,
        fd="branch-token-stable-h-h2-central-or-inward-second-order-one-sided",
        linear_step="full-column-rank-cpqr",
        maximum_corrections=MAX_CORRECTIONS,
        final_gate="HEURISTIC-guard-separation-not-z-cutoff",
        high_precision_answer_authority=true,
        shadow,
    )
    runner = function (case, start)
        case.public_guard_count == 0 && return fallback.run(case, start)
        lower = collect(Float64, case.lower_bounds)
        upper = collect(Float64, case.upper_bounds)
        bounds = (;
            lower,
            upper,
            origin=lower ./ 2 .+ upper ./ 2,
            half_range=upper ./ 2 .- lower ./ 2,
        )
        base, base_evaluation = _base_solve(
            case, start, lower, upper, bounds.origin, bounds.half_range,
        )
        state = _State(base.evaluations)
        if !_base_qualified(base, base_evaluation, lower, upper)
            state.reason = "base-pass-through"
            return SolverAttemptOutcome(
                base.final;
                status=string(base.status),
                reported_converged=base.status == LOCAL_CONVERGED,
                reported_accepted=base.accepted,
                evaluations=state.calls,
                iterations=base.iterations,
                diagnostic=_diagnostic(base, state, shadow, "guarded-base-pass-through"),
            )
        end
        contract_result = _guard_contract(
            base_evaluation, case.public_guard_count, case.has_branch_token,
        )
        if contract_result === nothing
            state.reason = "public-guard-contract-unknown"
            endpoint = shadow ? base.final : nothing
            return SolverAttemptOutcome(
                endpoint;
                status=STATUS_UNKNOWN,
                reported_converged=false,
                reported_accepted=shadow && base.accepted,
                evaluations=state.calls,
                iterations=base.iterations,
                diagnostic=_diagnostic(base, state, shadow, "guarded"),
            )
        end
        contract, guard_scale = contract_result
        corrected = _run_lifted(
            case, base, base_evaluation, bounds, contract, guard_scale, state,
        )
        separated = corrected !== nothing
        endpoint = shadow ? base.final : corrected
        accepted = shadow ? base.accepted : separated
        return SolverAttemptOutcome(
            endpoint;
            status=separated ? STATUS_HEURISTIC : STATUS_UNKNOWN,
            reported_converged=separated,
            reported_accepted=accepted,
            evaluations=state.calls,
            iterations=base.iterations + state.corrections,
            diagnostic=_diagnostic(base, state, shadow, "guarded-slack"),
        )
    end
    return SolverVariant(name, runner; configuration)
end

export CALLBACK_CAP,
    CANDIDATE_NAME,
    EXPERIMENT_ID,
    SHADOW_NAME,
    STATUS_HEURISTIC,
    STATUS_UNKNOWN,
    guard_slack_variant

end
