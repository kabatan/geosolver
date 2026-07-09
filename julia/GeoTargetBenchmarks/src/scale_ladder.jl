struct ScaleLadderParams
    dimension::Int
    residual_scale_spread::Float64
    instance_seed::UInt64
    start_seed::UInt64
    start_count::Int
end

function ScaleLadderParams(;
    dimension::Integer=4,
    residual_scale_spread::Real=1.0e6,
    instance_seed::Integer=101,
    start_seed::Integer=1001,
    start_count::Integer=32,
)
    d = _validated_dimension(dimension; minimum=2)
    spread = Float64(residual_scale_spread)
    isfinite(spread) && spread >= 1 ||
        throw(ArgumentError("residual_scale_spread must be finite and at least one"))
    start_count > 0 || throw(ArgumentError("start_count must be positive"))
    return ScaleLadderParams(
        d,
        spread,
        _validated_seed(instance_seed, "instance_seed"),
        _validated_seed(start_seed, "start_seed"),
        Int(start_count),
    )
end

function generate(parameters::ScaleLadderParams)
    d = parameters.dimension
    root = _rational_root(d)
    row_scales = _geometric_ladder(1, parameters.residual_scale_spread, d)
    lower = fill(-2.0, d)
    upper = fill(2.0, d)
    starts = _uniform_starts(lower, upper, parameters.start_count, parameters.start_seed)

    function residual!(output, input)
        _check_output_lengths(output, input, d, d)
        @inbounds for index in 1:d
            output[index] = row_scales[index] * (input[index] - root[index])
        end
        return output
    end

    function jacobian!(output, input)
        length(input) == d || throw(DimensionMismatch("input has wrong length"))
        _check_jacobian_size(output, d, d)
        fill!(output, zero(eltype(output)))
        @inbounds for index in 1:d
            output[index, index] = row_scales[index]
        end
        return output
    end

    target(input) = input[1]
    identity = "(1 - dimension) / (2 * (dimension + 1))"
    artifacts = MaterializedArtifact[
        _parameter_artifact(
            d,
            parameters.residual_scale_spread,
            parameters.instance_seed,
            parameters.start_seed,
            parameters.start_count,
        ),
        MaterializedArtifact(:row_scales, reshape(row_scales, :, 1)),
    ]
    metadata = Dict{Symbol,Any}(
        :requested_scale_spread => parameters.residual_scale_spread,
        :observed_jacobian_condition => parameters.residual_scale_spread,
        :root_separation => Inf,
        :generator_role => :analytic_scaling_control,
    )
    instance_id = string(
        "scale-ladder-d",
        d,
        "-spread",
        parameters.residual_scale_spread,
        "-i",
        parameters.instance_seed,
        "-s",
        parameters.start_seed,
    )
    return DirectAnalyticProblem(
        instance_id,
        "SCALE-LADDER",
        (:S1, :S8),
        parameters,
        d,
        d,
        residual!,
        jacobian!,
        target,
        lower,
        upper,
        fill(2.0, d),
        row_scales,
        reshape(root, :, 1),
        _exact_single_target(root[1], identity),
        starts,
        artifacts,
        metadata,
    )
end
