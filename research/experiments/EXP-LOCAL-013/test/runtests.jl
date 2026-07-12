using GeoTargetBenchmarks
import GeoTargetCore
using LinearAlgebra
using Test

include(joinpath(@__DIR__, "..", "..", "EXP-LOCAL-010", "src", "ExperimentLocal010.jl"))
include(joinpath(@__DIR__, "..", "src", "ExperimentLocal013.jl"))
using .ExperimentLocal010
using .ExperimentLocal013

function fixture_case(
    dimension,
    residual_dimension,
    lower,
    upper,
    residual_scales,
    residual;
    guards=input -> (),
    branch=input -> nothing,
    public_guard_count=0,
    has_branch_token=false,
    semantics=input -> true,
    calls=Ref(0),
)
    evaluator = function (input)
        calls[] += 1
        values = Tuple(Float64.(residual(input)))
        raw_guards = Tuple(guards(input))
        finite = all(isfinite, values) && all(isfinite(guard.margin) for guard in raw_guards)
        valid = finite && semantics(input) && all(
            !guard.strict || guard.margin > 0 for guard in raw_guards
        )
        return SolverCaseEvaluation(
            values,
            finite ? Float64(first(input)) : nothing,
            valid,
            finite,
            raw_guards,
            branch(input),
        )
    end
    return SolverExperimentCase(
        dimension,
        residual_dimension,
        Tuple(Float64.(lower)),
        Tuple(Float64.(upper)),
        Tuple(ones(dimension)),
        Tuple(Float64.(residual_scales)),
        public_guard_count,
        has_branch_token,
        evaluator,
    )
end

strict_guard(token, margin; scale=1.0) =
    SolverPublicGuardObservation(token, margin, scale, true)

function diagnostic_fields(text)
    fields = Dict{String,String}()
    for entry in split(text, ';')
        parts = split(entry, '='; limit=2)
        length(parts) == 2 && (fields[String(first(parts))] = String(last(parts)))
    end
    return fields
end

candidate_variant() = guard_slack_variant(
    ExperimentLocal010.endpoint_correction_variant(; shadow=false);
    shadow=false,
)

shadow_variant() = guard_slack_variant(
    ExperimentLocal010.endpoint_correction_variant(; shadow=true);
    shadow=true,
)

@testset "frozen heuristic capability lane" begin
    candidate = candidate_variant()
    shadow = shadow_variant()
    @test candidate.name == CANDIDATE_NAME
    @test shadow.name == SHADOW_NAME
    @test candidate.configuration.mechanism ==
          "HEURISTIC-normalized-exponential-strict-guard-slack"
    @test candidate.configuration.public_capability_route == "public_guard_count>0"
    @test candidate.configuration.guardless_fallback == "E1-FD2-CPQR3"
    @test candidate.configuration.callback_cap == 600
    @test candidate.configuration.maximum_corrections == 3
    @test candidate.configuration.high_precision_answer_authority
    @test occursin("HEURISTIC", candidate.configuration.final_gate)
    @test_throws ArgumentError guard_slack_variant(
        ExperimentLocal010.endpoint_correction_variant(; shadow=true);
        shadow=false,
    )
    frozen_e1 = ExperimentLocal010.endpoint_correction_variant(; shadow=false)
    expected_e1_configuration = (;
        base="prod-tol-120x600",
        callback_cap=600,
        proof_step=cbrt(eps(Float64)),
        proof_radius=1.0e-6,
        maximum_corrections=3,
        shadow=false,
    )
    @test frozen_e1.configuration == expected_e1_configuration
    altered_configurations = (
        merge(expected_e1_configuration, (; base="legacy-lab-120x600")),
        merge(expected_e1_configuration, (; callback_cap=599)),
        merge(expected_e1_configuration, (; proof_step=nextfloat(cbrt(eps(Float64))))),
        merge(expected_e1_configuration, (; proof_radius=2.0e-6)),
        merge(expected_e1_configuration, (; maximum_corrections=2)),
        merge(expected_e1_configuration, (; shadow=true)),
        merge(expected_e1_configuration, (; extra_knob=true)),
    )
    for configuration in altered_configurations
        counterfeit = SolverVariant(
            frozen_e1.name, frozen_e1.run; configuration,
        )
        @test_throws ArgumentError guard_slack_variant(counterfeit; shadow=false)
    end

    source = read(joinpath(@__DIR__, "..", "src", "ExperimentLocal013.jl"), String)
    for forbidden in (
        "family_id", "instance_id", "gold_configurations", "gold_targets",
        "primitive_name", "plugin_id",
    )
        @test !occursin(forbidden, source)
    end
    @test !occursin("z_cutoff", lowercase(source))
    @test occursin("exp.(z)", source)
    @test occursin("_guard_separation", source)
