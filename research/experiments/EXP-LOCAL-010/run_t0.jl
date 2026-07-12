using Dates
using GeoTargetBenchmarks
using GeoTargetCore
using JSON3
using LinearAlgebra

const REPOSITORY_ROOT = normpath(joinpath(@__DIR__, "..", "..", ".."))
const CAMPAIGN_PREREGISTRATION = joinpath(@__DIR__, "preregistration.json")
const SVD_PREREGISTRATION = joinpath(
    @__DIR__, "..", "EXP-LOCAL-011", "preregistration.json",
)
const CALLBACK_THRESHOLDS = (600, 1_200, 2_400, 4_800)
const MAXIMUM_STARTS = 64
const ATTEMPT_CALLBACK_CAP = 600

include(joinpath(REPOSITORY_ROOT, "benchmarks", "solver_lab", "CoreBaseline.jl"))
include(joinpath(@__DIR__, "src", "ExperimentLocal010.jl"))
include(joinpath(@__DIR__, "..", "EXP-LOCAL-011", "src", "ExperimentLocal011.jl"))

function variants()
    return SolverVariant[
        GeoTargetSolverLab.core_lmqr_control(:prod_tol_120x600),
        ExperimentLocal010.endpoint_correction_variant(; shadow=false),
        ExperimentLocal010.endpoint_correction_variant(; shadow=true),
        ExperimentLocal011.endpoint_correction_variant(; shadow=false),
        ExperimentLocal011.endpoint_correction_variant(; shadow=true),
    ]
end

function _assessor_metrics(attempts, target_count)
    targets = Set(
        attempt.assessor_matched_target_id for attempt in attempts if
        attempt.assessor_qualified && attempt.assessor_gold_matched &&
        !attempt.assessor_target_ambiguous
    )
    unsafe = count(
        attempt -> attempt.assessor_qualified &&
                   (!attempt.assessor_gold_matched || attempt.assessor_target_ambiguous),
        attempts,
    )
    return (;
        qualified=count(attempt -> attempt.assessor_qualified, attempts),
        targets_found=length(targets),
        target_recall=length(targets) / target_count,
        unsafe,
        safe_full=length(targets) == target_count && unsafe == 0,
    )
end

_assessor_safe(attempt) = !attempt.assessor_qualified ||
    (attempt.assessor_gold_matched && !attempt.assessor_target_ambiguous)

function _suffix_stable_work(attempts, target_count)
    for index in eachindex(attempts)
        _assessor_metrics(@view(attempts[1:index]), target_count).safe_full || continue
        all(_assessor_safe, @view(attempts[index + 1:end])) || continue
        return sum(attempt.evaluations for attempt in @view(attempts[1:index]))
    end
    return nothing
end

function _snapshot(variant, problem, threshold, cumulative, attempt_count, attempts)
    metrics = _assessor_metrics(attempts, length(problem.gold_targets))
    return Dict{String,Any}(
        "assessor_qualified" => metrics.qualified,
        "assessor_safe_full" => metrics.safe_full,
        "assessor_target_recall" => metrics.target_recall,
        "assessor_targets_found" => metrics.targets_found,
        "assessor_unsafe" => metrics.unsafe,
        "callback_threshold" => threshold,
        "crossing_callback_work" => cumulative,
        "crossing_start_index" => attempt_count,
        "family_id" => problem.family_id,
        "instance_id" => problem.instance_id,
        "variant" => variant.name,
    )
end

function _run_case(variant, problem; maximum_starts::Integer=MAXIMUM_STARTS)
    maximum_starts > 0 || throw(ArgumentError("maximum starts must be positive"))
    size(problem.saved_starts, 2) >= maximum_starts ||
        throw(ArgumentError("problem has fewer saved starts than requested"))
    case = GeoTargetBenchmarks._truth_blind_case(problem, ATTEMPT_CALLBACK_CAP)
    attempts = SolverExperimentAttempt[]
    snapshots = Dict{String,Any}[]
    cumulative = 0
    next_threshold = 1
    try
        for start_index in 1:maximum_starts
            attempt = GeoTargetBenchmarks._run_solver_attempt(
                problem,
                case,
                variant,
                start_index,
                start_index == 1 ? :cold_first_use : :warm,
                SolverExperimentTolerances(),
                time_ns,
            )
            push!(attempts, attempt)
            cumulative += attempt.evaluations
            while next_threshold <= length(CALLBACK_THRESHOLDS) &&
                  cumulative >= CALLBACK_THRESHOLDS[next_threshold]
                push!(
                    snapshots,
                    _snapshot(
                        variant,
                        problem,
                        CALLBACK_THRESHOLDS[next_threshold],
                        cumulative,
                        start_index,
                        attempts,
                    ),
                )
                next_threshold += 1
            end
            cumulative >= last(CALLBACK_THRESHOLDS) && break
        end
    finally
        GeoTargetBenchmarks._release_solver_case_oracle!(case._evaluate)
    end
    suffix_work = _suffix_stable_work(attempts, length(problem.gold_targets))
    authoritative_event = suffix_work !== nothing && suffix_work <= last(CALLBACK_THRESHOLDS)
    terminal = Dict{String,Any}(
        "attempt_count" => length(attempts),
        "callback_work" => cumulative,
        "evaluation_count_mismatches" => count(
            attempt -> attempt.evaluation_count_mismatch,
            attempts,
        ),
        "exceptions" => count(attempt -> attempt.exception !== nothing, attempts),
        "family_id" => problem.family_id,
        "instance_id" => problem.instance_id,
        "maximum_start_reached" => length(attempts) == maximum_starts,
        "right_censored_suffix_stable_work" => authoritative_event ? suffix_work : 4_800,
        "runner_budget_exhausted" => count(attempt -> attempt.budget_exhausted, attempts),
        "suffix_stable_event_by_4800" => authoritative_event,
        "suffix_stable_work" => suffix_work,
        "variant" => variant.name,
    )
    return attempts, snapshots, terminal
