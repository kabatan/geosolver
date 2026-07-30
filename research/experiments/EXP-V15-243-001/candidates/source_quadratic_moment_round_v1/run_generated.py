#!/usr/bin/env python3
"""Generated target-free static readiness checks."""

from __future__ import annotations

import json
import os
from pathlib import Path

from source_only_scanner import scan_document


HERE = Path(__file__).resolve().parent


def source(names, constraints, *, construction=None, guards=None):
    return {
        "task": "solve",
        "variables": {"names": names},
        "construction": construction or [],
        "constraints": constraints,
        "guards": guards or [],
    }


def main() -> int:
    if os.sched_getaffinity(0) != {14}:
        raise RuntimeError("generated readiness must be pinned to CPU14")
    fixtures = {
        "direct-quadratic": source(["x"], [{"def": "x*x", "value": "1"}]),
        "disconnected-direct-quadratics": source(
            ["x", "y"],
            [{"def": "x*x", "value": "1"}, {"def": "y*y", "value": "4"}],
        ),
        "sqrt-aux-closure": source(
            ["x"], [{"def": "sqrt(x)", "value": "2"}]
        ),
        "finite-phase-pair": source(
            ["t"],
            [{"def": "Distance(P,Point(1,0))", "value": "0"}],
            construction=[
                {"name": "O", "expr": "Point(0,0)"},
                {"name": "C", "expr": "Circle(O,1)"},
                {"name": "P", "expr": "PointOnCircle(C,t)"},
            ],
            guards=["Bound(t,(0,1))"],
        ),
    }
    positive = {name: scan_document(document) for name, document in fixtures.items()}
    negative_fixtures = {
        "target-present": {**fixtures["direct-quadratic"], "answer": "x"},
        "degree-three-only": source(["x"], [{"def": "x**3", "value": "1"}]),
        "unused-source-variable": source(
            ["x", "y"], [{"def": "x*x", "value": "1"}]
        ),
        "non-QQ-only": source(
            ["x"], [{"def": "x", "value": "sqrt(2)"}]
        ),
        "linear-only": source(["x"], [{"def": "x", "value": "1"}]),
    }
    negative = {name: scan_document(document) for name, document in negative_fixtures.items()}
    checks = {
        "positive_ready": all(item.get("ready") is True for item in positive.values()),
        "negative_rejected": all(item.get("ready") is False for item in negative.values()),
        "target_never_read": all(
            item.get("target_read") is False for item in [*positive.values(), *negative.values()]
        ),
        "authority_never_emitted": all(
            item.get("authority_pass") is False and item.get("target_release") is False
            for item in [*positive.values(), *negative.values()]
        ),
        "phase_mapping_exercised": positive["finite-phase-pair"].get("phase_mapping_count") == 1,
        "aux_closure_exercised": positive["sqrt-aux-closure"].get(
            "all_selected_aux_definitions_closed"
        )
        is True,
    }
    result = {
        "schema_version": "geotarget.source-quadratic-moment-generated/v1",
        "cpu_affinity": sorted(os.sched_getaffinity(0)),
        "checks": checks,
        "positive_statuses": {name: item["status"] for name, item in positive.items()},
        "negative_reasons": {name: item["reason"] for name, item in negative.items()},
        "individual_real_source_records_retained": False,
        "truth_used": False,
        "formal_scorer_used": False,
        "passed": all(checks.values()),
    }
    (HERE / "GENERATED_RESULT.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
