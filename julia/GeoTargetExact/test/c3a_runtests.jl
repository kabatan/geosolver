using GeoTargetBase
using GeoTargetCore
using JSON3

const C3A_FIXTURE_PLUGIN =
    parse(PluginId, "d55cb834-03f7-4d26-a1bd-a17fb5393952/exact_phase_b_fixture")
const C3A_SCALAR = TypeId(C3A_FIXTURE_PLUGIN, "scalar")
const C3A_CHOICE = TypeId(C3A_FIXTURE_PLUGIN, "choice")
const C3A_BOX = TypeId(C3A_FIXTURE_PLUGIN, "box")

struct C3AFixtureBox{T}
    value::T
end

function c3a_fixture_kernel(evaluator, prover; enabled=true)
    capabilities = enabled ? CapabilitySet(C0, C2, C3A) : CapabilitySet(C0, C2)
    return OperatorKernel(
        evaluator;
        algebraic_prover=enabled ? prover : nothing,
        capabilities,
        generic_numeric=true,
        smoothness=SMOOTH_C1,
    )
end

function c3a_fixture_plugin(mode::Symbol=:valid)
    supported_modes = (
        :valid,
        :missing_c3a,
        :nonexact_callback,
        :false_relation,
        :strict_boundary,
        :branch_tie,
        :forged_validity_margin,
        :close_roots,
        :multiple_root,
        :structured_literal,
    )
    mode in supported_modes || throw(ArgumentError("unsupported C3A fixture mode"))
    enabled = mode != :missing_c3a
    scalar_binary = SignatureSpec((C3A_SCALAR, C3A_SCALAR), C3A_SCALAR)
    scalar_unary = SignatureSpec((C3A_SCALAR,), C3A_SCALAR)
    choice_signature = SignatureSpec((C3A_SCALAR,), C3A_CHOICE)
    selector_signature = SignatureSpec((C3A_CHOICE,), C3A_SCALAR)
    box_signature = SignatureSpec((C3A_BOX, C3A_SCALAR), C3A_SCALAR)

    close_delta = 1 // (BigInt(1) << 20)
    numeric_relation = if mode == :close_roots
        (x, _) -> (x - one(x)) * (x - (one(x) + close_delta))
    elseif mode == :multiple_root
        (x, _) -> (x - one(x)) * (x - one(x))
    else
        (x, two) -> x * x - two
    end
    exact_relation = if mode == :nonexact_callback
        (x, two) -> Float64(x * x - two)
    elseif mode == :false_relation
        (x, two) -> one(x)
    else
        numeric_relation
    end
    numeric_margin(x) = x
    exact_guard = mode == :strict_boundary ? x -> zero(x) : numeric_margin
    make_choice(x) = Choice((x,), ("positive_root",), (x,))
    exact_make_choice = mode == :forged_validity_margin ?
                        x -> Choice((x,), ("positive_root",), (-x,)) :
                        make_choice
    numeric_select(choice) = Selection(choice, 1, one(choice.validity_margins[1]))
    exact_select = if mode == :branch_tie
        choice -> Selection(choice, 1, zero(choice.validity_margins[1]))
    elseif mode == :forged_validity_margin
        choice -> begin
            forged = Choice(choice.candidates, choice.keys, (-choice.validity_margins[1],))
            Selection(forged, 1, one(choice.validity_margins[1]))
        end
    else
        numeric_select
    end
    consume_box(box, x) = x

    relation = RelationSpec(
        PrimitiveId(C3A_FIXTURE_PLUGIN, "root_relation"),
        (scalar_binary,),
        c3a_fixture_kernel(numeric_relation, exact_relation; enabled);
        truth=(x, two) -> iszero(numeric_relation(x, two)),
        truth_policy=RELATION_TRUTH_APPROXIMATE_ZERO,
        scale_hint=1.0,
    )
    equality = RelationSpec(
        PrimitiveId(C3A_FIXTURE_PLUGIN, "equality_relation"),
        (scalar_binary,),
        c3a_fixture_kernel((left, right) -> left - right, (left, right) -> left - right; enabled);
        truth=(left, right) -> iszero(left - right),
        truth_policy=RELATION_TRUTH_APPROXIMATE_ZERO,
        scale_hint=1.0,
    )
    guard = GuardSpec(
        PrimitiveId(C3A_FIXTURE_PLUGIN, "positive_guard"),
        (scalar_unary,),
        c3a_fixture_kernel(numeric_margin, exact_guard; enabled),
        default_strict=true,
        scale_hint=1.0,
    )
    domain = DomainSpec(
        PrimitiveId(C3A_FIXTURE_PLUGIN, "positive_domain"),
        (scalar_unary,),
        c3a_fixture_kernel(numeric_margin, numeric_margin; enabled),
        default_strict=true,
    )
    branch = BranchSpec(
        PrimitiveId(C3A_FIXTURE_PLUGIN, "root_choice"),
        (choice_signature,),
        C3A_SCALAR,
        c3a_fixture_kernel(make_choice, exact_make_choice; enabled),
    )
    selector = SelectorSpec(
        SelectorId(C3A_FIXTURE_PLUGIN, "select_root"),
        (selector_signature,),
        c3a_fixture_kernel(numeric_select, exact_select; enabled),
    )
    consume = PrimitiveSpec(
        PrimitiveId(C3A_FIXTURE_PLUGIN, "consume_box"),
        (box_signature,),
        c3a_fixture_kernel(consume_box, consume_box; enabled),
    )
    return PluginSpec(
        C3A_FIXTURE_PLUGIN,
        v"0.1.0",
        GeoTargetCore.CORE_ABI_VERSION,
        content_hash("GeoTargetExact-C3A-fixture-$mode-v1");
        types=(
            TypeSpec(C3A_SCALAR, Real),
            TypeSpec(C3A_CHOICE, Choice),
            TypeSpec(C3A_BOX, C3AFixtureBox),
        ),
        primitives=(consume,),
        relations=(relation, equality),
        guards=(guard,),
        domains=(domain,),
        branches=(branch,),
        selectors=(selector,),
    )
