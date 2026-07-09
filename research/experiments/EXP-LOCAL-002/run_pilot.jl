const EXP_LOCAL_002_LOAD_START_NS = time_ns()

include(joinpath(@__DIR__, "src", "ExperimentLocal002.jl"))
using .ExperimentLocal002

const EXP_LOCAL_002_LOAD_COMPILE_SECONDS =
    (time_ns() - EXP_LOCAL_002_LOAD_START_NS) / 1.0e9

ExperimentLocal002.cli(ARGS; load_compile_seconds=EXP_LOCAL_002_LOAD_COMPILE_SECONDS)
