module ExperimentLocal012

using GeoTargetBase
using GeoTargetBenchmarks
using GeoTargetCore
using LinearAlgebra

const EXPERIMENT_ID = "EXP-LOCAL-012"
const CANDIDATE_NAME = "E3-FD2-GUARD-CHART-CPQR3"
const SHADOW_NAME = "E3-FD2-GUARD-CHART-CPQR3-SHADOW"
const CALLBACK_CAP = 600
const RESIDUAL_TOLERANCE = 1.0e-12
const FD_STEP = cbrt(eps(Float64))
const BX_LIMIT = 1.0e-6
const MAX_CORRECTIONS = 3
const ALPHAS = (1.0, 0.5, 0.25, 0.125)
const ARMIJO = 1.0e-4
const STEP_TOLERANCE = eps(Float64)^(4 / 5)
const _AGGREGATE_GUARD = NodeId("exp-local-012-semantics")

@enum ProofFailure::UInt8 begin
    PROOF_NONE = 0
    PROOF_BUDGET = 1
    PROOF_CALLBACK = 2
    PROOF_NONFINITE = 3
    PROOF_NON_GUARD_SEMANTICS = 4
    PROOF_BRANCH_CHANGE = 5
    PROOF_GUARD_CHART_UNAVAILABLE = 6
    PROOF_RESIDUAL_RANK = 7
    PROOF_BACKWARD_ERROR = 8
    PROOF_ARMIJO = 9
    PROOF_GUARD_INTERIOR = 10
end

struct GuardChartSample
    residual::Vector{Float64}
    semantics_valid::Bool
    finite::Bool
    public_guards::Tuple
    branch_token::Union{Nothing,UInt64}

    function GuardChartSample(
        residual,
        semantics_valid::Bool,
        finite::Bool,
        public_guards=(),
        branch_token=nothing,
    )
        frozen = Float64[residual...]
        guards = Tuple(public_guards)
        all(guard -> guard isa SolverPublicGuardObservation, guards) ||
            throw(ArgumentError("public guards have the wrong type"))
        token = branch_token === nothing ? nothing : UInt64(branch_token)
        return new(frozen, semantics_valid, finite, guards, token)
    end
end

struct CorrectionResult
    endpoint::Union{Nothing,Tuple}
    status::Symbol
    failure::ProofFailure
    evaluations::Int
    corrections::Int
    proofs::Int
    trials::Int
    chart_columns::Int
    sigma_min::Float64
    eta::Float64
    bx::Float64
    enclosure_radius::Float64
    minimum_guard_lower::Float64
end

struct _Budget
    used::Base.RefValue{Int}
    cap::Int
end

struct _CachedEvaluation
    sample::Union{Nothing,GuardChartSample}
    failure::ProofFailure
end

_normalized_guard(guard::SolverPublicGuardObservation) = guard.margin / guard.scale

function _guard_signature(sample::GuardChartSample)
    pairs = [(guard.token, guard.strict) for guard in sample.public_guards]
    length(pairs) == length(unique(first.(pairs))) || return nothing
    sort!(pairs; by=first)
    return Tuple(pairs)
end

function _guard_values(sample::GuardChartSample, signature)
    by_token = Dict(guard.token => guard for guard in sample.public_guards)
    Set(keys(by_token)) == Set(first.(signature)) || return nothing
    values = Float64[]
    for (token, strict) in signature
        guard = by_token[token]
        guard.strict == strict || return nothing
        value = _normalized_guard(guard)
        isfinite(value) || return nothing
        push!(values, value)
    end
    return values
end

function _guards_valid(values, signature)
    return all(eachindex(values)) do index
        signature[index][2] ? values[index] > 0 : values[index] >= 0
    end
end

_branch_matches(sample, branch_token) = sample.branch_token == branch_token

function _sample_state(sample, guard_signature, branch_token)
    sample isa GuardChartSample || return PROOF_CALLBACK
    sample.finite && all(isfinite, sample.residual) || return PROOF_NONFINITE
    _branch_matches(sample, branch_token) || return PROOF_BRANCH_CHANGE
    values = _guard_values(sample, guard_signature)
    values === nothing && return PROOF_NON_GUARD_SEMANTICS
    guard_valid = _guards_valid(values, guard_signature)
    sample.semantics_valid && guard_valid && return PROOF_NONE
    !guard_valid && return PROOF_GUARD_CHART_UNAVAILABLE
    return PROOF_NON_GUARD_SEMANTICS
