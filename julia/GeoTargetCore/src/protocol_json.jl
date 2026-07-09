using JSON3
using StructTypes

const PROBLEM_WIRE_VERSION = "geotarget.problem/v1"
const PLUGIN_WIRE_VERSION = "geotarget.plugin/v1"
const SOLVE_RESULT_WIRE_VERSION = "geotarget.solve-result/v1"
const _JCS_SAFE_INTEGER = Int128(9_007_199_254_740_991)

"""A path-qualified failure at the untrusted JSON boundary."""
struct ProtocolJsonError <: CoreError
    path::String
    message::String
end

Base.showerror(io::IO, error::ProtocolJsonError) =
    print(io, "GeoTarget protocol error at ", error.path, ": ", error.message)

_protocol_error(path, message) = throw(ProtocolJsonError(String(path), String(message)))

"""
Lossless canonical decimal used when a result document carries a decimal string.

The numerical value participates in Base result invariants, while `text` keeps a
validated wire spelling stable across decode/encode. This is deliberately not a
general arithmetic type.
"""
struct ProtocolDecimal <: Real
    text::String
    value::BigFloat
end

Base.isfinite(::ProtocolDecimal) = true
Base.zero(::Type{ProtocolDecimal}) = ProtocolDecimal("0", BigFloat(0))
Base.zero(::ProtocolDecimal) = zero(ProtocolDecimal)
Base.:(==)(left::ProtocolDecimal, right::ProtocolDecimal) = left.value == right.value
Base.isless(left::ProtocolDecimal, right::ProtocolDecimal) = isless(left.value, right.value)
Base.:(<=)(left::ProtocolDecimal, right::ProtocolDecimal) = left.value <= right.value
Base.:(>=)(left::ProtocolDecimal, right::ProtocolDecimal) = left.value >= right.value
Base.:(<)(left::ProtocolDecimal, right::ProtocolDecimal) = left.value < right.value
Base.:(>)(left::ProtocolDecimal, right::ProtocolDecimal) = left.value > right.value
Base.string(value::ProtocolDecimal) = value.text
Base.show(io::IO, value::ProtocolDecimal) = print(io, "ProtocolDecimal(\"", value.text, "\")")

# StructTypes marks the explicit metadata projection boundary. JSON3 performs
# parsing; canonical emission below is intentionally independent from JSON3's
# non-JCS number writer.
struct ProtocolProjection{T}
    value::T
end

StructTypes.StructType(::Type{ProtocolProjection{T}}) where {T} = StructTypes.CustomStruct()
StructTypes.lower(projection::ProtocolProjection) = projection.value

function _materialize(value, path::AbstractString = "document")
    if value isa JSON3.Object
        result = Dict{String,Any}()
        for (key, item) in pairs(value)
            name = String(key)
            haskey(result, name) && _protocol_error(path, "duplicate object member $(repr(name))")
            result[name] = _materialize(item, string(path, ".", name))
        end
        return result
    elseif value isa JSON3.Array
        return Any[_materialize(item, string(path, ".", index - 1)) for (index, item) in enumerate(value)]
    elseif value === nothing || value isa Union{String,Bool,Integer,AbstractFloat}
        return value
    end
    _protocol_error(path, "unsupported JSON value $(typeof(value))")
end

function parse_protocol_json(source::Union{AbstractString,AbstractVector{UInt8}})
    text = source isa AbstractString ? String(source) : String(copy(source))
    raw = try
        JSON3.read(text)
    catch error
        _protocol_error("document", "invalid JSON: $(sprint(showerror, error))")
    end
    return _materialize(raw)
end

function _utf16_less(left::String, right::String)
    a = transcode(UInt16, left)
    b = transcode(UInt16, right)
    for index in 1:min(length(a), length(b))
        a[index] == b[index] || return a[index] < b[index]
    end
    return length(a) < length(b)
end

function _write_json_string(io::IO, value::String)
    write(io, UInt8('"'))
    for character in value
        code = Int(character)
        if character == '"'
            write(io, "\\\"")
        elseif character == '\\'
            write(io, "\\\\")
        elseif character == '\b'
            write(io, "\\b")
        elseif character == '\t'
            write(io, "\\t")
        elseif character == '\n'
            write(io, "\\n")
        elseif character == '\f'
            write(io, "\\f")
        elseif character == '\r'
            write(io, "\\r")
        elseif code <= 0x1f
            write(io, "\\u", lpad(string(code; base = 16), 4, '0'))
        else
            write(io, string(character))
        end
    end
    write(io, UInt8('"'))
    return nothing
end

function _canonical_float(value::AbstractFloat, path::AbstractString)
    isfinite(value) || _protocol_error(path, "non-finite numbers are outside the RFC 8785 input domain")
    iszero(value) && return "0"
    float_value = Float64(value)
    isfinite(float_value) || _protocol_error(path, "number is outside the binary64 RFC 8785 domain")
    float_value == value || _protocol_error(path, "number is not exactly representable as binary64")
    if isinteger(float_value) && abs(float_value) <= Float64(_JCS_SAFE_INTEGER)
        return string(Int128(float_value))
    end
    spelling = repr(float_value)
    occursin('e', lowercase(spelling)) && _protocol_error(
        path,
        "exponent-form binary64 values are outside GeoTarget's audited JCS subset; encode an exact decimal string",
    )
    endswith(spelling, ".0") && (spelling = spelling[1:(end - 2)])
    return spelling
end

function _canonical_write(io::IO, value, path::AbstractString)
    if value isa ProtocolProjection
        return _canonical_write(io, value.value, path)
    elseif value === nothing
        write(io, "null")
    elseif value isa Bool
        write(io, value ? "true" : "false")
    elseif value isa String
        _write_json_string(io, value)
    elseif value isa Integer
        -_JCS_SAFE_INTEGER <= value <= _JCS_SAFE_INTEGER || _protocol_error(
            path,
            "integer is outside the interoperable binary64 RFC 8785 domain; encode it as a decimal string",
        )
        write(io, string(value))
    elseif value isa AbstractFloat
        write(io, _canonical_float(value, path))
    elseif value isa AbstractDict
        all(key -> key isa String, keys(value)) || _protocol_error(path, "JSON object keys must be strings")
        names = sort!(String[key for key in keys(value)]; lt = _utf16_less)
        write(io, UInt8('{'))
        for (index, name) in enumerate(names)
            index == 1 || write(io, UInt8(','))
            _write_json_string(io, name)
            write(io, UInt8(':'))
            _canonical_write(io, value[name], string(path, ".", name))
        end
        write(io, UInt8('}'))
    elseif value isa Union{AbstractVector,Tuple}
        write(io, UInt8('['))
        for (index, item) in enumerate(value)
            index == 1 || write(io, UInt8(','))
            _canonical_write(io, item, string(path, ".", index - 1))
        end
        write(io, UInt8(']'))
    elseif value isa NamedTuple
        lowered = Dict{String,Any}(string(name) => getproperty(value, name) for name in propertynames(value))
        _canonical_write(io, lowered, path)
    else
        # A codec may return a custom StructTypes projection. JSON3 is used only
        # to lower that declared representation; this file's writer still owns
        # key ordering and the audited RFC 8785 numeric subset.
        lowered = try
            parse_protocol_json(JSON3.write(value))
        catch error
            error isa ProtocolJsonError && rethrow()
            _protocol_error(path, "value $(typeof(value)) has no StructTypes JSON representation")
        end
        _canonical_write(io, lowered, path)
    end
    return nothing
