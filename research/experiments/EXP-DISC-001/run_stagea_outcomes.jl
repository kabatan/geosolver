include(joinpath(@__DIR__, "run_t0_outcomes.jl"))
include(joinpath(@__DIR__, "src", "stagea_corpus.jl"))
using .StageAInputs

const STAGEA_RUNNER = @__FILE__
const STAGEA_INPUT = joinpath(T0O_ROOT, "stagea-input-manifest.json")
const STAGEA_AUTH = joinpath(T0O_ROOT, "stagea-outcome-authorization.json")
const STAGEA_AGGREGATOR = joinpath(T0O_ROOT, "aggregate_stagea.py")
const STAGEA_RANDOMIZED_WIRES = Tuple(
    T0O_METHODS[index] for index in (1, 4, 5, 6, 7)
)

function stagea_expected_methods(replicate)
    1 <= replicate <= StageAInputs.STAGEA_REPLICATES || error("replicate must lie in 1:10")
    return replicate == 1 ? T0O_METHODS : STAGEA_RANDOMIZED_WIRES
end

function stagea_expected_pairs()
    return [
        (method, replicate) for replicate in 1:StageAInputs.STAGEA_REPLICATES
        for method in stagea_expected_methods(replicate)
    ]
end

function stagea_validate_preregistration(path, freeze_sha)
    committed(path, "Stage A preregistration")
    document = json_document(path, "Stage A preregistration")
    get(document, "schema_version", nothing) ==
        "geotarget.discovery-stagea-preregistration/v1" || error("Stage A preregistration schema drifted")
    get(document, "materialization_authorized", false) === true ||
        error("Stage A materialization is not authorized")
    get(document, "outcome_execution_authorized", true) === false ||
        error("Stage A preregistration cannot authorize outcomes")
    get(document, "local_freeze_sha256", nothing) == freeze_sha ||
        error("Stage A preregistration freeze drifted")
    parse(UInt64, String(get(document, "root_seed", ""))) == StageAInputs.STAGEA_ROOT_SEED ||
        error("Stage A root seed drifted")
    get(document, "randomized_replicate_count", nothing) == StageAInputs.STAGEA_REPLICATES ||
        error("Stage A replicate count drifted")
    Tuple(String.(get(document, "methods", Any[]))) == T0O_METHODS ||
        error("Stage A method order drifted")
    sources = get(document, "source_sha256", nothing)
    sources isa AbstractDict && !isempty(sources) || error("Stage A source bindings are absent")
    for (relative, expected) in sources
        source = repo_path(String(relative))
        committed(source, "Stage A preregistered source")
        sha256_text(expected) && sha256_file(source) == expected ||
            error("Stage A preregistered source drifted: $relative")
    end
    return document
end

function stagea_iid_document(method, artifact)
    method in (T0O_METHODS[1], T0O_METHODS[4], T0O_METHODS[7]) || return nothing
    audit = iid_bounded_gap_audit(artifact.lane_schedule; cadence=4)
    return Dict(
        "bounded_gap" => audit.bounded_gap,
        "cadence" => audit.cadence,
        "iid_count" => audit.iid_count,
        "maximum_gap" => audit.maximum_gap,
        "starvation_count" => audit.starvation_count,
        "violation_prefixes" => collect(audit.violation_prefixes),
    )
end

