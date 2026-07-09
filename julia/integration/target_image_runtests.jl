using GeoTargetBase
using GeoTargetCore
using GeoTargetGeometry
using Test

if !isdefined(GeoTargetCore, :TargetImageDiagnostic)
    Base.include(
        GeoTargetCore,
        joinpath(@__DIR__, "..", "GeoTargetCore", "src", "target_image.jl"),
    )
end

const TARGET_IMAGE_FIXTURE_PLUGIN =
    parse(PluginId, "b13a1ef0-b636-4713-b527-53367b86e46f/target_image_fixture")

_target_identity(value::Real) = value
_target_square(value::Real) = value * value
_target_sum(first::Real, second::Real) = first + second
_zero_residual(value::Real) = value
_sum_zero_residual(first::Real, second::Real) = first + second
_tiny_zero_residual(value::Real) = 1.0e-8 * value
_domain_margin(value::Real) = value

function _sign_choice(value::Real)
    key = value < zero(value) ? "negative" : value > zero(value) ? "positive" : "zero"
    return Choice((value,), (key,), (one(value),))
end

_stable_choice(value::Real) = Choice((value,), ("stable",), (one(value),))
_select_first(choice::Choice) = Selection(choice, 1, one(choice.validity_margins[1]))
_select_tied(choice::Choice) = Selection(choice, 1, zero(choice.validity_margins[1]))

function target_image_fixture_plugin()
    scalar_one = SignatureSpec((SCALAR_TYPE_ID,), SCALAR_TYPE_ID)
    scalar_two = SignatureSpec((SCALAR_TYPE_ID, SCALAR_TYPE_ID), SCALAR_TYPE_ID)
    choice_signature = SignatureSpec((SCALAR_TYPE_ID,), CHOICE_TYPE_ID)
    selector_signature = SignatureSpec((CHOICE_TYPE_ID,), SCALAR_TYPE_ID)
    generic_kernel(evaluator) = OperatorKernel(
        evaluator;
        capabilities = CapabilitySet(C0, C2),
        generic_numeric = true,
        smoothness = SMOOTH_C1,
    )
    primitives = (
        PrimitiveSpec(
            PrimitiveId(TARGET_IMAGE_FIXTURE_PLUGIN, "identity"),
            (scalar_one,),
            generic_kernel(_target_identity),
        ),
        PrimitiveSpec(
            PrimitiveId(TARGET_IMAGE_FIXTURE_PLUGIN, "square"),
            (scalar_one,),
            generic_kernel(_target_square),
        ),
        PrimitiveSpec(
            PrimitiveId(TARGET_IMAGE_FIXTURE_PLUGIN, "sum"),
            (scalar_two,),
            generic_kernel(_target_sum),
        ),
        PrimitiveSpec(
            PrimitiveId(TARGET_IMAGE_FIXTURE_PLUGIN, "c0_only"),
            (scalar_one,),
            OperatorKernel(
                value -> Float64(value);
                capabilities = CapabilitySet(C0),
                smoothness = SMOOTH_C1,
            ),
        ),
    )
    relations = (
        RelationSpec(
            PrimitiveId(TARGET_IMAGE_FIXTURE_PLUGIN, "zero"),
            (scalar_one,),
            generic_kernel(_zero_residual);
            truth = value -> iszero(value),
            scale_hint = 1.0,
        ),
        RelationSpec(
            PrimitiveId(TARGET_IMAGE_FIXTURE_PLUGIN, "sum_zero"),
            (scalar_two,),
            generic_kernel(_sum_zero_residual);
            truth = (first, second) -> iszero(first + second),
            scale_hint = 1.0,
        ),
        RelationSpec(
            PrimitiveId(TARGET_IMAGE_FIXTURE_PLUGIN, "tiny_zero"),
            (scalar_one,),
            generic_kernel(_tiny_zero_residual);
            truth = value -> iszero(value),
            scale_hint = 1.0,
        ),
    )
    domain = DomainSpec(
        PrimitiveId(TARGET_IMAGE_FIXTURE_PLUGIN, "domain"),
        (scalar_one,),
        generic_kernel(_domain_margin);
        default_strict = true,
    )
    branches = (
        BranchSpec(
            PrimitiveId(TARGET_IMAGE_FIXTURE_PLUGIN, "sign_choice"),
            (choice_signature,),
            SCALAR_TYPE_ID,
            generic_kernel(_sign_choice),
        ),
        BranchSpec(
            PrimitiveId(TARGET_IMAGE_FIXTURE_PLUGIN, "stable_choice"),
            (choice_signature,),
            SCALAR_TYPE_ID,
            generic_kernel(_stable_choice),
        ),
    )
    selectors = (
        SelectorSpec(
            SelectorId(TARGET_IMAGE_FIXTURE_PLUGIN, "first"),
            (selector_signature,),
            generic_kernel(_select_first),
        ),
        SelectorSpec(
            SelectorId(TARGET_IMAGE_FIXTURE_PLUGIN, "tied"),
            (selector_signature,),
            generic_kernel(_select_tied),
        ),
    )
    return PluginSpec(
        TARGET_IMAGE_FIXTURE_PLUGIN,
        v"0.1.0",
        GeoTargetCore.CORE_ABI_VERSION,
        content_hash("target-image-fixture-v2");
        primitives,
        relations,
        domains = (domain,),
        branches,
        selectors,
    )
