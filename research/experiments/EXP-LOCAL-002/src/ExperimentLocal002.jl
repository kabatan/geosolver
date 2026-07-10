module ExperimentLocal002

using ADTypes
using GeoTargetBase
using GeoTargetBenchmarks
using GeoTargetCore
using JSON3
using LinearAlgebra
using NonlinearSolve
using SHA
using Statistics

const EXPERIMENT_ID = "EXP-LOCAL-002"
const VARIANTS = ("NLS-LM", "NLS-TR", "NLS-RMN", "NLS-TR-STRICT", "LXR-LMQR")
const PILOT_START_COUNT = 8
const MAX_ITERATIONS = 250
const MAX_EVALUATIONS = 2_000
const INTERNAL_RESIDUAL_TOLERANCE = eps(Float64)^(2 / 3)
const STRICT_INTERNAL_RESIDUAL_TOLERANCE = 1.0e-12
const GOLD_CONFIGURATION_TOLERANCE = 1.0e-6
const GOLD_TARGET_TOLERANCE = 1.0e-6
const DERIVATIVE_ROUTE = "central-finite-difference"
const EXTERNAL_DERIVATIVE_BACKEND = "ADTypes.AutoFiniteDiff(fdtype=Val(:central))"

const REPO_ROOT = normpath(joinpath(@__DIR__, "..", "..", "..", ".."))
const EXPERIMENT_ROOT = normpath(joinpath(@__DIR__, ".."))
const CARD_PATH = joinpath(REPO_ROOT, "research", "experiments", "EXP-LOCAL-002.json")
const DEFAULT_OUTPUT_ROOT =
    joinpath(REPO_ROOT, "research", "results", EXPERIMENT_ID, "pilot-v0")

const STRICT_GUARD_NODE = NodeId("exp-local-002-strict-guard")

struct CallbackBudgetExceeded <: Exception
    limit::Int
end

Base.showerror(io::IO, error::CallbackBudgetExceeded) =
    print(io, "residual callback budget ", error.limit, " exhausted")

mutable struct ResidualCounter
    calls::Int
    limit::Int
    last_u::Vector{Float64}
end

struct AttemptExecution
    endpoint::Vector{Float64}
    retcode::String
    package_reported_success::Bool
    exception::Union{Nothing,String}
    wall_seconds::Float64
    solver_nf::Int
    callback_residual_calls::Int
    njacs::Int
    nfactors::Int
    nsolve::Int
    iterations::Int
    budget_exhausted::Bool
    budget_exceeded::Bool
end

"""The fixed, non-gating eight-instance pilot specified for EXP-LOCAL-002."""
function pilot_problems(; start_count::Integer=PILOT_START_COUNT)
    start_count > 0 || throw(ArgumentError("start_count must be positive"))
    count = Int(start_count)
    return DirectAnalyticProblem[
        generate(
            ScaleLadderParams(
                dimension=4,
                residual_scale_spread=1.0e12,
                instance_seed=201,
                start_seed=2_001,
                start_count=count,
            ),
        ),
        generate(
            CurvedChainParams(
                dimension=4,
                curvature=1.0e4,
                instance_seed=202,
                start_seed=2_002,
                start_count=count,
            ),
        ),
        generate(
            NearRankDeficientParams(
                dimension=4,
                singular_value_ratio=1.0e-8,
                orientation_seed=203,
                start_seed=2_003,
                start_count=count,
            ),
        ),
        generate(
            RedundantOverdeterminedParams(
                dimension=4,
                redundancy=2,
                dependency_error=1.0e-8,
                dependency_seed=204,
                start_seed=2_004,
                start_count=count,
            ),
        ),
        generate(
            TangentCircleLineParams(
                radius=1.0,
                height_radius_ratio=0.999999,
                instance_seed=205,
                start_seed=2_005,
                start_count=count,
            ),
        ),
        generate(
            MultiRootWarpedParams(
                dimension=4,
                root_count=4,
                minimum_separation=1.0e-3,
                warp=0.5,
                condition=1.0e4,
                target_map=:z1,
                coefficient_seed=206,
                start_seed=2_006,
                start_count=count,
            ),
        ),
        generate(
            StrictGuardBoundaryParams(
                boundary_case=:on_boundary,
                guard_margin=0.0,
                instance_seed=208,
                start_seed=2_008,
                start_count=count,
            ),
        ),
        generate(
            OpaqueTranscendentalParams(
                root_count=3,
                loop_count=8,
                phase=0.0,
                mixing=0.1,
                instance_seed=209,
                start_seed=2_009,
                start_count=count,
            ),
        ),
    ]
