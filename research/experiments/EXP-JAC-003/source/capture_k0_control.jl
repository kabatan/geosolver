using GeoTargetBase
using GeoTargetCore
using JSON3
using LinearAlgebra

length(ARGS) == 2 || error(
    "usage: capture_k0_control.jl <candidate-inputs.json> <output.json>",
)

const INPUT_PATH = abspath(ARGS[1])
const OUTPUT_PATH = abspath(ARGS[2])

isfile(INPUT_PATH) || error("candidate input does not exist")
ispath(OUTPUT_PATH) && error("K0 control output already exists; capture is one-shot")

document = JSON3.read(read(INPUT_PATH, String), Dict{String,Any})
document["schema_version"] == "exp-jac-003-candidate-inputs/v1" ||
    error("wrong JAC003 candidate-input schema")
Int(document["case_count"]) == 64 || error("K0 capture requires exactly 64 cases")
Int(document["starts_per_case"]) == 32 || error("K0 capture requires exactly 32 starts")

float_vector(values) = Float64[Float64(value) for value in values]
float_matrix(rows) = [float_vector(row) for row in rows]

function residual_values(program, point::Vector{Float64})
    offsets = float_vector(program["offsets"])
    length(offsets) == length(point) || error("oracle-program dimension mismatch")
    delta = point .+ offsets
    kind = String(program["kind"])
    if kind == "sin-cos-tree-v1"
        amplitude = Float64(program["amplitude"])
        result = zeros(Float64, length(point))
        for (row, raw_children) in enumerate(program["children"])
            children = Int[Int(value) + 1 for value in raw_children]
            correction = if isempty(children)
                0.0
            else
                total = sum(delta[column] for column in children)
                sin(total) + 0.5 * (1.0 - cos(delta[first(children)]))
            end
            result[row] = delta[row] + amplitude * correction
        end
        return result
    elseif kind == "safe-rational-hypergraph-v1"
        margin = Float64(program["margin"])
        alpha = Float64(program["alpha"])
        return Float64[
            delta[row] + alpha * sum(
                delta[Int(column) + 1] /
                (margin + delta[Int(column) + 1]^2) for column in edge
            ) for (row, edge) in enumerate(program["edges"])
        ]
    elseif kind == "hex-ring-atan-v1"
        curvature = Float64(program["curvature"])
        alpha = Float64(program["alpha"])
        return Float64[
            delta[row] + alpha * sum(
                atan(curvature * delta[Int(column) + 1]) / curvature for
                column in neighbours
            ) for (row, neighbours) in enumerate(program["neighbours"])
        ]
    elseif kind == "dense-chart-v1"
        matrix = float_matrix(program["matrix"])
        alternate = float_matrix(program["alternate_matrix"])
        weights = float_vector(program["chart_weights"])
        chart_value = sum(weights .* point) - Float64(program["chart_threshold"])
        if String(program["chart"]) == "piecewise"
            selected = chart_value >= 0.0 ? matrix : alternate
            return Float64[
                delta[row] + sum(selected[row] .* delta) for row in eachindex(delta)
            ]
        end
        gain = Float64(program["smooth_gain"])
        return Float64[
            delta[row] + gain * tanh(sum(matrix[row] .* delta)) for row in eachindex(delta)
        ]
    end
    error("unknown JAC003 oracle program: $kind")
end

function branch_observations(program, point::Vector{Float64})
    String(program["kind"]) == "dense-chart-v1" || return ()
    weights = float_vector(program["chart_weights"])
    margin = sum(weights .* point) - Float64(program["chart_threshold"])
    key = margin >= 0.0 ? ChoiceKey("nonnegative") : ChoiceKey("negative")
    decision = BranchDecision(NodeId("chart000"), key)
    return (BranchObservation(decision, abs(margin), abs(margin)),)
end

function domain_observations(program, point::Vector{Float64})
    String(program["kind"]) == "safe-rational-hypergraph-v1" || return ()
    offsets = float_vector(program["offsets"])
    delta = point .+ offsets
    margin = Float64(program["margin"])
    return Tuple(
        DomainObservation(
            NodeId("d$(lpad(row - 1, 3, '0'))"),
            minimum(margin + delta[Int(column) + 1]^2 for column in edge),
            true,
            true,
        ) for (row, edge) in enumerate(program["edges"])
    )
