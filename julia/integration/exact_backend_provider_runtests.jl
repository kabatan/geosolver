using GeoTargetBase
using GeoTargetCore
using GeoTargetGeometry
using Test

function exact_backend_fixture(tag="")
    plugin = geometry_plugin()
    builder = RegistryBuilder(allowlist=(plugin.id,))
    register!(builder, plugin)
    registry = freeze(builder)
    variable = VariableSpec(
        VariableId("exact_provider_x$tag"),
        SCALAR_TYPE_ID,
        0.0,
        1.0;
        lower=-2.0,
        upper=2.0,
    )
    graph = ConstructionGraph((
        ReferenceNode(NodeId("exact_provider_x_ref$tag"), variable.id),
        LiteralNode(NodeId("exact_provider_one$tag"), SCALAR_TYPE_ID, 1.0),
        CallNode(
            NodeId("exact_provider_relation$tag"),
            PrimitiveId(GEOMETRY_PLUGIN_ID, "scalar_equality"),
            (NodeId("exact_provider_x_ref$tag"), NodeId("exact_provider_one$tag")),
        ),
    ))
    problem = ProblemSpecV1(
        (plugin_lock(plugin),),
        (variable,),
        graph;
        relations=(RelationBinding(NodeId("exact_provider_relation$tag")),),
        target=NodeId("exact_provider_x_ref$tag"),
    )
    compiled = compile_problem(problem, registry)
    validation = validate_candidate(compiled, [0.8])
    @test validation.accepted
    return compiled, validation
end

struct ReportingExactBackend <: AbstractExactBackend
    bits::Int
end

function test_backend_descriptor(id, method)
    return ExactBackendDescriptor(
        id,
        v"1.0.0",
        method;
        configuration_certificate_schemes=("test_configuration_v1",),
        target_certificate_schemes=("test_target_v1",),
        policy_identity=content_hash("$id-policy-v1"),
        environment_identity=content_hash("$id-environment-v1"),
    )
end

GeoTargetCore.exact_backend_descriptor(::ReportingExactBackend) =
    test_backend_descriptor("reporting-test", "sample_then_fail")

function GeoTargetCore.exactify_candidate(
    backend::ReportingExactBackend,
    ::GeoTargetCore.CompiledProblem,
    ::ExactificationSeed,
    provider::ExactSampleProvider,
)
    first = exact_sample(provider, backend.bits; pass=:compiled)
    first.accepted || return ExactBackendOutcome(
        nothing,
        EXACTIFICATION_RECOGNITION_FAILED,
        "fixture sample failed",
        reported_oracle_work=typemax(Int),
    )
    second = exact_sample(provider, backend.bits; pass=:compiled)
    second.accepted && second.cached || error("fixture cache contract failed")
    return ExactBackendOutcome(
        nothing,
        EXACTIFICATION_RECOGNITION_FAILED,
        "fixture intentionally stops before recognition",
        reported_oracle_work=typemax(Int),
    )
end

struct UnsupportedExactBackend <: AbstractExactBackend end
GeoTargetCore.exact_backend_descriptor(::UnsupportedExactBackend) =
    test_backend_descriptor("unsupported-test", "none")

struct MissingDescriptorBackend <: AbstractExactBackend end

struct LegacyAbiBackend <: AbstractExactBackend end
GeoTargetCore.exact_backend_descriptor(::LegacyAbiBackend) = ExactBackendDescriptor(
    "legacy-abi-test",
    v"1.0.0",
    "obsolete-abi";
    backend_abi_version=v"1.1.0",
    configuration_certificate_schemes=("test_configuration_v1",),
    target_certificate_schemes=("test_target_v1",),
    policy_identity=content_hash("legacy-abi-policy"),
    environment_identity=content_hash("legacy-abi-environment"),
)

struct LegacyCandidateSignatureBackend <: AbstractExactBackend
    called::Base.RefValue{Bool}
