struct NemoExactBackend <: GeoTargetCore.AbstractExactBackend
    recognition_options::RecognitionOptions
end

function NemoExactBackend(; recognition_options::RecognitionOptions=RecognitionOptions())
    maximum(recognition_options.degree_limits) <= 12 || throw(
        ArgumentError("production exactification degree limit cannot exceed 12"),
    )
    maximum(recognition_options.height_bits) <= 64 || throw(
        ArgumentError("production exactification coefficient height cannot exceed 64 bits"),
    )
    maximum(
        working_precision(
            degree,
            height;
            base_precision_bits=recognition_options.base_precision_bits,
        ) + recognition_options.confirmation_extra_bits for
        degree in recognition_options.degree_limits for
        height in recognition_options.height_bits
    ) <= GeoTargetCore._MAX_EXACT_SAMPLE_PRECISION_BITS || throw(
        ArgumentError("exactification recognition ladder exceeds Core's precision limit"),
    )
    return NemoExactBackend(recognition_options)
end

function _checkpoint_provider(provider::ExactSampleProvider)
    checkpoint = GeoTargetCore.exactification_checkpoint(provider)
    checkpoint.ready || throw(_ExactSampleAbort(checkpoint.failure, checkpoint.detail))
    return nothing
end

function _recognition_options_document(options::RecognitionOptions)
    return Dict{String,Any}(
        "base_precision_bits" => options.base_precision_bits,
        "confirmation_extra_bits" => options.confirmation_extra_bits,
        "degree_limits" => collect(options.degree_limits),
        "height_bits" => collect(options.height_bits),
        "pslq" => "owned_pslq_v1",
        "rational_reconstruction" => "bounded_continued_fraction_v1",
    )
end

function _exact_backend_source_identity()
    names = (
        "GeoTargetExact.jl",
        "algebraic_real.jl",
        "backend.jl",
        "c3a_replay.jl",
        "certificates.jl",
        "exact_artifacts.jl",
        "pslq.jl",
        "recognition.jl",
    )
    document = join(
        (string(name, ':', content_hash(read(joinpath(@__DIR__, name), String))) for name in names),
        '\n',
    )
    return content_hash(document)
end

function _exact_backend_manifest_identity()
    manifest = normpath(joinpath(@__DIR__, "..", "Manifest.toml"))
    return content_hash(read(manifest, String))
end

function GeoTargetCore.exact_backend_descriptor(backend::NemoExactBackend)
    policy = GeoTargetCore.canonical_json(_recognition_options_document(
        backend.recognition_options,
    ))
    environment = GeoTargetCore.canonical_json(Dict{String,Any}(
        "geotarget_exact" => string(Base.pkgversion(@__MODULE__)),
        "implementation" => string(_exact_backend_source_identity()),
        "julia" => string(VERSION),
        "manifest" => string(_exact_backend_manifest_identity()),
        "nemo" => string(Base.pkgversion(Nemo)),
        "qqbar" => "Nemo.QQBar",
    ))
    return ExactBackendDescriptor(
        "geotarget-nemo-exact",
        v"0.1.0",
        "dual_precision_pslq_then_original_graph_c3a_replay";
        configuration_certificate_schemes=(_C3A_CONFIGURATION_SCHEME,),
        target_certificate_schemes=(_C3A_TARGET_SCHEME,),
        policy_identity=content_hash(policy),
        environment_identity=content_hash(environment),
    )
end

function _sample_coordinate_provider(provider::ExactSampleProvider, index::Int)
    return bits -> begin
        result = GeoTargetCore.exact_sample(provider, bits; pass=:reference)
        result.accepted || throw(_ExactSampleAbort(result.failure, result.detail))
        sample = result.sample
        sample !== nothing || throw(
            _ExactSampleAbort(EXACT_SAMPLE_INTERNAL_ERROR, "accepted sample lacks payload"),
        )
        index <= length(sample.coordinates) || throw(
            _ExactSampleAbort(EXACT_SAMPLE_INTERNAL_ERROR, "sample coordinate count drifted"),
        )
        value = sample.coordinates[index]
        value isa BigFloat || throw(
            _ExactSampleAbort(
                EXACT_SAMPLE_PRECISION_DOWNGRADE,
                "recognition coordinate $index is not BigFloat",
            ),
        )
        isfinite(value) && precision(value) >= bits || throw(
            _ExactSampleAbort(
                EXACT_SAMPLE_PRECISION_DOWNGRADE,
                "recognition coordinate $index has insufficient precision",
            ),
        )
        return deepcopy(value)
    end
end

