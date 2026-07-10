struct EndpointOracle{R,T,J}
    id::String
    family::String
    metamorphic_group::String
    dimension::Int
    residual_dimension::Int
    capability::Symbol
    residual::R
    target::T
    analytic_jacobian::J

    function EndpointOracle(
        id::AbstractString,
        family::AbstractString,
        metamorphic_group::AbstractString,
        dimension::Integer,
        residual_dimension::Integer,
        capability::Symbol,
        residual::R,
        target::T,
        analytic_jacobian::J,
    ) where {R,T,J}
        frozen_id = String(id)
        frozen_family = String(family)
        frozen_group = String(metamorphic_group)
        isempty(frozen_id) && throw(ArgumentError("oracle id must be nonempty"))
        isempty(frozen_family) && throw(ArgumentError("family must be nonempty"))
        isempty(frozen_group) && throw(ArgumentError("metamorphic group must be nonempty"))
        dimension > 0 || throw(ArgumentError("dimension must be positive"))
        residual_dimension > 0 || throw(
            ArgumentError("residual_dimension must be positive"),
        )
        capability in (:C0, :C2, :C3V) || throw(
            ArgumentError("capability must be C0, C2 or C3V"),
        )
        return new{R,T,J}(
            frozen_id,
            frozen_family,
            frozen_group,
            Int(dimension),
            Int(residual_dimension),
            capability,
            residual,
            target,
            analytic_jacobian,
        )
    end
end

struct CandidateInput{O<:EndpointOracle}
    oracle::O
    endpoint::Vector{Float64}

    function CandidateInput(oracle::O, endpoint::AbstractVector{<:Real}) where {O<:EndpointOracle}
        frozen = Float64[endpoint...]
        length(frozen) == oracle.dimension || throw(DimensionMismatch("endpoint dimension"))
        all(isfinite, frozen) || throw(ArgumentError("endpoint must be finite"))
        return new{O}(oracle, frozen)
    end
end

struct GoldTruth
    kind::Symbol
    configuration::Union{Nothing,Vector{Float64}}
    target::Union{Nothing,Float64}
    finite_discrete_target::Bool

    function GoldTruth(
        kind::Symbol;
        configuration=nothing,
        target=nothing,
        finite_discrete_target::Bool=false,
    )
        kind in (
            :isolated_root,
            :no_local_root,
            :nonfinite_target_image,
            :finite_manifold_target,
        ) || throw(
            ArgumentError("unsupported Gold truth kind"),
        )
        frozen_configuration = configuration === nothing ? nothing : Float64[configuration...]
        frozen_configuration === nothing || all(isfinite, frozen_configuration) || throw(
            ArgumentError("Gold configuration must be finite"),
        )
        frozen_target = target === nothing ? nothing : Float64(target)
        frozen_target === nothing || isfinite(frozen_target) || throw(
            ArgumentError("Gold target must be finite"),
        )
        kind == :isolated_root && frozen_configuration === nothing && throw(
            ArgumentError("isolated Gold truth needs a configuration"),
        )
        kind == :isolated_root && frozen_target === nothing && throw(
            ArgumentError("isolated Gold truth needs a target"),
        )
        return new(kind, frozen_configuration, frozen_target, finite_discrete_target)
    end
end

struct GeneratedEndpoint{O<:EndpointOracle}
    input::CandidateInput{O}
    gold::GoldTruth
    parameters::Dict{String,Any}
    checksum::String
end

candidate_input(endpoint::GeneratedEndpoint) = endpoint.input

struct ExperimentOptions
    precision_ladder::Tuple{Vararg{Int}}
    semantic_precision_bits::Int
    maximum_iterations::Int
    maximum_callbacks::Int
    wall_seconds::Float64
    finite_difference_exponent::Float64
    rank_roundoff_multiplier::Float64
    required_precision_guard_bits::Int
    independent_confirmation_count::Int
    confirmation_perturbation_radius::Float64
    error_reserve_multiplier::Float64
    target_error_goal::Float64
    configuration_error_goal::Float64
    semantic_residual_tolerance::Float64

    function ExperimentOptions(
        ;
        precision_ladder=(128, 256, 512, 1024),
        semantic_precision_bits::Integer=256,
        maximum_iterations::Integer=64,
        maximum_callbacks::Integer=4096,
        wall_seconds::Real=10.0,
        finite_difference_exponent::Real=1 / 3,
        rank_roundoff_multiplier::Real=32.0,
        required_precision_guard_bits::Integer=32,
        independent_confirmation_count::Integer=2,
        confirmation_perturbation_radius::Real=1.0e-6,
        error_reserve_multiplier::Real=16.0,
        target_error_goal::Real=1.0e-12,
        configuration_error_goal::Real=1.0e-10,
        semantic_residual_tolerance::Real=1.0e-12,
    )
        ladder = Tuple(Int(bits) for bits in precision_ladder)
        isempty(ladder) && throw(ArgumentError("precision ladder cannot be empty"))
        issorted(ladder) && allunique(ladder) && all(>=(64), ladder) || throw(
            ArgumentError("precision ladder must be unique, sorted and at least 64 bits"),
        )
        semantic_precision_bits >= 64 || throw(
            ArgumentError("semantic precision must be at least 64 bits"),
        )
        maximum_iterations > 0 || throw(ArgumentError("maximum_iterations must be positive"))
        maximum_callbacks > 0 || throw(ArgumentError("maximum_callbacks must be positive"))
        positive = Float64.((
            wall_seconds,
            finite_difference_exponent,
            rank_roundoff_multiplier,
            confirmation_perturbation_radius,
            error_reserve_multiplier,
            target_error_goal,
            configuration_error_goal,
            semantic_residual_tolerance,
        ))
        all(value -> isfinite(value) && value > 0, positive) || throw(
            ArgumentError("experiment numeric controls must be finite and positive"),
        )
        0 < finite_difference_exponent < 1 || throw(
            ArgumentError("finite difference exponent must lie in (0, 1)"),
        )
        required_precision_guard_bits >= 0 || throw(
            ArgumentError("precision guard bits must be nonnegative"),
        )
        independent_confirmation_count >= 1 || throw(
            ArgumentError("at least one independent confirmation is required"),
        )
        return new(
            ladder,
            Int(semantic_precision_bits),
            Int(maximum_iterations),
            Int(maximum_callbacks),
            positive[1],
            positive[2],
            positive[3],
            Int(required_precision_guard_bits),
            Int(independent_confirmation_count),
            positive[4],
            positive[5],
            positive[6],
            positive[7],
            positive[8],
        )
    end
