using GeoTargetBenchmarks
using LinearAlgebra
using Test

include(joinpath(
    REPOSITORY_ROOT,
    "benchmarks",
    "solver_lab",
    "NativeSafeguardedLM.jl",
))
using .GeoTargetNativeSafeguardedLM

function _native_lm_test_case(
    dimension,
    residual_dimension,
    residual_fn;
    lower=fill(-2.0, dimension),
    upper=fill(2.0, dimension),
    variable_scales=ones(dimension),
    residual_scales=ones(residual_dimension),
    semantics_fn=(_ -> true),
)
    calls = Ref(0)
    outside_bounds = Ref(0)
    callback = function (input)
        calls[] += 1
        outside_bounds[] += !all(lower .<= input .<= upper)
        values = collect(Float64, residual_fn(input))
        length(values) == residual_dimension ||
            throw(DimensionMismatch("test residual has wrong dimension"))
        semantics_valid = semantics_fn(input)
        finite = semantics_valid && all(isfinite, values)
        return SolverCaseEvaluation(
            Tuple(values),
            finite ? 0.0 : nothing,
            finite,
            finite,
        )
    end
    case = SolverExperimentCase(
        dimension,
        residual_dimension,
        Tuple(Float64[lower...]),
        Tuple(Float64[upper...]),
        Tuple(Float64[variable_scales...]),
        Tuple(Float64[residual_scales...]),
        callback,
    )
    return case, calls, outside_bounds
end

function _native_lm_diagnostic_count(outcome, key)
    matched = match(Regex("(?:^|;)$key=([0-9]+)(?:;|\$)"), outcome.diagnostic)
    matched === nothing && error("missing diagnostic field $key")
    return parse(Int, only(matched.captures))
end

function _native_lm_diagnostic_float(outcome, key)
    matched = match(Regex("(?:^|;)$key=([^;]+)(?:;|\$)"), outcome.diagnostic)
    matched === nothing && error("missing diagnostic field $key")
    return parse(Float64, only(matched.captures))
end

