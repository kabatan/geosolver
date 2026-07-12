using Test

include(joinpath(@__DIR__, "..", "run_t0.jl"))

@testset "cross-language candidate digest and CLI helpers" begin
    payload = Dict{String,Any}(
        "large" => 1.0e300,
        "negative_zero" => -0.0,
        "nested" => Any[true, 7, "plain", Dict("z" => 0.0)],
        "small" => 1.0e-6,
        "subnormal" => nextfloat(0.0),
    )
    @test _candidate_digest(payload) ==
          "da3ee560375576c5324fd68a358c491c4ea368f25c8094b13b931176b4ca41ca"
    @test _candidate_digest(Dict(reverse(collect(payload)))) == _candidate_digest(payload)
    changed = copy(payload)
    changed["negative_zero"] = 0.0
    @test _candidate_digest(changed) != _candidate_digest(payload)
    @test _candidate_digest(Dict("value" => 1.0)) !=
          _candidate_digest(Dict("value" => "float64_bits:3ff0000000000000"))
    @test _candidate_digest(Dict("value" => 7)) !=
          _candidate_digest(Dict("value" => "7"))

    parsed = _arguments([
        "--case-index", "7",
        "--output", "/tmp/exp-local-015.json",
        "--registration", "/tmp/registration.json",
    ])
    @test parsed.case_index == 7
    @test parsed.output == "/tmp/exp-local-015.json"
    @test parsed.registration == "/tmp/registration.json"
    @test _git_output("rev-parse", "--show-toplevel") == realpath(ROOT)
    runtime = _runtime_contract()
    @test runtime["julia_version"] == string(VERSION)
    @test runtime["active_project_path"] ==
          "research/experiments/EXP-LOCAL-002/Project.toml"
    @test all(value == 1 for value in values(_formal_thread_environment()))

    record = FIX.make_clustered_fixture(2, 4)
    candidate = FIX.candidate_view(record)
    endpoint = candidate.starts[1]
    shared_observed = Dict{String,Int}()
    prefilter = LAB.acquire_shared_prefilter(
        candidate,
        endpoint;
        observe_callback=bits -> _observe_precision!(shared_observed, bits),
    )
    row = _row(
        LAB.WEAK_ARM,
        1,
        _candidate_input(candidate, prefilter),
        prefilter,
        shared_observed,
        record,
        endpoint,
        observer -> LAB.run_weak_arm(
            candidate,
            prefilter;
            lane=:weak,
            observe_callback=observer,
        ),
    )
    @test row["observed_precision_counts"] == Dict("float64" => 8)
    @test row["observed_callback_count"] == row["reported_callback_count"] == 8
    @test row["observed_weighted_work"] == row["reported_weighted_work"] == 8
    @test row["shared_observed_precision_counts"] == Dict("float64" => 9)
    @test row["shared_observed_callback_count"] == row["shared_callback_count"] == 9
end
