# S4 development orchestration and artifact conversion live here. This file may
# share final field names and assessment predicates, but no candidate/control
# numerical helper.

function _s4_document_value(value)
    if value isa BigFloat || value isa Rational
        return string(value)
    elseif value isa AbstractFloat
        return isfinite(value) ? value : string(value)
    elseif value isa Integer || value isa Bool || value isa AbstractString || value === nothing
        return value
    elseif value isa NamedTuple
        return Dict{String,Any}(
            String(key) => _s4_document_value(item) for (key, item) in pairs(value)
        )
    elseif value isa AbstractDict
        return Dict{String,Any}(
            String(key) => _s4_document_value(item) for (key, item) in pairs(value)
        )
    elseif value isa Tuple || value isa AbstractVector
        return Any[_s4_document_value(item) for item in value]
    end
    return string(value)
end

function _s4_assessment(case::S4DevelopmentCase, outcome::ExperimentalOutcome)
    promoted = outcome.status == :promoted
    eligible = case.stratum == "isolated-deflation-one"
    base = Dict{String,Any}(
        "configuration_error" => nothing,
        "configuration_error_covered" => false,
        "eligible" => eligible,
        "false_promotion" => false,
        "gold_success" => false,
        "promoted" => promoted,
        "stratum" => case.stratum,
        "target_error" => nothing,
        "target_error_covered" => false,
    )
    promoted || return base
    evidence = outcome.root_evidence
    evidence isa Union{NumericalRootEvidence,NumericalSingularRootEvidence} || begin
        base["false_promotion"] = true
        return base
    end
    isempty(case.isolated_configurations) && begin
        base["false_promotion"] = true
        return base
    end
    endpoint = Float64[evidence.endpoint...]
    distances = Float64[
        norm(endpoint - Float64[configuration...], Inf) for
        configuration in case.isolated_configurations
    ]
    nearest = argmin(distances)
    configuration_error = distances[nearest]
    target_error = abs(Float64(evidence.target) - Float64(case.isolated_targets[nearest]))
    configuration_covered = configuration_error <=
                            Float64(evidence.configuration_error_estimate)
    target_covered = target_error <= Float64(evidence.target_error_estimate)
    success = configuration_covered && target_covered
    base["configuration_error"] = configuration_error
    base["configuration_error_covered"] = configuration_covered
    base["false_promotion"] = !success
    base["gold_success"] = success
    base["target_error"] = target_error
    base["target_error_covered"] = target_covered
    return base
end

function _s4_outcome_document(case, outcome::S4VariantOutcome)
    document = outcome_document(case.generated, outcome.core)
    document["diagnostics"] = _s4_document_value(outcome.diagnostics)
    return document
end

function _s4_baseline_outcome(outcome::ExperimentalOutcome)
    return S4VariantOutcome(
        outcome,
        Dict{String,Any}(
            "algorithm" => "unchanged-S1-AP-LMQR",
            "paired_baseline" => true,
            "product_connected" => false,
        ),
    )
end

function _s4_row(case, outcome::S4VariantOutcome, execution_index::Int)
    assessment = _s4_assessment(case, outcome.core)
    document = _s4_outcome_document(case, outcome)
    document["assessment"] = assessment
    document["execution_index"] = execution_index
    document["metamorphic_group"] = case.generated.input.oracle.metamorphic_group
    document["representation"] = case.representation
    document["stratum"] = case.stratum
    return document
end

function _run_s4_development_case(
    case,
    first_execution_index::Int;
    s4_options,
    baseline_options,
    clock_ns,
    variant_order=(
        "S1-AP-LMQR",
        "S4-C2-NULLSPACE-TWO-STEP",
        "S4-ANALYTIC-TWO-STEP-CONTROL",
    ),
)
    rows = Any[]
    frozen_variants = Set((
        "S1-AP-LMQR",
        "S4-C2-NULLSPACE-TWO-STEP",
        "S4-ANALYTIC-TWO-STEP-CONTROL",
    ))
    length(variant_order) == 3 && Set(variant_order) == frozen_variants ||
        throw(ArgumentError("S4 case variant order must be one frozen permutation"))
    input = candidate_input(case)
    mechanism_input = s4_candidate_input(input)
    for (offset, variant) in enumerate(variant_order)
        outcome = if variant == "S1-AP-LMQR"
            _s4_baseline_outcome(run_s1(
                input;
                options=baseline_options,
                derivative_mode=:dense,
                clock_ns,
            ))
        elseif variant == "S4-C2-NULLSPACE-TWO-STEP"
            run_s4(mechanism_input; options=s4_options, clock_ns)
        else
            run_s4_analytic_control(
                mechanism_input,
                case.analytic_control;
                options=s4_options,
                clock_ns,
            )
        end
        push!(rows, _s4_row(case, outcome, first_execution_index + offset - 1))
    end
    return rows
