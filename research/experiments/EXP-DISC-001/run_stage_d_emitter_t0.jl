using Random

include(joinpath(@__DIR__, "run_stagec_t0.jl"))
include(joinpath(@__DIR__, "src", "direct_rect_emitter.jl"))
include(joinpath(@__DIR__, "src", "simplicial_star_emitter.jl"))
include(joinpath(@__DIR__, "src", "ecp_acceptance_emitter.jl"))

const STAGED_ROOT = @__DIR__
const STAGED_REPO = T0O_REPO
const STAGED_RUNNER = @__FILE__
const STAGED_AGGREGATOR = joinpath(STAGED_ROOT, "aggregate_stage_d_emitter_t0.py")
const STAGED_PREREG = joinpath(STAGED_ROOT, "stage-d-emitter-t0-preregistration.json")
const STAGED_RAW_ROOT = joinpath(STAGED_REPO, "benchmarks", "results", "raw")
const STAGED_ROOT_SEED = UInt64(5_278_151_570_976_065_524)
const STAGED_CASE_COUNT = 12
const STAGED_LOCAL_COUNT = 64
const STAGED_INSURANCE_COUNT = 16
const STAGED_EMITTER_COUNT = 48
const STAGED_RAW_DRAW_COUNT = ECPAcceptanceEmitter.RAW_DRAW_CAP
const STAGED_LOCAL_CAP = 600
const STAGED_ARMS = (
    "D0_PRESCORED_64",
    "RECT_ORBIT_BREADTH",
    "DIRECT_RECT_EMIT",
    "SIMPLICIAL_UNGUIDED",
    "SIMPLICIAL_STAR_EMIT",
    "ECP_LB_FULL",
)

function _staged_value(value)
    value === nothing && return nothing
    value isa Enum && return string(value)
    value isa Symbol && return String(value)
    value isa AbstractString && return String(value)
    value isa Number && return value
    value isa Bool && return value
    value isa AbstractDict && return Dict{String,Any}(
        String(key) => _staged_value(child) for (key, child) in value
    )
    value isa AbstractArray && return Any[_staged_value(child) for child in value]
    value isa Tuple && return Any[_staged_value(child) for child in value]
    names = fieldnames(typeof(value))
    isempty(names) && error("unsupported Stage-D diagnostic value $(typeof(value))")
    return Dict{String,Any}(
        String(name) => _staged_value(getfield(value, name)) for name in names
    )
end

function _staged_preregistration(path=STAGED_PREREG)
    committed(path, "Stage-D emitter T0 preregistration")
    document = json_document(path, "Stage-D emitter T0 preregistration")
    get(document, "schema_version", nothing) ==
        "geotarget.discovery-stage-d-emitter-t0-preregistration/v1" ||
        error("Stage-D preregistration schema drifted")
    get(document, "status", nothing) == "preregistered" &&
        get(document, "outcome_execution_authorized", false) === true &&
        get(document, "nonpromotional_t0", false) === true ||
        error("Stage-D outcome scope is not authorized")
    parse(UInt64, String(document["root_seed"])) == STAGED_ROOT_SEED ||
        error("Stage-D root seed drifted")
    Tuple(String.(document["arms"])) == STAGED_ARMS || error("Stage-D arms drifted")
    document["case_count"] == STAGED_CASE_COUNT &&
        document["local_start_count"] == STAGED_LOCAL_COUNT &&
        document["logical_prescreen_callbacks_per_arm"] == STAGED_LOCAL_COUNT ||
        error("Stage-D fixed work contract drifted")
    for (relative, expected) in document["source_sha256"]
        source = repo_path(String(relative))
        committed(source, "Stage-D bound source")
        sha256_file(source) == expected || error("Stage-D source drifted: $relative")
    end
    for (relative, expected) in document["executable_sha256"]
        source = repo_path(String(relative))
        committed(source, "Stage-D executable")
        sha256_file(source) == expected || error("Stage-D executable drifted: $relative")
    end
    freeze = document["local_freeze"]
    freeze_path = repo_path(freeze["path"])
    committed(freeze_path, "local finalist freeze")
    sha256_file(freeze_path) == freeze["sha256"] || error("local finalist freeze drifted")
    upstream = document["upstream_source_manifest"]
    upstream_path = repo_path(String(upstream["path"]))
    committed(upstream_path, "Stage-D upstream source manifest")
    sha256_file(upstream_path) == upstream["sha256"] ||
        error("Stage-D upstream source manifest drifted")
    cases = document["case_manifests"]
    sources = document["case_sources"]
    length(cases) == STAGED_CASE_COUNT == length(sources) ||
        error("Stage-D fixed case binding count drifted")
    for case_index in 1:STAGED_CASE_COUNT
        case = cases[case_index]
        source = sources[case_index]
        case["case_index"] == case_index &&
            case["source_index"] == StageCT0Inputs.STAGEC_T0_SOURCE_INDICES[case_index] &&
            source["index"] == case["source_index"] ||
            error("Stage-D fixed case binding drifted at case $case_index")
    end
    return (; document, path=abspath(path), sha256=sha256_file(path), freeze_path)
