using JSON3
using Test

include(joinpath(@__DIR__, "..", "src", "ExperimentLocal002.jl"))
using .ExperimentLocal002

@testset "EXP-LOCAL-002 frozen pilot material" begin
    @test string(Base.pkgversion(ExperimentLocal002.NonlinearSolve)) == "4.20.2"
    problems = pilot_problems()
    @test length(problems) == 8
    @test all(problem -> size(problem.saved_starts, 2) == PILOT_START_COUNT, problems)
    @test all(ExperimentLocal002.verify_replay_material, problems)
    @test "STRICT-GUARD-BOUNDARY" in (problem.family_id for problem in problems)
    @test "OPAQUE-TRANSCENDENTAL-C0" in (problem.family_id for problem in problems)
    @test only(filter(problem -> problem.family_id == "OPAQUE-TRANSCENDENTAL-C0", problems)).jacobian! === nothing

    for problem in problems
        _, _, lower, upper = bounds_normalization(problem)
        @test lower ≈ fill(-1.0, problem.dimension)
        @test upper ≈ fill(1.0, problem.dimension)
        for configuration in eachcol(problem.gold_configurations)
            validation = validate_endpoint(problem, configuration)
            @test validation["canonical_valid"]
            @test validation["gold_matched"]
            @test validation["accepted"]
        end
    end
end

@testset "independent truth gate rejects the excluded S4 root" begin
    problem = only(filter(
        problem -> problem.family_id == "STRICT-GUARD-BOUNDARY",
        pilot_problems(),
    ))
    coupling = problem.gold_configurations[2, 1] / problem.gold_configurations[1, 1]
    excluded_boundary_root = [problem.metadata[:guard_boundary], coupling]
    validation = validate_endpoint(problem, excluded_boundary_root)
    @test validation["residual_qualified"]
    @test !validation["strict_guard_valid"]
    @test !validation["gold_matched"]
    @test !validation["accepted"]
    @test validation["false_candidate"]
end

@testset "C1 and opaque C0 adapters use bounded finite differences" begin
    problems = pilot_problems()
    c1 = first(problems)
    c0 = only(filter(problem -> problem.family_id == "OPAQUE-TRANSCENDENTAL-C0", problems))
    for problem in (c1, c0)
        attempt = run_attempt(problem, problem.saved_starts[:, 1], "NLS-TR")
        @test attempt.exception === nothing
        @test attempt.callback_residual_calls <= MAX_EVALUATIONS
        @test attempt.iterations <= MAX_ITERATIONS
        @test all((problem.lower_bounds .<= attempt.endpoint) .&
                  (attempt.endpoint .<= problem.upper_bounds))
    end

    control = run_attempt(c1, c1.saved_starts[:, 1], "LXR-LMQR")
    @test control.exception === nothing
    @test control.callback_residual_calls == control.solver_nf
    @test validate_endpoint(c1, control.endpoint)["accepted"]
end

@testset "CSV, JSON and Markdown artifact writers" begin
    problem = first(pilot_problems())
    execution = run_attempt(problem, problem.saved_starts[:, 1], "NLS-TR")
    row = ExperimentLocal002._attempt_row(problem, "NLS-TR", 1, execution, "cold-first-use")
    row["targets_seen"] = row["accepted"] ? 1 : 0
    row["target_count"] = length(problem.gold_targets)
    row["all_targets_prefix"] = row["targets_seen"] == row["target_count"]
    @test validate_result_rows([row], [problem]; variants=("NLS-TR",), start_count=1)
    environment = environment_record([problem]; load_compile_seconds=0.0)
    summary = summarize([row], environment)
    mktempdir() do directory
        write_results(directory, [row], environment, summary)
        for filename in ("attempts.csv", "attempts.json", "environment.json", "summary.json", "pilot-report.md")
            @test isfile(joinpath(directory, filename))
        end
        parsed = JSON3.read(read(joinpath(directory, "summary.json"), String))
        @test parsed.experiment_id == EXPERIMENT_ID
        @test parsed.status == "non-gating-pilot"
    end
end
