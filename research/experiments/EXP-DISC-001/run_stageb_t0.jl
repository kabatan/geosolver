include(joinpath(@__DIR__, "run_stagea_outcomes.jl"))
include(joinpath(@__DIR__, "src", "stageb_t0_inputs.jl"))
using .StageBT0Inputs
include(joinpath(@__DIR__, "src", "weak_geometry.jl"))
using .StageBWeakGeometry

const STAGEB_ROOT = T0O_ROOT
const STAGEB_REPO = T0O_REPO
const STAGEB_RUNNER = @__FILE__
const STAGEB_INPUT = StageBT0Inputs.DEFAULT_STAGEB_T0_INPUT_MANIFEST_PATH
const STAGEB_AUTH = joinpath(STAGEB_ROOT, "stageb-t0-outcome-authorization.json")
const STAGEB_AGGREGATOR = joinpath(STAGEB_ROOT, "aggregate_stageb_t0.py")
const STAGEB_PREARM_ROOT = joinpath(STAGEB_ROOT, "materialized", "stageb-t0")
const STAGEB_SOURCE_PREFIX = 64
const STAGEB_ARM_COLUMNS = 64
const STAGEB_LOCAL_CAP = 600
const STAGEB_GEOMETRY_CAP = 9_000
const STAGEB_GEOMETRY_NAMESPACE = "stageb-t0-weak-geometry-v1"
const STAGEB_ARMS = ("CONTINUATION", "ISOTROPIC", "WEAK")

_stageb_float_bits(value::Float64) =
    lowercase(string(reinterpret(UInt64, value); base=16, pad=16))

function _stageb_matrix_bits(matrix::AbstractMatrix{Float64})
    return Any[
        Any[_stageb_float_bits(matrix[row, column]) for row in axes(matrix, 1)] for
        column in axes(matrix, 2)
    ]
end

function _stageb_matrix_document(matrix::Matrix{Float64})
    size(matrix, 2) == STAGEB_ARM_COLUMNS || error("arm matrix must have 64 columns")
    all(isfinite, matrix) || error("arm matrix contains a nonfinite coordinate")
    payload = Dict{String,Any}(
        "column_count" => size(matrix, 2),
        "coordinate_float64_bits_by_column" => _stageb_matrix_bits(matrix),
        "dimension" => size(matrix, 1),
    )
    digest = bytes2hex(sha256(codeunits(canonical_json(payload))))
    return merge(payload, Dict("matrix_sha256" => digest))
end

function _stageb_write_exclusive(path, document; mode=0o600)
    ispath(path) && error("refusing to overwrite one-shot artifact: $path")
    mkpath(dirname(path))
    io = Base.Filesystem.open(
        path,
        Base.JL_O_WRONLY | Base.JL_O_CREAT | Base.JL_O_EXCL,
        mode,
    )
    try
        write(io, canonical_json(document), '\n')
    finally
        close(io)
    end
    return sha256_file(path)
end

function _stageb_validate_preregistration(path, freeze_sha)
    committed(path, "Stage-B T0 preregistration")
    authority = materialization_preflight(repo_path(
        "research/experiments/EXP-DISC-001/local-champion-freeze-record.json",
    ))
    authority.freeze_sha256 == freeze_sha || error("local freeze authority drifted")
    document = StageBT0Inputs._validate_stageb_t0_registration(path, authority)
    get(document, "nonpromotional_t0", false) === true ||
        error("Stage-B T0 must remain nonpromotional")
    return document
end

