const CHECKPOINT_WIRE_VERSION = "geotarget.checkpoint/v1"

struct SolveCheckpointArtifact
    snapshot::CheckpointSnapshot
    target_image_status::TargetImageStatus
    content::ContentHash
end

const _CHECKPOINT_INTEGER_TYPES = (
    ("Int8", Int8),
    ("UInt8", UInt8),
    ("Int16", Int16),
    ("UInt16", UInt16),
    ("Int32", Int32),
    ("UInt32", UInt32),
    ("Int64", Int64),
    ("UInt64", UInt64),
    ("Int128", Int128),
    ("UInt128", UInt128),
    ("BigInt", BigInt),
)

const _CHECKPOINT_LANE_FROM_WIRE = Dict(
    "iid" => LANE_IID,
    "heuristic" => LANE_HEURISTIC,
    "shell" => LANE_SHELL,
    "pending" => LANE_PENDING,
    "refinement" => LANE_REFINEMENT,
)
const _CHECKPOINT_LANE_TO_WIRE =
    Dict(value => key for (key, value) in _CHECKPOINT_LANE_FROM_WIRE)

const _CHECKPOINT_LOOP_FROM_WIRE = Dict(
    "running" => LOOP_RUNNING,
    "deadline_reached" => LOOP_DEADLINE_REACHED,
    "cancelled" => LOOP_CANCELLED,
    "budget_exhausted" => LOOP_BUDGET_EXHAUSTED,
    "paused" => LOOP_PAUSED,
    "callback_error" => LOOP_CALLBACK_ERROR,
    "protocol_error" => LOOP_PROTOCOL_ERROR,
)
const _CHECKPOINT_LOOP_TO_WIRE =
    Dict(value => key for (key, value) in _CHECKPOINT_LOOP_FROM_WIRE)

const _CHECKPOINT_EVENT_FROM_WIRE = Dict(
    "scheduled" => EVENT_SCHEDULED,
    "proposed" => EVENT_PROPOSED,
    "observed" => EVENT_OBSERVED,
    "budget_charged" => EVENT_BUDGET_CHARGED,
    "status" => EVENT_STATUS,
    "callback_failed" => EVENT_CALLBACK_FAILED,
    "protocol_failed" => EVENT_PROTOCOL_FAILED,
)
const _CHECKPOINT_EVENT_TO_WIRE =
    Dict(value => key for (key, value) in _CHECKPOINT_EVENT_FROM_WIRE)

function _checkpoint_integer_type_name(integer_type::Type)
    for (name, candidate) in _CHECKPOINT_INTEGER_TYPES
        integer_type === candidate && return name
    end
    _protocol_error("checkpoint", "unsupported integer type $integer_type")
end

function _checkpoint_integer_type(name, path)
    text = _string(name, path)
    for (candidate_name, integer_type) in _CHECKPOINT_INTEGER_TYPES
        text == candidate_name && return integer_type
    end
    _protocol_error(path, "unsupported integer type $(repr(text))")
end

_checkpoint_hex(value::Unsigned, width::Int) =
    lpad(string(value; base = 16), width, '0')

function _checkpoint_real_document(value::Real, path)
    value isa Bool && _protocol_error(path, "Bool is not a checkpoint real")
    if value isa Integer
        return Dict{String,Any}(
            "kind" => "integer",
            "type" => _checkpoint_integer_type_name(typeof(value)),
            "decimal" => string(value),
        )
    elseif value isa Float16
        return Dict{String,Any}(
            "kind" => "binary_float",
            "type" => "Float16",
            "bits" => _checkpoint_hex(reinterpret(UInt16, value), 4),
        )
    elseif value isa Float32
        return Dict{String,Any}(
            "kind" => "binary_float",
            "type" => "Float32",
            "bits" => _checkpoint_hex(reinterpret(UInt32, value), 8),
        )
    elseif value isa Float64
        return Dict{String,Any}(
            "kind" => "binary_float",
            "type" => "Float64",
            "bits" => _checkpoint_hex(reinterpret(UInt64, value), 16),
        )
    elseif value isa BigFloat
        isfinite(value) || _protocol_error(path, "BigFloat checkpoint values must be finite")
        return Dict{String,Any}(
            "kind" => "bigfloat",
            "precision_bits" => precision(value),
            "decimal" => string(value),
        )
    end
    _protocol_error(path, "unsupported checkpoint real type $(typeof(value))")
end

function _checkpoint_integer_decimal(raw, path)
    text = _string(raw, path)
    occursin(r"^(?:0|-[1-9][0-9]*|[1-9][0-9]*)$", text) ||
        _protocol_error(path, "must be a canonical integer decimal")
    return text
end

