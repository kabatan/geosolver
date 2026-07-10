module RoutingLocal002

using ..ExperimentLocal002
using ..DevelopmentLocal002
using GeoTargetBenchmarks
using JSON3
using LinearAlgebra
using SHA

include("routing_policy.jl")

const AMENDMENT_PATH = joinpath(
    ExperimentLocal002.EXPERIMENT_ROOT,
    "routing-amendment.json",
)
const DEFAULT_ROUTING_DEVELOPMENT_OUTPUT = joinpath(
    ExperimentLocal002.REPO_ROOT,
    "research",
    "results",
    ExperimentLocal002.EXPERIMENT_ID,
    "routing-development-v0",
)

const ROUTING_COLUMNS = (
    ExperimentLocal002.CSV_COLUMNS...,
    "selected_variant",
    "routing_capability",
    "routing_dimension",
    "routing_diagnostic_computed",
    "routing_numerical_rank",
    "routing_condition_estimate",
    "routing_rank_cutoff",
    "routing_residual_calls",
    "routing_svd_count",
    "routing_wall_seconds",
    "routing_status",
    "routing_explicit_fallback",
)

_sha256_file(path::AbstractString) = bytes2hex(sha256(read(path)))

function validate_amendment(path::AbstractString=AMENDMENT_PATH)
    amendment = JSON3.read(read(path, String))
    amendment.status == "preregistered-before-routing-outcomes" ||
        error("routing amendment is not preregistered")
    amendment.tuning_round.used == amendment.tuning_round.limit == 1 ||
        error("routing amendment does not freeze the single tuning round")
    amendment.tuning_round.post_amendment_retuning_allowed == false ||
        error("routing amendment permits post-amendment retuning")
    route = amendment.selected_route
    route.id == ROUTE_ID || error("route ID drift")
    diagnostic = route.jacobian_diagnostic
    diagnostic.minimum_dimension == ROUTE_MINIMUM_DIMENSION || error("dimension threshold drift")
    diagnostic.condition_threshold == ROUTE_CONDITION_THRESHOLD ||
        error("condition threshold drift")
    amendment.frozen_parent_evidence.card_sha256 ==
        ExperimentLocal002._file_sha256(ExperimentLocal002.CARD_PATH) ||
        error("parent experiment card checksum drift")
    return true
end

function routed_attempt(problem, start)
    diagnostic = route_diagnostic(problem, start)
    execution = ExperimentLocal002.run_attempt(
        problem,
        start,
        diagnostic.selected_algorithm,
    )
    return diagnostic, execution
end

function _routing_row(problem, start_index, diagnostic, execution, timing_phase)
    row = ExperimentLocal002._attempt_row(
        problem,
        diagnostic.selected_algorithm,
        start_index,
        execution,
        timing_phase,
    )
    row["variant"] = ROUTE_ID
    row["selected_variant"] = diagnostic.selected_algorithm
    row["routing_capability"] = diagnostic.capability
    row["routing_dimension"] = diagnostic.dimension
    row["routing_diagnostic_computed"] = diagnostic.computed
    row["routing_numerical_rank"] = diagnostic.numerical_rank
    row["routing_condition_estimate"] =
        ExperimentLocal002._finite_or_nothing(diagnostic.condition_estimate)
    row["routing_rank_cutoff"] =
        ExperimentLocal002._finite_or_nothing(diagnostic.rank_cutoff)
    row["routing_residual_calls"] = diagnostic.residual_calls
    row["routing_svd_count"] = diagnostic.svd_count
    row["routing_wall_seconds"] = diagnostic.wall_seconds
    row["routing_status"] = diagnostic.status
    row["routing_explicit_fallback"] = diagnostic.explicit_fallback
    return row
end

function _write_routing_csv(path, rows)
    open(path, "w") do io
        println(io, join(ROUTING_COLUMNS, ','))
        for row in rows
            println(
                io,
                join(
                    (
                        ExperimentLocal002._csv_escape(get(row, column, nothing)) for
                        column in ROUTING_COLUMNS
                    ),
                    ',',
                ),
            )
        end
    end
end

