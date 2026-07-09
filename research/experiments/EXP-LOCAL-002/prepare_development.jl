include(joinpath(@__DIR__, "src", "ExperimentLocal002.jl"))
include(joinpath(@__DIR__, "src", "DevelopmentLocal002.jl"))

using .DevelopmentLocal002

path = DevelopmentLocal002.write_development_input_manifest()
println("wrote frozen development input manifest to ", path)
