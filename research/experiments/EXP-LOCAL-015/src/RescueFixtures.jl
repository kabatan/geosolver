module RescueFixtures

using LinearAlgebra
using SHA

export AssessorTruth,
    FiniteBox,
    FixtureDescriptor,
    FixtureEvaluation,
    FixtureRecord,
    TruthBlindFixture,
    assessor_truth,
    candidate_view,
    corpus_replay_checksum,
    make_clustered_fixture,
    make_linear_fixture,
    make_safety_fixture,
    orthogonal_replica,
    replay_checksum,
    rescue_fixture_corpus,
    signed_permutation_replica

const Exact = Rational{BigInt}
const DEFAULT_START_COUNT = 16
const LINEAR_DIMENSIONS = (2, 4, 8)
const CONDITION_TIERS = (10^4, 10^8, 10^12)
const CLUSTER_ROOT_COUNTS = (4, 8)
const SAFETY_KINDS = (
    :stationary_nonroot,
    :even_multiple_root,
    :constant_manifold,
    :varying_manifold,
    :branch_crossing,
    :guard_crossing,
)

_exact(numerator::Integer, denominator::Integer=1) =
    BigInt(numerator) // BigInt(denominator)

function _power_of_two(exponent::Integer)
    exponent >= 0 && return (BigInt(1) << Int(exponent)) // BigInt(1)
    return BigInt(1) // (BigInt(1) << Int(-exponent))
end

_convert_exact(::Type{T}, value::Exact) where {T<:Real} =
    T(numerator(value)) / T(denominator(value))

function _convert_exact(::Type{T}, values::AbstractVector{Exact}) where {T<:Real}
    return T[_convert_exact(T, value) for value in values]
end

function _convert_exact(::Type{T}, values::AbstractMatrix{Exact}) where {T<:Real}
    return T[_convert_exact(T, values[row, column]) for row in axes(values, 1),
             column in axes(values, 2)]
end

struct FiniteBox
    lower::Vector{Float64}
    upper::Vector{Float64}

    function FiniteBox(lower::AbstractVector, upper::AbstractVector)
        length(lower) == length(upper) || throw(DimensionMismatch("fixture box"))
        isempty(lower) && throw(ArgumentError("fixture box must have positive dimension"))
        lo = Float64[lower...]
        hi = Float64[upper...]
        all(isfinite, lo) && all(isfinite, hi) ||
            throw(ArgumentError("fixture box must be finite"))
        all(lo .< hi) || throw(ArgumentError("fixture lower bound must be below upper"))
        new(lo, hi)
    end
end

FiniteBox(dimension::Integer) = dimension > 0 ?
    FiniteBox(fill(-1.0, dimension), fill(1.0, dimension)) :
    throw(ArgumentError("fixture dimension must be positive"))

"""Public black-box observation; `target` is observed, never assessor Gold."""
struct FixtureEvaluation{T<:Real,B,G,D}
    residual::Vector{T}
    target::T
    branch_identity::B
    guard_identity::G
    domain_identity::D
    branch_margin::T
    guard_margin::T
    domain_margin::T
    valid::Bool
end

"""
The only object passed to candidate algorithms.  It deliberately has no case
or family identifier, checksum, condition label, roots, Gold targets, or
classification.
"""
struct TruthBlindFixture
    box::FiniteBox
    evaluate_float64::Function
    evaluate_arbitrary::Function
    starts::Vector{Vector{Float64}}
end

struct FixtureDescriptor
    fixture_id::String
    stratum::Symbol
    dimension::Int
    parameter_tag::String
end

"""Assessor-only exact truth. Manifold witnesses are not isolated roots."""
struct AssessorTruth
    classification::Symbol
    isolated_roots::Vector{Vector{Exact}}
    targets::Vector{Exact}
    manifold_witnesses::Vector{Vector{Exact}}
    witness_targets::Vector{Exact}
end

abstract type AbstractFixtureModel end

struct LinearModel <: AbstractFixtureModel
    left_rotation::Matrix{Exact}
    right_rotation::Matrix{Exact}
    singular_values::Vector{Exact}
    latent_root::Vector{Exact}
    delta::Exact