end

function _evaluate!(cache, evaluate_fn, u, origins, scales, budget, lower_u, upper_u)
    key = Tuple(u)
    haskey(cache, key) && return cache[key]
    if !all(isfinite, u) || !all(lower_u .<= u .<= upper_u)
        value = _CachedEvaluation(nothing, PROOF_GUARD_CHART_UNAVAILABLE)
        cache[key] = value
        return value
    end
    if budget.used[] >= budget.cap
        return _CachedEvaluation(nothing, PROOF_BUDGET)
    end
    budget.used[] += 1
    sample = try
        evaluate_fn(origins .+ scales .* u)
    catch error
        error isa InterruptException && rethrow()
        nothing
    end
    value = sample isa GuardChartSample ?
            _CachedEvaluation(sample, PROOF_NONE) :
            _CachedEvaluation(nothing, PROOF_CALLBACK)
    cache[key] = value
    return value
end

function _point(u, column, displacement)
    result = copy(u)
    result[column] += displacement
    return result
end

function _rounding_envelope(samples, coefficients, denominator)
    gamma = 8eps(Float64) / (1 - 8eps(Float64))
    bound = zeros(Float64, length(samples[1]))
    for (sample, coefficient) in zip(samples, coefficients)
        bound .+= abs(coefficient) .* abs.(sample)
    end
    return gamma .* bound ./ denominator
end

function _derivative(samples, coefficients, denominator)
    result = zeros(Float64, length(samples[1]))
    for (sample, coefficient) in zip(samples, coefficients)
        result .+= coefficient .* sample
    end
    return result ./ denominator
end

function _select_column!(
    cache,
    evaluate_fn,
    u,
    column,
    h,
    base,
    signature,
    branch_token,
    origins,
    scales,
    budget,
    lower_u,
    upper_u,
)
    slots = Dict{Tuple{Int,Int},_CachedEvaluation}()
    for numerator in (-2, -1, 1, 2)
        displacement = numerator * h / 2
        slots[(numerator, 2)] = _evaluate!(
            cache, evaluate_fn, _point(u, column, displacement), origins, scales,
            budget, lower_u, upper_u,
        )
    end
    states = Dict(key => begin
        value = slots[key]
        value.failure == PROOF_NONE ? _sample_state(value.sample, signature, branch_token) :
        value.failure
    end for key in keys(slots))
    any(state -> state in (PROOF_BUDGET, PROOF_CALLBACK, PROOF_NONFINITE), values(states)) &&
        return nothing, first(
            state for state in values(states) if
            state in (PROOF_BUDGET, PROOF_CALLBACK, PROOF_NONFINITE)
        )
    central = all(states[key] == PROOF_NONE for key in ((-2, 2), (-1, 2), (1, 2), (2, 2)))
    central && return (:central, slots), PROOF_NONE
    all(state -> state in (PROOF_NONE, PROOF_GUARD_CHART_UNAVAILABLE), values(states)) ||
        return nothing, first(
            state for state in values(states) if
            state ∉ (PROOF_NONE, PROOF_GUARD_CHART_UNAVAILABLE)
        )
    viable = Int[]
    for direction in (-1, 1)
        half_key = (direction, 2)
        full_key = (2direction, 2)
        states[half_key] == PROOF_NONE && states[full_key] == PROOF_NONE || continue
        double = _evaluate!(
            cache, evaluate_fn, _point(u, column, 2direction * h), origins, scales,
            budget, lower_u, upper_u,
        )
        slots[(2direction, 1)] = double
        double_state = double.failure == PROOF_NONE ?
                       _sample_state(double.sample, signature, branch_token) : double.failure
        double_state == PROOF_NONE && push!(viable, direction)
        double_state in (PROOF_BUDGET, PROOF_CALLBACK, PROOF_NONFINITE) &&
            return nothing, double_state
    end
    length(viable) == 1 || return nothing, PROOF_GUARD_CHART_UNAVAILABLE
    return ((only(viable) == 1 ? :forward : :backward), slots), PROOF_NONE
end

