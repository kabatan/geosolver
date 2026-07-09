module ProtocolIntegrationTests

using GeoTargetBase
using GeoTargetCore
using Test
using UUIDs

if !isdefined(GeoTargetCore, :decode_problem_json)
    Base.include(
        GeoTargetCore,
        normpath(joinpath(@__DIR__, "..", "GeoTargetCore", "src", "protocol_json.jl")),
    )
end
include(normpath(joinpath(@__DIR__, "..", "app", "GeoTargetApp.jl")))

const ROOT = normpath(joinpath(@__DIR__, "..", ".."))
const VALID = joinpath(ROOT, "schemas", "fixtures", "valid")
const INVALID = joinpath(ROOT, "schemas", "fixtures", "invalid", "cases-v1.json")
const HASHES = joinpath(ROOT, "schemas", "fixtures", "canonical-hashes-v1.json")
const FIXTURE_PLUGIN = PluginId(UUID("11111111-1111-4111-8111-111111111111"), "fixture")
const REAL = TypeId(FIXTURE_PLUGIN, "Real")
const BIG = TypeId(FIXTURE_PLUGIN, "BigFloat")
const CONTENT = ContentHash("sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa")

struct StructCodecFixture
    b::Int
    a::String
end

GeoTargetCore.StructTypes.StructType(::Type{StructCodecFixture}) = GeoTargetCore.StructTypes.Struct()

_real_decode(value) = value isa Real && !(value isa Bool) ? Float64(value) :
    throw(ArgumentError("expected a JSON number"))
_real_encode(value::Real) = Float64(value)
_big_decode(value) = value isa String ? parse(BigFloat, value) : throw(ArgumentError("expected a decimal string"))
_big_encode(value::BigFloat) = GeoTargetCore._result_number_document(value, "literal")

function _kernel(
    evaluator;
    capabilities = CapabilitySet(C0),
    smoothness = SMOOTH_C1,
    derivative_mode = DERIVATIVE_NONE,
)
    return OperatorKernel(
        evaluator;
        capabilities,
        smoothness,
        derivative_mode,
        generic_numeric = true,
        deterministic = true,
    )
end

function problem_plugin()
    real = TypeSpec(REAL, Real; encoder = _real_encode, decoder = _real_decode, documentation = "Fixture real scalar")
    big = TypeSpec(BIG, BigFloat; encoder = _big_encode, decoder = _big_decode, documentation = "BigFloat literal")
    unary = SignatureSpec((REAL,), REAL)
    binary = SignatureSpec((REAL, REAL), REAL)
    target = PrimitiveSpec(
        PrimitiveId(FIXTURE_PLUGIN, "target_value"),
        (unary,),
        _kernel(identity; capabilities = CapabilitySet(C0, C1, C2), derivative_mode = DERIVATIVE_AUTODIFF);
        documentation = "Target projection",
    )
    equal = RelationSpec(
        PrimitiveId(FIXTURE_PLUGIN, "equal"),
        (binary,),
        _kernel(-);
        truth = (left, right) -> left == right,
        scale_hint = 1,
        documentation = "Equality residual",
    )
    return PluginSpec(
        FIXTURE_PLUGIN,
        v"1.2.3",
        CORE_ABI_VERSION,
        CONTENT;
        types = (real, big),
        primitives = (target,),
        relations = (equal,),
    )
end

function manifest_plugin()
    # The fixture manifest intentionally calls its Choice-producing wire type
    # "Real". Runtime Julia types are not wire metadata, so this registry is
    # kept separate from the problem-evaluation registry.
    real = TypeSpec(
        REAL,
        Choice;
        encoder = identity,
        decoder = identity,
        documentation = "Fixture real scalar",
    )
    unary = SignatureSpec((REAL,), REAL)
    binary = SignatureSpec((REAL, REAL), REAL)
    target = PrimitiveSpec(
        PrimitiveId(FIXTURE_PLUGIN, "target_value"),
        (unary,),
        _kernel(identity; capabilities = CapabilitySet(C0, C1, C2), derivative_mode = DERIVATIVE_AUTODIFF);
        documentation = "Target projection",
    )
    equal = RelationSpec(
        PrimitiveId(FIXTURE_PLUGIN, "equal"),
        (binary,),
        _kernel((left, right) -> left);
        truth = (left, right) -> left == right,
        scale_hint = 1,
        documentation = "Equality residual",
    )
    positive = GuardSpec(
        PrimitiveId(FIXTURE_PLUGIN, "positive"),
        (unary,),
        _kernel(identity);
        default_strict = true,
        scale_hint = 1,
        documentation = "Positive margin",
    )
    defined = DomainSpec(
        PrimitiveId(FIXTURE_PLUGIN, "defined"),
        (unary,),
        _kernel(identity; smoothness = LOCALLY_LIPSCHITZ);
        singularity = identity,
        default_strict = false,
        documentation = "Domain margin",
    )
    pair = BranchSpec(
        PrimitiveId(FIXTURE_PLUGIN, "pair"),
        (unary,),
        REAL,
        _kernel(identity; smoothness = PIECEWISE_SMOOTH);
        documentation = "Two candidates",
    )
    near = SelectorSpec(
        SelectorId(FIXTURE_PLUGIN, "near"),
        (binary,),
        _kernel(identity; smoothness = PIECEWISE_SMOOTH);
        documentation = "Nearest candidate selector",
    )
    return PluginSpec(
        FIXTURE_PLUGIN,
        v"1.2.3",
        CORE_ABI_VERSION,
        CONTENT;
        types = (real,),
        primitives = (target,),
        relations = (equal,),
        guards = (positive,),
        domains = (defined,),
        branches = (pair,),
        selectors = (near,),
    )
