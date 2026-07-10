using GeoTargetBase
using GeoTargetCore
using Test

const LOCAL_RELATION_NODE = NodeId("local_relation")
const LOCAL_GUARD_NODE = NodeId("local_guard")
const LOCAL_DOMAIN_NODE = NodeId("local_domain")

function local_observation(x; root = 1.0, relation_scale = 1.0, guard_offset = 2.0)
    value = x[1]
    relation = RelationObservation(
        LOCAL_RELATION_NODE,
        relation_scale * (value - root),
        relation_scale,
        value - root,
        value == root,
    )
    guard_margin = value + guard_offset
    guard = GuardObservation(
        LOCAL_GUARD_NODE,
        guard_margin,
        true,
        1.0,
        guard_margin > 0,
    )
    domain = DomainObservation(LOCAL_DOMAIN_NODE, value + 10.0, true, value > -10.0)
    status = domain.valid ? EVAL_OK : EVAL_INVALID_DOMAIN
    return OracleObservation(
        (relation,),
        value * value,
        (guard,),
        (domain,),
        (),
        status,
        1,
        nothing,
    )
end

function diagonal_observation(x; reject_combined = false)
    if reject_combined && count(value -> !iszero(value), x) > 1
        return OracleObservation(
            (),
            nothing,
            (),
            (),
            (),
            EVAL_INVALID_DOMAIN,
            1,
            "combined perturbation rejected",
        )
    end
    relations = Tuple(
        RelationObservation(
            NodeId("diagonal_relation_$index"),
            x[index] - 1.0,
            1.0,
            x[index] - 1.0,
            x[index] == 1.0,
        ) for index in eachindex(x)
    )
    return OracleObservation(relations, sum(x), (), (), (), EVAL_OK, 1, nothing)
end

@testset "public local solver documentation" begin
    metadata = Base.Docs.meta(GeoTargetCore)
    @test haskey(metadata, Base.Docs.Binding(GeoTargetCore, :solve_local))
    @test !haskey(metadata, Base.Docs.Binding(GeoTargetCore, :_solve_local_kernel))
end

@testset "scaled LM-QR local control" begin
    attempt = solve_local(
        x -> local_observation(x),
        [-1.5];
        origins = [0.0],
        scales = [3.0],
        lower = [-3.0],
        upper = [3.0],
    )
    @test attempt.status == LOCAL_CONVERGED
    @test attempt.accepted
    @test abs(only(scaled_residual_values(attempt.observation))) <= sqrt(eps(Float64))
    @test attempt.final[1] ≈ 1.0 atol = 2sqrt(eps(Float64))
    @test attempt.observation.target ≈ 1.0 atol = 3sqrt(eps(Float64))
    @test attempt.numerical_rank == 1
    @test attempt.evaluations <= LocalSolveOptions().max_evaluations
    @test any(point -> point.accepted_step, attempt.trace)

    scaled = solve_local(
        x -> local_observation(x; root = 3.0, relation_scale = 1.0e12),
        [-2.0];
        origins = [0.0],
        scales = [5.0],
        lower = [-5.0],
        upper = [5.0],
    )
    @test scaled.status == LOCAL_CONVERGED
    @test scaled.accepted
    @test scaled.final[1] ≈ 3.0 atol = 1.0e-7
end

@testset "local control keeps guards and interruption separate" begin
    invalid_guard = solve_local(
        x -> local_observation(x; root = 1.0, guard_offset = -2.0),
        [0.0];
        lower = [-5.0],
        upper = [5.0],
    )
    @test invalid_guard.status == LOCAL_CONVERGED
    @test !invalid_guard.accepted
    @test !only(invalid_guard.observation.guards).valid

    cancelled = solve_local(x -> local_observation(x), [0.0]; cancelled = () -> true)
    @test cancelled.status == LOCAL_CANCELLED
    @test !cancelled.accepted

    deadline = solve_local(x -> local_observation(x), [0.0]; deadline_ns = UInt64(0))
    @test deadline.status == LOCAL_DEADLINE
    @test !deadline.accepted

    failed = solve_local(
        _ -> OracleObservation((), nothing, (), (), (), EVAL_INVALID_DOMAIN, 1, nothing),
        [0.0],
    )
    @test failed.status == LOCAL_EVALUATION_FAILED