end

function target_image_registry()
    plugins = (geometry_plugin(), target_image_fixture_plugin())
    builder = RegistryBuilder(allowlist = Tuple(plugin.id for plugin in plugins))
    foreach(plugin -> register!(builder, plugin), plugins)
    return freeze(builder)
end

function _diagnostic_variable(
    name;
    origin = 0.0,
    scale = 1.0,
    lower = nothing,
    upper = nothing,
)
    return VariableSpec(
        VariableId(name),
        SCALAR_TYPE_ID,
        Float64(origin),
        Float64(scale);
        lower = lower === nothing ? nothing : Float64(lower),
        upper = upper === nothing ? nothing : Float64(upper),
    )
end

_diagnostic_locks() = (
    plugin_lock(geometry_plugin()),
    plugin_lock(target_image_fixture_plugin()),
)

function unconstrained_problem(target_operation; bounded = false)
    variable = _diagnostic_variable(
        "x";
        lower = bounded ? 0.0 : nothing,
        upper = bounded ? 2.0 : nothing,
    )
    graph = ConstructionGraph((
        ReferenceNode(NodeId("x_ref"), variable.id),
        CallNode(
            NodeId("target"),
            PrimitiveId(TARGET_IMAGE_FIXTURE_PLUGIN, target_operation),
            (NodeId("x_ref"),),
        ),
    ))
    return ProblemSpecV1(
        _diagnostic_locks(),
        (variable,),
        graph;
        target = NodeId("target"),
    )
end

function manifold_problem(; constant_target = false)
    x = _diagnostic_variable("x")
    y = _diagnostic_variable("y")
    target_operation = constant_target ? "sum" : "identity"
    target_arguments = constant_target ?
                       (NodeId("x_ref"), NodeId("y_ref")) :
                       (NodeId("x_ref"),)
    graph = ConstructionGraph((
        ReferenceNode(NodeId("x_ref"), x.id),
        ReferenceNode(NodeId("y_ref"), y.id),
        CallNode(
            NodeId("relation"),
            PrimitiveId(TARGET_IMAGE_FIXTURE_PLUGIN, "sum_zero"),
            (NodeId("x_ref"), NodeId("y_ref")),
        ),
        CallNode(
            NodeId("target"),
            PrimitiveId(TARGET_IMAGE_FIXTURE_PLUGIN, target_operation),
            target_arguments,
        ),
    ))
    return ProblemSpecV1(
        _diagnostic_locks(),
        (x, y),
        graph;
        relations = (RelationBinding(NodeId("relation")),),
        target = NodeId("target"),
    )
end

function constrained_scalar_problem(; tiny = false, variable_scale = 1.0, relation_scale = nothing)
    variable = _diagnostic_variable("x", scale = variable_scale)
    relation = tiny ? "tiny_zero" : "zero"
    graph = ConstructionGraph((
        ReferenceNode(NodeId("x_ref"), variable.id),
        CallNode(
            NodeId("relation"),
            PrimitiveId(TARGET_IMAGE_FIXTURE_PLUGIN, relation),
            (NodeId("x_ref"),),
        ),
        CallNode(
            NodeId("target"),
            PrimitiveId(TARGET_IMAGE_FIXTURE_PLUGIN, "identity"),
            (NodeId("x_ref"),),
        ),
    ))
    return ProblemSpecV1(
        _diagnostic_locks(),
        (variable,),
        graph;
        relations = (
            RelationBinding(NodeId("relation"); scale_override = relation_scale),
        ),
        target = NodeId("target"),
    )
