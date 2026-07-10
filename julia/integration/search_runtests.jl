using GeoTargetBase
using Test

module SearchShellHarness
using GeoTargetBase

include(joinpath(@__DIR__, "..", "GeoTargetCore", "src", "events.jl"))
include(joinpath(@__DIR__, "..", "GeoTargetCore", "src", "candidate_store.jl"))
include(joinpath(@__DIR__, "..", "GeoTargetCore", "src", "search_policy.jl"))
include(joinpath(@__DIR__, "..", "GeoTargetCore", "src", "search_loop.jl"))
end

const S = SearchShellHarness

struct FakeRNG
    seed::UInt64
end

struct ImmutableWrapperWithMutableField
    values::Vector{Int}
end

mutable struct MutableRNG
    counter::Int
end

mutable struct FakeClock
    value::Float64
end

(clock::FakeClock)() = clock.value

function resume_identity(label="default")
    return ResumeIdentity(
        content_hash("graph-$label"),
        (),
        content_hash("policy-$label"),
        content_hash("environment-$label"),
    )
end

function execution_context(
    policy=S.standard_policy();
    clock=FakeClock(0.0),
    deadline=nothing,
    adaptive_unbounded=false,
    cancel=S.CancellationToken(),
    mode=S.DETERMINISTIC_REPLAY,
    performance_hook=nothing,
)
    workspace = S.SearchWorkspace(; adaptive_unbounded)
    return S.ExecutionContext(
        resume_identity();
        rng=FakeRNG(0x1234),
        registry=:frozen_test_registry,
        precision_bits=53,
        policy,
        workspace,
        cancel,
        clock,
        deadline,
        mode,
        performance_hook,
    )
end

function proposal_for(decision::S.ScheduleDecision)
    configuration = something(decision.source_configuration, decision.task_id)
    coordinate = decision.shell === nothing ? Float64(decision.task_id) : Float64(decision.shell)
    return S.Proposal(
        decision.task_id,
        configuration,
        decision.lane,
        (coordinate,);
        shell=decision.shell,
        source_configuration=decision.source_configuration,
        metadata=((:scheduled_lane => decision.lane),),
    )
end

function empty_observation(proposal::S.Proposal; needs_refinement=false)
    return S.Observation(
        proposal.task_id,
        proposal.configuration_id;
        canonical_near_feasible=false,
        needs_refinement,
        oracle_work=1,
    )
end

function schedule_trace(events)
    return Tuple(
        (
            event.payload.lane,
            event.payload.task_id,
            event.payload.shell,
            event.payload.source_configuration,
        ) for event in events if event.kind === S.EVENT_SCHEDULED
    )
end

@testset "versioned public presets and typed budget ledger" begin
    fast = S.fast_policy()
    standard = S.standard_policy()
    thorough = S.thorough_policy()
    @test (fast.preset, standard.preset, thorough.preset) == (:fast, :standard, :thorough)
    @test (fast.wall_seconds, standard.wall_seconds, thorough.wall_seconds) ==
        (60.0, 180.0, 420.0)
    @test fast.version == standard.version == thorough.version == S.SOLVE_POLICY_VERSION
    @test_throws MethodError S.SolvePolicy()

    ledger = S.BudgetLedger(S.BudgetLimits(proposals=2, local_attempts=1))
    @test S.can_charge(ledger, S.BudgetCharge(proposals=2))
    S.charge!(ledger, S.BudgetCharge(proposals=2, local_attempts=1))
    @test !S.can_charge(ledger, S.BudgetCharge(proposals=1))
    @test_throws S.SearchProtocolError S.charge!(ledger, S.BudgetCharge(proposals=1))
end