end

function c3a_fixture(
    mode::Symbol=:valid;
    two_variables::Bool=false,
    expect_validation::Bool=true,
)
    plugin = c3a_fixture_plugin(mode)
    builder = RegistryBuilder(allowlist=(plugin.id,))
    register!(builder, plugin)
    registry = freeze(builder)
    start_x = mode in (:close_roots, :multiple_root) ? 1.0 : 1.4
    variable = VariableSpec(
        VariableId("x"),
        C3A_SCALAR,
        start_x,
        1.0;
        lower=0.0,
        upper=2.0,
    )
    variables = VariableSpec[variable]
    nodes = AbstractGraphNode[
        ReferenceNode(NodeId("x_ref"), variable.id),
        LiteralNode(NodeId("two"), C3A_SCALAR, 2.0),
        CallNode(
            NodeId("relation"),
            PrimitiveId(C3A_FIXTURE_PLUGIN, "root_relation"),
            (NodeId("x_ref"), NodeId("two")),
        ),
        CallNode(
            NodeId("guard"),
            PrimitiveId(C3A_FIXTURE_PLUGIN, "positive_guard"),
            (NodeId("x_ref"),),
        ),
        CallNode(
            NodeId("domain"),
            PrimitiveId(C3A_FIXTURE_PLUGIN, "positive_domain"),
            (NodeId("x_ref"),),
        ),
        CallNode(
            NodeId("choice"),
            PrimitiveId(C3A_FIXTURE_PLUGIN, "root_choice"),
            (NodeId("x_ref"),),
        ),
        SelectNode(
            NodeId("selected"),
            NodeId("choice"),
            SelectorId(C3A_FIXTURE_PLUGIN, "select_root"),
        ),
    ]
    relation_bindings = RelationBinding[RelationBinding(NodeId("relation"))]
    starts = [start_x]
    if two_variables
        second = VariableSpec(
            VariableId("y"),
            C3A_SCALAR,
            1.3,
            1.0;
            lower=0.0,
            upper=2.0,
        )
        push!(variables, second)
        # Insert the second reference and equality relation at the end. Both
        # depend only on already declared graph nodes, so topology remains canonical.
        push!(nodes, ReferenceNode(NodeId("y_ref"), second.id))
        push!(
            nodes,
            CallNode(
                NodeId("equality"),
                PrimitiveId(C3A_FIXTURE_PLUGIN, "equality_relation"),
                (NodeId("y_ref"), NodeId("x_ref")),
            ),
        )
        push!(relation_bindings, RelationBinding(NodeId("equality")))
        push!(starts, 1.3)
    end
    target = NodeId("selected")
    if mode == :structured_literal
        push!(nodes, LiteralNode(NodeId("box"), C3A_BOX, C3AFixtureBox(0.5)))
        push!(
            nodes,
            CallNode(
                NodeId("boxed_target"),
                PrimitiveId(C3A_FIXTURE_PLUGIN, "consume_box"),
                (NodeId("box"), NodeId("selected")),
            ),
        )
        target = NodeId("boxed_target")
    end
    problem = ProblemSpecV1(
        (plugin_lock(plugin),),
        Tuple(variables),
        ConstructionGraph(nodes);
        relations=Tuple(relation_bindings),
        guards=(GuardBinding(NodeId("guard"), true),),
        domains=(DomainBinding(NodeId("domain"), true),),
        target,
    )
    compiled = compile_problem(problem, registry)
    validation = validate_candidate(compiled, starts)
    expect_validation ? (@test validation.accepted) : (@test !validation.accepted)
    return compiled, validation
