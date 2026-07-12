using LinearAlgebra
using Random
using Test

include(joinpath(@__DIR__, "..", "src", "soft_tgo_ordering.jl"))
using .StageCSoftTGOOrdering

struct OpaqueBranchToken
    identity::Int
end
Base.isequal(left::OpaqueBranchToken, right::OpaqueBranchToken) =
    left.identity == right.identity
Base.hash(::OpaqueBranchToken, hash_value::UInt) = error("branch tokens must not be hashed")
Base.show(io::IO, ::OpaqueBranchToken) = error("branch tokens must not be displayed")
Base.isless(::OpaqueBranchToken, ::OpaqueBranchToken) =
    error("branch tokens must not be ordered")

struct ThrowingBranchToken
    identity::Int
end
Base.isequal(::ThrowingBranchToken, ::ThrowingBranchToken) =
    error("malformed plugin equality")

candidate(ordinal, point, residual; branch=:branch, valid=true) = OrderingCandidate(
    ordinal,
    point,
    residual;
    branch_token=branch,
    canonical_valid=valid,
)

source_schedule(result, candidates) =
    [candidates[index].source_ordinal for index in result.permutation]

@testset "finite-box contract and global FIFO control" begin
    candidates = [
        candidate(30, [0.0, 0.0], [3.0]),
        candidate(10, [0.1, 0.1], [1.0]),
        candidate(20, [-0.1, -0.1], [2.0]; valid=false),
    ]
    result = order_fixed_batch(
        candidates, [-1.0, -1.0], [1.0, 1.0];
        arm=FIFO_SCORED,
        branch_capability=true,
    )
    @test result.permutation == [2, 3, 1]
    @test source_schedule(result, candidates) == [10, 20, 30]
    @test result.diagnostics.batch_size == 3
    @test result.diagnostics.scored_count == 2
    @test result.diagnostics.fallback_count == 1
    @test result.diagnostics.branch_partition_count == 1
    @test result.diagnostics.branch_capability
    @test result.diagnostics.normalization_well_resolved
    @test result.diagnostics.all_candidates_drained
    @test result.diagnostics.rounds == 1
    @test all(group.neighbor_k == 0 for group in result.diagnostics.groups)
    @test all(isempty(group.local_minimum_source_ordinals)
              for group in result.diagnostics.groups)

    empty_result = order_fixed_batch(
        OrderingCandidate[], [-1.0], [1.0];
        arm=SOFT_TGO,
        branch_capability=false,
    )
    @test isempty(empty_result.permutation)
    @test empty_result.diagnostics.all_candidates_drained
    @test empty_result.diagnostics.rounds == 0

    duplicate = [candidate(1, [0.0], [1.0]), candidate(1, [0.1], [2.0])]
    @test_throws ArgumentError order_fixed_batch(
        duplicate, [-1.0], [1.0]; arm=SOFT_TGO, branch_capability=true,
    )
    @test_throws ArgumentError order_fixed_batch(
        candidates, [-Inf, -1.0], [1.0, 1.0];
        arm=SOFT_TGO,
        branch_capability=true,
    )
end

@testset "under-resolved affine boxes use the finite FIFO fallback" begin
    points = [[x] for x in (-0.9, -0.6, -0.3, 0.0, 0.3, 0.6, 0.9)]
    residuals = (10.0, 8.0, 9.0, 7.0, 1.0, 2.0, 3.0)
    base = [candidate(index, points[index], [residuals[index]])
            for index in eachindex(points)]
    offset = 1.0e14
    scale = 0.06165950018614822
    replica = [candidate(
        item.source_ordinal,
        offset .+ scale .* item.point,
        item.scaled_residual;
        branch=item.branch_token,
    ) for item in base]
    lower = [offset - scale]
    upper = [offset + scale]
    @test length(unique(only(item.point) for item in replica)) == 7
    for arm in (FIFO_SCORED, RESIDUAL_ONLY, SOFT_TGO)
        result = order_fixed_batch(
            replica, lower, upper; arm, branch_capability=true,
        )
        @test !result.diagnostics.normalization_well_resolved
        @test result.diagnostics.scored_count == 0
        @test result.diagnostics.fallback_count == 7
        @test source_schedule(result, replica) == collect(1:7)
        @test result.diagnostics.all_candidates_drained
    end
end

