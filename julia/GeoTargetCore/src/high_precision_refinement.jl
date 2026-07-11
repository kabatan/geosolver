@enum HighPrecisionRefinementFailure::UInt8 begin
    HIGH_PRECISION_REFINEMENT_NONE = 0
    HIGH_PRECISION_REFINEMENT_CANCELLED = 1
    HIGH_PRECISION_REFINEMENT_DEADLINE_REACHED = 2
    HIGH_PRECISION_REFINEMENT_ORACLE_BUDGET_EXHAUSTED = 3
    HIGH_PRECISION_REFINEMENT_BASE_EVALUATION_FAILED = 4
    HIGH_PRECISION_REFINEMENT_SEMANTICS_FAILED = 5
    HIGH_PRECISION_REFINEMENT_STENCIL_UNAVAILABLE = 6
    HIGH_PRECISION_REFINEMENT_RANK_DEFICIENT = 7
    HIGH_PRECISION_REFINEMENT_LINEAR_SOLVE_FAILED = 8
    HIGH_PRECISION_REFINEMENT_NO_PROGRESS = 9
    HIGH_PRECISION_REFINEMENT_ITERATION_LIMIT = 10
    HIGH_PRECISION_REFINEMENT_RESIDUAL_GOAL_FAILED = 11
    HIGH_PRECISION_REFINEMENT_PRECISION_DOWNGRADE = 12
end

struct HighPrecisionWorkSnapshot
    precision_bits::Int
    weight::Int
    evaluations::Int
    raw_oracle_work::Int
    oracle_work::Int
end

struct HighPrecisionRootEvidence
    method::String
    precision_bits::Int
    coordinates::Tuple
    observation::OracleObservation
    residual_bound::BigFloat
    correction_bound::BigFloat
    target_error_bound::BigFloat
    numerical_rank::Int
    condition_estimate::BigFloat
    rank_stable::Bool
    iterations::Int
    work::HighPrecisionWorkSnapshot
end

struct HighPrecisionRefinementResult
    accepted::Bool
    failure::HighPrecisionRefinementFailure
    diagnostic::Union{Nothing,String}
    evidence::HighPrecisionRootEvidence

    function HighPrecisionRefinementResult(
        accepted::Bool,
        failure::HighPrecisionRefinementFailure,
        diagnostic::Union{Nothing,AbstractString},
        evidence::HighPrecisionRootEvidence,
    )
        accepted == (failure == HIGH_PRECISION_REFINEMENT_NONE) || throw(
            InvariantError(
                :high_precision_refinement_status_mismatch,
                "high-precision refinement acceptance and failure disagree",
            ),
        )
        accepted == (diagnostic === nothing) || throw(
            InvariantError(
                :high_precision_refinement_diagnostic_mismatch,
                "only failed high-precision refinements carry diagnostics",
            ),
        )
        return new(
            accepted,
            failure,
            diagnostic === nothing ? nothing : String(diagnostic),
            evidence,
        )
    end
end

mutable struct _HighPrecisionWork{F,C}
    compiled::CompiledProblem
    evaluator::F
    precision_bits::Int
    weight::Int
    deadline_ns::UInt64
    cancelled::C
    oracle_work_limit::Int
    evaluations::Int
    raw_oracle_work::Int
    oracle_work::Int
    stop_failure::HighPrecisionRefinementFailure
end

_high_precision_weight(bits::Integer) = cld(Int(bits), 53)

function _high_precision_checked_product(left::Int, right::Int)
    try
        return Base.checked_mul(left, right)
    catch error
        error isa OverflowError || rethrow()
        return typemax(Int)
    end
end

function _high_precision_saturating_add(left::Int, right::Int)
    right >= 0 || throw(InvariantError(:negative_oracle_work, "work addition is negative"))
    return right > typemax(Int) - left ? typemax(Int) : left + right
end

