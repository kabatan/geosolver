module QA02Fuzz

using GeoTargetBase
using GeoTargetCore
using GeoTargetGeometry
using Random

const GENERATOR_VERSION = v"1.0.0"
const SUMMARY_SCHEMA = "geotarget.qa02-fuzz-summary/v1"
const GRAPH_SEED = UInt64(0x5141_3032_4752_4150)
const SOLVE_SEED = UInt64(0x5141_3032_534f_4c56)
const C2_PRECISION_BITS = 256
const NIGHTLY_GRAPH_MINIMUM = 10_000
const NIGHTLY_SOLVE_MINIMUM = 1_000

const QA02_PLUGIN_ID =
    parse(PluginId, "2ea66913-2e34-4fe8-9586-f407175fe38d/qa02_fuzz_fixture")
const QA02_OPAQUE_TYPE_ID = TypeId(QA02_PLUGIN_ID, "opaque_scalar")

"""Typed, seed-addressable invariant failure emitted by the QA-02 runner."""
struct QA02Failure <: Exception
    phase::Symbol
    case_index::Int
    seed::UInt64
    invariant::Symbol
    detail::String
end

function Base.showerror(io::IO, failure::QA02Failure)
    print(
        io,
        "GeoTarget QA-02 ",
        failure.phase,
        " failure at case ",
        failure.case_index,
        " (seed=", failure.seed, ", invariant=", failure.invariant, "): ",
        failure.detail,
    )
end

function _check(
    condition::Bool,
    phase::Symbol,
    case_index::Int,
    seed::UInt64,
    invariant::Symbol,
    detail::AbstractString,
)
    condition || throw(QA02Failure(phase, case_index, seed, invariant, String(detail)))
    return nothing
end

"""An immutable plugin-owned value that the compiler must treat as opaque."""
struct OpaqueScalar{T<:Real}
    value::T
    stamp::Int
end

_affine(value::Real, scale::Real, offset::Real) = scale * value + offset
_opaque(value::T) where {T<:Real} = OpaqueScalar(value, 17)
_unbox(value::OpaqueScalar) = value.value
_positive_margin(value::Real) = value
_interval_margin(value::Real, limit::Real) = limit * limit - value * value
_scaled_difference(left::Real, right::Real, scale::Real) = scale * (left - right)
_scaled_difference_truth(left::Real, right::Real, ::Real) = left == right

function _paired_opaque(center::Real, delta::Real, order::Real)
    promoted_center, promoted_delta = promote(center, delta)
    left = OpaqueScalar(promoted_center - promoted_delta, 1)
    right = OpaqueScalar(promoted_center + promoted_delta, 2)
    validity = promoted_delta
    if order < zero(order)
        return Choice((right, left), ("right", "left"), (validity, validity))
    end
    return Choice((left, right), ("left", "right"), (validity, validity))
end

function _select_near_opaque(choice::Choice, reference::Real)
    isempty(choice) && throw(DomainError(choice, "cannot select from an empty Choice"))
    distances = map(candidate -> abs(candidate.value - reference), choice.candidates)
    order = sortperm(collect(eachindex(distances)); by=index -> (distances[index], string(choice.keys[index])))
    selected = first(order)
    margin = length(order) == 1 ? oftype(distances[selected], Inf) :
             distances[order[2]] - distances[selected]
    return Selection(choice, selected, margin)
end

function _generic_kernel(evaluator; smoothness=SMOOTH_C1)
    return OperatorKernel(
        evaluator;
        capabilities=CapabilitySet(C0, C1, C2),
        smoothness,
        derivative_mode=DERIVATIVE_AUTODIFF,
        generic_numeric=true,
    )
end