end

function canonical_json_bytes(value)
    io = IOBuffer()
    _canonical_write(io, value, "document")
    return take!(io)
end

canonical_json(value) = String(canonical_json_bytes(value))
canonical_json_hash(value) = content_hash(canonical_json_bytes(value))

function _object(value, required, optional = (); path::AbstractString)
    value isa Dict{String,Any} || _protocol_error(path, "must be an object")
    required_set = Set(String.(required))
    allowed = union(required_set, Set(String.(optional)))
    missing = sort!(collect(setdiff(required_set, Set(keys(value)))))
    isempty(missing) || _protocol_error(path, "missing required member(s): $(join(missing, ", "))")
    unknown = sort!(collect(setdiff(Set(keys(value)), allowed)))
    isempty(unknown) || _protocol_error(path, "unknown member(s): $(join(unknown, ", "))")
    return value
end

_array(value, path) = value isa Vector{Any} ? value : _protocol_error(path, "must be an array")
_string(value, path) = value isa String ? value : _protocol_error(path, "must be a string")
_bool(value, path) = value isa Bool ? value : _protocol_error(path, "must be a boolean")

function _integer(value, path; minimum = nothing)
    value isa Integer && !(value isa Bool) || _protocol_error(path, "must be an integer")
    -_JCS_SAFE_INTEGER <= value <= _JCS_SAFE_INTEGER || _protocol_error(path, "integer is outside the safe JSON domain")
    minimum === nothing || value >= minimum || _protocol_error(path, "must be at least $minimum")
    return Int(value)
end

function _wire_number(value, path)
    value isa Real && !(value isa Bool) || _protocol_error(path, "must be a JSON number")
    if value isa Integer
        -_JCS_SAFE_INTEGER <= value <= _JCS_SAFE_INTEGER || _protocol_error(path, "integer is outside the safe JSON domain")
        return Float64(value)
    end
    value isa AbstractFloat || _protocol_error(path, "must be a JSON number")
    _canonical_float(value, path) # domain check
    return Float64(value)
end

function _construct(path::AbstractString, thunk)
    try
        return thunk()
    catch error
        error isa ProtocolJsonError && rethrow()
        _protocol_error(path, sprint(showerror, error))
    end
end

_parse_wire_id(::Type{T}, text::String) where {T} = parse(T, text)
_parse_wire_id(::Type{NodeId}, text::String) = NodeId(text)
_parse_wire_id(::Type{VariableId}, text::String) = VariableId(text)
_parse_wire_id(::Type{ChoiceKey}, text::String) = ChoiceKey(text)

function _canonical_id(::Type{T}, value, path) where {T}
    text = _string(value, path)
    parsed = _construct(path, () -> _parse_wire_id(T, text))
    string(parsed) == text || _protocol_error(path, "identifier is not in canonical wire form")
    return parsed
end

function _canonical_version(value, path)
    text = _string(value, path)
    parsed = _construct(path, () -> VersionNumber(text))
    string(parsed) == text || _protocol_error(path, "semantic version is not canonical")
    parsed == v"0.0.0" && _protocol_error(path, "version 0.0.0 is reserved")
    return parsed
end

_canonical_hash(value, path) = _canonical_id(ContentHash, value, path)

function _plugin_for(registry::FrozenPluginRegistry, id::PluginId, path)
    plugin = _find_plugin(registry, id)
    plugin === nothing && _protocol_error(path, "plugin $(string(id)) is not in the frozen allowlisted registry")
    return plugin
end

function _decode_plugin_lock(raw, path; registry::Union{Nothing,FrozenPluginRegistry} = nothing)
    object = _object(raw, ("plugin_id", "version", "core_abi", "content_hash"); path)
    id = _canonical_id(PluginId, object["plugin_id"], string(path, ".plugin_id"))
    lock = PluginLock(
        id,
        _canonical_version(object["version"], string(path, ".version")),
        _canonical_version(object["core_abi"], string(path, ".core_abi")),
        _canonical_hash(object["content_hash"], string(path, ".content_hash")),
    )
    if registry !== nothing
        plugin = _plugin_for(registry, id, string(path, ".plugin_id"))
        expected = plugin_lock(plugin)
        fields_match = lock.id == expected.id && lock.version == expected.version &&
            lock.core_abi == expected.core_abi && string(lock.content) == string(expected.content)
        fields_match || _protocol_error(path, "plugin lock does not match the registered PluginSpec")
    end
    return lock
end

function _decode_plugin_locks(raw, path; registry::Union{Nothing,FrozenPluginRegistry} = nothing)
    values = _array(raw, path)
    locks = [_decode_plugin_lock(value, string(path, ".", index - 1); registry) for (index, value) in enumerate(values)]
    ids = string.(getfield.(locks, :id))
    ids == sort(ids) || _protocol_error(path, "plugin locks must be sorted by plugin_id")
    allunique(ids) || _protocol_error(path, "plugin locks contain duplicate plugin_id values")
    return Tuple(locks)
end

_plugin_lock_document(lock::PluginLock) = Dict{String,Any}(
    "plugin_id" => string(lock.id),
    "version" => string(lock.version),
    "core_abi" => string(lock.core_abi),
    "content_hash" => string(lock.content),
)

function _decode_variable(raw, path)
    object = _object(raw, ("id", "type_id", "origin", "scale"), ("lower", "upper"); path)
    id = _canonical_id(VariableId, object["id"], string(path, ".id"))
    type_id = _canonical_id(TypeId, object["type_id"], string(path, ".type_id"))
    origin = _wire_number(object["origin"], string(path, ".origin"))
    scale = _wire_number(object["scale"], string(path, ".scale"))
    lower = haskey(object, "lower") ? _wire_number(object["lower"], string(path, ".lower")) : nothing
    upper = haskey(object, "upper") ? _wire_number(object["upper"], string(path, ".upper")) : nothing
    return _construct(path, () -> VariableSpec(id, type_id, origin, scale; lower, upper))
end

function _decode_literal_value(raw, type_id::TypeId, registry::FrozenPluginRegistry, path)
    type_spec = resolve_type(registry, type_id)
    type_spec === nothing && _protocol_error(path, "literal type $(string(type_id)) is not registered")
    type_spec.decoder === nothing && _protocol_error(path, "literal type $(string(type_id)) has no locked decoder")
    decoded = try
        type_spec.decoder(deepcopy(raw))
    catch error
        _protocol_error(path, "literal decoder failed: $(sprint(showerror, error))")
    end
    decoded isa type_spec.julia_type || _protocol_error(
        path,
        "literal decoder returned $(typeof(decoded)); registered type is $(type_spec.julia_type)",
    )
    encoded = try
        type_spec.encoder(decoded)
    catch error
        _protocol_error(path, "literal encoder failed during canonicality check: $(sprint(showerror, error))")
    end
    canonical_json_bytes(encoded) == canonical_json_bytes(raw) || _protocol_error(
        path,
        "literal is not the canonical representation selected by its locked codec",
    )
    return decoded