end

function _registry(plugin)
    builder = RegistryBuilder(allowlist = (plugin.id,))
    register!(builder, plugin)
    return freeze(builder)
end

const PROBLEM_REGISTRY = _registry(problem_plugin())
const MANIFEST_REGISTRY = _registry(manifest_plugin())

_fixture(name) = read(joinpath(VALID, basename(name)), String)

function _replace_pointer!(document, pointer::String, value)
    components = split(pointer, '/')[2:end]
    components = replace.(components, "~1" => "/", "~0" => "~")
    parent = document
    for component in components[1:(end - 1)]
        parent = parent isa Vector ? parent[parse(Int, component) + 1] : parent[component]
    end
    final = components[end]
    if parent isa Vector
        parent[parse(Int, final) + 1] = deepcopy(value)
    else
        parent[final] = deepcopy(value)
    end
    return document
end

function _decode_owned(document, registry)
    version = document["schema_version"]
    source = GeoTargetCore.canonical_json(document)
    if version == GeoTargetCore.PROBLEM_WIRE_VERSION
        return GeoTargetCore.decode_problem_json(source, registry)
    elseif version == GeoTargetCore.PLUGIN_WIRE_VERSION
        return GeoTargetCore.decode_plugin_manifest_json(source, registry)
    elseif version == GeoTargetCore.SOLVE_RESULT_WIRE_VERSION
        return GeoTargetCore.decode_solve_result_json(source)
    end
    error("not an owned fixture")
end

@testset "RFC 8785 common fixtures" begin
    manifest = GeoTargetCore.parse_protocol_json(read(HASHES, String))
    for (name, expected) in manifest["fixtures"]
        document = GeoTargetCore.parse_protocol_json(_fixture(name))
        @test string(GeoTargetCore.canonical_json_hash(document)) == expected
        canonical = GeoTargetCore.canonical_json(document)
        @test GeoTargetCore.canonical_json(GeoTargetCore.parse_protocol_json(canonical)) == canonical
    end

    problem_source = _fixture("problem-open-world-v1.json")
    problem = GeoTargetCore.decode_problem_json(problem_source, PROBLEM_REGISTRY)
    @test GeoTargetCore.encode_problem_json(problem, PROBLEM_REGISTRY) ==
        GeoTargetCore.canonical_json(GeoTargetCore.parse_protocol_json(problem_source))
    @test string(GeoTargetCore.problem_hash(problem, PROBLEM_REGISTRY)) ==
        manifest["fixtures"]["valid/problem-open-world-v1.json"]

    result_source = _fixture("solve-result-combined-v1.json")
    result = GeoTargetCore.decode_solve_result_json(result_source)
    @test GeoTargetCore.encode_solve_result_json(result) ==
        GeoTargetCore.canonical_json(GeoTargetCore.parse_protocol_json(result_source))
    @test string(result.environment_lock.graph) ==
        "sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"

    plugin_source = _fixture("plugin-manifest-full-v1.json")
    plugin = GeoTargetCore.decode_plugin_manifest_json(plugin_source, MANIFEST_REGISTRY)
    @test plugin === only(registered_plugins(MANIFEST_REGISTRY))
    @test GeoTargetCore.encode_plugin_manifest_json(plugin) ==
        GeoTargetCore.canonical_json(GeoTargetCore.parse_protocol_json(plugin_source))
end

