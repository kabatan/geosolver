abstract type GeoTargetError <: Exception end

struct InvariantError <: GeoTargetError
    code::Symbol
    message::String
end

Base.showerror(io::IO, error::InvariantError) =
    print(io, "GeoTarget invariant ", error.code, ": ", error.message)

struct CapabilityError <: GeoTargetError
    capability::Capability
    subject::String
end

Base.showerror(io::IO, error::CapabilityError) = print(
    io,
    "GeoTarget capability ",
    error.capability,
    " is unavailable for ",
    error.subject,
)

@enum EvalStatus::UInt8 begin
    EVAL_OK = 0
    EVAL_INVALID_DOMAIN = 1
    EVAL_NONFINITE = 2
    EVAL_UNSUPPORTED_CAPABILITY = 3
    EVAL_PLUGIN_ERROR = 4
    EVAL_INVALID_BRANCH = 5
    EVAL_AMBIGUOUS_BRANCH = 6
end

@enum SearchStatus::UInt8 begin
    SEARCH_DEADLINE_REACHED = 0
    SEARCH_CANCELLED = 1
    SEARCH_RESOURCE_EXHAUSTED = 2
    SEARCH_FINISHED_UNKNOWN = 3
    SEARCH_COMPLETE_CERTIFIED = 4
    SEARCH_EMPTY_CERTIFIED = 5
end

@enum TargetImageStatus::UInt8 begin
    TARGET_IMAGE_UNKNOWN = 0
    TARGET_FINITE_OBSERVED = 1
    TARGET_LIKELY_CONTINUOUS = 2
    TARGET_COMPLETE_CERTIFIED = 3
    TARGET_EMPTY_CERTIFIED = 4
end

"""Immutable candidates from a finite multi-valued construction."""
struct Choice{C<:Tuple,K<:Tuple,M<:Tuple}
    candidates::C
    keys::K
    validity_margins::M

    function Choice(candidates, keys, validity_margins)
        frozen_candidates = tuple((deepcopy(candidate) for candidate in candidates)...)
        frozen_keys = tuple((key isa ChoiceKey ? key : ChoiceKey(key) for key in keys)...)
        frozen_margins = tuple((deepcopy(margin) for margin in validity_margins)...)
        count = length(frozen_candidates)
        length(frozen_keys) == count || throw(
            InvariantError(:choice_length_mismatch, "each candidate requires exactly one stable key"),
        )
        length(frozen_margins) == count || throw(
            InvariantError(
                :choice_length_mismatch,
                "each candidate requires exactly one validity margin",
            ),
        )
        allunique(frozen_keys) || throw(
            InvariantError(:duplicate_choice_key, "choice keys must be unique within one Choice"),
        )
        return new{typeof(frozen_candidates),typeof(frozen_keys),typeof(frozen_margins)}(
            frozen_candidates,
            frozen_keys,
            frozen_margins,
        )
    end
end

Base.length(choice::Choice) = length(choice.candidates)
Base.isempty(choice::Choice) = isempty(choice.candidates)
Base.getindex(choice::Choice, index::Int) = choice.candidates[index]

"""A selector result that preserves branch identity and both relevant margins."""
struct Selection{T,K,V,S}
    value::T
    key::K
    validity_margin::V
    selector_margin::S

    function Selection(choice::Choice, index::Integer, selector_margin)
        1 <= index <= length(choice) || throw(
            InvariantError(:invalid_choice_index, "selection index is outside its Choice"),
        )
        value = deepcopy(choice.candidates[index])
        key = choice.keys[index]
        validity_margin = deepcopy(choice.validity_margins[index])
        frozen_selector_margin = deepcopy(selector_margin)
        return new{
            typeof(value),
            typeof(key),
            typeof(validity_margin),
            typeof(frozen_selector_margin),
        }(value, key, validity_margin, frozen_selector_margin)
    end
end