function _first_lm_trigger(problems)
    scan_count = 0
    scan_residual_calls = 0
    for problem in problems
        for start_index in 1:DevelopmentLocal002.DEVELOPMENT_START_COUNT
            diagnostic = route_diagnostic(problem, view(problem.saved_starts, :, start_index))
            scan_count += 1
            scan_residual_calls += diagnostic.residual_calls
            diagnostic.selected_algorithm == ROUTE_ALTERNATE_ALGORITHM &&
                return problem, start_index, diagnostic, scan_count, scan_residual_calls
        end
    end
    error("frozen development inputs contain no LM route activation")
end

function _warmup_problems(problems)
    seen = Set{String}()
    selected = DirectAnalyticProblem[]
    for problem in problems
        problem.family_id in seen && continue
        push!(seen, problem.family_id)
        push!(selected, problem)
    end
    return selected
end

function validate_routing_rows(rows, problems)
    length(rows) == DevelopmentLocal002.DEVELOPMENT_INSTANCE_COUNT *
        DevelopmentLocal002.DEVELOPMENT_START_COUNT || error("routing row count drift")
    instance_map = Dict(problem.instance_id => problem for problem in problems)
    for row in rows
        row["variant"] == ROUTE_ID || error("routing row variant drift")
        row["selected_variant"] in (ROUTE_DEFAULT_ALGORITHM, ROUTE_ALTERNATE_ALGORITHM) ||
            error("routing row selects an undeclared algorithm")
        row["accepted"] == (row["canonical_valid"] && row["gold_matched"]) ||
            error("routing row bypasses independent acceptance")
        row["budget_exceeded"] && error("routing row exceeds a declared solver budget")
        problem = instance_map[row["instance_id"]]
        replay = route_diagnostic(
            problem,
            view(problem.saved_starts, :, row["start_index"]),
        )
        replay.selected_algorithm == row["selected_variant"] || error("routing decision replay drift")
        replay.capability == row["routing_capability"] || error("capability replay drift")
        replay.numerical_rank == row["routing_numerical_rank"] || error("rank replay drift")
        replay.residual_calls == row["routing_residual_calls"] ||
            error("routing callback accounting drift")
        replay.explicit_fallback == row["routing_explicit_fallback"] ||
            error("routing fallback replay drift")
        if replay.computed && isfinite(replay.condition_estimate)
            replay.condition_estimate == row["routing_condition_estimate"] ||
                error("condition replay drift")
        end
    end
    return true
end

