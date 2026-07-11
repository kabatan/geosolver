@enum C3AReplayFailure::UInt8 begin
    C3A_REPLAY_NONE = 0
    C3A_REPLAY_CAPABILITY_MISSING = 1
    C3A_REPLAY_LITERAL_UNSUPPORTED = 2
    C3A_REPLAY_CALLBACK_FAILED = 3
    C3A_REPLAY_NONEXACT_VALUE = 4
    C3A_REPLAY_TYPE_MISMATCH = 5
    C3A_REPLAY_BOUNDS_FAILED = 6
    C3A_REPLAY_RELATION_FAILED = 7
    C3A_REPLAY_GUARD_FAILED = 8
    C3A_REPLAY_DOMAIN_FAILED = 9
    C3A_REPLAY_BRANCH_FAILED = 10
    C3A_REPLAY_BRANCH_MISMATCH = 11
    C3A_REPLAY_TARGET_FAILED = 12
end

struct C3ARelationProof
    node::NodeId
    value::AlgebraicReal
end

struct C3AMarginProof
    node::NodeId
    margin::AlgebraicReal
    strict::Bool
end

struct C3ABranchProof
    decision::BranchDecision
    validity_margin::AlgebraicReal
    selector_margin::AlgebraicReal
end

struct C3AReplayEvidence
    coordinates::Tuple
    target::AlgebraicReal
    relations::Tuple
    guards::Tuple
    domains::Tuple
    branches::Tuple
end

struct C3AReplayResult
    accepted::Bool
    evidence::Union{Nothing,C3AReplayEvidence}
    failure::C3AReplayFailure
    detail::String

    function C3AReplayResult(
        accepted::Bool,
        evidence::Union{Nothing,C3AReplayEvidence},
        failure::C3AReplayFailure,
        detail::AbstractString,
    )
        accepted == (evidence !== nothing) || throw(
            ArgumentError("C3A replay status and evidence disagree"),
        )
        accepted == (failure == C3A_REPLAY_NONE) || throw(
            ArgumentError("C3A replay status and failure disagree"),
        )
        accepted == isempty(detail) || throw(
            ArgumentError("only failed C3A replay may carry detail"),
        )
        return new(accepted, evidence, failure, String(detail))
    end
end

struct C3AReplayUnsupported
    detail::String
end

_c3a_success(evidence) = C3AReplayResult(true, evidence, C3A_REPLAY_NONE, "")
_c3a_failure(failure, detail) = C3AReplayResult(false, nothing, failure, String(detail))

function _c3a_scalar(value; allow_float::Bool=false)
    value isa AlgebraicReal && return value
    value isa QQBarFieldElem && return try
        AlgebraicReal(value)
    catch
        nothing
    end
    value isa Bool && return nothing
    value isa Union{Integer,Rational} && return try
        AlgebraicReal(value)
    catch
        nothing
    end
    if allow_float && value isa AbstractFloat
        isfinite(value) || return nothing
        return try
            AlgebraicReal(value)
        catch
            nothing
        end
    end
    return nothing
end

function _c3a_output(value, runtime_type)
    scalar = _c3a_scalar(value)
    if scalar !== nothing
        scalar isa runtime_type || return (
            false,
            nothing,
            C3A_REPLAY_TYPE_MISMATCH,
            "exact scalar output is inconsistent with registered runtime type $runtime_type",
        )
        return true, scalar, C3A_REPLAY_NONE, ""
    end
    exact_leaf_safe(value) || return (
        false,
        nothing,
        C3A_REPLAY_NONEXACT_VALUE,
        "C3A callback returned an inexact or unsupported value tree $(typeof(value))",
    )
    value isa runtime_type || return (
        false,
        nothing,
        C3A_REPLAY_TYPE_MISMATCH,
        "C3A callback output $(typeof(value)) is inconsistent with $runtime_type",
    )
    return true, deepcopy(value), C3A_REPLAY_NONE, ""
end

function _c3a_literal(value, runtime_type)
    if value isa Bool
        # Bool <: Integer <: Real in Julia, but accepting it as a numeric
        # scalar would silently reinterpret a logical literal as 0 or 1.
        return nothing
    elseif value isa Real
        scalar = _c3a_scalar(value; allow_float=true)
        scalar === nothing && return nothing
        scalar isa runtime_type || return nothing
        return scalar
    end
    exact_leaf_safe(value) || return nothing
    value isa runtime_type || return nothing
    return deepcopy(value)
end

