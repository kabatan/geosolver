# Frozen analytic lower-bound control. Numerical helpers in this file are kept
# separate from candidate.jl by protocol.

const _S4A_BITS = (128, 256)
const _S4A_GAP_MAX = 1.0e-6
const _S4A_MAX_NULLITY = 4
const _S4A_ANGLE_MAX = 1.0e-6
const _S4A_PROJECTED_CONDITION_MAX = 1.0e12
const _S4A_ORDER_MIN = 1 // 16
const _S4A_ORDER_MAX = 16
const _S4A_AUDIT_ITERATION = 65
const _S4A_COUNTER_NAMESPACE = UInt64(0x53342d43322d5631)

_s4a_fail(reason::AbstractString) = throw(_S4ControlReject(String(reason)))

function _s4a_frozen_options(options::ExperimentOptions)
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

function _s4a_residual!(ledger, oracle, x::AbstractVector{T}, bits::Int) where {T}
    values = T.(_evaluate_residual!(ledger, oracle, x, bits))
    _check_deadline!(ledger)
    all(isfinite, values) || _s4a_fail("nonfinite residual")
    return values
end

function _s4a_target!(ledger, oracle, x::AbstractVector{T}, bits::Int) where {T}
    value = T(_evaluate_target!(ledger, oracle, x, bits))
    _check_deadline!(ledger)
    isfinite(value) || _s4a_fail("nonfinite target")
    return value
end

function _s4a_jacobian!(
    ledger,
    analytic::S4AnalyticControlOracle,
    oracle,
    x::AbstractVector{T},
    bits::Int,
) where {T}
    _charge_callback!(ledger, :jacobian, bits)
    jacobian = Matrix{T}(analytic.analytic_jacobian(x))
    _check_deadline!(ledger)
    size(jacobian) == (oracle.residual_dimension, oracle.dimension) ||
        _s4a_fail("analytic Jacobian has wrong shape")
    all(isfinite, jacobian) || _s4a_fail("analytic Jacobian is nonfinite")
    return jacobian
end

function _s4a_second_directional!(
    ledger,
    analytic::S4AnalyticControlOracle,
    oracle,
    x::AbstractVector{T},
    first,
    second,
    bits::Int,
) where {T}
    _charge_callback!(ledger, :residual, bits)
    raw = analytic.analytic_second_directional(x, first, second)
    _check_deadline!(ledger)
    raw isa AbstractVector ||
        _s4a_fail("analytic second-directional callback must return a vector")
    values = T[raw...]
    length(values) == oracle.residual_dimension ||
        _s4a_fail("analytic second-directional callback has wrong shape")
    all(isfinite, values) || _s4a_fail("analytic second-directional callback is nonfinite")
    return values
end

function _s4a_split!(
    ledger,
    jacobian::AbstractMatrix{T};
    fixed_nullity=nothing,
    require_route_selection::Bool=false,
) where {T}
    n = size(jacobian, 2)
    size(jacobian) == (n, n) || _s4a_fail("analytic control requires a square Jacobian")
    _charge_factorization!(ledger)
    decomposition = svd(Matrix{T}(jacobian); full=true)
    _check_deadline!(ledger)
    singular_values = T[decomposition.S...]
    length(singular_values) == n && all(isfinite, singular_values) ||
        _s4a_fail("invalid analytic Jacobian singular values")
    sigma1 = singular_values[1]
    tau = T(32) * T(n) * eps(T) * max(one(T), sigma1)
    selected_by_gap = nothing
    if fixed_nullity === nothing || require_route_selection
        selected = nothing
        for index in 1:(n - 1)
            boundary = singular_values[index]
            ratio = iszero(boundary) ? T(Inf) : singular_values[index + 1] / boundary
            if ratio <= T(_S4A_GAP_MAX) && boundary > tau
                selected = index
                break
            end
        end
        selected === nothing && _s4a_fail("no qualifying analytic smallest gap")
        selected_by_gap = selected::Int
    end
    retained = if fixed_nullity === nothing
        selected_by_gap::Int
    else
        nullity = Int(fixed_nullity)
        1 <= nullity < n || _s4a_fail("invalid analytic frozen nullity")
        frozen_retained = n - nullity
        if require_route_selection && selected_by_gap != frozen_retained
            _s4a_fail("analytic frozen nullity disagrees with route selection")
        end
        frozen_retained
    end
    nullity = n - retained
    nullity <= _S4A_MAX_NULLITY || _s4a_fail("analytic nullity exceeds maximum")
    singular_values[retained] > tau || _s4a_fail("analytic retained value below cutoff")
    condition = iszero(singular_values[retained]) ? T(Inf) :
                sigma1 / singular_values[retained]
    isfinite(condition) || _s4a_fail("nonfinite analytic retained condition")
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

