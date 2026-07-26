#!/usr/bin/env python3
"""Run the general zero-dimensional lane on a tiny generated family."""

from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import sys


HERE = Path(__file__).resolve().parent


def _load(name: str, path: Path):
    specification = importlib.util.spec_from_file_location(name, path)
    if specification is None or specification.loader is None:
        raise ImportError(path)
    module = importlib.util.module_from_spec(specification)
    sys.modules[name] = module
    specification.loader.exec_module(module)
    return module


def main() -> None:
    candidate = _load(
        "zero_dimensional_candidate_smoke", HERE / "candidate.py"
    )
    generated = _load(
        "zero_dimensional_generated_smoke", HERE / "generated_cases.py"
    )
    expected_authority = {
        "constant_rational_positive": True,
        "rational_geometry_positive": True,
        "algebraic_geometry_positive": True,
        "exact_conditions_positive": True,
        # The exact certificate passes, but the unchanged numerical replay
        # cannot represent these extreme literals and must fail closed.
        "extreme_numeric_guards_positive": False,
        # Exact Boolean IR passes, but the unchanged numerical replay does
        # not support this nested representation and must fail closed.
        "nested_boolean_guards_positive": False,
        "invalid_guard_near_miss": False,
        "near_unsatisfied_constraint": False,
        "near_unsatisfied_guard": False,
        "underflow_guard_near_miss": False,
        "extreme_open_bound_near_miss": False,
        "nested_boolean_false_near_miss": False,
        "nested_boolean_unknown_under_not_near_miss": False,
        "unproved_geometry_guard": False,
        "transcendental_near_miss": False,
        "near_transcendental_shift_near_miss": False,
        "algebraic_argument_sine_near_miss": False,
        "inverse_trig_near_miss": False,
        "unsupported_target_near_miss": False,
        "positive_dimension_near_miss": False,
        "irrational_circle_phase_near_miss": False,
    }
    rows = []
    for name, payload in generated.generated_family().items():
        result = candidate.run_zero_dimensional_authority(
            payload,
            hashlib.sha256(payload).hexdigest(),
            (),
            deadline_seconds=3.0,
            primary_cap_seconds=1.5,
        )
        observed = result.get("authority_pass") is True
        rows.append(
            {
                "name": name,
                "expected_authority_pass": expected_authority[name],
                "observed_authority_pass": observed,
                "expectation_met": observed is expected_authority[name],
                "status": result.get("status"),
                "failure_reasons": result.get("failure_reasons"),
                "descriptor": result.get("exact_target_descriptor"),
            }
        )
    lexeme_probe = generated.generated_family()[
        "extreme_numeric_guards_positive"
    ]
    lexeme_failures = candidate._exact_source_conditions_certificate(
        lexeme_probe
    )
    nested_probe = generated.generated_family()[
        "nested_boolean_guards_positive"
    ]
    nested_failures = candidate._exact_source_conditions_certificate(
        nested_probe
    )
    evidence = {
        "schema_version": (
            "geotarget.exp-v15-243-zero-dimensional-light-smoke/v1"
        ),
        "all_expectations_met": (
            all(row["expectation_met"] for row in rows)
            and lexeme_failures == ()
            and nested_failures == ()
        ),
        "false_or_extra_target_count": sum(
            1
            for row in rows
            if row["observed_authority_pass"]
            and not row["expected_authority_pass"]
        ),
        "rows": rows,
        "exact_guard_lexeme_probe": {
            "source_family": "extreme_numeric_guards_positive",
            "expected_condition_failures": [],
            "observed_condition_failures": list(lexeme_failures),
            "exact_certificate_pass": lexeme_failures == (),
            "end_to_end_expected_fail_closed_reason": (
                "UNCHANGED_NUMERICAL_REPLAY_CANNOT_REPRESENT_EXTREME_LEXEMES"
            ),
        },
        "exact_nested_boolean_guard_probe": {
            "source_family": "nested_boolean_guards_positive",
            "expected_condition_failures": [],
            "observed_condition_failures": list(nested_failures),
            "exact_certificate_pass": nested_failures == (),
            "supported_boolean_ir": [
                "Assume",
                "And",
                "Or",
                "Not",
                "python_and_or_not",
            ],
            "end_to_end_expected_fail_closed_reason": (
                "UNCHANGED_NUMERICAL_REPLAY_LACKS_NESTED_BOOLEAN_SUPPORT"
            ),
        },
        "truth_or_known_target_count_used_by_candidate": False,
        "heavy_panel_run": False,
        "nondeterministic_timing_excluded_from_frozen_evidence": True,
    }
    (HERE / "LIGHT_SMOKE_EVIDENCE.json").write_text(
        json.dumps(evidence, indent=2) + "\n"
    )
    print(json.dumps(evidence, indent=2))
    if not evidence["all_expectations_met"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
