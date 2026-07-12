include(joinpath(@__DIR__, "run_stagea_outcomes.jl"))
include(joinpath(@__DIR__, "src", "stagec_t0_inputs.jl"))
using .StageCT0Inputs
include(joinpath(@__DIR__, "src", "soft_tgo_ordering.jl"))
using .StageCSoftTGOOrdering
const STAGEC_ROOT, STAGEC_REPO = T0O_ROOT, T0O_REPO
const STAGEC_RUNNER = @__FILE__
const STAGEC_INPUT = StageCT0Inputs.DEFAULT_STAGEC_T0_INPUT_MANIFEST_PATH
const STAGEC_AUTH = joinpath(STAGEC_ROOT, "stagec-t0-outcome-authorization.json")
const STAGEC_AGGREGATOR = joinpath(STAGEC_ROOT, "aggregate_stagec_t0.py")
const STAGEC_PREARM_ROOT = joinpath(STAGEC_ROOT, "materialized", "stagec-t0")
const STAGEC_ARMS = StageCT0Inputs.STAGEC_T0_CANDIDATE_ARMS
const STAGEC_SOURCE_COUNT = StageCT0Inputs.STAGEC_T0_BATCH_SIZE * StageCT0Inputs.STAGEC_T0_BATCH_COUNT
_stagec_float_bits(value::Float64) = lowercase(string(reinterpret(UInt64, value); base=16, pad=16))
_stagec_vector_bits(values) = _stagec_float_bits.(Float64[values...])
function _stagec_matrix_bits(matrix::AbstractMatrix{Float64})
    return Any[
        Any[_stagec_float_bits(matrix[row, column]) for row in axes(matrix, 1)] for
        column in axes(matrix, 2)
    ]
end
function _stagec_matrix_document(matrix::Matrix{Float64})
    all(isfinite, matrix) || error("Stage-C matrix contains a nonfinite coordinate")
    payload = Dict{String,Any}(
        "column_count" => size(matrix, 2),
        "coordinate_float64_bits_by_column" => _stagec_matrix_bits(matrix),
        "dimension" => size(matrix, 1),
    )
    return merge(payload, Dict(
        "matrix_sha256" => bytes2hex(sha256(codeunits(canonical_json(payload)))),
    ))
end
function _stagec_write_exclusive(path, document; mode=0o600)
    ispath(path) && error("refusing to overwrite one-shot artifact: $path")
    mkpath(dirname(path))
    stream = Base.Filesystem.open(
        path,
        Base.JL_O_WRONLY | Base.JL_O_CREAT | Base.JL_O_EXCL,
        mode,
    )
    try
        write(stream, canonical_json(document), '\n')
    finally
        close(stream)
    end
    return sha256_file(path)