end

function _decode_keywords(raw, path)
    raw isa Dict{String,Any} || _protocol_error(path, "must be an object")
    object = raw
    values = KeywordArg[]
    for name in sort!(collect(keys(object)))
        canonical_name = _construct(string(path, ".", name), () -> KeywordArg(name, NodeId(_string(object[name], string(path, ".", name)))))
        push!(values, canonical_name)
    end
    return Tuple(values)
end

function _decode_graph_node(raw, registry, path)
    raw isa Dict{String,Any} || _protocol_error(path, "must be an object")
    kind = _string(get(raw, "kind", nothing), string(path, ".kind"))
    if kind == "literal"
        object = _object(raw, ("kind", "id", "type_id", "value"); path)
        id = _canonical_id(NodeId, object["id"], string(path, ".id"))
        type_id = _canonical_id(TypeId, object["type_id"], string(path, ".type_id"))
        value = _decode_literal_value(object["value"], type_id, registry, string(path, ".value"))
        return LiteralNode(id, type_id, value)
    elseif kind == "reference"
        object = _object(raw, ("kind", "id", "variable"); path)
        return ReferenceNode(
            _canonical_id(NodeId, object["id"], string(path, ".id")),
            _canonical_id(VariableId, object["variable"], string(path, ".variable")),
        )
    elseif kind == "call"
        object = _object(raw, ("kind", "id", "operation", "args", "kwargs"); path)
        args = Tuple(
            _canonical_id(NodeId, value, string(path, ".args.", index - 1)) for
            (index, value) in enumerate(_array(object["args"], string(path, ".args")))
        )
        return CallNode(
            _canonical_id(NodeId, object["id"], string(path, ".id")),
            _canonical_id(PrimitiveId, object["operation"], string(path, ".operation")),
            args,
            _decode_keywords(object["kwargs"], string(path, ".kwargs")),
        )
    elseif kind == "select"
        object = _object(raw, ("kind", "id", "choice", "selector", "args", "kwargs"); path)
        args = Tuple(
            _canonical_id(NodeId, value, string(path, ".args.", index - 1)) for
            (index, value) in enumerate(_array(object["args"], string(path, ".args")))
        )
        return SelectNode(
            _canonical_id(NodeId, object["id"], string(path, ".id")),
            _canonical_id(NodeId, object["choice"], string(path, ".choice")),
            _canonical_id(SelectorId, object["selector"], string(path, ".selector")),
            args,
            _decode_keywords(object["kwargs"], string(path, ".kwargs")),
        )
    end
    _protocol_error(string(path, ".kind"), "unsupported graph node kind $(repr(kind))")
end

function _decode_relation(raw, path)
    object = _object(raw, ("node",), ("scale_override",); path)
    scale = haskey(object, "scale_override") ? _wire_number(object["scale_override"], string(path, ".scale_override")) : nothing
    return _construct(path, () -> RelationBinding(
        _canonical_id(NodeId, object["node"], string(path, ".node")); scale_override = scale,
    ))
end

function _decode_guard(raw, path)
    object = _object(raw, ("node", "strict"), ("scale_override",); path)
    scale = haskey(object, "scale_override") ? _wire_number(object["scale_override"], string(path, ".scale_override")) : nothing
    return _construct(path, () -> GuardBinding(
        _canonical_id(NodeId, object["node"], string(path, ".node")),
        _bool(object["strict"], string(path, ".strict"));
        scale_override = scale,
    ))
end

function _decode_domain(raw, path)
    object = _object(raw, ("node", "strict"); path)
    return DomainBinding(
        _canonical_id(NodeId, object["node"], string(path, ".node")),
        _bool(object["strict"], string(path, ".strict")),
    )
end

function _require_registered_problem_surface(problem::ProblemSpecV1, registry::FrozenPluginRegistry)
    for (index, lock) in enumerate(problem.plugin_locks)
        plugin = _plugin_for(registry, lock.id, string("plugin_locks.", index - 1, ".plugin_id"))
        expected = plugin_lock(plugin)
        lock.version == expected.version && lock.core_abi == expected.core_abi &&
            string(lock.content) == string(expected.content) ||
            _protocol_error(string("plugin_locks.", index - 1), "plugin lock does not match the registry")
    end
    for (index, variable) in enumerate(problem.variables)
        resolve_type(registry, variable.type_id) === nothing &&
            _protocol_error(string("variables.", index - 1, ".type_id"), "type is not registered")
    end
    for (index, node) in enumerate(problem.graph)
        path = string("graph.", index - 1)
        if node isa LiteralNode
            resolve_type(registry, node.type_id) === nothing && _protocol_error(string(path, ".type_id"), "type is not registered")
        elseif node isa CallNode
            resolve_operation(registry, node.operation) === nothing && _protocol_error(string(path, ".operation"), "operation is not registered")
        elseif node isa SelectNode
            resolve_selector(registry, node.selector) === nothing && _protocol_error(string(path, ".selector"), "selector is not registered")
        end
    end
    report = validate_problem(problem, registry)
    for issue in report.issues
        # The shared v1 schema deliberately allows literal guard/domain nodes;
        # operation-role compilation is a later Core concern. All other type,
        # signature, lock and graph failures remain protocol-boundary errors.
        issue.code in (:invalid_role_node, :invalid_role_operation) && continue
        location = issue.node === nothing ? "document" : string("graph.", issue.node)
        _protocol_error(location, issue.message)
    end
    return nothing
end

function decode_problem_document(raw, registry::FrozenPluginRegistry)
    object = _object(
        raw,
        ("schema_version", "plugin_locks", "variables", "graph", "relations", "guards", "domains", "target");
        path = "document",
    )
    _string(object["schema_version"], "schema_version") == PROBLEM_WIRE_VERSION ||
        _protocol_error("schema_version", "expected $PROBLEM_WIRE_VERSION")
    canonical_json_bytes(object) # reject values outside the audited JCS subset
    locks = _decode_plugin_locks(object["plugin_locks"], "plugin_locks"; registry)
    variables = Tuple(
        _decode_variable(value, string("variables.", index - 1)) for
        (index, value) in enumerate(_array(object["variables"], "variables"))
    )
    nodes = Tuple(
        _decode_graph_node(value, registry, string("graph.", index - 1)) for
        (index, value) in enumerate(_array(object["graph"], "graph"))
    )
    graph = _construct("graph", () -> ConstructionGraph(nodes))
    relations = Tuple(
        _decode_relation(value, string("relations.", index - 1)) for
        (index, value) in enumerate(_array(object["relations"], "relations"))
    )
    guards = Tuple(
        _decode_guard(value, string("guards.", index - 1)) for
        (index, value) in enumerate(_array(object["guards"], "guards"))
    )
    domains = Tuple(
        _decode_domain(value, string("domains.", index - 1)) for
        (index, value) in enumerate(_array(object["domains"], "domains"))
    )
    target = _canonical_id(NodeId, object["target"], "target")
    problem = _construct("document", () -> ProblemSpecV1(
        locks,
        variables,
        graph;
        relations,
        guards,
        domains,
        target,
    ))
    _require_registered_problem_surface(problem, registry)
    return problem
