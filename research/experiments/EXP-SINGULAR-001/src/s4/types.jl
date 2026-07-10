"""S4 result plus the complete fail-closed applicability trace."""
struct S4VariantOutcome
    core::ExperimentalOutcome
    diagnostics::Dict{String,Any}
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
