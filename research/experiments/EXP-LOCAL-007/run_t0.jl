using GeoTargetBenchmarks
using GeoTargetCore
using LinearAlgebra

const REPOSITORY_ROOT = normpath(joinpath(@__DIR__, "..", "..", ".."))

include(joinpath(REPOSITORY_ROOT, "benchmarks", "solver_lab", "CoreBaseline.jl"))
include(joinpath(@__DIR__, "src", "ExperimentLocal007.jl"))
using .ExperimentLocal007
using .GeoTargetSolverLab

const DEFAULT_CALLBACK_PREFIXES = [600, 1_200, 2_400, 4_800]
const DEFAULT_MAX_STARTS = 512
const RUNNER_ATTEMPT_HARD_LIMIT = 4_800

function usage()
    return """
    Usage: julia --project=research/experiments/EXP-LOCAL-007 \
      research/experiments/EXP-LOCAL-007/run_t0.jl [options]

      --callback-prefixes=600,1200,2400,4800
                           Sorted case-cumulative callback thresholds
      --max-starts=N       Saved starts generated per case (default: 512)
      --shard-index=N      Zero-based case shard index (default: 0)
      --shard-count=N      Number of outer case shards (default: 1)
      --output=PATH        Output JSON (default is experiment-local and ignored)
      --help               Show this message

    Each (case, variant) consumes the paired saved-start order once. A snapshot
    is taken after the first completed attempt whose cumulative observed callback
    count reaches each threshold; overshoot is recorded. Prefixes are never rerun.
    Run shards with all Julia, BLAS, and OpenMP thread counts fixed to one.
    """
end

function parse_integer(value, label; positive=false, nonnegative=false)
    parsed = tryparse(Int, value)
    parsed !== nothing || error("$label must be an integer")
    positive && parsed <= 0 && error("$label must be positive")
    nonnegative && parsed < 0 && error("$label must be nonnegative")
    return parsed
end

function parse_arguments(arguments)
    options = Dict{Symbol,Any}(
        :callback_prefixes => copy(DEFAULT_CALLBACK_PREFIXES),
        :max_starts => DEFAULT_MAX_STARTS,
        :shard_index => 0,
        :shard_count => 1,
        :output => nothing,
    )
    for argument in arguments
        argument == "--help" && return nothing
        if startswith(argument, "--callback-prefixes=")
            raw = split(argument[length("--callback-prefixes=") + 1:end], ',')
            options[:callback_prefixes] = [
                parse_integer(value, "callback prefix"; positive=true) for value in raw
            ]
        elseif startswith(argument, "--max-starts=")
            options[:max_starts] = parse_integer(
                argument[length("--max-starts=") + 1:end],
                "max starts";
                positive=true,
            )
        elseif startswith(argument, "--shard-index=")
            options[:shard_index] = parse_integer(
                argument[length("--shard-index=") + 1:end],
                "shard index";
                nonnegative=true,
            )
        elseif startswith(argument, "--shard-count=")
            options[:shard_count] = parse_integer(
                argument[length("--shard-count=") + 1:end],
                "shard count";
                positive=true,
            )
        elseif startswith(argument, "--output=")
            output = argument[length("--output=") + 1:end]
            isempty(output) && error("output path must be nonempty")
            options[:output] = abspath(output)
        else
            error("unknown option: $argument")
        end
    end
    prefixes = options[:callback_prefixes]
    issorted(prefixes) && allunique(prefixes) ||
        error("callback prefixes must be sorted and unique")
    options[:shard_index] < options[:shard_count] ||
        error("shard index must be less than shard count")
    options[:output] === nothing && (options[:output] = joinpath(
        @__DIR__,
        "results",
        "t0-callback-prefix-$(last(prefixes))-shard-$(options[:shard_index])-of-$(options[:shard_count]).json",
    ))
    return options
end

mutable struct CallbackPrefixTracker
    thresholds::Vector{Int}
    next_index::Int
    cumulative_callbacks::Int
