using GeoTargetBase
using GeoTargetCore
using GeoTargetGeometry
using Test

if !isdefined(Main, :OpaquePlugin)
    include(joinpath(@__DIR__, "..", "fixtures", "OpaquePlugin", "src", "OpaquePlugin.jl"))
end
using .OpaquePlugin

const CANDIDATE_FIXTURE_PLUGIN =
    parse(PluginId, "ea97f68c-82e6-46b1-a4a2-88af88177419/candidate_validation_fixture")

function _c0_choice(value)
    return Choice((value,), ("c0_key",), (one(value),))
end

function _c2_choice(value)
    return Choice((value,), ("c2_key",), (one(value),))
end

function _invalid_choice(value)
    return Choice((value,), ("stable_key",), (-one(value),))
end

function _stable_choice(value)
    return Choice((value,), ("stable_key",), (one(value),))
end

function _select_first(choice::Choice)
    return Selection(choice, 1, one(choice.validity_margins[1]))
end

function _select_tied(choice::Choice)
    return Selection(choice, 1, zero(choice.validity_margins[1]))
end

function _precision_shift(value)
    precision(value) >= 700 || return value
    return value + parse(BigFloat, "1e-50")
end

function _precision_root(value)
    precision(value) >= 700 || return value
    return value - parse(BigFloat, "1e-50")
end

function candidate_fixture_plugin()
    scalar_signature = SignatureSpec((SCALAR_TYPE_ID,), SCALAR_TYPE_ID)
    choice_signature = SignatureSpec((SCALAR_TYPE_ID,), CHOICE_TYPE_ID)
    selector_signature = SignatureSpec((CHOICE_TYPE_ID,), SCALAR_TYPE_ID)
    generic_kernel(evaluator) = OperatorKernel(
        evaluator;
        capabilities = CapabilitySet(C0, C2),
        generic_numeric = true,
        smoothness = SMOOTH_C1,
    )
    route = PrimitiveSpec(
        PrimitiveId(CANDIDATE_FIXTURE_PLUGIN, "target_route"),
        (scalar_signature,),
        OperatorKernel(
            identity;
            high_precision = value -> value + one(value),
            capabilities = CapabilitySet(C0, C2),
            smoothness = SMOOTH_C1,
        ),
    )
    downcast = PrimitiveSpec(
        PrimitiveId(CANDIDATE_FIXTURE_PLUGIN, "downcast_target"),
        (scalar_signature,),
        OperatorKernel(
            identity;
            high_precision=value -> Float64(value),
            capabilities=CapabilitySet(C0, C2),
            smoothness=SMOOTH_C1,
        ),
    )
    precision_target = PrimitiveSpec(
        PrimitiveId(CANDIDATE_FIXTURE_PLUGIN, "precision_target"),
        (scalar_signature,),
        OperatorKernel(
            identity;
            high_precision=_precision_shift,
            capabilities=CapabilitySet(C0, C2),
            smoothness=SMOOTH_C1,
        ),
    )
    false_truth = RelationSpec(
        PrimitiveId(CANDIDATE_FIXTURE_PLUGIN, "false_truth"),
        (scalar_signature,),
        generic_kernel(value -> value * 1.0e-13);
        truth = value -> false,
        scale_hint = 1.0,
    )
    shifted_root = RelationSpec(
        PrimitiveId(CANDIDATE_FIXTURE_PLUGIN, "precision_root"),
        (scalar_signature,),
        OperatorKernel(
            identity;
            high_precision=_precision_root,
            capabilities=CapabilitySet(C0, C2),
            smoothness=SMOOTH_C1,
        );
        scale_hint=1.0,
    )
    flip = BranchSpec(
        PrimitiveId(CANDIDATE_FIXTURE_PLUGIN, "flip_choice"),
        (choice_signature,),
        SCALAR_TYPE_ID,
        OperatorKernel(
            _c0_choice;
            high_precision = _c2_choice,
            capabilities = CapabilitySet(C0, C2),
            smoothness = PIECEWISE_SMOOTH,
        ),
    )
    invalid = BranchSpec(
        PrimitiveId(CANDIDATE_FIXTURE_PLUGIN, "invalid_choice"),
        (choice_signature,),
        SCALAR_TYPE_ID,
        generic_kernel(_invalid_choice),
    )
    stable = BranchSpec(
        PrimitiveId(CANDIDATE_FIXTURE_PLUGIN, "stable_choice"),
        (choice_signature,),
        SCALAR_TYPE_ID,
        generic_kernel(_stable_choice),
    )
    selectors = (
        SelectorSpec(
            SelectorId(CANDIDATE_FIXTURE_PLUGIN, "first"),
            (selector_signature,),
            generic_kernel(_select_first),
        ),
        SelectorSpec(
            SelectorId(CANDIDATE_FIXTURE_PLUGIN, "tied"),
            (selector_signature,),
            generic_kernel(_select_tied),
        ),
    )
    return PluginSpec(
        CANDIDATE_FIXTURE_PLUGIN,
        v"0.1.0",
        GeoTargetCore.CORE_ABI_VERSION,
        content_hash("candidate-validation-fixture-v3");
        primitives = (route, downcast, precision_target),
        relations = (false_truth, shifted_root),
        branches = (flip, invalid, stable),
        selectors,
    )
