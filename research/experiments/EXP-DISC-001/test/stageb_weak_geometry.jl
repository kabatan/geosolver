using LinearAlgebra
using Test

include(joinpath(@__DIR__, "..", "src", "weak_geometry.jl"))
using .StageBWeakGeometry

struct ExplosiveIdentity end
Base.isequal(::ExplosiveIdentity, ::ExplosiveIdentity) = error("identity comparison failed")

function linear_observer(matrix, box; semantic_rule=unit -> (
    branch_identity=:branch,
    guard_identity=:guard,
    domain_identity=:domain,
    branch_margin=1.0,
    guard_margin=1.0,
    domain_margin=1.0,
    valid=true,
))
    coefficients = Matrix{Float64}(matrix)
    return point -> begin
        unit = to_normalized(box, point)
        semantics = semantic_rule(unit)
        WeakPointEvaluation(
            coefficients * unit;
            semantics...,
        )
    end
end

function run_linear(matrix; lower=fill(-1.0, size(matrix, 2)),
    upper=fill(1.0, size(matrix, 2)), endpoint=nothing, seed=0x1234,
    semantic_rule=unit -> (
        branch_identity=:branch,
        guard_identity=:guard,
        domain_identity=:domain,
        branch_margin=1.0,
        guard_margin=1.0,
        domain_margin=1.0,
        valid=true,
    ))
    box = box_normalization(lower, upper)
    point = endpoint === nothing ? copy(box.midpoint) : Float64[endpoint...]
    observer = linear_observer(matrix, box; semantic_rule)
    return weak_geometry_plan(observer, point, lower, upper; seed)
end

@testset "frozen weak-geometry constants and finite-box normalization" begin
    @test reinterpret(UInt64, WEAK_FD_STEP) == 0x3ed965fea53d6e3d
    @test WEAK_RADII == (0x1.0p-20, 0x1.0p-14, 0x1.0p-8, 0x1.0p-2)
    @test WEAK_MAX_LAUNCH_SLOTS == 64
    @test WEAK_MAX_GEOMETRY_SLOTS == 48
    @test WEAK_MAX_COMPARISONS == 24

    box = box_normalization([-10.0, 100.0], [30.0, 108.0])
    unit = [-0.75, 0.25]
    @test to_normalized(box, to_physical(box, unit)) ≈ unit atol=2eps(Float64)
    @test_throws ArgumentError box_normalization([-Inf, 0.0], [1.0, 1.0])
    @test_throws ArgumentError box_normalization([0.0, 0.0], [0.0, 1.0])
end

@testset "stable line and physical-scale covariance" begin
    matrix = [2.0 0.0; 0.0 0.01]
    base = run_linear(matrix)
    scaled = run_linear(
        matrix;
        lower=[-20.0, -0.003],
        upper=[20.0, 0.003],
    )
    @test base.status == :applicable
    @test base.reason == :stable_weak_geometry
    @test base.evidence.gap.weak_dimension == 1
    @test base.evidence.gap.weak_strong_ratio <= 0.1
    @test base.evidence.gap.raw_cross_gap > 4base.evidence.eta
    @test base.evidence.gap.smallest_strong > 0
    @test base.evidence.rounding_envelope > 0
    @test base.evidence.eta ≈
          base.evidence.jacobian_disagreement + base.evidence.rounding_envelope
    gamma = 8eps(Float64) / (1 - 8eps(Float64))
    @test base.evidence.rounding_envelope ≈
          gamma * sqrt(2.0) * norm(matrix) rtol=2e-10
    @test base.evidence.projector_distance <= 0.1
    @test base.evidence.average_projector ≈ [0.0 0.0; 0.0 1.0] atol=1e-12
    @test scaled.evidence.average_projector ≈ base.evidence.average_projector atol=1e-10
    @test length(base.quartets) == length(WEAK_RADII)
    @test [quartet.radius for quartet in base.quartets] == collect(WEAK_RADII)
    @test base.callback_count == 1 + 4 * 2 + 4 * length(WEAK_RADII)
    @test length(base.launch_slots) == 64
    @test count(slot -> slot.lane == :iid, base.launch_slots) == 16
    @test count(slot -> slot.lane == :geometry, base.launch_slots) == 8
    @test count(slot -> slot.lane == :continuation, base.launch_slots) == 40
    @test all(slot.sign in (-1, 1) for slot in base.launch_slots if slot.lane == :geometry)
    @test all(slot.point_ordinal in (1, 2) for slot in base.launch_slots if slot.lane == :geometry)
end

