module ExperimentLocal007T2Corpus

using GeoTargetBenchmarks
using GeoTargetCore
using SHA

const T2_SCHEMA = "geotarget.exp-local-007.t2-corpus/v1"
const T2_START_COUNT = 32
const T2_INSTANCE_COUNT = 48
const T2_INSTANCES_PER_FAMILY = 6
const T2_START_PREFIXES = (8, 16, 32)
const T2_RUNNER_EVALUATION_LIMIT = 2_000
const T2_FAMILIES = (
    "SCALE-LADDER",
    "CURVED-CHAIN",
    "NEAR-RANK-DEFICIENT",
    "REDUNDANT-OVERDETERMINED",
    "TANGENT-CIRCLE-LINE",
    "MULTIROOT-WARPED",
    "STRICT-GUARD-BOUNDARY",
    "OPAQUE-TRANSCENDENTAL-C0",
)
const T2_APPLICABLE_FAMILIES = Tuple(
    family for family in T2_FAMILIES if family != "REDUNDANT-OVERDETERMINED"
)
const T2_NONSQUARE_FAMILY = "REDUNDANT-OVERDETERMINED"
const T2_REPOSITORY_ROOT = normpath(joinpath(@__DIR__, "..", "..", "..", ".."))
const T2_HISTORICAL_MANIFEST_PATH = joinpath(
    T2_REPOSITORY_ROOT,
    "research",
    "experiments",
    "EXP-LOCAL-004",
    "t2-input-manifest.json",
)
const T2_HISTORICAL_MANIFEST_SHA256 =
    "aa5da6b9655ebe97f5ae8832911cc253301cb64916e0f23f5637b645905bcd81"

# Filled from the canonical 48-case document before any T2 outcome exists.
const T2_CORPUS_SHA256 = "9b17d99a33b076833902b14d19c9b7a8f490f78d15e600c47fe068668d139e26"
_instance_seed(family_index, instance_index) =
    10_000 + 100 * family_index + instance_index
_start_seed(family_index, instance_index) =
    20_000 + 100 * family_index + instance_index
_file_sha256(path) = bytes2hex(sha256(read(path)))

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

function _artifact_checksum(problem, name::Symbol)
    matches = filter(artifact -> artifact.name === name, problem.artifacts)
    length(matches) == 1 || error(
        "problem $(problem.instance_id) lacks unique $name replay material",
    )
    return only(matches).sha256
end

function _counts(values)
    result = Dict{String,Int}()
    for value in values
        key = String(value)
        result[key] = get(result, key, 0) + 1
    end
    return result
end

function _instance_like_seed(parameters)
    names = filter(
        name -> hasproperty(parameters, name),
        (:instance_seed, :orientation_seed, :dependency_seed, :coefficient_seed),
    )
    length(names) == 1 || error("T2 parameter record must expose one instance-like seed")
    return Int(getproperty(parameters, only(names)))
end

