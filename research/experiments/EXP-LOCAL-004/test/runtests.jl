using GeoTargetBenchmarks
using Test

include(joinpath(@__DIR__, "..", "src", "ExperimentLocal004.jl"))
using .ExperimentLocal004

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
        @test config.reported_acceptance == "library-retcode-diagnostic-only"
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
