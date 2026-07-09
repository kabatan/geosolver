struct RelationObservation{T,S,V}
    node::NodeId
    raw::T
    scale::S
    scaled::V
    truth::Union{Nothing,Bool}
end

struct GuardObservation{T,S}
    node::NodeId
    margin::T
    strict::Bool
    scale::S
    valid::Bool
end

struct DomainObservation{T}
    node::NodeId
    margin::T
    strict::Bool
    valid::Bool
end

struct BranchObservation{V,S}
    decision::BranchDecision
    validity_margin::V
    selector_margin::S
end

"""Canonical, allocation-tolerant observation used as the semantic reference."""
struct OracleObservation
    relations::Tuple
    target::Any
    guards::Tuple
    domains::Tuple
    branches::Tuple
    status::EvalStatus
    evaluation_cost::Int
    diagnostic::Union{Nothing,String}
end

residual_values(observation::OracleObservation) =
    Tuple(relation.raw for relation in observation.relations)
scaled_residual_values(observation::OracleObservation) =
    Tuple(relation.scaled for relation in observation.relations)

function canonical_feasible(observation::OracleObservation; residual_tolerance::Real)
    residual_tolerance >= 0 || throw(ArgumentError("residual_tolerance must be nonnegative"))
    observation.status == EVAL_OK || return false
    all(guard -> guard.valid, observation.guards) || return false
    all(domain -> domain.valid, observation.domains) || return false
    return all(relation -> abs(relation.scaled) <= residual_tolerance, observation.relations)
end

