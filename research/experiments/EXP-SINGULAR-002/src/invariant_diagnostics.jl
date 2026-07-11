"""Frozen, outcome-independent constants for the S5 static diagnostic seam."""
Base.@kwdef struct InvariantDiagnosticOptions{T<:AbstractFloat}
    uncertainty_multiplier::T = T(2)
    roundoff_multiplier::T = T(16)
    robust_gap_ratio_max::T = T(1.0e-6)
    retained_uncertainty_multiplier_min::T = T(8)
    gap_winner_ratio_min::T = T(16)
    projector_uncertainty_multiplier::T = T(4)
    projector_distance_max::T = T(0.25)
    tensor_condition_max::T = T(1.0e12)
    contracted_condition_max::T = T(1.0e12)
    line_reconciliation_tolerance::T = T(6.25e-12)
    maximum_nullity::Int = 4
end

function _validate_options(options::InvariantDiagnosticOptions)
    options.uncertainty_multiplier >= 1 || throw(ArgumentError("uncertainty multiplier"))
    options.roundoff_multiplier > 0 || throw(ArgumentError("roundoff multiplier"))
    0 < options.robust_gap_ratio_max < 1 || throw(ArgumentError("gap ratio"))
    options.retained_uncertainty_multiplier_min > 1 ||
        throw(ArgumentError("retained uncertainty multiplier"))
    options.gap_winner_ratio_min > 1 || throw(ArgumentError("gap winner ratio"))
    options.projector_uncertainty_multiplier > 0 ||
        throw(ArgumentError("projector uncertainty multiplier"))
    0 < options.projector_distance_max < 1 ||
        throw(ArgumentError("projector distance maximum"))
    options.tensor_condition_max > 1 || throw(ArgumentError("tensor condition"))
    options.contracted_condition_max > 1 ||
        throw(ArgumentError("contracted condition"))
    options.line_reconciliation_tolerance > 0 ||
        throw(ArgumentError("line reconciliation tolerance"))
    options.maximum_nullity >= 1 || throw(ArgumentError("maximum nullity"))
    return options
end

"""
Return maps `(variable_to_physical, residual_to_normalized)` from declared
positive-definite metrics.  They satisfy

`||dx||_Gx = ||variable_to_physical \\ dx||_2` in inverse-map form and
`||r||_Gr = ||residual_to_normalized * r||_2`.
"""
function declared_metric_maps(
    variable_metric::AbstractMatrix{T},
    residual_metric::AbstractMatrix{T},
) where {T<:AbstractFloat}
    nx = size(variable_metric, 1)
    nr = size(residual_metric, 1)
    size(variable_metric) == (nx, nx) || throw(DimensionMismatch("variable metric"))
    size(residual_metric) == (nr, nr) || throw(DimensionMismatch("residual metric"))
    nx > 0 && nr > 0 || throw(ArgumentError("empty metric"))
    all(isfinite, variable_metric) || throw(ArgumentError("nonfinite variable metric"))
    all(isfinite, residual_metric) || throw(ArgumentError("nonfinite residual metric"))
    variable_metric == transpose(variable_metric) ||
        throw(ArgumentError("variable metric must be symmetric"))
    residual_metric == transpose(residual_metric) ||
        throw(ArgumentError("residual metric must be symmetric"))
    variable_factor = cholesky(Symmetric(Matrix{T}(variable_metric)); check=true).U
    residual_factor = cholesky(Symmetric(Matrix{T}(residual_metric)); check=true).U
    identity_x = Matrix{T}(I, nx, nx)
    return (
        variable_to_physical=Matrix{T}(variable_factor \ identity_x),
        residual_to_normalized=Matrix{T}(residual_factor),
    )
end

"""Map a physical Jacobian into the two declared normalized metrics."""
function normalized_jacobian(
    jacobian::AbstractMatrix{T},
    variable_to_physical::AbstractMatrix{T},
    residual_to_normalized::AbstractMatrix{T},
) where {T<:AbstractFloat}
    m, n = size(jacobian)
    size(variable_to_physical) == (n, n) ||
        throw(DimensionMismatch("variable normalization map"))
    size(residual_to_normalized) == (m, m) ||
        throw(DimensionMismatch("residual normalization map"))
    result = residual_to_normalized * jacobian * variable_to_physical
    all(isfinite, result) || throw(ArgumentError("nonfinite normalized Jacobian"))
    return Matrix{T}(result)
end

struct JacobianPairEvidence{T<:AbstractFloat}
    coarse::Matrix{T}
    fine::Matrix{T}
    delta_spectral::T
    roundoff_floor::T
    eta::T
    radius::T
    maximum_sample_norm::T
    callbacks::Int
end

function _finite_vector(value, length_expected::Int, ::Type{T}) where {T<:AbstractFloat}
    result = T[value...]
    length(result) == length_expected || throw(DimensionMismatch("residual callback"))
    all(isfinite, result) || throw(ArgumentError("nonfinite residual callback"))
    return result
