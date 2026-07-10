struct ExperimentBudgetExceeded <: Exception
    reason::Symbol
end

Base.showerror(io::IO, error::ExperimentBudgetExceeded) =
    print(io, "EXP-SINGULAR-001 budget exhausted: ", error.reason)

mutable struct _WorkLedger{C}
    options::ExperimentOptions
    clock_ns::C
    started_ns::UInt64
    deadline_ns::UInt64
    callbacks::Int
    residual_calls::Int
    target_calls::Int
    jacobian_calls::Int
    factorization_calls::Int
    iterations::Int
    precision_equivalent_oracle_work::Int
    calls_by_precision::Dict{Int,Int}
    maximum_precision_bits::Int
    budget_exhausted::Bool
    deadline_reached::Bool
end

function _work_ledger(options::ExperimentOptions, clock_ns)
    started = UInt64(clock_ns())
    duration = UInt64(clamp(
        floor(options.wall_seconds * 1.0e9),
        1,
        typemax(UInt64) - started,
    ))
    return _WorkLedger(
        options,
        clock_ns,
        started,
        started + duration,
        0,
        0,
        0,
        0,
        0,
        0,
        0,
        Dict{Int,Int}(),
        0,
        false,
        false,
    )
end

function _check_deadline!(ledger::_WorkLedger)
    if UInt64(ledger.clock_ns()) >= ledger.deadline_ns
        ledger.deadline_reached = true
        throw(ExperimentBudgetExceeded(:deadline))
    end
    return nothing
end

function _charge_callback!(ledger::_WorkLedger, kind::Symbol, precision_bits::Int)
    _check_deadline!(ledger)
    if ledger.callbacks >= ledger.options.maximum_callbacks
        ledger.budget_exhausted = true
        throw(ExperimentBudgetExceeded(:callbacks))
    end
    ledger.callbacks += 1
    kind === :residual && (ledger.residual_calls += 1)
    kind === :target && (ledger.target_calls += 1)
    kind === :jacobian && (ledger.jacobian_calls += 1)
    precision_weight = cld(precision_bits, 53)
    ledger.precision_equivalent_oracle_work += precision_weight
    ledger.calls_by_precision[precision_bits] =
        get(ledger.calls_by_precision, precision_bits, 0) + 1
    ledger.maximum_precision_bits = max(ledger.maximum_precision_bits, precision_bits)
    return nothing
end

function _charge_factorization!(ledger::_WorkLedger)
    _check_deadline!(ledger)
    ledger.factorization_calls += 1
    return nothing
end

function _charge_iteration!(ledger::_WorkLedger)
    _check_deadline!(ledger)
    if ledger.iterations >= ledger.options.maximum_iterations
        ledger.budget_exhausted = true
        throw(ExperimentBudgetExceeded(:iterations))
    end
    ledger.iterations += 1
    return nothing
end

function _work_snapshot(ledger::_WorkLedger)
    stopped = UInt64(ledger.clock_ns())
    elapsed = stopped >= ledger.started_ns ?
              Float64(stopped - ledger.started_ns) / 1.0e9 : 0.0
    calls = Tuple(
        (precision_bits=bits, callbacks=ledger.calls_by_precision[bits]) for
        bits in sort!(collect(keys(ledger.calls_by_precision)))
    )
    return WorkSnapshot(
        ledger.callbacks,
        ledger.residual_calls,
        ledger.target_calls,
        ledger.jacobian_calls,
        ledger.factorization_calls,
        ledger.iterations,
        ledger.precision_equivalent_oracle_work,
        calls,
        elapsed,
        ledger.maximum_precision_bits,
        ledger.budget_exhausted,
        ledger.deadline_reached,
    )
end

function _finite_vector(values, expected::Int, label::AbstractString)
    frozen = collect(values)
    length(frozen) == expected || throw(DimensionMismatch("$label has wrong length"))
    all(value -> value isa Real && isfinite(value), frozen) || throw(
        ArgumentError("$label must contain finite reals"),
    )
    return frozen
end

function _evaluate_residual!(ledger, oracle::EndpointOracle, x, precision_bits)
    _charge_callback!(ledger, :residual, precision_bits)
    return _finite_vector(
        oracle.residual(x),
        oracle.residual_dimension,
        "residual callback",
    )
end

function _evaluate_target!(ledger, oracle::EndpointOracle, x, precision_bits)
    _charge_callback!(ledger, :target, precision_bits)
    value = oracle.target(x)
    value isa Real && isfinite(value) || throw(
        ArgumentError("target callback must return a finite real"),
    )
    return value
end

function _evaluate_analytic_jacobian!(ledger, oracle::EndpointOracle, x, precision_bits)
    oracle.analytic_jacobian === nothing && throw(ArgumentError("analytic Jacobian unavailable"))
    _charge_callback!(ledger, :jacobian, precision_bits)
    jacobian = Matrix(oracle.analytic_jacobian(x))
    size(jacobian) == (oracle.residual_dimension, oracle.dimension) || throw(
        DimensionMismatch("analytic Jacobian has wrong size"),
    )
    all(value -> value isa Real && isfinite(value), jacobian) || throw(
        ArgumentError("analytic Jacobian must be finite"),
    )
    return jacobian
end

function _dense_jacobian!(
    ledger,
    oracle::EndpointOracle,
    x::AbstractVector{T},
    precision_bits::Int,
    options::ExperimentOptions;
    radius_multiplier::Real=1,
) where {T<:AbstractFloat}
    jacobian = zeros(T, oracle.residual_dimension, oracle.dimension)
    base_scale = eps(T)^T(options.finite_difference_exponent)
    multiplier = T(radius_multiplier)
    for column in 1:oracle.dimension
        step = multiplier * base_scale * max(one(T), abs(x[column]))
        plus = copy(x)
        minus = copy(x)
        plus[column] += step
        minus[column] -= step
        plus_residual = _evaluate_residual!(ledger, oracle, plus, precision_bits)
        minus_residual = _evaluate_residual!(ledger, oracle, minus, precision_bits)
        jacobian[:, column] .= (plus_residual .- minus_residual) ./ (T(2) * step)
    end
    return jacobian
end

function _target_gradient!(ledger, oracle, x::AbstractVector{T}, precision_bits, options) where {T}
    gradient = zeros(T, oracle.dimension)
    base_scale = eps(T)^T(options.finite_difference_exponent)
    for column in 1:oracle.dimension
        step = base_scale * max(one(T), abs(x[column]))
        plus = copy(x)
        minus = copy(x)
        plus[column] += step
        minus[column] -= step
        plus_target = _evaluate_target!(ledger, oracle, plus, precision_bits)
        minus_target = _evaluate_target!(ledger, oracle, minus, precision_bits)
        gradient[column] = (plus_target - minus_target) / (T(2) * step)
    end
    return gradient
end

struct _RankFactorization{F,T}
    factorization::F
    rank::Int
    condition_estimate::T
    threshold::T
end