function _decode_checkpoint_real(raw, path)
    raw isa Dict{String,Any} || _protocol_error(path, "must be a typed real object")
    kind = _string(get(raw, "kind", nothing), string(path, ".kind"))
    if kind == "integer"
        object = _object(raw, ("kind", "type", "decimal"); path)
        integer_type = _checkpoint_integer_type(object["type"], string(path, ".type"))
        decimal = _checkpoint_integer_decimal(object["decimal"], string(path, ".decimal"))
        return _construct(path, () -> parse(integer_type, decimal))
    elseif kind == "binary_float"
        object = _object(raw, ("kind", "type", "bits"); path)
        type_name = _string(object["type"], string(path, ".type"))
        float_type, unsigned_type, width = if type_name == "Float16"
            (Float16, UInt16, 4)
        elseif type_name == "Float32"
            (Float32, UInt32, 8)
        elseif type_name == "Float64"
            (Float64, UInt64, 16)
        else
            _protocol_error(string(path, ".type"), "unknown binary float type")
        end
        bits = _string(object["bits"], string(path, ".bits"))
        occursin(Regex("^[0-9a-f]{$width}\$"), bits) ||
            _protocol_error(string(path, ".bits"), "must be fixed-width lowercase hexadecimal")
        material = parse(unsigned_type, bits; base = 16)
        return reinterpret(float_type, material)
    elseif kind == "bigfloat"
        object = _object(raw, ("kind", "precision_bits", "decimal"); path)
        precision_bits = _integer(
            object["precision_bits"],
            string(path, ".precision_bits");
            minimum = 2,
        )
        decimal = _string(object["decimal"], string(path, ".decimal"))
        ncodeunits(decimal) <= 1_000_000 ||
            _protocol_error(string(path, ".decimal"), "BigFloat decimal is too long")
        value = _construct(path, () -> setprecision(BigFloat, precision_bits) do
            parse(BigFloat, decimal)
        end)
        isfinite(value) || _protocol_error(path, "BigFloat checkpoint values must be finite")
        string(value) == decimal ||
            _protocol_error(string(path, ".decimal"), "BigFloat decimal is not canonical")
        return value
    end
    _protocol_error(string(path, ".kind"), "unknown typed real kind")
end

function _checkpoint_uint64_document(value::UInt64)
    return value <= _JCS_SAFE_INTEGER ? Int64(value) : string(value)
end

function _decode_checkpoint_uint64(raw, path; positive::Bool = false)
    value = _decode_solve_seed(raw, path)
    positive && value == 0 && _protocol_error(path, "must be positive")
    canonical_json_bytes(_checkpoint_uint64_document(value)) == canonical_json_bytes(raw) ||
        _protocol_error(path, "UInt64 value is not in canonical number/string form")
    return value
end

function _checkpoint_value_document(value, path)
    if value === nothing
        return Dict{String,Any}("kind" => "nothing")
    elseif value isa Bool
        return Dict{String,Any}("kind" => "bool", "value" => value)
    elseif value isa String
        return Dict{String,Any}("kind" => "string", "value" => value)
    elseif value isa Symbol
        return Dict{String,Any}("kind" => "symbol", "value" => String(value))
    elseif value isa VersionNumber
        return Dict{String,Any}("kind" => "version", "value" => string(value))
    elseif value isa Real
        return Dict{String,Any}(
            "kind" => "real",
            "value" => _checkpoint_real_document(value, string(path, ".value")),
        )
    end
    _protocol_error(path, "unsupported typed checkpoint value $(typeof(value))")
end

function _decode_checkpoint_value(raw, path)
    raw isa Dict{String,Any} || _protocol_error(path, "must be a typed value object")
    kind = _string(get(raw, "kind", nothing), string(path, ".kind"))
    if kind == "nothing"
        _object(raw, ("kind",); path)
        return nothing
    elseif kind == "bool"
        object = _object(raw, ("kind", "value"); path)
        return _bool(object["value"], string(path, ".value"))
    elseif kind == "string"
        object = _object(raw, ("kind", "value"); path)
        return _string(object["value"], string(path, ".value"))
    elseif kind == "symbol"
        object = _object(raw, ("kind", "value"); path)
        text = _string(object["value"], string(path, ".value"))
        occursin(r"^[A-Za-z_][A-Za-z0-9_.-]*$", text) ||
            _protocol_error(string(path, ".value"), "symbol is not canonical")
        return Symbol(text)
    elseif kind == "version"
        object = _object(raw, ("kind", "value"); path)
        return _canonical_version(object["value"], string(path, ".value"))
    elseif kind == "real"
        object = _object(raw, ("kind", "value"); path)
        return _decode_checkpoint_real(object["value"], string(path, ".value"))
    end
    _protocol_error(string(path, ".kind"), "unknown typed value kind")
end

function _checkpoint_metadata_document(metadata::Tuple, path)
    document = Any[]
    for (index, entry) in enumerate(metadata)
        entry isa Pair && first(entry) isa Symbol ||
            _protocol_error(path, "proposal metadata entries must be Symbol pairs")
        push!(
            document,
            Dict{String,Any}(
                "key" => String(first(entry)),
                "value" => _checkpoint_value_document(
                    last(entry),
                    string(path, ".", index - 1, ".value"),
                ),
            ),
        )
    end
    return document
end

function _decode_checkpoint_metadata(raw, path)
    result = Pair[]
    keys_seen = String[]
    for (index, value) in enumerate(_array(raw, path))
        item_path = string(path, ".", index - 1)
        object = _object(value, ("key", "value"); path = item_path)
        key = _string(object["key"], string(item_path, ".key"))
        occursin(r"^[A-Za-z_][A-Za-z0-9_.-]*$", key) ||
            _protocol_error(string(item_path, ".key"), "metadata key is not canonical")
        push!(keys_seen, key)
        push!(
            result,
            Symbol(key) => _decode_checkpoint_value(
                object["value"],
                string(item_path, ".value"),
            ),
        )
    end
    allunique(keys_seen) || _protocol_error(path, "metadata keys must be unique")
    return Tuple(result)
end

function _checkpoint_lane(raw, path)
    text = _string(raw, path)
    value = get(_CHECKPOINT_LANE_FROM_WIRE, text, nothing)
    value === nothing && _protocol_error(path, "unknown search lane")
    return value
end

function _checkpoint_decision_document(decision::ScheduleDecision)
    return Dict{String,Any}(
        "lane" => _CHECKPOINT_LANE_TO_WIRE[decision.lane],
        "task_id" => _checkpoint_uint64_document(decision.task_id),
        "shell" => decision.shell,
        "source_configuration" => decision.source_configuration === nothing ?
                                  nothing :
                                  _checkpoint_uint64_document(decision.source_configuration),
    )
