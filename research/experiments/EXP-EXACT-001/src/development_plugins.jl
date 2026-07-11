const DEV_POLYNOMIAL_PLUGIN_ID =
    parse(PluginId, "916c3665-4cf4-45d3-a22e-b77069fd469c/exp_exact_001_polynomial_dev")
const DEV_BRANCH_PLUGIN_ID =
    parse(PluginId, "e6b0a554-5761-4e02-9ef5-90fe290d1b71/exp_exact_001_branch_dev")

const DEV_POLYNOMIAL_SCALAR = TypeId(DEV_POLYNOMIAL_PLUGIN_ID, "scalar")
const DEV_BRANCH_SCALAR = TypeId(DEV_BRANCH_PLUGIN_ID, "scalar")
const DEV_BRANCH_CHOICE = TypeId(DEV_BRANCH_PLUGIN_ID, "choice")

_c3a_kernel(callback) = OperatorKernel(
    callback;
    algebraic_prover=callback,
    capabilities=CapabilitySet(C0, C2, C3A),
    generic_numeric=true,
    smoothness=SMOOTH_C1,
)

function _relation(plugin_id, name, signature, callback)
    return RelationSpec(
        PrimitiveId(plugin_id, name),
        (signature,),
        _c3a_kernel(callback);
        truth=(arguments...) -> iszero(callback(arguments...)),
        truth_policy=RELATION_TRUTH_APPROXIMATE_ZERO,
        scale_hint=1.0,
    )
end

function development_polynomial_plugin()
    binary = SignatureSpec((DEV_POLYNOMIAL_SCALAR, DEV_POLYNOMIAL_SCALAR), DEV_POLYNOMIAL_SCALAR)
    ternary = SignatureSpec(
        (DEV_POLYNOMIAL_SCALAR, DEV_POLYNOMIAL_SCALAR, DEV_POLYNOMIAL_SCALAR),
        DEV_POLYNOMIAL_SCALAR,
    )
    relations = RelationSpec[
        _relation(DEV_POLYNOMIAL_PLUGIN_ID, "affine_root", binary, (x, c) -> x - c),
        _relation(
            DEV_POLYNOMIAL_PLUGIN_ID,
            "triangular_step",
            ternary,
            (y, x, offset) -> y - x - offset,
        ),
        _relation(DEV_POLYNOMIAL_PLUGIN_ID, "power_2", binary, (x, c) -> x^2 - c),
        _relation(DEV_POLYNOMIAL_PLUGIN_ID, "power_3", binary, (x, c) -> x^3 - c),
        _relation(DEV_POLYNOMIAL_PLUGIN_ID, "power_5", binary, (x, c) -> x^5 - c),
        _relation(DEV_POLYNOMIAL_PLUGIN_ID, "power_8", binary, (x, c) -> x^8 - c),
        _relation(DEV_POLYNOMIAL_PLUGIN_ID, "power_12", binary, (x, c) -> x^12 - c),
        _relation(
            DEV_POLYNOMIAL_PLUGIN_ID,
            "isolated_double_root",
            binary,
            (x, c) -> (x - c)^2,
        ),
    ]
    return PluginSpec(
        DEV_POLYNOMIAL_PLUGIN_ID,
        v"0.1.0",
        GeoTargetCore.CORE_ABI_VERSION,
        content_hash("EXP-EXACT-001-development-polynomial-plugin-v1");
        types=(TypeSpec(DEV_POLYNOMIAL_SCALAR, Real),),
        relations=Tuple(relations),
    )
end

function development_branch_plugin()
    binary = SignatureSpec((DEV_BRANCH_SCALAR, DEV_BRANCH_SCALAR), DEV_BRANCH_SCALAR)
    choice_signature = SignatureSpec((DEV_BRANCH_SCALAR,), DEV_BRANCH_CHOICE)
    selector_signature = SignatureSpec((DEV_BRANCH_CHOICE,), DEV_BRANCH_SCALAR)
    root_relation = _relation(
        DEV_BRANCH_PLUGIN_ID,
        "signed_quadratic_root",
        binary,
        (x, c) -> x^2 - c,
    )
    signed_choice = function (x)
        key = x > zero(x) ? "positive" : "negative"
        return Choice((x,), (key,), (abs(x),))
    end
    choose = choice -> Selection(choice, 1, choice.validity_margins[1])
    branch = BranchSpec(
        PrimitiveId(DEV_BRANCH_PLUGIN_ID, "signed_choice"),
        (choice_signature,),
        DEV_BRANCH_SCALAR,
        _c3a_kernel(signed_choice),
    )
    selector = SelectorSpec(
        SelectorId(DEV_BRANCH_PLUGIN_ID, "select_signed_root"),
        (selector_signature,),
        _c3a_kernel(choose),
    )
    return PluginSpec(
        DEV_BRANCH_PLUGIN_ID,
        v"0.1.0",
        GeoTargetCore.CORE_ABI_VERSION,
        content_hash("EXP-EXACT-001-development-branch-plugin-v1");
        types=(
            TypeSpec(DEV_BRANCH_SCALAR, Real),
            TypeSpec(DEV_BRANCH_CHOICE, Choice),
        ),
        relations=(root_relation,),
        branches=(branch,),
        selectors=(selector,),
    )
end
