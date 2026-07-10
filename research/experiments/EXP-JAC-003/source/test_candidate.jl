using GeoTargetBase
using GeoTargetCore
using JSON3
using LinearAlgebra
using Test

include("CandidateJac003.jl")
using .CandidateJac003
include("SafetyJac003.jl")
using .SafetyJac003

function relation(row, value)
    return RelationObservation(NodeId("t$row"), value, 1.0, value, nothing)
end

function identity_observation(point)
    return OracleObservation(
        (relation(1, point[1]), relation(2, point[2])),
        nothing,
        (),
        (),
        (),
        EVAL_OK,
        1,
        nothing,
    )
end

function provider_hash(supports, groups, structural_nonzeros)
    return string(canonical_json_hash(Dict{String,Any}(
        "groups" => Any[collect(group) for group in groups],
        "row_supports" => Any[collect(rows) for rows in supports],
        "structural_nonzeros" => structural_nonzeros,
    )))
end

@testset "EXP-JAC-003 exact identity-free route" begin
    @test use_colored_route(RouteProjection(10, 10, 10, 7))
    @test !use_colored_route(RouteProjection(10, 10, 0, 8))
    @test !use_colored_route(RouteProjection(10, 10, 10, 10))
    @test !use_colored_route(RouteProjection(0, 10, 0, 0))
    @test !use_colored_route(RouteProjection(10, 0, 0, 0))
    @test !use_colored_route(RouteProjection(10, 10, 101, 1))
    @test use_colored_route(RouteProjection(typemax(Int), 1, 0, 0))
    @test !use_colored_route(RouteProjection(typemax(Int), 1, typemax(Int), typemax(Int)))
    @test sort(String[string(name) for name in fieldnames(ProviderProjection)]) ==
          ["groups", "row_supports", "structural_nonzeros"]
    @test sort(String[string(name) for name in fieldnames(RouteProjection)]) ==
          ["color_count", "residual_count", "structural_nonzeros", "variable_count"]
    forbidden = Set((
        "opaque_case_id", "operation", "literal", "family_id", "factors", "seeds",
        "gold", "analytic", "jacobian", "k0", "starts", "targets", "outcomes",
    ))
    @test isempty(intersect(forbidden, Set(lowercase.(String.(fieldnames(ProviderProjection))))))
    @test isempty(intersect(forbidden, Set(lowercase.(String.(fieldnames(RouteProjection))))))
end

@testset "EXP-JAC-003 conservative typed graph compiler" begin
    graph = Dict{String,Any}(
        "schema_version" => "exp-jac-003-typed-graph/v1",
        "nodes" => Any[
            Dict("kind" => "reference", "node_id" => "v0", "value_type" => "real", "variable_slot" => 0),
            Dict("kind" => "reference", "node_id" => "v1", "value_type" => "real", "variable_slot" => 1),
            Dict(
                "kind" => "call",
                "node_id" => "r0",
                "operation" => "jac3.blackbox/test_relation",
                "value_type" => "relation",
                "arguments" => Any["v0"],
            ),
            Dict(
                "kind" => "call",
                "node_id" => "r1",
                "operation" => "jac3.blackbox/test_relation",
                "value_type" => "relation",
                "arguments" => Any["v1"],
            ),
        ],
        "relations" => Any["r0", "r1"],
        "domains" => Any[],
        "branches" => Any[],
    )
    dependencies = compile_dependencies(graph, 2, 2)
    @test dependencies.row_supports == ((1,), (2,))
    @test dependencies.structural_nonzeros == 2
    structure = compile_structure(graph, 2, 2)
    @test structure.provider.groups == ((1, 2),)
    @test structure.route == RouteProjection(2, 2, 2, 1)
    @test use_colored_route(structure.route)
    @test visibility_record(structure)["provider_field_names"] ==
          ["groups", "row_supports", "structural_nonzeros"]
    @test visibility_record(structure)["route_field_names"] ==
          ["color_count", "residual_count", "structural_nonzeros", "variable_count"]

    broken = deepcopy(graph)
    broken["nodes"][4]["arguments"] = Any["missing"]
    @test_throws CandidateCompileError compile_structure(broken, 2, 2)
    duplicate = deepcopy(graph)
    duplicate["nodes"][2]["variable_slot"] = 0
    @test_throws CandidateCompileError compile_structure(duplicate, 2, 2)
    reordered = deepcopy(graph)
    reordered["nodes"] = reverse(reordered["nodes"])
    @test_throws CandidateCompileError compile_structure(reordered, 2, 2)