end

decode_problem_json(source, registry::FrozenPluginRegistry) =
    decode_problem_document(parse_protocol_json(source), registry)

function _literal_document(node::LiteralNode, registry, path)
    type_spec = resolve_type(registry, node.type_id)
    type_spec === nothing && _protocol_error(path, "literal type $(string(node.type_id)) is not registered")
    type_spec.encoder === nothing && _protocol_error(path, "literal type $(string(node.type_id)) has no locked encoder")
    node.value isa type_spec.julia_type || _protocol_error(path, "literal value has the wrong registered Julia type")
    return try
        type_spec.encoder(deepcopy(node.value))
    catch error
        _protocol_error(path, "literal encoder failed: $(sprint(showerror, error))")
    end
end

_keyword_document(keywords) = Dict{String,Any}(keyword.name => string(keyword.value) for keyword in keywords)

function _graph_node_document(node, registry, path)
    if node isa LiteralNode
        return Dict{String,Any}(
            "kind" => "literal",
            "id" => string(node.id),
            "type_id" => string(node.type_id),
            "value" => _literal_document(node, registry, string(path, ".value")),
        )
    elseif node isa ReferenceNode
        return Dict{String,Any}(
            "kind" => "reference",
            "id" => string(node.id),
            "variable" => string(node.variable),
        )
    elseif node isa CallNode
        return Dict{String,Any}(
            "kind" => "call",
            "id" => string(node.id),
            "operation" => string(node.operation),
            "args" => Any[string(id) for id in node.arguments],
            "kwargs" => _keyword_document(node.keywords),
        )
    elseif node isa SelectNode
        return Dict{String,Any}(
            "kind" => "select",
            "id" => string(node.id),
            "choice" => string(node.choice),
            "selector" => string(node.selector),
            "args" => Any[string(id) for id in node.arguments],
            "kwargs" => _keyword_document(node.keywords),
        )
    end
    _protocol_error(path, "unsupported graph node $(typeof(node))")
end

function problem_document(problem::ProblemSpecV1, registry::FrozenPluginRegistry)
    _require_registered_problem_surface(problem, registry)
    ordered_locks = sort(collect(problem.plugin_locks); by = lock -> string(lock.id))
    variables = Any[]
    for variable in problem.variables
        item = Dict{String,Any}(
            "id" => string(variable.id),
            "type_id" => string(variable.type_id),
            "origin" => variable.origin,
            "scale" => variable.scale,
        )
        variable.lower === nothing || (item["lower"] = variable.lower)
        variable.upper === nothing || (item["upper"] = variable.upper)
        push!(variables, item)
    end
    relations = Any[]
    for binding in problem.relations
        item = Dict{String,Any}("node" => string(binding.node))
        binding.scale_override === nothing || (item["scale_override"] = binding.scale_override)
        push!(relations, item)
    end
    guards = Any[]
    for binding in problem.guards
        item = Dict{String,Any}("node" => string(binding.node), "strict" => binding.strict)
        binding.scale_override === nothing || (item["scale_override"] = binding.scale_override)
        push!(guards, item)
    end
    return Dict{String,Any}(
        "schema_version" => PROBLEM_WIRE_VERSION,
        "plugin_locks" => Any[_plugin_lock_document(lock) for lock in ordered_locks],
        "variables" => variables,
        "graph" => Any[
            _graph_node_document(node, registry, string("graph.", index - 1)) for
            (index, node) in enumerate(problem.graph)
        ],
        "relations" => relations,
        "guards" => guards,
        "domains" => Any[
            Dict{String,Any}("node" => string(binding.node), "strict" => binding.strict) for
            binding in problem.domains
        ],
        "target" => string(problem.target),
    )
end

encode_problem_json(problem::ProblemSpecV1, registry::FrozenPluginRegistry) =
    canonical_json(problem_document(problem, registry))

problem_hash(problem::ProblemSpecV1, registry::FrozenPluginRegistry) =
    canonical_json_hash(problem_document(problem, registry))

const _CANONICAL_DECIMAL = r"^-?(?:0|[1-9][0-9]*)(?:\.[0-9]*[1-9])?$"

function _protocol_decimal(value, path)
    text = if value isa String
        ncodeunits(value) <= 4096 || _protocol_error(path, "decimal string exceeds 4096 bytes")
        occursin(_CANONICAL_DECIMAL, value) || _protocol_error(path, "must be a canonical finite decimal")
        value
    elseif value isa Integer && !(value isa Bool)
        -_JCS_SAFE_INTEGER <= value <= _JCS_SAFE_INTEGER || _protocol_error(path, "integer is outside the safe JSON domain")
        string(value)
    elseif value isa AbstractFloat
        _canonical_float(value, path)
    else
        _protocol_error(path, "must be a finite number or canonical decimal string")
    end
    precision = max(256, 4 * ncodeunits(text) + 32)
    numeric = try
        setprecision(precision) do
            parse(BigFloat, text)
        end
    catch error
        _protocol_error(path, "invalid decimal: $(sprint(showerror, error))")
    end
    isfinite(numeric) || _protocol_error(path, "decimal must be finite")
    iszero(numeric) && startswith(text, '-') && _protocol_error(path, "negative zero is not canonical")
    return ProtocolDecimal(text, numeric)
end

function _expand_decimal_spelling(spelling::String)
    lower = lowercase(spelling)
    sign = startswith(lower, '-') ? "-" : ""
    unsigned = isempty(sign) ? lower : lower[2:end]
    parts = split(unsigned, 'e'; limit = 2)
    mantissa = parts[1]
    exponent = length(parts) == 2 ? parse(Int, parts[2]) : 0
    dot = findfirst(==('.'), mantissa)
    decimal_position = (dot === nothing ? ncodeunits(mantissa) : dot - 1) + exponent
    digits = replace(mantissa, "." => "")
    if decimal_position <= 0
        result = string("0.", repeat("0", -decimal_position), digits)
    elseif decimal_position >= ncodeunits(digits)
        result = string(digits, repeat("0", decimal_position - ncodeunits(digits)))
    else
        result = string(digits[1:decimal_position], ".", digits[(decimal_position + 1):end])
    end
    if occursin('.', result)
        result = rstrip(result, '0')
        result = rstrip(result, '.')
    end
    result = isempty(result) ? "0" : result
    result == "0" && return "0"
    return string(sign, result)
end

function _result_number_document(value::Real, path)
    value isa ProtocolDecimal && return value.text
    isfinite(value) || _protocol_error(path, "result numeric value must be finite")
    spelling = value isa Integer ? string(value) : string(value)
    decimal = _expand_decimal_spelling(spelling)
    occursin(_CANONICAL_DECIMAL, decimal) || _protocol_error(path, "cannot form a canonical decimal string")
    ncodeunits(decimal) <= 4096 || _protocol_error(path, "canonical decimal exceeds 4096 bytes")
    return decimal
end

const _BASE64_ALPHABET = collect(codeunits("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"))

