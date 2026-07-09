using GeoTargetBase
using GeoTargetCore
using Test
using UUIDs

const C = GeoTargetCore
const TEST_PLUGIN = PluginId(
    UUID("3eca5164-eb64-43f1-90d5-6d857dc3486f"),
    "proposal_engine_fixture",
)
const TEST_TYPE = TypeId(TEST_PLUGIN, "real")
const TEST_LOCK = PluginLock(
    TEST_PLUGIN,
    v"0.1.0",
    v"1.0.0",
    content_hash("proposal-engine-fixture-v1"),
)

struct FakeRNG
    state::UInt64
end

mutable struct FakeClock
    value::Float64
end

(clock::FakeClock)() = clock.value

function make_problem(variables; operation_name=nothing)
    if isempty(variables)
        graph = ConstructionGraph((LiteralNode(NodeId("target"), TEST_TYPE, 0.0),))
        return ProblemSpecV1((TEST_LOCK,), (), graph; target=NodeId("target"))
    end
    reference = ReferenceNode(NodeId("x_reference"), first(variables).id)
    if operation_name === nothing
        graph = ConstructionGraph((reference,))
        target = reference.id
    else
        target_node = CallNode(
            NodeId("target"),
            PrimitiveId(TEST_PLUGIN, operation_name),
            (reference.id,),
        )
        graph = ConstructionGraph((reference, target_node))
        target = target_node.id
    end
    return ProblemSpecV1(
        (TEST_LOCK,),
        Tuple(variables),
        graph;
        target,
    )
end

function variable(
    name,
    origin,
    scale;
    lower=nothing,
    upper=nothing,
)
    return VariableSpec(
        VariableId(name),
        TEST_TYPE,
        origin,
        scale;
        lower,
        upper,
    )
end

function mixed_problem()
    return make_problem((
        variable("bounded", 0.0, 1.0; lower=-2.0, upper=3.0),
        variable("lower_only", 1.0, 2.0; lower=0.0),
        variable("upper_only", -1.0, 3.0; upper=0.0),
        variable("two_sided", 0.0, 1.0),
    ))
end

function resume_identity(label="proposal-engine")
    return ResumeIdentity(
        content_hash("graph-$label"),
        (),
        content_hash("policy-$label"),
        content_hash("environment-$label"),
    )
end

function context_for(
    ;
    rng=FakeRNG(1),
    workspace=C.SearchWorkspace(adaptive_unbounded=true),
    deadline=1.0e9,
)
    return C.ExecutionContext(
        resume_identity();
        rng,
        registry=:proposal_test_registry,
        policy=C.thorough_policy(),
        workspace,
        clock=FakeClock(0.0),
        deadline,
    )
end

metadata(proposal) = Dict(proposal.metadata)

function proposal_at(engine, context, lane, task; shell=nothing, source=nothing)
    decision = C.ScheduleDecision(
        lane,
        task;
        shell,
        source_configuration=source,
    )
    return C.emit_proposal(engine, context, decision)
end

@testset "geometry-agnostic variable-only construction" begin
    variables = mixed_problem().variables
    geometry_named = make_problem(variables; operation_name="circle_intersection_magic")
    opaque_named = make_problem(variables; operation_name="opaque_post_freeze_plugin")
    first_engine = C.ProposalEngine(geometry_named; seed=17)
    second_engine = C.ProposalEngine(opaque_named; seed=17)
    context = context_for()

    for lane in (C.LANE_IID, C.LANE_HEURISTIC)
        first = proposal_at(first_engine, context, lane, 41)
        second = proposal_at(second_engine, context, lane, 41)
        @test first.coordinates == second.coordinates
    end
    first_shell = proposal_at(first_engine, context, C.LANE_SHELL, 42; shell=3)
    second_shell = proposal_at(second_engine, context, C.LANE_SHELL, 42; shell=3)
    @test first_shell.coordinates == second_shell.coordinates

    @test isimmutable(first_engine)
    @test C._freeze_search_value(first_engine) === first_engine
    @test fieldnames(C.ProposalEngine) == (:seed, :variables, :unbounded_dimensions)
    source = read(
        joinpath(@__DIR__, "..", "GeoTargetCore", "src", "proposal_engine.jl"),
        String,
    )
    @test !occursin("problem.graph", source)
    @test !occursin("PrimitiveId", source)
    @test !occursin(r"\b(Point2|Line2|Circle2|Intersect|Circumcircle)\b", source)