end

struct ClusteredModel <: AbstractFixtureModel
    left_rotation::Matrix{Exact}
    right_rotation::Matrix{Exact}
    weak_roots::Vector{Exact}
    separation::Exact
    quadratic_warp::Vector{Exact}
    cubic_warp::Vector{Exact}
end

struct SafetyModel <: AbstractFixtureModel
    kind::Symbol
    left_rotation::Matrix{Exact}
    right_rotation::Matrix{Exact}
    parameter::Exact
    threshold::Exact
end

struct ReplicaModel{M<:AbstractFixtureModel} <: AbstractFixtureModel
    base::M
    variable_rotation::Matrix{Exact}
    residual_rotation::Matrix{Exact}
end

"""Root-owned record. Only `candidate_view(record)` crosses the candidate seam."""
struct FixtureRecord{M<:AbstractFixtureModel}
    descriptor::FixtureDescriptor
    candidate::TruthBlindFixture
    assessor::AssessorTruth
    private_model::M
    checksum_payload::String
end

candidate_view(record::FixtureRecord) = record.candidate
assessor_truth(record::FixtureRecord) = record.assessor

_dimension(model::LinearModel) = length(model.latent_root)
_dimension(model::ClusteredModel) = length(model.quadratic_warp) + 1
_dimension(model::SafetyModel) = size(model.right_rotation, 1)
_dimension(model::ReplicaModel) = _dimension(model.base)

function _weighted_target(latent::AbstractVector{T}) where {T<:Real}
    result = zero(T)
    for index in eachindex(latent)
        result += T(index) * latent[index]
    end
    return result
end

function _default_evaluation(residual::Vector{T}, target::T) where {T<:Real}
    return FixtureEvaluation(
        residual,
        target,
        :single_branch,
        :single_guard,
        :finite_domain,
        one(T),
        one(T),
        one(T),
        true,
    )
end

function _evaluate(model::LinearModel, point::AbstractVector{T}) where {T<:Real}
    dimension = _dimension(model)
    length(point) == dimension || throw(DimensionMismatch("linear fixture point"))
    left = _convert_exact(T, model.left_rotation)
    right = _convert_exact(T, model.right_rotation)
    root = _convert_exact(T, model.latent_root)
    singular = _convert_exact(T, model.singular_values)
    latent = transpose(right) * T[point...]
    residual = left * (singular .* (latent .- root))
    return _default_evaluation(Vector{T}(residual), _weighted_target(latent))
end

function _cluster_warp(model::ClusteredModel, index::Int, parameter::T) where {T<:Real}
    quadratic = _convert_exact(T, model.quadratic_warp[index])
    cubic = _convert_exact(T, model.cubic_warp[index])
    return quadratic * parameter^2 + cubic * parameter^3
end

function _evaluate(model::ClusteredModel, point::AbstractVector{T}) where {T<:Real}
    dimension = _dimension(model)
    length(point) == dimension || throw(DimensionMismatch("clustered fixture point"))
    left = _convert_exact(T, model.left_rotation)
    right = _convert_exact(T, model.right_rotation)
    latent = transpose(right) * T[point...]
    parameter = latent[end]
    residual_latent = zeros(T, dimension)
    for index in 1:(dimension - 1)
        residual_latent[index] = latent[index] - _cluster_warp(model, index, parameter)
    end
    polynomial = one(T)
    for root in model.weak_roots
        polynomial *= parameter - _convert_exact(T, root)
    end
    separation = _convert_exact(T, model.separation)
    residual_latent[end] = polynomial / separation^(length(model.weak_roots) - 1)
    residual = left * residual_latent
    return _default_evaluation(Vector{T}(residual), _weighted_target(latent))
end

