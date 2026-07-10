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
    input = CandidateInput(oracle, [2.0^-80, -2.0^-82])
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
    return CandidateInput(oracle, [2.0^-70, -2.0^-72, 2.0^-75]),
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
    @test candidate.core.work.iterations == 4
    @test control.core.work.iterations == 4

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
    @test_throws ExperimentSingular001.ExperimentBudgetExceeded
        ExperimentSingular001._s4c_residual!(
            crossing_ledger,
            input.oracle,
            BigFloat.(input.endpoint),
            128,
        )
    @test crossing_ledger.deadline_reached

    calls[] = 0
    factor_ledger = ExperimentSingular001._work_ledger(options, crossing_clock)
    @test_throws ExperimentSingular001.ExperimentBudgetExceeded
        ExperimentSingular001._s4c_split!(
            factor_ledger,
            BigFloat[1 0; 0 0],
        )
    @test factor_ledger.deadline_reached

    calls[] = 0
    analytic_ledger = ExperimentSingular001._work_ledger(options, crossing_clock)
    @test_throws ExperimentSingular001.ExperimentBudgetExceeded
        ExperimentSingular001._s4a_jacobian!(
            analytic_ledger,
            analytic,
            input.oracle,
            BigFloat.(input.endpoint),
            128,
        )
    @test analytic_ledger.deadline_reached

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

@testset "S4 development artifact conversion is Gold-side only" begin
    input, analytic = _s4_synthetic_deflation_one()
    @test ExperimentSingular001._s4_document_value(BigFloat("0.125")) == "0.125"
    @test ExperimentSingular001._s4_document_value(1 // 16) == "1//16"
    @test candidate_input(first(ExperimentSingular001.s4_development_cases())) isa
          CandidateInput
    @test input.oracle.analytic_jacobian === nothing
    @test analytic.analytic_jacobian !== nothing
end