end

function candidate_registry()
    plugins = (geometry_plugin(), opaque_plugin(), candidate_fixture_plugin())
    builder = RegistryBuilder(allowlist = Tuple(plugin.id for plugin in plugins))
    foreach(plugin -> register!(builder, plugin), plugins)
    return freeze(builder)
end

function _scalar_variable(; origin = 1.0, bounded = false)
    return VariableSpec(
        VariableId("x"),
        SCALAR_TYPE_ID,
        Float64(origin),
        1.0;
        lower = bounded ? -2.0 : nothing,
        upper = bounded ? 2.0 : nothing,
    )
end

function geometry_validation_problem(; relation = :one, guard = :strict)
    plugin = geometry_plugin()
    variable = _scalar_variable(origin = guard == :nonstrict ? 0.0 : 1.0)
    nodes = AbstractGraphNode[
        ReferenceNode(NodeId("x_ref"), variable.id),
        LiteralNode(NodeId("zero"), SCALAR_TYPE_ID, 0.0),
        LiteralNode(NodeId("one"), SCALAR_TYPE_ID, 1.0),
    ]
    relation_arguments = if relation == :self
        (NodeId("x_ref"), NodeId("x_ref"))
    elseif relation == :zero
        (NodeId("x_ref"), NodeId("zero"))
    else
        (NodeId("x_ref"), NodeId("one"))
    end
    push!(
        nodes,
        CallNode(
            NodeId("relation"),
            PrimitiveId(GEOMETRY_PLUGIN_ID, "scalar_equality"),
            relation_arguments,
        ),
    )
    guards = ()
    if guard != :none
        push!(
            nodes,
            CallNode(
                NodeId("guard"),
                PrimitiveId(GEOMETRY_PLUGIN_ID, "positive"),
                (NodeId("x_ref"),),
            ),
        )
        guards = (GuardBinding(NodeId("guard"), guard == :strict),)
    end
    return ProblemSpecV1(
        (plugin_lock(plugin),),
        (variable,),
        ConstructionGraph(Tuple(nodes));
        relations = (RelationBinding(NodeId("relation")),),
        guards,
        target = NodeId("x_ref"),
    )
end

function c0_only_problem()
    geometry = geometry_plugin()
    opaque = opaque_plugin()
    variable = _scalar_variable(origin = 0.5)
    graph = ConstructionGraph((
        ReferenceNode(NodeId("x_ref"), variable.id),
        CallNode(
            NodeId("target"),
            PrimitiveId(OPAQUE_PLUGIN_ID, "float64_only"),
            (NodeId("x_ref"),),
        ),
    ))
    return ProblemSpecV1(
        (plugin_lock(geometry), plugin_lock(opaque)),
        (variable,),
        graph;
        target = NodeId("target"),
    )
