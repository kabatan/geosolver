abstract type AbstractAnswer end

"""Canonical immutable decimal representation of an arbitrary-size integer."""
struct ExactInteger
    decimal::String

    function ExactInteger(value::AbstractString)
        canonical = String(value)
        occursin(r"^(0|-?[1-9][0-9]*)$", canonical) || throw(
            InvariantError(
                :invalid_exact_integer,
                "exact integers must use canonical signed base-10 notation",
            ),
        )
        return new(canonical)
    end
end

ExactInteger(value::Integer) = ExactInteger(string(value))
Base.string(value::ExactInteger) = value.decimal
Base.show(io::IO, value::ExactInteger) = print(io, "ExactInteger(\"", value.decimal, "\")")
_bigint(value::ExactInteger) = parse(BigInt, value.decimal)

"""A reduced rational with a positive denominator."""
struct ExactRational
    numerator::ExactInteger
    denominator::ExactInteger

    function ExactRational(numerator, denominator = 1)
        raw_numerator = _bigint(_exact_integer(numerator))
        raw_denominator = _bigint(_exact_integer(denominator))
        iszero(raw_denominator) && throw(
            InvariantError(:zero_denominator, "an exact rational denominator cannot be zero"),
        )
        if raw_denominator < 0
            raw_numerator = -raw_numerator
            raw_denominator = -raw_denominator
        end
        divisor = gcd(abs(raw_numerator), raw_denominator)
        return new(
            ExactInteger(div(raw_numerator, divisor)),
            ExactInteger(div(raw_denominator, divisor)),
        )
    end
end

_exact_integer(value::ExactInteger) = value
_exact_integer(value::Integer) = ExactInteger(value)
_exact_integer(value::AbstractString) = ExactInteger(value)

Base.:(==)(left::ExactRational, right::ExactRational) =
    left.numerator == right.numerator && left.denominator == right.denominator
Base.isless(left::ExactRational, right::ExactRational) =
    _bigint(left.numerator) * _bigint(right.denominator) <
    _bigint(right.numerator) * _bigint(left.denominator)

function Base.show(io::IO, value::ExactRational)
    print(io, "ExactRational(", value.numerator.decimal, ", ", value.denominator.decimal, ")")
end

struct RationalInterval
    lower::ExactRational
    upper::ExactRational

    function RationalInterval(lower::ExactRational, upper::ExactRational)
        isless(lower, upper) || throw(
            InvariantError(:invalid_rational_interval, "an isolating interval must have lower < upper"),
        )
        return new(lower, upper)
    end
end

RationalInterval(lower, upper) = RationalInterval(_exact_rational(lower), _exact_rational(upper))
_exact_rational(value::ExactRational) = value
_exact_rational(value::Integer) = ExactRational(value)
_exact_rational(value::Rational) = ExactRational(numerator(value), denominator(value))
_exact_rational(value::Tuple{Any,Any}) = ExactRational(value[1], value[2])

"""Closed numerical target enclosure used only by validated provisional answers."""
struct NumericEnclosure{T<:Real}
    lower::T
    upper::T

    function NumericEnclosure(lower::T, upper::T) where {T<:Real}
        _is_finite(lower) && _is_finite(upper) || throw(
            InvariantError(:nonfinite_enclosure, "a numerical enclosure must be finite"),
        )
        lower <= upper || throw(
            InvariantError(:invalid_numeric_enclosure, "a numerical enclosure requires lower <= upper"),
        )
        return new{T}(deepcopy(lower), deepcopy(upper))
    end
end

