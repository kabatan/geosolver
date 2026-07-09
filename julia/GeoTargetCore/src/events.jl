abstract type SearchShellError <: Exception end

struct SearchProtocolError <: SearchShellError
    code::Symbol
    message::String
end

Base.showerror(io::IO, error::SearchProtocolError) =
    print(io, "GeoTarget search protocol ", error.code, ": ", error.message)

@enum SearchLane::UInt8 begin
    LANE_IID = 0
    LANE_HEURISTIC = 1
    LANE_SHELL = 2
    LANE_PENDING = 3
    LANE_REFINEMENT = 4
end

const _PROPOSAL_LANES = (LANE_IID, LANE_HEURISTIC, LANE_SHELL, LANE_REFINEMENT)

@enum SearchLoopStatus::UInt8 begin
    LOOP_RUNNING = 0
    LOOP_DEADLINE_REACHED = 1
    LOOP_CANCELLED = 2
    LOOP_BUDGET_EXHAUSTED = 3
    LOOP_PAUSED = 4
    LOOP_CALLBACK_ERROR = 5
    LOOP_PROTOCOL_ERROR = 6
end

@enum SearchEventKind::UInt8 begin
    EVENT_SCHEDULED = 0
    EVENT_PROPOSED = 1
    EVENT_OBSERVED = 2
    EVENT_BUDGET_CHARGED = 3
    EVENT_STATUS = 4
    EVENT_CALLBACK_FAILED = 5
    EVENT_PROTOCOL_FAILED = 6
end

function _freeze_search_value(value)
    if value === nothing || value isa Number || value isa Symbol || value isa AbstractString ||
       value isa VersionNumber || value isa Enum
        return value isa AbstractString ? String(value) : value
    elseif value isa Pair
        return _freeze_search_value(first(value)) => _freeze_search_value(last(value))
    elseif value isa NamedTuple
        return (; (key => _freeze_search_value(getfield(value, key)) for key in keys(value))...)
    elseif value isa AbstractDict
        pairs = [
            _freeze_search_value(key) => _freeze_search_value(entry) for
            (key, entry) in value
        ]
        sort!(pairs; by=pair -> string(first(pair)))
        return Tuple(pairs)
    elseif value isa Tuple || value isa AbstractVector
        return Tuple(_freeze_search_value(entry) for entry in value)
    end
    isimmutable(value) || throw(
        SearchProtocolError(
            :mutable_payload,
            "event/checkpoint payloads must be recursively immutable, got $(typeof(value))",
        ),
    )
    for field in 1:fieldcount(typeof(value))
        nested = getfield(value, field)
        frozen = _freeze_search_value(nested)
        typeof(frozen) === typeof(nested) || throw(
            SearchProtocolError(
                :nested_mutable_payload,
                "immutable wrapper $(typeof(value)) contains mutable field $(typeof(nested))",
            ),
        )
    end
    return value
end

struct TargetEnclosure
    lower::Float64
    upper::Float64

    function TargetEnclosure(lower::Real, upper::Real=lower)
        lo = Float64(lower)
        hi = Float64(upper)
        isfinite(lo) && isfinite(hi) ||
            throw(ArgumentError("target enclosure bounds must be finite"))
        lo <= hi || throw(ArgumentError("target enclosure lower bound exceeds upper"))
        return new(lo, hi)
    end
end

Base.isless(left::TargetEnclosure, right::TargetEnclosure) =
    (left.lower, left.upper) < (right.lower, right.upper)

overlaps(left::TargetEnclosure, right::TargetEnclosure) =
    max(left.lower, right.lower) <= min(left.upper, right.upper)

struct ScheduleDecision
    lane::SearchLane
    task_id::UInt64
    shell::Union{Nothing,Int}
    source_configuration::Union{Nothing,UInt64}

    function ScheduleDecision(
        lane::SearchLane,
        task_id::Integer;
        shell::Union{Nothing,Integer}=nothing,
        source_configuration::Union{Nothing,Integer}=nothing,
    )
        task_id >= 0 || throw(ArgumentError("task_id must be nonnegative"))
        lane === LANE_SHELL && shell === nothing &&
            throw(ArgumentError("shell proposals require a shell index"))
        lane !== LANE_SHELL && shell !== nothing &&
            throw(ArgumentError("only shell proposals carry a shell index"))
        lane === LANE_REFINEMENT && source_configuration === nothing &&
            throw(ArgumentError("refinement proposals require a source configuration"))
        lane !== LANE_REFINEMENT && source_configuration !== nothing &&
            throw(ArgumentError("only refinement proposals carry a source configuration"))
        frozen_shell = shell === nothing ? nothing : Int(shell)
        frozen_shell !== nothing && frozen_shell < 0 &&
            throw(ArgumentError("shell index must be nonnegative"))
        frozen_source =
            source_configuration === nothing ? nothing : UInt64(source_configuration)
        return new(lane, UInt64(task_id), frozen_shell, frozen_source)
    end
