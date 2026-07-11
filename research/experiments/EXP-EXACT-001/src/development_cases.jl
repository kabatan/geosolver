struct DevelopmentCaseInput
    id::String
    compiled::GeoTargetCore.CompiledProblem
end

struct DevelopmentTruth
    family::Symbol
    target_approximations::Tuple
end

struct DevelopmentFixture
    input::DevelopmentCaseInput
    truth::DevelopmentTruth
end

function _registry(plugin)
    builder = RegistryBuilder(allowlist=(plugin.id,))
    register!(builder, plugin)
    return freeze(builder)
end

function _polynomial_case(id, relation_name, start, constant; bounds=(0.0, 3.0))
    plugin = development_polynomial_plugin()
    variable = VariableSpec(
        VariableId("x"),
        DEV_POLYNOMIAL_SCALAR,
        Float64(start),
        1.0;
        lower=Float64(first(bounds)),
        upper=Float64(last(bounds)),
    )
    graph = ConstructionGraph((
        ReferenceNode(NodeId("x_ref"), variable.id),
        LiteralNode(NodeId("constant"), DEV_POLYNOMIAL_SCALAR, Float64(constant)),
        CallNode(
            NodeId("relation"),
            PrimitiveId(DEV_POLYNOMIAL_PLUGIN_ID, relation_name),
            (NodeId("x_ref"), NodeId("constant")),
        ),
    ))
    problem = ProblemSpecV1(
        (plugin_lock(plugin),),
        (variable,),
        graph;
        relations=(RelationBinding(NodeId("relation")),),
        target=NodeId("x_ref"),
    )
    return DevelopmentCaseInput(String(id), compile_problem(problem, _registry(plugin)))
end

function _triangular_case()
    plugin = development_polynomial_plugin()
    x = VariableSpec(
        VariableId("x"), DEV_POLYNOMIAL_SCALAR, 0.48, 1.0; lower=-2.0, upper=2.0,
    )
    y = VariableSpec(
        VariableId("y"), DEV_POLYNOMIAL_SCALAR, 1.22, 1.0; lower=-2.0, upper=3.0,
    )
    graph = ConstructionGraph((
        ReferenceNode(NodeId("x_ref"), x.id),
        ReferenceNode(NodeId("y_ref"), y.id),
        LiteralNode(NodeId("half"), DEV_POLYNOMIAL_SCALAR, 0.5),
        LiteralNode(NodeId("three_quarters"), DEV_POLYNOMIAL_SCALAR, 0.75),
        CallNode(
            NodeId("x_relation"),
            PrimitiveId(DEV_POLYNOMIAL_PLUGIN_ID, "affine_root"),
            (NodeId("x_ref"), NodeId("half")),
        ),
        CallNode(
            NodeId("y_relation"),
            PrimitiveId(DEV_POLYNOMIAL_PLUGIN_ID, "triangular_step"),
            (NodeId("y_ref"), NodeId("x_ref"), NodeId("three_quarters")),
        ),
    ))
    problem = ProblemSpecV1(
        (plugin_lock(plugin),),
        (x, y),
        graph;
        relations=(
            RelationBinding(NodeId("x_relation")),
            RelationBinding(NodeId("y_relation")),
        ),
        target=NodeId("y_ref"),
    )
    return DevelopmentCaseInput(
        "dev-rational-triangular",
        compile_problem(problem, _registry(plugin)),
    )
end

function _branch_case(id, start)
    plugin = development_branch_plugin()
    variable = VariableSpec(
        VariableId("x"), DEV_BRANCH_SCALAR, Float64(start), 1.0; lower=-2.0, upper=2.0,
    )
    graph = ConstructionGraph((
        ReferenceNode(NodeId("x_ref"), variable.id),
        LiteralNode(NodeId("two"), DEV_BRANCH_SCALAR, 2.0),
        CallNode(
            NodeId("relation"),
            PrimitiveId(DEV_BRANCH_PLUGIN_ID, "signed_quadratic_root"),
            (NodeId("x_ref"), NodeId("two")),
        ),
        CallNode(
            NodeId("choice"),
            PrimitiveId(DEV_BRANCH_PLUGIN_ID, "signed_choice"),
            (NodeId("x_ref"),),
        ),
        SelectNode(
            NodeId("selected"),
            NodeId("choice"),
            SelectorId(DEV_BRANCH_PLUGIN_ID, "select_signed_root"),
        ),
    ))
    problem = ProblemSpecV1(
        (plugin_lock(plugin),),
        (variable,),
        graph;
        relations=(RelationBinding(NodeId("relation")),),
        target=NodeId("selected"),
    )
    return DevelopmentCaseInput(String(id), compile_problem(problem, _registry(plugin)))
end

"""Development-only fixtures. These are never formal X1 or U4 inputs."""
function development_fixtures()
    fixtures = DevelopmentFixture[
        DevelopmentFixture(
            _triangular_case(),
            DevelopmentTruth(:rational_triangular, (1.25,)),
        ),
        DevelopmentFixture(
            _polynomial_case("dev-quadratic-radical", "power_2", 1.4, 2.0),
            DevelopmentTruth(:quadratic_radical, (sqrt(2.0),)),
        ),
    ]
    for degree in (3, 5, 8, 12)
        push!(
            fixtures,
            DevelopmentFixture(
                _polynomial_case(
                    "dev-higher-degree-$degree",
                    "power_$degree",
                    2.0^(1 / degree),
                    2.0,
                ),
                DevelopmentTruth(:higher_algebraic, (2.0^(1 / degree),)),
            ),
        )
    end
    push!(
        fixtures,
        DevelopmentFixture(
            _polynomial_case("dev-isolated-singular", "isolated_double_root", 1.0, 1.0),
            DevelopmentTruth(:isolated_singular, (1.0,)),
        ),
        DevelopmentFixture(
            _branch_case("dev-stable-branch-positive", 1.4),
            DevelopmentTruth(:stable_branch_multitarget, (sqrt(2.0), -sqrt(2.0))),
        ),
        DevelopmentFixture(
            _branch_case("dev-stable-branch-negative", -1.4),
            DevelopmentTruth(:stable_branch_multitarget, (sqrt(2.0), -sqrt(2.0))),
        ),
    )
    return fixtures
end