function _column_derivatives(selection, base, signature, h)
    scheme, slots = selection
    base_guard = _guard_values(base, signature)
    if scheme === :central
        minus_h = slots[(-2, 2)].sample
        minus_half = slots[(-1, 2)].sample
        plus_half = slots[(1, 2)].sample
        plus_h = slots[(2, 2)].sample
        residual_coarse_samples = [plus_h.residual, minus_h.residual]
        residual_fine_samples = [plus_half.residual, minus_half.residual]
        guard_coarse_samples = [
            _guard_values(plus_h, signature), _guard_values(minus_h, signature),
        ]
        guard_fine_samples = [
            _guard_values(plus_half, signature), _guard_values(minus_half, signature),
        ]
        coarse_coefficients = [1.0, -1.0]
        fine_coefficients = [1.0, -1.0]
        coarse_denominator = 2h
        fine_denominator = h
    else
        direction = scheme === :forward ? 1 : -1
        half = slots[(direction, 2)].sample
        full = slots[(2direction, 2)].sample
        double = slots[(2direction, 1)].sample
        residual_coarse_samples = [base.residual, full.residual, double.residual]
        residual_fine_samples = [base.residual, half.residual, full.residual]
        guard_coarse_samples = [base_guard, _guard_values(full, signature), _guard_values(double, signature)]
        guard_fine_samples = [base_guard, _guard_values(half, signature), _guard_values(full, signature)]
        coarse_coefficients = direction .* [-3.0, 4.0, -1.0]
        fine_coefficients = direction .* [-3.0, 4.0, -1.0]
        coarse_denominator = 2h
        fine_denominator = h
    end
    return (;
        residual_coarse=_derivative(residual_coarse_samples, coarse_coefficients, coarse_denominator),
        residual_fine=_derivative(residual_fine_samples, fine_coefficients, fine_denominator),
        residual_round_coarse=_rounding_envelope(residual_coarse_samples, coarse_coefficients, coarse_denominator),
        residual_round_fine=_rounding_envelope(residual_fine_samples, fine_coefficients, fine_denominator),
        guard_coarse=_derivative(guard_coarse_samples, coarse_coefficients, coarse_denominator),
        guard_fine=_derivative(guard_fine_samples, fine_coefficients, fine_denominator),
        guard_round_coarse=_rounding_envelope(guard_coarse_samples, coarse_coefficients, coarse_denominator),
        guard_round_fine=_rounding_envelope(guard_fine_samples, fine_coefficients, fine_denominator),
        chart=scheme !== :central,
    )
end

function _proof!(cache, evaluate_fn, u, base, origins, scales, budget, lower_u, upper_u)
    rows = length(base.residual)
    columns = length(u)
    rows >= columns || return nothing, PROOF_RESIDUAL_RANK
    signature = _guard_signature(base)
    signature === nothing && return nothing, PROOF_NON_GUARD_SEMANTICS
    guard_count = length(signature)
    coarse = zeros(Float64, rows, columns)
    fine = similar(coarse)
    coarse_round = similar(coarse)
    fine_round = similar(coarse)
    guard_coarse = zeros(Float64, guard_count, columns)
    guard_fine = similar(guard_coarse)
    guard_round_coarse = similar(guard_coarse)
    guard_round_fine = similar(guard_coarse)
    chart_columns = 0
    for column in 1:columns
        h = FD_STEP * max(1.0, abs(u[column]))
        selection, failure = _select_column!(
            cache, evaluate_fn, u, column, h, base, signature, base.branch_token,
            origins, scales, budget, lower_u, upper_u,
        )
        failure == PROOF_NONE || return nothing, failure
        data = _column_derivatives(selection, base, signature, h)
        coarse[:, column] .= data.residual_coarse
        fine[:, column] .= data.residual_fine
        coarse_round[:, column] .= data.residual_round_coarse
        fine_round[:, column] .= data.residual_round_fine
        guard_coarse[:, column] .= data.guard_coarse
        guard_fine[:, column] .= data.guard_fine
        guard_round_coarse[:, column] .= data.guard_round_coarse
        guard_round_fine[:, column] .= data.guard_round_fine
        chart_columns += data.chart
    end
    all(isfinite, coarse) && all(isfinite, fine) || return nothing, PROOF_NONFINITE
    eta = opnorm(coarse - fine, 2) + norm(coarse_round) + norm(fine_round)
    singular_minimum = min(minimum(svdvals(coarse)), minimum(svdvals(fine)))
    isfinite(eta) && isfinite(singular_minimum) && singular_minimum > 2eta ||
        return nothing, PROOF_RESIDUAL_RANK
    coarse_step = qr(coarse, ColumnNorm()) \ (-base.residual)
    fine_step = qr(fine, ColumnNorm()) \ (-base.residual)
    all(isfinite, coarse_step) && all(isfinite, fine_step) || return nothing, PROOF_NONFINITE
    bx = max(norm(coarse_step), norm(fine_step), norm(coarse_step - fine_step))
    isfinite(bx) && bx <= BX_LIMIT || return nothing, PROOF_BACKWARD_ERROR
    guard_eta = Float64[
        norm(guard_coarse[row, :] - guard_fine[row, :]) +
        norm(guard_round_coarse[row, :]) + norm(guard_round_fine[row, :]) for
        row in 1:guard_count
    ]
    return (;
        coarse_step,
        fine_step,
        fine,
        guard_fine,
        guard_eta,
        guard_signature=signature,
        eta,
        sigma_min=singular_minimum,
        bx,
        chart_columns,
    ), PROOF_NONE
