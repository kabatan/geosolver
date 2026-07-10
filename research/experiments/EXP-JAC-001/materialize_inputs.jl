include(joinpath(@__DIR__, "src", "ExperimentJac001.jl"))

using .ExperimentJac001

length(ARGS) == 2 || error("usage: materialize_inputs.jl <development|locked> <output.json>")
partition = Symbol(ARGS[1])
write_materialized_inputs(ARGS[2], partition)
document = load_materialized_inputs(ARGS[2])
validate_materialized_inputs(document)
println("materialized ", document["instance_count"], " ", partition, " instances")
