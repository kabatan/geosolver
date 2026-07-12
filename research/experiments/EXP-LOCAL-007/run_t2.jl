# Lightweight one-case T2 runner.  Case-level parallelism and aggregation live
# in run_t2_campaign.py; this process always remains single threaded.
include(joinpath(@__DIR__, "run_t1.jl"))
include(joinpath(@__DIR__, "src", "T2Corpus.jl"))
include(joinpath(@__DIR__, "src", "T2Policy.jl"))

using .ExperimentLocal007T2Corpus
using .ExperimentLocal007T2Policy
using SHA

const T2_PREREGISTRATION_PATH = joinpath(@__DIR__, "t2-preregistration.json")
const T2_SHARD_COUNT = T2_INSTANCE_COUNT
const T2_CALLBACK_WORK_CENSOR = 4_800

function t2_usage()
    return """
    Usage: julia --project=research/experiments/EXP-LOCAL-007 \\
      research/experiments/EXP-LOCAL-007/run_t2.jl [options]

      --shard-index=N   Explicit zero-based case index (required: 0..47)
      --shard-count=48  One-case-per-shard contract
      --output=PATH     New JSON output path (required)
      --help            Show this message

    Each shard runs 32 paired starts for three variants and materializes the
    saved-start prefixes 8/16/32.  Use run_t2_campaign.py for up to 16
    independent one-thread case processes.  Wall time is diagnostic only.
    """
end

function parse_t2_arguments(arguments)
    options = Dict{Symbol,Any}(
        :shard_index => nothing,
        :shard_count => T2_SHARD_COUNT,
        :output => nothing,
    )
    seen = Set{Symbol}()
    for argument in arguments
        argument == "--help" && return nothing
        if startswith(argument, "--shard-index=")
            :shard_index in seen && error("duplicate --shard-index")
            push!(seen, :shard_index)
            options[:shard_index] = parse_integer(
                argument[length("--shard-index=") + 1:end],
                "shard index";
                nonnegative=true,
            )
        elseif startswith(argument, "--shard-count=")
            :shard_count in seen && error("duplicate --shard-count")
            push!(seen, :shard_count)
            options[:shard_count] = parse_integer(
                argument[length("--shard-count=") + 1:end],
                "shard count";
                positive=true,
            )
        elseif startswith(argument, "--output=")
            :output in seen && error("duplicate --output")
            push!(seen, :output)
            value = argument[length("--output=") + 1:end]
            isempty(value) && error("output path must be nonempty")
            options[:output] = abspath(value)
        else
            error("unknown option: $argument")
        end
    end
    options[:shard_index] === nothing && error("--shard-index is required")
    options[:shard_count] == T2_SHARD_COUNT || error(
        "EXP-LOCAL-007 T2 requires exactly $T2_SHARD_COUNT case shards",
    )
    options[:shard_index] < T2_SHARD_COUNT || error("shard index must be in 0:47")
    options[:output] === nothing && error("--output is required")
    return options
end

function t2_variants()
    selected = variants()
    observed = Any[
        Dict{String,Any}(
            "name" => variant.name,
            "max_evaluations" => variant.name == T2_CANDIDATE ?
                variant.configuration.max_callbacks :
                variant.configuration.max_evaluations,
        ) for variant in selected
    ]
    expected = Any[
        Dict{String,Any}("name" => "prod-tol-120x600", "max_evaluations" => 600),
        Dict{String,Any}("name" => "prod-options-250x2000", "max_evaluations" => 2_000),
        Dict{String,Any}("name" => T2_CANDIDATE, "max_evaluations" => 600),
    ]
    canonical_json(observed) == canonical_json(expected) ||
        error("T2 variant contract drifted")
    return selected
end

