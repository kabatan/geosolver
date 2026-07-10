@enum CandidateValidationFailure::UInt8 begin
    CANDIDATE_VALIDATION_NONE = 0
    CANDIDATE_FAST_OBSERVATION_FAILED = 1
    CANDIDATE_CANONICAL_EVALUATION_FAILED = 2
    CANDIDATE_VARIABLE_BOUNDS_FAILED = 3
    CANDIDATE_RELATION_RESIDUAL_FAILED = 4
    CANDIDATE_RELATION_TRUTH_FAILED = 5
    CANDIDATE_DOMAIN_FAILED = 6
    CANDIDATE_STRICT_GUARD_UNSEPARATED = 7
    CANDIDATE_NONSTRICT_GUARD_FAILED = 8
    CANDIDATE_BRANCH_KEY_MISMATCH = 9
    CANDIDATE_BRANCH_VALIDITY_FAILED = 10
    CANDIDATE_BRANCH_SELECTOR_UNSEPARATED = 11
    CANDIDATE_TARGET_INCONSISTENT = 12
end

struct CandidateValidationDiagnostic
    failure::CandidateValidationFailure
    node::Union{Nothing,NodeId}
    message::String
end

struct CandidateValidationOptions
    precision_bits::Int
    residual_tolerance::Float64
    enclosure_absolute_error::Float64
    enclosure_relative_error::Float64
    target_consistency_tolerance::Float64
    roundoff_multiplier::Float64

    function CandidateValidationOptions(
        ;
        precision_bits::Integer = 256,
        residual_tolerance::Real = 1.0e-12,
        enclosure_absolute_error::Real = 0.0,
        enclosure_relative_error::Real = 0.0,
        target_consistency_tolerance::Real = 1.0e-12,
        roundoff_multiplier::Real = 8.0,
    )
        precision_bits >= 53 || throw(ArgumentError("precision_bits must be at least 53"))
        nonnegative = Float64.((
            residual_tolerance,
            enclosure_absolute_error,
            enclosure_relative_error,
            target_consistency_tolerance,
        ))
        all(value -> isfinite(value) && value >= 0, nonnegative) || throw(
            ArgumentError("validation tolerances must be finite and nonnegative"),
        )
        frozen_roundoff_multiplier = Float64(roundoff_multiplier)
        isfinite(frozen_roundoff_multiplier) && frozen_roundoff_multiplier > 0 || throw(
            ArgumentError("roundoff_multiplier must be finite and positive"),
        )
        return new(
            Int(precision_bits),
            nonnegative...,
            frozen_roundoff_multiplier,
        )
    end
end

struct CandidateValidationResult
    accepted::Bool
    provisional::Union{Nothing,ProvisionalAnswer}
    failure::CandidateValidationFailure
    diagnostic::Union{Nothing,CandidateValidationDiagnostic}
    problem::ContentHash
    problem_hash_method::String
    configuration::ContentHash
    validation_config::ContentHash
    method::String
    precision_bits::Int
    fast_observation::OracleObservation
    canonical_observation::OracleObservation
    artifact::CertificateArtifact
    target_enclosure::Union{Nothing,NumericEnclosure}
    guard_enclosures::Tuple
    oracle_work::Int
    exact_failure::ExactPromotionFailure

    function CandidateValidationResult(
        accepted::Bool,
        provisional::Union{Nothing,ProvisionalAnswer},
        failure::CandidateValidationFailure,
        diagnostic::Union{Nothing,CandidateValidationDiagnostic},
        problem::ContentHash,
        problem_hash_method::String,
        configuration::ContentHash,
        validation_config::ContentHash,
        method::String,
        precision_bits::Int,
        fast_observation::OracleObservation,
        canonical_observation::OracleObservation,
        artifact::CertificateArtifact,
        target_enclosure::Union{Nothing,NumericEnclosure},
        guard_enclosures::Tuple,
        oracle_work::Int,
        exact_failure::ExactPromotionFailure,
    )
        accepted == (provisional !== nothing) || throw(
            InvariantError(
                :candidate_validation_answer_mismatch,
                "accepted candidate validation must contain exactly one provisional answer",
            ),
        )
        accepted == (failure == CANDIDATE_VALIDATION_NONE) || throw(
            InvariantError(
                :candidate_validation_status_mismatch,
                "accepted validation and failure reason disagree",
            ),
        )
        accepted == (diagnostic === nothing) || throw(
            InvariantError(
                :candidate_validation_diagnostic_mismatch,
                "only rejected validation results carry a diagnostic",
            ),
        )
        diagnostic === nothing || diagnostic.failure == failure || throw(
            InvariantError(
                :candidate_validation_diagnostic_mismatch,
                "diagnostic and result failure reasons disagree",
            ),
        )
        oracle_work >= 0 || throw(
            InvariantError(:negative_oracle_work, "candidate validation work cannot be negative"),
        )
        return new(
            accepted,
            provisional,
            failure,
            diagnostic,
            problem,
            problem_hash_method,
            configuration,
            validation_config,
            method,
            precision_bits,
            fast_observation,
            canonical_observation,
            artifact,
            target_enclosure,
            guard_enclosures,
            oracle_work,
            exact_failure,
        )
    end
