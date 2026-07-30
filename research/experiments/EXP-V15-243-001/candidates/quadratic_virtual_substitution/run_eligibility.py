#!/usr/bin/env python3
"""Aggregate-only conservative eligibility for exact quadratic VS."""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import sys
from typing import Any

import sympy as sp


ARCHIVE_ROOT = Path("/home/kabatan/work/solver-experiment-runtime/solver")
COMPILER = ARCHIVE_ROOT / "research/experiments/EXP-REAL61-002/algebraic_lane/compiler.py"
EXPECTED_COMPILER_SHA256 = "f127f7f1e2f93161e1353f07222e93ffacfa1c2dbd4e68e5b1fd23a8a3b10318"
DATASET = (
    ARCHIVE_ROOT
    / "research/experiments/EXP-OMC-V15-MERGED5-EVAL-001/inputs/omc_v15_merged_5files.audit-canonical.jsonl"
)
SPLIT = ARCHIVE_ROOT / "research/experiments/EXP-V15-243-001/benchmark/SPLIT_MANIFEST.json"
EXPECTED_SPLIT_SHA256 = "065b2602e515b16086768c5a60abf91248faee7ed0cb76b9d88d4c421bcbdf3f"
ROW_ID = re.compile(rb'"problem_id":"([^"\\]+)"')
SUPPORTED_RELATIONS = frozenset({"eq", "ne", "gt", "ge", "lt", "le"})
MAX_POLYNOMIAL_VARIABLES = 4
MAX_ATOMS = 16
MAX_RECONSTRUCTION_ENTRIES = 16


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _compiler():
    if not COMPILER.is_file() or _sha256(COMPILER) != EXPECTED_COMPILER_SHA256:
        raise RuntimeError("compiler digest mismatch")
    name = "geotarget_qvs_pinned_algebraic_compiler"
    specification = importlib.util.spec_from_file_location(name, COMPILER)
    if specification is None or specification.loader is None:
        raise RuntimeError("compiler load failed")
    module = importlib.util.module_from_spec(specification)
    sys.modules[name] = module
    specification.loader.exec_module(module)
    return module


def _document(formulation: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": "anonymous-qvs-source",
        "task": "solve",
        **{
            key: value
            for key, value in formulation.items()
            if key in {"variables", "bounds", "construction", "constraints", "guards", "answer", "post_process"}
        },
    }


