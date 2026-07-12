using LinearAlgebra
using Test

include(joinpath(@__DIR__, "..", "src", "ExperimentLocal015.jl"))
const LAB015 = ExperimentLocal015
const FIX015 = LAB015.FIXTURES

function synthetic_fixture(matrix; scale=1.0, semantics=(x -> (:b, :g, :d, 1.0, 1.0, 1.0, true)))
    n = size(matrix, 2)
    box = FIX015.FiniteBox(n)
    evaluate = function (x)
        branch, guard, domain, branch_margin, guard_margin, domain_margin, valid =
            semantics(x)
        residual = scale .* matrix * Float64[x...]
        return FIX015.FixtureEvaluation(
            residual,
            0.0,
            branch,
            guard,
            domain,
            branch_margin,
            guard_margin,
            domain_margin,
            valid,
        )
    end
    return (;
        box,
        evaluate_float64=evaluate,
        evaluate_arbitrary=nothing,
        starts=[zeros(Float64, n)],
    )
end

@testset "63-case representation corpus and truth-blind seam" begin
    cases = LAB015.materialize_t0_cases()
    @test length(cases) == 63
    @test [count(case -> case.class_index == index, cases) for index in 1:21] == fill(3, 21)
    @test Set(case.replica_kind for case in cases) ==
          Set((:base, :signed_permutation, :orthogonal))
    for case in cases
        candidate = FIX015.candidate_view(case.record)
        @test fieldnames(typeof(candidate)) ==
              (:box, :evaluate_float64, :evaluate_arbitrary, :starts)
        @test !hasproperty(candidate, :descriptor)
        @test !hasproperty(candidate, :assessor)
        @test !hasproperty(candidate, :checksum_payload)
        @test length(candidate.starts) == 16
    end
end

@testset "shared h/h2 prefilter uses complete invariant SVD evidence" begin
    for dimension in (2, 4, 8)
        base = FIX015.make_linear_fixture(dimension, 10^8)
        candidate = FIX015.candidate_view(base)
        result = LAB015.acquire_shared_prefilter(candidate, candidate.starts[1])
        @test result.status == :ready
        @test result.reason == :none
        @test result.callbacks == result.required_callbacks == 1 + 4dimension
        @test result.coarse_rank == result.fine_rank == result.numerical_rank
        @test result.model_agreement
        @test isfinite(result.condition_estimate)
        @test result.condition_lower_bound == result.condition_estimate
        @test result.condition_lower_bound <= result.condition_upper_bound
        @test result.condition_class == :uncertain

        signed = FIX015.signed_permutation_replica(base)
        signed_candidate = FIX015.candidate_view(signed)
        signed_result = LAB015.acquire_shared_prefilter(
            signed_candidate,
            signed_candidate.starts[1],
        )
        @test signed_result.status == :ready
        @test signed_result.numerical_rank == result.numerical_rank
        @test signed_result.model_agreement == result.model_agreement
        @test signed_result.condition_class == result.condition_class
        @test signed_result.condition_estimate ≈ result.condition_estimate rtol=1e-3

        rotated = FIX015.orthogonal_replica(base)
        rotated_candidate = FIX015.candidate_view(rotated)
        rotated_result = LAB015.acquire_shared_prefilter(
            rotated_candidate,
            rotated_candidate.starts[1],
        )
        @test rotated_result.status == :ready
        @test rotated_result.numerical_rank == result.numerical_rank
        @test rotated_result.model_agreement == result.model_agreement
        @test rotated_result.condition_class == result.condition_class
        @test rotated_result.condition_estimate ≈ result.condition_estimate rtol=1e-3
    end
end

