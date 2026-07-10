_evidence_real(value::Real) = string(value)

function _work_document(work::WorkSnapshot)
    return Dict{String,Any}(
        "budget_exhausted" => work.budget_exhausted,
        "callbacks" => work.callbacks,
        "calls_by_precision" => Any[
            Dict{String,Any}(
                "callbacks" => entry.callbacks,
                "precision_bits" => entry.precision_bits,
            ) for entry in work.calls_by_precision
        ],
        "deadline_reached" => work.deadline_reached,
        "elapsed_seconds" => work.elapsed_seconds,
        "factorization_calls" => work.factorization_calls,
        "iterations" => work.iterations,
        "jacobian_calls" => work.jacobian_calls,
        "maximum_precision_bits" => work.maximum_precision_bits,
        "precision_equivalent_oracle_work" => work.precision_equivalent_oracle_work,
        "residual_calls" => work.residual_calls,
        "target_calls" => work.target_calls,
    )
end

function _semantic_document(evidence::SemanticReplayEvidence)
    return Dict{String,Any}(
        "accepted" => evidence.accepted,
        "endpoint" => Any[_evidence_real(value) for value in evidence.endpoint],
        "precision_bits" => evidence.precision_bits,
        "residual_linf" => _evidence_real(evidence.residual_linf),
        "target" => _evidence_real(evidence.target),
    )
end

function _root_document(evidence::NumericalRootEvidence)
    return Dict{String,Any}(
        "condition_estimate" => _evidence_real(evidence.condition_estimate),
        "configuration_error_estimate" =>
            _evidence_real(evidence.configuration_error_estimate),
        "confirmation_endpoints" => Any[
            Any[_evidence_real(value) for value in endpoint] for
            endpoint in evidence.confirmation_endpoints
        ],
        "confirmation_targets" =>
            Any[_evidence_real(value) for value in evidence.confirmation_targets],
        "endpoint" => Any[_evidence_real(value) for value in evidence.endpoint],
        "method" => evidence.method,
        "numerical_rank" => evidence.numerical_rank,
        "precision_bits" => evidence.precision_bits,
        "precision_stages" => Any[evidence.precision_stages...],
        "rank_stable" => evidence.rank_stable,
        "residual_linf" => _evidence_real(evidence.residual_linf),
        "target" => _evidence_real(evidence.target),
        "target_error_estimate" => _evidence_real(evidence.target_error_estimate),
    )
end

function _root_document(evidence::NumericalManifoldRootEvidence)
    return Dict{String,Any}(
        "active_columns" => Any[evidence.active_columns...],
        "active_configuration_error_estimate" =>
            _evidence_real(evidence.active_configuration_error_estimate),
        "condition_estimate" => _evidence_real(evidence.condition_estimate),
        "configuration_mode" => "target_constant_manifold",
        "confirmation_endpoints" => Any[
            Any[_evidence_real(value) for value in endpoint] for
            endpoint in evidence.confirmation_endpoints
        ],
        "confirmation_targets" =>
            Any[_evidence_real(value) for value in evidence.confirmation_targets],
        "endpoint" => Any[_evidence_real(value) for value in evidence.endpoint],
        "method" => evidence.method,
        "nullspace_target_sensitivity" =>
            _evidence_real(evidence.nullspace_target_sensitivity),
        "numerical_rank" => evidence.numerical_rank,
        "precision_bits" => evidence.precision_bits,
        "precision_stages" => Any[evidence.precision_stages...],
        "rank_stable" => evidence.rank_stable,
        "residual_linf" => _evidence_real(evidence.residual_linf),
        "target" => _evidence_real(evidence.target),
        "target_error_estimate" => _evidence_real(evidence.target_error_estimate),
    )
end

