const SOLVE_API_VERSION = v"1.6.0"

struct SolveConfigurationError <: CoreError
    code::Symbol
    message::String
end

Base.showerror(io::IO, error::SolveConfigurationError) =
    print(io, "GeoTarget solve configuration ", error.code, ": ", error.message)

@enum SolveAnswerLevel::UInt8 begin
    ANSWER_VALIDATED = 0
    ANSWER_EXACT_IF_AVAILABLE = 1
end

"""
Explicitly unstable, Julia-only hooks for numerical algorithm experiments.

This type is deliberately absent from the wire protocol and is not part of the
stable plugin ABI. `proposal_factory(compiled, options)` must return a proposal
emitter accepted by `run_search!`. `local_solver(compiled, evaluate_fn, start;
kwargs...)` must return a `LocalAttempt` and must route every charged oracle
evaluation through `evaluate_fn`; `compiled` is supplied for immutable metadata
such as dependency sparsity. Experimental executions cannot resume from or
produce a continuation compatible with a production checkpoint.
"""
struct UnstableResearchStrategy{P,L}
    id::String
    proposal_factory::P
    local_solver::L

    function UnstableResearchStrategy(
        id::AbstractString,
        proposal_factory::P,
        local_solver::L,
    ) where {P,L}
        frozen_id = String(id)
        occursin(r"^[a-z0-9][a-z0-9._/-]{0,127}$", frozen_id) || throw(
            ArgumentError(
                "unstable research strategy id must be a lowercase versioned identifier",
            ),
        )
        proposal_factory === nothing &&
            throw(ArgumentError("proposal_factory must be callable"))
        local_solver === nothing && throw(ArgumentError("local_solver must be callable"))
        return new{P,L}(frozen_id, proposal_factory, local_solver)
    end
end

"""Stable public solve controls; experimental knobs remain inside versioned presets."""
struct SolveOptions
    version::VersionNumber
    preset::Symbol
    wall_seconds::Float64
    seed::UInt64
    answer_level::SolveAnswerLevel
    worker_count::Int
    policy::SolvePolicy
    _local::LocalSolveOptions
    _validation::CandidateValidationOptions
end

function _solve_policy(preset::Symbol)
    preset in (:default, :standard) && return standard_policy(), :standard
    preset === :fast && return fast_policy(), :fast
    preset === :thorough && return thorough_policy(), :thorough
    throw(
        SolveConfigurationError(
            :unknown_preset,
            "preset must be fast, standard/default, or thorough",
        ),
    )
end

function _solve_answer_level(value)
    value isa SolveAnswerLevel && return value
    value in (:validated, "validated") && return ANSWER_VALIDATED
    value in (:exact_if_available, "exact_if_available") &&
        return ANSWER_EXACT_IF_AVAILABLE
    throw(
        SolveConfigurationError(
            :unknown_answer_level,
            "answer_level must be validated or exact_if_available",
        ),
    )
end

function SolveOptions(
    ;
    preset::Union{Symbol,AbstractString}=:standard,
    wall_seconds::Union{Nothing,Real}=nothing,
    seed::Integer=0,
    answer_level=:exact_if_available,
    worker_count::Integer=1,
)
    selected_policy, canonical_preset = _solve_policy(Symbol(preset))
    seconds = wall_seconds === nothing ? selected_policy.wall_seconds : Float64(wall_seconds)
    isfinite(seconds) && seconds > 0 || throw(
        SolveConfigurationError(:invalid_wall_budget, "wall_seconds must be finite and positive"),
    )
    0 <= seed <= typemax(UInt64) || throw(
        SolveConfigurationError(:invalid_seed, "seed must fit in UInt64"),
    )
    worker_count >= 1 || throw(
        SolveConfigurationError(:invalid_worker_count, "worker_count must be positive"),
    )
    validation = CandidateValidationOptions()
    # Float64 discovery convergence is deliberately separate from the
    # 1e-100 high-precision answer gate.
    local_options = LocalSolveOptions(residual_tolerance=1.0e-12)
    return SolveOptions(
        SOLVE_API_VERSION,
        canonical_preset,
        seconds,
        UInt64(seed),
        _solve_answer_level(answer_level),
        Int(worker_count),
        selected_policy,
        local_options,
        validation,
    )
end

SolveOptions(options::SolveOptionsV1) = SolveOptions(
    preset=options.preset,
    wall_seconds=options.wall_time_seconds,
    seed=options.seed,
    answer_level=options.answer_level,
    worker_count=options.worker_count,
)

"""A result plus its in-memory replay evidence and resumable search snapshot."""
struct SolveExecution
    result::SolveResult
    evidence_json::String
    checkpoint::CheckpointSnapshot
    loop_status::SearchLoopStatus
end

SolveCheckpointArtifact(execution::SolveExecution) = SolveCheckpointArtifact(
    execution.checkpoint,
    execution.result.target_image_status,
)

write_checkpoint(path::AbstractString, execution::SolveExecution) =
    write_checkpoint(path, SolveCheckpointArtifact(execution))

function _checkpoint_saw_inconclusive_image(checkpoint::SolveCheckpointArtifact)
    return any(
        record -> begin
            diagnostic = record.observation.diagnostic
            diagnostic !== nothing &&
                occursin("target_image=TARGET_IMAGE_INCONCLUSIVE", diagnostic)
        end,
        checkpoint.snapshot.workspace.candidates.history,
    )
end

mutable struct _CompiledAttemptRunner{I<:TargetImageDiagnosticOptions,L}
    compiled::CompiledProblem
    workspace::CompiledWorkspace
    local_options::LocalSolveOptions
    validation_options::CandidateValidationOptions
    image_options::I
    local_solver::L
    exact_backend::Union{Nothing,AbstractExactBackend}
    exact_descriptor::Union{Nothing,ExactBackendDescriptor}
    answer_level::SolveAnswerLevel
    saw_likely_continuous::Bool
    saw_inconclusive_image::Bool
end

_default_proposal_factory(compiled::CompiledProblem, options::SolveOptions) =
    ProposalEngine(compiled.problem; seed=options.seed)

function _default_compiled_local_solver(
    ::CompiledProblem,
    evaluate_fn,
    start;
    origins,
    scales,
    lower,
    upper,
    options,
    deadline_ns,
    cancelled,
)
    return solve_local(
        evaluate_fn,
        start;
        origins,
        scales,
        lower,
        upper,
        options,
        deadline_ns,
        cancelled,
    )
end

function _remaining_deadline_ns(context::ExecutionContext)
    remaining = max(0.0, context.deadline - Float64(context.clock()))
    now = time_ns()
    remaining >= Float64(typemax(UInt64) - now) / 1.0e9 && return typemax(UInt64)
    addition = UInt64(clamp(floor(remaining * 1.0e9), 0, typemax(UInt64) - now))
    return now + addition
end

function _remaining_oracle_work(context::ExecutionContext, uncommitted::Int=0)
    uncommitted >= 0 || throw(ArgumentError("uncommitted oracle work must be nonnegative"))
    limit = context.budget.limits.oracle_work
    limit === nothing && return typemax(Int)
    consumed = context.budget.oracle_work
    consumed <= limit || throw(
        InvariantError(:oracle_budget_overdrawn, "oracle budget ledger exceeds its limit"),
    )
    available = limit - consumed
    return uncommitted >= available ? 0 : available - uncommitted
end

function _local_options_with_evaluation_limit(options::LocalSolveOptions, limit::Int)
    limit > 0 || throw(ArgumentError("local evaluation limit must be positive"))
    limit == options.max_evaluations && return options
    return LocalSolveOptions(
        max_iterations=options.max_iterations,
        max_evaluations=limit,
        residual_tolerance=options.residual_tolerance,
        step_tolerance=options.step_tolerance,
        finite_difference_step=options.finite_difference_step,
        initial_damping=options.initial_damping,
        damping_increase=options.damping_increase,
        damping_decrease=options.damping_decrease,
    )
end

function _oracle_budget_partial_observation(proposal::Proposal)
    return Observation(
        proposal.task_id,
        proposal.configuration_id;
        canonical_near_feasible=false,
        needs_refinement=false,
        residual_score=Inf,
        oracle_work=0,
        endpoint=proposal.coordinates,
        diagnostic="local_status=not_run;resource=oracle_budget_exhausted",
    )
end

function _residual_score(observation::OracleObservation)
    isempty(observation.relations) && return 0.0
    values = Float64[]
    for relation in observation.relations
        value = Float64(abs(relation.scaled))
        isfinite(value) || return Inf
        push!(values, value)
    end
    return maximum(values)
end

function _near_feasible(observation::OracleObservation, tolerance::Float64)
    observation.status == EVAL_OK || return false
    all(guard -> guard.valid, observation.guards) || return false
    all(domain -> domain.valid, observation.domains) || return false
    return _residual_score(observation) <= max(100 * tolerance, sqrt(eps(Float64)))
