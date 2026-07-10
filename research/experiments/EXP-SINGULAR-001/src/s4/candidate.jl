# Frozen finite-difference candidate. Numerical helpers in this file are not shared
# with the analytic control.

const _S4C_BITS = (128, 256)
const _S4C_RADII = (1.0, 0.5)
const _S4C_GAP_MAX = 1.0e-6
const _S4C_MAX_NULLITY = 4
const _S4C_ANGLE_MAX = 1.0e-6
const _S4C_PROJECTED_CONDITION_MAX = 1.0e12
const _S4C_ORDER_MIN = 1 // 16
const _S4C_ORDER_MAX = 16
const _S4C_AUDIT_ITERATION = 65
const _S4C_COUNTER_NAMESPACE = UInt64(0x53342d43322d5631)

_s4c_fail(reason::AbstractString) = throw(_S4CandidateReject(String(reason)))

function _s4c_frozen_options(options::ExperimentOptions)
    return options.precision_ladder == (128, 256) &&
           options.semantic_precision_bits == 256 &&
           options.maximum_iterations == 64 &&
           options.maximum_callbacks == 4096 &&
           options.wall_seconds == 10.0 &&
           options.finite_difference_exponent == 1 / 3 &&
           options.rank_roundoff_multiplier == 32.0 &&
           options.independent_confirmation_count == 2 &&
           options.confirmation_perturbation_radius == 1.0e-6 &&
           options.error_reserve_multiplier == 16.0 &&
           options.target_error_goal == 1.0e-12 &&
           options.configuration_error_goal == 1.0e-10 &&
           options.semantic_residual_tolerance == 1.0e-12
end

function _s4c_residual!(ledger, oracle, x::AbstractVector{T}, bits::Int) where {T}
    values = T.(_evaluate_residual!(ledger, oracle, x, bits))
    _check_deadline!(ledger)
    all(isfinite, values) || _s4c_fail("nonfinite residual")
    return values
end

function _s4c_target!(ledger, oracle, x::AbstractVector{T}, bits::Int) where {T}
    value = T(_evaluate_target!(ledger, oracle, x, bits))
    _check_deadline!(ledger)
    isfinite(value) || _s4c_fail("nonfinite target")
    return value
end

function _s4c_jacobian!(
    ledger,
    oracle,
    x::AbstractVector{T},
    bits::Int,
    radius_multiplier::Real,
) where {T<:AbstractFloat}
    n = oracle.dimension
    jacobian = zeros(T, oracle.residual_dimension, n)
    scale = eps(T)^(one(T) / T(3))
    multiplier = T(radius_multiplier)
    isfinite(multiplier) && multiplier > 0 || _s4c_fail("invalid Jacobian radius")
    for column in 1:n
        step = multiplier * scale * max(one(T), abs(x[column]))
        isfinite(step) && step > 0 || _s4c_fail("invalid Jacobian step")
        plus = copy(x)
        minus = copy(x)
        plus[column] += step
        minus[column] -= step
        jacobian[:, column] .= (
            _s4c_residual!(ledger, oracle, plus, bits) .-
            _s4c_residual!(ledger, oracle, minus, bits)
        ) ./ (T(2) * step)
    end
    _check_deadline!(ledger)
    all(isfinite, jacobian) || _s4c_fail("nonfinite finite-difference Jacobian")
    return jacobian
end

function _s4c_split!(
    ledger,
    jacobian::AbstractMatrix{T};
    fixed_nullity=nothing,
    require_route_selection::Bool=false,
) where {T}
    n = size(jacobian, 2)
    size(jacobian) == (n, n) || _s4c_fail("S4 candidate requires a square Jacobian")
    _charge_factorization!(ledger)
    decomposition = svd(Matrix{T}(jacobian); full=true)
    _check_deadline!(ledger)
    singular_values = T[decomposition.S...]
    length(singular_values) == n && all(isfinite, singular_values) ||
        _s4c_fail("invalid Jacobian singular values")
    sigma1 = singular_values[1]
    tau = T(32) * T(n) * eps(T) * max(one(T), sigma1)
    selected_by_gap = nothing
    if fixed_nullity === nothing || require_route_selection
        selected = nothing
        for index in 1:(n - 1)
            boundary = singular_values[index]
            ratio = iszero(boundary) ? T(Inf) : singular_values[index + 1] / boundary
            if ratio <= T(_S4C_GAP_MAX) && boundary > tau
                selected = index
                break
            end
        end
        selected === nothing && _s4c_fail("no qualifying smallest singular-value gap")
        selected_by_gap = selected::Int
    end
    retained = if fixed_nullity === nothing
        selected_by_gap::Int
    else
        nullity = Int(fixed_nullity)
        1 <= nullity < n || _s4c_fail("invalid frozen nullity")
        frozen_retained = n - nullity
        if require_route_selection && selected_by_gap != frozen_retained
            _s4c_fail("frozen nullity disagrees with route selection")
        end
        frozen_retained
    end
    nullity = n - retained
    nullity <= _S4C_MAX_NULLITY || _s4c_fail("nullity exceeds frozen maximum")
    singular_values[retained] > tau || _s4c_fail("retained singular value below cutoff")
    condition = iszero(singular_values[retained]) ? T(Inf) :
                sigma1 / singular_values[retained]
    isfinite(condition) || _s4c_fail("nonfinite retained condition")
    return (
        U1=Matrix{T}(decomposition.U[:, 1:retained]),
        U2=Matrix{T}(decomposition.U[:, (retained + 1):n]),
        V1=Matrix{T}(decomposition.V[:, 1:retained]),
        V2=Matrix{T}(decomposition.V[:, (retained + 1):n]),
        retained_singular_values=T[singular_values[1:retained]...],
        singular_values=singular_values,
        retained=retained,
        nullity=nullity,
        tau=tau,
        condition=condition,
    )