@testset "weighted fairness, full-support IID, and ruler shells" begin
    policy = S.standard_policy()
    scheduler = S.FairScheduler()
    decisions = S.ScheduleDecision[]
    sizehint!(decisions, 100_000)
    for _ in 1:100_000
        push!(
            decisions,
            S.next_schedule!(
                scheduler,
                policy;
                adaptive_unbounded=true,
                pending_task_id=UInt64(999),
                refinement_configuration=UInt64(777),
                allow_new_proposals=true,
            ),
        )
    end
    @test S.iid_prefix_invariant(decisions, 4)
    for lane in (
        S.LANE_IID,
        S.LANE_HEURISTIC,
        S.LANE_SHELL,
        S.LANE_PENDING,
        S.LANE_REFINEMENT,
    )
        positions = findall(decision -> decision.lane === lane, decisions)
        @test length(positions) > 1_000
        @test maximum(diff(positions)) < 100
    end

    shell_visits = [decision.shell for decision in decisions if decision.lane === S.LANE_SHELL]
    @test shell_visits[1:8] == [0, 1, 0, 2, 0, 1, 0, 3]
    for shell in 0:7
        @test count(==(shell), shell_visits) >= 10
    end
    @test [S.ruler_shell(index) for index in 1:16] ==
        [0, 1, 0, 2, 0, 1, 0, 3, 0, 1, 0, 2, 0, 1, 0, 4]

    bounded_scheduler = S.FairScheduler()
    bounded = [
        S.next_schedule!(
            bounded_scheduler,
            policy;
            adaptive_unbounded=false,
            allow_new_proposals=true,
        ) for _ in 1:1_000
    ]
    @test all(decision -> decision.lane !== S.LANE_SHELL, bounded)
end

@testset "canonical target gate and reversible candidate niches" begin
    @test_throws S.SearchProtocolError S.Observation(
        1,
        1;
        canonical_near_feasible=false,
        target=S.TargetEnclosure(1.0),
    )
    @test_throws S.SearchProtocolError S.Observation(
        1,
        1;
        canonical_near_feasible=true,
        canonical_valid=true,
        target=S.TargetEnclosure(1.0),
        target_identity="unsafe-payload",
        verified=true,
        verified_payload=ImmutableWrapperWithMutableField([1]),
    )

    store = S.CandidateStore()
    first_proposal = S.Proposal(1, 11, S.LANE_IID, (0.0,))
    second_proposal = S.Proposal(2, 22, S.LANE_HEURISTIC, (1.0,))
    first_broad = S.Observation(
        1,
        11;
        canonical_near_feasible=true,
        target=S.TargetEnclosure(0.0, 2.0),
        branch_signature=(:left,),
        needs_refinement=true,
        residual_score=1.0e-4,
    )
    second_broad = S.Observation(
        2,
        22;
        canonical_near_feasible=true,
        target=S.TargetEnclosure(1.0, 3.0),
        branch_signature=(:left,),
        needs_refinement=true,
        residual_score=1.0e-4,
    )
    S.insert_candidate!(store, first_proposal, first_broad)
    S.insert_candidate!(store, second_proposal, second_broad)
    @test length(S.target_niches(store)) == 1
    @test only(S.target_niches(store)).configurations == (UInt64(11), UInt64(22))

    first_refinement = S.Proposal(
        3,
        11,
        S.LANE_REFINEMENT,
        (0.0,);
        source_configuration=11,
    )
    first_narrow = S.Observation(
        3,
        11;
        canonical_near_feasible=true,
        canonical_valid=true,
        target=S.TargetEnclosure(0.0, 0.1),
        target_identity="close-left",
        branch_signature=(:left,),
        verified=true,
        verified_payload=(:validated, :left),
        residual_score=0.0,
    )
    S.insert_candidate!(store, first_refinement, first_narrow)
    @test length(S.target_niches(store)) == 2

    no_target = S.Proposal(4, 33, S.LANE_IID, (2.0,))
    no_target_observation = S.Observation(
        4,
        33;
        canonical_near_feasible=true,
        target=nothing,
        needs_refinement=true,
        residual_score=1.0e-3,
    )
    S.insert_candidate!(store, no_target, no_target_observation)
    @test UInt64(33) in S.x_reservoir(store)
    @test length(S.candidate_records(store)) == 4
end