function _materialize_t2_problems()
    problems = DirectAnalyticProblem[]
    dimensions = (2, 4, 8, 16, 4, 8)

    scale_spreads = (1.0, 1.0e4, 1.0e8, 1.0e12, 1.0e8, 1.0e12)
    for index in 1:6
        push!(problems, generate(ScaleLadderParams(
            dimension=dimensions[index],
            residual_scale_spread=scale_spreads[index],
            instance_seed=_instance_seed(1, index),
            start_seed=_start_seed(1, index),
            start_count=T2_START_COUNT,
        )))
    end

    curvatures = (1.0, 1.0e2, 1.0e4, 1.0e4, 1.0e8, 1.0e12)
    for index in 1:6
        push!(problems, generate(CurvedChainParams(
            dimension=dimensions[index],
            curvature=curvatures[index],
            instance_seed=_instance_seed(2, index),
            start_seed=_start_seed(2, index),
            start_count=T2_START_COUNT,
        )))
    end

    singular_value_ratios = (1.0, 1.0e-4, 1.0e-8, 1.0e-12, 1.0e-8, 1.0e-12)
    for index in 1:6
        push!(problems, generate(NearRankDeficientParams(
            dimension=dimensions[index],
            singular_value_ratio=singular_value_ratios[index],
            orientation_seed=_instance_seed(3, index),
            start_seed=_start_seed(3, index),
            start_count=T2_START_COUNT,
        )))
    end

    redundancies = (1, 2, 3, 4, 2, 4)
    dependency_errors = (0.0, 1.0e-12, 1.0e-8, 1.0e-4, 0.0, 1.0e-8)
    for index in 1:6
        push!(problems, generate(RedundantOverdeterminedParams(
            dimension=dimensions[index],
            redundancy=redundancies[index],
            dependency_error=dependency_errors[index],
            dependency_seed=_instance_seed(4, index),
            start_seed=_start_seed(4, index),
            start_count=T2_START_COUNT,
        )))
    end

    tangent_ratios = (0.5, 0.9, 0.999, 0.9999, 0.999999, 0.99999999)
    tangent_radii = (0.5, 1.0, 2.0, 1.0, 2.0, 0.5)
    for index in 1:6
        push!(problems, generate(TangentCircleLineParams(
            radius=tangent_radii[index],
            height_radius_ratio=tangent_ratios[index],
            instance_seed=_instance_seed(5, index),
            start_seed=_start_seed(5, index),
            start_count=T2_START_COUNT,
        )))
    end

    multiroot_counts = (2, 4, 8, 4, 8, 4)
    separations = (0.1, 1.0e-3, 1.0e-6, 1.0e-3, 1.0e-6, 0.1)
    warp_values = (0.0, 0.25, 0.5, 0.75, 0.5, 0.25)
    conditions = (1.0, 1.0e4, 1.0e8, 1.0e12, 1.0e4, 1.0e8)
    for index in 1:6
        push!(problems, generate(MultiRootWarpedParams(
            dimension=dimensions[index],
            root_count=multiroot_counts[index],
            minimum_separation=separations[index],
            warp=warp_values[index],
            condition=conditions[index],
            target_map=:z1_squared,
            coefficient_seed=_instance_seed(6, index),
            start_seed=_start_seed(6, index),
            start_count=T2_START_COUNT,
        )))
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
        push!(problems, generate(StrictGuardBoundaryParams(
            boundary_case=boundary_case,
            guard_margin=guard_margin,
            instance_seed=_instance_seed(7, index),
            start_seed=_start_seed(7, index),
            start_count=T2_START_COUNT,
        )))
    end

    opaque_root_counts = (2, 3, 4, 6, 8, 3)
    opaque_loop_counts = (1, 4, 8, 16, 32, 64)
    opaque_phases = (-0.25, -0.1, 0.0, 0.1, 0.25, 0.4)
    opaque_mixings = (0.05, 0.1, 0.15, 0.2, 0.25, 0.1)
    for index in 1:6
        push!(problems, generate(OpaqueTranscendentalParams(
            root_count=opaque_root_counts[index],
            loop_count=opaque_loop_counts[index],
            phase=opaque_phases[index],
            mixing=opaque_mixings[index],
            instance_seed=_instance_seed(8, index),
            start_seed=_start_seed(8, index),
            start_count=T2_START_COUNT,
        )))
    end
    return problems
end

function validate_t2_grid(problems)
    length(problems) == T2_INSTANCE_COUNT || error("T2 must contain exactly 48 cases")
    all(verify_replay_material, problems) || error("T2 replay material is invalid")
    allunique(problem.instance_id for problem in problems) || error("duplicate T2 case ID")
    allunique(replay_checksum(problem) for problem in problems) ||
        error("duplicate T2 replay checksum")
    allunique(_artifact_checksum(problem, :saved_starts) for problem in problems) ||
        error("duplicate T2 saved-start material")
    _counts(problem.family_id for problem in problems) ==
        Dict(family => T2_INSTANCES_PER_FAMILY for family in T2_FAMILIES) ||
        error("T2 must contain six cases per family")
    for (family_index, family) in enumerate(T2_FAMILIES)
        for instance_index in 1:T2_INSTANCES_PER_FAMILY
            problem = problems[(family_index - 1) * T2_INSTANCES_PER_FAMILY + instance_index]
            problem.family_id == family || error("T2 family ordering drifted")
            _instance_like_seed(problem.parameters) ==
                _instance_seed(family_index, instance_index) ||
                error("T2 instance seed drifted for $(problem.instance_id)")
            Int(problem.parameters.start_seed) == _start_seed(family_index, instance_index) ||
                error("T2 start seed drifted for $(problem.instance_id)")
            size(problem.saved_starts) == (problem.dimension, T2_START_COUNT) ||
                error("T2 start matrix drifted for $(problem.instance_id)")
            square = problem.dimension == problem.residual_dimension
            (square == (family != T2_NONSQUARE_FAMILY)) ||
                error("T2 public square applicability drifted for $(problem.instance_id)")
        end
    end
    return true
end

function _problem_document(problem)
    return Dict{String,Any}(
        "configuration_count" => size(problem.gold_configurations, 2),
        "dimension" => problem.dimension,
        "family_id" => problem.family_id,
        "instance_id" => problem.instance_id,
        "replay_checksum" => replay_checksum(problem),
        "residual_dimension" => problem.residual_dimension,
        "saved_starts_checksum" => _artifact_checksum(problem, :saved_starts),
        "saved_starts_shape" => collect(size(problem.saved_starts)),
        "strata" => String.(problem.strata),
        "target_count" => length(problem.gold_targets),
    )
end

function _historical_problem_document(problem)
    artifacts = Dict{String,Any}(
        String(artifact.name) => artifact.sha256 for artifact in problem.artifacts
    )
    return Dict{String,Any}(
        "artifact_checksums" => artifacts,
        "configuration_count" => size(problem.gold_configurations, 2),
        "dimension" => problem.dimension,
        "family_id" => problem.family_id,
        "gold_configurations_checksum" =>
            _artifact_checksum(problem, :gold_configurations),
        "instance_id" => problem.instance_id,
        "parameters" => _parameter_document(problem.parameters),
        "parameters_checksum" => _artifact_checksum(problem, :parameters),
        "replay_checksum" => replay_checksum(problem),
        "residual_dimension" => problem.residual_dimension,
        "saved_starts_checksum" => _artifact_checksum(problem, :saved_starts),
        "saved_starts_shape" => collect(size(problem.saved_starts)),
        "strata" => collect(String.(problem.strata)),
        "target_count" => length(problem.gold_targets),
    )