end
function _stagec_load_inputs(path; selected_case=nothing, artifacts=false)
    committed(path, "Stage-C T0 input manifest")
    document = json_document(path, "Stage-C T0 input manifest")
    get(document, "schema_version", nothing) ==
        "geotarget.discovery-stagec-soft-tgo-t0-input/v1" || error("input schema drifted")
    get(document, "stage", nothing) == "stage-c-soft-tgo-t0" &&
        get(document, "nonpromotional_t0", false) === true || error("scope drifted")
    get(document, "case_count", nothing) == StageCT0Inputs.STAGEC_T0_CASE_COUNT &&
        get(document, "target_count", nothing) == 34 &&
        get(document, "method", nothing) == T0O_METHODS[1] || error("input size drifted")
    parse(UInt64, String(document["root_seed"])) == StageCT0Inputs.STAGEC_T0_ROOT_SEED &&
        get(document, "seed_namespace", nothing) == StageCT0Inputs.STAGEC_T0_SEED_NAMESPACE ||
        error("source seed contract drifted")
    freeze_path = ExperimentDisc001.DEFAULT_CHAMPION_FREEZE_PATH
    committed(freeze_path, "local freeze")
    freeze_sha = String(document["local_freeze_sha256"])
    sha256_text(freeze_sha) && sha256_file(freeze_path) == freeze_sha || error("freeze drifted")
    authority = materialization_preflight(freeze_path)
    authority.freeze_sha256 == freeze_sha || error("freeze authority drifted")
    freeze = json_document(freeze_path, "local freeze")
    preregistration = document["preregistration"]
    prereg_path = repo_path(preregistration["path"])
    committed(prereg_path, "Stage-C T0 preregistration")
    sha256_file(prereg_path) == preregistration["sha256"] || error("preregistration drifted")
    StageCT0Inputs._validate_registration(prereg_path, authority)
    problems = StageCT0Inputs.stagec_t0_problems()
    cases = document["cases"]
    length(cases) == length(problems) == StageCT0Inputs.STAGEC_T0_CASE_COUNT ||
        error("case list drifted")
    loaded = Any[nothing for _ in problems]
    for (case_index, problem) in enumerate(problems)
        case = cases[case_index]
        proposal = case["proposal"]
        get(case, "case_index", nothing) == case_index &&
            get(case, "formal_case_id", nothing) ==
                StageCT0Inputs.STAGEC_T0_RECIPE[case_index].formal_case_id &&
            get(case, "instance_id", nothing) == problem.instance_id &&
            get(case, "dimension", nothing) == problem.dimension &&
            get(case, "source_index", nothing) == StageCT0Inputs.STAGEC_T0_SOURCE_INDICES[case_index] &&
            get(case, "replay_checksum", nothing) == replay_checksum(problem) ||
            error("case replay drifted at $case_index")
        get(proposal, "truth_free_metadata", false) === true ||
            error("proposal contract drifted at $case_index")
        expected_seed = derive_seed(
            StageCT0Inputs.STAGEC_T0_ROOT_SEED,
            StageCT0Inputs.STAGEC_T0_METHOD,
            case_index,
            1,
            StageCT0Inputs.STAGEC_T0_SEED_NAMESPACE,
        )
        parse(UInt64, String(proposal["replicate_seed"])) == expected_seed ||
            error("proposal seed drifted at $case_index")
        load_artifact = artifacts && (selected_case === nothing || selected_case == case_index)
        load_artifact || continue
        artifact_path = repo_path(proposal["path"])
        sha256_file(artifact_path) == proposal["file_sha256"] || error("proposal file drifted")
        artifact = read_matrix_artifact(artifact_path)
        StageCT0Inputs._truth_free(artifact)
        artifact.method == D0_IID_ALL && artifact_sha256(artifact) == proposal["artifact_sha256"] &&
            artifact.authority_sha256 == freeze_sha && artifact.replicate_seed == expected_seed ||
            error("proposal artifact drifted")
        size(artifact.coordinates) == (problem.dimension, STAGEC_SOURCE_COUNT) &&
            all(==(:iid), artifact.lane_schedule) && static_prefix_audit(artifact).valid ||
            error("D0 maximum matrix drifted")
        loaded[case_index] = (artifact, proposal)
    end
    return (; document, sha256=sha256_file(path), problems, loaded, freeze,
        prereg=(prereg_path, String(preregistration["sha256"])))
end
function _stagec_authorize(path, input, input_sha, prereg)
    committed(path, "Stage-C T0 outcome authorization")
    authorization = json_document(path, "Stage-C T0 outcome authorization")
    get(authorization, "schema_version", nothing) ==
        "geotarget.discovery-stagec-soft-tgo-t0-outcome-authorization/v1" &&
        get(authorization, "outcome_execution_authorized", false) === true &&
        get(authorization, "nonpromotional_t0", false) === true || error("outcomes unauthorized")
    repo_path(authorization["input_manifest"]["path"]) == abspath(input) &&
        authorization["input_manifest"]["sha256"] == input_sha || error("authorized input drifted")
    repo_path(authorization["preregistration"]["path"]) == prereg[1] &&
        authorization["preregistration"]["sha256"] == prereg[2] || error("authorized prereg drifted")
    committed(STAGEC_RUNNER, "Stage-C T0 runner")
    committed(STAGEC_AGGREGATOR, "Stage-C T0 aggregator")
    authorization["runner_source_sha256"] == sha256_file(STAGEC_RUNNER) &&
        authorization["aggregator_source_sha256"] == sha256_file(STAGEC_AGGREGATOR) ||
        error("authorized executable source drifted")
    dependencies = authorization["dependency_source_sha256"]
    for source in (
        joinpath(STAGEC_ROOT, "run_t0_outcomes.jl"),
        joinpath(STAGEC_ROOT, "run_stagea_outcomes.jl"),
        joinpath(STAGEC_ROOT, "src", "stagec_t0_inputs.jl"),
        joinpath(STAGEC_ROOT, "src", "soft_tgo_ordering.jl"),
    )
        get(dependencies, repo_relative(source), nothing) == sha256_file(source) ||
            error("authorized dependency drifted: $(basename(source))")
    end
    return (; document=authorization, sha256=sha256_file(path))
