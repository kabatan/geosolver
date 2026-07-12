using LinearAlgebra
using Test

include(joinpath(@__DIR__, "..", "src", "RankPrecisionRescue.jl"))
include(joinpath(@__DIR__, "..", "src", "AdaptivePrecisionRescue.jl"))

const REF = RankPrecisionRescue
const ADAPT = AdaptivePrecisionRescue

struct ExplosiveResidual end
Base.iterate(::ExplosiveResidual, state...) = error("explosive residual iteration")

struct ExplosiveIdentity end
Base.isequal(::ExplosiveIdentity, ::ExplosiveIdentity) =
    error("explosive opaque identity equality")

semantic_state(
    branch;
    branch_margin=1.0,
    guard_ids=(),
    guard_margins=(),
    domain_ids=(),
    domain_margins=(),
) = ADAPT.AdaptiveSemanticState(
    branch,
    branch_margin,
    guard_ids,
    guard_margins,
    domain_ids,
    domain_margins,
)

function adaptive_problem(
    dimension,
    residual_dimension,
    callback;
    capability=:C2,
    lower=fill(-2.0, dimension),
    upper=fill(2.0, dimension),
    callback_cost=1,
)
    return ADAPT.AdaptiveRescueProblem(
        dimension,
        residual_dimension,
        capability,
        lower,
        upper,
        callback;
        callback_cost,
    )
end

adaptive_seed(
    coordinates;
    rank=length(coordinates) - 1,
    condition=Inf,
    agreement=true,
    semantics=true,
    branch=:stable,
) = ADAPT.AdaptiveRescueSeed(
    coordinates,
    rank,
    condition,
    agreement,
    semantics,
    branch,
)

function linear_fixture(delta_text; dimension=8)
    return setprecision(BigFloat, 1024) do
        delta = startswith(delta_text, "2^") ?
                ldexp(one(BigFloat), parse(Int, delta_text[3:end])) :
                parse(BigFloat, delta_text)
        matrix = Matrix{BigFloat}(I, dimension, dimension)
        matrix[1, 1] = 1
        matrix[1, 2] = 1
        matrix[2, 1] = 1
        matrix[2, 2] = 1 + delta
        root = BigFloat[ldexp(one(BigFloat), -(index + 1)) for index in 1:dimension]
        error = ldexp(one(BigFloat), -20)
        start = copy(root)
        start[1] += error
        start[2] -= error
        for index in 3:dimension
            start[index] += ldexp(error, -index)
        end
        return matrix, root, Float64.(start)
    end
end

function calls_document(work)
    return Dict(entry.precision_bits => entry.callbacks for entry in work.calls_by_precision)
end

