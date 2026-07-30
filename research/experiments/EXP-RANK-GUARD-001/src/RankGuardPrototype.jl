module RankGuardPrototype

using LinearAlgebra
using SHA

if !isdefined(@__MODULE__, :ExperimentLocal015)
    include(joinpath(@__DIR__, "..", "..", "EXP-LOCAL-015", "src", "ExperimentLocal015.jl"))
end

const LAB = ExperimentLocal015
const WEAK = LAB.WEAK

export GuardChart,
    ProposalBatch,
    WeakProposal,
    chart_to_physical,
    mechanism_hash,
    normalized_precision_ledger,
    physical_to_chart,
    weak_singular_proposals

const PROJECTOR_DISTANCE_MAX = 0.1
const WEAK_STRONG_RATIO_MAX = 0.1
const MIN_INTERIOR_FRACTION = 64eps(Float64)
const DEFAULT_RADIUS_FRACTIONS = (1.0, 0.25)

"""Finite strict-bound logit chart.  It has no answer/certificate authority."""
struct GuardChart
    lower::Vector{Float64}
    upper::Vector{Float64}

    function GuardChart(lower, upper)
        lo = Float64[lower...]
        hi = Float64[upper...]
        length(lo) == length(hi) || throw(DimensionMismatch("guard chart bounds"))
        !isempty(lo) || throw(ArgumentError("guard chart needs a positive dimension"))
        all(isfinite, lo) && all(isfinite, hi) && all(lo .< hi) || throw(
            ArgumentError("guard chart requires ordered finite bounds"),
        )
        return new(lo, hi)
    end
end

"""One truth-blind proposal; the canonical solver must still validate it."""
struct WeakProposal
    coordinates::Vector{Float64}
    parameter::Float64
    physical_radius::Float64
    residual_ratio::Float64
    charted::Bool
end

struct ProposalBatch
    status::Symbol
    reason::Symbol
    activated::Bool
    callbacks::Int
    proposals::Vector{WeakProposal}
    route::NamedTuple
end

"""Remove zero buckets so a requested no-op and no physical call agree."""
function normalized_precision_ledger(counts)
    normalized = Dict{String,Int}()
    for (tier, raw_count) in pairs(counts)
        count = Int(raw_count)
        count >= 0 || throw(ArgumentError("precision count cannot be negative"))
        count == 0 || (normalized[String(tier)] = count)
    end
    return normalized
end

function _clamped_fraction(value::Float64)
    return clamp(value, MIN_INTERIOR_FRACTION, 1.0 - MIN_INTERIOR_FRACTION)
end

function physical_to_chart(chart::GuardChart, point)
    x = Float64[point...]
    length(x) == length(chart.lower) || throw(DimensionMismatch("chart point"))
    all((chart.lower .< x) .& (x .< chart.upper)) || throw(
        ArgumentError("point must be strictly inside the guard chart"),
    )
    fraction = (x .- chart.lower) ./ (chart.upper .- chart.lower)
    return Float64[log(_clamped_fraction(value) / (1 - _clamped_fraction(value))) for value in fraction]
end

function _logistic(value::Float64)
    if value >= 0
        tail = exp(-value)
        return 1 / (1 + tail)
    end
    head = exp(value)
    return head / (1 + head)
end

function chart_to_physical(chart::GuardChart, coordinates)
    z = Float64[coordinates...]
    length(z) == length(chart.lower) || throw(DimensionMismatch("chart coordinates"))
    fraction = Float64[_clamped_fraction(_logistic(value)) for value in z]
    return chart.lower .+ (chart.upper .- chart.lower) .* fraction
end

function _canonical_line(direction)
    line = Float64[direction...]
    magnitude = norm(line, 2)
    isfinite(magnitude) && magnitude > sqrt(eps(Float64)) || return nothing
    line ./= magnitude
    pivot = argmax(abs.(line))
    signbit(line[pivot]) && (line .*= -1)
    return line
end