@testset "shared rank and model gates are globally residual-scale homogeneous" begin
    angle = pi / 7
    left = [cos(angle) -sin(angle); sin(angle) cos(angle)]
    right = [3 / 5 -4 / 5; 4 / 5 3 / 5]
    matrix = left * Diagonal([2.0, 1.0e-9]) * transpose(right)
    results = [
        LAB015.acquire_shared_prefilter(
            synthetic_fixture(matrix; scale),
            [0.125, -0.25],
        ) for scale in (1.0, 1.0e-60, 1.0e60)
    ]
    @test all(result -> result.status == :ready, results)
    @test length(unique(result.numerical_rank for result in results)) == 1
    @test length(unique(result.model_agreement for result in results)) == 1
    @test length(unique(result.condition_class for result in results)) == 1
    @test all(
        result -> max(result.condition_lower_bound, results[1].condition_lower_bound) <=
                  min(result.condition_upper_bound, results[1].condition_upper_bound),
        results,
    )

    kappa = 100000071.1
    diagonal = Diagonal([1.0, 1 / kappa])
    variable_angle = 0.37
    residual_angle = 0.71
    variable_rotation = [
        cos(variable_angle) -sin(variable_angle)
        sin(variable_angle) cos(variable_angle)
    ]
    residual_rotation = [
        cos(residual_angle) -sin(residual_angle)
        sin(residual_angle) cos(residual_angle)
    ]
    boundary_base = LAB015.acquire_shared_prefilter(
        synthetic_fixture(Matrix(diagonal)),
        [0.125, -0.25],
    )
    boundary_replica = LAB015.acquire_shared_prefilter(
        synthetic_fixture(residual_rotation * diagonal * transpose(variable_rotation)),
        variable_rotation * [0.125, -0.25],
    )
    @test boundary_base.status == boundary_replica.status == :ready
    @test boundary_base.condition_class == boundary_replica.condition_class == :uncertain
    @test LAB015._routed_condition(boundary_base) ==
          LAB015._routed_condition(boundary_replica) == 0.0
end

@testset "semantic failure charges the full shared stencil and fails closed" begin
    calls = Ref(0)
    semantics = function (x)
        calls[] += 1
        guard = x[1] > 1.0e-7 ? :outer : :inner
        return (:branch, guard, :domain, 1.0, 1.0, 1.0, true)
    end
    fixture = synthetic_fixture(Matrix{Float64}(I, 2, 2); semantics)
    result = LAB015.acquire_shared_prefilter(fixture, zeros(2))
    @test result.status == :unknown
    @test result.reason == :semantic_identity_changed
    @test result.callbacks == result.required_callbacks == calls[] == 9

    malformed_calls = Ref(0)
    malformed = (;
        box=FIX015.FiniteBox(2),
        evaluate_float64=(x -> begin
            malformed_calls[] += 1
            error("ordinary callback failure")
        end),
        evaluate_arbitrary=nothing,
        starts=[zeros(2)],
    )
    failed = LAB015.acquire_shared_prefilter(malformed, zeros(2))
    @test failed.status == :unknown
    @test failed.reason == :evaluation_failed
    @test failed.callbacks == failed.required_callbacks == malformed_calls[] == 9

    discontinuous = synthetic_fixture(Matrix{Float64}(I, 2, 2))
    piecewise = merge(discontinuous, (;
        evaluate_float64=(x -> begin
            slope = abs(x[1]) > 0.75LAB015.SHARED_FD_STEP ? 2.0 : 1.0
            FIX015.FixtureEvaluation(
                [slope * x[1], x[2]],
                0.0,
                :branch,
                :guard,
                :domain,
                1.0,
                1.0,
                1.0,
                true,
            )
        end),
    ))
    disagreement = LAB015.acquire_shared_prefilter(piecewise, zeros(2))
    @test disagreement.status == :unknown
    @test disagreement.reason == :h_h2_model_disagreement
    @test disagreement.condition_class == :unknown
    @test !disagreement.model_agreement
end