function stagea_load_inputs(path; artifacts=true)
    committed(path, "Stage A input manifest")
    document = json_document(path, "Stage A input manifest")
    get(document, "schema_version", nothing) == "geotarget.discovery-stagea-input/v1" ||
        error("Stage A input schema drifted")
    get(document, "experiment_id", nothing) == "EXP-DISC-001" || error("experiment drifted")
    get(document, "stage", nothing) == "stage-a-source-ablation" &&
        get(document, "partition", nothing) == "development" ||
        error("input crossed the Stage A development boundary")
    get(document, "lab_confirmation_512_768", true) === false ||
        error("DirectAnalytic Stage A cannot claim 512/768 confirmation")
    Tuple(String.(get(document, "methods", Any[]))) == T0O_METHODS || error("methods drifted")
    Tuple(Int.(get(document, "prefixes", Any[]))) == T0O_PREFIXES || error("prefixes drifted")
    Tuple(Int.(get(document, "callback_thresholds", Any[]))) == T0O_THRESHOLDS ||
        error("callback thresholds drifted")
    get(document, "attempt_evaluation_limit", nothing) == 600 || error("attempt cap drifted")
    parse(UInt64, String(get(document, "root_seed", ""))) == StageAInputs.STAGEA_ROOT_SEED ||
        error("input root seed drifted")
    get(document, "replicate_count", nothing) == StageAInputs.STAGEA_REPLICATES ||
        error("input replicate count drifted")
    get(document, "case_count", nothing) == 24 && get(document, "proposal_count", nothing) == 1248 ||
        error("Stage A input size drifted")
    counts = get(document, "method_replicate_counts", nothing)
    expected_counts = Dict(method => (method in (T0O_METHODS[2], T0O_METHODS[3]) ? 1 : 10)
        for method in T0O_METHODS)
    counts isa AbstractDict && all(get(counts, method, nothing) == count
        for (method, count) in expected_counts) || error("method replicate counts drifted")

    source_manifests = get(document, "source_manifests", nothing)
    source_manifests isa AbstractVector && !isempty(source_manifests) ||
        error("source manifest bindings are absent")
    for binding in source_manifests
        source = repo_path(binding["path"])
        committed(source, "Stage A source manifest")
        sha256_text(binding["sha256"]) && sha256_file(source) == binding["sha256"] ||
            error("Stage A source manifest drifted")
    end

    freeze_binding = document["local_freeze"]
    freeze_path = repo_path(freeze_binding["path"])
    committed(freeze_path, "local freeze")
    freeze_sha = freeze_binding["sha256"]
    sha256_text(freeze_sha) && sha256_file(freeze_path) == freeze_sha || error("freeze drifted")
    authority = materialization_preflight(freeze_path)
    authority.freeze_sha256 == freeze_sha || error("freeze authority drifted")
    freeze = json_document(freeze_path, "local freeze")

    prereg_binding = document["preregistration"]
    prereg_path = repo_path(prereg_binding["path"])
    sha256_text(prereg_binding["sha256"]) && sha256_file(prereg_path) == prereg_binding["sha256"] ||
        error("Stage A preregistration hash drifted")
    stagea_validate_preregistration(prereg_path, freeze_sha)

    problems = StageAInputs.stagea_problems()
    cases = document["cases"]
    length(cases) == length(problems) == 24 || error("Stage A case list drifted")
    loaded = [Dict{Tuple{String,Int},Any}() for _ in problems]
    expected_pairs = Set(stagea_expected_pairs())
    for (case_index, problem) in enumerate(problems)
        case = cases[case_index]
        get(case, "case_index", nothing) == case_index &&
            get(case, "formal_case_id", nothing) == "EXP-DISC-001-A-$(lpad(case_index, 3, '0'))" &&
            get(case, "instance_id", nothing) == problem.instance_id || error("case identity drifted")
        get(case, "source_replay_checksum", nothing) == replay_checksum(problem) ||
            error("case replay drifted")
        get(case, "dimension", nothing) == problem.dimension &&
            get(case, "residual_dimension", nothing) == problem.residual_dimension &&
            get(case, "configuration_count", nothing) == size(problem.gold_configurations, 2) &&
            get(case, "target_count", nothing) == length(problem.gold_targets) ||
            error("case dimensions, configurations, or targets drifted")
        proposals = get(case, "proposals", Any[])
        length(proposals) == 52 || error("case proposal count drifted")
        observed_pairs = Set{Tuple{String,Int}}()
        for entry in proposals
            method, replicate = String(entry["method"]), Int(entry["replicate"])
            pair = (method, replicate)
            pair in expected_pairs && !(pair in observed_pairs) || error("proposal identity drifted")
            push!(observed_pairs, pair)
            artifacts || continue
            artifact_path = repo_path(entry["path"])
            sha256_text(entry["file_sha256"]) && sha256_file(artifact_path) == entry["file_sha256"] ||
                error("proposal file hash drifted")
            artifact = read_matrix_artifact(artifact_path)
            StageAInputs._assert_truth_free_artifact(artifact)
            artifact.method == T0O_METHOD_ENUM[method] && artifact_sha256(artifact) == entry["artifact_sha256"] ||
                error("proposal artifact binding drifted")
            expected_seed = derive_seed(
                StageAInputs.STAGEA_ROOT_SEED,
                T0O_METHOD_ENUM[method],
                case_index,
                replicate,
                "stagea-proposal",
            )
            parse(UInt64, String(entry["replicate_seed"])) == expected_seed ||
                error("proposal seed derivation drifted")
            artifact.authority_sha256 == freeze_sha &&
                artifact.replicate_seed == expected_seed ||
                error("proposal authority or seed drifted")
            static_prefix_audit(artifact).valid || error("proposal prefix audit failed")
            digital = get(entry, "digital_net_minimal_t_by_prefix", nothing)
            if method in (T0O_METHODS[2], T0O_METHODS[5], T0O_METHODS[6])
                canonical_json(digital) == canonical_json(digital_net_prefix_audit(artifact)) ||
                    error("digital-net prefix audit drifted")
            else
                digital === nothing || error("non-digital stream carried a digital-net audit")
            end
            iid = get(entry, "iid_service_audit", nothing)
            expected_iid = stagea_iid_document(method, artifact)
            canonical_json(iid) == canonical_json(expected_iid) || error("IID service audit drifted")
            size(artifact.coordinates) == (problem.dimension, 128) || error("proposal shape drifted")
            loaded[case_index][pair] = (artifact=artifact, manifest=entry)
        end
        observed_pairs == expected_pairs || error("one or more proposal streams are absent")
        artifacts || continue
        for replicate in 1:StageAInputs.STAGEA_REPLICATES
            mixed = loaded[case_index][(T0O_METHODS[7], replicate)]
            iid = loaded[case_index][(T0O_METHODS[1], replicate)]
            rqmc = loaded[case_index][(T0O_METHODS[5], replicate)]
            sources = get(mixed.manifest, "mixed_sources", nothing)
            sources isa AbstractDict || error("mixed source bindings are absent")
            for (key, binding) in (("iid", iid), ("rqmc", rqmc))
                source = get(sources, key, nothing)
                source isa AbstractDict && source["path"] == binding.manifest["path"] &&
                    source["file_sha256"] == binding.manifest["file_sha256"] &&
                    source["artifact_sha256"] == binding.manifest["artifact_sha256"] ||
                    error("mixed source binding drifted")
            end
            metadata = JSON3.read(mixed.artifact.metadata_json, Dict{String,Any})
            metadata["iid_source_sha256"] == iid.artifact.sha256 &&
                metadata["rqmc_source_sha256"] == rqmc.artifact.sha256 ||
                error("mixed artifact source metadata drifted")
            for column in axes(mixed.artifact.coordinates, 2)
                source = mixed.artifact.lane_schedule[column] == :iid ? iid.artifact : rqmc.artifact
                source_column = mixed.artifact.source_columns[column]
                reinterpret(UInt64, mixed.artifact.coordinates[:, column]) ==
                    reinterpret(UInt64, source.coordinates[:, source_column]) ||
                    error("mixed coordinates are not bit-exact source columns")
            end
        end
    end
    get(document, "target_count", nothing) == sum(length(problem.gold_targets) for problem in problems) ||
        error("Stage A target total drifted")
    return (document=document, sha256=sha256_file(path), problems=problems, loaded=loaded,
        freeze=freeze, prereg=(prereg_path, prereg_binding["sha256"]))
