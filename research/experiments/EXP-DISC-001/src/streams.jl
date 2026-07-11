const _QMC_BASE = 2
const _QMC_PAD = 32
const _IID_CADENCE = 4
const _PROPOSAL_ENGINE_SOURCE = joinpath(
    REPOSITORY_ROOT,
    "julia",
    "GeoTargetCore",
    "src",
    "proposal_engine.jl",
)

function derive_seed(
    root_seed::Integer,
    method::DiscoveryMethod,
    case_ordinal::Integer,
    replicate::Integer,
    namespace::AbstractString="proposal",
)
    0 <= root_seed <= typemax(UInt64) || throw(ArgumentError("root seed must fit UInt64"))
    case_ordinal > 0 || throw(ArgumentError("case ordinal must be positive"))
    replicate > 0 || throw(ArgumentError("replicate must be positive"))
    payload = GeoTargetCore.canonical_json(Dict{String,Any}(
        "case_ordinal" => Int(case_ordinal),
        "experiment" => "EXP-DISC-001",
        "method" => _METHOD_WIRE[method],
        "namespace" => String(namespace),
        "replicate" => Int(replicate),
        "root_seed" => string(UInt64(root_seed)),
    ))
    digest = sha256(codeunits(payload))
    result = zero(UInt64)
    for byte in digest[1:8]
        result = (result << 8) | UInt64(byte)
    end
    return result
end

function stream_contract(method::DiscoveryMethod)
    common = Dict{String,Any}(
        "column_count" => MATRIX_COLUMN_COUNT,
        "prefixes" => collect(CHECKPOINT_COLUMNS),
        "runtime_inputs" => ["dimension", "finite_bounds", "numeric_seed"],
        "truth_fields_visible" => false,
    )
    difference = if method === D0_IID_ALL
        "Random.Xoshiro independent-uniform experimental model; every point launched"
    elseif method === D1_SOBOL_ALL
        "QuasiMonteCarlo SobolSample(NoRand), one maximum matrix"
    elseif method === D_HALTON_ALL
        "production task-indexed contiguous Halton source through dimension 64"
    elseif method === D_CURRENT_COUNTER_HALTON
        "production counter-IID and Halton raw-source schedule with H0 weights/cadence"
    elseif method === D2O_OWEN_ALL
        "one deterministic Sobol maximum matrix, then one Owen scramble"
    elseif method === D2M_MATOUSEK_ALL
        "one deterministic Sobol maximum matrix, then one Matousek scramble"
    else
        "fixed 1-in-4 IID schedule consuming persisted D0 and Owen source prefixes"
    end
    common["method"] = _METHOD_WIRE[method]
    common["only_difference"] = difference
    return common
end

function _stable_transform(domain::ProposalDomain, unit::Matrix{Float64})
    size(unit, 1) == length(domain.lower) || throw(
        DimensionMismatch("unit matrix dimension disagrees with proposal domain"),
    )
    points = similar(unit)
    for column in axes(unit, 2), row in axes(unit, 1)
        lower = domain.lower[row]
        upper = domain.upper[row]
        u = unit[row, column]
        midpoint = lower / 2 + upper / 2
        value = if u <= 0.5
            lower + (midpoint - lower) * (2 * u)
        else
            midpoint + (upper - midpoint) * (2 * u - 1)
        end
        isfinite(value) || (value = u < 0.5 ? lower : upper)
        points[row, column] = clamp(value, lower, upper)
    end
    return points
end

function _independent_unit(dimension::Int, seed::UInt64)
    rng = Random.Xoshiro(seed)
    return rand(rng, Float64, dimension, MATRIX_COLUMN_COUNT)
end

function _halton_unit(dimension::Int)
    dimension <= 64 || throw(
        DiscoveryGateError(
            :halton_dimension_unsupported,
            "the production Halton source is defined only through dimension 64",
        ),
    )
    primes = getfield(GeoTargetCore, :_HALTON_PRIMES)
    radical_inverse = getfield(GeoTargetCore, :_radical_inverse)
    unit = Matrix{Float64}(undef, dimension, MATRIX_COLUMN_COUNT)
    for column in 1:MATRIX_COLUMN_COUNT, row in 1:dimension
        unit[row, column] = radical_inverse(UInt64(column), primes[row])
    end
    return unit
end