@testset "assessor joins isolated-root truth only after candidate return" begin
    linear = FIX015.make_linear_fixture(2, 10^8)
    truth = FIX015.assessor_truth(linear)
    exact_root = truth.isolated_roots[1]
    point_match = LAB015.assess_point_seeds(truth, [exact_root])
    @test point_match.emitted_count == point_match.supported_count == 1
    @test point_match.matched_root_indices == [1]
    @test point_match.unsupported_count == 0
    bad_point = Float64[Float64(value) + 1.0e-4 for value in exact_root]
    unsupported = LAB015.assess_point_seeds(truth, [bad_point])
    @test unsupported.emitted_count == unsupported.unsupported_count == 1
    @test isempty(unsupported.matched_root_indices)

    clustered = FIX015.make_clustered_fixture(2, 4)
    candidate = FIX015.candidate_view(clustered)
    endpoint = candidate.starts[1]
    anchor = LAB015._weak_observation(candidate.evaluate_float64(endpoint))
    weak_result = LAB015.WEAK.weak_bracket_rescue(
        point -> LAB015._weak_observation(candidate.evaluate_float64(point)),
        LAB015.WEAK.NormalizedBox(candidate.box.lower, candidate.box.upper),
        endpoint,
        anchor;
        remaining_callbacks=600,
    )
    @test weak_result.status == :seeded
    bracket_match = LAB015.assess_bracket_seeds(
        FIX015.assessor_truth(clustered),
        endpoint,
        weak_result.seeds,
    )
    @test bracket_match.emitted_count == length(weak_result.seeds) > 0
    @test bracket_match.supported_count > 0
    @test !isempty(bracket_match.matched_root_indices)

    safety = FIX015.make_safety_fixture(:stationary_nonroot)
    safety_match = LAB015.assess_point_seeds(
        FIX015.assessor_truth(safety),
        [[0.0, 0.0]],
    )
    @test safety_match.emitted_count == safety_match.unsupported_count == 1
    @test safety_match.supported_count == 0
end

@testset "reference and weak arms preserve the non-answer/work boundary" begin
    linear = FIX015.make_linear_fixture(8, 10^12)
    linear_candidate = FIX015.candidate_view(linear)
    linear_prefilter = LAB015.acquire_shared_prefilter(
        linear_candidate,
        linear_candidate.starts[1],
    )
    baseline = LAB015.run_no_rescue_arm(linear_candidate.starts[1])
    @test baseline.arm == LAB015.NO_RESCUE_ARM
    @test baseline.rescue_weighted_work == 0
    @test baseline.new_seed_count == 0
    @test length(baseline.point_seeds) == 1
    diagnostic = LAB015.run_diagnostic_arm(linear_prefilter)
    @test diagnostic.arm == LAB015.DIAGNOSTIC_ARM
    @test diagnostic.status == :control
    @test diagnostic.rescue_weighted_work == 0
    @test diagnostic.activation
    @test diagnostic.observables.rank_or_condition_trigger

    reference_observed = Dict{Int,Int}()
    reference = LAB015.run_reference_arm(
        linear_candidate,
        linear_prefilter;
        observe_callback=bits -> begin
            reference_observed[bits] = get(reference_observed, bits, 0) + 1
        end,
    )
    @test reference.arm == LAB015.REFERENCE_ARM
    @test reference.status == :unknown
    @test reference.reason == :weighted_oracle_budget_exhausted
    @test reference.rescue_weighted_work == 600
    @test reference.rescue_callbacks == 60
    @test reference_observed == Dict(512 => reference.rescue_callbacks)
    @test reference.new_seed_count == 0
    @test !reference.observables.formal_equal_work_authority

    clustered = FIX015.make_clustered_fixture(2, 4)
    candidate = FIX015.candidate_view(clustered)
    shared_observed = Ref(0)
    prefilter = LAB015.acquire_shared_prefilter(
        candidate,
        candidate.starts[1];
        observe_callback=(bits) -> begin
            @test bits == 53
            shared_observed[] += 1
        end,
    )
    weak_observed = Ref(0)
    weak = LAB015.run_weak_arm(
        candidate,
        prefilter;
        lane=:weak,
        endpoint_ordinal=1,
        observe_callback=(bits) -> begin
            @test bits == 53
            weak_observed[] += 1
        end,
    )
    isotropic = LAB015.run_weak_arm(
        candidate,
        prefilter;
        lane=:isotropic,
        endpoint_ordinal=1,
    )
    suppressed = LAB015.run_weak_arm(
        candidate,
        prefilter;
        lane=:no_bracket,
        endpoint_ordinal=1,
    )
    @test weak.status == :seeded
    @test weak.new_seed_count == length(weak.bracket_seeds) > 0
    @test suppressed.status == :control
    @test suppressed.new_seed_count == 0
    @test isempty(suppressed.bracket_seeds)
    @test weak.rescue_callbacks == isotropic.rescue_callbacks ==
          suppressed.rescue_callbacks == 8
    @test shared_observed[] == 1 + 4length(candidate.starts[1])
    @test weak_observed[] == weak.rescue_callbacks
    @test weak.rescue_weighted_work == isotropic.rescue_weighted_work ==
          suppressed.rescue_weighted_work
    @test all(result -> result.rescue_weighted_work <= 600, (weak, isotropic, suppressed))
    @test !hasproperty(weak, :answer)

    rebound = FIX015.TruthBlindFixture(
        candidate.box,
        point -> candidate.evaluate_float64(point),
        candidate.evaluate_arbitrary,
        candidate.starts,
    )
    stale = LAB015.run_weak_arm(rebound, prefilter; lane=:weak)
    @test stale.status == :unknown
    @test stale.reason == :shared_weak_probe_source_mismatch
    @test stale.rescue_callbacks == 0
