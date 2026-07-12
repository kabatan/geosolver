using GeoTargetBenchmarks
using Test

include(joinpath(@__DIR__, "..", "run_t0.jl"))
using .ExperimentLocal009
using .ExperimentLocal009T0Policy

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

@testset "frozen truth-blind candidate configuration" begin
    variant = restoring_gn_variant()
    @test variant.name == VARIANT_NAME
    config = variant.configuration
    @test config.coordinate_map == "direct-midpoint-half-range-normalized-box"
    @test config.residual_scaling == "declared"
    @test occursin("forward-one-sided", config.derivative)
    @test occursin("cpqr", config.linear_step)
    @test occursin("armijo", config.globalization)
    @test config.invalid_trial_policy ==
          "charged-reject-and-backtrack-without-pseudoresidual"
    @test config.fallback == "none"
    @test !config.identity_routing
    @test config.max_evaluations == 600
    @test config.max_iterations == 120

    source = read(joinpath(@__DIR__, "..", "src", "ExperimentLocal009.jl"), String)
    for forbidden in (
        "family_id",
        "instance_id",
        "gold_configurations",
        "gold_targets",
        "primitive_name",
        "plugin_id",
    )
        @test !occursin(forbidden, source)
    end
    @test !occursin("core_lmqr", source)
    @test !occursin("scipy", lowercase(source))

    @test_throws ArgumentError restoring_gn_variant(max_iterations=0)
    @test_throws ArgumentError restoring_gn_variant(max_evaluations=0)
    @test_throws ArgumentError restoring_gn_variant(backtrack_factor=1.0)
    @test_throws ArgumentError restoring_gn_variant(armijo_coefficient=0.0)
    @test_throws ArgumentError restoring_gn_variant(model_ratio_floor=1.0)
end

@testset "regular solve, declared residual scaling and callback ledger" begin
    calls = Ref(0)
    case = fixture_case(
        2,
        2,
        [-2.0, -2.0],
        [2.0, 2.0],
        [2.0, 0.5],
        input -> [2.0 * (input[1] - 0.25), 0.5 * (input[2] + 0.75)];
        calls,
    )
    outcome = restoring_gn_variant(max_evaluations=100).run(case, [1.5, 1.0])
    @test outcome.status == STATUS_CONVERGED
    @test outcome.reported_converged
    @test outcome.reported_accepted
    @test collect(outcome.endpoint) ≈ [0.25, -0.75] atol=1.0e-9
    @test outcome.evaluations == calls[] <= 100
    fields = diagnostic_fields(outcome.diagnostic)
    @test parse(Int, fields["callbacks"]) == outcome.evaluations
    @test parse(Int, fields["accepted_steps"]) >= 1
    @test fields["oracle_exceptions"] == "0"
end

@testset "initial semantic restoration uses only the box-center segment" begin
    calls = Ref(0)
    case = fixture_case(
        1,
        1,
        [-1.0],
        [1.0],
        [1.0],
        input -> [input[1] - 0.5];
        semantics=input -> input[1] > -0.2,
        calls,
    )
    outcome = restoring_gn_variant(max_evaluations=100).run(case, [-0.8])
    @test outcome.status == STATUS_CONVERGED
    @test only(outcome.endpoint) ≈ 0.5 atol=1.0e-9
    @test outcome.evaluations == calls[]
    fields = diagnostic_fields(outcome.diagnostic)
    @test parse(Int, fields["restored_starts"]) == 1
    @test parse(Int, fields["restoration_trials"]) > 1
    @test parse(Int, fields["restoration_invalid_trials"]) > 0

    midpoint_invalid = fixture_case(
        1,
        1,
        [-1.0],
        [1.0],
        [1.0],
        input -> [input[1] - 0.9];
        semantics=input -> input[1] > 0.8,
    )
    failed = restoring_gn_variant(max_evaluations=20).run(midpoint_invalid, [-0.8])
    @test failed.status == STATUS_INITIAL_INFEASIBLE
    @test failed.evaluations == 2
    @test !failed.reported_accepted
end

