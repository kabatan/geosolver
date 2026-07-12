module StageBWeakGeometry

using LinearAlgebra

export WEAK_FD_STEP,
    WEAK_RADII,
    WEAK_MAX_LAUNCH_SLOTS,
    WEAK_MAX_GEOMETRY_SLOTS,
    WEAK_MAX_COMPARISONS,
    WEAK_ANCHOR_RESIDUAL_MAX,
    WeakPointEvaluation,
    WeakGapEvidence,
    WeakGeometryEvidence,
    WeakProbeQuartet,
    WeakLaunchSlot,
    WeakGeometryResult,
    BoxNormalization,
    box_normalization,
    to_normalized,
    to_physical,
    counter_gaussian,
    paired_probe_directions,
    weak_geometry_plan

# Julia 1.12 Float64 cbrt(eps(Float64)), frozen as bytes rather than recomputed.
const WEAK_FD_STEP = 0x1.965fea53d6e3dp-18
const WEAK_RADII = (0x1.0p-20, 0x1.0p-14, 0x1.0p-8, 0x1.0p-2)
const WEAK_MAX_LAUNCH_SLOTS = 64
const WEAK_IID_CADENCE = 4
# Per-arm geometry starts: 24 quartets times the two signs in one arm.
const WEAK_MAX_GEOMETRY_SLOTS = 48
const WEAK_MAX_COMPARISONS = 24
const WEAK_SUBSPACE_DRAWS = 6
const WEAK_RATIO_MAX = 0.1
const WEAK_GAP_ETA_MIN = 4.0
const WEAK_STRONG_ETA_MIN = 8.0
const WEAK_PROJECTOR_DISTANCE_MAX = 0.1
# Scaled residual 2-norm; unlike an infinity norm this is row-orthogonally invariant.
const WEAK_ANCHOR_RESIDUAL_MAX = 1.0e-12
const WEAK_FD_GAMMA = 8eps(Float64) / (1 - 8eps(Float64))

"""Affine map between a finite physical box and `u in [-1,1]^n`."""
struct BoxNormalization
    lower::Vector{Float64}
    upper::Vector{Float64}
    midpoint::Vector{Float64}
    half_range::Vector{Float64}
end

function box_normalization(lower::AbstractVector, upper::AbstractVector)
    length(lower) == length(upper) || throw(DimensionMismatch("box bounds"))
    isempty(lower) && throw(ArgumentError("box must have positive dimension"))
    lo = Float64[lower...]
    hi = Float64[upper...]
    all(isfinite, lo) && all(isfinite, hi) ||
        throw(ArgumentError("weak geometry requires finite bounds"))
    all(lo .< hi) || throw(ArgumentError("every lower bound must be below its upper bound"))
    midpoint = lo ./ 2 .+ hi ./ 2
    half_range = hi ./ 2 .- lo ./ 2
    all(isfinite, midpoint) && all(isfinite, half_range) && all(half_range .> 0) ||
        throw(ArgumentError("box normalization is not finite"))
    return BoxNormalization(lo, hi, midpoint, half_range)
end

function to_normalized(box::BoxNormalization, point::AbstractVector)
    length(point) == length(box.lower) || throw(DimensionMismatch("box point"))
    physical = Float64[point...]
    all(isfinite, physical) || throw(ArgumentError("point must be finite"))
    return (physical .- box.midpoint) ./ box.half_range
end

function to_physical(box::BoxNormalization, normalized::AbstractVector)
    length(normalized) == length(box.lower) || throw(DimensionMismatch("normalized point"))
    unit = Float64[normalized...]
    all(isfinite, unit) || throw(ArgumentError("normalized point must be finite"))
    return box.midpoint .+ box.half_range .* unit
end

