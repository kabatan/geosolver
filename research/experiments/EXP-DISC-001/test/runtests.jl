using ExperimentDisc001
using GeoTargetBenchmarks
using GeoTargetCore
using JSON3
using SHA
using Test

const EXP_ROOT = normpath(joinpath(@__DIR__, ".."))
const REPO_ROOT = normpath(joinpath(EXP_ROOT, "..", "..", ".."))

struct TruthPoisonView
    dimension::Int
    lower_bounds::Tuple
    upper_bounds::Tuple
end

function Base.getproperty(view::TruthPoisonView, name::Symbol)
    name in (:dimension, :lower_bounds, :upper_bounds) || error("forbidden truth field: $name")
    return getfield(view, name)
end

file_sha(path) = bytes2hex(sha256(read(path)))

function fake_freeze_document()
    preregistration = preregistration_bindings()
    source_path = "benchmarks/solver_lab/CoreBaseline.jl"
    options = GeoTargetCore.canonical_json(Dict(
        "finite_difference_step" => "0x1.0p-18",
        "initial_damping" => "0x1.0624dd2f1a9fcp-10",
        "max_evaluations" => 2_000,
        "max_iterations" => 250,
        "residual_tolerance" => "1e-12",
    ))
    return Dict{String,Any}(
        "confirmation" => Dict(
            "coordinate_stability_tolerance" => "1e-100",
            "primary_precision_bits" => 512,
            "reference_precision_bits" => 768,
            "scaled_residual_tolerance" => "1e-100",
            "target_stability_tolerance" => "1e-100",
        ),
        "experiment_id" => "EXP-DISC-001",
        "preregistration_sha256" => preregistration,
        "schema_version" => "exp-disc-001-local-champion-freeze/v1",
        "selected_local_solver" => Dict(
            "canonical_options_json" => options,
            "canonical_options_sha256" => bytes2hex(sha256(codeunits(options))),
            "source_sha256" => Dict(
                source_path => file_sha(joinpath(REPO_ROOT, split(source_path, '/')...)),
            ),
        ),
        "status" => "frozen",
        "upstream_decisions" => Dict(
            "EXP-LOCAL-003" => Dict("state" => "test-fixture"),
            "EXP-LOCAL-004" => Dict("state" => "test-fixture"),
        ),
        "versions" => Dict(
            "compiler" => file_sha(joinpath(
                REPO_ROOT,
                "julia",
                "GeoTargetCore",
                "src",
                "compiler.jl",
            )),
            "julia" => string(VERSION),
            "manifest_sha256" => file_sha(joinpath(EXP_ROOT, "Manifest.toml")),
            "plugin_abi" => string(GeoTargetCore.CORE_ABI_VERSION),
            "problem_wire" => GeoTargetCore.PROBLEM_WIRE_VERSION,
            "solve_api" => string(GeoTargetCore.SOLVE_API_VERSION),
        ),
    )
end

function fixed_matrix_fixture()
    dimension = 2
    columns = MATRIX_COLUMN_COUNT
    unit = Matrix{Float64}(undef, dimension, columns)
    for column in 1:columns
        unit[1, column] = (column - 0.5) / columns
        unit[2, column] = (columns - column + 0.5) / columns
    end
    coordinates = similar(unit)
    coordinates[1, :] .= -2 .+ 4 .* unit[1, :]
    coordinates[2, :] .= 10 .+ 2 .* unit[2, :]
    lanes = ntuple(index -> mod(index - 1, 4) == 0 ? :iid : :owen, columns)
    source_columns = ntuple(index -> index, columns)
    return ProposalMatrixArtifact(
        D3_OWEN_MIXED,
        unit,
        coordinates,
        lanes,
        source_columns,
        0x1234,
        Dict("fixture" => "static-prefix-only"),
        repeat("0", 64),
    )
end

@testset "A3 authority fails closed before side effects" begin
    mktempdir() do directory
        missing = joinpath(directory, "missing-freeze.json")
        output = joinpath(directory, "must-not-exist.json")
        proposals = joinpath(directory, "must-not-exist")
        options = RunnerOptions(
            freeze_path=missing,
            output=output,
            proposal_root=proposals,
        )
        observed = try
            run_preflight(options)
            nothing
        catch error
            error
        end
        @test observed isa DiscoveryGateError
        @test observed.code == :missing_local_champion_freeze
        @test !ispath(output)
        @test !ispath(proposals)
    end
end