end

function _decode_checkpoint_decision(raw, path)
    object = _object(raw, ("lane", "task_id", "shell", "source_configuration"); path)
    shell = object["shell"] === nothing ? nothing :
            _integer(object["shell"], string(path, ".shell"); minimum = 0)
    source = object["source_configuration"] === nothing ? nothing :
             _decode_checkpoint_uint64(
        object["source_configuration"],
        string(path, ".source_configuration");
        positive = true,
    )
    return _construct(path, () -> ScheduleDecision(
        _checkpoint_lane(object["lane"], string(path, ".lane")),
        _decode_checkpoint_uint64(object["task_id"], string(path, ".task_id"));
        shell,
        source_configuration = source,
    ))
end

function _checkpoint_proposal_document(proposal::Proposal, path)
    return Dict{String,Any}(
        "task_id" => _checkpoint_uint64_document(proposal.task_id),
        "configuration_id" => _checkpoint_uint64_document(proposal.configuration_id),
        "lane" => _CHECKPOINT_LANE_TO_WIRE[proposal.lane],
        "coordinates" => Any[
            _checkpoint_real_document(value, string(path, ".coordinates")) for
            value in proposal.coordinates
        ],
        "shell" => proposal.shell,
        "source_configuration" => proposal.source_configuration === nothing ?
                                  nothing :
                                  _checkpoint_uint64_document(proposal.source_configuration),
        "metadata" => _checkpoint_metadata_document(proposal.metadata, string(path, ".metadata")),
    )
end

function _decode_checkpoint_proposal(raw, path)
    object = _object(
        raw,
        (
            "task_id",
            "configuration_id",
            "lane",
            "coordinates",
            "shell",
            "source_configuration",
            "metadata",
        );
        path,
    )
    coordinates = Tuple(
        _decode_checkpoint_real(value, string(path, ".coordinates.", index - 1)) for
        (index, value) in enumerate(_array(object["coordinates"], string(path, ".coordinates")))
    )
    shell = object["shell"] === nothing ? nothing :
            _integer(object["shell"], string(path, ".shell"); minimum = 0)
    source = object["source_configuration"] === nothing ? nothing :
             _decode_checkpoint_uint64(
        object["source_configuration"],
        string(path, ".source_configuration");
        positive = true,
    )
    return _construct(path, () -> Proposal(
        _decode_checkpoint_uint64(object["task_id"], string(path, ".task_id"); positive = true),
        _decode_checkpoint_uint64(
            object["configuration_id"],
            string(path, ".configuration_id");
            positive = true,
        ),
        _checkpoint_lane(object["lane"], string(path, ".lane")),
        coordinates;
        shell,
        source_configuration = source,
        metadata = _decode_checkpoint_metadata(object["metadata"], string(path, ".metadata")),
    ))
end

function _checkpoint_target_document(target::TargetEnclosure, path)
    return Dict{String,Any}(
        "lower" => _checkpoint_real_document(target.lower, string(path, ".lower")),
        "upper" => _checkpoint_real_document(target.upper, string(path, ".upper")),
    )
end

function _decode_checkpoint_target(raw, path)
    object = _object(raw, ("lower", "upper"); path)
    return _construct(path, () -> TargetEnclosure(
        _decode_checkpoint_real(object["lower"], string(path, ".lower")),
        _decode_checkpoint_real(object["upper"], string(path, ".upper")),
    ))
end

function _checkpoint_numeric_enclosure_document(value::NumericEnclosure, path)
    return Dict{String,Any}(
        "lower" => _checkpoint_real_document(value.lower, string(path, ".lower")),
        "upper" => _checkpoint_real_document(value.upper, string(path, ".upper")),
    )
end

function _decode_checkpoint_numeric_enclosure(raw, path)
    object = _object(raw, ("lower", "upper"); path)
    return _construct(path, () -> NumericEnclosure(
        _decode_checkpoint_real(object["lower"], string(path, ".lower")),
        _decode_checkpoint_real(object["upper"], string(path, ".upper")),
    ))
end

function _checkpoint_provisional_document(answer::ProvisionalAnswer, path)
    return Dict{String,Any}(
        "target" => _checkpoint_numeric_enclosure_document(
            answer.target,
            string(path, ".target"),
        ),
        "canonical_residual_bound" => _checkpoint_real_document(
            answer.canonical_residual_bound,
            string(path, ".canonical_residual_bound"),
        ),
        "branch_signature" => _branch_document(answer.branch_signature),
        "guard_enclosures" => Any[
            Dict{String,Any}(
                "node" => string(guard.node),
                "enclosure" => _checkpoint_numeric_enclosure_document(
                    guard.enclosure,
                    string(path, ".guard_enclosures.", index - 1, ".enclosure"),
                ),
                "strict" => guard.strict,
            ) for (index, guard) in enumerate(answer.guard_enclosures)
        ],
        "validation" => _validation_document(answer.validation),
        "exact_failure" => _EXACT_FAILURE_TO_WIRE[answer.exact_failure],
        "exact_failure_detail" => answer.exact_failure_detail,
    )
end

