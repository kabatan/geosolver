module DevelopmentLocal002

using ..ExperimentLocal002
using GeoTargetBenchmarks
using JSON3
using SHA

const DEVELOPMENT_START_COUNT = 32
const DEVELOPMENT_INSTANCE_COUNT = 48
const DEVELOPMENT_PREFIXES = (8, 16, 32)
const DEVELOPMENT_BOOTSTRAP_SEED = 2_002
const DEVELOPMENT_BOOTSTRAP_RESAMPLES = 10_000
const INPUT_MANIFEST_PATH = joinpath(
    ExperimentLocal002.EXPERIMENT_ROOT,
    "development-input-manifest.json",
)
const DEFAULT_DEVELOPMENT_OUTPUT_ROOT = joinpath(
    ExperimentLocal002.REPO_ROOT,
    "research",
    "results",
    ExperimentLocal002.EXPERIMENT_ID,
    "development-v0",
)

const DEVELOPMENT_FAMILIES = (
    "SCALE-LADDER",
    "CURVED-CHAIN",
    "NEAR-RANK-DEFICIENT",
    "REDUNDANT-OVERDETERMINED",
    "TANGENT-CIRCLE-LINE",
    "MULTIROOT-WARPED",
    "STRICT-GUARD-BOUNDARY",
    "OPAQUE-TRANSCENDENTAL-C0",
)

_instance_seed(family_index, instance_index) = 10_000 + 100 * family_index + instance_index
_start_seed(family_index, instance_index) = 20_000 + 100 * family_index + instance_index

"""Materialize the frozen 48-instance development grid (six per family)."""
function development_problems(; start_count::Integer=DEVELOPMENT_START_COUNT)
    count = Int(start_count)
    count > 0 || throw(ArgumentError("start_count must be positive"))
    problems = DirectAnalyticProblem[]

    dimensions = (2, 4, 8, 16, 4, 8)
    scale_spreads = (1.0, 1.0e4, 1.0e8, 1.0e12, 1.0e8, 1.0e12)
    for index in 1:6
        push!(
            problems,
            generate(
                ScaleLadderParams(
                    dimension=dimensions[index],
                    residual_scale_spread=scale_spreads[index],
                    instance_seed=_instance_seed(1, index),
                    start_seed=_start_seed(1, index),
                    start_count=count,
                ),
            ),
        )
    end

    curvatures = (1.0, 1.0e2, 1.0e4, 1.0e4, 1.0e8, 1.0e12)
    for index in 1:6
        push!(
            problems,
            generate(
                CurvedChainParams(
                    dimension=dimensions[index],
                    curvature=curvatures[index],
                    instance_seed=_instance_seed(2, index),
                    start_seed=_start_seed(2, index),
                    start_count=count,
                ),
            ),
        )
    end

    singular_value_ratios = (1.0, 1.0e-4, 1.0e-8, 1.0e-12, 1.0e-8, 1.0e-12)
    for index in 1:6
        push!(
            problems,
            generate(
                NearRankDeficientParams(
                    dimension=dimensions[index],
                    singular_value_ratio=singular_value_ratios[index],
                    orientation_seed=_instance_seed(3, index),
                    start_seed=_start_seed(3, index),
                    start_count=count,
                ),
            ),
        )
    end

    redundancies = (1, 2, 3, 4, 2, 4)
    dependency_errors = (0.0, 1.0e-12, 1.0e-8, 1.0e-4, 0.0, 1.0e-8)
    for index in 1:6
        push!(
            problems,
            generate(
                RedundantOverdeterminedParams(
                    dimension=dimensions[index],
                    redundancy=redundancies[index],
                    dependency_error=dependency_errors[index],
                    dependency_seed=_instance_seed(4, index),
                    start_seed=_start_seed(4, index),
                    start_count=count,
                ),
            ),
        )
    end

    tangent_ratios = (0.5, 0.9, 0.999, 0.9999, 0.999999, 0.99999999)
    tangent_radii = (0.5, 1.0, 2.0, 1.0, 2.0, 0.5)
    for index in 1:6
        push!(
            problems,
            generate(
                TangentCircleLineParams(
                    radius=tangent_radii[index],
                    height_radius_ratio=tangent_ratios[index],
                    instance_seed=_instance_seed(5, index),
                    start_seed=_start_seed(5, index),
                    start_count=count,
                ),
            ),
        )
    end

    multiroot_counts = (2, 4, 8, 4, 8, 4)
    separations = (0.1, 1.0e-3, 1.0e-6, 1.0e-3, 1.0e-6, 0.1)
    warp_values = (0.0, 0.25, 0.5, 0.75, 0.5, 0.25)
    conditions = (1.0, 1.0e4, 1.0e8, 1.0e12, 1.0e4, 1.0e8)
    for index in 1:6
        push!(
            problems,
            generate(
                MultiRootWarpedParams(
                    dimension=dimensions[index],
                    root_count=multiroot_counts[index],
                    minimum_separation=separations[index],
                    warp=warp_values[index],
                    condition=conditions[index],
                    target_map=:z1_squared,
                    coefficient_seed=_instance_seed(6, index),
                    start_seed=_start_seed(6, index),
                    start_count=count,
                ),
            ),
        )
    end

    guard_cases = (
        (:well_separated, 0.25),
        (:well_separated, 0.75),
        (:near_boundary, 1.0e-6),
        (:near_boundary, 1.0e-8),
        (:near_boundary, 1.0e-12),
        (:on_boundary, 0.0),
    )
    for index in 1:6
        boundary_case, guard_margin = guard_cases[index]
        push!(
            problems,
            generate(
                StrictGuardBoundaryParams(
                    boundary_case=boundary_case,
                    guard_margin=guard_margin,
                    instance_seed=_instance_seed(7, index),
                    start_seed=_start_seed(7, index),
                    start_count=count,
                ),
            ),
        )
    end

    opaque_root_counts = (2, 3, 4, 6, 8, 3)
    opaque_loop_counts = (1, 4, 8, 16, 32, 64)
    opaque_phases = (-0.25, -0.1, 0.0, 0.1, 0.25, 0.4)
    opaque_mixings = (0.05, 0.1, 0.15, 0.2, 0.25, 0.1)
    for index in 1:6
        push!(
            problems,
            generate(
                OpaqueTranscendentalParams(
                    root_count=opaque_root_counts[index],
                    loop_count=opaque_loop_counts[index],
                    phase=opaque_phases[index],
                    mixing=opaque_mixings[index],
                    instance_seed=_instance_seed(8, index),
                    start_seed=_start_seed(8, index),
                    start_count=count,
                ),
            ),
        )
    end
    return problems
