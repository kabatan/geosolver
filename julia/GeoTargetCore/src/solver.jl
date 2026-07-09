const SOLVE_API_VERSION = v"1.0.0"

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
    local_options = LocalSolveOptions(residual_tolerance=validation.residual_tolerance)
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

"""A result plus its in-memory replay evidence and resumable search snapshot."""
struct SolveExecution
    result::SolveResult
    evidence_json::String
    checkpoint::CheckpointSnapshot
    loop_status::SearchLoopStatus
end

mutable struct _CompiledAttemptRunner
    compiled::CompiledProblem
    workspace::CompiledWorkspace
    local_options::LocalSolveOptions
    validation_options::CandidateValidationOptions
end

function _remaining_deadline_ns(context::ExecutionContext)
    remaining = max(0.0, context.deadline - Float64(context.clock()))
    now = time_ns()
    remaining >= Float64(typemax(UInt64) - now) / 1.0e9 && return typemax(UInt64)
    addition = UInt64(clamp(floor(remaining * 1.0e9), 0, typemax(UInt64) - now))
    return now + addition
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

function _local_diagnostic(attempt, validation=nothing)
    validation_text = validation === nothing ? "not_run" : string(validation.failure)
    return join(
        (
            "local_status=$(attempt.status)",
            "iterations=$(attempt.iterations)",
            "evaluations=$(attempt.evaluations)",
            "rank=$(attempt.numerical_rank)",
            "condition=$(attempt.condition_estimate)",
            "validation=$validation_text",
        ),
        ';',
    )
end

function (runner::_CompiledAttemptRunner)(
    context::ExecutionContext,
    proposal::Proposal,
)
    oracle_work = Ref(0)
    function evaluate_for_local(x)
        observation = evaluate(runner.compiled, x; workspace=runner.workspace)
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
    attempt = solve_local(
        evaluate_for_local,
        collect(proposal.coordinates);
        origins,
        scales,
        lower,
        upper,
        options=runner.local_options,
        deadline_ns=_remaining_deadline_ns(context),
        cancelled=() -> is_cancelled(context.cancel),
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

    validation = validate_candidate(
        runner.compiled,
        attempt;
        options=runner.validation_options,
    )
    oracle_work[] += validation.oracle_work
    if !validation.accepted
        return Observation(
            proposal.task_id,
            proposal.configuration_id;
            canonical_near_feasible=true,
            target=_candidate_target(attempt.observation),
            branch_signature=Tuple(branch.decision for branch in attempt.observation.branches),
            needs_refinement=true,
            residual_score=score,
            oracle_work=oracle_work[],
            endpoint=attempt.final,
            diagnostic=_local_diagnostic(attempt, validation),
        )
    end

    provisional = validation.provisional::ProvisionalAnswer
    target = _validation_target(validation)
    target === nothing && throw(
        SolveConfigurationError(
            :missing_validated_target,
            "accepted candidate validation did not carry a target enclosure",
        ),
    )
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
        endpoint=attempt.final,
        diagnostic=_local_diagnostic(attempt, validation),
    )
end

function _solve_policy_document(options::SolveOptions)
    limits = options.policy.budget_limits
    local_fields = Dict{String,Any}(
        String(name) => getfield(options._local, name) for
        name in fieldnames(LocalSolveOptions)
    )
    return Dict{String,Any}(
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
        "validation" => _validation_options_document(options._validation),
        "wall_seconds" => options.wall_seconds,
        "worker_count" => options.worker_count,
    )
end

function _solve_environment_document(compiled::CompiledProblem)
    return Dict{String,Any}(
        "architecture" => Sys.MACHINE,
        "blas" => sprint(show, LinearAlgebra.BLAS.get_config()),
        "compiled_backend" => compiled.cache_identity.numeric_backend,
        "compiled_cache_persistent" => compiled.cache_identity.persistent,
        "core_abi" => string(CORE_ABI_VERSION),
        "julia_threads" => Base.Threads.nthreads(),
        "julia_version" => string(VERSION),
        "word_size" => Sys.WORD_SIZE,
    )
end

