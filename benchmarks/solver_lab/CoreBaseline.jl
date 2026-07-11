module GeoTargetSolverLab

using GeoTargetBase
using GeoTargetBenchmarks
using GeoTargetCore

const _SEMANTICS_GUARD = NodeId("solver-lab-semantics")

function _oracle_observation(case, input, residual_scaling::Bool)
    evaluation = evaluate_case(case, input)
    residual_scales = residual_scaling ? case.residual_scales : ntuple(_ -> 1.0, case.residual_dimension)
    relations = Tuple(
        RelationObservation(
            NodeId("solver-lab-residual-$index"),
            evaluation.residuals[index],
            residual_scales[index],
            evaluation.residuals[index] / residual_scales[index],
            nothing,
        ) for index in 1:case.residual_dimension
    )
    guard = GuardObservation(
        _SEMANTICS_GUARD,
        evaluation.semantics_valid ? 1.0 : -1.0,
        true,
        1.0,
        evaluation.semantics_valid,
    )
    return OracleObservation(
        relations,
        evaluation.target,
        (guard,),
        (),
        (),
        evaluation.finite ? EVAL_OK : EVAL_NONFINITE,
        1,
        nothing,
    )
end

function _coordinates(case, mode::Symbol)
    lower = collect(case.lower_bounds)
    upper = collect(case.upper_bounds)
    if mode === :bounds
        return (lower .+ upper) ./ 2, (upper .- lower) ./ 2
    elseif mode === :declared
        return zeros(case.dimension), collect(case.variable_scales)
    elseif mode === :raw
        return zeros(case.dimension), ones(case.dimension)
    end
    throw(ArgumentError("coordinate scaling must be bounds, declared, or raw"))
end

"""Build the current Core LM-QR control as a truth-blind laboratory variant."""
function core_lmqr_variant(;
    name::Union{Nothing,AbstractString}=nothing,
    coordinate_scaling::Symbol=:bounds,
    residual_scaling::Bool=true,
    max_iterations::Integer=120,
    max_evaluations::Integer=600,
)
    options = LocalSolveOptions(
        max_iterations=max_iterations,
        max_evaluations=max_evaluations,
    )
    variant_name = name === nothing ? string(
        "core-lmqr-",
        coordinate_scaling,
        residual_scaling ? "-scaled" : "-raw-residuals",
    ) : String(name)
    configuration = (;
        coordinate_scaling,
        residual_scaling,
        max_iterations=Int(max_iterations),
        max_evaluations=Int(max_evaluations),
    )
    runner = function (case, start)
        origins, scales = _coordinates(case, coordinate_scaling)
        attempt = solve_local(
            input -> _oracle_observation(case, input, residual_scaling),
            start;
            origins,
            scales,
            lower=collect(case.lower_bounds),
            upper=collect(case.upper_bounds),
            options,
        )
        diagnostic = join(
            (
                "rank=$(attempt.numerical_rank)",
                "condition=$(attempt.condition_estimate)",
            ),
            ';',
        )
        return SolverAttemptOutcome(
            attempt.final;
            status=string(attempt.status),
            reported_converged=attempt.status == LOCAL_CONVERGED,
            reported_accepted=attempt.accepted,
            evaluations=attempt.evaluations,
            iterations=attempt.iterations,
            diagnostic,
        )
    end
    return SolverVariant(variant_name, runner; configuration)
end

"""One deterministic instance per family plus a distinct-target collision companion."""
function representative_problems(; start_count::Integer=8)
    start_count > 0 || throw(ArgumentError("start_count must be positive"))
    count = Int(start_count)
    return DirectAnalyticProblem[
        generate(
            ScaleLadderParams(
                dimension=4,
                residual_scale_spread=1.0e12,
                start_count=count,
            ),
        ),
        generate(
            CurvedChainParams(
                dimension=4,
                curvature=1.0e4,
                start_count=count,
            ),
        ),
        generate(
            NearRankDeficientParams(
                dimension=4,
                singular_value_ratio=1.0e-8,
                start_count=count,
            ),
        ),
        generate(
            RedundantOverdeterminedParams(
                dimension=4,
                redundancy=2,
                dependency_error=1.0e-8,
                start_count=count,
            ),
        ),
        generate(
            TangentCircleLineParams(
                radius=1.0,
                height_radius_ratio=0.999999,
                start_count=count,
            ),
        ),
        generate(
            MultiRootWarpedParams(
                dimension=4,
                root_count=4,
                minimum_separation=1.0e-3,
                warp=0.5,
                condition=1.0e4,
                target_map=:z1,
                start_count=count,
            ),
        ),
        generate(
            MultiRootWarpedParams(
                dimension=4,
                root_count=4,
                minimum_separation=1.0e-3,
                warp=0.5,
                condition=1.0e4,
                target_map=:z1_squared,
                start_count=count,
            ),
        ),
        generate(
            StrictGuardBoundaryParams(
                boundary_case=:on_boundary,
                guard_margin=0.0,
                start_count=count,
            ),
        ),
        generate(
            OpaqueTranscendentalParams(
                root_count=3,
                loop_count=8,
                phase=0.0,
                mixing=0.1,
                start_count=count,
            ),
        ),
    ]
end

export core_lmqr_variant, representative_problems

end
