const PROPOSAL_ENGINE_VERSION = v"1.0.0"
const _HALTON_DIMENSION_LIMIT = 64
const _FLOAT64_MAX = floatmax(Float64)
const _LOG_FLOAT64_MAX = log(_FLOAT64_MAX)

struct ProposalEngineError <: SearchShellError
    code::Symbol
    message::String
end

Base.showerror(io::IO, error::ProposalEngineError) =
    print(io, "GeoTarget proposal engine ", error.code, ": ", error.message)

@enum _VariableDomain::UInt8 begin
    _BOUNDED = 0
    _LOWER_UNBOUNDED = 1
    _UPPER_UNBOUNDED = 2
    _TWO_SIDED_UNBOUNDED = 3
end

struct _ProposalVariable
    origin::Float64
    scale::Float64
    lower::Union{Nothing,Float64}
    upper::Union{Nothing,Float64}
    domain::_VariableDomain
end

"""
Immutable, counter-only proposal generator that stores no graph or plugin data.

IID coordinates are keyed by seed/task/dimension/stream. Bounded variables use
uniform coordinates; unbounded directions use a local Pareto/log-uniform
mixture with support across finite Float64 magnitude bands. The heuristic lane
uses task-indexed Halton points through 64 dimensions and a counter-uniform
fallback for the whole vector above that documented limit.
"""
struct ProposalEngine
    seed::UInt64
    variables::Tuple
    unbounded_dimensions::Tuple{Vararg{Int}}
end

function _proposal_float64(value::Real, label::AbstractString)
    converted = try
        Float64(value)
    catch error
        throw(
            ProposalEngineError(
                :unrepresentable_variable,
                "$label cannot be represented as Float64: $(sprint(showerror, error))",
            ),
        )
    end
    isfinite(converted) || throw(
        ProposalEngineError(
            :unrepresentable_variable,
            "$label must have a finite Float64 representation",
        ),
    )
    return converted
end

function _proposal_variable(variable)
    origin = _proposal_float64(variable.origin, "variable origin")
    scale = _proposal_float64(variable.scale, "variable scale")
    scale > 0 || throw(
        ProposalEngineError(
            :unrepresentable_scale,
            "variable scale underflowed or is not positive in Float64",
        ),
    )
    lower = variable.lower === nothing ? nothing :
            _proposal_float64(variable.lower, "variable lower bound")
    upper = variable.upper === nothing ? nothing :
            _proposal_float64(variable.upper, "variable upper bound")
    lower !== nothing && upper !== nothing && lower >= upper && throw(
        ProposalEngineError(:degenerate_bounds, "variable bounds are not strictly ordered"),
    )
    lower !== nothing && origin < lower && throw(
        ProposalEngineError(:origin_outside_bounds, "origin lies below the lower bound"),
    )
    upper !== nothing && origin > upper && throw(
        ProposalEngineError(:origin_outside_bounds, "origin lies above the upper bound"),
    )
    domain = if lower !== nothing && upper !== nothing
        _BOUNDED
    elseif lower !== nothing
        origin < _FLOAT64_MAX || throw(
            ProposalEngineError(
                :unrepresentable_tail,
                "a lower-bounded variable at floatmax has no finite outward support",
            ),
        )
        _LOWER_UNBOUNDED
    elseif upper !== nothing
        origin > -_FLOAT64_MAX || throw(
            ProposalEngineError(
                :unrepresentable_tail,
                "an upper-bounded variable at -floatmax has no finite outward support",
            ),
        )
        _UPPER_UNBOUNDED
    else
        _TWO_SIDED_UNBOUNDED
    end
    return _ProposalVariable(origin, scale, lower, upper, domain)
end

function ProposalEngine(problem::ProblemSpecV1; seed::Integer=0)
    seed >= 0 || throw(ArgumentError("proposal seed must be nonnegative"))
    isempty(problem.variables) && throw(
        ProposalEngineError(:zero_dimension, "proposal generation requires at least one variable"),
    )
    variables = Tuple(_proposal_variable(variable) for variable in problem.variables)
    unbounded = Tuple(
        index for index in eachindex(variables) if variables[index].domain !== _BOUNDED
    )
    return ProposalEngine(UInt64(seed), variables, unbounded)
