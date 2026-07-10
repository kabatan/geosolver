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
const PRIMARY_REPRESENTATIONS = (
    "base",
    "signed-permutation",
    "semantic-equivalent-row-rescaling",
)
const SAFETY_REPRESENTATION = "orthogonal-safety"

function _stage_contract(candidate_version, assessor_version)
    pair = (String(candidate_version), String(assessor_version))
    if pair == (
        "exp-local-003-candidate-inputs/v1",
        "exp-local-003-generator-assessor-projection/v1",
    )
        return (;
            stage = "development",
            output_version = "exp-local-003-calibration-truth/v1",
            case_count = 64,
            latent_group_count = 16,
            latent_groups = 0:1,
            representations = (PRIMARY_REPRESENTATIONS..., SAFETY_REPRESENTATION),
            safety_qz_audit_status = "checked",
            safety_case_count = 16,
        )
    elseif pair == (
        "exp-local-003-locked-candidate-inputs/v1",
        "exp-local-003-locked-generator-assessor-projection/v1",
    )
        return (;
            stage = "locked",
            output_version = "exp-local-003-locked-calibration-truth/v1",
            case_count = 96,
            latent_group_count = 32,
            latent_groups = 2:5,
            representations = PRIMARY_REPRESENTATIONS,
            safety_qz_audit_status = "not_applicable_locked",
            safety_case_count = 0,
        )
    end
    error("candidate and assessor projection versions do not form a supported stage pair")
end

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

function _classify_calibration_observation(observation, residual_count::Int)
    observation.status == EVAL_OK || return nothing, "invalid_status"
    length(observation.relations) == residual_count ||
        return nothing, "residual_dimension_mismatch"
    values = Float64[Float64(relation.scaled) for relation in observation.relations]
    all(isfinite, values) || return nothing, "nonfinite_q"
    return values, "valid"
end

function _has_nonfinite_q(vector, scales)
    length(vector) == length(scales) ||
        throw(ArgumentError("z and model-scale dimensions differ"))
    return any(!isfinite(z / a) for (z, a) in zip(vector, scales))
end

function _calibration_record(
    z_vectors,
    residual_count::Int;
    q_nonfinite_count::Int = 0,
)
    0 <= q_nonfinite_count <= Base.count(isnothing, z_vectors) || throw(
        ArgumentError(
            "pre-scale q_nonfinite_count exceeds discarded calibration vectors",
        ),
    )
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
    # Invalid/nonfinite z observations are already included by the caller.
    # Also execute q=z/a after the frozen joint scale is known: a finite z can
    # still overflow this division, and such an observation is a model failure.
    q_nonfinite_count += sum(z_vectors; init = 0) do vector
        vector === nothing && return 0
        return Int(_has_nonfinite_q(vector, scales))
    end
    rank_bits = _float_bits.(ranks)
    scale_bits = _float_bits.(scales)
    return Dict{String,Any}(
        "valid_vector_count" => count,
        "nearest_rank_index" => rank_index,
        "r_bits" => rank_bits,
        "a_bits" => scale_bits,
        "a_vector_sha256" => string(canonical_json_hash(scale_bits)),
        "q_nonfinite_count" => q_nonfinite_count,
        "joint_fallback_reason" => fallback,
        "clamp_reasons" => clamp_reasons,
    ), scales
end

function _finite_metadata_vector(raw, label::String)
    raw isa AbstractVector || error("$label must be an array")
    values = Float64[]
    for (index, value) in enumerate(raw)
        converted = try
            Float64(value)
        catch
            error("$label[$(index - 1)] is not binary64 numeric data")
        end
        isfinite(converted) || error("$label[$(index - 1)] is nonfinite")
        push!(values, converted)
    end
    return values
end

function _safe_midpoint_halfwidth(lower::Float64, upper::Float64)
    lower < upper || error("compiled variable bounds are not strictly ordered")
    difference = upper - lower
    if isfinite(difference)
        halfwidth = difference / 2.0
        midpoint = lower + halfwidth
    else
        halfwidth = upper / 2.0 - lower / 2.0
        midpoint = lower / 2.0 + upper / 2.0
    end
    isfinite(midpoint) && isfinite(halfwidth) && halfwidth > 0.0 ||
        error("compiled bounds do not have a safe finite midpoint and halfwidth")
    return midpoint, halfwidth