function _stageb_load_inputs(path; artifacts=true)
    committed(path, "Stage-B T0 input manifest")
    document = json_document(path, "Stage-B T0 input manifest")
    get(document, "schema_version", nothing) == "geotarget.discovery-stageb-t0-input/v1" ||
        error("Stage-B T0 input schema drifted")
    get(document, "experiment_id", nothing) == "EXP-DISC-001" || error("experiment drifted")
    get(document, "stage", nothing) == "stage-b-weak-geometry-t0" &&
        get(document, "partition", nothing) == "development" ||
        error("input crossed the Stage-B T0 development boundary")
    get(document, "nonpromotional_t0", false) === true ||
        error("Stage-B T0 cannot promote an algorithm")
    get(document, "lab_confirmation_512_768", true) === false ||
        error("Stage-B T0 cannot claim 512/768 confirmation")
    get(document, "case_count", nothing) == StageBT0Inputs.STAGEB_T0_CASE_COUNT == 8 ||
        error("Stage-B T0 case count drifted")
    get(document, "proposal_count", nothing) == 8 || error("proposal count drifted")
    get(document, "method", nothing) == T0O_METHODS[1] || error("source method drifted")
    get(document, "replicate_count", nothing) == 1 || error("replicate count drifted")
    parse(UInt64, String(get(document, "root_seed", ""))) ==
        StageBT0Inputs.STAGEB_T0_ROOT_SEED || error("root seed drifted")
    get(document, "seed_namespace", nothing) == StageBT0Inputs.STAGEB_T0_SEED_NAMESPACE ||
        error("source seed namespace drifted")
    prefixes = get(document, "prefixes", nothing)
    prefixes isa AbstractDict && get(prefixes, "initial", nothing) == [1, 64] &&
        get(prefixes, "continuation", nothing) == [65, 128] &&
        get(prefixes, "maximum", nothing) == 128 || error("source prefix contract drifted")

    source_binding = document["source_manifest"]
    source_path = repo_path(source_binding["path"])
    committed(source_path, "Stage-B T0 source manifest")
    sha256_text(source_binding["sha256"]) &&
        sha256_file(source_path) == source_binding["sha256"] ||
        error("source manifest hash drifted")

    freeze_binding = document["local_freeze"]
    freeze_path = repo_path(freeze_binding["path"])
    committed(freeze_path, "local freeze")
    freeze_sha = String(freeze_binding["sha256"])
    sha256_text(freeze_sha) && sha256_file(freeze_path) == freeze_sha ||
        error("local freeze hash drifted")
    freeze = json_document(freeze_path, "local freeze")

    prereg_binding = document["preregistration"]
    prereg_path = repo_path(prereg_binding["path"])
    sha256_text(prereg_binding["sha256"]) &&
        sha256_file(prereg_path) == prereg_binding["sha256"] ||
        error("Stage-B T0 preregistration hash drifted")
    _stageb_validate_preregistration(prereg_path, freeze_sha)

    weak = document["weak_geometry"]
    for key in ("source", "test")
        binding = weak[key]
        dependency = repo_path(binding["path"])
        committed(dependency, "Stage-B weak-geometry $key")
        sha256_text(binding["sha256"]) && sha256_file(dependency) == binding["sha256"] ||
            error("weak-geometry $key hash drifted")
    end

    problems = StageBT0Inputs.stageb_t0_problems()
    cases = document["cases"]
    length(cases) == length(problems) == 8 || error("Stage-B T0 case list drifted")
    loaded = Vector{Any}(undef, 8)
    for (case_index, problem) in enumerate(problems)
        case = cases[case_index]
        recipe = StageBT0Inputs.STAGEB_T0_RECIPE[case_index]
        get(case, "case_index", nothing) == case_index &&
            get(case, "formal_case_id", nothing) == recipe.formal_case_id &&
            get(case, "instance_id", nothing) == problem.instance_id &&
            get(case, "family_id", nothing) == problem.family_id ||
            error("case identity drifted at $case_index")
        get(case, "dimension", nothing) == problem.dimension &&
            get(case, "residual_dimension", nothing) == problem.residual_dimension &&
            get(case, "configuration_count", nothing) == size(problem.gold_configurations, 2) &&
            get(case, "target_count", nothing) == length(problem.gold_targets) ||
            error("case dimensions or assessor counts drifted at $case_index")
        source = case["source"]
        get(source, "path", nothing) == recipe.source &&
            get(source, "index", nothing) == recipe.source_index &&
            get(source, "replay_checksum", nothing) == replay_checksum(problem) ||
            error("case source replay drifted at $case_index")
        proposal = case["proposal"]
        get(proposal, "method", nothing) == T0O_METHODS[1] &&
            get(proposal, "replicate", nothing) == 1 &&
            get(proposal, "initial_prefix_columns", nothing) == [1, 64] &&
            get(proposal, "continuation_columns", nothing) == [65, 128] &&
            get(proposal, "truth_free_metadata", false) === true ||
            error("case proposal contract drifted at $case_index")
        expected_seed = derive_seed(
            StageBT0Inputs.STAGEB_T0_ROOT_SEED,
            D0_IID_ALL,
            case_index,
            1,
            StageBT0Inputs.STAGEB_T0_SEED_NAMESPACE,
        )
        parse(UInt64, String(proposal["replicate_seed"])) == expected_seed ||
            error("case proposal seed drifted at $case_index")
        if artifacts
            artifact_path = repo_path(proposal["path"])
            sha256_text(proposal["file_sha256"]) &&
                sha256_file(artifact_path) == proposal["file_sha256"] ||
                error("proposal file hash drifted at $case_index")
            artifact = read_matrix_artifact(artifact_path)
            StageBT0Inputs._assert_truth_free_artifact(artifact)
            artifact.method == D0_IID_ALL && artifact_sha256(artifact) == proposal["artifact_sha256"] ||
                error("proposal artifact binding drifted at $case_index")
            artifact.replicate_seed == expected_seed && all(==(:iid), artifact.lane_schedule) ||
                error("proposal seed or IID lane drifted at $case_index")
            static_prefix_audit(artifact).valid || error("proposal prefix audit failed")
            StageBT0Inputs._column_slice_sha256(artifact, 1:64) ==
                proposal["initial_prefix_sha256"] || error("initial prefix hash drifted")
            StageBT0Inputs._column_slice_sha256(artifact, 65:128) ==
                proposal["continuation_sha256"] || error("continuation hash drifted")
            size(artifact.coordinates) == (problem.dimension, 128) ||
                error("proposal shape drifted")
            loaded[case_index] = (artifact=artifact, manifest=proposal)
        else
            loaded[case_index] = (artifact=nothing, manifest=proposal)
        end
    end
    get(document, "target_count", nothing) ==
        sum(length(problem.gold_targets) for problem in problems) ||
        error("Stage-B T0 target total drifted")
    return (document, sha256=sha256_file(path), problems, loaded, freeze,
        prereg=(prereg_path, prereg_binding["sha256"]))
