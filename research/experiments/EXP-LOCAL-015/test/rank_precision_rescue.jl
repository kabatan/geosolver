using Test

include(joinpath(@__DIR__, "..", "src", "RankPrecisionRescue.jl"))
using .RankPrecisionRescue

sample(residual; semantics=true, branch=:stable) =
    RankRescueSample(residual, semantics, branch)

function problem(
    dimension,
    residual_dimension,
    callback;
    capability=:C2,
    lower=fill(-2.0, dimension),
    upper=fill(2.0, dimension),
    callback_cost=1,
)
    return RankRescueProblem(
        dimension,
        residual_dimension,
        capability,
        lower,
        upper,
        callback;
        callback_cost,
    )
end

seed(
    coordinates;
    rank=length(coordinates) - 1,
    condition=Inf,
    agreement=true,
    semantics=true,
    branch=:stable,
) = RankRescueSeed(
    coordinates,
    rank,
    condition,
    agreement,
    semantics,
    branch,
)

@testset "ill-conditioned full-rank minimum-success fixture" begin
    delta, root = setprecision(BigFloat, 1024) do
        parse(BigFloat, "1e-30"), BigFloat[1 // 4, -1 // 8]
    end
    calls = Ref(0)
    evaluator = function (x, bits)
        calls[] += 1
        @test bits == 512
        @test all(value -> value isa BigFloat && precision(value) >= bits, x)
        first = (x[1] - root[1]) + (x[2] - root[2])
        second = (x[1] - root[1]) + (one(BigFloat) + delta) * (x[2] - root[2])
        return sample(BigFloat[first, second])
    end
    input = problem(2, 2, evaluator; callback_cost=3)
    start = seed([0.25 + 1.0e-8, -0.125 - 1.0e-8]; rank=1, condition=Inf)
    result = rescue_rank_precision(input, start)

    @test result.status == :seed_ready
    @test result.reason == :none
    @test result.evidence isa RankPrecisionEvidence
    @test result.evidence.rank_stable
    @test result.evidence.numerical_rank == 2
    @test result.evidence.residual_linf <= big"1e-110"
    @test result.evidence.correction_linf <= big"1e-100"
    @test maximum(abs.(collect(result.evidence.refined_coordinates) .- root)) <= big"1e-100"
    @test occursin("768-bit", result.diagnostic)
    @test !hasproperty(result, :answer)
    @test !hasproperty(result.evidence, :provisional)
    @test result.work.callbacks == calls[] > 0
    @test result.work.precision_bits == 512
    @test result.work.precision_weight == cld(512, 53) == 10
    @test result.work.raw_oracle_work == 3calls[]
    @test result.work.precision_weighted_oracle_work == 30calls[]
end

@testset "stationary nonroot is typed unknown" begin
    calls = Ref(0)
    evaluator = function (x, _)
        calls[] += 1
        return sample(BigFloat[x[1]^2 + 1])
    end
    result = rescue_rank_precision(
        problem(1, 1, evaluator),
        seed([0.0]; rank=0, condition=Inf),
    )
    @test result.status == :unknown
    @test result.reason == :stationary_nonroot_or_singular
    @test result.evidence === nothing
    @test result.work.callbacks == calls[]
    @test result.work.precision_weighted_oracle_work == 10calls[]
end

@testset "manifold and missing C2 fail before callbacks" begin
    manifold_calls = Ref(0)
    manifold = problem(2, 1, (x, _) -> begin
        manifold_calls[] += 1
        sample(BigFloat[x[1]])
    end)
    manifold_result = rescue_rank_precision(
        manifold,
        seed([0.0, 0.0]; rank=1, condition=Inf),
    )
    @test manifold_result.status == :unknown
    @test manifold_result.reason == :underdetermined_manifold
    @test manifold_calls[] == manifold_result.work.callbacks == 0

    square_manifold_calls = Ref(0)
    square_manifold = problem(2, 2, (x, _) -> begin
        square_manifold_calls[] += 1
        sample(BigFloat[x[1], 2x[1]])
    end)
    square_result = rescue_rank_precision(
        square_manifold,
        seed([0.0, 0.25]; rank=1, condition=Inf),
    )
    @test square_result.status == :unknown
    @test square_result.reason == :rank_deficient_or_manifold
    @test square_result.evidence === nothing
    @test square_result.work.callbacks == square_manifold_calls[] > 0
    @test square_result.work.precision_weighted_oracle_work ==
          10square_manifold_calls[]

    c2_calls = Ref(0)
    no_c2 = problem(1, 1, (x, _) -> begin
        c2_calls[] += 1
        sample(BigFloat[x[1]])
    end; capability=:C0)
    c2_result = rescue_rank_precision(no_c2, seed([0.0]; rank=0))
    @test c2_result.status == :unknown
    @test c2_result.reason == :c2_capability_missing
    @test c2_calls[] == c2_result.work.callbacks == 0
end

@testset "branch-changing correction is typed unknown" begin
    calls = Ref(0)
    evaluator = function (x, _)
        calls[] += 1
        branch = x[1] <= big"0.01" ? :left : :right
        return sample(BigFloat[x[1] - big"0.5"]; branch)
    end
    result = rescue_rank_precision(
        problem(1, 1, evaluator; lower=[-1.0], upper=[1.0]),
        seed([0.0]; rank=0, condition=Inf, branch=:left),
    )
    @test result.status == :unknown
    @test result.reason == :branch_changed
    @test result.evidence === nothing
    @test result.work.callbacks == calls[]
    @test result.work.precision_weighted_oracle_work == 10calls[]
end

@testset "semantics, model, trigger and precision downgrade are fail-closed" begin
    never_calls = Ref(0)
    never = problem(1, 1, (x, _) -> begin
        never_calls[] += 1
        sample(BigFloat[x[1]])
    end)
    bad_semantics = rescue_rank_precision(
        never,
        seed([0.0]; rank=0, semantics=false),
    )
    @test bad_semantics.reason == :prefilter_semantics_invalid
    bad_model = rescue_rank_precision(
        never,
        seed([0.0]; rank=0, agreement=false),
    )
    @test bad_model.reason == :model_disagreement
    untriggered = rescue_rank_precision(
        never,
        seed([0.0]; rank=1, condition=2.0),
    )
    @test untriggered.reason == :condition_trigger_not_met
    @test never_calls[] == 0

    downgrade_calls = Ref(0)
    downgrade = problem(1, 1, (x, _) -> begin
        downgrade_calls[] += 1
        sample(Float64[Float64(x[1])])
    end)
    downgraded = rescue_rank_precision(
        downgrade,
        seed([0.25]; rank=0, condition=Inf),
    )
    @test downgraded.status == :unknown
    @test downgraded.reason == :precision_downgrade
    @test downgraded.work.callbacks == downgrade_calls[] == 1
    @test downgraded.work.precision_weighted_oracle_work == 10
end

@testset "weighted callback cap charges failed invocations" begin
    calls = Ref(0)
    throwing = problem(1, 1, (x, _) -> begin
        calls[] += 1
        error("fixture failure")
    end; callback_cost=2)
    result = rescue_rank_precision(
        throwing,
        seed([0.0]; rank=0),
        options=RankRescueOptions(maximum_weighted_oracle_work=20),
    )
    @test result.status == :unknown
    @test result.reason == :callback_failed
    @test result.work.callbacks == calls[] == 1
    @test result.work.raw_oracle_work == 2
    @test result.work.precision_weighted_oracle_work == 20

    no_budget_calls = Ref(0)
    no_budget = problem(1, 1, (x, _) -> begin
        no_budget_calls[] += 1
        sample(BigFloat[x[1]])
    end; callback_cost=2)
    capped = rescue_rank_precision(
        no_budget,
        seed([0.25]; rank=0),
        options=RankRescueOptions(maximum_weighted_oracle_work=19),
    )
    @test capped.reason == :weighted_oracle_budget_exhausted
    @test capped.work.callbacks == no_budget_calls[] == 0
    @test capped.work.precision_weighted_oracle_work == 0
end

@testset "REFERENCE-512 d8 is structurally budget limited at formal work 600" begin
    calls = Ref(0)
    d8 = problem(8, 8, (x, bits) -> begin
        calls[] += 1
        @test bits == 512
        sample(BigFloat[x...])
    end; lower=fill(-1.0, 8), upper=fill(1.0, 8))
    result = rescue_rank_precision(
        d8,
        seed(zeros(8); rank=7, condition=Inf),
        options=RankRescueOptions(
            maximum_callbacks=512,
            maximum_weighted_oracle_work=600,
        ),
    )
    @test REFERENCE_NAME == "REFERENCE-512-CPQR-H-H2"
    @test !FORMAL_EQUAL_WORK_PROMOTION_AUTHORITY
    @test FORMAL_600_WORK_CLASSIFICATION == :BUDGET_OR_PARAMETER_LIMITED
    @test result.status == :unknown
    @test result.reason == :weighted_oracle_budget_exhausted
    @test result.evidence === nothing
    @test occursin("REFERENCE-512", result.diagnostic)
    @test result.work.callbacks == calls[] == 60
    @test result.work.precision_weighted_oracle_work == 600
    @test result.work.factorization_count == 0
    @test result.work.iteration_count == 1
end

@testset "source is truth-blind and experiment-local" begin
    source = read(joinpath(@__DIR__, "..", "src", "RankPrecisionRescue.jl"), String)
    for forbidden in (
        "family_id",
        "instance_id",
        "gold_configurations",
        "gold_targets",
        "primitive_name",
        "plugin_id",
        "ProvisionalAnswer",
        "ExactAnswer",
    )
        @test !occursin(forbidden, source)
    end
    @test occursin("cld(PRECISION_BITS, 53)", source)
    @test occursin("ColumnNorm()", source)
    @test occursin("h/h2", source)
    @test occursin("FORMAL_EQUAL_WORK_PROMOTION_AUTHORITY = false", source)
    @test occursin(":BUDGET_OR_PARAMETER_LIMITED", source)
end
