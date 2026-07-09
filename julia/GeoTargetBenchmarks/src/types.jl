"""A distinct scalar Gold target, possibly witnessed by several configurations."""
abstract type AbstractGoldTargetDescriptor end

struct ExactGoldTarget <: AbstractGoldTargetDescriptor
    target_id::String
    value::Float64
    identity::String
    configurations::Vector{Int}

    function ExactGoldTarget(
        target_id::AbstractString,
        value::Real,
        identity::AbstractString,
        configurations::AbstractVector{<:Integer},
    )
        id = String(target_id)
        isempty(id) && throw(ArgumentError("target_id must be nonempty"))
        numeric = Float64(value)
        isfinite(numeric) || throw(ArgumentError("exact target value must be finite"))
        proof_identity = String(identity)
        isempty(proof_identity) && throw(ArgumentError("exact identity must be nonempty"))
        indices = Int[configurations...]
        _validate_configuration_indices(indices)
        new(id, numeric, proof_identity, indices)
    end
end

struct ValidatedGoldTarget <: AbstractGoldTargetDescriptor
    target_id::String
    lower::Float64
    upper::Float64
    validation_method::String
    configurations::Vector{Int}

    function ValidatedGoldTarget(
        target_id::AbstractString,
        lower::Real,
        upper::Real,
        validation_method::AbstractString,
        configurations::AbstractVector{<:Integer},
    )
        id = String(target_id)
        isempty(id) && throw(ArgumentError("target_id must be nonempty"))
        lo = Float64(lower)
        hi = Float64(upper)
        isfinite(lo) && isfinite(hi) ||
            throw(ArgumentError("validated target bounds must be finite"))
        lo <= hi || throw(ArgumentError("validated target lower bound exceeds upper"))
        method = String(validation_method)
        isempty(method) && throw(ArgumentError("validation_method must be nonempty"))
        indices = Int[configurations...]
        _validate_configuration_indices(indices)
        new(id, lo, hi, method, indices)
    end
end

function _validate_configuration_indices(indices::Vector{Int})
    isempty(indices) && throw(ArgumentError("a Gold target needs at least one configuration"))
    any(<(1), indices) && throw(ArgumentError("configuration indices are one-based"))
    length(indices) == length(unique(indices)) ||
        throw(ArgumentError("configuration indices must be unique"))
    issorted(indices) || throw(ArgumentError("configuration indices must be sorted"))
    return nothing
end

numeric_target(target::ExactGoldTarget) = target.value
numeric_target(target::ValidatedGoldTarget) = (target.lower + target.upper) / 2
target_interval(target::ExactGoldTarget) = (target.value, target.value)
target_interval(target::ValidatedGoldTarget) = (target.lower, target.upper)
configuration_indices(target::AbstractGoldTargetDescriptor) = copy(target.configurations)

struct MaterializedArtifact
    name::Symbol
    values::Matrix{Float64}
    sha256::String

    function MaterializedArtifact(name::Symbol, values::AbstractMatrix{<:Real})
        isempty(String(name)) && throw(ArgumentError("artifact name must be nonempty"))
        material = Matrix{Float64}(values)
        all(isfinite, material) || throw(ArgumentError("artifact values must be finite"))
        new(name, material, artifact_checksum(name, material))
    end
end

"""Standalone analytic residual problem used only by the benchmark laboratory."""
struct DirectAnalyticProblem{P,R,J,T}
    instance_id::String
    family_id::String
    strata::Tuple{Vararg{Symbol}}
    parameters::P
    dimension::Int
    residual_dimension::Int
    residual!::R
    jacobian!::J
    target::T
    lower_bounds::Vector{Float64}
    upper_bounds::Vector{Float64}
    variable_scales::Vector{Float64}
    residual_scales::Vector{Float64}
    gold_configurations::Matrix{Float64}
    gold_targets::Vector{AbstractGoldTargetDescriptor}
    saved_starts::Matrix{Float64}
    artifacts::Vector{MaterializedArtifact}
    metadata::Dict{Symbol,Any}

    function DirectAnalyticProblem{P,R,J,T}(
        instance_id::String,
        family_id::String,
        strata::Tuple{Vararg{Symbol}},
        parameters::P,
        dimension::Int,
        residual_dimension::Int,
        residual!::R,
        jacobian!::J,
        target::T,
        lower_bounds::Vector{Float64},
        upper_bounds::Vector{Float64},
        variable_scales::Vector{Float64},
        residual_scales::Vector{Float64},
        gold_configurations::Matrix{Float64},
        gold_targets::Vector{AbstractGoldTargetDescriptor},
        saved_starts::Matrix{Float64},
        artifacts::Vector{MaterializedArtifact},
        metadata::Dict{Symbol,Any},
    ) where {P,R,J,T}
        new{P,R,J,T}(
            instance_id,
            family_id,
            strata,
            parameters,
            dimension,
            residual_dimension,
            residual!,
            jacobian!,
            target,
            lower_bounds,
            upper_bounds,
            variable_scales,
            residual_scales,
            gold_configurations,
            gold_targets,
            saved_starts,
            artifacts,
            metadata,
        )
    end
