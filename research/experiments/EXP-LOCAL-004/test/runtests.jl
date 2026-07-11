using GeoTargetBenchmarks
using GeoTargetCore
using Test

include(joinpath(@__DIR__, "..", "src", "ExperimentLocal004.jl"))
using .ExperimentLocal004

const T2_TEST_REPOSITORY_ROOT = normpath(joinpath(@__DIR__, "..", "..", "..", ".."))
const T2_TEST_EXP_LOCAL_002 = joinpath(
    T2_TEST_REPOSITORY_ROOT,
    "research",
    "experiments",
    "EXP-LOCAL-002",
)
include(joinpath(T2_TEST_EXP_LOCAL_002, "src", "ExperimentLocal002.jl"))
include(joinpath(T2_TEST_EXP_LOCAL_002, "src", "DevelopmentLocal002.jl"))
include(joinpath(@__DIR__, "..", "src", "T2Corpus.jl"))
using .T2Corpus

function fixture_case(
    dimension,
    residual_dimension,
    lower,
    upper,
    residual_scales,
    residual;
    target=input -> input[1],
    semantics=input -> true,
    calls=Ref(0),
)
    evaluator = function (input)
        calls[] += 1
        values = Tuple(residual(input))
        raw_target = target(input)
        finite = all(isfinite, values) && raw_target isa Real && isfinite(raw_target)
        return SolverCaseEvaluation(
            values,
            finite ? Float64(raw_target) : nothing,
            finite && semantics(input),
            finite,
        )
    end
    return SolverExperimentCase(
        dimension,
        residual_dimension,
        Tuple(Float64.(lower)),
        Tuple(Float64.(upper)),
        Tuple(ones(dimension)),
        Tuple(Float64.(residual_scales)),
        evaluator,
    )
end

@testset "EXP-LOCAL-004 T2 development corpus contract" begin
    problems = t2_problems()
    @test validate_t2_grid(problems)
    @test length(problems) == T2_INSTANCE_COUNT == 48
    @test T2_START_COUNT == 32
    @test T2_PREFIXES == (8, 16, 32)
    @test T2_RUNNER_EVALUATION_LIMIT == 2_000
    @test all(verify_replay_material, problems)
    @test all(problem -> size(problem.saved_starts, 2) == 32, problems)
    @test length(unique(
        only(filter(artifact -> artifact.name === :saved_starts, problem.artifacts)).sha256 for
        problem in problems
    )) == 48
    family_counts = Dict(
        family => count(problem -> problem.family_id == family, problems) for
        family in T2_FAMILIES
    )
    @test all(==(6), values(family_counts))
    for stratum in (Symbol("S$index") for index in 1:8)
        @test count(problem -> stratum in problem.strata, problems) >= 6
    end

    manifest = t2_input_manifest(problems)
    @test manifest["schema_version"] == T2_SCHEMA_VERSION
    @test manifest["partition"] == "development"
    @test manifest["locked_validation"] == false
    @test manifest["instance_count"] == 48
    @test manifest["instances_per_family"] == 6
    @test manifest["starts_per_instance"] == 32
    @test Tuple(manifest["prefixes"]) == (8, 16, 32)
    @test manifest["runner_evaluation_limit"] == 2_000
    @test manifest["solver_experiment_schema"] == SOLVER_EXPERIMENT_SCHEMA_VERSION
    @test manifest["assessor_manifest"] == fixed_assessor_manifest()
    @test manifest["holdout_separation"]["contains_holdout_inputs"] == false
    @test manifest["holdout_separation"]["historical_locked_recipe_loaded"] == false
    @test manifest["holdout_separation"]["reserved_partitions"] ==
          ["U1", "U2", "U3", "U4"]
    @test manifest["seed_contract"] == Dict{String,Any}(
        "instance_formula" => "10000 + 100*family_index + instance_index",
        "instance_namespace" => 10_000,
        "start_formula" => "20000 + 100*family_index + instance_index",
        "start_namespace" => 20_000,
    )
    @test length(manifest["instances"]) == 48
    @test all(record -> record["saved_starts_shape"][2] == 32, manifest["instances"])
    @test all(record -> length(record["saved_starts_checksum"]) == 64, manifest["instances"])
    @test all(record -> length(record["replay_checksum"]) == 64, manifest["instances"])
    @test all(value -> length(value) == 64, values(manifest["source_sha256"]))
    @test haskey(
        manifest["source_sha256"],
        "julia/GeoTargetBenchmarks/src/GeoTargetBenchmarks.jl",
    )
    @test haskey(
        manifest["source_sha256"],
        "research/experiments/EXP-LOCAL-002/src/ExperimentLocal002.jl",
    )
    @test manifest["variant_contract"] == t2_variant_contract()
    @test [(entry["name"], entry["max_evaluations"]) for
           entry in manifest["variant_contract"]] == [
        ("prod-tol-120x600", 600),
        ("prod-options-250x2000", 2_000),
        ("NLS-TR", 2_000),
    ]

    short = DevelopmentLocal002.development_problems(start_count=8)
    @test all(
        short[index].saved_starts == problems[index].saved_starts[:, 1:8] for
        index in eachindex(problems)
    )

    source = read(joinpath(@__DIR__, "..", "src", "T2Corpus.jl"), String)
    @test !occursin("validate_development_input_manifest", source)
    @test !occursin("development-input-manifest.json", source)
    @test !occursin("routing-amendment", source)
