using ExperimentDisc001
using GeoTargetCore

include(joinpath(@__DIR__, "src", "stagea_corpus.jl"))
using .StageAInputs

function main(arguments=ARGS)
    execute = "--execute" in arguments
    allowed = Set(("--execute", "--preflight-only"))
    all(argument -> argument in allowed, arguments) ||
        error("unknown Stage-A materializer option")
    if !execute
        preflight = stagea_materialization_preflight()
        println(GeoTargetCore.canonical_json(Dict(
            "authorized" => true,
            "case_count" => length(preflight.problems),
            "method_count" => length(STAGEA_METHODS),
            "proposal_file_count" => length(preflight.destinations),
            "randomized_replicate_count" => STAGEA_REPLICATES,
        )))
        return nothing
    end
    document = materialize_stagea_inputs()
    println("input_manifest_sha256=", ExperimentDisc001._file_sha256(
        DEFAULT_STAGEA_INPUT_MANIFEST_PATH,
    ))
    println("proposal_count=", document["proposal_count"])
    return document
end

if abspath(PROGRAM_FILE) == abspath(@__FILE__())
    main()
end
