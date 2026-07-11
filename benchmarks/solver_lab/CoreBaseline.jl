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
    residual_tolerance::Real=sqrt(eps(Float64)),
    initial_damping::Real=1.0e-3,
    finite_difference_step::Real=cbrt(eps(Float64)),
)
    options = LocalSolveOptions(
        max_iterations=max_iterations,
        max_evaluations=max_evaluations,
        residual_tolerance=residual_tolerance,
        initial_damping=initial_damping,
        finite_difference_step=finite_difference_step,
    )
    variant_name = name === nothing ? string(
        "core-lmqr-",
        coordinate_scaling,
        residual_scaling ? "-scaled" : "-raw-residuals",
    ) : String(name)
    configuration = (;
        coordinate_scaling,
        residual_scaling,
        max_iterations=options.max_iterations,
        max_evaluations=options.max_evaluations,
        residual_tolerance=options.residual_tolerance,
        initial_damping=options.initial_damping,
        finite_difference_step=options.finite_difference_step,
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

"""
Build one of the three frozen LM-QR laboratory controls.

Accepted names are `:legacy_lab_120x600`, `:prod_tol_120x600`, and
`:prod_options_250x2000` (hyphenated strings are accepted as well). These are
local-solver controls only; none includes production target-image analysis,
root correction, or candidate validation.
"""
function core_lmqr_control(control::Union{Symbol,AbstractString})
    control_name = replace(String(control), '_' => '-')
    if control_name == "legacy-lab-120x600"
        return core_lmqr_variant(
            name=control_name,
            max_iterations=120,
            max_evaluations=600,
            residual_tolerance=sqrt(eps(Float64)),
            initial_damping=1.0e-3,
            finite_difference_step=cbrt(eps(Float64)),
        )
    elseif control_name == "prod-tol-120x600"
        return core_lmqr_variant(
            name=control_name,
            max_iterations=120,
            max_evaluations=600,
            residual_tolerance=1.0e-12,
            initial_damping=1.0e-3,
            finite_difference_step=cbrt(eps(Float64)),
        )
    elseif control_name == "prod-options-250x2000"
        return core_lmqr_variant(
            name=control_name,
            max_iterations=250,
            max_evaluations=2_000,
            residual_tolerance=1.0e-12,
            initial_damping=1.0e-3,
            finite_difference_step=cbrt(eps(Float64)),
        )
    end
    throw(ArgumentError(
        "LM-QR control must be legacy-lab-120x600, prod-tol-120x600, or " *
        "prod-options-250x2000",
    ))
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

export core_lmqr_control, core_lmqr_variant, representative_problems

end