end

function bounds_normalization(problem::DirectAnalyticProblem)
    origins = (problem.lower_bounds .+ problem.upper_bounds) ./ 2
    scales = (problem.upper_bounds .- problem.lower_bounds) ./ 2
    lower = (problem.lower_bounds .- origins) ./ scales
    upper = (problem.upper_bounds .- origins) ./ scales
    return origins, scales, lower, upper
end

_denormalize(u, origins, scales) = origins .+ scales .* u
_normalize(x, origins, scales) = (x .- origins) ./ scales

function _external_algorithm(variant::AbstractString)
    backend = AutoFiniteDiff(fdtype=Val(:central))
    variant == "NLS-LM" && return LevenbergMarquardt(autodiff=backend)
    variant == "NLS-TR" && return TrustRegion(autodiff=backend)
    variant == "NLS-RMN" && return RobustMultiNewton(autodiff=backend)
    variant == "NLS-TR-STRICT" && return TrustRegion(autodiff=backend)
    throw(ArgumentError("unknown external variant: $variant"))
end

function _external_attempt(
    problem::DirectAnalyticProblem,
    start::AbstractVector,
    variant::AbstractString,
)
    origins, scales, lower_u, upper_u = bounds_normalization(problem)
    u0 = _normalize(collect(Float64, start), origins, scales)
    counter = ResidualCounter(0, MAX_EVALUATIONS, copy(u0))

    function scaled_residual!(output, u, _)
        counter.calls >= counter.limit && throw(CallbackBudgetExceeded(counter.limit))
        counter.calls += 1
        counter.last_u .= u
        x = _denormalize(u, origins, scales)
        problem.residual!(output, x)
        output ./= problem.residual_scales
        return output
    end

    # The analytic generator Jacobian is deliberately not attached.  The card
    # freezes one explicit central finite-difference route for every candidate,
    # including the Float64-only C0 opaque family.
    function_object = NonlinearFunction(
        scaled_residual!;
        resid_prototype=zeros(problem.residual_dimension),
    )
    least_squares_problem = NonlinearLeastSquaresProblem(
        function_object,
        u0,
        nothing;
        lb=lower_u,
        ub=upper_u,
    )
    tolerance = variant == "NLS-TR-STRICT" ?
        STRICT_INTERNAL_RESIDUAL_TOLERANCE : INTERNAL_RESIDUAL_TOLERANCE

    solution = nothing
    caught = nothing
    elapsed = @elapsed begin
        try
            solution = NonlinearSolve.solve(
                least_squares_problem,
                _external_algorithm(variant);
                abstol=tolerance,
                reltol=0.0,
                maxiters=MAX_ITERATIONS,
            )
        catch error
            caught = error
        end
    end

    if solution === nothing
        endpoint = _denormalize(counter.last_u, origins, scales)
        message = caught === nothing ? "solver returned no solution" : sprint(showerror, caught)
        exhausted = caught isa CallbackBudgetExceeded ||
            occursin("callback budget", lowercase(message))
        return AttemptExecution(
            endpoint,
            caught === nothing ? "NO-SOLUTION" : "EXCEPTION:$(nameof(typeof(caught)))",
            false,
            message,
            elapsed,
            -1,
            counter.calls,
            -1,
            -1,
            -1,
            -1,
            exhausted,
            counter.calls > MAX_EVALUATIONS,
        )
    end

    stats = solution.stats
    retcode = string(solution.retcode)
    endpoint = _denormalize(collect(Float64, solution.u), origins, scales)
    return AttemptExecution(
        endpoint,
        retcode,
        occursin("Success", retcode),
        nothing,
        elapsed,
        Int(stats.nf),
        counter.calls,
        Int(stats.njacs),
        Int(stats.nfactors),
        Int(stats.nsolve),
        Int(stats.nsteps),
        counter.calls >= MAX_EVALUATIONS || Int(stats.nsteps) >= MAX_ITERATIONS ||
            occursin("MaxIters", retcode),
        counter.calls > MAX_EVALUATIONS || Int(stats.nsteps) > MAX_ITERATIONS,
    )
end

