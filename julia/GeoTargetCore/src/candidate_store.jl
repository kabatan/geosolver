struct CandidateRecord
    revision::Int
    proposal::Proposal
    observation::Observation
end

struct TargetNiche
    branch_signature::Tuple
    intersection::TargetEnclosure
    configurations::Tuple{Vararg{UInt64}}
end

struct VerifiedTarget
    key::String
    identity::Union{Nothing,String}
    target::TargetEnclosure
    witnesses::Tuple{Vararg{UInt64}}
    payloads::Tuple
end

mutable struct CandidateStore
    _history::Vector{CandidateRecord}
    _latest::Dict{UInt64,CandidateRecord}
    _seen_tasks::Set{UInt64}
    _niches::Vector{TargetNiche}
    _x_reservoir::Vector{UInt64}
    _verified::Dict{String,VerifiedTarget}

    CandidateStore() = new(
        CandidateRecord[],
        Dict{UInt64,CandidateRecord}(),
        Set{UInt64}(),
        TargetNiche[],
        UInt64[],
        Dict{String,VerifiedTarget}(),
    )
end

function _branch_sort_key(branch_signature::Tuple)
    return join(string.(branch_signature), "\u001f")
end

function _rebuild_candidate_views!(store::CandidateStore)
    empty!(store._niches)
    empty!(store._x_reservoir)

    target_records = CandidateRecord[]
    for configuration in sort!(collect(keys(store._latest)))
        record = store._latest[configuration]
        if record.observation.target === nothing
            push!(store._x_reservoir, configuration)
        elseif record.observation.canonical_near_feasible
            push!(target_records, record)
        end
    end
    sort!(
        target_records;
        by=record -> (
            _branch_sort_key(record.observation.branch_signature),
            record.observation.target.lower,
            record.observation.target.upper,
            record.observation.configuration_id,
        ),
    )

    for record in target_records
        observation = record.observation
        target = observation.target::TargetEnclosure
        matched = nothing
        for (index, niche) in enumerate(store._niches)
            if niche.branch_signature == observation.branch_signature &&
               overlaps(niche.intersection, target)
                matched = index
                break
            end
        end
        if matched === nothing
            push!(
                store._niches,
                TargetNiche(
                    observation.branch_signature,
                    target,
                    (observation.configuration_id,),
                ),
            )
        else
            niche = store._niches[matched]
            intersection = TargetEnclosure(
                max(niche.intersection.lower, target.lower),
                min(niche.intersection.upper, target.upper),
            )
            configurations = Tuple(
                sort!(unique([niche.configurations...; observation.configuration_id])),
            )
            store._niches[matched] =
                TargetNiche(niche.branch_signature, intersection, configurations)
        end
    end
    sort!(
        store._niches;
        by=niche -> (
            _branch_sort_key(niche.branch_signature),
            niche.intersection.lower,
            niche.intersection.upper,
            niche.configurations,
        ),
    )
    return store
end

function _verified_key(observation::Observation)
    observation.target === nothing && throw(
        SearchProtocolError(:verified_without_target, "verified candidates require a target"),
    )
    if observation.target_identity !== nothing
        return "identity:" * observation.target_identity
    end
    # Numerical equality or overlap is not an irreversible target identity.
    # Without proof supplied by the validator, retain one output identity per
    # configuration and let reversible niches guide scheduling only.
    return "configuration:" * string(observation.configuration_id)
end

function _record_verified!(store::CandidateStore, observation::Observation)
    observation.verified || return store
    key = _verified_key(observation)
    target = observation.target::TargetEnclosure
    existing = get(store._verified, key, nothing)
    if existing === nothing
        store._verified[key] = VerifiedTarget(
            key,
            observation.target_identity,
            target,
            (observation.configuration_id,),
            (observation.verified_payload,),
        )
        return store
    end
    overlaps(existing.target, target) || throw(
        SearchProtocolError(
            :inconsistent_verified_identity,
            "one verified target identity received disjoint enclosures",
        ),
    )
    observation.configuration_id in existing.witnesses && return store
    witnesses = (existing.witnesses..., observation.configuration_id)
    order = sortperm(collect(eachindex(witnesses)); by=index -> witnesses[index])
    payloads = (existing.payloads..., observation.verified_payload)
    store._verified[key] = VerifiedTarget(
        existing.key,
        existing.identity,
        existing.target,
        Tuple(witnesses[index] for index in order),
        Tuple(payloads[index] for index in order),
    )
    return store
end

function _validate_verified_consistency(store::CandidateStore, observation::Observation)
    observation.verified || return nothing
    key = _verified_key(observation)
    existing = get(store._verified, key, nothing)
    existing === nothing && return nothing
    overlaps(existing.target, observation.target::TargetEnclosure) || throw(
        SearchProtocolError(
            :inconsistent_verified_identity,
            "one verified target identity received disjoint enclosures",
        ),
    )
    return nothing
end

function insert_candidate!(
    store::CandidateStore,
    proposal::Proposal,
    observation::Observation,
)
    proposal.task_id == observation.task_id || throw(
        SearchProtocolError(:task_mismatch, "proposal and observation task IDs differ"),
    )
    proposal.configuration_id == observation.configuration_id || throw(
        SearchProtocolError(
            :configuration_mismatch,
            "proposal and observation configuration IDs differ",
        ),
    )
    proposal.task_id in store._seen_tasks && throw(
        SearchProtocolError(:duplicate_task, "task $(proposal.task_id) was already observed"),
    )
    _validate_verified_consistency(store, observation)
    push!(store._seen_tasks, proposal.task_id)
    revision = if haskey(store._latest, proposal.configuration_id)
        store._latest[proposal.configuration_id].revision + 1
    else
        1
    end
    record = CandidateRecord(revision, proposal, observation)
    push!(store._history, record)
    store._latest[proposal.configuration_id] = record
    _record_verified!(store, observation)
    _rebuild_candidate_views!(store)
    return record
end

candidate_records(store::CandidateStore) = Tuple(store._history)
latest_candidates(store::CandidateStore) = Tuple(
    store._latest[key] for key in sort!(collect(keys(store._latest)))
)
target_niches(store::CandidateStore) = Tuple(store._niches)
x_reservoir(store::CandidateStore) = Tuple(store._x_reservoir)
verified_answers(store::CandidateStore) = Tuple(
    store._verified[key] for key in sort!(collect(keys(store._verified)))
)

struct CandidateStoreSnapshot
    history::Tuple
    latest::Tuple
    niches::Tuple
    x_reservoir::Tuple{Vararg{UInt64}}
    verified::Tuple
end

candidate_snapshot(store::CandidateStore) = CandidateStoreSnapshot(
    candidate_records(store),
    latest_candidates(store),
    target_niches(store),
    x_reservoir(store),
    verified_answers(store),
)
