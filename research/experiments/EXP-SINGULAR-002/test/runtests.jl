using ExperimentSingular002
using LinearAlgebra
using Random
using Test

function orthogonal(rng::AbstractRNG, dimension::Int)
    factor = qr(randn(rng, dimension, dimension)).Q
    result = Matrix(factor)
    det(result) < 0 && (result[:, 1] .*= -1)
    return result
end

function base_operator(nullity::Int)
    retained = 2
    dimension = retained + nullity
    values = vcat([3.0, 1.0], zeros(nullity))
    return Matrix(Diagonal(values))
end

function base_second_directional(nullity::Int)
    retained = 2
    dimension = retained + nullity
    function evaluate(first, second)
        output = zeros(eltype(first), dimension)
        # A symmetric cyclic tensor.  Every coordinate contraction B(e_i) is
        # a nonsingular weighted permutation, while the Gram contraction K has
        # distinct diagonal entries.  This avoids building the desired answer
        # into an arbitrary SVD basis direction.
        for first_index in 1:nullity, second_index in 1:nullity
            left_index = mod(first_index + second_index - 2, nullity) + 1
            weight = 1 + (first_index - 1) * (second_index - 1)
            output[retained + left_index] += weight *
                first[retained + first_index] *
                second[retained + second_index]
        end
        return output
    end
    return evaluate
end

@testset "declared metric normalization" begin
    variable_metric = Diagonal([4.0, 0.25]) |> Matrix
    residual_metric = Diagonal([9.0, 1.0 / 16.0]) |> Matrix
    maps = declared_metric_maps(variable_metric, residual_metric)
    dx = [0.5, -2.0]
    residual = [1.0 / 3.0, 4.0]
    @test norm(maps.variable_to_physical \ dx, 2)^2 ≈
          dot(dx, variable_metric * dx)
    @test norm(maps.residual_to_normalized * residual, 2)^2 ≈
          dot(residual, residual_metric * residual)
    @test_throws PosDefException declared_metric_maps(
        [1.0 0.0; 0.0 -1.0],
        Matrix{Float64}(I, 2, 2),
    )
    @test_throws ArgumentError declared_metric_maps(
        [1.0 1.0; 0.0 1.0],
        Matrix{Float64}(I, 2, 2),
    )
end

@testset "Jacobian pair and Weyl rank fail closed" begin
    endpoint = zeros(3)
    residual(x) = [x[1], 2x[2], x[3]^2 + 0.01x[1]^3]
    identity_map = Matrix{Float64}(I, 3, 3)
    charged = Ref(0)
    evidence = acquire_normalized_jacobian_pair(
        residual,
        endpoint,
        identity_map,
        identity_map,
        1.0e-4,
        charge_callback=() -> (charged[] += 1),
    )
    @test evidence.callbacks == 12
    @test charged[] == evidence.callbacks
    @test evidence.eta >= 2evidence.delta_spectral
    certificate = certify_weyl_rank(evidence.fine, evidence.eta)
    @test certificate.status == :certified
    @test certificate.rank == 2
    @test certificate.nullity == 1

    ambiguous = certify_weyl_rank(Diagonal([1.0, 1.0e-7, 1.0e-14]) |> Matrix, 0.0)
    @test ambiguous.status == :unknown
    @test occursin("ambiguous", ambiguous.reason)
    unresolved = certify_weyl_rank(Diagonal([1.0, 0.2, 0.1]) |> Matrix, 1.0e-3)
    @test unresolved.status == :unknown
    @test_throws DimensionMismatch certify_weyl_rank(ones(2, 3), 0.0)

    failed_charges = Ref(0)
    function failing_residual(x)
        failed_charges[] == 2 && error("synthetic callback failure")
        return residual(x)
    end
    @test_throws ErrorException acquire_normalized_jacobian_pair(
        failing_residual,
        endpoint,
        identity_map,
        identity_map,
        1.0e-4,
        charge_callback=() -> (failed_charges[] += 1),
    )
    @test failed_charges[] == 2
end

