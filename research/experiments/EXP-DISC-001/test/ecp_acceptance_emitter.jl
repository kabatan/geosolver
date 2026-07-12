using LinearAlgebra
using Test

include(joinpath(@__DIR__, "..", "src", "ecp_acceptance_emitter.jl"))
using .ECPAcceptanceEmitter

valid(residual) = ECPObservation(residual)
invalid() = ECPObservation([0.0]; canonical_valid=false)

function assert_public_numeric_finite_or_null(value)
    value === nothing && return
    if value isa Number
        @test isfinite(value)
        return
    elseif value isa Symbol || value isa AbstractString || value isa Enum
        return
    elseif value isa AbstractArray
        foreach(assert_public_numeric_finite_or_null, value)
        return
    end
    names = fieldnames(typeof(value))
    isempty(names) && return
    foreach(name -> assert_public_numeric_finite_or_null(getfield(value, name)), names)
end

function twin_residual(point)
    return valid([min(abs(point[1] + 0.5), abs(point[1] - 1.0))])
end

@testset "official minimization acceptance inequality" begin
    points = [[-1.0], [0.0]]
    rewards = [-1.0, 0.0]
    @test acceptance_envelope([1.0], points, rewards, 0.5) == 0.0
    @test acceptance_envelope([1.0], points, rewards, prevfloat(0.5)) < 0.0
    @test acceptance_envelope([1.0], points, rewards, 0.5) >= maximum(rewards)
    @test_throws ArgumentError acceptance_envelope([1.0], Vector{Vector{Float64}}(), Float64[], 0.5)

    raw = reshape([-1.0, -0.5, 1.0], 1, :)
    calls = Ref(0)
    result = emit_ecp(point -> (calls[] += 1; twin_residual(point)), raw; arm=ECP_V1)
    @test calls[] == 2
    @test [proposal.raw_draw_index for proposal in result.proposals] == [1, 2]
    @test result.proposals[1].optimistic_envelope === nothing
    @test result.proposals[1].best_reward_before === nothing
    @test result.proposals[2].optimistic_envelope !== nothing
    @test result.proposals[2].best_reward_before !== nothing
    @test result.diagnostics.rejected_unscored_draws == 1
end

@testset "bounded stable phi and residual-row permutation" begin
    residual = [1.0e-200, -3.0, 4.0, 2.0e-100]
    @test stable_phi(valid(residual)) == stable_phi(valid(residual[[3, 1, 4, 2]]))
    @test stable_phi(valid([0.0])) == (0.0, true)
    @test stable_phi(valid([1.0])) == (0.5, true)
    @test stable_phi(valid([floatmax(Float64), floatmax(Float64)])) ==
        (prevfloat(1.0), true)
    @test stable_phi(invalid()) == (1.0, false)
    @test stable_phi(valid([NaN])) == (1.0, false)
    @test stable_phi(valid(Float64[])) == (1.0, false)

    raw = [
        [0.38sin(0.73index) for index in 1:160]';
        [0.38cos(1.17index) for index in 1:160]';
    ]
    base(point) = valid([point[1] - 0.2, 2point[2] + 0.1, point[1] * point[2]])
    permuted(point) = begin
        observation = base(point)
        valid(observation.scaled_residual[[3, 1, 2]])
    end
    for arm in (ECP_V1, ECP_LB_FULL)
        left = emit_ecp(base, raw; arm)
        right = emit_ecp(permuted, raw; arm)
        @test [item.raw_draw_index for item in left.proposals] ==
            [item.raw_draw_index for item in right.proposals]
        @test [item.phi for item in left.proposals] == [item.phi for item in right.proposals]
    end
end

@testset "V1 and full-memory ECPv2 lower-bound recurrences" begin
    tau = 1.0 + 1.0 / ACCEPTED_SCREEN_CAP
    flat_raw = reshape(collect(range(-1.0, 1.0; length=ACCEPTED_SCREEN_CAP)), 1, :)
    for arm in (ECP_V1, ECP_LB_FULL), screen in (_ -> valid([2.0]), _ -> invalid())
        result = emit_ecp(screen, flat_raw; arm)
        @test result.diagnostics.status == ECP_COMPLETE
        @test length(result.proposals) == ACCEPTED_SCREEN_CAP
        @test result.diagnostics.logical_screening_callbacks == ACCEPTED_SCREEN_CAP
        @test result.diagnostics.accepted_screening_callbacks == ACCEPTED_SCREEN_CAP
        @test result.diagnostics.rejected_unscored_draws == 0
        @test result.diagnostics.fallback_requests == 0
        @test result.diagnostics.epsilon_final ≈ EPSILON0 * tau^47 rtol=8eps()
        @test result.diagnostics.lower_bound_update_count == 0
    end

    # Pre-outcome counterexample: equal-depth roots at -0.5 and 1.0.  The
    # caller fixes the raw stream; neither arm sees root/target truth.
    twin_raw = reshape(vcat(-1.0, -0.5, fill(1.0, 62)), 1, :)
    v1 = emit_ecp(twin_residual, twin_raw; arm=ECP_V1)
    lb = emit_ecp(twin_residual, twin_raw; arm=ECP_LB_FULL)
    @test [proposal.raw_draw_index for proposal in v1.proposals] == [1, 2]
    @test length(v1.fallbacks) == 46
    @test length(lb.proposals) == ACCEPTED_SCREEN_CAP
    @test lb.proposals[3].point == [1.0]
    @test count(proposal -> proposal.phi == 0.0, lb.proposals) == 47
    @test lb.diagnostics.lower_bound_update_count == 1
    @test lb.proposals[3].epsilon_used ≈ 1 / 6
    @test lb.diagnostics.epsilon_final ≈ (1 / 6) * tau^46 rtol=2e-14