end

function observation(program, point::Vector{Float64})
    residual = residual_values(program, point)
    all(isfinite, residual) || return OracleObservation(
        (), nothing, (), (), (), EVAL_NONFINITE, 1, "nonfinite JAC003 residual",
    )
    relations = Tuple(
        RelationObservation(
            NodeId("r$(lpad(row - 1, 3, '0'))"),
            value,
            1.0,
            value,
            nothing,
        ) for (row, value) in enumerate(residual)
    )
    return OracleObservation(
        relations,
        nothing,
        (),
        domain_observations(program, point),
        branch_observations(program, point),
        EVAL_OK,
        1,
        nothing,
    )
end

finite_or_tag(value::Real) = isfinite(value) ? Float64(value) : string(value)

function trace_document(point::LocalTracePoint)
    return Dict{String,Any}(
        "iteration" => point.iteration,
        "evaluations" => point.evaluations,
        "residual_infinity" => point.residual_infinity,
        "merit" => point.merit,
        "damping" => point.damping,
        "accepted_step" => point.accepted_step,
    )
end

function attempt_document(start_index::Int, attempt::LocalAttempt, jacobian_events)
    final_residual = Float64[relation.scaled for relation in attempt.observation.relations]
    return Dict{String,Any}(
        "start_index" => start_index,
        "status" => string(attempt.status),
        "accepted" => attempt.accepted,
        "final" => collect(attempt.final),
        "iterations" => attempt.iterations,
        "evaluations" => attempt.evaluations,
        "numerical_rank" => attempt.numerical_rank,
        "condition_estimate" => finite_or_tag(attempt.condition_estimate),
        "final_residual_infinity" => isempty(final_residual) ? nothing : norm(final_residual, Inf),
        "observation_status" => string(attempt.observation.status),
        "branch_keys" => Any[string(branch.decision.key) for branch in attempt.observation.branches],
        "jacobian_events" => jacobian_events,
        "trace" => Any[trace_document(point) for point in attempt.trace],
    )
end

case_traces = Any[]
for case in document["cases"]
    opaque_id = String(case["opaque_case_id"])
    program = case["oracle_program"]
    origins = float_vector(case["origins"])
    scales = float_vector(case["scales"])
    lower = float_vector(case["lower"])
    upper = float_vector(case["upper"])
    budgets = case["budgets"]
    options = LocalSolveOptions(
        max_iterations=Int(budgets["max_iterations"]),
        max_evaluations=Int(budgets["max_evaluations"]),
    )
    attempts = Any[]
    for (start_offset, raw_start) in enumerate(case["starts"])
        start = float_vector(raw_start)
        jacobian_events = Any[]
        attempt = solve_local(
            point -> observation(program, float_vector(point)),
            start;
            origins,
            scales,
            lower,
            upper,
            options,
            jacobian_observer=event -> push!(
                jacobian_events,
                Dict{String,Any}(
                    "colored" => event.colored,
                    "evaluations" => event.evaluations,
                ),
            ),
        )
        push!(attempts, attempt_document(start_offset - 1, attempt, jacobian_events))
    end
    push!(case_traces, Dict{String,Any}(
        "opaque_case_id" => opaque_id,
        "attempts" => attempts,
    ))
end

output = Dict{String,Any}(
    "schema_version" => "exp-jac-003-k0-control-traces/v1",
    "experiment_id" => "EXP-JAC-003",
    "variant" => "K0-DENSE-PUBLIC",
    "solve_api_version" => string(SOLVE_API_VERSION),
    "case_count" => length(case_traces),
    "starts_per_case" => 32,
    "cases" => case_traces,
)

mkpath(dirname(OUTPUT_PATH))
open(OUTPUT_PATH, "w") do io
    write(io, canonical_json(output))
    write(io, '\n')
end
println("captured JAC003 K0 public control traces at ", OUTPUT_PATH)
