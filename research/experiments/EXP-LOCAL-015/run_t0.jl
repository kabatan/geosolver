#!/usr/bin/env julia

using JSON3
using LinearAlgebra
using SHA

include(joinpath(@__DIR__, "src", "ExperimentLocal015.jl"))
const LAB = ExperimentLocal015
const FIX = LAB.FIXTURES

const RAW_SCHEMA = "geotarget.exp-local-015-t0-raw/v1"
const EXPERIMENT_ID = "EXP-LOCAL-015"
const CASE_COUNT = 63
const START_COUNT = 16
const ROOT = normpath(joinpath(@__DIR__, "..", "..", ".."))

_sha256(path) = bytes2hex(sha256(read(path)))

_precision_label(bits::Integer) = Int(bits) <= 53 ? "float64" : string(Int(bits))
_precision_weight(bits::Integer) = Int(bits) <= 53 ? 1 : cld(Int(bits), 53)

function _observe_precision!(counts::Dict{String,Int}, bits::Integer)
    label = _precision_label(bits)
    counts[label] = get(counts, label, 0) + 1
    return nothing
end

_observed_callbacks(counts) = sum(values(counts); init=0)
function _observed_work(counts)
    return sum(
        count * (tier == "float64" ? 1 : _precision_weight(parse(Int, tier))) for
        (tier, count) in pairs(counts);
        init=0,
    )
end

function _git_output(arguments...)
    command = Cmd(Cmd(vcat("git", String[arguments...])); dir=ROOT)
    return readchomp(command)
end

function _clean_revision()
    head = _git_output("rev-parse", "HEAD")
    dirty = !isempty(_git_output("status", "--porcelain", "--untracked-files=all"))
    dirty && error("EXP-LOCAL-015 outcome execution requires a clean revision")
    return (; git_head=head, git_dirty=false)
end

function _runtime_contract()
    VERSION == v"1.12.6" || error("EXP-LOCAL-015 requires Julia 1.12.6")
    project = Base.active_project()
    project === nothing && error("EXP-LOCAL-015 requires an explicit Julia project")
    expected_project = joinpath(ROOT, "research", "experiments", "EXP-LOCAL-002", "Project.toml")
    realpath(project) == realpath(expected_project) || error(
        "EXP-LOCAL-015 must run with --project=research/experiments/EXP-LOCAL-002",
    )
    manifest = joinpath(dirname(expected_project), "Manifest.toml")
    isfile(manifest) || error("formal Julia manifest is missing")
    return Dict(
        "active_project_path" => relpath(expected_project, ROOT),
        "julia_version" => string(VERSION),
        "manifest_sha256" => _sha256(manifest),
        "project_sha256" => _sha256(expected_project),
    )
end

function _formal_thread_environment()
    settings = Dict(
        "openblas_env_threads" => get(ENV, "OPENBLAS_NUM_THREADS", ""),
        "omp_env_threads" => get(ENV, "OMP_NUM_THREADS", ""),
        "mkl_env_threads" => get(ENV, "MKL_NUM_THREADS", ""),
    )
    all(value == "1" for value in values(settings)) || error(
        "OPENBLAS_NUM_THREADS, OMP_NUM_THREADS and MKL_NUM_THREADS must all equal 1",
    )
    return Dict(key => 1 for key in keys(settings))
end

function _registration(path)
    document = JSON3.read(read(path, String))
    String(document.experiment_id) == EXPERIMENT_ID || error("wrong registration")
    Bool(document.outcome_execution_authorized) || error("T0 outcome is not authorized")
    String(document.active_stage) == "t0" || error("registration is not at T0")
    Int(document.case_count) == CASE_COUNT || error("registered case count drifted")
    Int(document.start_count) == START_COUNT || error("registered start count drifted")
    String.(collect(document.arm_order)) == collect(LAB.T0_ARMS) || error(
        "registered arm order drifted",
    )
    for (relative, expected) in pairs(document.frozen_inputs)
        candidate = joinpath(ROOT, split(String(relative), '/')...)
        isfile(candidate) || error("missing frozen input: $(relative)")
        _sha256(candidate) == String(expected) || error("frozen input drifted: $(relative)")
    end
    return document
end

function _corpus_checksum(cases)
    payload = join((FIX.replay_checksum(case.record) for case in cases), "\n")
    return bytes2hex(sha256(codeunits(payload)))
end

_float_bits(value::Float64) = string(reinterpret(UInt64, value); base=16, pad=16)

