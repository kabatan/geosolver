function _kernel(resolved::ResolvedOperation)
    resolved.role == ROLE_RELATION && return resolved.spec.residual_kernel
    resolved.role == ROLE_GUARD && return resolved.spec.margin_kernel
    resolved.role == ROLE_DOMAIN && return resolved.spec.margin_kernel
    return resolved.spec.kernel
end

function _kernel_evaluator(kernel::OperatorKernel, capability::Capability)
    require_capability(kernel.capabilities, capability)
    capability == C0 && return kernel.evaluator
    capability == C2 && return kernel.generic_numeric ? kernel.evaluator : kernel.high_precision
    capability == C3V && return kernel.generic_numeric ? kernel.evaluator : kernel.validated
    throw(CapabilityError(capability, "graph value evaluation"))
end

function _invoke_plugin(kernel, args, kwargs, capability)
    try # Explicit plugin boundary: arbitrary plugin failures become typed observations.
        evaluator = _kernel_evaluator(kernel, capability)
        return true, evaluator(args...; kwargs...), EVAL_OK, nothing
    catch error
        if error isa CapabilityError
            return false, nothing, EVAL_UNSUPPORTED_CAPABILITY, sprint(showerror, error)
        elseif error isa DomainError
            return false, nothing, EVAL_INVALID_DOMAIN, sprint(showerror, error)
        end
        return false, nothing, EVAL_PLUGIN_ERROR, sprint(showerror, error)
    end
end

function _empty_observation(status::EvalStatus, cost::Int, diagnostic)
    return OracleObservation((), nothing, (), (), (), status, cost, diagnostic)
end

function _value_at(values, indexes, id::NodeId)
    return values[indexes[id]]
end

function _node_arguments(node, values, indexes)
    return Tuple(_value_at(values, indexes, id) for id in node.arguments)
end

function _node_keywords(node, values, indexes)
    return (; (
        Symbol(keyword.name) => _value_at(values, indexes, keyword.value) for
        keyword in node.keywords
    )...)
end

function _finite_real(value)
    return value isa Real && isfinite(value)
end

function _runtime_type_ok(registry, type_id, value)
    type_spec = resolve_type(registry, type_id)
    return type_spec !== nothing && value isa type_spec.julia_type
end

function _variable_domain_invalid(variable, value)
    variable.lower !== nothing && value < variable.lower && return true
    variable.upper !== nothing && value > variable.upper && return true
    return false
end

function _role_spec(problem, registry, node_indexes, binding)
    node = problem.graph[node_indexes[binding.node]]
    return resolve_operation(registry, node.operation).spec
end

function _truth_value(spec::RelationSpec, raw)
    spec.truth === nothing && return nothing, nothing
    try # Explicit plugin truth-predicate boundary.
        result = spec.truth(raw)
        result isa Bool || return nothing, "relation truth predicate did not return Bool"
        return result, nothing
    catch error
        return nothing, sprint(showerror, error)
    end
end

