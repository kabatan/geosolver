using JSON3
using LinearAlgebra
using SHA
using Test

include(joinpath(@__DIR__, "..", "src", "ExperimentSingular001.jl"))
using .ExperimentSingular001

function case_by_id(cases, id)
    return only(filter(case -> case.input.oracle.id == id, cases))
end

include(joinpath(@__DIR__, "test_s4.jl"))

@testset "S4 input scaffold is frozen before mechanism code" begin
    cases = ExperimentSingular001.s4_development_cases()
    @test length(cases) == 36
    @test length(unique(case.generated.input.oracle.metamorphic_group for case in cases)) == 12
    @test all(
        count(
            other -> other.generated.input.oracle.metamorphic_group ==
                     case.generated.input.oracle.metamorphic_group,
            cases,
        ) == 3 for case in cases
    )
    @test count(case -> case.stratum == "isolated-deflation-one", cases) == 15
    @test count(case -> case.stratum == "higher-deflation-depth-controls", cases) == 6
    @test count(case -> case.stratum == "manifold-controls", cases) == 6
    @test count(case -> case.stratum == "inconsistent-nonroots", cases) == 3
    @test count(case -> case.stratum == "regular-close-root-controls", cases) == 6
    @test all(
        count(other -> other.representation == representation, cases) == 12 for
        representation in (
            "orthogonal-variable-and-residual-rotation",
            "independent-signed-variable-and-residual-permutation",
            "equivalent-shared-DAG-reordering",
        )
    )
    @test all(case.generated.input.oracle.analytic_jacobian === nothing for case in cases)
    @test all(
        case.analytic_control.analytic_jacobian !== nothing &&
        case.analytic_control.analytic_second_directional !== nothing for case in cases
    )
    @test all(
        ExperimentSingular001.candidate_input(case) === case.generated.input for case in cases
    )

    for case in cases
        setprecision(BigFloat, 256) do
            input = ExperimentSingular001.candidate_input(case)
            point = BigFloat.(input.endpoint)
            residual = input.oracle.residual(point)
            target = input.oracle.target(point)
            jacobian = case.analytic_control.analytic_jacobian(point)
            direction = fill(inv(sqrt(BigFloat(input.oracle.dimension))), input.oracle.dimension)
            second = case.analytic_control.analytic_second_directional(
                point,
                direction,
                reverse(direction),
            )
            @test size(jacobian) == (input.oracle.residual_dimension, input.oracle.dimension)
            @test length(residual) == input.oracle.residual_dimension
            @test length(second) == input.oracle.residual_dimension
            @test all(isfinite, residual)
            @test all(isfinite, jacobian)
            @test all(isfinite, second)
            @test isfinite(target)
        end
    end

    experiment_directory = normpath(joinpath(@__DIR__, ".."))
    input_document = ExperimentSingular001.s4_development_input_document(
        cases;
        gold_artifact_sha256=repeat("0", 64),
    )
    @test input_document["development_instance_count"] == 36
    @test input_document["metamorphic_group_count"] == 12
    @test input_document["candidate_implementation_present"] == false
    @test input_document["gold_values_embedded"] == false
    @test input_document["locked_inputs_materialized"] == false
    @test input_document["product_connected"] == false
    @test length(input_document["cases"]) == 36
    @test all(!haskey(case_document, "gold_analysis_only") for case_document in input_document["cases"])
    @test input_document["amendment_a1_sha256"] == bytes2hex(sha256(read(
        joinpath(experiment_directory, "s4-protocol-amendment-a1.json"),
    )))
    @test input_document["amendment_a2_sha256"] == bytes2hex(sha256(read(
        joinpath(experiment_directory, "s4-protocol-amendment-a2.json"),
    )))

    gold_document = ExperimentSingular001.s4_development_gold_document(cases)
    @test gold_document["candidate_visible"] == false
    @test length(gold_document["cases"]) == 36
    fold_gold = filter(
        item -> occursin("regular-fold", item["case_id"]),
        gold_document["cases"],
    )
    @test length(fold_gold) == 6
    @test all(length(item["isolated_configurations"]) == 2 for item in fold_gold)
    @test all(length(item["isolated_targets"]) == 2 for item in fold_gold)

    mktempdir() do directory
        source_directory = joinpath(directory, "src")
        mechanism_directory = joinpath(source_directory, "s4")
        mkpath(mechanism_directory)
        @test ExperimentSingular001._assert_s4_preimplementation_state(
            ; source_directory,
        ) === nothing
        write(joinpath(mechanism_directory, "candidate.jl"), "# forbidden before input freeze\n")
        @test_throws ErrorException ExperimentSingular001._assert_s4_preimplementation_state(
            ; source_directory,
        )
    end
