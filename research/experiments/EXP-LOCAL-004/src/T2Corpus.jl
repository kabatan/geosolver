module T2Corpus

using ..DevelopmentLocal002
using GeoTargetBenchmarks
using GeoTargetCore
using JSON3
using LinearAlgebra
using SHA

const T2_SCHEMA_VERSION = "exp-local-004-t2-input/v1"
const T2_START_COUNT = 32
const T2_INSTANCE_COUNT = 48
const T2_PREFIXES = (8, 16, 32)
const T2_RUNNER_EVALUATION_LIMIT = 2_000
const T2_INSTANCES_PER_FAMILY = 6
const T2_FAMILIES = DevelopmentLocal002.DEVELOPMENT_FAMILIES
const T2_EXPERIMENT_ROOT = normpath(joinpath(@__DIR__, ".."))
const T2_REPOSITORY_ROOT = DevelopmentLocal002.ExperimentLocal002.REPO_ROOT
const T2_INPUT_MANIFEST_PATH = joinpath(T2_EXPERIMENT_ROOT, "t2-input-manifest.json")

const _T2_SOURCE_PATHS = (
    "benchmarks/solver_lab/CoreBaseline.jl",
    "julia/GeoTargetBenchmarks/src/GeoTargetBenchmarks.jl",
    "julia/GeoTargetBenchmarks/src/common.jl",
    "julia/GeoTargetBenchmarks/src/curved_chain.jl",
    "julia/GeoTargetBenchmarks/src/multiroot_warped.jl",
    "julia/GeoTargetBenchmarks/src/near_rank_deficient.jl",
    "julia/GeoTargetBenchmarks/src/opaque_transcendental.jl",
    "julia/GeoTargetBenchmarks/src/redundant_overdetermined.jl",
    "julia/GeoTargetBenchmarks/src/replay.jl",
    "julia/GeoTargetBenchmarks/src/scale_ladder.jl",
    "julia/GeoTargetBenchmarks/src/solver_experiment.jl",
    "julia/GeoTargetBenchmarks/src/strict_guard_boundary.jl",
    "julia/GeoTargetBenchmarks/src/tangent_circle_line.jl",
    "julia/GeoTargetBenchmarks/src/types.jl",
    "research/experiments/EXP-LOCAL-002/Manifest.toml",
    "research/experiments/EXP-LOCAL-002/Project.toml",
    "research/experiments/EXP-LOCAL-002/src/ExperimentLocal002.jl",
    "research/experiments/EXP-LOCAL-002/src/DevelopmentLocal002.jl",
    "research/experiments/EXP-LOCAL-004/prepare_t2.jl",
    "research/experiments/EXP-LOCAL-004/run_t2.jl",
    "research/experiments/EXP-LOCAL-004/src/ExperimentLocal004.jl",
    "research/experiments/EXP-LOCAL-004/src/T2Corpus.jl",
)

_file_sha256(path::AbstractString) = bytes2hex(sha256(read(path)))

function _artifact(problem::DirectAnalyticProblem, name::Symbol)
    matches = filter(artifact -> artifact.name === name, problem.artifacts)
    length(matches) == 1 || error("problem $(problem.instance_id) lacks unique $name material")
    return only(matches)
end

function _counts(values)
    result = Dict{String,Int}()
    for value in values
        key = String(value)
        result[key] = get(result, key, 0) + 1
    end
    return result
end

_manifest_value(value::Symbol) = String(value)
_manifest_value(value::UInt64) = Int(value)
_manifest_value(value::Tuple) = Any[_manifest_value(item) for item in value]
_manifest_value(value::AbstractVector) = Any[_manifest_value(item) for item in value]
_manifest_value(value) = value

function _parameter_document(parameters)
    return Dict{String,Any}(
        String(name) => _manifest_value(getfield(parameters, name)) for
        name in fieldnames(typeof(parameters))
    )
end

function _instance_seed(parameters)
    names = filter(
        name -> hasproperty(parameters, name),
        (:instance_seed, :orientation_seed, :dependency_seed, :coefficient_seed),
    )
    length(names) == 1 || error("parameter record must expose one instance-like seed")
    return Int(getproperty(parameters, only(names)))
