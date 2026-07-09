abstract type AbstractGeoTargetId end

const _ID_PATTERN = r"^[A-Za-z_][A-Za-z0-9_.-]*$"

function _canonical_name(value::AbstractString, kind::AbstractString)
    name = String(value)
    occursin(_ID_PATTERN, name) || throw(
        InvariantError(
            :invalid_identifier,
            "$kind must match $(_ID_PATTERN.pattern); received $(repr(name))",
        ),
    )
    return name
end

for (type_name, label) in (
    (:NodeId, "node identifier"),
    (:VariableId, "variable identifier"),
    (:ChoiceKey, "choice key"),
)
    @eval begin
        struct $type_name <: AbstractGeoTargetId
            value::String

            function $type_name(value::AbstractString)
                return new(_canonical_name(value, $label))
            end
        end

        Base.string(id::$type_name) = id.value
        Base.show(io::IO, id::$type_name) = print(io, $(string(type_name)), "(\"", id.value, "\")")
        Base.isless(left::$type_name, right::$type_name) = isless(left.value, right.value)
    end
end

"""Stable identity of a plugin namespace."""
struct PluginId <: AbstractGeoTargetId
    namespace::UUID
    name::String

    function PluginId(namespace::UUID, name::AbstractString)
        return new(namespace, _canonical_name(name, "plugin name"))
    end
end

Base.string(id::PluginId) = string(id.namespace, "/", id.name)
Base.show(io::IO, id::PluginId) = print(io, "PluginId(\"", string(id), "\")")
Base.isless(left::PluginId, right::PluginId) =
    (left.namespace.value, left.name) < (right.namespace.value, right.name)

function Base.parse(::Type{PluginId}, value::AbstractString)
    parts = split(String(value), '/'; limit = 2)
    length(parts) == 2 || throw(
        InvariantError(:invalid_plugin_id, "wire plugin IDs use <uuid>/<name>"),
    )
    occursin(
        r"^[0-9A-Fa-f]{8}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{12}$",
        parts[1],
    ) || throw(InvariantError(:invalid_plugin_id, "plugin namespace is not a UUID"))
    return PluginId(UUID(parts[1]), parts[2])
end

for (type_name, label) in (
    (:TypeId, "type name"),
    (:PrimitiveId, "operation name"),
    (:SelectorId, "selector name"),
)
    @eval begin
        struct $type_name <: AbstractGeoTargetId
            plugin::PluginId
            name::String

            function $type_name(plugin::PluginId, name::AbstractString)
                return new(plugin, _canonical_name(name, $label))
            end
        end

        Base.string(id::$type_name) = string(string(id.plugin), "::", id.name)
        Base.show(io::IO, id::$type_name) = print(io, $(string(type_name)), "(\"", string(id), "\")")
        Base.isless(left::$type_name, right::$type_name) =
            (left.plugin, left.name) < (right.plugin, right.name)

        function Base.parse(::Type{$type_name}, value::AbstractString)
            parts = split(String(value), "::"; limit = 2)
            length(parts) == 2 || throw(
                InvariantError(
                    :invalid_qualified_id,
                    "wire-qualified IDs use <uuid>/<plugin>::<symbol>",
                ),
            )
            return $type_name(parse(PluginId, parts[1]), parts[2])
        end
    end
end

"""A canonical SHA-256 digest used by plugin, graph, policy and environment locks."""
struct ContentHash
    bytes::NTuple{32,UInt8}
end

function ContentHash(value::AbstractString)
    canonical = lowercase(String(value))
    startswith(canonical, "sha256:") || throw(
        InvariantError(:invalid_content_hash, "a content hash must start with sha256:"),
    )
    digest = canonical[8:end]
    ncodeunits(digest) == 64 || throw(
        InvariantError(:invalid_content_hash, "a SHA-256 digest must contain 64 hexadecimal characters"),
    )
    occursin(r"^[0-9a-f]{64}$", digest) || throw(
        InvariantError(:invalid_content_hash, "a SHA-256 digest contains a non-hexadecimal character"),
    )
    return ContentHash(Tuple(hex2bytes(digest)))
end

"""Compute a canonical SHA-256 digest from bytes or UTF-8 text."""
content_hash(value::AbstractVector{UInt8}) = ContentHash(Tuple(SHA.sha256(value)))
content_hash(value::AbstractString) = content_hash(Vector{UInt8}(codeunits(value)))

hex(value::ContentHash) = bytes2hex(collect(value.bytes))
Base.string(value::ContentHash) = string("sha256:", hex(value))
Base.show(io::IO, value::ContentHash) = print(io, "ContentHash(\"", string(value), "\")")
Base.isless(left::ContentHash, right::ContentHash) = isless(left.bytes, right.bytes)
Base.parse(::Type{ContentHash}, value::AbstractString) = ContentHash(value)
