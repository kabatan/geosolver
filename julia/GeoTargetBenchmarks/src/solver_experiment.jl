const SOLVER_EXPERIMENT_SCHEMA_VERSION = "geotarget.solver-experiment/v2"

"""Independent scoring tolerances for the lightweight solver laboratory."""
struct SolverExperimentTolerances
    residual::Float64
    configuration::Float64
    target::Float64

    function SolverExperimentTolerances(;
        residual::Real=sqrt(eps(Float64)),
        configuration::Real=1.0e-6,
        target::Real=1.0e-6,
    )
        values = Float64[residual, configuration, target]
        all(value -> isfinite(value) && value >= 0, values) ||
            throw(ArgumentError("solver experiment tolerances must be finite and nonnegative"))
        return new(values...)
    end
end

# This card is deliberately independent of both a variant's retcode/acceptance
# and the configurable legacy endpoint tolerances above.  It is the common
# endpoint assessor used to compare every solver variant.
const _SOLVER_EXPERIMENT_ASSESSOR_TOLERANCES = SolverExperimentTolerances(
    residual=1.0e-12,
    configuration=1.0e-6,
    target=1.0e-6,
)

"""One public strict-guard value, identified only within the active case."""
struct SolverPublicGuardObservation
    token::UInt64
    margin::Float64
    scale::Float64
    strict::Bool

    function SolverPublicGuardObservation(
        token::Integer,
        margin::Real,
        scale::Real,
        strict::Bool,
    )
        0 <= token <= typemax(UInt64) || throw(ArgumentError("guard token must fit UInt64"))
        numeric_margin = Float64(margin)
        numeric_scale = Float64(scale)
        isfinite(numeric_margin) || throw(ArgumentError("guard margin must be finite"))
        isfinite(numeric_scale) && numeric_scale > 0 ||
            throw(ArgumentError("guard scale must be finite and positive"))
        return new(UInt64(token), numeric_margin, numeric_scale, strict)
    end
end

"""One black-box evaluation exposed to an algorithm, with no benchmark truth."""
struct SolverCaseEvaluation
    residuals::Tuple
    target::Union{Nothing,Float64}
    semantics_valid::Bool
    finite::Bool
    public_guards::Tuple
    branch_token::Union{Nothing,UInt64}
end

SolverCaseEvaluation(residuals, target, semantics_valid, finite) =
    SolverCaseEvaluation(residuals, target, semantics_valid, finite, (), nothing)

struct SolverExperimentBudgetExceeded <: Exception
    limit::Int
end

Base.showerror(io::IO, error::SolverExperimentBudgetExceeded) =
    print(io, "solver experiment evaluation budget ", error.limit, " exhausted")

struct _SolverCaseOracle{R,T}
    residual!::R
    target::T
    residual_dimension::Int
    lower_bounds::Tuple
    upper_bounds::Tuple
    strict_guard_boundary::Union{Nothing,Float64}
    public_guard_token::Union{Nothing,UInt64}
    evaluation_count::Base.RefValue{Int}
    evaluation_limit::Int
    budget_exhausted::Base.RefValue{Bool}
end

# A variant must not receive the concrete residual/target closures.  Besides
# exposing captured analytic roots through Julia reflection, those closures
# allowed direct calls that bypassed the callback counter.  The public case now
# carries one uniform, token-only callable; only the scorer resolves the token
# to the concrete oracle.  This is an in-process research boundary rather than
# a hostile-code sandbox, so candidate source is still audited against private
# module access.
struct _OpaqueSolverCaseEvaluator
    token::UInt128
end

const _SOLVER_CASE_ORACLE_LOCK = ReentrantLock()
const _SOLVER_CASE_ORACLES = Dict{UInt128,Any}()

function _register_solver_case_oracle(oracle::_SolverCaseOracle)
    evaluator = lock(_SOLVER_CASE_ORACLE_LOCK) do
        token = rand(RandomDevice(), UInt128)
        while haskey(_SOLVER_CASE_ORACLES, token)
            token = rand(RandomDevice(), UInt128)
        end
        _SOLVER_CASE_ORACLES[token] = oracle
        _OpaqueSolverCaseEvaluator(token)
    end
    return evaluator
end

function _solver_case_oracle(evaluator::_OpaqueSolverCaseEvaluator)
    return lock(_SOLVER_CASE_ORACLE_LOCK) do
        get(_SOLVER_CASE_ORACLES, evaluator.token, nothing)
    end
end

function _release_solver_case_oracle!(evaluator::_OpaqueSolverCaseEvaluator)
    lock(_SOLVER_CASE_ORACLE_LOCK) do
        pop!(_SOLVER_CASE_ORACLES, evaluator.token, nothing)
    end
    return nothing