end

function false_truth_problem()
    geometry = geometry_plugin()
    fixture = candidate_fixture_plugin()
    variable = _scalar_variable()
    graph = ConstructionGraph((
        ReferenceNode(NodeId("x_ref"), variable.id),
        CallNode(
            NodeId("relation"),
            PrimitiveId(CANDIDATE_FIXTURE_PLUGIN, "false_truth"),
            (NodeId("x_ref"),),
        ),
    ))
    return ProblemSpecV1(
        (plugin_lock(geometry), plugin_lock(fixture)),
        (variable,),
        graph;
        relations = (RelationBinding(NodeId("relation")),),
        target = NodeId("x_ref"),
    )
end

function invalid_domain_problem()
    geometry = geometry_plugin()
    opaque = opaque_plugin()
    variable = _scalar_variable(origin = -1.0)
    graph = ConstructionGraph((
        ReferenceNode(NodeId("x_ref"), variable.id),
        CallNode(
            NodeId("domain"),
            PrimitiveId(OPAQUE_PLUGIN_ID, "positive_log_domain"),
            (NodeId("x_ref"),),
        ),
    ))
    return ProblemSpecV1(
        (plugin_lock(geometry), plugin_lock(opaque)),
        (variable,),
        graph;
        domains = (DomainBinding(NodeId("domain"), true),),
        target = NodeId("x_ref"),
    )
end

function branch_validation_problem(; branch = "flip_choice", selector = "first")
    geometry = geometry_plugin()
    fixture = candidate_fixture_plugin()
    variable = _scalar_variable()
    graph = ConstructionGraph((
        ReferenceNode(NodeId("x_ref"), variable.id),
        LiteralNode(NodeId("one"), SCALAR_TYPE_ID, 1.0),
        CallNode(
            NodeId("relation"),
            PrimitiveId(GEOMETRY_PLUGIN_ID, "scalar_equality"),
            (NodeId("x_ref"), NodeId("one")),
        ),
        CallNode(
            NodeId("choices"),
            PrimitiveId(CANDIDATE_FIXTURE_PLUGIN, branch),
            (NodeId("x_ref"),),
        ),
        SelectNode(
            NodeId("selected"),
            NodeId("choices"),
            SelectorId(CANDIDATE_FIXTURE_PLUGIN, selector),
        ),
    ))
    return ProblemSpecV1(
        (plugin_lock(geometry), plugin_lock(fixture)),
        (variable,),
        graph;
        relations = (RelationBinding(NodeId("relation")),),
        target = NodeId("selected"),
    )
end

function precision_variant_problem(; target_primitive="precision_target", shifted_root=false)
    geometry = geometry_plugin()
    fixture = candidate_fixture_plugin()
    variable = _scalar_variable(origin=shifted_root ? 0.0 : 1.0)
    nodes = AbstractGraphNode[ReferenceNode(NodeId("x_ref"), variable.id)]
    relations = ()
    if shifted_root
        push!(nodes, CallNode(
            NodeId("relation"),
            PrimitiveId(CANDIDATE_FIXTURE_PLUGIN, "precision_root"),
            (NodeId("x_ref"),),
        ))
        relations = (RelationBinding(NodeId("relation")),)
    else
        push!(nodes, LiteralNode(NodeId("one"), SCALAR_TYPE_ID, 1.0))
        push!(nodes, CallNode(
            NodeId("relation"),
            PrimitiveId(GEOMETRY_PLUGIN_ID, "scalar_equality"),
            (NodeId("x_ref"), NodeId("one")),
        ))
        relations = (RelationBinding(NodeId("relation")),)
    end
    push!(nodes, CallNode(
        NodeId("target"),
        PrimitiveId(CANDIDATE_FIXTURE_PLUGIN, target_primitive),
        (NodeId("x_ref"),),
    ))
    return ProblemSpecV1(
        (plugin_lock(geometry), plugin_lock(fixture)),
        (variable,),
        ConstructionGraph(Tuple(nodes));
        relations,
        target=NodeId("target"),
    )
