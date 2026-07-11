using ExperimentDisc001
using GeoTargetCore

function usage()
    return """
    Usage: julia --project=research/experiments/EXP-DISC-001 \\
      research/experiments/EXP-DISC-001/run_t0.jl [options]

      --preflight-only          Validate A3 authority only (default)
      --execute-development     Reserved; fail-closed until pipeline audit
      --freeze=PATH             Champion freeze record
      --output=PATH             Future development result path
      --proposal-root=PATH      Future maximum-prefix artifact directory
      --shard-index=N           One-based case shard index
      --shard-count=N           Number of independent case shards
      --help                    Show this message

    The command checks A3 before corpus loading, proposal generation, or output
    creation. Run each shard with one Julia/BLAS/OMP/MKL thread.
    """
end

function main(arguments=ARGS)
    options = parse_runner_arguments(arguments)
    if options === nothing
        print(usage())
        return nothing
    end
    contract = run_preflight(options)
    println(GeoTargetCore.canonical_json(contract))
    return contract
end

if abspath(PROGRAM_FILE) == abspath(@__FILE__())
    main()
end
