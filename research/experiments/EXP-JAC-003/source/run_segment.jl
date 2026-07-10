using JSON3

include("HarnessJac003.jl")
using .HarnessJac003

length(ARGS) == 3 || error(
    "usage: run_segment.jl <K0-DENSE-PUBLIC|K1-CACHED-ROUTED> <candidate.json> <output.json>",
)

variant, candidate_path, output_path = ARGS
document = run_segment(variant, candidate_path)
write_segment(output_path, document)