@testset "orthogonal covariance of rank, projectors, and tensor spectrum" begin
    rng = MersenneTwister(0x53352d494e564152)
    for nullity in 1:4
        operator = base_operator(nullity)
        dimension = size(operator, 1)
        base_rank = certify_weyl_rank(operator, 0.0)
        @test base_rank.status == :certified
        hessian = base_second_directional(nullity)
        tensor_charges = Ref(0)
        base_projected_tensor = projected_hessian_tensor(
            hessian,
            base_rank.left_null_basis,
            base_rank.right_null_basis,
            charge_callback=() -> (tensor_charges[] += 1),
        )
        @test tensor_charges[] == nullity * (nullity + 1) ÷ 2
        base_tensor = symmetric_projected_operator(base_projected_tensor)
        base_spectrum = svdvals(base_tensor)
        @test certify_projected_tensor(base_tensor, base_tensor).passed
        base_lines = certify_covariant_lines(
            base_projected_tensor,
            base_projected_tensor,
            base_rank.right_null_basis,
        )
        @test base_lines.status == :certified
        @test length(base_lines.eigenvalues) == nullity
        base_contractions = certify_contracted_lines(
            base_projected_tensor,
            base_projected_tensor,
            base_lines,
        )
        @test base_contractions.passed
        @test base_contractions.valid_indices == collect(1:nullity)
        @test cross_precision_lines(base_lines, base_lines).passed
        @test cross_precision_contractions(base_contractions, base_contractions).passed

        for _ in 1:100
            variable_rotation = orthogonal(rng, dimension)
            residual_rotation = orthogonal(rng, dimension)
            replica_operator = residual_rotation * operator * transpose(variable_rotation)
            replica_rank = certify_weyl_rank(replica_operator, 0.0)
            @test replica_rank.status == :certified
            @test replica_rank.rank == base_rank.rank
            @test replica_rank.nullity == base_rank.nullity
            @test replica_rank.singular_values ≈ base_rank.singular_values rtol=2e-13 atol=2e-14
            @test replica_rank.right_null_projector ≈
                  variable_rotation * base_rank.right_null_projector *
                  transpose(variable_rotation) rtol=3e-13 atol=3e-13
            @test replica_rank.left_null_projector ≈
                  residual_rotation * base_rank.left_null_projector *
                  transpose(residual_rotation) rtol=3e-13 atol=3e-13

            function replica_hessian(first, second)
                physical_first = transpose(variable_rotation) * first
                physical_second = transpose(variable_rotation) * second
                return residual_rotation * hessian(physical_first, physical_second)
            end
            replica_projected_tensor = projected_hessian_tensor(
                replica_hessian,
                replica_rank.left_null_basis,
                replica_rank.right_null_basis,
            )
            replica_tensor = symmetric_projected_operator(replica_projected_tensor)
            @test svdvals(replica_tensor) ≈ base_spectrum rtol=5e-13 atol=5e-13
            @test certify_projected_tensor(replica_tensor, replica_tensor).passed
            replica_lines = certify_covariant_lines(
                replica_projected_tensor,
                replica_projected_tensor,
                replica_rank.right_null_basis,
            )
            @test replica_lines.status == :certified
            @test replica_lines.eigenvalues ≈ base_lines.eigenvalues rtol=8e-13 atol=8e-13
            replica_contractions = certify_contracted_lines(
                replica_projected_tensor,
                replica_projected_tensor,
                replica_lines,
            )
            @test replica_contractions.passed
            @test replica_contractions.valid_indices == base_contractions.valid_indices
            for line_index in 1:nullity
                @test replica_lines.ambient_projectors[line_index] ≈
                      variable_rotation * base_lines.ambient_projectors[line_index] *
                      transpose(variable_rotation) rtol=2e-12 atol=2e-12
                @test isapprox(
                    replica_contractions.certificates[line_index].singular_values,
                    base_contractions.certificates[line_index].singular_values;
                    rtol=2e-12,
                    atol=2e-12,
                )
            end
        end
    end
end