end

function inconsistent_target_problem()
    geometry = geometry_plugin()
    fixture = candidate_fixture_plugin()
    variable = _scalar_variable()
    graph = ConstructionGraph((
        ReferenceNode(NodeId("x_ref"), variable.id),
        CallNode(
            NodeId("target"),
            PrimitiveId(CANDIDATE_FIXTURE_PLUGIN, "target_route"),
            (NodeId("x_ref"),),
        ),
    ))
    return ProblemSpecV1(
        (plugin_lock(geometry), plugin_lock(fixture)),
        (variable,),
        graph;
        target = NodeId("target"),
    )
end

@testset "512/768 candidate confirmation produces v2 provisional evidence" begin
    registry = candidate_registry()
    problem = geometry_validation_problem()
    compiled = compile_problem(problem, registry)
    result = validate_candidate(compiled, [0.8])

    @test result.accepted
    @test result.failure == CANDIDATE_VALIDATION_NONE
    @test result.diagnostic === nothing
    @test result.method == "compiled512_reference768_confirmation"
    @test result.precision_bits == 768
    @test result.canonical_observation.target isa BigFloat
    @test all(value -> value isa BigFloat, result.canonical_coordinates)
    @test result.target_enclosure.lower isa BigFloat
    @test precision(result.target_enclosure.lower) == 768
    @test only(result.guard_enclosures).enclosure.lower > 0
    @test result.provisional isa ProvisionalAnswer
    @test !(result.provisional isa ExactAnswer)
    @test result.provisional.canonical_residual_bound <= big"1e-100"
    @test result.provisional.validation.precision_bits == 768
    @test result.provisional.validation.artifact.digest == result.artifact.digest
    @test result.problem == problem_hash(problem, registry)
    @test result.problem_hash_method == "protocol_canonical_json"

    document = parse_protocol_json(result.artifact.payload)
    @test canonical_json(document) == result.artifact.payload
    @test document["schema"] == "geotarget.candidate-validation/v2"
    @test document["problem_hash"] == string(result.problem)
    @test document["configuration_hash"] == string(result.configuration)
    @test document["validation_config_hash"] == string(result.validation_config)
    @test document["validation_failure"] == "CANDIDATE_VALIDATION_NONE"
    @test document["method"] == "compiled512_reference768_confirmation"
    @test document["primary_root_evidence"]["precision_bits"] == 512
    @test document["reference_root_evidence"]["precision_bits"] == 768
    @test document["canonical_replay_work"]["precision_weight"] == 15
    @test document["coordinate_disagreement"]["value"] != "Inf"
    @test document["target_disagreement"]["value"] != "Inf"
    @test result.artifact.digest == content_hash(result.artifact.payload)

    attempt = LocalAttempt(
        (0.8,),
        (0.8,),
        result.fast_observation,
        LOCAL_CONVERGED,
        true,
        0,
        result.fast_observation.evaluation_cost,
        1,
        1.0,
        (),
    )
    from_attempt = validate_candidate(compiled, attempt)
    @test from_attempt.accepted
    @test from_attempt.artifact.digest == result.artifact.digest
    @test result.oracle_work - from_attempt.oracle_work ==
          result.fast_observation.evaluation_cost
end

@testset "zero and tiny residual enclosures remain conservative and wire-bounded" begin
    options = CandidateValidationOptions()
    float_zero = GeoTargetCore._numeric_enclosure(0.0, options)
    @test float_zero.lower <= 0.0 <= float_zero.upper
    @test float_zero.lower == -8.0 * eps(1.0)
    @test float_zero.upper == 8.0 * eps(1.0)

    setprecision(BigFloat, 768) do
        unit_roundoff = BigFloat(8) * eps(BigFloat(1))
        for center in (BigFloat(0), parse(BigFloat, "1e-5000"))
            enclosure = GeoTargetCore._numeric_enclosure(center, options)
            @test enclosure.lower <= center <= enclosure.upper
            @test enclosure.upper - center >= unit_roundoff
            decimal = GeoTargetCore._result_number_document(
                GeoTargetCore._enclosure_bound(enclosure),
                "test.bound",
            )
            @test ncodeunits(decimal) <= 4096
            @test GeoTargetCore._protocol_decimal(decimal, "test.bound") isa
                  GeoTargetCore.ProtocolDecimal
        end
    end