function _c3a_kernel(resolved)
    resolved.role == GeoTargetCore.ROLE_RELATION && return resolved.spec.residual_kernel
    resolved.role == GeoTargetCore.ROLE_GUARD && return resolved.spec.margin_kernel
    resolved.role == GeoTargetCore.ROLE_DOMAIN && return resolved.spec.margin_kernel
    return resolved.spec.kernel
end

function _c3a_arguments(node, values)
    return Tuple(values[id] for id in node.arguments)
end

function _c3a_keywords(node, values)
    return (; (Symbol(keyword.name) => values[keyword.value] for keyword in node.keywords)...)
end

function _invoke_c3a(kernel::OperatorKernel, arguments, keywords, label)
    supports(kernel.capabilities, C3A) && kernel.algebraic_prover !== nothing || return (
        false,
        nothing,
        C3A_REPLAY_CAPABILITY_MISSING,
        "$label lacks an explicit C3A algebraic_prover",
    )
    value = try
        kernel.algebraic_prover(arguments...; keywords...)
    catch error
        error isa InterruptException && rethrow()
        return (
            false,
            nothing,
            C3A_REPLAY_CALLBACK_FAILED,
            "$label algebraic_prover failed: $(sprint(showerror, error))",
        )
    end
    return true, value, C3A_REPLAY_NONE, ""
end

function _canonical_branch_decisions(branches)
    frozen = Tuple(BranchDecision(branch.choice_node, branch.key) for branch in branches)
    return Tuple(sort(collect(frozen); by=branch -> string(branch.choice_node)))
end

function _expected_branch_decisions(expected)
    expected === nothing && return nothing
    decisions = BranchDecision[]
    for entry in expected
        decision = if entry isa BranchDecision
            entry
        elseif hasproperty(entry, :decision) && getproperty(entry, :decision) isa BranchDecision
            getproperty(entry, :decision)
        else
            return nothing
        end
        push!(decisions, decision)
    end
    return _canonical_branch_decisions(decisions)
end

function _branch_decisions_equal(left, right)
    length(left) == length(right) || return false
    return all(
        index -> left[index].choice_node == right[index].choice_node &&
                 left[index].key == right[index].key,
        eachindex(left),
    )
end

function _c3a_runtime_type(registry, report, node)
    type_id = GeoTargetCore.node_type(report, node.id)
    type_spec = GeoTargetCore.resolve_type(registry, type_id)
    type_spec === nothing && return nothing
    return type_spec.julia_type
end

function _c3a_bound(value)
    value === nothing && return true, nothing
    scalar = _c3a_scalar(value; allow_float=true)
    return scalar !== nothing, scalar
end