end

function _s4c_angle_sine!(ledger, reference::AbstractMatrix{T}, basis::AbstractMatrix{T}) where {T}
    size(reference) == size(basis) || _s4c_fail("nullspace dimension drift")
    _charge_factorization!(ledger)
    overlap = svd(Matrix{T}(transpose(reference) * basis); full=false).S
    _check_deadline!(ledger)
    isempty(overlap) && _s4c_fail("empty nullspace overlap")
    minimum_overlap = clamp(minimum(overlap), zero(T), one(T))
    sine = sqrt(max(zero(T), one(T) - minimum_overlap^2))
    isfinite(sine) || _s4c_fail("nonfinite principal angle")
    return sine
end

function _s4c_coefficients(::Type{T}, nullity::Int, iteration::Int) where {T}
    1 <= nullity <= _S4C_MAX_NULLITY || _s4c_fail("invalid coefficient nullity")
    iteration >= 1 || _s4c_fail("invalid coefficient iteration")
    integers = Vector{Int64}(undef, nullity)
    for coordinate in 1:nullity
        z = _S4C_COUNTER_NAMESPACE ⊻ (UInt64(nullity) << 48) ⊻
            (UInt64(iteration) << 16) ⊻ UInt64(coordinate)
        z += UInt64(0x9e3779b97f4a7c15)
        z = (z ⊻ (z >> 30)) * UInt64(0xbf58476d1ce4e5b9)
        z = (z ⊻ (z >> 27)) * UInt64(0x94d049bb133111eb)
        value = z ⊻ (z >> 31)
        magnitude = Int64(1 + Int(value & UInt64(0x7fffffff)))
        integers[coordinate] = iszero(value >> 63) ? magnitude : -magnitude
    end
    coefficients = T.(integers)
    scale = norm(coefficients, 2)
    isfinite(scale) && scale > 0 || _s4c_fail("invalid coefficient norm")
    return coefficients ./ scale
end

function _s4c_projected_operator!(
    ledger,
    oracle,
    x_range::AbstractVector{T},
    left_null::AbstractMatrix{T},
    right_null::AbstractMatrix{T},
    direction::AbstractVector{T},
    bits::Int,
    mixed_multiplier::Real,
) where {T<:AbstractFloat}
    nullity = size(right_null, 2)
    rho = T(mixed_multiplier) * eps(T)^(one(T) / T(4)) *
          max(one(T), norm(x_range, Inf))
    denominator = max(norm(direction, Inf), sqrt(eps(T)))
    h = rho / denominator
    isfinite(h) && h > 0 || _s4c_fail("invalid mixed-direction first step")
    operator = zeros(T, nullity, nullity)
    for column in 1:nullity
        basis_direction = view(right_null, :, column)
        kappa = rho / max(norm(basis_direction, Inf), sqrt(eps(T)))
        isfinite(kappa) && kappa > 0 || _s4c_fail("invalid mixed-direction second step")
        pp = x_range .+ h .* direction .+ kappa .* basis_direction
        pm = x_range .+ h .* direction .- kappa .* basis_direction
        mp = x_range .- h .* direction .+ kappa .* basis_direction
        mm = x_range .- h .* direction .- kappa .* basis_direction
        directional = (
            _s4c_residual!(ledger, oracle, pp, bits) .-
            _s4c_residual!(ledger, oracle, pm, bits) .-
            _s4c_residual!(ledger, oracle, mp, bits) .+
            _s4c_residual!(ledger, oracle, mm, bits)
        ) ./ (T(4) * h * kappa)
        operator[:, column] .= transpose(left_null) * directional
    end
    _check_deadline!(ledger)
    all(isfinite, operator) || _s4c_fail("nonfinite projected operator")
    return operator
end

function _s4c_projected_factor!(ledger, operator::AbstractMatrix{T}) where {T}
    nullity = size(operator, 1)
    size(operator) == (nullity, nullity) || _s4c_fail("projected operator is not square")
    _charge_factorization!(ledger)
    decomposition = svd(Matrix{T}(operator); full=true)
    _check_deadline!(ledger)
    spectrum = T[decomposition.S...]
    length(spectrum) == nullity && all(isfinite, spectrum) ||
        _s4c_fail("invalid projected spectrum")
    largest = spectrum[1]
    tau = T(32) * T(nullity) * sqrt(eps(T)) * max(one(T), largest)
    all(value -> value > tau, spectrum) || _s4c_fail("projected operator rank loss")
    condition = iszero(spectrum[end]) ? T(Inf) : largest / spectrum[end]
    isfinite(condition) && condition <= T(_S4C_PROJECTED_CONDITION_MAX) ||
        _s4c_fail("projected operator condition gate failed")
    return (factor=decomposition, spectrum=spectrum, tau=tau, condition=condition)
end