function _decode_checkpoint_provisional(raw, path)
    object = _object(
        raw,
        (
            "target",
            "canonical_residual_bound",
            "branch_signature",
            "guard_enclosures",
            "validation",
            "exact_failure",
            "exact_failure_detail",
        );
        path,
    )
    failure_text = _string(object["exact_failure"], string(path, ".exact_failure"))
    failure = get(_EXACT_FAILURE_FROM_WIRE, failure_text, nothing)
    failure === nothing &&
        _protocol_error(string(path, ".exact_failure"), "unknown exact-promotion failure")
    guards = GuardEnclosure[]
    for (index, raw_guard) in enumerate(
        _array(object["guard_enclosures"], string(path, ".guard_enclosures")),
    )
        guard_path = string(path, ".guard_enclosures.", index - 1)
        guard = _object(raw_guard, ("node", "enclosure", "strict"); path = guard_path)
        push!(guards, _construct(guard_path, () -> GuardEnclosure(
            _canonical_id(NodeId, guard["node"], string(guard_path, ".node")),
            _decode_checkpoint_numeric_enclosure(
                guard["enclosure"],
                string(guard_path, ".enclosure"),
            ),
            _bool(guard["strict"], string(guard_path, ".strict")),
        )))
    end
    return _construct(path, () -> ProvisionalAnswer(
        _decode_checkpoint_numeric_enclosure(object["target"], string(path, ".target")),
        _decode_checkpoint_real(
            object["canonical_residual_bound"],
            string(path, ".canonical_residual_bound"),
        ),
        _decode_branch_signature(
            object["branch_signature"],
            string(path, ".branch_signature"),
        ),
        _decode_validation(object["validation"], string(path, ".validation"));
        guard_enclosures = Tuple(guards),
        exact_failure = failure,
        exact_failure_detail = _string(
            object["exact_failure_detail"],
            string(path, ".exact_failure_detail"),
        ),
    ))
end

function _checkpoint_exact_document(answer::ExactAnswer, path)
    return Dict{String,Any}(
        "identity" => _identity_document(answer.identity),
        "approximation" => _checkpoint_real_document(
            answer.approximation,
            string(path, ".approximation"),
        ),
        "branch_signature" => _branch_document(answer.branch_signature),
        "configuration_certificate" =>
            _configuration_certificate_document(answer.configuration_certificate),
        "target_certificate" => _target_certificate_document(answer.target_certificate),
    )
end

function _decode_checkpoint_exact(raw, path)
    object = _object(
        raw,
        (
            "identity",
            "approximation",
            "branch_signature",
            "configuration_certificate",
            "target_certificate",
        );
        path,
    )
    return _construct(path, () -> ExactAnswer(
        _decode_identity(object["identity"], string(path, ".identity")),
        _decode_checkpoint_real(object["approximation"], string(path, ".approximation")),
        _decode_branch_signature(
            object["branch_signature"],
            string(path, ".branch_signature"),
        ),
        _decode_configuration_certificate(
            object["configuration_certificate"],
            string(path, ".configuration_certificate"),
        ),
        _decode_target_certificate(
            object["target_certificate"],
            string(path, ".target_certificate"),
        ),
    ))
end

function _checkpoint_payload_document(payload, path)
    payload === nothing && return nothing
    if payload isa ProvisionalAnswer
        return Dict{String,Any}(
            "kind" => "provisional_answer",
            "value" => _checkpoint_provisional_document(payload, string(path, ".value")),
        )
    elseif payload isa ExactAnswer
        return Dict{String,Any}(
            "kind" => "exact_answer",
            "value" => _checkpoint_exact_document(payload, string(path, ".value")),
        )
    end
    _protocol_error(path, "unsupported verified payload type $(typeof(payload))")
end

function _decode_checkpoint_payload(raw, path)
    raw === nothing && return nothing
    object = _object(raw, ("kind", "value"); path)
    kind = _string(object["kind"], string(path, ".kind"))
    kind == "provisional_answer" &&
        return _decode_checkpoint_provisional(object["value"], string(path, ".value"))
    kind == "exact_answer" &&
        return _decode_checkpoint_exact(object["value"], string(path, ".value"))
    _protocol_error(string(path, ".kind"), "unknown verified payload kind")
end

function _checkpoint_observation_document(observation::Observation, path)
    return Dict{String,Any}(
        "task_id" => _checkpoint_uint64_document(observation.task_id),
        "configuration_id" => _checkpoint_uint64_document(observation.configuration_id),
        "canonical_near_feasible" => observation.canonical_near_feasible,
        "canonical_valid" => observation.canonical_valid,
        "target" => observation.target === nothing ? nothing :
                    _checkpoint_target_document(observation.target, string(path, ".target")),
        "target_identity" => observation.target_identity,
        "branch_signature" => _branch_document(observation.branch_signature),
        "verified" => observation.verified,
        "verified_payload" => _checkpoint_payload_document(
            observation.verified_payload,
            string(path, ".verified_payload"),
        ),
        "needs_refinement" => observation.needs_refinement,
        "residual_score" => _checkpoint_real_document(
            observation.residual_score,
            string(path, ".residual_score"),
        ),
        "oracle_work" => observation.oracle_work,
        "endpoint" => observation.endpoint === nothing ? nothing : Any[
            _checkpoint_real_document(value, string(path, ".endpoint")) for
            value in observation.endpoint
        ],
        "diagnostic" => observation.diagnostic,
    )
end

