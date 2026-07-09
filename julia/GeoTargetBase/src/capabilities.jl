@enum Capability::UInt8 begin
    C0 = 0
    C1 = 1
    C2 = 2
    C3V = 3
    C3A = 4
end

"""Immutable bit set of explicitly declared operator capabilities."""
struct CapabilitySet
    bits::UInt8

    function CapabilitySet(bits::UInt8)
        bits & 0xe0 == 0 || throw(
            InvariantError(:invalid_capability_bits, "capability bits outside C0..C3A are set"),
        )
        return new(bits)
    end
end

CapabilitySet() = CapabilitySet(0x00)

function CapabilitySet(capabilities::Capability...)
    bits = UInt8(0)
    for capability in capabilities
        bits |= UInt8(1) << UInt8(capability)
    end
    return CapabilitySet(bits)
end

supports(set::CapabilitySet, capability::Capability) =
    !iszero(set.bits & (UInt8(1) << UInt8(capability)))

Base.in(capability::Capability, set::CapabilitySet) = supports(set, capability)
Base.isempty(set::CapabilitySet) = iszero(set.bits)
Base.length(set::CapabilitySet) = count_ones(set.bits)
Base.iterate(set::CapabilitySet, state::Int = 0) = _iterate_capabilities(set, state)

function _iterate_capabilities(set::CapabilitySet, state::Int)
    state > Int(C3A) && return nothing
    capability = Capability(state)
    if supports(set, capability)
        return capability, state + 1
    end
    return _iterate_capabilities(set, state + 1)
end

function require_capability(
    set::CapabilitySet,
    capability::Capability,
    subject::AbstractString = "operator",
)
    supports(set, capability) && return nothing
    throw(CapabilityError(capability, String(subject)))
end

@enum SmoothnessClass::UInt8 begin
    SMOOTHNESS_UNKNOWN = 0
    SMOOTH_C1 = 1
    PIECEWISE_SMOOTH = 2
    LOCALLY_LIPSCHITZ = 3
    DECLARED_NONSMOOTH = 4
end

@enum DerivativeMode::UInt8 begin
    DERIVATIVE_NONE = 0
    DERIVATIVE_AUTODIFF = 1
    DERIVATIVE_JACOBIAN = 2
    DERIVATIVE_JVP = 3
    DERIVATIVE_VJP = 4
end

"""
Julia-only implementations and serializable capability metadata for an operation.

Functions remain outside the JSON protocol. `generic_numeric=true` declares that
the primary evaluator is intentionally type-generic and can implement C2/C3V
without a dedicated callback.
"""
struct OperatorKernel{E,D,H,V,A}
    evaluator::E
    derivative::D
    high_precision::H
    validated::V
    algebraic_prover::A
    capabilities::CapabilitySet
    smoothness::SmoothnessClass
    derivative_mode::DerivativeMode
    generic_numeric::Bool
    deterministic::Bool

    function OperatorKernel(
        evaluator::E;
        derivative::D = nothing,
        high_precision::H = nothing,
        validated::V = nothing,
        algebraic_prover::A = nothing,
        capabilities::CapabilitySet = CapabilitySet(C0),
        smoothness::SmoothnessClass = SMOOTHNESS_UNKNOWN,
        derivative_mode::DerivativeMode = DERIVATIVE_NONE,
        generic_numeric::Bool = false,
        deterministic::Bool = true,
    ) where {E,D,H,V,A}
        evaluator === nothing && throw(
            InvariantError(:missing_evaluator, "an OperatorKernel requires a discovery evaluator"),
        )
        supports(capabilities, C0) || throw(
            InvariantError(:missing_c0, "an OperatorKernel must explicitly declare C0"),
        )
        derivative_mode == DERIVATIVE_NONE && derivative !== nothing && throw(
            InvariantError(
                :derivative_mode_mismatch,
                "a derivative callback requires a non-NONE derivative mode",
            ),
        )
        derivative_mode != DERIVATIVE_NONE && !supports(capabilities, C1) && throw(
            InvariantError(:missing_c1, "a derivative mode requires capability C1"),
        )
        derivative_mode in (DERIVATIVE_JACOBIAN, DERIVATIVE_JVP, DERIVATIVE_VJP) &&
            derivative === nothing && throw(
                InvariantError(
                    :missing_derivative_callback,
                    "an analytic derivative mode requires a derivative callback",
                ),
            )
        supports(capabilities, C2) && high_precision === nothing && !generic_numeric && throw(
            InvariantError(
                :missing_high_precision_kernel,
                "C2 requires a dedicated high-precision callback or generic_numeric=true",
            ),
        )
        supports(capabilities, C3V) && validated === nothing && !generic_numeric && throw(
            InvariantError(
                :missing_validated_kernel,
                "C3V requires a validated callback or generic_numeric=true",
            ),
        )
        supports(capabilities, C3A) && algebraic_prover === nothing && throw(
            InvariantError(
                :missing_algebraic_prover,
                "C3A requires an algebraic proof callback",
            ),
        )
        return new{E,D,H,V,A}(
            evaluator,
            derivative,
            high_precision,
            validated,
            algebraic_prover,
            capabilities,
            smoothness,
            derivative_mode,
            generic_numeric,
            deterministic,
        )
    end
end
