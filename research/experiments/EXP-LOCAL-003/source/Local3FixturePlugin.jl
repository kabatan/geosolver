module Local3FixturePlugin

using GeoTargetBase
using GeoTargetGeometry

export OpaqueProgram,
    execute_program,
    local3_fixture_plugin,
    LOCAL3_PLUGIN_ID,
    OPAQUE_PROGRAM_TYPE_ID,
    LOCAL3_CONTENT_HASH

struct OpaqueStepParameters
    loops::Int
    mixing::Float64
    bias::Float64
end

struct ProgramInstruction
    operation::Symbol
    argument::Union{Nothing,Int,Float64,OpaqueStepParameters}
end

"""A codec-locked stack program whose evaluator intentionally accepts only Float64."""
struct OpaqueProgram
    instructions::Tuple
end

const _UNARY_OPERATIONS = (:neg, :sin, :cos, :exp, :tanh, :abs, :sqrt)
const _BINARY_OPERATIONS = (:add, :sub, :mul, :div)
const _MAX_INSTRUCTIONS = 4096
const _MAX_INPUT_INDEX = 15

_codec_error(message::AbstractString) = throw(ArgumentError(String(message)))

function _object(raw, keys)
    raw isa AbstractDict || _codec_error("opaque program value must be an object")
    all(key -> key isa String, Base.keys(raw)) ||
        _codec_error("opaque program keys must be strings")
    actual = sort!(String[String(key) for key in Base.keys(raw)])
    expected = sort!(String[String(key) for key in keys])
    actual == expected || _codec_error(
        "opaque program object must contain exactly $(join(expected, ", "))",
    )
    return raw
end

function _decode_instruction(raw, index::Int)
    raw isa AbstractDict || _codec_error("instruction $index must be an object")
    haskey(raw, "op") || _codec_error("instruction $index is missing op")
    operation_raw = raw["op"]
    operation_raw isa String || _codec_error("instruction $index op must be a string")
    operation = Symbol(operation_raw)
    if operation === :input
        object = _object(raw, ("op", "index"))
        input_index = object["index"]
        input_index isa Integer && !(input_index isa Bool) ||
            _codec_error("instruction $index input index must be an integer")
        0 <= input_index <= _MAX_INPUT_INDEX ||
            _codec_error("instruction $index input index is outside 0:$_MAX_INPUT_INDEX")
        return ProgramInstruction(operation, Int(input_index))
    elseif operation === :constant
        object = _object(raw, ("op", "value"))
        value = object["value"]
        value isa Real && !(value isa Bool) ||
            _codec_error("instruction $index constant must be a number")
        number = Float64(value)
        isfinite(number) || _codec_error("instruction $index constant must be finite")
        return ProgramInstruction(operation, number)
    elseif operation === :opaque
        object = _object(raw, ("op", "loops", "mixing", "bias"))
        loops = object["loops"]
        loops isa Integer && !(loops isa Bool) && 1 <= loops <= 64 ||
            _codec_error("instruction $index opaque loops must be an integer in 1:64")
        mixing = object["mixing"]
        bias = object["bias"]
        mixing isa Real && !(mixing isa Bool) ||
            _codec_error("instruction $index opaque mixing must be a number")
        bias isa Real && !(bias isa Bool) ||
            _codec_error("instruction $index opaque bias must be a number")
        mixing_value = Float64(mixing)
        bias_value = Float64(bias)
        isfinite(mixing_value) && isfinite(bias_value) ||
            _codec_error("instruction $index opaque parameters must be finite")
        0.0 < mixing_value <= 0.25 ||
            _codec_error("instruction $index opaque mixing must lie in (0, 0.25]")
        abs(bias_value) <= 0.5 ||
            _codec_error("instruction $index opaque bias must lie in [-0.5, 0.5]")
        return ProgramInstruction(
            operation,
            OpaqueStepParameters(Int(loops), mixing_value, bias_value),
        )
    elseif operation in _UNARY_OPERATIONS || operation in _BINARY_OPERATIONS
        _object(raw, ("op",))
        return ProgramInstruction(operation, nothing)
    end
    _codec_error("instruction $index uses unsupported operation $(repr(operation_raw))")