function _rank_factorization!(ledger, jacobian::AbstractMatrix{T}, options) where {T}
    _charge_factorization!(ledger)
    factorization = qr(jacobian, ColumnNorm())
    triangular = Matrix(factorization.R)
    diagonal_count = min(size(jacobian)...)
    diagonal = T[abs(triangular[index, index]) for index in 1:diagonal_count]
    largest = isempty(diagonal) ? zero(T) : maximum(diagonal)
    threshold = T(options.rank_roundoff_multiplier) * T(max(size(jacobian)...)) *
                eps(T) * max(one(T), largest)
    retained = filter(value -> value > threshold, diagonal)
    rank = length(retained)
    condition = isempty(retained) ? T(Inf) : maximum(retained) / minimum(retained)
    return _RankFactorization(factorization, rank, condition, threshold)
end

function _jacobian!(ledger, oracle, x, bits, options, derivative_mode; radius_multiplier=1)
    if derivative_mode === :analytic
        return _evaluate_analytic_jacobian!(ledger, oracle, x, bits)
    elseif derivative_mode === :dense
        return _dense_jacobian!(
            ledger,
            oracle,
            x,
            bits,
            options;
            radius_multiplier,
        )
    end
    throw(ArgumentError("unsupported derivative mode"))
end

struct _StageResult
    precision_bits::Int
    endpoint::Vector{BigFloat}
    target::BigFloat
    residual_linf::BigFloat
    correction::Vector{BigFloat}
    correction_norm::BigFloat
    rank::Int
    condition_estimate::BigFloat
    rank_stable::Bool
    converged::Bool
    reason::String
end

function _residual_goal(::Type{T}) where {T<:AbstractFloat}
    return eps(T)^(T(2) / T(3))
end

function _correction_goal(::Type{T}, options) where {T<:AbstractFloat}
    return max(sqrt(eps(T)), T(options.configuration_error_goal) / T(100))
end

function _line_search!(ledger, oracle, x, residual, step, bits)
    merit = sum(abs2, residual) / 2
    alpha = one(eltype(x))
    for _ in 1:8
        trial_x = x .+ alpha .* step
        trial_residual = _evaluate_residual!(ledger, oracle, trial_x, bits)
        trial_merit = sum(abs2, trial_residual) / 2
        if trial_merit < merit
            return trial_x, trial_residual, true
        end
        alpha /= 2
    end
    return x, residual, false
end

function _refine_stage!(
    ledger,
    input::CandidateInput,
    start,
    precision_bits::Int,
    options::ExperimentOptions,
    derivative_mode::Symbol,
)
    oracle = input.oracle
    return setprecision(BigFloat, precision_bits) do
        x = BigFloat[BigFloat(value) for value in start]
        residual = BigFloat.(_evaluate_residual!(ledger, oracle, x, precision_bits))
        last_correction = fill(BigFloat(Inf), oracle.dimension)
        last_rank = 0
        last_condition = BigFloat(Inf)
        converged = false
        reason = "maximum_iterations"

        while true
            _charge_iteration!(ledger)
            jacobian = BigFloat.(_jacobian!(
                ledger,
                oracle,
                x,
                precision_bits,
                options,
                derivative_mode,
            ))
            rank_factor = _rank_factorization!(ledger, jacobian, options)
            last_rank = rank_factor.rank
            last_condition = BigFloat(rank_factor.condition_estimate)
            if last_rank < oracle.dimension
                reason = "rank_deficient"
                last_correction = fill(BigFloat(Inf), oracle.dimension)
                break
            end
            correction = rank_factor.factorization \ (-residual)
            all(isfinite, correction) || begin
                reason = "nonfinite_correction"
                last_correction = fill(BigFloat(Inf), oracle.dimension)
                break
            end
            last_correction = BigFloat[correction...]
            correction_norm = norm(last_correction, Inf)
            residual_norm = norm(residual, Inf)
            if residual_norm <= _residual_goal(BigFloat) &&
               correction_norm <= _correction_goal(BigFloat, options)
                converged = true
                reason = "converged"
                break
            end

            trial_x, trial_residual, accepted =
                _line_search!(ledger, oracle, x, residual, last_correction, precision_bits)
            if !accepted
                # LM fallback is charged separately and used only after the
                # full-rank Gauss-Newton step fails its canonical residual model.
                damping = sqrt(eps(BigFloat)) * max(one(BigFloat), opnorm(jacobian, Inf)^2)
                augmented = [
                    jacobian
                    sqrt(damping) * Matrix{BigFloat}(I, oracle.dimension, oracle.dimension)
                ]
                right_hand_side = [-residual; zeros(BigFloat, oracle.dimension)]
                damped_factor = _rank_factorization!(ledger, augmented, options)
                damped_step = damped_factor.factorization \ right_hand_side
                trial_x, trial_residual, accepted =
                    _line_search!(ledger, oracle, x, residual, damped_step, precision_bits)
            end
            if !accepted
                reason = "no_progress"
                break
            end
            x = BigFloat[trial_x...]
            residual = BigFloat[trial_residual...]
        end

        final_residual = BigFloat.(_evaluate_residual!(ledger, oracle, x, precision_bits))
        final_target = BigFloat(_evaluate_target!(ledger, oracle, x, precision_bits))
        first_jacobian = BigFloat.(_jacobian!(
            ledger,
            oracle,
            x,
            precision_bits,
            options,
            derivative_mode;
            radius_multiplier=1,
        ))
        second_jacobian = BigFloat.(_jacobian!(
            ledger,
            oracle,
            x,
            precision_bits,
            options,
            derivative_mode;
            radius_multiplier=0.5,
        ))
        first_rank = _rank_factorization!(ledger, first_jacobian, options)
        second_rank = _rank_factorization!(ledger, second_jacobian, options)
        rank_stable = first_rank.rank == second_rank.rank == oracle.dimension
        final_correction = if rank_stable
            first_rank.factorization \ (-final_residual)
        else
            fill(BigFloat(Inf), oracle.dimension)
        end
        return _StageResult(
            precision_bits,
            BigFloat[x...],
            final_target,
            BigFloat(norm(final_residual, Inf)),
            BigFloat[final_correction...],
            BigFloat(norm(final_correction, Inf)),
            first_rank.rank,
            BigFloat(first_rank.condition_estimate),
            rank_stable,
            converged,
            reason,
        )
    end
end

function _semantic_replay!(ledger, input, endpoint, precision_bits, options)
    oracle = input.oracle
    if oracle.capability == :C0
        coordinates = Float64[endpoint...]
        residual = Float64.(_evaluate_residual!(ledger, oracle, coordinates, 53))
        target = Float64(_evaluate_target!(ledger, oracle, coordinates, 53))
        bound = BigFloat(norm(residual, Inf))
        return SemanticReplayEvidence(
            53,
            Tuple(coordinates),
            bound,
            BigFloat(target),
            bound <= options.semantic_residual_tolerance,
        )
    end
    return setprecision(BigFloat, precision_bits) do
        coordinates = BigFloat[BigFloat(value) for value in endpoint]
        residual = BigFloat.(_evaluate_residual!(ledger, oracle, coordinates, precision_bits))
        target = BigFloat(_evaluate_target!(ledger, oracle, coordinates, precision_bits))
        bound = BigFloat(norm(residual, Inf))
        SemanticReplayEvidence(
            precision_bits,
            Tuple(coordinates),
            bound,
            target,
            bound <= BigFloat(options.semantic_residual_tolerance),
        )
    end