end

@testset "counter IID 10k prefix is finite, replayable, and full-support structured" begin
    problem = mixed_problem()
    engine = C.ProposalEngine(problem; seed=123456)
    context = context_for(rng=FakeRNG(1))
    count = 10_000
    starts = Matrix{Float64}(undef, 4, count)
    for task in 1:count
        proposal = proposal_at(engine, context, C.LANE_IID, task)
        starts[:, task] .= proposal.coordinates
        @test metadata(proposal)[:tail] === :pareto_log_uniform_mixture
    end
    @test all(isfinite, starts)
    @test all(-2.0 .<= starts[1, :] .<= 3.0)
    @test all(starts[2, :] .>= 0.0)
    @test all(starts[3, :] .<= 0.0)
    @test any(starts[2, :] .< 1.0)
    @test any(starts[2, :] .> 100.0)
    @test any(starts[3, :] .> -1.0)
    @test any(starts[3, :] .< -100.0)
    @test any(starts[4, :] .< 0.0)
    @test any(starts[4, :] .> 0.0)
    @test maximum(abs, starts[4, :]) > 1.0e50

    bins = zeros(Int, 10)
    for value in starts[1, :]
        index = clamp(floor(Int, 10 * (value + 2) / 5) + 1, 1, 10)
        bins[index] += 1
    end
    @test all(>(800), bins)
    @test length(unique(starts[1, :])) == count
    @test metadata(proposal_at(engine, context, C.LANE_IID, 1))[:seed] == UInt64(123456)

    repeated = [
        proposal_at(engine, context, C.LANE_IID, task).coordinates for task in 1:100
    ]
    @test repeated == [Tuple(starts[:, task]) for task in 1:100]
    different_seed = C.ProposalEngine(problem; seed=123457)
    @test any(
        proposal_at(engine, context, C.LANE_IID, task).coordinates !=
        proposal_at(different_seed, context, C.LANE_IID, task).coordinates for task in 1:100
    )

    different_rng_context = context_for(rng=FakeRNG(0xffff))
    @test all(
        proposal_at(engine, context, C.LANE_IID, task).coordinates ==
        proposal_at(engine, different_rng_context, C.LANE_IID, task).coordinates for
        task in 1:100
    )

    reverse_results = Dict{Int,Tuple}()
    for task in count:-1:(count - 999)
        reverse_results[task] = proposal_at(engine, context, C.LANE_IID, task).coordinates
    end
    @test all(reverse_results[task] == Tuple(starts[:, task]) for task in keys(reverse_results))

    threaded = Vector{Tuple}(undef, 1_000)
    Base.Threads.@threads for task in 1:1_000
        threaded[task] = proposal_at(engine, context, C.LANE_IID, task).coordinates
    end
    @test threaded == [Tuple(starts[:, task]) for task in 1:1_000]

    source = read(
        joinpath(@__DIR__, "..", "GeoTargetCore", "src", "proposal_engine.jl"),
        String,
    )
    @test !occursin("using Random", source)
    @test !occursin(r"\brand\s*\(", source)
    @test !occursin("GLOBAL_RNG", source)
end

@testset "Halton normalized coverage and documented high-dimensional fallback" begin
    bounded = make_problem((
        variable("x", 0.0, 1.0; lower=0.0, upper=1.0),
        variable("y", 0.0, 1.0; lower=0.0, upper=1.0),
    ))
    engine = C.ProposalEngine(bounded; seed=9)
    context = context_for(workspace=C.SearchWorkspace())
    grid = zeros(Int, 10, 10)
    values = Matrix{Float64}(undef, 2, 10_000)
    for task in 1:10_000
        proposal = proposal_at(engine, context, C.LANE_HEURISTIC, task)
        values[:, task] .= proposal.coordinates
        @test metadata(proposal)[:sequence] === :halton
        xbin = clamp(floor(Int, 10 * proposal.coordinates[1]) + 1, 1, 10)
        ybin = clamp(floor(Int, 10 * proposal.coordinates[2]) + 1, 1, 10)
        grid[xbin, ybin] += 1
    end
    @test all(isfinite, values)
    @test all(>(70), grid)
    @test abs(sum(values[1, :]) / 10_000 - 0.5) < 5.0e-3
    @test abs(sum(values[2, :]) / 10_000 - 0.5) < 5.0e-3

    high_variables = Tuple(
        variable("x$index", 0.0, 1.0; lower=-1.0, upper=1.0) for index in 1:65
    )
    high_engine = C.ProposalEngine(make_problem(high_variables); seed=9)
    high = proposal_at(high_engine, context, C.LANE_HEURISTIC, 77)
    @test metadata(high)[:sequence] === :counter_fallback
    @test metadata(high)[:halton_dimension_limit] == 64
    @test length(high.coordinates) == 65
    @test all(isfinite, high.coordinates)
    @test all(-1.0 .<= collect(high.coordinates) .<= 1.0)
