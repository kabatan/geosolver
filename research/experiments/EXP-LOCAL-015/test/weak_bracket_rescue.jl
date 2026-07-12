using LinearAlgebra
using Test

include(joinpath(@__DIR__, "..", "src", "WeakBracketRescue.jl"))
using .WeakBracketRescue

const TOTAL_CALLBACKS = 4 * 2 + 2length(BRACKET_RADII)

function clustered_evaluator(; root=1.0e-3, semantic_rule=point -> (
    branch_identity=:branch,
    guard_identity=:guard,
    domain_identity=:domain,
    branch_margin=1.0,
    guard_margin=1.0,
    domain_margin=1.0,
    valid=true,
))
    return point -> begin
        semantics = semantic_rule(point)
        RescueEvaluation(
            [point[1], point[2]^2 - root^2];
            semantics...,
        )
    end
end

function run_clustered(; lane=:weak, isotropic_direction=nothing, root=1.0e-3,
    evaluate=clustered_evaluator(; root), endpoint=zeros(2), remaining=TOTAL_CALLBACKS)
    anchor = clustered_evaluator(; root)(endpoint)
    calls = Ref(0)
    result = weak_bracket_rescue(
        evaluate,
        NormalizedBox(2),
        endpoint,
        anchor;
        remaining_callbacks=remaining,
        lane,
        isotropic_direction,
        charge_callback=() -> (calls[] += 1),
    )
    return result, calls[]
end

@testset "frozen constants and dimension-aware 4n reservation" begin
    @test reinterpret(UInt64, CPQR_FD_STEP) == 0x3ed965fea53d6e3d
    @test BRACKET_RADII == (0x1.0p-20, 0x1.0p-14, 0x1.0p-8, 0x1.0p-2)

    exact = reserve_cpqr_diagnostic(3, 12)
    @test exact.status == :reserved
    @test exact.required_callbacks == exact.reserved_callbacks == 12
    @test exact.reason == :complete_h_h2_stencil

    short = reserve_cpqr_diagnostic(3, 11)
    @test short.status == :unknown
    @test short.reason == :insufficient_cpqr_reserve
    @test short.required_callbacks == 12
    @test short.reserved_callbacks == 0
    @test reserve_cpqr_diagnostic(1, 100).reason == :dimension_below_two
    @test reserve_cpqr_diagnostic(2, -1).reason == :invalid_callback_budget
    @test_throws ArgumentError NormalizedBox(0)
    @test_throws ArgumentError NormalizedBox([-1.0, 0.0], [1.0, 0.0])
end

@testset "minimum-success fixture finds both clustered simple roots" begin
    root = 1.0e-3
    recorded = Vector{Vector{Float64}}()
    base = clustered_evaluator(; root)
    evaluate = point -> begin
        push!(recorded, copy(point))
        base(point)
    end
    result, charged = run_clustered(; root, evaluate)

    @test result.status == :seeded
    @test result.reason == :strict_projected_sign_bracket
    @test result.callback_count == charged == TOTAL_CALLBACKS == 16
    @test result.required_callbacks == TOTAL_CALLBACKS
    @test result.diagnostic.status == :applicable
    @test result.diagnostic.callback_count == 8
    @test result.diagnostic.reservation.required_callbacks == 8
    @test result.diagnostic.reservation.reserved_callbacks == 8
    @test result.diagnostic.evidence.weak_dimension == 1
    @test result.diagnostic.evidence.coarse_rank == 1
    @test result.diagnostic.evidence.fine_rank == 1
    @test result.diagnostic.evidence.right_projector_distance <= 0.1
    @test result.diagnostic.evidence.left_projector_distance <= 0.1
    @test result.probe.callback_count == 8
    @test result.probe.detected_bracket_count == 2
    @test length(result.seeds) == 2
    @test all(
        seed.lower_projected_residual * seed.upper_projected_residual < 0
        for seed in result.seeds
    )
    @test any(seed -> seed.lower_parameter < -root < seed.upper_parameter, result.seeds)
    @test any(seed -> seed.lower_parameter < root < seed.upper_parameter, result.seeds)
    @test all(seed -> seed.lane == :weak, result.seeds)

    # Four complete CPQR column pairs followed by four complete radius pairs.
    @test length(recorded) == TOTAL_CALLBACKS
    for pair_start in 1:2:8
        @test recorded[pair_start] + recorded[pair_start + 1] == zeros(2)
    end
    for (radius_index, radius) in enumerate(BRACKET_RADII)
        plus = recorded[8 + 2radius_index - 1]
        minus = recorded[8 + 2radius_index]
        @test plus + minus == zeros(2)
        @test norm(plus - minus, 2) ≈ 2radius
    end
