module HarnessJac003

using GeoTargetBase
using GeoTargetCore
using JSON3
using LinearAlgebra
using SHA

include("CandidateJac003.jl")
using .CandidateJac003

const VARIANT_K0 = "K0-DENSE-PUBLIC"
const VARIANT_K1 = "K1-CACHED-ROUTED"
const TRACE_SCHEMA = "exp-jac-003-segment-trace/v1"
const CASE_SECONDS = 180
const OBSERVATION_SECONDS = 60
const STARTS_PER_CASE = 32
const EXPECTED_CASE_KEYS = Set([
    "budgets",
    "lower",
    "opaque_case_id",
    "oracle_program",
    "origins",
    "residual_count",
    "scales",
    "starts",
    "typed_graph",
    "upper",
    "variable_count",
])
const FORBIDDEN_CANDIDATE_KEYS = Set([
    "family",
    "family_id",
    "factor",
    "factors",
    "seed",
    "seeds",
    "gold",
    "truth",
    "expected",
    "analytic",
    "jacobian",
    "target",
    "branch_label",
])

function _sha256_file(path)
    return bytes2hex(sha256(read(path)))
end

function _finite_or_tag(value::Real)
    return isfinite(value) ? Float64(value) : string(value)
end

function _forbidden_candidate_paths(value, path="")
    found = String[]
    if value isa AbstractDict
        for (raw_key, child) in value
            key = String(raw_key)
            child_path = isempty(path) ? key : "$path.$key"
            lowercase(key) in FORBIDDEN_CANDIDATE_KEYS && push!(found, child_path)
            append!(found, _forbidden_candidate_paths(child, child_path))
        end
    elseif value isa AbstractVector
        for (index, child) in enumerate(value)
            append!(found, _forbidden_candidate_paths(child, "$path[$index]"))
        end
    end
    return found
end

function _validate_candidate_document(document)
    String(document["schema_version"]) == CANDIDATE_SCHEMA ||
        error("wrong EXP-JAC-003 candidate schema")
    Int(document["case_count"]) == 64 || error("candidate case_count must equal 64")
    Int(document["starts_per_case"]) == STARTS_PER_CASE ||
        error("candidate starts_per_case must equal 32")
    cases = document["cases"]
    length(cases) == 64 || error("candidate cases length must equal 64")
    ids = String[]
    for case in cases
        Set(String(key) for key in keys(case)) == EXPECTED_CASE_KEYS ||
            error("candidate case field-set drift")
        id = String(case["opaque_case_id"])
        occursin(r"^[0-9a-f]{24}$", id) || error("invalid opaque_case_id")
        push!(ids, id)
        length(case["starts"]) == STARTS_PER_CASE ||
            error("candidate case must contain 32 starts")
    end
    issorted(ids) || error("candidate cases must be in ascending opaque-ID order")
    allunique(ids) || error("candidate opaque IDs must be unique")
    forbidden = _forbidden_candidate_paths(document)
    isempty(forbidden) || error("candidate forbidden key at $(first(forbidden))")
    return nothing
end

function _deadline(started_ns::UInt64)
    increment = UInt64(CASE_SECONDS) * UInt64(1_000_000_000)
    started_ns <= typemax(UInt64) - increment || return typemax(UInt64)
    return started_ns + increment
end

function _trace_point(point::LocalTracePoint)
    return Dict{String,Any}(
        "accepted_step" => point.accepted_step,
        "damping" => point.damping,
        "evaluations" => point.evaluations,
        "iteration" => point.iteration,
        "merit" => point.merit,
        "residual_infinity" => point.residual_infinity,
    )
end

function _group_event(event)
    return Dict{String,Any}(
        "columns" => collect(event.columns),
        "completed_fallback_columns" => hasproperty(event, :completed_fallback_columns) ?
                                        event.completed_fallback_columns :
                                        (event.fallback ? length(event.columns) : 0),
        "fallback" => event.fallback,
        "fallback_evaluations" => event.fallback_evaluations,
        "grouped_evaluations" => event.grouped_evaluations,
    )
end

