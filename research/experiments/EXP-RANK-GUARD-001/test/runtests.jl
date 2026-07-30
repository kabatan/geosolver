using LinearAlgebra
using Test

include(joinpath(@__DIR__, "..", "src", "RankGuardPrototype.jl"))
const RG = RankGuardPrototype
const LAB = RG.LAB
const FIX = LAB.FIXTURES

function synthetic_fixture(matrix; start=zeros(size(matrix, 2)), semantics=nothing)
    n = size(matrix, 2)
    semantic = semantics === nothing ?
               (_ -> (:branch, :guard, :domain, 1.0, 1.0, 1.0, true)) :
               semantics
    evaluate = function (point)
        branch, guard, domain, branch_margin, guard_margin, domain_margin, valid =
            semantic(point)
        return FIX.FixtureEvaluation(
            matrix * Float64[point...],
            0.0,
            branch,
            guard,
            domain,
            branch_margin,
            guard_margin,
            domain_margin,
            valid,
        )
    end
    return (;
        box=FIX.FiniteBox(n),
        evaluate_float64=evaluate,
        evaluate_arbitrary=nothing,
        starts=[Float64[start...]],
    )
end

@testset "zero precision buckets have one canonical no-work representation" begin
    @test RG.normalized_precision_ledger(Dict("512" => 0)) == Dict{String,Int}()
    @test RG.normalized_precision_ledger(Dict("float64" => 8, "512" => 0)) ==
          Dict("float64" => 8)
    @test_throws ArgumentError RG.normalized_precision_ledger(Dict("128" => -1))
end

@testset "finite strict guard chart is stable and interior" begin
    chart = RG.GuardChart([-1.0, 0.0], [1.0, 2.0])
    for point in ([-0.999999, 1.0e-8], [0.0, 1.0], [0.999999, 1.999999])
        recovered = RG.chart_to_physical(chart, RG.physical_to_chart(chart, point))
        @test recovered ≈ point rtol=2e-9 atol=2e-12
        @test all((chart.lower .< recovered) .& (recovered .< chart.upper))
    end
    extreme = RG.chart_to_physical(chart, [1.0e6, -1.0e6])
    @test all((chart.lower .< extreme) .& (extreme .< chart.upper))
end

@testset "weak right-singular proposals are symmetric, charged, and ablatable" begin
    fixture = synthetic_fixture(Diagonal([1.0, 1.0e-12]))
    prefilter = LAB.acquire_shared_prefilter(fixture, fixture.starts[1])
    @test prefilter.status == :ready
    observed_direct = Ref(0)
    direct = RG.weak_singular_proposals(
        fixture,
        prefilter;
        charted=false,
        observe_callback=bits -> begin
            @test bits == 53
            observed_direct[] += 1
        end,
    )
    observed_chart = Ref(0)
    chart = RG.weak_singular_proposals(
        fixture,
        prefilter;
        charted=true,
        observe_callback=bits -> begin
            @test bits == 53
            observed_chart[] += 1
        end,
    )
    @test direct.status == chart.status == :seeded
    @test direct.activated && chart.activated
    @test direct.callbacks == observed_direct[] == 4
    @test chart.callbacks == observed_chart[] == 4
    @test length(direct.proposals) == length(chart.proposals) == 4
    @test all(!proposal.charted for proposal in direct.proposals)
    @test all(proposal.charted for proposal in chart.proposals)
    for result in (direct, chart), index in (1, 3)
        left = result.proposals[index].coordinates
        right = result.proposals[index + 1].coordinates
        @test (left + right) / 2 ≈ prefilter.endpoint atol=2e-10
    end
end

@testset "semantic crossing rejects a complete pair without narrowing baseline" begin
    semantics = point -> (
        :branch,
        point[2] > 1.0e-3 ? :outside : :inside,
        :domain,
        1.0,
        1.0,
        1.0,
        true,
    )
    fixture = synthetic_fixture(Diagonal([1.0, 1.0e-12]); semantics)
    prefilter = LAB.acquire_shared_prefilter(fixture, fixture.starts[1])
    @test prefilter.status == :ready
    result = RG.weak_singular_proposals(fixture, prefilter)
    @test result.status == :unknown
    @test result.reason == :no_semantics_valid_pair
    @test result.activated
    @test result.callbacks == 4
    @test isempty(result.proposals)
    @test result.route.semantic_rejections == 2
    baseline = LAB.run_no_rescue_arm(prefilter.endpoint)
    @test baseline.status == :control
    @test baseline.rescue_weighted_work == 0
    @test baseline.point_seeds == Tuple[Tuple(prefilter.endpoint)]
end

@testset "guard chart proposals remain strictly inside finite bounds" begin
    fixture = synthetic_fixture(Diagonal([1.0, 1.0e-12]); start=[0.0, 0.99])
    prefilter = LAB.acquire_shared_prefilter(fixture, fixture.starts[1])
    @test prefilter.status == :ready
    result = RG.weak_singular_proposals(
        fixture,
        prefilter;
        charted=true,
        trust_radius=0.5,
        guard_fraction=1.0,
    )
    @test result.status == :seeded
    @test all(proposal -> all(
        (fixture.box.lower .< proposal.coordinates) .&
        (proposal.coordinates .< fixture.box.upper),
    ), result.proposals)
end
