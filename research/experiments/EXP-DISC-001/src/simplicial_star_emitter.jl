module SimplicialStarEmitter

export SIMPLICIAL_STAR_EMIT,
    SIMPLICIAL_UNGUIDED,
    SimplicialEmitterArm,
    SimplicialObservation,
    SimplicialProposal,
    SimplicialFallbackRequest,
    SimplicialEmitterReport,
    SimplicialEmitterPlan,
    SimplicialEmitterPair,
    plan_simplicial_pair

@enum SimplicialEmitterArm begin
    SIMPLICIAL_UNGUIDED
    SIMPLICIAL_STAR_EMIT
end

const EMITTER_SLOTS = 48
const MAX_BASE_VERTICES = 48
const MAX_SIMPLICES = 256
const MAX_INCIDENCES = 1_024

struct SimplicialObservation
    scaled_residual::Vector{Float64}
    branch_token::Any
    canonical_valid::Bool
end

SimplicialObservation(residual; branch_token=nothing, canonical_valid=true) =
    SimplicialObservation(Float64[residual...], branch_token, canonical_valid)

struct SimplicialProposal
    point::Vector{Float64}
    score::Float64
    canonical_valid::Bool
    callback_failed::Bool
    kind::Symbol
end

struct SimplicialFallbackRequest
    slot::Int
    reason::Symbol
end

struct SimplicialEmitterReport
    arm::SimplicialEmitterArm
    applicable::Bool
    reason::Symbol
    dimension::Int
    base_vertex_count::Int
    simplex_count::Int
    combinatorial_minimum_count::Int
    refinement_count::Int
    fallback_requests::Int
    logical_prescores::Int
    logical_screening_callbacks::Int
    shared_base_evaluation::Bool
    all_prescores_returned::Bool
    answer_authority::Bool
    homology_authority::Bool
    completeness_authority::Bool
end

struct SimplicialEmitterPlan
    proposals::Vector{SimplicialProposal}
    fallbacks::Vector{SimplicialFallbackRequest}
    report::SimplicialEmitterReport
end

struct SimplicialEmitterPair
    unguided::SimplicialEmitterPlan
    star::SimplicialEmitterPlan
end

struct _NormalizedBox
    lower::Vector{Float64}
    midpoint::Vector{Float64}
    upper::Vector{Float64}
    half_range::Vector{Float64}
end

_branchless(token) = token === nothing || ismissing(token)

function _same_branch(left, right)
    try
        value = isequal(left, right)
        return value isa Bool && value
    catch
        return false
    end
end

function _spacing(value::Float64)
    gaps = Float64[]
    isfinite(prevfloat(value)) && push!(gaps, abs(value - prevfloat(value)))
    isfinite(nextfloat(value)) && push!(gaps, abs(nextfloat(value) - value))
    return isempty(gaps) ? Inf : maximum(gaps)
end

function _normalized_box(lower, upper)
    length(lower) == length(upper) || return nothing, :dimension_mismatch
    isempty(lower) && return nothing, :empty_dimension
    lo, hi = try
        Float64[lower...], Float64[upper...]
    catch
        return nothing, :invalid_finite_box
    end
    all(isfinite, lo) && all(isfinite, hi) && all(lo .< hi) ||
        return nothing, :invalid_finite_box
    midpoint = lo ./ 2 .+ hi ./ 2
    half_range = hi ./ 2 .- lo ./ 2
    all(isfinite, midpoint) && all(isfinite, half_range) && all(half_range .> 0) ||
        return nothing, :invalid_finite_box
    resolved = all(eachindex(lo)) do index
        maximum((_spacing(lo[index]), _spacing(midpoint[index]), _spacing(hi[index]))) <=
            8eps(Float64) * half_range[index]
    end
    resolved || return nothing, :normalization_underresolved
    return _NormalizedBox(lo, midpoint, hi, half_range), :applicable
end

function _corner_count(dimension)
    corners = 1
    for _ in 1:dimension
        corners *= 2
        corners + 1 <= MAX_BASE_VERTICES || return nothing
    end
    return corners
end

function _base_vertices(dimension, corners)
    points = Vector{Vector{Float64}}()
    for mask in 0:(corners - 1)
        push!(points, [iszero(mask & (1 << (axis - 1))) ? -1.0 : 1.0
                       for axis in 1:dimension])
    end
    push!(points, zeros(Float64, dimension))
    return points
end

function _physical_point(box::_NormalizedBox, normalized)
    point = Vector{Float64}(undef, length(normalized))
    for index in eachindex(normalized)
        u = normalized[index]
        point[index] = u == -1 ? box.lower[index] : u == 1 ? box.upper[index] :
            clamp(muladd(box.half_range[index], u, box.midpoint[index]),
                box.lower[index], box.upper[index])
    end
    return point