function _build_plugin()
    scalar3 = SignatureSpec(
        (SCALAR_TYPE_ID, SCALAR_TYPE_ID, SCALAR_TYPE_ID),
        SCALAR_TYPE_ID,
    )
    scalar1 = SignatureSpec((SCALAR_TYPE_ID,), SCALAR_TYPE_ID)
    scalar2 = SignatureSpec((SCALAR_TYPE_ID, SCALAR_TYPE_ID), SCALAR_TYPE_ID)
    box_signature = SignatureSpec((SCALAR_TYPE_ID,), QA02_OPAQUE_TYPE_ID)
    unbox_signature = SignatureSpec((QA02_OPAQUE_TYPE_ID,), SCALAR_TYPE_ID)
    branch_signature = SignatureSpec(
        (SCALAR_TYPE_ID, SCALAR_TYPE_ID, SCALAR_TYPE_ID),
        CHOICE_TYPE_ID,
    )
    selector_signature = SignatureSpec(
        (CHOICE_TYPE_ID, SCALAR_TYPE_ID),
        QA02_OPAQUE_TYPE_ID,
    )
    primitives = (
        PrimitiveSpec(
            PrimitiveId(QA02_PLUGIN_ID, "affine"),
            (scalar3,),
            _generic_kernel(_affine),
        ),
        PrimitiveSpec(
            PrimitiveId(QA02_PLUGIN_ID, "opaque"),
            (box_signature,),
            _generic_kernel(_opaque),
        ),
        PrimitiveSpec(
            PrimitiveId(QA02_PLUGIN_ID, "unbox"),
            (unbox_signature,),
            _generic_kernel(_unbox),
        ),
    )
    relation = RelationSpec(
        PrimitiveId(QA02_PLUGIN_ID, "scaled_difference"),
        (scalar3,),
        _generic_kernel(_scaled_difference);
        truth=_scaled_difference_truth,
        truth_policy=RELATION_TRUTH_APPROXIMATE_ZERO,
    )
    guard = GuardSpec(
        PrimitiveId(QA02_PLUGIN_ID, "positive_margin"),
        (scalar1,),
        _generic_kernel(_positive_margin);
        default_strict=true,
        scale_hint=1.0,
    )
    domain = DomainSpec(
        PrimitiveId(QA02_PLUGIN_ID, "interval_margin"),
        (scalar2,),
        _generic_kernel(_interval_margin);
        default_strict=true,
    )
    branch = BranchSpec(
        PrimitiveId(QA02_PLUGIN_ID, "paired_opaque"),
        (branch_signature,),
        QA02_OPAQUE_TYPE_ID,
        _generic_kernel(_paired_opaque; smoothness=PIECEWISE_SMOOTH),
    )
    selector = SelectorSpec(
        SelectorId(QA02_PLUGIN_ID, "near_opaque"),
        (selector_signature,),
        _generic_kernel(_select_near_opaque; smoothness=PIECEWISE_SMOOTH),
    )
    return PluginSpec(
        QA02_PLUGIN_ID,
        v"1.0.0",
        GeoTargetCore.CORE_ABI_VERSION,
        content_hash("geotarget-qa02-fuzz-plugin-v1");
        types=(TypeSpec(QA02_OPAQUE_TYPE_ID, OpaqueScalar),),
        primitives,
        relations=(relation,),
        guards=(guard,),
        domains=(domain,),
        branches=(branch,),
        selectors=(selector,),
    )
end

const _QA02_PLUGIN = _build_plugin()

function qa02_registry()
    geometry = geometry_plugin()
    builder = RegistryBuilder(allowlist=(geometry.id, _QA02_PLUGIN.id))
    register!(builder, geometry)
    register!(builder, _QA02_PLUGIN)
    return freeze(builder)
end

_op(name) = PrimitiveId(QA02_PLUGIN_ID, name)

function _case_seed(namespace::UInt64, index::Integer)
    # SplitMix64 makes every generated case independently replayable without
    # sharing mutable RNG state with the solver.
    value = namespace + UInt64(index) * UInt64(0x9e37_79b9_7f4a_7c15)
    value = xor(value, value >> 30) * UInt64(0xbf58_476d_1ce4_e5b9)
    value = xor(value, value >> 27) * UInt64(0x94d0_49bb_1331_11eb)
    return xor(value, value >> 31)
end

_dyadic(rng, numerators, denominator=8) = rand(rng, numerators) / denominator

struct GraphPair
    base::ProblemSpecV1
    transformed::ProblemSpecV1
    family::Symbol
    target_scale::Float64
    target_offset::Float64
end

function _leaf_nodes(parameters)
    return AbstractGraphNode[
        ReferenceNode(NodeId("x-ref"), VariableId("x")),
        LiteralNode(NodeId("a"), SCALAR_TYPE_ID, parameters.a),
        LiteralNode(NodeId("b"), SCALAR_TYPE_ID, parameters.b),
        LiteralNode(NodeId("zero"), SCALAR_TYPE_ID, 0.0),
        LiteralNode(NodeId("one-a"), SCALAR_TYPE_ID, 1.0),
        LiteralNode(NodeId("one-b"), SCALAR_TYPE_ID, 1.0),
        LiteralNode(NodeId("relation-scale"), SCALAR_TYPE_ID, parameters.relation_scale),
        LiteralNode(NodeId("redundant-scale-a"), SCALAR_TYPE_ID, 2.0),
        LiteralNode(NodeId("redundant-scale-b"), SCALAR_TYPE_ID, 8.0),
        LiteralNode(NodeId("target-scale"), SCALAR_TYPE_ID, parameters.target_scale),
        LiteralNode(NodeId("target-offset"), SCALAR_TYPE_ID, parameters.target_offset),
        LiteralNode(NodeId("limit"), SCALAR_TYPE_ID, parameters.limit),
        LiteralNode(NodeId("delta"), SCALAR_TYPE_ID, parameters.delta),
        LiteralNode(NodeId("branch-order"), SCALAR_TYPE_ID, parameters.branch_order),
        LiteralNode(NodeId("branch-offset"), SCALAR_TYPE_ID, parameters.branch_offset),
        LiteralNode(NodeId("dead-value"), SCALAR_TYPE_ID, parameters.dead),
        LiteralNode(NodeId("dead-literal"), SCALAR_TYPE_ID, -parameters.dead),
    ]
end

