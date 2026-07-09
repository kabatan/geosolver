using GeoTargetBase
using GeoTargetCore
using Test
using UUIDs

const PLUGIN = PluginId(UUID("8d735472-4a6f-49bb-bb17-3f96776495b2"), "core_fixture")
const REAL = TypeId(PLUGIN, "real")
const CHOICE = TypeId(PLUGIN, "choice")

kernel(function_value; capabilities = CapabilitySet(C0, C2), generic_numeric = true) =
    OperatorKernel(
        function_value;
        capabilities,
        generic_numeric,
        smoothness = SMOOTH_C1,
        derivative_mode = DERIVATIVE_NONE,
    )

function fixture_plugin()
    real = TypeSpec(REAL, Real)
    choice_type = TypeSpec(CHOICE, Choice)
    unary_real = SignatureSpec((REAL,), REAL)
    binary_real = SignatureSpec((REAL, REAL), REAL)
    branch_signature = SignatureSpec((REAL,), CHOICE)
    selector_signature = SignatureSpec((CHOICE, REAL), REAL)

    add = PrimitiveSpec(PrimitiveId(PLUGIN, "add"), (binary_real,), kernel(+))
    relation = RelationSpec(
        PrimitiveId(PLUGIN, "relation"),
        (unary_real,),
        kernel(identity);
        truth = iszero,
        scale_hint = 2.0,
    )
    guard = GuardSpec(
        PrimitiveId(PLUGIN, "guard"),
        (unary_real,),
        kernel(identity);
        default_strict = true,
    )
    domain = DomainSpec(
        PrimitiveId(PLUGIN, "domain"),
        (unary_real,),
        kernel(identity);
        default_strict = false,
    )
    branch = BranchSpec(
        PrimitiveId(PLUGIN, "branch"),
        (branch_signature,),
        REAL,
        kernel(value -> Choice((value, -value), ("positive", "negative"), (1.0, 1.0))),
    )
    select_near = SelectorSpec(
        SelectorId(PLUGIN, "near"),
        (selector_signature,),
        kernel((values, reference) -> begin
            distances = abs.(values.candidates .- reference)
            order = sortperm(collect(eachindex(distances)); by = index -> (distances[index], index))
            margin = length(order) == 1 ? Inf : distances[order[2]] - distances[order[1]]
            Selection(values, order[1], margin)
        end),
    )
    return PluginSpec(
        PLUGIN,
        v"0.1.0",
        CORE_ABI_VERSION,
        content_hash("core-fixture-v1");
        types = (real, choice_type),
        primitives = (add,),
        relations = (relation,),
        guards = (guard,),
        domains = (domain,),
        branches = (branch,),
        selectors = (select_near,),
    )
end

function fixture_registry()
    builder = RegistryBuilder(allowlist = (PLUGIN,))
    register!(builder, fixture_plugin())
    return freeze(builder)
end

function fixture_problem(; selector_reference = 0.75, lock = plugin_lock(fixture_plugin()))
    variable = VariableSpec(VariableId("x"), REAL, 0.5, 1.0; lower = -2.0, upper = 2.0)
    nodes = (
        ReferenceNode(NodeId("x_ref"), variable.id),
        LiteralNode(NodeId("zero"), REAL, 0.0),
        LiteralNode(NodeId("selector_reference"), REAL, selector_reference),
        CallNode(NodeId("relation"), PrimitiveId(PLUGIN, "relation"), (NodeId("x_ref"),)),
        CallNode(NodeId("guard"), PrimitiveId(PLUGIN, "guard"), (NodeId("x_ref"),)),
        CallNode(NodeId("domain"), PrimitiveId(PLUGIN, "domain"), (NodeId("x_ref"),)),
        CallNode(NodeId("choices"), PrimitiveId(PLUGIN, "branch"), (NodeId("x_ref"),)),
        SelectNode(
            NodeId("selected"),
            NodeId("choices"),
            SelectorId(PLUGIN, "near"),
            (NodeId("selector_reference"),),
        ),
        CallNode(
            NodeId("target"),
            PrimitiveId(PLUGIN, "add"),
            (NodeId("selected"), NodeId("zero")),
        ),
    )
    return ProblemSpecV1(
        (lock,),
        (variable,),
        ConstructionGraph(nodes);
        relations = (RelationBinding(NodeId("relation")),),
        guards = (GuardBinding(NodeId("guard"), true),),
        domains = (DomainBinding(NodeId("domain"), false),),
        target = NodeId("target"),
    )
