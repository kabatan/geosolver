const EXACT_BACKEND_ABI_VERSION = v"1.1.0"
const _MAX_EXACT_SAMPLE_PRECISION_BITS = 4096

"""Optional exactification implementation. Concrete backends live outside Core."""
abstract type AbstractExactBackend end

"""Stable identity reported by an optional exactification backend."""
struct ExactBackendDescriptor
    id::String
    version::VersionNumber
    method::String
    backend_abi_version::VersionNumber
    configuration_certificate_schemes::Tuple
    target_certificate_schemes::Tuple
    policy_identity::ContentHash
    environment_identity::ContentHash

    function ExactBackendDescriptor(
        id::AbstractString,
        version::VersionNumber,
        method::AbstractString,
        ;
        backend_abi_version::VersionNumber=EXACT_BACKEND_ABI_VERSION,
        configuration_certificate_schemes,
        target_certificate_schemes,
        policy_identity::ContentHash,
        environment_identity::ContentHash,
    )
        frozen_id = String(id)
        frozen_method = String(method)
        occursin(r"^[a-z][a-z0-9_.-]*$", frozen_id) || throw(
            ArgumentError("exact backend id must be a lowercase stable identifier"),
        )
        !isempty(frozen_method) || throw(ArgumentError("exact backend method cannot be empty"))
        backend_abi_version == EXACT_BACKEND_ABI_VERSION || throw(
            ArgumentError("exact backend ABI version is incompatible with this Core build"),
        )
        freeze_schemes(values, role) = begin
            values isa Tuple || throw(ArgumentError("$role certificate schemes must be a tuple"))
            all(value -> value isa AbstractString, values) || throw(
                ArgumentError("$role certificate schemes must contain only strings"),
            )
            frozen = Tuple(String(value) for value in values)
            !isempty(frozen) || throw(ArgumentError("$role certificate schemes cannot be empty"))
            allunique(frozen) || throw(ArgumentError("$role certificate schemes must be unique"))
            all(value -> occursin(r"^[a-z][a-z0-9_.-]*$", value), frozen) || throw(
                ArgumentError("$role certificate schemes must be stable lowercase identifiers"),
            )
            frozen
        end
        configuration_schemes = freeze_schemes(
            configuration_certificate_schemes,
            "configuration",
        )
        target_schemes = freeze_schemes(target_certificate_schemes, "target")
        return new(
            frozen_id,
            version,
            frozen_method,
            backend_abi_version,
            configuration_schemes,
            target_schemes,
            policy_identity,
            environment_identity,
        )
    end
end

@enum ExactSampleFailure::UInt8 begin
    EXACT_SAMPLE_NONE = 0
    EXACT_SAMPLE_INVALID_REQUEST = 1
    EXACT_SAMPLE_INVALID_CANDIDATE = 2
    EXACT_SAMPLE_CANCELLED = 3
    EXACT_SAMPLE_DEADLINE_REACHED = 4
    EXACT_SAMPLE_ORACLE_BUDGET_EXHAUSTED = 5
    EXACT_SAMPLE_REFINEMENT_FAILED = 6
    EXACT_SAMPLE_BRANCH_MISMATCH = 7
    EXACT_SAMPLE_PRECISION_DOWNGRADE = 8
    EXACT_SAMPLE_GATE_FAILED = 9
    EXACT_SAMPLE_INTERNAL_ERROR = 10
end

"""Precision-dependent gates used to produce an algebraic-recognition sample."""
struct ExactSampleGates
    precision_bits::Int
    accuracy_bits::Int
    residual_accuracy_bits::Int
    residual_goal::BigFloat
    correction_tolerance::BigFloat
    target_tolerance::BigFloat
end

struct ExactSampleWork
    evaluations::Int
    raw_oracle_work::Int
    oracle_work::Int

    function ExactSampleWork(evaluations::Int, raw_oracle_work::Int, oracle_work::Int)
        all(>=(0), (evaluations, raw_oracle_work, oracle_work)) || throw(
            InvariantError(:negative_exact_sample_work, "exact sample work cannot be negative"),
        )
        return new(evaluations, raw_oracle_work, oracle_work)
    end
end

"""One branch-stable arbitrary-precision root/target sample owned by Core."""
struct ExactPrecisionSample
    precision_bits::Int
    minimum_value_precision_bits::Int
    pass::Symbol
    method::String
    coordinates::Tuple
    target::BigFloat
    observation::OracleObservation
    gates::ExactSampleGates
    residual_bound::BigFloat
    correction_bound::BigFloat
    target_error_bound::BigFloat
    numerical_rank::Int
    rank_stable::Bool
    work::ExactSampleWork
end

