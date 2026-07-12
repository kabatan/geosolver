const CASE_TOTAL_CALLBACK_THRESHOLDS = (600, 1_200, 2_400, 4_800)
const T0_RECIPE = (
    (
        source="benchmarks/generated/m0-analytic-seed-manifest.json",
        case_id="M0-ANALYTIC-006",
        source_index=6,
        role="close-root distinct-target MultiRoot development control",
    ),
    (
        source="benchmarks/generated/m0-analytic-seed-manifest.json",
        case_id="M0-ANALYTIC-007",
        source_index=7,
        role="well-separated target-collision MultiRoot development control",
    ),
    (
        source="research/experiments/EXP-LOCAL-004/t2-input-manifest.json",
        case_id="MULTIROOT-WARPED-development-01",
        source_index=31,
        role="well-separated target-collision control",
    ),
    (
        source="research/experiments/EXP-LOCAL-004/t2-input-manifest.json",
        case_id="MULTIROOT-WARPED-development-02",
        source_index=32,
        role="1e-3 close-root target-collision control",
    ),
    (
        source="research/experiments/EXP-LOCAL-004/t2-input-manifest.json",
        case_id="MULTIROOT-WARPED-development-03",
        source_index=33,
        role="1e-6 close-root target-collision control",
    ),
    (
        source="research/experiments/EXP-LOCAL-004/t2-input-manifest.json",
        case_id="MULTIROOT-WARPED-development-05",
        source_index=35,
        role="1e-6 close-root target-collision condition control",
    ),
)

struct RunnerOptions
    freeze_path::String
    output::String
    proposal_root::String
    shard_index::Int
    shard_count::Int
    preflight_only::Bool
end

function RunnerOptions(;
    freeze_path::AbstractString=DEFAULT_CHAMPION_FREEZE_PATH,
    output::AbstractString=joinpath(EXPERIMENT_ROOT, "dirty-t0-result.json"),
    proposal_root::AbstractString=joinpath(EXPERIMENT_ROOT, "materialized", "development"),
    shard_index::Integer=1,
    shard_count::Integer=1,
    preflight_only::Bool=true,
)
    shard_count > 0 || throw(ArgumentError("shard_count must be positive"))
    1 <= shard_index <= shard_count || throw(
        ArgumentError("shard_index must lie in 1:shard_count"),
    )
    return RunnerOptions(
        abspath(freeze_path),
        abspath(output),
        abspath(proposal_root),
        Int(shard_index),
        Int(shard_count),
        preflight_only,
    )
end

function shard_ordinals(total::Integer, shard_index::Integer, shard_count::Integer)
    total >= 0 || throw(ArgumentError("total must be nonnegative"))
    shard_count > 0 || throw(ArgumentError("shard_count must be positive"))
    1 <= shard_index <= shard_count || throw(
        ArgumentError("shard_index must lie in 1:shard_count"),
    )
    return Tuple(index for index in 1:Int(total) if mod(index - 1, shard_count) + 1 == shard_index)
end

function parse_runner_arguments(arguments=ARGS)
    freeze_path = DEFAULT_CHAMPION_FREEZE_PATH
    output = joinpath(EXPERIMENT_ROOT, "dirty-t0-result.json")
    proposal_root = joinpath(EXPERIMENT_ROOT, "materialized", "development")
    shard_index = 1
    shard_count = 1
    preflight_only = true
    for argument in arguments
        if startswith(argument, "--freeze=")
            freeze_path = argument[length("--freeze=") + 1:end]
        elseif startswith(argument, "--output=")
            output = argument[length("--output=") + 1:end]
        elseif startswith(argument, "--proposal-root=")
            proposal_root = argument[length("--proposal-root=") + 1:end]
        elseif startswith(argument, "--shard-index=")
            shard_index = parse(Int, argument[length("--shard-index=") + 1:end])
        elseif startswith(argument, "--shard-count=")
            shard_count = parse(Int, argument[length("--shard-count=") + 1:end])
        elseif argument == "--execute-development"
            preflight_only = false
        elseif argument == "--preflight-only"
            preflight_only = true
        elseif argument == "--help"
            return nothing
        else
            throw(ArgumentError("unknown EXP-DISC-001 runner option: $argument"))
        end
    end
    isempty(freeze_path) && throw(ArgumentError("freeze path must be nonempty"))
    isempty(output) && throw(ArgumentError("output path must be nonempty"))
    isempty(proposal_root) && throw(ArgumentError("proposal root must be nonempty"))
    return RunnerOptions(
        ; freeze_path,
        output,
        proposal_root,
        shard_index,
        shard_count,
        preflight_only,
    )
