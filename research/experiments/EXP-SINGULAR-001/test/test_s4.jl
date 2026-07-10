function _s4_synthetic_deflation_one()
    function residual(z::AbstractVector{T}) where {T<:Real}
        return T[z[2], z[1]^2]
    end
    function target(z::AbstractVector{T}) where {T<:Real}
        return z[1] / T(2) - z[2] / T(3) + T(3) / T(8)
    end
    function jacobian(z::AbstractVector{T}) where {T<:Real}
        return T[0 1; 2 * z[1] 0]
    end
    function second_directional(
        z::AbstractVector{T},
        first,
        second,
    ) where {T<:Real}
        return T[0, 2 * first[1] * second[1]]
    end
    oracle = EndpointOracle(
        "synthetic-s4-unit",
        "SYNTHETIC-UNIT",
        "synthetic-s4-unit-group",
        2,
        2,
        :C2,
        residual,
        target,
        nothing,
    )
    input = s4_candidate_input(CandidateInput(oracle, [2.0^-80, -2.0^-82]))
    analytic = ExperimentSingular001.S4AnalyticControlOracle(
        jacobian,
        second_directional,
    )
    return input, analytic
end

function _s4_synthetic_nullity_two()
    function residual(z::AbstractVector{T}) where {T<:Real}
        x, y, retained = z
        return T[retained, x^2 - y^2, 2 * x * y]
    end
    function target(z::AbstractVector{T}) where {T<:Real}
        return z[1] / T(2) - z[2] / T(3) + z[3] / T(4)
    end
    function jacobian(z::AbstractVector{T}) where {T<:Real}
        x, y, _ = z
        return T[0 0 1; 2x -2y 0; 2y 2x 0]
    end
    function second_directional(z::AbstractVector{T}, first, second) where {T<:Real}
        return T[
            0,
            2 * first[1] * second[1] - 2 * first[2] * second[2],
            2 * first[1] * second[2] + 2 * first[2] * second[1],
        ]
    end
    oracle = EndpointOracle(
        "synthetic-s4-k2-unit",
        "SYNTHETIC-UNIT",
        "synthetic-s4-k2-group",
        3,
        3,
        :C2,
        residual,
        target,
        nothing,
    )
    return s4_candidate_input(CandidateInput(
            oracle,
            [2.0^-70, -2.0^-72, 2.0^-75],
        )),
        ExperimentSingular001.S4AnalyticControlOracle(jacobian, second_directional)
end

function _s4_synthetic_nullity_four()
    function residual(z::AbstractVector{T}) where {T<:Real}
        return T[z[5], z[1]^2, z[2]^2, z[3]^2, z[4]^2]
    end
    function target(z::AbstractVector{T}) where {T<:Real}
        return sum(T(index) * z[index] / T(16) for index in eachindex(z))
    end
    function jacobian(z::AbstractVector{T}) where {T<:Real}
        result = zeros(T, 5, 5)
        result[1, 5] = one(T)
        for index in 1:4
            result[index + 1, index] = 2 * z[index]
        end
        return result
    end
    function second_directional(z::AbstractVector{T}, first, second) where {T<:Real}
        return T[0, (2 * first[index] * second[index] for index in 1:4)...]
    end
    oracle = EndpointOracle(
        "synthetic-s4-k4-unit",
        "SYNTHETIC-UNIT",
        "synthetic-s4-k4-group",
        5,
        5,
        :C2,
        residual,
        target,
        nothing,
    )
    endpoint = [2.0^-70, -2.0^-71, 2.0^-72, -2.0^-73, 2.0^-80]
    return s4_candidate_input(CandidateInput(oracle, endpoint)),
        ExperimentSingular001.S4AnalyticControlOracle(jacobian, second_directional)
end