function _attempt_document(
    start_index,
    attempt::LocalAttempt,
    attempt_wall_ns,
    replay,
    replay_wall_ns,
    group_events,
    jacobian_events,
    deadline_ns,
)
    final_residual = Float64[relation.scaled for relation in attempt.observation.relations]
    replay_residual = Float64[relation.scaled for relation in replay.relations]
    fallback_groups = count(event -> event["fallback"], group_events)
    fallback_columns = sum(
        event["completed_fallback_columns"] for event in group_events if event["fallback"]
    )
    return Dict{String,Any}(
        "accepted" => attempt.accepted,
        "attempt_wall_ns" => attempt_wall_ns,
        "branch_keys" => Any[
            string(branch.decision.key) for branch in attempt.observation.branches
        ],
        "callback_count" => attempt.evaluations + 1,
        "condition_estimate" => _finite_or_tag(attempt.condition_estimate),
        "deadline_ns" => string(deadline_ns),
        "evaluations" => attempt.evaluations,
        "fallback_column_count" => fallback_columns,
        "fallback_group_count" => fallback_groups,
        "final" => collect(attempt.final),
        "final_residual_infinity" => isempty(final_residual) ? nothing : norm(final_residual, Inf),
        "group_events" => group_events,
        "iterations" => attempt.iterations,
        "jacobian_events" => jacobian_events,
        "numerical_rank" => attempt.numerical_rank,
        "observation_status" => string(attempt.observation.status),
        "primal_equivalent_oracle_work" => attempt.evaluations + 1,
        "replay_canonical_feasible" => canonical_feasible(replay),
        "replay_branch_keys" => Any[
            string(branch.decision.key) for branch in replay.branches
        ],
        "replay_completed_within_deadline" => true,
        "replay_residual_infinity" => isempty(replay_residual) ? nothing :
                                      norm(replay_residual, Inf),
        "replay_residual_count" => length(replay_residual),
        "replay_status" => string(replay.status),
        "replay_wall_ns" => replay_wall_ns,
        "start_index" => start_index,
        "status" => string(attempt.status),
        "started" => true,
        "trace" => Any[_trace_point(point) for point in attempt.trace],
    )
end

function _unreplayed_attempt_document(
    start_index,
    attempt::LocalAttempt,
    attempt_wall_ns,
    group_events,
    jacobian_events,
    deadline_ns,
)
    final_residual = Float64[relation.scaled for relation in attempt.observation.relations]
    fallback_groups = count(event -> event["fallback"], group_events)
    fallback_columns = sum(
        event["completed_fallback_columns"] for event in group_events if event["fallback"]
    )
    return Dict{String,Any}(
        "accepted" => false,
        "attempt_wall_ns" => attempt_wall_ns,
        "branch_keys" => Any[
            string(branch.decision.key) for branch in attempt.observation.branches
        ],
        "callback_count" => attempt.evaluations,
        "condition_estimate" => _finite_or_tag(attempt.condition_estimate),
        "deadline_ns" => string(deadline_ns),
        "evaluations" => attempt.evaluations,
        "fallback_column_count" => fallback_columns,
        "fallback_group_count" => fallback_groups,
        "final" => collect(attempt.final),
        "final_residual_infinity" => isempty(final_residual) ? nothing : norm(final_residual, Inf),
        "group_events" => group_events,
        "iterations" => attempt.iterations,
        "jacobian_events" => jacobian_events,
        "numerical_rank" => attempt.numerical_rank,
        "observation_status" => string(attempt.observation.status),
        "primal_equivalent_oracle_work" => attempt.evaluations,
        "replay_canonical_feasible" => false,
        "replay_branch_keys" => Any[],
        "replay_completed_within_deadline" => false,
        "replay_residual_infinity" => nothing,
        "replay_residual_count" => 0,
        "replay_status" => "BUDGET_EXHAUSTED",
        "replay_wall_ns" => 0,
        "start_index" => start_index,
        "started" => true,
        "status" => string(attempt.status),
        "trace" => Any[_trace_point(point) for point in attempt.trace],
    )
end