end
function _stagec_execution_host(case_index, cpu)
    1 <= case_index <= StageCT0Inputs.STAGEC_T0_CASE_COUNT || error("case index out of range")
    cpu == case_index - 1 && 0 <= cpu <= 11 || error("case/CPU assignment drifted")
    get(ENV, "GEOTARGET_CASE_PROCESS_LIMIT", "unset") == "12" ||
        error("GEOTARGET_CASE_PROCESS_LIMIT=12 is required")
    matched = match(r"(?m)^Cpus_allowed_list:\s*(.+)$", read("/proc/self/status", String))
    matched !== nothing || error("cannot inspect CPU affinity")
    allowed = strip(matched.captures[1])
    allowed == string(cpu) && ccall(:sched_getcpu, Cint, ()) == cpu ||
        error("process must be pinned to CPU $cpu")
    return Dict("assigned_cpu" => cpu, "case_process_limit" => 12,
        "cpus_allowed_list" => allowed, "solver_worker_count" => 1)
end
function _stagec_acquire_cpu(cpu)
    stream = open("/tmp/geotarget-exp-disc-001-stagec-t0-cpu-$cpu.lock", "w")
    ccall(:flock, Cint, (Cint, Cint), fd(stream), 2 | 4) == 0 ||
        (close(stream); error("CPU $cpu already has a Stage-C case process"))
    return stream
end
mutable struct _StageCPrescoreCapture
    candidates::Vector{OrderingCandidate}
    records::Vector{Dict{String,Any}}
    branch_capability::Union{Nothing,Bool}
end
_StageCPrescoreCapture() = _StageCPrescoreCapture(OrderingCandidate[], Dict{String,Any}[], nothing)
function _stagec_observe(case::SolverExperimentCase, start::Vector{Float64})
    evaluation = evaluate_case(case, start)
    scales = Float64[case.residual_scales...]
    scale_contract = length(scales) == case.residual_dimension &&
        all(value -> isfinite(value) && value > 0, scales)
    residual = scale_contract ? Float64[
        evaluation.residuals[index] / scales[index] for index in 1:case.residual_dimension
    ] : Float64[]
    guards = collect(evaluation.public_guards)
    guard_contract = length(guards) == case.public_guard_count &&
        allunique(guard.token for guard in guards) && all(guard ->
            isfinite(guard.margin) && isfinite(guard.scale) && guard.scale > 0 &&
            (guard.strict ? guard.margin > 0 : guard.margin >= 0), guards)
    branch_contract = case.has_branch_token ? evaluation.branch_token !== nothing :
        evaluation.branch_token === nothing
    bounds_contract = length(start) == case.dimension && all(isfinite, start) && all(
        case.lower_bounds[index] <= start[index] <= case.upper_bounds[index] for
        index in eachindex(start)
    )
    score = StageCSoftTGOOrdering._scaled_residual_norm(residual)
    valid = evaluation.finite && evaluation.semantics_valid && bounds_contract &&
        guard_contract && branch_contract && score !== nothing
    return (; residual, score, branch_token=evaluation.branch_token, valid)
end
function _stagec_prescore_variant(matrix::Matrix{Float64}, capture::_StageCPrescoreCapture)
    runner = function (case, _start)
        isempty(capture.candidates) && isempty(capture.records) || error("prescore reused")
        capture.branch_capability = case.has_branch_token
        for source_ordinal in axes(matrix, 2)
            start = Vector{Float64}(matrix[:, source_ordinal])
            observation = try
                _stagec_observe(case, start)
            catch
                (residual=Float64[], score=nothing, branch_token=nothing, valid=false)
            end
            push!(capture.candidates, OrderingCandidate(
                source_ordinal,
                start,
                observation.residual;
                branch_token=observation.branch_token,
                canonical_valid=observation.valid,
            ))
            push!(capture.records, Dict{String,Any}(
                "branch_fallback" => nothing,
                "branch_partition_ordinal" => nothing,
                "canonical_valid" => observation.valid,
                "scaled_residual_float64_bits" => _stagec_vector_bits(observation.residual),
                "score_float64_bits" => observation.score === nothing ? nothing :
                    _stagec_float_bits(observation.score),
                "source_ordinal" => source_ordinal,
                "start_float64_bits" => _stagec_vector_bits(start),
            ))
        end
        return SolverAttemptOutcome(
            nothing;
            status="STAGEC_PRESCORE_ONLY",
            evaluations=STAGEC_SOURCE_COUNT,
            iterations=STAGEC_SOURCE_COUNT,
            diagnostic="truth-blind prescore; no answer endpoint",
        )
    end
    return SolverVariant("STAGEC-T0-PRESCORE-ONLY", runner; configuration=(;
        answer_authority=false,
        callbacks=STAGEC_SOURCE_COUNT,
        target_visible=false,
    ))
