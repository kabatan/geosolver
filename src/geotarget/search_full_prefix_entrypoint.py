"""Product wrapper that preserves the frozen champion search work graph.

The frozen worker remains the authority for proposal order, the shared wall
clock, per-lane callback quotas, endpoint replay, and artifact construction.
This wrapper may replace only the evaluator behind the frozen budget when a
whole-problem compiled evaluator has passed the general capability gate.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from geotarget.search_pool_worker_entrypoint import _activate_compiled_evaluator, _load


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--worker", type=Path, required=True)
    parser.add_argument("--case", type=Path, required=True)
    parser.add_argument("--case-sha256", required=True)
    parser.add_argument("--arm", required=True)
    parser.add_argument("--seconds", type=float, required=True)
    parser.add_argument("--starts", type=int, required=True)
    parser.add_argument("--callbacks-per-start", type=int, required=True)
    parser.add_argument("--aggregate-callback-cap", type=int, required=True)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--compiled-evaluator", action="store_true")
    arguments = parser.parse_args()

    search = _load(arguments.worker.resolve())
    base = search.BASE
    original_build_source_case = base.build_source_case
    compiled_metadata: dict[str, Any] = {
        "schema_version": "geotarget.compiled-residual-plan/v1",
        "enabled": False,
        "case_specific_routing": False,
        "qualification_mode": "disabled",
    }

    def build_source_case(document: Any, *, callback_cap: int, deadline: float):
        nonlocal compiled_metadata
        base_case, budget, evaluator = original_build_source_case(
            document,
            callback_cap=callback_cap,
            deadline=deadline,
        )
        if arguments.compiled_evaluator:
            evaluator, compiled_metadata = _activate_compiled_evaluator(
                evaluator,
                budget,
                source_sha256=arguments.case_sha256,
            )
        return base_case, budget, evaluator

    base.build_source_case = build_source_case
    sys.argv = [
        str(arguments.worker),
        "--case",
        str(arguments.case),
        "--case-sha256",
        arguments.case_sha256,
        "--arm",
        arguments.arm,
        "--seconds",
        str(arguments.seconds),
        "--starts",
        str(arguments.starts),
        "--callbacks-per-start",
        str(arguments.callbacks_per_start),
        "--aggregate-callback-cap",
        str(arguments.aggregate_callback_cap),
        "--seed",
        str(arguments.seed),
        "--output",
        str(arguments.output),
    ]
    base.main()

    artifact = json.loads(arguments.output.read_text(encoding="utf-8"))
    artifact["compiled_evaluator"] = compiled_metadata
    artifact["optimized_full_prefix"] = {
        "schema_version": "geotarget.optimized-full-prefix/v1",
        "frozen_work_graph_preserved": True,
        "frozen_clock_and_replay_preserved": True,
        "case_specific_routing": False,
    }
    arguments.output.write_text(
        json.dumps(artifact, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