end

CallbackPrefixTracker(thresholds) = CallbackPrefixTracker(collect(Int, thresholds), 1, 0)

function record_attempt!(tracker::CallbackPrefixTracker, callbacks::Int, start_index::Int)
    callbacks >= 0 || throw(ArgumentError("attempt callbacks must be nonnegative"))
    start_index > 0 || throw(ArgumentError("start index must be positive"))
    tracker.cumulative_callbacks += callbacks
    crossings = NamedTuple[]
    while tracker.next_index <= length(tracker.thresholds) &&
          tracker.cumulative_callbacks >= tracker.thresholds[tracker.next_index]
        threshold = tracker.thresholds[tracker.next_index]
        push!(crossings, (;
            threshold,
            start_index,
            cumulative_callbacks=tracker.cumulative_callbacks,
            overshoot_callbacks=tracker.cumulative_callbacks - threshold,
        ))
        tracker.next_index += 1
    end
    return crossings
end

tracker_complete(tracker::CallbackPrefixTracker) =
    tracker.next_index > length(tracker.thresholds)

function t0_problems(start_count)
    requested = Set((
        "CURVED-CHAIN",
        "NEAR-RANK-DEFICIENT",
        "TANGENT-CIRCLE-LINE",
        "MULTIROOT-WARPED",
    ))
    problems = filter(
        problem -> problem.family_id in requested,
        representative_problems(; start_count),
    )
    length(problems) == 5 ||
        error("T0 must contain Curved, NearRank, Tangent and two Warped maps")
    count(problem -> problem.family_id == "MULTIROOT-WARPED", problems) == 2 ||
        error("T0 must contain both Warped target maps")
    all(verify_replay_material, problems) ||
        error("T0 replay material failed checksum or paired-start validation")
    all(problem -> problem.dimension == problem.residual_dimension, problems) ||
        error("EXP-LOCAL-007 T0 must remain inside the public square-system applicability")
    return problems
end

function shard_problems(problems, shard_index::Int, shard_count::Int)
    shard_count <= length(problems) ||
        error("shard count cannot exceed the number of T0 cases")
    selected = [
        problem for (index, problem) in enumerate(problems) if
        mod(index - 1, shard_count) == shard_index
    ]
    isempty(selected) && error("selected shard is empty")
    return selected
end

function variants()
    return SolverVariant[
        core_lmqr_control(:prod_tol_120x600),
        core_lmqr_control(:prod_options_250x2000),
        scipy_hybr_variant(max_callbacks=ExperimentLocal007.DEFAULT_MAX_CALLBACKS),
    ]
end

function assert_serial_environment()
    Threads.nthreads() == 1 || error("EXP-LOCAL-007 shards require JULIA_NUM_THREADS=1")
    BLAS.get_num_threads() == 1 || error("EXP-LOCAL-007 shards require one Julia BLAS thread")
    for name in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS")
        get(ENV, name, "") == "1" || error("EXP-LOCAL-007 shards require $name=1")
    end
    return nothing
end

function _summary_document(summary, crossing)
    document = GeoTargetBenchmarks._prefix_document(summary)
    document["saved_start_prefix"] = document["prefix"]
    document["prefix"] = crossing.threshold
    document["callback_prefix"] = crossing.threshold
    document["prefix_unit"] = "case-cumulative-observed-callbacks"
    document["completed_attempts"] = crossing.start_index
    document["crossing_attempt_start_index"] = crossing.start_index
    document["cumulative_callbacks"] = crossing.cumulative_callbacks
    document["overshoot_callbacks"] = crossing.overshoot_callbacks
    document["snapshot_boundary"] = "first-completed-attempt-reaching-threshold"
    return document
end