end

"""
Acquire `A_h` and `A_(h/2)` in normalized coordinates around `endpoint`.
The returned callback count is exactly `4n`.  `charge_callback` runs before
every black-box call, so a callback that throws still consumes work in the
caller's single endpoint-global ledger.
"""
function acquire_normalized_jacobian_pair(
    residual,
    endpoint::AbstractVector{T},
    variable_to_physical::AbstractMatrix{T},
    residual_to_normalized::AbstractMatrix{T},
    radius::T;
    options::InvariantDiagnosticOptions{T}=InvariantDiagnosticOptions{T}(),
    charge_callback=() -> nothing,
) where {T<:AbstractFloat}
    _validate_options(options)
    n = length(endpoint)
    m = size(residual_to_normalized, 1)
    n > 1 || throw(ArgumentError("singular route requires dimension at least two"))
    size(variable_to_physical) == (n, n) || throw(DimensionMismatch("variable map"))
    size(residual_to_normalized) == (m, m) || throw(DimensionMismatch("residual map"))
    isfinite(radius) && radius > 0 || throw(ArgumentError("finite positive radius required"))
    all(isfinite, endpoint) || throw(ArgumentError("nonfinite endpoint"))

    coarse = zeros(T, m, n)
    fine = zeros(T, m, n)
    maximum_sample_norm = zero(T)
    for (destination, local_radius) in ((coarse, radius), (fine, radius / T(2)))
        for column in 1:n
            offset = local_radius .* view(variable_to_physical, :, column)
            charge_callback()
            plus = _finite_vector(residual(endpoint .+ offset), m, T)
            charge_callback()
            minus = _finite_vector(residual(endpoint .- offset), m, T)
            plus_normalized = residual_to_normalized * plus
            minus_normalized = residual_to_normalized * minus
            all(isfinite, plus_normalized) && all(isfinite, minus_normalized) ||
                throw(ArgumentError("nonfinite normalized residual"))
            destination[:, column] .= (plus_normalized .- minus_normalized) ./
                                       (T(2) * local_radius)
            maximum_sample_norm = max(
                maximum_sample_norm,
                norm(plus_normalized, 2),
                norm(minus_normalized, 2),
            )
        end
    end
    delta = T(opnorm(fine - coarse, 2))
    roundoff = options.roundoff_multiplier * eps(T) * sqrt(T(n)) *
               max(one(T), maximum_sample_norm) / (radius / T(2))
    eta = options.uncertainty_multiplier * delta + roundoff
    all(isfinite, coarse) && all(isfinite, fine) && isfinite(eta) ||
        throw(ArgumentError("invalid Jacobian-pair evidence"))
    return JacobianPairEvidence(
        coarse,
        fine,
        delta,
        roundoff,
        eta,
        radius,
        maximum_sample_norm,
        4n,
    )
end

struct RankCertificate{T<:AbstractFloat}
    status::Symbol
    reason::String
    rank::Int
    nullity::Int
    singular_values::Vector{T}
    lower::Vector{T}
    upper::Vector{T}
    gap_scores::Vector{T}
    eta::T
    retained_separation::T
    left_null_projector::Matrix{T}
    right_null_projector::Matrix{T}
    left_null_basis::Matrix{T}
    right_null_basis::Matrix{T}
end

function _unknown_rank(::Type{T}, n::Int, reason::AbstractString, eta::T) where {T}
    return RankCertificate(
        :unknown,
        String(reason),
        0,
        0,
        T[],
        T[],
        T[],
        T[],
        eta,
        zero(T),
        zeros(T, n, n),
        zeros(T, n, n),
        zeros(T, n, 0),
        zeros(T, n, 0),
    )
end