end

function _row_audit(rows, compiled_variables, label::String)
    dimension = length(compiled_variables)
    dimension_mismatch_count = 0
    nonfinite_coordinate_count = 0
    out_of_bounds_coordinate_count = 0
    for (row_index, row) in enumerate(rows)
        if !(row isa AbstractVector) || length(row) != dimension
            dimension_mismatch_count += 1
            continue
        end
        for column in 1:dimension
            value = try
                Float64(row[column])
            catch
                error("$label row $(row_index - 1) column $(column - 1) is not numeric")
            end
            if !isfinite(value)
                nonfinite_coordinate_count += 1
                continue
            end
            spec = compiled_variables[column].spec
            if (spec.lower !== nothing && value < Float64(spec.lower)) ||
               (spec.upper !== nothing && value > Float64(spec.upper))
                out_of_bounds_coordinate_count += 1
            end
        end
    end
    return (;
        dimension_mismatch_count,
        nonfinite_coordinate_count,
        out_of_bounds_coordinate_count,
    )
end

function _compiled_numeric_metadata_audit(case_document, compiled)
    key = String(case_document["opaque_case_key"])
    metadata = case_document["public_numeric_metadata"]
    variable_count = length(compiled.variables)
    residual_count = length(compiled.relations)
    metadata_mismatch_count = 0

    Int(metadata["dimension"]) == variable_count || (metadata_mismatch_count += 1)
    Int(metadata["relation_count"]) == residual_count || (metadata_mismatch_count += 1)
    metadata["logical_capability"] == "C0" || (metadata_mismatch_count += 1)

    public_bounds_raw = metadata["bounds"]
    public_bounds_raw isa AbstractVector || error("public bounds must be an array for $key")
    public_bounds = Tuple{Float64,Float64}[]
    for (index, bound) in enumerate(public_bounds_raw)
        bound isa AbstractVector && length(bound) == 2 ||
            error("public bound $(index - 1) is not a two-element row for $key")
        pair = _finite_metadata_vector(bound, "public bound $(index - 1)")
        push!(public_bounds, (pair[1], pair[2]))
    end
    public_origins = _finite_metadata_vector(metadata["origins"], "public origins")
    public_variable_scales =
        _finite_metadata_vector(metadata["variable_scales"], "public variable scales")
    public_relation_scales =
        _finite_metadata_vector(metadata["relation_scales"], "public relation scales")
    length(public_bounds) == variable_count || (metadata_mismatch_count += 1)
    length(public_origins) == variable_count || (metadata_mismatch_count += 1)
    length(public_variable_scales) == variable_count || (metadata_mismatch_count += 1)
    length(public_relation_scales) == residual_count || (metadata_mismatch_count += 1)

    variable_records = Dict{String,Any}[]
    for (index, variable) in enumerate(compiled.variables)
        spec = variable.spec
        spec.lower === nothing && error("compiled variable $(index - 1) has no lower bound")
        spec.upper === nothing && error("compiled variable $(index - 1) has no upper bound")
        lower = Float64(spec.lower)
        upper = Float64(spec.upper)
        origin = Float64(spec.origin)
        scale = Float64(spec.scale)
        all(isfinite, (lower, upper, origin, scale)) ||
            error("compiled variable $(index - 1) contains nonfinite numeric metadata")
        midpoint, halfwidth = _safe_midpoint_halfwidth(lower, upper)
        if index <= length(public_bounds)
            public_lower, public_upper = public_bounds[index]
            _same_bits(lower, public_lower) || (metadata_mismatch_count += 1)
            _same_bits(upper, public_upper) || (metadata_mismatch_count += 1)
        end
        if index > length(public_origins) || !_same_bits(origin, public_origins[index])
            metadata_mismatch_count += 1
        end
        if index > length(public_variable_scales) ||
           !_same_bits(scale, public_variable_scales[index])
            metadata_mismatch_count += 1
        end
        push!(
            variable_records,
            Dict{String,Any}(
                "variable_index" => index - 1,
                "lower_bits" => _float_bits(lower),
                "upper_bits" => _float_bits(upper),
                "origin_bits" => _float_bits(origin),
                "scale_bits" => _float_bits(scale),
                "safe_midpoint_bits" => _float_bits(midpoint),
                "safe_halfwidth_bits" => _float_bits(halfwidth),
            ),
        )
    end

    relation_scale_bits = String[]
    for (index, relation) in enumerate(compiled.relations)
        scale = Float64(relation.scale)
        isfinite(scale) && scale > 0.0 ||
            error("compiled relation $(index - 1) has an invalid semantic scale")
        if index > length(public_relation_scales) ||
           !_same_bits(scale, public_relation_scales[index])
            metadata_mismatch_count += 1
        end
        push!(relation_scale_bits, _float_bits(scale))
    end

    calibration_audit = _row_audit(
        case_document["calibration_points"],
        compiled.variables,
        "calibration",
    )
    start_audit = _row_audit(case_document["starts"], compiled.variables, "start")
    input_audit = Dict{String,Any}(
        "calibration_rows_checked" => length(case_document["calibration_points"]),
        "start_rows_checked" => length(case_document["starts"]),
        "calibration_row_dimension_mismatch_count" =>
            calibration_audit.dimension_mismatch_count,
        "start_row_dimension_mismatch_count" => start_audit.dimension_mismatch_count,
        "calibration_nonfinite_coordinate_count" =>
            calibration_audit.nonfinite_coordinate_count,
        "start_nonfinite_coordinate_count" => start_audit.nonfinite_coordinate_count,
        "calibration_out_of_bounds_coordinate_count" =>
            calibration_audit.out_of_bounds_coordinate_count,
        "start_out_of_bounds_coordinate_count" => start_audit.out_of_bounds_coordinate_count,
        "public_numeric_metadata_bit_mismatch_count" => metadata_mismatch_count,
        "unsafe_midpoint_halfwidth_count" => 0,
    )
    failures = sum(Int(value) for (name, value) in input_audit if endswith(name, "_count"))
    failures == 0 || error("candidate numeric/input audit failed for $key: $input_audit")
    return Dict{String,Any}(
        "variables" => variable_records,
        "relation_semantic_scale_bits" => relation_scale_bits,
    ), input_audit