function _lxr_observation(
    problem::DirectAnalyticProblem,
    x::AbstractVector,
    calls::Base.RefValue{Int},
    relation_nodes,
)
    calls[] += 1
    raw = zeros(problem.residual_dimension)
    problem.residual!(raw, x)
    relations = Tuple(
        RelationObservation(
            relation_nodes[index],
            raw[index],
            problem.residual_scales[index],
            raw[index] / problem.residual_scales[index],
            nothing,
        ) for index in eachindex(raw)
    )
    guards = if problem.family_id == "STRICT-GUARD-BOUNDARY"
        margin = strict_guard_margin(problem, x)
        (GuardObservation(STRICT_GUARD_NODE, margin, true, 1.0, margin > 0),)
    else
        ()
    end
    status = all(isfinite, raw) ? EVAL_OK : EVAL_NONFINITE
    target = all(isfinite, x) ? problem.target(x) : NaN
    return OracleObservation(relations, target, guards, (), (), status, 1, nothing)
end

function _lxr_attempt(problem::DirectAnalyticProblem, start::AbstractVector)
    origins, scales, _, _ = bounds_normalization(problem)
    calls = Ref(0)
    relation_nodes = [
        NodeId("exp-local-002-relation-$(index)") for
        index in 1:problem.residual_dimension
    ]
    options = LocalSolveOptions(
        max_iterations=MAX_ITERATIONS,
        max_evaluations=MAX_EVALUATIONS,
        residual_tolerance=INTERNAL_RESIDUAL_TOLERANCE,
        finite_difference_step=cbrt(eps(Float64)),
    )
    attempt = nothing
    caught = nothing
    elapsed = @elapsed begin
        try
            attempt = solve_local(
                x -> _lxr_observation(problem, x, calls, relation_nodes),
                collect(Float64, start);
                origins=origins,
                scales=scales,
                lower=problem.lower_bounds,
                upper=problem.upper_bounds,
                options=options,
            )
        catch error
            caught = error
        end
    end
    if attempt === nothing
        message = caught === nothing ? "solver returned no attempt" : sprint(showerror, caught)
        return AttemptExecution(
            collect(Float64, start),
            caught === nothing ? "NO-ATTEMPT" : "EXCEPTION:$(nameof(typeof(caught)))",
            false,
            message,
            elapsed,
            -1,
            calls[],
            -1,
            -1,
            -1,
            -1,
            calls[] >= MAX_EVALUATIONS,
            calls[] > MAX_EVALUATIONS,
        )
    end
    jacobians = length(attempt.trace)
    endpoint = Float64[attempt.final...]
    return AttemptExecution(
        endpoint,
        string(attempt.status),
        attempt.status == LOCAL_CONVERGED,
        nothing,
        elapsed,
        attempt.evaluations,
        calls[],
        jacobians,
        jacobians,
        jacobians,
        attempt.iterations,
        attempt.status in (LOCAL_MAX_EVALUATIONS, LOCAL_MAX_ITERATIONS) ||
            calls[] >= MAX_EVALUATIONS || attempt.iterations >= MAX_ITERATIONS,
        calls[] > MAX_EVALUATIONS || attempt.iterations > MAX_ITERATIONS,
    )
end

run_attempt(problem::DirectAnalyticProblem, start::AbstractVector, variant::AbstractString) =
    variant == "LXR-LMQR" ? _lxr_attempt(problem, start) :
    _external_attempt(problem, start, variant)

function _descriptor_for_configuration(problem::DirectAnalyticProblem, index::Int)
    descriptor_index = findfirst(
        descriptor -> index in configuration_indices(descriptor),
        problem.gold_targets,
    )
    descriptor_index === nothing && error("Gold configuration lacks a target descriptor")
    return problem.gold_targets[descriptor_index]
end

_finite_or_nothing(value::Real) = isfinite(value) ? Float64(value) : nothing