end

function _candidate_target(observation::OracleObservation)
    target = observation.target
    target isa Real && isfinite(target) || return nothing
    return TargetEnclosure(target)
end

function _validation_target(validation::CandidateValidationResult)
    enclosure = validation.target_enclosure
    enclosure === nothing && return nothing
    return TargetEnclosure(enclosure.lower, enclosure.upper)
end

function _local_diagnostic(attempt, validation=nothing, image=nothing, correction=nothing)
    validation_text = validation === nothing ? "not_run" : string(validation.failure)
    image_text = image === nothing ? "not_run" : string(image.classification)
    image_failure_text = image === nothing ? "not_run" : string(image.failure)
    correction_text = correction === nothing ? "not_run" : correction.detail
    return join(
        (
            "local_status=$(attempt.status)",
            "iterations=$(attempt.iterations)",
            "evaluations=$(attempt.evaluations)",
            "rank=$(attempt.numerical_rank)",
            "condition=$(attempt.condition_estimate)",
            "validation=$validation_text",
            "target_image=$image_text",
            "target_image_failure=$image_failure_text",
            "root_correction=$correction_text",
        ),
        ';',
    )
end

function _exactification_detail(result::ExactificationResult)
    result.accepted && return "accepted"
    isempty(result.detail) && return string(result.failure)
    return string(result.failure, ':', result.detail)
end

function _attempt_exactification!(
    runner::_CompiledAttemptRunner,
    context::ExecutionContext,
    candidate::Union{ExactificationSeed,CandidateValidationResult},
    oracle_work::Base.RefValue{Int},
)
    backend = runner.exact_backend
    descriptor = runner.exact_descriptor
    if runner.answer_level != ANSWER_EXACT_IF_AVAILABLE || backend === nothing ||
       descriptor === nothing
        return (
            answer=nothing,
            failure=nothing,
            detail="not_requested",
            reference_sample=nothing,
        )
    end
    result = run_exactification(
        backend,
        runner.compiled,
        candidate;
        deadline_ns=_remaining_deadline_ns(context),
        cancelled=() -> is_cancelled(context.cancel),
        remaining_oracle_work=_remaining_oracle_work(context, oracle_work[]),
    )
    oracle_work[] = Base.checked_add(oracle_work[], result.oracle_work)
    observed_descriptor = result.backend
    if observed_descriptor === nothing ||
       !_same_exact_backend_descriptor(descriptor, observed_descriptor)
        return (
            answer=nothing,
            failure=EXACTIFICATION_BACKEND_PROTOCOL_FAILED,
            detail="backend_descriptor_changed",
            reference_sample=nothing,
        )
    end
    result.accepted || return (
        answer=nothing,
        failure=result.failure,
        detail=_exactification_detail(result),
        reference_sample=nothing,
    )
    reference_sample = last(result.reference_samples)
    return (
        answer=result.answer::ExactAnswer,
        failure=EXACTIFICATION_NONE,
        detail="accepted",
        reference_sample,
    )
end

function _promotion_failure(failure::ExactificationFailure)
    failure == EXACTIFICATION_CAPABILITY_MISSING && return EXACT_CAPABILITY_MISSING
    failure == EXACTIFICATION_RECOGNITION_FAILED && return EXACT_RECOGNITION_FAILED
    failure in (
        EXACTIFICATION_CANCELLED,
        EXACTIFICATION_DEADLINE_REACHED,
        EXACTIFICATION_ORACLE_BUDGET_EXHAUSTED,
    ) && return EXACT_BUDGET_EXHAUSTED
    failure == EXACTIFICATION_SAMPLE_FAILED && return EXACT_SINGULAR
    failure in (
        EXACTIFICATION_REPLAY_FAILED,
        EXACTIFICATION_INVALID_CANDIDATE,
    ) && return EXACT_CONFIGURATION_CERT_FAILED
    failure in (
        EXACTIFICATION_CERTIFICATE_FAILED,
        EXACTIFICATION_VERIFICATION_FAILED,
    ) && return EXACT_TARGET_CERT_FAILED
    return EXACT_UNSUPPORTED
end

function _provisional_after_exactification(
    provisional::ProvisionalAnswer,
    exactification,
)
    failure = exactification.failure
    failure === nothing && return provisional
    return ProvisionalAnswer(
        provisional.target,
        provisional.canonical_residual_bound,
        provisional.branch_signature,
        provisional.validation;
        guard_enclosures=provisional.guard_enclosures,
        exact_failure=_promotion_failure(failure),
        exact_failure_detail=exactification.detail,
    )
end

function _unresolved_exactification_attempt!(
    runner::_CompiledAttemptRunner,
    context::ExecutionContext,
    endpoint,
    observation::OracleObservation,
    image::TargetImageDiagnostic,
    oracle_work::Base.RefValue{Int},
    ;
    allow_unresolved_correction::Bool=false,
)
    runner.answer_level == ANSWER_EXACT_IF_AVAILABLE || return (
        answer=nothing,
        failure=nothing,
        detail="not_requested",
        reference_sample=nothing,
    )
    runner.exact_backend === nothing && return (
        answer=nothing,
        failure=nothing,
        detail="not_requested",
        reference_sample=nothing,
    )
    supports(capabilities(runner.compiled), C3A) || return (
        answer=nothing,
        failure=EXACTIFICATION_CAPABILITY_MISSING,
        detail="c3a_capability_missing",
        reference_sample=nothing,
    )
    image.classification == TARGET_LIKELY_CONTINUOUS && return (
        answer=nothing,
        failure=EXACTIFICATION_INVALID_CANDIDATE,
        detail="likely_continuous",
        reference_sample=nothing,
    )
    image.linearization_computed || return (
        answer=nothing,
        failure=EXACTIFICATION_INVALID_CANDIDATE,
        detail="rank_unavailable",
        reference_sample=nothing,
    )
    rank = image.numerical_rank
    rank === nothing && return (
        answer=nothing,
        failure=EXACTIFICATION_INVALID_CANDIDATE,
        detail="rank_unavailable",
        reference_sample=nothing,
    )
    rank < length(runner.compiled.variables) || allow_unresolved_correction || return (
        answer=nothing,
        failure=EXACTIFICATION_INVALID_CANDIDATE,
        detail="full_variable_rank",
        reference_sample=nothing,
    )
    seed = try
        seed_factory = allow_unresolved_correction ?
                       unresolved_exactification_seed :
                       rank_deficient_exactification_seed
        seed_factory(
            runner.compiled,
            endpoint,
            observation;
            residual_tolerance=max(
                100 * runner.local_options.residual_tolerance,
                sqrt(eps(Float64)),
            ),
        )
    catch error
        error isa InterruptException && rethrow()
        error isa ArgumentError || rethrow()
        return (
            answer=nothing,
            failure=EXACTIFICATION_INVALID_CANDIDATE,
            detail="seed_rejected:$(sprint(showerror, error))",
            reference_sample=nothing,
        )
    end
    # `seed.kind` is intentionally not consulted. Numerically unresolved
    # promotion is exact-only here, regardless of any relabelled provenance.
    return _attempt_exactification!(runner, context, seed, oracle_work)
end

_exact_target_identity(answer::ExactAnswer) =
    "exact/$(string(answer.target_certificate.identity))"

function _exact_only_observation(
    proposal::Proposal,
    oracle_work::Int,
    answer::ExactAnswer,
    reference::ExactPrecisionSample,
    diagnostic::AbstractString,
)
    target = setprecision(BigFloat, reference.precision_bits) do
        center = BigFloat(reference.target)
        scale = max(one(BigFloat), abs(center))
        radius = max(BigFloat(reference.target_error_bound), parse(BigFloat, "1e-100") * scale)
        TargetEnclosure(center - radius, center + radius)
    end
    return Observation(
        proposal.task_id,
        proposal.configuration_id;
        canonical_near_feasible=true,
        canonical_valid=true,
        target,
        target_identity=_exact_target_identity(answer),
        branch_signature=answer.branch_signature,
        verified=true,
        verified_payload=answer,
        needs_refinement=false,
        residual_score=Float64(reference.residual_bound),
        oracle_work,
        endpoint=reference.coordinates,
        diagnostic=String(diagnostic),
    )
end

