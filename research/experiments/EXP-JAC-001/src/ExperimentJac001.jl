module ExperimentJac001

using GeoTargetBase
using GeoTargetCore
using JSON3
using LinearAlgebra
using Random
using SHA
using Statistics
using UUIDs

const EXPERIMENT_ID = "EXP-JAC-001"
const REPO_ROOT = normpath(joinpath(@__DIR__, "..", "..", "..", ".."))
const EXPERIMENT_ROOT = normpath(joinpath(@__DIR__, ".."))
const CARD_PATH = joinpath(REPO_ROOT, "research", "experiments", "EXP-JAC-001.json")
const PREREGISTRATION_PATH = joinpath(
    EXPERIMENT_ROOT,
    "frozen",
    "EXP-JAC-001-preregistered.json",
)
const DEVELOPMENT_COUNT = 10
const LOCKED_COUNT = 30
const START_COUNT = 32
const PREFIXES = (8, 16, 32)
const MAX_ITERATIONS = 250
const MAX_EVALUATIONS = 2_000
const CANONICAL_RESIDUAL_TOLERANCE = 1.0e-8
const GOLD_CONFIGURATION_TOLERANCE = 1.0e-5
const GOLD_TARGET_TOLERANCE = 1.0e-6
const DENSE_COLOR_ATOL = 1.0e-10
const DENSE_COLOR_RTOL = 1.0e-10
const DENSE_ANALYTIC_ATOL = 2.0e-5
const DENSE_ANALYTIC_RTOL = 2.0e-5

const PLUGIN_ID = PluginId(
    UUID("c941aa6f-5d92-40af-9ac8-13996b305dbe"),
    "exp_jac_001",
)
const SCALAR_TYPE_ID = TypeId(PLUGIN_ID, "Real")
const PLUGIN_VERSION = v"1.0.0"
const PLUGIN_CONTENT = content_hash("EXP-JAC-001 typed analytic graph plugin v1")

const ADD_ID = PrimitiveId(PLUGIN_ID, "add")
const SUB_ID = PrimitiveId(PLUGIN_ID, "subtract")
const MUL_ID = PrimitiveId(PLUGIN_ID, "multiply")
const BRANCH_WARP_ID = PrimitiveId(PLUGIN_ID, "piecewise_warp")
const ZERO_ID = PrimitiveId(PLUGIN_ID, "zero_relation")

_decode_real(value) = value isa Real && !(value isa Bool) ? Float64(value) :
    throw(ArgumentError("expected a real JSON literal"))
_encode_real(value::Real) = Float64(value)
_piecewise_warp(value::Real) = value >= 0 ? value + 0.05value^2 : value - 0.05value^2

function _kernel(
    evaluator;
    smoothness::SmoothnessClass=SMOOTH_C1,
)
    return OperatorKernel(
        evaluator;
        capabilities=CapabilitySet(C0),
        smoothness,
        derivative_mode=DERIVATIVE_NONE,
        generic_numeric=true,
        deterministic=true,
    )
end

function experiment_plugin()
    scalar = TypeSpec(
        SCALAR_TYPE_ID,
        Real;
        encoder=_encode_real,
        decoder=_decode_real,
        documentation="EXP-JAC-001 finite real scalar",
    )
    unary = SignatureSpec((SCALAR_TYPE_ID,), SCALAR_TYPE_ID)
    binary = SignatureSpec((SCALAR_TYPE_ID, SCALAR_TYPE_ID), SCALAR_TYPE_ID)
    primitives = (
        PrimitiveSpec(ADD_ID, (binary,), _kernel(+); documentation="scalar addition"),
        PrimitiveSpec(SUB_ID, (binary,), _kernel(-); documentation="scalar subtraction"),
        PrimitiveSpec(MUL_ID, (binary,), _kernel(*); documentation="scalar multiplication"),
        PrimitiveSpec(
            BRANCH_WARP_ID,
            (unary,),
            _kernel(_piecewise_warp; smoothness=PIECEWISE_SMOOTH);
            documentation="continuous piecewise-smooth branch warp",
        ),
    )
    relation = RelationSpec(
        ZERO_ID,
        (unary,),
        _kernel(identity);
        truth=iszero,
        truth_policy=RELATION_TRUTH_APPROXIMATE_ZERO,
        scale_hint=1.0,
        documentation="zero residual relation",
    )
    return PluginSpec(
        PLUGIN_ID,
        PLUGIN_VERSION,
        CORE_ABI_VERSION,
        PLUGIN_CONTENT;
        types=(scalar,),
        primitives,
        relations=(relation,),
    )
