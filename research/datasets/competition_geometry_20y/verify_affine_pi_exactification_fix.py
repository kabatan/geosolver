#!/usr/bin/env python3
"""Verify the frozen affine-in-pi exactification runtime and benchmark."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
MANIFEST_PATH = ROOT / "runtime_affine_pi_exactification_fix_manifest.json"
EXPECTED = {
    "HMMT-2006-FEB-GEO-04": "27*pi/40",
    "HMMT-2008-FEB-GEO-03": "-2 + pi",
    "HMMT-2010-FEB-GEO-01": "3*pi/7",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def check_hash(path: Path, expected: str) -> None:
    actual = sha256(path)
    if actual != expected:
        raise AssertionError(f"SHA256 mismatch for {path}: {actual} != {expected}")


def check_benchmark(path: Path) -> None:
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["budget_sec"] == 180.0
    assert payload["jobs"] == 1
    assert payload["hard_timeout"] is True
    assert payload["cpu_affinity"] == [0]
    assert payload["one_core_enforced"] is True
    assert payload["runs"] == len(EXPECTED)
    assert payload["success_runs"] == len(EXPECTED)
    assert payload["correct_runs"] == len(EXPECTED)
    assert payload["no_solution_runs"] == 0
    assert payload["timeout_runs"] == 0
    assert payload["exception_runs"] == 0
    rows = {row["case_id"]: row for row in payload["results"]}
    assert set(rows) == set(EXPECTED)
    for case_id, exact_value in EXPECTED.items():
        row = rows[case_id]
        assert row["status"] == "success"
        assert row["solution_values"] == [exact_value]
        assert row["phasec"]["answer_values"] == [exact_value]
        assert row["answer_set_exact"] is True


def check_general_exactifier(runtime_root: Path) -> None:
    sys.path.insert(0, str(runtime_root / "geosolver/src"))
    import sympy as sp
    from mpmath import mp

    from geosolver._internal.pipeline.exact.identify_answer import identify_answer
    from geosolver._internal.solver.exact.affine_pi_search import (
        identify_affine_pi,
        verify_affine_pi_expression,
    )

    with mp.workdps(180):
        numeric = mp.sqrt(2) * mp.pi + mp.sqrt(3)
        result = identify_answer(
            answer_hp=numeric,
            tier="strict",
            input_precision_dps=120,
        )
        assert result.exact_status == "identified"
        assert result.identification_method == "pslq-affine-pi-algebraic"
        assert result.selected_exact_value is not None
        assert sp.simplify(
            sp.sympify(result.selected_exact_value) - (sp.sqrt(2) * sp.pi + sp.sqrt(3))
        ) == 0

        inaccurate = mp.pi - 2 + mp.mpf("1e-70")
        assert identify_affine_pi(
            numeric_value=inaccurate,
            precision_dps=120,
            max_total_degree=4,
            max_coeff=10**8,
            max_steps=20_000,
        ) is None
        verified, residual = verify_affine_pi_expression(
            expression="pi-2",
            numeric_value=inaccurate,
            precision_dps=120,
        )
        assert not verified
        assert residual > mp.mpf("1e-100")
        assert identify_affine_pi(
            numeric_value=mp.pi**2 + 1,
            precision_dps=120,
            max_total_degree=4,
            max_coeff=10**8,
            max_steps=20_000,
        ) is None


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runtime-root", type=Path)
    args = parser.parse_args()
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    runtime_root = args.runtime_root or Path(manifest["runtime_root"])

    for entry in manifest["files"]:
        check_hash(runtime_root / entry["path"], entry["sha256"])
    for entry in manifest["dsl_inputs"]:
        check_hash(ROOT / entry["path"], entry["sha256"])
    check_hash(ROOT / manifest["benchmark"]["path"], manifest["benchmark"]["sha256"])
    check_hash(ROOT / manifest["patch"]["path"], manifest["patch"]["sha256"])
    check_benchmark(ROOT / manifest["benchmark"]["path"])
    check_general_exactifier(runtime_root)
    print(
        json.dumps(
            {
                "runtime_root": str(runtime_root),
                "runtime_files_verified": len(manifest["files"]),
                "dsl_inputs_verified": len(manifest["dsl_inputs"]),
                "pi_case_strict_exact_matches": "3/3",
                "algebraic_affine_synthetic": "passed",
                "insufficient_accuracy_rejection": "passed",
                "non_affine_rejection": "passed",
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