"""Validate an endpoint without consulting a solver return code."""
function validate_endpoint(problem::DirectAnalyticProblem, endpoint::AbstractVector)
    x = collect(Float64, endpoint)
    raw = fill(NaN, problem.residual_dimension)
    residual_error = nothing
    if length(x) == problem.dimension && all(isfinite, x)
        try
            problem.residual!(raw, x)
        catch error
            residual_error = sprint(showerror, error)
        end
    else
        residual_error = "endpoint is nonfinite or has the wrong dimension"
    end
    scaled = raw ./ problem.residual_scales
    raw_linf = all(isfinite, raw) ? norm(raw, Inf) : Inf
    scaled_linf = all(isfinite, scaled) ? norm(scaled, Inf) : Inf
    residual_qualified = scaled_linf <= INTERNAL_RESIDUAL_TOLERANCE
    bounds_valid = length(x) == problem.dimension && all(isfinite, x) &&
        all((problem.lower_bounds .<= x) .& (x .<= problem.upper_bounds))
    strict_guard_validity = problem.family_id == "STRICT-GUARD-BOUNDARY" ?
        (all(isfinite, x) && strict_guard_valid(problem, x)) : true
    canonical_valid = residual_qualified && bounds_valid && strict_guard_validity

    _, normalization_scales, _, _ = bounds_normalization(problem)
    distances = if length(x) == problem.dimension && all(isfinite, x)
        [
            maximum(abs.((x .- configuration) ./ normalization_scales)) for
            configuration in eachcol(problem.gold_configurations)
        ]
    else
        fill(Inf, size(problem.gold_configurations, 2))
    end
    nearest_index = argmin(distances)
    nearest_distance = distances[nearest_index]
    gold_configuration_match = nearest_distance <= GOLD_CONFIGURATION_TOLERANCE
    descriptor = _descriptor_for_configuration(problem, nearest_index)

    target_value = NaN
    target_error_message = nothing
    if length(x) == problem.dimension && all(isfinite, x)
        try
            target_value = Float64(problem.target(x))
        catch error
            target_error_message = sprint(showerror, error)
        end
    else
        target_error_message = "target is undefined for a nonfinite endpoint"
    end
    target_reference = numeric_target(descriptor)
    target_error = isfinite(target_value) ? abs(target_value - target_reference) : Inf
    target_match = target_error <= GOLD_TARGET_TOLERANCE
    gold_matched = gold_configuration_match && target_match
    accepted = canonical_valid && gold_matched
    false_candidate = residual_qualified && !gold_matched

    return Dict{String,Any}(
        "raw_residual_linf" => _finite_or_nothing(raw_linf),
        "scaled_residual_linf" => _finite_or_nothing(scaled_linf),
        "residual_qualified" => residual_qualified,
        "bounds_valid" => bounds_valid,
        "strict_guard_valid" => strict_guard_validity,
        "canonical_valid" => canonical_valid,
        "gold_config_index" => nearest_index,
        "gold_normalized_distance" => _finite_or_nothing(nearest_distance),
        "gold_config_match" => gold_configuration_match,
        "target" => _finite_or_nothing(target_value),
        "target_id" => descriptor.target_id,
        "target_reference" => target_reference,
        "target_error" => _finite_or_nothing(target_error),
        "target_match" => target_match,
        "gold_matched" => gold_matched,
        "accepted" => accepted,
        "false_candidate" => false_candidate,
        "residual_validation_error" => residual_error,
        "target_validation_error" => target_error_message,
    )
end

function _artifact_checksum(problem::DirectAnalyticProblem, name::Symbol)
    artifact = only(filter(entry -> entry.name === name, problem.artifacts))
    return artifact.sha256
end

function _attempt_row(
    problem::DirectAnalyticProblem,
    variant::AbstractString,
    start_index::Int,
    execution::AttemptExecution,
    timing_phase::AbstractString,
)
    validation = validate_endpoint(problem, execution.endpoint)
    row = Dict{String,Any}(
        "experiment_id" => EXPERIMENT_ID,
        "pilot_non_gating" => true,
        "variant" => String(variant),
        "family_id" => problem.family_id,
        "instance_id" => problem.instance_id,
        "strata" => String.(problem.strata),
        "start_index" => start_index,
        "start" => collect(problem.saved_starts[:, start_index]),
        "endpoint" => [_finite_or_nothing(value) for value in execution.endpoint],
        "timing_phase" => String(timing_phase),
        "derivative_route" => DERIVATIVE_ROUTE,
        "derivative_backend" => variant == "LXR-LMQR" ?
            "GeoTargetCore central finite difference" : EXTERNAL_DERIVATIVE_BACKEND,
        "internal_residual_tolerance" => variant == "NLS-TR-STRICT" ?
            STRICT_INTERNAL_RESIDUAL_TOLERANCE : INTERNAL_RESIDUAL_TOLERANCE,
        "retcode" => execution.retcode,
        "package_reported_success" => execution.package_reported_success,
        "exception" => execution.exception,
        "wall_seconds" => execution.wall_seconds,
        "solver_nf" => execution.solver_nf,
        "callback_residual_calls" => execution.callback_residual_calls,
        "validation_residual_calls" => 1,
        "njacs" => execution.njacs,
        "nfactors" => execution.nfactors,
        "nsolve" => execution.nsolve,
        "linear_work" => execution.nfactors >= 0 && execution.nsolve >= 0 ?
            execution.nfactors + execution.nsolve : nothing,
        "iterations" => execution.iterations,
        "budget_exhausted" => execution.budget_exhausted,
        "budget_exceeded" => execution.budget_exceeded,
        "replay_checksum" => replay_checksum(problem),
        "starts_checksum" => _artifact_checksum(problem, :saved_starts),
    )
    merge!(row, validation)
    return row