end
function _stagec_prescore(problem, matrix)
    capture = _StageCPrescoreCapture()
    run_problem = StageCT0Inputs.stagec_t0_problem_with_proposals(problem, matrix)
    run = run_solver_experiment(
        [run_problem],
        [_stagec_prescore_variant(matrix, capture)];
        prefixes=(1,),
        evaluation_limit=STAGEC_SOURCE_COUNT,
    )
    attempt = only(run.attempts)
    length(capture.candidates) == STAGEC_SOURCE_COUNT &&
        attempt.endpoint === nothing && attempt.status == "STAGEC_PRESCORE_ONLY" &&
        attempt.evaluations == attempt.reported_evaluations == STAGEC_SOURCE_COUNT &&
        !attempt.evaluation_count_mismatch && !attempt.budget_exhausted &&
        attempt.exception === nothing || error("truth-blind prescore failed")
    return (; capture, attempt)
end
function _stagec_truth_free_value(value)
    (value === nothing || value isa Number || value isa Bool || value isa AbstractString) &&
        return value
    value isa Symbol && return String(value)
    value isa Enum && return string(value)
    value isa AbstractVector && return Any[_stagec_truth_free_value(item) for item in value]
    names = fieldnames(typeof(value))
    isempty(names) && error("unsupported diagnostic value $(typeof(value))")
    forbidden = ("token", "target", "gold", "family", "instance", "identity")
    return Dict{String,Any}(String(name) => begin
        any(part -> occursin(part, lowercase(String(name))), forbidden) &&
            error("ordering diagnostic exposed forbidden field $name")
        _stagec_truth_free_value(getfield(value, name))
    end for name in names)
end
function _stagec_arm(name)
    name == "FIFO_SCORED" && return FIFO_SCORED
    name == "RESIDUAL_ONLY" && return RESIDUAL_ONLY
    name == "SOFT_TGO" && return SOFT_TGO
    error("unknown Stage-C arm")
end
function _stagec_schedules(candidates, records, matrix, lower, upper, branch_capability)
    schedules = Dict(name => Int[] for name in STAGEC_ARMS)
    batch_documents = Dict{String,Any}[]
    for batch_index in 1:StageCT0Inputs.STAGEC_T0_BATCH_COUNT
        first_column = (batch_index - 1) * StageCT0Inputs.STAGEC_T0_BATCH_SIZE + 1
        columns = first_column:(first_column + StageCT0Inputs.STAGEC_T0_BATCH_SIZE - 1)
        batch_candidates = candidates[columns]
        results = Dict{String,OrderingResult}()
        arm_documents = Dict{String,Any}[]
        for name in STAGEC_ARMS
            result = order_fixed_batch(
                batch_candidates,
                lower,
                upper;
                arm=_stagec_arm(name),
                branch_capability,
            )
            source_ordinals = [batch_candidates[index].source_ordinal for index in result.permutation]
            sort(source_ordinals) == collect(columns) && result.diagnostics.all_candidates_drained ||
                error("$name did not drain batch $batch_index")
            append!(schedules[name], source_ordinals)
            results[name] = result
            push!(arm_documents, Dict(
                "diagnostics" => _stagec_truth_free_value(result.diagnostics),
                "name" => name,
                "permutation_within_batch" => result.permutation,
                "source_ordinal_schedule" => source_ordinals,
            ))
        end
        reference = results["FIFO_SCORED"].diagnostics.groups
        for (partition_ordinal, group) in enumerate(reference)
            for source_ordinal in group.neighborhood_source_ordinals
                records[source_ordinal]["branch_partition_ordinal"] = partition_ordinal
                records[source_ordinal]["branch_fallback"] = group.fallback
            end
        end
        all(record -> record["branch_partition_ordinal"] !== nothing, records[columns]) ||
            error("branch partition serialization was incomplete")
        push!(batch_documents, Dict(
            "arms" => arm_documents,
            "batch_index" => batch_index,
            "logical_ledger" => "PRESCORE16_THEN_16_WHOLE_LOCAL_ATTEMPTS",
            "prescore_callback_cost" => StageCT0Inputs.STAGEC_T0_BATCH_SIZE,
            "source_ordinal_range" => [first(columns), last(columns)],
        ))
    end
    matrices = Dict(name => Matrix{Float64}(matrix[:, schedules[name]]) for name in STAGEC_ARMS)
    schedules["FIFO_SCORED"] == collect(1:STAGEC_SOURCE_COUNT) || error("FIFO order drifted")
    all(sort(schedule) == collect(1:STAGEC_SOURCE_COUNT) for schedule in values(schedules)) ||
        error("an arm did not drain the maximum matrix")
    return (; schedules, matrices, batches=batch_documents)