end

function _stageb_authorize(path, input_path, input_sha, prereg)
    committed(path, "Stage-B T0 outcome authorization")
    auth = json_document(path, "Stage-B T0 outcome authorization")
    get(auth, "schema_version", nothing) ==
        "geotarget.discovery-stageb-t0-outcome-authorization/v1" &&
        get(auth, "outcome_execution_authorized", false) === true ||
        error("Stage-B T0 outcomes are not authorized")
    get(auth, "nonpromotional_t0", false) === true || error("authorization scope drifted")
    repo_path(auth["input_manifest"]["path"]) == abspath(input_path) &&
        auth["input_manifest"]["sha256"] == input_sha || error("authorized input drifted")
    repo_path(auth["preregistration"]["path"]) == prereg[1] &&
        auth["preregistration"]["sha256"] == prereg[2] ||
        error("authorized preregistration drifted")
    committed(STAGEB_RUNNER, "Stage-B T0 outcome runner")
    committed(STAGEB_AGGREGATOR, "Stage-B T0 aggregator")
    auth["runner_source_sha256"] == sha256_file(STAGEB_RUNNER) ||
        error("authorized runner drifted")
    auth["aggregator_source_sha256"] == sha256_file(STAGEB_AGGREGATOR) ||
        error("authorized aggregator drifted")
    dependencies = get(auth, "dependency_source_sha256", nothing)
    expected = Dict(
        repo_relative(joinpath(STAGEB_ROOT, "run_stagea_outcomes.jl")) =>
            sha256_file(joinpath(STAGEB_ROOT, "run_stagea_outcomes.jl")),
        repo_relative(joinpath(STAGEB_ROOT, "src", "stageb_t0_inputs.jl")) =>
            sha256_file(joinpath(STAGEB_ROOT, "src", "stageb_t0_inputs.jl")),
        repo_relative(joinpath(STAGEB_ROOT, "src", "weak_geometry.jl")) =>
            sha256_file(joinpath(STAGEB_ROOT, "src", "weak_geometry.jl")),
    )
    dependencies isa AbstractDict && all(
        get(dependencies, relative, nothing) == digest for (relative, digest) in expected
    ) || error("authorized Stage-B dependency drifted")
    return (document=auth, sha256=sha256_file(path))
end

function _stageb_execution_host(case_index, cpu)
    1 <= case_index <= 8 || error("case index must lie in 1:8")
    expected = case_index - 1
    0 <= cpu <= 7 && cpu == expected || error("Stage-B case/CPU assignment drifted")
    get(ENV, "GEOTARGET_CASE_PROCESS_LIMIT", "unset") == "8" ||
        error("GEOTARGET_CASE_PROCESS_LIMIT=8 is required")
    matched = match(r"(?m)^Cpus_allowed_list:\s*(.+)$", read("/proc/self/status", String))
    matched !== nothing || error("cannot inspect CPU affinity")
    allowed = strip(matched.captures[1])
    allowed == string(cpu) && ccall(:sched_getcpu, Cint, ()) == cpu ||
        error("process must be pinned to CPU $cpu")
    return Dict(
        "assigned_cpu" => cpu,
        "case_process_limit" => 8,
        "cpus_allowed_list" => allowed,
        "solver_worker_count" => 1,
    )
end

function _stageb_acquire_cpu(cpu)
    io = open("/tmp/geotarget-exp-disc-001-stageb-t0-cpu-$cpu.lock", "w")
    ccall(:flock, Cint, (Cint, Cint), fd(io), 2 | 4) == 0 ||
        (close(io); error("CPU $cpu already has a Stage-B T0 case process"))
    return io
end

mutable struct _StageBEndpointFIFO
    invocations::Int
    endpoints::Vector{NamedTuple}
end

_StageBEndpointFIFO() = _StageBEndpointFIFO(0, NamedTuple[])

function _stageb_capture_variant(base::SolverVariant, fifo::_StageBEndpointFIFO)
    runner = function (case, start)
        fifo.invocations += 1
        outcome = base.run(case, start)
        outcome isa SolverAttemptOutcome || return outcome
        if outcome.endpoint !== nothing
            push!(fifo.endpoints, (;
                source_index=fifo.invocations,
                generation=0,
                endpoint=Tuple(outcome.endpoint),
            ))
        end
        return outcome
    end
    return SolverVariant(
        "STAGEB-T0-SOURCE-CAPTURE-E4",
        runner;
        configuration=(;
            base=base.name,
            capture="endpoint-before-scorer-fifo",
            capture_uses_reported_acceptance=false,
            generation=0,
        ),
    )
end

function _stageb_attempts(run, expected_starts)
    attempts = collect(run.attempts)
    length(attempts) == size(expected_starts, 2) || error("attempt count drifted")
    for (index, attempt) in enumerate(attempts)
        reinterpret(UInt64, collect(attempt.start)) ==
            reinterpret(UInt64, expected_starts[:, index]) ||
            error("attempt start bits drifted at ordinal $index")
    end
    return attempts, solver_experiment_document(run)["attempts"]
