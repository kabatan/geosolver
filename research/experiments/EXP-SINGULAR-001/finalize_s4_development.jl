include(joinpath(@__DIR__, "run_s4_development.jl"))

const S4_FINALIZATION_AMENDMENT = joinpath(
    @__DIR__,
    "s4-protocol-amendment-a8.json",
)
const S4_FAILED_FORMAL_AUDIT = normpath(joinpath(
    @__DIR__,
    "..",
    "..",
    "results",
    "EXP-SINGULAR-001",
    "development-s4-v0-formal-run-audit.json",
))
const S4_FAILED_FINALIZATION_AUDIT = normpath(joinpath(
    @__DIR__,
    "..",
    "..",
    "results",
    "EXP-SINGULAR-001",
    "development-s4-v0-finalization-formal-run-audit.json",
))

function _s4_checkpoint_collection_sha256(paths)
    lines = String[
        "$(basename(path)) $(_s4_sha(path))" for path in sort!(collect(paths))
    ]
    return bytes2hex(sha256(codeunits(join(lines, '\n'))))
end

function _s4_verify_finalization_amendment()
    isfile(S4_FINALIZATION_AMENDMENT) || error("missing S4 finalization amendment")
    amendment_payload = read(S4_FINALIZATION_AMENDMENT)
    amendment_sha256 = bytes2hex(sha256(amendment_payload))
    amendment = JSON3.read(String(amendment_payload))
    amendment.status == "frozen-after-finalizer-world-age-failure-before-result-finalization" ||
        error("S4 finalization amendment has wrong status")
    _s4_sha(@__FILE__) == String(amendment.finalizer_source_sha256) ||
        error("S4 finalizer source hash mismatch")
    freeze_payload = read(S4_IMPLEMENTATION_FREEZE)
    implementation_freeze_sha256 = bytes2hex(sha256(freeze_payload))
    implementation_freeze_sha256 ==
        String(amendment.failed_run_bindings.implementation_freeze_sha256) ||
        error("S4 finalization freeze mismatch")
    failed_audit_payload = read(S4_FAILED_FORMAL_AUDIT)
    failed_audit_sha256 = bytes2hex(sha256(failed_audit_payload))
    failed_audit_sha256 ==
        String(amendment.failed_run_bindings.failed_formal_run_audit_sha256) ||
        error("S4 failed formal audit mismatch")
    failed_finalization_payload = read(S4_FAILED_FINALIZATION_AUDIT)
    failed_finalization_audit_sha256 = bytes2hex(sha256(failed_finalization_payload))
    failed_finalization_audit_sha256 ==
        String(amendment.failed_run_bindings.failed_finalization_audit_sha256) ||
        error("S4 failed finalization audit mismatch")
    return (
        amendment_sha256=amendment_sha256,
        document=amendment,
        failed_audit_sha256=failed_audit_sha256,
        failed_finalization_audit_sha256=failed_finalization_audit_sha256,
        implementation_freeze_sha256=implementation_freeze_sha256,
    )
end

function _s4_failed_run_snapshot(amendment)
    bindings = amendment.failed_run_bindings
    identity_payload = read(S4_RUN_IDENTITY)
    identity_sha256 = bytes2hex(sha256(identity_payload))
    identity_sha256 == String(bindings.run_identity_sha256) ||
        error("S4 failed-run identity hash mismatch")
    warmup_payload = read(S4_WARMUP_ARTIFACT)
    warmup_sha256 = bytes2hex(sha256(warmup_payload))
    warmup_sha256 == String(bindings.warmup_sha256) ||
        error("S4 failed-run warm-up hash mismatch")
    manifest_payload = read(S4_CHECKPOINT_MANIFEST)
    manifest_sha256 = bytes2hex(sha256(manifest_payload))
    manifest_sha256 == String(bindings.checkpoint_manifest_sha256) ||
        error("S4 failed-run checkpoint manifest hash mismatch")
    return (
        checkpoint_manifest=JSON3.read(String(manifest_payload)),
        checkpoint_manifest_sha256=manifest_sha256,
        run_identity=JSON3.read(String(identity_payload), Dict{String,Any}),
        run_identity_sha256=identity_sha256,
        warmup_sha256=warmup_sha256,
    )
end