function _budget_exhausted(start_index, deadline_ns)
    return Dict{String,Any}(
        "accepted" => false,
        "attempt_wall_ns" => 0,
        "branch_keys" => Any[],
        "callback_count" => 0,
        "condition_estimate" => "Inf",
        "deadline_ns" => string(deadline_ns),
        "evaluations" => 0,
        "fallback_column_count" => 0,
        "fallback_group_count" => 0,
        "final" => nothing,
        "final_residual_infinity" => nothing,
        "group_events" => Any[],
        "iterations" => 0,
        "jacobian_events" => Any[],
        "numerical_rank" => 0,
        "observation_status" => "NOT_RUN",
        "primal_equivalent_oracle_work" => 0,
        "replay_canonical_feasible" => false,
        "replay_branch_keys" => Any[],
        "replay_completed_within_deadline" => false,
        "replay_residual_infinity" => nothing,
        "replay_residual_count" => 0,
        "replay_status" => "NOT_RUN",
        "replay_wall_ns" => 0,
        "start_index" => start_index,
        "started" => false,
        "status" => "BUDGET_EXHAUSTED",
        "trace" => Any[],
    )
end

function _compile_runner(variant, case)
    arguments = (
        case["typed_graph"],
        case["oracle_program"],
        Int(case["variable_count"]),
        Int(case["residual_count"]),
        case["origins"],
        case["scales"],
        case["lower"],
        case["upper"],
        case["budgets"],
    )
    if variant == VARIANT_K0
        return compile_dense_case_runner(arguments...)
    end
    return compile_case_runner(arguments...)
end

function _structure_document(runner::DenseCaseRunner)
    return Dict{String,Any}(
        "color_count" => nothing,
        "compiler_projection_hash" => runner.structure.compiler_hash,
        "provider_field_names" => Any[],
        "provider_projection_hash" => nothing,
        "residual_count" => runner.structure.residual_count,
        "route" => "dense-public",
        "route_field_names" => Any[],
        "route_projection_hash" => nothing,
        "structural_nonzeros" => runner.structure.structural_nonzeros,
        "variable_count" => runner.structure.variable_count,
    )
end

function _structure_document(runner::CompiledCaseRunner)
    route = runner.structure.route
    visibility = visibility_record(runner.structure)
    return Dict{String,Any}(
        "color_count" => route.color_count,
        "compiler_projection_hash" => nothing,
        "provider_field_names" => visibility["provider_field_names"],
        "provider_projection_hash" => visibility["provider_projection_hash"],
        "residual_count" => route.residual_count,
        "route" => runner.provider === nothing ? "dense-routed" : "colored",
        "route_field_names" => visibility["route_field_names"],
        "route_projection_hash" => visibility["route_projection_hash"],
        "structural_nonzeros" => route.structural_nonzeros,
        "variable_count" => route.variable_count,
    )
end

function _case_document(variant, case, case_ordinal)
    opaque_id = String(case["opaque_case_id"])
    case_started_ns = time_ns()
    deadline_ns = _deadline(case_started_ns)
    observation_ns = case_started_ns + UInt64(OBSERVATION_SECONDS) * UInt64(1_000_000_000)
    compile_timed = @timed _compile_runner(variant, case)
    runner = compile_timed.value
    attempts = Any[]
    timed_out = time_ns() >= deadline_ns
    for (start_offset, raw_start) in enumerate(case["starts"])
        start_index = start_offset - 1
        if timed_out || time_ns() >= deadline_ns
            timed_out = true
            push!(attempts, _budget_exhausted(start_index, deadline_ns))
            continue
        end
        group_events = Any[]
        jacobian_events = Any[]
        attempt_started_ns = time_ns()
        attempt = solve_attempt(
            runner,
            raw_start;
            deadline_ns,
            color_group_observer=event -> push!(group_events, _group_event(event)),
            jacobian_observer=event -> push!(
                jacobian_events,
                Dict{String,Any}(
                    "colored" => event.colored,
                    "evaluations" => event.evaluations,
                ),
            ),
        )
        attempt_finished_ns = time_ns()
        if attempt_finished_ns >= deadline_ns
            timed_out = true
            push!(
                attempts,
                _unreplayed_attempt_document(
                    start_index,
                    attempt,
                    attempt_finished_ns - attempt_started_ns,
                    group_events,
                    jacobian_events,
                    deadline_ns,
                ),
            )
            continue
        end
        replay_started_ns = time_ns()
        replay = observation(runner.program, attempt.final)
        replay_finished_ns = time_ns()
        if replay_finished_ns >= deadline_ns
            timed_out = true
            late = _attempt_document(
                start_index,
                attempt,
                attempt_finished_ns - attempt_started_ns,
                replay,
                replay_finished_ns - replay_started_ns,
                group_events,
                jacobian_events,
                deadline_ns,
            )
            late["replay_canonical_feasible"] = false
            late["replay_completed_within_deadline"] = false
            push!(attempts, late)
            continue
        end
        push!(
            attempts,
            _attempt_document(
                start_index,
                attempt,
                attempt_finished_ns - attempt_started_ns,
                replay,
                replay_finished_ns - replay_started_ns,
                group_events,
                jacobian_events,
                deadline_ns,
            ),
        )
        attempt.status == LOCAL_DEADLINE && (timed_out = true)
    end
    length(attempts) == STARTS_PER_CASE || error("case attempt-count drift")
    case_finished_ns = time_ns()
    actual_wall_ns = case_finished_ns - case_started_ns
    charged_wall_ns = timed_out ? UInt64(CASE_SECONDS) * UInt64(1_000_000_000) : actual_wall_ns
    budget_overrun_count = count(
        attempt -> attempt["evaluations"] > Int(case["budgets"]["max_evaluations"]),
        attempts,
    )
    return Dict{String,Any}(
        "actual_wall_ns" => actual_wall_ns,
        "attempts" => attempts,
        "budget_overrun_count" => budget_overrun_count,
        "case_ordinal" => case_ordinal,
        "charged_wall_ns" => charged_wall_ns,
        "compile_allocated_bytes" => compile_timed.bytes,
        "compile_gc_seconds" => compile_timed.gctime,
        "compile_wall_ns" => round(Int, compile_timed.time * 1.0e9),
        "observation_checkpoint_crossed" => case_finished_ns >= observation_ns,
        "opaque_case_id" => opaque_id,
        "post_deadline_callback_entry_count" => 0,
        "structure" => _structure_document(runner),
        "timed_out" => timed_out,
    )