end

function _source_hashes()
    return Dict{String,Any}(
        path => _file_sha256(joinpath(T2_REPOSITORY_ROOT, split(path, '/')...)) for
        path in _T2_SOURCE_PATHS
    )
end

function fixed_assessor_manifest()
    return Dict{String,Any}(
        "configuration_tolerance" => 1.0e-6,
        "qualification_predicate" =>
            "endpoint_present_finite_in_bounds_semantics_valid_scaled_residual_linf",
        "coverage_predicate" => "qualified_unique_gold_consistent_target_id",
        "residual_linf_tolerance" => 1.0e-12,
        "safety_predicate" =>
            "all_qualified_endpoints_gold_consistent_and_unambiguous",
        "target_tolerance" => 1.0e-6,
    )
end

function t2_variant_contract()
    return Any[
        Dict{String,Any}(
            "name" => "prod-tol-120x600",
            "max_iterations" => 120,
            "max_evaluations" => 600,
        ),
        Dict{String,Any}(
            "name" => "prod-options-250x2000",
            "max_iterations" => 250,
            "max_evaluations" => 2_000,
        ),
        Dict{String,Any}(
            "name" => "NLS-TR",
            "max_iterations" => 250,
            "max_evaluations" => 2_000,
        ),
    ]
end

function _materialization_environment()
    return Dict{String,Any}(
        "blas_config" => string(BLAS.get_config()),
        "blas_threads" => BLAS.get_num_threads(),
        "julia_threads" => Threads.nthreads(),
        "julia_version" => string(VERSION),
        "machine" => Sys.MACHINE,
        "openblas_num_threads" => get(ENV, "OPENBLAS_NUM_THREADS", "unset"),
        "word_size" => Sys.WORD_SIZE,
    )
end

function validate_t2_grid(problems)
    DevelopmentLocal002.validate_development_grid(problems)
    length(problems) == T2_INSTANCE_COUNT || error("T2 must contain exactly 48 instances")
    family_counts = _counts(problem.family_id for problem in problems)
    family_counts == Dict(family => T2_INSTANCES_PER_FAMILY for family in T2_FAMILIES) ||
        error("T2 must contain six instances from every family")
    start_checksums = String[]
    for (family_index, family) in enumerate(T2_FAMILIES)
        for instance_index in 1:T2_INSTANCES_PER_FAMILY
            problem = problems[(family_index - 1) * T2_INSTANCES_PER_FAMILY + instance_index]
            problem.family_id == family || error("T2 family ordering drifted")
            expected_instance_seed = 10_000 + 100 * family_index + instance_index
            expected_start_seed = 20_000 + 100 * family_index + instance_index
            _instance_seed(problem.parameters) == expected_instance_seed ||
                error("T2 instance seed drifted for $(problem.instance_id)")
            Int(problem.parameters.start_seed) == expected_start_seed ||
                error("T2 start seed drifted for $(problem.instance_id)")
            problem.parameters.start_count == T2_START_COUNT ||
                error("T2 parameter start count drifted")
            size(problem.saved_starts) == (problem.dimension, T2_START_COUNT) ||
                error("T2 saved-start shape drifted")
            push!(start_checksums, _artifact(problem, :saved_starts).sha256)
        end
    end
    allunique(start_checksums) || error("T2 start material must be unique per instance")
    return true
end

"""Generate and validate the open 48-case T2 development corpus exactly once."""
function t2_problems()
    problems = DevelopmentLocal002.development_problems(start_count=T2_START_COUNT)
    validate_t2_grid(problems)
    return problems
end

function _problem_document(problem)
    artifacts = Dict{String,Any}(
        String(artifact.name) => artifact.sha256 for artifact in problem.artifacts
    )
    return Dict{String,Any}(
        "artifact_checksums" => artifacts,
        "configuration_count" => size(problem.gold_configurations, 2),
        "dimension" => problem.dimension,
        "family_id" => problem.family_id,
        "gold_configurations_checksum" =>
            _artifact(problem, :gold_configurations).sha256,
        "instance_id" => problem.instance_id,
        "parameters" => _parameter_document(problem.parameters),
        "parameters_checksum" => _artifact(problem, :parameters).sha256,
        "replay_checksum" => replay_checksum(problem),
        "residual_dimension" => problem.residual_dimension,
        "saved_starts_checksum" => _artifact(problem, :saved_starts).sha256,
        "saved_starts_shape" => collect(size(problem.saved_starts)),
        "strata" => String.(problem.strata),
        "target_count" => length(problem.gold_targets),
    )
