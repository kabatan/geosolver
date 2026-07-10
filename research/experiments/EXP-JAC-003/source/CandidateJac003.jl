module CandidateJac003

using GeoTargetBase
using GeoTargetCore
using LinearAlgebra

const GRAPH_SCHEMA = "exp-jac-003-typed-graph/v1"
const CANDIDATE_SCHEMA = "exp-jac-003-candidate-inputs/v1"
const PROVIDER_FIELDS = (:row_supports, :groups, :structural_nonzeros)
const ROUTE_FIELDS = (:variable_count, :residual_count, :structural_nonzeros, :color_count)

struct CandidateCompileError <: Exception
    code::Symbol
    detail::String
end

Base.showerror(io::IO, error::CandidateCompileError) =
    print(io, "EXP-JAC-003 candidate compile ", error.code, ": ", error.detail)

struct ProviderProjection{R<:Tuple,G<:Tuple}
    row_supports::R
    groups::G
    structural_nonzeros::Int
end

struct RouteProjection
    variable_count::Int
    residual_count::Int
    structural_nonzeros::Int
    color_count::Int
end

struct DependencyStructure{R<:Tuple}
    row_supports::R
    structural_nonzeros::Int
    variable_count::Int
    residual_count::Int
    compiler_hash::String
end

struct CompiledStructure{P<:ProviderProjection,R<:RouteProjection}
    provider::P
    route::R
    provider_hash::String
    route_hash::String
end

abstract type AbstractJac003Program end

struct SinCosTreeProgram{O<:Tuple,C<:Tuple} <: AbstractJac003Program
    offsets::O
    children::C
    amplitude::Float64
end

struct SafeRationalProgram{O<:Tuple,E<:Tuple} <: AbstractJac003Program
    offsets::O
    edges::E
    margin::Float64
    alpha::Float64
end

struct HexRingAtanProgram{O<:Tuple,N<:Tuple} <: AbstractJac003Program
    offsets::O
    neighbours::N
    curvature::Float64
    alpha::Float64
end

struct DenseChartProgram{O<:Tuple,M<:Tuple,A<:Tuple,W<:Tuple} <: AbstractJac003Program
    offsets::O
    matrix::M
    alternate_matrix::A
    chart::Symbol
    chart_weights::W
    chart_threshold::Float64
    smooth_gain::Float64
end

struct CompiledCaseRunner{P<:AbstractJac003Program,S<:CompiledStructure,V<:Tuple,B}
    program::P
    structure::S
    provider::B
    origins::V
    scales::V
    lower::V
    upper::V
    options::LocalSolveOptions
end

struct DenseCaseRunner{P<:AbstractJac003Program,S<:DependencyStructure,V<:Tuple}
    program::P
    structure::S
    origins::V
    scales::V
    lower::V
    upper::V
    options::LocalSolveOptions
end

_compile_error(code, detail) = throw(CandidateCompileError(code, detail))

function _required(object, key::AbstractString)
    haskey(object, key) || _compile_error(:missing_field, "missing field $(repr(key))")
    return object[key]
end

function _integer(value, label)
    value isa Integer || _compile_error(:invalid_integer, "$label must be an integer")
    return Int(value)
end

function _float_tuple(values, label)
    values isa AbstractVector || _compile_error(:invalid_vector, "$label must be an array")
    result = Tuple(Float64(value) for value in values)
    all(isfinite, result) || _compile_error(:nonfinite_value, "$label must be finite")
    return result
end

function _index_tuple(values, variable_count, label)
    values isa AbstractVector || _compile_error(:invalid_vector, "$label must be an array")
    result = Tuple(_integer(value, label) + 1 for value in values)
    all(index -> 1 <= index <= variable_count, result) ||
        _compile_error(:index_range, "$label contains an out-of-range variable slot")
    allunique(result) || _compile_error(:duplicate_index, "$label contains a duplicate slot")
    return result
end