function _evaluate(model::SafetyModel, point::AbstractVector{T}) where {T<:Real}
    dimension = _dimension(model)
    length(point) == dimension || throw(DimensionMismatch("safety fixture point"))
    left = _convert_exact(T, model.left_rotation)
    right = _convert_exact(T, model.right_rotation)
    latent = transpose(right) * T[point...]
    parameter = latent[end]
    residual_latent = zeros(T, dimension)
    residual_latent[1:(dimension - 1)] .= latent[1:(dimension - 1)]
    value = _convert_exact(T, model.parameter)
    threshold = _convert_exact(T, model.threshold)
    kind = model.kind
    if kind == :stationary_nonroot
        residual_latent[end] = parameter^2 + value
        target = _weighted_target(latent)
        return _default_evaluation(Vector{T}(left * residual_latent), target)
    elseif kind == :even_multiple_root
        residual_latent[end] = (parameter - value)^2
        target = _weighted_target(latent)
        return _default_evaluation(Vector{T}(left * residual_latent), target)
    elseif kind == :constant_manifold
        residual_latent[end] = zero(T)
        target = T(7) / T(13)
        return _default_evaluation(Vector{T}(left * residual_latent), target)
    elseif kind == :varying_manifold
        residual_latent[end] = zero(T)
        return _default_evaluation(Vector{T}(left * residual_latent), parameter)
    elseif kind == :branch_crossing || kind == :guard_crossing
        residual_latent[end] = (parameter - value) * (parameter + value)
        residual = Vector{T}(left * residual_latent)
        branch_identity = kind == :branch_crossing ?
            (parameter < zero(T) ? :negative_branch : :nonnegative_branch) :
            :single_branch
        guard_identity = kind == :guard_crossing ?
            (abs(parameter) < threshold ? :inner_guard : :outer_guard) :
            :single_guard
        branch_margin = kind == :branch_crossing ?
            max(abs(parameter), _convert_exact(T, _power_of_two(-200))) : one(T)
        guard_margin = kind == :guard_crossing ? abs(abs(parameter) - threshold) : one(T)
        valid = branch_margin > zero(T) && guard_margin > zero(T)
        return FixtureEvaluation(
            residual,
            parameter,
            branch_identity,
            guard_identity,
            :finite_domain,
            branch_margin,
            guard_margin,
            one(T),
            valid,
        )
    end
    error("unknown safety fixture kind")
end

function _evaluate(model::ReplicaModel, point::AbstractVector{T}) where {T<:Real}
    dimension = _dimension(model)
    length(point) == dimension || throw(DimensionMismatch("replica fixture point"))
    variable = _convert_exact(T, model.variable_rotation)
    residual_rotation = _convert_exact(T, model.residual_rotation)
    base = _evaluate(model.base, transpose(variable) * T[point...])
    return FixtureEvaluation(
        Vector{T}(residual_rotation * base.residual),
        base.target,
        base.branch_identity,
        base.guard_identity,
        base.domain_identity,
        base.branch_margin,
        base.guard_margin,
        base.domain_margin,
        base.valid,
    )
end

function _identity_exact(dimension::Int)
    result = zeros(Exact, dimension, dimension)
    for index in 1:dimension
        result[index, index] = _exact(1)
    end
    return result
end

function _rational_orthogonal(dimension::Int, tag::Int)
    dimension >= 2 || throw(ArgumentError("orthogonal fixture dimension"))
    pairs = ((_exact(3, 5), _exact(4, 5)),
             (_exact(5, 13), _exact(12, 13)),
             (_exact(8, 17), _exact(15, 17)))
    result = _identity_exact(dimension)
    turns = dimension + mod(tag, 3) + 1
    for turn in 1:turns
        first = mod(turn + tag - 2, dimension) + 1
        second = mod(first + turn + tag - 1, dimension) + 1
        second == first && (second = mod(second, dimension) + 1)
        cosine, sine = pairs[mod(turn + tag - 2, length(pairs)) + 1]
        isodd(turn + tag) && (sine = -sine)
        givens = _identity_exact(dimension)
        givens[first, first] = cosine
        givens[second, second] = cosine
        givens[first, second] = -sine
        givens[second, first] = sine
        result = result * givens
    end
    transpose(result) * result == _identity_exact(dimension) ||
        error("exact orthogonal construction drifted")
    return result
end

