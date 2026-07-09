const _JCS_SAFE_INTEGER = Int64(9_007_199_254_740_991)

const _INTEGER_WIRE_TYPES = (
    ("Int8", Int8),
    ("UInt8", UInt8),
    ("Int16", Int16),
    ("UInt16", UInt16),
    ("Int32", Int32),
    ("UInt32", UInt32),
    ("Int64", Int64),
    ("UInt64", UInt64),
    ("Int128", Int128),
    ("UInt128", UInt128),
    ("BigInt", BigInt),
)

_codec_failure(message::AbstractString) = throw(ArgumentError(String(message)))

function _codec_object(raw, expected_keys)
    raw isa AbstractDict || _codec_failure("literal projection must be an object")
    all(key -> key isa String, keys(raw)) ||
        _codec_failure("literal projection object keys must be strings")
    actual = sort!(String[key for key in keys(raw)])
    expected = sort!(String[String(key) for key in expected_keys])
    actual == expected || _codec_failure(
        "literal projection must contain exactly $(join(expected, ", "))",
    )
    return raw
end

function _codec_string(raw, name::AbstractString)
    raw isa String || _codec_failure("$name must be a string")
    return raw
end

function _integer_wire_name(integer_type::Type)
    for (name, candidate) in _INTEGER_WIRE_TYPES
        integer_type === candidate && return name
    end
    _codec_failure("unsupported integer type $integer_type")
end

function _integer_wire_type(name::String)
    for (candidate_name, integer_type) in _INTEGER_WIRE_TYPES
        name == candidate_name && return integer_type
    end
    _codec_failure("unknown integer wire type $name")
end

function _canonical_integer_decimal(raw, name::AbstractString)
    decimal = _codec_string(raw, name)
    occursin(r"^(?:0|-[1-9][0-9]*|[1-9][0-9]*)$", decimal) ||
        _codec_failure("$name must be a canonical integer decimal")
    return decimal
end

function _parse_wire_integer(integer_type::Type, raw, name::AbstractString)
    decimal = _canonical_integer_decimal(raw, name)
    return try
        parse(integer_type, decimal)
    catch error
        _codec_failure("$name does not fit $integer_type: $(sprint(showerror, error))")
    end
end

_is_safe_json_integer(value::Integer) =
    -_JCS_SAFE_INTEGER <= value <= _JCS_SAFE_INTEGER

function _encode_integer(value::Integer)
    value isa Bool && _codec_failure("Bool is not a geometry scalar")
    if typeof(value) === Int64 && _is_safe_json_integer(value)
        return value
    end
    return Dict{String,Any}(
        "kind" => "integer",
        "type" => _integer_wire_name(typeof(value)),
        "decimal" => string(value),
    )
end

function _decode_integer(raw)
    object = _codec_object(raw, ("kind", "type", "decimal"))
    object["kind"] == "integer" || _codec_failure("integer kind must be integer")
    type_name = _codec_string(object["type"], "integer type")
    integer_type = _integer_wire_type(type_name)
    value = _parse_wire_integer(integer_type, object["decimal"], "integer decimal")
    _encode_integer(value) == object ||
        _codec_failure("integer projection is not canonical")
    return value
end

function _encode_rational(value::Rational{T}) where {T<:Integer}
    return Dict{String,Any}(
        "kind" => "rational",
        "type" => _integer_wire_name(T),
        "numerator" => string(numerator(value)),
        "denominator" => string(denominator(value)),
    )
end

function _decode_rational(raw)
    object = _codec_object(
        raw,
        ("kind", "type", "numerator", "denominator"),
    )
    object["kind"] == "rational" || _codec_failure("rational kind must be rational")
    type_name = _codec_string(object["type"], "rational integer type")
    integer_type = _integer_wire_type(type_name)
    numerator_value =
        _parse_wire_integer(integer_type, object["numerator"], "rational numerator")
    denominator_value =
        _parse_wire_integer(integer_type, object["denominator"], "rational denominator")
    denominator_value > 0 || _codec_failure("rational denominator must be positive")
    gcd(BigInt(numerator_value), BigInt(denominator_value)) == 1 ||
        _codec_failure("rational numerator and denominator must be reduced")
    value = Rational{integer_type}(numerator_value, denominator_value)
    _encode_rational(value) == object ||
        _codec_failure("rational projection is not canonical")
    return value
end

_requires_tag(value::Float64) =
    (iszero(value) && signbit(value)) ||
    (isinteger(value) && abs(value) > _JCS_SAFE_INTEGER)