@testset "Invalid common-fixture mutations are rejected" begin
    cases = GeoTargetCore.parse_protocol_json(read(INVALID, String))["cases"]
    for case in cases
        base = GeoTargetCore.parse_protocol_json(read(joinpath(ROOT, "schemas", "fixtures", case["base"]), String))
        base["schema_version"] == "geotarget.solve-options/v1" && continue
        for patch in case["patch"]
            @test patch["op"] == "replace"
            _replace_pointer!(base, patch["path"], patch["value"])
        end
        registry = base["schema_version"] == GeoTargetCore.PLUGIN_WIRE_VERSION ? MANIFEST_REGISTRY : PROBLEM_REGISTRY
        @test_throws GeoTargetCore.ProtocolJsonError _decode_owned(base, registry)
    end

    duplicate = "{\"schema_version\":\"geotarget.problem/v1\",\"schema_version\":\"geotarget.problem/v1\"}"
    @test_throws GeoTargetCore.ProtocolJsonError GeoTargetCore.parse_protocol_json(duplicate)
    @test_throws GeoTargetCore.ProtocolJsonError GeoTargetCore.canonical_json(Dict("x" => 1e30))
end

@testset "Binary artifacts and literal codecs" begin
    @test GeoTargetCore.canonical_json(StructCodecFixture(2, "x")) == "{\"a\":\"x\",\"b\":2}"
    payload = UInt8[0x00, 0xff, 0x80, 0x01]
    artifact = CertificateArtifact("binary_fixture", payload)
    document = GeoTargetCore._artifact_document(artifact)
    decoded = GeoTargetCore._decode_artifact(document, "artifact")
    @test collect(codeunits(decoded.payload)) == payload
    @test decoded.digest == artifact.digest

    graph = ConstructionGraph((
        LiteralNode(NodeId("float_literal"), REAL, 1.5),
        LiteralNode(NodeId("big_literal"), BIG, parse(BigFloat, "1.25")),
    ))
    problem = ProblemSpecV1(
        (plugin_lock(problem_plugin()),),
        (),
        graph;
        target = NodeId("big_literal"),
    )
    encoded = GeoTargetCore.encode_problem_json(problem, PROBLEM_REGISTRY)
    decoded_problem = GeoTargetCore.decode_problem_json(encoded, PROBLEM_REGISTRY)
    @test decoded_problem.graph[1].value isa Float64
    @test decoded_problem.graph[1].value == 1.5
    @test decoded_problem.graph[2].value isa BigFloat
    @test decoded_problem.graph[2].value == parse(BigFloat, "1.25")
    @test GeoTargetCore.encode_problem_json(decoded_problem, PROBLEM_REGISTRY) == encoded
end

@testset "CLI composition without solve" begin
    mktempdir() do directory
        fixture_path = joinpath(directory, "fixture.json")
        write(fixture_path, _fixture("problem-open-world-v1.json"))
        output = IOBuffer()
        errors = IOBuffer()
        @test GeoTargetApp.main(
            ["validate", fixture_path];
            registry = PROBLEM_REGISTRY,
            stdout = output,
            stderr = errors,
        ) == 0
        summary = GeoTargetCore.parse_protocol_json(String(take!(output)))
        @test summary["content_hash"] == "sha256:9634841e589f901c7409dcb5ac106e5c83dce619694f6293ea52dc1b1b0db979"

        output = IOBuffer()
        @test GeoTargetApp.main(
            ["plugin-info", string(FIXTURE_PLUGIN)];
            registry = MANIFEST_REGISTRY,
            stdout = output,
            stderr = errors,
        ) == 0
        @test strip(String(take!(output))) == GeoTargetCore.encode_plugin_manifest_json(manifest_plugin())

        variable = VariableSpec(VariableId("x"), REAL, 0.0, 1.0)
        evaluable = ProblemSpecV1(
            (plugin_lock(problem_plugin()),),
            (variable,),
            ConstructionGraph((
                ReferenceNode(NodeId("x_ref"), variable.id),
                CallNode(
                    NodeId("target"),
                    PrimitiveId(FIXTURE_PLUGIN, "target_value"),
                    (NodeId("x_ref"),),
                ),
            ));
            target = NodeId("target"),
        )
        eval_path = joinpath(directory, "eval.json")
        write(eval_path, GeoTargetCore.encode_problem_json(evaluable, PROBLEM_REGISTRY))
        output = IOBuffer()
        @test GeoTargetApp.main(
            ["eval", eval_path, "--x", "2.5"];
            registry = PROBLEM_REGISTRY,
            stdout = output,
            stderr = errors,
        ) == 0
        observation = GeoTargetCore.parse_protocol_json(String(take!(output)))
        @test observation["status"] == "ok"
        @test observation["target"] == "2.5"

        @test GeoTargetApp.main(
            ["solve", eval_path];
            registry = PROBLEM_REGISTRY,
            stdout = IOBuffer(),
            stderr = IOBuffer(),
        ) == 2
    end
end

end
