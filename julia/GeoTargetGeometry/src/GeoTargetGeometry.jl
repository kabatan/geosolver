module GeoTargetGeometry

using GeoTargetBase

include("types.jl")
include("operations.jl")
include("plugin.jl")

"""Return the ABI version implemented by the built-in geometry plugin."""
abi_version() = GEOMETRY_CORE_ABI

export abi_version,
    Point2,
    Line2,
    Circle2,
    point2,
    line_through,
    circle2,
    distance,
    scalar_equality_residual,
    scalar_equality_truth,
    positive_margin,
    safe_domain_margin,
    safe_domain_singularity,
    line_circle_intersections,
    select_near,
    select_far,
    select_orientation,
    GEOMETRY_PLUGIN_ID,
    GEOMETRY_PLUGIN_VERSION,
    GEOMETRY_CORE_ABI,
    GEOMETRY_CONTENT_HASH,
    SCALAR_TYPE_ID,
    POINT_TYPE_ID,
    LINE_TYPE_ID,
    CIRCLE_TYPE_ID,
    CHOICE_TYPE_ID,
    geometry_plugin

end
