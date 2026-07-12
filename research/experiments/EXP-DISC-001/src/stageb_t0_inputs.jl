module StageBT0Inputs

using ExperimentDisc001
using GeoTargetBenchmarks
using GeoTargetCore
using JSON3
using SHA

const REPOSITORY_ROOT = ExperimentDisc001.REPOSITORY_ROOT
const EXPERIMENT_ROOT = ExperimentDisc001.EXPERIMENT_ROOT

const STAGEB_T0_SOURCE_MANIFEST =
    "research/experiments/EXP-LOCAL-004/t2-input-manifest.json"
const STAGEB_T0_SOURCE_INDICES = (11, 12, 17, 18, 29, 30, 33, 35)
const STAGEB_T0_CASE_COUNT = length(STAGEB_T0_SOURCE_INDICES)
const STAGEB_T0_ROOT_SEED = UInt64(12_265_488_775_294_079_487)
const STAGEB_T0_REPLICATE_COUNT = 1
const STAGEB_T0_METHOD = D0_IID_ALL
const STAGEB_T0_SEED_NAMESPACE = "stageb-t0-source"
const STAGEB_T0_INITIAL_PREFIX = 64
const STAGEB_T0_CONTINUATION = 65:128
const STAGEB_T0_PROPOSAL_COUNT = STAGEB_T0_CASE_COUNT

const STAGEB_T0_REQUIRED_SOURCE_PATHS = Set((
    "julia/GeoTargetBenchmarks/src/GeoTargetBenchmarks.jl",
    "julia/GeoTargetBenchmarks/src/common.jl",
    "julia/GeoTargetBenchmarks/src/curved_chain.jl",
    "julia/GeoTargetBenchmarks/src/multiroot_warped.jl",
    "julia/GeoTargetBenchmarks/src/near_rank_deficient.jl",
    "julia/GeoTargetBenchmarks/src/replay.jl",
    "julia/GeoTargetBenchmarks/src/tangent_circle_line.jl",
    "julia/GeoTargetBenchmarks/src/types.jl",
    "julia/GeoTargetCore/src/proposal_engine.jl",
    "julia/GeoTargetCore/src/protocol_json.jl",
    "research/experiments/EXP-DISC-001/Manifest.toml",
    "research/experiments/EXP-DISC-001/Project.toml",
    "research/experiments/EXP-DISC-001/local-champion-freeze-record.json",
    "research/experiments/EXP-DISC-001/materialize_stageb_t0.jl",
    "research/experiments/EXP-DISC-001/src/ExperimentDisc001.jl",
    "research/experiments/EXP-DISC-001/src/gate.jl",
    "research/experiments/EXP-DISC-001/src/matrix_artifact.jl",
    "research/experiments/EXP-DISC-001/src/stageb_t0_inputs.jl",
    "research/experiments/EXP-DISC-001/src/streams.jl",
    "research/experiments/EXP-DISC-001/src/t0_corpus.jl",
    "research/experiments/EXP-DISC-001/src/weak_geometry.jl",
    "research/experiments/EXP-DISC-001/stagea-decision.json",
    "research/experiments/EXP-DISC-001/test/stageb_t0_inputs.jl",
    "research/experiments/EXP-DISC-001/test/stageb_weak_geometry.jl",
    "research/experiments/EXP-LOCAL-004/t2-input-manifest.json",
))

const STAGEB_T0_EXECUTION_CONTRACT = Dict{String,Any}(
    "one_case_per_process" => true,
    "maximum_case_processes" => 8,
    "physical_cpus" => "0-7",
    "assigned_cpu_formula" => "case_index - 1",
    "julia_threads" => 1,
    "blas_threads" => 1,
    "omp_threads" => 1,
    "mkl_threads" => 1,
    "solver_worker_count" => 1,
    "within_case_parallelism" => false,
    "wall_time_role" => "diagnostic only",
)

const DEFAULT_STAGEB_T0_PREREGISTRATION_PATH =
    joinpath(EXPERIMENT_ROOT, "stageb-t0-preregistration.json")
const DEFAULT_STAGEB_T0_INPUT_MANIFEST_PATH =
    joinpath(EXPERIMENT_ROOT, "stageb-t0-input-manifest.json")