end

@testset "local options and budgets fail closed" begin
    @test_throws ArgumentError LocalSolveOptions(max_iterations = 0)
    @test_throws ArgumentError LocalSolveOptions(damping_increase = 1.0)
    limited = solve_local(
        x -> local_observation(x; root = 100.0),
        [0.0];
        lower = [-1.0],
        upper = [1.0],
        options = LocalSolveOptions(max_evaluations = 3),
    )
    @test limited.status == LOCAL_MAX_EVALUATIONS
    @test !limited.accepted
end

@testset "compiler sparsity colors structurally orthogonal finite differences" begin
    dimension = 8
    origin = zeros(dimension)
    scales = ones(dimension)
    lower = fill(-2.0, dimension)
    upper = fill(2.0, dimension)
    base_residual = fill(-1.0, dimension)
    step = LocalSolveOptions().finite_difference_step
    entries = Tuple((index, index) for index in 1:dimension)
    coloring = GeoTargetCore._local_jacobian_coloring(dimension, dimension, entries)
    @test length(coloring.groups) == 1
    @test only(coloring.groups) == Tuple(1:dimension)
    @test coloring.structural_nonzeros == dimension

    dense, dense_evaluations = GeoTargetCore._finite_difference_jacobian(
        diagonal_observation,
        origin,
        base_residual,
        origin,
        scales,
        lower,
        upper,
        step,
    )
    colored, colored_evaluations = GeoTargetCore._colored_finite_difference_jacobian(
        diagonal_observation,
        origin,
        base_residual,
        origin,
        scales,
        lower,
        upper,
        step,
        coloring,
    )
    @test colored ≈ dense atol = 1.0e-12 rtol = 1.0e-12
    @test dense_evaluations == 2dimension
    @test colored_evaluations == 2

    dense_attempt = solve_local(
        diagonal_observation,
        fill(-0.5, dimension);
        lower,
        upper,
    )
    jacobian_events = NamedTuple[]
    colored_attempt = solve_local(
        diagonal_observation,
        fill(-0.5, dimension);
        lower,
        upper,
        jacobian_entries = entries,
        jacobian_observer = event -> push!(jacobian_events, event),
    )
    @test colored_attempt.accepted
    @test collect(colored_attempt.final) ≈ collect(dense_attempt.final) atol = 1.0e-10 rtol = 1.0e-10
    @test colored_attempt.evaluations < dense_attempt.evaluations
    @test !isempty(jacobian_events)
    @test all(event -> event.colored && event.evaluations == 2, jacobian_events)

    group_events = NamedTuple[]
    fallback, fallback_evaluations = GeoTargetCore._colored_finite_difference_jacobian(
        x -> diagonal_observation(x; reject_combined = true),
        origin,
        base_residual,
        origin,
        scales,
        lower,
        upper,
        step,
        coloring,
        group_observer = event -> push!(group_events, event),
    )
    @test fallback ≈ dense atol = 1.0e-12 rtol = 1.0e-12
    @test fallback_evaluations == 2 + 2dimension
    @test length(group_events) == 1
    @test only(group_events).columns == Tuple(1:dimension)
    @test only(group_events).grouped_evaluations == 2
    @test only(group_events).fallback
    @test only(group_events).fallback_evaluations == 2dimension

    incomplete = GeoTargetCore._local_jacobian_coloring(
        dimension,
        dimension,
        Tuple((index, index) for index in 1:(dimension - 1)),
    )
    incomplete_jacobian, _ = GeoTargetCore._colored_finite_difference_jacobian(
        diagonal_observation,
        origin,
        base_residual,
        origin,
        scales,
        lower,
        upper,
        step,
        incomplete,
    )
    @test incomplete_jacobian != dense
    @test_throws ArgumentError GeoTargetCore._local_jacobian_coloring(
        dimension,
        dimension,
        ((1, 1), (1, 1)),
    )
    @test_throws ArgumentError GeoTargetCore._local_jacobian_coloring(
        dimension,
        dimension,
        ((dimension + 1, 1),),
    )
end
