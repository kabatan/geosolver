using GeoTargetBase
using GeoTargetGeometry
using Test

include(joinpath(@__DIR__, "..", "..", "fixtures", "ArcPlugin", "src", "ArcPlugin.jl"))
include(joinpath(@__DIR__, "..", "..", "fixtures", "OpaquePlugin", "src", "OpaquePlugin.jl"))
using .ArcPlugin
using .OpaquePlugin

function operation_specs(plugin::PluginSpec)
    return (
        plugin.primitives...,
        plugin.relations...,
        plugin.guards...,
        plugin.domains...,
        plugin.branches...,
    )
end

kernel(spec::PrimitiveSpec) = spec.kernel
kernel(spec::RelationSpec) = spec.residual_kernel
kernel(spec::GuardSpec) = spec.margin_kernel
kernel(spec::DomainSpec) = spec.margin_kernel
kernel(spec::BranchSpec) = spec.kernel
kernel(spec::SelectorSpec) = spec.kernel

function operation(plugin::PluginSpec, name::AbstractString)
    id = PrimitiveId(plugin.id, name)
    return only(spec for spec in operation_specs(plugin) if spec.id == id)
end

@testset "built-in plugin identity and conformance" begin
    plugin = geometry_plugin()
    @test GeoTargetGeometry.abi_version() == v"1.0.0"
    @test plugin.core_abi == v"1.0.0"
    @test plugin === geometry_plugin()
    @test string(plugin.id) ==
          "5cba7841-765c-4ef1-987e-27fcb9985e3d/builtin_geometry"
    @test string(plugin.content) ==
          "sha256:22585ce0501f448de3184b7ee5aedef9f4e084f7c6bb728823e645d2bce3f7a7"
    @test plugin_lock(plugin).content == GEOMETRY_CONTENT_HASH
    @test length(plugin.types) == 5
    @test length(plugin.primitives) == 4
    @test length(plugin.relations) == 1
    @test length(plugin.guards) == 1
    @test length(plugin.domains) == 1
    @test length(plugin.branches) == 1
    @test length(plugin.selectors) == 3
    @test Set(spec.id for spec in plugin.types) ==
          Set((SCALAR_TYPE_ID, POINT_TYPE_ID, LINE_TYPE_ID, CIRCLE_TYPE_ID, CHOICE_TYPE_ID))
    @test all(spec -> spec.id.plugin == plugin.id, operation_specs(plugin))
    @test all(spec -> supports(kernel(spec).capabilities, C0), operation_specs(plugin))
    @test all(spec -> !supports(kernel(spec).capabilities, C3V), operation_specs(plugin))
    @test all(spec -> !supports(kernel(spec).capabilities, C3A), operation_specs(plugin))
    @test all(
        spec -> !supports(kernel(spec).capabilities, C2) ||
                kernel(spec).generic_numeric ||
                kernel(spec).high_precision !== nothing,
        (operation_specs(plugin)..., plugin.selectors...),
    )
    @test only(plugin.guards).default_strict
    @test only(plugin.domains).default_strict
end

@testset "numeric-generic elementary constructions" begin
    float_point = point2(1.0, 2.0)
    big_point = point2(big"1.0", big"2.0")
    @test float_point isa Point2{Float64}
    @test big_point isa Point2{BigFloat}

    float_line = line_through(point2(0.0, 0.0), point2(2.0, 1.0))
    big_line = line_through(
        point2(big"0.0", big"0.0"),
        point2(big"2.0", big"1.0"),
    )
    @test float_line isa Line2{Float64}
    @test big_line isa Line2{BigFloat}
    @test line_through(big_point, float_point) isa Line2{BigFloat}

    float_circle = circle2(float_point, 3.0)
    big_circle = circle2(big_point, big"3.0")
    @test float_circle isa Circle2{Float64}
    @test big_circle isa Circle2{BigFloat}
    @test circle2(big_point, 3.0) isa Circle2{BigFloat}
    @test distance(point2(0.0, 0.0), point2(3.0, 4.0)) == 5.0
    @test distance(
        point2(big"0.0", big"0.0"),
        point2(big"3.0", big"4.0"),
    ) == big"5.0"
    @test scalar_equality_residual(big"2.5", big"1.0") == big"1.5"
    @test scalar_equality_truth(big"2.5", big"2.5")
end

@testset "line-circle Choice has 0, 1 and 2 stable branches" begin
    circle = circle2(point2(0.0, 0.0), 1.0)
    no_hit = line_circle_intersections(
        line_through(point2(-2.0, 2.0), point2(2.0, 2.0)),
        circle,
    )
    tangent = line_circle_intersections(
        line_through(point2(-2.0, 1.0), point2(2.0, 1.0)),
        circle,
    )
    secant = line_circle_intersections(
        line_through(point2(-2.0, 0.0), point2(2.0, 0.0)),
        circle,
    )

    @test isempty(no_hit)
    @test length(tangent) == 1
    @test tangent.keys == (ChoiceKey("tangent"),)
    @test tangent.validity_margins[1] > 0
    @test tangent.candidates[1].x == 0.0
    @test tangent.candidates[1].y == 1.0
    @test length(secant) == 2
    @test secant.keys == (ChoiceKey("negative_root"), ChoiceKey("positive_root"))
    @test all(margin -> margin > 0, secant.validity_margins)
    @test secant.candidates[1] == point2(-1.0, 0.0)
    @test secant.candidates[2] == point2(1.0, 0.0)

    big_secant = line_circle_intersections(
        line_through(point2(big"-2.0", big"0.0"), point2(big"2.0", big"0.0")),
        circle2(point2(big"0.0", big"0.0"), big"1.0"),
    )
    @test all(candidate -> candidate isa Point2{BigFloat}, big_secant.candidates)
    @test big_secant.keys == secant.keys
