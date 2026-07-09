using GeoTargetBenchmarks
using LinearAlgebra
using Test

include(joinpath(@__DIR__, "..", "scripts", "render_m0_seed_manifest.jl"))

function evaluate_residual(problem, input)
    output = zeros(problem.residual_dimension)
    problem.residual!(output, input)
    return output
end

function evaluate_jacobian(problem, input)
    @assert has_analytic_jacobian(problem)
    output = zeros(problem.residual_dimension, problem.dimension)
    problem.jacobian!(output, input)
    return output
end

function central_difference_jacobian(problem, input)
    jacobian = zeros(problem.residual_dimension, problem.dimension)
    plus = copy(input)
    minus = copy(input)
    for column in 1:problem.dimension
        step = cbrt(eps(Float64)) * max(1.0, abs(input[column]))
        plus[column] = input[column] + step
        minus[column] = input[column] - step
        jacobian[:, column] .=
            (evaluate_residual(problem, plus) - evaluate_residual(problem, minus)) /
            (2 * step)
        plus[column] = input[column]
        minus[column] = input[column]
    end
    return jacobian
end

function test_all_gold(problem)
    @test has_analytic_jacobian(problem)
    @test verify_replay_material(problem)
    @test size(saved_starts(problem)) == (problem.dimension, problem.parameters.start_count)
    @test all(problem.lower_bounds .<= problem.saved_starts .<= problem.upper_bounds)

    represented = Int[]
    for target in problem.gold_targets
        append!(represented, configuration_indices(target))
        lower, upper = target_interval(target)
        @test lower <= numeric_target(target) <= upper
        for configuration in configuration_indices(target)
            input = problem.gold_configurations[:, configuration]
            value = problem.target(input)
            if target isa ExactGoldTarget
                @test isapprox(value, target.value; rtol=2e-14, atol=2e-15)
            else
                @test target.lower <= value <= target.upper
            end
        end
    end
    @test sort(represented) == collect(1:size(problem.gold_configurations, 2))
    @test length(unique(numeric_target.(problem.gold_targets))) == length(problem.gold_targets)

    for root in eachcol(problem.gold_configurations)
        residual = evaluate_residual(problem, root)
        normalized = residual ./ problem.residual_scales
        @test norm(normalized, Inf) <= 2e-11

        analytic = evaluate_jacobian(problem, root)
        finite_difference = central_difference_jacobian(problem, root)
        @test norm(analytic - finite_difference, Inf) <=
            2e-5 * max(1.0, norm(analytic, Inf))
    end
end

@testset "all analytic Gold roots and Jacobians" begin
    problems = DirectAnalyticProblem[
        generate(
            ScaleLadderParams(
                dimension=4,
                residual_scale_spread=1.0e12,
                instance_seed=201,
                start_seed=1201,
            ),
        ),
        generate(
            CurvedChainParams(
                dimension=8,
                curvature=1.0e4,
                instance_seed=202,
                start_seed=1202,
            ),
        ),
        generate(
            NearRankDeficientParams(
                dimension=8,
                singular_value_ratio=1.0e-12,
                orientation_seed=203,
                start_seed=1203,
            ),
        ),
        generate(
            RedundantOverdeterminedParams(
                dimension=4,
                redundancy=4,
                dependency_error=1.0e-8,
                dependency_seed=204,
                start_seed=1204,
            ),
        ),
        generate(
            TangentCircleLineParams(
                height_radius_ratio=0.99999999,
                instance_seed=205,
                start_seed=1205,
            ),
        ),
        generate(
            MultiRootWarpedParams(
                dimension=8,
                root_count=8,
                minimum_separation=1.0e-3,
                warp=0.9,
                condition=1.0e8,
                target_map=:z1,
                coefficient_seed=206,
                start_seed=1206,
            ),
        ),
        generate(
            MultiRootWarpedParams(
                dimension=4,
                root_count=8,
                minimum_separation=1.0e-6,
                warp=0.5,
                condition=1.0e4,
                target_map=:close_affine,
                coefficient_seed=207,
                start_seed=1207,
            ),
        ),
    ]
    foreach(test_all_gold, problems)
end

@testset "distinct target values versus duplicate configurations" begin
    common = (
        dimension=4,
        root_count=4,
        minimum_separation=0.1,
        warp=0.5,
        condition=100.0,
        coefficient_seed=301,
        start_seed=1301,
    )
    distinct = generate(MultiRootWarpedParams(; common..., target_map=:z1))
    collision = generate(MultiRootWarpedParams(; common..., target_map=:z1_squared))
    @test length(distinct.gold_targets) == 4
    @test all(length(configuration_indices(target)) == 1 for target in distinct.gold_targets)
    @test length(collision.gold_targets) == 2
    @test all(length(configuration_indices(target)) == 2 for target in collision.gold_targets)
    @test :S5 in collision.strata
    @test !(:S5 in distinct.strata)
    test_all_gold(distinct)
    test_all_gold(collision)
end

