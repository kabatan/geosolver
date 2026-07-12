using SHA

const EXP_LOCAL_014_ROOT = @__DIR__
const EXP_LOCAL_014_REPOSITORY_ROOT = normpath(joinpath(@__DIR__, "..", "..", ".."))
const EXP_LOCAL_014_REGISTRATION = joinpath(@__DIR__, "preregistration.json")
const EXP_LOCAL_014_E3_REGISTRATION = joinpath(@__DIR__, "..", "EXP-LOCAL-012", "preregistration.json")
const EXP_LOCAL_014_E4_REGISTRATION = joinpath(@__DIR__, "..", "EXP-LOCAL-013", "preregistration.json")

include(joinpath(@__DIR__, "..", "EXP-LOCAL-010", "run_t2.jl"))
include(joinpath(@__DIR__, "..", "EXP-LOCAL-012", "src", "ExperimentLocal012.jl"))
include(joinpath(@__DIR__, "..", "EXP-LOCAL-013", "src", "ExperimentLocal013.jl"))

const EXP_LOCAL_014_G0_SOURCE_INDICES = (13:18..., 37:42...)
const EXP_LOCAL_014_REQUIRED_FROZEN_PATHS = Set((
    "benchmarks/solver_lab/CoreBaseline.jl",
    "julia/GeoTargetBenchmarks/src/solver_experiment.jl",
    "research/experiments/EXP-LOCAL-002/Manifest.toml",
    "research/experiments/EXP-LOCAL-002/Project.toml",
    "research/experiments/EXP-LOCAL-004/src/T2Corpus.jl",
    "research/experiments/EXP-LOCAL-004/t2-input-manifest.json",
    "research/experiments/EXP-LOCAL-010/aggregate_t0.py",
    "research/experiments/EXP-LOCAL-010/run_t0.jl",
    "research/experiments/EXP-LOCAL-010/run_t2.jl",
    "research/experiments/EXP-LOCAL-010/src/ExperimentLocal010.jl",
    "research/experiments/EXP-LOCAL-010/t2-decision.json",
    "research/experiments/EXP-LOCAL-011/preregistration.json",
    "research/experiments/EXP-LOCAL-012/preregistration.json",
    "research/experiments/EXP-LOCAL-012/src/ExperimentLocal012.jl",
    "research/experiments/EXP-LOCAL-013/preregistration.json",
    "research/experiments/EXP-LOCAL-013/src/ExperimentLocal013.jl",
    "research/experiments/EXP-LOCAL-014/aggregate_wave.py",
    "research/experiments/EXP-LOCAL-014/preoutcome-evidence.json",
    "research/experiments/EXP-LOCAL-014/run_wave.jl",
    "research/experiments/EXP-LOCAL-014/test/runtests.jl",
    "research/experiments/EXP-LOCAL-014/test/test_aggregate_wave.py",
    "research/experiments/EXP-LOCAL-012/test/runtests.jl",
    "research/experiments/EXP-LOCAL-013/test/runtests.jl",
))

_wave_sha256(path) = bytes2hex(sha256(read(path)))

function _wave_registration()
    return JSON3.read(read(EXP_LOCAL_014_REGISTRATION, String), Dict{String,Any})
end

function _validate_wave_hashes(registration)
    frozen = registration["frozen_inputs"]
    Set(String.(keys(frozen))) == EXP_LOCAL_014_REQUIRED_FROZEN_PATHS ||
        error("preregistered frozen path set drifted")
    for (relative, expected) in frozen
        path = joinpath(EXP_LOCAL_014_REPOSITORY_ROOT, split(relative, '/')...)
        _wave_sha256(path) == expected || error("frozen wave input drifted: $relative")
    end
    return true
end

function _validate_predecessor(registration, stage)
    stage == "g0" && return true
    predecessor = get(registration, "predecessor_decision", nothing)
    predecessor isa Dict || error("$stage requires a committed predecessor decision")
    required_stage = stage == "r1" ? "g0" : "r1"
    predecessor["stage"] == required_stage || error("wrong predecessor stage")
    relative = String(predecessor["path"])
    path = joinpath(EXP_LOCAL_014_REPOSITORY_ROOT, split(relative, '/')...)
    isfile(path) || error("predecessor decision is missing")
    _wave_sha256(path) == predecessor["sha256"] || error("predecessor decision hash drifted")
    decision = JSON3.read(read(path, String), Dict{String,Any})
    decision["stage"] == required_stage || error("predecessor decision content drifted")
    decision["authorized_next_stage"] == stage || error("predecessor does not authorize $stage")
    Set(String.(decision["survivors"])) == Set(String.(registration["active_candidates"])) ||
        error("active candidates differ from predecessor decision")
    return true
