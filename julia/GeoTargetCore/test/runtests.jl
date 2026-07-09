using GeoTargetBase
using GeoTargetCore
using Test

@testset "GeoTargetCore bootstrap" begin
    @test GeoTargetCore.abi_version() == GeoTargetBase.PACKAGE_VERSION
end

