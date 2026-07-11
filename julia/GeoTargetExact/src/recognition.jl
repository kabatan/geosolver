"""Canonical exact description of one real algebraic number."""
struct AlgebraicDescriptor
    coefficients::Tuple
    lower::Rational{BigInt}
    upper::Rational{BigInt}
    root_index::Int

    function AlgebraicDescriptor(coefficients, lower::Rational, upper::Rational, root_index::Integer)
        frozen = Tuple(BigInt(coefficient) for coefficient in coefficients)
        length(frozen) >= 2 || throw(ArgumentError("an algebraic descriptor needs positive degree"))
        lower_exact = Rational{BigInt}(lower)
        upper_exact = Rational{BigInt}(upper)
        lower_exact < upper_exact || throw(ArgumentError("an isolating interval needs lower < upper"))
        root_index isa Bool && throw(ArgumentError("root_index cannot be Bool"))
        root_index >= 1 || throw(ArgumentError("root_index must be positive"))
        return new(frozen, lower_exact, upper_exact, Int(root_index))
    end
end

struct RecognitionCandidate
    descriptor::AlgebraicDescriptor
    degree_limit::Int
    height_bits::Int
    precision_bits::Int
    confirmation_precision_bits::Int
    method::String
end

struct RecognitionOptions
    degree_limits::Tuple
    height_bits::Tuple
    base_precision_bits::Int
    confirmation_extra_bits::Int

    function RecognitionOptions(
        ;
        degree_limits=(1, 2, 4, 8, 12),
        height_bits=(8, 16, 32, 64),
        base_precision_bits::Integer=768,
        confirmation_extra_bits::Integer=256,
    )
        degrees = Tuple(Int(value) for value in degree_limits)
        heights = Tuple(Int(value) for value in height_bits)
        !isempty(degrees) && issorted(degrees) && all(>(0), degrees) ||
            throw(ArgumentError("degree_limits must be nonempty, positive, and sorted"))
        !isempty(heights) && issorted(heights) && all(>(0), heights) ||
            throw(ArgumentError("height_bits must be nonempty, positive, and sorted"))
        base_precision_bits >= 64 || throw(ArgumentError("base precision must be at least 64 bits"))
        confirmation_extra_bits >= 32 ||
            throw(ArgumentError("confirmation precision must add at least 32 bits"))
        return new(
            degrees,
            heights,
            Int(base_precision_bits),
            Int(confirmation_extra_bits),
        )
    end
end

working_precision(degree::Integer, height_bits::Integer; base_precision_bits::Integer=768) =
    max(Int(base_precision_bits), 2 * (Int(degree) + 1) * Int(height_bits) + 128)

function normalize_polynomial(coefficients)
    values = BigInt[BigInt(coefficient) for coefficient in coefficients]
    while !isempty(values) && iszero(last(values))
        pop!(values)
    end
    length(values) >= 2 || return nothing
    divisor = foldl(gcd, abs.(values))
    iszero(divisor) && return nothing
    values = div.(values, divisor)
    last(values) < 0 && (values = -values)
    return Tuple(values)
end

_coefficient_bits(value::BigInt) = iszero(value) ? 0 : ndigits(abs(value); base=2)
_within_height(coefficients, height_bits) =
    maximum(_coefficient_bits(BigInt(value)) for value in coefficients) <= height_bits

function _polynomial(coefficients)
    return _ZZX(ZZRingElem[ZZ(coefficient) for coefficient in coefficients])
end

function _polynomial_coefficients(polynomial)
    return Tuple(BigInt(coeff(polynomial, exponent)) for exponent in 0:degree(polynomial))
end

function _relation_tolerance(value::BigFloat, precision_bits::Int, height_bits::Int, degree::Int)
    return setprecision(BigFloat, max(precision_bits, precision(value))) do
        # Match the 128-bit safety reserve in `working_precision`. Samples from
        # Core satisfy independent adaptive gates but need not be correctly
        # rounded to every requested bit.
        # Rank-general singular refinement can prove the 100-digit Core gates
        # while losing a precision-proportional tail to a vanishing Jacobian.
        # Retain at least three quarters of the requested bits. Dual-precision
        # identity agreement, reference-sample consistency, and exact C3A
        # replay remain mandatory before this proposal can become an answer.
        guard_bits = max(
            128,
            cld(precision_bits, 4),
            height_bits + ceil(Int, log2(degree + 1)) + 32,
        )
        reliable_bits = max(32, precision_bits - guard_bits)
        ldexp(max(one(value), abs(value)) ^ max(degree, 1), -reliable_bits)
    end