"""
Truth-blind black-box observation used by Stage B. `residual` is the canonical
scaled relation residual. The three identities and their strictly positive
margins expose only public branch/guard/domain semantics.
"""
struct WeakPointEvaluation{B,G,D}
    residual::Vector{Float64}
    branch_identity::B
    guard_identity::G
    domain_identity::D
    branch_margin::Float64
    guard_margin::Float64
    domain_margin::Float64
    valid::Bool
end

function WeakPointEvaluation(
    residual::AbstractVector;
    branch_identity=:default_branch,
    guard_identity=:default_guard,
    domain_identity=:default_domain,
    branch_margin::Real=1.0,
    guard_margin::Real=1.0,
    domain_margin::Real=1.0,
    valid::Bool=true,
)
    return WeakPointEvaluation(
        Float64[residual...],
        branch_identity,
        guard_identity,
        domain_identity,
        Float64(branch_margin),
        Float64(guard_margin),
        Float64(domain_margin),
        valid,
    )
end

struct WeakGapEvidence
    strong_dimension::Int
    weak_dimension::Int
    coarse_singular_values::Vector{Float64}
    fine_singular_values::Vector{Float64}
    largest_weak::Float64
    smallest_strong::Float64
    raw_cross_gap::Float64
    weak_strong_ratio::Float64
    coarse_projector::Matrix{Float64}
    fine_projector::Matrix{Float64}
end

struct WeakGeometryEvidence
    coarse_jacobian::Matrix{Float64}
    fine_jacobian::Matrix{Float64}
    jacobian_disagreement::Float64
    rounding_envelope::Float64
    eta::Float64
    gap::WeakGapEvidence
    projector_distance::Float64
    average_projector::Matrix{Float64}
    weak_basis::Matrix{Float64}
end

"""One jointly valid weak/isotropic comparison, in fixed point order `w+,w-,i+,i-`."""
struct WeakProbeQuartet
    comparison_index::Int
    direction_draw::Int
    radius::Float64
    weak_direction::Vector{Float64}
    isotropic_direction::Vector{Float64}
    normalized_points::Matrix{Float64}
    physical_points::Matrix{Float64}
end

"""
A paired-arm scheduler hint. Geometry `point_ordinal` is 1 for plus and 2 for
minus; the weak arm reads that quartet column and the isotropic arm reads
`point_ordinal + 2`. IID and continuation slots use zero ordinals.
"""
struct WeakLaunchSlot
    slot::Int
    lane::Symbol
    comparison_index::Int
    sign::Int
    point_ordinal::Int
end

"""
Typed outcome. `:applicable` is an empirical proposal decision, never a root,
rank, isolation, or answer certificate.
"""
struct WeakGeometryResult
    status::Symbol
    reason::Symbol
    evidence::Union{Nothing,WeakGeometryEvidence}
    quartets::Vector{WeakProbeQuartet}
    launch_slots::Vector{WeakLaunchSlot}
    attempted_comparisons::Int
    rejected_comparisons::Int
    callback_count::Int
end

_inapplicable(reason::Symbol; callbacks::Int=0, evidence=nothing,
    attempted::Int=0, rejected::Int=0) = WeakGeometryResult(
    :inapplicable,
    reason,
    evidence,
    WeakProbeQuartet[],
    WeakLaunchSlot[],
    attempted,
    rejected,
    callbacks,
)

_inside_open_box(unit::AbstractVector) =
    all(value -> isfinite(value) && -1.0 < value < 1.0, unit)

function _intrinsically_valid(observation::WeakPointEvaluation, residual_dimension::Int)
    length(observation.residual) == residual_dimension || return false
    all(isfinite, observation.residual) || return false
    observation.valid || return false
    margins = (
        observation.branch_margin,
        observation.guard_margin,
        observation.domain_margin,
    )
    return all(value -> isfinite(value) && value > 0.0, margins)
end

