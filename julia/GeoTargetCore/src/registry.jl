@enum OperationRole::UInt8 begin
    ROLE_PRIMITIVE = 0
    ROLE_RELATION = 1
    ROLE_GUARD = 2
    ROLE_DOMAIN = 3
    ROLE_BRANCH = 4
end

struct ResolvedOperation
    role::OperationRole
    spec::Any
end

"""Solve-local mutable builder; mutation is impossible after `freeze`."""
mutable struct RegistryBuilder
    core_abi::VersionNumber
    plugins::Vector{PluginSpec}
    allowlist::Union{Nothing,Set{PluginId}}
    frozen::Bool

    function RegistryBuilder(
        ;
        core_abi::VersionNumber = CORE_ABI_VERSION,
        allowlist = nothing,
    )
        allowed = allowlist === nothing ? nothing : Set{PluginId}(allowlist)
        return new(core_abi, PluginSpec[], allowed, false)
    end
end

"""Immutable registry captured by one compile/solve context."""
struct FrozenPluginRegistry
    core_abi::VersionNumber
    plugins::Tuple
end

registered_plugins(registry::FrozenPluginRegistry) = registry.plugins

function register!(builder::RegistryBuilder, plugin::PluginSpec)
    builder.frozen && throw(
        RegistryError(:registry_frozen, "a RegistryBuilder cannot change after freeze"),
    )
    plugin.core_abi == builder.core_abi || throw(
        RegistryError(
            :core_abi_mismatch,
            "plugin $(plugin.id) requires $(plugin.core_abi), registry provides $(builder.core_abi)",
        ),
    )
    builder.allowlist !== nothing && plugin.id ∉ builder.allowlist && throw(
        RegistryError(:plugin_not_allowed, "plugin $(plugin.id) is not in the explicit allowlist"),
    )
    any(existing -> existing.id == plugin.id, builder.plugins) && throw(
        RegistryError(:duplicate_plugin, "plugin $(plugin.id) is already registered"),
    )
    push!(builder.plugins, plugin)
    return builder
end

function freeze(builder::RegistryBuilder)
    builder.frozen && throw(
        RegistryError(:registry_frozen, "this RegistryBuilder has already been frozen"),
    )
    _validate_registry(builder.plugins)
    builder.frozen = true
    ordered = Tuple(sort(copy(builder.plugins); by = plugin -> string(plugin.id)))
    return FrozenPluginRegistry(builder.core_abi, ordered)
end

function _validate_registry(plugins)
    type_ids = Set{TypeId}()
    type_specs = Dict{TypeId,Any}()
    for plugin in plugins, type_spec in plugin.types
        type_spec.id in type_ids && throw(
            RegistryError(:duplicate_type, "type $(type_spec.id) is registered twice"),
        )
        (type_spec.julia_type isa Type || type_spec.julia_type isa UnionAll) || throw(
            RegistryError(
                :invalid_julia_type,
                "TypeSpec $(type_spec.id) must contain a Julia Type or UnionAll",
            ),
        )
        push!(type_ids, type_spec.id)
        type_specs[type_spec.id] = type_spec
    end

    for plugin in plugins
        for operation in (
            plugin.primitives...,
            plugin.relations...,
            plugin.guards...,
            plugin.domains...,
            plugin.branches...,
            plugin.selectors...,
        )
            for signature in operation.signatures
                for type_id in signature.arguments
                    type_id in type_ids || throw(
                        RegistryError(
                            :unknown_signature_type,
                            "operation $(operation.id) refers to unregistered type $type_id",
                        ),
                    )
                end
                for keyword in signature.keywords
                    keyword.type_id in type_ids || throw(
                        RegistryError(
                            :unknown_signature_type,
                            "operation $(operation.id) refers to unregistered type $(keyword.type_id)",
                        ),
                    )
                end
                signature.output in type_ids || throw(
                    RegistryError(
                        :unknown_signature_type,
                        "operation $(operation.id) returns unregistered type $(signature.output)",
                    ),
                )
            end
        end
        for branch in plugin.branches
            branch.candidate_type in type_ids || throw(
                RegistryError(
                    :unknown_branch_candidate_type,
                    "branch $(branch.id) declares unregistered candidate type $(branch.candidate_type)",
                ),
            )
            for signature in branch.signatures
                output_spec = type_specs[signature.output]
                output_spec.julia_type <: Choice || throw(
                    RegistryError(
                        :invalid_branch_output_type,
                        "branch $(branch.id) signatures must return a registered Choice type",
                    ),
                )
            end
        end
    end
    return nothing
end

function _find_plugin(registry::FrozenPluginRegistry, id::PluginId)
    index = findfirst(plugin -> plugin.id == id, registry.plugins)
    return index === nothing ? nothing : registry.plugins[index]
end

function resolve_type(registry::FrozenPluginRegistry, id::TypeId)
    plugin = _find_plugin(registry, id.plugin)
    plugin === nothing && return nothing
    index = findfirst(spec -> spec.id == id, plugin.types)
    return index === nothing ? nothing : plugin.types[index]
end

function resolve_operation(registry::FrozenPluginRegistry, id::PrimitiveId)
    plugin = _find_plugin(registry, id.plugin)
    plugin === nothing && return nothing
    for (role, collection) in (
        (ROLE_PRIMITIVE, plugin.primitives),
        (ROLE_RELATION, plugin.relations),
        (ROLE_GUARD, plugin.guards),
        (ROLE_DOMAIN, plugin.domains),
        (ROLE_BRANCH, plugin.branches),
    )
        index = findfirst(spec -> spec.id == id, collection)
        index === nothing || return ResolvedOperation(role, collection[index])
    end
    return nothing
end

function resolve_selector(registry::FrozenPluginRegistry, id::SelectorId)
    plugin = _find_plugin(registry, id.plugin)
    plugin === nothing && return nothing
    index = findfirst(spec -> spec.id == id, plugin.selectors)
    return index === nothing ? nothing : plugin.selectors[index]
end

function _plugin_matches_lock(plugin::PluginSpec, lock::PluginLock)
    return plugin.id == lock.id &&
           plugin.version == lock.version &&
           plugin.core_abi == lock.core_abi &&
           plugin.content == lock.content
end
