@enum ExecutionMode::UInt8 begin
    DETERMINISTIC_REPLAY = 0
    PERFORMANCE_MODE = 1
end

struct CancellationToken
    cancelled::Base.Threads.Atomic{Bool}

    CancellationToken() = new(Base.Threads.Atomic{Bool}(false))
end

cancel!(token::CancellationToken) = (token.cancelled[] = true; token)
is_cancelled(token::CancellationToken) = token.cancelled[]

mutable struct SearchWorkspace
    candidates::CandidateStore
    scheduler::FairScheduler
    pending::Vector{Proposal}
    refinement_queue::Vector{UInt64}
    refinement_members::Set{UInt64}
    seen_task_ids::Set{UInt64}
    adaptive_unbounded::Bool

    function SearchWorkspace(; adaptive_unbounded::Bool=false)
        return new(
            CandidateStore(),
            FairScheduler(),
            Proposal[],
            UInt64[],
            Set{UInt64}(),
            Set{UInt64}(),
            adaptive_unbounded,
        )
    end
end

function enqueue_proposal!(workspace::SearchWorkspace, proposal::Proposal)
    proposal.task_id in workspace.seen_task_ids && throw(
        SearchProtocolError(:duplicate_task, "task $(proposal.task_id) was already proposed"),
    )
    push!(workspace.seen_task_ids, proposal.task_id)
    push!(workspace.pending, proposal)
    return proposal
end

function _enqueue_refinement!(workspace::SearchWorkspace, configuration::UInt64)
    configuration in workspace.refinement_members && return workspace
    push!(workspace.refinement_members, configuration)
    push!(workspace.refinement_queue, configuration)
    return workspace
end

function _consume_refinement!(workspace::SearchWorkspace, configuration::UInt64)
    isempty(workspace.refinement_queue) && throw(
        SearchProtocolError(:missing_refinement, "refinement queue is unexpectedly empty"),
    )
    first(workspace.refinement_queue) == configuration || throw(
        SearchProtocolError(:refinement_order, "refinement queue order changed during scheduling"),
    )
    popfirst!(workspace.refinement_queue)
    delete!(workspace.refinement_members, configuration)
    return workspace
end

struct WorkspaceSnapshot
    candidates::CandidateStoreSnapshot
    scheduler::SchedulerSnapshot
    pending::Tuple
    refinement_queue::Tuple{Vararg{UInt64}}
    seen_task_ids::Tuple{Vararg{UInt64}}
    adaptive_unbounded::Bool
end

workspace_snapshot(workspace::SearchWorkspace) = WorkspaceSnapshot(
    candidate_snapshot(workspace.candidates),
    scheduler_snapshot(workspace.scheduler),
    Tuple(workspace.pending),
    Tuple(workspace.refinement_queue),
    Tuple(sort!(collect(workspace.seen_task_ids))),
    workspace.adaptive_unbounded,
)

struct ExecutionContext{R,G,C,H,K}
    deadline::Float64
    cancel::CancellationToken
    rng::R
    precision_bits::Int
    registry::G
    policy::SolvePolicy
    budget::BudgetLedger
    events::EvidenceLog
    workspace::SearchWorkspace
    resume_identity::ResumeIdentity
    clock::C
    mode::ExecutionMode
    performance_hook::H
    rng_checkpoint::K
end