function _s4a_angle_sine!(ledger, reference::AbstractMatrix{T}, basis::AbstractMatrix{T}) where {T}
    size(reference) == size(basis) || _s4a_fail("analytic nullspace dimension drift")
    _charge_factorization!(ledger)
    overlap = svd(Matrix{T}(transpose(reference) * basis); full=false).S
    _check_deadline!(ledger)
    isempty(overlap) && _s4a_fail("empty analytic nullspace overlap")
    minimum_overlap = clamp(minimum(overlap), zero(T), one(T))
    sine = sqrt(max(zero(T), one(T) - minimum_overlap^2))
    isfinite(sine) || _s4a_fail("nonfinite analytic principal angle")
    return sine
end

function _s4a_coefficients(::Type{T}, nullity::Int, iteration::Int) where {T}
    1 <= nullity <= _S4A_MAX_NULLITY || _s4a_fail("invalid analytic coefficient nullity")
    iteration >= 1 || _s4a_fail("invalid analytic coefficient iteration")
    integers = Vector{Int64}(undef, nullity)
    for coordinate in 1:nullity
        z = _S4A_COUNTER_NAMESPACE ⊻ (UInt64(nullity) << 48) ⊻
            (UInt64(iteration) << 16) ⊻ UInt64(coordinate)
        z += UInt64(0x9e3779b97f4a7c15)
        z = (z ⊻ (z >> 30)) * UInt64(0xbf58476d1ce4e5b9)
        z = (z ⊻ (z >> 27)) * UInt64(0x94d049bb133111eb)
        value = z ⊻ (z >> 31)
        magnitude = Int64(1 + Int(value & UInt64(0x7fffffff)))
        integers[coordinate] = iszero(value >> 63) ? magnitude : -magnitude
    end
    coefficients = T.(integers)
    magnitude = norm(coefficients, 2)
    isfinite(magnitude) && magnitude > 0 || _s4a_fail("invalid analytic coefficient norm")
    return coefficients ./ magnitude
end

function _s4a_projected_operator!(
    ledger,
    analytic,
    oracle,
    x_range::AbstractVector{T},
    left_null::AbstractMatrix{T},
    right_null::AbstractMatrix{T},
    direction::AbstractVector{T},
    bits::Int,
) where {T}
    nullity = size(right_null, 2)
    operator = zeros(T, nullity, nullity)
    for column in 1:nullity
        directional = _s4a_second_directional!(
            ledger,
            analytic,
            oracle,
            x_range,
            direction,
            view(right_null, :, column),
            bits,
        )
        operator[:, column] .= transpose(left_null) * directional
    end
    _check_deadline!(ledger)
    all(isfinite, operator) || _s4a_fail("nonfinite analytic projected operator")
    return operator
end

