function _write_uint64_le(io::IO, value::UInt64)
    for shift in 0:8:56
        write(io, UInt8((value >> shift) & 0xff))
    end
    return nothing
end

function _write_string(io::IO, value::AbstractString)
    bytes = codeunits(value)
    _write_uint64_le(io, UInt64(length(bytes)))
    write(io, bytes)
    return nothing
end

"""Platform-independent checksum of an explicitly materialized Float64 matrix."""
function artifact_checksum(name::Symbol, values::AbstractMatrix{<:Real})
    material = Matrix{Float64}(values)
    all(isfinite, material) || throw(ArgumentError("cannot checksum nonfinite values"))
    io = IOBuffer()
    _write_string(io, REPLAY_FORMAT_VERSION)
    _write_string(io, String(name))
    _write_uint64_le(io, UInt64(size(material, 1)))
    _write_uint64_le(io, UInt64(size(material, 2)))
    for value in material
        _write_uint64_le(io, reinterpret(UInt64, value))
    end
    return bytes2hex(sha256(take!(io)))
end

function replay_checksum(problem::DirectAnalyticProblem)
    io = IOBuffer()
    _write_string(io, REPLAY_FORMAT_VERSION)
    _write_string(io, problem.family_id)
    _write_string(io, problem.instance_id)
    for artifact in problem.artifacts
        _write_string(io, String(artifact.name))
        _write_string(io, artifact.sha256)
    end
    return bytes2hex(sha256(take!(io)))
end

"""Detect accidental mutation or seed-only/nonmaterialized replay records."""
function verify_replay_material(problem::DirectAnalyticProblem)
    required = Set(
        (:gold_configurations, :gold_targets, :saved_starts, :bounds, :scales, :parameters),
    )
    names = Set(entry.name for entry in problem.artifacts)
    issubset(required, names) || return false
    for artifact in problem.artifacts
        artifact.sha256 == artifact_checksum(artifact.name, artifact.values) || return false
    end
    starts = only(filter(entry -> entry.name === :saved_starts, problem.artifacts))
    gold = only(filter(entry -> entry.name === :gold_configurations, problem.artifacts))
    return starts.values == problem.saved_starts && gold.values == problem.gold_configurations
end