function _weak_direction(prefilter)
    n = length(prefilter.endpoint)
    size(prefilter.coarse_jacobian) == (n, n) || return nothing, :coarse_jacobian_unavailable
    size(prefilter.fine_jacobian) == (n, n) || return nothing, :fine_jacobian_unavailable
    coarse = svd(prefilter.coarse_jacobian; full=true)
    fine = svd(prefilter.fine_jacobian; full=true)
    coarse_line = _canonical_line(coarse.V[:, end])
    fine_line = _canonical_line(fine.V[:, end])
    coarse_line === nothing && return nothing, :coarse_weak_line_unavailable
    fine_line === nothing && return nothing, :fine_weak_line_unavailable
    projector_distance = opnorm(
        coarse_line * transpose(coarse_line) - fine_line * transpose(fine_line),
        2,
    )
    projector_distance <= PROJECTOR_DISTANCE_MAX || return nothing, :unstable_weak_projector
    values = Float64[fine.S...]
    length(values) >= 2 || return nothing, :dimension_below_two
    ratio = values[end - 1] > 0 ? values[end] / values[end - 1] : Inf
    triggered = prefilter.numerical_rank < n ||
                prefilter.condition_class == :above_trigger ||
                ratio <= WEAK_STRONG_RATIO_MAX
    triggered || return nothing, :weak_route_not_triggered
    return fine_line, :stable_weak_line
end

function _same_semantics(observation, anchor)
    return try
        isequal(observation.branch_identity, anchor.branch_identity) &&
        isequal(observation.guard_identity, anchor.guard_identity) &&
        isequal(observation.domain_identity, anchor.domain_identity)
    catch
        false
    end
end

function _valid_observation(observation, anchor)
    observation isa WEAK.RescueEvaluation || return false
    observation.valid || return false
    length(observation.residual) == length(anchor.residual) || return false
    all(isfinite, observation.residual) || return false
    all(value -> isfinite(value) && value > 0, (
        observation.branch_margin,
        observation.guard_margin,
        observation.domain_margin,
    )) || return false
    return _same_semantics(observation, anchor)
end

function _maximum_physical_radius(point, direction, lower, upper)
    radius = Inf
    for index in eachindex(point)
        component = direction[index]
        iszero(component) && continue
        positive = component > 0 ?
                   (upper[index] - point[index]) / component :
                   (point[index] - lower[index]) / -component
        negative = component > 0 ?
                   (point[index] - lower[index]) / component :
                   (upper[index] - point[index]) / -component
        radius = min(radius, positive, negative)
    end
    return radius
end

function _direct_pair(point, direction, radius)
    return point .+ radius .* direction, point .- radius .* direction
end

function _charted_pair(chart, point, direction, radius)
    z = physical_to_chart(chart, point)
    fraction = (point .- chart.lower) ./ (chart.upper .- chart.lower)
    derivative = (chart.upper .- chart.lower) .* fraction .* (1 .- fraction)
    all(derivative .> 0) || return nothing
    z_direction = _canonical_line(direction ./ derivative)
    z_direction === nothing && return nothing
    # Match the requested first-order physical displacement before mapping.
    physical_tangent = derivative .* z_direction
    tangent_norm = norm(physical_tangent, 2)
    isfinite(tangent_norm) && tangent_norm > 0 || return nothing
    z_radius = radius / tangent_norm
    return chart_to_physical(chart, z .+ z_radius .* z_direction),
           chart_to_physical(chart, z .- z_radius .* z_direction)
end

