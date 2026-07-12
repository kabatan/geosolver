module WeakBracketRescue

using LinearAlgebra

export BRACKET_RADII,
    CPQR_FD_STEP,
    CPQRDiagnostic,
    CPQRReservation,
    BracketProbeResult,
    NormalizedBox,
    RankProjectorEvidence,
    RefinementSeed,
    RescueEvaluation,
    WeakBracketRescueResult,
    acquire_cpqr_rank_evidence,
    reserve_cpqr_diagnostic,
    symmetric_bracket_probe,
    weak_bracket_rescue

# Frozen before any EXP-LOCAL-015 outcomes.  The FD step is Julia 1.12's
# Float64 cbrt(eps(Float64)); the probe radii span twenty binary orders.
const CPQR_FD_STEP = 0x1.965fea53d6e3dp-18
const BRACKET_RADII = (0x1.0p-20, 0x1.0p-14, 0x1.0p-8, 0x1.0p-2)
const PROJECTOR_DISTANCE_MAX = 0.1
const WEAK_STRONG_RATIO_MAX = 0.1
const GAP_ETA_MULTIPLIER = 4.0
const STRONG_ETA_MULTIPLIER = 8.0
const CPQR_ETA_MULTIPLIER = 8.0
const SIGN_ROUNDOFF_MULTIPLIER = 64.0
const FD_ROUNDOFF_GAMMA = 8eps(Float64) / (1 - 8eps(Float64))

"""A finite box whose coordinates are already normalized."""
struct NormalizedBox
    lower::Vector{Float64}
    upper::Vector{Float64}

    function NormalizedBox(lower::AbstractVector, upper::AbstractVector)
        length(lower) == length(upper) || throw(DimensionMismatch("normalized box"))
        isempty(lower) && throw(ArgumentError("normalized box must have positive dimension"))
        lo = Float64[lower...]
        hi = Float64[upper...]
        all(isfinite, lo) && all(isfinite, hi) ||
            throw(ArgumentError("normalized box must be finite"))
        all(lo .< hi) || throw(ArgumentError("normalized lower bound must be below upper"))
        new(lo, hi)
    end
end

NormalizedBox(dimension::Integer) = dimension > 0 ?
    NormalizedBox(fill(-1.0, dimension), fill(1.0, dimension)) :
    throw(ArgumentError("dimension must be positive"))

"""
Truth-blind observation.  `residual` is the scaled canonical residual.  The
identities and positive margins are public branch/guard/domain semantics, not
Gold, target, case, family, or primitive metadata.
"""
struct RescueEvaluation{B,G,D}
    residual::Vector{Float64}
    branch_identity::B
    guard_identity::G
    domain_identity::D
    branch_margin::Float64
    guard_margin::Float64
    domain_margin::Float64
    valid::Bool
end