function _float_bits(value::Float16)
    return lpad(string(reinterpret(UInt16, value); base = 16), 4, '0')
end

function _float_bits(value::Float32)
    return lpad(string(reinterpret(UInt32, value); base = 16), 8, '0')
end

function _float_bits(value::Float64)
    return lpad(string(reinterpret(UInt64, value); base = 16), 16, '0')
end

function _encode_binary_float(value::T) where {T<:Union{Float16,Float32,Float64}}
    isfinite(value) || _codec_failure("non-finite geometry scalars are not supported")
    if T === Float64 && !_requires_tag(value)
        return value
    end
    return Dict{String,Any}(
        "kind" => "float",
        "type" => string(T),
        "bits" => _float_bits(value),
    )
end

function _decode_float_bits(raw, float_type::Type, width::Int)
    bits = _codec_string(raw, "float bits")
    occursin(Regex("^[0-9a-f]{$width}\$"), bits) ||
        _codec_failure("float bits must contain exactly $width lowercase hexadecimal digits")
    unsigned_type =
        float_type === Float16 ? UInt16 : float_type === Float32 ? UInt32 : UInt64
    material = parse(unsigned_type, bits; base = 16)
    value = reinterpret(float_type, material)
    isfinite(value) || _codec_failure("non-finite geometry scalars are not supported")
    float_type === Float64 && !_requires_tag(value) &&
        _codec_failure("Float64 projection is not canonical; use a plain JSON number")
    return value
end

function _encode_bigfloat(value::BigFloat)
    isfinite(value) || _codec_failure("non-finite geometry scalars are not supported")
    return Dict{String,Any}(
        "kind" => "float",
        "type" => "BigFloat",
        "precision_bits" => precision(value),
        "decimal" => string(value),
    )
end

function _decode_bigfloat(raw)
    object = _codec_object(
        raw,
        ("kind", "type", "precision_bits", "decimal"),
    )
    object["kind"] == "float" || _codec_failure("BigFloat kind must be float")
    object["type"] == "BigFloat" || _codec_failure("BigFloat type must be BigFloat")
    precision_raw = object["precision_bits"]
    precision_raw isa Integer && !(precision_raw isa Bool) ||
        _codec_failure("BigFloat precision_bits must be an integer")
    2 <= precision_raw <= _JCS_SAFE_INTEGER ||
        _codec_failure("BigFloat precision_bits is outside the supported JSON range")
    precision_bits = try
        Int(precision_raw)
    catch
        _codec_failure("BigFloat precision_bits does not fit the runtime Int type")
    end
    decimal = _codec_string(object["decimal"], "BigFloat decimal")
    value = try
        setprecision(BigFloat, precision_bits) do
            parse(BigFloat, decimal)
        end
    catch error
        _codec_failure("invalid BigFloat decimal: $(sprint(showerror, error))")
    end
    isfinite(value) || _codec_failure("non-finite geometry scalars are not supported")
    _encode_bigfloat(value) == object ||
        _codec_failure("BigFloat projection is not canonical")
    return value
end

function _decode_float(raw)
    raw isa AbstractDict || _codec_failure("float projection must be an object")
    haskey(raw, "kind") || _codec_failure("float projection is missing kind")
    haskey(raw, "type") || _codec_failure("float projection is missing type")
    raw["kind"] == "float" || _codec_failure("float kind must be float")
    type_name = _codec_string(raw["type"], "float type")
    if type_name == "Float16"
        object = _codec_object(raw, ("kind", "type", "bits"))
        return _decode_float_bits(object["bits"], Float16, 4)
    elseif type_name == "Float32"
        object = _codec_object(raw, ("kind", "type", "bits"))
        return _decode_float_bits(object["bits"], Float32, 8)
    elseif type_name == "Float64"
        object = _codec_object(raw, ("kind", "type", "bits"))
        return _decode_float_bits(object["bits"], Float64, 16)
    elseif type_name == "BigFloat"
        return _decode_bigfloat(raw)
    end
    _codec_failure("unknown float wire type $type_name")
end

function _encode_scalar_literal(value)
    value isa Real || _codec_failure("geometry scalar must be Real")
    value isa Bool && _codec_failure("Bool is not a geometry scalar")
    value isa Rational && return _encode_rational(value)
    value isa Integer && return _encode_integer(value)
    value isa BigFloat && return _encode_bigfloat(value)
    value isa Union{Float16,Float32,Float64} && return _encode_binary_float(value)
    _codec_failure("unsupported geometry scalar type $(typeof(value))")
