#!/usr/bin/env python3
"""Aggregate-only real applicability gate for the sparse target upper bound.

This deliberately emits no source labels, expressions, factors, endpoints, or
case outcomes.  Stored ordinary target relations are only proposals; the
candidate proves a product identity and still claims neither per-root
existence nor target-set completeness.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import time

from candidate import prove_multi_target_identity


ADAPTER = Path(
    "/home/kabatan/work/solver-experiment-runtime/solver/research/experiments/"
    "EXP-V15-243-001/candidates/c3v_target_link_modernization/v15_adapter.py"
)
ADAPTER_SHA256 = "09a9f202e4b45bc50339185609f033530c2919ee0db9345e32162e1971f1b2be"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_adapter():
    if sha256(ADAPTER) != ADAPTER_SHA256:
        raise RuntimeError("frozen source-to-polynomial adapter changed")
    name = "geotarget_sparse_upper_real_v15_adapter"
    specification = importlib.util.spec_from_file_location(name, ADAPTER)
    if specification is None or specification.loader is None:
        raise RuntimeError("cannot load frozen source adapter")
    module = importlib.util.module_from_spec(specification)
    sys.modules[name] = module
    specification.loader.exec_module(module)
    return module


def authority_factor(path: Path) -> tuple[str, tuple[int, ...]] | None:
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
        final = document["final_result"]
        target = final["target_authority"]
        source_sha = final["source_raw_sha256"]
        coefficients = tuple(target["minimal_polynomial_high_to_low"])
    except (KeyError, TypeError, ValueError, json.JSONDecodeError):
        return None
    if not (
        document.get("authority_pass") is True
        and final.get("status") == "TARGET_AUTHORITY_READY"
        and final.get("authority_pass") is True
        and isinstance(source_sha, str)
        and len(source_sha) == 64
        and len(coefficients) >= 2
        and all(isinstance(value, int) and not isinstance(value, bool) for value in coefficients)
        and target.get("primitive") is True
        and target.get("square_free") is True
        and target.get("irreducible_over_Q") is True
    ):
        return None
    return source_sha, coefficients


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--control-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    started = time.process_time()
    adapter = load_adapter()
    grouped: dict[str, dict[tuple[int, ...], tuple[str, Path]]] = {}
    scanned = 0
    accepted = 0
    for path in sorted((arguments.control_root / "artifacts").rglob("authority.json")):
        scanned += 1
        factor = authority_factor(path)
        if factor is None:
            continue
        accepted += 1
        source_sha, coefficients = factor
        case_dir = path.relative_to(arguments.control_root / "artifacts").parts[0]
        source_path = arguments.control_root / "inputs" / f"{case_dir}.json"
        if not source_path.is_file() or sha256(source_path) != source_sha:
            continue
        artifact_sha = sha256(path)
        previous = grouped.setdefault(source_sha, {}).get(coefficients)
        if previous is None or artifact_sha < previous[0]:
            grouped[source_sha][coefficients] = (artifact_sha, source_path)

    eligible = 0
    verified = 0
    rejected = 0
    compiler_rejected = 0
    signature_hashes: set[str] = set()
    for source_sha in sorted(grouped):
        factors = grouped[source_sha]
        if len(factors) < 2:
            continue
        eligible += 1
        ordered = sorted(factors.items())
        source_path = ordered[0][1][1]
        try:
            source = json.loads(source_path.read_text(encoding="utf-8"))
            joint = adapter.compile_joint_system(source)
            if not joint.prototype_cap_eligible or joint.target_expression is None:
                compiler_rejected += 1
                continue
            result = prove_multi_target_identity(
                variables=joint.variables,
                active_equations=joint.equations,
                all_equations=joint.equations,
                target_expression=joint.target_expression,
                factors_high_to_low=[list(item[0]) for item in ordered],
                descriptor_artifact_sha256s=[item[1][0] for item in ordered],
                source_sha256=source_sha,
            )
            if result.get("status") == "IDENTITY_VERIFIED":
                verified += 1
                signature = {
                    "variable_count": len(joint.variables),
                    "equation_count": len(joint.equations),
                    "factor_count": len(ordered),
                    "product_degree": result.get("product_degree"),
                }
                signature_hashes.add(
                    hashlib.sha256(
                        json.dumps(signature, sort_keys=True, separators=(",", ":")).encode()
                    ).hexdigest()
                )
            else:
                rejected += 1
        except Exception:
            rejected += 1

    output = {
        "schema_version": "geotarget.multi-target-sparse-cofactor-real-applicability/v1",
        "decision": (
            "GO_REAL_WITNESS_JOIN"
            if verified >= 4 and len(signature_hashes) >= 2
            else "STOP_REAL_APPLICABILITY"
        ),
        "authority_artifact_count_scanned": scanned,
        "ordinary_authority_artifact_count_accepted": accepted,
        "multi_factor_source_count": eligible,
        "compiler_rejected_source_count": compiler_rejected,
        "product_identity_verified_source_count": verified,
        "product_identity_rejected_source_count": rejected,
        "mechanical_signature_count": len(signature_hashes),
        "proposal_authority": False,
        "target_release": False,
        "target_set_completeness_claim": False,
        "per_root_existence_required": True,
        "truth_case_family_outcome_routing": False,
        "individual_source_factor_endpoint_records_emitted": False,
        "control_root_sha256": hashlib.sha256(
            str(arguments.control_root.resolve()).encode()
        ).hexdigest(),
        "adapter_sha256": ADAPTER_SHA256,
        "cpu_seconds": time.process_time() - started,
    }
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n")
    print(json.dumps(output, sort_keys=True))
    return 0 if output["decision"].startswith("GO_") else 1


if __name__ == "__main__":
    raise SystemExit(main())
