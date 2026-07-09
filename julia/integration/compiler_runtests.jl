using GeoTargetBase
using GeoTargetCore
using GeoTargetGeometry
using Random
using Test

if !isdefined(GeoTargetCore, :CompiledProblem)
    Base.include(GeoTargetCore, joinpath(@__DIR__, "..", "GeoTargetCore", "src", "compiler.jl"))
    Base.include(
        GeoTargetCore,
        joinpath(@__DIR__, "..", "GeoTargetCore", "src", "compiled_oracle.jl"),
    )
end

if !isdefined(Main, :OpaquePlugin)
    include(joinpath(@__DIR__, "..", "fixtures", "OpaquePlugin", "src", "OpaquePlugin.jl"))
end
using .OpaquePlugin

const INVALID_BRANCH_PLUGIN =
    parse(PluginId, "6ab3e69c-0616-4e6f-a438-586f506e0210/invalid_branch_fixture")
const ROUTE_PLUGIN =
    parse(PluginId, "fef21c51-ad72-4705-8294-c0b99acc148c/capability_route_fixture")

function route_plugin()
    signature = SignatureSpec((SCALAR_TYPE_ID,), SCALAR_TYPE_ID)
    primitive = PrimitiveSpec(
        PrimitiveId(ROUTE_PLUGIN, "dedicated_high_precision"),
        (signature,),
        OperatorKernel(
            identity;
            high_precision = value -> value + 100,
            capabilities = CapabilitySet(C0, C2),
            smoothness = SMOOTH_C1,
        ),
    )
    return PluginSpec(
        ROUTE_PLUGIN,
        v"0.1.0",
        GeoTargetCore.CORE_ABI_VERSION,
        content_hash("capability-route-fixture-v1");
        primitives = (primitive,),
    )
end

function invalid_branch_plugin()
    signature = SignatureSpec((SCALAR_TYPE_ID,), CHOICE_TYPE_ID)
    branch = BranchSpec(
        PrimitiveId(INVALID_BRANCH_PLUGIN, "invalid_point"),
        (signature,),
        POINT_TYPE_ID,
        OperatorKernel(
            value -> Choice(
                (point2(value, zero(value)),),
                ("invalid",),
                (-one(value),),
            );
            capabilities = CapabilitySet(C0, C2),
            generic_numeric = true,
            smoothness = SMOOTH_C1,
        ),
    )
    return PluginSpec(
        INVALID_BRANCH_PLUGIN,
        v"0.1.0",
        GeoTargetCore.CORE_ABI_VERSION,
        content_hash("invalid-branch-fixture-v1");
        branches = (branch,),
    )
end

function compiler_registry(; invalid_branch = false)
    geometry = geometry_plugin()
    opaque = opaque_plugin()
    route = route_plugin()
    extra = invalid_branch ? (invalid_branch_plugin(),) : ()
    plugins = (geometry, opaque, route, extra...)
    builder = RegistryBuilder(allowlist = Tuple(plugin.id for plugin in plugins))
    foreach(plugin -> register!(builder, plugin), plugins)
    return freeze(builder)
end

function capability_constant_problem(; dedicated_route = false)
    geometry = geometry_plugin()
    plugin = dedicated_route ? route_plugin() : opaque_plugin()
    operation = dedicated_route ?
                PrimitiveId(ROUTE_PLUGIN, "dedicated_high_precision") :
                PrimitiveId(OPAQUE_PLUGIN_ID, "float64_only")
    graph = ConstructionGraph((
        LiteralNode(NodeId("one"), SCALAR_TYPE_ID, 1.0),
        CallNode(NodeId("target"), operation, (NodeId("one"),)),
    ))
    return ProblemSpecV1(
        (plugin_lock(geometry), plugin_lock(plugin)),
        (),
        graph;
        target = NodeId("target"),
    )
end

