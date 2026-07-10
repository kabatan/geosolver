using GeoTargetBase
using GeoTargetCore
using GeoTargetGeometry
using JSON3
using SHA

length(ARGS) == 3 || error(
    "usage: capture_current_public_surface.jl <baseline-contract.json> <baseline-snapshot.json> <output.json>",
)

contract_path, baseline_path, output_path = abspath.(ARGS)
ispath(output_path) && error("public-surface output already exists")
contract = JSON3.read(read(contract_path, String), Dict{String,Any})
baseline = JSON3.read(read(baseline_path, String), Dict{String,Any})
contract["schema_version"] == "exp-jac-003-public-baseline-contract/v1" ||
    error("public baseline contract schema drift")
baseline["schema_version"] == "exp-jac-003-public-baseline-snapshot/v1" ||
    error("public baseline snapshot schema drift")

repository_root = normpath(joinpath(@__DIR__, "..", "..", "..", ".."))
source_root = joinpath(repository_root, "julia", "GeoTargetCore", "src")
local_source = read(joinpath(source_root, "local_solver.jl"), String)
core_source = read(joinpath(source_root, "GeoTargetCore.jl"), String)
surface = contract["public_surface"]
for token in surface["required_tokens"]
    occursin(String(token), local_source) || error("required public token missing: $token")
end
for token in surface["forbidden_tokens"]
    occursin(String(token), local_source) && error("forbidden public token present: $token")
end
occursin(r"(?m)^\s*solve_local,\s*$", core_source) || error("solve_local export drift")
:solve_local in names(GeoTargetCore) || error("solve_local is not exported")
methods_list = collect(methods(solve_local))
length(methods_list) == Int(surface["method_count"]) || error("solve_local method count drift")
direct = only(filter(method -> !occursin("ProblemSpecV1", string(method)), methods_list))
problem = only(filter(method -> occursin("ProblemSpecV1", string(method)), methods_list))
direct_keywords = String[string(name) for name in Base.kwarg_decl(direct)]
problem_keywords = String[string(name) for name in Base.kwarg_decl(problem)]
direct_keywords == String[String(value) for value in surface["direct_keyword_order"]] ||
    error("direct solve_local keyword order drift: $direct_keywords")
problem_keywords == String[String(value) for value in surface["problem_keyword_order"]] ||
    error("problem solve_local keyword order drift: $problem_keywords")
occursin("solve_local(evaluate_fn, x0::AbstractVector", string(direct)) ||
    error("direct solve_local positional surface drift")
occursin("problem::ProblemSpecV1", string(problem)) ||
    error("problem solve_local positional surface drift")
occursin("registry::FrozenPluginRegistry", string(problem)) ||
    error("problem solve_local registry surface drift")

string(SOLVE_API_VERSION) == String(contract["solve_api_version"]) || error("solve API drift")
wire = contract["wire_versions"]
String(wire["problem"]) == PROBLEM_WIRE_VERSION || error("problem wire drift")
String(wire["plugin"]) == PLUGIN_WIRE_VERSION || error("plugin wire drift")
String(wire["solve_options"]) == SOLVE_OPTIONS_WIRE_VERSION || error("options wire drift")
String(wire["solve_result"]) == SOLVE_RESULT_WIRE_VERSION || error("result wire drift")
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
    specification = ProblemSpecV1(
        (plugin_lock(plugin),),
        (variable,),
        graph;
        relations=(RelationBinding(NodeId("relation")),),
        target=NodeId("x"),
    )
    builder = RegistryBuilder(allowlist=(plugin.id,))
    register!(builder, plugin)
    return specification, freeze(builder)
end

fixture = contract["checkpoint_fixture"]
specification, registry = baseline_problem()
options = SolveOptions(
    wall_seconds=300.0,
    seed=Int(fixture["solve_seed"]),
    answer_level=:validated,
)
execution = solve_execution(
    specification,
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
encode_checkpoint_json(round_trip) == checkpoint_json || error("checkpoint round-trip drift")
checkpoint_hash(round_trip) == checkpoint_hash(artifact) || error("checkpoint identity drift")
checkpoint = Dict{String,Any}(
    "canonical_json" => checkpoint_json,
    "canonical_json_sha256" => bytes2hex(sha256(Vector{UInt8}(codeunits(checkpoint_json)))),
    "content_hash" => string(checkpoint_hash(artifact)),
    "fixed_remaining_seconds" => Float64(fixture["fixed_remaining_seconds"]),
    "fixture_id" => String(fixture["fixture_id"]),
    "round_trip_identical" => true,
)
canonical_json(checkpoint) == canonical_json(baseline["checkpoint_fixture"]) ||
    error("checkpoint fixture differs from frozen public baseline")

declared_sources = sort!(String[String(path) for path in keys(contract["product_sources"])])
actual_sources = sort!(String[
    replace(relpath(path, repository_root), '\\' => '/') for
    path in readdir(source_root; join=true) if endswith(path, ".jl")
])
declared_sources == actual_sources || error("GeoTargetCore source-set drift")
source_hashes = Dict{String,Any}(
    relative => bytes2hex(sha256(read(joinpath(repository_root, split(relative, '/')...)))) for
    relative in declared_sources
)
for relative in declared_sources
    relative == "julia/GeoTargetCore/src/local_solver.jl" && continue
    source_hashes[relative] == baseline["product_sources"][relative] ||
        error("unauthorized product source drift: $relative")
end

document = Dict{String,Any}(
    "checkpoint_fixture" => checkpoint,
    "experiment_id" => "EXP-JAC-003",
    "local_solver_sha256" => source_hashes["julia/GeoTargetCore/src/local_solver.jl"],
    "product_sources" => source_hashes,
    "public_surface" => baseline["public_surface"],
    "schema_version" => "exp-jac-003-current-public-surface/v1",
    "solve_api_version" => string(SOLVE_API_VERSION),
    "wire_versions" => baseline["wire_versions"],
)
mkpath(dirname(output_path))
temporary = string(output_path, ".tmp")
ispath(temporary) && error("public-surface temporary output exists")
open(temporary, "w") do io
    write(io, canonical_json(document))
    write(io, '\n')
    flush(io)
end
mv(temporary, output_path)