function _high_precision_resource_failure(
    work::_HighPrecisionWork;
    reserve_evaluation::Bool,
)
    work.cancelled() && return HIGH_PRECISION_REFINEMENT_CANCELLED
    time_ns() >= work.deadline_ns && return HIGH_PRECISION_REFINEMENT_DEADLINE_REACHED
    if reserve_evaluation
        reservation = _high_precision_checked_product(
            work.weight,
            work.compiled.logical_evaluation_cost,
        )
        reservation > work.oracle_work_limit &&
            return HIGH_PRECISION_REFINEMENT_ORACLE_BUDGET_EXHAUSTED
        work.oracle_work > work.oracle_work_limit - reservation &&
            return HIGH_PRECISION_REFINEMENT_ORACLE_BUDGET_EXHAUSTED
    end
    return HIGH_PRECISION_REFINEMENT_NONE
end

function _check_high_precision_resources!(
    work::_HighPrecisionWork;
    reserve_evaluation::Bool,
)
    work.stop_failure == HIGH_PRECISION_REFINEMENT_NONE || return false
    work.stop_failure = _high_precision_resource_failure(work; reserve_evaluation)
    return work.stop_failure == HIGH_PRECISION_REFINEMENT_NONE
end

function _high_precision_snapshot(work::_HighPrecisionWork)
    return HighPrecisionWorkSnapshot(
        work.precision_bits,
        work.weight,
        work.evaluations,
        work.raw_oracle_work,
        work.oracle_work,
    )
end

function _high_precision_evaluate!(work::_HighPrecisionWork, coordinates)
    _check_high_precision_resources!(work; reserve_evaluation=true) || return nothing
    observation = work.evaluator(coordinates)
    _check_logical_evaluation_bound(work.compiled, observation)
    work.evaluations = _high_precision_saturating_add(work.evaluations, 1)
    work.raw_oracle_work = _high_precision_saturating_add(
        work.raw_oracle_work,
        observation.evaluation_cost,
    )
    weighted = _high_precision_checked_product(work.weight, observation.evaluation_cost)
    work.oracle_work = _high_precision_saturating_add(work.oracle_work, weighted)
    _check_high_precision_resources!(work; reserve_evaluation=false)
    return observation
end

function _high_precision_node_dependencies(compiled::CompiledProblem, node::NodeId)
    for pair in compiled.sparsity.node_variables
        first(pair) == node && return last(pair)
    end
    return ()
end

function _high_precision_value_ok(value::Real, dependencies, bits::Int)
    isempty(dependencies) && return true
    value isa Union{Integer,Rational} && return true
    value isa AbstractFloat || return false
    available = try
        precision(value)
    catch
        return false
    end
    return available >= bits
end

function _high_precision_observation_precision_ok(
    compiled::CompiledProblem,
    observation::OracleObservation,
    bits::Int,
)
    for relation in observation.relations
        dependencies = _high_precision_node_dependencies(compiled, relation.node)
        _high_precision_value_ok(relation.raw, dependencies, bits) || return false
        _high_precision_value_ok(relation.scaled, dependencies, bits) || return false
    end
    for guard in observation.guards
        dependencies = _high_precision_node_dependencies(compiled, guard.node)
        _high_precision_value_ok(guard.margin, dependencies, bits) || return false
    end
    for domain in observation.domains
        dependencies = _high_precision_node_dependencies(compiled, domain.node)
        _high_precision_value_ok(domain.margin, dependencies, bits) || return false
    end
    for branch in observation.branches
        dependencies = _high_precision_node_dependencies(
            compiled,
            branch.decision.choice_node,
        )
        _high_precision_value_ok(branch.validity_margin, dependencies, bits) || return false
        _high_precision_value_ok(branch.selector_margin, dependencies, bits) || return false
    end
    target = observation.target
    target isa Real || return false
    return _high_precision_value_ok(target, compiled.sparsity.target_variables, bits)
end

function _high_precision_observation_usable(
    compiled::CompiledProblem,
    observation::OracleObservation,
    base::OracleObservation,
    bits::Int,
)
    observation.status == EVAL_OK || return false
    length(observation.relations) == length(base.relations) || return false
    all(guard -> guard.valid, observation.guards) || return false
    all(domain -> domain.valid, observation.domains) || return false
    _same_branch_signature(observation, base) || return false
    return _high_precision_observation_precision_ok(compiled, observation, bits)
end

function _high_precision_coordinates(compiled::CompiledProblem, normalized)
    return BigFloat[
        BigFloat(variable.spec.origin) + BigFloat(variable.spec.scale) * normalized[index] for
        (index, variable) in enumerate(compiled.variables)
    ]