@testset "same target keeps multiple witnesses without merging close targets" begin
    store = S.CandidateStore()
    for (task, configuration, branch) in ((1, 101, :left), (2, 202, :right))
        proposal = S.Proposal(task, configuration, S.LANE_IID, (Float64(task),))
        observation = S.Observation(
            task,
            configuration;
            canonical_near_feasible=true,
            canonical_valid=true,
            target=S.TargetEnclosure(1.0),
            target_identity="shared-target",
            branch_signature=(branch,),
            verified=true,
            verified_payload=(:certificate, task),
            residual_score=0.0,
        )
        S.insert_candidate!(store, proposal, observation)
    end
    @test length(S.verified_answers(store)) == 1
    @test only(S.verified_answers(store)).witnesses == (UInt64(101), UInt64(202))

    for (task, configuration, value, identity) in (
        (3, 303, 1.0 + 1.0e-10, "close-a"),
        (4, 404, 1.0 + 2.0e-10, "close-b"),
    )
        proposal = S.Proposal(task, configuration, S.LANE_HEURISTIC, (value,))
        observation = S.Observation(
            task,
            configuration;
            canonical_near_feasible=true,
            canonical_valid=true,
            target=S.TargetEnclosure(value),
            target_identity=identity,
            verified=true,
            verified_payload=(:certificate, identity),
            residual_score=0.0,
        )
        S.insert_candidate!(store, proposal, observation)
    end
    @test length(S.verified_answers(store)) == 3

    unverified_update = S.Proposal(
        5,
        101,
        S.LANE_REFINEMENT,
        (1.0,);
        source_configuration=101,
    )
    S.insert_candidate!(
        store,
        unverified_update,
        S.Observation(
            5,
            101;
            canonical_near_feasible=true,
            target=S.TargetEnclosure(0.9, 1.1),
            needs_refinement=true,
            residual_score=1.0e-6,
        ),
    )
    @test length(S.verified_answers(store)) == 3

    history_length = length(S.candidate_records(store))
    inconsistent_proposal = S.Proposal(6, 606, S.LANE_IID, (9.0,))
    inconsistent_observation = S.Observation(
        6,
        606;
        canonical_near_feasible=true,
        canonical_valid=true,
        target=S.TargetEnclosure(9.0),
        target_identity="shared-target",
        verified=true,
        verified_payload=(:certificate, :inconsistent),
        residual_score=0.0,
    )
    @test_throws S.SearchProtocolError S.insert_candidate!(
        store,
        inconsistent_proposal,
        inconsistent_observation,
    )
    @test length(S.candidate_records(store)) == history_length
end

@testset "generic target enclosures never merge without proof identity" begin
    store = S.CandidateStore()
    first = S.Proposal(1, 101, S.LANE_IID, (0.0,))
    second = S.Proposal(2, 202, S.LANE_IID, (1.0,))
    value = setprecision(BigFloat, 256) do
        BigFloat("1e400")
    end
    for (proposal, configuration) in ((first, 101), (second, 202))
        observation = S.Observation(
            proposal.task_id,
            configuration;
            canonical_near_feasible=true,
            canonical_valid=true,
            target=S.TargetEnclosure(value),
            verified=true,
            verified_payload=(:validated, configuration),
            residual_score=0.0,
        )
        S.insert_candidate!(store, proposal, observation)
    end
    @test length(S.verified_answers(store)) == 2
    @test all(answer -> answer.target.lower isa BigFloat, S.verified_answers(store))
end

@testset "blocked pending or refinement work stops instead of accumulating" begin
    no_attempt_budget = S.BudgetLedger(
        S.BudgetLimits(proposals=10, local_attempts=0, refinements=10, oracle_work=100),
    )
    pending_context = S.ExecutionContext(
        resume_identity();
        rng=FakeRNG(1),
        registry=:registry,
        policy=S.fast_policy(),
        budget=no_attempt_budget,
        workspace=S.SearchWorkspace(),
        clock=FakeClock(0.0),
        deadline=100.0,
    )
    pending_result = S.run_search!(
        pending_context,
        (context, decision) -> proposal_for(decision),
        (context, proposal) -> empty_observation(proposal),
    )
    @test pending_result.status === S.LOOP_BUDGET_EXHAUSTED
    @test pending_context.budget.proposals == 1
    @test length(pending_context.workspace.pending) == 1

    no_refinement_budget = S.BudgetLedger(
        S.BudgetLimits(proposals=10, local_attempts=10, refinements=0, oracle_work=100),
    )
    refinement_context = S.ExecutionContext(
        resume_identity();
        rng=FakeRNG(1),
        registry=:registry,
        policy=S.fast_policy(),
        budget=no_refinement_budget,
        workspace=S.SearchWorkspace(),
        clock=FakeClock(0.0),
        deadline=100.0,
    )
    refinement_result = S.run_search!(
        refinement_context,
        (context, decision) -> proposal_for(decision),
        (context, proposal) -> empty_observation(proposal; needs_refinement=true),
    )
    @test refinement_result.status === S.LOOP_BUDGET_EXHAUSTED
    @test refinement_context.budget.proposals == 1
    @test refinement_context.workspace.refinement_queue == [UInt64(1)]