end

@testset "guardless capability fallback is exactly frozen E1" begin
    direct_calls = Ref(0)
    routed_calls = Ref(0)
    make_case(calls) = fixture_case(
        2, 2, [-2, -2], [2, 2], [1, 1],
        input -> [input[1] - 0.25, input[2] + 0.5]; calls,
    )
    direct = ExperimentLocal010.endpoint_correction_variant().run(
        make_case(direct_calls), [1.2, 1.4],
    )
    routed = candidate_variant().run(make_case(routed_calls), [1.2, 1.4])
    @test routed.endpoint == direct.endpoint
    @test routed.evaluations == direct.evaluations
    @test routed_calls[] == direct_calls[]
    @test routed.status == direct.status
    @test routed.reported_accepted == direct.reported_accepted
end

@testset "positive strict margins across the frozen scale ladder" begin
    for delta in (1.0e-6, 1.0e-8, 1.0e-12)
        calls = Ref(0)
        case = fixture_case(
            1, 1, [-1], [1], [1], input -> [input[1] - delta];
            guards=input -> (strict_guard(0x11, input[1]),),
            public_guard_count=1,
            calls,
        )
        outcome = candidate_variant().run(case, [0.5])
        @test outcome.evaluations == calls[] <= ExperimentLocal013.CALLBACK_CAP
        @test outcome.endpoint !== nothing
        @test outcome.reported_accepted
        @test only(outcome.endpoint) ≈ delta atol=max(1.0e-14, delta * 1.0e-6)
        @test occursin("HEURISTIC", outcome.diagnostic)
        @test parse(Float64, diagnostic_fields(outcome.diagnostic)["separation_lower"]) > 0
    end
end

@testset "excluded boundary root is unknown with same-work shadow" begin
    candidate_calls = Ref(0)
    shadow_calls = Ref(0)
    make_case(calls) = fixture_case(
        1, 1, [-1], [1], [1], input -> [input[1]];
        guards=input -> (strict_guard(0x21, input[1]),),
        public_guard_count=1,
        calls,
    )
    candidate = candidate_variant().run(make_case(candidate_calls), [0.5])
    shadow = shadow_variant().run(make_case(shadow_calls), [0.5])
    @test candidate.endpoint === nothing
    @test candidate.status == STATUS_UNKNOWN
    @test !candidate.reported_accepted
    @test shadow.endpoint !== nothing
    @test candidate.evaluations == shadow.evaluations
    @test candidate_calls[] == shadow_calls[] == candidate.evaluations
    candidate_fields = diagnostic_fields(candidate.diagnostic)
    shadow_fields = diagnostic_fields(shadow.diagnostic)
    @test candidate_fields["reason"] ==
          "heuristic-guard-separation-unknown"
    for field in (
        "callbacks", "fd_calls", "trial_calls", "invalid_fd", "invalid_trials",
        "central_columns", "inward_columns", "proofs", "corrections",
        "trust_radius", "correction_radius", "separation_lower", "reason",
    )
        @test candidate_fields[field] == shadow_fields[field]
    end
end