function run_case_stream(
    problem,
    variant,
    callback_prefixes,
    max_starts,
    first_attempt::Base.RefValue{Bool},
    tolerances,
)
    case = GeoTargetBenchmarks._truth_blind_case(problem, RUNNER_ATTEMPT_HARD_LIMIT)
    attempts = SolverExperimentAttempt[]
    snapshots = Dict{String,Any}[]
    tracker = CallbackPrefixTracker(callback_prefixes)
    try
        for start_index in 1:max_starts
            timing_phase = first_attempt[] ? :cold_first_use : :warm
            attempt = GeoTargetBenchmarks._run_solver_attempt(
                problem,
                case,
                variant,
                start_index,
                timing_phase,
                tolerances,
                time_ns,
            )
            first_attempt[] = false
            push!(attempts, attempt)
            crossings = record_attempt!(tracker, attempt.evaluations, start_index)
            for crossing in crossings
                summary = GeoTargetBenchmarks._prefix_summary(
                    problem,
                    variant,
                    attempts,
                    start_index,
                    nothing,
                )
                push!(snapshots, _summary_document(summary, crossing))
            end
            tracker_complete(tracker) && break
        end
    finally
        GeoTargetBenchmarks._release_solver_case_oracle!(case._evaluate)
    end
    tracker_complete(tracker) || error(
        "$(variant.name) / $(problem.instance_id) did not reach callback prefix " *
        "$(last(callback_prefixes)) within $max_starts paired starts; reached " *
        "$(tracker.cumulative_callbacks)",
    )
    suffix_stable = GeoTargetBenchmarks._suffix_stable_evaluations_to_lab_safe_full(
        problem,
        variant,
        attempts,
        length(attempts),
    )
    for snapshot in snapshots
        snapshot["suffix_stable_evaluations_to_lab_safe_full"] = suffix_stable
    end
    return attempts, snapshots
end

_configuration_value(value::Symbol) = String(value)
_configuration_value(value) = value

function _variant_manifest(variant)
    return Dict{String,Any}(
        "name" => variant.name,
        "configuration" => Dict{String,Any}(
            String(key) => _configuration_value(value) for
            (key, value) in pairs(variant.configuration)
        ),
    )
end

function _problem_manifest(problem)
    return Dict{String,Any}(
        "instance_id" => problem.instance_id,
        "family_id" => problem.family_id,
        "replay_checksum" => replay_checksum(problem),
        "saved_starts" => size(problem.saved_starts, 2),
        "configurations" => size(problem.gold_configurations, 2),
        "targets" => length(problem.gold_targets),
    )
end

function git_revision()
    return Dict{String,Any}(
        "git_dirty" => !isempty(strip(read(`git -C $REPOSITORY_ROOT status --porcelain`, String))),
        "git_head" => readchomp(`git -C $REPOSITORY_ROOT rev-parse HEAD`),
    )
end

function print_summary(summaries, final_prefix)
    println(
        "variant,instance,family,callback_prefix,cumulative_callbacks,overshoot," *
        "completed_attempts,assessor_recall,assessor_safe_full,evaluations",
    )
    for summary in summaries
        summary["callback_prefix"] == final_prefix || continue
        println(join((
            summary["variant"],
            summary["instance_id"],
            summary["family_id"],
            summary["callback_prefix"],
            summary["cumulative_callbacks"],
            summary["overshoot_callbacks"],
            summary["completed_attempts"],
            "$(summary["assessor_qualified_targets_found"])/$(summary["target_count"])",
            summary["assessor_safe_all_targets"],
            summary["evaluations"],
        ), ','))
    end
end