end

function experiment_registry()
    plugin = experiment_plugin()
    builder = RegistryBuilder(allowlist=(plugin.id,))
    register!(builder, plugin)
    return freeze(builder)
end

struct GeneratedInstance
    case_id::String
    family_id::String
    generator_id::String
    instance_seed::Int
    start_seed::Int
    factors::Dict{String,Any}
    problem::ProblemSpecV1
    coefficient_matrix::Matrix{Float64}
    root::Vector{Float64}
    starts::Matrix{Float64}
    nonlinear_kind::Symbol
    nonlinear_parameter::Float64
    row_scales::Vector{Float64}
    strata::Vector{String}
end

function _node_builder(nodes)
    counter = Ref(0)
    function literal(value, label)
        counter[] += 1
        id = NodeId("$(label)_lit_$(counter[])")
        push!(nodes, LiteralNode(id, SCALAR_TYPE_ID, Float64(value)))
        return id
    end
    function call(operation, arguments, label)
        counter[] += 1
        id = NodeId("$(label)_call_$(counter[])")
        push!(nodes, CallNode(id, operation, Tuple(arguments)))
        return id
    end
    return literal, call
end

function _expression_problem(
    matrix::AbstractMatrix,
    root::AbstractVector;
    nonlinear_kind::Symbol,
    nonlinear_parameter::Real,
    row_scales::AbstractVector=ones(size(matrix, 1)),
)
    residual_count, variable_count = size(matrix)
    residual_count == variable_count || throw(ArgumentError("experiment systems must be square"))
    length(root) == variable_count || throw(DimensionMismatch("root dimension mismatch"))
    length(row_scales) == residual_count || throw(DimensionMismatch("row scale mismatch"))
    nodes = AbstractGraphNode[]
    references = NodeId[]
    variables = VariableSpec[]
    for column in 1:variable_count
        variable = VariableSpec(
            VariableId("x_$column"),
            SCALAR_TYPE_ID,
            root[column],
            1.0;
            lower=-0.8,
            upper=0.8,
        )
        push!(variables, variable)
        id = NodeId("x_$column")
        push!(nodes, ReferenceNode(id, variable.id))
        push!(references, id)
    end
    literal, call = _node_builder(nodes)
    relations = RelationBinding[]
    for row in 1:residual_count
        terms = NodeId[]
        for column in 1:variable_count
            coefficient = Float64(matrix[row, column])
            iszero(coefficient) && continue
            transformed = if nonlinear_kind === :cubic_delta
                root_node = literal(root[column], "r$(row)_c$(column)_root")
                delta = call(SUB_ID, (references[column], root_node), "r$(row)_c$(column)_delta")
                square = call(MUL_ID, (delta, delta), "r$(row)_c$(column)_square")
                cube = call(MUL_ID, (square, delta), "r$(row)_c$(column)_cube")
                curvature = literal(
                    nonlinear_parameter,
                    "r$(row)_c$(column)_curvature",
                )
                curved = call(MUL_ID, (curvature, cube), "r$(row)_c$(column)_curved")
                call(ADD_ID, (delta, curved), "r$(row)_c$(column)_warp")
            elseif nonlinear_kind === :piecewise_absolute
                warped = call(BRANCH_WARP_ID, (references[column],), "r$(row)_c$(column)_branch")
                root_warp = literal(
                    _piecewise_warp(root[column]),
                    "r$(row)_c$(column)_rootwarp",
                )
                call(SUB_ID, (warped, root_warp), "r$(row)_c$(column)_delta")
            else
                throw(ArgumentError("unknown nonlinear kind $nonlinear_kind"))
            end
            coefficient_node = literal(coefficient, "r$(row)_c$(column)_coefficient")
            push!(
                terms,
                call(MUL_ID, (coefficient_node, transformed), "r$(row)_c$(column)_term"),
            )
        end
        isempty(terms) && error("every residual needs structural support")
        total = first(terms)
        for (index, term) in enumerate(terms[2:end])
            total = call(ADD_ID, (total, term), "r$(row)_sum_$(index + 1)")
        end
        scale = Float64(row_scales[row])
        raw = if scale == 1.0
            total
        else
            scale_node = literal(scale, "r$(row)_scale")
            call(MUL_ID, (scale_node, total), "r$(row)_scaled")
        end
        relation_node = call(ZERO_ID, (raw,), "relation_$row")
        push!(relations, RelationBinding(relation_node; scale_override=scale))
    end
    graph = ConstructionGraph(Tuple(nodes))
    plugin = experiment_plugin()
    return ProblemSpecV1(
        (plugin_lock(plugin),),
        Tuple(variables),
        graph;
        relations=Tuple(relations),
        target=first(references),
    )
