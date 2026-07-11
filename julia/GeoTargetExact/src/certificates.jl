_canonical_integer_text(value::BigInt) = string(value)

function _parse_canonical_integer(value)
    value isa AbstractString || return nothing
    occursin(r"^(0|-?[1-9][0-9]*)$", value) || return nothing
    return try
        parse(BigInt, value)
    catch
        nothing
    end
end

function _rational_document(value::Rational{BigInt})
    return Dict{String,Any}(
        "numerator" => _canonical_integer_text(numerator(value)),
        "denominator" => _canonical_integer_text(denominator(value)),
    )
end

function _rational_from_document(value)
    value isa AbstractDict || return nothing
    Set(keys(value)) == Set(("numerator", "denominator")) || return nothing
    numerator_value = _parse_canonical_integer(value["numerator"])
    denominator_value = _parse_canonical_integer(value["denominator"])
    numerator_value === nothing && return nothing
    denominator_value === nothing && return nothing
    denominator_value > 0 || return nothing
    gcd(abs(numerator_value), denominator_value) == 1 || return nothing
    return numerator_value // denominator_value
end

function descriptor_document(descriptor::AlgebraicDescriptor)
    return Dict{String,Any}(
        "coefficients" => Any[_canonical_integer_text(value) for value in descriptor.coefficients],
        "isolating_interval" => Dict{String,Any}(
            "lower" => _rational_document(descriptor.lower),
            "upper" => _rational_document(descriptor.upper),
        ),
        "real_root_index" => descriptor.root_index,
    )
end

"""
Decode and independently reconstruct a descriptor claim.

Returning `nothing` is intentional fail-closed behavior: canonical text,
primitive irreducible polynomial form, interval isolation, and root index are
all rechecked instead of trusting the supplied certificate fields.
"""
function descriptor_from_document(document)
    document isa AbstractDict || return nothing
    Set(keys(document)) == Set(("coefficients", "isolating_interval", "real_root_index")) ||
        return nothing
    raw_coefficients = document["coefficients"]
    raw_coefficients isa AbstractVector || return nothing
    coefficients = BigInt[]
    for raw in raw_coefficients
        coefficient = _parse_canonical_integer(raw)
        coefficient === nothing && return nothing
        push!(coefficients, coefficient)
    end
    interval = document["isolating_interval"]
    interval isa AbstractDict || return nothing
    Set(keys(interval)) == Set(("lower", "upper")) || return nothing
    lower = _rational_from_document(interval["lower"])
    upper = _rational_from_document(interval["upper"])
    lower === nothing && return nothing
    upper === nothing && return nothing
    root_index = document["real_root_index"]
    root_index isa Integer || return nothing
    root_index isa Bool && return nothing
    descriptor = try
        AlgebraicDescriptor(coefficients, lower, upper, root_index)
    catch
        return nothing
    end
    reconstruct_descriptor(descriptor) === nothing && return nothing
    return descriptor
end