end

function execute_pilot(
    problems::AbstractVector{<:DirectAnalyticProblem}=pilot_problems();
    variants=VARIANTS,
)
    all(verify_replay_material, problems) || error("pilot replay material failed checksum validation")
    all(problem -> size(problem.saved_starts, 2) == PILOT_START_COUNT, problems) ||
        throw(ArgumentError("the pilot requires exactly $PILOT_START_COUNT starts per instance"))
    Tuple(variants) == VARIANTS ||
        @warn "running a diagnostic subset; this is not the complete pilot" variants

    rows = Dict{String,Any}[]
    for variant in variants
        variant in VARIANTS || throw(ArgumentError("unknown variant: $variant"))
        first_attempt = true
        for problem in problems
            seen_targets = Set{String}()
            for start_index in 1:PILOT_START_COUNT
                execution = run_attempt(
                    problem,
                    view(problem.saved_starts, :, start_index),
                    variant,
                )
                row = _attempt_row(
                    problem,
                    variant,
                    start_index,
                    execution,
                    first_attempt ? "cold-first-use" : "warm",
                )
                first_attempt = false
                row["accepted"] && push!(seen_targets, row["target_id"])
                row["targets_seen"] = length(seen_targets)
                row["target_count"] = length(problem.gold_targets)
                row["all_targets_prefix"] = length(seen_targets) == length(problem.gold_targets)
                push!(rows, row)
            end
        end
    end
    return rows
end

"""Fail closed if result accounting or independent acceptance invariants drift."""
function validate_result_rows(
    rows,
    problems::AbstractVector{<:DirectAnalyticProblem};
    variants=VARIANTS,
    start_count::Integer=PILOT_START_COUNT,
)
    expected_count = length(problems) * length(variants) * Int(start_count)
    length(rows) == expected_count ||
        error("expected $expected_count attempt rows, found $(length(rows))")
    start_reference = Dict{Tuple{String,Int},Any}()
    combination_count = Dict{Tuple{String,String,Int},Int}()
    prefixes = Dict{Tuple{String,String},Tuple{Int,Bool}}()
    expected_replays = Dict(problem.instance_id => replay_checksum(problem) for problem in problems)

    for row in rows
        row["accepted"] == (row["canonical_valid"] && row["gold_matched"]) ||
            error("acceptance predicate drift at $(row["variant"])/$(row["instance_id"])")
        row["false_candidate"] ==
            (row["residual_qualified"] && !row["gold_matched"]) ||
            error("false-candidate predicate drift at $(row["variant"])/$(row["instance_id"])")
        row["accepted"] && row["false_candidate"] &&
            error("a false candidate was accepted")
        row["callback_residual_calls"] <= MAX_EVALUATIONS ||
            error("callback budget exceeded without interception")
        row["iterations"] <= MAX_ITERATIONS || error("iteration budget exceeded")
        row["replay_checksum"] == expected_replays[row["instance_id"]] ||
            error("replay checksum drift")
        expected_backend = row["variant"] == "LXR-LMQR" ?
            "GeoTargetCore central finite difference" : EXTERNAL_DERIVATIVE_BACKEND
        row["derivative_backend"] == expected_backend ||
            error("undeclared derivative backend or silent fallback")

        start_key = (row["instance_id"], row["start_index"])
        if haskey(start_reference, start_key)
            row["start"] == start_reference[start_key] || error("paired start drift")
        else
            start_reference[start_key] = row["start"]
        end
        combination_key = (row["variant"], row["instance_id"], row["start_index"])
        combination_count[combination_key] = get(combination_count, combination_key, 0) + 1

        prefix_key = (row["variant"], row["instance_id"])
        previous_seen, previous_full = get(prefixes, prefix_key, (0, false))
        row["targets_seen"] >= previous_seen || error("target prefix is not monotone")
        previous_full && !row["all_targets_prefix"] &&
            error("full-target prefix reverted from true to false")
        row["all_targets_prefix"] == (row["targets_seen"] == row["target_count"]) ||
            error("full-target prefix predicate drift")
        prefixes[prefix_key] = (row["targets_seen"], row["all_targets_prefix"])
    end
    all(==(1), values(combination_count)) || error("attempt combination duplicated")
    return true
end

