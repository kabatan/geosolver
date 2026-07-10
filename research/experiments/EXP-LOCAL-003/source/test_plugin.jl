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
    @test_throws ArgumentError Local3CalibrationTruth._calibration_record(
        [Float64[1.0]],
        1;
        q_nonfinite_count = 1,
    )

    # Seven small values and one finite max value choose a tiny lower-clamped
    # a, so the final q division overflows even though every input z is finite.
    overflow_vectors = [Float64[Local3CalibrationTruth.LOWER_MODEL_SCALE / 2] for _ in 1:7]
    push!(overflow_vectors, Float64[floatmax(Float64)])
    overflow_record, overflow_scales =
        Local3CalibrationTruth._calibration_record(overflow_vectors, 1)
    @test overflow_record["valid_vector_count"] == 8
    @test overflow_record["clamp_reasons"] == ["below_0x1.0p-40"]
    @test overflow_scales == [Local3CalibrationTruth.LOWER_MODEL_SCALE]
    @test overflow_record["q_nonfinite_count"] == 1
    @test Local3CalibrationTruth._has_nonfinite_q(
        Float64[floatmax(Float64)],
        overflow_scales,
    )
    @test !Local3CalibrationTruth._has_nonfinite_q(
        Float64[Local3CalibrationTruth.LOWER_MODEL_SCALE],
        overflow_scales,
    )
end

function _synthetic_stage_assessor_cases(contract)
    cases = Dict{String,Any}[]
    for family_ordinal in 0:7
        for latent_group in contract.latent_groups
            identity = string(family_ordinal * 6 + latent_group + 1; base = 16, pad = 64)
            for representation in contract.representations
                push!(
                    cases,
                    Dict{String,Any}(
                        "family_id" => "synthetic-family-$family_ordinal",
                        "family_ordinal" => family_ordinal,
                        "latent_group" => latent_group,
                        "representation" => representation,
                        "expected_invariant" =>
                            representation != Local3CalibrationTruth.SAFETY_REPRESENTATION,
                        "gold" => Dict{String,Any}("identity_key" => identity),
                    ),
                )
            end
        end
    end
    return cases
end

@testset "development and locked capture stage contracts are closed without materializing locked inputs" begin
    development = Local3CalibrationTruth._stage_contract(
        "exp-local-003-candidate-inputs/v1",
        "exp-local-003-generator-assessor-projection/v1",
    )
    @test development.stage == "development"
    @test development.case_count == 64
    @test development.latent_group_count == 16
    @test collect(development.latent_groups) == [0, 1]
    @test length(development.representations) == 4
    @test development.safety_case_count == 16

    locked = Local3CalibrationTruth._stage_contract(
        "exp-local-003-locked-candidate-inputs/v1",
        "exp-local-003-locked-generator-assessor-projection/v1",
    )
    @test locked.stage == "locked"
    @test locked.output_version == "exp-local-003-locked-calibration-truth/v1"
    @test locked.case_count == 96
    @test locked.latent_group_count == 32
    @test collect(locked.latent_groups) == [2, 3, 4, 5]
    @test locked.representations == Local3CalibrationTruth.PRIMARY_REPRESENTATIONS
    @test locked.safety_case_count == 0
    @test locked.safety_qz_audit_status == "not_applicable_locked"
    @test_throws ErrorException Local3CalibrationTruth._stage_contract(
        "exp-local-003-candidate-inputs/v1",
        "exp-local-003-locked-generator-assessor-projection/v1",
    )

    locked_cases = _synthetic_stage_assessor_cases(locked)
    @test length(locked_cases) == 96
    grouped = Local3CalibrationTruth._validate_stage_assessor_contract(locked_cases, locked)
    @test length(grouped) == 32
    @test all(length(truths) == 3 for truths in values(grouped))
    @test all(
        Set(truth["representation"] for truth in truths) ==
            Set(Local3CalibrationTruth.PRIMARY_REPRESENTATIONS) for truths in values(grouped)
    )

    wrong_group = deepcopy(locked_cases)
    wrong_group[1]["latent_group"] = 1
    @test_throws ErrorException Local3CalibrationTruth._validate_stage_assessor_contract(
        wrong_group,
        locked,
    )
    forbidden_safety = deepcopy(locked_cases)
    forbidden_safety[1]["representation"] = Local3CalibrationTruth.SAFETY_REPRESENTATION
    forbidden_safety[1]["expected_invariant"] = false
    @test_throws ErrorException Local3CalibrationTruth._validate_stage_assessor_contract(
        forbidden_safety,
        locked,
    )
    false_primary = deepcopy(locked_cases)
    false_primary[1]["expected_invariant"] = false
    @test_throws ErrorException Local3CalibrationTruth._validate_stage_assessor_contract(
        false_primary,
        locked,
    )
end

@testset "all 64 calibration blocks capture independent C0 truth and metamorphic audits" begin
    bundle = parse_protocol_json(_generator_output("--emit-development-bundle-for-tests"))
    truth = Local3CalibrationTruth.capture_calibration_truth(
        bundle["candidate"],
        bundle["assessor"],
    )
    @test truth["schema_version"] == "exp-local-003-calibration-truth/v1"
    @test truth["stage"] == "development"
    @test length(truth["cases"]) == 64
    @test truth["audit"]["latent_groups_checked"] == 16
    @test truth["audit"]["safety_cases_checked"] == 16
    @test truth["audit"]["safety_qz_audit_status"] == "checked"
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

    # Exercise only the locked output-schema branch. This reuses audited development
    # records as synthetic schema fixtures and does not call build_locked_documents.
    synthetic_locked_shape = deepcopy(truth)
    synthetic_locked_shape["schema_version"] =
        "exp-local-003-locked-calibration-truth/v1"
    synthetic_locked_shape["stage"] = "locked"
    synthetic_locked_shape["cases"] = [
        truth["cases"][mod1(index, length(truth["cases"]))] for index in 1:96
    ]
    synthetic_locked_shape["audit"]["latent_groups_checked"] = 32
    synthetic_locked_shape["audit"]["gold_configurations_checked"] = sum(
        record["gold_audit"]["configuration_count"] for
        record in synthetic_locked_shape["cases"]
    )
    synthetic_locked_shape["audit"]["primary_inverse_comparisons_checked"] = 64
    synthetic_locked_shape["audit"]["safety_cases_checked"] = 0
    synthetic_locked_shape["audit"]["safety_qz_audit_status"] =
        "not_applicable_locked"
    @test isnothing(_validate_calibration_truth_schema(synthetic_locked_shape))
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