function _decode_checkpoint_observation(raw, path)
    object = _object(
        raw,
        (
            "task_id",
            "configuration_id",
            "canonical_near_feasible",
            "canonical_valid",
            "target",
            "target_identity",
            "branch_signature",
            "verified",
            "verified_payload",
            "needs_refinement",
            "residual_score",
            "oracle_work",
            "endpoint",
            "diagnostic",
        );
        path,
    )
    target = object["target"] === nothing ? nothing :
             _decode_checkpoint_target(object["target"], string(path, ".target"))
    identity = object["target_identity"] === nothing ? nothing :
               _string(object["target_identity"], string(path, ".target_identity"))
    endpoint = object["endpoint"] === nothing ? nothing : Tuple(
        _decode_checkpoint_real(value, string(path, ".endpoint.", index - 1)) for
        (index, value) in enumerate(_array(object["endpoint"], string(path, ".endpoint")))
    )
    diagnostic = object["diagnostic"] === nothing ? nothing :
                 _string(object["diagnostic"], string(path, ".diagnostic"))
    return _construct(path, () -> Observation(
        _decode_checkpoint_uint64(object["task_id"], string(path, ".task_id"); positive = true),
        _decode_checkpoint_uint64(
            object["configuration_id"],
            string(path, ".configuration_id");
            positive = true,
        );
        canonical_near_feasible = _bool(
            object["canonical_near_feasible"],
            string(path, ".canonical_near_feasible"),
        ),
        canonical_valid = _bool(object["canonical_valid"], string(path, ".canonical_valid")),
        target,
        target_identity = identity,
        branch_signature = _decode_branch_signature(
            object["branch_signature"],
            string(path, ".branch_signature"),
        ),
        verified = _bool(object["verified"], string(path, ".verified")),
        verified_payload = _decode_checkpoint_payload(
            object["verified_payload"],
            string(path, ".verified_payload"),
        ),
        needs_refinement = _bool(
            object["needs_refinement"],
            string(path, ".needs_refinement"),
        ),
        residual_score = _decode_checkpoint_real(
            object["residual_score"],
            string(path, ".residual_score"),
        ),
        oracle_work = _integer(object["oracle_work"], string(path, ".oracle_work"); minimum = 0),
        endpoint,
        diagnostic,
    ))
end

function _checkpoint_budget_limits_document(limits::BudgetLimits)
    return Dict{String,Any}(
        "proposals" => limits.proposals,
        "local_attempts" => limits.local_attempts,
        "refinements" => limits.refinements,
        "oracle_work" => limits.oracle_work,
    )
end

function _decode_checkpoint_optional_count(raw, path)
    raw === nothing && return nothing
    return _integer(raw, path; minimum = 0)
end

function _decode_checkpoint_budget_limits(raw, path)
    object = _object(
        raw,
        ("proposals", "local_attempts", "refinements", "oracle_work");
        path,
    )
    return _construct(path, () -> BudgetLimits(
        proposals = _decode_checkpoint_optional_count(
            object["proposals"],
            string(path, ".proposals"),
        ),
        local_attempts = _decode_checkpoint_optional_count(
            object["local_attempts"],
            string(path, ".local_attempts"),
        ),
        refinements = _decode_checkpoint_optional_count(
            object["refinements"],
            string(path, ".refinements"),
        ),
        oracle_work = _decode_checkpoint_optional_count(
            object["oracle_work"],
            string(path, ".oracle_work"),
        ),
    ))
end

function _checkpoint_budget_snapshot_document(snapshot::BudgetSnapshot)
    return Dict{String,Any}(
        "limits" => _checkpoint_budget_limits_document(snapshot.limits),
        "proposals" => snapshot.proposals,
        "local_attempts" => snapshot.local_attempts,
        "refinements" => snapshot.refinements,
        "oracle_work" => snapshot.oracle_work,
    )
end

function _decode_checkpoint_budget_snapshot(raw, path)
    object = _object(
        raw,
        ("limits", "proposals", "local_attempts", "refinements", "oracle_work");
        path,
    )
    snapshot = BudgetSnapshot(
        _decode_checkpoint_budget_limits(object["limits"], string(path, ".limits")),
        _integer(object["proposals"], string(path, ".proposals"); minimum = 0),
        _integer(object["local_attempts"], string(path, ".local_attempts"); minimum = 0),
        _integer(object["refinements"], string(path, ".refinements"); minimum = 0),
        _integer(object["oracle_work"], string(path, ".oracle_work"); minimum = 0),
    )
    counts = (
        snapshot.proposals,
        snapshot.local_attempts,
        snapshot.refinements,
        snapshot.oracle_work,
    )
    limits = (
        snapshot.limits.proposals,
        snapshot.limits.local_attempts,
        snapshot.limits.refinements,
        snapshot.limits.oracle_work,
    )
    all(pair -> last(pair) === nothing || first(pair) <= last(pair), zip(counts, limits)) ||
        _protocol_error(path, "budget counters exceed their limits")
    return snapshot
end

function _checkpoint_budget_charge_document(charge::BudgetCharge)
    return Dict{String,Any}(
        "proposals" => charge.proposals,
        "local_attempts" => charge.local_attempts,
        "refinements" => charge.refinements,
        "oracle_work" => charge.oracle_work,
    )
end

function _decode_checkpoint_budget_charge(raw, path)
    object = _object(
        raw,
        ("proposals", "local_attempts", "refinements", "oracle_work");
        path,
    )
    return _construct(path, () -> BudgetCharge(
        proposals = _integer(object["proposals"], string(path, ".proposals"); minimum = 0),
        local_attempts = _integer(
            object["local_attempts"],
            string(path, ".local_attempts");
            minimum = 0,
        ),
        refinements = _integer(
            object["refinements"],
            string(path, ".refinements");
            minimum = 0,
        ),
        oracle_work = _integer(
            object["oracle_work"],
            string(path, ".oracle_work");
            minimum = 0,
        ),
    ))
end

