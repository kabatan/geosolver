include("SafetyJac003.jl")
using .SafetyJac003

length(ARGS) == 2 || error("usage: capture_safety.jl <candidate.json> <output.json>")
document = capture_safety(ARGS[1])
write_safety(ARGS[2], document)