@testset "validated fixture authority remains preflight-only" begin
    mktempdir() do directory
        freeze_path = joinpath(directory, "fixture-freeze.json")
        write(freeze_path, GeoTargetCore.canonical_json(fake_freeze_document()) * "\n")
        contract = run_preflight(RunnerOptions(freeze_path=freeze_path))
        @test contract["partition"] == "development"
        @test contract["proposal_only_difference"]
        @test contract["confirmation"]["primary_bits"] == 512
        @test contract["confirmation"]["reference_bits"] == 768

        drifted = fake_freeze_document()
        drifted["versions"]["solve_api"] = "stale"
        drifted_path = joinpath(directory, "drifted-freeze.json")
        write(drifted_path, GeoTargetCore.canonical_json(drifted) * "\n")
        observed = try
            run_preflight(RunnerOptions(freeze_path=drifted_path))
            nothing
        catch error
            error
        end
        @test observed isa DiscoveryGateError
        @test observed.code == :version_binding_drift

        execute = RunnerOptions(freeze_path=freeze_path, preflight_only=false)
        observed = try
            run_preflight(execute)
            nothing
        catch error
            error
        end
        @test observed isa DiscoveryGateError
        @test observed.code == :development_execution_not_enabled
    end
end

@testset "truth-blind domain projection" begin
    view = TruthPoisonView(2, (-3.0, 1.0), (4.0, 9.0))
    domain = truth_blind_domain(view)
    @test domain.lower == (-3.0, 1.0)
    @test domain.upper == (4.0, 9.0)
    @test_throws ErrorException getproperty(view, :family_id)
    source = read(joinpath(EXP_ROOT, "src", "streams.jl"), String)
    @test !occursin("gold_configurations", lowercase(source))
    @test !occursin("gold_targets", lowercase(source))
    @test !occursin("family_id", lowercase(source))
    @test !occursin("instance_id", lowercase(source))
end

@testset "frozen MultiRoot T0 corpus and proposal replacement" begin
    problems = t0_problems()
    @test length(problems) == 6
    @test sum(length(problem.gold_targets) for problem in problems) == 17
    @test [problem.dimension for problem in problems] == [4, 4, 2, 4, 8, 4]
    @test [length(problem.gold_targets) for problem in problems] == [4, 2, 1, 2, 4, 4]
    @test [recipe.source_index for recipe in ExperimentDisc001.T0_RECIPE] ==
          [6, 7, 31, 32, 33, 35]

    problem = first(problems)
    domain = t0_proposal_domain(problem)
    @test domain.lower == Tuple(problem.lower_bounds)
    @test domain.upper == Tuple(problem.upper_bounds)
    midpoint = (problem.lower_bounds .+ problem.upper_bounds) ./ 2
    proposals = repeat(reshape(midpoint, :, 1), 1, MATRIX_COLUMN_COUNT)
    replacement = t0_problem_with_proposals(problem, proposals)
    @test replacement.saved_starts == proposals
    @test GeoTargetBenchmarks.verify_replay_material(replacement)
    @test GeoTargetBenchmarks.replay_checksum(replacement) !=
          GeoTargetBenchmarks.replay_checksum(problem)
    @test size(problem.saved_starts, 2) == 32
end

@testset "T0 materialization contract is pre-outcome and side-effect free" begin
    mktempdir() do directory
        source_relative = "research/experiments/EXP-DISC-001/src/t0_corpus.jl"
        registration = Dict{String,Any}(
            "schema_version" => "geotarget.discovery-t0-preregistration/v1",
            "materialization_authorized" => true,
            "outcome_execution_authorized" => false,
            "local_freeze_sha256" => file_sha(
                ExperimentDisc001.DEFAULT_CHAMPION_FREEZE_PATH,
            ),
            "root_seed" => string(ExperimentDisc001.T0_ROOT_SEED),
            "replicate_count" => ExperimentDisc001.T0_REPLICATE_COUNT,
            "methods" => [
                ExperimentDisc001._METHOD_WIRE[method] for
                method in ExperimentDisc001.T0_METHODS
            ],
            "source_sha256" => Dict(
                source_relative => file_sha(joinpath(
                    REPO_ROOT,
                    split(source_relative, '/')...,
                )),
            ),
        )
        registration_path = joinpath(directory, "registration.json")
        write(registration_path, GeoTargetCore.canonical_json(registration) * "\n")
        proposal_root = joinpath(directory, "proposals")
        input_manifest = joinpath(directory, "input.json")
        preflight = t0_materialization_preflight(
            ; preregistration_path=registration_path,
            proposal_root,
            input_manifest_path=input_manifest,
        )
        @test length(preflight.problems) == 6
        @test length(preflight.destinations) == 42
        @test !ispath(proposal_root)
        @test !ispath(input_manifest)
    end
end

@testset "fixed lossless maximum-prefix fixture" begin
    artifact = fixed_matrix_fixture()
    audit = static_prefix_audit(artifact)
    @test audit.valid
    @test sort!(collect(keys(audit.prefix_sha256))) == collect(CHECKPOINT_COLUMNS)
    for prefix in CHECKPOINT_COLUMNS
        @test Matrix(leading_prefix(artifact, prefix)) == artifact.coordinates[:, 1:prefix]
    end
    document = artifact_document(artifact)
    replay = matrix_from_document(document)
    @test replay.sha256 == artifact.sha256
    @test reinterpret(UInt64, vec(replay.coordinates)) ==
          reinterpret(UInt64, vec(artifact.coordinates))

    mktempdir() do directory
        path = joinpath(directory, "fixture.json")
        @test write_matrix_once(path, artifact) == artifact.sha256
        loaded = read_matrix_artifact(path)
        @test loaded.sha256 == artifact.sha256
        @test_throws DiscoveryGateError write_matrix_once(path, artifact)
    end

    drifted = fixed_matrix_fixture()
    drifted.coordinates[1, 1] = nextfloat(drifted.coordinates[1, 1])
    @test_throws DiscoveryGateError static_prefix_audit(drifted)