end

const C3A_TEST_RECOGNITION_OPTIONS = RecognitionOptions(
    degree_limits=(1, 2),
    height_bits=(8,),
    base_precision_bits=768,
    confirmation_extra_bits=256,
)

const C3A_LOW_PRECISION_OPTIONS = RecognitionOptions(
    degree_limits=(1, 2, 4, 8),
    height_bits=(8,),
    base_precision_bits=256,
    confirmation_extra_bits=128,
)

function _shift_checkpoint_bigfloat!(document, delta::BigFloat)
    document["kind"] == "bigfloat" || error("fixture expected a BigFloat checkpoint real")
    bits = Int(document["precision_bits"])
    document["decimal"] = setprecision(BigFloat, bits) do
        string(parse(BigFloat, String(document["decimal"])) + BigFloat(delta))
    end
    return document
end

function _tamper_c3a_checkpoint(mutate!::Function, source::AbstractString)
    document = GeoTargetCore.parse_protocol_json(source)
    observed = only(
        event for event in document["state"]["events"] if event["kind"] == "observed"
    )
    mutate!(document["state"]["workspace"]["history"][1]["observation"])
    mutate!(observed["payload"])
    payload = Dict{String,Any}(
        "state" => document["state"],
        "target_image_status" => document["target_image_status"],
    )
    document["content_hash"] = string(GeoTargetCore.canonical_json_hash(payload))
    return GeoTargetCore.decode_checkpoint_document(document)
end

struct C3ACheckpointTriggerBackend <: AbstractExactBackend
    mode::Symbol
    cancelled::Base.RefValue{Bool}
end

struct C3ACrossSolutionBackend <: AbstractExactBackend
    answer::ExactAnswer
    recognition_options::RecognitionOptions
end

struct C3ARejectingSolverBackend <: AbstractExactBackend
    calls::Base.RefValue{Int}
end

GeoTargetCore.exact_backend_descriptor(::C3ARejectingSolverBackend) =
    ExactBackendDescriptor(
        "c3a-rejecting-solver-test",
        v"1.0.0",
        "reject-every-seed";
        configuration_certificate_schemes=("c3a_rejecting_configuration_v1",),
        target_certificate_schemes=("c3a_rejecting_target_v1",),
        policy_identity=content_hash("c3a-rejecting-solver-policy"),
        environment_identity=content_hash("c3a-rejecting-solver-environment"),
    )

function GeoTargetCore.exactify_candidate(
    backend::C3ARejectingSolverBackend,
    ::GeoTargetCore.CompiledProblem,
    ::ExactificationSeed,
    ::ExactSampleProvider,
)
    backend.calls[] += 1
    return ExactBackendOutcome(
        nothing,
        EXACTIFICATION_RECOGNITION_FAILED,
        "fixture rejects every seed",
    )
end

GeoTargetCore.exact_backend_descriptor(backend::C3ACrossSolutionBackend) =
    exact_backend_descriptor(NemoExactBackend(
        recognition_options=backend.recognition_options,
    ))

function GeoTargetCore.exactify_candidate(
    backend::C3ACrossSolutionBackend,
    ::GeoTargetCore.CompiledProblem,
    ::ExactificationSeed,
    provider::ExactSampleProvider,
)
    exact_sample(provider, 768; pass=:reference).accepted || error("768-bit sample failed")
    exact_sample(provider, 1024; pass=:reference).accepted || error("1024-bit sample failed")
    return ExactBackendOutcome(backend.answer, EXACTIFICATION_NONE, "")
end

GeoTargetCore.verify_exactified_answer(
    backend::C3ACrossSolutionBackend,
    compiled::GeoTargetCore.CompiledProblem,
    answer::ExactAnswer,
    provider::ExactSampleProvider,
) = GeoTargetCore.verify_exactified_answer(
    NemoExactBackend(recognition_options=backend.recognition_options),
    compiled,
    answer,
    provider,
)