"""
Select a unique robust singular-value gap using Weyl intervals.  `eta` is an
empirical acquisition uncertainty, so `:certified` means numerically stable for
this experiment; it is not a mathematical singular-root certificate.
"""
function certify_weyl_rank(
    jacobian::AbstractMatrix{T},
    eta::T;
    options::InvariantDiagnosticOptions{T}=InvariantDiagnosticOptions{T}(),
) where {T<:AbstractFloat}
    _validate_options(options)
    n = size(jacobian, 2)
    size(jacobian) == (n, n) || throw(DimensionMismatch("square Jacobian required"))
    n > 1 || throw(ArgumentError("rank split requires dimension at least two"))
    all(isfinite, jacobian) || throw(ArgumentError("nonfinite Jacobian"))
    isfinite(eta) && eta >= 0 || throw(ArgumentError("invalid Jacobian uncertainty"))
    decomposition = svd(Matrix{T}(jacobian); full=true)
    values = T[decomposition.S...]
    arithmetic_floor = options.roundoff_multiplier * eps(T) *
                       max(one(T), isempty(values) ? one(T) : values[1])
    total_eta = max(eta, arithmetic_floor)
    lower = max.(zero(T), values .- total_eta)
    upper = values .+ total_eta
    scores = zeros(T, n - 1)
    qualifying = Int[]
    for boundary in 1:(n - 1)
        nullity = n - boundary
        nullity <= options.maximum_nullity || continue
        retained = lower[boundary]
        next_upper = upper[boundary + 1]
        retained > options.retained_uncertainty_multiplier_min * total_eta || continue
        ratio = next_upper / retained
        ratio <= options.robust_gap_ratio_max || continue
        scores[boundary] = retained / max(next_upper, total_eta)
        push!(qualifying, boundary)
    end
    isempty(qualifying) && return _unknown_rank(T, n, "no robust Weyl gap", total_eta)
    ordered = sort(qualifying; by=index -> scores[index], rev=true)
    winner = first(ordered)
    if length(ordered) > 1 &&
       scores[winner] < options.gap_winner_ratio_min * scores[ordered[2]]
        return _unknown_rank(T, n, "ambiguous robust Weyl gaps", total_eta)
    end
    nullity = n - winner
    left = Matrix{T}(decomposition.U[:, (winner + 1):n])
    right = Matrix{T}(decomposition.V[:, (winner + 1):n])
    left_projector = left * transpose(left)
    right_projector = right * transpose(right)
    separation = lower[winner] - upper[winner + 1]
    separation > 0 || return _unknown_rank(T, n, "overlapping Weyl intervals", total_eta)
    return RankCertificate(
        :certified,
        "unique robust Weyl gap",
        winner,
        nullity,
        values,
        lower,
        upper,
        scores,
        total_eta,
        separation,
        left_projector,
        right_projector,
        left,
        right,
    )
end

struct ProjectorStability{T<:AbstractFloat}
    passed::Bool
    reason::String
    left_distance::T
    right_distance::T
    bound::T
end

"""Compare subspaces without choosing or transporting an SVD basis."""
function projector_stability(
    first::RankCertificate{T},
    second::RankCertificate{T};
    options::InvariantDiagnosticOptions{T}=InvariantDiagnosticOptions{T}(),
) where {T<:AbstractFloat}
    _validate_options(options)
    first.status == :certified && second.status == :certified ||
        return ProjectorStability(false, "rank evidence unavailable", T(Inf), T(Inf), zero(T))
    first.rank == second.rank && first.nullity == second.nullity ||
        return ProjectorStability(false, "rank or nullity disagreement", T(Inf), T(Inf), zero(T))
    left_distance = T(opnorm(
        first.left_null_projector - second.left_null_projector,
        2,
    ))
    right_distance = T(opnorm(
        first.right_null_projector - second.right_null_projector,
        2,
    ))
    separation = min(first.retained_separation, second.retained_separation)
    separation > 0 ||
        return ProjectorStability(false, "nonpositive interval separation", left_distance, right_distance, zero(T))
    uncertainty_bound = options.projector_uncertainty_multiplier *
                        (first.eta + second.eta) / separation
    numerical_floor = T(32) * eps(T)
    bound = min(
        options.projector_distance_max,
        max(numerical_floor, uncertainty_bound),
    )
    passed = isfinite(left_distance) && isfinite(right_distance) &&
             left_distance <= bound && right_distance <= bound
    return ProjectorStability(
        passed,
        passed ? "projectors stable" : "projector distance exceeds uncertainty bound",
        left_distance,
        right_distance,
        bound,
    )
end

"""
Build the matrix of `Sym^2(N_right) -> N_left` in orthonormal bases.  Diagonal
columns represent `v_i*v_i'`; off-diagonal columns represent
`(v_i*v_j' + v_j*v_i')/sqrt(2)`, hence the `sqrt(2)` multiplier.  The optional
charge hook runs before every second-directional callback.
"""
function symmetric_projected_operator(
    second_directional,
    left_null_basis::AbstractMatrix{T},
    right_null_basis::AbstractMatrix{T},
    ;
    charge_callback=() -> nothing,
) where {T<:AbstractFloat}
    tensor = projected_hessian_tensor(
        second_directional,
        left_null_basis,
        right_null_basis;
        charge_callback,
    )
    return symmetric_projected_operator(tensor)
end

