const _MULTIROOT_TARGET_MAPS = (:z1, :z1_squared, :close_affine)

struct MultiRootWarpedParams
    dimension::Int
    root_count::Int
    minimum_separation::Float64
    warp::Float64
    condition::Float64
    target_map::Symbol
    target_affine_scale::Float64
    coefficient_seed::UInt64
    start_seed::UInt64
    start_count::Int
end

function MultiRootWarpedParams(;
    dimension::Integer=4,
    root_count::Integer=4,
    minimum_separation::Real=1.0e-3,
    warp::Real=0.5,
    condition::Real=1.0e4,
    target_map::Symbol=:z1,
    target_affine_scale::Real=1.0e-6,
    coefficient_seed::Integer=106,
    start_seed::Integer=1006,
    start_count::Integer=32,
)
    d = _validated_dimension(dimension; minimum=2)
    2 <= root_count <= 12 || throw(ArgumentError("root_count must lie in 2:12"))
    separation = Float64(minimum_separation)
    isfinite(separation) && separation > 0 ||
        throw(ArgumentError("minimum_separation must be finite and positive"))
    (root_count - 1) * separation <= 1.2 ||
        throw(ArgumentError("requested roots do not fit the analytic latent interval"))
    warp_value = Float64(warp)
    isfinite(warp_value) && 0 <= warp_value < 1 ||
        throw(ArgumentError("warp must lie in [0, 1)"))
    condition_value = Float64(condition)
    isfinite(condition_value) && condition_value >= 1 ||
        throw(ArgumentError("condition must be finite and at least one"))
    target_map in _MULTIROOT_TARGET_MAPS ||
        throw(ArgumentError("target_map must be one of $_MULTIROOT_TARGET_MAPS"))
    affine_scale = Float64(target_affine_scale)
    isfinite(affine_scale) && affine_scale > 0 ||
        throw(ArgumentError("target_affine_scale must be finite and positive"))
    start_count > 0 || throw(ArgumentError("start_count must be positive"))
    return MultiRootWarpedParams(
        d,
        Int(root_count),
        separation,
        warp_value,
        condition_value,
        target_map,
        affine_scale,
        _validated_seed(coefficient_seed, "coefficient_seed"),
        _validated_seed(start_seed, "start_seed"),
        Int(start_count),
    )
end

function _polynomial_derivative(value, roots)
    derivative = zero(value)
    for omitted in eachindex(roots)
        term = one(value)
        for index in eachindex(roots)
            index == omitted && continue
            term *= value - roots[index]
        end
        derivative += term
    end
    return derivative
end

function _multiroot_target_descriptors(parameters, target_values)
    grouped = Vector{Tuple{Float64,Vector{Int}}}()
    for (index, value) in enumerate(target_values)
        found = findfirst(entry -> isequal(entry[1], value), grouped)
        if found === nothing
            push!(grouped, (value, [index]))
        else
            push!(grouped[found][2], index)
        end
    end
    sort!(grouped; by=first)

    targets = AbstractGoldTargetDescriptor[]
    for (index, (value, configurations)) in enumerate(grouped)
        target_id = string("target-", lpad(index, 3, '0'))
        if parameters.target_map === :close_affine
            push!(
                targets,
                ValidatedGoldTarget(
                    target_id,
                    prevfloat(value),
                    nextfloat(value),
                    "outward-rounded analytic close-affine target",
                    configurations,
                ),
            )
        else
            identity = parameters.target_map === :z1 ?
                "latent root alpha[$(configurations[1])]" :
                "latent root alpha^2 for symmetric configuration group"
            push!(targets, ExactGoldTarget(target_id, value, identity, configurations))
        end
    end
    return targets
end