end

function stagea_authorize(path, input_path, input_sha, prereg)
    committed(path, "Stage A outcome authorization")
    auth = json_document(path, "Stage A outcome authorization")
    get(auth, "schema_version", nothing) == "geotarget.discovery-stagea-outcome-authorization/v1" &&
        get(auth, "outcome_execution_authorized", false) === true || error("outcomes not authorized")
    repo_path(auth["input_manifest"]["path"]) == abspath(input_path) &&
        auth["input_manifest"]["sha256"] == input_sha || error("authorized input drifted")
    repo_path(auth["preregistration"]["path"]) == prereg[1] &&
        auth["preregistration"]["sha256"] == prereg[2] || error("authorized preregistration drifted")
    committed(STAGEA_RUNNER, "Stage A outcome runner")
    committed(STAGEA_AGGREGATOR, "Stage A aggregator")
    auth["runner_source_sha256"] == sha256_file(STAGEA_RUNNER) || error("authorized runner drifted")
    auth["aggregator_source_sha256"] == sha256_file(STAGEA_AGGREGATOR) ||
        error("authorized aggregator drifted")
    dependencies = get(auth, "dependency_source_sha256", nothing)
    expected_dependencies = Dict(
        repo_relative(T0O_RUNNER) => sha256_file(T0O_RUNNER),
        repo_relative(T0O_AGGREGATOR) => sha256_file(T0O_AGGREGATOR),
    )
    dependencies isa AbstractDict && all(
        get(dependencies, relative, nothing) == digest for
        (relative, digest) in expected_dependencies
    ) || error("authorized Stage A dependency drifted")
    return (document=auth, sha256=sha256_file(path))
