using ExperimentDisc001
using GeoTargetBenchmarks
using GeoTargetCore
using JSON3
using SHA
using Test

include(joinpath(@__DIR__, "..", "src", "stageb_t0_inputs.jl"))
using .StageBT0Inputs

const STAGEB_TEST_ROOT = normpath(joinpath(@__DIR__, ".."))
const STAGEB_TEST_REPOSITORY = normpath(joinpath(STAGEB_TEST_ROOT, "..", "..", ".."))

stageb_file_sha(path) = bytes2hex(sha256(read(path)))

function stageb_repository_path(relative)
    return joinpath(STAGEB_TEST_REPOSITORY, split(relative, '/')...)
end

function stageb_fixture_registration()
    freeze_sha = stageb_file_sha(ExperimentDisc001.DEFAULT_CHAMPION_FREEZE_PATH)
    bindings = Dict{String,Any}(
        name => Dict{String,Any}(
            "path" => relative,
            "sha256" => stageb_file_sha(stageb_repository_path(relative)),
        ) for (name, relative) in (
            "stagea_decision" =>
                "research/experiments/EXP-DISC-001/stagea-decision.json",
            "weak_geometry_source" =>
                "research/experiments/EXP-DISC-001/src/weak_geometry.jl",
            "weak_geometry_test" =>
                "research/experiments/EXP-DISC-001/test/stageb_weak_geometry.jl",
        )
    )
    return Dict{String,Any}(
        "case_count" => STAGEB_T0_CASE_COUNT,
        "case_sources" => Any[
            Dict{String,Any}(
                "formal_case_id" => recipe.formal_case_id,
                "index" => recipe.source_index,
                "path" => recipe.source,
            ) for recipe in STAGEB_T0_RECIPE
        ],
        "continuation_columns" => [
            first(STAGEB_T0_CONTINUATION),
            last(STAGEB_T0_CONTINUATION),
        ],
        "initial_prefix_columns" => [1, STAGEB_T0_INITIAL_PREFIX],
        "local_freeze_sha256" => freeze_sha,
        "materialization_authorized" => true,
        "method" => ExperimentDisc001._METHOD_WIRE[STAGEB_T0_METHOD],
        "nonpromotional_t0" => true,
        "outcome_execution_authorized" => false,
        "proposal_artifact_count" => STAGEB_T0_PROPOSAL_COUNT,
        "replicate_count" => STAGEB_T0_REPLICATE_COUNT,
        "root_seed" => string(STAGEB_T0_ROOT_SEED),
        "schema_version" => "geotarget.discovery-stageb-t0-preregistration/v1",
        "seed_namespace" => STAGEB_T0_SEED_NAMESPACE,
        "execution_contract" => deepcopy(STAGEB_T0_EXECUTION_CONTRACT),
        "source_sha256" => Dict(
            relative => stageb_file_sha(stageb_repository_path(relative)) for
            relative in STAGEB_T0_REQUIRED_SOURCE_PATHS
        ),
        "upstream_bindings" => bindings,
    )
end

@testset "Stage-B T0 corpus is manual, replayed, and balanced" begin
    problems = stageb_t0_problems()
    @test length(problems) == STAGEB_T0_CASE_COUNT == 8
    @test STAGEB_T0_SOURCE_INDICES == (11, 12, 17, 18, 29, 30, 33, 35)
    @test [recipe.formal_case_id for recipe in STAGEB_T0_RECIPE] ==
          ["EXP-DISC-001-B0-$(lpad(index, 3, '0'))" for index in 1:8]
    @test [problem.family_id for problem in problems] == [
        "CURVED-CHAIN",
        "CURVED-CHAIN",
        "NEAR-RANK-DEFICIENT",
        "NEAR-RANK-DEFICIENT",
        "TANGENT-CIRCLE-LINE",
        "TANGENT-CIRCLE-LINE",
        "MULTIROOT-WARPED",
        "MULTIROOT-WARPED",
    ]
    @test [problem.dimension for problem in problems] == [4, 8, 4, 8, 2, 2, 8, 4]
    @test all(GeoTargetBenchmarks.verify_replay_material, problems)
    @test sum(size(problem.gold_configurations, 2) for problem in problems) == 24
    @test sum(length(problem.gold_targets) for problem in problems) == 16
    @test StageBT0Inputs._parameter_document(problems[1].parameters) == Dict(
        "curvature" => 1.0e8,
        "dimension" => 4,
        "instance_seed" => 10_205,
        "start_count" => 32,
        "start_seed" => 20_205,
    )
    @test StageBT0Inputs._parameter_document(problems[8].parameters) == Dict(
        "coefficient_seed" => 10_605,
        "condition" => 1.0e4,
        "dimension" => 4,
        "minimum_separation" => 1.0e-6,
        "root_count" => 8,
        "start_count" => 32,
        "start_seed" => 20_605,
        "target_affine_scale" => 1.0e-6,
        "target_map" => "z1_squared",
        "warp" => 0.5,
    )

    midpoint = (problems[1].lower_bounds .+ problems[1].upper_bounds) ./ 2
    proposals = repeat(reshape(midpoint, :, 1), 1, MATRIX_COLUMN_COUNT)
    replacement = stageb_t0_problem_with_proposals(problems[1], proposals)
    @test replacement.saved_starts == proposals
    @test GeoTargetBenchmarks.verify_replay_material(replacement)
    @test GeoTargetBenchmarks.replay_checksum(replacement) !=
          GeoTargetBenchmarks.replay_checksum(problems[1])
end