end


function (evaluator::_OpaqueSolverCaseEvaluator)(input)
    oracle = _solver_case_oracle(evaluator)
    oracle === nothing && throw(ArgumentError("solver experiment case is no longer active"))
    return oracle(input)
end

function (oracle::_SolverCaseOracle)(input)
    if oracle.evaluation_count[] >= oracle.evaluation_limit
        oracle.budget_exhausted[] = true
        throw(SolverExperimentBudgetExceeded(oracle.evaluation_limit))
    end
    oracle.evaluation_count[] += 1
    residual = zeros(Float64, oracle.residual_dimension)
    oracle.residual!(residual, input)
    raw_target = oracle.target(input)
    target = raw_target isa Real ? Float64(raw_target) : nothing
    finite = all(isfinite, residual) && target !== nothing && isfinite(target)
    within_bounds = length(input) == length(oracle.lower_bounds) && all(
        oracle.lower_bounds[index] <= input[index] <= oracle.upper_bounds[index] for
        index in eachindex(input)
    )
    guard_valid = oracle.strict_guard_boundary === nothing ||
                  input[1] > oracle.strict_guard_boundary
    public_guards = if oracle.strict_guard_boundary === nothing
        ()
    else
        (
            SolverPublicGuardObservation(
                something(oracle.public_guard_token),
                input[1] - oracle.strict_guard_boundary,
                1.0,
                true,
            ),
        )
    end
    return SolverCaseEvaluation(
        Tuple(residual),
        finite ? target : nothing,
        finite && within_bounds && guard_valid,
        finite,
        public_guards,
        nothing,
    )
end

"""
Truth-blind numerical view passed to an algorithm variant.

It intentionally omits family IDs, instance IDs, Gold configurations, Gold
targets and saved-start matrices. The experiment runner retains those values
only for independent scoring after a variant returns.
"""
struct SolverExperimentCase{F}
    dimension::Int
    residual_dimension::Int
    lower_bounds::Tuple
    upper_bounds::Tuple
    variable_scales::Tuple
    residual_scales::Tuple
    _evaluate::F
end

function evaluate_case(case::SolverExperimentCase, input::AbstractVector)
    length(input) == case.dimension || throw(DimensionMismatch("input has wrong dimension"))
    evaluation = case._evaluate(collect(Float64, input))
    evaluation isa SolverCaseEvaluation || throw(
        ArgumentError("solver experiment callback must return SolverCaseEvaluation"),
    )
    length(evaluation.residuals) == case.residual_dimension || throw(
        DimensionMismatch("solver experiment callback returned the wrong residual dimension"),
    )
    return evaluation
end

"""A named callable with signature `(truth_blind_case, start) -> outcome`."""
struct SolverVariant{F,C<:NamedTuple}
    name::String
    run::F
    configuration::C

    function SolverVariant(
        name::AbstractString,
        run::F;
        configuration::C=(;),
    ) where {F,C<:NamedTuple}
        variant_name = strip(String(name))
        isempty(variant_name) && throw(ArgumentError("solver variant name must be nonempty"))
        return new{F,C}(variant_name, run, configuration)
    end
end

SolverVariant(run::F, name::AbstractString; kwargs...) where {F} =
    SolverVariant(name, run; kwargs...)

"""Normalized result returned by a solver variant before independent scoring."""
struct SolverAttemptOutcome
    endpoint::Union{Nothing,Tuple}
    status::String
    reported_converged::Bool
    reported_accepted::Bool
    evaluations::Int
    iterations::Int
    diagnostic::Union{Nothing,String}

    function SolverAttemptOutcome(
        endpoint;
        status::AbstractString,
        reported_converged::Bool=false,
        reported_accepted::Bool=false,
        evaluations::Integer=0,
        iterations::Integer=0,
        diagnostic::Union{Nothing,AbstractString}=nothing,
    )
        evaluations >= 0 || throw(ArgumentError("evaluations must be nonnegative"))
        iterations >= 0 || throw(ArgumentError("iterations must be nonnegative"))
        frozen_endpoint = endpoint === nothing ? nothing : Tuple(Float64.(endpoint))
        frozen_diagnostic = diagnostic === nothing ? nothing : String(diagnostic)
        return new(
            frozen_endpoint,
            String(status),
            reported_converged,
            reported_accepted,
            Int(evaluations),
            Int(iterations),
            frozen_diagnostic,
        )
    end
end

