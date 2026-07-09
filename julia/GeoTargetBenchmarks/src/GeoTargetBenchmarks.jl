module GeoTargetBenchmarks

using LinearAlgebra
using Random
using SHA

const PACKAGE_VERSION = v"0.1.0-DEV"
const REPLAY_FORMAT_VERSION = "direct-analytic-replay-v1"

include("types.jl")
include("replay.jl")
include("common.jl")
include("scale_ladder.jl")
include("curved_chain.jl")
include("near_rank_deficient.jl")
include("redundant_overdetermined.jl")
include("tangent_circle_line.jl")
include("multiroot_warped.jl")

export PACKAGE_VERSION,
    REPLAY_FORMAT_VERSION,
    AbstractGoldTargetDescriptor,
    ExactGoldTarget,
    ValidatedGoldTarget,
    DirectAnalyticProblem,
    MaterializedArtifact,
    configuration_indices,
    numeric_target,
    target_interval,
    has_analytic_jacobian,
    replay_checksum,
    artifact_checksum,
    verify_replay_material,
    saved_starts,
    generate,
    ScaleLadderParams,
    CurvedChainParams,
    NearRankDeficientParams,
    RedundantOverdeterminedParams,
    TangentCircleLineParams,
    MultiRootWarpedParams

end