end

@testset "Gold-independent fixed endpoint generator" begin
    cases = fixed_control_cases()
    repeated = fixed_control_cases()
    @test length(cases) == 10
    @test length(unique(case.input.oracle.id for case in cases)) == length(cases)
    @test fieldnames(CandidateInput) == (:oracle, :endpoint)
    @test [case.checksum for case in cases] == [case.checksum for case in repeated]
    @test all(length(case.checksum) == 64 for case in cases)
    @test count(case -> case.gold.kind == :isolated_root, cases) == 7
    @test count(case -> case.gold.kind != :isolated_root, cases) == 3

    for case in filter(case -> case.gold.kind == :isolated_root, cases)
        input = candidate_input(case)
        gold = case.gold.configuration
        residual = input.oracle.residual(gold)
        @test norm(residual, Inf) <= 1.0e-30
        @test input.oracle.target(gold) ≈ case.gold.target atol=1.0e-30
    end

    manifest = case_manifest_document(cases)
    @test manifest["schema"] == "geotarget.singular-development-input/v1"
    @test length(manifest["cases"]) == length(cases)
    @test all(haskey(entry, "gold_analysis_only") for entry in manifest["cases"])
end

@testset "development grid freezes the preregistered S0 S1 phase" begin
    cases = development_cases()
    @test length(cases) == 72
    @test length(unique(case.input.oracle.id for case in cases)) == 72
    @test count(case -> case.input.oracle.family == "SING-NEAR-NULL-FULL-RANK", cases) == 52
    @test count(case -> case.input.oracle.family == "SING-NONROOT-STATIONARY", cases) == 8
    @test count(case -> case.input.oracle.family == "SING-MANIFOLD-CONTROLS", cases) == 8
    @test count(case -> case.input.oracle.family == "SING-ISOLATED-MULTIPLE", cases) == 4
    @test count(case -> case.input.oracle.capability == :C0, cases) == 4
    document = development_input_document(cases)
    @test document["development_instance_count"] == 72
    @test length(document["case_collection_sha256"]) == 64
    @test length(document["card_sha256"]) == 64
    @test document["variants"] == [
        "S0-POINT-REPLAY",
        "S1-AP-LMQR",
        "SLB-ANALYTIC-DERIVATIVES",
    ]
    manifest_path = joinpath(@__DIR__, "..", "development-input-manifest.json")
    @test isfile(manifest_path)
    frozen = JSON3.read(read(manifest_path, String))
    @test frozen.card_path == "research/experiments/EXP-SINGULAR-001.json"
    @test frozen.case_collection_sha256 == document["case_collection_sha256"]
    @test [entry.checksum for entry in frozen.cases] ==
          [entry["checksum"] for entry in document["cases"]]
end

@testset "S0 point replay can diagnose but never promote" begin
    p1 = case_by_id(fixed_control_cases(), "p1-near-null-base")
    outcome = run_s0(candidate_input(p1))
    @test outcome.status == :diagnostic_only
    @test outcome.semantic_replay !== nothing
    @test outcome.semantic_replay.accepted
    @test outcome.semantic_replay.residual_linf <= 1.0e-12
    @test outcome.root_evidence === nothing
    @test !assess_outcome(p1, outcome).promoted
    @test outcome.work.callbacks == 2
    @test outcome.work.precision_equivalent_oracle_work == 10

    for case in fixed_control_cases()
        control = run_s0(candidate_input(case))
        @test control.status == :diagnostic_only
        @test control.root_evidence === nothing
        @test !assess_outcome(case, control).false_promotion
    end
end