function _candidate_root_correction(
    image::TargetImageDiagnostic,
    local_options::LocalSolveOptions,
    half_radius_image::Union{Nothing,TargetImageDiagnostic}=nothing,
)
    residual = Float64[relation.scaled for relation in image.base_observation.relations]
    isempty(residual) && return (
        resolved=true,
        normalized_step=0.0,
        target_step=0.0,
        normalized_correction=(),
        jacobian_relative_disagreement=0.0,
        linear_solve_relative_disagreement=0.0,
        detail="no_relations",
    )
    all(iszero, residual) && return (
        resolved=true,
        normalized_step=0.0,
        target_step=0.0,
        normalized_correction=Tuple(zeros(Float64, size(image.scaled_relation_jacobian, 2))),
        jacobian_relative_disagreement=0.0,
        linear_solve_relative_disagreement=0.0,
        detail="exact_zero_residual",
    )
    image.linearization_computed || return (
        resolved=false,
        normalized_step=Inf,
        target_step=Inf,
        normalized_correction=(),
        jacobian_relative_disagreement=Inf,
        linear_solve_relative_disagreement=Inf,
        detail="linearization_unavailable",
    )
    rank = image.numerical_rank
    if rank === nothing || rank == 0
        return (
            resolved=false,
            normalized_step=Inf,
            target_step=Inf,
            normalized_correction=(),
            jacobian_relative_disagreement=Inf,
            linear_solve_relative_disagreement=Inf,
            detail="rank_unresolved_nonzero_residual",
        )
    end
    jacobian = image.scaled_relation_jacobian
    if rank < min(size(jacobian)...)
        return (
            resolved=false,
            normalized_step=Inf,
            target_step=Inf,
            normalized_correction=(),
            jacobian_relative_disagreement=Inf,
            linear_solve_relative_disagreement=Inf,
            detail="rank_deficient_nonzero_residual",
        )
    end
    gradient = image.target_gradient
    jacobian_disagreement = 0.0
    if half_radius_image !== nothing
        comparison = half_radius_image::TargetImageDiagnostic
        compatible = comparison.linearization_computed &&
                     comparison.numerical_rank == image.numerical_rank &&
                     size(comparison.scaled_relation_jacobian) == size(jacobian) &&
                     comparison.difference_schemes == image.difference_schemes
        compatible || return (
            resolved=false,
            normalized_step=Inf,
            target_step=Inf,
            normalized_correction=(),
            jacobian_relative_disagreement=Inf,
            linear_solve_relative_disagreement=Inf,
            detail="h_half_linearization_mismatch",
        )
        half_jacobian = comparison.scaled_relation_jacobian
        jacobian_disagreement = norm(half_jacobian - jacobian, Inf) /
                                max(1.0, norm(half_jacobian, Inf))
        condition = something(image.condition_estimate, Inf)
        stability_limit = max(
            1.0e-8,
            min(1.0e-3, 64 * sqrt(eps(Float64)) * sqrt(max(1.0, condition))),
        )
        isfinite(jacobian_disagreement) && jacobian_disagreement <= stability_limit || return (
            resolved=false,
            normalized_step=Inf,
            target_step=Inf,
            normalized_correction=(),
            jacobian_relative_disagreement=jacobian_disagreement,
            linear_solve_relative_disagreement=Inf,
            detail="h_half_jacobian_unstable",
        )
        # Richardson extrapolation is column-wise because a boundary may force
        # a first-order one-sided stencil while interior columns remain central.
        extrapolated = similar(jacobian)
        extrapolated_gradient = similar(gradient)
        for column in axes(jacobian, 2)
            factor = image.difference_schemes[column] == TARGET_DIFFERENCE_CENTRAL ? 4.0 : 2.0
            extrapolated[:, column] .=
                (factor .* half_jacobian[:, column] .- jacobian[:, column]) ./ (factor - 1)
            extrapolated_gradient[column] =
                (factor * comparison.target_gradient[column] - gradient[column]) / (factor - 1)
        end
        jacobian = extrapolated
        gradient = extrapolated_gradient
    end
    factorization = svd(jacobian; full=false)
    retained = min(rank::Int, length(factorization.S))
    correction = zeros(Float64, size(jacobian, 2))
    for index in 1:retained
        singular = factorization.S[index]
        isfinite(singular) && singular > 0 || return (
            resolved=false,
            normalized_step=Inf,
            target_step=Inf,
            normalized_correction=(),
            jacobian_relative_disagreement=jacobian_disagreement,
            linear_solve_relative_disagreement=Inf,
            detail="nonfinite_root_correction",
        )
        coefficient = dot(view(factorization.U, :, index), residual) / singular
        correction .-= coefficient .* view(factorization.V, :, index)
    end
    qr_correction = try
        qr(jacobian, ColumnNorm()) \ (-residual)
    catch error
        error isa Union{LinearAlgebra.LAPACKException,SingularException,DimensionMismatch} ||
            rethrow()
        nothing
    end
    solve_disagreement = qr_correction === nothing ? Inf :
                         norm(qr_correction - correction, Inf) /
                         max(eps(Float64), norm(correction, Inf))
    if half_radius_image !== nothing
        condition = something(image.condition_estimate, Inf)
        solve_limit = max(
            1.0e-10,
            min(1.0e-5, 128 * eps(Float64) * max(1.0, condition)),
        )
        isfinite(solve_disagreement) && solve_disagreement <= solve_limit || return (
            resolved=false,
            normalized_step=norm(correction, Inf),
            target_step=Inf,
            normalized_correction=Tuple(correction),
            jacobian_relative_disagreement=jacobian_disagreement,
            linear_solve_relative_disagreement=solve_disagreement,
            detail="svd_cpqr_correction_disagreement",
        )
    end
    normalized_step = norm(correction, Inf)
    target_step = abs(dot(gradient, correction))
    configuration_tolerance = sqrt(local_options.residual_tolerance)
    resolved = isfinite(normalized_step) && isfinite(target_step) &&
               normalized_step <= configuration_tolerance &&
               target_step <= local_options.residual_tolerance
    return (
        resolved,
        normalized_step,
        target_step,
        normalized_correction=Tuple(correction),
        jacobian_relative_disagreement=jacobian_disagreement,
        linear_solve_relative_disagreement=solve_disagreement,
        detail=join(
            (
                "resolved=$(resolved)",
                "normalized_step=$(normalized_step)",
                "target_step=$(target_step)",
                "jacobian_relative_disagreement=$(jacobian_disagreement)",
                "linear_solve_relative_disagreement=$(solve_disagreement)",
            ),
            ',',
        ),
    )
end

const _ROOT_CORRECTION_RESOURCE_FAILURES = (
    TARGET_IMAGE_CANCELLED,
    TARGET_IMAGE_DEADLINE_REACHED,
    TARGET_IMAGE_ORACLE_BUDGET_EXHAUSTED,
)

function _half_radius_target_image_options(options::TargetImageDiagnosticOptions)
    return TargetImageDiagnosticOptions(
        finite_difference_radius=options.finite_difference_radius / 2,
        probe_radii=options.probe_radii,
        relation_tolerance=options.relation_tolerance,
        rank_absolute_tolerance=options.rank_absolute_tolerance,
        rank_relative_tolerance=options.rank_relative_tolerance,
        target_sensitivity_tolerance=options.target_sensitivity_tolerance,
        probe_target_tolerance=options.probe_target_tolerance,
        branch_margin_tolerance=options.branch_margin_tolerance,
        capability=options.capability,
        precision_bits=options.precision_bits,
    )
end

function _corrected_endpoint(compiled, endpoint, normalized_correction)
    length(normalized_correction) == length(endpoint) || return nothing
    corrected = Float64[]
    for (index, delta) in enumerate(normalized_correction)
        variable = compiled.variables[index].spec
        value = Float64(endpoint[index]) + Float64(variable.scale) * Float64(delta)
        isfinite(value) || return nothing
        variable.lower !== nothing && value < variable.lower && return nothing
        variable.upper !== nothing && value > variable.upper && return nothing
        push!(corrected, value)
    end
    return corrected
end

function _correction_summary(correction, steps::Int, suffix::AbstractString)
    return (
        resolved=correction.resolved,
        normalized_step=correction.normalized_step,
        target_step=correction.target_step,
        normalized_correction=correction.normalized_correction,
        jacobian_relative_disagreement=correction.jacobian_relative_disagreement,
        linear_solve_relative_disagreement=correction.linear_solve_relative_disagreement,
        detail=string(correction.detail, ",actual_steps=", steps, ",", suffix),
    )
end