end

function _high_precision_normalized(compiled::CompiledProblem, coordinates)
    return BigFloat[
        (BigFloat(coordinates[index]) - BigFloat(variable.spec.origin)) /
        BigFloat(variable.spec.scale) for
        (index, variable) in enumerate(compiled.variables)
    ]
end

function _high_precision_within_bounds(compiled::CompiledProblem, coordinates)
    for variable in compiled.variables
        value = coordinates[variable.index]
        variable.spec.lower !== nothing && value < variable.spec.lower && return false
        variable.spec.upper !== nothing && value > variable.spec.upper && return false
    end
    return true
end

function _high_precision_residual(observation::OracleObservation)
    return BigFloat[BigFloat(relation.scaled) for relation in observation.relations]
end

function _high_precision_target(observation::OracleObservation)
    value = observation.target
    value isa Real && isfinite(value) || return nothing
    return BigFloat(value)
end

_high_precision_residual_bound(residual) = isempty(residual) ? BigFloat(0) : norm(residual, Inf)

function _high_precision_sample!(
    work::_HighPrecisionWork,
    normalized,
    base::OracleObservation,
)
    coordinates = _high_precision_coordinates(work.compiled, normalized)
    _high_precision_within_bounds(work.compiled, coordinates) || return nothing
    observation = _high_precision_evaluate!(work, coordinates)
    observation === nothing && return nothing
    if !_high_precision_observation_precision_ok(
        work.compiled,
        observation,
        work.precision_bits,
    )
        work.stop_failure = HIGH_PRECISION_REFINEMENT_PRECISION_DOWNGRADE
        return nothing
    end
    _high_precision_observation_usable(
        work.compiled,
        observation,
        base,
        work.precision_bits,
    ) || return nothing
    target = _high_precision_target(observation)
    target === nothing && return nothing
    return (
        observation,
        residual=_high_precision_residual(observation),
        target,
    )
end

function _high_precision_stencil_column!(
    work::_HighPrecisionWork,
    normalized,
    base::OracleObservation,
    base_residual,
    base_target,
    column::Int;
    radius_multiplier::Real=1,
)
    T = BigFloat
    base_radius = eps(T)^(T(1) / T(5)) * max(one(T), abs(normalized[column]))
    radius = T(radius_multiplier) * base_radius
    for _ in 1:8
        samples = Dict{Int,Any}()
        function sample(offset::Int)
            haskey(samples, offset) && return samples[offset]
            point = copy(normalized)
            point[column] += T(offset) * radius
            samples[offset] = _high_precision_sample!(work, point, base)
            return samples[offset]
        end

        minus_two = sample(-2)
        minus_one = sample(-1)
        plus_one = sample(1)
        plus_two = sample(2)
        work.stop_failure == HIGH_PRECISION_REFINEMENT_NONE || return nothing
        if all(value -> value !== nothing, (minus_two, minus_one, plus_one, plus_two))
            derivative = (
                -plus_two.residual .+ T(8) .* plus_one.residual .-
                T(8) .* minus_one.residual .+ minus_two.residual
            ) ./ (T(12) * radius)
            target_derivative = (
                -plus_two.target + T(8) * plus_one.target -
                T(8) * minus_one.target + minus_two.target
            ) / (T(12) * radius)
            return derivative, target_derivative
        end

        plus_three = sample(3)
        plus_four = sample(4)
        work.stop_failure == HIGH_PRECISION_REFINEMENT_NONE || return nothing
        if all(value -> value !== nothing, (plus_one, plus_two, plus_three, plus_four))
            derivative = (
                -T(25) .* base_residual .+ T(48) .* plus_one.residual .-
                T(36) .* plus_two.residual .+ T(16) .* plus_three.residual .-
                T(3) .* plus_four.residual
            ) ./ (T(12) * radius)
            target_derivative = (
                -T(25) * base_target + T(48) * plus_one.target -
                T(36) * plus_two.target + T(16) * plus_three.target -
                T(3) * plus_four.target
            ) / (T(12) * radius)
            return derivative, target_derivative
        end

        minus_three = sample(-3)
        minus_four = sample(-4)
        work.stop_failure == HIGH_PRECISION_REFINEMENT_NONE || return nothing
        if all(value -> value !== nothing, (minus_one, minus_two, minus_three, minus_four))
            derivative = (
                T(25) .* base_residual .- T(48) .* minus_one.residual .+
                T(36) .* minus_two.residual .- T(16) .* minus_three.residual .+
                T(3) .* minus_four.residual
            ) ./ (T(12) * radius)
            target_derivative = (
                T(25) * base_target - T(48) * minus_one.target +
                T(36) * minus_two.target - T(16) * minus_three.target +
                T(3) * minus_four.target
            ) / (T(12) * radius)
            return derivative, target_derivative
        end
        radius /= T(2)
    end
    return nothing