function _append_signal_nodes!(nodes, family::Symbol; transformed::Bool)
    if transformed
        push!(
            nodes,
            CallNode(
                NodeId("linear-partial"),
                _op("affine"),
                (NodeId("x-ref"), NodeId("a"), NodeId("zero")),
            ),
        )
        push!(
            nodes,
            CallNode(
                NodeId("linear"),
                _op("affine"),
                (NodeId("linear-partial"), NodeId("one-a"), NodeId("b")),
            ),
        )
    else
        push!(
            nodes,
            CallNode(
                NodeId("linear"),
                _op("affine"),
                (NodeId("x-ref"), NodeId("a"), NodeId("b")),
            ),
        )
    end
    if family === :scalar
        push!(
            nodes,
            CallNode(
                NodeId("signal"),
                _op("affine"),
                (NodeId("linear"), NodeId("one-a"), NodeId("zero")),
            ),
        )
    elseif family === :opaque
        push!(nodes, CallNode(NodeId("boxed"), _op("opaque"), (NodeId("linear"),)))
        push!(nodes, CallNode(NodeId("signal"), _op("unbox"), (NodeId("boxed"),)))
    elseif family === :branch
        push!(
            nodes,
            CallNode(
                NodeId("branch-reference"),
                _op("affine"),
                (NodeId("linear"), NodeId("one-a"), NodeId("branch-offset")),
            ),
        )
        push!(
            nodes,
            CallNode(
                NodeId("choice"),
                _op("paired_opaque"),
                (NodeId("linear"), NodeId("delta"), NodeId("branch-order")),
            ),
        )
        push!(
            nodes,
            SelectNode(
                NodeId("selected"),
                NodeId("choice"),
                SelectorId(QA02_PLUGIN_ID, "near_opaque"),
                (NodeId("branch-reference"),),
            ),
        )
        push!(nodes, CallNode(NodeId("signal"), _op("unbox"), (NodeId("selected"),)))
    else
        throw(ArgumentError("unknown graph family $family"))
    end
    return nodes
end

function _graph_problem(parameters, family::Symbol; transformed::Bool, rng)
    variable = VariableSpec(
        VariableId("x"),
        SCALAR_TYPE_ID,
        parameters.origin,
        parameters.variable_scale;
        lower=-3.0,
        upper=3.0,
    )
    leaves = _leaf_nodes(parameters)
    if transformed
        shuffle!(rng, leaves)
    end
    nodes = AbstractGraphNode[leaves...]
    _append_signal_nodes!(nodes, family; transformed)

    # Both constant calls are live in the transformed redundant residuals. The
    # duplicate literal and equivalent arguments force safe constant CSE.
    push!(
        nodes,
        CallNode(
            NodeId("rhs-a"),
            _op("affine"),
            (NodeId("one-a"), NodeId("a"), NodeId("b")),
        ),
    )
    push!(
        nodes,
        CallNode(
            NodeId("rhs-b"),
            _op("affine"),
            (NodeId("one-b"), NodeId("a"), NodeId("b")),
        ),
    )
    push!(
        nodes,
        CallNode(
            NodeId("relation-1"),
            _op("scaled_difference"),
            (NodeId("signal"), NodeId("rhs-a"), NodeId("relation-scale")),
        ),
    )
    relation_bindings = RelationBinding[
        RelationBinding(NodeId("relation-1"); scale_override=parameters.relation_scale),
    ]
    if transformed
        push!(
            nodes,
            CallNode(
                NodeId("relation-2"),
                _op("scaled_difference"),
                (NodeId("signal"), NodeId("rhs-b"), NodeId("redundant-scale-a")),
            ),
        )
        push!(
            nodes,
            CallNode(
                NodeId("relation-3"),
                _op("scaled_difference"),
                (NodeId("signal"), NodeId("rhs-a"), NodeId("redundant-scale-b")),
            ),
        )
        push!(relation_bindings, RelationBinding(NodeId("relation-2"); scale_override=2.0))
        push!(relation_bindings, RelationBinding(NodeId("relation-3"); scale_override=8.0))
    end
    push!(nodes, CallNode(NodeId("guard"), _op("positive_margin"), (NodeId("signal"),)))
    push!(
        nodes,
        CallNode(
            NodeId("domain"),
            _op("interval_margin"),
            (NodeId("x-ref"), NodeId("limit")),
        ),
    )
    if transformed
        push!(
            nodes,
            CallNode(
                NodeId("target"),
                _op("affine"),
                (NodeId("signal"), NodeId("target-scale"), NodeId("target-offset")),
            ),
        )
    else
        push!(
            nodes,
            CallNode(
                NodeId("target"),
                _op("affine"),
                (NodeId("signal"), NodeId("one-a"), NodeId("zero")),
            ),
        )
    end
    push!(
        nodes,
        CallNode(
            NodeId("dead-call"),
            _op("affine"),
            (NodeId("dead-value"), NodeId("a"), NodeId("b")),
        ),
    )
    graph = ConstructionGraph(Tuple(nodes))
    return ProblemSpecV1(
        (plugin_lock(geometry_plugin()), plugin_lock(_QA02_PLUGIN)),
        (variable,),
        graph;
        relations=Tuple(relation_bindings),
        guards=(GuardBinding(NodeId("guard"), true),),
        domains=(DomainBinding(NodeId("domain"), true),),
        target=NodeId("target"),
    )
