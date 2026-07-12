using ExperimentDisc001
using GeoTargetCore

include(joinpath(@__DIR__, "src", "stageb_t0_inputs.jl"))
using .StageBT0Inputs

function main(arguments=ARGS)
    allowed = Set(("--execute", "--preflight-only"))
    all(argument -> argument in allowed, arguments) ||
        error("unknown Stage-B T0 materializer option")
    execute = "--execute" in arguments
    if !execute
        preflight = stageb_t0_materialization_preflight()
        println(GeoTargetCore.canonical_json(Dict(
            "authorized" => true,
            "case_count" => length(preflight.problems),
            "initial_prefix_columns" => [1, STAGEB_T0_INITIAL_PREFIX],
            "continuation_columns" => [
                first(STAGEB_T0_CONTINUATION),
                last(STAGEB_T0_CONTINUATION),
            ],
            "method" => ExperimentDisc001._METHOD_WIRE[STAGEB_T0_METHOD],
            "outcome_execution_authorized" => false,
            "proposal_file_count" => length(preflight.destinations),
        )))
        return nothing
    end
    document = materialize_stageb_t0_inputs()
    println(
        "input_manifest_sha256=",
        ExperimentDisc001._file_sha256(DEFAULT_STAGEB_T0_INPUT_MANIFEST_PATH),
    )
    println("proposal_count=", document["proposal_count"])
    return document
end

if abspath(PROGRAM_FILE) == abspath(@__FILE__())
    main()
end
