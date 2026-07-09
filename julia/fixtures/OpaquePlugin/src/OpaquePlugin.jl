module OpaquePlugin

using GeoTargetBase
using GeoTargetGeometry

export OpaqueValue,
    opaque_iterate,
    opaque_scalar,
    float64_only,
    log_exp,
    positive_log_domain,
    OPAQUE_PLUGIN_ID,
    OPAQUE_VALUE_TYPE_ID,
    OPAQUE_CONTENT_HASH,
    opaque_plugin

struct OpaqueValue{T<:Real}
    value::T
    iterations::Int
end

function opaque_iterate(input::T) where {T<:Real}
    value = input
    for _ in 1:7
        value = (sin(value) + cos(input) + exp(-(value * value))) / 3
    end
    return OpaqueValue(value, 7)
end

opaque_scalar(value::OpaqueValue) = value.value

"""Intentionally C0/Float64-only to test explicit capability loss."""
float64_only(value::Float64) = sin(value) + cos(value) + exp(-value)

"""Deliberately unsafe outside the separately declared positive domain."""
log_exp(value::Real) = log(value) + exp(-value)
positive_log_domain(value::Real) = value
positive_log_singularity(value::Real) = iszero(value)

const OPAQUE_PLUGIN_ID =
    parse(PluginId, "0b55885b-a501-4fb7-85a7-12d538c02ef8/opaque_fixture")
const OPAQUE_VALUE_TYPE_ID = TypeId(OPAQUE_PLUGIN_ID, "opaque_value")

# M1 canonical manifest source; generated from PluginSpec in a later build phase.
const _OPAQUE_MANIFEST_V1 = join(
    (
        "plugin=0b55885b-a501-4fb7-85a7-12d538c02ef8/opaque_fixture@0.1.0",
        "types=opaque_value",
        "primitives=opaque_iterate,opaque_scalar,float64_only,log_exp",
        "domains=positive_log_domain",
        "capabilities=float64_only_and_numeric_generic_bigfloat",
    ),
    "\n",
)
const OPAQUE_CONTENT_HASH = content_hash(_OPAQUE_MANIFEST_V1)

function _generic_smooth_kernel(evaluator)
    return OperatorKernel(
        evaluator;
        capabilities = CapabilitySet(C0, C1, C2),
        smoothness = SMOOTH_C1,
        derivative_mode = DERIVATIVE_AUTODIFF,
        generic_numeric = true,
    )
end

function _build_opaque_plugin()
    opaque_type = TypeSpec(
        OPAQUE_VALUE_TYPE_ID,
        OpaqueValue;
        documentation = "Opaque iterative result type",
    )
    iterate_signature = SignatureSpec((SCALAR_TYPE_ID,), OPAQUE_VALUE_TYPE_ID)
    extract_signature = SignatureSpec((OPAQUE_VALUE_TYPE_ID,), SCALAR_TYPE_ID)
    scalar_signature = SignatureSpec((SCALAR_TYPE_ID,), SCALAR_TYPE_ID)
    primitives = (
        PrimitiveSpec(
            PrimitiveId(OPAQUE_PLUGIN_ID, "opaque_iterate"),
            (iterate_signature,),
            _generic_smooth_kernel(opaque_iterate),
        ),
        PrimitiveSpec(
            PrimitiveId(OPAQUE_PLUGIN_ID, "opaque_scalar"),
            (extract_signature,),
            _generic_smooth_kernel(opaque_scalar),
        ),
        PrimitiveSpec(
            PrimitiveId(OPAQUE_PLUGIN_ID, "float64_only"),
            (scalar_signature,),
            OperatorKernel(
                float64_only;
                capabilities = CapabilitySet(C0),
                smoothness = SMOOTH_C1,
            ),
        ),
        PrimitiveSpec(
            PrimitiveId(OPAQUE_PLUGIN_ID, "log_exp"),
            (scalar_signature,),
            _generic_smooth_kernel(log_exp),
        ),
    )
    domain = DomainSpec(
        PrimitiveId(OPAQUE_PLUGIN_ID, "positive_log_domain"),
        (scalar_signature,),
        _generic_smooth_kernel(positive_log_domain);
        singularity = positive_log_singularity,
        default_strict = true,
    )
    return PluginSpec(
        OPAQUE_PLUGIN_ID,
        v"0.1.0",
        v"1.0.0",
        OPAQUE_CONTENT_HASH;
        types = (opaque_type,),
        primitives,
        domains = (domain,),
    )
end

const _OPAQUE_PLUGIN = _build_opaque_plugin()
opaque_plugin() = _OPAQUE_PLUGIN

end