end

function _staged_case_manifest(problem)
    return Dict{String,Any}(
        "configuration_count" => size(problem.gold_configurations, 2),
        "dimension" => problem.dimension,
        "family_id" => problem.family_id,
        "instance_id" => problem.instance_id,
        "replay_checksum" => replay_checksum(problem),
        "target_count" => length(problem.gold_targets),
    )
end

function _staged_validate_case_binding(prereg, case_index, problem)
    actual = _staged_case_manifest(problem)
    frozen = prereg.document["case_manifests"][case_index]
    for (field, value) in actual
        get(frozen, field, nothing) == value ||
            error("Stage-D frozen case $case_index field $field drifted")
    end
    return actual
end

function _staged_seed(case_index, namespace)
    return derive_seed(STAGED_ROOT_SEED, D0_IID_ALL, case_index, 1, namespace)
end

function _staged_normalized_random(dimension, seed, columns)
    unit = rand(Random.Xoshiro(seed), Float64, dimension, columns)
    return map(value -> muladd(2.0, value, -1.0), unit)
end

function _staged_matrix_sha(matrix::Matrix{Float64})
    return bytes2hex(sha256(reinterpret(UInt8, vec(matrix))))
end

function _staged_physical(problem, normalized)
    length(normalized) == problem.dimension || error("normalized point dimension drifted")
    point = Vector{Float64}(undef, problem.dimension)
    for index in eachindex(point)
        lower, upper, u = problem.lower_bounds[index], problem.upper_bounds[index], normalized[index]
        midpoint = lower / 2 + upper / 2
        point[index] = u <= 0 ?
            lower + (midpoint - lower) * (u + 1) :
            midpoint + (upper - midpoint) * u
        point[index] = clamp(point[index], lower, upper)
    end
    all(isfinite, point) || error("physical point became nonfinite")
    return point
end

function _staged_safe_observe(problem, point)
    try
        observation = _stagec_observe(problem, Vector{Float64}(point))
        score, _ = StageNextDirectRectEmitter.phi_score(
            StageNextDirectRectEmitter.ScreeningObservation(
                observation.residual; canonical_valid=observation.valid,
            ),
        )
        return (; observation, score, callback_failed=false)
    catch
        observation = (residual=Float64[], score=nothing, branch_token=nothing, valid=false)
        return (; observation, score=1.0, callback_failed=true)
    end
end

function _staged_prescore(problem, points::Matrix{Float64}, kind::AbstractString)
    records = Dict{String,Any}[]
    for slot in axes(points, 2)
        point = Vector{Float64}(points[:, slot])
        result = _staged_safe_observe(problem, point)
        push!(records, Dict{String,Any}(
            "callback_failed" => result.callback_failed,
            "canonical_valid" => result.observation.valid,
            "kind" => String(kind),
            "phi_float64_bits" => _stagec_float_bits(result.score),
            "scaled_residual_float64_bits" => _stagec_vector_bits(result.observation.residual),
            "slot" => slot,
        ))
    end
    return records
end