end

function _candidate_problem_identity(compiled::CompiledProblem)
    try
        return problem_hash(compiled.problem, compiled.registry), "protocol_canonical_json"
    catch error
        error isa ProtocolJsonError || rethrow()
        return compiled.cache_identity.problem, "compiled_structural_v1"
    end
end

function _candidate_configuration_hash(compiled::CompiledProblem, x::AbstractVector)
    io = IOBuffer()
    persistent = Ref(true)
    print(io, "geotarget-candidate-configuration-v1|")
    for (variable, value) in zip(compiled.variables, x)
        _stable_write(io, variable.spec.id, persistent)
        _stable_write(io, variable.spec.type_id, persistent)
        _stable_write(io, value, persistent)
    end
    return content_hash(take!(io))
end

function _validation_options_document(options::CandidateValidationOptions)
    return Dict{String,Any}(
        "enclosure_absolute_error" => string(options.enclosure_absolute_error),
        "enclosure_relative_error" => string(options.enclosure_relative_error),
        "precision_bits" => options.precision_bits,
        "residual_tolerance" => string(options.residual_tolerance),
        "roundoff_multiplier" => string(options.roundoff_multiplier),
        "target_consistency_tolerance" => string(options.target_consistency_tolerance),
    )
end

_validation_config_hash(options) = canonical_json_hash(_validation_options_document(options))

function _validation_center(value::Real)
    value isa AbstractFloat && return value
    return BigFloat(value)
end

function _numeric_enclosure(
    value::Real,
    options::CandidateValidationOptions;
    absolute_floor::Real=0,
)
    center = _validation_center(value)
    type = typeof(center)
    absolute_error = max(
        type(options.enclosure_absolute_error),
        type(absolute_floor),
    )
    relative_error = type(options.enclosure_relative_error) * abs(center)
    roundoff = if center isa AbstractFloat
        # `eps(BigFloat(0))` is the smallest representable positive BigFloat;
        # its exponent is near typemin and cannot be projected into the bounded
        # fixed-decimal wire format. A unit-scale floor is also the conservative
        # model needed when a computed zero may hide cancellation roundoff.
        roundoff_reference = max(abs(center), one(center))
        type(options.roundoff_multiplier) * eps(roundoff_reference)
    else
        zero(center)
    end
    radius = max(absolute_error, relative_error, roundoff)
    return NumericEnclosure(center - radius, center + radius)
end

_enclosure_bound(enclosure::NumericEnclosure) =
    max(abs(enclosure.lower), abs(enclosure.upper))

function _within_tolerance(value::Real, tolerance::Real)
    promoted_value, promoted_tolerance = promote(value, tolerance)
    return promoted_value <= promoted_tolerance
end

function _consistent_enclosures(
    first::NumericEnclosure,
    second::NumericEnclosure,
    tolerance::Real,
)
    first_lower, first_upper, second_lower, second_upper, promoted_tolerance = promote(
        first.lower,
        first.upper,
        second.lower,
        second.upper,
        tolerance,
    )
    return first_lower <= second_upper + promoted_tolerance &&
           second_lower <= first_upper + promoted_tolerance
end

function _candidate_outside_bounds(compiled, coordinates)
    for variable in compiled.variables
        value = coordinates[variable.index]
        variable.spec.lower !== nothing && value < variable.spec.lower && return true
        variable.spec.upper !== nothing && value > variable.spec.upper && return true
    end
    return false
end