end

function validate_t2_historical_records(problems)
    _file_sha256(T2_HISTORICAL_MANIFEST_PATH) == T2_HISTORICAL_MANIFEST_SHA256 ||
        error("historical pre-T1 T2 manifest hash drifted")
    historical = parse_protocol_json(read(T2_HISTORICAL_MANIFEST_PATH, String))
    historical["partition"] == "development" ||
        error("historical T2 material crossed the development partition")
    historical["locked_validation"] == false ||
        error("historical T2 material unexpectedly uses locked validation")
    separation = historical["holdout_separation"]
    separation["contains_holdout_inputs"] == false ||
        error("historical T2 material contains holdout inputs")
    records = historical["instances"]
    length(records) == length(problems) == T2_INSTANCE_COUNT ||
        error("historical T2 instance count drifted")
    for (index, problem) in enumerate(problems)
        current = _historical_problem_document(problem)
        canonical_json(records[index]) == canonical_json(current) || error(
            "T2 case $(problem.instance_id) differs from its pre-T1 materialized record",
        )
    end
    return T2_HISTORICAL_MANIFEST_SHA256
end

function t2_corpus_document(problems)
    validate_t2_grid(problems)
    return Dict{String,Any}(
        "applicable_families" => collect(T2_APPLICABLE_FAMILIES),
        "families" => collect(T2_FAMILIES),
        "family_counts" => _counts(problem.family_id for problem in problems),
        "instance_count" => T2_INSTANCE_COUNT,
        "instances" => Any[_problem_document(problem) for problem in problems],
        "instances_per_family" => T2_INSTANCES_PER_FAMILY,
        "nonsquare_family" => T2_NONSQUARE_FAMILY,
        "partition" => "development-not-holdout",
        "schema" => T2_SCHEMA,
        "seed_contract" => Dict{String,Any}(
            "instance" => "10000 + 100*family_index + instance_index",
            "start" => "20000 + 100*family_index + instance_index",
        ),
        "start_count" => T2_START_COUNT,
        "start_prefixes" => collect(T2_START_PREFIXES),
    )
end

t2_corpus_sha256(problems) = bytes2hex(sha256(canonical_json(t2_corpus_document(problems))))

function validate_t2_corpus_checksum(problems)
    observed = t2_corpus_sha256(problems)
    observed == T2_CORPUS_SHA256 || error(
        "T2 corpus checksum drifted: expected $T2_CORPUS_SHA256, observed $observed",
    )
    return observed
end

function t2_problems(; enforce_checksum=true, enforce_historical=true)
    problems = _materialize_t2_problems()
    validate_t2_grid(problems)
    enforce_checksum && validate_t2_corpus_checksum(problems)
    enforce_historical && validate_t2_historical_records(problems)
    return problems
end

function t2_variant_contract()
    return Any[
        Dict{String,Any}("name" => "prod-tol-120x600", "max_evaluations" => 600),
        Dict{String,Any}("name" => "prod-options-250x2000", "max_evaluations" => 2_000),
        Dict{String,Any}(
            "name" => "SCIPY-HYBR",
            "max_callbacks" => 600,
            "algorithm_callback_limit" => 599,
            "applicability" => "residual_dimension==dimension",
        ),
    ]
end

function fixed_assessor_manifest()
    return Dict{String,Any}(
        "configuration_tolerance" => 1.0e-6,
        "coverage_predicate" => "qualified_unique_gold_consistent_target_id",
        "qualification_predicate" =>
            "endpoint_present_finite_in_bounds_semantics_valid_scaled_residual_linf",
        "residual_linf_tolerance" => 1.0e-12,
        "safety_predicate" =>
            "all_qualified_endpoints_gold_consistent_and_unambiguous",
        "target_tolerance" => 1.0e-6,
    )
end

export T2_APPLICABLE_FAMILIES,
    T2_CORPUS_SHA256,
    T2_FAMILIES,
    T2_HISTORICAL_MANIFEST_PATH,
    T2_HISTORICAL_MANIFEST_SHA256,
    T2_INSTANCE_COUNT,
    T2_INSTANCES_PER_FAMILY,
    T2_NONSQUARE_FAMILY,
    T2_RUNNER_EVALUATION_LIMIT,
    T2_SCHEMA,
    T2_START_COUNT,
    T2_START_PREFIXES,
    fixed_assessor_manifest,
    t2_corpus_document,
    t2_corpus_sha256,
    t2_problems,
    t2_variant_contract,
    validate_t2_corpus_checksum,
    validate_t2_grid,
    validate_t2_historical_records

end
