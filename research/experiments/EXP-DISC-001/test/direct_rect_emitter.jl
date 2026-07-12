using Test

include(joinpath(@__DIR__, "..", "src", "direct_rect_emitter.jl"))
using .StageNextDirectRectEmitter

valid(residual) = ScreeningObservation(residual)
invalid() = ScreeningObservation([0.0]; canonical_valid=false)

point_key(point) = Tuple(value == 0.0 ? 0.0 : value for value in point)
point_sequence(result) = point_key.([proposal.point for proposal in result.proposals])
point_multiset(points) = sort(point_key.(points))

@testset "bounded stable phi adapter" begin
    residual = [1.0e-200, -3.0, 4.0, 2.0e-100]
    permuted = residual[[3, 1, 4, 2]]
    @test phi_score(valid(residual)) == phi_score(valid(permuted))
    @test phi_score(valid([0.0])) == (0.0, true)
    @test phi_score(valid([1.0])) == (0.5, true)
    @test phi_score(valid([2.0])) == (1.0 - 1.0 / 3.0, true)
    huge, huge_valid = phi_score(valid([floatmax(Float64), floatmax(Float64)]))
    @test huge_valid
    @test 0.0 <= huge < 1.0
    @test huge == prevfloat(1.0)
    @test phi_score(invalid()) == (1.0, false)
    @test phi_score(valid([NaN])) == (1.0, false)
    @test phi_score(valid(Float64[])) == (1.0, false)
end

@testset "finite box, resolution, and initial-stencil applicability" begin
    calls = Ref(0)
    screen(point) = (calls[] += 1; valid([sum(abs2, point)]))
    applicable = emit_points(screen, fill(-1.0, 23), fill(1.0, 23))
    @test calls[] == SCREEN_CALLBACK_CAP
    @test length(applicable.proposals) == SCREEN_CALLBACK_CAP
    @test applicable.diagnostics.status == EMITTER_COMPLETE
    @test applicable.diagnostics.initial_stencil_size == 47
    @test applicable.diagnostics.all_requests_serviced

    calls[] = 0
    too_large = emit_points(screen, fill(-1.0, 24), fill(1.0, 24))
    @test calls[] == 0
    @test isempty(too_large.proposals)
    @test too_large.diagnostics.status == INAPPLICABLE_INITIAL_STENCIL

    calls[] = 0
    unresolved = emit_points(screen, [1.0e16], [1.0e16 + 2.0])
    @test calls[] == 0
    @test unresolved.diagnostics.status == INAPPLICABLE_RESOLUTION
    @test !unresolved.diagnostics.normalization_well_resolved

    calls[] = 0
    bad_box = emit_points(screen, [-Inf], [1.0])
    @test calls[] == 0
    @test bad_box.diagnostics.status == INAPPLICABLE_BOX
end

@testset "same ternary geometry and objective-blind orbit-breadth control" begin
    flat(point) = valid([3.0])
    shaped(point) = valid([point[1] - 7point[2], 0.1point[1]])
    flat_control = emit_points(flat, [-1.0, -1.0], [1.0, 1.0]; arm=RECT_ORBIT_BREADTH)
    shaped_control = emit_points(shaped, [-1.0, -1.0], [1.0, 1.0]; arm=RECT_ORBIT_BREADTH)
    guided = emit_points(flat, [-1.0, -1.0], [1.0, 1.0]; arm=DIRECT_RECT_EMIT)
    @test point_sequence(flat_control) == point_sequence(shaped_control)
    @test point_sequence(flat_control)[1:5] == point_sequence(guided)[1:5]
    @test [proposal.normalized_point for proposal in flat_control.proposals[1:5]] == [
        [0.0, 0.0],
        [-2 / 3, 0.0],
        [2 / 3, 0.0],
        [0.0, -2 / 3],
        [0.0, 2 / 3],
    ]
    @test all(proposal -> all(value -> -1.0 <= value <= 1.0, proposal.normalized_point), flat_control.proposals)
    @test flat_control.diagnostics.screening_callbacks == SCREEN_CALLBACK_CAP
    @test flat_control.diagnostics.hard_discard_count == 0
    @test !flat_control.diagnostics.external_result_used
