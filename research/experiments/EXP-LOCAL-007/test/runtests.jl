using GeoTargetBenchmarks
using Test

const REPOSITORY_ROOT = normpath(joinpath(@__DIR__, "..", "..", "..", ".."))

include(joinpath(@__DIR__, "..", "run_t2.jl"))
using .ExperimentLocal007
using .ExperimentLocal007T1Policy
using .ExperimentLocal007T2Corpus
using .ExperimentLocal007T2Policy

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

function t2_gate_fixture(;
    candidate_safe_delta=0.0,
    improved_families=String[],
    candidate_work_ratio=0.7,
    critical_delta=0.0,
    safety_violation_count=0,
    nonsquare_violation_count=0,
)
    families = collect(T2_APPLICABLE_FAMILIES)
    control_safe = Dict(family => 0.5 for family in families)
    candidate_safe = Dict(
        family => control_safe[family] +
                  (family in improved_families ? candidate_safe_delta : 0.0) for
        family in families
    )
    control_work = Dict(family => 100.0 for family in families)
    candidate_work = Dict(family => 100.0 * candidate_work_ratio for family in families)
    control_critical = Dict(stratum => 0.5 for stratum in T2_CRITICAL_STRATA)
    candidate_critical = copy(control_critical)
    candidate_critical[first(T2_CRITICAL_STRATA)] += critical_delta
    return evaluate_t2_promotion_gate(;
        control_family_safe_full=control_safe,
        candidate_family_safe_full=candidate_safe,
        control_family_callback_work=control_work,
        candidate_family_callback_work=candidate_work,
        control_critical_safe_full=control_critical,
        candidate_critical_safe_full=candidate_critical,
        control_callback_work=700.0,
        candidate_callback_work=700.0 * candidate_work_ratio,
        candidate_safety_violation_count=safety_violation_count,
        nonsquare_inapplicability_violation_count=nonsquare_violation_count,
    )
end

@testset "lightweight T2 corpus, runner and promotion gate" begin
    problems = t2_problems()
    @test length(problems) == 48
    @test T2_INSTANCES_PER_FAMILY == 6
    @test T2_START_COUNT == 32
    @test T2_START_PREFIXES == (8, 16, 32)
    @test validate_t2_grid(problems)
    @test validate_t2_corpus_checksum(problems) == T2_CORPUS_SHA256
    @test validate_t2_historical_records(problems) == T2_HISTORICAL_MANIFEST_SHA256
    @test count(p -> p.dimension == p.residual_dimension, problems) == 42
    @test count(p -> p.dimension != p.residual_dimension, problems) == 6
    @test sum(length(problem.gold_targets) for problem in problems) == 88
    @test [only(shard_problems(problems, index, 48)).instance_id for index in 0:47] ==
          [problem.instance_id for problem in problems]

    mktempdir() do directory
        output = joinpath(directory, "shard.json")
        parsed = parse_t2_arguments([
            "--shard-index=47",
            "--shard-count=48",
            "--output=$output",
        ])
        @test parsed[:shard_index] == 47
        @test parsed[:shard_count] == 48
        @test parsed[:output] == output
    end
    @test_throws ErrorException parse_t2_arguments(String[])
    @test_throws ErrorException parse_t2_arguments(["--shard-index=48", "--output=x"])
    @test_throws ErrorException parse_t2_arguments([
        "--shard-index=0",
        "--shard-count=47",
        "--output=x",
    ])
    @test Tuple(variant.name for variant in t2_variants()) ==
          ("prod-tol-120x600", "prod-options-250x2000", "SCIPY-HYBR")

    families = collect(T2_APPLICABLE_FAMILIES)
    path_a = t2_gate_fixture(
        candidate_safe_delta=0.2,
        improved_families=families[1:3],
        candidate_work_ratio=1.0,
    )
    @test path_a["performance_path_a"]
    @test length(path_a["path_a_supporting_families"]) == 3
    @test path_a["passed"]
    path_b = t2_gate_fixture(candidate_work_ratio=0.79)
    @test path_b["performance_path_b"]
    @test path_b["passed"]
    @test t2_promotion_gate_contract()["callback_work_miss_value"] == 4_800
    @test !t2_gate_fixture(
        candidate_work_ratio=0.79,
        critical_delta=-0.03,
    )["passed"]
    @test !t2_gate_fixture(
        candidate_work_ratio=0.79,
        safety_violation_count=1,
    )["passed"]
    @test !t2_gate_fixture(
        candidate_work_ratio=0.79,
        nonsquare_violation_count=1,
    )["passed"]

    preregistration = parse_protocol_json(read(T2_PREREGISTRATION_PATH, String))
    @test preregistration["state"] == "preregistered-no-outcome"
    @test preregistration["corpus"]["corpus_sha256"] == T2_CORPUS_SHA256
    @test preregistration["execution"]["maximum_concurrent_processes"] == 16
    @test preregistration["execution"]["saved_start_prefixes"] == [8, 16, 32]
    @test !isfile(joinpath(@__DIR__, "..", "formal-environment.json"))
    @test !isfile(joinpath(@__DIR__, "..", "run_t2_formal.py"))
