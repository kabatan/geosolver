using ExperimentDisc001
using GeoTargetCore

include(joinpath(@__DIR__, "src", "stagec_t0_inputs.jl"))
using .StageCT0Inputs

function main(arguments=ARGS)
    allowed = Set(("--execute", "--preflight-only"))
    all(argument -> argument in allowed, arguments) ||
        error("unknown Stage-C T0 materializer option")
    execute = "--execute" in arguments
    if !execute
        preflight = stagec_t0_materialization_preflight()
        println(GeoTargetCore.canonical_json(Dict(
            "authorized" => true,
            "batch_count" => STAGEC_T0_BATCH_COUNT,
            "batch_size" => STAGEC_T0_BATCH_SIZE,
            "case_count" => length(preflight.problems),
            "candidate_arms" => collect(STAGEC_T0_CANDIDATE_ARMS),
            "derived_control" => STAGEC_T0_DERIVED_CONTROL,
            "method" => ExperimentDisc001._METHOD_WIRE[STAGEC_T0_METHOD],
            "outcome_execution_authorized" => false,
            "proposal_file_count" => length(preflight.destinations),
        )))
        return nothing
    end
    document = materialize_stagec_t0_inputs()
    println(
        "input_manifest_sha256=",
        ExperimentDisc001._file_sha256(DEFAULT_STAGEC_T0_INPUT_MANIFEST_PATH),
    )
    println("proposal_count=", document["case_count"])
    return document
end

if abspath(PROGRAM_FILE) == abspath(@__FILE__())
    main()
end