function _counter_unit(seed::UInt64, task_id::UInt64, dimension::Int)
    mix64 = getfield(GeoTargetCore, :_mix64)
    word = mix64(
        seed ⊛
        (task_id * 0xd2b74407b1ce6e93) ⊛
        (UInt64(dimension) * 0xca5a826395121157) ⊛
        (UInt64(0x11) * 0x9e3779b97f4a7c15),
    )
    mantissa = word >> 12
    return (Float64(mantissa) + 0.5) * 0x1.0p-52
end

function _current_raw_unit(dimension::Int, seed::UInt64)
    dimension <= 64 || throw(
        DiscoveryGateError(
            :halton_dimension_unsupported,
            "current raw-source comparison separates the above-64 fallback stratum",
        ),
    )
    scheduler = getfield(GeoTargetCore, :FairScheduler)()
    next_schedule! = getfield(GeoTargetCore, :next_schedule!)
    policy = GeoTargetCore.standard_policy()
    primes = getfield(GeoTargetCore, :_HALTON_PRIMES)
    radical_inverse = getfield(GeoTargetCore, :_radical_inverse)
    unit = Matrix{Float64}(undef, dimension, MATRIX_COLUMN_COUNT)
    lanes = Symbol[]
    task_ids = Int[]
    for column in 1:MATRIX_COLUMN_COUNT
        decision = next_schedule!(
            scheduler,
            policy;
            adaptive_unbounded=false,
            pending_task_id=nothing,
            refinement_configuration=nothing,
            allow_new_proposals=true,
        )
        decision === nothing && error("production raw-source scheduler stopped unexpectedly")
        task_id = decision.task_id
        if decision.lane === GeoTargetCore.LANE_IID
            push!(lanes, :iid)
            for row in 1:dimension
                unit[row, column] = _counter_unit(seed, task_id, row)
            end
        elseif decision.lane === GeoTargetCore.LANE_HEURISTIC
            push!(lanes, :halton)
            for row in 1:dimension
                unit[row, column] = radical_inverse(task_id, primes[row])
            end
        else
            throw(
                DiscoveryGateError(
                    :current_raw_schedule_drift,
                    "bounded raw-source schedule emitted a non-IID/non-Halton lane",
                ),
            )
        end
        push!(task_ids, Int(task_id))
    end
    audit = iid_bounded_gap_audit(lanes; cadence=_IID_CADENCE)
    audit.bounded_gap || throw(
        DiscoveryGateError(:iid_bounded_gap_failure, "current H0 raw IID cadence drifted"),
    )
    return unit, Tuple(lanes), Tuple(task_ids)
end

function _deterministic_sobol_unit(dimension::Int)
    unit = QuasiMonteCarlo.sample(
        MATRIX_COLUMN_COUNT,
        dimension,
        QuasiMonteCarlo.SobolSample(R=QuasiMonteCarlo.NoRand()),
        Float64,
    )
    size(unit) == (dimension, MATRIX_COLUMN_COUNT) || error("Sobol shape drifted")
    return Matrix{Float64}(unit)
end

function _scrambled_sobol_unit(
    dimension::Int,
    seed::UInt64,
    method::DiscoveryMethod,
)
    deterministic = _deterministic_sobol_unit(dimension)
    rng = Random.Xoshiro(seed)
    randomizer = if method === D2O_OWEN_ALL
        QuasiMonteCarlo.OwenScramble(base=_QMC_BASE, pad=_QMC_PAD, rng=rng)
    elseif method === D2M_MATOUSEK_ALL
        QuasiMonteCarlo.MatousekScramble(base=_QMC_BASE, pad=_QMC_PAD, rng=rng)
    else
        throw(ArgumentError("scrambled Sobol method must be Owen or Matousek"))
    end
    randomized = QuasiMonteCarlo.randomize(deterministic, randomizer)
    return deterministic, Matrix{Float64}(randomized)
end

function _default_trace(method::DiscoveryMethod)
    lane = if method === D0_IID_ALL
        :iid
    elseif method in (D1_SOBOL_ALL, D2O_OWEN_ALL, D2M_MATOUSEK_ALL)
        :sobol
    else
        :halton
    end
    return ntuple(_ -> lane, MATRIX_COLUMN_COUNT), ntuple(identity, MATRIX_COLUMN_COUNT)
end