end

function _strictly_diagonal_matrix(rng, dimension, supports)
    matrix = zeros(Float64, dimension, dimension)
    for row in 1:dimension
        matrix[row, row] = 1.0
        for column in supports[row]
            column == row && continue
            matrix[row, column] = (rand(rng, Bool) ? 1.0 : -1.0) *
                                  (0.08 / max(1, length(supports[row]) - 1))
        end
    end
    return matrix
end

function _root_vector(rng, dimension; magnitude=0.25)
    return [magnitude * (2rand(rng) - 1) for _ in 1:dimension]
end

function _starts(rng, root, radius; boundary_distance=nothing)
    dimension = length(root)
    starts = Matrix{Float64}(undef, dimension, START_COUNT)
    for index in 1:START_COUNT
        for column in 1:dimension
            starts[column, index] = clamp(
                root[column] + radius * (2rand(rng) - 1),
                -0.8,
                0.8,
            )
        end
    end
    if boundary_distance !== nothing
        distance = Float64(boundary_distance)
        starts[:, 1] .= 0.8 - distance
        dimension > 1 && (starts[2:2:end, 1] .*= -1)
    end
    return starts
end

function _diagonal_instance(partition, index, instance_seed, start_seed; locked=false)
    dimensions = (2, 4, 8, 16, 2, 4, 8, 16, 8, 16)
    blocks = (1, 2, 4, 1, 2, 4, 1, 2, 4, 2)
    spreads = (1.0, 1.0e8, 1.0e8, 1.0, 1.0e8, 1.0, 1.0e8, 1.0, 1.0e8, 1.0)
    factor_index = mod1(index, length(dimensions))
    dimension = dimensions[factor_index]
    block_size = min(blocks[factor_index], dimension)
    spread = spreads[factor_index]
    rng = Xoshiro(instance_seed)
    ordering = locked ? randperm(rng, dimension) : collect(1:dimension)
    groups = [ordering[first:min(first + block_size - 1, dimension)] for first in 1:block_size:dimension]
    supports = [copy(only(filter(group -> row in group, groups))) for row in 1:dimension]
    matrix = _strictly_diagonal_matrix(rng, dimension, supports)
    root = _root_vector(rng, dimension)
    row_scales = dimension == 1 ? ones(1) : [
        10.0^(log10(spread) * (row - 1) / (dimension - 1)) for row in 1:dimension
    ]
    problem = _expression_problem(
        matrix,
        root;
        nonlinear_kind=:cubic_delta,
        nonlinear_parameter=0.05,
        row_scales,
    )
    starts = _starts(Xoshiro(start_seed), root, 0.25)
    return GeneratedInstance(
        "$(partition)-diagonal-$(lpad(index, 3, '0'))",
        locked ? "JAC-PERMUTED-BLOCK-LOCKED" : "JAC-DIAGONAL-BLOCK",
        locked ? "typed-permuted-block-locked-v1" : "typed-block-v1",
        instance_seed,
        start_seed,
        Dict(
            "dimension" => dimension,
            "block_size" => block_size,
            "scale_spread" => spread,
        ),
        problem,
        matrix,
        root,
        starts,
        :cubic_delta,
        0.05,
        row_scales,
        ["S1", "S6"],
    )