"""
Acquire the symmetric projected Hessian tensor
`T[alpha,i,j] = u_alpha' * D2F[v_i,v_j]`.  Only `i <= j` is sampled; symmetry
fills the other half.  The charge hook runs before every sampled callback.
"""
function projected_hessian_tensor(
    second_directional,
    left_null_basis::AbstractMatrix{T},
    right_null_basis::AbstractMatrix{T};
    charge_callback=() -> nothing,
) where {T<:AbstractFloat}
    m, left_dimension = size(left_null_basis)
    _, right_dimension = size(right_null_basis)
    left_dimension == right_dimension ||
        throw(DimensionMismatch("square-system left/right nullity disagreement"))
    right_dimension > 0 || throw(ArgumentError("empty nullspace"))
    tensor = zeros(T, left_dimension, right_dimension, right_dimension)
    for first in 1:right_dimension
        for second in first:right_dimension
            charge_callback()
            direction = _finite_vector(
                second_directional(
                    view(right_null_basis, :, first),
                    view(right_null_basis, :, second),
                ),
                m,
                T,
            )
            projected = transpose(left_null_basis) * direction
            tensor[:, first, second] .= projected
            tensor[:, second, first] .= projected
        end
    end
    all(isfinite, tensor) || throw(ArgumentError("nonfinite projected tensor"))
    return tensor
end


"""Flatten a projected Hessian tensor on an orthonormal `Sym^2` basis."""
function symmetric_projected_operator(tensor::AbstractArray{T,3}) where {T<:AbstractFloat}
    left_dimension, first_dimension, second_dimension = size(tensor)
    first_dimension == second_dimension || throw(DimensionMismatch("symmetric tensor"))
    left_dimension == first_dimension ||
        throw(DimensionMismatch("square-system projected tensor"))
    all(isfinite, tensor) || throw(ArgumentError("nonfinite projected tensor"))
    output = zeros(T, left_dimension, first_dimension * (first_dimension + 1) ÷ 2)
    column = 0
    for first in 1:first_dimension
        for second in first:second_dimension
            column += 1
            multiplier = first == second ? one(T) : sqrt(T(2))
            output[:, column] .= multiplier .* view(tensor, :, first, second)
        end
    end
    return output
end

struct TensorCertificate{T<:AbstractFloat}
    passed::Bool
    reason::String
    singular_values::Vector{T}
    lower::Vector{T}
    upper::Vector{T}
    eta::T
    condition_upper::T
end

"""Apply a paired-radius Weyl and condition gate to the projected tensor map."""
function certify_projected_tensor(
    coarse::AbstractMatrix{T},
    fine::AbstractMatrix{T};
    arithmetic_floor::T=zero(T),
    options::InvariantDiagnosticOptions{T}=InvariantDiagnosticOptions{T}(),
) where {T<:AbstractFloat}
    _validate_options(options)
    size(coarse) == size(fine) || throw(DimensionMismatch("tensor pair"))
    rows, columns = size(fine)
    rows > 0 && columns >= rows || throw(DimensionMismatch("projected tensor shape"))
    all(isfinite, coarse) && all(isfinite, fine) ||
        throw(ArgumentError("nonfinite projected tensor pair"))
    isfinite(arithmetic_floor) && arithmetic_floor >= 0 ||
        throw(ArgumentError("invalid tensor arithmetic floor"))
    values = T[svdvals(Matrix{T}(fine))...]
    eta = max(
        options.uncertainty_multiplier * T(opnorm(fine - coarse, 2)),
        arithmetic_floor,
        options.roundoff_multiplier * eps(T) * max(one(T), values[1]),
    )
    lower = max.(zero(T), values .- eta)
    upper = values .+ eta
    smallest_lower = lower[end]
    if !(smallest_lower > options.retained_uncertainty_multiplier_min * eta)
        return TensorCertificate(
            false,
            "projected tensor row-rank interval reaches uncertainty",
            values,
            lower,
            upper,
            eta,
            T(Inf),
        )
    end
    condition_upper = upper[1] / smallest_lower
    passed = isfinite(condition_upper) && condition_upper <= options.tensor_condition_max
    return TensorCertificate(
        passed,
        passed ? "projected tensor interval is full row rank" :
                 "projected tensor condition upper bound exceeded",
        values,
        lower,
        upper,
        eta,
        condition_upper,
    )
end

"""
Basis-covariant Gram contraction on the right nullspace:

`K[i,j] = sum(T[alpha,i,k] * T[alpha,j,k], alpha, k)`.

Left-null rotations and the contracted right-null index cancel, while a change
of the remaining right-null basis transforms `K` by orthogonal similarity.
"""
function covariant_contraction(tensor::AbstractArray{T,3}) where {T<:AbstractFloat}
    left_dimension, first_dimension, second_dimension = size(tensor)
    left_dimension == first_dimension == second_dimension ||
        throw(DimensionMismatch("square projected Hessian tensor required"))
    all(isfinite, tensor) || throw(ArgumentError("nonfinite projected tensor"))
    contraction = zeros(T, first_dimension, first_dimension)
    for first in 1:first_dimension, second in first:first_dimension
        value = zero(T)
        for left in 1:left_dimension, contracted in 1:second_dimension
            value += tensor[left, first, contracted] *
                     tensor[left, second, contracted]
        end
        contraction[first, second] = value
        contraction[second, first] = value
    end
    all(isfinite, contraction) || throw(ArgumentError("nonfinite covariant contraction"))
    return contraction
