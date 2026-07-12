using GeoTargetBenchmarks
using JSON3
using LinearAlgebra
using Test

const TEST_EXPERIMENT_ROOT = normpath(joinpath(@__DIR__, ".."))
const TEST_REPOSITORY_ROOT = normpath(joinpath(TEST_EXPERIMENT_ROOT, "..", "..", ".."))

include(joinpath(TEST_EXPERIMENT_ROOT, "run_t0.jl"))
using .ExperimentLocal008
using .ExperimentLocal008T0Policy

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

function diagnostic_fields(text)
    fields = Dict{String,String}()
    for entry in split(text, ';')
        parts = split(entry, '='; limit=2)
        length(parts) == 2 || continue
        fields[String(first(parts))] = String(last(parts))
    end
    return fields
end

@testset "OrthoMADS adjusted Halton and scaled Householder construction" begin
    @test halton_direction(2, 6) ≈ [3 / 8, 2 / 9] atol=0.0
    @test adjusted_halton_direction(2, 6, 3) == [-1, -2]
    @test orthomads_basis(2, 6, 3) == [3 -4; -4 -3]

    for dimension in (2, 4, 7), ell in (1, 3, 6), t in (dimension + 1, dimension + 4)
        q = adjusted_halton_direction(dimension, t, ell)
        basis = orthomads_basis(dimension, t, ell)
        qnorm2 = sum(abs2, q)
        @test transpose(basis) * basis == qnorm2^2 .* Matrix{Int}(I, dimension, dimension)
        @test all(isinteger, basis)
        steps = orthomads_poll_steps(dimension, t, ell)
        @test size(steps) == (dimension, 2 * dimension)
        @test steps[:, 1:dimension] == -steps[:, dimension + 1:end]
        @test maximum(norm.(eachcol(steps))) <= 2.0^(-ell) + 8eps(Float64)
    end

    rotated = orthomads_basis(4, 8, 3)
    @test any(count(!iszero, view(rotated, :, column)) > 1 for column in axes(rotated, 2))
    @test orthomads_basis(4, 8, 3) != orthomads_basis(4, 9, 3)
    @test orthomads_poll_steps(4, 8, 3) == orthomads_poll_steps(4, 8, 3)
    @test_throws ArgumentError adjusted_halton_direction(2, 3, -1)
end

@testset "truth-blind candidate contract and deterministic options" begin
    source = read(joinpath(TEST_EXPERIMENT_ROOT, "src", "ExperimentLocal008.jl"), String)
    for forbidden in ("family_id", "instance_id", "gold_configurations", "gold_targets")
        @test !occursin(forbidden, source)
    end
    candidate = orthomads_variant()
    @test candidate.name == "ORTHOMADS-EB"
    config = candidate.configuration
    @test config.algorithm == "poll-only-OrthoMADS-2n"
    @test config.constraint_policy == "extreme-barrier"
    @test config.direction_generator == "Halton-adjusted-integer-scaled-Householder-2n"
    @test config.poll_policy == "complete-poll-strict-merit-decrease"
    @test config.incomplete_poll_policy ==
          "discard-partial-poll-best-and-stop-at-local-cap"
    @test !config.search_step
    @test !config.surrogate
    @test config.residual_scaling == "declared"
    @test config.max_callbacks == 600
    @test config.algorithm_callback_limit == 599
    @test config.endpoint_screen_reservation == 1
    @test config.deterministic_seed == 0
    @test config.stationary_nonroot_policy == "typed-nonanswer"
    @test config.all_callbacks_charged
    @test !config.identity_routing
    @test_throws ArgumentError orthomads_variant(max_callbacks=1)
    @test_throws ArgumentError orthomads_variant(max_mesh_index=51)
    @test_throws ArgumentError orthomads_variant(deterministic_seed=-1)
end