end

function _required_precision_bits(condition, options)
    isfinite(condition) || return typemax(Int)
    target_bits = ceil(Int, -log2(options.target_error_goal))
    condition_bits = ceil(Int, log2(max(1.0, Float64(condition))))
    return target_bits + condition_bits + options.required_precision_guard_bits
end

function _confirmation_direction(dimension::Int, index::Int)
    direction = Float64[
        sin(17 * index + 13 * coordinate) + cos(11 * index - 7 * coordinate) for
        coordinate in 1:dimension
    ]
    magnitude = norm(direction)
    magnitude > 0 || (direction[mod1(index, dimension)] = 1.0; magnitude = 1.0)
    return direction ./ magnitude
end

function run_s0(
    input::CandidateInput;
    options::ExperimentOptions=ExperimentOptions(),
    clock_ns=time_ns,
)
    ledger = _work_ledger(options, clock_ns)
    semantic = nothing
    reason = "point semantic replay is diagnostic-only"
    try
        semantic = _semantic_replay!(
            ledger,
            input,
            input.endpoint,
            options.semantic_precision_bits,
            options,
        )
    catch error
        error isa ExperimentBudgetExceeded || rethrow()
        reason = string(error.reason)
    end
    return ExperimentalOutcome(
        "S0-POINT-REPLAY",
        "semantic-replay-only",
        :diagnostic_only,
        reason,
        semantic,
        nothing,
        _work_snapshot(ledger),
    )
end

function run_s1(
    input::CandidateInput;
    options::ExperimentOptions=ExperimentOptions(),
    derivative_mode::Symbol=:dense,
    clock_ns=time_ns,
)
    variant = derivative_mode === :dense ? "S1-AP-LMQR" : "SLB-ANALYTIC-DERIVATIVES"
    route = derivative_mode === :dense ? "adaptive-precision-dense-lmqr" :
            "adaptive-precision-analytic-control"
    ledger = _work_ledger(options, clock_ns)
    if input.oracle.capability == :C0
        return ExperimentalOutcome(
            variant,
            route,
            :unknown,
            "C2 capability unavailable",
            nothing,
            nothing,
            _work_snapshot(ledger),
        )
    end
    derivative_mode in (:dense, :analytic) || throw(ArgumentError("unsupported derivative mode"))

    stages = _StageResult[]
    selected = nothing
    start = input.endpoint
    reason = "precision ladder exhausted"
    try
        for precision_bits in options.precision_ladder
            stage = _refine_stage!(
                ledger,
                input,
                start,
                precision_bits,
                options,
                derivative_mode,
            )
            push!(stages, stage)
            if !stage.converged || !stage.rank_stable
                reason = stage.reason
                break
            end
            if length(stages) >= 2
                previous = stages[end - 1]
                configuration_disagreement = norm(stage.endpoint .- previous.endpoint, Inf)
                target_disagreement = abs(stage.target - previous.target)
                enough_bits = precision_bits >= _required_precision_bits(
                    stage.condition_estimate,
                    options,
                )
                if enough_bits &&
                   configuration_disagreement <= options.configuration_error_goal /
                                                 options.error_reserve_multiplier &&
                   target_disagreement <= options.target_error_goal /
                                          options.error_reserve_multiplier
                    selected = stage
                    break
                end
            end
            start = stage.endpoint
        end

        selected === nothing && return ExperimentalOutcome(
            variant,
            route,
            :unknown,
            reason,
            isempty(stages) ? nothing : _semantic_replay!(
                ledger,
                input,
                stages[end].endpoint,
                stages[end].precision_bits,
                options,
            ),
            nothing,
            _work_snapshot(ledger),
        )

        final_stage = selected::_StageResult
        confirmations = _StageResult[]
        for index in 1:options.independent_confirmation_count
            direction = _confirmation_direction(input.oracle.dimension, index)
            confirmation_start = input.endpoint .+
                                 options.confirmation_perturbation_radius .* direction
            confirmation = _refine_stage!(
                ledger,
                input,
                confirmation_start,
                final_stage.precision_bits,
                options,
                derivative_mode,
            )
            push!(confirmations, confirmation)
        end

        confirmations_ok = all(
            confirmation -> confirmation.converged && confirmation.rank_stable,
            confirmations,
        )
        semantic = _semantic_replay!(
            ledger,
            input,
            final_stage.endpoint,
            final_stage.precision_bits,
            options,
        )
        previous = stages[end - 1]
        configuration_disagreement = norm(final_stage.endpoint .- previous.endpoint, Inf)
        confirmation_configuration_disagreement = maximum(
            norm(confirmation.endpoint .- final_stage.endpoint, Inf) for
            confirmation in confirmations
        )
        confirmation_target_disagreement = maximum(
            abs(confirmation.target - final_stage.target) for confirmation in confirmations
        )
        target_gradient = setprecision(BigFloat, final_stage.precision_bits) do
            _target_gradient!(
                ledger,
                input.oracle,
                final_stage.endpoint,
                final_stage.precision_bits,
                options,
            )
        end
        target_correction = abs(dot(target_gradient, final_stage.correction))
        configuration_roundoff = eps(BigFloat) * max(
            one(BigFloat),
            norm(final_stage.endpoint, Inf),
        )
        target_roundoff = eps(BigFloat) * max(one(BigFloat), abs(final_stage.target))
        configuration_error = BigFloat(options.error_reserve_multiplier) * maximum((
            final_stage.correction_norm,
            configuration_disagreement,
            confirmation_configuration_disagreement,
            configuration_roundoff,
        ))
        target_error = BigFloat(options.error_reserve_multiplier) * maximum((
            target_correction,
            abs(final_stage.target - previous.target),
            confirmation_target_disagreement,
            target_roundoff,
        ))
        evidence = NumericalRootEvidence(
            derivative_mode === :dense ? "adaptive_precision_dense_lmqr_v1" :
            "adaptive_precision_analytic_control_v1",
            final_stage.precision_bits,
            Tuple(stage.precision_bits for stage in stages),
            Tuple(final_stage.endpoint),
            final_stage.target,
            final_stage.residual_linf,
            final_stage.rank,
            final_stage.condition_estimate,
            configuration_error,
            target_error,
            Tuple(Tuple(confirmation.endpoint) for confirmation in confirmations),
            Tuple(confirmation.target for confirmation in confirmations),
            final_stage.rank_stable,
        )
        promotable = confirmations_ok && semantic.accepted &&
                     final_stage.residual_linf <= _residual_goal(BigFloat) &&
                     configuration_error <= options.configuration_error_goal &&
                     target_error <= options.target_error_goal
        return ExperimentalOutcome(
            variant,
            route,
            promotable ? :promoted : :unknown,
            promotable ? "numerical root evidence accepted" :
            "numerical root evidence gate failed",
            semantic,
            evidence,
            _work_snapshot(ledger),
        )
    catch error
        error isa ExperimentBudgetExceeded || rethrow()
        return ExperimentalOutcome(
            variant,
            route,
            :unknown,
            string(error.reason),
            nothing,
            nothing,
            _work_snapshot(ledger),
        )
    end
end

