using LinearAlgebra
using Test

include(joinpath(@__DIR__, "..", "src", "simplicial_star_emitter.jl"))
using .SimplicialStarEmitter

observation(residual; branch=:branch, valid=true) =
    SimplicialObservation(residual; branch_token=branch, canonical_valid=valid)

struct OpaqueBranchToken
    identity::Int
end
Base.isequal(left::OpaqueBranchToken, right::OpaqueBranchToken) =
    left.identity == right.identity
Base.hash(::OpaqueBranchToken, ::UInt) = error("opaque branch token was hashed")
Base.show(::IO, ::OpaqueBranchToken) = error("opaque branch token was displayed")
Base.isless(::OpaqueBranchToken, ::OpaqueBranchToken) =
    error("opaque branch token was ordered")

function point_multiset(plan; transport=identity)
    rows = [Tuple(map(value -> iszero(value) ? 0.0 : round(value; digits=14),
                      transport(item.point)))
            for item in plan.proposals]
    return sort(rows)
end

exact_point_multiset(plan; transport=identity) =
    sort([Tuple(transport(item.point)) for item in plan.proposals])

function check_service(pair, calls)
    report = pair.star.report
    @test calls == report.base_vertex_count + report.refinement_count +
          pair.unguided.report.refinement_count
    @test pair.unguided.report.base_vertex_count == report.base_vertex_count
    for plan in (pair.unguided, pair.star)
        @test length(plan.proposals) == plan.report.logical_prescores
        @test plan.report.logical_screening_callbacks == 48
        @test length(plan.fallbacks) == plan.report.fallback_requests
        @test plan.report.logical_prescores + plan.report.fallback_requests ==
              plan.report.logical_screening_callbacks
        @test length(plan.proposals) + length(plan.fallbacks) == 48
        @test [item.slot for item in plan.fallbacks] ==
              collect((length(plan.proposals) + 1):48)
        @test plan.report.all_prescores_returned
        @test plan.report.shared_base_evaluation == plan.report.applicable
        @test !plan.report.answer_authority
        @test !plan.report.homology_authority
        @test !plan.report.completeness_authority
        @test count(item -> item.kind == :base, plan.proposals) ==
              plan.report.base_vertex_count
    end
end

@testset "paired base proposal ownership is arm-local" begin
    pair = plan_simplicial_pair(
        point -> observation(point), fill(-1.0, 2), fill(1.0, 2);
        branch_capability=true,
    )
    base_count = pair.star.report.base_vertex_count
    unguided_base = pair.unguided.proposals[1:base_count]
    star_base = pair.star.proposals[1:base_count]
    @test all(left.point == right.point for (left, right) in zip(unguided_base, star_base))
    @test all(left.point !== right.point for (left, right) in zip(unguided_base, star_base))
    star_snapshot = copy(star_base[1].point)
    other_unguided_snapshot = copy(unguided_base[2].point)
    unguided_base[1].point[1] = 123.0
    @test star_base[1].point == star_snapshot
    @test unguided_base[2].point == other_unguided_snapshot
    star_base[2].point[2] = -456.0
    @test unguided_base[2].point == other_unguided_snapshot

    fresh = plan_simplicial_pair(
        point -> observation(point), fill(-1.0, 2), fill(1.0, 2);
        branch_capability=true,
    )
    @test fresh.unguided.proposals[1].point == star_snapshot
end