end

function _mix64(value::UInt64)
    mixed = value + 0x9e3779b97f4a7c15
    mixed = (mixed ⊻ (mixed >> 30)) * 0xbf58476d1ce4e5b9
    mixed = (mixed ⊻ (mixed >> 27)) * 0x94d049bb133111eb
    return mixed ⊻ (mixed >> 31)
end

function _counter_word(
    engine::ProposalEngine,
    task_id::UInt64,
    dimension::Int,
    stream::UInt64,
)
    return _mix64(
        engine.seed ⊻
        (task_id * 0xd2b74407b1ce6e93) ⊻
        (UInt64(dimension) * 0xca5a826395121157) ⊻
        (stream * 0x9e3779b97f4a7c15),
    )
end

"""An open-interval uniform variate with 52 counter-derived mantissa bits."""
function _counter_unit(
    engine::ProposalEngine,
    task_id::UInt64,
    dimension::Int,
    stream::UInt64,
)
    mantissa = _counter_word(engine, task_id, dimension, stream) >> 12
    return (Float64(mantissa) + 0.5) * 0x1.0p-52
end

function _stable_bounded_uniform(lower::Float64, upper::Float64, unit::Float64)
    midpoint = lower / 2 + upper / 2
    if unit <= 0.5
        value = lower + (midpoint - lower) * (2 * unit)
    else
        value = midpoint + (upper - midpoint) * (2 * unit - 1)
    end
    isfinite(value) || (value = unit < 0.5 ? lower : upper)
    return clamp(value, lower, upper)
end

function _clamp_variable(value::Float64, variable::_ProposalVariable)
    isfinite(value) || throw(
        ProposalEngineError(:nonfinite_coordinate, "internal transform produced a nonfinite value"),
    )
    variable.lower !== nothing && (value = max(value, variable.lower))
    variable.upper !== nothing && (value = min(value, variable.upper))
    isfinite(value) || throw(
        ProposalEngineError(:nonfinite_coordinate, "bound projection produced a nonfinite value"),
    )
    return value
end

function _saturating_offset(
    center::Float64,
    scale::Float64,
    normalized::Float64,
    variable::_ProposalVariable,
)
    isfinite(normalized) || throw(
        ProposalEngineError(:nonfinite_normalized, "normalized coordinate must be finite"),
    )
    magnitude = abs(normalized)
    delta = if magnitude == 0
        0.0
    elseif magnitude > _FLOAT64_MAX / scale
        copysign(_FLOAT64_MAX, normalized)
    else
        scale * normalized
    end
    value = center + delta
    if !isfinite(value)
        value = copysign(_FLOAT64_MAX, delta)
    end
    return _clamp_variable(value, variable)
end

function _heavy_radius(
    engine::ProposalEngine,
    task_id::UInt64,
    dimension::Int,
)
    selector = _counter_word(engine, task_id, dimension, UInt64(0x31)) & UInt64(0xff)
    unit = _counter_unit(engine, task_id, dimension, UInt64(0x32))
    if selector == 0
        # A 1/256 component is log-uniform across the finite Float64 exponent range.
        # It gives every representable magnitude band positive counter probability.
        radius = exp(unit * _LOG_FLOAT64_MAX) - 1
        return isfinite(radius) ? radius : _FLOAT64_MAX
    end
    # The common component is a local Pareto(1)-like tail.
    return unit / (1 - unit)
end