end

@testset "EXP-LOCAL-004 T2 manifest preparation and exact validation" begin
    problems = t2_problems()
    mktempdir() do directory
        path = joinpath(directory, "t2-input-manifest.json")
        checksum = prepare_t2_input_manifest(path; problems)
        @test isfile(path)
        @test length(checksum) == 64
        @test manifest_file_sha256(path) == checksum
        @test validate_t2_input_manifest(path, problems) == checksum
        @test read(path, String) == canonical_json(t2_input_manifest(problems)) * "\n"
        @test_throws ErrorException prepare_t2_input_manifest(path; problems)
        write(path, read(path, String) * " ")
        @test_throws ErrorException validate_t2_input_manifest(path, problems)
    end
end

@testset "EXP-LOCAL-004 T2 runner is manifest-gated and fixed" begin
    runner = joinpath(@__DIR__, "..", "run_t2.jl")
    source = read(runner, String)
    @test occursin("problems = t2_problems()", source)
    @test occursin("validate_t2_input_manifest", source)
    @test occursin("prefixes=T2_PREFIXES", source)
    @test occursin("evaluation_limit=T2_RUNNER_EVALUATION_LIMIT", source)
    @test occursin("core_lmqr_control(:prod_tol_120x600)", source)
    @test occursin("core_lmqr_control(:prod_options_250x2000)", source)
    @test occursin("nls_tr_variant(max_iterations=250, max_evaluations=2_000)", source)
    @test occursin("input_manifest_sha256", source)
    @test !occursin("validate_development_input_manifest", source)
    @test !occursin("run_attempt(", source)

    project = T2_TEST_EXP_LOCAL_002
    command = `$(Base.julia_cmd()) --startup-file=no --history-file=no --project=$project $runner --help`
    help = read(command, String)
    @test occursin("48 development cases", help)
    @test occursin("prefixes 8/16/32", help)
    @test occursin("runner hard cap of 2000", help)
end

const CANDIDATE_BUILDERS = (nls_tr_variant, nls_lm_variant)

@testset "EXP-LOCAL-004 pinned truth-blind variants" begin
    @test string(Base.pkgversion(ExperimentLocal004.NonlinearSolve)) ==
          NONLINEAR_SOLVE_VERSION == "4.20.2"
    source = read(joinpath(@__DIR__, "..", "src", "ExperimentLocal004.jl"), String)
    for forbidden in ("family_id", "instance_id", "gold_configurations", "gold_targets")
        @test !occursin(forbidden, source)
    end
    variants = (nls_tr_variant(), nls_lm_variant())
    @test Tuple(variant.name for variant in variants) == ("NLS-TR", "NLS-LM")
    @test !ExperimentLocal004.NonlinearSolve.SciMLBase.allowsbounds(
        ExperimentLocal004._algorithm(:tr),
    )
    @test !ExperimentLocal004.NonlinearSolve.SciMLBase.allowsbounds(
        ExperimentLocal004._algorithm(:lm),
    )
    for variant in variants
        config = variant.configuration
        @test config.package_version == "4.20.2"
        @test config.derivative_backend == DERIVATIVE_BACKEND
        @test config.finite_difference_step == cbrt(eps(Float64))
        @test config.bounds_transform == BOUNDS_TRANSFORM
        @test config.library_bounds_transform == LIBRARY_BOUNDS_TRANSFORM
        @test !config.native_bounds
        @test config.normalized_lower == -1.0
        @test config.normalized_upper == 1.0
        @test config.residual_scaling == "declared"
        @test config.abstol == 1.0e-12
        @test config.reltol == 0.0
        @test config.max_iterations == 250
        @test config.max_evaluations == 2_000
        @test config.endpoint_policy == "solution.u-only"
        @test config.reported_acceptance ==
              "finite-bounds-semantics-scaled-residual-linf"
        @test config.acceptance_residual_tolerance == 1.0e-12
        @test config.acceptance_requires_semantics_valid
    end
    @test variants[1].configuration.geodesic_acceleration == "not-applicable"
    @test variants[2].configuration.geodesic_acceleration == "enabled"
    @test variants[2].configuration.geodesic_finite_difference_step == 0.1
    @test variants[2].configuration.geodesic_alpha == 0.75
    @test_throws ArgumentError nonlinear_solve_variant(:unknown)
    @test_throws ArgumentError nls_tr_variant(max_iterations=0)
    @test_throws ArgumentError nls_lm_variant(max_evaluations=0)
