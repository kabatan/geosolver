using GeoTargetBenchmarks
using GeoTargetCore
using LinearAlgebra
using SHA

const REPOSITORY_ROOT = normpath(joinpath(@__DIR__, "..", "..", ".."))

include(joinpath(REPOSITORY_ROOT, "benchmarks", "solver_lab", "CoreBaseline.jl"))
include(joinpath(@__DIR__, "src", "ExperimentLocal008.jl"))
include(joinpath(@__DIR__, "src", "T0Policy.jl"))
using .ExperimentLocal008
using .ExperimentLocal008T0Policy
using .GeoTargetSolverLab

const CALLBACK_PREFIXES = collect(ExperimentLocal008T0Policy.CALLBACK_PREFIXES)
const MAX_STARTS = 512
const RUNNER_ATTEMPT_HARD_LIMIT = 4_800
const T0_CASE_COUNT = 6
const CALLBACK_WORK_CENSOR = 4_800
const PREREGISTRATION_PATH = joinpath(@__DIR__, "preregistration.json")
const T0_EXPECTED_REPLAY = Dict(
    "curved-chain-d4-curve10000.0-i102-s1002" =>
        "8a56042f6ddef9cc097cd1f13fe22b3eb1f376e4ed6a13b7cd70a16f0e566d74",
    "near-rank-d4-ratio1.0e-8-o103-s1003" =>
        "a55330b98965a2a65dc18d93955458ec88b34e14445cff69ff830db028552145",
    "tangent-circle-r1.0-ratio0.999999-i105-s1005" =>
        "0eab38a9ca7da57f68106a9daeb24f06122433b60362f01b3dafe157e3d557ac",
    "multiroot-d4-n4-sep0.001-condition10000.0-warp0.5-targetz1-c106-s1006" =>
        "3e012859175cd8291ffd03db916e618142f449df8a7aa03f1c0c7fe7159b48c9",
    "multiroot-d4-n4-sep0.001-condition10000.0-warp0.5-targetz1_squared-c106-s1006" =>
        "1fce84f2621b79af38bef92cd519f1569691f8bd22c6988bf9bde413d81f2cee",
    "strict-guard-on_boundary-margin0.0-i108-s1008" =>
        "8a3ae1e490fa272ca26b5903b8ff7d956ceb15eaf41d13e526676e71f42cbc13",
)

function usage()
    return """
    Usage: julia --project=research/experiments/EXP-LOCAL-008 \\
      research/experiments/EXP-LOCAL-008/run_t0.jl [options]

      --shard-index=N  Zero-based case shard index (default: 0)
      --shard-count=N  Number of case shards (default: 1)
      --output=PATH    Output JSON
      --help           Show this message

    The preregistered T0 has six cases, paired saved starts, and case-cumulative
    callback snapshots at 600/1200/2400/4800.  Run each shard with Julia, BLAS,
    OpenMP, and MKL thread counts fixed to one.
    """
end

function _parse_integer(value, label; nonnegative=false, positive=false)
    parsed = tryparse(Int, value)
    parsed === nothing && error("$label must be an integer")
    nonnegative && parsed < 0 && error("$label must be nonnegative")
    positive && parsed <= 0 && error("$label must be positive")
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
            options[:shard_index] = _parse_integer(
                argument[length("--shard-index=") + 1:end],
                "shard index";
                nonnegative=true,
            )
        elseif startswith(argument, "--shard-count=")
            options[:shard_count] = _parse_integer(
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
    options[:shard_index] < options[:shard_count] ||
        error("shard index must be less than shard count")
    if options[:output] === nothing
        options[:output] = joinpath(
            REPOSITORY_ROOT,
            "benchmarks",
            "results",
            "raw",
            "exp-local-008-t0-shard-$(options[:shard_index])-of-$(options[:shard_count]).json",
        )
    end
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

function t0_problems(start_count=MAX_STARTS)
    requested = Set((
        "CURVED-CHAIN",
        "NEAR-RANK-DEFICIENT",
        "TANGENT-CIRCLE-LINE",
        "MULTIROOT-WARPED",
        "STRICT-GUARD-BOUNDARY",
    ))
    problems = filter(
        problem -> problem.family_id in requested,
        representative_problems(; start_count),
    )
    length(problems) == T0_CASE_COUNT || error("T0 must contain exactly six cases")
    count(problem -> problem.family_id == "MULTIROOT-WARPED", problems) == 2 ||
        error("T0 must contain both Warped target maps")
    count(problem -> problem.family_id == "STRICT-GUARD-BOUNDARY", problems) == 1 ||
        error("T0 must contain the on-boundary StrictGuard counterexample")
    sum(length(problem.gold_targets) for problem in problems) == 11 ||
        error("T0 must contain exactly 11 Gold targets")
    all(verify_replay_material, problems) || error("T0 replay material failed validation")
    if start_count == MAX_STARTS
        Set(problem.instance_id for problem in problems) == Set(keys(T0_EXPECTED_REPLAY)) ||
            error("T0 instance set drifted after preregistration")
        all(
            problem -> replay_checksum(problem) == T0_EXPECTED_REPLAY[problem.instance_id],
            problems,
        ) || error("T0 replay checksum drifted after preregistration")
    end
    return problems
end

function shard_problems(problems, shard_index, shard_count)
    shard_count <= length(problems) || error("shard count exceeds T0 case count")
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
        orthomads_variant(),
    ]