@testset "signed, row, and orthogonal replica covariance" begin
    matrix = [3.0 0.0; 0.0 0.02]
    reference = run_linear(matrix)
    projector = reference.evidence.average_projector

    signed_permutation = [0.0 -1.0; 1.0 0.0]
    signed = run_linear(matrix * transpose(signed_permutation))
    @test signed.status == reference.status
    @test signed.evidence.average_projector ≈
          signed_permutation * projector * transpose(signed_permutation) atol=1e-11

    row_permutation = [0.0 1.0; 1.0 0.0]
    rows = run_linear(row_permutation * matrix)
    @test rows.status == reference.status
    @test rows.evidence.average_projector ≈ projector atol=1e-11

    row_angle = -0.61
    row_orthogonal = [cos(row_angle) -sin(row_angle); sin(row_angle) cos(row_angle)]
    rotated_rows = run_linear(row_orthogonal * matrix)
    @test rotated_rows.status == reference.status
    @test rotated_rows.evidence.average_projector ≈ projector atol=2e-10
    @test rotated_rows.evidence.rounding_envelope ≈
          reference.evidence.rounding_envelope rtol=2e-10

    angle = 0.37
    orthogonal = [cos(angle) -sin(angle); sin(angle) cos(angle)]
    rotated = run_linear(matrix * transpose(orthogonal))
    @test rotated.status == reference.status
    @test rotated.evidence.average_projector ≈
          orthogonal * projector * transpose(orthogonal) atol=2e-10

    z = counter_gaussian(0x77, 3, 2)
    paired = paired_probe_directions(projector, z)
    transported = paired_probe_directions(
        orthogonal * projector * transpose(orthogonal),
        orthogonal * z,
    )
    @test transported.weak ≈ orthogonal * paired.weak atol=2e-14
    @test transported.isotropic ≈ orthogonal * paired.isotropic atol=2e-14
    @test counter_gaussian(0x77, 3, 2) == z
    @test counter_gaussian(0x77, 4, 2) != z

    offset = [0.8e-12, 0.4e-12]
    box = box_normalization([-1.0, -1.0], [1.0, 1.0])
    affine = point -> WeakPointEvaluation(matrix * to_normalized(box, point) + offset)
    rotated_affine = point -> WeakPointEvaluation(
        row_orthogonal * (matrix * to_normalized(box, point) + offset),
    )
    affine_result = weak_geometry_plan(affine, zeros(2), fill(-1.0, 2), fill(1.0, 2); seed=1)
    rotated_affine_result = weak_geometry_plan(
        rotated_affine, zeros(2), fill(-1.0, 2), fill(1.0, 2); seed=1,
    )
    @test affine_result.status == rotated_affine_result.status == :applicable
    @test affine_result.evidence.average_projector ≈
          rotated_affine_result.evidence.average_projector atol=2e-10
end

@testset "branch, guard, and domain changes reject without leakage" begin
    matrix = [2.0 0.0; 0.0 0.01]
    branch_switch = run_linear(matrix; semantic_rule=unit -> (
        branch_identity=unit[1] > 0 ? :other_branch : :branch,
        guard_identity=:guard,
        domain_identity=:domain,
        branch_margin=1.0,
        guard_margin=1.0,
        domain_margin=1.0,
        valid=true,
    ))
    @test branch_switch.status == :inapplicable
    @test branch_switch.reason == :finite_difference_semantics_changed
    @test isempty(branch_switch.quartets)

    guard_calls = Ref(0)
    guard_box = box_normalization([-1.0, -1.0], [1.0, 1.0])
    guarded = linear_observer(matrix, guard_box; semantic_rule=unit -> begin
        off_axis = abs(unit[1]) > 0 && abs(unit[2]) > 0
        (
            branch_identity=:branch,
            guard_identity=:guard,
            domain_identity=:domain,
            branch_margin=1.0,
            guard_margin=off_axis ? -1.0 : 1.0,
            domain_margin=1.0,
            valid=true,
        )
    end)
    guard_switch = weak_geometry_plan(
        point -> begin
            guard_calls[] += 1
            guarded(point)
        end,
        [0.0, 0.0],
        [-1.0, -1.0],
        [1.0, 1.0];
        seed=0x1234,
    )
    @test guard_switch.status == :inapplicable
    @test guard_switch.reason == :no_jointly_valid_probe_quartet
    @test guard_switch.attempted_comparisons == 4
    @test guard_switch.rejected_comparisons == 4
    @test isempty(guard_switch.quartets)
    @test guard_switch.callback_count == guard_calls[] == 25

    throwing_calls = Ref(0)
    throwing = weak_geometry_plan(
        point -> begin
            throwing_calls[] += 1
            unit = to_normalized(guard_box, point)
            abs(unit[1]) > 0 && abs(unit[2]) > 0 && error("opaque domain failure")
            WeakPointEvaluation(matrix * unit)
        end,
        [0.0, 0.0],
        [-1.0, -1.0],
        [1.0, 1.0];
        seed=0x1234,
    )
    @test throwing.status == :inapplicable
    @test throwing.reason == :no_jointly_valid_probe_quartet
    @test throwing.callback_count == throwing_calls[] == 25

    vector_only_calls = Ref(0)
    vector_only(point::Vector{Float64}) = begin
        vector_only_calls[] += 1
        WeakPointEvaluation(matrix * point)
    end
    vector_only_result = weak_geometry_plan(
        vector_only,
        [0.0, 0.0],
        [-1.0, -1.0],
        [1.0, 1.0];
        seed=0x1234,
    )
    @test vector_only_result.status == :applicable
    @test vector_only_result.callback_count == vector_only_calls[]

    explosive = weak_geometry_plan(
        point -> WeakPointEvaluation(
            matrix * point;
            branch_identity=ExplosiveIdentity(),
        ),
        [0.0, 0.0],
        [-1.0, -1.0],
        [1.0, 1.0];
        seed=0x1234,
    )
    @test explosive.status == :inapplicable
    @test explosive.reason == :finite_difference_semantics_changed

    domain_switch = run_linear(matrix; semantic_rule=unit -> begin
        off_axis = abs(unit[1]) > 0 && abs(unit[2]) > 0
        (
            branch_identity=:branch,
            guard_identity=:guard,
            domain_identity=off_axis ? :other_chart : :domain,
            branch_margin=1.0,
            guard_margin=1.0,
            domain_margin=1.0,
            valid=true,
        )
    end)
    @test domain_switch.status == :inapplicable
    @test domain_switch.reason == :no_jointly_valid_probe_quartet
    @test isempty(domain_switch.launch_slots)

    outside_calls = Ref(0)
    anchor = WeakPointEvaluation([0.0, 0.0])
    outside, callbacks = StageBWeakGeometry._joint_quartet(
        point -> begin
            outside_calls[] += 1
            WeakPointEvaluation([0.0, 0.0])
        end,
        guard_box,
        anchor,
        2,
        [0.9, 0.0],
        [1.0, 0.0],
        [0.0, 1.0],
        0.25,
        1,
        1,
    )
    @test outside === nothing
    @test callbacks == outside_calls[] == 0