struct _SubsetStageResult
    precision_bits::Int
    endpoint::Vector{BigFloat}
    target::BigFloat
    residual_linf::BigFloat
    correction::Vector{BigFloat}
    correction_norm::BigFloat
    rank::Int
    condition_estimate::BigFloat
    active_columns::Tuple{Vararg{Int}}
    jacobian::Matrix{BigFloat}
    rank_stable::Bool
    converged::Bool
    reason::String
end

function _active_columns(rank_factor::_RankFactorization, rank::Int)
    permutation = rank_factor.factorization.p
    return Tuple(Int(permutation[index]) for index in 1:rank)
end

function _subset_correction!(ledger, jacobian, residual, active_columns, options)
    subset = jacobian[:, collect(active_columns)]
    subset_factor = _rank_factorization!(ledger, subset, options)
    subset_factor.rank == length(active_columns) || return nothing, BigFloat(Inf)
    active_step = subset_factor.factorization \ (-residual)
    correction = zeros(BigFloat, size(jacobian, 2))
    correction[collect(active_columns)] .= active_step
    return correction, BigFloat(subset_factor.condition_estimate)
end

function _refine_subset_stage!(
    ledger,
    input::CandidateInput,
    start,
    precision_bits::Int,
    options::ExperimentOptions,
    derivative_mode::Symbol,
)
    oracle = input.oracle
    return setprecision(BigFloat, precision_bits) do
        x = BigFloat[BigFloat(value) for value in start]
        residual = BigFloat.(_evaluate_residual!(ledger, oracle, x, precision_bits))
        last_correction = fill(BigFloat(Inf), oracle.dimension)
        last_rank = 0
        last_condition = BigFloat(Inf)
        last_active = ()
        converged = false
        reason = "maximum_iterations"

        while true
            _charge_iteration!(ledger)
            jacobian = BigFloat.(_jacobian!(
                ledger,
                oracle,
                x,
                precision_bits,
                options,
                derivative_mode,
            ))
            rank_factor = _rank_factorization!(ledger, jacobian, options)
            last_rank = rank_factor.rank
            if !(0 < last_rank < oracle.dimension)
                reason = "rank_not_subset"
                break
            end
            last_active = _active_columns(rank_factor, last_rank)
            correction, condition = _subset_correction!(
                ledger,
                jacobian,
                residual,
                last_active,
                options,
            )
            correction === nothing && begin
                reason = "subset_factorization_failed"
                break
            end
            last_correction = correction
            last_condition = condition
            correction_norm = norm(correction, Inf)
            residual_norm = norm(residual, Inf)
            if residual_norm <= _residual_goal(BigFloat) &&
               correction_norm <= _correction_goal(BigFloat, options)
                converged = true
                reason = "converged"
                break
            end
            trial_x, trial_residual, accepted =
                _line_search!(ledger, oracle, x, residual, correction, precision_bits)
            if !accepted
                reason = "no_progress"
                break
            end
            x = BigFloat[trial_x...]
            residual = BigFloat[trial_residual...]
        end

        final_residual = BigFloat.(_evaluate_residual!(ledger, oracle, x, precision_bits))
        final_target = BigFloat(_evaluate_target!(ledger, oracle, x, precision_bits))
        first_jacobian = BigFloat.(_jacobian!(
            ledger,
            oracle,
            x,
            precision_bits,
            options,
            derivative_mode;
            radius_multiplier=1,
        ))
        second_jacobian = BigFloat.(_jacobian!(
            ledger,
            oracle,
            x,
            precision_bits,
            options,
            derivative_mode;
            radius_multiplier=0.5,
        ))
        first_rank = _rank_factorization!(ledger, first_jacobian, options)
        second_rank = _rank_factorization!(ledger, second_jacobian, options)
        first_active = 0 < first_rank.rank < oracle.dimension ?
                       _active_columns(first_rank, first_rank.rank) : ()
        second_active = 0 < second_rank.rank < oracle.dimension ?
                        _active_columns(second_rank, second_rank.rank) : ()
        rank_stable = first_rank.rank == second_rank.rank &&
                      0 < first_rank.rank < oracle.dimension &&
                      first_active == second_active
        final_correction, final_condition = rank_stable ?
            _subset_correction!(
                ledger,
                first_jacobian,
                final_residual,
                first_active,
                options,
            ) : (nothing, BigFloat(Inf))
        frozen_correction = final_correction === nothing ?
                            fill(BigFloat(Inf), oracle.dimension) : final_correction
        return _SubsetStageResult(
            precision_bits,
            BigFloat[x...],
            final_target,
            BigFloat(norm(final_residual, Inf)),
            BigFloat[frozen_correction...],
            BigFloat(norm(frozen_correction, Inf)),
            first_rank.rank,
            BigFloat(final_condition),
            first_active,
            first_jacobian,
            rank_stable,
            converged,
            reason,
        )
    end
end

function _nullspace_target_sensitivity!(
    ledger,
    stage::_SubsetStageResult,
    target_gradient,
    options,
)
    active = collect(stage.active_columns)
    inactive = setdiff(collect(1:size(stage.jacobian, 2)), active)
    isempty(inactive) && return BigFloat(Inf)
    subset_factor = _rank_factorization!(ledger, stage.jacobian[:, active], options)
    subset_factor.rank == length(active) || return BigFloat(Inf)
    sensitivities = BigFloat[]
    for column in inactive
        active_coefficients = subset_factor.factorization \ (-stage.jacobian[:, column])
        direction = zeros(BigFloat, size(stage.jacobian, 2))
        direction[active] .= active_coefficients
        direction[column] = 1
        push!(
            sensitivities,
            abs(dot(target_gradient, direction)) / max(one(BigFloat), norm(direction)),
        )
    end
    return maximum(sensitivities)
end