function _base_metadata(
    authority::_MaterializationAuthority,
    method::DiscoveryMethod,
)
    source_paths = (
        "research/experiments/EXP-DISC-001/src/matrix_artifact.jl",
        "research/experiments/EXP-DISC-001/src/streams.jl",
    )
    return Dict{String,Any}(
        "authority_freeze_sha256" => authority.freeze_sha256,
        "confirmation_contract_sha256" => authority.confirmation_contract_sha256,
        "experiment_source_sha256" => Dict(
            path => _file_sha256(joinpath(REPOSITORY_ROOT, split(path, '/')...)) for
            path in source_paths
        ),
        "julia_version" => string(VERSION),
        "local_options_sha256" => authority.local_options_sha256,
        "local_source_sha256" => authority.local_source_sha256,
        "manifest_sha256" => _file_sha256(joinpath(EXPERIMENT_ROOT, "Manifest.toml")),
        "preregistration_sha256" => authority.preregistration_sha256,
        "proposal_engine_sha256" => _file_sha256(_PROPOSAL_ENGINE_SOURCE),
        "proposal_engine_version" => string(GeoTargetCore.PROPOSAL_ENGINE_VERSION),
        "quasi_monte_carlo_version" => string(Base.pkgversion(QuasiMonteCarlo)),
        "stream_contract" => stream_contract(method),
    )
end

function _bind_domain!(metadata::Dict{String,Any}, domain::ProposalDomain)
    metadata["domain_dimension"] = length(domain.lower)
    metadata["domain_lower_float64_bits"] = [_float64_hex(value) for value in domain.lower]
    metadata["domain_upper_float64_bits"] = [_float64_hex(value) for value in domain.upper]
    return metadata
end

function _artifact_matches_domain(
    artifact::ProposalMatrixArtifact,
    domain::ProposalDomain,
)
    metadata = JSON3.read(artifact.metadata_json, Dict{String,Any})
    return get(metadata, "domain_dimension", nothing) == length(domain.lower) &&
           get(metadata, "domain_lower_float64_bits", nothing) ==
               [_float64_hex(value) for value in domain.lower] &&
           get(metadata, "domain_upper_float64_bits", nothing) ==
               [_float64_hex(value) for value in domain.upper]
end

function _standalone_artifact(
    authority::_MaterializationAuthority,
    method::DiscoveryMethod,
    domain::ProposalDomain,
    seed::UInt64,
)
    dimension = length(domain.lower)
    metadata = _base_metadata(authority, method)
    _bind_domain!(metadata, domain)
    if method === D0_IID_ALL
        unit = _independent_unit(dimension, seed)
        lanes, source_columns = _default_trace(method)
        metadata["rng"] = "Random.Xoshiro"
        metadata["independence_model"] = "mutually-independent-uniform experimental model"
    elseif method === D1_SOBOL_ALL
        unit = _deterministic_sobol_unit(dimension)
        lanes, source_columns = _default_trace(method)
        metadata["sampler"] = "QuasiMonteCarlo.SobolSample(NoRand)"
    elseif method === D_HALTON_ALL
        unit = _halton_unit(dimension)
        lanes, source_columns = _default_trace(method)
        metadata["sampler"] = "GeoTargetCore contiguous task-index Halton"
        metadata["dimension_limit"] = 64
    elseif method === D_CURRENT_COUNTER_HALTON
        unit, lanes, source_columns = _current_raw_unit(dimension, seed)
        metadata["sampler"] = "GeoTargetCore bounded H0 raw-source schedule"
        metadata["iid_cadence"] = _IID_CADENCE
        metadata["scope"] = "raw proposal-source attribution; not the adaptive D-H0-CURRENT control"
    elseif method in (D2O_OWEN_ALL, D2M_MATOUSEK_ALL)
        deterministic, unit = _scrambled_sobol_unit(dimension, seed, method)
        lanes, source_columns = _default_trace(method)
        metadata["base"] = _QMC_BASE
        metadata["pad"] = _QMC_PAD
        metadata["rng"] = "Random.Xoshiro"
        metadata["sampler"] = "QuasiMonteCarlo.SobolSample(NoRand), post-generation scramble"
        metadata["deterministic_first_column_float64_bits"] =
            [_float64_hex(value) for value in deterministic[:, 1]]
    else
        throw(
            ArgumentError(
                "mixed stream must consume separately persisted D0 and D2O artifacts",
            ),
        )
    end
    coordinates = _stable_transform(domain, unit)
    return ProposalMatrixArtifact(
        method,
        unit,
        coordinates,
        lanes,
        source_columns,
        seed,
        metadata,
        authority.freeze_sha256,
    )
end

