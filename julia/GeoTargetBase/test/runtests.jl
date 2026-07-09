using GeoTargetBase
using Test
using UUIDs

const TEST_PLUGIN = PluginId(UUID("49f3be3e-9df0-499e-9ba8-a90b21ed5686"), "test")
const OTHER_PLUGIN = PluginId(UUID("3bcc45cd-d510-48c9-bdf8-bfabc338b0b8"), "other")
const SCALAR_TYPE = TypeId(TEST_PLUGIN, "scalar")
const POINT_TYPE = TypeId(TEST_PLUGIN, "opaque_point")
const CHOICE_TYPE = TypeId(TEST_PLUGIN, "point_choice")

generic_kernel() = OperatorKernel(
    identity;
    capabilities = CapabilitySet(C0, C1, C2, C3V),
    derivative_mode = DERIVATIVE_AUTODIFF,
    generic_numeric = true,
    smoothness = SMOOTH_C1,
)

@testset "GeoTargetBase package" begin
    @test GeoTargetBase.PACKAGE_VERSION == v"0.1.0-DEV"
end

@testset "stable identifiers and hashes" begin
    @test string(TEST_PLUGIN) == "49f3be3e-9df0-499e-9ba8-a90b21ed5686/test"
    @test string(SCALAR_TYPE) == "49f3be3e-9df0-499e-9ba8-a90b21ed5686/test::scalar"
    @test string(PrimitiveId(TEST_PLUGIN, "distance")) ==
          "49f3be3e-9df0-499e-9ba8-a90b21ed5686/test::distance"
    @test parse(PluginId, string(TEST_PLUGIN)) == TEST_PLUGIN
    @test parse(TypeId, string(SCALAR_TYPE)) == SCALAR_TYPE
    @test parse(PrimitiveId, string(PrimitiveId(TEST_PLUGIN, "distance"))) ==
          PrimitiveId(TEST_PLUGIN, "distance")
    @test NodeId("node_1") == NodeId(join(["node", "_1"]))
    @test hash(NodeId("node_1")) == hash(NodeId(join(["node", "_1"])))
    @test_throws InvariantError NodeId("")
    @test_throws InvariantError VariableId("contains space")
    @test_throws InvariantError TypeId(TEST_PLUGIN, "bad/name")

    digest = content_hash("canonical")
    @test startswith(string(digest), "sha256:")
    @test length(hex(digest)) == 64
    @test ContentHash(string(digest)) == digest
    @test_throws InvariantError ContentHash(hex(digest))
    @test_throws InvariantError ContentHash("sha256:xyz")
end

@testset "capability metadata has no silent inference" begin
    capabilities = CapabilitySet(C0, C1, C2, C3V)
    @test supports(capabilities, C0)
    @test supports(capabilities, C3V)
    @test !supports(capabilities, C3A)
    @test collect(capabilities) == [C0, C1, C2, C3V]
    @test require_capability(capabilities, C2, "fixture") === nothing
    @test_throws CapabilityError require_capability(capabilities, C3A, "fixture")
    @test_throws InvariantError CapabilitySet(0xff)

    kernel = generic_kernel()
    @test kernel.generic_numeric
    @test kernel.derivative_mode == DERIVATIVE_AUTODIFF
    exact_kernel = OperatorKernel(
        identity;
        capabilities = CapabilitySet(C0, C3A),
        algebraic_prover = identity,
    )
    @test supports(exact_kernel.capabilities, C3A)
    @test_throws InvariantError OperatorKernel(identity; capabilities = CapabilitySet(C1))
    @test_throws InvariantError OperatorKernel(
        identity;
        capabilities = CapabilitySet(C0, C1),
        derivative_mode = DERIVATIVE_JACOBIAN,
    )
    @test_throws InvariantError OperatorKernel(
        identity;
        capabilities = CapabilitySet(C0, C2),
    )
    @test_throws InvariantError OperatorKernel(
        identity;
        capabilities = CapabilitySet(C0, C3V),
    )
    @test_throws InvariantError OperatorKernel(
        identity;
        capabilities = CapabilitySet(C0, C3A),
    )
