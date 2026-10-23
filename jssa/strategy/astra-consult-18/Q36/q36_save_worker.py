"""Storage-only adapter around the unchanged frozen standard worker.

It executes the original worker main/execute. Only completed-artifact saving
is adapted, as required by the registered 5 MB limit. All public answers,
status/error fields, budgets and individual exact-answer origins are retained.
"""
import os
from pathlib import Path

from geosolver.runtime import worker
from geosolver.runtime.artifact_commit import atomic_write


def compact_artifact(artifact):
    diagnostic = artifact.diagnostics
    summary = diagnostic.get("pipeline_summary", {})
    sources = []
    for row in summary.get("exact_candidate_records", []):
        exact = row.get("exact_result", {})
        candidate = row.get("candidate", {})
        sources.append({
            "descriptor": exact.get("descriptor"),
            "selected_exact_value": exact.get("selected_exact_value"),
            "exact_status": exact.get("exact_status"),
            "identification_method": exact.get("identification_method"),
            "candidate_uid": candidate.get("candidate_uid"),
            "revision": candidate.get("revision"),
            "origin_phase": candidate.get("candidate_key", {}).get("phase"),
            "origin_backend": candidate.get("candidate_key", {}).get("backend"),
        })
    representative_id = summary.get("answer_source_candidate_id")
    representative = next((c for c in artifact.candidate_records if c.get("candidate_id") == representative_id), {})
    minimal = {k: v for k, v in diagnostic.items() if k != "pipeline_summary"}
    minimal.update(q36_value_sources=sources, q36_storage_compacted=True,
        original_candidate_record_count=len(artifact.candidate_records),
        original_pipeline_summary_keys=list(summary),
        representative_source={k: representative.get(k) for k in ("candidate_uid", "origin_phase", "origin_backend", "revision")},
        pipeline_summary={k: summary[k] for k in ("exact_assembly", "refinement", "answer_source_candidate_id", "answer_candidate_values", "answer_extraction_candidate_ids") if k in summary})
    return artifact.model_copy(update={"diagnostics": minimal, "candidate_records": []})


def save_completed(path, artifact):
    compact = compact_artifact(artifact)
    # Keep the original request-bound receipt and its deadline verification.
    atomic_write(path, compact)
    # A saved final set remains auditable even if the public parent later times out.
    target = os.environ.get("Q36_COMPLETED_SET_PATH")
    if target:
        from stage2 import save
        save(Path(target), compact.model_dump(mode="json"))


if __name__ == "__main__":
    worker._atomic_write = save_completed
    raise SystemExit(worker.main())