@testset "A_delta 2^-160 d8 adapted route and REFERENCE-512 differential" begin
    matrix, root, start = linear_fixture("2^-160")
    adaptive_calls = Dict{Int,Int}()
    adaptive_callback = function (x, bits)
        adaptive_calls[bits] = get(adaptive_calls, bits, 0) + 1
        @test bits in ADAPT.PRECISION_TIERS
        @test all(value -> value isa BigFloat && precision(value) >= bits, x)
        return ADAPT.AdaptiveRescueSample(matrix * (x .- root), true, :stable)
    end
    adapted = ADAPT.rescue_adaptive_precision(
        adaptive_problem(8, 8, adaptive_callback),
        adaptive_seed(start; rank=7, condition=Inf),
    )
    @test adapted.status == :seed_ready
    @test adapted.reason == :none
    @test adapted.evidence isa ADAPT.AdaptiveRefinementSeedEvidence
    @test adapted.evidence.selected_precision_bits == 256
    @test adapted.evidence.confirmation_precision_bits == 512
    @test adapted.evidence.precision_path == (256, 512)
    @test adapted.evidence.selected_numerical_rank == 8
    @test adapted.evidence.confirmation_numerical_rank == 8
    @test adapted.evidence.rank_stable
    @test adapted.evidence.correction_stable
    @test adapted.evidence.refined_residual_linf < adapted.evidence.source_residual_linf
    # 256 bits minus roughly 160 lost conditioning bits leaves about 29 decimal
    # configuration digits.  The evaluated seed beats that bound; 512-bit
    # confirmation records the remaining correction for downstream refinement.
    @test maximum(abs.(collect(adapted.evidence.refined_coordinates) .- root)) < big"1e-30"
    # Higher precision confirms the source model before the selected-tier step;
    # this is intentionally a full Newton-scale correction, not a refined-point
    # error bound.
    @test adapted.evidence.confirmation_correction_linf > big"1e-10"
    @test adapted.evidence.cross_tier_correction_disagreement <=
          adapted.evidence.cross_tier_correction_tolerance
    @test all(==(256), precision.(collect(adapted.evidence.refined_coordinates)))
    @test precision(adapted.evidence.source_residual_linf) == 256
    @test precision(adapted.evidence.refined_residual_linf) == 256
    @test precision(adapted.evidence.selected_condition_estimate) == 256
    @test precision(adapted.evidence.confirmation_condition_estimate) == 512
    @test precision(adapted.evidence.confirmation_correction_linf) == 512
    @test precision(adapted.evidence.confirmation_correction_disagreement) == 512
    @test precision(adapted.evidence.cross_tier_residual_disagreement) == 512
    @test precision(adapted.evidence.cross_tier_residual_tolerance) == 512
    @test precision(adapted.evidence.cross_tier_jacobian_disagreement) == 512
    @test precision(adapted.evidence.cross_tier_jacobian_tolerance) == 512
    @test precision(adapted.evidence.cross_tier_correction_disagreement) == 512
    @test precision(adapted.evidence.cross_tier_correction_tolerance) == 512
    @test !hasproperty(adapted, :answer)
    @test !hasproperty(adapted.evidence, :provisional)
    @test adapted.work.callbacks == 67
    @test adapted.work.raw_oracle_work == 67
    @test adapted.work.precision_weighted_oracle_work == 500 <= 600
    @test adapted.work.factorization_count == 4
    @test adapted.work.tier_count == 2
    @test adapted.work.newton_steps == 1
    @test calls_document(adapted.work) == Dict(256 => 34, 512 => 33)
    @test adaptive_calls == Dict(256 => 34, 512 => 33)
    @test occursin("512/768", adapted.diagnostic)

    reference_calls = Ref(0)
    reference_callback = function (x, bits)
        reference_calls[] += 1
        return REF.RankRescueSample(matrix * (x .- root), true, :stable)
    end
    reference = REF.rescue_rank_precision(
        REF.RankRescueProblem(
            8,
            8,
            :C2,
            fill(-2.0, 8),
            fill(2.0, 8),
            reference_callback,
        ),
        REF.RankRescueSeed(start, 7, Inf, true, true, :stable),
        options=REF.RankRescueOptions(
            maximum_callbacks=512,
            maximum_weighted_oracle_work=600,
        ),
    )
    @test reference.status == :unknown
    @test reference.reason == :weighted_oracle_budget_exhausted
    @test reference.work.callbacks == reference_calls[] == 60
    @test reference.work.precision_weighted_oracle_work == 600
    @test reference.work.factorization_count == 0
    @test REF.FORMAL_600_WORK_CLASSIFICATION == :BUDGET_OR_PARAMETER_LIMITED
    @test !REF.FORMAL_EQUAL_WORK_PROMOTION_AUTHORITY
end

@testset "NearRank-like delta 1e-12 starts 128 and confirms 256 only" begin
    matrix, root, start = linear_fixture("1e-12")
    calls = Dict{Int,Int}()
    callback = function (x, bits)
        calls[bits] = get(calls, bits, 0) + 1
        return ADAPT.AdaptiveRescueSample(matrix * (x .- root), true, :stable)
    end
    result = ADAPT.rescue_adaptive_precision(
        adaptive_problem(8, 8, callback),
        adaptive_seed(start; rank=8, condition=2.0e12),
    )
    @test result.status == :seed_ready
    @test result.evidence.selected_precision_bits == 128
    @test result.evidence.confirmation_precision_bits == 256
    @test result.evidence.precision_path == (128, 256)
    @test result.evidence.refined_residual_linf < result.evidence.source_residual_linf
    @test maximum(abs.(collect(result.evidence.refined_coordinates) .- root)) < big"1e-20"
    @test calls == Dict(128 => 34, 256 => 33)
    @test calls_document(result.work) == calls
    @test !haskey(calls, 512)
    @test result.work.callbacks == 67
    @test result.work.precision_weighted_oracle_work == 267
    @test result.work.newton_steps == 1
end

