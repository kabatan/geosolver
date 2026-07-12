using GeoTargetBenchmarks
using Test

include(joinpath(@__DIR__, "..", "src", "ExperimentLocal011.jl"))
using .ExperimentLocal011

function fixture_case(
    dimension,
    residual_dimension,
    lower,
    upper,
    residual_scales,
    residual;
    semantics=input -> true,
    calls=Ref(0),
)
    evaluator = function (input)
        calls[] += 1
        values = Tuple(Float64.(residual(input)))
        finite = all(isfinite, values)
        return SolverCaseEvaluation(
            values,
            finite ? Float64(first(input)) : nothing,
            finite && semantics(input),
            finite,
        )
    end
    return SolverExperimentCase(
        dimension,
        residual_dimension,
        Tuple(Float64.(lower)),
        Tuple(Float64.(upper)),
        Tuple(ones(dimension)),
        Tuple(Float64.(residual_scales)),
        evaluator,
    )
end

function fields(diagnostic)
    return Dict(first(parts) => last(parts) for entry in split(diagnostic, ';') for
        parts in (split(entry, '='; limit=2),) if length(parts) == 2)
end

@testset "frozen endpoint-only SVD mechanism" begin
    candidate = e2_fd2_svd3_variant()
    shadow = e2_fd2_svd3_shadow_variant()
    @test candidate.name == CANDIDATE_NAME
    @test shadow.name == SHADOW_NAME
    @test candidate.configuration.base == "prod-tol-120x600"
    @test candidate.configuration.max_evaluations == 600
    @test candidate.configuration.max_corrections == 3
    @test candidate.configuration.bx_limit == 1.0e-6
    @test candidate.configuration.unknown_policy == "drop-endpoint"
    @test shadow.configuration.unknown_policy == "return-original-endpoint"
    source = read(joinpath(@__DIR__, "..", "src", "ExperimentLocal011.jl"), String)
    for forbidden in (
        "family_id", "instance_id", "gold_configurations", "gold_targets",
        "primitive_name", "plugin_id", "pinv(", "\\\\",
    )
        @test !occursin(forbidden, source)
    end
    @test occursin("svd(jacobian; full=false)", source)
end

@testset "regular correction and same-work shadow" begin
    candidate_calls = Ref(0)
    shadow_calls = Ref(0)
    residual(input) = [input[1] - 0.25, 2 * (input[2] + 0.5)]
    candidate_case = fixture_case(
        2, 2, [-2, -2], [2, 2], [1, 2], residual; calls=candidate_calls,
    )
    shadow_case = fixture_case(
        2, 2, [-2, -2], [2, 2], [1, 2], residual; calls=shadow_calls,
    )
    candidate = e2_fd2_svd3_variant().run(candidate_case, [1.5, 1.25])
    shadow = e2_fd2_svd3_shadow_variant().run(shadow_case, [1.5, 1.25])
    @test candidate.status == STATUS_CERTIFIED
    @test candidate.reported_accepted
    @test collect(candidate.endpoint) ≈ [0.25, -0.5] atol=1.0e-10
    @test candidate.evaluations == candidate_calls[] <= MAX_EVALUATIONS
    @test shadow.evaluations == shadow_calls[] == candidate.evaluations
    @test fields(candidate.diagnostic)["base_callbacks"] ==
          fields(shadow.diagnostic)["base_callbacks"]
    @test fields(candidate.diagnostic)["fd_calls"] == fields(shadow.diagnostic)["fd_calls"]
    @test fields(candidate.diagnostic)["armijo_calls"] ==
          fields(shadow.diagnostic)["armijo_calls"]
end

@testset "singular and manifold endpoints are unknown, not truncated" begin
    singular = fixture_case(
        2, 2, [-2, -2], [2, 2], [1, 1],
        input -> [input[1] + input[2] - 1, 2 * (input[1] + input[2] - 1)],
    )
    outcome = e2_fd2_svd3_variant().run(singular, [0.0, 0.0])
    @test outcome.status == STATUS_UNKNOWN
    @test outcome.endpoint === nothing
    @test !outcome.reported_accepted
    @test fields(outcome.diagnostic)["reason"] == "proof-unknown"

    underdetermined = fixture_case(
        2, 1, [-1, -1], [1, 1], [1], input -> [input[1]],
    )
    under = e2_fd2_svd3_variant().run(underdetermined, [0.5, 0.5])
    @test under.endpoint === nothing
    @test fields(under.diagnostic)["reason"] == "m-lt-n"
end

