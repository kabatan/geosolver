using GeoTargetBenchmarks
using LinearAlgebra
using Test

include(joinpath(@__DIR__, "..", "src", "ExperimentLocal012.jl"))
using .ExperimentLocal012

function sample(residual, guard_specs=(); branch=UInt64(7), semantics=nothing)
    guards = Tuple(
        SolverPublicGuardObservation(token, value * scale, scale, strict) for
        (token, value, scale, strict) in guard_specs
    )
    guard_valid = all(guard -> guard.strict ? guard.margin > 0 : guard.margin >= 0, guards)
    valid = semantics === nothing ? guard_valid : semantics
    return GuardChartSample(residual, valid, true, guards, branch)
end

function run_kernel(evaluator, x0; shadow=false, base_evaluations=1)
    base = evaluator(collect(Float64, x0))
    dimension = length(x0)
    return correct_endpoint(
        evaluator,
        x0,
        base,
        base_evaluations,
        zeros(dimension),
        ones(dimension),
        -ones(dimension),
        ones(dimension);
        shadow,
    )
end

function guarded_evaluator(kind, delta; token=UInt64(11), guard_scale=1.0)
    return function (x)
        residual = if kind === :linear
            [x[1]]
        elseif kind === :curved
            [x[1] + 0.25x[1]^2]
        elseif kind === :coupled
            [x[1] + 0.2x[2], 0.1x[1] + x[2]]
        else
            error("unknown residual structure")
        end
        return sample(
            residual,
            ((token, x[1] + delta, guard_scale, true),),
        )
    end
end

@testset "positive public-guard margins retain three residual structures" begin
    for delta in (1.0e-6, 1.0e-8, 1.0e-12), kind in (:linear, :curved, :coupled)
        x0 = kind === :coupled ? [4.0e-13, 0.0] : [4.0e-13]
        result = run_kernel(guarded_evaluator(kind, delta), x0)
        @test result.status == :heuristic
        @test result.failure == PROOF_NONE
        @test result.endpoint !== nothing
        @test result.chart_columns >= 1
        @test result.minimum_guard_lower > 0
        @test result.evaluations <= CALLBACK_CAP
    end
end

@testset "strict-boundary ghost remains UNKNOWN" begin
    evaluator = guarded_evaluator(:linear, 0.0)
    result = run_kernel(evaluator, [4.0e-13])
    @test result.status == :unknown
    @test result.endpoint === nothing
    @test result.failure in (PROOF_ARMIJO, PROOF_GUARD_INTERIOR)
    @test result.evaluations <= CALLBACK_CAP
end

@testset "NearRank-like residual-qualified large step remains UNKNOWN" begin
    epsilon = 5.0e-13
    evaluator = x -> sample([x[1], epsilon * (x[2] - 1.0)], (); branch=nothing)
    result = run_kernel(evaluator, [0.0, 0.0])
    @test result.status == :unknown
    @test result.endpoint === nothing
    @test result.failure == PROOF_BACKWARD_ERROR
    @test result.chart_columns == 0
end

@testset "same-work shadow returns the original endpoint" begin
    evaluator = guarded_evaluator(:linear, 1.0e-8)
    candidate = run_kernel(evaluator, [4.0e-13])
    shadow = run_kernel(evaluator, [4.0e-13]; shadow=true)
    @test candidate.status == shadow.status == :heuristic
    @test candidate.evaluations == shadow.evaluations
    @test candidate.corrections == shadow.corrections
    @test candidate.proofs == shadow.proofs
    @test candidate.trials == shadow.trials
    @test candidate.chart_columns == shadow.chart_columns
    @test candidate.endpoint != shadow.endpoint
    @test shadow.endpoint == (4.0e-13,)
end