@testset "malformed opaque equality stays conservative and finite" begin
    candidates = [
        candidate(3, fill(0.3, 8), [3.0]; branch=ThrowingBranchToken(1)),
        candidate(1, fill(0.1, 8), [1.0]; branch=ThrowingBranchToken(1)),
        candidate(2, fill(0.2, 8), [2.0]; branch=ThrowingBranchToken(2)),
    ]
    for arm in (FIFO_SCORED, RESIDUAL_ONLY, SOFT_TGO)
        result = order_fixed_batch(
            candidates, fill(-1.0, 8), fill(1.0, 8);
            arm,
            branch_capability=true,
        )
        @test sort(result.permutation) == collect(1:3)
        @test result.diagnostics.all_candidates_drained
        @test result.diagnostics.branch_partition_count == 3
        arm == SOFT_TGO && @test all(
            group.neighbor_k == 0 for group in result.diagnostics.groups
        )
    end
end

@testset "branch capability distinguishes absence from a missing observation token" begin
    absent = [
        candidate(1, [-0.5], [4.0]; branch=nothing),
        candidate(2, [0.0], [1.0]; branch=nothing),
        candidate(3, [0.5], [2.0]; branch=nothing),
    ]
    no_capability = order_fixed_batch(
        absent, [-1.0], [1.0];
        arm=RESIDUAL_ONLY,
        branch_capability=false,
    )
    @test source_schedule(no_capability, absent) == [2, 3, 1]
    @test no_capability.diagnostics.scored_count == 3
    @test no_capability.diagnostics.fallback_count == 0
    @test no_capability.diagnostics.branch_partition_count == 1
    @test !no_capability.diagnostics.branch_capability

    token_required = order_fixed_batch(
        absent, [-1.0], [1.0];
        arm=RESIDUAL_ONLY,
        branch_capability=true,
    )
    @test source_schedule(token_required, absent) == [1, 2, 3]
    @test token_required.diagnostics.scored_count == 0
    @test token_required.diagnostics.fallback_count == 3
    @test token_required.diagnostics.branch_partition_count == 0
    @test only(token_required.diagnostics.groups).fallback

    # A disabled branch capability ignores even adversarial token identities.
    token_ignored = [
        candidate(1, [-0.5], [4.0]; branch=OpaqueBranchToken(1)),
        candidate(2, [0.0], [1.0]; branch=OpaqueBranchToken(2)),
        candidate(3, [0.5], [2.0]; branch=nothing),
    ]
    ignored = order_fixed_batch(
        token_ignored, [-1.0], [1.0];
        arm=RESIDUAL_ONLY,
        branch_capability=false,
    )
    @test source_schedule(ignored, token_ignored) == [2, 3, 1]
    @test ignored.diagnostics.branch_partition_count == 1
end

@testset "branch-local residual order and deterministic round robin" begin
    branch_a = OpaqueBranchToken(1)
    branch_b = OpaqueBranchToken(2)
    candidates = [
        candidate(1, [-0.8, 0.0], [10.0]; branch=branch_a),
        candidate(2, [0.8, 0.0], [1.0]; branch=branch_b),
        candidate(3, [-0.4, 0.0], [1.0]; branch=branch_a),
        candidate(4, [NaN, 0.0], [NaN]; branch=branch_a),
        candidate(5, [0.4, 0.0], [5.0]; branch=branch_b),
        candidate(6, [0.0, 0.0], [2.0]; branch=branch_a),
        candidate(7, [0.2, 0.0], [0.0]; branch=nothing),
    ]
    result = order_fixed_batch(
        candidates, [-1.0, -1.0], [1.0, 1.0];
        arm=RESIDUAL_ONLY,
        branch_capability=true,
    )
    # Branch A, branch B, and the fallback group are visited in first-source
    # order.  Residual 10 in A is not globally delayed behind every B point.
    @test source_schedule(result, candidates) == [3, 2, 4, 6, 5, 7, 1]
    @test result.diagnostics.group_first_source_ordinals == [1, 2, 4]
    @test result.diagnostics.rounds == 3
    @test result.diagnostics.scored_count == 5
    @test result.diagnostics.fallback_count == 2
    @test result.diagnostics.all_candidates_drained
    @test sort(result.permutation) == collect(eachindex(candidates))
    @test all(group.neighbor_k == 0 for group in result.diagnostics.groups)
end

@testset "soft topograph advances local minima but drains the batch" begin
    points = [[x] for x in (-0.9, -0.6, -0.3, 0.0, 0.3, 0.6, 0.9)]
    residuals = (10.0, 8.0, 9.0, 7.0, 1.0, 2.0, 3.0)
    candidates = [candidate(index, points[index], [residuals[index]])
                  for index in eachindex(points)]
    residual_only = order_fixed_batch(
        candidates, [-1.0], [1.0];
        arm=RESIDUAL_ONLY,
        branch_capability=true,
    )
    soft = order_fixed_batch(
        candidates, [-1.0], [1.0];
        arm=SOFT_TGO,
        branch_capability=true,
    )
    @test source_schedule(residual_only, candidates) == [5, 6, 7, 4, 2, 3, 1]
    # Ordinal 2 is a topographic local minimum (8 < 10,9), so it moves ahead of
    # distant lower-residual points without suppressing any of them.
    @test source_schedule(soft, candidates) == [5, 2, 6, 7, 4, 3, 1]
    group = only(soft.diagnostics.groups)
    @test group.neighbor_k == 2
    @test group.local_minimum_source_ordinals == [2, 5]
    @test group.neighborhood_source_ordinals == collect(1:7)
    @test all(==(2), group.neighborhood_sizes)
    @test soft.diagnostics.all_candidates_drained
    @test sort(soft.permutation) == collect(1:7)
