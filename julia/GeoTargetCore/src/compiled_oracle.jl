"""Solve-local reusable storage for one CompiledProblem."""
mutable struct CompiledWorkspace
    cache_key::ContentHash
    values::Vector{Any}
    branches::Vector{BranchObservation}
    state_lock::ReentrantLock
    in_use::Bool
end

CompiledWorkspace(compiled::CompiledProblem) = CompiledWorkspace(
    compiled.cache_identity.key,
    Vector{Any}(undef, compiled.slot_count),
    BranchObservation[],
    ReentrantLock(),
    false,
)

capabilities(compiled::CompiledProblem) = compiled.available_capabilities

function _acquire!(workspace::CompiledWorkspace, compiled::CompiledProblem)
    workspace.cache_key == compiled.cache_identity.key || throw(
        CompilerError(:workspace_mismatch, "workspace belongs to a different compiled plan"),
    )
    length(workspace.values) == compiled.slot_count || throw(
        CompilerError(:workspace_mismatch, "workspace slot count does not match compiled plan"),
    )
    lock(workspace.state_lock)
    try
        workspace.in_use && throw(
            CompilerError(:workspace_in_use, "a CompiledWorkspace cannot be used concurrently"),
        )
        workspace.in_use = true
    finally
        unlock(workspace.state_lock)
    end
    fill!(workspace.values, nothing)
    empty!(workspace.branches)
    return workspace
end

function _release!(workspace::CompiledWorkspace)
    lock(workspace.state_lock)
    try
        workspace.in_use = false
    finally
        unlock(workspace.state_lock)
    end
    return nothing
end

function _compiled_empty_observation(status::EvalStatus, cost::Int, diagnostic)
    return OracleObservation((), nothing, (), (), (), status, cost, diagnostic)
end

function _compiled_arguments(slots, values)
    return Tuple(values[slot] for slot in slots)
end

function _compiled_keywords(slots, values)
    return (; (name => values[slot] for (name, slot) in slots)...)
end

function _compiled_variable_invalid(variable::VariableSpec, value)
    variable.lower !== nothing && value < variable.lower && return true
    variable.upper !== nothing && value > variable.upper && return true
    return false
end

function _capability_status(kernel, capability::Capability, cost::Int)
    supports(kernel.capabilities, capability) && return nothing
    diagnostic = sprint(showerror, CapabilityError(capability, "operator"))
    return _compiled_empty_observation(EVAL_UNSUPPORTED_CAPABILITY, cost, diagnostic)
end

function _compiled_truth_value(truth, arguments, keywords)
    truth === nothing && return nothing, nothing
    try # Explicit plugin truth-predicate boundary, matching the reference path.
        result = truth(arguments...; keywords...)
        result isa Bool || return nothing, "relation truth predicate did not return Bool"
        return result, nothing
    catch error
        return nothing, sprint(showerror, error)
    end
end

function _execute_instruction!(
    instruction::ConstantInstruction,
    workspace,
    capability,
    cost,
    invalid_branch,
    ambiguous_branch,
)
    if instruction.logical_kernel !== nothing
        cost += instruction.logical_cost
        unsupported = _capability_status(instruction.logical_kernel, capability, cost)
        unsupported === nothing || return false, unsupported, cost, invalid_branch, ambiguous_branch
    end
    workspace.values[instruction.slot] = deepcopy(instruction.value)
    return true, nothing, cost, invalid_branch, ambiguous_branch
end

function _execute_instruction!(
    instruction::VariableInstruction,
    workspace,
    capability,
    cost,
    invalid_branch,
    ambiguous_branch,
    x,
)
    workspace.values[instruction.slot] = x[instruction.variable_index]
    return true, nothing, cost, invalid_branch, ambiguous_branch
end


function _execute_instruction!(
    instruction::AliasInstruction,
    workspace,
    capability,
    cost,
    invalid_branch,
    ambiguous_branch,
)
    if instruction.logical_kernel !== nothing
        cost += instruction.logical_cost
        unsupported = _capability_status(instruction.logical_kernel, capability, cost)
        unsupported === nothing || return false, unsupported, cost, invalid_branch, ambiguous_branch
    end
    # CSE is restricted to deeply immutable constants or duplicate references.
    # References must preserve the input object's identity, as the interpreter does.
    workspace.values[instruction.slot] = workspace.values[instruction.source_slot]
    return true, nothing, cost, invalid_branch, ambiguous_branch
