struct ValidationIssue
    code::Symbol
    node::Union{Nothing,NodeId}
    message::String
end

struct ValidationReport
    issues::Tuple
    node_types::Tuple
end

Base.isempty(report::ValidationReport) = isempty(report.issues)
Base.isvalid(report::ValidationReport) = isempty(report)

function node_type(report::ValidationReport, id::NodeId)
    index = findfirst(pair -> first(pair) == id, report.node_types)
    return index === nothing ? nothing : last(report.node_types[index])
end

function _issue!(issues, code::Symbol, message::AbstractString; node = nothing)
    push!(issues, ValidationIssue(code, node, String(message)))
    return nothing
end

function _plugin_is_locked(problem::ProblemSpecV1, plugin_id::PluginId)
    return any(lock -> lock.id == plugin_id, problem.plugin_locks)
end

function _keyword_type_map(node, inferred)
    return Tuple((keyword.name, get(inferred, keyword.value, nothing)) for keyword in node.keywords)
end

function _argument_types(ids, inferred)
    return Tuple(get(inferred, id, nothing) for id in ids)
end

function _positional_match(signature::SignatureSpec, argument_types::Tuple)
    any(isnothing, argument_types) && return false
    declared = signature.arguments
    if !signature.variadic
        return argument_types == declared
    end
    fixed_count = length(declared) - 1
    length(argument_types) >= fixed_count || return false
    argument_types[1:fixed_count] == declared[1:fixed_count] || return false
    repeated = declared[end]
    return all(type_id -> type_id == repeated, argument_types[(fixed_count + 1):end])
end

function _keyword_match(signature::SignatureSpec, keyword_types::Tuple)
    any(pair -> isnothing(last(pair)), keyword_types) && return false
    provided = Dict(keyword_types)
    declared = Dict(keyword.name => keyword for keyword in signature.keywords)
    all(name -> haskey(declared, name), keys(provided)) || return false
    all(keyword -> !keyword.required || haskey(provided, keyword.name), signature.keywords) ||
        return false
    return all(name -> provided[name] == declared[name].type_id, keys(provided))
end

function _matching_signature(signatures, argument_types::Tuple, keyword_types::Tuple)
    matches = Tuple(
        signature for signature in signatures if
        _positional_match(signature, argument_types) && _keyword_match(signature, keyword_types)
    )
    return length(matches) == 1 ? only(matches) : matches
end

function _validate_locks!(issues, problem, registry)
    for lock in problem.plugin_locks
        plugin = _find_plugin(registry, lock.id)
        if plugin === nothing
            _issue!(issues, :plugin_not_installed, "locked plugin $(lock.id) is not installed")
        elseif !_plugin_matches_lock(plugin, lock)
            _issue!(
                issues,
                :plugin_lock_mismatch,
                "installed plugin $(lock.id) does not match version/ABI/content lock",
            )
        end
    end
    return nothing
end

function _validate_type_id!(issues, problem, registry, id::TypeId; node = nothing)
    _plugin_is_locked(problem, id.plugin) || _issue!(
        issues,
        :unlocked_type,
        "type $id belongs to a plugin not locked by this problem";
        node,
    )
    resolve_type(registry, id) === nothing && _issue!(
        issues,
        :unknown_type,
        "type $id is not registered";
        node,
    )
    return nothing
end

