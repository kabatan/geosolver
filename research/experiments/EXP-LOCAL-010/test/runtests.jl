using GeoTargetBase
using GeoTargetBenchmarks
using GeoTargetCore
using LinearAlgebra
using Test

include(joinpath(@__DIR__, "..", "src", "ExperimentLocal010.jl"))
using .ExperimentLocal010

function observation(residual; valid=true, row_scales=ones(length(residual)))
    relations = Tuple(
        RelationObservation(
            NodeId("test-r-$index"),
            residual[index] * row_scales[index],
            row_scales[index],
            residual[index],
            nothing,
        ) for index in eachindex(residual)
    )
    guard = GuardObservation(NodeId("test-guard"), valid ? 1.0 : -1.0, true, 1.0, valid)
    return OracleObservation(
        relations,
        0.0,
        (guard,),
        (),
        (),
        EVAL_OK,
        1,
        nothing,
    )
end

function attempt(final, residual; evaluations=1, valid=true, row_scales=ones(length(residual)))
    obs = observation(residual; valid, row_scales)
    return LocalAttempt(
        Tuple(final),
        Tuple(final),
        obs,
        LOCAL_CONVERGED,
        true,
        0,
        evaluations,
        length(final),
        1.0,
        (),
    )
end

const LOWER_1 = [-1.0]
const UPPER_1 = [1.0]
const ORIGIN_1 = [0.0]
const SCALE_1 = [1.0]

@testset "certified correction and same-work shadow" begin
    root_shift = 8.0e-13
    evaluator = x -> observation([x[1] + root_shift])
    base = attempt([0.0], [root_shift]; evaluations=1)
    corrected = correct_endpoint(evaluator, base, ORIGIN_1, SCALE_1, LOWER_1, UPPER_1)
    shadow = correct_endpoint(
        evaluator, base, ORIGIN_1, SCALE_1, LOWER_1, UPPER_1; shadow=true,
    )
    @test corrected.status == :certified
    @test corrected.endpoint !== nothing
    @test abs(only(corrected.endpoint) + root_shift) <= 1.0e-15
    @test shadow.endpoint == (0.0,)
    @test shadow.status == corrected.status
    @test shadow.evaluations == corrected.evaluations
    @test shadow.corrections == corrected.corrections
    @test shadow.proof_count == corrected.proof_count
    @test shadow.trial_count == corrected.trial_count
    @test corrected.evaluations <= CALLBACK_CAP
end

@testset "singular and manifold proofs are UNKNOWN" begin
    singular = attempt([0.0], [0.0]; evaluations=1)
    singular_result = correct_endpoint(
        x -> observation([x[1]^2]), singular, ORIGIN_1, SCALE_1, LOWER_1, UPPER_1,
    )
    @test singular_result.status == :unknown
    @test singular_result.endpoint === nothing

    manifold = attempt([0.0, 0.0], [0.0]; evaluations=1)
    manifold_result = correct_endpoint(
        x -> observation([x[1]]),
        manifold,
        [0.0, 0.0],
        [1.0, 1.0],
        [-1.0, -1.0],
        [1.0, 1.0],
    )
    @test manifold_result.status == :unknown
    @test manifold_result.endpoint === nothing
    @test manifold_result.evaluations == 1
end

@testset "strict semantic stencil instability drops a qualified endpoint" begin
    base = attempt([0.0], [0.0]; evaluations=1)
    result = correct_endpoint(
        x -> observation([x[1]]; valid=x[1] <= 0.0),
        base,
        ORIGIN_1,
        SCALE_1,
        LOWER_1,
        UPPER_1,
    )
    @test result.status == :unknown
    @test result.endpoint === nothing
    @test result.evaluations > 1
    @test result.evaluations <= CALLBACK_CAP
end

@testset "noneligible strict boundary passes through without work" begin
    base = attempt([0.0], [0.0]; evaluations=7, valid=false)
    calls = Ref(0)
    result = correct_endpoint(
        x -> begin
            calls[] += 1
            observation([x[1]]; valid=false)
        end,
        base,
        ORIGIN_1,
        SCALE_1,
        LOWER_1,
        UPPER_1,
    )
    @test result.status == :not_eligible
    @test result.endpoint == (0.0,)
    @test result.evaluations == 7
    @test calls[] == 0
end