end

function _stageb_terminal(attempts, cap)
    return Dict{String,Any}(
        "attempt_count" => length(attempts),
        "callback_work" => sum(attempt.evaluations for attempt in attempts),
        "evaluation_count_mismatches" => count(
            attempt -> attempt.evaluation_count_mismatch,
            attempts,
        ),
        "exceptions" => count(attempt -> attempt.exception !== nothing, attempts),
        "runner_budget_exhausted" => count(attempt -> attempt.budget_exhausted, attempts),
        "callback_cap_violations" => count(
            attempt -> attempt.evaluations > cap || attempt.reported_evaluations > cap,
            attempts,
        ),
    )
end

function _stageb_source_phase(problem, artifact, base_variant)
    run_problem = StageBT0Inputs.stageb_t0_problem_with_proposals(
        problem,
        artifact.coordinates,
    )
    fifo = _StageBEndpointFIFO()
    capture = _stageb_capture_variant(base_variant, fifo)
    run = run_solver_experiment(
        [run_problem],
        [capture];
        prefixes=(STAGEB_SOURCE_PREFIX,),
        evaluation_limit=STAGEB_LOCAL_CAP,
    )
    fifo.invocations == STAGEB_SOURCE_PREFIX || error("source invocation count drifted")
    attempts, serialized = _stageb_attempts(
        run,
        Matrix{Float64}(artifact.coordinates[:, 1:64]),
    )
    return (run_problem, fifo, attempts, serialized,
        terminal=_stageb_terminal(attempts, STAGEB_LOCAL_CAP))
end

function _stageb_weak_evaluator(case::SolverExperimentCase)
    lower = Float64[case.lower_bounds...]
    upper = Float64[case.upper_bounds...]
    midpoint = lower ./ 2 .+ upper ./ 2
    half_range = upper ./ 2 .- lower ./ 2
    return function (point::Vector{Float64})
        evaluation = evaluate_case(case, point)
        normalized = (point .- midpoint) ./ half_range
        open_margin = minimum(1 .- abs.(normalized))
        guards = collect(evaluation.public_guards)
        guard_tokens = UInt64[guard.token for guard in guards]
        unique_tokens = allunique(guard_tokens)
        guard_identity = Tuple(sort(
            [(guard.token, guard.strict) for guard in guards];
            by=first,
        ))
        guard_values = Float64[
            guard.margin / guard.scale for guard in guards if
            isfinite(guard.scale) && guard.scale > 0
        ]
        guard_contract = length(guards) == case.public_guard_count &&
            length(guard_values) == length(guards) && unique_tokens
        guard_margin = isempty(guard_values) ? 1.0 : minimum(guard_values)
        branch_contract = !case.has_branch_token || evaluation.branch_token !== nothing
        residual = length(evaluation.residuals) == case.residual_dimension ?
            Float64[
                evaluation.residuals[index] / case.residual_scales[index] for
                index in 1:case.residual_dimension
            ] : Float64[]
        valid = length(point) == case.dimension && all(isfinite, point) &&
            all(isfinite, residual) && evaluation.finite && evaluation.semantics_valid &&
            all(isfinite, normalized) && isfinite(open_margin) && open_margin > 0 &&
            guard_contract && isfinite(guard_margin) && guard_margin > 0 && branch_contract
        return WeakPointEvaluation(
            residual;
            branch_identity=(evaluation.branch_token === nothing ?
                (:branch_absent,) : (:branch_token, evaluation.branch_token)),
            guard_identity=guard_identity,
            domain_identity=(:public_finite_open_box_v1, case.dimension),
            branch_margin=1.0,
            guard_margin,
            domain_margin=open_margin,
            valid,
        )
    end
end

function _stageb_evidence_document(evidence)
    evidence === nothing && return nothing
    gap = evidence.gap
    return Dict{String,Any}(
        "coarse_singular_values" => gap.coarse_singular_values,
        "fine_singular_values" => gap.fine_singular_values,
        "jacobian_disagreement" => evidence.jacobian_disagreement,
        "largest_weak" => gap.largest_weak,
        "projector_distance" => evidence.projector_distance,
        "raw_cross_gap" => gap.raw_cross_gap,
        "rounding_envelope" => evidence.rounding_envelope,
        "smallest_strong" => gap.smallest_strong,
        "strong_dimension" => gap.strong_dimension,
        "weak_dimension" => gap.weak_dimension,
        "weak_strong_ratio" => gap.weak_strong_ratio,
        "eta" => evidence.eta,
    )
end