function run_s2(
    input::CandidateInput;
    options::ExperimentOptions=ExperimentOptions(),
    derivative_mode::Symbol=:dense,
    clock_ns=time_ns,
)
    variant = derivative_mode === :dense ? "S2-AP-CPQR-SUBSET" :
              "S2-ANALYTIC-SUBSET-CONTROL"
    route = derivative_mode === :dense ? "adaptive-precision-cpqr-subset" :
            "analytic-cpqr-subset-control"
    ledger = _work_ledger(options, clock_ns)
    if input.oracle.capability == :C0
        return ExperimentalOutcome(
            variant,
            route,
            :unknown,
            "C2 capability unavailable",
            nothing,
            nothing,
            _work_snapshot(ledger),
        )
    end
    derivative_mode in (:dense, :analytic) || throw(ArgumentError("unsupported derivative mode"))
    stages = _SubsetStageResult[]
    selected = nothing
    start = input.endpoint
    reason = "precision ladder exhausted"
    try
        for precision_bits in options.precision_ladder
            stage = _refine_subset_stage!(
                ledger,
                input,
                start,
                precision_bits,
                options,
                derivative_mode,
            )
            push!(stages, stage)
            if !stage.converged || !stage.rank_stable
                reason = stage.reason
                break
            end
            if length(stages) >= 2
                previous = stages[end - 1]
                target_disagreement = abs(stage.target - previous.target)
                active_disagreement = isempty(stage.active_columns) ? BigFloat(Inf) : maximum(
                    abs(stage.endpoint[index] - previous.endpoint[index]) for
                    index in stage.active_columns
                )
                enough_bits = precision_bits >= _required_precision_bits(
                    stage.condition_estimate,
                    options,
                )
                if enough_bits && stage.active_columns == previous.active_columns &&
                   active_disagreement <= options.configuration_error_goal /
                                          options.error_reserve_multiplier &&
                   target_disagreement <= options.target_error_goal /
                                          options.error_reserve_multiplier
                    selected = stage
                    break
                end
            end
            start = stage.endpoint
        end
        selected === nothing && return ExperimentalOutcome(
            variant,
            route,
            :unknown,
            reason,
            isempty(stages) ? nothing : _semantic_replay!(
                ledger,
                input,
                stages[end].endpoint,
                stages[end].precision_bits,
                options,
            ),
            nothing,
            _work_snapshot(ledger),
        )

        final_stage = selected::_SubsetStageResult
        confirmations = _SubsetStageResult[]
        for index in 1:options.independent_confirmation_count
            direction = _confirmation_direction(input.oracle.dimension, index)
            confirmation_start = input.endpoint .+
                                 options.confirmation_perturbation_radius .* direction
            push!(
                confirmations,
                _refine_subset_stage!(
                    ledger,
                    input,
                    confirmation_start,
                    final_stage.precision_bits,
                    options,
                    derivative_mode,
                ),
            )
        end
        confirmations_ok = all(
            confirmation -> confirmation.converged && confirmation.rank_stable &&
                            confirmation.rank == final_stage.rank,
            confirmations,
        )
        semantic = _semantic_replay!(
            ledger,
            input,
            final_stage.endpoint,
            final_stage.precision_bits,
            options,
        )
        target_gradient = setprecision(BigFloat, final_stage.precision_bits) do
            _target_gradient!(
                ledger,
                input.oracle,
                final_stage.endpoint,
                final_stage.precision_bits,
                options,
            )
        end
        nullspace_sensitivity = _nullspace_target_sensitivity!(
            ledger,
            final_stage,
            target_gradient,
            options,
        )
        previous = stages[end - 1]
        active_disagreement = maximum(
            abs(final_stage.endpoint[index] - previous.endpoint[index]) for
            index in final_stage.active_columns
        )
        confirmation_target_disagreement = maximum(
            abs(confirmation.target - final_stage.target) for confirmation in confirmations
        )
        active_error = BigFloat(options.error_reserve_multiplier) * maximum((
            final_stage.correction_norm,
            active_disagreement,
            eps(BigFloat),
        ))
        target_error = BigFloat(options.error_reserve_multiplier) * maximum((
            abs(final_stage.target - previous.target),
            confirmation_target_disagreement,
            nullspace_sensitivity * BigFloat(options.confirmation_perturbation_radius),
            eps(BigFloat) * max(one(BigFloat), abs(final_stage.target)),
        ))
        evidence = NumericalManifoldRootEvidence(
            derivative_mode === :dense ? "adaptive_precision_cpqr_subset_v1" :
            "analytic_cpqr_subset_control_v1",
            final_stage.precision_bits,
            Tuple(stage.precision_bits for stage in stages),
            Tuple(final_stage.endpoint),
            final_stage.target,
            final_stage.residual_linf,
            final_stage.rank,
            final_stage.condition_estimate,
            final_stage.active_columns,
            active_error,
            target_error,
            nullspace_sensitivity,
            Tuple(Tuple(confirmation.endpoint) for confirmation in confirmations),
            Tuple(confirmation.target for confirmation in confirmations),
            final_stage.rank_stable,
        )
        promotable = confirmations_ok && semantic.accepted &&
                     final_stage.residual_linf <= _residual_goal(BigFloat) &&
                     active_error <= options.configuration_error_goal &&
                     target_error <= options.target_error_goal &&
                     nullspace_sensitivity <= options.target_error_goal
        return ExperimentalOutcome(
            variant,
            route,
            promotable ? :promoted : :unknown,
            promotable ? "target-constant rank-deficient root evidence accepted" :
            "rank-deficient root evidence gate failed",
            semantic,
            evidence,
            _work_snapshot(ledger),
        )
    catch error
        error isa ExperimentBudgetExceeded || rethrow()
        return ExperimentalOutcome(
            variant,
            route,
            :unknown,
            string(error.reason),
            nothing,
            nothing,
            _work_snapshot(ledger),
        )
    end
end

struct _BroydenStageResult
    precision_bits::Int
    endpoint::Vector{BigFloat}
    target::BigFloat
    residual_linf::BigFloat
    last_step_norm::BigFloat
    converged::Bool
    reason::String
    residual_trace::Tuple
    contraction_ratios::Tuple
    secant_updates::Int
    linear_trace_passed::Bool
end

function _s3_charge_iteration!(ledger::_WorkLedger, local_iteration::Int)
    local_iteration <= ledger.options.maximum_iterations || throw(
        AssertionError("trajectory index exceeded the endpoint-wide iteration cap"),
    )
    return _charge_iteration!(ledger)
end

function _s3_step_goal(::Type{T}, options::ExperimentOptions) where {T<:AbstractFloat}
    return min(T(options.configuration_error_goal), T(options.target_error_goal)) /
           (T(4) * T(options.error_reserve_multiplier))
end

function _s3_residual_goal(::Type{T}, options::ExperimentOptions) where {T<:AbstractFloat}
    return T(options.semantic_residual_tolerance) /
           (T(4) * T(options.error_reserve_multiplier))
end

function _s3_linear_trace_gate(ratios)
    finite = BigFloat[value for value in ratios if isfinite(value) && value > 0]
    length(finite) >= 4 || return false
    tail = finite[max(1, end - 7):end]
    all(value -> value < BigFloat("0.999"), tail) || return false
    ordered = sort(copy(tail))
    middle = length(ordered) ÷ 2
    median = isodd(length(ordered)) ? ordered[middle + 1] :
             (ordered[middle] + ordered[middle + 1]) / 2
    return BigFloat("0.05") <= median <= BigFloat("0.99")
end

function _s3_candidate_route!(ledger, input::CandidateInput, options::ExperimentOptions)
    oracle = input.oracle
    signatures = NamedTuple[]
    ranks = Int[]
    conditions = BigFloat[]
    residuals = BigFloat[]
    for precision_bits in (128, 256)
        setprecision(BigFloat, precision_bits) do
            endpoint = BigFloat[BigFloat(value) for value in input.endpoint]
            residual = BigFloat.(_evaluate_residual!(
                ledger,
                oracle,
                endpoint,
                precision_bits,
            ))
            push!(residuals, BigFloat(norm(residual, Inf)))
            for radius_multiplier in (1.0, 0.5)
                jacobian = BigFloat.(_dense_jacobian!(
                    ledger,
                    oracle,
                    endpoint,
                    precision_bits,
                    options;
                    radius_multiplier,
                ))
                factor = _rank_factorization!(ledger, jacobian, options)
                push!(ranks, factor.rank)
                push!(conditions, BigFloat(factor.condition_estimate))
                push!(
                    signatures,
                    (
                        precision_bits=precision_bits,
                        radius_multiplier=radius_multiplier,
                        rank=factor.rank,
                        nullity=oracle.dimension - factor.rank,
                        condition_estimate=string(factor.condition_estimate),
                    ),
                )
            end
        end
    end
    residual_ok = all(value -> value <= _residual_goal(BigFloat), residuals)
    stable_rank = !isempty(ranks) && all(==(first(ranks)), ranks)
    rank = stable_rank ? first(ranks) : -1
    singular = stable_rank && 0 < rank < oracle.dimension
    condition = isempty(conditions) ? BigFloat(Inf) : maximum(conditions)
    accepted = residual_ok && singular
    reason = !residual_ok ? "primary residual above strict numerical route goal" :
             !stable_rank ? "rank unstable across precision or radius" :
             !singular ? "stable endpoint is not rank-deficient" :
             "stable singular route accepted"
    return (
        accepted=accepted,
        reason=reason,
        rank=rank,
        condition=condition,
        signatures=Tuple(signatures),
    )
