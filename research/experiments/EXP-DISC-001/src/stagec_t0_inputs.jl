module StageCT0Inputs

using ExperimentDisc001
using GeoTargetBenchmarks
using GeoTargetCore
using JSON3

include("stagea_corpus.jl")
include("stageb_t0_inputs.jl")
using .StageAInputs
using .StageBT0Inputs

const STAGEC_T0_SOURCE_MANIFEST =
    "research/experiments/EXP-LOCAL-004/t2-input-manifest.json"
const STAGEC_T0_SOURCE_INDICES = (11, 12, 17, 18, 29, 30, 33, 35, 40, 41, 46, 47)
const STAGEC_T0_CASE_COUNT = 12
const STAGEC_T0_ROOT_SEED = UInt64(16_319_848_619_023_564_901)
const STAGEC_T0_REPLICATE_COUNT = 1
const STAGEC_T0_METHOD = D0_IID_ALL
const STAGEC_T0_SEED_NAMESPACE = "stagec-soft-tgo-t0-source"
const STAGEC_T0_BATCH_SIZE = 16
const STAGEC_T0_BATCH_COUNT = 8
const STAGEC_T0_LOCAL_CALLBACK_CAP = 600
const STAGEC_T0_CALLBACK_THRESHOLDS = (600, 1_200, 2_400, 4_800)
const STAGEC_T0_CANDIDATE_ARMS = ("FIFO_SCORED", "RESIDUAL_ONLY", "SOFT_TGO")
const STAGEC_T0_DERIVED_CONTROL = "FIFO_UNSCORED"
const STAGEC_T0_NORMALIZATION_ULP_MULTIPLIER = 8
const STAGEC_T0_NORMALIZATION_GATE =
    "each coordinate requires max finite prev/next ULP gap at lower, midpoint and upper <= 8eps(Float64) * half_range; otherwise the complete batch uses FIFO service"
const STAGEC_T0_COVARIANCE_CLAIM_BOUNDARY =
    "scale and orthogonal covariance is claimed only when both replica boxes pass the normalization-resolution gate"
const STAGEC_T0_ORDERER_SOURCE_SHA =
    "7eec93a5711e3f1049e562a05d1bd9a29eae3451513158549944f4fad40ad1d1"
const STAGEC_T0_ORDERER_TEST_SHA =
    "c4642474f56828fdb2bd00518fe35646cbb81d917b93f25cd37d183203d2f8b9"

const DEFAULT_STAGEC_T0_PREREGISTRATION_PATH =
    joinpath(ExperimentDisc001.EXPERIMENT_ROOT, "stagec-t0-preregistration.json")
const DEFAULT_STAGEC_T0_INPUT_MANIFEST_PATH =
    joinpath(ExperimentDisc001.EXPERIMENT_ROOT, "stagec-t0-input-manifest.json")
const DEFAULT_STAGEC_T0_PROPOSAL_ROOT =
    joinpath(ExperimentDisc001.EXPERIMENT_ROOT, "materialized", "stagec-t0")

const STAGEC_T0_RECIPE = Tuple(
    (
        formal_case_id="EXP-DISC-001-C0-$(lpad(case_index, 3, '0'))",
        source=STAGEC_T0_SOURCE_MANIFEST,
        source_index=source_index,
    ) for (case_index, source_index) in enumerate(STAGEC_T0_SOURCE_INDICES)
)

"""Reuse the frozen manual Stage-A/B recipes and their T2 replay checks."""
function stagec_t0_problems()
    stageb = stageb_t0_problems()
    stagea = stagea_problems()
    problems = vcat(stageb, stagea[[16, 17, 22, 23]])
    length(problems) == STAGEC_T0_CASE_COUNT || error("Stage-C T0 case count drifted")
    expected_families = (
        "CURVED-CHAIN",
        "NEAR-RANK-DEFICIENT",
        "TANGENT-CIRCLE-LINE",
        "MULTIROOT-WARPED",
        "STRICT-GUARD-BOUNDARY",
        "OPAQUE-TRANSCENDENTAL-C0",
    )
    all(family -> count(problem -> problem.family_id == family, problems) == 2,
        expected_families) || error("Stage-C T0 family balance drifted")
    sum(size(problem.gold_configurations, 2) for problem in problems) == 42 ||
        error("Stage-C T0 configuration count drifted")
    sum(length(problem.gold_targets) for problem in problems) == 34 ||
        error("Stage-C T0 target count drifted")
    all(verify_replay_material, problems) || error("Stage-C T0 replay drifted")
    return problems
end

stagec_t0_problem_with_proposals(problem::DirectAnalyticProblem, proposals) =
    t0_problem_with_proposals(problem, proposals)

_stagec_t0_domain(problem::DirectAnalyticProblem) = truth_blind_domain((;
    dimension=problem.dimension,
    lower_bounds=Tuple(problem.lower_bounds),
    upper_bounds=Tuple(problem.upper_bounds),
))