end

function _gold_target_contract(gold)
    configurations = gold["configurations"]
    targets_raw = gold["targets"]
    configurations isa AbstractVector && !isempty(configurations) ||
        error("Gold configurations must be a nonempty array")
    targets_raw isa AbstractVector && !isempty(targets_raw) ||
        error("Gold targets must be a nonempty array")
    configuration_count = length(configurations)
    coverage = zeros(Int, configuration_count)
    target_for_configuration = fill(-1, configuration_count)
    targets = NamedTuple[]
    out_of_range_index_count = 0
    for (target_index, target_raw) in enumerate(targets_raw)
        lower = Float64(target_raw["lower"])
        upper = Float64(target_raw["upper"])
        isfinite(lower) && isfinite(upper) && lower <= upper ||
            error("Gold target interval $(target_index - 1) is not finite and ordered")
        indexes = target_raw["configuration_indexes"]
        indexes isa AbstractVector && !isempty(indexes) ||
            error("Gold target interval $(target_index - 1) has no configuration indexes")
        for raw_index in indexes
            raw_index isa Integer || error("Gold configuration index is not an integer")
            configuration_index = Int(raw_index)
            if 0 <= configuration_index < configuration_count
                coverage[configuration_index + 1] += 1
                target_for_configuration[configuration_index + 1] = target_index - 1
            else
                out_of_range_index_count += 1
            end
        end
        push!(targets, (; lower, upper, target_index = target_index - 1))
    end
    coverage_exact = out_of_range_index_count == 0 && all(==(1), coverage)
    ordered = sort(targets; by = target -> (target.lower, target.upper))
    distinct_nonoverlapping = length(ordered) <= 1 || all(
        ordered[index].upper < ordered[index + 1].lower for
        index in 1:(length(ordered) - 1)
    )
    return (;
        configurations,
        targets,
        target_for_configuration,
        coverage_exact,
        distinct_nonoverlapping,
    )
end

function _branch_decision_document(observation)
    return [
        Dict{String,Any}(
            "choice_node" => string(branch.decision.choice_node),
            "choice_key" => string(branch.decision.key),
        ) for branch in observation.branches
    ]
end

