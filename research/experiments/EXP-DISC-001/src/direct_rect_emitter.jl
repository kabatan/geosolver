module StageNextDirectRectEmitter

export EmitterArm,
    DIRECT_RECT_EMIT,
    RECT_ORBIT_BREADTH,
    EmitterStatus,
    EMITTER_COMPLETE,
    INAPPLICABLE_BOX,
    INAPPLICABLE_RESOLUTION,
    INAPPLICABLE_INITIAL_STENCIL,
    ScreeningObservation,
    EmitterProposal,
    EmitterDiagnostics,
    EmitterResult,
    SCREEN_CALLBACK_CAP,
    phi_score,
    emit_points

@enum EmitterArm begin
    DIRECT_RECT_EMIT
    RECT_ORBIT_BREADTH
end

@enum EmitterStatus begin
    EMITTER_COMPLETE
    INAPPLICABLE_BOX
    INAPPLICABLE_RESOLUTION
    INAPPLICABLE_INITIAL_STENCIL
end

const SCREEN_CALLBACK_CAP = 48
const _GEOMETRY_CALLBACK_CAP = SCREEN_CALLBACK_CAP - 1
const DIRECT_EPSILON = 1.0e-4

"""Typed truth-blind result of one charged screening callback."""
struct ScreeningObservation
    scaled_residual::Vector{Float64}
    canonical_valid::Bool
end

ScreeningObservation(residual::AbstractVector; canonical_valid::Bool=true) =
    ScreeningObservation(Float64[residual...], canonical_valid)

"""One requested point. Every instance is a later local-solver proposal."""
struct EmitterProposal
    evaluation_ordinal::Int
    point::Vector{Float64}
    normalized_point::Vector{Float64}
    phi::Float64
    canonical_valid::Bool
    callback_failed::Bool
    duplicate_of::Union{Nothing,Int}
end

"""Only capability and accounting facts; no target, case, or branch identity."""
struct EmitterDiagnostics
    arm::EmitterArm
    status::EmitterStatus
    dimension::Int
    normalization_well_resolved::Bool
    initial_stencil_size::Int
    screening_callbacks::Int
    callback_cap::Int
    completed_splits::Int
    rectangle_count::Int
    invalid_count::Int
    callback_failure_count::Int
    duplicate_count::Int
    symmetry_tie_fallback::Bool
    symmetry_orbits_serviced::Int
    center_fill_count::Int
    all_requests_serviced::Bool
    hard_discard_count::Int
    external_result_used::Bool
end

struct EmitterResult
    proposals::Vector{EmitterProposal}
    diagnostics::EmitterDiagnostics
end

struct _Box
    lower::Vector{Float64}
    upper::Vector{Float64}
    midpoint::Vector{Float64}
    half_range::Vector{Float64}
end

mutable struct _Rectangle
    center::Vector{Float64}
    depths::Vector{Int}
    phi::Float64
    birth_ordinal::Int
end

mutable struct _ScreenState{F}
    screen!::F
    box::_Box
    proposals::Vector{EmitterProposal}
    seen::Dict{Any,Int}
    completed_splits::Int
    next_birth::Int
    evaluation_limit::Int
    symmetry_tie_fallback::Bool
    symmetry_orbits_serviced::Int
    center_fill_count::Int
end

function _spacing(value::Float64)
    gaps = Float64[]
    previous, following = prevfloat(value), nextfloat(value)
    isfinite(previous) && push!(gaps, abs(value - previous))
    isfinite(following) && push!(gaps, abs(following - value))
    return isempty(gaps) ? Inf : maximum(gaps)
end

function _box(lower::AbstractVector, upper::AbstractVector)
    length(lower) == length(upper) && !isempty(lower) || return nothing, INAPPLICABLE_BOX
    lo, hi = try
        Float64[lower...], Float64[upper...]
    catch
        return nothing, INAPPLICABLE_BOX
    end
    all(isfinite, lo) && all(isfinite, hi) && all(lo .< hi) ||
        return nothing, INAPPLICABLE_BOX
    midpoint = lo ./ 2 .+ hi ./ 2
    half_range = hi ./ 2 .- lo ./ 2
    all(isfinite, midpoint) && all(isfinite, half_range) && all(half_range .> 0) ||
        return nothing, INAPPLICABLE_BOX
    resolved = all(eachindex(midpoint)) do index
        maximum((_spacing(lo[index]), _spacing(midpoint[index]), _spacing(hi[index]))) <=
            8eps(Float64) * half_range[index]
    end
    resolved || return nothing, INAPPLICABLE_RESOLUTION
    return _Box(lo, hi, midpoint, half_range), EMITTER_COMPLETE
