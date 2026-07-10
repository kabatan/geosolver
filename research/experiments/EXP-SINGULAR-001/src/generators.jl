function _matrix_for_type(::Type{T}, values::AbstractMatrix) where {T<:Real}
    return T[T(value) for value in values]
end

function _near_null_matrix(::Type{T}, delta::Real) where {T<:Real}
    return T[one(T) one(T); one(T) one(T) + T(delta)]
end

function _case_checksum(input::CandidateInput, parameters::Dict{String,Any})
    io = IOBuffer()
    print(io, input.oracle.id, '|', input.oracle.family, '|', input.oracle.capability)
    for value in input.endpoint
        print(io, '|', reinterpret(UInt64, value))
    end
    for key in sort!(collect(keys(parameters)))
        print(io, '|', key, '=', repr(parameters[key]))
    end
    return bytes2hex(sha256(take!(io)))
end

function _generated(input, gold, parameters)
    material = Dict{String,Any}(String(key) => value for (key, value) in parameters)
    return GeneratedEndpoint(input, gold, material, _case_checksum(input, material))
end

function _linear_near_null_case(
    id::AbstractString;
    delta::Real,
    endpoint=(1.0, -1.0),
    variable_transform=Matrix{Float64}(I, 2, 2),
    residual_transform=Matrix{Float64}(I, 2, 2),
    group::AbstractString="near-null",
    capability::Symbol=:C2,
)
    q = Matrix{Float64}(variable_transform)
    p = Matrix{Float64}(residual_transform)
    size(q) == (2, 2) || throw(DimensionMismatch("variable transform must be 2x2"))
    size(p) == (2, 2) || throw(DimensionMismatch("residual transform must be 2x2"))
    frozen_endpoint = q * Float64[endpoint...]

    function residual(z::AbstractVector{T}) where {T<:Real}
        q_t = _matrix_for_type(T, q)
        p_t = _matrix_for_type(T, p)
        x = transpose(q_t) * z
        return p_t * (_near_null_matrix(T, delta) * x)
    end
    function target(z::AbstractVector{T}) where {T<:Real}
        q_t = _matrix_for_type(T, q)
        return first(transpose(q_t) * z)
    end
    function jacobian(z::AbstractVector{T}) where {T<:Real}
        length(z) == 2 || throw(DimensionMismatch("linear case expects two variables"))
        return _matrix_for_type(T, p) * _near_null_matrix(T, delta) *
               transpose(_matrix_for_type(T, q))
    end

    oracle = EndpointOracle(
        id,
        "SING-NEAR-NULL-FULL-RANK",
        group,
        2,
        2,
        capability,
        residual,
        target,
        jacobian,
    )
    input = CandidateInput(oracle, frozen_endpoint)
    parameters = Dict{String,Any}(
        "delta" => Float64(delta),
        "endpoint" => Float64[endpoint...],
        "variable_transform" => vec(q),
        "residual_transform" => vec(p),
    )
    gold = GoldTruth(
        :isolated_root;
        configuration=zeros(2),
        target=0.0,
        finite_discrete_target=true,
    )
    return _generated(input, gold, parameters)
end

function _regular_linear_case(id::AbstractString; capability::Symbol=:C2)
    matrix = [1.0 0.25; -0.5 1.5]
    endpoint = [0.5, -0.25]
    residual(x::AbstractVector{T}) where {T<:Real} = _matrix_for_type(T, matrix) * x
    target(x::AbstractVector{T}) where {T<:Real} = x[1] - T(0.5) * x[2]
    jacobian(x::AbstractVector{T}) where {T<:Real} = begin
        length(x) == 2 || throw(DimensionMismatch("regular case expects two variables"))
        _matrix_for_type(T, matrix)
    end
    oracle = EndpointOracle(
        id,
        "REGULAR-WELL-CONDITIONED",
        "regular-linear",
        2,
        2,
        capability,
        residual,
        target,
        jacobian,
    )
    input = CandidateInput(oracle, endpoint)
    parameters = Dict{String,Any}(
        "matrix" => vec(matrix),
        "endpoint" => endpoint,
    )
    gold = GoldTruth(
        :isolated_root;
        configuration=zeros(2),
        target=0.0,
        finite_discrete_target=true,
    )
    return _generated(input, gold, parameters)