function _s4a_projected_factor!(ledger, operator::AbstractMatrix{T}) where {T}
    nullity = size(operator, 1)
    size(operator) == (nullity, nullity) || _s4a_fail("analytic projected operator not square")
    _charge_factorization!(ledger)
    decomposition = svd(Matrix{T}(operator); full=true)
    _check_deadline!(ledger)
    spectrum = T[decomposition.S...]
    length(spectrum) == nullity && all(isfinite, spectrum) ||
        _s4a_fail("invalid analytic projected spectrum")
    largest = spectrum[1]
    tau = T(32) * T(nullity) * sqrt(eps(T)) * max(one(T), largest)
    all(value -> value > tau, spectrum) || _s4a_fail("analytic projected rank loss")
    condition = iszero(spectrum[end]) ? T(Inf) : largest / spectrum[end]
    isfinite(condition) && condition <= T(_S4A_PROJECTED_CONDITION_MAX) ||
        _s4a_fail("analytic projected condition gate failed")
    return (factor=decomposition, spectrum=spectrum, tau=tau, condition=condition)
end

function _s4a_local_probe(ledger, split, reference, nullity::Int, iteration::Int)
    T = eltype(split.V2)
    if reference === nothing
        coefficients = _s4a_coefficients(T, nullity, iteration)
        return (
            coefficients=coefficients,
            local_coordinates=copy(coefficients),
            local_coordinate_norm=norm(coefficients, 2),
            direction=split.V2 * coefficients,
            iteration=iteration,
            projection_loss=zero(T),
            angle_sine=zero(T),
            subspace_decision=true,
            transported=false,
        )
    end
    reference_basis = T.(reference.basis)
    reference_direction = T.(reference.direction)
    angle_sine = _s4a_angle_sine!(ledger, reference_basis, split.V2)
    angle_sine <= T(_S4A_ANGLE_MAX) || _s4a_fail("analytic transported angle failed")
    local_coordinates = transpose(split.V2) * reference_direction
    local_norm = norm(local_coordinates, 2)
    isfinite(local_norm) && local_norm > 0 || _s4a_fail("zero analytic transported projection")
    projection = split.V2 * local_coordinates
    projection_loss = norm(reference_direction - projection, 2)
    isfinite(projection_loss) || _s4a_fail("nonfinite analytic projection loss")
    normalized = local_coordinates ./ local_norm
    return (
        coefficients=normalized,
        local_coordinates=local_coordinates,
        local_coordinate_norm=local_norm,
        direction=split.V2 * normalized,
        iteration=iteration,
        projection_loss=projection_loss,
        angle_sine=angle_sine,
        subspace_decision=true,
        transported=true,
    )
end

function _s4a_probe_document(bits, split, projected, probe)
    return Dict{String,Any}(
        "angle_sine" => probe.angle_sine,
        "c_local" => collect(probe.local_coordinates),
        "c_local_norm" => probe.local_coordinate_norm,
        "coefficients" => collect(probe.coefficients),
        "condition" => split.condition,
        "direction" => collect(probe.direction),
        "gap_ratio" => split.singular_values[split.retained + 1] /
                       split.singular_values[split.retained],
        "ell" => probe.iteration,
        "left_null_basis" => Any[
            collect(column) for column in eachcol(split.U2)
        ],
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
        "subspace_angle_bound" => _S4A_ANGLE_MAX,
        "subspace_decision" => probe.subspace_decision,
        "transported" => probe.transported,
    )
end