end

"""
Stable row-permutation-invariant implementation of the frozen bounded score.

Finite valid residuals map to `[0, 1)` even when their mathematical two-norm
would overflow Float64. Invalid, empty, or nonfinite observations map to `1`.
"""
function phi_score(observation::ScreeningObservation)
    observation.canonical_valid || return 1.0, false
    residual = observation.scaled_residual
    isempty(residual) && return 1.0, false
    all(isfinite, residual) || return 1.0, false
    magnitudes = sort!(abs.(residual))
    scale = magnitudes[end]
    scale == 0.0 && return 0.0, true
    normalized_squares = sort!((magnitudes ./ scale) .^ 2)
    shape = sqrt(sum(normalized_squares))
    if scale <= inv(shape)
        rho = scale * shape
        return rho / (1.0 + rho), true
    end
    inverse_rho = inv(scale) / shape
    score = 1.0 - inverse_rho / (1.0 + inverse_rho)
    return min(prevfloat(1.0), score), true
end

_point_key(point::Vector{Float64}) = Tuple(reinterpret(UInt64, value) for value in point)

function _physical_point(box::_Box, normalized::Vector{Float64})
    point = Float64[
        clamp(muladd(box.half_range[index], normalized[index], box.midpoint[index]),
            box.lower[index], box.upper[index]) for index in eachindex(normalized)
    ]
    return point
end

function _evaluate!(state::_ScreenState, normalized::Vector{Float64})
    length(state.proposals) < state.evaluation_limit || return nothing
    requested = _physical_point(state.box, normalized)
    key = _point_key(requested)
    duplicate_of = get(state.seen, key, nothing)
    raw, callback_failed = try
        state.screen!(copy(requested)), false
    catch
        nothing, true
    end
    observation = raw isa ScreeningObservation ? raw : ScreeningObservation(Float64[]; canonical_valid=false)
    score, valid = phi_score(observation)
    ordinal = length(state.proposals) + 1
    push!(state.proposals, EmitterProposal(
        ordinal, requested, copy(normalized), score, valid, callback_failed || !(raw isa ScreeningObservation), duplicate_of,
    ))
    get!(state.seen, key, ordinal)
    return state.proposals[end]
end

function _diameter(rectangle::_Rectangle)
    squared = sort!(Float64[3.0^(-2depth) for depth in rectangle.depths])
    return sqrt(sum(squared))
end

_longest_dimensions(rectangle::_Rectangle) =
    findall(==(minimum(rectangle.depths)), rectangle.depths)

function _split_rectangle!(state::_ScreenState, rectangle::_Rectangle)
    dimensions = _longest_dimensions(rectangle)
    length(state.proposals) + 2length(dimensions) <= state.evaluation_limit || return false
    samples = Dict{Int,Tuple{EmitterProposal,EmitterProposal}}()
    for dimension in dimensions
        offset = 2.0 * 3.0^(-(rectangle.depths[dimension] + 1))
        negative, positive = copy(rectangle.center), copy(rectangle.center)
        negative[dimension] -= offset
        positive[dimension] += offset
        left = _evaluate!(state, negative)
        left === nothing && return false
        right = _evaluate!(state, positive)
        right === nothing && return false
        samples[dimension] = (left, right)
    end
    division_scores = Float64[
        min(samples[dimension][1].phi, samples[dimension][2].phi) for dimension in dimensions
    ]
    length(unique(division_scores)) == length(division_scores) || return :symmetry_tie
    division_order = sort(dimensions; by=dimension -> (
        min(samples[dimension][1].phi, samples[dimension][2].phi),
    ))
    current_depths = copy(rectangle.depths)
    side_rectangles = _Rectangle[]
    for dimension in division_order
        current_depths[dimension] += 1
        for sample in samples[dimension]
            push!(side_rectangles, _Rectangle(
                copy(sample.normalized_point), copy(current_depths), sample.phi, state.next_birth,
            ))
            state.next_birth += 1
        end
    end
    rectangle.depths = current_depths
    state.completed_splits += 1
    return side_rectangles
end