end

@testset "IID bounded-gap and starvation audit" begin
    good = ntuple(index -> mod(index - 1, 4) == 0 ? :iid : :owen, 128)
    audit = iid_bounded_gap_audit(good; cadence=4)
    @test audit.bounded_gap
    @test audit.iid_count == 32
    @test audit.maximum_gap == 4
    @test audit.starvation_count == 0

    bad = ntuple(index -> index == 1 ? :iid : :owen, 12)
    failed = iid_bounded_gap_audit(bad; cadence=4)
    @test !failed.bounded_gap
    @test failed.starvation_count == 1
    @test !isempty(failed.violation_prefixes)
end

@testset "base-2 digital-net t audit" begin
    centered = reshape([(index + 0.5) / 8 for index in 0:7], 1, :)
    @test digital_net_minimal_t(centered) == 0
    duplicated = repeat(centered[:, 1:1], 1, 8)
    @test digital_net_minimal_t(duplicated) == 3
    @test_throws ArgumentError digital_net_minimal_t(centered[:, 1:7])
    @test_throws ArgumentError digital_net_minimal_t(ones(1, 8))
end

@testset "all T0 proposal sources materialize before outcomes" begin
    authority = materialization_preflight()
    domain = t0_proposal_domain(first(t0_problems()))
    mktempdir() do directory
        paths = Dict{DiscoveryMethod,String}()
        artifacts = Dict{DiscoveryMethod,ProposalMatrixArtifact}()
        for method in ExperimentDisc001.T0_METHODS[1:end - 1]
            path = joinpath(directory, "$(Int(method)).json")
            seed = derive_seed(
                ExperimentDisc001.T0_ROOT_SEED,
                method,
                1,
                1,
                "t0-proposal",
            )
            artifacts[method] = materialize_stream_once(
                authority,
                method,
                domain,
                path;
                replicate_seed=seed,
            )
            paths[method] = path
            @test static_prefix_audit(artifacts[method]).valid
        end
        mixed = D3_OWEN_MIXED
        mixed_path = joinpath(directory, "mixed.json")
        artifacts[mixed] = materialize_stream_once(
            authority,
            mixed,
            domain,
            mixed_path;
            replicate_seed=derive_seed(
                ExperimentDisc001.T0_ROOT_SEED,
                mixed,
                1,
                1,
                "t0-proposal",
            ),
            iid_source_path=paths[D0_IID_ALL],
            rqmc_source_path=paths[D2O_OWEN_ALL],
        )
        @test length(artifacts) == 7
        @test iid_bounded_gap_audit(
            artifacts[D_CURRENT_COUNTER_HALTON].lane_schedule,
        ).bounded_gap
        @test iid_bounded_gap_audit(artifacts[mixed].lane_schedule).bounded_gap
        @test all(
            !isnothing(digital_net_prefix_audit(artifacts[method])) for
            method in (D1_SOBOL_ALL, D2O_OWEN_ALL, D2M_MATOUSEK_ALL)
        )
    end
end

@testset "seed namespaces and case sharding" begin
    first_seed = derive_seed(17, D0_IID_ALL, 2, 3)
    @test first_seed == derive_seed(17, D0_IID_ALL, 2, 3)
    @test first_seed != derive_seed(17, D2O_OWEN_ALL, 2, 3)
    @test first_seed != derive_seed(17, D0_IID_ALL, 3, 3)
    shards = [shard_ordinals(11, index, 4) for index in 1:4]
    @test sort(vcat((collect(shard) for shard in shards)...)) == collect(1:11)
    @test isempty(intersect(Set(shards[1]), Set(shards[2])))
    @test parse_runner_arguments(["--shard-index=2", "--shard-count=4"]).shard_index == 2
end

@testset "all Stage-A stream contracts remain proposal-only" begin
    methods = (
        D0_IID_ALL,
        D1_SOBOL_ALL,
        D_HALTON_ALL,
        D_CURRENT_COUNTER_HALTON,
        D2O_OWEN_ALL,
        D2M_MATOUSEK_ALL,
        D3_OWEN_MIXED,
    )
    @test all(method -> stream_contract(method)["truth_fields_visible"] == false, methods)
    @test all(method -> stream_contract(method)["column_count"] == 128, methods)
    @test all(method -> stream_contract(method)["prefixes"] == [8, 16, 32, 64, 128], methods)
end
