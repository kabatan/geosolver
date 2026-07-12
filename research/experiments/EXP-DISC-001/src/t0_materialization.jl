const T0_ROOT_SEED = UInt64(743_883_355_336_172_525)
const T0_REPLICATE_COUNT = 1
const T0_METHODS = (
    D0_IID_ALL,
    D1_SOBOL_ALL,
    D_HALTON_ALL,
    D_CURRENT_COUNTER_HALTON,
    D2O_OWEN_ALL,
    D2M_MATOUSEK_ALL,
    D3_OWEN_MIXED,
)
const DEFAULT_T0_PREREGISTRATION_PATH = joinpath(
    EXPERIMENT_ROOT,
    "t0-preregistration.json",
)
const DEFAULT_T0_INPUT_MANIFEST_PATH = joinpath(
    EXPERIMENT_ROOT,
    "t0-input-manifest.json",
)
const DEFAULT_T0_PROPOSAL_ROOT = joinpath(EXPERIMENT_ROOT, "materialized", "t0")

function _repository_relative(path::AbstractString)
    absolute = abspath(path)
    relative = relpath(absolute, REPOSITORY_ROOT)
    separator = string(Base.Filesystem.path_separator)
    !(relative == ".." || startswith(relative, ".." * separator) || isabspath(relative)) ||
        throw(ArgumentError("path escapes repository: $path"))
    return replace(relative, '\\' => '/')
end

function _validate_t0_registration(
    path::AbstractString,
    authority::_MaterializationAuthority,
)
    isfile(path) || throw(
        DiscoveryGateError(:missing_t0_preregistration, "T0 preregistration is absent"),
    )
    document = JSON3.read(read(path, String), Dict{String,Any})
    get(document, "schema_version", nothing) == "geotarget.discovery-t0-preregistration/v1" ||
        throw(DiscoveryGateError(:invalid_t0_preregistration, "unexpected T0 schema"))
    get(document, "materialization_authorized", false) === true || throw(
        DiscoveryGateError(:t0_materialization_not_authorized, "T0 materialization is disabled"),
    )
    get(document, "outcome_execution_authorized", true) === false || throw(
        DiscoveryGateError(
            :invalid_t0_preregistration,
            "input preregistration must not authorize outcome execution",
        ),
    )
    get(document, "local_freeze_sha256", nothing) == authority.freeze_sha256 || throw(
        DiscoveryGateError(:invalid_t0_preregistration, "local freeze hash differs"),
    )
    parse(UInt64, String(get(document, "root_seed", ""))) == T0_ROOT_SEED || throw(
        DiscoveryGateError(:invalid_t0_preregistration, "T0 root seed differs"),
    )
    get(document, "replicate_count", nothing) == T0_REPLICATE_COUNT || throw(
        DiscoveryGateError(:invalid_t0_preregistration, "T0 replicate count differs"),
    )
    String.(get(document, "methods", Any[])) == [_METHOD_WIRE[method] for method in T0_METHODS] ||
        throw(DiscoveryGateError(:invalid_t0_preregistration, "T0 method order differs"))
    sources = get(document, "source_sha256", nothing)
    sources isa AbstractDict && !isempty(sources) || throw(
        DiscoveryGateError(:invalid_t0_preregistration, "T0 source bindings are absent"),
    )
    for (relative, expected) in sources
        source = joinpath(REPOSITORY_ROOT, split(String(relative), '/')...)
        isfile(source) && _file_sha256(source) == expected || throw(
            DiscoveryGateError(
                :t0_source_drift,
                "T0 preregistered source changed: $relative",
            ),
        )
    end
    return document
end

function _t0_parameter_document(parameters::MultiRootWarpedParams)
    result = Dict{String,Any}()
    for name in fieldnames(MultiRootWarpedParams)
        value = getfield(parameters, name)
        result[String(name)] = value isa UInt64 ? string(value) :
                               value isa Symbol ? String(value) : value
    end
    return result
end

function _t0_method_slug(method::DiscoveryMethod)
    return lowercase(strip(replace(_METHOD_WIRE[method], r"[^A-Za-z0-9]+" => "-"), '-'))
end

function _t0_artifact_path(root, case_index, method)
    return joinpath(
        root,
        "case-$(lpad(case_index, 2, '0'))",
        "replicate-01-$(_t0_method_slug(method)).json",
    )
end

function _t0_iid_service_document(method, artifact)
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

function _t0_git_clean()
    status = strip(read(`git -C $REPOSITORY_ROOT status --porcelain`, String))
    isempty(status) || throw(
        DiscoveryGateError(:dirty_t0_materialization, "T0 materialization needs a clean tree"),
    )
    return readchomp(`git -C $REPOSITORY_ROOT rev-parse HEAD`)
end