end

@testset "typed inapplicability and singular-gap conditions" begin
    no_gap = run_linear(Matrix{Float64}(I, 2, 2))
    @test no_gap.status == :inapplicable
    @test no_gap.reason == :no_stable_singular_gap
    @test no_gap.callback_count == 1 + 4 * 2

    underdetermined = run_linear(reshape([1.0, 0.0], 1, 2))
    @test underdetermined.status == :inapplicable
    @test underdetermined.reason == :underdetermined

    overdetermined = run_linear([2.0 0.0; 0.0 0.01; 0.0 0.0])
    @test overdetermined.status == :applicable

    nonroot = run_linear([2.0 0.0; 0.0 0.01]; endpoint=[1.0e-6, 0.0])
    @test nonroot.status == :inapplicable
    @test nonroot.reason == :endpoint_residual_too_large

    one_dimensional = weak_geometry_plan(
        point -> WeakPointEvaluation([point[1]]),
        [0.0],
        [-1.0],
        [1.0];
        seed=1,
    )
    @test one_dimensional.reason == :dimension_below_two
    @test one_dimensional.callback_count == 0

    invalid_seed = weak_geometry_plan(
        point -> WeakPointEvaluation([point[1], point[2]]),
        [0.0, 0.0],
        [-1.0, -1.0],
        [1.0, 1.0];
        seed=-1,
    )
    @test invalid_seed.reason == :invalid_seed
    @test invalid_seed.callback_count == 0

    failed_endpoint = weak_geometry_plan(
        point -> error("opaque endpoint failure"),
        [0.0, 0.0],
        [-1.0, -1.0],
        [1.0, 1.0];
        seed=1,
    )
    @test failed_endpoint.reason == :endpoint_evaluation_failed
    @test failed_endpoint.callback_count == 1
end

@testset "manifold work is bounded and probe endpoints cannot recurse" begin
    manifold = run_linear([1.0 0.0; 0.0 0.0])
    @test manifold.status == :applicable
    @test manifold.evidence.gap.weak_dimension == 1
    @test length(manifold.quartets) == 4
    @test manifold.attempted_comparisons == 4
    @test manifold.callback_count == 25

    calls = Ref(0)
    recursive = weak_geometry_plan(
        point -> begin
            calls[] += 1
            WeakPointEvaluation([point[1], 0.0])
        end,
        [0.0, 0.0],
        [-1.0, -1.0],
        [1.0, 1.0];
        seed=1,
        derived_from_probe=true,
    )
    @test recursive.status == :inapplicable
    @test recursive.reason == :probe_derived_endpoint
    @test recursive.callback_count == 0
    @test calls[] == 0

    flat = run_linear(zeros(2, 2))
    @test flat.reason == :no_stable_singular_gap
    @test isempty(flat.quartets)