@testset "declared residual scaling, nonsquare support, and callback reconciliation" begin
    calls = Ref(0)
    scaled_nonsquare = fixture_case(
        1,
        2,
        [-1.0],
        [1.0],
        [1.0e8, 1.0e-8],
        input -> [1.0e8 * (input[1] - 0.25), 1.0e-8 * (input[1] - 0.25)];
        calls,
    )
    outcome = orthomads_variant(max_callbacks=200).run(scaled_nonsquare, [0.5])
    @test outcome.endpoint !== nothing
    @test only(outcome.endpoint) ≈ 0.25 atol=1.0e-14
    @test outcome.reported_converged
    @test outcome.reported_accepted
    @test outcome.status == "ORTHOMADS_ROOT"
    @test outcome.evaluations == calls[] <= 200
    fields = diagnostic_fields(outcome.diagnostic)
    @test parse(Int, fields["callbacks"]) == outcome.evaluations
    @test parse(Int, fields["algorithm_callbacks"]) +
          parse(Int, fields["endpoint_screen_callbacks"]) == outcome.evaluations
    @test fields["endpoint_screen_callbacks"] == "1"
    @test fields["screening_accepted"] == "true"
end

@testset "positive-residual stationary point is a typed non-answer" begin
    calls = Ref(0)
    stationary = fixture_case(
        1,
        1,
        [-1.0],
        [1.0],
        [1.0],
        input -> [1.0 + input[1]^2];
        calls,
    )
    outcome = orthomads_variant(max_callbacks=100, max_mesh_index=8).run(stationary, [0.0])
    @test outcome.endpoint !== nothing
    @test only(outcome.endpoint) == 0.0
    @test outcome.status == "MIN_POLL_SIZE_NONROOT"
    @test !outcome.reported_converged
    @test !outcome.reported_accepted
    @test outcome.evaluations == calls[]
    fields = diagnostic_fields(outcome.diagnostic)
    @test parse(Float64, fields["best_residual_linf"]) >= 1.0
    @test fields["screening_accepted"] == "false"
end

@testset "guard and domain failures use the extreme barrier without aborting poll" begin
    calls = Ref(0)
    guarded = fixture_case(
        1,
        1,
        [-1.0],
        [1.0],
        [1.0],
        input -> begin
            input[1] < 0.0 && error("fixture domain failure")
            [input[1] - 0.25]
        end;
        semantics=input -> input[1] > 0.0,
        calls,
    )
    outcome = orthomads_variant(max_callbacks=100).run(guarded, [0.5])
    @test outcome.endpoint !== nothing
    @test only(outcome.endpoint) ≈ 0.25 atol=1.0e-14
    @test outcome.reported_accepted
    @test outcome.evaluations == calls[]
    fields = diagnostic_fields(outcome.diagnostic)
    @test parse(Int, fields["oracle_exceptions"]) >= 1
    @test parse(Int, fields["extreme_barrier_callbacks"]) >= 1
    @test fields["screening_accepted"] == "true"

    semantic_calls = Ref(0)
    semantic = fixture_case(
        1,
        1,
        [-1.0],
        [1.0],
        [1.0],
        input -> [input[1] - 0.25];
        semantics=input -> input[1] > 0.0,
        calls=semantic_calls,
    )
    semantic_outcome = orthomads_variant(max_callbacks=100).run(semantic, [-0.25])
    @test semantic_outcome.reported_accepted
    @test semantic_outcome.evaluations == semantic_calls[]
    semantic_fields = diagnostic_fields(semantic_outcome.diagnostic)
    @test parse(Int, semantic_fields["semantic_invalid_callbacks"]) >= 1
    @test parse(Int, semantic_fields["extreme_barrier_callbacks"]) >= 1
end