end

function _validate_stack(instructions)
    depth = 0
    for (index, instruction) in enumerate(instructions)
        if instruction.operation in (:input, :constant)
            depth += 1
        elseif instruction.operation in _UNARY_OPERATIONS || instruction.operation === :opaque
            depth >= 1 || _codec_error("instruction $index has unary stack underflow")
        elseif instruction.operation in _BINARY_OPERATIONS
            depth >= 2 || _codec_error("instruction $index has binary stack underflow")
            depth -= 1
        else
            _codec_error("instruction $index has an unknown operation")
        end
    end
    depth == 1 || _codec_error("opaque program must leave exactly one stack value")
    return nothing
end

function _decode_program(raw)
    object = _object(raw, ("version", "instructions"))
    version = object["version"]
    version isa Integer && !(version isa Bool) && version == 1 ||
        _codec_error("opaque program version must be integer 1")
    instructions_raw = object["instructions"]
    instructions_raw isa AbstractVector ||
        _codec_error("opaque program instructions must be an array")
    1 <= length(instructions_raw) <= _MAX_INSTRUCTIONS ||
        _codec_error("opaque program instruction count is outside 1:$_MAX_INSTRUCTIONS")
    instructions = Tuple(
        _decode_instruction(instruction, index) for
        (index, instruction) in enumerate(instructions_raw)
    )
    _validate_stack(instructions)
    return OpaqueProgram(instructions)
end

function _encode_instruction(instruction::ProgramInstruction)
    if instruction.operation === :input
        return Dict{String,Any}(
            "op" => "input",
            "index" => instruction.argument::Int,
        )
    elseif instruction.operation === :constant
        return Dict{String,Any}(
            "op" => "constant",
            "value" => instruction.argument::Float64,
        )
    elseif instruction.operation === :opaque
        parameters = instruction.argument::OpaqueStepParameters
        return Dict{String,Any}(
            "op" => "opaque",
            "loops" => parameters.loops,
            "mixing" => parameters.mixing,
            "bias" => parameters.bias,
        )
    end
    return Dict{String,Any}("op" => String(instruction.operation))
end

function _encode_program(program::OpaqueProgram)
    return Dict{String,Any}(
        "version" => 1,
        "instructions" => Any[_encode_instruction(instruction) for instruction in program.instructions],
    )
end

function execute_program(program::OpaqueProgram, values::Vararg{Float64})
    isempty(values) && throw(ArgumentError("an opaque program requires at least one scalar input"))
    stack = Float64[]
    sizehint!(stack, length(program.instructions))
    for instruction in program.instructions
        operation = instruction.operation
        if operation === :input
            index = (instruction.argument::Int) + 1
            index <= length(values) || throw(BoundsError(values, index))
            push!(stack, values[index])
        elseif operation === :constant
            push!(stack, instruction.argument::Float64)
        elseif operation in _UNARY_OPERATIONS
            value = pop!(stack)
            result = if operation === :neg
                -value
            elseif operation === :sin
                sin(value)
            elseif operation === :cos
                cos(value)
            elseif operation === :exp
                exp(value)
            elseif operation === :tanh
                tanh(value)
            elseif operation === :abs
                abs(value)
            else
                sqrt(value)
            end
            push!(stack, result)
        elseif operation === :opaque
            input = pop!(stack)
            parameters = instruction.argument::OpaqueStepParameters
            state = input + parameters.bias
            for iteration in 1:parameters.loops
                attenuation = inv(Float64(iteration + 1))
                transcendental =
                    sin(state) + cos(attenuation * input) + exp(-abs(state))
                if isodd(iteration)
                    state = tanh(
                        transcendental / 3.0 +
                        parameters.mixing * input / (1.0 + abs(input)),
                    )
                else
                    state = tanh(
                        transcendental / 3.0 - parameters.mixing * state + parameters.bias,
                    )
                end
            end
            push!(stack, state)
        else
            right = pop!(stack)
            left = pop!(stack)
            result = if operation === :add
                left + right
            elseif operation === :sub
                left - right
            elseif operation === :mul
                left * right
            else
                left / right
            end
            push!(stack, result)
        end
    end
    return only(stack)