function _signed_permutation(dimension::Int, shift::Int, phase::Int)
    result = zeros(Exact, dimension, dimension)
    for column in 1:dimension
        row = mod(column - 1 + shift, dimension) + 1
        result[row, column] = isodd(column + phase) ? -_exact(1) : _exact(1)
    end
    transpose(result) * result == _identity_exact(dimension) ||
        error("signed permutation construction drifted")
    return result
end

function _splitmix64(value::UInt64)
    word = value + 0x9e3779b97f4a7c15
    word = xor(word, word >> 30) * 0xbf58476d1ce4e5b9
    word = xor(word, word >> 27) * 0x94d049bb133111eb
    return xor(word, word >> 31)
end

function _deterministic_starts(dimension::Int, seed::UInt64;
    count::Int=DEFAULT_START_COUNT)
    count >= 1 || throw(ArgumentError("start count must be positive"))
    starts = Vector{Vector{Float64}}(undef, count)
    starts[1] = zeros(Float64, dimension)
    for ordinal in 2:count
        raw = Vector{Float64}(undef, dimension)
        for coordinate in 1:dimension
            counter = UInt64((ordinal - 2) * dimension + coordinate)
            word = _splitmix64(xor(seed, counter * 0xd2b74407b1ce6e93))
            raw[coordinate] = (Float64(word >> 11) + 0.5) * 0x1.0p-52 - 1.0
        end
        magnitude = norm(raw, 2)
        magnitude > 0 || error("deterministic start generator produced zero")
        radius = 0.2 + 0.4 * mod(ordinal - 2, 7) / 6
        starts[ordinal] = radius .* raw ./ magnitude
        norm(starts[ordinal], 2) <= 0.600000000000001 ||
            error("start escaped frozen ball")
    end
    return starts
end

function _latent_linear_root(dimension::Int, delta::Exact)
    result = Exact[_exact(mod(3index + 1, 7) - 3, 16dimension) for index in 1:dimension]
    result[end] = _exact(1, 4) + delta
    return result
end

function _linear_singular_values(dimension::Int, condition::Int)
    condition in CONDITION_TIERS || throw(ArgumentError("unsupported condition tier"))
    exponent = condition == 10^4 ? 4 : condition == 10^8 ? 8 : 12
    return Exact[
        _exact(1, BigInt(10)^round(Int, exponent * (index - 1) / (dimension - 1)))
        for index in 1:dimension
    ]
end

function _linear_exact_root(model::LinearModel)
    return Vector{Exact}(model.right_rotation * model.latent_root)
end

function _cluster_latent_root(model::ClusteredModel, parameter::Exact)
    dimension = _dimension(model)
    latent = zeros(Exact, dimension)
    for index in 1:(dimension - 1)
        latent[index] = model.quadratic_warp[index] * parameter^2 +
                        model.cubic_warp[index] * parameter^3
    end
    latent[end] = parameter
    return latent
end

function _cluster_exact_roots(model::ClusteredModel)
    return Vector{Vector{Exact}}([
        Vector{Exact}(model.right_rotation * _cluster_latent_root(model, parameter))
        for parameter in model.weak_roots
    ])
end

function _safety_exact_truth(model::SafetyModel)
    dimension = _dimension(model)
    kind = model.kind
    if kind == :stationary_nonroot
        return Vector{Vector{Exact}}(), Vector{Vector{Exact}}()
    elseif kind == :even_multiple_root
        latent = zeros(Exact, dimension)
        latent[end] = model.parameter
        return [Vector{Exact}(model.right_rotation * latent)], Vector{Vector{Exact}}()
    elseif kind == :constant_manifold || kind == :varying_manifold
        witnesses = Vector{Vector{Exact}}()
        for parameter in (_exact(-1, 2), _exact(0), _exact(1, 2))
            latent = zeros(Exact, dimension)
            latent[end] = parameter
            push!(witnesses, Vector{Exact}(model.right_rotation * latent))
        end
        return Vector{Vector{Exact}}(), witnesses
    elseif kind == :branch_crossing || kind == :guard_crossing
        roots = Vector{Vector{Exact}}()
        for parameter in (-model.parameter, model.parameter)
            latent = zeros(Exact, dimension)
            latent[end] = parameter
            push!(roots, Vector{Exact}(model.right_rotation * latent))
        end
        return roots, Vector{Vector{Exact}}()
    end
    error("unknown safety fixture kind")