@testset "factor controls and metadata" begin
    for dimension in (2, 4, 8, 16)
        problem = generate(
            ScaleLadderParams(
                dimension=dimension,
                residual_scale_spread=1.0e6,
                start_count=2,
            ),
        )
        @test problem.dimension == dimension
        @test last(problem.residual_scales) / first(problem.residual_scales) ≈ 1.0e6
    end

    near = generate(
        NearRankDeficientParams(
            dimension=8,
            singular_value_ratio=1.0e-8,
            orientation_seed=401,
            start_seed=1401,
        ),
    )
    @test near.metadata[:requested_condition] == 1.0e8
    @test isapprox(near.metadata[:observed_jacobian_condition], 1.0e8; rtol=2e-8)
    left = only(filter(entry -> entry.name === :left_orthogonal, near.artifacts)).values
    right = only(filter(entry -> entry.name === :right_orthogonal, near.artifacts)).values
    @test left' * left ≈ I atol=2e-14
    @test right' * right ≈ I atol=2e-14

    redundant = generate(
        RedundantOverdeterminedParams(
            dimension=4,
            redundancy=4,
            dependency_error=1.0e-4,
        ),
    )
    @test redundant.residual_dimension == 20
    @test redundant.metadata[:dependency_error] == 1.0e-4

    regular = generate(TangentCircleLineParams(height_radius_ratio=0.0))
    tangent = generate(TangentCircleLineParams(height_radius_ratio=0.99999999))
    @test tangent.metadata[:root_separation] < regular.metadata[:root_separation]
    @test maximum(tangent.metadata[:observed_root_conditions]) >
        maximum(regular.metadata[:observed_root_conditions])

    close_roots = generate(
        MultiRootWarpedParams(
            root_count=8,
            minimum_separation=1.0e-6,
            condition=1.0e8,
        ),
    )
    @test isapprox(
        close_roots.metadata[:observed_minimum_latent_separation],
        1.0e-6;
        rtol=1e-12,
    )
    @test close_roots.metadata[:requested_condition] == 1.0e8
end

@testset "materialized deterministic replay" begin
    parameters = NearRankDeficientParams(
        dimension=8,
        singular_value_ratio=1.0e-8,
        orientation_seed=501,
        start_seed=1501,
    )
    first_problem = generate(parameters)
    second_problem = generate(parameters)
    @test replay_checksum(first_problem) == replay_checksum(second_problem)
    @test first_problem.saved_starts == second_problem.saved_starts
    @test [entry.sha256 for entry in first_problem.artifacts] ==
        [entry.sha256 for entry in second_problem.artifacts]

    changed_orientation = generate(
        NearRankDeficientParams(
            dimension=8,
            singular_value_ratio=1.0e-8,
            orientation_seed=502,
            start_seed=1501,
        ),
    )
    @test replay_checksum(first_problem) != replay_checksum(changed_orientation)
    @test first_problem.saved_starts == changed_orientation.saved_starts

    starts_artifact = only(
        filter(entry -> entry.name === :saved_starts, first_problem.artifacts),
    )
    @test starts_artifact.values == first_problem.saved_starts
    starts_artifact.values[1, 1] = nextfloat(starts_artifact.values[1, 1])
    @test !verify_replay_material(first_problem)
end

@testset "Gold truth is not a production routing input" begin
    common = (
        dimension=4,
        root_count=4,
        minimum_separation=0.1,
        warp=0.5,
        condition=100.0,
        coefficient_seed=601,
        start_seed=1601,
    )
    distinct = generate(MultiRootWarpedParams(; common..., target_map=:z1))
    collision = generate(MultiRootWarpedParams(; common..., target_map=:z1_squared))
    @test distinct.saved_starts == collision.saved_starts
    @test distinct.gold_configurations == collision.gold_configurations
    @test length(distinct.gold_targets) != length(collision.gold_targets)

    public_api = Set(names(GeoTargetBenchmarks; all=false, imported=false))
    @test isempty(intersect(public_api, Set((:solve, :route, :routing_hint, :preferred_solver))))
    fields = Set(fieldnames(typeof(distinct)))
    @test isempty(intersect(fields, Set((:routing_hint, :preferred_solver, :known_start))))

    project = read(joinpath(pkgdir(GeoTargetBenchmarks), "Project.toml"), String)
    @test !occursin("GeoTargetCore", project)
    @test !occursin("GeoTargetGeometry", project)
end

@testset "invalid factor combinations fail closed" begin
    @test_throws ArgumentError ScaleLadderParams(dimension=1)
    @test_throws ArgumentError NearRankDeficientParams(singular_value_ratio=0)
    @test_throws ArgumentError TangentCircleLineParams(height_radius_ratio=1)
    @test_throws ArgumentError MultiRootWarpedParams(root_count=13)
    @test_throws ArgumentError MultiRootWarpedParams(target_map=:unknown)
    @test_throws ArgumentError RedundantOverdeterminedParams(dependency_error=-1)
end

@testset "generated M0 seed manifest is replayable and scoped" begin
    repository_root = dirname(dirname(pkgdir(GeoTargetBenchmarks)))
    manifest_path = joinpath(
        repository_root,
        "benchmarks",
        "generated",
        "m0-analytic-seed-manifest.json",
    )
    generated = render_m0_seed_manifest()
    @test read(manifest_path, String) == generated
    @test occursin("\"not_claimed_strata\":[\"S4\",\"S6\"]", generated)
    @test !occursin(
        "\"covered_strata\":[\"S1\",\"S2\",\"S3\",\"S4\",\"S5\",\"S6\",\"S7\",\"S8\"]",
        generated,
    )
    @test length(m0_seed_problems()) == 7
end
