@enum ExactVerificationFailure::UInt8 begin
    EXACT_VERIFICATION_NONE = 0
    EXACT_VERIFICATION_UNSUPPORTED_SCHEME = 1
    EXACT_VERIFICATION_PROBLEM_MISMATCH = 2
    EXACT_VERIFICATION_CONFIGURATION_MISMATCH = 3
    EXACT_VERIFICATION_TARGET_MISMATCH = 4
    EXACT_VERIFICATION_ARTIFACT_INVALID = 5
end

"""Result of independently replaying an `ExactAnswer` certificate pair."""
struct ExactVerificationResult
    accepted::Bool
    failure::ExactVerificationFailure
    detail::String

    function ExactVerificationResult(
        accepted::Bool,
        failure::ExactVerificationFailure,
        detail::AbstractString,
    )
        accepted == (failure == EXACT_VERIFICATION_NONE) || throw(
            InvariantError(
                :exact_verification_status_mismatch,
                "exact verification status and failure reason disagree",
            ),
        )
        accepted == isempty(detail) || throw(
            InvariantError(
                :exact_verification_detail_mismatch,
                "only failed exact verification carries detail",
            ),
        )
        return new(accepted, failure, String(detail))
    end
end

_exact_verification_success() =
    ExactVerificationResult(true, EXACT_VERIFICATION_NONE, "")
_exact_verification_failure(failure, detail) =
    ExactVerificationResult(false, failure, detail)

function _exact_certificate_object(artifact, scheme, required, path)
    artifact.scheme == scheme || return nothing, "unsupported scheme $(artifact.scheme)"
    artifact.media_type == "application/json" ||
        return nothing, "certificate media type must be application/json"
    document = try
        parse_protocol_json(artifact.payload)
    catch error
        error isa ProtocolJsonError || rethrow()
        return nothing, sprint(showerror, error)
    end
    canonical_json(document) == artifact.payload ||
        return nothing, "certificate JSON is not canonical"
    object = try
        _object(document, required; path)
    catch error
        error isa ProtocolJsonError || rethrow()
        return nothing, sprint(showerror, error)
    end
    return object, nothing
end

function _literal_exact_rational(value::Rational{BigInt})
    return ExactRational(numerator(value), denominator(value))
end

function _identity_matches_literal(identity::AlgebraicTargetIdentity, rational)
    expected_coefficients = (string(-numerator(rational)), string(denominator(rational)))
    actual_coefficients = Tuple(string(coefficient) for coefficient in identity.coefficients)
    actual_coefficients == expected_coefficients || return false
    identity.real_root_index == 1 || return false
    exact = _literal_exact_rational(rational)
    interval = identity.isolating_interval
    return isless(interval.lower, exact) && isless(exact, interval.upper)
end

function _approximation_is_isolated(answer::ExactAnswer)
    interval = answer.identity.isolating_interval
    return try
        setprecision(BigFloat, 256) do
            approximation = parse(BigFloat, string(answer.approximation))
            lower = parse(BigFloat, string(interval.lower.numerator)) /
                    parse(BigFloat, string(interval.lower.denominator))
            upper = parse(BigFloat, string(interval.upper.numerator)) /
                    parse(BigFloat, string(interval.upper.denominator))
            lower < approximation < upper
        end
    catch error
        error isa ArgumentError || rethrow()
        false
    end
end