function _base64_encode(bytes::AbstractVector{UInt8})
    io = IOBuffer()
    index = 1
    while index <= length(bytes)
        remaining = length(bytes) - index + 1
        a = UInt32(bytes[index])
        b = remaining >= 2 ? UInt32(bytes[index + 1]) : UInt32(0)
        c = remaining >= 3 ? UInt32(bytes[index + 2]) : UInt32(0)
        bits = (a << 16) | (b << 8) | c
        write(io, _BASE64_ALPHABET[Int((bits >> 18) & 0x3f) + 1])
        write(io, _BASE64_ALPHABET[Int((bits >> 12) & 0x3f) + 1])
        write(io, remaining >= 2 ? _BASE64_ALPHABET[Int((bits >> 6) & 0x3f) + 1] : UInt8('='))
        write(io, remaining >= 3 ? _BASE64_ALPHABET[Int(bits & 0x3f) + 1] : UInt8('='))
        index += 3
    end
    return String(take!(io))
end

function _base64_value(byte::UInt8)
    if UInt8('A') <= byte <= UInt8('Z')
        return Int(byte - UInt8('A'))
    elseif UInt8('a') <= byte <= UInt8('z')
        return Int(byte - UInt8('a')) + 26
    elseif UInt8('0') <= byte <= UInt8('9')
        return Int(byte - UInt8('0')) + 52
    elseif byte == UInt8('+')
        return 62
    elseif byte == UInt8('/')
        return 63
    end
    return -1
end

function _base64_decode(value, path)
    text = _string(value, path)
    isempty(text) && _protocol_error(path, "certificate payload cannot be empty")
    bytes = collect(codeunits(text))
    length(bytes) % 4 == 0 || _protocol_error(path, "base64 length must be a multiple of four")
    output = UInt8[]
    for index in 1:4:length(bytes)
        block = bytes[index:(index + 3)]
        final = index + 3 == length(bytes)
        padding = block[4] == UInt8('=') ? (block[3] == UInt8('=') ? 2 : 1) : 0
        !final && padding > 0 && _protocol_error(path, "base64 padding is only allowed in the final block")
        block[3] == UInt8('=') && block[4] != UInt8('=') && _protocol_error(path, "invalid base64 padding")
        values = Int[
            _base64_value(block[1]),
            _base64_value(block[2]),
            block[3] == UInt8('=') ? 0 : _base64_value(block[3]),
            block[4] == UInt8('=') ? 0 : _base64_value(block[4]),
        ]
        any(<(0), values) && _protocol_error(path, "base64 contains an invalid character")
        bits = (UInt32(values[1]) << 18) | (UInt32(values[2]) << 12) |
            (UInt32(values[3]) << 6) | UInt32(values[4])
        push!(output, UInt8((bits >> 16) & 0xff))
        padding <= 1 && push!(output, UInt8((bits >> 8) & 0xff))
        padding == 0 && push!(output, UInt8(bits & 0xff))
    end
    isempty(output) && _protocol_error(path, "certificate payload cannot be empty")
    _base64_encode(output) == text || _protocol_error(path, "base64 is not in canonical form")
    return output
end

function _decode_artifact(raw, path)
    object = _object(raw, ("scheme", "media_type", "payload_base64", "digest"); path)
    payload = _base64_decode(object["payload_base64"], string(path, ".payload_base64"))
    artifact = _construct(path, () -> CertificateArtifact(
        _string(object["scheme"], string(path, ".scheme")),
        payload;
        media_type = _string(object["media_type"], string(path, ".media_type")),
    ))
    declared = _canonical_hash(object["digest"], string(path, ".digest"))
    string(declared) == string(artifact.digest) || _protocol_error(string(path, ".digest"), "digest does not match decoded payload bytes")
    return artifact
end

function _artifact_document(artifact::CertificateArtifact)
    payload = Vector{UInt8}(codeunits(artifact.payload))
    string(content_hash(payload)) == string(artifact.digest) || _protocol_error("artifact.digest", "artifact digest does not match its payload")
    return Dict{String,Any}(
        "scheme" => artifact.scheme,
        "media_type" => artifact.media_type,
        "payload_base64" => _base64_encode(payload),
        "digest" => string(artifact.digest),
    )
end

function _decode_rational(raw, path)
    object = _object(raw, ("numerator", "denominator"); path)
    numerator = _string(object["numerator"], string(path, ".numerator"))
    denominator = _string(object["denominator"], string(path, ".denominator"))
    rational = _construct(path, () -> ExactRational(numerator, denominator))
    string(rational.numerator) == numerator && string(rational.denominator) == denominator ||
        _protocol_error(path, "rational must be reduced with a positive canonical denominator")
    return rational
end

_rational_document(value::ExactRational) = Dict{String,Any}(
    "numerator" => string(value.numerator),
    "denominator" => string(value.denominator),
)

function _decode_identity(raw, path)
    object = _object(raw, ("coefficients", "isolating_interval", "real_root_index"); path)
    coefficient_values = _array(object["coefficients"], string(path, ".coefficients"))
    length(coefficient_values) >= 2 || _protocol_error(string(path, ".coefficients"), "requires at least two coefficients")
    coefficients = Tuple(
        _construct(string(path, ".coefficients.", index - 1), () -> ExactInteger(_string(value, string(path, ".coefficients.", index - 1)))) for
        (index, value) in enumerate(coefficient_values)
    )
    interval_object = _object(
        object["isolating_interval"],
        ("lower", "upper");
        path = string(path, ".isolating_interval"),
    )
    interval = _construct(string(path, ".isolating_interval"), () -> RationalInterval(
        _decode_rational(interval_object["lower"], string(path, ".isolating_interval.lower")),
        _decode_rational(interval_object["upper"], string(path, ".isolating_interval.upper")),
    ))
    return _construct(path, () -> AlgebraicTargetIdentity(
        coefficients,
        interval,
        _integer(object["real_root_index"], string(path, ".real_root_index"); minimum = 1),
    ))
end

function _identity_document(identity::AlgebraicTargetIdentity)
    interval = identity.isolating_interval
    return Dict{String,Any}(
        "coefficients" => Any[string(value) for value in identity.coefficients],
        "isolating_interval" => Dict{String,Any}(
            "lower" => _rational_document(interval.lower),
            "upper" => _rational_document(interval.upper),
        ),
        "real_root_index" => identity.real_root_index,
    )
end

function _decode_branch_signature(raw, path)
    decisions = BranchDecision[]
    for (index, value) in enumerate(_array(raw, path))
        item_path = string(path, ".", index - 1)
        object = _object(value, ("choice_node", "key"); path = item_path)
        push!(decisions, BranchDecision(
            _canonical_id(NodeId, object["choice_node"], string(item_path, ".choice_node")),
            _canonical_id(ChoiceKey, object["key"], string(item_path, ".key")),
        ))
    end
    allunique(getfield.(decisions, :choice_node)) || _protocol_error(path, "branch signature contains a duplicate choice node")
    return Tuple(decisions)
end

_branch_document(signature) = Any[
    Dict{String,Any}("choice_node" => string(decision.choice_node), "key" => string(decision.key)) for
    decision in signature
]