function _staged_mix(insurance::Matrix{Float64}, emitter::Matrix{Float64},
    insurance_records, emitter_records)
    size(insurance, 2) == STAGED_INSURANCE_COUNT || error("insurance count drifted")
    size(emitter, 2) == STAGED_EMITTER_COUNT || error("emitter count drifted")
    size(insurance, 1) == size(emitter, 1) || error("source dimensions drifted")
    matrix = Matrix{Float64}(undef, size(insurance, 1), STAGED_LOCAL_COUNT)
    schedule = Dict{String,Any}[]
    for block in 1:STAGED_INSURANCE_COUNT
        position = 4block - 3
        matrix[:, position] .= insurance[:, block]
        push!(schedule, merge(deepcopy(insurance_records[block]), Dict(
            "emitter_slot" => nothing,
            "insurance_slot" => block,
            "lane" => "IID_INSURANCE",
            "position" => position,
        )))
        for offset in 1:3
            emitter_slot = 3(block - 1) + offset
            position += 1
            matrix[:, position] .= emitter[:, emitter_slot]
            push!(schedule, merge(deepcopy(emitter_records[emitter_slot]), Dict(
                "emitter_slot" => emitter_slot,
                "insurance_slot" => nothing,
                "lane" => "EMITTER",
                "position" => position,
            )))
        end
    end
    sort!(schedule; by=record -> record["position"])
    all(schedule[4block - 3]["lane"] == "IID_INSURANCE" for block in 1:16) ||
        error("bounded-gap IID schedule drifted")
    return matrix, schedule
end

function _staged_insurance(problem, normalized, arm)
    physical = hcat((_staged_physical(problem, @view normalized[:, slot])
                     for slot in axes(normalized, 2))...)
    return physical, _staged_prescore(problem, physical, "$(arm)_IID_INSURANCE")
end

function _staged_d0(problem, insurance_normalized, candidate_normalized)
    insurance, insurance_records = _staged_insurance(problem, insurance_normalized, STAGED_ARMS[1])
    emitter = hcat((_staged_physical(problem, @view candidate_normalized[:, slot])
                    for slot in 1:STAGED_EMITTER_COUNT)...)
    records = _staged_prescore(problem, emitter, "D0_RAW_PREFIX")
    matrix, schedule = _staged_mix(insurance, emitter, insurance_records, records)
    return (; name=STAGED_ARMS[1], matrix, schedule, generation=Dict{String,Any}(
        "all_prescores_returned" => true,
        "answer_authority" => false,
        "logical_prescreen_callbacks" => 64,
        "physical_prescreen_callbacks" => 64,
        "source" => "FIRST_48_RAW_CANDIDATES",
    ))
end

function _staged_direct(problem, insurance_normalized, fallback_normalized, arm, name)
    calls = Ref(0)
    callback = point -> begin
        calls[] += 1
        observation = _stagec_observe(problem, Vector{Float64}(point))
        return StageNextDirectRectEmitter.ScreeningObservation(
            observation.residual; canonical_valid=observation.valid,
        )
    end
    result = StageNextDirectRectEmitter.emit_points(
        callback,
        collect(Float64, problem.lower_bounds),
        collect(Float64, problem.upper_bounds);
        arm,
    )
    emitter = Matrix{Float64}(undef, problem.dimension, STAGED_EMITTER_COUNT)
    records = Vector{Dict{String,Any}}(undef, STAGED_EMITTER_COUNT)
    for slot in 1:length(result.proposals)
        proposal = result.proposals[slot]
        emitter[:, slot] .= proposal.point
        records[slot] = Dict{String,Any}(
            "callback_failed" => proposal.callback_failed,
            "canonical_valid" => proposal.canonical_valid,
            "duplicate_of" => proposal.duplicate_of,
            "kind" => "DIRECT_ORBIT_PROPOSAL",
            "phi_float64_bits" => _stagec_float_bits(proposal.phi),
            "slot" => slot,
        )
    end
    fallback_calls = 0
    for slot in (length(result.proposals) + 1):STAGED_EMITTER_COUNT
        emitter[:, slot] .= _staged_physical(problem, @view fallback_normalized[:, slot])
        record = only(_staged_prescore(problem, Matrix(emitter[:, slot:slot]), "DIRECT_TYPED_IID_FALLBACK"))
        record["slot"] = slot
        records[slot] = record
        fallback_calls += 1
    end
    insurance, insurance_records = _staged_insurance(problem, insurance_normalized, name)
    matrix, schedule = _staged_mix(insurance, emitter, insurance_records, records)
    generation = Dict{String,Any}(
        "all_prescores_returned" => true,
        "answer_authority" => false,
        "applicable" => result.diagnostics.status == StageNextDirectRectEmitter.EMITTER_COMPLETE,
        "fallback_prescreen_callbacks" => fallback_calls,
        "logical_prescreen_callbacks" => 64,
        "module_proposal_count" => length(result.proposals),
        "module_diagnostics" => _staged_value(result.diagnostics),
        "physical_prescreen_callbacks" => 16 + calls[] + fallback_calls,
    )
    return (; name, matrix, schedule, generation)