end

function _guard_interior!(cache, evaluate_fn, u, base, proof, origins, scales, budget, lower_u, upper_u)
    center = u .+ proof.fine_step
    value = _evaluate!(cache, evaluate_fn, center, origins, scales, budget, lower_u, upper_u)
    value.failure == PROOF_NONE || return nothing, PROOF_GUARD_INTERIOR
    state = _sample_state(value.sample, proof.guard_signature, base.branch_token)
    state == PROOF_NONE || return nothing, PROOF_GUARD_INTERIOR
    mu = proof.sigma_min - 2proof.eta
    mu > 0 || return nothing, PROOF_RESIDUAL_RANK
    epsilon_x = 32eps(Float64) * max(1.0, norm(center))
    radius = norm(proof.coarse_step - proof.fine_step) +
             (norm(value.sample.residual) + 2proof.eta * norm(proof.fine_step)) / mu +
             epsilon_x
    isfinite(radius) && radius <= BX_LIMIT || return nothing, PROOF_GUARD_INTERIOR
    guard_values = _guard_values(value.sample, proof.guard_signature)
    lowers = Float64[]
    for row in eachindex(guard_values)
        value_at_center = guard_values[row]
        epsilon_guard = 32eps(Float64) * max(1.0, abs(value_at_center))
        lower = value_at_center -
                (norm(proof.guard_fine[row, :]) + 2proof.guard_eta[row]) * radius -
                epsilon_guard
        threshold = 64eps(Float64) * max(1.0, abs(value_at_center))
        strict = proof.guard_signature[row][2]
        (strict ? lower > threshold : lower >= 0) || return nothing, PROOF_GUARD_INTERIOR
        push!(lowers, lower)
    end
    return (
        radius=radius,
        minimum_guard_lower=isempty(lowers) ? Inf : minimum(lowers),
    ), PROOF_NONE
end

function _result(endpoint, status, failure, budget, corrections, proofs, trials, chart_columns, proof, model)
    return CorrectionResult(
        endpoint === nothing ? nothing : Tuple(endpoint),
        status,
        failure,
        budget.used[],
        corrections,
        proofs,
        trials,
        chart_columns,
        proof === nothing ? NaN : proof.sigma_min,
        proof === nothing ? NaN : proof.eta,
        proof === nothing ? NaN : proof.bx,
        model === nothing ? NaN : model.radius,
        model === nothing ? NaN : model.minimum_guard_lower,
    )
end

