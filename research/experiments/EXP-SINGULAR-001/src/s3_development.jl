const S3_DEVELOPMENT_VARIANTS = (
    "S1-AP-LMQR",
    "S3-AP-BROYDEN",
    "S3-ANALYTIC-SECANT-CONTROL",
)

function _run_s3_development_variant(case::GeneratedEndpoint, variant::AbstractString, options)
    input = candidate_input(case)
    variant == "S1-AP-LMQR" && return run_s1(input; options)
    variant == "S3-AP-BROYDEN" && return run_s3(input; options)
    variant == "S3-ANALYTIC-SECANT-CONTROL" && return run_s3_analytic_control(
        input;
        options,
    )
    throw(ArgumentError("unknown S3 development variant $variant"))
end

function run_s3_development(
    ;
    cases=s3_development_cases(),
    options::ExperimentOptions=ExperimentOptions(),
    variants=S3_DEVELOPMENT_VARIANTS,
)
    rows = Dict{String,Any}[]
    execution_index = 0
    for case in cases
        for variant in variants
            execution_index += 1
            outcome = _run_s3_development_variant(case, variant, options)
            assessment = assess_outcome(case, outcome)
            push!(rows, _development_row(case, outcome, assessment, execution_index))
        end
    end
    return rows
end

function _s3_singular_eligible(case::GeneratedEndpoint)
    case.gold.kind == :isolated_root || return false
    case.input.oracle.family == "SING-ISOLATED-MULTIPLE" && return true
    return case.input.oracle.family == "SING-TANGENCY-AND-CLOSE-ROOTS" &&
           case.parameters["separation"] == 0.0
end