end

function fixture_t2_variant(name; inapplicable=false)
    return SolverVariant(name, (case, start) -> SolverAttemptOutcome(
        nothing;
        status=inapplicable ? "INAPPLICABLE_NONSQUARE" : "FIXTURE_NO_ENDPOINT",
        evaluations=0,
    ))
end

@testset "T2 one-case paired-start and typed nonsquare contract" begin
    problem = generate(RedundantOverdeterminedParams(
        dimension=2,
        redundancy=1,
        dependency_error=0.0,
        dependency_seed=91_001,
        start_seed=91_002,
        start_count=32,
    ))
    fixture_variants = SolverVariant[
        fixture_t2_variant("prod-tol-120x600"),
        fixture_t2_variant("prod-options-250x2000"),
        fixture_t2_variant("SCIPY-HYBR"; inapplicable=true),
    ]
    run = run_solver_experiment(
        [problem],
        fixture_variants;
        prefixes=T2_START_PREFIXES,
        evaluation_limit=T2_RUNNER_EVALUATION_LIMIT,
    )
    contract = validate_t2_shard_contract(run)
    @test contract["attempt_count"] == contract["pairing_count"] == 96
    @test contract["summary_count"] == 9
    @test contract["all_variant_accounting_valid"]
    document = solver_experiment_document(run)
    attach_t2_assessor_work!(document, problem, fixture_variants, run.attempts)
    @test all(
        summary -> summary["right_censored_assessor_safe_full_work"] == 4_800,
        filter(summary -> summary["prefix"] == 32, document["summaries"]),
    )
    @test all(
        summary -> summary["assessor_safe_full_event_by_4800"] == false,
        filter(summary -> summary["prefix"] == 32, document["summaries"]),
    )
    @test all(
        summary -> !haskey(summary, "right_censored_assessor_safe_full_work"),
        filter(summary -> summary["prefix"] != 32, document["summaries"]),
    )
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

@testset "common-assessor suffix work and right censoring" begin
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
    late = _right_censored_assessor_work(5_100, 4_800)
    @test late == (work=4_800, event=false)
    miss = _right_censored_assessor_work(nothing, 4_800)
    @test miss == (work=4_800, event=false)
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

@testset "EXP-LOCAL-007 pinned truth-blind square HYBRD candidate" begin
    @test ExperimentLocal007._package_version() == SCIPY_VERSION == "1.18.0"
    @test ExperimentLocal007.PythonCall.python_executable_path() == PYTHON_EXECUTABLE
    source = read(joinpath(@__DIR__, "..", "src", "ExperimentLocal007.jl"), String)
    bridge = read(
        joinpath(@__DIR__, "..", "python", "geotarget_scipy_hybr_bridge.py"),
        String,
    )
    for forbidden in ("family_id", "instance_id", "gold_configurations", "gold_targets")
        @test !occursin(forbidden, source)
        @test !occursin(forbidden, bridge)
    end
    @test occursin("method=\"hybr\"", bridge)
    @test !occursin("least_squares", bridge)
    variant = scipy_hybr_variant()
    @test variant.name == "SCIPY-HYBR"
    config = variant.configuration
    @test config.package_version == "1.18.0"
    @test config.applicability == "residual_dimension==dimension"
    @test config.nonsquare_policy == "typed-inapplicable-zero-callbacks"
    @test config.residual_scaling == "declared"
    @test config.max_callbacks == 600
    @test config.algorithm_callback_limit == 599
    @test config.endpoint_screen_reservation == 1
    @test config.all_callbacks_charged
    @test config.scipy_success_role == "diagnostic-only"
    @test !config.identity_routing
    @test_throws ArgumentError scipy_hybr_variant(max_callbacks=1)

    nonsquare_calls = Ref(0)
    nonsquare = fixture_case(
        2,
        3,
        [-1.0, -1.0],
        [1.0, 1.0],
        [1.0, 1.0, 1.0],
        input -> [input[1], input[2], input[1] + input[2]];
        calls=nonsquare_calls,
    )
    outcome = variant.run(nonsquare, [0.25, -0.25])
    @test outcome.status == "INAPPLICABLE_NONSQUARE"
    @test outcome.endpoint === nothing
    @test outcome.evaluations == nonsquare_calls[] == 0
    @test occursin("inapplicable-residual-dimension", outcome.diagnostic)