end

function _sorted_eigenpairs(matrix::AbstractMatrix{T}) where {T<:AbstractFloat}
    decomposition = eigen(Symmetric(Matrix{T}(matrix)))
    order = sortperm(decomposition.values; rev=true)
    return (
        values=T[decomposition.values[index] for index in order],
        vectors=Matrix{T}(decomposition.vectors[:, order]),
    )
end

function _line_spectral_gap(values::AbstractVector{T}, index::Int) where {T}
    length(values) == 1 && return T(Inf)
    return minimum(abs(values[index] - values[other]) for other in eachindex(values) if other != index)
end

struct CovariantLineCertificate{T<:AbstractFloat}
    status::Symbol
    reason::String
    contraction::Matrix{T}
    eigenvalues::Vector{T}
    lower::Vector{T}
    upper::Vector{T}
    eta::T
    local_directions::Matrix{T}
    local_projectors::Vector{Matrix{T}}
    ambient_projectors::Vector{Matrix{T}}
    radius_projector_distances::Vector{T}
    projector_bounds::Vector{T}
end

function _line_certificate(
    status,
    reason,
    contraction,
    values,
    lower,
    upper,
    eta,
    directions,
    local_projectors,
    ambient_projectors,
    distances,
    bounds,
)
    T = eltype(contraction)
    return CovariantLineCertificate{T}(
        status,
        String(reason),
        Matrix{T}(contraction),
        T[values...],
        T[lower...],
        T[upper...],
        T(eta),
        Matrix{T}(directions),
        Matrix{T}[Matrix{T}(projector) for projector in local_projectors],
        Matrix{T}[Matrix{T}(projector) for projector in ambient_projectors],
        T[distances...],
        T[bounds...],
    )
end

"""
Certify every eigenline of the paired-radius covariant contraction.  Every
eigenvalue must be positive beyond uncertainty and every eigenvalue interval
must be simple.  Degeneracy returns `:unknown`; it is never resolved by an SVD
basis or a coordinate tie-break.

Both tensors must use the same fine-radius left/right null bases.  The supplied
right basis lifts local eigenlines to ambient normalized-coordinate projectors.
"""
function certify_covariant_lines(
    coarse_tensor::AbstractArray{T,3},
    fine_tensor::AbstractArray{T,3},
    right_null_basis::AbstractMatrix{T};
    arithmetic_floor::T=zero(T),
    options::InvariantDiagnosticOptions{T}=InvariantDiagnosticOptions{T}(),
) where {T<:AbstractFloat}
    _validate_options(options)
    size(coarse_tensor) == size(fine_tensor) ||
        throw(DimensionMismatch("projected Hessian tensor pair"))
    left_dimension, first_dimension, second_dimension = size(fine_tensor)
    left_dimension == first_dimension == second_dimension ||
        throw(DimensionMismatch("square projected Hessian tensor pair"))
    size(right_null_basis, 2) == first_dimension ||
        throw(DimensionMismatch("right null basis"))
    all(isfinite, coarse_tensor) && all(isfinite, fine_tensor) ||
        throw(ArgumentError("nonfinite projected Hessian tensor pair"))
    isfinite(arithmetic_floor) && arithmetic_floor >= 0 ||
        throw(ArgumentError("invalid contraction arithmetic floor"))
    gram_error = opnorm(
        transpose(right_null_basis) * right_null_basis -
        Matrix{T}(I, first_dimension, first_dimension),
        2,
    )
    gram_error <= T(128) * eps(T) * max(one(T), T(size(right_null_basis, 1))) ||
        throw(ArgumentError("right null basis is not orthonormal"))

    coarse = covariant_contraction(coarse_tensor)
    fine = covariant_contraction(fine_tensor)
    coarse_pairs = _sorted_eigenpairs(coarse)
    fine_pairs = _sorted_eigenpairs(fine)
    eta = max(
        options.uncertainty_multiplier * T(opnorm(fine - coarse, 2)),
        arithmetic_floor,
        options.roundoff_multiplier * eps(T) * max(one(T), T(opnorm(fine, 2))),
    )
    lower = max.(zero(T), fine_pairs.values .- eta)
    upper = fine_pairs.values .+ eta
    local_projectors = Matrix{T}[]
    ambient_projectors = Matrix{T}[]
    distances = T[]
    bounds = T[]
    for index in 1:first_dimension
        direction = view(fine_pairs.vectors, :, index)
        local_projector = direction * transpose(direction)
        coarse_direction = view(coarse_pairs.vectors, :, index)
        coarse_projector = coarse_direction * transpose(coarse_direction)
        distance = T(opnorm(local_projector - coarse_projector, 2))
        gap = min(
            _line_spectral_gap(fine_pairs.values, index),
            _line_spectral_gap(coarse_pairs.values, index),
        )
        uncertainty_bound = isfinite(gap) && gap > 0 ?
                            options.projector_uncertainty_multiplier * eta / gap :
                            zero(T)
        bound = min(
            options.projector_distance_max,
            max(T(32) * eps(T), uncertainty_bound),
        )
        push!(local_projectors, Matrix{T}(local_projector))
        push!(ambient_projectors, Matrix{T}(
            right_null_basis * local_projector * transpose(right_null_basis),
        ))
        push!(distances, distance)
        push!(bounds, bound)
    end

    common = (
        fine,
        fine_pairs.values,
        lower,
        upper,
        eta,
        fine_pairs.vectors,
        local_projectors,
        ambient_projectors,
        distances,
        bounds,
    )
    all(value -> value > options.retained_uncertainty_multiplier_min * eta, lower) ||
        return _line_certificate(
            :unknown,
            "covariant contraction reaches zero within uncertainty",
            common...,
        )
    for index in 1:(first_dimension - 1)
        lower[index] > upper[index + 1] || return _line_certificate(
            :unknown,
            "covariant contraction has an uncertainty-degenerate eigenline",
            common...,
        )
    end
    all(index -> distances[index] <= bounds[index], eachindex(distances)) ||
        return _line_certificate(
            :unknown,
            "covariant eigenline changes beyond paired-radius uncertainty",
            common...,
        )
    return _line_certificate(:certified, "all covariant eigenlines are simple", common...)