@testset "Stage-B T0 root and per-case seed contract" begin
    phrase = "EXP-DISC-001/STAGE-B/T0/preoutcome-v1"
    digest = sha256(codeunits(phrase))
    @test bytes2hex(digest) ==
          "aa37c50e47f1d1ffb7d9327175b6a5572e0eaa27911159d4cd014ae3254618a0"
    root = zero(UInt64)
    for byte in digest[1:8]
        root = (root << 8) | UInt64(byte)
    end
    @test root == STAGEB_T0_ROOT_SEED == UInt64(12_265_488_775_294_079_487)
    seeds = [
        derive_seed(
            STAGEB_T0_ROOT_SEED,
            STAGEB_T0_METHOD,
            case_index,
            1,
            STAGEB_T0_SEED_NAMESPACE,
        ) for case_index in 1:STAGEB_T0_CASE_COUNT
    ]
    @test length(unique(seeds)) == STAGEB_T0_CASE_COUNT
    @test seeds[1] == 0x4b3ee94421fa366b
    @test seeds[end] == 0x222a762b092101b9
end

@testset "Stage-B T0 preflight is authorized and side-effect free" begin
    mktempdir() do directory
        registration_path = joinpath(directory, "registration.json")
        write(
            registration_path,
            GeoTargetCore.canonical_json(stageb_fixture_registration()) * "\n",
        )
        proposal_root = joinpath(directory, "proposals")
        manifest_path = joinpath(directory, "input.json")
        preflight = stageb_t0_materialization_preflight(
            ; preregistration_path=registration_path,
            proposal_root,
            input_manifest_path=manifest_path,
        )
        @test length(preflight.problems) == 8
        @test length(preflight.destinations) == 8
        @test !ispath(proposal_root)
        @test !ispath(manifest_path)

        missing_source = stageb_fixture_registration()
        delete!(
            missing_source["source_sha256"],
            "research/experiments/EXP-DISC-001/src/t0_corpus.jl",
        )
        missing_source_path = joinpath(directory, "missing-source.json")
        write(
            missing_source_path,
            GeoTargetCore.canonical_json(missing_source) * "\n",
        )
        @test_throws DiscoveryGateError stageb_t0_materialization_preflight(
            ; preregistration_path=missing_source_path,
            proposal_root,
            input_manifest_path=manifest_path,
        )

        wrong_replicates = stageb_fixture_registration()
        wrong_replicates["replicate_count"] = 99
        wrong_replicates_path = joinpath(directory, "wrong-replicates.json")
        write(
            wrong_replicates_path,
            GeoTargetCore.canonical_json(wrong_replicates) * "\n",
        )
        @test_throws DiscoveryGateError stageb_t0_materialization_preflight(
            ; preregistration_path=wrong_replicates_path,
            proposal_root,
            input_manifest_path=manifest_path,
        )

        wrong_threads = stageb_fixture_registration()
        wrong_threads["execution_contract"]["julia_threads"] = 64
        wrong_threads_path = joinpath(directory, "wrong-threads.json")
        write(
            wrong_threads_path,
            GeoTargetCore.canonical_json(wrong_threads) * "\n",
        )
        @test_throws DiscoveryGateError stageb_t0_materialization_preflight(
            ; preregistration_path=wrong_threads_path,
            proposal_root,
            input_manifest_path=manifest_path,
        )

        drifted = stageb_fixture_registration()
        drifted["upstream_bindings"]["weak_geometry_source"]["sha256"] = repeat("0", 64)
        drifted_path = joinpath(directory, "drifted.json")
        write(drifted_path, GeoTargetCore.canonical_json(drifted) * "\n")
        observed = try
            stageb_t0_materialization_preflight(
                ; preregistration_path=drifted_path,
                proposal_root,
                input_manifest_path=manifest_path,
            )
            nothing
        catch error
            error
        end
        @test observed isa DiscoveryGateError
        @test observed.code == :stageb_t0_source_drift
        @test !ispath(proposal_root)
        @test !ispath(manifest_path)
    end
end

@testset "Stage-B T0 D0 input is frozen once and truth-free" begin
    authority = materialization_preflight()
    problem = first(stageb_t0_problems())
    domain = StageBT0Inputs._stageb_t0_proposal_domain(problem)
    seed = derive_seed(
        STAGEB_T0_ROOT_SEED,
        STAGEB_T0_METHOD,
        1,
        1,
        STAGEB_T0_SEED_NAMESPACE,
    )
    mktempdir() do directory
        path = joinpath(directory, "d0.json")
        artifact = materialize_stream_once(
            authority,
            STAGEB_T0_METHOD,
            domain,
            path;
            replicate_seed=seed,
        )
        @test artifact.method == D0_IID_ALL
        @test size(artifact.coordinates) == (problem.dimension, 128)
        @test all(==(:iid), artifact.lane_schedule)
        @test static_prefix_audit(artifact).valid
        @test StageBT0Inputs._column_slice_sha256(artifact, 1:64) !=
              StageBT0Inputs._column_slice_sha256(artifact, 65:128)
        @test StageBT0Inputs._column_slice_sha256(artifact, 1:64) ==
              StageBT0Inputs._column_slice_sha256(read_matrix_artifact(path), 1:64)
        metadata = JSON3.read(artifact.metadata_json, Dict{String,Any})
        serialized = lowercase(GeoTargetCore.canonical_json(metadata))
        @test !occursin("family_id", serialized)
        @test !occursin("instance_id", serialized)
        @test !occursin("gold_targets", serialized)
        @test !occursin("formal_case_id", serialized)
        @test_throws DiscoveryGateError materialize_stream_once(
            authority,
            STAGEB_T0_METHOD,
            domain,
            path;
            replicate_seed=seed,
        )
    end
end