function smooth_problem(; variable_scale = 1.0)
    geometry = geometry_plugin()
    x = VariableSpec(
        VariableId("x"),
        SCALAR_TYPE_ID,
        0.5,
        variable_scale;
        lower = -2.0,
        upper = 2.0,
    )
    y = VariableSpec(
        VariableId("y"),
        SCALAR_TYPE_ID,
        0.25,
        1.0;
        lower = -2.0,
        upper = 2.0,
    )
    plugin = GEOMETRY_PLUGIN_ID
    graph = ConstructionGraph((
        ReferenceNode(NodeId("x_ref"), x.id),
        ReferenceNode(NodeId("y_ref"), y.id),
        LiteralNode(NodeId("zero"), SCALAR_TYPE_ID, 0.0),
        LiteralNode(NodeId("one"), SCALAR_TYPE_ID, 1.0),
        CallNode(
            NodeId("point"),
            PrimitiveId(plugin, "point2"),
            (NodeId("x_ref"), NodeId("y_ref")),
        ),
        CallNode(
            NodeId("origin"),
            PrimitiveId(plugin, "point2"),
            (NodeId("zero"), NodeId("zero")),
        ),
        CallNode(
            NodeId("line"),
            PrimitiveId(plugin, "line_through"),
            (NodeId("origin"), NodeId("point")),
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
        CallNode(
            NodeId("domain"),
            PrimitiveId(plugin, "safe_geometry_domain"),
            (NodeId("line"),),
        ),
    ))
    return ProblemSpecV1(
        (plugin_lock(geometry),),
        (x, y),
        graph;
        relations = (RelationBinding(NodeId("relation")),),
        guards = (GuardBinding(NodeId("guard"), true),),
        domains = (DomainBinding(NodeId("domain"), true),),
        target = NodeId("target"),
    )
end

function branch_problem(; tie = false)
    geometry = geometry_plugin()
    y = VariableSpec(
        VariableId("y"),
        SCALAR_TYPE_ID,
        0.0,
        1.0;
        lower = -3.0,
        upper = 3.0,
    )
    plugin = GEOMETRY_PLUGIN_ID
    reference_x = tie ? 0.0 : -2.0
    graph = ConstructionGraph((
        ReferenceNode(NodeId("y_ref"), y.id),
        LiteralNode(NodeId("minus_two"), SCALAR_TYPE_ID, -2.0),
        LiteralNode(NodeId("plus_two"), SCALAR_TYPE_ID, 2.0),
        LiteralNode(NodeId("zero"), SCALAR_TYPE_ID, 0.0),
        LiteralNode(NodeId("one"), SCALAR_TYPE_ID, 1.0),
        LiteralNode(NodeId("reference_x"), SCALAR_TYPE_ID, reference_x),
        CallNode(
            NodeId("line_start"),
            PrimitiveId(plugin, "point2"),
            (NodeId("minus_two"), NodeId("y_ref")),
        ),
        CallNode(
            NodeId("line_stop"),
            PrimitiveId(plugin, "point2"),
            (NodeId("plus_two"), NodeId("y_ref")),
        ),
        CallNode(
            NodeId("line"),
            PrimitiveId(plugin, "line_through"),
            (NodeId("line_start"), NodeId("line_stop")),
        ),
        CallNode(
            NodeId("origin"),
            PrimitiveId(plugin, "point2"),
            (NodeId("zero"), NodeId("zero")),
        ),
        CallNode(
            NodeId("circle"),
            PrimitiveId(plugin, "circle2"),
            (NodeId("origin"), NodeId("one")),
        ),
        CallNode(
            NodeId("choices"),
            PrimitiveId(plugin, "line_circle_intersections"),
            (NodeId("line"), NodeId("circle")),
        ),
        CallNode(
            NodeId("reference"),
            PrimitiveId(plugin, "point2"),
            (NodeId("reference_x"), NodeId("zero")),
        ),
        SelectNode(
            NodeId("selected"),
            NodeId("choices"),
            SelectorId(plugin, "near"),
            (NodeId("reference"),),
        ),
        CallNode(
            NodeId("target"),
            PrimitiveId(plugin, "distance"),
            (NodeId("selected"), NodeId("origin")),
        ),
        CallNode(
            NodeId("relation"),
            PrimitiveId(plugin, "scalar_equality"),
            (NodeId("target"), NodeId("one")),
        ),
        CallNode(
            NodeId("line_domain"),
            PrimitiveId(plugin, "safe_geometry_domain"),
            (NodeId("line"),),
        ),
        CallNode(
            NodeId("circle_domain"),
            PrimitiveId(plugin, "safe_geometry_domain"),
            (NodeId("circle"),),
        ),
    ))
    return ProblemSpecV1(
        (plugin_lock(geometry),),
        (y,),
        graph;
        relations = (RelationBinding(NodeId("relation")),),
        domains = (
            DomainBinding(NodeId("line_domain"), true),
            DomainBinding(NodeId("circle_domain"), true),
        ),
        target = NodeId("target"),
    )
end

function invalid_branch_problem()
    geometry = geometry_plugin()
    bad = invalid_branch_plugin()
    x = VariableSpec(VariableId("x"), SCALAR_TYPE_ID, 1.0, 1.0)
    graph = ConstructionGraph((
        ReferenceNode(NodeId("x_ref"), x.id),
        LiteralNode(NodeId("zero"), SCALAR_TYPE_ID, 0.0),
        CallNode(
            NodeId("choices"),
            PrimitiveId(INVALID_BRANCH_PLUGIN, "invalid_point"),
            (NodeId("x_ref"),),
        ),
        CallNode(
            NodeId("origin"),
            PrimitiveId(GEOMETRY_PLUGIN_ID, "point2"),
            (NodeId("zero"), NodeId("zero")),
        ),
        SelectNode(
            NodeId("selected"),
            NodeId("choices"),
            SelectorId(GEOMETRY_PLUGIN_ID, "near"),
            (NodeId("origin"),),
        ),
        CallNode(
            NodeId("target"),
            PrimitiveId(GEOMETRY_PLUGIN_ID, "distance"),
            (NodeId("selected"), NodeId("origin")),
        ),
    ))
    return ProblemSpecV1(
        (plugin_lock(geometry), plugin_lock(bad)),
        (x,),
        graph;
        target = NodeId("target"),
    )
end

function opaque_problem(; float64_only_path = false)
    geometry = geometry_plugin()
    opaque = opaque_plugin()
    x = VariableSpec(
        VariableId("x"),
        SCALAR_TYPE_ID,
        0.5,
        1.0;
        lower = -2.0,
        upper = 2.0,
    )
    nodes = if float64_only_path
        (
            ReferenceNode(NodeId("x_ref"), x.id),
            CallNode(
                NodeId("target"),
                PrimitiveId(OPAQUE_PLUGIN_ID, "float64_only"),
                (NodeId("x_ref"),),
            ),
        )
    else
        (
            ReferenceNode(NodeId("x_ref"), x.id),
            CallNode(
                NodeId("opaque"),
                PrimitiveId(OPAQUE_PLUGIN_ID, "opaque_iterate"),
                (NodeId("x_ref"),),
            ),
            CallNode(
                NodeId("target"),
                PrimitiveId(OPAQUE_PLUGIN_ID, "opaque_scalar"),
                (NodeId("opaque"),),
            ),
            CallNode(
                NodeId("domain"),
                PrimitiveId(OPAQUE_PLUGIN_ID, "positive_log_domain"),
                (NodeId("x_ref"),),
            ),
        )
    end
    domains = float64_only_path ? () : (DomainBinding(NodeId("domain"), true),)
    return ProblemSpecV1(
        (plugin_lock(geometry), plugin_lock(opaque)),
        (x,),
        ConstructionGraph(nodes);
        domains,
        target = NodeId("target"),
    )
end

function folding_problem(; constant = 0.0)
    geometry = geometry_plugin()
    plugin = GEOMETRY_PLUGIN_ID
    graph = ConstructionGraph((
        LiteralNode(NodeId("zero_a"), SCALAR_TYPE_ID, constant),
        LiteralNode(NodeId("zero_b"), SCALAR_TYPE_ID, constant),
        LiteralNode(NodeId("unused"), SCALAR_TYPE_ID, 99.0),
        CallNode(
            NodeId("origin_a"),
            PrimitiveId(plugin, "point2"),
            (NodeId("zero_a"), NodeId("zero_a")),
        ),
        CallNode(
            NodeId("origin_b"),
            PrimitiveId(plugin, "point2"),
            (NodeId("zero_b"), NodeId("zero_b")),
        ),
        CallNode(
            NodeId("target"),
            PrimitiveId(plugin, "distance"),
            (NodeId("origin_a"), NodeId("origin_b")),
        ),
        CallNode(
            NodeId("relation"),
            PrimitiveId(plugin, "scalar_equality"),
            (NodeId("target"), NodeId("zero_a")),
        ),
    ))
    return ProblemSpecV1(
        (plugin_lock(geometry),),
        (),
        graph;
        relations = (RelationBinding(NodeId("relation")),),
        target = NodeId("target"),
    )
end

function semantic_projection(observation::OracleObservation)
    return (
        observation.status,
        observation.target,
        Tuple((r.node, r.raw, r.scale, r.scaled, r.truth) for r in observation.relations),
        Tuple((g.node, g.margin, g.strict, g.scale, g.valid) for g in observation.guards),
        Tuple((d.node, d.margin, d.strict, d.valid) for d in observation.domains),
        Tuple(
            (
                b.decision.choice_node,
                b.decision.key,
                b.validity_margin,
                b.selector_margin,
            ) for b in observation.branches
        ),
        observation.evaluation_cost,
    )
end

function test_differential(problem, registry, x; capability = C0)
    compiled = GeoTargetCore.compile_problem(problem, registry)
    reference = evaluate_reference(problem, registry, x; capability)
    observed = GeoTargetCore.evaluate(compiled, x; capability)
    @test semantic_projection(observed) == semantic_projection(reference)
    return compiled, observed
end


@testset "typed plan pre-resolves metadata and differential semantics" begin
    registry = compiler_registry()
    problem = smooth_problem()
    compiled = GeoTargetCore.compile_problem(problem, registry)
    @test compiled isa GeoTargetCore.CompiledProblem
    @test all(instruction -> !(instruction isa CallNode), compiled.instructions)
    @test all(pair -> last(pair) isa Int, compiled.node_slots)
    @test compiled.target_type == SCALAR_TYPE_ID
    @test compiled.cache_identity.persistent
    @test supports(GeoTargetCore.capabilities(compiled), C0)
    @test supports(GeoTargetCore.capabilities(compiled), C2)

    rng = MersenneTwister(0x5eed)
    workspace = GeoTargetCore.CompiledWorkspace(compiled)
    for _ in 1:50
        x = 6 .* rand(rng, 2) .- 3
        reference = evaluate_reference(problem, registry, x)
        observed = GeoTargetCore.evaluate(compiled, x; workspace)
        @test semantic_projection(observed) == semantic_projection(reference)
    end
    @test semantic_projection(GeoTargetCore.evaluate(compiled, [NaN, 1.0])) ==
          semantic_projection(evaluate_reference(problem, registry, [NaN, 1.0]))
    @test semantic_projection(GeoTargetCore.evaluate(compiled, [0.0, 0.0])) ==
          semantic_projection(evaluate_reference(problem, registry, [0.0, 0.0]))
end

@testset "branch, domain and capability statuses remain distinct" begin
    registry = compiler_registry(invalid_branch = true)
    valid, _ = test_differential(branch_problem(), registry, [0.0])
    @test GeoTargetCore.evaluate(valid, [0.0]).status == EVAL_OK

    tied, tie_observation = test_differential(branch_problem(tie = true), registry, [0.0])
    @test tie_observation.status == EVAL_AMBIGUOUS_BRANCH
    @test GeoTargetCore.evaluate(tied, [0.0]).branches[1].selector_margin == 0.0

    _, no_intersection = test_differential(branch_problem(), registry, [2.0])
    @test no_intersection.status == EVAL_PLUGIN_ERROR

    invalid_compiled, invalid_observation =
        test_differential(invalid_branch_problem(), registry, [1.0])
    @test invalid_observation.status == EVAL_INVALID_BRANCH
    @test GeoTargetCore.evaluate(invalid_compiled, [1.0]).branches[1].validity_margin < 0

    smooth = GeoTargetCore.compile_problem(smooth_problem(), registry)
    @test GeoTargetCore.evaluate(smooth, [3.0, 1.0]).status == EVAL_INVALID_DOMAIN
end

@testset "opaque custom values and C0/C2 routing" begin
    registry = compiler_registry()
    generic_problem = opaque_problem()
    generic = GeoTargetCore.compile_problem(generic_problem, registry)
    reference_big = evaluate_reference(generic_problem, registry, BigFloat[0.5]; capability = C2)
    compiled_big = GeoTargetCore.evaluate(generic, BigFloat[0.5]; capability = C2)
    @test semantic_projection(compiled_big) == semantic_projection(reference_big)
    @test compiled_big.target isa BigFloat

    negative_reference = evaluate_reference(generic_problem, registry, [-0.5])
    negative_compiled = GeoTargetCore.evaluate(generic, [-0.5])
    @test semantic_projection(negative_compiled) == semantic_projection(negative_reference)
    @test negative_compiled.status == EVAL_INVALID_DOMAIN

    c0_problem = opaque_problem(float64_only_path = true)
    c0_compiled = GeoTargetCore.compile_problem(c0_problem, registry)
    @test GeoTargetCore.evaluate(c0_compiled, [0.5]).status == EVAL_OK
    reference_unsupported = evaluate_reference(c0_problem, registry, BigFloat[0.5]; capability = C2)
    compiled_unsupported = GeoTargetCore.evaluate(c0_compiled, BigFloat[0.5]; capability = C2)
    @test semantic_projection(compiled_unsupported) == semantic_projection(reference_unsupported)
    @test compiled_unsupported.status == EVAL_UNSUPPORTED_CAPABILITY

    folded_problem = capability_constant_problem()
    folded = GeoTargetCore.compile_problem(folded_problem, registry)
    @test folded.stats.constant_folds == 1
    folded_reference = evaluate_reference(folded_problem, registry, Float64[]; capability = C2)
    folded_unsupported = GeoTargetCore.evaluate(folded, Float64[]; capability = C2)
    @test semantic_projection(folded_unsupported) == semantic_projection(folded_reference)
    @test folded_unsupported.diagnostic == folded_reference.diagnostic

    routed_problem = capability_constant_problem(dedicated_route = true)
    routed = GeoTargetCore.compile_problem(routed_problem, registry)
    @test routed.stats.constant_folds == 0
    routed_reference = evaluate_reference(routed_problem, registry, Float64[]; capability = C2)
    routed_compiled = GeoTargetCore.evaluate(routed, Float64[]; capability = C2)
    @test semantic_projection(routed_compiled) == semantic_projection(routed_reference)
    @test routed_compiled.target == 101.0
end

@testset "safe folding, CSE, DCE and sparsity are observable" begin
    registry = compiler_registry()
    problem = folding_problem()
    compiled, observed = test_differential(problem, registry, Float64[])
    @test observed.status == EVAL_OK
    @test compiled.stats.constant_folds >= 2
    @test compiled.stats.cse_hits >= 2
    @test compiled.stats.dead_nodes == 1
    @test compiled.stats.live_nodes + compiled.stats.dead_nodes == compiled.stats.source_nodes
    @test compiled.stats.runtime_calls < compiled.logical_evaluation_cost

    smooth = GeoTargetCore.compile_problem(smooth_problem(), registry)
    @test only(smooth.sparsity.relation_variables).second == (1, 2)
    @test only(smooth.sparsity.guard_variables).second == (1,)
    @test only(smooth.sparsity.domain_variables).second == (1, 2)
    @test smooth.sparsity.target_variables == (1, 2)
    @test smooth.sparsity.jacobian_entries == ((1, 1), (1, 2))
end

@testset "cache identity covers semantics, backend and environment" begin
    registry = compiler_registry()
    first = GeoTargetCore.compile_problem(smooth_problem(), registry)
    same = GeoTargetCore.compile_problem(smooth_problem(), registry)
    scaled = GeoTargetCore.compile_problem(smooth_problem(variable_scale = 2.0), registry)
    backend = GeoTargetCore.compile_problem(smooth_problem(), registry; numeric_backend = "Float64")
    changed_literal = GeoTargetCore.compile_problem(folding_problem(constant = 0.25), registry)
    base_literal = GeoTargetCore.compile_problem(folding_problem(), registry)
    @test first.cache_identity.key == same.cache_identity.key
    @test first.cache_identity.key != scaled.cache_identity.key
    @test first.cache_identity.key != backend.cache_identity.key
    @test base_literal.cache_identity.problem != changed_literal.cache_identity.problem
    @test first.cache_identity.plugin_locks == smooth_problem().plugin_locks
    @test first.cache_identity.core_abi == GeoTargetCore.CORE_ABI_VERSION
    @test first.cache_identity.julia_version == VERSION

    symbol_digest, _ = GeoTargetCore._literal_digest(:same_text)
    string_digest, _ = GeoTargetCore._literal_digest("same_text")
    @test symbol_digest != string_digest
    cyclic = Any[]
    push!(cyclic, cyclic)
    cyclic_digest, persistent = GeoTargetCore._literal_digest(cyclic)
    @test cyclic_digest isa ContentHash
    @test !persistent
end

@testset "batch, reusable workspace and contexts are isolated" begin
    registry = compiler_registry()
    compiled = GeoTargetCore.compile_problem(smooth_problem(), registry)
    workspace = GeoTargetCore.CompiledWorkspace(compiled)
    points = [0.5 0.25; 1.0 0.0; -1.0 1.0]
    batch = GeoTargetCore.evaluate_batch(compiled, points; workspace)
    @test length(batch) == 3
    @test [observation.target for observation in batch] ≈
          [hypot(points[row, 1], points[row, 2]) for row in axes(points, 1)]

    workspaces = (GeoTargetCore.CompiledWorkspace(compiled), GeoTargetCore.CompiledWorkspace(compiled))
    tasks = (
        Threads.@spawn(GeoTargetCore.evaluate(compiled, [0.25, 0.5]; workspace = workspaces[1])),
        Threads.@spawn(GeoTargetCore.evaluate(compiled, [1.5, -0.5]; workspace = workspaces[2])),
    )
    observations = fetch.(tasks)
    @test observations[1].target ≈ hypot(0.25, 0.5)
    @test observations[2].target ≈ hypot(1.5, -0.5)

    other = GeoTargetCore.compile_problem(smooth_problem(variable_scale = 3.0), registry)
    @test_throws GeoTargetCore.CompilerError GeoTargetCore.evaluate(
        other,
        [0.5, 0.25];
        workspace,
    )
end

@testset "canonical replay remains the final truth path" begin
    registry = compiler_registry()
    problem = branch_problem()
    compiled = GeoTargetCore.compile_problem(problem, registry)
    replay = GeoTargetCore.evaluate_canonical(compiled, [0.0])
    reference = evaluate_reference(problem, registry, [0.0])
    @test semantic_projection(replay) == semantic_projection(reference)

    source = read(
        joinpath(@__DIR__, "..", "GeoTargetCore", "src", "compiled_oracle.jl"),
        String,
    )
    @test !occursin("resolve_operation", source)
    @test !occursin("resolve_selector", source)
    @test !occursin("invokelatest", source)
    @test !occursin(r"\beval\s*\(", source)
    @test !occursin("GeoTargetGeometry", source)
end
