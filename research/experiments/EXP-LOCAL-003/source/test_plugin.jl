using GeoTargetBase
using GeoTargetCore
using GeoTargetGeometry
using Test

const SOURCE_DIRECTORY = @__DIR__
const REPOSITORY_ROOT = normpath(joinpath(SOURCE_DIRECTORY, "..", "..", "..", ".."))
const PYTHON_PROJECT = joinpath(REPOSITORY_ROOT, "python")
const PYTHON_SOURCE = joinpath(PYTHON_PROJECT, "src")
const GENERATOR = joinpath(SOURCE_DIRECTORY, "generator.py")

include(joinpath(SOURCE_DIRECTORY, "Local3FixturePlugin.jl"))
using .Local3FixturePlugin
include(joinpath(SOURCE_DIRECTORY, "capture_calibration_truth.jl"))
using .Local3CalibrationTruth

function _generator_output(option::String)
    command = addenv(
        `uv run --project $PYTHON_PROJECT --frozen python $GENERATOR $option`,
        "PYTHONPATH" => PYTHON_SOURCE,
    )
    return read(command, String)
end

@testset "all 64 calibration blocks capture independent C0 truth and metamorphic audits" begin
    bundle = parse_protocol_json(_generator_output("--emit-development-bundle-for-tests"))
    truth = Local3CalibrationTruth.capture_calibration_truth(
        bundle["candidate"],
        bundle["assessor"],
    )
    @test truth["schema_version"] == "exp-local-003-calibration-truth/v1"
    @test length(truth["cases"]) == 64
    @test truth["audit"] == Dict{String,Any}(
        "latent_groups_checked" => 16,
        "primary_semantic_z_mismatch_count" => 0,
        "primary_scale_permutation_mismatch_count" => 0,
        "safety_qz_mismatch_count" => 0,
    )
    @test all(length(record["observations"]) == 64 for record in truth["cases"])
    @test all(record["logical_evaluation_cost"] > 0 for record in truth["cases"])
    @test all(
        length(record["calibration"]["r_bits"]) == record["residual_count"] &&
        length(record["calibration"]["a_bits"]) == record["residual_count"] &&
        length(record["calibration"]["clamp_reasons"]) == record["residual_count"] for
        record in truth["cases"]
    )
    @test canonical_json(parse_protocol_json(canonical_json(truth))) == canonical_json(truth)
end

function _fixture_registry()
    geometry = GeoTargetGeometry.geometry_plugin()
    fixture = Local3FixturePlugin.local3_fixture_plugin()
    builder = RegistryBuilder(allowlist = (geometry.id, fixture.id))
    register!(builder, geometry)
    register!(builder, fixture)
    return freeze(builder), builder
end

@testset "EXP-LOCAL-003 unknown C0 plugin uses the real SDK/compiler/canonical path" begin
    registry, frozen_builder = _fixture_registry()
    @test length(registered_plugins(registry)) == 2
    @test_throws RegistryError register!(
        frozen_builder,
        Local3FixturePlugin.local3_fixture_plugin(),
    )

    bundle_source = _generator_output("--emit-smoke-bundle")
    bundle = parse_protocol_json(bundle_source)
    candidate_cases = bundle["candidate_cases"]
    assessor_cases = bundle["assessor_cases"]
    @test length(candidate_cases) == length(assessor_cases) == 3

    for (candidate, assessor) in zip(candidate_cases, assessor_cases)
        @test candidate["opaque_case_key"] == assessor["opaque_case_key"]
        document = candidate["problem_document"]
        canonical = canonical_json(document)
        @test canonical_json(parse_protocol_json(canonical)) == canonical

        problem = decode_problem_document(document, registry)
        compiled = compile_problem(problem, registry)
        @test supports(capabilities(compiled), C0)
        @test !supports(capabilities(compiled), C1)
        @test !supports(capabilities(compiled), C2)
        @test compiled.logical_evaluation_cost > 0

        gold = assessor["gold"]["configurations"][1]
        coordinates = Float64[value for value in gold]
        fast = evaluate(compiled, coordinates; capability = C0)
        replay = evaluate_canonical(compiled, coordinates; capability = C0)
        @test fast.status == EVAL_OK
        @test replay.status == EVAL_OK
        @test length(fast.relations) == length(replay.relations)
        @test fast.target == replay.target
        @test all(isfinite(relation.scaled) for relation in fast.relations)

        validation = validate_candidate(compiled, coordinates)
        @test validation.accepted
        @test validation.method == "canonical_c0_second_pass"
        @test validation.precision_bits == 53
        @test validation.canonical_observation.status == EVAL_OK
    end
end

@testset "Fraction exact FMA source agrees bit-for-bit with Julia Base.fma" begin
    document = parse_protocol_json(_generator_output("--emit-fma-vectors"))
    @test document["schema_version"] == "exp-local-003-ephemeral-fma-vectors/v1"
    @test length(document["vectors"]) >= 6
    for vector in document["vectors"]
        expected = parse(UInt64, vector["expected_bits"]; base = 16)
        actual = reinterpret(
            UInt64,
            Base.fma(
                Float64(vector["first"]),
                Float64(vector["second"]),
                Float64(vector["third"]),
            ),
        )
        @test actual == expected
    end
end

@testset "opaque-program codec rejects malformed stack programs" begin
    @test_throws ArgumentError Local3FixturePlugin._decode_program(Dict(
        "version" => 1,
        "instructions" => Any[Dict("op" => "add")],
    ))
    @test_throws ArgumentError Local3FixturePlugin._decode_program(Dict(
        "version" => 1,
        "instructions" => Any[Dict("op" => "input", "index" => 16)],
    ))
    @test_throws ArgumentError Local3FixturePlugin._decode_program(Dict(
        "version" => 1,
        "instructions" => Any[Dict("op" => "constant", "value" => Inf)],
    ))
end