function validate_t2_shard_contract(run)
    length(run.problem_manifest) == 1 || error("T2 shard must own exactly one case")
    problem = only(run.problem_manifest)
    Tuple(run.requested_prefixes) == T2_START_PREFIXES ||
        error("T2 saved-start prefixes drifted")
    run.evaluation_limit == T2_RUNNER_EVALUATION_LIMIT ||
        error("T2 runner cap drifted")
    expected_variants = ("prod-tol-120x600", "prod-options-250x2000", T2_CANDIDATE)
    Tuple(run.variant_names) == expected_variants || error("T2 variant order drifted")
    length(run.attempts) == 3 * T2_START_COUNT ||
        error("T2 shard must contain 96 variant-start attempts")
    length(run.prefixes) == 3 * length(T2_START_PREFIXES) ||
        error("T2 shard must contain nine variant-prefix summaries")

    caps = Dict(
        "prod-tol-120x600" => 600,
        "prod-options-250x2000" => 2_000,
        T2_CANDIDATE => 600,
    )
    pairings = Set{Tuple{String,Int}}()
    for attempt in run.attempts
        attempt.instance_id == problem.instance_id || error("attempt crossed case identity")
        attempt.family_id == problem.family_id || error("attempt crossed family identity")
        attempt.replay_checksum == problem.replay_checksum || error("replay checksum drifted")
        1 <= attempt.start_index <= T2_START_COUNT || error("start index outside 1:32")
        key = (attempt.variant, attempt.start_index)
        key in pairings && error("duplicate variant-start attempt")
        push!(pairings, key)
        attempt.evaluations <= caps[attempt.variant] || error("attempt exceeded callback cap")
        !attempt.evaluation_count_mismatch || error(
            "reported/observed callback mismatch in $(attempt.variant)",
        )
        !attempt.budget_exhausted || error(
            "runner hard cap exhausted in $(attempt.variant)",
        )
        attempt.exception === nothing || error(
            "unhandled exception in $(attempt.variant)",
        )
    end
    expected_pairings = Set(
        (variant, start) for variant in expected_variants for start in 1:T2_START_COUNT
    )
    pairings == expected_pairings || error("T2 paired-start grid is incomplete")

    summary_keys = Set((summary.variant, summary.prefix) for summary in run.prefixes)
    expected_summaries = Set(
        (variant, prefix) for variant in expected_variants for prefix in T2_START_PREFIXES
    )
    summary_keys == expected_summaries || error("T2 summary grid is incomplete")

    candidate = filter(attempt -> attempt.variant == T2_CANDIDATE, run.attempts)
    nonsquare = problem.family_id == T2_NONSQUARE_FAMILY
    for attempt in candidate
        if nonsquare
            attempt.status == "INAPPLICABLE_NONSQUARE" || error("wrong nonsquare status")
            attempt.evaluations == 0 && attempt.reported_evaluations == 0 ||
                error("nonsquare candidate used callbacks")
            attempt.endpoint === nothing || error("nonsquare candidate returned an endpoint")
            !attempt.reported_accepted && !attempt.reported_converged ||
                error("nonsquare candidate reported success")
            !attempt.budget_exhausted || error("nonsquare candidate exhausted runner")
            attempt.exception === nothing || error("nonsquare candidate threw")
        elseif startswith(attempt.status, "INAPPLICABLE_")
            error("candidate was inapplicable on a square case")
        end
    end
    return Dict{String,Any}(
        "attempt_count" => length(run.attempts),
        "all_variant_accounting_valid" => true,
        "pairing_count" => length(pairings),
        "summary_count" => length(run.prefixes),
    )
end

function _print_t2_summary(document)
    for summary in document["summaries"]
        summary["prefix"] == last(T2_START_PREFIXES) || continue
        println(join((
            summary["variant"],
            summary["instance_id"],
            summary["family_id"],
            "$(summary["assessor_qualified_targets_found"])/$(summary["target_count"])",
            summary["assessor_safe_all_targets"],
            summary["evaluations"],
        ), ','))
    end
end

function attach_t2_assessor_work!(document, problem, selected_variants, attempts)
    by_variant = Dict{String,Any}()
    mutable_attempts = collect(attempts)
    for variant in selected_variants
        suffix_work = _suffix_stable_evaluations_to_assessor_safe_full(
            problem,
            variant,
            mutable_attempts,
            T2_START_COUNT,
        )
        censored = _right_censored_assessor_work(suffix_work, T2_CALLBACK_WORK_CENSOR)
        by_variant[variant.name] = (suffix_work, censored)
    end
    for summary in document["summaries"]
        if summary["prefix"] == T2_START_COUNT
            suffix_work, censored = by_variant[summary["variant"]]
            summary["suffix_stable_evaluations_to_assessor_safe_full"] = suffix_work
            summary["right_censored_assessor_safe_full_work"] = censored.work
            summary["assessor_safe_full_event_by_4800"] = censored.event
        end
    end
    return document