function _natural_groups(row_supports)
    groups = Vector{Vector{Int}}()
    occupied = BitSet[]
    for column in eachindex(row_supports)
        isempty(row_supports[column]) && continue
        rows = BitSet(row_supports[column])
        destination = findfirst(existing -> isdisjoint(existing, rows), occupied)
        if destination === nothing
            push!(groups, [column])
            push!(occupied, rows)
        else
            push!(groups[destination], column)
            union!(occupied[destination], rows)
        end
    end
    return Tuple(Tuple(group) for group in groups)
end

function _projection_hash(projection::ProviderProjection)
    document = Dict{String,Any}(
        "groups" => Any[collect(group) for group in projection.groups],
        "row_supports" => Any[collect(rows) for rows in projection.row_supports],
        "structural_nonzeros" => projection.structural_nonzeros,
    )
    return string(canonical_json_hash(document))
end

function _projection_hash(projection::RouteProjection)
    document = Dict{String,Any}(
        "color_count" => projection.color_count,
        "residual_count" => projection.residual_count,
        "structural_nonzeros" => projection.structural_nonzeros,
        "variable_count" => projection.variable_count,
    )
    return string(canonical_json_hash(document))
end

function compile_dependencies(typed_graph, variable_count::Integer, residual_count::Integer)
    variable_count > 0 || _compile_error(:variable_count, "variable_count must be positive")
    residual_count > 0 || _compile_error(:residual_count, "residual_count must be positive")
    String(_required(typed_graph, "schema_version")) == GRAPH_SCHEMA ||
        _compile_error(:graph_schema, "unexpected typed-graph schema")
    nodes = _required(typed_graph, "nodes")
    nodes isa AbstractVector || _compile_error(:nodes, "nodes must be an array")

    dependencies = Dict{String,BitSet}()
    value_types = Dict{String,String}()
    reference_slots = BitSet()
    for node in nodes
        node isa AbstractDict || _compile_error(:node_shape, "every node must be an object")
        node_id = String(_required(node, "node_id"))
        isempty(node_id) && _compile_error(:node_id, "node_id must be nonempty")
        haskey(dependencies, node_id) && _compile_error(:duplicate_node, "duplicate node $node_id")
        kind = String(_required(node, "kind"))
        value_type = String(_required(node, "value_type"))
        current = BitSet()
        if kind == "reference"
            value_type == "real" ||
                _compile_error(:reference_type, "reference $node_id must have real type")
            slot = _integer(_required(node, "variable_slot"), "variable_slot") + 1
            1 <= slot <= variable_count ||
                _compile_error(:reference_range, "reference $node_id is out of range")
            slot in reference_slots &&
                _compile_error(:duplicate_reference, "variable slot $slot is referenced twice")
            push!(reference_slots, slot)
            push!(current, slot)
        elseif kind == "call"
            value_type in ("relation", "domain", "choice") ||
                _compile_error(:call_type, "call $node_id has unsupported type $value_type")
            operation = String(_required(node, "operation"))
            startswith(operation, "jac3.blackbox/") ||
                _compile_error(:operation_contract, "call $node_id is outside JAC003 contracts")
            arguments = _required(node, "arguments")
            arguments isa AbstractVector ||
                _compile_error(:arguments, "call $node_id arguments must be an array")
            isempty(arguments) && _compile_error(:arguments, "call $node_id has no arguments")
            for raw_argument in arguments
                argument = String(raw_argument)
                haskey(dependencies, argument) || _compile_error(
                    :topology,
                    "call $node_id argument $argument is missing or not earlier",
                )
                union!(current, dependencies[argument])
            end
        else
            _compile_error(:node_kind, "unsupported node kind $kind")
        end
        dependencies[node_id] = current
        value_types[node_id] = value_type
    end
    reference_slots == BitSet(1:variable_count) ||
        _compile_error(:reference_coverage, "references do not cover every variable exactly once")

    raw_relations = _required(typed_graph, "relations")
    raw_relations isa AbstractVector || _compile_error(:relations, "relations must be an array")
    length(raw_relations) == residual_count ||
        _compile_error(:relation_count, "relation count does not match residual_count")
    relation_ids = Tuple(String(value) for value in raw_relations)
    allunique(relation_ids) || _compile_error(:duplicate_relation, "relations must be unique")
    for relation in relation_ids
        get(value_types, relation, nothing) == "relation" ||
            _compile_error(:relation_type, "relation $relation is missing or not relation-typed")
    end

    for (field, required_type) in (("domains", "domain"), ("branches", "choice"))
        raw_ids = _required(typed_graph, field)
        raw_ids isa AbstractVector || _compile_error(:role_shape, "$field must be an array")
        ids = Tuple(String(value) for value in raw_ids)
        allunique(ids) || _compile_error(:duplicate_role, "$field must be unique")
        for id in ids
            get(value_types, id, nothing) == required_type ||
                _compile_error(:role_type, "$field node $id has the wrong type")
        end
    end

    supports = [Int[] for _ in 1:variable_count]
    for (row, relation) in enumerate(relation_ids)
        for column in dependencies[relation]
            push!(supports[column], row)
        end
    end
    row_supports = Tuple(Tuple(rows) for rows in supports)
    structural_nonzeros = sum(length, row_supports)
    compiler_document = Dict{String,Any}(
        "residual_count" => Int(residual_count),
        "row_supports" => Any[collect(rows) for rows in row_supports],
        "structural_nonzeros" => structural_nonzeros,
        "variable_count" => Int(variable_count),
    )
    return DependencyStructure(
        row_supports,
        structural_nonzeros,
        Int(variable_count),
        Int(residual_count),
        string(canonical_json_hash(compiler_document)),
    )