end

@testset "fixed tanh and atanh boundary policy" begin
    case = fixture_case(
        2,
        2,
        [-4.0, -2.0],
        [8.0, 6.0],
        [1.0, 1.0],
        input -> input,
    )
    bounds, unconstrained, normalized = ExperimentLocal007._bounds_map(case, [8.0, -2.0])
    @test normalized == [1.0, -1.0]
    @test unconstrained[1] == atanh(1.0 - BOUNDARY_INTERIOR_MARGIN)
    @test unconstrained[2] == atanh(-1.0 + BOUNDARY_INTERIOR_MARGIN)
    physical, mapped = ExperimentLocal007._physical_coordinates(bounds, unconstrained)
    @test all(-1.0 .< mapped .< 1.0)
    @test all(bounds.lower .< physical .< bounds.upper)
    @test ExperimentLocal007._open_tanh(1.0e6) == UPPER_OPEN_UNIT
    @test ExperimentLocal007._open_tanh(-1.0e6) == LOWER_OPEN_UNIT
    @test_throws ArgumentError ExperimentLocal007._bounds_map(case, [9.0, 0.0])
end

@testset "regular, declared scaling, and callback reconciliation" begin
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
    outcome = scipy_hybr_variant(max_callbacks=200).run(regular, [5.0, 3.0])
    @test outcome.endpoint !== nothing
    @test collect(outcome.endpoint) ≈ [1.0, -0.5] atol=2.0e-9
    @test outcome.reported_converged
    @test outcome.reported_accepted
    @test outcome.evaluations == regular_calls[] <= 200
    fields = diagnostic_fields(outcome.diagnostic)
    @test parse(Int, fields["callbacks"]) == outcome.evaluations
    @test parse(Int, fields["residual_callbacks"]) +
          parse(Int, fields["endpoint_screen_callbacks"]) == outcome.evaluations
    @test parse(Int, fields["endpoint_screen_callbacks"]) == 1
    @test parse(Int, fields["scipy_nfev"]) == parse(Int, fields["residual_callbacks"])
    @test fields["screening_accepted"] == "true"

    scaled_calls = Ref(0)
    scaled = fixture_case(
        2,
        2,
        [-2.0, -2.0],
        [2.0, 2.0],
        [1.0e8, 1.0e-8],
        input -> [1.0e8 * (input[1] - 0.25), 1.0e-8 * (input[2] + 0.75)];
        calls=scaled_calls,
    )
    scaled_outcome = scipy_hybr_variant(max_callbacks=200).run(scaled, [-1.0, 1.0])
    @test scaled_outcome.endpoint !== nothing
    @test collect(scaled_outcome.endpoint) ≈ [0.25, -0.75] atol=2.0e-9
    @test scaled_outcome.reported_accepted
    @test scaled_outcome.evaluations == scaled_calls[]
end

@testset "near-rank square system remains an ordinary numeric input" begin
    calls = Ref(0)
    near_rank = fixture_case(
        2,
        2,
        [-2.0, -2.0],
        [2.0, 2.0],
        [1.0, 1.0],
        input -> begin
            dx = input[1] - 0.2
            dy = input[2] + 0.3
            [dx + dy, dx + (1.0 + 1.0e-6) * dy]
        end;
        calls,
    )
    outcome = scipy_hybr_variant(max_callbacks=200).run(near_rank, [1.0, -1.0])
    @test outcome.endpoint !== nothing
    @test collect(outcome.endpoint) ≈ [0.2, -0.3] atol=2.0e-7
    @test outcome.reported_accepted
    @test outcome.evaluations == calls[]
    @test !occursin("inapplicable", outcome.status)
end

