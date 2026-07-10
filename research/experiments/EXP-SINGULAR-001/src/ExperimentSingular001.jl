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
include("development.jl")
include("s2_development.jl")

export EXPERIMENT_ID,
    HARNESS_VERSION,
    EndpointOracle,
    CandidateInput,
    GoldTruth,
    GeneratedEndpoint,
    ExperimentOptions,
    WorkSnapshot,
    SemanticReplayEvidence,
    AbstractNumericalRootEvidence,
    NumericalRootEvidence,
    NumericalManifoldRootEvidence,
    ExperimentalOutcome,
    GoldAssessment,
    fixed_control_cases,
    development_cases,
    s2_development_cases,
    candidate_input,
    run_s0,
    run_s1,
    run_s2,
    assess_outcome,
    case_manifest_document,
    outcome_document,
    assessment_document,
    development_input_document,
    s2_development_input_document,
    run_development,
    development_summary,
    write_development_results,
    run_s2_development,
    s2_development_summary,
    write_s2_development_results,
    write_json_artifact

end