end

function _high_precision_jacobian!(
    work::_HighPrecisionWork,
    normalized,
    base::OracleObservation;
    radius_multiplier::Real=1,
)
    residual = _high_precision_residual(base)
    target = _high_precision_target(base)
    target === nothing && return nothing
    jacobian = zeros(BigFloat, length(residual), length(normalized))
    gradient = zeros(BigFloat, length(normalized))
    for column in eachindex(normalized)
        stencil = _high_precision_stencil_column!(
            work,
            normalized,
            base,
            residual,
            target,
            column;
            radius_multiplier,
        )
        stencil === nothing && return nothing
        jacobian[:, column] .= first(stencil)
        gradient[column] = last(stencil)
    end
    return jacobian, gradient
end

function _high_precision_rank_factorization(jacobian; uncertainty::Real=0)
    factorization = qr(jacobian, ColumnNorm())
    count_diagonal = min(size(jacobian)...)
    diagonal = BigFloat[
        abs(factorization.R[index, index]) for index in 1:count_diagonal
    ]
    largest = isempty(diagonal) ? BigFloat(0) : maximum(diagonal)
    scale = max(one(BigFloat), norm(jacobian, Inf))
    roundoff = BigFloat(64 * max(1, maximum(size(jacobian)))) *
               eps(BigFloat)^(BigFloat(4) / BigFloat(5)) * scale
    threshold = max(roundoff, BigFloat(2) * BigFloat(uncertainty))
    retained = filter(value -> value > threshold, diagonal)
    rank = length(retained)
    condition = isempty(retained) ? BigFloat(Inf) : maximum(retained) / minimum(retained)
    return (; factorization, rank, condition, threshold)
end

function _high_precision_linear_step(factorization, residual)
    correction = try
        factorization \ (-residual)
    catch error
        error isa Union{SingularException,DimensionMismatch,LinearAlgebra.LAPACKException} ||
            rethrow()
        return nothing
    end
    all(isfinite, correction) || return nothing
    return BigFloat[correction...]
end

function _high_precision_line_search!(
    work::_HighPrecisionWork,
    normalized,
    base::OracleObservation,
    residual,
    step,
)
    merit = isempty(residual) ? BigFloat(0) : sum(abs2, residual) / BigFloat(2)
    alpha = one(BigFloat)
    for _ in 1:12
        trial_normalized = normalized .+ alpha .* step
        sample = _high_precision_sample!(work, trial_normalized, base)
        work.stop_failure == HIGH_PRECISION_REFINEMENT_NONE || return nothing
        if sample !== nothing
            trial_merit = isempty(sample.residual) ? BigFloat(0) :
                          sum(abs2, sample.residual) / BigFloat(2)
            trial_merit < merit && return (
                normalized=BigFloat[trial_normalized...],
                observation=sample.observation,
                residual=sample.residual,
            )
        end
        alpha /= BigFloat(2)
    end
    return nothing
end

function _high_precision_lm_step(jacobian, residual)
    variable_count = size(jacobian, 2)
    damping = sqrt(eps(BigFloat)) * max(one(BigFloat), norm(jacobian, Inf)^2)
    augmented = [
        jacobian
        sqrt(damping) * Matrix{BigFloat}(I, variable_count, variable_count)
    ]
    right_hand_side = [-residual; zeros(BigFloat, variable_count)]
    factor = _high_precision_rank_factorization(augmented)
    factor.rank == variable_count || return nothing
    correction = try
        factor.factorization \ right_hand_side
    catch error
        error isa Union{SingularException,DimensionMismatch,LinearAlgebra.LAPACKException} ||
            rethrow()
        return nothing
    end
    all(isfinite, correction) || return nothing
    return BigFloat[correction...]