end

@testset "C0-only candidates remain discoverable but cannot become answers" begin
    registry = candidate_registry()
    problem = c0_only_problem()
    compiled = compile_problem(problem, registry)
    @test !supports(capabilities(compiled), C2)
    result = validate_candidate(compiled, [0.5])
    @test !result.accepted
    @test result.failure == CANDIDATE_HIGH_PRECISION_CAPABILITY_MISSING
    @test result.provisional === nothing
    @test result.exact_failure == EXACT_CAPABILITY_MISSING
    @test result.fast_observation.status == EVAL_OK
    @test result.oracle_work == result.fast_observation.evaluation_cost
end

@testset "precision disagreement, downcast and semantic failures are typed" begin
    registry = candidate_registry()

    target_shift = validate_candidate(
        compile_problem(precision_variant_problem(), registry),
        [1.0],
    )
    @test !target_shift.accepted
    @test target_shift.failure == CANDIDATE_PRECISION_TARGET_MISMATCH
    @test target_shift.exact_failure == EXACT_TARGET_CERT_FAILED

    coordinate_shift = validate_candidate(
        compile_problem(precision_variant_problem(shifted_root=true), registry),
        [0.0],
    )
    @test !coordinate_shift.accepted
    @test coordinate_shift.failure == CANDIDATE_PRECISION_COORDINATE_MISMATCH

    downcast = validate_candidate(
        compile_problem(
            precision_variant_problem(target_primitive="downcast_target"),
            registry,
        ),
        [1.0],
    )
    @test !downcast.accepted
    @test downcast.failure == CANDIDATE_HIGH_PRECISION_DOWNGRADE
    @test downcast.oracle_work > 0

    truth = validate_candidate(compile_problem(false_truth_problem(), registry), [1.0])
    @test !truth.accepted
    @test truth.failure == CANDIDATE_RELATION_TRUTH_FAILED

    flip = validate_candidate(compile_problem(branch_validation_problem(), registry), [1.0])
    @test !flip.accepted
    @test flip.failure == CANDIDATE_PRECISION_BRANCH_MISMATCH

    invalid = validate_candidate(
        compile_problem(branch_validation_problem(branch="invalid_choice"), registry),
        [1.0],
    )
    @test !invalid.accepted
    @test invalid.failure == CANDIDATE_PRIMARY_REFINEMENT_FAILED

    tied = validate_candidate(
        compile_problem(
            branch_validation_problem(branch="stable_choice", selector="tied"),
            registry,
        ),
        [1.0],
    )
    @test !tied.accepted
    @test tied.failure == CANDIDATE_PRIMARY_REFINEMENT_FAILED
end

@testset "strict boundaries and rank-deficient exact zeros fail closed" begin
    registry = candidate_registry()
    strict = validate_candidate(
        compile_problem(geometry_validation_problem(relation=:zero), registry),
        [1.0e-16],
    )
    @test !strict.accepted
    @test strict.provisional === nothing

    manifold = validate_candidate(
        compile_problem(geometry_validation_problem(relation=:self, guard=:none), registry),
        [1.0],
    )
    @test !manifold.accepted
    @test manifold.failure == CANDIDATE_PRIMARY_REFINEMENT_FAILED

    manifold_compiled = compile_problem(
        geometry_validation_problem(relation=:self, guard=:none),
        registry,
    )
    exactification_sample = GeoTargetCore._run_high_precision_refinement(
        manifold_compiled,
        [1.0];
        precision_bits=512,
        evaluator_kind=:reference,
        residual_goal=big"1e-110",
        configuration_tolerance=big"1e-100",
        target_tolerance=big"1e-100",
        allow_rank_deficient=true,
    )
    @test exactification_sample.accepted
    @test exactification_sample.evidence.numerical_rank == 0
    @test exactification_sample.evidence.rank_stable
    @test exactification_sample.evidence.method ==
          "reference_c2_rank_general_lm_5point_geometric_v2"