end
function _stagec_prearm(input_sha, prereg, authorization, proposal, artifact, problem,
    prescore, schedule)
    arm_documents = Any[]
    for name in STAGEC_ARMS
        push!(arm_documents, Dict(
            "name" => name,
            "ordered_matrix" => _stagec_matrix_document(schedule.matrices[name]),
            "source_ordinal_schedule" => schedule.schedules[name],
        ))
    end
    batch_sha = bytes2hex(sha256(codeunits(canonical_json(schedule.batches))))
    bounds = Dict(
        "lower_float64_bits" => _stagec_vector_bits(problem.lower_bounds),
        "upper_float64_bits" => _stagec_vector_bits(problem.upper_bounds),
    )
    bounds["bounds_sha256"] = bytes2hex(sha256(codeunits(canonical_json(bounds))))
    return Dict{String,Any}(
        "arm_order" => collect(STAGEC_ARMS),
        "arms" => arm_documents,
        "authorization" => Dict("path" => repo_relative(authorization[1]), "sha256" => authorization[2]),
        "batch_schedule" => schedule.batches,
        "batch_schedule_sha256" => batch_sha,
        "bounds" => bounds,
        "branch_capability" => something(prescore.capture.branch_capability),
        "experiment_id" => "EXP-DISC-001",
        "input_manifest_sha256" => input_sha,
        "prescore_records" => prescore.capture.records,
        "preregistration" => Dict("path" => repo_relative(prereg[1]), "sha256" => prereg[2]),
        "schema_version" => "geotarget.discovery-stagec-soft-tgo-t0-prearm/v1",
        "source_artifact" => Dict(
            "artifact_sha256" => artifact.sha256,
            "file_sha256" => proposal["file_sha256"],
            "path" => proposal["path"],
        ),
        "source_matrix" => _stagec_matrix_document(Matrix{Float64}(artifact.coordinates)),
        "stage" => "stage-c-soft-tgo-t0",
        "truth_free" => true,
    )
end
function _stagec_terminal(attempts)
    return Dict{String,Any}(
        "attempt_count" => length(attempts),
        "callback_work" => sum(attempt.evaluations for attempt in attempts),
        "callback_cap_violations" => count(attempt ->
            attempt.evaluations > StageCT0Inputs.STAGEC_T0_LOCAL_CALLBACK_CAP ||
            attempt.reported_evaluations > StageCT0Inputs.STAGEC_T0_LOCAL_CALLBACK_CAP, attempts),
        "evaluation_count_mismatches" => count(attempt -> attempt.evaluation_count_mismatch, attempts),
        "exceptions" => count(attempt -> attempt.exception !== nothing, attempts),
        "runner_budget_exhausted" => count(attempt -> attempt.budget_exhausted, attempts),
    )
end
function _stagec_run_arm(problem, matrix, source_ordinals, variant)
    run_problem = StageCT0Inputs.stagec_t0_problem_with_proposals(problem, matrix)
    run = run_solver_experiment(
        [run_problem],
        [variant];
        prefixes=(STAGEC_SOURCE_COUNT,),
        evaluation_limit=StageCT0Inputs.STAGEC_T0_LOCAL_CALLBACK_CAP,
    )
    attempts = collect(run.attempts)
    serialized = solver_experiment_document(run)["attempts"]
    length(attempts) == length(serialized) == length(source_ordinals) == STAGEC_SOURCE_COUNT ||
        error("arm attempt count drifted")
    for position in eachindex(attempts)
        reinterpret(UInt64, collect(attempts[position].start)) ==
            reinterpret(UInt64, matrix[:, position]) || error("arm start bits drifted")
        serialized[position]["source_ordinal"] = source_ordinals[position]
    end
    return (; attempts, serialized, terminal=_stagec_terminal(attempts))
