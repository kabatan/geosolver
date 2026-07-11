using GeoTargetBenchmarks
using GeoTargetCore
using Test

const REPOSITORY_ROOT = normpath(joinpath(@__DIR__, "..", "..", "..", ".."))

include(joinpath(REPOSITORY_ROOT, "benchmarks", "solver_lab", "CoreBaseline.jl"))
include(joinpath(@__DIR__, "..", "src", "ExperimentLocal005.jl"))
using .ExperimentLocal005
using .GeoTargetSolverLab

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

@testset "EXP-LOCAL-005 pinned truth-blind candidate" begin
    @test ExperimentLocal005._package_version() == DFOLS_VERSION == "1.6.5"
    @test ExperimentLocal005.PythonCall.python_executable_path() == PYTHON_EXECUTABLE
    source = read(joinpath(@__DIR__, "..", "src", "ExperimentLocal005.jl"), String)
    bridge = read(
        joinpath(@__DIR__, "..", "python", "geotarget_dfols_bridge.py"),
        String,
    )
    for forbidden in ("family_id", "instance_id", "gold_configurations", "gold_targets")
        @test !occursin(forbidden, source)
        @test !occursin(forbidden, bridge)
    end
    variant = dfols_variant()
    @test variant.name == "DFO-LS-TR"
    config = variant.configuration
    @test config.package_version == "1.6.5"
    @test config.native_bounds
    @test config.bounds_transform == BOUNDS_TRANSFORM
    @test config.residual_scaling == "declared"
    @test config.max_evaluations == 2_000
    @test config.algorithm_max_evaluations == 1_999
    @test config.endpoint_screen_reservation == 1
    @test config.interpolation_points == "dimension-plus-one"
    @test !config.random_initial_directions
    @test !config.parallel_initial_evaluations
    @test !config.restarts
    @test config.acceptance_residual_tolerance == 1.0e-12
    @test config.acceptance_requires_semantics_valid
    @test_throws ArgumentError dfols_variant(max_evaluations=1)
end

@testset "regular and overdetermined systems" begin
    regular_calls = Ref(0)
    regular = fixture_case(
        2,
        2,
        [-4.0, -2.0],
        [8.0, 6.0],
        [2.0, 0.5],
        input -> [2.0 * (input[1] - 1.0), 0.5 * (input[2] + 0.5)];
        calls=regular_calls,
    )
    regular_outcome = dfols_variant(max_evaluations=300).run(regular, [5.0, 3.0])
    @test regular_outcome.endpoint !== nothing
    @test collect(regular_outcome.endpoint) ≈ [1.0, -0.5] atol=2.0e-10
    @test regular_outcome.reported_converged
    @test regular_outcome.reported_accepted
    @test regular_outcome.evaluations == regular_calls[]
    @test occursin("outside_bounds_callbacks=0", regular_outcome.diagnostic)

    overdetermined_calls = Ref(0)
    overdetermined = fixture_case(
        2,
        3,
        [-2.0, -2.0],
        [4.0, 4.0],
        [1.0, 2.0, 0.25],
        input -> [
            input[1] - 1.0,
            2.0 * (input[2] - 0.25),
            0.25 * (input[1] + input[2] - 1.25),
        ];
        calls=overdetermined_calls,
    )
    overdetermined_outcome =
        dfols_variant(max_evaluations=300).run(overdetermined, [-1.0, 3.0])
    @test overdetermined_outcome.endpoint !== nothing
    @test collect(overdetermined_outcome.endpoint) ≈ [1.0, 0.25] atol=2.0e-10
    @test overdetermined_outcome.reported_accepted
    @test overdetermined_outcome.evaluations == overdetermined_calls[]
end

@testset "native bounds and common semantics screen" begin
    bound_calls = Ref(0)
    bounded = fixture_case(
        1,
        1,
        [0.0],
        [1.0],
        [1.0],
        input -> [input[1] - 2.0];
        calls=bound_calls,
    )
    bound_outcome = dfols_variant(max_evaluations=100).run(bounded, [0.25])
    @test bound_outcome.endpoint !== nothing
    @test 0.0 <= only(bound_outcome.endpoint) <= 1.0
    @test only(bound_outcome.endpoint) ≈ 1.0 atol=1.0e-12
    @test !bound_outcome.reported_accepted
    @test bound_outcome.evaluations == bound_calls[]
    @test occursin("outside_bounds_callbacks=0", bound_outcome.diagnostic)

    semantic_calls = Ref(0)
    invalid_semantics = fixture_case(
        1,
        1,
        [-1.0],
        [1.0],
        [1.0],
        input -> [input[1]];
        semantics=input -> input[1] > 0.25,
        calls=semantic_calls,
    )
    semantic_outcome = dfols_variant(max_evaluations=100).run(invalid_semantics, [0.75])
    @test semantic_outcome.endpoint !== nothing
    @test abs(only(semantic_outcome.endpoint)) <= 1.0e-10
    @test semantic_outcome.reported_converged
    @test !semantic_outcome.reported_accepted
    @test occursin("screening_semantics_valid=false", semantic_outcome.diagnostic)
    @test semantic_outcome.evaluations == semantic_calls[]
end

@testset "candidate and runner caps remain distinct" begin
    calls = Ref(0)
    impossible = fixture_case(
        1,
        1,
        [-2.0],
        [4.0],
        [1.0],
        input -> [input[1]^2 + 1.0];
        calls,
    )
    outcome = dfols_variant(max_evaluations=5).run(impossible, [3.0])
    @test outcome.status == "LOCAL_MAX_EVALUATIONS"
    @test outcome.evaluations == calls[] == 5
    @test outcome.endpoint !== nothing
    @test !outcome.reported_accepted

    problem = first(representative_problems(start_count=1))
    run = run_solver_experiment(
        [problem],
        [dfols_variant(max_evaluations=50)];
        prefixes=[1],
        evaluation_limit=3,
    )
    attempt = only(run.attempts)
    @test attempt.status == "runner_evaluation_budget_exhausted"
    @test attempt.budget_exhausted
    @test attempt.evaluations == 3
    @test attempt.reported_evaluations == 3
    @test !attempt.evaluation_count_mismatch
    summary = only(run.prefixes)
    @test summary.local_max_evaluations == 0
    @test summary.runner_budget_exhausted == 1
end

@testset "runner sharding and serial environment contract" begin
    runner = joinpath(@__DIR__, "..", "run.jl")
    source = read(runner, String)
    @test occursin("mod(index - 1, shard_count) == shard_index", source)
    @test occursin("JULIA_NUM_THREADS=1", source)
    @test occursin("OPENBLAS_NUM_THREADS", source)
    @test occursin("primary_work_metric", source)
    @test occursin("wall_time_role", source)
    command = `$(Base.julia_cmd()) --startup-file=no --history-file=no --project=$(joinpath(@__DIR__, "..")) $runner --help`
    help = read(command, String)
    @test occursin("--shard-index", help)
    @test occursin("--shard-count", help)
    @test occursin("local solve stays serial", help)
end
