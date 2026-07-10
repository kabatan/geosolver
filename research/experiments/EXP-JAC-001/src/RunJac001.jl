module RunJac001

using ..ExperimentJac001
using GeoTargetBase
using GeoTargetCore
using LinearAlgebra
using SHA

struct RuntimeInstance
    raw::Dict{String,Any}
    problem::ProblemSpecV1
    compiled::CompiledProblem
    compile_seconds::Float64
    entries::Tuple
    starts::Vector{Vector{Float64}}
    root::Vector{Float64}
    matrix::Matrix{Float64}
    nonlinear_kind::Symbol
    nonlinear_parameter::Float64
end

mutable struct OracleCounter
    calls::Int
    work::Int
end

mutable struct JacobianCounter
    calls::Int
    constructions::Int
    groups::Int
    fallback_groups::Int
    fallback_calls::Int
end

_sha256_file(path) = bytes2hex(sha256(read(path)))

function _matrix(raw)
    rows = length(raw)
    columns = length(raw[1])
    result = Matrix{Float64}(undef, rows, columns)
    for row in 1:rows, column in 1:columns
        result[row, column] = Float64(raw[row][column])
    end
    return result
end

function _pattern(raw)
    return Tuple((Int(entry[1]), Int(entry[2])) for entry in raw)
end

function _runtime_instances(document, registry)
    instances = RuntimeInstance[]
    for raw in document["instances"]
        problem = decode_problem_document(raw["problem"], registry)
        timed = @timed compile_problem(problem, registry; numeric_backend="Float64")
        compiled = timed.value
        entries = _pattern(raw["compiler_jacobian_entries"])
        compiled.sparsity.jacobian_entries == entries || error(
            "compiler pattern drift for $(raw["case_id"])",
        )
        truth = raw["truth"]
        push!(
            instances,
            RuntimeInstance(
                raw,
                problem,
                compiled,
                timed.time,
                entries,
                [Float64[value for value in start] for start in raw["starts"]],
                Float64[value for value in truth["root"]],
                _matrix(truth["coefficient_matrix"]),
                Symbol(truth["nonlinear_kind"]),
                Float64(truth["nonlinear_parameter"]),
            ),
        )
    end
    return instances
end

function _counting_evaluator(instance::RuntimeInstance, counter::OracleCounter)
    workspace = CompiledWorkspace(instance.compiled)
    return function (x)
        observation = evaluate(instance.compiled, x; workspace)
        counter.calls += 1
        counter.work += observation.evaluation_cost
        return observation
    end
end

function _bounds(instance)
    count = length(instance.root)
    origins = copy(instance.root)
    scales = ones(count)
    lower = fill(-0.8, count)
    upper = fill(0.8, count)
    return origins, scales, lower, upper, lower .- origins, upper .- origins
end

function _color_lower_bound(entries, residual_count)
    counts = zeros(Int, residual_count)
    for (row, _) in entries
        counts[row] += 1
    end
    return isempty(counts) ? 0 : maximum(counts)
end

function _mismatch_count(observed, expected)
    size(observed) == size(expected) || return max(length(observed), length(expected))
    count = 0
    for index in eachindex(observed, expected)
        isapprox(
            observed[index],
            expected[index];
            atol=ExperimentJac001.DENSE_COLOR_ATOL,
            rtol=ExperimentJac001.DENSE_COLOR_RTOL,
        ) || (count += 1)
    end
    return count
end

function _outside_pattern_count(dense, entries)
    support = Set(entries)
    count = 0
    for row in axes(dense, 1), column in axes(dense, 2)
        (row, column) in support && continue
        tolerance = ExperimentJac001.DENSE_COLOR_ATOL +
                    ExperimentJac001.DENSE_COLOR_RTOL * abs(dense[row, column])
        abs(dense[row, column]) <= tolerance || (count += 1)
    end
    return count
end

function _colored_at_start(instance, start, base_residual, coloring; evaluator=nothing, observer=nothing)
    origins, scales, _, _, lower_u, upper_u = _bounds(instance)
    u = start .- origins
    callback = evaluator === nothing ? x -> evaluate(instance.compiled, x) : evaluator
    return GeoTargetCore._colored_finite_difference_jacobian(
        callback,
        u,
        base_residual,
        origins,
        scales,
        lower_u,
        upper_u,
        LocalSolveOptions().finite_difference_step,
        coloring;
        group_observer=observer,
    )
end

function _negative_control(instance, coloring_order)
    isempty(instance.entries) && error("negative control requires a nonempty pattern")
    incomplete_entries = Base.front(instance.entries)
    coloring = GeoTargetCore._local_jacobian_coloring(
        length(instance.root),
        length(instance.root),
        incomplete_entries;
        order=coloring_order,
    )
    start = instance.starts[1]
    trace = instance.raw["dense_traces"][1]
    dense = _matrix(trace["jacobian"])
    colored, _ = _colored_at_start(
        instance,
        start,
        Float64[value for value in trace["base_residual"]],
        coloring,
    )
    return _mismatch_count(colored, dense) > 0