end

function stagea_execution_host(case_index, replicate, cpu)
    expected = (case_index + replicate - 2) % 16
    0 <= cpu <= 15 && cpu == expected || error("case/replicate CPU assignment drifted")
    get(ENV, "GEOTARGET_CASE_PROCESS_LIMIT", "unset") == "16" ||
        error("GEOTARGET_CASE_PROCESS_LIMIT=16 is required")
    matched = match(r"(?m)^Cpus_allowed_list:\s*(.+)$", read("/proc/self/status", String))
    matched !== nothing || error("cannot inspect CPU affinity")
    allowed = strip(matched.captures[1])
    allowed == string(cpu) && ccall(:sched_getcpu, Cint, ()) == cpu ||
        error("process must be pinned to CPU $cpu")
    return Dict("assigned_cpu" => cpu, "case_process_limit" => 16,
        "cpus_allowed_list" => allowed, "solver_worker_count" => 1)
end

function stagea_acquire_cpu(cpu)
    io = open("/tmp/geotarget-exp-disc-001-stagea-cpu-$cpu.lock", "w")
    ccall(:flock, Cint, (Cint, Cint), fd(io), 2 | 4) == 0 ||
        (close(io); error("CPU $cpu already has a Stage A case process"))
    return io
end

function stagea_run_stream(problem, artifact, variant, method)
    run_problem = StageAInputs.stagea_problem_with_proposals(problem, artifact.coordinates)
    run = run_solver_experiment([run_problem], [variant]; prefixes=T0O_PREFIXES, evaluation_limit=600)
    length(run.attempts) == 128 && length(run.prefixes) == 5 || error("stream did not complete")
    for (index, attempt) in enumerate(run.attempts)
        reinterpret(UInt64, collect(attempt.start)) == reinterpret(UInt64, artifact.coordinates[:, index]) ||
            error("attempt start bits drifted")
    end
    attempts = collect(run.attempts)
    serialized = solver_experiment_document(run)
    return Dict("method" => method, "attempts" => serialized["attempts"],
        "proposal_summaries" => proposal_summaries(attempts, length(problem.gold_targets), method),
        "callback_snapshots" => stagea_callback_snapshots(
            attempts,
            length(problem.gold_targets),
            method,
        ),
        "terminal" => Dict("attempt_count" => 128,
            "callback_work" => sum(attempt.evaluations for attempt in attempts),
            "evaluation_count_mismatches" => count(a -> a.evaluation_count_mismatch, attempts),
            "exceptions" => count(a -> a.exception !== nothing, attempts),
            "runner_budget_exhausted" => count(a -> a.budget_exhausted, attempts),
            "local_cap_violations" => count(a -> a.evaluations > 600 || a.reported_evaluations > 600, attempts),
            "suffix_stable_assessor_work" => suffix_work(attempts, length(problem.gold_targets))))