end

function _wave_authorized(registration, stage)
    registrations = (
        registration,
        JSON3.read(read(EXP_LOCAL_014_E3_REGISTRATION, String), Dict{String,Any}),
        JSON3.read(read(EXP_LOCAL_014_E4_REGISTRATION, String), Dict{String,Any}),
    )
    _validate_predecessor(registration, stage)
    return registration["active_stage"] == stage && all(
        get(document, "outcome_execution_authorized", false) === true for
        document in registrations
    )
end

function _wave_variants(registration)
    e1 = ExperimentLocal010.endpoint_correction_variant(; shadow=false)
    e1_shadow = ExperimentLocal010.endpoint_correction_variant(; shadow=true)
    selected = SolverVariant[
        GeoTargetSolverLab.core_lmqr_control(:prod_tol_120x600),
        e1,
    ]
    for candidate in registration["active_candidates"]
        if candidate == ExperimentLocal012.CANDIDATE_NAME
            push!(selected, ExperimentLocal012.endpoint_correction_variant(; shadow=false))
            push!(selected, ExperimentLocal012.endpoint_correction_variant(; shadow=true))
        elseif candidate == ExperimentLocal013.CANDIDATE_NAME
            push!(
                selected,
                ExperimentLocal013.guard_slack_variant(e1; shadow=false),
                ExperimentLocal013.guard_slack_variant(e1_shadow; shadow=true),
            )
        else
            error("unknown active local candidate: $candidate")
        end
    end
    allunique(variant.name for variant in selected) || error("duplicate wave variant")
    return selected
end

function _wave_stage(stage::String)
    if stage == "g0"
        all_problems, _ = _validate_t2_corpus()
        return (
            problems=all_problems[collect(EXP_LOCAL_014_G0_SOURCE_INDICES)],
            source_indices=collect(EXP_LOCAL_014_G0_SOURCE_INDICES),
            maximum_starts=32,
            suite="g0",
        )
    elseif stage == "r1"
        problems = GeoTargetSolverLab.representative_problems(; start_count=64)
        length(problems) == 9 || error("representative stage must contain nine cases")
        return (
            problems,
            source_indices=collect(1:length(problems)),
            maximum_starts=64,
            suite="r1",
        )
    elseif stage == "t2"
        problems, _ = _validate_t2_corpus()
        return (
            problems,
            source_indices=collect(1:length(problems)),
            maximum_starts=32,
            suite="t2",
        )
    end
    error("stage must be g0, r1, or t2")
end

function wave_preflight_document(stage::String)
    _validate_active_project()
    registration = _wave_registration()
    _validate_wave_hashes(registration)
    string(VERSION) == registration["runtime_versions"]["julia"] ||
        error("Julia version differs from preregistration")
    registration["active_stage"] == stage || error("$stage is not the active preregistered stage")
    spec = _wave_stage(stage)
    variants = _wave_variants(registration)
    expected = registration["stages"][stage]
    length(spec.problems) == Int(expected["case_count"]) || error("stage case count drifted")
    spec.maximum_starts == Int(expected["maximum_starts"]) || error("stage start count drifted")
    last(CALLBACK_THRESHOLDS) == Int(expected["case_callback_stop"]) ||
        error("stage callback stop drifted")
    if stage == "g0"
        spec.source_indices == Int.(expected["source_case_indices"]) ||
            error("G0 source case indices drifted")
        total_targets = sum(length(problem.gold_targets) for problem in spec.problems)
        near_targets = sum(
            length(problem.gold_targets) for problem in spec.problems if
            problem.family_id == "NEAR-RANK-DEFICIENT"
        )
        guard_targets = sum(
            length(problem.gold_targets) for problem in spec.problems if
            problem.family_id == "STRICT-GUARD-BOUNDARY"
        )
        total_targets == Int(expected["target_count"]) || error("G0 target count drifted")
        near_targets == Int(expected["near_rank_target_count"]) ||
            error("G0 NearRank target count drifted")
        guard_targets == Int(expected["strict_guard_target_count"]) ||
            error("G0 StrictGuard target count drifted")
    elseif stage == "r1"
        expected_instances = expected["instances"]
        length(expected_instances) == length(spec.problems) ||
            error("R1 instance manifest count drifted")
        for (index, problem) in enumerate(spec.problems)
            wanted = expected_instances[index]
            observed = _wave_problem_manifest(problem, index, index)
            for field in (
                "family_id",
                "instance_id",
                "replay_checksum",
                "saved_starts_checksum",
                "saved_starts_shape",
                "source_case_index",
            )
                observed[field] == wanted[field] || error("R1 $field drifted at case $index")
            end
            observed["targets"] == Int(wanted["target_count"]) ||
                error("R1 target count drifted at case $index")
        end
        sum(length(problem.gold_targets) for problem in spec.problems) ==
            Int(expected["target_count"]) || error("R1 total target count drifted")
    end
    return Dict{String,Any}(
        "active_project" => relpath(something(Base.active_project()), EXP_LOCAL_014_REPOSITORY_ROOT),
        "active_stage" => stage,
        "authorized" => _wave_authorized(registration, stage),
        "case_count" => length(spec.problems),
        "case_work_stop" => last(CALLBACK_THRESHOLDS),
        "maximum_case_processes" => 16,
        "maximum_starts" => spec.maximum_starts,
        "registration_sha256" => _wave_sha256(EXP_LOCAL_014_REGISTRATION),
        "runtime_versions" => Dict(
            "blas_vendor" => string(BLAS.vendor()),
            "julia" => string(VERSION),
        ),
        "source_case_indices" => spec.source_indices,
        "thread_contract" => _thread_contract(),
        "variant_names" => [variant.name for variant in variants],
    )