end

function _staged_simplicial_pair(problem, insurance_normalized, fallback_normalized)
    calls = Ref(0)
    callback = point -> begin
        calls[] += 1
        observation = _stagec_observe(problem, Vector{Float64}(point))
        return SimplicialStarEmitter.SimplicialObservation(
            observation.residual;
            branch_token=observation.branch_token,
            canonical_valid=observation.valid,
        )
    end
    pair = SimplicialStarEmitter.plan_simplicial_pair(
        callback,
        collect(Float64, problem.lower_bounds),
        collect(Float64, problem.upper_bounds);
        branch_capability=problem.has_branch_token,
    )
    output = NamedTuple[]
    for (name, plan) in ((STAGED_ARMS[4], pair.unguided), (STAGED_ARMS[5], pair.star))
        emitter = Matrix{Float64}(undef, problem.dimension, STAGED_EMITTER_COUNT)
        records = Vector{Dict{String,Any}}(undef, STAGED_EMITTER_COUNT)
        for slot in 1:length(plan.proposals)
            proposal = plan.proposals[slot]
            emitter[:, slot] .= proposal.point
            records[slot] = Dict{String,Any}(
                "callback_failed" => proposal.callback_failed,
                "canonical_valid" => proposal.canonical_valid,
                "kind" => String(proposal.kind),
                "phi_float64_bits" => _stagec_float_bits(proposal.score),
                "slot" => slot,
            )
        end
        for request in plan.fallbacks
            slot = request.slot
            emitter[:, slot] .= _staged_physical(problem, @view fallback_normalized[:, slot])
            record = only(_staged_prescore(problem, Matrix(emitter[:, slot:slot]), "SIMPLICIAL_TYPED_IID_FALLBACK"))
            record["reason"] = String(request.reason)
            record["slot"] = slot
            records[slot] = record
        end
        insurance, insurance_records = _staged_insurance(problem, insurance_normalized, name)
        matrix, schedule = _staged_mix(insurance, emitter, insurance_records, records)
        generation = Dict{String,Any}(
            "all_prescores_returned" => plan.report.all_prescores_returned,
            "answer_authority" => false,
            "logical_prescreen_callbacks" => 64,
            "module_diagnostics" => _staged_value(plan.report),
            "paired_physical_module_callbacks" => calls[],
            "physical_fallback_callbacks" => length(plan.fallbacks),
            "physical_insurance_callbacks" => 16,
            "shared_pair_base_evaluation" => plan.report.shared_base_evaluation,
        )
        push!(output, (; name, matrix, schedule, generation))
    end
    return output
end