function _iid_coordinate(
    engine::ProposalEngine,
    variable::_ProposalVariable,
    task_id::UInt64,
    dimension::Int,
)
    unit = _counter_unit(engine, task_id, dimension, UInt64(0x11))
    if variable.domain === _BOUNDED
        return _stable_bounded_uniform(variable.lower, variable.upper, unit)
    end

    direction_word = _counter_word(engine, task_id, dimension, UInt64(0x12))
    radius = _heavy_radius(engine, task_id, dimension)
    if variable.domain === _LOWER_UNBOUNDED
        if isodd(direction_word) && variable.origin > variable.lower
            return _stable_bounded_uniform(variable.lower, variable.origin, unit)
        end
        return _saturating_offset(variable.origin, variable.scale, radius, variable)
    elseif variable.domain === _UPPER_UNBOUNDED
        if isodd(direction_word) && variable.origin < variable.upper
            return _stable_bounded_uniform(variable.origin, variable.upper, unit)
        end
        return _saturating_offset(variable.origin, variable.scale, -radius, variable)
    end
    signed_radius = isodd(direction_word) ? radius : -radius
    return _saturating_offset(variable.origin, variable.scale, signed_radius, variable)
end

const _HALTON_PRIMES = (
    2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37, 41, 43, 47, 53,
    59, 61, 67, 71, 73, 79, 83, 89, 97, 101, 103, 107, 109, 113, 127, 131,
    137, 139, 149, 151, 157, 163, 167, 173, 179, 181, 191, 193, 197, 199,
    211, 223, 227, 229, 233, 239, 241, 251, 257, 263, 269, 271, 277, 281,
    283, 293, 307, 311,
)

function _radical_inverse(index::UInt64, base::Int)
    factor = inv(Float64(base))
    result = 0.0
    remaining = index
    while remaining > 0
        digit = remaining % UInt64(base)
        result += Float64(digit) * factor
        remaining ÷= UInt64(base)
        factor /= base
    end
    return clamp(result, 0x1.0p-53, 1 - 0x1.0p-53)
end

function _normalized_interval(variable::_ProposalVariable)
    if variable.domain === _BOUNDED
        return variable.lower, variable.upper
    elseif variable.domain === _LOWER_UNBOUNDED
        high = _saturating_offset(variable.origin, variable.scale, 1.0, variable)
        high <= variable.lower && (high = nextfloat(variable.lower))
        return variable.lower, high
    elseif variable.domain === _UPPER_UNBOUNDED
        low = _saturating_offset(variable.origin, variable.scale, -1.0, variable)
        low >= variable.upper && (low = prevfloat(variable.upper))
        return low, variable.upper
    end
    low = _saturating_offset(variable.origin, variable.scale, -1.0, variable)
    high = _saturating_offset(variable.origin, variable.scale, 1.0, variable)
    if low >= high
        low = prevfloat(variable.origin)
        high = nextfloat(variable.origin)
    end
    return low, high
end

function _heuristic_coordinate(
    engine::ProposalEngine,
    variable::_ProposalVariable,
    task_id::UInt64,
    dimension::Int,
    use_halton::Bool,
)
    unit = if use_halton
        _radical_inverse(task_id, _HALTON_PRIMES[dimension])
    else
        _counter_unit(engine, task_id, dimension, UInt64(0x21))
    end
    lower, upper = _normalized_interval(variable)
    lower < upper || return _clamp_variable(variable.origin, variable)
    return _stable_bounded_uniform(lower, upper, unit)
end

function _normalized_distance(value::Float64, variable::_ProposalVariable)
    distance = abs(value - variable.origin)
    return distance / variable.scale
end


function _shell_capacity(variable::_ProposalVariable)
    if variable.domain === _LOWER_UNBOUNDED
        return (_FLOAT64_MAX - variable.origin) / variable.scale
    elseif variable.domain === _UPPER_UNBOUNDED
        return (variable.origin - (-_FLOAT64_MAX)) / variable.scale
    elseif variable.domain === _TWO_SIDED_UNBOUNDED
        positive = (_FLOAT64_MAX - variable.origin) / variable.scale
        negative = (variable.origin - (-_FLOAT64_MAX)) / variable.scale
        return max(positive, negative)
    end
    return 0.0
end

