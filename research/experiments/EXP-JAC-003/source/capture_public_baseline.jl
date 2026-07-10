using GeoTargetBase
using GeoTargetCore
using GeoTargetGeometry
using JSON3
using SHA

length(ARGS) == 2 || error(
    "usage: capture_public_baseline.jl <baseline-contract.json> <output.json>",
)

const CONTRACT_PATH = abspath(ARGS[1])
const OUTPUT_PATH = abspath(ARGS[2])
const REPOSITORY_ROOT = normpath(joinpath(@__DIR__, "..", "..", "..", ".."))

isfile(CONTRACT_PATH) || error("baseline contract does not exist")
ispath(OUTPUT_PATH) && error("baseline output already exists; capture is one-shot")

contract = JSON3.read(read(CONTRACT_PATH, String), Dict{String,Any})
contract["schema_version"] == "exp-jac-003-public-baseline-contract/v1" ||
    error("wrong baseline contract schema")

function source_sha256(path::AbstractString)
    return bytes2hex(sha256(read(path)))
end

declared_sources = Dict{String,String}(
    String(path) => String(value) for
    (path, value) in contract["product_sources"]
)
source_root = joinpath(REPOSITORY_ROOT, "julia", "GeoTargetCore", "src")
actual_source_paths = sort!(String[
    replace(relpath(path, REPOSITORY_ROOT), '\\' => '/') for
    path in readdir(source_root; join=true) if endswith(path, ".jl")
])
sort!(collect(keys(declared_sources))) == actual_source_paths ||
    error("GeoTargetCore product source set differs from the frozen baseline")
for (relative, expected) in declared_sources
    actual = source_sha256(joinpath(REPOSITORY_ROOT, split(relative, '/')...))
    actual == expected || error("product source hash drift: $relative")
end

surface = contract["public_surface"]
local_source = read(joinpath(source_root, "local_solver.jl"), String)
core_source = read(joinpath(source_root, "GeoTargetCore.jl"), String)
for token in surface["required_tokens"]
    occursin(String(token), local_source) || error("required solve_local token missing: $token")
end
for token in surface["forbidden_tokens"]
    occursin(String(token), local_source) && error("forbidden solve_local token present: $token")
end
occursin(r"(?m)^\s*solve_local,\s*$", core_source) ||
    error("solve_local is not present in the GeoTargetCore export list")
:solve_local in names(GeoTargetCore) || error("solve_local is not publicly exported")
length(methods(solve_local)) == Int(surface["method_count"]) ||
    error("solve_local method count drift")

string(SOLVE_API_VERSION) == String(contract["solve_api_version"]) ||
    error("SOLVE_API_VERSION drift")
wire = contract["wire_versions"]
String(wire["problem"]) == PROBLEM_WIRE_VERSION || error("problem wire drift")
String(wire["plugin"]) == PLUGIN_WIRE_VERSION || error("plugin wire drift")
String(wire["solve_options"]) == SOLVE_OPTIONS_WIRE_VERSION || error("solve-options wire drift")
String(wire["solve_result"]) == SOLVE_RESULT_WIRE_VERSION || error("solve-result wire drift")
String(wire["checkpoint"]) == CHECKPOINT_WIRE_VERSION || error("checkpoint wire drift")

function baseline_problem()
    plugin = geometry_plugin()
    variable = VariableSpec(
        VariableId("x"),
        SCALAR_TYPE_ID,
        0.0,
        1.0;
        lower=-2.0,
        upper=2.0,
    )
    graph = ConstructionGraph((
        ReferenceNode(NodeId("x"), variable.id),
        LiteralNode(NodeId("root"), SCALAR_TYPE_ID, 1.0),
        CallNode(
            NodeId("relation"),
            PrimitiveId(plugin.id, "scalar_equality"),
            (NodeId("x"), NodeId("root")),
        ),
    ))
    problem = ProblemSpecV1(
        (plugin_lock(plugin),),
        (variable,),
        graph;
        relations=(RelationBinding(NodeId("relation")),),
        target=NodeId("x"),
    )
    builder = RegistryBuilder(allowlist=(plugin.id,))
    register!(builder, plugin)
    return problem, freeze(builder)
