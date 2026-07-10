module ExperimentSingular001

using JSON3
using LinearAlgebra
using SHA

const EXPERIMENT_ID = "EXP-SINGULAR-001"
const HARNESS_VERSION = v"0.1.0"

include("types.jl")
include("generators.jl")
include("harness.jl")
include("artifacts.jl")

export EXPERIMENT_ID,
    HARNESS_VERSION,
    EndpointOracle,
    CandidateInput,
    GoldTruth,
    GeneratedEndpoint,
    ExperimentOptions,
    WorkSnapshot,
    SemanticReplayEvidence,
    NumericalRootEvidence,
    ExperimentalOutcome,
    GoldAssessment,
    fixed_control_cases,
    candidate_input,
    run_s0,
    run_s1,
    assess_outcome,
    case_manifest_document,
    outcome_document,
    assessment_document,
    write_json_artifact

end
