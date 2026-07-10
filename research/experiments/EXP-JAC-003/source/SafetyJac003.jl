module SafetyJac003

using GeoTargetBase
using GeoTargetCore
using JSON3
using LinearAlgebra
using SHA

include("CandidateJac003.jl")
using .CandidateJac003

const SAFETY_SCHEMA = "exp-jac-003-candidate-safety/v1"

function _matrix_document(matrix)
    return Dict{String,Any}(
        "entries" => Any[
            Any[row - 1, column - 1, matrix[row, column]] for
            row in axes(matrix, 1) for column in axes(matrix, 2) if matrix[row, column] != 0.0
        ],
        "shape" => Any[size(matrix, 1), size(matrix, 2)],
    )
end

function _group_document(event)
    return Dict{String,Any}(
        "columns" => collect(event.columns),
        "completed_fallback_columns" => event.completed_fallback_columns,
        "fallback" => event.fallback,
        "fallback_evaluations" => event.fallback_evaluations,
        "grouped_evaluations" => event.grouped_evaluations,
    )
end

function _finite_difference_pair(case, raw_start; provider_override=nothing)
    variable_count = Int(case["variable_count"])
    residual_count = Int(case["residual_count"])
    structure = compile_structure(case["typed_graph"], variable_count, residual_count)
    provider = provider_override === nothing ? seal_provider(structure) : provider_override
    program = parse_program(case["oracle_program"], variable_count)
    origins = Float64[Float64(value) for value in case["origins"]]
    scales = Float64[Float64(value) for value in case["scales"]]
    lower = Float64[Float64(value) for value in case["lower"]]
    upper = Float64[Float64(value) for value in case["upper"]]
    point = Float64[Float64(value) for value in raw_start]
    u = GeoTargetCore._normalize_problem(point, origins, scales)
    lower_u, upper_u = GeoTargetCore._normalized_bounds(lower, upper, origins, scales)
    evaluate_fn = value -> observation(program, value)
    base = GeoTargetCore._evaluate_local(evaluate_fn, u, origins, scales)
    base.status == EVAL_OK || error("safety base evaluation failed")
    base_residual = GeoTargetCore._float_residual(base)
    step = LocalSolveOptions().finite_difference_step
    dense, dense_evaluations = GeoTargetCore._finite_difference_jacobian(
        evaluate_fn,
        u,
        base_residual,
        origins,
        scales,
        lower_u,
        upper_u,
        step,
    )
    group_events = Any[]
    colored, colored_evaluations, failure =
        GeoTargetCore._sealed_colored_finite_difference_jacobian(
            evaluate_fn,
            u,
            base_residual,
            origins,
            scales,
            lower_u,
            upper_u,
            step,
            provider;
            deadline_ns=typemax(UInt64),
            cancelled=() -> false,
            group_observer=event -> push!(group_events, _group_document(event)),
        )
    return Dict{String,Any}(
        "colored" => _matrix_document(colored),
        "colored_evaluations" => colored_evaluations,
        "dense" => _matrix_document(dense),
        "dense_evaluations" => dense_evaluations,
        "failure" => failure === nothing ? nothing : string(failure),
        "group_events" => group_events,
        "provider_projection_hash" => provider.projection_hash,
        "route_projection_hash" => structure.route_hash,
    )
end

function _corrupted_provider(case)
    variable_count = Int(case["variable_count"])
    residual_count = Int(case["residual_count"])
    structure = compile_structure(case["typed_graph"], variable_count, residual_count)
    supports = [collect(rows) for rows in structure.provider.row_supports]
    removed_column = findfirst(rows -> !isempty(rows), supports)
    removed_column === nothing && error("KNEG requires an active column")
    removed_row = popfirst!(supports[removed_column])
    support_tuple = Tuple(Tuple(rows) for rows in supports)
    groups = CandidateJac003._natural_groups(support_tuple)
    structural_nonzeros = sum(length, support_tuple)
    document = Dict{String,Any}(
        "groups" => Any[collect(group) for group in groups],
        "row_supports" => Any[collect(rows) for rows in support_tuple],
        "structural_nonzeros" => structural_nonzeros,
    )
    projection_hash = string(canonical_json_hash(document))
    provider = GeoTargetCore._sealed_local_jacobian_provider(
        support_tuple,
        groups,
        structural_nonzeros,
        residual_count,
        variable_count,
        projection_hash,
    )
    return provider, removed_row, removed_column
end

function _relation_observation(row, value)
    return RelationObservation(
        NodeId("fallback-r$row"),
        value,
        1.0,
        value,
        nothing,
    )
end

