module EndToEndSolveTests

using GeoTargetBase
using GeoTargetCore
using GeoTargetGeometry
using Test

const NEAR_RANK_PLUGIN_ID =
    parse(PluginId, "11111111-1111-1111-1111-111111111111/near_rank_audit")
const NEAR_RANK_SUM_ID = PrimitiveId(NEAR_RANK_PLUGIN_ID, "sum_relation")
const NEAR_RANK_TILT_ID = PrimitiveId(NEAR_RANK_PLUGIN_ID, "tilted_relation")
const NEAR_RANK_ZERO_ID = PrimitiveId(NEAR_RANK_PLUGIN_ID, "zero_relation")

_near_rank_sum(left::Real, right::Real) = left + right
_near_rank_tilt(left::Real, right::Real, delta::Real) =
    left + (one(right) + delta) * right
_near_rank_zero(left::Real, right::Real) = zero(left + right)
_near_rank_sum_truth(left::Real, right::Real) = iszero(_near_rank_sum(left, right))
_near_rank_tilt_truth(left::Real, right::Real, delta::Real) =
    iszero(_near_rank_tilt(left, right, delta))
_near_rank_zero_truth(::Real, ::Real) = true

function _near_rank_kernel(evaluator)
    return OperatorKernel(
        evaluator;
        capabilities=CapabilitySet(C0, C1, C2),
        smoothness=SMOOTH_C1,
        derivative_mode=DERIVATIVE_AUTODIFF,
        generic_numeric=true,
    )
end

function near_rank_plugin()
    binary = SignatureSpec((SCALAR_TYPE_ID, SCALAR_TYPE_ID), SCALAR_TYPE_ID)
    ternary = SignatureSpec(
        (SCALAR_TYPE_ID, SCALAR_TYPE_ID, SCALAR_TYPE_ID),
        SCALAR_TYPE_ID,
    )
    return PluginSpec(
        NEAR_RANK_PLUGIN_ID,
        v"0.0.1",
        v"1.0.0",
        content_hash("near-rank-audit-plugin-v1");
        relations=(
            RelationSpec(
                NEAR_RANK_SUM_ID,
                (binary,),
                _near_rank_kernel(_near_rank_sum);
                truth=_near_rank_sum_truth,
                truth_policy=RELATION_TRUTH_APPROXIMATE_ZERO,
                scale_hint=1.0,
            ),
            RelationSpec(
                NEAR_RANK_TILT_ID,
                (ternary,),
                _near_rank_kernel(_near_rank_tilt);
                truth=_near_rank_tilt_truth,
                truth_policy=RELATION_TRUTH_APPROXIMATE_ZERO,
                scale_hint=1.0,
            ),
            RelationSpec(
                NEAR_RANK_ZERO_ID,
                (binary,),
                _near_rank_kernel(_near_rank_zero);
                truth=_near_rank_zero_truth,
                scale_hint=1.0,
            ),
        ),
    )
end

function singular_zero_manifold_problem()
    geometry = geometry_plugin()
    near_rank = near_rank_plugin()
    x = VariableSpec(
        VariableId("x"),
        SCALAR_TYPE_ID,
        0.0,
        1.0;
        lower=-2.0,
        upper=2.0,
    )
    y = VariableSpec(
        VariableId("y"),
        SCALAR_TYPE_ID,
        0.0,
        1.0;
        lower=-2.0,
        upper=2.0,
    )
    nodes = AbstractGraphNode[
        ReferenceNode(NodeId("x"), x.id),
        ReferenceNode(NodeId("y"), y.id),
        CallNode(
            NodeId("zero_relation_1"),
            NEAR_RANK_ZERO_ID,
            (NodeId("x"), NodeId("y")),
        ),
        CallNode(
            NodeId("zero_relation_2"),
            NEAR_RANK_ZERO_ID,
            (NodeId("y"), NodeId("x")),
        ),
    ]
    return ProblemSpecV1(
        (plugin_lock(geometry), plugin_lock(near_rank)),
        (x, y),
        ConstructionGraph(Tuple(nodes));
        relations=(
            RelationBinding(NodeId("zero_relation_1")),
            RelationBinding(NodeId("zero_relation_2")),
        ),
        target=NodeId("x"),
    )
end