GeoTargetCore.exact_backend_descriptor(::C3ACheckpointTriggerBackend) =
    ExactBackendDescriptor(
        "c3a-checkpoint-trigger-test",
        v"1.0.0",
        "trigger-resource-checkpoint";
        configuration_certificate_schemes=("test_configuration_v1",),
        target_certificate_schemes=("test_target_v1",),
        policy_identity=content_hash("c3a-checkpoint-trigger-policy"),
        environment_identity=content_hash("c3a-checkpoint-trigger-environment"),
    )

function GeoTargetCore.exactify_candidate(
    backend::C3ACheckpointTriggerBackend,
    ::GeoTargetCore.CompiledProblem,
    ::ExactificationSeed,
    provider::ExactSampleProvider,
)
    if backend.mode == :cancel
        backend.cancelled[] = true
    elseif backend.mode == :deadline
        provider.deadline_ns = 0
    else
        error("unsupported checkpoint trigger mode")
    end
    GeoTargetExact._checkpoint_provider(provider)
    error("resource checkpoint unexpectedly returned")
end

function successful_c3a_result()
    compiled, validation = c3a_fixture(:valid; two_variables=true)
    backend = NemoExactBackend(recognition_options=C3A_TEST_RECOGNITION_OPTIONS)
    result = run_exactification(
        backend,
        compiled,
        validation;
        remaining_oracle_work=500_000,
    )
    return compiled, validation, backend, result
end

function replace_configuration_artifact(answer, document, configuration_hash)
    old = answer.configuration_certificate
    artifact = CertificateArtifact(
        old.artifact.scheme,
        GeoTargetCore.canonical_json(document);
        media_type=old.artifact.media_type,
    )
    certificate = ConfigurationValidityCertificate(
        old.problem,
        configuration_hash,
        artifact,
    )
    return ExactAnswer(
        answer.identity,
        answer.approximation,
        answer.branch_signature,
        certificate,
        answer.target_certificate,
    )
end

@testset "C3A backend recognizes every free variable and self-verifies" begin
    compiled, validation, backend, result = successful_c3a_result()
    @test result.accepted
    @test result.failure == EXACTIFICATION_NONE
    @test result.answer isa ExactAnswer
    @test result.samples.requests == 4
    @test result.samples.cache_entries == 2
    @test length(result.reference_samples) == 2
    @test map(sample -> sample.precision_bits, result.reference_samples) == (768, 1024)
    @test all(sample -> sample.pass == :reference, result.reference_samples)
    @test result.oracle_work > 0
    @test result.backend == GeoTargetCore.exact_backend_descriptor(backend)
    @test result.backend.configuration_certificate_schemes ==
          ("geotarget-c3a-configuration-v1",)
    @test result.backend.target_certificate_schemes == ("geotarget-c3a-target-v1",)
    @test verify_stored_exact_answer(backend, compiled, result.answer).accepted
    descriptor = GeoTargetExact._descriptor_from_identity(result.answer.identity)
    @test descriptor.coefficients == (-2, 0, 1)
    @test verify_c3a_exact_answer(compiled, result.answer).accepted

    configuration_document = JSON3.read(
        result.answer.configuration_certificate.artifact.payload,
        Dict{String,Any},
    )
    @test length(configuration_document["claim"]["variables"]) == 2

    exact_coordinate = reconstruct_descriptor(descriptor)
    replay = replay_c3a(
        compiled,
        (exact_coordinate, exact_coordinate);
        expected_branches=validation.canonical_observation.branches,
    )
    @test replay.accepted
    @test length(replay.evidence.coordinates) == 2
    @test length(replay.evidence.relations) == 2
    @test all(proof -> iszero(proof.value), replay.evidence.relations)
    @test only(replay.evidence.guards).margin > zero(AlgebraicReal)
    @test only(replay.evidence.domains).margin > zero(AlgebraicReal)
    @test only(replay.evidence.branches).selector_margin > zero(AlgebraicReal)
end

@testset "rank-deficient hypothesis is exact-only and independently replayed" begin
    compiled, rejected = c3a_fixture(:multiple_root; expect_validation=false)
    @test rejected.provisional === nothing
    observation = GeoTargetCore.evaluate(compiled, [1.0]; capability=C0)
    seed = rank_deficient_exactification_seed(
        compiled,
        [1.0],
        observation;
        residual_tolerance=1.0e-12,
    )
    @test seed.kind == EXACT_SEED_RANK_DEFICIENT_HYPOTHESIS
    @test seed.branch_signature == Tuple(
        branch.decision for branch in observation.branches
    )

    result = run_exactification(
        NemoExactBackend(recognition_options=C3A_TEST_RECOGNITION_OPTIONS),
        compiled,
        seed;
        remaining_oracle_work=500_000,
    )
    @test result.accepted
    @test result.answer isa ExactAnswer
    @test verify_c3a_exact_answer(compiled, result.answer).accepted
    @test result.answer.approximation == 1.0
