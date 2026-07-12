using GeoTargetBenchmarks
using GeoTargetCore
using LinearAlgebra
using SHA

const REPOSITORY_ROOT = normpath(joinpath(@__DIR__, "..", "..", ".."))

include(joinpath(REPOSITORY_ROOT, "benchmarks", "solver_lab", "CoreBaseline.jl"))
include(joinpath(@__DIR__, "src", "ExperimentLocal009.jl"))
include(joinpath(@__DIR__, "src", "T0Policy.jl"))
using .ExperimentLocal009
using .ExperimentLocal009T0Policy
using .GeoTargetSolverLab

const T0_MAX_STARTS = 512
const T0_CASE_COUNT = 6
const RUNNER_ATTEMPT_HARD_LIMIT = 4_800
const PREREGISTRATION_PATH = joinpath(@__DIR__, "t0-preregistration.json")

function usage()
    return """
    Usage: julia --project=julia research/experiments/EXP-LOCAL-009/run_t0.jl [options]

      --shard-index=N   Zero-based case shard (default: 0)
      --shard-count=N   Case shard count, at most 6 (default: 1)
      --output=PATH     Output JSON (default: benchmarks/results/raw/...)
      --help            Show this message

    The corpus, 512 paired starts, variants and cumulative callback thresholds
    600/1200/2400/4800 are frozen and cannot be changed from the command line.
    """
end

function _parse_int(value, label; positive=false, nonnegative=false)
    parsed = tryparse(Int, value)
    parsed === nothing && error("$label must be an integer")
    positive && parsed <= 0 && error("$label must be positive")
    nonnegative && parsed < 0 && error("$label must be nonnegative")
    return parsed
end

function parse_arguments(arguments)
    options = Dict{Symbol,Any}(
        :shard_index => 0,
        :shard_count => 1,
        :output => nothing,
    )
    for argument in arguments
        argument == "--help" && return nothing
        if startswith(argument, "--shard-index=")
            options[:shard_index] = _parse_int(
                argument[length("--shard-index=") + 1:end],
                "shard index";
                nonnegative=true,
            )
        elseif startswith(argument, "--shard-count=")
            options[:shard_count] = _parse_int(
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
    options[:shard_count] <= T0_CASE_COUNT || error("shard count cannot exceed six")
    options[:shard_index] < options[:shard_count] ||
        error("shard index must be less than shard count")
    options[:output] === nothing && (options[:output] = joinpath(
        REPOSITORY_ROOT,
        "benchmarks",
        "results",
        "raw",
        "exp-local-009-t0-shard-$(options[:shard_index])-of-$(options[:shard_count]).json",
    ))
    return options
end

function t0_problems()
    requested = Set((
        "CURVED-CHAIN",
        "NEAR-RANK-DEFICIENT",
        "TANGENT-CIRCLE-LINE",
        "MULTIROOT-WARPED",
        "STRICT-GUARD-BOUNDARY",
    ))
    problems = filter(
        problem -> problem.family_id in requested,
        representative_problems(; start_count=T0_MAX_STARTS),
    )
    length(problems) == T0_CASE_COUNT ||
        error("T0 must contain the original five cases plus one strict-guard case")
    count(problem -> problem.family_id == "MULTIROOT-WARPED", problems) == 2 ||
        error("T0 must retain both Warped target maps")
    count(problem -> problem.family_id == "STRICT-GUARD-BOUNDARY", problems) == 1 ||
        error("T0 must contain exactly one strict-guard counterexample")
    all(verify_replay_material, problems) || error("T0 replay material is invalid")
    all(problem -> problem.dimension == problem.residual_dimension, problems) ||
        error("T0 candidate screen is frozen to square systems")
    return problems
end

function shard_problems(problems, shard_index, shard_count)
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
        restoring_gn_variant(),
    ]
end

mutable struct CallbackPrefixTracker
    thresholds::Vector{Int}
    next_index::Int
    callbacks::Int
end

CallbackPrefixTracker() = CallbackPrefixTracker(collect(Int, CALLBACK_PREFIXES), 1, 0)
tracker_complete(tracker) = tracker.next_index > length(tracker.thresholds)

function record_attempt!(tracker, callbacks, start_index)
    callbacks >= 0 || throw(ArgumentError("callbacks must be nonnegative"))
    tracker.callbacks += callbacks
    crossings = NamedTuple[]
    while !tracker_complete(tracker) &&
          tracker.callbacks >= tracker.thresholds[tracker.next_index]
        threshold = tracker.thresholds[tracker.next_index]
        push!(crossings, (;
            threshold,
            start_index,
            callbacks=tracker.callbacks,
            overshoot=tracker.callbacks - threshold,
        ))
        tracker.next_index += 1
    end
    return crossings