function validate_problem(problem::ProblemSpecV1, registry::FrozenPluginRegistry)
    issues = ValidationIssue[]
    inferred = Dict{NodeId,TypeId}()
    variables = Dict(variable.id => variable for variable in problem.variables)
    _validate_locks!(issues, problem, registry)

    for variable in problem.variables
        _validate_type_id!(issues, problem, registry, variable.type_id)
        type_spec = resolve_type(registry, variable.type_id)
        if type_spec !== nothing && !(type_spec.julia_type <: Real)
            _issue!(
                issues,
                :nonreal_variable_type,
                "v1 solve variable $(variable.id) must use a registered subtype of Real",
            )
        end
    end

    for node in problem.graph
        if node isa LiteralNode
            _validate_type_id!(issues, problem, registry, node.type_id; node = node.id)
            type_spec = resolve_type(registry, node.type_id)
            if type_spec !== nothing && !(node.value isa type_spec.julia_type)
                _issue!(
                    issues,
                    :literal_type_mismatch,
                    "literal value is not an instance of $(type_spec.julia_type)";
                    node = node.id,
                )
            end
            inferred[node.id] = node.type_id
        elseif node isa ReferenceNode
            variable = get(variables, node.variable, nothing)
            if variable === nothing
                _issue!(
                    issues,
                    :unknown_variable,
                    "reference uses undeclared variable $(node.variable)";
                    node = node.id,
                )
            else
                inferred[node.id] = variable.type_id
            end
        elseif node isa CallNode
            if !_plugin_is_locked(problem, node.operation.plugin)
                _issue!(
                    issues,
                    :unlocked_operation,
                    "operation $(node.operation) belongs to an unlocked plugin";
                    node = node.id,
                )
            end
            resolved = resolve_operation(registry, node.operation)
            if resolved === nothing
                _issue!(
                    issues,
                    :unknown_operation,
                    "operation $(node.operation) is not registered";
                    node = node.id,
                )
                continue
            end
            arguments = _argument_types(node.arguments, inferred)
            keywords = _keyword_type_map(node, inferred)
            matched = _matching_signature(resolved.spec.signatures, arguments, keywords)
            if matched isa Tuple
                code = isempty(matched) ? :no_matching_signature : :ambiguous_signature
                _issue!(
                    issues,
                    code,
                    "operation $(node.operation) has $(length(matched)) matching signatures";
                    node = node.id,
                )
            else
                inferred[node.id] = matched.output
            end
        elseif node isa SelectNode
            if !_plugin_is_locked(problem, node.selector.plugin)
                _issue!(
                    issues,
                    :unlocked_selector,
                    "selector $(node.selector) belongs to an unlocked plugin";
                    node = node.id,
                )
            end
            selector = resolve_selector(registry, node.selector)
            if selector === nothing
                _issue!(
                    issues,
                    :unknown_selector,
                    "selector $(node.selector) is not registered";
                    node = node.id,
                )
                continue
            end
            arguments = _argument_types((node.choice, node.arguments...), inferred)
            keywords = _keyword_type_map(node, inferred)
            matched = _matching_signature(selector.signatures, arguments, keywords)
            if matched isa Tuple
                code = isempty(matched) ? :no_matching_signature : :ambiguous_signature
                _issue!(
                    issues,
                    code,
                    "selector $(node.selector) has $(length(matched)) matching signatures";
                    node = node.id,
                )
            else
                inferred[node.id] = matched.output
            end
        end
    end

    _validate_role_nodes!(issues, problem, registry, inferred)
    ordered_types = Tuple(
        node.id => inferred[node.id] for node in problem.graph if haskey(inferred, node.id)
    )
    return ValidationReport(Tuple(issues), ordered_types)
end

function _validate_role_node!(issues, graph_nodes, registry, inferred, id, expected_role, label)
    node = get(graph_nodes, id, nothing)
    if !(node isa CallNode)
        _issue!(issues, :invalid_role_node, "$label node $id must be a CallNode"; node = id)
        return
    end
    resolved = resolve_operation(registry, node.operation)
    if resolved === nothing || resolved.role != expected_role
        _issue!(
            issues,
            :invalid_role_operation,
            "$label node $id must call a registered $expected_role operation";
            node = id,
        )
        return
    end
    output = get(inferred, id, nothing)
    type_spec = output === nothing ? nothing : resolve_type(registry, output)
    if type_spec !== nothing && !(type_spec.julia_type <: Real)
        _issue!(issues, :nonreal_role_output, "$label node $id must produce a Real"; node = id)
    end
end

function _validate_role_nodes!(issues, problem, registry, inferred)
    nodes = Dict(node.id => node for node in problem.graph)
    for binding in problem.relations
        _validate_role_node!(issues, nodes, registry, inferred, binding.node, ROLE_RELATION, "relation")
    end
    for binding in problem.guards
        _validate_role_node!(issues, nodes, registry, inferred, binding.node, ROLE_GUARD, "guard")
    end
    for binding in problem.domains
        _validate_role_node!(issues, nodes, registry, inferred, binding.node, ROLE_DOMAIN, "domain")
    end
    target_type = get(inferred, problem.target, nothing)
    type_spec = target_type === nothing ? nothing : resolve_type(registry, target_type)
    if type_spec !== nothing && !(type_spec.julia_type <: Real)
        _issue!(
            issues,
            :nonreal_target,
            "v1 target node $(problem.target) must produce a Real";
            node = problem.target,
        )
    end
    return nothing
end

function require_valid_problem(problem::ProblemSpecV1, registry::FrozenPluginRegistry)
    report = validate_problem(problem, registry)
    isempty(report) || throw(ProblemValidationError(report.issues))
    return report
end