end

@testset "duplicate tasks are rejected before a second launch" begin
    workspace = S.SearchWorkspace()
    proposal = S.Proposal(1, 1, S.LANE_IID, (0.0,))
    S.enqueue_proposal!(workspace, proposal)
    @test_throws S.SearchProtocolError S.enqueue_proposal!(workspace, proposal)

    clock = FakeClock(0.0)
    context = execution_context(S.fast_policy(); clock, deadline=100.0)
    bad_emitter = (context, decision) -> S.Proposal(
        1,
        decision.task_id,
        decision.lane,
        (0.0,);
        shell=decision.shell,
        source_configuration=decision.source_configuration,
    )
    result = S.run_search!(context, bad_emitter, (context, proposal) -> empty_observation(proposal))
    @test result.status === S.LOOP_PROTOCOL_ERROR
    proposed = [
        event.payload.task_id for event in S.evidence_events(context.events) if
        event.kind === S.EVENT_PROPOSED
    ]
    @test proposed == [UInt64(1)]
end

@testset "deadline and cancellation return verified partial state" begin
    deadline_clock = FakeClock(0.0)
    deadline_context = execution_context(
        S.fast_policy();
        clock=deadline_clock,
        deadline=0.0,
    )
    deadline_result = S.run_search!(
        deadline_context,
        (context, decision) -> proposal_for(decision),
        (context, proposal) -> empty_observation(proposal),
    )
    @test deadline_result.status === S.LOOP_DEADLINE_REACHED
    @test isempty(deadline_result.verified_answers)

    token = S.CancellationToken()
    S.cancel!(token)
    cancelled = execution_context(S.fast_policy(); cancel=token)
    cancelled_result = S.run_search!(
        cancelled,
        (context, decision) -> proposal_for(decision),
        (context, proposal) -> empty_observation(proposal),
    )
    @test cancelled_result.status === S.LOOP_CANCELLED

    partial_clock = FakeClock(0.0)
    partial = execution_context(S.fast_policy(); clock=partial_clock, deadline=100.0)
    function verify_then_cancel(context, proposal)
        partial_clock.value += 1
        S.cancel!(context.cancel)
        return S.Observation(
            proposal.task_id,
            proposal.configuration_id;
            canonical_near_feasible=true,
            canonical_valid=true,
            target=S.TargetEnclosure(7.0),
            target_identity="partial",
            verified=true,
            verified_payload=(:certificate, :partial),
            residual_score=0.0,
            oracle_work=1,
        )
    end
    partial_result = S.run_search!(partial, (context, decision) -> proposal_for(decision), verify_then_cancel)
    @test partial_result.status === S.LOOP_CANCELLED
    @test length(partial_result.verified_answers) == 1
end

function budget_prefix_result(policy)
    clock = FakeClock(0.0)
    context = execution_context(policy; clock)
    attempts = Ref(0)
    function attempt(context, proposal)
        attempts[] += 1
        clock.value += 1
        discovery = findfirst(==(attempts[]), (10, 100, 300))
        if discovery !== nothing
            return S.Observation(
                proposal.task_id,
                proposal.configuration_id;
                canonical_near_feasible=true,
                canonical_valid=true,
                target=S.TargetEnclosure(Float64(discovery)),
                target_identity="target-$discovery",
                verified=true,
                verified_payload=(:certificate, discovery),
                residual_score=0.0,
                oracle_work=1,
            )
        end
        return empty_observation(proposal)
    end
    result = S.run_search!(context, (context, decision) -> proposal_for(decision), attempt)
    return result, context
