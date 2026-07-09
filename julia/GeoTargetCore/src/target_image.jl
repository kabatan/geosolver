"""Local-only classes; likely-continuous reuses Base `TARGET_LIKELY_CONTINUOUS`."""
@enum LocalTargetImageClassification::UInt8 begin
    TARGET_LOCALLY_ISOLATED = 0
    TARGET_LOCALLY_CONSTANT_MANIFOLD = 1
    TARGET_IMAGE_INCONCLUSIVE = 2
end

const TargetImageClassification = Union{LocalTargetImageClassification,TargetImageStatus}

@enum TargetImageDiagnosticFailure::UInt8 begin
    TARGET_IMAGE_DIAGNOSTIC_NONE = 0
    TARGET_IMAGE_CAPABILITY_UNAVAILABLE = 1
    TARGET_IMAGE_BASE_EVALUATION_FAILED = 2
    TARGET_IMAGE_BASE_SEMANTICS_FAILED = 3
    TARGET_IMAGE_BASE_NOT_ON_RELATION = 4
    TARGET_IMAGE_INSUFFICIENT_STENCIL = 5
    TARGET_IMAGE_NONFINITE_LINEARIZATION = 6
    TARGET_IMAGE_INSUFFICIENT_PROBES = 7
    TARGET_IMAGE_SINGULAR_LINEARIZATION = 8
end

@enum TargetDifferenceScheme::UInt8 begin
    TARGET_DIFFERENCE_CENTRAL = 0
    TARGET_DIFFERENCE_FORWARD = 1
    TARGET_DIFFERENCE_BACKWARD = 2
    TARGET_DIFFERENCE_UNAVAILABLE = 3
end

"""Numerical controls for normalized finite differences, SVD rank and probes."""
struct TargetImageDiagnosticOptions
    finite_difference_radius::Float64
    probe_radii::Tuple
    relation_tolerance::Float64
    rank_absolute_tolerance::Float64
    rank_relative_tolerance::Float64
    target_sensitivity_tolerance::Float64
    probe_target_tolerance::Float64
    branch_margin_tolerance::Float64
    capability::Capability
    precision_bits::Int

    function TargetImageDiagnosticOptions(
        ;
        finite_difference_radius::Real = 1.0e-5,
        probe_radii = (1.0e-4, 1.0e-3, 1.0e-2),
        relation_tolerance::Real = 1.0e-8,
        rank_absolute_tolerance::Real = 0.0,
        rank_relative_tolerance::Real = sqrt(eps(Float64)),
        target_sensitivity_tolerance::Real = 1.0e-8,
        probe_target_tolerance::Real = 1.0e-8,
        branch_margin_tolerance::Real = 0.0,
        capability::Capability = C0,
        precision_bits::Integer = 256,
    )
        radius = Float64(finite_difference_radius)
        isfinite(radius) && radius > 0 || throw(
            ArgumentError("finite_difference_radius must be finite and positive"),
        )
        frozen_probe_radii = Tuple(sort!(unique(Float64[radius for radius in probe_radii])))
        isempty(frozen_probe_radii) && throw(ArgumentError("probe_radii cannot be empty"))
        all(radius -> isfinite(radius) && radius > 0, frozen_probe_radii) || throw(
            ArgumentError("probe_radii must be finite and positive"),
        )
        tolerances = Float64.((
            relation_tolerance,
            rank_absolute_tolerance,
            rank_relative_tolerance,
            target_sensitivity_tolerance,
            probe_target_tolerance,
            branch_margin_tolerance,
        ))
        all(value -> isfinite(value) && value >= 0, tolerances) || throw(
            ArgumentError("target-image tolerances must be finite and nonnegative"),
        )
        capability in (C0, C2) || throw(
            CapabilityError(capability, "target-image diagnostics support only C0 and C2"),
        )
        precision_bits >= 53 || throw(ArgumentError("precision_bits must be at least 53"))
        return new(
            radius,
            frozen_probe_radii,
            tolerances...,
            capability,
            Int(precision_bits),
        )
    end
