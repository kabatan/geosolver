using ExperimentExact001
using GeoTargetBase
using GeoTargetCore
using GeoTargetExact
using Test

const EXPERIMENT_ROOT = normpath(joinpath(@__DIR__, ".."))

const TEST_RECOGNITION = RecognitionOptions(
    degree_limits=(1, 2, 3, 5, 8, 12),
    height_bits=(8,),
    base_precision_bits=768,
    confirmation_extra_bits=256,
)

struct RejectStoredReplayBackend <: AbstractExactBackend end

function GeoTargetCore.verify_stored_exact_answer(
    ::RejectStoredReplayBackend,
    ::GeoTargetCore.CompiledProblem,
    ::ExactAnswer;
    observation=nothing,
    checkpoint=() -> nothing,
)
    checkpoint()
    observation === nothing && error("adapter omitted the stored observation binding")
    return ExactVerificationResult(
        false,
        EXACT_VERIFICATION_ARTIFACT_INVALID,
        "forced development rejection",
    )
end

@testset "outcome-unobserved exact campaign card" begin
    preregistration = parse_protocol_json(read(joinpath(EXPERIMENT_ROOT, "preregistration.json"), String))
    @test preregistration["state"] == "preregistered-no-outcome"
    @test preregistration["positive_corpus"]["case_count"] == 24
    @test preregistration["positive_corpus"]["family_count"] == 6
    @test preregistration["positive_corpus"]["instances_per_family"] == 4
    @test preregistration["positive_corpus"]["plugin_id_count"] == 3
    @test preregistration["campaign"]["seeds"] == 30
    @test preregistration["campaign"]["wall_seconds"] == Any[60, 180, 420]
    @test preregistration["campaign"]["maximum_parallel_case_processes"] == 16
    @test preregistration["formal_x1_open"] === false
    @test preregistration["u4_materialized"] === false
    @test preregistration["outcomes_observed"] === false
    @test !ispath(joinpath(EXPERIMENT_ROOT, "formal"))
    @test !ispath(joinpath(EXPERIMENT_ROOT, "x1"))
    @test !ispath(joinpath(EXPERIMENT_ROOT, "u4"))
end

@testset "development corpus spans six mechanisms and two plugin identities" begin
    fixtures = development_fixtures()
    @test length(fixtures) == 9
    @test Set(fixture.truth.family for fixture in fixtures) == Set((
        :rational_triangular,
        :quadratic_radical,
        :higher_algebraic,
        :isolated_singular,
        :stable_branch_multitarget,
    ))
    @test Set(
        only(fixture.input.compiled.problem.plugin_locks).id for fixture in fixtures
    ) == Set((DEV_POLYNOMIAL_PLUGIN_ID, DEV_BRANCH_PLUGIN_ID))
    @test count(fixture -> fixture.truth.family == :higher_algebraic, fixtures) == 4
    @test all(fixture -> supports(capabilities(fixture.input.compiled), C3A), fixtures)
end

@testset "C3A replay covers high degree, singular, and stable signed branches" begin
    fixtures = development_fixtures()
    by_id = Dict(fixture.input.id => fixture for fixture in fixtures)
    for degree in (3, 5, 8, 12)
        coefficients = zeros(Int, degree + 1)
        coefficients[1] = -2
        coefficients[end] = 1
        approximation = setprecision(BigFloat, 768) do
            BigFloat(2)^(inv(BigFloat(degree)))
        end
        descriptor = descriptor_from_relation(
            coefficients,
            approximation;
            precision_bits=768,
            height_bits=8,
        )
        @test descriptor !== nothing
        root = reconstruct_descriptor(descriptor)
        @test root !== nothing
        replay = replay_c3a(by_id["dev-higher-degree-$degree"].input.compiled, (root,))
        @test replay.accepted
        @test iszero(only(replay.evidence.relations).value)
    end
    singular = replay_c3a(
        by_id["dev-isolated-singular"].input.compiled,
        (AlgebraicReal(1),),
    )
    @test singular.accepted

    for (id, root, key) in (
        ("dev-stable-branch-positive", sqrt(AlgebraicReal(2)), "positive"),
        ("dev-stable-branch-negative", -sqrt(AlgebraicReal(2)), "negative"),
    )
        replay = replay_c3a(by_id[id].input.compiled, (root,))
        @test replay.accepted
        @test string(only(replay.evidence.branches).decision.key) == key
        @test only(replay.evidence.branches).validity_margin > zero(AlgebraicReal)
        @test only(replay.evidence.branches).selector_margin > zero(AlgebraicReal)
    end
end

@testset "solve adapter returns and independently replays exact evidence" begin
    fixtures = development_fixtures()
    selected = filter(
        fixture -> fixture.input.id in (
            "dev-rational-triangular",
            "dev-quadratic-radical",
            "dev-isolated-singular",
        ),
        fixtures,
    )
    backend = NemoExactBackend(recognition_options=TEST_RECOGNITION)
    first_run = nothing
    for fixture in selected
        run = run_exact_case(
            fixture.input.compiled;
            seed=0,
            wall_seconds=60.0,
            max_actions=2,
            backend,
        )
        @test length(run.execution.result.exact_answers) == 1
        @test isempty(run.execution.result.provisional_answers)
        @test length(run.replay_records) == 1
        @test only(run.replay_records).verification.accepted
        first_run === nothing && (first_run = (fixture.input.compiled, run.execution))
    end
    rejected = replay_returned_exact_answers(first_run[1], first_run[2], RejectStoredReplayBackend())
    @test length(rejected) == 1
    @test !only(rejected).verification.accepted
    @test only(rejected).verification.failure == EXACT_VERIFICATION_ARTIFACT_INVALID
end

@testset "runtime adapter has no truth or identity routing surface" begin
    adapter = read(joinpath(EXPERIMENT_ROOT, "src", "solve_adapter.jl"), String)
    lowered = lowercase(adapter)
    for forbidden in (
        "developmenttruth",
        "gold",
        "known_root",
        "expected_target",
        "family",
        string(DEV_POLYNOMIAL_PLUGIN_ID),
        string(DEV_BRANCH_PLUGIN_ID),
        "case_id",
    )
        @test !occursin(lowercase(forbidden), lowered)
    end
    @test occursin("verify_stored_exact_answer", adapter)
    @test occursin("worker_count=1", replace(adapter, " " => ""))
end