function evaluate_reference(
    problem::ProblemSpecV1,
    registry::FrozenPluginRegistry,
    x::AbstractVector;
    capability::Capability = C0,
)
    report = require_valid_problem(problem, registry)
    length(x) == length(problem.variables) || throw(
        ArgumentError("expected $(length(problem.variables)) variables, received $(length(x))"),
    )
    capability in (C0, C2, C3V) || throw(
        CapabilityError(capability, "reference value evaluation supports only C0, C2 and C3V"),
    )

    variable_values = Dict(variable.id => x[index] for (index, variable) in enumerate(problem.variables))
    for variable in problem.variables
        value = variable_values[variable.id]
        _runtime_type_ok(registry, variable.type_id, value) || return _empty_observation(
            EVAL_PLUGIN_ERROR,
            0,
            "variable $(variable.id) is inconsistent with registered type $(variable.type_id)",
        )
        _finite_real(value) || return _empty_observation(
            EVAL_NONFINITE,
            0,
            "variable $(variable.id) is not finite",
        )
    end
    bounds_invalid = any(
        _variable_domain_invalid(variable, variable_values[variable.id]) for
        variable in problem.variables
    )
    values = Vector{Any}(undef, length(problem.graph))
    indexes = Dict(node.id => index for (index, node) in enumerate(problem.graph))
    branch_observations = BranchObservation[]
    invalid_branch = false
    ambiguous_branch = false
    cost = 0

    for (index, node) in enumerate(problem.graph)
        expected_type = node_type(report, node.id)
        if node isa LiteralNode
            values[index] = deepcopy(node.value)
        elseif node isa ReferenceNode
            values[index] = variable_values[node.variable]
        elseif node isa CallNode
            resolved = resolve_operation(registry, node.operation)
            arguments = _node_arguments(node, values, indexes)
            keywords = _node_keywords(node, values, indexes)
            ok, value, status, diagnostic =
                _invoke_plugin(_kernel(resolved), arguments, keywords, capability)
            cost += 1
            ok || return _empty_observation(status, cost, diagnostic)
            if !_runtime_type_ok(registry, expected_type, value)
                return _empty_observation(
                    EVAL_PLUGIN_ERROR,
                    cost,
                    "operation $(node.operation) returned a value inconsistent with $expected_type",
                )
            end
            values[index] = value
        elseif node isa SelectNode
            selector = resolve_selector(registry, node.selector)
            choice = _value_at(values, indexes, node.choice)
            choice isa Choice || return _empty_observation(
                EVAL_PLUGIN_ERROR,
                cost,
                "selector $(node.selector) input is not a Choice",
            )
            arguments = (choice, _node_arguments(node, values, indexes)...)
            keywords = _node_keywords(node, values, indexes)
            ok, selected, status, diagnostic =
                _invoke_plugin(selector.kernel, arguments, keywords, capability)
            cost += 1
            ok || return _empty_observation(status, cost, diagnostic)
            selected isa Selection || return _empty_observation(
                EVAL_PLUGIN_ERROR,
                cost,
                "selector $(node.selector) must return Selection",
            )
            if !_runtime_type_ok(registry, expected_type, selected.value)
                return _empty_observation(
                    EVAL_PLUGIN_ERROR,
                    cost,
                    "selector $(node.selector) returned a value inconsistent with $expected_type",
                )
            end
            if !_finite_real(selected.validity_margin) || !_finite_real(selected.selector_margin)
                return _empty_observation(
                    EVAL_NONFINITE,
                    cost,
                    "selector $(node.selector) returned a nonfinite or non-real margin",
                )
            end
            invalid_branch |= selected.validity_margin <= 0
            ambiguous_branch |= selected.selector_margin <= 0
            push!(
                branch_observations,
                BranchObservation(
                    BranchDecision(node.choice, selected.key),
                    selected.validity_margin,
                    selected.selector_margin,
                ),
            )
            values[index] = selected.value
        end
    end

    relations = RelationObservation[]
    for binding in problem.relations
        raw = _value_at(values, indexes, binding.node)
        _finite_real(raw) || return _empty_observation(
            EVAL_NONFINITE,
            cost,
            "relation $(binding.node) did not produce a finite Real",
        )
        spec = _role_spec(problem, registry, indexes, binding)
        scale = something(binding.scale_override, spec.scale_hint, 1.0)
        truth, truth_error = _truth_value(spec, raw)
        truth_error === nothing || return _empty_observation(EVAL_PLUGIN_ERROR, cost, truth_error)
        push!(relations, RelationObservation(binding.node, raw, scale, raw / scale, truth))
    end

    guards = GuardObservation[]
    for binding in problem.guards
        margin = _value_at(values, indexes, binding.node)
        _finite_real(margin) || return _empty_observation(
            EVAL_NONFINITE,
            cost,
            "guard $(binding.node) did not produce a finite Real",
        )
        spec = _role_spec(problem, registry, indexes, binding)
        scale = something(binding.scale_override, spec.scale_hint, 1.0)
        valid = binding.strict ? margin > 0 : margin >= 0
        push!(guards, GuardObservation(binding.node, margin, binding.strict, scale, valid))
    end

    domains = DomainObservation[]
    for binding in problem.domains
        margin = _value_at(values, indexes, binding.node)
        _finite_real(margin) || return _empty_observation(
            EVAL_NONFINITE,
            cost,
            "domain $(binding.node) did not produce a finite Real",
        )
        valid = binding.strict ? margin > 0 : margin >= 0
        push!(domains, DomainObservation(binding.node, margin, binding.strict, valid))
    end

    target = _value_at(values, indexes, problem.target)
    _finite_real(target) || return _empty_observation(
        EVAL_NONFINITE,
        cost,
        "target $(problem.target) did not produce a finite Real",
    )

    status = if bounds_invalid || any(domain -> !domain.valid, domains)
        EVAL_INVALID_DOMAIN
    elseif invalid_branch
        EVAL_INVALID_BRANCH
    elseif ambiguous_branch
        EVAL_AMBIGUOUS_BRANCH
    else
        EVAL_OK
    end
    return OracleObservation(
        Tuple(relations),
        target,
        Tuple(guards),
        Tuple(domains),
        Tuple(branch_observations),
        status,
        cost,
        nothing,
    )
end