function near_rank_registry()
    geometry = geometry_plugin()
    near_rank = near_rank_plugin()
    builder = RegistryBuilder(allowlist=(geometry.id, near_rank.id))
    register!(builder, geometry)
    register!(builder, near_rank)
    return freeze(builder)
end

function near_rank_problem(delta::Real)
    geometry = geometry_plugin()
    near_rank = near_rank_plugin()
    x = VariableSpec(
        VariableId("x"),
        SCALAR_TYPE_ID,
        0.0,
        1.0;
        lower=-2.0,
        upper=2.0,
    )
    y = VariableSpec(
        VariableId("y"),
        SCALAR_TYPE_ID,
        0.0,
        1.0;
        lower=-2.0,
        upper=2.0,
    )
    nodes = AbstractGraphNode[
        ReferenceNode(NodeId("x"), x.id),
        ReferenceNode(NodeId("y"), y.id),
        LiteralNode(NodeId("delta"), SCALAR_TYPE_ID, delta),
        CallNode(
            NodeId("sum_relation"),
            NEAR_RANK_SUM_ID,
            (NodeId("x"), NodeId("y")),
        ),
        CallNode(
            NodeId("tilted_relation"),
            NEAR_RANK_TILT_ID,
            (NodeId("x"), NodeId("y"), NodeId("delta")),
        ),
    ]
    return ProblemSpecV1(
        (plugin_lock(geometry), plugin_lock(near_rank)),
        (x, y),
        ConstructionGraph(Tuple(nodes));
        relations=(
            RelationBinding(NodeId("sum_relation")),
            RelationBinding(NodeId("tilted_relation")),
        ),
        target=NodeId("x"),
    )
end

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

function evaluated_constant_problem()
    plugin = geometry_plugin()
    graph = ConstructionGraph((
        LiteralNode(NodeId("constant-zero-a"), SCALAR_TYPE_ID, 0.0),
        LiteralNode(NodeId("constant-zero-b"), SCALAR_TYPE_ID, 0.0),
        CallNode(
            NodeId("constant-point"),
            PrimitiveId(plugin.id, "point2"),
            (NodeId("constant-zero-a"), NodeId("constant-zero-b")),
        ),
        CallNode(
            NodeId("constant-target"),
            PrimitiveId(plugin.id, "distance"),
            (NodeId("constant-point"), NodeId("constant-point")),
        ),
    ))
    return ProblemSpecV1(
        (plugin_lock(plugin),),
        (),
        graph;
        target=NodeId("constant-target"),
    )
end

function unconstrained_target_problem()
    plugin = geometry_plugin()
    variable = VariableSpec(
        VariableId("x"),
        SCALAR_TYPE_ID,
        0.0,
        1.0;
        lower=-2.0,
        upper=2.0,
    )
    graph = ConstructionGraph((ReferenceNode(NodeId("x"), variable.id),))
    return ProblemSpecV1(
        (plugin_lock(plugin),),
        (variable,),
        graph;
        target=NodeId("x"),
    )
end

function constant_manifold_problem(value=7.0)
    plugin = geometry_plugin()
    variable = VariableSpec(
        VariableId("free"),
        SCALAR_TYPE_ID,
        0.0,
        1.0;
        lower=-2.0,
        upper=2.0,
    )
    graph = ConstructionGraph((LiteralNode(NodeId("target"), SCALAR_TYPE_ID, value),))
    return ProblemSpecV1(
        (plugin_lock(plugin),),
        (variable,),
        graph;
        target=NodeId("target"),
    )
end

function evaluated_constant_manifold_problem()
    plugin = geometry_plugin()
    variable = VariableSpec(
        VariableId("free-evaluated"),
        SCALAR_TYPE_ID,
        0.0,
        1.0;
        lower=-2.0,
        upper=2.0,
    )
    graph = ConstructionGraph((
        ReferenceNode(NodeId("free-evaluated-ref"), variable.id),
        LiteralNode(NodeId("zero"), SCALAR_TYPE_ID, 0.0),
        CallNode(
            NodeId("same-point"),
            PrimitiveId(plugin.id, "point2"),
            (NodeId("free-evaluated-ref"), NodeId("zero")),
        ),
        CallNode(
            NodeId("target"),
            PrimitiveId(plugin.id, "distance"),
            (NodeId("same-point"), NodeId("same-point")),
        ),
    ))
    return ProblemSpecV1(
        (plugin_lock(plugin),),
        (variable,),
        graph;
        target=NodeId("target"),
    )