end

function _evaluate_polynomial(coefficients, value::BigFloat)
    return setprecision(BigFloat, precision(value)) do
        result = zero(value)
        for coefficient in Iterators.reverse(coefficients)
            result = muladd(result, value, BigFloat(coefficient))
        end
        result
    end
end

"""
Recover a rational whose numerator and denominator each fit `height_bits`.

Only a height-bounded convergent agreeing through the conservative reliable-bit
window is returned. Merely being the best small-denominator approximation is
insufficient; dual-precision agreement and exact replay are separate gates.
"""
function bounded_rational_reconstruction(
    value::BigFloat,
    height_bits::Integer;
    precision_bits::Integer=precision(value),
    checkpoint=() -> nothing,
)
    checkpoint()
    isfinite(value) || return nothing
    height_bits > 0 || throw(ArgumentError("height_bits must be positive"))
    precision_bits >= 32 || throw(ArgumentError("precision_bits must be at least 32"))
    return setprecision(BigFloat, max(Int(precision_bits), precision(value))) do
        limit = (BigInt(1) << Int(height_bits)) - 1
        iszero(value) && return zero(BigInt) // one(BigInt)
        sign_value = signbit(value) ? -one(BigInt) : one(BigInt)
        magnitude = abs(value)
        p_previous_previous, p_previous = BigInt(0), BigInt(1)
        q_previous_previous, q_previous = BigInt(1), BigInt(0)
        y = BigFloat(magnitude)
        best = nothing
        max_steps = max(64, 2 * Int(precision_bits))

        for _ in 1:max_steps
            checkpoint()
            integer_part = floor(BigInt, y)
            numerator = integer_part * p_previous + p_previous_previous
            denominator = integer_part * q_previous + q_previous_previous
            denominator > limit && break
            abs(numerator) <= limit || break
            candidate = (sign_value * numerator) // denominator
            approximation = BigFloat(numerator) / BigFloat(denominator)
            error = abs(magnitude - approximation)
            tolerance = _relation_tolerance(
                magnitude,
                Int(precision_bits),
                Int(height_bits),
                1,
            )
            error <= tolerance && (best = candidate)

            remainder = y - BigFloat(integer_part)
            iszero(remainder) && break
            p_previous_previous, p_previous = p_previous, numerator
            q_previous_previous, q_previous = q_previous, denominator
            y = inv(remainder)
        end
        best
    end
end

"""
Generate an integer-relation candidate using Nemo's documented LLL `lindep`.

This is deliberately not named PSLQ: Nemo 0.56.1 exposes a heuristic LLL
integer-relation routine, not a PSLQ implementation. Exact replay remains the
future acceptance condition.
"""
function nemo_lll_relation(
    value::BigFloat,
    degree_limit::Integer,
    height_bits::Integer;
    precision_bits::Integer=precision(value),
)
    isfinite(value) || return nothing
    degree_limit >= 1 || throw(ArgumentError("degree_limit must be positive"))
    height_bits >= 1 || throw(ArgumentError("height_bits must be positive"))
    precision_bits >= 64 || throw(ArgumentError("precision_bits must be at least 64"))
    field = ArbField(Int(precision_bits))
    algebraic_approximation = field(value)
    powers = Vector{ArbFieldElem}(undef, Int(degree_limit) + 1)
    powers[1] = field(1)
    for index in 2:length(powers)
        powers[index] = powers[index - 1] * algebraic_approximation
    end
    relation_bits = min(
        Int(precision_bits) - 32,
        max(64, 2 * (Int(degree_limit) + 1) * Int(height_bits) + 32),
    )
    raw = try
        lindep(powers, relation_bits)
    catch
        return nothing
    end
    normalized = normalize_polynomial(BigInt(coefficient) for coefficient in raw)
    normalized === nothing && return nothing
    length(normalized) - 1 <= degree_limit || return nothing
    _within_height(normalized, Int(height_bits)) || return nothing
    accepted = setprecision(BigFloat, max(Int(precision_bits), precision(value))) do
        residual = _evaluate_polynomial(normalized, value)
        abs(residual) <= _relation_tolerance(
            value,
            Int(precision_bits),
            Int(height_bits),
            length(normalized) - 1,
        )
    end
    accepted || return nothing
    return normalized