end

@testset "Choice and Selection preserve branch evidence" begin
    empty_choice = Choice((), (), ())
    one_choice = Choice(([1.0, 2.0],), ("only",), (0.5,))
    two_choice = Choice((1.0, -1.0), ("positive", "negative"), (0.25, 0.3))

    @test isempty(empty_choice)
    @test length(one_choice) == 1
    @test length(two_choice) == 2
    @test two_choice.keys == (ChoiceKey("positive"), ChoiceKey("negative"))

    selected = Selection(two_choice, 2, 0.0)
    @test selected.value == -1.0
    @test selected.key == ChoiceKey("negative")
    @test selected.validity_margin == 0.3
    @test selected.selector_margin == 0.0
    @test EVAL_AMBIGUOUS_BRANCH != EVAL_INVALID_DOMAIN
    @test EVAL_INVALID_BRANCH != EVAL_AMBIGUOUS_BRANCH
    @test_throws InvariantError Selection(empty_choice, 1, 0.0)
    @test_throws InvariantError Choice((1, 2), ("same", "same"), (1.0, 1.0))
    @test_throws InvariantError Choice((1,), (), (1.0,))

    source = [1.0, 2.0]
    copied = Choice((source,), ("copied",), (1.0,))
    source[1] = 99.0
    @test copied.candidates[1] == [1.0, 2.0]
end

@testset "four-node graph IR is canonical and topological" begin
    literal_payload = [1.0, 2.0]
    literal = LiteralNode(NodeId("literal"), POINT_TYPE, literal_payload)
    reference = ReferenceNode(NodeId("x_ref"), VariableId("x"))
    operation = PrimitiveId(TEST_PLUGIN, "opaque_call")
    call = CallNode(
        NodeId("call"),
        operation,
        (literal.id, reference.id),
        (KeywordArg("zeta", reference.id), KeywordArg("alpha", literal.id)),
    )
    selector = SelectorId(TEST_PLUGIN, "near")
    selected = SelectNode(NodeId("selected"), call.id, selector, (reference.id,))
    graph = ConstructionGraph((literal, reference, call, selected))

    literal_payload[1] = 50.0
    @test literal.value == [1.0, 2.0]
    @test length(graph) == 4
    @test typeof(graph) === ConstructionGraph
    @test typeof(graph[3]) === CallNode
    @test typeof(graph[4]) === SelectNode
    @test map(keyword -> keyword.name, graph[3].keywords) == ("alpha", "zeta")
    @test referenced_nodes(graph[3]) ==
          (NodeId("literal"), NodeId("x_ref"), NodeId("literal"), NodeId("x_ref"))
    @test referenced_nodes(graph[4]) == (NodeId("call"), NodeId("x_ref"))

    @test_throws InvariantError CallNode(
        NodeId("bad_keywords"),
        operation,
        (),
        (KeywordArg("same", literal.id), KeywordArg("same", reference.id)),
    )
    @test_throws InvariantError ConstructionGraph((reference, reference))
    @test_throws InvariantError ConstructionGraph((call, literal, reference))
end

