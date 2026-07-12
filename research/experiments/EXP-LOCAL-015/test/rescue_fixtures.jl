using LinearAlgebra
using Test

include(joinpath(@__DIR__, "..", "src", "RescueFixtures.jl"))
using .RescueFixtures

const EXPECTED_CORPUS_CHECKSUM =
    "e80d0929d6e6af6a53724f2997d78fc70075ae40da631e0e324604ea00e81377"

exact_big(value) = BigFloat(numerator(value)) / BigFloat(denominator(value))
exact_big(values::AbstractVector) = BigFloat[exact_big(value) for value in values]

function exact_residual_is_zero(record, point)
    observation = RescueFixtures._evaluate(record.private_model, point)
    return all(iszero, observation.residual)
end

@testset "corpus shape, deterministic starts, and replay freeze" begin
    first = rescue_fixture_corpus()
    second = rescue_fixture_corpus()
    @test length(first) == length(second) == 21
    @test count(record -> record.descriptor.stratum == :ill_conditioned_full_rank, first) == 9
    @test count(record -> record.descriptor.stratum == :clustered_weak_lane, first) == 6
    @test count(record -> record.descriptor.stratum == :safety_control, first) == 6
    @test Set(record.descriptor.dimension for record in first if
              record.descriptor.stratum != :safety_control) == Set((2, 4, 8))

    checksums = replay_checksum.(first)
    @test checksums == replay_checksum.(second)
    @test length(unique(checksums)) == length(checksums)
    @test all(checksum -> occursin(r"^[0-9a-f]{64}$", checksum), checksums)
    @test corpus_replay_checksum(first) == corpus_replay_checksum(second) ==
          EXPECTED_CORPUS_CHECKSUM

    for index in eachindex(first)
        left = candidate_view(first[index])
        right = candidate_view(second[index])
        @test left.starts == right.starts
        @test length(left.starts) == 16
        @test left.starts[1] == zeros(first[index].descriptor.dimension)
        @test all(start -> length(start) == first[index].descriptor.dimension, left.starts)
        @test all(start -> norm(start, 2) <= 0.600000000000001, left.starts)
        @test all(start -> all(left.box.lower .< start .< left.box.upper), left.starts)
        @test all(isfinite, reduce(vcat, left.starts))
    end

    @test_throws ArgumentError make_linear_fixture(3, 10^12)
    @test_throws ArgumentError make_linear_fixture(2, 10^6)
    @test_throws ArgumentError make_clustered_fixture(2, 6)
    @test_throws ArgumentError make_safety_fixture(:named_case_patch)
end

@testset "candidate seam contains no assessor identity or truth" begin
    record = make_clustered_fixture(4, 8)
    candidate = candidate_view(record)
    @test fieldnames(TruthBlindFixture) ==
          (:box, :evaluate_float64, :evaluate_arbitrary, :starts)
    @test propertynames(candidate) == fieldnames(TruthBlindFixture)
    forbidden = ("id", "stratum", "condition", "root", "gold", "checksum", "family")
    @test all(name -> all(token -> !occursin(token, lowercase(String(name))), forbidden),
              propertynames(candidate))
    @test !hasproperty(candidate, :descriptor)
    @test !hasproperty(candidate, :assessor)
    @test !hasproperty(candidate, :targets)
    @test !hasproperty(candidate, :replay_checksum)
    @test candidate !== record
    @test assessor_truth(record) === record.assessor
    @test_throws MethodError assessor_truth(candidate)

    observation = candidate.evaluate_float64(candidate.starts[1])
    @test observation isa FixtureEvaluation
    @test observation.target isa Float64 # observed target, not an assessor target list
    @test length(observation.residual) == 4
    @test all(root -> all(Float64.(root) != candidate.starts[1]), record.assessor.isolated_roots)
end

