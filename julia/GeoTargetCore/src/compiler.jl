"""Content-addressed identity for one immutable typed plan."""
struct CompilerError <: CoreError
    code::Symbol
    message::String
end

Base.showerror(io::IO, error::CompilerError) =
    print(io, "GeoTarget compiler ", error.code, ": ", error.message)

struct CompiledCacheIdentity
    key::ContentHash
    problem::ContentHash
    plugin_locks::Tuple
    core_abi::VersionNumber
    julia_version::VersionNumber
    numeric_backend::String
    persistent::Bool
end

struct CompileStats
    source_nodes::Int
    live_nodes::Int
    dead_nodes::Int
    constant_folds::Int
    cse_hits::Int
    runtime_calls::Int
end

"""Variable dependency and residual Jacobian sparsity in declared variable indexes."""
struct CompiledSparsity
    node_variables::Tuple
    relation_variables::Tuple
    guard_variables::Tuple
    domain_variables::Tuple
    target_variables::Tuple
    jacobian_entries::Tuple
end

struct CompiledVariable
    spec::VariableSpec
    index::Int
    runtime_type::Any
end

struct CompiledRelationRole
    node::NodeId
    slot::Int
    scale::Float64
    truth::Any
    argument_slots::Tuple
    keyword_slots::Tuple
end

struct CompiledGuardRole
    node::NodeId
    slot::Int
    strict::Bool
    scale::Float64
end

struct CompiledDomainRole
    node::NodeId
    slot::Int
    strict::Bool
end

abstract type AbstractPlanInstruction end

struct ConstantInstruction <: AbstractPlanInstruction
    node::NodeId
    slot::Int
    value::Any
    type_id::TypeId
    runtime_type::Any
    logical_kernel::Any
    logical_cost::Int
end

struct VariableInstruction <: AbstractPlanInstruction
    node::NodeId
    slot::Int
    variable_index::Int
    type_id::TypeId
    runtime_type::Any
end

struct AliasInstruction <: AbstractPlanInstruction
    node::NodeId
    slot::Int
    source_slot::Int
    type_id::TypeId
    runtime_type::Any
    logical_kernel::Any
    logical_cost::Int
end

struct CallInstruction <: AbstractPlanInstruction
    node::NodeId
    slot::Int
    operation::PrimitiveId
    role::OperationRole
    spec::Any
    kernel::OperatorKernel
    signature::SignatureSpec
    argument_slots::Tuple
    keyword_slots::Tuple
    type_id::TypeId
    runtime_type::Any
end

struct SelectInstruction <: AbstractPlanInstruction
    node::NodeId
    slot::Int
    choice_node::NodeId
    selector::SelectorId
    spec::SelectorSpec
    kernel::OperatorKernel
    signature::SignatureSpec
    choice_slot::Int
    argument_slots::Tuple
    keyword_slots::Tuple
    type_id::TypeId
    runtime_type::Any
end

"""Immutable pre-resolved execution plan. `registry` is retained only for canonical replay."""
struct CompiledProblem
    problem::ProblemSpecV1
    registry::FrozenPluginRegistry
    instructions::Tuple
    slot_count::Int
    node_indexes::Tuple
    node_slots::Tuple
    variables::Tuple
    relations::Tuple
    guards::Tuple
    domains::Tuple
    target_slot::Int
    target_type::TypeId
    target_runtime_type::Any
    sparsity::CompiledSparsity
    stats::CompileStats
    cache_identity::CompiledCacheIdentity
    available_capabilities::CapabilitySet
    logical_evaluation_cost::Int
end

function _compiled_lookup(pairs::Tuple, key)
    index = findfirst(pair -> first(pair) == key, pairs)
    index === nothing && throw(
        CompilerError(:missing_metadata, "compiled metadata has no key $key"),
    )
    return last(pairs[index])
end

_stable_type_name(type) = string(parentmodule(type), '.', type)

function _stable_write(io::IO, value, persistent::Base.RefValue{Bool})
    return _stable_write(io, value, persistent, IdDict{Any,Int}())
end