function _canonical_replay_document(observation)
    target_bits = observation.target isa Real ?
                  _float_bits(Float64(observation.target)) : "not-real"
    return Dict{String,Any}(
        "status" => string(observation.status),
        "target_bits" => target_bits,
        "relation_scaled_bits" =>
            [_float_bits(Float64(relation.scaled)) for relation in observation.relations],
        "guard_validity" => [Bool(guard.valid) for guard in observation.guards],
        "domain_validity" => [Bool(domain.valid) for domain in observation.domains],
        "branch_decisions" => _branch_decision_document(observation),
    )
end

function _canonical_decision_document(
    observation,
    validation,
    residual_within_tolerance::Bool,
    target_within_tolerance::Bool,
    target_index::Int,
)
    return Dict{String,Any}(
        "canonical_status" => string(observation.status),
        "validation_accepted" => Bool(validation.accepted),
        "residual_within_tolerance" => residual_within_tolerance,
        "target_within_interval_tolerance" => target_within_tolerance,
        "target_interval_index" => target_index,
        "target_bits" => _float_bits(Float64(observation.target)),
        "guard_validity" => [Bool(guard.valid) for guard in observation.guards],
        "domain_validity" => [Bool(domain.valid) for domain in observation.domains],
        "branch_decisions" => _branch_decision_document(observation),
    )
end

