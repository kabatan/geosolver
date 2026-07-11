using GeoTargetBenchmarks
using Test

const REPOSITORY_ROOT = normpath(joinpath(@__DIR__, "..", "..", "..", ".."))

include(joinpath(@__DIR__, "..", "run_t0.jl"))
using .ExperimentLocal007

function fixture_case(
    dimension,
    residual_dimension,
    lower,
    upper,
    residual_scales,
    residual;
    target=input -> input[1],
    semantics=input -> true,
    calls=Ref(0),
)
    evaluator = function (input)
        calls[] += 1
        values = Tuple(residual(input))
        raw_target = target(input)
        finite = all(isfinite, values) && raw_target isa Real && isfinite(raw_target)
        return SolverCaseEvaluation(
            values,
            finite ? Float64(raw_target) : nothing,
            finite && semantics(input),
            finite,
        )
    end
    return SolverExperimentCase(
        dimension,
        residual_dimension,
        Tuple(Float64.(lower)),
        Tuple(Float64.(upper)),
        Tuple(ones(dimension)),
        Tuple(Float64.(residual_scales)),
        evaluator,
    )
end

function diagnostic_fields(text)
    fields = Dict{String,String}()
    for entry in split(text, ';')
        parts = split(entry, '='; limit=2)
        length(parts) == 2 || continue
        fields[String(first(parts))] = String(last(parts))
    end
    return fields
end

@testset "EXP-LOCAL-007 pinned truth-blind square HYBRD candidate" begin
    @test ExperimentLocal007._package_version() == SCIPY_VERSION == "1.18.0"
    @test ExperimentLocal007.PythonCall.python_executable_path() == PYTHON_EXECUTABLE
    source = read(joinpath(@__DIR__, "..", "src", "ExperimentLocal007.jl"), String)
    bridge = read(
        joinpath(@__DIR__, "..", "python", "geotarget_scipy_hybr_bridge.py"),
        String,
    )
    for forbidden in ("family_id", "instance_id", "gold_configurations", "gold_targets")
        @test !occursin(forbidden, source)
        @test !occursin(forbidden, bridge)
    end
    @test occursin("method=\"hybr\"", bridge)
    @test !occursin("least_squares", bridge)
    variant = scipy_hybr_variant()
    @test variant.name == "SCIPY-HYBR"
    config = variant.configuration
    @test config.package_version == "1.18.0"
    @test config.applicability == "residual_dimension==dimension"
    @test config.nonsquare_policy == "typed-inapplicable-zero-callbacks"
    @test config.residual_scaling == "declared"
    @test config.max_callbacks == 600
    @test config.algorithm_callback_limit == 599
    @test config.endpoint_screen_reservation == 1
    @test config.all_callbacks_charged
    @test config.scipy_success_role == "diagnostic-only"
    @test !config.identity_routing
    @test_throws ArgumentError scipy_hybr_variant(max_callbacks=1)

    nonsquare_calls = Ref(0)
    nonsquare = fixture_case(
        2,
        3,
        [-1.0, -1.0],
        [1.0, 1.0],
        [1.0, 1.0, 1.0],
        input -> [input[1], input[2], input[1] + input[2]];
        calls=nonsquare_calls,
    )
    outcome = variant.run(nonsquare, [0.25, -0.25])
    @test outcome.status == "INAPPLICABLE_NONSQUARE"
    @test outcome.endpoint === nothing
    @test outcome.evaluations == nonsquare_calls[] == 0
    @test occursin("inapplicable-residual-dimension", outcome.diagnostic)
end

@testset "fixed tanh and atanh boundary policy" begin
    case = fixture_case(
        2,
        2,
        [-4.0, -2.0],
        [8.0, 6.0],
        [1.0, 1.0],
        input -> input,
    )
    bounds, unconstrained, normalized = ExperimentLocal007._bounds_map(case, [8.0, -2.0])
    @test normalized == [1.0, -1.0]
    @test unconstrained[1] == atanh(1.0 - BOUNDARY_INTERIOR_MARGIN)
    @test unconstrained[2] == atanh(-1.0 + BOUNDARY_INTERIOR_MARGIN)
    physical, mapped = ExperimentLocal007._physical_coordinates(bounds, unconstrained)
    @test all(-1.0 .< mapped .< 1.0)
    @test all(bounds.lower .< physical .< bounds.upper)
    @test ExperimentLocal007._open_tanh(1.0e6) == UPPER_OPEN_UNIT
    @test ExperimentLocal007._open_tanh(-1.0e6) == LOWER_OPEN_UNIT
    @test_throws ArgumentError ExperimentLocal007._bounds_map(case, [9.0, 0.0])
