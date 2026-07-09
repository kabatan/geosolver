using GeoTargetBase
using GeoTargetGeometry
using Test

@testset "GeoTargetGeometry bootstrap" begin
    @test GeoTargetGeometry.abi_version() == GeoTargetBase.PACKAGE_VERSION
end