function ExecutionContext(
    resume_identity::ResumeIdentity;
    rng,
    registry,
    precision_bits::Integer=53,
    policy::SolvePolicy=standard_policy(),
    budget=nothing,
    events::EvidenceLog=EvidenceLog(),
    workspace::SearchWorkspace=SearchWorkspace(),
    cancel::CancellationToken=CancellationToken(),
    clock=time,
    deadline=nothing,
    remaining_seconds=nothing,
    mode::ExecutionMode=DETERMINISTIC_REPLAY,
    performance_hook=nothing,
    rng_checkpoint=identity,
)
    precision_bits >= 2 || throw(ArgumentError("precision_bits must be at least two"))
    now = Float64(clock())
    isfinite(now) || throw(ArgumentError("clock must return a finite real time"))
    deadline !== nothing && remaining_seconds !== nothing && throw(
        ArgumentError("deadline and remaining_seconds are mutually exclusive"),
    )
    remaining = remaining_seconds === nothing ? nothing : Float64(remaining_seconds)
    remaining === nothing || isfinite(remaining) && remaining >= 0 || throw(
        ArgumentError("remaining_seconds must be finite and nonnegative"),
    )
    stop_time = if remaining !== nothing
        now + remaining
    elseif deadline === nothing
        now + policy.wall_seconds
    else
        Float64(deadline)
    end
    isfinite(stop_time) || throw(ArgumentError("deadline must be finite"))
    stop_time >= now || throw(ArgumentError("deadline must not precede context creation"))
    selected_budget = budget === nothing ? BudgetLedger(policy.budget_limits) : budget
    selected_budget isa BudgetLedger || throw(ArgumentError("budget must be a BudgetLedger"))
    mode === DETERMINISTIC_REPLAY && performance_hook !== nothing && throw(
        ArgumentError("performance_hook is available only in PERFORMANCE_MODE"),
    )
    # Mutable RNG implementations must provide an explicit immutable state encoder.
    _freeze_search_value(rng_checkpoint(rng))
    return ExecutionContext(
        stop_time,
        cancel,
        rng,
        Int(precision_bits),
        registry,
        policy,
        selected_budget,
        events,
        workspace,
        resume_identity,
        clock,
        mode,
        performance_hook,
        rng_checkpoint,
    )
end

struct CheckpointSnapshot
    resume_identity::ResumeIdentity
    policy_version::VersionNumber
    budget::BudgetSnapshot
    workspace::WorkspaceSnapshot
    events::Tuple
    rng_state::Any
    precision_bits::Int
    remaining_seconds::Float64
    cancelled::Bool
end

function checkpoint_snapshot(context::ExecutionContext)
    captured_at = Float64(context.clock())
    isfinite(captured_at) || throw(
        SearchProtocolError(:invalid_clock, "clock returned nonfinite time at checkpoint"),
    )
    rng_state = _freeze_search_value(context.rng_checkpoint(context.rng))
    return CheckpointSnapshot(
        context.resume_identity,
        context.policy.version,
        budget_snapshot(context.budget),
        workspace_snapshot(context.workspace),
        evidence_events(context.events),
        rng_state,
        context.precision_bits,
        max(0.0, context.deadline - captured_at),
        is_cancelled(context.cancel),
    )
end

function assert_resume_identity(
    snapshot::CheckpointSnapshot,
    current::ResumeIdentity,
)
    can_resume(current, snapshot.resume_identity) || throw(
        SearchProtocolError(
            :resume_identity_mismatch,
            "checkpoint graph/plugins/policy/environment identity does not match",
        ),
    )
    return snapshot
end

_checkpoint_failure(code::Symbol, message::AbstractString) =
    throw(SearchProtocolError(code, String(message)))

function _same_budget_limits(left::BudgetLimits, right::BudgetLimits)
    return left.proposals == right.proposals &&
           left.local_attempts == right.local_attempts &&
           left.refinements == right.refinements &&
           left.oracle_work == right.oracle_work
end

function _restore_budget(snapshot::BudgetSnapshot, policy::SolvePolicy)
    _same_budget_limits(snapshot.limits, policy.budget_limits) || _checkpoint_failure(
        :resume_policy_mismatch,
        "checkpoint budget limits do not match the active solve policy",
    )
    counts = (
        snapshot.proposals,
        snapshot.local_attempts,
        snapshot.refinements,
        snapshot.oracle_work,
    )
    all(count -> count >= 0, counts) || _checkpoint_failure(
        :corrupt_checkpoint,
        "checkpoint contains a negative budget counter",
    )
    limits = (
        snapshot.limits.proposals,
        snapshot.limits.local_attempts,
        snapshot.limits.refinements,
        snapshot.limits.oracle_work,
    )
    all(
        pair -> last(pair) === nothing || first(pair) <= last(pair),
        zip(counts, limits),
    ) || _checkpoint_failure(
        :corrupt_checkpoint,
        "checkpoint budget counters exceed their hard limits",
    )
    ledger = BudgetLedger(snapshot.limits)
    ledger.proposals = snapshot.proposals
    ledger.local_attempts = snapshot.local_attempts
    ledger.refinements = snapshot.refinements
    ledger.oracle_work = snapshot.oracle_work
    return ledger