end

function run_s4_development(
    cases=s4_development_cases();
    s4_options::ExperimentOptions=ExperimentOptions(
        precision_ladder=(128, 256),
        semantic_precision_bits=256,
    ),
    baseline_options::ExperimentOptions=ExperimentOptions(),
    clock_ns=time_ns,
)
    rows = Any[]
    for (case_index, case) in enumerate(cases)
        variant_order = _s4_counterbalanced_variant_order(case_index)
        append!(rows, _run_s4_development_case(
            case,
            3 * (case_index - 1) + 1;
            s4_options,
            baseline_options,
            clock_ns,
            variant_order,
        ))
    end
    return rows
end

function _s4_counterbalanced_variant_order(case_index::Int)
    case_index >= 1 || throw(ArgumentError("case index must be positive"))
    variants = (
        "S1-AP-LMQR",
        "S4-C2-NULLSPACE-TWO-STEP",
        "S4-ANALYTIC-TWO-STEP-CONTROL",
    )
    representation_index = mod(case_index - 1, 3)
    group_index = fld(case_index - 1, 3)
    if iseven(group_index)
        return ntuple(position -> variants[mod1(position + representation_index, 3)], 3)
    end
    return ntuple(position -> variants[mod1(position - representation_index, 3)], 3)
end

function _s4_rows_for_variant(rows, variant)
    return Any[row for row in rows if row["variant"] == variant]
end

function _s4_variant_summary(rows, variant)
    selected = _s4_rows_for_variant(rows, variant)
    eligible = Any[row for row in selected if row["assessment"]["eligible"]]
    promoted = count(row -> row["status"] == "promoted", selected)
    return Dict{String,Any}(
        "budget_or_deadline_promotions" => count(
            row -> row["status"] == "promoted" &&
                   (row["work"]["budget_exhausted"] || row["work"]["deadline_reached"]),
            selected,
        ),
        "eligible_gold_successes" => count(
            row -> row["assessment"]["gold_success"],
            eligible,
        ),
        "eligible_instances" => length(eligible),
        "diagnostic_only" => count(row -> row["status"] == "diagnostic_only", selected),
        "false_promotions" => count(
            row -> row["assessment"]["false_promotion"],
            selected,
        ),
        "gold_successes" => count(row -> row["assessment"]["gold_success"], selected),
        "promoted" => promoted,
        "total" => length(selected),
        "unknown" => count(row -> row["status"] == "unknown", selected),
        "variant" => variant,
    )
end

function _s4_initial_route_signature(row)
    diagnostics = row["diagnostics"]
    if haskey(diagnostics, "initial_route")
        route = diagnostics["initial_route"]
        return "rank=$(route["selected_rank"]):nullity=$(route["nullity"])"
    end
    failure = get(diagnostics, "failure", Dict{String,Any}())
    return "failed:$(get(failure, "reason", row["reason"]))"
end

function _s4_metamorphic_disagreements(rows)
    disagreements = Any[]
    variants = sort!(unique(String(row["variant"]) for row in rows))
    groups = sort!(unique(String(row["metamorphic_group"]) for row in rows))
    for variant in variants, group in groups
        selected = Any[
            row for row in rows if row["variant"] == variant &&
            row["metamorphic_group"] == group
        ]
        isempty(selected) && continue
        promotions = unique(row["status"] == "promoted" for row in selected)
        successes = unique(row["assessment"]["gold_success"] for row in selected)
        routes = variant == "S1-AP-LMQR" ? String["paired-baseline"] :
                 unique(_s4_initial_route_signature(row) for row in selected)
        if length(promotions) != 1 || length(successes) != 1 || length(routes) != 1
            push!(disagreements, Dict{String,Any}(
                "group" => group,
                "gold_successes" => collect(successes),
                "promotions" => collect(promotions),
                "route_signatures" => collect(routes),
                "variant" => variant,
            ))
        end
    end
    return disagreements
