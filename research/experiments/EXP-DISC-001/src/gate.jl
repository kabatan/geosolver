const _ORIGINAL_CARD_PATH = joinpath(EXPERIMENT_ROOT, "..", "EXP-DISC-001.json")
const _A1_PATH = joinpath(EXPERIMENT_ROOT, "current-policy-amendment.json")
const _A2_PATH = joinpath(EXPERIMENT_ROOT, "qmc-prefix-amendment.json")
const _A3_PATH = joinpath(EXPERIMENT_ROOT, "local-champion-dependency-amendment.json")
const DEFAULT_CHAMPION_FREEZE_PATH = joinpath(
    EXPERIMENT_ROOT,
    "local-champion-freeze-record.json",
)
const _COMPILER_SOURCE_PATH = joinpath(
    REPOSITORY_ROOT,
    "julia",
    "GeoTargetCore",
    "src",
    "compiler.jl",
)

struct DiscoveryGateError <: Exception
    code::Symbol
    message::String
end

Base.showerror(io::IO, error::DiscoveryGateError) =
    print(io, "EXP-DISC-001 gate ", error.code, ": ", error.message)

_file_sha256(path::AbstractString) = bytes2hex(sha256(read(path)))
_is_sha256_text(value::AbstractString) = occursin(r"^[0-9a-f]{64}$", String(value))

function preregistration_bindings()
    paths = (
        "original" => _ORIGINAL_CARD_PATH,
        "a1" => _A1_PATH,
        "a2" => _A2_PATH,
        "a3" => _A3_PATH,
    )
    for (label, path) in paths
        isfile(path) || throw(
            DiscoveryGateError(
                :missing_preregistration,
                "$label preregistration file is absent: $path",
            ),
        )
    end
    return Dict{String,String}(label => _file_sha256(path) for (label, path) in paths)
end

struct _MaterializationAuthority
    freeze_path::String
    freeze_sha256::String
    preregistration_sha256::Dict{String,String}
    local_source_sha256::Dict{String,String}
    local_options_sha256::String
    confirmation_contract_sha256::String

    function _MaterializationAuthority(
        ::Val{:validated},
        freeze_path,
        freeze_sha256,
        preregistration_sha256,
        local_source_sha256,
        local_options_sha256,
        confirmation_contract_sha256,
    )
        return new(
            String(freeze_path),
            String(freeze_sha256),
            Dict{String,String}(preregistration_sha256),
            Dict{String,String}(local_source_sha256),
            String(local_options_sha256),
            String(confirmation_contract_sha256),
        )
    end
end

function _required_object(parent, key::String, context::AbstractString)
    haskey(parent, key) || throw(
        DiscoveryGateError(:invalid_champion_freeze, "$context lacks required key $key"),
    )
    value = parent[key]
    value isa AbstractDict || throw(
        DiscoveryGateError(:invalid_champion_freeze, "$context.$key must be an object"),
    )
    return value
end

function _required_string(parent, key::String, context::AbstractString)
    haskey(parent, key) || throw(
        DiscoveryGateError(:invalid_champion_freeze, "$context lacks required key $key"),
    )
    value = parent[key]
    value isa AbstractString && !isempty(value) || throw(
        DiscoveryGateError(
            :invalid_champion_freeze,
            "$context.$key must be a nonempty string",
        ),
    )
    return String(value)
end

function _validate_preregistration_bindings(record)
    expected = preregistration_bindings()
    observed_raw = _required_object(record, "preregistration_sha256", "freeze")
    Set(String.(keys(observed_raw))) == Set(keys(expected)) || throw(
        DiscoveryGateError(
            :preregistration_binding_mismatch,
            "freeze record must bind exactly original, a1, a2 and a3",
        ),
    )
    for (label, digest) in expected
        observed = _required_string(observed_raw, label, "freeze.preregistration_sha256")
        observed == digest || throw(
            DiscoveryGateError(
                :preregistration_binding_mismatch,
                "$label SHA-256 differs from the immutable preregistration bytes",
            ),
        )
    end
    return expected
end

function _validate_source_bindings(selected)
    source_raw = _required_object(selected, "source_sha256", "freeze.selected_local_solver")
    isempty(source_raw) && throw(
        DiscoveryGateError(
            :invalid_champion_freeze,
            "selected local solver must bind at least one source file",
        ),
    )
    result = Dict{String,String}()
    for (raw_path, raw_digest) in source_raw
        path = String(raw_path)
        digest = raw_digest isa AbstractString ? String(raw_digest) : ""
        isempty(path) && throw(
            DiscoveryGateError(:invalid_champion_freeze, "local source path is empty"),
        )
        occursin("\\", path) && throw(
            DiscoveryGateError(
                :invalid_champion_freeze,
                "local source paths must use repository-relative forward slashes",
            ),
        )
        full_path = normpath(joinpath(REPOSITORY_ROOT, split(path, '/')...))
        relative = relpath(full_path, REPOSITORY_ROOT)
        separator = string(Base.Filesystem.path_separator)
        !(relative == ".." || startswith(relative, ".." * separator) || isabspath(relative)) || throw(
            DiscoveryGateError(:invalid_champion_freeze, "local source path escapes repository"),
        )
        isfile(full_path) || throw(
            DiscoveryGateError(:local_source_drift, "bound local source is absent: $path"),
        )
        _is_sha256_text(digest) || throw(
            DiscoveryGateError(
                :invalid_champion_freeze,
                "bound local source digest is not lowercase SHA-256 text: $path",
            ),
        )
        _file_sha256(full_path) == digest || throw(
            DiscoveryGateError(:local_source_drift, "bound local source changed: $path"),
        )
        result[path] = digest
    end
    return result