end


function compile_structure(typed_graph, variable_count::Integer, residual_count::Integer)
    dependencies = compile_dependencies(typed_graph, variable_count, residual_count)
    groups = _natural_groups(dependencies.row_supports)
    structural_nonzeros = dependencies.structural_nonzeros
    provider = ProviderProjection(dependencies.row_supports, groups, structural_nonzeros)
    route = RouteProjection(
        Int(variable_count),
        Int(residual_count),
        structural_nonzeros,
        length(groups),
    )
    return CompiledStructure(
        provider,
        route,
        _projection_hash(provider),
        _projection_hash(route),
    )
end

function use_colored_route(route::RouteProjection)
    n = route.variable_count
    m = route.residual_count
    nnz = route.structural_nonzeros
    c = route.color_count
    n > 0 || return false
    m > 0 || return false
    0 <= nnz || return false
    big(nnz) <= big(m) * big(n) || return false
    0 <= c <= n || return false
    nnz >= c || return false
    (nnz == 0) == (c == 0) || return false
    c < n || return false
    return 40 * big(n) * big(c) + 5 * big(nnz) <= 32 * big(n) * big(n)
end

function seal_provider(structure::CompiledStructure)
    projection = structure.provider
    route = structure.route
    return GeoTargetCore._sealed_local_jacobian_provider(
        projection.row_supports,
        projection.groups,
        projection.structural_nonzeros,
        route.residual_count,
        route.variable_count,
        structure.provider_hash,
    )
end