"""
Claimed primitive square-free polynomial and isolated real root identity.

Coefficients are stored in ascending power order. The constructor verifies
canonical primitive form and square-freeness; minimality and root isolation are
established by the separate TargetIdentityCertificate.
"""
struct AlgebraicTargetIdentity{C<:Tuple}
    coefficients::C
    isolating_interval::RationalInterval
    real_root_index::Int

    function AlgebraicTargetIdentity(coefficients, interval::RationalInterval, real_root_index::Integer)
        frozen = tuple((_exact_integer(coefficient) for coefficient in coefficients)...)
        length(frozen) >= 2 || throw(
            InvariantError(:constant_target_polynomial, "an algebraic identity polynomial must have positive degree"),
        )
        raw = BigInt[_bigint(coefficient) for coefficient in frozen]
        iszero(last(raw)) && throw(
            InvariantError(:noncanonical_polynomial, "the leading coefficient cannot be zero"),
        )
        last(raw) > 0 || throw(
            InvariantError(:noncanonical_polynomial, "the leading coefficient must be positive"),
        )
        foldl(gcd, abs.(raw)) == 1 || throw(
            InvariantError(:nonprimitive_polynomial, "minimal-polynomial coefficients must be primitive"),
        )
        _is_square_free(raw) || throw(
            InvariantError(:nonsquarefree_polynomial, "target polynomial must be square-free"),
        )
        real_root_index >= 1 || throw(
            InvariantError(:invalid_root_index, "real-root index is one-based and must be positive"),
        )
        _evaluate_polynomial(raw, interval.lower) != 0 || throw(
            InvariantError(:root_on_interval_boundary, "lower isolating endpoint is a polynomial root"),
        )
        _evaluate_polynomial(raw, interval.upper) != 0 || throw(
            InvariantError(:root_on_interval_boundary, "upper isolating endpoint is a polynomial root"),
        )
        return new{typeof(frozen)}(frozen, interval, Int(real_root_index))
    end
end

function _evaluate_polynomial(coefficients::Vector{BigInt}, value::ExactRational)
    x = _bigint(value.numerator) // _bigint(value.denominator)
    result = zero(x)
    for coefficient in Iterators.reverse(coefficients)
        result = result * x + coefficient
    end
    return result
end

function _trim_polynomial!(polynomial)
    while !isempty(polynomial) && iszero(last(polynomial))
        pop!(polynomial)
    end
    return polynomial
end

function _polynomial_remainder(dividend, divisor)
    remainder = copy(dividend)
    _trim_polynomial!(remainder)
    denominator_degree = length(divisor) - 1
    while !isempty(remainder) && length(remainder) >= length(divisor)
        offset = length(remainder) - length(divisor)
        factor = last(remainder) / last(divisor)
        for index in eachindex(divisor)
            remainder[index + offset] -= factor * divisor[index]
        end
        _trim_polynomial!(remainder)
    end
    return remainder
end

function _is_square_free(coefficients::Vector{BigInt})
    polynomial = Rational{BigInt}.(coefficients)
    derivative = Rational{BigInt}[
        (index - 1) * polynomial[index] for index in 2:length(polynomial)
    ]
    _trim_polynomial!(polynomial)
    _trim_polynomial!(derivative)
    while !isempty(derivative)
        polynomial, derivative = derivative, _polynomial_remainder(polynomial, derivative)
    end
    return length(polynomial) == 1
end

function _identity_hash(identity::AlgebraicTargetIdentity)
    polynomial = join((coefficient.decimal for coefficient in identity.coefficients), ",")
    interval = identity.isolating_interval
    text = join(
        (
            polynomial,
            string(interval.lower.numerator),
            string(interval.lower.denominator),
            string(interval.upper.numerator),
            string(interval.upper.denominator),
            string(identity.real_root_index),
        ),
        "|",
    )
    return content_hash(text)
end

"""Replayable immutable certificate payload with an intrinsic digest."""
struct CertificateArtifact{P<:Tuple}
    scheme::String
    media_type::String
    payload::P
    digest::ContentHash

    function CertificateArtifact(
        scheme::AbstractString,
        payload::AbstractVector{UInt8};
        media_type::AbstractString = "application/octet-stream",
    )
        canonical_scheme = _canonical_name(scheme, "certificate scheme")
        canonical_media_type = String(media_type)
        isempty(strip(canonical_media_type)) && throw(
            InvariantError(:invalid_media_type, "certificate media type cannot be empty"),
        )
        isempty(payload) && throw(
            InvariantError(:empty_certificate, "a replayable certificate payload cannot be empty"),
        )
        frozen_payload = Tuple(payload)
        return new{typeof(frozen_payload)}(
            canonical_scheme,
            canonical_media_type,
            frozen_payload,
            content_hash(collect(frozen_payload)),
        )
    end
