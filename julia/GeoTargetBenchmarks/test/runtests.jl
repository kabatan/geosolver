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

@testset "platform-sensitive diagnostics do not enter replay artifacts" begin
    for problem in (
        generate(TangentCircleLineParams()),
        generate(MultiRootWarpedParams()),
    )
        @test haskey(problem.metadata, :observed_root_conditions)
        @test all(artifact -> artifact.name !== :root_conditions, problem.artifacts)
        @test verify_replay_material(problem)
    end
end

function solver_lab_collision_problem(; starts=[-2.0, -2.0, -1.0, 1.0])
    residual!(output, input) = (output[1] = (input[1]^2 - 1) * (input[1]^2 - 4); output)
    jacobian!(output, input) = (output[1, 1] = 4input[1]^3 - 10input[1]; output)
    target(input) = input[1]^2
    configurations = reshape([-2.0, -1.0, 1.0, 2.0], 1, :)
    targets = AbstractGoldTargetDescriptor[
        ExactGoldTarget("squared-four", 4.0, "x^2 = 4", [1, 4]),
        ExactGoldTarget("squared-one", 1.0, "x^2 = 1", [2, 3]),
    ]
    saved = reshape(Float64[starts...], 1, :)
    return DirectAnalyticProblem(
        "solver-lab-collision",
        "SOLVER-LAB-COLLISION",
        (:S5,),
        (start_count=length(starts),),
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
        saved,
        [MaterializedArtifact(:parameters, reshape([4.0], 1, 1))],
        Dict{Symbol,Any}(:generator_role => :solver_lab_test),
    )
end

function solver_lab_false_endpoint_problem(; starts=[-1.0])
    residual!(output, input) = (output[1] = input[1]^2 - 1; output)
    jacobian!(output, input) = (output[1, 1] = 2input[1]; output)
    target(input) = input[1]
    return DirectAnalyticProblem(
        "solver-lab-false-endpoint",
        "SOLVER-LAB-FALSE-ENDPOINT",
        (:S5,),
        (start_count=length(starts),),
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
            ExactGoldTarget("positive-one", 1.0, "target = 1", [1]),
        ],
        reshape(Float64[starts...], 1, :),
        [MaterializedArtifact(:parameters, reshape([1.0], 1, 1))],
        Dict{Symbol,Any}(:generator_role => :solver_lab_false_endpoint_test),
    )
end

function solver_lab_inconsistent_target_problem()
    residual!(output, input) = (output[1] = input[1]^2 - 1; output)
    jacobian!(output, input) = (output[1, 1] = 2input[1]; output)
    target(_) = 7.0
    return DirectAnalyticProblem(
        "solver-lab-inconsistent-target",
        "SOLVER-LAB-INCONSISTENT-TARGET",
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
        reshape([-1.0, 1.0], 1, :),
        AbstractGoldTargetDescriptor[
            ExactGoldTarget("seven", 7.0, "target = 7", [1]),
            ExactGoldTarget("eight", 8.0, "target = 8", [2]),
        ],
        reshape([1.0], 1, :),
        [MaterializedArtifact(:parameters, reshape([2.0], 1, 1))],
        Dict{Symbol,Any}(:generator_role => :solver_lab_inconsistent_target_test),
    )
end

