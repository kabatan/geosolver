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