end

"""Non-certifying local rank, nullspace and target-sensitivity evidence."""
struct TargetImageDiagnostic
    classification::TargetImageClassification
    failure::TargetImageDiagnosticFailure
    diagnostic::Union{Nothing,String}
    base_observation::OracleObservation
    capability::Capability
    precision_bits::Int
    linearization_computed::Bool
    scaled_relation_jacobian::Matrix{Float64}
    target_gradient::Vector{Float64}
    singular_values::Vector{Float64}
    numerical_rank::Union{Nothing,Int}
    rank_threshold::Float64
    nullspace_basis::Matrix{Float64}
    nullspace_target_projection::Vector{Float64}
    nullspace_target_sensitivity::Float64
    max_probe_target_variation::Float64
    max_probe_relation_drift::Float64
    probe_coverage::Tuple
    difference_schemes::Tuple
    condition_estimate::Union{Nothing,Float64}
    oracle_work::Int
    sampled_points::Int
    accepted_points::Int
    target_dependencies::Tuple
    svd_numeric_type::String

    function TargetImageDiagnostic(
        classification::TargetImageClassification,
        failure::TargetImageDiagnosticFailure,
        diagnostic::Union{Nothing,String},
        base_observation::OracleObservation,
        capability::Capability,
        precision_bits::Int,
        linearization_computed::Bool,
        scaled_relation_jacobian::AbstractMatrix,
        target_gradient::AbstractVector,
        singular_values::AbstractVector,
        numerical_rank::Union{Nothing,Int},
        rank_threshold::Real,
        nullspace_basis::AbstractMatrix,
        nullspace_target_projection::AbstractVector,
        nullspace_target_sensitivity::Real,
        max_probe_target_variation::Real,
        max_probe_relation_drift::Real,
        probe_coverage,
        difference_schemes,
        condition_estimate::Union{Nothing,Real},
        oracle_work::Int,
        sampled_points::Int,
        accepted_points::Int,
        target_dependencies,
        svd_numeric_type::AbstractString,
    )
        classification isa TargetImageStatus && classification != TARGET_LIKELY_CONTINUOUS && throw(
            InvariantError(
                :certified_target_image_from_diagnostic,
                "a local diagnostic may return only TARGET_LIKELY_CONTINUOUS from TargetImageStatus",
            ),
        )
        inconclusive = classification == TARGET_IMAGE_INCONCLUSIVE
        inconclusive == (failure != TARGET_IMAGE_DIAGNOSTIC_NONE) || throw(
            InvariantError(
                :target_image_failure_mismatch,
                "only inconclusive diagnostics carry a failure reason",
            ),
        )
        inconclusive == (diagnostic !== nothing) || throw(
            InvariantError(
                :target_image_diagnostic_mismatch,
                "only inconclusive diagnostics carry diagnostic text",
            ),
        )
        oracle_work >= 0 || throw(InvariantError(:negative_oracle_work, "oracle work is negative"))
        0 <= accepted_points <= sampled_points || throw(
            InvariantError(:invalid_sample_count, "accepted sample count is inconsistent"),
        )
        numerical_rank === nothing || 0 <= numerical_rank <= size(scaled_relation_jacobian, 2) ||
            throw(InvariantError(:invalid_numerical_rank, "numerical rank is out of range"))
        frozen_condition = condition_estimate === nothing ? nothing : Float64(condition_estimate)
        frozen_condition === nothing || !isnan(frozen_condition) || throw(
            InvariantError(:invalid_condition_estimate, "condition estimate cannot be NaN"),
        )
        return new(
            classification,
            failure,
            diagnostic,
            base_observation,
            capability,
            precision_bits,
            linearization_computed,
            Matrix{Float64}(scaled_relation_jacobian),
            Vector{Float64}(target_gradient),
            Vector{Float64}(singular_values),
            numerical_rank,
            Float64(rank_threshold),
            Matrix{Float64}(nullspace_basis),
            Vector{Float64}(nullspace_target_projection),
            Float64(nullspace_target_sensitivity),
            Float64(max_probe_target_variation),
            Float64(max_probe_relation_drift),
            Tuple(Int(value) for value in probe_coverage),
            Tuple(
                value isa TargetDifferenceScheme ? value : TargetDifferenceScheme(value) for
                value in difference_schemes
            ),
            frozen_condition,
            oracle_work,
            sampled_points,
            accepted_points,
            Tuple(Int(value) for value in target_dependencies),
            String(svd_numeric_type),
        )
    end