@testset "finite covariant lines, paper B(v), and endpoint reconciliation" begin
    nullity = 3
    operator = base_operator(nullity)
    rank = certify_weyl_rank(operator, 0.0)
    hessian = base_second_directional(nullity)
    tensor = projected_hessian_tensor(
        hessian,
        rank.left_null_basis,
        rank.right_null_basis,
    )
    lines = certify_covariant_lines(tensor, tensor, rank.right_null_basis)
    @test lines.status == :certified
    @test all(diff(lines.eigenvalues) .< 0)
    contraction = covariant_contraction(tensor)
    for first in 1:nullity, second in 1:nullity
        reconstructed = sum(
            tensor[left, first, contracted] * tensor[left, second, contracted] for
            left in 1:nullity for contracted in 1:nullity
        )
        @test contraction[first, second] ≈ reconstructed
    end

    contracted = certify_contracted_lines(tensor, tensor, lines)
    @test contracted.passed
    @test contracted.valid_indices == collect(1:nullity)
    coarse_tensor = (1 + 1.0e-12) .* tensor
    paired_lines = certify_covariant_lines(
        coarse_tensor,
        tensor,
        rank.right_null_basis,
    )
    paired_contracted = certify_contracted_lines(
        coarse_tensor,
        tensor,
        paired_lines,
    )
    @test paired_lines.status == :certified
    @test paired_contracted.passed
    @test cross_precision_lines(lines, paired_lines).passed
    @test cross_precision_contractions(contracted, paired_contracted).passed
    for line_index in contracted.valid_indices
        direction = lines.local_directions[:, line_index]
        positive = contracted_operator(tensor, direction)
        negative = contracted_operator(tensor, -direction)
        @test negative ≈ -positive
        @test minimum(svdvals(positive)) > 0
    end

    expected_correction = [0.125, -0.25, 0.375]
    projected_jacobian = zeros(nullity, nullity)
    for column in 1:nullity
        coordinate = zeros(nullity)
        coordinate[column] = 1
        projected_jacobian[:, column] .=
            -contracted_operator(tensor, coordinate) * expected_correction
    end
    line_precision_gate = cross_precision_lines(lines, lines)
    contraction_precision_gate = cross_precision_contractions(contracted, contracted)
    factorization_charges = Ref(0)
    trials = paper_two_step_null_trials(
        tensor,
        lines,
        contracted,
        projected_jacobian,
        line_precision_gate=line_precision_gate,
        contraction_precision_gate=contraction_precision_gate,
        charge_factorization=() -> (factorization_charges[] += 1),
    )
    @test length(trials) == 2nullity
    @test factorization_charges[] == length(trials)
    @test sort(unique(trial.sign for trial in trials)) == [-1, 1]
    @test sort(unique(trial.line_index for trial in trials)) == collect(1:nullity)
    @test all(trial -> isapprox(trial.correction, expected_correction; atol=2e-14), trials)
    endpoints = [trial.correction .+ 1.0e-13 .* trial.sign for trial in trials]
    reconciled = reconcile_signed_endpoints(endpoints, trials, contracted)
    @test reconciled.passed
    @test reconciled.endpoint_count == 2nullity
    @test reconciled.barycenter ≈ expected_correction atol=2e-14

    rotation = orthogonal(MersenneTwister(0x53352d5245434f4e), nullity)
    rotated_reconciliation = reconcile_signed_endpoints(
        [rotation * point for point in endpoints],
        trials,
        contracted,
    )
    @test rotated_reconciliation.passed
    @test rotated_reconciliation.barycenter ≈ rotation * reconciled.barycenter atol=2e-14
    @test rotated_reconciliation.maximum_pairwise_distance ≈
          reconciled.maximum_pairwise_distance atol=2e-14

    inconsistent_jacobian = copy(projected_jacobian)
    inconsistent_jacobian[:, 1] .= 0
    inconsistent_trials = paper_two_step_null_trials(
        tensor,
        lines,
        contracted,
        inconsistent_jacobian,
        line_precision_gate=line_precision_gate,
        contraction_precision_gate=contraction_precision_gate,
    )
    inconsistent = reconcile_signed_endpoints([
        trial.correction for trial in inconsistent_trials
    ], inconsistent_trials, contracted)
    @test !inconsistent.passed
    @test occursin("disagree", inconsistent.reason)

    scaled_tensor = 1.01 .* tensor
    scaled_lines = certify_covariant_lines(
        scaled_tensor,
        scaled_tensor,
        rank.right_null_basis,
    )
    scaled_contracted = certify_contracted_lines(
        scaled_tensor,
        scaled_tensor,
        scaled_lines,
    )
    @test scaled_lines.status == :certified
    @test scaled_contracted.passed
    scaled_line_precision = cross_precision_lines(lines, scaled_lines)
    scaled_B_precision = cross_precision_contractions(contracted, scaled_contracted)
    @test !scaled_line_precision.passed
    @test !scaled_B_precision.passed
    @test_throws ArgumentError paper_two_step_null_trials(
        tensor,
        lines,
        contracted,
        projected_jacobian,
        line_precision_gate=scaled_line_precision,
        contraction_precision_gate=scaled_B_precision,
    )
    @test_throws DimensionMismatch reconcile_signed_endpoints(
        endpoints[1:end-1],
        trials,
        contracted,
    )
    @test_throws ArgumentError reconcile_signed_endpoints(
        endpoints[1:2],
        trials[1:2],
        contracted,
    )
