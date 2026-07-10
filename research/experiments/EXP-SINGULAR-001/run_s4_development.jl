include(joinpath(@__DIR__, "src", "ExperimentSingular001.jl"))

using .ExperimentSingular001
using JSON3
using LinearAlgebra
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
const S4_PROJECT = joinpath(@__DIR__, "Project.toml")
const S4_MANIFEST = joinpath(@__DIR__, "Manifest.toml")
const S4_RUN_IDENTITY = joinpath(S4_RESULT_DIRECTORY, "run-identity.json")
const S4_WARMUP_ARTIFACT = joinpath(S4_RESULT_DIRECTORY, "warmup.json")
const S4_CHECKPOINT_MANIFEST = joinpath(S4_RESULT_DIRECTORY, "checkpoint-manifest.json")

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

function _s4_runtime_identity(freeze, s4_options, baseline_options)
    VERSION == v"1.12.6" || error("S4 requires Julia 1.12.6 exactly")
    Threads.nthreads() == 1 || error("S4 requires exactly one Julia thread")
    BLAS.set_num_threads(1)
    BLAS.get_num_threads() == 1 || error("S4 requires exactly one BLAS thread")
    return Dict{String,Any}(
        "baseline_options" => ExperimentSingular001._s4_options_document(
            baseline_options,
        ),
        "blas_threads" => BLAS.get_num_threads(),
        "implementation_freeze_sha256" => _s4_sha(S4_IMPLEMENTATION_FREEZE),
        "input_manifest_sha256" => _s4_sha(S4_INPUT_MANIFEST),
        "julia_threads" => Threads.nthreads(),
        "julia_version" => string(VERSION),
        "manifest_sha256" => _s4_sha(S4_MANIFEST),
        "project_sha256" => _s4_sha(S4_PROJECT),
        "runner_sha256" => _s4_sha(@__FILE__),
        "s4_options" => ExperimentSingular001._s4_options_document(s4_options),
        "schema" => "geotarget.singular-s4-run-identity/v1",
        "source_commit" => String(freeze.source_commit),
    )
end

function _s4_same_document(left, right)
    normalized_left = JSON3.read(JSON3.write(left), Dict{String,Any})
    normalized_right = JSON3.read(JSON3.write(right), Dict{String,Any})
    return normalized_left == normalized_right
end

function _s4_prepare_run_identity!(identity)
    mkpath(S4_RESULT_DIRECTORY)
    allowed = Set(("run-identity.json", "warmup.json", "case-checkpoints"))
    unexpected = String[
        entry for entry in readdir(S4_RESULT_DIRECTORY; join=false) if
        !(entry in allowed)
    ]
    isempty(unexpected) || error("unexpected partial S4 result artifacts: $unexpected")
    if isfile(S4_RUN_IDENTITY)
        existing = JSON3.read(read(S4_RUN_IDENTITY, String), Dict{String,Any})
        _s4_same_document(existing, identity) || error("S4 run identity mismatch")
    else
        ExperimentSingular001.write_json_artifact(S4_RUN_IDENTITY, identity)
    end
    return _s4_sha(S4_RUN_IDENTITY)
end

function _s4_run_or_verify_warmup!(s4_options, baseline_options)
    document = ExperimentSingular001._run_s4_family_disjoint_warmup!(
        s4_options,
        baseline_options;
        clock_ns=time_ns,
    )
    if isfile(S4_WARMUP_ARTIFACT)
        existing = JSON3.read(read(S4_WARMUP_ARTIFACT, String), Dict{String,Any})
        _s4_same_document(existing, document) || error("S4 warm-up replay mismatch")
    else
        ExperimentSingular001.write_json_artifact(S4_WARMUP_ARTIFACT, document)
    end
    return _s4_sha(S4_WARMUP_ARTIFACT)
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

function _s4_checkpoint_document(case, index, rows, provenance, variant_order)
    return Dict{String,Any}(
        "case_checksum" => case.generated.checksum,
        "case_id" => case.generated.input.oracle.id,
        "case_index" => index,
        "implementation_freeze_sha256" => provenance.implementation_freeze_sha256,
        "input_manifest_sha256" => provenance.input_manifest_sha256,
        "run_identity_sha256" => provenance.run_identity_sha256,
        "rows" => rows,
        "schema" => "geotarget.singular-s4-case-checkpoint/v1",
        "variant_order" => collect(variant_order),
        "warmup_sha256" => provenance.warmup_sha256,
    )
end