end

function _s3_control_route!(ledger, input::CandidateInput, options::ExperimentOptions)
    oracle = input.oracle
    signatures = NamedTuple[]
    ranks = Int[]
    conditions = BigFloat[]
    residuals = BigFloat[]
    for precision_bits in (128, 256)
        setprecision(BigFloat, precision_bits) do
            endpoint = BigFloat[BigFloat(value) for value in input.endpoint]
            residual = BigFloat.(_evaluate_residual!(
                ledger,
                oracle,
                endpoint,
                precision_bits,
            ))
            push!(residuals, BigFloat(norm(residual, Inf)))
            jacobian = BigFloat.(_evaluate_analytic_jacobian!(
                ledger,
                oracle,
                endpoint,
                precision_bits,
            ))
            factor = _rank_factorization!(ledger, jacobian, options)
            push!(ranks, factor.rank)
            push!(conditions, BigFloat(factor.condition_estimate))
            push!(
                signatures,
                (
                    precision_bits=precision_bits,
                    radius_multiplier="analytic",
                    rank=factor.rank,
                    nullity=oracle.dimension - factor.rank,
                    condition_estimate=string(factor.condition_estimate),
                ),
            )
        end
    end
    residual_ok = all(value -> value <= _residual_goal(BigFloat), residuals)
    stable_rank = !isempty(ranks) && all(==(first(ranks)), ranks)
    rank = stable_rank ? first(ranks) : -1
    singular = stable_rank && 0 < rank < oracle.dimension
    condition = isempty(conditions) ? BigFloat(Inf) : maximum(conditions)
    accepted = residual_ok && singular
    reason = !residual_ok ? "primary residual above strict numerical route goal" :
             !stable_rank ? "analytic rank unstable across precision" :
             !singular ? "stable endpoint is not analytically rank-deficient" :
             "stable analytic singular route accepted"
    return (
        accepted=accepted,
        reason=reason,
        rank=rank,
        condition=condition,
        signatures=Tuple(signatures),
    )
end

function _s3_direct_broyden_stage!(
    ledger,
    input::CandidateInput,
    start,
    precision_bits::Int,
    options::ExperimentOptions,
)
    oracle = input.oracle
    return setprecision(BigFloat, precision_bits) do
        x = BigFloat[BigFloat(value) for value in start]
        residual = BigFloat.(_evaluate_residual!(ledger, oracle, x, precision_bits))
        trace = BigFloat[BigFloat(norm(residual, Inf))]
        last_step_norm = zero(BigFloat)
        converged = trace[end] <= _residual_goal(BigFloat)
        reason = converged ? "primary_residual_converged" : "maximum_iterations"
        updates = 0
        if !converged
            broyden_matrix = BigFloat.(_dense_jacobian!(
                ledger,
                oracle,
                x,
                precision_bits,
                options,
            ))
            for local_iteration in 1:options.maximum_iterations
                _s3_charge_iteration!(ledger, local_iteration)
                factor = _rank_factorization!(ledger, broyden_matrix, options)
                if factor.rank != oracle.dimension
                    reason = "secant_matrix_rank_deficient"
                    break
                end
                step = BigFloat[factor.factorization \ (-residual)...]
                all(isfinite, step) || begin
                    reason = "nonfinite_secant_step"
                    break
                end
                trial_x, trial_residual, accepted =
                    _line_search!(ledger, oracle, x, residual, step, precision_bits)
                if !accepted
                    reason = "secant_no_progress"
                    break
                end
                displacement = BigFloat[trial_x .- x...]
                change = BigFloat[trial_residual .- residual...]
                denominator = dot(displacement, displacement)
                threshold = eps(BigFloat) * max(one(BigFloat), norm(displacement)^2)
                if !(isfinite(denominator) && denominator > threshold)
                    reason = "secant_update_degenerate"
                    break
                end
                broyden_matrix .+=
                    ((change .- broyden_matrix * displacement) * transpose(displacement)) ./
                    denominator
                updates += 1
                x = BigFloat[trial_x...]
                residual = BigFloat[trial_residual...]
                last_step_norm = BigFloat(norm(displacement, Inf))
                push!(trace, BigFloat(norm(residual, Inf)))
                if trace[end] <= _s3_residual_goal(BigFloat, options) &&
                   last_step_norm <= _s3_step_goal(BigFloat, options)
                    converged = true
                    reason = "converged"
                    break
                end
                if updates % 4 == 0
                    broyden_matrix = BigFloat.(_dense_jacobian!(
                        ledger,
                        oracle,
                        x,
                        precision_bits,
                        options,
                    ))
                end
            end
        end
        ratios = BigFloat[
            trace[index - 1] > 0 ? trace[index] / trace[index - 1] : BigFloat(Inf) for
            index in 2:length(trace)
        ]
        final_residual = BigFloat.(_evaluate_residual!(ledger, oracle, x, precision_bits))
        final_target = BigFloat(_evaluate_target!(ledger, oracle, x, precision_bits))
        return _BroydenStageResult(
            precision_bits,
            BigFloat[x...],
            final_target,
            BigFloat(norm(final_residual, Inf)),
            last_step_norm,
            converged,
            reason,
            Tuple(trace),
            Tuple(ratios),
            updates,
            _s3_linear_trace_gate(ratios),
        )
    end
end

function _s3_control_backtrack!(ledger, oracle, x, residual, step, precision_bits)
    current = norm(residual, 2)
    scale = one(eltype(x))
    for _ in 1:8
        proposal = x .+ scale .* step
        proposal_residual = BigFloat.(_evaluate_residual!(
            ledger,
            oracle,
            proposal,
            precision_bits,
        ))
        if norm(proposal_residual, 2) < current
            return BigFloat[proposal...], proposal_residual, true
        end
        scale /= 2
    end
    return BigFloat[x...], BigFloat[residual...], false
end