function _verify_literal_configuration_certificate(
    compiled::CompiledProblem,
    answer::ExactAnswer,
    problem_digest::ContentHash,
)
    certificate = answer.configuration_certificate
    certificate.problem == problem_digest || return _exact_verification_failure(
        EXACT_VERIFICATION_PROBLEM_MISMATCH,
        "configuration certificate problem hash differs from the supplied problem",
    )
    expected_configuration = _candidate_configuration_hash(compiled, Real[])
    certificate.configuration == expected_configuration || return _exact_verification_failure(
        EXACT_VERIFICATION_CONFIGURATION_MISMATCH,
        "configuration certificate hash is not the empty configuration hash",
    )
    object, error = _exact_certificate_object(
        certificate.artifact,
        _LITERAL_CONFIGURATION_CERTIFICATE_SCHEME,
        ("configuration", "constraint_count", "problem", "schema"),
        "configuration_certificate.artifact",
    )
    object === nothing && return _exact_verification_failure(
        occursin("unsupported scheme", error) ?
        EXACT_VERIFICATION_UNSUPPORTED_SCHEME : EXACT_VERIFICATION_ARTIFACT_INVALID,
        error,
    )
    try
        _string(object["schema"], "configuration_certificate.artifact.schema") ==
        _LITERAL_CONFIGURATION_CERTIFICATE_SCHEMA || return _exact_verification_failure(
            EXACT_VERIFICATION_CONFIGURATION_MISMATCH,
            "configuration certificate schema is not the literal proof schema",
        )
        _string(object["problem"], "configuration_certificate.artifact.problem") ==
        string(problem_digest) || return _exact_verification_failure(
            EXACT_VERIFICATION_PROBLEM_MISMATCH,
            "configuration artifact problem hash differs from the supplied problem",
        )
        _string(
            object["configuration"],
            "configuration_certificate.artifact.configuration",
        ) == string(expected_configuration) || return _exact_verification_failure(
            EXACT_VERIFICATION_CONFIGURATION_MISMATCH,
            "configuration artifact hash differs from the empty configuration hash",
        )
        _integer(
            object["constraint_count"],
            "configuration_certificate.artifact.constraint_count";
            minimum=0,
        ) == 0 || return _exact_verification_failure(
            EXACT_VERIFICATION_CONFIGURATION_MISMATCH,
            "literal configuration certificate must have zero constraints",
        )
    catch protocol_error
        protocol_error isa ProtocolJsonError || rethrow()
        return _exact_verification_failure(
            EXACT_VERIFICATION_ARTIFACT_INVALID,
            sprint(showerror, protocol_error),
        )
    end
    return _exact_verification_success()
end

function _verify_literal_target_certificate(
    answer::ExactAnswer,
    problem_digest::ContentHash,
    rational::Rational{BigInt},
)
    certificate = answer.target_certificate
    certificate.problem == problem_digest || return _exact_verification_failure(
        EXACT_VERIFICATION_PROBLEM_MISMATCH,
        "target certificate problem hash differs from the supplied problem",
    )
    certificate.identity == GeoTargetBase._identity_hash(answer.identity) ||
        return _exact_verification_failure(
            EXACT_VERIFICATION_TARGET_MISMATCH,
            "target certificate is not bound to the answer identity",
        )
    object, error = _exact_certificate_object(
        certificate.artifact,
        _LITERAL_TARGET_CERTIFICATE_SCHEME,
        (
            "isolating_interval",
            "polynomial_ascending",
            "problem",
            "real_root_index",
            "schema",
            "target",
        ),
        "target_certificate.artifact",
    )
    object === nothing && return _exact_verification_failure(
        occursin("unsupported scheme", error) ?
        EXACT_VERIFICATION_UNSUPPORTED_SCHEME : EXACT_VERIFICATION_ARTIFACT_INVALID,
        error,
    )
    payload_identity = try
        _decode_identity(
            Dict{String,Any}(
                "coefficients" => object["polynomial_ascending"],
                "isolating_interval" => object["isolating_interval"],
                "real_root_index" => object["real_root_index"],
            ),
            "target_certificate.artifact.identity",
        )
    catch protocol_error
        protocol_error isa ProtocolJsonError || rethrow()
        return _exact_verification_failure(
            EXACT_VERIFICATION_ARTIFACT_INVALID,
            sprint(showerror, protocol_error),
        )
    end
    GeoTargetBase._identity_hash(payload_identity) ==
        GeoTargetBase._identity_hash(answer.identity) || return _exact_verification_failure(
        EXACT_VERIFICATION_TARGET_MISMATCH,
        "target artifact identity differs from the answer identity",
    )
    payload_target = try
        _decode_rational(object["target"], "target_certificate.artifact.target")
    catch protocol_error
        protocol_error isa ProtocolJsonError || rethrow()
        return _exact_verification_failure(
            EXACT_VERIFICATION_ARTIFACT_INVALID,
            sprint(showerror, protocol_error),
        )
    end
    payload_target == _literal_exact_rational(rational) || return _exact_verification_failure(
        EXACT_VERIFICATION_TARGET_MISMATCH,
        "target artifact rational differs from the literal target",
    )
    approximation_matches = try
        setprecision(BigFloat, 768) do
            exact_target = BigFloat(numerator(rational)) / BigFloat(denominator(rational))
            approximation = answer.approximation isa BigFloat ?
                            BigFloat(answer.approximation) :
                            parse(BigFloat, string(answer.approximation))
            scale = max(one(BigFloat), abs(exact_target))
            abs(exact_target - approximation) / scale <= parse(BigFloat, "1e-100")
        end
    catch error
        error isa ArgumentError || rethrow()
        false
    end
    approximation_matches || return _exact_verification_failure(
        EXACT_VERIFICATION_TARGET_MISMATCH,
        "answer approximation disagrees with the exact literal target",
    )
    try
        _string(object["schema"], "target_certificate.artifact.schema") ==
        _LITERAL_TARGET_CERTIFICATE_SCHEMA || return _exact_verification_failure(
            EXACT_VERIFICATION_TARGET_MISMATCH,
            "target certificate schema is not the literal linear proof schema",
        )
        _string(object["problem"], "target_certificate.artifact.problem") ==
        string(problem_digest) || return _exact_verification_failure(
            EXACT_VERIFICATION_PROBLEM_MISMATCH,
            "target artifact problem hash differs from the supplied problem",
        )
    catch protocol_error
        protocol_error isa ProtocolJsonError || rethrow()
        return _exact_verification_failure(
            EXACT_VERIFICATION_ARTIFACT_INVALID,
            sprint(showerror, protocol_error),
        )
    end
    return _exact_verification_success()