function _checkpoint_event_payload_document(event::EvidenceEvent, path)
    payload = event.payload
    if event.kind === EVENT_SCHEDULED
        payload isa ScheduleDecision ||
            _protocol_error(path, "scheduled event payload must be ScheduleDecision")
        return _checkpoint_decision_document(payload)
    elseif event.kind === EVENT_PROPOSED
        payload isa Proposal || _protocol_error(path, "proposed event payload must be Proposal")
        return _checkpoint_proposal_document(payload, path)
    elseif event.kind === EVENT_OBSERVED
        payload isa Observation ||
            _protocol_error(path, "observed event payload must be Observation")
        return _checkpoint_observation_document(payload, path)
    elseif event.kind === EVENT_BUDGET_CHARGED
        payload isa NamedTuple && keys(payload) == (:charge, :snapshot) ||
            _protocol_error(path, "budget event payload has the wrong typed fields")
        payload.charge isa BudgetCharge && payload.snapshot isa BudgetSnapshot ||
            _protocol_error(path, "budget event payload has the wrong field types")
        return Dict{String,Any}(
            "charge" => _checkpoint_budget_charge_document(payload.charge),
            "snapshot" => _checkpoint_budget_snapshot_document(payload.snapshot),
        )
    elseif event.kind === EVENT_STATUS
        payload isa NamedTuple && keys(payload) == (:status, :detail) ||
            _protocol_error(path, "status event payload has the wrong typed fields")
        payload.status isa SearchLoopStatus ||
            _protocol_error(path, "status event payload has the wrong status type")
        payload.detail === nothing || payload.detail isa String ||
            _protocol_error(path, "status event detail must be a string or null")
        return Dict{String,Any}(
            "status" => _CHECKPOINT_LOOP_TO_WIRE[payload.status],
            "detail" => payload.detail,
        )
    elseif event.kind in (EVENT_CALLBACK_FAILED, EVENT_PROTOCOL_FAILED)
        payload isa NamedTuple && keys(payload) == (:stage, :error_type, :message) ||
            _protocol_error(path, "failure event payload has the wrong typed fields")
        payload.stage isa Symbol && payload.error_type isa String && payload.message isa String ||
            _protocol_error(path, "failure event payload has the wrong field types")
        return Dict{String,Any}(
            "stage" => String(payload.stage),
            "error_type" => payload.error_type,
            "message" => payload.message,
        )
    end
    _protocol_error(path, "unsupported checkpoint event kind")
end

function _decode_checkpoint_loop_status(raw, path)
    text = _string(raw, path)
    status = get(_CHECKPOINT_LOOP_FROM_WIRE, text, nothing)
    status === nothing && _protocol_error(path, "unknown search-loop status")
    return status
end

function _decode_checkpoint_event_payload(kind::SearchEventKind, raw, path)
    if kind === EVENT_SCHEDULED
        return _decode_checkpoint_decision(raw, path)
    elseif kind === EVENT_PROPOSED
        return _decode_checkpoint_proposal(raw, path)
    elseif kind === EVENT_OBSERVED
        return _decode_checkpoint_observation(raw, path)
    elseif kind === EVENT_BUDGET_CHARGED
        object = _object(raw, ("charge", "snapshot"); path)
        return (
            charge = _decode_checkpoint_budget_charge(
                object["charge"],
                string(path, ".charge"),
            ),
            snapshot = _decode_checkpoint_budget_snapshot(
                object["snapshot"],
                string(path, ".snapshot"),
            ),
        )
    elseif kind === EVENT_STATUS
        object = _object(raw, ("status", "detail"); path)
        detail = object["detail"] === nothing ? nothing :
                 _string(object["detail"], string(path, ".detail"))
        return (
            status = _decode_checkpoint_loop_status(
                object["status"],
                string(path, ".status"),
            ),
            detail = detail,
        )
    elseif kind in (EVENT_CALLBACK_FAILED, EVENT_PROTOCOL_FAILED)
        object = _object(raw, ("stage", "error_type", "message"); path)
        stage = _string(object["stage"], string(path, ".stage"))
        occursin(r"^[A-Za-z_][A-Za-z0-9_.-]*$", stage) ||
            _protocol_error(string(path, ".stage"), "failure stage is not canonical")
        return (
            stage = Symbol(stage),
            error_type = _string(object["error_type"], string(path, ".error_type")),
            message = _string(object["message"], string(path, ".message")),
        )
    end
    _protocol_error(path, "unsupported checkpoint event kind")
end

function _checkpoint_event_document(event::EvidenceEvent, path)
    return Dict{String,Any}(
        "sequence" => event.sequence,
        "kind" => _CHECKPOINT_EVENT_TO_WIRE[event.kind],
        "payload" => _checkpoint_event_payload_document(event, string(path, ".payload")),
    )
end

function _decode_checkpoint_event(raw, path)
    object = _object(raw, ("sequence", "kind", "payload"); path)
    kind_text = _string(object["kind"], string(path, ".kind"))
    kind = get(_CHECKPOINT_EVENT_FROM_WIRE, kind_text, nothing)
    kind === nothing && _protocol_error(string(path, ".kind"), "unknown event kind")
    return EvidenceEvent(
        _integer(object["sequence"], string(path, ".sequence"); minimum = 1),
        kind,
        _decode_checkpoint_event_payload(kind, object["payload"], string(path, ".payload")),
    )
end

function _checkpoint_scheduler_document(snapshot::SchedulerSnapshot)
    return Dict{String,Any}(
        "served" => Any[snapshot.served...],
        "total_actions" => snapshot.total_actions,
        "next_task_id" => _checkpoint_uint64_document(snapshot.next_task_id),
        "shell_ticks" => snapshot.shell_ticks,
    )
end

