module StageCSoftTGOOrdering

export OrderingArm,
    FIFO_SCORED,
    RESIDUAL_ONLY,
    SOFT_TGO,
    OrderingCandidate,
    BranchOrderingDiagnostics,
    OrderingDiagnostics,
    OrderingResult,
    order_fixed_batch

@enum OrderingArm begin
    FIFO_SCORED
    RESIDUAL_ONLY
    SOFT_TGO
end

"""
One truth-blind member of a fixed rolling batch.

`scaled_residual` must be the canonical scaled relation residual.  The opaque
`branch_token` is used only for equality partitioning; its value, type name,
hash, and display representation never participate in routing.  `nothing` and
`missing` denote a branchless observation.
"""
struct OrderingCandidate
    source_ordinal::Int
    point::Vector{Float64}
    scaled_residual::Vector{Float64}
    branch_token::Any
    canonical_valid::Bool
end

function OrderingCandidate(
    source_ordinal::Integer,
    point::AbstractVector,
    scaled_residual::AbstractVector;
    branch_token=nothing,
    canonical_valid::Bool=true,
)
    return OrderingCandidate(
        Int(source_ordinal),
        Float64[point...],
        Float64[scaled_residual...],
        branch_token,
        canonical_valid,
    )
end

"""Truth-free diagnostics for one branch partition or the FIFO fallback group."""
struct BranchOrderingDiagnostics
    first_source_ordinal::Int
    member_count::Int
    fallback::Bool
    neighbor_k::Int
    local_minimum_source_ordinals::Vector{Int}
    neighborhood_source_ordinals::Vector{Int}
    neighborhood_sizes::Vector{Int}
end

"""Diagnostics contain counts and source ordinals, never branch identities or scores."""
struct OrderingDiagnostics
    arm::OrderingArm
    batch_size::Int
    dimension::Int
    branch_capability::Bool
    normalization_well_resolved::Bool
    scored_count::Int
    fallback_count::Int
    branch_partition_count::Int
    group_first_source_ordinals::Vector{Int}
    rounds::Int
    all_candidates_drained::Bool
    groups::Vector{BranchOrderingDiagnostics}
end

"""The only scheduling output is a permutation of input indices plus diagnostics."""
struct OrderingResult
    permutation::Vector{Int}
    diagnostics::OrderingDiagnostics
end

struct _BoxNormalization
    midpoint::Vector{Float64}
    half_range::Vector{Float64}
    well_resolved::Bool
end

struct _ScoredCandidate
    index::Int
    source_ordinal::Int
    normalized_point::Vector{Float64}
    residual_norm::Float64
    residual_dimension::Int
    branch_token::Any
end

mutable struct _Partition
    token::Any
    fallback::Bool
    members::Vector{Int}
end

struct _NoBranchCapability end
const NO_BRANCH_CAPABILITY = _NoBranchCapability()

function _box_normalization(lower::AbstractVector, upper::AbstractVector)
    length(lower) == length(upper) || throw(DimensionMismatch("box bounds"))
    isempty(lower) && throw(ArgumentError("box must have positive dimension"))
    lo = Float64[lower...]
    hi = Float64[upper...]
    all(isfinite, lo) && all(isfinite, hi) ||
        throw(ArgumentError("soft TGO ordering requires finite bounds"))
    all(lo .< hi) || throw(ArgumentError("every lower bound must be below its upper bound"))
    # This split form avoids the avoidable overflow in `(lo + hi) / 2`.
    midpoint = lo ./ 2 .+ hi ./ 2
    half_range = hi ./ 2 .- lo ./ 2
    all(isfinite, midpoint) && all(isfinite, half_range) && all(half_range .> 0) ||
        throw(ArgumentError("box normalization is not finite"))
    function spacing(value::Float64)
        gaps = Float64[]
        previous = prevfloat(value)
        following = nextfloat(value)
        isfinite(previous) && push!(gaps, abs(value - previous))
        isfinite(following) && push!(gaps, abs(following - value))
        return isempty(gaps) ? Inf : maximum(gaps)
    end
    # With rho = ulp(x)/half_range, one normalized coordinate carries O(rho)
    # representation error and its squared-distance contribution carries at
    # most about 4rho.  Requiring rho <= 8eps leaves at least half of the
    # frozen 128*d*eps distance envelope for normalization arithmetic.  A box
    # that fails this numerical applicability gate remains fully serviced in
    # FIFO order; residual/topograph evidence is simply not used.
    well_resolved = all(eachindex(midpoint)) do index
        worst_spacing = maximum((
            spacing(lo[index]),
            spacing(midpoint[index]),
            spacing(hi[index]),
        ))
        isfinite(worst_spacing) &&
            worst_spacing <= 8eps(Float64) * half_range[index]
    end
    return _BoxNormalization(midpoint, half_range, well_resolved)
