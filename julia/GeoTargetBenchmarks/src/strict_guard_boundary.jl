const _STRICT_GUARD_CASES = (:well_separated, :near_boundary, :on_boundary)

struct StrictGuardBoundaryParams
    boundary_case::Symbol
    guard_margin::Float64
    instance_seed::UInt64
    start_seed::UInt64
    start_count::Int
end

function StrictGuardBoundaryParams(;
    boundary_case::Symbol=:near_boundary,
    guard_margin::Real=1.0e-8,
    instance_seed::Integer=108,
    start_seed::Integer=1008,
    start_count::Integer=32,
)
    boundary_case in _STRICT_GUARD_CASES ||
        throw(ArgumentError("boundary_case must be one of $_STRICT_GUARD_CASES"))
    margin = Float64(guard_margin)
    isfinite(margin) || throw(ArgumentError("guard_margin must be finite"))
    if boundary_case === :well_separated
        0.25 <= margin <= 0.75 ||
            throw(ArgumentError("well-separated guard_margin must lie in [0.25, 0.75]"))
    elseif boundary_case === :near_boundary
        0 < margin <= 1.0e-6 ||
            throw(ArgumentError("near-boundary guard_margin must lie in (0, 1e-6]"))
    else
        iszero(margin) || throw(ArgumentError("on-boundary guard_margin must be exactly zero"))
    end
    start_count > 0 || throw(ArgumentError("start_count must be positive"))
    return StrictGuardBoundaryParams(
        boundary_case,
        margin,
        _validated_seed(instance_seed, "instance_seed"),
        _validated_seed(start_seed, "start_seed"),
        Int(start_count),
    )
end

function strict_guard_margin(problem::DirectAnalyticProblem, input::AbstractVector)
    problem.family_id == "STRICT-GUARD-BOUNDARY" ||
        throw(ArgumentError("problem does not declare the strict-guard family contract"))
    length(input) == problem.dimension || throw(DimensionMismatch("input has wrong length"))
    return input[1] - problem.metadata[:guard_boundary]
end

strict_guard_valid(problem::DirectAnalyticProblem, input::AbstractVector) =
    strict_guard_margin(problem, input) > 0

function _strict_guard_targets(candidate_targets, valid_candidates)
    targets = AbstractGoldTargetDescriptor[]
    target_index = 0
    for candidate in eachindex(candidate_targets)
        valid_candidates[candidate] || continue
        target_index += 1
        value = candidate_targets[candidate]
        push!(
            targets,
            ExactGoldTarget(
                string("target-", lpad(target_index, 3, '0')),
                value,
                string("strictly feasible polynomial root x_1 = ", value),
                [target_index],
            ),
        )
    end
    return targets
end


function generate(parameters::StrictGuardBoundaryParams)
    candidate_targets = [1.0, 2.0]
    boundary = 1.0 - parameters.guard_margin
    coupling = 0.5 + Float64(parameters.instance_seed % UInt64(17)) / 32
    candidate_configurations = [
        candidate_targets[1] candidate_targets[2]
        coupling * candidate_targets[1] coupling * candidate_targets[2]
    ]
    candidate_margins = candidate_targets .- boundary
    valid_candidates = candidate_margins .> 0
    any(valid_candidates) || error("strict-guard family must retain at least one valid root")
    configurations = candidate_configurations[:, valid_candidates]
    gold_target_values = candidate_targets[valid_candidates]
    gold_targets = _strict_guard_targets(candidate_targets, valid_candidates)

    lower = [0.0, -1.0]
    upper = [3.0, 3.0]
    starts = _uniform_starts(lower, upper, parameters.start_count, parameters.start_seed)

    function residual!(output, input)
        _check_output_lengths(output, input, 2, 2)
        output[1] = (input[1] - candidate_targets[1]) * (input[1] - candidate_targets[2])
        output[2] = input[2] - coupling * input[1]
        return output
    end

    function jacobian!(output, input)
        length(input) == 2 || throw(DimensionMismatch("input has wrong length"))
        _check_jacobian_size(output, 2, 2)
        output[1, 1] = 2 * input[1] - sum(candidate_targets)
        output[1, 2] = 0
        output[2, 1] = -coupling
        output[2, 2] = 1
        return output
    end

    target(input) = input[1]
    case_code = findfirst(==(parameters.boundary_case), _STRICT_GUARD_CASES)
    artifacts = MaterializedArtifact[
        _parameter_artifact(
            case_code,
            parameters.guard_margin,
            parameters.instance_seed,
            parameters.start_seed,
            parameters.start_count,
        ),
        MaterializedArtifact(:candidate_configurations, candidate_configurations),
        MaterializedArtifact(:candidate_guard_margins, reshape(candidate_margins, :, 1)),
        MaterializedArtifact(
            :candidate_strict_validity,
            reshape(Float64.(valid_candidates), :, 1),
        ),
        MaterializedArtifact(:expected_target_values, reshape(gold_target_values, :, 1)),
        MaterializedArtifact(:guard_contract, reshape([boundary, 1.0, coupling], :, 1)),
    ]
    metadata = Dict{Symbol,Any}(
        :boundary_case => parameters.boundary_case,
        :strict_guard => true,
        :guard_boundary => boundary,
        :guard_margins_at_candidates => copy(candidate_margins),
        :candidate_strict_validity => copy(valid_candidates),
        :excluded_boundary_targets => candidate_targets[.!valid_candidates],
        :expected_target_values => copy(gold_target_values),
        :declared_capabilities => (:C0, :C1),
        :generator_role => :strict_guard_boundary_control,
    )
    instance_id = string(
        "strict-guard-",
        parameters.boundary_case,
        "-margin",
        parameters.guard_margin,
        "-i",
        parameters.instance_seed,
        "-s",
        parameters.start_seed,
    )
    return DirectAnalyticProblem(
        instance_id,
        "STRICT-GUARD-BOUNDARY",
        (:S4,),
        parameters,
        2,
        2,
        residual!,
        jacobian!,
        target,
        lower,
        upper,
        [1.5, 2.0],
        [1.0, 1.0],
        configurations,
        gold_targets,
        starts,
        artifacts,
        metadata,
    )
end