end

@testset "regular, declared scaling, and callback reconciliation" begin
    regular_calls = Ref(0)
    regular = fixture_case(
        2,
        2,
        [-4.0, -2.0],
        [8.0, 6.0],
        [2.0, 0.5],
        input -> [2.0 * (input[1] - 1.0), 0.5 * (input[2] + 0.5)];
        calls=regular_calls,
    )
    outcome = scipy_hybr_variant(max_callbacks=200).run(regular, [5.0, 3.0])
    @test outcome.endpoint !== nothing
    @test collect(outcome.endpoint) ≈ [1.0, -0.5] atol=2.0e-9
    @test outcome.reported_converged
    @test outcome.reported_accepted
    @test outcome.evaluations == regular_calls[] <= 200
    fields = diagnostic_fields(outcome.diagnostic)
    @test parse(Int, fields["callbacks"]) == outcome.evaluations
    @test parse(Int, fields["residual_callbacks"]) +
          parse(Int, fields["endpoint_screen_callbacks"]) == outcome.evaluations
    @test parse(Int, fields["endpoint_screen_callbacks"]) == 1
    @test parse(Int, fields["scipy_nfev"]) == parse(Int, fields["residual_callbacks"])
    @test fields["screening_accepted"] == "true"

    scaled_calls = Ref(0)
    scaled = fixture_case(
        2,
        2,
        [-2.0, -2.0],
        [2.0, 2.0],
        [1.0e8, 1.0e-8],
        input -> [1.0e8 * (input[1] - 0.25), 1.0e-8 * (input[2] + 0.75)];
        calls=scaled_calls,
    )
    scaled_outcome = scipy_hybr_variant(max_callbacks=200).run(scaled, [-1.0, 1.0])
    @test scaled_outcome.endpoint !== nothing
    @test collect(scaled_outcome.endpoint) ≈ [0.25, -0.75] atol=2.0e-9
    @test scaled_outcome.reported_accepted
    @test scaled_outcome.evaluations == scaled_calls[]
end

@testset "near-rank square system remains an ordinary numeric input" begin
    calls = Ref(0)
    near_rank = fixture_case(
        2,
        2,
        [-2.0, -2.0],
        [2.0, 2.0],
        [1.0, 1.0],
        input -> begin
            dx = input[1] - 0.2
            dy = input[2] + 0.3
            [dx + dy, dx + (1.0 + 1.0e-6) * dy]
        end;
        calls,
    )
    outcome = scipy_hybr_variant(max_callbacks=200).run(near_rank, [1.0, -1.0])
    @test outcome.endpoint !== nothing
    @test collect(outcome.endpoint) ≈ [0.2, -0.3] atol=2.0e-7
    @test outcome.reported_accepted
    @test outcome.evaluations == calls[]
    @test !occursin("inapplicable", outcome.status)
end

@testset "invalid, nonfinite, and throwing trials are charged and fail closed" begin
    semantic_calls = Ref(0)
    semantic_case = fixture_case(
        1,
        1,
        [-1.0],
        [1.0],
        [1.0],
        input -> [input[1] - 0.25];
        semantics=input -> input[1] > 0.0,
        calls=semantic_calls,
    )
    invalid = scipy_hybr_variant(max_callbacks=50).run(semantic_case, [-0.5])
    @test invalid.endpoint === nothing
    @test startswith(invalid.status, "exception:")
    @test invalid.evaluations == semantic_calls[] == 1
    invalid_fields = diagnostic_fields(invalid.diagnostic)
    @test invalid_fields["invalid_algorithm_callbacks"] == "1"
    @test invalid_fields["semantic_invalid_callbacks"] == "1"

    nonfinite_calls = Ref(0)
    nonfinite_case = fixture_case(
        1,
        1,
        [-1.0],
        [1.0],
        [1.0],
        input -> [NaN];
        calls=nonfinite_calls,
    )
    nonfinite = scipy_hybr_variant(max_callbacks=50).run(nonfinite_case, [0.0])
    @test nonfinite.endpoint === nothing
    @test nonfinite.evaluations == nonfinite_calls[] == 1
    nonfinite_fields = diagnostic_fields(nonfinite.diagnostic)
    @test nonfinite_fields["nonfinite_callbacks"] == "1"
    @test nonfinite_fields["invalid_algorithm_callbacks"] == "1"

    throwing_calls = Ref(0)
    throwing_case = fixture_case(
        1,
        1,
        [-1.0],
        [1.0],
        [1.0],
        input -> error("fixture domain failure");
        calls=throwing_calls,
    )
    throwing = scipy_hybr_variant(max_callbacks=50).run(throwing_case, [0.0])
    @test throwing.endpoint === nothing
    @test throwing.evaluations == throwing_calls[] == 1
    throwing_fields = diagnostic_fields(throwing.diagnostic)
    @test throwing_fields["oracle_exceptions"] == "1"
    @test occursin("fixture domain failure", throwing.diagnostic)