end

@testset "bracket assessor rejects forged geometry and preserves all supported roots" begin
    for dimension in (2, 4, 8), root_count in (4, 8)
        base = FIX015.make_clustered_fixture(dimension, root_count)
        class_matches = Vector{Vector{Int}}()
        for record in (
            base,
            FIX015.signed_permutation_replica(base),
            FIX015.orthogonal_replica(base),
        )
            candidate = FIX015.candidate_view(record)
            prefilter = LAB015.acquire_shared_prefilter(candidate, candidate.starts[1])
            result = LAB015.run_weak_arm(candidate, prefilter; lane=:weak)
            @test result.status == :seeded
            match = LAB015.assess_bracket_seeds(
                FIX015.assessor_truth(record),
                candidate.starts[1],
                result.bracket_seeds,
            )
            @test match.supported_count == match.emitted_count == length(result.bracket_seeds)
            @test match.unsupported_count == 0
            @test !isempty(match.matched_root_indices)
            push!(class_matches, match.matched_root_indices)
        end
        @test class_matches[1] == class_matches[2] == class_matches[3]
    end

    record = FIX015.make_clustered_fixture(2, 4)
    candidate = FIX015.candidate_view(record)
    endpoint = candidate.starts[1]
    prefilter = LAB015.acquire_shared_prefilter(candidate, endpoint)
    decomposition = svd(prefilter.fine_jacobian)
    strong = Vector{Float64}(decomposition.V[:, 1])
    strong ./= norm(strong)
    make_seed(lower, upper, left_value, right_value, point, direction) =
        LAB015.WEAK.RefinementSeed(
            lower,
            upper,
            left_value,
            right_value,
            Float64[point...],
            Float64[direction...],
            :weak,
        )
    forged = (
        make_seed(-0.25, 0.25, -1.0, 1.0, endpoint, strong),
        make_seed(-Inf, Inf, -1.0, 1.0, endpoint, strong),
        make_seed(-0.25, 0.25, 1.0, 1.0, endpoint, strong),
        make_seed(-0.25, 0.25, -1.0, 1.0, endpoint, 100 .* strong),
        make_seed(0.25, -0.25, -1.0, 1.0, endpoint, strong),
        make_seed(-0.25, 0.25, -1.0, 1.0, [99.0, 99.0], strong),
    )
    for seed in forged
        match = LAB015.assess_bracket_seeds(
            FIX015.assessor_truth(record),
            endpoint,
            [seed],
        )
        @test match.supported_count == 0
        @test match.unsupported_count == 1
        @test isempty(match.matched_root_indices)
    end

    actual = LAB015.run_weak_arm(candidate, prefilter; lane=:weak)
    first_seed = first(actual.bracket_seeds)
    scaled_seed = LAB015.WEAK.RefinementSeed(
        first_seed.lower_parameter,
        first_seed.upper_parameter,
        first_seed.lower_projected_residual * 1.0e-160,
        first_seed.upper_projected_residual * 1.0e-160,
        copy(first_seed.normalized_point),
        copy(first_seed.probe_direction),
        first_seed.lane,
    )
    original_support = LAB015.assess_bracket_seeds(
        FIX015.assessor_truth(record),
        endpoint,
        [first_seed],
    )
    scaled_support = LAB015.assess_bracket_seeds(
        FIX015.assessor_truth(record),
        endpoint,
        [scaled_seed],
    )
    @test original_support.emitted_count == scaled_support.emitted_count
    @test original_support.supported_count == scaled_support.supported_count
    @test original_support.matched_root_indices == scaled_support.matched_root_indices
    @test original_support.unsupported_count == scaled_support.unsupported_count
    for kind in (:even_multiple_root, :branch_crossing, :guard_crossing)
        safety = FIX015.make_safety_fixture(kind)
        rejected = LAB015.assess_bracket_seeds(
            FIX015.assessor_truth(safety),
            FIX015.candidate_view(safety).starts[1],
            actual.bracket_seeds,
        )
        @test rejected.supported_count == 0
        @test rejected.unsupported_count == length(actual.bracket_seeds)
        @test isempty(rejected.matched_root_indices)
    end