function _s4_verify_checkpoint_manifest!(manifest, cases, provenance, paths)
    manifest.schema == "geotarget.singular-s4-checkpoint-manifest/v1" ||
        error("S4 checkpoint manifest schema mismatch")
    Int(manifest.row_count) == 108 || error("S4 checkpoint manifest row count mismatch")
    String(manifest.implementation_freeze_sha256) ==
        provenance.implementation_freeze_sha256 ||
        error("S4 checkpoint manifest implementation mismatch")
    String(manifest.input_manifest_sha256) == provenance.input_manifest_sha256 ||
        error("S4 checkpoint manifest input mismatch")
    String(manifest.run_identity_sha256) == provenance.run_identity_sha256 ||
        error("S4 checkpoint manifest runtime mismatch")
    String(manifest.warmup_sha256) == provenance.warmup_sha256 ||
        error("S4 checkpoint manifest warm-up mismatch")
    length(manifest.checkpoints) == length(cases) == 36 ||
        error("S4 checkpoint manifest cardinality mismatch")
    for (index, (case, path, entry)) in enumerate(zip(cases, paths, manifest.checkpoints))
        expected_order = ExperimentSingular001._s4_counterbalanced_variant_order(index)
        Int(entry.case_index) == index || error("S4 checkpoint entry index mismatch")
        String(entry.case_id) == case.generated.input.oracle.id ||
            error("S4 checkpoint entry case mismatch")
        String(entry.case_checksum) == case.generated.checksum ||
            error("S4 checkpoint entry checksum mismatch")
        normpath(joinpath(S4_RESULT_DIRECTORY, String(entry.path))) == path ||
            error("S4 checkpoint entry path mismatch")
        String(entry.sha256) == _s4_sha(path) ||
            error("S4 checkpoint entry hash mismatch")
        Tuple(String(value) for value in entry.variant_order) == expected_order ||
            error("S4 checkpoint entry order mismatch")
    end
    return nothing
end

function _s4_load_frozen_checkpoint(path, case, index, provenance, expected_sha256)
    payload = read(path)
    bytes2hex(sha256(payload)) == expected_sha256 ||
        error("S4 frozen checkpoint changed before replay")
    checkpoint = JSON3.read(String(payload), Dict{String,Any})
    variant_order = ExperimentSingular001._s4_counterbalanced_variant_order(index)
    checkpoint["schema"] == "geotarget.singular-s4-case-checkpoint/v1" ||
        error("invalid S4 frozen checkpoint schema")
    checkpoint["case_id"] == case.generated.input.oracle.id ||
        error("S4 frozen checkpoint case id mismatch")
    checkpoint["case_checksum"] == case.generated.checksum ||
        error("S4 frozen checkpoint case checksum mismatch")
    checkpoint["case_index"] == index || error("S4 frozen checkpoint index mismatch")
    checkpoint["implementation_freeze_sha256"] ==
        provenance.implementation_freeze_sha256 ||
        error("S4 frozen checkpoint implementation mismatch")
    checkpoint["input_manifest_sha256"] == provenance.input_manifest_sha256 ||
        error("S4 frozen checkpoint input mismatch")
    checkpoint["run_identity_sha256"] == provenance.run_identity_sha256 ||
        error("S4 frozen checkpoint runtime mismatch")
    checkpoint["warmup_sha256"] == provenance.warmup_sha256 ||
        error("S4 frozen checkpoint warm-up mismatch")
    Tuple(String(value) for value in checkpoint["variant_order"]) == variant_order ||
        error("S4 frozen checkpoint variant-order mismatch")
    rows = checkpoint["rows"]
    length(rows) == 3 || error("S4 frozen checkpoint row count mismatch")
    Tuple(String(row["variant"]) for row in rows) == variant_order ||
        error("S4 frozen checkpoint row-order mismatch")
    Tuple(Int(row["execution_index"]) for row in rows) ==
        Tuple((3 * (index - 1) + 1):(3 * index)) ||
        error("S4 frozen checkpoint execution-index mismatch")
    all(row -> row["case_id"] == case.generated.input.oracle.id, rows) ||
        error("S4 frozen checkpoint row case mismatch")
    all(row -> row["case_checksum"] == case.generated.checksum, rows) ||
        error("S4 frozen checkpoint row checksum mismatch")
    return Any[rows...]
end

