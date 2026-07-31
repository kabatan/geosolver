#!/usr/bin/env python3
"""Generated static gate for barycentric area quotient proposals."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import candidate


HERE = Path(__file__).resolve().parent


def _case(scale, tx, ty, answer):
    qx, qy = tx + scale / 4, ty + scale / 2
    return {
        "task": "solve",
        "variables": {"names": ["x", "y"]},
        "bounds": [[tx - scale, tx + 2 * scale], [ty - scale, ty + 2 * scale]],
        "construction": [
            {"name": "A", "expr": f"Point({tx},{ty})"},
            {"name": "B", "expr": f"Point({tx+scale},{ty})"},
            {"name": "C", "expr": f"Point({tx},{ty+scale})"},
            {"name": "Q", "expr": "Point(x,y)"},
        ],
        "constraints": [
            {"def": "x", "value": str(qx)},
            {"def": "y", "value": str(qy)},
        ],
        "guards": [f"AssumeGt(x,{tx-scale})"],
        "answer": answer,
        "post_process": "",
    }, [qx, qy]


def run():
    shapes = (
        "Area(A,B,Q)",
        "Area(A,B,C,Q)",
        "2*Area(A,B,Q)+Area(A,Q,C)",
    )
    records = []
    for answer in shapes:
        source, endpoint = _case(1, 0, 0, answer)
        result = candidate.propose(source, endpoint)
        records.append(
            {
                "ready": result["status"] == "PROPOSAL_READY_HOLD",
                "proposal_count": result["proposal_count"],
                "replay_all": bool(result["proposals"])
                and all(
                    proposal["untouched_source_raw_target_replay_pass"]
                    for proposal in result["proposals"]
                ),
                "authority_pass": result["authority_pass"],
                "target_release": result["target_release"],
            }
        )
    base_source, base_endpoint = _case(1, 0, 0, shapes[0])
    moved_source, moved_endpoint = _case(8, 13, -7, shapes[0])
    base = candidate.propose(base_source, base_endpoint)
    moved = candidate.propose(moved_source, moved_endpoint)
    wrong = candidate.propose(base_source, [0.251, 0.5])
    result = {
        "schema_version": "geotarget.barycentric-area-quotient-generated/v1",
        "positive_total": len(records),
        "positive_ready": sum(record["ready"] for record in records),
        "positive_full_replay_all": sum(record["replay_all"] for record in records),
        "translation_scale_barycentric_signature_invariant": (
            base.get("barycentric_signature_sha256")
            == moved.get("barycentric_signature_sha256")
        ),
        "wrong_endpoint_fell_back": wrong["status"]
        == "NOT_APPLICABLE_BASELINE_FALLBACK",
        "authority_pass_count": sum(record["authority_pass"] for record in records),
        "target_release_count": sum(record["target_release"] for record in records),
        "truth_score_outcome_used": False,
        "records": records,
        "hashes": {
            name: hashlib.sha256((HERE / name).read_bytes()).hexdigest()
            for name in ("candidate.py", "run_generated.py")
        },
    }
    result["decision"] = (
        "GO_STATIC_TEST"
        if (
            result["positive_ready"] == len(records)
            and result["positive_full_replay_all"] == len(records)
            and result["translation_scale_barycentric_signature_invariant"]
            and result["wrong_endpoint_fell_back"]
            and result["authority_pass_count"] == 0
            and result["target_release_count"] == 0
        )
        else "STOP_STATIC_TEST"
    )
    return result


def main():
    result = run()
    (HERE / "GENERATED_RESULT.json").write_text(
        json.dumps(result, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({key: value for key, value in result.items() if key != "records"}, indent=2))
    if result["decision"] != "GO_STATIC_TEST":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