end

function _restore_events(events::Tuple)
    log = EvidenceLog()
    for (sequence, event) in enumerate(events)
        event isa EvidenceEvent || _checkpoint_failure(
            :corrupt_checkpoint,
            "checkpoint evidence contains a non-event payload",
        )
        event.sequence == sequence || _checkpoint_failure(
            :corrupt_checkpoint,
            "checkpoint evidence sequence is not contiguous",
        )
        restored = record_event!(log, event.kind, event.payload)
        isequal(restored.payload, event.payload) || _checkpoint_failure(
            :corrupt_checkpoint,
            "checkpoint evidence payload changed while being frozen",
        )
    end
    return log
end

function _restore_candidate_store(snapshot::CandidateStoreSnapshot)
    store = CandidateStore()
    for record in snapshot.history
        record isa CandidateRecord || _checkpoint_failure(
            :corrupt_checkpoint,
            "checkpoint candidate history contains a non-record payload",
        )
        restored = try
            insert_candidate!(store, record.proposal, record.observation)
        catch error
            error isa SearchProtocolError || rethrow()
            _checkpoint_failure(
                :corrupt_checkpoint,
                "checkpoint candidate history cannot be replayed: $(sprint(showerror, error))",
            )
        end
        restored.revision == record.revision || _checkpoint_failure(
            :corrupt_checkpoint,
            "checkpoint candidate revision is inconsistent with its history",
        )
    end
    isequal(candidate_snapshot(store), snapshot) || _checkpoint_failure(
        :corrupt_checkpoint,
        "checkpoint candidate derived views do not match replayed history",
    )
    return store
end

function _restore_scheduler(snapshot::SchedulerSnapshot)
    all(count -> count >= 0, snapshot.served) || _checkpoint_failure(
        :corrupt_checkpoint,
        "checkpoint scheduler contains a negative served counter",
    )
    served_total = sum(UInt128(count) for count in snapshot.served)
    served_total <= typemax(Int) || _checkpoint_failure(
        :corrupt_checkpoint,
        "checkpoint scheduler counters overflow the supported action range",
    )
    snapshot.total_actions == Int(served_total) || _checkpoint_failure(
        :corrupt_checkpoint,
        "checkpoint scheduler total does not equal its lane counters",
    )
    snapshot.shell_ticks == snapshot.served[_lane_index(LANE_SHELL)] ||
        _checkpoint_failure(
            :corrupt_checkpoint,
            "checkpoint shell counter does not equal scheduled shell work",
        )
    proposal_actions = sum(
        UInt128(snapshot.served[_lane_index(lane)]) for lane in _PROPOSAL_LANES
    )
    expected_next = proposal_actions + UInt128(1)
    expected_next <= typemax(UInt64) || _checkpoint_failure(
        :corrupt_checkpoint,
        "checkpoint scheduler task counter overflowed",
    )
    snapshot.next_task_id == UInt64(expected_next) || _checkpoint_failure(
        :corrupt_checkpoint,
        "checkpoint next task ID is inconsistent with scheduled proposal work",
    )
    scheduler = FairScheduler()
    scheduler.served .= snapshot.served
    scheduler.total_actions = snapshot.total_actions
    scheduler.next_task_id = snapshot.next_task_id
    scheduler.shell_ticks = snapshot.shell_ticks
    return scheduler
end