function _s4_replay_frozen_rows!(amendment, cases, provenance, manifest)
    base_entries = Set((
        "case-checkpoints",
        "checkpoint-manifest.json",
        "run-identity.json",
        "warmup.json",
    ))
    final_entries = Set((
        "raw.json",
        "summary.json",
        "environment.json",
        "report.md",
        "result-bindings.json",
    ))
    observed_entries = Set(readdir(S4_RESULT_DIRECTORY; join=false))
    issubset(base_entries, observed_entries) ||
        error("S4 failed-run archive is missing a base entry")
    issubset(observed_entries, union(base_entries, final_entries)) ||
        error("S4 failed-run archive contains an unexpected entry")
    "result-bindings.json" in observed_entries &&
        error("S4 finalization refuses a completed result archive")
    isfile(S4_RUN_IDENTITY) || error("missing S4 failed-run identity")
    isfile(S4_WARMUP_ARTIFACT) || error("missing S4 failed-run warm-up")
    isfile(S4_CHECKPOINT_MANIFEST) || error("missing S4 failed-run checkpoint manifest")
    expected_paths = String[
        normpath(_s4_checkpoint_path(index, case)) for (index, case) in enumerate(cases)
    ]
    actual_paths = sort!(filter(
        path -> endswith(path, ".json"),
        readdir(S4_CHECKPOINT_DIRECTORY; join=true),
    ))
    Set(readdir(S4_CHECKPOINT_DIRECTORY; join=false)) ==
        Set(basename(path) for path in expected_paths) ||
        error("S4 checkpoint directory contains an unexpected entry")
    actual_paths == expected_paths || error("S4 failed-run checkpoint set mismatch")
    length(actual_paths) == 36 || error("S4 failed-run checkpoint count mismatch")
    _s4_checkpoint_collection_sha256(actual_paths) ==
        String(amendment.failed_run_bindings.checkpoint_name_hash_collection_sha256) ||
        error("S4 failed-run checkpoint collection mismatch")
    _s4_verify_checkpoint_manifest!(manifest, cases, provenance, actual_paths)
    rows = Any[]
    for (index, (case, path, entry)) in
        enumerate(zip(cases, actual_paths, manifest.checkpoints))
        append!(rows, _s4_load_frozen_checkpoint(
            path,
            case,
            index,
            provenance,
            String(entry.sha256),
        ))
    end
    length(rows) == 108 || error("S4 replay row grid is incomplete")
    return rows
end

function _s4_install_frozen_writer_bindings!(provenance)
    for (name, value) in (
        (:checkpoint_manifest_sha256, provenance.checkpoint_manifest_sha256),
        (:run_identity_sha256, provenance.run_identity_sha256),
        (:warmup_sha256, provenance.warmup_sha256),
    )
        isdefined(ExperimentSingular001, name) &&
            error("S4 frozen writer binding already exists: $name")
        expression = Expr(:const, Expr(:(=), name, String(value)))
        Core.eval(ExperimentSingular001, expression)
        Base.invokelatest(isconst, ExperimentSingular001, name) ||
            error("S4 frozen writer binding is not constant: $name")
        Base.invokelatest(getfield, ExperimentSingular001, name) == String(value) ||
            error("S4 frozen writer binding differs: $name")
    end
    return nothing
end

function _s4_reverify_approved_inputs!(approved, provenance, bindings)
    _s4_verify_implementation_freeze()
    _s4_sha(S4_FINALIZATION_AMENDMENT) == approved.amendment_sha256 ||
        error("S4 finalization amendment changed before publication")
    _s4_sha(S4_FAILED_FORMAL_AUDIT) == approved.failed_audit_sha256 ||
        error("S4 failed formal audit changed before publication")
    _s4_sha(S4_FAILED_FINALIZATION_AUDIT) ==
        approved.failed_finalization_audit_sha256 ||
        error("S4 failed finalization audit changed before publication")
    _s4_sha(S4_IMPLEMENTATION_FREEZE) == approved.implementation_freeze_sha256 ||
        error("S4 implementation freeze changed before publication")
    _s4_sha(S4_RUN_IDENTITY) == provenance.run_identity_sha256 ||
        error("S4 run identity changed before publication")
    _s4_sha(S4_WARMUP_ARTIFACT) == provenance.warmup_sha256 ||
        error("S4 warm-up changed before publication")
    _s4_sha(S4_CHECKPOINT_MANIFEST) == provenance.checkpoint_manifest_sha256 ||
        error("S4 checkpoint manifest changed before publication")
    _s4_sha(S4_INPUT_MANIFEST) == provenance.input_manifest_sha256 ||
        error("S4 input manifest changed before publication")
    checkpoint_paths = sort!(readdir(S4_CHECKPOINT_DIRECTORY; join=true))
    length(checkpoint_paths) == 36 ||
        error("S4 checkpoint count changed before publication")
    _s4_checkpoint_collection_sha256(checkpoint_paths) == String(
        approved.document.failed_run_bindings.checkpoint_name_hash_collection_sha256,
    ) || error("S4 checkpoint collection changed before publication")
    expected_entries = Set((
        "case-checkpoints",
        "checkpoint-manifest.json",
        "environment.json",
        "raw.json",
        "report.md",
        "run-identity.json",
        "summary.json",
        "warmup.json",
    ))
    Set(readdir(S4_RESULT_DIRECTORY; join=false)) == expected_entries ||
        error("S4 pre-terminal archive set changed")
    for (name, key) in (
        ("environment.json", "environment_sha256"),
        ("raw.json", "raw_sha256"),
        ("report.md", "report_sha256"),
        ("summary.json", "summary_sha256"),
    )
        _s4_sha(joinpath(S4_RESULT_DIRECTORY, name)) == bindings[key] ||
            error("S4 published artifact changed before terminal marker: $name")
    end
    return nothing