function _ordered_decisions(observation::OracleObservation)
    return Tuple(sort(
        BranchDecision[branch.decision for branch in observation.branches];
        by = decision -> string(decision.choice_node),
    ))
end

function _branch_keys_match(fast::OracleObservation, canonical::OracleObservation)
    fast_decisions = _ordered_decisions(fast)
    canonical_decisions = _ordered_decisions(canonical)
    length(fast_decisions) == length(canonical_decisions) || return false
    return all(
        first.choice_node == second.choice_node && first.key == second.key for
        (first, second) in zip(fast_decisions, canonical_decisions)
    )
end

_artifact_value(value::Real) = Dict{String,Any}(
    "type" => string(typeof(value)),
    "value" => string(value),
)
_artifact_value(::Nothing) = nothing

function _enclosure_document(enclosure::NumericEnclosure)
    return Dict{String,Any}(
        "lower" => _artifact_value(enclosure.lower),
        "upper" => _artifact_value(enclosure.upper),
    )
end

function _observation_document(observation::OracleObservation)
    return Dict{String,Any}(
        "branches" => Any[
            Dict{String,Any}(
                "choice_node" => string(branch.decision.choice_node),
                "key" => string(branch.decision.key),
                "selector_margin" => _artifact_value(branch.selector_margin),
                "validity_margin" => _artifact_value(branch.validity_margin),
            ) for branch in observation.branches
        ],
        "diagnostic" => observation.diagnostic,
        "domains" => Any[
            Dict{String,Any}(
                "margin" => _artifact_value(domain.margin),
                "node" => string(domain.node),
                "strict" => domain.strict,
                "valid" => domain.valid,
            ) for domain in observation.domains
        ],
        "evaluation_cost" => observation.evaluation_cost,
        "guards" => Any[
            Dict{String,Any}(
                "margin" => _artifact_value(guard.margin),
                "node" => string(guard.node),
                "scale" => _artifact_value(guard.scale),
                "strict" => guard.strict,
                "valid" => guard.valid,
            ) for guard in observation.guards
        ],
        "relations" => Any[
            Dict{String,Any}(
                "node" => string(relation.node),
                "raw" => _artifact_value(relation.raw),
                "scale" => _artifact_value(relation.scale),
                "scaled" => _artifact_value(relation.scaled),
                "truth" => relation.truth,
            ) for relation in observation.relations
        ],
        "status" => string(observation.status),
        "target" => observation.target isa Real ? _artifact_value(observation.target) : nothing,
    )
end

function _indexed_enclosure_document(entries)
    return Any[
        Dict{String,Any}(
            "enclosure" => _enclosure_document(entry.enclosure),
            "node" => string(entry.node),
        ) for entry in entries
    ]
end

function _branch_enclosure_document(entries)
    return Any[
        Dict{String,Any}(
            "choice_node" => string(entry.node),
            "selector" => _enclosure_document(entry.selector),
            "validity" => _enclosure_document(entry.validity),
        ) for entry in entries
    ]
end

function _canonical_validation_artifact(
    compiled,
    candidate_coordinates,
    replay_coordinates,
    fast,
    canonical,
    options,
    problem_digest,
    problem_hash_method,
    configuration_digest,
    validation_config_digest,
    method,
    precision_bits,
    failure,
    diagnostic,
    exact_failure,
    target_enclosure,
    relation_enclosures,
    guard_enclosures,
    domain_enclosures,
    branch_enclosures,
)
    payload = canonical_json(Dict{String,Any}(
        "branch_margin_enclosures" => _branch_enclosure_document(branch_enclosures),
        "candidate_configuration" => Any[_artifact_value(value) for value in candidate_coordinates],
        "canonical_observation" => _observation_document(canonical),
        "compiled_cache_key" => string(compiled.cache_identity.key),
        "configuration_hash" => string(configuration_digest),
        "configuration_hash_method" => "compiler_stable_value_v1",
        "domain_enclosures" => _indexed_enclosure_document(domain_enclosures),
        "exact_promotion_failure" => string(exact_failure),
        "fast_observation" => _observation_document(fast),
        "guard_enclosures" => _indexed_enclosure_document(guard_enclosures),
        "independent" => true,
        "method" => method,
        "precision_bits" => precision_bits,
        "problem_hash" => string(problem_digest),
        "problem_hash_method" => problem_hash_method,
        "relation_scaled_enclosures" => _indexed_enclosure_document(relation_enclosures),
        "replay_configuration" => Any[_artifact_value(value) for value in replay_coordinates],
        "schema" => "geotarget.candidate-validation/v1",
        "target_enclosure" => target_enclosure === nothing ?
                              nothing : _enclosure_document(target_enclosure),
        "validation_config" => _validation_options_document(options),
        "validation_config_hash" => string(validation_config_digest),
        "validation_diagnostic" => diagnostic === nothing ? nothing : Dict{String,Any}(
            "failure" => string(diagnostic.failure),
            "message" => diagnostic.message,
            "node" => diagnostic.node === nothing ? nothing : string(diagnostic.node),
        ),
        "validation_failure" => string(failure),
    ))
    return CertificateArtifact(
        "canonical_candidate_replay_v1",
        payload;
        media_type = "application/json",
    )