@testset "native safeguarded LM regular, curved, and structural cases" begin
    candidate = native_safeguarded_lm_variant(
        max_iterations=200,
        max_evaluations=2_000,
    )
    @test candidate.configuration.implementation ==
          "native-scale-aware-safeguarded-lm-v1"
    @test candidate.configuration.coordinate_scaling == "bounds-midpoint-half-range"
    @test candidate.configuration.residual_scaling == "declared"
    @test candidate.configuration.residual_tolerance == 1.0e-12
    @test candidate.configuration.derivative ==
          "bounds-aware-central-with-one-sided-fallback"
    @test candidate.configuration.diagonal_scaling ==
          "max-jacobian-column-norm-floor"
    @test candidate.configuration.linear_system ==
          "augmented-J-sqrt-lambda-D-CPQR"
    @test candidate.configuration.damping_update ==
          "nielsen-actual-predicted-reduction-ratio"
    @test candidate.configuration.invalid_trial_policy ==
          "reject-and-increase-damping"
    @test candidate.configuration.max_iterations == 200
    @test candidate.configuration.max_evaluations == 2_000
    @test isempty(intersect(
        Set(keys(candidate.configuration)),
        Set((:family_id, :instance_id, :case_id, :gold, :known_root)),
    ))

    regular, regular_calls, regular_outside = _native_lm_test_case(
        2,
        2,
        input -> (input[1] - 0.25, 4 * (input[2] + 0.5));
        residual_scales=[1.0, 2.0],
    )
    regular_outcome = candidate.run(regular, [1.5, 1.25])
    @test regular_outcome.status == NATIVE_LM_CONVERGED
    @test regular_outcome.reported_converged
    @test regular_outcome.reported_accepted
    @test collect(regular_outcome.endpoint) ≈ [0.25, -0.5] atol=1.0e-10
    @test regular_outcome.evaluations == regular_calls[]
    @test regular_outcome.evaluations <= 2_000
    @test regular_outside[] == 0
    @test _native_lm_diagnostic_count(regular_outcome, "accepted_trials") >= 1
    @test _native_lm_diagnostic_count(regular_outcome, "central_columns") >= 1
    @test _native_lm_diagnostic_float(regular_outcome, "damping") !=
          candidate.configuration.initial_damping

    curved, curved_calls, curved_outside = _native_lm_test_case(
        2,
        2,
        input -> (10 * (input[2] - input[1]^2), 1 - input[1]);
        lower=[-2.0, -1.0],
        upper=[2.0, 3.0],
    )
    curved_outcome = candidate.run(curved, [-1.2, 1.0])
    @test curved_outcome.status == NATIVE_LM_CONVERGED
    @test curved_outcome.reported_accepted
    @test collect(curved_outcome.endpoint) ≈ [1.0, 1.0] atol=2.0e-9
    @test curved_outcome.evaluations == curved_calls[]
    @test curved_outcome.evaluations <= 2_000
    @test curved_outside[] == 0

    rank_deficient, rank_calls, rank_outside = _native_lm_test_case(
        2,
        2,
        input -> (
            input[1] + input[2] - 1,
            (1 + 1.0e-10) * (input[1] + input[2] - 1),
        ),
    )
    rank_outcome = candidate.run(rank_deficient, [-0.8, 0.2])
    @test rank_outcome.status == NATIVE_LM_CONVERGED
    @test abs(sum(rank_outcome.endpoint) - 1) <= 1.0e-10
    @test rank_outcome.evaluations == rank_calls[]
    @test rank_outcome.evaluations <= 2_000
    @test rank_outside[] == 0

    overdetermined, over_calls, over_outside = _native_lm_test_case(
        2,
        3,
        input -> (
            input[1] - 0.25,
            input[2] + 0.5,
            input[1] + input[2] + 0.25,
        ),
    )
    over_outcome = candidate.run(overdetermined, [1.5, 1.25])
    @test over_outcome.status == NATIVE_LM_CONVERGED
    @test collect(over_outcome.endpoint) ≈ [0.25, -0.5] atol=1.0e-10
    @test over_outcome.evaluations == over_calls[]
    @test over_outcome.evaluations <= 2_000
    @test over_outside[] == 0
end

