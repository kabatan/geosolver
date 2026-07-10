include(joinpath(@__DIR__, "src", "ExperimentJac001.jl"))
include(joinpath(@__DIR__, "src", "RunJac001.jl"))

using .RunJac001

length(ARGS) == 3 || error(
    "usage: run_variant.jl <input.json> <output.json> <variant>",
)
result = run_variant(ARGS[1], ARGS[2], ARGS[3])
println(
    "completed ",
    result["variant"],
    " with ",
    length(result["attempts"]),
    " paired attempts",
)
