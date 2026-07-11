using GeoTargetBase
using GeoTargetCore
using GeoTargetGeometry
using Test

function hp_refinement_problem(; underdetermined::Bool=false)
    plugin = geometry_plugin()
    builder = RegistryBuilder(allowlist=(plugin.id,))
    register!(builder, plugin)
    registry = freeze(builder)
    x = VariableSpec(
        VariableId("hp_x"),
        SCALAR_TYPE_ID,
        0.0,
        1.0;
        lower=-2.0,
        upper=2.0,
    )
    variables = if underdetermined
        (
            x,
            VariableSpec(
                VariableId("hp_y"),
                SCALAR_TYPE_ID,
                0.0,
                1.0;
                lower=-2.0,
                upper=2.0,
            ),
        )
    else
        (x,)
    end
    nodes = AbstractGraphNode[
        ReferenceNode(NodeId("hp_x_ref"), x.id),
        LiteralNode(NodeId("hp_one"), SCALAR_TYPE_ID, underdetermined ? 0.0 : 1.0),
        CallNode(
            NodeId("hp_relation"),
            PrimitiveId(GEOMETRY_PLUGIN_ID, "scalar_equality"),
            (NodeId("hp_x_ref"), NodeId("hp_one")),
        ),
    ]
    target = NodeId("hp_x_ref")
    if underdetermined
        push!(nodes, ReferenceNode(NodeId("hp_y_ref"), variables[2].id))
        target = NodeId("hp_y_ref")
    end
    problem = ProblemSpecV1(
        (plugin_lock(plugin),),
        variables,
        ConstructionGraph(Tuple(nodes));
        relations=(RelationBinding(NodeId("hp_relation")),),
        target,
    )
    return compile_problem(problem, registry)
end

function run_hp_refinement(compiled, start; bits=512, kind=:compiled, kwargs...)
    return GeoTargetCore._run_high_precision_refinement(
        compiled,
        start;
        precision_bits=bits,
        evaluator_kind=kind,
        residual_goal=1.0e-110,
        configuration_tolerance=1.0e-100,
        target_tolerance=1.0e-100,
        kwargs...,
    )
end

@testset "five-point BigFloat CPQR refinement and independent reference run" begin
    compiled = hp_refinement_problem()
    primary = run_hp_refinement(compiled, [0.8])
    reference = run_hp_refinement(compiled, [0.8]; bits=768, kind=:reference)

    @test primary.accepted
    @test reference.accepted
    @test primary.evidence.precision_bits == 512
    @test reference.evidence.precision_bits == 768
    @test primary.evidence.residual_bound <= big"1e-110"
    @test reference.evidence.residual_bound <= big"1e-110"
    @test primary.evidence.correction_bound <= big"1e-100"
    @test reference.evidence.correction_bound <= big"1e-100"
    @test primary.evidence.target_error_bound <= big"1e-100"
    @test reference.evidence.target_error_bound <= big"1e-100"
    @test primary.evidence.numerical_rank == 1
    @test reference.evidence.numerical_rank == 1
    @test primary.evidence.rank_stable
    @test reference.evidence.rank_stable
    @test primary.evidence.work.weight == 10
    @test reference.evidence.work.weight == 15
    @test primary.evidence.work.oracle_work ==
          primary.evidence.work.weight * primary.evidence.work.raw_oracle_work
    @test reference.evidence.work.oracle_work ==
          reference.evidence.work.weight * reference.evidence.work.raw_oracle_work

    replay = GeoTargetCore._run_high_precision_replay(
        compiled,
        collect(reference.evidence.coordinates);
        precision_bits=768,
    )
    @test replay.failure == GeoTargetCore.HIGH_PRECISION_REFINEMENT_NONE
    @test replay.observation.status == EVAL_OK
    @test replay.work.evaluations == 1
    @test replay.work.oracle_work == 15 * replay.work.raw_oracle_work
end

@testset "high-precision resources fail closed and preserve charged work" begin
    compiled = hp_refinement_problem()
    no_budget = run_hp_refinement(compiled, [0.8]; remaining_oracle_work=0)
    @test !no_budget.accepted
    @test no_budget.failure ==
          GeoTargetCore.HIGH_PRECISION_REFINEMENT_ORACLE_BUDGET_EXHAUSTED
    @test no_budget.evidence.work.evaluations == 0
    @test no_budget.evidence.work.oracle_work == 0

    base_only = run_hp_refinement(compiled, [0.8]; remaining_oracle_work=10)
    @test !base_only.accepted
    @test base_only.failure ==
          GeoTargetCore.HIGH_PRECISION_REFINEMENT_ORACLE_BUDGET_EXHAUSTED
    @test base_only.evidence.work.evaluations == 1
    @test base_only.evidence.work.oracle_work == 10

    cancelled = run_hp_refinement(compiled, [0.8]; cancelled=() -> true)
    @test cancelled.failure == GeoTargetCore.HIGH_PRECISION_REFINEMENT_CANCELLED
    @test cancelled.evidence.work.evaluations == 0

    deadline = run_hp_refinement(compiled, [0.8]; deadline_ns=UInt64(0))
    @test deadline.failure == GeoTargetCore.HIGH_PRECISION_REFINEMENT_DEADLINE_REACHED
    @test deadline.evidence.work.evaluations == 0

    @test_throws ArgumentError run_hp_refinement(
        compiled,
        [0.8];
        remaining_oracle_work=true,
    )
    @test_throws ArgumentError run_hp_refinement(
        compiled,
        [0.8];
        remaining_oracle_work=big(typemax(Int)) + 1,
    )
end

@testset "exact-zero underdetermined configurations are not numerical answers" begin
    compiled = hp_refinement_problem(underdetermined=true)
    result = run_hp_refinement(compiled, [0.0, 0.25])
    @test !result.accepted
    @test result.failure == GeoTargetCore.HIGH_PRECISION_REFINEMENT_RANK_DEFICIENT
    @test result.evidence.numerical_rank == 1
    @test length(result.evidence.coordinates) == 2
end