end

@testset "ruler shell proposals hit every finite dyadic max-norm shell" begin
    problem = mixed_problem()
    engine = C.ProposalEngine(problem; seed=777)
    context = context_for()
    for shell in 0:20
        proposal = proposal_at(engine, context, C.LANE_SHELL, shell + 1; shell)
        info = metadata(proposal)
        @test info[:sequence] === :dyadic_ruler_shell
        @test info[:shell] == shell
        @test all(isfinite, proposal.coordinates)
        @test -2.0 <= proposal.coordinates[1] <= 3.0
        anchor = info[:anchor_dimension]
        variable_spec = problem.variables[anchor]
        normalized = abs(
            (proposal.coordinates[anchor] - Float64(variable_spec.origin)) /
            Float64(variable_spec.scale),
        )
        @test normalized >= info[:normalized_inner]
        @test normalized <= info[:normalized_outer]
        @test info[:shell_space] === :unbounded_dimensions_max_norm
        unbounded_max_norm = maximum(
            abs(
                (proposal.coordinates[index] - Float64(problem.variables[index].origin)) /
                Float64(problem.variables[index].scale),
            ) for index in 2:4
        )
        @test unbounded_max_norm >= info[:normalized_inner]
        @test unbounded_max_norm <= info[:normalized_outer]
    end

    seen_shells = Set{Int}()
    for tick in 1:16_384
        shell = C.ruler_shell(tick)
        push!(seen_shells, shell)
        proposal = proposal_at(engine, context, C.LANE_SHELL, tick; shell)
        @test all(isfinite, proposal.coordinates)
    end
    @test issubset(Set(0:13), seen_shells)

    bounded = make_problem((variable("x", 0.0, 1.0; lower=-1.0, upper=1.0),))
    bounded_engine = C.ProposalEngine(bounded; seed=1)
    @test_throws C.ProposalEngineError proposal_at(
        bounded_engine,
        context,
        C.LANE_SHELL,
        1;
        shell=0,
    )
    @test_throws C.ProposalEngineError proposal_at(
        engine,
        context,
        C.LANE_SHELL,
        1;
        shell=1023,
    )
end

@testset "refinement is source-bound, shrinking, finite, and configuration-preserving" begin
    problem = mixed_problem()
    engine = C.ProposalEngine(problem; seed=31337)
    context = context_for()
    source = C.Proposal(1, 42, C.LANE_IID, (1.0, 2.0, -2.0, 0.5))
    source_observation = C.Observation(
        1,
        42;
        canonical_near_feasible=false,
        needs_refinement=true,
        oracle_work=1,
        endpoint=(0.75, 1.5, -1.5, 0.25),
    )
    C.insert_candidate!(context.workspace.candidates, source, source_observation)

    first = proposal_at(engine, context, C.LANE_REFINEMENT, 100; source=42)
    repeated = proposal_at(engine, context, C.LANE_REFINEMENT, 100; source=42)
    @test first.coordinates == repeated.coordinates
    @test first.configuration_id == UInt64(42)
    @test first.source_configuration == UInt64(42)
    @test all(isfinite, first.coordinates)
    @test -2.0 <= first.coordinates[1] <= 3.0
    @test first.coordinates[2] >= 0.0
    @test first.coordinates[3] <= 0.0
    @test metadata(first)[:source_revision] == 1
    @test metadata(first)[:source_kind] === :endpoint
    @test metadata(first)[:normalized_radius] == 0.5
    endpoint = source_observation.endpoint
    for index in 1:4
        change = abs(first.coordinates[index] - endpoint[index])
        @test change <= 0.5 * Float64(problem.variables[index].scale) +
              2 * eps(abs(endpoint[index]) + 1)
    end

    first_observation = C.Observation(
        first.task_id,
        42;
        canonical_near_feasible=false,
        needs_refinement=true,
        oracle_work=1,
        endpoint=first.coordinates,
    )
    C.insert_candidate!(context.workspace.candidates, first, first_observation)
    second = proposal_at(engine, context, C.LANE_REFINEMENT, 101; source=42)
    @test metadata(second)[:source_revision] == 2
    @test metadata(second)[:normalized_radius] == 0.25
    for index in 1:4
        change = abs(second.coordinates[index] - first.coordinates[index])
        @test change <= 0.25 * Float64(problem.variables[index].scale) +
              2 * eps(abs(first.coordinates[index]) + 1)
    end

    missing = context_for()
    @test_throws C.ProposalEngineError proposal_at(
        engine,
        missing,
        C.LANE_REFINEMENT,
        102;
        source=999,
    )

    invalid_context = context_for()
    outside = C.Proposal(2, 43, C.LANE_IID, (9.0, 2.0, -2.0, 0.5))
    outside_observation = C.Observation(
        2,
        43;
        canonical_near_feasible=false,
        needs_refinement=true,
    )
    C.insert_candidate!(
        invalid_context.workspace.candidates,
        outside,
        outside_observation,
    )
    @test_throws C.ProposalEngineError proposal_at(
        engine,
        invalid_context,
        C.LANE_REFINEMENT,
        103;
        source=43,
    )
