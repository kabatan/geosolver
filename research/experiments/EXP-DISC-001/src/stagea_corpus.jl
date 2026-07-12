module StageAInputs

using ExperimentDisc001
using GeoTargetBenchmarks
using GeoTargetCore
using JSON3

const REPOSITORY_ROOT = ExperimentDisc001.REPOSITORY_ROOT
const EXPERIMENT_ROOT = ExperimentDisc001.EXPERIMENT_ROOT
const STAGEA_SOURCE_MANIFEST =
    "research/experiments/EXP-LOCAL-004/t2-input-manifest.json"
const STAGEA_SOURCE_INDICES = Tuple(25:48)
const STAGEA_CASE_COUNT = 24
const STAGEA_ROOT_SEED = UInt64(13_263_594_411_351_949_634)
const STAGEA_REPLICATES = 10
const STAGEA_METHODS = (
    D0_IID_ALL,
    D1_SOBOL_ALL,
    D_HALTON_ALL,
    D_CURRENT_COUNTER_HALTON,
    D2O_OWEN_ALL,
    D2M_MATOUSEK_ALL,
    D3_OWEN_MIXED,
)
const STAGEA_RANDOMIZED_METHODS = (
    D0_IID_ALL,
    D_CURRENT_COUNTER_HALTON,
    D2O_OWEN_ALL,
    D2M_MATOUSEK_ALL,
    D3_OWEN_MIXED,
)
const STAGEA_DETERMINISTIC_METHODS = (D1_SOBOL_ALL, D_HALTON_ALL)
const STAGEA_CRITICAL_STRATA = ("S1", "S2", "S3", "S4", "S5", "S6")
const STAGEA_PROPOSAL_COUNT = STAGEA_CASE_COUNT * (
    length(STAGEA_RANDOMIZED_METHODS) * STAGEA_REPLICATES +
    length(STAGEA_DETERMINISTIC_METHODS)
)

const DEFAULT_STAGEA_PREREGISTRATION_PATH =
    joinpath(EXPERIMENT_ROOT, "stagea-preregistration.json")
const DEFAULT_STAGEA_INPUT_MANIFEST_PATH =
    joinpath(EXPERIMENT_ROOT, "stagea-input-manifest.json")
const DEFAULT_STAGEA_PROPOSAL_ROOT =
    joinpath(EXPERIMENT_ROOT, "materialized", "stagea")

const STAGEA_RECIPE = Tuple(
    (
        formal_case_id="EXP-DISC-001-A-$(lpad(case_index, 3, '0'))",
        source=STAGEA_SOURCE_MANIFEST,
        source_index=source_index,
    ) for (case_index, source_index) in enumerate(STAGEA_SOURCE_INDICES)
)

