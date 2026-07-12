using ExperimentDisc001
using GeoTargetBase
using GeoTargetBenchmarks
using GeoTargetCore
using JSON3
using LinearAlgebra
using SHA

const T0O_ROOT = ExperimentDisc001.EXPERIMENT_ROOT
const T0O_REPO = ExperimentDisc001.REPOSITORY_ROOT
const T0O_RUNNER = @__FILE__
const T0O_INPUT = joinpath(T0O_ROOT, "t0-input-manifest.json")
const T0O_AUTH = joinpath(T0O_ROOT, "t0-outcome-authorization.json")
const T0O_AGGREGATOR = joinpath(T0O_ROOT, "aggregate_t0.py")
const T0O_PREFIXES = (8, 16, 32, 64, 128)
const T0O_THRESHOLDS = (600, 1_200, 2_400, 4_800)
const T0O_METHODS = (
    "D0-IID-ALL",
    "D1-SOBOL-ALL",
    "D-HALTON-ALL",
    "D-CURRENT-COUNTER-HALTON-MIX",
    "D2O-RQMC-OWEN-ALL",
    "D2M-RQMC-MATOUSEK-ALL",
    "D3-OWEN-MIXED-25IID-75RQMC",
)
const T0O_METHOD_ENUM = Dict(
    T0O_METHODS[1] => D0_IID_ALL,
    T0O_METHODS[2] => D1_SOBOL_ALL,
    T0O_METHODS[3] => D_HALTON_ALL,
    T0O_METHODS[4] => D_CURRENT_COUNTER_HALTON,
    T0O_METHODS[5] => D2O_OWEN_ALL,
    T0O_METHODS[6] => D2M_MATOUSEK_ALL,
    T0O_METHODS[7] => D3_OWEN_MIXED,
)

include(joinpath(T0O_ROOT, "..", "EXP-LOCAL-010", "src", "ExperimentLocal010.jl"))
include(joinpath(T0O_ROOT, "..", "EXP-LOCAL-013", "src", "ExperimentLocal013.jl"))

sha256_file(path) = bytes2hex(sha256(read(path)))
sha256_text(value) = value isa AbstractString && occursin(r"^[0-9a-f]{64}$", value)

function repo_path(relative)
    relative isa AbstractString && !isempty(relative) && !isabspath(relative) ||
        error("repository path must be nonempty and relative")
    result = normpath(joinpath(T0O_REPO, split(String(relative), '/')...))
    escaped = relpath(result, T0O_REPO)
    (escaped == ".." || startswith(escaped, "../")) && error("path escapes repository")
    return result
end

repo_relative(path) = replace(relpath(abspath(path), T0O_REPO), '\\' => '/')

function committed(path, label)
    relative = repo_relative(path)
    success(`git -C $T0O_REPO ls-files --error-unmatch -- $relative`) ||
        error("$label is not committed")
    success(`git -C $T0O_REPO diff --quiet -- $relative`) || error("$label has byte drift")
    success(`git -C $T0O_REPO diff --cached --quiet -- $relative`) ||
        error("$label has staged drift")
    return relative
end

function json_document(path, label)
    isfile(path) || error("$label is absent: $path")
    try
        return JSON3.read(read(path, String), Dict{String,Any})
    catch exception
        error("$label is invalid JSON: $(sprint(showerror, exception))")
    end
end

function active_project()
    expected = normpath(joinpath(T0O_ROOT, "Project.toml"))
    observed = Base.active_project()
    observed !== nothing && normpath(observed) == expected ||
        error("run with --project=research/experiments/EXP-DISC-001")
    return repo_relative(expected)
end