function _normalize_digest_value(value)
    value === nothing && return Any["null"]
    value isa Bool && return Any["bool", value]
    value isa Integer && return Any["int", string(value)]
    value isa AbstractString && return Any["string", String(value)]
    value isa AbstractFloat && begin
        finite = Float64(value)
        isfinite(finite) || error("candidate digest contains a nonfinite Float64")
        return Any["float64", _float_bits(finite)]
    end
    value isa AbstractVector && return Any[
        "list",
        Any[_normalize_digest_value(child) for child in value],
    ]
    value isa Tuple && return Any[
        "list",
        Any[_normalize_digest_value(child) for child in value],
    ]
    value isa AbstractDict || error("unsupported candidate digest value $(typeof(value))")
    ordered_keys = sort!(String.(collect(Base.keys(value))))
    return Any[
        "dict",
        Any[Any[key, _normalize_digest_value(value[key])] for key in ordered_keys],
    ]
end

function _canonical_json(value)
    value === nothing && return "null"
    value isa Bool && return value ? "true" : "false"
    value isa Integer && return string(value)
    value isa AbstractString && return JSON3.write(String(value))
    value isa AbstractVector && return "[" * join((_canonical_json(child) for child in value), ',') * "]"
    value isa AbstractDict || error("unsupported normalized JSON type $(typeof(value))")
    ordered_keys = sort!(String.(collect(Base.keys(value))))
    members = (
        string(JSON3.write(key), ':', _canonical_json(value[key])) for key in ordered_keys
    )
    return "{" * join(members, ',') * "}"
end

function _candidate_digest(input)
    normalized = _normalize_digest_value(input)
    return bytes2hex(sha256(codeunits(_canonical_json(normalized))))
end

function _finite_tag(value)
    return isfinite(value) ? "float64_bits:$(_float_bits(Float64(value)))" : string(value)
end

function _candidate_input(candidate, prefilter)
    anchor = prefilter.anchor
    semantic_ids = anchor isa LAB.WEAK.RescueEvaluation ?
                   String[
                       repr(anchor.branch_identity),
                       repr(anchor.guard_identity),
                       repr(anchor.domain_identity),
                   ] : String[]
    semantic_margins = anchor isa LAB.WEAK.RescueEvaluation ?
                       Float64[
                           anchor.branch_margin,
                           anchor.guard_margin,
                           anchor.domain_margin,
                       ] : Float64[]
    return Dict{String,Any}(
        "bounds" => Any[
            Float64[candidate.box.lower[index], candidate.box.upper[index]] for
            index in eachindex(candidate.box.lower)
        ],
        "condition_class" => String(prefilter.condition_class),
        "condition_interval" => String[
            _finite_tag(prefilter.condition_lower_bound),
            _finite_tag(prefilter.condition_upper_bound),
        ],
        "dimension" => length(prefilter.endpoint),
        "endpoint" => copy(prefilter.endpoint),
        "model_agreement" => prefilter.model_agreement,
        "numerical_rank" => prefilter.numerical_rank,
        "prefilter_reason" => String(prefilter.reason),
        "prefilter_status" => String(prefilter.status),
        "semantic_ids" => semantic_ids,
        "semantic_margins" => semantic_margins,
    )
end

function _activation(arm, result)
    if arm in (LAB.WEAK_ARM, LAB.ISOTROPIC_ARM, LAB.WEAK_NO_EMIT_ARM)
        return Dict(
            "rank_evidence_activated" => Bool(result.observables.rank_evidence_activated),
            "strict_bracket_detected" => Bool(result.observables.strict_bracket_detected),
        )
    elseif arm == LAB.ADAPTIVE_ARM
        return Dict(
            "cross_tier_confirmed" => Bool(result.observables.cross_tier_confirmed),
            "newton_step_accepted" => Bool(result.observables.newton_step_accepted),
            "tier_started" => Bool(result.observables.tier_started),
        )
    elseif arm == LAB.WEAK_ADAPTIVE_ARM
        return Dict(
            "adaptive_attempt_started" => Bool(result.observables.adaptive_attempt_started),
            "cross_tier_confirmed" => Bool(result.observables.cross_tier_confirmed),
            "strict_bracket_detected" => Bool(result.observables.strict_bracket_detected),
        )
    elseif arm == LAB.DIAGNOSTIC_ARM
        return Dict("rank_or_condition_trigger" => Bool(result.activation))
    elseif arm == LAB.REFERENCE_ARM
        return Dict("factorization_performed" => Bool(result.activation))
    end
    return Dict("mechanism_activated" => Bool(result.activation))