@testset "one-sided FD reverses sign after a charged domain exception" begin
    calls = Ref(0)
    evaluator = function (input)
        calls[] += 1
        input[1] > 0 || error("fixture domain violation")
        return SolverCaseEvaluation((input[1] - 0.5,), input[1], true, true)
    end
    case = SolverExperimentCase(
        1,
        1,
        (-1.0,),
        (1.0,),
        (1.0,),
        (1.0,),
        evaluator,
    )
    outcome = restoring_gn_variant(max_evaluations=100).run(case, [1.0e-7])
    @test outcome.status == STATUS_CONVERGED
    @test only(outcome.endpoint) ≈ 0.5 atol=1.0e-9
    @test outcome.evaluations == calls[]
    fields = diagnostic_fields(outcome.diagnostic)
    @test parse(Int, fields["oracle_exceptions"]) >= 1
    @test parse(Int, fields["fd_invalid_trials"]) >= 1
    @test parse(Int, fields["fd_sign_reversals"]) >= 1
end

@testset "invalid full steps are rejected and restored by backtracking" begin
    calls = Ref(0)
    case = fixture_case(
        1,
        1,
        [-2.0],
        [2.0],
        [1.0],
        input -> [(input[1] - 0.2) * exp(-input[1])];
        semantics=input -> input[1] > 0.1,
        calls,
    )
    outcome = restoring_gn_variant(max_evaluations=200).run(case, [1.0])
    @test outcome.status == STATUS_CONVERGED
    @test only(outcome.endpoint) ≈ 0.2 atol=1.0e-8
    @test outcome.evaluations == calls[]
    fields = diagnostic_fields(outcome.diagnostic)
    @test parse(Int, fields["invalid_line_search_trials"]) >= 1
    @test parse(Int, fields["accepted_steps"]) >= 1
end

@testset "CPQR rank truncation and rank-zero safeguard" begin
    rank_one = fixture_case(
        2,
        2,
        [-2.0, -2.0],
        [2.0, 2.0],
        [1.0, 1.0],
        input -> [input[1] + input[2] - 1.0, 2.0 * (input[1] + input[2] - 1.0)],
    )
    outcome = restoring_gn_variant(max_evaluations=100).run(rank_one, [0.0, 0.0])
    @test outcome.status == STATUS_CONVERGED
    @test sum(outcome.endpoint) ≈ 1.0 atol=1.0e-8
    @test diagnostic_fields(outcome.diagnostic)["last_rank"] == "1"

    constant = fixture_case(
        2,
        2,
        [-1.0, -1.0],
        [1.0, 1.0],
        [1.0, 1.0],
        input -> [1.0, -1.0],
    )
    stalled = restoring_gn_variant(max_evaluations=20).run(constant, [0.0, 0.0])
    @test stalled.status == STATUS_RANK_STALLED
    @test !stalled.reported_accepted
    @test stalled.evaluations == 3
end

@testset "candidate hard cap never overdraws" begin
    calls = Ref(0)
    case = fixture_case(
        2,
        2,
        [-1.0, -1.0],
        [1.0, 1.0],
        [1.0, 1.0],
        input -> [input[1] - 0.25, input[2] + 0.25];
        calls,
    )
    outcome = restoring_gn_variant(max_evaluations=2).run(case, [0.0, 0.0])
    @test outcome.status == STATUS_MAX_EVALUATIONS
    @test outcome.evaluations == calls[] == 2
    @test !outcome.reported_accepted
end

function assessor_attempt(
    start_index,
    target,
    evaluations;
    qualified=true,
    gold=true,
    ambiguous=false,
)
    return (;
        start_index,
        evaluations,
        assessor_qualified=qualified,
        assessor_gold_matched=gold,
        assessor_target_ambiguous=ambiguous,
        assessor_matched_target_id=target,
    )
end

