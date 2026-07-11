# Reuse the committed T0 callback accounting, common assessor adapters and
# candidate construction without changing the outcome-producing T0 source.
include(joinpath(@__DIR__, "run_t0.jl"))
include(joinpath(@__DIR__, "src", "T1Policy.jl"))
using .ExperimentLocal007T1Policy

const T1_DEFAULT_CALLBACK_PREFIXES = collect(ExperimentLocal007T1Policy.CALLBACK_PREFIXES)
const T1_DEFAULT_MAX_STARTS = 512
const T1_EXPECTED_CASE_COUNT = 9
const T1_EXPECTED_APPLICABLE_CASE_COUNT = 8
const T1_TYPED_INAPPLICABLE_STATUS = "INAPPLICABLE_NONSQUARE"

function t1_usage()
    return """
    Usage: julia --project=research/experiments/EXP-LOCAL-007 \
      research/experiments/EXP-LOCAL-007/run_t1.jl [options]

      --callback-prefixes=600,1200,2400,4800
                           Sorted case-cumulative callback thresholds
      --max-starts=N       Saved starts generated per case (default: 512)
      --shard-index=N      Zero-based case shard index (default: 0)
      --shard-count=N      Number of outer case shards (default: 1)
      --output=PATH        Output JSON (default is experiment-local and ignored)
      --help               Show this message

    Normal applicable streams snapshot the first completed attempt crossing
    each callback threshold. The public nonsquare HYBR inapplicability is a
    zero-callback terminal observation and is explicitly repeated at all four
    threshold labels with threshold_reached=false; it is never credited as
    performance or silently removed from the representative-nine corpus.
    """
end