end

function _invalid_group_observation(observation)
    return OracleObservation(
        observation.relations,
        observation.target,
        observation.guards,
        observation.domains,
        observation.branches,
        EVAL_INVALID_DOMAIN,
        observation.evaluation_cost,
        "EXP-JAC-001 forced grouped-probe failure",
    )
end

function _fallback_control(instance, coloring, trace_index)
    start = instance.starts[trace_index]
    trace = instance.raw["dense_traces"][trace_index]
    dense = _matrix(trace["jacobian"])
    base_residual = Float64[value for value in trace["base_residual"]]
    counter = OracleCounter(0, 0)
    base_evaluate = _counting_evaluator(instance, counter)
    function reject_grouped(x)
        observation = base_evaluate(x)
        changed = count(index -> abs(x[index] - start[index]) > 0, eachindex(x))
        return changed > 1 ? _invalid_group_observation(observation) : observation
    end
    events = NamedTuple[]
    colored, callbacks = _colored_at_start(
        instance,
        start,
        base_residual,
        coloring;
        evaluator=reject_grouped,
        observer=event -> push!(events, event),
    )
    fallback_events = filter(event -> event.fallback, events)
    fallback_columns = sum(length(event.columns) for event in fallback_events; init=0)
    fallback_calls = sum(event.fallback_evaluations for event in fallback_events; init=0)
    return Dict{String,Any}(
        "case_id" => instance.raw["case_id"],
        "callbacks" => callbacks,
        "oracle_work" => counter.work,
        "fallback_groups" => length(fallback_events),
        "fallback_columns" => fallback_columns,
        "fallback_calls" => fallback_calls,
        "mismatch_count" => _mismatch_count(colored, dense),
        "all_affected_columns_retried" => all(
            event -> event.fallback_evaluations > 0 && !isempty(event.columns),
            fallback_events,
        ),
    )
end

function colored_preflight(instances, order)
    mismatch_count = 0
    outside_pattern_count = 0
    callback_count = 0
    oracle_work = 0
    per_instance = Dict{String,Any}[]
    negative_detections = 0
    fallback_controls = Dict{String,Any}[]
    fallback_family_done = Set{String}()
    for instance in instances
        coloring = GeoTargetCore._local_jacobian_coloring(
            length(instance.root),
            length(instance.root),
            instance.entries;
            order,
        )
        instance_mismatches = 0
        instance_outside = 0
        instance_callbacks = 0
        instance_work = 0
        for (index, start) in enumerate(instance.starts)
            trace = instance.raw["dense_traces"][index]
            dense = _matrix(trace["jacobian"])
            counter = OracleCounter(0, 0)
            colored, callbacks = _colored_at_start(
                instance,
                start,
                Float64[value for value in trace["base_residual"]],
                coloring;
                evaluator=_counting_evaluator(instance, counter),
            )
            instance_mismatches += _mismatch_count(colored, dense)
            instance_outside += _outside_pattern_count(dense, instance.entries)
            callbacks == counter.calls || error("differential callback accounting drift")
            instance_callbacks += callbacks
            instance_work += counter.work
        end
        negative_detections += Int(_negative_control(instance, order))
        family = String(instance.raw["family_id"])
        if !(family in fallback_family_done) && any(length(group) > 1 for group in coloring.groups)
            control = _fallback_control(instance, coloring, 2)
            push!(fallback_controls, control)
            push!(fallback_family_done, family)
        end
        lower_bound = _color_lower_bound(instance.entries, length(instance.root))
        push!(
            per_instance,
            Dict{String,Any}(
                "case_id" => instance.raw["case_id"],
                "family_id" => family,
                "color_count" => length(coloring.groups),
                "color_lower_bound" => lower_bound,
                "relative_gap" => lower_bound == 0 ? 0.0 :
                                  (length(coloring.groups) - lower_bound) / lower_bound,
                "structural_nonzeros" => coloring.structural_nonzeros,
                "mismatch_count" => instance_mismatches,
                "outside_pattern_count" => instance_outside,
                "callbacks" => instance_callbacks,
                "oracle_work" => instance_work,
            ),
        )
        mismatch_count += instance_mismatches
        outside_pattern_count += instance_outside
        callback_count += instance_callbacks
        oracle_work += instance_work
    end
    fallback_failures = count(
        control -> control["mismatch_count"] != 0 ||
                   control["fallback_groups"] == 0 ||
                   !control["all_affected_columns_retried"],
        fallback_controls,
    )
    return Dict{String,Any}(
        "order" => String(order),
        "dense_colored_mismatch_count" => mismatch_count,
        "dense_outside_pattern_count" => outside_pattern_count,
        "callbacks" => callback_count,
        "oracle_work" => oracle_work,
        "negative_control_instances" => length(instances),
        "negative_control_detections" => negative_detections,
        "fallback_controls" => fallback_controls,
        "fallback_control_failure_count" => fallback_failures,
        "per_instance" => per_instance,
        "passed" => mismatch_count == 0 && outside_pattern_count == 0 &&
                    negative_detections == length(instances) && fallback_failures == 0,
    )