@testset "common-assessor suffix-stable work and right censoring" begin
    reached = [
        assessor_attempt(1, "target-a", 100),
        assessor_attempt(2, "target-b", 200),
    ]
    @test _suffix_stable_assessor_work_from_sequence(reached, 2) == 300

    later_unqualified = [
        reached...,
        assessor_attempt(3, nothing, 50; qualified=false, gold=false),
    ]
    @test _suffix_stable_assessor_work_from_sequence(later_unqualified, 2) == 300

    later_inconsistent = [
        reached...,
        assessor_attempt(3, nothing, 50; qualified=true, gold=false),
    ]
    @test _suffix_stable_assessor_work_from_sequence(later_inconsistent, 2) === nothing

    observed = _right_censored_assessor_work(300, 4_800)
    @test observed == (work=300, event=true)
    @test _right_censored_assessor_work(5_100, 4_800) == (work=4_800, event=false)
    @test _right_censored_assessor_work(nothing, 4_800) ==
          (work=4_800, event=false)
    @test_throws ArgumentError _right_censored_assessor_work(1, 0)

    recovered = (;
        assessor_qualified=true,
        assessor_gold_matched=true,
        assessor_target_ambiguous=false,
        diagnostic="restored_starts=0;fd_sign_reversals=1;invalid_line_search_trials=0",
    )
    @test _diagnostic_integer(recovered.diagnostic, "fd_sign_reversals") == 1
    @test _qualified_invalid_trial_recoveries([recovered]) == 1
end

function gate_fixture(;
    candidate_targets=5,
    candidate_safe_full=4,
    candidate_work=1_100.0,
    stratum_delta=0,
    guard_safe=true,
    recoveries=1,
    violations=0,
)
    control_strata = Dict(stratum => 1 for stratum in T0_STRATA)
    candidate_strata = Dict(stratum => 1 for stratum in T0_STRATA)
    candidate_strata[first(T0_STRATA)] += stratum_delta
    return evaluate_promotion_gate(;
        control_targets=4,
        candidate_targets,
        control_safe_full=3,
        candidate_safe_full,
        control_right_censored_assessor_work=1_000.0,
        candidate_right_censored_assessor_work=candidate_work,
        control_stratum_targets=control_strata,
        candidate_stratum_targets=candidate_strata,
        candidate_strict_guard_safe_full=guard_safe,
        candidate_qualified_invalid_trial_recoveries=recoveries,
        candidate_safety_accounting_budget_exception_count=violations,
    )
end

@testset "prospective T0 promotion gate" begin
    path_a = gate_fixture()
    @test path_a["passed"]
    @test path_a["path_a"]
    @test !path_a["path_b"]
    @test path_a["right_censored_assessor_work_ratio"] == 1.1
    path_b = gate_fixture(candidate_targets=4, candidate_safe_full=3, candidate_work=800)
    @test path_b["passed"]
    @test !path_b["path_a"]
    @test path_b["path_b"]
    @test !gate_fixture(
        candidate_targets=4,
        candidate_safe_full=3,
        candidate_work=801,
    )["passed"]
    @test !gate_fixture(candidate_work=1_201.0)["passed"]
    @test !gate_fixture(stratum_delta=-1)["passed"]
    @test !gate_fixture(guard_safe=false)["passed"]
    @test !gate_fixture(recoveries=0)["passed"]
    @test !gate_fixture(violations=1)["passed"]
    contract = promotion_gate_contract()
    @test contract["final_callback_prefix"] == 4_800
    @test contract["path_a"]["maximum_right_censored_work_ratio"] == 1.20
    @test contract["path_b"]["maximum_right_censored_work_ratio"] == 0.80
    @test occursin("common-assessor", contract["primary_work"])
    @test contract["tuning_rounds"] == 0

    missing = Dict(stratum => 1 for stratum in T0_STRATA)
    pop!(missing, last(T0_STRATA))
    complete = Dict(stratum => 1 for stratum in T0_STRATA)
    @test_throws ArgumentError evaluate_promotion_gate(;
        control_targets=4,
        candidate_targets=5,
        control_safe_full=3,
        candidate_safe_full=4,
        control_right_censored_assessor_work=1_000,
        candidate_right_censored_assessor_work=1_000,
        control_stratum_targets=missing,
        candidate_stratum_targets=complete,
        candidate_strict_guard_safe_full=true,
        candidate_qualified_invalid_trial_recoveries=1,
        candidate_safety_accounting_budget_exception_count=0,
    )