end

function graph_pair(case_index::Int)
    seed = _case_seed(GRAPH_SEED, case_index)
    rng = MersenneTwister(seed)
    family = (:scalar, :opaque, :branch)[mod1(case_index, 3)]
    delta = _dyadic(rng, 2:8)
    select_right = isodd(rand(rng, UInt8))
    relation_scale = Float64(2.0 ^ rand(rng, -2:3))
    parameters = (
        a=_dyadic(rng, vcat(collect(-12:-2), collect(2:12))),
        b=_dyadic(rng, -8:8),
        relation_scale,
        target_scale=_dyadic(rng, vcat(collect(-8:-2), collect(2:8)), 4),
        target_offset=_dyadic(rng, -12:12),
        limit=_dyadic(rng, 8:24),
        delta,
        branch_order=1.0,
        branch_offset=(select_right ? 2.0 : -2.0) * delta,
        dead=_dyadic(rng, -32:32),
        origin=_dyadic(rng, -8:8),
        variable_scale=Float64(2.0 ^ rand(rng, -2:3)),
    )
    base = _graph_problem(parameters, family; transformed=false, rng)
    transformed_parameters = merge(parameters, (
        relation_scale=Float64(2.0 ^ rand(rng, -3:4)),
        branch_order=-1.0,
    ))
    transformed = _graph_problem(transformed_parameters, family; transformed=true, rng)
    return GraphPair(
        base,
        transformed,
        family,
        parameters.target_scale,
        parameters.target_offset,
    ), seed
end

function _semantic_projection(observation::OracleObservation)
    return (
        observation.status,
        observation.target,
        Tuple((r.node, r.raw, r.scale, r.scaled, r.truth) for r in observation.relations),
        Tuple((g.node, g.margin, g.strict, g.scale, g.valid) for g in observation.guards),
        Tuple((d.node, d.margin, d.strict, d.valid) for d in observation.domains),
        Tuple(
            (
                b.decision.choice_node,
                b.decision.key,
                b.validity_margin,
                b.selector_margin,
            ) for b in observation.branches
        ),
        observation.evaluation_cost,
        observation.diagnostic,
    )
end

function _approximately_equal(left::Real, right::Real)
    left == right && return true
    tolerance = 64 * eps(float(one(promote_type(typeof(left), typeof(right)))))
    return isapprox(left, right; rtol=tolerance, atol=tolerance)
end

function _metamorphic_check(
    base::OracleObservation,
    transformed::OracleObservation,
    pair::GraphPair,
    case_index::Int,
    seed::UInt64,
)
    _check(
        base.status == transformed.status,
        :graph,
        case_index,
        seed,
        :metamorphic_status,
        "status changed from $(base.status) to $(transformed.status)",
    )
    _check(
        length(base.relations) == 1 && length(transformed.relations) == 3,
        :graph,
        case_index,
        seed,
        :redundancy_shape,
        "expected one base and three transformed residuals",
    )
    baseline = only(base.relations)
    for relation in transformed.relations
        _check(
            _approximately_equal(baseline.scaled, relation.scaled),
            :graph,
            case_index,
            seed,
            :scaled_residual_equivalence,
            "scaled residual changed under positive scaling/redundancy",
        )
        _check(
            baseline.truth == relation.truth,
            :graph,
            case_index,
            seed,
            :relation_truth_equivalence,
            "relation truth changed under equivalent residual construction",
        )
    end
    _check(
        map(g -> (g.strict, g.valid), base.guards) ==
        map(g -> (g.strict, g.valid), transformed.guards),
        :graph,
        case_index,
        seed,
        :guard_equivalence,
        "guard semantics changed",
    )
    _check(
        map(d -> (d.strict, d.valid), base.domains) ==
        map(d -> (d.strict, d.valid), transformed.domains),
        :graph,
        case_index,
        seed,
        :domain_equivalence,
        "domain semantics changed",
    )
    _check(
        map(b -> (b.decision.key, b.validity_margin, b.selector_margin), base.branches) ==
        map(b -> (b.decision.key, b.validity_margin, b.selector_margin), transformed.branches),
        :graph,
        case_index,
        seed,
        :branch_order_equivalence,
        "stable branch selection changed when candidate order was reversed",
    )
    expected_target = pair.target_scale * base.target + pair.target_offset
    _check(
        _approximately_equal(expected_target, transformed.target),
        :graph,
        case_index,
        seed,
        :target_affine_equivalence,
        "target affine image differs from the declared map",
    )
    return nothing
end