function _sample_failure_to_exactification(failure::ExactSampleFailure)
    failure == EXACT_SAMPLE_CANCELLED && return EXACTIFICATION_CANCELLED
    failure == EXACT_SAMPLE_DEADLINE_REACHED && return EXACTIFICATION_DEADLINE_REACHED
    failure == EXACT_SAMPLE_ORACLE_BUDGET_EXHAUSTED &&
        return EXACTIFICATION_ORACLE_BUDGET_EXHAUSTED
    return EXACTIFICATION_SAMPLE_FAILED
end

function _backend_failure(failure::ExactificationFailure, detail)
    return ExactBackendOutcome(nothing, failure, String(detail); reported_oracle_work=0)
end

function _recognized_configuration(
    backend::NemoExactBackend,
    compiled::GeoTargetCore.CompiledProblem,
    provider::ExactSampleProvider,
)
    candidates = RecognitionCandidate[]
    for index in eachindex(compiled.problem.variables)
        _checkpoint_provider(provider)
        candidate = recognize_algebraic(
            _sample_coordinate_provider(provider, index);
            options=backend.recognition_options,
            checkpoint=() -> _checkpoint_provider(provider),
        )
        candidate === nothing && return nothing,
            "free variable $index has no stable bounded-degree/height algebraic identity"
        reconstruct_descriptor(
            candidate.descriptor;
            checkpoint=() -> _checkpoint_provider(provider),
        ) === nothing && return nothing,
            "free variable $index recognition descriptor cannot be reconstructed"
        push!(candidates, candidate)
        _checkpoint_provider(provider)
    end
    return Tuple(candidates), ""
end

function GeoTargetCore.exactify_candidate(
    backend::NemoExactBackend,
    compiled::GeoTargetCore.CompiledProblem,
    validation::CandidateValidationResult,
    provider::ExactSampleProvider,
)
    supports(GeoTargetCore.capabilities(compiled), C3A) || return _backend_failure(
        EXACTIFICATION_CAPABILITY_MISSING,
        "all original graph operations require explicit C3A algebraic_prover callbacks",
    )

    candidates = nothing
    recognition_detail = ""
    try
        candidates, recognition_detail = _recognized_configuration(backend, compiled, provider)
    catch error
        error isa InterruptException && rethrow()
        if error isa _ExactSampleAbort
            return _backend_failure(
                _sample_failure_to_exactification(error.failure),
                error.detail,
            )
        end
        return _backend_failure(
            EXACTIFICATION_RECOGNITION_FAILED,
            "algebraic recognition failed: $(sprint(showerror, error))",
        )
    end
    candidates === nothing && return _backend_failure(
        EXACTIFICATION_RECOGNITION_FAILED,
        recognition_detail,
    )
    coordinates = Tuple(
        reconstruct_descriptor(
            candidate.descriptor;
            checkpoint=() -> _checkpoint_provider(provider),
        )::AlgebraicReal for candidate in candidates
    )
    _checkpoint_provider(provider)
    replay = replay_c3a(
        compiled,
        coordinates;
        expected_branches=validation.canonical_observation.branches,
        checkpoint=() -> _checkpoint_provider(provider),
    )
    replay isa C3AReplayResult && replay.accepted || return _backend_failure(
        EXACTIFICATION_REPLAY_FAILED,
        replay isa C3AReplayResult ? replay.detail : "C3A replay returned an invalid result",
    )
    answer = try
        _checkpoint_provider(provider)
        reference_samples = exact_sample_provider_samples(provider; pass=:reference)
        isempty(reference_samples) && error("exactification has no reference approximation")
        _build_c3a_exact_answer(
            compiled,
            validation,
            candidates,
            replay.evidence;
            checkpoint=() -> _checkpoint_provider(provider),
            approximation=last(reference_samples).target,
        )
    catch error
        error isa InterruptException && rethrow()
        return _backend_failure(
            EXACTIFICATION_CERTIFICATE_FAILED,
            "exact certificate construction failed: $(sprint(showerror, error))",
        )
    end
    verification = try
        _checkpoint_provider(provider)
        verify_c3a_exact_answer(
            compiled,
            answer;
            checkpoint=() -> _checkpoint_provider(provider),
        )
    catch error
        error isa InterruptException && rethrow()
        return _backend_failure(
            EXACTIFICATION_CERTIFICATE_FAILED,
            "self-verification raised an exception: $(sprint(showerror, error))",
        )
    end
    verification.accepted || return _backend_failure(
        EXACTIFICATION_CERTIFICATE_FAILED,
        "self-verification failed: $(verification.detail)",
    )
    return ExactBackendOutcome(
        answer,
        EXACTIFICATION_NONE,
        "";
        reported_oracle_work=0,
    )
