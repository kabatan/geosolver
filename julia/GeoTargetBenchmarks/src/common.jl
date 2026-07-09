function _validated_seed(seed::Integer, label::AbstractString)
    seed >= 0 || throw(ArgumentError("$label must be nonnegative"))
    return UInt64(seed)
end

function _validated_dimension(dimension::Integer; minimum::Int=1, maximum::Int=16)
    minimum <= dimension <= maximum ||
        throw(ArgumentError("dimension must lie in $minimum:$maximum"))
    return Int(dimension)
end

function _uniform_starts(
    lower::AbstractVector{<:Real},
    upper::AbstractVector{<:Real},
    count::Integer,
    seed::UInt64,
)
    count > 0 || throw(ArgumentError("start_count must be positive"))
    length(lower) == length(upper) || throw(DimensionMismatch("bounds differ in length"))
    rng = MersenneTwister(seed)
    unit = rand(rng, length(lower), Int(count))
    return Float64.(lower) .+ (Float64.(upper) .- Float64.(lower)) .* unit
end

function _rational_root(dimension::Int)
    return Float64[(2 * index - dimension - 1) // (2 * (dimension + 1)) for index in 1:dimension]
end

function _geometric_ladder(first::Real, last::Real, count::Integer)
    first > 0 && last > 0 || throw(ArgumentError("ladder endpoints must be positive"))
    count > 0 || throw(ArgumentError("ladder count must be positive"))
    count == 1 && return [Float64(first)]
    return exp.(range(log(Float64(first)), log(Float64(last)); length=Int(count)))
end

function _canonical_orthogonal(dimension::Int, seed::UInt64)
    rng = MersenneTwister(seed)
    factorization = qr(randn(rng, dimension, dimension))
    orthogonal = Matrix(factorization.Q)
    triangular = Matrix(factorization.R)
    for column in 1:dimension
        if signbit(triangular[column, column])
            orthogonal[:, column] .*= -1
        end
    end
    return orthogonal
end

function _check_output_lengths(
    output::AbstractVector,
    input::AbstractVector,
    residual_dimension::Int,
    dimension::Int,
)
    length(output) == residual_dimension ||
        throw(DimensionMismatch("residual output has wrong length"))
    length(input) == dimension || throw(DimensionMismatch("input has wrong length"))
    return nothing
end

function _check_jacobian_size(jacobian::AbstractMatrix, rows::Int, columns::Int)
    size(jacobian) == (rows, columns) ||
        throw(DimensionMismatch("Jacobian output has wrong dimensions"))
    return nothing
end

function _exact_single_target(value::Real, identity::AbstractString)
    return AbstractGoldTargetDescriptor[
        ExactGoldTarget("target-001", value, identity, [1]),
    ]
end

function _parameter_artifact(values::Real...)
    return MaterializedArtifact(:parameters, reshape(Float64[values...], 1, :))
end