end

function _diagnostic(failure, message; node = nothing)
    return CandidateValidationDiagnostic(failure, node, String(message))
end

function _exact_failure_for_validation(failure, compiled, canonical)
    failure in (
        CANDIDATE_STRICT_GUARD_UNSEPARATED,
        CANDIDATE_NONSTRICT_GUARD_FAILED,
    ) && return EXACT_GUARD_NOT_SEPARATED
    failure == CANDIDATE_TARGET_INCONSISTENT && return EXACT_TARGET_CERT_FAILED
    failure == CANDIDATE_CANONICAL_EVALUATION_FAILED && return (
        canonical.status == EVAL_UNSUPPORTED_CAPABILITY ?
        EXACT_CAPABILITY_MISSING : EXACT_CONFIGURATION_CERT_FAILED
    )
    failure == CANDIDATE_VALIDATION_NONE || return EXACT_CONFIGURATION_CERT_FAILED
    return supports(capabilities(compiled), C3A) ? EXACT_UNSUPPORTED : EXACT_CAPABILITY_MISSING
end

function _exact_failure_detail(failure, compiled)
    failure == CANDIDATE_VALIDATION_NONE && return supports(capabilities(compiled), C3A) ?
        "candidate validation is provisional-only; exact proof requires a separate promotion stage" :
        "all-path C3A capability is unavailable; no exact claim was made"
    return "canonical candidate validation failed at $(string(failure)); no exact claim was made"
end