end

@testset "60/180/420 verified answers are prefix-monotone" begin
    fast, _ = budget_prefix_result(S.fast_policy())
    standard, _ = budget_prefix_result(S.standard_policy())
    thorough, _ = budget_prefix_result(S.thorough_policy())
    @test fast.status === S.LOOP_DEADLINE_REACHED
    @test standard.status === S.LOOP_DEADLINE_REACHED
    @test thorough.status === S.LOOP_DEADLINE_REACHED
    fast_keys = Set(answer.key for answer in fast.verified_answers)
    standard_keys = Set(answer.key for answer in standard.verified_answers)
    thorough_keys = Set(answer.key for answer in thorough.verified_answers)
    @test (length(fast_keys), length(standard_keys), length(thorough_keys)) == (1, 2, 3)
    @test issubset(fast_keys, standard_keys)
    @test issubset(standard_keys, thorough_keys)
end

@testset "deterministic replay and performance-mode hook" begin
    function replay_run(; mode=S.DETERMINISTIC_REPLAY, hook=nothing)
        context = execution_context(
            S.standard_policy();
            clock=FakeClock(0.0),
            deadline=1_000.0,
            adaptive_unbounded=true,
            mode,
            performance_hook=hook,
        )
        result = S.run_search!(
            context,
            (context, decision) -> proposal_for(decision),
            (context, proposal) -> empty_observation(proposal),
            max_actions=1_000,
        )
        return result, schedule_trace(S.evidence_events(context.events))
    end
    first_result, first_trace = replay_run()
    second_result, second_trace = replay_run()
    @test first_result.status === S.LOOP_PAUSED
    @test first_trace == second_trace

    hook_calls = Ref(0)
    performance_result, performance_trace = replay_run(
        mode=S.PERFORMANCE_MODE,
        hook=(context, decision) -> (hook_calls[] += 1),
    )
    @test performance_result.status === S.LOOP_PAUSED
    @test hook_calls[] == 1_000
    @test performance_trace == first_trace
end

@testset "pending and refinement queues cannot starve" begin
    context = execution_context(
        S.standard_policy();
        clock=FakeClock(0.0),
        deadline=10_000.0,
        adaptive_unbounded=true,
    )
    refined = Set{UInt64}()
    function attempt(context, proposal)
        needs_refinement = proposal.lane !== S.LANE_REFINEMENT &&
                           !(proposal.configuration_id in refined)
        proposal.lane === S.LANE_REFINEMENT && push!(refined, proposal.configuration_id)
        return S.Observation(
            proposal.task_id,
            proposal.configuration_id;
            canonical_near_feasible=false,
            needs_refinement,
            oracle_work=1,
        )
    end
    result = S.run_search!(
        context,
        (context, decision) -> proposal_for(decision),
        attempt;
        max_actions=4_000,
    )
    @test result.status === S.LOOP_PAUSED
    @test context.budget.local_attempts > 500
    @test context.budget.refinements > 100
    @test length(S.candidate_records(context.workspace.candidates)) ==
        context.budget.local_attempts
    @test length(context.workspace.pending) < 20
    @test any(
        event -> event.kind === S.EVENT_PROPOSED && event.payload.lane === S.LANE_SHELL,
        S.evidence_events(context.events),
    )
end