struct ExactSampleResult
    accepted::Bool
    sample::Union{Nothing,ExactPrecisionSample}
    failure::ExactSampleFailure
    detail::String
    cached::Bool
    work::ExactSampleWork

    function ExactSampleResult(
        accepted::Bool,
        sample::Union{Nothing,ExactPrecisionSample},
        failure::ExactSampleFailure,
        detail::AbstractString,
        cached::Bool,
        work::ExactSampleWork,
    )
        accepted == (sample !== nothing) || throw(
            InvariantError(:exact_sample_status_mismatch, "exact sample status and payload disagree"),
        )
        accepted == (failure == EXACT_SAMPLE_NONE) || throw(
            InvariantError(:exact_sample_failure_mismatch, "exact sample status and failure disagree"),
        )
        accepted == isempty(detail) || throw(
            InvariantError(:exact_sample_detail_mismatch, "only failed exact samples carry detail"),
        )
        cached && (!accepted || work.oracle_work != 0) && throw(
            InvariantError(:invalid_exact_sample_cache_hit, "only zero-cost successful samples may be cached"),
        )
        return new(accepted, sample, failure, String(detail), cached, work)
    end
end

struct ExactSampleProviderSnapshot
    requests::Int
    cache_entries::Int
    evaluations::Int
    raw_oracle_work::Int
    oracle_work::Int
    oracle_work_limit::Int
    fatal_failure::ExactSampleFailure
end

"""Zero-work cooperative resource checkpoint for optional exact backends."""
struct ExactificationCheckpoint
    ready::Bool
    failure::ExactSampleFailure
    detail::String

    function ExactificationCheckpoint(
        ready::Bool,
        failure::ExactSampleFailure,
        detail::AbstractString,
    )
        ready == (failure == EXACT_SAMPLE_NONE) || throw(
            InvariantError(
                :exactification_checkpoint_status_mismatch,
                "exactification checkpoint status and failure disagree",
            ),
        )
        ready == isempty(detail) || throw(
            InvariantError(
                :exactification_checkpoint_detail_mismatch,
                "only failed exactification checkpoints carry detail",
            ),
        )
        return new(ready, failure, String(detail))
    end
end

mutable struct ExactSampleProvider{C}
    compiled::CompiledProblem
    validation::CandidateValidationResult
    start::Tuple
    deadline_ns::UInt64
    cancelled::C
    oracle_work_limit::Int
    max_iterations::Int
    requests::Int
    evaluations::Int
    raw_oracle_work::Int
    oracle_work::Int
    fatal_failure::ExactSampleFailure
    fatal_detail::String
    cache::Dict{Tuple{Int,Symbol},ExactPrecisionSample}
end

function _validate_exact_sampling_parameters(deadline_ns, remaining_oracle_work, max_iterations)
    deadline_ns isa Bool && throw(ArgumentError("deadline_ns cannot be Bool"))
    deadline_ns isa Integer || throw(ArgumentError("deadline_ns must be an integer"))
    0 <= deadline_ns <= typemax(UInt64) || throw(
        ArgumentError("deadline_ns must fit a nonnegative UInt64"),
    )
    remaining_oracle_work isa Bool && throw(
        ArgumentError("remaining_oracle_work cannot be Bool"),
    )
    remaining_oracle_work isa Integer || throw(
        ArgumentError("remaining_oracle_work must be an integer"),
    )
    0 <= remaining_oracle_work <= typemax(Int) || throw(
        ArgumentError("remaining_oracle_work must fit a nonnegative Int"),
    )
    max_iterations isa Bool && throw(ArgumentError("max_iterations cannot be Bool"))
    max_iterations isa Integer || throw(ArgumentError("max_iterations must be an integer"))
    1 <= max_iterations <= 64 || throw(ArgumentError("max_iterations must lie in 1:64"))
    return UInt64(deadline_ns), Int(remaining_oracle_work), Int(max_iterations)
end

function ExactSampleProvider(
    compiled::CompiledProblem,
    validation::CandidateValidationResult;
    deadline_ns::Integer=typemax(UInt64),
    cancelled=() -> false,
    remaining_oracle_work::Integer=typemax(Int),
    max_iterations::Integer=24,
)
    validation.accepted || throw(ArgumentError("exact sampling requires an accepted candidate"))
    validation.failure == CANDIDATE_VALIDATION_NONE || throw(
        ArgumentError("exact sampling requires a numerically confirmed candidate"),
    )
    length(validation.canonical_coordinates) == length(compiled.variables) || throw(
        ArgumentError("candidate coordinates do not match the compiled problem"),
    )
    validation.problem == first(_candidate_problem_identity(compiled)) || throw(
        ArgumentError("candidate validation belongs to a different problem"),
    )
    frozen_deadline, frozen_work, frozen_iterations = _validate_exact_sampling_parameters(
        deadline_ns,
        remaining_oracle_work,
        max_iterations,
    )
    return ExactSampleProvider(
        compiled,
        validation,
        Tuple(deepcopy(value) for value in validation.canonical_coordinates),
        frozen_deadline,
        cancelled,
        frozen_work,
        frozen_iterations,
        0,
        0,
        0,
        0,
        EXACT_SAMPLE_NONE,
        "",
        Dict{Tuple{Int,Symbol},ExactPrecisionSample}(),
    )
end

function exact_sample_provider_snapshot(provider::ExactSampleProvider)
    return ExactSampleProviderSnapshot(
        provider.requests,
        length(provider.cache),
        provider.evaluations,
        provider.raw_oracle_work,
        provider.oracle_work,
        provider.oracle_work_limit,
        provider.fatal_failure,
    )