function _restore_workspace(snapshot::WorkspaceSnapshot)
    candidates = _restore_candidate_store(snapshot.candidates)
    scheduler = _restore_scheduler(snapshot.scheduler)
    all(proposal -> proposal isa Proposal, snapshot.pending) || _checkpoint_failure(
        :corrupt_checkpoint,
        "checkpoint pending queue contains a non-proposal payload",
    )
    pending = Proposal[snapshot.pending...]
    pending_ids = UInt64[proposal.task_id for proposal in pending]
    allunique(pending_ids) || _checkpoint_failure(
        :corrupt_checkpoint,
        "checkpoint pending queue contains duplicate task IDs",
    )
    seen_ids = UInt64[snapshot.seen_task_ids...]
    issorted(seen_ids) && allunique(seen_ids) || _checkpoint_failure(
        :corrupt_checkpoint,
        "checkpoint seen task IDs must be sorted and unique",
    )
    observed_ids = UInt64[record.proposal.task_id for record in snapshot.candidates.history]
    sort!(vcat(observed_ids, pending_ids)) == seen_ids || _checkpoint_failure(
        :corrupt_checkpoint,
        "checkpoint seen task IDs do not match observed and pending work",
    )
    queue = UInt64[snapshot.refinement_queue...]
    allunique(queue) || _checkpoint_failure(
        :corrupt_checkpoint,
        "checkpoint refinement queue contains duplicate configurations",
    )
    latest_configurations = Set(
        record.proposal.configuration_id for record in snapshot.candidates.latest
    )
    all(configuration -> configuration in latest_configurations, queue) ||
        _checkpoint_failure(
            :corrupt_checkpoint,
            "checkpoint refinement queue references an unknown configuration",
        )

    workspace = SearchWorkspace(; adaptive_unbounded=snapshot.adaptive_unbounded)
    workspace.candidates = candidates
    workspace.scheduler = scheduler
    workspace.pending = pending
    workspace.refinement_queue = queue
    workspace.refinement_members = Set(queue)
    workspace.seen_task_ids = Set(seen_ids)
    return workspace
end

"""
Restore a search context from an immutable checkpoint after validating all
identity, policy, derived-state, event, budget and RNG invariants.

Cancellation is intentionally supplied by the caller: a checkpoint records
whether the previous invocation was cancelled, but a new invocation receives a
fresh token unless an already-cancelled token is explicitly passed.
"""
function restore_execution_context(
    snapshot::CheckpointSnapshot,
    current::ResumeIdentity;
    registry,
    policy::SolvePolicy,
    rng_restore=identity,
    rng_checkpoint=identity,
    cancel::CancellationToken=CancellationToken(),
    clock=time,
    mode::ExecutionMode=DETERMINISTIC_REPLAY,
    performance_hook=nothing,
)
    assert_resume_identity(snapshot, current)
    snapshot.policy_version == policy.version || _checkpoint_failure(
        :resume_policy_mismatch,
        "checkpoint policy version does not match the active solve policy",
    )
    snapshot.precision_bits >= 2 || _checkpoint_failure(
        :corrupt_checkpoint,
        "checkpoint precision is invalid",
    )
    isfinite(snapshot.remaining_seconds) && snapshot.remaining_seconds >= 0 ||
        _checkpoint_failure(
            :corrupt_checkpoint,
            "checkpoint remaining wall budget is invalid",
        )
    budget = _restore_budget(snapshot.budget, policy)
    events = _restore_events(snapshot.events)
    workspace = _restore_workspace(snapshot.workspace)
    rng = rng_restore(snapshot.rng_state)
    restored_rng_state = _freeze_search_value(rng_checkpoint(rng))
    isequal(restored_rng_state, snapshot.rng_state) || _checkpoint_failure(
        :resume_rng_mismatch,
        "restored RNG state does not match the checkpoint",
    )
    return ExecutionContext(
        current;
        rng,
        registry,
        precision_bits=snapshot.precision_bits,
        policy,
        budget,
        events,
        workspace,
        cancel,
        clock,
        remaining_seconds=snapshot.remaining_seconds,
        mode,
        performance_hook,
        rng_checkpoint,
    )
end

struct SearchLoopResult
    status::SearchLoopStatus
    verified_answers::Tuple
    candidates::CandidateStoreSnapshot
    checkpoint::CheckpointSnapshot