end

"""Contract the projected Hessian tensor with a unit right-null direction."""
function contracted_operator(
    tensor::AbstractArray{T,3},
    direction::AbstractVector{T},
) where {T<:AbstractFloat}
    left_dimension, first_dimension, second_dimension = size(tensor)
    left_dimension == first_dimension == second_dimension ||
        throw(DimensionMismatch("square projected Hessian tensor required"))
    length(direction) == first_dimension || throw(DimensionMismatch("null direction"))
    magnitude = norm(direction, 2)
    isfinite(magnitude) && magnitude > 0 || throw(ArgumentError("nonzero finite direction required"))
    unit_direction = direction ./ magnitude
    operator = zeros(T, left_dimension, second_dimension)
    for left in 1:left_dimension, column in 1:second_dimension
        operator[left, column] = sum(
            tensor[left, index, column] * unit_direction[index] for
            index in 1:first_dimension
        )
    end
    all(isfinite, operator) || throw(ArgumentError("nonfinite contracted operator"))
    return operator
end

struct ContractedOperatorCertificate{T<:AbstractFloat}
    line_index::Int
    passed::Bool
    reason::String
    singular_values::Vector{T}
    lower::Vector{T}
    upper::Vector{T}
    eta::T
    condition_upper::T
end

struct ContractedLineEvidence{T<:AbstractFloat}
    passed::Bool
    reason::String
    certificates::Vector{ContractedOperatorCertificate{T}}
    valid_indices::Vector{Int}
end

"""
Apply paired-radius Weyl full-rank gates to `B(v)` for every robust covariant
eigenline.  A line whose `B(v)` fails remains in the trace but is not a valid
trial line.  No valid line returns a typed failure for the candidate route.
"""
function certify_contracted_lines(
    coarse_tensor::AbstractArray{T,3},
    fine_tensor::AbstractArray{T,3},
    lines::CovariantLineCertificate{T};
    arithmetic_floor::T=zero(T),
    options::InvariantDiagnosticOptions{T}=InvariantDiagnosticOptions{T}(),
) where {T<:AbstractFloat}
    _validate_options(options)
    lines.status == :certified || return ContractedLineEvidence{T}(
        false,
        "covariant eigenlines unavailable",
        ContractedOperatorCertificate{T}[],
        Int[],
    )
    size(coarse_tensor) == size(fine_tensor) || throw(DimensionMismatch("tensor pair"))
    isfinite(arithmetic_floor) && arithmetic_floor >= 0 ||
        throw(ArgumentError("invalid contracted arithmetic floor"))
    certificates = ContractedOperatorCertificate{T}[]
    valid_indices = Int[]
    for line_index in axes(lines.local_directions, 2)
        direction = view(lines.local_directions, :, line_index)
        coarse = contracted_operator(coarse_tensor, direction)
        fine = contracted_operator(fine_tensor, direction)
        values = T[svdvals(fine)...]
        eta = max(
            options.uncertainty_multiplier * T(opnorm(fine - coarse, 2)),
            arithmetic_floor,
            options.roundoff_multiplier * eps(T) * max(one(T), values[1]),
        )
        lower = max.(zero(T), values .- eta)
        upper = values .+ eta
        full_rank = lower[end] > options.retained_uncertainty_multiplier_min * eta
        condition_upper = full_rank ? upper[1] / lower[end] : T(Inf)
        passed = full_rank && isfinite(condition_upper) &&
                 condition_upper <= options.contracted_condition_max
        reason = !full_rank ? "B(v) row-rank interval reaches uncertainty" :
                 !isfinite(condition_upper) ||
                 condition_upper > options.contracted_condition_max ?
                 "B(v) condition upper bound exceeded" :
                 "B(v) paired-radius interval is full rank"
        push!(certificates, ContractedOperatorCertificate(
            line_index,
            passed,
            reason,
            values,
            lower,
            upper,
            eta,
            condition_upper,
        ))
        passed && push!(valid_indices, line_index)
    end
    passed = !isempty(valid_indices)
    return ContractedLineEvidence(
        passed,
        passed ? "at least one covariant line has robust B(v)" :
                 "no covariant line has robust B(v)",
        certificates,
        valid_indices,
    )