function _root_document(evidence::NumericalSingularRootEvidence)
    return Dict{String,Any}(
        "canonical_confirmations_passed" => evidence.canonical_confirmations_passed,
        "condition_estimate" => _evidence_real(evidence.condition_estimate),
        "configuration_error_estimate" =>
            _evidence_real(evidence.configuration_error_estimate),
        "confirmation_endpoints" => Any[
            Any[_evidence_real(value) for value in endpoint] for
            endpoint in evidence.confirmation_endpoints
        ],
        "confirmation_residuals" =>
            Any[_evidence_real(value) for value in evidence.confirmation_residuals],
        "confirmation_targets" =>
            Any[_evidence_real(value) for value in evidence.confirmation_targets],
        "contraction_ratios" =>
            Any[_evidence_real(value) for value in evidence.contraction_ratios],
        "endpoint" => Any[_evidence_real(value) for value in evidence.endpoint],
        "independent_confirmations_passed" =>
            evidence.independent_confirmations_passed,
        "linear_trace_passed" => evidence.linear_trace_passed,
        "method" => evidence.method,
        "nullity" => evidence.nullity,
        "numerical_rank" => evidence.numerical_rank,
        "precision_bits" => evidence.precision_bits,
        "precision_stages" => Any[evidence.precision_stages...],
        "rank_stable" => evidence.rank_stable,
        "residual_linf" => _evidence_real(evidence.residual_linf),
        "route_rank_signatures" => Any[
            Dict{String,Any}(String(key) => value for (key, value) in pairs(signature)) for
            signature in evidence.route_rank_signatures
        ],
        "secant_updates" => evidence.secant_updates,
        "target" => _evidence_real(evidence.target),
        "target_error_estimate" => _evidence_real(evidence.target_error_estimate),
    )
end

function outcome_document(case::GeneratedEndpoint, outcome::ExperimentalOutcome)
    return Dict{String,Any}(
        "case_checksum" => case.checksum,
        "case_id" => case.input.oracle.id,
        "experiment_id" => EXPERIMENT_ID,
        "harness_version" => string(HARNESS_VERSION),
        "reason" => outcome.reason,
        "root_evidence" => outcome.root_evidence === nothing ?
                           nothing : _root_document(outcome.root_evidence),
        "route" => outcome.route,
        "semantic_replay" => outcome.semantic_replay === nothing ?
                              nothing : _semantic_document(outcome.semantic_replay),
        "status" => string(outcome.status),
        "variant" => outcome.variant,
        "work" => _work_document(outcome.work),
    )
end

function assessment_document(assessment::GoldAssessment)
    return Dict{String,Any}(
        "case_id" => assessment.case_id,
        "configuration_error" => assessment.configuration_error,
        "configuration_error_covered" => assessment.configuration_error_covered,
        "false_promotion" => assessment.false_promotion,
        "gold_success" => assessment.gold_success,
        "promoted" => assessment.promoted,
        "target_error" => assessment.target_error,
        "target_error_covered" => assessment.target_error_covered,
        "variant" => assessment.variant,
    )
end

function case_manifest_document(cases=fixed_control_cases())
    return Dict{String,Any}(
        "cases" => Any[
            Dict{String,Any}(
                "capability" => string(case.input.oracle.capability),
                "checksum" => case.checksum,
                "dimension" => case.input.oracle.dimension,
                "endpoint" => Any[case.input.endpoint...],
                "family" => case.input.oracle.family,
                "gold_analysis_only" => Dict{String,Any}(
                    "configuration" => case.gold.configuration,
                    "finite_discrete_target" => case.gold.finite_discrete_target,
                    "kind" => string(case.gold.kind),
                    "target" => case.gold.target,
                ),
                "id" => case.input.oracle.id,
                "metamorphic_group" => case.input.oracle.metamorphic_group,
                "parameters" => case.parameters,
                "residual_dimension" => case.input.oracle.residual_dimension,
            ) for case in cases
        ],
        "experiment_id" => EXPERIMENT_ID,
        "harness_version" => string(HARNESS_VERSION),
        "schema" => "geotarget.singular-development-input/v1",
    )
end

function _options_document(options::ExperimentOptions)
    return Dict{String,Any}(
        "configuration_error_goal" => options.configuration_error_goal,
        "confirmation_perturbation_radius" => options.confirmation_perturbation_radius,
        "error_reserve_multiplier" => options.error_reserve_multiplier,
        "finite_difference_exponent" => options.finite_difference_exponent,
        "independent_confirmation_count" => options.independent_confirmation_count,
        "maximum_callbacks" => options.maximum_callbacks,
        "maximum_iterations" => options.maximum_iterations,
        "precision_ladder" => Any[options.precision_ladder...],
        "rank_roundoff_multiplier" => options.rank_roundoff_multiplier,
        "required_precision_guard_bits" => options.required_precision_guard_bits,
        "semantic_precision_bits" => options.semantic_precision_bits,
        "semantic_residual_tolerance" => options.semantic_residual_tolerance,
        "target_error_goal" => options.target_error_goal,
        "wall_seconds" => options.wall_seconds,
    )
end

