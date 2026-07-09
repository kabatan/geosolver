struct CurvedChainParams
    dimension::Int
    curvature::Float64
    instance_seed::UInt64
    start_seed::UInt64
    start_count::Int
end

function CurvedChainParams(;
    dimension::Integer=4,
    curvature::Real=100.0,
    instance_seed::Integer=102,
    start_seed::Integer=1002,
    start_count::Integer=32,
)
    d = _validated_dimension(dimension; minimum=2)
    curve = Float64(curvature)
    isfinite(curve) && curve >= 1 ||
        throw(ArgumentError("curvature must be finite and at least one"))
    start_count > 0 || throw(ArgumentError("start_count must be positive"))
    return CurvedChainParams(
        d,
        curve,
        _validated_seed(instance_seed, "instance_seed"),
        _validated_seed(start_seed, "start_seed"),
        Int(start_count),
    )
end

function generate(parameters::CurvedChainParams)
    d = parameters.dimension
    curvature = parameters.curvature
    root = ones(d)
    lower = fill(-2.0, d)
    upper = fill(2.0, d)
    row_scales = vcat(1.0, fill(curvature, d - 1))
    starts = _uniform_starts(lower, upper, parameters.start_count, parameters.start_seed)

    function residual!(output, input)
        _check_output_lengths(output, input, d, d)
        output[1] = input[1] - 1
        @inbounds for index in 2:d
            output[index] = curvature * (input[index] - input[index - 1]^2)
        end
        return output
    end

    function jacobian!(output, input)
        length(input) == d || throw(DimensionMismatch("input has wrong length"))
        _check_jacobian_size(output, d, d)
        fill!(output, zero(eltype(output)))
        output[1, 1] = 1
        @inbounds for index in 2:d
            output[index, index - 1] = -2 * curvature * input[index - 1]
            output[index, index] = curvature
        end
        return output
    end

    target(input) = input[end]
    root_jacobian = zeros(d, d)
    jacobian!(root_jacobian, root)
    artifacts = MaterializedArtifact[
        _parameter_artifact(
            d,
            curvature,
            parameters.instance_seed,
            parameters.start_seed,
            parameters.start_count,
        ),
        MaterializedArtifact(:root_jacobian, root_jacobian),
    ]
    metadata = Dict{Symbol,Any}(
        :requested_curvature => curvature,
        :observed_jacobian_condition => cond(root_jacobian),
        :root_separation => Inf,
        :generator_role => :analytic_curved_valley_control,
    )
    instance_id = string(
        "curved-chain-d",
        d,
        "-curve",
        curvature,
        "-i",
        parameters.instance_seed,
        "-s",
        parameters.start_seed,
    )
    return DirectAnalyticProblem(
        instance_id,
        "CURVED-CHAIN",
        (:S1, :S2),
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
        _exact_single_target(1.0, "target = x_dimension = 1"),
        starts,
        artifacts,
        metadata,
    )
end