function _stagea_parameter_records()
    records = Any[]

    tangent_radii = (0.5, 1.0, 2.0, 1.0, 2.0, 0.5)
    tangent_ratios = (0.5, 0.9, 0.999, 0.9999, 0.999999, 0.99999999)
    for index in 1:6
        push!(records, TangentCircleLineParams(
            radius=tangent_radii[index],
            height_radius_ratio=tangent_ratios[index],
            instance_seed=10_500 + index,
            start_seed=20_500 + index,
            start_count=32,
        ))
    end

    dimensions = (2, 4, 8, 16, 4, 8)
    root_counts = (2, 4, 8, 4, 8, 4)
    separations = (0.1, 1.0e-3, 1.0e-6, 1.0e-3, 1.0e-6, 0.1)
    warps = (0.0, 0.25, 0.5, 0.75, 0.5, 0.25)
    conditions = (1.0, 1.0e4, 1.0e8, 1.0e12, 1.0e4, 1.0e8)
    for index in 1:6
        push!(records, MultiRootWarpedParams(
            dimension=dimensions[index],
            root_count=root_counts[index],
            minimum_separation=separations[index],
            warp=warps[index],
            condition=conditions[index],
            target_map=:z1_squared,
            coefficient_seed=10_600 + index,
            start_seed=20_600 + index,
            start_count=32,
        ))
    end

    guard_cases = (
        (:well_separated, 0.25),
        (:well_separated, 0.75),
        (:near_boundary, 1.0e-6),
        (:near_boundary, 1.0e-8),
        (:near_boundary, 1.0e-12),
        (:on_boundary, 0.0),
    )
    for index in 1:6
        boundary_case, guard_margin = guard_cases[index]
        push!(records, StrictGuardBoundaryParams(
            boundary_case=boundary_case,
            guard_margin=guard_margin,
            instance_seed=10_700 + index,
            start_seed=20_700 + index,
            start_count=32,
        ))
    end

    opaque_root_counts = (2, 3, 4, 6, 8, 3)
    opaque_loop_counts = (1, 4, 8, 16, 32, 64)
    opaque_phases = (-0.25, -0.1, 0.0, 0.1, 0.25, 0.4)
    opaque_mixings = (0.05, 0.1, 0.15, 0.2, 0.25, 0.1)
    for index in 1:6
        push!(records, OpaqueTranscendentalParams(
            root_count=opaque_root_counts[index],
            loop_count=opaque_loop_counts[index],
            phase=opaque_phases[index],
            mixing=opaque_mixings[index],
            instance_seed=10_800 + index,
            start_seed=20_800 + index,
            start_count=32,
        ))
    end

    length(records) == STAGEA_CASE_COUNT || error("Stage-A parameter grid drifted")
    return records
end

function _stagea_source_document()
    path = joinpath(REPOSITORY_ROOT, split(STAGEA_SOURCE_MANIFEST, '/')...)
    document = JSON3.read(read(path, String), Dict{String,Any})
    get(document, "schema_version", nothing) == "exp-local-004-t2-input/v1" || throw(
        DiscoveryGateError(:stagea_corpus_drift, "unexpected source manifest schema"),
    )
    return document
end

function _verify_stagea_problem(problem, source, recipe, case_index)
    get(source, "instance_id", nothing) == problem.instance_id || throw(
        DiscoveryGateError(:stagea_corpus_drift, "instance ID drifted at case $case_index"),
    )
    get(source, "family_id", nothing) == problem.family_id || throw(
        DiscoveryGateError(:stagea_corpus_drift, "family drifted at case $case_index"),
    )
    get(source, "dimension", nothing) == problem.dimension || throw(
        DiscoveryGateError(:stagea_corpus_drift, "dimension drifted at case $case_index"),
    )
    get(source, "residual_dimension", nothing) == problem.residual_dimension || throw(
        DiscoveryGateError(
            :stagea_corpus_drift,
            "residual dimension drifted at case $case_index",
        ),
    )
    get(source, "replay_checksum", nothing) == replay_checksum(problem) || throw(
        DiscoveryGateError(:stagea_corpus_drift, "replay drifted at case $case_index"),
    )
    get(source, "configuration_count", nothing) == size(problem.gold_configurations, 2) ||
        throw(DiscoveryGateError(
            :stagea_corpus_drift,
            "configuration count drifted at case $case_index",
        ))
    get(source, "target_count", nothing) == length(problem.gold_targets) || throw(
        DiscoveryGateError(:stagea_corpus_drift, "target count drifted at case $case_index"),
    )
    String.(get(source, "strata", Any[])) == collect(String.(problem.strata)) || throw(
        DiscoveryGateError(:stagea_corpus_drift, "strata drifted at case $case_index"),
    )
    recipe.source_index == case_index + 24 || throw(
        DiscoveryGateError(:stagea_corpus_drift, "source ordinal drifted"),
    )
    verify_replay_material(problem) || throw(
        DiscoveryGateError(:stagea_corpus_drift, "case $case_index is not replayable"),
    )
    all(isfinite, problem.lower_bounds) && all(isfinite, problem.upper_bounds) || throw(
        DiscoveryGateError(:stagea_corpus_drift, "Stage-A requires finite proposal bounds"),
    )
    return problem
