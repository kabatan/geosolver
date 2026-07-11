using GeoTargetBenchmarks
using GeoTargetCore

const REPOSITORY_ROOT = normpath(joinpath(@__DIR__, "..", "..", ".."))

include(joinpath(REPOSITORY_ROOT, "benchmarks", "solver_lab", "CoreBaseline.jl"))
include(joinpath(REPOSITORY_ROOT, "benchmarks", "solver_lab", "NativeSafeguardedLM.jl"))
include(joinpath(@__DIR__, "src", "ExperimentLocal004.jl"))
using .ExperimentLocal004
using .GeoTargetNativeSafeguardedLM
using .GeoTargetSolverLab

function usage()
    return """
    Usage: julia --project=research/experiments/EXP-LOCAL-002 \\
      research/experiments/EXP-LOCAL-004/run_t0.jl [options]

      --prefixes=2,4,8   Sorted saved-start prefixes (default: 2,4,8)
      --suite=t0|t1      Five-case screen or representative nine cases (default: t0)
      --output=PATH      Output JSON (default: benchmarks/results/raw/exp-local-004-t0.json)
      --help             Show this message
    """
end

function parse_positive(value, label)
    parsed = tryparse(Int, value)
    parsed !== nothing && parsed > 0 || error("$label must be a positive integer")
    return parsed
end

function parse_arguments(arguments)
    options = Dict{Symbol,Any}(
        :prefixes => [2, 4, 8],
        :suite => :t0,
        :output => joinpath(
            REPOSITORY_ROOT,
            "benchmarks",
            "results",
            "raw",
            "exp-local-004-t0.json",
        ),
    )
    for argument in arguments
        argument == "--help" && return nothing
        if startswith(argument, "--prefixes=")
            raw = split(argument[length("--prefixes=") + 1:end], ',')
            options[:prefixes] = [parse_positive(value, "prefix") for value in raw]
        elseif startswith(argument, "--suite=")
            suite = Symbol(argument[length("--suite=") + 1:end])
            suite in (:t0, :t1) || error("suite must be t0 or t1")
            options[:suite] = suite
        elseif startswith(argument, "--output=")
            output = argument[length("--output=") + 1:end]
            isempty(output) && error("output path must be nonempty")
            options[:output] = abspath(output)
        else
            error("unknown option: $argument")
        end
    end
    prefixes = options[:prefixes]
    issorted(prefixes) && allunique(prefixes) || error("prefixes must be sorted and unique")
    return options
end

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
    length(problems) == 5 || error("T0 must contain Curved, NearRank, Tangent and two Warped maps")
    count(problem -> problem.family_id == "MULTIROOT-WARPED", problems) == 2 ||
        error("T0 must contain both Warped target maps")
    return problems
end

function selected_problems(suite::Symbol, start_count)
    suite === :t0 && return t0_problems(start_count)
    suite === :t1 || throw(ArgumentError("suite must be t0 or t1"))
    problems = representative_problems(; start_count)
    length(problems) == 9 || error("T1 must contain the nine representative cases")
    return problems
end

function variants(suite::Symbol)
    controls = SolverVariant[
        core_lmqr_control(:legacy_lab_120x600),
        core_lmqr_control(:prod_tol_120x600),
        core_lmqr_control(:prod_options_250x2000),
    ]
    suite === :t1 && return [controls; nls_tr_variant()]
    suite === :t0 || throw(ArgumentError("suite must be t0 or t1"))
    return [
        controls;
        nls_tr_variant();
        nls_lm_variant();
        native_safeguarded_lm_variant(
            max_iterations=250,
            max_evaluations=2_000,
        );
    ]
end

function git_revision()
    return Dict{String,Any}(
        "git_dirty" => !isempty(strip(read(`git -C $REPOSITORY_ROOT status --porcelain`, String))),
        "git_head" => readchomp(`git -C $REPOSITORY_ROOT rev-parse HEAD`),
    )
end

function print_summary(run)
    final_prefix = last(run.requested_prefixes)
    println(
        "variant,instance,family,assessor_recall,assessor_safe_full," *
        "reported_acceptance_safe_full,evaluations,budget_exhausted",
    )
    for summary in run.prefixes
        summary.prefix == final_prefix || continue
        println(join((
            summary.variant,
            summary.instance_id,
            summary.family_id,
            "$(summary.assessor_qualified_targets_found)/$(summary.target_count)",
            summary.assessor_safe_all_targets,
            summary.lab_safe_all_targets,
            summary.evaluations,
            summary.budget_exhausted,
        ), ','))
    end
end

function main(arguments=ARGS)
    options = parse_arguments(arguments)
    if options === nothing
        print(usage())
        return nothing
    end
    run = run_solver_experiment(
        selected_problems(options[:suite], last(options[:prefixes])),
        variants(options[:suite]);
        prefixes=options[:prefixes],
        evaluation_limit=ExperimentLocal004.DEFAULT_MAX_EVALUATIONS,
    )
    document = solver_experiment_document(run)
    document["experiment_id"] = EXPERIMENT_ID
    document["suite"] = String(options[:suite])
    document["environment"] = Dict{String,Any}(
        "julia_threads" => Threads.nthreads(),
        "julia_version" => string(VERSION),
        "machine" => Sys.MACHINE,
        "nonlinear_solve_version" => string(Base.pkgversion(ExperimentLocal004.NonlinearSolve)),
        "openblas_num_threads" => get(ENV, "OPENBLAS_NUM_THREADS", "unset"),
        "pinned_project" => "research/experiments/EXP-LOCAL-002",
    )
    document["revision"] = git_revision()
    document["runner_options"] = Dict{String,Any}(
        "evaluation_limit" => ExperimentLocal004.DEFAULT_MAX_EVALUATIONS,
        "prefixes" => collect(run.requested_prefixes),
        "problem_count" => length(run.problem_manifest),
    )
    output = abspath(options[:output])
    mkpath(dirname(output))
    write(output, canonical_json(document), "\n")
    print_summary(run)
    println("output=$output")
    return run
end

if abspath(PROGRAM_FILE) == abspath(@__FILE__())
    main()
end