function _observation_record(observation::OracleObservation, family::Symbol, capability)
    return Dict{String,Any}(
        "branches" => Any[
            Dict{String,Any}(
                "key" => string(branch.decision.key),
                "selector_margin" => Float64(branch.selector_margin),
                "validity_margin" => Float64(branch.validity_margin),
            ) for branch in observation.branches
        ],
        "capability" => string(capability),
        "domains" => Any[domain.valid for domain in observation.domains],
        "family" => String(family),
        "guards" => Any[guard.valid for guard in observation.guards],
        "relations" => Any[Float64(relation.scaled) for relation in observation.relations],
        "status" => string(observation.status),
        "target" => Float64(observation.target),
    )
end

function run_graph_suite(registry, requested::Int)
    requested > 0 || throw(ArgumentError("graph evaluation count must be positive"))
    completed = 0
    case_index = 0
    c0 = 0
    c2 = 0
    metamorphic_pairs = 0
    family_counts = Dict(:scalar => 0, :opaque => 0, :branch => 0)
    records = String[]
    while completed < requested
        case_index += 1
        pair, seed = graph_pair(case_index)
        base_compiled = compile_problem(pair.base, registry)
        transformed_compiled = compile_problem(pair.transformed, registry)
        _check(
            any(
                instruction -> instruction isa GeoTargetCore.AliasInstruction &&
                    instruction.node == NodeId("rhs-b"),
                transformed_compiled.instructions,
            ),
            :graph,
            case_index,
            seed,
            :constant_call_cse_exercised,
            "duplicate constant call rhs-b was not lowered to a CSE alias",
        )
        _check(
            base_compiled.stats.dead_nodes >= 1 && transformed_compiled.stats.dead_nodes >= 1,
            :graph,
            case_index,
            seed,
            :dce_exercised,
            "dead graph nodes were not removed",
        )
        _check(
            all(
                pair -> first(pair) != NodeId("dead-literal"),
                transformed_compiled.node_slots,
            ),
            :graph,
            case_index,
            seed,
            :literal_dce_exercised,
            "provably inert dead-literal remained in the compiled plan",
        )
        base_prefix = Tuple(string(node.id) for node in pair.base.graph.nodes[1:16])
        transformed_prefix = Tuple(string(node.id) for node in pair.transformed.graph.nodes[1:16])
        _check(
            base_prefix != transformed_prefix,
            :graph,
            case_index,
            seed,
            :ordering_exercised,
            "independent graph-node order was unchanged",
        )
        rng = MersenneTwister(xor(seed, UInt64(0xa5a5_a5a5_a5a5_a5a5)))
        for point_index in 1:10
            completed >= requested && break
            capability = isodd(point_index) ? C0 : C2
            coordinate = rand(rng, -40:40) / 16
            x = if capability == C0
                [Float64(coordinate)]
            else
                setprecision(BigFloat, C2_PRECISION_BITS) do
                    BigFloat[coordinate]
                end
            end
            base_reference = evaluate_reference(pair.base, registry, x; capability)
            base_observed = evaluate(base_compiled, x; capability)
            _check(
                _semantic_projection(base_reference) == _semantic_projection(base_observed),
                :graph,
                case_index,
                seed,
                :reference_compiled_differential,
                "base reference and compiled semantic projections differ",
            )
            push!(records, canonical_json(_observation_record(base_observed, pair.family, capability)))
            completed += 1
            family_counts[pair.family] += 1
            capability == C0 ? (c0 += 1) : (c2 += 1)
            completed >= requested && break

            transformed_reference =
                evaluate_reference(pair.transformed, registry, x; capability)
            transformed_observed = evaluate(transformed_compiled, x; capability)
            _check(
                _semantic_projection(transformed_reference) ==
                _semantic_projection(transformed_observed),
                :graph,
                case_index,
                seed,
                :reference_compiled_differential,
                "transformed reference and compiled semantic projections differ",
            )
            _metamorphic_check(
                base_observed,
                transformed_observed,
                pair,
                case_index,
                seed,
            )
            push!(
                records,
                canonical_json(_observation_record(
                    transformed_observed,
                    pair.family,
                    capability,
                )),
            )
            completed += 1
            metamorphic_pairs += 1
            family_counts[pair.family] += 1
            capability == C0 ? (c0 += 1) : (c2 += 1)
        end
    end
    _check(
        completed == requested,
        :graph,
        case_index,
        GRAPH_SEED,
        :count_shortfall,
        "completed $completed of $requested requested evaluations",
    )
    return Dict{String,Any}(
        "c0_evaluations" => c0,
        "c2_evaluations" => c2,
        "compiled_reference_matches" => completed,
        "digest" => string(content_hash(join(records, '\n'))),
        "families" => Dict{String,Any}(String(key) => value for (key, value) in family_counts),
        "generated_graph_pairs" => case_index,
        "metamorphic_pairs" => metamorphic_pairs,
        "ordering_cse_dce_pairs" => case_index,
        "redundancy_scaling_pairs" => metamorphic_pairs,
        "target_affine_pairs" => metamorphic_pairs,
    )
end

struct SolveTruth
    kind::Symbol
    finite_targets::Tuple
    finite_image::Bool
end