end

@testset "equal-work isotropic and no-bracket controls" begin
    candidate, candidate_calls = run_clustered()
    isotropic, isotropic_calls = run_clustered(
        lane=:isotropic,
        isotropic_direction=[1.0, 0.0],
    )
    suppressed, suppressed_calls = run_clustered(lane=:no_bracket)

    @test candidate.status == :seeded
    @test isotropic.status == :unknown
    @test isotropic.reason == :no_sign_bracket
    @test isempty(isotropic.seeds)
    @test suppressed.status == :control
    @test suppressed.reason == :no_bracket_emission_control
    @test isempty(suppressed.seeds)
    @test suppressed.probe.detected_bracket_count == 2
    @test candidate_calls == isotropic_calls == suppressed_calls == TOTAL_CALLBACKS
    @test candidate.probe.parameters == isotropic.probe.parameters ==
          suppressed.probe.parameters

    anchor = clustered_evaluator()(zeros(2))
    diagnostic = acquire_cpqr_rank_evidence(
        clustered_evaluator(),
        NormalizedBox(2),
        zeros(2),
        anchor;
        remaining_callbacks=8,
    )
    invalid = weak_bracket_rescue(
        clustered_evaluator(),
        NormalizedBox(2),
        zeros(2),
        anchor;
        remaining_callbacks=TOTAL_CALLBACKS,
        lane=:isotropic,
    )
    @test invalid.status == :unknown
    @test invalid.reason == :missing_isotropic_control_direction
    @test invalid.callback_count == 8

    external = symmetric_bracket_probe(
        clustered_evaluator(),
        NormalizedBox(2),
        zeros(2),
        anchor,
        diagnostic;
        remaining_callbacks=8,
    )
    @test external.status == :unknown
    @test external.reason == :external_cpqr_diagnostic_non_authoritative
    @test external.callback_count == 0

    # A naked record is never authoritative, even when it came from a valid
    # diagnostic. Routing requires the complete callback-bound diagnostic.
    standalone = symmetric_bracket_probe(
        clustered_evaluator(),
        NormalizedBox(2),
        zeros(2),
        anchor,
        diagnostic.evidence;
        remaining_callbacks=8,
    )
    @test standalone.status == :unknown
    @test standalone.reason == :standalone_rank_evidence_non_authoritative
    @test standalone.callback_count == 0

    # Forged singular values remain internally sorted, but the public seam
    # rejects the entire caller-supplied diagnostic before any probe callback.
    diagnostic.evidence.coarse_singular_values[end] = 1.0e-12
    forged = symmetric_bracket_probe(
        clustered_evaluator(),
        NormalizedBox(2),
        zeros(2),
        anchor,
        diagnostic;
        remaining_callbacks=8,
    )
    @test forged.status == :unknown
    @test forged.reason == :external_cpqr_diagnostic_non_authoritative
    @test forged.callback_count == 0
end