function _refine_candidate_endpoint(
    runner::_CompiledAttemptRunner,
    context::ExecutionContext,
    endpoint,
    initial_image::TargetImageDiagnostic,
    oracle_work::Base.RefValue{Int},
    logical_evaluation_cost::Int;
    max_corrections::Int=3,
)
    max_corrections >= 0 || throw(ArgumentError("max_corrections must be nonnegative"))
    current = collect(Float64, endpoint)
    image = initial_image
    steps = 0
    half_options = _half_radius_target_image_options(runner.image_options)
    while true
        preliminary = _candidate_root_correction(image, runner.local_options)
        if !preliminary.resolved || isempty(preliminary.normalized_correction) ||
           preliminary.normalized_step == 0
            suffix = preliminary.resolved ? "no_correction_required" : "precheck_rejected"
            return (
                endpoint=current,
                image,
                correction=_correction_summary(preliminary, steps, suffix),
                resource_failure=TARGET_IMAGE_DIAGNOSTIC_NONE,
            )
        end
        remaining = max(
            0,
            _remaining_oracle_work(context, oracle_work[]) - logical_evaluation_cost,
        )
        half_image = analyze_target_image(
            runner.compiled,
            current;
            options=half_options,
            deadline_ns=_remaining_deadline_ns(context),
            cancelled=() -> is_cancelled(context.cancel),
            remaining_oracle_work=remaining,
        )
        oracle_work[] += half_image.oracle_work
        if half_image.failure in _ROOT_CORRECTION_RESOURCE_FAILURES
            return (
                endpoint=current,
                image,
                correction=(
                    resolved=false,
                    normalized_step=Inf,
                    target_step=Inf,
                    normalized_correction=(),
                    jacobian_relative_disagreement=Inf,
                    linear_solve_relative_disagreement=Inf,
                    detail="h_half_resource_stop",
                ),
                resource_failure=half_image.failure,
            )
        end
        correction = _candidate_root_correction(
            image,
            runner.local_options,
            half_image,
        )
        correction.resolved || return (
            endpoint=current,
            image,
            correction=_correction_summary(correction, steps, "rejected"),
            resource_failure=TARGET_IMAGE_DIAGNOSTIC_NONE,
        )
        isempty(correction.normalized_correction) && return (
            endpoint=current,
            image,
            correction=_correction_summary(correction, steps, "no_relations"),
            resource_failure=TARGET_IMAGE_DIAGNOSTIC_NONE,
        )
        correction.normalized_step <= 32 * eps(Float64) && return (
            endpoint=current,
            image,
            correction=_correction_summary(correction, steps, "step_below_roundoff"),
            resource_failure=TARGET_IMAGE_DIAGNOSTIC_NONE,
        )
        steps >= max_corrections && return (
            endpoint=current,
            image,
            correction=_correction_summary(correction, steps, "maximum_reached"),
            resource_failure=TARGET_IMAGE_DIAGNOSTIC_NONE,
        )
        trial = _corrected_endpoint(
            runner.compiled,
            current,
            correction.normalized_correction,
        )
        trial === nothing && return (
            endpoint=current,
            image,
            correction=_correction_summary(correction, steps, "trial_outside_bounds"),
            resource_failure=TARGET_IMAGE_DIAGNOSTIC_NONE,
        )
        remaining = max(
            0,
            _remaining_oracle_work(context, oracle_work[]) - logical_evaluation_cost,
        )
        trial_image = analyze_target_image(
            runner.compiled,
            trial;
            options=runner.image_options,
            deadline_ns=_remaining_deadline_ns(context),
            cancelled=() -> is_cancelled(context.cancel),
            remaining_oracle_work=remaining,
        )
        oracle_work[] += trial_image.oracle_work
        if trial_image.failure in _ROOT_CORRECTION_RESOURCE_FAILURES
            return (
                endpoint=current,
                image,
                correction=_correction_summary(correction, steps, "trial_resource_stop"),
                resource_failure=trial_image.failure,
            )
        end
        old_score = _residual_score(image.base_observation)
        new_score = _residual_score(trial_image.base_observation)
        branch_stable = _same_branch_signature(
            image.base_observation,
            trial_image.base_observation,
        )
        if !branch_stable || !isfinite(new_score) || new_score >= old_score
            suffix = !branch_stable ? "branch_changed" : "no_strict_improvement"
            return (
                endpoint=current,
                image,
                correction=_correction_summary(correction, steps, suffix),
                resource_failure=TARGET_IMAGE_DIAGNOSTIC_NONE,
            )
        end
        current = trial
        image = trial_image
        steps += 1
        new_score <= 32 * eps(Float64) && return (
            endpoint=current,
            image,
            correction=_correction_summary(correction, steps, "residual_below_roundoff"),
            resource_failure=TARGET_IMAGE_DIAGNOSTIC_NONE,
        )
    end
end

function _zero_relation_attempt(runner, proposal, evaluate_for_local)
    start = Tuple(proposal.coordinates)
    observation = evaluate_for_local(collect(start))
    accepted = canonical_feasible(
        observation;
        residual_tolerance=runner.local_options.residual_tolerance,
    )
    return LocalAttempt(
        start,
        start,
        observation,
        accepted ? LOCAL_CONVERGED : LOCAL_EVALUATION_FAILED,
        accepted,
        0,
        1,
        0,
        Inf,
        (),
    )
end

