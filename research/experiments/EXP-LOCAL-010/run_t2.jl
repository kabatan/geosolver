using SHA

include(joinpath(@__DIR__, "run_t0.jl"))

const T2_EXP_LOCAL_002 = joinpath(REPOSITORY_ROOT, "research", "experiments", "EXP-LOCAL-002")
const T2_EXP_LOCAL_004 = joinpath(REPOSITORY_ROOT, "research", "experiments", "EXP-LOCAL-004")
const T2_PREREGISTRATION = joinpath(@__DIR__, "t2-preregistration.json")
const T2_INPUT_MANIFEST = joinpath(T2_EXP_LOCAL_004, "t2-input-manifest.json")
const T2_T0_SUMMARY = joinpath(
    REPOSITORY_ROOT,
    "benchmarks",
    "results",
    "raw",
    "exp-local-010-011-t0-summary.json",
)
const T2_EXPECTED_MANIFEST_SHA256 =
    "aa5da6b9655ebe97f5ae8832911cc253301cb64916e0f23f5637b645905bcd81"
const T2_EXPECTED_T0_SUMMARY_SHA256 =
    "03fb1dd3937a9fc8b88583738316d6035b455b89bdfb0dec1da95b233b3bb334"
const T2_EXPECTED_T0_REVISION = "24df0d8c0eac23f72e51f9dd8029d6b8ef6488a0"
const T2_EXPECTED_CPQR_SHA256 =
    "7be8b04852371b7b7846713b3f6066324c84c9bfcef1ec82ceb5a677e7b29950"
const T2_EXPECTED_SVD_SHA256 =
    "ea7ee7ba89a1b012f53614b2b94aa79e1ecdb2d6225dc0669210c27e73e9cbdc"
const T2_EXPECTED_T0_PREREG_SHA256 =
    "79bf4645625b2bbaee84d085f256e45f9528a6d97a68c8fdcd9a162df2e9fd87"
const T2_EXPECTED_SVD_PREREG_SHA256 =
    "38beb6ec513d0dcac2f5ce4442d17a3e4c691988c6662557480d43000f1b6f33"

include(joinpath(T2_EXP_LOCAL_002, "src", "ExperimentLocal002.jl"))
include(joinpath(T2_EXP_LOCAL_002, "src", "DevelopmentLocal002.jl"))
include(joinpath(T2_EXP_LOCAL_004, "src", "T2Corpus.jl"))

_sha256(path) = bytes2hex(sha256(read(path)))

function _artifact_sha(problem, name::Symbol)
    matches = filter(artifact -> artifact.name === name, problem.artifacts)
    length(matches) == 1 || error("$(problem.instance_id) lacks one $name artifact")
    return only(matches).sha256
end

function _validate_active_project()
    expected = normpath(joinpath(T2_EXP_LOCAL_002, "Project.toml"))
    observed = Base.active_project()
    observed !== nothing && normpath(observed) == expected || error(
        "T2 requires --project=research/experiments/EXP-LOCAL-002",
    )
    return relpath(expected, REPOSITORY_ROOT)
end

function _validate_t0_evidence()
    _sha256(T2_T0_SUMMARY) == T2_EXPECTED_T0_SUMMARY_SHA256 ||
        error("T0 summary hash drifted")
    summary = JSON3.read(read(T2_T0_SUMMARY, String), Dict{String,Any})
    summary["revision"] == T2_EXPECTED_T0_REVISION || error("T0 revision drifted")
    for candidate in ("E1-FD2-CPQR3", "E2-FD2-SVD3")
        summary["candidate_gates"][candidate]["passes_t0"] == true ||
            error("$candidate did not pass the bound T0 result")
    end
    _sha256(joinpath(@__DIR__, "src", "ExperimentLocal010.jl")) ==
        T2_EXPECTED_CPQR_SHA256 || error("CPQR candidate changed after T0")
    _sha256(joinpath(@__DIR__, "..", "EXP-LOCAL-011", "src", "ExperimentLocal011.jl")) ==
        T2_EXPECTED_SVD_SHA256 || error("SVD candidate changed after T0")
    return true
end

function _validate_t0_preregistrations()
    paths = (
        (joinpath(@__DIR__, "preregistration.json"), T2_EXPECTED_T0_PREREG_SHA256),
        (
            joinpath(@__DIR__, "..", "EXP-LOCAL-011", "preregistration.json"),
            T2_EXPECTED_SVD_PREREG_SHA256,
        ),
    )
    for (path, expected_sha) in paths
        _sha256(path) == expected_sha || error("T0 preregistration hash drifted: $path")
        document = JSON3.read(read(path, String), Dict{String,Any})
        document["outcome_execution_authorized"] == true ||
            error("T0 preregistration is not outcome-authorized: $path")
    end
    return true
end

function _validate_t2_corpus()
    _sha256(T2_INPUT_MANIFEST) == T2_EXPECTED_MANIFEST_SHA256 ||
        error("committed T2 input manifest hash drifted")
    manifest = JSON3.read(read(T2_INPUT_MANIFEST, String), Dict{String,Any})
    problems = T2Corpus.t2_problems()
    T2Corpus.validate_t2_grid(problems)
    length(problems) == 48 || error("T2 must contain 48 cases")
    length(manifest["instances"]) == length(problems) || error("T2 manifest case count drifted")
    sum(length(problem.gold_targets) for problem in problems) == 88 ||
        error("T2 target count drifted")
    for (index, problem) in enumerate(problems)
        expected = manifest["instances"][index]
        problem.instance_id == expected["instance_id"] || error("instance $index ID drifted")
        problem.family_id == expected["family_id"] || error("instance $index family drifted")
        replay_checksum(problem) == expected["replay_checksum"] ||
            error("instance $index replay checksum drifted")
        length(problem.gold_targets) == expected["target_count"] ||
            error("instance $index target count drifted")
        _artifact_sha(problem, :gold_targets) == expected["artifact_checksums"]["gold_targets"] ||
            error("instance $index target checksum drifted")
        _artifact_sha(problem, :gold_configurations) == expected["gold_configurations_checksum"] ||
            error("instance $index Gold configuration checksum drifted")
        _artifact_sha(problem, :saved_starts) == expected["saved_starts_checksum"] ||
            error("instance $index saved-start checksum drifted")
        collect(size(problem.saved_starts)) == expected["saved_starts_shape"] ==
            [problem.dimension, 32] || error("instance $index saved-start shape drifted")
    end
    return problems, manifest