@testset "nonfinite barrier and hard callback limits fail closed" begin
    nonfinite_calls = Ref(0)
    nonfinite = fixture_case(
        1,
        1,
        [-1.0],
        [1.0],
        [1.0],
        input -> [NaN];
        calls=nonfinite_calls,
    )
    invalid = orthomads_variant(max_callbacks=30, max_mesh_index=4).run(nonfinite, [0.0])
    @test invalid.endpoint === nothing
    @test !invalid.reported_accepted
    @test invalid.evaluations == nonfinite_calls[]
    invalid_fields = diagnostic_fields(invalid.diagnostic)
    @test parse(Int, invalid_fields["nonfinite_callbacks"]) > 0
    @test parse(Int, invalid_fields["extreme_barrier_callbacks"]) > 0

    cap_calls = Ref(0)
    impossible = fixture_case(
        1,
        1,
        [-1.0],
        [1.0],
        [1.0],
        input -> [1.0];
        calls=cap_calls,
    )
    capped = orthomads_variant(max_callbacks=8).run(impossible, [0.0])
    @test capped.status == "LOCAL_MAX_EVALUATIONS"
    @test capped.evaluations == cap_calls[] == 8
    capped_fields = diagnostic_fields(capped.diagnostic)
    @test capped_fields["algorithm_callbacks"] == "7"
    @test capped_fields["endpoint_screen_callbacks"] == "1"

    # At n=2, t=3, ell=0 the first poll direction is +e1.  The first
    # trial therefore sees the exact root, but the cap interrupts the 2n
    # poll before its opposite directions.  That partial best is not eligible.
    partial_calls = Ref(0)
    partial_root = fixture_case(
        2,
        2,
        [-1.0, -1.0],
        [1.0, 1.0],
        [1.0, 1.0],
        input -> [input[1] - 1.0, input[2]];
        calls=partial_calls,
    )
    partial = orthomads_variant(max_callbacks=4).run(partial_root, [0.0, 0.0])
    @test partial.status == "LOCAL_MAX_EVALUATIONS"
    @test collect(partial.endpoint) == [0.0, 0.0]
    @test !partial.reported_accepted
    @test partial.evaluations == partial_calls[] == 4

    problem = first(GeoTargetSolverLab.representative_problems(start_count=1))
    run = run_solver_experiment(
        [problem],
        [orthomads_variant(max_callbacks=50)];
        prefixes=[1],
        evaluation_limit=3,
    )
    attempt = only(run.attempts)
    @test attempt.status == "runner_evaluation_budget_exhausted"
    @test attempt.budget_exhausted
    @test attempt.evaluations == attempt.reported_evaluations == 3
    @test !attempt.evaluation_count_mismatch
end

function assessor_attempt(
    start_index,
    target,
    evaluations;
    qualified=true,
    gold=true,
    ambiguous=false,
    diagnostic=nothing,
)
    return (;
        start_index,
        evaluations,
        assessor_qualified=qualified,
        assessor_gold_matched=gold,
        assessor_target_ambiguous=ambiguous,
        assessor_matched_target_id=target,
        diagnostic,
    )
end

@testset "raw common-assessor suffix work and right censoring" begin
    reached = [
        assessor_attempt(1, "target-a", 100),
        assessor_attempt(2, "target-b", 200),
    ]
    @test _suffix_stable_assessor_work_from_sequence(reached, 2) == 300
    @test _right_censored_assessor_work(300) == (work=300, event=true)
    @test _right_censored_assessor_work(5_100) == (work=4_800, event=false)
    @test _right_censored_assessor_work(nothing) == (work=4_800, event=false)

    later_unqualified = [
        reached...,
        assessor_attempt(3, nothing, 50; qualified=false, gold=false),
    ]
    @test _suffix_stable_assessor_work_from_sequence(later_unqualified, 2) == 300
    later_unsafe = [
        reached...,
        assessor_attempt(3, nothing, 50; qualified=true, gold=false),
    ]
    @test _suffix_stable_assessor_work_from_sequence(later_unsafe, 2) === nothing
    @test_throws ErrorException _suffix_stable_assessor_work_from_sequence(
        [assessor_attempt(2, "target-a", 100)],
        1,
    )

    recoveries = [
        assessor_attempt(
            1,
            "target-a",
            20;
            diagnostic="callbacks=20;extreme_barrier_callbacks=2",
        ),
        assessor_attempt(2, "target-a", 10; diagnostic="callbacks=10"),
    ]
    @test _qualified_extreme_barrier_recoveries(recoveries) == 1