function _stable_write(io::IO, value, persistent::Base.RefValue{Bool}, seen::IdDict)
    if value === nothing
        print(io, "N;")
    elseif value isa Bool
        print(io, "B", value ? '1' : '0', ';')
    elseif value isa AbstractFloat
        print(io, "F", _stable_type_name(typeof(value)), ':')
        value isa BigFloat && print(io, precision(value), ':')
        print(io, repr(value), ';')
    elseif value isa Integer
        print(io, "I", _stable_type_name(typeof(value)), ':', value, ';')
    elseif value isa Rational
        print(io, "Q")
        _stable_write(io, numerator(value), persistent, seen)
        _stable_write(io, denominator(value), persistent, seen)
    elseif value isa AbstractString
        print(io, "S", _stable_type_name(typeof(value)), ':', ncodeunits(value), ':', value, ';')
    elseif value isa Symbol
        rendered = String(value)
        print(io, "Y", ncodeunits(rendered), ':', rendered, ';')
    elseif value isa VersionNumber
        print(io, "V", value, ';')
    elseif value isa ContentHash || value isa PluginId || value isa TypeId ||
           value isa PrimitiveId || value isa SelectorId || value isa NodeId ||
           value isa VariableId || value isa ChoiceKey
        print(io, "D", nameof(typeof(value)), ':', string(value), ';')
    elseif value isa NamedTuple
        print(io, "M")
        _stable_write(io, keys(value), persistent, seen)
        _stable_write(io, values(value), persistent, seen)
    elseif value isa Tuple
        print(io, "T", _stable_type_name(typeof(value)), ':', length(value), '[')
        for item in value
            _stable_write(io, item, persistent, seen)
        end
        print(io, "]")
    elseif value isa Pair
        print(io, "P")
        _stable_write(io, first(value), persistent, seen)
        _stable_write(io, last(value), persistent, seen)
    elseif value isa AbstractArray
        persistent[] = false
        if haskey(seen, value)
            print(io, "Z", seen[value], ';')
            return nothing
        end
        identity = length(seen) + 1
        seen[value] = identity
        print(io, "A", identity, ':', _stable_type_name(typeof(value)), ':', size(value), '[')
        for item in value
            _stable_write(io, item, persistent, seen)
        end
        print(io, "]")
    elseif isstructtype(typeof(value)) && !Base.ismutable(value)
        print(io, "R", _stable_type_name(typeof(value)), '{')
        for index in 1:fieldcount(typeof(value))
            _stable_write(io, getfield(value, index), persistent, seen)
        end
        print(io, "}")
    else
        persistent[] = false
        rendered = repr(value)
        print(io, "X", _stable_type_name(typeof(value)), ':', objectid(value), ':')
        print(io, ncodeunits(rendered), ':', rendered, ';')
    end
    return nothing
end

function _problem_digest(problem::ProblemSpecV1)
    io = IOBuffer()
    persistent = Ref(true)
    print(io, "ProblemSpecV1|")
    locks = Tuple(sort(collect(problem.plugin_locks); by = lock -> string(lock.id)))
    for lock in locks
        _stable_write(io, lock.id, persistent)
        _stable_write(io, lock.version, persistent)
        _stable_write(io, lock.core_abi, persistent)
        _stable_write(io, lock.content, persistent)
    end
    for variable in problem.variables
        _stable_write(io, variable.id, persistent)
        _stable_write(io, variable.type_id, persistent)
        _stable_write(io, variable.lower, persistent)
        _stable_write(io, variable.upper, persistent)
        _stable_write(io, variable.origin, persistent)
        _stable_write(io, variable.scale, persistent)
    end
    for node in problem.graph
        _stable_write(io, node.id, persistent)
        if node isa LiteralNode
            print(io, "literal|")
            _stable_write(io, node.type_id, persistent)
            _stable_write(io, node.value, persistent)
        elseif node isa ReferenceNode
            print(io, "reference|")
            _stable_write(io, node.variable, persistent)
        elseif node isa CallNode
            print(io, "call|")
            _stable_write(io, node.operation, persistent)
            _stable_write(io, node.arguments, persistent)
            _stable_write(io, Tuple(keyword.name => keyword.value for keyword in node.keywords), persistent)
        elseif node isa SelectNode
            print(io, "select|")
            _stable_write(io, node.choice, persistent)
            _stable_write(io, node.selector, persistent)
            _stable_write(io, node.arguments, persistent)
            _stable_write(io, Tuple(keyword.name => keyword.value for keyword in node.keywords), persistent)
        end
    end
    for binding in problem.relations
        print(io, "relation|")
        _stable_write(io, binding.node, persistent)
        _stable_write(io, binding.scale_override, persistent)
    end
    for binding in problem.guards
        print(io, "guard|")
        _stable_write(io, binding.node, persistent)
        _stable_write(io, binding.strict, persistent)
        _stable_write(io, binding.scale_override, persistent)
    end
    for binding in problem.domains
        print(io, "domain|")
        _stable_write(io, binding.node, persistent)
        _stable_write(io, binding.strict, persistent)
    end
    print(io, "target|")
    _stable_write(io, problem.target, persistent)
    return content_hash(String(take!(io))), persistent[]
