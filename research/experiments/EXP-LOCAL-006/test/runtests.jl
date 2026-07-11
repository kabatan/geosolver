using GeoTargetBenchmarks
using Test

const REPOSITORY_ROOT = normpath(joinpath(@__DIR__, "..", "..", "..", ".."))

include(joinpath(@__DIR__, "..", "run_t0.jl"))
using .ExperimentLocal006

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

@testset "EXP-LOCAL-006 pinned truth-blind native-bound candidate" begin
    @test ExperimentLocal006._package_version() == SCIPY_VERSION == "1.18.0"
    @test ExperimentLocal006.PythonCall.python_executable_path() == PYTHON_EXECUTABLE
    source = read(joinpath(@__DIR__, "..", "src", "ExperimentLocal006.jl"), String)
    bridge = read(
        joinpath(@__DIR__, "..", "python", "geotarget_scipy_trf_bridge.py"),
        String,
    )
    for forbidden in ("family_id", "instance_id", "gold_configurations", "gold_targets")
        @test !occursin(forbidden, source)
        @test !occursin(forbidden, bridge)
    end
    @test occursin("method=\"trf\"", bridge)
    @test occursin("tr_solver=\"exact\"", bridge)
    variant = scipy_trf_exact_variant()
    @test variant.name == "SCIPY-TRF-EXACT"
    config = variant.configuration
    @test config.package_version == "1.18.0"
    @test config.native_bounds
    @test config.normalized_lower == -1.0
    @test config.normalized_upper == 1.0
    @test config.residual_scaling == "declared"
    @test config.max_callbacks == 600
    @test config.algorithm_callback_limit == 599
    @test config.endpoint_screen_reservation == 1
    @test config.all_probes_charged
    @test config.scipy_success_role == "diagnostic-only"
    @test !config.identity_routing
    @test !config.upfront_rank_condition_routing
    @test_throws ArgumentError scipy_trf_exact_variant(max_callbacks=1)
    @test_throws ArgumentError scipy_trf_exact_variant(max_backoffs=-1)
end

@testset "regular, overdetermined, scaling, and endpoint ledger" begin
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
    outcome = scipy_trf_exact_variant(max_callbacks=200).run(regular, [5.0, 3.0])
    @test outcome.endpoint !== nothing
    @test collect(outcome.endpoint) ≈ [1.0, -0.5] atol=2.0e-9
    @test outcome.reported_converged
    @test outcome.reported_accepted
    @test outcome.evaluations == regular_calls[]
    @test occursin("endpoint_screen_callbacks=1", outcome.diagnostic)
    @test occursin("outside_bounds_callbacks=0", outcome.diagnostic)

    over_calls = Ref(0)
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
        calls=over_calls,
    )
    over_outcome =
        scipy_trf_exact_variant(max_callbacks=200).run(overdetermined, [-1.0, 3.0])
    @test over_outcome.endpoint !== nothing
    @test collect(over_outcome.endpoint) ≈ [1.0, 0.25] atol=2.0e-9
    @test over_outcome.reported_accepted
    @test over_outcome.evaluations == over_calls[]
end

@testset "native bounds and SciPy success is not acceptance" begin
    calls = Ref(0)
    bounded = fixture_case(
        1,
        1,
        [0.0],
        [1.0],
        [1.0],
        input -> [input[1] - 2.0];
        calls,
    )
    outcome = scipy_trf_exact_variant(max_callbacks=100).run(bounded, [0.25])
    @test outcome.endpoint !== nothing
    @test 0.0 <= only(outcome.endpoint) <= 1.0
    @test only(outcome.endpoint) ≈ 1.0 atol=2.0e-8
    @test outcome.reported_converged
    @test !outcome.reported_accepted
    @test outcome.evaluations == calls[]
    @test occursin("native_bounds=true", outcome.diagnostic)
    @test occursin("screening_accepted=false", outcome.diagnostic)
end

