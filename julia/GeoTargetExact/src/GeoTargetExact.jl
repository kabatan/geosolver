module GeoTargetExact

using Nemo

include("algebraic_real.jl")
include("recognition.jl")
include("certificates.jl")
include("c3a_stub.jl")

export AlgebraicReal,
    algebraic_value,
    exact_leaf_safe,
    AlgebraicDescriptor,
    RecognitionCandidate,
    RecognitionOptions,
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
    C3AReplayUnsupported,
    replay_c3a

end