end

function _required_env(name)
    value = get(ENV, name, "")
    isempty(value) && error("required environment variable $name is missing")
    return value
end

function run_segment(variant::AbstractString, candidate_path::AbstractString)
    variant in (VARIANT_K0, VARIANT_K1) || error("unknown EXP-JAC-003 variant")
    Threads.nthreads() == 1 || error("formal segment requires one Julia thread")
    BLAS.get_num_threads() == 1 || error("formal segment requires one BLAS thread")
    candidate_bytes = read(candidate_path)
    candidate_sha256 = bytes2hex(sha256(candidate_bytes))
    candidate_sha256 == _required_env("EXP_JAC003_CANDIDATE_SHA256") ||
        error("candidate input SHA-256 mismatch")
    manifest_path = joinpath(dirname(Base.active_project()), "Manifest.toml")
    manifest_sha256 = _sha256_file(manifest_path)
    manifest_sha256 == _required_env("EXP_JAC003_MANIFEST_SHA256") ||
        error("Manifest.toml SHA-256 mismatch")
    source_lock_sha256 = _required_env("EXP_JAC003_SOURCE_LOCK_SHA256")
    document = JSON3.read(candidate_bytes, Dict{String,Any})
    _validate_candidate_document(document)
    segment_started_ns = time_ns()
    cases = Any[
        _case_document(variant, case, case_ordinal) for
        (case_ordinal, case) in enumerate(document["cases"])
    ]
    return Dict{String,Any}(
        "candidate_input_sha256" => candidate_sha256,
        "case_count" => length(cases),
        "cases" => cases,
        "experiment_id" => "EXP-JAC-003",
        "julia_threads" => Threads.nthreads(),
        "manifest_sha256" => manifest_sha256,
        "schema_version" => TRACE_SCHEMA,
        "segment_inner_wall_ns" => time_ns() - segment_started_ns,
        "source_lock_sha256" => source_lock_sha256,
        "starts_per_case" => STARTS_PER_CASE,
        "variant" => String(variant),
        "version" => string(VERSION),
    )
end

function write_segment(path::AbstractString, document)
    ispath(path) && error("segment output already exists")
    mkpath(dirname(abspath(path)))
    temporary = string(path, ".tmp")
    ispath(temporary) && error("segment temporary output already exists")
    open(temporary, "w") do io
        write(io, canonical_json(document))
        write(io, '\n')
        flush(io)
    end
    mv(temporary, path)
    return nothing
end

export run_segment, write_segment, VARIANT_K0, VARIANT_K1, TRACE_SCHEMA

end