@testset "S1 dense C2 refinement produces separate root evidence" begin
    cases = fixed_control_cases()
    for id in (
        "p1-near-null-base",
        "near-null-full-rank-1e-4",
        "regular-linear-c2",
    )
        case = case_by_id(cases, id)
        outcome = run_s1(candidate_input(case))
        assessment = assess_outcome(case, outcome)
        @test outcome.status == :promoted
        @test outcome.semantic_replay !== nothing
        @test outcome.semantic_replay.accepted
        @test outcome.root_evidence !== nothing
        @test outcome.root_evidence.rank_stable
        @test length(outcome.root_evidence.precision_stages) >= 2
        @test assessment.gold_success
        @test !assessment.false_promotion
        @test assessment.configuration_error_covered
        @test assessment.target_error_covered
        @test outcome.work.callbacks <= ExperimentOptions().maximum_callbacks
        @test outcome.work.precision_equivalent_oracle_work >= outcome.work.callbacks
        @test sum(entry.callbacks for entry in outcome.work.calls_by_precision) ==
              outcome.work.callbacks
    end

    p1 = case_by_id(cases, "p1-near-null-base")
    dense = run_s1(candidate_input(p1))
    analytic = run_s1(candidate_input(p1); derivative_mode=:analytic)
    @test analytic.status == :promoted
    @test assess_outcome(p1, analytic).gold_success
    @test analytic.work.jacobian_calls > 0
    @test analytic.work.residual_calls < dense.work.residual_calls
end

@testset "negative and capability controls fail closed" begin
    cases = fixed_control_cases()
    for id in (
        "nonroot-stationary-1e-13",
        "zero-manifold-varying-target",
        "zero-manifold-constant-target",
    )
        case = case_by_id(cases, id)
        outcome = run_s1(candidate_input(case))
        @test outcome.status != :promoted
        @test outcome.root_evidence === nothing || !assess_outcome(case, outcome).gold_success
        @test !assess_outcome(case, outcome).false_promotion
    end

    c0 = case_by_id(cases, "regular-linear-c0")
    outcome = run_s1(candidate_input(c0))
    @test outcome.status == :unknown
    @test outcome.reason == "C2 capability unavailable"
    @test outcome.work.callbacks == 0
    @test outcome.root_evidence === nothing
end

@testset "metamorphic P1 decisions and routes agree" begin
    cases = filter(
        case -> case.input.oracle.metamorphic_group == "p1-near-null",
        fixed_control_cases(),
    )
    outcomes = [run_s1(candidate_input(case)) for case in cases]
    assessments = [assess_outcome(case, outcome) for (case, outcome) in zip(cases, outcomes)]
    @test length(cases) == 3
    @test all(outcome -> outcome.status == :promoted, outcomes)
    @test length(unique(outcome.route for outcome in outcomes)) == 1
    @test all(assessment -> assessment.gold_success, assessments)
    @test all(assessment -> !assessment.false_promotion, assessments)
end

mutable struct FakeClock
    value::UInt64
    step::UInt64
end

function (clock::FakeClock)()
    current = clock.value
    clock.value += clock.step
    return current
end

@testset "callback, precision and wall budgets fail closed" begin
    p1 = case_by_id(fixed_control_cases(), "p1-near-null-base")
    callback_limited = run_s1(
        candidate_input(p1);
        options=ExperimentOptions(maximum_callbacks=1),
    )
    @test callback_limited.status == :unknown
    @test callback_limited.reason == "callbacks"
    @test callback_limited.work.callbacks == 1
    @test callback_limited.work.budget_exhausted
    @test callback_limited.root_evidence === nothing

    clock = FakeClock(0, 100)
    deadline_limited = run_s1(
        candidate_input(p1);
        options=ExperimentOptions(wall_seconds=1.0e-9),
        clock_ns=clock,
    )
    @test deadline_limited.status == :unknown
    @test deadline_limited.reason == "deadline"
    @test deadline_limited.work.deadline_reached
    @test deadline_limited.root_evidence === nothing
end

@testset "semantic replay cannot manufacture a promoted outcome" begin
    empty_work = WorkSnapshot(0, 0, 0, 0, 0, 0, 0, (), 0.0, 0, false, false)
    semantic = SemanticReplayEvidence(256, (BigFloat(0),), BigFloat(0), BigFloat(0), true)
    @test_throws ArgumentError ExperimentalOutcome(
        "invalid",
        "semantic-only",
        :promoted,
        "invalid",
        semantic,
        nothing,
        empty_work,
    )