end

function _inconsistent_nonroot_case(
    id::AbstractString="nonroot-stationary-1e-13";
    inconsistency::Real=1.0e-13,
    residual_transform=Matrix{Float64}(I, 2, 2),
)
    p = Matrix{Float64}(residual_transform)
    size(p) == (2, 2) || throw(DimensionMismatch("residual transform must be 2x2"))
    frozen_inconsistency = Float64(inconsistency)
    endpoint = [-inconsistency / 2]
    residual(x::AbstractVector{T}) where {T<:Real} =
        _matrix_for_type(T, p) * T[x[1], x[1] + T(frozen_inconsistency)]
    target(x::AbstractVector{T}) where {T<:Real} = x[1]
    jacobian(x::AbstractVector{T}) where {T<:Real} = begin
        length(x) == 1 || throw(DimensionMismatch("nonroot case expects one variable"))
        _matrix_for_type(T, p) * T[one(T); one(T);;]
    end
    oracle = EndpointOracle(
        id,
        "SING-NONROOT-STATIONARY",
        "nonroot-stationary",
        1,
        2,
        :C2,
        residual,
        target,
        jacobian,
    )
    input = CandidateInput(oracle, endpoint)
    parameters = Dict{String,Any}(
        "inconsistency" => frozen_inconsistency,
        "endpoint" => endpoint,
        "residual_transform" => vec(p),
    )
    return _generated(input, GoldTruth(:no_local_root), parameters)
end

function _zero_manifold_case(
    id::Union{Nothing,AbstractString}=nothing;
    constant_target::Bool=false,
    endpoint=(0.75, -0.5),
)
    frozen_id = id === nothing ?
                (constant_target ?
                 "zero-manifold-constant-target" :
                 "zero-manifold-varying-target") : String(id)
    residual(x::AbstractVector{T}) where {T<:Real} = T[zero(T), zero(T)]
    target = constant_target ? (x -> oftype(x[1], 7)) : (x -> x[1])
    jacobian(x::AbstractVector{T}) where {T<:Real} = zeros(T, 2, 2)
    oracle = EndpointOracle(
        frozen_id,
        "SING-MANIFOLD-CONTROLS",
        frozen_id,
        2,
        2,
        :C2,
        residual,
        target,
        jacobian,
    )
    frozen_endpoint = Float64[endpoint...]
    input = CandidateInput(oracle, frozen_endpoint)
    parameters = Dict{String,Any}(
        "constant_target" => constant_target,
        "endpoint" => frozen_endpoint,
    )
    gold = constant_target ?
           GoldTruth(:finite_manifold_target; target=7.0, finite_discrete_target=true) :
           GoldTruth(:nonfinite_target_image; finite_discrete_target=false)
    return _generated(input, gold, parameters)
end

function _double_root_case(
    id::AbstractString="isolated-double-root";
    endpoint_value::Real=1.0e-4,
)
    endpoint = [Float64(endpoint_value)]
    residual(x::AbstractVector{T}) where {T<:Real} = T[x[1]^2]
    target(x::AbstractVector{T}) where {T<:Real} = x[1]
    jacobian(x::AbstractVector{T}) where {T<:Real} = T[T(2) * x[1];;]
    oracle = EndpointOracle(
        id,
        "SING-ISOLATED-MULTIPLE",
        "isolated-double-root",
        1,
        1,
        :C2,
        residual,
        target,
        jacobian,
    )
    input = CandidateInput(oracle, endpoint)
    parameters = Dict{String,Any}("multiplicity" => 2, "endpoint" => endpoint)
    gold = GoldTruth(
        :isolated_root;
        configuration=[0.0],
        target=0.0,
        finite_discrete_target=true,
    )
    return _generated(input, gold, parameters)
end

function _token(value::Real)
    return replace(lowercase(string(Float64(value))), "." => "p", "+" => "", "-" => "m")
end