struct SolverExperimentAttempt
    variant::String
    instance_id::String
    family_id::String
    replay_checksum::String
    start_index::Int
    start::Tuple
    timing_phase::Symbol
    endpoint::Union{Nothing,Tuple}
    status::String
    reported_converged::Bool
    reported_accepted::Bool
    canonical_valid::Bool
    configuration_matched::Bool
    numeric_target_matched::Bool
    gold_matched::Bool
    false_candidate::Bool
    false_target::Bool
    target_ambiguous::Bool
    matched_configuration::Union{Nothing,Int}
    matched_target_id::Union{Nothing,String}
    target_value::Union{Nothing,Float64}
    scaled_residual_linf::Union{Nothing,Float64}
    normalized_configuration_distance::Union{Nothing,Float64}
    assessor_qualified::Bool
    assessor_configuration_matched::Bool
    assessor_numeric_target_matched::Bool
    assessor_gold_matched::Bool
    assessor_target_ambiguous::Bool
    assessor_matched_configuration::Union{Nothing,Int}
    assessor_matched_target_id::Union{Nothing,String}
    evaluations::Int
    reported_evaluations::Int
    evaluation_count_mismatch::Bool
    evaluation_count_difference::Int
    iterations::Int
    budget_exhausted::Bool
    wall_seconds::Float64
    diagnostic::Union{Nothing,String}
    exception::Union{Nothing,String}
end

struct SolverExperimentPrefix
    variant::String
    instance_id::String
    family_id::String
    prefix::Int
    configuration_count::Int
    configurations_found::Int
    target_count::Int
    targets_found::Int
    configuration_recall::Float64
    target_recall::Float64
    all_targets::Bool
    reported_converged::Int
    reported_accepted::Int
    gold_matched::Int
    false_candidates::Int
    false_targets::Int
    ambiguous_targets::Int
    numeric_target_only_hits::Int
    budget_exhausted::Int
    duplicate_configuration_hits::Int
    duplicate_target_hits::Int
    exceptions::Int
    evaluations::Int
    iterations::Int
    wall_seconds::Float64
    warm_wall_seconds::Float64
    status_counts::Tuple
    reported_accepted_targets_found::Int
    reported_accepted_target_recall::Float64
    lab_safe_all_targets::Bool
    reported_accepted_canonical_invalid::Int
    reported_accepted_gold_inconsistent::Int
    reported_accepted_numeric_target_only::Int
    reported_accepted_ambiguous::Int
    assessor_qualified::Int
    assessor_qualified_targets_found::Int
    assessor_qualified_target_recall::Float64
    assessor_qualified_gold_inconsistent::Int
    assessor_all_targets::Bool
    assessor_safe_all_targets::Bool
    local_max_evaluations::Int
    runner_budget_exhausted::Int
    evaluation_count_mismatches::Int
    suffix_stable_evaluations_to_lab_safe_full::Union{Nothing,Int}
end

struct SolverExperimentRun
    attempts::Tuple
    prefixes::Tuple
    requested_prefixes::Tuple
    variant_names::Tuple
    variant_manifest::Tuple
    problem_manifest::Tuple
    tolerances::SolverExperimentTolerances
    evaluation_limit::Int
end

function _benchmark_semantics_valid(problem::DirectAnalyticProblem, input)
    length(input) == problem.dimension || return false
    all(isfinite, input) || return false
    all(problem.lower_bounds .<= input .<= problem.upper_bounds) || return false
    if problem.parameters isa StrictGuardBoundaryParams
        return strict_guard_valid(problem, input)
    end
    return true
end

function _truth_blind_case(problem::DirectAnalyticProblem, evaluation_limit::Int)
    strict_guard_boundary = problem.parameters isa StrictGuardBoundaryParams ?
                            Float64(problem.metadata[:guard_boundary]) : nothing
    public_guard_token = strict_guard_boundary === nothing ? nothing :
                         rand(RandomDevice(), UInt64)
    oracle = _SolverCaseOracle(
        problem.residual!,
        problem.target,
        problem.residual_dimension,
        Tuple(problem.lower_bounds),
        Tuple(problem.upper_bounds),
        strict_guard_boundary,
        public_guard_token,
        Ref(0),
        evaluation_limit,
        Ref(false),
    )
    evaluator = _register_solver_case_oracle(oracle)
    return SolverExperimentCase(
        problem.dimension,
        problem.residual_dimension,
        Tuple(problem.lower_bounds),
        Tuple(problem.upper_bounds),
        Tuple(problem.variable_scales),
        Tuple(problem.residual_scales),
        evaluator,
    )
end