end

function _warmup!(instances, variant, order)
    seen = Set{String}()
    for instance in instances
        family = String(instance.raw["family_id"])
        family in seen && continue
        push!(seen, family)
        counter = OracleCounter(0, 0)
        entries = variant == "J0-DENSE-CENTRAL" ? nothing : instance.entries
        solve_local(
            _counting_evaluator(instance, counter),
            instance.starts[1];
            origins=instance.root,
            scales=ones(length(instance.root)),
            lower=fill(-0.8, length(instance.root)),
            upper=fill(0.8, length(instance.root)),
            options=LocalSolveOptions(
                max_iterations=ExperimentJac001.MAX_ITERATIONS,
                max_evaluations=ExperimentJac001.MAX_EVALUATIONS,
                residual_tolerance=ExperimentJac001.CANONICAL_RESIDUAL_TOLERANCE,
            ),
            jacobian_entries=entries,
            color_order=order,
        )
    end
    return nothing
end

function _cold_records(instances, variant, order)
    # Remove method compilation from the per-problem construction measurement.
    GeoTargetCore._local_jacobian_coloring(1, 1, ((1, 1),); order)
    records = Dict{String,Any}[]
    for instance in instances
        if variant == "J0-DENSE-CENTRAL"
            push!(records, Dict(
                "case_id" => instance.raw["case_id"],
                "compile_seconds" => instance.compile_seconds,
                "coloring_seconds" => 0.0,
                "coloring_bytes" => 0,
                "color_count" => length(instance.root),
                "color_lower_bound" => _color_lower_bound(
                    instance.entries,
                    length(instance.root),
                ),
            ))
        else
            timed = @timed GeoTargetCore._local_jacobian_coloring(
                length(instance.root),
                length(instance.root),
                instance.entries;
                order,
            )
            push!(records, Dict(
                "case_id" => instance.raw["case_id"],
                "compile_seconds" => instance.compile_seconds,
                "coloring_seconds" => timed.time,
                "coloring_bytes" => timed.bytes,
                "color_count" => length(timed.value.groups),
                "color_lower_bound" => _color_lower_bound(
                    instance.entries,
                    length(instance.root),
                ),
            ))
        end
    end
    return records
end