end

function _finish_search(context::ExecutionContext, status::SearchLoopStatus; detail=nothing)
    status === LOOP_RUNNING && throw(ArgumentError("cannot finish with LOOP_RUNNING"))
    record_event!(context.events, EVENT_STATUS, (; status, detail))
    checkpoint = checkpoint_snapshot(context)
    answers = verified_answers(context.workspace.candidates)
    return SearchLoopResult(
        status,
        answers,
        candidate_snapshot(context.workspace.candidates),
        checkpoint,
    )
end

function _record_charge!(
    context::ExecutionContext,
    charge::BudgetCharge,
)
    charge!(context.budget, charge)
    record_event!(
        context.events,
        EVENT_BUDGET_CHARGED,
        (; charge, snapshot=budget_snapshot(context.budget)),
    )
    return context.budget
end

function _validate_emitted_proposal(decision::ScheduleDecision, proposal)
    proposal isa Proposal || throw(
        SearchProtocolError(:invalid_proposal, "proposal emitter must return Proposal"),
    )
    proposal.task_id == decision.task_id || throw(
        SearchProtocolError(:task_mismatch, "emitter changed the scheduled task ID"),
    )
    proposal.lane === decision.lane || throw(
        SearchProtocolError(:lane_mismatch, "emitter changed the scheduled lane"),
    )
    proposal.shell == decision.shell || throw(
        SearchProtocolError(:shell_mismatch, "emitter changed the scheduled shell"),
    )
    proposal.source_configuration == decision.source_configuration || throw(
        SearchProtocolError(
            :refinement_source_mismatch,
            "emitter changed the scheduled refinement source",
        ),
    )
    if decision.lane === LANE_REFINEMENT &&
       proposal.configuration_id != decision.source_configuration
        throw(
            SearchProtocolError(
                :refinement_configuration_mismatch,
                "a refinement proposal must preserve its configuration identity",
            ),
        )
    end
    return proposal
end

function _record_failure!(context, kind::SearchEventKind, stage::Symbol, error)
    record_event!(
        context.events,
        kind,
        (; stage, error_type=string(typeof(error)), message=sprint(showerror, error)),
    )
end

function _emit_proposal!(context::ExecutionContext, decision::ScheduleDecision, emitter)
    proposal = _validate_emitted_proposal(decision, emitter(context, decision))
    charge = BudgetCharge(
        proposals=1,
        refinements=decision.lane === LANE_REFINEMENT ? 1 : 0,
    )
    can_charge(context.budget, charge) || throw(
        SearchProtocolError(:budget_exceeded, "proposal emission exceeded its typed budget"),
    )
    enqueue_proposal!(context.workspace, proposal)
    decision.lane === LANE_REFINEMENT && _consume_refinement!(
        context.workspace,
        decision.source_configuration::UInt64,
    )
    _record_charge!(context, charge)
    record_event!(context.events, EVENT_PROPOSED, proposal)
    return proposal
end

function _attempt_pending!(context::ExecutionContext, local_attempt)
    proposal = first(context.workspace.pending)
    attempt_charge = BudgetCharge(local_attempts=1)
    can_charge(context.budget, attempt_charge) || throw(
        SearchProtocolError(:budget_exceeded, "local attempt exceeded its typed budget"),
    )
    _record_charge!(context, attempt_charge)
    observation = local_attempt(context, proposal)
    observation isa Observation || throw(
        SearchProtocolError(:invalid_observation, "local-attempt callback must return Observation"),
    )
    proposal.task_id == observation.task_id || throw(
        SearchProtocolError(:task_mismatch, "local attempt returned the wrong task ID"),
    )
    proposal.configuration_id == observation.configuration_id || throw(
        SearchProtocolError(
            :configuration_mismatch,
            "local attempt returned the wrong configuration ID",
        ),
    )
    oracle_charge = BudgetCharge(oracle_work=observation.oracle_work)
    can_charge(context.budget, oracle_charge) || throw(
        SearchProtocolError(
            :callback_budget_overrun,
            "local attempt reported oracle work beyond its remaining budget",
        ),
    )
    _record_charge!(context, oracle_charge)
    insert_candidate!(context.workspace.candidates, proposal, observation)
    popfirst!(context.workspace.pending)
    observation.needs_refinement &&
        _enqueue_refinement!(context.workspace, observation.configuration_id)
    record_event!(context.events, EVENT_OBSERVED, observation)
    return observation
