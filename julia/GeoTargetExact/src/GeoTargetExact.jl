module GeoTargetExact

using GeoTargetBase
using GeoTargetCore
using JSON3
using Nemo

struct _ExactSampleAbort <: Exception
    failure::ExactSampleFailure
    detail::String
end

Base.showerror(io::IO, error::_ExactSampleAbort) =
    print(io, "exact sample ", error.failure, ": ", error.detail)

include("algebraic_real.jl")
include("pslq.jl")
include("recognition.jl")
include("certificates.jl")
include("c3a_replay.jl")
include("exact_artifacts.jl")
include("backend.jl")

export AlgebraicReal,
    algebraic_value,
    exact_leaf_safe,
    AlgebraicDescriptor,
    RecognitionCandidate,
    RecognitionOptions,
    PSLQFailure,
    PSLQ_NONE,
    PSLQ_INVALID_INPUT,
    PSLQ_INSUFFICIENT_PRECISION,
    PSLQ_COEFFICIENT_LIMIT,
    PSLQ_MAX_ITERATIONS,
    PSLQ_NUMERICAL_BREAKDOWN,
    PSLQResult,
    pslq_relation,
    working_precision,
    bounded_rational_reconstruction,
    nemo_lll_relation,
    normalize_polynomial,
    descriptor_from_relation,
    descriptor_from_root,
    descriptor_document,
    descriptor_from_document,
    reconstruct_descriptor,
    recognize_at,
    recognize_algebraic,
    same_algebraic_identity,
    C3AReplayFailure,
    C3A_REPLAY_NONE,
    C3A_REPLAY_CAPABILITY_MISSING,
    C3A_REPLAY_LITERAL_UNSUPPORTED,
    C3A_REPLAY_CALLBACK_FAILED,
    C3A_REPLAY_NONEXACT_VALUE,
    C3A_REPLAY_TYPE_MISMATCH,
    C3A_REPLAY_BOUNDS_FAILED,
    C3A_REPLAY_RELATION_FAILED,
    C3A_REPLAY_GUARD_FAILED,
    C3A_REPLAY_DOMAIN_FAILED,
    C3A_REPLAY_BRANCH_FAILED,
    C3A_REPLAY_BRANCH_MISMATCH,
    C3A_REPLAY_TARGET_FAILED,
    C3AReplayUnsupported,
    C3ARelationProof,
    C3AMarginProof,
    C3ABranchProof,
    C3AReplayEvidence,
    C3AReplayResult,
    replay_c3a,
    C3AVerificationFailure,
    C3A_VERIFY_NONE,
    C3A_VERIFY_UNSUPPORTED_SCHEME,
    C3A_VERIFY_ARTIFACT_INVALID,
    C3A_VERIFY_PROBLEM_MISMATCH,
    C3A_VERIFY_CONFIGURATION_MISMATCH,
    C3A_VERIFY_BRANCH_MISMATCH,
    C3A_VERIFY_REPLAY_FAILED,
    C3A_VERIFY_TARGET_MISMATCH,
    C3AVerificationResult,
    verify_c3a_exact_answer,
    NemoExactBackend,
    exact_backend_descriptor,
    exactify_candidate

end