function _score_endpoint(
    problem::DirectAnalyticProblem,
    endpoint,
    tolerances::SolverExperimentTolerances,
)
    if endpoint === nothing || length(endpoint) != problem.dimension ||
       !all(value -> value isa Real && isfinite(value), endpoint)
        return (
            canonical_valid=false,
            configuration_matched=false,
            numeric_target_matched=false,
            gold_matched=false,
            false_candidate=false,
            false_target=false,
            target_ambiguous=false,
            configuration=nothing,
            target_id=nothing,
            target_value=nothing,
            residual_linf=nothing,
            configuration_distance=nothing,
            diagnostic="endpoint is absent, nonfinite, or has the wrong dimension",
        )
    end
    input = Float64[endpoint...]
    residual = fill(NaN, problem.residual_dimension)
    target_value = nothing
    evaluation_error = nothing
    try
        problem.residual!(residual, input)
        raw_target = problem.target(input)
        raw_target isa Real || throw(ArgumentError("target is not real"))
        numeric_target_value = Float64(raw_target)
        isfinite(numeric_target_value) || throw(ArgumentError("target is nonfinite"))
        target_value = numeric_target_value
    catch error
        evaluation_error = sprint(showerror, error)
    end
    scaled = residual ./ problem.residual_scales
    residual_linf = all(isfinite, scaled) ? norm(scaled, Inf) : nothing
    canonical_valid = evaluation_error === nothing && residual_linf !== nothing &&
                      residual_linf <= tolerances.residual &&
                      _benchmark_semantics_valid(problem, input)

    midpoint = (problem.lower_bounds .+ problem.upper_bounds) ./ 2
    half_range = (problem.upper_bounds .- problem.lower_bounds) ./ 2
    distances = [
        norm((input .- configuration) ./ half_range, Inf) for
        configuration in eachcol(problem.gold_configurations)
    ]
    nearest = argmin(distances)
    nearest_distance = distances[nearest]
    configuration = nearest_distance <= tolerances.configuration ? nearest : nothing
    matching_targets = Int[]
    if target_value !== nothing
        for (index, descriptor) in enumerate(problem.gold_targets)
            lower, upper = target_interval(descriptor)
            lower - tolerances.target <= target_value <= upper + tolerances.target &&
                push!(matching_targets, index)
        end
    end
    target_ambiguous = canonical_valid && length(matching_targets) > 1
    target_index = length(matching_targets) == 1 ? only(matching_targets) : nothing
    target_descriptor = target_index === nothing ? nothing : problem.gold_targets[target_index]
    configuration_matched = canonical_valid && configuration !== nothing
    numeric_target_matched = canonical_valid && target_descriptor !== nothing
    gold_matched = configuration_matched && numeric_target_matched &&
                   configuration in configuration_indices(target_descriptor)
    return (
        canonical_valid,
        configuration_matched,
        numeric_target_matched,
        gold_matched,
        false_candidate=canonical_valid && !configuration_matched,
        false_target=canonical_valid && isempty(matching_targets),
        target_ambiguous,
        configuration=configuration_matched ? configuration : nothing,
        target_id=numeric_target_matched ? target_descriptor.target_id : nothing,
        target_value,
        residual_linf,
        configuration_distance=nearest_distance,
        diagnostic=evaluation_error,
    )
end

function _run_solver_attempt(
    problem::DirectAnalyticProblem,
    case::SolverExperimentCase,
    variant::SolverVariant,
    start_index::Int,
    timing_phase::Symbol,
    tolerances::SolverExperimentTolerances,
    clock_ns,
)
    start = Tuple(problem.saved_starts[:, start_index])
    outcome = nothing
    exception = nothing
    oracle = _solver_case_oracle(case._evaluate)
    oracle === nothing && error("solver experiment oracle was released before its attempt")
    oracle.evaluation_count[] = 0
    oracle.budget_exhausted[] = false
    started = clock_ns()
    try
        outcome = variant.run(case, collect(start))
        outcome isa SolverAttemptOutcome || throw(
            ArgumentError("solver variant must return SolverAttemptOutcome"),
        )
    catch error
        exception = sprint(showerror, error)
    end
    stopped = clock_ns()
    observed_evaluations = oracle.evaluation_count[]
    budget_exhausted = oracle.budget_exhausted[]
    stopped >= started || throw(ArgumentError("experiment clock moved backwards"))
    wall_seconds = Float64(stopped - started) / 1.0e9
    if outcome === nothing
        outcome = SolverAttemptOutcome(
            nothing;
            status=budget_exhausted ? "evaluation_budget_exhausted" : "exception",
            diagnostic=exception,
        )
    end
    score = _score_endpoint(problem, outcome.endpoint, tolerances)
    assessor_score = _score_endpoint(
        problem,
        outcome.endpoint,
        _SOLVER_EXPERIMENT_ASSESSOR_TOLERANCES,
    )
    diagnostic = outcome.diagnostic === nothing ? score.diagnostic : outcome.diagnostic
    return SolverExperimentAttempt(
        variant.name,
        problem.instance_id,
        problem.family_id,
        replay_checksum(problem),
        start_index,
        start,
        timing_phase,
        outcome.endpoint,
        outcome.status,
        outcome.reported_converged,
        outcome.reported_accepted,
        score.canonical_valid,
        score.configuration_matched,
        score.numeric_target_matched,
        score.gold_matched,
        score.false_candidate,
        score.false_target,
        score.target_ambiguous,
        score.configuration,
        score.target_id,
        score.target_value,
        score.residual_linf,
        score.configuration_distance,
        assessor_score.canonical_valid,
        assessor_score.configuration_matched,
        assessor_score.numeric_target_matched,
        assessor_score.gold_matched,
        assessor_score.target_ambiguous,
        assessor_score.configuration,
        assessor_score.target_id,
        observed_evaluations,
        outcome.evaluations,
        observed_evaluations != outcome.evaluations,
        observed_evaluations - outcome.evaluations,
        outcome.iterations,
        budget_exhausted,
        wall_seconds,
        diagnostic,
        exception,
    )