@testset "plugin ABI separates semantic roles" begin
    scalar = TypeSpec(SCALAR_TYPE, Float64; documentation = "scalar")
    point = TypeSpec(POINT_TYPE, NamedTuple)
    choice = TypeSpec(CHOICE_TYPE, Choice)
    signature = SignatureSpec((SCALAR_TYPE,), SCALAR_TYPE)
    point_signature = SignatureSpec((POINT_TYPE,), SCALAR_TYPE)
    branch_signature = SignatureSpec((SCALAR_TYPE,), CHOICE_TYPE)
    selector_signature = SignatureSpec((CHOICE_TYPE, POINT_TYPE), POINT_TYPE)
    kernel = generic_kernel()

    primitive = PrimitiveSpec(
        PrimitiveId(TEST_PLUGIN, "primitive"),
        (signature,),
        kernel,
    )
    relation = RelationSpec(
        PrimitiveId(TEST_PLUGIN, "relation"),
        (point_signature,),
        kernel;
        truth = iszero,
        scale_hint = 2,
    )
    guard = GuardSpec(
        PrimitiveId(TEST_PLUGIN, "guard"),
        (point_signature,),
        kernel;
        default_strict = true,
    )
    domain = DomainSpec(
        PrimitiveId(TEST_PLUGIN, "domain"),
        (point_signature,),
        kernel;
        singularity = iszero,
        default_strict = true,
    )
    branch = BranchSpec(
        PrimitiveId(TEST_PLUGIN, "branch"),
        (branch_signature,),
        POINT_TYPE,
        kernel,
    )
    selector = SelectorSpec(
        SelectorId(TEST_PLUGIN, "near"),
        (selector_signature,),
        kernel,
    )
    plugin = PluginSpec(
        TEST_PLUGIN,
        v"0.1.0",
        v"1.0.0",
        content_hash("plugin");
        types = (scalar, point, choice),
        primitives = (primitive,),
        relations = (relation,),
        guards = (guard,),
        domains = (domain,),
        branches = (branch,),
        selectors = (selector,),
    )

    @test plugin_lock(plugin) ==
          PluginLock(TEST_PLUGIN, v"0.1.0", v"1.0.0", content_hash("plugin"))
    @test plugin.guards[1].default_strict
    @test plugin.relations[1].truth === iszero
    @test plugin.domains[1].singularity === iszero
    @test plugin.branches[1].candidate_type == POINT_TYPE
    @test_throws InvariantError TypeSpec(SCALAR_TYPE, Float64; encoder = identity)
    @test_throws InvariantError SignatureSpec((), SCALAR_TYPE; variadic = true)
    @test_throws InvariantError RelationSpec(
        PrimitiveId(TEST_PLUGIN, "bad_scale"),
        (signature,),
        kernel;
        scale_hint = 0,
    )

    foreign_primitive = PrimitiveSpec(
        PrimitiveId(OTHER_PLUGIN, "foreign"),
        (SignatureSpec((TypeId(OTHER_PLUGIN, "scalar"),), TypeId(OTHER_PLUGIN, "scalar")),),
        kernel,
    )
    @test_throws InvariantError PluginSpec(
        TEST_PLUGIN,
        v"0.1.0",
        v"1.0.0",
        content_hash("foreign");
        primitives = (foreign_primitive,),
    )
    @test_throws InvariantError PluginSpec(
        TEST_PLUGIN,
        v"0.1.0",
        v"1.0.0",
        content_hash("duplicate");
        primitives = (primitive,),
        relations = (
            RelationSpec(primitive.id, (signature,), kernel),
        ),
    )
end

