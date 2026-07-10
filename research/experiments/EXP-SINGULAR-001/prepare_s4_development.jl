include(joinpath(@__DIR__, "src", "ExperimentSingular001.jl"))

using SHA

const S4 = ExperimentSingular001
const DESTINATION = joinpath(@__DIR__, "s4-development-input-manifest.json")
const GOLD_DESTINATION = joinpath(@__DIR__, "s4-development-gold.json")

S4._assert_s4_preimplementation_state()
isfile(DESTINATION) && error("refusing to overwrite frozen S4 input manifest")
isfile(GOLD_DESTINATION) && error("refusing to overwrite frozen S4 Gold artifact")
cases = S4.s4_development_cases()
gold_document = S4.s4_development_gold_document(cases)
try
    S4.write_json_artifact(GOLD_DESTINATION, gold_document)
    gold_sha256 = bytes2hex(sha256(read(GOLD_DESTINATION)))
    document = S4.s4_development_input_document(
        cases;
        gold_artifact_sha256=gold_sha256,
    )
    S4.write_json_artifact(DESTINATION, document)
catch
    isfile(DESTINATION) || rm(GOLD_DESTINATION; force=true)
    rethrow()
end