end

"""Return immutable successful samples for backend-side certificate comparison."""
function exact_sample_provider_samples(
    provider::ExactSampleProvider;
    pass::Symbol=:reference,
)
    pass in (:compiled, :reference) || throw(
        ArgumentError("sample pass must be :compiled or :reference"),
    )
    samples = ExactPrecisionSample[
        deepcopy(sample) for ((_, kind), sample) in provider.cache if kind == pass
    ]
    sort!(samples; by=sample -> sample.precision_bits)
    return Tuple(samples)
end

"""
Poll cancellation and deadline state without requesting a numerical sample.

The first resource failure is irreversible for the provider. Backends should
call this at bounded intervals around recognition, CAS, replay, and artifact
work; Core performs a final checkpoint before accepting any answer.
"""
function exactification_checkpoint(provider::ExactSampleProvider)
    if provider.fatal_failure != EXACT_SAMPLE_NONE
        return ExactificationCheckpoint(
            false,
            provider.fatal_failure,
            provider.fatal_detail,
        )
    end
    failure, detail = _exact_provider_resource_failure(provider)
    return failure == EXACT_SAMPLE_NONE ?
           ExactificationCheckpoint(true, EXACT_SAMPLE_NONE, "") :
           ExactificationCheckpoint(false, failure, detail)
end

_empty_exact_sample_work() = ExactSampleWork(0, 0, 0)

function _exact_sample_failure(failure::ExactSampleFailure, detail; work=_empty_exact_sample_work())
    return ExactSampleResult(false, nothing, failure, String(detail), false, work)
end

function _set_exact_sample_fatal!(provider, failure, detail)
    provider.fatal_failure == EXACT_SAMPLE_NONE || return
    provider.fatal_failure = failure
    provider.fatal_detail = String(detail)
end

function _exact_provider_resource_failure(provider::ExactSampleProvider)
    cancelled = try
        provider.cancelled()
    catch error
        error isa InterruptException && rethrow()
        detail = "cancellation callback failed: $(sprint(showerror, error))"
        _set_exact_sample_fatal!(provider, EXACT_SAMPLE_INTERNAL_ERROR, detail)
        return EXACT_SAMPLE_INTERNAL_ERROR, detail
    end
    cancelled isa Bool || begin
        detail = "cancellation callback must return Bool"
        _set_exact_sample_fatal!(provider, EXACT_SAMPLE_INTERNAL_ERROR, detail)
        return EXACT_SAMPLE_INTERNAL_ERROR, detail
    end
    if cancelled
        detail = "exact sampling was cancelled"
        _set_exact_sample_fatal!(provider, EXACT_SAMPLE_CANCELLED, detail)
        return EXACT_SAMPLE_CANCELLED, detail
    end
    if time_ns() >= provider.deadline_ns
        detail = "exact sampling reached its deadline"
        _set_exact_sample_fatal!(provider, EXACT_SAMPLE_DEADLINE_REACHED, detail)
        return EXACT_SAMPLE_DEADLINE_REACHED, detail
    end
    return EXACT_SAMPLE_NONE, ""
end

function _exact_sample_gates(bits::Int)
    accuracy_bits = bits - 96
    residual_accuracy_bits = bits - 64
    return setprecision(BigFloat, bits) do
        ExactSampleGates(
            bits,
            accuracy_bits,
            residual_accuracy_bits,
            ldexp(one(BigFloat), -residual_accuracy_bits),
            ldexp(one(BigFloat), -accuracy_bits),
            ldexp(one(BigFloat), -accuracy_bits),
        )
    end
end

function _checked_exact_sample_product(left::Int, right::Int)
    try
        return Base.checked_mul(left, right)
    catch error
        error isa OverflowError || rethrow()
        return nothing
    end
end

function _checked_exact_sample_add(left::Int, right::Int)
    try
        return Base.checked_add(left, right)
    catch error
        error isa OverflowError || rethrow()
        return nothing
    end
end

function _record_exact_sample_work!(provider::ExactSampleProvider, snapshot)
    snapshot.precision_bits >= 512 || return nothing
    snapshot.weight == cld(snapshot.precision_bits, 53) || return nothing
    snapshot.evaluations >= 0 || return nothing
    snapshot.raw_oracle_work >= 0 || return nothing
    computed = _checked_exact_sample_product(snapshot.weight, snapshot.raw_oracle_work)
    computed === nothing && return nothing
    snapshot.oracle_work == computed || return nothing
    remaining = provider.oracle_work_limit - provider.oracle_work
    computed <= remaining || return nothing
    evaluations = _checked_exact_sample_add(provider.evaluations, snapshot.evaluations)
    raw = _checked_exact_sample_add(provider.raw_oracle_work, snapshot.raw_oracle_work)
    official = _checked_exact_sample_add(provider.oracle_work, computed)
    any(isnothing, (evaluations, raw, official)) && return nothing
    provider.evaluations = evaluations::Int
    provider.raw_oracle_work = raw::Int
    provider.oracle_work = official::Int
    return ExactSampleWork(snapshot.evaluations, snapshot.raw_oracle_work, computed)
end