end

function _high_precision_empty_observation(diagnostic::AbstractString)
    return OracleObservation((), nothing, (), (), (), EVAL_PLUGIN_ERROR, 0, String(diagnostic))
end

function _high_precision_failure_result(
    work::_HighPrecisionWork,
    method,
    coordinates,
    observation,
    failure,
    diagnostic;
    residual_bound=BigFloat(Inf),
    correction_bound=BigFloat(Inf),
    target_error_bound=BigFloat(Inf),
    numerical_rank=0,
    condition_estimate=BigFloat(Inf),
    rank_stable=false,
    iterations=0,
)
    effective_failure = work.stop_failure == HIGH_PRECISION_REFINEMENT_NONE ?
                        failure : work.stop_failure
    effective_diagnostic = if effective_failure == HIGH_PRECISION_REFINEMENT_CANCELLED
        "high-precision refinement was cancelled"
    elseif effective_failure == HIGH_PRECISION_REFINEMENT_DEADLINE_REACHED
        "high-precision refinement reached its deadline"
    elseif effective_failure == HIGH_PRECISION_REFINEMENT_ORACLE_BUDGET_EXHAUSTED
        "high-precision refinement exhausted its oracle budget"
    elseif effective_failure == HIGH_PRECISION_REFINEMENT_PRECISION_DOWNGRADE
        "a variable-dependent C2 output did not preserve the requested precision"
    else
        String(diagnostic)
    end
    evidence = HighPrecisionRootEvidence(
        String(method),
        work.precision_bits,
        Tuple(coordinates),
        observation,
        BigFloat(residual_bound),
        BigFloat(correction_bound),
        BigFloat(target_error_bound),
        Int(numerical_rank),
        BigFloat(condition_estimate),
        Bool(rank_stable),
        Int(iterations),
        _high_precision_snapshot(work),
    )
    return HighPrecisionRefinementResult(false, effective_failure, effective_diagnostic, evidence)
end

function _high_precision_success_result(
    work,
    method,
    coordinates,
    observation,
    residual_bound,
    correction_bound,
    target_error_bound,
    numerical_rank,
    condition_estimate,
    rank_stable,
    iterations,
)
    evidence = HighPrecisionRootEvidence(
        String(method),
        work.precision_bits,
        Tuple(coordinates),
        observation,
        BigFloat(residual_bound),
        BigFloat(correction_bound),
        BigFloat(target_error_bound),
        Int(numerical_rank),
        BigFloat(condition_estimate),
        Bool(rank_stable),
        Int(iterations),
        _high_precision_snapshot(work),
    )
    return HighPrecisionRefinementResult(
        true,
        HIGH_PRECISION_REFINEMENT_NONE,
        nothing,
        evidence,
    )
end