end

@testset "regular and overdetermined systems" begin
    regular = fixture_case(
        1,
        1,
        [-2.0],
        [4.0],
        [10.0],
        input -> (10.0 * (input[1] - 0.25),),
    )
    overdetermined = fixture_case(
        2,
        3,
        [-2.0, -2.0],
        [2.0, 2.0],
        [1.0, 2.0, 4.0],
        input -> (
            input[1] - 1.0,
            2.0 * (input[2] + 0.5),
            4.0 * (input[1] + input[2] - 0.5),
        ),
    )
    for build in CANDIDATE_BUILDERS
        regular_outcome = build(max_evaluations=200).run(regular, [1.5])
        @test regular_outcome.endpoint !== nothing
        @test only(regular_outcome.endpoint) ≈ 0.25 atol = 1.0e-8
        @test regular_outcome.reported_converged
        @test regular_outcome.reported_accepted
        @test regular_outcome.evaluations <= 200
        @test occursin("bounds_origin=[1.0]", regular_outcome.diagnostic)
        @test occursin("bounds_half_range=[3.0]", regular_outcome.diagnostic)
        @test occursin(
            "library_bounds_transform=$LIBRARY_BOUNDS_TRANSFORM",
            regular_outcome.diagnostic,
        )
        @test occursin("nf=", regular_outcome.diagnostic)
        @test occursin("screening_accepted=true", regular_outcome.diagnostic)
        @test occursin("screening_semantics_valid=true", regular_outcome.diagnostic)
        @test occursin("screening_residual_linf=", regular_outcome.diagnostic)

        over_outcome = build(max_evaluations=300).run(overdetermined, [0.0, 0.0])
        @test over_outcome.endpoint !== nothing
        @test collect(over_outcome.endpoint) ≈ [1.0, -0.5] atol = 1.0e-8
        @test over_outcome.reported_accepted
        @test over_outcome.evaluations <= 300
        @test occursin("outside_bounds_callbacks=0", over_outcome.diagnostic)
    end
end

@testset "rank-deficient and boundary systems fail safely" begin
    rank_deficient = fixture_case(
        2,
        2,
        [-2.0, -2.0],
        [2.0, 2.0],
        [1.0, 1.0],
        input -> begin
            shared = input[1] + input[2] - 1.0
            (shared, 2.0 * shared)
        end,
    )
    boundary = fixture_case(
        1,
        1,
        [-1.0],
        [1.0],
        [1.0],
        input -> (input[1] - 1.0,),
    )
    for build in CANDIDATE_BUILDERS
        rank_outcome = build(max_evaluations=300).run(rank_deficient, [0.0, 0.0])
        @test rank_outcome.endpoint !== nothing
        rank_endpoint = collect(rank_outcome.endpoint)
        @test abs(sum(rank_endpoint) - 1.0) <= 1.0e-8
        @test all((-2.0 .<= rank_endpoint) .& (rank_endpoint .<= 2.0))
        @test rank_outcome.evaluations <= 300

        boundary_outcome = build(max_evaluations=500).run(boundary, [0.0])
        @test boundary_outcome.endpoint !== nothing
        endpoint = only(boundary_outcome.endpoint)
        @test -1.0 <= endpoint <= 1.0
        @test abs(endpoint - 1.0) <= 1.0e-6
        @test boundary_outcome.evaluations <= 500
        @test occursin("outside_bounds_callbacks=0", boundary_outcome.diagnostic)

        boundary_start_outcome = build(max_evaluations=500).run(boundary, [1.0])
        @test boundary_start_outcome.endpoint !== nothing
        boundary_start_endpoint = only(boundary_start_outcome.endpoint)
        @test -1.0 <= boundary_start_endpoint <= 1.0
        @test boundary_start_outcome.evaluations <= 500
        @test occursin("outside_bounds_callbacks=0", boundary_start_outcome.diagnostic)
    end