end

function _normalized_point(box::_BoxNormalization, point::Vector{Float64}, dimension::Int)
    length(point) == dimension || return nothing
    all(isfinite, point) || return nothing
    unit = (point .- box.midpoint) ./ box.half_range
    all(isfinite, unit) || return nothing
    # Boundary points may be canonically valid, so this is a closed-box check.
    all(value -> -1.0 <= value <= 1.0, unit) || return nothing
    return unit
end

"""
Permutation-invariant Euclidean norm of a canonical scaled residual.

Sorting magnitudes before the scaled sum makes a residual-row permutation an
exactly identical computation, while the scale factor avoids overflow and
underflow.  This score is numerical evidence only; it is never answer authority.
"""
function _scaled_residual_norm(residual::Vector{Float64})
    isempty(residual) && return nothing
    all(isfinite, residual) || return nothing
    magnitudes = sort!(abs.(residual))
    scale = magnitudes[end]
    scale == 0.0 && return 0.0
    normalized_squares = sort!((magnitudes ./ scale) .^ 2)
    score = scale * sqrt(sum(normalized_squares))
    return isfinite(score) ? score : nothing
end

_branchless(token) = token === nothing || ismissing(token)

function _same_branch(left, right)
    # Tokens are deliberately opaque.  Equality is the sole public operation.
    # A malformed unknown-plugin token must not abort the finite batch.  If its
    # equality is not a total Bool operation, conservatively keep the two
    # observations in separate partitions; both remain serviced.
    value = try
        isequal(left, right)
    catch
        return false
    end
    return value isa Bool ? value : false
end

function _stable_squared_distance(left::Vector{Float64}, right::Vector{Float64})
    differences = abs.(left .- right)
    scale = maximum(differences; init=0.0)
    scale == 0.0 && return 0.0
    # Sorted nonnegative contributions make signed-coordinate permutations
    # bitwise invariant.  In normalized coordinates q is at most 4d.
    terms = sort!((differences ./ scale) .^ 2)
    return scale^2 * sum(terms)
end

"""
Conservative roundoff envelope for a squared normalized Euclidean distance.

For `q = sum_j (u_j-v_j)^2`, ordinary first-order accumulation error is
`O(d*eps*q)`.  The larger `128*d*eps*max(1,q)` envelope also covers subtraction,
normalization, and replica roundoff.  If the lower interval of a candidate
neighbor intersects the upper interval of the nominal kth neighbor, it is
included.  Consequently an equal-distance shell is never split by source order;
the neighborhood may contain more than k points, but never hard-discards one on
an unresolved distance tie.
"""
function _distance_envelope(distance_squared::Float64, dimension::Int)
    return 128eps(Float64) * max(1, dimension) * max(1.0, distance_squared)
end

function _neighbor_indices(
    position::Int,
    members::Vector{_ScoredCandidate},
    k::Int,
    dimension::Int,
)
    k == 0 && return Int[]
    distances = NamedTuple{(:position, :distance, :ordinal),Tuple{Int,Float64,Int}}[]
    origin = members[position]
    for other_position in eachindex(members)
        other_position == position && continue
        other = members[other_position]
        push!(distances, (;
            position=other_position,
            distance=_stable_squared_distance(origin.normalized_point, other.normalized_point),
            ordinal=other.source_ordinal,
        ))
    end
    sort!(distances; by=item -> (item.distance, item.ordinal))
    cutoff = distances[k].distance
    cutoff_upper = cutoff + _distance_envelope(cutoff, dimension)
    included = Int[]
    for item in distances
        lower = max(0.0, item.distance - _distance_envelope(item.distance, dimension))
        lower <= cutoff_upper && push!(included, item.position)
    end
    # Downstream residual ties use source ordinal, never distance iteration order.
    sort!(included; by=index -> members[index].source_ordinal)
    return included
end

"""
Roundoff envelope for one residual 2-norm.

The norm evaluation and an orthogonal residual replica each accumulate
`O(p*eps)` relative error for residual dimension p.  The frozen factor 128 is a
conservative allowance for both transforms and the scaled norm implementation.
The smallest subnormal floor keeps the interval representable at zero; ordinary
scale covariance holds away from the unavoidable IEEE underflow boundary.
"""
function _score_envelope(candidate::_ScoredCandidate)
    scale = max(candidate.residual_norm, floatmin(Float64))
    computed = 128.0 * max(1, candidate.residual_dimension) * eps(Float64) * scale
    return max(nextfloat(0.0), computed)
end