end

"""Rebuild and verify formal development cases A-001 through A-024."""
function stagea_problems()
    source = _stagea_source_document()
    instances = source["instances"]
    records = _stagea_parameter_records()
    problems = DirectAnalyticProblem[]
    for case_index in 1:STAGEA_CASE_COUNT
        recipe = STAGEA_RECIPE[case_index]
        problem = generate(records[case_index])
        push!(
            problems,
            _verify_stagea_problem(
                problem,
                instances[recipe.source_index],
                recipe,
                case_index,
            ),
        )
    end
    sum(length(problem.gold_targets) for problem in problems) == 64 || throw(
        DiscoveryGateError(:stagea_corpus_drift, "Stage-A must expose 64 assessor targets"),
    )
    Set(problem.family_id for problem in problems) == Set((
        "TANGENT-CIRCLE-LINE",
        "MULTIROOT-WARPED",
        "STRICT-GUARD-BOUNDARY",
        "OPAQUE-TRANSCENDENTAL-C0",
    )) || throw(DiscoveryGateError(:stagea_corpus_drift, "Stage-A family grid drifted"))
    return problems
end

stagea_proposal_domain(problem::DirectAnalyticProblem) =
    truth_blind_domain((;
        dimension=problem.dimension,
        lower_bounds=Tuple(problem.lower_bounds),
        upper_bounds=Tuple(problem.upper_bounds),
    ))

function stagea_problem_with_proposals(
    problem::DirectAnalyticProblem,
    proposals::AbstractMatrix{<:Real},
)
    return t0_problem_with_proposals(problem, proposals)
end

_stagea_replicates(method::DiscoveryMethod) =
    method in STAGEA_RANDOMIZED_METHODS ? (1:STAGEA_REPLICATES) : (1:1)

function _stagea_method_counts()
    return Dict{String,Any}(
        ExperimentDisc001._METHOD_WIRE[method] => length(_stagea_replicates(method)) for
        method in STAGEA_METHODS
    )
end

function _stagea_method_slug(method::DiscoveryMethod)
    wire = ExperimentDisc001._METHOD_WIRE[method]
    return lowercase(strip(replace(wire, r"[^A-Za-z0-9]+" => "-"), '-'))
end

function _stagea_artifact_path(root, case_index, method, replicate)
    return joinpath(
        root,
        "case-$(lpad(case_index, 2, '0'))",
        "replicate-$(lpad(replicate, 2, '0'))-$(_stagea_method_slug(method)).json",
    )
end

function _stagea_iid_service_document(method, artifact)
    method in (D0_IID_ALL, D_CURRENT_COUNTER_HALTON, D3_OWEN_MIXED) || return nothing
    audit = iid_bounded_gap_audit(artifact.lane_schedule; cadence=4)
    return Dict{String,Any}(
        "bounded_gap" => audit.bounded_gap,
        "cadence" => audit.cadence,
        "iid_count" => audit.iid_count,
        "maximum_gap" => audit.maximum_gap,
        "starvation_count" => audit.starvation_count,
        "violation_prefixes" => collect(audit.violation_prefixes),
    )
end