_stagec_t0_artifact_path(root, case_index) = joinpath(
    root,
    "case-$(lpad(case_index, 2, '0'))",
    "replicate-01-d0-iid-all.json",
)

function _validate_registration(path, authority)
    document = JSON3.read(read(path, String), Dict{String,Any})
    get(document, "schema_version", nothing) ==
        "geotarget.discovery-stagec-soft-tgo-t0-preregistration/v1" ||
        error("Stage-C T0 preregistration schema drifted")
    get(document, "materialization_authorized", false) === true ||
        error("Stage-C T0 materialization is not authorized")
    get(document, "outcome_execution_authorized", true) === false ||
        error("Stage-C T0 preregistration authorized outcomes")
    get(document, "local_freeze_sha256", nothing) == authority.freeze_sha256 ||
        error("Stage-C T0 local freeze drifted")
    parse(UInt64, String(document["root_seed"])) == STAGEC_T0_ROOT_SEED ||
        error("Stage-C T0 root seed drifted")
    get(document, "seed_namespace", nothing) == STAGEC_T0_SEED_NAMESPACE ||
        error("Stage-C T0 seed namespace drifted")
    get(document, "method", nothing) == "D0-IID-ALL" ||
        error("Stage-C T0 method drifted")
    get(document, "case_count", nothing) == STAGEC_T0_CASE_COUNT ||
        error("Stage-C T0 case count drifted")
    registered = get(document, "case_sources", Any[])
    length(registered) == STAGEC_T0_CASE_COUNT || error("Stage-C T0 recipe count drifted")
    for (case_index, recipe) in enumerate(STAGEC_T0_RECIPE)
        item = registered[case_index]
        get(item, "formal_case_id", nothing) == recipe.formal_case_id &&
            get(item, "path", nothing) == recipe.source &&
            get(item, "index", nothing) == recipe.source_index ||
            error("Stage-C T0 recipe drifted at case $case_index")
    end
    bindings = document["upstream_bindings"]
    for (name, relative) in (
        "stagea_decision" =>
            "research/experiments/EXP-DISC-001/stagea-decision.json",
        "stageb_t0_decision" =>
            "research/experiments/EXP-DISC-001/stageb-t0-decision.json",
    )
        binding = bindings[name]
        get(binding, "path", nothing) == relative ||
            error("Stage-C T0 $name path drifted")
        path = joinpath(ExperimentDisc001.REPOSITORY_ROOT, split(relative, '/')...)
        get(binding, "sha256", nothing) == ExperimentDisc001._file_sha256(path) ||
            error("Stage-C T0 $name hash drifted")
    end
    get(bindings["soft_tgo_ordering_source"], "sha256", nothing) ==
        STAGEC_T0_ORDERER_SOURCE_SHA || error("Stage-C T0 orderer source hash drifted")
    get(bindings["soft_tgo_ordering_test"], "sha256", nothing) ==
        STAGEC_T0_ORDERER_TEST_SHA || error("Stage-C T0 orderer test hash drifted")
    for (relative, expected) in (
        "research/experiments/EXP-DISC-001/src/soft_tgo_ordering.jl" =>
            STAGEC_T0_ORDERER_SOURCE_SHA,
        "research/experiments/EXP-DISC-001/test/stagec_soft_tgo_ordering.jl" =>
            STAGEC_T0_ORDERER_TEST_SHA,
    )
        path = joinpath(ExperimentDisc001.REPOSITORY_ROOT, split(relative, '/')...)
        ExperimentDisc001._file_sha256(path) == expected || error("Stage-C orderer drifted")
    end
    return document
end

function stagec_t0_materialization_preflight(;
    freeze_path::AbstractString=ExperimentDisc001.DEFAULT_CHAMPION_FREEZE_PATH,
    preregistration_path::AbstractString=DEFAULT_STAGEC_T0_PREREGISTRATION_PATH,
    proposal_root::AbstractString=DEFAULT_STAGEC_T0_PROPOSAL_ROOT,
    input_manifest_path::AbstractString=DEFAULT_STAGEC_T0_INPUT_MANIFEST_PATH,
)
    authority = materialization_preflight(freeze_path)
    registration = _validate_registration(preregistration_path, authority)
    problems = stagec_t0_problems()
    destinations = [
        _stagec_t0_artifact_path(abspath(proposal_root), case_index) for
        case_index in eachindex(problems)
    ]
    any(ispath, destinations) && error("a Stage-C T0 proposal already exists")
    ispath(input_manifest_path) && error("the Stage-C T0 input manifest already exists")
    return (;
        authority,
        registration,
        problems,
        destinations,
        preregistration_sha256=ExperimentDisc001._file_sha256(preregistration_path),
    )
end

function _truth_free(artifact)
    text = lowercase(artifact.metadata_json)
    for forbidden in ("family_id", "instance_id", "formal_case_id", "gold_targets")
        occursin(forbidden, text) && error("truth leaked into Stage-C proposal metadata")
    end
    return true
end