end

@testset "artifact documents are finite and replayable" begin
    case = case_by_id(fixed_control_cases(), "regular-linear-c2")
    outcome = run_s1(candidate_input(case))
    assessment = assess_outcome(case, outcome)
    document = Dict{String,Any}(
        "assessment" => assessment_document(assessment),
        "outcome" => outcome_document(case, outcome),
    )
    encoded = JSON3.write(document; allow_inf=false)
    @test JSON3.read(encoded).outcome.status == "promoted"
    mktempdir() do directory
        path = joinpath(directory, "artifact.json")
        @test write_json_artifact(path, document) == abspath(path)
        @test JSON3.read(read(path, String)).assessment.gold_success
        @test isempty(filter(name -> occursin(".tmp-", name), readdir(directory)))
    end
end

@testset "development runner summarizes without product promotion" begin
    controls = fixed_control_cases()
    cases = [
        case_by_id(controls, "p1-near-null-base"),
        case_by_id(controls, "nonroot-stationary-1e-13"),
        case_by_id(controls, "zero-manifold-varying-target"),
        case_by_id(controls, "regular-linear-c0"),
    ]
    rows = run_development(; cases)
    summary = development_summary(rows, cases)
    @test length(rows) == 12
    @test summary["product_connected"] == false
    @test summary["locked_validation"] == false
    @test summary["false_promotions"] == 0
    @test summary["semantic_replay_only_promotions"] == 0
    @test summary["variants"]["S1-AP-LMQR"]["phase_a_gold_successes"] == 1
    mktempdir() do directory
        write_development_results(directory, rows, summary; cases)
        for filename in (
            "attempts.json",
            "development-report.md",
            "environment.json",
            "summary.json",
        )
            @test isfile(joinpath(directory, filename))
        end
        parsed = JSON3.read(read(joinpath(directory, "summary.json"), String))
        @test !parsed.product_connected
        @test !parsed.locked_validation
    end
end

@testset "S2 CPQR subset is target-aware and fail-closed" begin
    cases = s2_development_cases()
    @test length(cases) == 24
    @test count(case -> case.gold.kind == :finite_manifold_target, cases) == 12
    @test count(case -> case.gold.kind == :nonfinite_target_image, cases) == 6
    @test count(case -> case.gold.kind == :no_local_root, cases) == 6
    input_document = s2_development_input_document(cases)
    @test input_document["schema"] == "geotarget.singular-s2-development-input/v1"
    @test input_document["development_instance_count"] == 24
    @test input_document["parent_gate"] == "development-s0-s1-v0"
    @test input_document["variants"] == [
        "S1-AP-LMQR",
        "S2-AP-CPQR-SUBSET",
        "S2-ANALYTIC-SUBSET-CONTROL",
    ]
    s2_manifest_path = joinpath(@__DIR__, "..", "s2-development-input-manifest.json")
    @test isfile(s2_manifest_path)
    frozen_s2 = JSON3.read(read(s2_manifest_path, String))
    @test frozen_s2.case_collection_sha256 == input_document["case_collection_sha256"]
    @test [entry.checksum for entry in frozen_s2.cases] ==
          [entry["checksum"] for entry in input_document["cases"]]

    constant_case = first(filter(
        case -> case.gold.kind == :finite_manifold_target,
        cases,
    ))
    s1 = run_s1(candidate_input(constant_case))
    @test s1.status == :unknown
    @test s1.reason == "rank_deficient"

    s2 = run_s2(candidate_input(constant_case))
    @test s2.status == :promoted
    @test s2.root_evidence isa NumericalManifoldRootEvidence
    @test s2.root_evidence.numerical_rank == 1
    @test s2.root_evidence.nullspace_target_sensitivity <= 1.0e-12
    @test assess_outcome(constant_case, s2).gold_success

    analytic = run_s2(candidate_input(constant_case); derivative_mode=:analytic)
    @test analytic.status == :promoted
    @test assess_outcome(constant_case, analytic).gold_success
    @test analytic.work.residual_calls < s2.work.residual_calls

    for kind in (:nonfinite_target_image, :no_local_root)
        case = first(filter(case -> case.gold.kind == kind, cases))
        outcome = run_s2(candidate_input(case))
        @test outcome.status != :promoted
        @test !assess_outcome(case, outcome).false_promotion
    end

    p1 = case_by_id(fixed_control_cases(), "p1-near-null-base")
    full_rank = run_s2(candidate_input(p1))
    @test full_rank.status == :unknown
    @test full_rank.reason == "rank_not_subset"
    @test full_rank.root_evidence === nothing