function _run_high_precision_refinement(
    compiled::CompiledProblem,
    start::AbstractVector;
    precision_bits::Integer,
    evaluator_kind::Symbol,
    residual_goal::Real,
    configuration_tolerance::Real,
    target_tolerance::Real,
    deadline_ns::UInt64=typemax(UInt64),
    cancelled=() -> false,
    remaining_oracle_work::Integer=typemax(Int),
    max_iterations::Integer=16,
)
    evaluator_kind in (:compiled, :reference) || throw(
        ArgumentError("evaluator_kind must be :compiled or :reference"),
    )
    precision_bits >= 64 || throw(ArgumentError("precision_bits must be at least 64"))
    remaining_oracle_work isa Bool && throw(
        ArgumentError("remaining_oracle_work must be an integer count, not Bool"),
    )
    0 <= remaining_oracle_work <= typemax(Int) || throw(
        ArgumentError("remaining_oracle_work must fit a nonnegative Int"),
    )
    max_iterations >= 0 || throw(ArgumentError("max_iterations must be nonnegative"))
    length(start) == length(compiled.variables) || throw(
        ArgumentError("high-precision refinement received the wrong coordinate count"),
    )
    method = evaluator_kind == :compiled ?
             "compiled_c2_cpqr_5point_v1" : "reference_c2_cpqr_5point_v1"

    return setprecision(BigFloat, Int(precision_bits)) do
        workspace = evaluator_kind == :compiled ? CompiledWorkspace(compiled) : nothing
        evaluator = if evaluator_kind == :compiled
            coordinates -> evaluate(
                compiled,
                coordinates;
                capability=C2,
                workspace=workspace::CompiledWorkspace,
            )
        else
            coordinates -> evaluate_reference(
                compiled.problem,
                compiled.registry,
                coordinates;
                capability=C2,
            )
        end
        work = _HighPrecisionWork(
            compiled,
            evaluator,
            Int(precision_bits),
            _high_precision_weight(precision_bits),
            deadline_ns,
            cancelled,
            Int(remaining_oracle_work),
            0,
            0,
            0,
            HIGH_PRECISION_REFINEMENT_NONE,
        )
        coordinates = BigFloat[BigFloat(value) for value in start]
        normalized = _high_precision_normalized(compiled, coordinates)
        base = _high_precision_evaluate!(work, coordinates)
        if base === nothing
            return _high_precision_failure_result(
                work,
                method,
                coordinates,
                _high_precision_empty_observation("base evaluation was not run"),
                HIGH_PRECISION_REFINEMENT_BASE_EVALUATION_FAILED,
                "high-precision base evaluation was not available",
            )
        end
        if !_high_precision_observation_precision_ok(compiled, base, Int(precision_bits))
            work.stop_failure = HIGH_PRECISION_REFINEMENT_PRECISION_DOWNGRADE
            return _high_precision_failure_result(
                work,
                method,
                coordinates,
                base,
                HIGH_PRECISION_REFINEMENT_PRECISION_DOWNGRADE,
                "high-precision base evaluation downgraded a variable-dependent value",
            )
        end
        if base.status != EVAL_OK || !all(guard -> guard.valid, base.guards) ||
           !all(domain -> domain.valid, base.domains)
            return _high_precision_failure_result(
                work,
                method,
                coordinates,
                base,
                HIGH_PRECISION_REFINEMENT_SEMANTICS_FAILED,
                something(base.diagnostic, "high-precision base semantics are invalid"),
            )
        end

        residual = _high_precision_residual(base)
        residual_bound = _high_precision_residual_bound(residual)
        exact_zero = isempty(residual) || all(iszero, residual)
        if exact_zero && isempty(compiled.variables)
            if !_check_high_precision_resources!(work; reserve_evaluation=false)
                return _high_precision_failure_result(
                    work,
                    method,
                    coordinates,
                    base,
                    work.stop_failure,
                    "resource stop after exact-zero base evaluation",
                    residual_bound=residual_bound,
                )
            end
            return _high_precision_success_result(
                work,
                method,
                coordinates,
                base,
                residual_bound,
                BigFloat(0),
                BigFloat(0),
                0,
                BigFloat(Inf),
                true,
                0,
            )
        end

        goal = BigFloat(residual_goal)
        configuration_gate = BigFloat(configuration_tolerance)
        target_gate = BigFloat(target_tolerance)
        last_rank = 0
        last_condition = BigFloat(Inf)
        last_correction = BigFloat(Inf)
        last_target_error = BigFloat(Inf)

        for iteration in 0:Int(max_iterations)
            if !_check_high_precision_resources!(work; reserve_evaluation=false)
                return _high_precision_failure_result(
                    work,
                    method,
                    coordinates,
                    base,
                    work.stop_failure,
                    "resource stop before high-precision Jacobian",
                    residual_bound=residual_bound,
                    correction_bound=last_correction,
                    target_error_bound=last_target_error,
                    numerical_rank=last_rank,
                    condition_estimate=last_condition,
                    iterations=iteration,
                )
            end
            first_linearization = _high_precision_jacobian!(work, normalized, base)
            first_linearization === nothing && return _high_precision_failure_result(
                work,
                method,
                coordinates,
                base,
                HIGH_PRECISION_REFINEMENT_STENCIL_UNAVAILABLE,
                "a complete branch-stable five-point stencil was unavailable",
                residual_bound=residual_bound,
                iterations=iteration,
            )
            jacobian, gradient = first_linearization
            factor = _high_precision_rank_factorization(jacobian)
            last_rank = factor.rank
            last_condition = factor.condition
            # A numerical configuration claim requires local isolation in every
            # free-variable direction. Full row rank is insufficient for an
            # underdetermined manifold even when its target appears constant.
            required_rank = size(jacobian, 2)
            factor.rank == required_rank || return _high_precision_failure_result(
                work,
                method,
                coordinates,
                base,
                HIGH_PRECISION_REFINEMENT_RANK_DEFICIENT,
                "the five-point Jacobian is rank deficient for a nonzero residual",
                residual_bound=residual_bound,
                numerical_rank=last_rank,
                condition_estimate=last_condition,
                iterations=iteration,
            )
            correction = _high_precision_linear_step(factor.factorization, residual)
            correction === nothing && return _high_precision_failure_result(
                work,
                method,
                coordinates,
                base,
                HIGH_PRECISION_REFINEMENT_LINEAR_SOLVE_FAILED,
                "the BigFloat CPQR correction failed",
                residual_bound=residual_bound,
                numerical_rank=last_rank,
                condition_estimate=last_condition,
                iterations=iteration,
            )
            last_correction = norm(correction, Inf)
            target_scale = max(one(BigFloat), abs(BigFloat(base.target)))
            last_target_error = abs(dot(gradient, correction)) / target_scale

            if residual_bound <= goal && last_correction <= configuration_gate &&
               last_target_error <= target_gate
                second_linearization = _high_precision_jacobian!(
                    work,
                    normalized,
                    base;
                    radius_multiplier=BigFloat(0.5),
                )
                second_linearization === nothing && return _high_precision_failure_result(
                    work,
                    method,
                    coordinates,
                    base,
                    HIGH_PRECISION_REFINEMENT_STENCIL_UNAVAILABLE,
                    "the h/2 confirmation stencil was unavailable",
                    residual_bound=residual_bound,
                    correction_bound=last_correction,
                    target_error_bound=last_target_error,
                    numerical_rank=last_rank,
                    condition_estimate=last_condition,
                    iterations=iteration,
                )
                second_jacobian, second_gradient = second_linearization
                uncertainty = norm(second_jacobian - jacobian, Inf)
                first_confirmed = _high_precision_rank_factorization(
                    jacobian;
                    uncertainty,
                )
                second_factor = _high_precision_rank_factorization(
                    second_jacobian;
                    uncertainty,
                )
                rank_stable = first_confirmed.rank == second_factor.rank == required_rank
                rank_stable || return _high_precision_failure_result(
                    work,
                    method,
                    coordinates,
                    base,
                    HIGH_PRECISION_REFINEMENT_RANK_DEFICIENT,
                    "h and h/2 rank decisions disagree or are deficient",
                    residual_bound=residual_bound,
                    correction_bound=last_correction,
                    target_error_bound=last_target_error,
                    numerical_rank=min(first_confirmed.rank, second_factor.rank),
                    condition_estimate=max(first_confirmed.condition, second_factor.condition),
                    iterations=iteration,
                )
                first_correction = _high_precision_linear_step(
                    first_confirmed.factorization,
                    residual,
                )
                second_correction = _high_precision_linear_step(
                    second_factor.factorization,
                    residual,
                )
                if first_correction === nothing || second_correction === nothing
                    return _high_precision_failure_result(
                        work,
                        method,
                        coordinates,
                        base,
                        HIGH_PRECISION_REFINEMENT_LINEAR_SOLVE_FAILED,
                        "the h/h2 confirmation corrections failed",
                        residual_bound=residual_bound,
                        numerical_rank=required_rank,
                        condition_estimate=max(
                            first_confirmed.condition,
                            second_factor.condition,
                        ),
                        iterations=iteration,
                    )
                end
                correction_bound = max(
                    norm(first_correction, Inf),
                    norm(second_correction, Inf),
                    norm(first_correction - second_correction, Inf),
                )
                target_error_bound = max(
                    abs(dot(gradient, first_correction)),
                    abs(dot(second_gradient, second_correction)),
                ) / target_scale
                if correction_bound <= configuration_gate && target_error_bound <= target_gate
                    if !_check_high_precision_resources!(work; reserve_evaluation=false)
                        return _high_precision_failure_result(
                            work,
                            method,
                            coordinates,
                            base,
                            work.stop_failure,
                            "resource stop after high-precision confirmation",
                            residual_bound=residual_bound,
                            correction_bound=correction_bound,
                            target_error_bound=target_error_bound,
                            numerical_rank=required_rank,
                            condition_estimate=max(
                                first_confirmed.condition,
                                second_factor.condition,
                            ),
                            rank_stable=true,
                            iterations=iteration,
                        )
                    end
                    return _high_precision_success_result(
                        work,
                        method,
                        coordinates,
                        base,
                        residual_bound,
                        correction_bound,
                        target_error_bound,
                        required_rank,
                        max(first_confirmed.condition, second_factor.condition),
                        true,
                        iteration,
                    )
                end
                correction = second_correction
                last_correction = correction_bound
                last_target_error = target_error_bound
            end

            iteration == max_iterations && break
            trial = _high_precision_line_search!(work, normalized, base, residual, correction)
            if trial === nothing && work.stop_failure == HIGH_PRECISION_REFINEMENT_NONE
                damped = _high_precision_lm_step(jacobian, residual)
                damped === nothing ||
                    (trial = _high_precision_line_search!(
                        work,
                        normalized,
                        base,
                        residual,
                        damped,
                    ))
            end
            trial === nothing && return _high_precision_failure_result(
                work,
                method,
                coordinates,
                base,
                HIGH_PRECISION_REFINEMENT_NO_PROGRESS,
                "neither CPQR Gauss-Newton nor safeguarded LM improved the residual",
                residual_bound=residual_bound,
                correction_bound=last_correction,
                target_error_bound=last_target_error,
                numerical_rank=last_rank,
                condition_estimate=last_condition,
                iterations=iteration,
            )
            normalized = trial.normalized
            coordinates = _high_precision_coordinates(compiled, normalized)
            base = trial.observation
            residual = trial.residual
            residual_bound = _high_precision_residual_bound(residual)
        end

        return _high_precision_failure_result(
            work,
            method,
            coordinates,
            base,
            residual_bound > goal ?
            HIGH_PRECISION_REFINEMENT_RESIDUAL_GOAL_FAILED :
            HIGH_PRECISION_REFINEMENT_ITERATION_LIMIT,
            "high-precision refinement did not meet its residual and forward-error gates",
            residual_bound=residual_bound,
            correction_bound=last_correction,
            target_error_bound=last_target_error,
            numerical_rank=last_rank,
            condition_estimate=last_condition,
            iterations=Int(max_iterations),
        )
    end