const DEFAULT_STAGEB_T0_PROPOSAL_ROOT =
    joinpath(EXPERIMENT_ROOT, "materialized", "stageb-t0")

const STAGEB_T0_RECIPE = Tuple(
    (
        formal_case_id="EXP-DISC-001-B0-$(lpad(case_index, 3, '0'))",
        source=STAGEB_T0_SOURCE_MANIFEST,
        source_index=source_index,
    ) for (case_index, source_index) in enumerate(STAGEB_T0_SOURCE_INDICES)
)

function _stageb_t0_parameter_records()
    return Any[
        CurvedChainParams(
            dimension=4,
            curvature=1.0e8,
            instance_seed=10_205,
            start_seed=20_205,
            start_count=32,
        ),
        CurvedChainParams(
            dimension=8,
            curvature=1.0e12,
            instance_seed=10_206,
            start_seed=20_206,
            start_count=32,
        ),
        NearRankDeficientParams(
            dimension=4,
            singular_value_ratio=1.0e-8,
            orientation_seed=10_305,
            start_seed=20_305,
            start_count=32,
        ),
        NearRankDeficientParams(
            dimension=8,
            singular_value_ratio=1.0e-12,
            orientation_seed=10_306,
            start_seed=20_306,
            start_count=32,
        ),
        TangentCircleLineParams(
            radius=2.0,
            height_radius_ratio=0.999999,
            instance_seed=10_505,
            start_seed=20_505,
            start_count=32,
        ),
        TangentCircleLineParams(
            radius=0.5,
            height_radius_ratio=0.99999999,
            instance_seed=10_506,
            start_seed=20_506,
            start_count=32,
        ),
        MultiRootWarpedParams(
            dimension=8,
            root_count=8,
            minimum_separation=1.0e-6,
            warp=0.5,
            condition=1.0e8,
            target_map=:z1_squared,
            target_affine_scale=1.0e-6,
            coefficient_seed=10_603,
            start_seed=20_603,
            start_count=32,
        ),
        MultiRootWarpedParams(
            dimension=4,
            root_count=8,
            minimum_separation=1.0e-6,
            warp=0.5,
            condition=1.0e4,
            target_map=:z1_squared,
            target_affine_scale=1.0e-6,
            coefficient_seed=10_605,
            start_seed=20_605,
            start_count=32,
        ),
    ]
end

function _manifest_parameter_value(value::Symbol)
    return String(value)
end

function _manifest_parameter_value(value::UInt64)
    value <= typemax(Int) || throw(ArgumentError("parameter seed does not fit Int"))
    return Int(value)
end

_manifest_parameter_value(value::Tuple) = Any[_manifest_parameter_value(item) for item in value]
_manifest_parameter_value(value::AbstractVector) =
    Any[_manifest_parameter_value(item) for item in value]
_manifest_parameter_value(value) = value

function _parameter_document(parameters)
    return Dict{String,Any}(
        String(name) => _manifest_parameter_value(getfield(parameters, name)) for
        name in fieldnames(typeof(parameters))
    )
end

function _stageb_t0_source_document()
    path = joinpath(REPOSITORY_ROOT, split(STAGEB_T0_SOURCE_MANIFEST, '/')...)
    document = JSON3.read(read(path, String), Dict{String,Any})
    get(document, "schema_version", nothing) == "exp-local-004-t2-input/v1" || throw(
        DiscoveryGateError(:stageb_t0_corpus_drift, "unexpected source manifest schema"),
    )
    return document
end

