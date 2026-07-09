const GEOMETRY_PLUGIN_ID =
    parse(PluginId, "5cba7841-765c-4ef1-987e-27fcb9985e3d/builtin_geometry")
const GEOMETRY_PLUGIN_VERSION = v"0.1.0"
const GEOMETRY_CORE_ABI = v"1.0.0"

const SCALAR_TYPE_ID = TypeId(GEOMETRY_PLUGIN_ID, "scalar")
const POINT_TYPE_ID = TypeId(GEOMETRY_PLUGIN_ID, "point2")
const LINE_TYPE_ID = TypeId(GEOMETRY_PLUGIN_ID, "line2")
const CIRCLE_TYPE_ID = TypeId(GEOMETRY_PLUGIN_ID, "circle2")
const CHOICE_TYPE_ID = TypeId(GEOMETRY_PLUGIN_ID, "choice")

# This canonical manifest source is intentionally explicit during M1. The build
# pipeline will generate it from PluginSpec metadata once code generation lands.
const _GEOMETRY_MANIFEST_V1 = join(
    (
        "plugin=5cba7841-765c-4ef1-987e-27fcb9985e3d/builtin_geometry@0.1.0",
        "types=scalar,point2,line2,circle2,choice",
        "primitives=point2,line_through,circle2,distance",
        "relations=scalar_equality",
        "guards=positive",
        "domains=safe_geometry_domain",
        "branches=line_circle_intersections",
        "selectors=near,far,orientation",
        "capabilities=numeric_generic_float64_bigfloat",
    ),
    "\n",
)
const GEOMETRY_CONTENT_HASH = content_hash(_GEOMETRY_MANIFEST_V1)

function _smooth_kernel(evaluator)
    return OperatorKernel(
        evaluator;
        capabilities = CapabilitySet(C0, C1, C2),
        smoothness = SMOOTH_C1,
        derivative_mode = DERIVATIVE_AUTODIFF,
        generic_numeric = true,
    )
end

function _generic_kernel(evaluator, smoothness::SmoothnessClass)
    return OperatorKernel(
        evaluator;
        capabilities = CapabilitySet(C0, C2),
        smoothness,
        generic_numeric = true,
    )
end

function _piecewise_derivative_kernel(evaluator)
    return OperatorKernel(
        evaluator;
        capabilities = CapabilitySet(C0, C1, C2),
        smoothness = PIECEWISE_SMOOTH,
        derivative_mode = DERIVATIVE_AUTODIFF,
        generic_numeric = true,
    )
end