function _staged_ecp(problem, insurance_normalized, candidate_normalized,
    fallback_normalized)
    calls = Ref(0)
    callback = normalized -> begin
        calls[] += 1
        point = _staged_physical(problem, normalized)
        observation = _stagec_observe(problem, point)
        return ECPAcceptanceEmitter.ECPObservation(
            observation.residual; canonical_valid=observation.valid,
        )
    end
    result = ECPAcceptanceEmitter.emit_ecp(
        callback, candidate_normalized; arm=ECPAcceptanceEmitter.ECP_LB_FULL,
    )
    emitter = Matrix{Float64}(undef, problem.dimension, STAGED_EMITTER_COUNT)
    records = Vector{Dict{String,Any}}(undef, STAGED_EMITTER_COUNT)
    for slot in 1:length(result.proposals)
        proposal = result.proposals[slot]
        emitter[:, slot] .= _staged_physical(problem, proposal.point)
        records[slot] = Dict{String,Any}(
            "callback_failed" => proposal.callback_failed,
            "canonical_valid" => proposal.canonical_valid,
            "kind" => "ECP_ACCEPTED",
            "phi_float64_bits" => _stagec_float_bits(proposal.phi),
            "raw_draw_index" => proposal.raw_draw_index,
            "slot" => slot,
        )
    end
    for request in result.fallbacks
        slot = request.slot
        emitter[:, slot] .= _staged_physical(problem, @view fallback_normalized[:, slot])
        record = only(_staged_prescore(problem, Matrix(emitter[:, slot:slot]), "ECP_TYPED_IID_FALLBACK"))
        record["reason"] = String(request.reason)
        record["slot"] = slot
        records[slot] = record
    end
    insurance, insurance_records = _staged_insurance(problem, insurance_normalized, STAGED_ARMS[6])
    matrix, schedule = _staged_mix(insurance, emitter, insurance_records, records)
    generation = Dict{String,Any}(
        "all_prescores_returned" => result.diagnostics.all_evaluated_proposals_retained,
        "answer_authority" => false,
        "logical_prescreen_callbacks" => 64,
        "module_diagnostics" => _staged_value(result.diagnostics),
        "physical_fallback_callbacks" => length(result.fallbacks),
        "physical_insurance_callbacks" => 16,
        "physical_module_callbacks" => calls[],
    )
    return (; name=STAGED_ARMS[6], matrix, schedule, generation)
end