"""
Construct a transitive, replica-stable total preorder for one whole branch.

For score `s_i=||r_i||_2`, form `I_i=[s_i-e_i,s_i+e_i]`.  After sorting by
nominal `(s_i, source_ordinal)`, consecutive overlapping intervals are closed
transitively into connected components.  A score key is then
`(component_rank, source_ordinal)`.  This avoids a nontransitive pairwise
`isapprox` comparator and makes every downstream use share the same tie class.
"""
function _stable_score_ranks(members::Vector{_ScoredCandidate})
    count = length(members)
    count == 0 && return Int[]
    nominal_order = sortperm(eachindex(members); by=position -> (
        members[position].residual_norm,
        members[position].source_ordinal,
    ))
    ranks = zeros(Int, count)
    component_rank = 1
    first_position = nominal_order[1]
    first_score = members[first_position].residual_norm
    component_upper = min(
        floatmax(Float64),
        first_score + _score_envelope(members[first_position]),
    )
    ranks[first_position] = component_rank
    for position in @view nominal_order[2:end]
        candidate = members[position]
        envelope = _score_envelope(candidate)
        lower = max(0.0, candidate.residual_norm - envelope)
        upper = min(floatmax(Float64), candidate.residual_norm + envelope)
        if lower <= component_upper
            component_upper = max(component_upper, upper)
        else
            component_rank += 1
            component_upper = upper
        end
        ranks[position] = component_rank
    end
    return ranks
end

_score_key(candidate::_ScoredCandidate, stable_rank::Int) =
    (stable_rank, candidate.source_ordinal)

function _topograph_order(
    members::Vector{_ScoredCandidate},
    dimension::Int,
    stable_ranks::Vector{Int},
)
    count = length(members)
    length(stable_ranks) == count || throw(DimensionMismatch("stable score ranks"))
    k = min(count - 1, 2dimension)
    neighborhoods = Vector{Vector{Int}}(undef, count)
    local_minima = falses(count)
    for position in eachindex(members)
        neighbors = _neighbor_indices(position, members, k, dimension)
        neighborhoods[position] = neighbors
        candidate_key = _score_key(members[position], stable_ranks[position])
        # With c_i the branch-wide interval-component rank and o_i the source
        # ordinal, the soft-TGO set is
        #   M = {i : (c_i,o_i) <= (c_j,o_j) for every j in N_k(i)}.
        # M is only advanced in the permutation; its complement remains in the
        # same finite batch and is subsequently drained.
        local_minima[position] = all(
            _score_key(members[neighbor], stable_ranks[neighbor]) >= candidate_key
            for neighbor in neighbors
        )
    end

    minima = findall(local_minima)
    remainder = findall(!, local_minima)
    sort!(minima; by=index -> _score_key(members[index], stable_ranks[index]))
    sort!(remainder; by=index -> _score_key(members[index], stable_ranks[index]))
    order = vcat(minima, remainder)
    return (; order, k, neighborhoods, minima)
end

function _round_robin(local_orders::Vector{Vector{Int}})
    output = Int[]
    maximum_length = maximum(length, local_orders; init=0)
    for round in 1:maximum_length
        for order in local_orders
            round <= length(order) && push!(output, order[round])
        end
    end
    return output, maximum_length
end

