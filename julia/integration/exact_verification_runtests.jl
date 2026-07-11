module ExactVerificationTests

using GeoTargetBase
using GeoTargetCore
using GeoTargetGeometry
using Test

function exact_registry()
    plugin = geometry_plugin()
    builder = RegistryBuilder(allowlist=(plugin.id,))
    register!(builder, plugin)
    return freeze(builder)
end

function literal_problem(value=3.5)
    plugin = geometry_plugin()
    return ProblemSpecV1(
        (plugin_lock(plugin),),
        (),
        ConstructionGraph((LiteralNode(NodeId("target"), SCALAR_TYPE_ID, value),));
        target=NodeId("target"),
    )
end

function replace_configuration_artifact(answer, artifact; problem=answer.configuration_certificate.problem)
    configuration = ConfigurationValidityCertificate(
        problem,
        answer.configuration_certificate.configuration,
        artifact,
    )
    target = problem == answer.target_certificate.problem ?
             answer.target_certificate : TargetIdentityCertificate(
        problem,
        answer.identity,
        answer.target_certificate.artifact,
    )
    return ExactAnswer(
        answer.identity,
        answer.approximation,
        answer.branch_signature,
        configuration,
        target,
    )
end

function widen_literal_checkpoint(source::AbstractString)
    document = parse_protocol_json(source)
    observed = only(
        event for event in document["state"]["events"] if event["kind"] == "observed"
    )
    observations = (
        document["state"]["workspace"]["history"][1]["observation"],
        observed["payload"],
    )
    for observation in observations
        for (bound, delta) in (("lower", -big"1e6"), ("upper", big"1e6"))
            encoded = observation["target"][bound]
            @assert encoded["kind"] == "bigfloat"
            bits = Int(encoded["precision_bits"])
            encoded["decimal"] = setprecision(BigFloat, bits) do
                string(parse(BigFloat, String(encoded["decimal"])) + delta)
            end
        end
    end
    payload = Dict{String,Any}(
        "state" => document["state"],
        "target_image_status" => document["target_image_status"],
    )
    document["content_hash"] = string(canonical_json_hash(payload))
    return decode_checkpoint_document(document)
end

function forge_literal_observed_event(source::AbstractString)
    document = parse_protocol_json(source)
    observed = only(
        event for event in document["state"]["events"] if event["kind"] == "observed"
    )
    approximation = observed["payload"]["verified_payload"]["value"]["approximation"]
    @assert approximation["kind"] == "bigfloat"
    bits = Int(approximation["precision_bits"])
    approximation["decimal"] = setprecision(BigFloat, bits) do
        string(parse(BigFloat, String(approximation["decimal"])) + big"0.25")
    end
    payload = Dict{String,Any}(
        "state" => document["state"],
        "target_image_status" => document["target_image_status"],
    )
    document["content_hash"] = string(canonical_json_hash(payload))
    return decode_checkpoint_document(document)
end

@testset "literal exact certificates replay independently" begin
    registry = exact_registry()
    problem = literal_problem()
    execution = solve_execution(problem, registry; options=SolveOptions(wall_seconds=60))
    answer = only(execution.result.exact_answers)
    @test occursin("exact_verification=accepted", execution.evidence_json)

    verification = verify_exact_answer(problem, registry, answer)
    @test verification.accepted
    @test verification.failure == EXACT_VERIFICATION_NONE
    @test isempty(verification.detail)

    decoded = only(decode_solve_result_json(
        encode_solve_result_json(execution.result),
    ).exact_answers)
    @test verify_exact_answer(problem, registry, decoded).accepted
    checkpoint = decode_checkpoint_json(
        encode_checkpoint_json(SolveCheckpointArtifact(execution)),
    )
    resumed = solve_execution(
        problem,
        registry;
        options=SolveOptions(wall_seconds=60),
        max_actions=0,
        checkpoint,
    )
    @test verify_exact_answer(problem, registry, only(resumed.result.exact_answers)).accepted
    @test_throws SolveConfigurationError solve_execution(
        problem,
        registry;
        options=SolveOptions(wall_seconds=60),
        max_actions=0,
        checkpoint=widen_literal_checkpoint(encode_checkpoint_json(checkpoint)),
    )
    @test_throws GeoTargetCore.SearchProtocolError solve_execution(
        problem,
        registry;
        options=SolveOptions(wall_seconds=60),
        max_actions=0,
        checkpoint=forge_literal_observed_event(encode_checkpoint_json(checkpoint)),
    )

    configuration_document = parse_protocol_json(
        answer.configuration_certificate.artifact.payload,
    )
    configuration_document["constraint_count"] = 1
    invalid_configuration = replace_configuration_artifact(
        answer,
        CertificateArtifact(
            "literal_configuration_v1",
            canonical_json(configuration_document);
            media_type="application/json",
        ),
    )
    invalid_configuration_result = verify_exact_answer(problem, registry, invalid_configuration)
    @test !invalid_configuration_result.accepted
    @test invalid_configuration_result.failure == EXACT_VERIFICATION_CONFIGURATION_MISMATCH

    unsupported = replace_configuration_artifact(
        answer,
        CertificateArtifact(
            "unsupported_literal_configuration",
            answer.configuration_certificate.artifact.payload;
            media_type="application/json",
        ),
    )
    unsupported_result = verify_exact_answer(problem, registry, unsupported)
    @test !unsupported_result.accepted
    @test unsupported_result.failure == EXACT_VERIFICATION_UNSUPPORTED_SCHEME

    malformed = replace_configuration_artifact(
        answer,
        CertificateArtifact(
            "literal_configuration_v1",
            "{not-json";
            media_type="application/json",
        ),
    )
    malformed_result = verify_exact_answer(problem, registry, malformed)
    @test !malformed_result.accepted
    @test malformed_result.failure == EXACT_VERIFICATION_ARTIFACT_INVALID

    foreign = replace_configuration_artifact(
        answer,
        answer.configuration_certificate.artifact;
        problem=content_hash("foreign literal proof fixture"),
    )
    foreign_result = verify_exact_answer(problem, registry, foreign)
    @test !foreign_result.accepted
    @test foreign_result.failure == EXACT_VERIFICATION_PROBLEM_MISMATCH

    target_document = parse_protocol_json(answer.target_certificate.artifact.payload)
    target_document["target"]["numerator"] = "9"
    invalid_target_certificate = TargetIdentityCertificate(
        answer.target_certificate.problem,
        answer.identity,
        CertificateArtifact(
            "literal_linear_target_v1",
            canonical_json(target_document);
            media_type="application/json",
        ),
    )
    invalid_target = ExactAnswer(
        answer.identity,
        answer.approximation,
        answer.branch_signature,
        answer.configuration_certificate,
        invalid_target_certificate,
    )
    invalid_target_result = verify_exact_answer(problem, registry, invalid_target)
    @test !invalid_target_result.accepted
    @test invalid_target_result.failure == EXACT_VERIFICATION_TARGET_MISMATCH

    shifted_approximation = ExactAnswer(
        answer.identity,
        BigFloat(answer.approximation) + big"0.25",
        answer.branch_signature,
        answer.configuration_certificate,
        answer.target_certificate,
    )
    @test answer.identity.isolating_interval.lower <
          ExactRational(15, 4) < answer.identity.isolating_interval.upper
    shifted_result = verify_exact_answer(problem, registry, shifted_approximation)
    @test !shifted_result.accepted
    @test shifted_result.failure == EXACT_VERIFICATION_TARGET_MISMATCH
    @test occursin("approximation", shifted_result.detail)
end

end