end

program_relation(program::OpaqueProgram, values::Vararg{Float64}) =
    execute_program(program, values...)
program_relation_truth(program::OpaqueProgram, values::Vararg{Float64}) =
    iszero(program_relation(program, values...))
program_target(program::OpaqueProgram, values::Vararg{Float64}) =
    execute_program(program, values...)
program_guard(program::OpaqueProgram, values::Vararg{Float64}) =
    execute_program(program, values...)
program_domain(program::OpaqueProgram, values::Vararg{Float64}) =
    execute_program(program, values...)

const LOCAL3_PLUGIN_ID =
    parse(PluginId, "dbf04752-3c0a-4a52-894d-d26ac0522dde/local3_c0_fixture")
const OPAQUE_PROGRAM_TYPE_ID = TypeId(LOCAL3_PLUGIN_ID, "opaque_program")

const _LOCAL3_MANIFEST_V1 = join(
    (
        "plugin=dbf04752-3c0a-4a52-894d-d26ac0522dde/local3_c0_fixture@0.1.0",
        "types=opaque_program",
        "primitives=program_target",
        "relations=program_relation",
        "relation_truth_policy=program_relation:approximate_zero",
        "guards=program_guard",
        "domains=program_domain",
        "signatures=opaque_program,variadic_scalar",
        "instructions=scalar_stack_v1,opaque_loop_v1",
        "capabilities=float64_c0_only",
    ),
    "\n",
)
const LOCAL3_CONTENT_HASH = content_hash(_LOCAL3_MANIFEST_V1)

function _c0_kernel(evaluator)
    return OperatorKernel(
        evaluator;
        capabilities = CapabilitySet(C0),
        smoothness = SMOOTHNESS_UNKNOWN,
        generic_numeric = false,
    )
end

function _build_plugin()
    program_type = TypeSpec(
        OPAQUE_PROGRAM_TYPE_ID,
        OpaqueProgram;
        encoder = _encode_program,
        decoder = _decode_program,
        documentation = "Codec-locked Float64-only stack program",
    )
    variadic_signature = SignatureSpec(
        (OPAQUE_PROGRAM_TYPE_ID, GeoTargetGeometry.SCALAR_TYPE_ID),
        GeoTargetGeometry.SCALAR_TYPE_ID;
        variadic = true,
    )
    target = PrimitiveSpec(
        PrimitiveId(LOCAL3_PLUGIN_ID, "program_target"),
        (variadic_signature,),
        _c0_kernel(program_target),
    )
    relation = RelationSpec(
        PrimitiveId(LOCAL3_PLUGIN_ID, "program_relation"),
        (variadic_signature,),
        _c0_kernel(program_relation);
        truth = program_relation_truth,
        truth_policy = RELATION_TRUTH_APPROXIMATE_ZERO,
        scale_hint = 1.0,
    )
    guard = GuardSpec(
        PrimitiveId(LOCAL3_PLUGIN_ID, "program_guard"),
        (variadic_signature,),
        _c0_kernel(program_guard);
        default_strict = true,
        scale_hint = 1.0,
    )
    domain = DomainSpec(
        PrimitiveId(LOCAL3_PLUGIN_ID, "program_domain"),
        (variadic_signature,),
        _c0_kernel(program_domain);
        default_strict = true,
    )
    return PluginSpec(
        LOCAL3_PLUGIN_ID,
        v"0.1.0",
        v"1.0.0",
        LOCAL3_CONTENT_HASH;
        types = (program_type,),
        primitives = (target,),
        relations = (relation,),
        guards = (guard,),
        domains = (domain,),
    )
end

const _LOCAL3_PLUGIN = _build_plugin()
local3_fixture_plugin() = _LOCAL3_PLUGIN

end
