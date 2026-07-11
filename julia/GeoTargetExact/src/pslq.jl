# Ferguson, Bailey and Arno, "Analysis of PSLQ, an Integer Relation Finding
# Algorithm", Math. Comp. 68 (1999), doi:10.1090/S0025-5718-99-00995-3.
@enum PSLQFailure::UInt8 begin
    PSLQ_NONE = 0
    PSLQ_INVALID_INPUT = 1
    PSLQ_INSUFFICIENT_PRECISION = 2
    PSLQ_COEFFICIENT_LIMIT = 3
    PSLQ_MAX_ITERATIONS = 4
    PSLQ_NUMERICAL_BREAKDOWN = 5
end

"""Typed result of the owned Ferguson-Bailey-Arno PSLQ implementation."""
struct PSLQResult
    relation::Union{Nothing,Tuple}
    failure::PSLQFailure
    iterations::Int
    precision_bits::Int
    height_bits::Int
    residual::Union{Nothing,BigFloat}
    detail::String

    function PSLQResult(
        relation,
        failure::PSLQFailure,
        iterations::Integer,
        precision_bits::Integer,
        height_bits::Integer,
        residual,
        detail::AbstractString,
    )
        success = relation !== nothing
        success == (failure == PSLQ_NONE) ||
            throw(ArgumentError("PSLQ relation and failure status disagree"))
        success == isempty(detail) ||
            throw(ArgumentError("only failed PSLQ results carry detail"))
        return new(
            relation === nothing ? nothing : Tuple(BigInt(value) for value in relation),
            failure,
            Int(iterations),
            Int(precision_bits),
            Int(height_bits),
            residual === nothing ? nothing : BigFloat(residual),
            String(detail),
        )
    end
end

_pslq_success(relation, iterations, precision_bits, height_bits, residual) =
    PSLQResult(relation, PSLQ_NONE, iterations, precision_bits, height_bits, residual, "")

_pslq_failure(failure, iterations, precision_bits, height_bits, detail; residual=nothing) =
    PSLQResult(nothing, failure, iterations, precision_bits, height_bits, residual, detail)

_pslq_coefficient_bits(value::BigInt) = iszero(value) ? 0 : ndigits(abs(value); base=2)

function _pslq_contract_int(value::Integer)
    value isa Bool && return nothing
    typemin(Int) <= value <= typemax(Int) || return nothing
    return Int(value)
end

function _pslq_normalize(relation)
    values = BigInt[BigInt(value) for value in relation]
    while !isempty(values) && iszero(last(values))
        pop!(values)
    end
    # The public PSLQ surface is specifically [1,x,...,x^d]. For nonzero x
    # (zero is handled before iteration), leading coefficient zeros are a
    # removable factor x^k and should not inflate the reported polynomial.
    while !isempty(values) && iszero(first(values))
        popfirst!(values)
    end
    isempty(values) && return nothing
    divisor = foldl(gcd, abs.(values))
    iszero(divisor) && return nothing
    values = div.(values, divisor)
    last(values) < 0 && (values = -values)
    return Tuple(values)
end

function _pslq_residual(relation, values, precision_bits, height_bits)
    return setprecision(BigFloat, precision_bits) do
        residual = zero(BigFloat)
        scale = zero(BigFloat)
        for (coefficient, value) in zip(relation, values)
            term = BigFloat(coefficient) * value
            residual += term
            scale += abs(term)
        end
        # Core's provider guarantees adaptive root/target gates with a 96-bit
        # accuracy reserve, not a correctly rounded algebraic value at every
        # requested bit. Keep the recognition residual inside the 128-bit
        # working-precision safety reserve required by the degree/height rule.
        guard_bits = max(128, height_bits + ceil(Int, log2(length(values))) + 32)
        reliable_bits = max(32, precision_bits - guard_bits)
        tolerance = ldexp(max(one(BigFloat), scale), -reliable_bits)
        residual, tolerance
    end
end

function _pslq_candidate(B, column, values, precision_bits, height_bits)
    raw = Tuple(B[row, column] for row in axes(B, 1))
    relation = _pslq_normalize(raw)
    relation === nothing && return nothing, nothing, false
    padded = ntuple(index -> index <= length(relation) ? relation[index] : BigInt(0), length(values))
    residual, tolerance = _pslq_residual(padded, values, precision_bits, height_bits)
    abs(residual) <= tolerance || return nothing, residual, false
    within_height = maximum(_pslq_coefficient_bits(value) for value in relation) <= height_bits
    return relation, residual, within_height
end