end

function _banded_instance(partition, index, instance_seed, start_seed; locked=false)
    dimensions = (4, 8, 16, 4, 8, 16, 8, 16, 4, 16)
    bandwidths = (1, 2, 4, 2, 4, 1, 1, 2, 4, 4)
    curvatures = (1.0, 1.0e4, 1.0, 1.0e4, 1.0, 1.0e4, 1.0, 1.0e4, 1.0e4, 1.0)
    factor_index = mod1(index, length(dimensions))
    dimension = dimensions[factor_index]
    bandwidth = min(bandwidths[factor_index], dimension - 1)
    curvature = curvatures[factor_index]
    rng = Xoshiro(instance_seed)
    supports = if locked
        [
            sort!(unique([mod1(row + offset, dimension) for offset in -bandwidth:bandwidth])) for
            row in 1:dimension
        ]
    else
        [
            collect(max(1, row - bandwidth):min(dimension, row + bandwidth)) for
            row in 1:dimension
        ]
    end
    matrix = _strictly_diagonal_matrix(rng, dimension, supports)
    root = _root_vector(rng, dimension)
    problem = _expression_problem(
        matrix,
        root;
        nonlinear_kind=:cubic_delta,
        nonlinear_parameter=curvature,
    )
    radius = min(0.2, 0.1 / sqrt(curvature))
    starts = _starts(Xoshiro(start_seed), root, radius)
    return GeneratedInstance(
        "$(partition)-banded-$(lpad(index, 3, '0'))",
        locked ? "JAC-CYCLIC-BANDED-LOCKED" : "JAC-BANDED-CHAIN",
        locked ? "typed-cyclic-banded-locked-v1" : "typed-banded-v1",
        instance_seed,
        start_seed,
        Dict(
            "dimension" => dimension,
            "bandwidth" => bandwidth,
            "curvature" => curvature,
        ),
        problem,
        matrix,
        root,
        starts,
        :cubic_delta,
        curvature,
        ones(dimension),
        ["S2", "S6"],
    )
end

function _dense_supports(rng, dimension, density)
    target = max(dimension, ceil(Int, density * dimension^2))
    entries = Set((row, row) for row in 1:dimension)
    candidates = [(row, column) for row in 1:dimension for column in 1:dimension if row != column]
    shuffle!(rng, candidates)
    for entry in candidates
        length(entries) >= target && break
        push!(entries, entry)
    end
    return [sort([column for (candidate_row, column) in entries if candidate_row == row]) for row in 1:dimension]
end

function _dense_instance(partition, index, instance_seed, start_seed; locked=false)
    dimensions = (2, 4, 8, 2, 4, 8, 4, 8, 2, 8)
    densities = (0.5, 1.0, 0.5, 1.0, 0.5, 1.0, 0.5, 1.0, 0.5, 1.0)
    distances = (0.0, 1.0e-8, 0.1, 1.0e-8, 0.1, 0.0, 0.0, 0.1, 0.1, 1.0e-8)
    factor_index = mod1(index, length(dimensions))
    dimension = dimensions[factor_index]
    density = densities[factor_index]
    boundary_distance = distances[factor_index]
    rng = Xoshiro(instance_seed)
    supports = _dense_supports(rng, dimension, density)
    matrix = _strictly_diagonal_matrix(rng, dimension, supports)
    root = [isodd(column) ? boundary_distance : -boundary_distance for column in 1:dimension]
    problem = _expression_problem(
        matrix,
        root;
        nonlinear_kind=:piecewise_absolute,
        nonlinear_parameter=0.05,
    )
    starts = _starts(
        Xoshiro(start_seed),
        root,
        0.2;
        boundary_distance,
    )
    return GeneratedInstance(
        "$(partition)-dense-branch-$(lpad(index, 3, '0'))",
        locked ? "JAC-MIXED-BRANCH-LOCKED" : "JAC-DENSE-AND-BRANCH",
        locked ? "typed-mixed-branch-locked-v1" : "typed-dense-branch-v1",
        instance_seed,
        start_seed,
        Dict(
            "dimension" => dimension,
            "density" => density,
            "boundary_distance" => boundary_distance,
        ),
        problem,
        matrix,
        root,
        starts,
        :piecewise_absolute,
        0.05,
        ones(dimension),
        ["S4", "S6"],
    )