function _s4c_local_probe(
    ledger,
    split,
    reference,
    nullity::Int,
    iteration::Int,
)
    T = eltype(split.V2)
    if reference === nothing
        coefficients = _s4c_coefficients(T, nullity, iteration)
        direction = split.V2 * coefficients
        return (
            coefficients=coefficients,
            local_coordinates=copy(coefficients),
            local_coordinate_norm=norm(coefficients, 2),
            direction=direction,
            iteration=iteration,
            projection_loss=zero(T),
            angle_sine=zero(T),
            subspace_decision=true,
            transported=false,
        )
    end
    reference_basis = T.(reference.basis)
    reference_direction = T.(reference.direction)
    angle_sine = _s4c_angle_sine!(ledger, reference_basis, split.V2)
    angle_sine <= T(_S4C_ANGLE_MAX) || _s4c_fail("transported subspace angle gate failed")
    local_coordinates = transpose(split.V2) * reference_direction
    local_norm = norm(local_coordinates, 2)
    isfinite(local_norm) && local_norm > 0 || _s4c_fail("zero transported projection")
    projection = split.V2 * local_coordinates
    projection_loss = norm(reference_direction - projection, 2)
    isfinite(projection_loss) || _s4c_fail("nonfinite transported projection loss")
    normalized_coordinates = local_coordinates ./ local_norm
    direction = split.V2 * normalized_coordinates
    return (
        coefficients=normalized_coordinates,
        local_coordinates=local_coordinates,
        local_coordinate_norm=local_norm,
        direction=direction,
        iteration=iteration,
        projection_loss=projection_loss,
        angle_sine=angle_sine,
        subspace_decision=true,
        transported=true,
    )
end

function _s4c_probe_document(bits, radius, split, projected, probe)
    boundary_ratio = split.singular_values[split.retained + 1] /
                     split.singular_values[split.retained]
    return Dict{String,Any}(
        "angle_sine" => probe.angle_sine,
        "c_local" => collect(probe.local_coordinates),
        "c_local_norm" => probe.local_coordinate_norm,
        "coefficients" => collect(probe.coefficients),
        "condition" => split.condition,
        "direction" => collect(probe.direction),
        "gap_ratio" => boundary_ratio,
        "jacobian_radius_multiplier" => radius,
        "left_null_basis" => Any[
            collect(column) for column in eachcol(split.U2)
        ],
        "ell" => probe.iteration,
        "nullity" => split.nullity,
        "precision_bits" => bits,
        "projected_condition" => projected.condition,
        "projected_spectrum" => collect(projected.spectrum),
        "projected_tau" => projected.tau,
        "projection_loss" => probe.projection_loss,
        "rank" => split.retained,
        "right_null_basis" => Any[
            collect(column) for column in eachcol(split.V2)
        ],
        "singular_values" => collect(split.singular_values),
        "tau_rank" => split.tau,
        "subspace_angle_bound" => _S4C_ANGLE_MAX,
        "subspace_decision" => probe.subspace_decision,
        "transported" => probe.transported,
    )
end

function _s4c_initial_route!(ledger, input::S4CandidateInput, options::ExperimentOptions)
    oracle = input.oracle
    probes = Dict{Tuple{Int,Float64},Any}()
    documents = Any[]
    selected_nullity = nothing
    route_goal = BigFloat(options.semantic_residual_tolerance) /
                 (BigFloat(4) * BigFloat(options.error_reserve_multiplier))
    for bits in _S4C_BITS
        for radius in _S4C_RADII
            probe = setprecision(BigFloat, bits) do
                x = BigFloat.(input.endpoint)
                residual = _s4c_residual!(ledger, oracle, x, bits)
                norm(residual, Inf) <= BigFloat(route_goal) ||
                    _s4c_fail("primary route residual above frozen goal")
                jacobian = _s4c_jacobian!(ledger, oracle, x, bits, radius)
                split = _s4c_split!(ledger, jacobian)
                if selected_nullity === nothing
                    selected_nullity = split.nullity
                elseif split.nullity != selected_nullity
                    _s4c_fail("route nullity disagreement")
                end
                range_coordinates = transpose(split.U1) * residual
                range_step = split.V1 * (range_coordinates ./ split.retained_singular_values)
                x_range = x - range_step
                local_probe = _s4c_local_probe(
                    ledger,
                    split,
                    nothing,
                    split.nullity,
                    1,
                )
                operator = _s4c_projected_operator!(
                    ledger,
                    oracle,
                    x_range,
                    split.U2,
                    split.V2,
                    local_probe.direction,
                    bits,
                    radius,
                )
                projected = _s4c_projected_factor!(ledger, operator)
                document = _s4c_probe_document(
                    bits,
                    radius,
                    split,
                    projected,
                    local_probe,
                )
                document["residual_linf"] = norm(residual, Inf)
                (
                    split=split,
                    projected=projected,
                    probe=local_probe,
                    residual_linf=BigFloat(norm(residual, Inf)),
                    document=document,
                )
            end
            probes[(bits, radius)] = probe
            push!(documents, probe.document)
        end
    end
    nullity = selected_nullity::Int
    reference = probes[(256, 0.5)].split
    max_left = BigFloat(0)
    max_right = BigFloat(0)
    angle_documents = Any[]
    for bits in _S4C_BITS
        for radius in _S4C_RADII
            bits == 256 && radius == 0.5 && continue
            current = probes[(bits, radius)].split
            left, right = setprecision(BigFloat, bits) do
                left_reference = BigFloat.(reference.U2)
                right_reference = BigFloat.(reference.V2)
                (
                    _s4c_angle_sine!(ledger, left_reference, BigFloat.(current.U2)),
                    _s4c_angle_sine!(ledger, right_reference, BigFloat.(current.V2)),
                )
            end
            max_left = max(max_left, BigFloat(left))
            max_right = max(max_right, BigFloat(right))
            push!(angle_documents, Dict{String,Any}(
                "left_sine" => left,
                "precision_bits" => bits,
                "radius_multiplier" => radius,
                "right_sine" => right,
            ))
        end
    end
    max_left <= BigFloat(_S4C_ANGLE_MAX) || _s4c_fail("left-nullspace route angle failed")
    max_right <= BigFloat(_S4C_ANGLE_MAX) ||
        _s4c_fail("right-nullspace route angle failed")
    return (
        nullity=nullity,
        retained=oracle.dimension - nullity,
        condition=maximum(BigFloat(probe.split.condition) for probe in values(probes)),
        signatures=Tuple((
            precision_bits=bits,
            radius_multiplier=radius,
            rank=probes[(bits, radius)].split.retained,
            nullity=probes[(bits, radius)].split.nullity,
        ) for bits in _S4C_BITS for radius in _S4C_RADII),
        document=Dict{String,Any}(
            "angle_bound" => _S4C_ANGLE_MAX,
            "angles" => angle_documents,
            "maximum_left_angle_sine" => max_left,
            "maximum_right_angle_sine" => max_right,
            "nullity" => nullity,
            "probes" => documents,
            "residual_goal" => route_goal,
            "selected_rank" => oracle.dimension - nullity,
        ),
    )