function parse_program(raw, variable_count::Integer)::AbstractJac003Program
    kind = String(_required(raw, "kind"))
    offsets = _float_tuple(_required(raw, "offsets"), "offsets")
    length(offsets) == variable_count ||
        _compile_error(:program_dimension, "offset count does not match variable_count")
    if kind == "sin-cos-tree-v1"
        children = Tuple(
            _index_tuple(values, variable_count, "children") for
            values in _required(raw, "children")
        )
        length(children) == variable_count ||
            _compile_error(:program_dimension, "children count does not match variable_count")
        amplitude = Float64(_required(raw, "amplitude"))
        isfinite(amplitude) || _compile_error(:program_value, "amplitude must be finite")
        return SinCosTreeProgram(offsets, children, amplitude)
    elseif kind == "safe-rational-hypergraph-v1"
        edges = Tuple(
            _index_tuple(values, variable_count, "edges") for
            values in _required(raw, "edges")
        )
        length(edges) == variable_count ||
            _compile_error(:program_dimension, "edge count does not match variable_count")
        margin = Float64(_required(raw, "margin"))
        alpha = Float64(_required(raw, "alpha"))
        isfinite(margin) && margin > 0 ||
            _compile_error(:program_value, "margin must be finite and positive")
        isfinite(alpha) || _compile_error(:program_value, "alpha must be finite")
        return SafeRationalProgram(offsets, edges, margin, alpha)
    elseif kind == "hex-ring-atan-v1"
        neighbours = Tuple(
            _index_tuple(values, variable_count, "neighbours") for
            values in _required(raw, "neighbours")
        )
        length(neighbours) == variable_count || _compile_error(
            :program_dimension,
            "neighbour count does not match variable_count",
        )
        curvature = Float64(_required(raw, "curvature"))
        alpha = Float64(_required(raw, "alpha"))
        isfinite(curvature) && curvature > 0 ||
            _compile_error(:program_value, "curvature must be finite and positive")
        isfinite(alpha) || _compile_error(:program_value, "alpha must be finite")
        return HexRingAtanProgram(offsets, neighbours, curvature, alpha)
    elseif kind == "dense-chart-v1"
        matrix = Tuple(
            _float_tuple(row, "matrix row") for row in _required(raw, "matrix")
        )
        alternate = Tuple(
            _float_tuple(row, "alternate matrix row") for
            row in _required(raw, "alternate_matrix")
        )
        length(matrix) == variable_count && all(row -> length(row) == variable_count, matrix) ||
            _compile_error(:program_dimension, "matrix must be square")
        length(alternate) == variable_count &&
            all(row -> length(row) == variable_count, alternate) ||
            _compile_error(:program_dimension, "alternate matrix must be square")
        weights = _float_tuple(_required(raw, "chart_weights"), "chart_weights")
        length(weights) == variable_count ||
            _compile_error(:program_dimension, "chart weights do not match variable_count")
        chart_text = String(_required(raw, "chart"))
        chart_text in ("piecewise", "smooth-switch") ||
            _compile_error(:program_value, "unknown chart")
        threshold = Float64(_required(raw, "chart_threshold"))
        gain = Float64(_required(raw, "smooth_gain"))
        isfinite(threshold) && isfinite(gain) ||
            _compile_error(:program_value, "chart values must be finite")
        return DenseChartProgram(
            offsets,
            matrix,
            alternate,
            Symbol(chart_text),
            weights,
            threshold,
            gain,
        )
    end
    _compile_error(:program_kind, "unknown JAC003 oracle program")
end

function residual_values(program::SinCosTreeProgram, point::Vector{Float64})
    delta = point .+ collect(program.offsets)
    result = zeros(Float64, length(point))
    for (row, children) in enumerate(program.children)
        correction = if isempty(children)
            0.0
        else
            total = sum(delta[column] for column in children)
            sin(total) + 0.5 * (1.0 - cos(delta[first(children)]))
        end
        result[row] = delta[row] + program.amplitude * correction
    end
    return result
end

function residual_values(program::SafeRationalProgram, point::Vector{Float64})
    delta = point .+ collect(program.offsets)
    return Float64[
        delta[row] + program.alpha * sum(
            delta[column] / (program.margin + delta[column]^2) for column in edge
        ) for (row, edge) in enumerate(program.edges)
    ]
end

function residual_values(program::HexRingAtanProgram, point::Vector{Float64})
    delta = point .+ collect(program.offsets)
    return Float64[
        delta[row] + program.alpha * sum(
            atan(program.curvature * delta[column]) / program.curvature for
            column in neighbours
        ) for (row, neighbours) in enumerate(program.neighbours)
    ]
