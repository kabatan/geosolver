"""Family-disjoint synthetic fixture used only to remove JIT/order asymmetry."""
function _s4_warmup_fixture(nullity::Int)
    nullity in (1, 2, 4) || throw(ArgumentError("unsupported S4 warm-up nullity"))
    dimension = nullity + 1
    function residual(z::AbstractVector{T}) where {T<:Real}
        length(z) == dimension || throw(DimensionMismatch("S4 warm-up residual"))
        return T[z[end], (z[index]^2 for index in 1:nullity)...]
    end
    function target(z::AbstractVector{T}) where {T<:Real}
        length(z) == dimension || throw(DimensionMismatch("S4 warm-up target"))
        return sum(T(index) * z[index] / T(32) for index in eachindex(z))
    end
    function jacobian(z::AbstractVector{T}) where {T<:Real}
        result = zeros(T, dimension, dimension)
        result[1, end] = one(T)
        for index in 1:nullity
            result[index + 1, index] = T(2) * z[index]
        end
        return result
    end
    function second_directional(
        z::AbstractVector{T},
        first,
        second,
    ) where {T<:Real}
        return T[
            0,
            (T(2) * first[index] * second[index] for index in 1:nullity)...,
        ]
    end
    oracle = EndpointOracle(
        "s4-warmup-k$nullity",
        "S4-WARMUP-DISJOINT",
        "s4-warmup-k$nullity",
        dimension,
        dimension,
        :C2,
        residual,
        target,
        nothing,
    )
    endpoint = Float64[
        (isodd(index) ? 1 : -1) * 2.0^(-65 - index) for index in 1:nullity
    ]
    push!(endpoint, 2.0^-80)
    baseline_input = CandidateInput(oracle, endpoint)
    return (
        baseline=baseline_input,
        mechanism=s4_candidate_input(baseline_input),
        analytic=S4AnalyticControlOracle(jacobian, second_directional),
        nullity=nullity,
    )
end

function _run_s4_family_disjoint_warmup!(
    s4_options::ExperimentOptions,
    baseline_options::ExperimentOptions;
    clock_ns=time_ns,
)
    orders = (
        ("S1-AP-LMQR", "S4-C2-NULLSPACE-TWO-STEP", "S4-ANALYTIC-TWO-STEP-CONTROL"),
        ("S4-C2-NULLSPACE-TWO-STEP", "S4-ANALYTIC-TWO-STEP-CONTROL", "S1-AP-LMQR"),
        ("S4-ANALYTIC-TWO-STEP-CONTROL", "S1-AP-LMQR", "S4-C2-NULLSPACE-TWO-STEP"),
    )
    documents = Any[]
    for (fixture_index, nullity) in enumerate((1, 2, 4))
        fixture = _s4_warmup_fixture(nullity)
        statuses = Dict{String,String}()
        for variant in orders[fixture_index]
            outcome = if variant == "S1-AP-LMQR"
                run_s1(
                    fixture.baseline;
                    options=baseline_options,
                    derivative_mode=:dense,
                    clock_ns,
                )
            elseif variant == "S4-C2-NULLSPACE-TWO-STEP"
                run_s4(fixture.mechanism; options=s4_options, clock_ns).core
            else
                run_s4_analytic_control(
                    fixture.mechanism,
                    fixture.analytic;
                    options=s4_options,
                    clock_ns,
                ).core
            end
            statuses[variant] = string(outcome.status)
            if variant != "S1-AP-LMQR" && outcome.status != :promoted
                error("S4 family-disjoint warm-up mechanism failed: $variant k=$nullity")
            end
        end
        push!(documents, Dict{String,Any}(
            "nullity" => nullity,
            "order" => collect(orders[fixture_index]),
            "statuses" => statuses,
        ))
    end
    return Dict{String,Any}(
        "fixtures" => documents,
        "measured" => false,
        "namespace" => "singular-s4-family-disjoint-warmup-v1",
        "schema" => "geotarget.singular-s4-warmup/v1",
    )
end
