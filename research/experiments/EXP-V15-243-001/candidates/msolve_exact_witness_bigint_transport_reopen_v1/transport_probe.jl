#!/usr/bin/env julia

using JSON3

length(ARGS) == 1 || error("usage: transport_probe.jl JOB.json")
job = JSON3.read(read(ARGS[1], String))
values = String[]

function collect_coefficients(value)
  if value isa JSON3.Object
    for (key, child) in pairs(value)
      if String(key) in (
        "coefficients_high_to_low",
        "coefficients_low_to_high",
        "minimal_polynomial_high_to_low",
        "minimal_polynomial_low_to_high",
        "theta_numerators_low_to_high",
      )
        for coefficient in child
          text = String(coefficient)
          parse(BigInt, text)
          push!(values, text)
        end
      else
        collect_coefficients(child)
      end
    end
  elseif value isa JSON3.Array
    for child in value
      collect_coefficients(child)
    end
  end
end

collect_coefficients(job)
println(JSON3.write(Dict("status" => "PARSED", "values" => values)))