end

function _coordinates(result)
    if !isempty(result.bracket_seeds)
        return [Float64[seed.normalized_point...] for seed in result.bracket_seeds]
    end
    return [Float64[Float64(value) for value in point] for point in result.point_seeds]
end

function _brackets(result)
    return Any[
        Dict(
            "lower_parameter" => seed.lower_parameter,
            "lower_projected_residual" => seed.lower_projected_residual,
            "midpoint_coordinates" => Float64[seed.normalized_point...],
            "unit_direction" => Float64[seed.probe_direction...],
            "upper_parameter" => seed.upper_parameter,
            "upper_projected_residual" => seed.upper_projected_residual,
        ) for seed in result.bracket_seeds
    ]
end

function _diagnostic_value(value)
    value === nothing && return nothing
    value isa Bool && return value
    value isa Integer && return value
    value isa AbstractFloat && return isfinite(value) ? Float64(value) : string(value)
    value isa AbstractString && return String(value)
    value isa Symbol && return String(value)
    value isa Tuple && return Any[_diagnostic_value(child) for child in value]
    value isa AbstractVector && return Any[_diagnostic_value(child) for child in value]
    if value isa NamedTuple
        return Dict(String(key) => _diagnostic_value(getproperty(value, key)) for key in keys(value))
    elseif value isa AbstractDict
        return Dict(String(key) => _diagnostic_value(child) for (key, child) in pairs(value))
    end
    return string(value)
end

function _root_labels(indices)
    return ["root-$(lpad(string(index), 3, '0'))" for index in indices]
end

function _assess(arm, result, record, endpoint)
    truth = FIX.assessor_truth(record)
    safety = record.descriptor.stratum == :safety_control
    if arm == LAB.NO_RESCUE_ARM
        matched = LAB.assess_point_seeds(truth, [endpoint])
        return Dict(
            "matched_isolated_root_classes" => safety ? String[] : _root_labels(matched.matched_root_indices),
            "safety_control" => safety,
            "valid_refinement_seed" => false,
        )
    elseif arm in (LAB.WEAK_ARM, LAB.ISOTROPIC_ARM)
        matched = LAB.assess_bracket_seeds(truth, endpoint, result.bracket_seeds)
        valid = !safety && matched.emitted_count > 0 && matched.unsupported_count == 0
        # A weak bracket is seed/activation evidence, never root-recall authority.
        return Dict(
            "matched_isolated_root_classes" => String[],
            "safety_control" => safety,
            "valid_refinement_seed" => valid,
        )
    elseif arm in (LAB.DIAGNOSTIC_ARM, LAB.WEAK_NO_EMIT_ARM)
        return Dict(
            "matched_isolated_root_classes" => String[],
            "safety_control" => safety,
            "valid_refinement_seed" => false,
        )
    end
    matched = LAB.assess_point_seeds(truth, result.point_seeds)
    valid = !safety && matched.emitted_count > 0 && matched.unsupported_count == 0
    return Dict(
        "matched_isolated_root_classes" => valid ? _root_labels(matched.matched_root_indices) : String[],
        "safety_control" => safety,
        "valid_refinement_seed" => valid,
    )
end

function _exception_activation(arm)
    if arm in (LAB.WEAK_ARM, LAB.ISOTROPIC_ARM, LAB.WEAK_NO_EMIT_ARM)
        return Dict("rank_evidence_activated" => false, "strict_bracket_detected" => false)
    elseif arm == LAB.ADAPTIVE_ARM
        return Dict(
            "cross_tier_confirmed" => false,
            "newton_step_accepted" => false,
            "tier_started" => false,
        )
    elseif arm == LAB.WEAK_ADAPTIVE_ARM
        return Dict(
            "adaptive_attempt_started" => false,
            "cross_tier_confirmed" => false,
            "strict_bracket_detected" => false,
        )
    elseif arm == LAB.DIAGNOSTIC_ARM
        return Dict("rank_or_condition_trigger" => false)
    elseif arm == LAB.REFERENCE_ARM
        return Dict("factorization_performed" => false)
    end
    return Dict("mechanism_activated" => false)
end