end

@testset "multi-dimensional weak subspace has paired bounded work" begin
    matrix = Diagonal([2.0, 1.0, 0.01, 0.001])
    result = run_linear(Matrix(matrix); seed=0x5eed)
    @test result.status == :applicable
    @test result.evidence.gap.weak_dimension == 2
    @test result.attempted_comparisons == 24
    @test result.rejected_comparisons == 0
    @test length(result.quartets) == 24
    @test 2length(result.quartets) == WEAK_MAX_GEOMETRY_SLOTS
    first_z = counter_gaussian(0x5eed, 1, 4)
    first_pair = paired_probe_directions(result.evidence.average_projector, first_z)
    @test result.quartets[1].weak_direction ≈ first_pair.weak atol=2e-14
    @test result.quartets[1].isotropic_direction ≈ first_pair.isotropic atol=2e-14
    @test all(size(quartet.normalized_points, 2) == 4 for quartet in result.quartets)
    @test all(
        quartet.normalized_points[:, 1] + quartet.normalized_points[:, 2] ≈
            2 .* zeros(4) for quartet in result.quartets
    )
    @test all(
        quartet.normalized_points[:, 3] + quartet.normalized_points[:, 4] ≈
            2 .* zeros(4) for quartet in result.quartets
    )
    @test length(result.launch_slots) == 64
    @test count(slot -> slot.lane == :geometry, result.launch_slots) == 48
    @test count(slot -> slot.lane == :iid, result.launch_slots) == 16
    @test count(slot -> slot.lane == :continuation, result.launch_slots) == 0
    @test all(
        slot.lane == :iid for slot in result.launch_slots if mod(slot.slot - 1, 4) == 0
    )
    @test all(
        slot.lane == :geometry for slot in result.launch_slots if mod(slot.slot - 1, 4) != 0
    )
    @test all(
        slot.point_ordinal == (slot.sign == 1 ? 1 : 2) for
        slot in result.launch_slots if slot.lane == :geometry
    )
    @test all(begin
        quartet = result.quartets[slot.comparison_index]
        weak_point = quartet.normalized_points[:, slot.point_ordinal]
        isotropic_point = quartet.normalized_points[:, slot.point_ordinal + 2]
        dot(weak_point, quartet.weak_direction) * slot.sign > 0 &&
            dot(isotropic_point, quartet.isotropic_direction) * slot.sign > 0
    end for slot in result.launch_slots if slot.lane == :geometry)
    @test result.callback_count == 1 + 4 * 4 + 4 * 24

    limited = weak_geometry_plan(
        linear_observer(Matrix(matrix), box_normalization(fill(-1.0, 4), fill(1.0, 4))),
        zeros(4),
        fill(-1.0, 4),
        fill(1.0, 4);
        seed=0x5eed,
        maximum_comparisons=4,
    )
    @test limited.status == :applicable
    @test limited.attempted_comparisons == length(limited.quartets) == 4
    @test count(slot -> slot.lane == :geometry, limited.launch_slots) == 8
    @test count(slot -> slot.lane == :continuation, limited.launch_slots) == 40
    @test limited.callback_count == 1 + 4 * 4 + 4 * 4

    empty_budget = weak_geometry_plan(
        point -> WeakPointEvaluation(zeros(4)),
        zeros(4),
        fill(-1.0, 4),
        fill(1.0, 4);
        seed=1,
        maximum_comparisons=0,
    )
    @test empty_budget.reason == :comparison_budget_empty
    @test empty_budget.callback_count == 0
end

@testset "joint split minimizes padded ratio with weak-dimension tie break" begin
    jacobian = Matrix(Diagonal([1.0, 0.05, 0.0025]))
    gap = StageBWeakGeometry._joint_gap_evidence(jacobian, jacobian, 0.0)
    @test gap !== nothing
    @test gap.weak_strong_ratio ≈ 0.05
    @test gap.weak_dimension == 1
    @test gap.strong_dimension == 2

    coarse = Matrix(Diagonal([1.0, 0.09, 0.001]))
    fine = Matrix(Diagonal([1.0, 0.11, 0.001]))
    joint = StageBWeakGeometry._joint_gap_evidence(coarse, fine, 0.0)
    @test joint !== nothing
    @test joint.weak_dimension == 1
    @test joint.strong_dimension == 2
end

@testset "runtime source contains no identity-based routing seam" begin
    source = lowercase(read(joinpath(@__DIR__, "..", "src", "weak_geometry.jl"), String))
    @test !occursin("family_id", source)
    @test !occursin("case_id", source)
    @test !occursin("gold_", source)
    @test !occursin("file_name", source)
end
