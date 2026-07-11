#!/usr/bin/env julia

using GeoTargetCore

function bits_value(text)::Float64
    text isa AbstractString || error("bit authority must be text")
    occursin(r"^0x[0-9a-f]{16}$", text) || error("invalid binary64 authority")
    return reinterpret(Float64, parse(UInt64, text[3:end]; base=16))
end

function verify_numeric_environment(path::AbstractString)
    fixture = parse_protocol_json(read(path, String))
    fixture["schema_version"] == "exp-local-003-numeric-json-domain/v1" ||
        error("numeric fixture schema drift")
    for row in fixture["fma_fixture"]
        observed = Base.fma(
            bits_value(row["a_bits"]),
            bits_value(row["b_bits"]),
            bits_value(row["c_bits"]),
        )
        reinterpret(UInt64, observed) ==
            reinterpret(UInt64, bits_value(row["result_bits"])) ||
            error("Base.fma bit mismatch")
    end
    integral = only(filter(
        row -> row["id"] == "integral-real-token", fixture["cases"]
    ))
    value = integral["json_value"]
    ((value isa Integer || value isa AbstractFloat) && !(value isa Bool)) ||
        error("integral real JSON token rejected")
    reinterpret(UInt64, Float64(value)) ==
        reinterpret(UInt64, bits_value(integral["binary64_bits"])) ||
        error("integral real binary64 mismatch")
    parsed_payload = parse_protocol_json(String(fixture["canonical_payload_text"]))
    Float64(parsed_payload["exact_integral_real"]) == 1.0 ||
        error("canonical integral-real payload mismatch")
    print("numeric-environment-ok")
    return nothing
end

if abspath(PROGRAM_FILE) == @__FILE__
    length(ARGS) == 1 || error("usage: verify_numeric_environment.jl FIXTURE")
    verify_numeric_environment(ARGS[1])
end