end

CertificateArtifact(scheme::AbstractString, payload::AbstractString; kwargs...) =
    CertificateArtifact(scheme, Vector{UInt8}(codeunits(payload)); kwargs...)

"""Proof that one configuration satisfies canonical relation/domain/guard/branch semantics."""
struct ConfigurationValidityCertificate{A<:CertificateArtifact}
    problem::ContentHash
    configuration::ContentHash
    artifact::A
end

"""Proof binding an algebraic identity to the final target value."""
struct TargetIdentityCertificate{A<:CertificateArtifact}
    problem::ContentHash
    identity::ContentHash
    artifact::A
end

TargetIdentityCertificate(
    problem::ContentHash,
    identity::AlgebraicTargetIdentity,
    artifact::CertificateArtifact,
) = TargetIdentityCertificate(problem, _identity_hash(identity), artifact)

"""Independent high-precision or validated replay evidence for a provisional answer."""
struct NumericalValidationEvidence{A<:CertificateArtifact}
    problem::ContentHash
    configuration::ContentHash
    method::String
    precision_bits::Int
    artifact::A

    function NumericalValidationEvidence(
        problem::ContentHash,
        configuration::ContentHash,
        method::AbstractString,
        precision_bits::Integer,
        artifact::CertificateArtifact;
        independent::Bool,
    )
        independent || throw(
            InvariantError(
                :nonindependent_validation,
                "provisional answers require an independent validation pass",
            ),
        )
        precision_bits >= 53 || throw(
            InvariantError(:insufficient_precision, "validation precision must be at least 53 bits"),
        )
        return new{typeof(artifact)}(
            problem,
            configuration,
            _canonical_name(method, "validation method"),
            Int(precision_bits),
            artifact,
        )
    end
end

"""One branch decision, independent of its selected numerical value."""
struct BranchDecision
    choice_node::NodeId
    key::ChoiceKey
end

"""Validated guard range bound to its graph node and strictness semantics."""
struct GuardEnclosure{E<:NumericEnclosure}
    node::NodeId
    enclosure::E
    strict::Bool

    function GuardEnclosure(node::NodeId, enclosure::NumericEnclosure, strict::Bool)
        if strict
            enclosure.lower > zero(enclosure.lower) || throw(
                InvariantError(
                    :unseparated_strict_guard,
                    "a strict guard enclosure must lie strictly above zero",
                ),
            )
        else
            enclosure.lower >= zero(enclosure.lower) || throw(
                InvariantError(
                    :invalid_nonstrict_guard,
                    "a non-strict guard enclosure may not cross below zero",
                ),
            )
        end
        return new{typeof(enclosure)}(node, enclosure, strict)
    end
end

@enum ExactPromotionFailure::UInt8 begin
    EXACT_CAPABILITY_MISSING = 0
    EXACT_NONALGEBRAIC = 1
    EXACT_RECOGNITION_FAILED = 2
    EXACT_CONFIGURATION_CERT_FAILED = 3
    EXACT_TARGET_CERT_FAILED = 4
    EXACT_SINGULAR = 5
    EXACT_BUDGET_EXHAUSTED = 6
    EXACT_UNSUPPORTED = 7
end

function _freeze_branch_signature(signature)
    frozen = tuple((decision::BranchDecision for decision in signature)...)
    nodes = map(decision -> decision.choice_node, frozen)
    allunique(nodes) || throw(
        InvariantError(
            :duplicate_branch_decision,
            "a branch signature may decide each Choice node only once",
        ),
    )
    return Tuple(sort(collect(frozen); by = decision -> string(decision.choice_node)))
end