function _staged_sources(problem, case_index)
    # The source algorithms receive only the same truth-blind numerical case
    # view used by local variants.  The root runner retains Gold solely for the
    # later assessor.  Across all six logical arms there are at most 6*64
    # physical prescreens; paired simplicial base evaluations only reduce this.
    screen_case = GeoTargetBenchmarks._truth_blind_case(
        problem, length(STAGED_ARMS) * STAGED_LOCAL_COUNT,
    )
    oracle = GeoTargetBenchmarks._solver_case_oracle(screen_case._evaluate)
    oracle === nothing && error("source screening oracle was not registered")
    try
    insurance_seed = _staged_seed(case_index, "stage-d-emitter-t0-insurance")
    candidate_seed = _staged_seed(case_index, "stage-d-emitter-t0-candidates")
    fallback_seed = _staged_seed(case_index, "stage-d-emitter-t0-fallback")
    insurance = _staged_normalized_random(problem.dimension, insurance_seed, STAGED_INSURANCE_COUNT)
    candidates = _staged_normalized_random(problem.dimension, candidate_seed, STAGED_RAW_DRAW_COUNT)
    fallback = _staged_normalized_random(problem.dimension, fallback_seed, STAGED_EMITTER_COUNT)
    sources = NamedTuple[]
    push!(sources, _staged_d0(screen_case, insurance, candidates))
    push!(sources, _staged_direct(
        screen_case, insurance, fallback,
        StageNextDirectRectEmitter.RECT_ORBIT_BREADTH, STAGED_ARMS[2],
    ))
    push!(sources, _staged_direct(
        screen_case, insurance, fallback,
        StageNextDirectRectEmitter.DIRECT_RECT_EMIT, STAGED_ARMS[3],
    ))
    append!(sources, _staged_simplicial_pair(screen_case, insurance, fallback))
    push!(sources, _staged_ecp(screen_case, insurance, candidates, fallback))
    Tuple(source.name for source in sources) == STAGED_ARMS || error("Stage-D arm order drifted")
    all(source -> size(source.matrix) == (problem.dimension, STAGED_LOCAL_COUNT) &&
        length(source.schedule) == STAGED_LOCAL_COUNT &&
        source.generation["logical_prescreen_callbacks"] == STAGED_LOCAL_COUNT,
        sources) || error("one or more Stage-D arms did not close at 64/64")
    ecp_diagnostics = sources[6].generation["module_diagnostics"]
    ecp_indices = Int[
        record["raw_draw_index"] for record in sources[6].schedule if
        get(record, "lane", nothing) == "EMITTER" && haskey(record, "raw_draw_index")
    ]
    issorted(ecp_indices) && allunique(ecp_indices) &&
        !isempty(ecp_indices) && first(ecp_indices) == 1 &&
        all(index -> 1 <= index <= ecp_diagnostics["raw_draws_consumed"], ecp_indices) &&
        length(ecp_indices) == ecp_diagnostics["accepted_screening_callbacks"] ||
        error("ECP accepted raw-index ledger drifted")
    ecp_diagnostics["raw_draw_cap"] == STAGED_RAW_DRAW_COUNT &&
        0 <= ecp_diagnostics["raw_draws_consumed"] <= STAGED_RAW_DRAW_COUNT &&
        ecp_diagnostics["rejected_unscored_draws"] ==
            ecp_diagnostics["raw_draws_consumed"] -
            ecp_diagnostics["accepted_screening_callbacks"] &&
        ecp_diagnostics["logical_screening_callbacks"] == STAGED_EMITTER_COUNT &&
        ecp_diagnostics["all_evaluated_proposals_retained"] === true &&
        ecp_diagnostics["screened_evidence_discard_count"] == 0 &&
        all(ecp_diagnostics[field] === false for field in (
            "answer_authority", "target_authority", "gold_authority",
            "completeness_authority", "external_result_used",
        )) || error("ECP work/authority ledger drifted")
    for source in sources[2:3]
        diagnostics = source.generation["module_diagnostics"]
        proposal_count = source.generation["module_proposal_count"]
        fallback_count = source.generation["fallback_prescreen_callbacks"]
        closed = diagnostics["status"] == "EMITTER_COMPLETE" ?
            proposal_count == STAGED_EMITTER_COUNT && fallback_count == 0 :
            proposal_count == 0 && fallback_count == STAGED_EMITTER_COUNT
        diagnostics["external_result_used"] === false && closed ||
            error("DIRECT module authority drifted")
    end
    for source in sources[4:5]
        diagnostics = source.generation["module_diagnostics"]
        diagnostics["answer_authority"] === false &&
            diagnostics["homology_authority"] === false &&
            diagnostics["completeness_authority"] === false ||
            error("simplicial module authority drifted")
    end
    paired_module = sources[4].generation["paired_physical_module_callbacks"]
    sources[5].generation["paired_physical_module_callbacks"] == paired_module ||
        error("simplicial pair physical count drifted")
    paired_physical = paired_module +
        sources[4].generation["physical_fallback_callbacks"] +
        sources[5].generation["physical_fallback_callbacks"] + 32
    physical_total =
        sources[1].generation["physical_prescreen_callbacks"] +
        sources[2].generation["physical_prescreen_callbacks"] +
        sources[3].generation["physical_prescreen_callbacks"] +
        paired_physical +
        sources[6].generation["physical_module_callbacks"] +
        sources[6].generation["physical_fallback_callbacks"] +
        sources[6].generation["physical_insurance_callbacks"]
    physical_total <= length(STAGED_ARMS) * STAGED_LOCAL_COUNT ||
        error("physical source callback cap drifted")
    observed_total = oracle.evaluation_count[]
    observed_total == physical_total || error(
        "physical source callback mismatch: declared=$physical_total observed=$observed_total",
    )
    oracle.budget_exhausted[] || observed_total <= oracle.evaluation_limit ||
        error("source screening oracle ledger is inconsistent")
    !oracle.budget_exhausted[] || error("source screening oracle budget exhausted")
    stream = Dict{String,Any}(
        "candidate_columns" => STAGED_RAW_DRAW_COUNT,
        "candidate_matrix_sha256" => _staged_matrix_sha(candidates),
        "candidate_seed" => string(candidate_seed),
        "fallback_columns" => STAGED_EMITTER_COUNT,
        "fallback_matrix_sha256" => _staged_matrix_sha(fallback),
        "fallback_seed" => string(fallback_seed),
        "generator" => "Random.Xoshiro Float64 normalized by muladd(2,u,-1)",
        "insurance_columns" => STAGED_INSURANCE_COUNT,
        "insurance_matrix_sha256" => _staged_matrix_sha(insurance),
        "insurance_seed" => string(insurance_seed),
        "observed_physical_prescreen_callbacks" => observed_total,
        "physical_prescreen_callbacks_total" => physical_total,
        "screen_oracle_budget_exhausted" => oracle.budget_exhausted[],
        "screen_oracle_evaluation_limit" => oracle.evaluation_limit,
        "truth_fields_visible" => false,
    )
    return sources, stream
    finally
        GeoTargetBenchmarks._release_solver_case_oracle!(screen_case._evaluate)
    end