@testset "rotated full-rank tiers and the 2^-160 Float64 barrier" begin
    for dimension in (2, 4, 8), condition in (10^4, 10^8, 10^12)
        record = make_linear_fixture(dimension, condition)
        model = record.private_model
        truth = assessor_truth(record)
        @test model.delta == BigInt(1) // (BigInt(1) << 160)
        @test model.singular_values[1] / model.singular_values[end] == condition
        @test all(>(0), model.singular_values)
        @test transpose(model.left_rotation) * model.left_rotation ==
              RescueFixtures._identity_exact(dimension)
        @test transpose(model.right_rotation) * model.right_rotation ==
              RescueFixtures._identity_exact(dimension)
        @test length(truth.isolated_roots) == length(truth.targets) == 1
        root = only(truth.isolated_roots)
        @test all(value -> -1 < value < 1, root)
        exact_observation = RescueFixtures._evaluate(model, root)
        @test all(iszero, exact_observation.residual)
        @test exact_observation.target == only(truth.targets)

        setprecision(BigFloat, 384) do
            observation = candidate_view(record).evaluate_arbitrary(exact_big(root))
            @test eltype(observation.residual) == BigFloat
            @test maximum(abs, observation.residual) < BigFloat(2)^-240
            @test abs(observation.target - exact_big(only(truth.targets))) < BigFloat(2)^-300
        end
        float_observation = candidate_view(record).evaluate_float64(Float64.(root))
        @test eltype(float_observation.residual) == Float64
        @test all(isfinite, float_observation.residual)
    end

    barrier = make_linear_fixture(2, 10^12)
    model = barrier.private_model
    root = only(barrier.assessor.isolated_roots)
    weak_delta = Vector{RescueFixtures.Exact}(model.right_rotation[:, end] .* model.delta)
    without_delta = root .- weak_delta
    @test root != without_delta
    @test Float64.(root) == Float64.(without_delta)
    @test candidate_view(barrier).evaluate_float64(Float64.(root)).residual ==
          candidate_view(barrier).evaluate_float64(Float64.(without_delta)).residual
    @test candidate_view(barrier).evaluate_float64(Float64.(root)).target ==
          candidate_view(barrier).evaluate_float64(Float64.(without_delta)).target

    setprecision(BigFloat, 384) do
        exact_root_observation = candidate_view(barrier).evaluate_arbitrary(exact_big(root))
        truncated_observation = candidate_view(barrier).evaluate_arbitrary(exact_big(without_delta))
        @test maximum(abs, exact_root_observation.residual) < BigFloat(2)^-240
        @test maximum(abs, truncated_observation.residual) > BigFloat(2)^-220
        @test abs(exact_root_observation.target - truncated_observation.target) >
              BigFloat(2)^-161
        @test precision(exact_root_observation.target) == 384
    end
    @test_throws ArgumentError candidate_view(barrier).evaluate_arbitrary(root)
end

@testset "clustered roots are exact, simple, separated, curved, and warped" begin
    for dimension in (2, 4, 8), root_count in (4, 8)
        record = make_clustered_fixture(dimension, root_count)
        model = record.private_model
        truth = assessor_truth(record)
        @test truth.classification == :clustered_simple_roots
        @test length(truth.isolated_roots) == length(truth.targets) == root_count
        @test model.separation == BigInt(1) // (BigInt(1) << 20)
        @test all(diff(model.weak_roots) .== model.separation)
        @test all(!iszero, model.quadratic_warp)
        @test all(!iszero, model.cubic_warp)
        @test length(unique(truth.targets)) == root_count

        for (root_index, root) in enumerate(truth.isolated_roots)
            @test all(value -> -1 < value < 1, root)
            exact_observation = RescueFixtures._evaluate(model, root)
            @test all(iszero, exact_observation.residual)
            @test exact_observation.target == truth.targets[root_index]
            parameter = model.weak_roots[root_index]
            derivative = prod(
                parameter - model.weak_roots[other] for other in eachindex(model.weak_roots)
                if other != root_index
            ) / model.separation^(root_count - 1)
            @test !iszero(derivative)
        end

        setprecision(BigFloat, 384) do
            separation = exact_big(model.separation)
            roots = [exact_big(root) for root in truth.isolated_roots]
            for index in 1:(length(roots) - 1)
                ratio = norm(roots[index + 1] - roots[index], 2) / separation
                @test BigFloat("0.999") < ratio < BigFloat("1.001")
            end
            for root in roots
                observation = candidate_view(record).evaluate_arbitrary(root)
                @test maximum(abs, observation.residual) < BigFloat(2)^-220
            end
        end
        center = candidate_view(record).evaluate_float64(zeros(dimension))
        @test all(isfinite, center.residual)
        @test center.valid
    end
end