end

function _s4_control_disagreements(rows)
    candidate = Dict(
        row["case_id"] => row for row in rows if
        row["variant"] == "S4-C2-NULLSPACE-TWO-STEP"
    )
    control = Dict(
        row["case_id"] => row for row in rows if
        row["variant"] == "S4-ANALYTIC-TWO-STEP-CONTROL"
    )
    disagreements = Any[]
    for case_id in sort!(collect(intersect(keys(candidate), keys(control))))
        left = candidate[case_id]
        right = control[case_id]
        if left["status"] != right["status"] ||
           left["assessment"]["gold_success"] != right["assessment"]["gold_success"]
            push!(disagreements, Dict{String,Any}(
                "candidate_gold_success" => left["assessment"]["gold_success"],
                "candidate_status" => left["status"],
                "case_id" => case_id,
                "control_gold_success" => right["assessment"]["gold_success"],
                "control_status" => right["status"],
            ))
        end
    end
    return disagreements
end

function _s4_budget_violations(rows, s4_options, baseline_options)
    violations = Any[]
    for row in rows
        options = row["variant"] == "S1-AP-LMQR" ? baseline_options : s4_options
        work = row["work"]
        categorized_callbacks = work["residual_calls"] + work["target_calls"] +
                                work["jacobian_calls"]
        precision_callbacks = sum(
            entry["callbacks"] for entry in work["calls_by_precision"]
        )
        precision_equivalent = sum(
            entry["callbacks"] * cld(entry["precision_bits"], 53) for
            entry in work["calls_by_precision"]
        )
        maximum_precision = isempty(work["calls_by_precision"]) ? 0 : maximum(
            entry["precision_bits"] for entry in work["calls_by_precision"]
        )
        if work["callbacks"] > options.maximum_callbacks ||
           work["iterations"] > options.maximum_iterations ||
           work["elapsed_seconds"] > options.wall_seconds ||
           categorized_callbacks != work["callbacks"] ||
           precision_callbacks != work["callbacks"] ||
           precision_equivalent != work["precision_equivalent_oracle_work"] ||
           maximum_precision != work["maximum_precision_bits"] ||
           (row["status"] == "promoted" &&
            (work["budget_exhausted"] || work["deadline_reached"]))
            push!(violations, Dict{String,Any}(
                "case_id" => row["case_id"],
                "variant" => row["variant"],
                "work" => work,
            ))
        end
    end
    return violations
end

function _s4_promoted_evidence_failures(rows)
    failures = Any[]
    for row in rows
        row["status"] == "promoted" || continue
        assessment = row["assessment"]
        base_failed = row["root_evidence"] === nothing ||
                      row["semantic_replay"] === nothing ||
                      !row["semantic_replay"]["accepted"] ||
                      !assessment["configuration_error_covered"] ||
                      !assessment["target_error_covered"]
        diagnostic_failed = false
        if row["variant"] != "S1-AP-LMQR"
            diagnostics = row["diagnostics"]
            diagnostic_failed = get(diagnostics, "phase", "") != "promoted" ||
                                !get(diagnostics["error_audit"], "decision", false) ||
                                any(
                audit -> !get(audit, "decision", false),
                diagnostics["applicability_audits"],
            )
        end
        if base_failed || diagnostic_failed
            push!(failures, Dict{String,Any}(
                "case_id" => row["case_id"],
                "diagnostic_failed" => diagnostic_failed,
                "variant" => row["variant"],
            ))
        end
    end
    return failures
end