end

function _truth(model::AbstractFixtureModel, classification::Symbol,
    roots::Vector{Vector{Exact}}, witnesses::Vector{Vector{Exact}})
    targets = Exact[_evaluate(model, root).target for root in roots]
    witness_targets = Exact[_evaluate(model, witness).target for witness in witnesses]
    return AssessorTruth(classification, roots, targets, witnesses, witness_targets)
end

function _candidate(model::AbstractFixtureModel, starts::Vector{Vector{Float64}})
    dimension = _dimension(model)
    float64_evaluator = let frozen_model=model
        function (point::AbstractVector)
            length(point) == dimension || throw(DimensionMismatch("Float64 fixture point"))
            return _evaluate(frozen_model, Float64[point...])
        end
    end
    arbitrary_evaluator = let frozen_model=model
        function (point::AbstractVector)
            length(point) == dimension || throw(DimensionMismatch("arbitrary fixture point"))
            T = eltype(point)
            T <: AbstractFloat || throw(ArgumentError("arbitrary evaluator requires floats"))
            all(isfinite, point) || throw(ArgumentError("fixture point must be finite"))
            return _evaluate(frozen_model, T[point...])
        end
    end
    return TruthBlindFixture(
        FiniteBox(dimension),
        float64_evaluator,
        arbitrary_evaluator,
        [copy(start) for start in starts],
    )
end

_exact_text(value::Exact) = string(numerator(value), '/', denominator(value))
_exact_payload(values::AbstractArray{Exact}) = join((_exact_text(value) for value in values), ',')

function _model_payload(model::LinearModel)
    return join((
        "linear",
        _exact_payload(model.left_rotation),
        _exact_payload(model.right_rotation),
        _exact_payload(model.singular_values),
        _exact_payload(model.latent_root),
        _exact_text(model.delta),
    ), '|')
end

function _model_payload(model::ClusteredModel)
    return join((
        "clustered",
        _exact_payload(model.left_rotation),
        _exact_payload(model.right_rotation),
        _exact_payload(model.weak_roots),
        _exact_text(model.separation),
        _exact_payload(model.quadratic_warp),
        _exact_payload(model.cubic_warp),
    ), '|')
end


function _model_payload(model::SafetyModel)
    return join((
        "safety",
        String(model.kind),
        _exact_payload(model.left_rotation),
        _exact_payload(model.right_rotation),
        _exact_text(model.parameter),
        _exact_text(model.threshold),
    ), '|')
end

function _model_payload(model::ReplicaModel)
    return join((
        "replica",
        _model_payload(model.base),
        _exact_payload(model.variable_rotation),
        _exact_payload(model.residual_rotation),
    ), '|')
end

function _starts_payload(starts::Vector{Vector{Float64}})
    return join((
        join((string(reinterpret(UInt64, value); base=16, pad=16) for value in start), ',')
        for start in starts
    ), ';')
end

function _truth_payload(truth::AssessorTruth)
    root_text = join((_exact_payload(root) for root in truth.isolated_roots), ';')
    witness_text = join((_exact_payload(root) for root in truth.manifold_witnesses), ';')
    return join((
        String(truth.classification),
        root_text,
        _exact_payload(truth.targets),
        witness_text,
        _exact_payload(truth.witness_targets),
    ), '|')
end

function _make_record(
    descriptor::FixtureDescriptor,
    model::M,
    truth::AssessorTruth,
    starts::Vector{Vector{Float64}},
) where {M<:AbstractFixtureModel}
    payload = join((
        "EXP-LOCAL-015-RESCUE-FIXTURE-V1",
        descriptor.fixture_id,
        String(descriptor.stratum),
        string(descriptor.dimension),
        descriptor.parameter_tag,
        _model_payload(model),
        _starts_payload(starts),
        _truth_payload(truth),
    ), '\n')
    return FixtureRecord(
        descriptor,
        _candidate(model, starts),
        truth,
        model,
        payload,
    )
end