function _s4_negative_fixture(mode::Symbol)
    mode in (:higher_depth, :regular_fold, :manifold, :nonroot) ||
        throw(ArgumentError("unsupported negative fixture"))
    separation = 1.0e-7
    inconsistency = 2.0^-50
    function residual(z::AbstractVector{T}) where {T<:Real}
        x, y = z
        second = if mode === :higher_depth
            x^3
        elseif mode === :regular_fold
            x^2 - T(separation)^2
        elseif mode === :manifold
            zero(T)
        else
            x^2 + T(inconsistency)
        end
        return T[y, second]
    end
    target(z::AbstractVector{T}) where {T<:Real} = z[1] / T(2) - z[2] / T(3)
    function jacobian(z::AbstractVector{T}) where {T<:Real}
        x, _ = z
        derivative = mode === :higher_depth ? 3 * x^2 :
                     mode === :manifold ? zero(T) : 2 * x
        return T[0 1; derivative 0]
    end
    function second_directional(z::AbstractVector{T}, first, second) where {T<:Real}
        x, _ = z
        curvature = mode === :higher_depth ? 6 * x :
                    mode === :manifold ? zero(T) : T(2)
        return T[0, curvature * first[1] * second[1]]
    end
    endpoint = mode === :higher_depth ? [2.0^-20, 0.0] :
               mode === :regular_fold ? [separation, 0.0] : [0.0, 0.0]
    oracle = EndpointOracle(
        "synthetic-s4-negative-$(mode)",
        "SYNTHETIC-NEGATIVE",
        "synthetic-s4-negative-$(mode)",
        2,
        2,
        :C2,
        residual,
        target,
        nothing,
    )
    return s4_candidate_input(CandidateInput(oracle, endpoint)),
        ExperimentSingular001.S4AnalyticControlOracle(jacobian, second_directional)
end

@testset "S4 frozen numerical mechanisms on synthetic input" begin
    input, analytic = _s4_synthetic_deflation_one()
    candidate_source = read(joinpath(@__DIR__, "..", "src", "s4", "candidate.jl"), String)
    control_source = read(
        joinpath(@__DIR__, "..", "src", "s4", "analytic_control.jl"),
        String,
    )
    @test !occursin("S4AnalyticControlOracle", candidate_source)
    @test !occursin("analytic_second_directional", candidate_source)
    @test !occursin("metamorphic_group", candidate_source)
    @test !occursin(r"\.family\b", candidate_source)
    @test !occursin(r"\.id\b", candidate_source)
    @test !occursin("_s4c_", control_source)
    @test !occursin("_s4a_", candidate_source)

    for nullity in 1:4, iteration in (1, 2, 64, 65)
        candidate_coefficients = ExperimentSingular001._s4c_coefficients(
            BigFloat,
            nullity,
            iteration,
        )
        control_coefficients = ExperimentSingular001._s4a_coefficients(
            BigFloat,
            nullity,
            iteration,
        )
        @test candidate_coefficients == control_coefficients
        @test norm(candidate_coefficients, 2) ≈ 1
    end

    options = ExperimentOptions(
        precision_ladder=(128, 256),
        semantic_precision_bits=256,
        wall_seconds=10.0,
    )
    candidate = run_s4(input; options)
    control = run_s4_analytic_control(input, analytic; options)
    @test candidate.core.status == :promoted
    @test control.core.status == :promoted
    @test candidate.core.root_evidence isa NumericalSingularRootEvidence
    @test control.core.root_evidence isa NumericalSingularRootEvidence
    @test candidate.core.root_evidence.nullity == 1
    @test control.core.root_evidence.nullity == 1
    @test candidate.diagnostics["phase"] == "promoted"
    @test control.diagnostics["phase"] == "promoted"
    @test candidate.core.work.callbacks <= options.maximum_callbacks
    @test control.core.work.callbacks <= options.maximum_callbacks
    # Each perturbed confirmation first reaches the root, then performs a
    # second complete step to satisfy the frozen normalized-last-step gate.
    @test candidate.core.work.iterations == 6
    @test control.core.work.iterations == 6
    @test candidate.core.work.callbacks == 516
    @test candidate.core.work.factorization_calls == 126
    @test candidate.core.work.target_calls == 24
    @test candidate.core.work.jacobian_calls == 0
    @test control.core.work.callbacks == 124
    @test control.core.work.factorization_calls == 70
    @test control.core.work.target_calls == 24
    @test control.core.work.jacobian_calls == 42

    candidate_audit = candidate.diagnostics["applicability_audits"][1]
    @test candidate_audit["physical_reference"]["ell"] == 65
    for entry in candidate_audit["probes"], side in ("start", "final")
        probe = entry[side]
        @test haskey(probe, "c_local")
        @test haskey(probe, "c_local_norm")
        @test probe["ell"] == 65
        @test probe["subspace_decision"]
        @test haskey(probe, "complete_correction")
    end
    for key in (
        "final_corrections",
        "final_correction_magnitude",
        "final_correction_norms",
        "gradients",
        "raw_configuration_components",
        "target_error_components",
    )
        @test haskey(candidate.diagnostics["error_audit"], key)
    end

    starved = ExperimentOptions(
        precision_ladder=(128, 256),
        semantic_precision_bits=256,
        maximum_callbacks=8,
        wall_seconds=10.0,
    )
    exhausted = run_s4(input; options=starved)
    @test exhausted.core.status == :unknown
    @test exhausted.core.work.callbacks == 0
    @test occursin("options differ", exhausted.core.reason)