@testset "stale same-anchor diagnostic cannot cross the opaque operation" begin
    old = point -> RescueEvaluation([point[1], point[2]^2 - 1.0e-6])
    current = point -> RescueEvaluation([point[1], point[2] - 1.0e-6])
    endpoint = zeros(2)
    # Both callbacks deliberately have exactly the same endpoint observation.
    @test old(endpoint).residual == current(endpoint).residual
    old_diagnostic = acquire_cpqr_rank_evidence(
        old,
        NormalizedBox(2),
        endpoint,
        old(endpoint);
        remaining_callbacks=8,
    )
    @test old_diagnostic.status == :applicable

    stale_calls = Ref(0)
    stale = symmetric_bracket_probe(
        current,
        NormalizedBox(2),
        endpoint,
        current(endpoint),
        old_diagnostic;
        remaining_callbacks=8,
        charge_callback=() -> (stale_calls[] += 1),
    )
    @test stale.status == :unknown
    @test stale.reason == :external_cpqr_diagnostic_non_authoritative
    @test stale.callback_count == stale_calls[] == 0
    @test isempty(stale.seeds)

    proper_calls = Ref(0)
    proper = weak_bracket_rescue(
        current,
        NormalizedBox(2),
        endpoint,
        current(endpoint);
        remaining_callbacks=TOTAL_CALLBACKS,
        charge_callback=() -> (proper_calls[] += 1),
    )
    @test proper.status == :unknown
    @test proper.reason == :no_stable_one_dimensional_invariant_rank
    @test proper.callback_count == proper_calls[] == 8
    @test isempty(proper.seeds)
end

@testset "SVD applicability survives the exact CPQR rotation counterexample" begin
    weak_linear = 1.53e-14
    base = point -> RescueEvaluation([
        point[1],
        point[2]^2 + weak_linear * point[2] - 1.0e-6,
    ])
    inverse_sqrt_two = inv(sqrt(2.0))
    variable_rotation = [
        inverse_sqrt_two -inverse_sqrt_two
        inverse_sqrt_two inverse_sqrt_two
    ]
    rotated = point -> RescueEvaluation(
        base(transpose(variable_rotation) * point).residual,
    )

    base_result = weak_bracket_rescue(
        base,
        NormalizedBox(2),
        zeros(2),
        base(zeros(2));
        remaining_callbacks=TOTAL_CALLBACKS,
    )
    rotated_result = weak_bracket_rescue(
        rotated,
        NormalizedBox(2),
        zeros(2),
        rotated(zeros(2));
        remaining_callbacks=TOTAL_CALLBACKS,
    )
    @test base_result.status == rotated_result.status == :seeded
    @test base_result.diagnostic.status == rotated_result.diagnostic.status == :applicable
    @test length(base_result.seeds) == length(rotated_result.seeds) == 2
    @test base_result.diagnostic.evidence.coarse_singular_values ≈
          rotated_result.diagnostic.evidence.coarse_singular_values rtol=1e-15 atol=1e-16
    @test base_result.diagnostic.evidence.fine_singular_values ≈
          rotated_result.diagnostic.evidence.fine_singular_values rtol=1e-15 atol=1e-16
    base_cpqr_rank = count(
        >(base_result.diagnostic.cpqr_threshold),
        base_result.diagnostic.coarse_cpqr_diagonal,
    )
    rotated_cpqr_rank = count(
        >(rotated_result.diagnostic.cpqr_threshold),
        rotated_result.diagnostic.coarse_cpqr_diagonal,
    )
    @test base_cpqr_rank == 1
    @test rotated_cpqr_rank == 2 # telemetry differs; applicability must not
    @test [
        (seed.lower_parameter, seed.upper_parameter) for seed in base_result.seeds
    ] == [
        (seed.lower_parameter, seed.upper_parameter) for seed in rotated_result.seeds
    ]
end

@testset "projected sign and bracket class are globally scale homogeneous" begin
    results = WeakBracketRescueResult[]
    for scale in (1.0, 1.0e-10, 1.0e-13)
        evaluate = point -> RescueEvaluation(scale .* [
            point[1],
            point[2]^2 - 1.0e-6,
        ])
        result = weak_bracket_rescue(
            evaluate,
            NormalizedBox(2),
            zeros(2),
            evaluate(zeros(2));
            remaining_callbacks=TOTAL_CALLBACKS,
        )
        @test result.status == :seeded
        @test result.callback_count == TOTAL_CALLBACKS
        push!(results, result)
    end
    reference = first(results)
    for result in results[2:end]
        @test result.probe.robust_signs == reference.probe.robust_signs
        @test result.probe.detected_bracket_count == reference.probe.detected_bracket_count
        @test [
            (seed.lower_parameter, seed.upper_parameter) for seed in result.seeds
        ] == [
            (seed.lower_parameter, seed.upper_parameter) for seed in reference.seeds
        ]
        @test result.diagnostic.evidence.weak_strong_ratio ≈
              reference.diagnostic.evidence.weak_strong_ratio rtol=2e-15
    end
    @test count(>(results[end].diagnostic.cpqr_threshold),
                results[end].diagnostic.coarse_cpqr_diagonal) == 1