function correct_endpoint(
    evaluate_fn,
    original,
    base::GuardChartSample,
    base_evaluations::Integer,
    origins,
    scales,
    lower,
    upper;
    shadow::Bool=false,
    callback_cap::Integer=CALLBACK_CAP,
)
    original_x = collect(Float64, original)
    origins_x = collect(Float64, origins)
    scales_x = collect(Float64, scales)
    lower_x = collect(Float64, lower)
    upper_x = collect(Float64, upper)
    budget = _Budget(Ref(Int(base_evaluations)), Int(callback_cap))
    eligible = length(original_x) == length(origins_x) && all(isfinite, original_x) &&
               all(lower_x .<= original_x .<= upper_x) && base.finite &&
               base.semantics_valid && all(isfinite, base.residual) &&
               norm(base.residual, Inf) <= RESIDUAL_TOLERANCE &&
               _guard_signature(base) !== nothing &&
               _guards_valid(_guard_values(base, _guard_signature(base)), _guard_signature(base))
    eligible || return _result(original_x, :not_eligible, PROOF_NONE, budget, 0, 0, 0, 0, nothing, nothing)
    u = (original_x .- origins_x) ./ scales_x
    lower_u = (lower_x .- origins_x) ./ scales_x
    upper_u = (upper_x .- origins_x) ./ scales_x
    cache = Dict{Tuple,_CachedEvaluation}(Tuple(u) => _CachedEvaluation(base, PROOF_NONE))
    current = base
    corrections = 0
    proofs = 0
    trials = 0
    chart_columns = 0
    final_proof = nothing
    while corrections < MAX_CORRECTIONS
        proof, failure = _proof!(cache, evaluate_fn, u, current, origins_x, scales_x, budget, lower_u, upper_u)
        proofs += 1
        failure == PROOF_NONE || return _result(
            shadow ? original_x : nothing, :unknown, failure, budget, corrections,
            proofs, trials, chart_columns, nothing, nothing,
        )
        final_proof = proof
        chart_columns += proof.chart_columns
        norm(proof.fine_step) <= STEP_TOLERANCE && break
        merit = 0.5sum(abs2, current.residual)
        slope = dot(proof.fine' * current.residual, proof.fine_step)
        isfinite(slope) && slope < 0 || break
        accepted = false
        for alpha in ALPHAS
            trials += 1
            trial_u = u .+ alpha .* proof.fine_step
            value = _evaluate!(cache, evaluate_fn, trial_u, origins_x, scales_x, budget, lower_u, upper_u)
            value.failure == PROOF_BUDGET && return _result(
                shadow ? original_x : nothing, :unknown, PROOF_BUDGET, budget,
                corrections, proofs, trials, chart_columns, nothing, nothing,
            )
            value.failure == PROOF_NONE || continue
            _sample_state(value.sample, proof.guard_signature, current.branch_token) == PROOF_NONE || continue
            trial_merit = 0.5sum(abs2, value.sample.residual)
            if trial_merit <= merit + ARMIJO * alpha * slope
                u = trial_u
                current = value.sample
                corrections += 1
                accepted = true
                break
            end
        end
        accepted || return _result(
            shadow ? original_x : nothing, :unknown, PROOF_ARMIJO, budget,
            corrections, proofs, trials, chart_columns, final_proof, nothing,
        )
    end
    if corrections > 0
        final_proof, failure = _proof!(cache, evaluate_fn, u, current, origins_x, scales_x, budget, lower_u, upper_u)
        proofs += 1
        failure == PROOF_NONE || return _result(
            shadow ? original_x : nothing, :unknown, failure, budget, corrections,
            proofs, trials, chart_columns, nothing, nothing,
        )
        chart_columns += final_proof.chart_columns
    end
    model, failure = _guard_interior!(
        cache, evaluate_fn, u, current, final_proof, origins_x, scales_x, budget,
        lower_u, upper_u,
    )
    failure == PROOF_NONE || return _result(
        shadow ? original_x : nothing, :unknown, failure, budget, corrections,
        proofs, trials, chart_columns, final_proof, nothing,
    )
    final_x = origins_x .+ scales_x .* u
    final_valid = all(isfinite, final_x) && all(lower_x .<= final_x .<= upper_x) &&
                  current.finite && current.semantics_valid &&
                  norm(current.residual, Inf) <= RESIDUAL_TOLERANCE
    final_valid || return _result(
        shadow ? original_x : nothing, :unknown, PROOF_NON_GUARD_SEMANTICS,
        budget, corrections, proofs, trials, chart_columns, final_proof, nothing,
    )
    endpoint = shadow ? original_x : final_x
    return _result(endpoint, :heuristic, PROOF_NONE, budget, corrections, proofs, trials, chart_columns, final_proof, model)
end

function _case_sample(case, evaluation)
    residual = Float64[
        evaluation.residuals[index] / case.residual_scales[index] for
        index in 1:case.residual_dimension
    ]
    return GuardChartSample(
        residual,
        evaluation.semantics_valid,
        evaluation.finite,
        evaluation.public_guards,
        evaluation.branch_token,
    )
end

function _oracle(case, evaluation)
    relations = Tuple(
        RelationObservation(
            NodeId("exp-local-012-residual-$index"),
            evaluation.residuals[index],
            case.residual_scales[index],
            evaluation.residuals[index] / case.residual_scales[index],
            nothing,
        ) for index in 1:case.residual_dimension
    )
    aggregate = GuardObservation(
        _AGGREGATE_GUARD,
        evaluation.semantics_valid ? 1.0 : -1.0,
        true,
        1.0,
        evaluation.semantics_valid,
    )
    guards = Tuple(GuardObservation(
        NodeId("exp-local-012-public-$(guard.token)"),
        guard.margin,
        guard.strict,
        guard.scale,
        guard.strict ? guard.margin > 0 : guard.margin >= 0,
    ) for guard in evaluation.public_guards)
    return OracleObservation(
        relations,
        evaluation.target,
        (aggregate, guards...),
        (),
        (),
        evaluation.finite ? EVAL_OK : EVAL_NONFINITE,
        1,
        nothing,
    )
end

function endpoint_correction_variant(; shadow::Bool=false)
    name = shadow ? SHADOW_NAME : CANDIDATE_NAME
    configuration = (;
        base="prod-tol-120x600",
        callback_cap=CALLBACK_CAP,
        finite_difference="h-h2-guard-chart-cpqr",
        result_level="heuristic-not-validated",
        shadow,
    )
    runner = function (case, start)
        lower = collect(Float64, case.lower_bounds)
        upper = collect(Float64, case.upper_bounds)
        origins = (lower .+ upper) ./ 2
        scales = (upper .- lower) ./ 2
        samples = Dict{Tuple,GuardChartSample}()
        evaluate_base = function (input)
            evaluation = evaluate_case(case, input)
            samples[Tuple(input)] = _case_sample(case, evaluation)
            return _oracle(case, evaluation)
        end
        base = solve_local(
            evaluate_base,
            start;
            origins,
            scales,
            lower,
            upper,
            options=LocalSolveOptions(
                max_iterations=120,
                max_evaluations=CALLBACK_CAP,
                residual_tolerance=RESIDUAL_TOLERANCE,
                initial_damping=1.0e-3,
                finite_difference_step=FD_STEP,
            ),
        )
        base_sample = get(samples, Tuple(base.final), nothing)
        if base_sample === nothing
            return SolverAttemptOutcome(
                shadow ? base.final : nothing;
                status="LOCAL_GUARD_CHART_UNKNOWN",
                reported_accepted=shadow && base.accepted,
                evaluations=base.evaluations,
                iterations=base.iterations,
                diagnostic="failure=missing-base-public-sample;shadow=$shadow",
            )
        end
        correction = correct_endpoint(
            input -> _case_sample(case, evaluate_case(case, input)),
            base.final,
            base_sample,
            base.evaluations,
            origins,
            scales,
            lower,
            upper;
            shadow,
        )
        pass_through = correction.status == :not_eligible
        status = pass_through ? string(base.status) :
                 correction.status == :heuristic ? "LOCAL_HEURISTIC_GUARD_INTERIOR" :
                 "LOCAL_GUARD_CHART_UNKNOWN"
        accepted = pass_through ? base.accepted :
                   correction.status == :heuristic ? true : shadow && base.accepted
        diagnostic = join((
            "failure=$(correction.failure)",
            "callbacks=$(correction.evaluations)",
            "proofs=$(correction.proofs)",
            "corrections=$(correction.corrections)",
            "trials=$(correction.trials)",
            "chart_columns=$(correction.chart_columns)",
            "sigma_min=$(correction.sigma_min)",
            "eta=$(correction.eta)",
            "bx=$(correction.bx)",
            "enclosure_radius=$(correction.enclosure_radius)",
            "minimum_guard_lower=$(correction.minimum_guard_lower)",
            "result_level=heuristic-not-validated",
            "shadow=$shadow",
        ), ';')
        return SolverAttemptOutcome(
            correction.endpoint;
            status,
            reported_converged=false,
            reported_accepted=accepted,
            evaluations=correction.evaluations,
            iterations=base.iterations + correction.corrections,
            diagnostic,
        )
    end
    return SolverVariant(name, runner; configuration)
end

export ALPHAS,
    BX_LIMIT,
    CALLBACK_CAP,
    CANDIDATE_NAME,
    CorrectionResult,
    EXPERIMENT_ID,
    GuardChartSample,
    PROOF_ARMIJO,
    PROOF_BACKWARD_ERROR,
    PROOF_BRANCH_CHANGE,
    PROOF_BUDGET,
    PROOF_GUARD_CHART_UNAVAILABLE,
    PROOF_GUARD_INTERIOR,
    PROOF_NON_GUARD_SEMANTICS,
    PROOF_NONE,
    ProofFailure,
    SHADOW_NAME,
    correct_endpoint,
    endpoint_correction_variant

end