end

@testset "preregistered T0 gate" begin
    strata = Dict(stratum => 1 for stratum in T0_STRATA)
    path_a = evaluate_t0_gate(
        control_targets=4,
        candidate_targets=5,
        control_safe_full=2,
        candidate_safe_full=3,
        control_callback_work=10_000,
        candidate_callback_work=11_000,
        control_stratum_targets=strata,
        candidate_stratum_targets=strata,
        candidate_strict_guard_safe_full=true,
        candidate_qualified_extreme_barrier_recoveries=1,
        candidate_safety_accounting_budget_exception_count=0,
        mechanism_fixture_tests_passed=true,
        truth_blind_source_audit_passed=true,
    )
    @test path_a["passed"]
    @test path_a["path_a"]
    @test !path_a["path_b"]

    path_b = evaluate_t0_gate(
        control_targets=4,
        candidate_targets=4,
        control_safe_full=2,
        candidate_safe_full=2,
        control_callback_work=10_000,
        candidate_callback_work=8_000,
        control_stratum_targets=strata,
        candidate_stratum_targets=strata,
        candidate_strict_guard_safe_full=true,
        candidate_qualified_extreme_barrier_recoveries=1,
        candidate_safety_accounting_budget_exception_count=0,
        mechanism_fixture_tests_passed=true,
        truth_blind_source_audit_passed=true,
    )
    @test path_b["passed"]
    @test !path_b["path_a"]
    @test path_b["path_b"]

    regressed = evaluate_t0_gate(
        control_targets=4,
        candidate_targets=5,
        control_safe_full=2,
        candidate_safe_full=3,
        control_callback_work=10_000,
        candidate_callback_work=11_000,
        control_stratum_targets=strata,
        candidate_stratum_targets=merge(strata, Dict(first(T0_STRATA) => 0)),
        candidate_strict_guard_safe_full=true,
        candidate_qualified_extreme_barrier_recoveries=1,
        candidate_safety_accounting_budget_exception_count=0,
        mechanism_fixture_tests_passed=true,
        truth_blind_source_audit_passed=true,
    )
    @test !regressed["passed"]
    @test !regressed["every_predeclared_stratum_noninferior"]

    @test_throws ArgumentError evaluate_t0_gate(
        control_targets=4,
        candidate_targets=5,
        control_safe_full=2,
        candidate_safe_full=3,
        control_callback_work=10_000,
        candidate_callback_work=11_000,
        control_stratum_targets=Dict("not-a-stratum" => 1),
        candidate_stratum_targets=strata,
        candidate_strict_guard_safe_full=true,
        candidate_qualified_extreme_barrier_recoveries=1,
        candidate_safety_accounting_budget_exception_count=0,
        mechanism_fixture_tests_passed=true,
        truth_blind_source_audit_passed=true,
    )

    no_guard = evaluate_t0_gate(
        control_targets=4,
        candidate_targets=5,
        control_safe_full=2,
        candidate_safe_full=3,
        control_callback_work=10_000,
        candidate_callback_work=11_000,
        control_stratum_targets=strata,
        candidate_stratum_targets=strata,
        candidate_strict_guard_safe_full=false,
        candidate_qualified_extreme_barrier_recoveries=0,
        candidate_safety_accounting_budget_exception_count=0,
        mechanism_fixture_tests_passed=true,
        truth_blind_source_audit_passed=true,
    )
    @test !no_guard["passed"]
    @test !no_guard["strict_guard_mechanism_gate"]
end

