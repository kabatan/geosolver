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
    false_truth = RelationSpec(
        PrimitiveId(CANDIDATE_FIXTURE_PLUGIN, "false_truth"),
        (scalar_signature,),
        generic_kernel(value -> zero(value));
        truth = value -> false,
        scale_hint = 1.0,
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
        content_hash("candidate-validation-fixture-v2");
        primitives = (route,),
        relations = (false_truth,),
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

function geometry_validation_problem(; relation = :self, guard = :strict)
    plugin = geometry_plugin()
    variable = _scalar_variable(origin = guard == :nonstrict ? 0.0 : 1.0)
    nodes = AbstractGraphNode[
        ReferenceNode(NodeId("x_ref"), variable.id),
        LiteralNode(NodeId("zero"), SCALAR_TYPE_ID, 0.0),
    ]
    relation_arguments = relation == :self ?
                         (NodeId("x_ref"), NodeId("x_ref")) :
                         (NodeId("x_ref"), NodeId("zero"))
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
        target = NodeId("selected"),
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

@testset "C2 candidate validation produces replayable provisional evidence only" begin
    registry = candidate_registry()
    problem = geometry_validation_problem()
    compiled = GeoTargetCore.compile_problem(problem, registry)
    options = GeoTargetCore.CandidateValidationOptions(precision_bits = 320)
    result = GeoTargetCore.validate_candidate(compiled, [1.0]; options)

    @test result.accepted
    @test result.failure == GeoTargetCore.CANDIDATE_VALIDATION_NONE
    @test result.diagnostic === nothing
    @test result.method == "canonical_bigfloat_recheck"
    @test result.precision_bits == 320
    @test result.canonical_observation.target isa BigFloat
    @test result.target_enclosure.lower isa BigFloat
    @test precision(result.target_enclosure.lower) == 320
    @test only(result.guard_enclosures).enclosure.lower > 0
    @test result.provisional isa ProvisionalAnswer
    @test !(result.provisional isa ExactAnswer)
    @test result.provisional.exact_failure == EXACT_CAPABILITY_MISSING
    @test result.exact_failure == EXACT_CAPABILITY_MISSING
    @test result.provisional.validation.artifact.digest == result.artifact.digest
    @test result.problem == compiled.cache_identity.problem
    @test result.problem_hash_method == "compiled_structural_v1"
    @test result.oracle_work ==
          result.fast_observation.evaluation_cost + result.canonical_observation.evaluation_cost

    document = GeoTargetCore.parse_protocol_json(result.artifact.payload)
    @test GeoTargetCore.canonical_json(document) == result.artifact.payload
    @test document["schema"] == "geotarget.candidate-validation/v1"
    @test document["problem_hash"] == string(result.problem)
    @test document["problem_hash_method"] == result.problem_hash_method
    @test document["configuration_hash"] == string(result.configuration)
    @test document["validation_config_hash"] == string(result.validation_config)
    @test document["validation_failure"] == "CANDIDATE_VALIDATION_NONE"
    @test document["method"] == "canonical_bigfloat_recheck"
    @test result.artifact.digest == content_hash(result.artifact.payload)

    attempt = GeoTargetCore.LocalAttempt(
        (1.0,),
        (1.0,),
        result.fast_observation,
        GeoTargetCore.LOCAL_CONVERGED,
        true,
        0,
        result.fast_observation.evaluation_cost,
        1,
        1.0,
        (),
    )
    from_attempt = GeoTargetCore.validate_candidate(compiled, attempt; options)
    @test from_attempt.accepted
    @test from_attempt.artifact.digest == result.artifact.digest
    @test from_attempt.oracle_work == from_attempt.canonical_observation.evaluation_cost
end

@testset "C0-only paths use an explicit independent canonical second pass" begin
    registry = candidate_registry()
    problem = c0_only_problem()
    compiled = GeoTargetCore.compile_problem(problem, registry)
    @test !supports(GeoTargetCore.capabilities(compiled), C2)
    result = GeoTargetCore.validate_candidate(compiled, [0.5])
    @test result.accepted
    @test result.method == "canonical_c0_second_pass"
    @test result.precision_bits == 53
    @test result.canonical_observation.status == EVAL_OK
    @test result.problem_hash_method == "protocol_canonical_json"
    @test result.problem == GeoTargetCore.problem_hash(problem, registry)
    @test result.provisional.validation.method == "canonical_c0_second_pass"
    @test result.provisional.validation.precision_bits == 53
    @test result.provisional.exact_failure == EXACT_CAPABILITY_MISSING
end

@testset "each canonical checkpoint fails closed with a typed reason" begin
    registry = candidate_registry()

    residual_problem = geometry_validation_problem(relation = :zero, guard = :none)
    residual_compiled = GeoTargetCore.compile_problem(residual_problem, registry)
    misleading_fast = GeoTargetCore.evaluate(residual_compiled, [0.0])
    residual = GeoTargetCore.validate_candidate(
        residual_compiled,
        [1.0];
        fast_observation = misleading_fast,
    )
    @test !residual.accepted
    @test residual.failure == GeoTargetCore.CANDIDATE_RELATION_RESIDUAL_FAILED
    @test residual.provisional === nothing
    @test residual.exact_failure == EXACT_CONFIGURATION_CERT_FAILED
    @test residual.canonical_observation.target == BigFloat(1.0)
    residual_document = GeoTargetCore.parse_protocol_json(residual.artifact.payload)
    @test residual_document["validation_diagnostic"]["failure"] ==
          "CANDIDATE_RELATION_RESIDUAL_FAILED"
    @test residual_document["validation_diagnostic"]["node"] == "relation"

    truth = GeoTargetCore.validate_candidate(
        GeoTargetCore.compile_problem(false_truth_problem(), registry),
        [1.0],
    )
    @test truth.failure == GeoTargetCore.CANDIDATE_RELATION_TRUTH_FAILED

    error_options = GeoTargetCore.CandidateValidationOptions(
        enclosure_absolute_error = 1.0e-12,
    )
    strict = GeoTargetCore.validate_candidate(
        GeoTargetCore.compile_problem(geometry_validation_problem(), registry),
        [1.0e-16];
        options = error_options,
    )
    @test strict.failure == GeoTargetCore.CANDIDATE_STRICT_GUARD_UNSEPARATED
    @test strict.exact_failure == EXACT_GUARD_NOT_SEPARATED
    @test strict.target_enclosure !== nothing

    nonstrict = GeoTargetCore.validate_candidate(
        GeoTargetCore.compile_problem(
            geometry_validation_problem(guard = :nonstrict),
            registry,
        ),
        [0.0];
        options = error_options,
    )
    @test nonstrict.failure == GeoTargetCore.CANDIDATE_NONSTRICT_GUARD_FAILED
    @test nonstrict.exact_failure == EXACT_GUARD_NOT_SEPARATED

    domain = GeoTargetCore.validate_candidate(
        GeoTargetCore.compile_problem(invalid_domain_problem(), registry),
        [-1.0],
    )
    @test domain.failure == GeoTargetCore.CANDIDATE_DOMAIN_FAILED

    flip = GeoTargetCore.validate_candidate(
        GeoTargetCore.compile_problem(branch_validation_problem(), registry),
        [1.0],
    )
    @test flip.failure == GeoTargetCore.CANDIDATE_BRANCH_KEY_MISMATCH

    invalid = GeoTargetCore.validate_candidate(
        GeoTargetCore.compile_problem(
            branch_validation_problem(branch = "invalid_choice"),
            registry,
        ),
        [1.0],
    )
    @test invalid.failure == GeoTargetCore.CANDIDATE_BRANCH_VALIDITY_FAILED

    selector_tie = GeoTargetCore.validate_candidate(
        GeoTargetCore.compile_problem(
            branch_validation_problem(branch = "stable_choice", selector = "tied"),
            registry,
        ),
        [1.0],
    )
    @test selector_tie.failure == GeoTargetCore.CANDIDATE_BRANCH_SELECTOR_UNSEPARATED

    target = GeoTargetCore.validate_candidate(
        GeoTargetCore.compile_problem(inconsistent_target_problem(), registry),
        [1.0],
    )
    @test target.failure == GeoTargetCore.CANDIDATE_TARGET_INCONSISTENT
    @test target.exact_failure == EXACT_TARGET_CERT_FAILED
end

@testset "BigFloat precision is isolated and validation artifacts are deterministic" begin
    registry = candidate_registry()
    compiled = GeoTargetCore.compile_problem(geometry_validation_problem(), registry)
    options = GeoTargetCore.CandidateValidationOptions(precision_bits = 384)
    before = precision(BigFloat)
    first = setprecision(BigFloat, 137) do
        @test precision(BigFloat) == 137
        result = GeoTargetCore.validate_candidate(compiled, [1.0]; options)
        @test precision(BigFloat) == 137
        result
    end
    @test precision(BigFloat) == before
    @test precision(first.target_enclosure.lower) == 384

    second = GeoTargetCore.validate_candidate(compiled, [1.0]; options)
    @test first.problem == second.problem
    @test first.configuration == second.configuration
    @test first.validation_config == second.validation_config
    @test first.artifact.digest == second.artifact.digest
    @test first.artifact.payload == second.artifact.payload
    @test first.provisional.target.lower == second.provisional.target.lower
    @test first.provisional.canonical_residual_bound ==
          second.provisional.canonical_residual_bound

    concurrent = (
        Threads.@spawn(GeoTargetCore.validate_candidate(
            compiled,
            [1.0];
            options = GeoTargetCore.CandidateValidationOptions(precision_bits = 192),
        )),
        Threads.@spawn(GeoTargetCore.validate_candidate(
            compiled,
            [1.0];
            options = GeoTargetCore.CandidateValidationOptions(precision_bits = 448),
        )),
    )
    concurrent_results = fetch.(concurrent)
    @test precision(concurrent_results[1].target_enclosure.lower) == 192
    @test precision(concurrent_results[2].target_enclosure.lower) == 448
    @test precision(BigFloat) == before
end

@testset "candidate validation options reject unsafe numeric contracts" begin
    @test_throws ArgumentError GeoTargetCore.CandidateValidationOptions(precision_bits = 52)
    @test_throws ArgumentError GeoTargetCore.CandidateValidationOptions(residual_tolerance = -1)
    @test_throws ArgumentError GeoTargetCore.CandidateValidationOptions(
        enclosure_absolute_error = Inf,
    )
    @test_throws ArgumentError GeoTargetCore.CandidateValidationOptions(
        residual_tolerance = big"1e1000",
    )
    @test_throws ArgumentError GeoTargetCore.CandidateValidationOptions(roundoff_multiplier = 0)

    large = GeoTargetCore._numeric_enclosure(
        1.0e100,
        GeoTargetCore.CandidateValidationOptions(),
    )
    @test large.upper - large.lower < 1.0e87
end
