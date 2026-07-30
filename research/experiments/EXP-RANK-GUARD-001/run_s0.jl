#!/usr/bin/env julia

using JSON3
using LinearAlgebra
using SHA

include(joinpath(@__DIR__, "src", "RankGuardPrototype.jl"))
const RG = RankGuardPrototype
const LAB = RG.LAB
const FIX = LAB.FIXTURES

const ARM_ORDER = (
    "BASELINE-NO-RESCUE",
    LAB.ADAPTIVE_ARM,
    LAB.WEAK_ADAPTIVE_ARM,
    "WEAK-SINGULAR-PAIR",
    "WEAK-SINGULAR-PAIR-GUARD-CHART",
)

function _arguments(arguments)
    length(arguments) == 2 && arguments[1] == "--output" || error("--output PATH is required")
    return abspath(arguments[2])
end

function _records()
    bases = Any[
        FIX.make_linear_fixture(2, 10^12),
        FIX.make_clustered_fixture(2, 4),
        FIX.make_safety_fixture(:stationary_nonroot),
        FIX.make_safety_fixture(:even_multiple_root),
        FIX.make_safety_fixture(:branch_crossing),
        FIX.make_safety_fixture(:guard_crossing),
    ]
    records = NamedTuple[]
    for (index, base) in enumerate(bases)
        for (representation, record) in (
            (:base, base),
            (:signed_permutation, FIX.signed_permutation_replica(base)),
            (:orthogonal, FIX.orthogonal_replica(base)),
        )
            push!(records, (; class_index=index, representation, record))
        end
    end
    return records
end

function _assess_points(record, result_points)
    truth = FIX.assessor_truth(record)
    safety = record.descriptor.stratum == :safety_control
    match = LAB.assess_point_seeds(truth, result_points)
    emitted = match.emitted_count
    valid = !safety && emitted > 0 && match.unsupported_count == 0
    return (;
        emitted,
        valid=Int(valid),
        unsupported=emitted > 0 && !valid ? 1 : 0,
        safety_emission=safety && emitted > 0 ? 1 : 0,
        safety_proposal=0,
    )
end

function _run_arm(arm, candidate, prefilter, endpoint, record, start_index)
    observed = Dict{String,Int}()
    observer = bits -> begin
        label = bits <= 53 ? "float64" : string(bits)
        observed[label] = get(observed, label, 0) + 1
    end
    if arm == "BASELINE-NO-RESCUE"
        result = LAB.run_no_rescue_arm(endpoint)
        assessed = _assess_points(record, Tuple[])
        return (;
            outcome=(status=String(result.status), emitted=0, valid=0),
            requested=Dict{String,Int}(),
            observed,
            assessed,
            callbacks=0,
            residual_improving=0,
        )
    elseif arm == LAB.ADAPTIVE_ARM
        result = LAB.run_adaptive_arm(candidate, prefilter; observe_callback=observer)
        assessed = _assess_points(record, result.point_seeds)
        return (;
            outcome=(status=String(result.status), emitted=result.new_seed_count, valid=assessed.valid),
            requested=RG.normalized_precision_ledger(result.requested_precision_counts),
            observed=RG.normalized_precision_ledger(observed),
            assessed,
            callbacks=result.rescue_callbacks,
            residual_improving=0,
        )
    elseif arm == LAB.WEAK_ADAPTIVE_ARM
        result = LAB.run_combined_arm(
            candidate,
            prefilter;
            endpoint_ordinal=start_index,
            observe_callback=observer,
        )
        assessed = _assess_points(record, result.point_seeds)
        return (;
            outcome=(status=String(result.status), emitted=result.new_seed_count, valid=assessed.valid),
            requested=RG.normalized_precision_ledger(result.requested_precision_counts),
            observed=RG.normalized_precision_ledger(observed),
            assessed,
            callbacks=result.rescue_callbacks,
            residual_improving=0,
        )
    end
    charted = arm == "WEAK-SINGULAR-PAIR-GUARD-CHART"
    result = RG.weak_singular_proposals(
        candidate,
        prefilter;
        charted,
        observe_callback=observer,
    )
    points = Tuple[Tuple(proposal.coordinates) for proposal in result.proposals]
    diagnostic_assessment = _assess_points(record, points)
    # These are search starts, never refinement seeds or answers.  Keep their
    # safety-control incidence visible without misclassifying it as an emission.
    assessed = (;
        emitted=0,
        valid=0,
        unsupported=0,
        safety_emission=0,
        safety_proposal=diagnostic_assessment.safety_emission,
    )
    improving = count(proposal -> proposal.residual_ratio < 1, result.proposals)
    requested = result.callbacks == 0 ? Dict{String,Int}() : Dict("float64" => result.callbacks)
    return (;
        outcome=(status=String(result.status), emitted=length(points), valid=assessed.valid),
        requested,
        observed=RG.normalized_precision_ledger(observed),
        assessed,
        callbacks=result.callbacks,
        residual_improving=improving,
    )