function RescueEvaluation(
    residual::AbstractVector;
    branch_identity=:default_branch,
    guard_identity=:default_guard,
    domain_identity=:default_domain,
    branch_margin::Real=1.0,
    guard_margin::Real=1.0,
    domain_margin::Real=1.0,
    valid::Bool=true,
)
    return RescueEvaluation(
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

struct CPQRReservation
    status::Symbol
    reason::Symbol
    dimension::Int
    remaining_callbacks::Int
    required_callbacks::Int
    reserved_callbacks::Int
end

"""Reserve the complete `h`/`h/2`, plus/minus stencil: exactly `4n` calls."""
function reserve_cpqr_diagnostic(dimension::Integer, remaining_callbacks::Integer)
    n = Int(dimension)
    remaining = Int(remaining_callbacks)
    if n < 2
        return CPQRReservation(:unknown, :dimension_below_two, n, remaining, 0, 0)
    end
    required = 4n
    if remaining < 0
        return CPQRReservation(:unknown, :invalid_callback_budget, n, remaining, required, 0)
    elseif remaining < required
        return CPQRReservation(
            :unknown,
            :insufficient_cpqr_reserve,
            n,
            remaining,
            required,
            0,
        )
    end
    return CPQRReservation(:reserved, :complete_h_h2_stencil, n, remaining, required, required)
end

"""
Numerically stable rank-one left/right weak-projector evidence.  This is an
empirical trigger only; it is not an isolation, existence, or answer proof.
"""
struct RankProjectorEvidence
    dimension::Int
    coarse_rank::Int
    fine_rank::Int
    weak_dimension::Int
    coarse_singular_values::Vector{Float64}
    fine_singular_values::Vector{Float64}
    eta::Float64
    smallest_strong::Float64
    largest_weak::Float64
    weak_strong_ratio::Float64
    coarse_right_projector::Matrix{Float64}
    fine_right_projector::Matrix{Float64}
    coarse_left_projector::Matrix{Float64}
    fine_left_projector::Matrix{Float64}
    right_projector_distance::Float64
    left_projector_distance::Float64
    average_right_projector::Matrix{Float64}
    average_left_projector::Matrix{Float64}
end

struct CPQRDiagnostic
    status::Symbol
    reason::Symbol
    reservation::CPQRReservation
    callback_count::Int
    step::Float64
    coarse_jacobian::Matrix{Float64}
    fine_jacobian::Matrix{Float64}
    coarse_cpqr_diagonal::Vector{Float64}
    fine_cpqr_diagonal::Vector{Float64}
    cpqr_threshold::Float64
    evidence::Union{Nothing,RankProjectorEvidence}
end

function _empty_diagnostic(
    status::Symbol,
    reason::Symbol,
    reservation::CPQRReservation,
    callbacks::Integer,
    step::Real,
    dimension::Integer;
    coarse=zeros(Float64, 0, 0),
    fine=zeros(Float64, 0, 0),
    coarse_diagonal=Float64[],
    fine_diagonal=Float64[],
    threshold=NaN,
)
    return CPQRDiagnostic(
        status,
        reason,
        reservation,
        Int(callbacks),
        Float64(step),
        Matrix{Float64}(coarse),
        Matrix{Float64}(fine),
        Float64[coarse_diagonal...],
        Float64[fine_diagonal...],
        Float64(threshold),
        nothing,
    )
end

function _inside_open_box(box::NormalizedBox, point::AbstractVector)
    length(point) == length(box.lower) || return false
    return all(index -> begin
        value = point[index]
        isfinite(value) && box.lower[index] < value < box.upper[index]
    end, eachindex(point))
end

function _intrinsically_valid(observation::RescueEvaluation, residual_dimension::Int)
    length(observation.residual) == residual_dimension || return false
    observation.valid || return false
    all(isfinite, observation.residual) || return false
    return all(value -> isfinite(value) && value > 0.0, (
        observation.branch_margin,
        observation.guard_margin,
        observation.domain_margin,
    ))
end

function _same_semantics(observation::RescueEvaluation, anchor::RescueEvaluation)
    return try
        isequal(observation.branch_identity, anchor.branch_identity) &&
        isequal(observation.guard_identity, anchor.guard_identity) &&
        isequal(observation.domain_identity, anchor.domain_identity)
    catch
        false
    end
end

function _evaluate_once(evaluate, point, charge_callback)
    charge_callback()
    value = try
        evaluate(copy(point))
    catch error
        error isa InterruptException && rethrow()
        return nothing, :evaluation_failed
    end
    value isa RescueEvaluation || return nothing, :malformed_evaluation
    return value, :ok
end

function _average_rank_one_projector(first::AbstractMatrix, second::AbstractMatrix)
    decomposition = eigen(Symmetric((Matrix{Float64}(first) + Matrix{Float64}(second)) ./ 2))
    direction = Vector{Float64}(decomposition.vectors[:, end])
    direction ./= norm(direction)
    projector = direction * transpose(direction)
    return projector
end

function _cpqr_diagonal(matrix::AbstractMatrix)
    factor = qr(Matrix{Float64}(matrix), ColumnNorm())
    triangular = Matrix{Float64}(factor.R)
    count = min(size(triangular)...)
    return Float64[abs(triangular[index, index]) for index in 1:count]
end

"""
Return the orthogonally invariant SVD gap/projector trigger.  CPQR diagonals
are deliberately absent: they remain useful diagnostic telemetry, but a
threshold-near variable rotation must not change applicability.
"""
function _invariant_rank_evidence(
    coarse::AbstractMatrix{Float64},
    fine::AbstractMatrix{Float64},
    eta::Float64,
)
    size(coarse) == size(fine) || return (evidence=nothing, reason=:jacobian_shape_mismatch)
    n = size(coarse, 2)
    size(coarse) == (n, n) && n >= 2 ||
        return (evidence=nothing, reason=:square_jacobian_dimension_required)
    all(isfinite, coarse) && all(isfinite, fine) && isfinite(eta) && eta >= 0 ||
        return (evidence=nothing, reason=:invalid_invariant_rank_inputs)

    coarse_svd = svd(Matrix{Float64}(coarse); full=true)
    fine_svd = svd(Matrix{Float64}(fine); full=true)
    coarse_values = Float64[coarse_svd.S...]
    fine_values = Float64[fine_svd.S...]
    raw_smallest_strong = min(coarse_values[n - 1], fine_values[n - 1])
    raw_largest_weak = max(coarse_values[n], fine_values[n])
    smallest_strong = raw_smallest_strong - eta
    largest_weak = raw_largest_weak + eta
    raw_gap = raw_smallest_strong - raw_largest_weak
    ratio = smallest_strong > 0 ? largest_weak / smallest_strong : Inf
    stable_gap = smallest_strong > STRONG_ETA_MULTIPLIER * eta &&
                 raw_gap > GAP_ETA_MULTIPLIER * eta &&
                 ratio <= WEAK_STRONG_RATIO_MAX
    stable_gap || return (
        evidence=nothing,
        reason=:no_stable_one_dimensional_invariant_rank,
    )

    coarse_right = Matrix{Float64}(coarse_svd.V[:, n:n])
    fine_right = Matrix{Float64}(fine_svd.V[:, n:n])
    coarse_left = Matrix{Float64}(coarse_svd.U[:, n:n])
    fine_left = Matrix{Float64}(fine_svd.U[:, n:n])
    coarse_right_projector = coarse_right * transpose(coarse_right)
    fine_right_projector = fine_right * transpose(fine_right)
    coarse_left_projector = coarse_left * transpose(coarse_left)
    fine_left_projector = fine_left * transpose(fine_left)
    right_distance = opnorm(coarse_right_projector - fine_right_projector, 2)
    left_distance = opnorm(coarse_left_projector - fine_left_projector, 2)
    stable_projectors = isfinite(right_distance) && isfinite(left_distance) &&
                        right_distance <= PROJECTOR_DISTANCE_MAX &&
                        left_distance <= PROJECTOR_DISTANCE_MAX
    stable_projectors || return (evidence=nothing, reason=:unstable_weak_projector)
    evidence = RankProjectorEvidence(
        n,
        n - 1,
        n - 1,
        1,
        coarse_values,
        fine_values,
        eta,
        smallest_strong,
        largest_weak,
        ratio,
        coarse_right_projector,
        fine_right_projector,
        coarse_left_projector,
        fine_left_projector,
        right_distance,
        left_distance,
        _average_rank_one_projector(coarse_right_projector, fine_right_projector),
        _average_rank_one_projector(coarse_left_projector, fine_left_projector),
    )
    return (evidence, reason=:stable_one_dimensional_rank_projector)
end

"""
Acquire a central Float64 Jacobian pair.  All stencil points are prevalidated,
then all `4n` calls are made even when one callback fails or changes semantics;
there is no outcome-dependent half-stencil.
"""
function acquire_cpqr_rank_evidence(
    evaluate,
    box::NormalizedBox,
    endpoint::AbstractVector,
    anchor::RescueEvaluation;
    remaining_callbacks::Integer,
    charge_callback=() -> nothing,
)
    point = Float64[endpoint...]
    n = length(point)
    reservation = reserve_cpqr_diagnostic(n, remaining_callbacks)
    reservation.status == :reserved || return _empty_diagnostic(
        :unknown,
        reservation.reason,
        reservation,
        0,
        CPQR_FD_STEP,
        n,
    )
    length(box.lower) == n || return _empty_diagnostic(
        :unknown, :box_dimension_mismatch, reservation, 0, CPQR_FD_STEP, n,
    )
    _inside_open_box(box, point) || return _empty_diagnostic(
        :unknown, :endpoint_not_strictly_inside_box, reservation, 0, CPQR_FD_STEP, n,
    )
    residual_dimension = length(anchor.residual)
    residual_dimension == n || return _empty_diagnostic(
        :unknown, :square_residual_required, reservation, 0, CPQR_FD_STEP, n,
    )
    _intrinsically_valid(anchor, residual_dimension) || return _empty_diagnostic(
        :unknown, :invalid_anchor, reservation, 0, CPQR_FD_STEP, n,
    )

    stencil = NamedTuple[]
    for (level, step) in enumerate((CPQR_FD_STEP, CPQR_FD_STEP / 2))
        for column in 1:n, sign in (1, -1)
            sample = copy(point)
            sample[column] += sign * step
            _inside_open_box(box, sample) || return _empty_diagnostic(
                :unknown,
                :cpqr_stencil_outside_normalized_box,
                reservation,
                0,
                CPQR_FD_STEP,
                n,
            )
            push!(stencil, (; level, column, sign, step, point=sample))
        end
    end
    length(stencil) == reservation.required_callbacks || error("4n stencil drifted")

    observations = Vector{Any}(undef, length(stencil))
    outcomes = Vector{Symbol}(undef, length(stencil))
    for index in eachindex(stencil)
        observations[index], outcomes[index] = _evaluate_once(
            evaluate,
            stencil[index].point,
            charge_callback,
        )
    end
    callbacks = length(stencil)
    callbacks == reservation.required_callbacks || error("4n callback accounting drifted")

    first_failure = nothing
    for index in eachindex(stencil)
        observation = observations[index]
        if outcomes[index] != :ok
            first_failure === nothing && (first_failure = outcomes[index])
        elseif !_intrinsically_valid(observation, residual_dimension)
            first_failure === nothing && (first_failure = :invalid_stencil_evaluation)
        elseif !_same_semantics(observation, anchor)
            first_failure === nothing && (first_failure = :cpqr_branch_or_guard_changed)
        end
    end
    first_failure === nothing || return _empty_diagnostic(
        :unknown,
        first_failure,
        reservation,
        callbacks,
        CPQR_FD_STEP,
        n,
    )

    coarse = zeros(Float64, n, n)
    fine = zeros(Float64, n, n)
    rounding_squared = 0.0
    cursor = 1
    for destination in (coarse, fine)
        for column in 1:n
            plus = observations[cursor]::RescueEvaluation
            minus = observations[cursor + 1]::RescueEvaluation
            step = stencil[cursor].step
            destination[:, column] .= (plus.residual .- minus.residual) ./ (2step)
            rounding = FD_ROUNDOFF_GAMMA *
                (norm(plus.residual, 2) + norm(minus.residual, 2)) / (2step)
            isfinite(rounding) || return _empty_diagnostic(
                :unknown,
                :nonfinite_roundoff_envelope,
                reservation,
                callbacks,
                CPQR_FD_STEP,
                n;
                coarse,
                fine,
            )
            rounding_squared += rounding^2
            cursor += 2
        end
    end
    all(isfinite, coarse) && all(isfinite, fine) || return _empty_diagnostic(
        :unknown,
        :nonfinite_jacobian,
        reservation,
        callbacks,
        CPQR_FD_STEP,
        n;
        coarse,
        fine,
    )

    eta = opnorm(fine - coarse, 2) + sqrt(rounding_squared)
    isfinite(eta) || return _empty_diagnostic(
        :unknown,
        :nonfinite_jacobian_uncertainty,
        reservation,
        callbacks,
        CPQR_FD_STEP,
        n;
        coarse,
        fine,
    )
    coarse_diagonal = _cpqr_diagonal(coarse)
    fine_diagonal = _cpqr_diagonal(fine)
    cpqr_threshold = max(
        CPQR_ETA_MULTIPLIER * eta,
        64eps(Float64) * max(1.0, opnorm(coarse, 2), opnorm(fine, 2)),
    )
    # CPQR is recorded above, but only the SVD gap and projectors have routing
    # authority.  This avoids the known threshold-near 45-degree rotation bug.
    invariant = _invariant_rank_evidence(coarse, fine, eta)
    invariant.evidence === nothing && return _empty_diagnostic(
        :unknown,
        invariant.reason,
        reservation,
        callbacks,
        CPQR_FD_STEP,
        n;
        coarse,
        fine,
        coarse_diagonal,
        fine_diagonal,
        threshold=cpqr_threshold,
    )
    evidence = invariant.evidence::RankProjectorEvidence
    return CPQRDiagnostic(
        :applicable,
        :stable_one_dimensional_rank_projector,
        reservation,
        callbacks,
        CPQR_FD_STEP,
        coarse,
        fine,
        coarse_diagonal,
        fine_diagonal,
        cpqr_threshold,
        evidence,
    )
end

struct RefinementSeed
    lower_parameter::Float64
    upper_parameter::Float64
    lower_projected_residual::Float64
    upper_projected_residual::Float64
    normalized_point::Vector{Float64}
    probe_direction::Vector{Float64}
    lane::Symbol
end

struct BracketProbeResult
    status::Symbol
    reason::Symbol
    lane::Symbol
    callback_count::Int
    required_callbacks::Int
    parameters::Vector{Float64}
    projected_residuals::Vector{Float64}
    robust_signs::Vector{Int}
    detected_bracket_count::Int
    seeds::Vector{RefinementSeed}
end

function _empty_probe(status, reason, lane, callbacks, required;
    parameters=Float64[], projected=Float64[], signs=Int[], detected=0)
    return BracketProbeResult(
        status,
        reason,
        lane,
        Int(callbacks),
        Int(required),
        Float64[parameters...],
        Float64[projected...],
        Int[signs...],
        Int(detected),
        RefinementSeed[],
    )
end

function _projector_is_rank_one(projector::AbstractMatrix, dimension::Int)
    size(projector) == (dimension, dimension) || return false
    all(isfinite, projector) || return false
    matrix = Matrix{Float64}(projector)
    tolerance = 1.0e-8
    opnorm(matrix - transpose(matrix), 2) <= tolerance || return false
    opnorm(matrix * matrix - matrix, 2) <= tolerance || return false
    abs(tr(matrix) - 1.0) <= tolerance || return false
    return true
end

function _evidence_valid(evidence::RankProjectorEvidence, dimension::Int)
    evidence.dimension == dimension || return false
    evidence.weak_dimension == 1 || return false
    evidence.coarse_rank == dimension - 1 || return false
    evidence.fine_rank == dimension - 1 || return false
    length(evidence.coarse_singular_values) == dimension || return false
    length(evidence.fine_singular_values) == dimension || return false
    all(isfinite, evidence.coarse_singular_values) || return false
    all(isfinite, evidence.fine_singular_values) || return false
    issorted(evidence.coarse_singular_values; rev=true) || return false
    issorted(evidence.fine_singular_values; rev=true) || return false
    evidence.smallest_strong > 0 || return false
    isfinite(evidence.smallest_strong) || return false
    isfinite(evidence.largest_weak) && evidence.largest_weak >= 0 || return false
    isfinite(evidence.eta) && evidence.eta >= 0 || return false
    isfinite(evidence.weak_strong_ratio) &&
        evidence.weak_strong_ratio <= WEAK_STRONG_RATIO_MAX || return false
    isapprox(
        evidence.weak_strong_ratio,
        evidence.largest_weak / evidence.smallest_strong;
        rtol=64eps(Float64),
        atol=64eps(Float64),
    ) || return false
    projectors = (
        evidence.coarse_right_projector,
        evidence.fine_right_projector,
        evidence.coarse_left_projector,
        evidence.fine_left_projector,
        evidence.average_right_projector,
        evidence.average_left_projector,
    )
    all(projector -> _projector_is_rank_one(projector, dimension), projectors) || return false
    computed_right_distance = opnorm(
        evidence.coarse_right_projector - evidence.fine_right_projector,
        2,
    )
    computed_left_distance = opnorm(
        evidence.coarse_left_projector - evidence.fine_left_projector,
        2,
    )
    computed_right_distance <= PROJECTOR_DISTANCE_MAX || return false
    computed_left_distance <= PROJECTOR_DISTANCE_MAX || return false
    isfinite(evidence.right_projector_distance) || return false
    isfinite(evidence.left_projector_distance) || return false
    abs(computed_right_distance - evidence.right_projector_distance) <= 1.0e-10 || return false
    abs(computed_left_distance - evidence.left_projector_distance) <= 1.0e-10 || return false
    expected_right = _average_rank_one_projector(
        evidence.coarse_right_projector,
        evidence.fine_right_projector,
    )
    expected_left = _average_rank_one_projector(
        evidence.coarse_left_projector,
        evidence.fine_left_projector,
    )
    opnorm(expected_right - evidence.average_right_projector, 2) <= 1.0e-10 || return false
    opnorm(expected_left - evidence.average_left_projector, 2) <= 1.0e-10 || return false
    return true
end

function _evidence_matches(
    recorded::RankProjectorEvidence,
    recomputed::RankProjectorEvidence,
)
    scalar_pairs = (
        (recorded.eta, recomputed.eta),
        (recorded.smallest_strong, recomputed.smallest_strong),
        (recorded.largest_weak, recomputed.largest_weak),
        (recorded.weak_strong_ratio, recomputed.weak_strong_ratio),
        (recorded.right_projector_distance, recomputed.right_projector_distance),
        (recorded.left_projector_distance, recomputed.left_projector_distance),
    )
    all(pair -> isapprox(pair[1], pair[2]; rtol=128eps(Float64), atol=128eps(Float64)),
        scalar_pairs) || return false
    isapprox(
        recorded.coarse_singular_values,
        recomputed.coarse_singular_values;
        rtol=128eps(Float64),
        atol=128eps(Float64),
    ) || return false
    isapprox(
        recorded.fine_singular_values,
        recomputed.fine_singular_values;
        rtol=128eps(Float64),
        atol=128eps(Float64),
    ) || return false
    projector_pairs = (
        (recorded.coarse_right_projector, recomputed.coarse_right_projector),
        (recorded.fine_right_projector, recomputed.fine_right_projector),
        (recorded.coarse_left_projector, recomputed.coarse_left_projector),
        (recorded.fine_left_projector, recomputed.fine_left_projector),
        (recorded.average_right_projector, recomputed.average_right_projector),
        (recorded.average_left_projector, recomputed.average_left_projector),
    )
    all(pair -> opnorm(pair[1] - pair[2], 2) <= 1.0e-10, projector_pairs) || return false
    return recorded.dimension == recomputed.dimension &&
           recorded.coarse_rank == recomputed.coarse_rank &&
           recorded.fine_rank == recomputed.fine_rank &&
           recorded.weak_dimension == recomputed.weak_dimension
end

"""Rebind routing evidence to the acquired Jacobian pair, never caller fields."""
function _validated_diagnostic_evidence(diagnostic::CPQRDiagnostic, dimension::Int)
    diagnostic.status == :applicable || return (
        evidence=nothing,
        reason=:cpqr_diagnostic_not_applicable,
    )
    reservation = diagnostic.reservation
    reservation.status == :reserved &&
        reservation.dimension == dimension &&
        reservation.required_callbacks == 4dimension &&
        reservation.reserved_callbacks == 4dimension &&
        diagnostic.callback_count == 4dimension || return (
        evidence=nothing,
        reason=:invalid_cpqr_diagnostic_accounting,
    )
    size(diagnostic.coarse_jacobian) == (dimension, dimension) &&
        size(diagnostic.fine_jacobian) == (dimension, dimension) || return (
        evidence=nothing,
        reason=:invalid_cpqr_diagnostic_shape,
    )
    all(isfinite, diagnostic.coarse_jacobian) &&
        all(isfinite, diagnostic.fine_jacobian) || return (
        evidence=nothing,
        reason=:invalid_cpqr_diagnostic_jacobian,
    )
    recorded = diagnostic.evidence
    recorded isa RankProjectorEvidence || return (
        evidence=nothing,
        reason=:missing_cpqr_rank_evidence,
    )
    _evidence_valid(recorded, dimension) || return (
        evidence=nothing,
        reason=:invalid_cpqr_rank_evidence,
    )
    recomputation = _invariant_rank_evidence(
        diagnostic.coarse_jacobian,
        diagnostic.fine_jacobian,
        recorded.eta,
    )
    recomputation.evidence isa RankProjectorEvidence || return (
        evidence=nothing,
        reason=:cpqr_invariant_recomputation_failed,
    )
    recomputed = recomputation.evidence::RankProjectorEvidence
    _evidence_matches(recorded, recomputed) || return (
        evidence=nothing,
        reason=:cpqr_evidence_recomputation_mismatch,
    )
    # CPQR telemetry is also bound to the matrices, although it has no
    # applicability authority.
    isapprox(
        diagnostic.coarse_cpqr_diagonal,
        _cpqr_diagonal(diagnostic.coarse_jacobian);
        rtol=128eps(Float64),
        atol=128eps(Float64),
    ) && isapprox(
        diagnostic.fine_cpqr_diagonal,
        _cpqr_diagonal(diagnostic.fine_jacobian);
        rtol=128eps(Float64),
        atol=128eps(Float64),
    ) || return (evidence=nothing, reason=:cpqr_telemetry_recomputation_mismatch)
    return (evidence=recomputed, reason=:validated_invariant_rank_evidence)
end

function _canonical_line(projector::AbstractMatrix)
    decomposition = eigen(Symmetric(Matrix{Float64}(projector)))
    direction = Vector{Float64}(decomposition.vectors[:, end])
    direction ./= norm(direction)
    pivot = argmax(abs.(direction))
    direction[pivot] < 0 && (direction .*= -1)
    return direction
end

function _robust_projected_sign(value::Float64, residual::AbstractVector)
    # Homogeneous of degree one in the entire residual.  Therefore a global
    # representable row scale cannot change the robust sign class.
    residual_scale = norm(residual, 2)
    isfinite(residual_scale) || return 0
    tolerance = SIGN_ROUNDOFF_MULTIPLIER * eps(Float64) * residual_scale
    abs(value) <= tolerance && return 0
    return signbit(value) ? -1 : 1
end

"""
Probe every frozen radius in complete `+/-` pairs.  `:weak` emits bracket
midpoints, `:isotropic` is an equal-work directional control, and
`:no_bracket` performs identical weak probes but suppresses emission.
"""
function _symmetric_bracket_probe_authoritative(
    evaluate,
    box::NormalizedBox,
    endpoint::AbstractVector,
    anchor::RescueEvaluation,
    diagnostic::CPQRDiagnostic;
    remaining_callbacks::Integer,
    lane::Symbol=:weak,
    isotropic_direction=nothing,
    charge_callback=() -> nothing,
)
    point = Float64[endpoint...]
    n = length(point)
    required = 2length(BRACKET_RADII)
    lane in (:weak, :isotropic, :no_bracket) || return _empty_probe(
        :unknown, :invalid_probe_lane, lane, 0, required,
    )
    Int(remaining_callbacks) >= required || return _empty_probe(
        :unknown, :insufficient_probe_budget, lane, 0, required,
    )
    length(box.lower) == n || return _empty_probe(
        :unknown, :box_dimension_mismatch, lane, 0, required,
    )
    _inside_open_box(box, point) || return _empty_probe(
        :unknown, :endpoint_not_strictly_inside_box, lane, 0, required,
    )
    residual_dimension = length(anchor.residual)
    residual_dimension == n && _intrinsically_valid(anchor, residual_dimension) ||
        return _empty_probe(:unknown, :invalid_anchor, lane, 0, required)
    validation = _validated_diagnostic_evidence(diagnostic, n)
    validation.evidence isa RankProjectorEvidence || return _empty_probe(
        :unknown, validation.reason, lane, 0, required,
    )
    evidence = validation.evidence::RankProjectorEvidence

    weak_direction = _canonical_line(evidence.average_right_projector)
    direction = if lane == :isotropic
        isotropic_direction === nothing && return _empty_probe(
            :unknown, :missing_isotropic_control_direction, lane, 0, required,
        )
        candidate = try
            Float64[isotropic_direction...]
        catch
            return _empty_probe(:unknown, :invalid_isotropic_control_direction, lane, 0, required)
        end
        length(candidate) == n && all(isfinite, candidate) || return _empty_probe(
            :unknown, :invalid_isotropic_control_direction, lane, 0, required,
        )
        magnitude = norm(candidate, 2)
        isfinite(magnitude) && magnitude > sqrt(eps(Float64)) || return _empty_probe(
            :unknown, :invalid_isotropic_control_direction, lane, 0, required,
        )
        candidate ./ magnitude
    else
        weak_direction
    end
    left_direction = _canonical_line(evidence.average_left_projector)

    stencil = NamedTuple[]
    for radius in BRACKET_RADII, sign in (1, -1)
        sample = point .+ sign * radius .* direction
        _inside_open_box(box, sample) || return _empty_probe(
            :unknown,
            :probe_outside_normalized_box,
            lane,
            0,
            required,
        )
        push!(stencil, (; radius, sign, parameter=sign * radius, point=sample))
    end
    length(stencil) == required || error("symmetric probe budget drifted")

    observations = Vector{Any}(undef, required)
    outcomes = Vector{Symbol}(undef, required)
    for index in eachindex(stencil)
        observations[index], outcomes[index] = _evaluate_once(
            evaluate,
            stencil[index].point,
            charge_callback,
        )
    end
    first_failure = nothing
    for index in eachindex(stencil)
        observation = observations[index]
        if outcomes[index] != :ok
            first_failure === nothing && (first_failure = outcomes[index])
        elseif !_intrinsically_valid(observation, residual_dimension)
            first_failure === nothing && (first_failure = :invalid_probe_evaluation)
        elseif !_same_semantics(observation, anchor)
            first_failure === nothing && (first_failure = :probe_branch_or_guard_changed)
        end
    end
    first_failure === nothing || return _empty_probe(
        :unknown,
        first_failure,
        lane,
        required,
        required,
    )

    samples = NamedTuple[]
    anchor_value = dot(left_direction, anchor.residual)
    push!(samples, (;
        parameter=0.0,
        projected=anchor_value,
        sign=_robust_projected_sign(anchor_value, anchor.residual),
    ))
    for index in eachindex(stencil)
        observation = observations[index]::RescueEvaluation
        value = dot(left_direction, observation.residual)
        isfinite(value) || return _empty_probe(
            :unknown, :nonfinite_projected_residual, lane, required, required,
        )
        push!(samples, (;
            parameter=stencil[index].parameter,
            projected=value,
            sign=_robust_projected_sign(value, observation.residual),
        ))
    end
    sort!(samples; by=sample -> sample.parameter)
    parameters = Float64[sample.parameter for sample in samples]
    projected = Float64[sample.projected for sample in samples]
    signs = Int[sample.sign for sample in samples]

    if all(==(0), signs)
        return _empty_probe(
            :unknown,
            :projected_manifold_or_unresolved_zero,
            lane,
            required,
            required;
            parameters,
            projected,
            signs,
        )
    end

    detected = RefinementSeed[]
    for index in 1:(length(samples) - 1)
        lower_sample = samples[index]
        upper_sample = samples[index + 1]
        lower_sample.sign * upper_sample.sign == -1 || continue
        midpoint = (lower_sample.parameter + upper_sample.parameter) / 2
        seed_point = point .+ midpoint .* direction
        push!(detected, RefinementSeed(
            lower_sample.parameter,
            upper_sample.parameter,
            lower_sample.projected,
            upper_sample.projected,
            seed_point,
            copy(direction),
            lane,
        ))
    end
    detected_count = length(detected)
    if lane == :no_bracket
        return _empty_probe(
            :control,
            :no_bracket_emission_control,
            lane,
            required,
            required;
            parameters,
            projected,
            signs,
            detected=detected_count,
        )
    elseif !isempty(detected)
        return BracketProbeResult(
            :seeded,
            :strict_projected_sign_bracket,
            lane,
            required,
            required,
            parameters,
            projected,
            signs,
            detected_count,
            detected,
        )
    end
    reason = signs[findfirst(==(0), parameters)] == 0 ?
             :even_or_tangent_projected_root :
             (any(==(0), signs) ? :projected_sign_ambiguous : :no_sign_bracket)
    return _empty_probe(
        :unknown,
        reason,
        lane,
        required,
        required;
        parameters,
        projected,
        signs,
    )
end

"""
An externally supplied diagnostic is never routing authority: even internally
consistent matrices are not bound to this evaluator, endpoint, or anchor.
Only `weak_bracket_rescue` may acquire and immediately consume a diagnostic in
one opaque operation.
"""
function symmetric_bracket_probe(
    evaluate,
    box::NormalizedBox,
    endpoint::AbstractVector,
    anchor::RescueEvaluation,
    diagnostic::CPQRDiagnostic;
    remaining_callbacks::Integer,
    lane::Symbol=:weak,
    isotropic_direction=nothing,
    charge_callback=() -> nothing,
)
    required = 2length(BRACKET_RADII)
    return _empty_probe(
        :unknown,
        :external_cpqr_diagnostic_non_authoritative,
        lane,
        0,
        required,
    )
end

"""
A naked projector record is likewise never routing authority because its
singular-value and uncertainty fields are not callback-bound.  Keep this typed
method so stale/forged experiment adapters fail closed without work.
"""
function symmetric_bracket_probe(
    evaluate,
    box::NormalizedBox,
    endpoint::AbstractVector,
    anchor::RescueEvaluation,
    evidence::RankProjectorEvidence;
    remaining_callbacks::Integer,
    lane::Symbol=:weak,
    isotropic_direction=nothing,
    charge_callback=() -> nothing,
)
    required = 2length(BRACKET_RADII)
    return _empty_probe(
        :unknown,
        :standalone_rank_evidence_non_authoritative,
        lane,
        0,
        required,
    )
end

struct WeakBracketRescueResult
    status::Symbol
    reason::Symbol
    lane::Symbol
    callback_count::Int
    required_callbacks::Int
    diagnostic::Union{Nothing,CPQRDiagnostic}
    probe::Union{Nothing,BracketProbeResult}
    seeds::Vector{RefinementSeed}
end

function _empty_rescue(status, reason, lane, callbacks, required;
    diagnostic=nothing, probe=nothing)
    return WeakBracketRescueResult(
        status,
        reason,
        lane,
        Int(callbacks),
        Int(required),
        diagnostic,
        probe,
        RefinementSeed[],
    )
end

"""
Acquire the reserved Float64 CPQR/rank evidence, then run the fixed symmetric
probe.  The returned seeds are only starts for the unchanged canonical local
and 512/768-bit validation pipeline; this function never declares an answer.
"""
function weak_bracket_rescue(
    evaluate,
    box::NormalizedBox,
    endpoint::AbstractVector,
    anchor::RescueEvaluation;
    remaining_callbacks::Integer,
    lane::Symbol=:weak,
    isotropic_direction=nothing,
    charge_callback=() -> nothing,
)
    n = length(endpoint)
    diagnostic_required = n >= 2 ? 4n : 0
    probe_required = 2length(BRACKET_RADII)
    total_required = diagnostic_required + probe_required
    Int(remaining_callbacks) >= total_required || return _empty_rescue(
        :unknown,
        n < 2 ? :dimension_below_two : :insufficient_total_budget,
        lane,
        0,
        total_required,
    )
    diagnostic = acquire_cpqr_rank_evidence(
        evaluate,
        box,
        endpoint,
        anchor;
        remaining_callbacks,
        charge_callback,
    )
    diagnostic.status == :applicable || return _empty_rescue(
        :unknown,
        diagnostic.reason,
        lane,
        diagnostic.callback_count,
        total_required;
        diagnostic,
    )
    probe = _symmetric_bracket_probe_authoritative(
        evaluate,
        box,
        endpoint,
        anchor,
        diagnostic;
        remaining_callbacks=Int(remaining_callbacks) - diagnostic.callback_count,
        lane,
        isotropic_direction,
        charge_callback,
    )
    callbacks = diagnostic.callback_count + probe.callback_count
    callbacks <= Int(remaining_callbacks) || error("endpoint callback budget exceeded")
    if probe.status == :seeded
        return WeakBracketRescueResult(
            :seeded,
            probe.reason,
            lane,
            callbacks,
            total_required,
            diagnostic,
            probe,
            copy(probe.seeds),
        )
    elseif probe.status == :control
        return _empty_rescue(
            :control,
            probe.reason,
            lane,
            callbacks,
            total_required;
            diagnostic,
            probe,
        )
    end
    return _empty_rescue(
        :unknown,
        probe.reason,
        lane,
        callbacks,
        total_required;
        diagnostic,
        probe,
    )
end

end