end

function _wave_problem_manifest(problem, local_index, source_index)
    return Dict{String,Any}(
        "family_id" => problem.family_id,
        "instance_id" => problem.instance_id,
        "local_case_index" => local_index,
        "replay_checksum" => replay_checksum(problem),
        "saved_starts_checksum" => _artifact_sha(problem, :saved_starts),
        "saved_starts_shape" => collect(size(problem.saved_starts)),
        "source_case_index" => source_index,
        "targets" => length(problem.gold_targets),
    )
end

function _execution_host_contract(assigned_cpu::Integer, case_index::Integer)
    0 <= assigned_cpu <= 15 || error("assigned CPU must be in physical-core set 0..15")
    assigned_cpu == (case_index - 1) % 16 || error("case-to-CPU rotation contract violated")
    get(ENV, "GEOTARGET_CASE_PROCESS_LIMIT", "unset") == "16" ||
        error("GEOTARGET_CASE_PROCESS_LIMIT=16 is required")
    status = read("/proc/self/status", String)
    match_result = match(r"(?m)^Cpus_allowed_list:\s*(.+)$", status)
    match_result === nothing && error("cannot read process CPU affinity")
    allowed = strip(match_result.captures[1])
    allowed == string(assigned_cpu) || error("process must be pinned to CPU $assigned_cpu")
    current = ccall(:sched_getcpu, Cint, ())
    current == assigned_cpu || error("process is not running on assigned CPU")
    return Dict{String,Any}(
        "assigned_cpu" => Int(assigned_cpu),
        "case_process_limit" => 16,
        "cpus_allowed_list" => allowed,
        "solver_worker_count" => 1,
    )
end

function _acquire_cpu_slot(assigned_cpu::Integer)
    path = "/tmp/geotarget-exp-local-014-cpu-$assigned_cpu.lock"
    io = open(path, "w")
    result = ccall(:flock, Cint, (Cint, Cint), fd(io), 2 | 4)
    if result != 0
        close(io)
        error("exclusive case-process slot for CPU $assigned_cpu is already occupied")
    end
    return io
end

