#!/usr/bin/env julia

# C0-owned, result-blind child for EXP-LOCAL-003 default equivalence.
#
# The child receives a fixture but never an expected result.  It emits exactly
# one RFC 8785/JCS observation document and no newline.  The C0 Python observer
# runs `reference` and `mechanism-disabled` in separate fresh AppContainers and
# alone compares these bytes with the C0 golden bytes.

using GeoTargetBase
using GeoTargetCore
using GeoTargetGeometry

const FIXTURE_SCHEMA = "geotarget.exp-local-003.c2-equivalence-fixture/v1"
const OBSERVATION_SCHEMA = "geotarget.exp-local-003.c2-equivalence-observation/v1"
const MECHANISM_API_VERSION = v"1.0.0"

function fail(message)
    throw(ArgumentError(String(message)))
end

length(ARGS) in (3, 4) || fail(
    "usage: c2_equivalence_child.jl MODE FIXTURE PLUGIN [MECHANISM]",
)
const CHILD_MODE = ARGS[1]
const FIXTURE_PATH = ARGS[2]
const PLUGIN_SOURCE_PATH = ARGS[3]
CHILD_MODE in ("reference", "mechanism-disabled") || fail("child mode differs")
(CHILD_MODE == "reference" && length(ARGS) == 3) ||
    (CHILD_MODE == "mechanism-disabled" && length(ARGS) == 4) ||
    fail("child argument set differs from mode")
isabspath(FIXTURE_PATH) || fail("fixture path must be absolute")
isabspath(PLUGIN_SOURCE_PATH) || fail("plugin source path must be absolute")
include(PLUGIN_SOURCE_PATH)
if CHILD_MODE == "mechanism-disabled"
    isabspath(ARGS[4]) || fail("mechanism source path must be absolute")
    include(ARGS[4])
end

function closed_object(value, keys, context)
    value isa Dict{String,Any} || fail("$context must be an object")
    Set(Base.keys(value)) == Set(String.(keys)) || fail("$context is not closed")
    return value
end

function f64_bits(value)
    value isa Real && !(value isa Bool) || fail("observed numeric value is not real")
    number = Float64(value)
    return "0x" * string(reinterpret(UInt64, number); base = 16, pad = 16)
end

function observation_projection(observation::OracleObservation)
    return Dict{String,Any}(
        "relations" => Any[
            Dict{String,Any}(
                "node" => string(relation.node),
                "raw_bits" => f64_bits(relation.raw),
                "scale_bits" => f64_bits(relation.scale),
                "scaled_bits" => f64_bits(relation.scaled),
                "truth" => relation.truth,
            ) for relation in observation.relations
        ],
        "target_bits" => f64_bits(observation.target),
        "guards" => Any[
            Dict{String,Any}(
                "node" => string(guard.node),
                "margin_bits" => f64_bits(guard.margin),
                "strict" => guard.strict,
                "scale_bits" => f64_bits(guard.scale),
                "valid" => guard.valid,
            ) for guard in observation.guards
        ],
        "domains" => Any[
            Dict{String,Any}(
                "node" => string(domain.node),
                "margin_bits" => f64_bits(domain.margin),
                "strict" => domain.strict,
                "valid" => domain.valid,
            ) for domain in observation.domains
        ],
        "branch_count" => length(observation.branches),
        "status" => string(observation.status),
        "evaluation_cost" => observation.evaluation_cost,
        "diagnostic" => observation.diagnostic,
    )
end

function trace_projection(point::LocalTracePoint)
    return Dict{String,Any}(
        "iteration" => point.iteration,
        "evaluations" => point.evaluations,
        "residual_infinity_bits" => f64_bits(point.residual_infinity),
        "merit_bits" => f64_bits(point.merit),
        "damping_bits" => f64_bits(point.damping),
        "accepted_step" => point.accepted_step,
    )
end

function attempt_projection(attempt::LocalAttempt)
    return Dict{String,Any}(
        "start_bits" => Any[f64_bits(value) for value in attempt.start],
        "final_bits" => Any[f64_bits(value) for value in attempt.final],
        "status" => string(attempt.status),
        "accepted" => attempt.accepted,
        "iterations" => attempt.iterations,
        "evaluations" => attempt.evaluations,
        "numerical_rank" => attempt.numerical_rank,
        "condition_estimate_bits" => f64_bits(attempt.condition_estimate),
        "observation" => observation_projection(attempt.observation),
        "trace" => Any[trace_projection(point) for point in attempt.trace],
    )
end

function options_projection(options::LocalSolveOptions)
    return Dict{String,Any}(
        "max_iterations" => options.max_iterations,
        "max_evaluations" => options.max_evaluations,
        "residual_tolerance_bits" => f64_bits(options.residual_tolerance),
        "step_tolerance_bits" => f64_bits(options.step_tolerance),
        "finite_difference_step_bits" => f64_bits(options.finite_difference_step),
        "initial_damping_bits" => f64_bits(options.initial_damping),
        "damping_increase_bits" => f64_bits(options.damping_increase),
        "damping_decrease_bits" => f64_bits(options.damping_decrease),
    )
end

