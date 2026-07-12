module ExperimentDisc001

using GeoTargetBenchmarks
using GeoTargetCore
using JSON3
using LinearAlgebra
using QuasiMonteCarlo
using Random
using SHA

const EXPERIMENT_ROOT = normpath(joinpath(@__DIR__, ".."))
const REPOSITORY_ROOT = normpath(joinpath(EXPERIMENT_ROOT, "..", "..", ".."))

include("gate.jl")
include("matrix_artifact.jl")
include("streams.jl")
include("runner_contract.jl")
include("t0_corpus.jl")
include("t0_materialization.jl")

export CHECKPOINT_COLUMNS,
    MATRIX_COLUMN_COUNT,
    DiscoveryGateError,
    DiscoveryMethod,
    D0_IID_ALL,
    D1_SOBOL_ALL,
    D_HALTON_ALL,
    D_CURRENT_COUNTER_HALTON,
    D2O_OWEN_ALL,
    D2M_MATOUSEK_ALL,
    D3_OWEN_MIXED,
    ProposalDomain,
    ProposalMatrixArtifact,
    RunnerOptions,
    artifact_document,
    artifact_sha256,
    derive_seed,
    digital_net_minimal_t,
    digital_net_prefix_audit,
    iid_bounded_gap_audit,
    leading_prefix,
    materialization_preflight,
    materialize_t0_inputs,
    materialize_stream_once,
    matrix_from_document,
    parse_runner_arguments,
    preregistration_bindings,
    read_matrix_artifact,
    run_preflight,
    shard_ordinals,
    static_prefix_audit,
    stream_contract,
    t0_materialization_preflight,
    t0_problem_with_proposals,
    t0_problems,
    t0_proposal_domain,
    truth_blind_domain,
    write_matrix_once

end