@testset "invalid, nonfinite, and throwing trials are charged and fail closed" begin
    semantic_calls = Ref(0)
    semantic_case = fixture_case(
        1,
        1,
        [-1.0],
        [1.0],
        [1.0],
        input -> [input[1] - 0.25];
        semantics=input -> input[1] > 0.0,
        calls=semantic_calls,
    )
    invalid = scipy_hybr_variant(max_callbacks=50).run(semantic_case, [-0.5])
    @test invalid.endpoint === nothing
    @test startswith(invalid.status, "exception:")
    @test invalid.evaluations == semantic_calls[] == 1
    invalid_fields = diagnostic_fields(invalid.diagnostic)
    @test invalid_fields["invalid_algorithm_callbacks"] == "1"
    @test invalid_fields["semantic_invalid_callbacks"] == "1"

    nonfinite_calls = Ref(0)
    nonfinite_case = fixture_case(
        1,
        1,
        [-1.0],
        [1.0],
        [1.0],
        input -> [NaN];
        calls=nonfinite_calls,
    )
    nonfinite = scipy_hybr_variant(max_callbacks=50).run(nonfinite_case, [0.0])
    @test nonfinite.endpoint === nothing
    @test nonfinite.evaluations == nonfinite_calls[] == 1
    nonfinite_fields = diagnostic_fields(nonfinite.diagnostic)
    @test nonfinite_fields["nonfinite_callbacks"] == "1"
    @test nonfinite_fields["invalid_algorithm_callbacks"] == "1"

    throwing_calls = Ref(0)
    throwing_case = fixture_case(
        1,
        1,
        [-1.0],
        [1.0],
        [1.0],
        input -> error("fixture domain failure");
        calls=throwing_calls,
    )
    throwing = scipy_hybr_variant(max_callbacks=50).run(throwing_case, [0.0])
    @test throwing.endpoint === nothing
    @test throwing.evaluations == throwing_calls[] == 1
    throwing_fields = diagnostic_fields(throwing.diagnostic)
    @test throwing_fields["oracle_exceptions"] == "1"
    @test occursin("fixture domain failure", throwing.diagnostic)
end

@testset "external hard caps and endpoint screen reservation" begin
    calls = Ref(0)
    impossible = fixture_case(
        1,
        1,
        [-2.0],
        [2.0],
        [1.0],
        input -> [1.0];
        calls,
    )
    exhausted = scipy_hybr_variant(max_callbacks=4).run(impossible, [0.0])
    @test exhausted.status == "LOCAL_MAX_EVALUATIONS"
    @test exhausted.evaluations == calls[] == 3
    exhausted_fields = diagnostic_fields(exhausted.diagnostic)
    @test exhausted_fields["algorithm_callback_limit"] == "3"
    @test exhausted_fields["endpoint_screen_callbacks"] == "0"

    outside_calls = Ref(0)
    outside_root = fixture_case(
        1,
        1,
        [-1.0],
        [1.0],
        [1.0],
        input -> [input[1] - 2.0];
        calls=outside_calls,
    )
    bounded = scipy_hybr_variant(max_callbacks=100).run(outside_root, [0.5])
    @test bounded.endpoint !== nothing
    @test -1.0 <= only(bounded.endpoint) <= 1.0
    @test !bounded.reported_accepted
    @test bounded.evaluations == outside_calls[]
    @test occursin("screening_accepted=false", bounded.diagnostic)

    problem = first(GeoTargetSolverLab.representative_problems(start_count=1))
    run = run_solver_experiment(
        [problem],
        [scipy_hybr_variant(max_callbacks=50)];
        prefixes=[1],
        evaluation_limit=3,
    )
    attempt = only(run.attempts)
    @test attempt.status == "runner_evaluation_budget_exhausted"
    @test attempt.budget_exhausted
    @test attempt.evaluations == attempt.reported_evaluations == 3
    @test !attempt.evaluation_count_mismatch
end

@testset "case-cumulative runner, clean provenance, and sharding contract" begin
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
    @test occursin("verify_replay_material", runner)
    @test occursin("_suffix_stable_evaluations_to_lab_safe_full", runner)
    @test occursin("formal T0 requires a clean committed worktree", runner)
    @test occursin("BLAS.get_num_threads() == 1", runner)
    @test occursin("RUNNER_ATTEMPT_HARD_LIMIT", runner)
    @test occursin("overshoot_callbacks", runner)
    @test occursin("single-stream-attempt-boundary-snapshots-no-reruns", runner)
    @test !isdir(joinpath(@__DIR__, "..", "results"))
end

