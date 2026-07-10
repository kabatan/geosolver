const EXP_LOCAL_002_ROUTING_LOAD_START_NS = time_ns()

include(joinpath(@__DIR__, "src", "ExperimentLocal002.jl"))
include(joinpath(@__DIR__, "src", "DevelopmentLocal002.jl"))
include(joinpath(@__DIR__, "src", "RoutingLocal002.jl"))

using .RoutingLocal002

const EXP_LOCAL_002_ROUTING_LOAD_COMPILE_SECONDS =
    (time_ns() - EXP_LOCAL_002_ROUTING_LOAD_START_NS) / 1.0e9

RoutingLocal002.worker_cli(
    ARGS;
    load_compile_seconds=EXP_LOCAL_002_ROUTING_LOAD_COMPILE_SECONDS,
)
