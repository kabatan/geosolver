module EndToEndSolveTests

using GeoTargetBase
using GeoTargetCore
using GeoTargetGeometry
using Test

function solve_registry()
    plugin = geometry_plugin()
    builder = RegistryBuilder(allowlist=(plugin.id,))
    register!(builder, plugin)
    return freeze(builder)
end

function scalar_root_problem(root=1.0; guard=false)
    plugin = geometry_plugin()
    lower, upper = root > 0 ? (-2.0, 2.0) : (-2.0, 0.0)
    variable = VariableSpec(
        VariableId("x"),
        SCALAR_TYPE_ID,
        0.0,
        1.0;
        lower,
        upper,
    )
    nodes = AbstractGraphNode[
        ReferenceNode(NodeId("x"), variable.id),
        LiteralNode(NodeId("root"), SCALAR_TYPE_ID, root),
        CallNode(
            NodeId("relation"),
            PrimitiveId(plugin.id, "scalar_equality"),
            (NodeId("x"), NodeId("root")),
        ),
    ]
    guards = ()
    if guard
        push!(
            nodes,
            CallNode(
                NodeId("guard"),
                PrimitiveId(plugin.id, "positive"),
                (NodeId("x"),),
            ),
        )
        guards = (GuardBinding(NodeId("guard"), true),)
    end
    return ProblemSpecV1(
        (plugin_lock(plugin),),
        (variable,),
        ConstructionGraph(Tuple(nodes));
        relations=(RelationBinding(NodeId("relation")),),
        guards,
        target=NodeId("x"),
    )
end

function constant_problem(value=3.5)
    plugin = geometry_plugin()
    graph = ConstructionGraph((LiteralNode(NodeId("target"), SCALAR_TYPE_ID, value),))
    return ProblemSpecV1(
        (plugin_lock(plugin),),
        (),
        graph;
        target=NodeId("target"),
    )
end

function short_options(; kwargs...)
    return SolveOptions(; preset=:fast, wall_seconds=60.0, seed=17, kwargs...)
end

@testset "public solve path returns canonical provisional evidence" begin
    registry = solve_registry()
    problem = scalar_root_problem()
    execution = solve_execution(
        problem,
        registry;
        options=short_options(),
        max_actions=2,
    )
    result = execution.result
    @test execution.loop_status == GeoTargetCore.LOOP_PAUSED
    @test result.search_status == SEARCH_FINISHED_UNKNOWN
    @test result.target_image_status == TARGET_FINITE_OBSERVED
    @test isempty(result.exact_answers)
    @test length(result.provisional_answers) == 1
    answer = only(result.provisional_answers)
    @test answer.target.lower <= BigFloat(1) <= answer.target.upper
    @test answer.validation.method == "canonical_bigfloat_recheck"
    @test answer.validation.precision_bits == 256
    @test answer.exact_failure == EXACT_CAPABILITY_MISSING
    @test result.coverage.proposed_tasks == 1
    @test result.coverage.completed_tasks == 1
    @test result.coverage.pending_tasks == 0
    @test result.coverage.independent_waves == 1

    @test result.evidence_log.content == content_hash(execution.evidence_json)
    @test result.evidence_log.location == "memory:$(string(result.evidence_log.content))"
    evidence = parse_protocol_json(execution.evidence_json)
    @test evidence["schema"] == "geotarget.evidence-log/v1"
    @test length(evidence["events"]) >= 8
    @test canonical_json(evidence) == execution.evidence_json

    encoded = encode_solve_result_json(result)
    decoded = decode_solve_result_json(encoded)
    @test encode_solve_result_json(decoded) == encoded
    @test decoded.search_status == SEARCH_FINISHED_UNKNOWN
end

@testset "replay is deterministic and longer action prefixes retain answers" begin
    registry = solve_registry()
    problem = scalar_root_problem()
    first = solve_execution(problem, registry; options=short_options(), max_actions=2)
    replay = solve_execution(problem, registry; options=short_options(), max_actions=2)
    @test replay.evidence_json == first.evidence_json
    @test map(answer -> answer.validation.artifact.digest, replay.result.provisional_answers) ==
          map(answer -> answer.validation.artifact.digest, first.result.provisional_answers)

    longer = solve_execution(problem, registry; options=short_options(), max_actions=4)
    @test length(longer.result.provisional_answers) == 2
    first_digest = only(first.result.provisional_answers).validation.artifact.digest
    @test first_digest in (
        answer.validation.artifact.digest for answer in longer.result.provisional_answers
    )
end

@testset "strict guard, cancellation and deadlines never claim false certainty" begin
    registry = solve_registry()
    invalid = solve_execution(
        scalar_root_problem(-1.0; guard=true),
        registry;
        options=short_options(),
        max_actions=2,
    )
    @test isempty(invalid.result.provisional_answers)
    @test invalid.result.target_image_status == TARGET_IMAGE_UNKNOWN
    @test invalid.result.search_status == SEARCH_FINISHED_UNKNOWN

    token = CancellationToken()
    cancel!(token)
    cancelled = solve_execution(
        scalar_root_problem(),
        registry;
        options=short_options(),
        cancel=token,
    )
    @test cancelled.result.search_status == SEARCH_CANCELLED
    @test isempty(cancelled.result.provisional_answers)
    @test cancelled.result.target_image_status == TARGET_IMAGE_UNKNOWN

    deadline = solve_execution(
        scalar_root_problem(),
        registry;
        options=SolveOptions(preset=:fast, wall_seconds=1.0e-9),
    )
    @test deadline.result.search_status == SEARCH_DEADLINE_REACHED
    @test isempty(deadline.result.provisional_answers)
    @test deadline.result.search_status ∉ (SEARCH_COMPLETE_CERTIFIED, SEARCH_EMPTY_CERTIFIED)
end

@testset "constant problems and materialized evidence use the same result contract" begin
    registry = solve_registry()
    destination = tempname() * ".json"
    execution = solve_execution(
        constant_problem(),
        registry;
        options=short_options(),
        evidence_path=destination,
    )
    @test execution.loop_status == GeoTargetCore.LOOP_PAUSED
    @test length(execution.result.provisional_answers) == 1
    answer = only(execution.result.provisional_answers)
    @test answer.target.lower <= BigFloat(3.5) <= answer.target.upper
    @test execution.result.evidence_log.location == abspath(destination)
    @test read(destination, String) == execution.evidence_json
    @test content_hash(read(destination)) == execution.result.evidence_log.content
    rm(destination; force=true)
end

@testset "stable options reject unsupported execution expansion" begin
    @test SolveOptions(preset="default").preset == :standard
    @test SolveOptions(answer_level="validated").answer_level == ANSWER_VALIDATED
    @test_throws SolveConfigurationError SolveOptions(preset=:unknown)
    @test_throws SolveConfigurationError SolveOptions(wall_seconds=0)
    @test_throws SolveConfigurationError SolveOptions(seed=big(2)^80)
    @test_throws SolveConfigurationError solve_execution(
        scalar_root_problem(),
        solve_registry();
        options=SolveOptions(worker_count=2),
    )
end

end