@testset "audited T0 decision and representative-nine T1 freeze" begin
    decision = read(joinpath(@__DIR__, "..", "t0-decision.json"), String)
    @test occursin("949386bf4b89fe500cb0790d299e4cfc89d9f1ae", decision)
    @test occursin("e4353b76ca716bd02164fbbfaff584f80a10b0cf5106bd68e3dec07c2a998d3b", decision)
    @test occursin("896cba794bb6968ac6296a452bf295eb1472a93aefaeb2b5ceab844d3e525d21", decision)
    @test occursin("\"callback_work_ratio\": 0.9608874475994622", decision)
    @test occursin("\"passed\": true", decision)
    @test occursin("advance-scipy-hybr-to-preregistered-t1", decision)

    preregistration = read(
        joinpath(@__DIR__, "..", "t1-preregistration.json"),
        String,
    )
    @test occursin("\"state\": \"preregistered-no-outcome\"", preregistration)
    @test occursin("\"case_count\": 9", preregistration)
    @test occursin("\"callback_prefixes\": [600, 1200, 2400, 4800]", preregistration)
    @test occursin("\"minimum_family_equal_safe_full_delta\": 0.05", preregistration)
    @test occursin("\"minimum_family_equal_safe_full_delta\": -0.01", preregistration)
    @test occursin("\"minimum_critical_stratum_safe_full_delta\": -0.02", preregistration)
    @test occursin("\"minimum_unrelated_supporting_families\": 3", preregistration)
    @test occursin("INAPPLICABLE_NONSQUARE", preregistration)
    @test occursin("candidate streams across all applicable cases", preregistration)
    @test occursin("control violations affect control safe-full", preregistration)
    @test occursin("suffix-stable common-assessor safe-full callback work", preregistration)
    @test occursin("miss_or_null=4800", preregistration)
    @test !occursin("t1-decision", preregistration)

    problems = GeoTargetSolverLab.representative_problems(start_count=512)
    @test length(problems) == 9
    @test all(verify_replay_material, problems)
    @test all(problem -> size(problem.saved_starts, 2) == 512, problems)
    square = filter(problem -> problem.dimension == problem.residual_dimension, problems)
    nonsquare = filter(problem -> problem.dimension != problem.residual_dimension, problems)
    @test length(square) == 8
    @test length(nonsquare) == 1
    @test Set(problem.family_id for problem in square) == Set(APPLICABLE_FAMILIES)
    @test Set(problem.family_id for problem in nonsquare) ==
          Set(EXPECTED_INAPPLICABLE_FAMILIES)
    expected = Dict(entry.instance_id => entry for entry in EXPECTED_CORPUS)
    @test Set(problem.instance_id for problem in problems) == Set(keys(expected))
    @test all(
        problem -> replay_checksum(problem) == expected[problem.instance_id].replay_checksum,
        problems,
    )

    runner = read(joinpath(@__DIR__, "..", "run_t1.jl"), String)
    @test Meta.parseall(runner) isa Expr
    @test occursin("representative_problems", runner)
    @test occursin("verify_replay_material", runner)
    @test occursin("_suffix_stable_evaluations_to_lab_safe_full", runner)
    @test occursin("formal T1 requires a clean committed worktree", runner)
    @test occursin("BLAS.get_num_threads() == 1", read(joinpath(@__DIR__, "..", "run_t0.jl"), String))
    @test occursin("typed-inapplicable-zero-callback-terminal", runner)
    @test occursin("threshold_reached", runner)
    @test occursin("single-stream-attempt-boundary-snapshots-no-reruns", runner)
    @test occursin(
        "suffix-stable-assessor-safe-full-callbacks-right-censored-at-4800",
        runner,
    )
    @test occursin("_assessor_metrics", runner)
    @test occursin("right_censored_assessor_safe_full_work", runner)
    @test occursin("assessor_safe_full_event_by_4800", runner)
end