function solver_lab_ambiguous_target_problem()
    residual!(output, input) = (output[1] = input[1]^2 - 1; output)
    jacobian!(output, input) = (output[1, 1] = 2input[1]; output)
    target(_) = 0.0
    return DirectAnalyticProblem(
        "solver-lab-ambiguous-target",
        "SOLVER-LAB-AMBIGUOUS-TARGET",
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
        reshape([-1.0, 1.0], 1, :),
        AbstractGoldTargetDescriptor[
            ValidatedGoldTarget("left", -0.5, 0.5, "fixture interval", [1]),
            ValidatedGoldTarget("right", -0.25, 0.25, "fixture interval", [2]),
        ],
        reshape([-1.0], 1, :),
        [MaterializedArtifact(:parameters, reshape([2.0], 1, 1))],
        Dict{Symbol,Any}(:generator_role => :solver_lab_ambiguous_target_test),
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
    # Target coverage first becomes safe at start 3 even though 3 is not a
    # requested reporting prefix.  Work-to-success must not depend on prefix
    # coarseness.
    @test fourth_prefix.reported_accepted_targets_found == 2
    @test fourth_prefix.reported_accepted_target_recall == 1.0
    @test fourth_prefix.lab_safe_all_targets
    @test fourth_prefix.assessor_all_targets
    @test fourth_prefix.assessor_safe_all_targets
    @test fourth_prefix.suffix_stable_evaluations_to_lab_safe_full == 3
    @test fourth_prefix.evaluation_count_mismatches == 0

    document = solver_experiment_document(run)
    @test document["schema"] == SOLVER_EXPERIMENT_SCHEMA_VERSION
    @test document["schema"] == "geotarget.solver-experiment/v2"
    @test document["variants"] == ["identity"]
    @test length(document["attempts"]) == 4
    @test document["summaries"][end]["target_recall"] == 1.0
    @test document["assessor_manifest"] == Dict{String,Any}(
        "configuration_tolerance" => 1.0e-6,
        "qualification_predicate" =>
            "endpoint_present_finite_in_bounds_semantics_valid_scaled_residual_linf",
        "coverage_predicate" => "qualified_unique_gold_consistent_target_id",
        "residual_linf_tolerance" => 1.0e-12,
        "safety_predicate" =>
            "all_qualified_endpoints_gold_consistent_and_unambiguous",
        "target_tolerance" => 1.0e-6,
    )
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
    @test attempt.evaluation_count_mismatch
    @test attempt.evaluation_count_difference == 2
    @test !attempt.assessor_qualified

    summary = only(run.prefixes)
    @test summary.configuration_recall == 0.0
    @test summary.target_recall == 0.0
    @test !summary.all_targets
    @test summary.numeric_target_only_hits == 1
    @test summary.reported_accepted_numeric_target_only == 1
    @test summary.reported_accepted_gold_inconsistent == 1
    @test !summary.lab_safe_all_targets
    @test summary.assessor_qualified == 0
    @test summary.assessor_qualified_target_recall == 0.0
    @test summary.evaluation_count_mismatches == 1
    @test solver_experiment_document(run)["attempts"][1]["evaluation_count_difference"] == 2
end

@testset "solver experiment v2 accepted and assessor fixtures" begin
    # 1. A rejected Gold endpoint remains in the legacy endpoint diagnostic,
    # but never enters solver-reported accepted recall.  The frozen assessor is
    # deliberately independent of that self-report.
    collision = solver_lab_collision_problem()
    rejected_gold = SolverVariant("rejected-gold") do _, start
        SolverAttemptOutcome(
            start;
            status="rejected",
            reported_converged=true,
            reported_accepted=false,
        )
    end
    rejected_gold_run = run_solver_experiment(
        [collision],
        [rejected_gold];
        prefixes=(1,),
    )
    rejected_gold_summary = only(rejected_gold_run.prefixes)
    @test rejected_gold_summary.targets_found == 1
    @test rejected_gold_summary.reported_accepted_targets_found == 0
    @test rejected_gold_summary.reported_accepted_target_recall == 0.0
    @test rejected_gold_summary.assessor_qualified_targets_found == 1
    @test rejected_gold_summary.assessor_qualified_target_recall == 0.5

    # 2. An accepted canonical-invalid endpoint is an explicit safety failure.
    accepted_invalid = SolverVariant("accepted-invalid") do _, _
        SolverAttemptOutcome(
            [0.0];
            status="accepted-invalid",
            reported_accepted=true,
        )
    end
    invalid_run = run_solver_experiment(
        [collision],
        [accepted_invalid];
        prefixes=(1,),
    )
    invalid_summary = only(invalid_run.prefixes)
    @test invalid_summary.reported_accepted_canonical_invalid == 1
    @test invalid_summary.reported_accepted_gold_inconsistent == 1
    @test !invalid_summary.lab_safe_all_targets

    # 3. A residual-qualified endpoint outside the Gold configuration/target
    # relation is Gold-inconsistent when the solver reports it as accepted.
    false_problem = solver_lab_false_endpoint_problem()
    accepted_false = SolverVariant("accepted-false") do _, start
        SolverAttemptOutcome(
            start;
            status="accepted-false",
            reported_accepted=true,
        )
    end
    accepted_false_run = run_solver_experiment(
        [false_problem],
        [accepted_false];
        prefixes=(1,),
    )
    accepted_false_attempt = only(accepted_false_run.attempts)
    accepted_false_summary = only(accepted_false_run.prefixes)
    @test accepted_false_attempt.canonical_valid
    @test accepted_false_attempt.false_candidate
    @test accepted_false_attempt.false_target
    @test accepted_false_attempt.assessor_qualified
    @test accepted_false_summary.reported_accepted_gold_inconsistent == 1
    @test accepted_false_summary.assessor_qualified_gold_inconsistent == 1
    @test !accepted_false_summary.assessor_safe_all_targets

    # 4. A numeric target coincidence with the wrong configuration descriptor
    # gets its own counter and is never accepted as a consistent target witness.
    inconsistent_problem = solver_lab_inconsistent_target_problem()
    accepted_numeric_only = SolverVariant("accepted-numeric-only") do _, start
        SolverAttemptOutcome(
            start;
            status="accepted-numeric-only",
            reported_accepted=true,
        )
    end
    numeric_only_run = run_solver_experiment(
        [inconsistent_problem],
        [accepted_numeric_only];
        prefixes=(1,),
    )
    numeric_only_attempt = only(numeric_only_run.attempts)
    numeric_only_summary = only(numeric_only_run.prefixes)
    @test numeric_only_attempt.configuration_matched
    @test numeric_only_attempt.numeric_target_matched
    @test !numeric_only_attempt.gold_matched
    @test numeric_only_summary.reported_accepted_numeric_target_only == 1
    @test numeric_only_summary.reported_accepted_gold_inconsistent == 1
    @test numeric_only_summary.reported_accepted_targets_found == 0

    # 5. The same false endpoint is still a legacy diagnostic when rejected,
    # while every reported-accepted safety count remains zero.
    rejected_false = SolverVariant("rejected-false") do _, start
        SolverAttemptOutcome(
            start;
            status="rejected-false",
            reported_accepted=false,
        )
    end
    rejected_false_run = run_solver_experiment(
        [false_problem],
        [rejected_false];
        prefixes=(1,),
    )
    rejected_false_attempt = only(rejected_false_run.attempts)
    rejected_false_summary = only(rejected_false_run.prefixes)
    @test rejected_false_attempt.false_candidate
    @test rejected_false_attempt.false_target
    @test rejected_false_summary.reported_accepted_canonical_invalid == 0
    @test rejected_false_summary.reported_accepted_gold_inconsistent == 0
    @test rejected_false_summary.reported_accepted_numeric_target_only == 0
    @test rejected_false_summary.reported_accepted_ambiguous == 0

    assessor_mixed_problem = solver_lab_false_endpoint_problem(; starts=[1.0, -1.0])
    assessor_mixed_run = run_solver_experiment(
        [assessor_mixed_problem],
        [rejected_false];
        prefixes=(2,),
    )
    assessor_mixed_summary = only(assessor_mixed_run.prefixes)
    @test assessor_mixed_summary.assessor_all_targets
    @test assessor_mixed_summary.assessor_qualified_gold_inconsistent == 1
    @test !assessor_mixed_summary.assessor_safe_all_targets

    # 6. Complete accepted coverage is not safe-full when any later accepted
    # endpoint is inconsistent; the earlier success is not suffix-stable.
    unsafe_late = SolverVariant("unsafe-late") do _, start
        endpoint = start[1] == 1.0 ? [0.0] : start
        SolverAttemptOutcome(
            endpoint;
            status="unsafe-late",
            reported_accepted=true,
        )
    end
    unsafe_late_run = run_solver_experiment(
        [collision],
        [unsafe_late];
        prefixes=(3, 4),
    )
    safe_prefix, unsafe_prefix = unsafe_late_run.prefixes
    @test safe_prefix.lab_safe_all_targets
    @test safe_prefix.suffix_stable_evaluations_to_lab_safe_full === nothing
    @test unsafe_prefix.reported_accepted_targets_found == 2
    @test unsafe_prefix.reported_accepted_canonical_invalid == 1
    @test !unsafe_prefix.lab_safe_all_targets
    @test unsafe_prefix.suffix_stable_evaluations_to_lab_safe_full === nothing

    # 7. Two different Gold configurations witnessing one collision target are
    # counted once in the accepted target set.
    target_collision = solver_lab_collision_problem(; starts=[-2.0, 2.0])
    accepted_collision = SolverVariant("accepted-collision") do _, start
        SolverAttemptOutcome(
            start;
            status="accepted-collision",
            reported_accepted=true,
        )
    end
    collision_run = run_solver_experiment(
        [target_collision],
        [accepted_collision];
        prefixes=(2,),
    )
    collision_summary = only(collision_run.prefixes)
    @test collision_summary.gold_matched == 2
    @test collision_summary.reported_accepted_targets_found == 1
    @test collision_summary.reported_accepted_target_recall == 0.5
    @test collision_summary.duplicate_target_hits == 1

    # Ambiguity is also exposed independently rather than being hidden in the
    # aggregate Gold-inconsistent count.
    ambiguous_problem = solver_lab_ambiguous_target_problem()
    accepted_ambiguous = SolverVariant("accepted-ambiguous") do _, start
        SolverAttemptOutcome(
            start;
            status="accepted-ambiguous",
            reported_accepted=true,
        )
    end
    ambiguous_run = run_solver_experiment(
        [ambiguous_problem],
        [accepted_ambiguous];
        prefixes=(1,),
    )
    ambiguous_attempt = only(ambiguous_run.attempts)
    ambiguous_summary = only(ambiguous_run.prefixes)
    @test ambiguous_attempt.target_ambiguous
    @test ambiguous_attempt.assessor_target_ambiguous
    @test ambiguous_summary.reported_accepted_ambiguous == 1
    @test ambiguous_summary.assessor_qualified_gold_inconsistent == 1
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
    @test budget_attempt.evaluation_count_mismatch
    @test budget_attempt.evaluation_count_difference == 2
    @test occursin("evaluation budget 2 exhausted", budget_attempt.exception)
    budget_summary = only(budget_run.prefixes)
    @test budget_summary.budget_exhausted == 1
    @test budget_summary.runner_budget_exhausted == 1
    @test budget_summary.local_max_evaluations == 0
    @test budget_summary.evaluation_count_mismatches == 1
    @test Dict(budget_summary.status_counts)["evaluation_budget_exhausted"] == 1
    @test solver_experiment_document(budget_run)["evaluation_limit"] == 2

    local_cap = SolverVariant("local-cap") do _, start
        SolverAttemptOutcome(
            start;
            status="LOCAL_MAX_EVALUATIONS",
            evaluations=0,
        )
    end
    local_cap_run = run_solver_experiment(
        [problem],
        [local_cap];
        prefixes=(1,),
    )
    local_cap_summary = only(local_cap_run.prefixes)
    @test local_cap_summary.local_max_evaluations == 1
    @test local_cap_summary.runner_budget_exhausted == 0
    @test Dict(local_cap_summary.status_counts)["LOCAL_MAX_EVALUATIONS"] == 1

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
