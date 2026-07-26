#!/usr/bin/env python3
"""Re-audit the two stored zero-dimensional sources without new search."""

from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import sys


HERE = Path(__file__).resolve().parent
BASELINE = HERE.parents[1] / "results/baseline-corrected-247-180s-seed0-v1"


def _load_candidate():
    specification = importlib.util.spec_from_file_location(
        "zero_dimensional_stored_exact_audit", HERE / "candidate.py"
    )
    if specification is None or specification.loader is None:
        raise ImportError(HERE / "candidate.py")
    module = importlib.util.module_from_spec(specification)
    sys.modules[specification.name] = module
    specification.loader.exec_module(module)
    return module


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def main() -> None:
    candidate = _load_candidate()
    expected = {
        "039-OMC009_C": [29, -81],
        "087-OMC142_B": [16, -675],
    }
    rows = []
    for slug, expected_polynomial in expected.items():
        source = (BASELINE / "inputs" / f"{slug}.json").read_bytes()
        authority_path = (
            BASELINE
            / "artifacts"
            / slug
            / "hp/0000-df3f619804a92fdb/authority.json"
        )
        authority_payload = authority_path.read_bytes()
        authority = json.loads(authority_payload)
        result = candidate.run_zero_dimensional_authority(
            source,
            _sha256(source),
            (),
            backend=lambda *_args, _authority=authority, **_kwargs: _authority,
        )
        descriptor = result.get("exact_target_descriptor")
        observed_polynomial = (
            descriptor.get("minimal_polynomial_high_to_low")
            if isinstance(descriptor, dict)
            else None
        )
        rows.append(
            {
                "slug": slug,
                "source_sha256": _sha256(source),
                "stored_numeric_replay_sha256": _sha256(authority_payload),
                "authority_pass": result.get("authority_pass"),
                "status": result.get("status"),
                "expected_polynomial_for_test_only": expected_polynomial,
                "observed_source_exact_polynomial": observed_polynomial,
                "polynomial_expectation_met": (
                    observed_polynomial == expected_polynomial
                ),
                "selected_real_root_index": (
                    descriptor.get("selected_real_root_index")
                    if isinstance(descriptor, dict)
                    else None
                ),
                "exact_authority_kind": result.get("exact_authority_kind"),
                "numeric_pslq_descriptor_used": result.get(
                    "numeric_pslq_descriptor_used"
                ),
                "numeric_replay_audit": result.get("numeric_replay_audit"),
                "failure_reasons": result.get("failure_reasons"),
            }
        )
    evidence = {
        "schema_version": (
            "geotarget.exp-v15-243-zero-dimensional-stored-exact-audit/v1"
        ),
        "new_search_or_heldout_run": False,
        "stored_numeric_artifacts_used_only_for_replay_parity": True,
        "numeric_pslq_descriptor_used": False,
        "nondeterministic_timing_excluded_from_frozen_evidence": True,
        "all_pass": all(
            row["authority_pass"] is True
            and row["polynomial_expectation_met"] is True
            and row["numeric_pslq_descriptor_used"] is False
            for row in rows
        ),
        "rows": rows,
    }
    output = HERE / "STORED_ZERO_DIMENSIONAL_EXACT_EVIDENCE.json"
    output.write_text(json.dumps(evidence, indent=2) + "\n")
    print(json.dumps(evidence, indent=2))
    if not evidence["all_pass"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
