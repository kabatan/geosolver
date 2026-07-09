using GeoTargetBase
using GeoTargetCore
using GeoTargetGeometry
using Printf

if !isdefined(GeoTargetCore, :CompiledProblem)
    Base.include(
        GeoTargetCore,
        joinpath(@__DIR__, "..", "..", "..", "julia", "GeoTargetCore", "src", "compiler.jl"),
    )
    Base.include(
        GeoTargetCore,
        joinpath(
            @__DIR__,
            "..",
            "..",
            "..",
            "julia",
            "GeoTargetCore",
            "src",
            "compiled_oracle.jl",
        ),
    )
end

function benchmark_registry()
    plugin = geometry_plugin()
    builder = RegistryBuilder(allowlist = (plugin.id,))
    register!(builder, plugin)
    return freeze(builder)
end

function benchmark_problem()
    plugin = geometry_plugin()
    x = VariableSpec(
        VariableId("x"),
        SCALAR_TYPE_ID,
        0.5,
        1.0;
        lower = -2.0,
        upper = 2.0,
    )
    y = VariableSpec(
        VariableId("y"),
        SCALAR_TYPE_ID,
        0.25,
        1.0;
        lower = -2.0,
        upper = 2.0,
    )
    geometry = GEOMETRY_PLUGIN_ID
    graph = ConstructionGraph((
        ReferenceNode(NodeId("x_ref"), x.id),
        ReferenceNode(NodeId("y_ref"), y.id),
        LiteralNode(NodeId("zero"), SCALAR_TYPE_ID, 0.0),
        LiteralNode(NodeId("one"), SCALAR_TYPE_ID, 1.0),
        CallNode(
            NodeId("point"),
            PrimitiveId(geometry, "point2"),
            (NodeId("x_ref"), NodeId("y_ref")),
        ),
        CallNode(
            NodeId("origin"),
            PrimitiveId(geometry, "point2"),
            (NodeId("zero"), NodeId("zero")),
        ),
        CallNode(
            NodeId("line"),
            PrimitiveId(geometry, "line_through"),
            (NodeId("origin"), NodeId("point")),
        ),
        CallNode(
            NodeId("target"),
            PrimitiveId(geometry, "distance"),
            (NodeId("point"), NodeId("origin")),
        ),
        CallNode(
            NodeId("relation"),
            PrimitiveId(geometry, "scalar_equality"),
            (NodeId("target"), NodeId("one")),
        ),
        CallNode(
            NodeId("guard"),
            PrimitiveId(geometry, "positive"),
            (NodeId("x_ref"),),
        ),
        CallNode(
            NodeId("domain"),
            PrimitiveId(geometry, "safe_geometry_domain"),
            (NodeId("line"),),
        ),
    ))
    return ProblemSpecV1(
        (plugin_lock(plugin),),
        (x, y),
        graph;
        relations = (RelationBinding(NodeId("relation")),),
        guards = (GuardBinding(NodeId("guard"), true),),
        domains = (DomainBinding(NodeId("domain"), true),),
        target = NodeId("target"),
    )
end

function run_scalar(function_, samples)
    checksum = 0.0
    for _ in 1:samples
        observation = function_()
        checksum += Float64(observation.target)
    end
    return checksum
end

function run_batch(function_, repetitions)
    checksum = 0.0
    for _ in 1:repetitions
        observations = function_()
        for observation in observations
            checksum += Float64(observation.target)
        end
    end
    return checksum
end

function report_measurement(label, runner, evaluations)
    runner() # Compile this benchmark path before recording warm economics.
    GC.gc()
    elapsed = @elapsed checksum = runner()
    GC.gc()
    allocated = @allocated runner()
    @printf(
        "%-24s seconds=%10.6f ns/eval=%12.1f bytes/eval=%12.1f checksum=%.8f\n",
        label,
        elapsed,
        1.0e9 * elapsed / evaluations,
        allocated / evaluations,
        checksum,
    )
    return nothing
end

function parse_samples(arguments)
    samples = isempty(arguments) ? 1_000 : parse(Int, only(arguments))
    samples > 0 || throw(ArgumentError("sample count must be positive"))
    return samples
end

function main(arguments = ARGS)
    samples = parse_samples(arguments)
    registry = benchmark_registry()
    problem = benchmark_problem()

    GC.gc()
    compilation = @timed GeoTargetCore.compile_problem(problem, registry)
    compiled = compilation.value
    workspace = GeoTargetCore.CompiledWorkspace(compiled)
    point = [0.75, 0.5]

    reference = evaluate_reference(problem, registry, point)
    observed = GeoTargetCore.evaluate(compiled, point; workspace)
    (reference.status, reference.target, reference.evaluation_cost) ==
        (observed.status, observed.target, observed.evaluation_cost) ||
        error("compiled/reference semantic mismatch before measurement")

    batch_rows = min(samples, 256)
    repetitions = cld(samples, batch_rows)
    points = Matrix{Float64}(undef, batch_rows, 2)
    for row in axes(points, 1)
        points[row, 1] = 0.25 + row / (2 * batch_rows)
        points[row, 2] = 0.125 + row / (4 * batch_rows)
    end
    batch_evaluations = batch_rows * repetitions

    reference_scalar = () -> evaluate_reference(problem, registry, point)
    compiled_scalar = () -> GeoTargetCore.evaluate(compiled, point; workspace)
    reference_batch = () -> [
        evaluate_reference(problem, registry, view(points, row, :)) for
        row in axes(points, 1)
    ]
    compiled_batch = () -> GeoTargetCore.evaluate_batch(compiled, points; workspace)

    println("EXP-COMP-001 typed-plan control")
    println("julia_version=$(VERSION)")
    println("samples=$samples batch_rows=$batch_rows batch_repetitions=$repetitions")
    @printf(
        "compile                  seconds=%10.6f bytes=%d live=%d dead=%d folds=%d cse=%d\n",
        compilation.time,
        compilation.bytes,
        compiled.stats.live_nodes,
        compiled.stats.dead_nodes,
        compiled.stats.constant_folds,
        compiled.stats.cse_hits,
    )
    report_measurement(
        "reference scalar",
        () -> run_scalar(reference_scalar, samples),
        samples,
    )
    report_measurement(
        "compiled scalar",
        () -> run_scalar(compiled_scalar, samples),
        samples,
    )
    report_measurement(
        "reference batch API",
        () -> run_batch(reference_batch, repetitions),
        batch_evaluations,
    )
    report_measurement(
        "compiled batch API",
        () -> run_batch(compiled_batch, repetitions),
        batch_evaluations,
    )
    return nothing
end

main()
