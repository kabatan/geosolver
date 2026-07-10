include(joinpath(@__DIR__, "src", "ExperimentSingular001.jl"))
using .ExperimentSingular001

const REPO_ROOT = normpath(joinpath(@__DIR__, "..", "..", ".."))
const DEFAULT_OUTPUT = joinpath(
    REPO_ROOT,
    "research",
    "results",
    EXPERIMENT_ID,
    "development-s2-v0",
)

output_root = isempty(ARGS) ? DEFAULT_OUTPUT : abspath(first(ARGS))
length(ARGS) <= 1 || error("usage: run_s2_development.jl [output-directory]")

options = ExperimentOptions()
cases = s2_development_cases()
rows = run_s2_development(; cases, options)
summary = s2_development_summary(rows, cases; options)
write_s2_development_results(output_root, rows, summary; options)
println(output_root)