end

function t2_preflight_document()
    active_project = _validate_active_project()
    _validate_t0_evidence()
    _validate_t0_preregistrations()
    problems, manifest = _validate_t2_corpus()
    selected_variants = variants()
    return Dict{String,Any}(
        "active_project" => active_project,
        "case_count" => length(problems),
        "family_counts" => manifest["family_counts"],
        "input_manifest_sha256" => _sha256(T2_INPUT_MANIFEST),
        "maximum_starts" => 32,
        "schema" => "geotarget.local-correction-t2-preflight/v1",
        "t0_revision" => T2_EXPECTED_T0_REVISION,
        "t0_summary_sha256" => _sha256(T2_T0_SUMMARY),
        "target_count" => sum(length(problem.gold_targets) for problem in problems),
        "thread_contract" => _thread_contract(),
        "variants" => [variant.name for variant in selected_variants],
    )
end

function _t2_authorized()
    document = JSON3.read(read(T2_PREREGISTRATION, String), Dict{String,Any})
    return document["outcome_execution_authorized"] == true
end

function run_t2_case(case_index::Integer)
    revision = _git_revision()
    revision["git_dirty"] && error("T2 outcome execution requires a clean committed tree")
    preflight = t2_preflight_document()
    problems, _ = _validate_t2_corpus()
    1 <= case_index <= length(problems) || error("case index must be in 1:48")
    problem = problems[Int(case_index)]
    selected_variants = variants()
    document = Dict{String,Any}(
        "attempts" => Any[],
        "case_count" => length(problems),
        "case_index" => Int(case_index),
        "environment" => preflight["thread_contract"],
        "experiment_id" => "EXP-LOCAL-010-011-T2",
        "generated_at_utc" => Dates.format(now(UTC), dateformat"yyyy-mm-ddTHH:MM:SS.sssZ"),
        "input_manifest" => Dict(
            "path" => relpath(T2_INPUT_MANIFEST, REPOSITORY_ROOT),
            "sha256" => T2_EXPECTED_MANIFEST_SHA256,
        ),
        "locked_validation" => false,
        "partition" => "development",
        "prefix_policy" => "snapshot-after-first-completed-attempt-crossing-threshold",
        "problem_manifest" => Any[Dict(
            "family_id" => problem.family_id,
            "instance_id" => problem.instance_id,
            "replay_checksum" => replay_checksum(problem),
            "saved_starts_checksum" => _artifact_sha(problem, :saved_starts),
            "targets" => length(problem.gold_targets),
        )],
        "revision" => revision,
        "schema" => "geotarget.local-correction-campaign/v1",
        "suite" => "t2",
        "t0_evidence" => Dict(
            "revision" => T2_EXPECTED_T0_REVISION,
            "summary_sha256" => T2_EXPECTED_T0_SUMMARY_SHA256,
        ),
        "terminals" => Any[],
        "threshold_snapshots" => Any[],
        "variant_manifest" => Any[
            Dict(
                "configuration" => Dict(
                    String(key) => value for (key, value) in pairs(variant.configuration)
                ),
                "name" => variant.name,
            ) for variant in selected_variants
        ],
    )
    for variant in selected_variants
        attempts, snapshots, terminal = _run_case(variant, problem; maximum_starts=32)
        append!(
            document["attempts"],
            (GeoTargetBenchmarks._attempt_document(attempt) for attempt in attempts),
        )
        append!(document["threshold_snapshots"], snapshots)
        push!(document["terminals"], terminal)
    end
    return document
end

function run_t2_main(arguments=ARGS)
    execute = "--execute" in arguments
    case_argument = findfirst(argument -> startswith(argument, "--case-index="), arguments)
    case_index = case_argument === nothing ? nothing : tryparse(
        Int,
        arguments[case_argument][length("--case-index=") + 1:end],
    )
    output_argument = findfirst(argument -> startswith(argument, "--output="), arguments)
    output = output_argument === nothing ? joinpath(
        REPOSITORY_ROOT,
        "benchmarks",
        "results",
        "raw",
        case_index === nothing ?
        "exp-local-010-011-t2-preflight.json" :
        "exp-local-010-011-t2-case-$(lpad(case_index, 2, '0')).json",
    ) : abspath(arguments[output_argument][length("--output=") + 1:end])
    allowed = argument -> argument == "--execute" || startswith(argument, "--case-index=") ||
        startswith(argument, "--output=")
    all(allowed, arguments) || error("unknown T2 runner option")
    if !execute
        println(JSON3.write(t2_preflight_document()))
        return nothing
    end
    _t2_authorized() || error("T2 outcome execution is not authorized")
    case_index !== nothing || error("--case-index=1..48 is required for T2 outcome execution")
    document = run_t2_case(case_index)
    mkpath(dirname(output))
    write(output, JSON3.write(document), '\n')
    println("output=$output")
    return document
end

if abspath(PROGRAM_FILE) == abspath(@__FILE__())
    run_t2_main()
end
