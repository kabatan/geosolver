include(joinpath(@__DIR__, "BlackBoxCirclePlugin.jl"))
include(joinpath(@__DIR__, "..", "..", "julia", "app", "GeoTargetApp.jl"))

using GeoTargetBase
using GeoTargetCore
using GeoTargetGeometry
using .BlackBoxCirclePlugin

geometry = GeoTargetGeometry.geometry_plugin()
custom = BlackBoxCirclePlugin.black_box_circle_plugin()
builder = RegistryBuilder(allowlist = (geometry.id, custom.id))
register!(builder, geometry)
register!(builder, custom)
registry = freeze(builder)

exit(GeoTargetApp.main(ARGS; registry))