@testset "T0 corpus, controls, runner, and preregistration are frozen before outcome" begin
    problems = t0_problems()
    @test length(problems) == 6
    @test count(problem -> problem.family_id == "MULTIROOT-WARPED", problems) == 2
    @test count(problem -> problem.family_id == "STRICT-GUARD-BOUNDARY", problems) == 1
    @test sum(length(problem.gold_targets) for problem in problems) == 11
    @test all(verify_replay_material, problems)
    @test Set(problem.instance_id for problem in problems) == Set(keys(T0_EXPECTED_REPLAY))
    @test all(
        problem -> replay_checksum(problem) == T0_EXPECTED_REPLAY[problem.instance_id],
        problems,
    )
    @test Tuple(variant.name for variant in variants()) == (
        "prod-tol-120x600",
        "prod-options-250x2000",
        "ORTHOMADS-EB",
    )
    @test CALLBACK_PREFIXES == [600, 1_200, 2_400, 4_800]
    @test RUNNER_ATTEMPT_HARD_LIMIT == 4_800

    tracker = CallbackPrefixTracker(CALLBACK_PREFIXES)
    @test isempty(record_attempt!(tracker, 550, 1))
    @test only(record_attempt!(tracker, 100, 2)).threshold == 600
    @test [entry.threshold for entry in record_attempt!(tracker, 2_000, 3)] == [1_200, 2_400]
    @test only(record_attempt!(tracker, 2_150, 4)).threshold == 4_800
    @test tracker_complete(tracker)

    runner_source = read(joinpath(TEST_EXPERIMENT_ROOT, "run_t0.jl"), String)
    @test Meta.parseall(runner_source) isa Expr
    @test occursin("representative_problems", runner_source)
    @test occursin("_suffix_stable_assessor_work_from_sequence", runner_source)
    @test occursin("right_censored_assessor_safe_full_work", runner_source)
    @test occursin("raw-common-assessor-attempt-fields-not-lab-safe-full-field", runner_source)
    @test !occursin("_suffix_stable_evaluations_to_lab_safe_full", runner_source)
    @test occursin("core_lmqr_control(:prod_tol_120x600)", runner_source)
    @test occursin("core_lmqr_control(:prod_options_250x2000)", runner_source)
    @test occursin("orthomads_variant()", runner_source)
    @test occursin("clean committed worktree", runner_source)
    @test occursin("BLAS.get_num_threads() == 1", runner_source)

    preregistration_path = joinpath(TEST_EXPERIMENT_ROOT, "preregistration.json")
    preregistration = JSON3.read(read(preregistration_path, String), Dict{String,Any})
    @test preregistration["state"] == "preregistered-no-outcome"
    @test preregistration["candidate"] == "ORTHOMADS-EB"
    @test preregistration["algorithm"]["search"] == "disabled"
    @test preregistration["algorithm"]["surrogate"] == "disabled"
    @test preregistration["algorithm"]["tuning_rounds"] == 0
    @test preregistration["t0"]["case_count"] == 6
    @test preregistration["t0"]["target_count"] == 11
    @test length(preregistration["t0"]["instances"]) == 6
    @test preregistration["t0"]["case_cumulative_callback_prefixes"] ==
          [600, 1200, 2400, 4800]
    @test preregistration["promotion_gate"]["exact_strata"] == collect(T0_STRATA)
    @test preregistration["promotion_gate"]["minimum_qualified_extreme_barrier_recoveries"] == 1
    contract = promotion_gate_contract()
    @test contract["path_a"]["maximum_work_ratio"] == 1.2
    @test contract["path_b"]["maximum_work_ratio"] == 0.8
    @test contract["exact_strata"] == collect(T0_STRATA)
    @test !isfile(joinpath(TEST_EXPERIMENT_ROOT, "t0-decision.json"))
    @test !isdir(joinpath(TEST_EXPERIMENT_ROOT, "results"))
end
