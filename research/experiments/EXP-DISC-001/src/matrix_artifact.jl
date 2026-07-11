const MATRIX_SCHEMA_VERSION = "geotarget.discovery-proposal-matrix/v1"
const MATRIX_COLUMN_COUNT = 128
const CHECKPOINT_COLUMNS = (8, 16, 32, 64, 128)

@enum DiscoveryMethod::UInt8 begin
    D0_IID_ALL = 0
    D1_SOBOL_ALL = 1
    D_HALTON_ALL = 2
    D_CURRENT_COUNTER_HALTON = 3
    D2O_OWEN_ALL = 4
    D2M_MATOUSEK_ALL = 5
    D3_OWEN_MIXED = 6
end

const _METHOD_WIRE = Dict(
    D0_IID_ALL => "D0-IID-ALL",
    D1_SOBOL_ALL => "D1-SOBOL-ALL",
    D_HALTON_ALL => "D-HALTON-ALL",
    D_CURRENT_COUNTER_HALTON => "D-CURRENT-COUNTER-HALTON-MIX",
    D2O_OWEN_ALL => "D2O-RQMC-OWEN-ALL",
    D2M_MATOUSEK_ALL => "D2M-RQMC-MATOUSEK-ALL",
    D3_OWEN_MIXED => "D3-OWEN-MIXED-25IID-75RQMC",
)
const _WIRE_METHOD = Dict(value => key for (key, value) in _METHOD_WIRE)

struct ProposalDomain
    lower::Tuple
    upper::Tuple

    function ProposalDomain(lower, upper)
        lo = Tuple(Float64.(lower))
        hi = Tuple(Float64.(upper))
        !isempty(lo) && length(lo) == length(hi) || throw(
            ArgumentError("bounded discovery domain must have a positive dimension"),
        )
        all(isfinite, lo) && all(isfinite, hi) || throw(
            ArgumentError("bounded discovery limits must be finite"),
        )
        all(index -> lo[index] < hi[index], eachindex(lo)) || throw(
            ArgumentError("every bounded discovery interval must be strictly ordered"),
        )
        return new(lo, hi)
    end
end

function truth_blind_domain(case)
    # Keep this projection intentionally narrow: no family/instance identifier,
    # target, Gold configuration or saved-start field is observed here.
    dimension = getproperty(case, :dimension)
    lower = getproperty(case, :lower_bounds)
    upper = getproperty(case, :upper_bounds)
    length(lower) == dimension == length(upper) || throw(
        DimensionMismatch("truth-blind case bounds disagree with its dimension"),
    )
    return ProposalDomain(lower, upper)
end

