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

        if has_analytic_jacobian(problem)
            analytic = evaluate_jacobian(problem, root)
            finite_difference = central_difference_jacobian(problem, root)
            @test norm(analytic - finite_difference, Inf) <=
                2e-5 * max(1.0, norm(analytic, Inf))
        else
            @test problem.metadata[:declared_capabilities] == (:C0,)
        end
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
        generate(
            StrictGuardBoundaryParams(
                boundary_case=:near_boundary,
                guard_margin=1.0e-10,
                instance_seed=208,
                start_seed=1208,
            ),
        ),
        generate(
            OpaqueTranscendentalParams(
                root_count=5,
                loop_count=16,
                phase=0.1,
                mixing=0.2,
                instance_seed=209,
                start_seed=1209,
            ),
        ),
    ]
    foreach(test_all_gold, problems)
end

@testset "S4 strict guard boundary truth" begin
    problems = s4_seed_problems()
    @test length(problems) == 20
    @test Set(problem.metadata[:boundary_case] for problem in problems) ==
        Set((:well_separated, :near_boundary, :on_boundary))
    for problem in problems
        test_all_gold(problem)
        @test problem.strata == (:S4,)
        @test problem.metadata[:strict_guard] === true
        candidates = only(
            artifact.values for artifact in problem.artifacts if
            artifact.name === :candidate_configurations
        )
        margins = vec(
            only(
                artifact.values for artifact in problem.artifacts if
                artifact.name === :candidate_guard_margins
            ),
        )
        validity = Bool.(
            vec(
                only(
                    artifact.values for artifact in problem.artifacts if
                    artifact.name === :candidate_strict_validity
                ),
            ),
        )
        @test validity == (margins .> 0)
        @test margins ≈ [strict_guard_margin(problem, candidate) for candidate in eachcol(candidates)]
        @test validity == [strict_guard_valid(problem, candidate) for candidate in eachcol(candidates)]
        for candidate in eachcol(candidates)
            @test norm(evaluate_residual(problem, candidate), Inf) <= 2e-15
        end
        expected = sort([
            problem.target(candidate) for candidate in eachcol(candidates) if
            strict_guard_valid(problem, candidate)
        ])
        @test expected == sort(problem.metadata[:expected_target_values])
        @test expected == sort(numeric_target.(problem.gold_targets))
        if problem.parameters.boundary_case === :on_boundary
            @test margins[1] == 0
            @test !validity[1]
            @test expected == [2.0]
        elseif problem.parameters.boundary_case === :near_boundary
            @test 0 < margins[1] <= 1.0e-6
            @test validity[1]
            @test expected == [1.0, 2.0]
        else
            @test margins[1] >= 0.25
            @test all(validity)
        end
    end
end

@testset "S6 C0-only opaque transcendental truth" begin
    problems = s6_seed_problems()
    @test length(problems) == 20
    for problem in problems
        test_all_gold(problem)
        @test problem.strata == (:S6,)
        @test !has_analytic_jacobian(problem)
        @test problem.metadata[:declared_capabilities] == (:C0,)
        @test problem.metadata[:opaque_callback] === true
        @test problem.metadata[:capability_order] == (:C0, :C1, :C2, :C3V, :C3A)
        @test problem.metadata[:plugin_high_precision_available] === false
        @test problem.metadata[:plugin_validated_available] === false
        @test problem.metadata[:plugin_algebraic_available] === false
        capability = vec(
            only(
                artifact.values for artifact in problem.artifacts if
                artifact.name === :capability_contract
            ),
        )
        @test capability == [1.0, 0.0, 0.0, 0.0, 0.0]
        @test all(target -> target isa ValidatedGoldTarget, problem.gold_targets)
        @test length(problem.gold_targets) == problem.parameters.root_count
        @test all(
            target_interval(target)[1] <= expected <= target_interval(target)[2] for
            (target, expected) in zip(
                problem.gold_targets,
                problem.metadata[:expected_target_values],
            )
        )
        root = problem.gold_configurations[:, 1]
        @test_throws MethodError problem.residual!(zeros(BigFloat, 2), BigFloat.(root))
    end
end