@testset "guarded finite differences back off and charge every probe" begin
    semantic_calls = Ref(0)
    semantic_case = fixture_case(
        1,
        1,
        [-1.0],
        [1.0],
        [1.0],
        input -> [input[1]^2];
        semantics=input -> input[1] > 0.0,
        calls=semantic_calls,
    )
    bounds, normalized = ExperimentLocal006._bounds_map(
        semantic_case,
        [ExperimentLocal006.FINITE_DIFFERENCE_STEP / 4],
    )
    ledger = ExperimentLocal006.CallbackLedger(100)
    base, valid, _ = ExperimentLocal006._scaled_evaluation(
        semantic_case,
        bounds,
        normalized,
        [1.0],
        ledger,
        :residual,
    )
    @test valid
    jacobian = ExperimentLocal006._guarded_fd_jacobian(
        semantic_case,
        bounds,
        normalized,
        base,
        [1.0],
        ledger;
        finite_difference_step=FINITE_DIFFERENCE_STEP,
        max_backoffs=8,
    )
    @test jacobian[1, 1] ≈ 2normalized[1] atol=2.0e-10
    @test ledger.backoff_events > 0
    @test ledger.semantic_invalid_calls > 0
    @test ledger.central_columns == 1
    @test ledger.calls == semantic_calls[]

    bound_calls = Ref(0)
    bound_case = fixture_case(
        1,
        1,
        [-1.0],
        [1.0],
        [1.0],
        input -> [input[1]^2];
        calls=bound_calls,
    )
    bound_map, at_upper = ExperimentLocal006._bounds_map(bound_case, [1.0])
    bound_ledger = ExperimentLocal006.CallbackLedger(20)
    bound_base, bound_valid, _ = ExperimentLocal006._scaled_evaluation(
        bound_case,
        bound_map,
        at_upper,
        [1.0],
        bound_ledger,
        :residual,
    )
    @test bound_valid
    bound_jacobian = ExperimentLocal006._guarded_fd_jacobian(
        bound_case,
        bound_map,
        at_upper,
        bound_base,
        [1.0],
        bound_ledger,
    )
    @test bound_jacobian[1, 1] ≈ 2.0 atol=2.0e-5
    @test bound_ledger.one_sided_columns == 1
    @test bound_ledger.calls == bound_calls[]
    @test bound_ledger.outside_bounds_calls == 0

    domain_calls = Ref(0)
    domain_case = fixture_case(
        1,
        1,
        [-1.0],
        [1.0],
        [1.0],
        input -> [input[1] > 0.0 ? sqrt(input[1]) : NaN];
        calls=domain_calls,
    )
    domain_map, near_domain_edge = ExperimentLocal006._bounds_map(
        domain_case,
        [FINITE_DIFFERENCE_STEP / 4],
    )
    domain_ledger = ExperimentLocal006.CallbackLedger(100)
    domain_base, domain_valid, _ = ExperimentLocal006._scaled_evaluation(
        domain_case,
        domain_map,
        near_domain_edge,
        [1.0],
        domain_ledger,
        :residual,
    )
    @test domain_valid
    domain_jacobian = ExperimentLocal006._guarded_fd_jacobian(
        domain_case,
        domain_map,
        near_domain_edge,
        domain_base,
        [1.0],
        domain_ledger;
        finite_difference_step=FINITE_DIFFERENCE_STEP,
        max_backoffs=8,
    )
    @test isfinite(domain_jacobian[1, 1])
    @test domain_ledger.nonfinite_calls > 0
    @test domain_ledger.backoff_events > 0
    @test domain_ledger.calls == domain_calls[]

    outside_calls = Ref(0)
    outside_case = fixture_case(
        1,
        1,
        [-1.0],
        [1.0],
        [1.0],
        input -> [input[1]];
        calls=outside_calls,
    )
    outside_map, _ = ExperimentLocal006._bounds_map(outside_case, [0.0])
    outside_ledger = ExperimentLocal006.CallbackLedger(20)
    _, outside_valid, _ = ExperimentLocal006._scaled_evaluation(
        outside_case,
        outside_map,
        [nextfloat(1.0)],
        [1.0],
        outside_ledger,
        :jacobian_probe,
    )
    @test !outside_valid
    @test outside_ledger.calls == outside_calls[] == 1
    @test outside_ledger.outside_bounds_calls == 1
    @test outside_ledger.semantic_invalid_calls == 1