end

@testset "C spectrum cannot rescue degenerate K or singular B(v)" begin
    nullity = 3
    right_basis = Matrix{Float64}(I, nullity, nullity)

    degenerate = zeros(nullity, nullity, nullity)
    for index in 1:nullity
        degenerate[index, index, index] = 1
    end
    degenerate_lines = certify_covariant_lines(
        degenerate,
        degenerate,
        right_basis,
    )
    @test degenerate_lines.status == :unknown
    @test occursin("degenerate", degenerate_lines.reason)

    singular_contractions = zeros(nullity, nullity, nullity)
    for index in 1:nullity
        singular_contractions[index, index, index] = index
    end
    flattened = symmetric_projected_operator(singular_contractions)
    @test certify_projected_tensor(flattened, flattened).passed
    simple_lines = certify_covariant_lines(
        singular_contractions,
        singular_contractions,
        right_basis,
    )
    @test simple_lines.status == :certified
    no_valid_contraction = certify_contracted_lines(
        singular_contractions,
        singular_contractions,
        simple_lines,
    )
    @test !no_valid_contraction.passed
    @test isempty(no_valid_contraction.valid_indices)
    @test all(certificate -> !certificate.passed, no_valid_contraction.certificates)
    no_valid_line_precision = cross_precision_lines(simple_lines, simple_lines)
    no_valid_B_precision = cross_precision_contractions(
        no_valid_contraction,
        no_valid_contraction,
    )
    @test_throws ArgumentError paper_two_step_null_trials(
        singular_contractions,
        simple_lines,
        no_valid_contraction,
        zeros(nullity, nullity),
        line_precision_gate=no_valid_line_precision,
        contraction_precision_gate=no_valid_B_precision,
    )
end

@testset "metric-covariant scale and signed-permutation replicas" begin
    rng = MersenneTwister(0x53352d4d45545249)
    nullity = 2
    operator = base_operator(nullity)
    dimension = size(operator, 1)
    hessian = base_second_directional(nullity)
    base_rank = certify_weyl_rank(operator, 0.0)
    base_tensor = symmetric_projected_operator(
        hessian,
        base_rank.left_null_basis,
        base_rank.right_null_basis,
    )
    base_spectrum = svdvals(base_tensor)
    identity_matrix = Matrix{Float64}(I, dimension, dimension)

    for replica_index in 1:50
        variable_rotation = orthogonal(rng, dimension)
        residual_rotation = orthogonal(rng, dimension)
        variable_scales = exp.(range(log(1.0e-1), log(1.0e1); length=dimension))
        residual_scales = reverse(variable_scales)
        isodd(replica_index) && reverse!(variable_scales)
        variable_transform = variable_rotation * Diagonal(variable_scales)
        residual_transform = residual_rotation * Diagonal(residual_scales)
        variable_inverse = variable_transform \ identity_matrix
        residual_inverse = residual_transform \ identity_matrix
        variable_metric = transpose(variable_inverse) * variable_inverse
        residual_metric = transpose(residual_inverse) * residual_inverse
        maps = declared_metric_maps(variable_metric, residual_metric)
        transformed_operator = residual_transform * operator * variable_inverse
        normalized = normalized_jacobian(
            transformed_operator,
            maps.variable_to_physical,
            maps.residual_to_normalized,
        )
        replica_rank = certify_weyl_rank(normalized, 0.0)
        @test replica_rank.status == :certified
        @test replica_rank.rank == base_rank.rank
        @test replica_rank.nullity == base_rank.nullity
        @test replica_rank.singular_values ≈ base_rank.singular_values rtol=2e-10 atol=2e-11

        function normalized_hessian(first, second)
            new_first = maps.variable_to_physical * first
            new_second = maps.variable_to_physical * second
            old_first = variable_inverse * new_first
            old_second = variable_inverse * new_second
            transformed = residual_transform * hessian(old_first, old_second)
            return maps.residual_to_normalized * transformed
        end
        replica_tensor = symmetric_projected_operator(
            normalized_hessian,
            replica_rank.left_null_basis,
            replica_rank.right_null_basis,
        )
        @test svdvals(replica_tensor) ≈ base_spectrum rtol=5e-9 atol=5e-10
    end

    variable_permutation = [0.0 -1.0 0.0 0.0; 1.0 0.0 0.0 0.0; 0.0 0.0 0.0 -1.0; 0.0 0.0 1.0 0.0]
    residual_permutation = [0.0 0.0 1.0 0.0; 0.0 -1.0 0.0 0.0; 0.0 0.0 0.0 1.0; -1.0 0.0 0.0 0.0]
    signed = residual_permutation * operator * transpose(variable_permutation)
    signed_rank = certify_weyl_rank(signed, 0.0)
    @test signed_rank.status == :certified
    @test signed_rank.singular_values ≈ base_rank.singular_values