end

function stagea_callback_snapshots(attempts, target_count, method)
    snapshots = callback_snapshots(attempts, target_count, method)
    for snapshot in snapshots
        snapshot["threshold_reached"] = true
    end
    reached = Set(snapshot["callback_threshold"] for snapshot in snapshots)
    terminal_work = sum(attempt.evaluations for attempt in attempts)
    for threshold in T0O_THRESHOLDS
        threshold in reached && continue
        push!(snapshots, merge(assessor_metrics(attempts, target_count), Dict(
            "callback_threshold" => threshold,
            "crossing_callback_work" => terminal_work,
            "crossing_start_index" => length(attempts),
            "method" => method,
            "threshold_reached" => false,
        )))
    end
    sort!(snapshots; by=snapshot -> snapshot["callback_threshold"])
    return snapshots
end

function stagea_case_identity(case)
    return Dict(String(key) => value for (key, value) in case if String(key) != "proposals")
end

function stagea_preflight(input, case_index, replicate)
    project, threads, bundle = active_project(), thread_contract(), stagea_load_inputs(input)
    case_indices = case_index === nothing ? collect(1:24) : [case_index]
    replicates = replicate === nothing ? collect(1:10) : [replicate]
    all(index -> 1 <= index <= 24, case_indices) || error("case index must lie in 1:24")
    all(rep -> 1 <= rep <= 10, replicates) || error("replicate must lie in 1:10")
    variant = local_variant(bundle.freeze)
    artifact_count = sum(length(stagea_expected_methods(rep)) for rep in replicates) * length(case_indices)
    return Dict("schema_version" => "geotarget.discovery-stagea-outcome-preflight/v1",
        "active_project" => project, "thread_contract" => threads,
        "case_indices" => case_indices, "replicates" => replicates,
        "input_manifest_sha256" => bundle.sha256, "artifact_count" => artifact_count,
        "local_policy" => variant.name, "lab_confirmation_512_768" => false,
        "raw_counter_halton_scope" => "h0-raw-attribution-only", "outcomes_executed" => false)
end

function stagea_execute(input, auth_path, output, case_index, replicate, cpu)
    project, threads = active_project(), thread_contract()
    isempty(strip(read(`git -C $T0O_REPO status --porcelain`, String))) || error("clean tree required")
    header = json_document(input, "Stage A input manifest")
    prereg = (repo_path(header["preregistration"]["path"]), header["preregistration"]["sha256"])
    auth = stagea_authorize(auth_path, input, sha256_file(input), prereg)
    host, slot = stagea_execution_host(case_index, replicate, cpu), stagea_acquire_cpu(cpu)
    try
        bundle = stagea_load_inputs(input)
        variant, problem = local_variant(bundle.freeze), bundle.problems[case_index]
        methods, streams = stagea_expected_methods(replicate), Dict{String,Any}[]
        for method in methods
            binding = bundle.loaded[case_index][(method, replicate)]
            stream = stagea_run_stream(problem, binding.artifact, variant, method)
            stream["replicate"] = replicate
            stream["source_scope"] = method == T0O_METHODS[4] ?
                "h0-raw-attribution-only" : "fixed-source"
            stream["proposal"] = binding.manifest
            push!(streams, stream)
        end
        document = Dict("schema_version" => "geotarget.discovery-stagea-raw/v1",
            "experiment_id" => "EXP-DISC-001", "stage" => "stage-a-source-ablation",
            "partition" => "development", "case_index" => case_index,
            "replicate" => replicate, "lab_confirmation_512_768" => false,
            "input_manifest" => Dict("path" => repo_relative(input), "sha256" => bundle.sha256),
            "authorization" => Dict("path" => repo_relative(auth_path), "sha256" => auth.sha256),
            "revision" => Dict("git_head" => readchomp(`git -C $T0O_REPO rev-parse HEAD`),
                "git_dirty" => false),
            "thread_contract" => merge(threads, host),
            "case_manifest" => stagea_case_identity(bundle.document["cases"][case_index]),
            "stream_order" => collect(methods), "streams" => streams)
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

