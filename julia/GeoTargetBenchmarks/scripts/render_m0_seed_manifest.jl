using GeoTargetBenchmarks

struct JsonObject
    fields::Vector{Pair{String,Any}}
end

JsonObject(fields::Pair...) = JsonObject(Pair{String,Any}[String(key) => value for (key, value) in fields])

function write_json(io::IO, value::AbstractString)
    print(io, '"')
    for character in value
        if character == '"'
            print(io, "\\\"")
        elseif character == '\\'
            print(io, "\\\\")
        elseif character == '\n'
            print(io, "\\n")
        elseif character == '\r'
            print(io, "\\r")
        elseif character == '\t'
            print(io, "\\t")
        elseif Int(character) < 0x20
            print(io, "\\u", lowercase(string(Int(character); base=16, pad=4)))
        else
            print(io, character)
        end
    end
    print(io, '"')
end

write_json(io::IO, value::Symbol) = write_json(io, String(value))
write_json(io::IO, value::Bool) = print(io, value ? "true" : "false")
write_json(io::IO, value::Integer) = print(io, value)

function write_json(io::IO, value::AbstractFloat)
    isfinite(value) || throw(ArgumentError("JSON manifest values must be finite"))
    print(io, repr(value))
end

function write_json(io::IO, values::Union{Tuple,AbstractVector})
    print(io, '[')
    for (index, value) in enumerate(values)
        index > 1 && print(io, ',')
        write_json(io, value)
    end
    print(io, ']')
end

function write_json(io::IO, object::JsonObject)
    print(io, '{')
    for (index, (key, value)) in enumerate(object.fields)
        index > 1 && print(io, ',')
        write_json(io, key)
        print(io, ':')
        write_json(io, value)
    end
    print(io, '}')
end

function parameter_object(parameters)
    return JsonObject(
        (
            String(name) => getfield(parameters, name)
            for name in fieldnames(typeof(parameters))
        )...,
    )
end

function m0_seed_problems()
    return DirectAnalyticProblem[
        generate(
            ScaleLadderParams(
                dimension=4,
                residual_scale_spread=1.0e12,
                instance_seed=701,
                start_seed=1701,
                start_count=32,
            ),
        ),
        generate(
            CurvedChainParams(
                dimension=4,
                curvature=1.0e4,
                instance_seed=702,
                start_seed=1702,
                start_count=32,
            ),
        ),
        generate(
            NearRankDeficientParams(
                dimension=4,
                singular_value_ratio=1.0e-8,
                orientation_seed=703,
                start_seed=1703,
                start_count=32,
            ),
        ),
        generate(
            RedundantOverdeterminedParams(
                dimension=4,
                redundancy=2,
                dependency_error=1.0e-8,
                dependency_seed=704,
                start_seed=1704,
                start_count=32,
            ),
        ),
        generate(
            TangentCircleLineParams(
                radius=1.0,
                height_radius_ratio=0.999,
                instance_seed=705,
                start_seed=1705,
                start_count=32,
            ),
        ),
        generate(
            MultiRootWarpedParams(
                dimension=4,
                root_count=4,
                minimum_separation=1.0e-3,
                warp=0.5,
                condition=1.0e4,
                target_map=:z1,
                coefficient_seed=706,
                start_seed=1706,
                start_count=32,
            ),
        ),
        generate(
            MultiRootWarpedParams(
                dimension=4,
                root_count=4,
                minimum_separation=0.1,
                warp=0.5,
                condition=100.0,
                target_map=:z1_squared,
                coefficient_seed=707,
                start_seed=1707,
                start_count=32,
            ),
        ),
    ]
end

function case_object(index::Int, problem::DirectAnalyticProblem)
    truth_levels = sort!(
        unique(
            target isa ExactGoldTarget ? "exact_analytic" : "validated_interval"
            for target in problem.gold_targets
        ),
    )
    starts_artifact = only(
        filter(artifact -> artifact.name === :saved_starts, problem.artifacts),
    )
    return JsonObject(
        "case_id" => string("M0-ANALYTIC-", lpad(index, 3, '0')),
        "family_id" => problem.family_id,
        "instance_id" => problem.instance_id,
        "strata" => String.(problem.strata),
        "parameters" => parameter_object(problem.parameters),
        "configuration_count" => size(problem.gold_configurations, 2),
        "distinct_target_count" => length(problem.gold_targets),
        "truth_levels" => truth_levels,
        "saved_start_count" => size(problem.saved_starts, 2),
        "saved_starts_sha256" => starts_artifact.sha256,
        "materialized_artifact_count" => length(problem.artifacts),
        "replay_sha256" => replay_checksum(problem),
    )
end

function render_m0_seed_manifest()
    problems = m0_seed_problems()
    all(verify_replay_material, problems) || error("seed problem replay material is invalid")
    covered = sort!(unique(String(stratum) for problem in problems for stratum in problem.strata))
    not_claimed = sort!(setdiff(["S$(index)" for index in 1:8], covered))
    manifest = JsonObject(
        "format_version" => "1.0.0",
        "manifest_id" => "M0-ANALYTIC-SEED-1",
        "status" => "development",
        "partition" => "D2",
        "generator_package" => "GeoTargetBenchmarks",
        "generator_version" => string(PACKAGE_VERSION),
        "replay_format" => REPLAY_FORMAT_VERSION,
        "truth_policy" => "Analytic construction truth only; no retired solver output or numerical union.",
        "covered_strata" => covered,
        "not_claimed_strata" => not_claimed,
        "cases" => [case_object(index, problem) for (index, problem) in enumerate(problems)],
    )
    io = IOBuffer()
    write_json(io, manifest)
    write(io, UInt8('\n'))
    return String(take!(io))
end

if abspath(PROGRAM_FILE) == @__FILE__
    print(render_m0_seed_manifest())
end