"""
Replay the original `ProblemSpecV1` graph using only explicit C3A callbacks.

No compiled or reference numerical evaluator is invoked here. Coordinates must
already be exact algebraic values (normally reconstructed recognition
descriptors). Float literals are embedded as their exact binary rationals;
floating leaves inside structured literals are unsupported.

For relation nodes, the algebraic prover's scalar result is the C3A residual
contract and must be exactly zero. The discovery `truth` predicate is never
called or inherited as an exact proof callback.
"""
function replay_c3a(
    compiled::GeoTargetCore.CompiledProblem,
    coordinates;
    expected_branches=nothing,
)
    supports(GeoTargetCore.capabilities(compiled), C3A) || return _c3a_failure(
        C3A_REPLAY_CAPABILITY_MISSING,
        "compiled problem does not have all-path C3A capability",
    )
    problem = compiled.problem
    registry = compiled.registry
    length(coordinates) == length(problem.variables) || return _c3a_failure(
        C3A_REPLAY_TYPE_MISMATCH,
        "exact coordinate count differs from the free-variable count",
    )
    report = try
        GeoTargetCore.require_valid_problem(problem, registry)
    catch error
        error isa InterruptException && rethrow()
        return _c3a_failure(
            C3A_REPLAY_TYPE_MISMATCH,
            "original problem no longer validates: $(sprint(showerror, error))",
        )
    end

    exact_coordinates = AlgebraicReal[]
    variable_values = Dict{VariableId,Any}()
    for (index, variable) in enumerate(problem.variables)
        exact = _c3a_scalar(coordinates[index])
        exact === nothing && return _c3a_failure(
            C3A_REPLAY_NONEXACT_VALUE,
            "coordinate $index is not an exact real algebraic value",
        )
        runtime_type = GeoTargetCore.resolve_type(registry, variable.type_id).julia_type
        exact isa runtime_type || return _c3a_failure(
            C3A_REPLAY_TYPE_MISMATCH,
            "coordinate $index is inconsistent with registered variable type",
        )
        lower_ok, lower = _c3a_bound(variable.lower)
        upper_ok, upper = _c3a_bound(variable.upper)
        lower_ok || return _c3a_failure(
            C3A_REPLAY_BOUNDS_FAILED,
            "coordinate $index has a lower bound that cannot be represented exactly",
        )
        upper_ok || return _c3a_failure(
            C3A_REPLAY_BOUNDS_FAILED,
            "coordinate $index has an upper bound that cannot be represented exactly",
        )
        lower !== nothing && exact < lower && return _c3a_failure(
            C3A_REPLAY_BOUNDS_FAILED,
            "coordinate $index is exactly below its lower bound",
        )
        upper !== nothing && exact > upper && return _c3a_failure(
            C3A_REPLAY_BOUNDS_FAILED,
            "coordinate $index is exactly above its upper bound",
        )
        push!(exact_coordinates, exact)
        variable_values[variable.id] = exact
    end

    values = Dict{NodeId,Any}()
    branch_proofs = C3ABranchProof[]
    for node in problem.graph
        runtime_type = _c3a_runtime_type(registry, report, node)
        runtime_type === nothing && return _c3a_failure(
            C3A_REPLAY_TYPE_MISMATCH,
            "node $(node.id) has no registered runtime type",
        )
        if node isa LiteralNode
            literal = _c3a_literal(node.value, runtime_type)
            literal === nothing && return _c3a_failure(
                C3A_REPLAY_LITERAL_UNSUPPORTED,
                "literal $(node.id) is not an exact scalar or exact structured value",
            )
            values[node.id] = literal
        elseif node isa ReferenceNode
            values[node.id] = variable_values[node.variable]
        elseif node isa CallNode
            resolved = GeoTargetCore.resolve_operation(registry, node.operation)
            resolved === nothing && return _c3a_failure(
                C3A_REPLAY_CAPABILITY_MISSING,
                "operation $(node.operation) is not registered",
            )
            ok, raw, failure, detail = _invoke_c3a(
                _c3a_kernel(resolved),
                _c3a_arguments(node, values),
                _c3a_keywords(node, values),
                "operation $(node.operation)",
            )
            ok || return _c3a_failure(failure, detail)
            output_ok, exact, output_failure, output_detail = _c3a_output(raw, runtime_type)
            output_ok || return _c3a_failure(output_failure, output_detail)
            values[node.id] = exact
        elseif node isa SelectNode
            selector = GeoTargetCore.resolve_selector(registry, node.selector)
            selector === nothing && return _c3a_failure(
                C3A_REPLAY_CAPABILITY_MISSING,
                "selector $(node.selector) is not registered",
            )
            choice = values[node.choice]
            choice isa Choice || return _c3a_failure(
                C3A_REPLAY_BRANCH_FAILED,
                "selector $(node.selector) input is not an exact Choice",
            )
            exact_leaf_safe(choice) || return _c3a_failure(
                C3A_REPLAY_NONEXACT_VALUE,
                "selector $(node.selector) Choice contains an inexact leaf",
            )
            arguments = (choice, _c3a_arguments(node, values)...)
            ok, selected, failure, detail = _invoke_c3a(
                selector.kernel,
                arguments,
                _c3a_keywords(node, values),
                "selector $(node.selector)",
            )
            ok || return _c3a_failure(failure, detail)
            selected isa Selection || return _c3a_failure(
                C3A_REPLAY_BRANCH_FAILED,
                "selector $(node.selector) algebraic_prover did not return Selection",
            )
            exact_leaf_safe(selected) || return _c3a_failure(
                C3A_REPLAY_NONEXACT_VALUE,
                "selector $(node.selector) returned an inexact Selection",
            )
            selected_index = findfirst(key -> key == selected.key, choice.keys)
            selected_index === nothing && return _c3a_failure(
                C3A_REPLAY_BRANCH_FAILED,
                "selector $(node.selector) returned a key absent from its Choice",
            )
            consistent = try
                selected.value == choice.candidates[selected_index]
            catch
                false
            end
            consistent || return _c3a_failure(
                C3A_REPLAY_BRANCH_FAILED,
                "selector $(node.selector) returned a value inconsistent with its key",
            )
            validity = _c3a_scalar(selected.validity_margin)
            selector_margin = _c3a_scalar(selected.selector_margin)
            validity !== nothing && selector_margin !== nothing || return _c3a_failure(
                C3A_REPLAY_NONEXACT_VALUE,
                "selector $(node.selector) margins are not exact algebraic scalars",
            )
            choice_validity = _c3a_scalar(choice.validity_margins[selected_index])
            choice_validity !== nothing || return _c3a_failure(
                C3A_REPLAY_NONEXACT_VALUE,
                "selector $(node.selector) selected a Choice with a nonexact validity margin",
            )
            consistent_validity = try
                validity == choice_validity
            catch
                false
            end
            consistent_validity || return _c3a_failure(
                C3A_REPLAY_BRANCH_FAILED,
                "selector $(node.selector) returned a validity margin inconsistent with its Choice",
            )
            validity > zero(validity) || return _c3a_failure(
                C3A_REPLAY_BRANCH_FAILED,
                "selector $(node.selector) selected a branch with nonpositive validity margin",
            )
            selector_margin > zero(selector_margin) || return _c3a_failure(
                C3A_REPLAY_BRANCH_FAILED,
                "selector $(node.selector) has an exact branch tie or nonpositive margin",
            )
            output_ok, exact, output_failure, output_detail =
                _c3a_output(selected.value, runtime_type)
            output_ok || return _c3a_failure(output_failure, output_detail)
            decision = BranchDecision(node.choice, selected.key)
            push!(branch_proofs, C3ABranchProof(decision, validity, selector_margin))
            values[node.id] = exact
        end
    end

    relations = C3ARelationProof[]
    for binding in problem.relations
        value = _c3a_scalar(values[binding.node])
        value === nothing && return _c3a_failure(
            C3A_REPLAY_NONEXACT_VALUE,
            "relation $(binding.node) is not an exact algebraic scalar",
        )
        iszero(value) || return _c3a_failure(
            C3A_REPLAY_RELATION_FAILED,
            "relation $(binding.node) is not exactly zero",
        )
        push!(relations, C3ARelationProof(binding.node, value))
    end

    guards = C3AMarginProof[]
    for binding in problem.guards
        margin = _c3a_scalar(values[binding.node])
        margin === nothing && return _c3a_failure(
            C3A_REPLAY_NONEXACT_VALUE,
            "guard $(binding.node) is not an exact algebraic scalar",
        )
        valid = binding.strict ? margin > zero(margin) : margin >= zero(margin)
        valid || return _c3a_failure(
            C3A_REPLAY_GUARD_FAILED,
            "guard $(binding.node) fails its exact $(binding.strict ? "strict" : "nonstrict") sign",
        )
        push!(guards, C3AMarginProof(binding.node, margin, binding.strict))
    end

    domains = C3AMarginProof[]
    for binding in problem.domains
        margin = _c3a_scalar(values[binding.node])
        margin === nothing && return _c3a_failure(
            C3A_REPLAY_NONEXACT_VALUE,
            "domain $(binding.node) is not an exact algebraic scalar",
        )
        valid = binding.strict ? margin > zero(margin) : margin >= zero(margin)
        valid || return _c3a_failure(
            C3A_REPLAY_DOMAIN_FAILED,
            "domain $(binding.node) fails its exact $(binding.strict ? "strict" : "nonstrict") sign",
        )
        push!(domains, C3AMarginProof(binding.node, margin, binding.strict))
    end

    observed_decisions = _canonical_branch_decisions(
        proof.decision for proof in branch_proofs
    )
    expected_decisions = _expected_branch_decisions(expected_branches)
    expected_branches !== nothing && expected_decisions === nothing && return _c3a_failure(
        C3A_REPLAY_BRANCH_MISMATCH,
        "expected branch signature has an invalid shape",
    )
    expected_decisions !== nothing &&
        !_branch_decisions_equal(observed_decisions, expected_decisions) && return _c3a_failure(
            C3A_REPLAY_BRANCH_MISMATCH,
            "exact branch keys differ from the numerically confirmed signature",
        )

    target = _c3a_scalar(values[problem.target])
    target === nothing && return _c3a_failure(
        C3A_REPLAY_TARGET_FAILED,
        "target $(problem.target) is not an exact real algebraic scalar",
    )
    evidence = C3AReplayEvidence(
        Tuple(exact_coordinates),
        target,
        Tuple(relations),
        Tuple(guards),
        Tuple(domains),
        Tuple(sort(branch_proofs; by=proof -> string(proof.decision.choice_node))),
    )
    return _c3a_success(evidence)
end

replay_c3a(::Any...; kwargs...) = C3AReplayUnsupported(
    "C3A replay requires a GeoTargetCore.CompiledProblem and exact coordinate tuple",
)
