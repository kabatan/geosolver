using GeoTargetBenchmarks
using GeoTargetCore

const T2_RUN_REPOSITORY_ROOT = normpath(joinpath(@__DIR__, "..", "..", ".."))
const T2_RUN_EXP_LOCAL_002 = joinpath(
    T2_RUN_REPOSITORY_ROOT,
    "research",
    "experiments",
    "EXP-LOCAL-002",
)

include(joinpath(T2_RUN_EXP_LOCAL_002, "src", "ExperimentLocal002.jl"))
include(joinpath(T2_RUN_EXP_LOCAL_002, "src", "DevelopmentLocal002.jl"))
include(joinpath(T2_RUN_REPOSITORY_ROOT, "benchmarks", "solver_lab", "CoreBaseline.jl"))
include(joinpath(@__DIR__, "src", "ExperimentLocal004.jl"))
include(joinpath(@__DIR__, "src", "T2Corpus.jl"))
using .ExperimentLocal004
using .GeoTargetSolverLab
using .T2Corpus

function t2_usage()
    return """
    Usage: julia --project=research/experiments/EXP-LOCAL-002 \\
      research/experiments/EXP-LOCAL-004/run_t2.jl [options]

      --output=PATH   JSON output (default: benchmarks/results/raw/exp-local-004-t2-linux.json)
      --help          Show this message

    The official T2 contract is fixed at 48 development cases, 32 materialized
    starts, prefixes 8/16/32, variants prod-tol-120x600,
    prod-options-250x2000 and NLS-TR, and a runner hard cap of 2000 callbacks.
    """
end

function parse_t2_arguments(arguments)
    output = joinpath(
        T2_RUN_REPOSITORY_ROOT,
        "benchmarks",
        "results",
        "raw",
        "exp-local-004-t2-linux.json",
    )
    for argument in arguments
        argument == "--help" && return nothing
        if startswith(argument, "--output=")
            value = argument[length("--output=") + 1:end]
            isempty(value) && error("output path must be nonempty")
            output = abspath(value)
        else
            error("unknown option: $argument")
        end
    end
    return output
end

function t2_variants()
    variants = SolverVariant[
        core_lmqr_control(:prod_tol_120x600),
        core_lmqr_control(:prod_options_250x2000),
        nls_tr_variant(max_iterations=250, max_evaluations=2_000),
    ]
    observed_contract = Any[
        Dict{String,Any}(
            "name" => variant.name,
            "max_iterations" => variant.configuration.max_iterations,
            "max_evaluations" => variant.configuration.max_evaluations,
        ) for variant in variants
    ]
    canonical_json(observed_contract) == canonical_json(t2_variant_contract()) ||
        error("T2 variant contract drifted")
    return variants
end

function _t2_revision()
    return Dict{String,Any}(
        "git_dirty" => !isempty(strip(read(
            `git -C $T2_RUN_REPOSITORY_ROOT status --porcelain`,
            String,
        ))),
        "git_head" => readchomp(`git -C $T2_RUN_REPOSITORY_ROOT rev-parse HEAD`),
    )
end

function _print_t2_summary(run)
    for summary in run.prefixes
        summary.prefix == last(T2_PREFIXES) || continue
        println(join((
            summary.variant,
            summary.instance_id,
            summary.family_id,
            "$(summary.assessor_qualified_targets_found)/$(summary.target_count)",
            summary.assessor_safe_all_targets,
            summary.lab_safe_all_targets,
            summary.evaluations,
            summary.runner_budget_exhausted,
        ), ','))
    end
end

function run_t2_main(arguments=ARGS)
    output = parse_t2_arguments(arguments)
    if output === nothing
        print(t2_usage())
        return nothing
    end
    isfile(T2_INPUT_MANIFEST_PATH) || error(
        "T2 input manifest is absent; run prepare_t2.jl and commit the frozen manifest first",
    )

    # This is the only corpus-generation call in the official execution path.
    problems = t2_problems()
    input_manifest_sha256 = validate_t2_input_manifest(
        T2_INPUT_MANIFEST_PATH,
        problems,
    )
    variants = t2_variants()
    run = run_solver_experiment(
        problems,
        variants;
        prefixes=T2_PREFIXES,
        evaluation_limit=T2_RUNNER_EVALUATION_LIMIT,
    )
    run.requested_prefixes == T2_PREFIXES || error("T2 prefix contract drifted")
    run.evaluation_limit == T2_RUNNER_EVALUATION_LIMIT ||
        error("T2 runner evaluation cap drifted")

    document = solver_experiment_document(run)
    canonical_json(document["assessor_manifest"]) ==
        canonical_json(fixed_assessor_manifest()) ||
        error("T2 fixed assessor drifted")
    document["experiment_id"] = "EXP-LOCAL-004"
    document["suite"] = "t2"
    document["partition"] = "development"
    document["locked_validation"] = false
    document["input_manifest"] = Dict{String,Any}(
        "path" => relpath(T2_INPUT_MANIFEST_PATH, T2_RUN_REPOSITORY_ROOT),
        "schema_version" => T2_SCHEMA_VERSION,
        "sha256" => input_manifest_sha256,
    )
    document["environment"] = Dict{String,Any}(
        "julia_threads" => Threads.nthreads(),
        "julia_version" => string(VERSION),
        "machine" => Sys.MACHINE,
        "nonlinear_solve_version" =>
            string(Base.pkgversion(ExperimentLocal004.NonlinearSolve)),
        "openblas_num_threads" => get(ENV, "OPENBLAS_NUM_THREADS", "unset"),
        "pinned_project" => "research/experiments/EXP-LOCAL-002",
    )
    document["revision"] = _t2_revision()
    document["runner_options"] = Dict{String,Any}(
        "evaluation_limit" => T2_RUNNER_EVALUATION_LIMIT,
        "prefixes" => collect(T2_PREFIXES),
        "problem_count" => T2_INSTANCE_COUNT,
        "starts_per_problem" => T2_START_COUNT,
    )

    mkpath(dirname(output))
    write(output, canonical_json(document), "\n")
    _print_t2_summary(run)
    println("input_manifest_sha256=", input_manifest_sha256)
    println("output=", output)
    return run
end

if abspath(PROGRAM_FILE) == abspath(@__FILE__())
    run_t2_main()
end