function _decode_checkpoint_scheduler(raw, path)
    object = _object(raw, ("served", "total_actions", "next_task_id", "shell_ticks"); path)
    raw_served = _array(object["served"], string(path, ".served"))
    length(raw_served) == 5 || _protocol_error(string(path, ".served"), "must have five lanes")
    served = Tuple(
        _integer(value, string(path, ".served.", index - 1); minimum = 0) for
        (index, value) in enumerate(raw_served)
    )
    return SchedulerSnapshot(
        served,
        _integer(object["total_actions"], string(path, ".total_actions"); minimum = 0),
        _decode_checkpoint_uint64(
            object["next_task_id"],
            string(path, ".next_task_id");
            positive = true,
        ),
        _integer(object["shell_ticks"], string(path, ".shell_ticks"); minimum = 0),
    )
end

function _checkpoint_candidate_record_document(record::CandidateRecord, path)
    return Dict{String,Any}(
        "revision" => record.revision,
        "proposal" => _checkpoint_proposal_document(record.proposal, string(path, ".proposal")),
        "observation" => _checkpoint_observation_document(
            record.observation,
            string(path, ".observation"),
        ),
    )
end

function _decode_checkpoint_candidate_history(raw, path)
    store = CandidateStore()
    for (index, raw_record) in enumerate(_array(raw, path))
        record_path = string(path, ".", index - 1)
        object = _object(raw_record, ("revision", "proposal", "observation"); path = record_path)
        revision = _integer(object["revision"], string(record_path, ".revision"); minimum = 1)
        proposal = _decode_checkpoint_proposal(
            object["proposal"],
            string(record_path, ".proposal"),
        )
        observation = _decode_checkpoint_observation(
            object["observation"],
            string(record_path, ".observation"),
        )
        restored = _construct(record_path, () -> insert_candidate!(store, proposal, observation))
        restored.revision == revision ||
            _protocol_error(string(record_path, ".revision"), "candidate revision is inconsistent")
    end
    return candidate_snapshot(store)
end

function _checkpoint_workspace_document(snapshot::WorkspaceSnapshot)
    return Dict{String,Any}(
        "history" => Any[
            _checkpoint_candidate_record_document(
                record,
                string("state.workspace.history.", index - 1),
            ) for (index, record) in enumerate(snapshot.candidates.history)
        ],
        "scheduler" => _checkpoint_scheduler_document(snapshot.scheduler),
        "pending" => Any[
            _checkpoint_proposal_document(
                proposal,
                string("state.workspace.pending.", index - 1),
            ) for (index, proposal) in enumerate(snapshot.pending)
        ],
        "refinement_queue" => Any[
            _checkpoint_uint64_document(configuration) for
            configuration in snapshot.refinement_queue
        ],
        "adaptive_unbounded" => snapshot.adaptive_unbounded,
    )
end

function _decode_checkpoint_workspace(raw, path)
    object = _object(
        raw,
        ("history", "scheduler", "pending", "refinement_queue", "adaptive_unbounded");
        path,
    )
    candidates = _decode_checkpoint_candidate_history(
        object["history"],
        string(path, ".history"),
    )
    scheduler = _decode_checkpoint_scheduler(object["scheduler"], string(path, ".scheduler"))
    pending = Tuple(
        _decode_checkpoint_proposal(value, string(path, ".pending.", index - 1)) for
        (index, value) in enumerate(_array(object["pending"], string(path, ".pending")))
    )
    refinement_queue = Tuple(
        _decode_checkpoint_uint64(
            value,
            string(path, ".refinement_queue.", index - 1);
            positive = true,
        ) for (index, value) in enumerate(
            _array(object["refinement_queue"], string(path, ".refinement_queue")),
        )
    )
    seen_task_ids = Tuple(sort!(UInt64[
        (record.proposal.task_id for record in candidates.history)...,
        (proposal.task_id for proposal in pending)...,
    ]))
    snapshot = WorkspaceSnapshot(
        candidates,
        scheduler,
        pending,
        refinement_queue,
        seen_task_ids,
        _bool(object["adaptive_unbounded"], string(path, ".adaptive_unbounded")),
    )
    _construct(path, () -> _restore_workspace(snapshot))
    return snapshot
end

function _checkpoint_rng_document(rng_state)
    rng_state isa NamedTuple && keys(rng_state) == (:seed,) && rng_state.seed isa UInt64 ||
        _protocol_error("state.rng_state", "only the deterministic counter seed RNG is checkpointable")
    return Dict{String,Any}(
        "kind" => "counter_seed",
        "seed" => _checkpoint_uint64_document(rng_state.seed),
    )
end

function _decode_checkpoint_rng(raw, path)
    object = _object(raw, ("kind", "seed"); path)
    _string(object["kind"], string(path, ".kind")) == "counter_seed" ||
        _protocol_error(string(path, ".kind"), "unknown RNG state kind")
    return (
        seed = _decode_checkpoint_uint64(object["seed"], string(path, ".seed")),
    )
end

function _checkpoint_state_document(snapshot::CheckpointSnapshot)
    return Dict{String,Any}(
        "resume_identity" => _environment_lock_document(snapshot.resume_identity),
        "policy_version" => string(snapshot.policy_version),
        "budget" => _checkpoint_budget_snapshot_document(snapshot.budget),
        "workspace" => _checkpoint_workspace_document(snapshot.workspace),
        "events" => Any[
            _checkpoint_event_document(event, string("state.events.", index - 1)) for
            (index, event) in enumerate(snapshot.events)
        ],
        "rng_state" => _checkpoint_rng_document(snapshot.rng_state),
        "precision_bits" => snapshot.precision_bits,
        "remaining_seconds" => _checkpoint_real_document(
            snapshot.remaining_seconds,
            "state.remaining_seconds",
        ),
        "cancelled" => snapshot.cancelled,
    )
end

