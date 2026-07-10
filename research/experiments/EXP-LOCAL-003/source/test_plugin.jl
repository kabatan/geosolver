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

function _validate_calibration_truth_schema(truth)
    schema = joinpath(SOURCE_DIRECTORY, "calibration-truth.schema.json")
    script = """
import json
import sys
from jsonschema import Draft202012Validator

schema = json.load(open(sys.argv[1], encoding="utf-8"))
Draft202012Validator.check_schema(schema)
Draft202012Validator(schema).validate(json.load(sys.stdin))
"""
    command = `uv run --project $PYTHON_PROJECT --frozen python -c $script $schema`
    open(command, "w") do input
        write(input, canonical_json(truth))
    end
    return nothing
end

function _single_component_calibration(rank::Float64; count::Int = 8)
    vectors = [Float64[rank] for _ in 1:count]
    return Local3CalibrationTruth._calibration_record(vectors, 1)
end

@testset "calibration nearest-rank clamps, joint fallbacks, and nonfinite q classification" begin
    lower = Local3CalibrationTruth.LOWER_MODEL_SCALE
    upper = Local3CalibrationTruth.UPPER_MODEL_SCALE

    below, below_scales = _single_component_calibration(prevfloat(lower))
    @test below["nearest_rank_index"] == 6
    @test below["clamp_reasons"] == ["below_0x1.0p-40"]
    @test reinterpret(UInt64, only(below_scales)) == reinterpret(UInt64, lower)

    equal_lower, equal_lower_scales = _single_component_calibration(lower)
    @test equal_lower["clamp_reasons"] == ["none"]
    @test reinterpret(UInt64, only(equal_lower_scales)) == reinterpret(UInt64, lower)

    equal_upper, equal_upper_scales = _single_component_calibration(upper)
    @test equal_upper["clamp_reasons"] == ["none"]
    @test reinterpret(UInt64, only(equal_upper_scales)) == reinterpret(UInt64, upper)

    above, above_scales = _single_component_calibration(nextfloat(upper))
    @test above["clamp_reasons"] == ["above_0x1.0p+40"]
    @test reinterpret(UInt64, only(above_scales)) == reinterpret(UInt64, upper)

    insufficient, insufficient_scales = _single_component_calibration(2.0; count = 7)
    @test insufficient["valid_vector_count"] == 7
    @test insufficient["joint_fallback_reason"] == "insufficient_valid_vectors"
    @test insufficient["clamp_reasons"] == ["joint_fallback"]
    @test insufficient_scales == [1.0]

    zero_rank, zero_rank_scales = _single_component_calibration(0.0)
    @test zero_rank["joint_fallback_reason"] == "nonpositive_or_nonfinite_nearest_rank"
    @test zero_rank["clamp_reasons"] == ["joint_fallback"]
    @test zero_rank_scales == [1.0]

    nonfinite_observation = (status = EVAL_OK, relations = ((scaled = Inf,),))
    vector, classification = Local3CalibrationTruth._classify_calibration_observation(
        nonfinite_observation,
        1,
    )
    @test vector === nothing
    @test classification == "nonfinite_q"
    nonfinite_record, nonfinite_scales = Local3CalibrationTruth._calibration_record(
        Union{Nothing,Vector{Float64}}[vector],
        1;
        q_nonfinite_count = 1,
    )
    @test nonfinite_record["q_nonfinite_count"] == 1
    @test nonfinite_record["valid_vector_count"] == 0
    @test nonfinite_record["joint_fallback_reason"] == "insufficient_valid_vectors"
    @test nonfinite_scales == [1.0]
end

@testset "all 64 calibration blocks capture independent C0 truth and metamorphic audits" begin
    bundle = parse_protocol_json(_generator_output("--emit-development-bundle-for-tests"))
    truth = Local3CalibrationTruth.capture_calibration_truth(
        bundle["candidate"],
        bundle["assessor"],
    )
    @test truth["schema_version"] == "exp-local-003-calibration-truth/v1"
    @test length(truth["cases"]) == 64
    @test truth["audit"]["latent_groups_checked"] == 16
    @test truth["audit"]["gold_configurations_checked"] == sum(
        record["gold_audit"]["configuration_count"] for record in truth["cases"]
    )
    @test truth["audit"]["primary_inverse_comparisons_checked"] > 0
    @test all(
        value == 0 for (name, value) in truth["audit"] if endswith(name, "_count")
    )
    @test all(length(record["observations"]) == 64 for record in truth["cases"])
    @test all(record["logical_evaluation_cost"] > 0 for record in truth["cases"])
    @test all(
        length(record["calibration"]["r_bits"]) == record["residual_count"] &&
        length(record["calibration"]["a_bits"]) == record["residual_count"] &&
        length(record["calibration"]["clamp_reasons"]) == record["residual_count"] for
        record in truth["cases"]
    )
    @test all(
        record["calibration"]["q_nonfinite_count"] == count(
            observation -> observation["classification"] == "nonfinite_q",
            record["observations"],
        ) for record in truth["cases"]
    )
    @test all(
        length(record["compiled_numeric_metadata"]["variables"]) ==
            record["variable_count"] &&
        length(record["compiled_numeric_metadata"]["relation_semantic_scale_bits"]) ==
            record["residual_count"] for record in truth["cases"]
    )
    @test all(
        audit["calibration_rows_checked"] == 64 &&
        audit["start_rows_checked"] == 32 &&
        all(value == 0 for (name, value) in audit if endswith(name, "_count")) for
        audit in (record["candidate_input_audit"] for record in truth["cases"])
    )
    @test all(
        gold["configuration_index_coverage_exact"] &&
        gold["target_intervals_distinct_nonoverlapping"] &&
        gold["canonical_eval_ok_count"] == gold["configuration_count"] &&
        gold["validation_accepted_count"] == gold["configuration_count"] &&
        gold["residual_within_tolerance_count"] == gold["configuration_count"] &&
        gold["target_within_interval_tolerance_count"] == gold["configuration_count"] &&
        gold["canonical_replay_agreement_count"] == gold["configuration_count"] &&
        length(gold["configurations"]) == gold["configuration_count"] for
        gold in (record["gold_audit"] for record in truth["cases"])
    )
    identity_counts = Dict{String,Int}()
    for record in truth["cases"]
        identity = record["gold_audit"]["gold_identity_key"]
        identity_counts[identity] = get(identity_counts, identity, 0) + 1
    end
    @test length(identity_counts) == 16
    @test all(==(4), values(identity_counts))
    @test isnothing(_validate_calibration_truth_schema(truth))
    @test canonical_json(parse_protocol_json(canonical_json(truth))) == canonical_json(truth)

    malformed_assessor = deepcopy(bundle["assessor"])
    first_target = malformed_assessor["cases"][1]["gold"]["targets"][1]
    push!(first_target["configuration_indexes"], first(first_target["configuration_indexes"]))
    @test_throws ErrorException Local3CalibrationTruth.capture_calibration_truth(
        bundle["candidate"],
        malformed_assessor,
    )
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
