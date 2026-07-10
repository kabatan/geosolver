"""Analytic derivative data visible only to the independent S4 control."""
struct S4AnalyticControlOracle{J,H}
    analytic_jacobian::J
    analytic_second_directional::H
end

"""Frozen S4 case wrapper; the candidate receives only `candidate_input(case)`."""
struct S4DevelopmentCase{E<:GeneratedEndpoint,C<:S4AnalyticControlOracle}
    generated::E
    analytic_control::C
    stratum::String
    representation::String
    isolated_configurations::Tuple
    isolated_targets::Tuple

    function S4DevelopmentCase(
        generated::E,
        analytic_control::C,
        stratum::AbstractString,
        representation::AbstractString,
        isolated_configurations::Tuple,
        isolated_targets::Tuple,
    ) where {E<:GeneratedEndpoint,C<:S4AnalyticControlOracle}
        frozen_stratum = String(stratum)
        frozen_representation = String(representation)
        isempty(frozen_stratum) && throw(ArgumentError("S4 stratum must be nonempty"))
        isempty(frozen_representation) && throw(
            ArgumentError("S4 representation must be nonempty"),
        )
        return new{E,C}(
            generated,
            analytic_control,
            frozen_stratum,
            frozen_representation,
            isolated_configurations,
            isolated_targets,
        )
    end
end

candidate_input(case::S4DevelopmentCase) = candidate_input(case.generated)

const _S4_TRANSFORM_NAMESPACE = "singular-s4-development-v0"
const _S4_REPRESENTATIONS = (
    "orthogonal-variable-and-residual-rotation",
    "independent-signed-variable-and-residual-permutation",
    "equivalent-shared-DAG-reordering",
)

const _S4_INPUT_CONTROLS = (
    precision_bits=(128, 256),
    jacobian_radius_multipliers=(1.0, 0.5),
    finite_difference_exponent=1 / 3,
    mixed_direction_step_exponent=1 / 4,
    singular_value_gap_ratio_max=1.0e-6,
    maximum_nullity=4,
    maximum_global_iterations=64,
    maximum_callbacks=4096,
    wall_seconds=10.0,
    independent_confirmation_count=2,
    confirmation_perturbation_radius=1.0e-6,
    nullspace_principal_angle_sine_max=1.0e-6,
    projected_condition_max=1.0e12,
    error_reserve_multiplier=16.0,
    configuration_error_goal=1.0e-10,
    target_error_goal=1.0e-12,
    semantic_residual_tolerance=1.0e-12,
)

function _s4_spec(
    group::AbstractString,
    stratum::AbstractString,
    mode::Symbol,
    dimension::Integer,
    nullity::Integer;
    degree::Integer=2,
    coefficients=ones(Rational{Int}, nullity),
    coupling_scale::Rational{Int}=1 // 4,
    endpoint_scale::Real=2.0^-90,
    tangent_coordinate::Real=0.0,
    inconsistency::Real=0.0,
    separation_numerator::Integer=0,
    separation_denominator::Integer=1,
    target_mode::Symbol=:linear,
)
    mode in (:isolated, :higher_depth, :manifold, :nonroot, :regular_fold) ||
        throw(ArgumentError("unsupported S4 mode"))
    dimension >= 2 || throw(ArgumentError("S4 dimension must be at least two"))
    1 <= nullity < dimension || throw(ArgumentError("invalid S4 nullity"))
    nullity <= _S4_INPUT_CONTROLS.maximum_nullity || throw(
        ArgumentError("S4 nullity exceeds the frozen maximum"),
    )
    degree >= 2 || throw(ArgumentError("S4 degree must be at least two"))
    frozen_coefficients = Rational{Int}[coefficients...]
    length(frozen_coefficients) == nullity || throw(
        DimensionMismatch("S4 coefficient count must equal nullity"),
    )
    all(value -> !iszero(value), frozen_coefficients) || throw(
        ArgumentError("S4 coefficients must be nonzero"),
    )
    target_mode in (:linear, :constant_manifold, :varying_manifold) || throw(
        ArgumentError("unsupported S4 target mode"),
    )
    separation_denominator > 0 || throw(
        ArgumentError("S4 separation denominator must be positive"),
    )
    return (
        group=String(group),
        stratum=String(stratum),
        mode=mode,
        dimension=Int(dimension),
        nullity=Int(nullity),
        retained=Int(dimension - nullity),
        degree=Int(degree),
        coefficients=frozen_coefficients,
        coupling_scale=coupling_scale,
        endpoint_scale=Float64(endpoint_scale),
        tangent_coordinate=Float64(tangent_coordinate),
        inconsistency=Float64(inconsistency),
        separation_numerator=Int(separation_numerator),
        separation_denominator=Int(separation_denominator),
        target_mode=target_mode,
    )