end

@testset "even root, stationary nonroot, and manifold fail typed unknown" begin
    function run_residual(residual)
        evaluate = point -> RescueEvaluation(residual(point))
        endpoint = zeros(2)
        anchor = evaluate(endpoint)
        calls = Ref(0)
        result = weak_bracket_rescue(
            evaluate,
            NormalizedBox(2),
            endpoint,
            anchor;
            remaining_callbacks=TOTAL_CALLBACKS,
            charge_callback=() -> (calls[] += 1),
        )
        return result, calls[]
    end

    even, even_calls = run_residual(point -> [point[1], point[2]^2])
    @test even.status == :unknown
    @test even.reason == :even_or_tangent_projected_root
    @test even_calls == TOTAL_CALLBACKS
    @test isempty(even.seeds)

    stationary, stationary_calls = run_residual(
        point -> [point[1], point[2]^2 + 0.1],
    )
    @test stationary.status == :unknown
    @test stationary.reason == :no_sign_bracket
    @test stationary_calls == TOTAL_CALLBACKS
    @test isempty(stationary.seeds)

    manifold, manifold_calls = run_residual(point -> [point[1], 0.0])
    @test manifold.status == :unknown
    @test manifold.reason == :projected_manifold_or_unresolved_zero
    @test manifold_calls == TOTAL_CALLBACKS
    @test isempty(manifold.seeds)
end

@testset "branch, guard, and callback failures are fail-closed and symmetric" begin
    threshold = 1.0e-5
    semantic_rule = point -> (
        branch_identity=abs(point[2]) > threshold ? :other_branch : :branch,
        guard_identity=:guard,
        domain_identity=:domain,
        branch_margin=1.0,
        guard_margin=1.0,
        domain_margin=1.0,
        valid=true,
    )
    evaluate = clustered_evaluator(; semantic_rule)
    result, charged = run_clustered(; evaluate)
    @test result.status == :unknown
    @test result.reason == :probe_branch_or_guard_changed
    @test result.callback_count == charged == TOTAL_CALLBACKS
    @test isempty(result.seeds)

    throwing_calls = Ref(0)
    throwing = point -> begin
        throwing_calls[] += 1
        error("opaque callback failure")
    end
    anchor = RescueEvaluation([-1.0e-6, -1.0e-6])
    charged_throwing = Ref(0)
    failed = weak_bracket_rescue(
        throwing,
        NormalizedBox(2),
        zeros(2),
        anchor;
        remaining_callbacks=TOTAL_CALLBACKS,
        charge_callback=() -> (charged_throwing[] += 1),
    )
    @test failed.status == :unknown
    @test failed.reason == :evaluation_failed
    @test failed.callback_count == 8
    @test throwing_calls[] == charged_throwing[] == 8

    struct ExplosiveIdentity end
    Base.isequal(::ExplosiveIdentity, ::ExplosiveIdentity) = error("identity comparison")
    explosive = point -> RescueEvaluation(
        [point[1], point[2]^2 - 1.0e-6];
        branch_identity=ExplosiveIdentity(),
    )
    explosive_anchor = explosive(zeros(2))
    explosive_calls = Ref(0)
    explosive_result = weak_bracket_rescue(
        explosive,
        NormalizedBox(2),
        zeros(2),
        explosive_anchor;
        remaining_callbacks=TOTAL_CALLBACKS,
        charge_callback=() -> (explosive_calls[] += 1),
    )
    @test explosive_result.status == :unknown
    @test explosive_result.reason == :cpqr_branch_or_guard_changed
    @test explosive_result.callback_count == explosive_calls[] == 8
end