end

@testset "extreme and degenerate metadata fail closed or remain finite" begin
    adjacent_lower = prevfloat(floatmax(Float64))
    adjacent = make_problem((
        variable(
            "adjacent",
            adjacent_lower,
            1.0;
            lower=adjacent_lower,
            upper=floatmax(Float64),
        ),
        variable("huge_scale", 0.0, 1.0e300),
        variable("tiny_scale", 0.0, nextfloat(0.0)),
        variable("one_sided", 0.0, 1.0e300; lower=-1.0e300),
    ))
    engine = C.ProposalEngine(adjacent; seed=44)
    context = context_for()
    for lane in (C.LANE_IID, C.LANE_HEURISTIC)
        for task in 1:1_000
            proposal = proposal_at(engine, context, lane, task)
            @test all(isfinite, proposal.coordinates)
            @test adjacent_lower <= proposal.coordinates[1] <= floatmax(Float64)
            @test proposal.coordinates[4] >= -1.0e300
        end
    end

    big = BigFloat
    unrepresentable = make_problem((
        variable("too_large", big(0), big"1e1000"),
    ))
    @test_throws C.ProposalEngineError C.ProposalEngine(unrepresentable; seed=1)
    @test_throws C.ProposalEngineError C.ProposalEngine(make_problem(()); seed=1)
    @test_throws InvariantError variable(
        "degenerate",
        1.0,
        1.0;
        lower=1.0,
        upper=1.0,
    )

    no_outward_float = make_problem((
        variable(
            "max_lower",
            floatmax(Float64),
            1.0;
            lower=floatmax(Float64),
        ),
    ))
    @test_throws C.ProposalEngineError C.ProposalEngine(no_outward_float; seed=1)
end

@testset "ProposalEngine plugs directly into the fair event loop" begin
    problem = mixed_problem()
    engine = C.ProposalEngine(problem; seed=2026)
    context = context_for()
    refined = Set{UInt64}()
    function observe(context, proposal)
        needs_refinement = proposal.lane !== C.LANE_REFINEMENT &&
                           !(proposal.configuration_id in refined)
        proposal.lane === C.LANE_REFINEMENT && push!(refined, proposal.configuration_id)
        return C.Observation(
            proposal.task_id,
            proposal.configuration_id;
            canonical_near_feasible=false,
            needs_refinement,
            oracle_work=1,
        )
    end
    result = C.run_search!(context, engine, observe; max_actions=5_000)
    @test result.status === C.LOOP_PAUSED
    @test context.budget.proposals > 500
    @test context.budget.refinements > 100
    @test all(
        all(isfinite, record.proposal.coordinates) for
        record in C.candidate_records(context.workspace.candidates)
    )
    @test any(
        record -> record.proposal.lane === C.LANE_SHELL,
        C.candidate_records(context.workspace.candidates),
    )
    @test any(
        record -> record.proposal.lane === C.LANE_REFINEMENT,
        C.candidate_records(context.workspace.candidates),
    )
end