end

function _staged_run_arm(problem, source, variant)
    # The existing development-corpus adapter stores a fixed 128-column maximum
    # matrix.  Stage D authorizes only its first 64 columns; the duplicated tail
    # is structural padding and is never requested by the `(64,)` prefix.
    padded = hcat(source.matrix, source.matrix)
    run_problem = StageCT0Inputs.stagec_t0_problem_with_proposals(problem, padded)
    run = run_solver_experiment(
        [run_problem], [variant]; prefixes=(STAGED_LOCAL_COUNT,),
        evaluation_limit=STAGED_LOCAL_CAP,
    )
    attempts = collect(run.attempts)
    serialized = solver_experiment_document(run)["attempts"]
    length(attempts) == length(serialized) == STAGED_LOCAL_COUNT || error("local service count drifted")
    for position in eachindex(attempts)
        reinterpret(UInt64, collect(attempts[position].start)) ==
            reinterpret(UInt64, source.matrix[:, position]) || error("local start bits drifted")
        serialized[position]["discovery_lane"] = source.schedule[position]["lane"]
        serialized[position]["discovery_position"] = position
        serialized[position]["emitter_slot"] = source.schedule[position]["emitter_slot"]
        serialized[position]["insurance_slot"] = source.schedule[position]["insurance_slot"]
    end
    return (; attempts, serialized, terminal=_stagec_terminal(attempts))
end

function _staged_lock(cpu)
    stream = open("/tmp/geotarget-exp-disc-001-stage-d-emitter-cpu-$cpu.lock", "w")
    ccall(:flock, Cint, (Cint, Cint), fd(stream), 2 | 4) == 0 ||
        (close(stream); error("CPU $cpu already has a Stage-D case process"))
    return stream
end

function _staged_execute(case_index, cpu, output)
    active_project()
    threads = thread_contract()
    isempty(strip(read(`git -C $STAGED_REPO status --porcelain`, String))) || error("clean tree required")
    prereg = _staged_preregistration()
    1 <= case_index <= STAGED_CASE_COUNT || error("case index out of range")
    cpu == case_index - 1 && 0 <= cpu <= 11 || error("case/CPU assignment drifted")
    get(ENV, "GEOTARGET_CASE_PROCESS_LIMIT", "unset") == "12" ||
        error("GEOTARGET_CASE_PROCESS_LIMIT=12 is required")
    matched = match(r"(?m)^Cpus_allowed_list:\s*(.+)$", read("/proc/self/status", String))
    allowed = matched === nothing ? "" : strip(matched.captures[1])
    matched !== nothing && allowed == string(cpu) &&
        ccall(:sched_getcpu, Cint, ()) == cpu || error("process must be pinned to CPU $cpu")
    ispath(output) && error("refusing to overwrite Stage-D raw shard")
    lock = _staged_lock(cpu)
    try
        problems = StageCT0Inputs.stagec_t0_problems()
        problem = problems[case_index]
        case_manifest = _staged_validate_case_binding(prereg, case_index, problem)
        source_started = time_ns()
        sources, stream = _staged_sources(problem, case_index)
        source_seconds = (time_ns() - source_started) / 1.0e9
        freeze = json_document(prereg.freeze_path, "local finalist freeze")
        variant = local_variant(freeze)
        arm_documents = Dict{String,Any}[]
        for source in sources
            phase = _staged_run_arm(problem, source, variant)
            push!(arm_documents, Dict{String,Any}(
                "all_locally_serviced" => length(phase.attempts) == STAGED_LOCAL_COUNT,
                "attempts" => phase.serialized,
                "generation" => source.generation,
                "matrix" => _stagec_matrix_document(source.matrix),
                "name" => source.name,
                "schedule" => source.schedule,
                "terminal" => phase.terminal,
            ))
        end
        document = Dict{String,Any}(
            "arm_order" => collect(STAGED_ARMS),
            "arms" => arm_documents,
            "case_index" => case_index,
            "case_manifest" => case_manifest,
            "experiment_id" => "EXP-DISC-001",
            "lab_confirmation_512_768" => false,
            "nonpromotional_t0" => true,
            "preregistration" => Dict("path" => repo_relative(prereg.path), "sha256" => prereg.sha256),
            "revision" => Dict(
                "git_dirty" => false,
                "git_head" => readchomp(`git -C $STAGED_REPO rev-parse HEAD`),
            ),
            "schema_version" => "geotarget.discovery-stage-d-emitter-t0-raw/v1",
            "source_generation_completed_before_local" => true,
            "source_generation_wall_seconds" => source_seconds,
            "source_stream" => stream,
            "stage" => "stage-d-emitter-t0",
            "thread_contract" => merge(threads, Dict(
                "assigned_cpu" => cpu,
                "case_process_limit" => 12,
                "cpus_allowed_list" => allowed,
                "solver_worker_count" => 1,
            )),
        )
        _stagec_write_exclusive(output, document)
        println("output=", output)
        return document
    finally
        close(lock)
    end