end

function domain_problem()
    variable = _diagnostic_variable("x", origin = -1.0)
    graph = ConstructionGraph((
        ReferenceNode(NodeId("x_ref"), variable.id),
        CallNode(
            NodeId("domain"),
            PrimitiveId(TARGET_IMAGE_FIXTURE_PLUGIN, "domain"),
            (NodeId("x_ref"),),
        ),
        CallNode(
            NodeId("target"),
            PrimitiveId(TARGET_IMAGE_FIXTURE_PLUGIN, "identity"),
            (NodeId("x_ref"),),
        ),
    ))
    return ProblemSpecV1(
        _diagnostic_locks(),
        (variable,),
        graph;
        domains = (DomainBinding(NodeId("domain"), true),),
        target = NodeId("target"),
    )
end

function branch_problem(; tied = false)
    variable = _diagnostic_variable("x")
    branch = tied ? "stable_choice" : "sign_choice"
    selector = tied ? "tied" : "first"
    graph = ConstructionGraph((
        ReferenceNode(NodeId("x_ref"), variable.id),
        CallNode(
            NodeId("choice"),
            PrimitiveId(TARGET_IMAGE_FIXTURE_PLUGIN, branch),
            (NodeId("x_ref"),),
        ),
        SelectNode(
            NodeId("target"),
            NodeId("choice"),
            SelectorId(TARGET_IMAGE_FIXTURE_PLUGIN, selector),
        ),
    ))
    return ProblemSpecV1(
        _diagnostic_locks(),
        (variable,),
        graph;
        target = NodeId("target"),
    )
end

function constant_target_problem()
    variable = _diagnostic_variable("x")
    graph = ConstructionGraph((
        ReferenceNode(NodeId("unused_x"), variable.id),
        LiteralNode(NodeId("target"), SCALAR_TYPE_ID, 7.0),
    ))
    return ProblemSpecV1(
        _diagnostic_locks(),
        (variable,),
        graph;
        target = NodeId("target"),
    )
end

@testset "unconstrained first- and second-order target sensitivity" begin
    registry = target_image_registry()
    linear = GeoTargetCore.analyze_target_image(
        GeoTargetCore.compile_problem(unconstrained_problem("identity"), registry),
        [0.0],
    )
    @test linear.classification == TARGET_LIKELY_CONTINUOUS
    @test linear.failure == GeoTargetCore.TARGET_IMAGE_DIAGNOSTIC_NONE
    @test linear.numerical_rank == 0
    @test size(linear.nullspace_basis) == (1, 1)
    @test linear.target_gradient ≈ [1.0]
    @test linear.nullspace_target_sensitivity ≈ 1.0
    @test linear.oracle_work > 0

    square_compiled = GeoTargetCore.compile_problem(unconstrained_problem("square"), registry)
    square = GeoTargetCore.analyze_target_image(square_compiled, [0.0])
    @test square.classification == TARGET_LIKELY_CONTINUOUS
    @test abs(only(square.target_gradient)) <= 1.0e-12
    @test square.nullspace_target_sensitivity <= 1.0e-12
    @test square.max_probe_target_variation >= 1.0e-4 - 1.0e-12
    @test all(>(0), square.probe_coverage)

    repeated = GeoTargetCore.analyze_target_image(square_compiled, [0.0])
    @test repeated.classification == square.classification
    @test repeated.scaled_relation_jacobian == square.scaled_relation_jacobian
    @test repeated.target_gradient == square.target_gradient
    @test repeated.nullspace_basis == square.nullspace_basis
    @test repeated.max_probe_target_variation == square.max_probe_target_variation
    @test repeated.oracle_work == square.oracle_work
end

