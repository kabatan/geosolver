using GeoTargetBenchmarks
using GeoTargetCore

const REPOSITORY_ROOT = normpath(joinpath(@__DIR__, "..", "..", ".."))

include(joinpath(REPOSITORY_ROOT, "benchmarks", "solver_lab", "CoreBaseline.jl"))
include(joinpath(REPOSITORY_ROOT, "research", "experiments", "EXP-LOCAL-004", "src", "ExperimentLocal004.jl"))
include(joinpath(@__DIR__, "src", "ExperimentLocal005.jl"))
using .ExperimentLocal004
using .ExperimentLocal005
using .GeoTargetSolverLab

function usage()
    return """
    Usage: julia --project=research/experiments/EXP-LOCAL-005 \\
      research/experiments/EXP-LOCAL-005/run.jl [options]

      --suite=t0|t1      Five-case screen or representative nine cases (default: t0)
      --prefixes=2,4,8   Sorted saved-start prefixes (default: 2,4,8)
      --shard-index=N    Zero-based shard index (default: 0)
      --shard-count=N    Number of outer case shards (default: 1)
      --output=PATH      Output JSON (default includes suite and shard)
      --help             Show this message

    Run each shard with JULIA_NUM_THREADS=1 and native BLAS/OpenMP thread counts 1.
    Sharding changes only the outer set of cases; each local solve stays serial.
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
        :suite => :t0,
        :prefixes => [2, 4, 8],
        :shard_index => 0,
        :shard_count => 1,
        :output => nothing,
    )
    for argument in arguments
        argument == "--help" && return nothing
        if startswith(argument, "--suite=")
            suite = Symbol(argument[length("--suite=") + 1:end])
            suite in (:t0, :t1) || error("suite must be t0 or t1")
            options[:suite] = suite
        elseif startswith(argument, "--prefixes=")
            raw = split(argument[length("--prefixes=") + 1:end], ',')
            options[:prefixes] = [
                parse_integer(value, "prefix"; positive=true) for value in raw
            ]
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
    prefixes = options[:prefixes]
    issorted(prefixes) && allunique(prefixes) || error("prefixes must be sorted and unique")
    options[:shard_index] < options[:shard_count] ||
        error("shard index must be less than shard count")
    options[:output] === nothing && (options[:output] = joinpath(
        REPOSITORY_ROOT,
        "benchmarks",
        "results",
        "raw",
        "exp-local-005-$(options[:suite])-shard-$(options[:shard_index])-of-$(options[:shard_count]).json",
    ))
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

function suite_problems(suite::Symbol, start_count)
    suite === :t0 && return t0_problems(start_count)
    suite === :t1 || throw(ArgumentError("suite must be t0 or t1"))
    problems = representative_problems(; start_count)
    length(problems) == 9 || error("T1 must contain nine representative cases")
    return problems
end

function shard_problems(problems, shard_index::Int, shard_count::Int)
    shard_count <= length(problems) ||
        error("shard count cannot exceed the number of cases")
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
        nls_tr_variant(max_iterations=250, max_evaluations=2_000),
        dfols_variant(max_evaluations=2_000),
    ]
end

function git_revision()
    return Dict{String,Any}(
        "git_dirty" => !isempty(strip(read(`git -C $REPOSITORY_ROOT status --porcelain`, String))),
        "git_head" => readchomp(`git -C $REPOSITORY_ROOT rev-parse HEAD`),
    )
end

function assert_serial_environment()
    Threads.nthreads() == 1 || error("EXP-LOCAL-005 shards require JULIA_NUM_THREADS=1")
    for name in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS")
        get(ENV, name, "") == "1" || error("EXP-LOCAL-005 shards require $name=1")
    end
    return nothing
end

function print_summary(run)
    final_prefix = last(run.requested_prefixes)
    println(
        "variant,instance,family,assessor_recall,assessor_safe_full," *
        "reported_acceptance_safe_full,evaluations,local_cap,runner_cap",
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
            summary.local_max_evaluations,
            summary.runner_budget_exhausted,
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
    all_problems = suite_problems(options[:suite], last(options[:prefixes]))
    problems = shard_problems(
        all_problems,
        options[:shard_index],
        options[:shard_count],
    )
    run = run_solver_experiment(
        problems,
        variants();
        prefixes=options[:prefixes],
        evaluation_limit=ExperimentLocal005.DEFAULT_MAX_EVALUATIONS,
    )
    document = solver_experiment_document(run)
    document["experiment_id"] = ExperimentLocal005.EXPERIMENT_ID
    document["suite"] = String(options[:suite])
    document["shard"] = Dict{String,Any}(
        "index" => options[:shard_index],
        "count" => options[:shard_count],
        "unsharded_problem_count" => length(all_problems),
        "problem_count" => length(problems),
        "rule" => "zero-based-case-index-modulo-shard-count",
    )
    document["environment"] = Dict{String,Any}(
        "julia_threads" => Threads.nthreads(),
        "julia_version" => string(VERSION),
        "machine" => Sys.MACHINE,
        "openblas_num_threads" => ENV["OPENBLAS_NUM_THREADS"],
        "omp_num_threads" => ENV["OMP_NUM_THREADS"],
        "mkl_num_threads" => ENV["MKL_NUM_THREADS"],
        "python_executable" => ExperimentLocal005.PYTHON_EXECUTABLE,
        "python_version" => string(ExperimentLocal005.PythonCall.python_version()),
        "dfols_version" => ExperimentLocal005._package_version(),
    )
    document["revision"] = git_revision()
    document["runner_options"] = Dict{String,Any}(
        "evaluation_limit" => ExperimentLocal005.DEFAULT_MAX_EVALUATIONS,
        "prefixes" => collect(run.requested_prefixes),
        "problem_count" => length(run.problem_manifest),
        "wall_time_role" => "diagnostic-python-interop-included",
        "primary_work_metric" => "observed-residual-callback-count",
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