function _row(
    arm,
    start_index,
    candidate_input,
    prefilter,
    shared_observed_counts,
    record,
    endpoint,
    thunk,
)
    result = nothing
    exception = nothing
    observed_counts = Dict{String,Int}()
    observer = bits -> _observe_precision!(observed_counts, bits)
    try
        result = thunk(observer)
    catch error
        error isa InterruptException && rethrow()
        exception = sprint(showerror, error, catch_backtrace())
    end
    if result === nothing
        counts = Dict{String,Int}()
        callbacks = 0
        work = 0
        status = "exception"
        reason = "exception"
        activation = _exception_activation(arm)
        coordinates = Vector{Vector{Float64}}()
        brackets = Any[]
        diagnostics = Dict{String,Any}()
        assessor = Dict(
            "matched_isolated_root_classes" => String[],
            "safety_control" => record.descriptor.stratum == :safety_control,
            "valid_refinement_seed" => false,
        )
    else
        counts = result.requested_precision_counts
        callbacks = result.rescue_callbacks
        work = result.rescue_weighted_work
        status = String(result.status)
        reason = String(result.reason)
        activation = _activation(arm, result)
        coordinates = result.new_seed_count > 0 ? _coordinates(result) : Vector{Vector{Float64}}()
        brackets = _brackets(result)
        diagnostics = _diagnostic_value(result.observables)
        assessor = _assess(arm, result, record, endpoint)
    end
    emission = !isempty(brackets) ? "bracket_seed" :
               !isempty(coordinates) ? "refinement_seed" : "none"
    shared_callbacks = prefilter.callbacks
    shared_work = prefilter.callbacks
    observed_callbacks = _observed_callbacks(observed_counts)
    observed_work = _observed_work(observed_counts)
    shared_observed_callbacks = _observed_callbacks(shared_observed_counts)
    shared_observed_work = _observed_work(shared_observed_counts)
    return Dict(
        "activation_observables" => activation,
        "arm" => arm,
        "assessor" => assessor,
        "budget_exhausted" => occursin("budget", lowercase(reason)),
        "candidate_input" => candidate_input,
        "charged_callback_count" => callbacks,
        "charged_weighted_work" => work,
        "emission_kind" => emission,
        "emitted_brackets" => brackets,
        "emitted_seed_coordinates" => coordinates,
        "exception" => exception,
        "mechanism_diagnostics" => diagnostics,
        "observed_callback_count" => observed_callbacks,
        "observed_precision_counts" => copy(observed_counts),
        "observed_weighted_work" => observed_work,
        "reason" => reason,
        "reported_callback_count" => callbacks,
        "reported_weighted_work" => work,
        "requested_precision_counts" => counts,
        "shared_callback_count" => shared_callbacks,
        "shared_observed_callback_count" => shared_observed_callbacks,
        "shared_observed_precision_counts" => copy(shared_observed_counts),
        "shared_observed_weighted_work" => shared_observed_work,
        "shared_requested_precision_counts" => Dict("float64" => shared_callbacks),
        "shared_weighted_work" => shared_work,
        "start_index" => start_index,
        "status" => status,
        "total_callback_count" => shared_callbacks + callbacks,
        "total_weighted_work" => shared_work + work,
        "truth_free_replay_digest" => _candidate_digest(candidate_input),
    )
end