function _shell_bounds(shell::Int)
    0 <= shell <= 1022 || throw(
        ProposalEngineError(
            :unrepresentable_shell,
            "shell index $shell is outside the finite Float64 dyadic range 0:1022",
        ),
    )
    outer = ldexp(1.0, shell)
    inner = shell == 0 ? 0.0 : ldexp(1.0, shell - 1)
    return inner, outer
end

function _shell_coordinate(
    engine::ProposalEngine,
    variable::_ProposalVariable,
    task_id::UInt64,
    dimension::Int,
    inner::Float64,
    outer::Float64,
    anchor::Bool,
)
    unit = _counter_unit(engine, task_id, dimension, UInt64(0x41))
    if variable.domain === _BOUNDED
        return _stable_bounded_uniform(variable.lower, variable.upper, unit)
    end
    radius = anchor ? inner + (outer - inner) * unit : outer * unit
    direction_word = _counter_word(engine, task_id, dimension, UInt64(0x42))
    signed = if variable.domain === _LOWER_UNBOUNDED
        radius
    elseif variable.domain === _UPPER_UNBOUNDED
        -radius
    else
        isodd(direction_word) ? radius : -radius
    end
    coordinate = _saturating_offset(variable.origin, variable.scale, signed, variable)
    if anchor && _normalized_distance(coordinate, variable) < inner &&
       variable.domain === _TWO_SIDED_UNBOUNDED
        coordinate = _saturating_offset(
            variable.origin,
            variable.scale,
            -signed,
            variable,
        )
    end
    if anchor && _normalized_distance(coordinate, variable) < inner
        throw(
            ProposalEngineError(
                :unrepresentable_shell,
                "variable metadata cannot represent requested shell with finite coordinates",
            ),
        )
    end
    return coordinate
end

function _latest_source_record(context, configuration::UInt64)
    for record in latest_candidates(context.workspace.candidates)
        record.observation.configuration_id == configuration && return record
    end
    throw(
        ProposalEngineError(
            :missing_refinement_source,
            "configuration $configuration is absent from CandidateStore",
        ),
    )
end

function _finite_source_coordinate(
    value,
    dimension::Int,
    variable::_ProposalVariable,
)
    value isa Real || throw(
        ProposalEngineError(
            :invalid_refinement_source,
            "source coordinate $dimension is not real",
        ),
    )
    coordinate = _proposal_float64(value, "refinement source coordinate $dimension")
    variable.lower !== nothing && coordinate < variable.lower && throw(
        ProposalEngineError(
            :invalid_refinement_source,
            "source coordinate $dimension lies below its variable bound",
        ),
    )
    variable.upper !== nothing && coordinate > variable.upper && throw(
        ProposalEngineError(
            :invalid_refinement_source,
            "source coordinate $dimension lies above its variable bound",
        ),
    )
    return coordinate
end

function _refined_coordinate(
    engine::ProposalEngine,
    variable::_ProposalVariable,
    source::Float64,
    task_id::UInt64,
    dimension::Int,
    revision::Int,
)
    exponent = -min(revision, 1022)
    radius = ldexp(1.0, exponent)
    unit = _counter_unit(engine, task_id, dimension, UInt64(0x51))
    direction = 2 * unit - 1
    refined = _saturating_offset(source, variable.scale, radius * direction, variable)
    if refined == source && direction != 0
        neighbor = direction > 0 ? nextfloat(source) : prevfloat(source)
        isfinite(neighbor) && (refined = _clamp_variable(neighbor, variable))
    end
    return refined
end

function _proposal_metadata(entries::Pair...)
    return Tuple(entries)
end

