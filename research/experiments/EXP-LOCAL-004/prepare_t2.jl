using GeoTargetBenchmarks
using GeoTargetCore

const T2_PREPARE_REPOSITORY_ROOT = normpath(joinpath(@__DIR__, "..", "..", ".."))
const T2_PREPARE_EXP_LOCAL_002 = joinpath(
    T2_PREPARE_REPOSITORY_ROOT,
    "research",
    "experiments",
    "EXP-LOCAL-002",
)

include(joinpath(T2_PREPARE_EXP_LOCAL_002, "src", "ExperimentLocal002.jl"))
include(joinpath(T2_PREPARE_EXP_LOCAL_002, "src", "DevelopmentLocal002.jl"))
include(joinpath(@__DIR__, "src", "T2Corpus.jl"))
using .T2Corpus

function prepare_t2_main(arguments=ARGS)
    isempty(arguments) || throw(ArgumentError("prepare_t2.jl accepts no arguments"))
    problems = t2_problems()
    checksum = prepare_t2_input_manifest(T2_INPUT_MANIFEST_PATH; problems)
    println("wrote frozen T2 development input manifest: ", T2_INPUT_MANIFEST_PATH)
    println("sha256=", checksum)
    return checksum
end

if abspath(PROGRAM_FILE) == abspath(@__FILE__())
    prepare_t2_main()
end