function development_input_document(
    cases=development_cases(),
    options::ExperimentOptions=ExperimentOptions();
    card_path=normpath(joinpath(@__DIR__, "..", "..", "EXP-SINGULAR-001.json")),
)
    case_document = case_manifest_document(cases)
    collection_material = join((case.checksum for case in cases), '\n')
    return Dict{String,Any}(
        "card_path" => replace(
            relpath(card_path, normpath(joinpath(@__DIR__, "..", "..", "..", ".."))),
            '\\' => '/',
        ),
        "card_sha256" => bytes2hex(sha256(read(card_path))),
        "case_collection_sha256" => bytes2hex(sha256(collection_material)),
        "cases" => case_document["cases"],
        "development_instance_count" => length(cases),
        "experiment_id" => EXPERIMENT_ID,
        "harness_version" => string(HARNESS_VERSION),
        "options" => _options_document(options),
        "schema" => "geotarget.singular-development-input/v1",
        "variants" => Any[
            "S0-POINT-REPLAY",
            "S1-AP-LMQR",
            "SLB-ANALYTIC-DERIVATIVES",
        ],
    )
end

function s2_development_input_document(
    cases=s2_development_cases(),
    options::ExperimentOptions=ExperimentOptions();
    card_path=normpath(joinpath(@__DIR__, "..", "..", "EXP-SINGULAR-001.json")),
)
    case_document = case_manifest_document(cases)
    collection_material = join((case.checksum for case in cases), '\n')
    return Dict{String,Any}(
        "card_path" => replace(
            relpath(card_path, normpath(joinpath(@__DIR__, "..", "..", "..", ".."))),
            '\\' => '/',
        ),
        "card_sha256" => bytes2hex(sha256(read(card_path))),
        "case_collection_sha256" => bytes2hex(sha256(collection_material)),
        "cases" => case_document["cases"],
        "development_instance_count" => length(cases),
        "experiment_id" => EXPERIMENT_ID,
        "harness_version" => string(HARNESS_VERSION),
        "options" => _options_document(options),
        "parent_gate" => "development-s0-s1-v0",
        "schema" => "geotarget.singular-s2-development-input/v1",
        "variants" => Any[
            "S1-AP-LMQR",
            "S2-AP-CPQR-SUBSET",
            "S2-ANALYTIC-SUBSET-CONTROL",
        ],
    )
end

function s3_development_input_document(
    cases=s3_development_cases(),
    options::ExperimentOptions=ExperimentOptions();
    card_path=normpath(joinpath(@__DIR__, "..", "..", "EXP-SINGULAR-001.json")),
    preregistration_path=normpath(joinpath(@__DIR__, "..", "s3-preregistration.json")),
    parent_summary_path=normpath(joinpath(
        @__DIR__,
        "..",
        "..",
        "..",
        "results",
        "EXP-SINGULAR-001",
        "development-s2-v0",
        "summary.json",
    )),
)
    case_document = case_manifest_document(cases)
    collection_material = join((case.checksum for case in cases), '\n')
    return Dict{String,Any}(
        "card_path" => replace(
            relpath(card_path, normpath(joinpath(@__DIR__, "..", "..", "..", ".."))),
            '\\' => '/',
        ),
        "card_sha256" => bytes2hex(sha256(read(card_path))),
        "case_collection_sha256" => bytes2hex(sha256(collection_material)),
        "cases" => case_document["cases"],
        "development_instance_count" => length(cases),
        "experiment_id" => EXPERIMENT_ID,
        "harness_version" => string(HARNESS_VERSION),
        "options" => _options_document(options),
        "parent_gate" => "development-s2-v0",
        "parent_summary_sha256" => bytes2hex(sha256(read(parent_summary_path))),
        "preregistration_sha256" => bytes2hex(sha256(read(preregistration_path))),
        "route_precision_bits" => Any[128, 256],
        "schema" => "geotarget.singular-s3-development-input/v1",
        "transform_namespace" => "singular-s3-development-v0",
        "variants" => Any[
            "S1-AP-LMQR",
            "S3-AP-BROYDEN",
            "S3-ANALYTIC-SECANT-CONTROL",
        ],
    )
end

function write_json_artifact(path::AbstractString, document)
    destination = abspath(String(path))
    mkpath(dirname(destination))
    temporary = string(destination, ".tmp-", getpid(), '-', time_ns())
    try
        open(temporary, "w") do io
            JSON3.pretty(io, document; allow_inf=false)
            write(io, '\n')
        end
        mv(temporary, destination; force=true)
    finally
        isfile(temporary) && rm(temporary; force=true)
    end
    return destination
end