end

function assert_serial_environment()
    Threads.nthreads() == 1 || error("T0 shards require JULIA_NUM_THREADS=1")
    BLAS.get_num_threads() == 1 || error("T0 shards require one BLAS thread")
    for name in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS")
        get(ENV, name, "") == "1" || error("T0 shards require $name=1")
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
    document["cumulative_callbacks"] = crossing.cumulative_callbacks
    document["overshoot_callbacks"] = crossing.overshoot_callbacks
    return document
end

function _suffix_stable_assessor_work_from_sequence(sequence, target_count::Int)
    target_count > 0 || throw(ArgumentError("target count must be positive"))
    ordered = sort(collect(sequence); by=attempt -> attempt.start_index)
    [attempt.start_index for attempt in ordered] == collect(1:length(ordered)) ||
        error("raw common-assessor attempt sequence is incomplete")
    assessor_safe(attempt) = !attempt.assessor_qualified ||
                               (attempt.assessor_gold_matched &&
                                !attempt.assessor_target_ambiguous)
    for start_index in eachindex(ordered)
        prefix_attempts = @view ordered[1:start_index]
        metrics = GeoTargetBenchmarks._assessor_metrics(prefix_attempts, target_count)
        metrics.safe_all_targets || continue
        all(assessor_safe, @view(ordered[start_index + 1:end])) || continue
        return sum(attempt.evaluations for attempt in prefix_attempts)
    end
    return nothing
end

function _right_censored_assessor_work(suffix_work, threshold::Int=CALLBACK_WORK_CENSOR)
    threshold > 0 || throw(ArgumentError("censoring threshold must be positive"))
    event = suffix_work !== nothing && 0 <= suffix_work <= threshold
    return (work=event ? Int(suffix_work) : threshold, event)
end

function _diagnostic_integer(diagnostic, key)
    diagnostic === nothing && return 0
    prefix = String(key) * "="
    for field in split(diagnostic, ';')
        startswith(field, prefix) || continue
        parsed = tryparse(Int, field[length(prefix) + 1:end])
        parsed === nothing && error("diagnostic field $key is not an integer")
        return parsed
    end
    return 0
end

function _qualified_extreme_barrier_recoveries(attempts)
    return count(attempts) do attempt
        attempt.assessor_qualified && attempt.assessor_gold_matched &&
        !attempt.assessor_target_ambiguous &&
        _diagnostic_integer(attempt.diagnostic, "extreme_barrier_callbacks") > 0
    end
end