struct ExactAnswer{I<:AlgebraicTargetIdentity,A<:Real,B<:Tuple,C<:ConfigurationValidityCertificate,T<:TargetIdentityCertificate} <: AbstractAnswer
    identity::I
    approximation::A
    branch_signature::B
    configuration_certificate::C
    target_certificate::T

    function ExactAnswer(
        identity::AlgebraicTargetIdentity,
        approximation::Real,
        branch_signature,
        configuration_certificate::ConfigurationValidityCertificate,
        target_certificate::TargetIdentityCertificate,
    )
        _is_finite(approximation) || throw(
            InvariantError(:nonfinite_approximation, "an exact answer approximation must be finite"),
        )
        frozen_approximation = deepcopy(approximation)
        target_certificate.identity == _identity_hash(identity) || throw(
            InvariantError(
                :target_certificate_mismatch,
                "target certificate is not bound to the supplied algebraic identity",
            ),
        )
        target_certificate.problem == configuration_certificate.problem || throw(
            InvariantError(
                :certificate_problem_mismatch,
                "configuration and target certificates refer to different problems",
            ),
        )
        frozen_branches = _freeze_branch_signature(branch_signature)
        return new{
            typeof(identity),
            typeof(frozen_approximation),
            typeof(frozen_branches),
            typeof(configuration_certificate),
            typeof(target_certificate),
        }(
            identity,
            frozen_approximation,
            frozen_branches,
            configuration_certificate,
            target_certificate,
        )
    end
end

struct ProvisionalAnswer{E<:NumericEnclosure,R<:Real,B<:Tuple,G<:Tuple,V<:NumericalValidationEvidence} <: AbstractAnswer
    target::E
    canonical_residual_bound::R
    branch_signature::B
    guard_enclosures::G
    validation::V
    exact_failure::ExactPromotionFailure
    exact_failure_detail::String

    function ProvisionalAnswer(
        target::NumericEnclosure,
        canonical_residual_bound::R,
        branch_signature,
        validation::NumericalValidationEvidence,
        ;
        guard_enclosures = (),
        exact_failure::ExactPromotionFailure,
        exact_failure_detail::AbstractString = "",
    ) where {R<:Real}
        _is_finite(canonical_residual_bound) && canonical_residual_bound >= zero(R) || throw(
            InvariantError(
                :invalid_residual_bound,
                "a canonical residual bound must be finite and nonnegative",
            ),
        )
        frozen_branches = _freeze_branch_signature(branch_signature)
        frozen_guards = tuple((guard::GuardEnclosure for guard in guard_enclosures)...)
        guard_nodes = map(guard -> guard.node, frozen_guards)
        allunique(guard_nodes) || throw(
            InvariantError(
                :duplicate_guard_enclosure,
                "a provisional answer may report each guard node only once",
            ),
        )
        frozen_bound = deepcopy(canonical_residual_bound)
        return new{
            typeof(target),
            typeof(frozen_bound),
            typeof(frozen_branches),
            typeof(frozen_guards),
            typeof(validation),
        }(
            target,
            frozen_bound,
            frozen_branches,
            frozen_guards,
            validation,
            exact_failure,
            String(exact_failure_detail),
        )
    end
end

"""Exact identity required to resume a checkpoint without semantic drift."""
struct ResumeIdentity{L<:Tuple}
    graph::ContentHash
    plugin_locks::L
    policy::ContentHash
    environment::ContentHash

    function ResumeIdentity(graph::ContentHash, plugin_locks, policy::ContentHash, environment::ContentHash)
        frozen_locks = tuple((lock::PluginLock for lock in plugin_locks)...)
        allunique(map(lock -> lock.id, frozen_locks)) || throw(
            InvariantError(:duplicate_plugin_lock, "resume identity contains a duplicate plugin lock"),
        )
        ordered_locks = Tuple(sort(collect(frozen_locks); by = lock -> string(lock.id)))
        return new{typeof(ordered_locks)}(graph, ordered_locks, policy, environment)
    end
end

can_resume(current::ResumeIdentity, stored::ResumeIdentity) = current == stored