function _gold_audit(assessor_case, compiled)
    key = String(assessor_case["opaque_case_key"])
    gold_document = assessor_case["gold"]
    gold_identity_key = String(gold_document["identity_key"])
    occursin(r"^[0-9a-f]{64}$", gold_identity_key) ||
        error("Gold identity key is not a full lowercase digest for $key")
    tolerances = assessor_case["tolerances"]
    configuration_tolerance = Float64(tolerances["configuration_absolute"])
    target_tolerance = Float64(tolerances["target_absolute"])
    canonical_tolerance = Float64(tolerances["canonical_residual"])
    all(
        value -> isfinite(value) && value > 0.0,
        (configuration_tolerance, target_tolerance, canonical_tolerance),
    ) || error("Gold tolerances must be finite and positive for $key")
    contract = _gold_target_contract(gold_document)
    dimension = length(compiled.variables)
    coordinates_by_index = Vector{Vector{Float64}}()
    for (configuration_index, raw) in enumerate(contract.configurations)
        raw isa AbstractVector && length(raw) == dimension || error(
            "Gold configuration $(configuration_index - 1) has the wrong dimension for $key",
        )
        coordinates = Float64[Float64(value) for value in raw]
        all(isfinite, coordinates) ||
            error("Gold configuration $(configuration_index - 1) is nonfinite for $key")
        push!(coordinates_by_index, coordinates)
    end

    options = CandidateValidationOptions(
        residual_tolerance = canonical_tolerance,
        target_consistency_tolerance = target_tolerance,
    )
    audits = Dict{String,Any}[]
    decision_documents = Dict{String,Any}[]
    canonical_eval_ok_count = 0
    validation_accepted_count = 0
    residual_within_tolerance_count = 0
    target_within_interval_tolerance_count = 0
    canonical_replay_agreement_count = 0
    for (configuration_index, coordinates) in enumerate(coordinates_by_index)
        target_index = contract.target_for_configuration[configuration_index]
        target_index >= 0 || continue
        interval = contract.targets[target_index + 1]
        canonical = evaluate_canonical(compiled, coordinates; capability = C0)
        validation = validate_candidate(compiled, coordinates; options)
        canonical.status == EVAL_OK && (canonical_eval_ok_count += 1)
        validation.accepted && (validation_accepted_count += 1)

        residuals = Float64[abs(Float64(relation.scaled)) for relation in canonical.relations]
        max_residual = isempty(residuals) ? Inf : maximum(residuals)
        residual_within_tolerance =
            length(residuals) == length(compiled.relations) &&
            all(isfinite, residuals) &&
            max_residual <= canonical_tolerance
        residual_within_tolerance && (residual_within_tolerance_count += 1)

        target = canonical.target isa Real ? Float64(canonical.target) : NaN
        target_distance = if !isfinite(target)
            Inf
        elseif target < interval.lower
            interval.lower - target
        elseif target > interval.upper
            target - interval.upper
        else
            0.0
        end
        target_within_tolerance = isfinite(target_distance) && target_distance <= target_tolerance
        target_within_tolerance && (target_within_interval_tolerance_count += 1)
        replay_agrees = _canonical_replay_document(canonical) ==
                         _canonical_replay_document(validation.canonical_observation)
        replay_agrees && (canonical_replay_agreement_count += 1)

        if canonical.status == EVAL_OK && canonical.target isa Real && isfinite(target)
            decision = _canonical_decision_document(
                canonical,
                validation,
                residual_within_tolerance,
                target_within_tolerance,
                target_index,
            )
            push!(decision_documents, decision)
            push!(
                audits,
                Dict{String,Any}(
                    "configuration_index" => configuration_index - 1,
                    "target_interval_index" => target_index,
                    "canonical_status" => string(canonical.status),
                    "validation_accepted" => Bool(validation.accepted),
                    "validation_method" => String(validation.method),
                    "max_abs_scaled_residual_bits" => _float_bits(max_residual),
                    "canonical_target_bits" => _float_bits(target),
                    "target_interval_distance_bits" => _float_bits(target_distance),
                    "residual_within_tolerance" => residual_within_tolerance,
                    "target_within_interval_tolerance" => target_within_tolerance,
                    "canonical_replay_agrees" => replay_agrees,
                    "canonical_decision_sha256" => string(canonical_json_hash(decision)),
                ),
            )
        end
    end

    configuration_count = length(coordinates_by_index)
    failure_counts = Dict{String,Int}(
        "gold_configuration_index_coverage_failure_count" =>
            contract.coverage_exact ? 0 : 1,
        "gold_target_interval_overlap_failure_count" =>
            contract.distinct_nonoverlapping ? 0 : 1,
        "gold_canonical_status_failure_count" =>
            configuration_count - canonical_eval_ok_count,
        "gold_validation_rejection_count" =>
            configuration_count - validation_accepted_count,
        "gold_residual_tolerance_failure_count" =>
            configuration_count - residual_within_tolerance_count,
        "gold_target_tolerance_failure_count" =>
            configuration_count - target_within_interval_tolerance_count,
        "gold_canonical_replay_mismatch_count" =>
            configuration_count - canonical_replay_agreement_count,
    )
    all(iszero, values(failure_counts)) ||
        error("Gold audit failed for $key: $failure_counts")
    length(audits) == configuration_count == length(decision_documents) ||
        error("Gold audit did not produce one record per configuration for $key")
    return Dict{String,Any}(
        "gold_identity_key" => gold_identity_key,
        "configuration_count" => configuration_count,
        "target_interval_count" => length(contract.targets),
        "configuration_absolute_tolerance_bits" => _float_bits(configuration_tolerance),
        "target_absolute_tolerance_bits" => _float_bits(target_tolerance),
        "canonical_residual_tolerance_bits" => _float_bits(canonical_tolerance),
        "configuration_index_coverage_exact" => contract.coverage_exact,
        "target_intervals_distinct_nonoverlapping" => contract.distinct_nonoverlapping,
        "canonical_eval_ok_count" => canonical_eval_ok_count,
        "validation_accepted_count" => validation_accepted_count,
        "residual_within_tolerance_count" => residual_within_tolerance_count,
        "target_within_interval_tolerance_count" =>
            target_within_interval_tolerance_count,
        "canonical_replay_agreement_count" => canonical_replay_agreement_count,
        "configurations" => audits,
    ), (;
        coordinates = coordinates_by_index,
        decisions = decision_documents,
        configuration_tolerance,
        failure_counts,
    )
end