function thread_contract()
    Threads.nthreads() == 1 || error("JULIA_NUM_THREADS=1 is required")
    BLAS.get_num_threads() == 1 || error("one BLAS thread is required")
    env = Dict(name => get(ENV, name, "unset") for name in
        ("JULIA_NUM_THREADS", "OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"))
    all(get(env, name, "unset") == "1" for name in
        ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS")) ||
        error("OPENBLAS/OMP/MKL thread counts must all be one")
    return Dict("julia_threads" => 1, "blas_threads" => 1, "environment" => env)
end

function execution_host(case_index, cpu)
    0 <= cpu <= 15 && cpu == (case_index - 1) % 16 || error("case/CPU assignment drifted")
    get(ENV, "GEOTARGET_CASE_PROCESS_LIMIT", "unset") == "16" ||
        error("GEOTARGET_CASE_PROCESS_LIMIT=16 is required")
    matched = match(r"(?m)^Cpus_allowed_list:\s*(.+)$", read("/proc/self/status", String))
    matched !== nothing || error("cannot inspect CPU affinity")
    allowed = strip(matched.captures[1])
    allowed == string(cpu) && ccall(:sched_getcpu, Cint, ()) == cpu ||
        error("process must be pinned to CPU $cpu")
    return Dict(
        "assigned_cpu" => cpu,
        "case_process_limit" => 16,
        "cpus_allowed_list" => allowed,
        "solver_worker_count" => 1,
    )
end

function acquire_cpu(cpu)
    io = open("/tmp/geotarget-exp-disc-001-cpu-$cpu.lock", "w")
    ccall(:flock, Cint, (Cint, Cint), fd(io), 2 | 4) == 0 ||
        (close(io); error("CPU $cpu already has a case process"))
    return io
end

function local_variant(freeze)
    selected = freeze["selected_local_solver"]
    selected["id"] == ExperimentLocal013.CANDIDATE_NAME || error("local finalist drifted")
    for relative in (
        "research/experiments/EXP-LOCAL-010/src/ExperimentLocal010.jl",
        "research/experiments/EXP-LOCAL-013/src/ExperimentLocal013.jl",
    )
        sha256_file(repo_path(relative)) == selected["source_sha256"][relative] ||
            error("frozen local source drifted")
    end
    e1 = ExperimentLocal010.endpoint_correction_variant(; shadow=false)
    e4 = ExperimentLocal013.guard_slack_variant(e1; shadow=false)
    e4.configuration.callback_cap == 600 && e4.configuration.guardless_fallback == e1.name ||
        error("constructed E4 policy drifted")
    return e4
end


function load_inputs(path; artifacts=true)
    committed(path, "T0 input manifest")
    document = json_document(path, "T0 input manifest")
    get(document, "schema_version", nothing) == "geotarget.discovery-t0-input/v1" ||
        error("input schema drifted")
    get(document, "experiment_id", nothing) == "EXP-DISC-001" || error("experiment drifted")
    get(document, "stage", nothing) == "t0" && get(document, "partition", nothing) == "development" ||
        error("input crossed the T0 development boundary")
    get(document, "lab_confirmation_512_768", true) === false ||
        error("DirectAnalytic T0 cannot claim 512/768 confirmation")
    Tuple(String.(get(document, "methods", Any[]))) == T0O_METHODS || error("method order drifted")
    Tuple(Int.(get(document, "prefixes", Any[]))) == T0O_PREFIXES || error("prefixes drifted")
    Tuple(Int.(get(document, "callback_thresholds", Any[]))) == T0O_THRESHOLDS ||
        error("callback thresholds drifted")
    get(document, "attempt_evaluation_limit", nothing) == 600 || error("attempt cap drifted")
    parse(UInt64, String(get(document, "root_seed", ""))) == ExperimentDisc001.T0_ROOT_SEED ||
        error("T0 root seed drifted")
    get(document, "replicate_count", nothing) == ExperimentDisc001.T0_REPLICATE_COUNT == 1 ||
        error("T0 replicate count drifted")
    get(document, "case_count", nothing) == 6 && get(document, "target_count", nothing) == 17 ||
        error("T0 size drifted")

    source_manifests = get(document, "source_manifests", nothing)
    source_manifests isa AbstractVector && !isempty(source_manifests) ||
        error("source manifest bindings are absent")
    for binding in source_manifests
        source_path = repo_path(binding["path"])
        committed(source_path, "T0 source manifest")
        sha256_text(binding["sha256"]) && sha256_file(source_path) == binding["sha256"] ||
            error("T0 source manifest hash drifted")
    end

    freeze_binding = document["local_freeze"]
    freeze_path = repo_path(freeze_binding["path"])
    committed(freeze_path, "local freeze")
    freeze_sha = freeze_binding["sha256"]
    sha256_text(freeze_sha) && sha256_file(freeze_path) == freeze_sha || error("freeze hash drifted")
    authority = materialization_preflight(freeze_path)
    authority.freeze_sha256 == freeze_sha || error("freeze authority drifted")
    freeze = json_document(freeze_path, "local freeze")

    prereg = document["preregistration"]
    prereg_path = repo_path(prereg["path"])
    committed(prereg_path, "T0 preregistration")
    sha256_text(prereg["sha256"]) && sha256_file(prereg_path) == prereg["sha256"] ||
        error("T0 preregistration hash drifted")
    ExperimentDisc001._validate_t0_registration(prereg_path, authority)

    problems = t0_problems()
    cases = document["cases"]
    length(cases) == length(problems) || error("T0 case list drifted")
    loaded = [Dict{String,Any}() for _ in problems]
    for (index, problem) in enumerate(problems)
        case = cases[index]
        case["case_index"] == index && case["instance_id"] == problem.instance_id ||
            error("T0 case identity drifted")
        case["source_replay_checksum"] == replay_checksum(problem) || error("case replay drifted")
        case["dimension"] == problem.dimension && case["target_count"] == length(problem.gold_targets) ||
            error("case dimensions or targets drifted")
        proposals = case["proposals"]
        Tuple(String(entry["method"]) for entry in proposals) == T0O_METHODS ||
            error("case proposal order drifted")
        artifacts || continue
        for entry in proposals
            method = String(entry["method"])
            artifact_path = repo_path(entry["path"])
            sha256_text(entry["file_sha256"]) && sha256_file(artifact_path) == entry["file_sha256"] ||
                error("proposal file hash drifted")
            artifact = read_matrix_artifact(artifact_path)
            artifact.method == T0O_METHOD_ENUM[method] && artifact_sha256(artifact) == entry["artifact_sha256"] ||
                error("proposal artifact binding drifted")
            artifact.authority_sha256 == freeze_sha && artifact.replicate_seed == parse(UInt64, entry["replicate_seed"]) ||
                error("proposal authority or seed drifted")
            static_prefix_audit(artifact).valid || error("proposal prefix audit failed")
            digital = get(entry, "digital_net_minimal_t_by_prefix", nothing)
            if method in (T0O_METHODS[2], T0O_METHODS[5], T0O_METHODS[6])
                canonical_json(digital) == canonical_json(digital_net_prefix_audit(artifact)) ||
                    error("digital-net prefix audit drifted")
            else
                digital === nothing || error("non-digital stream carried a digital-net audit")
            end
            iid_service = get(entry, "iid_service_audit", nothing)
            if method in (T0O_METHODS[1], T0O_METHODS[4], T0O_METHODS[7])
                audit = iid_bounded_gap_audit(artifact.lane_schedule; cadence=4)
                expected_iid = Dict(
                    "bounded_gap" => audit.bounded_gap,
                    "cadence" => audit.cadence,
                    "iid_count" => audit.iid_count,
                    "maximum_gap" => audit.maximum_gap,
                    "starvation_count" => audit.starvation_count,
                    "violation_prefixes" => collect(audit.violation_prefixes),
                )
                canonical_json(iid_service) == canonical_json(expected_iid) ||
                    error("IID service audit binding drifted")
            else
                iid_service === nothing || error("pure QMC stream carried an IID service claim")
            end
            size(artifact.coordinates) == (problem.dimension, 128) || error("proposal shape drifted")
            loaded[index][method] = (artifact=artifact, manifest=entry)
        end
    end
    return (document=document, sha256=sha256_file(path), problems=problems,
        loaded=loaded, freeze=freeze, prereg=(prereg_path, prereg["sha256"]))
end

function authorize(path, input_path, input_sha, prereg)
    committed(path, "outcome authorization")
    auth = json_document(path, "outcome authorization")
    get(auth, "schema_version", nothing) == "geotarget.discovery-t0-outcome-authorization/v1" &&
        get(auth, "outcome_execution_authorized", false) === true || error("outcomes not authorized")
    repo_path(auth["input_manifest"]["path"]) == abspath(input_path) &&
        auth["input_manifest"]["sha256"] == input_sha || error("authorized input drifted")
    repo_path(auth["preregistration"]["path"]) == prereg[1] &&
        auth["preregistration"]["sha256"] == prereg[2] || error("authorized preregistration drifted")
    committed(T0O_RUNNER, "outcome runner")
    committed(T0O_AGGREGATOR, "outcome aggregator")
    auth["runner_source_sha256"] == sha256_file(T0O_RUNNER) || error("authorized runner drifted")
    auth["aggregator_source_sha256"] == sha256_file(T0O_AGGREGATOR) ||
        error("authorized aggregator drifted")
    return (document=auth, sha256=sha256_file(path))
end

function assessor_metrics(attempts, target_count)
    qualified = filter(a -> a.assessor_qualified, attempts)
    safe = filter(a -> a.assessor_gold_matched && !a.assessor_target_ambiguous, qualified)
    targets = Set(a.assessor_matched_target_id for a in safe)
    unsafe = count(a -> !a.assessor_gold_matched || a.assessor_target_ambiguous, qualified)
    return Dict("assessor_qualified" => length(qualified), "assessor_targets_found" => length(targets),
        "assessor_target_recall" => length(targets) / target_count,
        "assessor_unsafe" => unsafe, "assessor_safe_full" => length(targets) == target_count && unsafe == 0)
end

function suffix_work(attempts, target_count)
    for index in eachindex(attempts)
        assessor_metrics(@view(attempts[1:index]), target_count)["assessor_safe_full"] || continue
        all(a -> !a.assessor_qualified || (a.assessor_gold_matched && !a.assessor_target_ambiguous),
            @view(attempts[index + 1:end])) || continue
        return sum(a.evaluations for a in @view(attempts[1:index]))
    end
    return nothing
end

function proposal_summaries(attempts, target_count, method)
    return [
        merge(assessor_metrics(@view(attempts[1:prefix]), target_count), Dict(
            "callback_work" => sum(attempt.evaluations for attempt in @view(attempts[1:prefix])),
            "evaluation_count_mismatches" => count(
                attempt -> attempt.evaluation_count_mismatch,
                @view(attempts[1:prefix]),
            ),
            "method" => method,
            "prefix" => prefix,
        )) for prefix in T0O_PREFIXES
    ]
end

function callback_snapshots(attempts, target_count, method)
    result, cumulative, next = Dict{String,Any}[], 0, 1
    for (index, attempt) in enumerate(attempts)
        cumulative += attempt.evaluations
        while next <= length(T0O_THRESHOLDS) && cumulative >= T0O_THRESHOLDS[next]
            push!(result, merge(assessor_metrics(@view(attempts[1:index]), target_count), Dict(
                "callback_threshold" => T0O_THRESHOLDS[next], "crossing_callback_work" => cumulative,
                "crossing_start_index" => index, "method" => method)))
            next += 1
        end
    end
    return result
end

function run_stream(problem, artifact, variant, method)
    run_problem = t0_problem_with_proposals(problem, artifact.coordinates)
    run = run_solver_experiment([run_problem], [variant]; prefixes=T0O_PREFIXES, evaluation_limit=600)
    length(run.attempts) == 128 && length(run.prefixes) == 5 || error("stream did not complete")
    for (index, attempt) in enumerate(run.attempts)
        reinterpret(UInt64, collect(attempt.start)) == reinterpret(UInt64, artifact.coordinates[:, index]) ||
            error("attempt start bits drifted")
    end
    attempts = collect(run.attempts)
    serialized = solver_experiment_document(run)
    return Dict("method" => method, "attempts" => serialized["attempts"],
        "proposal_summaries" => proposal_summaries(
            attempts, length(problem.gold_targets), method,
        ),
        "callback_snapshots" => callback_snapshots(
            attempts, length(problem.gold_targets), method,
        ),
        "terminal" => Dict("attempt_count" => 128, "callback_work" => sum(a.evaluations for a in attempts),
            "evaluation_count_mismatches" => count(a -> a.evaluation_count_mismatch, attempts),
            "exceptions" => count(a -> a.exception !== nothing, attempts),
            "runner_budget_exhausted" => count(a -> a.budget_exhausted, attempts),
            "local_cap_violations" => count(a -> a.evaluations > 600 || a.reported_evaluations > 600, attempts),
            "suffix_stable_assessor_work" => suffix_work(attempts, length(problem.gold_targets))))
end

function preflight(input, case_index)
    project, threads, bundle = active_project(), thread_contract(), load_inputs(input)
    indices = case_index === nothing ? collect(1:6) : [case_index]
    all(index -> 1 <= index <= 6, indices) || error("case index must lie in 1:6")
    variant = local_variant(bundle.freeze)
    return Dict("schema_version" => "geotarget.discovery-t0-outcome-preflight/v1",
        "active_project" => project, "thread_contract" => threads, "case_indices" => indices,
        "input_manifest_sha256" => bundle.sha256, "artifact_count" => 7length(indices),
        "local_policy" => variant.name, "lab_confirmation_512_768" => false,
        "raw_counter_halton_scope" => "h0-raw-attribution-only", "outcomes_executed" => false)
end

function execute(input, auth_path, output, case_index, cpu)
    project, threads = active_project(), thread_contract()
    isempty(strip(read(`git -C $T0O_REPO status --porcelain`, String))) || error("clean tree required")
    input_sha = sha256_file(input)
    header = json_document(input, "T0 input manifest")
    prereg = (repo_path(header["preregistration"]["path"]), header["preregistration"]["sha256"])
    auth = authorize(auth_path, input, input_sha, prereg)
    host, slot = execution_host(case_index, cpu), acquire_cpu(cpu)
    try
        bundle = load_inputs(input)
        variant, problem = local_variant(bundle.freeze), bundle.problems[case_index]
        streams = Dict{String,Any}[]
        for method in T0O_METHODS
            binding = bundle.loaded[case_index][method]
            stream = run_stream(problem, binding.artifact, variant, method)
            stream["source_scope"] = method == T0O_METHODS[4] ? "h0-raw-attribution-only" : "fixed-source"
            stream["proposal"] = binding.manifest
            push!(streams, stream)
        end
        document = Dict("schema_version" => "geotarget.discovery-t0-raw/v1",
            "experiment_id" => "EXP-DISC-001", "stage" => "t0", "partition" => "development",
            "case_index" => case_index, "lab_confirmation_512_768" => false,
            "input_manifest" => Dict("path" => repo_relative(input), "sha256" => bundle.sha256),
            "authorization" => Dict("path" => repo_relative(auth_path), "sha256" => auth.sha256),
            "revision" => Dict("git_head" => readchomp(`git -C $T0O_REPO rev-parse HEAD`), "git_dirty" => false),
            "thread_contract" => merge(threads, host), "case_manifest" => bundle.document["cases"][case_index],
            "stream_order" => collect(T0O_METHODS), "streams" => streams)
        ispath(output) && error("refusing to overwrite outcome")
        mkpath(dirname(output))
        io = Base.Filesystem.open(output, Base.JL_O_WRONLY | Base.JL_O_CREAT | Base.JL_O_EXCL, 0o600)
        try write(io, canonical_json(document), '\n') finally close(io) end
        println("output=", output)
        return document
    finally
        close(slot)
    end
end

function self_test()
    active_project(); thread_contract()
    problems = t0_problems()
    length(problems) == 6 && sum(length(p.gold_targets) for p in problems) == 17 || error("corpus fixture")
    starts = repeat(reshape((problems[1].lower_bounds .+ problems[1].upper_bounds) ./ 2, :, 1), 1, 128)
    replacement = t0_problem_with_proposals(problems[1], starts)
    size(replacement.saved_starts) == (problems[1].dimension, 128) || error("start fixture")
    freeze = json_document(joinpath(T0O_ROOT, "local-champion-freeze-record.json"), "freeze")
    local_variant(freeze)
    return Dict("schema_version" => "geotarget.discovery-t0-runner-self-test/v1",
        "corpus_fixture" => true, "proposal_adapter_fixture" => true,
        "solver_invocations" => 0, "outcomes_executed" => false)
end

function parse_args(args)
    mode, input, auth, output, case_index, cpu = :preflight, T0O_INPUT, T0O_AUTH,
        joinpath(T0O_REPO, "benchmarks", "results", "raw", "exp-disc-001-t0.json"), nothing, nothing
    for arg in args
        arg == "--execute" ? (mode = :execute) : arg == "--self-test" ? (mode = :self_test) :
        arg == "--preflight-only" ? (mode = :preflight) : arg == "--help" ? (return nothing) :
        startswith(arg, "--input-manifest=") ? (input = abspath(split(arg, '='; limit=2)[2])) :
        startswith(arg, "--authorization=") ? (auth = abspath(split(arg, '='; limit=2)[2])) :
        startswith(arg, "--output=") ? (output = abspath(split(arg, '='; limit=2)[2])) :
        startswith(arg, "--case-index=") ? (case_index = parse(Int, split(arg, '=')[2])) :
        startswith(arg, "--assigned-cpu=") ? (cpu = parse(Int, split(arg, '=')[2])) : error("unknown option: $arg")
    end
    return (; mode, input, auth, output, case_index, cpu)
end

function main(args=ARGS)
    options = parse_args(args)
    options === nothing && return print("Use --preflight-only, --self-test, or --execute --case-index=N --assigned-cpu=N\n")
    if options.mode == :execute
        options.case_index === nothing && error("--case-index is required")
        options.cpu === nothing && error("--assigned-cpu is required")
    end
    result = options.mode == :self_test ? self_test() : options.mode == :preflight ?
        preflight(options.input, options.case_index) :
        execute(options.input, options.auth, options.output, options.case_index, options.cpu)
    options.mode == :execute || println(canonical_json(result))
    return result
end

abspath(PROGRAM_FILE) == abspath(@__FILE__) && main()
