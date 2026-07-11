const _C3A_CONFIGURATION_SCHEME = "geotarget-c3a-configuration-v1"
const _C3A_TARGET_SCHEME = "geotarget-c3a-target-v1"
const _C3A_MEDIA_TYPE = "application/vnd.geotarget.c3a+json"
const _C3A_CONFIGURATION_SCHEMA = "geotarget.c3a-configuration/v1"
const _C3A_CONFIGURATION_CLAIM_SCHEMA = "geotarget.c3a-configuration-claim/v1"
const _C3A_TARGET_SCHEMA = "geotarget.c3a-target/v1"
const _C3A_MAX_ARTIFACT_BYTES = 1_048_576

@enum C3AVerificationFailure::UInt8 begin
    C3A_VERIFY_NONE = 0
    C3A_VERIFY_UNSUPPORTED_SCHEME = 1
    C3A_VERIFY_ARTIFACT_INVALID = 2
    C3A_VERIFY_PROBLEM_MISMATCH = 3
    C3A_VERIFY_CONFIGURATION_MISMATCH = 4
    C3A_VERIFY_BRANCH_MISMATCH = 5
    C3A_VERIFY_REPLAY_FAILED = 6
    C3A_VERIFY_TARGET_MISMATCH = 7
end

struct C3AVerificationResult
    accepted::Bool
    failure::C3AVerificationFailure
    detail::String

    function C3AVerificationResult(
        accepted::Bool,
        failure::C3AVerificationFailure,
        detail::AbstractString,
    )
        accepted == (failure == C3A_VERIFY_NONE) || throw(
            ArgumentError("C3A verification status and failure disagree"),
        )
        accepted == isempty(detail) || throw(
            ArgumentError("only failed C3A verification may carry detail"),
        )
        return new(accepted, failure, String(detail))
    end
end

_c3a_verify_success() = C3AVerificationResult(true, C3A_VERIFY_NONE, "")
_c3a_verify_failure(failure, detail) =
    C3AVerificationResult(false, failure, String(detail))

function _descriptor_or_error(value::AlgebraicReal, label::AbstractString)
    descriptor = descriptor_from_root(value)
    descriptor === nothing && error("cannot construct canonical descriptor for $label")
    return descriptor
end

function _branch_document(decision::BranchDecision)
    return Dict{String,Any}(
        "choice_node" => string(decision.choice_node),
        "key" => string(decision.key),
    )
end

function _branch_from_document(document)
    document isa AbstractDict || return nothing
    Set(String.(keys(document))) == Set(("choice_node", "key")) || return nothing
    node = get(document, "choice_node", nothing)
    key = get(document, "key", nothing)
    node isa AbstractString && key isa AbstractString || return nothing
    return try
        BranchDecision(NodeId(node), ChoiceKey(key))
    catch
        nothing
    end
end

function _configuration_claim_document(problem, candidates, branches)
    length(candidates) == length(problem.variables) || throw(
        DimensionMismatch("recognition candidate count differs from problem variables"),
    )
    variable_documents = Any[
        Dict{String,Any}(
            "descriptor" => descriptor_document(candidates[index].descriptor),
            "variable" => string(problem.variables[index].id),
        ) for index in eachindex(candidates)
    ]
    branch_documents = Any[_branch_document(decision) for decision in branches]
    sort!(branch_documents; by=document -> document["choice_node"])
    return Dict{String,Any}(
        "branch_signature" => branch_documents,
        "schema" => _C3A_CONFIGURATION_CLAIM_SCHEMA,
        "variables" => variable_documents,
    )
end

function _margin_document(proof::C3AMarginProof)
    return Dict{String,Any}(
        "margin" => descriptor_document(_descriptor_or_error(proof.margin, "margin")),
        "node" => string(proof.node),
        "strict" => proof.strict,
    )
end