end

function _selected_attempts(
    problem::DirectAnalyticProblem,
    variant::SolverVariant,
    attempts,
    prefix::Int,
)
    return filter(
        attempt -> attempt.variant == variant.name &&
                   attempt.instance_id == problem.instance_id &&
                   attempt.start_index <= prefix,
        attempts,
    )
end

_reported_accepted_safe(attempt::SolverExperimentAttempt) =
    !attempt.reported_accepted ||
    (attempt.canonical_valid && attempt.gold_matched && !attempt.target_ambiguous)

function _reported_acceptance_metrics(selected, target_count::Int)
    accepted_targets = Set(
        attempt.matched_target_id for attempt in selected if
        attempt.reported_accepted && attempt.gold_matched
    )
    return (
        targets_found=length(accepted_targets),
        target_recall=length(accepted_targets) / target_count,
        safe_all_targets=length(accepted_targets) == target_count &&
                         all(_reported_accepted_safe, selected),
        canonical_invalid=count(
            attempt -> attempt.reported_accepted && !attempt.canonical_valid,
            selected,
        ),
        gold_inconsistent=count(
            attempt -> attempt.reported_accepted && !attempt.gold_matched,
            selected,
        ),
        numeric_target_only=count(
            attempt -> attempt.reported_accepted &&
                       attempt.numeric_target_matched && !attempt.gold_matched,
            selected,
        ),
        ambiguous=count(
            attempt -> attempt.reported_accepted && attempt.target_ambiguous,
            selected,
        ),
    )
end

function _assessor_metrics(selected, target_count::Int)
    qualified_targets = Set(
        attempt.assessor_matched_target_id for attempt in selected if
        attempt.assessor_qualified && attempt.assessor_gold_matched
    )
    gold_inconsistent = count(
        attempt -> attempt.assessor_qualified &&
                   (!attempt.assessor_gold_matched || attempt.assessor_target_ambiguous),
        selected,
    )
    all_targets = length(qualified_targets) == target_count
    return (
        qualified=count(attempt -> attempt.assessor_qualified, selected),
        targets_found=length(qualified_targets),
        target_recall=length(qualified_targets) / target_count,
        gold_inconsistent,
        all_targets,
        safe_all_targets=all_targets && gold_inconsistent == 0,
    )
end

function _suffix_stable_evaluations_to_lab_safe_full(
    problem::DirectAnalyticProblem,
    variant::SolverVariant,
    attempts,
    maximum_start::Int,
)
    sequence = _selected_attempts(problem, variant, attempts, maximum_start)
    length(sequence) == maximum_start || error("solver experiment sequence is incomplete")
    sort!(sequence; by=attempt -> attempt.start_index)
    target_count = length(problem.gold_targets)
    for start_index in eachindex(sequence)
        prefix_attempts = @view sequence[1:start_index]
        metrics = _reported_acceptance_metrics(prefix_attempts, target_count)
        metrics.safe_all_targets || continue
        all(_reported_accepted_safe, @view(sequence[start_index + 1:end])) || continue
        return sum(attempt.evaluations for attempt in prefix_attempts)
    end
    return nothing
end