function (runner::_CompiledAttemptRunner)(
    context::ExecutionContext,
    proposal::Proposal,
)
    oracle_work = Ref(0)
    logical_evaluation_cost = runner.compiled.logical_evaluation_cost
    available_at_start = _remaining_oracle_work(context)
    local_evaluation_limit = logical_evaluation_cost == 0 ?
                             runner.local_options.max_evaluations : min(
        runner.local_options.max_evaluations,
        div(available_at_start, logical_evaluation_cost),
    )
    local_evaluation_limit > 0 || return _oracle_budget_partial_observation(proposal)
    local_options = _local_options_with_evaluation_limit(
        runner.local_options,
        local_evaluation_limit,
    )
    function evaluate_for_local(x)
        observation = evaluate(runner.compiled, x; workspace=runner.workspace)
        _check_logical_evaluation_bound(runner.compiled, observation)
        oracle_work[] += observation.evaluation_cost
        return observation
    end
    problem = runner.compiled.problem
    origins = Float64[variable.origin for variable in problem.variables]
    scales = Float64[variable.scale for variable in problem.variables]
    lower = Float64[
        variable.lower === nothing ? -Inf : variable.lower for variable in problem.variables
    ]
    upper = Float64[
        variable.upper === nothing ? Inf : variable.upper for variable in problem.variables
    ]
    attempt = if isempty(problem.relations)
        _zero_relation_attempt(runner, proposal, evaluate_for_local)
    else
        runner.local_solver(
            runner.compiled,
            evaluate_for_local,
            collect(proposal.coordinates);
            origins,
            scales,
            lower,
            upper,
            options=local_options,
            deadline_ns=_remaining_deadline_ns(context),
            cancelled=() -> is_cancelled(context.cancel),
        )
    end
    attempt isa LocalAttempt || throw(
        SolveConfigurationError(
            :invalid_research_local_result,
            "compiled-aware local solver must return LocalAttempt",
        ),
    )
    score = _residual_score(attempt.observation)
    near = _near_feasible(attempt.observation, runner.local_options.residual_tolerance)
    if !attempt.accepted || is_cancelled(context.cancel) ||
       Float64(context.clock()) >= context.deadline
        return Observation(
            proposal.task_id,
            proposal.configuration_id;
            canonical_near_feasible=near,
            target=near ? _candidate_target(attempt.observation) : nothing,
            branch_signature=Tuple(branch.decision for branch in attempt.observation.branches),
            needs_refinement=near && attempt.status ∉ (LOCAL_CANCELLED, LOCAL_DEADLINE),
            residual_score=score,
            oracle_work=oracle_work[],
            endpoint=attempt.final,
            diagnostic=_local_diagnostic(attempt),
        )
    end

    image = analyze_target_image(
        runner.compiled,
        collect(attempt.final);
        options=runner.image_options,
        deadline_ns=_remaining_deadline_ns(context),
        cancelled=() -> is_cancelled(context.cancel),
        remaining_oracle_work=max(
            0,
            _remaining_oracle_work(context, oracle_work[]) - logical_evaluation_cost,
        ),
    )
    oracle_work[] += image.oracle_work
    if image.failure in (
        TARGET_IMAGE_CANCELLED,
        TARGET_IMAGE_DEADLINE_REACHED,
        TARGET_IMAGE_ORACLE_BUDGET_EXHAUSTED,
    )
        runner.saw_inconclusive_image = true
        return Observation(
            proposal.task_id,
            proposal.configuration_id;
            canonical_near_feasible=true,
            target=_candidate_target(attempt.observation),
            branch_signature=Tuple(branch.decision for branch in attempt.observation.branches),
            needs_refinement=image.failure == TARGET_IMAGE_ORACLE_BUDGET_EXHAUSTED,
            residual_score=score,
            oracle_work=oracle_work[],
            endpoint=attempt.final,
            diagnostic=_local_diagnostic(attempt, nothing, image),
        )
    end
    refinement = _refine_candidate_endpoint(
        runner,
        context,
        collect(attempt.final),
        image,
        oracle_work,
        logical_evaluation_cost,
    )
    endpoint = refinement.endpoint
    image = refinement.image
    correction = refinement.correction
    fast_observation = image.base_observation
    score = _residual_score(fast_observation)
    if refinement.resource_failure in _ROOT_CORRECTION_RESOURCE_FAILURES
        runner.saw_inconclusive_image = true
        return Observation(
            proposal.task_id,
            proposal.configuration_id;
            canonical_near_feasible=true,
            target=_candidate_target(fast_observation),
            branch_signature=Tuple(
                branch.decision for branch in fast_observation.branches
            ),
            needs_refinement=refinement.resource_failure ==
                             TARGET_IMAGE_ORACLE_BUDGET_EXHAUSTED,
            residual_score=score,
            oracle_work=oracle_work[],
            endpoint=Tuple(endpoint),
            diagnostic=_local_diagnostic(attempt, nothing, image, correction),
        )
    end
    inconclusive_image = image.classification == TARGET_IMAGE_INCONCLUSIVE
    runner.saw_inconclusive_image |= inconclusive_image
    if !correction.resolved
        exactification = _unresolved_exactification_attempt!(
            runner,
            context,
            endpoint,
            fast_observation,
            image,
            oracle_work,
            allow_unresolved_correction=true,
        )
        if exactification.answer !== nothing
            return _exact_only_observation(
                proposal,
                oracle_work[],
                exactification.answer,
                exactification.reference_sample,
                string(
                    _local_diagnostic(attempt, nothing, image, correction),
                    ";exactification=",
                    exactification.detail,
                    ";promotion=exact_only_numerically_unresolved",
                ),
            )
        end
        return Observation(
            proposal.task_id,
            proposal.configuration_id;
            canonical_near_feasible=true,
            target=_candidate_target(fast_observation),
            branch_signature=Tuple(
                branch.decision for branch in fast_observation.branches
            ),
            needs_refinement=true,
            residual_score=score,
            oracle_work=oracle_work[],
            endpoint=Tuple(endpoint),
            diagnostic=string(
                _local_diagnostic(attempt, nothing, image, correction),
                ";exactification=",
                exactification.detail,
            ),
        )
    end
    if image.classification == TARGET_LIKELY_CONTINUOUS
        runner.saw_likely_continuous = true
        return Observation(
            proposal.task_id,
            proposal.configuration_id;
            canonical_near_feasible=true,
            target=_candidate_target(fast_observation),
            branch_signature=Tuple(
                branch.decision for branch in fast_observation.branches
            ),
            verified=false,
            needs_refinement=false,
            residual_score=score,
            oracle_work=oracle_work[],
            endpoint=Tuple(endpoint),
            diagnostic=_local_diagnostic(attempt, nothing, image, correction),
        )
    end
    validation_capacity = _remaining_oracle_work(context, oracle_work[])
    cancelled_before_validation = is_cancelled(context.cancel)
    deadline_before_validation = Float64(context.clock()) >= context.deadline
    if cancelled_before_validation || deadline_before_validation
        runner.saw_inconclusive_image = true
        resource = if cancelled_before_validation
            "cancelled_before_canonical_validation"
        else
            "deadline_before_canonical_validation"
        end
        return Observation(
            proposal.task_id,
            proposal.configuration_id;
            canonical_near_feasible=true,
            target=_candidate_target(fast_observation),
            branch_signature=Tuple(
                branch.decision for branch in fast_observation.branches
            ),
            needs_refinement=false,
            residual_score=score,
            oracle_work=oracle_work[],
            endpoint=Tuple(endpoint),
            diagnostic=string(
                _local_diagnostic(attempt, nothing, image, correction),
                ';',
                resource,
            ),
        )
    end
    validation = validate_candidate(
        runner.compiled,
        endpoint;
        options=runner.validation_options,
        fast_observation,
        deadline_ns=_remaining_deadline_ns(context),
        cancelled=() -> is_cancelled(context.cancel),
        remaining_oracle_work=validation_capacity,
    )
    _check_logical_evaluation_bound(runner.compiled, validation.canonical_observation)
    oracle_work[] = Base.checked_add(oracle_work[], validation.oracle_work)
    if !validation.accepted
        exactification = _unresolved_exactification_attempt!(
            runner,
            context,
            endpoint,
            fast_observation,
            image,
            oracle_work,
        )
        if exactification.answer !== nothing
            return _exact_only_observation(
                proposal,
                oracle_work[],
                exactification.answer,
                exactification.reference_sample,
                string(
                    _local_diagnostic(attempt, validation, image, correction),
                    ";exactification=",
                    exactification.detail,
                    ";promotion=exact_only_numerically_unresolved",
                ),
            )
        end
        retryable = validation.failure ∉ (
            CANDIDATE_HIGH_PRECISION_CAPABILITY_MISSING,
            CANDIDATE_HIGH_PRECISION_DOWNGRADE,
            CANDIDATE_VALIDATION_CANCELLED,
            CANDIDATE_VALIDATION_DEADLINE_REACHED,
            CANDIDATE_VALIDATION_ORACLE_BUDGET_EXHAUSTED,
        )
        return Observation(
            proposal.task_id,
            proposal.configuration_id;
            canonical_near_feasible=true,
            target=_candidate_target(fast_observation),
            branch_signature=Tuple(
                branch.decision for branch in fast_observation.branches
            ),
            needs_refinement=retryable,
            residual_score=score,
            oracle_work=oracle_work[],
            endpoint=validation.canonical_coordinates,
            diagnostic=string(
                _local_diagnostic(attempt, validation, image, correction),
                ";exactification=",
                exactification.detail,
            ),
        )
    end

    confirmed_endpoint = validation.canonical_coordinates

    provisional = validation.provisional::ProvisionalAnswer
    target = _validation_target(validation)
    target === nothing && throw(
        SolveConfigurationError(
            :missing_validated_target,
            "accepted candidate validation did not carry a target enclosure",
        ),
    )
    if inconclusive_image
        return Observation(
            proposal.task_id,
            proposal.configuration_id;
            canonical_near_feasible=true,
            canonical_valid=true,
            target,
            branch_signature=provisional.branch_signature,
            verified=false,
            needs_refinement=true,
            residual_score=Float64(provisional.canonical_residual_bound),
            oracle_work=oracle_work[],
            endpoint=confirmed_endpoint,
            diagnostic=_local_diagnostic(attempt, validation, image, correction),
        )
    end
    exactification = _attempt_exactification!(runner, context, validation, oracle_work)
    if exactification.answer !== nothing
        return _exact_only_observation(
            proposal,
            oracle_work[],
            exactification.answer,
            exactification.reference_sample,
            string(
                _local_diagnostic(attempt, validation, image, correction),
                ";exactification=",
                exactification.detail,
                ";promotion=exact_regular",
            ),
        )
    end
    provisional = _provisional_after_exactification(provisional, exactification)
    return Observation(
        proposal.task_id,
        proposal.configuration_id;
        canonical_near_feasible=true,
        canonical_valid=true,
        target,
        target_identity="provisional-configuration/$(string(validation.configuration))",
        branch_signature=provisional.branch_signature,
        verified=true,
        verified_payload=provisional,
        needs_refinement=false,
        residual_score=Float64(provisional.canonical_residual_bound),
        oracle_work=oracle_work[],
        endpoint=confirmed_endpoint,
        diagnostic=string(
            _local_diagnostic(attempt, validation, image, correction),
            ";exactification=",
            exactification.detail,
            ";promotion=",
            "validated_numerical",
        ),
    )
end

function _solve_exact_backend_descriptor(backend::AbstractExactBackend)
    descriptor = try
        exact_backend_descriptor(backend)
    catch error
        error isa InterruptException && rethrow()
        throw(
            SolveConfigurationError(
                :exact_backend_descriptor_failed,
                "exact backend descriptor failed: $(sprint(showerror, error))",
            ),
        )
    end
    descriptor isa ExactBackendDescriptor || throw(
        SolveConfigurationError(
            :invalid_exact_backend_descriptor,
            "exact backend descriptor returned $(typeof(descriptor))",
        ),
    )
    return descriptor
end

function _same_exact_backend_descriptor(
    left::ExactBackendDescriptor,
    right::ExactBackendDescriptor,
)
    return left.id == right.id &&
           left.version == right.version &&
           left.method == right.method &&
           left.backend_abi_version == right.backend_abi_version &&
           left.configuration_certificate_schemes == right.configuration_certificate_schemes &&
           left.target_certificate_schemes == right.target_certificate_schemes &&
           left.policy_identity == right.policy_identity &&
           left.environment_identity == right.environment_identity
end

function _exact_backend_policy_document(descriptor::ExactBackendDescriptor)
    return Dict{String,Any}(
        "backend_abi_version" => string(descriptor.backend_abi_version),
        "configuration_certificate_schemes" =>
            Any[descriptor.configuration_certificate_schemes...],
        "id" => descriptor.id,
        "method" => descriptor.method,
        "policy_identity" => string(descriptor.policy_identity),
        "target_certificate_schemes" => Any[descriptor.target_certificate_schemes...],
        "version" => string(descriptor.version),
    )
end

function _exact_backend_environment_document(descriptor::ExactBackendDescriptor)
    return Dict{String,Any}(
        "backend_abi_version" => string(descriptor.backend_abi_version),
        "environment_identity" => string(descriptor.environment_identity),
        "id" => descriptor.id,
        "version" => string(descriptor.version),
    )