@testset "outer BigFloat default cannot downcast tier computations or evidence" begin
    matrix, root, start = linear_fixture("2^-80"; dimension=2)
    function run_with_outer_precision(outer_bits)
        calls = Dict{Int,Int}()
        result = setprecision(BigFloat, outer_bits) do
            @test precision(BigFloat) == outer_bits
            callback = function (x, bits)
                @test precision(BigFloat) == bits
                calls[bits] = get(calls, bits, 0) + 1
                ADAPT.AdaptiveRescueSample(matrix * (x .- root), true, :stable)
            end
            observed = ADAPT.rescue_adaptive_precision(
                adaptive_problem(2, 2, callback),
                adaptive_seed(start; rank=1, condition=Inf),
            )
            @test precision(BigFloat) == outer_bits
            observed
        end
        return result, calls
    end

    low, low_calls = run_with_outer_precision(64)
    high, high_calls = run_with_outer_precision(1024)
    @test low.status == high.status == :seed_ready
    @test low.reason == high.reason == :none
    @test low.evidence.precision_path == high.evidence.precision_path == (256, 512)
    @test low.evidence.refined_coordinates == high.evidence.refined_coordinates
    @test low.evidence.source_residual_linf == high.evidence.source_residual_linf
    @test low.evidence.refined_residual_linf == high.evidence.refined_residual_linf
    @test low.evidence.selected_condition_estimate ==
          high.evidence.selected_condition_estimate
    @test low.evidence.confirmation_condition_estimate ==
          high.evidence.confirmation_condition_estimate
    @test low.evidence.confirmation_correction_linf ==
          high.evidence.confirmation_correction_linf
    @test low.evidence.confirmation_correction_disagreement ==
          high.evidence.confirmation_correction_disagreement
    @test low.evidence.cross_tier_residual_disagreement ==
          high.evidence.cross_tier_residual_disagreement
    @test low.evidence.cross_tier_residual_tolerance ==
          high.evidence.cross_tier_residual_tolerance
    @test low.evidence.cross_tier_jacobian_disagreement ==
          high.evidence.cross_tier_jacobian_disagreement
    @test low.evidence.cross_tier_jacobian_tolerance ==
          high.evidence.cross_tier_jacobian_tolerance
    @test low.evidence.cross_tier_correction_disagreement ==
          high.evidence.cross_tier_correction_disagreement
    @test low.evidence.cross_tier_correction_tolerance ==
          high.evidence.cross_tier_correction_tolerance
    @test low.work == high.work
    @test low_calls == high_calls == Dict(256 => 10, 512 => 9)
    @test low.work.precision_weighted_oracle_work == 140
    for result in (low, high)
        @test all(==(256), precision.(collect(result.evidence.refined_coordinates)))
        @test precision(result.evidence.source_residual_linf) == 256
        @test precision(result.evidence.refined_residual_linf) == 256
        @test precision(result.evidence.selected_condition_estimate) == 256
        @test precision(result.evidence.confirmation_condition_estimate) == 512
        @test precision(result.evidence.confirmation_correction_linf) == 512
        @test precision(result.evidence.confirmation_correction_disagreement) == 512
        @test precision(result.evidence.cross_tier_residual_disagreement) == 512
        @test precision(result.evidence.cross_tier_residual_tolerance) == 512
        @test precision(result.evidence.cross_tier_jacobian_disagreement) == 512
        @test precision(result.evidence.cross_tier_jacobian_tolerance) == 512
        @test precision(result.evidence.cross_tier_correction_disagreement) == 512
        @test precision(result.evidence.cross_tier_correction_tolerance) == 512
    end
end

@testset "128 rank evidence failure escalates through the exact 599-work route" begin
    matrix, root, start = linear_fixture("2^-100")
    calls = Dict{Int,Int}()
    callback = function (x, bits)
        calls[bits] = get(calls, bits, 0) + 1
        return ADAPT.AdaptiveRescueSample(matrix * (x .- root), true, :stable)
    end
    # This models a noisy Float64 full-rank diagnostic: public condition data
    # selects 128, while canonical 128-bit h/h2 evidence correctly refuses the
    # 2^-100 weak direction and alone causes escalation.
    result = ADAPT.rescue_adaptive_precision(
        adaptive_problem(8, 8, callback),
        adaptive_seed(start; rank=8, condition=Inf),
    )
    @test result.status == :seed_ready
    @test result.evidence.selected_precision_bits == 256
    @test result.evidence.confirmation_precision_bits == 512
    @test result.evidence.precision_path == (128, 256, 512)
    @test calls == Dict(128 => 33, 256 => 34, 512 => 33)
    @test calls_document(result.work) == calls
    @test result.work.callbacks == 100
    @test result.work.precision_weighted_oracle_work == 599
    @test result.work.factorization_count == 6
    @test result.work.tier_count == 3
    @test result.work.newton_steps == 1
end