end
function _stagec_attempt_fingerprint(document)
    ignored = Set(("start_index", "timing_phase", "wall_seconds"))
    return canonical_json(Dict(key => value for (key, value) in document if !(key in ignored)))
end
function _stagec_assert_paired(arms)
    reference = Dict(
        attempt["source_ordinal"] => _stagec_attempt_fingerprint(attempt) for
        attempt in arms[1]["attempts"]
    )
    for arm in arms[2:end], attempt in arm["attempts"]
        get(reference, attempt["source_ordinal"], nothing) == _stagec_attempt_fingerprint(attempt) ||
            error("per-source local outcome drifted between ordering arms")
    end
end
function _stagec_work_ledger(arms, prescore_attempt)
    logical = Dict{String,Any}()
    charged = Dict{String,Any}()
    for arm in arms
        entries = Any[]
        attempts = arm["attempt_objects"]
        for batch_index in 1:StageCT0Inputs.STAGEC_T0_BATCH_COUNT
            first_position = (batch_index - 1) * StageCT0Inputs.STAGEC_T0_BATCH_SIZE + 1
            positions = first_position:(first_position + StageCT0Inputs.STAGEC_T0_BATCH_SIZE - 1)
            push!(entries, Dict(
                "attempt_position_range" => [first(positions), last(positions)],
                "batch_index" => batch_index,
                "local_observed_callbacks" => sum(attempt.evaluations for attempt in attempts[positions]),
                "prescore_observed_callbacks" => StageCT0Inputs.STAGEC_T0_BATCH_SIZE,
                "source_ordinals" => arm["source_ordinals"][positions],
            ))
        end
        logical[arm["name"]] = entries
        charged[arm["name"]] = prescore_attempt.evaluations + arm["terminal"]["callback_work"]
    end
    fifo = only(filter(arm -> arm["name"] == "FIFO_SCORED", arms))
    return Dict{String,Any}(
        "charged_total_callback_work_by_arm" => charged,
        "derived_fifo_unscored" => Dict(
            "prescore_charge" => 0,
            "reuses_arm" => "FIFO_SCORED",
            "solver_executed" => false,
            "total_callback_work" => fifo["terminal"]["callback_work"],
        ),
        "logical_rolling_batches_by_arm" => logical,
        "physical_prescore_observed_callbacks" => prescore_attempt.evaluations,
        "physical_prescore_reported_callbacks" => prescore_attempt.reported_evaluations,
        "work_contract" => "PRESCORE16_THEN_16_WHOLE_LOCAL_ATTEMPTS_V1",
    )
end
function _stagec_prescore_attempt_document(attempt)
    return Dict{String,Any}(
        "budget_exhausted" => attempt.budget_exhausted,
        "endpoint" => nothing,
        "evaluation_count_mismatch" => attempt.evaluation_count_mismatch,
        "exception" => attempt.exception,
        "iterations" => attempt.iterations,
        "observed_evaluations" => attempt.evaluations,
        "reported_evaluations" => attempt.reported_evaluations,
        "status" => attempt.status,
    )