function _decode_checkpoint_state(raw, path)
    object = _object(
        raw,
        (
            "resume_identity",
            "policy_version",
            "budget",
            "workspace",
            "events",
            "rng_state",
            "precision_bits",
            "remaining_seconds",
            "cancelled",
        );
        path,
    )
    events = Tuple(
        _decode_checkpoint_event(value, string(path, ".events.", index - 1)) for
        (index, value) in enumerate(_array(object["events"], string(path, ".events")))
    )
    _construct(string(path, ".events"), () -> _restore_events(events))
    remaining = _decode_checkpoint_real(
        object["remaining_seconds"],
        string(path, ".remaining_seconds"),
    )
    remaining isa Float64 && isfinite(remaining) && remaining >= 0 ||
        _protocol_error(string(path, ".remaining_seconds"), "must be a finite Float64")
    return CheckpointSnapshot(
        _decode_environment_lock(object["resume_identity"], string(path, ".resume_identity")),
        _canonical_version(object["policy_version"], string(path, ".policy_version")),
        _decode_checkpoint_budget_snapshot(object["budget"], string(path, ".budget")),
        _decode_checkpoint_workspace(object["workspace"], string(path, ".workspace")),
        events,
        _decode_checkpoint_rng(object["rng_state"], string(path, ".rng_state")),
        _integer(object["precision_bits"], string(path, ".precision_bits"); minimum = 2),
        remaining,
        _bool(object["cancelled"], string(path, ".cancelled")),
    )
end

function _checkpoint_payload_document(
    snapshot::CheckpointSnapshot,
    target_image_status::TargetImageStatus,
)
    target_image_status in (
        TARGET_IMAGE_UNKNOWN,
        TARGET_FINITE_OBSERVED,
        TARGET_LIKELY_CONTINUOUS,
    ) || _protocol_error(
        "target_image_status",
        "checkpoint cannot carry a certified target-image status",
    )
    return Dict{String,Any}(
        "target_image_status" => _TARGET_TO_WIRE[target_image_status],
        "state" => _checkpoint_state_document(snapshot),
    )
end

function SolveCheckpointArtifact(
    snapshot::CheckpointSnapshot,
    target_image_status::TargetImageStatus,
)
    payload = _checkpoint_payload_document(snapshot, target_image_status)
    return SolveCheckpointArtifact(
        snapshot,
        target_image_status,
        canonical_json_hash(payload),
    )
end

checkpoint_hash(checkpoint::SolveCheckpointArtifact) = checkpoint.content

function checkpoint_document(checkpoint::SolveCheckpointArtifact)
    payload = _checkpoint_payload_document(
        checkpoint.snapshot,
        checkpoint.target_image_status,
    )
    canonical_json_hash(payload) == checkpoint.content ||
        _protocol_error("content_hash", "checkpoint content hash does not match its typed state")
    return Dict{String,Any}(
        "schema_version" => CHECKPOINT_WIRE_VERSION,
        "content_hash" => string(checkpoint.content),
        "target_image_status" => payload["target_image_status"],
        "state" => payload["state"],
    )
end

encode_checkpoint_json(checkpoint::SolveCheckpointArtifact) =
    canonical_json(checkpoint_document(checkpoint))

function decode_checkpoint_document(raw)
    object = _object(
        raw,
        ("schema_version", "content_hash", "target_image_status", "state");
        path = "document",
    )
    _string(object["schema_version"], "schema_version") == CHECKPOINT_WIRE_VERSION ||
        _protocol_error("schema_version", "expected $CHECKPOINT_WIRE_VERSION")
    canonical_json_bytes(object)
    target_text = _string(object["target_image_status"], "target_image_status")
    target_status = get(_TARGET_FROM_WIRE, target_text, nothing)
    target_status in (
        TARGET_IMAGE_UNKNOWN,
        TARGET_FINITE_OBSERVED,
        TARGET_LIKELY_CONTINUOUS,
    ) || _protocol_error("target_image_status", "unsupported checkpoint target-image status")
    payload = Dict{String,Any}(
        "target_image_status" => target_text,
        "state" => object["state"],
    )
    declared = _canonical_hash(object["content_hash"], "content_hash")
    canonical_json_hash(payload) == declared ||
        _protocol_error("content_hash", "checkpoint content hash mismatch")
    snapshot = _decode_checkpoint_state(object["state"], "state")
    checkpoint = SolveCheckpointArtifact(snapshot, target_status)
    checkpoint.content == declared ||
        _protocol_error("content_hash", "decoded checkpoint state changed its content hash")
    canonical_json_bytes(checkpoint_document(checkpoint)) == canonical_json_bytes(object) ||
        _protocol_error("document", "checkpoint is not its canonical typed projection")
    return checkpoint
end

decode_checkpoint_json(source) = decode_checkpoint_document(parse_protocol_json(source))

function write_checkpoint(path::AbstractString, checkpoint::SolveCheckpointArtifact)
    supplied = String(path)
    isempty(strip(supplied)) && throw(ArgumentError("checkpoint path must not be blank"))
    destination = abspath(supplied)
    mkpath(dirname(destination))
    temporary = string(destination, ".tmp-", getpid(), '-', time_ns())
    try
        open(temporary, "w") do io
            write(io, encode_checkpoint_json(checkpoint))
        end
        # The temporary is a sibling, so filesystem rename is a single atomic
        # replacement rather than `mv(...; force=true)`, which may unlink the
        # destination before moving on some platforms.
        Base.Filesystem.rename(temporary, destination)
    finally
        isfile(temporary) && rm(temporary; force = true)
    end
    return checkpoint
end
read_checkpoint(path::AbstractString) = decode_checkpoint_json(read(path, String))