@testset "adjacent-tier model inconsistency and correction disagreement fail closed" begin
    calls = Dict{Int,Int}()
    inconsistent = adaptive_problem(
        1,
        1,
        (x, bits) -> begin
            calls[bits] = get(calls, bits, 0) + 1
            residual = bits == 128 ? x[1] - 1 : x[1] + 1
            ADAPT.AdaptiveRescueSample(BigFloat[residual], true, :stable)
        end;
        lower=[-2.0],
        upper=[2.0],
    )
    inconsistent_result = ADAPT.rescue_adaptive_precision(
        inconsistent,
        adaptive_seed([0.0]; rank=1, condition=1.0e9),
    )
    @test inconsistent_result.status == :unknown
    @test inconsistent_result.reason == :cross_tier_model_disagreement
    @test inconsistent_result.evidence === nothing
    @test calls == Dict(128 => 5, 256 => 5)
    @test inconsistent_result.work.precision_weighted_oracle_work == 40

    scale_calls = Dict{Int,Int}()
    tier_scaled = adaptive_problem(
        1,
        1,
        (x, bits) -> begin
            scale_calls[bits] = get(scale_calls, bits, 0) + 1
            multiplier = bits == 128 ? BigFloat(1) : BigFloat(1000)
            ADAPT.AdaptiveRescueSample(
                BigFloat[multiplier * (x[1] - BigFloat(1 // 2))],
                true,
                :stable,
            )
        end;
        lower=[-2.0],
        upper=[2.0],
    )
    scale_result = ADAPT.rescue_adaptive_precision(
        tier_scaled,
        adaptive_seed([0.0]; rank=1, condition=1.0e9),
    )
    @test scale_result.status == :unknown
    @test scale_result.reason == :cross_tier_model_disagreement
    @test scale_result.evidence === nothing
    @test scale_calls == Dict(128 => 5, 256 => 5)
    @test scale_result.work.precision_weighted_oracle_work == 40
    @test scale_result.work.newton_steps == 0

    stable_100, disagreement_100, tolerance_100 =
        ADAPT._relative_correction_agreement(
            BigFloat[1],
            BigFloat[0],
            256,
            BigFloat(1),
        )
    stable_99, disagreement_99, tolerance_99 =
        ADAPT._relative_correction_agreement(
            BigFloat[1],
            BigFloat[1 // 100],
            256,
            BigFloat(1),
        )
    @test !stable_100
    @test !stable_99
    @test disagreement_100 == 1
    @test isapprox(disagreement_99, BigFloat(99 // 100); rtol=eps(BigFloat))
    @test tolerance_100 < 1 // 8
    @test tolerance_99 == tolerance_100

    cubic_calls = Ref(0)
    selected_bits = 256
    h = setprecision(BigFloat, selected_bits) do
        ldexp(one(BigFloat), -cld(selected_bits, 3))
    end
    cubic = adaptive_problem(
        1,
        1,
        (x, bits) -> begin
            cubic_calls[] += 1
            value = x[1] - BigFloat(1 // 10) +
                    BigFloat(1 // 100) * x[1]^3 / h^2
            ADAPT.AdaptiveRescueSample(BigFloat[value], true, :stable)
        end;
        lower=[-1.0],
        upper=[1.0],
    )
    cubic_result = ADAPT.rescue_adaptive_precision(
        cubic,
        adaptive_seed([0.0]; rank=0, condition=Inf),
    )
    @test cubic_result.status == :unknown
    @test cubic_result.reason == :correction_unstable
    @test cubic_result.evidence === nothing
    @test cubic_result.work.callbacks == cubic_calls[] == 5
    @test cubic_result.work.newton_steps == 0
end

@testset "spectral rank authority is orthogonal and global-scale invariant" begin
    base_matrix, left_rotation, row_permutation, right_rotation, scaled_matrix =
        setprecision(BigFloat, 128) do
            weak = BigFloat("0.8") * BigFloat(16) *
                   eps(BigFloat)^(BigFloat(2) / BigFloat(3))
            base = BigFloat[2 0; 0 weak]
            inverse_root_two = inv(sqrt(BigFloat(2)))
            rotation = BigFloat[
                inverse_root_two -inverse_root_two
                inverse_root_two inverse_root_two
            ]
            permutation = BigFloat[0 1; 1 0]
            scale = parse(BigFloat, "1e-80")
            (base, rotation, permutation, rotation, scale * base)
        end
    direct_factors = setprecision(BigFloat, 128) do
        (
            ADAPT._rank_factorization(base_matrix, BigFloat(0)),
            ADAPT._rank_factorization(left_rotation * base_matrix, BigFloat(0)),
            ADAPT._rank_factorization(row_permutation * base_matrix, BigFloat(0)),
            ADAPT._rank_factorization(base_matrix * right_rotation, BigFloat(0)),
            ADAPT._rank_factorization(scaled_matrix, BigFloat(0)),
        )
    end
    @test all(factor -> factor.rank == 1, direct_factors)
    @test all(factor -> factor.gap_stable, direct_factors)
    @test all(
        factor -> length(factor.singular_values) == 2,
        direct_factors,
    )
    @test direct_factors[1].rank == direct_factors[2].rank ==
          direct_factors[3].rank == direct_factors[4].rank == direct_factors[5].rank
    @test isapprox(
        direct_factors[5].threshold / direct_factors[1].threshold,
        big"1e-80";
        rtol=big"1e-30",
    )
    audit_literal_factors = setprecision(BigFloat, 256) do
        audit_matrix = BigFloat[2 0; 0 parse(BigFloat, "1.52347588475e-50")]
        inverse_root_two = inv(sqrt(BigFloat(2)))
        rotation = BigFloat[
            inverse_root_two -inverse_root_two
            inverse_root_two inverse_root_two
        ]
        (
            ADAPT._rank_factorization(audit_matrix, BigFloat(0)),
            ADAPT._rank_factorization(rotation * audit_matrix, BigFloat(0)),
            ADAPT._rank_factorization(audit_matrix * rotation, BigFloat(0)),
            ADAPT._rank_factorization(BigFloat("1e-80") * audit_matrix, BigFloat(0)),
        )
    end
    @test all(factor -> factor.rank == first(audit_literal_factors).rank, audit_literal_factors)
    @test all(factor -> factor.gap_stable, audit_literal_factors)

    root = BigFloat[1 // 4, -1 // 8]
    start = BigFloat[root[1] + 1 // 1024, root[2] - 1 // 2048]
    variants = (
        (matrix=base_matrix, root, start),
        (matrix=left_rotation * base_matrix, root, start),
        (matrix=row_permutation * base_matrix, root, start),
        (
            matrix=base_matrix * right_rotation,
            root=transpose(right_rotation) * root,
            start=transpose(right_rotation) * start,
        ),
        (matrix=scaled_matrix, root, start),
    )
    outcomes = ADAPT.AdaptivePrecisionResult[]
    for variant in variants
        callback = (x, bits) -> ADAPT.AdaptiveRescueSample(
            variant.matrix * (x .- variant.root),
            true,
            :stable,
        )
        result = ADAPT.rescue_adaptive_precision(
            adaptive_problem(2, 2, callback; lower=[-2.0, -2.0], upper=[2.0, 2.0]),
            adaptive_seed(Float64.(variant.start); rank=2, condition=Inf),
        )
        push!(outcomes, result)
    end
    @test all(result -> result.status == :seed_ready, outcomes)
    @test all(result -> result.reason == :none, outcomes)
    @test all(
        result -> result.evidence.precision_path == (128, 256, 512),
        outcomes,
    )
    @test all(result -> result.work.precision_weighted_oracle_work == 167, outcomes)
    @test all(result -> result.work.newton_steps == 1, outcomes)
    @test length(unique(result.status for result in outcomes)) == 1
    @test length(unique(result.work.precision_weighted_oracle_work for result in outcomes)) == 1
end

@testset "opaque semantic identity, margins and malformed outputs fail closed" begin
    branch_contract = semantic_state(:stable; branch_margin=1.0)
    branch_margin_calls = Ref(0)
    branch_margin_crossing = adaptive_problem(
        1,
        1,
        (x, bits) -> begin
            branch_margin_calls[] += 1
            state = semantic_state(
                :stable;
                branch_margin=BigFloat("0.01") - x[1],
            )
            ADAPT.AdaptiveRescueSample(BigFloat[x[1] - BigFloat(1 // 2)], true, state)
        end;
        lower=[-1.0],
        upper=[1.0],
    )
    branch_margin_result = ADAPT.rescue_adaptive_precision(
        branch_margin_crossing,
        adaptive_seed([0.0]; rank=0, branch=branch_contract),
    )
    @test branch_margin_result.status == :unknown
    @test branch_margin_result.reason == :semantic_margin_failed
    @test branch_margin_result.evidence === nothing
    @test branch_margin_result.work.callbacks == branch_margin_calls[] == 11
    @test branch_margin_result.work.precision_weighted_oracle_work == 80

    for invalid_margin in (0.0, -1.0, NaN)
        invalid_calls = Ref(0)
        invalid_problem = adaptive_problem(1, 1, (x, bits) -> begin
            invalid_calls[] += 1
            state = semantic_state(:stable; branch_margin=invalid_margin)
            ADAPT.AdaptiveRescueSample(BigFloat[x[1]], true, state)
        end)
        invalid_result = ADAPT.rescue_adaptive_precision(
            invalid_problem,
            adaptive_seed([0.25]; rank=0, branch=branch_contract),
        )
        @test invalid_result.status == :unknown
        @test invalid_result.reason == :semantic_margin_failed
        @test invalid_result.work.callbacks == invalid_calls[] == 1
    end

    guard_contract = semantic_state(
        :stable;
        guard_ids=(:strict_guard,),
        guard_margins=(1.0,),
    )
    guard_calls = Ref(0)
    guard_crossing = adaptive_problem(
        1,
        1,
        (x, bits) -> begin
            guard_calls[] += 1
            observed = semantic_state(
                :stable;
                guard_ids=(:strict_guard,),
                guard_margins=(BigFloat("0.01") - x[1],),
            )
            ADAPT.AdaptiveRescueSample(BigFloat[x[1] - BigFloat(1 // 2)], true, observed)
        end;
        lower=[-1.0],
        upper=[1.0],
    )
    guard_result = ADAPT.rescue_adaptive_precision(
        guard_crossing,
        adaptive_seed([0.0]; rank=0, branch=guard_contract),
    )
    @test guard_result.status == :unknown
    @test guard_result.reason == :semantic_margin_failed
    @test guard_result.evidence === nothing
    @test guard_result.work.callbacks == guard_calls[] == 11
    @test guard_result.work.precision_weighted_oracle_work == 80

    identity_calls = Ref(0)
    identity_change = adaptive_problem(1, 1, (x, bits) -> begin
        identity_calls[] += 1
        state = semantic_state(:stable; guard_ids=(:different,), guard_margins=(1.0,))
        ADAPT.AdaptiveRescueSample(BigFloat[x[1]], true, state)
    end)
    identity_result = ADAPT.rescue_adaptive_precision(
        identity_change,
        adaptive_seed([0.25]; rank=0, branch=guard_contract),
    )
    @test identity_result.reason == :semantic_identity_failed
    @test identity_result.work.callbacks == identity_calls[] == 1

    zero_domain_calls = Ref(0)
    domain_contract = semantic_state(
        :stable;
        domain_ids=(:positive_domain,),
        domain_margins=(1.0,),
    )
    zero_domain = adaptive_problem(1, 1, (x, bits) -> begin
        zero_domain_calls[] += 1
        state = semantic_state(
            :stable;
            domain_ids=(:positive_domain,),
            domain_margins=(BigFloat(0),),
        )
        ADAPT.AdaptiveRescueSample(BigFloat[x[1]], true, state)
    end)
    zero_result = ADAPT.rescue_adaptive_precision(
        zero_domain,
        adaptive_seed([0.25]; rank=0, branch=domain_contract),
    )
    @test zero_result.reason == :semantic_margin_failed
    @test zero_result.work.callbacks == zero_domain_calls[] == 1

    nonfinite_calls = Ref(0)
    nonfinite_domain = adaptive_problem(1, 1, (x, bits) -> begin
        nonfinite_calls[] += 1
        state = semantic_state(
            :stable;
            domain_ids=(:positive_domain,),
            domain_margins=(BigFloat(NaN),),
        )
        ADAPT.AdaptiveRescueSample(BigFloat[x[1]], true, state)
    end)
    nonfinite_result = ADAPT.rescue_adaptive_precision(
        nonfinite_domain,
        adaptive_seed([0.25]; rank=0, branch=domain_contract),
    )
    @test nonfinite_result.reason == :semantic_margin_failed
    @test nonfinite_result.work.callbacks == nonfinite_calls[] == 1

    domain_identity_calls = Ref(0)
    changed_domain = adaptive_problem(1, 1, (x, bits) -> begin
        domain_identity_calls[] += 1
        state = semantic_state(
            :stable;
            domain_ids=(:different_domain,),
            domain_margins=(1.0,),
        )
        ADAPT.AdaptiveRescueSample(BigFloat[x[1]], true, state)
    end)
    changed_domain_result = ADAPT.rescue_adaptive_precision(
        changed_domain,
        adaptive_seed([0.25]; rank=0, branch=domain_contract),
    )
    @test changed_domain_result.reason == :semantic_identity_failed
    @test changed_domain_result.work.callbacks == domain_identity_calls[] == 1

    prefilter_calls = Ref(0)
    never = adaptive_problem(1, 1, (x, bits) -> begin
        prefilter_calls[] += 1
        ADAPT.AdaptiveRescueSample(BigFloat[x[1]], true, :stable)
    end)
    bad_prefilter = semantic_state(
        :stable;
        guard_ids=(:strict_guard,),
        guard_margins=(0.0,),
    )
    prefilter_result = ADAPT.rescue_adaptive_precision(
        never,
        adaptive_seed([0.25]; rank=0, branch=bad_prefilter),
    )
    @test prefilter_result.reason == :prefilter_semantic_margin_invalid
    @test prefilter_result.work.callbacks == prefilter_calls[] == 0

    bad_branch_prefilter = semantic_state(:stable; branch_margin=0.0)
    branch_prefilter_result = ADAPT.rescue_adaptive_precision(
        never,
        adaptive_seed([0.25]; rank=0, branch=bad_branch_prefilter),
    )
    @test branch_prefilter_result.reason == :prefilter_semantic_margin_invalid
    @test branch_prefilter_result.work.callbacks == prefilter_calls[] == 0

    residual_calls = Ref(0)
    explosive_residual = adaptive_problem(1, 1, (x, bits) -> begin
        residual_calls[] += 1
        ADAPT.AdaptiveRescueSample(ExplosiveResidual(), true, :stable)
    end)
    residual_result = ADAPT.rescue_adaptive_precision(
        explosive_residual,
        adaptive_seed([0.25]; rank=0),
    )
    @test residual_result.reason == :callback_contract_failed
    @test residual_result.work.callbacks == residual_calls[] == 1

    identity_explosive_calls = Ref(0)
    explosive_identity = ExplosiveIdentity()
    identity_problem = adaptive_problem(1, 1, (x, bits) -> begin
        identity_explosive_calls[] += 1
        ADAPT.AdaptiveRescueSample(BigFloat[x[1]], true, explosive_identity)
    end)
    explosive_identity_result = ADAPT.rescue_adaptive_precision(
        identity_problem,
        adaptive_seed([0.25]; rank=0, branch=explosive_identity),
    )
    @test explosive_identity_result.reason == :branch_identity_failed
    @test explosive_identity_result.work.callbacks == identity_explosive_calls[] == 1
end

@testset "stationary nonroot, manifold and even singular are typed unknown" begin
    stationary_calls = Ref(0)
    stationary = adaptive_problem(1, 1, (x, bits) -> begin
        stationary_calls[] += 1
        ADAPT.AdaptiveRescueSample(BigFloat[x[1]^2 + 1], true, :stable)
    end)
    stationary_result = ADAPT.rescue_adaptive_precision(
        stationary,
        adaptive_seed([0.0]; rank=0),
    )
    @test stationary_result.status == :unknown
    @test stationary_result.reason == :stationary_nonroot_or_singular
    @test stationary_result.evidence === nothing
    @test stationary_result.work.callbacks == stationary_calls[] == 5
    @test stationary_result.work.precision_weighted_oracle_work == 25

    manifold_calls = Ref(0)
    manifold = adaptive_problem(2, 2, (x, bits) -> begin
        manifold_calls[] += 1
        ADAPT.AdaptiveRescueSample(BigFloat[x[1], 2x[1]], true, :stable)
    end)
    manifold_result = ADAPT.rescue_adaptive_precision(
        manifold,
        adaptive_seed([0.0, 0.25]; rank=1),
    )
    @test manifold_result.status == :unknown
    @test manifold_result.reason == :rank_deficient_unisolated
    @test manifold_result.evidence === nothing
    @test manifold_result.work.callbacks == manifold_calls[] == 9
    @test manifold_result.work.precision_weighted_oracle_work == 45

    even_calls = Ref(0)
    even = adaptive_problem(1, 1, (x, bits) -> begin
        even_calls[] += 1
        ADAPT.AdaptiveRescueSample(BigFloat[x[1]^2], true, :stable)
    end)
    even_result = ADAPT.rescue_adaptive_precision(
        even,
        adaptive_seed([0.0]; rank=0),
    )
    @test even_result.status == :unknown
    @test even_result.reason == :rank_deficient_unisolated
    @test even_result.evidence === nothing
    @test even_result.work.callbacks == even_calls[] == 5
    @test even_result.work.precision_weighted_oracle_work == 25

    structural_calls = Ref(0)
    underdetermined = adaptive_problem(2, 1, (x, bits) -> begin
        structural_calls[] += 1
        ADAPT.AdaptiveRescueSample(BigFloat[x[1]], true, :stable)
    end)
    structural_result = ADAPT.rescue_adaptive_precision(
        underdetermined,
        adaptive_seed([0.0, 0.0]; rank=1),
    )
    @test structural_result.reason == :underdetermined_manifold
    @test structural_result.work.callbacks == structural_calls[] == 0
end

@testset "C2, branch and full-route budget failures are fail-closed" begin
    missing_calls = Ref(0)
    missing = adaptive_problem(1, 1, (x, bits) -> begin
        missing_calls[] += 1
        ADAPT.AdaptiveRescueSample(BigFloat[x[1]], true, :stable)
    end; capability=:C0)
    missing_result = ADAPT.rescue_adaptive_precision(
        missing,
        adaptive_seed([0.25]; rank=0),
    )
    @test missing_result.status == :unknown
    @test missing_result.reason == :c2_capability_missing
    @test missing_result.work.callbacks == missing_calls[] == 0

    branch_calls = Ref(0)
    branch_problem = adaptive_problem(
        1,
        1,
        (x, bits) -> begin
            branch_calls[] += 1
            branch = x[1] <= big"0.01" ? :left : :right
            ADAPT.AdaptiveRescueSample(BigFloat[x[1] - big"0.5"], true, branch)
        end;
        lower=[-1.0],
        upper=[1.0],
    )
    branch_result = ADAPT.rescue_adaptive_precision(
        branch_problem,
        adaptive_seed([0.0]; rank=0, branch=:left),
    )
    @test branch_result.status == :unknown
    @test branch_result.reason == :branch_identity_failed
    @test branch_result.evidence === nothing
    @test branch_result.work.callbacks == branch_calls[] == 11
    @test branch_result.work.precision_weighted_oracle_work == 80
    @test branch_result.work.newton_steps == 0

    matrix, root, start = linear_fixture("2^-160")
    budget_calls = Ref(0)
    budget_problem = adaptive_problem(8, 8, (x, bits) -> begin
        budget_calls[] += 1
        ADAPT.AdaptiveRescueSample(matrix * (x .- root), true, :stable)
    end)
    budget_result = ADAPT.rescue_adaptive_precision(
        budget_problem,
        adaptive_seed(start; rank=7),
        options=ADAPT.AdaptiveRescueOptions(maximum_weighted_oracle_work=499),
    )
    @test budget_result.status == :unknown
    @test budget_result.reason == :complete_route_budget_insufficient
    @test budget_result.evidence === nothing
    @test budget_result.work.callbacks == budget_calls[] == 0
    @test budget_result.work.precision_weighted_oracle_work == 0
    @test budget_result.work.tier_count == 0
end

@testset "trigger/model/precision contract and charged failures" begin
    never_calls = Ref(0)
    never = adaptive_problem(1, 1, (x, bits) -> begin
        never_calls[] += 1
        ADAPT.AdaptiveRescueSample(BigFloat[x[1]], true, :stable)
    end)
    @test ADAPT.rescue_adaptive_precision(
        never,
        adaptive_seed([0.0]; rank=1, condition=2.0),
    ).reason == :condition_trigger_not_met
    @test ADAPT.rescue_adaptive_precision(
        never,
        adaptive_seed([0.0]; rank=0, agreement=false),
    ).reason == :model_disagreement
    @test ADAPT.rescue_adaptive_precision(
        never,
        adaptive_seed([0.0]; rank=0, semantics=false),
    ).reason == :prefilter_semantics_invalid
    @test never_calls[] == 0

    downgrade_calls = Ref(0)
    downgrade = adaptive_problem(1, 1, (x, bits) -> begin
        downgrade_calls[] += 1
        ADAPT.AdaptiveRescueSample(Float64[Float64(x[1])], true, :stable)
    end)
    downgraded = ADAPT.rescue_adaptive_precision(
        downgrade,
        adaptive_seed([0.25]; rank=0),
    )
    @test downgraded.reason == :precision_downgrade
    @test downgraded.work.callbacks == downgrade_calls[] == 1
    @test downgraded.work.precision_weighted_oracle_work == 5

    throw_calls = Ref(0)
    throwing = adaptive_problem(1, 1, (x, bits) -> begin
        throw_calls[] += 1
        error("fixture callback failure")
    end; callback_cost=2)
    thrown = ADAPT.rescue_adaptive_precision(
        throwing,
        adaptive_seed([0.25]; rank=0),
    )
    @test thrown.reason == :callback_failed
    @test thrown.work.callbacks == throw_calls[] == 1
    @test thrown.work.raw_oracle_work == 2
    @test thrown.work.precision_weighted_oracle_work == 10
end

@testset "source contract is general and fixed" begin
    source = read(joinpath(@__DIR__, "..", "src", "AdaptivePrecisionRescue.jl"), String)
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
    @test ADAPT.PRECISION_TIERS == (128, 256, 512)
    @test ADAPT.FORMAL_WEIGHTED_WORK_CAP == 600
    @test ADAPT.CONDITION_TRIGGER == 1.0e8
    @test ADAPT.AdaptiveSemanticState(:compatibility).branch_margin == 1
    @test occursin("1 + 4problem.dimension", source)
    @test occursin("complete_route_budget_insufficient", source)
    @test occursin("production 512/768", source)
    @test ADAPT.REFERENCE_ADAPTED_DIFFERENCES.reference_precision_route ==
          "fixed 512 bits"
    @test occursin(
        "five-point",
        ADAPT.REFERENCE_ADAPTED_DIFFERENCES.reference_stencil,
    )
    @test occursin(
        "central two-point",
        ADAPT.REFERENCE_ADAPTED_DIFFERENCES.adapted_stencil,
    )
    @test occursin(
        "one-sided Jacobi",
        ADAPT.REFERENCE_ADAPTED_DIFFERENCES.adapted_rank_authority,
    )
    @test occursin(
        "same source model",
        ADAPT.REFERENCE_ADAPTED_DIFFERENCES.adapted_confirmation_site,
    )
    @test ADAPT.REFERENCE_ADAPTED_DIFFERENCES.adapted_d8_longest_route ==
          "599 weighted units for 128 diagnostic, 256 step, 512 confirmation"
    @test Set(ADAPT.ACTIVATION_OBSERVABLES) == Set((
        :selected_precision_bits,
        :confirmation_precision_bits,
        :precision_path,
        :calls_by_precision,
        :tier_count,
        :newton_steps,
        :source_residual_linf,
        :refined_residual_linf,
        :selected_numerical_rank,
        :confirmation_numerical_rank,
        :cross_tier_residual_disagreement,
        :cross_tier_residual_tolerance,
        :cross_tier_jacobian_disagreement,
        :cross_tier_jacobian_tolerance,
        :cross_tier_correction_disagreement,
        :cross_tier_correction_tolerance,
        :rank_stable,
        :correction_stable,
    ))
    @test Set((
        :c2_capability_missing,
        :complete_route_budget_insufficient,
        :precision_downgrade,
        :branch_identity_failed,
        :semantic_identity_failed,
        :semantic_margin_failed,
        :stationary_nonroot_or_singular,
        :rank_deficient_unisolated,
        :correction_unstable,
        :newton_step_not_residual_decreasing,
        :cross_tier_model_disagreement,
    )) <= Set(ADAPT.TYPED_BREAK_CONDITIONS)
end