end

function _root_approximation(root::QQBarFieldElem, bits::Int)
    return setprecision(BigFloat, bits) do
        BigFloat(ArbField(bits)(root))
    end
end

function _real_roots(polynomial)
    roots_exact = QQBarFieldElem[root for root in roots(_QQBAR, polynomial) if isreal(root)]
    sort!(roots_exact; lt=(left, right) -> left < right)
    return roots_exact
end

function _isolating_interval(root::QQBarFieldElem, real_roots; checkpoint=() -> nothing)
    approximation = _root_approximation(root, 512)
    for denominator_bits in (16, 32, 64, 128, 256, 512, 1024, 2048, 4096)
        checkpoint()
        denominator = BigInt(1) << denominator_bits
        midpoint = round(BigInt, ldexp(approximation, denominator_bits))
        lower = (midpoint - 1) // denominator
        upper = (midpoint + 1) // denominator
        lower_exact = _QQBAR(lower)
        upper_exact = _QQBAR(upper)
        lower_exact < root < upper_exact || continue
        count(candidate -> lower_exact < candidate < upper_exact, real_roots) == 1 || continue
        return lower, upper
    end
    return nothing
end

function descriptor_from_root(root::QQBarFieldElem; checkpoint=() -> nothing)
    checkpoint()
    isreal(root) || return nothing
    polynomial = minpoly(_ZZX, root)
    checkpoint()
    coefficients = normalize_polynomial(_polynomial_coefficients(polynomial))
    coefficients === nothing && return nothing
    canonical_polynomial = _polynomial(coefficients)
    real_roots = _real_roots(canonical_polynomial)
    checkpoint()
    root_index = findfirst(candidate -> candidate == root, real_roots)
    root_index === nothing && return nothing
    interval = _isolating_interval(root, real_roots; checkpoint)
    interval === nothing && return nothing
    return AlgebraicDescriptor(coefficients, interval[1], interval[2], root_index)
end

descriptor_from_root(root::AlgebraicReal; kwargs...) = descriptor_from_root(root.value; kwargs...)
descriptor_from_root(root::Union{Integer,Rational}; kwargs...) =
    descriptor_from_root(_QQBAR(root); kwargs...)

function descriptor_from_relation(
    coefficients,
    approximation::BigFloat;
    precision_bits::Integer=precision(approximation),
    height_bits::Integer=64,
    checkpoint=() -> nothing,
)
    checkpoint()
    canonical = normalize_polynomial(coefficients)
    canonical === nothing && return nothing
    _within_height(canonical, Int(height_bits)) || return nothing
    polynomial = _polynomial(canonical)
    possible = QQBarFieldElem[]
    factorization = try
        factor(polynomial)
    catch
        return nothing
    end
    checkpoint()
    tolerance = _relation_tolerance(
        approximation,
        Int(precision_bits),
        Int(height_bits),
        length(canonical) - 1,
    )
    for (irreducible, _) in factorization
        checkpoint()
        for root in _real_roots(irreducible)
            checkpoint()
            close = setprecision(BigFloat, max(Int(precision_bits), precision(approximation))) do
                root_approximation = _root_approximation(root, Int(precision_bits))
                abs(root_approximation - approximation) <= tolerance
            end
            close && push!(possible, root)
        end
    end
    length(possible) == 1 || return nothing
    checkpoint()
    return descriptor_from_root(only(possible); checkpoint)
end

function _reconstruct_descriptor(descriptor::AlgebraicDescriptor; checkpoint=() -> nothing)
    checkpoint()
    canonical = normalize_polynomial(descriptor.coefficients)
    canonical == descriptor.coefficients || return nothing
    polynomial = _polynomial(canonical)
    factorization = factor(polynomial)
    checkpoint()
    length(factorization) == 1 || return nothing
    factor_entry = only(collect(factorization))
    irreducible, exponent = factor_entry
    exponent == 1 || return nothing
    _polynomial_coefficients(irreducible) == descriptor.coefficients || return nothing
    real_roots = _real_roots(polynomial)
    checkpoint()
    descriptor.root_index <= length(real_roots) || return nothing
    selected = real_roots[descriptor.root_index]
    lower = _QQBAR(descriptor.lower)
    upper = _QQBAR(descriptor.upper)
    lower < selected < upper || return nothing
    count(root -> lower < root < upper, real_roots) == 1 || return nothing
    minpoly(_ZZX, selected) == polynomial || return nothing
    return AlgebraicReal(selected)
