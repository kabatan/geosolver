const S2_DEVELOPMENT_VARIANTS = (
    "S1-AP-LMQR",
    "S2-AP-CPQR-SUBSET",
    "S2-ANALYTIC-SUBSET-CONTROL",
)

function _run_s2_development_variant(case::GeneratedEndpoint, variant::AbstractString, options)
    input = candidate_input(case)
    variant == "S1-AP-LMQR" && return run_s1(input; options)
    variant == "S2-AP-CPQR-SUBSET" && return run_s2(input; options)
    variant == "S2-ANALYTIC-SUBSET-CONTROL" && return run_s2(
        input;
        options,
        derivative_mode=:analytic,
    )
    throw(ArgumentError("unknown S2 development variant $variant"))
end

function run_s2_development(
    ;
    cases=s2_development_cases(),
    options::ExperimentOptions=ExperimentOptions(),
    variants=S2_DEVELOPMENT_VARIANTS,
)
    rows = Dict{String,Any}[]
    execution_index = 0
    for case in cases
        for variant in variants
            execution_index += 1
            outcome = _run_s2_development_variant(case, variant, options)
            assessment = assess_outcome(case, outcome)
            push!(rows, _development_row(case, outcome, assessment, execution_index))
        end
    end
    return rows
end

function _s2_variant_summary(rows, variant, case_lookup)
    selected = filter(row -> row["variant"] == variant, rows)
    eligible = filter(
        row -> case_lookup[row["case_id"]].gold.kind == :finite_manifold_target,
        selected,
    )
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

function _s2_metamorphic_disagreements(rows)
    disagreements = String[]
    group_count = 0
    for variant in S2_DEVELOPMENT_VARIANTS
        selected = filter(row -> row["variant"] == variant, rows)
        groups = Dict{String,Vector{Dict{String,Any}}}()
        for row in selected
            push!(
                get!(groups, row["metamorphic_group"], Dict{String,Any}[]),
                row,
            )
        end
        group_count = max(group_count, length(groups))
        for (group, entries) in sort!(collect(groups); by=first)
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
    return disagreements, group_count
end

function _s2_cross_variant_disagreements(rows)
    by_case = Dict{String,Dict{String,Dict{String,Any}}}()
    for row in rows
        by_variant = get!(by_case, row["case_id"], Dict{String,Dict{String,Any}}())
        by_variant[row["variant"]] = row
    end
    disagreements = String[]
    for (case_id, variants) in sort!(collect(by_case); by=first)
        dense = variants["S2-AP-CPQR-SUBSET"]
        analytic = variants["S2-ANALYTIC-SUBSET-CONTROL"]
        dense_decision = (
            _row_status(dense),
            _row_assessment(dense)["gold_success"],
            _row_assessment(dense)["false_promotion"],
        )
        analytic_decision = (
            _row_status(analytic),
            _row_assessment(analytic)["gold_success"],
            _row_assessment(analytic)["false_promotion"],
        )
        dense_decision == analytic_decision || push!(disagreements, case_id)
    end
    return disagreements
end

function _s2_budget_limit_violations(rows, options::ExperimentOptions)
    violations = String[]
    maximum_precision = maximum(options.precision_ladder)
    for row in rows
        work = _row_work(row)
        if work["callbacks"] > options.maximum_callbacks ||
           work["iterations"] > options.maximum_iterations ||
           work["maximum_precision_bits"] > maximum_precision
            push!(violations, "$(row["variant"]):$(row["case_id"])")
        end
    end
    return violations
end