end

@testset "GeoTargetCore bootstrap" begin
    @test GeoTargetCore.abi_version() == v"1.0.0"
end

@testset "registry is explicit, content locked, and frozen" begin
    plugin = fixture_plugin()
    builder = RegistryBuilder(allowlist = (PLUGIN,))
    @test register!(builder, plugin) === builder
    registry = freeze(builder)
    @test registered_plugins(registry) == (plugin,)
    @test resolve_type(registry, REAL).julia_type === Real
    @test resolve_operation(registry, PrimitiveId(PLUGIN, "relation")).role == ROLE_RELATION
    @test resolve_selector(registry, SelectorId(PLUGIN, "near")) !== nothing
    @test_throws RegistryError register!(builder, plugin)
    @test_throws RegistryError freeze(builder)

    denied = RegistryBuilder(allowlist = ())
    @test_throws RegistryError register!(denied, plugin)
    duplicate = RegistryBuilder()
    register!(duplicate, plugin)
    @test_throws RegistryError register!(duplicate, plugin)
end

@testset "typed validation is geometry agnostic" begin
    registry = fixture_registry()
    problem = fixture_problem()
    report = validate_problem(problem, registry)
    @test isempty(report)
    @test node_type(report, NodeId("x_ref")) == REAL
    @test node_type(report, NodeId("choices")) == CHOICE
    @test node_type(report, NodeId("selected")) == REAL
    @test isempty(require_valid_problem(problem, registry))

    wrong_lock = PluginLock(PLUGIN, v"0.2.0", CORE_ABI_VERSION, content_hash("wrong"))
    invalid = fixture_problem(lock = wrong_lock)
    invalid_report = validate_problem(invalid, registry)
    @test any(issue -> issue.code == :plugin_lock_mismatch, invalid_report.issues)
    @test_throws ProblemValidationError require_valid_problem(invalid, registry)

    bad_nodes = collect(problem.graph.nodes)
    bad_nodes[4] = CallNode(
        NodeId("relation"),
        PrimitiveId(PLUGIN, "add"),
        (NodeId("x_ref"),),
    )
    bad = ProblemSpecV1(
        problem.plugin_locks,
        problem.variables,
        ConstructionGraph(bad_nodes);
        relations = problem.relations,
        guards = problem.guards,
        domains = problem.domains,
        target = problem.target,
    )
    @test any(
        issue -> issue.code in (:no_matching_signature, :invalid_role_operation),
        validate_problem(bad, registry).issues,
    )
end

@testset "reference interpreter preserves semantic channels" begin
    registry = fixture_registry()
    problem = fixture_problem()
    observation = evaluate_reference(problem, registry, [1.0])
    @test observation.status == EVAL_OK
    @test observation.target == 1.0
    @test residual_values(observation) == (1.0,)
    @test scaled_residual_values(observation) == (0.5,)
    @test observation.relations[1].truth == false
    @test observation.guards[1].valid
    @test observation.domains[1].valid
    @test observation.branches[1].decision.key == ChoiceKey("positive")
    @test observation.evaluation_cost == 6
    @test !canonical_feasible(observation; residual_tolerance = 1.0e-8)

    root = evaluate_reference(problem, registry, [0.0])
    @test root.relations[1].truth
    @test !root.guards[1].valid
    @test canonical_feasible(root; residual_tolerance = 0.0) == false

    out_of_bounds = evaluate_reference(problem, registry, [3.0])
    @test out_of_bounds.status == EVAL_INVALID_DOMAIN
    @test evaluate_reference(problem, registry, [NaN]).status == EVAL_NONFINITE
    @test evaluate_reference(problem, registry, Any["not-real"]).status == EVAL_PLUGIN_ERROR

    tied = evaluate_reference(fixture_problem(selector_reference = 0.0), registry, [1.0])
    @test tied.status == EVAL_AMBIGUOUS_BRANCH

    high_precision = evaluate_reference(problem, registry, BigFloat[1]; capability = C2)
    @test high_precision.target == BigFloat(1)
    @test eltype(BigFloat[high_precision.target]) == BigFloat
end