function _branch_proof_document(proof::C3ABranchProof)
    return Dict{String,Any}(
        "choice_node" => string(proof.decision.choice_node),
        "key" => string(proof.decision.key),
        "selector_margin" => descriptor_document(
            _descriptor_or_error(proof.selector_margin, "selector margin"),
        ),
        "validity_margin" => descriptor_document(
            _descriptor_or_error(proof.validity_margin, "validity margin"),
        ),
    )
end

function _proof_document(evidence::C3AReplayEvidence)
    relation_documents = Any[
        Dict{String,Any}("node" => string(proof.node)) for proof in evidence.relations
    ]
    guard_documents = Any[_margin_document(proof) for proof in evidence.guards]
    domain_documents = Any[_margin_document(proof) for proof in evidence.domains]
    branch_documents = Any[_branch_proof_document(proof) for proof in evidence.branches]
    sort!(relation_documents; by=document -> document["node"])
    sort!(guard_documents; by=document -> document["node"])
    sort!(domain_documents; by=document -> document["node"])
    sort!(branch_documents; by=document -> document["choice_node"])
    return Dict{String,Any}(
        "branches" => branch_documents,
        "domains" => domain_documents,
        "guards" => guard_documents,
        "relations_exactly_zero" => relation_documents,
        "target" => descriptor_document(_descriptor_or_error(evidence.target, "target")),
    )
end

function _configuration_hash(claim)
    return content_hash(GeoTargetCore.canonical_json(claim))
end

function _identity_from_descriptor(descriptor::AlgebraicDescriptor)
    interval = RationalInterval(
        ExactRational(numerator(descriptor.lower), denominator(descriptor.lower)),
        ExactRational(numerator(descriptor.upper), denominator(descriptor.upper)),
    )
    return AlgebraicTargetIdentity(
        Tuple(ExactInteger(value) for value in descriptor.coefficients),
        interval,
        descriptor.root_index,
    )
end

function _descriptor_from_identity(identity::AlgebraicTargetIdentity)
    coefficients = Tuple(parse(BigInt, value.decimal) for value in identity.coefficients)
    lower = identity.isolating_interval.lower
    upper = identity.isolating_interval.upper
    lower_rational = parse(BigInt, lower.numerator.decimal) //
                     parse(BigInt, lower.denominator.decimal)
    upper_rational = parse(BigInt, upper.numerator.decimal) //
                     parse(BigInt, upper.denominator.decimal)
    return try
        AlgebraicDescriptor(coefficients, lower_rational, upper_rational, identity.real_root_index)
    catch
        nothing
    end
end

function _build_c3a_exact_answer(
    compiled::GeoTargetCore.CompiledProblem,
    validation::CandidateValidationResult,
    candidates,
    replay::C3AReplayEvidence,
)
    branches = Tuple(proof.decision for proof in replay.branches)
    claim = _configuration_claim_document(compiled.problem, candidates, branches)
    configuration_digest = _configuration_hash(claim)
    # Bind the same canonical identity already established by Core candidate
    # validation. A structural compiler-cache identity is not a substitute.
    problem_digest = validation.problem
    configuration_document = Dict{String,Any}(
        "claim" => claim,
        "configuration" => string(configuration_digest),
        "problem" => string(problem_digest),
        "proof" => _proof_document(replay),
        "schema" => _C3A_CONFIGURATION_SCHEMA,
    )
    configuration_payload = GeoTargetCore.canonical_json(configuration_document)
    configuration_artifact = CertificateArtifact(
        _C3A_CONFIGURATION_SCHEME,
        configuration_payload;
        media_type=_C3A_MEDIA_TYPE,
    )
    configuration_certificate = ConfigurationValidityCertificate(
        problem_digest,
        configuration_digest,
        configuration_artifact,
    )

    target_descriptor = _descriptor_or_error(replay.target, "target")
    identity = _identity_from_descriptor(target_descriptor)
    target_document = Dict{String,Any}(
        "configuration" => string(configuration_digest),
        "descriptor" => descriptor_document(target_descriptor),
        "problem" => string(problem_digest),
        "schema" => _C3A_TARGET_SCHEMA,
    )
    target_artifact = CertificateArtifact(
        _C3A_TARGET_SCHEME,
        GeoTargetCore.canonical_json(target_document);
        media_type=_C3A_MEDIA_TYPE,
    )
    target_certificate = TargetIdentityCertificate(problem_digest, identity, target_artifact)
    approximation = validation.canonical_observation.target
    approximation isa Real && isfinite(approximation) || error(
        "validated target approximation is not finite Real",
    )
    return ExactAnswer(
        identity,
        deepcopy(approximation),
        branches,
        configuration_certificate,
        target_certificate,
    )