end

@testset "S4 basis transport, ambient precision and deadline invariants" begin
    input, analytic = _s4_synthetic_nullity_two()
    options = ExperimentOptions(
        precision_ladder=(128, 256),
        semantic_precision_bits=256,
    )
    candidate_128 = setprecision(BigFloat, 128) do
        run_s4(input; options)
    end
    candidate_512 = setprecision(BigFloat, 512) do
        run_s4(input; options)
    end
    control = run_s4_analytic_control(input, analytic; options)
    @test candidate_128.core.status == candidate_512.core.status == :promoted
    @test control.core.status == :promoted
    @test candidate_128.core.root_evidence.nullity == 2
    @test control.core.root_evidence.nullity == 2
    @test candidate_128.core.root_evidence.configuration_error_estimate ==
          candidate_512.core.root_evidence.configuration_error_estimate
    @test candidate_128.core.root_evidence.target_error_estimate ==
          candidate_512.core.root_evidence.target_error_estimate

    # A confirmation start inherits k from the eligible primary endpoint.
    # Its retained direction must remain valid, but its temporary gap need
    # not independently satisfy the endpoint routing threshold.  Final audits
    # still invoke the strict branch exercised by the throwing assertions.
    above_gap = BigFloat[1 0; 0 BigFloat("2e-6")]
    candidate_route_ledger = ExperimentSingular001._work_ledger(options, () -> UInt64(0))
    inherited_candidate = ExperimentSingular001._s4c_split!(
        candidate_route_ledger,
        above_gap;
        fixed_nullity=1,
        require_route_selection=false,
    )
    @test inherited_candidate.nullity == 1
    @test_throws ExperimentSingular001._S4CandidateReject begin
        ExperimentSingular001._s4c_split!(
            candidate_route_ledger,
            above_gap;
            fixed_nullity=1,
            require_route_selection=true,
        )
    end
    control_route_ledger = ExperimentSingular001._work_ledger(options, () -> UInt64(0))
    inherited_control = ExperimentSingular001._s4a_split!(
        control_route_ledger,
        above_gap;
        fixed_nullity=1,
        require_route_selection=false,
    )
    @test inherited_control.nullity == 1
    @test_throws ExperimentSingular001._S4ControlReject begin
        ExperimentSingular001._s4a_split!(
            control_route_ledger,
            above_gap;
            fixed_nullity=1,
            require_route_selection=true,
        )
    end

    ledger = ExperimentSingular001._work_ledger(options, () -> UInt64(0))
    reference_basis = BigFloat[1 0; 0 1; 0 0]
    angle = BigFloat(3) / BigFloat(5)
    sine = BigFloat(4) / BigFloat(5)
    rotation = BigFloat[angle -sine; sine angle]
    rotated_basis = reference_basis * rotation
    coefficients = ExperimentSingular001._s4c_coefficients(BigFloat, 2, 65)
    reference = (
        basis=reference_basis,
        direction=reference_basis * coefficients,
    )
    candidate_probe = ExperimentSingular001._s4c_local_probe(
        ledger,
        (V2=rotated_basis,),
        reference,
        2,
        65,
    )
    control_probe = ExperimentSingular001._s4a_local_probe(
        ledger,
        (V2=rotated_basis,),
        reference,
        2,
        65,
    )
    @test candidate_probe.direction ≈ reference.direction
    @test control_probe.direction ≈ reference.direction
    @test candidate_probe.local_coordinate_norm ≈ 1
    @test control_probe.local_coordinate_norm ≈ 1

    calls = Ref(0)
    crossing_clock = () -> begin
        calls[] += 1
        return calls[] <= 2 ? UInt64(0) : UInt64(11_000_000_000)
    end
    crossing_ledger = ExperimentSingular001._work_ledger(options, crossing_clock)
    @test_throws ExperimentSingular001.ExperimentBudgetExceeded begin
        ExperimentSingular001._s4c_residual!(
            crossing_ledger,
            input.oracle,
            BigFloat.(input.endpoint),
            128,
        )
    end
    @test crossing_ledger.deadline_reached

    calls[] = 0
    factor_ledger = ExperimentSingular001._work_ledger(options, crossing_clock)
    @test_throws ExperimentSingular001.ExperimentBudgetExceeded begin
        ExperimentSingular001._s4c_split!(
            factor_ledger,
            BigFloat[1 0; 0 0],
        )
    end
    @test factor_ledger.deadline_reached

    calls[] = 0
    analytic_ledger = ExperimentSingular001._work_ledger(options, crossing_clock)
    @test_throws ExperimentSingular001.ExperimentBudgetExceeded begin
        ExperimentSingular001._s4a_jacobian!(
            analytic_ledger,
            analytic,
            input.oracle,
            BigFloat.(input.endpoint),
            128,
        )
    end
    @test analytic_ledger.deadline_reached

    snapshot_calls = Ref(0)
    snapshot_clock = () -> begin
        snapshot_calls[] += 1
        return snapshot_calls[] == 1 ? UInt64(0) : UInt64(11_000_000_000)
    end
    snapshot_ledger = ExperimentSingular001._work_ledger(options, snapshot_clock)
    @test_throws ExperimentSingular001.ExperimentBudgetExceeded begin
        ExperimentSingular001._s4_checked_work_snapshot!(snapshot_ledger)
    end
    @test snapshot_ledger.deadline_reached

    spy_input, base_analytic = _s4_synthetic_deflation_one()
    events = Any[]
    spy_jacobian = point -> begin
        push!(events, (kind=:jacobian, point=copy(point)))
        base_analytic.analytic_jacobian(point)
    end
    spy_second = (point, first, second) -> begin
        push!(events, (
            first=copy(first),
            kind=:second,
            point=copy(point),
            second=copy(second),
        ))
        base_analytic.analytic_second_directional(point, first, second)
    end
    spy = ExperimentSingular001.S4AnalyticControlOracle(spy_jacobian, spy_second)
    spy_ledger = ExperimentSingular001._work_ledger(options, () -> UInt64(0))
    step = setprecision(BigFloat, 128) do
        ExperimentSingular001._s4a_step!(
            spy_ledger,
            spy_input,
            spy,
            BigFloat.(spy_input.endpoint),
            128,
            1,
            1,
        )
    end
    @test [event.kind for event in events] == [:jacobian, :second, :jacobian]
    @test events[2].point ≈ step.x_range
    @test events[3].point ≈ step.x_range