end
function _stagec_execute(input, auth_path, output, prearm_output, case_index, cpu)
    project, threads = active_project(), thread_contract()
    isempty(strip(read(`git -C $STAGEC_REPO status --porcelain`, String))) || error("clean tree required")
    ispath(output) && error("refusing to overwrite outcome")
    ispath(prearm_output) && error("refusing to overwrite prearm")
    abspath(output) == abspath(prearm_output) && error("output paths must differ")
    header = json_document(input, "Stage-C T0 input manifest")
    prereg = (repo_path(header["preregistration"]["path"]), header["preregistration"]["sha256"])
    authorization = _stagec_authorize(auth_path, input, sha256_file(input), prereg)
    host, slot = _stagec_execution_host(case_index, cpu), _stagec_acquire_cpu(cpu)
    try
        bundle = _stagec_load_inputs(input; selected_case=case_index, artifacts=true)
        problem = bundle.problems[case_index]
        artifact, proposal = bundle.loaded[case_index]
        source_matrix = Matrix{Float64}(artifact.coordinates)
        prescore = _stagec_prescore(problem, source_matrix)
        schedule = _stagec_schedules(
            prescore.capture.candidates,
            prescore.capture.records,
            source_matrix,
            problem.lower_bounds,
            problem.upper_bounds,
            something(prescore.capture.branch_capability),
        )
        prearm = _stagec_prearm(
            bundle.sha256,
            bundle.prereg,
            (auth_path, authorization.sha256),
            proposal,
            artifact,
            problem,
            prescore,
            schedule,
        )
        prearm_sha = _stagec_write_exclusive(prearm_output, prearm)
        variant = local_variant(bundle.freeze)
        arm_records = Dict{String,Any}[]
        internal_arms = Dict{String,Any}[]
        for name in STAGEC_ARMS
            phase = _stagec_run_arm(
                problem,
                schedule.matrices[name],
                schedule.schedules[name],
                variant,
            )
            push!(arm_records, Dict(
                "attempts" => phase.serialized,
                "matrix_sha256" => _stagec_matrix_document(schedule.matrices[name])["matrix_sha256"],
                "name" => name,
                "source_ordinals" => schedule.schedules[name],
                "terminal" => phase.terminal,
            ))
            push!(internal_arms, Dict(
                "attempt_objects" => phase.attempts,
                "attempts" => phase.serialized,
                "name" => name,
                "source_ordinals" => schedule.schedules[name],
                "terminal" => phase.terminal,
            ))
        end
        _stagec_assert_paired(arm_records)
        work = _stagec_work_ledger(internal_arms, prescore.attempt)
        document = Dict{String,Any}(
            "arm_order" => collect(STAGEC_ARMS),
            "arms" => arm_records,
            "authorization" => Dict("path" => repo_relative(auth_path), "sha256" => authorization.sha256),
            "case_index" => case_index,
            "experiment_id" => "EXP-DISC-001",
            "input_manifest" => Dict("path" => repo_relative(input), "sha256" => bundle.sha256),
            "lab_confirmation_512_768" => false,
            "nonpromotional_t0" => true,
            "prearm" => Dict(
                "batch_schedule_sha256" => prearm["batch_schedule_sha256"],
                "path" => repo_relative(prearm_output),
                "sha256" => prearm_sha,
            ),
            "prescore_attempt" => _stagec_prescore_attempt_document(prescore.attempt),
            "preregistration" => Dict("path" => repo_relative(bundle.prereg[1]), "sha256" => bundle.prereg[2]),
            "revision" => Dict("git_dirty" => false,
                "git_head" => readchomp(`git -C $STAGEC_REPO rev-parse HEAD`)),
            "schema_version" => "geotarget.discovery-stagec-soft-tgo-t0-raw/v1",
            "stage" => "stage-c-soft-tgo-t0",
            "thread_contract" => merge(threads, host),
            "work_ledger" => work,
        )
        _stagec_write_exclusive(output, document)
        println("prearm=", prearm_output)
        println("output=", output)
        return document
    finally
        close(slot)
    end
end
function _stagec_preflight(input, case_index)
    project, threads, bundle = active_project(), thread_contract(), _stagec_load_inputs(input)
    indices = case_index === nothing ? collect(1:StageCT0Inputs.STAGEC_T0_CASE_COUNT) : [case_index]
    all(index -> 1 <= index <= StageCT0Inputs.STAGEC_T0_CASE_COUNT, indices) ||
        error("case index out of range")
    variant = local_variant(bundle.freeze)
    return Dict{String,Any}(
        "active_project" => project,
        "arm_order" => collect(STAGEC_ARMS),
        "case_indices" => indices,
        "derived_control" => StageCT0Inputs.STAGEC_T0_DERIVED_CONTROL,
        "input_manifest_sha256" => bundle.sha256,
        "local_callback_cap" => StageCT0Inputs.STAGEC_T0_LOCAL_CALLBACK_CAP,
        "local_policy" => variant.name,
        "nonpromotional_t0" => true,
        "outcomes_executed" => false,
        "schema_version" => "geotarget.discovery-stagec-soft-tgo-t0-preflight/v1",
        "thread_contract" => threads,
    )