end

function _parse_canonical_artifact(artifact::CertificateArtifact, scheme::String)
    artifact.scheme == scheme || return nothing, C3A_VERIFY_UNSUPPORTED_SCHEME,
        "certificate scheme $(artifact.scheme) is unsupported"
    artifact.media_type == _C3A_MEDIA_TYPE || return nothing, C3A_VERIFY_ARTIFACT_INVALID,
        "certificate media type is not the canonical C3A JSON type"
    content_hash(Vector{UInt8}(codeunits(artifact.payload))) == artifact.digest || return (
        nothing,
        C3A_VERIFY_ARTIFACT_INVALID,
        "certificate digest does not match its payload",
    )
    ncodeunits(artifact.payload) <= _C3A_MAX_ARTIFACT_BYTES || return (
        nothing,
        C3A_VERIFY_ARTIFACT_INVALID,
        "certificate JSON exceeds the C3A verifier size limit",
    )
    document = try
        JSON3.read(artifact.payload, Dict{String,Any})
    catch error
        return nothing, C3A_VERIFY_ARTIFACT_INVALID,
            "certificate JSON cannot be parsed: $(sprint(showerror, error))"
    end
    canonical = try
        GeoTargetCore.canonical_json(document)
    catch error
        error isa InterruptException && rethrow()
        return nothing, C3A_VERIFY_ARTIFACT_INVALID,
            "certificate JSON cannot be canonicalized: $(sprint(showerror, error))"
    end
    canonical == artifact.payload || return (
        nothing,
        C3A_VERIFY_ARTIFACT_INVALID,
        "certificate JSON is not in canonical byte form",
    )
    return document, C3A_VERIFY_NONE, ""
end

function _decode_configuration_claim(problem, claim)
    claim isa AbstractDict || return nothing
    Set(String.(keys(claim))) == Set(("branch_signature", "schema", "variables")) ||
        return nothing
    get(claim, "schema", nothing) == _C3A_CONFIGURATION_CLAIM_SCHEMA || return nothing
    raw_variables = get(claim, "variables", nothing)
    raw_variables isa AbstractVector && length(raw_variables) == length(problem.variables) ||
        return nothing
    descriptors = AlgebraicDescriptor[]
    coordinates = AlgebraicReal[]
    for (index, raw) in enumerate(raw_variables)
        raw isa AbstractDict || return nothing
        Set(String.(keys(raw))) == Set(("descriptor", "variable")) || return nothing
        get(raw, "variable", nothing) == string(problem.variables[index].id) || return nothing
        descriptor = descriptor_from_document(raw["descriptor"])
        descriptor === nothing && return nothing
        coordinate = reconstruct_descriptor(descriptor)
        coordinate === nothing && return nothing
        push!(descriptors, descriptor)
        push!(coordinates, coordinate)
    end
    raw_branches = get(claim, "branch_signature", nothing)
    raw_branches isa AbstractVector || return nothing
    branches = BranchDecision[]
    for raw in raw_branches
        branch = _branch_from_document(raw)
        branch === nothing && return nothing
        push!(branches, branch)
    end
    canonical_branches = _canonical_branch_decisions(branches)
    length(canonical_branches) == length(branches) || return nothing
    canonical_document = _configuration_claim_document(
        problem,
        Tuple(RecognitionCandidate(
            descriptors[index],
            length(descriptors[index].coefficients) - 1,
            1,
            512,
            768,
            "artifact_reconstruction",
        ) for index in eachindex(descriptors)),
        canonical_branches,
    )
    GeoTargetCore.canonical_json(canonical_document) == GeoTargetCore.canonical_json(claim) ||
        return nothing
    return (Tuple(coordinates), Tuple(descriptors), canonical_branches)