@testset "Armijo invalid full step uses only the fixed shorter alpha" begin
    root = 4.0e-13
    full_step = 2root
    invalid_lower = 6.0e-13
    invalid_upper = 1.0e-12
    curvature = 1 / root

    function evaluator(mode, log)
        return function (x)
            push!(log, x[1])
            residual = [x[1] + curvature * x[1]^2 - full_step]
            guard_value = mode === :guard ? invalid_lower - x[1] : 1.0
            branch = mode === :branch && invalid_lower < x[1] < invalid_upper ?
                     UInt64(2) : UInt64(1)
            non_guard_invalid = mode === :non_guard && invalid_lower < x[1] < invalid_upper
            guard_valid = guard_value > 0
            return sample(
                residual,
                ((UInt64(61), guard_value, 1.0, true),);
                branch,
                semantics=guard_valid && !non_guard_invalid,
            )
        end
    end

    @test ALPHAS == (1.0, 0.5, 0.25, 0.125)
    for mode in (:guard, :branch, :non_guard)
        candidate_log = Float64[]
        shadow_log = Float64[]
        candidate = run_kernel(evaluator(mode, candidate_log), [0.0])
        shadow = run_kernel(evaluator(mode, shadow_log), [0.0]; shadow=true)
        @test candidate.status == shadow.status == :heuristic
        @test candidate.trials == shadow.trials == 2
        @test candidate.corrections == shadow.corrections == 1
        @test candidate.evaluations == shadow.evaluations
        @test candidate_log == shadow_log
        small_trials = filter(value -> 0 < value < 2.0e-12, candidate_log)
        # The first two are the fixed alpha=1 and alpha=1/2 Armijo trials.
        # A later value may be the mandatory direct predicted-center check.
        @test length(small_trials) >= 2
        @test small_trials[1] ≈ full_step atol=1.0e-21 rtol=0
        @test small_trials[2] ≈ root atol=1.0e-21 rtol=0
        @test all(value -> isapprox(value, root; atol=1.0e-21, rtol=0), small_trials[2:end])
        @test candidate.endpoint !== nothing
        @test only(candidate.endpoint) ≈ root atol=1.0e-21 rtol=0
        @test shadow.endpoint == (0.0,)
    end
end

@testset "oscillatory guard without a unique interior chart is UNKNOWN" begin
    h = cbrt(eps(Float64))
    delta = 1.0e-8
    amplitude = 2.0e-8
    evaluator = function (x)
        guard = delta + amplitude * cos(2pi * x[1] / h)
        return sample([x[1]], ((UInt64(5), guard, 1.0, true),))
    end
    result = run_kernel(evaluator, [0.0])
    @test result.status == :unknown
    @test result.endpoint === nothing
    @test result.failure == PROOF_GUARD_CHART_UNAVAILABLE
end

@testset "finite samples are explicitly not a guard proof" begin
    h = cbrt(eps(Float64))
    points = (0.0, -h, -h / 2, h / 2, h)
    delta = 1.0e-6
    polynomial = x -> prod((x - point)^2 for point in points)
    midpoint = h / 4
    amplitude = 2delta / polynomial(midpoint)
    constant_guard = x -> delta
    alias_guard = x -> delta - amplitude * polynomial(x)
    constant_result = run_kernel(
        x -> sample([x[1]], ((UInt64(1), constant_guard(x[1]), 1.0, true),)),
        [0.0],
    )
    alias_result = run_kernel(
        x -> sample([x[1]], ((UInt64(1), alias_guard(x[1]), 1.0, true),)),
        [0.0],
    )
    @test constant_result.status == alias_result.status == :heuristic
    @test constant_result.endpoint == alias_result.endpoint
    @test constant_result.evaluations == alias_result.evaluations
    @test alias_guard(midpoint) < 0
    @test !occursin("certified", String(alias_result.status))
    @test !occursin("validated", String(alias_result.status))
end

@testset "guard token order, relabel and scale do not change the answer" begin
    function evaluator(x, mode)
        first = mode === :plain ? (UInt64(1), x[1] + 1.0e-8, 1.0, true) :
                (UInt64(91), (x[1] + 1.0e-8), 1.0e9, true)
        second = mode === :plain ? (UInt64(2), 2.0e-8, 1.0, true) :
                 (UInt64(17), 2.0e-8, 1.0e-9, true)
        specs = mode === :plain ? (first, second) : (second, first)
        return sample([x[1]], specs)
    end
    plain = run_kernel(x -> evaluator(x, :plain), [4.0e-13])
    transformed = run_kernel(x -> evaluator(x, :transformed), [4.0e-13])
    @test plain.status == transformed.status == :heuristic
    @test collect(plain.endpoint) ≈ collect(transformed.endpoint) atol=1.0e-15 rtol=0
    @test plain.failure == transformed.failure
end

@testset "signed coordinate permutation preserves the answer class" begin
    transform = [0.0 -1.0; 1.0 0.0]
    matrix = [1.0 0.2; 0.1 1.0]
    delta = 1.0e-8
    original_evaluator = x -> sample(
        matrix * x,
        ((UInt64(3), x[1] + delta, 1.0, true),),
    )
    transformed_evaluator = y -> begin
        x = transform' * y
        sample(
            transform * (matrix * x),
            ((UInt64(77), x[1] + delta, 1.0e6, true),),
        )
    end
    x0 = [4.0e-13, 0.0]
    original = run_kernel(original_evaluator, x0)
    transformed = run_kernel(transformed_evaluator, transform * x0)
    @test original.status == transformed.status == :heuristic
    @test collect(transformed.endpoint) ≈ transform * collect(original.endpoint) atol=1.0e-15 rtol=0