end

function short_options(; kwargs...)
    return SolveOptions(; preset=:fast, wall_seconds=60.0, seed=17, kwargs...)
end

function options_with_oracle_budget(limit::Integer)
    options = short_options()
    source = options.policy
    limits = source.budget_limits
    policy = GeoTargetCore.SolvePolicy(
        Val(:internal),
        source.preset,
        source.wall_seconds,
        GeoTargetCore.BudgetLimits(
            proposals=limits.proposals,
            local_attempts=limits.local_attempts,
            refinements=limits.refinements,
            oracle_work=limit,
        ),
        source._h0,
    )
    return GeoTargetCore.SolveOptions(
        options.version,
        options.preset,
        options.wall_seconds,
        options.seed,
        options.answer_level,
        options.worker_count,
        policy,
        options._local,
        options._validation,
    )
end

struct SolverFixtureExactBackend <: AbstractExactBackend
    promote::Bool
    descriptor_tag::String
    exact_calls::Base.RefValue{Int}
    stored_verify_calls::Base.RefValue{Int}
end

function solver_fixture_exact_backend(; promote=true, descriptor_tag="v1")
    return SolverFixtureExactBackend(
        promote,
        String(descriptor_tag),
        Ref(0),
        Ref(0),
    )
end

GeoTargetCore.exact_backend_descriptor(backend::SolverFixtureExactBackend) =
    ExactBackendDescriptor(
        "solver-fixture-exact",
        v"1.0.0",
        "two-reference-fixture";
        configuration_certificate_schemes=("solver_fixture_configuration_v1",),
        target_certificate_schemes=("solver_fixture_target_v1",),
        policy_identity=content_hash("solver-fixture-policy-$(backend.descriptor_tag)"),
        environment_identity=content_hash("solver-fixture-environment-v1"),
    )