function _potentially_optimal(rectangles::Vector{_Rectangle})
    diameters = _diameter.(rectangles)
    best = minimum(rectangle.phi for rectangle in rectangles)
    selected = Int[]
    for candidate in eachindex(rectangles)
        diameter, score = diameters[candidate], rectangles[candidate].phi
        any(index -> diameters[index] == diameter && rectangles[index].phi < score, eachindex(rectangles)) && continue
        lower, upper = 0.0, Inf
        for other in eachindex(rectangles)
            other == candidate && continue
            other_diameter, other_score = diameters[other], rectangles[other].phi
            if other_diameter < diameter
                lower = max(lower, (score - other_score) / (diameter - other_diameter))
            elseif other_diameter > diameter
                upper = min(upper, (other_score - score) / (other_diameter - diameter))
            elseif other_score < score
                upper = -Inf
            end
        end
        target = best - DIRECT_EPSILON * abs(best)
        lower = max(lower, (score - target) / diameter, 0.0)
        upper > 0.0 && lower <= upper && push!(selected, candidate)
    end
    if isempty(selected)
        fallback_keys = [(rectangle.phi, -_diameter(rectangle)) for rectangle in rectangles]
        fallback_key = minimum(fallback_keys)
        append!(selected, findall(==(fallback_key), fallback_keys))
    end
    sort!(selected; by=index -> (-_diameter(rectangles[index]), rectangles[index].phi, rectangles[index].birth_ordinal))
    return rectangles[selected]
end

function _selection_has_exact_tie(rectangles::Vector{_Rectangle})
    keys = [(_diameter(rectangle), rectangle.phi) for rectangle in rectangles]
    return length(unique(keys)) != length(keys)
end

function _axis_combinations(dimension::Int, support::Int)
    result, current = Vector{Vector{Int}}(), Int[]
    function visit(first_axis::Int)
        if length(current) == support
            push!(result, copy(current))
            return
        end
        remaining = support - length(current)
        for axis in first_axis:(dimension - remaining + 1)
            push!(current, axis)
            visit(axis + 1)
            pop!(current)
        end
    end
    visit(1)
    return result
end

function _orbit_size(dimension::Int, support::Int)
    return binomial(big(dimension), support) * big(2)^support
end

function _service_orbit!(state::_ScreenState, level::Int, support::Int)
    dimension = length(state.box.lower)
    cardinality = _orbit_size(dimension, support)
    cardinality <= state.evaluation_limit - length(state.proposals) || return false
    radius = 2.0 * 3.0^(-level)
    for axes in _axis_combinations(dimension, support)
        for sign_mask in 0:(2^support - 1)
            point = zeros(Float64, dimension)
            for (position, axis) in enumerate(axes)
                point[axis] = ((sign_mask >> (position - 1)) & 1 == 0 ? -radius : radius)
            end
            _evaluate!(state, point)::EmitterProposal
        end
    end
    state.symmetry_orbits_serviced += 1
    return true
end

function _service_orbit_breadth!(state::_ScreenState; tie_fallback::Bool)
    state.symmetry_tie_fallback |= tie_fallback
    state.evaluation_limit = _GEOMETRY_CALLBACK_CAP
    dimension = length(state.box.lower)
    level, first_support = 1, 2
    while _orbit_size(dimension, 1) <= state.evaluation_limit - length(state.proposals)
        for support in first_support:dimension
            _service_orbit!(state, level, support) || break
        end
        level += 1
        first_support = 1
    end
    _service_center_fill!(state)
    return nothing
end

function _service_center_fill!(state::_ScreenState)
    state.evaluation_limit = SCREEN_CALLBACK_CAP
    dimension = length(state.box.lower)
    center = zeros(Float64, dimension)
    while length(state.proposals) < SCREEN_CALLBACK_CAP
        _evaluate!(state, center)::EmitterProposal
        state.center_fill_count += 1
    end
    return nothing
end

function _diagnostics(
    arm::EmitterArm,
    status::EmitterStatus,
    dimension::Int,
    resolved::Bool,
    proposals::Vector{EmitterProposal},
    completed_splits::Int,
    rectangle_count::Int,
    tie_fallback::Bool,
    orbit_count::Int,
    center_fill_count::Int,
)
    return EmitterDiagnostics(
        arm,
        status,
        dimension,
        resolved,
        1 + 2dimension,
        length(proposals),
        SCREEN_CALLBACK_CAP,
        completed_splits,
        rectangle_count,
        count(!proposal.canonical_valid for proposal in proposals),
        count(proposal.callback_failed for proposal in proposals),
        count(proposal.duplicate_of !== nothing for proposal in proposals),
        tie_fallback,
        orbit_count,
        center_fill_count,
        status != EMITTER_COMPLETE || length(proposals) == SCREEN_CALLBACK_CAP,
        0,
        false,
    )