end

function _counts(values)
    result = Dict{String,Int}()
    for value in values
        key = String(value)
        result[key] = get(result, key, 0) + 1
    end
    return result
end

function validate_development_grid(problems=development_problems())
    length(problems) == DEVELOPMENT_INSTANCE_COUNT ||
        error("development grid must contain exactly $DEVELOPMENT_INSTANCE_COUNT instances")
    all(verify_replay_material, problems) || error("development replay material is invalid")
    all(problem -> size(problem.saved_starts, 2) == DEVELOPMENT_START_COUNT, problems) ||
        error("every development instance must have $DEVELOPMENT_START_COUNT starts")
    instance_ids = [problem.instance_id for problem in problems]
    length(unique(instance_ids)) == length(instance_ids) || error("duplicate instance IDs")
    replay_ids = [replay_checksum(problem) for problem in problems]
    length(unique(replay_ids)) == length(replay_ids) || error("duplicate replay checksums")
    family_counts = _counts(problem.family_id for problem in problems)
    family_counts == Dict(family => 6 for family in DEVELOPMENT_FAMILIES) ||
        error("development grid must contain six instances per family")
    stratum_counts = _counts(stratum for problem in problems for stratum in problem.strata)
    for index in 1:8
        get(stratum_counts, "S$index", 0) >= 6 || error("stratum S$index has fewer than six instances")
    end
    Set(problem.dimension for problem in problems) >= Set((2, 4, 8, 16)) ||
        error("development grid does not cover dimensions 2/4/8/16")
    guard_cases = Set(
        problem.metadata[:boundary_case] for problem in problems if
        problem.family_id == "STRICT-GUARD-BOUNDARY"
    )
    guard_cases == Set((:well_separated, :near_boundary, :on_boundary)) ||
        error("strict-guard cases are incomplete")
    opaque_loops = sort([
        problem.metadata[:loop_count] for problem in problems if
        problem.family_id == "OPAQUE-TRANSCENDENTAL-C0"
    ])
    opaque_loops == [1, 4, 8, 16, 32, 64] || error("opaque loop grid drift")
    return true
end

function _artifact_checksums(problem)
    return Dict(String(artifact.name) => artifact.sha256 for artifact in problem.artifacts)
end

function _problem_record(problem)
    return Dict{String,Any}(
        "instance_id" => problem.instance_id,
        "family_id" => problem.family_id,
        "strata" => String.(problem.strata),
        "dimension" => problem.dimension,
        "residual_dimension" => problem.residual_dimension,
        "start_count" => size(problem.saved_starts, 2),
        "target_count" => length(problem.gold_targets),
        "replay_checksum" => replay_checksum(problem),
        "starts_checksum" => ExperimentLocal002._artifact_checksum(problem, :saved_starts),
        "gold_checksum" =>
            ExperimentLocal002._artifact_checksum(problem, :gold_configurations),
        "artifact_checksums" => _artifact_checksums(problem),
    )