function _same_semantics(observation::WeakPointEvaluation, anchor::WeakPointEvaluation)
    return try
        isequal(observation.branch_identity, anchor.branch_identity) &&
        isequal(observation.guard_identity, anchor.guard_identity) &&
        isequal(observation.domain_identity, anchor.domain_identity)
    catch
        false
    end
end

function _observe(evaluate, box, unit, anchor, residual_dimension)
    _inside_open_box(unit) || return nothing
    observation = try
        evaluate(to_physical(box, unit))
    catch
        return nothing
    end
    observation isa WeakPointEvaluation || return nothing
    _intrinsically_valid(observation, residual_dimension) || return nothing
    anchor === nothing || _same_semantics(observation, anchor) || return nothing
    return observation
end

function _joint_gap_evidence(
    coarse::Matrix{Float64},
    fine::Matrix{Float64},
    eta::Float64,
)
    coarse_decomposition = svd(coarse; full=false)
    fine_decomposition = svd(fine; full=false)
    coarse_values = Vector{Float64}(coarse_decomposition.S)
    fine_values = Vector{Float64}(fine_decomposition.S)
    n = size(coarse, 2)
    candidates = NamedTuple[]
    for strong_dimension in 1:(n - 1)
        weak_dimension = n - strong_dimension
        raw_smallest_strong = min(
            coarse_values[strong_dimension],
            fine_values[strong_dimension],
        )
        raw_largest_weak = max(
            coarse_values[strong_dimension + 1],
            fine_values[strong_dimension + 1],
        )
        raw_cross_gap = raw_smallest_strong - raw_largest_weak
        smallest_strong = raw_smallest_strong - eta
        largest_weak = raw_largest_weak + eta
        smallest_strong > 0.0 || continue
        ratio = largest_weak / smallest_strong
        ratio <= WEAK_RATIO_MAX || continue
        raw_cross_gap > WEAK_GAP_ETA_MIN * eta || continue
        raw_smallest_strong > WEAK_STRONG_ETA_MIN * eta || continue
        push!(candidates, (;
            strong_dimension,
            weak_dimension,
            smallest_strong,
            largest_weak,
            raw_cross_gap,
            ratio,
        ))
    end
    isempty(candidates) && return nothing
    # Minimize the padded weak/strong ratio; exact ties prefer smaller weak k.
    winner = first(sort(candidates; by=candidate -> (
        candidate.ratio,
        candidate.weak_dimension,
    )))
    weak_columns = (winner.strong_dimension + 1):n
    coarse_basis = Matrix{Float64}(coarse_decomposition.V[:, weak_columns])
    fine_basis = Matrix{Float64}(fine_decomposition.V[:, weak_columns])
    return WeakGapEvidence(
        winner.strong_dimension,
        winner.weak_dimension,
        coarse_values,
        fine_values,
        winner.largest_weak,
        winner.smallest_strong,
        winner.raw_cross_gap,
        winner.ratio,
        coarse_basis * transpose(coarse_basis),
        fine_basis * transpose(fine_basis),
    )
end

function _average_eigenspace(first::Matrix{Float64}, second::Matrix{Float64}, k::Int)
    averaged = Symmetric((first + second) ./ 2)
    decomposition = eigen(averaged)
    indices = (length(decomposition.values) - k + 1):length(decomposition.values)
    basis = Matrix{Float64}(decomposition.vectors[:, indices])
    projector = basis * transpose(basis)
    return projector, basis
end

function _splitmix64(value::UInt64)
    word = value + 0x9e3779b97f4a7c15
    word = xor(word, word >> 30) * 0xbf58476d1ce4e5b9
    word = xor(word, word >> 27) * 0x94d049bb133111eb
    return xor(word, word >> 31)
end

function _counter_uniform(seed::UInt64, counter::UInt64)
    word = _splitmix64(xor(seed, counter * 0xd2b74407b1ce6e93))
    return (Float64(word >> 11) + 0.5) * 0x1.0p-53
end