end

"""
Emit exactly 48 charged rectangle-screen points when applicable.

The callback sees physical-box points and must return `ScreeningObservation`.
Callback failures and malformed returns become typed invalid evidence at `phi=1`;
their requested points remain in `result.proposals`. No proposal is accepted as an
answer, merged, deduplicated, or suppressed by this module.
"""
function emit_points(
    screen!::F,
    lower::AbstractVector,
    upper::AbstractVector;
    arm::EmitterArm=DIRECT_RECT_EMIT,
) where {F}
    dimension = length(lower)
    box, status = _box(lower, upper)
    if status != EMITTER_COMPLETE
        diagnostics = _diagnostics(arm, status, dimension, false, EmitterProposal[], 0, 0, false, 0, 0)
        return EmitterResult(EmitterProposal[], diagnostics)
    end
    if 1 + 2dimension > SCREEN_CALLBACK_CAP
        diagnostics = _diagnostics(
            arm, INAPPLICABLE_INITIAL_STENCIL, dimension, true, EmitterProposal[], 0, 0, false, 0, 0,
        )
        return EmitterResult(EmitterProposal[], diagnostics)
    end

    state = _ScreenState(
        screen!, box, EmitterProposal[], Dict{Any,Int}(), 0, 2, _GEOMETRY_CALLBACK_CAP, false, 0, 0,
    )
    center = zeros(Float64, dimension)
    center_proposal = _evaluate!(state, center)::EmitterProposal
    if arm == RECT_ORBIT_BREADTH
        _service_orbit!(state, 1, 1) || error("applicable initial orbit must fit the cap")
        _service_orbit_breadth!(state; tie_fallback=false)
        diagnostics = _diagnostics(
            arm, EMITTER_COMPLETE, dimension, true, state.proposals, 0, 0,
            state.symmetry_tie_fallback, state.symmetry_orbits_serviced,
            state.center_fill_count,
        )
        return EmitterResult(state.proposals, diagnostics)
    end

    rectangles = [_Rectangle(center, zeros(Int, dimension), center_proposal.phi, 1)]
    initial = _split_rectangle!(state, rectangles[1])
    initial === false && error("applicable initial stencil must fit the frozen callback cap")
    state.symmetry_orbits_serviced = 1
    if initial === :symmetry_tie
        _service_orbit_breadth!(state; tie_fallback=true)
        diagnostics = _diagnostics(
            arm, EMITTER_COMPLETE, dimension, true, state.proposals, state.completed_splits,
            length(rectangles), state.symmetry_tie_fallback, state.symmetry_orbits_serviced,
            state.center_fill_count,
        )
        return EmitterResult(state.proposals, diagnostics)
    end
    append!(rectangles, initial)

    geometry_exhausted = false
    while length(state.proposals) < _GEOMETRY_CALLBACK_CAP
        selected = _potentially_optimal(rectangles)
        selection_tie = _selection_has_exact_tie(selected)
        if selection_tie
            _service_orbit_breadth!(state; tie_fallback=true)
            break
        end
        for rectangle in selected
            children = _split_rectangle!(state, rectangle)
            if children === false
                geometry_exhausted = true
                break
            end
            if children === :symmetry_tie
                _service_orbit_breadth!(state; tie_fallback=true)
                break
            end
            append!(rectangles, children)
        end
        geometry_exhausted && break
    end
    # Whole ternary stencils consume an odd total after the initial center.
    # Any even-cap remainder is therefore closed with explicit center
    # re-observations. They remain duplicate proposals and never update state.
    length(state.proposals) < SCREEN_CALLBACK_CAP && _service_center_fill!(state)
    diagnostics = _diagnostics(
        arm, EMITTER_COMPLETE, dimension, true, state.proposals, state.completed_splits,
        length(rectangles), state.symmetry_tie_fallback, state.symmetry_orbits_serviced,
        state.center_fill_count,
    )
    return EmitterResult(state.proposals, diagnostics)
end

end
