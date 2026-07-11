const SOLVE_POLICY_VERSION = v"1.1.0"
const _LANE_ORDER = (
    LANE_IID,
    LANE_HEURISTIC,
    LANE_SHELL,
    LANE_PENDING,
    LANE_REFINEMENT,
)

struct _H0Config
    lane_weights::NTuple{5,Int}
    iid_cadence::Int

    function _H0Config(lane_weights::NTuple{5,<:Integer}, iid_cadence::Integer)
        all(>(0), lane_weights) || throw(ArgumentError("all H0 lane weights must be positive"))
        iid_cadence >= 2 || throw(ArgumentError("IID cadence must be at least two"))
        return new(Int.(lane_weights), Int(iid_cadence))
    end
end

struct SolvePolicy
    version::VersionNumber
    preset::Symbol
    wall_seconds::Float64
    budget_limits::BudgetLimits
    _h0::_H0Config

    function SolvePolicy(
        ::Val{:internal},
        preset::Symbol,
        wall_seconds::Real,
        budget_limits::BudgetLimits,
        h0::_H0Config,
    )
        preset in (:fast, :standard, :thorough) ||
            throw(ArgumentError("public policy presets are fast, standard, and thorough"))
        seconds = Float64(wall_seconds)
        isfinite(seconds) && seconds > 0 ||
            throw(ArgumentError("policy wall budget must be finite and positive"))
        return new(SOLVE_POLICY_VERSION, preset, seconds, budget_limits, h0)
    end
end

function _preset_policy(preset::Symbol, seconds::Real, scale::Int)
    h0 = _H0Config((4, 3, 2, 12, 2), 4)
    limits = BudgetLimits(
        proposals=512 * scale,
        local_attempts=512 * scale,
        refinements=128 * scale,
        oracle_work=1_000_000 * scale,
    )
    return SolvePolicy(Val(:internal), preset, seconds, limits, h0)
end

fast_policy() = _preset_policy(:fast, 60.0, 1)
standard_policy() = _preset_policy(:standard, 180.0, 4)
thorough_policy() = _preset_policy(:thorough, 420.0, 16)

mutable struct FairScheduler
    served::Vector{Int}
    total_actions::Int
    next_task_id::UInt64
    shell_ticks::Int

    FairScheduler() = new(zeros(Int, length(_LANE_ORDER)), 0, UInt64(1), 0)
end

struct SchedulerSnapshot
    served::NTuple{5,Int}
    total_actions::Int
    next_task_id::UInt64
    shell_ticks::Int
end

scheduler_snapshot(scheduler::FairScheduler) = SchedulerSnapshot(
    Tuple(scheduler.served),
    scheduler.total_actions,
    scheduler.next_task_id,
    scheduler.shell_ticks,
)

_lane_index(lane::SearchLane) = Int(lane) + 1

function _proposal_count(scheduler::FairScheduler)
    return sum(
        scheduler.served[_lane_index(lane)] for
        lane in (LANE_IID, LANE_HEURISTIC, LANE_SHELL, LANE_REFINEMENT)
    )
end

function _iid_due(scheduler::FairScheduler, cadence::Int)
    proposal_count = _proposal_count(scheduler)
    required_after_next = cld(proposal_count + 1, cadence)
    return scheduler.served[_lane_index(LANE_IID)] < required_after_next
end

function _eligible_lanes(
    ;
    adaptive_unbounded::Bool,
    pending_task_id::Union{Nothing,UInt64},
    refinement_configuration::Union{Nothing,UInt64},
    allow_new_proposals::Bool,
)
    lanes = SearchLane[]
    if allow_new_proposals
        push!(lanes, LANE_IID, LANE_HEURISTIC)
        adaptive_unbounded && push!(lanes, LANE_SHELL)
        refinement_configuration !== nothing && push!(lanes, LANE_REFINEMENT)
    end
    pending_task_id !== nothing && push!(lanes, LANE_PENDING)
    return lanes
end

function _weighted_fair_lane(
    scheduler::FairScheduler,
    config::_H0Config,
    eligible::Vector{SearchLane},
)
    isempty(eligible) && return nothing
    if LANE_IID in eligible && _iid_due(scheduler, config.iid_cadence)
        return LANE_IID
    end

    best = first(eligible)
    for lane in Iterators.drop(eligible, 1)
        lane_count = scheduler.served[_lane_index(lane)] + 1
        best_count = scheduler.served[_lane_index(best)] + 1
        lane_weight = config.lane_weights[_lane_index(lane)]
        best_weight = config.lane_weights[_lane_index(best)]
        left = Int128(lane_count) * Int128(best_weight)
        right = Int128(best_count) * Int128(lane_weight)
        if left < right || (left == right && _lane_index(lane) < _lane_index(best))
            best = lane
        end
    end
    return best
end

"""The binary ruler sequence 0,1,0,2,... revisits every finite shell forever."""
function ruler_shell(shell_tick::Integer)
    shell_tick > 0 || throw(ArgumentError("shell_tick must be positive"))
    return trailing_zeros(UInt(shell_tick))
end

function next_schedule!(
    scheduler::FairScheduler,
    policy::SolvePolicy;
    adaptive_unbounded::Bool,
    pending_task_id::Union{Nothing,UInt64}=nothing,
    refinement_configuration::Union{Nothing,UInt64}=nothing,
    allow_new_proposals::Bool=true,
)
    eligible = _eligible_lanes(
        ;
        adaptive_unbounded,
        pending_task_id,
        refinement_configuration,
        allow_new_proposals,
    )
    lane = _weighted_fair_lane(scheduler, policy._h0, eligible)
    lane === nothing && return nothing
    scheduler.served[_lane_index(lane)] += 1
    scheduler.total_actions += 1

    if lane === LANE_PENDING
        return ScheduleDecision(lane, pending_task_id::UInt64)
    end

    task_id = scheduler.next_task_id
    scheduler.next_task_id += UInt64(1)
    if lane === LANE_SHELL
        scheduler.shell_ticks += 1
        return ScheduleDecision(lane, task_id; shell=ruler_shell(scheduler.shell_ticks))
    elseif lane === LANE_REFINEMENT
        return ScheduleDecision(
            lane,
            task_id;
            source_configuration=refinement_configuration::UInt64,
        )
    end
    return ScheduleDecision(lane, task_id)
end

function iid_prefix_invariant(decisions, cadence::Integer)
    cadence >= 2 || throw(ArgumentError("cadence must be at least two"))
    proposals = 0
    iid = 0
    for decision in decisions
        decision.lane in _PROPOSAL_LANES || continue
        proposals += 1
        iid += decision.lane === LANE_IID
        iid >= cld(proposals, cadence) || return false
    end
    return true
end