function _capture_case(case_document, assessor_case, registry)
    case_document["opaque_case_key"] == assessor_case["opaque_case_key"] ||
        error("candidate/assessor key mismatch during case capture")
    problem_document = case_document["problem_document"]
    string(canonical_json_hash(problem_document)) == case_document["problem_sha256"] ||
        error("problem hash mismatch for $(case_document["opaque_case_key"])")
    points = case_document["calibration_points"]
    string(canonical_json_hash(points)) == case_document["calibration_points_sha256"] ||
        error("calibration point hash mismatch for $(case_document["opaque_case_key"])")
    length(points) == 64 || error("a calibration block must contain exactly 64 points")
    starts = case_document["starts"]
    string(canonical_json_hash(starts)) == case_document["starts_sha256"] ||
        error("start hash mismatch for $(case_document["opaque_case_key"])")
    length(starts) == 32 || error("a start block must contain exactly 32 points")

    problem = decode_problem_document(problem_document, registry)
    compiled = compile_problem(problem, registry)
    supports(capabilities(compiled), C0) || error("calibration problem does not support C0")
    !supports(capabilities(compiled), C1) || error("fixture unexpectedly exposes C1")
    !supports(capabilities(compiled), C2) || error("fixture unexpectedly exposes C2")
    residual_count = length(compiled.relations)
    residual_count > 0 || error("calibration problem has no residuals")
    logical_cost = compiled.logical_evaluation_cost
    logical_cost > 0 || error("compiled logical evaluation cost must be positive")
    compiled_numeric_metadata, candidate_input_audit =
        _compiled_numeric_metadata_audit(case_document, compiled)

    z_vectors = Union{Nothing,Vector{Float64}}[]
    observations = Dict{String,Any}[]
    q_nonfinite_count = 0
    for point in points
        coordinates = Float64[Float64(value) for value in point]
        observation = evaluate(compiled, coordinates; capability = C0)
        z, classification = _classify_calibration_observation(observation, residual_count)
        classification == "nonfinite_q" && (q_nonfinite_count += 1)
        push!(z_vectors, z)
        push!(
            observations,
            Dict{String,Any}(
                "status" => string(observation.status),
                "evaluation_cost" => observation.evaluation_cost,
                "classification" => classification,
                "z_bits" => z === nothing ? String[] : _float_bits.(z),
            ),
        )
    end
    calibration, scales = _calibration_record(
        z_vectors,
        residual_count;
        q_nonfinite_count,
    )
    for (index, vector) in enumerate(z_vectors)
        vector === nothing && continue
        if _has_nonfinite_q(vector, scales)
            observations[index]["classification"] = "nonfinite_q"
        end
    end
    gold_audit, gold_internal = _gold_audit(assessor_case, compiled)
    record = Dict{String,Any}(
        "opaque_case_key" => case_document["opaque_case_key"],
        "problem_sha256" => case_document["problem_sha256"],
        "calibration_points_sha256" => case_document["calibration_points_sha256"],
        "starts_sha256" => case_document["starts_sha256"],
        "variable_count" => length(compiled.variables),
        "residual_count" => residual_count,
        "logical_evaluation_cost" => logical_cost,
        "compiled_numeric_metadata" => compiled_numeric_metadata,
        "candidate_input_audit" => candidate_input_audit,
        "gold_audit" => gold_audit,
        "observations" => observations,
        "calibration" => calibration,
    )
    return record, (; z_vectors, scales, gold = gold_internal)
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

function _inverse_mapped_coordinates(truth, coordinates)
    mapping = truth["inverse_mapping"]
    permutation = Int[Int(value) for value in mapping["base_from_candidate_permutation"]]
    signs = Float64[Float64(value) for value in mapping["base_from_candidate_signs"]]
    dimension = length(coordinates)
    length(permutation) == length(signs) == dimension ||
        error("inverse variable mapping dimension mismatch")
    sort(permutation) == collect(0:(dimension - 1)) ||
        error("inverse variable mapping is not a permutation")
    all(sign -> sign == -1.0 || sign == 1.0, signs) ||
        error("inverse variable mapping contains a non-sign multiplier")
    return Float64[
        signs[base_index] * coordinates[permutation[base_index] + 1] for
        base_index in 1:dimension
    ]
end