end

fixture = contract["checkpoint_fixture"]
problem, registry = baseline_problem()
options = SolveOptions(
    wall_seconds=300.0,
    seed=Int(fixture["solve_seed"]),
    answer_level=:validated,
)
execution = solve_execution(
    problem,
    registry;
    options,
    max_actions=Int(fixture["max_actions"]),
)
snapshot = execution.checkpoint
fixed_snapshot = GeoTargetCore.CheckpointSnapshot(
    snapshot.resume_identity,
    snapshot.policy_version,
    snapshot.budget,
    snapshot.workspace,
    snapshot.events,
    snapshot.rng_state,
    snapshot.precision_bits,
    Float64(fixture["fixed_remaining_seconds"]),
    snapshot.cancelled,
)
artifact = SolveCheckpointArtifact(fixed_snapshot, execution.result.target_image_status)
checkpoint_json = encode_checkpoint_json(artifact)
round_trip = decode_checkpoint_json(checkpoint_json)
encode_checkpoint_json(round_trip) == checkpoint_json ||
    error("fixed checkpoint fixture is not byte-stable after round trip")
checkpoint_hash(round_trip) == checkpoint_hash(artifact) ||
    error("fixed checkpoint identity changed after round trip")

document = Dict{String,Any}(
    "schema_version" => "exp-jac-003-public-baseline-snapshot/v1",
    "experiment_id" => "EXP-JAC-003",
    "baseline_commit" => String(contract["baseline_commit"]),
    "contract_sha256" => source_sha256(CONTRACT_PATH),
    "product_sources" => Dict(
        path => source_sha256(joinpath(REPOSITORY_ROOT, split(path, '/')...)) for
        path in sort!(collect(keys(declared_sources)))
    ),
    "public_surface" => Dict(
        "exported_name" => String(surface["exported_name"]),
        "exported" => true,
        "method_count" => length(methods(solve_local)),
        "direct_positional" => surface["direct_positional"],
        "direct_keyword_order" => surface["direct_keyword_order"],
        "problem_positional" => surface["problem_positional"],
        "problem_keyword_order" => surface["problem_keyword_order"],
        "forbidden_tokens_absent" => true,
    ),
    "solve_api_version" => string(SOLVE_API_VERSION),
    "wire_versions" => Dict(
        "problem" => PROBLEM_WIRE_VERSION,
        "plugin" => PLUGIN_WIRE_VERSION,
        "solve_options" => SOLVE_OPTIONS_WIRE_VERSION,
        "solve_result" => SOLVE_RESULT_WIRE_VERSION,
        "checkpoint" => CHECKPOINT_WIRE_VERSION,
    ),
    "checkpoint_fixture" => Dict(
        "fixture_id" => String(fixture["fixture_id"]),
        "content_hash" => string(checkpoint_hash(artifact)),
        "canonical_json_sha256" => bytes2hex(sha256(Vector{UInt8}(codeunits(checkpoint_json)))),
        "canonical_json" => checkpoint_json,
        "round_trip_identical" => true,
        "fixed_remaining_seconds" => Float64(fixture["fixed_remaining_seconds"]),
    ),
)

mkpath(dirname(OUTPUT_PATH))
temporary = string(OUTPUT_PATH, ".tmp-", getpid())
try
    open(temporary, "w") do io
        write(io, canonical_json(document))
        write(io, '\n')
    end
    ispath(OUTPUT_PATH) && error("baseline output appeared during capture")
    Base.Filesystem.rename(temporary, OUTPUT_PATH)
finally
    isfile(temporary) && rm(temporary; force=true)
end
println("captured JAC003 public baseline at ", OUTPUT_PATH)