function _s4a_initial_route!(
    ledger,
    input::S4CandidateInput,
    analytic::S4AnalyticControlOracle,
    options::ExperimentOptions,
)
    probes = Dict{Int,Any}()
    documents = Any[]
    selected_nullity = nothing
    route_goal = BigFloat(options.semantic_residual_tolerance) /
                 (BigFloat(4) * BigFloat(options.error_reserve_multiplier))
    for bits in _S4A_BITS
        probe = setprecision(BigFloat, bits) do
            x = BigFloat.(input.endpoint)
            residual = _s4a_residual!(ledger, input.oracle, x, bits)
            norm(residual, Inf) <= route_goal ||
                _s4a_fail("analytic primary route residual above frozen goal")
            jacobian = _s4a_jacobian!(ledger, analytic, input.oracle, x, bits)
            split = _s4a_split!(ledger, jacobian)
            if selected_nullity === nothing
                selected_nullity = split.nullity
            elseif split.nullity != selected_nullity
                _s4a_fail("analytic route nullity disagreement")
            end
            range_coordinates = transpose(split.U1) * residual
            x_range = x - split.V1 *
                      (range_coordinates ./ split.retained_singular_values)
            local_probe = _s4a_local_probe(ledger, split, nothing, split.nullity, 1)
            operator = _s4a_projected_operator!(
                ledger,
                analytic,
                input.oracle,
                x_range,
                split.U2,
                split.V2,
                local_probe.direction,
                bits,
            )
            projected = _s4a_projected_factor!(ledger, operator)
            document = _s4a_probe_document(bits, split, projected, local_probe)
            document["residual_linf"] = norm(residual, Inf)
            (
                split=split,
                projected=projected,
                probe=local_probe,
                document=document,
            )
        end
        probes[bits] = probe
        push!(documents, probe.document)
    end
    nullity = selected_nullity::Int
    left_angle, right_angle = setprecision(BigFloat, 128) do
        (
            _s4a_angle_sine!(
                ledger,
                BigFloat.(probes[256].split.U2),
                BigFloat.(probes[128].split.U2),
            ),
            _s4a_angle_sine!(
                ledger,
                BigFloat.(probes[256].split.V2),
                BigFloat.(probes[128].split.V2),
            ),
        )
    end
    left_angle <= BigFloat(_S4A_ANGLE_MAX) || _s4a_fail("analytic left angle failed")
    right_angle <= BigFloat(_S4A_ANGLE_MAX) || _s4a_fail("analytic right angle failed")
    return (
        nullity=nullity,
        retained=input.oracle.dimension - nullity,
        condition=max(
            BigFloat(probes[128].split.condition),
            BigFloat(probes[256].split.condition),
        ),
        signatures=Tuple((
            precision_bits=bits,
            rank=probes[bits].split.retained,
            nullity=probes[bits].split.nullity,
        ) for bits in _S4A_BITS),
        document=Dict{String,Any}(
            "angle_bound" => _S4A_ANGLE_MAX,
            "left_angle_sine" => left_angle,
            "nullity" => nullity,
            "probes" => documents,
            "residual_goal" => route_goal,
            "right_angle_sine" => right_angle,
            "selected_rank" => input.oracle.dimension - nullity,
        ),
    )
end

function _s4a_step!(
    ledger,
    input::S4CandidateInput,
    analytic::S4AnalyticControlOracle,
    x::AbstractVector{T},
    bits::Int,
    nullity::Int,
    iteration::Int;
    reference=nothing,
    compute_correction::Bool=true,
    require_route_selection::Bool=false,
) where {T<:AbstractFloat}
    jacobian = _s4a_jacobian!(ledger, analytic, input.oracle, x, bits)
    split = _s4a_split!(
        ledger,
        jacobian;
        fixed_nullity=nullity,
        require_route_selection,
    )
    residual = _s4a_residual!(ledger, input.oracle, x, bits)
    range_coordinates = transpose(split.U1) * residual
    x_range = x - split.V1 * (range_coordinates ./ split.retained_singular_values)
    probe = _s4a_local_probe(ledger, split, reference, nullity, iteration)
    operator = _s4a_projected_operator!(
        ledger,
        analytic,
        input.oracle,
        x_range,
        split.U2,
        split.V2,
        probe.direction,
        bits,
    )
    projected = _s4a_projected_factor!(ledger, operator)
    correction = zeros(T, length(x))
    next = copy(x)
    if compute_correction
        range_jacobian = _s4a_jacobian!(
            ledger,
            analytic,
            input.oracle,
            x_range,
            bits,
        )
        right_hand_side = -(transpose(split.U2) * range_jacobian * probe.direction)
        delta = projected.factor \ right_hand_side
        _check_deadline!(ledger)
        all(isfinite, delta) || _s4a_fail("nonfinite analytic projected solve")
        next = x_range + split.V2 * delta
        correction = next - x
        all(isfinite, next) && all(isfinite, correction) ||
            _s4a_fail("nonfinite analytic complete step")
    end
    document = _s4a_probe_document(bits, split, projected, probe)
    document["complete_correction"] = collect(correction)
    document["correction_computed"] = compute_correction
    document["jacobian_inf_norm"] = norm(jacobian, Inf)
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