function _fallback_observation(point, base, mode)
    changed = count(index -> point[index] != base[index], eachindex(base))
    grouped = changed > 1
    invalid = grouped && (
        mode == :nonfinite ||
        mode == :length ||
        (mode == :plus_invalid && point[1] > base[1]) ||
        (mode == :minus_invalid && point[1] < base[1])
    )
    if invalid && mode == :nonfinite
        return OracleObservation(
            (), nothing, (), (), (), EVAL_NONFINITE, 1, "forced grouped nonfinite",
        )
    elseif invalid && mode == :length
        return OracleObservation(
            (_relation_observation(1, point[1]),),
            nothing,
            (),
            (),
            (),
            EVAL_OK,
            1,
            nothing,
        )
    elseif invalid
        return OracleObservation(
            (), nothing, (), (), (), EVAL_INVALID_DOMAIN, 1, "forced grouped invalidity",
        )
    end
    relations = (
        _relation_observation(1, point[1]),
        _relation_observation(2, point[2]),
    )
    return OracleObservation(relations, nothing, (), (), (), EVAL_OK, 1, nothing)
end

function _fallback_controls()
    supports = ((1,), (2,))
    groups = ((1, 2),)
    projection = Dict{String,Any}(
        "groups" => Any[collect(group) for group in groups],
        "row_supports" => Any[collect(rows) for rows in supports],
        "structural_nonzeros" => 2,
    )
    provider = GeoTargetCore._sealed_local_jacobian_provider(
        supports,
        groups,
        2,
        2,
        2,
        string(canonical_json_hash(projection)),
    )
    base = [0.125, -0.25]
    origins = zeros(2)
    scales = ones(2)
    lower = fill(-1.0, 2)
    upper = fill(1.0, 2)
    base_residual = copy(base)
    controls = Any[]
    for mode in (:plus_invalid, :minus_invalid, :nonfinite, :length)
        events = Any[]
        matrix, evaluations, failure =
            GeoTargetCore._sealed_colored_finite_difference_jacobian(
                point -> _fallback_observation(point, base, mode),
                copy(base),
                base_residual,
                origins,
                scales,
                lower,
                upper,
                LocalSolveOptions().finite_difference_step,
                provider;
                deadline_ns=typemax(UInt64),
                cancelled=() -> false,
                group_observer=event -> push!(events, _group_document(event)),
            )
        push!(controls, Dict{String,Any}(
            "evaluations" => evaluations,
            "failure" => failure === nothing ? nothing : string(failure),
            "group_events" => events,
            "matrix" => _matrix_document(matrix),
            "mode" => string(mode),
        ))
    end
    return controls
end

function capture_safety(candidate_path::AbstractString)
    candidate_bytes = read(candidate_path)
    expected_sha = get(ENV, "EXP_JAC003_CANDIDATE_SHA256", "")
    isempty(expected_sha) && error("EXP_JAC003_CANDIDATE_SHA256 is required")
    bytes2hex(sha256(candidate_bytes)) == expected_sha || error("candidate SHA-256 mismatch")
    document = JSON3.read(candidate_bytes, Dict{String,Any})
    String(document["schema_version"]) == CANDIDATE_SCHEMA || error("candidate schema drift")
    length(document["cases"]) == 64 || error("safety capture requires 64 cases")
    cases = Any[]
    negatives = Any[]
    for case in document["cases"]
        opaque_id = String(case["opaque_case_id"])
        structure = compile_structure(
            case["typed_graph"],
            Int(case["variable_count"]),
            Int(case["residual_count"]),
        )
        starts = Any[]
        for (start_offset, start) in enumerate(case["starts"])
            pair = _finite_difference_pair(case, start)
            pair["start_index"] = start_offset - 1
            push!(starts, pair)
        end
        push!(cases, Dict{String,Any}(
            "opaque_case_id" => opaque_id,
            "provider_projection_hash" => structure.provider_hash,
            "row_supports" => Any[
                Any[row - 1 for row in rows] for rows in structure.provider.row_supports
            ],
            "route_projection_hash" => structure.route_hash,
            "starts" => starts,
        ))
        provider, removed_row, removed_column = _corrupted_provider(case)
        negative = _finite_difference_pair(
            case,
            first(case["starts"]);
            provider_override=provider,
        )
        negative["opaque_case_id"] = opaque_id
        negative["removed_column"] = removed_column - 1
        negative["removed_row"] = removed_row - 1
        negative["start_index"] = 0
        push!(negatives, negative)
    end
    return Dict{String,Any}(
        "candidate_input_sha256" => expected_sha,
        "case_count" => length(cases),
        "cases" => cases,
        "experiment_id" => "EXP-JAC-003",
        "fallback_controls" => _fallback_controls(),
        "incomplete_pattern_controls" => negatives,
        "schema_version" => SAFETY_SCHEMA,
        "starts_per_case" => 32,
    )
end

function write_safety(path::AbstractString, document)
    ispath(path) && error("safety output already exists")
    temporary = string(path, ".tmp")
    ispath(temporary) && error("safety temporary output already exists")
    mkpath(dirname(abspath(path)))
    open(temporary, "w") do io
        write(io, canonical_json(document))
        write(io, '\n')
        flush(io)
    end
    mv(temporary, path)
    return nothing
end

export capture_safety, write_safety, SAFETY_SCHEMA

end