function _solve_problem(case_index::Int)
    seed = _case_seed(SOLVE_SEED, case_index)
    rng = MersenneTwister(seed)
    kind = (:valid_linear, :guard_rejected, :domain_rejected, :continuous, :constant)[
        mod1(case_index, 5)
    ]
    if kind === :constant
        target = rand(rng, -24:24) / 8
        problem = ProblemSpecV1(
            (plugin_lock(geometry_plugin()),),
            (),
            ConstructionGraph((LiteralNode(NodeId("target"), SCALAR_TYPE_ID, target),));
            target=NodeId("target"),
        )
        return problem, SolveTruth(kind, (target,), true), seed
    end

    root = if kind === :valid_linear
        rand(rng, 2:12) / 8
    elseif kind === :guard_rejected
        -rand(rng, 2:12) / 8
    elseif kind === :domain_rejected
        rand(rng, 10:14) / 8
    else
        rand(rng, -8:8) / 8
    end
    target_scale = rand(rng, vcat(collect(-8:-2), collect(2:8))) / 4
    target_offset = rand(rng, -12:12) / 8
    relation_scale = Float64(2.0 ^ rand(rng, -2:3))
    domain_limit = kind === :domain_rejected ? 0.75 : 2.5
    variable = VariableSpec(
        VariableId("x"),
        SCALAR_TYPE_ID,
        0.0,
        Float64(2.0 ^ rand(rng, -2:2));
        lower=-2.0,
        upper=2.0,
    )
    nodes = AbstractGraphNode[
        ReferenceNode(NodeId("x-ref"), variable.id),
        LiteralNode(NodeId("root"), SCALAR_TYPE_ID, root),
        LiteralNode(NodeId("relation-scale"), SCALAR_TYPE_ID, relation_scale),
        LiteralNode(NodeId("target-scale"), SCALAR_TYPE_ID, target_scale),
        LiteralNode(NodeId("target-offset"), SCALAR_TYPE_ID, target_offset),
        LiteralNode(NodeId("limit"), SCALAR_TYPE_ID, domain_limit),
        CallNode(
            NodeId("target"),
            _op("affine"),
            (NodeId("x-ref"), NodeId("target-scale"), NodeId("target-offset")),
        ),
        CallNode(NodeId("guard"), _op("positive_margin"), (NodeId("x-ref"),)),
        CallNode(
            NodeId("domain"),
            _op("interval_margin"),
            (NodeId("x-ref"), NodeId("limit")),
        ),
    ]
    relations = ()
    if kind !== :continuous
        push!(
            nodes,
            CallNode(
                NodeId("relation"),
                _op("scaled_difference"),
                (NodeId("x-ref"), NodeId("root"), NodeId("relation-scale")),
            ),
        )
        relations = (
            RelationBinding(NodeId("relation"); scale_override=relation_scale),
        )
    end
    problem = ProblemSpecV1(
        (plugin_lock(geometry_plugin()), plugin_lock(_QA02_PLUGIN)),
        (variable,),
        ConstructionGraph(Tuple(nodes));
        relations,
        guards=(GuardBinding(NodeId("guard"), true),),
        domains=(DomainBinding(NodeId("domain"), true),),
        target=NodeId("target"),
    )
    feasible = kind === :valid_linear
    target = target_scale * root + target_offset
    truth = SolveTruth(kind, feasible ? (target,) : (), kind !== :continuous)
    return problem, truth, seed
end

function _result_projection(result::SolveResult)
    return Dict{String,Any}(
        "coverage" => Dict{String,Any}(
            "completed" => result.coverage.completed_tasks,
            "iid" => result.coverage.independent_waves,
            "pending" => result.coverage.pending_tasks,
            "proposed" => result.coverage.proposed_tasks,
        ),
        "exact" => Any[
            Dict{String,Any}(
                "approximation" => Float64(answer.approximation),
                "coefficients" => Any[c.decimal for c in answer.identity.coefficients],
                "root_index" => answer.identity.real_root_index,
            ) for answer in result.exact_answers
        ],
        "provisional" => Any[
            Dict{String,Any}(
                "lower" => Float64(answer.target.lower),
                "residual_bound" => Float64(answer.canonical_residual_bound),
                "upper" => Float64(answer.target.upper),
            ) for answer in result.provisional_answers
        ],
        "search_status" => string(result.search_status),
        "target_image_status" => string(result.target_image_status),
    )
end

function _trace_without_pauses(execution::SolveExecution)
    document = Any[
        Dict{String,Any}(
            "kind" => string(event.kind),
            "payload" => GeoTargetCore._checkpoint_event_payload_document(
                event,
                "trace.payload",
            ),
        ) for event in execution.checkpoint.events if !(
            event.kind === GeoTargetCore.EVENT_STATUS &&
            event.payload.status === GeoTargetCore.LOOP_PAUSED
        )
    ]
    return canonical_json(document)
end

function _budget_tuple(snapshot)
    return (
        snapshot.proposals,
        snapshot.local_attempts,
        snapshot.refinements,
        snapshot.oracle_work,
    )
end