end

function generated_instances(partition::Symbol)
    family_counts, prefix, instance_base, start_base = if partition === :development
        ((4, 3, 3), "development", 110_000, 210_000)
    elseif partition === :locked
        ((10, 10, 10), "locked", 910_000, 1_010_000)
    else
        throw(ArgumentError("partition must be development or locked"))
    end
    instances = GeneratedInstance[]
    for family in 1:3, index in 1:family_counts[family]
        instance_seed = instance_base + 10_000family + index
        start_seed = start_base + 10_000family + index
        generator = family == 1 ? _diagonal_instance : family == 2 ? _banded_instance : _dense_instance
        push!(
            instances,
            generator(
                prefix,
                index,
                instance_seed,
                start_seed;
                locked=partition === :locked,
            ),
        )
    end
    length(instances) == (partition === :development ? DEVELOPMENT_COUNT : LOCKED_COUNT) ||
        error("partition seed count drift")
    return instances
end

function _analytic_jacobian(instance::GeneratedInstance, x)
    derivatives = if instance.nonlinear_kind === :cubic_delta
        1 .+ 3instance.nonlinear_parameter .* (x .- instance.root) .^ 2
    elseif instance.nonlinear_kind === :piecewise_absolute
        1 .+ 0.1 .* abs.(x)
    else
        error("unknown nonlinear kind")
    end
    return instance.coefficient_matrix * Diagonal(derivatives)
end

_matrix_document(matrix) = [collect(Float64, matrix[row, :]) for row in axes(matrix, 1)]
_starts_document(starts) = [collect(Float64, starts[:, column]) for column in axes(starts, 2)]

function _hash_document(value)
    return replace(string(canonical_json_hash(value)), "sha256:" => "")
end

_file_sha256(path) = bytes2hex(sha256(read(path)))
_preregistration_path() = isfile(PREREGISTRATION_PATH) ? PREREGISTRATION_PATH : CARD_PATH

function _plugin_lock_document()
    lock = plugin_lock(experiment_plugin())
    return Dict{String,Any}(
        "plugin_id" => string(lock.id),
        "version" => string(lock.version),
        "core_abi" => string(lock.core_abi),
        "content_hash" => string(lock.content),
    )
end

plugin_lock_sha256() = _hash_document(_plugin_lock_document())

function _dense_trace(instance, compiled, start)
    origins = copy(instance.root)
    scales = ones(length(instance.root))
    lower = fill(-0.8, length(instance.root))
    upper = fill(0.8, length(instance.root))
    lower_u = lower .- origins
    upper_u = upper .- origins
    u = start .- origins
    workspace = CompiledWorkspace(compiled)
    evaluate_fn = x -> evaluate(compiled, x; workspace)
    base = evaluate_fn(start)
    base.status == EVAL_OK || error("frozen start is not evaluable")
    base_residual = Float64[relation.scaled for relation in base.relations]
    jacobian, callbacks = GeoTargetCore._finite_difference_jacobian(
        evaluate_fn,
        u,
        base_residual,
        origins,
        scales,
        lower_u,
        upper_u,
        LocalSolveOptions().finite_difference_step,
    )
    analytic = _analytic_jacobian(instance, start)
    analytic_error = maximum(abs.(jacobian .- analytic))
    tolerance = DENSE_ANALYTIC_ATOL + DENSE_ANALYTIC_RTOL * maximum(abs.(analytic))
    analytic_error <= tolerance || error(
        "dense finite difference disagrees with analytic Jacobian for $(instance.case_id): " *
        "$analytic_error > $tolerance",
    )
    return Dict{String,Any}(
        "base_residual" => collect(base_residual),
        "jacobian" => _matrix_document(jacobian),
        "callbacks" => callbacks,
        "analytic_max_error" => analytic_error,
    )