end

struct Proposal
    task_id::UInt64
    configuration_id::UInt64
    lane::SearchLane
    coordinates::Tuple
    shell::Union{Nothing,Int}
    source_configuration::Union{Nothing,UInt64}
    metadata::Tuple

    function Proposal(
        task_id::Integer,
        configuration_id::Integer,
        lane::SearchLane,
        coordinates;
        shell::Union{Nothing,Integer}=nothing,
        source_configuration::Union{Nothing,Integer}=nothing,
        metadata=(),
    )
        task_id > 0 || throw(ArgumentError("task_id must be positive"))
        configuration_id > 0 || throw(ArgumentError("configuration_id must be positive"))
        lane in _PROPOSAL_LANES ||
            throw(ArgumentError("a Proposal cannot use the pending-work lane"))
        decision = ScheduleDecision(
            lane,
            task_id;
            shell,
            source_configuration,
        )
        frozen_coordinates = _freeze_search_value(coordinates)
        frozen_coordinates isa Tuple ||
            throw(ArgumentError("proposal coordinates must be an iterable finite tuple"))
        all(value -> value isa Real && isfinite(value), frozen_coordinates) ||
            throw(ArgumentError("proposal coordinates must be finite real values"))
        frozen_metadata = _freeze_search_value(metadata)
        frozen_metadata isa Tuple || throw(ArgumentError("proposal metadata must freeze to a tuple"))
        return new(
            UInt64(task_id),
            UInt64(configuration_id),
            lane,
            frozen_coordinates,
            decision.shell,
            decision.source_configuration,
            frozen_metadata,
        )
    end
end

struct Observation
    task_id::UInt64
    configuration_id::UInt64
    canonical_near_feasible::Bool
    canonical_valid::Bool
    target::Union{Nothing,TargetEnclosure}
    target_identity::Union{Nothing,String}
    branch_signature::Tuple
    verified::Bool
    verified_payload::Any
    needs_refinement::Bool
    residual_score::Float64
    oracle_work::Int
    diagnostic::Union{Nothing,String}

    function Observation(
        task_id::Integer,
        configuration_id::Integer;
        canonical_near_feasible::Bool,
        canonical_valid::Bool=false,
        target::Union{Nothing,TargetEnclosure}=nothing,
        target_identity::Union{Nothing,AbstractString}=nothing,
        branch_signature=(),
        verified::Bool=false,
        verified_payload=nothing,
        needs_refinement::Bool=false,
        residual_score::Real=Inf,
        oracle_work::Integer=0,
        diagnostic::Union{Nothing,AbstractString}=nothing,
    )
        task_id > 0 || throw(ArgumentError("task_id must be positive"))
        configuration_id > 0 || throw(ArgumentError("configuration_id must be positive"))
        canonical_valid && !canonical_near_feasible && throw(
            SearchProtocolError(
                :valid_without_near_feasible,
                "canonical validity implies canonical near-feasibility",
            ),
        )
        target !== nothing && !canonical_near_feasible && throw(
            SearchProtocolError(
                :target_before_near_feasible,
                "target values may be observed only after canonical near-feasibility",
            ),
        )
        target_identity !== nothing && target === nothing && throw(
            SearchProtocolError(
                :identity_without_target,
                "target identity requires a canonical near-feasible target observation",
            ),
        )
        verified && (!canonical_valid || target === nothing || verified_payload === nothing) && throw(
            SearchProtocolError(
                :unverified_answer,
                "verified output requires canonical validity, a target, and immutable evidence",
            ),
        )
        score = Float64(residual_score)
        (isfinite(score) || score == Inf) && score >= 0 ||
            throw(ArgumentError("residual_score must be nonnegative or +Inf"))
        oracle_work >= 0 || throw(ArgumentError("oracle_work must be nonnegative"))
        branches = _freeze_search_value(branch_signature)
        branches isa Tuple || throw(ArgumentError("branch_signature must freeze to a tuple"))
        payload = _freeze_search_value(verified_payload)
        return new(
            UInt64(task_id),
            UInt64(configuration_id),
            canonical_near_feasible,
            canonical_valid,
            target,
            target_identity === nothing ? nothing : String(target_identity),
            branches,
            verified,
            payload,
            needs_refinement,
            score,
            Int(oracle_work),
            diagnostic === nothing ? nothing : String(diagnostic),
        )
    end