end

function _loop_terminal_status(context::ExecutionContext)
    is_cancelled(context.cancel) && return LOOP_CANCELLED
    now = Float64(context.clock())
    isfinite(now) || throw(
        SearchProtocolError(:invalid_clock, "clock returned a nonfinite value during search"),
    )
    now >= context.deadline && return LOOP_DEADLINE_REACHED
    return LOOP_RUNNING
end

function run_search!(
    context::ExecutionContext,
    proposal_emitter,
    local_attempt;
    max_actions::Integer=typemax(Int),
)
    max_actions >= 0 || throw(ArgumentError("max_actions must be nonnegative"))
    actions = 0
    while actions < max_actions
        status = try
            _loop_terminal_status(context)
        catch error
            _record_failure!(context, EVENT_PROTOCOL_FAILED, :clock, error)
            return _finish_search(context, LOOP_PROTOCOL_ERROR; detail=sprint(showerror, error))
        end
        status === LOOP_RUNNING || return _finish_search(context, status)

        pending_charge = BudgetCharge(local_attempts=1)
        pending_task_id = if !isempty(context.workspace.pending) &&
                             can_charge(context.budget, pending_charge)
            first(context.workspace.pending).task_id
        else
            nothing
        end
        proposal_charge = BudgetCharge(proposals=1)
        proposal_budget_available = can_charge(context.budget, proposal_charge)
        refinement_budget_available = can_charge(
            context.budget,
            BudgetCharge(proposals=1, refinements=1),
        )
        pending_blocked = !isempty(context.workspace.pending) && pending_task_id === nothing
        # Exhausting the optional refinement lane must not starve fresh global
        # proposals. In particular, the bounded-gap IID insurance lane remains
        # serviceable until the proposal or local-attempt budget is exhausted.
        allow_new = proposal_budget_available && !pending_blocked
        refinement_configuration = if allow_new && refinement_budget_available &&
                                      !isempty(context.workspace.refinement_queue)
            first(context.workspace.refinement_queue)
        else
            nothing
        end
        decision = next_schedule!(
            context.workspace.scheduler,
            context.policy;
            adaptive_unbounded=context.workspace.adaptive_unbounded,
            pending_task_id,
            refinement_configuration,
            allow_new_proposals=allow_new,
        )
        decision === nothing &&
            return _finish_search(context, LOOP_BUDGET_EXHAUSTED)
        record_event!(context.events, EVENT_SCHEDULED, decision)

        if context.mode === PERFORMANCE_MODE && context.performance_hook !== nothing
            try
                context.performance_hook(context, decision)
            catch error
                _record_failure!(context, EVENT_CALLBACK_FAILED, :performance_hook, error)
                return _finish_search(
                    context,
                    LOOP_CALLBACK_ERROR;
                    detail=sprint(showerror, error),
                )
            end
        end

        try
            if decision.lane === LANE_PENDING
                _attempt_pending!(context, local_attempt)
            else
                _emit_proposal!(context, decision, proposal_emitter)
            end
        catch error
            if error isa SearchProtocolError
                _record_failure!(context, EVENT_PROTOCOL_FAILED, :search_action, error)
                return _finish_search(
                    context,
                    LOOP_PROTOCOL_ERROR;
                    detail=sprint(showerror, error),
                )
            end
            _record_failure!(context, EVENT_CALLBACK_FAILED, :search_action, error)
            return _finish_search(
                context,
                LOOP_CALLBACK_ERROR;
                detail=sprint(showerror, error),
            )
        end
        actions += 1
    end
    return _finish_search(context, LOOP_PAUSED; detail="max_actions reached")
end