end

function _solve_policy_document(
    options::SolveOptions,
    research_strategy::Union{Nothing,UnstableResearchStrategy}=nothing,
    exact_descriptor::Union{Nothing,ExactBackendDescriptor}=nothing,
)
    limits = options.policy.budget_limits
    local_fields = Dict{String,Any}(
        String(name) => getfield(options._local, name) for
        name in fieldnames(LocalSolveOptions)
    )
    document = Dict{String,Any}(
        "answer_level" => string(options.answer_level),
        "budget_limits" => Dict{String,Any}(
            "local_attempts" => limits.local_attempts,
            "oracle_work" => limits.oracle_work,
            "proposals" => limits.proposals,
            "refinements" => limits.refinements,
        ),
        "local" => local_fields,
        "policy_version" => string(options.policy.version),
        "preset" => string(options.preset),
        "proposal_engine_version" => string(PROPOSAL_ENGINE_VERSION),
        "seed" => string(options.seed),
        "solve_api_version" => string(options.version),
        "target_image" => _target_image_options_document(_solve_target_image_options(options)),
        "validation" => _validation_options_document(options._validation),
        "wall_seconds" => options.wall_seconds,
        "worker_count" => options.worker_count,
    )
    research_strategy === nothing ||
        (document["unstable_research_strategy_id"] = research_strategy.id)
    exact_descriptor === nothing ||
        (document["exact_backend"] = _exact_backend_policy_document(exact_descriptor))
    return document
end

_solve_target_image_options(options::SolveOptions) = TargetImageDiagnosticOptions(
    relation_tolerance=options._local.residual_tolerance,
)

function _target_image_options_document(options::TargetImageDiagnosticOptions)
    return Dict{String,Any}(
        "branch_margin_tolerance" => options.branch_margin_tolerance,
        "capability" => string(options.capability),
        "finite_difference_radius" => options.finite_difference_radius,
        "precision_bits" => options.precision_bits,
        "probe_radii" => Any[options.probe_radii...],
        "probe_target_tolerance" => options.probe_target_tolerance,
        "rank_absolute_tolerance" => options.rank_absolute_tolerance,
        "rank_relative_tolerance" => options.rank_relative_tolerance,
        "relation_tolerance" => options.relation_tolerance,
        "target_sensitivity_tolerance" => options.target_sensitivity_tolerance,
    )
end

function _solve_environment_document(
    compiled::CompiledProblem,
    exact_descriptor::Union{Nothing,ExactBackendDescriptor}=nothing,
)
    document = Dict{String,Any}(
        "architecture" => Sys.MACHINE,
        "blas" => sprint(show, LinearAlgebra.BLAS.get_config()),
        "compiled_backend" => compiled.cache_identity.numeric_backend,
        "compiled_cache_persistent" => compiled.cache_identity.persistent,
        "core_abi" => string(CORE_ABI_VERSION),
        "julia_threads" => Base.Threads.nthreads(),
        "julia_version" => string(VERSION),
        "word_size" => Sys.WORD_SIZE,
    )
    exact_descriptor === nothing ||
        (document["exact_backend"] = _exact_backend_environment_document(exact_descriptor))
    return document
end

function _solve_resume_identity(
    compiled::CompiledProblem,
    options::SolveOptions,
    research_strategy::Union{Nothing,UnstableResearchStrategy}=nothing,
    exact_descriptor::Union{Nothing,ExactBackendDescriptor}=nothing,
)
    problem_digest, _ = _candidate_problem_identity(compiled)
    return ResumeIdentity(
        problem_digest,
        compiled.problem.plugin_locks,
        canonical_json_hash(
            _solve_policy_document(options, research_strategy, exact_descriptor),
        ),
        canonical_json_hash(_solve_environment_document(compiled, exact_descriptor)),
    )
end

function _evidence_value(value)
    if value === nothing || value isa Bool || value isa AbstractString
        return value
    elseif value isa Symbol || value isa Enum || value isa VersionNumber ||
           value isa ContentHash || value isa PluginId || value isa TypeId ||
           value isa PrimitiveId || value isa SelectorId || value isa NodeId ||
           value isa VariableId || value isa ChoiceKey
        return string(value)
    elseif value isa Integer
        return abs(BigInt(value)) <= 9_007_199_254_740_991 ? Int64(value) : string(value)
    elseif value isa Union{Float16,Float32,Float64}
        isfinite(value) || return string(value)
        return Float64(value)
    elseif value isa Real
        return Dict{String,Any}("type" => string(typeof(value)), "value" => string(value))
    elseif value isa Pair
        return Dict{String,Any}("first" => _evidence_value(first(value)), "second" => _evidence_value(last(value)))
    elseif value isa NamedTuple
        return Dict{String,Any}(
            String(name) => _evidence_value(getfield(value, name)) for name in keys(value)
        )
    elseif value isa AbstractDict
        return Dict{String,Any}(string(key) => _evidence_value(entry) for (key, entry) in value)
    elseif value isa Tuple || value isa AbstractVector
        return Any[_evidence_value(entry) for entry in value]
    elseif isstructtype(typeof(value))
        document = Dict{String,Any}("type" => string(typeof(value)))
        for name in fieldnames(typeof(value))
            document[String(name)] = _evidence_value(getfield(value, name))
        end
        return document
    end
    throw(
        SolveConfigurationError(
            :unsupported_evidence_value,
            "cannot serialize evidence value $(typeof(value))",
        ),
    )
end

function _evidence_json(context::ExecutionContext)
    document = Dict{String,Any}(
        "events" => Any[
            Dict{String,Any}(
                "kind" => string(event.kind),
                "payload" => _evidence_value(event.payload),
                "sequence" => event.sequence,
            ) for event in evidence_events(context.events)
        ],
        "resume_identity" => _evidence_value(context.resume_identity),
        "schema" => "geotarget.evidence-log/v1",
    )
    return canonical_json(document)
end

function _write_evidence(path::AbstractString, evidence::String)
    destination = abspath(String(path))
    mkpath(dirname(destination))
    temporary = string(destination, ".tmp-", getpid(), '-', time_ns())
    try
        open(temporary, "w") do io
            write(io, evidence)
        end
        mv(temporary, destination; force=true)
    finally
        isfile(temporary) && rm(temporary; force=true)
    end
    return destination
end

function _loop_search_status(status::SearchLoopStatus)
    status === LOOP_DEADLINE_REACHED && return SEARCH_DEADLINE_REACHED
    status === LOOP_CANCELLED && return SEARCH_CANCELLED
    status === LOOP_BUDGET_EXHAUSTED && return SEARCH_RESOURCE_EXHAUSTED
    return SEARCH_FINISHED_UNKNOWN
end

function _coverage(context::ExecutionContext)
    proposed = context.budget.proposals
    completed = length(candidate_records(context.workspace.candidates))
    pending = length(context.workspace.pending)
    shells = sort!(unique(Int[
        record.proposal.shell for record in candidate_records(context.workspace.candidates) if
        record.proposal.shell !== nothing
    ]))
    iid = context.workspace.scheduler.served[_lane_index(LANE_IID)]
    return CoverageEvidence(
        iid,
        proposed,
        completed,
        pending;
        explored_shells=shells,
    )
end

function _provisional_answers(store::CandidateStore)
    answers = ProvisionalAnswer[]
    for verified in verified_answers(store), payload in verified.payloads
        payload isa ProvisionalAnswer && push!(answers, payload)
    end
    return Tuple(answers)
end

function _exact_answers(store::CandidateStore)
    answers = ExactAnswer[]
    for verified in verified_answers(store), payload in verified.payloads
        payload isa ExactAnswer && push!(answers, payload)
    end
    return Tuple(answers)
end

function _verify_solver_exact_answer(
    compiled::CompiledProblem,
    answer::ExactAnswer,
    exact_backend::Union{Nothing,AbstractExactBackend},
    ;
    observation::Union{Nothing,StoredExactObservation}=nothing,
    checkpoint=() -> nothing,
)
    checkpoint()
    builtin = verify_exact_answer(compiled, answer)
    checkpoint()
    builtin.accepted && return builtin
    builtin.failure == EXACT_VERIFICATION_UNSUPPORTED_SCHEME || return builtin
    exact_backend === nothing && return builtin
    verification = try
        verify_stored_exact_answer(
            exact_backend,
            compiled,
            answer;
            observation,
            checkpoint,
        )
    catch error
        error isa InterruptException && rethrow()
        throw(
            SolveConfigurationError(
                :exact_certificate_replay_failed,
                "stored exact backend verifier raised an exception: $(sprint(showerror, error))",
            ),
        )
    end
    verification isa ExactVerificationResult || throw(
        SolveConfigurationError(
            :invalid_exact_backend_verifier,
            "stored exact backend verifier returned $(typeof(verification))",
        ),
    )
    return verification