@testset "native safeguarded LM bounds, invalid trials, and budget" begin
    boundary, boundary_calls, boundary_outside = _native_lm_test_case(
        1,
        1,
        input -> (input[1] - 1,);
        lower=[-1.0],
        upper=[1.0],
    )
    boundary_candidate = native_safeguarded_lm_variant(
        max_iterations=40,
        max_evaluations=200,
    )
    boundary_outcome = boundary_candidate.run(boundary, [-1.0])
    @test boundary_outcome.status == NATIVE_LM_CONVERGED
    @test only(boundary_outcome.endpoint) ≈ 1.0 atol=1.0e-12
    @test boundary_outcome.evaluations == boundary_calls[]
    @test boundary_outcome.evaluations <= 200
    @test boundary_outside[] == 0
    @test _native_lm_diagnostic_count(boundary_outcome, "one_sided_columns") >= 1

    nonfinite, nonfinite_calls, nonfinite_outside = _native_lm_test_case(
        1,
        1,
        input -> input[1] >= 0 ? (input[1] + 1,) : (NaN,);
        lower=[-1.0],
        upper=[1.0],
        semantics_fn=input -> input[1] >= 0,
    )
    nonfinite_candidate = native_safeguarded_lm_variant(
        max_iterations=20,
        max_evaluations=200,
    )
    nonfinite_outcome = nonfinite_candidate.run(nonfinite, [0.5])
    @test nonfinite_outcome.status in (NATIVE_LM_NO_PROGRESS, NATIVE_LM_MAX_ITERATIONS)
    @test !nonfinite_outcome.reported_accepted
    @test _native_lm_diagnostic_count(nonfinite_outcome, "invalid_trials") >= 1
    @test _native_lm_diagnostic_count(nonfinite_outcome, "invalid_callbacks") >= 1
    @test nonfinite_outcome.evaluations == nonfinite_calls[]
    @test nonfinite_outcome.evaluations <= 200
    @test nonfinite_outside[] == 0

    budget_case, budget_calls, budget_outside = _native_lm_test_case(
        2,
        2,
        input -> (input[1] - 0.25, input[2] + 0.5),
    )
    budget_candidate = native_safeguarded_lm_variant(
        max_iterations=20,
        max_evaluations=3,
    )
    budget_outcome = budget_candidate.run(budget_case, [1.0, 1.0])
    @test budget_outcome.status == NATIVE_LM_MAX_EVALUATIONS
    @test !budget_outcome.reported_accepted
    @test budget_outcome.evaluations == budget_calls[] == 3
    @test budget_outside[] == 0

    iteration_case, iteration_calls, iteration_outside = _native_lm_test_case(
        2,
        2,
        input -> (input[1] - 0.25, input[2] + 0.5),
    )
    iteration_candidate = native_safeguarded_lm_variant(
        max_iterations=1,
        max_evaluations=20,
    )
    iteration_outcome = iteration_candidate.run(iteration_case, [1.0, 1.0])
    @test iteration_outcome.status == NATIVE_LM_MAX_ITERATIONS
    @test iteration_outcome.iterations == 1
    @test iteration_outcome.evaluations == iteration_calls[] <= 20
    @test iteration_outside[] == 0

    invalid_initial, invalid_calls, invalid_outside = _native_lm_test_case(
        1,
        1,
        _ -> (NaN,);
        lower=[-1.0],
        upper=[1.0],
        semantics_fn=_ -> false,
    )
    invalid_outcome = boundary_candidate.run(invalid_initial, [0.0])
    @test invalid_outcome.status == NATIVE_LM_INITIAL_EVALUATION_INVALID
    @test invalid_outcome.evaluations == invalid_calls[] == 1
    @test !invalid_outcome.reported_accepted
    @test invalid_outside[] == 0
end

@testset "native safeguarded LM signed and permuted replica" begin
    root = [0.25, -0.4]
    start = [0.8, 0.7]
    base, base_calls, base_outside = _native_lm_test_case(
        2,
        2,
        input -> (input[1] - root[1], 3 * (input[2] - root[2]));
        lower=[-1.0, -1.0],
        upper=[1.0, 1.0],
    )
    replica, replica_calls, replica_outside = _native_lm_test_case(
        2,
        2,
        input -> begin
            base_coordinates = [input[2], -input[1]]
            base_residual = [
                base_coordinates[1] - root[1],
                3 * (base_coordinates[2] - root[2]),
            ]
            (-base_residual[2], base_residual[1])
        end;
        lower=[-1.0, -1.0],
        upper=[1.0, 1.0],
    )
    candidate = native_safeguarded_lm_variant(
        max_iterations=80,
        max_evaluations=500,
    )
    base_outcome = candidate.run(base, start)
    replica_start = [-start[2], start[1]]
    replica_outcome = candidate.run(replica, replica_start)
    @test base_outcome.status == replica_outcome.status == NATIVE_LM_CONVERGED
    replica_as_base = [replica_outcome.endpoint[2], -replica_outcome.endpoint[1]]
    @test collect(base_outcome.endpoint) ≈ root atol=1.0e-10
    @test replica_as_base ≈ root atol=1.0e-10
    @test collect(base_outcome.endpoint) ≈ replica_as_base atol=1.0e-10
    @test base_outcome.evaluations == base_calls[]
    @test replica_outcome.evaluations == replica_calls[]
    @test base_outside[] == replica_outside[] == 0

    @test_throws ArgumentError native_safeguarded_lm_variant(max_evaluations=0)
    @test_throws ArgumentError native_safeguarded_lm_variant(initial_damping=0)
    @test_throws ArgumentError native_safeguarded_lm_variant(acceptance_ratio=1)
    @test_throws ArgumentError native_safeguarded_lm_variant(
        minimum_damping=1.0,
        initial_damping=0.5,
    )
end