end

function _validate_options_binding(selected)
    canonical = _required_string(
        selected,
        "canonical_options_json",
        "freeze.selected_local_solver",
    )
    digest = _required_string(
        selected,
        "canonical_options_sha256",
        "freeze.selected_local_solver",
    )
    observed = bytes2hex(sha256(codeunits(canonical)))
    observed == digest || throw(
        DiscoveryGateError(
            :local_options_drift,
            "canonical local-options bytes do not match their bound SHA-256",
        ),
    )
    parsed = try
        JSON3.read(canonical, Dict{String,Any})
    catch error
        throw(
            DiscoveryGateError(
                :local_options_drift,
                "canonical local options are not a JSON object: $(sprint(showerror, error))",
            ),
        )
    end
    GeoTargetCore.canonical_json(parsed) == canonical || throw(
        DiscoveryGateError(
            :local_options_drift,
            "local options JSON is not in the canonical wire representation",
        ),
    )
    return digest
end

function _validate_version_bindings(record)
    versions = _required_object(record, "versions", "freeze")
    expected = Dict(
        "compiler" => _file_sha256(_COMPILER_SOURCE_PATH),
        "plugin_abi" => string(GeoTargetCore.CORE_ABI_VERSION),
        "problem_wire" => GeoTargetCore.PROBLEM_WIRE_VERSION,
        "solve_api" => string(GeoTargetCore.SOLVE_API_VERSION),
        "julia" => string(VERSION),
        "manifest_sha256" => _file_sha256(joinpath(EXPERIMENT_ROOT, "Manifest.toml")),
    )
    for (key, value) in expected
        observed = _required_string(versions, key, "freeze.versions")
        observed == value || throw(
            DiscoveryGateError(
                :version_binding_drift,
                "freeze.versions.$key differs from the materialization environment",
            ),
        )
    end
    return expected
end

function _validate_confirmation_contract(record)
    confirmation = _required_object(record, "confirmation", "freeze")
    primary = get(confirmation, "primary_precision_bits", nothing)
    reference = get(confirmation, "reference_precision_bits", nothing)
    residual = get(confirmation, "scaled_residual_tolerance", nothing)
    coordinate = get(confirmation, "coordinate_stability_tolerance", nothing)
    target = get(confirmation, "target_stability_tolerance", nothing)
    primary == 512 || throw(
        DiscoveryGateError(:confirmation_contract_drift, "primary precision must be 512 bits"),
    )
    reference == 768 || throw(
        DiscoveryGateError(:confirmation_contract_drift, "reference precision must be 768 bits"),
    )
    string(residual) == "1e-100" || throw(
        DiscoveryGateError(:confirmation_contract_drift, "residual gate must be encoded as 1e-100"),
    )
    string(coordinate) == "1e-100" || throw(
        DiscoveryGateError(:confirmation_contract_drift, "coordinate gate must be encoded as 1e-100"),
    )
    string(target) == "1e-100" || throw(
        DiscoveryGateError(:confirmation_contract_drift, "target gate must be encoded as 1e-100"),
    )
    return bytes2hex(sha256(codeunits(GeoTargetCore.canonical_json(confirmation))))
end

"""
Validate the A3 outcome-bound local champion record before any proposal bytes
or benchmark truth are materialized. Missing or drifting authority is a typed
stop; this function performs no sampling and creates no files.
"""
function materialization_preflight(
    freeze_path::AbstractString=DEFAULT_CHAMPION_FREEZE_PATH,
)
    path = abspath(freeze_path)
    isfile(path) || throw(
        DiscoveryGateError(
            :missing_local_champion_freeze,
            "A3 forbids proposal/input/outcome materialization until the outcome-bound " *
            "local champion freeze exists at $path",
        ),
    )
    record = try
        JSON3.read(read(path, String), Dict{String,Any})
    catch error
        throw(
            DiscoveryGateError(
                :invalid_champion_freeze,
                "cannot parse champion freeze: $(sprint(showerror, error))",
            ),
        )
    end
    get(record, "schema_version", nothing) == "exp-disc-001-local-champion-freeze/v1" ||
        throw(
            DiscoveryGateError(
                :invalid_champion_freeze,
                "unexpected champion freeze schema_version",
            ),
        )
    get(record, "experiment_id", nothing) == "EXP-DISC-001" || throw(
        DiscoveryGateError(:invalid_champion_freeze, "freeze record names another experiment"),
    )
    get(record, "status", nothing) == "frozen" || throw(
        DiscoveryGateError(:invalid_champion_freeze, "champion record is not frozen"),
    )
    preregistration = _validate_preregistration_bindings(record)
    selected = _required_object(record, "selected_local_solver", "freeze")
    source = _validate_source_bindings(selected)
    options = _validate_options_binding(selected)
    confirmation = _validate_confirmation_contract(record)
    upstream = _required_object(record, "upstream_decisions", "freeze")
    haskey(upstream, "EXP-LOCAL-003") && haskey(upstream, "EXP-LOCAL-004") || throw(
        DiscoveryGateError(
            :invalid_champion_freeze,
            "A3 requires explicit EXP-LOCAL-003 and EXP-LOCAL-004 decision bindings",
        ),
    )
    _validate_version_bindings(record)
    return _MaterializationAuthority(
        Val(:validated),
        path,
        _file_sha256(path),
        preregistration,
        source,
        options,
        confirmation,
    )
end
