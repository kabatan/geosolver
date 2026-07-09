struct NearRankDeficientParams
    dimension::Int
    singular_value_ratio::Float64
    orientation_seed::UInt64
    start_seed::UInt64
    start_count::Int
end

function NearRankDeficientParams(;
    dimension::Integer=4,
    singular_value_ratio::Real=1.0e-8,
    orientation_seed::Integer=103,
    start_seed::Integer=1003,
    start_count::Integer=32,
)
    d = _validated_dimension(dimension; minimum=2)
    ratio = Float64(singular_value_ratio)
    isfinite(ratio) && 0 < ratio <= 1 ||
        throw(ArgumentError("singular_value_ratio must lie in (0, 1]"))
    start_count > 0 || throw(ArgumentError("start_count must be positive"))
    return NearRankDeficientParams(
        d,
        ratio,
        _validated_seed(orientation_seed, "orientation_seed"),
        _validated_seed(start_seed, "start_seed"),
        Int(start_count),
    )
end

function generate(parameters::NearRankDeficientParams)
    d = parameters.dimension
    singular_values = _geometric_ladder(1, parameters.singular_value_ratio, d)
    left = _canonical_orthogonal(d, parameters.orientation_seed)
    right = _canonical_orthogonal(d, parameters.orientation_seed + UInt64(1))
    operator = left * Diagonal(singular_values) * transpose(right)
    root = _rational_root(d)
    lower = fill(-2.0, d)
    upper = fill(2.0, d)
    row_scales = vec(sqrt.(sum(abs2, operator; dims=2)))
    starts = _uniform_starts(lower, upper, parameters.start_count, parameters.start_seed)

    function residual!(output, input)
        _check_output_lengths(output, input, d, d)
        mul!(output, operator, input - root)
        return output
    end

    function jacobian!(output, input)
        length(input) == d || throw(DimensionMismatch("input has wrong length"))
        _check_jacobian_size(output, d, d)
        copyto!(output, operator)
        return output
    end

    target(input) = input[1]
    artifacts = MaterializedArtifact[
        _parameter_artifact(
            d,
            parameters.singular_value_ratio,
            parameters.orientation_seed,
            parameters.start_seed,
            parameters.start_count,
        ),
        MaterializedArtifact(:left_orthogonal, left),
        MaterializedArtifact(:right_orthogonal, right),
        MaterializedArtifact(:singular_values, reshape(singular_values, :, 1)),
        MaterializedArtifact(:linear_operator, operator),
    ]
    metadata = Dict{Symbol,Any}(
        :requested_singular_value_ratio => parameters.singular_value_ratio,
        :requested_condition => inv(parameters.singular_value_ratio),
        :observed_jacobian_condition => cond(operator),
        :root_separation => Inf,
        :generator_role => :analytic_conditioning_control,
    )
    instance_id = string(
        "near-rank-d",
        d,
        "-ratio",
        parameters.singular_value_ratio,
        "-o",
        parameters.orientation_seed,
        "-s",
        parameters.start_seed,
    )
    return DirectAnalyticProblem(
        instance_id,
        "NEAR-RANK-DEFICIENT",
        (:S3,),
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
        _exact_single_target(root[1], "(1 - dimension) / (2 * (dimension + 1))"),
        starts,
        artifacts,
        metadata,
    )
end