end

function _execute_instruction!(
    instruction::CallInstruction,
    workspace,
    capability,
    cost,
    invalid_branch,
    ambiguous_branch,
)
    arguments = _compiled_arguments(instruction.argument_slots, workspace.values)
    keywords = _compiled_keywords(instruction.keyword_slots, workspace.values)
    ok, value, status, diagnostic =
        _invoke_plugin(instruction.kernel, arguments, keywords, capability)
    cost += 1
    ok || return false,
    _compiled_empty_observation(status, cost, diagnostic),
    cost,
    invalid_branch,
    ambiguous_branch
    value isa instruction.runtime_type || return false,
    _compiled_empty_observation(
        EVAL_PLUGIN_ERROR,
        cost,
        "operation $(instruction.operation) returned a value inconsistent with $(instruction.type_id)",
    ),
    cost,
    invalid_branch,
    ambiguous_branch
    workspace.values[instruction.slot] = value
    return true, nothing, cost, invalid_branch, ambiguous_branch
end

function _execute_instruction!(
    instruction::SelectInstruction,
    workspace,
    capability,
    cost,
    invalid_branch,
    ambiguous_branch,
)
    choice = workspace.values[instruction.choice_slot]
    choice isa Choice || return false,
    _compiled_empty_observation(
        EVAL_PLUGIN_ERROR,
        cost,
        "selector $(instruction.selector) input is not a Choice",
    ),
    cost,
    invalid_branch,
    ambiguous_branch
    arguments = (
        choice,
        _compiled_arguments(instruction.argument_slots, workspace.values)...,
    )
    keywords = _compiled_keywords(instruction.keyword_slots, workspace.values)
    ok, selected, status, diagnostic =
        _invoke_plugin(instruction.kernel, arguments, keywords, capability)
    cost += 1
    ok || return false,
    _compiled_empty_observation(status, cost, diagnostic),
    cost,
    invalid_branch,
    ambiguous_branch
    selected isa Selection || return false,
    _compiled_empty_observation(
        EVAL_PLUGIN_ERROR,
        cost,
        "selector $(instruction.selector) must return Selection",
    ),
    cost,
    invalid_branch,
    ambiguous_branch
    selected.value isa instruction.runtime_type || return false,
    _compiled_empty_observation(
        EVAL_PLUGIN_ERROR,
        cost,
        "selector $(instruction.selector) returned a value inconsistent with $(instruction.type_id)",
    ),
    cost,
    invalid_branch,
    ambiguous_branch
    if !_finite_real(selected.validity_margin) || !_finite_real(selected.selector_margin)
        observation = _compiled_empty_observation(
            EVAL_NONFINITE,
            cost,
            "selector $(instruction.selector) returned a nonfinite or non-real margin",
        )
        return false, observation, cost, invalid_branch, ambiguous_branch
    end
    invalid_branch |= selected.validity_margin <= 0
    ambiguous_branch |= selected.selector_margin <= 0
    push!(
        workspace.branches,
        BranchObservation(
            BranchDecision(instruction.choice_node, selected.key),
            selected.validity_margin,
            selected.selector_margin,
        ),
    )
    workspace.values[instruction.slot] = selected.value
    return true, nothing, cost, invalid_branch, ambiguous_branch
end

function _execute_plan!(compiled, workspace, x, capability)
    cost = 0
    invalid_branch = false
    ambiguous_branch = false
    for instruction in compiled.instructions
        result = if instruction isa VariableInstruction
            _execute_instruction!(
                instruction,
                workspace,
                capability,
                cost,
                invalid_branch,
                ambiguous_branch,
                x,
            )
        else
            _execute_instruction!(
                instruction,
                workspace,
                capability,
                cost,
                invalid_branch,
                ambiguous_branch,
            )
        end
        ok, observation, cost, invalid_branch, ambiguous_branch = result
        ok || return false, observation, cost, invalid_branch, ambiguous_branch
    end
    return true, nothing, cost, invalid_branch, ambiguous_branch
end

