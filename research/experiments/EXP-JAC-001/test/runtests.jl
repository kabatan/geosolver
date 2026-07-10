using Test

include(joinpath(@__DIR__, "..", "src", "ExperimentJac001.jl"))
include(joinpath(@__DIR__, "..", "src", "RunJac001.jl"))

using .ExperimentJac001
using .RunJac001

@testset "typed graph materialization is replayable and compiler-derived" begin
    instance = ExperimentJac001._diagonal_instance(
        "test",
        1,
        111_001,
        211_001,
    )
    registry = experiment_registry()
    record = ExperimentJac001._instance_document(instance, registry)
    document = Dict{String,Any}(
        "schema_version" => "exp-jac-001-input/v1",
        "experiment_id" => EXPERIMENT_ID,
        "card_sha256" => ExperimentJac001._file_sha256(
            ExperimentJac001._preregistration_path(),
        ),
        "plugin_lock_sha256" => plugin_lock_sha256(),
        "instance_count" => 1,
        "instances" => [record],
    )
    @test validate_materialized_inputs(document)
    runtime = only(RunJac001._runtime_instances(document, registry))
    @test runtime.entries == ((1, 1), (2, 2))
    @test length(runtime.starts) == START_COUNT
    @test all(trace -> trace["callbacks"] == 4, record["dense_traces"])

    preflight = colored_preflight([runtime], :natural)
    @test preflight["passed"]
    @test preflight["dense_colored_mismatch_count"] == 0
    @test preflight["dense_outside_pattern_count"] == 0
    @test preflight["negative_control_detections"] == 1
    @test preflight["fallback_control_failure_count"] == 0
    @test only(preflight["fallback_controls"])["fallback_groups"] == 1

    dense = RunJac001._run_attempt(
        runtime,
        runtime.starts[2],
        2,
        "J0-DENSE-CENTRAL",
        :natural,
    )
    colored = RunJac001._run_attempt(
        runtime,
        runtime.starts[2],
        2,
        "J1-GREEDY-COLOR",
        :natural,
    )
    @test dense["gold_valid"] == colored["gold_valid"]
    @test !dense["false_candidate"]
    @test !colored["false_candidate"]
    @test colored["jacobian_callbacks"] < dense["jacobian_callbacks"]
    @test colored["total_callbacks"] < dense["total_callbacks"]
end

@testset "locked generators are family-disjoint" begin
    development = (
        ExperimentJac001._diagonal_instance("development", 1, 111, 211),
        ExperimentJac001._banded_instance("development", 1, 112, 212),
        ExperimentJac001._dense_instance("development", 1, 113, 213),
    )
    locked = (
        ExperimentJac001._diagonal_instance("locked", 1, 911, 1_011; locked=true),
        ExperimentJac001._banded_instance("locked", 1, 912, 1_012; locked=true),
        ExperimentJac001._dense_instance("locked", 1, 913, 1_013; locked=true),
    )
    @test isdisjoint(
        Set(instance.family_id for instance in development),
        Set(instance.family_id for instance in locked),
    )
    @test all(instance -> occursin("locked", instance.generator_id), locked)
end