function GeoTargetCore.exactify_candidate(
    backend::SolverFixtureExactBackend,
    ::GeoTargetCore.CompiledProblem,
    seed::ExactificationSeed,
    provider::ExactSampleProvider,
)
    backend.exact_calls[] += 1
    backend.promote || return ExactBackendOutcome(
        nothing,
        EXACTIFICATION_RECOGNITION_FAILED,
        "fixture exactification was intentionally rejected",
    )
    first = exact_sample(provider, 512; pass=:reference)
    first.accepted || return ExactBackendOutcome(
        nothing,
        EXACTIFICATION_SAMPLE_FAILED,
        first.detail,
    )
    second = exact_sample(provider, 768; pass=:reference)
    second.accepted || return ExactBackendOutcome(
        nothing,
        EXACTIFICATION_SAMPLE_FAILED,
        second.detail,
    )
    identity = AlgebraicTargetIdentity((-1, 1), RationalInterval(0 // 1, 2 // 1), 1)
    configuration = ConfigurationValidityCertificate(
        seed.problem,
        seed.start_configuration,
        CertificateArtifact(
            "solver_fixture_configuration_v1",
            "{}";
            media_type="application/json",
        ),
    )
    target = TargetIdentityCertificate(
        seed.problem,
        identity,
        CertificateArtifact(
            "solver_fixture_target_v1",
            "{}";
            media_type="application/json",
        ),
    )
    answer = ExactAnswer(
        identity,
        second.sample.target,
        seed.branch_signature,
        configuration,
        target,
    )
    return ExactBackendOutcome(answer, EXACTIFICATION_NONE, "")
end

GeoTargetCore.verify_exactified_answer(
    ::SolverFixtureExactBackend,
    ::GeoTargetCore.CompiledProblem,
    ::ExactAnswer,
    ::ExactSampleProvider,
) = ExactVerificationResult(true, EXACT_VERIFICATION_NONE, "")

function GeoTargetCore.verify_stored_exact_answer(
    backend::SolverFixtureExactBackend,
    ::GeoTargetCore.CompiledProblem,
    ::ExactAnswer,
    ;
    observation::Union{Nothing,GeoTargetCore.StoredExactObservation}=nothing,
    checkpoint=() -> nothing,
)
    checkpoint()
    backend.stored_verify_calls[] += 1
    return ExactVerificationResult(true, EXACT_VERIFICATION_NONE, "")
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
    @test answer.validation.method == "compiled512_reference768_confirmation"
    @test answer.validation.precision_bits == 768
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

@testset "optional exact backend is budgeted, replayed, and resume-bound" begin
    registry = solve_registry()
    problem = scalar_root_problem()
    options = short_options()
    numerical = solve_execution(problem, registry; options, max_actions=2)

    backend = solver_fixture_exact_backend()
    exact = solve_execution(
        problem,
        registry;
        options,
        max_actions=2,
        exact_backend=backend,
    )
    @test isempty(exact.result.provisional_answers)
    @test length(exact.result.exact_answers) == 1
    @test backend.exact_calls[] == 1
    @test backend.stored_verify_calls[] == 0
    @test exact.checkpoint.budget.oracle_work > numerical.checkpoint.budget.oracle_work
    @test occursin("exactification=accepted", exact.evidence_json)
    @test occursin("promotion=exact_regular", exact.evidence_json)
    @test exact.result.environment_lock.policy != numerical.result.environment_lock.policy
    @test exact.result.environment_lock.environment != numerical.result.environment_lock.environment

    resumed = solve_execution(
        problem,
        registry;
        options,
        max_actions=0,
        checkpoint=SolveCheckpointArtifact(exact),
        exact_backend=backend,
    )
    @test only(resumed.result.exact_answers).identity ==
          only(exact.result.exact_answers).identity
    @test backend.stored_verify_calls[] == 1
    @test_throws GeoTargetCore.SearchProtocolError solve_execution(
        problem,
        registry;
        options,
        max_actions=0,
        checkpoint=SolveCheckpointArtifact(exact),
    )
    @test_throws GeoTargetCore.SearchProtocolError solve_execution(
        problem,
        registry;
        options,
        max_actions=0,
        checkpoint=SolveCheckpointArtifact(exact),
        exact_backend=solver_fixture_exact_backend(descriptor_tag="different"),
    )
    cancelled_token = CancellationToken()
    cancel!(cancelled_token)
    @test_throws SolveConfigurationError solve_execution(
        problem,
        registry;
        options,
        cancel=cancelled_token,
        max_actions=0,
        checkpoint=SolveCheckpointArtifact(exact),
        exact_backend=backend,
    )
    snapshot = exact.checkpoint
    expired_snapshot = GeoTargetCore.CheckpointSnapshot(
        snapshot.resume_identity,
        snapshot.policy_version,
        snapshot.budget,
        snapshot.workspace,
        snapshot.events,
        snapshot.rng_state,
        snapshot.precision_bits,
        0.0,
        snapshot.cancelled,
    )
    expired = SolveCheckpointArtifact(
        expired_snapshot,
        exact.result.target_image_status,
    )
    @test_throws SolveConfigurationError solve_execution(
        problem,
        registry;
        options,
        max_actions=0,
        checkpoint=expired,
        exact_backend=backend,
    )

    rejected_backend = solver_fixture_exact_backend(promote=false)
    fallback = solve_execution(
        problem,
        registry;
        options,
        max_actions=2,
        exact_backend=rejected_backend,
    )
    @test isempty(fallback.result.exact_answers)
    @test length(fallback.result.provisional_answers) == 1
    fallback_answer = only(fallback.result.provisional_answers)
    @test fallback_answer.exact_failure == EXACT_RECOGNITION_FAILED
    @test occursin("intentionally rejected", fallback_answer.exact_failure_detail)
    @test rejected_backend.exact_calls[] == 1
    @test rejected_backend.stored_verify_calls[] == 0
    @test occursin("EXACTIFICATION_RECOGNITION_FAILED", fallback.evidence_json)
    @test occursin("promotion=validated_numerical", fallback.evidence_json)

    validated_backend = solver_fixture_exact_backend()
    validated_options = short_options(answer_level=:validated)
    validated_only = solve_execution(
        problem,
        registry;
        options=validated_options,
        max_actions=2,
        exact_backend=validated_backend,
    )
    @test isempty(validated_only.result.exact_answers)
    @test length(validated_only.result.provisional_answers) == 1
    @test validated_backend.exact_calls[] == 0
    @test validated_backend.stored_verify_calls[] == 0
    @test validated_only.result.environment_lock.policy ==
          canonical_json_hash(GeoTargetCore._solve_policy_document(validated_options))
    @test !haskey(GeoTargetCore._solve_policy_document(validated_options), "exact_backend")
end

@testset "singular nonzero residuals fail closed before answer promotion" begin
    registry = near_rank_registry()
    singular = compile_problem(near_rank_problem(1.0e-13), registry)
    start = [1.0, -1.0]
    attempt = solve_local(
        coordinates -> evaluate(singular, coordinates),
        start;
        lower=[-2.0, -2.0],
        upper=[2.0, 2.0],
        options=LocalSolveOptions(residual_tolerance=1.0e-12),
    )
    @test attempt.status == LOCAL_CONVERGED
    @test attempt.accepted

    singular_image = analyze_target_image(singular, collect(attempt.final))
    @test singular_image.classification == TARGET_IMAGE_INCONCLUSIVE
    @test singular_image.failure == GeoTargetCore.TARGET_IMAGE_SINGULAR_LINEARIZATION
    @test singular_image.numerical_rank == 1
    singular_correction = GeoTargetCore._candidate_root_correction(
        singular_image,
        LocalSolveOptions(),
    )
    @test !singular_correction.resolved
    @test singular_correction.detail == "rank_deficient_nonzero_residual"

    direct_validation = validate_candidate(singular, attempt)
    @test direct_validation.accepted
    @test direct_validation.provisional.target.lower <= BigFloat(0) <=
          direct_validation.provisional.target.upper
    @test maximum(abs, direct_validation.canonical_coordinates) <= big"1e-100"

    execution = solve_execution(
        near_rank_problem(1.0e-13),
        registry;
        options=short_options(),
        max_actions=2,
    )
    @test isempty(execution.result.provisional_answers)
    @test execution.result.target_image_status == TARGET_IMAGE_UNKNOWN
    record = only(execution.checkpoint.workspace.candidates.history)
    @test record.observation.canonical_near_feasible
    @test !record.observation.verified
    @test record.observation.verified_payload === nothing
    @test record.observation.needs_refinement
    @test occursin("rank_deficient_nonzero_residual", record.observation.diagnostic)
    @test execution.checkpoint.workspace.refinement_queue ==
          (record.observation.configuration_id,)

    exact_zero_execution = solve_execution(
        singular_zero_manifold_problem(),
        registry;
        options=short_options(),
        max_actions=2,
    )
    @test isempty(exact_zero_execution.result.provisional_answers)
    exact_zero_record = only(exact_zero_execution.checkpoint.workspace.candidates.history)
    @test !exact_zero_record.observation.canonical_valid
    @test !exact_zero_record.observation.verified
    @test exact_zero_record.observation.verified_payload === nothing
    @test exact_zero_record.observation.needs_refinement
    @test occursin("TARGET_IMAGE_INCONCLUSIVE", exact_zero_record.observation.diagnostic)
    @test occursin("exact_zero_residual", exact_zero_record.observation.diagnostic)

    exact_zero_image = analyze_target_image(singular, [0.0, 0.0])
    exact_zero_correction = GeoTargetCore._candidate_root_correction(
        exact_zero_image,
        LocalSolveOptions(),
    )
    @test exact_zero_correction.resolved
    @test exact_zero_correction.detail == "exact_zero_residual"

    full_rank = compile_problem(near_rank_problem(1.0e-4), registry)
    full_rank_image = analyze_target_image(full_rank, [1.0e-13, -1.0e-13])
    @test full_rank_image.classification == TARGET_LOCALLY_ISOLATED
    @test full_rank_image.numerical_rank == 2
    full_rank_correction = GeoTargetCore._candidate_root_correction(
        full_rank_image,
        LocalSolveOptions(),
    )
    @test full_rank_correction.resolved
    half_rank_image = analyze_target_image(
        full_rank,
        [1.0e-13, -1.0e-13];
        options=GeoTargetCore._half_radius_target_image_options(
            TargetImageDiagnosticOptions(),
        ),
    )
    compared_correction = GeoTargetCore._candidate_root_correction(
        full_rank_image,
        LocalSolveOptions(),
        half_rank_image,
    )
    @test compared_correction.resolved
    @test compared_correction.jacobian_relative_disagreement <= 1.0e-8
    @test compared_correction.linear_solve_relative_disagreement <= 1.0e-10
    corrected = GeoTargetCore._corrected_endpoint(
        full_rank,
        [1.0e-13, -1.0e-13],
        compared_correction.normalized_correction,
    )
    @test corrected !== nothing
    @test GeoTargetCore._residual_score(evaluate(full_rank, corrected)) <
          GeoTargetCore._residual_score(full_rank_image.base_observation)
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
    @test isempty(execution.result.provisional_answers)
    @test length(execution.result.exact_answers) == 1
    answer = only(execution.result.exact_answers)
    @test Tuple(coefficient.decimal for coefficient in answer.identity.coefficients) ==
          ("-7", "2")
    @test answer.approximation == 3.5
    @test answer.configuration_certificate.problem == answer.target_certificate.problem
    @test answer.target_certificate.identity == GeoTargetBase._identity_hash(answer.identity)
    @test encode_solve_result_json(decode_solve_result_json(
        encode_solve_result_json(execution.result),
    )) == encode_solve_result_json(execution.result)

    checkpoint_source = encode_checkpoint_json(SolveCheckpointArtifact(execution))
    checkpoint = decode_checkpoint_json(checkpoint_source)
    @test encode_checkpoint_json(checkpoint) == checkpoint_source
    resumed = solve_execution(
        constant_problem(),
        registry;
        options=short_options(),
        max_actions=0,
        checkpoint,
    )
    @test isempty(resumed.result.provisional_answers)
    @test length(resumed.result.exact_answers) == 1
    resumed_answer = only(resumed.result.exact_answers)
    @test typeof(resumed_answer.approximation) === typeof(answer.approximation)
    @test resumed_answer.approximation == answer.approximation
    @test resumed_answer.target_certificate.identity == answer.target_certificate.identity

    @test execution.result.evidence_log.location == abspath(destination)
    @test read(destination, String) == execution.evidence_json
    @test content_hash(read(destination)) == execution.result.evidence_log.content
    rm(destination; force=true)

    validated = solve_execution(
        constant_problem(),
        registry;
        options=short_options(answer_level=:validated),
    )
    @test isempty(validated.result.exact_answers)
    @test length(validated.result.provisional_answers) == 1
    provisional = only(validated.result.provisional_answers)
    @test provisional.target.lower <= BigFloat(3.5) <= provisional.target.upper
end

@testset "constant confirmation obeys oracle, cancellation and deadline budgets" begin
    registry = solve_registry()
    problem = evaluated_constant_problem()
    compiled = compile_problem(problem, registry)
    limited = solve_execution(
        problem,
        registry;
        options=options_with_oracle_budget(compiled.logical_evaluation_cost),
    )
    @test isempty(limited.result.provisional_answers)
    @test isempty(limited.result.exact_answers)
    @test limited.checkpoint.budget.oracle_work <= compiled.logical_evaluation_cost
    @test occursin("CANDIDATE_VALIDATION_ORACLE_BUDGET_EXHAUSTED", limited.evidence_json)

    token = CancellationToken()
    cancel!(token)
    cancelled = solve_execution(
        problem,
        registry;
        options=short_options(),
        cancel=token,
    )
    @test cancelled.loop_status == GeoTargetCore.LOOP_CANCELLED
    @test cancelled.result.search_status == SEARCH_CANCELLED
    @test isempty(cancelled.result.provisional_answers)

    deadline = solve_execution(
        problem,
        registry;
        options=SolveOptions(preset=:fast, wall_seconds=1.0e-9),
    )
    @test deadline.loop_status == GeoTargetCore.LOOP_DEADLINE_REACHED
    @test deadline.result.search_status == SEARCH_DEADLINE_REACHED
    @test isempty(deadline.result.provisional_answers)
end

function _checkpoint_trace(execution::SolveExecution)
    document = Any[
        Dict{String,Any}(
            "kind" => string(event.kind),
            "payload" => GeoTargetCore._checkpoint_event_payload_document(
                event,
                "trace.payload",
            ),
        ) for event in execution.checkpoint.events if !(
            event.kind === GeoTargetCore.EVENT_STATUS &&
            event.payload.status === GeoTargetCore.LOOP_PAUSED
        )
    ]
    return canonical_json(document)
end

function _result_without_evidence(result::SolveResult)
    document = solve_result_document(result)
    delete!(document, "evidence_log")
    return canonical_json(document)
end

@testset "canonical checkpoint persistence resumes the deterministic trace" begin
    registry = solve_registry()
    problem = scalar_root_problem()
    options = short_options()
    uninterrupted = solve_execution(problem, registry; options, max_actions = 4)
    prefix = solve_execution(problem, registry; options, max_actions = 2)

    checkpoint = SolveCheckpointArtifact(prefix)
    source = encode_checkpoint_json(checkpoint)
    decoded = decode_checkpoint_json(source)
    @test encode_checkpoint_json(decoded) == source
    @test checkpoint_hash(decoded) == checkpoint_hash(checkpoint)
    @test decoded.snapshot.resume_identity == prefix.result.environment_lock

    resumed = solve_execution(
        problem,
        registry;
        options,
        max_actions = 2,
        checkpoint = decoded,
    )
    @test _result_without_evidence(resumed.result) ==
          _result_without_evidence(uninterrupted.result)
    @test canonical_json(GeoTargetCore._checkpoint_workspace_document(
        resumed.checkpoint.workspace,
    )) == canonical_json(GeoTargetCore._checkpoint_workspace_document(
        uninterrupted.checkpoint.workspace,
    ))
    @test isequal(resumed.checkpoint.budget, uninterrupted.checkpoint.budget)
    @test isequal(_checkpoint_trace(resumed), _checkpoint_trace(uninterrupted))

    pending_prefix = solve_execution(problem, registry; options, max_actions = 1)
    @test length(pending_prefix.checkpoint.workspace.pending) == 1
    pending_checkpoint = decode_checkpoint_json(
        encode_checkpoint_json(SolveCheckpointArtifact(pending_prefix)),
    )
    pending_resumed = solve_execution(
        problem,
        registry;
        options,
        max_actions = 3,
        checkpoint = pending_checkpoint,
    )
    @test _result_without_evidence(pending_resumed.result) ==
          _result_without_evidence(uninterrupted.result)
    @test canonical_json(GeoTargetCore._checkpoint_workspace_document(
        pending_resumed.checkpoint.workspace,
    )) == canonical_json(GeoTargetCore._checkpoint_workspace_document(
        uninterrupted.checkpoint.workspace,
    ))
    @test isequal(pending_resumed.checkpoint.budget, uninterrupted.checkpoint.budget)
    @test isequal(_checkpoint_trace(pending_resumed), _checkpoint_trace(uninterrupted))

    mktempdir() do directory
        path = joinpath(directory, "checkpoint.json")
        @test write_checkpoint(path, prefix).content == checkpoint.content
        @test read_checkpoint(path).content == checkpoint.content
        write(path, "old checkpoint contents")
        @test write_checkpoint(path, prefix).content == checkpoint.content
        @test read_checkpoint(path).content == checkpoint.content
        @test isempty(filter(name -> occursin(".tmp-", name), readdir(directory)))
    end
    @test_throws ArgumentError write_checkpoint("   ", prefix)

    corrupted = parse_protocol_json(source)
    corrupted["state"]["budget"]["proposals"] += 1
    @test_throws ProtocolJsonError decode_checkpoint_document(corrupted)

    invalid = parse_protocol_json(source)
    invalid["state"]["budget"]["proposals"] = 10_000
    payload = Dict{String,Any}(
        "target_image_status" => invalid["target_image_status"],
        "state" => invalid["state"],
    )
    invalid["content_hash"] = string(canonical_json_hash(payload))
    @test_throws ProtocolJsonError decode_checkpoint_document(invalid)

    mismatched_options = SolveOptions(preset = :fast, wall_seconds = 61.0, seed = 17)
    @test_throws GeoTargetCore.SearchProtocolError solve_execution(
        problem,
        registry;
        options = mismatched_options,
        max_actions = 2,
        checkpoint = decoded,
    )
end

@testset "solve distinguishes continuous target images from constant manifolds" begin
    registry = solve_registry()
    continuous = solve_execution(
        unconstrained_target_problem(),
        registry;
        options=short_options(),
        max_actions=2,
    )
    @test continuous.result.target_image_status == TARGET_LIKELY_CONTINUOUS
    @test isempty(continuous.result.exact_answers)
    @test isempty(continuous.result.provisional_answers)
    @test continuous.result.search_status == SEARCH_FINISHED_UNKNOWN
    @test occursin("TARGET_LIKELY_CONTINUOUS", continuous.evidence_json)

    continuous_checkpoint = decode_checkpoint_json(
        encode_checkpoint_json(SolveCheckpointArtifact(continuous)),
    )
    resumed_continuous = solve_execution(
        unconstrained_target_problem(),
        registry;
        options = short_options(),
        max_actions = 2,
        checkpoint = continuous_checkpoint,
    )
    @test resumed_continuous.result.target_image_status == TARGET_LIKELY_CONTINUOUS

    constant_manifold = solve_execution(
        constant_manifold_problem(),
        registry;
        options=short_options(),
        max_actions=2,
    )
    @test constant_manifold.result.target_image_status == TARGET_IMAGE_UNKNOWN
    @test isempty(constant_manifold.result.provisional_answers)
    @test occursin("TARGET_LOCALLY_CONSTANT_MANIFOLD", constant_manifold.evidence_json)
    @test occursin("CANDIDATE_PRIMARY_REFINEMENT_FAILED", constant_manifold.evidence_json)
end

@testset "target-image work respects the enclosing oracle budget" begin
    registry = solve_registry()
    problem = evaluated_constant_manifold_problem()
    compiled = GeoTargetCore.compile_problem(problem, registry)
    @test compiled.logical_evaluation_cost > 0
    oracle_limit = 2 * compiled.logical_evaluation_cost
    execution = solve_execution(
        problem,
        registry;
        options=options_with_oracle_budget(oracle_limit),
        max_actions=2,
    )
    @test execution.loop_status != GeoTargetCore.LOOP_PROTOCOL_ERROR
    @test execution.loop_status != GeoTargetCore.LOOP_CALLBACK_ERROR
    @test execution.result.search_status == SEARCH_FINISHED_UNKNOWN
    @test execution.result.target_image_status == TARGET_IMAGE_UNKNOWN
    @test isempty(execution.result.provisional_answers)
    @test execution.checkpoint.budget.oracle_work <= oracle_limit
    @test occursin("TARGET_IMAGE_ORACLE_BUDGET_EXHAUSTED", execution.evidence_json)
    @test !occursin("callback_budget_overrun", execution.evidence_json)
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

@testset "unstable research strategy injects only numerical components" begin
    registry = solve_registry()
    problem = scalar_root_problem()
    options = short_options()
    default_policy = GeoTargetCore._solve_policy_document(options)
    default_hash = canonical_json_hash(default_policy)
    @test string(default_hash) ==
          "sha256:d02351d7dd936e891096b7abccf4f7bac62f4c6564efb0e2131b66f7acd3a5ee"

    proposal_factory_calls = Ref(0)
    local_solver_calls = Ref(0)
    observed_sparsity = Ref{Any}(nothing)
    strategy = UnstableResearchStrategy(
        "integration/default-components-v1",
        (compiled, solve_options) -> begin
            proposal_factory_calls[] += 1
            ProposalEngine(compiled.problem; seed=solve_options.seed)
        end,
        (compiled, evaluate_fn, start; kwargs...) -> begin
            local_solver_calls[] += 1
            observed_sparsity[] = compiled.sparsity.jacobian_entries
            solve_local(evaluate_fn, start; kwargs...)
        end,
    )
    strategy_policy = GeoTargetCore._solve_policy_document(options, strategy)
    @test strategy_policy["unstable_research_strategy_id"] == strategy.id
    @test canonical_json_hash(strategy_policy) != default_hash

    execution = solve_execution(
        problem,
        registry;
        options,
        max_actions=2,
        research_strategy=strategy,
    )
    @test proposal_factory_calls[] == 1
    @test local_solver_calls[] == 1
    @test observed_sparsity[] == ((1, 1),)
    @test length(execution.result.provisional_answers) == 1
    @test execution.result.environment_lock.policy == canonical_json_hash(strategy_policy)

    default_execution = solve_execution(problem, registry; options, max_actions=2)
    @test default_execution.result.environment_lock.policy == default_hash
    @test_throws SolveConfigurationError solve_execution(
        problem,
        registry;
        options,
        checkpoint=SolveCheckpointArtifact(default_execution),
        research_strategy=strategy,
    )
    @test_throws ArgumentError UnstableResearchStrategy(
        "Unversioned Strategy",
        strategy.proposal_factory,
        strategy.local_solver,
    )
end

end
