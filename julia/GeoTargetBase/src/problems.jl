const PROBLEM_SCHEMA_VERSION = v"1.0.0"

"""One real-valued solve variable with explicit origin and scale."""
struct VariableSpec{T<:Real}
    id::VariableId
    type_id::TypeId
    lower::Union{Nothing,T}
    upper::Union{Nothing,T}
    origin::T
    scale::T

    function VariableSpec(
        id::VariableId,
        type_id::TypeId,
        origin::T,
        scale::T;
        lower::Union{Nothing,T} = nothing,
        upper::Union{Nothing,T} = nothing,
    ) where {T<:Real}
        _is_finite(origin) || throw(
            InvariantError(:invalid_variable_origin, "variable origin must be finite"),
        )
        _is_finite(scale) && scale > zero(T) || throw(
            InvariantError(:invalid_variable_scale, "variable scale must be finite and positive"),
        )
        lower !== nothing && !_is_finite(lower) && throw(
            InvariantError(:invalid_variable_bound, "a finite lower bound is required when present"),
        )
        upper !== nothing && !_is_finite(upper) && throw(
            InvariantError(:invalid_variable_bound, "a finite upper bound is required when present"),
        )
        lower !== nothing && upper !== nothing && lower >= upper && throw(
            InvariantError(:invalid_variable_bounds, "lower bound must be strictly below upper bound"),
        )
        lower !== nothing && origin < lower && throw(
            InvariantError(:origin_outside_bounds, "variable origin lies below its lower bound"),
        )
        upper !== nothing && origin > upper && throw(
            InvariantError(:origin_outside_bounds, "variable origin lies above its upper bound"),
        )
        return new{T}(id, type_id, lower, upper, deepcopy(origin), deepcopy(scale))
    end
end

_is_finite(value::Real) = isfinite(value)

struct RelationBinding
    node::NodeId
    scale_override::Union{Nothing,Float64}

    function RelationBinding(node::NodeId; scale_override::Union{Nothing,Real} = nothing)
        return new(node, _validate_scale_hint(scale_override))
    end
end

struct GuardBinding
    node::NodeId
    strict::Bool
    scale_override::Union{Nothing,Float64}

    function GuardBinding(
        node::NodeId,
        strict::Bool;
        scale_override::Union{Nothing,Real} = nothing,
    )
        return new(node, strict, _validate_scale_hint(scale_override))
    end
end

struct DomainBinding
    node::NodeId
    strict::Bool
end

"""Canonical v1 problem contract; semantic operator roles remain disjoint."""
struct ProblemSpecV1{L<:Tuple,V<:Tuple,G<:ConstructionGraph,R<:Tuple,U<:Tuple,D<:Tuple}
    plugin_locks::L
    variables::V
    graph::G
    relations::R
    guards::U
    domains::D
    target::NodeId

    function ProblemSpecV1(
        plugin_locks,
        variables,
        graph::ConstructionGraph;
        relations = (),
        guards = (),
        domains = (),
        target::NodeId,
    )
        frozen_locks = tuple((lock::PluginLock for lock in plugin_locks)...)
        frozen_variables = tuple((variable::VariableSpec for variable in variables)...)
        frozen_relations = tuple((binding::RelationBinding for binding in relations)...)
        frozen_guards = tuple((binding::GuardBinding for binding in guards)...)
        frozen_domains = tuple((binding::DomainBinding for binding in domains)...)

        allunique(map(lock -> lock.id, frozen_locks)) || throw(
            InvariantError(:duplicate_plugin_lock, "a problem may lock each plugin only once"),
        )
        variable_ids = map(variable -> variable.id, frozen_variables)
        allunique(variable_ids) || throw(
            InvariantError(:duplicate_variable_id, "a problem may declare each variable only once"),
        )

        locked_plugins = Set(lock.id for lock in frozen_locks)
        for variable in frozen_variables
            variable.type_id.plugin in locked_plugins || throw(
                InvariantError(
                    :unlocked_type,
                    "variable $(variable.id) uses a type from an unlocked plugin",
                ),
            )
        end

        node_ids = Set(node_id(node) for node in graph)
        for node in graph
            if node isa ReferenceNode
                node.variable in variable_ids || throw(
                    InvariantError(
                        :unknown_variable_reference,
                        "ReferenceNode $(node.id) uses undeclared variable $(node.variable)",
                    ),
                )
            elseif node isa LiteralNode
                node.type_id.plugin in locked_plugins || throw(
                    InvariantError(:unlocked_type, "LiteralNode $(node.id) uses an unlocked type"),
                )
            elseif node isa CallNode
                node.operation.plugin in locked_plugins || throw(
                    InvariantError(:unlocked_operation, "CallNode $(node.id) uses an unlocked operation"),
                )
            elseif node isa SelectNode
                node.selector.plugin in locked_plugins || throw(
                    InvariantError(:unlocked_selector, "SelectNode $(node.id) uses an unlocked selector"),
                )
            end
        end

        role_ids = (
            (binding.node for binding in frozen_relations)...,
            (binding.node for binding in frozen_guards)...,
            (binding.node for binding in frozen_domains)...,
            target,
        )
        for id in role_ids
            id in node_ids || throw(
                InvariantError(:unknown_role_node, "problem role references unknown node $(string(id))"),
            )
        end
        allunique(role_ids) || throw(
            InvariantError(
                :overlapping_semantic_roles,
                "relation, guard, domain and target node roles must be disjoint",
            ),
        )

        return new{
            typeof(frozen_locks),
            typeof(frozen_variables),
            typeof(graph),
            typeof(frozen_relations),
            typeof(frozen_guards),
            typeof(frozen_domains),
        }(
            frozen_locks,
            frozen_variables,
            graph,
            frozen_relations,
            frozen_guards,
            frozen_domains,
            target,
        )
    end
end