end

@testset "frozen six-case T0 runner and paired-start contract" begin
    problems = t0_problems()
    @test length(problems) == 6
    @test all(problem -> size(problem.saved_starts, 2) == 512, problems)
    @test sum(length(problem.gold_targets) for problem in problems) == 11
    @test count(problem -> problem.family_id == "MULTIROOT-WARPED", problems) == 2
    @test count(problem -> problem.family_id == "STRICT-GUARD-BOUNDARY", problems) == 1
    expected = Dict(
        "curved-chain-d4-curve10000.0-i102-s1002" =>
            "8a56042f6ddef9cc097cd1f13fe22b3eb1f376e4ed6a13b7cd70a16f0e566d74",
        "near-rank-d4-ratio1.0e-8-o103-s1003" =>
            "a55330b98965a2a65dc18d93955458ec88b34e14445cff69ff830db028552145",
        "tangent-circle-r1.0-ratio0.999999-i105-s1005" =>
            "0eab38a9ca7da57f68106a9daeb24f06122433b60362f01b3dafe157e3d557ac",
        "multiroot-d4-n4-sep0.001-condition10000.0-warp0.5-targetz1-c106-s1006" =>
            "3e012859175cd8291ffd03db916e618142f449df8a7aa03f1c0c7fe7159b48c9",
        "multiroot-d4-n4-sep0.001-condition10000.0-warp0.5-targetz1_squared-c106-s1006" =>
            "1fce84f2621b79af38bef92cd519f1569691f8bd22c6988bf9bde413d81f2cee",
        "strict-guard-on_boundary-margin0.0-i108-s1008" =>
            "8a3ae1e490fa272ca26b5903b8ff7d956ceb15eaf41d13e526676e71f42cbc13",
    )
    @test Set(problem.instance_id for problem in problems) == Set(keys(expected))
    @test all(problem -> replay_checksum(problem) == expected[problem.instance_id], problems)
    @test Tuple(variant.name for variant in variants()) ==
          ("prod-tol-120x600", "prod-options-250x2000", VARIANT_NAME)

    tracker = CallbackPrefixTracker()
    @test isempty(record_attempt!(tracker, 599, 1))
    first_crossing = only(record_attempt!(tracker, 2, 2))
    @test first_crossing.threshold == 600
    @test first_crossing.overshoot == 1

    parsed = parse_arguments(["--shard-index=1", "--shard-count=2", "--output=x"])
    @test parsed[:shard_index] == 1
    @test parsed[:shard_count] == 2
    @test_throws ErrorException parse_arguments(["--shard-count=7"])
    @test_throws ErrorException parse_arguments(["--max-starts=8"])

    preregistration = read(PREREGISTRATION_PATH, String)
    @test occursin("\"state\": \"preregistered-no-outcome\"", preregistration)
    @test occursin("\"outcome_execution_authorized\": false", preregistration)
    @test occursin("\"case_count\": 6", preregistration)
    @test occursin("\"paired_start_count_per_case\": 512", preregistration)
    @test occursin("\"callback_prefixes\": [600, 1200, 2400, 4800]", preregistration)
    @test occursin("suffix-stable common-assessor safe-full", preregistration)
    @test occursin("\"path_a\"", preregistration)
    @test occursin("\"path_b\"", preregistration)
    @test occursin("\"tuning_rounds\": 0", preregistration)

    runner = read(joinpath(@__DIR__, "..", "run_t0.jl"), String)
    @test isdefined(Main, :canonical_json)
    @test occursin("T0 requires a clean committed worktree", runner)
    @test occursin("case-cumulative-observed-callbacks", runner)
    @test occursin("_suffix_stable_evaluations_to_lab_safe_full", runner)
    @test occursin("_suffix_stable_evaluations_to_assessor_safe_full", runner)
    @test occursin("right_censored_assessor_safe_full_work", runner)
    @test occursin("qualified_invalid_trial_recoveries", runner)
    @test occursin("diagnostic-only-not-gate-authority", runner)
    @test !isdir(joinpath(@__DIR__, "..", "results"))
end