@testset "constraint rank separates continuous, constant-manifold and isolated images" begin
    registry = target_image_registry()
    continuous = GeoTargetCore.analyze_target_image(
        GeoTargetCore.compile_problem(manifold_problem(), registry),
        [0.0, 0.0],
    )
    @test continuous.classification == TARGET_LIKELY_CONTINUOUS
    @test continuous.numerical_rank == 1
    @test size(continuous.nullspace_basis) == (2, 1)
    @test continuous.nullspace_target_sensitivity > 0.5
    @test continuous.condition_estimate ≈ 1.0

    constant = GeoTargetCore.analyze_target_image(
        GeoTargetCore.compile_problem(manifold_problem(constant_target = true), registry),
        [0.0, 0.0],
    )
    @test constant.classification == GeoTargetCore.TARGET_LOCALLY_CONSTANT_MANIFOLD
    @test constant.numerical_rank == 1
    @test constant.nullspace_target_sensitivity <= 1.0e-8
    @test constant.max_probe_target_variation <= 1.0e-8

    isolated = GeoTargetCore.analyze_target_image(
        GeoTargetCore.compile_problem(constrained_scalar_problem(), registry),
        [0.0],
    )
    @test isolated.classification == GeoTargetCore.TARGET_LOCALLY_ISOLATED
    @test isolated.numerical_rank == 1
    @test isempty(isolated.probe_coverage)
    @test isolated.condition_estimate ≈ 1.0

    normalized = GeoTargetCore.analyze_target_image(
        GeoTargetCore.compile_problem(
            constrained_scalar_problem(variable_scale = 4.0, relation_scale = 2.0),
            registry,
        ),
        [0.0],
    )
    @test normalized.scaled_relation_jacobian[1, 1] ≈ 2.0 atol = 1.0e-9
    @test only(normalized.target_gradient) ≈ 4.0 atol = 1.0e-9

    compiled_constant = GeoTargetCore.compile_problem(constant_target_problem(), registry)
    dependency_fast_path = GeoTargetCore.analyze_target_image(compiled_constant, [3.0])
    @test isempty(compiled_constant.sparsity.target_variables)
    @test dependency_fast_path.classification ==
          GeoTargetCore.TARGET_LOCALLY_CONSTANT_MANIFOLD
    @test !dependency_fast_path.linearization_computed
    @test dependency_fast_path.numerical_rank === nothing
    @test dependency_fast_path.sampled_points == 1
end

@testset "rank threshold and normalized one-sided bounds are explicit" begin
    registry = target_image_registry()
    compiled = GeoTargetCore.compile_problem(constrained_scalar_problem(tiny = true), registry)
    low_threshold = GeoTargetCore.analyze_target_image(
        compiled,
        [0.0];
        options = GeoTargetCore.TargetImageDiagnosticOptions(
            rank_absolute_tolerance = 1.0e-12,
            rank_relative_tolerance = 0.0,
        ),
    )
    high_threshold = GeoTargetCore.analyze_target_image(
        compiled,
        [0.0];
        options = GeoTargetCore.TargetImageDiagnosticOptions(
            rank_absolute_tolerance = 1.0e-6,
            rank_relative_tolerance = 0.0,
        ),
    )
    @test low_threshold.numerical_rank == 1
    @test low_threshold.classification == GeoTargetCore.TARGET_LOCALLY_ISOLATED
    @test high_threshold.numerical_rank == 0
    @test high_threshold.classification == TARGET_LIKELY_CONTINUOUS
    @test high_threshold.rank_threshold == 1.0e-6

    bounded = GeoTargetCore.analyze_target_image(
        GeoTargetCore.compile_problem(unconstrained_problem("identity", bounded = true), registry),
        [0.0],
    )
    @test bounded.classification == TARGET_LIKELY_CONTINUOUS
    @test bounded.difference_schemes == (GeoTargetCore.TARGET_DIFFERENCE_FORWARD,)
    @test only(bounded.probe_coverage) == length(
        GeoTargetCore.TargetImageDiagnosticOptions().probe_radii,
    )
end

@testset "invalid domains and unstable branches stay inconclusive" begin
    registry = target_image_registry()
    domain = GeoTargetCore.analyze_target_image(
        GeoTargetCore.compile_problem(domain_problem(), registry),
        [-1.0],
    )
    @test domain.classification == GeoTargetCore.TARGET_IMAGE_INCONCLUSIVE
    @test domain.failure == GeoTargetCore.TARGET_IMAGE_BASE_SEMANTICS_FAILED
    @test domain.base_observation.status == EVAL_INVALID_DOMAIN

    flip = GeoTargetCore.analyze_target_image(
        GeoTargetCore.compile_problem(branch_problem(), registry),
        [0.0],
    )
    @test flip.classification == GeoTargetCore.TARGET_IMAGE_INCONCLUSIVE
    @test flip.failure == GeoTargetCore.TARGET_IMAGE_INSUFFICIENT_STENCIL
    @test flip.difference_schemes == (GeoTargetCore.TARGET_DIFFERENCE_UNAVAILABLE,)

    tie = GeoTargetCore.analyze_target_image(
        GeoTargetCore.compile_problem(branch_problem(tied = true), registry),
        [0.0],
    )
    @test tie.classification == GeoTargetCore.TARGET_IMAGE_INCONCLUSIVE
    @test tie.failure == GeoTargetCore.TARGET_IMAGE_BASE_SEMANTICS_FAILED
    @test tie.base_observation.status == EVAL_AMBIGUOUS_BRANCH