end
function _stagec_self_test()
    active_project(); thread_contract()
    dimension = 2
    matrix = Matrix{Float64}(undef, dimension, STAGEC_SOURCE_COUNT)
    candidates = OrderingCandidate[]
    records = Dict{String,Any}[]
    for ordinal in 1:STAGEC_SOURCE_COUNT
        point = [0.8sin(ordinal), 0.8cos(ordinal)]
        matrix[:, ordinal] .= point
        push!(candidates, OrderingCandidate(
            ordinal, point, [Float64(mod(ordinal, 11)), Float64(mod(ordinal, 7))];
            branch_token=nothing, canonical_valid=true,
        ))
        push!(records, Dict("branch_partition_ordinal" => nothing,
            "branch_fallback" => nothing))
    end
    schedule = _stagec_schedules(candidates, records, matrix, fill(-1.0, 2), fill(1.0, 2), false)
    all(length(schedule.schedules[name]) == STAGEC_SOURCE_COUNT for name in STAGEC_ARMS) ||
        error("synthetic schedule did not drain")
    schedule.schedules["FIFO_SCORED"] == collect(1:STAGEC_SOURCE_COUNT) || error("FIFO fixture")
    mktempdir() do directory
        path = joinpath(directory, "exclusive.json")
        _stagec_write_exclusive(path, Dict("fixture" => true))
        isfile(path) || error("exclusive writer fixture")
    end
    return Dict{String,Any}(
        "arm_order" => collect(STAGEC_ARMS),
        "batch_count" => StageCT0Inputs.STAGEC_T0_BATCH_COUNT,
        "batch_size" => StageCT0Inputs.STAGEC_T0_BATCH_SIZE,
        "case_count" => StageCT0Inputs.STAGEC_T0_CASE_COUNT,
        "outcomes_executed" => false,
        "schema_version" => "geotarget.discovery-stagec-soft-tgo-t0-runner-self-test/v1",
        "solver_invocations" => 0,
    )
end
function _stagec_parse_args(args)
    mode, input, auth = :preflight, STAGEC_INPUT, STAGEC_AUTH
    output = prearm = case_index = cpu = nothing
    for argument in args
        argument == "--execute" ? (mode = :execute) :
        argument == "--self-test" ? (mode = :self_test) :
        argument == "--preflight-only" ? (mode = :preflight) :
        argument == "--help" ? (return nothing) :
        startswith(argument, "--input-manifest=") ?
            (input = abspath(split(argument, '='; limit=2)[2])) :
        startswith(argument, "--authorization=") ?
            (auth = abspath(split(argument, '='; limit=2)[2])) :
        startswith(argument, "--output=") ?
            (output = abspath(split(argument, '='; limit=2)[2])) :
        startswith(argument, "--prearm-output=") ?
            (prearm = abspath(split(argument, '='; limit=2)[2])) :
        startswith(argument, "--case-index=") ?
            (case_index = parse(Int, split(argument, '=')[2])) :
        startswith(argument, "--assigned-cpu=") ?
            (cpu = parse(Int, split(argument, '=')[2])) : error("unknown option: $argument")
    end
    if case_index !== nothing
        prearm === nothing && (prearm = joinpath(
            STAGEC_PREARM_ROOT, "prearm-case-$(lpad(case_index, 2, '0')).json"))
        output === nothing && (output = joinpath(
            STAGEC_REPO, "benchmarks", "results", "raw",
            "exp-disc-001-stagec-t0-case-$(lpad(case_index, 2, '0')).json"))
    end
    return (; mode, input, auth, output, prearm, case_index, cpu)
end
function stagec_t0_main(args=ARGS)
    options = _stagec_parse_args(args)
    options === nothing && return print("Use --preflight-only, --self-test, or --execute --case-index=N --assigned-cpu=N\n")
    if options.mode == :execute
        options.case_index === nothing && error("--case-index is required")
        options.cpu === nothing && error("--assigned-cpu is required")
    end
    result = options.mode == :self_test ? _stagec_self_test() :
        options.mode == :preflight ? _stagec_preflight(options.input, options.case_index) :
        _stagec_execute(options.input, options.auth, options.output, options.prearm,
            options.case_index, options.cpu)
    options.mode == :execute || println(canonical_json(result))
    return result
end
abspath(PROGRAM_FILE) == abspath(@__FILE__) && stagec_t0_main()
