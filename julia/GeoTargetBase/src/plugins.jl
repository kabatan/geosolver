struct KeywordTypeSpec
    name::String
    type_id::TypeId
    required::Bool

    function KeywordTypeSpec(name::AbstractString, type_id::TypeId; required::Bool = true)
        return new(_canonical_name(name, "keyword type name"), type_id, required)
    end
end

Base.isless(left::KeywordTypeSpec, right::KeywordTypeSpec) = isless(left.name, right.name)

"""One typed callable signature in plugin metadata."""
struct SignatureSpec{A<:Tuple,K<:Tuple}
    arguments::A
    keywords::K
    output::TypeId
    variadic::Bool

    function SignatureSpec(
        arguments,
        output::TypeId;
        keywords = (),
        variadic::Bool = false,
    )
        frozen_arguments = tuple((argument::TypeId for argument in arguments)...)
        frozen_keywords = tuple(
            (
                keyword isa KeywordTypeSpec ? keyword : KeywordTypeSpec(keyword...)
                for keyword in keywords
            )...,
        )
        ordered_keywords = Tuple(sort(collect(frozen_keywords); by = keyword -> keyword.name))
        allunique(map(keyword -> keyword.name, ordered_keywords)) || throw(
            InvariantError(
                :duplicate_signature_keyword,
                "signature keyword names must be unique",
            ),
        )
        variadic && isempty(frozen_arguments) && throw(
            InvariantError(
                :invalid_variadic_signature,
                "a variadic signature requires a final repeated argument type",
            ),
        )
        return new{typeof(frozen_arguments),typeof(ordered_keywords)}(
            frozen_arguments,
            ordered_keywords,
            output,
            variadic,
        )
    end
end

function _freeze_signatures(signatures)
    frozen = tuple((signature::SignatureSpec for signature in signatures)...)
    isempty(frozen) && throw(
        InvariantError(:missing_signature, "an operation must declare at least one signature"),
    )
    allunique(frozen) || throw(
        InvariantError(:duplicate_signature, "an operation declares the same signature twice"),
    )
    return frozen
end

function _documentation(value::AbstractString)
    return String(value)
end

"""A nominal plugin-owned type and its optional protocol codec."""
struct TypeSpec{T,E,D}
    id::TypeId
    julia_type::T
    encoder::E
    decoder::D
    documentation::String

    function TypeSpec(
        id::TypeId,
        julia_type::T;
        encoder::E = nothing,
        decoder::D = nothing,
        documentation::AbstractString = "",
    ) where {T,E,D}
        xor(encoder === nothing, decoder === nothing) && throw(
            InvariantError(
                :incomplete_type_codec,
                "a TypeSpec must provide both encoder and decoder, or neither",
            ),
        )
        return new{T,E,D}(id, julia_type, encoder, decoder, _documentation(documentation))
    end
end

struct PrimitiveSpec{S<:Tuple,K}
    id::PrimitiveId
    signatures::S
    kernel::K
    documentation::String

    function PrimitiveSpec(
        id::PrimitiveId,
        signatures,
        kernel::OperatorKernel;
        documentation::AbstractString = "",
    )
        frozen_signatures = _freeze_signatures(signatures)
        return new{typeof(frozen_signatures),typeof(kernel)}(
            id,
            frozen_signatures,
            kernel,
            _documentation(documentation),
        )
    end
end

@enum RelationTruthPolicy::UInt8 begin
    RELATION_TRUTH_REQUIRED = 0
    RELATION_TRUTH_APPROXIMATE_ZERO = 1
end

"""An equality relation with separate optimization residual and truth predicate."""
struct RelationSpec{S<:Tuple,K,T}
    id::PrimitiveId
    signatures::S
    residual_kernel::K
    truth::T
    truth_policy::RelationTruthPolicy
    scale_hint::Union{Nothing,Float64}
    documentation::String

    function RelationSpec(
        id::PrimitiveId,
        signatures,
        residual_kernel::OperatorKernel;
        truth = nothing,
        truth_policy::RelationTruthPolicy = RELATION_TRUTH_REQUIRED,
        scale_hint::Union{Nothing,Real} = nothing,
        documentation::AbstractString = "",
    )
        frozen_signatures = _freeze_signatures(signatures)
        frozen_scale = _validate_scale_hint(scale_hint)
        truth === nothing && truth_policy != RELATION_TRUTH_REQUIRED && throw(
            InvariantError(
                :truth_policy_without_predicate,
                "an approximate truth policy requires an explicit truth predicate",
            ),
        )
        return new{typeof(frozen_signatures),typeof(residual_kernel),typeof(truth)}(
            id,
            frozen_signatures,
            residual_kernel,
            truth,
            truth_policy,
            frozen_scale,
            _documentation(documentation),
        )
    end
end

"""A validity margin with a DSL default; each problem binds strictness explicitly."""
struct GuardSpec{S<:Tuple,K}
    id::PrimitiveId
    signatures::S
    margin_kernel::K
    default_strict::Bool
    scale_hint::Union{Nothing,Float64}
    documentation::String

    function GuardSpec(
        id::PrimitiveId,
        signatures,
        margin_kernel::OperatorKernel;
        default_strict::Bool = true,
        scale_hint::Union{Nothing,Real} = nothing,
        documentation::AbstractString = "",
    )
        frozen_signatures = _freeze_signatures(signatures)
        frozen_scale = _validate_scale_hint(scale_hint)
        return new{typeof(frozen_signatures),typeof(margin_kernel)}(
            id,
            frozen_signatures,
            margin_kernel,
            default_strict,
            frozen_scale,
            _documentation(documentation),
        )
    end
end