end

function _instance_document(instance, registry)
    encoded = encode_problem_json(instance.problem, registry)
    problem_document = parse_protocol_json(encoded)
    compiled = compile_problem(instance.problem, registry; numeric_backend="Float64")
    expected_entries = Tuple(
        (row, column) for row in axes(instance.coefficient_matrix, 1) for
        column in axes(instance.coefficient_matrix, 2) if
        !iszero(instance.coefficient_matrix[row, column])
    )
    compiled.sparsity.jacobian_entries == expected_entries || error(
        "compiler-derived pattern drift for $(instance.case_id)",
    )
    starts = _starts_document(instance.starts)
    truth = Dict{String,Any}(
        "root" => copy(instance.root),
        "target" => instance.root[1],
        "coefficient_matrix" => _matrix_document(instance.coefficient_matrix),
        "nonlinear_kind" => String(instance.nonlinear_kind),
        "nonlinear_parameter" => instance.nonlinear_parameter,
        "row_scales" => copy(instance.row_scales),
    )
    dense_traces = [
        _dense_trace(instance, compiled, instance.starts[:, index]) for
        index in axes(instance.starts, 2)
    ]
    pattern = [Any[row, column] for (row, column) in compiled.sparsity.jacobian_entries]
    return Dict{String,Any}(
        "case_id" => instance.case_id,
        "family_id" => instance.family_id,
        "generator_id" => instance.generator_id,
        "instance_seed" => instance.instance_seed,
        "start_seed" => instance.start_seed,
        "factors" => instance.factors,
        "strata" => instance.strata,
        "problem" => problem_document,
        "problem_sha256" => _hash_document(problem_document),
        "starts" => starts,
        "starts_sha256" => _hash_document(starts),
        "truth" => truth,
        "truth_sha256" => _hash_document(truth),
        "compiler_jacobian_entries" => pattern,
        "pattern_sha256" => _hash_document(pattern),
        "dense_traces" => dense_traces,
        "dense_traces_sha256" => _hash_document(dense_traces),
    )
end

function materialized_input_document(partition::Symbol)
    registry = experiment_registry()
    instances = [_instance_document(instance, registry) for instance in generated_instances(partition)]
    return Dict{String,Any}(
        "schema_version" => "exp-jac-001-input/v1",
        "experiment_id" => EXPERIMENT_ID,
        "partition" => String(partition),
        "locked_validation" => partition === :locked,
        "instance_count" => length(instances),
        "starts_per_instance" => START_COUNT,
        "prefixes" => collect(PREFIXES),
        "variants" => ["J0-DENSE-CENTRAL", "J1-GREEDY-COLOR"],
        "seed_namespaces" => Dict(
            "instance" => partition === :development ? "110000+family*10000+index" :
                          "910000+family*10000+index",
            "start" => partition === :development ? "210000+family*10000+index" :
                       "1010000+family*10000+index",
        ),
        "thresholds" => Dict(
            "canonical_residual" => CANONICAL_RESIDUAL_TOLERANCE,
            "gold_configuration_normalized" => GOLD_CONFIGURATION_TOLERANCE,
            "gold_target" => GOLD_TARGET_TOLERANCE,
            "dense_color_atol" => DENSE_COLOR_ATOL,
            "dense_color_rtol" => DENSE_COLOR_RTOL,
            "dense_analytic_atol" => DENSE_ANALYTIC_ATOL,
            "dense_analytic_rtol" => DENSE_ANALYTIC_RTOL,
            "max_iterations" => MAX_ITERATIONS,
            "max_evaluations" => MAX_EVALUATIONS,
            "j2_family_trigger_relative_gap" => 0.20,
            "j2_trigger_family_count" => 3,
            "color_lower_bound" => "maximum structural row support",
        ),
        "analysis_contract" => Dict(
            "bootstrap_seed" => 3_001,
            "bootstrap_resamples" => 10_000,
            "bootstrap_method" =>
                "resample families, then cases within family, retaining paired starts",
            "one_sided_lower_quantile" => 0.05,
            "paired_reduction" => "(J0 oracle_work - J1 oracle_work) / J0 oracle_work",
            "warm_overhead" => "paired mean (J1 wall - J0 wall) / J0 wall",
            "cold_coloring_fraction" =>
                "maximum case coloring_seconds / sum(J1 wall over 32 starts)",
            "sparse_development_families" =>
                ["JAC-DIAGONAL-BLOCK", "JAC-BANDED-CHAIN"],
            "dense_development_family" => "JAC-DENSE-AND-BRANCH",
            "critical_boundary_distances" => [0.0, 1.0e-8],
        ),
        "card_sha256" => _file_sha256(_preregistration_path()),
        "plugin_lock" => _plugin_lock_document(),
        "plugin_lock_sha256" => plugin_lock_sha256(),
        "instances" => instances,
    )
