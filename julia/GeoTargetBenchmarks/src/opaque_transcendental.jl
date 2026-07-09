struct OpaqueTranscendentalParams
    root_count::Int
    loop_count::Int
    phase::Float64
    mixing::Float64
    instance_seed::UInt64
    start_seed::UInt64
    start_count::Int
end

function OpaqueTranscendentalParams(;
    root_count::Integer=3,
    loop_count::Integer=8,
    phase::Real=0.0,
    mixing::Real=0.1,
    instance_seed::Integer=109,
    start_seed::Integer=1009,
    start_count::Integer=32,
)
    2 <= root_count <= 8 || throw(ArgumentError("root_count must lie in 2:8"))
    1 <= loop_count <= 64 || throw(ArgumentError("loop_count must lie in 1:64"))
    phase_value = Float64(phase)
    isfinite(phase_value) && abs(phase_value) <= 0.5 ||
        throw(ArgumentError("phase must be finite and lie in [-0.5, 0.5]"))
    mixing_value = Float64(mixing)
    isfinite(mixing_value) && 0 < mixing_value <= 0.25 ||
        throw(ArgumentError("mixing must lie in (0, 0.25]"))
    start_count > 0 || throw(ArgumentError("start_count must be positive"))
    return OpaqueTranscendentalParams(
        Int(root_count),
        Int(loop_count),
        phase_value,
        mixing_value,
        _validated_seed(instance_seed, "instance_seed"),
        _validated_seed(start_seed, "start_seed"),
        Int(start_count),
    )
end

"""Intentionally Float64-only opaque callback with loops, branches and transcendentals."""
function _opaque_c0_callback(
    input::Float64,
    loop_count::Int,
    mixing::Float64,
    bias::Float64,
)
    state = input + bias
    for iteration in 1:loop_count
        attenuation = inv(iteration + 1)
        transcendental = sin(state) + cos(attenuation * input) + exp(-abs(state))
        if isodd(iteration)
            state = tanh(transcendental / 3 + mixing * input / (1 + abs(input)))
        else
            state = tanh(transcendental / 3 - mixing * state + bias)
        end
    end
    return state
end

function _opaque_validated_targets(values)
    return AbstractGoldTargetDescriptor[
        ValidatedGoldTarget(
            string("target-", lpad(index, 3, '0')),
            prevfloat(value),
            nextfloat(value),
            "outward-rounded direct C0 opaque/transcendental replay",
            [index],
        ) for (index, value) in enumerate(values)
    ]
end

function generate(parameters::OpaqueTranscendentalParams)
    count = parameters.root_count
    roots = collect(range(-0.75, 0.75; length=count)) .+ parameters.phase
    bias = Float64(parameters.instance_seed % UInt64(101)) / 1000
    opaque_values = Float64[
        _opaque_c0_callback(root, parameters.loop_count, parameters.mixing, bias) for
        root in roots
    ]
    configurations = vcat(transpose(roots), transpose(opaque_values))
    expected_targets = roots .+ 0.125 .* opaque_values
    gold_targets = _opaque_validated_targets(expected_targets)
    lower = [parameters.phase - 1.25, -1.5]
    upper = [parameters.phase + 1.25, 1.5]
    starts = _uniform_starts(lower, upper, parameters.start_count, parameters.start_seed)

    function residual!(output, input)
        _check_output_lengths(output, input, 2, 2)
        opaque = _opaque_c0_callback(
            input[1],
            parameters.loop_count,
            parameters.mixing,
            bias,
        )
        polynomial = prod(input[1] - root for root in roots)
        output[1] = polynomial * (1 + 0.05 * opaque)
        output[2] = input[2] - opaque
        return output
    end

    target(input) = input[1] + 0.125 * input[2]
    artifacts = MaterializedArtifact[
        _parameter_artifact(
            count,
            parameters.loop_count,
            parameters.phase,
            parameters.mixing,
            parameters.instance_seed,
            parameters.start_seed,
            parameters.start_count,
        ),
        MaterializedArtifact(:latent_roots, reshape(roots, :, 1)),
        MaterializedArtifact(:opaque_callback_values, reshape(opaque_values, :, 1)),
        MaterializedArtifact(:expected_target_values, reshape(expected_targets, :, 1)),
        MaterializedArtifact(
            :capability_contract,
            reshape([1.0, 0.0, 0.0, 0.0, 0.0], :, 1),
        ),
        MaterializedArtifact(:opaque_contract, reshape([bias, 0.125, 0.05], :, 1)),
    ]
    metadata = Dict{Symbol,Any}(
        :declared_capabilities => (:C0,),
        :opaque_callback => true,
        :transcendental_calls => (:sin, :cos, :exp, :tanh),
        :loop_count => parameters.loop_count,
        :control_flow_paths => 2,
        :numeric_type => Float64,
        :capability_order => (:C0, :C1, :C2, :C3V, :C3A),
        :plugin_high_precision_available => false,
        :plugin_validated_available => false,
        :plugin_algebraic_available => false,
        :expected_target_values => copy(expected_targets),
        :generator_role => :c0_opaque_transcendental_control,
    )
    instance_id = string(
        "opaque-transcendental-n",
        count,
        "-loops",
        parameters.loop_count,
        "-phase",
        parameters.phase,
        "-mix",
        parameters.mixing,
        "-i",
        parameters.instance_seed,
        "-s",
        parameters.start_seed,
    )
    return DirectAnalyticProblem(
        instance_id,
        "OPAQUE-TRANSCENDENTAL-C0",
        (:S6,),
        parameters,
        2,
        2,
        residual!,
        nothing,
        target,
        lower,
        upper,
        [1.25, 1.5],
        [1.0, 1.0],
        configurations,
        gold_targets,
        starts,
        artifacts,
        metadata,
    )
end