function _verify_stageb_t0_problem(problem, source, recipe, case_index)
    checks = (
        ("instance_id", problem.instance_id),
        ("family_id", problem.family_id),
        ("dimension", problem.dimension),
        ("residual_dimension", problem.residual_dimension),
        ("configuration_count", size(problem.gold_configurations, 2)),
        ("target_count", length(problem.gold_targets)),
        ("replay_checksum", replay_checksum(problem)),
    )
    for (field, expected) in checks
        get(source, field, nothing) == expected || throw(
            DiscoveryGateError(
                :stageb_t0_corpus_drift,
                "$field drifted at Stage-B T0 case $case_index",
            ),
        )
    end
    get(source, "parameters", nothing) == _parameter_document(problem.parameters) || throw(
        DiscoveryGateError(
            :stageb_t0_corpus_drift,
            "manual parameter replay drifted at Stage-B T0 case $case_index",
        ),
    )
    String.(get(source, "strata", Any[])) == collect(String.(problem.strata)) || throw(
        DiscoveryGateError(
            :stageb_t0_corpus_drift,
            "strata drifted at Stage-B T0 case $case_index",
        ),
    )
    recipe.source_index == STAGEB_T0_SOURCE_INDICES[case_index] || throw(
        DiscoveryGateError(:stageb_t0_corpus_drift, "source ordinal drifted"),
    )
    verify_replay_material(problem) || throw(
        DiscoveryGateError(
            :stageb_t0_corpus_drift,
            "Stage-B T0 case $case_index is not replayable",
        ),
    )
    all(isfinite, problem.lower_bounds) && all(isfinite, problem.upper_bounds) || throw(
        DiscoveryGateError(
            :stageb_t0_corpus_drift,
            "Stage-B T0 requires finite proposal bounds",
        ),
    )
    return problem
end

"""Rebuild the eight preregistered Stage-B T0 cases from manual parameters."""
function stageb_t0_problems()
    source = _stageb_t0_source_document()
    instances = source["instances"]
    records = _stageb_t0_parameter_records()
    length(records) == STAGEB_T0_CASE_COUNT || error("Stage-B T0 recipe drifted")
    problems = DirectAnalyticProblem[]
    for case_index in 1:STAGEB_T0_CASE_COUNT
        recipe = STAGEB_T0_RECIPE[case_index]
        problem = generate(records[case_index])
        push!(
            problems,
            _verify_stageb_t0_problem(
                problem,
                instances[recipe.source_index],
                recipe,
                case_index,
            ),
        )
    end
    family_counts = Dict(
        family => count(problem -> problem.family_id == family, problems) for family in (
            "CURVED-CHAIN",
            "NEAR-RANK-DEFICIENT",
            "TANGENT-CIRCLE-LINE",
            "MULTIROOT-WARPED",
        )
    )
    all(==(2), values(family_counts)) || throw(
        DiscoveryGateError(:stageb_t0_corpus_drift, "Stage-B T0 family counts drifted"),
    )
    sum(size(problem.gold_configurations, 2) for problem in problems) == 24 || throw(
        DiscoveryGateError(
            :stageb_t0_corpus_drift,
            "Stage-B T0 must contain 24 assessor configurations",
        ),
    )
    sum(length(problem.gold_targets) for problem in problems) == 16 || throw(
        DiscoveryGateError(
            :stageb_t0_corpus_drift,
            "Stage-B T0 must contain 16 assessor targets",
        ),
    )
    return problems
end

_stageb_t0_proposal_domain(problem::DirectAnalyticProblem) =
    truth_blind_domain((;
        dimension=problem.dimension,
        lower_bounds=Tuple(problem.lower_bounds),
        upper_bounds=Tuple(problem.upper_bounds),
    ))

function stageb_t0_problem_with_proposals(
    problem::DirectAnalyticProblem,
    proposals::AbstractMatrix{<:Real},
)
    return t0_problem_with_proposals(problem, proposals)
end

function _stageb_t0_artifact_path(root, case_index)
    return joinpath(
        root,
        "case-$(lpad(case_index, 2, '0'))",
        "replicate-01-d0-iid-all.json",
    )
end

