include(joinpath(@__DIR__, "src", "ExperimentSingular001.jl"))
using .ExperimentSingular001

const REPO_ROOT = normpath(joinpath(@__DIR__, "..", "..", ".."))
const DEFAULT_OUTPUT = joinpath(
    REPO_ROOT,
    "research",
    "results",
    EXPERIMENT_ID,
    "development-s0-s1-v0",
)

output_root = isempty(ARGS) ? DEFAULT_OUTPUT : abspath(first(ARGS))
length(ARGS) <= 1 || error("usage: run_development.jl [output-directory]")

options = ExperimentOptions()
cases = development_cases()
rows = run_development(; cases, options)
summary = development_summary(rows, cases)
write_development_results(output_root, rows, summary; cases, options)
println(output_root)