function _mixed_artifact(
    authority::_MaterializationAuthority,
    domain::ProposalDomain,
    seed::UInt64,
    iid_source::ProposalMatrixArtifact,
    rqmc_source::ProposalMatrixArtifact,
)
    iid_source.method === D0_IID_ALL || throw(
        ArgumentError("mixed IID source must be D0-IID-ALL"),
    )
    rqmc_source.method === D2O_OWEN_ALL || throw(
        ArgumentError("requested mixed candidate requires the persisted Owen source"),
    )
    iid_source.authority_sha256 == authority.freeze_sha256 == rqmc_source.authority_sha256 ||
        throw(
            DiscoveryGateError(
                :mixed_authority_mismatch,
                "mixed source artifacts were not bound by this champion freeze",
            ),
        )
    dimension = length(domain.lower)
    size(iid_source.coordinates, 1) == dimension == size(rqmc_source.coordinates, 1) ||
        throw(DimensionMismatch("mixed source dimensions disagree"))
    _artifact_matches_domain(iid_source, domain) &&
        _artifact_matches_domain(rqmc_source, domain) || throw(
            DiscoveryGateError(
                :mixed_domain_mismatch,
                "mixed sources were materialized for another bounded domain",
            ),
        )
    unit = Matrix{Float64}(undef, dimension, MATRIX_COLUMN_COUNT)
    coordinates = similar(unit)
    lanes = Symbol[]
    source_columns = Int[]
    iid_column = 0
    rqmc_column = 0
    for column in 1:MATRIX_COLUMN_COUNT
        if mod(column - 1, _IID_CADENCE) == 0
            iid_column += 1
            unit[:, column] .= iid_source.unit_points[:, iid_column]
            coordinates[:, column] .= iid_source.coordinates[:, iid_column]
            push!(lanes, :iid)
            push!(source_columns, iid_column)
        else
            rqmc_column += 1
            unit[:, column] .= rqmc_source.unit_points[:, rqmc_column]
            coordinates[:, column] .= rqmc_source.coordinates[:, rqmc_column]
            push!(lanes, :owen)
            push!(source_columns, rqmc_column)
        end
    end
    audit = iid_bounded_gap_audit(lanes; cadence=_IID_CADENCE)
    audit.bounded_gap || throw(
        DiscoveryGateError(:iid_bounded_gap_failure, "mixed IID schedule can starve"),
    )
    metadata = _base_metadata(authority, D3_OWEN_MIXED)
    _bind_domain!(metadata, domain)
    metadata["iid_cadence"] = _IID_CADENCE
    metadata["iid_fraction"] = "1/4"
    metadata["iid_source_sha256"] = iid_source.sha256
    metadata["rqmc_fraction"] = "3/4"
    metadata["rqmc_source_sha256"] = rqmc_source.sha256
    metadata["schedule_phase"] = "IID at launch ordinals congruent to 1 mod 4"
    return ProposalMatrixArtifact(
        D3_OWEN_MIXED,
        unit,
        coordinates,
        lanes,
        source_columns,
        seed,
        metadata,
        authority.freeze_sha256,
    )
end

"""
Generate exactly one maximum-prefix artifact and persist it with no-overwrite
semantics. Every smaller checkpoint is a view of this artifact. The A3
authority is required before any generator is invoked.
"""
function materialize_stream_once(
    authority::_MaterializationAuthority,
    method::DiscoveryMethod,
    domain::ProposalDomain,
    destination::AbstractString;
    replicate_seed::Integer,
    iid_source_path::Union{Nothing,AbstractString}=nothing,
    rqmc_source_path::Union{Nothing,AbstractString}=nothing,
)
    0 <= replicate_seed <= typemax(UInt64) || throw(
        ArgumentError("replicate_seed must fit UInt64"),
    )
    ispath(destination) && throw(
        DiscoveryGateError(:matrix_already_exists, "refusing to overwrite $destination"),
    )
    seed = UInt64(replicate_seed)
    artifact = if method === D3_OWEN_MIXED
        iid_source_path === nothing && throw(
            ArgumentError("mixed stream requires a persisted D0 source artifact"),
        )
        rqmc_source_path === nothing && throw(
            ArgumentError("mixed stream requires a persisted D2O source artifact"),
        )
        _mixed_artifact(
            authority,
            domain,
            seed,
            read_matrix_artifact(iid_source_path),
            read_matrix_artifact(rqmc_source_path),
        )
    else
        _standalone_artifact(authority, method, domain, seed)
    end
    static_prefix_audit(artifact).valid || error("prefix audit failed")
    write_matrix_once(destination, artifact)
    return artifact
end