function _s4a_trajectory!(
    ledger,
    input,
    analytic,
    start,
    bits::Int,
    nullity::Int,
    options,
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
            step = _s4a_step!(
                ledger,
                input,
                analytic,
                x,
                bits,
                nullity,
                iteration,
            )
            previous = copy(x)
            x = BigFloat.(step.next)
            residual = _s4a_residual!(ledger, input.oracle, x, bits)
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
        converged || _s4a_fail("analytic trajectory failed frozen stop rule")
        target = _s4a_target!(ledger, input.oracle, x, bits)
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

function _s4a_reference!(ledger, input, analytic, start, nullity::Int)
    return setprecision(BigFloat, 256) do
        x = BigFloat.(start)
        jacobian = _s4a_jacobian!(ledger, analytic, input.oracle, x, 256)
        split = _s4a_split!(
            ledger,
            jacobian;
            fixed_nullity=nullity,
            # The initial endpoint has already selected k.  A perturbed
            # trajectory start supplies a basis for that frozen route; it is
            # not a second gap-based routing decision.
            require_route_selection=false,
        )
        coefficients = _s4a_coefficients(BigFloat, nullity, _S4A_AUDIT_ITERATION)
        direction = split.V2 * coefficients
        magnitude = norm(direction, 2)
        isfinite(magnitude) && magnitude > 0 || _s4a_fail("invalid analytic reference")
        direction ./= magnitude
        (
            basis=copy(split.V2),
            direction=copy(direction),
            coefficients=copy(coefficients),
            precision_bits=256,
        )
    end
end

function _s4a_order_and_null_decision(start_probe, final_probe, stage, bits, options)
    return setprecision(BigFloat, bits) do
        ratios = BigFloat.(final_probe.projected.spectrum) ./
                 BigFloat.(start_probe.projected.spectrum)
        order_passed = all(
            ratio -> isfinite(ratio) && ratio >= BigFloat(_S4A_ORDER_MIN) &&
                     ratio <= BigFloat(_S4A_ORDER_MAX),
            ratios,
        )
        normalized_discarded = maximum(BigFloat.(
            final_probe.split.singular_values[(final_probe.split.retained + 1):end],
        )) / max(one(BigFloat), BigFloat(final_probe.split.singular_values[1]))
        normalized_step = BigFloat(stage.last_step) /
                          max(one(BigFloat), norm(BigFloat.(stage.endpoint), Inf))
        null_bound = BigFloat(options.error_reserve_multiplier) *
                     (normalized_step^2 + eps(BigFloat)^(BigFloat(2) / BigFloat(3)))
        null_passed = isfinite(normalized_discarded) && normalized_discarded <= null_bound
        return (
            ratios=ratios,
            order_passed=order_passed,
            normalized_discarded=normalized_discarded,
            normalized_step=normalized_step,
            null_bound=null_bound,
            null_passed=null_passed,
        )
    end
end

function _s4a_residual_decay_decision(start_probe, final_probe, stage, bits, options)
    return setprecision(BigFloat, bits) do
        start_residual = BigFloat(norm(start_probe.residual, Inf))
        final_residual = BigFloat(norm(final_probe.residual, Inf))
        scale = max(
            one(BigFloat),
            start_residual,
            BigFloat(norm(start_probe.jacobian, Inf)) *
            max(one(BigFloat), norm(BigFloat.(stage.start), Inf)),
        )
        ratio = final_residual / scale
        normalized_step = BigFloat(stage.last_step) /
                          max(one(BigFloat), norm(BigFloat.(stage.endpoint), Inf))
        bound = BigFloat(options.error_reserve_multiplier) *
                (normalized_step^2 + eps(BigFloat)^(BigFloat(2) / BigFloat(3)))
        return (
            scale=scale,
            ratio=ratio,
            normalized_step=normalized_step,
            bound=bound,
            passed=isfinite(ratio) && ratio <= bound,
        )
    end
end

function _s4a_trajectory_audit!(
    ledger,
    input,
    analytic,
    stage,
    nullity::Int,
    options,
)
    reference = _s4a_reference!(ledger, input, analytic, stage.start, nullity)
    start_probes = Dict{Int,Any}()
    final_probes = Dict{Int,Any}()
    documents = Any[]
    all_passed = true
    for bits in _S4A_BITS
        start_probe, final_probe = setprecision(BigFloat, bits) do
            (
                _s4a_step!(
                    ledger,
                    input,
                    analytic,
                    BigFloat.(stage.start),
                    bits,
                    nullity,
                    _S4A_AUDIT_ITERATION;
                    reference=reference,
                    compute_correction=false,
                    # Start-side order probes inherit the frozen route.  The
                    # final-side probe below deliberately rechecks the gap.
                    require_route_selection=false,
                ),
                _s4a_step!(
                    ledger,
                    input,
                    analytic,
                    BigFloat.(stage.endpoint),
                    bits,
                    nullity,
                    _S4A_AUDIT_ITERATION;
                    reference=reference,
                    compute_correction=true,
                    require_route_selection=true,
                ),
            )
        end
        start_probes[bits] = start_probe
        final_probes[bits] = final_probe
        decision = _s4a_order_and_null_decision(
            start_probe,
            final_probe,
            stage,
            bits,
            options,
        )
        all_passed &= decision.order_passed && decision.null_passed
        push!(documents, Dict{String,Any}(
            "final" => final_probe.document,
            "null_decay" => Dict{String,Any}(
                "bound" => decision.null_bound,
                "decision" => decision.null_passed,
                "normalized_discarded_sigma" => decision.normalized_discarded,
                "normalized_last_step" => decision.normalized_step,
            ),
            "order_persistence" => Dict{String,Any}(
                "decision" => decision.order_passed,
                "lower_bound" => _S4A_ORDER_MIN,
                "ratios" => collect(decision.ratios),
                "upper_bound" => _S4A_ORDER_MAX,
            ),
            "precision_bits" => bits,
            "start" => start_probe.document,
        ))
    end
    residual_documents = Any[]
    for bits in _S4A_BITS
        start_probe = start_probes[bits]
        final_probe = final_probes[bits]
        decision = _s4a_residual_decay_decision(
            start_probe,
            final_probe,
            stage,
            bits,
            options,
        )
        all_passed &= decision.passed
        push!(residual_documents, Dict{String,Any}(
            "F_scale" => decision.scale,
            "bound" => decision.bound,
            "decision" => decision.passed,
            "normalized_last_step" => decision.normalized_step,
            "precision_bits" => bits,
            "residual_ratio" => decision.ratio,
        ))
    end
    all_passed || _s4a_fail("analytic trajectory final applicability audit failed")
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
                "ell" => _S4A_AUDIT_ITERATION,
                "precision_bits" => reference.precision_bits,
            ),
            "probes" => documents,
            "residual_decay" => residual_documents,
        ),
    )