end

function _one_thread_contract()
    julia_threads = Threads.nthreads()
    blas_threads = BLAS.get_num_threads()
    env = Dict(
        name => get(ENV, name, "unset") for
        name in ("JULIA_NUM_THREADS", "OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS")
    )
    julia_threads == 1 || throw(
        DiscoveryGateError(
            :thread_contract_violation,
            "each case process must use one Julia thread, observed $julia_threads",
        ),
    )
    blas_threads == 1 || throw(
        DiscoveryGateError(
            :thread_contract_violation,
            "each case process must use one BLAS thread, observed $blas_threads",
        ),
    )
    for name in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS")
        get(env, name, "unset") in ("1", "unset") || throw(
            DiscoveryGateError(
                :thread_contract_violation,
                "$name must be 1 (or unset when the observed library thread count is one)",
            ),
        )
    end
    return Dict{String,Any}(
        "blas_threads" => blas_threads,
        "environment" => env,
        "julia_threads" => julia_threads,
    )
end

function _runner_contract_document(options::RunnerOptions, authority::_MaterializationAuthority)
    methods = (
        D0_IID_ALL,
        D1_SOBOL_ALL,
        D_HALTON_ALL,
        D_CURRENT_COUNTER_HALTON,
        D2O_OWEN_ALL,
        D2M_MATOUSEK_ALL,
        D3_OWEN_MIXED,
    )
    return Dict{String,Any}(
        "assessor_only_fields" => [
            "family_id",
            "instance_id",
            "Gold configurations",
            "Gold targets",
        ],
        "callback_thresholds" => collect(CASE_TOTAL_CALLBACK_THRESHOLDS),
        "case_ordinals" => collect(shard_ordinals(
            length(T0_RECIPE),
            options.shard_index,
            options.shard_count,
        )),
        "confirmation" => Dict(
            "coordinate_tolerance" => "1e-100",
            "primary_bits" => 512,
            "reference_bits" => 768,
            "residual_tolerance" => "1e-100",
            "target_tolerance" => "1e-100",
        ),
        "freeze_sha256" => authority.freeze_sha256,
        "metrics" => [
            "full-target",
            "qualified-recall",
            "safe-full",
            "duplicate-configuration",
            "duplicate-target",
            "ambiguity",
            "false-target",
            "IID-bounded-gap",
            "IID-starvation",
        ],
        "partition" => "development",
        "prefixes" => collect(CHECKPOINT_COLUMNS),
        "proposal_only_difference" => true,
        "shard_count" => options.shard_count,
        "shard_index" => options.shard_index,
        "stream_contracts" => [stream_contract(method) for method in methods],
        "truth_visible_to_proposal_runtime" => false,
        "weak_direction_enabled" => false,
    )
end

"""
Perform the only operation currently authorized before the A3 champion record
exists. The authority check happens before corpus loading, proposal generation,
directory creation or result writing.
"""
function run_preflight(options::RunnerOptions)
    authority = materialization_preflight(options.freeze_path)
    thread_contract = _one_thread_contract()
    contract = _runner_contract_document(options, authority)
    contract["thread_contract"] = thread_contract
    if !options.preflight_only
        throw(
            DiscoveryGateError(
                :development_execution_not_enabled,
                "this checkpoint implements the audited materialization seam only; " *
                "enable outcome execution after the champion freeze and pipeline audit",
            ),
        )
    end
    return contract
end