end

function _cache_identity(problem, registry, numeric_backend::AbstractString)
    problem_digest, persistent = _problem_digest(problem)
    io = IOBuffer()
    print(io, string(problem_digest), '|', registry.core_abi, '|', VERSION, '|', numeric_backend)
    locks = Tuple(sort(collect(problem.plugin_locks); by = lock -> string(lock.id)))
    for lock in locks
        print(io, '|', string(lock.id), '@', lock.version, '/', lock.core_abi, '/', string(lock.content))
    end
    return CompiledCacheIdentity(
        content_hash(String(take!(io))),
        problem_digest,
        locks,
        registry.core_abi,
        VERSION,
        String(numeric_backend),
        persistent,
    )
end

function _mark_dependencies!(live::BitVector, graph, indexes, root::NodeId)
    stack = NodeId[root]
    while !isempty(stack)
        id = pop!(stack)
        index = indexes[id]
        live[index] && continue
        live[index] = true
        append!(stack, referenced_nodes(graph[index]))
    end
    return nothing
end

function _safe_live_mask(problem::ProblemSpecV1, indexes)
    live = falses(length(problem.graph))
    for id in (
        (binding.node for binding in problem.relations)...,
        (binding.node for binding in problem.guards)...,
        (binding.node for binding in problem.domains)...,
        problem.target,
    )
        _mark_dependencies!(live, problem.graph, indexes, id)
    end

    # Calls and selectors are status-bearing plugin boundaries. Until the ABI has
    # an explicit total/pure flag, preserve every otherwise-dead boundary and its
    # dependencies; only provably inert structural nodes are eliminated.
    for node in problem.graph
        boundary = node isa CallNode || node isa SelectNode
        stateful_literal = node isa LiteralNode && !_deeply_immutable(node.value)
        if (boundary || stateful_literal) && !live[indexes[node.id]]
            _mark_dependencies!(live, problem.graph, indexes, node.id)
        end
    end
    return live
end

function _node_variable_dependencies(problem, variable_indexes)
    dependencies = Vector{BitSet}(undef, length(problem.graph))
    indexes = Dict(node.id => index for (index, node) in enumerate(problem.graph))
    for (index, node) in enumerate(problem.graph)
        current = BitSet()
        if node isa ReferenceNode
            push!(current, variable_indexes[node.variable])
        else
            for dependency in referenced_nodes(node)
                union!(current, dependencies[indexes[dependency]])
            end
        end
        dependencies[index] = current
    end
    return dependencies, indexes
end

function _compiled_sparsity(problem, dependencies, indexes, live)
    dependency_tuple(id) = Tuple(sort!(collect(dependencies[indexes[id]])))
    node_variables = Tuple(
        node.id => dependency_tuple(node.id) for
        (index, node) in enumerate(problem.graph) if live[index]
    )
    relation_variables = Tuple(binding.node => dependency_tuple(binding.node) for binding in problem.relations)
    guard_variables = Tuple(binding.node => dependency_tuple(binding.node) for binding in problem.guards)
    domain_variables = Tuple(binding.node => dependency_tuple(binding.node) for binding in problem.domains)
    target_variables = dependency_tuple(problem.target)
    jacobian_entries = Tuple(
        (row, variable) for (row, binding) in enumerate(problem.relations) for
        variable in dependency_tuple(binding.node)
    )
    return CompiledSparsity(
        node_variables,
        relation_variables,
        guard_variables,
        domain_variables,
        target_variables,
        jacobian_entries,
    )
end

function _matched_signature(node::CallNode, resolved, report)
    arguments = Tuple(node_type(report, id) for id in node.arguments)
    keywords = Tuple((keyword.name, node_type(report, keyword.value)) for keyword in node.keywords)
    matched = _matching_signature(resolved.spec.signatures, arguments, keywords)
    matched isa SignatureSpec || throw(
        CompilerError(:signature_invariant, "validated call has no unique signature"),
    )
    return matched
end

function _matched_signature(node::SelectNode, selector, report)
    arguments = Tuple(node_type(report, id) for id in (node.choice, node.arguments...))
    keywords = Tuple((keyword.name, node_type(report, keyword.value)) for keyword in node.keywords)
    matched = _matching_signature(selector.signatures, arguments, keywords)
    matched isa SignatureSpec || throw(
        CompilerError(:signature_invariant, "validated selector has no unique signature"),
    )
    return matched
end

function _slot_arguments(ids, slots)
    return Tuple(slots[id] for id in ids)
end

function _slot_keywords(keywords, slots)
    return Tuple(Symbol(keyword.name) => slots[keyword.value] for keyword in keywords)
