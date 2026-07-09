abstract type AbstractGraphNode end

"""A typed literal. The payload is defensively copied at construction."""
struct LiteralNode{T} <: AbstractGraphNode
    id::NodeId
    type_id::TypeId
    value::T

    function LiteralNode(id::NodeId, type_id::TypeId, value)
        frozen = deepcopy(value)
        return new{typeof(frozen)}(id, type_id, frozen)
    end
end

"""A reference to one declared real input variable."""
struct ReferenceNode <: AbstractGraphNode
    id::NodeId
    variable::VariableId
end

"""One canonical keyword edge in a Call or Select node."""
struct KeywordArg
    name::String
    value::NodeId

    function KeywordArg(name::AbstractString, value::NodeId)
        return new(_canonical_name(name, "keyword name"), value)
    end
end

Base.isless(left::KeywordArg, right::KeywordArg) = isless(left.name, right.name)

function _canonical_keywords(keywords)
    frozen = tuple((keyword isa KeywordArg ? keyword : KeywordArg(keyword...) for keyword in keywords)...)
    ordered = Tuple(sort(collect(frozen); by = keyword -> keyword.name))
    names = map(keyword -> keyword.name, ordered)
    allunique(names) || throw(
        InvariantError(:duplicate_keyword, "keyword names must be unique within a node"),
    )
    return ordered
end

"""A call to one plugin-qualified operation."""
struct CallNode{A<:Tuple,K<:Tuple} <: AbstractGraphNode
    id::NodeId
    operation::PrimitiveId
    arguments::A
    keywords::K

    function CallNode(
        id::NodeId,
        operation::PrimitiveId,
        arguments = (),
        keywords = (),
    )
        frozen_arguments = tuple((argument isa NodeId ? argument : NodeId(argument) for argument in arguments)...)
        frozen_keywords = _canonical_keywords(keywords)
        return new{typeof(frozen_arguments),typeof(frozen_keywords)}(
            id,
            operation,
            frozen_arguments,
            frozen_keywords,
        )
    end
end

"""A generic plugin selector applied to a Choice-producing node."""
struct SelectNode{A<:Tuple,K<:Tuple} <: AbstractGraphNode
    id::NodeId
    choice::NodeId
    selector::SelectorId
    arguments::A
    keywords::K

    function SelectNode(
        id::NodeId,
        choice::NodeId,
        selector::SelectorId,
        arguments = (),
        keywords = (),
    )
        frozen_arguments = tuple((argument isa NodeId ? argument : NodeId(argument) for argument in arguments)...)
        frozen_keywords = _canonical_keywords(keywords)
        return new{typeof(frozen_arguments),typeof(frozen_keywords)}(
            id,
            choice,
            selector,
            frozen_arguments,
            frozen_keywords,
        )
    end
end

node_id(node::AbstractGraphNode) = node.id

referenced_nodes(::LiteralNode) = ()
referenced_nodes(::ReferenceNode) = ()
referenced_nodes(node::CallNode) =
    (node.arguments..., (keyword.value for keyword in node.keywords)...)
referenced_nodes(node::SelectNode) =
    (node.choice, node.arguments..., (keyword.value for keyword in node.keywords)...)

"""
Canonical topologically ordered construction graph.

Every edge must point to an earlier node. This gives deterministic traversal and
prevents cycles before plugin typing or numerical compilation begins.
"""
struct ConstructionGraph{N<:Tuple}
    nodes::N

    function ConstructionGraph(nodes)
        frozen = tuple((deepcopy(node) for node in nodes)...)
        all(node -> node isa AbstractGraphNode, frozen) || throw(
            InvariantError(:invalid_graph_node, "all graph entries must be AbstractGraphNode values"),
        )

        seen = Set{NodeId}()
        for node in frozen
            id = node_id(node)
            id in seen && throw(
                InvariantError(:duplicate_node_id, "graph node $(string(id)) is declared more than once"),
            )
            for dependency in referenced_nodes(node)
                dependency in seen || throw(
                    InvariantError(
                        :non_topological_edge,
                        "node $(string(id)) references $(string(dependency)) before it is declared",
                    ),
                )
            end
            push!(seen, id)
        end
        return new{typeof(frozen)}(frozen)
    end
end

Base.length(graph::ConstructionGraph) = length(graph.nodes)
Base.isempty(graph::ConstructionGraph) = isempty(graph.nodes)
Base.iterate(graph::ConstructionGraph, state...) = iterate(graph.nodes, state...)
Base.getindex(graph::ConstructionGraph, index::Int) = graph.nodes[index]