function _pslq_hermite_reduce!(H, y, B)
    n = length(y)
    for row in 2:n
        for column in min(row - 1, n - 1):-1:1
            diagonal = H[column, column]
            iszero(diagonal) && return false
            multiplier = round(BigInt, H[row, column] / diagonal)
            iszero(multiplier) && continue
            floating_multiplier = BigFloat(multiplier)
            y[column] += floating_multiplier * y[row]
            for index in 1:column
                H[row, index] -= floating_multiplier * H[column, index]
            end
            for index in 1:n
                B[index, column] += multiplier * B[index, row]
            end
        end
    end
    return true
end

function _pslq_initial_state(values, precision_bits)
    n = length(values)
    y = BigFloat[BigFloat(value) for value in values]
    partial_norms = zeros(BigFloat, n)
    partial_norms[n] = abs(y[n])
    for index in (n - 1):-1:1
        partial_norms[index] = sqrt(partial_norms[index + 1]^2 + y[index]^2)
    end
    iszero(partial_norms[1]) && return nothing
    normalization = partial_norms[1]
    y ./= normalization
    partial_norms ./= normalization
    any(iszero, partial_norms) && return nothing

    H = zeros(BigFloat, n, n - 1)
    for row in 1:n
        for column in 1:(n - 1)
            if row < column
                H[row, column] = zero(BigFloat)
            elseif row == column
                H[row, column] = partial_norms[column + 1] / partial_norms[column]
            else
                H[row, column] = -y[row] * y[column] /
                                 (partial_norms[column] * partial_norms[column + 1])
            end
        end
    end
    B = Matrix{BigInt}(undef, n, n)
    for row in 1:n, column in 1:n
        B[row, column] = row == column ? BigInt(1) : BigInt(0)
    end
    _pslq_hermite_reduce!(H, y, B) || return nothing
    return y, H, B
end

function _pslq_best_candidate(B, values, precision_bits, height_bits)
    ordered_columns = sort(collect(axes(B, 2)); by=column -> begin
        relation = Tuple(B[row, column] for row in axes(B, 1))
        residual, _ = _pslq_residual(relation, values, precision_bits, height_bits)
        abs(residual)
    end)
    overheight_relation = nothing
    overheight_residual = nothing
    for column in ordered_columns
        relation, residual, within_height =
            _pslq_candidate(B, column, values, precision_bits, height_bits)
        relation === nothing && continue
        within_height && return relation, residual, true
        if overheight_relation === nothing
            overheight_relation = relation
            overheight_residual = residual
        end
    end
    return overheight_relation, overheight_residual, false
end

function _pslq_iterate!(y, H, B)
    n = length(y)
    gamma = BigFloat(2) / sqrt(BigFloat(3))
    best_index = 1
    best_score = gamma * abs(H[1, 1])
    gamma_power = gamma
    for index in 2:(n - 1)
        gamma_power *= gamma
        score = gamma_power * abs(H[index, index])
        if score > best_score
            best_score = score
            best_index = index
        end
    end
    exchange = best_index
    y[exchange], y[exchange + 1] = y[exchange + 1], y[exchange]
    for column in axes(H, 2)
        H[exchange, column], H[exchange + 1, column] =
            H[exchange + 1, column], H[exchange, column]
    end
    for row in axes(B, 1)
        B[row, exchange], B[row, exchange + 1] =
            B[row, exchange + 1], B[row, exchange]
    end

    if exchange <= n - 2
        first = H[exchange, exchange]
        second = H[exchange, exchange + 1]
        norm = sqrt(first^2 + second^2)
        iszero(norm) && return false
        cosine = first / norm
        sine = second / norm
        for row in exchange:n
            left = H[row, exchange]
            right = H[row, exchange + 1]
            H[row, exchange] = cosine * left + sine * right
            H[row, exchange + 1] = -sine * left + cosine * right
        end
    end
    return _pslq_hermite_reduce!(H, y, B)
end

function _pslq_values(value::BigFloat, degree_limit::Int, precision_bits::Int)
    return setprecision(BigFloat, precision_bits) do
        values = Vector{BigFloat}(undef, degree_limit + 1)
        values[1] = one(BigFloat)
        for index in 2:length(values)
            values[index] = values[index - 1] * value
        end
        values
    end
end