end

@testset "generic selectors retain key and independent margin" begin
    circle = circle2(point2(0.0, 0.0), 1.0)
    choice = line_circle_intersections(
        line_through(point2(-2.0, 0.0), point2(2.0, 0.0)),
        circle,
    )

    tie = select_near(choice, point2(0.0, 0.0))
    @test tie.key == ChoiceKey("negative_root")
    @test tie.selector_margin == 0.0
    @test tie.validity_margin > 0

    near = select_near(choice, point2(-2.0, 0.0))
    far = select_far(choice, point2(-2.0, 0.0))
    oriented = select_orientation(choice, point2(0.0, 0.0), point2(0.0, 1.0))
    @test near.key == ChoiceKey("negative_root")
    @test far.key == ChoiceKey("positive_root")
    @test oriented.key == ChoiceKey("negative_root")
    @test near.selector_margin == 8.0
    @test far.selector_margin == 8.0
    @test oriented.selector_margin == 2.0

    tangent = line_circle_intersections(
        line_through(point2(-2.0, 1.0), point2(2.0, 1.0)),
        circle,
    )
    @test select_near(tangent, point2(0.0, 0.0)).selector_margin > 0
    @test_throws InvariantError select_near(Choice((), (), ()), point2(0.0, 0.0))
end

@testset "strict guard and safe domain stay separate" begin
    plugin = geometry_plugin()
    @test positive_margin(1.0) > 0
    @test iszero(positive_margin(0.0))
    @test positive_margin(-1.0) < 0
    @test only(plugin.guards).default_strict

    degenerate = line_through(point2(1.0, 1.0), point2(1.0, 1.0))
    invalid_circle = circle2(point2(0.0, 0.0), -1.0)
    @test iszero(safe_domain_margin(degenerate))
    @test safe_domain_singularity(degenerate)
    @test safe_domain_margin(invalid_circle) < 0
    @test isempty(line_circle_intersections(degenerate, invalid_circle))
end

@testset "external ArcPlugin composes built-in custom objects" begin
    plugin = arc_plugin()
    @test plugin.core_abi == v"1.0.0"
    @test string(plugin.content) ==
          "sha256:470996af9a6733ef65941253492e99f1a79bf5558f22a4c696cdfbf934f33325"
    @test length(plugin.types) == 1
    @test only(plugin.types).id == ORIENTED_ARC_TYPE_ID
    @test all(spec -> spec.id.plugin == ARC_PLUGIN_ID, plugin.primitives)
    @test all(spec -> supports(spec.kernel.capabilities, C2), plugin.primitives)

    circle = circle2(point2(0.0, 0.0), 1.0)
    arc = oriented_arc(circle, point2(1.0, 0.0), point2(-1.0, 0.0), 1.0)
    midpoint = arc_midpoint(arc)
    @test arc isa OrientedArc{Float64}
    @test midpoint.x ≈ 0.0 atol = 1.0e-14
    @test midpoint.y ≈ 1.0 atol = 1.0e-14

    big_circle = circle2(point2(big"0.0", big"0.0"), big"1.0")
    big_arc = oriented_arc(
        big_circle,
        point2(big"1.0", big"0.0"),
        point2(big"-1.0", big"0.0"),
        big"1.0",
    )
    big_midpoint = arc_midpoint(big_arc)
    @test big_midpoint isa Point2{BigFloat}
    @test abs(big_midpoint.x) < big"1e-70"
    @test abs(big_midpoint.y - 1) < big"1e-70"
end

@testset "OpaquePlugin advertises truthful capability loss" begin
    plugin = opaque_plugin()
    @test plugin.core_abi == v"1.0.0"
    @test string(plugin.content) ==
          "sha256:96534b4fd97e7f83e0fba1b05fc998013830ed8da7e4d8117940a23e9bb3b5be"
    generic_spec = operation(plugin, "opaque_iterate")
    float64_spec = operation(plugin, "float64_only")
    log_spec = operation(plugin, "log_exp")
    @test supports(kernel(generic_spec).capabilities, C2)
    @test kernel(generic_spec).generic_numeric
    @test supports(kernel(float64_spec).capabilities, C0)
    @test !supports(kernel(float64_spec).capabilities, C1)
    @test !supports(kernel(float64_spec).capabilities, C2)
    @test supports(kernel(log_spec).capabilities, C2)

    float_value = opaque_iterate(0.25)
    big_value = opaque_iterate(big"0.25")
    @test float_value isa OpaqueValue{Float64}
    @test big_value isa OpaqueValue{BigFloat}
    @test float_value.iterations == 7
    @test opaque_scalar(big_value) isa BigFloat
    @test isfinite(float64_only(0.25))
    @test_throws MethodError float64_only(big"0.25")

    @test positive_log_domain(1.0) > 0
    @test iszero(positive_log_domain(0.0))
    @test positive_log_domain(-1.0) < 0
    @test_throws DomainError log_exp(-1.0)
    @test log_exp(big"2.0") isa BigFloat
end

@testset "plugin layer has no Core coupling or global registration" begin
    roots = (
        normpath(joinpath(@__DIR__, "..", "src")),
        normpath(joinpath(@__DIR__, "..", "..", "fixtures")),
    )
    source_files = String[]
    for root in roots
        for (directory, _, files) in walkdir(root)
            for file in files
                endswith(file, ".jl") && push!(source_files, joinpath(directory, file))
            end
        end
    end
    source = join((read(file, String) for file in source_files), "\n")
    @test !occursin("GeoTargetCore", source)
    @test !occursin("register!", source)
    @test !occursin(r"(?m)^\s*global\s+", source)
end
