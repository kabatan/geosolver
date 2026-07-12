module ExperimentLocal010

using GeoTargetBase
using GeoTargetBenchmarks
using GeoTargetCore
using LinearAlgebra

const EXPERIMENT_ID = "EXP-LOCAL-010"
const CALLBACK_CAP = 600
const RESIDUAL_TOLERANCE = 1.0e-12
const PROOF_STEP = cbrt(eps(Float64))
const PROOF_RADIUS = 1.0e-6
const ARMIJO = 1.0e-4
const ALPHAS = (1.0, 0.5, 0.25, 0.125)
const MAX_CORRECTIONS = 3
const _SEMANTICS_GUARD = NodeId("exp-local-010-semantics")

struct _Budget
    used::Base.RefValue{Int}
    cap::Int
end

struct CorrectionResult
    endpoint::Union{Nothing,Tuple}
    status::Symbol
    evaluations::Int
    corrections::Int
    proof_count::Int
    trial_count::Int
    invalid_trials::Int
    sigma_min::Float64
    eta::Float64
    backward_error::Float64
end

function _oracle_observation(case, input)
    evaluation = evaluate_case(case, input)
    relations = Tuple(
        RelationObservation(
            NodeId("exp-local-010-residual-$index"),
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

_residual(observation::OracleObservation) =
    Float64[relation.scaled for relation in observation.relations]

function _observation_valid(observation::OracleObservation)
    observation.status == EVAL_OK || return false
    residual = _residual(observation)
    !isempty(residual) && all(isfinite, residual) || return false
    all(guard -> guard.valid, observation.guards) || return false
    all(domain -> domain.valid, observation.domains) || return false
    return true
end

function _semantics_signature(observation::OracleObservation)
    return (
        Tuple((guard.strict, guard.valid) for guard in observation.guards),
        Tuple((domain.strict, domain.valid) for domain in observation.domains),
        Tuple(branch.decision for branch in observation.branches),
    )
end

function _eligible(attempt::LocalAttempt, lower, upper)
    x = collect(Float64, attempt.final)
    length(x) == length(lower) || return false
    all(isfinite, x) || return false
    all(lower .<= x .<= upper) || return false
    _observation_valid(attempt.observation) || return false
    residual = _residual(attempt.observation)
    return norm(residual, Inf) <= RESIDUAL_TOLERANCE
end

function _evaluate_cached!(cache, evaluate_fn, u, origins, scales, budget::_Budget)
    key = Tuple(u)
    haskey(cache, key) && return cache[key]
    if budget.used[] >= budget.cap
        return nothing
    end
    budget.used[] += 1
    observation = try
        evaluate_fn(origins .+ scales .* u)
    catch error
        error isa InterruptException && rethrow()
        nothing
    end
    cache[key] = observation
    return observation
end

function _stable(observation, signature)
    observation isa OracleObservation || return false
    _observation_valid(observation) || return false
    return _semantics_signature(observation) == signature
end

function _stencil_scheme(u_j, h)
    if u_j - h >= -1.0 && u_j + h <= 1.0
        return :central
    elseif u_j + 2h <= 1.0
        return :forward
    elseif u_j - 2h >= -1.0
        return :backward
    end
    return :none
end

function _stencil_column!(
    cache,
    evaluate_fn,
    u,
    column,
    step,
    scheme,
    base_residual,
    signature,
    origins,
    scales,
    budget,
)
    points = Vector{Vector{Float64}}()
    coefficients = Float64[]
    denominator = 1.0
    if scheme === :central
        plus = copy(u); plus[column] += step
        minus = copy(u); minus[column] -= step
        points = [plus, minus]
        coefficients = [1.0, -1.0]
        denominator = 2step
    else
        direction = scheme === :forward ? 1.0 : -1.0
        one = copy(u); one[column] += direction * step
        two = copy(u); two[column] += direction * 2step
        points = [one, two]
        coefficients = direction .* [4.0, -1.0]
        denominator = 2step
    end
    observations = OracleObservation[]
    for point in points
        observation = _evaluate_cached!(cache, evaluate_fn, point, origins, scales, budget)
        _stable(observation, signature) || return nothing
        push!(observations, observation)
    end
    sample_residuals = [_residual(observation) for observation in observations]
    derivative = if scheme === :central
        (sample_residuals[1] .- sample_residuals[2]) ./ denominator
    else
        direction = scheme === :forward ? 1.0 : -1.0
        direction .* (-3 .* base_residual .+ 4 .* sample_residuals[1] .- sample_residuals[2]) ./ denominator
    end
    all(isfinite, derivative) || return nothing
    gamma = 8eps(Float64) / (1 - 8eps(Float64))
    numerator_bound = if scheme === :central
        abs.(sample_residuals[1]) .+ abs.(sample_residuals[2])
    else
        3 .* abs.(base_residual) .+ 4 .* abs.(sample_residuals[1]) .+
        abs.(sample_residuals[2])
    end
    rounding = norm(gamma .* numerator_bound ./ denominator)
    return derivative, rounding
end

function _jacobian_pair!(
    cache,
    evaluate_fn,
    u,
    base_observation,
    origins,
    scales,
    budget,
)
    residual = _residual(base_observation)
    rows = length(residual)
    columns = length(u)
    rows >= columns || return nothing
    signature = _semantics_signature(base_observation)
    coarse = zeros(Float64, rows, columns)
    fine = zeros(Float64, rows, columns)
    rounding = 0.0
    for column in 1:columns
        h = PROOF_STEP * max(1.0, abs(u[column]))
        scheme = _stencil_scheme(u[column], h)
        scheme === :none && return nothing
        coarse_column = _stencil_column!(
            cache, evaluate_fn, u, column, h, scheme, residual, signature,
            origins, scales, budget,
        )
        coarse_column === nothing && return nothing
        fine_column = _stencil_column!(
            cache, evaluate_fn, u, column, h / 2, scheme, residual, signature,
            origins, scales, budget,
        )
        fine_column === nothing && return nothing
        coarse[:, column] .= coarse_column[1]
        fine[:, column] .= fine_column[1]
        rounding += coarse_column[2]^2 + fine_column[2]^2
    end
    eta = opnorm(coarse - fine, 2) + sqrt(rounding)
    singular_minimum = min(minimum(svdvals(coarse)), minimum(svdvals(fine)))
    isfinite(eta) && isfinite(singular_minimum) && singular_minimum > 2eta || return nothing
    coarse_step = qr(coarse, ColumnNorm()) \ (-residual)
    fine_step = qr(fine, ColumnNorm()) \ (-residual)
    all(isfinite, coarse_step) && all(isfinite, fine_step) || return nothing
    backward_error = max(
        norm(coarse_step),
        norm(fine_step),
        norm(coarse_step - fine_step),
    )
    isfinite(backward_error) && backward_error <= PROOF_RADIUS || return nothing
    return (;
        coarse,
        fine,
        step=fine_step,
        eta,
        sigma_min=singular_minimum,
        backward_error,
    )
end

function _result(endpoint, status, budget, corrections, proofs, trials, invalid, proof)
    return CorrectionResult(
        endpoint === nothing ? nothing : Tuple(endpoint),
        status,
        budget.used[],
        corrections,
        proofs,
        trials,
        invalid,
        proof === nothing ? NaN : proof.sigma_min,
        proof === nothing ? NaN : proof.eta,
        proof === nothing ? NaN : proof.backward_error,
    )
end

"""Run the preregistered endpoint-only correction or its same-work shadow."""
function correct_endpoint(
    evaluate_fn,
    attempt::LocalAttempt,
    origins::AbstractVector,
    scales::AbstractVector,
    lower::AbstractVector,
    upper::AbstractVector;
    shadow::Bool=false,
    callback_cap::Integer=CALLBACK_CAP,
)
    lower_values = collect(Float64, lower)
    upper_values = collect(Float64, upper)
    origin_values = collect(Float64, origins)
    scale_values = collect(Float64, scales)
    original = collect(Float64, attempt.final)
    budget = _Budget(Ref(attempt.evaluations), Int(callback_cap))
    if !_eligible(attempt, lower_values, upper_values)
        return _result(original, :not_eligible, budget, 0, 0, 0, 0, nothing)
    end
    u = (original .- origin_values) ./ scale_values
    cache = Dict{Tuple,Any}(Tuple(u) => attempt.observation)
    observation = attempt.observation
    initial_signature = _semantics_signature(observation)
    corrections = 0
    proofs = 0
    trials = 0
    invalid = 0
    final_proof = nothing
    while corrections < MAX_CORRECTIONS
        proof = _jacobian_pair!(
            cache, evaluate_fn, u, observation, origin_values, scale_values, budget,
        )
        proofs += 1
        proof === nothing && return _result(
            shadow ? original : nothing,
            :unknown,
            budget,
            corrections,
            proofs,
            trials,
            invalid,
            nothing,
        )
        final_proof = proof
        norm(proof.step) <= eps(Float64)^(4 / 5) && break
        residual = _residual(observation)
        merit = 0.5 * sum(abs2, residual)
        slope = dot(proof.fine' * residual, proof.step)
        isfinite(slope) && slope < 0 || break
        accepted = false
        for alpha in ALPHAS
            trial_u = u .+ alpha .* proof.step
            trials += 1
            if !all(-1.0 .<= trial_u .<= 1.0)
                invalid += 1
                continue
            end
            trial_observation = _evaluate_cached!(
                cache, evaluate_fn, trial_u, origin_values, scale_values, budget,
            )
            if !_stable(trial_observation, _semantics_signature(observation))
                invalid += 1
                continue
            end
            trial_residual = _residual(trial_observation)
            trial_merit = 0.5 * sum(abs2, trial_residual)
            if trial_merit <= merit + ARMIJO * alpha * slope
                u = trial_u
                observation = trial_observation
                corrections += 1
                accepted = true
                break
            end
        end
        accepted || break
    end
    if corrections > 0
        final_proof = _jacobian_pair!(
            cache, evaluate_fn, u, observation, origin_values, scale_values, budget,
        )
        proofs += 1
        final_proof === nothing && return _result(
            shadow ? original : nothing,
            :unknown,
            budget,
            corrections,
            proofs,
            trials,
            invalid,
            nothing,
        )
    end
    final_x = origin_values .+ scale_values .* u
    final_valid = all(isfinite, final_x) && all(lower_values .<= final_x .<= upper_values) &&
                  _observation_valid(observation) &&
                  _semantics_signature(observation) == initial_signature &&
                  norm(_residual(observation), Inf) <= RESIDUAL_TOLERANCE
    final_valid || return _result(
        shadow ? original : nothing,
        :unknown,
        budget,
        corrections,
        proofs,
        trials,
        invalid,
        nothing,
    )
    endpoint = shadow ? original : final_x
    return _result(endpoint, :certified, budget, corrections, proofs, trials, invalid, final_proof)
end

function _diagnostic(base, correction, shadow)
    fields = (
        "base_status=$(base.status)",
        "correction_status=$(correction.status)",
        "callbacks=$(correction.evaluations)",
        "corrections=$(correction.corrections)",
        "proofs=$(correction.proof_count)",
        "trials=$(correction.trial_count)",
        "invalid_trials=$(correction.invalid_trials)",
        "sigma_min=$(correction.sigma_min)",
        "eta=$(correction.eta)",
        "backward_error=$(correction.backward_error)",
        "shadow=$shadow",
    )
    return join(fields, ';')
end

function endpoint_correction_variant(; shadow::Bool=false)
    name = shadow ? "E1-FD2-CPQR3-SHADOW" : "E1-FD2-CPQR3"
    configuration = (;
        base="prod-tol-120x600",
        callback_cap=CALLBACK_CAP,
        proof_step=PROOF_STEP,
        proof_radius=PROOF_RADIUS,
        maximum_corrections=MAX_CORRECTIONS,
        shadow,
    )
    runner = function (case, start)
        lower = collect(Float64, case.lower_bounds)
        upper = collect(Float64, case.upper_bounds)
        origins = (lower .+ upper) ./ 2
        scales = (upper .- lower) ./ 2
        options = LocalSolveOptions(
            max_iterations=120,
            max_evaluations=CALLBACK_CAP,
            residual_tolerance=RESIDUAL_TOLERANCE,
            initial_damping=1.0e-3,
            finite_difference_step=PROOF_STEP,
        )
        base = solve_local(
            input -> _oracle_observation(case, input),
            start;
            origins,
            scales,
            lower,
            upper,
            options,
        )
        correction = correct_endpoint(
            input -> _oracle_observation(case, input),
            base,
            origins,
            scales,
            lower,
            upper;
            shadow,
        )
        pass_through = correction.status == :not_eligible
        accepted = pass_through ? base.accepted :
                   correction.endpoint !== nothing && correction.status == :certified &&
                   (shadow ? base.accepted : true)
        return SolverAttemptOutcome(
            correction.endpoint;
            status=pass_through ? string(base.status) : String(correction.status),
            reported_converged=pass_through ? base.status == LOCAL_CONVERGED :
                               correction.status == :certified,
            reported_accepted=accepted,
            evaluations=correction.evaluations,
            iterations=base.iterations + correction.corrections,
            diagnostic=_diagnostic(base, correction, shadow),
        )
    end
    return SolverVariant(name, runner; configuration)
end

export CALLBACK_CAP,
    CorrectionResult,
    correct_endpoint,
    endpoint_correction_variant

end