function _audit_primary_gold_group!(truths, internal)
    primary = [truth for truth in truths if truth["expected_invariant"]]
    length(primary) == 3 || error("latent group must have exactly three primary cases")
    Set(String(truth["representation"]) for truth in primary) ==
        Set(PRIMARY_REPRESENTATIONS) ||
        error("latent group has the wrong primary representation set")
    base_truth = only(truth for truth in primary if truth["representation"] == "base")
    base_gold = internal[String(base_truth["opaque_case_key"])].gold
    comparisons_checked = 0
    for truth in primary
        truth["representation"] == "base" && continue
        key = String(truth["opaque_case_key"])
        candidate_gold = internal[key].gold
        length(candidate_gold.coordinates) == length(base_gold.coordinates) ||
            error("primary Gold configuration count mismatch for $key")
        length(candidate_gold.decisions) == length(base_gold.decisions) ||
            error("primary canonical decision count mismatch for $key")
        for configuration_index in eachindex(base_gold.coordinates)
            mapped = _inverse_mapped_coordinates(
                truth,
                candidate_gold.coordinates[configuration_index],
            )
            base = base_gold.coordinates[configuration_index]
            length(mapped) == length(base) ||
                error("primary inverse-mapped Gold dimension mismatch for $key")
            all(
                abs(observed - expected) <= candidate_gold.configuration_tolerance for
                (observed, expected) in zip(mapped, base)
            ) || error(
                "primary inverse-mapped Gold configuration mismatch for $key configuration $(configuration_index - 1)",
            )
            candidate_gold.decisions[configuration_index] ==
                base_gold.decisions[configuration_index] || error(
                "primary inverse-mapped canonical decision mismatch for $key configuration $(configuration_index - 1)",
            )
            comparisons_checked += 1
        end
    end
    return comparisons_checked
end

function _grouped_truth(assessor_cases)
    grouped = Dict{String,Vector{Any}}()
    for truth in assessor_cases
        identity = String(truth["gold"]["identity_key"])
        occursin(r"^[0-9a-f]{64}$", identity) ||
            error("assessor Gold identity key is not a full lowercase digest")
        push!(get!(grouped, identity, Any[]), truth)
    end
    return grouped
end

function _validate_stage_assessor_contract(assessor_cases, contract)
    length(assessor_cases) == contract.case_count || error(
        "$(contract.stage) assessor projection must contain exactly $(contract.case_count) cases",
    )
    expected_representations = Set(contract.representations)
    expected_pairs = Set(
        (family_ordinal, latent_group) for family_ordinal in 0:7 for
        latent_group in contract.latent_groups
    )
    observed_pairs = Set{Tuple{Int,Int}}()
    family_by_ordinal = Dict{Int,String}()
    identities_by_pair = Dict{Tuple{Int,Int},Set{String}}()
    for truth in assessor_cases
        family_ordinal = Int(truth["family_ordinal"])
        latent_group = Int(truth["latent_group"])
        representation = String(truth["representation"])
        family_id = String(truth["family_id"])
        0 <= family_ordinal <= 7 || error("assessor family ordinal lies outside 0:7")
        latent_group in contract.latent_groups || error(
            "$(contract.stage) assessor latent group $latent_group lies outside $(first(contract.latent_groups)):$(last(contract.latent_groups))",
        )
        representation in expected_representations || error(
            "$(contract.stage) assessor contains forbidden representation $representation",
        )
        expected_invariant = representation != SAFETY_REPRESENTATION
        truth["expected_invariant"] === expected_invariant || error(
            "assessor expected_invariant disagrees with representation $representation",
        )
        if haskey(family_by_ordinal, family_ordinal)
            family_by_ordinal[family_ordinal] == family_id ||
                error("one family ordinal maps to multiple family identifiers")
        else
            family_by_ordinal[family_ordinal] = family_id
        end
        pair = (family_ordinal, latent_group)
        push!(observed_pairs, pair)
        identity = String(truth["gold"]["identity_key"])
        push!(get!(identities_by_pair, pair, Set{String}()), identity)
    end
    observed_pairs == expected_pairs ||
        error("$(contract.stage) assessor does not cover the exact family/group product")
    length(family_by_ordinal) == 8 && allunique(values(family_by_ordinal)) ||
        error("assessor must carry eight one-to-one family ordinal identifiers")
    all(length(identities) == 1 for identities in values(identities_by_pair)) ||
        error("one declared family/group pair maps to multiple Gold identities")

    grouped = _grouped_truth(assessor_cases)
    length(grouped) == contract.latent_group_count || error(
        "$(contract.stage) assessor must contain $(contract.latent_group_count) Gold identity groups",
    )
    for truths in values(grouped)
        length(truths) == length(contract.representations) || error(
            "$(contract.stage) Gold identity group has the wrong representation count",
        )
        labels = Set(
            (Int(truth["family_ordinal"]), Int(truth["latent_group"])) for truth in truths
        )
        length(labels) == 1 || error("Gold identity key crosses declared latent groups")
        representations = [String(truth["representation"]) for truth in truths]
        length(unique(representations)) == length(representations) ||
            error("Gold identity group repeats a representation")
        Set(representations) == expected_representations || error(
            "$(contract.stage) Gold identity group has the wrong representation set",
        )
    end
    return grouped