end

@testset "EXP-JAC-003 sealed provider validation" begin
    valid_hash = provider_hash(((1,), (2,)), ((1, 2),), 2)
    provider = GeoTargetCore._sealed_local_jacobian_provider(
        ((1,), (2,)),
        ((1, 2),),
        2,
        2,
        2,
        valid_hash,
    )
    @test provider.residual_count == 2
    @test provider.variable_count == 2
    @test GeoTargetCore._jacobian_evaluation_bound(provider, 2) == 6
    @test_throws ArgumentError GeoTargetCore._sealed_local_jacobian_provider(
        ((1, 1), (2,)), ((1, 2),), 3, 2, 2, valid_hash,
    )
    @test_throws ArgumentError GeoTargetCore._sealed_local_jacobian_provider(
        ((1,), (1,)), ((1, 2),), 2, 2, 2, valid_hash,
    )
    @test_throws ArgumentError GeoTargetCore._sealed_local_jacobian_provider(
        ((1,), (2,)), ((2, 1),), 2, 2, 2, valid_hash,
    )
    @test_throws ArgumentError GeoTargetCore._sealed_local_jacobian_provider(
        ((1,), (2,)), ((1, 2),), 1, 2, 2, valid_hash,
    )
    @test_throws ArgumentError GeoTargetCore._sealed_local_jacobian_provider(
        ((1,), (2,)), ((1, 2),), 2, 3, 2, "",
    )
    @test_throws ArgumentError GeoTargetCore._resolve_local_jacobian_source(provider, 3, 2)
    @test_throws ArgumentError GeoTargetCore._resolve_local_jacobian_source(provider, 2, 3)
end

@testset "EXP-JAC-003 fallback reservation and coverage" begin
    controls = SafetyJac003._fallback_controls()
    @test Set(control["mode"] for control in controls) ==
          Set(("plus_invalid", "minus_invalid", "nonfinite", "length"))
    for control in controls
        @test control["failure"] === nothing
        @test control["evaluations"] == 6
        @test control["matrix"]["shape"] == Any[2, 2]
        @test control["matrix"]["entries"] == Any[Any[0, 0, 1.0], Any[1, 1, 1.0]]
        @test length(control["group_events"]) == 1
        event = only(control["group_events"])
        @test event["fallback"]
        @test event["columns"] == [1, 2]
        @test event["grouped_evaluations"] == 2
        @test event["fallback_evaluations"] == 4
        @test event["completed_fallback_columns"] == 2
    end
end

@testset "EXP-JAC-003 shared kernel leaves public surface closed" begin
    @test length(methods(solve_local)) == 2
    @test :solve_local in names(GeoTargetCore)
    @test !(:_solve_local_with_provider in names(GeoTargetCore))
    @test !(:_SealedLocalJacobianProvider in names(GeoTargetCore))
    direct = only(filter(method -> occursin("evaluate_fn", string(method)), methods(solve_local)))
    text = string(direct)
    @test !occursin("provider", text)
    @test !occursin("prepared_coloring", text)
    valid_hash = provider_hash(((1,), (2,)), ((1, 2),), 2)
    provider = GeoTargetCore._sealed_local_jacobian_provider(
        ((1,), (2,)), ((1, 2),), 2, 2, 2, valid_hash,
    )
    dense = solve_local(identity_observation, [0.25, -0.5])
    cached = GeoTargetCore._solve_local_with_provider(
        identity_observation,
        [0.25, -0.5],
        provider,
    )
    @test dense.status == cached.status
    @test dense.accepted == cached.accepted
    @test dense.final == cached.final
    @test dense.observation == cached.observation
end