function _s3_inverse_analytic_secant_stage!(
    ledger,
    input::CandidateInput,
    start,
    precision_bits::Int,
    options::ExperimentOptions,
)
    oracle = input.oracle
    return setprecision(BigFloat, precision_bits) do
        x = BigFloat[BigFloat(value) for value in start]
        residual = BigFloat.(_evaluate_residual!(ledger, oracle, x, precision_bits))
        trace = BigFloat[BigFloat(norm(residual, Inf))]
        last_step_norm = zero(BigFloat)
        converged = trace[end] <= _residual_goal(BigFloat)
        reason = converged ? "primary_residual_converged" : "maximum_iterations"
        updates = 0
        inverse_secant = nothing
        if !converged
            analytic = BigFloat.(_evaluate_analytic_jacobian!(
                ledger,
                oracle,
                x,
                precision_bits,
            ))
            factor = _rank_factorization!(ledger, analytic, options)
            if factor.rank == oracle.dimension
                inverse_secant = Matrix{BigFloat}(factor.factorization \ Matrix{BigFloat}(
                    I,
                    oracle.dimension,
                    oracle.dimension,
                ))
            else
                reason = "analytic_secant_seed_rank_deficient"
            end
        end
        if inverse_secant !== nothing
            for local_iteration in 1:options.maximum_iterations
                _s3_charge_iteration!(ledger, local_iteration)
                step = BigFloat[-(inverse_secant * residual)...]
                all(isfinite, step) || begin
                    reason = "nonfinite_inverse_secant_step"
                    break
                end
                trial_x, trial_residual, accepted = _s3_control_backtrack!(
                    ledger,
                    oracle,
                    x,
                    residual,
                    step,
                    precision_bits,
                )
                if !accepted
                    reason = "inverse_secant_no_progress"
                    break
                end
                displacement = BigFloat[trial_x .- x...]
                change = BigFloat[trial_residual .- residual...]
                mapped_change = inverse_secant * change
                denominator = dot(displacement, mapped_change)
                threshold = eps(BigFloat) * max(
                    one(BigFloat),
                    norm(displacement) * norm(mapped_change),
                )
                if !(isfinite(denominator) && abs(denominator) > threshold)
                    reason = "inverse_secant_update_degenerate"
                    break
                end
                inverse_secant .+=
                    ((displacement .- mapped_change) *
                     (transpose(displacement) * inverse_secant)) ./ denominator
                updates += 1
                x = trial_x
                residual = trial_residual
                last_step_norm = BigFloat(norm(displacement, Inf))
                push!(trace, BigFloat(norm(residual, Inf)))
                if trace[end] <= _s3_residual_goal(BigFloat, options) &&
                   last_step_norm <= _s3_step_goal(BigFloat, options)
                    converged = true
                    reason = "converged"
                    break
                end
                if updates % 4 == 0
                    analytic = BigFloat.(_evaluate_analytic_jacobian!(
                        ledger,
                        oracle,
                        x,
                        precision_bits,
                    ))
                    factor = _rank_factorization!(ledger, analytic, options)
                    if factor.rank != oracle.dimension
                        reason = "analytic_restart_rank_deficient"
                        break
                    end
                    inverse_secant = Matrix{BigFloat}(
                        factor.factorization \ Matrix{BigFloat}(
                            I,
                            oracle.dimension,
                            oracle.dimension,
                        ),
                    )
                end
            end
        end
        ratios = BigFloat[
            trace[index - 1] > 0 ? trace[index] / trace[index - 1] : BigFloat(Inf) for
            index in 2:length(trace)
        ]
        final_residual = BigFloat.(_evaluate_residual!(ledger, oracle, x, precision_bits))
        final_target = BigFloat(_evaluate_target!(ledger, oracle, x, precision_bits))
        return _BroydenStageResult(
            precision_bits,
            BigFloat[x...],
            final_target,
            BigFloat(norm(final_residual, Inf)),
            last_step_norm,
            converged,
            reason,
            Tuple(trace),
            Tuple(ratios),
            updates,
            _s3_linear_trace_gate(ratios),
        )
    end
end

function _s3_finalize_outcome!(
    ledger,
    input::CandidateInput,
    options::ExperimentOptions,
    variant::String,
    route_name::String,
    route,
    primary_stages,
    confirmations,
    method::String,
)
    final_stage = primary_stages[end]
    semantic = _semantic_replay!(
        ledger,
        input,
        final_stage.endpoint,
        final_stage.precision_bits,
        options,
    )
    confirmations_converged = all(stage -> stage.converged, confirmations)
    linear_trace_passed = confirmations_converged &&
                          all(stage -> stage.linear_trace_passed, confirmations)
    if !confirmations_converged || !linear_trace_passed
        reason = !confirmations_converged ? "independent confirmation failed" :
                 "linear convergence trace gate failed"
        return ExperimentalOutcome(
            variant,
            route_name,
            :unknown,
            reason,
            semantic,
            nothing,
            _work_snapshot(ledger),
        )
    end
    confirmation_semantics = SemanticReplayEvidence[
        _semantic_replay!(
            ledger,
            input,
            stage.endpoint,
            stage.precision_bits,
            options,
        ) for stage in confirmations
    ]
    canonical_confirmations_passed = all(evidence -> evidence.accepted, confirmation_semantics)
    previous = primary_stages[end - 1]
    stage_disagreement = norm(final_stage.endpoint .- previous.endpoint, Inf)
    confirmation_disagreement = maximum(
        norm(stage.endpoint .- final_stage.endpoint, Inf) for stage in confirmations
    )
    confirmation_target_disagreement = maximum(
        abs(stage.target - final_stage.target) for stage in confirmations
    )
    precision_target_disagreement = abs(final_stage.target - previous.target)
    target_gradient = setprecision(BigFloat, final_stage.precision_bits) do
        _target_gradient!(
            ledger,
            input.oracle,
            final_stage.endpoint,
            final_stage.precision_bits,
            options,
        )
    end
    configuration_roundoff = setprecision(BigFloat, final_stage.precision_bits) do
        eps(BigFloat) * max(one(BigFloat), norm(final_stage.endpoint, Inf))
    end
    target_roundoff = setprecision(BigFloat, final_stage.precision_bits) do
        eps(BigFloat) * max(one(BigFloat), abs(final_stage.target))
    end
    raw_configuration_error = maximum((
        final_stage.last_step_norm,
        stage_disagreement,
        confirmation_disagreement,
        configuration_roundoff,
    ))
    configuration_error = BigFloat(options.error_reserve_multiplier) *
                          raw_configuration_error
    target_error = BigFloat(options.error_reserve_multiplier) * maximum((
        precision_target_disagreement,
        confirmation_target_disagreement,
        norm(target_gradient, 1) * raw_configuration_error,
        target_roundoff,
    ))
    ratios = Tuple(
        ratio for stage in confirmations for ratio in stage.contraction_ratios
    )
    evidence = NumericalSingularRootEvidence(
        method,
        final_stage.precision_bits,
        Tuple(stage.precision_bits for stage in primary_stages),
        Tuple(final_stage.endpoint),
        final_stage.target,
        final_stage.residual_linf,
        route.rank,
        input.oracle.dimension - route.rank,
        route.condition,
        configuration_error,
        target_error,
        Tuple(Tuple(stage.endpoint) for stage in confirmations),
        Tuple(stage.target for stage in confirmations),
        Tuple(stage.residual_linf for stage in confirmations),
        route.signatures,
        ratios,
        sum(stage.secant_updates for stage in confirmations; init=0),
        true,
        confirmations_converged,
        canonical_confirmations_passed,
        linear_trace_passed,
    )
    promotable = semantic.accepted && canonical_confirmations_passed &&
                 final_stage.residual_linf <= _residual_goal(BigFloat) &&
                 configuration_error <= options.configuration_error_goal &&
                 target_error <= options.target_error_goal
    return ExperimentalOutcome(
        variant,
        route_name,
        promotable ? :promoted : :unknown,
        promotable ? "singular numerical root evidence accepted" :
        "singular numerical root evidence gate failed",
        semantic,
        evidence,
        _work_snapshot(ledger),
    )