"""Deterministic counter-derived standard-normal vector (Box-Muller)."""
function counter_gaussian(seed::Integer, draw::Integer, dimension::Integer)
    0 <= seed <= typemax(UInt64) || throw(ArgumentError("seed must fit UInt64"))
    draw > 0 || throw(ArgumentError("draw must be positive"))
    dimension > 0 || throw(ArgumentError("dimension must be positive"))
    result = Vector{Float64}(undef, dimension)
    pair_count = cld(dimension, 2)
    base = UInt64(draw - 1) * UInt64(2pair_count)
    output = 1
    for pair in 1:pair_count
        first = _counter_uniform(UInt64(seed), base + UInt64(2pair - 1))
        second = _counter_uniform(UInt64(seed), base + UInt64(2pair))
        radius = sqrt(-2.0 * log(first))
        sine, cosine = sincospi(2.0 * second)
        result[output] = radius * cosine
        output += 1
        if output <= dimension
            result[output] = radius * sine
            output += 1
        end
    end
    return result
end

"""
Return paired unit directions from one isotropic vector. The map is exactly
orthogonally covariant when both `projector` and `z` are transported; the
counter distribution is isotropic, so randomized replicas are distributionally
covariant without a representation-specific route.
"""
function paired_probe_directions(projector::AbstractMatrix, z::AbstractVector)
    n = length(z)
    size(projector) == (n, n) || throw(DimensionMismatch("weak projector"))
    vector = Float64[z...]
    all(isfinite, vector) || throw(ArgumentError("counter vector must be finite"))
    isotropic_norm = norm(vector)
    isfinite(isotropic_norm) && isotropic_norm > 0 || return nothing
    weak = Matrix{Float64}(projector) * vector
    weak_norm = norm(weak)
    weak_norm > sqrt(eps(Float64)) * isotropic_norm || return nothing
    return (weak=weak ./ weak_norm, isotropic=vector ./ isotropic_norm)
end

function _canonical_line(basis::Matrix{Float64})
    direction = copy(view(basis, :, 1))
    pivot = argmax(abs.(direction))
    direction[pivot] < 0 && (direction .*= -1)
    return direction ./ norm(direction)
end

function _joint_quartet(
    evaluate,
    box,
    anchor,
    residual_dimension,
    endpoint_unit,
    weak_direction,
    isotropic_direction,
    radius,
    comparison_index,
    direction_draw,
)
    normalized = hcat(
        endpoint_unit .+ radius .* weak_direction,
        endpoint_unit .- radius .* weak_direction,
        endpoint_unit .+ radius .* isotropic_direction,
        endpoint_unit .- radius .* isotropic_direction,
    )
    physical = hcat((to_physical(box, view(normalized, :, column)) for
                     column in axes(normalized, 2))...)
    all(column -> _inside_open_box(view(normalized, :, column)), axes(normalized, 2)) ||
        return nothing, 0
    jointly_valid = true
    for column in axes(normalized, 2)
        observation = try
            evaluate(Vector{Float64}(view(physical, :, column)))
        catch
            nothing
        end
        point_valid = observation isa WeakPointEvaluation &&
                      _intrinsically_valid(observation, residual_dimension) &&
                      _same_semantics(observation, anchor)
        jointly_valid &= point_valid
    end
    jointly_valid || return nothing, 4
    return WeakProbeQuartet(
        comparison_index,
        direction_draw,
        radius,
        Vector{Float64}(weak_direction),
        Vector{Float64}(isotropic_direction),
        Matrix{Float64}(normalized),
        Matrix{Float64}(physical),
    ), 4
end