function _prefix_summary(
    problem::DirectAnalyticProblem,
    variant::SolverVariant,
    attempts,
    prefix::Int,
    suffix_stable_evaluations::Union{Nothing,Int},
)
    selected = _selected_attempts(problem, variant, attempts, prefix)
    length(selected) == prefix || error("solver experiment prefix is incomplete")
    matched_configurations = filter(attempt -> attempt.configuration_matched, selected)
    matched_targets = filter(attempt -> attempt.gold_matched, selected)
    configurations = Set(
        attempt.matched_configuration for attempt in matched_configurations
    )
    targets = Set(attempt.matched_target_id for attempt in matched_targets)
    configuration_count = size(problem.gold_configurations, 2)
    target_count = length(problem.gold_targets)
    reported = _reported_acceptance_metrics(selected, target_count)
    assessor = _assessor_metrics(selected, target_count)
    statuses = sort!(unique(attempt.status for attempt in selected))
    status_counts = Tuple(
        status => count(attempt -> attempt.status == status, selected) for status in statuses
    )
    return SolverExperimentPrefix(
        variant.name,
        problem.instance_id,
        problem.family_id,
        prefix,
        configuration_count,
        length(configurations),
        target_count,
        length(targets),
        length(configurations) / configuration_count,
        length(targets) / target_count,
        length(targets) == target_count,
        count(attempt -> attempt.reported_converged, selected),
        count(attempt -> attempt.reported_accepted, selected),
        length(matched_targets),
        count(attempt -> attempt.false_candidate, selected),
        count(attempt -> attempt.false_target, selected),
        count(attempt -> attempt.target_ambiguous, selected),
        count(
            attempt -> attempt.numeric_target_matched && !attempt.gold_matched,
            selected,
        ),
        count(attempt -> attempt.budget_exhausted, selected),
        length(matched_configurations) - length(configurations),
        length(matched_targets) - length(targets),
        count(attempt -> attempt.exception !== nothing, selected),
        sum(attempt.evaluations for attempt in selected),
        sum(attempt.iterations for attempt in selected),
        sum(attempt.wall_seconds for attempt in selected),
        sum(
            (attempt.wall_seconds for attempt in selected if
             attempt.timing_phase === :warm);
            init=0.0,
        ),
        status_counts,
        reported.targets_found,
        reported.target_recall,
        reported.safe_all_targets,
        reported.canonical_invalid,
        reported.gold_inconsistent,
        reported.numeric_target_only,
        reported.ambiguous,
        assessor.qualified,
        assessor.targets_found,
        assessor.target_recall,
        assessor.gold_inconsistent,
        assessor.all_targets,
        assessor.safe_all_targets,
        count(attempt -> attempt.status == "LOCAL_MAX_EVALUATIONS", selected),
        count(attempt -> attempt.budget_exhausted, selected),
        count(attempt -> attempt.evaluation_count_mismatch, selected),
        suffix_stable_evaluations,
    )
end

"""
Run paired, saved-start solver variants and score them after the fact.

Variants receive only a `SolverExperimentCase`; Gold truth and benchmark
identity remain in the runner. Wall time is diagnostic. Evaluation/action
counts observed at the truth-blind callback are the primary matched-budget
comparison. `evaluation_limit` is enforced by that callback for every attempt;
a variant's self-reported count is retained only as a diagnostic. Likewise,
`reported_accepted` is a local-solver screening proxy, not production answer
promotion. The fixed assessor replays every endpoint independently of both
solver status and acceptance.
"""
function run_solver_experiment(
    problems::AbstractVector{<:DirectAnalyticProblem},
    variants::AbstractVector{<:SolverVariant};
    prefixes=(8,),
    tolerances::SolverExperimentTolerances=SolverExperimentTolerances(),
    evaluation_limit::Integer=600,
    clock_ns=time_ns,
)
    isempty(problems) && throw(ArgumentError("solver experiment needs at least one problem"))
    isempty(variants) && throw(ArgumentError("solver experiment needs at least one variant"))
    evaluation_limit > 0 || throw(ArgumentError("evaluation_limit must be positive"))
    problem_ids = [problem.instance_id for problem in problems]
    allunique(problem_ids) || throw(ArgumentError("solver experiment instance IDs must be unique"))
    variant_names = [variant.name for variant in variants]
    allunique(variant_names) || throw(ArgumentError("solver experiment variant names must be unique"))
    requested_prefixes = Int[prefixes...]
    !isempty(requested_prefixes) && all(>(0), requested_prefixes) ||
        throw(ArgumentError("solver experiment prefixes must be positive"))
    issorted(requested_prefixes) && allunique(requested_prefixes) ||
        throw(ArgumentError("solver experiment prefixes must be sorted and unique"))
    maximum_prefix = last(requested_prefixes)
    for problem in problems
        verify_replay_material(problem) || error("benchmark replay material failed validation")
        size(problem.saved_starts, 2) >= maximum_prefix || throw(
            ArgumentError("problem $(problem.instance_id) has too few saved starts"),
        )
    end

    attempts = SolverExperimentAttempt[]
    first_attempt = Dict(variant.name => true for variant in variants)
    for variant in variants, problem in problems
        case = _truth_blind_case(problem, Int(evaluation_limit))
        try
            for start_index in 1:maximum_prefix
                phase = first_attempt[variant.name] ? :cold_first_use : :warm
                push!(
                    attempts,
                    _run_solver_attempt(
                        problem,
                        case,
                        variant,
                        start_index,
                        phase,
                        tolerances,
                        clock_ns,
                    ),
                )
                first_attempt[variant.name] = false
            end
        finally
            _release_solver_case_oracle!(case._evaluate)
        end
    end
    suffix_stable_work = Dict(
        (variant.name, problem.instance_id) =>
            _suffix_stable_evaluations_to_lab_safe_full(
                problem,
                variant,
                attempts,
                maximum_prefix,
            ) for variant in variants for problem in problems
    )
    summaries = SolverExperimentPrefix[
        _prefix_summary(
            problem,
            variant,
            attempts,
            prefix,
            suffix_stable_work[(variant.name, problem.instance_id)],
        ) for
        variant in variants for problem in problems for prefix in requested_prefixes
    ]
    manifest = Tuple((
        instance_id=problem.instance_id,
        family_id=problem.family_id,
        replay_checksum=replay_checksum(problem),
        saved_starts=size(problem.saved_starts, 2),
        configurations=size(problem.gold_configurations, 2),
        targets=length(problem.gold_targets),
    ) for problem in problems)
    return SolverExperimentRun(
        Tuple(attempts),
        Tuple(summaries),
        Tuple(requested_prefixes),
        Tuple(variant_names),
        Tuple((name=variant.name, configuration=variant.configuration) for variant in variants),
        manifest,
        tolerances,
        Int(evaluation_limit),
    )