function _minimum_exact_value_precision(sample_coordinates, target)
    values = Int[precision(target)]
    append!(values, precision(value) for value in sample_coordinates if value isa AbstractFloat)
    return minimum(values)
end

function _exact_sample_metadata_ok(compiled, refinement, bits, pass, gates)
    evidence = refinement.evidence
    evidence.precision_bits == bits || return false
    evidence.work.precision_bits == bits || return false
    expected_method = pass == :compiled ?
                      "compiled_c2_rank_general_lm_5point_v1" :
                      "reference_c2_rank_general_lm_5point_v1"
    evidence.method == expected_method || return false
    _high_precision_observation_precision_ok(compiled, evidence.observation, bits) || return false
    all(value -> !(value isa AbstractFloat) || precision(value) >= bits, evidence.coordinates) ||
        return false
    evidence.residual_bound <= gates.residual_goal || return false
    evidence.correction_bound <= gates.correction_tolerance || return false
    evidence.target_error_bound <= gates.target_tolerance || return false
    return true
end

function _map_high_precision_sample_failure(failure::HighPrecisionRefinementFailure)
    failure == HIGH_PRECISION_REFINEMENT_CANCELLED && return EXACT_SAMPLE_CANCELLED
    failure == HIGH_PRECISION_REFINEMENT_DEADLINE_REACHED && return EXACT_SAMPLE_DEADLINE_REACHED
    failure == HIGH_PRECISION_REFINEMENT_ORACLE_BUDGET_EXHAUSTED &&
        return EXACT_SAMPLE_ORACLE_BUDGET_EXHAUSTED
    failure == HIGH_PRECISION_REFINEMENT_PRECISION_DOWNGRADE &&
        return EXACT_SAMPLE_PRECISION_DOWNGRADE
    return EXACT_SAMPLE_REFINEMENT_FAILED
end

"""
Return a compiled or independent-reference sample at `precision_bits`.

Every cache miss starts from the accepted validation's canonical coordinates;
samples at different precisions never seed each other. Only successful samples
are cached. Deadline, cancellation and weighted oracle work remain Core-owned.
"""
function exact_sample(
    provider::ExactSampleProvider,
    precision_bits;
    pass=:reference,
)
    provider.requests = something(_checked_exact_sample_add(provider.requests, 1), typemax(Int))
    provider.fatal_failure == EXACT_SAMPLE_NONE || return _exact_sample_failure(
        provider.fatal_failure,
        provider.fatal_detail,
    )
    precision_bits isa Bool && return _exact_sample_failure(
        EXACT_SAMPLE_INVALID_REQUEST,
        "precision_bits cannot be Bool",
    )
    precision_bits isa Integer || return _exact_sample_failure(
        EXACT_SAMPLE_INVALID_REQUEST,
        "precision_bits must be an integer",
    )
    512 <= precision_bits <= _MAX_EXACT_SAMPLE_PRECISION_BITS || return _exact_sample_failure(
        EXACT_SAMPLE_INVALID_REQUEST,
        "precision_bits must lie in 512:$(_MAX_EXACT_SAMPLE_PRECISION_BITS)",
    )
    pass in (:compiled, :reference) || return _exact_sample_failure(
        EXACT_SAMPLE_INVALID_REQUEST,
        "pass must be :compiled or :reference",
    )
    bits = Int(precision_bits)
    kind = Symbol(pass)
    resource_failure, resource_detail = _exact_provider_resource_failure(provider)
    resource_failure == EXACT_SAMPLE_NONE || return _exact_sample_failure(
        resource_failure,
        resource_detail,
    )
    key = (bits, kind)
    if haskey(provider.cache, key)
        return ExactSampleResult(
            true,
            deepcopy(provider.cache[key]),
            EXACT_SAMPLE_NONE,
            "",
            true,
            _empty_exact_sample_work(),
        )
    end
    remaining = provider.oracle_work_limit - provider.oracle_work
    minimum_work = _checked_exact_sample_product(
        cld(bits, 53),
        provider.compiled.logical_evaluation_cost,
    )
    if minimum_work === nothing || minimum_work > remaining
        detail = "exact sampling has insufficient work for one high-precision evaluation"
        _set_exact_sample_fatal!(
            provider,
            EXACT_SAMPLE_ORACLE_BUDGET_EXHAUSTED,
            detail,
        )
        return _exact_sample_failure(
            EXACT_SAMPLE_ORACLE_BUDGET_EXHAUSTED,
            detail,
        )
    end
    gates = _exact_sample_gates(bits)
    refinement = try
        _run_high_precision_refinement(
            provider.compiled,
            collect(provider.start);
            precision_bits=bits,
            evaluator_kind=kind,
            residual_goal=gates.residual_goal,
            configuration_tolerance=gates.correction_tolerance,
            target_tolerance=gates.target_tolerance,
            deadline_ns=provider.deadline_ns,
            cancelled=provider.cancelled,
            remaining_oracle_work=remaining,
            max_iterations=provider.max_iterations,
            allow_rank_deficient=true,
        )
    catch error
        error isa InterruptException && rethrow()
        detail = "high-precision sample refinement failed internally: $(sprint(showerror, error))"
        _set_exact_sample_fatal!(provider, EXACT_SAMPLE_INTERNAL_ERROR, detail)
        return _exact_sample_failure(EXACT_SAMPLE_INTERNAL_ERROR, detail)
    end
    work = _record_exact_sample_work!(provider, refinement.evidence.work)
    if work === nothing
        detail = "high-precision work metadata overflowed or violated the Core budget"
        _set_exact_sample_fatal!(provider, EXACT_SAMPLE_INTERNAL_ERROR, detail)
        return _exact_sample_failure(EXACT_SAMPLE_INTERNAL_ERROR, detail)
    end
    if !refinement.accepted
        failure = _map_high_precision_sample_failure(refinement.failure)
        failure in (
            EXACT_SAMPLE_CANCELLED,
            EXACT_SAMPLE_DEADLINE_REACHED,
            EXACT_SAMPLE_ORACLE_BUDGET_EXHAUSTED,
            EXACT_SAMPLE_PRECISION_DOWNGRADE,
        ) && _set_exact_sample_fatal!(
            provider,
            failure,
            something(refinement.diagnostic, "high-precision sampling failed"),
        )
        return _exact_sample_failure(
            failure,
            something(refinement.diagnostic, "high-precision sampling failed"),
            work=work,
        )
    end
    _branch_keys_match(
        provider.validation.canonical_observation,
        refinement.evidence.observation,
    ) || begin
        detail = "arbitrary-precision sample changed the validated branch signature"
        _set_exact_sample_fatal!(provider, EXACT_SAMPLE_BRANCH_MISMATCH, detail)
        return _exact_sample_failure(EXACT_SAMPLE_BRANCH_MISMATCH, detail, work=work)
    end
    _exact_sample_metadata_ok(provider.compiled, refinement, bits, kind, gates) || begin
        detail = "arbitrary-precision sample failed precision or adaptive gate metadata checks"
        _set_exact_sample_fatal!(provider, EXACT_SAMPLE_GATE_FAILED, detail)
        return _exact_sample_failure(EXACT_SAMPLE_GATE_FAILED, detail, work=work)
    end
    evidence = refinement.evidence
    target = setprecision(BigFloat, bits) do
        BigFloat(evidence.observation.target)
    end
    minimum_precision = _minimum_exact_value_precision(evidence.coordinates, target)
    minimum_precision >= bits || begin
        detail = "arbitrary-precision sample values were silently downcast"
        _set_exact_sample_fatal!(provider, EXACT_SAMPLE_PRECISION_DOWNGRADE, detail)
        return _exact_sample_failure(EXACT_SAMPLE_PRECISION_DOWNGRADE, detail, work=work)
    end
    sample = ExactPrecisionSample(
        bits,
        minimum_precision,
        kind,
        evidence.method,
        Tuple(deepcopy(value) for value in evidence.coordinates),
        target,
        deepcopy(evidence.observation),
        deepcopy(gates),
        deepcopy(evidence.residual_bound),
        deepcopy(evidence.correction_bound),
        deepcopy(evidence.target_error_bound),
        evidence.numerical_rank,
        evidence.rank_stable,
        work,
    )
    provider.cache[key] = deepcopy(sample)
    return ExactSampleResult(true, sample, EXACT_SAMPLE_NONE, "", false, work)