function _stageb_quartet_document(quartet, parent_source_index, global_index, anchor)
    return Dict{String,Any}(
        "anchor_float64_bits" => _stageb_float_bits.(Float64[anchor...]),
        "direction_draw" => quartet.direction_draw,
        "global_comparison_index" => global_index,
        "local_comparison_index" => quartet.comparison_index,
        "normalized_float64_bits_by_column" => _stageb_matrix_bits(
            quartet.normalized_points,
        ),
        "parent_generation" => 0,
        "parent_source_index" => parent_source_index,
        "physical_float64_bits_by_column" => _stageb_matrix_bits(quartet.physical_points),
        "radius" => quartet.radius,
        "isotropic_direction_float64_bits" =>
            _stageb_float_bits.(quartet.isotropic_direction),
        "weak_direction_float64_bits" => _stageb_float_bits.(quartet.weak_direction),
    )
end

function _stageb_geometry_variant(fifo, case_index, records, quartets)
    runner = function (case, _start)
        observer = _stageb_weak_evaluator(case)
        reported_callbacks = 0
        for captured in fifo.endpoints
            captured.generation == 0 || error("recursive geometry endpoint entered FIFO")
            remaining = WEAK_MAX_COMPARISONS - length(quartets)
            remaining >= 0 || error("global geometry quartet cap drifted")
            seed = derive_seed(
                StageBT0Inputs.STAGEB_T0_ROOT_SEED,
                D0_IID_ALL,
                case_index,
                captured.source_index,
                STAGEB_GEOMETRY_NAMESPACE,
            )
            result = weak_geometry_plan(
                observer,
                collect(Float64, captured.endpoint),
                collect(Float64, case.lower_bounds),
                collect(Float64, case.upper_bounds);
                seed,
                derived_from_probe=false,
                maximum_comparisons=remaining,
            )
            reported_callbacks += result.callback_count
            first_global = length(quartets) + 1
            append!(quartets, ((;
                quartet,
                parent_source_index=captured.source_index,
                global_comparison_index=first_global + offset - 1,
            ) for (offset, quartet) in enumerate(result.quartets)))
            push!(records, Dict{String,Any}(
                "attempted_comparisons" => result.attempted_comparisons,
                "callback_count" => result.callback_count,
                "evidence" => _stageb_evidence_document(result.evidence),
                "generation" => captured.generation,
                "maximum_comparisons" => remaining,
                "quartet_count" => length(result.quartets),
                "reason" => String(result.reason),
                "rejected_comparisons" => result.rejected_comparisons,
                "seed" => string(seed),
                "source_index" => captured.source_index,
                "status" => String(result.status),
            ))
        end
        length(quartets) <= WEAK_MAX_COMPARISONS || error("global quartet cap exceeded")
        return SolverAttemptOutcome(
            nothing;
            status="STAGEB_GEOMETRY_ONLY",
            reported_converged=false,
            reported_accepted=false,
            evaluations=reported_callbacks,
            iterations=length(fifo.endpoints),
            diagnostic="truth-blind geometry; no answer endpoint",
        )
    end
    return SolverVariant(
        "STAGEB-T0-GEOMETRY-ONLY",
        runner;
        configuration=(;
            answer_authority=false,
            callback_cap=STAGEB_GEOMETRY_CAP,
            generation=0,
            global_maximum_comparisons=WEAK_MAX_COMPARISONS,
            recursive_emission=false,
        ),
    )
end

function _stageb_geometry_phase(run_problem, fifo, case_index, dummy_start)
    records = Dict{String,Any}[]
    quartets = NamedTuple[]
    variant = _stageb_geometry_variant(fifo, case_index, records, quartets)
    run = run_solver_experiment(
        [run_problem],
        [variant];
        prefixes=(1,),
        evaluation_limit=STAGEB_GEOMETRY_CAP,
    )
    attempts, serialized = _stageb_attempts(run, reshape(dummy_start, :, 1))
    length(attempts) == 1 || error("geometry must use exactly one opaque attempt")
    attempt = only(attempts)
    attempt.exception === nothing && attempt.status == "STAGEB_GEOMETRY_ONLY" ||
        error("geometry-only attempt failed")
    attempt.endpoint === nothing && !attempt.assessor_qualified &&
        !attempt.reported_accepted || error("geometry outcome entered the answer set")
    attempt.evaluation_count_mismatch && error("geometry callback accounting mismatch")
    attempt.evaluations <= STAGEB_GEOMETRY_CAP && !attempt.budget_exhausted ||
        error("geometry callback cap exhausted")
    length(records) == length(fifo.endpoints) || error("FIFO anchor scan was incomplete")
    return (attempt, serialized=only(serialized), records, quartets)
end