end

function _thread_contract()
    Threads.nthreads() == 1 || error("run each case process with JULIA_NUM_THREADS=1")
    BLAS.get_num_threads() == 1 || error("run each case process with one BLAS thread")
    for name in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS")
        get(ENV, name, "unset") == "1" || error("$name must be 1")
    end
    return Dict{String,Any}(
        "blas_threads" => BLAS.get_num_threads(),
        "julia_threads" => Threads.nthreads(),
        "openblas_num_threads" => get(ENV, "OPENBLAS_NUM_THREADS", "unset"),
        "omp_num_threads" => get(ENV, "OMP_NUM_THREADS", "unset"),
        "mkl_num_threads" => get(ENV, "MKL_NUM_THREADS", "unset"),
    )
end

function preflight_document()
    problems = GeoTargetSolverLab.representative_problems(; start_count=MAXIMUM_STARTS)
    length(problems) == 9 || error("representative corpus must contain nine cases")
    candidates = variants()
    length(candidates) == 5 && allunique(variant.name for variant in candidates) ||
        error("campaign must contain five unique variants")
    return Dict{String,Any}(
        "attempt_callback_cap" => ATTEMPT_CALLBACK_CAP,
        "callback_thresholds" => collect(CALLBACK_THRESHOLDS),
        "case_count" => length(problems),
        "maximum_starts" => MAXIMUM_STARTS,
        "problem_checksums" => Dict(
            problem.instance_id => replay_checksum(problem) for problem in problems
        ),
        "thread_contract" => _thread_contract(),
        "variants" => [variant.name for variant in candidates],
    )
end

function _git_revision()
    dirty = !isempty(strip(read(`git -C $REPOSITORY_ROOT status --porcelain`, String)))
    return Dict{String,Any}(
        "git_dirty" => dirty,
        "git_head" => readchomp(`git -C $REPOSITORY_ROOT rev-parse HEAD`),
    )
end

function run_campaign(case_index::Integer)
    revision = _git_revision()
    revision["git_dirty"] && error("outcome execution requires a clean committed tree")
    problems = GeoTargetSolverLab.representative_problems(; start_count=MAXIMUM_STARTS)
    1 <= case_index <= length(problems) || error("case index must be in 1:$(length(problems))")
    problem = problems[Int(case_index)]
    document = Dict{String,Any}(
        "attempts" => Any[],
        "case_count" => length(problems),
        "case_index" => Int(case_index),
        "environment" => preflight_document()["thread_contract"],
        "experiment_id" => "EXP-LOCAL-010/011-T0",
        "generated_at_utc" => Dates.format(now(UTC), dateformat"yyyy-mm-ddTHH:MM:SS.sssZ"),
        "prefix_policy" => "snapshot-after-first-completed-attempt-crossing-threshold",
        "problem_manifest" => Any[],
        "revision" => revision,
        "schema" => "geotarget.local-correction-campaign/v1",
        "terminals" => Any[],
        "threshold_snapshots" => Any[],
        "variant_manifest" => Any[],
    )
    selected_variants = variants()
    document["problem_manifest"] = Any[
        Dict(
            "family_id" => problem.family_id,
            "instance_id" => problem.instance_id,
            "replay_checksum" => replay_checksum(problem),
            "targets" => length(problem.gold_targets),
        )
    ]
    document["variant_manifest"] = Any[
        Dict(
            "configuration" => Dict(String(key) => value for (key, value) in pairs(variant.configuration)),
            "name" => variant.name,
        ) for variant in selected_variants
    ]
    for variant in selected_variants
        attempts, snapshots, terminal = _run_case(variant, problem)
        append!(
            document["attempts"],
            (GeoTargetBenchmarks._attempt_document(attempt) for attempt in attempts),
        )
        append!(document["threshold_snapshots"], snapshots)
        push!(document["terminals"], terminal)
    end
    return document
end

function _authorized()
    registrations = (
        JSON3.read(read(CAMPAIGN_PREREGISTRATION, String)),
        JSON3.read(read(SVD_PREREGISTRATION, String)),
    )
    return all(
        registration ->
            get(registration, :outcome_execution_authorized, false) === true,
        registrations,
    )
end

function main(arguments=ARGS)
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
        "exp-local-010-011-t0.json" :
        "exp-local-010-011-t0-case-$(lpad(case_index, 2, '0')).json",
    ) : abspath(arguments[output_argument][length("--output=") + 1:end])
    if !execute
        println(JSON3.write(preflight_document()))
        return nothing
    end
    _authorized() || error("outcome execution is not authorized by preregistration.json")
    case_index !== nothing || error("--case-index=1..9 is required for outcome execution")
    document = run_campaign(case_index)
    mkpath(dirname(output))
    write(output, JSON3.write(document), '\n')
    println("output=$output")
    return document
end

if abspath(PROGRAM_FILE) == abspath(@__FILE__())
    main()
end
