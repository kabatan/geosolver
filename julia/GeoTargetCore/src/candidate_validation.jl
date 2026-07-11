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
    CANDIDATE_HIGH_PRECISION_CAPABILITY_MISSING = 13
    CANDIDATE_PRIMARY_REFINEMENT_FAILED = 14
    CANDIDATE_REFERENCE_REFINEMENT_FAILED = 15
    CANDIDATE_PRECISION_COORDINATE_MISMATCH = 16
    CANDIDATE_PRECISION_TARGET_MISMATCH = 17
    CANDIDATE_PRECISION_BRANCH_MISMATCH = 18
    CANDIDATE_VALIDATION_CANCELLED = 19
    CANDIDATE_VALIDATION_DEADLINE_REACHED = 20
    CANDIDATE_VALIDATION_ORACLE_BUDGET_EXHAUSTED = 21
    CANDIDATE_HIGH_PRECISION_DOWNGRADE = 22
end

struct CandidateValidationDiagnostic
    failure::CandidateValidationFailure
    node::Union{Nothing,NodeId}
    message::String
end

struct CandidateValidationOptions
    primary_precision_bits::Int
    precision_bits::Int
    refinement_residual_goal::Float64
    residual_tolerance::Float64
    coordinate_stability_tolerance::Float64
    enclosure_absolute_error::Float64
    enclosure_relative_error::Float64
    target_consistency_tolerance::Float64
    roundoff_multiplier::Float64
    max_refinement_iterations::Int

    function CandidateValidationOptions(
        ;
        primary_precision_bits::Integer = 512,
        precision_bits::Integer = 768,
        refinement_residual_goal::Real = 1.0e-110,
        residual_tolerance::Real = 1.0e-100,
        coordinate_stability_tolerance::Real = 1.0e-100,
        enclosure_absolute_error::Real = 0.0,
        enclosure_relative_error::Real = 0.0,
        target_consistency_tolerance::Real = 1.0e-100,
        roundoff_multiplier::Real = 8.0,
        max_refinement_iterations::Integer = 16,
    )
        primary_precision_bits == 512 || throw(
            ArgumentError("primary_precision_bits is fixed at 512"),
        )
        precision_bits == 768 || throw(
            ArgumentError("precision_bits is fixed at 768"),
        )
        nonnegative = Float64.((
            refinement_residual_goal,
            residual_tolerance,
            coordinate_stability_tolerance,
            enclosure_absolute_error,
            enclosure_relative_error,
            target_consistency_tolerance,
        ))
        all(value -> isfinite(value) && value >= 0, nonnegative) || throw(
            ArgumentError("validation tolerances must be finite and nonnegative"),
        )
        nonnegative[1] <= 1.0e-110 || throw(
            ArgumentError("refinement_residual_goal may not exceed 1e-110"),
        )
        nonnegative[2] <= 1.0e-100 || throw(
            ArgumentError("residual_tolerance may not exceed 1e-100"),
        )
        nonnegative[3] <= 1.0e-100 || throw(
            ArgumentError("coordinate_stability_tolerance may not exceed 1e-100"),
        )
        nonnegative[6] <= 1.0e-100 || throw(
            ArgumentError("target_consistency_tolerance may not exceed 1e-100"),
        )
        1 <= max_refinement_iterations <= 64 || throw(
            ArgumentError("max_refinement_iterations must lie in 1:64"),
        )
        frozen_roundoff_multiplier = Float64(roundoff_multiplier)
        isfinite(frozen_roundoff_multiplier) && frozen_roundoff_multiplier > 0 || throw(
            ArgumentError("roundoff_multiplier must be finite and positive"),
        )
        return new(
            Int(primary_precision_bits),
            Int(precision_bits),
            nonnegative...,
            frozen_roundoff_multiplier,
            Int(max_refinement_iterations),
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
    canonical_coordinates::Tuple
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
        canonical_coordinates,
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
            Tuple(deepcopy(value) for value in canonical_coordinates),
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
        "coordinate_stability_tolerance" => string(options.coordinate_stability_tolerance),
        "enclosure_absolute_error" => string(options.enclosure_absolute_error),
        "enclosure_relative_error" => string(options.enclosure_relative_error),
        "max_refinement_iterations" => options.max_refinement_iterations,
        "precision_bits" => options.precision_bits,
        "primary_precision_bits" => options.primary_precision_bits,
        "refinement_residual_goal" => string(options.refinement_residual_goal),
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

function _diagnostic(failure, message; node = nothing)
    return CandidateValidationDiagnostic(failure, node, String(message))
end

function _high_precision_work_document(work::HighPrecisionWorkSnapshot)
    return Dict{String,Any}(
        "evaluations" => work.evaluations,
        "precision_bits" => work.precision_bits,
        "precision_weight" => work.weight,
        "raw_oracle_work" => work.raw_oracle_work,
        "weighted_oracle_work" => work.oracle_work,
    )
end

function _root_evidence_document(evidence::HighPrecisionRootEvidence)
    return Dict{String,Any}(
        "condition_estimate" => _artifact_value(evidence.condition_estimate),
        "configuration" => Any[_artifact_value(value) for value in evidence.coordinates],
        "correction_bound" => _artifact_value(evidence.correction_bound),
        "iterations" => evidence.iterations,
        "method" => evidence.method,
        "numerical_rank" => evidence.numerical_rank,
        "observation" => _observation_document(evidence.observation),
        "precision_bits" => evidence.precision_bits,
        "rank_stable" => evidence.rank_stable,
        "residual_bound" => _artifact_value(evidence.residual_bound),
        "target_error_bound" => _artifact_value(evidence.target_error_bound),
        "work" => _high_precision_work_document(evidence.work),
    )
end

function _candidate_validation_artifact_v2(
    compiled,
    candidate_coordinates,
    replay_coordinates,
    fast,
    canonical,
    options,
    problem_digest,
    problem_hash_method,
    candidate_configuration_digest,
    configuration_digest,
    validation_config_digest,
    method,
    failure,
    diagnostic,
    exact_failure,
    target_enclosure,
    relation_enclosures,
    guard_enclosures,
    domain_enclosures,
    branch_enclosures,
    primary,
    reference,
    replay_work,
    coordinate_disagreement,
    target_disagreement,
)
    payload = canonical_json(Dict{String,Any}(
        "branch_margin_enclosures" => _branch_enclosure_document(branch_enclosures),
        "candidate_configuration" => Any[_artifact_value(value) for value in candidate_coordinates],
        "candidate_configuration_hash" => string(candidate_configuration_digest),
        "canonical_observation" => _observation_document(canonical),
        "canonical_replay_work" => _high_precision_work_document(replay_work),
        "compiled_cache_key" => string(compiled.cache_identity.key),
        "configuration_hash" => string(configuration_digest),
        "configuration_hash_method" => "compiler_stable_value_v1",
        "coordinate_disagreement" => _artifact_value(coordinate_disagreement),
        "domain_enclosures" => _indexed_enclosure_document(domain_enclosures),
        "exact_promotion_failure" => string(exact_failure),
        "fast_observation" => _observation_document(fast),
        "guard_enclosures" => _indexed_enclosure_document(guard_enclosures),
        "independence" => Dict{String,Any}(
            "canonical_interpreter" => "reference_interpreter",
            "canonical_start" => "original_float64_endpoint",
            "primary_interpreter" => "compiled_plan",
            "primary_start" => "original_float64_endpoint",
        ),
        "method" => method,
        "precision_bits" => options.precision_bits,
        "primary_root_evidence" => primary === nothing ?
                                   nothing : _root_evidence_document(primary.evidence),
        "problem_hash" => string(problem_digest),
        "problem_hash_method" => problem_hash_method,
        "reference_root_evidence" => reference === nothing ?
                                     nothing : _root_evidence_document(reference.evidence),
        "relation_scaled_enclosures" => _indexed_enclosure_document(relation_enclosures),
        "replay_configuration" => Any[_artifact_value(value) for value in replay_coordinates],
        "schema" => "geotarget.candidate-validation/v2",
        "target_disagreement" => _artifact_value(target_disagreement),
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
        "canonical_candidate_confirmation_v2",
        payload;
        media_type="application/json",
    )
end

function _exact_failure_for_validation(failure, compiled, canonical)
    failure in (
        CANDIDATE_STRICT_GUARD_UNSEPARATED,
        CANDIDATE_NONSTRICT_GUARD_FAILED,
    ) && return EXACT_GUARD_NOT_SEPARATED
    failure in (
        CANDIDATE_TARGET_INCONSISTENT,
        CANDIDATE_PRECISION_TARGET_MISMATCH,
    ) && return EXACT_TARGET_CERT_FAILED
    failure in (
        CANDIDATE_HIGH_PRECISION_CAPABILITY_MISSING,
        CANDIDATE_HIGH_PRECISION_DOWNGRADE,
    ) && return EXACT_CAPABILITY_MISSING
    failure in (
        CANDIDATE_VALIDATION_CANCELLED,
        CANDIDATE_VALIDATION_DEADLINE_REACHED,
        CANDIDATE_VALIDATION_ORACLE_BUDGET_EXHAUSTED,
    ) && return EXACT_BUDGET_EXHAUSTED
    failure == CANDIDATE_CANONICAL_EVALUATION_FAILED && return (
        canonical.status == EVAL_UNSUPPORTED_CAPABILITY ?
        EXACT_CAPABILITY_MISSING : EXACT_CONFIGURATION_CERT_FAILED
    )
    failure == CANDIDATE_VALIDATION_NONE || return EXACT_CONFIGURATION_CERT_FAILED
    return supports(capabilities(compiled), C3A) ? EXACT_UNSUPPORTED : EXACT_CAPABILITY_MISSING
end

function _exact_failure_detail(failure, compiled)
    failure == CANDIDATE_VALIDATION_NONE && return supports(capabilities(compiled), C3A) ?
        "numerical confirmation is provisional-only; exact proof requires a separate promotion stage" :
        "all-path C3A capability is unavailable; no exact claim was made"
    return "numerical candidate confirmation failed at $(string(failure)); no exact claim was made"
end

function _candidate_semantic_enclosures(observation, options)
    relations = Tuple(
        (node=relation.node, enclosure=_numeric_enclosure(relation.scaled, options)) for
        relation in observation.relations
    )
    guards = Tuple(
        (node=guard.node, enclosure=_numeric_enclosure(guard.margin, options)) for
        guard in observation.guards
    )
    domains = Tuple(
        (node=domain.node, enclosure=_numeric_enclosure(domain.margin, options)) for
        domain in observation.domains
    )
    branches = Tuple(
        (
            node=branch.decision.choice_node,
            validity=_numeric_enclosure(branch.validity_margin, options),
            selector=_numeric_enclosure(branch.selector_margin, options),
        ) for branch in observation.branches
    )
    return (; relations, guards, domains, branches)
end

function _classify_semantic_observation(
    compiled,
    coordinates,
    observation,
    options,
    enclosures,
)
    observation.status in (
        EVAL_OK,
        EVAL_INVALID_DOMAIN,
        EVAL_INVALID_BRANCH,
        EVAL_AMBIGUOUS_BRANCH,
    ) || return _diagnostic(
        CANDIDATE_CANONICAL_EVALUATION_FAILED,
        something(observation.diagnostic, "canonical evaluator returned $(observation.status)"),
    )
    length(observation.relations) == length(compiled.relations) || return _diagnostic(
        CANDIDATE_CANONICAL_EVALUATION_FAILED,
        "canonical relation observation count changed",
    )
    for (relation, entry) in zip(observation.relations, enclosures.relations)
        bound = _enclosure_bound(entry.enclosure)
        _within_tolerance(bound, options.residual_tolerance) || return _diagnostic(
            CANDIDATE_RELATION_RESIDUAL_FAILED,
            "scaled residual enclosure exceeds 1e-100 confirmation tolerance: $(string(bound))",
            node=relation.node,
        )
    end
    for (relation, role) in zip(observation.relations, compiled.relations)
        _relation_truth_accepted(relation.truth, relation.raw, role.truth_policy) || return _diagnostic(
            CANDIDATE_RELATION_TRUTH_FAILED,
            "relation truth predicate rejected the confirmed configuration under $(role.truth_policy)",
            node=relation.node,
        )
    end
    _candidate_outside_bounds(compiled, coordinates) && return _diagnostic(
        CANDIDATE_VARIABLE_BOUNDS_FAILED,
        "confirmed coordinates violate a declared variable bound",
    )
    for (domain, entry) in zip(observation.domains, enclosures.domains)
        separated = domain.strict ? entry.enclosure.lower > 0 : entry.enclosure.lower >= 0
        separated || return _diagnostic(
            CANDIDATE_DOMAIN_FAILED,
            "domain margin enclosure is not separated from its invalid side",
            node=domain.node,
        )
    end
    for (guard, entry) in zip(observation.guards, enclosures.guards)
        if guard.strict
            entry.enclosure.lower > 0 || return _diagnostic(
                CANDIDATE_STRICT_GUARD_UNSEPARATED,
                "strict guard lower bound must be greater than zero",
                node=guard.node,
            )
        else
            entry.enclosure.lower >= 0 || return _diagnostic(
                CANDIDATE_NONSTRICT_GUARD_FAILED,
                "non-strict guard lower bound may not be below zero",
                node=guard.node,
            )
        end
    end
    for (branch, entry) in zip(observation.branches, enclosures.branches)
        entry.validity.lower > 0 || return _diagnostic(
            CANDIDATE_BRANCH_VALIDITY_FAILED,
            "branch validity lower bound must be greater than zero",
            node=branch.decision.choice_node,
        )
        entry.selector.lower > 0 || return _diagnostic(
            CANDIDATE_BRANCH_SELECTOR_UNSEPARATED,
            "selector margin lower bound must be greater than zero",
            node=branch.decision.choice_node,
        )
    end
    observation.status == EVAL_OK || return _diagnostic(
        CANDIDATE_CANONICAL_EVALUATION_FAILED,
        "canonical evaluator returned $(observation.status) without a classified margin failure",
    )
    observation.target isa Real && isfinite(observation.target) || return _diagnostic(
        CANDIDATE_TARGET_INCONSISTENT,
        "confirmed observation did not contain a finite real target",
        node=compiled.problem.target,
    )
    return nothing
end

function _candidate_target_enclosure(primary, reference, canonical, options)
    observations = (
        (primary.evidence.observation, primary.evidence.target_error_bound),
        (reference.evidence.observation, reference.evidence.target_error_bound),
        (canonical, BigFloat(0)),
    )
    enclosures = NumericEnclosure[]
    for (observation, relative_error) in observations
        target = observation.target
        target isa Real && isfinite(target) || return nothing
        center = BigFloat(target)
        absolute_error = BigFloat(relative_error) * max(one(BigFloat), abs(center))
        push!(enclosures, _numeric_enclosure(center, options; absolute_floor=absolute_error))
    end
    return NumericEnclosure(
        minimum(enclosure.lower for enclosure in enclosures),
        maximum(enclosure.upper for enclosure in enclosures),
    )
end

function _candidate_precision_disagreement(compiled, primary, reference, canonical)
    primary_normalized = _high_precision_normalized(
        compiled,
        collect(primary.evidence.coordinates),
    )
    canonical_normalized = _high_precision_normalized(
        compiled,
        collect(reference.evidence.coordinates),
    )
    coordinate = isempty(primary_normalized) ? BigFloat(0) :
                 norm(primary_normalized - canonical_normalized, Inf)
    primary_target = BigFloat(primary.evidence.observation.target)
    reference_target = BigFloat(reference.evidence.observation.target)
    replay_target = canonical.target isa Real ? BigFloat(canonical.target) : BigFloat(Inf)
    target_scale = max(
        one(BigFloat),
        abs(primary_target),
        abs(reference_target),
        abs(replay_target),
    )
    target = max(
        abs(primary_target - replay_target),
        abs(reference_target - replay_target),
    ) / target_scale
    return coordinate, target
end

function _candidate_failure_from_refinement(result, primary_stage::Bool)
    result.failure == HIGH_PRECISION_REFINEMENT_CANCELLED &&
        return CANDIDATE_VALIDATION_CANCELLED
    result.failure == HIGH_PRECISION_REFINEMENT_DEADLINE_REACHED &&
        return CANDIDATE_VALIDATION_DEADLINE_REACHED
    result.failure == HIGH_PRECISION_REFINEMENT_ORACLE_BUDGET_EXHAUSTED &&
        return CANDIDATE_VALIDATION_ORACLE_BUDGET_EXHAUSTED
    result.failure == HIGH_PRECISION_REFINEMENT_PRECISION_DOWNGRADE &&
        return CANDIDATE_HIGH_PRECISION_DOWNGRADE
    return primary_stage ?
           CANDIDATE_PRIMARY_REFINEMENT_FAILED : CANDIDATE_REFERENCE_REFINEMENT_FAILED
end

function _empty_high_precision_work(bits::Int)
    return HighPrecisionWorkSnapshot(bits, _high_precision_weight(bits), 0, 0, 0)
end

function _finish_candidate_validation(
    compiled,
    candidate_coordinates,
    fast,
    options,
    problem_digest,
    problem_hash_method,
    validation_config_digest,
    primary,
    reference,
    replay_coordinates,
    canonical,
    replay_work,
    oracle_work;
    forced_diagnostic=nothing,
)
    method = "compiled512_reference768_confirmation"
    replay_coordinates = Tuple(replay_coordinates)
    candidate_configuration_digest = _candidate_configuration_hash(
        compiled,
        collect(candidate_coordinates),
    )
    configuration_digest = isempty(replay_coordinates) && !isempty(candidate_coordinates) ?
                           candidate_configuration_digest :
                           _candidate_configuration_hash(compiled, collect(replay_coordinates))
    semantic = setprecision(BigFloat, options.precision_bits) do
        _candidate_semantic_enclosures(canonical, options)
    end
    target_enclosure = if primary === nothing || reference === nothing
        nothing
    else
        setprecision(BigFloat, options.precision_bits) do
            _candidate_target_enclosure(primary, reference, canonical, options)
        end
    end
    coordinate_disagreement, target_disagreement = if primary === nothing || reference === nothing
        BigFloat(Inf), BigFloat(Inf)
    else
        setprecision(BigFloat, options.precision_bits) do
            _candidate_precision_disagreement(compiled, primary, reference, canonical)
        end
    end

    diagnostic = forced_diagnostic
    if diagnostic === nothing && primary !== nothing && reference !== nothing
        primary_semantic = setprecision(BigFloat, options.primary_precision_bits) do
            _candidate_semantic_enclosures(primary.evidence.observation, options)
        end
        reference_semantic = setprecision(BigFloat, options.precision_bits) do
            _candidate_semantic_enclosures(reference.evidence.observation, options)
        end
        diagnostic = _classify_semantic_observation(
            compiled,
            primary.evidence.coordinates,
            primary.evidence.observation,
            options,
            primary_semantic,
        )
        diagnostic === nothing && (diagnostic = _classify_semantic_observation(
            compiled,
            reference.evidence.coordinates,
            reference.evidence.observation,
            options,
            reference_semantic,
        ))
        diagnostic === nothing && (diagnostic = _classify_semantic_observation(
            compiled,
            replay_coordinates,
            canonical,
            options,
            semantic,
        ))
        if diagnostic === nothing && fast.status != EVAL_OK
            diagnostic = _diagnostic(
                CANDIDATE_FAST_OBSERVATION_FAILED,
                something(fast.diagnostic, "fast observation returned $(fast.status)"),
            )
        end
        if diagnostic === nothing && !(
            _branch_keys_match(fast, primary.evidence.observation) &&
            _branch_keys_match(primary.evidence.observation, reference.evidence.observation) &&
            _branch_keys_match(reference.evidence.observation, canonical)
        )
            diagnostic = _diagnostic(
                CANDIDATE_PRECISION_BRANCH_MISMATCH,
                "Float64, compiled-512 and reference-768 branch keys disagree",
            )
        end
        if diagnostic === nothing &&
           coordinate_disagreement > BigFloat(options.coordinate_stability_tolerance)
            diagnostic = _diagnostic(
                CANDIDATE_PRECISION_COORDINATE_MISMATCH,
                "512-bit and independent 768-bit normalized coordinates differ by $(coordinate_disagreement)",
            )
        end
        if diagnostic === nothing &&
           target_disagreement > BigFloat(options.target_consistency_tolerance)
            diagnostic = _diagnostic(
                CANDIDATE_PRECISION_TARGET_MISMATCH,
                "512-bit and independent 768-bit targets differ by $(target_disagreement)",
                node=compiled.problem.target,
            )
        end
    end
    failure = diagnostic === nothing ? CANDIDATE_VALIDATION_NONE : diagnostic.failure
    exact_failure = _exact_failure_for_validation(failure, compiled, canonical)
    artifact = _candidate_validation_artifact_v2(
        compiled,
        candidate_coordinates,
        replay_coordinates,
        fast,
        canonical,
        options,
        problem_digest,
        problem_hash_method,
        candidate_configuration_digest,
        configuration_digest,
        validation_config_digest,
        method,
        failure,
        diagnostic,
        exact_failure,
        target_enclosure,
        semantic.relations,
        semantic.guards,
        semantic.domains,
        semantic.branches,
        primary,
        reference,
        replay_work,
        coordinate_disagreement,
        target_disagreement,
    )
    accepted_guards = diagnostic === nothing ? Tuple(
        GuardEnclosure(guard.node, entry.enclosure, guard.strict) for
        (guard, entry) in zip(canonical.guards, semantic.guards)
    ) : ()
    provisional = if diagnostic === nothing
        residual_bounds = BigFloat[
            primary.evidence.residual_bound,
            reference.evidence.residual_bound,
        ]
        append!(
            residual_bounds,
            BigFloat[_enclosure_bound(entry.enclosure) for entry in semantic.relations],
        )
        residual_bound = isempty(residual_bounds) ? BigFloat(0) : maximum(residual_bounds)
        evidence = NumericalValidationEvidence(
            problem_digest,
            configuration_digest,
            method,
            options.precision_bits,
            artifact;
            independent=true,
        )
        ProvisionalAnswer(
            target_enclosure,
            residual_bound,
            _ordered_decisions(canonical),
            evidence;
            guard_enclosures=accepted_guards,
            exact_failure,
            exact_failure_detail=_exact_failure_detail(failure, compiled),
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
        options.precision_bits,
        fast,
        replay_coordinates,
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

function _remaining_candidate_work(limit::Int, consumed::Int)
    limit == typemax(Int) && return typemax(Int)
    return consumed >= limit ? 0 : limit - consumed
end

function _add_candidate_work(consumed::Int, addition::Int, limit::Int)
    addition >= 0 || throw(InvariantError(:negative_oracle_work, "candidate work is negative"))
    consumed <= limit || throw(InvariantError(:oracle_budget_overdrawn, "candidate work exceeds its limit"))
    addition <= limit - consumed || throw(
        InvariantError(:oracle_budget_overdrawn, "candidate stage exceeded its reserved work"),
    )
    return consumed + addition
end

function _candidate_resource_diagnostic(failure, message)
    return _diagnostic(failure, message)
end

"""
Refine and confirm a discovered endpoint at independent high precisions.

The primary run uses the compiled C2 plan at 512 bits. A second run starts
again from the original endpoint and uses the canonical reference interpreter
at 768 bits, followed by a fresh reference replay. Only stable, isolated
configurations satisfying the 1e-100 numerical gates can produce a
`ProvisionalAnswer`. C2 absence is a typed non-promotion, never a C0 fallback.
"""
function validate_candidate(
    compiled::CompiledProblem,
    x::AbstractVector;
    options::CandidateValidationOptions=CandidateValidationOptions(),
    fast_observation::Union{Nothing,OracleObservation}=nothing,
    deadline_ns::UInt64=typemax(UInt64),
    cancelled=() -> false,
    remaining_oracle_work::Integer=typemax(Int),
)
    length(x) == length(compiled.variables) || throw(
        ArgumentError("expected $(length(compiled.variables)) variables, received $(length(x))"),
    )
    remaining_oracle_work isa Bool && throw(
        ArgumentError("remaining_oracle_work must be an integer count, not Bool"),
    )
    0 <= remaining_oracle_work <= typemax(Int) || throw(
        ArgumentError("remaining_oracle_work must be nonnegative"),
    )
    limit = Int(remaining_oracle_work)
    candidate_coordinates = Tuple(deepcopy(value) for value in x)
    problem_digest, problem_hash_method = _candidate_problem_identity(compiled)
    validation_config_digest = _validation_config_hash(options)
    empty_observation = _high_precision_empty_observation("confirmation stage was not run")
    empty_work = _empty_high_precision_work(options.precision_bits)
    fast_work = 0
    fast = if fast_observation !== nothing
        fast_observation
    else
        if cancelled()
            return _finish_candidate_validation(
                compiled,
                candidate_coordinates,
                empty_observation,
                options,
                problem_digest,
                problem_hash_method,
                validation_config_digest,
                nothing,
                nothing,
                candidate_coordinates,
                empty_observation,
                empty_work,
                0;
                forced_diagnostic=_candidate_resource_diagnostic(
                    CANDIDATE_VALIDATION_CANCELLED,
                    "candidate confirmation was cancelled before the fast observation",
                ),
            )
        end
        if time_ns() >= deadline_ns
            return _finish_candidate_validation(
                compiled,
                candidate_coordinates,
                empty_observation,
                options,
                problem_digest,
                problem_hash_method,
                validation_config_digest,
                nothing,
                nothing,
                candidate_coordinates,
                empty_observation,
                empty_work,
                0;
                forced_diagnostic=_candidate_resource_diagnostic(
                    CANDIDATE_VALIDATION_DEADLINE_REACHED,
                    "candidate confirmation reached its deadline before the fast observation",
                ),
            )
        end
        if compiled.logical_evaluation_cost > limit
            return _finish_candidate_validation(
                compiled,
                candidate_coordinates,
                empty_observation,
                options,
                problem_digest,
                problem_hash_method,
                validation_config_digest,
                nothing,
                nothing,
                candidate_coordinates,
                empty_observation,
                empty_work,
                0;
                forced_diagnostic=_candidate_resource_diagnostic(
                    CANDIDATE_VALIDATION_ORACLE_BUDGET_EXHAUSTED,
                    "candidate confirmation cannot reserve the fast observation",
                ),
            )
        end
        observation = evaluate(compiled, x; capability=C0)
        _check_logical_evaluation_bound(compiled, observation)
        fast_work = observation.evaluation_cost
        observation
    end
    consumed = fast_work

    if !_supports_bigfloat_replay(compiled)
        return _finish_candidate_validation(
            compiled,
            candidate_coordinates,
            fast,
            options,
            problem_digest,
            problem_hash_method,
            validation_config_digest,
            nothing,
            nothing,
            candidate_coordinates,
            empty_observation,
            empty_work,
            consumed;
            forced_diagnostic=_diagnostic(
                CANDIDATE_HIGH_PRECISION_CAPABILITY_MISSING,
                "all-path C2 high-precision capability is required for a numerical answer",
            ),
        )
    end

    primary = _run_high_precision_refinement(
        compiled,
        collect(candidate_coordinates);
        precision_bits=options.primary_precision_bits,
        evaluator_kind=:compiled,
        residual_goal=options.refinement_residual_goal,
        configuration_tolerance=options.coordinate_stability_tolerance,
        target_tolerance=options.target_consistency_tolerance,
        deadline_ns,
        cancelled,
        remaining_oracle_work=_remaining_candidate_work(limit, consumed),
        max_iterations=options.max_refinement_iterations,
    )
    consumed = _add_candidate_work(consumed, primary.evidence.work.oracle_work, limit)
    if !primary.accepted
        candidate_failure = _candidate_failure_from_refinement(primary, true)
        return _finish_candidate_validation(
            compiled,
            candidate_coordinates,
            fast,
            options,
            problem_digest,
            problem_hash_method,
            validation_config_digest,
            primary,
            nothing,
            candidate_coordinates,
            empty_observation,
            empty_work,
            consumed;
            forced_diagnostic=_diagnostic(
                candidate_failure,
                "primary 512-bit refinement failed: $(primary.diagnostic)",
            ),
        )
    end

    reference = _run_high_precision_refinement(
        compiled,
        collect(candidate_coordinates);
        precision_bits=options.precision_bits,
        evaluator_kind=:reference,
        residual_goal=options.refinement_residual_goal,
        configuration_tolerance=options.coordinate_stability_tolerance,
        target_tolerance=options.target_consistency_tolerance,
        deadline_ns,
        cancelled,
        remaining_oracle_work=_remaining_candidate_work(limit, consumed),
        max_iterations=options.max_refinement_iterations,
    )
    consumed = _add_candidate_work(consumed, reference.evidence.work.oracle_work, limit)
    if !reference.accepted
        candidate_failure = _candidate_failure_from_refinement(reference, false)
        return _finish_candidate_validation(
            compiled,
            candidate_coordinates,
            fast,
            options,
            problem_digest,
            problem_hash_method,
            validation_config_digest,
            primary,
            reference,
            reference.evidence.coordinates,
            reference.evidence.observation,
            empty_work,
            consumed;
            forced_diagnostic=_diagnostic(
                candidate_failure,
                "independent 768-bit refinement failed: $(reference.diagnostic)",
            ),
        )
    end

    replay = _run_high_precision_replay(
        compiled,
        collect(reference.evidence.coordinates);
        precision_bits=options.precision_bits,
        deadline_ns,
        cancelled,
        remaining_oracle_work=_remaining_candidate_work(limit, consumed),
    )
    consumed = _add_candidate_work(consumed, replay.work.oracle_work, limit)
    if replay.failure != HIGH_PRECISION_REFINEMENT_NONE
        candidate_failure = if replay.failure == HIGH_PRECISION_REFINEMENT_CANCELLED
            CANDIDATE_VALIDATION_CANCELLED
        elseif replay.failure == HIGH_PRECISION_REFINEMENT_DEADLINE_REACHED
            CANDIDATE_VALIDATION_DEADLINE_REACHED
        elseif replay.failure == HIGH_PRECISION_REFINEMENT_ORACLE_BUDGET_EXHAUSTED
            CANDIDATE_VALIDATION_ORACLE_BUDGET_EXHAUSTED
        elseif replay.failure == HIGH_PRECISION_REFINEMENT_PRECISION_DOWNGRADE
            CANDIDATE_HIGH_PRECISION_DOWNGRADE
        else
            CANDIDATE_CANONICAL_EVALUATION_FAILED
        end
        return _finish_candidate_validation(
            compiled,
            candidate_coordinates,
            fast,
            options,
            problem_digest,
            problem_hash_method,
            validation_config_digest,
            primary,
            reference,
            replay.coordinates,
            replay.observation,
            replay.work,
            consumed;
            forced_diagnostic=_diagnostic(
                candidate_failure,
                "fresh 768-bit canonical replay did not complete",
            ),
        )
    end
    return _finish_candidate_validation(
        compiled,
        candidate_coordinates,
        fast,
        options,
        problem_digest,
        problem_hash_method,
        validation_config_digest,
        primary,
        reference,
        replay.coordinates,
        replay.observation,
        replay.work,
        consumed,
    )
end

function validate_candidate(
    compiled::CompiledProblem,
    attempt::LocalAttempt;
    options::CandidateValidationOptions=CandidateValidationOptions(),
    kwargs...,
)
    return validate_candidate(
        compiled,
        collect(attempt.final);
        options,
        fast_observation=attempt.observation,
        kwargs...,
    )
end
