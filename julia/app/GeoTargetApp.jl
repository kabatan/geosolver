module GeoTargetApp

using GeoTargetBase
using GeoTargetCore
using GeoTargetGeometry

if !isdefined(GeoTargetCore, :decode_problem_json)
    Base.include(
        GeoTargetCore,
        normpath(joinpath(@__DIR__, "..", "GeoTargetCore", "src", "protocol_json.jl")),
    )
end

function default_registry()
    plugin = GeoTargetGeometry.geometry_plugin()
    builder = RegistryBuilder(allowlist = (plugin.id,))
    register!(builder, plugin)
    return freeze(builder)
end

function _status_text(status::EvalStatus)
    status == EVAL_OK && return "ok"
    status == EVAL_INVALID_DOMAIN && return "invalid_domain"
    status == EVAL_NONFINITE && return "nonfinite"
    status == EVAL_UNSUPPORTED_CAPABILITY && return "unsupported_capability"
    status == EVAL_PLUGIN_ERROR && return "plugin_error"
    status == EVAL_INVALID_BRANCH && return "invalid_branch"
    status == EVAL_AMBIGUOUS_BRANCH && return "ambiguous_branch"
    return "unknown"
end

_number(value, path) = GeoTargetCore._result_number_document(value, path)

function _observation_document(observation::OracleObservation)
    return Dict{String,Any}(
        "status" => _status_text(observation.status),
        "target" => observation.target === nothing ? nothing : _number(observation.target, "target"),
        "evaluation_cost" => observation.evaluation_cost,
        "diagnostic" => observation.diagnostic,
        "relations" => Any[
            Dict{String,Any}(
                "node" => string(value.node),
                "raw" => _number(value.raw, "relations.raw"),
                "scale" => _number(value.scale, "relations.scale"),
                "scaled" => _number(value.scaled, "relations.scaled"),
                "truth" => value.truth,
            ) for value in observation.relations
        ],
        "guards" => Any[
            Dict{String,Any}(
                "node" => string(value.node),
                "margin" => _number(value.margin, "guards.margin"),
                "strict" => value.strict,
                "scale" => _number(value.scale, "guards.scale"),
                "valid" => value.valid,
            ) for value in observation.guards
        ],
        "domains" => Any[
            Dict{String,Any}(
                "node" => string(value.node),
                "margin" => _number(value.margin, "domains.margin"),
                "strict" => value.strict,
                "valid" => value.valid,
            ) for value in observation.domains
        ],
        "branches" => Any[
            Dict{String,Any}(
                "choice_node" => string(value.decision.choice_node),
                "key" => string(value.decision.key),
                "validity_margin" => _number(value.validity_margin, "branches.validity_margin"),
                "selector_margin" => _number(value.selector_margin, "branches.selector_margin"),
            ) for value in observation.branches
        ],
    )
end

function _parse_x(text::AbstractString)
    stripped = strip(text)
    values = if startswith(stripped, '[')
        document = GeoTargetCore.parse_protocol_json(stripped)
        document isa Vector{Any} || throw(ArgumentError("--x JSON form must be an array"))
        document
    elseif isempty(stripped)
        Any[]
    else
        Any[strip(value) for value in split(stripped, ',')]
    end
    return Float64[
        value isa Real && !(value isa Bool) ? Float64(value) : parse(Float64, String(value)) for
        value in values
    ]
end

function _validate(path, registry, output)
    source = read(path, String)
    version, document = GeoTargetCore.validate_protocol_json(source, registry)
    summary = Dict{String,Any}(
        "schema_version" => version,
        "content_hash" => string(GeoTargetCore.canonical_json_hash(document)),
    )
    println(output, GeoTargetCore.canonical_json(summary))
    return 0
end

function _eval(path, x_text, registry, output)
    problem = GeoTargetCore.decode_problem_json(read(path, String), registry)
    observation = evaluate_reference(problem, registry, _parse_x(x_text))
    println(output, GeoTargetCore.canonical_json(_observation_document(observation)))
    return 0
end

function _plugin_info(id_text, registry, output)
    plugins = collect(registered_plugins(registry))
    if id_text === nothing
        document = Dict{String,Any}(
            "plugins" => Any[GeoTargetCore.plugin_manifest_document(plugin) for plugin in plugins],
        )
        println(output, GeoTargetCore.canonical_json(document))
        return 0
    end
    id = try
        parse(PluginId, id_text)
    catch error
        throw(ArgumentError("invalid plugin id: $(sprint(showerror, error))"))
    end
    string(id) == id_text || throw(ArgumentError("plugin id is not canonical"))
    index = findfirst(plugin -> plugin.id == id, plugins)
    index === nothing && throw(ArgumentError("plugin is not in the explicit registry allowlist"))
    println(output, GeoTargetCore.encode_plugin_manifest_json(plugins[index]))
    return 0
end

function _usage(io)
    println(io, "usage:")
    println(io, "  geotarget validate <document.json>")
    println(io, "  geotarget eval <problem.json> --x <comma-separated-values|JSON-array>")
    println(io, "  geotarget plugin-info [canonical-plugin-id]")
end

function main(
    args = ARGS;
    registry::FrozenPluginRegistry = default_registry(),
    stdout::IO = Base.stdout,
    stderr::IO = Base.stderr,
)
    try
        isempty(args) && (_usage(stderr); return 2)
        command = args[1]
        if command == "validate"
            length(args) == 2 || throw(ArgumentError("validate expects one document path"))
            return _validate(args[2], registry, stdout)
        elseif command == "eval"
            length(args) == 4 || throw(ArgumentError("eval expects <problem.json> --x <values>"))
            args[3] == "--x" || throw(ArgumentError("eval requires --x"))
            return _eval(args[2], args[4], registry, stdout)
        elseif command == "plugin-info"
            length(args) <= 2 || throw(ArgumentError("plugin-info accepts at most one plugin id"))
            return _plugin_info(length(args) == 2 ? args[2] : nothing, registry, stdout)
        end
        throw(ArgumentError("unknown command $(repr(command)); solve is intentionally unavailable"))
    catch error
        println(stderr, "error: ", sprint(showerror, error))
        return 2
    end
end

end