end

@testset "S3 development inputs are frozen before candidate outcomes" begin
    cases = s3_development_cases()
    @test length(cases) == 30
    @test length(unique(case.input.oracle.id for case in cases)) == 30
    @test length(unique(case.input.oracle.metamorphic_group for case in cases)) == 10
    @test all(
        count(other -> other.input.oracle.metamorphic_group == case.input.oracle.metamorphic_group, cases) == 3 for
        case in cases
    )
    @test count(case -> case.input.oracle.family == "SING-ISOLATED-MULTIPLE", cases) == 9
    @test count(case -> case.input.oracle.family == "SING-MANIFOLD-CONTROLS", cases) == 6
    @test count(case -> case.input.oracle.family == "SING-NONROOT-STATIONARY", cases) == 6
    @test count(case -> case.input.oracle.family == "SING-TANGENCY-AND-CLOSE-ROOTS", cases) == 9
    document = s3_development_input_document(cases)
    @test document["schema"] == "geotarget.singular-s3-development-input/v1"
    @test document["development_instance_count"] == 30
    @test document["parent_gate"] == "development-s2-v0"
    @test document["transform_namespace"] == "singular-s3-development-v0"
    @test length(document["case_collection_sha256"]) == 64
    @test length(document["preregistration_sha256"]) == 64
    @test document["variants"] == [
        "S1-AP-LMQR",
        "S3-AP-BROYDEN",
        "S3-ANALYTIC-SECANT-CONTROL",
    ]
    manifest_path = joinpath(@__DIR__, "..", "s3-development-input-manifest.json")
    @test isfile(manifest_path)
    frozen = JSON3.read(read(manifest_path, String))
    @test frozen.case_collection_sha256 == document["case_collection_sha256"]
    @test frozen.preregistration_sha256 == document["preregistration_sha256"]
    @test [entry.checksum for entry in frozen.cases] ==
          [entry["checksum"] for entry in document["cases"]]
end