end

@testset "kth-distance shell uses inclusive roundoff-stable neighborhoods" begin
    radius = 0.5
    ring = [[radius * cos(2pi * index / 5), radius * sin(2pi * index / 5)]
            for index in 0:4]
    points = vcat([[0.0, 0.0]], ring)
    candidates = [candidate(index, points[index], [Float64(index)])
                  for index in eachindex(points)]
    result = order_fixed_batch(
        candidates, [-1.0, -1.0], [1.0, 1.0];
        arm=SOFT_TGO,
        branch_capability=true,
    )
    group = only(result.diagnostics.groups)
    @test group.neighbor_k == 4
    center_position = findfirst(==(1), group.neighborhood_source_ordinals)
    @test group.neighborhood_sizes[center_position] == 5
    @test length(result.permutation) == 6

    angle = 0.371
    rotation = [cos(angle) -sin(angle); sin(angle) cos(angle)]
    rotated = [candidate(
        item.source_ordinal,
        rotation * item.point,
        item.scaled_residual;
        branch=item.branch_token,
        valid=item.canonical_valid,
    ) for item in candidates]
    replica = order_fixed_batch(
        rotated, [-1.0, -1.0], [1.0, 1.0];
        arm=SOFT_TGO,
        branch_capability=true,
    )
    replica_group = only(replica.diagnostics.groups)
    replica_center = findfirst(==(1), replica_group.neighborhood_source_ordinals)
    @test replica_group.neighborhood_sizes[replica_center] == 5
    @test source_schedule(replica, rotated) == source_schedule(result, candidates)
end

function transformed_candidates(candidates, point_transform, residual_transform, token_transform)
    return [candidate(
        item.source_ordinal,
        point_transform(item.point),
        residual_transform(item.scaled_residual);
        branch=token_transform(item.branch_token),
        valid=item.canonical_valid,
    ) for item in candidates]
end

function topology_signature(result)
    return (
        result.diagnostics.scored_count,
        result.diagnostics.fallback_count,
        result.diagnostics.branch_partition_count,
        result.diagnostics.group_first_source_ordinals,
        [group.local_minimum_source_ordinals for group in result.diagnostics.groups],
        [group.neighborhood_sizes for group in result.diagnostics.groups],
    )
end

@testset "representation invariance and opaque branch renaming" begin
    token_a = OpaqueBranchToken(10)
    token_b = OpaqueBranchToken(20)
    points = (
        [-0.55, -0.10], [-0.35, 0.15], [-0.05, -0.25], [0.25, 0.20],
        [0.45, -0.15], [0.10, 0.55], [-0.20, 0.40], [0.55, 0.05],
    )
    scores = (9.0, 5.0, 8.0, 1.0, 7.0, 3.0, 6.0, 2.0)
    candidates = [candidate(
        index,
        points[index],
        [scores[index], scores[index] / 7, -scores[index] / 11];
        branch=isodd(index) ? token_a : token_b,
    ) for index in eachindex(points)]
    reference = order_fixed_batch(
        candidates, [-1.0, -1.0], [1.0, 1.0];
        arm=SOFT_TGO,
        branch_capability=true,
    )
    reference_schedule = source_schedule(reference, candidates)
    reference_signature = topology_signature(reference)

    offset = [7.0, -11.0]
    # Both affine boxes remain above the frozen normalization-resolution gate.
    physical_scale = [13.0, 2.0]
    scaled = transformed_candidates(
        candidates,
        point -> offset .+ physical_scale .* point,
        identity,
        identity,
    )
    scaled_result = order_fixed_batch(
        scaled,
        offset .- physical_scale,
        offset .+ physical_scale;
        arm=SOFT_TGO,
        branch_capability=true,
    )

    signed_permutation = [0.0 -1.0; 1.0 0.0]
    signed = transformed_candidates(
        candidates,
        point -> signed_permutation * point,
        residual -> residual[[3, 1, 2]],
        token -> token.identity == 10 ? OpaqueBranchToken(991) : OpaqueBranchToken(-4),
    )
    signed_result = order_fixed_batch(
        signed, [-1.0, -1.0], [1.0, 1.0];
        arm=SOFT_TGO,
        branch_capability=true,
    )

    angle = -0.413
    orthogonal = [cos(angle) -sin(angle); sin(angle) cos(angle)]
    rotated = transformed_candidates(candidates, point -> orthogonal * point, identity, identity)
    rotated_result = order_fixed_batch(
        rotated, [-1.0, -1.0], [1.0, 1.0];
        arm=SOFT_TGO,
        branch_capability=true,
    )

    for (replica, replica_candidates) in (
        (scaled_result, scaled),
        (signed_result, signed),
        (rotated_result, rotated),
    )
        @test source_schedule(replica, replica_candidates) == reference_schedule
        @test topology_signature(replica) == reference_signature
    end
