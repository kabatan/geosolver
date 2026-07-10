const DEVELOPMENT_VARIANTS = (
    "S0-POINT-REPLAY",
    "S1-AP-LMQR",
    "SLB-ANALYTIC-DERIVATIVES",
)

function _run_variant(case::GeneratedEndpoint, variant::AbstractString, options)
    input = candidate_input(case)
    variant == "S0-POINT-REPLAY" && return run_s0(input; options)
    variant == "S1-AP-LMQR" && return run_s1(input; options)
    variant == "SLB-ANALYTIC-DERIVATIVES" && return run_s1(
        input;
        options,
        derivative_mode=:analytic,
    )
    throw(ArgumentError("unknown development variant $variant"))
end

function _development_row(case, outcome, assessment, execution_index)
    return Dict{String,Any}(
        "assessment" => assessment_document(assessment),
        "capability" => string(case.input.oracle.capability),
        "case_checksum" => case.checksum,
        "case_id" => case.input.oracle.id,
        "execution_index" => execution_index,
        "family" => case.input.oracle.family,
        "gold_kind" => string(case.gold.kind),
        "metamorphic_group" => case.input.oracle.metamorphic_group,
        "outcome" => outcome_document(case, outcome),
        "variant" => outcome.variant,
    )
end

function run_development(
    ;
    cases=development_cases(),
    options::ExperimentOptions=ExperimentOptions(),
    variants=DEVELOPMENT_VARIANTS,
)
    rows = Dict{String,Any}[]
    execution_index = 0
    for case in cases
        for variant in variants
            execution_index += 1
            outcome = _run_variant(case, variant, options)
            assessment = assess_outcome(case, outcome)
            push!(rows, _development_row(case, outcome, assessment, execution_index))
        end
    end
    return rows
end

_row_status(row) = row["outcome"]["status"]
_row_work(row) = row["outcome"]["work"]
_row_assessment(row) = row["assessment"]

function _variant_summary(rows, variant, case_lookup)
    selected = filter(row -> row["variant"] == variant, rows)
    phase_a = filter(selected) do row
        case = case_lookup[row["case_id"]]
        case.gold.kind == :isolated_root &&
            case.input.oracle.capability == :C2 &&
            case.input.oracle.family == "SING-NEAR-NULL-FULL-RANK"
    end
    phase_a_successes = count(row -> _row_assessment(row)["gold_success"], phase_a)
    promoted = filter(row -> _row_assessment(row)["promoted"], selected)
    return Dict{String,Any}(
        "budget_exhaustions" => count(
            row -> _row_work(row)["budget_exhausted"],
            selected,
        ),
        "callbacks" => sum(row -> _row_work(row)["callbacks"], selected; init=0),
        "deadline_reached" => count(row -> _row_work(row)["deadline_reached"], selected),
        "false_promotions" => count(
            row -> _row_assessment(row)["false_promotion"],
            selected,
        ),
        "gold_successes" => count(row -> _row_assessment(row)["gold_success"], selected),
        "phase_a_eligible" => length(phase_a),
        "phase_a_gold_successes" => phase_a_successes,
        "phase_a_p_refinement_gold" => isempty(phase_a) ? 0.0 :
            phase_a_successes / length(phase_a),
        "precision_equivalent_oracle_work" => sum(
            row -> _row_work(row)["precision_equivalent_oracle_work"],
            selected;
            init=0,
        ),
        "promoted" => length(promoted),
        "promoted_configuration_coverage_failures" => count(
            row -> !_row_assessment(row)["configuration_error_covered"],
            promoted,
        ),
        "promoted_target_coverage_failures" => count(
            row -> !_row_assessment(row)["target_error_covered"],
            promoted,
        ),
        "status_counts" => Dict{String,Any}(
            status => count(row -> _row_status(row) == status, selected) for
            status in ("promoted", "diagnostic_only", "unknown")
        ),
        "variant" => variant,
    )
end

function _metamorphic_disagreements(rows, variant)
    selected = filter(row -> row["variant"] == variant, rows)
    groups = Dict{String,Vector{Dict{String,Any}}}()
    for row in selected
        startswith(row["metamorphic_group"], "dev-near-") || continue
        push!(get!(groups, row["metamorphic_group"], Dict{String,Any}[]), row)
    end
    disagreements = String[]
    for (group, entries) in sort!(collect(groups); by=first)
        decisions = Set(
            (
                _row_status(row),
                _row_assessment(row)["gold_success"],
                _row_assessment(row)["false_promotion"],
            ) for row in entries
        )
        length(decisions) == 1 || push!(disagreements, group)
    end
    return disagreements, length(groups)
end

