using ExperimentDisc001
using GeoTargetBenchmarks
using GeoTargetCore
using JSON3
using SHA
using Test

include(joinpath(@__DIR__, "..", "src", "stagec_t0_inputs.jl"))
using .StageCT0Inputs

@testset "Stage-C T0 corpus and fresh seed contract" begin
    problems = stagec_t0_problems()
    @test length(problems) == STAGEC_T0_CASE_COUNT == 12
    @test STAGEC_T0_SOURCE_INDICES ==
          (11, 12, 17, 18, 29, 30, 33, 35, 40, 41, 46, 47)
    @test [problem.family_id for problem in problems] == [
        "CURVED-CHAIN", "CURVED-CHAIN",
        "NEAR-RANK-DEFICIENT", "NEAR-RANK-DEFICIENT",
        "TANGENT-CIRCLE-LINE", "TANGENT-CIRCLE-LINE",
        "MULTIROOT-WARPED", "MULTIROOT-WARPED",
        "STRICT-GUARD-BOUNDARY", "STRICT-GUARD-BOUNDARY",
        "OPAQUE-TRANSCENDENTAL-C0", "OPAQUE-TRANSCENDENTAL-C0",
    ]
    @test all(verify_replay_material, problems)
    @test sum(size(problem.gold_configurations, 2) for problem in problems) == 42
    @test sum(length(problem.gold_targets) for problem in problems) == 34

    phrase = "EXP-DISC-001/STAGE-C/SOFT-TGO-T0/preoutcome-v1"
    digest = sha256(codeunits(phrase))
    @test bytes2hex(digest) ==
          "e27bbfda4d0c806506ccfea96c5e538947e61a5e94a1e9d61a4360f1960dd6bc"
    root = foldl((value, byte) -> (value << 8) | UInt64(byte), digest[1:8];
        init=zero(UInt64))
    @test root == STAGEC_T0_ROOT_SEED == UInt64(16_319_848_619_023_564_901)
    seeds = [derive_seed(
        STAGEC_T0_ROOT_SEED, STAGEC_T0_METHOD, case_index, 1,
        STAGEC_T0_SEED_NAMESPACE,
    ) for case_index in 1:12]
    @test length(unique(seeds)) == 12
    @test (first(seeds), last(seeds)) ==
          (0x39250f9d8b55ed21, 0xf0d0b9fe020b061d)
    @test STAGEC_T0_BATCH_SIZE * STAGEC_T0_BATCH_COUNT == 128
    @test STAGEC_T0_DERIVED_CONTROL == "FIFO_UNSCORED"
    @test STAGEC_T0_NORMALIZATION_ULP_MULTIPLIER == 8
    @test occursin("complete batch uses FIFO", STAGEC_T0_NORMALIZATION_GATE)
    @test occursin("both replica boxes pass", STAGEC_T0_COVARIANCE_CLAIM_BOUNDARY)
    @test ExperimentDisc001._file_sha256(joinpath(
        ExperimentDisc001.REPOSITORY_ROOT,
        "research", "experiments", "EXP-DISC-001", "src", "soft_tgo_ordering.jl",
    )) == StageCT0Inputs.STAGEC_T0_ORDERER_SOURCE_SHA
    @test ExperimentDisc001._file_sha256(joinpath(
        ExperimentDisc001.REPOSITORY_ROOT,
        "research", "experiments", "EXP-DISC-001", "test",
        "stagec_soft_tgo_ordering.jl",
    )) == StageCT0Inputs.STAGEC_T0_ORDERER_TEST_SHA
end

@testset "Stage-C T0 preflight and D0 materialization are bounded" begin
    authority = materialization_preflight()
    registration = JSON3.read(
        read(DEFAULT_STAGEC_T0_PREREGISTRATION_PATH, String),
        Dict{String,Any},
    )
    mktempdir() do directory
        for field in ("path", "sha256")
            tampered = deepcopy(registration)
            tampered["upstream_bindings"]["stagea_decision"][field] =
                field == "path" ? "wrong-stagea-decision.json" : repeat("0", 64)
            path = joinpath(directory, "tampered-$field.json")
            write(path, GeoTargetCore.canonical_json(tampered), '\n')
            @test_throws ErrorException StageCT0Inputs._validate_registration(path, authority)
        end
    end
    mktempdir() do directory
        proposal_root = joinpath(directory, "formal-proposals")
        input_path = joinpath(directory, "formal-input.json")
        preflight = stagec_t0_materialization_preflight(
            ; proposal_root, input_manifest_path=input_path,
        )
        @test length(preflight.problems) == 12
        @test length(preflight.destinations) == 12
        @test !ispath(proposal_root)
        @test !ispath(input_path)

        problem = first(preflight.problems)
        domain = StageCT0Inputs._stagec_t0_domain(problem)
        seed = derive_seed(
            STAGEC_T0_ROOT_SEED, STAGEC_T0_METHOD, 1, 1,
            STAGEC_T0_SEED_NAMESPACE,
        )
        path = joinpath(directory, "d0.json")
        artifact = materialize_stream_once(
            authority, STAGEC_T0_METHOD, domain, path; replicate_seed=seed,
        )
        @test size(artifact.coordinates) == (problem.dimension, 128)
        @test all(==(:iid), artifact.lane_schedule)
        @test StageCT0Inputs._truth_free(artifact)
        metadata = lowercase(artifact.metadata_json)
        @test all(!occursin(field, metadata) for field in
            ("family_id", "instance_id", "formal_case_id", "gold_targets"))
        @test_throws DiscoveryGateError materialize_stream_once(
            authority, STAGEC_T0_METHOD, domain, path; replicate_seed=seed,
        )
    end
end