function s2_development_summary(
    rows,
    cases=s2_development_cases();
    options::ExperimentOptions=ExperimentOptions(),
)
    case_lookup = Dict(case.input.oracle.id => case for case in cases)
    expected_pairs = Set(
        (case.input.oracle.id, variant) for case in cases for
        variant in S2_DEVELOPMENT_VARIANTS
    )
    actual_pairs = Set((row["case_id"], row["variant"]) for row in rows)
    length(rows) == length(expected_pairs) && actual_pairs == expected_pairs || throw(
        ArgumentError("S2 rows do not cover the frozen case/variant grid"),
    )
    variants = Dict{String,Any}(
        variant => _s2_variant_summary(rows, variant, case_lookup) for
        variant in S2_DEVELOPMENT_VARIANTS
    )
    s1 = variants["S1-AP-LMQR"]
    s2 = variants["S2-AP-CPQR-SUBSET"]
    analytic = variants["S2-ANALYTIC-SUBSET-CONTROL"]
    metamorphic_disagreements, metamorphic_group_count =
        _s2_metamorphic_disagreements(rows)
    cross_variant_disagreements = _s2_cross_variant_disagreements(rows)
    budget_limit_violations = _s2_budget_limit_violations(rows, options)
    semantic_only_promotions = count(rows) do row
        _row_status(row) == "promoted" && row["outcome"]["root_evidence"] === nothing
    end
    false_promotions = sum(
        variant["false_promotions"] for variant in values(variants);
        init=0,
    )
    coverage_failures = s2["promoted_configuration_coverage_failures"] +
                        s2["promoted_target_coverage_failures"]
    recall_delta = s2["p_refinement_gold"] - s1["p_refinement_gold"]
    advancement_criteria = Dict{String,Any}(
        "analytic_control_decisions_match" => isempty(cross_variant_disagreements),
        "budget_limit_violations_zero" => isempty(budget_limit_violations),
        "dense_s2_recall_at_least_0_90" => s2["p_refinement_gold"] >= 0.90,
        "error_coverage_failures_zero" => coverage_failures == 0,
        "false_promotions_zero" => false_promotions == 0,
        "metamorphic_disagreements_zero" => isempty(metamorphic_disagreements),
        "recall_gain_at_least_0_15" => recall_delta >= 0.15,
        "semantic_replay_only_promotions_zero" => semantic_only_promotions == 0,
    )
    passed = all(values(advancement_criteria))
    return Dict{String,Any}(
        "advancement_criteria" => advancement_criteria,
        "analytic_control_disagreement_cases" => cross_variant_disagreements,
        "budget_limit_violation_rows" => budget_limit_violations,
        "development_advancement_passed" => passed,
        "development_instance_count" => length(cases),
        "experiment_id" => EXPERIMENT_ID,
        "false_promotions" => false_promotions,
        "harness_version" => string(HARNESS_VERSION),
        "locked_validation" => false,
        "metamorphic_group_count" => metamorphic_group_count,
        "metamorphic_disagreement_groups" => metamorphic_disagreements,
        "next_route" => passed ? "S3-AP-BROYDEN" : nothing,
        "product_connected" => false,
        "recall_delta_from_s1" => recall_delta,
        "semantic_replay_only_promotions" => semantic_only_promotions,
        "status" => passed ? "development-advance-s3" : "development-stop-s2",
        "variants" => variants,
    )
end

function _s2_development_report(summary)
    lines = String[
        "# EXP-SINGULAR-001 S2 development result",
        "",
        "This is a development advancement gate, not locked validation or product promotion.",
        "Product connection: **false**.",
        "",
        "| Variant | Eligible Gold | P_refinement_gold | Promoted | False | Callbacks | Precision-equivalent work |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for variant in S2_DEVELOPMENT_VARIANTS
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
        "Advancement decision: **$(summary["development_advancement_passed"] ? "advance to S3" : "stop after S2")**.",
    )
    push!(lines, "")
    for (criterion, passed) in sort!(collect(summary["advancement_criteria"]); by=first)
        push!(lines, "- `$criterion`: $passed")
    end
    push!(lines, "")
    push!(
        lines,
        "Only target-constant rank-deficient manifolds are eligible in this split; varying target images and inconsistent systems must remain typed unknown.",
    )
    return join(lines, '\n') * "\n"
end

function write_s2_development_results(
    output_root::AbstractString,
    rows,
    summary;
    options::ExperimentOptions=ExperimentOptions(),
    input_manifest_path=normpath(joinpath(
        @__DIR__,
        "..",
        "s2-development-input-manifest.json",
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
            "schema" => "geotarget.singular-s2-development-attempts/v1",
        ),
    )
    write_json_artifact(joinpath(root, "environment.json"), environment)
    write_json_artifact(joinpath(root, "summary.json"), summary)
    report_path = joinpath(root, "development-report.md")
    temporary = string(report_path, ".tmp-", getpid(), '-', time_ns())
    try
        write(temporary, _s2_development_report(summary))
        mv(temporary, report_path; force=true)
    finally
        isfile(temporary) && rm(temporary; force=true)
    end
    return root
end