function _decode_configuration_certificate(raw, path)
    object = _object(raw, ("problem_hash", "configuration_hash", "artifact"); path)
    return ConfigurationValidityCertificate(
        _canonical_hash(object["problem_hash"], string(path, ".problem_hash")),
        _canonical_hash(object["configuration_hash"], string(path, ".configuration_hash")),
        _decode_artifact(object["artifact"], string(path, ".artifact")),
    )
end

function _decode_target_certificate(raw, path)
    object = _object(raw, ("problem_hash", "identity_hash", "artifact"); path)
    return TargetIdentityCertificate(
        _canonical_hash(object["problem_hash"], string(path, ".problem_hash")),
        _canonical_hash(object["identity_hash"], string(path, ".identity_hash")),
        _decode_artifact(object["artifact"], string(path, ".artifact")),
    )
end

function _configuration_certificate_document(value::ConfigurationValidityCertificate)
    return Dict{String,Any}(
        "problem_hash" => string(value.problem),
        "configuration_hash" => string(value.configuration),
        "artifact" => _artifact_document(value.artifact),
    )
end

function _target_certificate_document(value::TargetIdentityCertificate)
    return Dict{String,Any}(
        "problem_hash" => string(value.problem),
        "identity_hash" => string(value.identity),
        "artifact" => _artifact_document(value.artifact),
    )
end

function _decode_exact_answer(raw, path)
    object = _object(
        raw,
        ("identity", "approximation", "branch_signature", "configuration_certificate", "target_certificate");
        path,
    )
    identity = _decode_identity(object["identity"], string(path, ".identity"))
    return _construct(path, () -> ExactAnswer(
        identity,
        _protocol_decimal(object["approximation"], string(path, ".approximation")),
        _decode_branch_signature(object["branch_signature"], string(path, ".branch_signature")),
        _decode_configuration_certificate(object["configuration_certificate"], string(path, ".configuration_certificate")),
        _decode_target_certificate(object["target_certificate"], string(path, ".target_certificate")),
    ))
end

function _exact_answer_document(answer::ExactAnswer, path)
    return Dict{String,Any}(
        "identity" => _identity_document(answer.identity),
        "approximation" => _result_number_document(answer.approximation, string(path, ".approximation")),
        "branch_signature" => _branch_document(answer.branch_signature),
        "configuration_certificate" => _configuration_certificate_document(answer.configuration_certificate),
        "target_certificate" => _target_certificate_document(answer.target_certificate),
    )
end

const _EXACT_FAILURE_FROM_WIRE = Dict(
    "capability_missing" => EXACT_CAPABILITY_MISSING,
    "non_algebraic" => EXACT_NONALGEBRAIC,
    "recognition_failed" => EXACT_RECOGNITION_FAILED,
    "configuration_certificate_failed" => EXACT_CONFIGURATION_CERT_FAILED,
    "target_certificate_failed" => EXACT_TARGET_CERT_FAILED,
    "guard_not_separated" => EXACT_GUARD_NOT_SEPARATED,
    "singular" => EXACT_SINGULAR,
    "budget_exhausted" => EXACT_BUDGET_EXHAUSTED,
    "unsupported" => EXACT_UNSUPPORTED,
)
const _EXACT_FAILURE_TO_WIRE = Dict(value => key for (key, value) in _EXACT_FAILURE_FROM_WIRE)

function _decode_validation(raw, path)
    object = _object(
        raw,
        ("problem_hash", "configuration_hash", "method", "precision_bits", "independent", "artifact");
        path,
    )
    _bool(object["independent"], string(path, ".independent")) ||
        _protocol_error(string(path, ".independent"), "must be true")
    return _construct(path, () -> NumericalValidationEvidence(
        _canonical_hash(object["problem_hash"], string(path, ".problem_hash")),
        _canonical_hash(object["configuration_hash"], string(path, ".configuration_hash")),
        _string(object["method"], string(path, ".method")),
        _integer(object["precision_bits"], string(path, ".precision_bits"); minimum = 53),
        _decode_artifact(object["artifact"], string(path, ".artifact"));
        independent = true,
    ))
end

function _validation_document(value::NumericalValidationEvidence)
    return Dict{String,Any}(
        "problem_hash" => string(value.problem),
        "configuration_hash" => string(value.configuration),
        "method" => value.method,
        "precision_bits" => value.precision_bits,
        "independent" => true,
        "artifact" => _artifact_document(value.artifact),
    )
end

function _decode_enclosure(raw, path)
    object = _object(raw, ("lower", "upper"); path)
    return _construct(path, () -> NumericEnclosure(
        _protocol_decimal(object["lower"], string(path, ".lower")),
        _protocol_decimal(object["upper"], string(path, ".upper")),
    ))
end

_enclosure_document(value::NumericEnclosure, path) = Dict{String,Any}(
    "lower" => _result_number_document(value.lower, string(path, ".lower")),
    "upper" => _result_number_document(value.upper, string(path, ".upper")),
)

function _decode_guard_enclosure(raw, path)
    object = _object(raw, ("node", "enclosure", "strict"); path)
    return _construct(path, () -> GuardEnclosure(
        _canonical_id(NodeId, object["node"], string(path, ".node")),
        _decode_enclosure(object["enclosure"], string(path, ".enclosure")),
        _bool(object["strict"], string(path, ".strict")),
    ))
end

function _guard_enclosure_document(value::GuardEnclosure, path)
    return Dict{String,Any}(
        "node" => string(value.node),
        "enclosure" => _enclosure_document(value.enclosure, string(path, ".enclosure")),
        "strict" => value.strict,
    )
end

function _decode_provisional_answer(raw, path)
    object = _object(
        raw,
        (
            "target",
            "canonical_residual_bound",
            "branch_signature",
            "guard_enclosures",
            "validation",
            "exact_failure",
            "exact_failure_detail",
        );
        path,
    )
    failure_text = _string(object["exact_failure"], string(path, ".exact_failure"))
    failure = get(_EXACT_FAILURE_FROM_WIRE, failure_text, nothing)
    failure === nothing && _protocol_error(string(path, ".exact_failure"), "unknown exact-promotion failure")
    guards = Tuple(
        _decode_guard_enclosure(value, string(path, ".guard_enclosures.", index - 1)) for
        (index, value) in enumerate(_array(object["guard_enclosures"], string(path, ".guard_enclosures")))
    )
    return _construct(path, () -> ProvisionalAnswer(
        _decode_enclosure(object["target"], string(path, ".target")),
        _protocol_decimal(object["canonical_residual_bound"], string(path, ".canonical_residual_bound")),
        _decode_branch_signature(object["branch_signature"], string(path, ".branch_signature")),
        _decode_validation(object["validation"], string(path, ".validation"));
        guard_enclosures = guards,
        exact_failure = failure,
        exact_failure_detail = _string(object["exact_failure_detail"], string(path, ".exact_failure_detail")),
    ))
end

function _provisional_answer_document(answer::ProvisionalAnswer, path)
    return Dict{String,Any}(
        "target" => _enclosure_document(answer.target, string(path, ".target")),
        "canonical_residual_bound" => _result_number_document(answer.canonical_residual_bound, string(path, ".canonical_residual_bound")),
        "branch_signature" => _branch_document(answer.branch_signature),
        "guard_enclosures" => Any[
            _guard_enclosure_document(value, string(path, ".guard_enclosures.", index - 1)) for
            (index, value) in enumerate(answer.guard_enclosures)
        ],
        "validation" => _validation_document(answer.validation),
        "exact_failure" => _EXACT_FAILURE_TO_WIRE[answer.exact_failure],
        "exact_failure_detail" => answer.exact_failure_detail,
    )