end

function _interval_vectors_overlap(first_lower, first_upper, second_lower, second_upper)
    length(first_lower) == length(second_lower) || return false
    return all(
        max(first_lower[index], second_lower[index]) <=
        min(first_upper[index], second_upper[index]) for index in eachindex(first_lower)
    )
end

struct CrossPrecisionLineEvidence{T<:AbstractFloat}
    passed::Bool
    reason::String
    distances::Vector{T}
    bounds::Vector{T}
end

struct CrossPrecisionContractionEvidence
    passed::Bool
    reason::String
end

"""Cross-precision gate for ordered simple ambient eigenlines."""
function cross_precision_lines(
    first::CovariantLineCertificate{T},
    second::CovariantLineCertificate{T};
    options::InvariantDiagnosticOptions{T}=InvariantDiagnosticOptions{T}(),
) where {T<:AbstractFloat}
    _validate_options(options)
    first.status == :certified && second.status == :certified ||
        return CrossPrecisionLineEvidence(false, "line certificate unavailable", T[], T[])
    length(first.eigenvalues) == length(second.eigenvalues) ||
        return CrossPrecisionLineEvidence(false, "line count disagreement", T[], T[])
    distances = T[]
    bounds = T[]
    for index in eachindex(first.eigenvalues)
        _interval_vectors_overlap(
            first.lower[index:index],
            first.upper[index:index],
            second.lower[index:index],
            second.upper[index:index],
        ) || return CrossPrecisionLineEvidence(
            false,
            "covariant eigenvalue intervals disagree across precision",
            distances,
            bounds,
        )
        distance = T(opnorm(
            first.ambient_projectors[index] - second.ambient_projectors[index],
            2,
        ))
        gap = min(
            _line_spectral_gap(first.eigenvalues, index),
            _line_spectral_gap(second.eigenvalues, index),
        )
        uncertainty_bound = isfinite(gap) && gap > 0 ?
                            options.projector_uncertainty_multiplier *
                            (first.eta + second.eta) / gap : zero(T)
        bound = min(
            options.projector_distance_max,
            max(T(32) * eps(T), uncertainty_bound),
        )
        push!(distances, distance)
        push!(bounds, bound)
        distance <= bound || return CrossPrecisionLineEvidence(
            false,
            "ambient eigenline projector disagrees across precision",
            distances,
            bounds,
        )
    end
    return CrossPrecisionLineEvidence(
        true,
        "covariant lines agree across precision",
        distances,
        bounds,
    )
end

"""Cross-precision interval and decision gate for every contracted line."""
function cross_precision_contractions(
    first::ContractedLineEvidence{T},
    second::ContractedLineEvidence{T},
) where {T<:AbstractFloat}
    first.passed && second.passed ||
        return CrossPrecisionContractionEvidence(
            false,
            "contracted line evidence unavailable",
        )
    length(first.certificates) == length(second.certificates) ||
        return CrossPrecisionContractionEvidence(false, "contracted line count disagreement")
    first.valid_indices == second.valid_indices ||
        return CrossPrecisionContractionEvidence(false, "B(v) validity changes across precision")
    for index in eachindex(first.certificates)
        first_certificate = first.certificates[index]
        second_certificate = second.certificates[index]
        first_certificate.passed == second_certificate.passed ||
            return CrossPrecisionContractionEvidence(
                false,
                "B(v) decision changes across precision",
            )
        first_certificate.passed || continue
        _interval_vectors_overlap(
            first_certificate.lower,
            first_certificate.upper,
            second_certificate.lower,
            second_certificate.upper,
        ) || return CrossPrecisionContractionEvidence(
            false,
            "B(v) intervals disagree across precision",
        )
    end
    return CrossPrecisionContractionEvidence(
        true,
        "all B(v) decisions and intervals agree across precision",
    )
end

struct NullTrial{T<:AbstractFloat}
    line_index::Int
    sign::Int
    direction::Vector{T}
    contracted::Matrix{T}
    right_hand_side::Vector{T}
    correction::Vector{T}
end