end

struct EvidenceEvent
    sequence::Int
    kind::SearchEventKind
    payload::Any
end

mutable struct EvidenceLog
    _events::Vector{EvidenceEvent}
    _next_sequence::Int

    EvidenceLog() = new(EvidenceEvent[], 1)
end

function record_event!(log::EvidenceLog, kind::SearchEventKind, payload)
    event = EvidenceEvent(log._next_sequence, kind, _freeze_search_value(payload))
    push!(log._events, event)
    log._next_sequence += 1
    return event
end

evidence_events(log::EvidenceLog) = Tuple(log._events)

struct BudgetLimits
    proposals::Union{Nothing,Int}
    local_attempts::Union{Nothing,Int}
    refinements::Union{Nothing,Int}
    oracle_work::Union{Nothing,Int}

    function BudgetLimits(;
        proposals::Union{Nothing,Integer}=nothing,
        local_attempts::Union{Nothing,Integer}=nothing,
        refinements::Union{Nothing,Integer}=nothing,
        oracle_work::Union{Nothing,Integer}=nothing,
    )
        values = (proposals, local_attempts, refinements, oracle_work)
        any(value -> value !== nothing && value < 0, values) &&
            throw(ArgumentError("budget limits must be nonnegative"))
        return new(
            proposals === nothing ? nothing : Int(proposals),
            local_attempts === nothing ? nothing : Int(local_attempts),
            refinements === nothing ? nothing : Int(refinements),
            oracle_work === nothing ? nothing : Int(oracle_work),
        )
    end
end

struct BudgetCharge
    proposals::Int
    local_attempts::Int
    refinements::Int
    oracle_work::Int

    function BudgetCharge(;
        proposals::Integer=0,
        local_attempts::Integer=0,
        refinements::Integer=0,
        oracle_work::Integer=0,
    )
        values = (proposals, local_attempts, refinements, oracle_work)
        any(value -> value < 0, values) &&
            throw(ArgumentError("budget charges must be nonnegative"))
        return new(Int.(values)...)
    end
end

mutable struct BudgetLedger
    limits::BudgetLimits
    proposals::Int
    local_attempts::Int
    refinements::Int
    oracle_work::Int

    BudgetLedger(limits::BudgetLimits) = new(limits, 0, 0, 0, 0)
end

struct BudgetSnapshot
    limits::BudgetLimits
    proposals::Int
    local_attempts::Int
    refinements::Int
    oracle_work::Int
end

budget_snapshot(ledger::BudgetLedger) = BudgetSnapshot(
    ledger.limits,
    ledger.proposals,
    ledger.local_attempts,
    ledger.refinements,
    ledger.oracle_work,
)

function _within_limit(current::Int, addition::Int, limit::Union{Nothing,Int})
    return limit === nothing || current + addition <= limit
end

function can_charge(ledger::BudgetLedger, charge::BudgetCharge)
    return _within_limit(ledger.proposals, charge.proposals, ledger.limits.proposals) &&
           _within_limit(
        ledger.local_attempts,
        charge.local_attempts,
        ledger.limits.local_attempts,
    ) &&
           _within_limit(ledger.refinements, charge.refinements, ledger.limits.refinements) &&
           _within_limit(ledger.oracle_work, charge.oracle_work, ledger.limits.oracle_work)
end

function charge!(ledger::BudgetLedger, charge::BudgetCharge)
    can_charge(ledger, charge) || throw(
        SearchProtocolError(:budget_exceeded, "budget charge exceeds a typed hard limit"),
    )
    ledger.proposals += charge.proposals
    ledger.local_attempts += charge.local_attempts
    ledger.refinements += charge.refinements
    ledger.oracle_work += charge.oracle_work
    return ledger
end