end

@testset "production solver promotes regular and singular candidates through C3A" begin
    options = SolveOptions(preset=:fast, wall_seconds=60.0, seed=0)
    backend = NemoExactBackend(recognition_options=C3A_TEST_RECOGNITION_OPTIONS)

    regular_compiled, _ = c3a_fixture(:valid)
    regular = solve_execution(
        regular_compiled.problem,
        regular_compiled.registry;
        options,
        max_actions=2,
        exact_backend=backend,
    )
    @test isempty(regular.result.provisional_answers)
    @test length(regular.result.exact_answers) == 1
    @test occursin("promotion=exact_regular", regular.evidence_json)
    @test verify_stored_exact_answer(
        backend,
        regular_compiled,
        only(regular.result.exact_answers),
    ).accepted
    checkpoint_source = encode_checkpoint_json(SolveCheckpointArtifact(regular))
    resumed_regular = solve_execution(
        regular_compiled.problem,
        regular_compiled.registry;
        options,
        max_actions=0,
        checkpoint=decode_checkpoint_json(checkpoint_source),
        exact_backend=backend,
    )
    @test only(resumed_regular.result.exact_answers).identity ==
          only(regular.result.exact_answers).identity

    shifted_endpoint = _tamper_c3a_checkpoint(checkpoint_source) do observation
        _shift_checkpoint_bigfloat!(observation["endpoint"][1], big"1e-6")
    end
    @test_throws SolveConfigurationError solve_execution(
        regular_compiled.problem,
        regular_compiled.registry;
        options,
        max_actions=0,
        checkpoint=shifted_endpoint,
        exact_backend=backend,
    )

    widened_target = _tamper_c3a_checkpoint(checkpoint_source) do observation
        _shift_checkpoint_bigfloat!(observation["target"]["lower"], -big"1e-6")
        _shift_checkpoint_bigfloat!(observation["target"]["upper"], big"1e-6")
    end
    @test_throws SolveConfigurationError solve_execution(
        regular_compiled.problem,
        regular_compiled.registry;
        options,
        max_actions=0,
        checkpoint=widened_target,
        exact_backend=backend,
    )

    shifted_target = _tamper_c3a_checkpoint(checkpoint_source) do observation
        _shift_checkpoint_bigfloat!(
            observation["verified_payload"]["value"]["approximation"],
            big"1e-6",
        )
        _shift_checkpoint_bigfloat!(observation["target"]["lower"], big"1e-6")
        _shift_checkpoint_bigfloat!(observation["target"]["upper"], big"1e-6")
    end
    @test_throws SolveConfigurationError solve_execution(
        regular_compiled.problem,
        regular_compiled.registry;
        options,
        max_actions=0,
        checkpoint=shifted_target,
        exact_backend=backend,
    )

    singular_compiled, rejected = c3a_fixture(:multiple_root; expect_validation=false)
    @test rejected.provisional === nothing
    singular = solve_execution(
        singular_compiled.problem,
        singular_compiled.registry;
        options,
        max_actions=2,
        exact_backend=backend,
    )
    @test isempty(singular.result.provisional_answers)
    @test length(singular.result.exact_answers) == 1
    @test singular.result.target_image_status == TARGET_FINITE_OBSERVED
    singular_record = only(singular.checkpoint.workspace.candidates.history)
    @test singular_record.observation.verified
    @test singular_record.observation.verified_payload isa ExactAnswer
    @test singular_record.observation.target.lower <= BigFloat(1) <=
          singular_record.observation.target.upper
    @test abs(only(singular_record.observation.endpoint) - BigFloat(1)) <= big"1e-100"
    @test occursin(
        "promotion=exact_only_numerically_unresolved",
        singular_record.observation.diagnostic,
    )

    rejecting = C3ARejectingSolverBackend(Ref(0))
    exact_only_failure = solve_execution(
        singular_compiled.problem,
        singular_compiled.registry;
        options,
        max_actions=2,
        exact_backend=rejecting,
    )
    @test rejecting.calls[] == 1
    @test isempty(exact_only_failure.result.exact_answers)
    @test isempty(exact_only_failure.result.provisional_answers)
    failed_record = only(exact_only_failure.checkpoint.workspace.candidates.history)
    @test !failed_record.observation.verified
    @test failed_record.observation.verified_payload === nothing
    @test failed_record.observation.needs_refinement
    @test occursin("EXACTIFICATION_RECOGNITION_FAILED", failed_record.observation.diagnostic)

    singular_observation = GeoTargetCore.evaluate(
        singular_compiled,
        [1.0];
        capability=C0,
    )
    rank_seed = rank_deficient_exactification_seed(
        singular_compiled,
        [1.0],
        singular_observation;
        residual_tolerance=1.0e-12,
    )
    relabelled = ExactificationSeed(
        EXACT_SEED_VALIDATED_REGULAR,
        rank_seed.problem,
        rank_seed.problem_hash_method,
        rank_seed.start,
        rank_seed.branch_signature,
        rank_seed.start_configuration,
    )
    relabelled_result = run_exactification(
        rejecting,
        singular_compiled,
        relabelled;
        remaining_oracle_work=500_000,
    )
    @test relabelled.kind == EXACT_SEED_VALIDATED_REGULAR
    @test !relabelled_result.accepted
    @test relabelled_result.answer === nothing
    @test isempty(exact_only_failure.result.provisional_answers)