"""A primitive domain margin and optional singularity indicator."""
struct DomainSpec{S<:Tuple,K,G}
    id::PrimitiveId
    signatures::S
    margin_kernel::K
    singularity::G
    default_strict::Bool
    documentation::String

    function DomainSpec(
        id::PrimitiveId,
        signatures,
        margin_kernel::OperatorKernel;
        singularity = nothing,
        default_strict::Bool = true,
        documentation::AbstractString = "",
    )
        frozen_signatures = _freeze_signatures(signatures)
        return new{typeof(frozen_signatures),typeof(margin_kernel),typeof(singularity)}(
            id,
            frozen_signatures,
            margin_kernel,
            singularity,
            default_strict,
            _documentation(documentation),
        )
    end
end

"""A finite multi-valued construction whose evaluator returns Choice."""
struct BranchSpec{S<:Tuple,K}
    id::PrimitiveId
    signatures::S
    candidate_type::TypeId
    kernel::K
    documentation::String

    function BranchSpec(
        id::PrimitiveId,
        signatures,
        candidate_type::TypeId,
        kernel::OperatorKernel;
        documentation::AbstractString = "",
    )
        frozen_signatures = _freeze_signatures(signatures)
        return new{typeof(frozen_signatures),typeof(kernel)}(
            id,
            frozen_signatures,
            candidate_type,
            kernel,
            _documentation(documentation),
        )
    end
end

"""A generic selector for a Choice value."""
struct SelectorSpec{S<:Tuple,K}
    id::SelectorId
    signatures::S
    kernel::K
    documentation::String

    function SelectorSpec(
        id::SelectorId,
        signatures,
        kernel::OperatorKernel;
        documentation::AbstractString = "",
    )
        frozen_signatures = _freeze_signatures(signatures)
        return new{typeof(frozen_signatures),typeof(kernel)}(
            id,
            frozen_signatures,
            kernel,
            _documentation(documentation),
        )
    end
end

function _validate_scale_hint(scale_hint)
    scale_hint === nothing && return nothing
    value = Float64(scale_hint)
    isfinite(value) && value > 0 || throw(
        InvariantError(:invalid_scale_hint, "a scale hint must be finite and strictly positive"),
    )
    return value
end

"""Content-locked plugin identity required by a problem."""
struct PluginLock
    id::PluginId
    version::VersionNumber
    core_abi::VersionNumber
    content::ContentHash
end

"""The single immutable source of all Julia and generated protocol metadata."""
struct PluginSpec
    id::PluginId
    version::VersionNumber
    core_abi::VersionNumber
    content::ContentHash
    types::Tuple
    primitives::Tuple
    relations::Tuple
    guards::Tuple
    domains::Tuple
    branches::Tuple
    selectors::Tuple

    function PluginSpec(
        id::PluginId,
        version::VersionNumber,
        core_abi::VersionNumber,
        content::ContentHash;
        types = (),
        primitives = (),
        relations = (),
        guards = (),
        domains = (),
        branches = (),
        selectors = (),
    )
        version == v"0.0.0" && throw(
            InvariantError(:invalid_plugin_version, "plugin version 0.0.0 is reserved"),
        )
        core_abi == v"0.0.0" && throw(
            InvariantError(:invalid_core_abi, "core ABI version 0.0.0 is reserved"),
        )

        frozen_types = tuple((spec::TypeSpec for spec in types)...)
        frozen_primitives = tuple((spec::PrimitiveSpec for spec in primitives)...)
        frozen_relations = tuple((spec::RelationSpec for spec in relations)...)
        frozen_guards = tuple((spec::GuardSpec for spec in guards)...)
        frozen_domains = tuple((spec::DomainSpec for spec in domains)...)
        frozen_branches = tuple((spec::BranchSpec for spec in branches)...)
        frozen_selectors = tuple((spec::SelectorSpec for spec in selectors)...)

        _validate_plugin_members(id, frozen_types, frozen_primitives, frozen_relations,
            frozen_guards, frozen_domains, frozen_branches, frozen_selectors)

        return new(
            id,
            version,
            core_abi,
            content,
            frozen_types,
            frozen_primitives,
            frozen_relations,
            frozen_guards,
            frozen_domains,
            frozen_branches,
            frozen_selectors,
        )
    end
end

function _validate_plugin_members(id, types, primitives, relations, guards, domains, branches, selectors)
    for spec in types
        spec.id.plugin == id || throw(
            InvariantError(:foreign_type_id, "TypeSpec $(spec.id) is not owned by plugin $id"),
        )
    end
    type_ids = map(spec -> spec.id, types)
    allunique(type_ids) || throw(
        InvariantError(:duplicate_type_id, "a plugin cannot declare a TypeId twice"),
    )

    operations = (primitives..., relations..., guards..., domains..., branches...)
    for spec in operations
        spec.id.plugin == id || throw(
            InvariantError(:foreign_operation_id, "operation $(spec.id) is not owned by plugin $id"),
        )
    end
    operation_ids = map(spec -> spec.id, operations)
    allunique(operation_ids) || throw(
        InvariantError(
            :duplicate_operation_id,
            "operation IDs must be unique across primitive/relation/guard/domain/branch roles",
        ),
    )

    for spec in selectors
        spec.id.plugin == id || throw(
            InvariantError(:foreign_selector_id, "selector $(spec.id) is not owned by plugin $id"),
        )
    end
    selector_ids = map(spec -> spec.id, selectors)
    allunique(selector_ids) || throw(
        InvariantError(:duplicate_selector_id, "a plugin cannot declare a SelectorId twice"),
    )
    return nothing
end

plugin_lock(spec::PluginSpec) = PluginLock(spec.id, spec.version, spec.core_abi, spec.content)
