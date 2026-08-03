#!/usr/bin/env julia

"""Run one pinned HomotopyContinuation solve for a compiled polynomial system.

Input is the JSON emitted by ``Compilation.json()``.  The worker deliberately
returns numerical witnesses and certificate metadata only; exact target
polynomials and root intervals are produced by the Python exact-elimination
stage from the original rational coefficients.
"""

using HomotopyContinuation
using JSON3
using Nemo
using Singular

const PRECISIONS = (256, 512, 1024)

function _json_number(value)
    value isa Integer && return string(value)
    return string(value)
end

function _coordinate(value)
    return Dict("re" => string(real(value)), "im" => string(imag(value)))
end

function _solution_coordinates(solution)
    return [_coordinate(value) for value in solution]
end

function _make_variables(names)
    all(Base.isidentifier, names) || error("non-identifier polynomial variable")
    expression = Meta.parse("@polyvar " * join(names, " "))
    values = Core.eval(Main, expression)
    return values isa Tuple ? collect(values) : [values]
end

function _polynomial(payload, variables)
    result = 0
    for term in payload["terms"]
        coefficient = BigInt(term["numerator"]) // BigInt(term["denominator"])
        monomial = coefficient
        for (variable, exponent) in zip(variables, term["exponents"])
            monomial *= variable ^ Int(exponent)
        end
        result += monomial
    end
    return result
end

function _certificate_summary(system, solutions_to_certify)
    isempty(solutions_to_certify) && return Any[], 0, nothing
    all_certificates = nothing
    last_error = nothing
    for precision in PRECISIONS
        try
            result = certify(
                system,
                solutions_to_certify;
                max_precision = precision,
                show_progress = false,
            )
            all_certificates = result.certificates
            if all(c -> c.certified, all_certificates)
                return all_certificates, precision, nothing
            end
        catch error
            last_error = sprint(showerror, error)
        end
    end
    return all_certificates, maximum(PRECISIONS), last_error
end

function main(input_path, output_path)
    started = time()
    payload = JSON3.read(read(input_path, String), Dict{String, Any})
    names = [String(value) for value in payload["variables"]]
    variables = _make_variables(names)
    equations = [_polynomial(item, variables) for item in payload["equations"]]
    system = System(equations; variables = variables)
    seed = UInt32(mod(Int(get(payload, "seed", 0)), 2^32))
    homotopy_started = time()
    result = solve(
        system;
        start_system = :polyhedral,
        only_non_zero = false,
        seed = seed,
        show_progress = false,
        threading = false,
        catch_interrupt = true,
    )
    homotopy_elapsed = time() - homotopy_started
    paths = result.path_results
    successful = [path for path in paths if path.return_code == :success]
    singular_count = count(path -> Bool(path.singular), successful)
    raw_solutions = [solution(path) for path in successful]
    certification_started = time()
    certificates, precision, certification_error = _certificate_summary(system, raw_solutions)
    certification_elapsed = time() - certification_started
    candidates = Any[]
    certified_count = 0
    real_certified_count = 0
    certificate_precisions = Int[]
    if certificates !== nothing
        for (index, certificate) in enumerate(certificates)
            is_certified = Bool(certificate.certified)
            is_real_solution = Bool(certificate.real)
            certified_count += is_certified ? 1 : 0
            real_certified_count += (is_certified && is_real_solution) ? 1 : 0
            push!(certificate_precisions, Int(certificate.prec))
            push!(
                candidates,
                Dict(
                    "path_index" => index,
                    "coordinates" => _solution_coordinates(raw_solutions[index]),
                    "certified" => is_certified,
                    "real" => is_real_solution,
                    "precision_bits" => Int(certificate.prec),
                    "certificate_interval" => string(certificate.I),
                ),
            )
        end
    else
        for (index, solution_value) in enumerate(raw_solutions)
            push!(
                candidates,
                Dict(
                    "path_index" => index,
                    "coordinates" => _solution_coordinates(solution_value),
                    "certified" => false,
                    "real" => false,
                ),
            )
        end
    end
    output = Dict(
        "schema_version" => "geotarget.homotopy-worker/v1",
        "exact_backend" => "Nemo+Singular (pinned; Python mirrors the exact elimination for JSON portability)",
        "status" => certification_error === nothing ? "certified" : "certification_failed",
        "paths" => length(paths),
        "successful_paths" => length(successful),
        "failed_paths" => length(paths) - length(successful),
        "singular_paths" => singular_count,
        "certified_count" => certified_count,
        "real_certified_count" => real_certified_count,
        "certification_precision_bits" => precision,
        "certificate_min_precision_bits" => isempty(certificate_precisions) ? nothing : minimum(certificate_precisions),
        "certificate_max_precision_bits" => isempty(certificate_precisions) ? nothing : maximum(certificate_precisions),
        "certification_error" => certification_error,
        "candidates" => candidates,
        "timings" => Dict(
            "homotopy_seconds" => homotopy_elapsed,
            "certification_seconds" => certification_elapsed,
            "worker_seconds" => time() - started,
        ),
    )
    open(output_path, "w") do io
        JSON3.write(io, output)
    end
    return nothing
end

if abspath(PROGRAM_FILE) == @__FILE__
    length(ARGS) == 2 || error("usage: worker.jl INPUT.json OUTPUT.json")
    main(ARGS[1], ARGS[2])
end