function _write_exclusive(path, document)
    mkpath(dirname(abspath(path)))
    stream = Base.Filesystem.open(
        abspath(path),
        Base.JL_O_WRONLY | Base.JL_O_CREAT | Base.JL_O_EXCL,
        0o644,
    )
    try
        write(stream, GeoTargetCore.canonical_json(document), "\n")
    finally
        close(stream)
    end
end

function materialize_stagec_t0_inputs(;
    freeze_path::AbstractString=ExperimentDisc001.DEFAULT_CHAMPION_FREEZE_PATH,
    preregistration_path::AbstractString=DEFAULT_STAGEC_T0_PREREGISTRATION_PATH,
    proposal_root::AbstractString=DEFAULT_STAGEC_T0_PROPOSAL_ROOT,
    input_manifest_path::AbstractString=DEFAULT_STAGEC_T0_INPUT_MANIFEST_PATH,
)
    isempty(strip(read(`git -C $(ExperimentDisc001.REPOSITORY_ROOT) status --porcelain`, String))) ||
        error("Stage-C T0 materialization requires a clean tree")
    preflight = stagec_t0_materialization_preflight(
        ; freeze_path, preregistration_path, proposal_root, input_manifest_path,
    )
    cases = Any[]
    for (case_index, problem) in enumerate(preflight.problems)
        recipe = STAGEC_T0_RECIPE[case_index]
        seed = derive_seed(
            STAGEC_T0_ROOT_SEED,
            STAGEC_T0_METHOD,
            case_index,
            1,
            STAGEC_T0_SEED_NAMESPACE,
        )
        destination = preflight.destinations[case_index]
        artifact = materialize_stream_once(
            preflight.authority,
            STAGEC_T0_METHOD,
            _stagec_t0_domain(problem),
            destination;
            replicate_seed=seed,
        )
        size(artifact.coordinates, 2) == 128 && all(==(:iid), artifact.lane_schedule) ||
            error("Stage-C T0 D0 source drifted")
        _truth_free(artifact)
        push!(cases, Dict{String,Any}(
            "case_index" => case_index,
            "configuration_count" => size(problem.gold_configurations, 2),
            "dimension" => problem.dimension,
            "family_id" => problem.family_id,
            "formal_case_id" => recipe.formal_case_id,
            "instance_id" => problem.instance_id,
            "proposal" => Dict{String,Any}(
                "artifact_sha256" => artifact.sha256,
                "file_sha256" => ExperimentDisc001._file_sha256(destination),
                "path" => ExperimentDisc001._repository_relative(destination),
                "replicate_seed" => string(seed),
                "truth_free_metadata" => true,
            ),
            "replay_checksum" => replay_checksum(problem),
            "source_index" => recipe.source_index,
            "target_count" => length(problem.gold_targets),
        ))
    end
    document = Dict{String,Any}(
        "case_count" => STAGEC_T0_CASE_COUNT,
        "cases" => cases,
        "experiment_id" => "EXP-DISC-001",
        "local_freeze_sha256" => preflight.authority.freeze_sha256,
        "method" => "D0-IID-ALL",
        "nonpromotional_t0" => true,
        "preregistration" => Dict(
            "path" => ExperimentDisc001._repository_relative(preregistration_path),
            "sha256" => preflight.preregistration_sha256,
        ),
        "revision" => readchomp(`git -C $(ExperimentDisc001.REPOSITORY_ROOT) rev-parse HEAD`),
        "root_seed" => string(STAGEC_T0_ROOT_SEED),
        "schema_version" => "geotarget.discovery-stagec-soft-tgo-t0-input/v1",
        "seed_namespace" => STAGEC_T0_SEED_NAMESPACE,
        "stage" => "stage-c-soft-tgo-t0",
        "target_count" => 34,
    )
    _write_exclusive(input_manifest_path, document)
    return document
end

export DEFAULT_STAGEC_T0_INPUT_MANIFEST_PATH,
    DEFAULT_STAGEC_T0_PREREGISTRATION_PATH,
    DEFAULT_STAGEC_T0_PROPOSAL_ROOT,
    STAGEC_T0_BATCH_COUNT,
    STAGEC_T0_BATCH_SIZE,
    STAGEC_T0_CALLBACK_THRESHOLDS,
    STAGEC_T0_CANDIDATE_ARMS,
    STAGEC_T0_CASE_COUNT,
    STAGEC_T0_DERIVED_CONTROL,
    STAGEC_T0_LOCAL_CALLBACK_CAP,
    STAGEC_T0_METHOD,
    STAGEC_T0_NORMALIZATION_GATE,
    STAGEC_T0_NORMALIZATION_ULP_MULTIPLIER,
    STAGEC_T0_COVARIANCE_CLAIM_BOUNDARY,
    STAGEC_T0_RECIPE,
    STAGEC_T0_ROOT_SEED,
    STAGEC_T0_SEED_NAMESPACE,
    STAGEC_T0_SOURCE_INDICES,
    materialize_stagec_t0_inputs,
    stagec_t0_materialization_preflight,
    stagec_t0_problem_with_proposals,
    stagec_t0_problems

end
