"""S4 result plus the complete fail-closed applicability trace."""
struct S4VariantOutcome
    core::ExperimentalOutcome
    diagnostics::Dict{String,Any}
end

"""Metadata-free black-box oracle exposed to both S4 numerical mechanisms."""
struct S4BlackBoxOracle{R,T}
    dimension::Int
    residual_dimension::Int
    capability::Symbol
    residual::R
    target::T

    function S4BlackBoxOracle(
        dimension::Integer,
        residual_dimension::Integer,
        capability::Symbol,
        residual::R,
        target::T,
    ) where {R,T}
        dimension > 0 || throw(ArgumentError("S4 dimension must be positive"))
        residual_dimension > 0 || throw(
            ArgumentError("S4 residual dimension must be positive"),
        )
        capability == :C2 || throw(ArgumentError("S4 requires C2 capability"))
        return new{R,T}(
            Int(dimension),
            Int(residual_dimension),
            capability,
            residual,
            target,
        )
    end
end

function _evaluate_residual!(ledger, oracle::S4BlackBoxOracle, x, precision_bits)
    _charge_callback!(ledger, :residual, precision_bits)
    return _finite_vector(
        oracle.residual(x),
        oracle.residual_dimension,
        "S4 residual callback",
    )
end

function _evaluate_target!(ledger, oracle::S4BlackBoxOracle, x, precision_bits)
    _charge_callback!(ledger, :target, precision_bits)
    value = oracle.target(x)
    value isa Real && isfinite(value) || throw(
        ArgumentError("S4 target callback must return a finite real"),
    )
    return value
end

"""S4 input capability with no id, family, group, Gold, or derivative fixture."""
struct S4CandidateInput{O<:S4BlackBoxOracle}
    oracle::O
    endpoint::Vector{Float64}

    function S4CandidateInput(
        oracle::O,
        endpoint::AbstractVector{<:Real},
    ) where {O<:S4BlackBoxOracle}
        frozen = Float64[endpoint...]
        length(frozen) == oracle.dimension || throw(DimensionMismatch("S4 endpoint"))
        all(isfinite, frozen) || throw(ArgumentError("S4 endpoint must be finite"))
        return new{O}(oracle, frozen)
    end
end

function s4_candidate_input(input::CandidateInput)
    oracle = input.oracle
    black_box = S4BlackBoxOracle(
        oracle.dimension,
        oracle.residual_dimension,
        oracle.capability,
        oracle.residual,
        oracle.target,
    )
    return S4CandidateInput(black_box, input.endpoint)
end

function S4VariantOutcome(core::ExperimentalOutcome, diagnostics::AbstractDict)
    return S4VariantOutcome(core, Dict{String,Any}(
        String(key) => value for (key, value) in pairs(diagnostics)
    ))
end

"""Internal candidate rejection; work already charged remains observable."""
struct _S4CandidateReject <: Exception
    reason::String
end

Base.showerror(io::IO, error::_S4CandidateReject) = print(io, error.reason)

"""Internal analytic-control rejection, deliberately distinct from the candidate."""
struct _S4ControlReject <: Exception
    reason::String
end

Base.showerror(io::IO, error::_S4ControlReject) = print(io, error.reason)

function _s4_unknown_core(variant, route, reason, ledger; semantic=nothing)
    return ExperimentalOutcome(
        variant,
        route,
        :unknown,
        reason,
        semantic,
        nothing,
        _work_snapshot(ledger),
    )
end

"""Capture the promotion timestamp once and fail closed if it reached the deadline."""
function _s4_checked_work_snapshot!(ledger::_WorkLedger)
    stopped = UInt64(ledger.clock_ns())
    if stopped >= ledger.deadline_ns
        ledger.deadline_reached = true
        throw(ExperimentBudgetExceeded(:deadline))
    end
    elapsed = stopped >= ledger.started_ns ?
              Float64(stopped - ledger.started_ns) / 1.0e9 : 0.0
    calls = Tuple(
        (precision_bits=bits, callbacks=ledger.calls_by_precision[bits]) for
        bits in sort!(collect(keys(ledger.calls_by_precision)))
    )
    return WorkSnapshot(
        ledger.callbacks,
        ledger.residual_calls,
        ledger.target_calls,
        ledger.jacobian_calls,
        ledger.factorization_calls,
        ledger.iterations,
        ledger.precision_equivalent_oracle_work,
        calls,
        elapsed,
        ledger.maximum_precision_bits,
        ledger.budget_exhausted,
        ledger.deadline_reached,
    )
end