@testset "finite normalized box, fixed caps, and typed fallback" begin
    @test SimplicialStarEmitter.EMITTER_SLOTS == 48
    @test SimplicialStarEmitter.MAX_BASE_VERTICES == 48
    @test SimplicialStarEmitter.MAX_SIMPLICES == 256
    @test SimplicialStarEmitter.MAX_INCIDENCES == 1_024
    calls = Ref(0)
    evaluate = point -> begin
        calls[] += 1
        observation(point)
    end
    pair = plan_simplicial_pair(
        evaluate, [-2.0, 10.0], [4.0, 14.0]; branch_capability=true,
    )
    @test pair.star.report.applicable
    @test pair.star.report.reason == :applicable
    @test pair.star.report.base_vertex_count == 2^2 + 1
    @test pair.star.report.simplex_count == 4
    @test all(item.reason == :iid_fill for item in pair.star.fallbacks)
    check_service(pair, calls[])

    underresolved_calls = Ref(0)
    offset, radius = 1.0e14, 0.06165950018614822
    underresolved = plan_simplicial_pair(
        point -> begin
            underresolved_calls[] += 1
            observation(point)
        end,
        [offset - radius], [offset + radius]; branch_capability=true,
    )
    @test !underresolved.star.report.applicable
    @test underresolved.star.report.reason == :normalization_underresolved
    @test underresolved_calls[] == 0
    @test all(item.reason == :normalization_underresolved
              for item in underresolved.star.fallbacks)
    check_service(underresolved, 0)

    capped_calls = Ref(0)
    capped = plan_simplicial_pair(
        point -> begin
            capped_calls[] += 1
            observation(point)
        end,
        fill(-1.0, 6), fill(1.0, 6); branch_capability=true,
    )
    @test !capped.star.report.applicable
    @test capped.star.report.reason == :base_vertex_cap
    @test capped.star.report.dimension == 6
    @test capped_calls[] == 0
    check_service(capped, 0)
end

@testset "flat ties round-robin finitely and overflow-safe scores stay valid" begin
    calls = Ref(0)
    pair = plan_simplicial_pair(
        point -> begin
            calls[] += 1
            observation(fill(floatmax(Float64), 2))
        end,
        fill(-1.0, 3), fill(1.0, 3); branch_capability=true,
    )
    @test pair.star.report.combinatorial_minimum_count == 9
    @test pair.star.report.refinement_count == 24
    @test length(pair.star.fallbacks) == 15
    @test all(item.canonical_valid && item.score < 1 for item in pair.star.proposals)
    @test all(item.score == pair.star.proposals[1].score for item in pair.star.proposals)
    check_service(pair, calls[])

    for dimension in 3:5
        signed_cycle = zeros(dimension, dimension)
        for axis in 1:dimension
            signed_cycle[mod1(axis + 1, dimension), axis] = 1
        end
        signed_cycle[1, :] .*= -1
        flat = point -> observation([3.0]; branch=:b)
        original = plan_simplicial_pair(
            flat, fill(-1.0, dimension), fill(1.0, dimension);
            branch_capability=true,
        )
        replica = plan_simplicial_pair(
            flat, fill(-1.0, dimension), fill(1.0, dimension);
            branch_capability=true,
        )
        for field in (:unguided, :star)
            left, right = getproperty(original, field), getproperty(replica, field)
            @test exact_point_multiset(left) == exact_point_multiset(
                right; transport=point -> transpose(signed_cycle) * point,
            )
            @test left.report.logical_screening_callbacks ==
                  right.report.logical_screening_callbacks == 48
        end
    end
end

@testset "invalid island and callback failures are retained at score one" begin
    calls = Ref(0)
    pair = plan_simplicial_pair(
        point -> begin
            calls[] += 1
            point == [-1.0, -1.0] && error("opaque invalid domain")
            valid = maximum(abs, point) < 0.6
            observation(point; branch=valid ? :island : nothing, valid)
        end,
        fill(-1.0, 2), fill(1.0, 2); branch_capability=true,
    )
    @test pair.star.report.combinatorial_minimum_count == 1
    @test pair.star.report.refinement_count == 4
    for plan in (pair.unguided, pair.star)
        base = filter(item -> item.kind == :base, plan.proposals)
        @test count(!, getproperty.(base, :canonical_valid)) == 4
        @test all(item.score == 1 for item in base if !item.canonical_valid)
        @test any(item.callback_failed for item in base)
        @test all(item in plan.proposals for item in base)
    end
    check_service(pair, calls[])
end