end

function _run_high_precision_replay(
    compiled::CompiledProblem,
    coordinates::AbstractVector;
    precision_bits::Integer,
    deadline_ns::UInt64=typemax(UInt64),
    cancelled=() -> false,
    remaining_oracle_work::Integer=typemax(Int),
)
    remaining_oracle_work isa Bool && throw(
        ArgumentError("remaining_oracle_work must be an integer count, not Bool"),
    )
    0 <= remaining_oracle_work <= typemax(Int) || throw(
        ArgumentError("remaining_oracle_work must fit a nonnegative Int"),
    )
    return setprecision(BigFloat, Int(precision_bits)) do
        evaluator = point -> evaluate_reference(
            compiled.problem,
            compiled.registry,
            point;
            capability=C2,
        )
        work = _HighPrecisionWork(
            compiled,
            evaluator,
            Int(precision_bits),
            _high_precision_weight(precision_bits),
            deadline_ns,
            cancelled,
            Int(remaining_oracle_work),
            0,
            0,
            0,
            HIGH_PRECISION_REFINEMENT_NONE,
        )
        replay_coordinates = BigFloat[BigFloat(value) for value in coordinates]
        observation = _high_precision_evaluate!(work, replay_coordinates)
        if observation !== nothing && !_high_precision_observation_precision_ok(
            compiled,
            observation,
            Int(precision_bits),
        )
            work.stop_failure = HIGH_PRECISION_REFINEMENT_PRECISION_DOWNGRADE
        end
        return (
            coordinates=Tuple(replay_coordinates),
            observation=observation === nothing ?
                        _high_precision_empty_observation("canonical replay was not run") :
                        observation,
            failure=work.stop_failure,
            work=_high_precision_snapshot(work),
        )
    end
end