@testset "curved, flat and two-guard charts" begin
    curved_delta = 1.0e-8
    curved_root = [0.25^2 + curved_delta, 0.25]
    curved = fixture_case(
        2, 2, [-1, -1], [1, 1], [1, 1],
        input -> [input[1] - curved_root[1], input[2] - curved_root[2]];
        guards=input -> (strict_guard(0x31, input[1] - input[2]^2),),
        public_guard_count=1,
    )
    curved_outcome = candidate_variant().run(curved, [0.4, 0.3])
    @test curved_outcome.endpoint !== nothing
    @test collect(curved_outcome.endpoint) ≈ curved_root atol=1.0e-10

    flat_delta = 1.0e-4
    flat = fixture_case(
        1, 1, [-1], [1], [1], input -> [input[1] - flat_delta];
        guards=input -> (strict_guard(0x32, input[1]^3),),
        public_guard_count=1,
    )
    flat_outcome = candidate_variant().run(flat, [0.2])
    @test flat_outcome.endpoint !== nothing
    @test only(flat_outcome.endpoint) ≈ flat_delta atol=1.0e-10

    two_root = [1.0e-6, 1.0e-8]
    two = fixture_case(
        2, 2, [-1, -1], [1, 1], [1, 1], input -> input .- two_root;
        guards=input -> (
            strict_guard(0x42, input[2]),
            strict_guard(0x41, input[1]),
        ),
        public_guard_count=2,
    )
    two_outcome = candidate_variant().run(two, [0.2, 0.3])
    @test two_outcome.endpoint !== nothing
    @test collect(two_outcome.endpoint) ≈ two_root atol=1.0e-10
end

@testset "positive guard scaling and token order are invariant" begin
    endpoints = Tuple[]
    evaluations = Int[]
    statuses = String[]
    for multiplier in (1.0e-12, 1.0, 1.0e12), order in (:forward, :reverse)
        root = [1.0e-8, 2.0e-8]
        guard_builder = order === :forward ?
            input -> (
                strict_guard(0x51, multiplier * input[1]; scale=multiplier),
                strict_guard(0x52, multiplier * input[2]; scale=multiplier),
            ) :
            input -> (
                strict_guard(0x52, multiplier * input[2]; scale=multiplier),
                strict_guard(0x51, multiplier * input[1]; scale=multiplier),
            )
        case = fixture_case(
            2, 2, [-1, -1], [1, 1], [1, 1], input -> input .- root;
            guards=guard_builder,
            public_guard_count=2,
        )
        outcome = candidate_variant().run(case, [0.2, 0.3])
        @test outcome.endpoint !== nothing
        push!(endpoints, outcome.endpoint)
        push!(evaluations, outcome.evaluations)
        push!(statuses, outcome.status)
    end
    @test all(
        endpoint -> isapprox(collect(endpoint), collect(first(endpoints)); atol=1.0e-12),
        endpoints,
    )
    @test all(==(STATUS_HEURISTIC), statuses)
    @test all(<=(ExperimentLocal013.CALLBACK_CAP), evaluations)
end

@testset "branch token instability and exp underflow are unknown" begin
    root = 0.25
    unstable = fixture_case(
        1, 1, [-1], [1], [1], input -> [input[1] - root];
        guards=input -> (strict_guard(0x61, input[1]),),
        branch=input -> abs(input[1] - root) < 1.0e-10 ? UInt64(1) : UInt64(2),
        public_guard_count=1,
        has_branch_token=true,
    )
    outcome = candidate_variant().run(unstable, [0.5])
    @test outcome.endpoint === nothing
    @test outcome.status == STATUS_UNKNOWN
    fields = diagnostic_fields(outcome.diagnostic)
    @test parse(Int, fields["invalid_fd"]) > 0
    @test parse(Int, fields["invalid_trials"]) == 0

    sample = ExperimentLocal013._Sample([0.0], [1.0])
    @test ExperimentLocal013._augmented(sample, [-1.0e3], [1.0]) === nothing
end