end

function development_input_manifest(problems=development_problems())
    validate_development_grid(problems)
    family_counts = _counts(problem.family_id for problem in problems)
    stratum_counts = _counts(stratum for problem in problems for stratum in problem.strata)
    return Dict{String,Any}(
        "schema_version" => "exp-local-002-development-input-v1",
        "experiment_id" => ExperimentLocal002.EXPERIMENT_ID,
        "partition" => "development",
        "locked_validation" => false,
        "instance_count" => DEVELOPMENT_INSTANCE_COUNT,
        "starts_per_instance" => DEVELOPMENT_START_COUNT,
        "prefixes" => collect(DEVELOPMENT_PREFIXES),
        "variants" => collect(ExperimentLocal002.VARIANTS),
        "thresholds" => Dict(
            "canonical_scaled_residual" =>
                ExperimentLocal002.INTERNAL_RESIDUAL_TOLERANCE,
            "strict_internal_residual" =>
                ExperimentLocal002.STRICT_INTERNAL_RESIDUAL_TOLERANCE,
            "gold_configuration_normalized" =>
                ExperimentLocal002.GOLD_CONFIGURATION_TOLERANCE,
            "gold_target" => ExperimentLocal002.GOLD_TARGET_TOLERANCE,
            "max_iterations" => ExperimentLocal002.MAX_ITERATIONS,
            "max_callback_residual_evaluations" => ExperimentLocal002.MAX_EVALUATIONS,
        ),
        "family_counts" => family_counts,
        "stratum_counts" => stratum_counts,
        "card_sha256" => ExperimentLocal002._file_sha256(ExperimentLocal002.CARD_PATH),
        "instances" => [_problem_record(problem) for problem in problems],
    )
end

function write_development_input_manifest(path::AbstractString=INPUT_MANIFEST_PATH)
    manifest = development_input_manifest()
    ExperimentLocal002._write_json(path, manifest)
    return path
end

function validate_development_input_manifest(
    path::AbstractString=INPUT_MANIFEST_PATH,
    problems=development_problems(),
)
    isfile(path) || error("development input manifest does not exist: $path")
    observed = JSON3.read(read(path, String))
    expected = development_input_manifest(problems)
    JSON3.write(observed) == JSON3.write(expected) ||
        error("development input manifest does not match generated material")
    return true
end

_sha256_file(path::AbstractString) = bytes2hex(sha256(read(path)))

function _warmup_problems(problems)
    seen = Set{String}()
    selected = DirectAnalyticProblem[]
    for problem in problems
        problem.family_id in seen && continue
        push!(seen, problem.family_id)
        push!(selected, problem)
    end
    return selected
end