end

"""
Capture authoritative development or locked C0 calibration truth without importing candidate outcomes.

``candidate_document`` and ``assessor_document`` remain separate inputs.  The
assessor mapping is used only after every candidate problem has been compiled
and evaluated, to reject malformed primary and Safety representation fixtures.
"""
function capture_calibration_truth(candidate_document, assessor_document)
    contract = _stage_contract(
        candidate_document["schema_version"],
        assessor_document["schema_version"],
    )
    candidate_cases = candidate_document["cases"]
    assessor_cases = assessor_document["cases"]
    length(candidate_cases) == length(assessor_cases) == contract.case_count || error(
        "$(contract.stage) calibration capture requires exactly $(contract.case_count) cases",
    )
    candidate_document["card_sha256"] == assessor_document["card_sha256"] ||
        error("candidate and assessor card hashes differ")

    assessor_keys = Set(String(case["opaque_case_key"]) for case in assessor_cases)
    candidate_keys = Set(String(case["opaque_case_key"]) for case in candidate_cases)
    length(assessor_keys) == length(candidate_keys) == contract.case_count ||
        error("candidate or assessor projection contains duplicate case keys")
    candidate_keys == assessor_keys || error("candidate and assessor case-key sets differ")
    assessor_by_key =
        Dict(String(case["opaque_case_key"]) => case for case in assessor_cases)
    grouped = _validate_stage_assessor_contract(assessor_cases, contract)

    registry = _registry()
    records = Dict{String,Any}[]
    internal = Dict{String,Any}()
    for case_document in candidate_cases
        key = String(case_document["opaque_case_key"])
        record, case_internal =
            _capture_case(case_document, assessor_by_key[key], registry)
        push!(records, record)
        internal[key] = case_internal
    end
    sort!(records; by = record -> String(record["opaque_case_key"]))

    primary_inverse_comparisons_checked = 0
    for truths in values(grouped)
        _audit_group!(truths, internal)
        primary_inverse_comparisons_checked += _audit_primary_gold_group!(truths, internal)
    end
    gold_configurations_checked =
        sum(Int(record["gold_audit"]["configuration_count"]) for record in records)

    return Dict{String,Any}(
        "schema_version" => contract.output_version,
        "stage" => contract.stage,
        "card_sha256" => candidate_document["card_sha256"],
        "candidate_projection_sha256" => string(canonical_json_hash(candidate_document)),
        "assessor_projection_sha256" => string(canonical_json_hash(assessor_document)),
        "audit" => Dict{String,Any}(
            "latent_groups_checked" => length(grouped),
            "gold_configurations_checked" => gold_configurations_checked,
            "primary_inverse_comparisons_checked" =>
                primary_inverse_comparisons_checked,
            "primary_semantic_z_mismatch_count" => 0,
            "primary_scale_permutation_mismatch_count" => 0,
            "safety_cases_checked" => contract.safety_case_count,
            "safety_qz_audit_status" => contract.safety_qz_audit_status,
            "safety_qz_mismatch_count" => 0,
            "gold_configuration_index_coverage_failure_count" => 0,
            "gold_target_interval_overlap_failure_count" => 0,
            "gold_canonical_status_failure_count" => 0,
            "gold_validation_rejection_count" => 0,
            "gold_residual_tolerance_failure_count" => 0,
            "gold_target_tolerance_failure_count" => 0,
            "gold_canonical_replay_mismatch_count" => 0,
            "primary_inverse_configuration_mismatch_count" => 0,
            "primary_inverse_canonical_decision_mismatch_count" => 0,
            "public_numeric_metadata_bit_mismatch_count" => 0,
            "calibration_row_dimension_mismatch_count" => 0,
            "start_row_dimension_mismatch_count" => 0,
            "calibration_nonfinite_coordinate_count" => 0,
            "start_nonfinite_coordinate_count" => 0,
            "calibration_out_of_bounds_coordinate_count" => 0,
            "start_out_of_bounds_coordinate_count" => 0,
            "unsafe_midpoint_halfwidth_count" => 0,
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