end

function _s4c_step!(
    ledger,
    input::S4CandidateInput,
    x::AbstractVector{T},
    bits::Int,
    nullity::Int,
    iteration::Int;
    jacobian_radius::Real=1.0,
    mixed_multiplier::Real=1.0,
    reference=nothing,
    compute_correction::Bool=true,
    require_route_selection::Bool=false,
) where {T<:AbstractFloat}
    oracle = input.oracle
    jacobian = _s4c_jacobian!(ledger, oracle, x, bits, jacobian_radius)
    split = _s4c_split!(
        ledger,
        jacobian;
        fixed_nullity=nullity,
        require_route_selection,
    )
    residual = _s4c_residual!(ledger, oracle, x, bits)
    range_coordinates = transpose(split.U1) * residual
    range_step = split.V1 * (range_coordinates ./ split.retained_singular_values)
    x_range = x - range_step
    probe = _s4c_local_probe(ledger, split, reference, nullity, iteration)
    operator = _s4c_projected_operator!(
        ledger,
        oracle,
        x_range,
        split.U2,
        split.V2,
        probe.direction,
        bits,
        mixed_multiplier,
    )
    projected = _s4c_projected_factor!(ledger, operator)
    correction = zeros(T, length(x))
    next = copy(x)
    if compute_correction
        range_jacobian = _s4c_jacobian!(
            ledger,
            oracle,
            x_range,
            bits,
            jacobian_radius,
        )
        right_hand_side = -(transpose(split.U2) * range_jacobian * probe.direction)
        delta = projected.factor \ right_hand_side
        _check_deadline!(ledger)
        all(isfinite, delta) || _s4c_fail("nonfinite projected solve")
        next = x_range + split.V2 * delta
        correction = next - x
        all(isfinite, next) && all(isfinite, correction) ||
            _s4c_fail("nonfinite complete two-step")
    end
    document = _s4c_probe_document(
        bits,
        jacobian_radius,
        split,
        projected,
        probe,
    )
    document["complete_correction"] = collect(correction)
    document["correction_computed"] = compute_correction
    document["jacobian_inf_norm"] = norm(jacobian, Inf)
    document["mixed_direction_multiplier"] = mixed_multiplier
    document["point"] = collect(x)
    document["residual_linf"] = norm(residual, Inf)
    document["x_range"] = collect(x_range)
    return (
        next=next,
        correction=correction,
        residual=residual,
        jacobian=jacobian,
        x_range=x_range,
        split=split,
        projected=projected,
        probe=probe,
        document=document,
    )
end

function _s4c_trajectory!(
    ledger,
    input::S4CandidateInput,
    start,
    bits::Int,
    nullity::Int,
    options::ExperimentOptions,
    identity::AbstractString,
)
    return setprecision(BigFloat, bits) do
        x = BigFloat.(start)
        frozen_start = copy(x)
        previous = copy(x)
        last_step = BigFloat(Inf)
        residual_linf = BigFloat(Inf)
        trace = Any[]
        converged = false
        local_iterations = 0
        for iteration in 1:options.maximum_iterations
            _charge_iteration!(ledger)
            local_iterations = iteration
            step = _s4c_step!(
                ledger,
                input,
                x,
                bits,
                nullity,
                iteration,
            )
            previous = copy(x)
            x = BigFloat.(step.next)
            residual = _s4c_residual!(ledger, input.oracle, x, bits)
            residual_linf = BigFloat(norm(residual, Inf))
            last_step = BigFloat(norm(x - previous, Inf))
            normalized_step = last_step / max(one(BigFloat), norm(x, Inf))
            push!(trace, Dict{String,Any}(
                "coefficients" => collect(step.probe.coefficients),
                "direction" => collect(step.probe.direction),
                "iteration" => iteration,
                "normalized_step" => normalized_step,
                "projected_condition" => step.projected.condition,
                "projected_spectrum" => collect(step.projected.spectrum),
                "residual_linf" => residual_linf,
                "singular_values" => collect(step.split.singular_values),
            ))
            residual_goal = BigFloat(options.semantic_residual_tolerance) /
                            (BigFloat(4) * BigFloat(options.error_reserve_multiplier))
            step_goal = BigFloat(options.configuration_error_goal) /
                        (BigFloat(4) * BigFloat(options.error_reserve_multiplier))
            if residual_linf <= residual_goal && normalized_step <= step_goal
                converged = true
                break
            end
        end
        converged || _s4c_fail("trajectory did not satisfy the frozen stop rule")
        target = _s4c_target!(ledger, input.oracle, x, bits)
        return (
            identity=String(identity),
            bits=bits,
            start=frozen_start,
            endpoint=x,
            previous=previous,
            target=BigFloat(target),
            residual_linf=residual_linf,
            last_step=last_step,
            iterations=local_iterations,
            trace=trace,
        )
    end