end

function _bounded_score(observation::SimplicialObservation, branch_capability)
    valid = observation.canonical_valid &&
        (!branch_capability || !_branchless(observation.branch_token)) &&
        !isempty(observation.scaled_residual) && all(isfinite, observation.scaled_residual)
    valid || return 1.0, false
    magnitudes = sort!(abs.(observation.scaled_residual))
    scale = magnitudes[end]
    scale == 0 && return 0.0, true
    shape = sqrt(sum(sort!((magnitudes ./ scale) .^ 2)))
    if scale <= inv(shape)
        rho = scale * shape
        return rho / (1 + rho), true
    end
    inverse_rho = inv(scale) / shape
    score = 1 - inverse_rho / (1 + inverse_rho)
    return min(prevfloat(1.0), score), true
end

function _observe(evaluate, box, normalized, kind, branch_capability)
    point = _physical_point(box, normalized)
    raw, callback_failed = try
        evaluate(copy(point)), false
    catch
        nothing, true
    end
    callback_failed |= !(raw isa SimplicialObservation)
    observation = raw isa SimplicialObservation ? raw :
        SimplicialObservation(Float64[]; canonical_valid=false)
    score, valid = _bounded_score(observation, branch_capability)
    return SimplicialProposal(point, score, valid, callback_failed, kind), observation
end

"""
Symmetric SHGO-style star cover on the `2^d` cube corners plus center.

Each simplex contains the center, one corner and all but one adjacent corner.
The cover, rather than a selected diagonal triangulation, is invariant as a set under
signed coordinate permutations. It supplies only proposal geometry, not homology.
"""
function _simplices(dimension, corners)
    center = corners + 1
    unique_simplices = Set{Tuple}()
    for mask in 0:(corners - 1), omitted in 1:dimension
        vertices = Int[center, mask + 1]
        for axis in 1:dimension
            axis == omitted && continue
            push!(vertices, (mask ⊻ (1 << (axis - 1))) + 1)
        end
        push!(unique_simplices, Tuple(sort!(unique(vertices))))
    end
    simplices = collect(unique_simplices)
    sort!(simplices)
    return simplices
end

function _adjacency(vertex_count, simplices)
    adjacency = falses(vertex_count, vertex_count)
    for simplex in simplices, left in simplex, right in simplex
        left == right || (adjacency[left, right] = true)
    end
    return adjacency
end

function _minimum_vertices(observations, proposals, adjacency, branch_capability)
    minima = Int[]
    for index in eachindex(proposals)
        proposals[index].canonical_valid || continue
        compatible = Int[]
        for neighbor in axes(adjacency, 2)
            adjacency[index, neighbor] || continue
            if !branch_capability ||
               (!_branchless(observations[index].branch_token) &&
                !_branchless(observations[neighbor].branch_token) &&
                _same_branch(observations[index].branch_token,
                    observations[neighbor].branch_token))
                push!(compatible, neighbor)
            end
        end
        all(proposals[index].score <= proposals[neighbor].score for neighbor in compatible) &&
            push!(minima, index)
    end
    return minima
end

function _squared_distance(left, right)
    terms = sort!((Float64[left...] .- Float64[right...]) .^ 2)
    return sum(terms)
end

function _incidences(points, simplices)
    records = NamedTuple[]
    for simplex in simplices
        barycenter = zeros(Float64, length(first(points)))
        for vertex in simplex
            barycenter .+= points[vertex]
        end
        barycenter ./= length(simplex)
        edge_signature = sort([
            _squared_distance(points[left], points[right]) for left in simplex for
            right in simplex if left < right
        ])
        simplex_points = Tuple(sort([Tuple(points[vertex]) for vertex in simplex]))
        for anchor in simplex
            point = (points[anchor] .+ barycenter) ./ 2
            geometry_key = (
                Tuple(sort(abs.(point))),
                Tuple(sort(abs.(points[anchor]))),
                Tuple(edge_signature),
                _squared_distance(points[anchor], barycenter),
            )
            fifo_key = (geometry_key, Tuple(point), Tuple(points[anchor]), simplex_points)
            push!(records, (; anchor, simplex, point, geometry_key, fifo_key))
        end
    end
    return records
end

function _invariant_shells(records)
    ordered = sort(copy(records); by=record -> (record.geometry_key, record.fifo_key))
    shells = Vector{Vector{NamedTuple}}()
    for record in ordered
        if isempty(shells) || !isequal(last(last(shells)).geometry_key, record.geometry_key)
            push!(shells, NamedTuple[record])
        else
            push!(last(shells), record)
        end
    end
    return shells
end