end

@testset "paper h recurrence and official-repository first-rejection defect" begin
    # The paper starts h_1=1,h_2=0.  This first rejection is therefore
    # current_h=1, previous_h=1: no growth and no deque-length division.
    first_rejection = emit_ecp(twin_residual, reshape([-1.0, -0.5, 1.0], 1, :); arm=ECP_V1)
    @test first_rejection.diagnostics.rejection_growth_count == 0
    @test first_rejection.diagnostics.previous_round_h_final == 1
    @test first_rejection.diagnostics.current_round_h_final == 1

    # Complete one round with h=5, then pin the next threshold to C+h_prev:
    # current_h=1001 does not grow, while current_h=1006 does and resets to 0.
    phi_at_minus_one = 0.015
    residual_at_minus_one = phi_at_minus_one / (1 - phi_at_minus_one)
    scale = 2residual_at_minus_one
    h_fixture(point) = valid([
        scale * min(abs(point[1] + 0.5), abs(point[1] - 1.0)),
    ])
    prefix = vcat(-1.0, -0.5, fill(0.0, 4), 1.0)
    before_growth_raw = reshape(vcat(prefix, fill(0.0, REJECTION_GROWTH_C + 1)), 1, :)
    before_growth = emit_ecp(h_fixture, before_growth_raw; arm=ECP_V1)
    @test length(before_growth.proposals) == 3
    @test before_growth.diagnostics.previous_round_h_final == 5
    @test before_growth.diagnostics.current_round_h_final == REJECTION_GROWTH_C + 1
    @test before_growth.diagnostics.rejection_growth_count == 0

    growth_raw = reshape(vcat(prefix, fill(0.0, REJECTION_GROWTH_C + 6)), 1, :)
    calls = Ref(0)
    result = emit_ecp(point -> (calls[] += 1; h_fixture(point)), growth_raw; arm=ECP_V1)
    tau = 1.0 + 1.0 / ACCEPTED_SCREEN_CAP
    @test calls[] == 3
    @test result.diagnostics.rejected_unscored_draws == 4 + REJECTION_GROWTH_C + 6
    @test result.diagnostics.rejection_growth_count == 1
    @test result.diagnostics.previous_round_h_final == 5
    @test result.diagnostics.current_round_h_final == 0
    @test result.diagnostics.epsilon_final ≈ EPSILON0 * tau^3 rtol=12eps()
end

@testset "paper growth check precedes acceptance" begin
    tau = 1.0 + 1.0 / ACCEPTED_SCREEN_CAP
    epsilon_before = EPSILON0 * tau^2
    epsilon_after = epsilon_before * tau
    acceptance_threshold = sqrt(epsilon_before * epsilon_after)
    phi_at_minus_one = acceptance_threshold
    residual_at_minus_one = phi_at_minus_one / (1 - phi_at_minus_one)
    scale = 2residual_at_minus_one
    gentle_twin(point) = valid([
        scale * min(abs(point[1] + 0.5), abs(point[1] - 1.0)),
    ])
    prefix = vcat(-1.0, -0.5, fill(0.0, 4), 1.0)
    raw = reshape(vcat(prefix, fill(0.0, REJECTION_GROWTH_C + 6)), 1, :)
    result = emit_ecp(gentle_twin, raw; arm=ECP_V1)
    @test [proposal.raw_draw_index for proposal in result.proposals] == [1, 2, 7, 1_013]
    @test result.proposals[end].point == [0.0]
    @test result.proposals[end].epsilon_used ≈ epsilon_after rtol=12eps()
    @test result.proposals[end].optimistic_envelope >=
        result.proposals[end].best_reward_before
    @test result.diagnostics.rejection_growth_count == 1
    @test result.diagnostics.previous_round_h_final == 0
    @test result.diagnostics.current_round_h_final == 0
end

@testset "invalid moat, callback failure, and evaluated evidence retention" begin
    raw = reshape(vcat(0.9, 0.0, fill(0.95, 62)), 1, :)
    calls = Ref(0)
    function moat(point)
        calls[] += 1
        abs(point[1]) > 0.8 && return invalid()
        return valid([point[1]])
    end
    result = emit_ecp(moat, raw; arm=ECP_V1)
    @test calls[] == 2
    @test length(result.proposals) == 2
    @test result.diagnostics.invalid_count == 1
    @test result.proposals[1].phi == 1.0
    @test result.proposals[1].canonical_valid == false
    @test result.diagnostics.screened_evidence_discard_count == 0
    @test result.diagnostics.all_evaluated_proposals_retained

    failed = emit_ecp(_ -> error("screen failure"), zeros(1, ACCEPTED_SCREEN_CAP))
    @test length(failed.proposals) == ACCEPTED_SCREEN_CAP
    @test failed.diagnostics.callback_failure_count == ACCEPTED_SCREEN_CAP
    @test failed.diagnostics.invalid_count == ACCEPTED_SCREEN_CAP
    @test all(proposal -> proposal.callback_failed && proposal.phi == 1.0, failed.proposals)