end

@enum ExactificationFailure::UInt8 begin
    EXACTIFICATION_NONE = 0
    EXACTIFICATION_UNSUPPORTED = 1
    EXACTIFICATION_INVALID_CANDIDATE = 2
    EXACTIFICATION_CAPABILITY_MISSING = 3
    EXACTIFICATION_RECOGNITION_FAILED = 4
    EXACTIFICATION_REPLAY_FAILED = 5
    EXACTIFICATION_CERTIFICATE_FAILED = 6
    EXACTIFICATION_CANCELLED = 7
    EXACTIFICATION_DEADLINE_REACHED = 8
    EXACTIFICATION_ORACLE_BUDGET_EXHAUSTED = 9
    EXACTIFICATION_SAMPLE_FAILED = 10
    EXACTIFICATION_BACKEND_PROTOCOL_FAILED = 11
    EXACTIFICATION_BACKEND_ERROR = 12
    EXACTIFICATION_VERIFICATION_FAILED = 13
end

"""Untrusted typed outcome returned by an optional backend extension."""
struct ExactBackendOutcome
    answer::Union{Nothing,ExactAnswer}
    failure::ExactificationFailure
    detail::String
    reported_oracle_work::Int

    function ExactBackendOutcome(
        answer::Union{Nothing,ExactAnswer},
        failure::ExactificationFailure,
        detail::AbstractString;
        reported_oracle_work::Integer=0,
    )
        reported_oracle_work isa Bool && throw(ArgumentError("reported work cannot be Bool"))
        0 <= reported_oracle_work <= typemax(Int) || throw(
            ArgumentError("reported work must fit a nonnegative Int"),
        )
        (answer !== nothing) == (failure == EXACTIFICATION_NONE) || throw(
            InvariantError(:exact_backend_outcome_mismatch, "backend answer and failure disagree"),
        )
        (answer !== nothing) == isempty(detail) || throw(
            InvariantError(:exact_backend_detail_mismatch, "only failed backend outcomes carry detail"),
        )
        return new(answer, failure, String(detail), Int(reported_oracle_work))
    end
