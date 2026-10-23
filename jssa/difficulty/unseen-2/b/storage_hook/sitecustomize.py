"""Storage-only interception of completed CLI output; no solver imports/hooks.

Path.write_text is intercepted ONLY for Q30b's public .solver.tmp.json output,
after solve_problem has returned. The internal worker and commit timing remain
unmodified. Public answers and all research_runner scoring fields are retained.
"""
import hashlib
import json
from pathlib import Path

DEST = Path(__file__).resolve().parents[1] / "execution" / "runs"
ORIGINAL_WRITE_TEXT = Path.write_text


def sample(value, depth=0):
    if isinstance(value, dict):
        if depth >= 7:
            return {"omitted_keys": list(value)[:40], "key_count": len(value)}
        items = list(value.items())
        out = {k: sample(v, depth + 1) for k, v in items[:40]}
        if len(items) > 40:
            out["omitted_key_count"] = len(items) - 40
        return out
    if isinstance(value, list):
        if len(value) > 4:
            return {"original_count": len(value), "first_3": [sample(v, depth + 1) for v in value[:3]],
                    "last_1": [sample(value[-1], depth + 1)]}
        return [sample(v, depth + 1) for v in value]
    if isinstance(value, str) and len(value) > 700:
        return value[:700] + f" [truncated: {len(value)} chars]"
    return value


def compact_result(result, original_text):
    diagnostics = result.get("diagnostics") or {}
    pipeline = diagnostics.get("pipeline_summary") or {}
    assembly = pipeline.get("exact_assembly") or {}
    kept = {k: diagnostics[k] for k in ("process_info", "phase_timings", "counters", "rejection_tags",
            "numeric_feasible", "exact_identified", "public_solved", "config_snapshot") if k in diagnostics}
    kept["pipeline_summary"] = {
        "exact_assembly": {k: assembly[k] for k in ("numeric_feasible_count", "rejection_tags") if k in assembly},
        "verification_records": [True] if pipeline.get("verification_records") else [],
    }
    evidence = {k: sample(v) for k, v in diagnostics.items() if k != "pipeline_summary"}
    evidence["pipeline_summary"] = {k: sample(v) for k, v in pipeline.items() if k not in
        {"debug_candidates", "candidate_ledger"}}
    output = {k: v for k, v in result.items() if k != "diagnostics"}
    output["diagnostics"] = kept
    output["q30b_storage_summary"] = {
        "schema": "completed-cli-output-storage-v2", "original_utf8_bytes": len(original_text.encode()),
        "original_sha256": hashlib.sha256(original_text.encode()).hexdigest(),
        "solver_computation_modified": False, "worker_artifact_commit_modified": False,
        "diagnostic_evidence": evidence,
    }
    payload = json.dumps(output, ensure_ascii=False, allow_nan=False, separators=(",", ":")) + "\n"
    if len(payload.encode()) >= 4_900_000:
        output["q30b_storage_summary"]["diagnostic_evidence"] = {
            "omitted_due_to_size": True, "original_keys": list(diagnostics)}
        payload = json.dumps(output, ensure_ascii=False, allow_nan=False, separators=(",", ":")) + "\n"
    return payload


def write_completed_output(self, data, *args, **kwargs):
    if self.name.endswith(".solver.tmp.json") and self.parent.parent == DEST:
        result = json.loads(data)
        payload = compact_result(result, data)
        ORIGINAL_WRITE_TEXT(self, payload, *args, **kwargs)
        return len(data)
    return ORIGINAL_WRITE_TEXT(self, data, *args, **kwargs)


Path.write_text = write_completed_output