function _validate_stageb_t0_registration(path, authority)
    isfile(path) || throw(
        DiscoveryGateError(
            :missing_stageb_t0_preregistration,
            "Stage-B T0 preregistration is absent",
        ),
    )
    document = JSON3.read(read(path, String), Dict{String,Any})
    get(document, "schema_version", nothing) ==
        "geotarget.discovery-stageb-t0-preregistration/v1" || throw(
        DiscoveryGateError(
            :invalid_stageb_t0_preregistration,
            "unexpected Stage-B T0 preregistration schema",
        ),
    )
    get(document, "materialization_authorized", false) === true || throw(
        DiscoveryGateError(
            :stageb_t0_materialization_not_authorized,
            "Stage-B T0 materialization is disabled",
        ),
    )
    get(document, "outcome_execution_authorized", true) === false || throw(
        DiscoveryGateError(
            :invalid_stageb_t0_preregistration,
            "input preregistration must not authorize outcomes",
        ),
    )
    get(document, "nonpromotional_t0", false) === true || throw(
        DiscoveryGateError(
            :invalid_stageb_t0_preregistration,
            "Stage-B T0 must remain nonpromotional",
        ),
    )
    get(document, "local_freeze_sha256", nothing) == authority.freeze_sha256 || throw(
        DiscoveryGateError(
            :invalid_stageb_t0_preregistration,
            "local freeze hash differs",
        ),
    )
    parse(UInt64, String(get(document, "root_seed", ""))) == STAGEB_T0_ROOT_SEED || throw(
        DiscoveryGateError(:invalid_stageb_t0_preregistration, "root seed differs"),
    )
    get(document, "seed_namespace", nothing) == STAGEB_T0_SEED_NAMESPACE || throw(
        DiscoveryGateError(:invalid_stageb_t0_preregistration, "seed namespace differs"),
    )
    get(document, "case_count", nothing) == STAGEB_T0_CASE_COUNT || throw(
        DiscoveryGateError(:invalid_stageb_t0_preregistration, "case count differs"),
    )
    get(document, "replicate_count", nothing) == STAGEB_T0_REPLICATE_COUNT || throw(
        DiscoveryGateError(:invalid_stageb_t0_preregistration, "replicate count differs"),
    )
    get(document, "proposal_artifact_count", nothing) == STAGEB_T0_PROPOSAL_COUNT || throw(
        DiscoveryGateError(:invalid_stageb_t0_preregistration, "proposal count differs"),
    )
    execution = get(document, "execution_contract", nothing)
    execution isa AbstractDict &&
        GeoTargetCore.canonical_json(execution) ==
        GeoTargetCore.canonical_json(STAGEB_T0_EXECUTION_CONTRACT) || throw(
        DiscoveryGateError(:invalid_stageb_t0_preregistration, "execution contract differs"),
    )
    get(document, "method", nothing) == ExperimentDisc001._METHOD_WIRE[STAGEB_T0_METHOD] ||
        throw(DiscoveryGateError(:invalid_stageb_t0_preregistration, "method differs"))
    get(document, "initial_prefix_columns", nothing) == [1, STAGEB_T0_INITIAL_PREFIX] ||
        throw(DiscoveryGateError(:invalid_stageb_t0_preregistration, "prefix differs"))
    get(document, "continuation_columns", nothing) ==
        [first(STAGEB_T0_CONTINUATION), last(STAGEB_T0_CONTINUATION)] || throw(
        DiscoveryGateError(:invalid_stageb_t0_preregistration, "continuation differs"),
    )
    cases = get(document, "case_sources", nothing)
    cases isa AbstractVector && length(cases) == STAGEB_T0_CASE_COUNT || throw(
        DiscoveryGateError(:invalid_stageb_t0_preregistration, "case sources differ"),
    )
    for (case_index, registered) in enumerate(cases)
        recipe = STAGEB_T0_RECIPE[case_index]
        get(registered, "formal_case_id", nothing) == recipe.formal_case_id &&
            get(registered, "path", nothing) == recipe.source &&
            get(registered, "index", nothing) == recipe.source_index || throw(
            DiscoveryGateError(
                :invalid_stageb_t0_preregistration,
                "case source differs at case $case_index",
            ),
        )
    end
    bindings = get(document, "upstream_bindings", nothing)
    bindings isa AbstractDict || throw(
        DiscoveryGateError(:invalid_stageb_t0_preregistration, "upstream bindings absent"),
    )
    for name in ("stagea_decision", "weak_geometry_source", "weak_geometry_test")
        binding = get(bindings, name, nothing)
        binding isa AbstractDict || throw(
            DiscoveryGateError(
                :invalid_stageb_t0_preregistration,
                "upstream binding $name is absent",
            ),
        )
        relative = get(binding, "path", nothing)
        expected = get(binding, "sha256", nothing)
        relative isa AbstractString && expected isa AbstractString || throw(
            DiscoveryGateError(
                :invalid_stageb_t0_preregistration,
                "upstream binding $name is malformed",
            ),
        )
        source = joinpath(REPOSITORY_ROOT, split(String(relative), '/')...)
        isfile(source) && ExperimentDisc001._file_sha256(source) == expected || throw(
            DiscoveryGateError(:stageb_t0_source_drift, "upstream binding changed: $name"),
        )
    end
    source_hashes = get(document, "source_sha256", nothing)
    source_hashes isa AbstractDict && !isempty(source_hashes) || throw(
        DiscoveryGateError(:invalid_stageb_t0_preregistration, "source map is absent"),
    )
    Set(String.(keys(source_hashes))) == STAGEB_T0_REQUIRED_SOURCE_PATHS || throw(
        DiscoveryGateError(
            :invalid_stageb_t0_preregistration,
            "required Stage-B T0 source set differs",
        ),
    )
    for (relative, expected) in source_hashes
        source = joinpath(REPOSITORY_ROOT, split(String(relative), '/')...)
        isfile(source) && ExperimentDisc001._file_sha256(source) == expected || throw(
            DiscoveryGateError(
                :stageb_t0_source_drift,
                "preregistered Stage-B T0 source changed: $relative",
            ),
        )
    end
    return document