function _launch_schedule(comparison_count::Int)
    0 <= comparison_count <= WEAK_MAX_COMPARISONS ||
        throw(ArgumentError("geometry comparison count exceeds frozen maximum"))
    result = WeakLaunchSlot[]
    geometry_point = 1
    geometry_point_count = 2comparison_count
    geometry_point_count <= WEAK_MAX_GEOMETRY_SLOTS ||
        error("per-arm geometry-start bound drifted")
    for slot in 1:WEAK_MAX_LAUNCH_SLOTS
        if mod(slot - 1, WEAK_IID_CADENCE) == 0
            push!(result, WeakLaunchSlot(slot, :iid, 0, 0, 0))
        elseif geometry_point <= geometry_point_count
            comparison = cld(geometry_point, 2)
            point_ordinal = isodd(geometry_point) ? 1 : 2
            sign = point_ordinal == 1 ? 1 : -1
            push!(
                result,
                WeakLaunchSlot(slot, :geometry, comparison, sign, point_ordinal),
            )
            geometry_point += 1
        else
            push!(result, WeakLaunchSlot(slot, :continuation, 0, 0, 0))
        end
    end
    geometry_point == geometry_point_count + 1 ||
        error("frozen launch bound cannot service all geometry starts")
    return result
end

"""
Build a bounded Stage-B weak-geometry proposal plan from one canonical-valid
endpoint. Probe-derived endpoints are statically inapplicable, preventing
recursive emission. All decisions depend only on numerical/public semantics.
"""
function weak_geometry_plan(
    evaluate,
    endpoint::AbstractVector,
    lower::AbstractVector,
    upper::AbstractVector;
    seed::Integer,
    derived_from_probe::Bool=false,
)
    derived_from_probe && return _inapplicable(:probe_derived_endpoint)
    0 <= seed <= typemax(UInt64) || return _inapplicable(:invalid_seed)
    n = length(endpoint)
    n >= 2 || return _inapplicable(:dimension_below_two)
    length(lower) == n && length(upper) == n || return _inapplicable(:box_dimension_mismatch)
    box = try
        box_normalization(lower, upper)
    catch
        return _inapplicable(:finite_box_required)
    end
    endpoint_unit = try
        to_normalized(box, endpoint)
    catch
        return _inapplicable(:invalid_endpoint)
    end
    _inside_open_box(endpoint_unit) || return _inapplicable(:endpoint_not_strictly_inside_box)

    callback_count = 1
    anchor = try
        evaluate(Float64[endpoint...])
    catch
        return _inapplicable(:endpoint_evaluation_failed; callbacks=callback_count)
    end
    anchor isa WeakPointEvaluation || return _inapplicable(:malformed_endpoint_evaluation;
        callbacks=callback_count)
    residual_dimension = length(anchor.residual)
    residual_dimension >= n || return _inapplicable(:underdetermined;
        callbacks=callback_count)
    _intrinsically_valid(anchor, residual_dimension) || return _inapplicable(
        :invalid_canonical_endpoint; callbacks=callback_count,
    )
    # The 2-norm keeps anchor eligibility invariant under residual-row
    # permutations and orthogonal transforms.
    norm(anchor.residual) <= WEAK_ANCHOR_RESIDUAL_MAX || return _inapplicable(
        :endpoint_residual_too_large; callbacks=callback_count,
    )

    coarse = zeros(Float64, residual_dimension, n)
    fine = zeros(Float64, residual_dimension, n)
    rounding_squared = 0.0
    for (destination, step) in ((coarse, WEAK_FD_STEP), (fine, WEAK_FD_STEP / 2))
        for column in 1:n
            offset = zeros(Float64, n)
            offset[column] = step
            plus_unit = endpoint_unit .+ offset
            minus_unit = endpoint_unit .- offset
            _inside_open_box(plus_unit) && _inside_open_box(minus_unit) || return _inapplicable(
                :finite_difference_semantics_changed; callbacks=callback_count,
            )
            plus = _observe(
                evaluate,
                box,
                plus_unit,
                anchor,
                residual_dimension,
            )
            callback_count += 1
            plus === nothing && return _inapplicable(
                :finite_difference_semantics_changed; callbacks=callback_count,
            )
            minus = _observe(
                evaluate,
                box,
                minus_unit,
                anchor,
                residual_dimension,
            )
            callback_count += 1
            minus === nothing && return _inapplicable(
                :finite_difference_semantics_changed; callbacks=callback_count,
            )
            destination[:, column] .=
                (plus.residual .- minus.residual) ./ (2.0 * step)
            # A conservative row-orthogonally invariant form of the E1
            # componentwise roundoff envelope.
            rounding_column = WEAK_FD_GAMMA *
                (norm(plus.residual) + norm(minus.residual)) / (2.0 * step)
            isfinite(rounding_column) || return _inapplicable(
                :nonfinite_jacobian_uncertainty; callbacks=callback_count,
            )
            rounding_squared += rounding_column^2
        end
    end

    all(isfinite, coarse) && all(isfinite, fine) || return _inapplicable(
        :nonfinite_jacobian; callbacks=callback_count,
    )
    jacobian_disagreement = opnorm(fine - coarse, 2)
    rounding_envelope = sqrt(rounding_squared)
    eta = jacobian_disagreement + rounding_envelope
    isfinite(eta) || return _inapplicable(:nonfinite_jacobian_disagreement;
        callbacks=callback_count)
    gap = _joint_gap_evidence(coarse, fine, eta)
    gap === nothing && return _inapplicable(:no_stable_singular_gap;
        callbacks=callback_count)
    distance = opnorm(gap.coarse_projector - gap.fine_projector, 2)
    isfinite(distance) && distance <= WEAK_PROJECTOR_DISTANCE_MAX || return _inapplicable(
        :unstable_weak_projector; callbacks=callback_count,
    )
    weak_dimension = gap.weak_dimension
    average_projector, weak_basis = _average_eigenspace(
        gap.coarse_projector,
        gap.fine_projector,
        weak_dimension,
    )
    evidence = WeakGeometryEvidence(
        coarse,
        fine,
        jacobian_disagreement,
        rounding_envelope,
        eta,
        gap,
        distance,
        average_projector,
        weak_basis,
    )

    direction_draws = weak_dimension == 1 ? 1 : WEAK_SUBSPACE_DRAWS
    line_direction = weak_dimension == 1 ? _canonical_line(weak_basis) : Float64[]
    quartets = WeakProbeQuartet[]
    attempted = 0
    rejected = 0
    comparison_index = 0
    for draw in 1:direction_draws
        z = counter_gaussian(seed, draw, n)
        paired = if weak_dimension == 1
            z_norm = norm(z)
            isfinite(z_norm) && z_norm > 0 ?
                (weak=line_direction, isotropic=z ./ z_norm) : nothing
        else
            paired_probe_directions(average_projector, z)
        end
        for radius in WEAK_RADII
            attempted += 1
            if paired === nothing
                rejected += 1
                continue
            end
            weak_direction = weak_dimension == 1 ? line_direction : paired.weak
            comparison_index += 1
            quartet, probe_callbacks = _joint_quartet(
                evaluate,
                box,
                anchor,
                residual_dimension,
                endpoint_unit,
                weak_direction,
                paired.isotropic,
                radius,
                comparison_index,
                draw,
            )
            callback_count += probe_callbacks
            if quartet === nothing
                rejected += 1
                comparison_index -= 1
            else
                push!(quartets, quartet)
            end
        end
    end
    attempted <= WEAK_MAX_COMPARISONS || error("frozen comparison bound drifted")
    isempty(quartets) && return _inapplicable(
        :no_jointly_valid_probe_quartet;
        callbacks=callback_count,
        evidence,
        attempted,
        rejected,
    )
    schedule = _launch_schedule(length(quartets))
    return WeakGeometryResult(
        :applicable,
        :stable_weak_geometry,
        evidence,
        quartets,
        schedule,
        attempted,
        rejected,
        callback_count,
    )
end

end