end

function _snapshot(summary, crossing)
    document = GeoTargetBenchmarks._prefix_document(summary)
    document["saved_start_prefix"] = document["prefix"]
    document["prefix"] = crossing.threshold
    document["callback_prefix"] = crossing.threshold
    document["prefix_unit"] = "case-cumulative-observed-callbacks"
    document["completed_attempts"] = crossing.start_index
    document["cumulative_callbacks"] = crossing.callbacks
    document["overshoot_callbacks"] = crossing.overshoot
    return document
end

function _suffix_stable_assessor_work_from_sequence(sequence, target_count::Int)
    target_count > 0 || throw(ArgumentError("target count must be positive"))
    assessor_safe(attempt) = !attempt.assessor_qualified ||
                               (attempt.assessor_gold_matched &&
                                !attempt.assessor_target_ambiguous)
    for start_index in eachindex(sequence)
        prefix_attempts = @view sequence[1:start_index]
        metrics = GeoTargetBenchmarks._assessor_metrics(prefix_attempts, target_count)
        metrics.safe_all_targets || continue
        all(assessor_safe, @view(sequence[start_index + 1:end])) || continue
        return sum(attempt.evaluations for attempt in prefix_attempts)
    end
    return nothing
end

function _suffix_stable_evaluations_to_assessor_safe_full(
    problem,
    variant,
    attempts,
    maximum_start,
)
    sequence = GeoTargetBenchmarks._selected_attempts(
        problem,
        variant,
        attempts,
        maximum_start,
    )
    length(sequence) == maximum_start || error("T0 assessor sequence is incomplete")
    sort!(sequence; by=attempt -> attempt.start_index)
    return _suffix_stable_assessor_work_from_sequence(
        sequence,
        length(problem.gold_targets),
    )
end

function _right_censored_assessor_work(suffix_work, threshold::Int)
    threshold > 0 || throw(ArgumentError("censoring threshold must be positive"))
    event = suffix_work !== nothing && 0 <= suffix_work <= threshold
    return (work=event ? Int(suffix_work) : threshold, event)
end

function _diagnostic_integer(diagnostic, key)
    diagnostic === nothing && return 0
    prefix = String(key) * "="
    for field in split(diagnostic, ';')
        startswith(field, prefix) || continue
        value = tryparse(Int, field[length(prefix) + 1:end])
        value === nothing && error("diagnostic field $key is not an integer")
        return value
    end
    return 0
end

function _qualified_invalid_trial_recoveries(attempts)
    return count(attempts) do attempt
        recovered = any(
            _diagnostic_integer(attempt.diagnostic, key) > 0 for key in (
                "restored_starts",
                "fd_sign_reversals",
                "fd_invalid_trials",
                "invalid_line_search_trials",
            )
        )
        attempt.assessor_qualified && attempt.assessor_gold_matched &&
        !attempt.assessor_target_ambiguous && recovered
    end
end

function run_case_stream(problem, variant, first_attempt, tolerances)
    case = GeoTargetBenchmarks._truth_blind_case(problem, RUNNER_ATTEMPT_HARD_LIMIT)
    attempts = SolverExperimentAttempt[]
    snapshots = Dict{String,Any}[]
    tracker = CallbackPrefixTracker()
    try
        for start_index in 1:T0_MAX_STARTS
            attempt = GeoTargetBenchmarks._run_solver_attempt(
                problem,
                case,
                variant,
                start_index,
                first_attempt[] ? :cold_first_use : :warm,
                tolerances,
                time_ns,
            )
            first_attempt[] = false
            push!(attempts, attempt)
            for crossing in record_attempt!(tracker, attempt.evaluations, start_index)
                summary = GeoTargetBenchmarks._prefix_summary(
                    problem,
                    variant,
                    attempts,
                    start_index,
                    nothing,
                )
                push!(snapshots, _snapshot(summary, crossing))
            end
            tracker_complete(tracker) && break
        end
    finally
        GeoTargetBenchmarks._release_solver_case_oracle!(case._evaluate)
    end
    tracker_complete(tracker) || error(
        "$(variant.name) / $(problem.instance_id) reached only $(tracker.callbacks) callbacks",
    )
    lab_suffix_stable = GeoTargetBenchmarks._suffix_stable_evaluations_to_lab_safe_full(
        problem,
        variant,
        attempts,
        length(attempts),
    )
    assessor_suffix_stable = _suffix_stable_evaluations_to_assessor_safe_full(
        problem,
        variant,
        attempts,
        length(attempts),
    )
    censored = _right_censored_assessor_work(
        assessor_suffix_stable,
        last(CALLBACK_PREFIXES),
    )
    recoveries = _qualified_invalid_trial_recoveries(attempts)
    for snapshot in snapshots
        snapshot["callback_prefix"] == last(CALLBACK_PREFIXES) || continue
        snapshot["suffix_stable_evaluations_to_lab_safe_full"] = lab_suffix_stable
        snapshot["suffix_stable_evaluations_to_assessor_safe_full"] =
            assessor_suffix_stable
        snapshot["right_censored_assessor_safe_full_work"] = censored.work
        snapshot["assessor_safe_full_event_by_4800"] = censored.event
        snapshot["qualified_invalid_trial_recoveries"] = recoveries
        snapshot["callback_work_authority"] =
            "raw-common-assessor-attempt-fields-not-lab-safe-full-field"
    end
    return attempts, snapshots