end

struct ExactificationResult
    accepted::Bool
    answer::Union{Nothing,ExactAnswer}
    failure::ExactificationFailure
    detail::String
    backend::Union{Nothing,ExactBackendDescriptor}
    oracle_work::Int
    backend_reported_oracle_work::Int
    samples::ExactSampleProviderSnapshot

    function ExactificationResult(
        accepted::Bool,
        answer::Union{Nothing,ExactAnswer},
        failure::ExactificationFailure,
        detail::AbstractString,
        backend::Union{Nothing,ExactBackendDescriptor},
        oracle_work::Int,
        backend_reported_oracle_work::Int,
        samples::ExactSampleProviderSnapshot,
    )
        accepted == (answer !== nothing) || throw(
            InvariantError(:exactification_answer_mismatch, "exactification status and answer disagree"),
        )
        accepted == (failure == EXACTIFICATION_NONE) || throw(
            InvariantError(:exactification_failure_mismatch, "exactification status and failure disagree"),
        )
        accepted == isempty(detail) || throw(
            InvariantError(:exactification_detail_mismatch, "only failed exactification carries detail"),
        )
        oracle_work >= 0 || throw(
            InvariantError(:negative_exactification_work, "exactification work cannot be negative"),
        )
        backend_reported_oracle_work >= 0 || throw(
            InvariantError(:negative_backend_reported_work, "reported work cannot be negative"),
        )
        oracle_work == samples.oracle_work || throw(
            InvariantError(:exactification_work_mismatch, "official work must equal the Core provider ledger"),
        )
        return new(
            accepted,
            answer,
            failure,
            String(detail),
            backend,
            oracle_work,
            backend_reported_oracle_work,
            samples,
        )
    end
end

function _exactification_result(
    answer,
    failure,
    detail,
    backend,
    provider::ExactSampleProvider;
    backend_reported_oracle_work=0,
)
    snapshot = exact_sample_provider_snapshot(provider)
    return ExactificationResult(
        answer !== nothing,
        answer,
        failure,
        String(detail),
        backend,
        snapshot.oracle_work,
        Int(backend_reported_oracle_work),
        snapshot,
    )
end

function _exactification_result(
    answer,
    failure,
    detail,
    backend,
    snapshot::ExactSampleProviderSnapshot;
    backend_reported_oracle_work=0,
)
    return ExactificationResult(
        answer !== nothing,
        answer,
        failure,
        String(detail),
        backend,
        snapshot.oracle_work,
        Int(backend_reported_oracle_work),
        snapshot,
    )
end

function _empty_exact_sample_snapshot(oracle_work_limit::Int)
    return ExactSampleProviderSnapshot(0, 0, 0, 0, 0, oracle_work_limit, EXACT_SAMPLE_NONE)
end

function _exactification_candidate_issue(
    compiled::CompiledProblem,
    validation::CandidateValidationResult,
)
    validation.accepted || return "exactification requires an accepted candidate validation"
    validation.failure == CANDIDATE_VALIDATION_NONE ||
        return "exactification requires a numerically confirmed candidate"
    length(validation.canonical_coordinates) == length(compiled.variables) ||
        return "candidate coordinates do not match the compiled problem"
    expected_problem = first(_candidate_problem_identity(compiled))
    validation.problem == expected_problem ||
        return "candidate validation belongs to a different problem"
    return nothing
end

"""Extension point: concrete backends must return their stable descriptor."""
function exact_backend_descriptor(backend::AbstractExactBackend)
    throw(MethodError(exact_backend_descriptor, (backend,)))
end

"""
Extension point implemented by optional exact backends.

All numerical sampling must go through `provider`. The reported work in the
returned outcome is untrusted and never participates in Core accounting.
"""
function exactify_candidate(
    ::AbstractExactBackend,
    ::CompiledProblem,
    ::CandidateValidationResult,
    ::ExactSampleProvider,
)
    return ExactBackendOutcome(
        nothing,
        EXACTIFICATION_UNSUPPORTED,
        "the exact backend does not implement candidate exactification",
    )
end

"""
Mandatory independent verifier hook for optional exactification backends.

Core never accepts a backend-produced `ExactAnswer` from backend self-checking
alone. Concrete backends must reconstruct their artifacts and replay the
original graph here; the default is a typed rejection.
"""
function verify_exactified_answer(
    ::AbstractExactBackend,
    ::CompiledProblem,
    ::ExactAnswer,
    ::ExactSampleProvider,
)
    return ExactVerificationResult(
        false,
        EXACT_VERIFICATION_UNSUPPORTED_SCHEME,
        "the exact backend does not implement independent answer verification",
    )
end

function _canonical_exact_branches(signature)
    all(branch -> branch isa BranchDecision, signature) || return nothing
    branches = BranchDecision[
        BranchDecision(branch.choice_node, branch.key) for branch in signature
    ]
    allunique(branch.choice_node for branch in branches) || return nothing
    sort!(branches; by=branch -> string(branch.choice_node))
    return Tuple(branches)