function _safe_git_commit()
    try
        return readchomp(Cmd(`git rev-parse HEAD`; dir=REPO_ROOT))
    catch
        return "unavailable"
    end
end

_file_sha256(path::AbstractString) = bytes2hex(sha256(read(path)))

function environment_record(problems; load_compile_seconds::Real)
    project_path = joinpath(EXPERIMENT_ROOT, "Project.toml")
    manifest_path = joinpath(EXPERIMENT_ROOT, "Manifest.toml")
    source_path = joinpath(EXPERIMENT_ROOT, "src", "ExperimentLocal002.jl")
    entrypoint_path = joinpath(EXPERIMENT_ROOT, "run_pilot.jl")
    problem_records = [
        Dict(
            "family_id" => problem.family_id,
            "instance_id" => problem.instance_id,
            "replay_checksum" => replay_checksum(problem),
            "starts_checksum" => _artifact_checksum(problem, :saved_starts),
            "gold_checksum" => _artifact_checksum(problem, :gold_configurations),
            "starts" => size(problem.saved_starts, 2),
        ) for problem in problems
    ]
    return Dict{String,Any}(
        "experiment_id" => EXPERIMENT_ID,
        "pilot_non_gating" => true,
        "git_commit" => _safe_git_commit(),
        "julia_version" => string(VERSION),
        "kernel" => string(Sys.KERNEL),
        "architecture" => string(Sys.ARCH),
        "cpu_threads" => Sys.CPU_THREADS,
        "package_load_compile_seconds" => Float64(load_compile_seconds),
        "packages" => Dict(
            "ADTypes" => string(Base.pkgversion(ADTypes)),
            "GeoTargetBase" => string(Base.pkgversion(GeoTargetBase)),
            "GeoTargetBenchmarks" => string(Base.pkgversion(GeoTargetBenchmarks)),
            "GeoTargetCore" => string(Base.pkgversion(GeoTargetCore)),
            "JSON3" => string(Base.pkgversion(JSON3)),
            "NonlinearSolve" => string(Base.pkgversion(NonlinearSolve)),
        ),
        "checksums" => Dict(
            "experiment_card_sha256" => _file_sha256(CARD_PATH),
            "project_sha256" => _file_sha256(project_path),
            "manifest_sha256" => _file_sha256(manifest_path),
            "runner_source_sha256" => _file_sha256(source_path),
            "runner_entrypoint_sha256" => _file_sha256(entrypoint_path),
        ),
        "budgets" => Dict(
            "max_iterations" => MAX_ITERATIONS,
            "max_callback_residual_evaluations" => MAX_EVALUATIONS,
        ),
        "validation" => Dict(
            "canonical_scaled_residual_tolerance" => INTERNAL_RESIDUAL_TOLERANCE,
            "gold_configuration_normalized_tolerance" => GOLD_CONFIGURATION_TOLERANCE,
            "gold_target_tolerance" => GOLD_TARGET_TOLERANCE,
            "package_retcode_is_acceptance_predicate" => false,
        ),
        "derivative_route" => Dict(
            "declared" => DERIVATIVE_ROUTE,
            "external_backend" => EXTERNAL_DERIVATIVE_BACKEND,
            "c1_analytic_jacobian_attached" => false,
            "c0_opaque_backend" => EXTERNAL_DERIVATIVE_BACKEND,
            "silent_fallback_allowed" => false,
        ),
        "problems" => problem_records,
    )
end

function _last_rows_by_instance(rows, variant)
    selected = filter(row -> row["variant"] == variant, rows)
    latest = Dict{String,Dict{String,Any}}()
    for row in selected
        latest[row["instance_id"]] = row
    end
    return collect(values(latest))
end