function _stageb_arm_matrices(artifact, quartets)
    continuation = Matrix{Float64}(artifact.coordinates[:, 65:128])
    isotropic = copy(continuation)
    weak = copy(continuation)
    schedule = Dict{String,Any}[]
    slots = StageBWeakGeometry._launch_schedule(length(quartets))
    length(slots) == STAGEB_ARM_COLUMNS || error("launch schedule length drifted")
    for launch in slots
        if launch.lane === :geometry
            entry = quartets[launch.comparison_index]
            quartet = entry.quartet
            weak[:, launch.slot] .= quartet.physical_points[:, launch.point_ordinal]
            isotropic[:, launch.slot] .=
                quartet.physical_points[:, launch.point_ordinal + 2]
            push!(schedule, Dict{String,Any}(
                "derived_from_probe" => true,
                "generation" => 1,
                "global_comparison_index" => launch.comparison_index,
                "lane" => "GEOMETRY",
                "local_comparison_index" => quartet.comparison_index,
                "parent_generation" => 0,
                "parent_source_index" => entry.parent_source_index,
                "point_ordinal" => launch.point_ordinal,
                "radius" => quartet.radius,
                "sign" => launch.sign,
                "slot" => launch.slot,
                "source_column" => nothing,
            ))
        else
            expected_lane = mod(launch.slot - 1, 4) == 0 ? :iid : :continuation
            launch.lane === expected_lane || error("global IID/continuation schedule drifted")
            push!(schedule, Dict{String,Any}(
                "derived_from_probe" => false,
                "generation" => 0,
                "global_comparison_index" => 0,
                "lane" => launch.lane === :iid ? "IID" : "CONTINUATION",
                "local_comparison_index" => 0,
                "parent_generation" => nothing,
                "parent_source_index" => nothing,
                "point_ordinal" => 0,
                "radius" => nothing,
                "sign" => 0,
                "slot" => launch.slot,
                "source_column" => 64 + launch.slot,
            ))
        end
    end
    all(entry["lane"] == "IID" for entry in schedule[1:4:end]) ||
        error("IID bounded-gap lane drifted")
    return Dict(
        "CONTINUATION" => continuation,
        "ISOTROPIC" => isotropic,
        "WEAK" => weak,
    ), schedule
end

function _stageb_prearm_document(input_sha, prereg, proposal, artifact, problem, fifo,
    geometry, matrices, schedule)
    arms = Any[]
    for name in STAGEB_ARMS
        entry = _stageb_matrix_document(matrices[name])
        entry["name"] = name
        push!(arms, entry)
    end
    anchors = Dict(
        captured.source_index => captured.endpoint for captured in fifo.endpoints
    )
    plan_quartets = Any[
        _stageb_quartet_document(
            entry.quartet,
            entry.parent_source_index,
            entry.global_comparison_index,
            anchors[entry.parent_source_index],
        ) for entry in geometry.quartets
    ]
    schedule_sha = bytes2hex(sha256(codeunits(canonical_json(schedule))))
    provenance_sha = bytes2hex(sha256(codeunits(canonical_json(plan_quartets))))
    lower = reshape(Float64[problem.lower_bounds...], :, 1)
    upper = reshape(Float64[problem.upper_bounds...], :, 1)
    return Dict{String,Any}(
        "arm_matrices" => arms,
        "arm_order" => collect(STAGEB_ARMS),
        "bounds" => Dict(
            "lower_float64_bits" => first(_stageb_matrix_bits(lower)),
            "upper_float64_bits" => first(_stageb_matrix_bits(upper)),
        ),
        "column_count" => STAGEB_ARM_COLUMNS,
        "dimension" => problem.dimension,
        "experiment_id" => "EXP-DISC-001",
        "geometry" => Dict(
            "anchor_count" => length(fifo.endpoints),
            "callback_count" => geometry.attempt.evaluations,
            "generation_contract" => "source-0-to-probe-1-no-recursion",
            "quartet_count" => length(geometry.quartets),
            "quartet_provenance_sha256" => provenance_sha,
            "quartets" => plan_quartets,
        ),
        "input_manifest_sha256" => input_sha,
        "preregistration" => Dict(
            "path" => repo_relative(prereg[1]),
            "sha256" => prereg[2],
        ),
        "schedule" => schedule,
        "schedule_sha256" => schedule_sha,
        "schema_version" => "geotarget.discovery-stageb-t0-prearm/v1",
        "source_artifact" => Dict(
            "artifact_sha256" => artifact.sha256,
            "continuation_sha256" => proposal["continuation_sha256"],
            "file_sha256" => proposal["file_sha256"],
            "path" => proposal["path"],
        ),
        "stage" => "stage-b-t0",
        "truth_free" => true,
    )
end

function _stageb_arm_phase(problem, matrix, base_variant)
    padded = hcat(matrix, matrix)
    run_problem = StageBT0Inputs.stageb_t0_problem_with_proposals(problem, padded)
    run = run_solver_experiment(
        [run_problem],
        [base_variant];
        prefixes=(STAGEB_ARM_COLUMNS,),
        evaluation_limit=STAGEB_LOCAL_CAP,
    )
    attempts, serialized = _stageb_attempts(run, matrix)
    return (attempts, serialized, terminal=_stageb_terminal(attempts, STAGEB_LOCAL_CAP))
end

function _stageb_case_manifest(case)
    return Dict{String,Any}(
        String(key) => value for (key, value) in case if String(key) != "proposal"
    )
end

function _stageb_preflight(input, case_index)
    project, threads, bundle = active_project(), thread_contract(),
        _stageb_load_inputs(input)
    indices = case_index === nothing ? collect(1:8) : [case_index]
    all(index -> 1 <= index <= 8, indices) || error("case index must lie in 1:8")
    variant = local_variant(bundle.freeze)
    return Dict{String,Any}(
        "active_project" => project,
        "arm_order" => collect(STAGEB_ARMS),
        "case_indices" => indices,
        "geometry_callback_cap" => STAGEB_GEOMETRY_CAP,
        "input_manifest_sha256" => bundle.sha256,
        "lab_confirmation_512_768" => false,
        "local_callback_cap" => STAGEB_LOCAL_CAP,
        "local_policy" => variant.name,
        "nonpromotional_t0" => true,
        "outcomes_executed" => false,
        "schema_version" => "geotarget.discovery-stageb-t0-preflight/v1",
        "thread_contract" => threads,
    )