function generate(parameters::MultiRootWarpedParams)
    d = parameters.dimension
    root_count = parameters.root_count
    separation = parameters.minimum_separation
    latent_roots = Float64[
        (index - (root_count + 1) / 2) * separation for index in 1:root_count
    ]
    rng = MersenneTwister(parameters.coefficient_seed)
    coefficients = 0.5 .+ rand(rng, d - 1)
    row_scales = vcat(1.0, _geometric_ladder(1, parameters.condition, d - 1))

    configurations = zeros(d, root_count)
    for (column, alpha) in enumerate(latent_roots)
        configurations[1, column] = alpha
        for index in 2:d
            coefficient = coefficients[index - 1]
            dependent = coefficient * (alpha^2 + 0.1 * index * alpha)
            configurations[index, column] =
                dependent - parameters.warp * coefficient * sin(alpha)
        end
    end
    lower = fill(-2.0, d)
    upper = fill(2.0, d)
    starts = _uniform_starts(lower, upper, parameters.start_count, parameters.start_seed)

    function residual!(output, input)
        _check_output_lengths(output, input, d, d)
        output[1] = prod(input[1] - root for root in latent_roots)
        @inbounds for index in 2:d
            coefficient = coefficients[index - 1]
            dependent = coefficient * (input[1]^2 + 0.1 * index * input[1])
            latent_coordinate =
                input[index] + parameters.warp * coefficient * sin(input[1])
            output[index] = row_scales[index] * (latent_coordinate - dependent)
        end
        return output
    end

    function jacobian!(output, input)
        length(input) == d || throw(DimensionMismatch("input has wrong length"))
        _check_jacobian_size(output, d, d)
        fill!(output, zero(eltype(output)))
        output[1, 1] = _polynomial_derivative(input[1], latent_roots)
        @inbounds for index in 2:d
            coefficient = coefficients[index - 1]
            output[index, 1] = row_scales[index] * coefficient *
                (parameters.warp * cos(input[1]) - 2 * input[1] - 0.1 * index)
            output[index, index] = row_scales[index]
        end
        return output
    end

    function target(input)
        if parameters.target_map === :z1
            return input[1]
        elseif parameters.target_map === :z1_squared
            return input[1]^2
        else
            return 1 + parameters.target_affine_scale * input[1]
        end
    end

    target_values = Float64[target(root) for root in eachcol(configurations)]
    targets = _multiroot_target_descriptors(parameters, target_values)
    conditions = Float64[]
    for root in eachcol(configurations)
        jacobian = zeros(d, d)
        jacobian!(jacobian, root)
        push!(conditions, cond(jacobian))
    end
    artifacts = MaterializedArtifact[
        _parameter_artifact(
            d,
            root_count,
            separation,
            parameters.warp,
            parameters.condition,
            parameters.target_affine_scale,
            parameters.coefficient_seed,
            parameters.start_seed,
            parameters.start_count,
        ),
        MaterializedArtifact(:latent_roots, reshape(latent_roots, :, 1)),
        MaterializedArtifact(:warp_coefficients, reshape(coefficients, :, 1)),
        MaterializedArtifact(:row_scales, reshape(row_scales, :, 1)),
        MaterializedArtifact(:root_conditions, reshape(conditions, :, 1)),
    ]
    metadata = Dict{Symbol,Any}(
        :root_count => root_count,
        :requested_minimum_separation => separation,
        :observed_minimum_latent_separation => minimum(diff(sort(latent_roots))),
        :requested_condition => parameters.condition,
        :observed_root_conditions => conditions,
        :warp => parameters.warp,
        :target_map => parameters.target_map,
        :generator_role => :analytic_multibasin_control,
    )
    strata = parameters.target_map === :z1_squared ? (:S2, :S5) : (:S2,)
    instance_id = string(
        "multiroot-d",
        d,
        "-n",
        root_count,
        "-sep",
        separation,
        "-condition",
        parameters.condition,
        "-warp",
        parameters.warp,
        "-target",
        parameters.target_map,
        "-c",
        parameters.coefficient_seed,
        "-s",
        parameters.start_seed,
    )
    return DirectAnalyticProblem(
        instance_id,
        "MULTIROOT-WARPED",
        strata,
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
        configurations,
        targets,
        starts,
        artifacts,
        metadata,
    )
end
