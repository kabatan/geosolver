using GeoTargetBase
using GeoTargetCore
using GeoTargetGeometry
using Test

if !isdefined(Main, :GeoTargetApp)
    include(joinpath(@__DIR__, "..", "app", "GeoTargetApp.jl"))
end

if !isdefined(Main, :BlackBoxCirclePlugin)
    include(joinpath(
        @__DIR__,
        "..",
        "..",
        "examples",
        "open_world_plugin",
        "BlackBoxCirclePlugin.jl",
    ))
end
using .BlackBoxCirclePlugin

@testset "open-world SDK quickstart reaches custom-registry CLI solve" begin
    geometry = GeoTargetGeometry.geometry_plugin()
    custom = BlackBoxCirclePlugin.black_box_circle_plugin()
    builder = RegistryBuilder(allowlist = (geometry.id, custom.id))
    register!(builder, geometry)
    register!(builder, custom)
    registry = freeze(builder)

    example = normpath(joinpath(@__DIR__, "..", "..", "examples", "open_world_plugin"))
    problem_path = joinpath(example, "problem.json")
    options_path = joinpath(example, "options.json")
    problem_source = read(problem_path, String)
    problem = GeoTargetCore.decode_problem_json(problem_source, registry)

    @test GeoTargetCore.encode_problem_json(problem, registry) == chomp(problem_source)
    @test isempty(validate_problem(problem, registry))
    observation = evaluate_reference(problem, registry, [1.0])
    @test observation.status == EVAL_OK
    @test observation.target == 1.0
    @test only(observation.relations).raw == 0.0
    @test only(observation.relations).truth

    mktempdir() do directory
        output = IOBuffer()
        errors = IOBuffer()
        evidence = joinpath(directory, "evidence.json")
        @test GeoTargetApp.main(
            [
                "solve",
                problem_path,
                "--options",
                options_path,
                "--evidence",
                evidence,
                "--max-actions",
                "2",
            ];
            registry,
            stdout = output,
            stderr = errors,
        ) == 0
        @test isempty(String(take!(errors)))
        result = GeoTargetCore.decode_solve_result_json(String(take!(output)))
        @test result.search_status == SEARCH_FINISHED_UNKNOWN
        @test result.target_image_status == TARGET_FINITE_OBSERVED
        @test length(result.provisional_answers) == 1
        answer = only(result.provisional_answers)
        target_lower = parse(BigFloat, string(answer.target.lower))
        target_upper = parse(BigFloat, string(answer.target.upper))
        @test target_lower <= BigFloat(1) <= target_upper
        @test answer.validation.method == "canonical_bigfloat_recheck"
        @test isfile(evidence)
    end
end