function summarize(rows, environment)
    variants = Dict{String,Any}[]
    present_variants = [
        variant for variant in VARIANTS if any(row -> row["variant"] == variant, rows)
    ]
    for variant in present_variants
        selected = filter(row -> row["variant"] == variant, rows)
        warm = Float64[
            row["wall_seconds"] for row in selected if row["timing_phase"] == "warm"
        ]
        cold = only(filter(row -> row["timing_phase"] == "cold-first-use", selected))
        last_rows = _last_rows_by_instance(rows, variant)
        push!(
            variants,
            Dict{String,Any}(
                "variant" => variant,
                "attempts" => length(selected),
                "accepted" => count(row -> row["accepted"], selected),
                "p_local_gold" => count(row -> row["accepted"], selected) / length(selected),
                "residual_qualified" => count(row -> row["residual_qualified"], selected),
                "false_candidates" => count(row -> row["false_candidate"], selected),
                "package_reported_success" =>
                    count(row -> row["package_reported_success"], selected),
                "full_target_instances_at_eight" =>
                    count(row -> row["all_targets_prefix"], last_rows),
                "cold_first_attempt_seconds" => cold["wall_seconds"],
                "median_warm_attempt_seconds" => isempty(warm) ? nothing : median(warm),
                "callback_residual_calls" =>
                    sum(row["callback_residual_calls"] for row in selected),
                "njacs" => sum(max(0, row["njacs"]) for row in selected),
                "linear_work" => sum(
                    row["linear_work"] === nothing ? 0 : row["linear_work"] for
                    row in selected
                ),
                "budget_overruns" => count(row -> row["budget_exceeded"], selected),
                "budget_exhaustions" => count(row -> row["budget_exhausted"], selected),
                "exceptions" => count(row -> row["exception"] !== nothing, selected),
            ),
        )
    end

    family_rows = Dict{String,Any}[]
    for family in unique(row["family_id"] for row in rows), variant in present_variants
        selected = filter(
            row -> row["family_id"] == family && row["variant"] == variant,
            rows,
        )
        last_row = selected[end]
        push!(
            family_rows,
            Dict(
                "family_id" => family,
                "variant" => variant,
                "accepted" => count(row -> row["accepted"], selected),
                "attempts" => length(selected),
                "false_candidates" => count(row -> row["false_candidate"], selected),
                "all_targets_at_eight" => last_row["all_targets_prefix"],
            ),
        )
    end
    return Dict{String,Any}(
        "experiment_id" => EXPERIMENT_ID,
        "status" => "non-gating-pilot",
        "promotion_decision" => "not-evaluated",
        "environment" => environment,
        "variant_summary" => variants,
        "family_summary" => family_rows,
        "fairness_limits" => [
            "Package load/compile is measured once for the fresh process.",
            "Each variant's first attempt is marked cold, but variants run sequentially and may share compiled infrastructure; cold comparisons are exploratory.",
            "solver_nf has implementation-specific semantics; callback_residual_calls is the comparable primal callback count.",
            "All external candidates use the preregistered explicit central AutoFiniteDiff route; no analytic-Jacobian lower-bound control is included in this pilot.",
        ],
    )
end

const CSV_COLUMNS = (
    "experiment_id",
    "pilot_non_gating",
    "variant",
    "family_id",
    "instance_id",
    "strata",
    "start_index",
    "start",
    "endpoint",
    "timing_phase",
    "derivative_route",
    "derivative_backend",
    "internal_residual_tolerance",
    "retcode",
    "package_reported_success",
    "exception",
    "wall_seconds",
    "solver_nf",
    "callback_residual_calls",
    "validation_residual_calls",
    "njacs",
    "nfactors",
    "nsolve",
    "linear_work",
    "iterations",
    "budget_exhausted",
    "budget_exceeded",
    "raw_residual_linf",
    "scaled_residual_linf",
    "residual_qualified",
    "bounds_valid",
    "strict_guard_valid",
    "canonical_valid",
    "gold_config_index",
    "gold_normalized_distance",
    "gold_config_match",
    "target",
    "target_id",
    "target_reference",
    "target_error",
    "target_match",
    "gold_matched",
    "accepted",
    "false_candidate",
    "targets_seen",
    "target_count",
    "all_targets_prefix",
    "replay_checksum",
    "starts_checksum",
)

function _csv_value(value)
    value === nothing && return ""
    value isa AbstractVector && return join((item === nothing ? "null" : string(item) for item in value), ";")
    value isa Bool && return lowercase(string(value))
    return string(value)
end

function _csv_escape(value)
    text = _csv_value(value)
    if occursin(',', text) || occursin('"', text) || occursin('\n', text) || occursin('\r', text)
        return string('"', replace(text, '"' => "\"\""), '"')
    end
    return text
end

function _write_csv(path, rows)
    open(path, "w") do io
        println(io, join(CSV_COLUMNS, ','))
        for row in rows
            println(io, join((_csv_escape(get(row, column, nothing)) for column in CSV_COLUMNS), ','))
        end
    end
end

function _write_json(path, object)
    open(path, "w") do io
        JSON3.pretty(io, object)
        println(io)
    end
end