function _case_document(
    case_index,
    registration_path,
    registration,
    revision,
    runtime_contract,
)
    cases = LAB.materialize_t0_cases()
    registered_checksum = String(registration.corpus_checksum)
    _corpus_checksum(cases) == registered_checksum || error("registered corpus drifted")
    selected = cases[case_index]
    record = selected.record
    candidate = FIX.candidate_view(record)
    rows = Any[]
    for (start_index, endpoint) in enumerate(candidate.starts)
        shared_observed_counts = Dict{String,Int}()
        prefilter = LAB.acquire_shared_prefilter(
            candidate,
            endpoint;
            observe_callback=bits -> _observe_precision!(shared_observed_counts, bits),
        )
        prefilter.callbacks == 1 + 4length(endpoint) || error("shared work drifted")
        _observed_callbacks(shared_observed_counts) == prefilter.callbacks || error(
            "shared physical callback observation drifted",
        )
        input = _candidate_input(candidate, prefilter)
        arms = (
            (LAB.NO_RESCUE_ARM, _ -> LAB.run_no_rescue_arm(endpoint)),
            (LAB.DIAGNOSTIC_ARM, _ -> LAB.run_diagnostic_arm(prefilter)),
            (LAB.REFERENCE_ARM, observer -> LAB.run_reference_arm(
                candidate,
                prefilter;
                observe_callback=observer,
            )),
            (LAB.ADAPTIVE_ARM, observer -> LAB.run_adaptive_arm(
                candidate,
                prefilter;
                observe_callback=observer,
            )),
            (LAB.WEAK_ARM, observer -> LAB.run_weak_arm(
                candidate,
                prefilter;
                lane=:weak,
                endpoint_ordinal=start_index,
                observe_callback=observer,
            )),
            (LAB.ISOTROPIC_ARM, observer -> LAB.run_weak_arm(
                candidate,
                prefilter;
                lane=:isotropic,
                endpoint_ordinal=start_index,
                observe_callback=observer,
            )),
            (LAB.WEAK_NO_EMIT_ARM, observer -> LAB.run_weak_arm(
                candidate,
                prefilter;
                lane=:no_bracket,
                endpoint_ordinal=start_index,
                observe_callback=observer,
            )),
            (LAB.WEAK_ADAPTIVE_ARM, observer -> LAB.run_combined_arm(
                candidate,
                prefilter;
                endpoint_ordinal=start_index,
                observe_callback=observer,
            )),
        )
        for (arm, thunk) in arms
            push!(rows, _row(
                arm,
                start_index,
                input,
                prefilter,
                shared_observed_counts,
                record,
                endpoint,
                thunk,
            ))
        end
    end
    length(rows) == START_COUNT * length(LAB.T0_ARMS) || error("row count drifted")
    assigned_cpu = Sys.islinux() ? Int(ccall(:sched_getcpu, Cint, ())) : -1
    thread_contract = Dict{String,Any}(pairs(_formal_thread_environment()))
    thread_contract["assigned_cpu"] = assigned_cpu
    thread_contract["blas_threads"] = BLAS.get_num_threads()
    thread_contract["julia_threads"] = Threads.nthreads()
    thread_contract["solver_worker_count"] = 1
    thread_contract["within_case_parallelism"] = false
    document = Dict(
        "arm_order" => collect(LAB.T0_ARMS),
        "case" => Dict(
            "representation" => String(selected.replica_kind),
            "representation_class_id" => "class-$(lpad(string(selected.class_index), 3, '0'))",
            "stratum_id" => String(record.descriptor.stratum),
        ),
        "case_count" => CASE_COUNT,
        "case_index" => case_index,
        "corpus_checksum" => registered_checksum,
        "experiment_id" => EXPERIMENT_ID,
        "nonpromotional_t0" => true,
        "preregistration" => Dict(
            "path" => relpath(registration_path, ROOT),
            "sha256" => _sha256(registration_path),
        ),
        "revision" => Dict(pairs(revision)),
        "rows" => rows,
        "runtime_contract" => copy(runtime_contract),
        "schema_version" => RAW_SCHEMA,
        "shared_prefilter_physical_evaluations" => START_COUNT,
        "thread_contract" => thread_contract,
    )
    return document
end

function _arguments(arguments)
    values = Dict{String,String}()
    index = 1
    while index <= length(arguments)
        key = arguments[index]
        key in ("--case-index", "--output", "--registration") || error("unknown argument $key")
        index < length(arguments) || error("missing value for $key")
        values[key] = arguments[index + 1]
        index += 2
    end
    all(haskey(values, key) for key in ("--case-index", "--output", "--registration")) ||
        error("--case-index, --output and --registration are required")
    return (
        case_index=parse(Int, values["--case-index"]),
        output=abspath(values["--output"]),
        registration=abspath(values["--registration"]),
    )
end

function main(arguments=ARGS)
    options = _arguments(arguments)
    1 <= options.case_index <= CASE_COUNT || error("case index must lie in 1:63")
    Threads.nthreads() == 1 || error("T0 requires JULIA_NUM_THREADS=1")
    _formal_thread_environment()
    BLAS.set_num_threads(1)
    runtime_contract = _runtime_contract()
    registration = _registration(options.registration)
    revision = _clean_revision()
    document = _case_document(
        options.case_index,
        options.registration,
        registration,
        revision,
        runtime_contract,
    )
    mkpath(dirname(options.output))
    open(options.output, "w") do io
        JSON3.write(io, document)
        write(io, '\n')
    end
    println("case_index=$(options.case_index) output=$(options.output)")
end

if abspath(PROGRAM_FILE) == @__FILE__
    main()
end