"""
Run owned BigFloat/BigInt Ferguson-Bailey-Arno PSLQ on `[1,x,...,x^d]`.

The result is always typed. A relation is returned only when its primitive
coefficients fit the declared height and its residual passes a precision-aware
guard. Recognition still requires a second, higher-precision run and exact
QQBar reconstruction.
"""
function pslq_relation(
    value::BigFloat,
    degree_limit::Integer,
    height_bits::Integer;
    precision_bits::Integer=precision(value),
    max_iterations::Integer=10_000,
    checkpoint=() -> nothing,
)
    checkpoint()
    degree = _pslq_contract_int(degree_limit)
    height = _pslq_contract_int(height_bits)
    bits = _pslq_contract_int(precision_bits)
    iterations_limit = _pslq_contract_int(max_iterations)
    if degree === nothing || height === nothing || bits === nothing ||
       iterations_limit === nothing
        return _pslq_failure(
            PSLQ_INVALID_INPUT,
            0,
            something(bits, 0),
            something(height, 0),
            "degree, height, precision, and iterations must be non-Bool values fitting Int",
        )
    end
    if degree < 1 || height < 1 || bits < 32 || iterations_limit < 1 || !isfinite(value)
        return _pslq_failure(
            PSLQ_INVALID_INPUT,
            0,
            bits,
            height,
            "degree, height, precision, iterations, and input must define a finite positive contract",
        )
    end
    minimum_precision = BigInt(2) * (BigInt(degree) + 1) * BigInt(height) + 128
    if BigInt(bits) < minimum_precision || precision(value) < bits
        return _pslq_failure(
            PSLQ_INSUFFICIENT_PRECISION,
            0,
            bits,
            height,
            "PSLQ requires at least $minimum_precision working bits and a value computed at that precision",
        )
    end
    if iszero(value)
        relation = ntuple(index -> index == 2 ? BigInt(1) : BigInt(0), degree + 1)
        return _pslq_success(relation, 0, bits, height, zero(BigFloat))
    end

    return setprecision(BigFloat, bits) do
        checkpoint()
        values = _pslq_values(value, degree, bits)
        state = _pslq_initial_state(values, bits)
        state === nothing && return _pslq_failure(
            PSLQ_NUMERICAL_BREAKDOWN,
            0,
            bits,
            height,
            "PSLQ hyperplane initialization was singular",
        )
        y, H, B = state
        relation, residual, within_height = _pslq_best_candidate(B, values, bits, height)
        relation !== nothing && within_height &&
            return _pslq_success(relation, 0, bits, height, residual)
        first_overheight_iteration = relation === nothing ? nothing : 0
        last_overheight_residual = relation === nothing ? nothing : residual
        overheight_grace = max(8, 4 * length(values))

        precision_floor = ldexp(one(BigFloat), -max(32, bits - height - 32))
        for iteration in 1:iterations_limit
            checkpoint()
            _pslq_iterate!(y, H, B) || return _pslq_failure(
                PSLQ_NUMERICAL_BREAKDOWN,
                iteration,
                bits,
                height,
                "PSLQ encountered a zero reduction or rotation pivot",
            )
            relation, residual, within_height = _pslq_best_candidate(B, values, bits, height)
            if relation !== nothing
                within_height &&
                    return _pslq_success(relation, iteration, bits, height, residual)
                first_overheight_iteration === nothing &&
                    (first_overheight_iteration = iteration)
                last_overheight_residual = residual
                iteration - first_overheight_iteration >= overheight_grace &&
                    return _pslq_failure(
                        PSLQ_COEFFICIENT_LIMIT,
                        iteration,
                        bits,
                        height,
                        "only verified relations above the coefficient-height limit persisted";
                        residual=last_overheight_residual,
                    )
            end
            if minimum(abs, y) <= precision_floor
                if first_overheight_iteration !== nothing
                    return _pslq_failure(
                        PSLQ_COEFFICIENT_LIMIT,
                        iteration,
                        bits,
                        height,
                        "PSLQ found only verified relations above the coefficient-height limit";
                        residual=last_overheight_residual,
                    )
                end
                return _pslq_failure(
                    PSLQ_INSUFFICIENT_PRECISION,
                    iteration,
                    bits,
                    height,
                    "PSLQ exhausted reliable digits before finding an admissible relation",
                )
            end
        end
        checkpoint()
        first_overheight_iteration !== nothing && return _pslq_failure(
            PSLQ_COEFFICIENT_LIMIT,
            iterations_limit,
            bits,
            height,
            "PSLQ found only verified relations above the coefficient-height limit";
            residual=last_overheight_residual,
        )
        return _pslq_failure(
            PSLQ_MAX_ITERATIONS,
            iterations_limit,
            bits,
            height,
            "PSLQ reached max_iterations without an admissible relation",
        )
    end
end