end

function t2_input_manifest(problems)
    validate_t2_grid(problems)
    return Dict{String,Any}(
        "assessor_manifest" => fixed_assessor_manifest(),
        "experiment_id" => "EXP-LOCAL-004",
        "family_counts" => _counts(problem.family_id for problem in problems),
        "holdout_separation" => Dict{String,Any}(
            "contains_holdout_inputs" => false,
            "historical_locked_recipe_loaded" => false,
            "reserved_partitions" => ["U1", "U2", "U3", "U4"],
        ),
        "instance_count" => T2_INSTANCE_COUNT,
        "instances" => Any[_problem_document(problem) for problem in problems],
        "instances_per_family" => T2_INSTANCES_PER_FAMILY,
        "locked_validation" => false,
        "materialization_environment" => _materialization_environment(),
        "partition" => "development",
        "prefixes" => collect(T2_PREFIXES),
        "runner_evaluation_limit" => T2_RUNNER_EVALUATION_LIMIT,
        "schema_version" => T2_SCHEMA_VERSION,
        "seed_contract" => Dict{String,Any}(
            "instance_formula" => "10000 + 100*family_index + instance_index",
            "instance_namespace" => 10_000,
            "start_formula" => "20000 + 100*family_index + instance_index",
            "start_namespace" => 20_000,
        ),
        "solver_experiment_schema" => SOLVER_EXPERIMENT_SCHEMA_VERSION,
        "source_sha256" => _source_hashes(),
        "starts_per_instance" => T2_START_COUNT,
        "stratum_counts" =>
            _counts(stratum for problem in problems for stratum in problem.strata),
        "suite" => "t2",
        "variant_contract" => t2_variant_contract(),
    )
end

function manifest_file_sha256(path::AbstractString=T2_INPUT_MANIFEST_PATH)
    isfile(path) || error("T2 input manifest does not exist: $path")
    return _file_sha256(path)
end

function prepare_t2_input_manifest(
    path::AbstractString=T2_INPUT_MANIFEST_PATH;
    problems=nothing,
)
    ispath(path) && error("refusing to overwrite existing T2 input manifest: $path")
    material = problems === nothing ? t2_problems() : problems
    document = t2_input_manifest(material)
    mkpath(dirname(abspath(path)))
    open(path, "w") do stream
        write(stream, canonical_json(document), "\n")
    end
    return manifest_file_sha256(path)
end

function validate_t2_input_manifest(
    path::AbstractString=T2_INPUT_MANIFEST_PATH,
    problems=nothing,
)
    isfile(path) || error("T2 input manifest does not exist: $path")
    material = problems === nothing ? t2_problems() : problems
    expected = canonical_json(t2_input_manifest(material)) * "\n"
    observed = read(path, String)
    observed == expected || error("T2 input manifest does not exactly match generated material")
    decoded = JSON3.read(observed, Dict{String,Any})
    decoded["partition"] == "development" && decoded["locked_validation"] == false ||
        error("T2 input manifest crossed the holdout boundary")
    return manifest_file_sha256(path)
end

export T2_FAMILIES,
    T2_INPUT_MANIFEST_PATH,
    T2_INSTANCE_COUNT,
    T2_INSTANCES_PER_FAMILY,
    T2_PREFIXES,
    T2_RUNNER_EVALUATION_LIMIT,
    T2_SCHEMA_VERSION,
    T2_START_COUNT,
    fixed_assessor_manifest,
    manifest_file_sha256,
    prepare_t2_input_manifest,
    t2_input_manifest,
    t2_problems,
    t2_variant_contract,
    validate_t2_grid,
    validate_t2_input_manifest

end