def census(dataset: Path) -> dict[str, Any]:
    split_bytes = SPLIT.read_bytes()
    if hashlib.sha256(split_bytes).hexdigest() != EXPECTED_SPLIT_SHA256:
        raise RuntimeError("split digest mismatch")
    development_ids = frozenset(json.loads(split_bytes)["partitions"]["development"]["case_ids"])
    compiler = _compiler()
    payload = dataset.read_bytes()
    selected = skipped = 0
    stages = Counter()
    reasons = Counter()
    dimensions = Counter()
    atom_counts = Counter()
    degree_histogram = Counter()
    signatures = Counter()
    theoretical_quadratic = 0
    ready = 0
    for line in payload.splitlines():
        if not line.strip():
            continue
        match = ROW_ID.search(line)
        if match is None:
            raise RuntimeError("row identity missing")
        if match.group(1).decode() not in development_ids:
            skipped += 1
            continue
        selected += 1
        formulation = json.loads(line)["formulation"]
        try:
            artifact = compiler.compile_document(_document(formulation))
            stages["compiler_returned"] += 1
        except Exception:
            reasons["compiler-exception"] += 1
            continue
        if artifact.classification != "EXACT_SEMIALGEBRAIC" or artifact.unsupported:
            reasons["not-exact-semialgebraic"] += 1
            continue
        stages["exact_semialgebraic"] += 1
        symbols = [sp.Symbol(name) for name in artifact.variables]
        locals_ = {symbol.name: symbol for symbol in symbols}
        polynomials = []
        qq_quadratic = True
        texts = list(artifact.equations) + [item["expression"] for item in artifact.predicates]
        for text in texts:
            try:
                polynomial = sp.Poly(sp.sympify(text, locals=locals_), *symbols, domain=sp.QQ)
            except Exception:
                qq_quadratic = False
                reasons["non-QQ-polynomial-atom"] += 1
                break
            polynomials.append(polynomial)
            if polynomial.total_degree() > 2 or any(polynomial.degree(symbol) > 2 for symbol in symbols):
                qq_quadratic = False
                reasons["degree-above-quadratic"] += 1
                break
        if not qq_quadratic or any(item.get("relation") not in SUPPORTED_RELATIONS for item in artifact.predicates):
            continue
        theoretical_quadratic += 1
        stages["all_atoms_QQ_quadratic"] += 1
        variable_count = len(symbols)
        atom_count = len(texts)
        dimensions[str(variable_count)] += 1
        atom_counts[str(atom_count)] += 1
        degree_histogram[str(max((polynomial.total_degree() for polynomial in polynomials), default=0))] += 1
        if variable_count > MAX_POLYNOMIAL_VARIABLES:
            reasons["variable-cap"] += 1
            continue
        if atom_count > MAX_ATOMS:
            reasons["atom-cap"] += 1
            continue
        if len(artifact.reconstruction) > MAX_RECONSTRUCTION_ENTRIES:
            reasons["reconstruction-cap"] += 1
            continue
        ready += 1
        signature_payload = {
            "variables": variable_count,
            "atoms": atom_count,
            "degrees": sorted(polynomial.total_degree() for polynomial in polynomials),
            "relations": sorted(Counter(item["relation"] for item in artifact.predicates).items()),
            "reconstruction_count": len(artifact.reconstruction),
            "replay_count": len(artifact.replay_obligations),
        }
        signatures[
            hashlib.sha256(
                json.dumps(signature_payload, sort_keys=True, separators=(",", ":")).encode()
            ).hexdigest()[:16]
        ] += 1
    if selected != 145 or skipped != 102:
        raise RuntimeError("partition custody mismatch")
    return {
        "schema": "geotarget.quadratic-virtual-substitution-eligibility/v1",
        "authority": "TRUTH_FREE_AGGREGATE_ONLY_PINNED_EXACT_EXPORTER",
        "development_case_count": selected,
        "compiler_sha256": EXPECTED_COMPILER_SHA256,
        "exact_semialgebraic_count": stages["exact_semialgebraic"],
        "theoretical_all_QQ_quadratic_count": theoretical_quadratic,
        "conservative_ready_count": ready,
        "anonymous_structural_signature_count": len(signatures),
        "anonymous_signature_multiplicity_histogram": dict(sorted(Counter(signatures.values()).items())),
        "quadratic_variable_count_histogram": dict(sorted(dimensions.items(), key=lambda item: int(item[0]))),
        "quadratic_atom_count_histogram": dict(sorted(atom_counts.items(), key=lambda item: int(item[0]))),
        "maximum_degree_histogram": dict(sorted(degree_histogram.items())),
        "stage_counts": dict(sorted(stages.items())),
        "rejection_reason_histogram": dict(sorted(reasons.items())),
        "caps": {
            "maximum_polynomial_variables": MAX_POLYNOMIAL_VARIABLES,
            "maximum_atoms": MAX_ATOMS,
            "maximum_reconstruction_entries": MAX_RECONSTRUCTION_ENTRIES,
        },
        "gate": {"minimum_attempts": 4, "minimum_signatures": 2, "pass": ready >= 4 and len(signatures) >= 2},
        "nondevelopment_rows_skipped_without_json_deserialization": skipped,
        "validation_or_sealed_formulation_parsed": False,
        "individual_id_value_target_truth_or_outcome_emitted": False,
        "formal_execute_scorer_full98_or_truth_used": False,
        "interpretation_limit": (
            "Eligibility only. Virtual substitution, exact sample-term semantics, reconstruction, and untouched "
            "canonical replay are not implemented by this artifact. The six-case quadratic count is an upper bound."
        ),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=DATASET)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    result = census(arguments.dataset)
    arguments.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__": main()
