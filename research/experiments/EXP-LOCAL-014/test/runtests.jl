using JSON3
using Test

include(joinpath(@__DIR__, "..", "run_wave.jl"))

@testset "T2 runner is predecessor-bound and outcome-authorized" begin
    preflight = wave_preflight_document("t2")
    @test preflight["active_stage"] == "t2"
    @test preflight["authorized"]
    @test preflight["case_count"] == 48
    @test preflight["maximum_starts"] == 32
    @test preflight["case_work_stop"] == 4_800
    @test preflight["maximum_case_processes"] == 16
    @test preflight["runtime_versions"]["julia"] == "1.12.6"
    @test preflight["source_case_indices"] == collect(1:48)
    @test preflight["variant_names"] == [
        "prod-tol-120x600",
        "E1-FD2-CPQR3",
        "E4-EXP-GUARD-SLACK-CPQR",
        "E4-EXP-GUARD-SLACK-CPQR-SHADOW",
    ]
    @test _wave_authorized(_wave_registration(), "t2")
    @test_throws ErrorException _execution_host_contract(1, 1)
    slot = _acquire_cpu_slot(15)
    try
        @test_throws ErrorException _acquire_cpu_slot(15)
    finally
        close(slot)
    end
end

@testset "T2 is R1-bound and the R1 manifest remains frozen" begin
    registration = _wave_registration()
    @test _validate_predecessor(registration, "t2")
    spec = _wave_stage("r1")
    expected = registration["stages"]["r1"]
    @test length(spec.problems) == length(expected["instances"]) == 9
    @test sum(length(problem.gold_targets) for problem in spec.problems) == 16
    for (index, problem) in enumerate(spec.problems)
        observed = _wave_problem_manifest(problem, index, index)
        wanted = expected["instances"][index]
        @test observed["instance_id"] == wanted["instance_id"]
        @test observed["replay_checksum"] == wanted["replay_checksum"]
        @test observed["saved_starts_checksum"] == wanted["saved_starts_checksum"]
        @test observed["saved_starts_shape"] == wanted["saved_starts_shape"]
        @test observed["targets"] == wanted["target_count"]
    end
end

@testset "frozen G0 stratum and truth separation" begin
    spec = _wave_stage("g0")
    @test sum(length(problem.gold_targets) for problem in spec.problems) == 17
    @test count(problem -> problem.family_id == "NEAR-RANK-DEFICIENT", spec.problems) == 6
    @test count(problem -> problem.family_id == "STRICT-GUARD-BOUNDARY", spec.problems) == 6
    @test all(size(problem.saved_starts, 2) == 32 for problem in spec.problems)
    source = read(joinpath(@__DIR__, "..", "run_wave.jl"), String)
    @test occursin("_truth_blind_case", read(
        joinpath(@__DIR__, "..", "..", "EXP-LOCAL-010", "run_t0.jl"), String,
    ))
    @test !occursin("gold_targets", lowercase(read(
        joinpath(@__DIR__, "..", "..", "EXP-LOCAL-012", "src", "ExperimentLocal012.jl"), String,
    )))
    @test !occursin("gold_targets", lowercase(read(
        joinpath(@__DIR__, "..", "..", "EXP-LOCAL-013", "src", "ExperimentLocal013.jl"), String,
    )))
    @test occursin("case/family/Gold", read(
        joinpath(@__DIR__, "..", "preregistration.json"), String,
    ))
    @test occursin("_wave_variants", source)
end