end

@testset "candidate resource limits include weighted high-precision work" begin
    registry = candidate_registry()
    compiled = compile_problem(geometry_validation_problem(), registry)
    budget = validate_candidate(
        compiled,
        [0.8];
        remaining_oracle_work=compiled.logical_evaluation_cost,
    )
    @test !budget.accepted
    @test budget.failure == CANDIDATE_VALIDATION_ORACLE_BUDGET_EXHAUSTED
    @test budget.oracle_work == budget.fast_observation.evaluation_cost

    cancelled = validate_candidate(compiled, [0.8]; cancelled=() -> true)
    @test cancelled.failure == CANDIDATE_VALIDATION_CANCELLED
    @test cancelled.oracle_work == 0

    deadline = validate_candidate(compiled, [0.8]; deadline_ns=UInt64(0))
    @test deadline.failure == CANDIDATE_VALIDATION_DEADLINE_REACHED
    @test deadline.oracle_work == 0

    @test_throws ArgumentError validate_candidate(
        compiled,
        [0.8];
        remaining_oracle_work=true,
    )
    @test_throws ArgumentError validate_candidate(
        compiled,
        [0.8];
        remaining_oracle_work=big(typemax(Int)) + 1,
    )
end

@testset "BigFloat precision is isolated and artifacts are deterministic" begin
    registry = candidate_registry()
    compiled = compile_problem(geometry_validation_problem(), registry)
    before = precision(BigFloat)
    first = setprecision(BigFloat, 137) do
        @test precision(BigFloat) == 137
        result = validate_candidate(compiled, [1.0])
        @test precision(BigFloat) == 137
        result
    end
    @test precision(BigFloat) == before
    @test precision(first.target_enclosure.lower) == 768

    second = validate_candidate(compiled, [1.0])
    @test first.problem == second.problem
    @test first.configuration == second.configuration
    @test first.validation_config == second.validation_config
    @test first.artifact.digest == second.artifact.digest
    @test first.artifact.payload == second.artifact.payload
    @test first.provisional.target.lower == second.provisional.target.lower
    @test first.provisional.target.upper == second.provisional.target.upper

    concurrent = (
        Threads.@spawn(validate_candidate(compiled, [1.0])),
        Threads.@spawn(validate_candidate(compiled, [1.0])),
    )
    concurrent_results = fetch.(concurrent)
    @test all(result -> result.accepted, concurrent_results)
    @test concurrent_results[1].artifact.digest == concurrent_results[2].artifact.digest ==
          first.artifact.digest
    @test all(
        result -> precision(result.target_enclosure.lower) == 768,
        concurrent_results,
    )
    @test precision(BigFloat) == before
end

@testset "candidate options reject weaker confirmation contracts" begin
    @test_throws ArgumentError CandidateValidationOptions(precision_bits=767)
    @test_throws ArgumentError CandidateValidationOptions(primary_precision_bits=511)
    @test_throws ArgumentError CandidateValidationOptions(residual_tolerance=1.0e-99)
    @test_throws ArgumentError CandidateValidationOptions(
        coordinate_stability_tolerance=1.0e-99,
    )
    @test_throws ArgumentError CandidateValidationOptions(
        target_consistency_tolerance=1.0e-99,
    )
    @test_throws ArgumentError CandidateValidationOptions(refinement_residual_goal=1.0e-109)
    @test_throws ArgumentError CandidateValidationOptions(enclosure_absolute_error=Inf)
    @test_throws ArgumentError CandidateValidationOptions(roundoff_multiplier=0)
    @test_throws ArgumentError CandidateValidationOptions(max_refinement_iterations=0)

    large = GeoTargetCore._numeric_enclosure(1.0e100, CandidateValidationOptions())
    @test large.upper - large.lower < 1.0e87
end