end

function _constant_kwargs(keyword_slots, values)
    return (; (name => values[slot] for (name, slot) in keyword_slots)...)
end

function _deeply_immutable(value)
    Base.ismutable(value) && return false
    type = typeof(value)
    isstructtype(type) || return true
    for index in 1:fieldcount(type)
        _deeply_immutable(getfield(value, index)) || return false
    end
    return true
end

function _logical_capabilities(kernels)
    bits = UInt8(0x1f)
    for kernel in kernels
        bits &= kernel.capabilities.bits
    end
    return CapabilitySet(bits)
end

function _folding_preserves_value_routes(kernel::OperatorKernel)
    kernel.generic_numeric && return true
    return !supports(kernel.capabilities, C2) && !supports(kernel.capabilities, C3V)
end

function compile_problem(
    problem::ProblemSpecV1,
    registry::FrozenPluginRegistry;
    numeric_backend::AbstractString = "generic",
)
    isempty(strip(numeric_backend)) && throw(
        CompilerError(:invalid_numeric_backend, "numeric_backend cannot be empty"),
    )
    report = require_valid_problem(problem, registry)
    source_indexes = Dict(node.id => index for (index, node) in enumerate(problem.graph))
    variable_indexes = Dict(variable.id => index for (index, variable) in enumerate(problem.variables))
    dependencies, _ = _node_variable_dependencies(problem, variable_indexes)
    live = _safe_live_mask(problem, source_indexes)

    compiled_variables = Tuple(
        CompiledVariable(
            variable,
            index,
            resolve_type(registry, variable.type_id).julia_type,
        ) for (index, variable) in enumerate(problem.variables)
    )
    instructions = AbstractPlanInstruction[]
    slots = Dict{NodeId,Int}()
    representatives = Int[]
    constants = Dict{Int,Any}()
    cse = Dict{Any,Int}()
    logical_kernels = OperatorKernel[]
    constant_folds = 0
    cse_hits = 0
    runtime_calls = 0
    logical_cost = 0

    for (source_index, node) in enumerate(problem.graph)
        live[source_index] || continue
        slot = length(slots) + 1
        slots[node.id] = slot
        push!(representatives, slot)
        output_type = node_type(report, node.id)
        type_spec = resolve_type(registry, output_type)
        runtime_type = type_spec.julia_type

        if node isa LiteralNode
            literal_digest, _ = _literal_digest(node.value)
            key = (:literal, node.type_id, literal_digest)
            cse_safe = _deeply_immutable(node.value)
            source_slot = cse_safe ? get(cse, key, 0) : 0
            if !iszero(source_slot)
                push!(instructions, AliasInstruction(
                    node.id, slot, source_slot, output_type, runtime_type, nothing, 0,
                ))
                representatives[slot] = representatives[source_slot]
                constants[slot] = deepcopy(constants[source_slot])
                cse_hits += 1
            else
                value = deepcopy(node.value)
                push!(instructions, ConstantInstruction(
                    node.id, slot, value, output_type, runtime_type, nothing, 0,
                ))
                constants[slot] = value
                cse_safe && (cse[key] = slot)
            end
        elseif node isa ReferenceNode
            variable_index = variable_indexes[node.variable]
            key = (:reference, node.variable)
            source_slot = get(cse, key, 0)
            if !iszero(source_slot)
                push!(instructions, AliasInstruction(
                    node.id, slot, source_slot, output_type, runtime_type, nothing, 0,
                ))
                representatives[slot] = representatives[source_slot]
                cse_hits += 1
            else
                push!(instructions, VariableInstruction(
                    node.id, slot, variable_index, output_type, runtime_type,
                ))
                cse[key] = slot
            end
        elseif node isa CallNode
            resolved = resolve_operation(registry, node.operation)
            signature = _matched_signature(node, resolved, report)
            kernel = _kernel(resolved)
            push!(logical_kernels, kernel)
            logical_cost += 1
            argument_slots = _slot_arguments(node.arguments, slots)
            keyword_slots = _slot_keywords(node.keywords, slots)
            representative_arguments = Tuple(representatives[slot] for slot in argument_slots)
            representative_keywords = Tuple(
                name => representatives[keyword_slot] for (name, keyword_slot) in keyword_slots
            )
            all_constant = all(slot -> haskey(constants, slot), argument_slots) &&
                           all(pair -> haskey(constants, last(pair)), keyword_slots)
            immutable_inputs = all_constant &&
                               all(slot -> _deeply_immutable(constants[slot]), argument_slots) &&
                               all(
                pair -> _deeply_immutable(constants[last(pair)]),
                keyword_slots,
            )
            foldable = resolved.role == ROLE_PRIMITIVE &&
                       kernel.deterministic &&
                       _folding_preserves_value_routes(kernel) &&
                       immutable_inputs
            key = (
                :constant_call,
                node.operation,
                signature,
                representative_arguments,
                representative_keywords,
            )
            source_slot = foldable ? get(cse, key, 0) : 0

            if !iszero(source_slot)
                push!(instructions, AliasInstruction(
                    node.id, slot, source_slot, output_type, runtime_type, kernel, 1,
                ))
                representatives[slot] = representatives[source_slot]
                constants[slot] = deepcopy(constants[source_slot])
                cse_hits += 1
            elseif foldable
                arguments = Tuple(constants[argument_slot] for argument_slot in argument_slots)
                keywords = _constant_kwargs(keyword_slots, constants)
                ok, value, _, _ = _invoke_plugin(kernel, arguments, keywords, C0)
                if ok && value isa runtime_type && _deeply_immutable(value)
                    frozen = deepcopy(value)
                    push!(instructions, ConstantInstruction(
                        node.id, slot, frozen, output_type, runtime_type, kernel, 1,
                    ))
                    constants[slot] = frozen
                    cse[key] = slot
                    constant_folds += 1
                else
                    push!(instructions, CallInstruction(
                        node.id,
                        slot,
                        node.operation,
                        resolved.role,
                        resolved.spec,
                        kernel,
                        signature,
                        argument_slots,
                        keyword_slots,
                        output_type,
                        runtime_type,
                    ))
                    runtime_calls += 1
                end
            else
                push!(instructions, CallInstruction(
                    node.id,
                    slot,
                    node.operation,
                    resolved.role,
                    resolved.spec,
                    kernel,
                    signature,
                    argument_slots,
                    keyword_slots,
                    output_type,
                    runtime_type,
                ))
                runtime_calls += 1
            end
        elseif node isa SelectNode
            selector = resolve_selector(registry, node.selector)
            signature = _matched_signature(node, selector, report)
            kernel = selector.kernel
            push!(logical_kernels, kernel)
            logical_cost += 1
            push!(instructions, SelectInstruction(
                node.id,
                slot,
                node.choice,
                node.selector,
                selector,
                kernel,
                signature,
                slots[node.choice],
                _slot_arguments(node.arguments, slots),
                _slot_keywords(node.keywords, slots),
                output_type,
                runtime_type,
            ))
            runtime_calls += 1
        end
    end

    node_indexes = Tuple(node.id => index for (index, node) in enumerate(problem.graph))
    node_slots = Tuple(node.id => slots[node.id] for node in problem.graph if haskey(slots, node.id))

    relations = Tuple(begin
        node = problem.graph[source_indexes[binding.node]]
        resolved = resolve_operation(registry, node.operation)
        spec = resolved.spec
        CompiledRelationRole(
            binding.node,
            slots[binding.node],
            Float64(something(binding.scale_override, spec.scale_hint, 1.0)),
            spec.truth,
            _slot_arguments(node.arguments, slots),
            _slot_keywords(node.keywords, slots),
        )
    end for binding in problem.relations)
    guards = Tuple(begin
        node = problem.graph[source_indexes[binding.node]]
        spec = resolve_operation(registry, node.operation).spec
        CompiledGuardRole(
            binding.node,
            slots[binding.node],
            binding.strict,
            Float64(something(binding.scale_override, spec.scale_hint, 1.0)),
        )
    end for binding in problem.guards)
    domains = Tuple(
        CompiledDomainRole(binding.node, slots[binding.node], binding.strict) for
        binding in problem.domains
    )
    sparsity = _compiled_sparsity(problem, dependencies, source_indexes, live)
    stats = CompileStats(
        length(problem.graph),
        count(live),
        length(problem.graph) - count(live),
        constant_folds,
        cse_hits,
        runtime_calls,
    )
    cache_identity = _cache_identity(problem, registry, numeric_backend)
    target_type = node_type(report, problem.target)
    return CompiledProblem(
        problem,
        registry,
        Tuple(instructions),
        length(slots),
        node_indexes,
        node_slots,
        compiled_variables,
        relations,
        guards,
        domains,
        slots[problem.target],
        target_type,
        resolve_type(registry, target_type).julia_type,
        sparsity,
        stats,
        cache_identity,
        _logical_capabilities(logical_kernels),
        logical_cost,
    )
end

function _literal_digest(value)
    io = IOBuffer()
    persistent = Ref(true)
    _stable_write(io, value, persistent)
    return content_hash(String(take!(io))), persistent[]
end