end

@testset "S4 maximum frozen nullity remains inside hard work budgets" begin
    input, analytic = _s4_synthetic_nullity_four()
    options = ExperimentOptions(
        precision_ladder=(128, 256),
        semantic_precision_bits=256,
    )
    candidate = run_s4(input; options)
    control = run_s4_analytic_control(input, analytic; options)
    @test candidate.core.status == :promoted
    @test control.core.status == :promoted
    @test candidate.core.root_evidence.nullity == 4
    @test control.core.root_evidence.nullity == 4
    @test candidate.core.work.callbacks <= 4096
    @test control.core.work.callbacks <= 4096
    @test candidate.core.work.iterations == 6
    @test control.core.work.iterations == 6
    @test candidate.core.work.elapsed_seconds <= 10.0
    @test control.core.work.elapsed_seconds <= 10.0
end

@testset "S4 warm-up and per-group variant schedule are frozen" begin
    s4_options = ExperimentOptions(
        precision_ladder=(128, 256),
        semantic_precision_bits=256,
    )
    warmup = ExperimentSingular001._run_s4_family_disjoint_warmup!(
        s4_options,
        ExperimentOptions(),
    )
    @test warmup["measured"] == false
    @test length(warmup["fixtures"]) == 3
    @test [fixture["nullity"] for fixture in warmup["fixtures"]] == [1, 2, 4]
    @test all(
        fixture["statuses"]["S4-C2-NULLSPACE-TWO-STEP"] == "promoted" &&
        fixture["statuses"]["S4-ANALYTIC-TWO-STEP-CONTROL"] == "promoted" for
        fixture in warmup["fixtures"]
    )
    variants = Set((
        "S1-AP-LMQR",
        "S4-C2-NULLSPACE-TWO-STEP",
        "S4-ANALYTIC-TWO-STEP-CONTROL",
    ))
    for group_start in 1:3:36
        orders = [
            ExperimentSingular001._s4_counterbalanced_variant_order(index) for
            index in group_start:(group_start + 2)
        ]
        @test all(Set(order) == variants for order in orders)
        @test all(
            Set(order[position] for order in orders) == variants for position in 1:3
        )
    end
