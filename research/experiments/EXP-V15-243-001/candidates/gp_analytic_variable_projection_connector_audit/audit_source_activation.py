#!/usr/bin/env python3
"""Truth-blind source-only activation gate for analytic variable projection."""

from __future__ import annotations

from collections import Counter
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

from source_affinity import find_affine_blocks


EXPECTED_DEVELOPMENT_SHA256 = "c150bb352fc905dc4eead8a56ec50125d6dd2409d2de14ccd91a502836ea8511"
EXPECTED_FORMULATION_COUNT = 145
DEFAULT_DATASET = Path(
    "/home/kabatan/work/solver-artifacts/experiment-freeze-20260727/"
    "product-145-20260727-v4/development145.jsonl"
)
FROZEN_RUNTIME = Path("/home/kabatan/work/solver-experiment-runtime/solver")
TYPED_CANDIDATE = (
    FROZEN_RUNTIME
    / "research/experiments/EXP-V15-243-001/candidates/"
    "whole_evaluator_compiler/ssa_jvp_wave2/candidate.py"
)
GEOSOLVER_SOURCE = FROZEN_RUNTIME.parent / "geosolver/src"


def _load(name: str, path: Path):
    specification = importlib.util.spec_from_file_location(name, path)
    if specification is None or specification.loader is None:
        raise ImportError(path)
    module = importlib.util.module_from_spec(specification)
    sys.modules[name] = module
    specification.loader.exec_module(module)
    return module


def audit(dataset: Path = DEFAULT_DATASET) -> dict[str, object]:
    repository = Path(__file__).resolve().parents[5]
    poly_directory = repository / "research/experiments/EXP-POLY-001"
    interval_directory = repository / "research/experiments/EXP-INTERVAL-001"
    for path in (poly_directory, interval_directory, FROZEN_RUNTIME, GEOSOLVER_SOURCE):
        if str(path) not in sys.path:
            sys.path.insert(0, str(path))

    from audit_development_formulations import formulation_bytes
    from formulation_audit import project_formulation
    from geosolver._internal.pipeline.evaluator.ir_evaluator import build_ir_evaluator
    from geosolver._internal.pipeline.problem.load_problem_bundle import load_problem_bundle

    typed = _load("_gp_connector_static_typed_ssa", TYPED_CANDIDATE)
    raw_container = dataset.read_bytes()
    container_sha256 = hashlib.sha256(raw_container).hexdigest()
    if container_sha256 != EXPECTED_DEVELOPMENT_SHA256:
        raise RuntimeError("development source container digest mismatch")

    classifications: Counter[str] = Counter()
    clusters: Counter[tuple[object, ...]] = Counter()
    inner_dimensions: Counter[int] = Counter()
    affected_rows: Counter[int] = Counter()
    formulation_digest = hashlib.sha256()
    count = typed_programs = activation_count = 0
    for row in raw_container.splitlines():
        if not row.strip():
            continue
        source = formulation_bytes(row)
        formulation_digest.update(len(source).to_bytes(8, "big"))
        formulation_digest.update(source)
        document = project_formulation(source)
        anonymous_document = {
            "id": "STATIC-CENSUS-ANONYMOUS",
            **document,
            "answer": "0",
            "post_process": "",
        }
        count += 1
        try:
            evaluator = build_ir_evaluator(
                load_problem_bundle(anonymous_document, prefer_fast=False)
            )
            program = typed.compile_typed_program(evaluator)
        except Exception:
            classifications["typed-unsupported"] += 1
            continue
        typed_programs += 1
        plans = find_affine_blocks(program)
        if not plans:
            classifications["typed-no-affine-block"] += 1
            continue
        classifications["applicable"] += 1
        activation_count += 1
        best = max(plans, key=lambda item: (item[2], item[3], item[4], item[5]))
        clusters[best] += 1
        inner_dimensions[int(best[2])] += 1
        affected_rows[int(best[3])] += 1

    if count != EXPECTED_FORMULATION_COUNT:
        raise RuntimeError("development formulation count mismatch")
    cluster_records = [
        {
            "signature": {
                "variable_dimension": signature[0],
                "residual_dimension": signature[1],
                "inner_dimension": signature[2],
                "affected_rows": signature[3],
                "inner_incidence_histogram": [list(item) for item in signature[4]],
                "outer_incidence_histogram": [list(item) for item in signature[5]],
            },
            "multiplicity": multiplicity,
        }
        for signature, multiplicity in sorted(clusters.items())
    ]
    return {
        "schema_version": "geotarget.gp-analytic-connector-source-gate/v1",
        "authority": {
            "development_container_sha256": container_sha256,
            "formulation_stream_sha256": formulation_digest.hexdigest(),
            "typed_ssa_candidate_sha256": hashlib.sha256(TYPED_CANDIDATE.read_bytes()).hexdigest(),
        },
        "custody": {
            "formulations": count,
            "row_objects_deserialized": False,
            "sibling_values_deserialized": False,
            "problem_ids_retained_or_reported": False,
            "source_answer_target_postprocess_decoded": False,
            "numeric_evaluator_calls": 0,
            "scorer_or_previous_outcome_reads": 0,
            "validation_or_sealed_access": False,
            "formal_solver_run": False,
        },
        "gate": {
            "required_anonymous_graph_clusters": 2,
            "typed_programs": typed_programs,
            "activation_count": activation_count,
            "anonymous_graph_cluster_count": len(clusters),
            "passed": len(clusters) >= 2,
            "classification_counts": dict(sorted(classifications.items())),
            "inner_dimension_counts": {
                str(key): value for key, value in sorted(inner_dimensions.items())
            },
            "affected_row_counts": {
                str(key): value for key, value in sorted(affected_rows.items())
            },
            "anonymous_graph_clusters": cluster_records,
        },
        "decision": {
            "status": "STOP_SOURCE_ACTIVATION_GATE",
            "connector_created": False,
            "worker_or_portfolio_changed": False,
            "reason": "only one anonymous source-DAG graph cluster passed the exact joint-affinity and structural-matching gate",
        },
    }


if __name__ == "__main__":
    print(json.dumps(audit(), indent=2, sort_keys=True))