end

const _SEARCH_FROM_WIRE = Dict(
    "deadline_reached" => SEARCH_DEADLINE_REACHED,
    "cancelled" => SEARCH_CANCELLED,
    "resource_exhausted" => SEARCH_RESOURCE_EXHAUSTED,
    "finished_unknown" => SEARCH_FINISHED_UNKNOWN,
    "complete_certified" => SEARCH_COMPLETE_CERTIFIED,
    "empty_certified" => SEARCH_EMPTY_CERTIFIED,
)
const _SEARCH_TO_WIRE = Dict(value => key for (key, value) in _SEARCH_FROM_WIRE)
const _TARGET_FROM_WIRE = Dict(
    "unknown" => TARGET_IMAGE_UNKNOWN,
    "finite_observed" => TARGET_FINITE_OBSERVED,
    "likely_continuous" => TARGET_LIKELY_CONTINUOUS,
    "complete_certified" => TARGET_COMPLETE_CERTIFIED,
    "empty_certified" => TARGET_EMPTY_CERTIFIED,
)
const _TARGET_TO_WIRE = Dict(value => key for (key, value) in _TARGET_FROM_WIRE)

function _wire_enum(mapping, value, path)
    text = _string(value, path)
    result = get(mapping, text, nothing)
    result === nothing && _protocol_error(path, "unknown enum value $(repr(text))")
    return result
end

function _decode_coverage(raw, path)
    object = _object(
        raw,
        (
            "independent_waves",
            "proposed_tasks",
            "completed_tasks",
            "pending_tasks",
            "explored_shells",
            "last_new_target_seconds",
        );
        path,
    )
    shells = Tuple(
        _integer(value, string(path, ".explored_shells.", index - 1); minimum = 0) for
        (index, value) in enumerate(_array(object["explored_shells"], string(path, ".explored_shells")))
    )
    last = object["last_new_target_seconds"] === nothing ? nothing :
        _wire_number(object["last_new_target_seconds"], string(path, ".last_new_target_seconds"))
    return _construct(path, () -> CoverageEvidence(
        _integer(object["independent_waves"], string(path, ".independent_waves"); minimum = 0),
        _integer(object["proposed_tasks"], string(path, ".proposed_tasks"); minimum = 0),
        _integer(object["completed_tasks"], string(path, ".completed_tasks"); minimum = 0),
        _integer(object["pending_tasks"], string(path, ".pending_tasks"); minimum = 0);
        explored_shells = shells,
        last_new_target_seconds = last,
    ))
end

function _coverage_document(value::CoverageEvidence)
    return Dict{String,Any}(
        "independent_waves" => value.independent_waves,
        "proposed_tasks" => value.proposed_tasks,
        "completed_tasks" => value.completed_tasks,
        "pending_tasks" => value.pending_tasks,
        "explored_shells" => Any[value.explored_shells...],
        "last_new_target_seconds" => value.last_new_target_seconds,
    )
end

function _decode_environment_lock(raw, path)
    object = _object(raw, ("problem_hash", "plugin_locks", "policy_hash", "environment_hash"); path)
    return _construct(path, () -> ResumeIdentity(
        _canonical_hash(object["problem_hash"], string(path, ".problem_hash")),
        _decode_plugin_locks(object["plugin_locks"], string(path, ".plugin_locks")),
        _canonical_hash(object["policy_hash"], string(path, ".policy_hash")),
        _canonical_hash(object["environment_hash"], string(path, ".environment_hash")),
    ))
end

function _environment_lock_document(value::ResumeIdentity)
    return Dict{String,Any}(
        "problem_hash" => string(value.graph),
        "plugin_locks" => Any[_plugin_lock_document(lock) for lock in value.plugin_locks],
        "policy_hash" => string(value.policy),
        "environment_hash" => string(value.environment),
    )
end

function decode_solve_result_document(raw)
    object = _object(
        raw,
        (
            "schema_version",
            "exact_answers",
            "provisional_answers",
            "search_status",
            "target_image_status",
            "coverage",
            "environment_lock",
            "evidence_log",
        );
        path = "document",
    )
    _string(object["schema_version"], "schema_version") == SOLVE_RESULT_WIRE_VERSION ||
        _protocol_error("schema_version", "expected $SOLVE_RESULT_WIRE_VERSION")
    canonical_json_bytes(object)
    exact = Tuple(
        _decode_exact_answer(value, string("exact_answers.", index - 1)) for
        (index, value) in enumerate(_array(object["exact_answers"], "exact_answers"))
    )
    provisional = Tuple(
        _decode_provisional_answer(value, string("provisional_answers.", index - 1)) for
        (index, value) in enumerate(_array(object["provisional_answers"], "provisional_answers"))
    )
    lock = _decode_environment_lock(object["environment_lock"], "environment_lock")
    for (index, answer) in enumerate(exact)
        string(answer.configuration_certificate.problem) == string(lock.graph) ||
            _protocol_error(string("exact_answers.", index - 1), "certificate problem differs from environment lock")
    end
    for (index, answer) in enumerate(provisional)
        string(answer.validation.problem) == string(lock.graph) ||
            _protocol_error(string("provisional_answers.", index - 1, ".validation"), "problem hash differs from environment lock")
    end
    evidence_raw = _object(object["evidence_log"], ("content_hash", "location"); path = "evidence_log")
    evidence = _construct("evidence_log", () -> EvidenceLogReference(
        _canonical_hash(evidence_raw["content_hash"], "evidence_log.content_hash"),
        _string(evidence_raw["location"], "evidence_log.location"),
    ))
    return _construct("document", () -> SolveResult(
        exact,
        provisional,
        _wire_enum(_SEARCH_FROM_WIRE, object["search_status"], "search_status"),
        _wire_enum(_TARGET_FROM_WIRE, object["target_image_status"], "target_image_status"),
        _decode_coverage(object["coverage"], "coverage"),
        lock,
        evidence,
    ))
end

decode_solve_result_json(source) = decode_solve_result_document(parse_protocol_json(source))

function _require_result_problem_binding(result::SolveResult)
    expected = string(result.environment_lock.graph)
    for (index, answer) in enumerate(result.exact_answers)
        string(answer.configuration_certificate.problem) == expected || _protocol_error(
            string("exact_answers.", index - 1, ".configuration_certificate.problem_hash"),
            "certificate problem differs from environment lock",
        )
        string(answer.target_certificate.problem) == expected || _protocol_error(
            string("exact_answers.", index - 1, ".target_certificate.problem_hash"),
            "certificate problem differs from environment lock",
        )
    end
    for (index, answer) in enumerate(result.provisional_answers)
        string(answer.validation.problem) == expected || _protocol_error(
            string("provisional_answers.", index - 1, ".validation.problem_hash"),
            "validation problem differs from environment lock",
        )
    end
    return nothing
end