@testset "S4/S6 fixed-seed replay checksums" begin
    first = vcat(s4_seed_problems(), s6_seed_problems())
    second = vcat(s4_seed_problems(), s6_seed_problems())
    @test length(first) == 40
    @test replay_checksum.(first) == replay_checksum.(second)
    @test [problem.saved_starts for problem in first] ==
        [problem.saved_starts for problem in second]
    @test all(verify_replay_material, first)
    @test all(
        artifact.sha256 == artifact_checksum(artifact.name, artifact.values) for
        problem in first for artifact in problem.artifacts
    )
    @test length(unique(replay_checksum.(first))) == 40
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
    @test_throws ArgumentError StrictGuardBoundaryParams(
        boundary_case=:on_boundary,
        guard_margin=eps(),
    )
    @test_throws ArgumentError StrictGuardBoundaryParams(
        boundary_case=:near_boundary,
        guard_margin=0,
    )
    @test_throws ArgumentError OpaqueTranscendentalParams(root_count=1)
    @test_throws ArgumentError OpaqueTranscendentalParams(mixing=0)
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
    @test occursin(
        "\"covered_strata\":[\"S1\",\"S2\",\"S3\",\"S4\",\"S5\",\"S6\",\"S7\",\"S8\"]",
        generated,
    )
    @test occursin("\"not_claimed_strata\":[]", generated)
    @test length(m0_seed_problems()) == 47
    @test length(findall("\"family_id\":\"STRICT-GUARD-BOUNDARY\"", generated)) == 20
    @test length(findall("\"family_id\":\"OPAQUE-TRANSCENDENTAL-C0\"", generated)) == 20
    @test occursin("\"case_id\":\"M0-ANALYTIC-047\"", generated)
end

function solver_lab_collision_problem()
    residual!(output, input) = (output[1] = (input[1]^2 - 1) * (input[1]^2 - 4); output)
    jacobian!(output, input) = (output[1, 1] = 4input[1]^3 - 10input[1]; output)
    target(input) = input[1]^2
    configurations = reshape([-2.0, -1.0, 1.0, 2.0], 1, :)
    targets = AbstractGoldTargetDescriptor[
        ExactGoldTarget("squared-four", 4.0, "x^2 = 4", [1, 4]),
        ExactGoldTarget("squared-one", 1.0, "x^2 = 1", [2, 3]),
    ]
    starts = reshape([-2.0, -2.0, -1.0, 1.0], 1, :)
    return DirectAnalyticProblem(
        "solver-lab-collision",
        "SOLVER-LAB-COLLISION",
        (:S5,),
        (start_count=4,),
        1,
        1,
        residual!,
        jacobian!,
        target,
        [-3.0],
        [3.0],
        [3.0],
        [1.0],
        configurations,
        targets,
        starts,
        [MaterializedArtifact(:parameters, reshape([4.0], 1, 1))],
        Dict{Symbol,Any}(:generator_role => :solver_lab_test),
    )
end

function solver_lab_target_only_problem()
    residual!(output, input) = (output[1] = 1.0e-10 * (input[1] - 1); output)
    jacobian!(output, _) = (output[1, 1] = 1.0e-10; output)
    target(_) = 7.0
    return DirectAnalyticProblem(
        "solver-lab-target-only",
        "SOLVER-LAB-TARGET-ONLY",
        (:S5,),
        (start_count=1,),
        1,
        1,
        residual!,
        jacobian!,
        target,
        [-2.0],
        [2.0],
        [2.0],
        [1.0],
        reshape([1.0], 1, :),
        AbstractGoldTargetDescriptor[
            ExactGoldTarget("seven", 7.0, "target = 7", [1]),
        ],
        reshape([0.0], 1, :),
        [MaterializedArtifact(:parameters, reshape([1.0], 1, 1))],
        Dict{Symbol,Any}(:generator_role => :solver_lab_target_only_test),
    )
end