function _solve_resume_identity(compiled::CompiledProblem, options::SolveOptions)
    problem_digest, _ = _candidate_problem_identity(compiled)
    return ResumeIdentity(
        problem_digest,
        compiled.problem.plugin_locks,
        canonical_json_hash(_solve_policy_document(options)),
        canonical_json_hash(_solve_environment_document(compiled)),
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

function _finish_execution(
    context::ExecutionContext,
    search::SearchLoopResult;
    evidence_path::Union{Nothing,AbstractString}=nothing,
)
    evidence = _evidence_json(context)
    digest = content_hash(evidence)
    location = evidence_path === nothing ?
               "memory:$(string(digest))" : _write_evidence(evidence_path, evidence)
    provisional = _provisional_answers(context.workspace.candidates)
    target_status = isempty(provisional) ? TARGET_IMAGE_UNKNOWN : TARGET_FINITE_OBSERVED
    result = SolveResult(
        (),
        provisional,
        _loop_search_status(search.status),
        target_status,
        _coverage(context),
        context.resume_identity,
        EvidenceLogReference(digest, location),
    )
    return SolveExecution(result, evidence, search.checkpoint, search.status)
end

function _constant_search!(context, compiled, options)
    if Float64(context.clock()) >= context.deadline
        return _finish_search(context, LOOP_DEADLINE_REACHED)
    end
    decision = ScheduleDecision(LANE_IID, 1)
    proposal = Proposal(1, 1, LANE_IID, ())
    record_event!(context.events, EVENT_SCHEDULED, decision)
    enqueue_proposal!(context.workspace, proposal)
    _record_charge!(context, BudgetCharge(proposals=1))
    record_event!(context.events, EVENT_PROPOSED, proposal)
    validation = validate_candidate(compiled, Real[]; options=options._validation)
    target = validation.accepted ? _validation_target(validation) : nothing
    observation = Observation(
        1,
        1;
        canonical_near_feasible=validation.accepted,
        canonical_valid=validation.accepted,
        target,
        target_identity=validation.accepted ?
                        "constant/$(string(validation.configuration))" : nothing,
        branch_signature=validation.accepted ? validation.provisional.branch_signature : (),
        verified=validation.accepted,
        verified_payload=validation.accepted ? validation.provisional : nothing,
        residual_score=validation.accepted ? Float64(validation.provisional.canonical_residual_bound) : Inf,
        oracle_work=validation.oracle_work,
        endpoint=(),
        diagnostic=validation.accepted ? "constant canonical validation" : string(validation.failure),
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
)
    options.worker_count == 1 || throw(
        SolveConfigurationError(
            :parallel_execution_unavailable,
            "worker_count > 1 is not available in the deterministic v1 execution path",
        ),
    )
    max_actions >= 0 || throw(ArgumentError("max_actions must be nonnegative"))
    started = time()
    deadline = started + options.wall_seconds
    compiled = compile_problem(problem, registry; numeric_backend="Float64")
    resume = _solve_resume_identity(compiled, options)
    now = time()
    workspace = SearchWorkspace(
        adaptive_unbounded=any(
            variable -> variable.lower === nothing || variable.upper === nothing,
            problem.variables,
        ),
    )
    context = ExecutionContext(
        resume;
        rng=(seed=options.seed,),
        registry,
        precision_bits=options._validation.precision_bits,
        policy=options.policy,
        workspace,
        cancel,
        clock=time,
        deadline=max(deadline, now),
        rng_checkpoint=Base.identity,
    )
    search = if now >= deadline
        _finish_search(context, LOOP_DEADLINE_REACHED; detail="compile consumed wall budget")
    elseif isempty(problem.variables)
        _constant_search!(context, compiled, options)
    else
        engine = ProposalEngine(problem; seed=options.seed)
        runner = _CompiledAttemptRunner(
            compiled,
            CompiledWorkspace(compiled),
            options._local,
            options._validation,
        )
        run_search!(context, engine, runner; max_actions)
    end
    return _finish_execution(context, search; evidence_path)
end

function solve(
    problem::ProblemSpecV1,
    registry::FrozenPluginRegistry;
    options::SolveOptions=SolveOptions(),
    cancel::CancellationToken=CancellationToken(),
    evidence_path::Union{Nothing,AbstractString}=nothing,
)
    return solve_execution(
        problem,
        registry;
        options,
        cancel,
        evidence_path,
    ).result
end