function solve_result_document(result::SolveResult)
    _require_result_problem_binding(result)
    return Dict{String,Any}(
        "schema_version" => SOLVE_RESULT_WIRE_VERSION,
        "exact_answers" => Any[
            _exact_answer_document(answer, string("exact_answers.", index - 1)) for
            (index, answer) in enumerate(result.exact_answers)
        ],
        "provisional_answers" => Any[
            _provisional_answer_document(answer, string("provisional_answers.", index - 1)) for
            (index, answer) in enumerate(result.provisional_answers)
        ],
        "search_status" => _SEARCH_TO_WIRE[result.search_status],
        "target_image_status" => _TARGET_TO_WIRE[result.target_image_status],
        "coverage" => _coverage_document(result.coverage),
        "environment_lock" => _environment_lock_document(result.environment_lock),
        "evidence_log" => Dict{String,Any}(
            "content_hash" => string(result.evidence_log.content),
            "location" => result.evidence_log.location,
        ),
    )
end

encode_solve_result_json(result::SolveResult) = canonical_json(solve_result_document(result))

const _SMOOTHNESS_TO_WIRE = Dict(
    SMOOTHNESS_UNKNOWN => "unknown",
    SMOOTH_C1 => "smooth_c1",
    PIECEWISE_SMOOTH => "piecewise_smooth",
    LOCALLY_LIPSCHITZ => "locally_lipschitz",
    DECLARED_NONSMOOTH => "declared_nonsmooth",
)
const _DERIVATIVE_TO_WIRE = Dict(
    DERIVATIVE_NONE => "none",
    DERIVATIVE_AUTODIFF => "autodiff",
    DERIVATIVE_JACOBIAN => "jacobian",
    DERIVATIVE_JVP => "jvp",
    DERIVATIVE_VJP => "vjp",
)

function _kernel_document(kernel::OperatorKernel)
    return Dict{String,Any}(
        "capabilities" => Any[string(capability) for capability in kernel.capabilities],
        "smoothness" => _SMOOTHNESS_TO_WIRE[kernel.smoothness],
        "derivative_mode" => _DERIVATIVE_TO_WIRE[kernel.derivative_mode],
        "generic_numeric" => kernel.generic_numeric,
        "deterministic" => kernel.deterministic,
    )
end

function _signature_document(signature::SignatureSpec)
    keywords = Dict{String,Any}()
    for keyword in signature.keywords
        keywords[keyword.name] = Dict{String,Any}(
            "type_id" => string(keyword.type_id),
            "required" => keyword.required,
        )
    end
    return Dict{String,Any}(
        "arguments" => Any[string(value) for value in signature.arguments],
        "keywords" => keywords,
        "output" => string(signature.output),
        "variadic" => signature.variadic,
    )
end

_operation_base(spec) = Dict{String,Any}(
    "id" => string(spec.id),
    "signatures" => Any[_signature_document(signature) for signature in spec.signatures],
    "documentation" => spec.documentation,
)

function _operation_document(spec::PrimitiveSpec)
    value = _operation_base(spec)
    value["kernel"] = _kernel_document(spec.kernel)
    return value
end

function _operation_document(spec::RelationSpec)
    value = _operation_base(spec)
    value["residual_kernel"] = _kernel_document(spec.residual_kernel)
    value["truth_available"] = spec.truth !== nothing
    spec.scale_hint === nothing || (value["scale_hint"] = spec.scale_hint)
    return value
end

function _operation_document(spec::GuardSpec)
    value = _operation_base(spec)
    value["margin_kernel"] = _kernel_document(spec.margin_kernel)
    value["default_strict"] = spec.default_strict
    spec.scale_hint === nothing || (value["scale_hint"] = spec.scale_hint)
    return value
end


function _operation_document(spec::DomainSpec)
    value = _operation_base(spec)
    value["margin_kernel"] = _kernel_document(spec.margin_kernel)
    value["singularity_available"] = spec.singularity !== nothing
    value["default_strict"] = spec.default_strict
    return value
end

function _operation_document(spec::BranchSpec)
    value = _operation_base(spec)
    value["candidate_type"] = string(spec.candidate_type)
    value["kernel"] = _kernel_document(spec.kernel)
    return value
end

function _operation_document(spec::SelectorSpec)
    value = _operation_base(spec)
    value["kernel"] = _kernel_document(spec.kernel)
    return value
end

function plugin_manifest_document(plugin::PluginSpec)
    return Dict{String,Any}(
        "schema_version" => PLUGIN_WIRE_VERSION,
        "plugin_id" => string(plugin.id),
        "version" => string(plugin.version),
        "core_abi" => string(plugin.core_abi),
        "content_hash" => string(plugin.content),
        "types" => Any[
            Dict{String,Any}(
                "id" => string(type_spec.id),
                "literal_codec" => type_spec.encoder !== nothing,
                "documentation" => type_spec.documentation,
            ) for type_spec in plugin.types
        ],
        "primitives" => Any[_operation_document(spec) for spec in plugin.primitives],
        "relations" => Any[_operation_document(spec) for spec in plugin.relations],
        "guards" => Any[_operation_document(spec) for spec in plugin.guards],
        "domains" => Any[_operation_document(spec) for spec in plugin.domains],
        "branches" => Any[_operation_document(spec) for spec in plugin.branches],
        "selectors" => Any[_operation_document(spec) for spec in plugin.selectors],
    )
end

encode_plugin_manifest_json(plugin::PluginSpec) = canonical_json(plugin_manifest_document(plugin))

function decode_plugin_manifest_document(raw, registry::FrozenPluginRegistry)
    object = _object(
        raw,
        (
            "schema_version",
            "plugin_id",
            "version",
            "core_abi",
            "content_hash",
            "types",
            "primitives",
            "relations",
            "guards",
            "domains",
            "branches",
            "selectors",
        );
        path = "document",
    )
    _string(object["schema_version"], "schema_version") == PLUGIN_WIRE_VERSION ||
        _protocol_error("schema_version", "expected $PLUGIN_WIRE_VERSION")
    canonical_json_bytes(object)
    id = _canonical_id(PluginId, object["plugin_id"], "plugin_id")
    plugin = _plugin_for(registry, id, "plugin_id")
    expected = plugin_manifest_document(plugin)
    canonical_json_bytes(object) == canonical_json_bytes(expected) || _protocol_error(
        "document",
        "manifest is not the exact metadata projection of the allowlisted PluginSpec",
    )
    return plugin
end

decode_plugin_manifest_json(source, registry::FrozenPluginRegistry) =
    decode_plugin_manifest_document(parse_protocol_json(source), registry)

function validate_protocol_json(source, registry::FrozenPluginRegistry)
    document = parse_protocol_json(source)
    document isa Dict{String,Any} || _protocol_error("document", "must be an object")
    version = _string(get(document, "schema_version", nothing), "schema_version")
    if version == PROBLEM_WIRE_VERSION
        decode_problem_document(document, registry)
    elseif version == PLUGIN_WIRE_VERSION
        decode_plugin_manifest_document(document, registry)
    elseif version == SOLVE_RESULT_WIRE_VERSION
        decode_solve_result_document(document)
    else
        _protocol_error("schema_version", "unsupported schema version $(repr(version))")
    end
    return version, document
end