function execute_development_variant(
    variant::AbstractString;
    output_directory::AbstractString,
    input_manifest_path::AbstractString=INPUT_MANIFEST_PATH,
    load_compile_seconds::Real=NaN,
)
    variant in ExperimentLocal002.VARIANTS || throw(ArgumentError("unknown variant $variant"))
    problems = development_problems()
    validate_development_input_manifest(input_manifest_path, problems)
    mkpath(output_directory)

    worker_start_ns = time_ns()
    reference = first(problems)
    cold_probe = ExperimentLocal002.run_attempt(
        reference,
        reference.saved_starts[:, 1],
        variant,
    )
    cold_probe.exception === nothing || error("cold probe failed: $(cold_probe.exception)")

    warmup_start_ns = time_ns()
    for problem in _warmup_problems(problems)
        warmup = ExperimentLocal002.run_attempt(
            problem,
            problem.saved_starts[:, 1],
            variant,
        )
        warmup.exception === nothing || warmup.budget_exhausted ||
            error("warmup failed for $(problem.instance_id): $(warmup.exception)")
    end
    warmup_seconds = (time_ns() - warmup_start_ns) / 1.0e9

    rows = Dict{String,Any}[]
    measured_start_ns = time_ns()
    for problem in problems
        seen_targets = Set{String}()
        for start_index in 1:DEVELOPMENT_START_COUNT
            execution = ExperimentLocal002.run_attempt(
                problem,
                view(problem.saved_starts, :, start_index),
                variant,
            )
            row = ExperimentLocal002._attempt_row(
                problem,
                variant,
                start_index,
                execution,
                "warm-measured",
            )
            row["accepted"] && push!(seen_targets, row["target_id"])
            row["targets_seen"] = length(seen_targets)
            row["target_count"] = length(problem.gold_targets)
            row["all_targets_prefix"] = length(seen_targets) == length(problem.gold_targets)
            push!(rows, row)
        end
    end
    measured_seconds = (time_ns() - measured_start_ns) / 1.0e9
    ExperimentLocal002.validate_result_rows(
        rows,
        problems;
        variants=(variant,),
        start_count=DEVELOPMENT_START_COUNT,
    )

    slug = lowercase(replace(variant, '-' => '_'))
    csv_path = joinpath(output_directory, "worker-$slug.csv")
    metadata_path = joinpath(output_directory, "worker-$slug.json")
    ExperimentLocal002._write_csv(csv_path, rows)
    metadata = Dict{String,Any}(
        "schema_version" => "exp-local-002-development-worker-v1",
        "experiment_id" => ExperimentLocal002.EXPERIMENT_ID,
        "variant" => String(variant),
        "source_commit" => ExperimentLocal002._safe_git_commit(),
        "julia_version" => string(VERSION),
        "packages" => Dict(
            "ADTypes" => string(Base.pkgversion(ExperimentLocal002.ADTypes)),
            "GeoTargetBenchmarks" => string(Base.pkgversion(GeoTargetBenchmarks)),
            "GeoTargetCore" => string(Base.pkgversion(ExperimentLocal002.GeoTargetCore)),
            "NonlinearSolve" => string(Base.pkgversion(ExperimentLocal002.NonlinearSolve)),
        ),
        "input_manifest_sha256" => _sha256_file(input_manifest_path),
        "result_csv_sha256" => _sha256_file(csv_path),
        "attempt_count" => length(rows),
        "package_load_compile_seconds" => Float64(load_compile_seconds),
        "cold_probe_solve_seconds" => cold_probe.wall_seconds,
        "cold_total_seconds" => Float64(load_compile_seconds) + cold_probe.wall_seconds,
        "cold_probe_callback_residual_calls" => cold_probe.callback_residual_calls,
        "cold_probe_retcode" => cold_probe.retcode,
        "warmup_family_count" => length(_warmup_problems(problems)),
        "warmup_seconds" => warmup_seconds,
        "measured_attempt_seconds" => measured_seconds,
        "worker_seconds" => (time_ns() - worker_start_ns) / 1.0e9,
        "budget_overruns" => count(row -> row["budget_exceeded"], rows),
        "budget_exhaustions" => count(row -> row["budget_exhausted"], rows),
        "exceptions" => count(row -> row["exception"] !== nothing, rows),
        "nonbudget_exceptions" => count(
            row -> row["exception"] !== nothing && !row["budget_exhausted"],
            rows,
        ),
        "accepted" => count(row -> row["accepted"], rows),
        "false_candidates" => count(row -> row["false_candidate"], rows),
        "callback_residual_calls" => sum(row["callback_residual_calls"] for row in rows),
    )
    ExperimentLocal002._write_json(metadata_path, metadata)
    return metadata
end

function worker_cli(args=ARGS; load_compile_seconds::Real=NaN)
    variant = nothing
    output_directory = nothing
    input_manifest_path = INPUT_MANIFEST_PATH
    index = 1
    while index <= length(args)
        argument = args[index]
        if argument in ("--variant", "--out", "--input-manifest")
            index == length(args) && throw(ArgumentError("$argument requires a value"))
            index += 1
            if argument == "--variant"
                variant = args[index]
            elseif argument == "--out"
                output_directory = abspath(args[index])
            else
                input_manifest_path = abspath(args[index])
            end
        else
            throw(ArgumentError("unknown worker argument: $argument"))
        end
        index += 1
    end
    variant === nothing && throw(ArgumentError("--variant is required"))
    output_directory === nothing && throw(ArgumentError("--out is required"))
    metadata = execute_development_variant(
        variant;
        output_directory=output_directory,
        input_manifest_path=input_manifest_path,
        load_compile_seconds=load_compile_seconds,
    )
    println(
        "completed ",
        variant,
        ": accepted=",
        metadata["accepted"],
        "/",
        metadata["attempt_count"],
        ", worker_seconds=",
        round(metadata["worker_seconds"]; digits=3),
    )
    return metadata
end

export DEVELOPMENT_START_COUNT,
    DEVELOPMENT_INSTANCE_COUNT,
    DEVELOPMENT_PREFIXES,
    DEVELOPMENT_BOOTSTRAP_SEED,
    DEVELOPMENT_BOOTSTRAP_RESAMPLES,
    INPUT_MANIFEST_PATH,
    DEFAULT_DEVELOPMENT_OUTPUT_ROOT,
    DEVELOPMENT_FAMILIES,
    development_problems,
    validate_development_grid,
    development_input_manifest,
    write_development_input_manifest,
    validate_development_input_manifest,
    execute_development_variant,
    worker_cli

end