function _compiled_observation(compiled, workspace, cost, bounds_invalid, invalid_branch, ambiguous_branch)
    relations = RelationObservation[]
    for role in compiled.relations
        raw = workspace.values[role.slot]
        _finite_real(raw) || return _compiled_empty_observation(
            EVAL_NONFINITE,
            cost,
            "relation $(role.node) did not produce a finite Real",
        )
        arguments = _compiled_arguments(role.argument_slots, workspace.values)
        keywords = _compiled_keywords(role.keyword_slots, workspace.values)
        truth, truth_error = _compiled_truth_value(role.truth, arguments, keywords)
        truth_error === nothing || return _compiled_empty_observation(
            EVAL_PLUGIN_ERROR,
            cost,
            truth_error,
        )
        push!(relations, RelationObservation(role.node, raw, role.scale, raw / role.scale, truth))
    end

    guards = GuardObservation[]
    for role in compiled.guards
        margin = workspace.values[role.slot]
        _finite_real(margin) || return _compiled_empty_observation(
            EVAL_NONFINITE,
            cost,
            "guard $(role.node) did not produce a finite Real",
        )
        valid = role.strict ? margin > 0 : margin >= 0
        push!(guards, GuardObservation(role.node, margin, role.strict, role.scale, valid))
    end

    domains = DomainObservation[]
    for role in compiled.domains
        margin = workspace.values[role.slot]
        _finite_real(margin) || return _compiled_empty_observation(
            EVAL_NONFINITE,
            cost,
            "domain $(role.node) did not produce a finite Real",
        )
        valid = role.strict ? margin > 0 : margin >= 0
        push!(domains, DomainObservation(role.node, margin, role.strict, valid))
    end

    target = workspace.values[compiled.target_slot]
    target isa compiled.target_runtime_type || return _compiled_empty_observation(
        EVAL_PLUGIN_ERROR,
        cost,
        "target $(compiled.problem.target) is inconsistent with $(compiled.target_type)",
    )
    _finite_real(target) || return _compiled_empty_observation(
        EVAL_NONFINITE,
        cost,
        "target $(compiled.problem.target) did not produce a finite Real",
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
        Tuple(workspace.branches),
        status,
        cost,
        nothing,
    )
end

function evaluate(
    compiled::CompiledProblem,
    x::AbstractVector;
    capability::Capability = C0,
    workspace::CompiledWorkspace = CompiledWorkspace(compiled),
)
    length(x) == length(compiled.variables) || throw(
        ArgumentError("expected $(length(compiled.variables)) variables, received $(length(x))"),
    )
    capability in (C0, C2, C3V) || throw(
        CapabilityError(capability, "compiled value evaluation supports only C0, C2 and C3V"),
    )
    _acquire!(workspace, compiled)
    try
        bounds_invalid = false
        for variable in compiled.variables
            value = x[variable.index]
            value isa variable.runtime_type || return _compiled_empty_observation(
                EVAL_PLUGIN_ERROR,
                0,
                "variable $(variable.spec.id) is inconsistent with registered type $(variable.spec.type_id)",
            )
            _finite_real(value) || return _compiled_empty_observation(
                EVAL_NONFINITE,
                0,
                "variable $(variable.spec.id) is not finite",
            )
            bounds_invalid |= _compiled_variable_invalid(variable.spec, value)
        end
        ok, observation, cost, invalid_branch, ambiguous_branch =
            _execute_plan!(compiled, workspace, x, capability)
        ok || return observation
        return _compiled_observation(
            compiled,
            workspace,
            cost,
            bounds_invalid,
            invalid_branch,
            ambiguous_branch,
        )
    finally
        _release!(workspace)
    end
end

function evaluate_batch(
    compiled::CompiledProblem,
    points::AbstractMatrix;
    capability::Capability = C0,
    workspace::CompiledWorkspace = CompiledWorkspace(compiled),
)
    size(points, 2) == length(compiled.variables) || throw(
        ArgumentError("batch matrices use one sample per row and one variable per column"),
    )
    observations = Vector{OracleObservation}(undef, size(points, 1))
    for row in axes(points, 1)
        observations[row] = evaluate(
            compiled,
            view(points, row, :);
            capability,
            workspace,
        )
    end
    return observations
end

function evaluate_batch(
    compiled::CompiledProblem,
    points::AbstractVector{<:AbstractVector};
    capability::Capability = C0,
    workspace::CompiledWorkspace = CompiledWorkspace(compiled),
)
    return [evaluate(compiled, point; capability, workspace) for point in points]
end

"""Canonical replay used for every final semantic acceptance decision."""
function evaluate_canonical(
    compiled::CompiledProblem,
    x::AbstractVector;
    capability::Capability = C0,
)
    return evaluate_reference(compiled.problem, compiled.registry, x; capability)
end
