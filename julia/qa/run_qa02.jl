#!/usr/bin/env julia

include(joinpath(@__DIR__, "QA02Fuzz.jl"))
using .QA02Fuzz
using GeoTargetCore

function _parse_positive(value::AbstractString, flag::AbstractString)
    parsed = tryparse(Int, value)
    parsed !== nothing && parsed > 0 || throw(ArgumentError("$flag requires a positive integer"))
    return parsed
end

function _arguments(args)
    options = Dict{Symbol,Any}(
        :graph_evaluations => 200,
        :solve_executions => 20,
        :require_nightly_minimum => false,
        :skip_isolation => false,
        :checksum_only => false,
        :ambient_precision => nothing,
        :output => nothing,
    )
    index = 1
    while index <= length(args)
        argument = args[index]
        if argument == "--require-nightly-minimum"
            options[:require_nightly_minimum] = true
        elseif argument == "--skip-isolation"
            options[:skip_isolation] = true
        elseif argument == "--checksum-only"
            options[:checksum_only] = true
        elseif argument in (
            "--graph-evaluations",
            "--solve-executions",
            "--ambient-precision",
            "--output",
        )
            index < length(args) || throw(ArgumentError("$argument requires a value"))
            index += 1
            value = args[index]
            if argument == "--graph-evaluations"
                options[:graph_evaluations] = _parse_positive(value, argument)
            elseif argument == "--solve-executions"
                options[:solve_executions] = _parse_positive(value, argument)
            elseif argument == "--ambient-precision"
                options[:ambient_precision] = _parse_positive(value, argument)
            else
                isempty(strip(value)) && throw(ArgumentError("--output cannot be blank"))
                options[:output] = abspath(value)
            end
        else
            throw(ArgumentError("unknown argument: $argument"))
        end
        index += 1
    end
    return options
end

function _write_summary(path::AbstractString, source::String)
    mkpath(dirname(path))
    temporary = string(path, ".tmp-", getpid(), '-', time_ns())
    try
        open(temporary, "w") do io
            write(io, source)
            write(io, '\n')
        end
        mv(temporary, path; force=true)
    finally
        isfile(temporary) && rm(temporary; force=true)
    end
    return path
end

function _child_checksum(threads::Int, ambient_precision::Int)
    project_file = Base.active_project()
    project_file === nothing && throw(ArgumentError("QA-02 isolation requires an active project"))
    project = dirname(project_file)
    command = `$(Base.julia_cmd()) --startup-file=no --history-file=no --project=$project $(@__FILE__) --graph-evaluations 40 --solve-executions 8 --ambient-precision $ambient_precision --skip-isolation --checksum-only`
    environment = copy(ENV)
    environment["JULIA_NUM_THREADS"] = string(threads)
    environment["OPENBLAS_NUM_THREADS"] = "1"
    return strip(read(setenv(command, environment), String))
end

function _isolation_check()
    single = _child_checksum(1, 96)
    threaded = _child_checksum(2, 384)
    single == threaded || throw(
        QA02Failure(
            :isolation,
            0,
            UInt64(0),
            :thread_precision_interference,
            "isolated thread/ambient-precision runs produced different stable checksums: $single != $threaded",
        ),
    )
    return single
end

function _failure_document(error)
    if error isa QA02Failure
        return Dict{String,Any}(
            "case_index" => error.case_index,
            "detail" => error.detail,
            "error_type" => string(typeof(error)),
            "invariant" => String(error.invariant),
            "phase" => String(error.phase),
            "schema" => "geotarget.qa02-fuzz-failure/v1",
            "seed" => string(error.seed),
        )
    end
    return Dict{String,Any}(
        "detail" => sprint(showerror, error),
        "error_type" => string(typeof(error)),
        "invariant" => "runner_exception",
        "phase" => "runner",
        "schema" => "geotarget.qa02-fuzz-failure/v1",
    )
end

function main(args=ARGS)
    options = _arguments(args)
    ambient = options[:ambient_precision]
    ambient === nothing || setprecision(BigFloat, ambient)
    started = time()
    try
        summary = run_suite(
            graph_evaluations=options[:graph_evaluations],
            solve_executions=options[:solve_executions],
            require_nightly_minimum=options[:require_nightly_minimum],
        )
        isolation_started = time()
        if !options[:skip_isolation]
            summary["isolation_checksum"] = _isolation_check()
        end
        isolation_seconds = time() - isolation_started
        source = canonical_json(summary)
        options[:output] === nothing || _write_summary(options[:output], source)
        if options[:checksum_only]
            println(summary["run_checksum"])
        else
            println(source)
        end
        println(
            stderr,
            "QA02 TIMING total_seconds=$(round(time() - started; digits=3)) " *
            "isolation_seconds=$(round(isolation_seconds; digits=3)) " *
            "graph_evaluations=$(options[:graph_evaluations]) " *
            "solve_executions=$(options[:solve_executions])",
        )
        return 0
    catch error
        println(stderr, canonical_json(_failure_document(error)))
        Base.display_error(Base.catch_stack())
        return 1
    end
end

exit(main())