end

function _stageb_t0_git_clean()
    status = strip(read(`git -C $REPOSITORY_ROOT status --porcelain`, String))
    isempty(status) || throw(
        DiscoveryGateError(
            :dirty_stageb_t0_materialization,
            "Stage-B T0 materialization needs a clean tree",
        ),
    )
    return readchomp(`git -C $REPOSITORY_ROOT rev-parse HEAD`)
end

function stageb_t0_materialization_preflight(;
    freeze_path::AbstractString=ExperimentDisc001.DEFAULT_CHAMPION_FREEZE_PATH,
    preregistration_path::AbstractString=DEFAULT_STAGEB_T0_PREREGISTRATION_PATH,
    proposal_root::AbstractString=DEFAULT_STAGEB_T0_PROPOSAL_ROOT,
    input_manifest_path::AbstractString=DEFAULT_STAGEB_T0_INPUT_MANIFEST_PATH,
)
    authority = materialization_preflight(freeze_path)
    registration = _validate_stageb_t0_registration(preregistration_path, authority)
    problems = stageb_t0_problems()
    destinations = [
        _stageb_t0_artifact_path(abspath(proposal_root), case_index) for
        case_index in eachindex(problems)
    ]
    length(destinations) == STAGEB_T0_PROPOSAL_COUNT || error("proposal count drifted")
    any(ispath, destinations) && throw(
        DiscoveryGateError(
            :stageb_t0_input_already_exists,
            "one or more Stage-B T0 proposal files exist",
        ),
    )
    ispath(input_manifest_path) && throw(
        DiscoveryGateError(
            :stageb_t0_input_already_exists,
            "Stage-B T0 input manifest already exists",
        ),
    )
    return (;
        authority,
        registration,
        problems,
        destinations,
        preregistration_sha256=ExperimentDisc001._file_sha256(preregistration_path),
    )
end

function _assert_truth_free_artifact(artifact)
    metadata = JSON3.read(artifact.metadata_json, Dict{String,Any})
    forbidden = Set((
        "case_id",
        "family_id",
        "formal_case_id",
        "gold_configurations",
        "gold_targets",
        "instance_id",
        "source_index",
        "target_count",
    ))
    function inspect(value)
        if value isa AbstractDict
            for (key, child) in value
                String(key) in forbidden && throw(
                    DiscoveryGateError(
                        :truth_leak,
                        "proposal artifact metadata contains $(String(key))",
                    ),
                )
                inspect(child)
            end
        elseif value isa AbstractVector
            foreach(inspect, value)
        end
    end
    inspect(metadata)
    return artifact
end

function _column_slice_sha256(artifact, columns::UnitRange{Int})
    bits = Any[
        Any[
            lowercase(string(reinterpret(UInt64, artifact.coordinates[row, column]); base=16, pad=16))
            for row in axes(artifact.coordinates, 1)
        ] for column in columns
    ]
    document = Dict{String,Any}(
        "artifact_sha256" => artifact.sha256,
        "column_range" => [first(columns), last(columns)],
        "coordinate_float64_bits_by_column" => bits,
        "lane_schedule" => String.(artifact.lane_schedule[columns]),
        "source_columns" => collect(artifact.source_columns[columns]),
    )
    return bytes2hex(sha256(codeunits(GeoTargetCore.canonical_json(document))))