function development_summary(rows, cases=development_cases())
    case_lookup = Dict(case.input.oracle.id => case for case in cases)
    length(rows) == length(cases) * length(DEVELOPMENT_VARIANTS) || throw(
        ArgumentError("development rows do not cover the frozen case/variant grid"),
    )
    variants = Dict{String,Any}(
        variant => _variant_summary(rows, variant, case_lookup) for
        variant in DEVELOPMENT_VARIANTS
    )
    s0 = variants["S0-POINT-REPLAY"]
    s1 = variants["S1-AP-LMQR"]
    disagreements, metamorphic_group_count = _metamorphic_disagreements(
        rows,
        "S1-AP-LMQR",
    )
    semantic_only_promotions = count(rows) do row
        _row_status(row) == "promoted" && row["outcome"]["root_evidence"] === nothing
    end
    false_promotions = sum(
        variant["false_promotions"] for variant in values(variants);
        init=0,
    )
    coverage_failures = s1["promoted_configuration_coverage_failures"] +
                        s1["promoted_target_coverage_failures"]
    phase_a_delta = s1["phase_a_p_refinement_gold"] - s0["phase_a_p_refinement_gold"]
    advancement_criteria = Dict{String,Any}(
        "error_coverage_failures_zero" => coverage_failures == 0,
        "false_promotions_zero" => false_promotions == 0,
        "metamorphic_disagreements_zero" => isempty(disagreements),
        "phase_a_gain_at_least_0_15" => phase_a_delta >= 0.15,
        "phase_a_s1_recall_at_least_0_90" => s1["phase_a_p_refinement_gold"] >= 0.90,
        "semantic_replay_only_promotions_zero" => semantic_only_promotions == 0,
    )
    passed = all(values(advancement_criteria))
    return Dict{String,Any}(
        "advancement_criteria" => advancement_criteria,
        "development_advancement_passed" => passed,
        "development_instance_count" => length(cases),
        "experiment_id" => EXPERIMENT_ID,
        "false_promotions" => false_promotions,
        "harness_version" => string(HARNESS_VERSION),
        "locked_validation" => false,
        "metamorphic_group_count" => metamorphic_group_count,
        "metamorphic_disagreement_groups" => disagreements,
        "next_route" => passed ? "S2-AP-CPQR-SUBSET" : nothing,
        "phase_a_p_refinement_gold_delta" => phase_a_delta,
        "product_connected" => false,
        "semantic_replay_only_promotions" => semantic_only_promotions,
        "status" => passed ? "development-advance-s2" : "development-stop-s1",
        "variants" => variants,
    )
end

function _environment_document(input_manifest_path, options)
    commit = try
        readchomp(Cmd(["git", "rev-parse", "HEAD"]))
    catch
        "unavailable"
    end
    return Dict{String,Any}(
        "blas_threads" => LinearAlgebra.BLAS.get_num_threads(),
        "experiment_id" => EXPERIMENT_ID,
        "harness_version" => string(HARNESS_VERSION),
        "input_manifest_path" => replace(String(input_manifest_path), '\\' => '/'),
        "input_manifest_sha256" => bytes2hex(sha256(read(input_manifest_path))),
        "julia_threads" => Threads.nthreads(),
        "julia_version" => string(VERSION),
        "options" => _options_document(options),
        "source_commit" => commit,
    )
end

function _development_report(summary)
    variants = summary["variants"]
    lines = String[
        "# EXP-SINGULAR-001 S0/S1 development result",
        "",
        "This is a development advancement gate, not locked validation or product promotion.",
        "Product connection: **false**.",
        "",
        "| Variant | Phase-A Gold | P_refinement_gold | Promoted | False | Callbacks | Precision-equivalent work |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for variant in DEVELOPMENT_VARIANTS
        entry = variants[variant]
        push!(
            lines,
            "| $variant | $(entry["phase_a_gold_successes"])/$(entry["phase_a_eligible"]) | " *
            "$(round(entry["phase_a_p_refinement_gold"]; digits=4)) | " *
            "$(entry["promoted"]) | $(entry["false_promotions"]) | " *
            "$(entry["callbacks"]) | $(entry["precision_equivalent_oracle_work"]) |",
        )
    end
    push!(lines, "")
    push!(
        lines,
        "Advancement decision: **$(summary["development_advancement_passed"] ? "advance to S2" : "stop after S1")**.",
    )
    push!(lines, "")
    for (criterion, passed) in sort!(collect(summary["advancement_criteria"]); by=first)
        push!(lines, "- `$criterion`: $passed")
    end
    push!(lines, "")
    push!(
        lines,
        "The S0 point replay remains diagnostic-only even when its residual gate accepts the fixed P1 endpoint.",
    )
    return join(lines, '\n') * "\n"
end

function write_development_results(
    output_root::AbstractString,
    rows,
    summary;
    cases=development_cases(),
    options::ExperimentOptions=ExperimentOptions(),
    input_manifest_path=normpath(joinpath(
        @__DIR__,
        "..",
        "development-input-manifest.json",
    )),
)
    root = abspath(String(output_root))
    mkpath(root)
    environment = _environment_document(input_manifest_path, options)
    write_json_artifact(
        joinpath(root, "attempts.json"),
        Dict{String,Any}(
            "experiment_id" => EXPERIMENT_ID,
            "input_manifest_sha256" => environment["input_manifest_sha256"],
            "rows" => rows,
            "schema" => "geotarget.singular-development-attempts/v1",
        ),
    )
    write_json_artifact(joinpath(root, "environment.json"), environment)
    write_json_artifact(joinpath(root, "summary.json"), summary)
    report_path = joinpath(root, "development-report.md")
    temporary = string(report_path, ".tmp-", getpid(), '-', time_ns())
    try
        write(temporary, _development_report(summary))
        mv(temporary, report_path; force=true)
    finally
        isfile(temporary) && rm(temporary; force=true)
    end
    return root
end