struct ProposalMatrixArtifact
    method::DiscoveryMethod
    unit_points::Matrix{Float64}
    coordinates::Matrix{Float64}
    lane_schedule::Tuple{Vararg{Symbol}}
    source_columns::Tuple{Vararg{Int}}
    replicate_seed::UInt64
    metadata_json::String
    authority_sha256::String
    sha256::String

    function ProposalMatrixArtifact(
        method::DiscoveryMethod,
        unit_points::AbstractMatrix{<:Real},
        coordinates::AbstractMatrix{<:Real},
        lane_schedule,
        source_columns,
        replicate_seed::Integer,
        metadata::AbstractDict,
        authority_sha256::AbstractString;
        expected_sha256::Union{Nothing,AbstractString}=nothing,
    )
        unit = Matrix{Float64}(unit_points)
        points = Matrix{Float64}(coordinates)
        size(unit) == size(points) || throw(
            DimensionMismatch("unit and transformed proposal matrices differ in shape"),
        )
        size(unit, 1) > 0 && size(unit, 2) == MATRIX_COLUMN_COUNT || throw(
            DimensionMismatch(
                "proposal matrices must have positive dimension and $MATRIX_COLUMN_COUNT columns",
            ),
        )
        all(isfinite, unit) && all(isfinite, points) || throw(
            ArgumentError("proposal matrices must contain only finite Float64 values"),
        )
        all(value -> 0.0 <= value <= 1.0, unit) || throw(
            ArgumentError("unit proposal coordinates must lie in [0,1]"),
        )
        lanes = Tuple(Symbol.(lane_schedule))
        columns = Tuple(Int.(source_columns))
        length(lanes) == MATRIX_COLUMN_COUNT || throw(
            DimensionMismatch("lane schedule must have $MATRIX_COLUMN_COUNT entries"),
        )
        length(columns) == MATRIX_COLUMN_COUNT || throw(
            DimensionMismatch("source-column trace must have $MATRIX_COLUMN_COUNT entries"),
        )
        all(>(0), columns) || throw(ArgumentError("source columns must be one-based"))
        0 <= replicate_seed <= typemax(UInt64) || throw(
            ArgumentError("replicate seed must fit in UInt64"),
        )
        frozen_metadata = Dict{String,Any}(String(key) => value for (key, value) in metadata)
        metadata_json = GeoTargetCore.canonical_json(frozen_metadata)
        authority = String(authority_sha256)
        _is_sha256_text(authority) || throw(
            ArgumentError("authority SHA-256 must be lowercase hexadecimal text"),
        )
        provisional = new(
            method,
            unit,
            points,
            lanes,
            columns,
            UInt64(replicate_seed),
            metadata_json,
            authority,
            "",
        )
        digest = bytes2hex(sha256(codeunits(GeoTargetCore.canonical_json(
            artifact_document(provisional; include_sha256=false),
        ))))
        expected_sha256 === nothing || digest == String(expected_sha256) || throw(
            DiscoveryGateError(:matrix_checksum_mismatch, "proposal matrix checksum differs"),
        )
        return new(
            method,
            unit,
            points,
            lanes,
            columns,
            UInt64(replicate_seed),
            metadata_json,
            authority,
            digest,
        )
    end
end

artifact_sha256(artifact::ProposalMatrixArtifact) = artifact.sha256

_float64_hex(value::Float64) = lowercase(string(reinterpret(UInt64, value); base=16, pad=16))

function _hex_float64(value, context::AbstractString)
    value isa AbstractString && length(value) == 16 || throw(
        DiscoveryGateError(:invalid_matrix_artifact, "$context must be 16 hex digits"),
    )
    bits = try
        parse(UInt64, String(value); base=16)
    catch error
        throw(
            DiscoveryGateError(
                :invalid_matrix_artifact,
                "$context is not Float64 bits: $(sprint(showerror, error))",
            ),
        )
    end
    result = reinterpret(Float64, bits)
    isfinite(result) || throw(
        DiscoveryGateError(:invalid_matrix_artifact, "$context decodes to a nonfinite value"),
    )
    return result
end

function _matrix_bits(matrix::Matrix{Float64})
    return Any[
        Any[_float64_hex(matrix[row, column]) for row in axes(matrix, 1)] for
        column in axes(matrix, 2)
    ]
end

function _matrix_from_bits(raw, dimension::Int, columns::Int, context::AbstractString)
    raw isa AbstractVector && length(raw) == columns || throw(
        DiscoveryGateError(
            :invalid_matrix_artifact,
            "$context must contain exactly $columns columns",
        ),
    )
    result = Matrix{Float64}(undef, dimension, columns)
    for column in 1:columns
        values = raw[column]
        values isa AbstractVector && length(values) == dimension || throw(
            DiscoveryGateError(
                :invalid_matrix_artifact,
                "$context column $column has the wrong dimension",
            ),
        )
        for row in 1:dimension
            result[row, column] = _hex_float64(values[row], "$context[$column][$row]")
        end
    end
    return result
end

function artifact_document(
    artifact::ProposalMatrixArtifact;
    include_sha256::Bool=true,
)
    document = Dict{String,Any}(
        "authority_sha256" => artifact.authority_sha256,
        "column_count" => size(artifact.coordinates, 2),
        "coordinate_float64_bits_by_column" => _matrix_bits(artifact.coordinates),
        "dimension" => size(artifact.coordinates, 1),
        "lane_schedule" => String.(artifact.lane_schedule),
        "metadata" => JSON3.read(artifact.metadata_json, Dict{String,Any}),
        "method" => _METHOD_WIRE[artifact.method],
        "replicate_seed" => string(artifact.replicate_seed),
        "schema_version" => MATRIX_SCHEMA_VERSION,
        "source_columns" => collect(artifact.source_columns),
        "unit_float64_bits_by_column" => _matrix_bits(artifact.unit_points),
    )
    include_sha256 && (document["sha256"] = artifact.sha256)
    return document
