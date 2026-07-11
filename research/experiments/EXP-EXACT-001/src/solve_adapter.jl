struct ExactReplayRecord
    task_id::UInt64
    answer::ExactAnswer
    verification::GeoTargetCore.ExactVerificationResult
end

struct ExactCampaignRun
    execution::GeoTargetCore.SolveExecution
    replay_records::Tuple
end

function _stored_binding(observation)
    return StoredExactObservation(
        observation.target.lower,
        observation.target.upper,
        observation.target_identity,
        observation.branch_signature,
        observation.endpoint,
    )
end

"""Re-run the provider-free verifier and retain failures as explicit records."""
function replay_returned_exact_answers(compiled, execution, backend)
    records = ExactReplayRecord[]
    for candidate in execution.checkpoint.workspace.candidates.history
        observation = candidate.observation
        payload = observation.verified_payload
        payload isa ExactAnswer || continue
        verification = verify_stored_exact_answer(
            backend,
            compiled,
            payload;
            observation=_stored_binding(observation),
        )
        push!(records, ExactReplayRecord(candidate.proposal.task_id, payload, verification))
    end
    return Tuple(records)
end

function run_exact_case(
    compiled;
    seed::Integer=0,
    wall_seconds::Real=60.0,
    max_actions::Integer=2,
    backend=NemoExactBackend(),
)
    options = SolveOptions(
        preset=:fast,
        wall_seconds=wall_seconds,
        seed=seed,
        answer_level=:exact_if_available,
        worker_count=1,
    )
    execution = solve_execution(
        compiled.problem,
        compiled.registry;
        options,
        max_actions,
        exact_backend=backend,
    )
    return ExactCampaignRun(
        execution,
        replay_returned_exact_answers(compiled, execution, backend),
    )
end