end

@testset "capability and BigFloat precision are isolated without silent fallback" begin
    registry = target_image_registry()
    c0_compiled = GeoTargetCore.compile_problem(unconstrained_problem("c0_only"), registry)
    unavailable = GeoTargetCore.analyze_target_image(
        c0_compiled,
        [1.0];
        options = GeoTargetCore.TargetImageDiagnosticOptions(capability = C2),
    )
    @test unavailable.classification == GeoTargetCore.TARGET_IMAGE_INCONCLUSIVE
    @test unavailable.failure == GeoTargetCore.TARGET_IMAGE_CAPABILITY_UNAVAILABLE
    @test unavailable.sampled_points == 0
    @test unavailable.oracle_work == 0

    compiled = GeoTargetCore.compile_problem(unconstrained_problem("identity"), registry)
    before = precision(BigFloat)
    high_precision = setprecision(BigFloat, 137) do
        result = GeoTargetCore.analyze_target_image(
            compiled,
            [1.0];
            options = GeoTargetCore.TargetImageDiagnosticOptions(
                capability = C2,
                precision_bits = 320,
            ),
        )
        @test precision(BigFloat) == 137
        result
    end
    @test precision(BigFloat) == before
    @test high_precision.classification == TARGET_LIKELY_CONTINUOUS
    @test high_precision.capability == C2
    @test high_precision.precision_bits == 320
    @test high_precision.base_observation.target isa BigFloat
    @test precision(high_precision.base_observation.target) == 320
    @test occursin("Float64 SVD", high_precision.svd_numeric_type)

    concurrent = (
        Threads.@spawn(GeoTargetCore.analyze_target_image(
            compiled,
            [1.0];
            options = GeoTargetCore.TargetImageDiagnosticOptions(
                capability = C2,
                precision_bits = 192,
            ),
        )),
        Threads.@spawn(GeoTargetCore.analyze_target_image(
            compiled,
            [1.0];
            options = GeoTargetCore.TargetImageDiagnosticOptions(
                capability = C2,
                precision_bits = 448,
            ),
        )),
    )
    concurrent_results = fetch.(concurrent)
    @test precision(concurrent_results[1].base_observation.target) == 192
    @test precision(concurrent_results[2].base_observation.target) == 448
    @test precision(BigFloat) == before
end

@testset "local diagnostics cannot manufacture certified target-image status" begin
    registry = target_image_registry()
    diagnostic = GeoTargetCore.analyze_target_image(
        GeoTargetCore.compile_problem(unconstrained_problem("identity"), registry),
        [0.0],
    )
    @test_throws InvariantError GeoTargetCore.TargetImageDiagnostic(
        TARGET_COMPLETE_CERTIFIED,
        diagnostic,
    )
    @test_throws InvariantError GeoTargetCore.TargetImageDiagnostic(
        TARGET_EMPTY_CERTIFIED,
        diagnostic,
    )

    source = read(
        joinpath(@__DIR__, "..", "GeoTargetCore", "src", "target_image.jl"),
        String,
    )
    @test !occursin("GeoTargetGeometry", source)
    @test !occursin("builtin_geometry", source)
    @test !occursin("invokelatest", source)
    @test !occursin(r"\beval\s*\(", source)
    @test !occursin(r"\b(point2|line_through|circle2|scalar_equality)\b", source)
end

@testset "target-image options reject unsafe controls" begin
    @test_throws ArgumentError GeoTargetCore.TargetImageDiagnosticOptions(
        finite_difference_radius = 0,
    )
    @test_throws ArgumentError GeoTargetCore.TargetImageDiagnosticOptions(probe_radii = ())
    @test_throws ArgumentError GeoTargetCore.TargetImageDiagnosticOptions(
        rank_relative_tolerance = -1,
    )
    @test_throws ArgumentError GeoTargetCore.TargetImageDiagnosticOptions(precision_bits = 52)
    @test_throws CapabilityError GeoTargetCore.TargetImageDiagnosticOptions(capability = C3V)
end
