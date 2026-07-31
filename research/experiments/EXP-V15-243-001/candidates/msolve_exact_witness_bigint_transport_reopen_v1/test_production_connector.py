from copy import deepcopy
import hashlib
import json
from pathlib import Path

import execute_selected_one as child
import ordinary_proposal_binding as binding
import run_selected_execution as parent
import saved_chain_verifier as saved
import selected_execution_common as common


PANEL = binding.APPROVED_PANEL_ROOT / "requests.json"


def _descriptor(coefficients, left, right, ordinal):
    return {
        "minimal_polynomial_high_to_low": coefficients,
        "proposal_relation_low_to_high": list(reversed(coefficients)),
        "confirmation_relation_low_to_high": list(reversed(coefficients)),
        "selected_real_root_index": ordinal,
        "isolating_interval": {
            "left": str(left),
            "right": str(right),
            "multiplicity": 1,
            "real_root_index": ordinal,
        },
        "target_512": "proposal-only",
        "target_768": "proposal-only",
        "target_1024": "proposal-only",
    }


def test_saved_ordinary_panel_binds_complete_proposal_bytes():
    rows = json.loads(PANEL.read_bytes())
    bound = [binding.bind_row(row) for row in rows]
    assert len(bound) == 4
    assert all(item.proposal_sha256 == row["proposal_sha256"] for item, row in zip(bound, rows, strict=True))
    assert all(item.authority_pass is False and item.target_release is False for item in bound)


def test_general_degree_one_two_and_four_descriptor_contract():
    degree_one = _descriptor([1, -2], 2, 2, 0)
    _exact_one, target_one, coefficients_one, ordinal_one = binding._validated_descriptor(degree_one)
    assert len(coefficients_one) - 1 == 1 and ordinal_one == 0
    assert target_one["coefficients_high_to_low"] == [1, -2]

    degree_two = _descriptor([1, 0, -2], 1, 2, 1)
    exact_two, target_two, coefficients_two, ordinal_two = binding._validated_descriptor(degree_two)
    assert len(coefficients_two) - 1 == 2 and ordinal_two == 1
    assert target_two["coefficients_high_to_low"] == [1, 0, -2]
    assert exact_two == degree_two

    degree_four = _descriptor([1, 0, 0, -1, -1], 1, 2, 1)
    _exact_four, target_four, coefficients_four, ordinal_four = binding._validated_descriptor(degree_four)
    assert len(coefficients_four) - 1 == 4 and ordinal_four == 1
    assert target_four["coefficients_high_to_low"] == [1, 0, 0, -1, -1]


def test_degree_three_and_oversized_bigint_descriptor_rejected():
    for descriptor in (
        _descriptor([1, 0, 0, -2], 1, 2, 0),
        _descriptor([1 << 4096, -1], 0, 1, 0),
    ):
        try:
            binding._validated_descriptor(descriptor)
        except binding.OrdinaryBindingRejected as error:
            assert "FIXED_CAP" in str(error)
        else:
            raise AssertionError("out-of-contract descriptor was accepted")


def test_wrong_factor_local_ordinal_rejected():
    descriptor = _descriptor([1, 0, -2], 1, 2, 0)
    try:
        binding._validated_descriptor(descriptor)
    except binding.OrdinaryBindingRejected as error:
        assert "ORDINAL" in str(error)
    else:
        raise AssertionError("wrong real-root ordinal was accepted")


def test_wrong_ordinary_all_bytes_sha_rejected():
    row = deepcopy(json.loads(PANEL.read_bytes())[0])
    row["proposal_sha256"] = "0" * 64
    try:
        binding.bind_row(row)
    except binding.OrdinaryBindingRejected as error:
        assert "ALL_BYTES" in str(error)
    else:
        raise AssertionError("wrong ordinary proposal bytes SHA was accepted")


def test_original_result_and_plan_provenance_mutations_rejected():
    bound = binding.bind_row(json.loads(PANEL.read_bytes())[0])
    original, _payload, original_path = binding._original_result(
        bound.original_result_sha256
    )
    wrong_original = deepcopy(original)
    wrong_original["truth_case_family_known_target_count_read"] = True
    try:
        binding._verify_original_result_contract(wrong_original)
    except binding.OrdinaryBindingRejected as error:
        assert "PROVENANCE" in str(error)
    else:
        raise AssertionError("truth-reading original result was accepted")

    plans = []
    for path in original_path.parent.glob("reservoir-batch-*/hp/*/PLAN.json"):
        plan = json.loads(path.read_bytes())
        if plan.get("endpoint_float64_sha256") == bound.endpoint_float64_sha256:
            plans.append(plan)
    assert len(plans) == 1
    wrong_plan = deepcopy(plans[0])
    wrong_plan["endpoint_unchanged_before_refinement"] = False
    try:
        binding._verify_original_plan_contract(
            wrong_plan, original_source_sha256=str(original["source_sha256"])
        )
    except binding.OrdinaryBindingRejected as error:
        assert "PROVENANCE" in str(error)
    else:
        raise AssertionError("endpoint-changing original plan was accepted")