end

function _s4c_reference!(ledger, input, start, nullity::Int)
    return setprecision(BigFloat, 256) do
        x = BigFloat.(start)
        jacobian = _s4c_jacobian!(ledger, input.oracle, x, 256, 0.5)
        split = _s4c_split!(
            ledger,
            jacobian;
            fixed_nullity=nullity,
            require_route_selection=true,
        )
        coefficients = _s4c_coefficients(BigFloat, nullity, _S4C_AUDIT_ITERATION)
        direction = split.V2 * coefficients
        magnitude = norm(direction, 2)
        isfinite(magnitude) && magnitude > 0 || _s4c_fail("invalid physical reference")
        direction ./= magnitude
        return (
            basis=copy(split.V2),
            direction=copy(direction),
            coefficients=copy(coefficients),
            precision_bits=256,
            radius_multiplier=0.5,
        )
    end
end

function _s4c_order_and_null_decision(start_probe, final_probe, stage, bits, options)
    return setprecision(BigFloat, bits) do
        ratios = BigFloat.(final_probe.projected.spectrum) ./
                 BigFloat.(start_probe.projected.spectrum)
        order_passed = all(
            ratio -> isfinite(ratio) && ratio >= BigFloat(_S4C_ORDER_MIN) &&
                     ratio <= BigFloat(_S4C_ORDER_MAX),
            ratios,
        )
        normalized_discarded = maximum(BigFloat.(
            final_probe.split.singular_values[(final_probe.split.retained + 1):end],
        )) / max(one(BigFloat), BigFloat(final_probe.split.singular_values[1]))
        normalized_step = BigFloat(stage.last_step) /
                          max(one(BigFloat), norm(BigFloat.(stage.endpoint), Inf))
        null_bound = BigFloat(options.error_reserve_multiplier) *
                     (normalized_step^2 + eps(BigFloat)^(BigFloat(2) / BigFloat(3)))
        null_decay_passed = isfinite(normalized_discarded) &&
                            normalized_discarded <= null_bound
        return (
            ratios=ratios,
            order_passed=order_passed,
            normalized_discarded=normalized_discarded,
            normalized_step=normalized_step,
            null_bound=null_bound,
            null_decay_passed=null_decay_passed,
        )
    end
end

function _s4c_residual_decay_decision(start_probe, final_probe, stage, bits, options)
    return setprecision(BigFloat, bits) do
        start_residual = BigFloat(norm(start_probe.residual, Inf))
        final_residual = BigFloat(norm(final_probe.residual, Inf))
        start_scale = max(
            one(BigFloat),
            start_residual,
            BigFloat(norm(start_probe.jacobian, Inf)) *
            max(one(BigFloat), norm(BigFloat.(stage.start), Inf)),
        )
        residual_ratio = final_residual / start_scale
        normalized_step = BigFloat(stage.last_step) /
                          max(one(BigFloat), norm(BigFloat.(stage.endpoint), Inf))
        bound = BigFloat(options.error_reserve_multiplier) *
                (normalized_step^2 + eps(BigFloat)^(BigFloat(2) / BigFloat(3)))
        return (
            start_scale=start_scale,
            residual_ratio=residual_ratio,
            normalized_step=normalized_step,
            bound=bound,
            passed=isfinite(residual_ratio) && residual_ratio <= bound,
        )
    end
end

function _s4c_trajectory_audit!(
    ledger,
    input::S4CandidateInput,
    stage,
    nullity::Int,
    options::ExperimentOptions,
)
    reference = _s4c_reference!(ledger, input, stage.start, nullity)
    start_probes = Dict{Tuple{Int,Float64},Any}()
    final_probes = Dict{Tuple{Int,Float64},Any}()
    documents = Any[]
    all_passed = true
    for bits in _S4C_BITS
        for radius in _S4C_RADII
            start_probe, final_probe = setprecision(BigFloat, bits) do
                start_x = BigFloat.(stage.start)
                final_x = BigFloat.(stage.endpoint)
                start_value = _s4c_step!(
                    ledger,
                    input,
                    start_x,
                    bits,
                    nullity,
                    _S4C_AUDIT_ITERATION;
                    jacobian_radius=radius,
                    mixed_multiplier=radius,
                    reference=reference,
                    compute_correction=false,
                    require_route_selection=true,
                )
                final_value = _s4c_step!(
                    ledger,
                    input,
                    final_x,
                    bits,
                    nullity,
                    _S4C_AUDIT_ITERATION;
                    jacobian_radius=radius,
                    mixed_multiplier=radius,
                    reference=reference,
                    compute_correction=true,
                    require_route_selection=true,
                )
                (start_value, final_value)
            end
            start_probes[(bits, radius)] = start_probe
            final_probes[(bits, radius)] = final_probe
            decision = _s4c_order_and_null_decision(
                start_probe,
                final_probe,
                stage,
                bits,
                options,
            )
            all_passed &= decision.order_passed && decision.null_decay_passed
            push!(documents, Dict{String,Any}(
                "final" => final_probe.document,
                "null_decay" => Dict{String,Any}(
                    "bound" => decision.null_bound,
                    "decision" => decision.null_decay_passed,
                    "normalized_discarded_sigma" => decision.normalized_discarded,
                    "normalized_last_step" => decision.normalized_step,
                ),
                "order_persistence" => Dict{String,Any}(
                    "decision" => decision.order_passed,
                    "lower_bound" => _S4C_ORDER_MIN,
                    "ratios" => collect(decision.ratios),
                    "upper_bound" => _S4C_ORDER_MAX,
                ),
                "precision_bits" => bits,
                "radius_multiplier" => radius,
                "start" => start_probe.document,
            ))
        end
    end
    residual_documents = Any[]
    for bits in _S4C_BITS
        start_probe = start_probes[(bits, 1.0)]
        final_probe = final_probes[(bits, 1.0)]
        decision = _s4c_residual_decay_decision(
            start_probe,
            final_probe,
            stage,
            bits,
            options,
        )
        all_passed &= decision.passed
        push!(residual_documents, Dict{String,Any}(
            "F_scale" => decision.start_scale,
            "bound" => decision.bound,
            "decision" => decision.passed,
            "normalized_last_step" => decision.normalized_step,
            "precision_bits" => bits,
            "residual_ratio" => decision.residual_ratio,
        ))
    end
    all_passed || _s4c_fail("trajectory final applicability audit failed")
    return (
        reference=reference,
        start=start_probes,
        final=final_probes,
        document=Dict{String,Any}(
            "decision" => all_passed,
            "identity" => stage.identity,
            "physical_reference" => Dict{String,Any}(
                "basis" => [collect(column) for column in eachcol(reference.basis)],
                "coefficients" => collect(reference.coefficients),
                "direction" => collect(reference.direction),
                "ell" => _S4C_AUDIT_ITERATION,
                "precision_bits" => reference.precision_bits,
                "radius_multiplier" => reference.radius_multiplier,
            ),
            "probes" => documents,
            "residual_decay" => residual_documents,
        ),
    )
