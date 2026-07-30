from __future__ import annotations

import hashlib
import json
from pathlib import Path

from connector import c3v, connect
from generated_cases import cases


def main() -> int:
    rows = []
    for item in cases():
        payload = f"unchanged-baseline:{item.name}".encode()
        result = connect(item.problem, total_work=8, baseline_payload=payload)
        rows.append(
            {
                "name": item.name,
                "expected_authority": item.expected_authority,
                "observed_authority": result.authority,
                "status": result.status,
                "reason": result.reason,
                "baseline_work": result.baseline_work,
                "side_work": result.side_work,
                "baseline_payload_preserved": result.baseline_payload == payload,
                "baseline_payload_sha256": hashlib.sha256(result.baseline_payload).hexdigest(),
                "source_certificate_self_digest_valid": _source_digest_valid(result.source_certificate),
                "target_link_self_digest_valid": bool(result.target_link and c3v.verify_artifact(result.target_link)),
            }
        )
    positives = [row for row in rows if row["expected_authority"]]
    negatives = [row for row in rows if not row["expected_authority"]]
    report = {
        "schema_version": "geotarget.krawczyk-c3v-generated-d0/v1",
        "source_only": True,
        "truth_or_case_identity_used": False,
        "real_corpus_used": False,
        "positive_verified": sum(row["observed_authority"] for row in positives),
        "positive_total": len(positives),
        "negative_false_authority": sum(row["observed_authority"] for row in negatives),
        "negative_total": len(negatives),
        "metamorphic_permutation_scale_preserved": rows[0]["observed_authority"] == rows[3]["observed_authority"],
        "baseline_minimum_fraction": 0.75,
        "all_baseline_payloads_preserved": all(row["baseline_payload_preserved"] for row in rows),
        "rows": rows,
    }
    output = Path(__file__).with_name("GENERATED_D0.json")
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps(report, sort_keys=True))
    return 0 if (
        report["positive_verified"] == report["positive_total"]
        and report["negative_false_authority"] == 0
        and report["metamorphic_permutation_scale_preserved"]
        and report["all_baseline_payloads_preserved"]
    ) else 1


def _source_digest_valid(document: dict | None) -> bool:
    if not document or not isinstance(document.get("artifact_sha256"), str):
        return False
    body = dict(document)
    expected = body.pop("artifact_sha256")
    return c3v.canonical_sha256(body) == expected


if __name__ == "__main__":
    raise SystemExit(main())