end

function assert_execution_environment()
    Threads.nthreads() == 1 || error("T0 requires JULIA_NUM_THREADS=1")
    BLAS.get_num_threads() == 1 || error("T0 requires one Julia BLAS thread")
    for name in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS")
        get(ENV, name, "") == "1" || error("T0 requires $name=1")
    end
    status = strip(read(`git -C $REPOSITORY_ROOT status --porcelain`, String))
    isempty(status) || error("T0 requires a clean committed worktree")
    return nothing
end

_configuration_value(value::Symbol) = String(value)
_configuration_value(value) = value

function main(arguments=ARGS)
    options = parse_arguments(arguments)
    options === nothing && return print(usage())
    assert_execution_environment()
    all_problems = t0_problems()
    problems = shard_problems(all_problems, options[:shard_index], options[:shard_count])
    selected_variants = variants()
    tolerances = SolverExperimentTolerances()
    attempts = SolverExperimentAttempt[]
    summaries = Dict{String,Any}[]
    first_attempt = Dict(variant.name => Ref(true) for variant in selected_variants)
    for variant in selected_variants, problem in problems
        stream_attempts, stream_summaries = run_case_stream(
            problem,
            variant,
            first_attempt[variant.name],
            tolerances,
        )
        append!(attempts, stream_attempts)
        append!(summaries, stream_summaries)
    end
    document = Dict{String,Any}(
        "schema" => "geotarget.exp-local-009.callback-prefix/v1",
        "experiment_id" => EXPERIMENT_ID,
        "suite" => "t0-preregistered",
        "attempts" => Any[GeoTargetBenchmarks._attempt_document(value) for value in attempts],
        "summaries" => summaries,
        "callback_prefixes" => collect(CALLBACK_PREFIXES),
        "problem_manifest" => Any[Dict{String,Any}(
            "instance_id" => problem.instance_id,
            "family_id" => problem.family_id,
            "replay_checksum" => replay_checksum(problem),
            "saved_starts" => size(problem.saved_starts, 2),
            "target_count" => length(problem.gold_targets),
        ) for problem in problems],
        "variant_manifest" => Any[Dict{String,Any}(
            "name" => variant.name,
            "configuration" => Dict{String,Any}(
                String(key) => _configuration_value(value) for
                (key, value) in pairs(variant.configuration)
            ),
        ) for variant in selected_variants],
        "shard" => Dict(
            "index" => options[:shard_index],
            "count" => options[:shard_count],
            "unsharded_case_count" => T0_CASE_COUNT,
        ),
        "runner" => Dict(
            "max_paired_starts" => T0_MAX_STARTS,
            "attempt_hard_limit" => RUNNER_ATTEMPT_HARD_LIMIT,
            "candidate_hard_limit" => DEFAULT_MAX_EVALUATIONS,
            "primary_work_metric" =>
                "suffix-stable-common-assessor-safe-full-right-censored-at-4800-per-case",
            "lab_suffix_work_role" => "diagnostic-only-not-gate-authority",
            "wall_time_role" => "diagnostic-only",
        ),
        "environment" => Dict(
            "julia_version" => string(VERSION),
            "julia_threads" => Threads.nthreads(),
            "blas_threads" => BLAS.get_num_threads(),
            "machine" => Sys.MACHINE,
            "openblas_num_threads" => ENV["OPENBLAS_NUM_THREADS"],
            "omp_num_threads" => ENV["OMP_NUM_THREADS"],
            "mkl_num_threads" => ENV["MKL_NUM_THREADS"],
        ),
        "revision" => Dict(
            "git_head" => readchomp(`git -C $REPOSITORY_ROOT rev-parse HEAD`),
            "preregistration_sha256" => bytes2hex(sha256(read(PREREGISTRATION_PATH))),
        ),
    )
    output = abspath(options[:output])
    ispath(output) && error("refusing to replace T0 output: $output")
    mkpath(dirname(output))
    write(output, canonical_json(document), "\n")
    println("output=$output")
    return document
end

if abspath(PROGRAM_FILE) == abspath(@__FILE__())
    main()
end