end

function _exact_answer_contract_issue(
    descriptor::ExactBackendDescriptor,
    validation::CandidateValidationResult,
    answer::ExactAnswer,
)
    answer.configuration_certificate.artifact.scheme in
        descriptor.configuration_certificate_schemes || return (
        "configuration certificate scheme is not declared by the exact backend"
    )
    answer.target_certificate.artifact.scheme in descriptor.target_certificate_schemes ||
        return "target certificate scheme is not declared by the exact backend"
    answer.configuration_certificate.problem == validation.problem || return (
        "configuration certificate belongs to a different problem"
    )
    answer.target_certificate.problem == validation.problem || return (
        "target certificate belongs to a different problem"
    )
    answer.target_certificate.identity == GeoTargetBase._identity_hash(answer.identity) ||
        return "target certificate identity hash differs from the exact answer"
    expected = _canonical_exact_branches(
        Tuple(branch.decision for branch in validation.canonical_observation.branches),
    )
    observed = _canonical_exact_branches(answer.branch_signature)
    expected !== nothing && observed !== nothing && expected == observed || return (
        "exact answer branch signature differs from numerical confirmation"
    )
    return nothing
end

function _exact_reference_evidence_issue(provider::ExactSampleProvider)
    reference = exact_sample_provider_samples(provider; pass=:reference)
    bits = unique(sample.precision_bits for sample in reference)
    length(bits) >= 2 || return (
        "exactification requires two independent reference samples at distinct precisions"
    )
    first(bits) >= 512 || return "reference evidence is below 512 bits"
    last(bits) >= 768 || return "reference evidence never reaches 768 bits"
    last(bits) - first(bits) >= 256 || return (
        "reference evidence precisions must differ by at least 256 bits"
    )
    all(sample -> sample.rank_stable, reference) || return (
        "reference sample rank is not stable"
    )
    length(unique(sample.numerical_rank for sample in reference)) == 1 || return (
        "reference sample numerical rank changes across precisions"
    )
    return nothing
end

function _exactification_resource_failure(failure::ExactSampleFailure)
    failure == EXACT_SAMPLE_CANCELLED && return EXACTIFICATION_CANCELLED
    failure == EXACT_SAMPLE_DEADLINE_REACHED && return EXACTIFICATION_DEADLINE_REACHED
    failure == EXACT_SAMPLE_ORACLE_BUDGET_EXHAUSTED &&
        return EXACTIFICATION_ORACLE_BUDGET_EXHAUSTED
    return EXACTIFICATION_SAMPLE_FAILED
end

