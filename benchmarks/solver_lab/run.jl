using GeoTargetBenchmarks
using GeoTargetCore
using JSON3

include(joinpath(@__DIR__, "CoreBaseline.jl"))
using .GeoTargetSolverLab

const REPOSITORY_ROOT = normpath(joinpath(@__DIR__, "..", ".."))

function _usage()
    return """
    Usage: julia --project=julia benchmarks/solver_lab/run.jl [options]

      --prefixes=2,4,8          Sorted saved-start prefixes (default: 2,4,8)
      --families=ID,ID          Optional family filter
      --max-iterations=N        Per-start local iteration cap (default: 120)
      --max-evaluations=N       Per-start local evaluation cap (default: 600)
      --coordinate-scaling=MODE bounds, declared, or raw (default: bounds)
      --raw-residuals           Disable declared residual scaling
      --output=PATH             JSON output (default: ignored raw-results path)
      --help                    Show this message
    """
end

function _parse_positive(value, label)
    parsed = tryparse(Int, value)
    parsed !== nothing && parsed > 0 || error("$label must be a positive integer")
    return parsed
end

function _parse_args(arguments)
    options = Dict{Symbol,Any}(
        :prefixes => [2, 4, 8],
        :families => nothing,
        :max_iterations => 120,
        :max_evaluations => 600,
        :coordinate_scaling => :bounds,
        :residual_scaling => true,
        :output => joinpath(
            REPOSITORY_ROOT,
            "benchmarks",
            "results",
            "raw",
            "solver-lab-baseline.json",
        ),
    )
    for argument in arguments
        argument == "--help" && return nothing
        argument == "--raw-residuals" && (options[:residual_scaling] = false; continue)
        if startswith(argument, "--prefixes=")
            values = split(argument[length("--prefixes=") + 1:end], ',')
            options[:prefixes] = [_parse_positive(value, "prefix") for value in values]
        elseif startswith(argument, "--families=")
            values = filter(!isempty, split(argument[length("--families=") + 1:end], ','))
            isempty(values) && error("family filter must be nonempty")
            options[:families] = Set(values)
        elseif startswith(argument, "--max-iterations=")
            options[:max_iterations] = _parse_positive(
                argument[length("--max-iterations=") + 1:end],
                "max iterations",
            )
        elseif startswith(argument, "--max-evaluations=")
            options[:max_evaluations] = _parse_positive(
                argument[length("--max-evaluations=") + 1:end],
                "max evaluations",
            )
        elseif startswith(argument, "--coordinate-scaling=")
            mode = Symbol(argument[length("--coordinate-scaling=") + 1:end])
            mode in (:bounds, :declared, :raw) ||
                error("coordinate scaling must be bounds, declared, or raw")
            options[:coordinate_scaling] = mode
        elseif startswith(argument, "--output=")
            path = argument[length("--output=") + 1:end]
            isempty(path) && error("output path must be nonempty")
            options[:output] = abspath(path)
        else
            error("unknown option: $argument")
        end
    end
    prefixes = options[:prefixes]
    issorted(prefixes) && allunique(prefixes) || error("prefixes must be sorted and unique")
    return options
end

function _print_summary(run)
    final_prefix = last(run.requested_prefixes)
    println(
        "instance,family,target_recall,all_targets,false_candidates,false_targets," *
        "budget_exhausted,duplicate_targets,evaluations",
    )
    for summary in run.prefixes
        summary.prefix == final_prefix || continue
        println(
            join(
                (
                    summary.instance_id,
                    summary.family_id,
                    "$(summary.targets_found)/$(summary.target_count)",
                    summary.all_targets,
                    summary.false_candidates,
                    summary.false_targets,
                    summary.budget_exhausted,
                    summary.duplicate_target_hits,
                    summary.evaluations,
                ),
                ',',
            ),
        )
    end
end

function _git_revision()
    head = readchomp(`git -C $REPOSITORY_ROOT rev-parse HEAD`)
    status = read(`git -C $REPOSITORY_ROOT status --porcelain`, String)
    return Dict{String,Any}(
        "git_dirty" => !isempty(strip(status)),
        "git_head" => head,
    )
end

function main(arguments=ARGS)
    options = _parse_args(arguments)
    if options === nothing
        print(_usage())
        return nothing
    end
    start_count = last(options[:prefixes])
    problems = representative_problems(; start_count)
    if options[:families] !== nothing
        requested = options[:families]
        problems = filter(problem -> problem.family_id in requested, problems)
        found = Set(problem.family_id for problem in problems)
        found == requested || error("unknown family IDs: $(join(sort!(collect(setdiff(requested, found))), ','))")
    end
    variant = core_lmqr_variant(
        coordinate_scaling=options[:coordinate_scaling],
        residual_scaling=options[:residual_scaling],
        max_iterations=options[:max_iterations],
        max_evaluations=options[:max_evaluations],
    )
    run = run_solver_experiment(
        problems,
        [variant];
        prefixes=options[:prefixes],
        evaluation_limit=options[:max_evaluations],
    )
    document = solver_experiment_document(run)
    document["environment"] = Dict{String,Any}(
        "julia_threads" => Threads.nthreads(),
        "julia_version" => string(VERSION),
        "machine" => Sys.MACHINE,
    )
    document["runner_options"] = Dict{String,Any}(
        "coordinate_scaling" => String(options[:coordinate_scaling]),
        "max_evaluations" => options[:max_evaluations],
        "max_iterations" => options[:max_iterations],
        "residual_scaling" => options[:residual_scaling],
    )
    document["revision"] = _git_revision()
    output = abspath(options[:output])
    mkpath(dirname(output))
    write(output, canonical_json(document), "\n")
    _print_summary(run)
    println("output=$output")
    return run
end

if abspath(PROGRAM_FILE) == abspath(@__FILE__())
    main()
end