end

function residual_values(program::DenseChartProgram, point::Vector{Float64})
    delta = point .+ collect(program.offsets)
    chart_value = sum(collect(program.chart_weights) .* point) - program.chart_threshold
    if program.chart == :piecewise
        selected = chart_value >= 0.0 ? program.matrix : program.alternate_matrix
        return Float64[
            delta[row] + sum(collect(selected[row]) .* delta) for row in eachindex(delta)
        ]
    end
    return Float64[
        delta[row] + program.smooth_gain * tanh(sum(collect(program.matrix[row]) .* delta))
        for row in eachindex(delta)
    ]
end

_branch_observations(::AbstractJac003Program, point) = ()

function _branch_observations(program::DenseChartProgram, point)
    margin = sum(collect(program.chart_weights) .* point) - program.chart_threshold
    key = margin >= 0.0 ? ChoiceKey("nonnegative") : ChoiceKey("negative")
    decision = BranchDecision(NodeId("chart000"), key)
    return (BranchObservation(decision, abs(margin), abs(margin)),)
end

_domain_observations(::AbstractJac003Program, point) = ()

function _domain_observations(program::SafeRationalProgram, point)
    delta = point .+ collect(program.offsets)
    return Tuple(
        DomainObservation(
            NodeId("d$(lpad(row - 1, 3, '0'))"),
            minimum(program.margin + delta[column]^2 for column in edge),
            true,
            true,
        ) for (row, edge) in enumerate(program.edges)
    )
end

function observation(program::AbstractJac003Program, raw_point)
    point = Float64[Float64(value) for value in raw_point]
    residual = residual_values(program, point)
    all(isfinite, residual) || return OracleObservation(
        (), nothing, (), (), (), EVAL_NONFINITE, 1, "nonfinite JAC003 residual",
    )
    relations = Tuple(
        RelationObservation(
            NodeId("r$(lpad(row - 1, 3, '0'))"),
            value,
            1.0,
            value,
            nothing,
        ) for (row, value) in enumerate(residual)
    )
    return OracleObservation(
        relations,
        nothing,
        (),
        _domain_observations(program, point),
        _branch_observations(program, point),
        EVAL_OK,
        1,
        nothing,
    )
end

function _solver_inputs(
    variable_count::Integer,
    origins,
    scales,
    lower,
    upper,
    budgets,
)
    origin_values = _float_tuple(origins, "origins")
    scale_values = _float_tuple(scales, "scales")
    lower_values = _float_tuple(lower, "lower")
    upper_values = _float_tuple(upper, "upper")
    all(length(values) == variable_count for values in (
        origin_values,
        scale_values,
        lower_values,
        upper_values,
    )) || _compile_error(:vector_dimension, "solver vectors do not match variable_count")
    all(value -> value > 0, scale_values) ||
        _compile_error(:scale_value, "scales must be positive")
    all(lower_values .< upper_values) ||
        _compile_error(:bound_value, "each lower bound must be below upper")
    max_iterations = _integer(_required(budgets, "max_iterations"), "max_iterations")
    max_evaluations = _integer(_required(budgets, "max_evaluations"), "max_evaluations")
    max_iterations == 250 || _compile_error(:budget_drift, "max_iterations must equal 250")
    max_evaluations == 2000 || _compile_error(:budget_drift, "max_evaluations must equal 2000")
    _integer(_required(budgets, "observation_wall_seconds"), "observation wall") == 60 ||
        _compile_error(:budget_drift, "observation wall must equal 60")
    _integer(_required(budgets, "hard_wall_seconds"), "hard wall") == 180 ||
        _compile_error(:budget_drift, "hard wall must equal 180")
    options = LocalSolveOptions(; max_iterations, max_evaluations)
    return origin_values, scale_values, lower_values, upper_values, options
end