"""Run one optional backend without connecting it to the production solver."""
function run_exactification(
    backend::AbstractExactBackend,
    compiled::CompiledProblem,
    validation::CandidateValidationResult;
    deadline_ns::Integer=typemax(UInt64),
    cancelled=() -> false,
    remaining_oracle_work::Integer=typemax(Int),
    max_iterations::Integer=24,
)
    frozen_deadline, frozen_work, frozen_iterations = _validate_exact_sampling_parameters(
        deadline_ns,
        remaining_oracle_work,
        max_iterations,
    )
    empty_snapshot = _empty_exact_sample_snapshot(frozen_work)
    descriptor = try
        exact_backend_descriptor(backend)
    catch error
        error isa InterruptException && rethrow()
        return _exactification_result(
            nothing,
            EXACTIFICATION_BACKEND_PROTOCOL_FAILED,
            "exact backend descriptor failed: $(sprint(showerror, error))",
            nothing,
            empty_snapshot,
        )
    end
    descriptor isa ExactBackendDescriptor || return _exactification_result(
        nothing,
        EXACTIFICATION_BACKEND_PROTOCOL_FAILED,
        "exact backend descriptor returned the wrong type",
        nothing,
        empty_snapshot,
    )
    candidate_issue = _exactification_candidate_issue(compiled, validation)
    candidate_issue === nothing || return _exactification_result(
        nothing,
        EXACTIFICATION_INVALID_CANDIDATE,
        candidate_issue,
        descriptor,
        empty_snapshot,
    )
    provider = ExactSampleProvider(
        compiled,
        validation;
        deadline_ns=frozen_deadline,
        cancelled,
        remaining_oracle_work=frozen_work,
        max_iterations=frozen_iterations,
    )
    resource_failure, resource_detail = _exact_provider_resource_failure(provider)
    resource_failure == EXACT_SAMPLE_NONE || return _exactification_result(
        nothing,
        _exactification_resource_failure(resource_failure),
        resource_detail,
        descriptor,
        provider,
    )
    outcome = try
        exactify_candidate(backend, compiled, validation, provider)
    catch error
        error isa InterruptException && rethrow()
        checkpoint = exactification_checkpoint(provider)
        checkpoint.ready || return _exactification_result(
            nothing,
            _exactification_resource_failure(checkpoint.failure),
            checkpoint.detail,
            descriptor,
            provider,
        )
        return _exactification_result(
            nothing,
            EXACTIFICATION_BACKEND_ERROR,
            "exact backend raised an exception: $(sprint(showerror, error))",
            descriptor,
            provider,
        )
    end
    checkpoint = exactification_checkpoint(provider)
    checkpoint.ready || return _exactification_result(
        nothing,
        _exactification_resource_failure(checkpoint.failure),
        checkpoint.detail,
        descriptor,
        provider,
        backend_reported_oracle_work=outcome isa ExactBackendOutcome ?
                                     outcome.reported_oracle_work : 0,
    )
    outcome isa ExactBackendOutcome || return _exactification_result(
        nothing,
        EXACTIFICATION_BACKEND_PROTOCOL_FAILED,
        "exact backend returned the wrong outcome type",
        descriptor,
        provider,
    )
    resource_failure, resource_detail = _exact_provider_resource_failure(provider)
    if resource_failure != EXACT_SAMPLE_NONE
        return _exactification_result(
            nothing,
            _exactification_resource_failure(resource_failure),
            resource_detail,
            descriptor,
            provider,
            backend_reported_oracle_work=outcome.reported_oracle_work,
        )
    end
    if provider.fatal_failure in (
        EXACT_SAMPLE_CANCELLED,
        EXACT_SAMPLE_DEADLINE_REACHED,
        EXACT_SAMPLE_ORACLE_BUDGET_EXHAUSTED,
        EXACT_SAMPLE_INTERNAL_ERROR,
    )
        return _exactification_result(
            nothing,
            _exactification_resource_failure(provider.fatal_failure),
            provider.fatal_detail,
            descriptor,
            provider,
            backend_reported_oracle_work=outcome.reported_oracle_work,
        )
    end
    if outcome.answer !== nothing && provider.fatal_failure != EXACT_SAMPLE_NONE
        return _exactification_result(
            nothing,
            _exactification_resource_failure(provider.fatal_failure),
            provider.fatal_detail,
            descriptor,
            provider,
            backend_reported_oracle_work=outcome.reported_oracle_work,
        )
    end
    if outcome.answer !== nothing
        answer = outcome.answer::ExactAnswer
        contract_issue = _exact_answer_contract_issue(descriptor, validation, answer)
        contract_issue === nothing || return _exactification_result(
            nothing,
            EXACTIFICATION_VERIFICATION_FAILED,
            contract_issue,
            descriptor,
            provider,
            backend_reported_oracle_work=outcome.reported_oracle_work,
        )
        evidence_issue = _exact_reference_evidence_issue(provider)
        evidence_issue === nothing || return _exactification_result(
            nothing,
            EXACTIFICATION_VERIFICATION_FAILED,
            evidence_issue,
            descriptor,
            provider,
            backend_reported_oracle_work=outcome.reported_oracle_work,
        )
        checkpoint = exactification_checkpoint(provider)
        checkpoint.ready || return _exactification_result(
            nothing,
            _exactification_resource_failure(checkpoint.failure),
            checkpoint.detail,
            descriptor,
            provider,
            backend_reported_oracle_work=outcome.reported_oracle_work,
        )
        verification = try
            verify_exactified_answer(backend, compiled, answer, provider)
        catch error
            error isa InterruptException && rethrow()
            checkpoint = exactification_checkpoint(provider)
            checkpoint.ready || return _exactification_result(
                nothing,
                _exactification_resource_failure(checkpoint.failure),
                checkpoint.detail,
                descriptor,
                provider,
                backend_reported_oracle_work=outcome.reported_oracle_work,
            )
            return _exactification_result(
                nothing,
                EXACTIFICATION_BACKEND_ERROR,
                "exact backend verifier raised an exception: $(sprint(showerror, error))",
                descriptor,
                provider,
                backend_reported_oracle_work=outcome.reported_oracle_work,
            )
        end
        checkpoint = exactification_checkpoint(provider)
        checkpoint.ready || return _exactification_result(
            nothing,
            _exactification_resource_failure(checkpoint.failure),
            checkpoint.detail,
            descriptor,
            provider,
            backend_reported_oracle_work=outcome.reported_oracle_work,
        )
        verification isa ExactVerificationResult || return _exactification_result(
            nothing,
            EXACTIFICATION_BACKEND_PROTOCOL_FAILED,
            "exact backend verifier returned the wrong result type",
            descriptor,
            provider,
            backend_reported_oracle_work=outcome.reported_oracle_work,
        )
        checkpoint = exactification_checkpoint(provider)
        checkpoint.ready || return _exactification_result(
            nothing,
            _exactification_resource_failure(checkpoint.failure),
            checkpoint.detail,
            descriptor,
            provider,
            backend_reported_oracle_work=outcome.reported_oracle_work,
        )
        verification.accepted || return _exactification_result(
            nothing,
            EXACTIFICATION_VERIFICATION_FAILED,
            "independent exact verification failed: $(verification.failure): $(verification.detail)",
            descriptor,
            provider,
            backend_reported_oracle_work=outcome.reported_oracle_work,
        )
    end
    return _exactification_result(
        outcome.answer,
        outcome.failure,
        outcome.detail,
        descriptor,
        provider,
        backend_reported_oracle_work=outcome.reported_oracle_work,
    )
end