end

function _staged_self_test()
    dimension = 3
    seed = _staged_seed(1, "stage-d-emitter-t0-self-test")
    first = _staged_normalized_random(dimension, seed, 64)
    second = _staged_normalized_random(dimension, seed, 64)
    reinterpret(UInt64, first) == reinterpret(UInt64, second) || error("raw generator is not repeatable")
    insurance_records = [Dict{String,Any}("slot" => slot) for slot in 1:16]
    emitter_records = [Dict{String,Any}("slot" => slot) for slot in 1:48]
    matrix, schedule = _staged_mix(first[:, 1:16], first[:, 17:64], insurance_records, emitter_records)
    size(matrix) == (3, 64) && count(row -> row["lane"] == "IID_INSURANCE", schedule) == 16 ||
        error("synthetic bounded-gap mix drifted")
    return Dict{String,Any}(
        "arm_order" => collect(STAGED_ARMS),
        "case_count" => STAGED_CASE_COUNT,
        "raw_generator_repeatable" => true,
        "schema_version" => "geotarget.discovery-stage-d-emitter-t0-runner-self-test/v1",
        "solver_invocations" => 0,
    )
end

function _staged_parse(args)
    mode, case_index, cpu, output = :preflight, nothing, nothing, nothing
    for argument in args
        argument == "--self-test" ? (mode = :self_test) :
        argument == "--preflight-only" ? (mode = :preflight) :
        argument == "--execute" ? (mode = :execute) :
        startswith(argument, "--case-index=") ?
            (case_index = parse(Int, split(argument, '='; limit=2)[2])) :
        startswith(argument, "--assigned-cpu=") ?
            (cpu = parse(Int, split(argument, '='; limit=2)[2])) :
        startswith(argument, "--output=") ?
            (output = abspath(split(argument, '='; limit=2)[2])) :
        error("unknown Stage-D option: $argument")
    end
    if case_index !== nothing && output === nothing
        output = joinpath(
            STAGED_RAW_ROOT,
            "exp-disc-001-stage-d-emitter-t0-case-$(lpad(case_index, 2, '0')).json",
        )
    end
    return (; mode, case_index, cpu, output)
end

function staged_emitter_t0_main(args=ARGS)
    options = _staged_parse(args)
    result = if options.mode == :self_test
        _staged_self_test()
    elseif options.mode == :preflight
        active_project(); thread_contract()
        prereg = _staged_preregistration()
        Dict{String,Any}(
            "arm_order" => collect(STAGED_ARMS),
            "case_indices" => collect(1:STAGED_CASE_COUNT),
            "outcomes_executed" => false,
            "preregistration_sha256" => prereg.sha256,
            "schema_version" => "geotarget.discovery-stage-d-emitter-t0-preflight/v1",
        )
    else
        options.case_index === nothing && error("--case-index is required")
        options.cpu === nothing && error("--assigned-cpu is required")
        options.output === nothing && error("--output is required")
        _staged_execute(options.case_index, options.cpu, options.output)
    end
    options.mode == :execute || println(canonical_json(result))
    return result
end

abspath(PROGRAM_FILE) == abspath(@__FILE__) && staged_emitter_t0_main()