end

_document_float(value::Union{Nothing,Float64}) =
    value === nothing || !isfinite(value) ? nothing : value

function _attempt_document(attempt::SolverExperimentAttempt)
    return Dict{String,Any}(
        "assessor_configuration_matched" => attempt.assessor_configuration_matched,
        "assessor_gold_matched" => attempt.assessor_gold_matched,
        "assessor_matched_configuration" => attempt.assessor_matched_configuration,
        "assessor_matched_target_id" => attempt.assessor_matched_target_id,
        "assessor_numeric_target_matched" => attempt.assessor_numeric_target_matched,
        "assessor_qualified" => attempt.assessor_qualified,
        "assessor_target_ambiguous" => attempt.assessor_target_ambiguous,
        "canonical_valid" => attempt.canonical_valid,
        "budget_exhausted" => attempt.budget_exhausted,
        "configuration_matched" => attempt.configuration_matched,
        "diagnostic" => attempt.diagnostic,
        "endpoint" => attempt.endpoint === nothing ? nothing : [
            isfinite(value) ? value : nothing for value in attempt.endpoint
        ],
        "evaluations" => attempt.evaluations,
        "evaluation_count_difference" => attempt.evaluation_count_difference,
        "evaluation_count_mismatch" => attempt.evaluation_count_mismatch,
        "observed_minus_reported_evaluations" => attempt.evaluation_count_difference,
        "exception" => attempt.exception,
        "false_candidate" => attempt.false_candidate,
        "false_target" => attempt.false_target,
        "family_id" => attempt.family_id,
        "gold_matched" => attempt.gold_matched,
        "instance_id" => attempt.instance_id,
        "iterations" => attempt.iterations,
        "matched_configuration" => attempt.matched_configuration,
        "matched_target_id" => attempt.matched_target_id,
        "normalized_configuration_distance" =>
            _document_float(attempt.normalized_configuration_distance),
        "replay_checksum" => attempt.replay_checksum,
        "reported_accepted" => attempt.reported_accepted,
        "reported_converged" => attempt.reported_converged,
        "reported_evaluations" => attempt.reported_evaluations,
        "observed_evaluations" => attempt.evaluations,
        "scaled_residual_linf" => _document_float(attempt.scaled_residual_linf),
        "start" => collect(attempt.start),
        "start_index" => attempt.start_index,
        "status" => attempt.status,
        "target_value" => _document_float(attempt.target_value),
        "target_ambiguous" => attempt.target_ambiguous,
        "numeric_target_matched" => attempt.numeric_target_matched,
        "timing_phase" => String(attempt.timing_phase),
        "variant" => attempt.variant,
        "wall_seconds" => attempt.wall_seconds,
    )
end