end

function TargetImageDiagnostic(
    classification::TargetImageStatus,
    source::TargetImageDiagnostic,
)
    return TargetImageDiagnostic(
        classification,
        source.failure,
        source.diagnostic,
        source.base_observation,
        source.capability,
        source.precision_bits,
        source.linearization_computed,
        source.scaled_relation_jacobian,
        source.target_gradient,
        source.singular_values,
        source.numerical_rank,
        source.rank_threshold,
        source.nullspace_basis,
        source.nullspace_target_projection,
        source.nullspace_target_sensitivity,
        source.max_probe_target_variation,
        source.max_probe_relation_drift,
        source.probe_coverage,
        source.difference_schemes,
        source.condition_estimate,
        source.oracle_work,
        source.sampled_points,
        source.accepted_points,
        source.target_dependencies,
        source.svd_numeric_type,
    )
end

mutable struct _TargetImageWork
    compiled::CompiledProblem
    base_coordinates::Vector
    base_observation::OracleObservation
    options::TargetImageDiagnosticOptions
    workspace::CompiledWorkspace
    oracle_work::Int
    sampled_points::Int
    accepted_points::Int
end

function _target_image_empty_observation(status, diagnostic)
    return OracleObservation((), nothing, (), (), (), status, 0, diagnostic)
end

function _target_image_capability_available(compiled, options)
    options.capability == C0 && return true
    supports(capabilities(compiled), C2) || return false
    return all(variable -> BigFloat(0) isa variable.runtime_type, compiled.variables)
end

function _same_branch_signature(first::OracleObservation, second::OracleObservation)
    first_branches = Tuple(sort(
        collect(first.branches);
        by = branch -> string(branch.decision.choice_node),
    ))
    second_branches = Tuple(sort(
        collect(second.branches);
        by = branch -> string(branch.decision.choice_node),
    ))
    length(first_branches) == length(second_branches) || return false
    return all(
        left.decision.choice_node == right.decision.choice_node &&
        left.decision.key == right.decision.key for
        (left, right) in zip(first_branches, second_branches)
    )
end

function _separated_branches(observation, tolerance)
    return all(
        branch -> branch.validity_margin > tolerance && branch.selector_margin > tolerance,
        observation.branches,
    )
end

function _usable_target_image_base(observation, options)
    observation.status == EVAL_OK || return false
    observation.target isa Real && isfinite(observation.target) || return false
    canonical_feasible(observation; residual_tolerance = options.relation_tolerance) || return false
    all(
        relation -> relation.truth !== false || !iszero(relation.raw),
        observation.relations,
    ) || return false
    return _separated_branches(observation, options.branch_margin_tolerance)
end

function _usable_target_image_sample(observation, base, options)
    observation.status == EVAL_OK || return false
    observation.target isa Real && isfinite(observation.target) || return false
    length(observation.relations) == length(base.relations) || return false
    all(relation -> relation.scaled isa Real && isfinite(relation.scaled), observation.relations) ||
        return false
    all(guard -> guard.valid, observation.guards) || return false
    all(domain -> domain.valid, observation.domains) || return false
    _same_branch_signature(observation, base) || return false
    return _separated_branches(observation, options.branch_margin_tolerance)