end

function _verify_artifact_digest(artifact::ProposalMatrixArtifact)
    observed = bytes2hex(sha256(codeunits(GeoTargetCore.canonical_json(
        artifact_document(artifact; include_sha256=false),
    ))))
    observed == artifact.sha256 || throw(
        DiscoveryGateError(
            :matrix_checksum_mismatch,
            "in-memory proposal matrix bytes changed after construction",
        ),
    )
    return true
end

function matrix_from_document(document)
    document isa AbstractDict || throw(
        DiscoveryGateError(:invalid_matrix_artifact, "proposal matrix document must be an object"),
    )
    get(document, "schema_version", nothing) == MATRIX_SCHEMA_VERSION || throw(
        DiscoveryGateError(:invalid_matrix_artifact, "unexpected matrix schema_version"),
    )
    method_wire = get(document, "method", nothing)
    method_wire isa AbstractString && haskey(_WIRE_METHOD, String(method_wire)) || throw(
        DiscoveryGateError(:invalid_matrix_artifact, "unknown proposal method"),
    )
    dimension = get(document, "dimension", nothing)
    columns = get(document, "column_count", nothing)
    dimension isa Integer && dimension > 0 || throw(
        DiscoveryGateError(:invalid_matrix_artifact, "dimension must be positive"),
    )
    columns == MATRIX_COLUMN_COUNT || throw(
        DiscoveryGateError(
            :invalid_matrix_artifact,
            "column_count must be $MATRIX_COLUMN_COUNT",
        ),
    )
    seed_text = get(document, "replicate_seed", nothing)
    seed_text isa AbstractString || throw(
        DiscoveryGateError(:invalid_matrix_artifact, "replicate_seed must be decimal text"),
    )
    seed = try
        parse(UInt64, seed_text)
    catch error
        throw(
            DiscoveryGateError(
                :invalid_matrix_artifact,
                "replicate_seed is invalid: $(sprint(showerror, error))",
            ),
        )
    end
    lanes = get(document, "lane_schedule", nothing)
    source_columns = get(document, "source_columns", nothing)
    (lanes isa AbstractVector || lanes isa Tuple) || throw(
        DiscoveryGateError(:invalid_matrix_artifact, "lane_schedule must be an array"),
    )
    (source_columns isa AbstractVector || source_columns isa Tuple) || throw(
        DiscoveryGateError(:invalid_matrix_artifact, "source_columns must be an array"),
    )
    metadata = get(document, "metadata", nothing)
    metadata isa AbstractDict || throw(
        DiscoveryGateError(:invalid_matrix_artifact, "metadata must be an object"),
    )
    authority = get(document, "authority_sha256", nothing)
    authority isa AbstractString || throw(
        DiscoveryGateError(:invalid_matrix_artifact, "authority_sha256 must be text"),
    )
    digest = get(document, "sha256", nothing)
    digest isa AbstractString && _is_sha256_text(digest) || throw(
        DiscoveryGateError(:invalid_matrix_artifact, "sha256 must be text"),
    )
    unit = _matrix_from_bits(
        get(document, "unit_float64_bits_by_column", nothing),
        Int(dimension),
        MATRIX_COLUMN_COUNT,
        "unit_float64_bits_by_column",
    )
    coordinates = _matrix_from_bits(
        get(document, "coordinate_float64_bits_by_column", nothing),
        Int(dimension),
        MATRIX_COLUMN_COUNT,
        "coordinate_float64_bits_by_column",
    )
    return ProposalMatrixArtifact(
        _WIRE_METHOD[String(method_wire)],
        unit,
        coordinates,
        Symbol.(String.(lanes)),
        Int.(source_columns),
        seed,
        Dict{String,Any}(String(key) => value for (key, value) in metadata),
        String(authority);
        expected_sha256=String(digest),
    )