@testset "safety controls carry typed assessor truth" begin
    records = Dict(
        record.assessor.classification => record for record in
        (make_safety_fixture(kind) for kind in (
            :stationary_nonroot,
            :even_multiple_root,
            :constant_manifold,
            :varying_manifold,
            :branch_crossing,
            :guard_crossing,
        ))
    )

    stationary = records[:stationary_nonroot]
    @test isempty(stationary.assessor.isolated_roots)
    @test isempty(stationary.assessor.targets)
    @test isempty(stationary.assessor.manifold_witnesses)
    @test norm(candidate_view(stationary).evaluate_float64(zeros(2)).residual, 2) > 0

    even = records[:even_multiple_root]
    @test length(even.assessor.isolated_roots) == 1
    @test exact_residual_is_zero(even, only(even.assessor.isolated_roots))

    constant = records[:constant_manifold]
    varying = records[:varying_manifold]
    @test isempty(constant.assessor.isolated_roots)
    @test isempty(varying.assessor.isolated_roots)
    @test length(constant.assessor.manifold_witnesses) == 3
    @test length(varying.assessor.manifold_witnesses) == 3
    @test all(witness -> exact_residual_is_zero(constant, witness),
              constant.assessor.manifold_witnesses)
    @test all(witness -> exact_residual_is_zero(varying, witness),
              varying.assessor.manifold_witnesses)
    @test length(unique(constant.assessor.witness_targets)) == 1
    @test length(unique(varying.assessor.witness_targets)) == 3

    branch = records[:branch_crossing]
    @test length(branch.assessor.isolated_roots) == 2
    branch_observations = [
        RescueFixtures._evaluate(branch.private_model, root) for
        root in branch.assessor.isolated_roots
    ]
    @test all(observation -> all(iszero, observation.residual), branch_observations)
    @test branch_observations[1].branch_identity != branch_observations[2].branch_identity
    @test all(observation -> observation.valid, branch_observations)

    guard = records[:guard_crossing]
    model = guard.private_model
    inner = zeros(RescueFixtures.Exact, 2)
    outer = zeros(RescueFixtures.Exact, 2)
    outer[end] = 2model.threshold
    inner_point = Vector{RescueFixtures.Exact}(model.right_rotation * inner)
    outer_point = Vector{RescueFixtures.Exact}(model.right_rotation * outer)
    inner_observation = RescueFixtures._evaluate(model, inner_point)
    outer_observation = RescueFixtures._evaluate(model, outer_point)
    @test inner_observation.guard_identity == :inner_guard
    @test outer_observation.guard_identity == :outer_guard
    @test inner_observation.valid && outer_observation.valid
end

@testset "signed-permutation and exact-orthogonal replicas replay covariantly" begin
    base = make_clustered_fixture(4, 4)
    signed = signed_permutation_replica(
        base;
        variable_shift=1,
        residual_shift=3,
        variable_phase=1,
        residual_phase=0,
    )
    signed_again = signed_permutation_replica(
        base;
        variable_shift=1,
        residual_shift=3,
        variable_phase=1,
        residual_phase=0,
    )
    orthogonal = orthogonal_replica(base; variable_tag=307, residual_tag=401)
    orthogonal_again = orthogonal_replica(base; variable_tag=307, residual_tag=401)

    @test replay_checksum(signed) == replay_checksum(signed_again)
    @test replay_checksum(orthogonal) == replay_checksum(orthogonal_again)
    @test replay_checksum(base) != replay_checksum(signed) != replay_checksum(orthogonal)
    @test signed.candidate.starts == signed_again.candidate.starts
    @test orthogonal.candidate.starts == orthogonal_again.candidate.starts
    @test all(start -> all(-1.0 .< start .< 1.0), signed.candidate.starts)
    @test all(start -> all(-1.0 .< start .< 1.0), orthogonal.candidate.starts)

    for replica in (signed, orthogonal)
        model = replica.private_model
        @test transpose(model.variable_rotation) * model.variable_rotation ==
              RescueFixtures._identity_exact(4)
        @test transpose(model.residual_rotation) * model.residual_rotation ==
              RescueFixtures._identity_exact(4)
        @test replica.assessor.targets == base.assessor.targets
        @test length(replica.assessor.isolated_roots) == 4
        @test all(root -> exact_residual_is_zero(replica, root),
                  replica.assessor.isolated_roots)

        point = RescueFixtures.Exact[
            BigInt(index) // BigInt(100 * 4) for index in 1:4
        ]
        base_point = Vector{RescueFixtures.Exact}(
            transpose(model.variable_rotation) * point,
        )
        base_observation = RescueFixtures._evaluate(base.private_model, base_point)
        replica_observation = RescueFixtures._evaluate(model, point)
        @test replica_observation.residual ==
              model.residual_rotation * base_observation.residual
        @test replica_observation.target == base_observation.target
        @test replica_observation.branch_identity == base_observation.branch_identity
        @test replica_observation.guard_identity == base_observation.guard_identity
    end

    first_base_root = first(base.assessor.isolated_roots)
    @test first(signed.assessor.isolated_roots) ==
          signed.private_model.variable_rotation * first_base_root
    @test first(orthogonal.assessor.isolated_roots) ==
          orthogonal.private_model.variable_rotation * first_base_root
end