@testset "row scaling and signed permutation replicas" begin
    shift = [8.0e-13, -7.0e-13]
    base = attempt([0.0, 0.0], shift; evaluations=1)
    ordinary = correct_endpoint(
        x -> observation(x .+ shift),
        base,
        zeros(2),
        ones(2),
        -ones(2),
        ones(2),
    )
    scaled_base = attempt(
        [0.0, 0.0], shift; evaluations=1, row_scales=[1.0e-9, 1.0e9],
    )
    scaled = correct_endpoint(
        x -> observation(x .+ shift; row_scales=[1.0e-9, 1.0e9]),
        scaled_base,
        zeros(2),
        ones(2),
        -ones(2),
        ones(2),
    )
    @test ordinary.status == scaled.status == :certified
    @test collect(ordinary.endpoint) ≈ collect(scaled.endpoint) atol=1.0e-15 rtol=0

    transform = [0.0 -1.0; 1.0 0.0]
    permuted_shift = transform * shift
    permuted_base = attempt([0.0, 0.0], permuted_shift; evaluations=1)
    permuted = correct_endpoint(
        y -> observation(y .+ permuted_shift),
        permuted_base,
        zeros(2),
        ones(2),
        -ones(2),
        ones(2),
    )
    @test permuted.status == :certified
    @test collect(permuted.endpoint) ≈ transform * collect(ordinary.endpoint) atol=1.0e-15 rtol=0
end

@testset "callback cap and reported work" begin
    base = attempt([0.0], [8.0e-13]; evaluations=599)
    calls = Ref(0)
    result = correct_endpoint(
        x -> begin
            calls[] += 1
            observation([x[1] + 8.0e-13])
        end,
        base,
        ORIGIN_1,
        SCALE_1,
        LOWER_1,
        UPPER_1,
    )
    @test result.status == :unknown
    @test result.endpoint === nothing
    @test result.evaluations == CALLBACK_CAP
    @test calls[] == 1
end

@testset "variant reports observed callbacks and shadow repeats work" begin
    function run_variant(shadow)
        calls = Ref(0)
        evaluator = input -> begin
            calls[] += 1
            SolverCaseEvaluation((input[1] + 8.0e-13,), 0.0, true, true)
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
        outcome = endpoint_correction_variant(; shadow).run(case, [0.0])
        return outcome, calls[]
    end
    corrected, corrected_calls = run_variant(false)
    shadow, shadow_calls = run_variant(true)
    @test corrected.evaluations == corrected_calls
    @test shadow.evaluations == shadow_calls
    @test corrected_calls == shadow_calls
    @test corrected_calls <= CALLBACK_CAP
    @test corrected.endpoint != shadow.endpoint
end

@testset "variant preserves noneligible base outcome" begin
    function run_noneligible(shadow)
        calls = Ref(0)
        evaluator = input -> begin
            calls[] += 1
            SolverCaseEvaluation((input[1] - 2.0,), input[1], true, true)
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
        return endpoint_correction_variant(; shadow).run(case, [0.0]), calls[]
    end
    candidate, candidate_calls = run_noneligible(false)
    shadow, shadow_calls = run_noneligible(true)
    @test candidate.endpoint == shadow.endpoint
    @test candidate.status == shadow.status
    @test candidate.reported_converged == shadow.reported_converged
    @test candidate.reported_accepted == shadow.reported_accepted
    @test candidate.evaluations == shadow.evaluations == candidate_calls == shadow_calls
end

@testset "source remains experiment-local and truth blind" begin
    source = read(joinpath(@__DIR__, "..", "src", "ExperimentLocal010.jl"), String)
    @test !occursin("family_id", source)
    @test !occursin("instance_id", source)
    @test !occursin("gold_", lowercase(source))
    @test occursin("qr(coarse, ColumnNorm())", source)
    @test occursin("qr(fine, ColumnNorm())", source)
end

@testset "shared campaign runner is callback-threshold bounded" begin
    runner = read(joinpath(@__DIR__, "..", "run_t0.jl"), String)
    preregistration = read(joinpath(@__DIR__, "..", "preregistration.json"), String)
    @test occursin("const CALLBACK_THRESHOLDS = (600, 1_200, 2_400, 4_800)", runner)
    @test occursin("const MAXIMUM_STARTS = 64", runner)
    @test occursin("cumulative >= last(CALLBACK_THRESHOLDS) && break", runner)
    @test occursin("ExperimentLocal011.endpoint_correction_variant", runner)
    @test occursin("GeoTargetBenchmarks._attempt_document", runner)
    @test occursin("--case-index=1..9 is required", runner)
    @test occursin("\"case_index\" => Int(case_index)", runner)
    @test occursin("SVD_PREREGISTRATION", runner)
    @test occursin("registrations", runner)
    @test occursin("\"outcome_execution_authorized\": false", preregistration)
    @test occursin("\"qualified_target_recall_delta_minimum\": -0.02", preregistration)
end