end

function _decode_scalar_literal(raw)
    raw isa Bool && _codec_failure("Bool is not a geometry scalar")
    if raw isa Integer
        _is_safe_json_integer(raw) ||
            _codec_failure("plain integers must be in the safe JSON range")
        return Int64(raw)
    elseif raw isa Float64
        isfinite(raw) || _codec_failure("non-finite geometry scalars are not supported")
        _requires_tag(raw) &&
            _codec_failure("this Float64 value requires its canonical tagged projection")
        return raw
    elseif raw isa AbstractDict
        haskey(raw, "kind") || _codec_failure("tagged scalar projection is missing kind")
        kind = _codec_string(raw["kind"], "scalar kind")
        kind == "integer" && return _decode_integer(raw)
        kind == "rational" && return _decode_rational(raw)
        kind == "float" && return _decode_float(raw)
        _codec_failure("unknown scalar kind $kind")
    end
    _codec_failure("scalar projection must be a JSON number or tagged object")
end

function _numeric_wire_name(numeric_type::Type)
    numeric_type === Float16 && return "Float16"
    numeric_type === Float32 && return "Float32"
    numeric_type === Float64 && return "Float64"
    numeric_type === BigFloat && return "BigFloat"
    numeric_type <: Integer && return _integer_wire_name(numeric_type)
    if numeric_type <: Rational
        integer_type = numeric_type.parameters[1]
        return "Rational{$(_integer_wire_name(integer_type))}"
    end
    _codec_failure("unsupported geometry numeric type $numeric_type")
end

function _numeric_wire_type(name::String)
    name == "Float16" && return Float16
    name == "Float32" && return Float32
    name == "Float64" && return Float64
    name == "BigFloat" && return BigFloat
    for (integer_name, integer_type) in _INTEGER_WIRE_TYPES
        name == integer_name && return integer_type
        name == "Rational{$integer_name}" && return Rational{integer_type}
    end
    _codec_failure("unknown geometry numeric wire type $name")
end

function _nested_scalar(raw, expected_type::Type)
    value = _decode_scalar_literal(raw)
    typeof(value) === expected_type && return value
    if expected_type === Float64 && value isa Int64 && _is_safe_json_integer(value)
        return Float64(value)
    end
    _codec_failure(
        "nested scalar has type $(typeof(value)); expected canonical $expected_type projection",
    )
end

function _encode_point_literal(value::Point2{T}) where {T<:Real}
    return Dict{String,Any}(
        "kind" => "point2",
        "numeric_type" => _numeric_wire_name(T),
        "x" => _encode_scalar_literal(value.x),
        "y" => _encode_scalar_literal(value.y),
    )
end

function _decode_point_literal(raw)
    object = _codec_object(raw, ("kind", "numeric_type", "x", "y"))
    object["kind"] == "point2" || _codec_failure("point kind must be point2")
    type_name = _codec_string(object["numeric_type"], "point numeric_type")
    numeric_type = _numeric_wire_type(type_name)
    x = _nested_scalar(object["x"], numeric_type)
    y = _nested_scalar(object["y"], numeric_type)
    return Point2{numeric_type}(x, y)
end

function _encode_line_literal(value::Line2)
    return Dict{String,Any}(
        "kind" => "line2",
        "anchor" => _encode_point_literal(value.anchor),
        "direction" => _encode_point_literal(value.direction),
    )
end

function _decode_line_literal(raw)
    object = _codec_object(raw, ("kind", "anchor", "direction"))
    object["kind"] == "line2" || _codec_failure("line kind must be line2")
    anchor = _decode_point_literal(object["anchor"])
    direction = _decode_point_literal(object["direction"])
    typeof(anchor) === typeof(direction) ||
        _codec_failure("line anchor and direction must use the same numeric type")
    numeric_type = typeof(anchor).parameters[1]
    return Line2{numeric_type}(anchor, direction)
end

function _encode_circle_literal(value::Circle2)
    return Dict{String,Any}(
        "kind" => "circle2",
        "center" => _encode_point_literal(value.center),
        "radius" => _encode_scalar_literal(value.radius),
    )
end

function _decode_circle_literal(raw)
    object = _codec_object(raw, ("kind", "center", "radius"))
    object["kind"] == "circle2" || _codec_failure("circle kind must be circle2")
    center = _decode_point_literal(object["center"])
    numeric_type = typeof(center).parameters[1]
    radius = _nested_scalar(object["radius"], numeric_type)
    return Circle2{numeric_type}(center, radius)
end