end

@testset "same-chart projector uncertainty and tensor rejection" begin
    first = certify_weyl_rank(Diagonal([2.0, 1.0, 0.0]) |> Matrix, 1.0e-14)
    rotation = [cos(1.0e-8) 0.0 -sin(1.0e-8); 0.0 1.0 0.0; sin(1.0e-8) 0.0 cos(1.0e-8)]
    second_operator = Diagonal([2.0, 1.0, 0.0]) * transpose(rotation)
    second = certify_weyl_rank(second_operator, 1.0e-8)
    stability = projector_stability(first, second)
    @test stability.passed
    @test stability.left_distance ≈ 0.0 atol=1e-14
    @test stability.right_distance <= stability.bound

    collapsed = [1.0 0.0 0.0; 0.0 0.0 0.0]
    tensor = certify_projected_tensor(collapsed, collapsed)
    @test !tensor.passed
    @test occursin("rank", tensor.reason)
    @test_throws DimensionMismatch certify_projected_tensor(ones(2, 3), ones(3, 3))
end

@testset "nonlinear finite-difference representation decisions" begin
    rng = MersenneTwister(0x53352d4644504149)
    dimension = 3
    base_endpoint = zeros(dimension)
    identity_map = Matrix{Float64}(I, dimension, dimension)
    function base_residual(x)
        return [
            2x[1] + 0.03x[3]^3,
            x[2] - 0.02x[1] * x[3]^2,
            x[3]^2 + 0.01x[1]^3,
        ]
    end
    base_pair = acquire_normalized_jacobian_pair(
        base_residual,
        base_endpoint,
        identity_map,
        identity_map,
        2.0e-4,
    )
    base_certificate = certify_weyl_rank(base_pair.fine, base_pair.eta)
    @test base_certificate.status == :certified
    for _ in 1:100
        variable_rotation = orthogonal(rng, dimension)
        residual_rotation = orthogonal(rng, dimension)
        replica_residual(y) = residual_rotation * base_residual(
            transpose(variable_rotation) * y,
        )
        replica_pair = acquire_normalized_jacobian_pair(
            replica_residual,
            base_endpoint,
            identity_map,
            identity_map,
            2.0e-4,
        )
        replica_certificate = certify_weyl_rank(replica_pair.fine, replica_pair.eta)
        @test replica_certificate.status == :certified
        @test replica_certificate.rank == base_certificate.rank
        @test replica_certificate.nullity == base_certificate.nullity
        for index in eachindex(base_certificate.singular_values)
            base_interval = (
                base_certificate.lower[index],
                base_certificate.upper[index],
            )
            replica_interval = (
                replica_certificate.lower[index],
                replica_certificate.upper[index],
            )
            @test max(base_interval[1], replica_interval[1]) <=
                  min(base_interval[2], replica_interval[2])
        end
    end
end

@testset "truth-blind and no-outcome static source boundary" begin
    source = read(joinpath(@__DIR__, "..", "src", "invariant_diagnostics.jl"), String)
    for forbidden in (
        "case_id",
        "family_id",
        "Gold",
        "metamorphic_group",
        "representation_id",
        "primitive_name",
        "counter_namespace",
        "coefficient_counter",
    )
        @test !occursin(forbidden, source)
    end
    experiment_root = normpath(joinpath(@__DIR__, ".."))
    @test !isfile(joinpath(experiment_root, "run_development.jl"))
    @test !isfile(joinpath(experiment_root, "prepare_development.jl"))
end