function _classify_candidate(
    compiled,
    replay_coordinates,
    fast,
    canonical,
    options,
    relation_enclosures,
    guard_enclosures,
    domain_enclosures,
    branch_enclosures,
    target_enclosure,
    fast_target_enclosure,
)
    canonical.status in (
        EVAL_OK,
        EVAL_INVALID_DOMAIN,
        EVAL_INVALID_BRANCH,
        EVAL_AMBIGUOUS_BRANCH,
    ) || return _diagnostic(
        CANDIDATE_CANONICAL_EVALUATION_FAILED,
        something(canonical.diagnostic, "canonical evaluator returned $(canonical.status)"),
    )
    for (relation, entry) in zip(canonical.relations, relation_enclosures)
        bound = _enclosure_bound(entry.enclosure)
        _within_tolerance(bound, options.residual_tolerance) || return _diagnostic(
            CANDIDATE_RELATION_RESIDUAL_FAILED,
            "scaled residual enclosure exceeds tolerance: $(string(bound))",
            node = relation.node,
        )
    end
    for (relation, role) in zip(canonical.relations, compiled.relations)
        _relation_truth_accepted(relation.truth, relation.raw, role.truth_policy) || return _diagnostic(
            CANDIDATE_RELATION_TRUTH_FAILED,
            "relation truth predicate rejected the canonical configuration under $(role.truth_policy)",
            node = relation.node,
        )
    end

    _candidate_outside_bounds(compiled, replay_coordinates) && return _diagnostic(
        CANDIDATE_VARIABLE_BOUNDS_FAILED,
        "canonical replay coordinates violate a declared variable bound",
    )
    for (domain, entry) in zip(canonical.domains, domain_enclosures)
        separated = domain.strict ?
                    entry.enclosure.lower > zero(entry.enclosure.lower) :
                    entry.enclosure.lower >= zero(entry.enclosure.lower)
        separated || return _diagnostic(
            CANDIDATE_DOMAIN_FAILED,
            "domain margin enclosure is not separated from its invalid side",
            node = domain.node,
        )
    end

    for (guard, entry) in zip(canonical.guards, guard_enclosures)
        if guard.strict
            entry.enclosure.lower > zero(entry.enclosure.lower) || return _diagnostic(
                CANDIDATE_STRICT_GUARD_UNSEPARATED,
                "strict guard lower bound must be greater than zero",
                node = guard.node,
            )
        else
            entry.enclosure.lower >= zero(entry.enclosure.lower) || return _diagnostic(
                CANDIDATE_NONSTRICT_GUARD_FAILED,
                "non-strict guard lower bound may not be below zero",
                node = guard.node,
            )
        end
    end

    _branch_keys_match(fast, canonical) || return _diagnostic(
        CANDIDATE_BRANCH_KEY_MISMATCH,
        "fast and canonical replay selected different branch keys",
    )
    for (branch, entry) in zip(canonical.branches, branch_enclosures)
        entry.validity.lower > zero(entry.validity.lower) || return _diagnostic(
            CANDIDATE_BRANCH_VALIDITY_FAILED,
            "branch validity lower bound must be greater than zero",
            node = branch.decision.choice_node,
        )
        entry.selector.lower > zero(entry.selector.lower) || return _diagnostic(
            CANDIDATE_BRANCH_SELECTOR_UNSEPARATED,
            "selector margin lower bound must be greater than zero",
            node = branch.decision.choice_node,
        )
    end

    canonical.status == EVAL_OK || return _diagnostic(
        CANDIDATE_CANONICAL_EVALUATION_FAILED,
        "canonical evaluator returned $(canonical.status) without a classified margin failure",
    )
    fast.status == EVAL_OK || return _diagnostic(
        CANDIDATE_FAST_OBSERVATION_FAILED,
        something(fast.diagnostic, "fast observation returned $(fast.status)"),
    )
    target_enclosure !== nothing && fast_target_enclosure !== nothing || return _diagnostic(
        CANDIDATE_TARGET_INCONSISTENT,
        "fast and canonical observations must both contain finite real targets",
    )
    _consistent_enclosures(
        fast_target_enclosure,
        target_enclosure,
        options.target_consistency_tolerance,
    ) || return _diagnostic(
        CANDIDATE_TARGET_INCONSISTENT,
        "fast and canonical target enclosures are disjoint beyond tolerance",
        node = compiled.problem.target,
    )
    return nothing
end

function _finish_candidate_validation(
    compiled,
    candidate_coordinates,
    replay_coordinates,
    fast,
    canonical,
    options,
    problem_digest,
    problem_hash_method,
    configuration_digest,
    validation_config_digest,
    method,
    precision_bits,
    oracle_work,
)
    relation_enclosures = Tuple(
        (node = relation.node, enclosure = _numeric_enclosure(relation.scaled, options)) for
        relation in canonical.relations
    )
    guard_enclosures = Tuple(
        (node = guard.node, enclosure = _numeric_enclosure(guard.margin, options)) for
        guard in canonical.guards
    )
    domain_enclosures = Tuple(
        (node = domain.node, enclosure = _numeric_enclosure(domain.margin, options)) for
        domain in canonical.domains
    )
    branch_enclosures = Tuple(
        (
            node = branch.decision.choice_node,
            validity = _numeric_enclosure(branch.validity_margin, options),
            selector = _numeric_enclosure(branch.selector_margin, options),
        ) for branch in canonical.branches
    )
    target_enclosure = canonical.target isa Real && isfinite(canonical.target) ?
                       _numeric_enclosure(
        canonical.target,
        options;
        absolute_floor=options.target_consistency_tolerance,
    ) : nothing
    fast_target_enclosure = fast.target isa Real && isfinite(fast.target) ?
                            _numeric_enclosure(
        fast.target,
        options;
        absolute_floor=options.target_consistency_tolerance,
    ) : nothing
    diagnostic = _classify_candidate(
        compiled,
        replay_coordinates,
        fast,
        canonical,
        options,
        relation_enclosures,
        guard_enclosures,
        domain_enclosures,
        branch_enclosures,
        target_enclosure,
        fast_target_enclosure,
    )
    failure = diagnostic === nothing ? CANDIDATE_VALIDATION_NONE : diagnostic.failure
    exact_failure = _exact_failure_for_validation(failure, compiled, canonical)
    artifact = _canonical_validation_artifact(
        compiled,
        candidate_coordinates,
        replay_coordinates,
        fast,
        canonical,
        options,
        problem_digest,
        problem_hash_method,
        configuration_digest,
        validation_config_digest,
        method,
        precision_bits,
        failure,
        diagnostic,
        exact_failure,
        target_enclosure,
        relation_enclosures,
        guard_enclosures,
        domain_enclosures,
        branch_enclosures,
    )

    accepted_guards = diagnostic === nothing ? Tuple(
        GuardEnclosure(guard.node, entry.enclosure, guard.strict) for
        (guard, entry) in zip(canonical.guards, guard_enclosures)
    ) : ()
    provisional = if diagnostic === nothing
        residual_bound = isempty(relation_enclosures) ?
                         (target_enclosure.lower isa BigFloat ? BigFloat(0) : 0.0) :
                         maximum(_enclosure_bound(entry.enclosure) for entry in relation_enclosures)
        evidence = NumericalValidationEvidence(
            problem_digest,
            configuration_digest,
            method,
            precision_bits,
            artifact;
            independent = true,
        )
        ProvisionalAnswer(
            target_enclosure,
            residual_bound,
            _ordered_decisions(canonical),
            evidence;
            guard_enclosures = accepted_guards,
            exact_failure,
            exact_failure_detail = _exact_failure_detail(failure, compiled),
        )
    else
        nothing
    end
    return CandidateValidationResult(
        diagnostic === nothing,
        provisional,
        failure,
        diagnostic,
        problem_digest,
        problem_hash_method,
        configuration_digest,
        validation_config_digest,
        method,
        precision_bits,
        fast,
        canonical,
        artifact,
        target_enclosure,
        accepted_guards,
        oracle_work,
        exact_failure,
    )
