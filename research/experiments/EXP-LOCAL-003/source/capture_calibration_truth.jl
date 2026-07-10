module Local3CalibrationTruth

using GeoTargetBase
using GeoTargetCore
using GeoTargetGeometry

include(joinpath(@__DIR__, "Local3FixturePlugin.jl"))
using .Local3FixturePlugin

export capture_calibration_truth, main

const LOWER_MODEL_SCALE = 0x1.0p-40
const UPPER_MODEL_SCALE = 0x1.0p+40
const MINIMUM_VALID_VECTORS = 8

_float_bits(value::Float64) =
    string("0x", string(reinterpret(UInt64, value); base = 16, pad = 16))

function _registry()
    geometry = GeoTargetGeometry.geometry_plugin()
    fixture = Local3FixturePlugin.local3_fixture_plugin()
    builder = RegistryBuilder(allowlist = (geometry.id, fixture.id))
    register!(builder, geometry)
    register!(builder, fixture)
    return freeze(builder)
end

function _finite_z(observation, residual_count::Int)
    observation.status == EVAL_OK || return nothing
    length(observation.relations) == residual_count || return nothing
    values = Float64[Float64(relation.scaled) for relation in observation.relations]
    all(isfinite, values) || return nothing
    return values
end

function _calibration_record(z_vectors, residual_count::Int)
    valid = Vector{Vector{Float64}}()
    for vector in z_vectors
        vector === nothing || push!(valid, vector)
    end
    count = length(valid)
    rank_index = count == 0 ? 0 : cld(3 * count, 4)
    ranks = if count == 0
        zeros(Float64, residual_count)
    else
        Float64[
            sort!(Float64[abs(vector[component]) for vector in valid])[rank_index] for
            component in 1:residual_count
        ]
    end

    fallback = if count < MINIMUM_VALID_VECTORS
        "insufficient_valid_vectors"
    elseif any(value -> !isfinite(value) || value <= 0.0, ranks)
        "nonpositive_or_nonfinite_nearest_rank"
    else
        nothing
    end
    scales = ones(Float64, residual_count)
    clamp_reasons = fill("joint_fallback", residual_count)
    if fallback === nothing
        for component in 1:residual_count
            rank = ranks[component]
            if rank < LOWER_MODEL_SCALE
                scales[component] = LOWER_MODEL_SCALE
                clamp_reasons[component] = "below_0x1.0p-40"
            elseif rank > UPPER_MODEL_SCALE
                scales[component] = UPPER_MODEL_SCALE
                clamp_reasons[component] = "above_0x1.0p+40"
            else
                scales[component] = rank
                clamp_reasons[component] = "none"
            end
        end
    end
    rank_bits = _float_bits.(ranks)
    scale_bits = _float_bits.(scales)
    return Dict{String,Any}(
        "valid_vector_count" => count,
        "nearest_rank_index" => rank_index,
        "r_bits" => rank_bits,
        "a_bits" => scale_bits,
        "a_vector_sha256" => string(canonical_json_hash(scale_bits)),
        "joint_fallback_reason" => fallback,
        "clamp_reasons" => clamp_reasons,
    ), scales
end

function _capture_case(case_document, registry)
    problem_document = case_document["problem_document"]
    string(canonical_json_hash(problem_document)) == case_document["problem_sha256"] ||
        error("problem hash mismatch for $(case_document["opaque_case_key"])")
    points = case_document["calibration_points"]
    string(canonical_json_hash(points)) == case_document["calibration_points_sha256"] ||
        error("calibration point hash mismatch for $(case_document["opaque_case_key"])")
    length(points) == 64 || error("a calibration block must contain exactly 64 points")

    problem = decode_problem_document(problem_document, registry)
    compiled = compile_problem(problem, registry)
    supports(capabilities(compiled), C0) || error("calibration problem does not support C0")
    !supports(capabilities(compiled), C1) || error("fixture unexpectedly exposes C1")
    !supports(capabilities(compiled), C2) || error("fixture unexpectedly exposes C2")
    residual_count = length(compiled.relations)
    residual_count > 0 || error("calibration problem has no residuals")
    logical_cost = compiled.logical_evaluation_cost
    logical_cost > 0 || error("compiled logical evaluation cost must be positive")

    z_vectors = Union{Nothing,Vector{Float64}}[]
    observations = Dict{String,Any}[]
    for point in points
        coordinates = Float64[Float64(value) for value in point]
        observation = evaluate(compiled, coordinates; capability = C0)
        z = _finite_z(observation, residual_count)
        push!(z_vectors, z)
        push!(
            observations,
            Dict{String,Any}(
                "status" => string(observation.status),
                "evaluation_cost" => observation.evaluation_cost,
                "z_bits" => z === nothing ? String[] : _float_bits.(z),
            ),
        )
    end
    calibration, scales = _calibration_record(z_vectors, residual_count)
    record = Dict{String,Any}(
        "opaque_case_key" => case_document["opaque_case_key"],
        "problem_sha256" => case_document["problem_sha256"],
        "calibration_points_sha256" => case_document["calibration_points_sha256"],
        "variable_count" => length(compiled.variables),
        "residual_count" => residual_count,
        "logical_evaluation_cost" => logical_cost,
        "observations" => observations,
        "calibration" => calibration,
    )
    return record, z_vectors, scales
end