end

function write_materialized_inputs(path::AbstractString, partition::Symbol)
    document = materialized_input_document(partition)
    mkpath(dirname(path))
    write(path, canonical_json(document))
    return path
end

function load_materialized_inputs(path::AbstractString)
    return JSON3.read(read(path, String), Dict{String,Any})
end

function validate_materialized_inputs(document)
    document["schema_version"] == "exp-jac-001-input/v1" || error("input schema drift")
    document["experiment_id"] == EXPERIMENT_ID || error("experiment ID drift")
    document["card_sha256"] == _file_sha256(_preregistration_path()) ||
        error("preregistered experiment card drift")
    document["plugin_lock_sha256"] == plugin_lock_sha256() || error("plugin lock drift")
    length(document["instances"]) == document["instance_count"] || error("instance count drift")
    registry = experiment_registry()
    seen = Set{String}()
    for instance in document["instances"]
        case_id = String(instance["case_id"])
        case_id in seen && error("duplicate case ID $case_id")
        push!(seen, case_id)
        _hash_document(instance["problem"]) == instance["problem_sha256"] ||
            error("problem checksum drift for $case_id")
        _hash_document(instance["starts"]) == instance["starts_sha256"] ||
            error("start checksum drift for $case_id")
        _hash_document(instance["truth"]) == instance["truth_sha256"] ||
            error("truth checksum drift for $case_id")
        _hash_document(instance["dense_traces"]) == instance["dense_traces_sha256"] ||
            error("dense trace checksum drift for $case_id")
        problem = decode_problem_document(instance["problem"], registry)
        compiled = compile_problem(problem, registry; numeric_backend="Float64")
        observed = [Any[row, column] for (row, column) in compiled.sparsity.jacobian_entries]
        canonical_json(observed) == canonical_json(instance["compiler_jacobian_entries"]) ||
            error("compiler pattern drift for $case_id")
    end
    return true
end

export EXPERIMENT_ID,
    REPO_ROOT,
    EXPERIMENT_ROOT,
    CARD_PATH,
    PREREGISTRATION_PATH,
    DEVELOPMENT_COUNT,
    LOCKED_COUNT,
    START_COUNT,
    PREFIXES,
    MAX_ITERATIONS,
    MAX_EVALUATIONS,
    CANONICAL_RESIDUAL_TOLERANCE,
    GOLD_CONFIGURATION_TOLERANCE,
    GOLD_TARGET_TOLERANCE,
    DENSE_COLOR_ATOL,
    DENSE_COLOR_RTOL,
    experiment_plugin,
    experiment_registry,
    generated_instances,
    materialized_input_document,
    write_materialized_inputs,
    load_materialized_inputs,
    validate_materialized_inputs,
    plugin_lock_sha256

end