end

@testset "flat plateau ties are deterministic and fully serviced" begin
    requested = Vector{Vector{Float64}}()
    function plateau(point)
        push!(requested, copy(point))
        return valid([1.0, -1.0])
    end
    first_run = emit_points(plateau, [-1.0, -1.0], [1.0, 1.0])
    empty!(requested)
    second_run = emit_points(plateau, [-1.0, -1.0], [1.0, 1.0])
    @test point_sequence(first_run) == point_sequence(second_run)
    @test length(requested) == SCREEN_CALLBACK_CAP
    @test point_sequence(second_run) == point_key.(requested)
    @test [proposal.evaluation_ordinal for proposal in second_run.proposals] == collect(1:48)
    @test second_run.diagnostics.all_requests_serviced
    @test second_run.diagnostics.symmetry_tie_fallback
    @test second_run.diagnostics.duplicate_count == second_run.diagnostics.center_fill_count == 3
    @test second_run.proposals[6].normalized_point == [-2 / 3, -2 / 3]
    @test second_run.proposals[end].duplicate_of == 1
    @test point_key(second_run.proposals[end].point) == point_key(second_run.proposals[1].point)
end

@testset "signed-permutation replica and score ties" begin
    base_screen(point) = valid([point[1] + 2point[2], point[1] - point[2]])
    base = emit_points(base_screen, [-1.0, -1.0], [1.0, 1.0])
    # y = (-x2, x1); the callback applies the exact inverse signed permutation.
    replica_screen(point) = base_screen([point[2], -point[1]])
    replica = emit_points(replica_screen, [-1.0, -1.0], [1.0, 1.0])
    mapped_back = [[proposal.point[2], -proposal.point[1]] for proposal in replica.proposals]
    @test point_multiset([proposal.point for proposal in base.proposals]) == point_multiset(mapped_back)
    @test sort([proposal.phi for proposal in base.proposals]) ==
        sort([proposal.phi for proposal in replica.proposals])

    tied(point) = valid([abs(point[1]), abs(point[2])])
    tie_one = emit_points(tied, [-1.0, -1.0], [1.0, 1.0])
    tie_two = emit_points(tied, [-1.0, -1.0], [1.0, 1.0])
    @test point_sequence(tie_one) == point_sequence(tie_two)
end

@testset "flat signed-permutation tie fallback services complete orbits" begin
    for arm in (DIRECT_RECT_EMIT, RECT_ORBIT_BREADTH), dimension in 2:12,
        screen in (_ -> valid([1.0]), _ -> invalid())
        lower, upper = fill(-1.0, dimension), fill(1.0, dimension)
        base = emit_points(screen, lower, upper; arm)
        permutation = reverse(1:dimension)
        signs = [isodd(index) ? -1.0 : 1.0 for index in 1:dimension]
        replica = emit_points(screen, lower, upper; arm)
        mapped_back = Vector{Vector{Float64}}()
        for proposal in replica.proposals
            point = zeros(Float64, dimension)
            for index in 1:dimension
                point[permutation[index]] = signs[index] * proposal.point[index]
            end
            push!(mapped_back, point)
        end
        @test point_multiset([proposal.point for proposal in base.proposals]) ==
            point_multiset(mapped_back)
        @test base.diagnostics.symmetry_tie_fallback == (arm == DIRECT_RECT_EMIT)
        @test base.diagnostics.screening_callbacks == length(base.proposals) == 48
        @test base.diagnostics.center_fill_count > 0
        @test base.diagnostics.hard_discard_count == 0
    end
end

