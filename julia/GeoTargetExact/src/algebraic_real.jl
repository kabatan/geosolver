const _QQBAR = algebraic_closure(QQ)
const _ZZX, _ZZX_GENERATOR = polynomial_ring(ZZ, "x")

"""A real algebraic number backed by Nemo's exact `QQBar` domain."""
struct AlgebraicReal <: Real
    value::QQBarFieldElem

    function AlgebraicReal(value::QQBarFieldElem)
        isreal(value) || throw(DomainError(value, "an AlgebraicReal must be real"))
        return new(value)
    end
end

algebraic_value(value::AlgebraicReal) = value.value

AlgebraicReal(value::AlgebraicReal) = value
AlgebraicReal(value::Integer) = AlgebraicReal(_QQBAR(value))
AlgebraicReal(value::Rational) = AlgebraicReal(_QQBAR(value))

function AlgebraicReal(value::AbstractFloat)
    isfinite(value) || throw(DomainError(value, "only finite floating-point values embed exactly"))
    # Julia's Rational conversion preserves the exact binary floating-point value.
    return AlgebraicReal(Rational{BigInt}(value))
end

Base.convert(::Type{AlgebraicReal}, value::AlgebraicReal) = value
Base.convert(::Type{AlgebraicReal}, value::Integer) = AlgebraicReal(value)
Base.convert(::Type{AlgebraicReal}, value::Rational) = AlgebraicReal(value)
Base.convert(::Type{AlgebraicReal}, value::AbstractFloat) = AlgebraicReal(value)

for NumericType in (Integer, Rational, AbstractFloat)
    @eval begin
        Base.promote_rule(::Type{AlgebraicReal}, ::Type{T}) where {T<:$NumericType} =
            AlgebraicReal
        Base.promote_rule(::Type{T}, ::Type{AlgebraicReal}) where {T<:$NumericType} =
            AlgebraicReal
    end
end

Base.zero(::Type{AlgebraicReal}) = AlgebraicReal(0)
Base.zero(::AlgebraicReal) = AlgebraicReal(0)
Base.one(::Type{AlgebraicReal}) = AlgebraicReal(1)
Base.one(::AlgebraicReal) = AlgebraicReal(1)

Base.:+(left::AlgebraicReal, right::AlgebraicReal) =
    AlgebraicReal(left.value + right.value)
Base.:-(left::AlgebraicReal, right::AlgebraicReal) =
    AlgebraicReal(left.value - right.value)
Base.:*(left::AlgebraicReal, right::AlgebraicReal) =
    AlgebraicReal(left.value * right.value)
Base.:/(left::AlgebraicReal, right::AlgebraicReal) =
    AlgebraicReal(left.value / right.value)
Base.://(left::AlgebraicReal, right::AlgebraicReal) = left / right
Base.:-(value::AlgebraicReal) = AlgebraicReal(-value.value)
Base.:+(value::AlgebraicReal) = value
Base.inv(value::AlgebraicReal) = AlgebraicReal(inv(value.value))
Base.:^(value::AlgebraicReal, exponent::Integer) =
    AlgebraicReal(value.value ^ exponent)

Base.:(==)(left::AlgebraicReal, right::AlgebraicReal) = left.value == right.value
Base.isless(left::AlgebraicReal, right::AlgebraicReal) = isless(left.value, right.value)
Base.:<(left::AlgebraicReal, right::AlgebraicReal) = left.value < right.value
Base.:<=(left::AlgebraicReal, right::AlgebraicReal) = left.value <= right.value
Base.:>(left::AlgebraicReal, right::AlgebraicReal) = left.value > right.value
Base.:>=(left::AlgebraicReal, right::AlgebraicReal) = left.value >= right.value
Base.iszero(value::AlgebraicReal) = iszero(value.value)
Base.isone(value::AlgebraicReal) = isone(value.value)
Base.isfinite(::AlgebraicReal) = true
Base.isinf(::AlgebraicReal) = false
Base.isnan(::AlgebraicReal) = false
Base.real(value::AlgebraicReal) = value
Base.imag(::AlgebraicReal) = zero(AlgebraicReal)
Base.conj(value::AlgebraicReal) = value
Base.abs(value::AlgebraicReal) = value < zero(value) ? -value : value
Base.abs2(value::AlgebraicReal) = value * value
Base.sign(value::AlgebraicReal) = iszero(value) ? zero(value) :
                                  (value > zero(value) ? one(value) : -one(value))

function Base.sqrt(value::AlgebraicReal)
    root = sqrt(value.value)
    isreal(root) || throw(DomainError(value, "the principal square root is not real"))
    return AlgebraicReal(root)
end

function Base.BigFloat(value::AlgebraicReal)
    field = ArbField(precision(BigFloat))
    return BigFloat(field(value.value))
end

Base.Float64(value::AlgebraicReal) = Float64(ArbField(128)(value.value))
Base.hash(value::AlgebraicReal, seed::UInt) = hash(value.value, seed)
Base.show(io::IO, value::AlgebraicReal) = print(io, "AlgebraicReal(", value.value, ")")

"""
Return true only when a value tree contains no floating-point leaf.

This is a defensive primitive for the C3A interpreter. Nemo algebraic values
and `AlgebraicReal` are exact leaves; arbitrary floats are rejected even when
their displayed decimal happens to look algebraic.
"""
function exact_leaf_safe(value)
    return _exact_leaf_safe(value, IdDict{Any,Nothing}())
end

function _exact_leaf_safe(value, seen)
    value isa AbstractFloat && return false
    value isa Union{Function,Module,Type,Ptr,Task} && return false
    value isa Union{Nothing,Bool,Integer,Rational,AbstractString,Symbol,Char} && return true
    value isa Union{AlgebraicReal,QQBarFieldElem,ZZRingElem,QQFieldElem} && return true
    if Base.ismutable(value)
        haskey(seen, value) && return true
        seen[value] = nothing
    end
    if value isa AbstractDict
        return all(
            pair -> _exact_leaf_safe(first(pair), seen) &&
                    _exact_leaf_safe(last(pair), seen),
            pairs(value),
        )
    end
    if value isa Tuple || value isa NamedTuple || value isa AbstractArray
        return all(entry -> _exact_leaf_safe(entry, seen), value)
    end
    type = typeof(value)
    isstructtype(type) || return false
    fieldcount(type) > 0 || return false
    return all(index -> _exact_leaf_safe(getfield(value, index), seen), 1:fieldcount(type))
end