@testset "checkpoint is immutable and ResumeIdentity-bound" begin
    context = execution_context(S.fast_policy(); deadline=100.0)
    result = S.run_search!(
        context,
        (context, decision) -> proposal_for(decision),
        (context, proposal) -> empty_observation(proposal),
        max_actions=20,
    )
    snapshot = result.checkpoint
    @test isimmutable(snapshot)
    @test snapshot.events isa Tuple
    @test snapshot.workspace.pending isa Tuple
    @test snapshot.rng_state == FakeRNG(0x1234)
    @test snapshot.precision_bits == 53
    @test snapshot.remaining_seconds == 100.0
    @test S.assert_resume_identity(snapshot, resume_identity()) === snapshot
    @test_throws S.SearchProtocolError S.assert_resume_identity(
        snapshot,
        resume_identity("different"),
    )

    restored = S.restore_execution_context(
        snapshot,
        resume_identity();
        registry=:frozen_test_registry,
        policy=S.fast_policy(),
        clock=FakeClock(0.0),
    )
    restored_snapshot = S.checkpoint_snapshot(restored)
    @test isequal(restored_snapshot.budget, snapshot.budget)
    @test isequal(restored_snapshot.workspace, snapshot.workspace)
    @test isequal(restored_snapshot.events, snapshot.events)
    @test restored_snapshot.rng_state == snapshot.rng_state
    @test restored_snapshot.remaining_seconds == snapshot.remaining_seconds

    original_continuation = S.run_search!(
        context,
        (context, decision) -> proposal_for(decision),
        (context, proposal) -> empty_observation(proposal);
        max_actions=200,
    )
    restored_continuation = S.run_search!(
        restored,
        (context, decision) -> proposal_for(decision),
        (context, proposal) -> empty_observation(proposal);
        max_actions=200,
    )
    @test isequal(original_continuation.candidates, restored_continuation.candidates)
    @test isequal(
        original_continuation.checkpoint.workspace,
        restored_continuation.checkpoint.workspace,
    )
    @test isequal(
        original_continuation.checkpoint.budget,
        restored_continuation.checkpoint.budget,
    )
    @test isequal(
        original_continuation.checkpoint.events,
        restored_continuation.checkpoint.events,
    )

    @test_throws S.SearchProtocolError S.restore_execution_context(
        snapshot,
        resume_identity();
        registry=:frozen_test_registry,
        policy=S.standard_policy(),
        clock=FakeClock(0.0),
    )
    @test_throws S.SearchProtocolError S.restore_execution_context(
        snapshot,
        resume_identity();
        registry=:frozen_test_registry,
        policy=S.fast_policy(),
        rng_restore=state -> FakeRNG(0),
        clock=FakeClock(0.0),
    )

    over_limit_budget = S.BudgetSnapshot(
        snapshot.budget.limits,
        something(snapshot.budget.limits.proposals, 0) + 1,
        snapshot.budget.local_attempts,
        snapshot.budget.refinements,
        snapshot.budget.oracle_work,
    )
    corrupt = S.CheckpointSnapshot(
        snapshot.resume_identity,
        snapshot.policy_version,
        over_limit_budget,
        snapshot.workspace,
        snapshot.events,
        snapshot.rng_state,
        snapshot.precision_bits,
        snapshot.remaining_seconds,
        snapshot.cancelled,
    )
    @test_throws S.SearchProtocolError S.restore_execution_context(
        corrupt,
        resume_identity();
        registry=:frozen_test_registry,
        policy=S.fast_policy(),
        clock=FakeClock(0.0),
    )

    captured_event_count = length(snapshot.events)
    S.record_event!(context.events, S.EVENT_STATUS, (; status=:after_snapshot))
    @test length(snapshot.events) == captured_event_count

    @test_throws S.SearchProtocolError S.ExecutionContext(
        resume_identity();
        rng=MutableRNG(0),
        registry=:registry,
        policy=S.fast_policy(),
        clock=FakeClock(0.0),
        deadline=1.0,
    )
    mutable_rng_context = S.ExecutionContext(
        resume_identity();
        rng=MutableRNG(7),
        registry=:registry,
        policy=S.fast_policy(),
        clock=FakeClock(0.0),
        deadline=1.0,
        rng_checkpoint=rng -> (counter=rng.counter,),
    )
    @test S.checkpoint_snapshot(mutable_rng_context).rng_state == (counter=7,)
end

@testset "search status vocabulary cannot assert false completeness" begin
    statuses = string.(instances(S.SearchLoopStatus))
    @test all(status -> !occursin("NO_SOLUTION", status), statuses)
    @test all(status -> !occursin("COMPLETE", status), statuses)
    @test all(status -> !occursin("EMPTY", status), statuses)

    source = join(
        read.(
            [
                joinpath(@__DIR__, "..", "GeoTargetCore", "src", file) for file in
                ("events.jl", "candidate_store.jl", "search_policy.jl", "search_loop.jl")
            ],
            String,
        ),
        "\n",
    )
    @test !occursin("NO_SOLUTION", source)
end