function replay_checksum(record::FixtureRecord)
    return bytes2hex(sha256(codeunits(record.checksum_payload)))
end

function corpus_replay_checksum(records::AbstractVector{<:FixtureRecord})
    payload = join((replay_checksum(record) for record in records), "\n")
    return bytes2hex(sha256(codeunits(payload)))
end

function make_linear_fixture(dimension::Integer, condition::Integer;
    delta_exponent::Integer=-160)
    d = Int(dimension)
    d in LINEAR_DIMENSIONS || throw(ArgumentError("unsupported linear dimension"))
    tier = Int(condition)
    tier in CONDITION_TIERS || throw(ArgumentError("unsupported condition tier"))
    delta = _power_of_two(delta_exponent)
    model = LinearModel(
        _rational_orthogonal(d, 11 + d),
        _rational_orthogonal(d, 23 + d),
        _linear_singular_values(d, tier),
        _latent_linear_root(d, delta),
        delta,
    )
    roots = [_linear_exact_root(model)]
    truth = _truth(model, :isolated_simple_full_rank, roots, Vector{Vector{Exact}}())
    descriptor = FixtureDescriptor(
        "linear-d$(d)-k$(tier)-delta2^$(delta_exponent)",
        :ill_conditioned_full_rank,
        d,
        "condition=$(tier);delta_exponent=$(delta_exponent)",
    )
    seed = xor(UInt64(d) << 48, UInt64(tier), UInt64(mod(-delta_exponent, 256)) << 32)
    return _make_record(descriptor, model, truth, _deterministic_starts(d, seed))
end

function make_clustered_fixture(dimension::Integer, root_count::Integer;
    separation_exponent::Integer=-20)
    d = Int(dimension)
    count = Int(root_count)
    d in LINEAR_DIMENSIONS || throw(ArgumentError("unsupported clustered dimension"))
    count in CLUSTER_ROOT_COUNTS || throw(ArgumentError("unsupported clustered root count"))
    separation = _power_of_two(separation_exponent)
    roots = Exact[
        _exact(2index - count - 1, 2) * separation for index in 1:count
    ]
    quadratic = Exact[
        (isodd(index) ? -_exact(1) : _exact(1)) * _exact(index + 1, 8d)
        for index in 1:(d - 1)
    ]
    cubic = Exact[_exact(2index + 1, 16d) for index in 1:(d - 1)]
    model = ClusteredModel(
        _rational_orthogonal(d, 37 + count + d),
        _rational_orthogonal(d, 53 + count + d),
        roots,
        separation,
        quadratic,
        cubic,
    )
    exact_roots = _cluster_exact_roots(model)
    truth = _truth(model, :clustered_simple_roots, exact_roots, Vector{Vector{Exact}}())
    descriptor = FixtureDescriptor(
        "cluster-d$(d)-roots$(count)-sep2^$(separation_exponent)",
        :clustered_weak_lane,
        d,
        "roots=$(count);separation_exponent=$(separation_exponent);curved=true;warped=true",
    )
    seed = xor(UInt64(d) << 48, UInt64(count) << 40,
               UInt64(mod(-separation_exponent, 256)) << 32, 0x434c555354455200)
    return _make_record(descriptor, model, truth, _deterministic_starts(d, seed))
end

function make_safety_fixture(kind::Symbol; dimension::Integer=2)
    kind in SAFETY_KINDS || throw(ArgumentError("unsupported safety fixture"))
    d = Int(dimension)
    d in LINEAR_DIMENSIONS || throw(ArgumentError("unsupported safety dimension"))
    parameter = kind == :stationary_nonroot ? _power_of_two(-12) :
                kind == :even_multiple_root ? _power_of_two(-10) :
                (kind == :branch_crossing || kind == :guard_crossing) ?
                _power_of_two(-19) : _exact(0)
    threshold = _power_of_two(-18)
    ordinal = findfirst(==(kind), SAFETY_KINDS)::Int
    model = SafetyModel(
        kind,
        _rational_orthogonal(d, 71 + ordinal + d),
        _rational_orthogonal(d, 89 + ordinal + d),
        parameter,
        threshold,
    )
    roots, witnesses = _safety_exact_truth(model)
    truth = _truth(model, kind, roots, witnesses)
    descriptor = FixtureDescriptor(
        "safety-$(kind)-d$(d)",
        :safety_control,
        d,
        "kind=$(kind)",
    )
    seed = xor(UInt64(d) << 48, UInt64(ordinal) << 32, 0x5341464554590000)
    return _make_record(descriptor, model, truth, _deterministic_starts(d, seed))