end

"""
Independently replay the proof pair of an exact literal-target answer.

Unsupported future proof schemes return a typed failure; they never inherit
trust from the `ExactAnswer` container or from numerical agreement.
"""
function verify_exact_answer(compiled::CompiledProblem, answer::ExactAnswer)
    problem = compiled.problem
    isempty(problem.variables) && isempty(problem.relations) &&
        isempty(problem.guards) && isempty(problem.domains) ||
        return _exact_verification_failure(
            EXACT_VERIFICATION_UNSUPPORTED_SCHEME,
            "literal exact verification requires an unconstrained zero-variable problem",
        )
    isempty(answer.branch_signature) || return _exact_verification_failure(
        EXACT_VERIFICATION_CONFIGURATION_MISMATCH,
        "literal exact answers cannot carry branch decisions",
    )
    literal = _literal_target_node(problem)
    literal === nothing && return _exact_verification_failure(
        EXACT_VERIFICATION_UNSUPPORTED_SCHEME,
        "the supplied problem target is not a direct literal",
    )
    rational = _exact_literal_rational(literal.value)
    rational === nothing && return _exact_verification_failure(
        EXACT_VERIFICATION_UNSUPPORTED_SCHEME,
        "the literal target cannot be represented as a finite exact rational",
    )
    _identity_matches_literal(answer.identity, rational) ||
        return _exact_verification_failure(
            EXACT_VERIFICATION_TARGET_MISMATCH,
            "answer identity does not isolate the literal rational",
        )
    _approximation_is_isolated(answer) || return _exact_verification_failure(
        EXACT_VERIFICATION_TARGET_MISMATCH,
        "answer approximation lies outside its isolating interval",
    )
    problem_digest, _ = _candidate_problem_identity(compiled)
    configuration = _verify_literal_configuration_certificate(
        compiled,
        answer,
        problem_digest,
    )
    configuration.accepted || return configuration
    return _verify_literal_target_certificate(answer, problem_digest, rational)
end

function verify_exact_answer(
    problem::ProblemSpecV1,
    registry::FrozenPluginRegistry,
    answer::ExactAnswer,
)
    return verify_exact_answer(compile_problem(problem, registry), answer)
end
