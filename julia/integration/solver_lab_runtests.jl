using GeoTargetBenchmarks

include(joinpath(REPOSITORY_ROOT, "benchmarks", "solver_lab", "CoreBaseline.jl"))
using .GeoTargetSolverLab

@testset "solver lab Core adapter and independent scoring" begin
    problems = representative_problems(start_count=8)
    @test length(problems) == 9
    @test all(verify_replay_material, problems)
    @test length(unique(problem.family_id for problem in problems)) == 8
    warped_problems = filter(problem -> problem.family_id == "MULTIROOT-WARPED", problems)
    @test length(warped_problems) == 2
    @test warped_problems[1].saved_starts == warped_problems[2].saved_starts
    @test warped_problems[1].gold_configurations == warped_problems[2].gold_configurations
    @test sort([length(problem.gold_targets) for problem in warped_problems]) == [2, 4]

    selected = filter(
        problem -> problem.family_id in ("TANGENT-CIRCLE-LINE", "MULTIROOT-WARPED"),
        problems,
    )
    run = run_solver_experiment(
        selected,
        [core_lmqr_variant()];
        prefixes=(2, 4, 8),
    )
    @test length(run.attempts) == 24
    @test all(attempt -> attempt.exception === nothing, run.attempts)
    @test all(attempt -> attempt.evaluations <= 600, run.attempts)

    tangent = only(filter(
        summary -> summary.family_id == "TANGENT-CIRCLE-LINE" && summary.prefix == 8,
        run.prefixes,
    ))
    @test tangent.targets_found == tangent.target_count == 2
    @test tangent.all_targets

    warped = only(filter(
        summary -> summary.family_id == "MULTIROOT-WARPED" &&
                   summary.target_count == 4 && summary.prefix == 8,
        run.prefixes,
    ))
    @test warped.target_count == 4
    @test warped.false_candidates >= 1
    @test warped.targets_found == 0
    @test warped.evaluations <= 8 * 600

    document = solver_experiment_document(run)
    encoded = canonical_json(document)
    parsed = JSON3.read(encoded)
    @test parsed.schema == SOLVER_EXPERIMENT_SCHEMA_VERSION
    @test parsed.tolerances.configuration == 1.0e-6
    @test parsed.variant_manifest[1].configuration.coordinate_scaling == "bounds"
end

@testset "solver lab command entrypoint parses in a fresh process" begin
    runner = joinpath(REPOSITORY_ROOT, "benchmarks", "solver_lab", "run.jl")
    project = joinpath(REPOSITORY_ROOT, "julia")
    command = `$(Base.julia_cmd()) --startup-file=no --history-file=no --project=$project $runner --help`
    help = read(command, String)
    @test occursin("Usage:", help)
    @test occursin("--prefixes=2,4,8", help)
end