function _validate_stagea_registration(path, authority)
    isfile(path) || throw(
        DiscoveryGateError(:missing_stagea_preregistration, "Stage-A preregistration is absent"),
    )
    document = JSON3.read(read(path, String), Dict{String,Any})
    get(document, "schema_version", nothing) ==
        "geotarget.discovery-stagea-preregistration/v1" || throw(
        DiscoveryGateError(:invalid_stagea_preregistration, "unexpected Stage-A schema"),
    )
    get(document, "materialization_authorized", false) === true || throw(
        DiscoveryGateError(
            :stagea_materialization_not_authorized,
            "Stage-A materialization is disabled",
        ),
    )
    get(document, "outcome_execution_authorized", true) === false || throw(
        DiscoveryGateError(
            :invalid_stagea_preregistration,
            "input preregistration must not authorize outcomes",
        ),
    )
    get(document, "local_freeze_sha256", nothing) == authority.freeze_sha256 || throw(
        DiscoveryGateError(:invalid_stagea_preregistration, "local freeze hash differs"),
    )
    parse(UInt64, String(get(document, "root_seed", ""))) == STAGEA_ROOT_SEED || throw(
        DiscoveryGateError(:invalid_stagea_preregistration, "root seed differs"),
    )
    get(document, "randomized_replicate_count", nothing) == STAGEA_REPLICATES || throw(
        DiscoveryGateError(:invalid_stagea_preregistration, "replicate count differs"),
    )
    get(document, "method_replicate_counts", nothing) == _stagea_method_counts() || throw(
        DiscoveryGateError(:invalid_stagea_preregistration, "method replicate counts differ"),
    )
    sources = get(document, "source_sha256", nothing)
    sources isa AbstractDict && !isempty(sources) || throw(
        DiscoveryGateError(:invalid_stagea_preregistration, "source bindings are absent"),
    )
    for (relative, expected) in sources
        path = joinpath(REPOSITORY_ROOT, split(String(relative), '/')...)
        isfile(path) && ExperimentDisc001._file_sha256(path) == expected || throw(
            DiscoveryGateError(:stagea_source_drift, "bound source changed: $relative"),
        )
    end
    registered_cases = get(document, "case_sources", nothing)
    registered_cases isa AbstractVector && length(registered_cases) == STAGEA_CASE_COUNT ||
        throw(DiscoveryGateError(:invalid_stagea_preregistration, "case sources differ"))
    for (case_index, registered) in enumerate(registered_cases)
        recipe = STAGEA_RECIPE[case_index]
        get(registered, "formal_case_id", nothing) == recipe.formal_case_id &&
            get(registered, "path", nothing) == recipe.source &&
            get(registered, "index", nothing) == recipe.source_index || throw(
            DiscoveryGateError(
                :invalid_stagea_preregistration,
                "case source differs at case $case_index",
            ),
        )
    end
    return document
end

function _stagea_git_clean()
    status = strip(read(`git -C $REPOSITORY_ROOT status --porcelain`, String))
    isempty(status) || throw(
        DiscoveryGateError(:dirty_stagea_materialization, "Stage-A needs a clean tree"),
    )
    return readchomp(`git -C $REPOSITORY_ROOT rev-parse HEAD`)
end

function stagea_materialization_preflight(;
    freeze_path::AbstractString=ExperimentDisc001.DEFAULT_CHAMPION_FREEZE_PATH,
    preregistration_path::AbstractString=DEFAULT_STAGEA_PREREGISTRATION_PATH,
    proposal_root::AbstractString=DEFAULT_STAGEA_PROPOSAL_ROOT,
    input_manifest_path::AbstractString=DEFAULT_STAGEA_INPUT_MANIFEST_PATH,
)
    authority = materialization_preflight(freeze_path)
    registration = _validate_stagea_registration(preregistration_path, authority)
    problems = stagea_problems()
    destinations = String[]
    for case_index in eachindex(problems), method in STAGEA_METHODS
        for replicate in _stagea_replicates(method)
            push!(
                destinations,
                _stagea_artifact_path(
                    abspath(proposal_root),
                    case_index,
                    method,
                    replicate,
                ),
            )
        end
    end
    length(destinations) == STAGEA_PROPOSAL_COUNT || error("proposal count drifted")
    any(ispath, destinations) && throw(
        DiscoveryGateError(
            :stagea_input_already_exists,
            "one or more Stage-A proposal files exist",
        ),
    )
    ispath(input_manifest_path) && throw(
        DiscoveryGateError(:stagea_input_already_exists, "Stage-A manifest already exists"),
    )
    return (;
        authority,
        registration,
        problems,
        destinations,
        preregistration_sha256=ExperimentDisc001._file_sha256(preregistration_path),
    )
