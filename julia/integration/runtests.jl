using GeoTargetBase
using GeoTargetCore
using GeoTargetGeometry
using Test

const REPOSITORY_ROOT = normpath(joinpath(@__DIR__, "..", ".."))

@testset "GeoTarget workspace" begin
    include(joinpath(@__DIR__, "..", "GeoTargetBase", "test", "runtests.jl"))
    include(joinpath(@__DIR__, "..", "GeoTargetCore", "test", "runtests.jl"))
    include(joinpath(@__DIR__, "..", "GeoTargetGeometry", "test", "runtests.jl"))
end

@testset "Dependency direction" begin
    core_source = read(
        joinpath(@__DIR__, "..", "GeoTargetCore", "src", "GeoTargetCore.jl"),
        String,
    )
    @test !occursin("GeoTargetGeometry", core_source)
end

