include(joinpath(@__DIR__, "src", "ExperimentSingular001.jl"))

using .ExperimentSingular001
using JSON3
using SHA

const S4_RESULT_DIRECTORY = normpath(joinpath(
    @__DIR__,
    "..",
    "..",
    "results",
    "EXP-SINGULAR-001",
    "development-s4-v0",
))
const S4_CHECKPOINT_DIRECTORY = joinpath(S4_RESULT_DIRECTORY, "case-checkpoints")
const S4_INPUT_MANIFEST = joinpath(@__DIR__, "s4-development-input-manifest.json")
const S4_GOLD = joinpath(@__DIR__, "s4-development-gold.json")
const S4_IMPLEMENTATION_FREEZE = joinpath(@__DIR__, "s4-implementation-freeze.json")

_s4_sha(path) = bytes2hex(sha256(read(path)))

function _s4_repository_root()
    return realpath(joinpath(@__DIR__, "..", "..", ".."))
end

function _s4_verify_implementation_freeze()
    isfile(S4_IMPLEMENTATION_FREEZE) || error("missing S4 implementation freeze")
    freeze = JSON3.read(read(S4_IMPLEMENTATION_FREEZE, String))
    freeze.status == "frozen-before-first-development-outcome" ||
        error("S4 implementation freeze has wrong status")
    root = _s4_repository_root()
    for (relative, expected) in pairs(freeze.implementation_sources)
        path = normpath(joinpath(root, String(relative)))
        isfile(path) || error("missing frozen implementation source: $relative")
        _s4_sha(path) == String(expected) || error("S4 implementation hash mismatch: $relative")
    end
    _s4_sha(S4_INPUT_MANIFEST) == String(freeze.input_manifest_sha256) ||
        error("S4 input manifest hash mismatch")
    _s4_sha(S4_GOLD) == String(freeze.gold_artifact_sha256) ||
        error("S4 Gold artifact hash mismatch")
    return freeze
end

function _s4_verify_case_grid(cases)
    manifest = JSON3.read(read(S4_INPUT_MANIFEST, String))
    length(cases) == manifest.development_instance_count == 36 ||
        error("S4 case count mismatch")
    expected = Dict(String(item.id) => String(item.checksum) for item in manifest.cases)
    actual = Dict(
        case.generated.input.oracle.id => case.generated.checksum for case in cases
    )
    actual == expected || error("S4 generated case grid does not match frozen manifest")
    _s4_sha(S4_GOLD) == String(manifest.gold_artifact_sha256) ||
        error("S4 manifest does not bind Gold artifact")
    return manifest
end

function _s4_checkpoint_path(index, case)
    id = replace(case.generated.input.oracle.id, r"[^A-Za-z0-9_.-]" => "_")
    return joinpath(S4_CHECKPOINT_DIRECTORY, lpad(index, 3, '0') * "-" * id * ".json")
end

function _s4_checkpoint_document(case, index, rows, provenance)
    return Dict{String,Any}(
        "case_checksum" => case.generated.checksum,
        "case_id" => case.generated.input.oracle.id,
        "case_index" => index,
        "implementation_freeze_sha256" => provenance.implementation_freeze_sha256,
        "input_manifest_sha256" => provenance.input_manifest_sha256,
        "rows" => rows,
        "schema" => "geotarget.singular-s4-case-checkpoint/v1",
    )
end

function _s4_load_or_run_case!(case, index, provenance, s4_options, baseline_options)
    path = _s4_checkpoint_path(index, case)
    if isfile(path)
        checkpoint = JSON3.read(read(path, String), Dict{String,Any})
        checkpoint["schema"] == "geotarget.singular-s4-case-checkpoint/v1" ||
            error("invalid S4 checkpoint schema")
        checkpoint["case_id"] == case.generated.input.oracle.id ||
            error("S4 checkpoint case id mismatch")
        checkpoint["case_checksum"] == case.generated.checksum ||
            error("S4 checkpoint case checksum mismatch")
        checkpoint["case_index"] == index || error("S4 checkpoint index mismatch")
        checkpoint["implementation_freeze_sha256"] ==
            provenance.implementation_freeze_sha256 ||
            error("S4 checkpoint implementation mismatch")
        checkpoint["input_manifest_sha256"] == provenance.input_manifest_sha256 ||
            error("S4 checkpoint input mismatch")
        rows = checkpoint["rows"]
        length(rows) == 3 || error("S4 checkpoint row count mismatch")
        return Any[rows...]
    end
    rows = ExperimentSingular001._run_s4_development_case(
        case,
        3 * (index - 1) + 1;
        s4_options,
        baseline_options,
        clock_ns=time_ns,
    )
    ExperimentSingular001.write_json_artifact(
        path,
        _s4_checkpoint_document(case, index, rows, provenance),
    )
    return rows
end

function main()
    isfile(joinpath(S4_RESULT_DIRECTORY, "result-bindings.json")) &&
        error("refusing to rerun completed S4 development archive")
    freeze = _s4_verify_implementation_freeze()
    cases = ExperimentSingular001.s4_development_cases()
    _s4_verify_case_grid(cases)
    mkpath(S4_CHECKPOINT_DIRECTORY)
    s4_options = ExperimentOptions(
        precision_ladder=(128, 256),
        semantic_precision_bits=256,
    )
    baseline_options = ExperimentOptions()
    provenance = (
        implementation_freeze_sha256=_s4_sha(S4_IMPLEMENTATION_FREEZE),
        input_manifest_sha256=_s4_sha(S4_INPUT_MANIFEST),
    )
    rows = Any[]
    for (index, case) in enumerate(cases)
        append!(rows, _s4_load_or_run_case!(
            case,
            index,
            provenance,
            s4_options,
            baseline_options,
        ))
    end
    length(rows) == 108 || error("S4 raw row grid is incomplete")
    summary = ExperimentSingular001.s4_development_summary(
        rows;
        s4_options,
        baseline_options,
    )
    bindings = ExperimentSingular001.write_s4_development_results(
        S4_RESULT_DIRECTORY,
        rows,
        summary;
        input_manifest_path=S4_INPUT_MANIFEST,
        implementation_freeze_path=S4_IMPLEMENTATION_FREEZE,
        s4_options,
        baseline_options,
    )
    ExperimentSingular001.write_json_artifact(
        joinpath(S4_RESULT_DIRECTORY, "result-bindings.json"),
        Dict{String,Any}(
            "bindings" => bindings,
            "implementation_freeze_sha256" => provenance.implementation_freeze_sha256,
            "input_manifest_sha256" => provenance.input_manifest_sha256,
            "product_connected" => false,
            "schema" => "geotarget.singular-s4-result-bindings/v1",
        ),
    )
    return nothing
end

abspath(PROGRAM_FILE) == @__FILE__ && main()
