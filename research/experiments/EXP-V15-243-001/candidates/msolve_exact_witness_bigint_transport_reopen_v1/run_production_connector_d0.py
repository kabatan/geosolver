#!/usr/bin/env python3.12
"""Generated/saved-only D0 for the full ordinary proposal connector."""

from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import platform
import time

import ordinary_proposal_binding as binding
import saved_chain_verifier as saved
import selected_execution_common as common


HERE = Path(__file__).resolve().parent
PANEL = binding.APPROVED_PANEL_ROOT / "requests.json"
PANEL_SHA256 = "29f00d60bbdf4e4862eccdd3ac5c1274b48ba3ee5d4d0f5ee218cf42fea51233"


def _rejected(function, *args, **kwargs):
    try:
        function(*args, **kwargs)
    except (binding.OrdinaryBindingRejected, saved.SavedChainRejected) as error:
        return True, str(error)
    return False, "NOT_REJECTED"


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


def run():
    started = time.monotonic()
    if os.sched_getaffinity(0) != {14}:
        raise RuntimeError("connector D0 must run pinned to CPU14")
    panel_bytes = PANEL.read_bytes()
    if hashlib.sha256(panel_bytes).hexdigest() != PANEL_SHA256:
        raise RuntimeError("saved ordinary binding panel SHA changed")
    rows = json.loads(panel_bytes)
    bound = [binding.bind_row(row) for row in rows]
    dependencies = common.load_admission_dependencies()
    admissions = [
        common.classify_bound_ordinary_row(row, dependencies=dependencies)
        for row in rows
    ]

    descriptor_degrees = []
    for descriptor in (
        _descriptor([1, -2], 2, 2, 0),
        _descriptor([1, 0, -2], 1, 2, 1),
        _descriptor([1, 0, 0, -1, -1], 1, 2, 1),
    ):
        _exact, _target, coefficients, _ordinal = binding._validated_descriptor(descriptor)
        descriptor_degrees.append(len(coefficients) - 1)
    degree_three_rejected, degree_three_reason = _rejected(
        binding._validated_descriptor,
        _descriptor([1, 0, 0, -2], 1, 2, 0),
    )
    oversized_bigint_rejected, oversized_bigint_reason = _rejected(
        binding._validated_descriptor,
        _descriptor([1 << 4096, -1], 0, 1, 0),
    )

    replay_ledger_pass = 0
    for admission in admissions:
        compiled = admission["compiled"]
        exact_counts = {
            "source_relation_count": 2,
            "source_guard_count": 3,
            "source_bound_count": 1,
            "rur_relation_count": 4,
            "compiler_equation_count": len(compiled["equations"]),
            "compiler_predicate_count": len(compiled["predicates"]),
        }
        replay_result = {
            "source_relation_count": 6 + len(compiled["equations"]),
            "source_guard_count": 3 + len(compiled["predicates"]),
            "source_bound_count": 1,
            "source_raw_answer_exact": True,
            "target_link_exact": True,
        }
        common.exact_replay_ledger(compiled, exact_counts, replay_result)
        replay_ledger_pass += 1

    frozen = saved.load_frozen()
    chain = saved.verify_saved_chain(*frozen)
    replay, _replay_bytes, selection, selection_bytes, factor, _factor_bytes = frozen

    wrong_factor_replay, wrong_factor = deepcopy(replay), deepcopy(factor)
    wrong_factor["selected_factor_coefficients_low_to_high"][0] += 1
    wrong_factor_bytes = saved.canonical_mutation_bytes(wrong_factor)
    wrong_factor_replay["source_artifact_bindings"]["selected_factor_sha256"] = saved._sha256(wrong_factor_bytes)
    wrong_factor_replay_bytes = saved.canonical_mutation_bytes(wrong_factor_replay)
    wrong_factor_rejected, wrong_factor_reason = _rejected(
        saved.verify_saved_chain,
        wrong_factor_replay,
        wrong_factor_replay_bytes,
        selection,
        selection_bytes,
        wrong_factor,
        wrong_factor_bytes,
        require_frozen_replay_sha=False,
    )

    wrong_branch = deepcopy(replay)
    wrong_branch["qqbar_replay"]["source_guard_count"] -= 1
    wrong_branch_rejected, wrong_branch_reason = _rejected(
        saved.verify_saved_chain,
        wrong_branch,
        saved.canonical_mutation_bytes(wrong_branch),
        selection,
        selection_bytes,
        factor,
        frozen[5],
        require_frozen_replay_sha=False,
    )
    wrong_ordinal_rejected, wrong_ordinal_reason = _rejected(
        binding._validated_descriptor,
        _descriptor([1, 0, -2], 1, 2, 0),
    )
    wrong_binding_row = deepcopy(rows[0])
    wrong_binding_row["proposal_sha256"] = "0" * 64
    wrong_binding_rejected, wrong_binding_reason = _rejected(
        binding.bind_row, wrong_binding_row
    )

    result = {
        "schema_version": "geotarget.msolve-production-connector-d0/v1",
        "status": "PASS",
        "saved_ordinary_binding_total": len(rows),
        "saved_ordinary_binding_pass": len(bound),
        "production_selected_admission_pass": sum(
            item.get("eligible") is True for item in admissions
        ),
        "generated_descriptor_degrees_pass": sorted(descriptor_degrees),
        "degree_three_rejected": degree_three_rejected,
        "degree_three_reason_class": degree_three_reason,
        "oversized_bigint_rejected": oversized_bigint_rejected,
        "oversized_bigint_reason_class": oversized_bigint_reason,
        "compiler_replay_ledger_pass": replay_ledger_pass,
        "saved_rur_factor_qqbar_chain_pass": chain["saved_chain_pass"],
        "wrong_factor_rejected": wrong_factor_rejected,
        "wrong_factor_reason_class": wrong_factor_reason,
        "wrong_ordinal_rejected": wrong_ordinal_rejected,
        "wrong_ordinal_reason_class": wrong_ordinal_reason,
        "wrong_branch_rejected": wrong_branch_rejected,
        "wrong_branch_reason_class": wrong_branch_reason,
        "wrong_ordinary_binding_rejected": wrong_binding_rejected,
        "wrong_ordinary_binding_reason_class": wrong_binding_reason,
        "ordinary_full_proposal_binding": True,
        "individual_descriptor_only": True,
        "authority_pass": False,
        "target_release": False,
        "completeness_claim": "NOT_MADE",
        "truth_used": False,
        "formal_scorer_used": False,
        "msolve_runs": 0,
        "julia_runs": 0,
        "environment": {
            "cpu_affinity": sorted(os.sched_getaffinity(0)),
            "python": platform.python_version(),
            "elapsed_seconds": time.monotonic() - started,
        },
    }
    if not (
        result["saved_ordinary_binding_pass"] == result["saved_ordinary_binding_total"] == 4
        and result["production_selected_admission_pass"] == 4
        and result["generated_descriptor_degrees_pass"] == [1, 2, 4]
        and result["degree_three_rejected"]
        and result["oversized_bigint_rejected"]
        and result["compiler_replay_ledger_pass"] == 4
        and result["saved_rur_factor_qqbar_chain_pass"]
        and wrong_factor_rejected
        and wrong_ordinal_rejected
        and wrong_branch_rejected
        and wrong_binding_rejected
    ):
        result["status"] = "FAIL"
    return result


def main():
    result = run()
    (HERE / "PRODUCTION_CONNECTOR_D0_RESULT.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(result, ensure_ascii=False, separators=(",", ":")))
    raise SystemExit(0 if result["status"] == "PASS" else 1)


if __name__ == "__main__":
    main()