end

@testset "S4 A3 common-mode final correction is charged to error" begin
    input, _ = _s4_synthetic_deflation_one()
    options = ExperimentOptions(
        precision_ladder=(128, 256),
        semantic_precision_bits=256,
    )
    stage128 = (
        endpoint=BigFloat[0, 0],
        last_step=BigFloat(0),
        target=BigFloat(0),
    )
    stage256 = stage128
    confirmations = Any[stage256, stage256]
    correction = BigFloat[BigFloat("1e-4"), BigFloat(0)]
    candidate_audits = Any[
        (final=Dict(
            (128, 1.0) => (correction=correction,),
            (128, 0.5) => (correction=correction,),
        ),),
        (final=Dict(
            (256, 1.0) => (correction=correction,),
            (256, 0.5) => (correction=correction,),
        ),),
    ]
    ledger = ExperimentSingular001._work_ledger(options, () -> UInt64(0))
    audit = ExperimentSingular001._s4c_error_audit!(
        ledger,
        input,
        Any[stage128, stage256],
        confirmations,
        candidate_audits,
        options,
    )
    @test audit.raw_configuration >= BigFloat("1e-4")
    @test audit.configuration_error >= BigFloat("0.0016")
    @test !audit.passed
    @test audit.document["final_correction_magnitude"] == BigFloat("1e-4")
end

@testset "S4 fail-closed negative mechanism controls" begin
    options = ExperimentOptions(
        precision_ladder=(128, 256),
        semantic_precision_bits=256,
    )
    for mode in (:higher_depth, :regular_fold, :manifold, :nonroot)
        input, analytic = _s4_negative_fixture(mode)
        candidate = run_s4(input; options)
        control = run_s4_analytic_control(input, analytic; options)
        @test candidate.core.status == :unknown
        @test control.core.status == :unknown
        @test candidate.core.root_evidence === nothing
        @test control.core.root_evidence === nothing
        @test candidate.core.work.callbacks <= 4096
        @test control.core.work.callbacks <= 4096
    end
end

@testset "S4 development artifact conversion is Gold-side only" begin
    input, analytic = _s4_synthetic_deflation_one()
    @test ExperimentSingular001._s4_document_value(BigFloat("0.125")) == "0.125"
    @test ExperimentSingular001._s4_document_value(1 // 16) == "1//16"
    @test candidate_input(first(ExperimentSingular001.s4_development_cases())) isa
          CandidateInput
    @test input isa S4CandidateInput
    @test !hasproperty(input.oracle, :analytic_jacobian)
    @test !hasproperty(input.oracle, :id)
    @test !hasproperty(input.oracle, :family)
    @test !hasproperty(input.oracle, :metamorphic_group)
    @test analytic.analytic_jacobian !== nothing
end