function _row_value(row, values)
    terms = Float64[]
    for (column, coefficient_raw) in enumerate(row)
        coefficient = Float64(coefficient_raw)
        iszero(coefficient) && continue
        push!(terms, coefficient * values[column])
    end
    isempty(terms) && return 0.0
    result = first(terms)
    for term in Iterators.drop(terms, 1)
        result += term
    end
    return result
end

function _same_bits(left::Float64, right::Float64)
    return reinterpret(UInt64, left) == reinterpret(UInt64, right)
end

function _audit_group!(truths, internal)
    base_truth_index = findfirst(truth -> truth["representation"] == "base", truths)
    base_truth_index === nothing && error("latent group has no base representation")
    base_truth = truths[base_truth_index]
    base_key = base_truth["opaque_case_key"]
    base_z = internal[base_key].z_vectors
    base_scales = internal[base_key].scales

    for truth in truths
        key = truth["opaque_case_key"]
        candidate_z = internal[key].z_vectors
        length(candidate_z) == length(base_z) || error("calibration block length mismatch")
        semantic_matrix = truth["inverse_mapping"]["semantic_z_from_base"]
        for point_index in eachindex(base_z)
            base_vector = base_z[point_index]
            candidate_vector = candidate_z[point_index]
            (base_vector === nothing) == (candidate_vector === nothing) || error(
                "C0 validity status differs inside latent group for $key point $(point_index - 1)",
            )
            base_vector === nothing && continue
            length(candidate_vector) == length(semantic_matrix) ||
                error("semantic residual row count mismatch")
            for row_index in eachindex(semantic_matrix)
                expected = _row_value(semantic_matrix[row_index], base_vector)
                _same_bits(candidate_vector[row_index], expected) || error(
                    "semantic z transform mismatch for $key point $(point_index - 1) row $(row_index - 1)",
                )
            end
        end

        if truth["expected_invariant"]
            expected_scales = Float64[
                _row_value(abs.(Float64.(row)), base_scales) for row in semantic_matrix
            ]
            length(expected_scales) == length(internal[key].scales) ||
                error("calibration scale vector length mismatch")
            all(
                _same_bits(observed, expected) for
                (observed, expected) in zip(internal[key].scales, expected_scales)
            ) || error("primary calibration scale is not the expected residual permutation for $key")
        end
    end
    return nothing
end

function _grouped_truth(assessor_cases)
    grouped = Dict{Tuple{String,Int},Vector{Any}}()
    for truth in assessor_cases
        identity = (String(truth["family_id"]), Int(truth["latent_group"]))
        push!(get!(grouped, identity, Any[]), truth)
    end
    return grouped
end

"""
Capture authoritative C0 calibration truth without importing candidate outcomes.

``candidate_document`` and ``assessor_document`` remain separate inputs.  The
assessor mapping is used only after every candidate problem has been compiled
and evaluated, to reject malformed primary and Safety representation fixtures.
"""
function capture_calibration_truth(candidate_document, assessor_document)
    candidate_document["schema_version"] == "exp-local-003-candidate-inputs/v1" ||
        error("unexpected candidate projection schema")
    assessor_document["schema_version"] ==
        "exp-local-003-generator-assessor-projection/v1" ||
        error("unexpected generator assessor projection schema")
    candidate_cases = candidate_document["cases"]
    assessor_cases = assessor_document["cases"]
    length(candidate_cases) == length(assessor_cases) == 64 ||
        error("development calibration capture requires exactly 64 cases")

    assessor_keys = Set(String(case["opaque_case_key"]) for case in assessor_cases)
    candidate_keys = Set(String(case["opaque_case_key"]) for case in candidate_cases)
    candidate_keys == assessor_keys || error("candidate and assessor case-key sets differ")

    registry = _registry()
    records = Dict{String,Any}[]
    internal = Dict{String,Any}()
    for case_document in candidate_cases
        record, z_vectors, scales = _capture_case(case_document, registry)
        key = String(case_document["opaque_case_key"])
        push!(records, record)
        internal[key] = (; z_vectors, scales)
    end
    sort!(records; by = record -> String(record["opaque_case_key"]))

    grouped = _grouped_truth(assessor_cases)
    length(grouped) == 16 || error("assessor projection must contain 16 latent groups")
    for truths in values(grouped)
        length(truths) == 4 || error("each latent group must contain four representations")
        _audit_group!(truths, internal)
    end

    return Dict{String,Any}(
        "schema_version" => "exp-local-003-calibration-truth/v1",
        "card_sha256" => candidate_document["card_sha256"],
        "candidate_projection_sha256" => string(canonical_json_hash(candidate_document)),
        "assessor_projection_sha256" => string(canonical_json_hash(assessor_document)),
        "audit" => Dict{String,Any}(
            "latent_groups_checked" => length(grouped),
            "primary_semantic_z_mismatch_count" => 0,
            "primary_scale_permutation_mismatch_count" => 0,
            "safety_qz_mismatch_count" => 0,
        ),
        "cases" => records,
    )
end

function main(arguments = ARGS)
    length(arguments) == 2 || error(
        "usage: capture_calibration_truth.jl CANDIDATE.json ASSESSOR.json",
    )
    candidate = parse_protocol_json(read(arguments[1], String))
    assessor = parse_protocol_json(read(arguments[2], String))
    print(canonical_json(capture_calibration_truth(candidate, assessor)))
    return nothing
end

end

if abspath(PROGRAM_FILE) == @__FILE__
    Local3CalibrationTruth.main(ARGS)
end