function s4_development_summary(
    rows;
    s4_options::ExperimentOptions=ExperimentOptions(
        precision_ladder=(128, 256),
        semantic_precision_bits=256,
    ),
    baseline_options::ExperimentOptions=ExperimentOptions(),
    checkpoint_manifest_sha256::AbstractString,
    run_identity_sha256::AbstractString,
    warmup_sha256::AbstractString,
)
    variants = (
        "S1-AP-LMQR",
        "S4-C2-NULLSPACE-TWO-STEP",
        "S4-ANALYTIC-TWO-STEP-CONTROL",
    )
    summaries = Dict(
        variant => _s4_variant_summary(rows, variant) for variant in variants
    )
    candidate = summaries["S4-C2-NULLSPACE-TWO-STEP"]
    baseline = summaries["S1-AP-LMQR"]
    eligible_count = candidate["eligible_instances"]
    candidate_rate = eligible_count == 0 ? 0.0 :
                     candidate["eligible_gold_successes"] / eligible_count
    baseline_rate = eligible_count == 0 ? 0.0 :
                    baseline["eligible_gold_successes"] / eligible_count
    gain = candidate_rate - baseline_rate
    metamorphic = _s4_metamorphic_disagreements(rows)
    control = _s4_control_disagreements(rows)
    budgets = _s4_budget_violations(rows, s4_options, baseline_options)
    evidence = _s4_promoted_evidence_failures(rows)
    s4_rows = Any[row for row in rows if row["variant"] != "S1-AP-LMQR"]
    noneligible_promotions = Any[
        Dict{String,Any}(
            "case_id" => row["case_id"],
            "stratum" => row["stratum"],
            "variant" => row["variant"],
        ) for row in s4_rows if
        !row["assessment"]["eligible"] && row["status"] == "promoted"
    ]
    all_false_promotions = sum(summary["false_promotions"] for summary in values(summaries))
    gate = Dict{String,Any}(
        "candidate_control_decisions_identical" => isempty(control),
        "candidate_gain_at_least_60_percentage_points" => gain >= 0.60,
        "candidate_recovers_at_least_12_of_15" =>
            candidate["eligible_instances"] == 15 &&
            candidate["eligible_gold_successes"] >= 12,
        "control_strata_unpromoted" => isempty(noneligible_promotions),
        "false_promotions_zero" => all_false_promotions == 0,
        "hard_budget_violations_zero" => isempty(budgets),
        "metamorphic_disagreements_zero" => isempty(metamorphic),
        "promoted_evidence_failures_zero" => isempty(evidence),
    )
    advanced = all(values(gate))
    return Dict{String,Any}(
        "advancement_gate" => gate,
        "candidate_control_disagreements" => control,
        "candidate_eligible_recovery_rate" => candidate_rate,
        "candidate_gain_over_s1" => gain,
        "decision" => advanced ?
            "advance-to-family-disjoint-locked-validation" :
            "record-bounded-S4-negative-and-continue",
        "development_gate_passed" => advanced,
        "evidence_failures" => evidence,
        "experiment_id" => EXPERIMENT_ID,
        "hard_budget_violations" => budgets,
        "locked_inputs_materialized" => false,
        "metamorphic_disagreements" => metamorphic,
        "noneligible_s4_promotions" => noneligible_promotions,
        "product_connected" => false,
        "schema" => "geotarget.singular-s4-development-summary/v1",
        "variant_summaries" => summaries,
    )
end

function _s4_development_report(summary)
    lines = String[
        "# EXP-SINGULAR-001 S4 development report",
        "",
        "Decision: `$(summary["decision"])`",
        "",
        "Product connected: `false`",
        "Locked inputs materialized: `false`",
        "",
        "## Variant counts",
        "",
    ]
    for variant in sort!(collect(keys(summary["variant_summaries"])))
        values = summary["variant_summaries"][variant]
        push!(
            lines,
            "- `$variant`: promoted $(values["promoted"])/$(values["total"]), " *
            "eligible Gold successes $(values["eligible_gold_successes"])/" *
            "$(values["eligible_instances"]), false promotions $(values["false_promotions"])",
        )
    end
    append!(lines, String[
        "",
        "## Frozen advancement gate",
        "",
    ])
    for key in sort!(collect(keys(summary["advancement_gate"])))
        push!(lines, "- `$key`: `$(summary["advancement_gate"][key])`")
    end
    append!(lines, String[
        "",
        "This is a development-only empirical result. It does not certify a singular root,",
        "prove all-root completeness, connect S4 to the product, or open locked inputs.",
        "",
    ])
    return join(lines, '\n')