end

function _core_verification_failure(failure::C3AVerificationFailure)
    failure == C3A_VERIFY_NONE && return EXACT_VERIFICATION_NONE
    failure == C3A_VERIFY_UNSUPPORTED_SCHEME &&
        return EXACT_VERIFICATION_UNSUPPORTED_SCHEME
    failure == C3A_VERIFY_ARTIFACT_INVALID && return EXACT_VERIFICATION_ARTIFACT_INVALID
    failure == C3A_VERIFY_PROBLEM_MISMATCH && return EXACT_VERIFICATION_PROBLEM_MISMATCH
    failure == C3A_VERIFY_TARGET_MISMATCH && return EXACT_VERIFICATION_TARGET_MISMATCH
    return EXACT_VERIFICATION_CONFIGURATION_MISMATCH
end

function _sample_consistency_failure(
    compiled::GeoTargetCore.CompiledProblem,
    provider::ExactSampleProvider,
    answer::ExactAnswer,
    evidence::C3AReplayEvidence,
)
    samples = exact_sample_provider_samples(provider; pass=:reference)
    length(evidence.coordinates) == length(compiled.variables) || return (
        EXACT_VERIFICATION_CONFIGURATION_MISMATCH,
        "exact artifact coordinate count differs from the compiled problem",
    )
    for sample in samples
        _checkpoint_provider(provider)
        bits = sample.precision_bits
        coordinate_error, target_error, approximation_error = setprecision(BigFloat, bits) do
            exact_coordinates = BigFloat[
                _root_approximation(coordinate.value, bits) for
                coordinate in evidence.coordinates
            ]
            exact_normalized = BigFloat[
                (exact_coordinates[index] - BigFloat(variable.spec.origin)) /
                BigFloat(variable.spec.scale) for
                (index, variable) in enumerate(compiled.variables)
            ]
            sample_normalized = BigFloat[
                (BigFloat(sample.coordinates[index]) - BigFloat(variable.spec.origin)) /
                BigFloat(variable.spec.scale) for
                (index, variable) in enumerate(compiled.variables)
            ]
            coordinate_disagreement = maximum(
                abs,
                exact_normalized - sample_normalized;
                init=BigFloat(0),
            )
            exact_target = _root_approximation(evidence.target.value, bits)
            target_scale = max(one(BigFloat), abs(exact_target), abs(sample.target))
            target_disagreement = abs(exact_target - sample.target) / target_scale
            approximation = try
                answer.approximation isa BigFloat ? BigFloat(answer.approximation) :
                parse(BigFloat, string(answer.approximation))
            catch
                BigFloat(Inf)
            end
            approximation_disagreement = abs(exact_target - approximation) / target_scale
            coordinate_disagreement, target_disagreement, approximation_disagreement
        end
        coordinate_error <= sample.gates.correction_tolerance || return (
            EXACT_VERIFICATION_CONFIGURATION_MISMATCH,
            "exact artifact coordinates disagree with the $(bits)-bit reference sample",
        )
        target_error <= sample.gates.target_tolerance || return (
            EXACT_VERIFICATION_TARGET_MISMATCH,
            "exact artifact target disagrees with the $(bits)-bit reference sample",
        )
        approximation_error <= sample.gates.target_tolerance || return (
            EXACT_VERIFICATION_TARGET_MISMATCH,
            "exact answer approximation disagrees with the $(bits)-bit reference sample",
        )
    end
    return nothing
end

function GeoTargetCore.verify_exactified_answer(
    ::NemoExactBackend,
    compiled::GeoTargetCore.CompiledProblem,
    answer::ExactAnswer,
    provider::ExactSampleProvider,
)
    verification = verify_c3a_exact_answer(
        compiled,
        answer;
        checkpoint=() -> _checkpoint_provider(provider),
    )
    if verification.accepted
        evidence = _reconstruct_verified_c3a_evidence(
            compiled,
            answer;
            checkpoint=() -> _checkpoint_provider(provider),
        )
        evidence === nothing && return ExactVerificationResult(
            false,
            EXACT_VERIFICATION_ARTIFACT_INVALID,
            "verified C3A artifacts could not be reconstructed for sample comparison",
        )
        consistency = _sample_consistency_failure(compiled, provider, answer, evidence)
        consistency === nothing || return ExactVerificationResult(
            false,
            first(consistency),
            last(consistency),
        )
    end
    failure = _core_verification_failure(verification.failure)
    return ExactVerificationResult(
        verification.accepted,
        failure,
        verification.detail,
    )
end