function execute_development_route(
    ;
    output_directory::AbstractString,
    load_compile_seconds::Real=NaN,
)
    validate_amendment()
    problems = DevelopmentLocal002.development_problems()
    DevelopmentLocal002.validate_development_input_manifest(
        DevelopmentLocal002.INPUT_MANIFEST_PATH,
        problems,
    )
    mkpath(output_directory)
    worker_started_ns = time_ns()

    cold_problem = first(problems)
    cold_diagnostic, cold_execution = routed_attempt(
        cold_problem,
        view(cold_problem.saved_starts, :, 1),
    )
    cold_execution.exception === nothing || error("routing cold probe failed")

    scan_started_ns = time_ns()
    lm_problem, lm_start, _, scan_count, scan_residual_calls = _first_lm_trigger(problems)
    scan_seconds = (time_ns() - scan_started_ns) / 1.0e9
    activation_started_ns = time_ns()
    activation_diagnostic, activation_execution = routed_attempt(
        lm_problem,
        view(lm_problem.saved_starts, :, lm_start),
    )
    activation_seconds = (time_ns() - activation_started_ns) / 1.0e9
    activation_diagnostic.selected_algorithm == ROUTE_ALTERNATE_ALGORITHM ||
        error("LM activation probe did not select LM")
    activation_execution.exception === nothing || activation_execution.budget_exhausted ||
        error("LM activation probe failed")

    warmup_started_ns = time_ns()
    for problem in _warmup_problems(problems)
        diagnostic, execution = routed_attempt(
            problem,
            view(problem.saved_starts, :, 1),
        )
        execution.exception === nothing || execution.budget_exhausted ||
            error("routing warmup failed for selected algorithm $(diagnostic.selected_algorithm)")
    end
    warmup_seconds = (time_ns() - warmup_started_ns) / 1.0e9

    rows = Dict{String,Any}[]
    measured_started_ns = time_ns()
    for problem in problems
        seen_targets = Set{String}()
        for start_index in 1:DevelopmentLocal002.DEVELOPMENT_START_COUNT
            diagnostic, execution = routed_attempt(
                problem,
                view(problem.saved_starts, :, start_index),
            )
            row = _routing_row(problem, start_index, diagnostic, execution, "warm-measured")
            row["accepted"] && push!(seen_targets, row["target_id"])
            row["targets_seen"] = length(seen_targets)
            row["target_count"] = length(problem.gold_targets)
            row["all_targets_prefix"] = length(seen_targets) == length(problem.gold_targets)
            push!(rows, row)
        end
    end
    measured_seconds = (time_ns() - measured_started_ns) / 1.0e9
    validate_routing_rows(rows, problems)

    csv_path = joinpath(output_directory, "worker-route-lmtr-a1.csv")
    metadata_path = joinpath(output_directory, "worker-route-lmtr-a1.json")
    _write_routing_csv(csv_path, rows)
    metadata = Dict{String,Any}(
        "schema_version" => "exp-local-002-routing-worker-v1",
        "experiment_id" => ExperimentLocal002.EXPERIMENT_ID,
        "route_id" => ROUTE_ID,
        "source_commit" => ExperimentLocal002._safe_git_commit(),
        "amendment_sha256" => _sha256_file(AMENDMENT_PATH),
        "input_manifest_sha256" => _sha256_file(DevelopmentLocal002.INPUT_MANIFEST_PATH),
        "result_csv_sha256" => _sha256_file(csv_path),
        "attempt_count" => length(rows),
        "package_load_compile_seconds" => Float64(load_compile_seconds),
        "cold_default_probe_seconds" => cold_diagnostic.wall_seconds + cold_execution.wall_seconds,
        "cold_default_selected_algorithm" => cold_diagnostic.selected_algorithm,
        "cold_lm_scan_seconds" => scan_seconds,
        "cold_lm_scan_diagnostics" => scan_count,
        "cold_lm_scan_residual_calls" => scan_residual_calls,
        "cold_lm_activation_seconds" => activation_seconds,
        "cold_total_seconds" => Float64(load_compile_seconds) + cold_diagnostic.wall_seconds +
            cold_execution.wall_seconds + scan_seconds + activation_seconds,
        "warmup_seconds" => warmup_seconds,
        "measured_seconds" => measured_seconds,
        "worker_seconds" => (time_ns() - worker_started_ns) / 1.0e9,
        "lm_selected_count" => count(row -> row["selected_variant"] == ROUTE_ALTERNATE_ALGORITHM, rows),
        "diagnostic_residual_calls" => sum(row["routing_residual_calls"] for row in rows),
        "diagnostic_svd_count" => sum(row["routing_svd_count"] for row in rows),
        "explicit_diagnostic_fallbacks" => count(row -> row["routing_explicit_fallback"], rows),
        "accepted" => count(row -> row["accepted"], rows),
        "budget_exhaustions" => count(row -> row["budget_exhausted"], rows),
        "budget_overruns" => count(row -> row["budget_exceeded"], rows),
        "nonbudget_exceptions" => count(
            row -> row["exception"] !== nothing && !row["budget_exhausted"],
            rows,
        ),
    )
    ExperimentLocal002._write_json(metadata_path, metadata)
    return metadata
end

function worker_cli(args=ARGS; load_compile_seconds::Real=NaN)
    output_directory = nothing
    index = 1
    while index <= length(args)
        argument = args[index]
        if argument == "--out"
            index == length(args) && throw(ArgumentError("--out requires a value"))
            index += 1
            output_directory = abspath(args[index])
        else
            throw(ArgumentError("unknown routing worker argument: $argument"))
        end
        index += 1
    end
    output_directory === nothing && throw(ArgumentError("--out is required"))
    metadata = execute_development_route(
        output_directory=output_directory,
        load_compile_seconds=load_compile_seconds,
    )
    println(
        "completed ",
        ROUTE_ID,
        ": accepted=",
        metadata["accepted"],
        "/",
        metadata["attempt_count"],
        ", lm_selected=",
        metadata["lm_selected_count"],
    )
    return metadata
end

export ROUTE_ID,
    ROUTE_DEFAULT_ALGORITHM,
    ROUTE_ALTERNATE_ALGORITHM,
    ROUTE_MINIMUM_DIMENSION,
    ROUTE_CONDITION_THRESHOLD,
    RouteDiagnostic,
    route_diagnostic,
    validate_amendment,
    routed_attempt,
    validate_routing_rows,
    execute_development_route,
    worker_cli

end
