using GeoTargetExact
using Nemo
using Test

const TEST_ZZX, TEST_X = polynomial_ring(ZZ, "x")
const TEST_QQBAR = algebraic_closure(QQ)

bigfloat_provider(function_value) = bits -> setprecision(BigFloat, bits) do
    function_value()
end

function algebraic_provider(value)
    return bits -> setprecision(BigFloat, bits) do
        BigFloat(ArbField(bits)(value))
    end
end

const FAST_OPTIONS = RecognitionOptions(
    degree_limits=(1, 2, 4, 8),
    height_bits=(8,),
    base_precision_bits=256,
    confirmation_extra_bits=128,
)

struct EmptyLeafFixture end

@testset "AlgebraicReal exact arithmetic and leaf audit" begin
    square_root = sqrt(AlgebraicReal(2))
    @test square_root * square_root == AlgebraicReal(2)
    @test square_root + 1 - 1 == square_root
    @test abs(-square_root) == square_root
    @test sign(-square_root) == -one(AlgebraicReal)
    @test AlgebraicReal(3 // 7) * 7 == 3
    @test AlgebraicReal(0.5) == AlgebraicReal(Rational{BigInt}(0.5))
    @test isfinite(square_root)
    @test_throws DomainError AlgebraicReal(Inf)
    @test_throws DomainError sqrt(AlgebraicReal(-1))

    @test exact_leaf_safe((square_root, 3 // 7, (2,)))
    @test !exact_leaf_safe((square_root, 0.5))
    @test !exact_leaf_safe((nested=(value=big"1.25",),))

    safe_cycle = Any[1]
    push!(safe_cycle, safe_cycle)
    unsafe_cycle = Any[1.0]
    push!(unsafe_cycle, unsafe_cycle)
    safe_dictionary = Dict{Any,Any}(:exact => square_root)
    safe_dictionary[:self] = safe_dictionary
    unsafe_dictionary_key = Dict{Any,Any}(0.5 => square_root)
    unsafe_dictionary_value = Dict{Any,Any}(:inexact => 0.5)
    @test exact_leaf_safe(safe_cycle)
    @test !exact_leaf_safe(unsafe_cycle)
    @test exact_leaf_safe(safe_dictionary)
    @test !exact_leaf_safe(unsafe_dictionary_key)
    @test !exact_leaf_safe(unsafe_dictionary_value)
    @test !exact_leaf_safe(identity)
    @test !exact_leaf_safe(Main)
    @test !exact_leaf_safe(Int)
    @test !exact_leaf_safe(Ptr{Nothing}(0))
    @test !exact_leaf_safe(current_task())
    @test !exact_leaf_safe(EmptyLeafFixture())
end

@testset "production recognition ladder contract" begin
    defaults = RecognitionOptions()
    @test defaults.degree_limits == (1, 2, 4, 8, 12)
    @test defaults.height_bits == (8, 16, 32, 64)
    @test working_precision(1, 8) == 768
    @test working_precision(4, 64) == 768
    @test working_precision(8, 64) == 1280
    @test working_precision(12, 64) == 1792
end

@testset "bounded rational reconstruction" begin
    rational_provider = bigfloat_provider(() -> BigFloat(3) / BigFloat(7))
    value = rational_provider(256)
    @test bounded_rational_reconstruction(value, 8; precision_bits=256) == 3 // 7
    @test bounded_rational_reconstruction(
        bigfloat_provider(() -> sqrt(BigFloat(2)))(256),
        8;
        precision_bits=256,
    ) === nothing

    candidate = recognize_algebraic(rational_provider; options=FAST_OPTIONS)
    @test candidate !== nothing
    @test candidate.method == "bounded_rational_reconstruction"
    @test candidate.descriptor.coefficients == (-3, 7)
    @test reconstruct_descriptor(candidate.descriptor) == AlgebraicReal(3 // 7)
end

@testset "owned PSLQ typed contract" begin
    sqrt_two = bigfloat_provider(() -> sqrt(BigFloat(2)))(256)
    first = pslq_relation(sqrt_two, 2, 8; precision_bits=256)
    second = pslq_relation(sqrt_two, 2, 8; precision_bits=256)
    @test first.failure == PSLQ_NONE
    @test first.relation == (-2, 0, 1)
    @test first.iterations == second.iterations
    @test first.relation == second.relation
    @test first.residual == second.residual

    rational = bigfloat_provider(() -> BigFloat(3) / BigFloat(7))(256)
    rational_result = pslq_relation(rational, 2, 8; precision_bits=256)
    @test rational_result.failure == PSLQ_NONE
    @test rational_result.relation == (-3, 7)

    lll_relation = nemo_lll_relation(sqrt_two, 2, 8; precision_bits=256)
    @test lll_relation == first.relation

    pi_value = bigfloat_provider(() -> BigFloat(pi))(256)
    false_result = pslq_relation(
        pi_value,
        4,
        8;
        precision_bits=256,
        max_iterations=2_000,
    )
    @test false_result.relation === nothing
    @test false_result.failure != PSLQ_NONE

    short_result = pslq_relation(
        pi_value,
        4,
        8;
        precision_bits=256,
        max_iterations=1,
    )
    @test short_result.failure == PSLQ_MAX_ITERATIONS

    low_precision = bigfloat_provider(() -> sqrt(BigFloat(2)))(128)
    low_precision_result = pslq_relation(
        low_precision,
        8,
        8;
        precision_bits=128,
    )
    @test low_precision_result.failure == PSLQ_INSUFFICIENT_PRECISION
    @test low_precision_result.relation === nothing

    height_overflow_value = bigfloat_provider(() -> sqrt(BigFloat(257)))(256)
    height_overflow = pslq_relation(
        height_overflow_value,
        2,
        8;
        precision_bits=256,
        max_iterations=2_000,
    )
    @test height_overflow.failure == PSLQ_COEFFICIENT_LIMIT
    @test height_overflow.relation === nothing

    oversized = big(typemax(Int)) + 1
    invalid_contracts = (
        pslq_relation(sqrt_two, true, 8; precision_bits=256),
        pslq_relation(sqrt_two, 2, true; precision_bits=256),
        pslq_relation(sqrt_two, oversized, 8; precision_bits=256),
        pslq_relation(sqrt_two, 2, oversized; precision_bits=256),
        pslq_relation(sqrt_two, 2, 8; precision_bits=oversized),
        pslq_relation(sqrt_two, 2, 8; precision_bits=256, max_iterations=oversized),
        pslq_relation(sqrt_two, typemax(Int), typemax(Int); precision_bits=256),
    )
    @test all(result -> result.failure == PSLQ_INVALID_INPUT, invalid_contracts[1:6])
    @test invalid_contracts[7].failure == PSLQ_INSUFFICIENT_PRECISION
    @test all(result -> result.relation === nothing, invalid_contracts)
end

@testset "dual-precision algebraic recognition" begin
    sqrt_two = sqrt(TEST_QQBAR(2))
    degree_five = only(filter(isreal, roots(TEST_QQBAR, TEST_X^5 - TEST_X - 1)))
    degree_eight = last(sort(filter(isreal, roots(TEST_QQBAR, TEST_X^8 - 2))))
    sqrt_two_plus_sqrt_three = sqrt(TEST_QQBAR(2)) + sqrt(TEST_QQBAR(3))

    fixtures = (
        (sqrt_two, (-2, 0, 1), 2),
        (degree_five, (-1, -1, 0, 0, 0, 1), 1),
        (degree_eight, (-2, 0, 0, 0, 0, 0, 0, 0, 1), 2),
        (sqrt_two_plus_sqrt_three, (1, 0, -10, 0, 1), 4),
    )
    for (exact_value, coefficients, root_index) in fixtures
        candidate = recognize_algebraic(algebraic_provider(exact_value); options=FAST_OPTIONS)
        @test candidate !== nothing
        @test candidate.method == "owned_pslq_v1"
        @test candidate.descriptor.coefficients == coefficients
        @test candidate.descriptor.root_index == root_index
        reconstructed = reconstruct_descriptor(candidate.descriptor)
        @test reconstructed !== nothing
        @test algebraic_value(reconstructed) == exact_value

        document = descriptor_document(candidate.descriptor)
        decoded = descriptor_from_document(document)
        @test decoded !== nothing
        @test same_algebraic_identity(decoded, candidate.descriptor)
    end
end

@testset "relation normalization and factor selection" begin
    approximation = bigfloat_provider(() -> sqrt(BigFloat(2)))(256)
    expected = (-2, 0, 1)
    @test normalize_polynomial((-4, 0, 2, 0)) == expected

    # Reducible relation, nonprimitive relation, and a repeated relation must
    # all reduce to the same irreducible minimal polynomial candidate.
    relations = (
        (6, -2, -3, 1),       # (x^2 - 2)(x - 3)
        (-4, 0, 2),           # 2(x^2 - 2)
        (4, 0, -4, 0, 1),     # (x^2 - 2)^2
    )
    descriptors = map(relations) do relation
        descriptor_from_relation(
            relation,
            approximation;
            precision_bits=256,
            height_bits=8,
        )
    end
    @test all(descriptor -> descriptor !== nothing, descriptors)
    @test all(descriptor -> descriptor.coefficients == expected, descriptors)

    valid = first(descriptors)
    nonprimitive_claim = AlgebraicDescriptor(
        (-4, 0, 2),
        valid.lower,
        valid.upper,
        valid.root_index,
    )
    reducible_claim = AlgebraicDescriptor(
        (6, -2, -3, 1),
        valid.lower,
        valid.upper,
        valid.root_index,
    )
    repeated_claim = AlgebraicDescriptor(
        (4, 0, -4, 0, 1),
        valid.lower,
        valid.upper,
        valid.root_index,
    )
    @test reconstruct_descriptor(nonprimitive_claim) === nothing
    @test reconstruct_descriptor(reducible_claim) === nothing
    @test reconstruct_descriptor(repeated_claim) === nothing
end

@testset "false relation and precision disagreement fail closed" begin
    pi_provider = bigfloat_provider(() -> BigFloat(pi))
    @test recognize_algebraic(pi_provider; options=FAST_OPTIONS) === nothing

    disagreeing_provider = bits -> if bits == 256
        bigfloat_provider(() -> sqrt(BigFloat(2)))(bits)
    else
        bigfloat_provider(() -> sqrt(BigFloat(3)))(bits)
    end
    @test recognize_at(
        disagreeing_provider,
        2,
        8;
        options=RecognitionOptions(
            degree_limits=(2,),
            height_bits=(8,),
            base_precision_bits=256,
            confirmation_extra_bits=128,
        ),
    ) === nothing
end

@testset "certificate interval and root-index tampering fail closed" begin
    candidate = recognize_algebraic(
        bigfloat_provider(() -> sqrt(BigFloat(2)));
        options=FAST_OPTIONS,
    )
    descriptor = candidate.descriptor

    outside_interval = AlgebraicDescriptor(
        descriptor.coefficients,
        2 // 1,
        3 // 1,
        descriptor.root_index,
    )
    wrong_root = AlgebraicDescriptor(
        descriptor.coefficients,
        descriptor.lower,
        descriptor.upper,
        1,
    )
    missing_root = AlgebraicDescriptor(
        descriptor.coefficients,
        descriptor.lower,
        descriptor.upper,
        99,
    )
    @test reconstruct_descriptor(outside_interval) === nothing
    @test reconstruct_descriptor(wrong_root) === nothing
    @test reconstruct_descriptor(missing_root) === nothing
    @test_throws ArgumentError AlgebraicDescriptor(
        descriptor.coefficients,
        descriptor.lower,
        descriptor.upper,
        true,
    )

    interval_document = descriptor_document(descriptor)
    interval_document["isolating_interval"]["lower"] = Dict(
        "numerator" => "2",
        "denominator" => "1",
    )
    interval_document["isolating_interval"]["upper"] = Dict(
        "numerator" => "3",
        "denominator" => "1",
    )
    @test descriptor_from_document(interval_document) === nothing

    root_document = descriptor_document(descriptor)
    root_document["real_root_index"] = 99
    @test descriptor_from_document(root_document) === nothing

    boolean_root_document = descriptor_document(descriptor)
    boolean_root_document["real_root_index"] = true
    @test descriptor_from_document(boolean_root_document) === nothing

    noncanonical_document = descriptor_document(descriptor)
    noncanonical_document["coefficients"][1] = "-02"
    @test descriptor_from_document(noncanonical_document) === nothing
end

@testset "Phase B C3A boundary is explicit" begin
    unsupported = replay_c3a(:fixture)
    @test unsupported isa C3AReplayUnsupported
    @test occursin("Phase B", unsupported.detail)
end