@testset "orbit breadth has score-blind unique ternary coverage" begin
    flat(_point) = valid([1.0])
    for dimension in (2, 4, 8)
        result = emit_points(
            flat, fill(-1.0, dimension), fill(1.0, dimension);
            arm=RECT_ORBIT_BREADTH,
        )
        unique_points = Set(point_key(proposal.normalized_point) for proposal in result.proposals)
        @test length(result.proposals) == 48
        @test length(unique_points) == 48 - result.diagnostics.center_fill_count
        @test result.diagnostics.duplicate_count == result.diagnostics.center_fill_count
        @test result.diagnostics.symmetry_orbits_serviced >= 2
        @test !result.diagnostics.symmetry_tie_fallback
        if dimension <= 4
            expected = vcat(fill(-2 / 3, 2), zeros(dimension - 2))
            @test point_key(expected) in unique_points
        else
            expected = vcat([-2 / 9], zeros(dimension - 1))
            @test point_key(expected) in unique_points
        end
    end
end

@testset "late exact tie changes no state by coordinate FIFO" begin
    late_tie(point) = valid([abs(point[1]) + 2abs(point[2])])
    base = emit_points(late_tie, [-1.0, -1.0], [1.0, 1.0])
    replica_screen(point) = late_tie([point[2], -point[1]])
    replica = emit_points(replica_screen, [-1.0, -1.0], [1.0, 1.0])
    mapped_back = [[proposal.point[2], -proposal.point[1]] for proposal in replica.proposals]
    @test base.diagnostics.completed_splits == 1
    @test base.diagnostics.symmetry_tie_fallback
    @test base.diagnostics.screening_callbacks == length(base.proposals) == 48
    @test point_multiset([proposal.point for proposal in base.proposals]) ==
        point_multiset(mapped_back)
end

@testset "invalid moat remains proposal evidence" begin
    function invalid_moat(point)
        sum(abs2, point) <= 0.06^2 || return invalid()
        return valid(point)
    end
    result = emit_points(invalid_moat, [-1.0, -1.0], [1.0, 1.0])
    invalid_proposals = filter(proposal -> !proposal.canonical_valid, result.proposals)
    @test length(result.proposals) == SCREEN_CALLBACK_CAP
    @test length(invalid_proposals) == result.diagnostics.invalid_count
    @test 0 < result.diagnostics.invalid_count < SCREEN_CALLBACK_CAP
    @test all(proposal.phi == 1.0 for proposal in invalid_proposals)
    @test result.diagnostics.hard_discard_count == 0
    @test result.diagnostics.all_requests_serviced

    thrown = emit_points(_ -> error("guard failure"), [-1.0], [1.0]; arm=RECT_ORBIT_BREADTH)
    @test length(thrown.proposals) == SCREEN_CALLBACK_CAP
    @test thrown.diagnostics.callback_failure_count == SCREEN_CALLBACK_CAP
    @test thrown.diagnostics.invalid_count == SCREEN_CALLBACK_CAP
end

@testset "thin rotated basin distinguishes guidance from geometry" begin
    function thin_rotated(point)
        perpendicular = (point[2] - 0.37point[1] - 0.11) / 0.012
        longitudinal = 0.08(point[1] - 0.25)
        return valid([perpendicular, longitudinal])
    end
    guided = emit_points(thin_rotated, [-1.0, -1.0], [1.0, 1.0]; arm=DIRECT_RECT_EMIT)
    breadth = emit_points(thin_rotated, [-1.0, -1.0], [1.0, 1.0]; arm=RECT_ORBIT_BREADTH)
    @test length(guided.proposals) == length(breadth.proposals) == SCREEN_CALLBACK_CAP
    @test minimum(proposal.phi for proposal in guided.proposals) <
        minimum(proposal.phi for proposal in breadth.proposals)
    @test point_sequence(guided) != point_sequence(breadth)
    @test guided.diagnostics.hard_discard_count == breadth.diagnostics.hard_discard_count == 0
    replica = emit_points(
        point -> thin_rotated([point[2], -point[1]]),
        [-1.0, -1.0], [1.0, 1.0]; arm=DIRECT_RECT_EMIT,
    )
    mapped_back = [[proposal.point[2], -proposal.point[1]] for proposal in replica.proposals]
    @test !guided.diagnostics.symmetry_tie_fallback && !replica.diagnostics.symmetry_tie_fallback
    @test point_multiset([proposal.point for proposal in guided.proposals]) ==
        point_multiset(mapped_back)
end
