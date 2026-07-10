include(joinpath(@__DIR__, "src", "ExperimentSingular001.jl"))
using .ExperimentSingular001

const OUTPUT_PATH = joinpath(@__DIR__, "s2-development-input-manifest.json")

document = s2_development_input_document()
write_json_artifact(OUTPUT_PATH, document)
println(OUTPUT_PATH)