@testset "FD-invalid and trial-invalid counters are disjoint" begin
    case = fixture_case(
        1, 1, [-1], [1], [1], input -> [input[1]];
        guards=input -> (strict_guard(0x81, input[1] + 1),),
        branch=input -> abs(input[1]) < 0.1 ? UInt64(1) : UInt64(2),
        public_guard_count=1,
        has_branch_token=true,
    )
    bounds = (; origin=[0.0], half_range=[1.0])
    contract = ExperimentLocal013._GuardContract(UInt64[0x81], UInt64(1))

    fd_state = ExperimentLocal013._State(0)
    fd_cache = Dict{Tuple,Any}()
    @test ExperimentLocal013._evaluate_sample!(
        fd_cache, case, bounds, [0.5], contract, fd_state; fd=true,
    ) === nothing
    @test fd_state.calls == fd_state.fd_calls == fd_state.invalid_fd == 1
    @test fd_state.trial_calls == fd_state.invalid_trials == 0

    trial_state = ExperimentLocal013._State(0)
    trial_cache = Dict{Tuple,Any}()
    @test ExperimentLocal013._evaluate_sample!(
        trial_cache, case, bounds, [0.5], contract, trial_state; fd=false,
    ) === nothing
    @test trial_state.calls == trial_state.trial_calls == trial_state.invalid_trials == 1
    @test trial_state.fd_calls == trial_state.invalid_fd == 0
end

@testset "alpha-backtracked effective step does not expand trust radius" begin
    state = ExperimentLocal013._State(0)
    clipped_step = [1.0, 0.0]
    alpha = 0.5
    @test norm(clipped_step, 2) >= 0.9state.trust_radius
    accepted_effective = alpha .* clipped_step
    @test ExperimentLocal013._update_trust_radius!(
        state, 0.9, norm(accepted_effective, 2),
    ) == 1.0
    @test state.trust_radius == 1.0

    full_boundary_step = [0.95, 0.0]
    @test ExperimentLocal013._update_trust_radius!(
        state, 0.9, norm(full_boundary_step, 2),
    ) == 2.0
end

@testset "pre-outcome metamorphic answer classes" begin
    root = [1.0e-6, 2.0e-8]
    start = [0.2, 0.3]
    function guarded_case(tokens=(UInt64(0x91), UInt64(0x92)); multiplier=1.0)
        return fixture_case(
            2, 2, [-1, -1], [1, 1], [multiplier, multiplier],
            input -> multiplier .* (input .- root);
            guards=input -> (
                strict_guard(tokens[1], input[1]),
                strict_guard(tokens[2], input[2]),
            ),
            public_guard_count=2,
        )
    end
    function assert_safe(case, outcome)
        @test outcome.status == STATUS_HEURISTIC
        @test outcome.reported_accepted
        @test outcome.endpoint !== nothing
        @test outcome.evaluations <= ExperimentLocal013.CALLBACK_CAP
        evaluation = evaluate_case(case, collect(outcome.endpoint))
        @test evaluation.finite && evaluation.semantics_valid
        @test norm(
            collect(evaluation.residuals) ./ collect(case.residual_scales), Inf,
        ) <= ExperimentLocal013.RESIDUAL_TOLERANCE
        @test all(guard -> !guard.strict || guard.margin > 0, evaluation.public_guards)
        return collect(outcome.endpoint)
    end

    baseline_case = guarded_case()
    baseline = assert_safe(baseline_case, candidate_variant().run(baseline_case, start))

    relabel_case = guarded_case((UInt64(0x02), UInt64(0xf1)))
    relabel = assert_safe(relabel_case, candidate_variant().run(relabel_case, start))
    @test relabel ≈ baseline atol=1.0e-12

    for multiplier in (1.0e-12, 1.0e12)
        scaled_case = guarded_case(; multiplier)
        scaled = assert_safe(scaled_case, candidate_variant().run(scaled_case, start))
        @test scaled ≈ baseline atol=1.0e-12
    end

    transformed_root = [-root[2], root[1]]
    transformed_start = [-start[2], start[1]]
    transformed_case = fixture_case(
        2, 2, [-1, -1], [1, 1], [1, 1],
        input -> input .- transformed_root;
        guards=input -> (
            strict_guard(0x91, input[2]),
            strict_guard(0x92, -input[1]),
        ),
        public_guard_count=2,
    )
    transformed = assert_safe(
        transformed_case,
        candidate_variant().run(transformed_case, transformed_start),
    )
    mapped_back = [transformed[2], -transformed[1]]
    @test mapped_back ≈ baseline atol=1.0e-12