function run_case_stream(problem, variant, first_attempt, tolerances)
    case = GeoTargetBenchmarks._truth_blind_case(problem, RUNNER_ATTEMPT_HARD_LIMIT)
    attempts = SolverExperimentAttempt[]
    summaries = Dict{String,Any}[]
    tracker = CallbackPrefixTracker(CALLBACK_PREFIXES)
    try
        for start_index in 1:MAX_STARTS
            phase = first_attempt[] ? :cold_first_use : :warm
            attempt = GeoTargetBenchmarks._run_solver_attempt(
                problem,
                case,
                variant,
                start_index,
                phase,
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
                push!(summaries, _summary_document(summary, crossing))
            end
            tracker_complete(tracker) && break
        end
    finally
        GeoTargetBenchmarks._release_solver_case_oracle!(case._evaluate)
    end
    tracker_complete(tracker) || error(
        "$(variant.name) / $(problem.instance_id) did not reach 4800 callbacks",
    )
    suffix_work = _suffix_stable_assessor_work_from_sequence(
        attempts,
        length(problem.gold_targets),
    )
    censored = _right_censored_assessor_work(suffix_work)
    recoveries = _qualified_extreme_barrier_recoveries(attempts)
    for summary in summaries
        summary["callback_prefix"] == CALLBACK_WORK_CENSOR || continue
        summary["suffix_stable_evaluations_to_assessor_safe_full"] = suffix_work
        summary["right_censored_assessor_safe_full_work"] = censored.work
        summary["assessor_safe_full_event_by_4800"] = censored.event
        summary["qualified_extreme_barrier_recoveries"] = recoveries
        summary["callback_work_authority"] =
            "raw-common-assessor-attempt-fields-not-lab-safe-full-field"
    end
    return attempts, summaries
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

function main(arguments=ARGS)
    options = parse_arguments(arguments)
    options === nothing && return print(usage())
    assert_serial_environment()
    revision = git_revision()
    revision["git_dirty"] && error("T0 outcome requires a clean committed worktree")
    revision["preregistration_sha256"] = bytes2hex(sha256(read(PREREGISTRATION_PATH)))
    all_problems = t0_problems()
    problems = shard_problems(all_problems, options[:shard_index], options[:shard_count])
    selected_variants = variants()
    tolerances = SolverExperimentTolerances()
    all_attempts = SolverExperimentAttempt[]
    all_summaries = Dict{String,Any}[]
    first_attempt = Dict(variant.name => Ref(true) for variant in selected_variants)
    for variant in selected_variants, problem in problems
        attempts, summaries = run_case_stream(
            problem,
            variant,
            first_attempt[variant.name],
            tolerances,
        )
        append!(all_attempts, attempts)
        append!(all_summaries, summaries)
    end
    document = Dict{String,Any}(
        "schema" => "geotarget.exp-local-008.callback-prefix/v1",
        "experiment_id" => EXPERIMENT_ID,
        "suite" => "t0",
        "attempts" => Any[
            GeoTargetBenchmarks._attempt_document(attempt) for attempt in all_attempts
        ],
        "summaries" => all_summaries,
        "callback_prefixes" => CALLBACK_PREFIXES,
        "problem_manifest" => Any[_problem_manifest(problem) for problem in problems],
        "variant_manifest" => Any[_variant_manifest(variant) for variant in selected_variants],
        "assessor_manifest" => Dict{String,Any}(
            "source" => "GeoTargetBenchmarks-common-schema-v2-assessor",
            "residual_linf_tolerance" => 1.0e-12,
            "configuration_tolerance" => 1.0e-6,
            "target_tolerance" => 1.0e-6,
        ),
        "shard" => Dict{String,Any}(
            "index" => options[:shard_index],
            "count" => options[:shard_count],
            "unsharded_problem_count" => length(all_problems),
            "problem_count" => length(problems),
        ),
        "runner_options" => Dict{String,Any}(
            "candidate_attempt_callback_hard_limit" => DEFAULT_MAX_CALLBACKS,
            "candidate_algorithm_callback_limit" => DEFAULT_MAX_CALLBACKS - 1,
            "runner_attempt_hard_limit" => RUNNER_ATTEMPT_HARD_LIMIT,
            "max_paired_starts" => MAX_STARTS,
            "stream_prefix_axis" => "case-cumulative-observed-truth-blind-callback-count",
            "primary_work_metric" =>
                "per-case-raw-common-assessor-suffix-stable-safe-full-right-censored-at-4800",
            "callback_work_censor" => CALLBACK_WORK_CENSOR,
            "wall_time_role" => "diagnostic-only",
        ),
        "environment" => Dict{String,Any}(
            "julia_threads" => Threads.nthreads(),
            "julia_blas_threads" => BLAS.get_num_threads(),
            "julia_version" => string(VERSION),
            "machine" => Sys.MACHINE,
            "openblas_num_threads" => ENV["OPENBLAS_NUM_THREADS"],
            "omp_num_threads" => ENV["OMP_NUM_THREADS"],
            "mkl_num_threads" => ENV["MKL_NUM_THREADS"],
        ),
        "revision" => revision,
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