"""
Generate complete symmetric weak-line proposal pairs.

The evaluator is source-bound through `prefilter.weak_probe_context`; all calls
are charged before evaluation.  A failed or semantic-crossing pair emits
nothing, preserving the baseline lane and canonical verifier boundary.
"""
function weak_singular_proposals(
    fixture,
    prefilter;
    trust_radius::Real=0.25,
    guard_fraction::Real=0.25,
    radius_fractions=DEFAULT_RADIUS_FRACTIONS,
    charted::Bool=false,
    observe_callback=(precision_bits) -> nothing,
)
    prefilter.status == :ready || return ProposalBatch(
        :unknown, :shared_prefilter_unavailable, false, 0, WeakProposal[], (; charted),
    )
    anchor = prefilter.anchor
    anchor isa WEAK.RescueEvaluation || return ProposalBatch(
        :unknown, :shared_anchor_unavailable, false, 0, WeakProposal[], (; charted),
    )
    context = prefilter.weak_probe_context
    context isa LAB.SharedWeakProbeContext || return ProposalBatch(
        :unknown, :source_context_unavailable, false, 0, WeakProposal[], (; charted),
    )
    fixture.evaluate_float64 === context.evaluate_float64 || return ProposalBatch(
        :unknown, :source_context_mismatch, false, 0, WeakProposal[], (; charted),
    )
    direction, route_reason = _weak_direction(prefilter)
    direction === nothing && return ProposalBatch(
        :unknown, route_reason, false, 0, WeakProposal[], (; charted),
    )
    trust = Float64(trust_radius)
    guard = Float64(guard_fraction)
    isfinite(trust) && trust > 0 || throw(ArgumentError("trust radius must be positive"))
    isfinite(guard) && 0 < guard <= 1 || throw(ArgumentError("guard fraction must lie in (0,1]"))
    fractions = Float64[radius_fractions...]
    !isempty(fractions) && all(value -> isfinite(value) && 0 < value <= 1, fractions) ||
        throw(ArgumentError("radius fractions must lie in (0,1]"))

    point = copy(prefilter.endpoint)
    lower = context.box.lower
    upper = context.box.upper
    bound_radius = _maximum_physical_radius(point, direction, lower, upper)
    semantic_margin = min(
        anchor.branch_margin,
        anchor.guard_margin,
        anchor.domain_margin,
    )
    base_radius = min(trust, 0.5bound_radius, guard * semantic_margin)
    isfinite(base_radius) && base_radius > 0 || return ProposalBatch(
        :unknown, :no_strictly_interior_radius, true, 0, WeakProposal[], (; charted),
    )

    chart = charted ? GuardChart(lower, upper) : nothing
    callbacks = 0
    proposals = WeakProposal[]
    anchor_norm = max(norm(anchor.residual, Inf), floatmin(Float64))
    complete_pairs = 0
    semantic_rejections = 0
    for fraction in fractions
        radius = base_radius * fraction
        pair = charted ? _charted_pair(chart, point, direction, radius) :
                         _direct_pair(point, direction, radius)
        pair === nothing && continue
        observations = Any[]
        pair_valid = true
        for candidate in pair
            callbacks += 1
            observe_callback(53)
            raw = try
                context.evaluate_float64(copy(candidate))
            catch error
                error isa InterruptException && rethrow()
                nothing
            end
            observation = raw === nothing ? nothing : LAB._weak_observation(raw)
            push!(observations, observation)
            pair_valid &= _valid_observation(observation, anchor)
        end
        complete_pairs += 1
        if !pair_valid
            semantic_rejections += 1
            continue
        end
        for (sign, candidate, observation) in zip((1.0, -1.0), pair, observations)
            displacement = norm(candidate - point, 2)
            ratio = norm(observation.residual, Inf) / anchor_norm
            push!(proposals, WeakProposal(
                Float64[candidate...],
                sign * radius,
                displacement,
                ratio,
                charted,
            ))
        end
    end
    status = isempty(proposals) ? :unknown : :seeded
    reason = isempty(proposals) ? :no_semantics_valid_pair : :symmetric_weak_pair
    return ProposalBatch(
        status,
        reason,
        true,
        callbacks,
        proposals,
        (;
            charted,
            complete_pairs,
            semantic_rejections,
            weak_direction=Tuple(direction),
            base_radius,
            trust_radius=trust,
            guard_fraction=guard,
        ),
    )
end

function mechanism_hash()
    return bytes2hex(sha256(read(@__FILE__)))
end

end