@testset "truth-blind solver experiment runner" begin
    problem = solver_lab_collision_problem()
    saw_truth_blind_case = Ref(false)
    identity = SolverVariant("identity") do case, start
        @test !hasproperty(case, :gold_targets)
        @test !hasproperty(case, :gold_configurations)
        @test !hasproperty(case, :family_id)
        @test !hasproperty(case, :instance_id)
        @test all(
            !(getfield(case._evaluate, index) isa DirectAnalyticProblem) for
            index in 1:fieldcount(typeof(case._evaluate))
        )
        evaluation = evaluate_case(case, start)
        @test evaluation.finite
        saw_truth_blind_case[] = true
        return SolverAttemptOutcome(
            start;
            status="identity",
            reported_converged=true,
            reported_accepted=true,
            evaluations=1,
            iterations=0,
        )
    end
    ticks = Ref(UInt64(0))
    clock_ns() = (ticks[] += UInt64(1_000_000))
    run = run_solver_experiment(
        [problem],
        [identity];
        prefixes=(1, 2, 4),
        clock_ns,
    )
    @test saw_truth_blind_case[]
    @test length(run.attempts) == 4
    @test all(attempt -> attempt.gold_matched, run.attempts)
    @test all(attempt -> attempt.evaluations == attempt.reported_evaluations == 1, run.attempts)
    @test all(attempt -> attempt.wall_seconds == 0.001, run.attempts)

    first_prefix, second_prefix, fourth_prefix = run.prefixes
    @test (first_prefix.targets_found, first_prefix.configurations_found) == (1, 1)
    @test !first_prefix.all_targets
    @test second_prefix.duplicate_configuration_hits == 1
    @test second_prefix.duplicate_target_hits == 1
    @test fourth_prefix.targets_found == fourth_prefix.target_count == 2
    @test fourth_prefix.configurations_found == 3
    @test fourth_prefix.all_targets
    @test fourth_prefix.duplicate_configuration_hits == 1
    @test fourth_prefix.duplicate_target_hits == 2
    @test fourth_prefix.evaluations == 4

    document = solver_experiment_document(run)
    @test document["schema"] == SOLVER_EXPERIMENT_SCHEMA_VERSION
    @test document["variants"] == ["identity"]
    @test length(document["attempts"]) == 4
    @test document["summaries"][end]["target_recall"] == 1.0
end


@testset "target-only numeric coincidence is not all-target recall" begin
    problem = solver_lab_target_only_problem()
    variant = SolverVariant("target-only") do case, start
        evaluate_case(case, start)
        evaluate_case(case, start)
        SolverAttemptOutcome(
            start;
            status="misreported-count",
            reported_converged=true,
            reported_accepted=true,
            evaluations=0,
        )
    end
    run = run_solver_experiment([problem], [variant]; prefixes=(1,))
    attempt = only(run.attempts)
    @test attempt.canonical_valid
    @test !attempt.configuration_matched
    @test attempt.numeric_target_matched
    @test !attempt.gold_matched
    @test attempt.false_candidate
    @test !attempt.false_target
    @test attempt.evaluations == 2
    @test attempt.reported_evaluations == 0

    summary = only(run.prefixes)
    @test summary.configuration_recall == 0.0
    @test summary.target_recall == 0.0
    @test !summary.all_targets
    @test summary.numeric_target_only_hits == 1
end

@testset "solver experiment failures and contracts are explicit" begin
    problem = solver_lab_collision_problem()
    failing = SolverVariant("failing") do _, _
        error("intentional variant failure")
    end
    run = run_solver_experiment([problem], [failing]; prefixes=(1,))
    attempt = only(run.attempts)
    @test attempt.exception == "intentional variant failure"
    @test !attempt.canonical_valid
    @test !attempt.false_candidate
    @test only(run.prefixes).exceptions == 1

    over_budget = SolverVariant("over-budget") do case, start
        for _ in 1:3
            case._evaluate(start)
        end
        SolverAttemptOutcome(start; status="unreachable", evaluations=0)
    end
    budget_run = run_solver_experiment(
        [problem],
        [over_budget];
        prefixes=(1,),
        evaluation_limit=2,
    )
    budget_attempt = only(budget_run.attempts)
    @test budget_attempt.budget_exhausted
    @test budget_attempt.evaluations == 2
    @test budget_attempt.reported_evaluations == 0
    @test occursin("evaluation budget 2 exhausted", budget_attempt.exception)
    @test only(budget_run.prefixes).budget_exhausted == 1
    @test solver_experiment_document(budget_run)["evaluation_limit"] == 2

    @test_throws ArgumentError run_solver_experiment([problem], [failing]; prefixes=(2, 1))
    @test_throws ArgumentError run_solver_experiment(
        [problem],
        [failing];
        prefixes=(1,),
        evaluation_limit=0,
    )
    @test_throws ArgumentError run_solver_experiment(
        [problem],
        [failing, SolverVariant("failing", (_, _) -> nothing)];
        prefixes=(1,),
    )
    @test_throws ArgumentError SolverExperimentTolerances(residual=-1)
end