function main(arguments=ARGS)
    options = parse_arguments(arguments)
    if options === nothing
        print(usage())
        return nothing
    end
    assert_serial_environment()
    revision = git_revision()
    revision["git_dirty"] && error(
        "EXP-LOCAL-007 formal T0 requires a clean committed worktree; no dirty outcome is allowed",
    )
    all_problems = t0_problems(options[:max_starts])
    problems = shard_problems(
        all_problems,
        options[:shard_index],
        options[:shard_count],
    )
    selected_variants = variants()
    tolerances = SolverExperimentTolerances()
    all_attempts = SolverExperimentAttempt[]
    all_summaries = Dict{String,Any}[]
    first_attempt = Dict(variant.name => Ref(true) for variant in selected_variants)
    for variant in selected_variants, problem in problems
        attempts, summaries = run_case_stream(
            problem,
            variant,
            options[:callback_prefixes],
            options[:max_starts],
            first_attempt[variant.name],
            tolerances,
        )
        append!(all_attempts, attempts)
        append!(all_summaries, summaries)
    end
    document = Dict{String,Any}(
        "schema" => "geotarget.exp-local-007.case-callback-prefix/v1",
        "experiment_id" => ExperimentLocal007.EXPERIMENT_ID,
        "suite" => "t0",
        "attempts" => Any[
            GeoTargetBenchmarks._attempt_document(attempt) for attempt in all_attempts
        ],
        "summaries" => all_summaries,
        "callback_prefixes" => options[:callback_prefixes],
        "prefix_execution" => "single-stream-attempt-boundary-snapshots-no-reruns",
        "problem_manifest" => Any[_problem_manifest(problem) for problem in problems],
        "variant_manifest" => Any[_variant_manifest(variant) for variant in selected_variants],
        "tolerances" => Dict{String,Any}(
            "configuration" => tolerances.configuration,
            "residual" => tolerances.residual,
            "target" => tolerances.target,
        ),
        "assessor_manifest" => Dict{String,Any}(
            "source" => "GeoTargetBenchmarks-common-schema-v2-assessor",
            "qualification_predicate" =>
                "endpoint-present-finite-in-bounds-semantics-valid-scaled-residual-linf",
            "residual_linf_tolerance" => 1.0e-12,
            "configuration_tolerance" => 1.0e-6,
            "target_tolerance" => 1.0e-6,
        ),
        "shard" => Dict{String,Any}(
            "index" => options[:shard_index],
            "count" => options[:shard_count],
            "unsharded_problem_count" => length(all_problems),
            "problem_count" => length(problems),
            "rule" => "zero-based-case-index-modulo-shard-count",
        ),
        "runner_options" => Dict{String,Any}(
            "case_cumulative_callback_thresholds" => options[:callback_prefixes],
            "candidate_attempt_callback_hard_limit" =>
                ExperimentLocal007.DEFAULT_MAX_CALLBACKS,
            "candidate_algorithm_callback_limit" =>
                ExperimentLocal007.DEFAULT_MAX_CALLBACKS - 1,
            "candidate_endpoint_screen_reservation" => 1,
            "runner_attempt_hard_limit" => RUNNER_ATTEMPT_HARD_LIMIT,
            "max_paired_starts" => options[:max_starts],
            "overshoot_policy" => "record-first-completed-attempt-reaching-threshold",
            "primary_work_metric" => "observed-truth-blind-callback-count",
            "wall_time_role" => "diagnostic-python-interop-included",
        ),
        "environment" => Dict{String,Any}(
            "julia_threads" => Threads.nthreads(),
            "julia_blas_threads" => BLAS.get_num_threads(),
            "julia_version" => string(VERSION),
            "machine" => Sys.MACHINE,
            "openblas_num_threads" => ENV["OPENBLAS_NUM_THREADS"],
            "omp_num_threads" => ENV["OMP_NUM_THREADS"],
            "mkl_num_threads" => ENV["MKL_NUM_THREADS"],
            "python_executable" => ExperimentLocal007.PYTHON_EXECUTABLE,
            "python_version" => string(ExperimentLocal007.PythonCall.python_version()),
            "scipy_version" => ExperimentLocal007._package_version(),
        ),
        "revision" => revision,
    )
    output = abspath(options[:output])
    mkpath(dirname(output))
    write(output, canonical_json(document), "\n")
    print_summary(all_summaries, last(options[:callback_prefixes]))
    println("output=$output")
    return document
end

if abspath(PROGRAM_FILE) == abspath(@__FILE__())
    main()
end
