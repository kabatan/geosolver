using ExperimentDisc001
using GeoTargetCore

function main(arguments=ARGS)
    execute = "--execute" in arguments
    allowed = Set(("--execute", "--preflight-only"))
    all(argument -> argument in allowed, arguments) || error("unknown T0 materializer option")
    if !execute
        preflight = t0_materialization_preflight()
        println(GeoTargetCore.canonical_json(Dict(
            "authorized" => true,
            "case_count" => length(preflight.problems),
            "method_count" => length(ExperimentDisc001.T0_METHODS),
            "proposal_file_count" => length(preflight.destinations),
            "replicate_count" => ExperimentDisc001.T0_REPLICATE_COUNT,
        )))
        return nothing
    end
    document = materialize_t0_inputs()
    println("input_manifest_sha256=", ExperimentDisc001._file_sha256(
        ExperimentDisc001.DEFAULT_T0_INPUT_MANIFEST_PATH,
    ))
    println("proposal_count=", sum(length(case["proposals"]) for case in document["cases"]))
    return document
end

if abspath(PROGRAM_FILE) == abspath(@__FILE__())
    main()
end