"""
Construct the finite paper-style null corrections for both signs of every
paired-radius/precision-valid covariant line:

`B(v) * delta = -U2' * J(x_range) * v`.

`projected_jacobian` is `U2' * J(x_range) * V2` in the same local bases as the
fine tensor.  Successful cross-precision line and `B(v)` gate records are
mandatory.  The factorization hook runs before each solve.
"""
function paper_two_step_null_trials(
    fine_tensor::AbstractArray{T,3},
    lines::CovariantLineCertificate{T},
    contractions::ContractedLineEvidence{T},
    projected_jacobian::AbstractMatrix{T};
    line_precision_gate::CrossPrecisionLineEvidence{T},
    contraction_precision_gate::CrossPrecisionContractionEvidence,
    charge_factorization=() -> nothing,
) where {T<:AbstractFloat}
    lines.status == :certified || throw(ArgumentError("covariant lines unavailable"))
    contractions.passed || throw(ArgumentError("no valid contracted line"))
    line_precision_gate.passed ||
        throw(ArgumentError("cross-precision line gate required"))
    contraction_precision_gate.passed ||
        throw(ArgumentError("cross-precision B(v) gate required"))
    dimension = size(fine_tensor, 2)
    size(projected_jacobian) == (dimension, dimension) ||
        throw(DimensionMismatch("projected Jacobian"))
    all(isfinite, projected_jacobian) ||
        throw(ArgumentError("nonfinite projected Jacobian"))
    trials = NullTrial{T}[]
    for line_index in contractions.valid_indices
        base_direction = view(lines.local_directions, :, line_index)
        for sign in (-1, 1)
            direction = T(sign) .* base_direction
            contracted = contracted_operator(fine_tensor, direction)
            right_hand_side = -(projected_jacobian * direction)
            charge_factorization()
            correction = contracted \ right_hand_side
            all(isfinite, correction) || throw(ArgumentError("nonfinite null correction"))
            push!(trials, NullTrial(
                line_index,
                sign,
                collect(direction),
                contracted,
                collect(right_hand_side),
                collect(correction),
            ))
        end
    end
    length(trials) == 2 * length(contractions.valid_indices) ||
        throw(AssertionError("both signs were not evaluated"))
    return trials
end

struct EndpointReconciliation{T<:AbstractFloat}
    passed::Bool
    reason::String
    barycenter::Vector{T}
    maximum_pairwise_distance::T
    tolerance::T
    endpoint_count::Int
end

"""
Reconcile normalized canonical trial endpoints without selecting a preferred
eigenline or sign.  Every pair must agree within one frozen Euclidean tolerance;
the covariant barycenter is returned only as the common safeguarded proposal.
The complete `NullTrial` and contracted-line evidence are required, preventing
a caller from dropping one sign or a disagreeing robust line before
reconciliation.
"""
function reconcile_signed_endpoints(
    endpoints::AbstractVector{<:AbstractVector{T}},
    trials::AbstractVector{<:NullTrial{T}},
    contractions::ContractedLineEvidence{T};
    options::InvariantDiagnosticOptions{T}=InvariantDiagnosticOptions{T}(),
) where {T<:AbstractFloat}
    _validate_options(options)
    length(endpoints) == length(trials) ||
        throw(DimensionMismatch("one endpoint per signed line trial required"))
    length(trials) >= 2 && iseven(length(trials)) ||
        throw(ArgumentError("both signs of at least one line are required"))
    line_indices = sort(unique(trial.line_index for trial in trials))
    line_indices == sort(contractions.valid_indices) || throw(
        ArgumentError("every robust contracted line must be reconciled"),
    )
    for line_index in line_indices
        signs = sort([trial.sign for trial in trials if trial.line_index == line_index])
        signs == [-1, 1] || throw(
            ArgumentError("exactly both signs of every robust line are required"),
        )
    end
    dimension = length(first(endpoints))
    dimension > 0 || throw(ArgumentError("empty endpoint"))
    all(endpoint -> length(endpoint) == dimension, endpoints) ||
        throw(DimensionMismatch("trial endpoints"))
    all(endpoint -> all(isfinite, endpoint), endpoints) ||
        throw(ArgumentError("nonfinite trial endpoint"))
    barycenter = zeros(T, dimension)
    for endpoint in endpoints
        barycenter .+= endpoint
    end
    barycenter ./= T(length(endpoints))
    maximum_distance = maximum(
        norm(endpoints[first_index] - endpoints[second_index], 2) for
        first_index in 1:(length(endpoints) - 1) for
        second_index in (first_index + 1):length(endpoints)
    )
    tolerance = options.line_reconciliation_tolerance
    passed = isfinite(maximum_distance) && maximum_distance <= tolerance
    return EndpointReconciliation(
        passed,
        passed ? "all line/sign endpoints agree" :
                 "line/sign endpoints disagree beyond frozen tolerance",
        barycenter,
        maximum_distance,
        tolerance,
        length(endpoints),
    )
end
