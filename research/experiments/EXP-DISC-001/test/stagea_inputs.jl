using ExperimentDisc001
using GeoTargetBenchmarks
using JSON3
using Test

include(joinpath(@__DIR__, "..", "src", "stagea_corpus.jl"))
using .StageAInputs

@testset "formal Stage-A corpus" begin
    problems = stagea_problems()
    @test length(problems) == 24
    @test [recipe.source_index for recipe in STAGEA_RECIPE] == collect(25:48)
    @test [recipe.formal_case_id for recipe in STAGEA_RECIPE] ==
          ["EXP-DISC-001-A-$(lpad(index, 3, '0'))" for index in 1:24]
    @test sum(length(problem.gold_targets) for problem in problems) == 64
    @test Set(problem.family_id for problem in problems) == Set((
        "TANGENT-CIRCLE-LINE",
        "MULTIROOT-WARPED",
        "STRICT-GUARD-BOUNDARY",
        "OPAQUE-TRANSCENDENTAL-C0",
    ))
    @test all(GeoTargetBenchmarks.verify_replay_material, problems)

    problem = problems[7]
    domain = stagea_proposal_domain(problem)
    @test domain.lower == Tuple(problem.lower_bounds)
    @test domain.upper == Tuple(problem.upper_bounds)
    midpoint = (problem.lower_bounds .+ problem.upper_bounds) ./ 2
    proposals = repeat(reshape(midpoint, :, 1), 1, MATRIX_COLUMN_COUNT)
    replacement = stagea_problem_with_proposals(problem, proposals)
    @test replacement.saved_starts == proposals
    @test GeoTargetBenchmarks.verify_replay_material(replacement)
end

@testset "formal Stage-A replicate and seed contract" begin
    counts = StageAInputs._stagea_method_counts()
    @test counts[ExperimentDisc001._METHOD_WIRE[D0_IID_ALL]] == 10
    @test counts[ExperimentDisc001._METHOD_WIRE[D1_SOBOL_ALL]] == 1
    @test counts[ExperimentDisc001._METHOD_WIRE[D_HALTON_ALL]] == 1
    @test counts[ExperimentDisc001._METHOD_WIRE[D_CURRENT_COUNTER_HALTON]] == 10
    @test counts[ExperimentDisc001._METHOD_WIRE[D2O_OWEN_ALL]] == 10
    @test counts[ExperimentDisc001._METHOD_WIRE[D2M_MATOUSEK_ALL]] == 10
    @test counts[ExperimentDisc001._METHOD_WIRE[D3_OWEN_MIXED]] == 10
    @test STAGEA_PROPOSAL_COUNT == 1_248
    @test derive_seed(
        STAGEA_ROOT_SEED,
        D0_IID_ALL,
        1,
        1,
        "stagea-proposal",
    ) != derive_seed(
        STAGEA_ROOT_SEED,
        D0_IID_ALL,
        1,
        2,
        "stagea-proposal",
    )
end

@testset "formal Stage-A preflight has no output side effects" begin
    mktempdir() do directory
        proposal_root = joinpath(directory, "proposals")
        manifest_path = joinpath(directory, "input.json")
        preflight = stagea_materialization_preflight(
            ; proposal_root, input_manifest_path=manifest_path,
        )
        @test length(preflight.problems) == 24
        @test length(preflight.destinations) == 1_248
        @test !ispath(proposal_root)
        @test !ispath(manifest_path)
    end
end

@testset "same-replicate mixed inputs are persisted and truth blind" begin
    authority = materialization_preflight()
    domain = stagea_proposal_domain(first(stagea_problems()))
    mktempdir() do directory
        paths = Dict(
            D0_IID_ALL => joinpath(directory, "iid.json"),
            D2O_OWEN_ALL => joinpath(directory, "owen.json"),
            D3_OWEN_MIXED => joinpath(directory, "mixed.json"),
        )
        artifacts = Dict{DiscoveryMethod,ProposalMatrixArtifact}()
        for method in (D0_IID_ALL, D2O_OWEN_ALL)
            artifacts[method] = materialize_stream_once(
                authority,
                method,
                domain,
                paths[method];
                replicate_seed=derive_seed(
                    STAGEA_ROOT_SEED,
                    method,
                    1,
                    3,
                    "stagea-proposal",
                ),
            )
        end
        artifacts[D3_OWEN_MIXED] = materialize_stream_once(
            authority,
            D3_OWEN_MIXED,
            domain,
            paths[D3_OWEN_MIXED];
            replicate_seed=derive_seed(
                STAGEA_ROOT_SEED,
                D3_OWEN_MIXED,
                1,
                3,
                "stagea-proposal",
            ),
            iid_source_path=paths[D0_IID_ALL],
            rqmc_source_path=paths[D2O_OWEN_ALL],
        )
        metadata = JSON3.read(
            artifacts[D3_OWEN_MIXED].metadata_json,
            Dict{String,Any},
        )
        @test metadata["iid_source_sha256"] == artifacts[D0_IID_ALL].sha256
        @test metadata["rqmc_source_sha256"] == artifacts[D2O_OWEN_ALL].sha256
        @test !haskey(metadata, "family_id")
        @test !haskey(metadata, "instance_id")
        @test !haskey(metadata, "gold_targets")
        @test iid_bounded_gap_audit(
            artifacts[D3_OWEN_MIXED].lane_schedule,
        ).bounded_gap
        @test_throws DiscoveryGateError materialize_stream_once(
            authority,
            D0_IID_ALL,
            domain,
            paths[D0_IID_ALL];
            replicate_seed=1,
        )
    end
end