@testset "S3 good-Broyden evidence is typed and the frozen budget is fail-closed" begin
    cases = s3_development_cases()
    double_group = filter(
        case -> case.input.oracle.metamorphic_group == "s3-isolated-m2-a",
        cases,
    )
    @test length(double_group) == 3
    for case in double_group
        baseline = run_s1(candidate_input(case))
        candidate = run_s3(candidate_input(case))
        control = run_s3_analytic_control(candidate_input(case))
        @test baseline.status == :unknown
        @test candidate.status == :unknown
        @test candidate.reason == "iterations"
        @test candidate.work.iterations == ExperimentOptions().maximum_iterations
        @test candidate.work.budget_exhausted
        @test candidate.root_evidence === nothing
        @test control.status == :unknown
        @test control.reason == "iterations"
        @test control.work.iterations == ExperimentOptions().maximum_iterations
        @test control.work.budget_exhausted
        @test control.root_evidence === nothing
        @test candidate.work.callbacks <= ExperimentOptions().maximum_callbacks
        @test candidate.work.iterations <= ExperimentOptions().maximum_iterations
    end

    # A non-gating diagnostic with a larger explicit budget exercises the typed
    # evidence path and measures why the frozen 64-iteration gate rejected S3.
    diagnostic_options = ExperimentOptions(maximum_iterations=80)
    diagnostic_case = first(double_group)
    diagnostic = run_s3(candidate_input(diagnostic_case); options=diagnostic_options)
    diagnostic_control = run_s3_analytic_control(
        candidate_input(diagnostic_case);
        options=diagnostic_options,
    )
    @test diagnostic.status == :promoted
    @test diagnostic_control.status == :promoted
    @test diagnostic.work.iterations == 68
    @test diagnostic_control.work.iterations == 68
    @test diagnostic.root_evidence isa NumericalSingularRootEvidence
    @test diagnostic.root_evidence.rank_stable
    @test diagnostic.root_evidence.nullity == 1
    @test diagnostic.root_evidence.independent_confirmations_passed
    @test diagnostic.root_evidence.canonical_confirmations_passed
    @test diagnostic.root_evidence.linear_trace_passed
    @test length(diagnostic.root_evidence.route_rank_signatures) == 4
    @test length(diagnostic_control.root_evidence.route_rank_signatures) == 2
    @test diagnostic.root_evidence.configuration_error_estimate <= 1.0e-10
    @test diagnostic.root_evidence.target_error_estimate <= 1.0e-12
    @test assess_outcome(diagnostic_case, diagnostic).gold_success
    @test assess_outcome(diagnostic_case, diagnostic_control).gold_success

    quartic = first(filter(
        case -> case.input.oracle.metamorphic_group == "s3-isolated-m4-stress",
        cases,
    ))
    quartic_budget = run_s3(candidate_input(quartic))
    @test quartic_budget.status == :unknown
    @test quartic_budget.work.iterations <= ExperimentOptions().maximum_iterations
    @test quartic_budget.work.budget_exhausted
    @test quartic_budget.reason == "iterations"
    @test run_s3_analytic_control(candidate_input(quartic)).status == :unknown

    coalesced = first(filter(
        case -> case.input.oracle.metamorphic_group == "s3-fold-coalesced",
        cases,
    ))
    coalesced_outcome = run_s3(candidate_input(coalesced))
    @test coalesced_outcome.status == :unknown
    @test coalesced_outcome.reason == "iterations"
    @test coalesced_outcome.work.iterations == ExperimentOptions().maximum_iterations

    for group in (
        "s3-manifold-constant",
        "s3-manifold-varying",
        "s3-nonroot-below-semantic",
        "s3-nonroot-visible",
        "s3-fold-separated",
        "s3-fold-close",
    )
        case = first(filter(case -> case.input.oracle.metamorphic_group == group, cases))
        candidate = run_s3(candidate_input(case))
        @test candidate.status == :unknown
        @test !assess_outcome(case, candidate).false_promotion
    end

    subtle_nonroot = first(filter(
        case -> case.input.oracle.metamorphic_group == "s3-nonroot-below-semantic",
        cases,
    ))
    @test run_s0(candidate_input(subtle_nonroot)).semantic_replay.accepted
    @test run_s3(candidate_input(subtle_nonroot)).reason ==
          "primary residual above strict numerical route goal"

    callback_limited = run_s3(
        candidate_input(first(double_group));
        options=ExperimentOptions(maximum_callbacks=1),
    )
    @test callback_limited.status == :unknown
    @test callback_limited.reason == "callbacks"
    @test callback_limited.work.budget_exhausted
    @test callback_limited.root_evidence === nothing

    clock = FakeClock(0, 100)
    deadline_limited = run_s3(
        candidate_input(first(double_group));
        options=ExperimentOptions(wall_seconds=1.0e-9),
        clock_ns=clock,
    )
    @test deadline_limited.status == :unknown
    @test deadline_limited.reason == "deadline"
    @test deadline_limited.work.deadline_reached

    document = outcome_document(diagnostic_case, diagnostic)
    parsed = JSON3.read(JSON3.write(document; allow_inf=false))
    @test parsed.root_evidence.method ==
          "multiprecision_good_broyden_singular_evidence_v1"
    @test parsed.root_evidence.linear_trace_passed
    @test length(parsed.root_evidence.route_rank_signatures) == 4
end