end

function _supports_bigfloat_replay(compiled::CompiledProblem)
    supports(capabilities(compiled), C2) || return false
    return all(variable -> BigFloat(0) isa variable.runtime_type, compiled.variables)
end

"""
Independently replay a discovered candidate through the canonical interpreter.

This gate can produce only a `ProvisionalAnswer`. Exact promotion belongs to a
separate proof stage and cannot be inferred from numerical agreement.
"""
function validate_candidate(
    compiled::CompiledProblem,
    x::AbstractVector;
    options::CandidateValidationOptions = CandidateValidationOptions(),
    fast_observation::Union{Nothing,OracleObservation} = nothing,
)
    length(x) == length(compiled.variables) || throw(
        ArgumentError("expected $(length(compiled.variables)) variables, received $(length(x))"),
    )
    candidate_coordinates = Tuple(deepcopy(value) for value in x)
    fast = fast_observation === nothing ? evaluate(compiled, x; capability = C0) : fast_observation
    fast_work = fast_observation === nothing ? fast.evaluation_cost : 0
    problem_digest, problem_hash_method = _candidate_problem_identity(compiled)
    configuration_digest = _candidate_configuration_hash(compiled, x)
    validation_config_digest = _validation_config_hash(options)

    if _supports_bigfloat_replay(compiled)
        return setprecision(BigFloat, options.precision_bits) do
            replay_coordinates = BigFloat[BigFloat(value) for value in x]
            canonical = evaluate_canonical(compiled, replay_coordinates; capability = C2)
            _finish_candidate_validation(
                compiled,
                candidate_coordinates,
                Tuple(replay_coordinates),
                fast,
                canonical,
                options,
                problem_digest,
                problem_hash_method,
                configuration_digest,
                validation_config_digest,
                "canonical_bigfloat_recheck",
                options.precision_bits,
                fast_work + canonical.evaluation_cost,
            )
        end
    end

    replay_coordinates = Tuple(deepcopy(value) for value in x)
    canonical = evaluate_canonical(compiled, collect(replay_coordinates); capability = C0)
    return setprecision(BigFloat, 53) do
        _finish_candidate_validation(
            compiled,
            candidate_coordinates,
            replay_coordinates,
            fast,
            canonical,
            options,
            problem_digest,
            problem_hash_method,
            configuration_digest,
            validation_config_digest,
            "canonical_c0_second_pass",
            53,
            fast_work + canonical.evaluation_cost,
        )
    end
end

function validate_candidate(
    compiled::CompiledProblem,
    attempt::LocalAttempt;
    options::CandidateValidationOptions = CandidateValidationOptions(),
)
    return validate_candidate(
        compiled,
        collect(attempt.final);
        options,
        fast_observation = attempt.observation,
    )
end