end

@testset "near-rank nonqualified base preserves pass-through contract" begin
    root = [0.25, 0.25]
    start = [0.25, 0.9]
    direct_calls = Ref(0)
    routed_calls = Ref(0)
    make_case(calls) = fixture_case(
        2, 2, [-1, -1], [1, 1], [1, 1],
        input -> [input[1] - root[1], 1.0e-10 * (input[2] - root[2])];
        guards=input -> (strict_guard(0x71, input[2]),),
        public_guard_count=1,
        calls,
    )
    direct_case = make_case(direct_calls)
    lower = [-1.0, -1.0]
    upper = [1.0, 1.0]
    direct_base, direct_evaluation = ExperimentLocal013._base_solve(
        direct_case, start, lower, upper, [0.0, 0.0], [1.0, 1.0],
    )
    @test !ExperimentLocal013._base_qualified(
        direct_base, direct_evaluation, lower, upper,
    )

    outcome = candidate_variant().run(make_case(routed_calls), start)
    @test outcome.endpoint == Tuple(direct_base.final)
    @test outcome.status == string(direct_base.status)
    @test outcome.reported_converged ==
          (direct_base.status == GeoTargetCore.LOCAL_CONVERGED)
    @test outcome.reported_accepted == direct_base.accepted
    @test outcome.evaluations == direct_base.evaluations
    @test outcome.iterations == direct_base.iterations
    @test routed_calls[] == outcome.evaluations
    @test diagnostic_fields(outcome.diagnostic)["reason"] == "base-pass-through"
    @test outcome.evaluations <= ExperimentLocal013.CALLBACK_CAP
end

@testset "near-rank qualified guard-crossing correction is unknown" begin
    root = [0.25, -0.25]
    start = [0.25, 0.9]
    epsilon = 5.0e-13
    direct_calls = Ref(0)
    candidate_calls = Ref(0)
    shadow_calls = Ref(0)
    make_case(calls) = fixture_case(
        2, 2, [-1, -1], [1, 1], [1, 1],
        input -> [input[1] - 0.25, epsilon * (input[2] + 0.25)];
        guards=input -> (strict_guard(0x72, input[2]),),
        public_guard_count=1,
        calls,
    )
    lower = [-1.0, -1.0]
    upper = [1.0, 1.0]
    direct_base, direct_evaluation = ExperimentLocal013._base_solve(
        make_case(direct_calls), start, lower, upper, [0.0, 0.0], [1.0, 1.0],
    )
    @test ExperimentLocal013._base_qualified(
        direct_base, direct_evaluation, lower, upper,
    )
    @test norm(collect(direct_base.final) .- root, Inf) > 1.0

    candidate = candidate_variant().run(make_case(candidate_calls), start)
    shadow = shadow_variant().run(make_case(shadow_calls), start)
    @test candidate.endpoint === nothing
    @test candidate.status == STATUS_UNKNOWN
    @test !candidate.reported_converged
    @test !candidate.reported_accepted
    @test shadow.endpoint == Tuple(direct_base.final)
    @test shadow.status == STATUS_UNKNOWN
    @test candidate.evaluations == shadow.evaluations <= ExperimentLocal013.CALLBACK_CAP
    @test candidate_calls[] == shadow_calls[] == candidate.evaluations
    candidate_fields = diagnostic_fields(candidate.diagnostic)
    shadow_fields = diagnostic_fields(shadow.diagnostic)
    @test candidate_fields["route"] == shadow_fields["route"] == "guarded-slack"
    for field in (
        "callbacks", "fd_calls", "trial_calls", "invalid_fd", "invalid_trials",
        "central_columns", "inward_columns", "proofs", "corrections",
        "trust_radius", "correction_radius", "separation_lower", "reason",
    )
        @test candidate_fields[field] == shadow_fields[field]
    end
end