end

@testset "residual ties use source ordinal and malformed points remain serviced" begin
    candidates = [
        candidate(4, [0.4], [3.0, 4.0]),
        candidate(2, [0.2], [-4.0, 3.0]),
        candidate(3, [2.0], [0.0]),
        candidate(1, [0.1], [1.0e308, 1.0e-308]),
        candidate(5, [0.5], Float64[]),
    ]
    result = order_fixed_batch(
        candidates, [-1.0], [1.0];
        arm=RESIDUAL_ONLY,
        branch_capability=true,
    )
    # Ordinals 2 and 4 both have norm 5; ordinal 2 wins the tie.  Out-of-box and
    # empty-residual observations are in a FIFO group and still appear once.
    @test source_schedule(result, candidates) == [2, 3, 4, 5, 1]
    @test result.diagnostics.fallback_count == 2
    @test result.diagnostics.all_candidates_drained
end

@testset "audit seed 991 residual-orthogonal score intervals" begin
    # Independent audit fixture: exact Float64 score ordering flips under an
    # orthogonal residual-row replica.  Branch-wide overlapping score intervals
    # must assign ordinals 2 and 5 one component before either ordering arm runs.
    rng = MersenneTwister(991)
    residual_dimension = 15
    a = randn(rng, residual_dimension)
    a ./= norm(a)
    b = randn(rng, residual_dimension)
    b ./= norm(b)
    _ = Matrix(qr(randn(rng, residual_dimension, residual_dimension)).Q)
    orthogonal = Matrix(qr(randn(rng, residual_dimension, residual_dimension)).Q)

    points = [[x] for x in (-0.9, -0.6, -0.3, 0.0, 0.3, 0.6, 0.9)]
    axis_residual(value) = vcat([value], zeros(residual_dimension - 1))
    residuals = [
        axis_residual(10.0),
        b,
        axis_residual(9.0),
        axis_residual(7.0),
        a,
        axis_residual(2.0),
        axis_residual(3.0),
    ]
    candidates = [candidate(index, points[index], residuals[index])
                  for index in eachindex(points)]
    replica = [candidate(
        index,
        points[index],
        orthogonal * residuals[index],
    ) for index in eachindex(points)]

    base_scores = StageCSoftTGOOrdering._scaled_residual_norm.(residuals)
    replica_scores = StageCSoftTGOOrdering._scaled_residual_norm.(
        [item.scaled_residual for item in replica],
    )
    @test base_scores[5] == 1.0
    @test base_scores[2] == nextfloat(1.0)
    @test replica_scores[5] == replica_scores[2] == nextfloat(1.0)

    expected = [2, 5, 6, 7, 4, 3, 1]
    for arm in (RESIDUAL_ONLY, SOFT_TGO)
        base_result = order_fixed_batch(
            candidates, [-1.0], [1.0]; arm, branch_capability=true,
        )
        replica_result = order_fixed_batch(
            replica, [-1.0], [1.0]; arm, branch_capability=true,
        )
        @test source_schedule(base_result, candidates) == expected
        @test source_schedule(replica_result, replica) == expected
        @test topology_signature(base_result) == topology_signature(replica_result)
    end
end

@testset "score-interval overlap is closed transitively" begin
    nextfloats(value, count) = foldl((current, _) -> nextfloat(current), 1:count; init=value)
    candidates = [
        candidate(3, [-0.5], [1.0]),
        candidate(2, [0.0], [nextfloats(1.0, 200)]),
        candidate(1, [0.5], [nextfloats(1.0, 400)]),
    ]
    result = order_fixed_batch(
        candidates, [-1.0], [1.0];
        arm=RESIDUAL_ONLY,
        branch_capability=true,
    )
    # Adjacent intervals overlap while the two endpoints do not.  Connected
    # component closure gives one transitive rank, then source ordinal orders it.
    @test source_schedule(result, candidates) == [1, 2, 3]
end