function _prefix_document(prefix::SolverExperimentPrefix)
    return Dict{String,Any}(
        "all_targets" => prefix.all_targets,
        "assessor_all_targets" => prefix.assessor_all_targets,
        "assessor_qualified" => prefix.assessor_qualified,
        "assessor_qualified_gold_inconsistent" =>
            prefix.assessor_qualified_gold_inconsistent,
        "assessor_qualified_target_recall" => prefix.assessor_qualified_target_recall,
        "assessor_qualified_targets_found" => prefix.assessor_qualified_targets_found,
        "assessor_safe_all_targets" => prefix.assessor_safe_all_targets,
        "configuration_count" => prefix.configuration_count,
        "configuration_recall" => prefix.configuration_recall,
        "configurations_found" => prefix.configurations_found,
        "duplicate_configuration_hits" => prefix.duplicate_configuration_hits,
        "duplicate_target_hits" => prefix.duplicate_target_hits,
        "evaluations" => prefix.evaluations,
        "evaluation_count_mismatches" => prefix.evaluation_count_mismatches,
        "exceptions" => prefix.exceptions,
        "false_candidates" => prefix.false_candidates,
        "false_targets" => prefix.false_targets,
        "ambiguous_targets" => prefix.ambiguous_targets,
        "budget_exhausted" => prefix.budget_exhausted,
        "numeric_target_only_hits" => prefix.numeric_target_only_hits,
        "family_id" => prefix.family_id,
        "gold_matched" => prefix.gold_matched,
        "instance_id" => prefix.instance_id,
        "iterations" => prefix.iterations,
        "lab_safe_all_targets" => prefix.lab_safe_all_targets,
        "local_max_evaluations" => prefix.local_max_evaluations,
        "prefix" => prefix.prefix,
        "reported_accepted" => prefix.reported_accepted,
        "reported_accepted_ambiguous" => prefix.reported_accepted_ambiguous,
        "reported_accepted_canonical_invalid" =>
            prefix.reported_accepted_canonical_invalid,
        "reported_accepted_gold_inconsistent" =>
            prefix.reported_accepted_gold_inconsistent,
        "reported_accepted_numeric_target_only" =>
            prefix.reported_accepted_numeric_target_only,
        "reported_accepted_target_recall" => prefix.reported_accepted_target_recall,
        "reported_accepted_targets_found" => prefix.reported_accepted_targets_found,
        "reported_converged" => prefix.reported_converged,
        "runner_budget_exhausted" => prefix.runner_budget_exhausted,
        "status_counts" => Dict(String(status) => count for (status, count) in prefix.status_counts),
        "target_count" => prefix.target_count,
        "target_recall" => prefix.target_recall,
        "targets_found" => prefix.targets_found,
        "suffix_stable_evaluations_to_lab_safe_full" =>
            prefix.suffix_stable_evaluations_to_lab_safe_full,
        "variant" => prefix.variant,
        "wall_seconds" => prefix.wall_seconds,
        "warm_wall_seconds" => prefix.warm_wall_seconds,
    )
end

_configuration_value(value::Symbol) = String(value)
_configuration_value(value) = value

function _variant_document(entry)
    return Dict{String,Any}(
        "configuration" => Dict{String,Any}(
            String(key) => _configuration_value(value) for
            (key, value) in pairs(entry.configuration)
        ),
        "name" => entry.name,
    )
end

"""Convert a run to a JSON-compatible document without adding a JSON dependency."""
function solver_experiment_document(run::SolverExperimentRun)
    return Dict{String,Any}(
        "assessor_manifest" => Dict{String,Any}(
            "configuration_tolerance" =>
                _SOLVER_EXPERIMENT_ASSESSOR_TOLERANCES.configuration,
            "qualification_predicate" =>
                "endpoint_present_finite_in_bounds_semantics_valid_scaled_residual_linf",
            "coverage_predicate" =>
                "qualified_unique_gold_consistent_target_id",
            "residual_linf_tolerance" =>
                _SOLVER_EXPERIMENT_ASSESSOR_TOLERANCES.residual,
            "safety_predicate" =>
                "all_qualified_endpoints_gold_consistent_and_unambiguous",
            "target_tolerance" => _SOLVER_EXPERIMENT_ASSESSOR_TOLERANCES.target,
        ),
        "attempts" => Any[_attempt_document(attempt) for attempt in run.attempts],
        "evaluation_limit" => run.evaluation_limit,
        "package_version" => string(PACKAGE_VERSION),
        "prefixes" => collect(run.requested_prefixes),
        "problem_manifest" => Any[
            Dict{String,Any}(String(key) => value for (key, value) in pairs(entry)) for
            entry in run.problem_manifest
        ],
        "schema" => SOLVER_EXPERIMENT_SCHEMA_VERSION,
        "summaries" => Any[_prefix_document(prefix) for prefix in run.prefixes],
        "tolerances" => Dict{String,Any}(
            "configuration" => run.tolerances.configuration,
            "residual" => run.tolerances.residual,
            "target" => run.tolerances.target,
        ),
        "variant_manifest" => Any[_variant_document(entry) for entry in run.variant_manifest],
        "variants" => collect(run.variant_names),
    )
end
