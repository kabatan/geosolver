const _M0_SEED_MANIFEST_PATH = joinpath(
    REPOSITORY_ROOT,
    "benchmarks",
    "generated",
    "m0-analytic-seed-manifest.json",
)
const _LOCAL004_T2_MANIFEST_PATH = joinpath(
    REPOSITORY_ROOT,
    "research",
    "experiments",
    "EXP-LOCAL-004",
    "t2-input-manifest.json",
)

const _T0_CASE_PARAMETERS = (
    MultiRootWarpedParams(
        dimension=4,
        root_count=4,
        minimum_separation=1.0e-3,
        warp=0.5,
        condition=1.0e4,
        target_map=:z1,
        coefficient_seed=706,
        start_seed=1706,
        start_count=32,
    ),
    MultiRootWarpedParams(
        dimension=4,
        root_count=4,
        minimum_separation=0.1,
        warp=0.5,
        condition=100.0,
        target_map=:z1_squared,
        coefficient_seed=707,
        start_seed=1707,
        start_count=32,
    ),
    MultiRootWarpedParams(
        dimension=2,
        root_count=2,
        minimum_separation=0.1,
        warp=0.0,
        condition=1.0,
        target_map=:z1_squared,
        coefficient_seed=10_601,
        start_seed=20_601,
        start_count=32,
    ),
    MultiRootWarpedParams(
        dimension=4,
        root_count=4,
        minimum_separation=1.0e-3,
        warp=0.25,
        condition=1.0e4,
        target_map=:z1_squared,
        coefficient_seed=10_602,
        start_seed=20_602,
        start_count=32,
    ),
    MultiRootWarpedParams(
        dimension=8,
        root_count=8,
        minimum_separation=1.0e-6,
        warp=0.5,
        condition=1.0e8,
        target_map=:z1_squared,
        coefficient_seed=10_603,
        start_seed=20_603,
        start_count=32,
    ),
    MultiRootWarpedParams(
        dimension=4,
        root_count=8,
        minimum_separation=1.0e-6,
        warp=0.5,
        condition=1.0e4,
        target_map=:z1_squared,
        coefficient_seed=10_605,
        start_seed=20_605,
        start_count=32,
    ),
)

const _BASE_ARTIFACT_NAMES = Set((
    :gold_configurations,
    :gold_targets,
    :saved_starts,
    :bounds,
    :scales,
))

function _manifest_case_document(source::AbstractString, source_index::Int)
    path = normpath(joinpath(REPOSITORY_ROOT, split(source, '/')...))
    document = JSON3.read(read(path, String), Dict{String,Any})
    entries = endswith(source, "m0-analytic-seed-manifest.json") ?
              document["cases"] : document["instances"]
    1 <= source_index <= length(entries) || throw(
        DiscoveryGateError(:t0_corpus_drift, "source index is outside $source"),
    )
    return entries[source_index]
end

"""Rebuild and verify the six preregistered MultiRoot T0 cases."""
function t0_problems()
    length(T0_RECIPE) == length(_T0_CASE_PARAMETERS) ||
        error("T0 corpus tables differ in length")
    problems = DirectAnalyticProblem[]
    for index in eachindex(_T0_CASE_PARAMETERS)
        recipe = T0_RECIPE[index]
        source_index = recipe.source_index
        problem = generate(_T0_CASE_PARAMETERS[index])
        verify_replay_material(problem) || throw(
            DiscoveryGateError(:t0_corpus_drift, "generated case $index is not replayable"),
        )
        source = _manifest_case_document(recipe.source, source_index)
        if haskey(source, "case_id")
            source["case_id"] == recipe.case_id || throw(
                DiscoveryGateError(:t0_corpus_drift, "M0 case label drifted at $index"),
            )
        end
        source["instance_id"] == problem.instance_id || throw(
            DiscoveryGateError(:t0_corpus_drift, "instance ID drifted at T0 case $index"),
        )
        replay_field = haskey(source, "replay_checksum") ?
                       "replay_checksum" : "replay_sha256"
        source[replay_field] == replay_checksum(problem) || throw(
            DiscoveryGateError(:t0_corpus_drift, "replay checksum drifted at T0 case $index"),
        )
        target_field = haskey(source, "target_count") ?
                       "target_count" : "distinct_target_count"
        source[target_field] == length(problem.gold_targets) || throw(
            DiscoveryGateError(:t0_corpus_drift, "target count drifted at T0 case $index"),
        )
        all(isfinite, problem.lower_bounds) && all(isfinite, problem.upper_bounds) || throw(
            DiscoveryGateError(:t0_corpus_drift, "T0 requires finite proposal bounds"),
        )
        push!(problems, problem)
    end
    sum(length(problem.gold_targets) for problem in problems) == 17 || throw(
        DiscoveryGateError(:t0_corpus_drift, "T0 must expose 17 assessor-side targets"),
    )
    return problems
end

function t0_proposal_domain(problem::DirectAnalyticProblem)
    view = (;
        dimension=problem.dimension,
        lower_bounds=Tuple(problem.lower_bounds),
        upper_bounds=Tuple(problem.upper_bounds),
    )
    return truth_blind_domain(view)
end

"""
Return an assessor-owned problem whose only changed input is the materialized
proposal matrix. Gold and family fields remain in the runner; the local solver
still receives `SolverExperimentCase` only.
"""
function t0_problem_with_proposals(
    problem::DirectAnalyticProblem,
    proposals::AbstractMatrix{<:Real},
)
    starts = Matrix{Float64}(proposals)
    size(starts) == (problem.dimension, MATRIX_COLUMN_COUNT) || throw(
        DimensionMismatch("T0 proposal matrix has the wrong shape"),
    )
    all(isfinite, starts) || throw(ArgumentError("T0 proposals must be finite"))
    all(
        problem.lower_bounds[row] <= starts[row, column] <= problem.upper_bounds[row] for
        row in axes(starts, 1), column in axes(starts, 2)
    ) || throw(ArgumentError("T0 proposal lies outside the public finite box"))
    extras = MaterializedArtifact[
        artifact for artifact in problem.artifacts if
        !(artifact.name in _BASE_ARTIFACT_NAMES)
    ]
    metadata = copy(problem.metadata)
    metadata[:proposal_start_count_override] = size(starts, 2)
    replacement = DirectAnalyticProblem(
        problem.instance_id,
        problem.family_id,
        problem.strata,
        problem.parameters,
        problem.dimension,
        problem.residual_dimension,
        problem.residual!,
        problem.jacobian!,
        problem.target,
        problem.lower_bounds,
        problem.upper_bounds,
        problem.variable_scales,
        problem.residual_scales,
        problem.gold_configurations,
        problem.gold_targets,
        starts,
        extras,
        metadata,
    )
    verify_replay_material(replacement) || error("proposal replacement broke replay material")
    return replacement
end