function _s3_variant_summary(rows, variant, case_lookup)
    selected = filter(row -> row["variant"] == variant, rows)
    eligible = filter(row -> _s3_singular_eligible(case_lookup[row["case_id"]]), selected)
    eligible_successes = count(row -> _row_assessment(row)["gold_success"], eligible)
    promoted = filter(row -> _row_assessment(row)["promoted"], selected)
    return Dict{String,Any}(
        "budget_exhaustions" => count(
            row -> _row_work(row)["budget_exhausted"],
            selected,
        ),
        "callbacks" => sum(row -> _row_work(row)["callbacks"], selected; init=0),
        "deadline_reached" => count(row -> _row_work(row)["deadline_reached"], selected),
        "eligible" => length(eligible),
        "eligible_gold_successes" => eligible_successes,
        "false_promotions" => count(
            row -> _row_assessment(row)["false_promotion"],
            selected,
        ),
        "p_refinement_gold" => isempty(eligible) ? 0.0 :
            eligible_successes / length(eligible),
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

function _s3_metamorphic_disagreements(rows)
    disagreements = String[]
    groups = Set{String}()
    for variant in S3_DEVELOPMENT_VARIANTS
        selected = filter(row -> row["variant"] == variant, rows)
        by_group = Dict{String,Vector{Dict{String,Any}}}()
        for row in selected
            push!(groups, row["metamorphic_group"])
            push!(get!(by_group, row["metamorphic_group"], Dict{String,Any}[]), row)
        end
        for (group, entries) in sort!(collect(by_group); by=first)
            decisions = Set(
                (
                    _row_status(row),
                    _row_assessment(row)["gold_success"],
                    _row_assessment(row)["false_promotion"],
                ) for row in entries
            )
            length(decisions) == 1 || push!(disagreements, "$variant:$group")
        end
    end
    return disagreements, length(groups)
end

function _s3_control_disagreements(rows)
    by_case = Dict{String,Dict{String,Dict{String,Any}}}()
    for row in rows
        by_variant = get!(by_case, row["case_id"], Dict{String,Dict{String,Any}}())
        by_variant[row["variant"]] = row
    end
    disagreements = String[]
    for (case_id, variants) in sort!(collect(by_case); by=first)
        candidate = variants["S3-AP-BROYDEN"]
        control = variants["S3-ANALYTIC-SECANT-CONTROL"]
        candidate_decision = (
            _row_status(candidate),
            _row_assessment(candidate)["gold_success"],
            _row_assessment(candidate)["false_promotion"],
        )
        control_decision = (
            _row_status(control),
            _row_assessment(control)["gold_success"],
            _row_assessment(control)["false_promotion"],
        )
        candidate_decision == control_decision || push!(disagreements, case_id)
    end
    return disagreements
end

function _s3_budget_limit_violations(rows, options::ExperimentOptions)
    violations = String[]
    maximum_precision = maximum(options.precision_ladder)
    for row in rows
        work = _row_work(row)
        iteration_limit = options.maximum_iterations
        if work["callbacks"] > options.maximum_callbacks ||
           work["iterations"] > iteration_limit ||
           work["maximum_precision_bits"] > maximum_precision
            push!(violations, "$(row["variant"]):$(row["case_id"])")
        end
    end
    return violations
end

function _s3_noneligible_promotions(rows, case_lookup)
    return String[
        row["case_id"] for row in rows if
        row["variant"] == "S3-AP-BROYDEN" &&
        !_s3_singular_eligible(case_lookup[row["case_id"]]) &&
        _row_assessment(row)["promoted"]
    ]
end

function _s3_evidence_gate_failures(rows)
    failures = String[]
    for row in rows
        row["variant"] == "S3-AP-BROYDEN" || continue
        _row_status(row) == "promoted" || continue
        evidence = row["outcome"]["root_evidence"]
        passed = evidence !== nothing && evidence["rank_stable"] &&
                 evidence["independent_confirmations_passed"] &&
                 evidence["canonical_confirmations_passed"] &&
                 evidence["linear_trace_passed"] &&
                 evidence["nullity"] > 0
        passed || push!(failures, row["case_id"])
    end
    return failures
end

function s3_development_summary(
    rows,
    cases=s3_development_cases();
    options::ExperimentOptions=ExperimentOptions(),
)
    case_lookup = Dict(case.input.oracle.id => case for case in cases)
    expected_pairs = Set(
        (case.input.oracle.id, variant) for case in cases for
        variant in S3_DEVELOPMENT_VARIANTS
    )
    actual_pairs = Set((row["case_id"], row["variant"]) for row in rows)
    length(rows) == length(expected_pairs) && actual_pairs == expected_pairs || throw(
        ArgumentError("S3 rows do not cover the frozen case/variant grid"),
    )
    variants = Dict{String,Any}(
        variant => _s3_variant_summary(rows, variant, case_lookup) for
        variant in S3_DEVELOPMENT_VARIANTS
    )
    s1 = variants["S1-AP-LMQR"]
    s3 = variants["S3-AP-BROYDEN"]
    control = variants["S3-ANALYTIC-SECANT-CONTROL"]
    metamorphic_disagreements, metamorphic_group_count =
        _s3_metamorphic_disagreements(rows)
    control_disagreements = _s3_control_disagreements(rows)
    budget_limit_violations = _s3_budget_limit_violations(rows, options)
    noneligible_promotions = _s3_noneligible_promotions(rows, case_lookup)
    evidence_gate_failures = _s3_evidence_gate_failures(rows)
    semantic_only_promotions = count(rows) do row
        _row_status(row) == "promoted" && row["outcome"]["root_evidence"] === nothing
    end
    false_promotions = sum(
        variant["false_promotions"] for variant in values(variants);
        init=0,
    )
    coverage_failures = s3["promoted_configuration_coverage_failures"] +
                        s3["promoted_target_coverage_failures"]
    recall_delta = s3["p_refinement_gold"] - s1["p_refinement_gold"]
    advancement_criteria = Dict{String,Any}(
        "analytic_control_decisions_match" => isempty(control_disagreements),
        "budget_limit_violations_zero" => isempty(budget_limit_violations),
        "candidate_control_recall_equal" =>
            s3["p_refinement_gold"] == control["p_refinement_gold"],
        "error_coverage_failures_zero" => coverage_failures == 0,
        "false_promotions_zero" => false_promotions == 0,
        "metamorphic_disagreements_zero" => isempty(metamorphic_disagreements),
        "noneligible_s3_promotions_zero" => isempty(noneligible_promotions),
        "promoted_evidence_gate_failures_zero" => isempty(evidence_gate_failures),
        "recall_gain_at_least_0_50" => recall_delta >= 0.50,
        "s3_singular_recall_at_least_0_75" => s3["p_refinement_gold"] >= 0.75,
        "semantic_replay_only_promotions_zero" => semantic_only_promotions == 0,
    )
    passed = all(values(advancement_criteria))
    return Dict{String,Any}(
        "advancement_criteria" => advancement_criteria,
        "analytic_control_disagreement_cases" => control_disagreements,
        "budget_limit_violation_rows" => budget_limit_violations,
        "development_advancement_passed" => passed,
        "development_instance_count" => length(cases),
        "evidence_gate_failure_cases" => evidence_gate_failures,
        "experiment_id" => EXPERIMENT_ID,
        "false_promotions" => false_promotions,
        "harness_version" => string(HARNESS_VERSION),
        "locked_validation" => false,
        "metamorphic_group_count" => metamorphic_group_count,
        "metamorphic_disagreement_groups" => metamorphic_disagreements,
        "next_route" => passed ? "S4-AP-BORDERED-NULLSPACE" : nothing,
        "noneligible_s3_promotion_cases" => noneligible_promotions,
        "product_connected" => false,
        "recall_delta_from_s1" => recall_delta,
        "semantic_replay_only_promotions" => semantic_only_promotions,
        "status" => passed ? "development-advance-s4" : "development-stop-s3",
        "variants" => variants,
    )
end

function _s3_development_report(summary)
    lines = String[
        "# EXP-SINGULAR-001 S3 development result",
        "",
        "This is a development advancement gate, not locked validation or product promotion.",
        "Product connection: **false**.",
        "",
        "| Variant | Eligible Gold | P_refinement_gold | Promoted | False | Callbacks | Precision-equivalent work |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for variant in S3_DEVELOPMENT_VARIANTS
        entry = summary["variants"][variant]
        push!(
            lines,
            "| $variant | $(entry["eligible_gold_successes"])/$(entry["eligible"]) | " *
            "$(round(entry["p_refinement_gold"]; digits=4)) | " *
            "$(entry["promoted"]) | $(entry["false_promotions"]) | " *
            "$(entry["callbacks"]) | $(entry["precision_equivalent_oracle_work"]) |",
        )
    end
    push!(lines, "")
    push!(
        lines,
        "Advancement decision: **$(summary["development_advancement_passed"] ? "advance to S4" : "stop after S3")**.",
    )
    push!(lines, "")
    for (criterion, passed) in sort!(collect(summary["advancement_criteria"]); by=first)
        push!(lines, "- `$criterion`: $passed")
    end
    push!(lines, "")
    push!(
        lines,
        "The result is bounded to exact stable-rank-deficient development endpoints. It does not certify general singular roots, open locked data, or connect S3 to production.",
    )
    return join(lines, '\n') * "\n"
end

function write_s3_development_results(
    output_root::AbstractString,
    rows,
    summary;
    options::ExperimentOptions=ExperimentOptions(),
    input_manifest_path=normpath(joinpath(
        @__DIR__,
        "..",
        "s3-development-input-manifest.json",
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
            "schema" => "geotarget.singular-s3-development-attempts/v1",
        ),
    )
    write_json_artifact(joinpath(root, "environment.json"), environment)
    write_json_artifact(joinpath(root, "summary.json"), summary)
    report_path = joinpath(root, "development-report.md")
    temporary = string(report_path, ".tmp-", getpid(), '-', time_ns())
    try
        write(temporary, _s3_development_report(summary))
        mv(temporary, report_path; force=true)
    finally
        isfile(temporary) && rm(temporary; force=true)
    end
    return root
end