end

@testset "typed fresh-IID fallback and hard raw-draw termination" begin
    short = emit_ecp(twin_residual, reshape([-1.0, -0.5, 1.0], 1, :); arm=ECP_V1)
    @test length(short.proposals) == 2
    @test length(short.fallbacks) == 46
    @test all(request -> request.source == :fresh_iid, short.fallbacks)
    @test all(request -> request.reason == :raw_candidates_exhausted, short.fallbacks)
    @test short.diagnostics.logical_screening_callbacks == ACCEPTED_SCREEN_CAP

    cap_raw = reshape(vcat(-1.0, -0.5, fill(1.0, RAW_DRAW_CAP - 1)), 1, :)
    capped = emit_ecp(twin_residual, cap_raw; arm=ECP_V1)
    @test capped.diagnostics.raw_draws_consumed == RAW_DRAW_CAP
    @test capped.diagnostics.rejected_unscored_draws == RAW_DRAW_CAP - 2
    paper_cycle = REJECTION_GROWTH_C + 2 # previous_h=1 and strict `>`
    @test capped.diagnostics.rejection_growth_count == div(RAW_DRAW_CAP - 2, paper_cycle)
    @test capped.diagnostics.previous_round_h_final == 1
    @test capped.diagnostics.current_round_h_final == mod(RAW_DRAW_CAP - 2, paper_cycle)
    @test capped.diagnostics.reason == :raw_draw_cap_reached
    @test length(capped.proposals) == 2
    @test length(capped.fallbacks) == 46
    @test all(request -> request.reason == :raw_draw_cap_reached, capped.fallbacks)
end

@testset "transported signed-permutation and orthogonal replicas" begin
    raw = [
        [0.32sin(0.61index) for index in 1:180]';
        [0.32cos(1.03index) for index in 1:180]';
    ]
    screen(point) = valid([point[1] - 0.17, 0.7point[2] + 0.11, point[1] * point[2]])
    transforms = (
        [0.0 -1.0; 1.0 0.0],
        [cos(0.37) -sin(0.37); sin(0.37) cos(0.37)],
    )
    for arm in (ECP_V1, ECP_LB_FULL), transform in transforms
        transported_raw = transform * raw
        @test all(value -> -1.0 <= value <= 1.0, transported_raw)
        base = emit_ecp(screen, raw; arm)
        replica = emit_ecp(point -> screen(transform' * point), transported_raw; arm)
        @test [item.raw_draw_index for item in base.proposals] ==
            [item.raw_draw_index for item in replica.proposals]
        @test length(base.proposals) == length(replica.proposals)
        for (left, right) in zip(base.proposals, replica.proposals)
            @test left.point ≈ transform' * right.point atol=2e-15 rtol=2e-15
            @test left.phi ≈ right.phi atol=4eps() rtol=4eps()
        end
    end
end

@testset "no mutation, aliasing, authority, or nonfinite artifact fields" begin
    raw = repeat(reshape([-0.25, 0.5], 2, 1), 1, ACCEPTED_SCREEN_CAP)
    original = copy(raw)
    function mutating_screen(point)
        point .= 99.0
        return valid([0.0])
    end
    result = emit_ecp(mutating_screen, raw)
    @test raw == original
    @test length(result.proposals) == ACCEPTED_SCREEN_CAP
    @test all(proposal -> proposal.point == original[:, 1], result.proposals)
    result.proposals[1].point[1] = 77.0
    @test result.proposals[2].point == original[:, 1]
    @test raw == original
    @test !result.diagnostics.answer_authority
    @test !result.diagnostics.target_authority
    @test !result.diagnostics.gold_authority
    @test !result.diagnostics.completeness_authority
    assert_public_numeric_finite_or_null(result)

    inapplicable = emit_ecp(_ -> valid([0.0]), fill(NaN, 1, 1))
    @test inapplicable.diagnostics.status == ECP_INAPPLICABLE_RAW_MATRIX
    @test inapplicable.diagnostics.tau === nothing
    @test length(inapplicable.fallbacks) == ACCEPTED_SCREEN_CAP
    assert_public_numeric_finite_or_null(inapplicable)

    empty_source = emit_ecp(_ -> valid([0.0]), zeros(2, 0))
    @test empty_source.diagnostics.status == ECP_FALLBACK_REQUIRED
    @test empty_source.diagnostics.logical_screening_callbacks == ACCEPTED_SCREEN_CAP
    @test length(empty_source.fallbacks) == ACCEPTED_SCREEN_CAP
    assert_public_numeric_finite_or_null(empty_source)
end