@testset "all-invalid evidence cannot starve the independent control" begin
    calls = Ref(0)
    opaque = OpaqueBranchToken(7)
    pair = plan_simplicial_pair(
        point -> begin
            calls[] += 1
            observation([NaN]; branch=opaque, valid=false)
        end,
        fill(-1.0, 2), fill(1.0, 2); branch_capability=true,
    )
    @test pair.star.report.combinatorial_minimum_count == 0
    @test pair.star.report.refinement_count == 0
    @test pair.unguided.report.refinement_count == 12
    @test length(pair.star.proposals) == 5
    @test length(pair.star.fallbacks) == 43
    @test length(pair.unguided.proposals) == 17
    @test length(pair.unguided.fallbacks) == 31
    for plan in (pair.unguided, pair.star)
        @test all(!item.canonical_valid && item.score == 1 for item in plan.proposals)
    end
    check_service(pair, calls[])
end

@testset "an interior basin is emitted without answer authority" begin
    target = [0.0, 1 / 3]
    calls = Ref(0)
    pair = plan_simplicial_pair(
        point -> begin
            calls[] += 1
            observation(point .- target)
        end,
        fill(-1.0, 2), fill(1.0, 2); branch_capability=true,
    )
    base_score = minimum(item.score for item in pair.star.proposals if item.kind == :base)
    interior = filter(item -> item.kind == :star, pair.star.proposals)
    @test any(item -> all(abs.(item.point) .< 1), interior)
    @test minimum(item.score for item in interior) < base_score
    @test any(item -> item.score == 0, interior)
    check_service(pair, calls[])
end

@testset "branch-compatible combinatorial minima" begin
    branch_a, branch_b = OpaqueBranchToken(1), OpaqueBranchToken(2)
    evaluator(point) = point[1] < -0.5 ? observation([4.0]; branch=branch_a) :
        point[1] > 0.5 ? observation([1.0]; branch=branch_b) :
        observation([3.0]; branch=branch_a)
    branch_local = plan_simplicial_pair(
        evaluator, [-1.0], [1.0]; branch_capability=true,
    )
    branch_ignored = plan_simplicial_pair(
        evaluator, [-1.0], [1.0]; branch_capability=false,
    )
    @test branch_local.star.report.combinatorial_minimum_count == 2
    @test branch_ignored.star.report.combinatorial_minimum_count == 1
end

@testset "signed permutation and triangulation bookkeeping replicas" begin
    matrix = [2.0 0.0; 0.0 1.0]
    signed_permutation = [0.0 -1.0; 1.0 0.0]
    reference = plan_simplicial_pair(
        point -> observation(matrix * point),
        fill(-1.0, 2), fill(1.0, 2); branch_capability=true,
    )
    replica = plan_simplicial_pair(
        point -> observation(matrix * transpose(signed_permutation) * point),
        fill(-1.0, 2), fill(1.0, 2); branch_capability=true,
    )
    for field in (:unguided, :star)
        original_plan = getproperty(reference, field)
        replica_plan = getproperty(replica, field)
        @test point_multiset(original_plan) == point_multiset(
            replica_plan; transport=point -> transpose(signed_permutation) * point,
        )
        @test original_plan.report.refinement_count == replica_plan.report.refinement_count
    end

    box, reason = SimplicialStarEmitter._normalized_box(fill(-1.0, 2), fill(1.0, 2))
    @test reason == :applicable
    points = SimplicialStarEmitter._base_vertices(2, 4)
    simplices = SimplicialStarEmitter._simplices(2, 4)
    vertex_order = [5, 3, 1, 4, 2]
    inverse_order = invperm(vertex_order)
    remapped = [Tuple(sort([inverse_order[vertex] for vertex in simplex]))
                for simplex in reverse(simplices)]
    evaluator = point -> observation(point .- [0.9, 0.8])
    original = SimplicialStarEmitter._plan_with_simplices(
        evaluator, box, points, simplices; branch_capability=true,
    )
    reordered = SimplicialStarEmitter._plan_with_simplices(
        evaluator, box, points[vertex_order], remapped; branch_capability=true,
    )
    for field in (:unguided, :star)
        left, right = getproperty(original, field), getproperty(reordered, field)
        @test point_multiset(left) == point_multiset(right)
        @test left.report.refinement_count == right.report.refinement_count
        @test left.report.combinatorial_minimum_count ==
              right.report.combinatorial_minimum_count
    end
end