end

function _solver_exact_verification_checkpoint(context::ExecutionContext)
    is_cancelled(context.cancel) && throw(
        SolveConfigurationError(
            :stored_exact_verification_cancelled,
            "stored exact-answer verification was cancelled",
        ),
    )
    Float64(context.clock()) < context.deadline || throw(
        SolveConfigurationError(
            :stored_exact_verification_deadline,
            "stored exact-answer verification reached the solve deadline",
        ),
    )
    return nothing
end

function _verify_exact_store!(
    context::ExecutionContext,
    compiled::CompiledProblem,
    exact_backend::Union{Nothing,AbstractExactBackend},
)
    checkpoint = () -> _solver_exact_verification_checkpoint(context)
    for record in candidate_records(context.workspace.candidates)
        stored = record.observation
        answer = stored.verified_payload
        answer isa ExactAnswer || continue
        expected_identity = _exact_target_identity(answer)
        stored.verified && stored.canonical_valid || throw(
            SolveConfigurationError(
                :exact_observation_binding_failed,
                "stored exact answer is not attached to a canonically valid observation",
            ),
        )
        stored.target !== nothing || throw(
            SolveConfigurationError(
                :exact_observation_binding_failed,
                "stored exact answer has no target enclosure",
            ),
        )
        stored.target_identity == expected_identity || throw(
            SolveConfigurationError(
                :exact_observation_binding_failed,
                "stored exact target identity differs from its certificate identity",
            ),
        )
        stored.branch_signature == answer.branch_signature || throw(
            SolveConfigurationError(
                :exact_observation_binding_failed,
                "stored exact branch signature differs from its certified branch",
            ),
        )
        stored.endpoint !== nothing || throw(
            SolveConfigurationError(
                :exact_observation_binding_failed,
                "stored exact answer has no endpoint evidence",
            ),
        )
        stored.needs_refinement && throw(
            SolveConfigurationError(
                :exact_observation_binding_failed,
                "stored exact answer is still marked as needing refinement",
            ),
        )
        length(stored.endpoint) == length(compiled.variables) || throw(
            SolveConfigurationError(
                :exact_observation_binding_failed,
                "stored exact endpoint dimension differs from the compiled problem",
            ),
        )
        all(zip(stored.endpoint, compiled.variables)) do (value, variable)
            (variable.spec.lower === nothing || value >= variable.spec.lower) &&
                (variable.spec.upper === nothing || value <= variable.spec.upper)
        end || throw(
            SolveConfigurationError(
                :exact_observation_binding_failed,
                "stored exact endpoint lies outside the declared variable bounds",
            ),
        )
        approximation_contained, target_radius_valid = try
            setprecision(BigFloat, 768) do
                approximation = answer.approximation isa BigFloat ?
                                BigFloat(answer.approximation) :
                                parse(BigFloat, string(answer.approximation))
                lower = BigFloat(stored.target.lower)
                upper = BigFloat(stored.target.upper)
                scale = max(one(BigFloat), abs(approximation))
                tolerance = parse(BigFloat, "1e-100") + ldexp(one(BigFloat), -700)
                (
                    lower <= approximation <= upper,
                    max(abs(lower - approximation), abs(upper - approximation)) / scale <=
                    tolerance,
                )
            end
        catch error
            error isa ArgumentError || rethrow()
            (false, false)
        end
        approximation_contained || throw(
            SolveConfigurationError(
                :exact_observation_binding_failed,
                "stored exact target enclosure excludes the answer approximation",
            ),
        )
        target_radius_valid || throw(
            SolveConfigurationError(
                :exact_observation_binding_failed,
                "stored exact target enclosure is wider than the 100-digit answer gate",
            ),
        )
        binding = StoredExactObservation(
            stored.target.lower,
            stored.target.upper,
            expected_identity,
            stored.branch_signature,
            stored.endpoint,
        )
        verification = _verify_solver_exact_answer(
            compiled,
            answer,
            exact_backend;
            observation=binding,
            checkpoint,
        )
        verification.accepted || throw(
            SolveConfigurationError(
                :exact_certificate_replay_failed,
                "stored exact answer failed independent replay: $(verification.failure): $(verification.detail)",
            ),
        )
    end
    return nothing
end

function _finish_execution(
    context::ExecutionContext,
    search::SearchLoopResult;
    compiled::CompiledProblem,
    exact_backend::Union{Nothing,AbstractExactBackend}=nothing,
    verify_exact_store::Bool=true,
    evidence_path::Union{Nothing,AbstractString}=nothing,
    target_image_override::Union{Nothing,TargetImageStatus}=nothing,
)
    provisional = _provisional_answers(context.workspace.candidates)
    exact = _exact_answers(context.workspace.candidates)
    verify_exact_store && _verify_exact_store!(context, compiled, exact_backend)
    evidence = _evidence_json(context)
    digest = content_hash(evidence)
    location = evidence_path === nothing ?
               "memory:$(string(digest))" : _write_evidence(evidence_path, evidence)
    target_status = if target_image_override !== nothing
        target_image_override
    else
        isempty(provisional) && isempty(exact) ? TARGET_IMAGE_UNKNOWN : TARGET_FINITE_OBSERVED
    end
    result = SolveResult(
        exact,
        provisional,
        _loop_search_status(search.status),
        target_status,
        _coverage(context),
        context.resume_identity,
        EvidenceLogReference(digest, location),
    )
    return SolveExecution(result, evidence, search.checkpoint, search.status)
end

function _literal_target_node(problem::ProblemSpecV1)
    for node in problem.graph
        node.id == problem.target || continue
        return node isa LiteralNode ? node : nothing
    end
    return nothing
end

function _exact_literal_rational(value)
    value isa Bool && return nothing
    value isa Real && isfinite(value) || return nothing
    return try
        Rational{BigInt}(value)
    catch error
        error isa Union{ArgumentError,InexactError,MethodError,OverflowError} || rethrow()
        nothing
    end
end

function _rational_certificate_document(value::Rational{BigInt})
    return Dict{String,Any}(
        "denominator" => string(denominator(value)),
        "numerator" => string(numerator(value)),
    )
end

const _LITERAL_CONFIGURATION_CERTIFICATE_SCHEME = "literal_configuration_v1"
const _LITERAL_CONFIGURATION_CERTIFICATE_SCHEMA =
    "geotarget.literal-configuration-certificate/v1"
const _LITERAL_TARGET_CERTIFICATE_SCHEME = "literal_linear_target_v1"
const _LITERAL_TARGET_CERTIFICATE_SCHEMA =
    "geotarget.literal-linear-target-certificate/v1"

function _exact_constant_answer(
    compiled::CompiledProblem,
    validation::CandidateValidationResult,
    options::SolveOptions,
)
    options.answer_level == ANSWER_EXACT_IF_AVAILABLE || return nothing
    isempty(compiled.problem.variables) || return nothing
    isempty(compiled.problem.relations) || return nothing
    isempty(compiled.problem.guards) || return nothing
    isempty(compiled.problem.domains) || return nothing
    isempty(validation.canonical_observation.branches) || return nothing
    literal = _literal_target_node(compiled.problem)
    literal === nothing && return nothing
    rational = _exact_literal_rational(literal.value)
    rational === nothing && return nothing

    numerator_value = numerator(rational)
    denominator_value = denominator(rational)
    lower = rational - 1
    upper = rational + 1
    identity = AlgebraicTargetIdentity(
        (-numerator_value, denominator_value),
        RationalInterval(lower, upper),
        1,
    )
    configuration_payload = canonical_json(Dict{String,Any}(
        "configuration" => string(validation.configuration),
        "constraint_count" => 0,
        "problem" => string(validation.problem),
        "schema" => _LITERAL_CONFIGURATION_CERTIFICATE_SCHEMA,
    ))
    target_payload = canonical_json(Dict{String,Any}(
        "isolating_interval" => Dict{String,Any}(
            "lower" => _rational_certificate_document(lower),
            "upper" => _rational_certificate_document(upper),
        ),
        "polynomial_ascending" => Any[string(-numerator_value), string(denominator_value)],
        "problem" => string(validation.problem),
        "real_root_index" => 1,
        "schema" => _LITERAL_TARGET_CERTIFICATE_SCHEMA,
        "target" => _rational_certificate_document(rational),
    ))
    configuration_certificate = ConfigurationValidityCertificate(
        validation.problem,
        validation.configuration,
        CertificateArtifact(
            _LITERAL_CONFIGURATION_CERTIFICATE_SCHEME,
            configuration_payload;
            media_type="application/json",
        ),
    )
    target_certificate = TargetIdentityCertificate(
        validation.problem,
        identity,
        CertificateArtifact(
            _LITERAL_TARGET_CERTIFICATE_SCHEME,
            target_payload;
            media_type="application/json",
        ),
    )
    return ExactAnswer(
        identity,
        setprecision(BigFloat, 768) do
            BigFloat(numerator_value) / BigFloat(denominator_value)
        end,
        (),
        configuration_certificate,
        target_certificate,
    )