end
GeoTargetCore.exact_backend_descriptor(::LegacyCandidateSignatureBackend) =
    test_backend_descriptor("legacy-signature-test", "obsolete-candidate-validation-signature")
function GeoTargetCore.exactify_candidate(
    backend::LegacyCandidateSignatureBackend,
    ::GeoTargetCore.CompiledProblem,
    ::CandidateValidationResult,
    ::ExactSampleProvider,
)
    backend.called[] = true
    return ExactBackendOutcome(nothing, EXACTIFICATION_RECOGNITION_FAILED, "legacy method ran")
end

struct WrongOutcomeBackend <: AbstractExactBackend end
GeoTargetCore.exact_backend_descriptor(::WrongOutcomeBackend) =
    test_backend_descriptor("wrong-outcome-test", "invalid")
GeoTargetCore.exactify_candidate(
    ::WrongOutcomeBackend,
    ::GeoTargetCore.CompiledProblem,
    ::ExactificationSeed,
    ::ExactSampleProvider,
) = :not_a_typed_outcome

struct NoSampleAnswerBackend <: AbstractExactBackend
    scheme_matches::Bool
end

GeoTargetCore.exact_backend_descriptor(::NoSampleAnswerBackend) =
    test_backend_descriptor("no-sample-answer-test", "forged-answer")

