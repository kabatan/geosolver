struct TangentCircleLineParams
    radius::Float64
    height_radius_ratio::Float64
    instance_seed::UInt64
    start_seed::UInt64
    start_count::Int
end

function TangentCircleLineParams(;
    radius::Real=1.0,
    height_radius_ratio::Real=0.999,
    instance_seed::Integer=105,
    start_seed::Integer=1005,
    start_count::Integer=32,
)
    r = Float64(radius)
    ratio = Float64(height_radius_ratio)
    isfinite(r) && r > 0 || throw(ArgumentError("radius must be finite and positive"))
    isfinite(ratio) && 0 <= ratio < 1 ||
        throw(ArgumentError("height_radius_ratio must lie in [0, 1)"))
    start_count > 0 || throw(ArgumentError("start_count must be positive"))
    return TangentCircleLineParams(
        r,
        ratio,
        _validated_seed(instance_seed, "instance_seed"),
        _validated_seed(start_seed, "start_seed"),
        Int(start_count),
    )
end

function generate(parameters::TangentCircleLineParams)
    radius = parameters.radius
    height = radius * parameters.height_radius_ratio
    horizontal = sqrt((radius - height) * (radius + height))
    roots = [-horizontal horizontal; height height]
    lower = fill(-1.5 * radius, 2)
    upper = fill(1.5 * radius, 2)
    starts = _uniform_starts(lower, upper, parameters.start_count, parameters.start_seed)

    function residual!(output, input)
        _check_output_lengths(output, input, 2, 2)
        output[1] = input[1]^2 + input[2]^2 - radius^2
        output[2] = input[2] - height
        return output
    end

    function jacobian!(output, input)
        length(input) == 2 || throw(DimensionMismatch("input has wrong length"))
        _check_jacobian_size(output, 2, 2)
        output[1, 1] = 2 * input[1]
        output[1, 2] = 2 * input[2]
        output[2, 1] = 0
        output[2, 2] = 1
        return output
    end

    target(input) = input[1]
    gold_targets = AbstractGoldTargetDescriptor[
        ExactGoldTarget(
            "target-001",
            -horizontal,
            "-radius * sqrt(1 - height_radius_ratio^2)",
            [1],
        ),
        ExactGoldTarget(
            "target-002",
            horizontal,
            "radius * sqrt(1 - height_radius_ratio^2)",
            [2],
        ),
    ]
    conditions = Float64[]
    for root in eachcol(roots)
        jacobian = zeros(2, 2)
        jacobian!(jacobian, root)
        push!(conditions, cond(jacobian))
    end
    artifacts = MaterializedArtifact[
        _parameter_artifact(
            radius,
            parameters.height_radius_ratio,
            parameters.instance_seed,
            parameters.start_seed,
            parameters.start_count,
        ),
        MaterializedArtifact(:root_conditions, reshape(conditions, :, 1)),
    ]
    metadata = Dict{Symbol,Any}(
        :height => height,
        :height_radius_ratio => parameters.height_radius_ratio,
        :root_separation => 2 * horizontal,
        :observed_root_conditions => conditions,
        :generator_role => :analytic_tangency_control,
    )
    strata = parameters.height_radius_ratio >= 0.9 ? (:S2, :S3) : (:S1, :S3)
    instance_id = string(
        "tangent-circle-r",
        radius,
        "-ratio",
        parameters.height_radius_ratio,
        "-i",
        parameters.instance_seed,
        "-s",
        parameters.start_seed,
    )
    return DirectAnalyticProblem(
        instance_id,
        "TANGENT-CIRCLE-LINE",
        strata,
        parameters,
        2,
        2,
        residual!,
        jacobian!,
        target,
        lower,
        upper,
        fill(1.5 * radius, 2),
        [radius^2, radius],
        roots,
        gold_targets,
        starts,
        artifacts,
        metadata,
    )
end