end

@testset "external hard caps and endpoint screen reservation" begin
    calls = Ref(0)
    impossible = fixture_case(
        1,
        1,
        [-2.0],
        [2.0],
        [1.0],
        input -> [1.0];
        calls,
    )
    exhausted = scipy_hybr_variant(max_callbacks=4).run(impossible, [0.0])
    @test exhausted.status == "LOCAL_MAX_EVALUATIONS"
    @test exhausted.evaluations == calls[] == 3
    exhausted_fields = diagnostic_fields(exhausted.diagnostic)
    @test exhausted_fields["algorithm_callback_limit"] == "3"
    @test exhausted_fields["endpoint_screen_callbacks"] == "0"

    outside_calls = Ref(0)
    outside_root = fixture_case(
        1,
        1,
        [-1.0],
        [1.0],
        [1.0],
        input -> [input[1] - 2.0];
        calls=outside_calls,
    )
    bounded = scipy_hybr_variant(max_callbacks=100).run(outside_root, [0.5])
    @test bounded.endpoint !== nothing
    @test -1.0 <= only(bounded.endpoint) <= 1.0
    @test !bounded.reported_accepted
    @test bounded.evaluations == outside_calls[]
    @test occursin("screening_accepted=false", bounded.diagnostic)

    problem = first(GeoTargetSolverLab.representative_problems(start_count=1))
    run = run_solver_experiment(
        [problem],
        [scipy_hybr_variant(max_callbacks=50)];
        prefixes=[1],
        evaluation_limit=3,
    )
    attempt = only(run.attempts)
    @test attempt.status == "runner_evaluation_budget_exhausted"
    @test attempt.budget_exhausted
    @test attempt.evaluations == attempt.reported_evaluations == 3
    @test !attempt.evaluation_count_mismatch
end

@testset "case-cumulative runner, clean provenance, and sharding contract" begin
    tracker = CallbackPrefixTracker([600, 1_200, 2_400, 4_800])
    @test isempty(record_attempt!(tracker, 550, 1))
    first_crossing = only(record_attempt!(tracker, 100, 2))
    @test first_crossing.threshold == 600
    @test first_crossing.cumulative_callbacks == 650
    @test first_crossing.overshoot_callbacks == 50
    double_crossing = record_attempt!(tracker, 2_000, 3)
    @test [entry.threshold for entry in double_crossing] == [1_200, 2_400]
    @test all(entry.start_index == 3 for entry in double_crossing)
    final_crossing = only(record_attempt!(tracker, 2_150, 4))
    @test final_crossing.threshold == 4_800
    @test final_crossing.overshoot_callbacks == 0
    @test tracker_complete(tracker)

    options = parse_arguments([
        "--callback-prefixes=600",
        "--max-starts=16",
        "--shard-index=1",
        "--shard-count=2",
    ])
    @test options[:callback_prefixes] == [600]
    @test options[:max_starts] == 16
    @test options[:shard_index] == 1
    @test_throws ErrorException parse_arguments(["--callback-prefixes=1200,600"])

    runner = read(joinpath(@__DIR__, "..", "run_t0.jl"), String)
    @test occursin("mod(index - 1, shard_count) == shard_index", runner)
    @test occursin("verify_replay_material", runner)
    @test occursin("_suffix_stable_evaluations_to_lab_safe_full", runner)
    @test occursin("formal T0 requires a clean committed worktree", runner)
    @test occursin("BLAS.get_num_threads() == 1", runner)
    @test occursin("RUNNER_ATTEMPT_HARD_LIMIT", runner)
    @test occursin("overshoot_callbacks", runner)
    @test occursin("single-stream-attempt-boundary-snapshots-no-reruns", runner)
    @test !isdir(joinpath(@__DIR__, "..", "results"))
end