end

function _write_json_exclusive(path::AbstractString, document)
    destination = abspath(path)
    ispath(destination) && throw(
        DiscoveryGateError(
            :stageb_t0_input_already_exists,
            "refusing to overwrite Stage-B T0 input manifest",
        ),
    )
    mkpath(dirname(destination))
    stream = Base.Filesystem.open(
        destination,
        Base.JL_O_WRONLY | Base.JL_O_CREAT | Base.JL_O_EXCL,
        0o644,
    )
    try
        write(stream, GeoTargetCore.canonical_json(document), "\n")
    finally
        close(stream)
    end
    return destination
end

"""Materialize eight fresh D0 maximum matrices and their frozen input manifest once."""
function materialize_stageb_t0_inputs(;
    freeze_path::AbstractString=ExperimentDisc001.DEFAULT_CHAMPION_FREEZE_PATH,
    preregistration_path::AbstractString=DEFAULT_STAGEB_T0_PREREGISTRATION_PATH,
    proposal_root::AbstractString=DEFAULT_STAGEB_T0_PROPOSAL_ROOT,
    input_manifest_path::AbstractString=DEFAULT_STAGEB_T0_INPUT_MANIFEST_PATH,
)
    revision = _stageb_t0_git_clean()
    preflight = stageb_t0_materialization_preflight(
        ; freeze_path, preregistration_path, proposal_root, input_manifest_path,
    )
    source_document = _stageb_t0_source_document()
    cases = Any[]
    for (case_index, problem) in enumerate(preflight.problems)
        recipe = STAGEB_T0_RECIPE[case_index]
        seed = derive_seed(
            STAGEB_T0_ROOT_SEED,
            STAGEB_T0_METHOD,
            case_index,
            STAGEB_T0_REPLICATE_COUNT,
            STAGEB_T0_SEED_NAMESPACE,
        )
        destination = _stageb_t0_artifact_path(abspath(proposal_root), case_index)
        artifact = materialize_stream_once(
            preflight.authority,
            STAGEB_T0_METHOD,
            _stageb_t0_proposal_domain(problem),
            destination;
            replicate_seed=seed,
        )
        _assert_truth_free_artifact(artifact)
        all(==(:iid), artifact.lane_schedule) || throw(
            DiscoveryGateError(:stageb_t0_source_drift, "D0 emitted a non-IID lane"),
        )
        prefix_audit = static_prefix_audit(artifact)
        prefix_audit.valid || error("Stage-B T0 maximum-prefix audit failed")
        source = source_document["instances"][recipe.source_index]
        proposal = Dict{String,Any}(
            "artifact_sha256" => artifact.sha256,
            "continuation_columns" => [
                first(STAGEB_T0_CONTINUATION),
                last(STAGEB_T0_CONTINUATION),
            ],
            "continuation_sha256" => _column_slice_sha256(
                artifact,
                STAGEB_T0_CONTINUATION,
            ),
            "file_sha256" => ExperimentDisc001._file_sha256(destination),
            "initial_prefix_columns" => [1, STAGEB_T0_INITIAL_PREFIX],
            "initial_prefix_sha256" => _column_slice_sha256(
                artifact,
                1:STAGEB_T0_INITIAL_PREFIX,
            ),
            "lane_schedule" => "IID at all 128 launch ordinals",
            "maximum_prefix_sha256" => prefix_audit.maximum_sha256,
            "method" => ExperimentDisc001._METHOD_WIRE[STAGEB_T0_METHOD],
            "path" => ExperimentDisc001._repository_relative(destination),
            "replicate" => STAGEB_T0_REPLICATE_COUNT,
            "replicate_seed" => string(seed),
            "truth_free_metadata" => true,
        )
        push!(cases, Dict{String,Any}(
            "case_index" => case_index,
            "configuration_count" => size(problem.gold_configurations, 2),
            "dimension" => problem.dimension,
            "family_id" => problem.family_id,
            "formal_case_id" => recipe.formal_case_id,
            "instance_id" => problem.instance_id,
            "parameters" => _parameter_document(problem.parameters),
            "proposal" => proposal,
            "residual_dimension" => problem.residual_dimension,
            "source" => Dict{String,Any}(
                "index" => recipe.source_index,
                "parameters_sha256" => source["parameters_checksum"],
                "path" => recipe.source,
                "replay_checksum" => replay_checksum(problem),
            ),
            "strata" => String.(problem.strata),
            "target_count" => length(problem.gold_targets),
        ))
    end
    registration = preflight.registration
    bindings = registration["upstream_bindings"]
    document = Dict{String,Any}(
        "case_count" => STAGEB_T0_CASE_COUNT,
        "cases" => cases,
        "execution_contract" => registration["execution_contract"],
        "experiment_id" => "EXP-DISC-001",
        "lab_confirmation_512_768" => false,
        "local_freeze" => Dict{String,Any}(
            "path" => ExperimentDisc001._repository_relative(freeze_path),
            "sha256" => preflight.authority.freeze_sha256,
        ),
        "method" => ExperimentDisc001._METHOD_WIRE[STAGEB_T0_METHOD],
        "nonpromotional_t0" => true,
        "partition" => "development",
        "prefixes" => Dict{String,Any}(
            "continuation" => [first(STAGEB_T0_CONTINUATION), last(STAGEB_T0_CONTINUATION)],
            "initial" => [1, STAGEB_T0_INITIAL_PREFIX],
            "maximum" => MATRIX_COLUMN_COUNT,
        ),
        "preregistration" => Dict{String,Any}(
            "path" => ExperimentDisc001._repository_relative(preregistration_path),
            "sha256" => preflight.preregistration_sha256,
        ),
        "proposal_count" => STAGEB_T0_PROPOSAL_COUNT,
        "replicate_count" => STAGEB_T0_REPLICATE_COUNT,
        "revision" => revision,
        "root_seed" => string(STAGEB_T0_ROOT_SEED),
        "schema_version" => "geotarget.discovery-stageb-t0-input/v1",
        "seed_namespace" => STAGEB_T0_SEED_NAMESPACE,
        "slice_digest_contract" =>
            "sha256(canonical_json({artifact_sha256,column_range,coordinate_float64_bits_by_column,lane_schedule,source_columns})); Float64 bits are lowercase 16-hex strings in column-major outer order",
        "source_manifest" => Dict{String,Any}(
            "path" => STAGEB_T0_SOURCE_MANIFEST,
            "sha256" => ExperimentDisc001._file_sha256(joinpath(
                REPOSITORY_ROOT,
                split(STAGEB_T0_SOURCE_MANIFEST, '/')...,
            )),
        ),
        "stage" => "stage-b-weak-geometry-t0",
        "stagea_decision" => bindings["stagea_decision"],
        "target_count" => sum(case["target_count"] for case in cases),
        "weak_geometry" => Dict{String,Any}(
            "source" => bindings["weak_geometry_source"],
            "test" => bindings["weak_geometry_test"],
        ),
    )
    _write_json_exclusive(input_manifest_path, document)
    return document
end

export DEFAULT_STAGEB_T0_INPUT_MANIFEST_PATH,
    DEFAULT_STAGEB_T0_PREREGISTRATION_PATH,
    DEFAULT_STAGEB_T0_PROPOSAL_ROOT,
    STAGEB_T0_CASE_COUNT,
    STAGEB_T0_CONTINUATION,
    STAGEB_T0_EXECUTION_CONTRACT,
    STAGEB_T0_INITIAL_PREFIX,
    STAGEB_T0_METHOD,
    STAGEB_T0_PROPOSAL_COUNT,
    STAGEB_T0_REQUIRED_SOURCE_PATHS,
    STAGEB_T0_RECIPE,
    STAGEB_T0_REPLICATE_COUNT,
    STAGEB_T0_ROOT_SEED,
    STAGEB_T0_SEED_NAMESPACE,
    STAGEB_T0_SOURCE_INDICES,
    STAGEB_T0_SOURCE_MANIFEST,
    materialize_stageb_t0_inputs,
    stageb_t0_materialization_preflight,
    stageb_t0_problem_with_proposals,
    stageb_t0_problems

end