end

function _identity_contains_approximation(identity, approximation)
    approximation isa Real && isfinite(approximation) || return false
    lower = identity.isolating_interval.lower
    upper = identity.isolating_interval.upper
    lower_value = parse(BigInt, lower.numerator.decimal) //
                  parse(BigInt, lower.denominator.decimal)
    upper_value = parse(BigInt, upper.numerator.decimal) //
                  parse(BigInt, upper.denominator.decimal)
    text = try
        string(approximation)
    catch
        return false
    end
    precision_bits = max(
        256,
        approximation isa BigFloat ? precision(approximation) : 4 * ncodeunits(text) + 32,
    )
    return try
        setprecision(BigFloat, precision_bits) do
            parsed = parse(BigFloat, text)
            isfinite(parsed) && BigFloat(lower_value) < parsed < BigFloat(upper_value)
        end
    catch
        false
    end
end

"""Reconstruct both artifacts and independently replay the original graph."""
function _verify_c3a_exact_answer(
    compiled::GeoTargetCore.CompiledProblem,
    answer::ExactAnswer,
)
    problem_digest = first(GeoTargetCore._candidate_problem_identity(compiled))
    configuration_certificate = answer.configuration_certificate
    target_certificate = answer.target_certificate
    configuration_certificate.problem == problem_digest &&
        target_certificate.problem == problem_digest || return _c3a_verify_failure(
            C3A_VERIFY_PROBLEM_MISMATCH,
            "certificate problem hash differs from the supplied original graph",
        )

    configuration_document, failure, detail = _parse_canonical_artifact(
        configuration_certificate.artifact,
        _C3A_CONFIGURATION_SCHEME,
    )
    configuration_document === nothing && return _c3a_verify_failure(failure, detail)
    Set(String.(keys(configuration_document))) ==
        Set(("claim", "configuration", "problem", "proof", "schema")) ||
        return _c3a_verify_failure(
            C3A_VERIFY_ARTIFACT_INVALID,
            "configuration artifact has unexpected fields",
        )
    get(configuration_document, "schema", nothing) == _C3A_CONFIGURATION_SCHEMA ||
        return _c3a_verify_failure(
            C3A_VERIFY_ARTIFACT_INVALID,
            "configuration artifact schema is unsupported",
        )
    get(configuration_document, "problem", nothing) == string(problem_digest) ||
        return _c3a_verify_failure(
            C3A_VERIFY_PROBLEM_MISMATCH,
            "configuration artifact problem hash differs",
        )
    decoded = _decode_configuration_claim(compiled.problem, configuration_document["claim"])
    decoded === nothing && return _c3a_verify_failure(
        C3A_VERIFY_CONFIGURATION_MISMATCH,
        "configuration claim cannot be reconstructed canonically",
    )
    coordinates, _, claimed_branches = decoded
    configuration_digest = _configuration_hash(configuration_document["claim"])
    configuration_digest == configuration_certificate.configuration &&
        get(configuration_document, "configuration", nothing) == string(configuration_digest) ||
        return _c3a_verify_failure(
            C3A_VERIFY_CONFIGURATION_MISMATCH,
            "configuration hash does not bind the reconstructed descriptors",
        )
    answer_branches = _canonical_branch_decisions(answer.branch_signature)
    _branch_decisions_equal(answer_branches, claimed_branches) || return _c3a_verify_failure(
        C3A_VERIFY_BRANCH_MISMATCH,
        "answer branch signature differs from the configuration artifact",
    )

    replay = replay_c3a(compiled, coordinates; expected_branches=answer_branches)
    replay isa C3AReplayResult && replay.accepted || return _c3a_verify_failure(
        C3A_VERIFY_REPLAY_FAILED,
        replay isa C3AReplayResult ? replay.detail : "C3A replay returned an invalid result",
    )
    GeoTargetCore.canonical_json(configuration_document["proof"]) ==
        GeoTargetCore.canonical_json(_proof_document(replay.evidence)) ||
        return _c3a_verify_failure(
            C3A_VERIFY_CONFIGURATION_MISMATCH,
            "configuration proof does not equal the independent exact replay",
        )

    target_document, failure, detail = _parse_canonical_artifact(
        target_certificate.artifact,
        _C3A_TARGET_SCHEME,
    )
    target_document === nothing && return _c3a_verify_failure(failure, detail)
    Set(String.(keys(target_document))) ==
        Set(("configuration", "descriptor", "problem", "schema")) ||
        return _c3a_verify_failure(
            C3A_VERIFY_ARTIFACT_INVALID,
            "target artifact has unexpected fields",
        )
    get(target_document, "schema", nothing) == _C3A_TARGET_SCHEMA || return _c3a_verify_failure(
        C3A_VERIFY_ARTIFACT_INVALID,
        "target artifact schema is unsupported",
    )
    get(target_document, "problem", nothing) == string(problem_digest) ||
        return _c3a_verify_failure(C3A_VERIFY_PROBLEM_MISMATCH, "target problem hash differs")
    get(target_document, "configuration", nothing) == string(configuration_digest) ||
        return _c3a_verify_failure(
            C3A_VERIFY_CONFIGURATION_MISMATCH,
            "target artifact is not bound to the configuration claim",
        )
    target_descriptor = descriptor_from_document(target_document["descriptor"])
    target_descriptor === nothing && return _c3a_verify_failure(
        C3A_VERIFY_TARGET_MISMATCH,
        "target descriptor cannot be reconstructed",
    )
    answer_descriptor = _descriptor_from_identity(answer.identity)
    answer_descriptor !== nothing &&
        same_algebraic_identity(answer_descriptor, target_descriptor) ||
        return _c3a_verify_failure(
            C3A_VERIFY_TARGET_MISMATCH,
            "answer identity differs from its target artifact",
        )
    replay_descriptor = descriptor_from_root(replay.evidence.target)
    replay_descriptor !== nothing &&
        same_algebraic_identity(replay_descriptor, target_descriptor) ||
        return _c3a_verify_failure(
            C3A_VERIFY_TARGET_MISMATCH,
            "target artifact differs from independent exact graph replay",
        )
    target_certificate.identity == GeoTargetBase._identity_hash(answer.identity) ||
        return _c3a_verify_failure(
            C3A_VERIFY_TARGET_MISMATCH,
            "target certificate identity hash differs",
        )
    _identity_contains_approximation(answer.identity, answer.approximation) ||
        return _c3a_verify_failure(
            C3A_VERIFY_TARGET_MISMATCH,
            "numerical approximation lies outside the exact isolating interval",
        )
    return _c3a_verify_success()
end

"""Fail-closed public boundary around C3A artifact reconstruction and replay."""
function verify_c3a_exact_answer(
    compiled::GeoTargetCore.CompiledProblem,
    answer::ExactAnswer,
)
    return try
        _verify_c3a_exact_answer(compiled, answer)
    catch error
        error isa InterruptException && rethrow()
        _c3a_verify_failure(
            C3A_VERIFY_ARTIFACT_INVALID,
            "C3A verification failed closed: $(sprint(showerror, error))",
        )
    end
end