function _check_budget(execution::SolveExecution, case_index::Int, seed::UInt64)
    snapshot = execution.checkpoint.budget
    limits = snapshot.limits
    values = _budget_tuple(snapshot)
    ceilings = (limits.proposals, limits.local_attempts, limits.refinements, limits.oracle_work)
    _check(
        all(pair -> last(pair) === nothing || first(pair) <= last(pair), zip(values, ceilings)),
        :solve,
        case_index,
        seed,
        :budget_limit,
        "budget ledger exceeded its configured ceiling",
    )
    previous = (0, 0, 0, 0)
    for event in execution.checkpoint.events
        event.kind === GeoTargetCore.EVENT_BUDGET_CHARGED || continue
        current = _budget_tuple(event.payload.snapshot)
        _check(
            all(current .>= previous),
            :solve,
            case_index,
            seed,
            :budget_monotonicity,
            "budget counters decreased in the event log",
        )
        previous = current
    end
    _check(
        previous == values,
        :solve,
        case_index,
        seed,
        :budget_event_consistency,
        "final budget event does not match checkpoint ledger",
    )
    coverage = execution.result.coverage
    _check(
        coverage.proposed_tasks == snapshot.proposals &&
        coverage.completed_tasks == length(execution.checkpoint.workspace.candidates.history) &&
        coverage.pending_tasks == length(execution.checkpoint.workspace.pending),
        :solve,
        case_index,
        seed,
        :coverage_budget_consistency,
        "public coverage does not match checkpoint state",
    )
    _check(
        execution.loop_status ∉ (
            GeoTargetCore.LOOP_CALLBACK_ERROR,
            GeoTargetCore.LOOP_PROTOCOL_ERROR,
        ),
        :solve,
        case_index,
        seed,
        :typed_loop_completion,
        "bounded execution ended in callback/protocol failure",
    )
    return nothing
end

function _check_public_answers(
    result::SolveResult,
    truth::SolveTruth,
    case_index::Int,
    seed::UInt64,
)
    answers = (result.exact_answers..., result.provisional_answers...)
    if isempty(truth.finite_targets)
        _check(
            isempty(answers),
            :solve,
            case_index,
            seed,
            :false_public_answer,
            "$(truth.kind) has no finite isolated target but returned $(length(answers)) answers",
        )
        return nothing
    end
    targets = setprecision(BigFloat, C2_PRECISION_BITS) do
        Tuple(BigFloat(value) for value in truth.finite_targets)
    end
    for answer in result.exact_answers
        approximation = BigFloat(answer.approximation)
        _check(
            any(target -> isapprox(approximation, target; rtol=big"1e-40", atol=big"1e-40"), targets),
            :solve,
            case_index,
            seed,
            :false_public_answer,
            "exact-answer approximation is outside generated analytic truth",
        )
    end
    for answer in result.provisional_answers
        _check(
            any(target -> answer.target.lower <= target <= answer.target.upper, targets),
            :solve,
            case_index,
            seed,
            :false_public_answer,
            "provisional enclosure excludes every generated analytic target",
        )
    end
    return nothing
end

function _check_analytic_problem(problem, truth, registry, case_index, seed)
    truth.kind in (:constant, :continuous) && return nothing
    root_node = first(node for node in problem.graph if node.id == NodeId("root"))
    root = root_node.value
    observation = evaluate_reference(problem, registry, [root])
    expected_feasible = truth.kind === :valid_linear
    _check(
        canonical_feasible(observation; residual_tolerance=0.0) == expected_feasible,
        :solve,
        case_index,
        seed,
        :analytic_truth_fixture,
        "generated root feasibility disagrees with its analytic label",
    )
    return nothing
end

function _same_final_state(left::SolveExecution, right::SolveExecution)
    return canonical_json(_result_projection(left.result)) ==
           canonical_json(_result_projection(right.result)) &&
           canonical_json(GeoTargetCore._checkpoint_workspace_document(
        left.checkpoint.workspace,
    )) == canonical_json(GeoTargetCore._checkpoint_workspace_document(
        right.checkpoint.workspace,
    )) &&
           _budget_tuple(left.checkpoint.budget) == _budget_tuple(right.checkpoint.budget) &&
           _trace_without_pauses(left) == _trace_without_pauses(right)
end