@testset "strict boundary ghost is dropped" begin
    candidate_calls = Ref(0)
    shadow_calls = Ref(0)
    boundary = fixture_case(
        1, 1, [0], [1], [1], input -> [input[1] - 1];
        semantics=input -> input[1] < 1,
        calls=candidate_calls,
    )
    shadow_boundary = fixture_case(
        1, 1, [0], [1], [1], input -> [input[1] - 1];
        semantics=input -> input[1] < 1,
        calls=shadow_calls,
    )
    outcome = e2_fd2_svd3_variant().run(boundary, [0.5])
    shadow = e2_fd2_svd3_shadow_variant().run(shadow_boundary, [0.5])
    @test outcome.endpoint === nothing
    @test outcome.status == STATUS_UNKNOWN
    @test !outcome.reported_accepted
    @test shadow.endpoint !== nothing
    @test outcome.evaluations == shadow.evaluations
    @test candidate_calls[] == shadow_calls[] == outcome.evaluations
    @test fields(outcome.diagnostic)["invalid_armijo_calls"] ==
          fields(shadow.diagnostic)["invalid_armijo_calls"]
end

@testset "nonqualified base endpoint is a zero-probe pass-through" begin
    candidate_calls = Ref(0)
    shadow_calls = Ref(0)
    make_case(calls) = fixture_case(
        1, 1, [-1], [1], [1], input -> [input[1] - 0.25];
        semantics=input -> false,
        calls,
    )
    candidate = e2_fd2_svd3_variant().run(make_case(candidate_calls), [0.0])
    shadow = e2_fd2_svd3_shadow_variant().run(make_case(shadow_calls), [0.0])
    @test candidate.endpoint == shadow.endpoint
    @test candidate.evaluations == shadow.evaluations
    @test candidate_calls[] == shadow_calls[] == candidate.evaluations
    @test fields(candidate.diagnostic)["reason"] == "base-pass-through"
    @test fields(candidate.diagnostic)["callbacks"] ==
          fields(candidate.diagnostic)["base_callbacks"]
    @test fields(candidate.diagnostic)["fd_calls"] == "0"
    @test fields(candidate.diagnostic)["armijo_calls"] == "0"
end

@testset "declared row-scale and signed-permutation replicas" begin
    base = fixture_case(
        2, 2, [-2, -2], [2, 2], [1, 1],
        input -> [input[1] - 0.25, input[2] + 0.5],
    )
    row_scaled = fixture_case(
        2, 2, [-2, -2], [2, 2], [1.0e9, 1.0e-7],
        input -> [1.0e9 * (input[1] - 0.25), 1.0e-7 * (input[2] + 0.5)],
    )
    signed_permuted = fixture_case(
        2, 2, [-2, -2], [2, 2], [1, 1],
        input -> [input[2] - 0.25, -input[1] + 0.5],
    )
    a = e2_fd2_svd3_variant().run(base, [1.1, 1.2])
    b = e2_fd2_svd3_variant().run(row_scaled, [1.1, 1.2])
    c = e2_fd2_svd3_variant().run(signed_permuted, [-1.2, 1.1])
    @test a.status == b.status == c.status == STATUS_CERTIFIED
    @test collect(a.endpoint) ≈ collect(b.endpoint) atol=1.0e-9
    @test collect(a.endpoint) ≈ [c.endpoint[2], -c.endpoint[1]] atol=1.0e-9
end

@testset "rounding-aware rank and bx gates are explicit" begin
    @test BX_LIMIT == 1.0e-6
    source = read(joinpath(@__DIR__, "..", "src", "ExperimentLocal011.jl"), String)
    @test occursin("sigma_min > 2eta", source)
    @test occursin("norm(solve_h.step .- solve_h2.step, 2)", source)
    @test occursin("rounding_h .+ rounding_h2", source)
    @test occursin("ARMIJO_ALPHAS", source)
end

@testset "central semantic invalidity cannot select a one-sided escape" begin
    h = ExperimentLocal011.FD_RADIUS
    case = fixture_case(
        1, 1, [-1], [1], [1], input -> [input[1]];
        semantics=input -> !(0.9h < input[1] < 1.1h),
    )
    bounds = ExperimentLocal011._bounds_map(case)
    state = ExperimentLocal011._State(0)
    pair = ExperimentLocal011._fd_pair(case, bounds, [0.0], [0.0], state)
    @test pair === nothing
    @test state.central_columns == 0
    @test state.one_sided_columns == 0
    @test state.invalid_fd_calls == 1

    capped_calls = Ref(0)
    capped_case = fixture_case(
        1, 1, [-1], [1], [1], input -> [input[1]]; calls=capped_calls,
    )
    capped_state = ExperimentLocal011._State(MAX_EVALUATIONS)
    @test ExperimentLocal011._evaluate_scaled(
        capped_case, ExperimentLocal011._bounds_map(capped_case), [0.0], capped_state;
        fd=true,
    ) === nothing
    @test capped_calls[] == 0
    @test capped_state.calls == MAX_EVALUATIONS
end