def test_saved_rur_factor_qqbar_source_chain_passes():
    documents = saved.load_frozen()
    result = saved.verify_saved_chain(*documents)
    assert result["saved_chain_pass"] is True
    assert result["authority_pass"] is False
    assert result["target_release"] is False


def test_wrong_factor_rejected_after_rebinding_mutation_bytes():
    replay, _replay_bytes, selection, selection_bytes, factor, _factor_bytes = saved.load_frozen()
    replay, factor = deepcopy(replay), deepcopy(factor)
    factor["selected_factor_coefficients_low_to_high"][0] += 1
    factor_bytes = saved.canonical_mutation_bytes(factor)
    replay["source_artifact_bindings"]["selected_factor_sha256"] = saved._sha256(factor_bytes)
    replay_bytes = saved.canonical_mutation_bytes(replay)
    try:
        saved.verify_saved_chain(
            replay,
            replay_bytes,
            selection,
            selection_bytes,
            factor,
            factor_bytes,
            require_frozen_replay_sha=False,
        )
    except saved.SavedChainRejected as error:
        assert "FACTOR" in str(error)
    else:
        raise AssertionError("wrong selected factor was accepted")


def test_branch_guard_replay_mutation_rejected():
    replay, _replay_bytes, selection, selection_bytes, factor, factor_bytes = saved.load_frozen()
    replay = deepcopy(replay)
    replay["qqbar_replay"]["source_guard_count"] -= 1
    replay_bytes = saved.canonical_mutation_bytes(replay)
    try:
        saved.verify_saved_chain(
            replay,
            replay_bytes,
            selection,
            selection_bytes,
            factor,
            factor_bytes,
            require_frozen_replay_sha=False,
        )
    except saved.SavedChainRejected as error:
        assert "BRANCH" in str(error)
    else:
        raise AssertionError("wrong branch/guard replay ledger was accepted")


def _synthetic_exact_replay(compiled):
    counts = {
        "source_relation_count": 2,
        "source_guard_count": 3,
        "source_bound_count": 1,
        "rur_relation_count": 4,
        "compiler_equation_count": len(compiled["equations"]),
        "compiler_predicate_count": len(compiled["predicates"]),
    }
    replay = {
        "source_relation_count": counts["source_relation_count"]
        + counts["rur_relation_count"]
        + counts["compiler_equation_count"],
        "source_guard_count": counts["source_guard_count"]
        + counts["compiler_predicate_count"],
        "source_bound_count": counts["source_bound_count"],
        "source_raw_answer_exact": True,
        "target_link_exact": True,
    }
    return counts, replay


def test_compiler_definedness_and_branch_ledgers_fail_closed():
    row = json.loads(PANEL.read_bytes())[0]
    admission = common.classify_bound_ordinary_row(
        row, dependencies=common.load_admission_dependencies()
    )
    compiled = admission["compiled"]
    counts, replay = _synthetic_exact_replay(compiled)
    ledger = common.exact_replay_ledger(compiled, counts, replay)
    assert ledger["canonical_definedness_replay"] is True
    assert ledger["canonical_branch_replay"] is True

    wrong_replay = deepcopy(replay)
    wrong_replay["source_guard_count"] -= 1
    try:
        common.exact_replay_ledger(compiled, counts, wrong_replay)
    except common.SelectedExecutionError as error:
        assert "accounting" in str(error)
    else:
        raise AssertionError("wrong definedness count was accepted")

    wrong_compiled = deepcopy(compiled)
    wrong_compiled["branch_replay_obligation_count"] += 1
    unsigned = dict(wrong_compiled)
    unsigned.pop("artifact_sha256")
    wrong_compiled["artifact_sha256"] = common.canonical_sha256(unsigned)
    try:
        common.exact_replay_ledger(wrong_compiled, counts, replay)
    except common.SelectedExecutionError as error:
        assert "branch" in str(error)
    else:
        raise AssertionError("wrong branch obligation count was accepted")

    unknown_obligation = deepcopy(compiled)
    unknown_obligation["replay_obligations"][0]["kind"] = "unimplemented-periodic"
    unsigned = dict(unknown_obligation)
    unsigned.pop("artifact_sha256")
    unknown_obligation["artifact_sha256"] = common.canonical_sha256(unsigned)
    try:
        common.exact_replay_ledger(unknown_obligation, counts, replay)
    except common.SelectedExecutionError as error:
        assert "obligation ledger" in str(error)
    else:
        raise AssertionError("unknown replay obligation kind was accepted")