function promotion_fixture(;
    candidate_safe_delta=0.0,
    improved_families=String[],
    candidate_work_ratio=0.7,
    candidate_wall_ratio=1.0,
    critical_delta=0.0,
    safety_violation_count=0,
    wall_confirmation_passed=false,
)
    control_safe = Dict(family => 0.5 for family in APPLICABLE_FAMILIES)
    candidate_safe = Dict(
        family => control_safe[family] +
                  (family in improved_families ? candidate_safe_delta : 0.0) for
        family in APPLICABLE_FAMILIES
    )
    control_work = Dict(family => 100.0 for family in APPLICABLE_FAMILIES)
    candidate_work = Dict(
        family => 100.0 * candidate_work_ratio for family in APPLICABLE_FAMILIES
    )
    control_wall = Dict(family => 10.0 for family in APPLICABLE_FAMILIES)
    candidate_wall = Dict(
        family => 10.0 * candidate_wall_ratio for family in APPLICABLE_FAMILIES
    )
    control_critical = Dict(stratum => 0.5 for stratum in CRITICAL_STRATA)
    candidate_critical = Dict(stratum => 0.5 for stratum in CRITICAL_STRATA)
    candidate_critical[first(CRITICAL_STRATA)] += critical_delta
    return evaluate_promotion_gate(;
        control_family_safe_full=control_safe,
        candidate_family_safe_full=candidate_safe,
        control_family_callback_work=control_work,
        candidate_family_callback_work=candidate_work,
        control_family_end_to_end_wall=control_wall,
        candidate_family_end_to_end_wall=candidate_wall,
        control_critical_safe_full=control_critical,
        candidate_critical_safe_full=candidate_critical,
        control_callback_work=700.0,
        candidate_callback_work=700.0 * candidate_work_ratio,
        control_end_to_end_wall=70.0,
        candidate_end_to_end_wall=70.0 * candidate_wall_ratio,
        safety_violation_count,
        wall_confirmation_passed,
    )
end

@testset "T1-to-T2 numerical promotion gate" begin
    families = collect(APPLICABLE_FAMILIES)
    path_a = promotion_fixture(
        candidate_safe_delta=0.2,
        improved_families=families[1:3],
        candidate_work_ratio=1.0,
    )
    @test path_a["performance_path_a"]
    @test length(path_a["path_a_supporting_families"]) == 3
    @test path_a["passed"]

    path_b = promotion_fixture(candidate_work_ratio=0.79)
    @test path_b["performance_path_b"]
    @test length(path_b["path_b_supporting_families"]) == 7
    @test path_b["passed"]

    unsafe = promotion_fixture(candidate_work_ratio=0.79, safety_violation_count=1)
    @test !unsafe["safety_gate"]
    @test !unsafe["passed"]

    critical_regression = promotion_fixture(
        candidate_work_ratio=0.79,
        critical_delta=-0.03,
    )
    @test !critical_regression["critical_gate"]
    @test !critical_regression["passed"]

    unconfirmed_wall = promotion_fixture(
        candidate_work_ratio=1.0,
        candidate_wall_ratio=0.79,
    )
    @test !unconfirmed_wall["performance_path_b"]
    @test !unconfirmed_wall["passed"]
    confirmed_wall = promotion_fixture(
        candidate_work_ratio=1.0,
        candidate_wall_ratio=0.79,
        wall_confirmation_passed=true,
    )
    @test confirmed_wall["confirmed_wall_efficiency"]
    @test confirmed_wall["performance_path_b"]
    @test confirmed_wall["passed"]

    contract = promotion_gate_contract()
    @test contract["performance_path_a"]["minimum_family_equal_safe_full_delta"] == 0.05
    @test contract["performance_path_b"]["minimum_family_equal_safe_full_delta"] == -0.01
    @test contract["minimum_critical_stratum_safe_full_delta"] == -0.02
    @test contract["minimum_unrelated_supporting_families"] == 3
    @test contract["callback_work_miss_value"] == 4_800
    @test occursin("suffix-stable", contract["callback_work"])
    @test occursin("candidate-only", contract["zero_required_scope"])
    @test contract["actual_tuning_rounds"] == 0

    @test_throws ArgumentError evaluate_promotion_gate(;
        control_family_safe_full=Dict(family => 0.5 for family in APPLICABLE_FAMILIES),
        candidate_family_safe_full=Dict(family => 0.5 for family in APPLICABLE_FAMILIES),
        control_family_callback_work=Dict(family => 100.0 for family in APPLICABLE_FAMILIES),
        candidate_family_callback_work=Dict(family => 100.0 for family in APPLICABLE_FAMILIES),
        control_family_end_to_end_wall=Dict(family => 10.0 for family in APPLICABLE_FAMILIES),
        candidate_family_end_to_end_wall=Dict(family => 10.0 for family in APPLICABLE_FAMILIES),
        control_critical_safe_full=Dict(stratum => 0.5 for stratum in CRITICAL_STRATA),
        candidate_critical_safe_full=Dict(stratum => 0.5 for stratum in CRITICAL_STRATA),
        control_callback_work=701.0,
        candidate_callback_work=700.0,
        control_end_to_end_wall=70.0,
        candidate_end_to_end_wall=70.0,
        safety_violation_count=0,
    )
end