end

function _within_variable_bounds(compiled, coordinates)
    for variable in compiled.variables
        value = coordinates[variable.index]
        variable.spec.lower !== nothing && value < variable.spec.lower && return false
        variable.spec.upper !== nothing && value > variable.spec.upper && return false
    end
    return true
end

function _normalized_perturbation(work::_TargetImageWork, delta)
    return [
        begin
            coordinate, scale, step = promote(
                work.base_coordinates[index],
                work.compiled.variables[index].spec.scale,
                delta[index],
            )
            coordinate + scale * step
        end for index in eachindex(work.base_coordinates)
    ]
end

function _sample_delta!(work::_TargetImageWork, delta)
    coordinates = _normalized_perturbation(work, delta)
    _within_variable_bounds(work.compiled, coordinates) || return nothing
    observation = evaluate(
        work.compiled,
        coordinates;
        capability = work.options.capability,
        workspace = work.workspace,
    )
    work.oracle_work += observation.evaluation_cost
    work.sampled_points += 1
    if _usable_target_image_sample(observation, work.base_observation, work.options)
        work.accepted_points += 1
        return observation
    end
    return nothing
end

function _float_target_image_value(value)
    # Narrow representation boundary: plugin evaluation errors were already
    # converted to OracleObservation; only unsupported Float64 projections fail closed here.
    converted = try
        Float64(value)
    catch error
        error isa Union{InexactError,OverflowError,MethodError} || rethrow()
        return nothing
    end
    return isfinite(converted) ? converted : nothing
end

function _float_relation_vector(observation)
    values = Float64[]
    for relation in observation.relations
        value = _float_target_image_value(relation.scaled)
        value === nothing && return nothing
        push!(values, value)
    end
    return values
end

function _linearize_target_image!(work::_TargetImageWork)
    variable_count = length(work.compiled.variables)
    relation_count = length(work.base_observation.relations)
    jacobian = zeros(Float64, relation_count, variable_count)
    gradient = zeros(Float64, variable_count)
    schemes = fill(TARGET_DIFFERENCE_UNAVAILABLE, variable_count)
    base_residual = _float_relation_vector(work.base_observation)
    base_target = _float_target_image_value(work.base_observation.target)
    (base_residual === nothing || base_target === nothing) && return nothing
    radius = work.options.finite_difference_radius

    for column in 1:variable_count
        plus_delta = zeros(Float64, variable_count)
        minus_delta = zeros(Float64, variable_count)
        plus_delta[column] = radius
        minus_delta[column] = -radius
        plus = _sample_delta!(work, plus_delta)
        minus = _sample_delta!(work, minus_delta)
        plus_residual = plus === nothing ? nothing : _float_relation_vector(plus)
        minus_residual = minus === nothing ? nothing : _float_relation_vector(minus)
        plus_target = plus === nothing ? nothing : _float_target_image_value(plus.target)
        minus_target = minus === nothing ? nothing : _float_target_image_value(minus.target)

        if plus_residual !== nothing && minus_residual !== nothing &&
           plus_target !== nothing && minus_target !== nothing
            jacobian[:, column] .= (plus_residual .- minus_residual) ./ (2 * radius)
            gradient[column] = (plus_target - minus_target) / (2 * radius)
            schemes[column] = TARGET_DIFFERENCE_CENTRAL
        elseif plus_residual !== nothing && plus_target !== nothing
            jacobian[:, column] .= (plus_residual .- base_residual) ./ radius
            gradient[column] = (plus_target - base_target) / radius
            schemes[column] = TARGET_DIFFERENCE_FORWARD
        elseif minus_residual !== nothing && minus_target !== nothing
            jacobian[:, column] .= (base_residual .- minus_residual) ./ radius
            gradient[column] = (base_target - minus_target) / radius
            schemes[column] = TARGET_DIFFERENCE_BACKWARD
        end
    end
    return jacobian, gradient, Tuple(schemes)