function _markdown_report(summary)
    io = IOBuffer()
    println(io, "# EXP-LOCAL-002 non-gating pilot")
    println(io)
    println(io, "This pilot checks adapters and records observations only. It does not evaluate the preregistered promotion gate.")
    println(io)
    println(io, "| Variant | Gold-valid / attempts | Full-target instances | False candidates | Callback calls | Median warm (s) | Cold first attempt (s) |")
    println(io, "|---|---:|---:|---:|---:|---:|---:|")
    for entry in summary["variant_summary"]
        warm = entry["median_warm_attempt_seconds"]
        warm_text = warm === nothing ? "n/a" : string(round(warm; sigdigits=5))
        println(
            io,
            "| ",
            entry["variant"],
            " | ",
            entry["accepted"],
            " / ",
            entry["attempts"],
            " | ",
            entry["full_target_instances_at_eight"],
            " / 8 | ",
            entry["false_candidates"],
            " | ",
            entry["callback_residual_calls"],
            " | ",
            warm_text,
            " | ",
            round(entry["cold_first_attempt_seconds"]; sigdigits=5),
            " |",
        )
    end
    println(io)
    println(io, "## Fixed protocol")
    println(io)
    println(io, "- Eight checksum-pinned starts for each of eight representative families, including S4 and S6.")
    println(io, "- Bounds-midpoint/half-range variable normalization and declared residual scales for every variant.")
    println(io, "- `NonlinearLeastSquaresProblem` receives explicit normalized `lb` and `ub`.")
    println(io, "- All external routes use `AutoFiniteDiff(fdtype=Val(:central))`; no analytic or silent fallback route is attached.")
    println(io, "- Acceptance ignores package retcodes and independently checks scaled residual, bounds, the S4 strict guard, normalized Gold configuration distance, and target error.")
    println(io)
    println(io, "## Fairness limits")
    println(io)
    for limit in summary["fairness_limits"]
        println(io, "- ", limit)
    end
    println(io)
    println(io, "Environment, exact package versions, card/environment checksums, replay checksums, and per-attempt records are in `summary.json`, `environment.json`, `attempts.json`, and `attempts.csv`.")
    return String(take!(io))
end

function write_results(output_root, rows, environment, summary)
    mkpath(output_root)
    _write_csv(joinpath(output_root, "attempts.csv"), rows)
    _write_json(joinpath(output_root, "attempts.json"), rows)
    _write_json(joinpath(output_root, "environment.json"), environment)
    _write_json(joinpath(output_root, "summary.json"), summary)
    write(joinpath(output_root, "pilot-report.md"), _markdown_report(summary))
    return output_root
end

function run_pilot(; output_root=DEFAULT_OUTPUT_ROOT, load_compile_seconds::Real=NaN)
    problems = pilot_problems()
    rows = execute_pilot(problems)
    validate_result_rows(rows, problems)
    environment = environment_record(problems; load_compile_seconds=load_compile_seconds)
    summary = summarize(rows, environment)
    write_results(output_root, rows, environment, summary)
    return summary
end

function cli(args=ARGS; load_compile_seconds::Real=NaN)
    output_root = DEFAULT_OUTPUT_ROOT
    index = 1
    while index <= length(args)
        argument = args[index]
        if argument == "--out"
            index == length(args) && throw(ArgumentError("--out requires a path"))
            index += 1
            output_root = abspath(args[index])
        elseif argument in ("--help", "-h")
            println("usage: julia --project=. run_pilot.jl [--out PATH]")
            return nothing
        else
            throw(ArgumentError("unknown argument: $argument"))
        end
        index += 1
    end
    summary = run_pilot(
        output_root=output_root,
        load_compile_seconds=load_compile_seconds,
    )
    println("wrote non-gating pilot to ", output_root)
    for entry in summary["variant_summary"]
        println(
            entry["variant"],
            ": accepted=",
            entry["accepted"],
            "/",
            entry["attempts"],
            ", false_candidates=",
            entry["false_candidates"],
        )
    end
    return summary
end

export EXPERIMENT_ID,
    VARIANTS,
    PILOT_START_COUNT,
    MAX_ITERATIONS,
    MAX_EVALUATIONS,
    INTERNAL_RESIDUAL_TOLERANCE,
    STRICT_INTERNAL_RESIDUAL_TOLERANCE,
    GOLD_CONFIGURATION_TOLERANCE,
    GOLD_TARGET_TOLERANCE,
    DEFAULT_OUTPUT_ROOT,
    pilot_problems,
    bounds_normalization,
    run_attempt,
    validate_endpoint,
    execute_pilot,
    validate_result_rows,
    environment_record,
    summarize,
    write_results,
    run_pilot,
    cli

end