function parse_t1_arguments(arguments)
    options = Dict{Symbol,Any}(
        :callback_prefixes => copy(T1_DEFAULT_CALLBACK_PREFIXES),
        :max_starts => T1_DEFAULT_MAX_STARTS,
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
    prefixes == T1_DEFAULT_CALLBACK_PREFIXES || error(
        "formal EXP-LOCAL-007 T1 prefixes are frozen at " *
        join(T1_DEFAULT_CALLBACK_PREFIXES, ','),
    )
    options[:max_starts] == T1_DEFAULT_MAX_STARTS || error(
        "formal EXP-LOCAL-007 T1 saved-start count is frozen at $T1_DEFAULT_MAX_STARTS",
    )
    options[:shard_index] < options[:shard_count] ||
        error("shard index must be less than shard count")
    options[:shard_count] <= T1_EXPECTED_CASE_COUNT ||
        error("shard count cannot exceed the nine-case T1 corpus")
    options[:output] === nothing && (options[:output] = joinpath(
        @__DIR__,
        "results",
        "t1-callback-prefix-$(last(prefixes))-shard-$(options[:shard_index])-of-$(options[:shard_count]).json",
    ))
    return options
end

function t1_problems(start_count)
    start_count == T1_DEFAULT_MAX_STARTS || error(
        "T1 replay material is frozen at $T1_DEFAULT_MAX_STARTS saved starts per case",
    )
    problems = representative_problems(; start_count)
    length(problems) == T1_EXPECTED_CASE_COUNT ||
        error("T1 representative corpus must contain exactly nine cases")
    allunique(problem.instance_id for problem in problems) ||
        error("T1 instance identifiers must be unique")
    all(verify_replay_material, problems) ||
        error("T1 replay material failed checksum or paired-start validation")
    expected = Dict(entry.instance_id => entry for entry in
                    ExperimentLocal007T1Policy.EXPECTED_CORPUS)
    Set(problem.instance_id for problem in problems) == Set(keys(expected)) ||
        error("T1 instance set changed after preregistration")
    for problem in problems
        frozen = expected[problem.instance_id]
        problem.family_id == frozen.family_id ||
            error("T1 family changed for $(problem.instance_id)")
        problem.dimension == frozen.dimension ||
            error("T1 dimension changed for $(problem.instance_id)")
        problem.residual_dimension == frozen.residual_dimension ||
            error("T1 residual dimension changed for $(problem.instance_id)")
        replay_checksum(problem) == frozen.replay_checksum ||
            error("T1 replay checksum changed for $(problem.instance_id)")
    end
    applicable = count(
        problem -> problem.dimension == problem.residual_dimension,
        problems,
    )
    applicable == T1_EXPECTED_APPLICABLE_CASE_COUNT || error(
        "T1 must contain eight square-applicable cases and one public nonsquare case",
    )
    count(
        problem -> problem.dimension != problem.residual_dimension,
        problems,
    ) == 1 || error("T1 must contain exactly one typed-inapplicable nonsquare case")
    Set(problem.family_id for problem in problems if
        problem.dimension == problem.residual_dimension) ==
        Set(ExperimentLocal007T1Policy.APPLICABLE_FAMILIES) ||
        error("T1 square-applicable family set changed after preregistration")
    Set(problem.family_id for problem in problems if
        problem.dimension != problem.residual_dimension) ==
        Set(ExperimentLocal007T1Policy.EXPECTED_INAPPLICABLE_FAMILIES) ||
        error("T1 typed-inapplicable family set changed after preregistration")
    return problems
end

function _is_typed_terminal_inapplicable(attempt, problem)
    attempt.status == T1_TYPED_INAPPLICABLE_STATUS || return false
    problem.dimension != problem.residual_dimension || error(
        "typed nonsquare inapplicability was returned for a square problem",
    )
    attempt.evaluations == 0 || error("typed inapplicability must use zero callbacks")
    attempt.reported_evaluations == 0 ||
        error("typed inapplicability must report zero callbacks")
    attempt.endpoint === nothing || error("typed inapplicability must have no endpoint")
    !attempt.reported_accepted || error("typed inapplicability cannot be accepted")
    !attempt.reported_converged || error("typed inapplicability cannot be converged")
    !attempt.budget_exhausted || error("typed inapplicability cannot exhaust the runner")
    attempt.exception === nothing || error("typed inapplicability cannot be an exception")
    return true
end

function _t1_crossing_summary(summary, crossing)
    document = _summary_document(summary, crossing)
    document["threshold_reached"] = true
    document["callback_shortfall"] = 0
    document["terminal_inapplicable"] = false
    document["terminal_status"] = nothing
    return document
end

function _t1_inapplicable_summary(summary, threshold)
    document = GeoTargetBenchmarks._prefix_document(summary)
    document["saved_start_prefix"] = 1
    document["prefix"] = threshold
    document["callback_prefix"] = threshold
    document["prefix_unit"] = "case-cumulative-observed-callbacks"
    document["completed_attempts"] = 1
    document["crossing_attempt_start_index"] = nothing
    document["cumulative_callbacks"] = 0
    document["overshoot_callbacks"] = nothing
    document["callback_shortfall"] = threshold
    document["threshold_reached"] = false
    document["snapshot_boundary"] = "typed-inapplicable-zero-callback-terminal"
    document["terminal_inapplicable"] = true
    document["terminal_status"] = T1_TYPED_INAPPLICABLE_STATUS
    document["suffix_stable_evaluations_to_lab_safe_full"] = nothing
    document["suffix_stable_evaluations_to_assessor_safe_full"] = nothing
    document["right_censored_assessor_safe_full_work"] = nothing
    document["assessor_safe_full_event_by_4800"] = false
    return document
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
    length(sequence) == maximum_start || error("T1 assessor sequence is incomplete")
    sort!(sequence; by=attempt -> attempt.start_index)
    return _suffix_stable_assessor_work_from_sequence(
        sequence,
        length(problem.gold_targets),
    )
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


function _right_censored_assessor_work(suffix_work, threshold::Int)
    threshold > 0 || throw(ArgumentError("censoring threshold must be positive"))
    event = suffix_work !== nothing && 0 <= suffix_work <= threshold
    return (work=event ? Int(suffix_work) : threshold, event)
end

function run_t1_case_stream(
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
    terminal_inapplicable = false
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
            if _is_typed_terminal_inapplicable(attempt, problem)
                start_index == 1 || error(
                    "typed inapplicability must be stable and appear on the first paired start",
                )
                terminal_inapplicable = true
                summary = GeoTargetBenchmarks._prefix_summary(
                    problem,
                    variant,
                    attempts,
                    1,
                    nothing,
                )
                append!(snapshots, (
                    _t1_inapplicable_summary(summary, threshold) for
                    threshold in callback_prefixes
                ))
                break
            elseif startswith(attempt.status, "INAPPLICABLE_")
                error("unregistered typed inapplicability: $(attempt.status)")
            elseif problem.dimension != problem.residual_dimension &&
                   variant.name == ExperimentLocal007T1Policy.CANDIDATE
                error("HYBR must fail closed as typed-inapplicable on the nonsquare case")
            end
            crossings = record_attempt!(tracker, attempt.evaluations, start_index)
            for crossing in crossings
                summary = GeoTargetBenchmarks._prefix_summary(
                    problem,
                    variant,
                    attempts,
                    start_index,
                    nothing,
                )
                push!(snapshots, _t1_crossing_summary(summary, crossing))
            end
            tracker_complete(tracker) && break
        end
    finally
        GeoTargetBenchmarks._release_solver_case_oracle!(case._evaluate)
    end
    if terminal_inapplicable
        length(snapshots) == length(callback_prefixes) ||
            error("typed-inapplicable stream did not materialize all threshold labels")
        return attempts, snapshots
    end
    tracker_complete(tracker) || error(
        "$(variant.name) / $(problem.instance_id) did not reach callback prefix " *
        "$(last(callback_prefixes)) within $max_starts paired starts; reached " *
        "$(tracker.cumulative_callbacks)",
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
    censoring_threshold = last(callback_prefixes)
    censored = _right_censored_assessor_work(
        assessor_suffix_stable,
        censoring_threshold,
    )
    for snapshot in snapshots
        snapshot["suffix_stable_evaluations_to_lab_safe_full"] = lab_suffix_stable
        snapshot["suffix_stable_evaluations_to_assessor_safe_full"] =
            assessor_suffix_stable
        snapshot["right_censored_assessor_safe_full_work"] = censored.work
        snapshot["assessor_safe_full_event_by_4800"] = censored.event
    end
    return attempts, snapshots
end

function t1_main(arguments=ARGS)
    options = parse_t1_arguments(arguments)
    if options === nothing
        print(t1_usage())
        return nothing
    end
    assert_serial_environment()
    revision = git_revision()
    revision["git_dirty"] && error(
        "EXP-LOCAL-007 formal T1 requires a clean committed worktree; no dirty outcome is allowed",
    )
    all_problems = t1_problems(options[:max_starts])
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
        attempts, summaries = run_t1_case_stream(
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
        "schema" => "geotarget.exp-local-007.t1-case-callback-prefix/v1",
        "experiment_id" => ExperimentLocal007.EXPERIMENT_ID,
        "suite" => "t1-representative-nine",
        "attempts" => Any[
            GeoTargetBenchmarks._attempt_document(attempt) for attempt in all_attempts
        ],
        "summaries" => all_summaries,
        "callback_prefixes" => options[:callback_prefixes],
        "prefix_execution" =>
            "single-stream-attempt-boundary-snapshots-no-reruns-with-explicit-zero-callback-inapplicability",
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
        "promotion_gate_preregistration" => promotion_gate_contract(),
        "inapplicability_policy" => Dict{String,Any}(
            "predicate" => "residual_dimension!=dimension",
            "status" => T1_TYPED_INAPPLICABLE_STATUS,
            "callbacks" => 0,
            "threshold_snapshot" => "terminal-with-threshold_reached=false",
            "performance_denominator" => "excluded-by-public-preregistered-applicability",
            "production_claim" => "not-supported",
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
            "primary_work_metric" =>
                "per-case-suffix-stable-assessor-safe-full-callbacks-right-censored-at-4800",
            "work_miss_value" => last(options[:callback_prefixes]),
            "wall_time_metric" =>
                "sum-end-to-end-attempt-wall-including-cold-python-interop-per-case-shard",
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
    t1_main()
end
