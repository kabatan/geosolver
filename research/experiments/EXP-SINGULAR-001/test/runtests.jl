using JSON3
using LinearAlgebra
using Test

include(joinpath(@__DIR__, "..", "src", "ExperimentSingular001.jl"))
using .ExperimentSingular001

function case_by_id(cases, id)
    return only(filter(case -> case.input.oracle.id == id, cases))
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