@testset "problem roles and variable domains are explicit" begin
    variable = VariableSpec(
        VariableId("x"),
        SCALAR_TYPE,
        0.0,
        2.0;
        lower = -1.0,
        upper = 1.0,
    )
    reference = ReferenceNode(NodeId("x"), variable.id)
    literal = LiteralNode(NodeId("zero"), SCALAR_TYPE, 0.0)
    operation = PrimitiveId(TEST_PLUGIN, "op")
    relation = CallNode(NodeId("relation"), operation, (reference.id, literal.id))
    guard = CallNode(NodeId("guard"), operation, (reference.id,))
    domain = CallNode(NodeId("domain"), operation, (reference.id,))
    target = CallNode(NodeId("target"), operation, (reference.id,))
    graph = ConstructionGraph((reference, literal, relation, guard, domain, target))
    lock = PluginLock(TEST_PLUGIN, v"0.1.0", v"1.0.0", content_hash("plugin"))
    problem = ProblemSpecV1(
        (lock,),
        (variable,),
        graph;
        relations = (RelationBinding(relation.id; scale_override = 3.0),),
        guards = (GuardBinding(guard.id, true; scale_override = 2.0),),
        domains = (DomainBinding(domain.id, false),),
        target = target.id,
    )

    @test problem.relations[1].scale_override == 3.0
    @test problem.guards[1].strict
    @test !problem.domains[1].strict
    @test variable.type_id == SCALAR_TYPE
    @test_throws InvariantError VariableSpec(VariableId("bad"), SCALAR_TYPE, 0.0, 0.0)
    @test_throws InvariantError VariableSpec(
        VariableId("outside"),
        SCALAR_TYPE,
        2.0,
        1.0;
        lower = -1.0,
        upper = 1.0,
    )
    @test_throws InvariantError RelationBinding(relation.id; scale_override = -1)
    @test_throws InvariantError ProblemSpecV1(
        (lock,),
        (variable,),
        graph;
        relations = (RelationBinding(relation.id),),
        guards = (GuardBinding(relation.id, true),),
        target = target.id,
    )

    unknown_reference = ReferenceNode(NodeId("unknown"), VariableId("y"))
    unknown_target = LiteralNode(NodeId("unknown_target"), SCALAR_TYPE, 0.0)
    unknown_graph = ConstructionGraph((unknown_reference, unknown_target))
    @test_throws InvariantError ProblemSpecV1(
        (),
        (variable,),
        unknown_graph;
        target = unknown_target.id,
    )
end