end

@testset "branch changes cannot be charted" begin
    evaluator = function (x)
        branch = x[1] > 0 ? UInt64(2) : UInt64(1)
        sample(
            [x[1]],
            ((UInt64(4), x[1] + 1.0e-8, 1.0, true),);
            branch,
        )
    end
    result = run_kernel(evaluator, [4.0e-13])
    @test result.status == :unknown
    @test result.failure in (PROOF_BRANCH_CHANGE, PROOF_GUARD_CHART_UNAVAILABLE)
end

@testset "non-guard semantics and budget failures remain typed UNKNOWN" begin
    h = cbrt(eps(Float64))
    semantics_evaluator = function (x)
        valid = abs(x[1]) < h / 4
        sample(
            [x[1]],
            ((UInt64(8), 1.0, 1.0, true),);
            semantics=valid,
        )
    end
    semantics_result = run_kernel(semantics_evaluator, [0.0])
    @test semantics_result.status == :unknown
    @test semantics_result.failure == PROOF_NON_GUARD_SEMANTICS

    budget_result = run_kernel(
        guarded_evaluator(:linear, 1.0e-8),
        [4.0e-13];
        base_evaluations=599,
    )
    @test budget_result.status == :unknown
    @test budget_result.failure == PROOF_BUDGET
    @test budget_result.evaluations == CALLBACK_CAP
end

@testset "a unique bounds-interior chart is allowed" begin
    evaluator = x -> sample([x[1] - 1.0], ((UInt64(2), 1.0, 1.0, true),))
    result = run_kernel(evaluator, [1.0])
    @test result.status == :heuristic
    @test result.chart_columns >= 1
    @test result.endpoint == (1.0,)
end

@testset "noneligible endpoints pass through with zero correction work" begin
    evaluator = x -> sample([1.0e-4], ((UInt64(1), 1.0, 1.0, true),))
    result = run_kernel(evaluator, [0.0]; base_evaluations=7)
    @test result.status == :not_eligible
    @test result.endpoint == (0.0,)
    @test result.evaluations == 7
    @test result.proofs == 0
end

@testset "solver-lab public guard API and reported callbacks" begin
    function run_variant(shadow, row_scale)
        calls = Ref(0)
        evaluator = input -> begin
            calls[] += 1
            guard = input[1] + 1.0e-8
            SolverCaseEvaluation(
                (row_scale * input[1],),
                0.0,
                guard > 0,
                true,
                (SolverPublicGuardObservation(9, guard * 1.0e6, 1.0e6, true),),
                UInt64(12),
            )
        end
        case = SolverExperimentCase(
            1, 1, (-1.0,), (1.0,), (1.0,), (row_scale,), 1, true, evaluator,
        )
        outcome = endpoint_correction_variant(; shadow).run(case, [4.0e-13])
        return outcome, calls[]
    end
    candidate, candidate_calls = run_variant(false, 1.0)
    shadow, shadow_calls = run_variant(true, 1.0)
    scaled, scaled_calls = run_variant(false, 1.0e9)
    @test candidate.status == "LOCAL_HEURISTIC_GUARD_INTERIOR"
    @test candidate.evaluations == candidate_calls
    @test shadow.evaluations == shadow_calls == candidate_calls
    @test scaled.evaluations == scaled_calls
    @test collect(candidate.endpoint) ≈ collect(scaled.endpoint) atol=1.0e-15 rtol=0
    @test occursin("heuristic-not-validated", candidate.diagnostic)
    @test !candidate.reported_converged
end

@testset "source is experiment-local and truth blind" begin
    source = read(joinpath(@__DIR__, "..", "src", "ExperimentLocal012.jl"), String)
    preregistration = read(joinpath(@__DIR__, "..", "preregistration.json"), String)
    @test !occursin("family_id", source)
    @test !occursin("instance_id", source)
    @test !occursin("gold_", lowercase(source))
    @test occursin("public_guards", source)
    @test occursin("branch_token", source)
    @test occursin("result_level=heuristic-not-validated", source)
    @test occursin("\"outcome_execution_authorized\": true", preregistration)
    @test occursin("\"strict_guard_dropped_witnesses\": 42", preregistration)
    @test occursin("\"near_rank_unsafe_shadow_endpoints_rejected\": 8", preregistration)
end