function emit_proposal(
    engine::ProposalEngine,
    context::ExecutionContext,
    decision::ScheduleDecision,
)
    decision.lane in _PROPOSAL_LANES || throw(
        ProposalEngineError(:pending_not_proposal, "pending work does not emit a new Proposal"),
    )
    dimension = length(engine.variables)
    coordinates = Vector{Float64}(undef, dimension)
    configuration_id = decision.task_id
    metadata = if decision.lane === LANE_IID
        for index in 1:dimension
            coordinates[index] = _iid_coordinate(
                engine,
                engine.variables[index],
                decision.task_id,
                index,
            )
        end
        _proposal_metadata(
            :engine_version => PROPOSAL_ENGINE_VERSION,
            :seed => engine.seed,
            :sequence => :counter_iid,
            :tail => :pareto_log_uniform_mixture,
        )
    elseif decision.lane === LANE_HEURISTIC
        use_halton = dimension <= _HALTON_DIMENSION_LIMIT
        for index in 1:dimension
            coordinates[index] = _heuristic_coordinate(
                engine,
                engine.variables[index],
                decision.task_id,
                index,
                use_halton,
            )
        end
        sequence = use_halton ? :halton : :counter_fallback
        _proposal_metadata(
            :engine_version => PROPOSAL_ENGINE_VERSION,
            :seed => engine.seed,
            :sequence => sequence,
            :halton_dimension_limit => _HALTON_DIMENSION_LIMIT,
            :index_source => :task_id,
        )
    elseif decision.lane === LANE_SHELL
        isempty(engine.unbounded_dimensions) && throw(
            ProposalEngineError(
                :shell_on_bounded_problem,
                "shell proposals require at least one unbounded variable",
            ),
        )
        shell = decision.shell::Int
        inner, outer = _shell_bounds(shell)
        eligible_anchors = Tuple(
            index for index in engine.unbounded_dimensions if
            _shell_capacity(engine.variables[index]) >= inner
        )
        isempty(eligible_anchors) && throw(
            ProposalEngineError(
                :unrepresentable_shell,
                "no unbounded variable can represent shell $shell with finite coordinates",
            ),
        )
        word = _counter_word(engine, decision.task_id, 0, UInt64(0x43))
        anchor_position = Int(mod(word, UInt64(length(eligible_anchors)))) + 1
        anchor_dimension = eligible_anchors[anchor_position]
        for index in 1:dimension
            coordinates[index] = _shell_coordinate(
                engine,
                engine.variables[index],
                decision.task_id,
                index,
                inner,
                outer,
                index == anchor_dimension,
            )
        end
        _proposal_metadata(
            :engine_version => PROPOSAL_ENGINE_VERSION,
            :seed => engine.seed,
            :sequence => :dyadic_ruler_shell,
            :shell => shell,
            :normalized_inner => inner,
            :normalized_outer => outer,
            :anchor_dimension => anchor_dimension,
            :shell_space => :unbounded_dimensions_max_norm,
        )
    else
        source_configuration = decision.source_configuration::UInt64
        record = _latest_source_record(context, source_configuration)
        length(record.proposal.coordinates) == dimension || throw(
            ProposalEngineError(
                :refinement_dimension_mismatch,
                "source coordinate dimension does not match ProposalEngine",
            ),
        )
        for index in 1:dimension
            source = _finite_source_coordinate(
                record.proposal.coordinates[index],
                index,
                engine.variables[index],
            )
            coordinates[index] = _refined_coordinate(
                engine,
                engine.variables[index],
                source,
                decision.task_id,
                index,
                record.revision,
            )
        end
        configuration_id = source_configuration
        _proposal_metadata(
            :engine_version => PROPOSAL_ENGINE_VERSION,
            :seed => engine.seed,
            :sequence => :deterministic_refinement,
            :source_revision => record.revision,
            :normalized_radius => ldexp(1.0, -min(record.revision, 1022)),
        )
    end
    all(isfinite, coordinates) || throw(
        ProposalEngineError(:nonfinite_coordinate, "proposal coordinates must all be finite"),
    )
    return Proposal(
        decision.task_id,
        configuration_id,
        decision.lane,
        Tuple(coordinates);
        shell=decision.shell,
        source_configuration=decision.source_configuration,
        metadata,
    )
end

(engine::ProposalEngine)(context::ExecutionContext, decision::ScheduleDecision) =
    emit_proposal(engine, context, decision)