function run_solve_suite(registry, requested::Int)
    requested > 0 || throw(ArgumentError("solve execution count must be positive"))
    requested % 4 == 0 || throw(
        ArgumentError("solve execution count must be divisible by four for replay/prefix/resume cycles"),
    )
    cycles = div(requested, 4)
    completed = 0
    checkpoint_resumes = 0
    false_public_answers = 0
    kind_counts = Dict(
        :valid_linear => 0,
        :guard_rejected => 0,
        :domain_rejected => 0,
        :continuous => 0,
        :constant => 0,
    )
    records = String[]
    ambient_precision = precision(BigFloat)
    process_rng = Random.default_rng()
    original_process_rng = copy(process_rng)
    Random.seed!(process_rng, UInt64(0x5141_3032_524e_4721))
    control_rng = copy(process_rng)

    for case_index in 1:cycles
        problem, truth, seed = _solve_problem(case_index)
        _check_analytic_problem(problem, truth, registry, case_index, seed)
        options = SolveOptions(
            preset=:fast,
            wall_seconds=30.0,
            seed=seed,
            answer_level=:exact_if_available,
        )
        full = solve_execution(problem, registry; options, max_actions=2)
        replay = solve_execution(problem, registry; options, max_actions=2)
        prefix = solve_execution(problem, registry; options, max_actions=1)
        checkpoint_source = encode_checkpoint_json(SolveCheckpointArtifact(prefix))
        checkpoint = decode_checkpoint_json(checkpoint_source)
        _check(
            encode_checkpoint_json(checkpoint) == checkpoint_source,
            :solve,
            case_index,
            seed,
            :checkpoint_canonical_roundtrip,
            "checkpoint bytes changed after typed decode/encode",
        )
        resumed = solve_execution(
            problem,
            registry;
            options,
            max_actions=1,
            checkpoint,
        )
        completed += 4
        checkpoint_resumes += 1
        kind_counts[truth.kind] += 4

        for execution in (full, replay, prefix, resumed)
            _check_budget(execution, case_index, seed)
            try
                _check_public_answers(execution.result, truth, case_index, seed)
            catch failure
                failure isa QA02Failure && failure.invariant === :false_public_answer &&
                    (false_public_answers += 1)
                rethrow()
            end
        end
        _check(
            full.evidence_json == replay.evidence_json,
            :solve,
            case_index,
            seed,
            :replay_determinism,
            "same seed/problem/action prefix produced a different evidence log",
        )
        _check(
            _same_final_state(full, resumed),
            :solve,
            case_index,
            seed,
            :checkpoint_prefix_determinism,
            "resumed action suffix differs from uninterrupted execution",
        )
        _check(
            precision(BigFloat) == ambient_precision,
            :solve,
            case_index,
            seed,
            :precision_leak,
            "solver changed ambient BigFloat precision",
        )
        _check(
            rand(process_rng, UInt64) == rand(control_rng, UInt64),
            :solve,
            case_index,
            seed,
            :rng_interference,
            "bounded solve activity consumed the process-default RNG",
        )
        push!(records, canonical_json(Dict{String,Any}(
            "budget" => Any[_budget_tuple(full.checkpoint.budget)...],
            "case" => case_index,
            "kind" => String(truth.kind),
            "result" => _result_projection(full.result),
        )))
    end
    copy!(process_rng, original_process_rng)
    _check(
        completed == requested,
        :solve,
        cycles,
        SOLVE_SEED,
        :count_shortfall,
        "completed $completed of $requested requested executions",
    )
    return Dict{String,Any}(
        "checkpoint_resumes" => checkpoint_resumes,
        "digest" => string(content_hash(join(records, '\n'))),
        "false_public_answers" => false_public_answers,
        "kinds" => Dict{String,Any}(String(key) => value for (key, value) in kind_counts),
        "prefix_determinism_cycles" => cycles,
        "precision_leaks" => 0,
        "replay_cycles" => cycles,
        "rng_interference_failures" => 0,
    )
end

function run_suite(
    ;
    graph_evaluations::Integer,
    solve_executions::Integer,
    require_nightly_minimum::Bool=false,
)
    graphs = Int(graph_evaluations)
    solves = Int(solve_executions)
    require_nightly_minimum && graphs < NIGHTLY_GRAPH_MINIMUM && throw(
        ArgumentError("Nightly requires at least $NIGHTLY_GRAPH_MINIMUM graph evaluations"),
    )
    require_nightly_minimum && solves < NIGHTLY_SOLVE_MINIMUM && throw(
        ArgumentError("Nightly requires at least $NIGHTLY_SOLVE_MINIMUM solve executions"),
    )
    registry = qa02_registry()
    graph = run_graph_suite(registry, graphs)
    solve = run_solve_suite(registry, solves)
    payload = Dict{String,Any}(
        "completed" => Dict{String,Any}(
            "graph_evaluations" => graph["compiled_reference_matches"],
            "solve_executions" => solves,
        ),
        "generator" => Dict{String,Any}(
            "c2_precision_bits" => C2_PRECISION_BITS,
            "graph_seed" => string(GRAPH_SEED),
            "solve_seed" => string(SOLVE_SEED),
            "version" => string(GENERATOR_VERSION),
        ),
        "graph" => graph,
        "requested" => Dict{String,Any}(
            "graph_evaluations" => graphs,
            "solve_executions" => solves,
        ),
        "schema" => SUMMARY_SCHEMA,
        "solve" => solve,
    )
    summary = copy(payload)
    summary["run_checksum"] = string(canonical_json_hash(payload))
    return summary
end

export GENERATOR_VERSION,
    SUMMARY_SCHEMA,
    NIGHTLY_GRAPH_MINIMUM,
    NIGHTLY_SOLVE_MINIMUM,
    QA02Failure,
    OpaqueScalar,
    qa02_registry,
    graph_pair,
    run_graph_suite,
    run_solve_suite,
    run_suite

end