struct CoverageEvidence{S<:Tuple}
    independent_waves::Int
    proposed_tasks::Int
    completed_tasks::Int
    pending_tasks::Int
    explored_shells::S
    last_new_target_seconds::Union{Nothing,Float64}

    function CoverageEvidence(
        independent_waves::Integer,
        proposed_tasks::Integer,
        completed_tasks::Integer,
        pending_tasks::Integer;
        explored_shells = (),
        last_new_target_seconds::Union{Nothing,Real} = nothing,
    )
        counts = (independent_waves, proposed_tasks, completed_tasks, pending_tasks)
        all(count -> count >= 0, counts) || throw(
            InvariantError(:negative_coverage_count, "coverage counters cannot be negative"),
        )
        completed_tasks <= proposed_tasks || throw(
            InvariantError(:invalid_coverage_count, "completed tasks cannot exceed proposed tasks"),
        )
        completed_tasks + pending_tasks <= proposed_tasks || throw(
            InvariantError(
                :invalid_coverage_count,
                "completed plus pending tasks cannot exceed proposed tasks",
            ),
        )
        frozen_shells = tuple((Int(shell) for shell in explored_shells)...)
        all(shell -> shell >= 0, frozen_shells) || throw(
            InvariantError(:invalid_shell, "unbounded shell indexes cannot be negative"),
        )
        allunique(frozen_shells) || throw(
            InvariantError(:duplicate_shell, "each explored shell is recorded once"),
        )
        frozen_time = last_new_target_seconds === nothing ? nothing : Float64(last_new_target_seconds)
        frozen_time !== nothing && (!isfinite(frozen_time) || frozen_time < 0) && throw(
            InvariantError(:invalid_discovery_time, "last-new-target time must be finite and nonnegative"),
        )
        return new{typeof(frozen_shells)}(
            Int(independent_waves),
            Int(proposed_tasks),
            Int(completed_tasks),
            Int(pending_tasks),
            frozen_shells,
            frozen_time,
        )
    end
end

"""Content-locked pointer to the append-only diagnostic evidence log."""
struct EvidenceLogReference
    content::ContentHash
    location::String

    function EvidenceLogReference(content::ContentHash, location::AbstractString)
        frozen_location = String(location)
        isempty(strip(frozen_location)) && throw(
            InvariantError(:missing_evidence_log, "evidence-log location cannot be empty"),
        )
        return new(content, frozen_location)
    end
end

struct SolveResult{E<:Tuple,P<:Tuple,C<:CoverageEvidence,R<:ResumeIdentity,L<:EvidenceLogReference}
    exact_answers::E
    provisional_answers::P
    search_status::SearchStatus
    target_image_status::TargetImageStatus
    coverage::C
    environment_lock::R
    evidence_log::L

    function SolveResult(
        exact_answers,
        provisional_answers,
        search_status::SearchStatus,
        target_image_status::TargetImageStatus,
        coverage::CoverageEvidence,
        environment_lock::ResumeIdentity,
        evidence_log::EvidenceLogReference,
    )
        frozen_exact = tuple((answer::ExactAnswer for answer in exact_answers)...)
        frozen_provisional = tuple((answer::ProvisionalAnswer for answer in provisional_answers)...)
        allunique(map(answer -> answer.identity, frozen_exact)) || throw(
            InvariantError(:duplicate_exact_answer, "exact answers must be proof-deduplicated"),
        )

        isempty(frozen_exact) && isempty(frozen_provisional) ||
            target_image_status != TARGET_EMPTY_CERTIFIED || throw(
                InvariantError(:answers_in_empty_image, "a certified-empty image cannot contain answers"),
            )
        search_status == SEARCH_EMPTY_CERTIFIED && target_image_status != TARGET_EMPTY_CERTIFIED && throw(
            InvariantError(
                :inconsistent_empty_status,
                "SEARCH_EMPTY_CERTIFIED requires TARGET_EMPTY_CERTIFIED",
            ),
        )
        search_status == SEARCH_COMPLETE_CERTIFIED &&
            target_image_status ∉ (TARGET_COMPLETE_CERTIFIED, TARGET_EMPTY_CERTIFIED) && throw(
                InvariantError(
                    :inconsistent_complete_status,
                    "SEARCH_COMPLETE_CERTIFIED requires a certified target-image status",
                ),
            )
        return new{
            typeof(frozen_exact),
            typeof(frozen_provisional),
            typeof(coverage),
            typeof(environment_lock),
            typeof(evidence_log),
        }(
            frozen_exact,
            frozen_provisional,
            search_status,
            target_image_status,
            coverage,
            environment_lock,
            evidence_log,
        )
    end
end


environment_lock(result::SolveResult) = result.environment_lock