end

function run_s0()
    rows = NamedTuple[]
    for entry in _records()
        candidate = FIX.candidate_view(entry.record)
        for (start_index, endpoint) in enumerate(candidate.starts[1:min(4, length(candidate.starts))])
            prefilter = LAB.acquire_shared_prefilter(candidate, endpoint)
            for arm in ARM_ORDER
                result = _run_arm(
                    arm,
                    candidate,
                    prefilter,
                    endpoint,
                    entry.record,
                    start_index,
                )
                push!(rows, (;
                    class_index=entry.class_index,
                    representation=entry.representation,
                    start_index,
                    arm,
                    result...,
                ))
            end
        end
    end

    metrics = Dict{String,Any}()
    for arm in ARM_ORDER
        selected = filter(row -> row.arm == arm, rows)
        metrics[arm] = Dict(
            "callback_count" => sum(row.callbacks for row in selected),
            "precision_mismatch_count" => count(row -> row.requested != row.observed, selected),
            "residual_improving_proposal_count" => sum(row.residual_improving for row in selected),
            "safety_emission_count" => sum(row.assessed.safety_emission for row in selected),
            "safety_proposal_trial_count" => sum(row.assessed.safety_proposal for row in selected),
            "trial_count" => length(selected),
            "unsupported_seed_count" => sum(row.assessed.unsupported for row in selected),
            "valid_refinement_seed_count" => sum(row.assessed.valid for row in selected),
        )
    end

    representation_mismatches = Dict(arm => 0 for arm in ARM_ORDER)
    for class_index in unique(row.class_index for row in rows),
        start_index in unique(row.start_index for row in rows if row.class_index == class_index),
        arm in ARM_ORDER
        selected = [
            row for row in rows if row.class_index == class_index &&
            row.start_index == start_index && row.arm == arm
        ]
        length(selected) == 3 || error("representation triplet is incomplete")
        signatures = Set(JSON3.write(row.outcome) for row in selected)
        representation_mismatches[arm] += length(signatures) != 1
    end
    for arm in ARM_ORDER
        metrics[arm]["proposal_representation_mismatch_count"] =
            representation_mismatches[arm]
    end

    return Dict(
        "schema_version" => "geotarget.exp-rank-guard-001-s0/v1",
        "experiment_id" => "EXP-RANK-GUARD-001",
        "nonpromotional" => true,
        "canonical_verifier_unchanged" => true,
        "truth_visible_to_candidate" => false,
        "case_count" => length(_records()),
        "start_prefix" => 4,
        "arm_order" => collect(ARM_ORDER),
        "mechanism_sha256" => RG.mechanism_hash(),
        "metrics" => metrics,
    )
end

function main(arguments=ARGS)
    output = _arguments(arguments)
    document = run_s0()
    mkpath(dirname(output))
    open(output, "w") do stream
        JSON3.pretty(stream, document)
        write(stream, '\n')
    end
    println(JSON3.pretty(document))
end

abspath(PROGRAM_FILE) == abspath(@__FILE__) && main()