end

function _stageb_execute(input, auth_path, output, prearm_output, case_index, cpu)
    project, threads = active_project(), thread_contract()
    isempty(strip(read(`git -C $STAGEB_REPO status --porcelain`, String))) ||
        error("clean tree required")
    ispath(output) && error("refusing to overwrite outcome")
    ispath(prearm_output) && error("refusing to overwrite pre-arm artifact")
    abspath(output) == abspath(prearm_output) && error("outcome and pre-arm paths must differ")
    header = json_document(input, "Stage-B T0 input manifest")
    prereg = (repo_path(header["preregistration"]["path"]),
        header["preregistration"]["sha256"])
    auth = _stageb_authorize(auth_path, input, sha256_file(input), prereg)
    host, slot = _stageb_execution_host(case_index, cpu), _stageb_acquire_cpu(cpu)
    try
        bundle = _stageb_load_inputs(input)
        problem = bundle.problems[case_index]
        binding = bundle.loaded[case_index]
        base_variant = local_variant(bundle.freeze)

        source = _stageb_source_phase(problem, binding.artifact, base_variant)
        geometry = _stageb_geometry_phase(
            source.run_problem,
            source.fifo,
            case_index,
            Vector{Float64}(binding.artifact.coordinates[:, 1]),
        )
        matrices, schedule = _stageb_arm_matrices(binding.artifact, geometry.quartets)
        prearm = _stageb_prearm_document(
            bundle.sha256,
            bundle.prereg,
            binding.manifest,
            binding.artifact,
            problem,
            source.fifo,
            geometry,
            matrices,
            schedule,
        )
        prearm_sha = _stageb_write_exclusive(prearm_output, prearm)

        arms = Dict{String,Any}[]
        for name in STAGEB_ARMS
            phase = _stageb_arm_phase(problem, matrices[name], base_variant)
            matrix_sha = _stageb_matrix_document(matrices[name])["matrix_sha256"]
            push!(arms, Dict{String,Any}(
                "attempts" => phase.serialized,
                "matrix_sha256" => matrix_sha,
                "name" => name,
                "terminal" => phase.terminal,
            ))
        end

        reason_counts = Dict{String,Int}()
        for record in geometry.records
            reason = record["reason"]
            reason_counts[reason] = get(reason_counts, reason, 0) + 1
        end
        source_callbacks = source.terminal["callback_work"]
        geometry_callbacks = geometry.attempt.evaluations
        geometry_charge = Dict(
            "CONTINUATION" => 0,
            "ISOTROPIC" => geometry_callbacks,
            "WEAK" => geometry_callbacks,
        )
        work_ledger = Dict{String,Any}(
            "geometry_observed_callbacks" => geometry.attempt.evaluations,
            "geometry_reported_callbacks" => geometry.attempt.reported_evaluations,
            "geometry_charge_by_arm" => geometry_charge,
            "source_common_observed_callbacks" => source_callbacks,
            "charged_total_callback_work_by_arm" => Dict(
                arm["name"] => source_callbacks + geometry_charge[arm["name"]] +
                    arm["terminal"]["callback_work"] for arm in arms
            ),
        )
        document = Dict{String,Any}(
            "arm_order" => collect(STAGEB_ARMS),
            "arms" => arms,
            "authorization" => Dict(
                "path" => repo_relative(auth_path),
                "sha256" => auth.sha256,
            ),
            "case_index" => case_index,
            "case_manifest" => _stageb_case_manifest(bundle.document["cases"][case_index]),
            "experiment_id" => "EXP-DISC-001",
            "geometry" => Dict(
                "anchor_count" => length(source.fifo.endpoints),
                "applicable_anchor_count" => count(
                    record -> record["status"] == "applicable",
                    geometry.records,
                ),
                "attempt" => geometry.serialized,
                "callback_count" => geometry.attempt.evaluations,
                "plans" => geometry.records,
                "quartet_count" => length(geometry.quartets),
                "reasons" => reason_counts,
            ),
            "input_manifest" => Dict(
                "path" => repo_relative(input),
                "sha256" => bundle.sha256,
            ),
            "lab_confirmation_512_768" => false,
            "nonpromotional_t0" => true,
            "prearm" => Dict(
                "path" => repo_relative(prearm_output),
                "quartet_provenance_sha256" =>
                    prearm["geometry"]["quartet_provenance_sha256"],
                "schedule_sha256" => prearm["schedule_sha256"],
                "sha256" => prearm_sha,
            ),
            "preregistration" => Dict(
                "path" => repo_relative(bundle.prereg[1]),
                "sha256" => bundle.prereg[2],
            ),
            "revision" => Dict(
                "git_dirty" => false,
                "git_head" => readchomp(`git -C $STAGEB_REPO rev-parse HEAD`),
            ),
            "schema_version" => "geotarget.discovery-stageb-t0-raw/v1",
            "source" => Dict(
                "attempts" => source.serialized,
                "proposal" => binding.manifest,
                "preregistration_sha256" => bundle.prereg[2],
                "terminal" => source.terminal,
            ),
            "stage" => "stage-b-t0",
            "thread_contract" => merge(threads, host),
            "work_ledger" => work_ledger,
        )
        _stageb_write_exclusive(output, document)
        println("prearm=", prearm_output)
        println("output=", output)
        return document
    finally
        close(slot)
    end