function stagea_self_test()
    active_project(); thread_contract()
    problems = StageAInputs.stagea_problems()
    length(problems) == 24 && sum(length(problem.gold_targets) for problem in problems) == 64 ||
        error("Stage A corpus fixture")
    length(stagea_expected_pairs()) == 52 || error("Stage A stream fixture")
    starts = repeat(reshape((problems[1].lower_bounds .+ problems[1].upper_bounds) ./ 2, :, 1), 1, 128)
    replacement = StageAInputs.stagea_problem_with_proposals(problems[1], starts)
    size(replacement.saved_starts) == (problems[1].dimension, 128) || error("proposal fixture")
    freeze = json_document(joinpath(T0O_ROOT, "local-champion-freeze-record.json"), "freeze")
    local_variant(freeze)
    return Dict("schema_version" => "geotarget.discovery-stagea-runner-self-test/v1",
        "case_count" => 24, "target_count" => 64, "streams_per_case" => 52,
        "solver_invocations" => 0, "outcomes_executed" => false)
end

function stagea_parse_args(args)
    mode, input, auth, output = :preflight, STAGEA_INPUT, STAGEA_AUTH,
        joinpath(T0O_REPO, "benchmarks", "results", "raw", "exp-disc-001-stagea.json")
    case_index = replicate = cpu = nothing
    for arg in args
        arg == "--execute" ? (mode = :execute) : arg == "--self-test" ? (mode = :self_test) :
        arg == "--preflight-only" ? (mode = :preflight) : arg == "--help" ? (return nothing) :
        startswith(arg, "--input-manifest=") ? (input = abspath(split(arg, '='; limit=2)[2])) :
        startswith(arg, "--authorization=") ? (auth = abspath(split(arg, '='; limit=2)[2])) :
        startswith(arg, "--output=") ? (output = abspath(split(arg, '='; limit=2)[2])) :
        startswith(arg, "--case-index=") ? (case_index = parse(Int, split(arg, '=')[2])) :
        startswith(arg, "--replicate=") ? (replicate = parse(Int, split(arg, '=')[2])) :
        startswith(arg, "--assigned-cpu=") ? (cpu = parse(Int, split(arg, '=')[2])) :
        error("unknown option: $arg")
    end
    return (; mode, input, auth, output, case_index, replicate, cpu)
end

function stagea_main(args=ARGS)
    options = stagea_parse_args(args)
    options === nothing && return print(
        "Use --preflight-only, --self-test, or --execute --case-index=N --replicate=R --assigned-cpu=C\n",
    )
    if options.mode == :execute
        options.case_index === nothing && error("--case-index is required")
        options.replicate === nothing && error("--replicate is required")
        options.cpu === nothing && error("--assigned-cpu is required")
    end
    result = options.mode == :self_test ? stagea_self_test() : options.mode == :preflight ?
        stagea_preflight(options.input, options.case_index, options.replicate) :
        stagea_execute(options.input, options.auth, options.output,
            options.case_index, options.replicate, options.cpu)
    options.mode == :execute || println(canonical_json(result))
    return result
end

abspath(PROGRAM_FILE) == abspath(@__FILE__) && stagea_main()