end

@testset "C3A replay fails closed on callbacks and exact semantics" begin
    @test GeoTargetExact._c3a_literal(true, Real) === nothing
    @test GeoTargetExact._c3a_bound(nothing) == (true, nothing)
    @test GeoTargetExact._c3a_bound(Ref(1.0)) == (false, nothing)

    expected = Dict(
        :nonexact_callback => C3A_REPLAY_NONEXACT_VALUE,
        :false_relation => C3A_REPLAY_RELATION_FAILED,
        :strict_boundary => C3A_REPLAY_GUARD_FAILED,
        :branch_tie => C3A_REPLAY_BRANCH_FAILED,
        :forged_validity_margin => C3A_REPLAY_BRANCH_FAILED,
        :structured_literal => C3A_REPLAY_LITERAL_UNSUPPORTED,
    )
    exact_root = sqrt(AlgebraicReal(2))
    for (mode, failure) in expected
        compiled, validation = c3a_fixture(mode)
        replay = replay_c3a(
            compiled,
            (exact_root,);
            expected_branches=validation.canonical_observation.branches,
        )
        @test !replay.accepted
        @test replay.failure == failure
        backend_result = run_exactification(
            NemoExactBackend(recognition_options=C3A_TEST_RECOGNITION_OPTIONS),
            compiled,
            validation;
            remaining_oracle_work=500_000,
        )
        @test !backend_result.accepted
        @test backend_result.failure == EXACTIFICATION_REPLAY_FAILED
    end

    missing_compiled, missing_validation = c3a_fixture(:missing_c3a)
    missing = run_exactification(
        NemoExactBackend(recognition_options=C3A_TEST_RECOGNITION_OPTIONS),
        missing_compiled,
        missing_validation,
    )
    @test missing.failure == EXACTIFICATION_CAPABILITY_MISSING

    bounded_compiled, _ = c3a_fixture(:valid)
    below_bound = replay_c3a(bounded_compiled, (-sqrt(AlgebraicReal(2)),))
    @test below_bound.failure == C3A_REPLAY_BOUNDS_FAILED
end