end

function _s4_givens(
    dimension::Int,
    cosine::Rational{Int},
    sine::Rational{Int},
    first::Int,
    second::Int,
)
    matrix = Matrix{Rational{Int}}(I, dimension, dimension)
    matrix[first, first] = cosine
    matrix[first, second] = -sine
    matrix[second, first] = sine
    matrix[second, second] = cosine
    return matrix
end

function _s4_signed_permutation(dimension::Int, shift::Int, sign_offset::Int)
    matrix = zeros(Rational{Int}, dimension, dimension)
    for column in 1:dimension
        row = mod1(column + shift, dimension)
        sign = isodd(column + sign_offset) ? (-1 // 1) : (1 // 1)
        matrix[row, column] = sign
    end
    return matrix
end

function _s4_representation(dimension::Int, representation::AbstractString)
    if representation == _S4_REPRESENTATIONS[1]
        variable = _s4_givens(dimension, 3 // 5, 4 // 5, 1, dimension)
        residual = _s4_givens(dimension, 5 // 13, 12 // 13, 1, min(2, dimension))
        return variable, residual, false
    elseif representation == _S4_REPRESENTATIONS[2]
        return _s4_signed_permutation(dimension, 1, 0),
            _s4_signed_permutation(dimension, dimension - 1, 1), false
    elseif representation == _S4_REPRESENTATIONS[3]
        identity = Matrix{Rational{Int}}(I, dimension, dimension)
        return identity, copy(identity), true
    end
    throw(ArgumentError("unknown S4 representation"))
end

_s4_separation(::Type{T}, spec) where {T} =
    T(spec.separation_numerator) / T(spec.separation_denominator)

_s4_rational_strings(matrix) = String[repr(value) for value in vec(matrix)]

function _s4_coupling_matrix(spec)
    return [
        spec.coupling_scale * (isodd(row + column) ? (-1 // 1) : (1 // 1)) *
        ((row + 2 * column) // (spec.dimension + 3))
        for row in 1:spec.retained, column in 1:spec.nullity
    ]
end

function _s4_power(value::T, degree::Int, coefficient::T, reordered::Bool) where {T}
    if !reordered
        return coefficient * value^degree
    end
    result = coefficient
    for _ in 1:degree
        result *= value
    end
    return result
end

function _s4_raw_residual(
    ::Type{T},
    local_coordinates,
    spec,
    coupling,
    reordered::Bool,
) where {T}
    raw = zeros(T, spec.dimension)
    if spec.mode in (:isolated, :higher_depth, :regular_fold)
        nonlinear = zeros(T, spec.nullity)
        for column in 1:spec.nullity
            value = local_coordinates[spec.retained + column]
            coefficient = T(spec.coefficients[column])
            nonlinear[column] = _s4_power(
                value,
                spec.degree,
                coefficient,
                reordered,
            )
            if spec.mode === :regular_fold
                separation = _s4_separation(T, spec)
                nonlinear[column] -= reordered ?
                                     (coefficient * separation) * separation :
                                     coefficient * separation^2
            end
        end
        for row in 1:spec.retained
            value = local_coordinates[row]
            order = reordered ? (spec.nullity:-1:1) : (1:spec.nullity)
            for column in order
                value += T(coupling[row, column]) * nonlinear[column]
            end
            raw[row] = value
        end
        raw[(spec.retained + 1):end] .= nonlinear
    else
        for row in 1:spec.dimension
            coefficient = T(isodd(row) ? row : -row)
            raw[row] = coefficient * local_coordinates[1]
        end
        if spec.mode === :nonroot
            raw[end] += T(spec.inconsistency)
        end
    end
    return raw
end

function _s4_raw_jacobian(::Type{T}, local_coordinates, spec, coupling) where {T}
    jacobian = zeros(T, spec.dimension, spec.dimension)
    if spec.mode in (:isolated, :higher_depth, :regular_fold)
        for row in 1:spec.retained
            jacobian[row, row] = one(T)
        end
        for column in 1:spec.nullity
            local_index = spec.retained + column
            value = local_coordinates[local_index]
            derivative = T(spec.coefficients[column]) * T(spec.degree) *
                         value^(spec.degree - 1)
            jacobian[local_index, local_index] = derivative
            for row in 1:spec.retained
                jacobian[row, local_index] = T(coupling[row, column]) * derivative
            end
        end
    else
        for row in 1:spec.dimension
            jacobian[row, 1] = T(isodd(row) ? row : -row)
        end
    end
    return jacobian
end

function _s4_raw_second_directional(
    ::Type{T},
    local_coordinates,
    a,
    b,
    spec,
    coupling,
) where {T}
    result = zeros(T, spec.dimension)
    spec.mode in (:isolated, :higher_depth, :regular_fold) || return result
    nonlinear = zeros(T, spec.nullity)
    for column in 1:spec.nullity
        local_index = spec.retained + column
        value = local_coordinates[local_index]
        nonlinear[column] = T(spec.coefficients[column]) * T(spec.degree) *
                            T(spec.degree - 1) * value^(spec.degree - 2) *
                            a[local_index] * b[local_index]
    end
    for row in 1:spec.retained
        for column in 1:spec.nullity
            result[row] += T(coupling[row, column]) * nonlinear[column]
        end
    end
    result[(spec.retained + 1):end] .= nonlinear
    return result
end

function _s4_local_points(spec)
    endpoint = zeros(Float64, spec.dimension)
    gold = zeros(Float64, spec.dimension)
    if spec.mode in (:isolated, :higher_depth)
        endpoint[1] = spec.endpoint_scale / 8
        for column in 1:spec.nullity
            endpoint[spec.retained + column] = column * spec.endpoint_scale
        end
    elseif spec.mode === :manifold
        endpoint[end] = spec.tangent_coordinate
    elseif spec.mode === :nonroot
        endpoint[1] = -spec.inconsistency / 5
        endpoint[end] = spec.tangent_coordinate
    else
        separation = Float64(spec.separation_numerator) /
                     Float64(spec.separation_denominator)
        endpoint[spec.retained + 1] = separation
        gold[spec.retained + 1] = separation
    end
    return endpoint, gold
end

function _s4_target_coefficients(dimension::Int)
    return Rational{Int}[
        (isodd(index) ? 1 : -1) // (index + 1) for index in 1:dimension
    ]
end

function _s4_system_case(spec, representation::AbstractString)
    variable_transform, residual_transform, reordered =
        _s4_representation(spec.dimension, representation)
    coupling = _s4_coupling_matrix(spec)
    local_endpoint, local_gold = _s4_local_points(spec)
    endpoint = Float64.(variable_transform) * local_endpoint
    gold_configuration = Float64.(variable_transform) * local_gold
    target_coefficients = _s4_target_coefficients(spec.dimension)

    function residual(z::AbstractVector{T}) where {T<:Real}
        length(z) == spec.dimension || throw(DimensionMismatch("S4 residual input"))
        q = _matrix_for_type(T, variable_transform)
        p = _matrix_for_type(T, residual_transform)
        local_coordinates = transpose(q) * z
        raw = _s4_raw_residual(T, local_coordinates, spec, coupling, reordered)
        return p * raw
    end
    function target(z::AbstractVector{T}) where {T<:Real}
        length(z) == spec.dimension || throw(DimensionMismatch("S4 target input"))
        local_coordinates = transpose(_matrix_for_type(T, variable_transform)) * z
        if spec.target_mode === :constant_manifold
            return T(1) / T(8) + local_coordinates[1]
        elseif spec.target_mode === :varying_manifold
            return local_coordinates[end]
        end
        return T(3) / T(8) + sum(
            T(target_coefficients[index]) * local_coordinates[index] for
            index in 1:spec.dimension
        )
    end
    function jacobian(z::AbstractVector{T}) where {T<:Real}
        length(z) == spec.dimension || throw(DimensionMismatch("S4 Jacobian input"))
        q = _matrix_for_type(T, variable_transform)
        p = _matrix_for_type(T, residual_transform)
        local_coordinates = transpose(q) * z
        return p * _s4_raw_jacobian(T, local_coordinates, spec, coupling) * transpose(q)
    end
    function analytic_second_directional(
        z::AbstractVector{T},
        first_direction,
        second_direction,
    ) where {T<:Real}
        length(z) == spec.dimension || throw(DimensionMismatch("S4 Hessian point"))
        length(first_direction) == spec.dimension || throw(
            DimensionMismatch("S4 first Hessian direction"),
        )
        length(second_direction) == spec.dimension || throw(
            DimensionMismatch("S4 second Hessian direction"),
        )
        q = _matrix_for_type(T, variable_transform)
        p = _matrix_for_type(T, residual_transform)
        local_coordinates = transpose(q) * z
        first_local = transpose(q) * T[first_direction...]
        second_local = transpose(q) * T[second_direction...]
        raw = _s4_raw_second_directional(
            T,
            local_coordinates,
            first_local,
            second_local,
            spec,
            coupling,
        )
        return p * raw
    end

    family = if spec.stratum == "isolated-deflation-one"
        "SING-S4-DEFLATION-ONE"
    elseif spec.stratum == "higher-deflation-depth-controls"
        "SING-S4-HIGHER-DEPTH"
    elseif spec.stratum == "manifold-controls"
        "SING-S4-MANIFOLD"
    elseif spec.stratum == "inconsistent-nonroots"
        "SING-S4-NONROOT"
    else
        "SING-S4-REGULAR-CLOSE-ROOT"
    end
    id = "$(spec.group)-$(representation)"
    oracle = EndpointOracle(
        id,
        family,
        spec.group,
        spec.dimension,
        spec.dimension,
        :C2,
        residual,
        target,
        nothing,
    )
    input = CandidateInput(oracle, endpoint)
    parameters = Dict{String,Any}(
        "coefficient_rationals" => String[repr(value) for value in spec.coefficients],
        "coupling_matrix_rationals" => _s4_rational_strings(coupling),
        "dag_reordered" => reordered,
        "degree" => spec.degree,
        "endpoint_scale" => spec.endpoint_scale,
        "inconsistency" => spec.inconsistency,
        "local_endpoint" => local_endpoint,
        "mode" => string(spec.mode),
        "nullity" => spec.nullity,
        "representation" => String(representation),
        "residual_transform_rationals" => _s4_rational_strings(residual_transform),
        "retained" => spec.retained,
        "separation_denominator" => spec.separation_denominator,
        "separation_numerator" => spec.separation_numerator,
        "stratum" => spec.stratum,
        "tangent_coordinate" => spec.tangent_coordinate,
        "target_coefficient_rationals" =>
            String[repr(value) for value in target_coefficients],
        "target_mode" => string(spec.target_mode),
        "transform_namespace" => _S4_TRANSFORM_NAMESPACE,
        "variable_transform_rationals" => _s4_rational_strings(variable_transform),
    )
    gold = if spec.mode in (:isolated, :higher_depth, :regular_fold)
        GoldTruth(
            :isolated_root;
            configuration=gold_configuration,
            target=Float64(target(gold_configuration)),
            finite_discrete_target=true,
        )
    elseif spec.mode === :manifold && spec.target_mode === :constant_manifold
        GoldTruth(
            :finite_manifold_target;
            target=1 / 8,
            finite_discrete_target=true,
        )
    elseif spec.mode === :manifold
        GoldTruth(:nonfinite_target_image; finite_discrete_target=false)
    else
        GoldTruth(:no_local_root)
    end
    generated = _generated(input, gold, parameters)
    local_isolated_configurations = if spec.mode === :regular_fold
        positive = copy(local_gold)
        negative = copy(local_gold)
        separation = Float64(spec.separation_numerator) /
                     Float64(spec.separation_denominator)
        positive[spec.retained + 1] = separation
        negative[spec.retained + 1] = -separation
        (positive, negative)
    elseif spec.mode in (:isolated, :higher_depth)
        (copy(local_gold),)
    else
        ()
    end
    isolated_configurations = Tuple(
        Tuple(Float64.(variable_transform) * local_configuration) for
        local_configuration in local_isolated_configurations
    )
    isolated_targets = Tuple(
        Float64(target(collect(configuration))) for
        configuration in isolated_configurations
    )
    return S4DevelopmentCase(
        generated,
        S4AnalyticControlOracle(jacobian, analytic_second_directional),
        spec.stratum,
        representation,
        isolated_configurations,
        isolated_targets,
    )
end

function _s4_development_specs()
    return (
        _s4_spec("s4-d1-k1-a", "isolated-deflation-one", :isolated, 2, 1;
            coefficients=[1 // 1], coupling_scale=1 // 4, endpoint_scale=2.0^-90),
        _s4_spec("s4-d1-k2-a", "isolated-deflation-one", :isolated, 3, 2;
            coefficients=[1 // 1, 3 // 4], coupling_scale=-3 // 8, endpoint_scale=2.0^-91),
        _s4_spec("s4-d1-r2-k2", "isolated-deflation-one", :isolated, 4, 2;
            coefficients=[5 // 4, -7 // 8], coupling_scale=1 // 2, endpoint_scale=2.0^-92),
        _s4_spec("s4-d1-k3", "isolated-deflation-one", :isolated, 4, 3;
            coefficients=[1 // 1, -5 // 4, 5 // 8], coupling_scale=-1 // 4, endpoint_scale=2.0^-93),
        _s4_spec("s4-d1-k4", "isolated-deflation-one", :isolated, 5, 4;
            coefficients=[1 // 1, 3 // 4, -3 // 2, 5 // 4],
            coupling_scale=5 // 16, endpoint_scale=2.0^-94),
        _s4_spec("s4-depth3-k1", "higher-deflation-depth-controls", :higher_depth, 2, 1;
            degree=3, coefficients=[1 // 1], endpoint_scale=2.0^-60),
        _s4_spec("s4-depth4-k2", "higher-deflation-depth-controls", :higher_depth, 3, 2;
            degree=4, coefficients=[1 // 1, -3 // 4], endpoint_scale=2.0^-48),
        _s4_spec("s4-manifold-constant", "manifold-controls", :manifold, 2, 1;
            tangent_coordinate=0.375, target_mode=:constant_manifold),
        _s4_spec("s4-manifold-varying", "manifold-controls", :manifold, 3, 2;
            tangent_coordinate=-0.25, target_mode=:varying_manifold),
        _s4_spec("s4-inconsistent-small", "inconsistent-nonroots", :nonroot, 2, 1;
            inconsistency=2.0^-42, tangent_coordinate=0.125,
            target_mode=:linear),
        _s4_spec("s4-regular-fold-above-gap", "regular-close-root-controls", :regular_fold, 2, 1;
            separation_numerator=1, separation_denominator=10_000,
            coefficients=[1 // 1], coupling_scale=1 // 4),
        _s4_spec("s4-regular-fold-midpoint-trap", "regular-close-root-controls", :regular_fold, 2, 1;
            separation_numerator=1, separation_denominator=10_000_000,
            coefficients=[1 // 1], coupling_scale=-3 // 8),
    )
end

"""Input-only S4 development cases. No candidate or control map is defined here."""
function s4_development_cases()
    cases = S4DevelopmentCase[]
    for spec in _s4_development_specs()
        for representation in _S4_REPRESENTATIONS
            push!(cases, _s4_system_case(spec, representation))
        end
    end
    length(cases) == 36 || error("S4 development split must contain 36 cases")
    length(unique(case.generated.input.oracle.metamorphic_group for case in cases)) == 12 ||
        error("S4 development split must contain 12 metamorphic groups")
    allunique(case.generated.input.oracle.id for case in cases) ||
        error("S4 development ids must be unique")
    return cases
end

function _s4_controls_document()
    return Dict{String,Any}(
        "configuration_error_goal" => _S4_INPUT_CONTROLS.configuration_error_goal,
        "confirmation_perturbation_radius" =>
            _S4_INPUT_CONTROLS.confirmation_perturbation_radius,
        "error_reserve_multiplier" => _S4_INPUT_CONTROLS.error_reserve_multiplier,
        "finite_difference_exponent" => _S4_INPUT_CONTROLS.finite_difference_exponent,
        "independent_confirmation_count" =>
            _S4_INPUT_CONTROLS.independent_confirmation_count,
        "jacobian_radius_multipliers" => Any[
            _S4_INPUT_CONTROLS.jacobian_radius_multipliers...,
        ],
        "maximum_callbacks" => _S4_INPUT_CONTROLS.maximum_callbacks,
        "maximum_global_iterations" => _S4_INPUT_CONTROLS.maximum_global_iterations,
        "maximum_nullity" => _S4_INPUT_CONTROLS.maximum_nullity,
        "mixed_direction_step_exponent" =>
            _S4_INPUT_CONTROLS.mixed_direction_step_exponent,
        "nullspace_principal_angle_sine_max" =>
            _S4_INPUT_CONTROLS.nullspace_principal_angle_sine_max,
        "precision_bits" => Any[_S4_INPUT_CONTROLS.precision_bits...],
        "projected_condition_max" => _S4_INPUT_CONTROLS.projected_condition_max,
        "semantic_residual_tolerance" =>
            _S4_INPUT_CONTROLS.semantic_residual_tolerance,
        "singular_value_gap_ratio_max" =>
            _S4_INPUT_CONTROLS.singular_value_gap_ratio_max,
        "target_error_goal" => _S4_INPUT_CONTROLS.target_error_goal,
        "wall_seconds" => _S4_INPUT_CONTROLS.wall_seconds,
    )
end

function _s4_case_manifest_document(cases)
    documents = Any[]
    for case in cases
        base = only(case_manifest_document([case.generated])["cases"])
        delete!(base, "gold_analysis_only")
        base["analytic_control_jacobian_available"] = true
        base["analytic_second_directional_available"] = true
        base["representation"] = case.representation
        base["stratum"] = case.stratum
        push!(documents, base)
    end
    return documents
end

function s4_development_gold_document(cases=s4_development_cases())
    collection_material = join((case.generated.checksum for case in cases), '\n')
    return Dict{String,Any}(
        "candidate_visible" => false,
        "case_collection_sha256" => bytes2hex(sha256(collection_material)),
        "cases" => Any[
            Dict{String,Any}(
                "case_checksum" => case.generated.checksum,
                "case_id" => case.generated.input.oracle.id,
                "finite_discrete_target" =>
                    case.generated.gold.finite_discrete_target,
                "isolated_configurations" => Any[
                    Any[configuration...] for
                    configuration in case.isolated_configurations
                ],
                "isolated_targets" => Any[case.isolated_targets...],
                "kind" => string(case.generated.gold.kind),
                "reference_configuration" => case.generated.gold.configuration,
                "reference_target" => case.generated.gold.target,
            ) for case in cases
        ],
        "experiment_id" => EXPERIMENT_ID,
        "schema" => "geotarget.singular-s4-development-gold/v1",
        "transform_namespace" => _S4_TRANSFORM_NAMESPACE,
    )
end

function _assert_s4_preimplementation_state(; source_directory::AbstractString=@__DIR__)
    frozen_source_directory = normpath(String(source_directory))
    forbidden = (
        normpath(joinpath(frozen_source_directory, "s4", "candidate.jl")),
        normpath(joinpath(frozen_source_directory, "s4", "analytic_control.jl")),
        normpath(joinpath(frozen_source_directory, "s4", "development.jl")),
    )
    for path in forbidden
        isfile(path) && error("S4 input freeze must precede candidate source: $path")
    end
    return nothing
end

function s4_development_input_document(
    cases=s4_development_cases();
    gold_artifact_sha256::AbstractString,
    gold_artifact_path::AbstractString=
        "research/experiments/EXP-SINGULAR-001/s4-development-gold.json",
    card_path=normpath(joinpath(@__DIR__, "..", "..", "EXP-SINGULAR-001.json")),
    preregistration_path=normpath(joinpath(@__DIR__, "..", "s4-preregistration.json")),
    amendment_a1_path=normpath(joinpath(
        @__DIR__,
        "..",
        "s4-protocol-amendment-a1.json",
    )),
    amendment_a2_path=normpath(joinpath(
        @__DIR__,
        "..",
        "s4-protocol-amendment-a2.json",
    )),
    parent_summary_path=normpath(joinpath(
        @__DIR__,
        "..",
        "..",
        "..",
        "results",
        "EXP-SINGULAR-001",
        "development-s3-v0",
        "summary.json",
    )),
)
    collection_material = join((case.generated.checksum for case in cases), '\n')
    repo_root = normpath(joinpath(@__DIR__, "..", "..", "..", ".."))
    frozen_gold_sha256 = lowercase(String(gold_artifact_sha256))
    length(frozen_gold_sha256) == 64 &&
        all(character -> character in "0123456789abcdef", frozen_gold_sha256) ||
        throw(ArgumentError("Gold artifact SHA-256 must contain 64 hex digits"))
    return Dict{String,Any}(
        "amendment_a1_sha256" => bytes2hex(sha256(read(amendment_a1_path))),
        "amendment_a2_sha256" => bytes2hex(sha256(read(amendment_a2_path))),
        "analytic_control_fixture" => "analytic_second_directional(x,v,w)",
        "candidate_implementation_present" => false,
        "card_path" => replace(relpath(card_path, repo_root), '\\' => '/'),
        "card_sha256" => bytes2hex(sha256(read(card_path))),
        "case_collection_sha256" => bytes2hex(sha256(collection_material)),
        "cases" => _s4_case_manifest_document(cases),
        "development_instance_count" => length(cases),
        "experiment_id" => EXPERIMENT_ID,
        "gold_artifact_path" => String(gold_artifact_path),
        "gold_artifact_sha256" => frozen_gold_sha256,
        "gold_values_embedded" => false,
        "generator_scaffold_commit" =>
            "658f9f6bd0a889e68c6fbcab6d737449e91c92ec",
        "generator_scaffold_source_sha256" =>
            "b364801483a338787b80558a3dabe197bcea40ef49049e4072b747e506f04593",
        "harness_version" => string(HARNESS_VERSION),
        "input_source_sha256" => bytes2hex(sha256(read(@__FILE__))),
        "locked_inputs_materialized" => false,
        "metamorphic_group_count" => length(unique(
            case.generated.input.oracle.metamorphic_group for case in cases
        )),
        "parent_gate" => "development-s3-v0-rejected",
        "parent_summary_sha256" => bytes2hex(sha256(read(parent_summary_path))),
        "preregistration_sha256" => bytes2hex(sha256(read(preregistration_path))),
        "product_connected" => false,
        "representations_per_group" => 3,
        "s4_controls" => _s4_controls_document(),
        "schema" => "geotarget.singular-s4-development-input/v1",
        "transform_namespace" => _S4_TRANSFORM_NAMESPACE,
        "transforms" => Any[_S4_REPRESENTATIONS...],
        "variants" => Any[
            "S1-AP-LMQR",
            "S4-C2-NULLSPACE-TWO-STEP",
            "S4-ANALYTIC-TWO-STEP-CONTROL",
        ],
    )
end