function _s4_load_or_run_case!(case, index, provenance, s4_options, baseline_options)
    path = _s4_checkpoint_path(index, case)
    variant_order = ExperimentSingular001._s4_counterbalanced_variant_order(index)
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
        checkpoint["run_identity_sha256"] == provenance.run_identity_sha256 ||
            error("S4 checkpoint runtime mismatch")
        checkpoint["warmup_sha256"] == provenance.warmup_sha256 ||
            error("S4 checkpoint warm-up mismatch")
        Tuple(String(value) for value in checkpoint["variant_order"]) == variant_order ||
            error("S4 checkpoint variant-order mismatch")
        rows = checkpoint["rows"]
        length(rows) == 3 || error("S4 checkpoint row count mismatch")
        Tuple(String(row["variant"]) for row in rows) == variant_order ||
            error("S4 checkpoint row-order mismatch")
        Tuple(Int(row["execution_index"]) for row in rows) ==
            Tuple((3 * (index - 1) + 1):(3 * index)) ||
            error("S4 checkpoint execution-index mismatch")
        all(row -> row["case_id"] == case.generated.input.oracle.id, rows) ||
            error("S4 checkpoint row case mismatch")
        all(row -> row["case_checksum"] == case.generated.checksum, rows) ||
            error("S4 checkpoint row checksum mismatch")
        return Any[rows...]
    end
    rows = ExperimentSingular001._run_s4_development_case(
        case,
        3 * (index - 1) + 1;
        s4_options,
        baseline_options,
        clock_ns=time_ns,
        variant_order,
    )
    ExperimentSingular001.write_json_artifact(
        path,
        _s4_checkpoint_document(case, index, rows, provenance, variant_order),
    )
    return rows
end

function _s4_write_checkpoint_manifest!(cases, provenance)
    paths = sort!(filter(
        path -> endswith(path, ".json"),
        readdir(S4_CHECKPOINT_DIRECTORY; join=true),
    ))
    length(paths) == length(cases) == 36 || error("S4 checkpoint set is incomplete")
    entries = Any[]
    for (index, (case, path)) in enumerate(zip(cases, paths))
        checkpoint = JSON3.read(read(path, String))
        Int(checkpoint.case_index) == index || error("S4 checkpoint manifest index mismatch")
        String(checkpoint.case_id) == case.generated.input.oracle.id ||
            error("S4 checkpoint manifest case mismatch")
        push!(entries, Dict{String,Any}(
            "case_checksum" => case.generated.checksum,
            "case_id" => case.generated.input.oracle.id,
            "case_index" => index,
            "path" => replace(relpath(path, S4_RESULT_DIRECTORY), '\\' => '/'),
            "sha256" => _s4_sha(path),
            "variant_order" => collect(
                ExperimentSingular001._s4_counterbalanced_variant_order(index),
            ),
        ))
    end
    document = Dict{String,Any}(
        "checkpoints" => entries,
        "implementation_freeze_sha256" => provenance.implementation_freeze_sha256,
        "input_manifest_sha256" => provenance.input_manifest_sha256,
        "row_count" => 108,
        "run_identity_sha256" => provenance.run_identity_sha256,
        "schema" => "geotarget.singular-s4-checkpoint-manifest/v1",
        "warmup_sha256" => provenance.warmup_sha256,
    )
    ExperimentSingular001.write_json_artifact(S4_CHECKPOINT_MANIFEST, document)
    return _s4_sha(S4_CHECKPOINT_MANIFEST)
end

function main()
    isfile(joinpath(S4_RESULT_DIRECTORY, "result-bindings.json")) &&
        error("refusing to rerun completed S4 development archive")
    freeze = _s4_verify_implementation_freeze()
    s4_options = ExperimentOptions(
        precision_ladder=(128, 256),
        semantic_precision_bits=256,
    )
    baseline_options = ExperimentOptions()
    identity = _s4_runtime_identity(freeze, s4_options, baseline_options)
    run_identity_sha256 = _s4_prepare_run_identity!(identity)
    warmup_sha256 = _s4_run_or_verify_warmup!(s4_options, baseline_options)
    cases = ExperimentSingular001.s4_development_cases()
    _s4_verify_case_grid(cases)
    mkpath(S4_CHECKPOINT_DIRECTORY)
    provenance = (
        implementation_freeze_sha256=_s4_sha(S4_IMPLEMENTATION_FREEZE),
        input_manifest_sha256=_s4_sha(S4_INPUT_MANIFEST),
        run_identity_sha256=run_identity_sha256,
        warmup_sha256=warmup_sha256,
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
    checkpoint_manifest_sha256 = _s4_write_checkpoint_manifest!(cases, provenance)
    summary = ExperimentSingular001.s4_development_summary(
        rows;
        s4_options,
        baseline_options,
        checkpoint_manifest_sha256,
        run_identity_sha256,
        warmup_sha256,
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
            "checkpoint_manifest_sha256" => checkpoint_manifest_sha256,
            "product_connected" => false,
            "run_identity_sha256" => run_identity_sha256,
            "schema" => "geotarget.singular-s4-result-bindings/v1",
            "warmup_sha256" => warmup_sha256,
        ),
    )
    return nothing
end

abspath(PROGRAM_FILE) == @__FILE__ && main()