@testset "C3A artifacts are reconstructed and independently replayed" begin
    compiled, _, _, result = successful_c3a_result()
    answer = result.answer

    wire_document = GeoTargetCore._exact_answer_document(answer, "answer")
    wire_answer = GeoTargetCore._decode_exact_answer(wire_document, "answer")
    @test verify_c3a_exact_answer(compiled, wire_answer).accepted

    proof_tamper = JSON3.read(
        answer.configuration_certificate.artifact.payload,
        Dict{String,Any},
    )
    proof_tamper["proof"]["relations_exactly_zero"] = Any[]
    tampered_proof_answer = replace_configuration_artifact(
        answer,
        proof_tamper,
        answer.configuration_certificate.configuration,
    )
    proof_verification = verify_c3a_exact_answer(compiled, tampered_proof_answer)
    @test !proof_verification.accepted
    @test proof_verification.failure == GeoTargetExact.C3A_VERIFY_CONFIGURATION_MISMATCH

    false_coordinate = JSON3.read(
        answer.configuration_certificate.artifact.payload,
        Dict{String,Any},
    )
    false_coordinate["claim"]["variables"][1]["descriptor"] =
        descriptor_document(descriptor_from_root(AlgebraicReal(1)))
    false_hash = content_hash(GeoTargetCore.canonical_json(false_coordinate["claim"]))
    false_coordinate["configuration"] = string(false_hash)
    false_answer = replace_configuration_artifact(answer, false_coordinate, false_hash)
    false_verification = verify_c3a_exact_answer(compiled, false_answer)
    @test !false_verification.accepted
    @test false_verification.failure == GeoTargetExact.C3A_VERIFY_REPLAY_FAILED

    branch_tamper = JSON3.read(
        answer.configuration_certificate.artifact.payload,
        Dict{String,Any},
    )
    branch_tamper["claim"]["branch_signature"][1]["key"] = "tampered_key"
    branch_hash = content_hash(GeoTargetCore.canonical_json(branch_tamper["claim"]))
    branch_tamper["configuration"] = string(branch_hash)
    branch_answer = replace_configuration_artifact(answer, branch_tamper, branch_hash)
    branch_verification = verify_c3a_exact_answer(compiled, branch_answer)
    @test !branch_verification.accepted
    @test branch_verification.failure in (
        GeoTargetExact.C3A_VERIFY_BRANCH_MISMATCH,
        GeoTargetExact.C3A_VERIFY_REPLAY_FAILED,
    )

    target_document = JSON3.read(
        answer.target_certificate.artifact.payload,
        Dict{String,Any},
    )
    target_document["descriptor"] = descriptor_document(
        descriptor_from_root(sqrt(AlgebraicReal(3))),
    )
    target_artifact = CertificateArtifact(
        answer.target_certificate.artifact.scheme,
        GeoTargetCore.canonical_json(target_document);
        media_type=answer.target_certificate.artifact.media_type,
    )
    target_certificate = TargetIdentityCertificate(
        answer.target_certificate.problem,
        answer.identity,
        target_artifact,
    )
    target_answer = ExactAnswer(
        answer.identity,
        answer.approximation,
        answer.branch_signature,
        answer.configuration_certificate,
        target_certificate,
    )
    target_verification = verify_c3a_exact_answer(compiled, target_answer)
    @test !target_verification.accepted
    @test target_verification.failure == GeoTargetExact.C3A_VERIFY_TARGET_MISMATCH

    noncanonical_artifact = CertificateArtifact(
        answer.configuration_certificate.artifact.scheme,
        "{\"x\":9007199254740992}";
        media_type=answer.configuration_certificate.artifact.media_type,
    )
    noncanonical_certificate = ConfigurationValidityCertificate(
        answer.configuration_certificate.problem,
        answer.configuration_certificate.configuration,
        noncanonical_artifact,
    )
    noncanonical_answer = ExactAnswer(
        answer.identity,
        answer.approximation,
        answer.branch_signature,
        noncanonical_certificate,
        answer.target_certificate,
    )
    noncanonical_verification = verify_c3a_exact_answer(compiled, noncanonical_answer)
    @test !noncanonical_verification.accepted
    @test noncanonical_verification.failure == GeoTargetExact.C3A_VERIFY_ARTIFACT_INVALID
end

@testset "C3A exact answer is bound to both reference precision samples" begin
    compiled, validation = c3a_fixture(:close_roots)
    delta = 1 // (BigInt(1) << 20)
    alternate = AlgebraicReal(one(BigInt) + delta)
    descriptor = descriptor_from_root(alternate)
    candidate = RecognitionCandidate(
        descriptor,
        1,
        64,
        768,
        1024,
        "test_alternate_root",
    )
    replay = replay_c3a(
        compiled,
        (alternate,);
        expected_branches=validation.canonical_observation.branches,
    )
    @test replay.accepted
    alternate_answer = GeoTargetExact._build_c3a_exact_answer(
        compiled,
        validation.problem,
        (candidate,),
        replay.evidence,
        approximation=validation.canonical_observation.target,
    )
    # The deliberately coarse isolating interval overlaps the numerical root,
    # so ordinary artifact replay alone cannot detect this cross-solution swap.
    @test verify_c3a_exact_answer(compiled, alternate_answer).accepted

    result = run_exactification(
        C3ACrossSolutionBackend(
            alternate_answer,
            C3A_TEST_RECOGNITION_OPTIONS,
        ),
        compiled,
        validation;
        remaining_oracle_work=500_000,
    )
    @test !result.accepted
    @test result.failure == EXACTIFICATION_VERIFICATION_FAILED
    @test occursin("reference sample", result.detail)

    shifted_compiled, shifted_validation, _, shifted_source = successful_c3a_result()
    source_answer = shifted_source.answer
    shifted_answer = ExactAnswer(
        source_answer.identity,
        BigFloat(source_answer.approximation) + big"1e-6",
        source_answer.branch_signature,
        source_answer.configuration_certificate,
        source_answer.target_certificate,
    )
    @test verify_c3a_exact_answer(shifted_compiled, shifted_answer).accepted
    stored_shifted = verify_stored_exact_answer(
        NemoExactBackend(recognition_options=C3A_TEST_RECOGNITION_OPTIONS),
        shifted_compiled,
        shifted_answer,
    )
    @test !stored_shifted.accepted
    @test stored_shifted.failure == EXACT_VERIFICATION_TARGET_MISMATCH
    @test occursin("approximation", stored_shifted.detail)
    shifted_result = run_exactification(
        C3ACrossSolutionBackend(
            shifted_answer,
            C3A_TEST_RECOGNITION_OPTIONS,
        ),
        shifted_compiled,
        shifted_validation;
        remaining_oracle_work=500_000,
    )
    @test !shifted_result.accepted
    @test shifted_result.failure == EXACTIFICATION_VERIFICATION_FAILED
    @test occursin("approximation", shifted_result.detail)