@testset "S3 development gate remains research-only" begin
    cases = s3_development_cases()
    options = ExperimentOptions()
    rows = run_s3_development(; cases, options)
    summary = s3_development_summary(rows, cases; options)
    @test length(rows) == 90
    @test summary["development_instance_count"] == 30
    @test summary["product_connected"] == false
    @test summary["locked_validation"] == false
    @test summary["false_promotions"] == 0
    @test summary["semantic_replay_only_promotions"] == 0
    @test summary["metamorphic_group_count"] == 10
    @test summary["metamorphic_disagreement_groups"] == [
        "S1-AP-LMQR:s3-fold-close",
    ]
    @test isempty(summary["analytic_control_disagreement_cases"])
    @test isempty(summary["budget_limit_violation_rows"])
    @test isempty(summary["noneligible_s3_promotion_cases"])
    @test isempty(summary["evidence_gate_failure_cases"])
    @test summary["variants"]["S1-AP-LMQR"]["eligible_gold_successes"] == 0
    @test summary["variants"]["S3-AP-BROYDEN"]["eligible_gold_successes"] == 0
    @test summary["variants"]["S3-ANALYTIC-SECANT-CONTROL"]["eligible_gold_successes"] == 0
    @test summary["variants"]["S3-AP-BROYDEN"]["budget_exhaustions"] == 12
    @test summary["variants"]["S3-ANALYTIC-SECANT-CONTROL"]["budget_exhaustions"] == 12
    @test !summary["development_advancement_passed"]
    @test summary["next_route"] === nothing
    @test summary["status"] == "development-stop-s3"
    @test !summary["advancement_criteria"]["recall_gain_at_least_0_50"]
    @test !summary["advancement_criteria"]["s3_singular_recall_at_least_0_75"]
    @test summary["advancement_criteria"]["false_promotions_zero"]
    @test !summary["advancement_criteria"]["metamorphic_disagreements_zero"]
    @test summary["advancement_criteria"]["budget_limit_violations_zero"]
    duplicate_grid = vcat(rows[1:(end - 1)], rows[1:1])
    @test_throws ArgumentError s3_development_summary(
        duplicate_grid,
        cases;
        options,
    )
    mktempdir() do directory
        write_s3_development_results(directory, rows, summary; options)
        for filename in (
            "attempts.json",
            "development-report.md",
            "environment.json",
            "summary.json",
        )
            @test isfile(joinpath(directory, filename))
        end
        parsed = JSON3.read(read(joinpath(directory, "summary.json"), String))
        @test !parsed.development_advancement_passed
        @test !parsed.product_connected
        @test !parsed.locked_validation
    end
end

@testset "S2 metamorphic decisions agree" begin
    cases = s2_development_cases()
    for group in unique(case.input.oracle.metamorphic_group for case in cases)
        grouped = filter(case -> case.input.oracle.metamorphic_group == group, cases)
        outcomes = [run_s2(candidate_input(case)) for case in grouped]
        assessments = [
            assess_outcome(case, outcome) for
            (case, outcome) in zip(grouped, outcomes)
        ]
        @test length(grouped) == 3
        @test length(unique(outcome.status for outcome in outcomes)) == 1
        @test length(unique(assessment.false_promotion for assessment in assessments)) == 1
    end
end

@testset "S2 development gate remains research-only" begin
    cases = s2_development_cases()
    options = ExperimentOptions()
    rows = run_s2_development(; cases, options)
    summary = s2_development_summary(rows, cases; options)
    @test length(rows) == 72
    @test summary["development_instance_count"] == 24
    @test summary["product_connected"] == false
    @test summary["locked_validation"] == false
    @test summary["false_promotions"] == 0
    @test summary["semantic_replay_only_promotions"] == 0
    @test summary["metamorphic_group_count"] == 8
    @test isempty(summary["metamorphic_disagreement_groups"])
    @test isempty(summary["analytic_control_disagreement_cases"])
    @test isempty(summary["budget_limit_violation_rows"])
    @test summary["variants"]["S1-AP-LMQR"]["eligible_gold_successes"] == 0
    @test summary["variants"]["S2-AP-CPQR-SUBSET"]["eligible_gold_successes"] == 12
    @test summary["variants"]["S2-ANALYTIC-SUBSET-CONTROL"]["eligible_gold_successes"] == 12
    @test summary["development_advancement_passed"]
    @test summary["next_route"] == "S3-AP-BROYDEN"
    @test all(values(summary["advancement_criteria"]))
    duplicate_grid = vcat(rows[1:(end - 1)], rows[1:1])
    @test_throws ArgumentError s2_development_summary(
        duplicate_grid,
        cases;
        options,
    )
    mktempdir() do directory
        write_s2_development_results(directory, rows, summary; options)
        for filename in (
            "attempts.json",
            "development-report.md",
            "environment.json",
            "summary.json",
        )
            @test isfile(joinpath(directory, filename))
        end
        parsed = JSON3.read(read(joinpath(directory, "summary.json"), String))
        @test parsed.development_advancement_passed
        @test !parsed.product_connected
        @test !parsed.locked_validation
    end
end