@testset "answer levels and certificates are disjoint" begin
    @test ExactInteger("-12") == ExactInteger(-12)
    @test_throws InvariantError ExactInteger("+1")
    @test ExactRational(2, -4) == ExactRational(-1, 2)
    @test_throws InvariantError ExactRational(1, 0)

    interval = RationalInterval((1, 1), (2, 1))
    identity = AlgebraicTargetIdentity((-2, 0, 1), interval, 1)
    @test_throws InvariantError AlgebraicTargetIdentity((-4, 0, 2), interval, 1)
    @test_throws InvariantError AlgebraicTargetIdentity((1, -2, 1), RationalInterval(0, 2), 1)
    @test_throws InvariantError AlgebraicTargetIdentity((-1, 1), RationalInterval(0, 1), 1)

    artifact = CertificateArtifact("interval_v1", "replayable")
    @test typeof(artifact) === CertificateArtifact
    @test typeof(CertificateArtifact("interval_v1", repeat("x", 1000))) === CertificateArtifact
    binary_artifact = CertificateArtifact("binary_v1", UInt8[0xff, 0x00, 0x7f])
    @test collect(codeunits(binary_artifact.payload)) == UInt8[0xff, 0x00, 0x7f]
    @test binary_artifact.digest == content_hash(UInt8[0xff, 0x00, 0x7f])
    problem_hash = content_hash("problem")
    config_certificate = ConfigurationValidityCertificate(
        problem_hash,
        content_hash("configuration"),
        artifact,
    )
    target_certificate = TargetIdentityCertificate(problem_hash, identity, artifact)
    branches = (BranchDecision(NodeId("intersection"), ChoiceKey("positive")),)
    exact = ExactAnswer(
        identity,
        sqrt(2),
        branches,
        config_certificate,
        target_certificate,
    )
    @test exact isa AbstractAnswer
    @test exact.configuration_certificate !== exact.target_certificate
    @test_throws InvariantError ExactAnswer(
        identity,
        sqrt(2),
        branches,
        config_certificate,
        TargetIdentityCertificate(problem_hash, content_hash("wrong"), artifact),
    )
    @test_throws InvariantError ExactAnswer(
        identity,
        sqrt(2),
        branches,
        config_certificate,
        TargetIdentityCertificate(content_hash("other_problem"), identity, artifact),
    )

    evidence = NumericalValidationEvidence(
        problem_hash,
        content_hash("configuration"),
        "bigfloat_recheck",
        256,
        artifact;
        independent = true,
    )
    provisional = ProvisionalAnswer(
        NumericEnclosure(1.4142, 1.4143),
        1.0e-20,
        branches,
        evidence;
        guard_enclosures = (
            GuardEnclosure(NodeId("strict_guard"), NumericEnclosure(0.1, 0.2), true),
            GuardEnclosure(NodeId("closed_guard"), NumericEnclosure(0.0, 0.3), false),
        ),
        exact_failure = EXACT_TARGET_CERT_FAILED,
        exact_failure_detail = "interval target proof did not contract",
    )
    @test provisional isa AbstractAnswer
    @test !(provisional isa ExactAnswer)
    @test provisional.exact_failure == EXACT_TARGET_CERT_FAILED
    @test provisional.guard_enclosures[1].enclosure.lower == 0.1
    @test_throws InvariantError GuardEnclosure(
        NodeId("strict_boundary"),
        NumericEnclosure(0.0, 0.1),
        true,
    )
    @test_throws InvariantError GuardEnclosure(
        NodeId("invalid_closed"),
        NumericEnclosure(-0.1, 0.1),
        false,
    )
    @test_throws InvariantError NumericalValidationEvidence(
        problem_hash,
        content_hash("configuration"),
        "same_pass",
        256,
        artifact;
        independent = false,
    )
    @test_throws InvariantError ProvisionalAnswer(
        NumericEnclosure(1.0, 1.1),
        -1.0,
        (),
        evidence;
        exact_failure = EXACT_RECOGNITION_FAILED,
    )
    @test_throws InvariantError ProvisionalAnswer(
        NumericEnclosure(1.0, 1.1),
        0.0,
        (
            BranchDecision(NodeId("same_choice"), ChoiceKey("a")),
            BranchDecision(NodeId("same_choice"), ChoiceKey("b")),
        ),
        evidence;
        exact_failure = EXACT_SINGULAR,
    )

    resume = ResumeIdentity(
        content_hash("graph"),
        (PluginLock(TEST_PLUGIN, v"0.1.0", v"1.0.0", content_hash("plugin")),),
        content_hash("policy"),
        content_hash("environment"),
    )
    @test can_resume(resume, deepcopy(resume))
    @test !can_resume(
        resume,
        ResumeIdentity(
            content_hash("other_graph"),
            resume.plugin_locks,
            resume.policy,
            resume.environment,
        ),
    )

    coverage = CoverageEvidence(3, 10, 8, 2; explored_shells = (0, 1), last_new_target_seconds = 2.5)
    evidence_log = EvidenceLogReference(content_hash("events"), "evidence/run-001.jsonl")
    result = SolveResult(
        (exact,),
        (provisional,),
        SEARCH_DEADLINE_REACHED,
        TARGET_FINITE_OBSERVED,
        coverage,
        resume,
        evidence_log,
    )
    @test length(result.exact_answers) == 1
    @test length(result.provisional_answers) == 1
    @test environment_lock(result) == resume
    @test result.evidence_log.content == content_hash("events")
    @test_throws InvariantError SolveResult(
        (exact,),
        (),
        SEARCH_EMPTY_CERTIFIED,
        TARGET_EMPTY_CERTIFIED,
        coverage,
        resume,
        evidence_log,
    )
    @test_throws InvariantError SolveResult(
        (),
        (),
        SEARCH_COMPLETE_CERTIFIED,
        TARGET_IMAGE_UNKNOWN,
        coverage,
        resume,
        evidence_log,
    )
    @test_throws InvariantError EvidenceLogReference(content_hash("events"), "")
end

@testset "architecture boundary" begin
    source_dir = normpath(joinpath(@__DIR__, "..", "src"))
    source = join((read(joinpath(source_dir, file), String) for file in readdir(source_dir)), "\n")
    @test !occursin("GeoTargetCore", source)
    @test !occursin("GeoTargetGeometry", source)
    @test !occursin(r"\b(Point|Line|Circle|Arc)\b", source)
    @test !occursin("JSON3", source)
    @test !isdefined(GeoTargetBase, :TargetCluster)
    @test !isdefined(GeoTargetBase, :FloatCandidate)
end