end

@testset "C3A backend resources and precision requests fail closed" begin
    compiled, validation = c3a_fixture(:valid)
    backend = NemoExactBackend(recognition_options=C3A_TEST_RECOGNITION_OPTIONS)
    exhausted = run_exactification(
        backend,
        compiled,
        validation;
        remaining_oracle_work=0,
    )
    @test !exhausted.accepted
    @test exhausted.failure == EXACTIFICATION_ORACLE_BUDGET_EXHAUSTED
    @test exhausted.oracle_work == 0

    cancelled = run_exactification(
        backend,
        compiled,
        validation;
        cancelled=() -> true,
    )
    @test cancelled.failure == EXACTIFICATION_CANCELLED
    @test cancelled.oracle_work == 0

    low_precision_backend = NemoExactBackend(recognition_options=C3A_LOW_PRECISION_OPTIONS)
    low_precision = run_exactification(
        low_precision_backend,
        compiled,
        validation;
        remaining_oracle_work=500_000,
    )
    @test !low_precision.accepted
    @test low_precision.failure == EXACTIFICATION_SAMPLE_FAILED
    @test occursin("precision_bits", low_precision.detail)

    cancel_flag = Ref(false)
    mid_cancel = run_exactification(
        C3ACheckpointTriggerBackend(:cancel, cancel_flag),
        compiled,
        validation;
        cancelled=() -> cancel_flag[],
        remaining_oracle_work=500_000,
    )
    @test mid_cancel.failure == EXACTIFICATION_CANCELLED
    @test mid_cancel.answer === nothing

    deadline_flag = Ref(false)
    mid_deadline = run_exactification(
        C3ACheckpointTriggerBackend(:deadline, deadline_flag),
        compiled,
        validation;
        remaining_oracle_work=500_000,
    )
    @test mid_deadline.failure == EXACTIFICATION_DEADLINE_REACHED
    @test mid_deadline.answer === nothing

    poll_count = Ref(0)
    stop_poll() = begin
        poll_count[] += 1
        poll_count[] >= 4 && throw(
            GeoTargetExact._ExactSampleAbort(EXACT_SAMPLE_CANCELLED, "test stop"),
        )
        nothing
    end
    pi_value = setprecision(BigFloat, 768) do
        BigFloat(pi)
    end
    @test_throws GeoTargetExact._ExactSampleAbort pslq_relation(
        pi_value,
        4,
        8;
        precision_bits=768,
        checkpoint=stop_poll,
    )
    @test poll_count[] == 4

    replay_polls = Ref(0)
    @test_throws GeoTargetExact._ExactSampleAbort replay_c3a(
        compiled,
        (sqrt(AlgebraicReal(2)),);
        expected_branches=validation.canonical_observation.branches,
        checkpoint=() -> begin
            replay_polls[] += 1
            replay_polls[] == 3 && throw(
                GeoTargetExact._ExactSampleAbort(EXACT_SAMPLE_CANCELLED, "replay stop"),
            )
            nothing
        end,
    )

    verified_compiled, _, _, verified_result = successful_c3a_result()
    @test_throws GeoTargetExact._ExactSampleAbort verify_c3a_exact_answer(
        verified_compiled,
        verified_result.answer;
        checkpoint=() -> throw(
            GeoTargetExact._ExactSampleAbort(EXACT_SAMPLE_CANCELLED, "verify stop"),
        ),
    )
end