def test_parent_request_digest_and_token_are_required(tmp_path):
    run_path = tmp_path / "RUN_BINDING.json"
    child_dir = tmp_path / "request-000"
    raw_dir = child_dir / "raw"
    child_dir.mkdir()
    request_path = child_dir / "ordinary-binding.json"
    request_path.write_text("{}\n", encoding="utf-8")
    request_digest = hashlib.sha256(request_path.read_bytes()).hexdigest()
    run_document = {
        "schema_version": "geotarget.msolve-selected-exact-run-binding/v2",
        "candidate_id": "MSOLVE_EXACT_WITNESS_BIGINT_TRANSPORT_REOPEN_V1",
        "ordinary_full_proposal_binding_required": True,
        "authority_pass": False,
        "target_release": False,
        "completeness_claim": "NOT_MADE",
        "truth_used": False,
    }
    run_path.write_text(json.dumps(run_document) + "\n", encoding="utf-8")
    run_digest = hashlib.sha256(run_path.read_bytes()).hexdigest()
    token = "a" * 64
    token_digest = hashlib.sha256(token.encode("ascii")).hexdigest()
    authorization_path = child_dir / "PARENT_AUTHORIZATION.json"
    authorization = {
        "schema_version": "geotarget.msolve-selected-parent-authorization/v1",
        "candidate_id": "MSOLVE_EXACT_WITNESS_BIGINT_TRANSPORT_REOPEN_V1",
        "request_ordinal": 0,
        "ordinary_binding_request_sha256": request_digest,
        "parent_run_binding_sha256": run_digest,
        "parent_token_sha256": token_digest,
        "parent_acceptance_required": True,
        "authority_pass": False,
        "target_release": False,
        "completeness_claim": "NOT_MADE",
    }
    authorization_path.write_text(json.dumps(authorization) + "\n", encoding="utf-8")
    authorization_digest = hashlib.sha256(authorization_path.read_bytes()).hexdigest()
    _request, evidence = child._validate_parent_binding(
        raw_dir=raw_dir,
        ordinary_binding=request_path,
        ordinary_binding_sha256=request_digest,
        parent_run_binding=run_path,
        parent_run_binding_sha256=run_digest,
        parent_authorization=authorization_path,
        parent_authorization_sha256=authorization_digest,
        parent_token=token,
    )
    official = {
        **evidence,
        "authority_pass": False,
        "target_release": False,
        "completeness_claim": "NOT_MADE",
    }
    assert parent._parent_binding_matches(
        official,
        {
            "ordinary_binding_request_sha256": request_digest,
            "parent_run_binding_sha256": run_digest,
            "parent_authorization_sha256": authorization_digest,
            "parent_token_sha256": token_digest,
        },
    )
    assert not parent._parent_binding_matches(
        {**official, "ordinary_binding_request_sha256": "0" * 64},
        {
            "ordinary_binding_request_sha256": request_digest,
            "parent_run_binding_sha256": run_digest,
            "parent_authorization_sha256": authorization_digest,
            "parent_token_sha256": token_digest,
        },
    )
    for wrong_request_digest, wrong_token in (
        ("0" * 64, token),
        (request_digest, "b" * 64),
    ):
        try:
            child._validate_parent_binding(
                raw_dir=raw_dir,
                ordinary_binding=request_path,
                ordinary_binding_sha256=wrong_request_digest,
                parent_run_binding=run_path,
                parent_run_binding_sha256=run_digest,
                parent_authorization=authorization_path,
                parent_authorization_sha256=authorization_digest,
                parent_token=wrong_token,
            )
        except child.ChildExecutionError:
            pass
        else:
            raise AssertionError("direct child bypass accepted wrong request/token")


def test_stale_candidate_local_dependency_is_rejected():
    try:
        common.verify_local_runtime({Path(binding.__file__).resolve(): "0" * 64})
    except common.SelectedExecutionError as error:
        assert "digest changed" in str(error)
    else:
        raise AssertionError("stale candidate-local dependency was accepted")