end

function DirectAnalyticProblem(
    instance_id::AbstractString,
    family_id::AbstractString,
    strata::Tuple{Vararg{Symbol}},
    parameters,
    dimension::Integer,
    residual_dimension::Integer,
    residual!,
    jacobian!,
    target,
    lower_bounds::AbstractVector{<:Real},
    upper_bounds::AbstractVector{<:Real},
    variable_scales::AbstractVector{<:Real},
    residual_scales::AbstractVector{<:Real},
    gold_configurations::AbstractMatrix{<:Real},
    gold_targets::AbstractVector{<:AbstractGoldTargetDescriptor},
    saved_starts::AbstractMatrix{<:Real},
    extra_artifacts::AbstractVector{MaterializedArtifact},
    metadata::AbstractDict{Symbol},
)
    id = String(instance_id)
    family = String(family_id)
    isempty(id) && throw(ArgumentError("instance_id must be nonempty"))
    isempty(family) && throw(ArgumentError("family_id must be nonempty"))
    isempty(strata) && throw(ArgumentError("at least one critical stratum is required"))
    all(stratum -> stratum in (:S1, :S2, :S3, :S4, :S5, :S6, :S7, :S8), strata) ||
        throw(ArgumentError("strata must be S1 through S8"))
    length(strata) == length(unique(strata)) ||
        throw(ArgumentError("strata must be unique"))

    d = Int(dimension)
    m = Int(residual_dimension)
    d > 0 || throw(ArgumentError("dimension must be positive"))
    m > 0 || throw(ArgumentError("residual_dimension must be positive"))
    lower = Float64[lower_bounds...]
    upper = Float64[upper_bounds...]
    xscale = Float64[variable_scales...]
    rscale = Float64[residual_scales...]
    length(lower) == length(upper) == length(xscale) == d ||
        throw(DimensionMismatch("bound and variable scale lengths must equal dimension"))
    length(rscale) == m ||
        throw(DimensionMismatch("residual scale length must equal residual_dimension"))
    all(isfinite, lower) && all(isfinite, upper) && all(isfinite, xscale) &&
        all(isfinite, rscale) || throw(ArgumentError("bounds and scales must be finite"))
    all(lower .< upper) || throw(ArgumentError("every lower bound must be below upper"))
    all(>(0), xscale) && all(>(0), rscale) ||
        throw(ArgumentError("all scales must be positive"))

    configurations = Matrix{Float64}(gold_configurations)
    size(configurations, 1) == d ||
        throw(DimensionMismatch("Gold configurations must have dimension rows"))
    all(isfinite, configurations) ||
        throw(ArgumentError("Gold configurations must be finite"))
    starts = Matrix{Float64}(saved_starts)
    size(starts, 1) == d || throw(DimensionMismatch("saved starts must have dimension rows"))
    all(isfinite, starts) || throw(ArgumentError("saved starts must be finite"))

    targets = AbstractGoldTargetDescriptor[gold_targets...]
    isempty(targets) && throw(ArgumentError("at least one distinct Gold target is required"))
    ids = [entry.target_id for entry in targets]
    length(ids) == length(unique(ids)) || throw(ArgumentError("Gold target IDs must be unique"))
    represented = Int[]
    for entry in targets
        append!(represented, entry.configurations)
    end
    sort(represented) == collect(1:size(configurations, 2)) ||
        throw(ArgumentError("every Gold configuration must belong to exactly one target"))

    artifacts = MaterializedArtifact[
        MaterializedArtifact(:gold_configurations, configurations),
        MaterializedArtifact(:saved_starts, starts),
        MaterializedArtifact(:bounds, hcat(lower, upper)),
        MaterializedArtifact(:scales, reshape(vcat(xscale, rscale), :, 1)),
    ]
    append!(artifacts, extra_artifacts)
    artifact_names = [entry.name for entry in artifacts]
    length(artifact_names) == length(unique(artifact_names)) ||
        throw(ArgumentError("materialized artifact names must be unique"))

    return DirectAnalyticProblem{
        typeof(parameters),
        typeof(residual!),
        typeof(jacobian!),
        typeof(target),
    }(
        id,
        family,
        strata,
        parameters,
        d,
        m,
        residual!,
        jacobian!,
        target,
        lower,
        upper,
        xscale,
        rscale,
        configurations,
        targets,
        starts,
        artifacts,
        Dict{Symbol,Any}(metadata),
    )
end

has_analytic_jacobian(problem::DirectAnalyticProblem) = problem.jacobian! !== nothing
saved_starts(problem::DirectAnalyticProblem) = copy(problem.saved_starts)