end

function _s4c_target_gradient!(
    ledger,
    oracle,
    point,
    bits::Int,
    radius_multiplier::Real,
)
    return setprecision(BigFloat, bits) do
        x = BigFloat.(point)
        gradient = zeros(BigFloat, oracle.dimension)
        scale = eps(BigFloat)^(one(BigFloat) / BigFloat(3))
        for coordinate in 1:oracle.dimension
            step = BigFloat(radius_multiplier) * scale *
                   max(one(BigFloat), abs(x[coordinate]))
            plus = copy(x)
            minus = copy(x)
            plus[coordinate] += step
            minus[coordinate] -= step
            gradient[coordinate] = (
                _s4c_target!(ledger, oracle, plus, bits) -
                _s4c_target!(ledger, oracle, minus, bits)
            ) / (BigFloat(2) * step)
        end
        all(isfinite, gradient) || _s4c_fail("nonfinite target gradient")
        gradient
    end
end

function _s4c_pairwise_configuration_disagreement(stages)
    points = [BigFloat.(stage.endpoint) for stage in stages]
    length(points) <= 1 && return BigFloat(0)
    return maximum(
        norm(points[first] - points[second], Inf) for
        first in 1:(length(points) - 1) for second in (first + 1):length(points)
    )
end

function _s4c_error_audit_256!(
    ledger,
    input,
    primary,
    confirmations,
    audits,
    options,
)
    stage128, stage256 = primary
    audit128, audit256 = audits[1], audits[2]
    q128_1 = BigFloat.(audit128.final[(128, 1.0)].correction)
    q128_half = BigFloat.(audit128.final[(128, 0.5)].correction)
    q256_1 = BigFloat.(audit256.final[(256, 1.0)].correction)
    q256_half = BigFloat.(audit256.final[(256, 0.5)].correction)
    s128 = setprecision(BigFloat, 128) do
        eps(BigFloat)^(BigFloat(2) / BigFloat(3)) *
        max(one(BigFloat), norm(BigFloat.(stage128.endpoint), Inf))
    end
    s256 = setprecision(BigFloat, 256) do
        eps(BigFloat)^(BigFloat(2) / BigFloat(3)) *
        max(one(BigFloat), norm(BigFloat.(stage256.endpoint), Inf))
    end
    radius_reserve_components = BigFloat[
        norm(q128_1 - q128_half, Inf) + s128,
        norm(q256_1 - q256_half, Inf) + s256,
    ]
    radius_reserve = maximum(radius_reserve_components)
    precision_reserve_components = BigFloat[
        norm(q256_1 - q128_1, Inf) + max(s128, s256),
        norm(q256_half - q128_half, Inf) + max(s128, s256),
    ]
    precision_reserve = maximum(precision_reserve_components)
    correction_reserve = max(radius_reserve, precision_reserve)
    final_correction_norms = BigFloat[
        norm(q128_1, Inf),
        norm(q128_half, Inf),
        norm(q256_1, Inf),
        norm(q256_half, Inf),
    ]
    final_correction_magnitude = maximum(final_correction_norms)
    comparison_stages = Any[stage256, confirmations...]
    raw_configuration_components = BigFloat[
        BigFloat(stage128.last_step),
        BigFloat(stage256.last_step),
        norm(BigFloat.(stage256.endpoint) - BigFloat.(stage128.endpoint), Inf),
        _s4c_pairwise_configuration_disagreement(comparison_stages),
        correction_reserve,
        final_correction_magnitude,
    ]
    raw_configuration = maximum(raw_configuration_components)
    configuration_error = BigFloat(options.error_reserve_multiplier) * raw_configuration

    gradients = Dict{Tuple{Int,Float64},Vector{BigFloat}}()
    for (bits, stage) in ((128, stage128), (256, stage256))
        for radius in _S4C_RADII
            gradients[(bits, radius)] = BigFloat.(_s4c_target_gradient!(
                ledger,
                input.oracle,
                stage.endpoint,
                bits,
                radius,
            ))
        end
    end
    uncertainty = Dict{Tuple{Int,Float64},BigFloat}()
    for bits in _S4C_BITS, radius in _S4C_RADII
        gradient = gradients[(bits, radius)]
        uncertainty[(bits, radius)] = setprecision(BigFloat, bits) do
            eps(BigFloat)^(BigFloat(2) / BigFloat(3)) *
            max(one(BigFloat), norm(gradient, 1))
        end
    end
    gradient_radius_components = BigFloat[
        norm(gradients[(bits, 1.0)] - gradients[(bits, 0.5)], 1) +
        max(uncertainty[(bits, 1.0)], uncertainty[(bits, 0.5)]) for
        bits in _S4C_BITS
    ]
    gradient_radius_reserve = maximum(gradient_radius_components)
    gradient_precision_components = BigFloat[
        norm(gradients[(256, radius)] - gradients[(128, radius)], 1) +
        max(uncertainty[(128, radius)], uncertainty[(256, radius)]) for
        radius in _S4C_RADII
    ]
    gradient_precision_reserve = maximum(gradient_precision_components)
    gradient_reserve = max(gradient_radius_reserve, gradient_precision_reserve)
    target_precision_disagreement = abs(stage256.target - stage128.target)
    target_comparisons = BigFloat[stage256.target; (stage.target for stage in confirmations)...]
    target_confirmation_disagreement = isempty(confirmations) ? BigFloat(0) :
        maximum(abs(first - second) for first in target_comparisons for second in target_comparisons)
    target_roundoff = max(
        setprecision(BigFloat, 128) do
            eps(BigFloat) * max(one(BigFloat), abs(stage128.target))
        end,
        setprecision(BigFloat, 256) do
            eps(BigFloat) * max(one(BigFloat), abs(stage256.target))
        end,
    )
    target_error_components = BigFloat[
        target_precision_disagreement,
        target_confirmation_disagreement,
        norm(gradients[(256, 1.0)], 1) * raw_configuration,
        gradient_reserve * raw_configuration,
        target_roundoff,
    ]
    target_error = BigFloat(options.error_reserve_multiplier) *
                   maximum(target_error_components)
    passed = configuration_error <= BigFloat(options.configuration_error_goal) &&
             target_error <= BigFloat(options.target_error_goal)
    return (
        raw_configuration=raw_configuration,
        configuration_error=configuration_error,
        target_error=target_error,
        passed=passed,
        document=Dict{String,Any}(
            "configuration_error" => configuration_error,
            "configuration_goal" => options.configuration_error_goal,
            "configuration_sources" => Dict{String,Any}(
                "confirmation_endpoints" => Any[
                    collect(stage.endpoint) for stage in confirmations
                ],
                "primary_128_endpoint" => collect(stage128.endpoint),
                "primary_128_last_step" => stage128.last_step,
                "primary_256_endpoint" => collect(stage256.endpoint),
                "primary_256_last_step" => stage256.last_step,
            ),
            "correction_reserve" => correction_reserve,
            "final_corrections" => Dict{String,Any}(
                "q128_radius_0.5" => collect(q128_half),
                "q128_radius_1" => collect(q128_1),
                "q256_radius_0.5" => collect(q256_half),
                "q256_radius_1" => collect(q256_1),
            ),
            "final_correction_magnitude" => final_correction_magnitude,
            "final_correction_norms" => final_correction_norms,
            "decision" => passed,
            "gradient_precision_components" => gradient_precision_components,
            "gradient_precision_reserve" => gradient_precision_reserve,
            "gradient_radius_components" => gradient_radius_components,
            "gradient_radius_reserve" => gradient_radius_reserve,
            "gradient_reserve" => gradient_reserve,
            "gradients" => Any[
                Dict{String,Any}(
                    "precision_bits" => bits,
                    "radius_multiplier" => radius,
                    "uncertainty" => uncertainty[(bits, radius)],
                    "values" => collect(gradients[(bits, radius)]),
                ) for bits in _S4C_BITS for radius in _S4C_RADII
            ],
            "precision_reserve_components" => precision_reserve_components,
            "radius_reserve_components" => radius_reserve_components,
            "raw_configuration_components" => raw_configuration_components,
            "raw_configuration_error" => raw_configuration,
            "roundoff_scales" => Dict{String,Any}("s128" => s128, "s256" => s256),
            "target_error" => target_error,
            "target_error_components" => target_error_components,
            "target_goal" => options.target_error_goal,
            "target_precision_disagreement" => target_precision_disagreement,
            "target_confirmation_disagreement" => target_confirmation_disagreement,
            "target_roundoff" => target_roundoff,
            "target_values" => Dict{String,Any}(
                "confirmation" => Any[stage.target for stage in confirmations],
                "primary_128" => stage128.target,
                "primary_256" => stage256.target,
            ),
        ),
    )
