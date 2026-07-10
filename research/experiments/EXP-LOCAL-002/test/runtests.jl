using JSON3
using Test

include(joinpath(@__DIR__, "..", "src", "ExperimentLocal002.jl"))
include(joinpath(@__DIR__, "..", "src", "DevelopmentLocal002.jl"))
include(joinpath(@__DIR__, "..", "src", "RoutingLocal002.jl"))
using .ExperimentLocal002
using .DevelopmentLocal002
using .RoutingLocal002

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

@testset "EXP-LOCAL-002 preregistered diagnostic routing" begin
    @test validate_amendment()
    policy_source = read(joinpath(@__DIR__, "..", "src", "routing_policy.jl"), String)
    for forbidden in ("family_id", "instance_id", "known_answer", "target value", "start_index")
        @test !occursin(forbidden, policy_source)
    end

    problems = development_problems()
    low_dimension = first(problems)
    low = route_diagnostic(low_dimension, low_dimension.saved_starts[:, 1])
    @test low.selected_algorithm == "NLS-TR"
    @test !low.computed
    @test low.residual_calls == 0

    opaque = only(filter(
        problem -> problem.family_id == "OPAQUE-TRANSCENDENTAL-C0" &&
            problem.metadata[:loop_count] == 1,
        problems,
    ))
    c0 = route_diagnostic(opaque, opaque.saved_starts[:, 1])
    @test c0.selected_algorithm == "NLS-TR"
    @test c0.capability == "C0"
    @test !c0.computed

    rank_deficient = only(filter(
        problem -> problem.dimension == 16 &&
            problem.metadata[:generator_role] == :analytic_conditioning_control,
        problems,
    ))
    rank_route = route_diagnostic(rank_deficient, rank_deficient.saved_starts[:, 1])
    @test rank_route.selected_algorithm == "NLS-TR"
    @test rank_route.computed
    @test rank_route.numerical_rank < rank_route.dimension

    selected_count = 0
    diagnostic_calls = 0
    fallback_count = 0
    for problem in problems, start in eachcol(problem.saved_starts)
        diagnostic = route_diagnostic(problem, start)
        selected_count += diagnostic.selected_algorithm == "NLS-LM"
        diagnostic_calls += diagnostic.residual_calls
        fallback_count += diagnostic.explicit_fallback
    end
    @test selected_count == 11
    @test diagnostic_calls == 5_120
    @test fallback_count == 0
end

@testset "EXP-LOCAL-002 frozen development grid" begin
    problems = development_problems()
    @test validate_development_grid(problems)
    @test length(problems) == DEVELOPMENT_INSTANCE_COUNT == 48
    @test all(problem -> size(problem.saved_starts, 2) == DEVELOPMENT_START_COUNT, problems)
    @test Set(problem.dimension for problem in problems) >= Set((2, 4, 8, 16))
    family_counts = Dict(
        family => count(problem -> problem.family_id == family, problems) for
        family in DEVELOPMENT_FAMILIES
    )
    @test all(==(6), values(family_counts))
    for stratum in (Symbol("S$index") for index in 1:8)
        @test count(problem -> stratum in problem.strata, problems) >= 6
    end
    @test validate_development_input_manifest()
    manifest = development_input_manifest(problems)
    @test manifest["thresholds"]["gold_configuration_normalized"] ==
        GOLD_CONFIGURATION_TOLERANCE == 1.0e-6
    @test manifest["thresholds"]["gold_target"] == GOLD_TARGET_TOLERANCE == 1.0e-6
    @test Tuple(manifest["variants"]) == VARIANTS

    largest_overdetermined = only(filter(
        problem -> problem.family_id == "REDUNDANT-OVERDETERMINED" &&
            problem.residual_dimension == 80,
        problems,
    ))
    control = run_attempt(
        largest_overdetermined,
        largest_overdetermined.saved_starts[:, 1],
        "LXR-LMQR",
    )
    @test control.exception === nothing
    @test !control.budget_exceeded
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