end

function _s4a_target_gradient!(ledger, oracle, point, bits::Int, radius_multiplier::Real)
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
                _s4a_target!(ledger, oracle, plus, bits) -
                _s4a_target!(ledger, oracle, minus, bits)
            ) / (BigFloat(2) * step)
        end
        all(isfinite, gradient) || _s4a_fail("nonfinite analytic-control target gradient")
        gradient
    end
end

function _s4a_pairwise_configuration_disagreement(stages)
    points = [BigFloat.(stage.endpoint) for stage in stages]
    length(points) <= 1 && return BigFloat(0)
    return maximum(
        norm(points[first] - points[second], Inf) for
        first in 1:(length(points) - 1) for second in (first + 1):length(points)
    )
end

function _s4a_error_audit_256!(ledger, input, primary, confirmations, audits, options)
    stage128, stage256 = primary
    q128 = BigFloat.(audits[1].final[128].correction)
    q256 = BigFloat.(audits[2].final[256].correction)
    s128 = setprecision(BigFloat, 128) do
        eps(BigFloat)^(BigFloat(2) / BigFloat(3)) *
        max(one(BigFloat), norm(BigFloat.(stage128.endpoint), Inf))
    end
    s256 = setprecision(BigFloat, 256) do
        eps(BigFloat)^(BigFloat(2) / BigFloat(3)) *
        max(one(BigFloat), norm(BigFloat.(stage256.endpoint), Inf))
    end
    correction_reserve = norm(q256 - q128, Inf) + max(s128, s256)
    final_correction_norms = BigFloat[norm(q128, Inf), norm(q256, Inf)]
    final_correction_magnitude = maximum(final_correction_norms)
    comparison_stages = Any[stage256, confirmations...]
    raw_configuration_components = BigFloat[
        BigFloat(stage128.last_step),
        BigFloat(stage256.last_step),
        norm(BigFloat.(stage256.endpoint) - BigFloat.(stage128.endpoint), Inf),
        _s4a_pairwise_configuration_disagreement(comparison_stages),
        correction_reserve,
        final_correction_magnitude,
    ]
    raw_configuration = maximum(raw_configuration_components)
    configuration_error = BigFloat(options.error_reserve_multiplier) * raw_configuration
    gradients = Dict{Tuple{Int,Float64},Vector{BigFloat}}()
    for (bits, stage) in ((128, stage128), (256, stage256)), radius in (1.0, 0.5)
        gradients[(bits, radius)] = BigFloat.(_s4a_target_gradient!(
            ledger,
            input.oracle,
            stage.endpoint,
            bits,
            radius,
        ))
    end
    uncertainty = Dict{Tuple{Int,Float64},BigFloat}()
    for bits in _S4A_BITS, radius in (1.0, 0.5)
        uncertainty[(bits, radius)] = setprecision(BigFloat, bits) do
            eps(BigFloat)^(BigFloat(2) / BigFloat(3)) *
            max(one(BigFloat), norm(gradients[(bits, radius)], 1))
        end
    end
    gradient_radius_components = BigFloat[
        norm(gradients[(bits, 1.0)] - gradients[(bits, 0.5)], 1) +
        max(uncertainty[(bits, 1.0)], uncertainty[(bits, 0.5)]) for bits in _S4A_BITS
    ]
    gradient_radius_reserve = maximum(gradient_radius_components)
    gradient_precision_components = BigFloat[
        norm(gradients[(256, radius)] - gradients[(128, radius)], 1) +
        max(uncertainty[(128, radius)], uncertainty[(256, radius)]) for
        radius in (1.0, 0.5)
    ]
    gradient_precision_reserve = maximum(gradient_precision_components)
    gradient_reserve = max(gradient_radius_reserve, gradient_precision_reserve)
    target_precision_disagreement = abs(stage256.target - stage128.target)
    target_values = BigFloat[stage256.target, (stage.target for stage in confirmations)...]
    target_confirmation_disagreement = isempty(confirmations) ? BigFloat(0) :
        maximum(abs(first - second) for first in target_values for second in target_values)
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
                "q128" => collect(q128),
                "q256" => collect(q256),
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
                ) for bits in _S4A_BITS for radius in (1.0, 0.5)
            ],
            "raw_configuration_components" => raw_configuration_components,
            "raw_configuration_error" => raw_configuration,
            "roundoff_scales" => Dict{String,Any}("s128" => s128, "s256" => s256),
            "target_confirmation_disagreement" => target_confirmation_disagreement,
            "target_error" => target_error,
            "target_error_components" => target_error_components,
            "target_goal" => options.target_error_goal,
            "target_precision_disagreement" => target_precision_disagreement,
            "target_roundoff" => target_roundoff,
            "target_values" => Dict{String,Any}(
                "confirmation" => Any[stage.target for stage in confirmations],
                "primary_128" => stage128.target,
                "primary_256" => stage256.target,
            ),
        ),
    )