end

function _constant_search!(
    context::ExecutionContext,
    compiled::CompiledProblem,
    options::SolveOptions,
)
    if is_cancelled(context.cancel)
        return _finish_search(context, LOOP_CANCELLED)
    end
    if Float64(context.clock()) >= context.deadline
        return _finish_search(context, LOOP_DEADLINE_REACHED)
    end
    decision = ScheduleDecision(LANE_IID, 1)
    proposal = Proposal(1, 1, LANE_IID, ())
    record_event!(context.events, EVENT_SCHEDULED, decision)
    enqueue_proposal!(context.workspace, proposal)
    _record_charge!(context, BudgetCharge(proposals=1))
    record_event!(context.events, EVENT_PROPOSED, proposal)
    validation = validate_candidate(
        compiled,
        Real[];
        options=options._validation,
        deadline_ns=_remaining_deadline_ns(context),
        cancelled=() -> is_cancelled(context.cancel),
        remaining_oracle_work=_remaining_oracle_work(context),
    )
    exact = validation.accepted ? _exact_constant_answer(compiled, validation, options) : nothing
    exact_verification = exact === nothing ? nothing : verify_exact_answer(compiled, exact)
    if exact_verification !== nothing && !exact_verification.accepted
        exact = nothing
    end
    payload = exact === nothing ? validation.provisional : exact
    target = validation.accepted ? _validation_target(validation) : nothing
    target_identity = if !validation.accepted
        nothing
    elseif exact === nothing
        "constant/$(string(validation.configuration))"
    else
        "exact/$(string(exact.target_certificate.identity))"
    end
    observation = Observation(
        1,
        1;
        canonical_near_feasible=validation.accepted,
        canonical_valid=validation.accepted,
        target,
        target_identity,
        branch_signature=validation.accepted ? validation.provisional.branch_signature : (),
        verified=validation.accepted,
        verified_payload=validation.accepted ? payload : nothing,
        residual_score=validation.accepted ? Float64(validation.provisional.canonical_residual_bound) : Inf,
        oracle_work=validation.oracle_work,
        endpoint=(),
        diagnostic=validation.accepted ? string(
            "constant canonical validation;exact_verification=",
            exact_verification === nothing ?
            "not_requested" : exact_verification.accepted ?
            "accepted" : string("rejected:", exact_verification.failure),
        ) : string(validation.failure),
    )
    _record_charge!(context, BudgetCharge(oracle_work=validation.oracle_work))
    insert_candidate!(context.workspace.candidates, proposal, observation)
    popfirst!(context.workspace.pending)
    record_event!(context.events, EVENT_OBSERVED, observation)
    return _finish_search(context, LOOP_PAUSED; detail="constant problem evaluated once")
end

function solve_execution(
    problem::ProblemSpecV1,
    registry::FrozenPluginRegistry;
    options::SolveOptions=SolveOptions(),
    cancel::CancellationToken=CancellationToken(),
    evidence_path::Union{Nothing,AbstractString}=nothing,
    max_actions::Integer=typemax(Int),
    checkpoint::Union{Nothing,SolveCheckpointArtifact}=nothing,
    research_strategy::Union{Nothing,UnstableResearchStrategy}=nothing,
    exact_backend::Union{Nothing,AbstractExactBackend}=nothing,
)
    options.worker_count == 1 || throw(
        SolveConfigurationError(
            :parallel_execution_unavailable,
            "worker_count > 1 is not available in the deterministic v1 execution path",
        ),
    )
    max_actions >= 0 || throw(ArgumentError("max_actions must be nonnegative"))
    research_strategy !== nothing && checkpoint !== nothing && throw(
        SolveConfigurationError(
            :research_strategy_checkpoint_unsupported,
            "unstable research strategies cannot resume from a checkpoint",
        ),
    )
    started = time()
    deadline = started + options.wall_seconds
    effective_exact_backend = options.answer_level == ANSWER_EXACT_IF_AVAILABLE ?
                              exact_backend : nothing
    exact_descriptor = effective_exact_backend === nothing ?
                       nothing : _solve_exact_backend_descriptor(effective_exact_backend)
    compiled = compile_problem(problem, registry; numeric_backend="Float64")
    resume = _solve_resume_identity(
        compiled,
        options,
        research_strategy,
        exact_descriptor,
    )
    now = time()
    context = if checkpoint === nothing
        # Pass a duration instead of an absolute deadline.  A zero (or nearly
        # exhausted) budget can otherwise become stale between `now` above and
        # the clock read inside `ExecutionContext`, which made immediate-
        # deadline solves platform/clock-resolution dependent.
        remaining = max(0.0, deadline - now)
        workspace = SearchWorkspace(
            adaptive_unbounded=any(
                variable -> variable.lower === nothing || variable.upper === nothing,
                problem.variables,
            ),
        )
        ExecutionContext(
            resume;
            rng=(seed=options.seed,),
            registry,
            precision_bits=options._validation.precision_bits,
            policy=options.policy,
            workspace,
            cancel,
            clock=time,
            remaining_seconds=remaining,
            rng_checkpoint=Base.identity,
        )
    else
        checkpoint.snapshot.rng_state == (seed=options.seed,) || throw(
            SolveConfigurationError(
                :checkpoint_seed_mismatch,
                "checkpoint RNG seed does not match SolveOptions",
            ),
        )
        elapsed = max(0.0, now - started)
        remaining = max(0.0, checkpoint.snapshot.remaining_seconds - elapsed)
        snapshot = CheckpointSnapshot(
            checkpoint.snapshot.resume_identity,
            checkpoint.snapshot.policy_version,
            checkpoint.snapshot.budget,
            checkpoint.snapshot.workspace,
            checkpoint.snapshot.events,
            checkpoint.snapshot.rng_state,
            checkpoint.snapshot.precision_bits,
            remaining,
            checkpoint.snapshot.cancelled,
        )
        restore_execution_context(
            snapshot,
            resume;
            registry,
            policy=options.policy,
            rng_restore=Base.identity,
            rng_checkpoint=Base.identity,
            cancel,
            clock=time,
        )
    end
    checkpoint === nothing || _verify_exact_store!(
        context,
        compiled,
        effective_exact_backend,
    )
    target_image_override = if checkpoint === nothing
        nothing
    elseif checkpoint.target_image_status == TARGET_LIKELY_CONTINUOUS
        TARGET_LIKELY_CONTINUOUS
    elseif _checkpoint_saw_inconclusive_image(checkpoint)
        TARGET_IMAGE_UNKNOWN
    else
        nothing
    end
    search = if Float64(context.clock()) >= context.deadline
        _finish_search(context, LOOP_DEADLINE_REACHED; detail="compile consumed wall budget")
    elseif isempty(problem.variables) && checkpoint === nothing
        _constant_search!(context, compiled, options)
    elseif isempty(problem.variables)
        _finish_search(context, LOOP_PAUSED; detail="constant problem was already evaluated")
    else
        proposal_factory = research_strategy === nothing ?
                           _default_proposal_factory : research_strategy.proposal_factory
        local_solver = research_strategy === nothing ?
                       _default_compiled_local_solver : research_strategy.local_solver
        engine = proposal_factory(compiled, options)
        runner = _CompiledAttemptRunner(
            compiled,
            CompiledWorkspace(compiled),
            options._local,
            options._validation,
            _solve_target_image_options(options),
            local_solver,
            effective_exact_backend,
            exact_descriptor,
            options.answer_level,
            target_image_override == TARGET_LIKELY_CONTINUOUS,
            target_image_override == TARGET_IMAGE_UNKNOWN,
        )
        loop_result = run_search!(context, engine, runner; max_actions)
        if runner.saw_likely_continuous
            target_image_override = TARGET_LIKELY_CONTINUOUS
        elseif runner.saw_inconclusive_image
            target_image_override = TARGET_IMAGE_UNKNOWN
        end
        loop_result
    end
    return _finish_execution(
        context,
        search;
        compiled,
        exact_backend=effective_exact_backend,
        verify_exact_store=false,
        evidence_path,
        target_image_override,
    )
end

function solve(
    problem::ProblemSpecV1,
    registry::FrozenPluginRegistry;
    options::SolveOptions=SolveOptions(),
    cancel::CancellationToken=CancellationToken(),
    evidence_path::Union{Nothing,AbstractString}=nothing,
    checkpoint::Union{Nothing,SolveCheckpointArtifact}=nothing,
    exact_backend::Union{Nothing,AbstractExactBackend}=nothing,
)
    return solve_execution(
        problem,
        registry;
        options,
        cancel,
        evidence_path,
        checkpoint,
        exact_backend,
    ).result
end