end

function _s4c_error_audit!(ledger, input, primary, confirmations, audits, options)
    return setprecision(BigFloat, 256) do
        _s4c_error_audit_256!(
            ledger,
            input,
            primary,
            confirmations,
            audits,
            options,
        )
    end
end

function run_s4(
    input::S4CandidateInput;
    options::ExperimentOptions=ExperimentOptions(
        precision_ladder=(128, 256),
        semantic_precision_bits=256,
    ),
    clock_ns=time_ns,
)
    variant = "S4-C2-NULLSPACE-TWO-STEP"
    route_name = "c2-finite-difference-nullspace-two-step"
    ledger = _work_ledger(options, clock_ns)
    diagnostics = Dict{String,Any}(
        "algorithm" => "finite-difference-nullspace-two-step-v1",
        "analytic_fixture_visible" => false,
        "phase" => "initialization",
        "product_connected" => false,
    )
    if !_s4c_frozen_options(options)
        return S4VariantOutcome(
            _s4_unknown_core(
                variant,
                route_name,
                "S4 candidate options differ from the frozen protocol",
                ledger,
            ),
            diagnostics,
        )
    end
    if input.oracle.capability != :C2
        core = _s4_unknown_core(
            variant,
            route_name,
            "declared C2 capability required",
            ledger,
        )
        return S4VariantOutcome(core, diagnostics)
    end
    if input.oracle.dimension != input.oracle.residual_dimension
        core = _s4_unknown_core(
            variant,
            route_name,
            "S4 requires a square system",
            ledger,
        )
        return S4VariantOutcome(core, diagnostics)
    end
    try
        diagnostics["phase"] = "initial_route"
        route = _s4c_initial_route!(ledger, input, options)
        diagnostics["initial_route"] = route.document

        diagnostics["phase"] = "primary_trajectories"
        primary = Any[
            _s4c_trajectory!(
                ledger,
                input,
                input.endpoint,
                bits,
                route.nullity,
                options,
                "primary-$bits",
            ) for bits in _S4C_BITS
        ]
        diagnostics["primary_trajectories"] = Any[
            Dict{String,Any}(
                "endpoint" => collect(stage.endpoint),
                "identity" => stage.identity,
                "iterations" => stage.iterations,
                "last_step" => stage.last_step,
                "precision_bits" => stage.bits,
                "residual_linf" => stage.residual_linf,
                "start" => collect(stage.start),
                "target" => stage.target,
                "trace" => stage.trace,
            ) for stage in primary
        ]

        diagnostics["phase"] = "confirmation_trajectories"
        confirmations = Any[]
        for index in 1:options.independent_confirmation_count
            direction = _confirmation_direction(input.oracle.dimension, index)
            start = input.endpoint .+
                    options.confirmation_perturbation_radius .* direction
            push!(confirmations, _s4c_trajectory!(
                ledger,
                input,
                start,
                256,
                route.nullity,
                options,
                "confirmation-$index",
            ))
        end
        diagnostics["confirmation_trajectories"] = Any[
            Dict{String,Any}(
                "endpoint" => collect(stage.endpoint),
                "identity" => stage.identity,
                "iterations" => stage.iterations,
                "last_step" => stage.last_step,
                "precision_bits" => stage.bits,
                "residual_linf" => stage.residual_linf,
                "start" => collect(stage.start),
                "target" => stage.target,
                "trace" => stage.trace,
            ) for stage in confirmations
        ]

        diagnostics["phase"] = "applicability_audits"
        all_stages = Any[primary...; confirmations...]
        audits = Any[
            _s4c_trajectory_audit!(
                ledger,
                input,
                stage,
                route.nullity,
                options,
            ) for stage in all_stages
        ]
        diagnostics["applicability_audits"] = Any[audit.document for audit in audits]

        diagnostics["phase"] = "canonical_semantics"
        semantics = SemanticReplayEvidence[
            _semantic_replay!(
                ledger,
                input,
                stage.endpoint,
                stage.bits,
                options,
            ) for stage in all_stages
        ]
        all(evidence -> evidence.accepted, semantics) ||
            _s4c_fail("canonical semantic replay failed")
        diagnostics["semantic_replays"] = Any[
            Dict{String,Any}(
                "accepted" => evidence.accepted,
                "endpoint" => collect(evidence.endpoint),
                "precision_bits" => evidence.precision_bits,
                "residual_linf" => evidence.residual_linf,
                "target" => evidence.target,
            ) for evidence in semantics
        ]

        diagnostics["phase"] = "error_audit"
        error_audit = _s4c_error_audit!(
            ledger,
            input,
            primary,
            confirmations,
            audits,
            options,
        )
        diagnostics["error_audit"] = error_audit.document
        error_audit.passed || _s4c_fail("configuration or target error gate failed")

        final_stage = primary[2]
        evidence = NumericalSingularRootEvidence(
            "finite_difference_nullspace_two_step_v1",
            256,
            _S4C_BITS,
            Tuple(final_stage.endpoint),
            final_stage.target,
            final_stage.residual_linf,
            route.retained,
            route.nullity,
            route.condition,
            error_audit.configuration_error,
            error_audit.target_error,
            Tuple(Tuple(stage.endpoint) for stage in confirmations),
            Tuple(stage.target for stage in confirmations),
            Tuple(stage.residual_linf for stage in confirmations),
            route.signatures,
            (),
            0,
            true,
            true,
            true,
            true,
        )
        diagnostics["phase"] = "promoted"
        promotion_work = _s4_checked_work_snapshot!(ledger)
        core = ExperimentalOutcome(
            variant,
            route_name,
            :promoted,
            "S4 applicability and numerical-root evidence accepted",
            semantics[2],
            evidence,
            promotion_work,
        )
        return S4VariantOutcome(core, diagnostics)
    catch error
        error isa InterruptException && rethrow()
        reason = if error isa ExperimentBudgetExceeded
            string(error.reason)
        elseif error isa _S4CandidateReject
            error.reason
        else
            "candidate callback or numerical failure: $(nameof(typeof(error))): $(sprint(showerror, error))"
        end
        diagnostics["failure"] = Dict{String,Any}(
            "exception_type" => string(nameof(typeof(error))),
            "reason" => reason,
        )
        diagnostics["phase"] = "failed"
        core = _s4_unknown_core(variant, route_name, reason, ledger)
        return S4VariantOutcome(core, diagnostics)
    end
end