end

@testset "adaptive and combined adapters close the 600-work seed-only ledger" begin
    base = FIX015.make_linear_fixture(2, 10^12)
    base_candidate = FIX015.candidate_view(base)
    setprecision(BigFloat, 256) do
        point = BigFloat[BigFloat(value) for value in base_candidate.starts[1]]
        raw = base_candidate.evaluate_arbitrary(point)
        sample = LAB015._adaptive_sample(base_candidate, point, 256)
        @test sample.semantic_state.branch_identity == raw.branch_identity
        @test sample.semantic_state.branch_margin == raw.branch_margin
        @test sample.semantic_state.guard_identities == (raw.guard_identity,)
        @test sample.semantic_state.guard_margins == (raw.guard_margin,)
        @test sample.semantic_state.domain_identities == (raw.domain_identity,)
        @test sample.semantic_state.domain_margins == (raw.domain_margin,)
        @test !hasproperty(sample, :target)
    end
    signatures = NamedTuple[]
    for record in (
        base,
        FIX015.signed_permutation_replica(base),
        FIX015.orthogonal_replica(base),
    )
        candidate = FIX015.candidate_view(record)
        prefilter = LAB015.acquire_shared_prefilter(candidate, candidate.starts[1])
        observed = Dict{Int,Int}()
        result = LAB015.run_adaptive_arm(
            candidate,
            prefilter;
            observe_callback=bits -> begin
                observed[bits] = get(observed, bits, 0) + 1
            end,
        )
        @test result.status == :seed_ready
        @test result.reason == :none
        @test result.activation
        @test result.new_seed_count == length(result.point_seeds) == 1
        @test result.rescue_weighted_work <= 600
        @test result.rescue_callbacks == sum(values(result.requested_precision_counts))
        @test Dict(string(bits) => count for (bits, count) in observed) ==
              result.requested_precision_counts
        @test result.rescue_weighted_work == sum(
            count * (tier == "128" ? 3 : tier == "256" ? 5 : 10) for
            (tier, count) in result.requested_precision_counts
        )
        match = LAB015.assess_point_seeds(
            FIX015.assessor_truth(record),
            result.point_seeds,
        )
        @test match.supported_count == 1
        @test match.unsupported_count == 0
        @test !hasproperty(result, :answer)
        @test result.observables.confirmation_site == "same_source_model"
        @test result.observables.same_source_model_confirmed
        @test !result.observables.refined_endpoint_high_precision_confirmed
        @test result.observables.selected_precision_bits == 256
        @test result.observables.confirmation_precision_bits == 512
        @test result.observables.selected_numerical_rank == 2
        @test result.observables.confirmation_numerical_rank == 2
        @test result.observables.rank_stable
        @test result.observables.correction_stable
        @test parse(BigFloat, result.observables.cross_tier_residual_disagreement) <=
              parse(BigFloat, result.observables.cross_tier_residual_tolerance)
        @test parse(BigFloat, result.observables.cross_tier_jacobian_disagreement) <=
              parse(BigFloat, result.observables.cross_tier_jacobian_tolerance)
        @test parse(BigFloat, result.observables.cross_tier_correction_disagreement) <=
              parse(BigFloat, result.observables.cross_tier_correction_tolerance)
        push!(signatures, (;
            status=result.status,
            reason=result.reason,
            work=result.rescue_weighted_work,
            counts=sort!(collect(result.requested_precision_counts)),
            path=result.observables.precision_path,
            matched=match.matched_root_indices,
        ))
    end
    @test signatures[1] == signatures[2] == signatures[3]

    clustered = FIX015.make_clustered_fixture(2, 4)
    candidate = FIX015.candidate_view(clustered)
    prefilter = LAB015.acquire_shared_prefilter(candidate, candidate.starts[1])
    combined_observed = Dict{Int,Int}()
    combined = LAB015.run_combined_arm(
        candidate,
        prefilter;
        observe_callback=bits -> begin
            combined_observed[bits] = get(combined_observed, bits, 0) + 1
        end,
    )
    @test combined.rescue_weighted_work <= 600
    @test combined.rescue_callbacks == sum(values(combined.requested_precision_counts))
    @test Dict((bits <= 53 ? "float64" : string(bits)) => count for
               (bits, count) in combined_observed) == combined.requested_precision_counts
    @test combined.rescue_weighted_work ==
          get(combined.requested_precision_counts, "float64", 0) +
          3get(combined.requested_precision_counts, "128", 0) +
          5get(combined.requested_precision_counts, "256", 0) +
          10get(combined.requested_precision_counts, "512", 0)
    @test combined.observables.strict_bracket_detected
    @test combined.activation
    @test !hasproperty(combined, :answer)
    @test combined.observables.confirmation_site == "same_source_model"
    @test !combined.observables.refined_endpoint_high_precision_confirmed
    @test length(combined.observables.adaptive_attempt_observables) ==
          combined.observables.adaptive_attempt_count
    @test all(
        attempt -> attempt.confirmation_site == "same_source_model" &&
                   !attempt.refined_endpoint_high_precision_confirmed,
        combined.observables.adaptive_attempt_observables,
    )
    if combined.status == :seed_ready
        match = LAB015.assess_point_seeds(
            FIX015.assessor_truth(clustered),
            combined.point_seeds,
        )
        @test match.unsupported_count == 0
    else
        @test isempty(combined.point_seeds)
    end

    evaluate_above = function (point)
        T = eltype(point)
        residual = T[
            point[1] - T(1) / T(4),
            (point[2] + T(1) / T(8)) / T(1_000_000_000),
        ]
        return FIX015.FixtureEvaluation(
            residual,
            zero(T),
            :branch,
            :guard,
            :domain,
            one(T),
            one(T),
            one(T),
            true,
        )
    end
    above_candidate = FIX015.TruthBlindFixture(
        FIX015.FiniteBox(2),
        point -> evaluate_above(Float64[point...]),
        evaluate_above,
        [zeros(2)],
    )
    above_prefilter = LAB015.acquire_shared_prefilter(above_candidate, zeros(2))
    @test above_prefilter.status == :ready
    @test above_prefilter.numerical_rank == 2
    @test above_prefilter.condition_class == :above_trigger
    @test LAB015._routed_condition(above_prefilter) > LAB015.CONDITION_TRIGGER
    above = LAB015.run_adaptive_arm(above_candidate, above_prefilter)
    @test above.status == :seed_ready
    @test above.observables.selected_precision_bits == 128
    @test above.observables.confirmation_precision_bits == 256
    @test above.observables.precision_path == (128, 256)
    @test above.requested_precision_counts == Dict("128" => 10, "256" => 9)
    @test above.rescue_weighted_work == 75
end
