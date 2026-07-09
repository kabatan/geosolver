struct RedundantOverdeterminedParams
    dimension::Int
    redundancy::Int
    dependency_error::Float64
    dependency_seed::UInt64
    start_seed::UInt64
    start_count::Int
end

function RedundantOverdeterminedParams(;
    dimension::Integer=4,
    redundancy::Integer=2,
    dependency_error::Real=0.0,
    dependency_seed::Integer=104,
    start_seed::Integer=1004,
    start_count::Integer=32,
)
    d = _validated_dimension(dimension; minimum=2)
    1 <= redundancy <= 4 || throw(ArgumentError("redundancy must lie in 1:4"))
    error = Float64(dependency_error)
    isfinite(error) && error >= 0 ||
        throw(ArgumentError("dependency_error must be finite and nonnegative"))
    start_count > 0 || throw(ArgumentError("start_count must be positive"))
    return RedundantOverdeterminedParams(
        d,
        Int(redundancy),
        error,
        _validated_seed(dependency_seed, "dependency_seed"),
        _validated_seed(start_seed, "start_seed"),
        Int(start_count),
    )
end

function generate(parameters::RedundantOverdeterminedParams)
    d = parameters.dimension
    redundancy = parameters.redundancy
    base = _canonical_orthogonal(d, parameters.dependency_seed)
    rng = MersenneTwister(parameters.dependency_seed + UInt64(1))
    blocks = Matrix{Float64}[base]
    for _ in 1:redundancy
        perturbation = randn(rng, d, d) / sqrt(d)
        push!(blocks, base + parameters.dependency_error * perturbation)
    end
    operator = reduce(vcat, blocks)
    m = size(operator, 1)
    root = _rational_root(d)
    lower = fill(-2.0, d)
    upper = fill(2.0, d)
    row_scales = vec(sqrt.(sum(abs2, operator; dims=2)))
    starts = _uniform_starts(lower, upper, parameters.start_count, parameters.start_seed)

    function residual!(output, input)
        _check_output_lengths(output, input, m, d)
        mul!(output, operator, input - root)
        return output
    end

    function jacobian!(output, input)
        length(input) == d || throw(DimensionMismatch("input has wrong length"))
        _check_jacobian_size(output, m, d)
        copyto!(output, operator)
        return output
    end

    target(input) = input[1]
    artifacts = MaterializedArtifact[
        _parameter_artifact(
            d,
            redundancy,
            parameters.dependency_error,
            parameters.dependency_seed,
            parameters.start_seed,
            parameters.start_count,
        ),
        MaterializedArtifact(:base_orthogonal, base),
        MaterializedArtifact(:overdetermined_operator, operator),
    ]
    metadata = Dict{Symbol,Any}(
        :redundancy => redundancy,
        :dependency_error => parameters.dependency_error,
        :observed_jacobian_condition => cond(operator),
        :root_separation => Inf,
        :generator_role => :analytic_overdetermined_control,
    )
    instance_id = string(
        "redundant-d",
        d,
        "-r",
        redundancy,
        "-error",
        parameters.dependency_error,
        "-i",
        parameters.dependency_seed,
        "-s",
        parameters.start_seed,
    )
    return DirectAnalyticProblem(
        instance_id,
        "REDUNDANT-OVERDETERMINED",
        (:S7,),
        parameters,
        d,
        m,
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