end

function _s4a_error_audit!(ledger, input, primary, confirmations, audits, options)
    return setprecision(BigFloat, 256) do
        _s4a_error_audit_256!(
            ledger,
            input,
            primary,
            confirmations,
            audits,
            options,
        )
    end
end

function run_s4_analytic_control(
    input::S4CandidateInput,
    analytic::S4AnalyticControlOracle;
    options::ExperimentOptions=ExperimentOptions(
        precision_ladder=(128, 256),
        semantic_precision_bits=256,
    ),
    clock_ns=time_ns,
)
    variant = "S4-ANALYTIC-TWO-STEP-CONTROL"
    route_name = "analytic-nullspace-two-step-control"
    ledger = _work_ledger(options, clock_ns)
    diagnostics = Dict{String,Any}(
        "algorithm" => "independent-analytic-nullspace-two-step-v1",
        "analytic_fixture_visible" => true,
        "phase" => "initialization",
        "product_connected" => false,
    )
    if !_s4a_frozen_options(options)
        return S4VariantOutcome(
            _s4_unknown_core(
                variant,
                route_name,
                "analytic S4 options differ from the frozen protocol",
                ledger,
            ),
            diagnostics,
        )
    end
    if input.oracle.capability != :C2
        return S4VariantOutcome(
            _s4_unknown_core(
                variant,
                route_name,
                "declared C2 capability required",
                ledger,
            ),
            diagnostics,
        )
    end
    if input.oracle.dimension != input.oracle.residual_dimension
        return S4VariantOutcome(
            _s4_unknown_core(
                variant,
                route_name,
                "analytic S4 requires a square system",
                ledger,
            ),
            diagnostics,
        )
    end
    try
        diagnostics["phase"] = "initial_route"
        route = _s4a_initial_route!(ledger, input, analytic, options)
        diagnostics["initial_route"] = route.document

        diagnostics["phase"] = "primary_trajectories"
        primary = Any[
            _s4a_trajectory!(
                ledger,
                input,
                analytic,
                input.endpoint,
                bits,
                route.nullity,
                options,
                "primary-$bits",
            ) for bits in _S4A_BITS
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
            push!(confirmations, _s4a_trajectory!(
                ledger,
                input,
                analytic,
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
            _s4a_trajectory_audit!(
                ledger,
                input,
                analytic,
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
            _s4a_fail("analytic canonical semantic replay failed")
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
        error_audit = _s4a_error_audit!(
            ledger,
            input,
            primary,
            confirmations,
            audits,
            options,
        )
        diagnostics["error_audit"] = error_audit.document
        error_audit.passed || _s4a_fail("analytic configuration or target error gate failed")

        final_stage = primary[2]
        evidence = NumericalSingularRootEvidence(
            "analytic_nullspace_two_step_control_v1",
            256,
            _S4A_BITS,
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
            "analytic S4 applicability and numerical-root evidence accepted",
            semantics[2],
            evidence,
            promotion_work,
        )
        return S4VariantOutcome(core, diagnostics)
    catch error
        error isa InterruptException && rethrow()
        reason = if error isa ExperimentBudgetExceeded
            string(error.reason)
        elseif error isa _S4ControlReject
            error.reason
        else
            "analytic callback or numerical failure: $(nameof(typeof(error))): $(sprint(showerror, error))"
        end
        diagnostics["failure"] = Dict{String,Any}(
            "exception_type" => string(nameof(typeof(error))),
            "reason" => reason,
        )
        diagnostics["phase"] = "failed"
        return S4VariantOutcome(
            _s4_unknown_core(variant, route_name, reason, ledger),
            diagnostics,
        )
    end
end