end

function _target_image_svd(jacobian, options)
    factorization = svd(jacobian; full = true)
    singular_values = Vector{Float64}(factorization.S)
    largest = isempty(singular_values) ? 0.0 : maximum(singular_values)
    threshold = max(options.rank_absolute_tolerance, options.rank_relative_tolerance * largest)
    numerical_rank = count(value -> value > threshold, singular_values)
    variable_count = size(jacobian, 2)
    right_vectors = Matrix{Float64}(factorization.Vt')
    nullspace = numerical_rank < variable_count ?
                right_vectors[:, (numerical_rank + 1):variable_count] :
                zeros(Float64, variable_count, 0)
    for column in axes(nullspace, 2)
        vector = view(nullspace, :, column)
        pivot = argmax(abs.(vector))
        vector[pivot] < 0 && (vector .*= -1)
    end
    condition = numerical_rank == 0 ? Inf : singular_values[1] / singular_values[numerical_rank]
    return singular_values, numerical_rank, threshold, nullspace, condition
end

function _probe_target_nullspace!(work, nullspace)
    base_target = Float64(work.base_observation.target)
    max_variation = 0.0
    max_relation_drift = 0.0
    coverage = Int[]
    variable_count = size(nullspace, 1)
    for direction_index in axes(nullspace, 2)
        direction = view(nullspace, :, direction_index)
        direction_coverage = 0
        for radius in work.options.probe_radii
            for sign in (1.0, -1.0)
                delta = Vector{Float64}(undef, variable_count)
                delta .= sign * radius .* direction
                observation = _sample_delta!(work, delta)
                observation === nothing && continue
                target = _float_target_image_value(observation.target)
                residual = _float_relation_vector(observation)
                (target === nothing || residual === nothing) && continue
                direction_coverage += 1
                max_variation = max(max_variation, abs(target - base_target))
                residual_drift = isempty(residual) ? 0.0 : maximum(abs, residual)
                max_relation_drift = max(max_relation_drift, residual_drift)
            end
        end
        push!(coverage, direction_coverage)
    end
    return max_variation, max_relation_drift, Tuple(coverage)
end

function _target_image_result(
    classification,
    base,
    options,
    target_dependencies;
    failure = TARGET_IMAGE_DIAGNOSTIC_NONE,
    diagnostic = nothing,
    linearization_computed = false,
    jacobian = zeros(Float64, length(base.relations), length(target_dependencies)),
    gradient = Float64[],
    singular_values = Float64[],
    numerical_rank = nothing,
    rank_threshold = 0.0,
    nullspace = zeros(Float64, length(gradient), 0),
    projection = Float64[],
    sensitivity = 0.0,
    probe_variation = 0.0,
    probe_relation_drift = 0.0,
    probe_coverage = (),
    schemes = (),
    condition = nothing,
    oracle_work = base.evaluation_cost,
    sampled_points = 1,
    accepted_points = 0,
)
    effective_precision = options.capability == C2 ? options.precision_bits : 53
    return TargetImageDiagnostic(
        classification,
        failure,
        diagnostic,
        base,
        options.capability,
        effective_precision,
        linearization_computed,
        jacobian,
        gradient,
        singular_values,
        numerical_rank,
        rank_threshold,
        nullspace,
        projection,
        sensitivity,
        probe_variation,
        probe_relation_drift,
        probe_coverage,
        schemes,
        condition,
        oracle_work,
        sampled_points,
        accepted_points,
        target_dependencies,
        "Float64 SVD from explicitly converted oracle samples",
    )
end

function _analyze_target_image(compiled, coordinates, options)
    workspace = CompiledWorkspace(compiled)
    base = evaluate(compiled, coordinates; capability = options.capability, workspace)
    target_dependencies = compiled.sparsity.target_variables
    if !_usable_target_image_base(base, options)
        failure = if base.status in (EVAL_INVALID_DOMAIN, EVAL_INVALID_BRANCH, EVAL_AMBIGUOUS_BRANCH)
            TARGET_IMAGE_BASE_SEMANTICS_FAILED
        elseif base.status != EVAL_OK
            TARGET_IMAGE_BASE_EVALUATION_FAILED
        elseif any(
            relation -> abs(relation.scaled) > options.relation_tolerance ||
                        (relation.truth === false && iszero(relation.raw)),
            base.relations,
        )
            TARGET_IMAGE_BASE_NOT_ON_RELATION
        else
            TARGET_IMAGE_BASE_SEMANTICS_FAILED
        end
        return _target_image_result(
            TARGET_IMAGE_INCONCLUSIVE,
            base,
            options,
            target_dependencies;
            failure,
            diagnostic = "base point is not usable for local target-image analysis: $(base.status)",
            jacobian = zeros(Float64, length(base.relations), length(compiled.variables)),
            gradient = zeros(Float64, length(compiled.variables)),
            accepted_points = 0,
        )
    end

    if isempty(target_dependencies)
        return _target_image_result(
            TARGET_LOCALLY_CONSTANT_MANIFOLD,
            base,
            options,
            target_dependencies;
            jacobian = zeros(Float64, length(base.relations), length(compiled.variables)),
            gradient = zeros(Float64, length(compiled.variables)),
            accepted_points = 1,
        )
    end

    work = _TargetImageWork(
        compiled,
        collect(coordinates),
        base,
        options,
        workspace,
        base.evaluation_cost,
        1,
        1,
    )
    linearization = _linearize_target_image!(work)
    if linearization === nothing
        return _target_image_result(
            TARGET_IMAGE_INCONCLUSIVE,
            base,
            options,
            target_dependencies;
            failure = TARGET_IMAGE_NONFINITE_LINEARIZATION,
            diagnostic = "oracle values cannot be represented in the explicit Float64 SVD control",
            jacobian = zeros(Float64, length(base.relations), length(compiled.variables)),
            gradient = zeros(Float64, length(compiled.variables)),
            oracle_work = work.oracle_work,
            sampled_points = work.sampled_points,
            accepted_points = work.accepted_points,
        )
    end
    jacobian, gradient, schemes = linearization
    if any(scheme -> scheme == TARGET_DIFFERENCE_UNAVAILABLE, schemes)
        return _target_image_result(
            TARGET_IMAGE_INCONCLUSIVE,
            base,
            options,
            target_dependencies;
            failure = TARGET_IMAGE_INSUFFICIENT_STENCIL,
            diagnostic = "no bounds/domain/branch-preserving finite-difference stencil exists",
            linearization_computed = true,
            jacobian,
            gradient,
            schemes,
            oracle_work = work.oracle_work,
            sampled_points = work.sampled_points,
            accepted_points = work.accepted_points,
        )
    end

    singular_values, numerical_rank, rank_threshold, nullspace, condition =
        _target_image_svd(jacobian, options)
    projection = Vector{Float64}(nullspace' * gradient)
    sensitivity = norm(projection)
    if numerical_rank == length(compiled.variables)
        return _target_image_result(
            TARGET_LOCALLY_ISOLATED,
            base,
            options,
            target_dependencies;
            linearization_computed = true,
            jacobian,
            gradient,
            singular_values,
            numerical_rank,
            rank_threshold,
            nullspace,
            projection,
            sensitivity,
            schemes,
            condition,
            oracle_work = work.oracle_work,
            sampled_points = work.sampled_points,
            accepted_points = work.accepted_points,
        )
    end

    probe_variation, probe_relation_drift, probe_coverage =
        _probe_target_nullspace!(work, nullspace)
    if any(iszero, probe_coverage)
        return _target_image_result(
            TARGET_IMAGE_INCONCLUSIVE,
            base,
            options,
            target_dependencies;
            failure = TARGET_IMAGE_INSUFFICIENT_PROBES,
            diagnostic = "at least one nullspace direction has no bounds/domain/branch-preserving probe",
            linearization_computed = true,
            jacobian,
            gradient,
            singular_values,
            numerical_rank,
            rank_threshold,
            nullspace,
            projection,
            sensitivity,
            probe_variation,
            probe_relation_drift,
            probe_coverage,
            schemes,
            condition,
            oracle_work = work.oracle_work,
            sampled_points = work.sampled_points,
            accepted_points = work.accepted_points,
        )
    end

    target_scale = max(1.0, abs(Float64(base.target)))
    continuous = sensitivity > options.target_sensitivity_tolerance * target_scale ||
                 probe_variation > options.probe_target_tolerance * target_scale
    regular_manifold = isempty(base.relations) ||
                       numerical_rank == min(
        length(base.relations),
        length(compiled.variables),
    )
    if continuous && !regular_manifold
        return _target_image_result(
            TARGET_IMAGE_INCONCLUSIVE,
            base,
            options,
            target_dependencies;
            failure = TARGET_IMAGE_SINGULAR_LINEARIZATION,
            diagnostic = "rank-deficient relation linearization cannot distinguish a singular isolated root from a feasible manifold",
            linearization_computed = true,
            jacobian,
            gradient,
            singular_values,
            numerical_rank,
            rank_threshold,
            nullspace,
            projection,
            sensitivity,
            probe_variation,
            probe_relation_drift,
            probe_coverage,
            schemes,
            condition,
            oracle_work = work.oracle_work,
            sampled_points = work.sampled_points,
            accepted_points = work.accepted_points,
        )
    end
    classification = continuous ? TARGET_LIKELY_CONTINUOUS : TARGET_LOCALLY_CONSTANT_MANIFOLD
    return _target_image_result(
        classification,
        base,
        options,
        target_dependencies;
        linearization_computed = true,
        jacobian,
        gradient,
        singular_values,
        numerical_rank,
        rank_threshold,
        nullspace,
        projection,
        sensitivity,
        probe_variation,
        probe_relation_drift,
        probe_coverage,
        schemes,
        condition,
        oracle_work = work.oracle_work,
        sampled_points = work.sampled_points,
        accepted_points = work.accepted_points,
    )
end

"""
Estimate the local target image without making any completeness or exactness claim.

Finite differences are taken in normalized variables. SVD is an explicitly
Float64 diagnostic control even when samples are evaluated through C2 BigFloat.
"""
function analyze_target_image(
    compiled::CompiledProblem,
    x::AbstractVector;
    options::TargetImageDiagnosticOptions = TargetImageDiagnosticOptions(),
)
    length(x) == length(compiled.variables) || throw(
        ArgumentError("expected $(length(compiled.variables)) variables, received $(length(x))"),
    )
    if !_target_image_capability_available(compiled, options)
        diagnostic = "requested $(options.capability) is not available on every target-image path"
        observation = _target_image_empty_observation(EVAL_UNSUPPORTED_CAPABILITY, diagnostic)
        return _target_image_result(
            TARGET_IMAGE_INCONCLUSIVE,
            observation,
            options,
            compiled.sparsity.target_variables;
            failure = TARGET_IMAGE_CAPABILITY_UNAVAILABLE,
            diagnostic,
            jacobian = zeros(Float64, length(compiled.relations), length(compiled.variables)),
            gradient = zeros(Float64, length(compiled.variables)),
            sampled_points = 0,
            accepted_points = 0,
        )
    end
    if options.capability == C2
        return setprecision(BigFloat, options.precision_bits) do
            coordinates = BigFloat[BigFloat(value) for value in x]
            _analyze_target_image(compiled, coordinates, options)
        end
    end
    return _analyze_target_image(compiled, collect(x), options)
end