function _run_wave_case_locked(
    stage::String,
    case_index::Integer,
    assigned_cpu::Integer,
    host,
)
    revision = _git_revision()
    revision["git_dirty"] && error("wave outcome execution requires a clean committed tree")
    registration = _wave_registration()
    _wave_authorized(registration, stage) || error("wave outcome execution is not authorized")
    preflight = wave_preflight_document(stage)
    spec = _wave_stage(stage)
    1 <= case_index <= length(spec.problems) || error("case index is outside active stage")
    problem = spec.problems[Int(case_index)]
    selected = _wave_variants(registration)
    manifest = _wave_problem_manifest(
        problem, Int(case_index), spec.source_indices[Int(case_index)],
    )
    document = Dict{String,Any}(
        "attempts" => Any[],
        "case_count" => length(spec.problems),
        "case_index" => Int(case_index),
        "environment" => preflight["thread_contract"],
        "experiment_id" => "EXP-LOCAL-014",
        "generated_at_utc" => Dates.format(now(UTC), dateformat"yyyy-mm-ddTHH:MM:SS.sssZ"),
        "authorization" => Dict(
            "active_candidates" => registration["active_candidates"],
            "active_stage" => stage,
            "frozen_inputs" => registration["frozen_inputs"],
            "predecessor_decision" => registration["predecessor_decision"],
            "registration_path" => relpath(
                EXP_LOCAL_014_REGISTRATION, EXP_LOCAL_014_REPOSITORY_ROOT,
            ),
            "registration_sha256" => _wave_sha256(EXP_LOCAL_014_REGISTRATION),
        ),
        "callback_thresholds" => collect(CALLBACK_THRESHOLDS),
        "case_callback_stop" => last(CALLBACK_THRESHOLDS),
        "host_execution" => host,
        "input_manifest" => stage in ("g0", "t2") ? Dict(
            "path" => relpath(T2_INPUT_MANIFEST, EXP_LOCAL_014_REPOSITORY_ROOT),
            "sha256" => registration["frozen_inputs"][
                "research/experiments/EXP-LOCAL-004/t2-input-manifest.json"
            ],
        ) : nothing,
        "locked_validation" => false,
        "maximum_starts" => spec.maximum_starts,
        "partition" => "development",
        "prefix_policy" => "snapshot-after-first-completed-attempt-crossing-threshold",
        "runtime_versions" => preflight["runtime_versions"],
        "problem_manifest" => Any[manifest],
        "revision" => revision,
        "schema" => "geotarget.local-successor-campaign/v1",
        "stage" => stage,
        "terminals" => Any[],
        "threshold_snapshots" => Any[],
        "variant_manifest" => Any[
            Dict(
                "configuration" => Dict(
                    String(key) => value for (key, value) in pairs(variant.configuration)
                ),
                "name" => variant.name,
            ) for variant in selected
        ],
    )
    for variant in selected
        attempts, snapshots, terminal = _run_case(
            variant, problem; maximum_starts=spec.maximum_starts,
        )
        append!(
            document["attempts"],
            (GeoTargetBenchmarks._attempt_document(attempt) for attempt in attempts),
        )
        append!(document["threshold_snapshots"], snapshots)
        push!(document["terminals"], terminal)
    end
    return document
end

function run_wave_case(stage::String, case_index::Integer, assigned_cpu::Integer)
    host = _execution_host_contract(assigned_cpu, case_index)
    slot = _acquire_cpu_slot(assigned_cpu)
    try
        return _run_wave_case_locked(stage, case_index, assigned_cpu, host)
    finally
        close(slot)
    end
end

function run_wave_main(arguments=ARGS)
    execute = "--execute" in arguments
    stage_argument = findfirst(argument -> startswith(argument, "--stage="), arguments)
    stage = stage_argument === nothing ? "g0" : arguments[stage_argument][9:end]
    case_argument = findfirst(argument -> startswith(argument, "--case-index="), arguments)
    case_index = case_argument === nothing ? nothing : tryparse(
        Int, arguments[case_argument][length("--case-index=") + 1:end],
    )
    cpu_argument = findfirst(argument -> startswith(argument, "--assigned-cpu="), arguments)
    assigned_cpu = cpu_argument === nothing ? nothing : tryparse(
        Int, arguments[cpu_argument][length("--assigned-cpu=") + 1:end],
    )
    output_argument = findfirst(argument -> startswith(argument, "--output="), arguments)
    output = output_argument === nothing ? joinpath(
        EXP_LOCAL_014_REPOSITORY_ROOT,
        "benchmarks",
        "results",
        "raw",
        case_index === nothing ?
        "exp-local-014-$stage-preflight.json" :
        "exp-local-014-$stage-case-$(lpad(case_index, 2, '0')).json",
    ) : abspath(arguments[output_argument][length("--output=") + 1:end])
    allowed = argument -> argument == "--execute" || startswith(argument, "--stage=") ||
        startswith(argument, "--case-index=") || startswith(argument, "--assigned-cpu=") ||
        startswith(argument, "--output=")
    all(allowed, arguments) || error("unknown wave runner option")
    if !execute
        println(JSON3.write(wave_preflight_document(stage)))
        return nothing
    end
    case_index !== nothing || error("--case-index is required for outcome execution")
    assigned_cpu !== nothing || error("--assigned-cpu is required for outcome execution")
    document = run_wave_case(stage, case_index, assigned_cpu)
    mkpath(dirname(output))
    write(output, JSON3.write(document), '\n')
    println("output=$output")
    return document
end

if abspath(PROGRAM_FILE) == abspath(@__FILE__())
    run_wave_main()
end