"""
    order_fixed_batch(candidates, lower, upper; arm=SOFT_TGO, branch_capability)

Return a truth-blind permutation for one finite rolling batch.

* `FIFO_SCORED` is the preregistered source-order control.
* `RESIDUAL_ONLY` sorts within each canonical-valid branch by scaled residual
  2-norm.
* `SOFT_TGO` advances k-neighborhood topograph minima before the residual order,
  with `k=min(m-1,2d)` in each branch.

The latter two arms never compare scores between branches.  Branch partitions,
plus one FIFO invalid/branchless partition when needed, are ordered by their
first source ordinal and drained by deterministic round-robin.  No candidate is
discarded, merged, or suppressed.

Scale/orthogonal covariance refers to replicas for which both boxes pass the
frozen normalization-resolution gate `max_ulp(lo,mid,hi)/half_range <= 8eps`.
Injectivity alone is insufficient: even distinct points can have their metric
geometry distorted by cancellation in a large-offset, narrow Float64 box.

`branch_capability` is deliberately required.  When it is `false`, absence of a
branch token is valid and all otherwise eligible observations form one branch
partition.  When it is `true`, an observation without its required token goes
to the serviced FIFO fallback group.  This separates a case-level absence of
branch semantics from a malformed observation without inspecting case identity.
"""
function order_fixed_batch(
    candidates::AbstractVector{<:OrderingCandidate},
    lower::AbstractVector,
    upper::AbstractVector;
    arm::OrderingArm=SOFT_TGO,
    branch_capability::Bool,
)
    box = _box_normalization(lower, upper)
    dimension = length(box.midpoint)
    batch_size = length(candidates)

    ordinals = [candidate.source_ordinal for candidate in candidates]
    all(ordinal -> ordinal > 0, ordinals) ||
        throw(ArgumentError("source ordinals must be positive"))
    length(unique(ordinals)) == batch_size ||
        throw(ArgumentError("source ordinals must be unique within a batch"))
    source_order = sortperm(ordinals)

    scored = _ScoredCandidate[]
    fallback_indices = Int[]
    for index in source_order
        candidate = candidates[index]
        point = _normalized_point(box, candidate.point, dimension)
        score = _scaled_residual_norm(candidate.scaled_residual)
        branch_present = !branch_capability || !_branchless(candidate.branch_token)
        eligible = box.well_resolved && candidate.canonical_valid && branch_present &&
            point !== nothing &&
            score !== nothing
        if eligible
            push!(scored, _ScoredCandidate(
                index,
                candidate.source_ordinal,
                point,
                score,
                length(candidate.scaled_residual),
                branch_capability ? candidate.branch_token : NO_BRANCH_CAPABILITY,
            ))
        else
            push!(fallback_indices, index)
        end
    end

    branch_partitions = _Partition[]
    for scored_position in eachindex(scored)
        item = scored[scored_position]
        partition_position = findfirst(
            partition -> _same_branch(partition.token, item.branch_token),
            branch_partitions,
        )
        if partition_position === nothing
            push!(branch_partitions, _Partition(item.branch_token, false, [scored_position]))
        else
            push!(branch_partitions[partition_position].members, scored_position)
        end
    end

    partitions = copy(branch_partitions)
    isempty(fallback_indices) || push!(partitions, _Partition(nothing, true, fallback_indices))
    first_ordinal(partition::_Partition) = partition.fallback ?
        candidates[partition.members[1]].source_ordinal :
        scored[partition.members[1]].source_ordinal
    sort!(partitions; by=first_ordinal)

    diagnostics_by_partition = BranchOrderingDiagnostics[]
    local_orders = Vector{Vector{Int}}()
    for partition in partitions
        if partition.fallback
            order = sort(copy(partition.members); by=index -> candidates[index].source_ordinal)
            push!(local_orders, order)
            push!(diagnostics_by_partition, BranchOrderingDiagnostics(
                first_ordinal(partition),
                length(order),
                true,
                0,
                Int[],
                [candidates[index].source_ordinal for index in order],
                zeros(Int, length(order)),
            ))
            continue
        end

        members = scored[partition.members]
        stable_ranks = arm == FIFO_SCORED ? Int[] : _stable_score_ranks(members)
        topology = arm == SOFT_TGO ?
            _topograph_order(members, dimension, stable_ranks) : nothing
        local_positions = if arm == FIFO_SCORED
            sortperm([member.source_ordinal for member in members])
        elseif arm == RESIDUAL_ONLY
            sortperm(eachindex(members); by=index ->
                _score_key(members[index], stable_ranks[index]))
        else
            topology.order
        end
        push!(local_orders, [members[position].index for position in local_positions])
        source_positions = sortperm([member.source_ordinal for member in members])
        push!(diagnostics_by_partition, BranchOrderingDiagnostics(
            first_ordinal(partition),
            length(members),
            false,
            topology === nothing ? 0 : topology.k,
            topology === nothing ? Int[] :
                sort([members[position].source_ordinal for position in topology.minima]),
            [members[position].source_ordinal for position in source_positions],
            topology === nothing ? zeros(Int, length(members)) :
                [length(topology.neighborhoods[position]) for position in source_positions],
        ))
    end

    permutation, rounds = if arm == FIFO_SCORED
        # The FIFO control is intentionally global; branch partitioning is still
        # diagnosed but cannot perturb its preregistered source-order schedule.
        (source_order, batch_size == 0 ? 0 : 1)
    else
        _round_robin(local_orders)
    end

    drained = length(permutation) == batch_size &&
        sort(permutation) == collect(1:batch_size)
    drained || error("internal ordering error: finite batch was not drained")
    diagnostics = OrderingDiagnostics(
        arm,
        batch_size,
        dimension,
        branch_capability,
        box.well_resolved,
        length(scored),
        length(fallback_indices),
        length(branch_partitions),
        [group.first_source_ordinal for group in diagnostics_by_partition],
        rounds,
        drained,
        diagnostics_by_partition,
    )
    return OrderingResult(permutation, diagnostics)
end

end # module StageCSoftTGOOrdering