end

struct WorkSnapshot
    callbacks::Int
    residual_calls::Int
    target_calls::Int
    jacobian_calls::Int
    factorization_calls::Int
    iterations::Int
    precision_equivalent_oracle_work::Int
    calls_by_precision::Tuple
    elapsed_seconds::Float64
    maximum_precision_bits::Int
    budget_exhausted::Bool
    deadline_reached::Bool
end

struct SemanticReplayEvidence
    precision_bits::Int
    endpoint::Tuple
    residual_linf::BigFloat
    target::BigFloat
    accepted::Bool
end

abstract type AbstractNumericalRootEvidence end

struct NumericalRootEvidence <: AbstractNumericalRootEvidence
    method::String
    precision_bits::Int
    precision_stages::Tuple
    endpoint::Tuple
    target::BigFloat
    residual_linf::BigFloat
    numerical_rank::Int
    condition_estimate::BigFloat
    configuration_error_estimate::BigFloat
    target_error_estimate::BigFloat
    confirmation_endpoints::Tuple
    confirmation_targets::Tuple
    rank_stable::Bool
end

struct NumericalManifoldRootEvidence <: AbstractNumericalRootEvidence
    method::String
    precision_bits::Int
    precision_stages::Tuple
    endpoint::Tuple
    target::BigFloat
    residual_linf::BigFloat
    numerical_rank::Int
    condition_estimate::BigFloat
    active_columns::Tuple{Vararg{Int}}
    active_configuration_error_estimate::BigFloat
    target_error_estimate::BigFloat
    nullspace_target_sensitivity::BigFloat
    confirmation_endpoints::Tuple
    confirmation_targets::Tuple
    rank_stable::Bool
end

struct NumericalSingularRootEvidence <: AbstractNumericalRootEvidence
    method::String
    precision_bits::Int
    precision_stages::Tuple
    endpoint::Tuple
    target::BigFloat
    residual_linf::BigFloat
    numerical_rank::Int
    nullity::Int
    condition_estimate::BigFloat
    configuration_error_estimate::BigFloat
    target_error_estimate::BigFloat
    confirmation_endpoints::Tuple
    confirmation_targets::Tuple
    confirmation_residuals::Tuple
    route_rank_signatures::Tuple
    contraction_ratios::Tuple
    secant_updates::Int
    rank_stable::Bool
    independent_confirmations_passed::Bool
    canonical_confirmations_passed::Bool
    linear_trace_passed::Bool
end

struct ExperimentalOutcome
    variant::String
    route::String
    status::Symbol
    reason::String
    semantic_replay::Union{Nothing,SemanticReplayEvidence}
    root_evidence::Union{Nothing,AbstractNumericalRootEvidence}
    work::WorkSnapshot

    function ExperimentalOutcome(
        variant::AbstractString,
        route::AbstractString,
        status::Symbol,
        reason::AbstractString,
        semantic_replay,
        root_evidence,
        work::WorkSnapshot,
    )
        status in (:promoted, :diagnostic_only, :unknown) || throw(
            ArgumentError("unsupported experimental outcome status"),
        )
        status == :promoted && root_evidence === nothing && throw(
            ArgumentError("promotion requires NumericalRootEvidence"),
        )
        status == :promoted && semantic_replay === nothing && throw(
            ArgumentError("promotion requires SemanticReplayEvidence"),
        )
        semantic_replay === nothing || semantic_replay isa SemanticReplayEvidence || throw(
            ArgumentError("invalid semantic replay evidence"),
        )
        root_evidence === nothing || root_evidence isa AbstractNumericalRootEvidence || throw(
            ArgumentError("invalid root evidence"),
        )
        return new(
            String(variant),
            String(route),
            status,
            String(reason),
            semantic_replay,
            root_evidence,
            work,
        )
    end
end

struct GoldAssessment
    case_id::String
    variant::String
    promoted::Bool
    gold_success::Bool
    false_promotion::Bool
    configuration_error::Union{Nothing,Float64}
    target_error::Union{Nothing,Float64}
    configuration_error_covered::Bool
    target_error_covered::Bool
end