function validation_projection(validation::CandidateValidationResult)
    diagnostic = validation.diagnostic === nothing ? nothing : Dict{String,Any}(
        "failure" => string(validation.diagnostic.failure),
        "node" => validation.diagnostic.node === nothing ? nothing : string(validation.diagnostic.node),
        "message" => validation.diagnostic.message,
    )
    return Dict{String,Any}(
        "accepted" => validation.accepted,
        "failure" => string(validation.failure),
        "diagnostic" => diagnostic,
        "problem" => string(validation.problem),
        "problem_hash_method" => validation.problem_hash_method,
        "configuration" => string(validation.configuration),
        "validation_config" => string(validation.validation_config),
        "method" => validation.method,
        "precision_bits" => validation.precision_bits,
        "fast_observation" => observation_projection(validation.fast_observation),
        "canonical_observation" => observation_projection(validation.canonical_observation),
        "oracle_work" => validation.oracle_work,
        "exact_failure" => string(validation.exact_failure),
    )
end

function load_fixture(path::String)
    isabspath(path) || fail("fixture path must be absolute")
    payload = read(path)
    document = parse_protocol_json(payload)
    expected = vcat(canonical_json_bytes(document), UInt8('\n'))
    expected == payload || fail("fixture is not one exact RFC 8785 JCS line")
    fixture = closed_object(
        document,
        ("schema_version", "fixture_id", "registry", "problem", "start"),
        "fixture",
    )
    fixture["schema_version"] == FIXTURE_SCHEMA || fail("fixture schema differs")
    fixture["fixture_id"] in ("JULIA-CORE-DEFAULT", "OPAQUE-PLUGIN-DEFAULT") ||
        fail("fixture id differs")
    fixture["registry"] in ("geometry", "geometry+opaque") ||
        fail("fixture registry differs")
    fixture["start"] isa Vector{Any} || fail("fixture start must be an array")
    return fixture
end

function build_registry(fixture)
    opaque_module = Local3FixturePlugin
    allowlist = fixture["registry"] == "geometry" ?
                (GeoTargetGeometry.GEOMETRY_PLUGIN_ID,) :
                (GeoTargetGeometry.GEOMETRY_PLUGIN_ID, opaque_module.LOCAL3_PLUGIN_ID)
    builder = RegistryBuilder(; allowlist)
    register!(builder, GeoTargetGeometry.geometry_plugin())
    fixture["registry"] == "geometry+opaque" &&
        register!(builder, opaque_module.local3_fixture_plugin())
    return freeze(builder)
end

function disabled_solver()
    isdefined(Main, :GeoTargetLocalModelTransform) ||
        fail("mechanism source did not define GeoTargetLocalModelTransform")
    mechanism = GeoTargetLocalModelTransform
    isdefined(mechanism, :LOCAL_MODEL_TRANSFORM_API_VERSION) ||
        fail("mechanism API version is absent")
    getfield(mechanism, :LOCAL_MODEL_TRANSFORM_API_VERSION) == MECHANISM_API_VERSION ||
        fail("mechanism API version differs")
    isdefined(mechanism, :solve_local_variant) || fail("mechanism solver entry point is absent")
    return getfield(mechanism, :solve_local_variant)
end

function main()
    fixture = load_fixture(FIXTURE_PATH)
    registry = build_registry(fixture)
    problem = decode_problem_document(fixture["problem"], registry)
    compiled = compile_problem(problem, registry)
    start = Float64[
        value isa Real && !(value isa Bool) ? Float64(value) : fail("start is not numeric")
        for value in fixture["start"]
    ]
    length(start) == length(problem.variables) || fail("start dimension differs")
    origins = Float64[variable.origin for variable in problem.variables]
    scales = Float64[variable.scale for variable in problem.variables]
    lower = Float64[
        variable.lower === nothing ? -Inf : variable.lower for variable in problem.variables
    ]
    upper = Float64[
        variable.upper === nothing ? Inf : variable.upper for variable in problem.variables
    ]
    options = LocalSolveOptions()
    evaluate_fn = coordinates -> evaluate(compiled, coordinates; capability = C0)
    initial = evaluate_fn(start)
    common = (
        origins = origins,
        scales = scales,
        lower = lower,
        upper = upper,
        options = options,
        jacobian_entries = compiled.sparsity.jacobian_entries,
    )
    attempt = if CHILD_MODE == "reference"
        solve_local(evaluate_fn, start; common...)
    else
        solve_variant = disabled_solver()
        solve_variant(evaluate_fn, start, :L0_SEMANTIC; common...)
    end
    validation_options = CandidateValidationOptions(
        residual_tolerance = options.residual_tolerance,
        target_consistency_tolerance = options.residual_tolerance,
    )
    validation = validate_candidate(compiled, attempt; options = validation_options)
    output = Dict{String,Any}(
        "schema_version" => OBSERVATION_SCHEMA,
        "fixture_id" => fixture["fixture_id"],
        "problem_hash" => string(problem_hash(problem, registry)),
        "compiled_cache_key" => string(compiled.cache_identity.key),
        "compile_stats" => Dict{String,Any}(
            "source_nodes" => compiled.stats.source_nodes,
            "live_nodes" => compiled.stats.live_nodes,
            "dead_nodes" => compiled.stats.dead_nodes,
            "constant_folds" => compiled.stats.constant_folds,
            "cse_hits" => compiled.stats.cse_hits,
            "runtime_calls" => compiled.stats.runtime_calls,
            "logical_evaluation_cost" => compiled.logical_evaluation_cost,
        ),
        "default_options" => options_projection(options),
        "canonical_validation_tolerance_bits" => f64_bits(options.residual_tolerance),
        "initial_observation" => observation_projection(initial),
        "attempt" => attempt_projection(attempt),
        "canonical_validation" => validation_projection(validation),
    )
    write(stdout, canonical_json_bytes(output))
    write(stdout, UInt8('\n'))
    flush(stdout)
    return nothing
end

main()
