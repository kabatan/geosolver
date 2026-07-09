using GeoTargetBase
using Test

@testset "GeoTargetBase bootstrap" begin
    @test GeoTargetBase.PACKAGE_VERSION == v"0.1.0-DEV"
end