function t0_materialization_preflight(;
    freeze_path::AbstractString=DEFAULT_CHAMPION_FREEZE_PATH,
    preregistration_path::AbstractString=DEFAULT_T0_PREREGISTRATION_PATH,
    proposal_root::AbstractString=DEFAULT_T0_PROPOSAL_ROOT,
    input_manifest_path::AbstractString=DEFAULT_T0_INPUT_MANIFEST_PATH,
)
    authority = materialization_preflight(freeze_path)
    registration = _validate_t0_registration(preregistration_path, authority)
    problems = t0_problems()
    destinations = [
        _t0_artifact_path(abspath(proposal_root), case_index, method) for
        case_index in eachindex(problems), method in T0_METHODS
    ]
    any(ispath, destinations) && throw(
        DiscoveryGateError(:t0_input_already_exists, "one or more T0 proposal files exist"),
    )
    ispath(input_manifest_path) && throw(
        DiscoveryGateError(:t0_input_already_exists, "T0 input manifest already exists"),
    )
    return (;
        authority,
        registration,
        problems,
        destinations,
        preregistration_sha256=_file_sha256(preregistration_path),
    )
end

"""Materialize the one-replicate, non-promotional T0 source screen once."""
function materialize_t0_inputs(;
    freeze_path::AbstractString=DEFAULT_CHAMPION_FREEZE_PATH,
    preregistration_path::AbstractString=DEFAULT_T0_PREREGISTRATION_PATH,
    proposal_root::AbstractString=DEFAULT_T0_PROPOSAL_ROOT,
    input_manifest_path::AbstractString=DEFAULT_T0_INPUT_MANIFEST_PATH,
)
    revision = _t0_git_clean()
    preflight = t0_materialization_preflight(
        ; freeze_path, preregistration_path, proposal_root, input_manifest_path,
    )
    proposal_root = abspath(proposal_root)
    cases = Any[]
    for (case_index, problem) in enumerate(preflight.problems)
        domain = t0_proposal_domain(problem)
        proposal_records = Any[]
        for method in T0_METHODS
            seed = derive_seed(T0_ROOT_SEED, method, case_index, 1, "t0-proposal")
            destination = _t0_artifact_path(proposal_root, case_index, method)
            artifact = if method === D3_OWEN_MIXED
                materialize_stream_once(
                    preflight.authority,
                    method,
                    domain,
                    destination;
                    replicate_seed=seed,
                    iid_source_path=_t0_artifact_path(
                        proposal_root, case_index, D0_IID_ALL,
                    ),
                    rqmc_source_path=_t0_artifact_path(
                        proposal_root, case_index, D2O_OWEN_ALL,
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
            push!(proposal_records, Dict{String,Any}(
                "artifact_sha256" => artifact.sha256,
                "digital_net_minimal_t_by_prefix" => method in (
                    D1_SOBOL_ALL,
                    D2O_OWEN_ALL,
                    D2M_MATOUSEK_ALL,
                ) ? digital_net_prefix_audit(artifact) : nothing,
                "file_sha256" => _file_sha256(destination),
                "iid_service_audit" => _t0_iid_service_document(method, artifact),
                "method" => _METHOD_WIRE[method],
                "path" => _repository_relative(destination),
                "replicate_seed" => string(seed),
            ))
        end
        recipe = T0_RECIPE[case_index]
        push!(cases, Dict{String,Any}(
            "case_id" => recipe.case_id,
            "case_index" => case_index,
            "configuration_count" => size(problem.gold_configurations, 2),
            "dimension" => problem.dimension,
            "family_id" => problem.family_id,
            "instance_id" => problem.instance_id,
            "parameters" => _t0_parameter_document(problem.parameters),
            "proposals" => proposal_records,
            "residual_dimension" => problem.residual_dimension,
            "role" => recipe.role,
            "source" => Dict(
                "index" => recipe.source_index,
                "path" => recipe.source,
            ),
            "source_replay_checksum" => replay_checksum(problem),
            "target_count" => length(problem.gold_targets),
        ))
    end
    source_manifests = Any[
        Dict("path" => relative, "sha256" => _file_sha256(joinpath(
            REPOSITORY_ROOT, split(relative, '/')...,
        ))) for relative in unique([recipe.source for recipe in T0_RECIPE])
    ]
    document = Dict{String,Any}(
        "attempt_evaluation_limit" => 600,
        "callback_thresholds" => collect(CASE_TOTAL_CALLBACK_THRESHOLDS),
        "case_count" => length(cases),
        "cases" => cases,
        "experiment_id" => "EXP-DISC-001",
        "lab_confirmation_512_768" => false,
        "local_freeze" => Dict(
            "path" => _repository_relative(freeze_path),
            "sha256" => preflight.authority.freeze_sha256,
        ),
        "methods" => [_METHOD_WIRE[method] for method in T0_METHODS],
        "partition" => "development",
        "prefixes" => collect(CHECKPOINT_COLUMNS),
        "preregistration" => Dict(
            "path" => _repository_relative(preregistration_path),
            "sha256" => preflight.preregistration_sha256,
        ),
        "replicate_count" => T0_REPLICATE_COUNT,
        "revision" => revision,
        "root_seed" => string(T0_ROOT_SEED),
        "schema_version" => "geotarget.discovery-t0-input/v1",
        "source_manifests" => source_manifests,
        "stage" => "t0",
        "target_count" => sum(case["target_count"] for case in cases),
    )
    text = GeoTargetCore.canonical_json(document) * "\n"
    destination = abspath(input_manifest_path)
    ispath(destination) && throw(
        DiscoveryGateError(:t0_input_already_exists, "T0 input manifest already exists"),
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
