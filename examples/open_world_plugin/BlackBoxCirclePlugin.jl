module BlackBoxCirclePlugin

using GeoTargetBase
using GeoTargetGeometry

export BLACK_BOX_CIRCLE_PLUGIN_ID,
    BLACK_BOX_CIRCLE_CONTENT_HASH,
    HIDDEN_POINT_TYPE_ID,
    black_box_circle_plugin

"""
An intentionally opaque geometric object.

Core sees values of this type only through the plugin ABI. The coordinates and
the formula used by `unit_circle_residual` are not represented as graph nodes.
"""
struct HiddenPoint2{T<:Real}
    x::T
    y::T
end

function hidden_point2(x::Real, y::Real)
    promoted_x, promoted_y = promote(x, y)
    return HiddenPoint2(promoted_x, promoted_y)
end

unit_circle_residual(point::HiddenPoint2) =
    point.x * point.x + point.y * point.y - one(point.x)
unit_circle_truth(point::HiddenPoint2) = iszero(unit_circle_residual(point))

const BLACK_BOX_CIRCLE_PLUGIN_ID =
    parse(PluginId, "2f8f6d72-565e-43fe-865b-a3c497a211ef/black_box_circle")
const HIDDEN_POINT_TYPE_ID = TypeId(BLACK_BOX_CIRCLE_PLUGIN_ID, "hidden_point2")

# Plugin content identities are developer-owned, stable hashes of a canonical
# implementation/metadata manifest. Changing semantics requires a new hash (and
# normally a version bump), so stale problem locks fail closed.
const _BLACK_BOX_CIRCLE_MANIFEST_V1 = join(
    (
        "plugin=2f8f6d72-565e-43fe-865b-a3c497a211ef/black_box_circle@0.1.0",
        "types=hidden_point2",
        "primitives=hidden_point2",
        "relations=unit_circle",
        "relation_truth_policy=unit_circle:approximate_zero",
        "capabilities=numeric_generic_float64_bigfloat",
    ),
    "\n",
)
const BLACK_BOX_CIRCLE_CONTENT_HASH = content_hash(_BLACK_BOX_CIRCLE_MANIFEST_V1)

function _smooth_kernel(evaluator)
    return OperatorKernel(
        evaluator;
        capabilities = CapabilitySet(C0, C1, C2),
        smoothness = SMOOTH_C1,
        derivative_mode = DERIVATIVE_AUTODIFF,
        generic_numeric = true,
    )
end

function _build_plugin()
    hidden_point = TypeSpec(
        HIDDEN_POINT_TYPE_ID,
        HiddenPoint2;
        documentation = "Opaque two-dimensional point",
    )
    point_signature = SignatureSpec(
        (GeoTargetGeometry.SCALAR_TYPE_ID, GeoTargetGeometry.SCALAR_TYPE_ID),
        HIDDEN_POINT_TYPE_ID,
    )
    circle_signature =
        SignatureSpec((HIDDEN_POINT_TYPE_ID,), GeoTargetGeometry.SCALAR_TYPE_ID)

    point = PrimitiveSpec(
        PrimitiveId(BLACK_BOX_CIRCLE_PLUGIN_ID, "hidden_point2"),
        (point_signature,),
        _smooth_kernel(hidden_point2);
        documentation = "Construct a point whose representation remains plugin-private",
    )
    circle = RelationSpec(
        PrimitiveId(BLACK_BOX_CIRCLE_PLUGIN_ID, "unit_circle"),
        (circle_signature,),
        _smooth_kernel(unit_circle_residual);
        truth = unit_circle_truth,
        truth_policy = RELATION_TRUTH_APPROXIMATE_ZERO,
        scale_hint = 1.0,
        documentation = "Point lies on the unit circle",
    )

    return PluginSpec(
        BLACK_BOX_CIRCLE_PLUGIN_ID,
        v"0.1.0",
        v"1.0.0",
        BLACK_BOX_CIRCLE_CONTENT_HASH;
        types = (hidden_point,),
        primitives = (point,),
        relations = (circle,),
    )
end

const _PLUGIN = _build_plugin()

"""Return the immutable plugin specification; no global registry is mutated."""
black_box_circle_plugin() = _PLUGIN

end
