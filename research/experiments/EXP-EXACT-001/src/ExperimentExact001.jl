module ExperimentExact001

using GeoTargetBase
using GeoTargetCore
using GeoTargetExact

include("development_plugins.jl")
include("development_cases.jl")
include("solve_adapter.jl")

export DEV_POLYNOMIAL_PLUGIN_ID,
    DEV_BRANCH_PLUGIN_ID,
    DevelopmentCaseInput,
    DevelopmentTruth,
    DevelopmentFixture,
    development_fixtures,
    ExactReplayRecord,
    ExactCampaignRun,
    replay_returned_exact_answers,
    run_exact_case

end