end

function _s4_publish_staged_archive!(staging_directory, filenames)
    expected = Dict(
        name => _s4_sha(joinpath(staging_directory, name)) for name in filenames
    )
    for name in filenames
        source = joinpath(staging_directory, name)
        destination = joinpath(S4_RESULT_DIRECTORY, name)
        if isfile(destination)
            _s4_sha(destination) == expected[name] ||
                error("S4 existing finalization artifact differs: $name")
        else
            mv(source, destination)
        end
        _s4_sha(destination) == expected[name] ||
            error("S4 published finalization artifact differs: $name")
    end
    return nothing
end

function main()
    approved = _s4_verify_finalization_amendment()
    amendment = approved.document
    freeze = _s4_verify_implementation_freeze()
    s4_options = ExperimentOptions(
        precision_ladder=(128, 256),
        semantic_precision_bits=256,
    )
    baseline_options = ExperimentOptions()
    expected_identity = _s4_runtime_identity(freeze, s4_options, baseline_options)
    snapshot = _s4_failed_run_snapshot(amendment)
    _s4_same_document(snapshot.run_identity, expected_identity) ||
        error("S4 failed-run identity content mismatch")
    cases = ExperimentSingular001.s4_development_cases()
    _s4_verify_case_grid(cases)
    provenance = (
        checkpoint_manifest_sha256=snapshot.checkpoint_manifest_sha256,
        implementation_freeze_sha256=approved.implementation_freeze_sha256,
        input_manifest_sha256=_s4_sha(S4_INPUT_MANIFEST),
        run_identity_sha256=snapshot.run_identity_sha256,
        warmup_sha256=snapshot.warmup_sha256,
    )
    rows = _s4_replay_frozen_rows!(
        amendment,
        cases,
        provenance,
        snapshot.checkpoint_manifest,
    )
    summary = ExperimentSingular001.s4_development_summary(
        rows;
        s4_options,
        baseline_options,
        checkpoint_manifest_sha256=provenance.checkpoint_manifest_sha256,
        run_identity_sha256=provenance.run_identity_sha256,
        warmup_sha256=provenance.warmup_sha256,
    )
    _s4_install_frozen_writer_bindings!(provenance)
    mktempdir(dirname(S4_RESULT_DIRECTORY); prefix=".s4-finalization-a7-") do staging
        bindings = ExperimentSingular001.write_s4_development_results(
            staging,
            rows,
            summary;
            input_manifest_path=S4_INPUT_MANIFEST,
            implementation_freeze_path=S4_IMPLEMENTATION_FREEZE,
            s4_options,
            baseline_options,
        )
        for (name, key) in (
            ("environment.json", "environment_sha256"),
            ("raw.json", "raw_sha256"),
            ("report.md", "report_sha256"),
            ("summary.json", "summary_sha256"),
        )
            _s4_sha(joinpath(staging, name)) == bindings[key] ||
                error("S4 staged artifact binding mismatch: $name")
        end
        ExperimentSingular001.write_json_artifact(
            joinpath(staging, "result-bindings.json"),
            Dict{String,Any}(
                "bindings" => bindings,
                "checkpoint_manifest_sha256" => provenance.checkpoint_manifest_sha256,
                "failed_formal_run_audit_sha256" => approved.failed_audit_sha256,
                "failed_finalization_audit_sha256" =>
                    approved.failed_finalization_audit_sha256,
                "finalization_amendment_sha256" => approved.amendment_sha256,
                "implementation_freeze_sha256" => provenance.implementation_freeze_sha256,
                "input_manifest_sha256" => provenance.input_manifest_sha256,
                "product_connected" => false,
                "run_identity_sha256" => provenance.run_identity_sha256,
                "schema" => "geotarget.singular-s4-result-bindings/v1",
                "warmup_sha256" => provenance.warmup_sha256,
            ),
        )
        # Publish nonterminal artifacts, then reverify the entire frozen/base
        # closure and exact preterminal archive before publishing the marker.
        _s4_publish_staged_archive!(
            staging,
            (
                "raw.json",
                "summary.json",
                "environment.json",
                "report.md",
            ),
        )
        _s4_reverify_approved_inputs!(approved, provenance, bindings)
        _s4_publish_staged_archive!(staging, ("result-bindings.json",))
    end
    return nothing
end

if abspath(PROGRAM_FILE) == abspath(@__FILE__)
    main()
end