function compile_case_runner(
    typed_graph,
    oracle_program,
    variable_count::Integer,
    residual_count::Integer,
    origins,
    scales,
    lower,
    upper,
    budgets,
)
    structure = compile_structure(typed_graph, variable_count, residual_count)
    program = parse_program(oracle_program, variable_count)
    origin_values, scale_values, lower_values, upper_values, options = _solver_inputs(
        variable_count,
        origins,
        scales,
        lower,
        upper,
        budgets,
    )
    provider = use_colored_route(structure.route) ? seal_provider(structure) : nothing
    return CompiledCaseRunner(
        program,
        structure,
        provider,
        origin_values,
        scale_values,
        lower_values,
        upper_values,
        options,
    )
end

function compile_dense_case_runner(
    typed_graph,
    oracle_program,
    variable_count::Integer,
    residual_count::Integer,
    origins,
    scales,
    lower,
    upper,
    budgets,
)
    structure = compile_dependencies(typed_graph, variable_count, residual_count)
    program = parse_program(oracle_program, variable_count)
    origin_values, scale_values, lower_values, upper_values, options = _solver_inputs(
        variable_count,
        origins,
        scales,
        lower,
        upper,
        budgets,
    )
    return DenseCaseRunner(
        program,
        structure,
        origin_values,
        scale_values,
        lower_values,
        upper_values,
        options,
    )
end

function solve_attempt(
    runner::CompiledCaseRunner,
    raw_start;
    deadline_ns::UInt64,
    cancelled=() -> false,
    color_group_observer=nothing,
    jacobian_observer=nothing,
)
    start = Float64[Float64(value) for value in raw_start]
    length(start) == runner.structure.route.variable_count ||
        _compile_error(:start_dimension, "start does not match variable_count")
    evaluate_fn = point -> observation(runner.program, point)
    common = (
        origins=runner.origins,
        scales=runner.scales,
        lower=runner.lower,
        upper=runner.upper,
        options=runner.options,
        deadline_ns=deadline_ns,
        cancelled=cancelled,
        color_group_observer=color_group_observer,
        jacobian_observer=jacobian_observer,
    )
    if runner.provider === nothing
        return solve_local(evaluate_fn, start; common...)
    end
    return GeoTargetCore._solve_local_with_provider(
        evaluate_fn,
        start,
        runner.provider;
        common...,
    )
end

function solve_attempt(
    runner::DenseCaseRunner,
    raw_start;
    deadline_ns::UInt64,
    cancelled=() -> false,
    color_group_observer=nothing,
    jacobian_observer=nothing,
)
    start = Float64[Float64(value) for value in raw_start]
    length(start) == runner.structure.variable_count ||
        _compile_error(:start_dimension, "start does not match variable_count")
    evaluate_fn = point -> observation(runner.program, point)
    return solve_local(
        evaluate_fn,
        start;
        origins=runner.origins,
        scales=runner.scales,
        lower=runner.lower,
        upper=runner.upper,
        options=runner.options,
        deadline_ns,
        cancelled,
        color_group_observer,
        jacobian_observer,
    )
end

function visibility_record(structure::CompiledStructure)
    return Dict{String,Any}(
        "provider_field_names" => sort!(String[
            string(name) for name in fieldnames(ProviderProjection)
        ]),
        "provider_projection_hash" => structure.provider_hash,
        "route_field_names" => sort!(String[
            string(name) for name in fieldnames(RouteProjection)
        ]),
        "route_projection_hash" => structure.route_hash,
    )
end

export CandidateCompileError,
    ProviderProjection,
    RouteProjection,
    DependencyStructure,
    CompiledStructure,
    CompiledCaseRunner,
    DenseCaseRunner,
    compile_dependencies,
    compile_structure,
    compile_case_runner,
    compile_dense_case_runner,
    parse_program,
    seal_provider,
    use_colored_route,
    solve_attempt,
    observation,
    visibility_record,
    CANDIDATE_SCHEMA,
    PROVIDER_FIELDS,
    ROUTE_FIELDS

end