function _build_geometry_plugin()
    scalar = TypeSpec(SCALAR_TYPE_ID, Real; documentation = "Real scalar")
    point = TypeSpec(POINT_TYPE_ID, Point2; documentation = "Cartesian Point2{T}")
    line = TypeSpec(LINE_TYPE_ID, Line2; documentation = "Directed unnormalized Line2{T}")
    circle = TypeSpec(CIRCLE_TYPE_ID, Circle2; documentation = "Circle2{T}")
    choice = TypeSpec(CHOICE_TYPE_ID, Choice; documentation = "Finite branch Choice")

    point_signature = SignatureSpec((SCALAR_TYPE_ID, SCALAR_TYPE_ID), POINT_TYPE_ID)
    line_signature = SignatureSpec((POINT_TYPE_ID, POINT_TYPE_ID), LINE_TYPE_ID)
    circle_signature = SignatureSpec((POINT_TYPE_ID, SCALAR_TYPE_ID), CIRCLE_TYPE_ID)
    distance_signature = SignatureSpec((POINT_TYPE_ID, POINT_TYPE_ID), SCALAR_TYPE_ID)
    equality_signature = SignatureSpec((SCALAR_TYPE_ID, SCALAR_TYPE_ID), SCALAR_TYPE_ID)
    scalar_margin_signature = SignatureSpec((SCALAR_TYPE_ID,), SCALAR_TYPE_ID)
    line_domain_signature = SignatureSpec((LINE_TYPE_ID,), SCALAR_TYPE_ID)
    circle_domain_signature = SignatureSpec((CIRCLE_TYPE_ID,), SCALAR_TYPE_ID)
    intersection_signature = SignatureSpec((LINE_TYPE_ID, CIRCLE_TYPE_ID), CHOICE_TYPE_ID)
    point_selector_signature = SignatureSpec(
        (CHOICE_TYPE_ID, POINT_TYPE_ID),
        POINT_TYPE_ID,
    )
    orientation_selector_signature = SignatureSpec(
        (CHOICE_TYPE_ID, POINT_TYPE_ID, POINT_TYPE_ID),
        POINT_TYPE_ID,
    )

    primitives = (
        PrimitiveSpec(
            PrimitiveId(GEOMETRY_PLUGIN_ID, "point2"),
            (point_signature,),
            _smooth_kernel(point2),
        ),
        PrimitiveSpec(
            PrimitiveId(GEOMETRY_PLUGIN_ID, "line_through"),
            (line_signature,),
            _smooth_kernel(line_through),
        ),
        PrimitiveSpec(
            PrimitiveId(GEOMETRY_PLUGIN_ID, "circle2"),
            (circle_signature,),
            _smooth_kernel(circle2),
        ),
        PrimitiveSpec(
            PrimitiveId(GEOMETRY_PLUGIN_ID, "distance"),
            (distance_signature,),
            _generic_kernel(distance, LOCALLY_LIPSCHITZ),
        ),
    )

    relation = RelationSpec(
        PrimitiveId(GEOMETRY_PLUGIN_ID, "scalar_equality"),
        (equality_signature,),
        _smooth_kernel(scalar_equality_residual);
        truth = scalar_equality_truth,
        scale_hint = 1.0,
    )
    guard = GuardSpec(
        PrimitiveId(GEOMETRY_PLUGIN_ID, "positive"),
        (scalar_margin_signature,),
        _smooth_kernel(positive_margin);
        default_strict = true,
        scale_hint = 1.0,
    )
    domain = DomainSpec(
        PrimitiveId(GEOMETRY_PLUGIN_ID, "safe_geometry_domain"),
        (line_domain_signature, circle_domain_signature),
        _smooth_kernel(safe_domain_margin);
        singularity = safe_domain_singularity,
        default_strict = true,
    )
    branch = BranchSpec(
        PrimitiveId(GEOMETRY_PLUGIN_ID, "line_circle_intersections"),
        (intersection_signature,),
        POINT_TYPE_ID,
        _piecewise_derivative_kernel(line_circle_intersections),
    )
    selectors = (
        SelectorSpec(
            SelectorId(GEOMETRY_PLUGIN_ID, "near"),
            (point_selector_signature,),
            _generic_kernel(select_near, PIECEWISE_SMOOTH),
        ),
        SelectorSpec(
            SelectorId(GEOMETRY_PLUGIN_ID, "far"),
            (point_selector_signature,),
            _generic_kernel(select_far, PIECEWISE_SMOOTH),
        ),
        SelectorSpec(
            SelectorId(GEOMETRY_PLUGIN_ID, "orientation"),
            (orientation_selector_signature,),
            _generic_kernel(select_orientation, PIECEWISE_SMOOTH),
        ),
    )

    return PluginSpec(
        GEOMETRY_PLUGIN_ID,
        GEOMETRY_PLUGIN_VERSION,
        GEOMETRY_CORE_ABI,
        GEOMETRY_CONTENT_HASH;
        types = (scalar, point, line, circle, choice),
        primitives,
        relations = (relation,),
        guards = (guard,),
        domains = (domain,),
        branches = (branch,),
        selectors,
    )
end

const _GEOMETRY_PLUGIN = _build_geometry_plugin()

"""Return the immutable built-in geometry PluginSpec without global registration."""
geometry_plugin() = _GEOMETRY_PLUGIN