end

function run_s3(
    input::CandidateInput;
    options::ExperimentOptions=ExperimentOptions(),
    clock_ns=time_ns,
)
    variant = "S3-AP-BROYDEN"
    route_name = "stable-singular-multiprecision-good-broyden"
    ledger = _work_ledger(options, clock_ns)
    if input.oracle.capability == :C0
        return ExperimentalOutcome(
            variant,
            route_name,
            :unknown,
            "C2 capability unavailable",
            nothing,
            nothing,
            _work_snapshot(ledger),
        )
    end
    if input.oracle.dimension != input.oracle.residual_dimension
        return ExperimentalOutcome(
            variant,
            route_name,
            :unknown,
            "good-Broyden route requires a square system",
            nothing,
            nothing,
            _work_snapshot(ledger),
        )
    end
    try
        route = _s3_candidate_route!(ledger, input, options)
        route.accepted || return ExperimentalOutcome(
            variant,
            route_name,
            :unknown,
            route.reason,
            nothing,
            nothing,
            _work_snapshot(ledger),
        )
        primary_stages = _BroydenStageResult[
            _s3_direct_broyden_stage!(ledger, input, input.endpoint, bits, options) for
            bits in (128, 256)
        ]
        all(stage -> stage.converged, primary_stages) || return ExperimentalOutcome(
            variant,
            route_name,
            :unknown,
            "primary precision replay failed",
            nothing,
            nothing,
            _work_snapshot(ledger),
        )
        confirmations = _BroydenStageResult[]
        for index in 1:options.independent_confirmation_count
            direction = _confirmation_direction(input.oracle.dimension, index)
            start = input.endpoint .+
                    options.confirmation_perturbation_radius .* direction
            push!(
                confirmations,
                _s3_direct_broyden_stage!(ledger, input, start, 256, options),
            )
        end
        return _s3_finalize_outcome!(
            ledger,
            input,
            options,
            variant,
            route_name,
            route,
            primary_stages,
            confirmations,
            "multiprecision_good_broyden_singular_evidence_v1",
        )
    catch error
        error isa ExperimentBudgetExceeded || rethrow()
        return ExperimentalOutcome(
            variant,
            route_name,
            :unknown,
            string(error.reason),
            nothing,
            nothing,
            _work_snapshot(ledger),
        )
    end
end

function run_s3_analytic_control(
    input::CandidateInput;
    options::ExperimentOptions=ExperimentOptions(),
    clock_ns=time_ns,
)
    variant = "S3-ANALYTIC-SECANT-CONTROL"
    route_name = "stable-singular-analytic-inverse-secant-control"
    ledger = _work_ledger(options, clock_ns)
    if input.oracle.capability == :C0 || input.oracle.analytic_jacobian === nothing
        return ExperimentalOutcome(
            variant,
            route_name,
            :unknown,
            "analytic C2 capability unavailable",
            nothing,
            nothing,
            _work_snapshot(ledger),
        )
    end
    if input.oracle.dimension != input.oracle.residual_dimension
        return ExperimentalOutcome(
            variant,
            route_name,
            :unknown,
            "analytic secant control requires a square system",
            nothing,
            nothing,
            _work_snapshot(ledger),
        )
    end
    try
        route = _s3_control_route!(ledger, input, options)
        route.accepted || return ExperimentalOutcome(
            variant,
            route_name,
            :unknown,
            route.reason,
            nothing,
            nothing,
            _work_snapshot(ledger),
        )
        primary_stages = _BroydenStageResult[
            _s3_inverse_analytic_secant_stage!(
                ledger,
                input,
                input.endpoint,
                bits,
                options,
            ) for bits in (128, 256)
        ]
        all(stage -> stage.converged, primary_stages) || return ExperimentalOutcome(
            variant,
            route_name,
            :unknown,
            "analytic primary precision replay failed",
            nothing,
            nothing,
            _work_snapshot(ledger),
        )
        confirmations = _BroydenStageResult[]
        for index in 1:options.independent_confirmation_count
            direction = _confirmation_direction(input.oracle.dimension, index)
            start = input.endpoint .+
                    options.confirmation_perturbation_radius .* direction
            push!(
                confirmations,
                _s3_inverse_analytic_secant_stage!(
                    ledger,
                    input,
                    start,
                    256,
                    options,
                ),
            )
        end
        return _s3_finalize_outcome!(
            ledger,
            input,
            options,
            variant,
            route_name,
            route,
            primary_stages,
            confirmations,
            "analytic_inverse_secant_singular_control_v1",
        )
    catch error
        error isa ExperimentBudgetExceeded || rethrow()
        return ExperimentalOutcome(
            variant,
            route_name,
            :unknown,
            string(error.reason),
            nothing,
            nothing,
            _work_snapshot(ledger),
        )
    end
end

function assess_outcome(case::GeneratedEndpoint, outcome::ExperimentalOutcome)
    promoted = outcome.status == :promoted
    if !promoted
        return GoldAssessment(
            case.input.oracle.id,
            outcome.variant,
            false,
            false,
            false,
            nothing,
            nothing,
            false,
            false,
        )
    end
    evidence = outcome.root_evidence::AbstractNumericalRootEvidence
    if case.gold.kind == :finite_manifold_target &&
       evidence isa NumericalManifoldRootEvidence
        target_error = abs(Float64(evidence.target) - (case.gold.target::Float64))
        target_covered = target_error <= Float64(evidence.target_error_estimate)
        return GoldAssessment(
            case.input.oracle.id,
            outcome.variant,
            true,
            target_covered,
            !target_covered,
            nothing,
            target_error,
            true,
            target_covered,
        )
    end
    if case.gold.kind != :isolated_root ||
       !(evidence isa Union{NumericalRootEvidence,NumericalSingularRootEvidence})
        return GoldAssessment(
            case.input.oracle.id,
            outcome.variant,
            true,
            false,
            true,
            nothing,
            nothing,
            false,
            false,
        )
    end
    gold_configuration = case.gold.configuration::Vector{Float64}
    endpoint = Float64[value for value in evidence.endpoint]
    configuration_error = norm(endpoint .- gold_configuration, Inf)
    target_error = abs(Float64(evidence.target) - (case.gold.target::Float64))
    configuration_covered = configuration_error <= Float64(evidence.configuration_error_estimate)
    target_covered = target_error <= Float64(evidence.target_error_estimate)
    success = configuration_covered && target_covered
    return GoldAssessment(
        case.input.oracle.id,
        outcome.variant,
        true,
        success,
        !success,
        configuration_error,
        target_error,
        configuration_covered,
        target_covered,
    )
end
