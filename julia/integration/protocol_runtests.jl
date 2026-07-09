module ProtocolIntegrationTests

using GeoTargetBase
using GeoTargetCore
using GeoTargetGeometry
using Test
using UUIDs

include(normpath(joinpath(@__DIR__, "..", "app", "GeoTargetApp.jl")))

const ROOT = normpath(joinpath(@__DIR__, "..", ".."))
const VALID = joinpath(ROOT, "schemas", "fixtures", "valid")
const INVALID = joinpath(ROOT, "schemas", "fixtures", "invalid", "cases-v1.json")
const HASHES = joinpath(ROOT, "schemas", "fixtures", "canonical-hashes-v1.json")
const JCS_BINARY64_CORPUS =
    joinpath(@__DIR__, "fixtures", "jcs-binary64-random-v1.tsv")
const JCS_BINARY64_CORPUS_HASH =
    "sha256:983ea9412bc8db8bd84100391970ce5e557bc84d18132530c22140e8d8b0ece0"
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

function _geometry_codec_registry()
    plugin = geometry_plugin()
    builder = RegistryBuilder(allowlist = (plugin.id,))
    register!(builder, plugin)
    return freeze(builder)
end

function _geometry_codec_problem()
    plugin = geometry_plugin()
    big_value = setprecision(BigFloat, 192) do
        parse(BigFloat, "0.1")
    end
    nodes = (
        LiteralNode(NodeId("safe_int"), SCALAR_TYPE_ID, Int64(7)),
        LiteralNode(NodeId("small_float"), SCALAR_TYPE_ID, 0.25),
        LiteralNode(NodeId("negative_zero"), SCALAR_TYPE_ID, -0.0),
        LiteralNode(NodeId("float16"), SCALAR_TYPE_ID, Float16(0.1)),
        LiteralNode(NodeId("float32"), SCALAR_TYPE_ID, Float32(0.1)),
        LiteralNode(NodeId("bigfloat"), SCALAR_TYPE_ID, big_value),
        LiteralNode(NodeId("integer"), SCALAR_TYPE_ID, Int128(2)^100),
        LiteralNode(NodeId("bigint"), SCALAR_TYPE_ID, big(2)^200),
        LiteralNode(
            NodeId("rational"),
            SCALAR_TYPE_ID,
            Int16(5) // Int16(7),
        ),
        LiteralNode(NodeId("point"), POINT_TYPE_ID, point2(1.0, 2.0)),
        LiteralNode(
            NodeId("line"),
            LINE_TYPE_ID,
            line_through(
                point2(Float32(1), Float32(2)),
                point2(Float32(3), Float32(5)),
            ),
        ),
        LiteralNode(
            NodeId("circle"),
            CIRCLE_TYPE_ID,
            circle2(
                point2(Int16(1) // Int16(3), Int16(2) // Int16(5)),
                Int16(7) // Int16(11),
            ),
        ),
    )
    return ProblemSpecV1(
        (plugin_lock(plugin),),
        (),
        ConstructionGraph(nodes);
        target = NodeId("safe_int"),
    )
end

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

@testset "built-in geometry literals round-trip through the owned protocol" begin
    registry = _geometry_codec_registry()
    problem = _geometry_codec_problem()
    source = GeoTargetCore.encode_problem_json(problem, registry)
    document = GeoTargetCore.parse_protocol_json(source)
    projections = Dict(
        node["id"] => node["value"] for node in document["graph"] if
        node["kind"] == "literal"
    )

    @test projections["safe_int"] == 7
    @test projections["small_float"] == 0.25
    @test projections["negative_zero"]["type"] == "Float64"
    @test projections["float16"]["type"] == "Float16"
    @test projections["float32"]["bits"] == "3dcccccd"
    @test projections["bigfloat"]["precision_bits"] == 192
    @test projections["integer"]["type"] == "Int128"
    @test projections["bigint"]["type"] == "BigInt"
    @test projections["rational"]["type"] == "Int16"
    @test projections["point"]["numeric_type"] == "Float64"
    @test projections["line"]["direction"]["numeric_type"] == "Float32"
    @test projections["circle"]["center"]["numeric_type"] == "Rational{Int16}"

    decoded = GeoTargetCore.decode_problem_json(source, registry)
    @test GeoTargetCore.encode_problem_json(decoded, registry) == source
    @test GeoTargetCore.problem_hash(decoded, registry) ==
          GeoTargetCore.problem_hash(problem, registry)
    @test GeoTargetCore.problem_hash(problem, registry) ==
          GeoTargetCore.canonical_json_hash(document)

    values = Dict(
        string(node.id) => node.value for node in decoded.graph.nodes if
        node isa LiteralNode
    )
    @test typeof(values["negative_zero"]) === Float64
    @test signbit(values["negative_zero"])
    @test typeof(values["float16"]) === Float16
    @test typeof(values["float32"]) === Float32
    @test typeof(values["bigfloat"]) === BigFloat
    @test precision(values["bigfloat"]) == 192
    @test typeof(values["integer"]) === Int128
    @test typeof(values["bigint"]) === BigInt
    @test typeof(values["rational"]) === Rational{Int16}
    @test typeof(values["point"]) === Point2{Float64}
    @test typeof(values["line"]) === Line2{Float32}
    @test typeof(values["circle"]) === Circle2{Rational{Int16}}
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
end

@testset "RFC 8785 binary64 boundary vectors" begin
    vectors = (
        (0x0000000000000000, "0"),
        (0x8000000000000000, "0"),
        (0x0000000000000001, "5e-324"),
        (0x8000000000000001, "-5e-324"),
        (0x7fefffffffffffff, "1.7976931348623157e+308"),
        (0xffefffffffffffff, "-1.7976931348623157e+308"),
        (0x433fffffffffffff, "9007199254740991"),
        (0x4340000000000000, "9007199254740992"),
        (0xc340000000000000, "-9007199254740992"),
        (0x4430000000000000, "295147905179352830000"),
        (0x44b52d02c7e14af5, "9.999999999999997e+22"),
        (0x44b52d02c7e14af6, "1e+23"),
        (0x44b52d02c7e14af7, "1.0000000000000001e+23"),
        (0x444b1ae4d6e2ef4e, "999999999999999700000"),
        (0x444b1ae4d6e2ef4f, "999999999999999900000"),
        (0x444b1ae4d6e2ef50, "1e+21"),
        (0x444b1ae4d6e2ef51, "1.0000000000000001e+21"),
        (0x3eb0c6f7a0b5ed8c, "9.999999999999997e-7"),
        (0x3eb0c6f7a0b5ed8d, "0.000001"),
        (0x3eb0c6f7a0b5ed8e, "0.0000010000000000000002"),
        (0x41b3de4355555553, "333333333.3333332"),
        (0x41b3de4355555554, "333333333.33333325"),
        (0x41b3de4355555555, "333333333.3333333"),
        (0x41b3de4355555556, "333333333.3333334"),
        (0x41b3de4355555557, "333333333.33333343"),
        (0xbecbf647612f3696, "-0.0000033333333333333333"),
        (0x43143ff3c1cb0959, "1424953923781206.2"),
        (0x46293e5939a08cea, "1e+30"),
        (0x3a53ce9a36f23c10, "1e-27"),
    )
    for (bits, expected) in vectors
        value = reinterpret(Float64, UInt64(bits))
        @test GeoTargetCore.canonical_json(value) == expected
    end

    @test GeoTargetCore.canonical_json(9_007_199_254_740_991) == "9007199254740991"
    @test_throws GeoTargetCore.ProtocolJsonError GeoTargetCore.canonical_json(9_007_199_254_740_992)
    @test GeoTargetCore.canonical_json(-9_007_199_254_740_991) == "-9007199254740991"
    @test_throws GeoTargetCore.ProtocolJsonError GeoTargetCore.canonical_json(-9_007_199_254_740_992)
    @test GeoTargetCore.canonical_json(Float64(9_007_199_254_740_992)) == "9007199254740992"
    @test GeoTargetCore.canonical_json(1.0e20) == "100000000000000000000"
    @test GeoTargetCore.canonical_json(1.0e-7) == "1e-7"
    @test GeoTargetCore.canonical_json(1.0e30) == "1e+30"
    @test GeoTargetCore.canonical_json(Float32(0.1)) == "0.10000000149011612"
    for value in (NaN, Inf, -Inf)
        @test_throws GeoTargetCore.ProtocolJsonError GeoTargetCore.canonical_json(value)
    end
    @test_throws GeoTargetCore.ProtocolJsonError GeoTargetCore.canonical_json(big"1.25")
    @test_throws GeoTargetCore.ProtocolJsonError GeoTargetCore.canonical_json(big"0.0")
end

@testset "Python rfc8785 fixed-seed binary64 differential corpus" begin
    bytes = read(JCS_BINARY64_CORPUS)
    @test string(content_hash(bytes)) == JCS_BINARY64_CORPUS_HASH
    lines = readlines(IOBuffer(bytes))
    @test lines[1:5] == [
        "# format=geotarget-jcs-binary64-v1",
        "# oracle=rfc8785==0.1.4",
        "# generator=splitmix64",
        "# seed=0x6a09e667f3bcc909",
        "# finite_count=10000",
    ]
    entries = lines[6:end]
    @test length(entries) == 10_000
    for entry in entries
        hexadecimal, expected = split(entry, '\t'; limit = 2)
        bits = parse(UInt64, hexadecimal; base = 16)
        value = reinterpret(Float64, bits)
        @test isfinite(value)
        @test GeoTargetCore.canonical_json(value) == expected
    end
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