@testset "budget, bounds, and rank failures terminate without partial work" begin
    short_calls = Ref(0)
    short = weak_bracket_rescue(
        clustered_evaluator(),
        NormalizedBox(2),
        zeros(2),
        clustered_evaluator()(zeros(2));
        remaining_callbacks=TOTAL_CALLBACKS - 1,
        charge_callback=() -> (short_calls[] += 1),
    )
    @test short.status == :unknown
    @test short.reason == :insufficient_total_budget
    @test short.callback_count == short_calls[] == 0

    diagnostic_short_calls = Ref(0)
    diagnostic_short = acquire_cpqr_rank_evidence(
        clustered_evaluator(),
        NormalizedBox(2),
        zeros(2),
        clustered_evaluator()(zeros(2));
        remaining_callbacks=7,
        charge_callback=() -> (diagnostic_short_calls[] += 1),
    )
    @test diagnostic_short.status == :unknown
    @test diagnostic_short.reason == :insufficient_cpqr_reserve
    @test diagnostic_short.callback_count == diagnostic_short_calls[] == 0

    boundary_endpoint = [0.0, 1.0 - CPQR_FD_STEP / 2]
    boundary_anchor = clustered_evaluator()(boundary_endpoint)
    boundary_calls = Ref(0)
    boundary = weak_bracket_rescue(
        clustered_evaluator(),
        NormalizedBox(2),
        boundary_endpoint,
        boundary_anchor;
        remaining_callbacks=TOTAL_CALLBACKS,
        charge_callback=() -> (boundary_calls[] += 1),
    )
    @test boundary.status == :unknown
    @test boundary.reason == :cpqr_stencil_outside_normalized_box
    @test boundary.callback_count == boundary_calls[] == 0

    full_rank_evaluate = point -> RescueEvaluation(copy(point))
    full_rank_calls = Ref(0)
    full_rank = weak_bracket_rescue(
        full_rank_evaluate,
        NormalizedBox(2),
        zeros(2),
        full_rank_evaluate(zeros(2));
        remaining_callbacks=TOTAL_CALLBACKS,
        charge_callback=() -> (full_rank_calls[] += 1),
    )
    @test full_rank.status == :unknown
    @test full_rank.reason == :no_stable_one_dimensional_invariant_rank
    @test full_rank.callback_count == full_rank_calls[] == 8
end

@testset "signed/orthogonal variable and residual replicas preserve answer class" begin
    root = 1.0e-3
    base_result, _ = run_clustered(; root)
    variable_angle = 0.37
    residual_angle = -0.51
    variable_rotation = [
        cos(variable_angle) -sin(variable_angle)
        sin(variable_angle) cos(variable_angle)
    ]
    residual_rotation = [
        cos(residual_angle) -sin(residual_angle)
        sin(residual_angle) cos(residual_angle)
    ]
    base_residual(point) = [point[1], point[2]^2 - root^2]
    replica = point -> RescueEvaluation(
        residual_rotation * base_residual(transpose(variable_rotation) * point),
    )
    replica_anchor = replica(zeros(2))
    replica_result = weak_bracket_rescue(
        replica,
        NormalizedBox(2),
        zeros(2),
        replica_anchor;
        remaining_callbacks=TOTAL_CALLBACKS,
    )
    @test replica_result.status == :seeded
    @test length(replica_result.seeds) == length(base_result.seeds) == 2
    @test [
        (seed.lower_parameter, seed.upper_parameter) for seed in replica_result.seeds
    ] == [
        (seed.lower_parameter, seed.upper_parameter) for seed in base_result.seeds
    ]
    base_points = sort(base_result.seeds; by=seed -> seed.normalized_point[2])
    replica_points = sort(replica_result.seeds; by=seed ->
        (transpose(variable_rotation) * seed.normalized_point)[2])
    for index in eachindex(base_points)
        @test replica_points[index].normalized_point ≈
              variable_rotation * base_points[index].normalized_point atol=2e-12
    end
    @test replica_result.diagnostic.evidence.average_right_projector ≈
          variable_rotation * base_result.diagnostic.evidence.average_right_projector *
          transpose(variable_rotation) atol=2e-10
    @test replica_result.diagnostic.evidence.average_left_projector ≈
          residual_rotation * base_result.diagnostic.evidence.average_left_projector *
          transpose(residual_rotation) atol=2e-10
end
