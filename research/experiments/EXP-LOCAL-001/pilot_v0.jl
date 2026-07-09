using GeoTargetBase
using GeoTargetBenchmarks
using GeoTargetCore

const PILOT_TOLERANCE = 1.0e-6

function direct_observation(problem, x, scale_residuals::Bool)
    residual = zeros(Float64, problem.residual_dimension)
    problem.residual!(residual, x)
    relations = Tuple(
        begin
            scale = scale_residuals ? problem.residual_scales[index] : 1.0
            RelationObservation(
                NodeId("residual_$(index)"),
                value,
                scale,
                value / scale,
                nothing,
            )
        end for (index, value) in enumerate(residual)
    )
    target = problem.target(x)
    finite = all(isfinite, residual) && isfinite(target)
    return OracleObservation(
        relations,
        target,
        (),
        (),
        (),
        finite ? EVAL_OK : EVAL_NONFINITE,
        1,
        nothing,
    )
end

function target_index(problem, value)
    for (index, target) in enumerate(problem.gold_targets)
        lower, upper = target_interval(target)
        if lower - PILOT_TOLERANCE <= value <= upper + PILOT_TOLERANCE
            return index
        end
    end
    return nothing
end

function median_integer(values)
    ordered = sort(values)
    isempty(ordered) && return 0.0
    middle = length(ordered) ÷ 2
    return isodd(length(ordered)) ? ordered[middle + 1] :
           (ordered[middle] + ordered[middle + 1]) / 2
end

function run_variant(problem, name; scale_variables::Bool, scale_residuals::Bool)
    midpoint = (problem.lower_bounds + problem.upper_bounds) / 2
    half_range = (problem.upper_bounds - problem.lower_bounds) / 2
    origins = scale_variables ? midpoint : zeros(problem.dimension)
    scales = scale_variables ? half_range : ones(problem.dimension)
    accepted = 0
    evaluations = Int[]
    found_targets = Set{Int}()
    for start in eachcol(problem.saved_starts)
        oracle = x -> direct_observation(problem, x, scale_residuals)
        attempt = solve_local(
            oracle,
            collect(start);
            origins,
            scales,
            lower = problem.lower_bounds,
            upper = problem.upper_bounds,
            options = LocalSolveOptions(max_iterations = 120, max_evaluations = 600),
        )
        push!(evaluations, attempt.evaluations)
        attempt.accepted || continue
        accepted += 1
        index = target_index(problem, attempt.observation.target)
        index === nothing || push!(found_targets, index)
    end
    gold_count = length(problem.gold_targets)
    return (
        instance = problem.instance_id,
        family = problem.family_id,
        variant = name,
        starts = size(problem.saved_starts, 2),
        accepted,
        targets_found = length(found_targets),
        gold_targets = gold_count,
        full = length(found_targets) == gold_count,
        median_evaluations = median_integer(evaluations),
        total_evaluations = sum(evaluations),
    )
end

function pilot_problems()
    return (
        generate(ScaleLadderParams(dimension = 4, residual_scale_spread = 1.0e12, start_count = 8)),
        generate(CurvedChainParams(dimension = 4, curvature = 1.0e4, start_count = 8)),
        generate(
            NearRankDeficientParams(
                dimension = 4,
                singular_value_ratio = 1.0e-8,
                start_count = 8,
            ),
        ),
        generate(RedundantOverdeterminedParams(dimension = 4, redundancy = 2, start_count = 8)),
        generate(
            TangentCircleLineParams(height_radius_ratio = 0.999999, start_count = 8),
        ),
        generate(
            MultiRootWarpedParams(
                dimension = 4,
                root_count = 4,
                minimum_separation = 1.0e-3,
                condition = 1.0e4,
                target_map = :z1,
                start_count = 8,
            ),
        ),
    )
end

function main()
    println(
        "instance,family,variant,starts,accepted,targets_found,gold_targets,full," *
        "median_evaluations,total_evaluations",
    )
    variants = (
        ("L0", false, false),
        ("LX", true, false),
        ("LR", false, true),
        ("LXR", true, true),
    )
    for problem in pilot_problems(), (name, scale_variables, scale_residuals) in variants
        result = run_variant(problem, name; scale_variables, scale_residuals)
        println(join(values(result), ','))
    end
end

main()