end

function write_matrix_once(path::AbstractString, artifact::ProposalMatrixArtifact)
    _verify_artifact_digest(artifact)
    destination = abspath(path)
    ispath(destination) && throw(
        DiscoveryGateError(:matrix_already_exists, "refusing to overwrite $destination"),
    )
    mkpath(dirname(destination))
    text = GeoTargetCore.canonical_json(artifact_document(artifact)) * "\n"
    try
        stream = Base.Filesystem.open(
            destination,
            Base.JL_O_WRONLY | Base.JL_O_CREAT | Base.JL_O_EXCL,
            0o600,
        )
        try
            write(stream, text)
        finally
            close(stream)
        end
    catch error
        ispath(destination) && throw(
            DiscoveryGateError(:matrix_already_exists, "refusing to overwrite $destination"),
        )
        rethrow(error)
    end
    return artifact.sha256
end

function read_matrix_artifact(path::AbstractString)
    isfile(path) || throw(
        DiscoveryGateError(:missing_matrix_artifact, "proposal matrix is absent: $path"),
    )
    document = try
        JSON3.read(read(path, String), Dict{String,Any})
    catch error
        throw(
            DiscoveryGateError(
                :invalid_matrix_artifact,
                "cannot parse proposal matrix: $(sprint(showerror, error))",
            ),
        )
    end
    return matrix_from_document(document)
end

function leading_prefix(artifact::ProposalMatrixArtifact, columns::Integer)
    columns in CHECKPOINT_COLUMNS || throw(
        ArgumentError("prefix must be one of $(collect(CHECKPOINT_COLUMNS))"),
    )
    return @view artifact.coordinates[:, 1:Int(columns)]
end

function _prefix_checksum(artifact::ProposalMatrixArtifact, columns::Int)
    document = Dict{String,Any}(
        "artifact_sha256" => artifact.sha256,
        "coordinate_float64_bits_by_column" =>
            _matrix_bits(Matrix(@view artifact.coordinates[:, 1:columns])),
        "lane_schedule" => String.(artifact.lane_schedule[1:columns]),
        "prefix" => columns,
        "source_columns" => collect(artifact.source_columns[1:columns]),
    )
    return bytes2hex(sha256(codeunits(GeoTargetCore.canonical_json(document))))
end

function static_prefix_audit(artifact::ProposalMatrixArtifact)
    _verify_artifact_digest(artifact)
    checksums = Dict{Int,String}()
    for columns in CHECKPOINT_COLUMNS
        prefix = leading_prefix(artifact, columns)
        size(prefix) == (size(artifact.coordinates, 1), columns) || throw(
            DiscoveryGateError(:prefix_identity_failure, "prefix $columns has wrong shape"),
        )
        prefix == artifact.coordinates[:, 1:columns] || throw(
            DiscoveryGateError(:prefix_identity_failure, "prefix $columns was regenerated"),
        )
        checksums[columns] = _prefix_checksum(artifact, columns)
    end
    return (
        valid=true,
        maximum_sha256=artifact.sha256,
        prefix_sha256=checksums,
    )
end

function iid_bounded_gap_audit(lanes; cadence::Integer=4)
    cadence >= 2 || throw(ArgumentError("IID cadence must be at least two"))
    schedule = Tuple(Symbol.(lanes))
    iid_count = 0
    maximum_gap = 0
    last_iid = 0
    violations = Int[]
    for (index, lane) in enumerate(schedule)
        if lane === :iid
            iid_count += 1
            maximum_gap = max(maximum_gap, index - last_iid)
            last_iid = index
        end
        iid_count >= cld(index, cadence) || push!(violations, index)
    end
    maximum_gap = max(maximum_gap, length(schedule) + 1 - last_iid)
    bounded_gap = isempty(violations) && maximum_gap <= cadence
    return (
        bounded_gap,
        cadence=Int(cadence),
        iid_count,
        maximum_gap,
        starvation_count=bounded_gap ? 0 : 1,
        violation_prefixes=Tuple(violations),
    )
end