function forged_exact_answer(seed::ExactificationSeed, scheme_matches::Bool=true)
    identity = AlgebraicTargetIdentity(
        (-1, 1),
        RationalInterval(0 // 1, 2 // 1),
        1,
    )
    configuration_scheme = scheme_matches ? "test_configuration_v1" : "wrong_configuration_v1"
    configuration = ConfigurationValidityCertificate(
        seed.problem,
        seed.start_configuration,
        CertificateArtifact(configuration_scheme, "{}"; media_type="application/json"),
    )
    target = TargetIdentityCertificate(
        seed.problem,
        identity,
        CertificateArtifact("test_target_v1", "{}"; media_type="application/json"),
    )
    return ExactAnswer(identity, 1.0, seed.branch_signature, configuration, target)
end

GeoTargetCore.exactify_candidate(
    backend::NoSampleAnswerBackend,
    ::GeoTargetCore.CompiledProblem,
    seed::ExactificationSeed,
    ::ExactSampleProvider,
) = ExactBackendOutcome(
    forged_exact_answer(seed, backend.scheme_matches),
    EXACTIFICATION_NONE,
    "",
)

struct SampledUnverifiedBackend <: AbstractExactBackend end
GeoTargetCore.exact_backend_descriptor(::SampledUnverifiedBackend) =
    test_backend_descriptor("sampled-unverified-test", "sample-then-forge")

function GeoTargetCore.exactify_candidate(
    ::SampledUnverifiedBackend,
    ::GeoTargetCore.CompiledProblem,
    seed::ExactificationSeed,
    provider::ExactSampleProvider,
)
    exact_sample(provider, 512; pass=:reference).accepted || error("512-bit sample failed")
    exact_sample(provider, 768; pass=:reference).accepted || error("768-bit sample failed")
    return ExactBackendOutcome(
        forged_exact_answer(seed),
        EXACTIFICATION_NONE,
        "",
    )
end

@testset "Core-owned arbitrary-precision exact sample provider" begin
    compiled, validation = exact_backend_fixture()
    seed = exactification_seed(compiled, validation)
    @test seed.kind == EXACT_SEED_VALIDATED_REGULAR
    @test seed.problem == validation.problem
    @test seed.problem_hash_method == validation.problem_hash_method
    @test seed.start == validation.canonical_coordinates
    @test seed.branch_signature == ()
    provider = ExactSampleProvider(
        compiled,
        seed;
        remaining_oracle_work=100_000,
    )
    @test provider.seed.kind == seed.kind
    @test provider.seed.problem == seed.problem
    @test provider.seed.problem_hash_method == seed.problem_hash_method
    @test provider.seed.start == seed.start
    @test provider.seed.branch_signature == seed.branch_signature
    @test provider.seed.start_configuration == seed.start_configuration
    compiled_sample = exact_sample(provider, 640; pass=:compiled)
    @test compiled_sample.accepted
    @test !compiled_sample.cached
    @test compiled_sample.sample !== nothing
    sample = compiled_sample.sample
    @test sample.precision_bits == 640
    @test sample.minimum_value_precision_bits >= 640
    @test sample.pass == :compiled
    @test sample.gates.accuracy_bits == 640 - 96
    @test sample.gates.residual_accuracy_bits == 640 - 64
    @test sample.residual_bound <= sample.gates.residual_goal
    @test sample.correction_bound <= sample.gates.correction_tolerance
    @test sample.target_error_bound <= sample.gates.target_tolerance
    @test sample.work.oracle_work == cld(640, 53) * sample.work.raw_oracle_work

    cached = exact_sample(provider, 640; pass=:compiled)
    @test cached.accepted
    @test cached.cached
    @test cached.work == ExactSampleWork(0, 0, 0)
    @test cached.sample.coordinates == sample.coordinates

    reference = exact_sample(provider, 640; pass=:reference)
    @test reference.accepted
    @test reference.sample.pass == :reference
    @test reference.sample.method == "reference_c2_rank_general_lm_5point_v1"
    @test reference.sample.coordinates == sample.coordinates
    snapshot = exact_sample_provider_snapshot(provider)
    @test snapshot.requests == 3
    @test snapshot.cache_entries == 2
    @test snapshot.oracle_work ==
          compiled_sample.work.oracle_work + reference.work.oracle_work
    @test snapshot.oracle_work <= snapshot.oracle_work_limit
end

@testset "exactification seeds are immutable hypotheses and fail closed" begin
    compiled, validation = exact_backend_fixture("_seed_contract")
    seed = exactification_seed(compiled, validation)
    wrong_method = ExactificationSeed(
        seed.kind,
        seed.problem,
        "forged_hash_method",
        seed.start,
        seed.branch_signature,
        seed.start_configuration,
    )
    wrong_configuration = ExactificationSeed(
        seed.kind,
        seed.problem,
        seed.problem_hash_method,
        seed.start,
        seed.branch_signature,
        content_hash("forged-seed-configuration"),
    )
    @test_throws ArgumentError ExactSampleProvider(compiled, wrong_method)
    @test_throws ArgumentError ExactSampleProvider(compiled, wrong_configuration)
    @test run_exactification(UnsupportedExactBackend(), compiled, wrong_method).failure ==
          EXACTIFICATION_INVALID_CANDIDATE
    @test run_exactification(UnsupportedExactBackend(), compiled, wrong_configuration).failure ==
          EXACTIFICATION_INVALID_CANDIDATE

    legacy_called = Ref(false)
    legacy = run_exactification(
        LegacyCandidateSignatureBackend(legacy_called),
        compiled,
        validation,
    )
    @test !legacy.accepted
    @test legacy.failure == EXACTIFICATION_UNSUPPORTED
    @test !legacy_called[]
    abi_mismatch = run_exactification(LegacyAbiBackend(), compiled, validation)
    @test !abi_mismatch.accepted
    @test abi_mismatch.failure == EXACTIFICATION_BACKEND_PROTOCOL_FAILED
    @test occursin("ABI version", abi_mismatch.detail)

    observation = GeoTargetCore.evaluate(compiled, collect(seed.start); capability=C0)
    hypothesis = rank_deficient_exactification_seed(
        compiled,
        seed.start,
        observation;
        residual_tolerance=1.0e-12,
    )
    @test hypothesis.kind == EXACT_SEED_RANK_DEFICIENT_HYPOTHESIS
    @test hypothesis.problem == seed.problem
    @test hypothesis.start == seed.start
    @test hypothesis.branch_signature == seed.branch_signature
    @test_throws ArgumentError rank_deficient_exactification_seed(
        compiled,
        seed.start,
        observation;
        residual_tolerance=true,
    )
    @test_throws ArgumentError rank_deficient_exactification_seed(
        compiled,
        seed.start,
        observation;
        residual_tolerance=Inf,
    )
end

@testset "exact sample resources and public counts fail closed" begin
    compiled, validation = exact_backend_fixture()

    no_budget = ExactSampleProvider(compiled, validation; remaining_oracle_work=0)
    exhausted = exact_sample(no_budget, 640)
    @test !exhausted.accepted
    @test exhausted.failure == EXACT_SAMPLE_ORACLE_BUDGET_EXHAUSTED
    @test exact_sample_provider_snapshot(no_budget).oracle_work == 0

    cancelled = ExactSampleProvider(compiled, validation; cancelled=() -> true)
    @test exact_sample(cancelled, 640).failure == EXACT_SAMPLE_CANCELLED
    @test exact_sample_provider_snapshot(cancelled).evaluations == 0
    @test exact_sample_provider_snapshot(cancelled).fatal_failure == EXACT_SAMPLE_CANCELLED

    deadline = ExactSampleProvider(compiled, validation; deadline_ns=0)
    @test exact_sample(deadline, 640).failure == EXACT_SAMPLE_DEADLINE_REACHED
    @test exact_sample_provider_snapshot(deadline).oracle_work == 0
    @test exact_sample_provider_snapshot(deadline).fatal_failure ==
          EXACT_SAMPLE_DEADLINE_REACHED

    invalid_cancel = ExactSampleProvider(compiled, validation; cancelled=() -> 1)
    @test exact_sample(invalid_cancel, 640).failure == EXACT_SAMPLE_INTERNAL_ERROR
    @test exact_sample(invalid_cancel, 640).failure == EXACT_SAMPLE_INTERNAL_ERROR

    request_provider = ExactSampleProvider(compiled, validation)
    checkpoint = exactification_checkpoint(request_provider)
    @test checkpoint.ready
    @test checkpoint.failure == EXACT_SAMPLE_NONE
    @test exact_sample(request_provider, true).failure == EXACT_SAMPLE_INVALID_REQUEST
    @test exact_sample(request_provider, big(typemax(Int)) + 1).failure ==
          EXACT_SAMPLE_INVALID_REQUEST
    @test exact_sample(request_provider, 640; pass=:neither).failure ==
          EXACT_SAMPLE_INVALID_REQUEST

    @test_throws ArgumentError ExactSampleProvider(
        compiled,
        validation;
        remaining_oracle_work=true,
    )
    @test_throws ArgumentError ExactSampleProvider(
        compiled,
        validation;
        remaining_oracle_work=big(typemax(Int)) + 1,
    )
    @test_throws ArgumentError ExactSampleProvider(compiled, validation; deadline_ns=true)
    @test_throws ArgumentError ExactSampleProvider(
        compiled,
        validation;
        deadline_ns=big(typemax(UInt64)) + 1,
    )

    rejected = validate_candidate(compiled, [0.8]; remaining_oracle_work=0)
    @test !rejected.accepted
    @test_throws ArgumentError ExactSampleProvider(compiled, rejected)
end

@testset "backend answers require Core evidence and independent verification" begin
    compiled, validation = exact_backend_fixture("_verification")

    no_samples = run_exactification(
        NoSampleAnswerBackend(true),
        compiled,
        validation;
        remaining_oracle_work=100_000,
    )
    @test !no_samples.accepted
    @test no_samples.failure == EXACTIFICATION_VERIFICATION_FAILED
    @test occursin("two independent reference samples", no_samples.detail)
    @test no_samples.samples.requests == 0

    wrong_scheme = run_exactification(
        NoSampleAnswerBackend(false),
        compiled,
        validation;
        remaining_oracle_work=100_000,
    )
    @test !wrong_scheme.accepted
    @test wrong_scheme.failure == EXACTIFICATION_VERIFICATION_FAILED
    @test occursin("scheme", wrong_scheme.detail)

    unverified = run_exactification(
        SampledUnverifiedBackend(),
        compiled,
        validation;
        remaining_oracle_work=100_000,
    )
    @test !unverified.accepted
    @test unverified.failure == EXACTIFICATION_VERIFICATION_FAILED
    @test occursin("independent exact verification failed", unverified.detail)
    @test unverified.samples.cache_entries == 2
end

@testset "backend work reports never affect the Core ledger" begin
    compiled, validation = exact_backend_fixture()
    result = run_exactification(
        ReportingExactBackend(640),
        compiled,
        validation;
        remaining_oracle_work=100_000,
    )
    @test !result.accepted
    @test result.failure == EXACTIFICATION_RECOGNITION_FAILED
    @test result.backend.id == "reporting-test"
    @test result.backend.backend_abi_version == EXACT_BACKEND_ABI_VERSION
    @test result.backend.configuration_certificate_schemes == ("test_configuration_v1",)
    @test result.backend.target_certificate_schemes == ("test_target_v1",)
    @test result.backend_reported_oracle_work == typemax(Int)
    @test 0 < result.oracle_work < typemax(Int)
    @test result.oracle_work == result.samples.oracle_work
    @test result.samples.requests == 2
    @test result.samples.cache_entries == 1

    unsupported = run_exactification(UnsupportedExactBackend(), compiled, validation)
    @test unsupported.failure == EXACTIFICATION_UNSUPPORTED
    @test unsupported.oracle_work == 0

    missing = run_exactification(MissingDescriptorBackend(), compiled, validation)
    @test missing.failure == EXACTIFICATION_BACKEND_PROTOCOL_FAILED
    @test missing.backend === nothing

    wrong = run_exactification(WrongOutcomeBackend(), compiled, validation)
    @test wrong.failure == EXACTIFICATION_BACKEND_PROTOCOL_FAILED
    @test wrong.oracle_work == 0

    stopped = run_exactification(
        ReportingExactBackend(640),
        compiled,
        validation;
        cancelled=() -> true,
    )
    @test stopped.failure == EXACTIFICATION_CANCELLED
    @test stopped.samples.requests == 0
    @test stopped.oracle_work == 0

    exhausted = run_exactification(
        ReportingExactBackend(640),
        compiled,
        validation;
        remaining_oracle_work=0,
    )
    @test exhausted.failure == EXACTIFICATION_ORACLE_BUDGET_EXHAUSTED
    @test exhausted.oracle_work == 0
    @test exhausted.backend_reported_oracle_work == typemax(Int)

    rejected = validate_candidate(compiled, [0.8]; remaining_oracle_work=0)
    invalid = run_exactification(UnsupportedExactBackend(), compiled, rejected)
    @test invalid.failure == EXACTIFICATION_INVALID_CANDIDATE
    @test invalid.backend.id == "unsupported-test"
    @test invalid.oracle_work == 0

    other_compiled, other_validation = exact_backend_fixture("_other")
    @test other_compiled !== compiled
    mismatch = run_exactification(UnsupportedExactBackend(), compiled, other_validation)
    @test mismatch.failure == EXACTIFICATION_INVALID_CANDIDATE

    missing_and_invalid = run_exactification(MissingDescriptorBackend(), compiled, rejected)
    @test missing_and_invalid.failure == EXACTIFICATION_BACKEND_PROTOCOL_FAILED

    @test_throws ArgumentError run_exactification(
        UnsupportedExactBackend(),
        compiled,
        validation;
        remaining_oracle_work=-1,
    )
end