function _run_attempt(instance, start, start_index, variant, order)
    oracle = OracleCounter(0, 0)
    jacobian = JacobianCounter(0, 0, 0, 0, 0)
    evaluate_fn = _counting_evaluator(instance, oracle)
    entries = variant == "J0-DENSE-CENTRAL" ? nothing : instance.entries
    group_observer = function (event)
        jacobian.groups += 1
        if event.fallback
            jacobian.fallback_groups += 1
            jacobian.fallback_calls += event.fallback_evaluations
        end
        return nothing
    end
    jacobian_observer = function (event)
        jacobian.calls += event.evaluations
        jacobian.constructions += 1
        return nothing
    end
    options = LocalSolveOptions(
        max_iterations=ExperimentJac001.MAX_ITERATIONS,
        max_evaluations=ExperimentJac001.MAX_EVALUATIONS,
        residual_tolerance=ExperimentJac001.CANONICAL_RESIDUAL_TOLERANCE,
    )
    timed = @timed begin
        attempt = solve_local(
            evaluate_fn,
            start;
            origins=instance.root,
            scales=ones(length(instance.root)),
            lower=fill(-0.8, length(instance.root)),
            upper=fill(0.8, length(instance.root)),
            options,
            deadline_ns=time_ns() + UInt64(60_000_000_000),
            jacobian_entries=entries,
            color_order=order,
            color_group_observer=group_observer,
            jacobian_observer,
        )
        solve_calls = oracle.calls
        replay = evaluate_fn(collect(attempt.final))
        canonical = canonical_feasible(
            replay;
            residual_tolerance=ExperimentJac001.CANONICAL_RESIDUAL_TOLERANCE,
        )
        configuration_error = maximum(abs.(collect(attempt.final) .- instance.root))
        target_error = abs(Float64(replay.target) - instance.root[1])
        gold = canonical &&
               configuration_error <= ExperimentJac001.GOLD_CONFIGURATION_TOLERANCE &&
               target_error <= ExperimentJac001.GOLD_TARGET_TOLERANCE
        (
            attempt,
            solve_calls,
            replay,
            canonical,
            configuration_error,
            target_error,
            gold,
        )
    end
    attempt, solve_calls, replay, canonical, configuration_error, target_error, gold = timed.value
    solve_calls == attempt.evaluations || error("local callback accounting drift")
    oracle.calls == solve_calls + 1 || error("validation callback was not charged")
    false_candidate = attempt.accepted && !gold
    budget_overrun = attempt.evaluations > ExperimentJac001.MAX_EVALUATIONS ||
                     attempt.iterations > ExperimentJac001.MAX_ITERATIONS ||
                     timed.time > 60.0
    coloring = GeoTargetCore._local_jacobian_coloring(
        length(instance.root),
        length(instance.root),
        instance.entries;
        order,
    )
    return Dict{String,Any}(
        "case_id" => instance.raw["case_id"],
        "family_id" => instance.raw["family_id"],
        "generator_id" => instance.raw["generator_id"],
        "start_index" => start_index,
        "variant" => variant,
        "dimension" => length(instance.root),
        "factors" => instance.raw["factors"],
        "status" => string(attempt.status),
        "accepted" => attempt.accepted,
        "canonical_valid" => canonical,
        "gold_valid" => gold,
        "false_candidate" => false_candidate,
        "budget_overrun" => budget_overrun,
        "configuration_error" => configuration_error,
        "target_error" => target_error,
        "iterations" => attempt.iterations,
        "factorizations" => jacobian.constructions,
        "solver_callbacks" => solve_calls,
        "validation_callbacks" => 1,
        "total_callbacks" => oracle.calls,
        "oracle_work" => oracle.work,
        "jacobian_callbacks" => jacobian.calls,
        "jacobian_constructions" => jacobian.constructions,
        "color_groups_evaluated" => jacobian.groups,
        "fallback_groups" => jacobian.fallback_groups,
        "fallback_callbacks" => jacobian.fallback_calls,
        "color_count" => length(coloring.groups),
        "color_lower_bound" => _color_lower_bound(
            instance.entries,
            length(instance.root),
        ),
        "structural_nonzeros" => coloring.structural_nonzeros,
        "wall_seconds" => timed.time,
        "allocated_bytes" => timed.bytes,
        "gc_seconds" => timed.gctime,
        "compile_seconds_in_attempt" => timed.compile_time,
        "endpoint" => collect(attempt.final),
        "replay_status" => string(replay.status),
    )
end

function run_variant(input_path, output_path, variant)
    variant in ("J0-DENSE-CENTRAL", "J1-GREEDY-COLOR", "J2-LARGEST-FIRST-COLOR") ||
        throw(ArgumentError("unknown variant $variant"))
    order = variant == "J2-LARGEST-FIRST-COLOR" ? :largest_first : :natural
    document = ExperimentJac001.load_materialized_inputs(input_path)
    ExperimentJac001.validate_materialized_inputs(document)
    registry = ExperimentJac001.experiment_registry()
    instances = _runtime_instances(document, registry)
    cold = _cold_records(instances, variant, order)
    preflight = variant == "J0-DENSE-CENTRAL" ? Dict{String,Any}(
        "order" => "dense",
        "passed" => true,
        "dense_colored_mismatch_count" => 0,
        "dense_outside_pattern_count" => 0,
        "negative_control_instances" => 0,
        "negative_control_detections" => 0,
        "fallback_controls" => Any[],
        "fallback_control_failure_count" => 0,
        "per_instance" => Any[],
        "callbacks" => 0,
        "oracle_work" => 0,
    ) : colored_preflight(instances, order)
    preflight["passed"] || error("colored differential preflight failed")
    _warmup!(instances, variant, order)
    attempts = Dict{String,Any}[]
    for instance in instances
        for (start_index, start) in enumerate(instance.starts)
            push!(attempts, _run_attempt(instance, start, start_index, variant, order))
        end
    end
    result = Dict{String,Any}(
        "schema_version" => "exp-jac-001-worker-result/v1",
        "experiment_id" => ExperimentJac001.EXPERIMENT_ID,
        "partition" => document["partition"],
        "variant" => variant,
        "input_sha256" => _sha256_file(input_path),
        "input_card_sha256" => document["card_sha256"],
        "plugin_lock_sha256" => document["plugin_lock_sha256"],
        "instance_count" => length(instances),
        "starts_per_instance" => document["starts_per_instance"],
        "preflight" => preflight,
        "cold" => cold,
        "attempts" => attempts,
    )
    mkpath(dirname(output_path))
    write(output_path, canonical_json(result))
    return result
end

export run_variant, colored_preflight

end
