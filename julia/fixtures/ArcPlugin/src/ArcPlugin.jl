module ArcPlugin

using GeoTargetBase
using GeoTargetGeometry

export OrientedArc,
    oriented_arc,
    arc_midpoint,
    ARC_PLUGIN_ID,
    ORIENTED_ARC_TYPE_ID,
    ARC_CONTENT_HASH,
    arc_plugin

struct OrientedArc{T<:Real}
    circle::Circle2{T}
    start::Point2{T}
    stop::Point2{T}
    counterclockwise::Bool
end

function oriented_arc(
    circle::Circle2{T},
    start::Point2{T},
    stop::Point2{T},
    orientation::Real,
) where {T<:Real}
    return OrientedArc(circle, start, stop, orientation >= zero(orientation))
end

function arc_midpoint(arc::OrientedArc{T}) where {T<:Real}
    center = arc.circle.center
    start_angle = atan(arc.start.y - center.y, arc.start.x - center.x)
    stop_angle = atan(arc.stop.y - center.y, arc.stop.x - center.x)
    delta = stop_angle - start_angle
    two_pi = oftype(delta, 2) * oftype(delta, pi)

    if arc.counterclockwise
        delta < zero(delta) && (delta += two_pi)
    else
        delta > zero(delta) && (delta -= two_pi)
    end
    angle = start_angle + delta / oftype(delta, 2)
    return Point2(
        center.x + arc.circle.radius * cos(angle),
        center.y + arc.circle.radius * sin(angle),
    )
end

const ARC_PLUGIN_ID = parse(PluginId, "b727f09c-1ab7-4374-9a70-1c704bdc7286/arc_fixture")
const ORIENTED_ARC_TYPE_ID = TypeId(ARC_PLUGIN_ID, "oriented_arc")

# M1 canonical manifest source; generated from PluginSpec in a later build phase.
const _ARC_MANIFEST_V1 = join(
    (
        "plugin=b727f09c-1ab7-4374-9a70-1c704bdc7286/arc_fixture@0.1.0",
        "types=oriented_arc",
        "primitives=oriented_arc,arc_midpoint",
        "external_types=builtin_geometry/circle2,point2,scalar",
        "capabilities=numeric_generic_float64_bigfloat",
    ),
    "\n",
)
const ARC_CONTENT_HASH = content_hash(_ARC_MANIFEST_V1)

function _arc_kernel(evaluator)
    return OperatorKernel(
        evaluator;
        capabilities = CapabilitySet(C0, C2),
        smoothness = PIECEWISE_SMOOTH,
        generic_numeric = true,
    )
end

function _build_arc_plugin()
    arc_type = TypeSpec(
        ORIENTED_ARC_TYPE_ID,
        OrientedArc;
        documentation = "External custom OrientedArc{T}",
    )
    constructor_signature = SignatureSpec(
        (CIRCLE_TYPE_ID, POINT_TYPE_ID, POINT_TYPE_ID, SCALAR_TYPE_ID),
        ORIENTED_ARC_TYPE_ID,
    )
    midpoint_signature = SignatureSpec((ORIENTED_ARC_TYPE_ID,), POINT_TYPE_ID)
    primitives = (
        PrimitiveSpec(
            PrimitiveId(ARC_PLUGIN_ID, "oriented_arc"),
            (constructor_signature,),
            _arc_kernel(oriented_arc),
        ),
        PrimitiveSpec(
            PrimitiveId(ARC_PLUGIN_ID, "arc_midpoint"),
            (midpoint_signature,),
            _arc_kernel(arc_midpoint),
        ),
    )
    return PluginSpec(
        ARC_PLUGIN_ID,
        v"0.1.0",
        v"1.0.0",
        ARC_CONTENT_HASH;
        types = (arc_type,),
        primitives,
    )
end

const _ARC_PLUGIN = _build_arc_plugin()
arc_plugin() = _ARC_PLUGIN

end