end

function _transform_exact_points(points::Vector{Vector{Exact}}, rotation::Matrix{Exact})
    return Vector{Vector{Exact}}([
        Vector{Exact}(rotation * point) for point in points
    ])
end

function _transform_starts(starts::Vector{Vector{Float64}}, rotation::Matrix{Exact})
    matrix = _convert_exact(Float64, rotation)
    transformed = Vector{Vector{Float64}}([
        Vector{Float64}(matrix * start) for start in starts
    ])
    all(start -> all(value -> -1.0 < value < 1.0, start), transformed) ||
        error("replica start escaped finite box")
    return transformed
end

function _replica_record(record::FixtureRecord, variable::Matrix{Exact}, residual::Matrix{Exact},
    suffix::String, parameter_tag::String)
    dimension = record.descriptor.dimension
    size(variable) == (dimension, dimension) || throw(DimensionMismatch("variable replica"))
    size(residual) == (dimension, dimension) || throw(DimensionMismatch("residual replica"))
    transpose(variable) * variable == _identity_exact(dimension) ||
        throw(ArgumentError("variable replica must be exactly orthogonal"))
    transpose(residual) * residual == _identity_exact(dimension) ||
        throw(ArgumentError("residual replica must be exactly orthogonal"))
    model = ReplicaModel(record.private_model, variable, residual)
    base_truth = record.assessor
    truth = AssessorTruth(
        base_truth.classification,
        _transform_exact_points(base_truth.isolated_roots, variable),
        copy(base_truth.targets),
        _transform_exact_points(base_truth.manifold_witnesses, variable),
        copy(base_truth.witness_targets),
    )
    descriptor = FixtureDescriptor(
        string(record.descriptor.fixture_id, suffix),
        record.descriptor.stratum,
        dimension,
        string(record.descriptor.parameter_tag, ';', parameter_tag),
    )
    starts = _transform_starts(record.candidate.starts, variable)
    return _make_record(descriptor, model, truth, starts)
end

function signed_permutation_replica(record::FixtureRecord;
    variable_shift::Integer=1,
    residual_shift::Integer=2,
    variable_phase::Integer=0,
    residual_phase::Integer=1)
    dimension = record.descriptor.dimension
    variable = _signed_permutation(dimension, Int(variable_shift), Int(variable_phase))
    residual = _signed_permutation(dimension, Int(residual_shift), Int(residual_phase))
    suffix = "__signed-v$(variable_shift)-r$(residual_shift)-vp$(variable_phase)-rp$(residual_phase)"
    tag = "replica=signed_permutation"
    return _replica_record(record, variable, residual, suffix, tag)
end

function orthogonal_replica(record::FixtureRecord;
    variable_tag::Integer=101,
    residual_tag::Integer=211)
    dimension = record.descriptor.dimension
    variable = _rational_orthogonal(dimension, Int(variable_tag))
    residual = _rational_orthogonal(dimension, Int(residual_tag))
    suffix = "__orthogonal-v$(variable_tag)-r$(residual_tag)"
    tag = "replica=orthogonal"
    return _replica_record(record, variable, residual, suffix, tag)
end

function rescue_fixture_corpus()
    records = FixtureRecord[]
    for dimension in LINEAR_DIMENSIONS, condition in CONDITION_TIERS
        push!(records, make_linear_fixture(dimension, condition))
    end
    for dimension in LINEAR_DIMENSIONS, root_count in CLUSTER_ROOT_COUNTS
        push!(records, make_clustered_fixture(dimension, root_count))
    end
    for kind in SAFETY_KINDS
        push!(records, make_safety_fixture(kind))
    end
    return records
end

end