"""The preregistered 72-instance development grid, materialized before execution."""
function development_cases()
    angle = pi / 4
    rotation = [cos(angle) -sin(angle); sin(angle) cos(angle)]
    reflection = [0.0 1.0; 1.0 0.0]
    representations = (
        ("base", Matrix{Float64}(I, 2, 2), Matrix{Float64}(I, 2, 2)),
        ("variable_rotation", rotation, Matrix{Float64}(I, 2, 2)),
        ("residual_rotation", Matrix{Float64}(I, 2, 2), rotation),
        ("variable_reflection", reflection, Matrix{Float64}(I, 2, 2)),
    )
    cases = GeneratedEndpoint[]
    for delta in (1.0, 1.0e-4, 1.0e-8, 1.0e-12, 1.0e-13, 1.0e-16)
        for magnitude in (0.1, 1.0)
            group = "dev-near-d$(_token(delta))-m$(_token(magnitude))"
            for (representation, q, p) in representations
                id = "$group-$representation"
                push!(
                    cases,
                    _linear_near_null_case(
                        id;
                        delta,
                        endpoint=(magnitude, -magnitude),
                        variable_transform=q,
                        residual_transform=p,
                        group,
                    ),
                )
            end
        end
    end

    for inconsistency in (1.0e-14, 1.0e-13, 1.0e-12, 1.0e-10)
        for (name, transform) in (
            ("base", Matrix{Float64}(I, 2, 2)),
            ("rotation", rotation),
        )
            id = "dev-nonroot-i$(_token(inconsistency))-$name"
            push!(
                cases,
                _inconsistent_nonroot_case(
                    id;
                    inconsistency,
                    residual_transform=transform,
                ),
            )
        end
    end

    manifold_endpoints = ((0.0, 0.0), (0.75, -0.5), (-1.0, 0.25), (1.5, -1.5))
    for constant_target in (false, true)
        mode = constant_target ? "constant" : "varying"
        for (index, endpoint) in enumerate(manifold_endpoints)
            push!(
                cases,
                _zero_manifold_case(
                    "dev-manifold-$mode-$index";
                    constant_target,
                    endpoint,
                ),
            )
        end
    end

    for delta in (1.0, 1.0e-4, 1.0e-8, 1.0e-12)
        push!(
            cases,
            _linear_near_null_case(
                "dev-c0-d$(_token(delta))";
                delta,
                endpoint=(0.5, -0.5),
                group="dev-c0",
                capability=:C0,
            ),
        )
    end

    for endpoint_value in (1.0e-2, 1.0e-4, 1.0e-6, 1.0e-8)
        push!(
            cases,
            _double_root_case(
                "dev-double-e$(_token(endpoint_value))";
                endpoint_value,
            ),
        )
    end
    length(cases) == 72 || error("development grid must contain exactly 72 cases")
    allunique(case.input.oracle.id for case in cases) || error("development ids must be unique")
    return cases
end

"""Frozen in-memory controls; development materialization is a later step."""
function fixed_control_cases()
    angle = pi / 4
    rotation = [cos(angle) -sin(angle); sin(angle) cos(angle)]
    return GeneratedEndpoint[
        _linear_near_null_case("p1-near-null-base"; delta=1.0e-13, group="p1-near-null"),
        _linear_near_null_case(
            "p1-near-null-variable-rotation";
            delta=1.0e-13,
            variable_transform=rotation,
            group="p1-near-null",
        ),
        _linear_near_null_case(
            "p1-near-null-residual-rotation";
            delta=1.0e-13,
            residual_transform=rotation,
            group="p1-near-null",
        ),
        _linear_near_null_case(
            "near-null-full-rank-1e-4";
            delta=1.0e-4,
            endpoint=(0.5, -0.5),
            group="near-null-1e-4",
        ),
        _regular_linear_case("regular-linear-c2"),
        _regular_linear_case("regular-linear-c0"; capability=:C0),
        _inconsistent_nonroot_case(),
        _zero_manifold_case(),
        _zero_manifold_case(constant_target=true),
        _double_root_case(),
    ]
end