end

@testset "nonfinite residuals and callback budget" begin
    nonfinite = fixture_case(
        1,
        1,
        [-1.0],
        [1.0],
        [1.0],
        input -> (NaN,);
        target=input -> NaN,
    )
    for build in CANDIDATE_BUILDERS
        nonfinite_outcome = build(max_evaluations=30).run(nonfinite, [0.0])
        @test !nonfinite_outcome.reported_accepted
        @test nonfinite_outcome.evaluations <= 30
        @test occursin("nonfinite_callbacks=", nonfinite_outcome.diagnostic)
        @test !occursin("nonfinite_callbacks=0", nonfinite_outcome.diagnostic)

        target_nonfinite_calls = Ref(0)
        target_nonfinite = fixture_case(
            1,
            1,
            [-1.0],
            [1.0],
            [1.0],
            input -> (input[1],);
            target=input -> NaN,
            calls=target_nonfinite_calls,
        )
        target_nonfinite_outcome =
            build(max_evaluations=100).run(target_nonfinite, [0.0])
        @test target_nonfinite_outcome.endpoint !== nothing
        @test !target_nonfinite_outcome.reported_accepted
        @test target_nonfinite_outcome.evaluations == target_nonfinite_calls[]
        @test occursin("screening_finite=false", target_nonfinite_outcome.diagnostic)
        @test !occursin("nonfinite_callbacks=0", target_nonfinite_outcome.diagnostic)

        stationary_calls = Ref(0)
        positive_stationary = fixture_case(
            1,
            2,
            [-2.0],
            [4.0],
            [1.0, 1.0],
            input -> (input[1], input[1] - 2.0);
            calls=stationary_calls,
        )
        stationary_outcome = build().run(positive_stationary, [1.0])
        @test stationary_outcome.status == "StalledSuccess"
        @test stationary_outcome.reported_converged
        @test !stationary_outcome.reported_accepted
        @test stationary_outcome.evaluations == stationary_calls[]
        @test occursin("retcode_success=true", stationary_outcome.diagnostic)
        @test occursin("screening_accepted=false", stationary_outcome.diagnostic)

        guard_invalid_calls = Ref(0)
        guard_invalid = fixture_case(
            1,
            1,
            [-1.0],
            [1.0],
            [1.0],
            input -> (input[1],);
            semantics=input -> false,
            calls=guard_invalid_calls,
        )
        guard_invalid_outcome = build().run(guard_invalid, [0.0])
        @test guard_invalid_outcome.endpoint !== nothing
        @test guard_invalid_outcome.reported_converged
        @test !guard_invalid_outcome.reported_accepted
        @test guard_invalid_outcome.evaluations == guard_invalid_calls[]
        @test occursin(
            "screening_semantics_valid=false",
            guard_invalid_outcome.diagnostic,
        )
        @test occursin("screening_residual_linf=0.0", guard_invalid_outcome.diagnostic)
        @test occursin("screening_accepted=false", guard_invalid_outcome.diagnostic)

        observed = Ref(0)
        budget_case = fixture_case(
            2,
            2,
            [-2.0, -2.0],
            [2.0, 2.0],
            [1.0, 1.0],
            input -> (input[1] - 1.0, input[2] + 1.0);
            calls=observed,
        )
        budget_outcome = build(max_evaluations=2).run(budget_case, [0.0, 0.0])
        @test budget_outcome.endpoint === nothing
        @test budget_outcome.status == "LOCAL_MAX_EVALUATIONS"
        @test budget_outcome.evaluations == observed[] == 2
        @test !budget_outcome.reported_converged
        @test !budget_outcome.reported_accepted
        @test occursin("callback_limit=2", budget_outcome.diagnostic)

        runner_observed = Ref(0)
        runner_limited = SolverExperimentCase(
            1,
            1,
            (-1.0,),
            (1.0,),
            (1.0,),
            (1.0,),
            input -> begin
                runner_observed[] >= 1 && throw(SolverExperimentBudgetExceeded(1))
                runner_observed[] += 1
                SolverCaseEvaluation((input[1] - 0.5,), input[1], true, true)
            end,
        )
        runner_outcome = build(max_evaluations=20).run(runner_limited, [0.0])
        @test runner_outcome.endpoint === nothing
        @test runner_outcome.status == "runner_evaluation_budget_exhausted"
        @test runner_outcome.evaluations == runner_observed[] == 1
        @test occursin("retcode=RUNNER-BUDGET", runner_outcome.diagnostic)
    end
end