end

@testset "candidate hard cap reserves endpoint screen" begin
    calls = Ref(0)
    simple = fixture_case(
        1,
        1,
        [-2.0],
        [2.0],
        [1.0],
        input -> [input[1] - 0.25];
        calls,
    )
    outcome = scipy_trf_exact_variant(max_callbacks=20).run(simple, [1.5])
    @test outcome.evaluations == calls[] <= 20
    @test occursin("algorithm_callback_limit=19", outcome.diagnostic)
    @test occursin("endpoint_screen_reservation=1", outcome.diagnostic)
    @test occursin("endpoint_screen_callbacks=1", outcome.diagnostic)

    impossible_calls = Ref(0)
    impossible = fixture_case(
        1,
        1,
        [-2.0],
        [2.0],
        [1.0],
        input -> [input[1]^2 + 1.0];
        calls=impossible_calls,
    )
    exhausted = scipy_trf_exact_variant(max_callbacks=5).run(impossible, [1.5])
    @test exhausted.status == "LOCAL_MAX_EVALUATIONS"
    @test exhausted.evaluations == impossible_calls[] == 4
    @test occursin("algorithm_callback_limit=4", exhausted.diagnostic)
    @test occursin("endpoint_screen_callbacks=0", exhausted.diagnostic)

    problem = first(GeoTargetSolverLab.representative_problems(start_count=1))
    run = run_solver_experiment(
        [problem],
        [scipy_trf_exact_variant(max_callbacks=50)];
        prefixes=[1],
        evaluation_limit=3,
    )
    attempt = only(run.attempts)
    @test attempt.status == "runner_evaluation_budget_exhausted"
    @test attempt.budget_exhausted
    @test attempt.evaluations == attempt.reported_evaluations == 3
    @test !attempt.evaluation_count_mismatch
end

@testset "case-cumulative attempt-boundary prefixes and sharding contract" begin
    tracker = CallbackPrefixTracker([600, 1_200, 2_400, 4_800])
    @test isempty(record_attempt!(tracker, 550, 1))
    first_crossing = only(record_attempt!(tracker, 100, 2))
    @test first_crossing.threshold == 600
    @test first_crossing.cumulative_callbacks == 650
    @test first_crossing.overshoot_callbacks == 50
    double_crossing = record_attempt!(tracker, 2_000, 3)
    @test [entry.threshold for entry in double_crossing] == [1_200, 2_400]
    @test all(entry.start_index == 3 for entry in double_crossing)
    final_crossing = only(record_attempt!(tracker, 2_150, 4))
    @test final_crossing.threshold == 4_800
    @test final_crossing.overshoot_callbacks == 0
    @test tracker_complete(tracker)

    options = parse_arguments([
        "--callback-prefixes=600",
        "--max-starts=16",
        "--shard-index=1",
        "--shard-count=2",
    ])
    @test options[:callback_prefixes] == [600]
    @test options[:max_starts] == 16
    @test options[:shard_index] == 1
    @test_throws ErrorException parse_arguments(["--callback-prefixes=1200,600"])

    runner = read(joinpath(@__DIR__, "..", "run_t0.jl"), String)
    @test occursin("mod(index - 1, shard_count) == shard_index", runner)
    @test occursin("JULIA_NUM_THREADS=1", runner)
    @test occursin("RUNNER_ATTEMPT_HARD_LIMIT", runner)
    @test occursin("verify_replay_material", runner)
    @test occursin("_suffix_stable_evaluations_to_lab_safe_full", runner)
    @test occursin("formal T0 requires a clean committed worktree", runner)
    @test occursin("overshoot_callbacks", runner)
    @test occursin("single-stream-attempt-boundary-snapshots-no-reruns", runner)
end