end

function _stageb_self_test()
    active_project(); thread_contract()
    problems = StageBT0Inputs.stageb_t0_problems()
    length(problems) == 8 || error("Stage-B T0 corpus fixture")
    sum(length(problem.gold_targets) for problem in problems) == 16 ||
        error("Stage-B T0 target fixture")
    freeze = json_document(joinpath(STAGEB_ROOT, "local-champion-freeze-record.json"), "freeze")
    local_variant(freeze)
    synthetic = reshape(Float64[0.0, -0.0, 1.0, -1.0], 2, 2)
    decoded = _stageb_matrix_bits(synthetic)
    decoded[1] == ["0000000000000000", "8000000000000000"] ||
        error("Float64 bit fixture drifted")
    fake_artifact = (coordinates=reshape(Float64.(1:256), 2, 128),)
    empty_matrices, empty_schedule = _stageb_arm_matrices(fake_artifact, NamedTuple[])
    reference_bits = reinterpret(UInt64, vec(empty_matrices["CONTINUATION"]))
    all(
        reinterpret(UInt64, vec(empty_matrices[name])) == reference_bits for
        name in STAGEB_ARMS
    ) || error("all-inapplicable continuation fallback drifted")
    all(empty_schedule[index]["lane"] == "IID" for index in 1:4:64) ||
        error("IID cadence fixture drifted")
    return Dict{String,Any}(
        "arm_order" => collect(STAGEB_ARMS),
        "case_count" => 8,
        "geometry_callback_cap" => STAGEB_GEOMETRY_CAP,
        "local_callback_cap" => STAGEB_LOCAL_CAP,
        "outcomes_executed" => false,
        "schema_version" => "geotarget.discovery-stageb-t0-runner-self-test/v1",
        "solver_invocations" => 0,
    )
end

function _stageb_parse_args(args)
    mode = :preflight
    input = STAGEB_INPUT
    auth = STAGEB_AUTH
    output = nothing
    prearm = nothing
    case_index = cpu = nothing
    for arg in args
        arg == "--execute" ? (mode = :execute) :
        arg == "--self-test" ? (mode = :self_test) :
        arg == "--preflight-only" ? (mode = :preflight) :
        arg == "--help" ? (return nothing) :
        startswith(arg, "--input-manifest=") ?
            (input = abspath(split(arg, '='; limit=2)[2])) :
        startswith(arg, "--authorization=") ?
            (auth = abspath(split(arg, '='; limit=2)[2])) :
        startswith(arg, "--output=") ?
            (output = abspath(split(arg, '='; limit=2)[2])) :
        startswith(arg, "--prearm-output=") ?
            (prearm = abspath(split(arg, '='; limit=2)[2])) :
        startswith(arg, "--case-index=") ?
            (case_index = parse(Int, split(arg, '=')[2])) :
        startswith(arg, "--assigned-cpu=") ?
            (cpu = parse(Int, split(arg, '=')[2])) :
        error("unknown option: $arg")
    end
    if case_index !== nothing && prearm === nothing
        prearm = joinpath(
            STAGEB_PREARM_ROOT,
            "prearm-case-$(lpad(case_index, 2, '0')).json",
        )
    end
    if case_index !== nothing && output === nothing
        output = joinpath(
            STAGEB_REPO,
            "benchmarks",
            "results",
            "raw",
            "exp-disc-001-stageb-t0-case-$(lpad(case_index, 2, '0')).json",
        )
    end
    return (; mode, input, auth, output, prearm, case_index, cpu)
end

function stageb_t0_main(args=ARGS)
    options = _stageb_parse_args(args)
    options === nothing && return print(
        "Use --preflight-only, --self-test, or --execute --case-index=N --assigned-cpu=N\n",
    )
    if options.mode == :execute
        options.case_index === nothing && error("--case-index is required")
        options.cpu === nothing && error("--assigned-cpu is required")
        options.prearm === nothing && error("--prearm-output is required")
        options.output === nothing && error("--output is required")
    end
    result = options.mode == :self_test ? _stageb_self_test() :
        options.mode == :preflight ? _stageb_preflight(options.input, options.case_index) :
        _stageb_execute(
            options.input,
            options.auth,
            options.output,
            options.prearm,
            options.case_index,
            options.cpu,
        )
    options.mode == :execute || println(canonical_json(result))
    return result
end

abspath(PROGRAM_FILE) == abspath(@__FILE__) && stageb_t0_main()