end

function _parameter_document(parameters)
    value(item::Symbol) = String(item)
    value(item::UInt64) = string(item)
    value(item) = item
    return Dict{String,Any}(
        String(name) => value(getfield(parameters, name)) for
        name in fieldnames(typeof(parameters))
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

function _proposal_record(method, replicate, seed, destination, artifact)
    return Dict{String,Any}(
        "artifact_sha256" => artifact.sha256,
        "digital_net_minimal_t_by_prefix" => method in (
            D1_SOBOL_ALL,
            D2O_OWEN_ALL,
            D2M_MATOUSEK_ALL,
        ) ? digital_net_prefix_audit(artifact) : nothing,
        "file_sha256" => ExperimentDisc001._file_sha256(destination),
        "iid_service_audit" => _stagea_iid_service_document(method, artifact),
        "method" => ExperimentDisc001._METHOD_WIRE[method],
        "path" => ExperimentDisc001._repository_relative(destination),
        "replicate" => replicate,
        "replicate_seed" => string(seed),
    )
end

function _mixed_binding(record)
    return Dict{String,Any}(
        "artifact_sha256" => record["artifact_sha256"],
        "file_sha256" => record["file_sha256"],
        "path" => record["path"],
    )
end

"""Materialize the frozen 24-case, ten-replicate formal Stage-A inputs once."""
function materialize_stagea_inputs(;
    freeze_path::AbstractString=ExperimentDisc001.DEFAULT_CHAMPION_FREEZE_PATH,
    preregistration_path::AbstractString=DEFAULT_STAGEA_PREREGISTRATION_PATH,
    proposal_root::AbstractString=DEFAULT_STAGEA_PROPOSAL_ROOT,
    input_manifest_path::AbstractString=DEFAULT_STAGEA_INPUT_MANIFEST_PATH,
)
    revision = _stagea_git_clean()
    preflight = stagea_materialization_preflight(
        ; freeze_path, preregistration_path, proposal_root, input_manifest_path,
    )
    proposal_root = abspath(proposal_root)
    source_document = _stagea_source_document()
    cases = Any[]
    for (case_index, problem) in enumerate(preflight.problems)
        domain = stagea_proposal_domain(problem)
        proposal_records = Any[]
        records_by_key = Dict{Tuple{DiscoveryMethod,Int},Dict{String,Any}}()
        for method in STAGEA_METHODS, replicate in _stagea_replicates(method)
            seed = derive_seed(
                STAGEA_ROOT_SEED,
                method,
                case_index,
                replicate,
                "stagea-proposal",
            )
            destination = _stagea_artifact_path(
                proposal_root,
                case_index,
                method,
                replicate,
            )
            artifact = if method === D3_OWEN_MIXED
                materialize_stream_once(
                    preflight.authority,
                    method,
                    domain,
                    destination;
                    replicate_seed=seed,
                    iid_source_path=_stagea_artifact_path(
                        proposal_root,
                        case_index,
                        D0_IID_ALL,
                        replicate,
                    ),
                    rqmc_source_path=_stagea_artifact_path(
                        proposal_root,
                        case_index,
                        D2O_OWEN_ALL,
                        replicate,
                    ),
                )
            else
                materialize_stream_once(
                    preflight.authority,
                    method,
                    domain,
                    destination;
                    replicate_seed=seed,
                )
            end
            _assert_truth_free_artifact(artifact)
            record = _proposal_record(method, replicate, seed, destination, artifact)
            if method === D3_OWEN_MIXED
                record["mixed_sources"] = Dict{String,Any}(
                    "iid" => _mixed_binding(records_by_key[(D0_IID_ALL, replicate)]),
                    "rqmc" => _mixed_binding(records_by_key[(D2O_OWEN_ALL, replicate)]),
                )
            end
            records_by_key[(method, replicate)] = record
            push!(proposal_records, record)
        end
        recipe = STAGEA_RECIPE[case_index]
        source = source_document["instances"][recipe.source_index]
        push!(cases, Dict{String,Any}(
            "case_index" => case_index,
            "configuration_count" => size(problem.gold_configurations, 2),
            "dimension" => problem.dimension,
            "family_id" => problem.family_id,
            "formal_case_id" => recipe.formal_case_id,
            "instance_id" => problem.instance_id,
            "parameters" => _parameter_document(problem.parameters),
            "proposals" => proposal_records,
            "residual_dimension" => problem.residual_dimension,
            "source" => Dict("index" => recipe.source_index, "path" => recipe.source),
            "source_parameters_sha256" => source["parameters_checksum"],
            "source_replay_checksum" => replay_checksum(problem),
            "strata" => String.(problem.strata),
            "target_count" => length(problem.gold_targets),
        ))
    end
    document = Dict{String,Any}(
        "attempt_evaluation_limit" => 600,
        "callback_thresholds" => [600, 1_200, 2_400, 4_800],
        "case_count" => length(cases),
        "cases" => cases,
        "critical_strata" => collect(STAGEA_CRITICAL_STRATA),
        "experiment_id" => "EXP-DISC-001",
        "lab_confirmation_512_768" => false,
        "local_freeze" => Dict(
            "path" => ExperimentDisc001._repository_relative(freeze_path),
            "sha256" => preflight.authority.freeze_sha256,
        ),
        "method_replicate_counts" => _stagea_method_counts(),
        "methods" => [ExperimentDisc001._METHOD_WIRE[method] for method in STAGEA_METHODS],
        "partition" => "development",
        "prefixes" => collect(CHECKPOINT_COLUMNS),
        "preregistration" => Dict(
            "path" => ExperimentDisc001._repository_relative(preregistration_path),
            "sha256" => preflight.preregistration_sha256,
        ),
        "proposal_count" => STAGEA_PROPOSAL_COUNT,
        "randomized_replicate_count" => STAGEA_REPLICATES,
        "replicate_count" => STAGEA_REPLICATES,
        "revision" => revision,
        "root_seed" => string(STAGEA_ROOT_SEED),
        "schema_version" => "geotarget.discovery-stagea-input/v1",
        "source_manifests" => Any[Dict(
            "path" => STAGEA_SOURCE_MANIFEST,
            "sha256" => ExperimentDisc001._file_sha256(joinpath(
                REPOSITORY_ROOT,
                split(STAGEA_SOURCE_MANIFEST, '/')...,
            )),
        )],
        "stage" => "stage-a-source-ablation",
        "target_count" => sum(case["target_count"] for case in cases),
    )
    text = GeoTargetCore.canonical_json(document) * "\n"
    destination = abspath(input_manifest_path)
    ispath(destination) && throw(
        DiscoveryGateError(:stagea_input_already_exists, "Stage-A manifest already exists"),
    )
    stream = Base.Filesystem.open(
        destination,
        Base.JL_O_WRONLY | Base.JL_O_CREAT | Base.JL_O_EXCL,
        0o644,
    )
    try
        write(stream, text)
    finally
        close(stream)
    end
    return document
end

export DEFAULT_STAGEA_INPUT_MANIFEST_PATH,
    DEFAULT_STAGEA_PREREGISTRATION_PATH,
    DEFAULT_STAGEA_PROPOSAL_ROOT,
    STAGEA_CASE_COUNT,
    STAGEA_CRITICAL_STRATA,
    STAGEA_DETERMINISTIC_METHODS,
    STAGEA_METHODS,
    STAGEA_PROPOSAL_COUNT,
    STAGEA_RANDOMIZED_METHODS,
    STAGEA_RECIPE,
    STAGEA_REPLICATES,
    STAGEA_ROOT_SEED,
    materialize_stagea_inputs,
    stagea_materialization_preflight,
    stagea_problem_with_proposals,
    stagea_problems,
    stagea_proposal_domain

end
