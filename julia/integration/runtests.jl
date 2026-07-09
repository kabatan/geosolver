using GeoTargetBase
using GeoTargetCore
using GeoTargetGeometry
using Test

const REPOSITORY_ROOT = normpath(joinpath(@__DIR__, "..", ".."))

@testset "GeoTarget workspace" begin
    include(joinpath(@__DIR__, "..", "GeoTargetBase", "test", "runtests.jl"))
    include(joinpath(@__DIR__, "..", "GeoTargetCore", "test", "runtests.jl"))
    include(joinpath(@__DIR__, "..", "GeoTargetGeometry", "test", "runtests.jl"))
end

@testset "Dependency direction" begin
    core_source = read(
        joinpath(@__DIR__, "..", "GeoTargetCore", "src", "GeoTargetCore.jl"),
        String,
    )
    @test !occursin("GeoTargetGeometry", core_source)
end

@testset "Open-world plugins pass through Core without special cases" begin
    geometry = GeoTargetGeometry.geometry_plugin()
    arc = ArcPlugin.arc_plugin()
    opaque = OpaquePlugin.opaque_plugin()
    builder = RegistryBuilder(allowlist = (geometry.id, arc.id, opaque.id))
    register!(builder, geometry)
    register!(builder, arc)
    register!(builder, opaque)
    registry = freeze(builder)
    @test length(registered_plugins(registry)) == 3

    variable = VariableSpec(
        VariableId("x"),
        GeoTargetGeometry.SCALAR_TYPE_ID,
        1.0,
        1.0;
        lower = -2.0,
        upper = 2.0,
    )
    plugin = GeoTargetGeometry.GEOMETRY_PLUGIN_ID
    graph = ConstructionGraph((
        ReferenceNode(NodeId("x_ref"), variable.id),
        LiteralNode(NodeId("zero"), GeoTargetGeometry.SCALAR_TYPE_ID, 0.0),
        LiteralNode(NodeId("one"), GeoTargetGeometry.SCALAR_TYPE_ID, 1.0),
        CallNode(
            NodeId("point"),
            PrimitiveId(plugin, "point2"),
            (NodeId("x_ref"), NodeId("zero")),
        ),
        CallNode(
            NodeId("origin"),
            PrimitiveId(plugin, "point2"),
            (NodeId("zero"), NodeId("zero")),
        ),
        CallNode(
            NodeId("target"),
            PrimitiveId(plugin, "distance"),
            (NodeId("point"), NodeId("origin")),
        ),
        CallNode(
            NodeId("relation"),
            PrimitiveId(plugin, "scalar_equality"),
            (NodeId("target"), NodeId("one")),
        ),
        CallNode(
            NodeId("guard"),
            PrimitiveId(plugin, "positive"),
            (NodeId("x_ref"),),
        ),
    ))
    problem = ProblemSpecV1(
        (plugin_lock(geometry),),
        (variable,),
        graph;
        relations = (RelationBinding(NodeId("relation")),),
        guards = (GuardBinding(NodeId("guard"), true),),
        target = NodeId("target"),
    )
    report = validate_problem(problem, registry)
    @test isempty(report)
    observation = evaluate_reference(problem, registry, [1.0])
    @test observation.status == EVAL_OK
    @test observation.target == 1.0
    @test canonical_feasible(observation; residual_tolerance = 0.0)
end

include(joinpath(@__DIR__, "local_solver_runtests.jl"))
include(joinpath(@__DIR__, "search_runtests.jl"))
include(joinpath(@__DIR__, "protocol_runtests.jl"))
include(joinpath(@__DIR__, "compiler_runtests.jl"))
include(joinpath(@__DIR__, "proposal_engine_runtests.jl"))
include(joinpath(@__DIR__, "candidate_validation_runtests.jl"))
include(joinpath(@__DIR__, "solver_runtests.jl"))
include(joinpath(@__DIR__, "target_image_runtests.jl"))
