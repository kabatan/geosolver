struct NemoExactBackend <: GeoTargetCore.AbstractExactBackend
    recognition_options::RecognitionOptions
end

NemoExactBackend(; recognition_options::RecognitionOptions=RecognitionOptions()) =
    NemoExactBackend(recognition_options)

struct _ExactSampleAbort <: Exception
    failure::ExactSampleFailure
    detail::String
end

Base.showerror(io::IO, error::_ExactSampleAbort) =
    print(io, "exact sample ", error.failure, ": ", error.detail)

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

function GeoTargetCore.exact_backend_descriptor(backend::NemoExactBackend)
    policy = GeoTargetCore.canonical_json(_recognition_options_document(
        backend.recognition_options,
    ))
    environment = GeoTargetCore.canonical_json(Dict{String,Any}(
        "julia" => string(VERSION),
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
        candidate = recognize_algebraic(
            _sample_coordinate_provider(provider, index);
            options=backend.recognition_options,
        )
        candidate === nothing && return nothing,
            "free variable $index has no stable bounded-degree/height algebraic identity"
        reconstruct_descriptor(candidate.descriptor) === nothing && return nothing,
            "free variable $index recognition descriptor cannot be reconstructed"
        push!(candidates, candidate)
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
        reconstruct_descriptor(candidate.descriptor)::AlgebraicReal for candidate in candidates
    )
    replay = replay_c3a(
        compiled,
        coordinates;
        expected_branches=validation.canonical_observation.branches,
    )
    replay isa C3AReplayResult && replay.accepted || return _backend_failure(
        EXACTIFICATION_REPLAY_FAILED,
        replay isa C3AReplayResult ? replay.detail : "C3A replay returned an invalid result",
    )
    answer = try
        _build_c3a_exact_answer(compiled, validation, candidates, replay.evidence)
    catch error
        error isa InterruptException && rethrow()
        return _backend_failure(
            EXACTIFICATION_CERTIFICATE_FAILED,
            "exact certificate construction failed: $(sprint(showerror, error))",
        )
    end
    verification = try
        verify_c3a_exact_answer(compiled, answer)
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