end

function _s4_options_document(options::ExperimentOptions)
    return Dict{String,Any}(
        "configuration_error_goal" => options.configuration_error_goal,
        "error_reserve_multiplier" => options.error_reserve_multiplier,
        "finite_difference_exponent" => options.finite_difference_exponent,
        "independent_confirmation_count" => options.independent_confirmation_count,
        "maximum_callbacks" => options.maximum_callbacks,
        "maximum_iterations" => options.maximum_iterations,
        "precision_ladder" => collect(options.precision_ladder),
        "semantic_precision_bits" => options.semantic_precision_bits,
        "semantic_residual_tolerance" => options.semantic_residual_tolerance,
        "target_error_goal" => options.target_error_goal,
        "wall_seconds" => options.wall_seconds,
    )
end

function write_s4_development_results(
    result_directory::AbstractString,
    rows,
    summary;
    input_manifest_path::AbstractString=joinpath(
        @__DIR__,
        "..",
        "..",
        "s4-development-input-manifest.json",
    ),
    implementation_freeze_path::AbstractString=joinpath(
        @__DIR__,
        "..",
        "..",
        "s4-implementation-freeze.json",
    ),
    s4_options::ExperimentOptions=ExperimentOptions(
        precision_ladder=(128, 256),
        semantic_precision_bits=256,
    ),
    baseline_options::ExperimentOptions=ExperimentOptions(),
)
    isfile(input_manifest_path) || error("missing frozen S4 input manifest")
    isfile(implementation_freeze_path) || error("missing S4 implementation freeze")
    mkpath(result_directory)
    raw_document = Dict{String,Any}(
        "experiment_id" => EXPERIMENT_ID,
        "rows" => rows,
        "schema" => "geotarget.singular-s4-development-raw/v1",
    )
    environment = Dict{String,Any}(
        "baseline_options" => _s4_options_document(baseline_options),
        "blas_threads" => BLAS.get_num_threads(),
        "checkpoint_manifest_sha256" => String(checkpoint_manifest_sha256),
        "implementation_freeze_path" => replace(
            normpath(implementation_freeze_path),
            '\\' => '/',
        ),
        "implementation_freeze_sha256" => bytes2hex(sha256(read(
            implementation_freeze_path,
        ))),
        "input_manifest_path" => replace(normpath(input_manifest_path), '\\' => '/'),
        "input_manifest_sha256" => bytes2hex(sha256(read(input_manifest_path))),
        "julia_version" => string(VERSION),
        "julia_threads" => Threads.nthreads(),
        "manifest_sha256" => bytes2hex(sha256(read(joinpath(
            @__DIR__,
            "..",
            "..",
            "Manifest.toml",
        )))),
        "product_connected" => false,
        "project_sha256" => bytes2hex(sha256(read(joinpath(
            @__DIR__,
            "..",
            "..",
            "Project.toml",
        )))),
        "run_identity_sha256" => String(run_identity_sha256),
        "schema" => "geotarget.singular-s4-development-environment/v1",
        "s4_options" => _s4_options_document(s4_options),
        "warmup_sha256" => String(warmup_sha256),
    )
    raw_path = joinpath(result_directory, "raw.json")
    summary_path = joinpath(result_directory, "summary.json")
    environment_path = joinpath(result_directory, "environment.json")
    report_path = joinpath(result_directory, "report.md")
    write_json_artifact(raw_path, raw_document)
    write_json_artifact(summary_path, summary)
    write_json_artifact(environment_path, environment)
    open(report_path, "w") do io
        write(io, _s4_development_report(summary))
    end
    return Dict{String,Any}(
        "checkpoint_manifest_sha256" => String(checkpoint_manifest_sha256),
        "environment_sha256" => bytes2hex(sha256(read(environment_path))),
        "raw_sha256" => bytes2hex(sha256(read(raw_path))),
        "report_sha256" => bytes2hex(sha256(read(report_path))),
        "summary_sha256" => bytes2hex(sha256(read(summary_path))),
    )
end