function _guided_shells(records, minima)
    per_minimum = [_invariant_shells(
        [record for record in records if record.anchor == minimum],
    ) for minimum in minima]
    rounds = Vector{Vector{NamedTuple}}()
    for round in 1:maximum(length, per_minimum; init=0)
        combined = NamedTuple[]
        for minimum_shells in per_minimum
            round <= length(minimum_shells) && append!(combined, minimum_shells[round])
        end
        append!(rounds, _invariant_shells(combined))
    end
    return rounds
end

function _complete_shell_prefix(shells, capacity)
    output = NamedTuple[]
    for shell in shells
        length(output) + length(shell) <= capacity || break
        append!(output, shell)
    end
    return output
end

function _report(arm, applicable, reason, dimension, base_count, simplex_count,
    minimum_count, refinement_count, proposal_count)
    return SimplicialEmitterReport(
        arm, applicable, reason, dimension, base_count, simplex_count, minimum_count,
        refinement_count, EMITTER_SLOTS - proposal_count, proposal_count,
        EMITTER_SLOTS, applicable, true, false, false, false,
    )
end

function _inapplicable_pair(reason, dimension)
    fallbacks = [SimplicialFallbackRequest(slot, reason) for slot in 1:EMITTER_SLOTS]
    plans = [SimplicialEmitterPlan(SimplicialProposal[], copy(fallbacks),
        _report(arm, false, reason, dimension, 0, 0, 0, 0, 0))
        for arm in (SIMPLICIAL_UNGUIDED, SIMPLICIAL_STAR_EMIT)]
    return SimplicialEmitterPair(plans...)
end

function _plan_with_simplices(evaluate, box, normalized_points, simplices;
    branch_capability)
    base_proposals, observations = SimplicialProposal[], SimplicialObservation[]
    for point in normalized_points
        proposal, observation = _observe(evaluate, box, point, :base, branch_capability)
        push!(base_proposals, proposal)
        push!(observations, observation)
    end
    adjacency = _adjacency(length(normalized_points), simplices)
    minima = _minimum_vertices(observations, base_proposals, adjacency, branch_capability)
    records = _incidences(normalized_points, simplices)
    capacity = EMITTER_SLOTS - length(base_proposals)
    guided_records = _complete_shell_prefix(_guided_shells(records, minima), capacity)
    control_records = _complete_shell_prefix(_invariant_shells(records), capacity)
    selected = Dict(
        SIMPLICIAL_UNGUIDED => control_records,
        SIMPLICIAL_STAR_EMIT => guided_records,
    )
    plans = SimplicialEmitterPlan[]
    for arm in (SIMPLICIAL_UNGUIDED, SIMPLICIAL_STAR_EMIT)
        proposals = [SimplicialProposal(
            copy(proposal.point), proposal.score, proposal.canonical_valid,
            proposal.callback_failed, proposal.kind,
        ) for proposal in base_proposals]
        kind = arm == SIMPLICIAL_UNGUIDED ? :unguided : :star
        refinement_count = length(selected[arm])
        for record in selected[arm]
            proposal, _ = _observe(evaluate, box, record.point, kind, branch_capability)
            push!(proposals, proposal)
        end
        fallbacks = [SimplicialFallbackRequest(slot, :iid_fill)
                     for slot in (length(proposals) + 1):EMITTER_SLOTS]
        push!(plans, SimplicialEmitterPlan(proposals, fallbacks,
            _report(arm, true, :applicable, length(box.lower), length(base_proposals),
                length(simplices), length(minima), refinement_count, length(proposals))))
    end
    return SimplicialEmitterPair(plans...)
end

"""
    plan_simplicial_pair(evaluate, lower, upper; branch_capability)

Create paired `SIMPLICIAL-UNGUIDED` and `SIMPLICIAL-STAR-EMIT` proposal plans.
Every emitter callback result is returned as a proposal. Unused slots are returned as typed
IID fallback requests. Base observations are physically shared once by this paired API,
but each arm is charged all 48 logical screening callbacks after its typed fallbacks are
fulfilled. The result has no answer, homology, or completeness authority.
"""
function plan_simplicial_pair(evaluate, lower, upper; branch_capability::Bool)
    box, reason = _normalized_box(lower, upper)
    box === nothing && return _inapplicable_pair(reason, length(lower))
    dimension = length(box.lower)
    corners = _corner_count(dimension)
    corners === nothing && return _inapplicable_pair(:base_vertex_cap, dimension)
    points = _base_vertices(dimension, corners)
    simplices = _simplices(dimension, corners)
    length(simplices) <= MAX_SIMPLICES ||
        return _inapplicable_pair(:simplex_memory_cap, dimension)
    sum(length, simplices) <= MAX_INCIDENCES ||
        return _inapplicable_pair(:incidence_memory_cap, dimension)
    return _plan_with_simplices(evaluate, box, points, simplices; branch_capability)
end

end