end

function t2_main(arguments=ARGS)
    options = parse_t2_arguments(arguments)
    if options === nothing
        print(t2_usage())
        return nothing
    end
    assert_serial_environment()
    revision = git_revision()
    revision["git_dirty"] && error("T2 requires a clean committed worktree")
    ispath(options[:output]) && error("refusing to replace T2 output: $(options[:output])")

    all_problems = t2_problems()
    problems = shard_problems(all_problems, options[:shard_index], options[:shard_count])
    selected_variants = t2_variants()
    run = run_solver_experiment(
        problems,
        selected_variants;
        prefixes=T2_START_PREFIXES,
        evaluation_limit=T2_RUNNER_EVALUATION_LIMIT,
    )
    shard_contract = validate_t2_shard_contract(run)
    document = solver_experiment_document(run)
    attach_t2_assessor_work!(document, only(problems), selected_variants, run.attempts)
    canonical_json(document["assessor_manifest"]) ==
        canonical_json(fixed_assessor_manifest()) || error("T2 assessor drifted")
    preregistration_sha256 = bytes2hex(sha256(read(T2_PREREGISTRATION_PATH)))

    document["schema"] = "geotarget.exp-local-007.t2-case-start-prefix/v1"
    document["experiment_id"] = "EXP-LOCAL-007-T2"
    document["suite"] = "t2-generalization"
    document["partition"] = "development-not-holdout"
    document["revision"] = revision
    document["corpus"] = Dict{String,Any}(
        "case_count" => T2_INSTANCE_COUNT,
        "family_count" => length(T2_FAMILIES),
        "instances_per_family" => T2_INSTANCES_PER_FAMILY,
        "sha256" => T2_CORPUS_SHA256,
        "starts_per_case" => T2_START_COUNT,
    )
    document["preregistration"] = Dict{String,Any}(
        "path" => relpath(T2_PREREGISTRATION_PATH, REPOSITORY_ROOT),
        "sha256" => preregistration_sha256,
    )
    document["promotion_gate_preregistration"] = t2_promotion_gate_contract()
    document["shard"] = Dict{String,Any}(
        "count" => options[:shard_count],
        "index" => options[:shard_index],
        "problem_count" => 1,
        "validated_contract" => shard_contract,
    )
    document["runner_options"] = Dict{String,Any}(
        "case_parallelism_only" => true,
        "evaluation_limit_per_attempt" => T2_RUNNER_EVALUATION_LIMIT,
        "paired_starts_per_case" => T2_START_COUNT,
        "callback_work_censor" => T2_CALLBACK_WORK_CENSOR,
        "primary_work_metric" =>
            "per-case-suffix-stable-common-assessor-safe-full-callbacks-miss-right-censored-at-4800",
        "saved_start_prefixes" => collect(T2_START_PREFIXES),
        "solver_internal_parallelism" => false,
        "wall_time_role" => "diagnostic-never-gating",
    )
    document["environment"] = Dict{String,Any}(
        "julia_blas_threads" => BLAS.get_num_threads(),
        "julia_threads" => Threads.nthreads(),
        "julia_version" => string(VERSION),
        "machine" => Sys.MACHINE,
        "mkl_num_threads" => ENV["MKL_NUM_THREADS"],
        "omp_num_threads" => ENV["OMP_NUM_THREADS"],
        "openblas_num_threads" => ENV["OPENBLAS_NUM_THREADS"],
        "python_executable" => ExperimentLocal007.PYTHON_EXECUTABLE,
        "python_version" => string(ExperimentLocal007.PythonCall.python_version()),
        "scipy_version" => ExperimentLocal007._package_version(),
    )

    mkpath(dirname(options[:output]))
    write(options[:output], canonical_json(document), "\n")
    _print_t2_summary(document)
    println("output=$(options[:output])")
    return document
end

if abspath(PROGRAM_FILE) == abspath(@__FILE__())
    t2_main()
end