end

function reconstruct_descriptor(descriptor::AlgebraicDescriptor; checkpoint=() -> nothing)
    return try
        _reconstruct_descriptor(descriptor; checkpoint)
    catch error
        error isa _ExactSampleAbort && rethrow()
        nothing
    end
end

function same_algebraic_identity(
    left::AlgebraicDescriptor,
    right::AlgebraicDescriptor;
    checkpoint=() -> nothing,
)
    checkpoint()
    left.coefficients == right.coefficients || return false
    left.root_index == right.root_index || return false
    left_value = reconstruct_descriptor(left; checkpoint)
    right_value = reconstruct_descriptor(right; checkpoint)
    left_value === nothing && return false
    right_value === nothing && return false
    return left_value == right_value
end

function _provider_value(provider, bits::Int)
    value = provider(bits)
    value isa BigFloat || throw(ArgumentError("the precision provider must return BigFloat"))
    isfinite(value) || throw(ArgumentError("the precision provider returned a nonfinite value"))
    precision(value) >= bits || throw(
        ArgumentError("the precision provider returned fewer than the requested $bits bits"),
    )
    return value
end

function _recognize_sample(
    value,
    degree_limit,
    height_bits,
    precision_bits;
    checkpoint=() -> nothing,
)
    checkpoint()
    if degree_limit == 1
        rational = bounded_rational_reconstruction(
            value,
            height_bits;
            precision_bits,
            checkpoint,
        )
        rational === nothing && return nothing, "bounded_rational_reconstruction"
        checkpoint()
        return descriptor_from_root(rational; checkpoint), "bounded_rational_reconstruction"
    end
    result = pslq_relation(
        value,
        degree_limit,
        height_bits;
        precision_bits,
        checkpoint,
    )
    result.relation === nothing && return nothing, "owned_pslq_v1"
    checkpoint()
    return descriptor_from_relation(
        result.relation,
        value;
        precision_bits,
        height_bits,
        checkpoint,
    ), "owned_pslq_v1"
end

function _recognize_at(
    provider,
    degree_limit,
    height_bits,
    options,
    cache;
    checkpoint=() -> nothing,
)
    checkpoint()
    precision_bits = working_precision(
        degree_limit,
        height_bits;
        base_precision_bits=options.base_precision_bits,
    )
    confirmation_bits = precision_bits + options.confirmation_extra_bits
    sample(bits) = get!(cache, bits) do
        _provider_value(provider, bits)
    end
    first_descriptor, method = _recognize_sample(
        sample(precision_bits),
        degree_limit,
        height_bits,
        precision_bits;
        checkpoint,
    )
    first_descriptor === nothing && return nothing
    checkpoint()
    second_descriptor, second_method = _recognize_sample(
        sample(confirmation_bits),
        degree_limit,
        height_bits,
        confirmation_bits;
        checkpoint,
    )
    second_descriptor === nothing && return nothing
    method == second_method || return nothing
    same_algebraic_identity(first_descriptor, second_descriptor; checkpoint) || return nothing
    return RecognitionCandidate(
        first_descriptor,
        Int(degree_limit),
        Int(height_bits),
        precision_bits,
        confirmation_bits,
        method,
    )
end

function recognize_at(
    provider,
    degree_limit::Integer,
    height_bits::Integer;
    options::RecognitionOptions=RecognitionOptions(),
    checkpoint=() -> nothing,
)
    return _recognize_at(
        provider,
        Int(degree_limit),
        Int(height_bits),
        options,
        Dict{Int,BigFloat}();
        checkpoint,
    )
end

function recognize_algebraic(
    provider;
    options::RecognitionOptions=RecognitionOptions(),
    checkpoint=() -> nothing,
)
    cache = Dict{Int,BigFloat}()
    for degree_limit in options.degree_limits
        for height_bits in options.height_bits
            checkpoint()
            candidate = _recognize_at(
                provider,
                degree_limit,
                height_bits,
                options,
                cache;
                checkpoint,
            )
            candidate === nothing || return candidate
        end
    end
    return nothing
end
